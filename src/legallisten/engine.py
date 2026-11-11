"""LegalListen consultation engine: Speak or Type → Understand → Cross-question → Build the Case Graph →
Identify the law → Explain → Clarify doubts → Recommend next steps; and keep updating on new information."""

from __future__ import annotations

import datetime as dt
import re

from . import consult, followup, graph, policy
from .i18n import t
from .knowledge import is_urgent, kb
from .llm import LLM, LLMError, lang_kw, prompt
from .nlu import rules as R
from .nlu.cues import _is_negative
from .nlu.cues import match as cue_match
from .nlu.extract import Extraction, ElementUpdate, extract, pending_element_guess, personal_law_of
from .provisions import cards
from .state import CaseState, Chip, Contradiction, EvidenceState, Message, Pending, Person, RiskState, Statement

ASR_CONFIDENCE_MIN = 0.6
LATE_ISSUE_MIN = 0.7        # a new issue raised mid-consultation needs a strong cue
SAME_AREA_MIN = 0.6         # ... unless it is in the same legal area as the current issues


def _negative(text: str) -> bool:
    return _is_negative(" " + text.lower() + " ")
MAX_LEN = 4000


class Engine:
    def __init__(self, llm: LLM | None = None):
        self.k = kb()
        self.llm = llm

    # ---------------------------------------------------------------- session
    def start(self, lang: str = "en", use_llm: bool = False, conversation_date: str | None = None) -> CaseState:
        st = CaseState(lang=lang if lang in ("en", "kn", "hi") else "en", use_llm=bool(use_llm and self.llm))
        if conversation_date:
            st.conversation_date = conversation_date
        st.say(t("greeting", st.lang), kind="message", source="system")
        return st

    def _llm(self, st: CaseState) -> LLM | None:
        return self.llm if (st.use_llm and self.llm is not None) else None

    # ---------------------------------------------------------------- one turn
    def handle(self, st: CaseState, text: str, source: str = "text", asr_confidence: float | None = None,
               chip: str | None = None) -> list[Message]:
        text = (text or "").strip()[:MAX_LEN]
        before = len(st.messages)
        st.turn += 1
        st.updated = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        if not chip and text and st.pending:          # typed the text of one of the offered options
            norm = lambda x: re.sub(r"[\W_]+", " ", x.lower()).strip()  # noqa: E731
            hit = next((c for c in st.pending.chips if norm(c.label) == norm(text)), None)
            if hit:
                chip = hit.id
        if chip and chip.startswith("ask:"):           # quick follow-up buttons under the consultation card
            label = text or t("fu_hint_" + {"next_steps": "next", "documents": "docs", "where": "where", "laws": "laws"}.get(chip[4:], "next"), st.lang)
            st.messages.append(Message(role="user", text=label, turn=st.turn, source="option", lang=st.lang))
            st.notes.append(f"_followup:{chip[4:]}:")
            st.notes.append(f"_fq:{label}")
            self._respond(st)
            return st.messages[before:]
        if chip and st.pending and not any(c.id == chip for c in st.pending.chips):
            chip = None                      # stale option from an earlier question: treat as text
        if chip and st.pending:
            label = next((c.label for c in st.pending.chips if c.id == chip), text or chip)
            st.messages.append(Message(role="user", text=label, turn=st.turn, source="option", lang=st.lang))
            self._apply_chip(st, chip, label)
        elif text:
            variant = R.detect_variant(text)
            st.input_variant = st.input_variant or variant
            st.messages.append(Message(role="user", text=text, turn=st.turn, source="voice" if source == "voice" else "text",
                                       asr_confidence=asr_confidence, variant=variant, lang=R.base_lang(variant)))
            if source == "voice" and asr_confidence is not None and asr_confidence < ASR_CONFIDENCE_MIN:
                st.pending = Pending(kind="confirm_transcript", data={"text": text, "prev": st.pending.model_dump() if st.pending else None},
                                     chips=[Chip(id="tr:yes", label=t("yes_correct", st.lang)), Chip(id="tr:no", label=t("no", st.lang))])
                st.say(t("unclear_audio", st.lang, t=text), kind="clarify", chips=st.pending.chips)
                return st.messages[before:]
            self._process_text(st, text)
        else:
            st.turn -= 1
            return []
        self._respond(st)
        return st.messages[before:]

    # ------------------------------------------------------------ chips
    def _apply_chip(self, st: CaseState, chip: str, label: str) -> None:
        p = st.pending
        st.pending = None
        if p.kind == "confirm_transcript":
            if chip == "tr:yes":
                if p.data.get("prev"):
                    st.pending = Pending(**p.data["prev"])
                self._process_text(st, p.data["text"])
            else:
                if p.data.get("prev"):
                    st.pending = Pending(**p.data["prev"])
                st.notes.append("transcript rejected by client")
                st.say(t("unclear_audio", st.lang, t="…").split("?")[-1].strip() or t("need_more", st.lang), kind="clarify")
                st.notes.append("_skip_respond")
            return
        if p.kind == "element":
            val = {"el:sat": "satisfied", "el:con": "contradicted", "dk": "unknown"}.get(chip)
            if val:
                self._apply_element(st, ElementUpdate(p.key, val, label), source="option")
                self._ack(st, val)
        elif p.kind == "evidence":
            avail = {"ev:held": "held", "ev:missing": "missing"}.get(chip)
            if avail:
                self._apply_evidence(st, p.key, avail, label)
            self._ack(st, "unknown" if chip == "dk" else "satisfied")
        elif p.kind == "date":
            if chip in ("date:old", "date:new"):
                st.law_regime = chip.split(":")[1]
                st.incident_date_text = label
            self._ack(st, "unknown" if chip == "dk" else "satisfied")
        elif p.kind == "personal_law":
            st.personal_law = chip.split(":", 1)[1] if chip.startswith("pl:") else "skipped"
            self._ack(st, "satisfied")
        elif p.kind == "safety":
            st.safety_checked = True
            if chip == "safe:no":
                st.safety_unsafe = True
                st.say(t("unsafe_reply", st.lang), kind="alert")
        elif p.kind == "contradiction":
            c = next((c for c in st.contradictions if c.id == p.key), None)
            if c:
                self._resolve_contradiction(st, c, {"c:first": "first", "c:second": "second"}.get(chip, "unsure"))
        elif p.kind == "issue_choice":
            issue = chip.split(":", 1)[1]
            if issue in self.k.issues:
                st.issue_prior[issue] = 0.75
                self._rescan(st, issue)
            else:
                st.notes.append("_tell_more")

    def _ack(self, st: CaseState, val: str) -> None:
        st.notes.append("_ack_unknown" if val == "unknown" else "_ack")

    # ------------------------------------------------------------ free text
    def _process_text(self, st: CaseState, text: str) -> None:
        conv = dt.date.fromisoformat(st.conversation_date)
        ex: Extraction = extract(text, conv, set(st.issue_prior), self._llm(st), self._summary_for_llm(st),
                                 self._pending_desc(st), context=self._user_text(st))
        if ex.backend == "llm":
            st.llm_calls += 1
        if ex.reexplain:
            st.notes.append("_reexplain")
            return
        if ex.unclear and ex.backend == "llm":
            st.say(t("unclear_audio", st.lang, t=text), kind="clarify")
            st.notes.append("_skip_respond")
            return
        p = st.pending
        if p is not None and p.kind == "issue_choice":
            st.pending = p = None
        answered = False
        if p is not None:
            answered = self._answer_pending(st, p, text, ex)
        known_before = {k for k, e in st.elements.items() if e.value} | set(st.evidence)
        self._merge(st, ex, text)
        learned = ({k for k, e in st.elements.items() if e.value} | set(st.evidence)) - known_before
        fu = followup.detect(text) if not answered else None
        if fu and not learned and ex.answer is None and st.issue_prior:
            # a question to LegalListen, not an answer: reply in the chat and keep the pending question open
            st.notes.append(f"_followup:{fu[0]}:{fu[1] or ''}")
            st.notes.append(f"_fq:{text[:500]}")
            if p is not None:
                st.pending = p
            return
        if not answered and not learned and len(text.split()) >= 3 and ex.answer is None and \
                (p is not None or st.consultation_ready):
            st.other_facts.append(text[:400])          # keep what the client said, even if it fits no question yet
            st.notes.append("_noted")
        if p is not None and not answered and p.kind in ("element", "evidence", "date", "personal_law"):
            # the client said something else; keep the question open once, then move on
            if p.reask < 1:
                p.reask += 1
                st.pending = p
            else:
                if p.kind == "element":
                    st.element(p.key).asked = True
                st.pending = None
        elif answered:
            st.pending = None

    def _answer_pending(self, st: CaseState, p: Pending, text: str, ex: Extraction) -> bool:
        ans = ex.answer
        if p.kind == "element":
            el = self.k.elements[p.key]
            if any(u.key == p.key for u in ex.elements):
                return True
            if ans == "dont_know":
                self._apply_element(st, ElementUpdate(p.key, "unknown", text), source="answer")
                self._ack(st, "unknown")
                return True
            cue = cue_match(text, p.key)
            if cue:                                      # the client's own words are the most specific signal
                self._apply_element(st, ElementUpdate(p.key, cue[0], text), source="answer", correction=ex.correction)
                self._ack(st, cue[0])
                return True
            yes_val = el.yes_value
            short_no = ans is None and len(text.split()) <= 6 and _negative(text)
            if yes_val and (ans in ("yes", "no") or short_no):
                no_val = "contradicted" if yes_val == "satisfied" else "satisfied"
                val = yes_val if ans == "yes" else no_val
                self._apply_element(st, ElementUpdate(p.key, val, text), source="answer", correction=ex.correction)
                self._ack(st, val)
                return True
            guess = pending_element_guess(ex, p.key, text)
            if guess:
                self._apply_element(st, ElementUpdate(p.key, guess, text), source="answer", correction=ex.correction)
                self._ack(st, guess)
                return True
            return False
        if p.kind == "evidence":
            if any(e[0] == p.key for e in ex.evidence):
                return True
            if ans in ("yes", "no"):
                self._apply_evidence(st, p.key, "held" if ans == "yes" else "missing", text)
                self._ack(st, "satisfied")
                return True
            if ans == "dont_know":
                self._ack(st, "unknown")
                return True
            return False
        if p.kind == "date":
            low = text.lower()
            if re.search(r"\b(before|earlier than)\b|ಮೊದಲು|ಮುಂಚೆ|से पहले|pehle", low) and re.search(r"2024|july|ಜುಲೈ|जुलाई", low):
                st.law_regime, st.incident_date_text = "old", text
                self._ack(st, "satisfied")
                return True
            if re.search(r"\b(after|since|on or after)\b|ನಂತರ|ಆಮೇಲೆ|के बाद|baad", low) and re.search(r"2024|july|ಜುಲೈ|जुलाई", low):
                st.law_regime, st.incident_date_text = "new", text
                self._ack(st, "satisfied")
                return True
            if ex.dates:
                d = ex.dates[0][0]
                self._set_incident_date(st, d)
                self._ack(st, "satisfied")
                return st.law_regime is not None
            if ans == "dont_know":
                self._ack(st, "unknown")
                return True
            return False
        if p.kind == "personal_law":
            pl = ex.personal_law or personal_law_of(text)
            if pl:
                st.personal_law = pl
                self._ack(st, "satisfied")
                return True
            if ans in ("no", "dont_know"):
                st.personal_law = "skipped"
                return True
            return False
        if p.kind == "safety":
            st.safety_checked = True
            if ans == "no" or R.safety_negative(text):
                st.safety_unsafe = True
                st.say(t("unsafe_reply", st.lang), kind="alert")
            return True
        if p.kind == "contradiction":
            c = next((c for c in st.contradictions if c.id == p.key), None)
            if c is None:
                return True
            for u in ex.elements:
                if u.key == c.key and u.value in ("satisfied", "contradicted"):
                    self._resolve_contradiction(st, c, "first" if u.value == c.a.value else "second", quote=text)
                    return True
            if ans == "dont_know":
                self._resolve_contradiction(st, c, "unsure")
                return True
            self._resolve_contradiction(st, c, "unsure")
            return True
        return False

    # ------------------------------------------------------------ merging
    def _merge(self, st: CaseState, ex: Extraction, text: str) -> None:
        first = not st.issue_prior
        for issue, p in ex.issues.items():
            if issue not in self.k.issues:
                continue
            same_area = any(self.k.domain(i) == self.k.domain(issue) for i in st.issue_prior)
            if first or issue in st.issue_prior or p >= LATE_ISSUE_MIN or (same_area and p >= SAME_AREA_MIN):
                st.issue_prior[issue] = max(st.issue_prior.get(issue, 0.0), min(0.95, p))
        if first and st.issue_prior:
            keep = sorted(st.issue_prior.items(), key=lambda x: -x[1])[:4]
            st.issue_prior = dict(keep)
        st.out_of_scope = max(st.out_of_scope, ex.out_of_scope) if first else max(st.out_of_scope * 0.9, ex.out_of_scope)
        st.non_legal = ex.non_legal if first else min(st.non_legal, ex.non_legal)
        pkey = st.pending.key if st.pending is not None else None
        for u in ex.elements:
            if u.key in self.k.elements:
                if self.k.elements[u.key].issue not in st.issue_prior and not first:
                    continue                      # facts about issues not under consideration are ignored
                st.issue_prior.setdefault(self.k.elements[u.key].issue, 0.5)
                before = st.elements[u.key].value if u.key in st.elements else None
                self._apply_element(st, u, source="llm" if ex.backend == "llm" else ("narrative" if first else "answer"),
                                    correction=ex.correction)
                if u.key != pkey and u.value in ("satisfied", "contradicted") and before != u.value:
                    st.notes.append(f"_understood:{u.key}")
        for key, avail, quote in ex.evidence:
            self._apply_evidence(st, key, avail, quote)
        for d, ek in ex.dates:
            if ek and ek in self.k.elements:
                es = st.element(ek)
                es.date, es.date_text = d.iso, d.text
                if self.k.elements[ek].date_slot_required:
                    self._set_incident_date(st, d)
        if st.incident_date is None and not st.law_regime:
            self._date_from_sentences(st, text, ex)
        for flag, quote in ex.risks.items():
            if flag not in st.risks and flag in self.k.guidance["risk_alerts"]:
                st.risks[flag] = RiskState(flag=flag, quote=quote, turn=st.turn)
        for pm in ex.people:
            if not any(p.relation == pm.relation for p in st.people):
                st.people.append(Person(id=f"per_{len(st.people) + 1}", label=pm.surface, relation=pm.relation,
                                        noun=pm.noun, is_org=pm.is_org, name=pm.name, turns=[st.turn]))
        for m in ex.money:
            if m not in st.money:
                st.money.append(m)
        if ex.personal_law and not st.personal_law:
            st.personal_law = ex.personal_law
        policy.recompute_beliefs(st)
        self._recompute_status(st)

    def _date_from_sentences(self, st: CaseState, text: str, ex: Extraction) -> None:
        """A date in the same sentence as a cue for a regime-dependent issue is taken as the incident date."""
        conv = dt.date.fromisoformat(st.conversation_date)
        for sent in R.sentences(text):
            dates = R.extract_dates(sent, conv)
            if len(dates) != 1:
                continue
            cues = R.keyword_issue_scores(sent)
            if any(self._needs_regime(i) for i in cues) or \
                    any(u.quote == sent and self._needs_regime(self.k.elements[u.key].issue) for u in ex.elements):
                self._set_incident_date(st, dates[0])
                return

    def _needs_regime(self, issue: str) -> bool:
        return issue in self.k.issues and any(r.name == "law_regime" for r in self.k.issues[issue].routing_variables)

    def _set_incident_date(self, st: CaseState, d: R.DateMention, tentative: bool = False) -> None:
        reg = R.regime_of(d)
        if st.incident_date and st.incident_date != d.iso and not tentative and st.law_regime and reg and reg != st.law_regime:
            a = Statement(turn=st.turn, quote=st.incident_date_text or st.incident_date, value="satisfied")
            b = Statement(turn=st.turn, quote=d.text, value="satisfied")
            st.contradictions.append(Contradiction(id=f"c{len(st.contradictions) + 1}", key="date", a=a, b=b))
            return
        st.incident_date, st.incident_date_text = d.iso, d.text
        st.law_regime = reg
        if tentative:
            st.notes.append("incident date taken from the narrative (only date mentioned)")

    def _apply_element(self, st: CaseState, u: ElementUpdate, source: str, correction: bool = False) -> None:
        es = st.element(u.key)
        active = [s for s in es.statements if not s.corrected]
        s = Statement(turn=st.turn, quote=u.quote[:300], value=u.value, source=source, hedged=u.hedged,
                      gloss_en=u.gloss_en)
        if u.inferred:
            st.notes.append(f"inferred:{u.key}:{len(es.statements)}")
        es.asked = es.asked or source in ("option", "answer")
        if u.value == "unknown":
            es.statements.append(s)
            if not any(x.value in ("satisfied", "contradicted") for x in active):
                es.value = "unknown"
            return
        opposite = [x for x in active if x.value in ("satisfied", "contradicted") and x.value != u.value]
        same = [x for x in active if x.value == u.value]
        if opposite and correction:
            for x in opposite:
                x.corrected = True
            st.notes.append("_correction")
        elif opposite and not same:
            if not any(c.key == u.key and not c.resolved for c in st.contradictions):
                st.contradictions.append(Contradiction(id=f"c{len(st.contradictions) + 1}", key=u.key, a=opposite[-1], b=s))
        es.statements.append(s)
        unresolved = any(c.key == u.key and not c.resolved for c in st.contradictions)
        es.value = "unknown" if unresolved else u.value

    def _resolve_contradiction(self, st: CaseState, c: Contradiction, which: str, quote: str | None = None) -> None:
        c.resolved, c.resolution = True, which
        if c.key == "date":
            if which == "second":
                d = R.extract_dates(c.b.quote, dt.date.fromisoformat(st.conversation_date))
                if d:
                    st.incident_date, st.incident_date_text, st.law_regime = d[0].iso, d[0].text, R.regime_of(d[0])
            elif which == "unsure":
                st.law_regime = None
            return
        es = st.element(c.key)
        if which in ("first", "second"):
            keep = c.a if which == "first" else c.b
            for s in es.statements:
                if s.value in ("satisfied", "contradicted") and s.value != keep.value:
                    s.corrected = True
            es.value = keep.value
        else:
            es.value = "unknown"
        self._recompute_status(st)
        policy.recompute_beliefs(st)

    def _apply_evidence(self, st: CaseState, key: str, avail: str, quote: str) -> None:
        if key in self.k.evidence:
            info = self.k.evidence[key]
            ev = st.evidence.get(key) or EvidenceState(key=key, label=info.label[st.lang], supports=info.supports)
        else:
            ev = st.evidence.get(key) or EvidenceState(key=key, label=quote[:60])
        ev.availability, ev.quote, ev.turn = avail, quote[:300], st.turn
        st.evidence[key] = ev
        self._recompute_status(st)

    def _recompute_status(self, st: CaseState) -> None:
        held = {s for ev in st.evidence.values() if ev.availability == "held" for s in ev.supports}
        inferred = {n.split(":")[1] for n in st.notes if n.startswith("inferred:")}
        for key, es in st.elements.items():
            if any(c.key == key and not c.resolved for c in st.contradictions):
                es.status = "conflicting"
            elif es.value == "satisfied" and key in held:
                es.status = "evidence_supported"
            elif es.value in ("satisfied", "contradicted"):
                active = [s for s in es.statements if not s.corrected and s.value == es.value]
                es.status = "inferred" if active and key in inferred and all(s.source == "llm" for s in active) else "reported"
            else:
                es.status = "unknown"

    # ------------------------------------------------------------ respond
    def _respond(self, st: CaseState) -> None:
        policy.recompute_beliefs(st)
        self._recompute_status(st)
        notes = st.notes
        if "_skip_respond" in notes:
            st.notes = [n for n in notes if not n.startswith("_")]
            return
        lang = st.lang
        flags = [n for n in notes if n.startswith("_")]
        st.notes = [n for n in notes if not n.startswith("_")]
        if "_reexplain" in flags:
            self._reexplain(st)
            return
        fus = [f for f in flags if f.startswith("_followup:")]
        if fus:
            _, intent, detail = fus[0].split(":", 2)
            question = next((f[4:] for f in flags if f.startswith("_fq:")), "")
            self._answer_followup(st, intent, detail or None, question)
            if st.pending is not None:
                st.say(t("back_to_q", lang) + "\n" + st.pending.data.get("text", ""), kind="question",
                       chips=st.pending.chips, target=st.pending.key, why=st.pending.data.get("why"))
                return
            if st.consultation_ready:
                return
            flags = [f for f in flags if not f.startswith("_followup:")]
        for flag, r in st.risks.items():
            if not r.alerted:
                r.alerted = True
                alert = self.k.guidance["risk_alerts"].get(flag)
                if alert:
                    auth = "\n".join("• " + self.k.guidance["authorities"][a][lang] for a in alert["authorities"])
                    st.say(f"{alert[lang]}\n{auth}", kind="alert", target=flag)
        prefix = []
        if "_noted" in flags:
            prefix.append(t("noted", lang))
        if "_correction" in flags:
            prefix.append(t("correction_ack", lang))
        elif "_ack_unknown" in flags:
            prefix.append(t("ack_unknown", lang))
        understood = [f.split(":", 1)[1] for f in flags if f.startswith("_understood:")]
        understood = [k for k in dict.fromkeys(understood) if k in st.elements and st.elements[k].value in ("satisfied", "contradicted")]
        if understood:
            lines = [t("understood_facts", lang)]
            for k in understood[:8]:
                el = self.k.elements[k]
                lines.append(f"• {el.topic[lang]}: {el.options[st.elements[k].value][lang]}")
            lines.append(t("understood_tail", lang))
            st.say("\n".join(lines), kind="message")
        newly = [i for i in policy.identified(st) if i not in st.announced]
        if newly:
            prefix.append(t("understood_issues", lang, issues=", ".join(self.k.issue_title(i, lang) for i in newly)))
            st.announced += newly
        if not st.issue_prior and st.questions_asked == 0:
            if st.out_of_scope >= 0.5:
                st.say(self.k.guidance["out_of_scope"]["help"][lang], kind="message")
                self._mark_ready(st)
                return
            if st.non_legal >= 0.5:
                st.say(self.k.guidance["non_legal"]["help"][lang], kind="message")
                return
            if "_tell_more" not in flags and self._ask_issue_choice(st):
                return
            st.say(t("need_more", lang), kind="question")
            return
        if st.pending is not None:
            self._ask_pending(st, st.pending, prefix, reask=True)
            return
        cand = policy.next_question(st)
        if cand is None:
            if prefix:
                st.say(" ".join(prefix), kind="message")
            self._mark_ready(st)
            return
        self._ask(st, cand, prefix)

    def _signature(self, st: CaseState) -> str:
        import hashlib
        parts = sorted(f"{k}={e.value}/{e.status}" for k, e in st.elements.items()) + \
            sorted(f"{k}={e.availability}" for k, e in st.evidence.items()) + sorted(st.risks) + \
            [str(st.law_regime), str(st.personal_law), str(len(st.other_facts))] + sorted(policy.identified(st))
        return hashlib.sha1("|".join(parts).encode()).hexdigest()

    def _quick_chips(self, st: CaseState) -> list[Chip]:
        lang = st.lang
        return [Chip(id="show:consultation", label=t("view_consultation", lang)),
                Chip(id="show:drafts", label=t("view_drafts", lang))] + \
            [Chip(id=f"ask:{i}", label=t("fu_hint_" + h, lang)) for i, h in
             (("next_steps", "next"), ("documents", "docs"), ("where", "where"), ("laws", "laws"))]

    def _mark_ready(self, st: CaseState) -> None:
        was = st.consultation_ready
        st.consultation_ready = True
        sig = self._signature(st)
        if was and sig == st.card_signature:
            return                                           # nothing new: no repeated card
        st.card_signature = sig
        st.say(self._card_text(st, updated=was), kind="consultation", chips=self._quick_chips(st))

    def _card_text(self, st: CaseState, updated: bool) -> str:
        """A compact consultation shown directly in the chat (the full one is in the Consultation tab)."""
        lang = st.lang
        c = consult.build(st, None, explain_with_llm=False)
        lines = [t("card_updated" if updated else "card_title", lang), "", c["triage_text"]]
        if c["issues"]:
            lines += ["", t("card_issues", lang) + ":"] + [f"• {i['title']} — {i['summary']}" for i in c["issues"]]
        elif c.get("out_of_scope"):
            lines += ["", c["options"][0] if c["options"] else ""]
        if c["provisions"]:
            lines += ["", t("card_laws", lang) + ":"] + [
                f"• {p['act_title'].split(',')[0]} — {p['section']}" + (f": {p['title_hint']}" if p["title_hint"] else "")
                for p in c["provisions"][:6]]
        urgent = [r for r in c["risks"] if r.get("urgent")]
        if urgent:
            lines += ["", "⚠ " + urgent[0]["advice"]]
        if c["steps"]:
            lines += ["", t("card_steps", lang) + ":"] + [f"{n}. {x}" for n, x in enumerate(c["steps"][:3], 1)]
        if c["unresolved"]:
            lines += ["", t("card_open", lang) + ":"] + [f"• {q}" for q in c["unresolved"][:3]]
        if st.other_facts:
            lines += ["", t("other_facts", lang)] + [f"• “{x[:160]}”" for x in st.other_facts[-3:]]
        lines += ["", t("card_ask", lang)]
        return "\n".join(lines)

    def _answer_followup(self, st: CaseState, intent: str, detail: str | None, question: str) -> None:
        c = consult.build(st, None, explain_with_llm=False)
        text = None
        llm = self._llm(st)
        if llm is not None and question:
            text = followup.answer_llm(llm, question, c, st.lang)
            if text:
                st.llm_calls += 1
        if not text:
            text = followup.answer(intent, detail, c, st.lang)
        st.say(text, kind="answer", chips=self._quick_chips(st) if st.pending is None else [])

    def _why(self, st: CaseState, cand: policy.Candidate) -> str:
        lang = st.lang
        if cand.kind == "element":
            el = self.k.elements[cand.key]
            if cand.reason == "distinguish" and cand.other:
                w = t("why_distinguish", lang, issue=self.k.issue_title(el.issue, lang), other=self.k.issue_title(cand.other, lang))
            else:
                w = t("why_critical", lang, issue=self.k.issue_title(el.issue, lang))
        else:
            w = t({"evidence": "why_evidence", "date": "why_regime", "personal_law": "why_pl"}.get(cand.kind, "why_evidence"), lang)
        return t("why_ask", lang, why=w)

    def _ask(self, st: CaseState, cand: policy.Candidate, prefix: list[str]) -> None:
        lang = st.lang
        if cand.kind == "contradiction":
            c = next(c for c in st.contradictions if c.id == cand.key)
            p = Pending(kind="contradiction", key=c.id, chips=[Chip(id="c:first", label=t("first_correct", lang)),
                                                                 Chip(id="c:second", label=t("second_correct", lang)),
                                                                 Chip(id="c:unsure", label=t("not_sure", lang))],
                        data={"text": t("contradiction", lang, a=c.a.quote, b=c.b.quote)})
        elif cand.kind == "safety":
            p = Pending(kind="safety", chips=[Chip(id="safe:yes", label=t("safe_yes", lang)), Chip(id="safe:no", label=t("safe_no", lang))],
                        data={"text": t("q_safe", lang)})
        elif cand.kind == "element":
            el = self.k.elements[cand.key]
            st.asked.append(cand.key)
            p = Pending(kind="element", key=cand.key,
                        chips=[Chip(id="el:sat", label=el.options["satisfied"][lang]),
                               Chip(id="el:con", label=el.options["contradicted"][lang]),
                               Chip(id="dk", label=t("dont_know", lang))],
                        data={"text": self._personalize(st, el.question[lang], el.issue)})
            if st.last_issue_asked and st.last_issue_asked != el.issue and len(policy.identified(st)) > 1:
                prefix = prefix + [t("now_about", lang, issue=self.k.issue_title(el.issue, lang))]
            st.last_issue_asked = el.issue
        elif cand.kind == "evidence":
            ev = self.k.evidence[cand.key]
            st.asked.append(cand.key)
            p = Pending(kind="evidence", key=cand.key,
                        chips=[Chip(id="ev:held", label=t("have_it", lang)), Chip(id="ev:missing", label=t("dont_have", lang)),
                               Chip(id="dk", label=t("dont_know", lang))],
                        data={"text": t("evidence_q", lang, ev=ev.label[lang])})
        elif cand.kind == "date":
            st.asked.append("date")
            p = Pending(kind="date", chips=[Chip(id="date:old", label=t("date_before", lang)), Chip(id="date:new", label=t("date_after", lang)),
                                            Chip(id="dk", label=t("dont_know", lang))],
                        data={"text": t("q_date", lang, event=t("the_incident", lang))})
        else:
            st.asked.append("personal_law")
            p = Pending(kind="personal_law", chips=[Chip(id=f"pl:{x}", label=t(f"pl_{y}", lang)) for x, y in
                                                     (("hindu", "hindu"), ("muslim", "muslim"), ("christian", "christian"), ("interfaith_sma", "sma"))]
                        + [Chip(id="skip", label=t("skip", lang))], data={"text": t("q_personal_law", lang)})
        p.data["why"] = self._why(st, cand) if cand.kind not in ("contradiction", "safety") else None
        st.pending = p
        st.questions_asked += 1
        self._ask_pending(st, p, prefix)

    def _ask_pending(self, st: CaseState, p: Pending, prefix: list[str], reask: bool = False) -> None:
        q = p.data.get("text", "")
        text = q
        llm = self._llm(st)
        if llm is not None and p.kind in ("element", "evidence", "date") and not reask:
            try:
                last = next((m.text for m in reversed(st.messages) if m.role == "user"), "")
                r = llm.json(prompt("legallisten_reply_v1", **lang_kw(st.lang), last_user=last[:1500],
                                    known=self._summary_for_llm(st)[:1500], question=q), "reply")
                st.llm_calls += 1
                if r.get("reply"):
                    text = str(r["reply"]).strip()
                    prefix = []
            except (LLMError, KeyError, ValueError, TypeError):
                pass
        if reask:
            text = t("choose_or_type", st.lang) + " " + q
        if prefix:
            text = " ".join(prefix) + "\n\n" + text
        kind = "clarify" if p.kind == "contradiction" else "question"
        st.say(text, kind=kind, chips=p.chips, target=p.key, why=p.data.get("why"))

    def _reexplain(self, st: CaseState) -> None:
        lang = st.lang
        p = st.pending
        if p is not None and p.kind == "element":
            el = self.k.elements[p.key]
            simple = t("reexplain_intro", lang) + "\n" + " / ".join(f"“{c.label}”" for c in p.chips[:2]) + " — " + \
                t("choose_or_type", lang)
            st.say(simple, kind="question", chips=p.chips, target=p.key, why=p.data.get("why"))
            return
        if p is not None:
            st.say(t("reexplain_intro", lang) + " " + p.data.get("text", ""), kind="question", chips=p.chips, target=p.key)
            return
        if st.last_explained:
            st.say(self.explain(st, st.last_explained, "simpler"), kind="explain", target=st.last_explained)
            return
        st.say(t("need_more", lang), kind="question")

    # ------------------------------------------------------------ helpers
    def _respondent_label(self, st: CaseState, issue: str) -> str | None:
        """'your brother' / 'ನಿಮ್ಮ ಅಣ್ಣ' / 'आपके भाई' for the person the client named in this issue."""
        from lexvaani.render.lexicon import lexicon, noun_forms
        from lexvaani.schemas.common import LangVariant
        cast = {n for c in self.k.issues[issue].cast for n in c.nouns}
        family_bg = {"father", "mother", "son", "daughter", "child", "police", "bank"}
        person = next((p for p in st.people if p.noun in cast), None) or \
            next((p for p in st.people if not p.is_org and p.relation not in family_bg and p.noun in lexicon()["role_nouns"]), None)
        if person is None:
            return None
        variant = {"en": LangVariant.EN, "kn": LangVariant.KN, "hi": LangVariant.HI}[st.lang]
        try:
            bare, _ = noun_forms(person.noun, "male" if person.relation not in ("wife", "mother_in_law", "sister") else "female", variant)
        except KeyError:
            return None
        bare = bare.get("nom") if isinstance(bare, dict) else bare
        if not isinstance(bare, str):
            return None
        for a, b in (("my ", "your "), ("ನನ್ನ ", "ನಿಮ್ಮ "), ("ನಮ್ಮ ", "ನಿಮ್ಮ "), ("मेरे ", "आपके "), ("मेरी ", "आपकी "), ("मेरा ", "आपके ")):
            if bare.startswith(a):
                return b + bare[len(a):]
        return bare

    def _personalize(self, st: CaseState, question: str, issue: str) -> str:
        """Make a library question refer to the people and things the client actually mentioned."""
        said = self._user_text(st).lower()
        q = question
        who = self._respondent_label(st, issue)
        if who:
            for generic in ("the person", "this person", "that person", "the other person", "ಆ ವ್ಯಕ್ತಿ", "उस व्यक्ति"):
                q = q.replace(generic, who).replace(generic.capitalize(), who[:1].upper() + who[1:])
        doc = next((v for k, v in {"will": ("the will", "ಆ ವಿಲ್", "उस वसीयत"), "वसीयत": ("the will", "ಆ ವಿಲ್", "उस वसीयत"),
                                    "ವಿಲ್": ("the will", "ಆ ವಿಲ್", "उस वसीयत"), "deed": ("the deed", "ಆ ಪತ್ರ", "उस बैनामे")}.items()
                    if re.search(r"(?<![a-z])" + re.escape(k), said)), None)
        if doc:
            i = {"en": 0, "kn": 1, "hi": 2}[st.lang]
            q = q.replace("that document", doc[i]).replace("ಆ ದಾಖಲೆ", doc[i]).replace("उस दस्तावेज़", doc[i])
        if re.search(r"(?<![a-z])land|ಜಮೀನು|ज़मीन|जमीन|zameen", said):
            q = q.replace("the property", "the land").replace("this property", "this land")
        return q

    def _user_text(self, st: CaseState) -> str:
        return " ".join(m.text for m in st.messages if m.role == "user" and m.source != "option")

    def _ask_issue_choice(self, st: CaseState) -> bool:
        """The client's words point to a legal area but not to one problem: ask which is closest."""
        domains = R.domains_mentioned(self._user_text(st))
        if not domains:
            return False
        choices = []
        for d in domains[:2]:
            choices += [i for i in self.k.guidance["domain_choices"].get(d, []) if R.anchored(i, self._user_text(st))]
        choices = list(dict.fromkeys(choices))[:6]
        if not choices:
            return False
        chips = [Chip(id=f"issue:{i}", label=f"{self.k.issue_title(i, st.lang)} — {self.k.summary(i, st.lang)}") for i in choices]
        chips.append(Chip(id="issue:other", label=t("something_else", st.lang)))
        st.pending = Pending(kind="issue_choice", chips=chips, data={"text": t("which_issue", st.lang)})
        st.say(t("which_issue", st.lang), kind="question", chips=chips)
        return True

    def _rescan(self, st: CaseState, issue: str) -> None:
        """After the client picks an issue, read their earlier words again for facts about it."""
        from .nlu.cues import elements_in
        before = len(st.notes)
        for m in st.messages:
            if m.role != "user" or m.source == "option":
                continue
            for sent in R.sentences(m.text):
                for key, val, _ in elements_in(sent, [issue]):
                    es = st.elements.get(key)
                    if es is None or es.value is None:
                        self._apply_element(st, ElementUpdate(key, val, sent), source="narrative")
                        st.notes.append(f"_understood:{key}")
        if len(st.notes) == before:
            st.notes.append("_ack")

    def _pending_desc(self, st: CaseState) -> str:
        p = st.pending
        if not p:
            return ""
        if p.kind == "element":
            el = self.k.elements[p.key]
            return f"element {p.key}: {el.question['en']} (satisfied means: {el.proposition['satisfied']}; contradicted means: {el.proposition['contradicted']})"
        if p.kind == "evidence":
            return f"evidence {p.key}: does the client have {self.k.evidence[p.key].label['en']}?"
        return f"{p.kind}: {p.data.get('text', '')}"

    def _summary_for_llm(self, st: CaseState) -> str:
        parts = []
        for key, es in st.elements.items():
            if es.value:
                parts.append(f"{key}={es.value}[{es.status}]")
        if st.incident_date:
            parts.append(f"incident_date={st.incident_date}")
        if st.risks:
            parts.append("risks=" + ",".join(st.risks))
        if st.issue_prior:
            parts.append("hypotheses=" + ",".join(f"{i}:{b:.2f}" for i, b in st.beliefs.items()))
        return "; ".join(parts)

    # ------------------------------------------------------------ outputs
    def consultation(self, st: CaseState, explain_with_llm: bool = True) -> dict:
        c = consult.build(st, self._llm(st), explain_with_llm)
        st.consultation_version = c["version"]
        st.consultation_ready = True
        return c

    def explain(self, st: CaseState, provision_id: str, mode: str = "standard") -> str:
        card = next((c for c in cards(st) if c.provision_id == provision_id), None)
        if card is None:
            return t("need_more", st.lang)
        st.last_explained = provision_id
        return consult.explain(card, st, self._llm(st), mode)

    def graph(self, st: CaseState) -> dict:
        g = graph.build(st)
        g["errors"] = graph.validate(g)
        return g

    def summary(self, st: CaseState) -> dict:
        k = self.k
        return {
            "issues": [{"id": i, "title": k.issue_title(i, st.lang), "belief": b, "identified": b >= policy.IDENTIFIED}
                       for i, b in sorted(st.beliefs.items(), key=lambda x: -x[1])],
            "urgent": any(is_urgent(f) for f in st.risks) or st.safety_unsafe,
            "risks": list(st.risks),
            "consultation_ready": st.consultation_ready,
            "questions_asked": st.questions_asked,
            "law_regime": st.law_regime, "incident_date": st.incident_date, "personal_law": st.personal_law,
            "llm": bool(self._llm(st)), "input_variant": st.input_variant, "lang": st.lang,
            "title": self._title(st), "created": st.created, "updated": st.updated,
        }

    def _title(self, st: CaseState) -> str:
        ids = policy.identified(st) or sorted(st.issue_prior, key=lambda i: -st.issue_prior[i])[:2]
        if ids:
            return ", ".join(self.k.issue_title(i, st.lang) for i in ids[:2])
        first = next((m.text for m in st.messages if m.role == "user"), "")
        return (first[:60] + "…") if len(first) > 60 else first
