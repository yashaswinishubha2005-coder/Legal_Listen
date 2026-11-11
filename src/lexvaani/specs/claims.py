"""Claim records and the Case Graph builder shared by specs, narratives and dialogues.

A ClaimRecord is one assertion the user makes. The same builder produces the
spec-level gold graph (all revealed facts, no spans) and the narrative-level
graph (only facts stated in that narrative, with spans).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import combinations

from lexvaani.schemas.common import EpistemicStatus, IssueId, Span
from lexvaani.schemas.issue_library import IssueSchema
from lexvaani.schemas.ontology import CaseGraph, ElementValue
from lexvaani.schemas.spec import ScenarioSpec

S = EpistemicStatus


@dataclass
class ClaimRecord:
    claim_id: str
    kind: str                         # element | evidence | risk | setup | other
    issue_id: IssueId | None
    element_id: str | None
    polarity: ElementValue            # satisfied | contradicted (evidence: held=satisfied)
    proposition: str
    status: EpistemicStatus = S.REPORTED
    fact_id: str | None = None
    event_id: str | None = None
    evidence_id: str | None = None
    hedged: bool = False
    spans: list[Span] = field(default_factory=list)
    hedge_cues: list[Span] = field(default_factory=list)
    negation_cues: list[Span] = field(default_factory=list)
    turn_index: int | None = None
    contradicts: str | None = None    # claim id of the opposite-polarity claim
    corrects: str | None = None


def element_values(spec: ScenarioSpec, claims: list[ClaimRecord]) -> dict[tuple[str, str], ElementValue]:
    """Element value established by a set of claims (T7 rule, guidelines §T7)."""
    out: dict[tuple[str, str], ElementValue] = {}
    for et in spec.elements:
        key = (et.issue_id.value, et.element_id)
        pols = {c.polarity for c in claims if c.kind == "element" and c.issue_id == et.issue_id
                and c.element_id == et.element_id and c.status != S.UNKNOWN and c.corrects is None
                and not _is_corrected(c, claims)}
        conflicting = any(c.status == S.CONFLICTING for c in claims
                          if c.kind == "element" and c.issue_id == et.issue_id and c.element_id == et.element_id)
        if conflicting or len(pols) > 1:
            out[key] = ElementValue.UNKNOWN
        elif pols:
            out[key] = pols.pop()
        else:
            out[key] = ElementValue.UNKNOWN
        # a correction replaces the corrected claim's polarity
        corr = [c for c in claims if c.corrects and c.issue_id == et.issue_id and c.element_id == et.element_id]
        if corr and not conflicting:
            out[key] = corr[-1].polarity
    return out


def _is_corrected(c: ClaimRecord, claims: list[ClaimRecord]) -> bool:
    return any(o.corrects == c.claim_id for o in claims)


def assign_statuses(claims: list[ClaimRecord], supporting: dict[tuple[str, str], list[str]]) -> None:
    """Set epistemic status. Precedence: conflicting > evidence_supported > reported.
    ``supporting`` maps (issue, element) -> evidence ids held/obtainable AND stated."""
    for c in claims:
        if c.status in (S.UNKNOWN, S.INFERRED):
            continue
        if c.contradicts:
            c.status = S.CONFLICTING
        elif c.kind == "element" and c.polarity == ElementValue.SATISFIED and supporting.get(
                (c.issue_id.value, c.element_id)):
            c.status = S.EVIDENCE_SUPPORTED
        else:
            c.status = S.REPORTED


def build_graph(spec: ScenarioSpec, lib: dict[IssueId, IssueSchema], claims: list[ClaimRecord],
                stated_evidence: set[str], mention_spans: dict[str, list[Span]] | None = None,
                trigger_spans: dict[str, list[Span]] | None = None,
                evidence_spans: dict[str, list[Span]] | None = None,
                stated_events: set[str] | None = None) -> CaseGraph:
    mention_spans = mention_spans or {}
    trigger_spans = trigger_spans or {}
    evidence_spans = evidence_spans or {}
    nodes: list[dict] = []
    edges: list[dict] = []
    eid = iter(range(1, 10_000))

    def edge(t: str, s: str, tgt: str, status: S, attrs: dict | None = None, spans=None) -> None:
        if t in ("OVERLAP", "CONTRADICTS") and s > tgt:
            s, tgt = tgt, s
        edges.append({"id": f"e_{next(eid)}", "type": t, "source_id": s, "target_id": tgt,
                      "status": status.value, "attributes": attrs or {},
                      "source_spans": [x.model_dump() for x in (spans or [])]})

    def sp(node_id: str) -> list[dict]:
        return [x.model_dump() for x in mention_spans.get(node_id, [])]

    # --- people / orgs / assets / accounts
    nodes.append({"type": "Person", "id": "per_0", "label": "speaker", "role": "speaker",
                  "gender": spec.metadata.gender.value, "status": "reported"})
    for p in spec.cast:
        if p.is_org:
            kind = {"organization": "Organization", "account": "Account", "asset": "Asset"}[p.role] \
                if p.role in ("organization", "account", "asset") else "Organization"
            if kind == "Organization":
                nodes.append({"type": "Organization", "id": p.node_id, "label": p.slot.lower(),
                              "org_type": p.noun, "status": "reported", "source_spans": sp(p.node_id)})
            elif kind == "Account":
                nodes.append({"type": "Account", "id": p.node_id, "label": p.slot.lower(),
                              "account_type": p.noun, "status": "reported", "source_spans": sp(p.node_id)})
                edge("OWNS", "per_0", p.node_id, S.REPORTED)
            else:
                nodes.append({"type": "Asset", "id": p.node_id, "label": p.slot.lower(),
                              "asset_type": p.noun, "status": "reported", "source_spans": sp(p.node_id)})
            continue
        nodes.append({"type": "Person", "id": p.node_id, "label": p.name or p.noun, "role": p.role
                      if p.role in ("complainant", "respondent", "witness", "other") else "other",
                      "gender": p.gender if p.gender in ("female", "male") else "unknown",
                      "is_minor": p.is_minor, "synthetic_name": p.name, "status": "reported",
                      "source_spans": sp(p.node_id)})
        if p.kin_relation:
            first = mention_spans.get(p.node_id, [])[:1]
            edge("KIN_OF", p.node_id, "per_0", S.REPORTED,
                 {"relation": p.kin_relation, "surface_term": p.noun}, first)
    for v in spec.values:
        if v.node_id and v.kind == "item":
            from lexvaani.render.lexicon import item as lex_item
            nodes.append({"type": "Asset", "id": v.node_id, "label": v.key,
                          "asset_type": lex_item(v.key)["asset_type"], "status": "reported",
                          "source_spans": sp(v.node_id)})
            edge("OWNS", "per_0", v.node_id, S.REPORTED)
    # affiliations (e.g. recovery agent -> lender)
    for p in spec.cast:
        if p.is_org:
            continue
        for i in spec.issues:
            if i not in lib:
                continue
            slot = next((c for c in lib[i].cast if c.slot == p.slot), None)
            if slot and slot.affiliated_with:
                org = next((o for o in spec.cast if o.slot == slot.affiliated_with), None)
                if org:
                    edge("AFFILIATED_WITH", p.node_id, org.node_id, S.REPORTED)
                break

    # --- events
    ev_ids = stated_events if stated_events is not None else {e.event_id for e in spec.events}
    events = [e for e in spec.events if e.event_id in ev_ids]
    by_slot = {p.slot: p.node_id for p in spec.cast}
    by_slot.update({v.slot: v.node_id for v in spec.values if v.node_id})
    for e in events:
        trig = trigger_spans.get(e.event_id, [])
        nodes.append({"type": "Event", "id": e.event_id, "label": e.event_type, "event_type": e.event_type,
                      "trigger": trig[0].model_dump() if trig else None, "negated": e.negated,
                      "hypothetical": e.hypothetical, "status": "reported",
                      "source_spans": [x.model_dump() for x in trig]})
        for slot, role in e.args.items():
            if role == "place" or slot not in by_slot:
                continue
            edge("PARTICIPANT_IN", by_slot[slot], e.event_id, S.REPORTED, {"role": role})
    dated = sorted(events, key=lambda e: e.date)
    for a, b in combinations(dated, 2):
        if a.negated or b.negated or a.hypothetical or b.hypothetical:
            continue
        if a.date < b.date:
            edge("BEFORE", a.event_id, b.event_id, S.REPORTED)
        elif a.date == b.date:
            edge("OVERLAP", a.event_id, b.event_id, S.REPORTED)
    for issue_id in spec.issues:
        if issue_id not in lib:
            continue
        for el in lib[issue_id].elements:
            if not el.caused_by:
                continue
            src = next((e for e in events if e.issue_id == issue_id and e.element_id == el.caused_by), None)
            dst = next((e for e in events if e.issue_id == issue_id and e.element_id == el.element_id), None)
            if src and dst and not (src.negated or dst.negated):
                edge("CAUSES", src.event_id, dst.event_id, S.INFERRED)

    # --- evidence
    for ev in spec.evidence:
        if ev.evidence_id not in stated_evidence:
            continue
        defn = next(d for d in lib[ev.issue_id].evidence if d.evidence_id == ev.def_id)
        nodes.append({"type": "Evidence", "id": ev.evidence_id, "label": ev.def_id,
                      "evidence_type": defn.evidence_type.value, "availability": ev.availability.value,
                      "status": "reported",
                      "source_spans": [x.model_dump() for x in evidence_spans.get(ev.evidence_id, [])]})
        if ev.availability.value in ("held", "obtainable"):
            edge("HOLDS", "per_0", ev.evidence_id, S.REPORTED)

    # --- claims
    for c in claims:
        nodes.append({"type": "Claim", "id": c.claim_id, "label": c.kind, "proposition": c.proposition,
                      "polarity": "positive" if c.polarity == ElementValue.SATISFIED else "negative",
                      "hedged": c.hedged, "status": c.status.value, "turn_index": c.turn_index,
                      "hedge_cues": [x.model_dump() for x in c.hedge_cues],
                      "negation_cues": [x.model_dump() for x in c.negation_cues],
                      "source_spans": [x.model_dump() for x in c.spans]})
        edge("ASSERTS", "per_0", c.claim_id, S.REPORTED)
        if c.event_id and c.event_id in ev_ids:
            edge("ABOUT", c.claim_id, c.event_id, S.REPORTED)
        else:
            resp = next((p for p in spec.cast if p.role == "respondent"), None)
            if resp:
                edge("ABOUT", c.claim_id, resp.node_id, S.REPORTED)
        if c.kind == "element" and c.evidence_id is None:
            for ev in spec.evidence:
                if (ev.evidence_id in stated_evidence and ev.issue_id == c.issue_id
                        and c.element_id in ev.supports and ev.availability.value in ("held", "obtainable")
                        and c.polarity == ElementValue.SATISFIED):
                    edge("SUPPORTS", ev.evidence_id, c.claim_id, S.REPORTED)
        if c.contradicts and c.claim_id < c.contradicts:
            edge("CONTRADICTS", c.claim_id, c.contradicts, S.CONFLICTING)
        if c.corrects:
            edge("CORRECTS", c.claim_id, c.corrects, S.REPORTED)

    # --- issues, elements, provisions
    values = element_values(spec, claims)
    elm_n = iter(range(1, 1000))
    for i_n, issue_id in enumerate(spec.issues, start=1):
        iss = f"iss_{i_n}"
        nodes.append({"type": "Issue", "id": iss, "label": issue_id.value, "issue_id": issue_id.value,
                      "status": "inferred"})
        if issue_id not in lib:
            continue
        for c in claims:
            if c.kind == "element" and c.issue_id == issue_id and c.polarity == ElementValue.SATISFIED \
                    and c.status != S.CONFLICTING:
                if c.event_id and c.event_id in ev_ids:
                    edge("INDICATES", c.event_id, iss, S.INFERRED)
                else:
                    edge("INDICATES", c.claim_id, iss, S.INFERRED)
        for et in [e for e in spec.elements if e.issue_id == issue_id]:
            el_id = f"elm_{next(elm_n)}"
            val = values[(issue_id.value, et.element_id)]
            status = {ElementValue.SATISFIED: S.REPORTED, ElementValue.CONTRADICTED: S.REPORTED,
                      ElementValue.UNKNOWN: S.UNKNOWN}[val]
            rel = [c for c in claims if c.kind == "element" and c.issue_id == issue_id
                   and c.element_id == et.element_id and c.status != S.UNKNOWN]
            if val != ElementValue.UNKNOWN and any(c.status == S.EVIDENCE_SUPPORTED for c in rel):
                status = S.EVIDENCE_SUPPORTED
            nodes.append({"type": "Element", "id": el_id, "label": et.element_id, "issue_id": issue_id.value,
                          "element_id": et.element_id, "critical": et.critical, "value": val.value,
                          "status": status.value})
            edge("HAS_ELEMENT", iss, el_id, S.INFERRED)
            if val == ElementValue.UNKNOWN:
                edge("LACKS", iss, el_id, S.UNKNOWN)
            else:
                for c in rel:
                    if c.polarity == val and not _is_corrected(c, claims):
                        edge("SATISFIES" if val == ElementValue.SATISFIED else "REFUTES",
                             c.claim_id, el_id, c.status)
    for p_n, pid in enumerate(spec.gold_provisions, start=1):
        prv = f"prv_{p_n}"
        nodes.append({"type": "Provision", "id": prv, "label": pid, "provision_id": pid, "status": "inferred"})
        for i_n, issue_id in enumerate(spec.issues, start=1):
            if issue_id in lib and any(cp.provision_id == pid for cp in lib[issue_id].candidate_provisions):
                edge("APPLIES_TO", prv, f"iss_{i_n}", S.INFERRED)
    return CaseGraph.model_validate({"nodes": nodes, "edges": edges})
