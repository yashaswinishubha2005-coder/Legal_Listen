"""Spec-grounded user simulator + oracle-driven system (T5 across turns, T9, T12).

The simulated user answers ONLY from the hidden spec:
  - facts revealed in the narrative are not asked again (they are already known);
  - facts with reveal=dialogue are answered with the fact template;
  - facts with reveal=never get "I don't know" (status unknown);
  - elements of confusable (absent) issues get a generic "no";
  - occasionally the user asks for re-explanation, or answers with a wrong
    amount/date and corrects it in the next turn.
"""

from __future__ import annotations

import datetime as dt

from lexvaani.render.engine import DocContext, keyed_rng
from lexvaani.render.lexicon import lexicon, variant_entry
from lexvaani.render.narrative import apply_hedge, collect, coref_for, plan_units, render_units
from lexvaani.schemas.common import EpistemicStatus, IssueId, Language, LangVariant
from lexvaani.schemas.dialogue import (CandidateQuestion, ClarificationLabel, DecisionPoint, Dialogue,
                                       DialogueState, Speaker, Turn)
from lexvaani.schemas.issue_library import IssueSchema
from lexvaani.schemas.metadata import Provenance
from lexvaani.schemas.ontology import ElementValue
from lexvaani.schemas.sample import FactAnnotation
from lexvaani.schemas.spec import Reveal, ScenarioSpec, Variation
from lexvaani.specs.claims import element_values

from . import oracle

V = LangVariant
SYSTEM_LANG = {V.EN: Language.EN, V.KN: Language.KN, V.KN_EN_LATN: Language.KN, V.KN_EN_MIXED: Language.KN,
               V.HI: Language.HI, V.HI_EN_LATN: Language.HI}
MAX_QUESTIONS = 6
P_REEXPLAIN = 0.15
P_CORRECTION = 0.25


def _hypotheses(spec: ScenarioSpec, lib: dict[IssueId, IssueSchema]) -> list[IssueId]:
    hyp = [i for i in spec.issues if i in lib]
    for i in list(hyp):
        for c in lib[i].confusable_with[:1]:
            if c in lib and c not in hyp:
                hyp.append(c)
    return hyp


