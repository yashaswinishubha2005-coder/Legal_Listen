"""System-level evaluation of LegalListen on LexVaani-IN.

    python -m eval.legallisten_eval [--limit N]     -> reports/legallisten_eval.md (+ .json)

A. Interactive simulation (LexVaani-IN test split, every language variant). The simulated client opens with
   the test narrative and answers each question from the hidden scenario spec (the same truth the dataset's
   dialogues are generated from). Measures issue identification, fact finding, questions asked, triage,
   law-regime routing, provision retrieval and Case Graph validity — for the adaptive policy and for a
   fixed-questionnaire baseline (every element of every hypothesis in library order, no early stopping).
B. Free-form check: 36 hand-written narratives (eval/legallisten_freeform.jsonl, en / kn / hi / romanised),
   written by the developers, not template-generated and not native-reviewed — a small, honest probe of how
   the offline NLU handles natural language. Only the opening turn is evaluated.
Runs fully offline (no LLM). With an LLM configured, run the web app instead; LLM mode is not evaluated here.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from legallisten import policy  # noqa: E402
from legallisten.engine import Engine  # noqa: E402
from legallisten.knowledge import kb  # noqa: E402

REL = ROOT / "release" / "lexvaani-in-v0.1.0"


def _read(p):
    with open(p, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def truth_answer(spec: dict, pending) -> str:
    k = kb()
    ids = [c.id for c in pending.chips]
    pick = lambda c: c if c in ids else ids[-1]  # noqa: E731
    if pending.kind == "element":
        issue, el = pending.key.split("|")
        facts = [f for f in spec["facts"] if f["issue_id"] == issue and f["element_id"] == el]
        truth = next((e for e in spec["elements"] if e["issue_id"] == issue and e["element_id"] == el), None)
        if facts:
            f = facts[-1]
            if f["reveal"] == "never":
                return "dk"
            return "el:sat" if f["polarity"] == "satisfied" else "el:con"
        if truth:
            return {"satisfied": "el:sat", "contradicted": "el:con"}.get(truth["world_value"], "dk")
        return "el:con"                                  # not the client's situation
    if pending.kind == "evidence":
        _, evid = pending.key.split("|")
        ev = next((e for e in spec["evidence"] if e["def_id"] == evid), None)
        if ev is None:
            return "dk"
        return {"held": "ev:held", "missing": "ev:missing"}.get(ev["availability"], "dk")
    if pending.kind == "date":
        return {"old": "date:old", "new": "date:new"}.get(spec.get("law_regime"), "dk")
    if pending.kind == "personal_law":
        pl = spec.get("routing", {}).get("personal_law")
        return pick(f"pl:{pl}") if pl else "skip"
    if pending.kind == "safety":
        return "safe:yes"
    if pending.kind == "contradiction":
        return "c:unsure"
    return ids[0]


def fixed_questionnaire(state):
    """Baseline policy: ask every element of every hypothesis in library order; no information-based stopping."""
    k = kb()
    cands = [c for c in policy.candidates(state) if c.kind in ("contradiction", "safety")]
    if cands:
        return cands[0]
    hyps = sorted(state.issue_prior, key=lambda i: -state.issue_prior[i])
    for issue in hyps:
        for el in k.elements_of(issue):
            es = state.elements.get(el.key)
            if el.key not in state.asked and not (es and es.value is not None):
                return policy.Candidate("element", el.key, 1.0, "critical")
    rest = [c for c in policy.candidates(state) if c.kind in ("date", "personal_law", "evidence")]
    return rest[0] if rest and state.questions_asked < 40 else None


def simulate(engine: Engine, spec: dict, narrative: dict, max_turns: int = 40) -> dict:
    st = engine.start(narrative["lang_variant"][:2] if narrative["lang_variant"][:2] in ("en", "kn", "hi") else "en",
                      conversation_date=spec["conversation_date"])
    engine.handle(st, narrative["text"])
    turns = 0
    while st.pending is not None and turns < max_turns:
        engine.handle(st, "", chip=truth_answer(spec, st.pending))
        turns += 1
    c = engine.consultation(st, explain_with_llm=False)
    g = engine.graph(st)
    return {"state": st, "consult": c, "graph": g, "turns": turns}


def prf(pred: set, gold: set) -> tuple[float, float, float]:
    tp = len(pred & gold)
    p = tp / len(pred) if pred else (1.0 if not gold else 0.0)
    r = tp / len(gold) if gold else 1.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f


def evaluate_interactive(limit: int | None, fixed: bool) -> dict:
    specs = {s["spec_id"]: s for s in _read(REL / "specs" / "test.jsonl")}
    narr = _read(REL / "narratives" / "test.jsonl")
    if limit:
        narr = narr[:limit]
    engine = Engine(None)
    orig = policy.next_question
    if fixed:
        policy.next_question = fixed_questionnaire
        import legallisten.engine as E
        E.policy.next_question = fixed_questionnaire
    agg = defaultdict(list)
    by_variant = defaultdict(lambda: defaultdict(list))
    t0 = time.time()
    try:
        for n in narr:
            spec = specs[n["spec_id"]]
            r = simulate(engine, spec, n)
            st, c = r["state"], r["consult"]
            gold = set(spec["issues"])
            pred = set(policy.identified(st))
            if gold & {"x.out_of_scope", "x.non_legal"}:
                pred = pred or ({"x.out_of_scope"} if st.out_of_scope >= 0.5 else {"x.non_legal"} if st.non_legal >= 0.5 else set())
                gold = gold & {"x.out_of_scope", "x.non_legal"}
            tp, fp, fn = len(pred & gold), len(pred - gold), len(gold - pred)
            agg["tp"].append(tp); agg["fp"].append(fp); agg["fn"].append(fn)
            agg["questions"].append(st.questions_asked)
            crit = [e for e in spec["elements"] if e["critical"] and e["world_value"] in ("satisfied", "contradicted")]
            for e in crit:
                es = st.elements.get(f"{e['issue_id']}|{e['element_id']}")
                revealed = any(f["issue_id"] == e["issue_id"] and f["element_id"] == e["element_id"] and f["reveal"] != "never"
                               for f in spec["facts"])
                if revealed:
                    agg["crit_found"].append(bool(es and es.value == e["world_value"]))
            agg["triage_acc"].append(c["triage"] == spec["triage"])
            if spec["triage"] == "urgent":
                agg["urgent_recall"].append(c["triage"] == "urgent")
            if spec.get("law_regime"):
                agg["regime_acc"].append(st.law_regime == spec["law_regime"])
            if spec.get("gold_provisions"):
                p, rr, f = prf({x["provision_id"] for x in c["provisions"]}, set(spec["gold_provisions"]))
                agg["prov_p"].append(p); agg["prov_r"].append(rr); agg["prov_f"].append(f)
            agg["graph_valid"].append(not r["graph"]["errors"])
            v = n["lang_variant"]
            by_variant[v]["issue_exact"].append(pred == gold)
            by_variant[v]["questions"].append(st.questions_asked)
    finally:
        policy.next_question = orig
        import legallisten.engine as E
        E.policy.next_question = orig
    tp, fp, fn = sum(agg["tp"]), sum(agg["fp"]), sum(agg["fn"])
    prec = tp / (tp + fp) if tp + fp else 0
    rec = tp / (tp + fn) if tp + fn else 0
    mean = lambda xs: round(statistics.mean(xs), 3) if xs else None  # noqa: E731
    return {
        "n": len(narr), "seconds": round(time.time() - t0, 1),
        "issue_micro_f1": round(2 * prec * rec / (prec + rec), 3) if prec + rec else 0.0,
        "issue_precision": round(prec, 3), "issue_recall": round(rec, 3),
        "critical_fact_recall": mean(agg["crit_found"]), "questions_mean": mean(agg["questions"]),
        "questions_median": statistics.median(agg["questions"]) if agg["questions"] else None,
        "triage_accuracy": mean(agg["triage_acc"]), "urgent_recall": mean(agg["urgent_recall"]),
        "regime_accuracy": mean(agg["regime_acc"]), "provision_precision": mean(agg["prov_p"]),
        "provision_recall": mean(agg["prov_r"]), "provision_f1": mean(agg["prov_f"]),
        "graph_valid_rate": mean(agg["graph_valid"]),
        "by_variant": {v: {"issue_exact": mean(d["issue_exact"]), "questions_mean": mean(d["questions"])}
                       for v, d in sorted(by_variant.items())},
    }


def evaluate_freeform() -> dict:
    rows = _read(ROOT / "eval" / "legallisten_freeform.jsonl")
    engine = Engine(None)
    out = {"n": len(rows), "items": []}
    hits, top1, urg_tp, urg_fn, urg_fp, exact = 0, 0, 0, 0, 0, 0
    for r in rows:
        st = engine.start(r["lang"], conversation_date="2026-10-25")
        engine.handle(st, r["text"])
        ranked = [i for i, _ in sorted(st.issue_prior.items(), key=lambda x: -x[1])]
        gold = set(r["issues"])
        if gold & {"x.out_of_scope", "x.non_legal"}:
            pred_label = "x.out_of_scope" if st.out_of_scope >= 0.5 else "x.non_legal" if st.non_legal >= 0.5 else (ranked[0] if ranked else "none")
            ok_any = pred_label in gold or (not ranked and bool(gold & {"x.out_of_scope", "x.non_legal"}))
            ok_top = ok_any
        else:
            ok_any = bool(set(ranked[:3]) & gold)
            ok_top = bool(ranked[:1]) and ranked[0] in gold
        hits += ok_any
        top1 += ok_top
        flagged = any(f in st.risks for f in ("imminent_violence", "ongoing_abuse", "threat_to_life", "self_harm",
                                              "image_circulation", "golden_hour_fraud", "imminent_property_transfer",
                                              "eviction_imminent", "child_removal_imminent", "limitation_near_expiry"))
        urgent_pred = flagged or "cyb.morphed_intimate_image" in ranked[:1]
        if r["urgent"]:
            urg_tp += urgent_pred; urg_fn += not urgent_pred
        else:
            urg_fp += urgent_pred
        out["items"].append({"id": r["id"], "lang": r["lang"], "gold": sorted(gold), "hypotheses": ranked[:3],
                             "hit@3": ok_any, "top1": ok_top, "risks": sorted(st.risks)})
    out["hit_at_3"] = round(hits / len(rows), 3)
    out["top1"] = round(top1 / len(rows), 3)
    out["urgent_recall"] = round(urg_tp / max(1, urg_tp + urg_fn), 3)
    out["urgent_false_alarms"] = urg_fp
    by_lang = defaultdict(list)
    for it in out["items"]:
        by_lang[it["lang"]].append(it["hit@3"])
    out["hit_at_3_by_lang"] = {l: round(sum(v) / len(v), 3) for l, v in by_lang.items()}
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()
    adaptive = evaluate_interactive(args.limit, fixed=False)
    fixed = evaluate_interactive(args.limit, fixed=True)
    free = evaluate_freeform()
    res = {"adaptive": adaptive, "fixed_questionnaire": fixed, "freeform": free}
    (ROOT / "reports" / "legallisten_eval.json").write_text(json.dumps(res, indent=1, ensure_ascii=False), encoding="utf-8")
    keys = [("issue_micro_f1", "Issue identification micro-F1 (T1, end of consultation)"),
            ("critical_fact_recall", "Critical facts correctly established (revealable ones)"),
            ("questions_mean", "Questions asked (mean)"), ("questions_median", "Questions asked (median)"),
            ("triage_accuracy", "Triage accuracy (T13)"), ("urgent_recall", "Urgent-case recall (T13)"),
            ("regime_accuracy", "IPC/BNS regime routed correctly"), ("provision_precision", "Provision precision (T10)"),
            ("provision_recall", "Provision recall (T10)"), ("provision_f1", "Provision F1 (T10)"),
            ("graph_valid_rate", "Case Graphs passing structural validation")]
    L = ["# LegalListen system evaluation (offline mode, no LLM)", "",
         f"Interactive simulation on the LexVaani-IN **test** split: {adaptive['n']} consultations "
         "(every test narrative, all six language variants). The simulated client answers from the hidden scenario spec.", "",
         "| Metric | Adaptive policy (LegalListen) | Fixed questionnaire baseline |", "|---|---|---|"]
    L += [f"| {name} | {adaptive[k]} | {fixed[k]} |" for k, name in keys]
    L += ["", "Per language variant (adaptive): exact issue-set match / mean questions", "",
          "| variant | exact issue set | questions |", "|---|---|---|"]
    L += [f"| {v} | {d['issue_exact']} | {d['questions_mean']} |" for v, d in adaptive["by_variant"].items()]
    L += ["", "## Free-form narratives (hand-written, opening turn only)", "",
          f"{free['n']} short narratives written by the developers in English, Kannada, Hindi and romanised Kanglish / "
          "Hinglish (eval/legallisten_freeform.jsonl). Not template-generated, not native-reviewed, and **used during development** to tune the rule cues (co-occurrence and risk keywords) — so these scores are optimistic and are not a blind test.", "",
          f"- Gold issue among the top-3 hypotheses after the first message: **{free['hit_at_3']}** "
          f"(by language: {free['hit_at_3_by_lang']})",
          f"- Top-1 hypothesis correct: **{free['top1']}**",
          f"- Urgent cases flagged from the first message: **{free['urgent_recall']}** recall, "
          f"{free['urgent_false_alarms']} false alarms", "",
          "| id | lang | gold | top-3 hypotheses | hit@3 | risks |", "|---|---|---|---|---|---|"]
    L += [f"| {i['id']} | {i['lang']} | {', '.join(i['gold'])} | {', '.join(i['hypotheses'])} | {'✓' if i['hit@3'] else '✗'} | {', '.join(i['risks'])} |"
          for i in free["items"]]
    L += ["", "## How to read these numbers", "",
          "- The interactive numbers use template-generated narratives and a simulated client that always answers "
          "truthfully from the scenario, so they are an **upper bound** for real conversations.",
          "- The free-form probe is small (36 items), written by the developers and used while tuning the rule cues; "
          "a blind, native-speaker-written test set is still needed. With Gemini enabled, extraction is done by the LLM (not measured here).",
          "- Provision metrics compare against the dataset's gold provision ids, which are themselves TO_VERIFY.", ""]
    (ROOT / "reports" / "legallisten_eval.md").write_text("\n".join(L), encoding="utf-8")
    print(json.dumps({k: v for k, v in adaptive.items() if k != "by_variant"}, indent=1))
    print(json.dumps({k: v for k, v in fixed.items() if k != "by_variant"}, indent=1))
    print({k: free[k] for k in ("hit_at_3", "top1", "urgent_recall", "urgent_false_alarms", "hit_at_3_by_lang")})


if __name__ == "__main__":
    main()
