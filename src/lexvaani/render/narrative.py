"""Spec -> first-person narrative with full span-level and case-level gold labels."""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations

from lexvaani.schemas.common import EpistemicStatus, IssueId, LangVariant, Span, Timex, TimexType
from lexvaani.schemas.issue_library import IssueSchema
from lexvaani.schemas.metadata import Provenance
from lexvaani.schemas.ontology import ElementValue, EvidenceAvailability
from lexvaani.schemas.sample import (Annotations, CorefCluster, ElementLabel, EntityMention, EntityType,
                                     EventAnnotation, EventArgument, FactAnnotation, MentionKind,
                                     NarrativeSample, TLink, TLinkRel)
from lexvaani.schemas.spec import Difficulty, Reveal, ScenarioSpec, Variation
from lexvaani.specs.claims import ClaimRecord, assign_statuses, build_graph, element_values
from lexvaani.specs.generate import supporting_map

from .engine import DocContext, keyed_rng
from .lexicon import HINDI, lexicon, variant_entry
from .markup import RSpan, Sentence

V = LangVariant
LATIN_VARIANTS = {V.EN, V.KN_EN_LATN, V.HI_EN_LATN}

PERSONAL_LAW = {
    "hindu": {V.EN: "Our family is Hindu.", V.KN: "ನಮ್ಮದು ಹಿಂದೂ ಕುಟುಂಬ.", V.KN_EN_LATN: "Nammadu Hindu kutumba.",
              V.KN_EN_MIXED: "ನಮ್ಮದು Hindu family.", V.HI: "हमारा परिवार हिंदू है।", V.HI_EN_LATN: "Hamara parivaar Hindu hai."},
    "muslim": {V.EN: "Our family is Muslim.", V.KN: "ನಮ್ಮದು ಮುಸ್ಲಿಂ ಕುಟುಂಬ.", V.KN_EN_LATN: "Nammadu Muslim kutumba.",
               V.KN_EN_MIXED: "ನಮ್ಮದು Muslim family.", V.HI: "हमारा परिवार मुस्लिम है।", V.HI_EN_LATN: "Hamara parivaar Muslim hai."},
    "christian": {V.EN: "Our family is Christian.", V.KN: "ನಮ್ಮದು ಕ್ರಿಶ್ಚಿಯನ್ ಕುಟುಂಬ.", V.KN_EN_LATN: "Nammadu Christian kutumba.",
                  V.KN_EN_MIXED: "ನಮ್ಮದು Christian family.", V.HI: "हमारा परिवार ईसाई है।", V.HI_EN_LATN: "Hamara parivaar Christian hai."},
    "interfaith_sma": {V.EN: "Ours is an inter-faith marriage; we did a registered marriage.",
                       V.KN: "ನಮ್ಮದು ಅಂತರ್ಧರ್ಮೀಯ ಮದುವೆ, ರಿಜಿಸ್ಟರ್ ಮ್ಯಾರೇಜ್ ಮಾಡಿಕೊಂಡಿದ್ದೀವಿ.",
                       V.KN_EN_LATN: "Nammadu inter-religion maduve, register marriage maadkondiddivi.",
                       V.KN_EN_MIXED: "ನಮ್ಮದು inter-religion marriage, register marriage ಮಾಡ್ಕೊಂಡಿದ್ದೀವಿ.",
                       V.HI: "हमारी अंतरधार्मिक शादी है, हमने रजिस्टर्ड मैरिज की थी।",
                       V.HI_EN_LATN: "Hamari inter-religion shaadi hai, humne registered marriage ki thi."},
}


@dataclass
class Unit:
    kind: str                      # setup | element | evidence | risk | routing | emotion | closer | other
    issue: IssueId | None
    template: str
    claim: ClaimRecord | None = None
    event_id: str | None = None
    evidence_id: str | None = None
    must_resolve: bool = False
    hedge: bool = False
    sort_date: str | None = None
    prefix: str | None = None      # discourse filler or flashback marker (outside the claim span)
    meta: dict = field(default_factory=dict)


