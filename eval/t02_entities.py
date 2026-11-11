"""T2 Entity extraction. pred: {"sample_id", "entities": [{"start", "end", "type"}]}
strict  = exact boundaries + type;  partial = overlapping boundaries + type (one-to-one)."""
from collections import Counter, defaultdict

from eval.common import by_key, cli, r4
from eval.metrics import prf


def _strict(G, Q):
    g, q = Counter(G), Counter(Q)
    tp = sum((g & q).values())
    return prf(tp, len(Q) - tp, len(G) - tp)


def _partial(G, Q):
    gs = defaultdict(list)
    for x in G:
        gs[x[0]].append(x)
    qs = defaultdict(list)
    for x in Q:
        qs[x[0]].append(x)
    tp = 0
    for sid, qq in qs.items():
        used = set()
        for q in qq:
            for i, g in enumerate(gs.get(sid, [])):
                if i not in used and g[3] == q[3] and g[1] < q[2] and q[1] < g[2]:
                    used.add(i)
                    tp += 1
                    break
    return prf(tp, len(Q) - tp, len(G) - tp)


def score(gold, pred):
    P = by_key(pred, "sample_id")
    G, Q = [], []
    for g in gold:
        sid = g["sample_id"]
        G += [(sid, m["span"]["start"], m["span"]["end"], m["type"]) for m in g["annotations"]["entities"]]
        Q += [(sid, e["start"], e["end"], e["type"]) for e in P.get(sid, {}).get("entities", [])]
    by_type = {t: _partial([x for x in G if x[3] == t], [x for x in Q if x[3] == t])["f1"]
               for t in sorted({x[3] for x in G})}
    return r4({"n_gold": len(G), "n_pred": len(Q), "strict": _strict(G, Q), "partial": _partial(G, Q),
               "partial_f1_by_type": by_type})


if __name__ == "__main__":
    cli("T2 entity extraction", "narratives", score)
