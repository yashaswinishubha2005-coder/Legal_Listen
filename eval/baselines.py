"""Reference baselines + gold-as-prediction sanity checks.

    python -m eval.baselines   -> reports/baselines.md, eval/preds/*.jsonl

Baselines are deliberately simple (keyword / majority / prior); they exist to show the
evaluators work end-to-end and to give a floor that real models must beat.
"""

from __future__ import annotations

import json
import random
import re
from pathlib import Path

from eval import (t01_issues, t02_entities, t03_events, t04_temporal, t05_coref, t06_epistemic, t07_elements,
                  t08_graph, t09_next_question, t10_retrieval, t11_explanation, t12_clarification, t13_triage)
from eval.common import DEFAULT_GOLD, RELEASE, ROOT, read_jsonl

KEYWORDS = {
    "crim.hurt_assault": ["hit", "stick", "ಹೊಡೆ", "hode", "मारा", "maara", "injur", "ಗಾಯ", "chot", "चोट"],
    "crim.criminal_intimidation": ["threat", "ಬೆದರಿ", "bedari", "धमकी", "dhamki"],
    "crim.theft": ["stole", "ಕದ್ದ", "kadd", "चुरा", "chura", "चोरी", "chori", "steal"],
    "crim.cheating": ["job", "ಕೆಲಸ", "kelsa", "नौकरी", "naukri", "promise", "promised"],
    "crim.police_refusal_fir": ["refused to write", "police station", "ಠಾಣೆ", "पुलिस स्टेशन", "police station"],
    "fam.divorce": ["divorce", "ಡಿವೋರ್ಸ್", "तलाक", "marriage", "ಮದುವೆ"],
    "fam.maintenance": ["expenses", "ಖರ್ಚ", "kharch", "खर्च", "income", "earn"],
    "fam.custody": ["son", "daughter", "ಮಗ", "बेटा", "बेटी", "beta", "beti", "maga"],
    "fam.domestic_violence": ["beat", "pulled my hair", "ಕೂದಲು", "बाल", "baal", "mother-in-law", "ಅತ್ತೆ", "सास", "saas"],
    "fam.dowry_harassment": ["dowry", "ವರದಕ್ಷಿಣೆ", "varadakshine", "दहेज", "dahej"],
    "prop.inheritance_partition": ["share", "ಪಾಲು", "paalu", "हिस्सा", "hissa", "heir", "ancestral"],
    "prop.encroachment": ["wall", "ಗೋಡೆ", "gode", "दीवार", "deewar"],
    "prop.coheir_sale_without_consent": ["sold", "ಮಾರಿ", "maari", "बेच", "bech", "sale"],
    "prop.boundary_dispute": ["boundary", "ಗಡಿ", "gadi", "सीमा", "survey"],
    "prop.forged_documents": ["fake will", "ವಿಲ್", "will", "वसीयत", "forged", "ನಕಲಿ"],
    "cyb.upi_payment_fraud": ["upi", "ಯುಪಿಐ", "यूपीआई", "pin", "ಪಿನ್", "पिन"],
    "cyb.phishing_account_takeover": ["kyc", "ಕೆವೈಸಿ", "केवाईसी", "link", "otp"],
    "cyb.impersonation": ["fake social media profile", "fake profile", "ಪ್ರೊಫೈಲ್", "प्रोफ़ाइल", "profile"],
    "cyb.cyberstalking": ["every day", "ಪ್ರತಿ ದಿನ", "हर दिन", "har din", "location"],
    "cyb.morphed_intimate_image": ["morph", "ಮಾರ್ಫ್", "मॉर्फ़", "obscene", "ಅಶ್ಲೀಲ", "अश्लील"],
    "con.defective_product": ["warranty", "ವಾರಂಟಿ", "वारंटी", "showroom", "ಶೋರೂಮ್", "शोरूम"],
    "con.deficiency_in_service": ["internet", "ಇಂಟರ್ನೆಟ್", "इंटरनेट", "connection"],
    "fin.unauthorized_bank_txn": ["card payment", "ಕಾರ್ಡ್", "कार्ड", "statement"],
    "con.refund_refusal": ["refund", "ರಿಫಂಡ್", "रिफ़ंड", "return", "ವಾಪಸ್"],
    "fin.loan_recovery_harassment": ["loan app", "ಲೋನ್", "लोन", "recovery"],
}
URGENT_WORDS = ["tonight", "ಇವತ್ತು ರಾತ್ರಿ", "ivattu raatri", "आज रात", "aaj raat", "hour ago", "ಗಂಟೆ ಹಿಂದೆ",
                "घंटे पहले", "ghante pehle", "right now", "ಈಗಲೂ", "अभी भी", "abhi bhi", "tomorrow", "ನಾಳೆ", "naale",
                "living", "ಬದುಕೋದೇ", "जीने", "jeene", "ending my life", "ಜೀವ", "जान देने", "jaan dene",
                "two years", "ಎರಡು ವರ್ಷ", "दो साल", "do saal", "electric shock", "ಕರೆಂಟ್", "करंट", "burnt", "ಸುಡ್ತೀವಿ", "जला"]
