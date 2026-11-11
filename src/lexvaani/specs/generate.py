"""Phase 2: scenario-spec generation (balanced by construction) + minimal pairs."""

from __future__ import annotations

import copy
import datetime as dt
import hashlib
import random
from dataclasses import dataclass, field

from lexvaani.render.lexicon import item as lex_item
from lexvaani.render.lexicon import lexicon, noun_forms, noun_kin, pick_name
from lexvaani.schemas.common import Domain, EpistemicStatus, IssueId, LangVariant
from lexvaani.schemas.issue_library import URGENT_FLAGS, IssueSchema, RiskFlag, Triage
from lexvaani.schemas.metadata import (AgeGroup, Gender, KarnatakaRegion, Literacy, Provenance, Religion,
                                       Settlement, SpeakerMetadata)
from lexvaani.schemas.ontology import ElementValue, EvidenceAvailability
from lexvaani.schemas.spec import (Difficulty, ElementTruth, LawRegime, MinimalPair, Reveal, ScenarioSpec,
                                   SpecEvent, SpecEvidence, SpecFact, SpecPerson, SpecValue, Variation)

from .claims import ClaimRecord, assign_statuses, build_graph, element_values

GENERATOR_VERSION = "template-v1"
LIB_VARIATIONS = [Variation.COMPLETE, Variation.INCOMPLETE, Variation.CONTRADICTORY,
                  Variation.MULTI_ISSUE, Variation.HIGH_RISK]
DIFF_CYCLE = [Difficulty.EASY, Difficulty.MEDIUM, Difficulty.HARD, Difficulty.MEDIUM]
REGIME_CUTOFF = dt.date(2024, 7, 1)
FAMILY_LIKE = {Domain.FAMILY, Domain.PROPERTY}
AMOUNT_BANDS = {
    "small": [5_000, 10_000, 12_000, 15_000, 18_000, 20_000, 25_000],
    "medium": [30_000, 40_000, 45_000, 50_000, 60_000, 75_000, 80_000, 90_000],
    "large": [100_000, 200_000, 300_000, 500_000],
}


def rng_for(*parts: object) -> random.Random:
    h = hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()
    return random.Random(int(h[:16], 16))


def rand_date(rng: random.Random, lo: dt.date, hi: dt.date) -> dt.date:
    if hi < lo:
        return lo
    return lo + dt.timedelta(days=rng.randint(0, (hi - lo).days))


# ----------------------------------------------------------------- drafts --

@dataclass
class Draft:
    spec_id: str
    family_id: str
    variation: Variation
    difficulty: Difficulty
    issues: list[IssueId]
    conversation_date: dt.date
    metadata: SpeakerMetadata
    regime: LawRegime | None = None
    cast: list[SpecPerson] = field(default_factory=list)
    values: list[SpecValue] = field(default_factory=list)
    events: list[SpecEvent] = field(default_factory=list)
    facts: list[SpecFact] = field(default_factory=list)
    world: dict[tuple[str, str], ElementValue] = field(default_factory=dict)
    evidence: list[SpecEvidence] = field(default_factory=list)
    risk_flags: list[RiskFlag] = field(default_factory=list)
    other_template: str | None = None
    minimal_pair: MinimalPair | None = None
    seed: int = 0


def _metadata(rng: random.Random, issue: IssueSchema | None) -> SpeakerMetadata:
    genders = issue.speaker_genders if issue else ["female", "male"]
    gender = Gender(rng.choice(genders))
    religion = Religion.NOT_RECORDED
    if issue and issue.domain in FAMILY_LIKE and any(r.name == "personal_law" for r in issue.routing_variables):
        pl = next(r for r in issue.routing_variables if r.name == "personal_law").values
        weights = {"hindu": 0.72, "muslim": 0.12, "christian": 0.08, "interfaith_sma": 0.08}
        opts = [v for v in pl if v in weights]
        religion = Religion(rng.choices(opts, weights=[weights[o] for o in opts])[0])
    return SpeakerMetadata(
        gender=gender,
        age_group=rng.choices(list(AgeGroup), weights=[0.25, 0.4, 0.25, 0.1])[0],
        settlement=rng.choices(list(Settlement), weights=[0.6, 0.4])[0],
        region=rng.choice(list(KarnatakaRegion)),
        religion=religion,
        literacy_proxy=rng.choices(list(Literacy), weights=[0.25, 0.45, 0.3])[0],
    )


