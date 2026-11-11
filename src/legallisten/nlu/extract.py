"""Turn one client message into structured, validated case updates.

Two back-ends with the same output:
  * local  — LexVaani-IN-trained classifiers + multilingual rules (always available, offline)
  * llm    — Gemini (or another provider) with a strict JSON contract; every id is validated
             against the issue library, quotes are checked against the message, and anything
             that fails validation is dropped. On any LLM error the local back-end is used.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field

from ..knowledge import kb
from ..llm import LLM, LLMError, prompt
from . import rules as R
from .cues import elements_in, match as cue_match
from .model import load

HEDGES = ["i think", "maybe", "probably", "not fully sure", "i guess", "perhaps", "ಅನ್ಸುತ್ತೆ", "ಅನಿಸುತ್ತೆ", "ಬಹುಶಃ",
          "anstide", "ansutte", "bahusha", "मुझे लगता", "शायद", "lagta hai", "shayad"]
SENT_MIN = 0.5
ISSUE_MIN = 0.2


@dataclass
class ElementUpdate:
    key: str
    value: str
    quote: str
    hedged: bool = False
    inferred: bool = False
    gloss_en: str | None = None
    prob: float = 1.0


@dataclass
class Extraction:
    backend: str
    variant: str
    issues: dict[str, float] = field(default_factory=dict)
    out_of_scope: float = 0.0
    non_legal: float = 0.0
    elements: list[ElementUpdate] = field(default_factory=list)
    evidence: list[tuple[str, str, str]] = field(default_factory=list)     # key, availability, quote
    risks: dict[str, str] = field(default_factory=dict)
    people: list[R.PersonMention] = field(default_factory=list)
    dates: list[tuple[R.DateMention, str | None]] = field(default_factory=list)   # date, element key
    money: list[str] = field(default_factory=list)
    personal_law: str | None = None
    answer: str | None = None
    correction: bool = False
    reexplain: bool = False
    unclear: bool = False
    unclear_reason: str | None = None
    sentence_probs: dict[str, dict[str, float]] = field(default_factory=dict)


PL_CUES = {
    "hindu": ["hindu", "ಹಿಂದೂ", "हिंदू", "हिन्दू", "sikh", "jain", "buddhist", "ಸಿಖ್", "ಜೈನ", "सिख", "जैन", "बौद्ध"],
    "muslim": ["muslim", "ಮುಸ್ಲಿಂ", "मुस्लिम", "मुसलमान", "nikah", "निकाह"],
    "christian": ["christian", "ಕ್ರಿಶ್ಚಿಯನ್", "ಕ್ರೈಸ್ತ", "ईसाई", "क्रिश्चियन", "church"],
    "interfaith_sma": ["special marriage", "registered marriage", "court marriage", "ವಿಶೇಷ ವಿವಾಹ", "विशेष विवाह", "कोर्ट मैरिज"],
}


def personal_law_of(text: str) -> str | None:
    for pl, cues in PL_CUES.items():
        if R._has(text, cues):
            return pl
    return None


def _focus_issues(ex: "Extraction", context: str) -> None:
    """Keep only issues the client's words actually point to, and at most three of them."""
    ctx = context or ""
    ex.issues = {i: p for i, p in ex.issues.items() if R.anchored(i, ctx)}
    ranked = sorted(ex.issues.items(), key=lambda x: -x[1])
    if ranked and ranked[0][1] >= 0.7:
        ranked = [(i, p) for i, p in ranked if p >= 0.5]
    ex.issues = dict(ranked[:3])


