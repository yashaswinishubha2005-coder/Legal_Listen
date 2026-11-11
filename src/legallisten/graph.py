"""Legal Case Graph: people, events, claims, evidence, issues, elements, provisions, missing
information and contradictions, connected by typed edges (aligned with docs/ontology.md).

Every Claim carries an epistemic status (reported / evidence_supported / inferred / conflicting /
unknown). An edge records a connection, never proof: SATISFIES means "the client's statement bears
on this element", not that the element is established.
"""

from __future__ import annotations

from collections import Counter

from .i18n import risk_name, t
from .knowledge import kb
from .policy import hypotheses, identified
from .provisions import cards
from .state import CaseState

EDGE_TYPES = {
    "KIN_OF": ("Person", "Person"), "INVOLVED_IN": ("Person", "Event"), "ASSERTS": ("Person", "Claim"),
    "ABOUT": ("Claim", "Event"), "BEARS_ON": ("Claim", "Element"), "SUPPORTS": ("Evidence", "Claim"),
    "HOLDS": ("Person", "Evidence"), "HAS_ELEMENT": ("Issue", "Element"), "MISSING": ("Element", "Question"),
    "APPLIES_TO": ("Provision", "Issue"), "RELEVANT_BECAUSE": ("Element", "Provision"),
    "CONTRADICTS": ("Claim", "Claim"), "BEFORE": ("Event", "Event"), "ABOUT_CONTRADICTION": ("Contradiction", "Claim"),
    "RAISES": ("Claim", "Issue"),
}


def build(state: CaseState) -> dict:
    k = kb()
    lang = state.lang
    nodes: dict[str, dict] = {}
    edges: list[dict] = []

    def node(nid, ntype, label, **attrs):
        nodes[nid] = {"id": nid, "type": ntype, "label": label, **attrs}

    def edge(src, dst, etype, **attrs):
        if src in nodes and dst in nodes:
            edges.append({"source": src, "target": dst, "type": etype, **attrs})

    node("per_0", "Person", t("the_client", lang), role="client", status="reported")
    for p in state.people:
        node(p.id, "Organization" if p.is_org else "Person", p.label, relation=p.relation, status="reported")
        if not p.is_org:
            edge(p.id, "per_0", "KIN_OF", relation=p.relation)
    shown = set(hypotheses(state)) | set(identified(state))
    for issue in shown:
        node(f"iss_{issue}", "Issue", k.issue_title(issue, lang), belief=state.beliefs.get(issue, 0),
             identified=issue in identified(state), domain=k.domain(issue))
        for el in k.elements_of(issue):
            es = state.elements.get(el.key)
            value = es.value if es and es.value else "not_discussed"
            node(f"el_{el.key}", "Element", el.topic[lang],
                 answer=el.options[value][lang] if value in ("satisfied", "contradicted") else None,
                 question=el.question[lang], issue=issue, order=el.order,
                 value=value, status=es.status if es else "unknown", critical=el.critical, description=el.description)
            edge(f"iss_{issue}", f"el_{el.key}", "HAS_ELEMENT")
            if (not es or es.value in (None, "unknown") or es.status == "conflicting") and el.critical:
                qid = f"q_{el.key}"
                node(qid, "Question", el.question[lang], asked=el.key in state.asked)
                edge(f"el_{el.key}", qid, "MISSING")
    events = []
    in_conflict: dict[str, set[str]] = {}
    for c in state.contradictions:
        if not c.resolved:
            in_conflict.setdefault(c.key, set()).update({c.a.quote, c.b.quote})
    for key, es in state.elements.items():
        el = k.elements.get(key)
        if not el:
            continue
        for i, s in enumerate(es.statements):
            cid = f"clm_{key}_{i}"
            status = es.status
            if s.corrected:
                status = "corrected"
            elif es.status == "conflicting":
                status = "conflicting" if s.quote in in_conflict.get(key, ()) else "reported"
            elif s.value == "unknown":
                status = "unknown"
            elif es.status == "evidence_supported" and s.value != "satisfied":
                status = "reported"
            node(cid, "Claim", s.quote, status=status, value=s.value, turn=s.turn, hedged=s.hedged,
                 gloss_en=s.gloss_en)
            edge("per_0", cid, "ASSERTS")
            edge(cid, f"el_{key}", "BEARS_ON", polarity=s.value)
            if el.issue in shown:
                edge(cid, f"iss_{el.issue}", "RAISES")
        if el.event_type and es.value in ("satisfied", "contradicted"):
            eid = f"evt_{key}"
            node(eid, "Event", el.topic[lang], date=es.date, date_text=es.date_text,
                 negated=es.value == "contradicted", status=es.status)
            events.append((es.date or "", eid))
            for i, s in enumerate(es.statements):
                edge(f"clm_{key}_{i}", eid, "ABOUT")
            for p in state.people:
                if not p.is_org and p.relation not in ("father", "mother", "son", "daughter") and el.issue in shown:
                    edge(p.id, eid, "INVOLVED_IN")
                    break
    dated = sorted((d, e) for d, e in events if d)
    for (d1, e1), (d2, e2) in zip(dated, dated[1:]):
        if d1 < d2:
            edge(e1, e2, "BEFORE")
    for key, ev in state.evidence.items():
        vid = f"evd_{key}"
        node(vid, "Evidence", ev.label, availability=ev.availability, quote=ev.quote)
        if ev.availability == "held":
            edge("per_0", vid, "HOLDS")
            for sk in ev.supports:
                es = state.elements.get(sk)
                if es:
                    for i, s in enumerate(es.statements):
                        if not s.corrected and s.value == "satisfied":
                            edge(vid, f"clm_{sk}_{i}", "SUPPORTS")
    for c in state.contradictions:
        cid = f"con_{c.id}"
        node(cid, "Contradiction", f"{c.a.quote} ↔ {c.b.quote}", resolved=c.resolved, resolution=c.resolution)
        es = state.elements.get(c.key)
        if es:
            idx = {s.quote: i for i, s in enumerate(es.statements)}
            a, b = idx.get(c.a.quote), idx.get(c.b.quote)
            if a is not None and b is not None:
                edge(f"clm_{c.key}_{a}", f"clm_{c.key}_{b}", "CONTRADICTS")
                edge(cid, f"clm_{c.key}_{a}", "ABOUT_CONTRADICTION")
                edge(cid, f"clm_{c.key}_{b}", "ABOUT_CONTRADICTION")
    for card in cards(state):
        pid = f"prv_{card.provision_id}"
        if pid not in nodes:
            node(pid, "Provision", f"{card.provision_id.split(':')[0]} s.{card.section}",
                 act_title=card.act_title, title_hint=card.title_hint, issue=card.issue, regime_note=card.regime_note,
                 verification=card.verification, in_corpus=bool(card.official_text))
        edge(pid, f"iss_{card.issue}", "APPLIES_TO")
        for ek in card.supporting_elements:
            edge(f"el_{ek}", pid, "RELEVANT_BECAUSE")
    for flag, r in state.risks.items():
        node(f"risk_{flag}", "Risk", risk_name(flag, lang), quote=r.quote)
    return {"nodes": list(nodes.values()), "edges": edges, "stats": dict(Counter(n["type"] for n in nodes.values()))}


