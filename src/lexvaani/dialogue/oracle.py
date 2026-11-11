"""Next-question oracle (T9). Formal definition: docs/tasks.md §T9.

Belief model: one independent Bernoulli b_h = P(issue h applies) per hypothesis
h in H = gold issues ∪ confusable issues. Each element e belongs to one issue h(e):

    P(e = satisfied | h present) = 0.9 (critical) / 0.7 (non-critical)
    P(e = satisfied | h absent)  = 0.2

A known value updates b_{h(e)} by Bayes' rule; "unknown" answers do not update.

Score of asking about element e (not yet known or asked):

    score(e) = w(e) * ( IG(e) + b_{h(e)} * H(V_e) )

    IG(e)  = H(b_h) - E_{a ~ P(V_e)} [ H(b_h | a) ]     expected entropy reduction over the issue
    H(V_e) = binary entropy of the predicted element value  (uncertainty about the element itself,
             counted only in proportion to how likely its issue is)
    w(e)   = 2 if critical else 1

gold_best = argmax (score - 0.001 * order(e)): ties are broken by the issue library's
interview order, so gold_best is deterministic; acceptable_set = {e : score(e) >= 0.9 * max score}.
The oracle uses only the dialogue state (never the hidden answer), so it is a
fair target for models that see the same state.
"""

from __future__ import annotations

import math

P_SAT_PRESENT = {True: 0.9, False: 0.7}
P_SAT_ABSENT = 0.2
PRIOR = 0.5
ACCEPT_RATIO = 0.9
MIN_SCORE = 0.2


def h2(p: float) -> float:
    if p <= 0 or p >= 1:
        return 0.0
    return -(p * math.log2(p) + (1 - p) * math.log2(1 - p))


def update(b: float, critical: bool, satisfied: bool) -> float:
    p1 = P_SAT_PRESENT[critical] if satisfied else 1 - P_SAT_PRESENT[critical]
    p0 = P_SAT_ABSENT if satisfied else 1 - P_SAT_ABSENT
    num = b * p1
    den = num + (1 - b) * p0
    return num / den if den else b


def beliefs(hypotheses: list[str], known: dict[str, str], criticality: dict[str, bool]) -> dict[str, float]:
    """known: 'issue|element' -> satisfied|contradicted|unknown."""
    b = {h: PRIOR for h in hypotheses}
    for key, val in known.items():
        issue, _ = key.split("|", 1)
        if issue in b and val in ("satisfied", "contradicted"):
            b[issue] = update(b[issue], criticality.get(key, False), val == "satisfied")
    return b


def score(key: str, b: dict[str, float], critical: bool) -> float:
    issue = key.split("|", 1)[0]
    bh = b[issue]
    p_sat = bh * P_SAT_PRESENT[critical] + (1 - bh) * P_SAT_ABSENT
    post_sat = update(bh, critical, True)
    post_con = update(bh, critical, False)
    ig = h2(bh) - (p_sat * h2(post_sat) + (1 - p_sat) * h2(post_con))
    w = 2.0 if critical else 1.0
    return w * (ig + bh * h2(p_sat))


ORDER_EPS = 0.001


def rank(candidates: list[str], b: dict[str, float], criticality: dict[str, bool],
         order: dict[str, int] | None = None) -> list[tuple[str, float]]:
    order = order or {}
    scored = [(k, round(score(k, b, criticality[k]), 6)) for k in candidates]
    scored.sort(key=lambda x: (-(x[1] - ORDER_EPS * order.get(x[0], 0)), x[0]))
    return scored


def acceptable(ranked: list[tuple[str, float]]) -> list[str]:
    if not ranked:
        return []
    best = ranked[0][1]
    return [k for k, s in ranked if s >= ACCEPT_RATIO * best]


def completeness(known: dict[str, str], gold_critical: list[str]) -> float:
    if not gold_critical:
        return 1.0
    return sum(known.get(k) in ("satisfied", "contradicted") for k in gold_critical) / len(gold_critical)
