"""Official metric implementations for LexVaani-IN (no external dependencies)."""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from typing import Hashable, Iterable


# ------------------------------------------------------------ set / class F1
def prf(tp: int, fp: int, fn: int) -> dict:
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return {"precision": p, "recall": r, "f1": f}


def multilabel_f1(gold: list[set], pred: list[set]) -> dict:
    labels = sorted(set().union(*gold, *pred)) if gold else []
    tp = fp = fn = 0
    per = {}
    for l in labels:
        t = sum(1 for g, p in zip(gold, pred) if l in g and l in p)
        f_p = sum(1 for g, p in zip(gold, pred) if l not in g and l in p)
        f_n = sum(1 for g, p in zip(gold, pred) if l in g and l not in p)
        tp, fp, fn = tp + t, fp + f_p, fn + f_n
        per[l] = prf(t, f_p, f_n)["f1"]
    gold_labels = sorted(set().union(*gold)) if gold else []
    macro = sum(per[l] for l in gold_labels) / len(gold_labels) if gold_labels else 0.0
    return {"micro_f1": prf(tp, fp, fn)["f1"], "macro_f1": macro, "per_label_f1": per}


def classification(gold: list[Hashable], pred: list[Hashable], labels: Iterable | None = None) -> dict:
    labels = sorted(set(gold) | set(pred), key=str) if labels is None else list(labels)
    per = {}
    for l in labels:
        tp = sum(g == l and p == l for g, p in zip(gold, pred))
        fp = sum(g != l and p == l for g, p in zip(gold, pred))
        fn = sum(g == l and p != l for g, p in zip(gold, pred))
        per[str(l)] = prf(tp, fp, fn)
    present = [str(l) for l in labels if l in set(gold)]
    acc = sum(g == p for g, p in zip(gold, pred)) / len(gold) if gold else 0.0
    return {"accuracy": acc, "macro_f1": sum(per[l]["f1"] for l in present) / len(present) if present else 0.0,
            "per_class": per}


def top_k_accuracy(gold: list[set], ranked: list[list], k: int) -> float:
    if not gold:
        return 0.0
    return sum(1 for g, r in zip(gold, ranked) if g & set(r[:k])) / len(gold)