def _name_group(rng: random.Random, religion: Religion) -> str:
    if religion == Religion.MUSLIM:
        return "muslim"
    if religion == Religion.CHRISTIAN:
        return "christian"
    return rng.choices(["kn_hindu", "hi_hindu"], weights=[0.75, 0.25])[0]


def _noun_genders(noun: str) -> list[str]:
    entry = lexicon()["role_nouns"][noun]
    if "any" in entry:
        return ["male", "female"]
    return [g for g, k in (("male", "m"), ("female", "f")) if k in entry]


def _add_cast(d: Draft, issue: IssueSchema, rng: random.Random, share_with: list[SpecPerson]) -> None:
    used_names = {p.name for p in d.cast if p.name}
    group = _name_group(rng, d.metadata.religion)
    for slot in issue.cast:
        ref = f"{issue.issue_id.value}:{slot.slot}"
        # share an entity across issues in a multi-issue spec when the role overlaps
        shared = None
        for p in share_with:
            if slot.kind != "person" and p.is_org and p.slot.split("__")[0] == slot.slot:
                shared = p
            elif slot.kind == "person" and not p.is_org and p.noun in slot.nouns:
                shared = p
            if shared:
                break
        if shared:
            shared.refs.append(ref)
            continue
        unique = slot.slot if all(p.slot != slot.slot for p in d.cast) else f"{slot.slot}__{len(d.cast)}"
        if slot.kind != "person":
            prefix = {"organization": "org", "account": "acc", "asset": "ast"}[slot.kind]
            n = sum(p.node_id.startswith(prefix) for p in d.cast) + 1
            d.cast.append(SpecPerson(slot=unique, node_id=f"{prefix}_{n}", role=slot.kind if slot.kind != "organization" else "organization",
                                     gender="n", noun=(slot.nouns or ["other"])[0], is_org=True, refs=[ref]))
            continue
        speaker_g = d.metadata.gender.value
        nouns = [n for n in slot.nouns if _noun_ok(n, speaker_g)] or slot.nouns
        noun = rng.choice(nouns)
        genders = [g for g in slot.genders if g in _noun_genders(noun)] or _noun_genders(noun)
        if noun == "spouse":
            genders = ["female" if speaker_g == "male" else "male"]
        gender = rng.choice(genders)
        name = None
        if slot.named:
            name = pick_name(rng, group, gender, used_names)[0]
            used_names.add(name)
        kin = slot.kin_relation or noun_kin(noun, gender)
        n = sum((not p.is_org) for p in d.cast) + 1
        d.cast.append(SpecPerson(slot=unique, node_id=f"per_{n}", role=slot.role, gender=gender, name=name,
                                 noun=noun, kin_relation=kin, is_minor=(noun == "child"), refs=[ref]))


def _noun_ok(noun: str, speaker_gender: str) -> bool:
    # an ex-partner / spouse is assumed to be of the other gender (documented limitation)
    return True