def local_extract(text: str, conv: dt.date, active: set[str], context: str = "") -> Extraction:
    k = kb()
    rr = R.analyse(text, conv)
    ex = Extraction(backend="local", variant=rr.variant, risks=dict(rr.risks), people=rr.people, money=rr.money,
                    answer=rr.answer, correction=rr.correction, reexplain=rr.reexplain,
                    personal_law=personal_law_of(text))
    models = load()
    if models:
        probs = models.issue_probs(text)
        ex.out_of_scope = probs.pop("x.out_of_scope", 0.0)
        ex.non_legal = probs.pop("x.non_legal", 0.0)
        top = max(probs.values()) if probs else 0.0
        for i, p in probs.items():
            if p >= 0.5:
                ex.issues[i] = p
        if max(ex.out_of_scope, ex.non_legal) < max(0.4, top):
            ex.out_of_scope = ex.non_legal = 0.0
    for i, p in rr.issue_kw.items():
        ex.issues[i] = max(ex.issues.get(i, 0.0), p)
    if models and not ex.issues and not active and max(ex.out_of_scope, ex.non_legal) < 0.4:
        # no explicit cue: keep at most the two strongest model guesses as tentative hypotheses to test
        for i, p in sorted(probs.items(), key=lambda x: -x[1])[:2]:
            if p >= 0.08 and p >= 0.5 * top:
                ex.issues[i] = 0.3 + 0.15 * (p / top)
    sents = R.sentences(text)
    used_dates: set[str] = set()
    for s in sents:
        sdates = R.extract_dates(s, conv)
        label, prob = "none", 0.0
        if models:
            sp = models.sentence_probs(s)
            ex.sentence_probs[s] = sp
            label, prob = max(sp.items(), key=lambda x: x[1])
        if label.startswith("el|") and prob >= SENT_MIN:
            _, issue, el, val = label.split("|")
            if issue in active or ex.issues.get(issue, 0) >= ISSUE_MIN or prob >= 0.8:
                key = f"{issue}|{el}"
                ex.elements.append(ElementUpdate(key, val, s, hedged=R._has(s, HEDGES), prob=prob))
                ex.issues.setdefault(issue, 0.45)
                for d in sdates:
                    ex.dates.append((d, key))
                    used_dates.add(d.iso)
        elif label.startswith("ev|") and prob >= SENT_MIN:
            _, issue, ev, avail = label.split("|")
            ex.evidence.append((f"{issue}|{ev}", avail, s))
        elif label.startswith("risk|") and prob >= SENT_MIN:
            ex.risks.setdefault(label.split("|")[1], s)
    _focus_issues(ex, (context + " " + text) if context else text)
    ex.elements = [u for u in ex.elements if u.key.split("|")[0] in ex.issues or u.key.split("|")[0] in active]
    # cue-based reading of the client's own words, for issues already under consideration
    focus = set(active) | {i for i, p in ex.issues.items() if p >= 0.4}
    found = {u.key for u in ex.elements}
    for s in sents:
        for key, val, cue in elements_in(s, focus):
            if key not in found:
                found.add(key)
                ex.elements.append(ElementUpdate(key, val, s, hedged=R._has(s, HEDGES), prob=0.6))
                for d in R.extract_dates(s, conv):
                    if k.elements[key].event_type:
                        ex.dates.append((d, key))
                        used_dates.add(d.iso)
    for d in rr.dates:
        if d.iso not in used_dates:
            ex.dates.append((d, None))
    return ex


def pending_element_guess(ex: Extraction, key: str, text: str) -> str | None:
    """For a free-text answer to a pending element question, read its polarity from the sentence model."""
    best, best_p = None, 0.0
    for s, sp in ex.sentence_probs.items():
        for val in ("satisfied", "contradicted"):
            p = sp.get(f"el|{key}|{val}", 0.0)
            if p > best_p:
                best, best_p = val, p
    return best if best_p >= 0.15 else None