# ------------------------------------------------------------------ plan --

def plan_units(spec: ScenarioSpec, lib: dict[IssueId, IssueSchema], variant: LangVariant,
               other: dict | None = None) -> list[Unit]:
    prng = keyed_rng(spec.family_id, "plan")
    units: list[Unit] = []
    claim_n = iter(range(1, 10_000))
    if spec.variation in (Variation.OUT_OF_SCOPE, Variation.NON_LEGAL):
        props = other.get("propositions", [])
        for i, tpl in enumerate(other["sentences"][variant.value]):
            c = ClaimRecord(f"clm_{next(claim_n)}", "other", None, None, ElementValue.SATISFIED,
                            props[i] if i < len(props) else tpl)
            ev = spec.events[0].event_id if spec.events and "{DATE" in tpl else None
            units.append(Unit("other", spec.issues[0], tpl, claim=c, event_id=ev))
        _discourse(spec, units, variant, prng)
        return units

    personal_law = spec.routing.get("personal_law")
    for idx, issue_id in enumerate(spec.issues):
        issue = lib[issue_id]
        setup_claim = ClaimRecord(f"clm_{next(claim_n)}", "setup", issue_id, None, ElementValue.SATISFIED,
                                  f"Context: {issue.title['en']}.")
        units.append(Unit("setup", issue_id, issue.setup[variant], claim=setup_claim))
        if idx == 0 and personal_law:
            units.append(Unit("routing", issue_id, PERSONAL_LAW[personal_law][variant],
                              claim=ClaimRecord(f"clm_{next(claim_n)}", "routing", issue_id, None,
                                                ElementValue.SATISFIED, f"Personal law: {personal_law}.")))
        facts = [f for f in spec.facts if f.issue_id == issue_id and f.reveal == Reveal.NARRATIVE]
        late: list[Unit] = []
        for f in facts:
            el = next(e for e in issue.elements if e.element_id == f.element_id)
            ev = next((e for e in spec.events if e.event_id == f.event_id), None)
            c = ClaimRecord(f"clm_{next(claim_n)}", "element", issue_id, f.element_id, f.polarity,
                            el.proposition[f.polarity.value], fact_id=f.fact_id, event_id=f.event_id,
                            hedged=f.hedged)
            tpl = getattr(el, f.polarity.value)[variant]
            units.append(Unit("element", issue_id, tpl, claim=c, event_id=f.event_id,
                              must_resolve=el.date_slot_required and spec.law_regime is not None,
                              hedge=f.hedged, sort_date=ev.date if ev else None, meta={"order": el.order}))
            if f.self_contradicted:
                opp = ElementValue.CONTRADICTED if f.polarity == ElementValue.SATISFIED else ElementValue.SATISFIED
                c2 = ClaimRecord(f"clm_{next(claim_n)}", "element", issue_id, f.element_id, opp,
                                 el.proposition[opp.value], fact_id=f.fact_id, event_id=f.event_id)
                c.contradicts, c2.contradicts = c2.claim_id, c.claim_id
                late.append(Unit("element", issue_id, getattr(el, opp.value)[variant], claim=c2,
                                 event_id=f.event_id, must_resolve=el.date_slot_required and spec.law_regime is not None,
                                 meta={"order": 99, "contradiction": True}))
        for ev in spec.evidence:
            if ev.issue_id != issue_id or ev.reveal != Reveal.NARRATIVE:
                continue
            d = next(x for x in issue.evidence if x.evidence_id == ev.def_id)
            held = ev.availability != EvidenceAvailability.MISSING
            c = ClaimRecord(f"clm_{next(claim_n)}", "evidence", issue_id, None,
                            ElementValue.SATISFIED if held else ElementValue.CONTRADICTED,
                            f"The speaker {'has' if held else 'does not have'} {ev.def_id.replace('_', ' ')}.",
                            evidence_id=ev.evidence_id)
            units.append(Unit("evidence", issue_id, (d.held if held else d.missing)[variant], claim=c,
                              evidence_id=ev.evidence_id, meta={"order": 50}))
        units.extend(late)
    for flag in spec.risk_flags:
        issue = lib[spec.issues[0]]
        rf = next(r for r in issue.risk_facts if r.flag == flag)
        units.append(Unit("risk", spec.issues[0], rf.template[variant],
                          claim=ClaimRecord(f"clm_{next(claim_n)}", "risk", spec.issues[0], None,
                                            ElementValue.SATISFIED, f"Risk: {flag.value.replace('_', ' ')}.")))
    _order(spec, units, prng)
    _discourse(spec, units, variant, prng)
    return units