def _add_values(d: Draft, issue: IssueSchema, rng: random.Random) -> None:
    for slot, keys in issue.value_slots.items():
        ref = f"{issue.issue_id.value}:{slot}"
        existing = next((v for v in d.values if v.slot.split("__")[0] == slot and v.kind != "amount"), None)
        if slot == "AMOUNT":
            band = rng.choice(keys)
            amt = rng.choice(AMOUNT_BANDS[band])
            unique = slot if all(v.slot != slot for v in d.values) else f"{slot}__{len(d.values)}"
            d.values.append(SpecValue(slot=unique, kind="amount", key=band, value=str(amt), refs=[ref]))
            continue
        if existing and slot == "PLACE":
            existing.refs.append(ref)
            continue
        key = rng.choice(keys)
        unique = slot if all(v.slot != slot for v in d.values) else f"{slot}__{len(d.values)}"
        if slot == "ITEM":
            n = sum(1 for v in d.values if v.node_id) + 1 + sum(p.node_id.startswith("ast") for p in d.cast)
            d.values.append(SpecValue(slot=unique, node_id=f"ast_{n}", kind="item", key=key, value=key, refs=[ref]))
        elif slot == "PLACE":
            d.values.append(SpecValue(slot=unique, kind="place", key=key, value=key, refs=[ref]))
        elif slot == "IDNUM":
            if key == "survey":
                digits = f"{rng.randint(12, 299)}/{rng.randint(1, 9)}"
            elif key == "phone_tail":
                digits = "".join(str(rng.randint(0, 9)) for _ in range(4))
            else:
                digits = "".join(str(rng.randint(0, 9)) for _ in range(12))
            d.values.append(SpecValue(slot=unique, kind="idnum", key=key, value=digits, refs=[ref]))
        else:
            d.values.append(SpecValue(slot=unique, kind="other", key=key, value=key, refs=[ref]))


def _has_regime(issue: IssueSchema) -> bool:
    return any(r.name == "law_regime" for r in issue.routing_variables)


def _incident_date(d: Draft, issues: list[IssueSchema], rng: random.Random, recent: bool) -> dt.date:
    conv = d.conversation_date
    if recent:
        if issues[0].risk_facts[0].flag == RiskFlag.GOLDEN_HOUR_FRAUD:
            return conv   # "an hour ago" must agree with the event date
        if issues[0].risk_facts[0].flag == RiskFlag.LIMITATION_NEAR_EXPIRY:
            return conv - dt.timedelta(days=rng.randint(690, 720))   # "almost two years"
        return conv - dt.timedelta(days=rng.randint(0, 2))
    if any(_has_regime(i) for i in issues):
        if d.regime == LawRegime.OLD:
            return rand_date(rng, dt.date(2022, 6, 1), dt.date(2024, 5, 31))
        return rand_date(rng, max(REGIME_CUTOFF + dt.timedelta(days=5), conv - dt.timedelta(days=400)),
                         conv - dt.timedelta(days=1))
    return rand_date(rng, conv - dt.timedelta(days=700), conv - dt.timedelta(days=3))


def _timeline(d: Draft, issue: IssueSchema, start: dt.date, rng: random.Random) -> None:
    orders = sorted({e.order for e in issue.elements if e.event_type})
    dates: dict[int, dt.date] = {}
    cur = start
    for i, o in enumerate(orders):
        if i:
            cur = min(cur + dt.timedelta(days=rng.randint(0, 20)), d.conversation_date)
        dates[o] = cur
    if d.regime == LawRegime.OLD and _has_regime(issue):
        cap = REGIME_CUTOFF - dt.timedelta(days=1)
        dates = {o: min(x, cap) for o, x in dates.items()}
    for el in issue.elements:
        if not el.event_type:
            continue
        n = len(d.events) + 1
        d.events.append(SpecEvent(event_id=f"evt_{n}", issue_id=issue.issue_id, element_id=el.element_id,
                                  event_type=el.event_type, date=dates[el.order].isoformat(),
                                  args=dict(el.args)))