NEG_WORDS = re.compile(r"\b(not|no|never|nothing|nobody|don't|nahi|nahin|na|illa|alla)\b|नहीं|ಇಲ್ಲ|ಅಲ್ಲ|ಲಿಲ್ಲ|ಿಲ್ಲ")
MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"


def kw_issues(text: str) -> list[str]:
    low = text.lower()
    scores = {i: sum(low.count(k.lower()) for k in kws) for i, kws in KEYWORDS.items()}
    ranked = [i for i, s in sorted(scores.items(), key=lambda x: -x[1]) if s > 0]
    return ranked


def run() -> str:
    narr = read_jsonl(DEFAULT_GOLD["narratives"])
    dlg = read_jsonl(DEFAULT_GOLD["dialogues"])
    exp = read_jsonl(DEFAULT_GOLD["explanations"])
    lib = {r["issue_id"]: r for r in read_jsonl(RELEASE / "resources" / "issue_library.jsonl")}
    preds = ROOT / "eval" / "preds"
    preds.mkdir(exist_ok=True)
    rows = []

    def add(task, name, module, gold, pred, metric_keys):
        res = module.score(gold, pred)
        (preds / f"{task}_{name}.jsonl").write_text("\n".join(json.dumps(p, ensure_ascii=False) for p in pred) + "\n",
                                                   encoding="utf-8")
        rows.append((task, name, {k: _get(res, k) for k in metric_keys}))

    gold_pred = lambda f: [f(g) for g in narr]  # noqa: E731
    # T1
    t1 = []
    for g in narr:
        r = kw_issues(g["text"])
        t1.append({"sample_id": g["sample_id"], "issues": r[:1] or ["x.non_legal"], "ranked_issues": r})
    add("T1", "keyword", t01_issues, narr, t1, ["micro_f1", "macro_f1", "top3_accuracy"])
    add("T1", "gold", t01_issues, narr, gold_pred(lambda g: {"sample_id": g["sample_id"], "issues": g["annotations"]["issues"],
        "domains": g["annotations"]["domains"]}), ["micro_f1", "macro_f1"])
    # T2
    t2 = []
    for g in narr:
        ents = [{"start": m.start(), "end": m.end(), "type": "TIME"} for m in re.finditer(rf"({MONTHS}) \d{{1,2}}, \d{{4}}|\d{{1,2}} ({MONTHS})( \d{{4}})?", g["text"])]
        ents += [{"start": m.start(), "end": m.end(), "type": "MONEY"} for m in re.finditer(r"₹[\d,]+|[\d,]{4,} (rupees|ರೂಪಾಯಿ|रुपये|rupaye)", g["text"])]
        t2.append({"sample_id": g["sample_id"], "entities": ents})
    add("T2", "regex(TIME,MONEY)", t02_entities, narr, t2, ["strict.f1", "partial.f1"])
    add("T2", "gold", t02_entities, narr, gold_pred(lambda g: {"sample_id": g["sample_id"], "entities": [
        {"start": m["span"]["start"], "end": m["span"]["end"], "type": m["type"]} for m in g["annotations"]["entities"]]}),
        ["strict.f1"])
    # T3 / T4 / T5 / T8 gold sanity + trivial baselines
    add("T3", "gold", t03_events, narr, gold_pred(lambda g: {"sample_id": g["sample_id"], "events": [
        {"trigger": [e["trigger"]["start"], e["trigger"]["end"]], "event_type": e["event_type"], "arguments": [
            {"role": a, "start": s, "end": t} for a, s, t in t03_events._gold_args(g)[i]["args"]]}
        for i, e in enumerate(g["annotations"]["events"])]}), ["trigger.f1", "argument.f1"])
    add("T4", "gold", t04_temporal, narr, gold_pred(lambda g: {"sample_id": g["sample_id"], "timexes": [
        {"start": t["span"]["start"], "end": t["span"]["end"], "value": t["value"]} for t in g["annotations"]["timexes"] if t.get("span")],
        "tlinks": [{"source": _trig(g, l["source"]), "target": _trig(g, l["target"]), "relation": l["relation"]}
                   for l in g["annotations"]["tlinks"]]}), ["timex_value_accuracy", "tlink.f1"])
    add("T5", "singletons(gold mentions)", t05_coref, narr, gold_pred(lambda g: {"sample_id": g["sample_id"], "clusters": [
        [[m["span"]["start"], m["span"]["end"]]] for m in g["annotations"]["entities"] if m["type"] in ("PERSON", "ORGANIZATION")]}),
        ["conll_f1"])
    add("T5", "gold", t05_coref, narr, gold_pred(lambda g: {"sample_id": g["sample_id"], "clusters": [
        [[m["span"]["start"], m["span"]["end"]] for m in g["annotations"]["entities"] if m["mention_id"] in c["mention_ids"]]
        for c in g["annotations"]["coref"]]}), ["conll_f1"])
    # T6
    t6 = []
    for g in narr:
        sents = [(m.start(), m.end()) for m in re.finditer(r"[^.?!।]+[.?!।]?", g["text"]) if m.group().strip()]
        t6.append({"sample_id": g["sample_id"], "facts": [{"start": s, "end": e, "status": "reported"} for s, e in sents],
                   "cues": [{"start": m.start(), "end": m.end(), "type": "neg"} for m in NEG_WORDS.finditer(g["text"])]})
    add("T6", "all-reported+neg-lexicon", t06_epistemic, narr, t6, ["status_macro_f1", "cue.f1"])
    # T7
    add("T7", "all-unknown", t07_elements, narr, gold_pred(lambda g: {"sample_id": g["sample_id"], "elements": [
        {**{k: e[k] for k in ("issue_id", "element_id")}, "value": "unknown"} for e in g["annotations"]["elements"]]}),
        ["macro_f1", "critical_macro_f1"])
    add("T7", "all-satisfied", t07_elements, narr, gold_pred(lambda g: {"sample_id": g["sample_id"], "elements": [
        {**{k: e[k] for k in ("issue_id", "element_id")}, "value": "satisfied"} for e in g["annotations"]["elements"]]}),
        ["macro_f1", "critical_macro_f1"])
    add("T8", "gold", t08_graph, narr, gold_pred(lambda g: {"sample_id": g["sample_id"], "graph": g["annotations"]["case_graph"]}),
        ["node.f1", "edge.f1", "normalised_graph_edit_distance"])
    # T9
    rnd = random.Random(0)
    t9r = [{"dialogue_id": d["dialogue_id"], "system_turn": dp["system_turn"],
            "ranking": rnd.sample([c["question_id"] for c in dp["candidates"]], len(dp["candidates"]))}
           for d in dlg for dp in d["decision_points"]]
    add("T9", "random", t09_next_question, dlg, t9r, ["hit@1", "hit@1_strict", "mrr"])
    t9c = [{"dialogue_id": d["dialogue_id"], "system_turn": dp["system_turn"],
            "ranking": sorted([c["question_id"] for c in dp["candidates"]], key=lambda q: (not next(c for c in dp["candidates"] if c["question_id"] == q)["critical"], q))}
           for d in dlg for dp in d["decision_points"]]
    add("T9", "critical-first", t09_next_question, dlg, t9c, ["hit@1", "hit@1_strict", "mrr"])
    # T10
    t10 = []
    for p1 in t1:
        ids = []
        for i in p1["ranked_issues"][:2]:
            ids += [c["provision_id"] for c in lib[i]["candidate_provisions"]]
        t10.append({"sample_id": p1["sample_id"], "provisions": list(dict.fromkeys(ids)) + ["BNS:999"]})
    add("T10", "keyword-issue->all-candidates (+1 fake id)", t10_retrieval, narr, t10,
        ["recall@5", "ndcg@10", "citation_validity"])
    # T11
    t11 = [{"explanation_id": e["explanation_id"], "text": e["what_it_means"]} for e in exp]
    add("T11", "summary-only", t11_explanation, exp, t11, ["en.chrf", "kn.chrf", "hi.chrf"])
    # T12
    t12 = [{"dialogue_id": d["dialogue_id"], "turn": t["index"], "label": "new_fact"} for d in dlg for t in d["turns"] if t.get("clarification")]
    add("T12", "majority(new_fact)", t12_clarification, dlg, t12, ["macro_f1", "accuracy"])
    t12k = []
    for d in dlg:
        for t in d["turns"]:
            if t.get("clarification"):
                low = t["text"].lower()
                lab = "reexplain_request" if re.search(r"understand|artha|samajh|समझ|ಅರ್ಥ|mean|matlab|ಅಂದ್ರೆ ಏನು", low) else \
                      "correction" if re.search(r"wrong|correct|tappaagi|ತಪ್ಪಾಗಿ|galat|गलत|ruko|रुकिए|illa illa", low) else "new_fact"
                t12k.append({"dialogue_id": d["dialogue_id"], "turn": t["index"], "label": lab})
    add("T12", "keyword", t12_clarification, dlg, t12k, ["macro_f1", "accuracy"])
    # T13
    t13 = []
    for g, p1 in zip(narr, t1):
        low = g["text"].lower()
        urg = any(w.lower() in low for w in URGENT_WORDS)
        top = p1["ranked_issues"][0] if p1["ranked_issues"] else None
        t13.append({"sample_id": g["sample_id"], "triage": "urgent" if urg else (lib[top]["default_triage"] if top else "self_help"),
                    "risk_flags": []})
    add("T13", "keyword-urgency+issue-default", t13_triage, narr, t13, ["urgent_recall", "accuracy", "macro_f1"])
    add("T13", "always-lawyer", t13_triage, narr, gold_pred(lambda g: {"sample_id": g["sample_id"], "triage": "lawyer"}),
        ["urgent_recall", "accuracy", "macro_f1"])

    # interactive T9
    specs = [s for s in read_jsonl(RELEASE / "specs" / "test.jsonl") if s["variation"] not in ("out_of_scope", "non_legal")]
    comp = {}
    for name, pol in (("oracle", t09_next_question.oracle_policy), ("random", t09_next_question.random_policy)):
        for n in (1, 3):
            vals = [t09_next_question.simulate_policy(s, lib, pol, n) for s in specs]
            comp[(name, n)] = sum(vals) / len(vals)

    lines = ["# Baselines and evaluator sanity checks (test split)", "",
             "`gold` rows feed the gold labels back as predictions; they must score 1.0 (or 0 GED) and "
             "verify the evaluators. Other rows are simple reference baselines.", "",
             "| Task | System | Metrics |", "|---|---|---|"]
    for task, name, m in rows:
        lines.append(f"| {task} | {name} | " + ", ".join(f"{k}={v:.3f}" if isinstance(v, (int, float)) else f"{k}={v}" for k, v in m.items()) + " |")
    lines += ["", "## T9 interactive: case completeness after N questions", "", "| Policy | N=1 | N=3 |", "|---|---|---|"]
    for name in ("oracle", "random"):
        lines.append(f"| {name} | {comp[(name, 1)]:.3f} | {comp[(name, 3)]:.3f} |")
    md = "\n".join(lines) + "\n"
    (ROOT / "reports" / "baselines.md").write_text(md, encoding="utf-8")
    return md


def _trig(g, event_id):
    e = next(e for e in g["annotations"]["events"] if e["event_id"] == event_id)
    return [e["trigger"]["start"], e["trigger"]["end"]]


def _get(d, path):
    for k in path.split("."):
        d = d.get(k) if isinstance(d, dict) else None
    return d


if __name__ == "__main__":
    print(run())