def _order(spec: ScenarioSpec, units: list[Unit], prng) -> None:
    """Chronological for easy; one displacement for medium; shuffled for hard."""
    def chrono_key(u: Unit):
        return (u.sort_date or "9999", u.meta.get("order", 0))

    # within each issue block: element facts are ordered chronologically first
    blocks: list[list[Unit]] = []
    for u in units:
        if u.kind == "setup" or not blocks:
            blocks.append([u])
        else:
            blocks[-1].append(u)
    out: list[Unit] = []
    for b in blocks:
        head = [u for u in b if u.kind in ("setup", "routing")]
        facts = [u for u in b if u.kind == "element" and not u.meta.get("contradiction")]
        rest = [u for u in b if u not in head and u not in facts]
        facts.sort(key=chrono_key)
        if spec.difficulty == Difficulty.MEDIUM and len(facts) >= 2:
            i = prng.randrange(len(facts) - 1)
            facts[i], facts[i + 1] = facts[i + 1], facts[i]
        elif spec.difficulty == Difficulty.HARD and len(facts) >= 2:
            prng.shuffle(facts)
        if spec.difficulty == Difficulty.HARD:
            ev = [u for u in rest if u.kind == "evidence"]
            other = [u for u in rest if u.kind != "evidence"]
            mixed = facts + ev
            prng.shuffle(mixed)
            # a contradiction must come after the statement it contradicts
            out.extend(head + mixed + other)
        else:
            out.extend(head + facts + rest)
    risk = [u for u in out if u.kind == "risk"]
    if risk and spec.difficulty == Difficulty.HARD:
        out = [u for u in out if u.kind != "risk"]
        out.insert(0, risk[0])
    units[:] = out


def _discourse(spec: ScenarioSpec, units: list[Unit], variant: LangVariant, prng) -> None:
    lex = lexicon()["discourse"]
    sg = spec.metadata.gender.value
    diff = spec.difficulty
    n_fill = {Difficulty.EASY: 0, Difficulty.MEDIUM: 1, Difficulty.HARD: 2}[diff]
    idxs = [i for i, u in enumerate(units) if u.kind in ("element", "evidence", "other")]
    for i in prng.sample(idxs, k=min(n_fill, len(idxs))):
        bank = variant_entry(lex["fillers"], variant, sg)
        units[i].prefix = bank[keyed_rng(spec.family_id, i, "fill").randrange(len(bank))]
    # flashback marker when an event fact precedes, in time, the previous event fact
    last = None
    for u in units:
        if u.kind == "element" and u.sort_date and not u.meta.get("contradiction"):
            if last and u.sort_date < last and diff != Difficulty.EASY:
                bank = variant_entry(lex["flashback"], variant, sg)
                u.prefix = bank[keyed_rng(spec.family_id, u.claim.claim_id, "fb").randrange(len(bank))]
            last = max(last or u.sort_date, u.sort_date)
    if diff != Difficulty.EASY or spec.variation == Variation.HIGH_RISK:
        bank = variant_entry(lex["emotion"], variant, sg)
        pos = prng.randrange(1, len(units) + 1)
        units.insert(pos, Unit("emotion", None, bank[keyed_rng(spec.family_id, "emo").randrange(len(bank))]))
    bank = variant_entry(lex["closers"], variant, sg)
    units.append(Unit("closer", None, bank[keyed_rng(spec.family_id, "close").randrange(len(bank))]))