def _facts(d: Draft, issue: IssueSchema, rng: random.Random, variation: Variation, k: int) -> None:
    els = issue.elements
    crit = [e for e in els if e.critical]
    unknown_el = contra_el = flip_el = None
    if variation == Variation.INCOMPLETE:
        unknown_el = rng.choice([e for e in crit if e.may_be_unknown])
    if variation == Variation.CONTRADICTORY:
        contra_el = rng.choice(crit)
    if variation == Variation.COMPLETE and k == 3:
        flip_el = rng.choice(crit)
    hedge_p = {Difficulty.EASY: 0.0, Difficulty.MEDIUM: 0.15, Difficulty.HARD: 0.3}[d.difficulty]
    for el in els:
        key = (issue.issue_id.value, el.element_id)
        if el.critical:
            pol = ElementValue.CONTRADICTED if el is flip_el else ElementValue.SATISFIED
        else:
            pol = rng.choice([ElementValue.SATISFIED, ElementValue.CONTRADICTED])
        reveal = Reveal.NARRATIVE
        if el is unknown_el:
            reveal = Reveal.NEVER
            pol = rng.choice([ElementValue.SATISFIED, ElementValue.CONTRADICTED])
        d.world[key] = pol
        ev = next((e for e in d.events if e.issue_id == issue.issue_id and e.element_id == el.element_id), None)
        n = len(d.facts) + 1
        d.facts.append(SpecFact(fact_id=f"fct_{n}", issue_id=issue.issue_id, element_id=el.element_id,
                                polarity=pol, reveal=reveal, hedged=rng.random() < hedge_p,
                                self_contradicted=el is contra_el, event_id=ev.event_id if ev else None))
    # difficulty: move some facts to the dialogue only
    narrative = [f for f in d.facts if f.issue_id == issue.issue_id and f.reveal == Reveal.NARRATIVE
                 and not f.self_contradicted]
    moves = {Difficulty.EASY: 0, Difficulty.MEDIUM: 1, Difficulty.HARD: 2}[d.difficulty]
    rng.shuffle(narrative)
    for f in narrative[:moves]:
        if len([x for x in d.facts if x.issue_id == issue.issue_id and x.reveal == Reveal.NARRATIVE]) <= 2:
            break
        idx = d.facts.index(f)
        d.facts[idx] = f.model_copy(update={"reveal": Reveal.DIALOGUE})
    contradicted = {f.element_id for f in d.facts if f.issue_id == issue.issue_id
                    and f.polarity == ElementValue.CONTRADICTED and f.reveal != Reveal.NEVER}
    for evd in issue.evidence:
        avail = evd.default_availability if rng.random() < 0.6 else EvidenceAvailability.MISSING
        if set(evd.supports) <= contradicted:   # no proof can exist for something that did not happen
            avail = EvidenceAvailability.MISSING
        reveal = Reveal.NARRATIVE if (d.difficulty == Difficulty.EASY or rng.random() < 0.7) else Reveal.DIALOGUE
        n = len(d.evidence) + 1
        d.evidence.append(SpecEvidence(evidence_id=f"evd_{n}", issue_id=issue.issue_id, def_id=evd.evidence_id,
                                       availability=avail, supports=list(evd.supports), reveal=reveal))


def draft_library_spec(lib: dict[IssueId, IssueSchema], issue_id: IssueId, variation: Variation, k: int,
                       spec_id: str, seed: int) -> Draft:
    rng = rng_for(seed, issue_id.value, variation.value, k)
    issue = lib[issue_id]
    conv = rand_date(rng, dt.date(2025, 3, 1), dt.date(2026, 9, 30))
    difficulty = DIFF_CYCLE[(k + list(lib).index(issue_id)) % len(DIFF_CYCLE)]
    d = Draft(spec_id=spec_id, family_id=f"fam_{spec_id[4:]}", variation=variation, difficulty=difficulty,
              issues=[issue_id], conversation_date=conv, metadata=_metadata(rng, issue), seed=seed)
    issues = [issue]
    if variation == Variation.MULTI_ISSUE:
        partners = [p for p in issue.co_occurs_with if p in lib and p != issue_id]
        cross = [p for p in partners if lib[p].domain != issue.domain]
        partner = rng.choice(cross or partners) if partners else None
        if partner is None:
            others = [i for i in lib if i != issue_id]
            partner = rng.choice(others)
        d.issues.append(partner)
        issues.append(lib[partner])
    if any(_has_regime(i) for i in issues):
        d.regime = LawRegime.NEW if (variation == Variation.HIGH_RISK or rng.random() < 0.7) else LawRegime.OLD
    start = _incident_date(d, issues, rng, recent=variation == Variation.HIGH_RISK)
    for i, iss in enumerate(issues):
        _add_cast(d, iss, rng, share_with=list(d.cast) if i else [])
        _add_values(d, iss, rng)
        _timeline(d, iss, start, rng)
        _facts(d, iss, rng, variation if i == 0 else Variation.COMPLETE, k if i == 0 else 0)
    if variation == Variation.HIGH_RISK:
        d.risk_flags = [issue.risk_facts[0].flag]
    return d


