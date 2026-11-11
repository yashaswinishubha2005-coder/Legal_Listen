"""Adaptive cross-questioning: choose the most useful next question.

Priorities (docs/legallisten.md §4):
  1. unresolved contradictions             (an earlier statement needs clarification)
  2. safety check after an urgent risk     (safety first)
  3. information value of each question:
       element questions  — LexVaani-IN Bayesian oracle score (expected information about which
                            issue applies + uncertainty about the element), x2 for critical elements
       incident date      — decides old vs new criminal law (changes the applicable provisions)
       personal law       — decides the family / succession statute
       evidence           — can turn a reported claim into an evidence-supported one
  4. stop when no question is worth asking (score < MIN_SCORE) or the question budget is spent.
"""

from __future__ import annotations

from dataclasses import dataclass

from lexvaani.dialogue.oracle import score as oracle_score
from lexvaani.dialogue.oracle import update

from .knowledge import kb
from .state import CaseState

MIN_SCORE = 0.25
MAX_QUESTIONS = 16
HYP_MIN = 0.2
IDENTIFIED = 0.5
DATE_SCORE = 1.05
PL_SCORE = 1.0
EVIDENCE_SCORE = 0.6
SAFETY_FLAGS = {"imminent_violence", "ongoing_abuse", "threat_to_life", "self_harm"}


@dataclass
class Candidate:
    kind: str          # contradiction | safety | element | date | personal_law | evidence
    key: str | None
    score: float
    reason: str        # critical | distinguish | regime | personal_law | evidence | contradiction | safety
    other: str | None = None


def recompute_beliefs(state: CaseState) -> None:
    k = kb()
    beliefs = {}
    for issue, prior in state.issue_prior.items():
        b = min(0.95, max(0.05, prior))
        for el in k.elements_of(issue):
            es = state.elements.get(el.key)
            if es and es.value in ("satisfied", "contradicted") and es.status != "conflicting":
                b = update(b, el.critical, es.value == "satisfied")
        beliefs[issue] = round(b, 4)
    state.beliefs = beliefs


def identified(state: CaseState) -> list[str]:
    return [i for i, b in sorted(state.beliefs.items(), key=lambda x: -x[1]) if b >= IDENTIFIED]


def hypotheses(state: CaseState, n: int = 4) -> list[str]:
    return [i for i, b in sorted(state.beliefs.items(), key=lambda x: -x[1]) if b >= HYP_MIN][:n]


def _routing(issue: str) -> set[str]:
    return {r.name for r in kb().issues[issue].routing_variables}


def gate_element(issue: str) -> str | None:
    """The element describing the event that defines the issue (the regime-determining incident)."""
    k = kb()
    el = next((e for e in k.elements_of(issue) if e.date_slot_required), None)
    return el.key if el else None


def candidates(state: CaseState) -> list[Candidate]:
    k = kb()
    out: list[Candidate] = []
    for c in state.contradictions:
        if not c.resolved:
            out.append(Candidate("contradiction", c.id, 100.0, "contradiction"))
    if any(f in SAFETY_FLAGS for f in state.risks) and not state.safety_checked:
        out.append(Candidate("safety", None, 90.0, "safety"))
    hyps = hypotheses(state)
    ident = identified(state)
    crit = {e.key: e.critical for e in k.elements.values()}
    for issue in hyps:
        gate = gate_element(issue)
        confirmed = any(state.elements.get(e.key) and state.elements[e.key].value == "satisfied" for e in k.elements_of(issue))
        for el in k.elements_of(issue):
            es = state.elements.get(el.key)
            if el.key in state.asked or (es and es.value is not None):
                continue
            # an issue nobody has confirmed yet is opened with its defining event ("has it been sold, or only
            # threatened?") before any detail question about it
            if not confirmed and gate and el.key != gate and gate not in state.asked and \
                    not (state.elements.get(gate) and state.elements[gate].value is not None):
                continue
            s = oracle_score(el.key, state.beliefs, crit[el.key]) - 0.001 * el.order
            if not confirmed and el.key == gate:
                s += 0.3
            other = next((h for h in hyps if h != issue), None)
            reason = "critical" if el.critical else "distinguish"
            if other and state.beliefs[issue] < 0.8:
                reason = "distinguish"
            out.append(Candidate("element", el.key, s, reason, other))
    if ident and state.law_regime is None and "date" not in state.asked and any("law_regime" in _routing(i) for i in ident):
        out.append(Candidate("date", None, DATE_SCORE, "regime"))
    if ident and state.personal_law is None and "personal_law" not in state.asked and \
            any("personal_law" in _routing(i) for i in ident):
        out.append(Candidate("personal_law", None, PL_SCORE, "personal_law"))
    for issue in ident:
        for ev in (e for e in k.evidence.values() if e.issue == issue):
            st = state.evidence.get(ev.key)
            if ev.key in state.asked or (st and st.availability != "unknown"):
                continue
            sat = [s for s in ev.supports if state.elements.get(s) and state.elements[s].value == "satisfied"]
            if sat:
                bonus = 0.2 if any(crit[s] for s in sat) else 0.0
                out.append(Candidate("evidence", ev.key, EVIDENCE_SCORE + bonus, "evidence"))
    out.sort(key=lambda c: -c.score)
    return out


def next_question(state: CaseState) -> Candidate | None:
    cands = candidates(state)
    if not cands:
        return None
    best = cands[0]
    if best.kind in ("contradiction", "safety"):
        return best
    if state.questions_asked >= MAX_QUESTIONS or best.score < MIN_SCORE:
        return None
    return best