def simulate(spec: ScenarioSpec, lib: dict[IssueId, IssueSchema], variant: LangVariant,
             other_bank: dict | None = None) -> Dialogue:
    did = f"dlg_{spec.spec_id}_{variant.value}"
    lang = SYSTEM_LANG[variant]
    lex = lexicon()["dialogue"]
    sg = spec.metadata.gender.value
    ctx = DocContext(spec=spec, variant=variant, family=spec.family_id, difficulty=spec.difficulty.value)
    turns: list[Turn] = []
    decisions: list[DecisionPoint] = []
    all_mentions = []

    def add_turn(speaker: Speaker, text: str, entities=None, facts=None, qid=None, clar=None) -> int:
        i = len(turns)
        turns.append(Turn(index=i, speaker=speaker, text=text, unit_id=f"{did}#t{i}", question_id=qid,
                          clarification=clar, entities=entities or [], facts=facts or []))
        return i

    # ---- opening
    add_turn(Speaker.SYSTEM, lex["opening_system"][lang.value])
    other = None
    if spec.other_template:
        pool = (other_bank or {}).get("out_of_scope", []) + (other_bank or {}).get("non_legal", [])
        other = next(t for t in pool if t["id"] == spec.other_template)
    units = plan_units(spec, lib, variant, other)
    uid = f"{did}#t1"
    text, rendered = render_units(ctx, spec, units, variant, uid)
    col = collect(spec, lib, text, rendered, uid)
    claims = col["claims"]
    if spec.variation in (Variation.OUT_OF_SCOPE, Variation.NON_LEGAL):
        _set_status(claims)
    else:
        from lexvaani.specs.claims import assign_statuses
        from lexvaani.specs.generate import supporting_map
        assign_statuses(claims, supporting_map(type("D", (), {"evidence": spec.evidence}), col["stated_ev"]))
    add_turn(Speaker.USER, text, col["entities"], _facts(claims))
    all_mentions += col["entities"]

    if spec.variation in (Variation.OUT_OF_SCOPE, Variation.NON_LEGAL):
        return Dialogue(dialogue_id=did, spec_id=spec.spec_id, family_id=spec.family_id, lang_variant=variant,
                        turns=turns, decision_points=[], coref=coref_for(all_mentions), provenance=_prov(spec))

    # ---- state
    hyp = _hypotheses(spec, lib)
    crit = {f"{i.value}|{e.element_id}": e.critical for i in hyp for e in lib[i].elements}
    order = {f"{i.value}|{e.element_id}": e.order for i in hyp for e in lib[i].elements}
    gold_crit = [f"{e.issue_id.value}|{e.element_id}" for e in spec.elements if e.critical]
    vals = element_values(spec, claims)
    known = {f"{k[0]}|{k[1]}": v.value for k, v in vals.items() if v != ElementValue.UNKNOWN}
    asked: list[str] = []
    reexplained = False

    def state() -> DialogueState:
        b = oracle.beliefs([h.value for h in hyp], known, crit)
        return DialogueState(known={k: ElementValue(v) for k, v in known.items()}, asked=list(asked),
                             belief={k: round(v, 6) for k, v in b.items()},
                             completeness=round(oracle.completeness(known, gold_crit), 6))

    for q_n in range(MAX_QUESTIONS):
        before = state()
        cands = [k for k in crit if k not in known and k not in asked]
        ranked = oracle.rank(cands, before.belief, crit, order)
        if not ranked or ranked[0][1] < oracle.MIN_SCORE:
            break
        best = ranked[0][0]
        acc = oracle.acceptable(ranked)
        cq = []
        for k, s in ranked:
            issue_v, el_id = k.split("|", 1)
            el = next(e for e in lib[IssueId(issue_v)].elements if e.element_id == el_id)
            cq.append(CandidateQuestion(question_id=k, issue_id=issue_v, element_id=el_id, critical=el.critical,
                                        text=el.question[lang], oracle_score=s))
        q_text = next(c.text for c in cq if c.question_id == best)
        sys_turn = add_turn(Speaker.SYSTEM, q_text, qid=best)
        asked.append(best)
        rng = keyed_rng(spec.family_id, variant.value, "dlg", q_n)
        if not reexplained and rng.random() < P_REEXPLAIN:
            reexplained = True
            bank = variant_entry(lex["reexplain"], variant, sg)
            s = ctx.render(bank[rng.randrange(len(bank))], None)
            add_turn(Speaker.USER, s.text, clar=ClarificationLabel.REEXPLAIN_REQUEST)
            add_turn(Speaker.SYSTEM, lex["reask_prefix"][lang.value] + q_text, qid=best)
        ans_turn = _answer(spec, lib, variant, ctx, best, rng, add_turn, did, len(turns), all_mentions, known, sg)
        decisions.append(DecisionPoint(system_turn=sys_turn, state_before=before, candidates=cq, gold_best=best,
                                       acceptable_set=acc, answer_turn=ans_turn, state_after=state()))
    return Dialogue(dialogue_id=did, spec_id=spec.spec_id, family_id=spec.family_id, lang_variant=variant,
                    turns=turns, decision_points=decisions, coref=coref_for(all_mentions), provenance=_prov(spec))