def validate(graph: dict) -> list[str]:
    """Structural checks: edge endpoint types, no dangling edges, status/edge consistency."""
    errs = []
    types = {n["id"]: n["type"] for n in graph["nodes"]}
    for e in graph["edges"]:
        if e["source"] not in types or e["target"] not in types:
            errs.append(f"dangling edge {e}")
            continue
        want = EDGE_TYPES.get(e["type"])
        if want is None:
            errs.append(f"unknown edge type {e['type']}")
            continue
        s, d = types[e["source"]], types[e["target"]]
        ok_s = s == want[0] or (want[0] == "Person" and s == "Organization")
        ok_d = d == want[1] or (want[1] == "Person" and d == "Organization")
        if not (ok_s and ok_d):
            errs.append(f"{e['type']} {s}->{d}")
    supported = {e["target"] for e in graph["edges"] if e["type"] == "SUPPORTS"}
    contradicted = {e["source"] for e in graph["edges"] if e["type"] == "CONTRADICTS"} | \
                   {e["target"] for e in graph["edges"] if e["type"] == "CONTRADICTS"}
    for n in graph["nodes"]:
        if n["type"] != "Claim":
            continue
        if n["status"] == "evidence_supported" and n["value"] == "satisfied" and n["id"] not in supported:
            errs.append(f"{n['id']} evidence_supported without SUPPORTS")
        if n["status"] == "conflicting" and n["id"] not in contradicted:
            errs.append(f"{n['id']} conflicting without CONTRADICTS")
    order = {}
    for e in graph["edges"]:
        if e["type"] == "BEFORE":
            order.setdefault(e["source"], set()).add(e["target"])
    seen, stack = set(), set()

    def dfs(v):
        if v in stack:
            errs.append("temporal cycle")
            return
        if v in seen:
            return
        seen.add(v)
        stack.add(v)
        for w in order.get(v, ()):
            dfs(w)
        stack.discard(v)

    for v in list(order):
        dfs(v)
    return errs


def insights(state: CaseState) -> dict:
    """Plain-language summary of the graph for the consultation."""
    k = kb()
    lang = state.lang
    people = ", ".join(f"{p.label} ({p.relation.replace('_', ' ')})" for p in state.people) or t("none", lang)
    timeline = []
    for key, es in state.elements.items():
        if es.date and key in k.elements:
            el = k.elements[key]
            timeline.append((es.date, el.options[es.value if es.value in ('satisfied', 'contradicted') else 'satisfied'][lang]))
    if state.incident_date and not timeline:
        timeline.append((state.incident_date, t("the_incident", lang)))
    timeline.sort()
    claims = [es for es in state.elements.values() if es.statements]
    c = Counter(es.status for es in claims)
    ev = ", ".join(f"{e.label} — {t(e.availability if e.availability != 'unknown' else 'status_unknown', lang)}"
                   for e in state.evidence.values()) or t("none", lang)
    missing = []
    for issue in identified(state):
        for el in k.elements_of(issue):
            es = state.elements.get(el.key)
            if el.critical and (not es or es.value in (None, "unknown") or es.status == "conflicting"):
                missing.append(el.question[lang])
    return {
        "people": t("graph_people", lang, x=people),
        "timeline": t("graph_timeline", lang, x=" → ".join(f"{d}: {x}" for d, x in timeline) or t("none", lang)),
        "claims": t("graph_claims", lang, n=len(claims), sup=c.get("evidence_supported", 0), rep=c.get("reported", 0) + c.get("inferred", 0),
                    con=c.get("conflicting", 0)),
        "evidence": t("graph_evidence", lang, x=ev),
        "missing": missing,
    }