# -------------------------------------------------------------- assemble --

def _lower_first_if_ok(sent: Sentence) -> None:
    """After a Latin-script prefix, lowercase the first letter unless it starts a
    name, the pronoun 'I', or an acronym."""
    first = sent.text.lstrip()
    if not first or not ("A" <= first[0] <= "Z"):
        return
    word = first.split()[0].strip(",.")
    if word in ("I", "I'm", "I've") or word.isupper():
        return
    lead = len(sent.text) - len(first)
    for s in sent.spans:
        if s.start == lead and s.kind == "mention" and s.meta.get("mkind") == "name":
            return
    sent.text = sent.text[:lead] + first[0].lower() + sent.text[lead + 1:]


CONNECTIVES = ("But ", "ಆದರೆ ", "ಆದ್ರೆ ", "Aadre ", "लेकिन ", "Lekin ")


def _strip_leading_connective(sent: Sentence) -> None:
    """A displaced sentence cannot keep a contrastive 'But' that linked it to its old neighbour."""
    for c in CONNECTIVES:
        if sent.text.startswith(c) and all(sp.start >= len(c) for sp in sent.spans):
            sent.text = sent.text[len(c):]
            for sp in sent.spans:
                sp.start -= len(c)
                sp.end -= len(c)
            sent.meta["claim_end"] = sent.meta.get("claim_end", len(sent.text) + len(c)) - len(c)
            return


def apply_hedge(spec: ScenarioSpec, sent: Sentence, variant: LangVariant, key: str) -> None:
    bank = lexicon()["discourse"]["hedges"][variant.value]
    h = bank[keyed_rng(spec.family_id, key, "hedge").randrange(len(bank))]
    if "pre" in h:
        if variant in LATIN_VARIANTS or variant == V.KN_EN_MIXED:
            _lower_first_if_ok(sent)
        sent.prepend(h["pre"], "hedge")
    else:
        sent.insert_before_final_punct(h["post"], "hedge")


def render_units(ctx: DocContext, spec: ScenarioSpec, units: list[Unit], variant: LangVariant,
                 unit_id: str) -> tuple[str, list[tuple[Unit, Sentence, int]]]:
    """Render all units; returns full text and (unit, sentence, offset) triples."""
    events = {e.event_id: e for e in spec.events}
    text = ""
    out = []
    for u in units:
        ev = events.get(u.event_id) if u.event_id else None
        sent = ctx.render(u.template, u.issue, event=ev, evidence_id=u.evidence_id, must_resolve=u.must_resolve)
        if u.hedge:
            apply_hedge(spec, sent, variant, u.claim.claim_id)
        sent.meta["claim_start"] = 0
        sent.meta["claim_end"] = len(sent.text.rstrip())
        if u.prefix:
            _strip_leading_connective(sent)
            if variant in LATIN_VARIANTS or variant == V.KN_EN_MIXED:
                _lower_first_if_ok(sent)
            lead = len(sent.text)
            sent.prepend(u.prefix + " ")
            shift = len(sent.text) - lead
            sent.meta["claim_start"] += shift
            sent.meta["claim_end"] += shift
        if variant in LATIN_VARIANTS or variant == V.KN_EN_MIXED:
            sent.capitalize_first()
        if text:
            text += " "
        out.append((u, sent, len(text)))
        text += sent.text
    return text, out


def _span(unit_id: str, text: str, start: int, end: int) -> Span:
    return Span(unit_id=unit_id, start=start, end=end, text=text[start:end])