def _answer(spec, lib, variant, ctx, key, rng, add_turn, did, next_index, all_mentions, known, sg) -> int:
    from lexvaani.specs.claims import ClaimRecord
    issue_v, el_id = key.split("|", 1)
    issue_id = IssueId(issue_v)
    lex = lexicon()["dialogue"]
    fact = next((f for f in spec.facts if f.issue_id == issue_id and f.element_id == el_id), None)
    el = next(e for e in lib[issue_id].elements if e.element_id == el_id)

    def emit(template: str, polarity: ElementValue, status: EpistemicStatus, *, event=None, hedge=False,
             amount=None, clar=ClarificationLabel.NEW_FACT, corrects=None, lead: str | None = None) -> int:
        i = len_turns[0]
        uid = f"{did}#t{i}"
        s = ctx.render(template, issue_id, event=event, amount_override=amount)
        if hedge:
            apply_hedge(spec, s, variant, f"{key}|ans")
        if lead:
            s.prepend(lead + " ")
        c = ClaimRecord(f"clm_t{i}", "element", issue_id, el_id, polarity, el.proposition.get(polarity.value, ""),
                        status=status, event_id=event.event_id if event else None)
        unit = type("U", (), {"claim": c, "evidence_id": None, "event_id": None})()
        s.meta["claim_start"] = len(lead) + 1 if lead else 0
        s.meta["claim_end"] = len(s.text.rstrip())
        col = collect(spec, lib, s.text, [(unit, s, 0)], uid)
        all_mentions.extend(col["entities"])
        idx = add_turn(Speaker.USER, s.text, col["entities"], _facts(col["claims"]), clar=clar)
        len_turns[0] = idx + 1
        return idx

    len_turns = [next_index]
    if fact is None:   # element of a confusable (absent) issue
        known[key] = ElementValue.CONTRADICTED.value
        return emit(lex["no_generic"][variant.value], ElementValue.CONTRADICTED, EpistemicStatus.REPORTED)
    if fact.reveal == Reveal.NEVER:
        known[key] = ElementValue.UNKNOWN.value
        bank = variant_entry(lex["dont_know"], variant, sg)
        return emit(bank[rng.randrange(len(bank))], ElementValue.UNKNOWN, EpistemicStatus.UNKNOWN)
    template = getattr(el, fact.polarity.value)[variant]
    event = next((e for e in spec.events if e.event_id == fact.event_id), None)
    has_amount = "{AMOUNT" in template
    has_date = "{DATE" in template and event is not None
    if (has_amount or has_date) and rng.random() < P_CORRECTION:
        wrong_amount = wrong_event = None
        if has_amount:
            true_amt = int(next(v.value for v in spec.values if f"{issue_id.value}:AMOUNT" in v.refs))
            wrong_amount = _confusable_amount(true_amt, rng)
        else:
            d = dt.date.fromisoformat(event.date) - dt.timedelta(days=rng.choice([3, 7, 10]))
            wrong_event = event.model_copy(update={"date": d.isoformat()})
        first = emit(template, fact.polarity, EpistemicStatus.REPORTED,
                     event=wrong_event or event, amount=wrong_amount)
        bank = variant_entry(lex["correction"], variant, sg)
        lead_tpl = bank[rng.randrange(len(bank))]
        lead = ctx.render(lead_tpl, None).text
        known[key] = fact.polarity.value
        emit(template, fact.polarity, EpistemicStatus.REPORTED, event=event, clar=ClarificationLabel.CORRECTION,
             lead=lead)
        return first
    known[key] = fact.polarity.value
    return emit(template, fact.polarity, EpistemicStatus.REPORTED, event=event, hedge=fact.hedged)


SWAPS = {15: 50, 50: 15, 14: 40, 40: 14, 18: 80, 80: 18, 60: 6, 90: 10, 30: 3}


def _confusable_amount(amount: int, rng) -> int:
    """A plausible mis-statement: 'fifty' vs 'fifteen' style swaps, else a neighbouring band value."""
    from lexvaani.specs.generate import AMOUNT_BANDS
    unit = 100_000 if amount % 100_000 == 0 else 1000
    n = amount // unit
    if n in SWAPS and SWAPS[n] in lexicon()["numbers"]:
        return SWAPS[n] * unit
    band = next(b for b in AMOUNT_BANDS.values() if amount in b)
    return rng.choice([x for x in band if x != amount])


def _set_status(claims) -> None:
    for c in claims:
        if c.contradicts:
            c.status = EpistemicStatus.CONFLICTING
        elif c.status not in (EpistemicStatus.UNKNOWN,):
            c.status = EpistemicStatus.REPORTED


def _facts(claims) -> list[FactAnnotation]:
    return [FactAnnotation(claim_id=c.claim_id, span=c.spans[0], status=c.status, issue_id=c.issue_id,
                           element_id=c.element_id, polarity=c.polarity, hedged=c.hedged,
                           hedge_cues=c.hedge_cues, negation_cues=c.negation_cues) for c in claims if c.spans]


def _prov(spec: ScenarioSpec) -> Provenance:
    return Provenance(generator="template-v1+oracle", generator_version="0.1.0", seed=spec.provenance.seed,
                      created="2026-10-24")