# --------------------------------------------------------------------------- LLM
def catalog(active: set[str]) -> str:
    """Compact catalog: full detail for active issues, ids + one line for the rest."""
    k = kb()
    lines = []
    for iid in k.issues:
        if iid in active or not active:
            lines.append(f"ISSUE {iid} — {k.issue_title(iid, 'en')}: {k.summary(iid, 'en')}")
            for el in k.elements_of(iid):
                lines.append(f"  element {el.key}{' (critical)' if el.critical else ''}: {el.description}")
            for ev in (e for e in k.evidence.values() if e.issue == iid):
                lines.append(f"  evidence {ev.key}: {ev.label['en']}")
        else:
            lines.append(f"ISSUE {iid} — {k.issue_title(iid, 'en')}: {k.summary(iid, 'en')}")
    flags = ", ".join(k.guidance["risk_alerts"])
    lines.append(f"RISK FLAGS: {flags}")
    lines.append("If the problem is legal but none of the issues fit, set out_of_scope high; if not legal, non_legal high.")
    return "\n".join(lines)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def llm_extract(llm: LLM, text: str, conv: dt.date, active: set[str], summary: str, pending: str) -> Extraction:
    k = kb()
    hint = local_extract(text, conv, active)          # cheap; also gives sentence probs and rules
    focus = set(active) | {i for i, p in hint.issues.items() if p >= 0.3}
    raw = llm.json(prompt("legallisten_extract_v1", conversation_date=conv.isoformat(), pending=pending or "(none)",
                          summary=summary or "(start of consultation)", catalog=catalog(focus), message=text), "extract")
    ex = Extraction(backend="llm", variant=hint.variant, people=hint.people, money=hint.money, answer=hint.answer,
                    sentence_probs=hint.sentence_probs)
    for it in raw.get("issues") or []:
        iid, c = it.get("issue_id"), it.get("confidence", 0)
        if iid in k.issues and isinstance(c, (int, float)):
            ex.issues[iid] = max(0.0, min(1.0, float(c)))
    ex.out_of_scope = float(raw.get("out_of_scope") or 0)
    ex.non_legal = float(raw.get("non_legal") or 0)
    msg = _norm(text)
    for e in raw.get("elements") or []:
        key, val = e.get("key"), e.get("value")
        if key not in k.elements or val not in ("satisfied", "contradicted", "unknown"):
            continue
        quote = (e.get("quote") or "").strip()
        in_msg = bool(quote) and _norm(quote) in msg
        ex.elements.append(ElementUpdate(key, val, quote if in_msg else text[:200], hedged=bool(e.get("hedged")),
                                         inferred=(e.get("status_hint") == "inferred") or not in_msg,
                                         gloss_en=e.get("gloss_en")))
        ex.issues.setdefault(k.elements[key].issue, 0.5)
    for e in raw.get("evidence") or []:
        if e.get("key") in k.evidence and e.get("availability") in ("held", "missing"):
            ex.evidence.append((e["key"], e["availability"], e.get("quote") or ""))
    for r in raw.get("risks") or []:
        if r.get("flag") in k.guidance["risk_alerts"]:
            ex.risks[r["flag"]] = r.get("quote") or ""
    for flag, cue in hint.risks.items():           # rules are a safety net: never drop a risk cue
        ex.risks.setdefault(flag, cue)
    for p in raw.get("people") or []:
        if p.get("label") and not any(x.relation == p.get("relation") for x in ex.people):
            ex.people.append(R.PersonMention(p["label"], p.get("relation") or "other", p.get("relation") or "other",
                                             is_org=(p.get("relation") or "") in R.ORG_NOUNS))
    for d in raw.get("dates") or []:
        iso = str(d.get("iso") or "")
        if re.fullmatch(r"20\d\d(-\d\d(-\d\d)?)?", iso):
            gran = {4: "year", 7: "month", 10: "day"}[len(iso)]
            ek = d.get("element_key") if d.get("element_key") in k.elements else None
            try:
                dm = R.DateMention(d.get("text") or iso, iso, gran)
                dm.as_date()
                ex.dates.append((dm, ek))
            except ValueError:
                continue
    if not ex.dates:
        ex.dates = hint.dates
    pl = raw.get("personal_law")
    ex.personal_law = pl if pl in PL_CUES else hint.personal_law
    ex.correction = bool(raw.get("correction")) or hint.correction
    ex.reexplain = bool(raw.get("reexplain")) or hint.reexplain
    ex.unclear = bool(raw.get("unclear"))
    ex.unclear_reason = raw.get("unclear_reason")
    return ex


def extract(text: str, conv: dt.date, active: set[str], llm: LLM | None = None, summary: str = "",
            pending: str = "", context: str = "") -> Extraction:
    if llm is not None:
        try:
            return llm_extract(llm, text, conv, active, summary, pending)
        except (LLMError, KeyError, ValueError, TypeError):
            pass
    return local_extract(text, conv, active, context)
