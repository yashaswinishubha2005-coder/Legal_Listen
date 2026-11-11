"""T9 Next-question selection.

Offline (default): pred {"dialogue_id", "system_turn", "ranking": [question ids]} for every
decision point; Hit@1 = top-ranked id in the acceptable set, MRR = reciprocal rank of the
first acceptable id.

Interactive (--policy module:function): the policy is run against the spec-grounded user
simulator for N turns and "case completeness after N turns" (fraction of critical gold
elements whose value is known) is reported. policy(state: dict, candidates: list[dict]) -> question_id.
"""
import argparse
import importlib
import json
import random

from eval.common import DEFAULT_GOLD, RELEASE, read_jsonl, r4
from eval.metrics import mrr


def score(gold, pred):
    P = {(p["dialogue_id"], p["system_turn"]): p["ranking"] for p in pred}
    acc, ranks, hits, strict = [], [], 0, 0
    for d in gold:
        for dp in d["decision_points"]:
            r = P.get((d["dialogue_id"], dp["system_turn"]), [])
            acc.append(set(dp["acceptable_set"]))
            ranks.append(r)
            hits += bool(r) and r[0] in dp["acceptable_set"]
            strict += bool(r) and r[0] == dp["gold_best"]
    return r4({"n_decisions": len(acc), "hit@1": hits / max(1, len(acc)),
               "hit@1_strict": strict / max(1, len(acc)), "mrr": mrr(acc, ranks)})


# ----------------------------------------------------------- interactive mode
def simulate_policy(spec: dict, lib: dict, policy, n_turns: int) -> float:
    from lexvaani.dialogue import oracle
    issues = spec["issues"]
    hyp = [i for i in issues if i in lib]
    for i in list(hyp):
        hyp += [c for c in lib[i]["confusable_with"][:1] if c in lib and c not in hyp]
    crit = {f"{i}|{e['element_id']}": e["critical"] for i in hyp for e in lib[i]["elements"]}
    order = {f"{i}|{e['element_id']}": e["order"] for i in hyp for e in lib[i]["elements"]}
    facts = {(f["issue_id"], f["element_id"]): f for f in spec["facts"]}
    known = {}
    for (i, el), f in facts.items():
        if f["reveal"] == "narrative":
            known[f"{i}|{el}"] = "unknown" if f["self_contradicted"] else f["polarity"]
    known = {k: v for k, v in known.items() if v != "unknown"}
    gold_crit = [f"{e['issue_id']}|{e['element_id']}" for e in spec["elements"] if e["critical"]]
    asked = []
    for _ in range(n_turns):
        cands = [k for k in crit if k not in known and k not in asked]
        if not cands:
            break
        b = oracle.beliefs(hyp, known, crit)
        state = {"known": dict(known), "asked": list(asked), "belief": b, "order": order}
        q = policy(state, [{"question_id": k, "critical": crit[k]} for k in cands])
        asked.append(q)
        i, el = q.split("|", 1)
        f = facts.get((i, el))
        if f is None:
            known[q] = "contradicted"
        elif f["reveal"] != "never":
            known[q] = f["polarity"]
    return oracle.completeness(known, gold_crit)


def oracle_policy(state, cands):
    from lexvaani.dialogue import oracle
    crit = {c["question_id"]: c["critical"] for c in cands}
    return oracle.rank(list(crit), state["belief"], crit, state.get("order"))[0][0]


def random_policy(state, cands, _r=random.Random(0)):
    return _r.choice(cands)["question_id"]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pred")
    ap.add_argument("--gold", default=str(DEFAULT_GOLD["dialogues"]))
    ap.add_argument("--policy", help="module:function, or 'oracle' / 'random'")
    ap.add_argument("--turns", type=int, default=3)
    ap.add_argument("--specs", default=str(RELEASE / "specs" / "test.jsonl"))
    a = ap.parse_args()
    if a.policy:
        if a.policy in ("oracle", "random"):
            pol = oracle_policy if a.policy == "oracle" else random_policy
        else:
            mod, fn = a.policy.split(":")
            pol = getattr(importlib.import_module(mod), fn)
        lib = {r["issue_id"]: r for r in read_jsonl(RELEASE / "resources" / "issue_library.jsonl")}
        specs = [s for s in read_jsonl(a.specs) if s["variation"] not in ("out_of_scope", "non_legal")]
        vals = [simulate_policy(s, lib, pol, a.turns) for s in specs]
        print(json.dumps({"policy": a.policy, "turns": a.turns, "n_specs": len(vals),
                          "case_completeness": round(sum(vals) / len(vals), 4)}, indent=2))
    else:
        print(json.dumps(score(read_jsonl(a.gold), read_jsonl(a.pred)), indent=2))