# --------------------------------------------------------------- finalize --

def routing_of(d: Draft) -> dict[str, str]:
    r: dict[str, str] = {}
    if d.regime:
        r["law_regime"] = d.regime.value
    if d.metadata.religion != Religion.NOT_RECORDED:
        r["personal_law"] = d.metadata.religion.value
    if d.risk_flags:
        r["risk"] = ",".join(f.value for f in d.risk_flags)
    return r


def provisions_for(lib: dict[IssueId, IssueSchema], issues: list[IssueId], routing: dict[str, str]) -> list[str]:
    out: list[str] = []
    risks = set(routing.get("risk", "").split(",")) - {""}
    for i in issues:
        if i not in lib:
            continue
        for cp in lib[i].candidate_provisions:
            ok = True
            for key, vals in cp.when.items():
                if key == "risk":
                    ok &= bool(risks & set(vals))
                else:
                    ok &= routing.get(key) in vals
            if ok and cp.provision_id not in out:
                out.append(cp.provision_id)
    return out


def spec_claims(d: Draft, lib: dict[IssueId, IssueSchema], reveal: set[Reveal]) -> tuple[list[ClaimRecord], set[str]]:
    claims: list[ClaimRecord] = []
    n = iter(range(1, 10_000))
    for f in d.facts:
        if f.reveal not in reveal:
            continue
        el = next(e for e in lib[f.issue_id].elements if e.element_id == f.element_id)
        c1 = ClaimRecord(f"clm_{next(n)}", "element", f.issue_id, f.element_id, f.polarity,
                         el.proposition[f.polarity.value], fact_id=f.fact_id, event_id=f.event_id, hedged=f.hedged)
        claims.append(c1)
        if f.self_contradicted:
            opp = ElementValue.CONTRADICTED if f.polarity == ElementValue.SATISFIED else ElementValue.SATISFIED
            c2 = ClaimRecord(f"clm_{next(n)}", "element", f.issue_id, f.element_id, opp,
                             el.proposition[opp.value], fact_id=f.fact_id, event_id=f.event_id)
            c1.contradicts, c2.contradicts = c2.claim_id, c1.claim_id
            claims.append(c2)
    stated_ev: set[str] = set()
    for ev in d.evidence:
        if ev.reveal not in reveal:
            continue
        stated_ev.add(ev.evidence_id)
        held = ev.availability != EvidenceAvailability.MISSING
        claims.append(ClaimRecord(f"clm_{next(n)}", "evidence", ev.issue_id, None,
                                  ElementValue.SATISFIED if held else ElementValue.CONTRADICTED,
                                  f"The speaker {'has' if held else 'does not have'} {ev.def_id.replace('_', ' ')}.",
                                  evidence_id=ev.evidence_id))
    for flag in d.risk_flags:
        claims.append(ClaimRecord(f"clm_{next(n)}", "risk", d.issues[0], None, ElementValue.SATISFIED,
                                  f"Risk: {flag.value.replace('_', ' ')}."))
    assign_statuses(claims, supporting_map(d, stated_ev))
    return claims, stated_ev


def supporting_map(d: Draft, stated_ev: set[str]) -> dict[tuple[str, str], list[str]]:
    out: dict[tuple[str, str], list[str]] = {}
    for ev in d.evidence:
        if ev.evidence_id in stated_ev and ev.availability != EvidenceAvailability.MISSING:
            for el in ev.supports:
                out.setdefault((ev.issue_id.value, el), []).append(ev.evidence_id)
    return out


