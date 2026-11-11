"""T5 Coreference (PERSON/ORGANIZATION mentions). Works on narratives and on dialogues
(mentions across turns, span = (turn index, start, end)).
pred (narratives): {"sample_id", "clusters": [[[start, end], ...], ...]}
pred (dialogues):  {"dialogue_id", "clusters": [[[turn, start, end], ...], ...]}"""
import argparse, json
from eval.common import DEFAULT_GOLD, by_key, read_jsonl, r4
from eval.metrics import conll_f1


def _avg(results):
    keys = ["muc", "b3", "ceafe"]
    out = {k: sum(r[k]["f1"] for r in results) / len(results) for k in keys}
    out["conll_f1"] = sum(r["conll_f1"] for r in results) / len(results)
    return out


def score(gold, pred, dialogues=False):
    key = "dialogue_id" if dialogues else "sample_id"
    P = by_key(pred, key)
    res = []
    for g in gold:
        if dialogues:
            ments = {}
            for t in g["turns"]:
                for m in t["entities"]:
                    ments[m["mention_id"]] = (t["index"], m["span"]["start"], m["span"]["end"])
            clusters = [{ments[m] for m in c["mention_ids"] if m in ments} for c in g["coref"]]
        else:
            ments = {m["mention_id"]: (m["span"]["start"], m["span"]["end"]) for m in g["annotations"]["entities"]}
            clusters = [{ments[m] for m in c["mention_ids"]} for c in g["annotations"]["coref"]]
        clusters = [c for c in clusters if c]
        if not clusters:
            continue
        resp = [{tuple(x) for x in c} for c in P.get(g[key], {}).get("clusters", [])]
        res.append(conll_f1(clusters, resp))
    return r4({"n_docs": len(res), **(_avg(res) if res else {})})


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pred", required=True)
    ap.add_argument("--gold", default=None)
    ap.add_argument("--dialogues", action="store_true")
    a = ap.parse_args()
    gold = read_jsonl(a.gold or DEFAULT_GOLD["dialogues" if a.dialogues else "narratives"])
    print(json.dumps(score(gold, read_jsonl(a.pred), a.dialogues), indent=2))
