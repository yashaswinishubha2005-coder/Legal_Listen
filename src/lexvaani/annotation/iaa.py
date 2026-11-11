"""Inter-annotator agreement: Cohen's / Fleiss' / weighted kappa, span F1, graph F1,
soft labels, and an adjudication queue.

    python -m lexvaani.annotation.iaa annotations_a.jsonl annotations_b.jsonl
"""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict


def cohen_kappa(a: list, b: list) -> float:
    assert len(a) == len(b) and a
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(a) | set(b)) / (n * n)
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def weighted_kappa(a: list, b: list, labels: list) -> float:
    """Quadratic-weighted kappa for ordinal labels."""
    idx = {l: i for i, l in enumerate(labels)}
    k = len(labels)
    n = len(a)
    O = [[0.0] * k for _ in range(k)]
    for x, y in zip(a, b):
        O[idx[x]][idx[y]] += 1
    ra = [sum(r) for r in O]
    cb = [sum(O[i][j] for i in range(k)) for j in range(k)]
    num = den = 0.0
    for i in range(k):
        for j in range(k):
            w = ((i - j) ** 2) / ((k - 1) ** 2) if k > 1 else 0
            num += w * O[i][j]
            den += w * ra[i] * cb[j] / n
    return 1.0 if den == 0 else 1 - num / den


def fleiss_kappa(items: list[list]) -> float:
    """items: one list of labels (one per annotator) per item; equal annotators per item."""
    cats = sorted({l for it in items for l in it})
    n = len(items[0])
    N = len(items)
    p_j = {c: sum(it.count(c) for it in items) / (N * n) for c in cats}
    P_i = [(sum(it.count(c) ** 2 for c in cats) - n) / (n * (n - 1)) for it in items]
    P_bar = sum(P_i) / N
    P_e = sum(v * v for v in p_j.values())
    return 1.0 if P_e == 1 else (P_bar - P_e) / (1 - P_e)


def span_f1(a: set[tuple], b: set[tuple]) -> float:
    """Agreement as F1 treating annotator A as reference (symmetric)."""
    if not a and not b:
        return 1.0
    tp = len(a & b)
    return 2 * tp / (len(a) + len(b)) if (a or b) else 1.0


def graph_f1(nodes_a: set, nodes_b: set, edges_a: set, edges_b: set) -> dict:
    return {"node_f1": span_f1(nodes_a, nodes_b), "edge_f1": span_f1(edges_a, edges_b)}


def soft_label(labels: list) -> dict[str, float]:
    c = Counter(labels)
    return {k: v / len(labels) for k, v in sorted(c.items())}


def compute(ann_a: list[dict], ann_b: list[dict]) -> dict:
    """Annotation records: {"item_id", "task", "label"} for categorical tasks or
    {"item_id", "task", "spans": [[start, end, type], ...]} for span tasks."""
    A = {(r["item_id"], r["task"]): r for r in ann_a}
    B = {(r["item_id"], r["task"]): r for r in ann_b}
    common = sorted(set(A) & set(B))
    by_task: dict[str, list] = defaultdict(list)
    for key in common:
        by_task[key[1]].append((A[key], B[key]))
    out = {}
    disagreements = []
    for task, pairs in by_task.items():
        if "label" in pairs[0][0]:
            la, lb = [p[0]["label"] for p in pairs], [p[1]["label"] for p in pairs]
            out[task] = {"n": len(pairs), "cohen_kappa": round(cohen_kappa(la, lb), 4),
                         "raw_agreement": round(sum(x == y for x, y in zip(la, lb)) / len(la), 4)}
            disagreements += [{"item_id": p[0]["item_id"], "task": task, "a": p[0]["label"], "b": p[1]["label"]}
                              for p in pairs if p[0]["label"] != p[1]["label"]]
        else:
            f1s = [span_f1({tuple(s) for s in p[0]["spans"]}, {tuple(s) for s in p[1]["spans"]}) for p in pairs]
            out[task] = {"n": len(pairs), "span_f1_strict": round(sum(f1s) / len(f1s), 4)}
            disagreements += [{"item_id": p[0]["item_id"], "task": task, "f1": round(f, 3)}
                              for p, f in zip(pairs, f1s) if f < 1.0]
    return {"agreement": out, "adjudication_queue": disagreements}


def main() -> None:  # pragma: no cover - CLI
    a = [json.loads(l) for l in open(sys.argv[1], encoding="utf-8") if l.strip()]
    b = [json.loads(l) for l in open(sys.argv[2], encoding="utf-8") if l.strip()]
    res = compute(a, b)
    print(json.dumps(res["agreement"], indent=2))
    with open("adjudication_queue.jsonl", "w", encoding="utf-8") as f:
        for d in res["adjudication_queue"]:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    print(f"{len(res['adjudication_queue'])} items written to adjudication_queue.jsonl")


if __name__ == "__main__":  # pragma: no cover
    main()