def triage_for(d: Draft, lib: dict[IssueId, IssueSchema], notes: list[str]) -> Triage:
    if set(d.risk_flags) & URGENT_FLAGS:
        return Triage.URGENT
    if any(i in lib and lib[i].default_triage == Triage.URGENT for i in d.issues):
        return Triage.URGENT
    if d.variation == Variation.OUT_OF_SCOPE:
        return Triage.LAWYER
    if d.variation == Variation.NON_LEGAL:
        return Triage.SELF_HELP
    if len(d.issues) > 1 or notes or any(lib[i].default_triage == Triage.LAWYER for i in d.issues):
        return Triage.LAWYER
    return Triage.SELF_HELP


def finalize(d: Draft, lib: dict[IssueId, IssueSchema], other: dict | None = None) -> ScenarioSpec:
    routing = routing_of(d)
    events = []
    for e in d.events:
        f = next((x for x in d.facts if x.event_id == e.event_id), None)
        if f is None:
            events.append(e)
            continue
        el = next(x for x in lib[e.issue_id].elements if x.element_id == e.element_id)
        contra = f.polarity == ElementValue.CONTRADICTED and not f.self_contradicted
        events.append(e.model_copy(update={
            "negated": contra and not el.hypothetical_when_contradicted,
            "hypothetical": contra and el.hypothetical_when_contradicted}))
    d.events = events
    notes: list[str] = []
    if d.variation in (Variation.OUT_OF_SCOPE, Variation.NON_LEGAL):
        claims: list[ClaimRecord] = []
        for i, s in enumerate((other or {}).get("propositions", []), start=1):
            claims.append(ClaimRecord(f"clm_{i}", "other", None, None, ElementValue.SATISFIED, s))
        stated_ev: set[str] = set()
        gold: list[str] = []
        elements: list[ElementTruth] = []
    else:
        claims, stated_ev = spec_claims(d, lib, {Reveal.NARRATIVE, Reveal.DIALOGUE})
        gold = provisions_for(lib, d.issues, routing)
        rel = d.metadata.religion
        for i in d.issues:
            if any(r.name == "personal_law" for r in lib[i].routing_variables) and rel in (Religion.MUSLIM, Religion.CHRISTIAN):
                notes.append(f"{i.value}: personal law ({rel.value}) is outside the corpus; route to a lawyer")
        elements = []
        tmp = ScenarioSpec.model_construct(elements=[ElementTruth(
            issue_id=f.issue_id, element_id=f.element_id,
            critical=next(e for e in lib[f.issue_id].elements if e.element_id == f.element_id).critical,
            world_value=d.world[(f.issue_id.value, f.element_id)], gold_value=ElementValue.UNKNOWN)
            for f in d.facts])
        vals = element_values(tmp, claims)
        for et in tmp.elements:
            elements.append(et.model_copy(update={"gold_value": vals[(et.issue_id.value, et.element_id)]}))
    triage = triage_for(d, lib, notes)
    incident = min((e.date for e in d.events), default=None)
    base = dict(
        spec_id=d.spec_id, family_id=d.family_id, variation=d.variation, difficulty=d.difficulty,
        issues=d.issues, conversation_date=d.conversation_date.isoformat(), incident_date=incident,
        law_regime=d.regime, routing=routing, cast=d.cast, values=d.values, events=d.events,
        facts=d.facts, elements=elements, evidence=d.evidence, risk_flags=d.risk_flags, triage=triage,
        gold_provisions=gold, provision_notes=notes, other_template=d.other_template,
        metadata=d.metadata, minimal_pair=d.minimal_pair,
        provenance=Provenance(generator=GENERATOR_VERSION, generator_version="0.1.0", seed=d.seed,
                              created="2026-10-24"),
    )
    pre = ScenarioSpec.model_construct(**base)
    stated_events = {c.event_id for c in claims if c.event_id} if d.variation not in (
        Variation.OUT_OF_SCOPE, Variation.NON_LEGAL) else {e.event_id for e in d.events}
    graph = build_graph(pre, lib, claims, stated_ev, stated_events=stated_events)
    return ScenarioSpec.model_validate({**base, "case_graph": graph})


# ---------------------------------------------------------- minimal pairs --

