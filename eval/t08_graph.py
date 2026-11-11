"""T8 Case Graph construction.
pred: {"sample_id", "graph": {"nodes": [...], "edges": [...]}} in the release CaseGraph format
(ids are free; nodes are matched by type + key attributes, falling back to span overlap).
Reports node F1, edge F1 and a normalised graph edit distance (insertions + deletions +
relabels of status/value, divided by gold size)."""
from eval.common import by_key, cli, r4
from eval.metrics import prf

KEY = {
    "Person": lambda n: (n.get("synthetic_name") or n.get("role") or "").lower(),
    "Organization": lambda n: n.get("org_type"),
    "Event": lambda n: n.get("event_type"),
    "Claim": lambda n: None,
    "Evidence": lambda n: n.get("evidence_type"),
    "Asset": lambda n: n.get("asset_type"),
    "Account": lambda n: n.get("account_type"),
    "Issue": lambda n: n.get("issue_id"),
    "Element": lambda n: (n.get("issue_id"), n.get("element_id")),
    "Provision": lambda n: n.get("provision_id"),
    "Question": lambda n: n.get("template_id"),
}


def _spans(n):
    return [(s["start"], s["end"]) for s in n.get("source_spans", [])]


def match_nodes(gn, pn):
    m, used = {}, set()
    for strategy in ("key", "span"):
        for g in gn:
            if g["id"] in m:
                continue
            for p in pn:
                if p["id"] in used or p["type"] != g["type"]:
                    continue
                if strategy == "key":
                    k = KEY[g["type"]](g)
                    ok = k is not None and k == KEY[p["type"]](p)
                else:
                    ok = any(a < d and c < b for a, b in _spans(g) for c, d in _spans(p))
                if ok:
                    m[g["id"]] = p["id"]; used.add(p["id"]); break
    return m


def score(gold, pred):
    P = by_key(pred, "sample_id")
    n_tp = n_fp = n_fn = e_tp = e_fp = e_fn = 0
    geds = []
    for g in gold:
        G = g["annotations"]["case_graph"]
        Q = P.get(g["sample_id"], {}).get("graph", {"nodes": [], "edges": []})
        m = match_nodes(G["nodes"], Q["nodes"])
        n_tp += len(m); n_fp += len(Q["nodes"]) - len(m); n_fn += len(G["nodes"]) - len(m)
        inv = m
        ge = {(e["type"], e["source_id"], e["target_id"]) for e in G["edges"]}
        rev = {v: k for k, v in m.items()}
        pe = {(e["type"], rev.get(e["source_id"], "?" + e["source_id"]), rev.get(e["target_id"], "?" + e["target_id"]))
              for e in Q["edges"]}
        sym = {"OVERLAP", "CONTRADICTS"}
        norm = lambda s: {(t, *sorted((a, b))) if t in sym else (t, a, b) for t, a, b in s}  # noqa: E731
        ge, pe = norm(ge), norm(pe)
        e_tp += len(ge & pe); e_fp += len(pe - ge); e_fn += len(ge - pe)
        relabel = 0
        qn = {n["id"]: n for n in Q["nodes"]}
        for gnode in G["nodes"]:
            if gnode["id"] in m:
                q = qn[m[gnode["id"]]]
                relabel += (q.get("status") != gnode.get("status")) + (q.get("value") != gnode.get("value"))
        cost = (len(G["nodes"]) - len(m)) + (len(Q["nodes"]) - len(m)) + len(ge ^ pe) + relabel
        geds.append(cost / max(1, len(G["nodes"]) + len(G["edges"])))
    return r4({"node": prf(n_tp, n_fp, n_fn), "edge": prf(e_tp, e_fp, e_fn),
               "normalised_graph_edit_distance": sum(geds) / max(1, len(geds))})


if __name__ == "__main__":
    cli("T8 case graph", "narratives", score)
