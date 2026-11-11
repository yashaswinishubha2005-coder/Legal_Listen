"""T11 Plain-language explanation. pred: {"explanation_id", "text"}
chrF against the reference (all available sections concatenated), readability of the prediction,
and the mean human faithfulness rating when --human (explanation_id -> 1..5) is supplied.
References whose official text is still pending are scored without the 'what it says' part."""
import argparse
import json

from eval.common import DEFAULT_GOLD, by_key, read_jsonl, r4
from eval.metrics import chrf, readability


def ref_text(e):
    parts = [e.get("what_it_says") or "", e["what_it_means"], e["why_it_may_apply"], " ".join(e["conditions"]),
             e["where_to_verify"]]
    return " ".join(p for p in parts if p)


def score(gold, pred, human=None):
    P = by_key(pred, "explanation_id")
    by_lang = {}
    for g in gold:
        p = P.get(g["explanation_id"])
        if not p:
            continue
        d = by_lang.setdefault(g["language"], {"chrf": [], "wps": [], "fre": []})
        d["chrf"].append(chrf(p["text"], ref_text(g)))
        rd = readability(p["text"], g["language"])
        d["wps"].append(rd["words_per_sentence"])
        if "flesch_reading_ease" in rd:
            d["fre"].append(rd["flesch_reading_ease"])
    out = {"coverage": sum(g["explanation_id"] in P for g in gold) / max(1, len(gold))}
    for lang, d in by_lang.items():
        out[lang] = {"chrf": sum(d["chrf"]) / len(d["chrf"]), "words_per_sentence": sum(d["wps"]) / len(d["wps"])}
        if d["fre"]:
            out[lang]["flesch_reading_ease"] = sum(d["fre"]) / len(d["fre"])
    if human:
        vals = [v for k, v in human.items() if k in P]
        out["human_faithfulness_mean"] = sum(vals) / len(vals) if vals else None
    out["pending_corpus_text_share"] = sum(g["status"] == "pending_corpus_text" for g in gold) / max(1, len(gold))
    return r4(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pred", required=True)
    ap.add_argument("--gold", default=str(DEFAULT_GOLD["explanations"]))
    ap.add_argument("--human", default=None, help="JSON {explanation_id: rating}")
    a = ap.parse_args()
    human = json.load(open(a.human)) if a.human else None
    print(json.dumps(score(read_jsonl(a.gold), read_jsonl(a.pred), human), indent=2, ensure_ascii=False))