FLIP_TASKS = {
    "element_flip": ["T7", "T8"],
    "evidence_flip": ["T6", "T8"],
    "date_regime_flip": ["T4", "T10"],
    "risk_flip": ["T13"],
}


def make_sibling(d: Draft, lib: dict[IssueId, IssueSchema], prefer: list[str]) -> Draft | None:
    issue = lib[d.issues[0]]
    for flip in prefer:
        s = copy.deepcopy(d)
        s.spec_id = d.spec_id + "b"
        if flip == "date_regime_flip" and d.regime and d.variation != Variation.HIGH_RISK:
            years = 2 if d.regime == LawRegime.NEW else -2
            new_events = []
            for e in s.events:
                x = dt.date.fromisoformat(e.date)
                try:
                    y = x.replace(year=x.year - years)
                except ValueError:
                    y = x.replace(year=x.year - years, day=28)
                new_events.append(e.model_copy(update={"date": y.isoformat()}))
            dates = [dt.date.fromisoformat(e.date) for e in new_events]
            if any(x > s.conversation_date for x in dates):
                continue
            target = LawRegime.OLD if d.regime == LawRegime.NEW else LawRegime.NEW
            if target == LawRegime.OLD and any(x >= REGIME_CUTOFF for x in dates):
                continue
            if target == LawRegime.NEW and any(x < REGIME_CUTOFF for x in dates):
                continue
            s.events, s.regime = new_events, target
            desc = f"incident moved from {d.regime.value} to {target.value} criminal-law regime (2024-07-01 cut-off)"
        elif flip == "evidence_flip":
            cands = [e for e in s.evidence if e.availability != EvidenceAvailability.MISSING
                     and e.reveal == Reveal.NARRATIVE and e.issue_id == d.issues[0]
                     and any(f.element_id in e.supports and f.reveal == Reveal.NARRATIVE
                             and f.polarity == ElementValue.SATISFIED and not f.self_contradicted
                             for f in s.facts if f.issue_id == e.issue_id)]
            if not cands:
                continue
            ev = cands[0]
            s.evidence = [x.model_copy(update={"availability": EvidenceAvailability.MISSING})
                          if x.evidence_id == ev.evidence_id else x for x in s.evidence]
            desc = f"evidence '{ev.def_id}' changed from {ev.availability.value} to missing"
        elif flip == "element_flip":
            cands = [f for f in s.facts if f.issue_id == d.issues[0] and f.reveal == Reveal.NARRATIVE
                     and not f.self_contradicted and f.polarity == ElementValue.SATISFIED
                     and next(e for e in issue.elements if e.element_id == f.element_id).critical]
            if not cands:
                continue
            f = cands[0]
            s.facts = [x.model_copy(update={"polarity": ElementValue.CONTRADICTED}) if x.fact_id == f.fact_id else x
                       for x in s.facts]
            s.world[(f.issue_id.value, f.element_id)] = ElementValue.CONTRADICTED
            s.evidence = [x.model_copy(update={"availability": EvidenceAvailability.MISSING})
                          if x.issue_id == f.issue_id and set(x.supports) <= {f.element_id} else x
                          for x in s.evidence]
            desc = f"critical element '{f.element_id}' flipped from satisfied to contradicted"
        elif flip == "risk_flip" and not d.risk_flags:
            s.risk_flags = [issue.risk_facts[0].flag]
            desc = f"added risk fact '{issue.risk_facts[0].flag.value}'"
        else:
            continue
        s.minimal_pair = MinimalPair(base_spec_id=d.spec_id, flip_type=flip, changed=desc,
                                     flipped_tasks=FLIP_TASKS[flip])
        return s
    return None


# ------------------------------------------------------- out-of-library --