# ------------------------------------------------------------------- spans
def overlaps(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def span_f1(gold: list[tuple], pred: list[tuple], mode: str = "strict") -> dict:
    """Items are (start, end, type). strict = exact boundaries + type;
    partial = any overlap + same type (each gold/pred matched at most once)."""
    if mode == "strict":
        g, p = Counter(gold), Counter(pred)
        tp = sum((g & p).values())
        return prf(tp, sum(p.values()) - tp, sum(g.values()) - tp)
    used = set()
    tp = 0
    for pi, ps in enumerate(pred):
        for gi, gs in enumerate(gold):
            if gi not in used and gs[2] == ps[2] and overlaps(gs[:2], ps[:2]):
                used.add(gi)
                tp += 1
                break
    return prf(tp, len(pred) - tp, len(gold) - tp)


# -------------------------------------------------------------- coreference
def _muc(key: list[set], resp: list[set]) -> tuple[float, float]:
    def part(clusters, other):
        num = den = 0
        for c in clusters:
            if len(c) < 1:
                continue
            parts = set()
            left = set(c)
            for o in other:
                inter = c & o
                if inter:
                    parts.add(frozenset(inter))
                    left -= inter
            n_parts = len(parts) + len(left)
            num += len(c) - n_parts
            den += len(c) - 1
        return num, den
    rn, rd = part(key, resp)
    pn, pd = part(resp, key)
    # MUC is undefined without links; a side with no links is treated as perfectly recalled / precise
    return (rn / rd if rd else 1.0), (pn / pd if pd else 1.0)


def _b3(key: list[set], resp: list[set]) -> tuple[float, float]:
    km = {m: c for c in key for m in c}
    rm = {m: c for c in resp for m in c}
    rec = sum(len(km[m] & rm.get(m, set())) / len(km[m]) for m in km) / len(km) if km else 0.0
    pre = sum(len(rm[m] & km.get(m, set())) / len(rm[m]) for m in rm) / len(rm) if rm else 0.0
    return rec, pre


def hungarian(cost: list[list[float]]) -> list[tuple[int, int]]:
    """Minimum-cost assignment for a rectangular matrix (Kuhn-Munkres, O(n^3))."""
    n, m = len(cost), len(cost[0]) if cost else 0
    if n == 0 or m == 0:
        return []
    size = max(n, m)
    big = max(max(r) for r in cost) + 1 if cost else 1
    C = [[cost[i][j] if i < n and j < m else big for j in range(size)] for i in range(size)]
    u = [0.0] * (size + 1)
    v = [0.0] * (size + 1)
    p = [0] * (size + 1)
    way = [0] * (size + 1)
    for i in range(1, size + 1):
        p[0] = i
        j0 = 0
        minv = [math.inf] * (size + 1)
        used = [False] * (size + 1)
        while True:
            used[j0] = True
            i0, delta, j1 = p[j0], math.inf, 0
            for j in range(1, size + 1):
                if not used[j]:
                    cur = C[i0 - 1][j - 1] - u[i0] - v[j]
                    if cur < minv[j]:
                        minv[j], way[j] = cur, j0
                    if minv[j] < delta:
                        delta, j1 = minv[j], j
            for j in range(size + 1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minv[j] -= delta
            j0 = j1
            if p[j0] == 0:
                break
        while True:
            j1 = way[j0]
            p[j0] = p[j1]
            j0 = j1
            if j0 == 0:
                break
    return [(p[j] - 1, j - 1) for j in range(1, size + 1) if p[j] and p[j] - 1 < n and j - 1 < m]


def _ceafe(key: list[set], resp: list[set]) -> tuple[float, float]:
    if not key or not resp:
        return 0.0, 0.0
    phi = lambda k, r: 2 * len(k & r) / (len(k) + len(r))  # noqa: E731
    sim = [[phi(k, r) for r in resp] for k in key]
    match = hungarian([[-s for s in row] for row in sim])
    total = sum(sim[i][j] for i, j in match)
    return total / len(key), total / len(resp)


def conll_f1(key: list[set], resp: list[set]) -> dict:
    out = {}
    for name, fn in (("muc", _muc), ("b3", _b3), ("ceafe", _ceafe)):
        r, p = fn(key, resp)
        out[name] = {"recall": r, "precision": p, "f1": 2 * p * r / (p + r) if p + r else 0.0}
    out["conll_f1"] = sum(out[k]["f1"] for k in ("muc", "b3", "ceafe")) / 3
    return out


# ---------------------------------------------------------------- ranking
def mrr(gold_sets: list[set], ranked: list[list]) -> float:
    tot = 0.0
    for g, r in zip(gold_sets, ranked):
        for i, x in enumerate(r, start=1):
            if x in g:
                tot += 1 / i
                break
    return tot / len(gold_sets) if gold_sets else 0.0


def recall_at_k(gold_sets: list[set], ranked: list[list], k: int) -> float:
    vals = [len(g & set(r[:k])) / len(g) for g, r in zip(gold_sets, ranked) if g]
    return sum(vals) / len(vals) if vals else 0.0


def ndcg_at_k(gold_sets: list[set], ranked: list[list], k: int) -> float:
    vals = []
    for g, r in zip(gold_sets, ranked):
        if not g:
            continue
        dcg = sum(1 / math.log2(i + 1) for i, x in enumerate(r[:k], start=1) if x in g)
        idcg = sum(1 / math.log2(i + 1) for i in range(1, min(len(g), k) + 1))
        vals.append(dcg / idcg)
    return sum(vals) / len(vals) if vals else 0.0


# ------------------------------------------------------------- calibration
def ece(confidences: list[float], correct: list[bool], bins: int = 10) -> float:
    if not confidences:
        return 0.0
    buckets = defaultdict(list)
    for c, ok in zip(confidences, correct):
        buckets[min(bins - 1, int(c * bins))].append((c, ok))
    n = len(confidences)
    return sum(len(b) / n * abs(sum(c for c, _ in b) / len(b) - sum(ok for _, ok in b) / len(b))
               for b in buckets.values())


# ----------------------------------------------------------------- text gen
def chrf(hyp: str, ref: str, n: int = 6, beta: float = 2.0) -> float:
    """chrF (Popović 2015): character n-gram F-beta, averaged over n = 1..6, whitespace removed."""
    h, r = re.sub(r"\s+", "", hyp), re.sub(r"\s+", "", ref)
    ps, rs = [], []
    for k in range(1, n + 1):
        hc = Counter(h[i:i + k] for i in range(len(h) - k + 1))
        rc = Counter(r[i:i + k] for i in range(len(r) - k + 1))
        if not hc or not rc:
            continue
        m = sum((hc & rc).values())
        ps.append(m / sum(hc.values()))
        rs.append(m / sum(rc.values()))
    if not ps:
        return 0.0
    p, rr = sum(ps) / len(ps), sum(rs) / len(rs)
    if p + rr == 0:
        return 0.0
    b2 = beta * beta
    return 100 * (1 + b2) * p * rr / (b2 * p + rr)


def readability(text: str, lang: str) -> dict:
    """English: Flesch reading ease. kn/hi: words per sentence and characters per word
    (proxies; no validated formula exists for these languages)."""
    sents = [s for s in re.split(r"[.?!।]+", text) if s.strip()]
    words = re.findall(r"[\wऀ-ॿಀ-೿]+", text)
    wps = len(words) / max(1, len(sents))
    cpw = sum(len(w) for w in words) / max(1, len(words))
    out = {"words_per_sentence": wps, "chars_per_word": cpw}
    if lang == "en":
        syl = sum(max(1, len(re.findall(r"[aeiouy]+", w.lower()))) for w in words)
        out["flesch_reading_ease"] = 206.835 - 1.015 * wps - 84.6 * (syl / max(1, len(words)))
    return out