def collect(spec: ScenarioSpec, lib, text: str, rendered: list[tuple[Unit, Sentence, int]], unit_id: str):
    """Turn rendered sentences into annotation objects."""
    entities: list[EntityMention] = []
    timexes: list[Timex] = []
    events: list[EventAnnotation] = []
    claims: list[ClaimRecord] = []
    mention_spans: dict[str, list[Span]] = {}
    trigger_spans: dict[str, list[Span]] = {}
    evidence_spans: dict[str, list[Span]] = {}
    stated_ev: set[str] = set()
    spec_events = {e.event_id: e for e in spec.events}
    for u, sent, off in rendered:
        sent_mentions = []
        trig = None
        time_id = None
        negs, hedges = [], []
        for rs in sent.spans:
            sp = _span(unit_id, text, rs.start + off, rs.end + off)
            if rs.kind == "mention":
                m = EntityMention(mention_id=rs.meta["mention_id"], type=EntityType(rs.meta["etype"]), span=sp,
                                  kind=MentionKind(rs.meta["mkind"]), entity_id=rs.meta.get("node_id"))
                entities.append(m)
                sent_mentions.append(m)
                if m.entity_id:
                    target = evidence_spans if m.type == EntityType.EVIDENCE else mention_spans
                    target.setdefault(m.entity_id, []).append(sp)
            elif rs.kind == "timex":
                tx = Timex(id=rs.meta["timex_id"], type=TimexType(rs.meta["ttype"]), value=rs.meta["value"],
                           anchor=rs.meta["anchor"], approximate=rs.meta["approximate"], span=sp)
                timexes.append(tx)
                entities.append(EntityMention(mention_id=rs.meta["mention_id"], type=EntityType.TIME, span=sp,
                                              kind=MentionKind.VALUE, entity_id=None))
                if rs.meta.get("event_id"):
                    time_id = tx.id
            elif rs.kind == "trigger":
                if trig is None:
                    trig = sp
            elif rs.kind == "neg":
                negs.append(sp)
            elif rs.kind == "hedge":
                hedges.append(sp)
        if u.claim is not None:
            c = u.claim
            c.spans = [_span(unit_id, text, off + sent.meta["claim_start"], off + sent.meta["claim_end"])]
            c.negation_cues, c.hedge_cues = negs, hedges
            c.hedged = bool(hedges)
            claims.append(c)
        if u.evidence_id:
            stated_ev.add(u.evidence_id)
        if trig is not None and u.event_id:
            ev = spec_events[u.event_id]
            trigger_spans.setdefault(ev.event_id, []).append(trig)
            args = []
            for m in sent_mentions:
                for slot, role in ev.args.items():
                    if role == "place":
                        if m.type == EntityType.LOCATION:
                            args.append(EventArgument(role="place", mention_id=m.mention_id))
                        continue
                    node = _slot_node(spec, ev.issue_id, slot)
                    if node and m.entity_id == node:
                        args.append(EventArgument(role=role, mention_id=m.mention_id, entity_id=node))
            contra = u.claim is not None and u.claim.polarity == ElementValue.CONTRADICTED
            el = next((e for e in lib[ev.issue_id].elements if e.element_id == ev.element_id), None) \
                if ev.issue_id in lib else None
            hyp = bool(contra and el and el.hypothetical_when_contradicted)
            events.append(EventAnnotation(event_id=ev.event_id, event_type=ev.event_type, trigger=trig,
                                          arguments=_dedupe_args(args), time_id=time_id,
                                          negated=contra and not hyp, hypothetical=hyp))
    return dict(entities=entities, timexes=timexes, events=events, claims=claims, mention_spans=mention_spans,
                trigger_spans=trigger_spans, evidence_spans=evidence_spans, stated_ev=stated_ev)


def _dedupe_args(args: list[EventArgument]) -> list[EventArgument]:
    seen, out = set(), []
    for a in args:
        k = (a.role, a.mention_id)
        if k not in seen:
            seen.add(k)
            out.append(a)
    return out


def _slot_node(spec: ScenarioSpec, issue: IssueId, slot: str) -> str | None:
    ref = f"{issue.value}:{slot}"
    for p in spec.cast:
        if ref in p.refs:
            return p.node_id
    for v in spec.values:
        if ref in v.refs and v.node_id:
            return v.node_id
    return None