def draft_other_spec(variation: Variation, tpl: dict, k: int, spec_id: str, seed: int) -> Draft:
    rng = rng_for(seed, variation.value, tpl["id"], k)
    conv = rand_date(rng, dt.date(2025, 3, 1), dt.date(2026, 9, 30))
    label = IssueId.OUT_OF_SCOPE if variation == Variation.OUT_OF_SCOPE else IssueId.NON_LEGAL
    d = Draft(spec_id=spec_id, family_id=f"fam_{spec_id[4:]}", variation=variation,
              difficulty=DIFF_CYCLE[k % 4], issues=[label], conversation_date=conv,
              metadata=_metadata(rng, None), other_template=tpl["id"], seed=seed)
    group = _name_group(rng, d.metadata.religion)
    for i, slot in enumerate(tpl.get("cast", []), start=1):
        if slot.get("kind") == "organization":
            d.cast.append(SpecPerson(slot=slot["slot"], node_id=f"org_{i}", role="organization", gender="n",
                                     noun=slot["nouns"][0], is_org=True, refs=[f"{label.value}:{slot['slot']}"]))
            continue
        noun = rng.choice(slot["nouns"])
        gender = rng.choice(_noun_genders(noun))
        name = pick_name(rng, group, gender, set())[0] if slot.get("named", True) else None
        if not slot.get("named", True):
            noun = "unknown_person"
        d.cast.append(SpecPerson(slot=slot["slot"], node_id=f"per_{i}", role="other", gender=gender, name=name,
                                 noun=noun, kin_relation=noun_kin(noun, gender), refs=[f"{label.value}:{slot['slot']}"]))
    for slot, keys in tpl.get("value_slots", {}).items():
        if slot == "AMOUNT":
            band = rng.choice(keys)
            d.values.append(SpecValue(slot=slot, kind="amount", key=band, value=str(rng.choice(AMOUNT_BANDS[band])),
                                      refs=[f"{label.value}:{slot}"]))
    if tpl.get("has_date"):
        ev_date = rand_date(rng, conv - dt.timedelta(days=200), conv - dt.timedelta(days=1))
        d.events.append(SpecEvent(event_id="evt_1", issue_id=label, element_id="background",
                                  event_type=tpl.get("event_type", "background"), date=ev_date.isoformat()))
    return d


# ------------------------------------------------------------------- main --

def generate_all(lib: dict[IssueId, IssueSchema], other_bank: dict, seed: int = 13, per_cell: int = 4,
                 pair_rate: float = 0.3, others_per_variation: int = 40) -> list[ScenarioSpec]:
    specs: list[ScenarioSpec] = []
    drafts: list[Draft] = []
    n = 0
    for issue_id in lib:
        for variation in LIB_VARIATIONS:
            for k in range(per_cell):
                n += 1
                drafts.append(draft_library_spec(lib, issue_id, variation, k, f"spc_{n:04d}", seed))
    pair_rng = rng_for(seed, "pairs")
    order = ["date_regime_flip", "evidence_flip", "element_flip", "risk_flip"]
    eligible = [d for d in drafts if d.variation in (Variation.COMPLETE, Variation.MULTI_ISSUE,
                                                      Variation.INCOMPLETE, Variation.HIGH_RISK)]
    chosen = set(id(d) for d in pair_rng.sample(eligible, k=int(round(pair_rate * len(drafts)))))
    siblings: list[Draft] = []
    used = {k: 0 for k in order}
    for d in drafts:
        if id(d) not in chosen:
            continue
        prefer = sorted(order, key=lambda k: (used[k], order.index(k)))   # least-used feasible flip
        s = make_sibling(d, lib, prefer)
        if s:
            siblings.append(s)
            used[s.minimal_pair.flip_type] += 1
    for d in drafts + siblings:
        specs.append(finalize(d, lib))
    by_var = {Variation.OUT_OF_SCOPE: other_bank["out_of_scope"], Variation.NON_LEGAL: other_bank["non_legal"]}
    for variation, templates in by_var.items():
        for k in range(others_per_variation):
            n += 1
            tpl = templates[k % len(templates)]
            d = draft_other_spec(variation, tpl, k // len(templates), f"spc_{n:04d}", seed)
            specs.append(finalize(d, lib, tpl))
    specs.sort(key=lambda s: s.spec_id)
    return specs