def tlinks_for(spec: ScenarioSpec, events: list[EventAnnotation]) -> list[TLink]:
    dates = {e.event_id: e.date for e in spec.events}
    real = {}
    for e in events:
        if not (e.negated or e.hypothetical):
            real.setdefault(e.event_id, e)
    out = []
    for a, b in combinations(sorted(real, key=lambda x: (dates[x], x)), 2):
        rel = TLinkRel.BEFORE if dates[a] < dates[b] else TLinkRel.OVERLAP
        out.append(TLink(source=a, target=b, relation=rel))
    return out


def coref_for(entities: list[EntityMention]) -> list[CorefCluster]:
    clusters: dict[str, list[str]] = {}
    for m in entities:
        if m.type in (EntityType.PERSON, EntityType.ORGANIZATION) and m.entity_id:
            clusters.setdefault(m.entity_id, []).append(m.mention_id)
    return [CorefCluster(entity_id=k, mention_ids=v) for k, v in clusters.items()]


def render_narrative(spec: ScenarioSpec, lib: dict[IssueId, IssueSchema], variant: LangVariant,
                     other_bank: dict | None = None) -> NarrativeSample:
    other = None
    if spec.other_template:
        pool = (other_bank or {}).get("out_of_scope", []) + (other_bank or {}).get("non_legal", [])
        other = next(t for t in pool if t["id"] == spec.other_template)
    sample_id = f"{spec.spec_id}_{variant.value}"
    ctx = DocContext(spec=spec, variant=variant, family=spec.family_id, difficulty=spec.difficulty.value)
    units = plan_units(spec, lib, variant, other)
    text, rendered = render_units(ctx, spec, units, variant, sample_id)
    col = collect(spec, lib, text, rendered, sample_id)
    claims: list[ClaimRecord] = col["claims"]
    if spec.variation in (Variation.OUT_OF_SCOPE, Variation.NON_LEGAL):
        for c in claims:
            c.status = EpistemicStatus.REPORTED
        stated_events = {e.event_id for e in col["events"]}
    else:
        tmp = type("D", (), {"evidence": spec.evidence})
        assign_statuses(claims, supporting_map(tmp, col["stated_ev"]))
        stated_events = {c.event_id for c in claims if c.event_id and c.event_id in col["trigger_spans"]}
    graph = build_graph(spec, lib, claims, col["stated_ev"], col["mention_spans"], col["trigger_spans"],
                        col["evidence_spans"], stated_events=stated_events)
    values = element_values(spec, claims)
    facts = [FactAnnotation(claim_id=c.claim_id, span=c.spans[0], status=c.status, issue_id=c.issue_id,
                            element_id=c.element_id, polarity=c.polarity, hedged=c.hedged,
                            hedge_cues=c.hedge_cues, negation_cues=c.negation_cues) for c in claims]
    elements = [ElementLabel(issue_id=e.issue_id, element_id=e.element_id, critical=e.critical,
                             value=values[(e.issue_id.value, e.element_id)]) for e in spec.elements]
    domains = sorted({i.domain for i in spec.issues if i.domain}, key=lambda d: d.value)
    ann = Annotations(issues=spec.issues, domains=domains, entities=col["entities"], events=col["events"],
                      timexes=col["timexes"], tlinks=tlinks_for(spec, col["events"]),
                      coref=coref_for(col["entities"]), facts=facts, elements=elements, case_graph=graph,
                      provisions=spec.gold_provisions, triage=spec.triage, risk_flags=spec.risk_flags)
    return NarrativeSample(sample_id=sample_id, spec_id=spec.spec_id, family_id=spec.family_id,
                           lang_variant=variant, variation=spec.variation, difficulty=spec.difficulty,
                           conversation_date=spec.conversation_date, text=text, annotations=ann,
                           metadata=spec.metadata,
                           provenance=Provenance(generator="template-v1", generator_version="0.1.0",
                                                 seed=spec.provenance.seed, created="2026-10-24",
                                                 template_ids=[u.kind for u in units][:0]))
