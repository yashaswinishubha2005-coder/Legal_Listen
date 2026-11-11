"""T10 Provision retrieval. pred: {"sample_id", "provisions": [ranked provision ids]}
Recall@k / nDCG@10 over samples with at least one gold provision. Citation validity = share of
ALL predicted ids that exist in the reference set (parsed corpus; the provision registry while
the corpus is empty). Hallucination rate = 1 - citation validity."""
import argparse
import json

from eval.common import DEFAULT_GOLD, RELEASE, by_key, read_jsonl, r4
from eval.metrics import ndcg_at_k, recall_at_k


def reference_set(release=RELEASE):
    corpus = {r["provision_id"] for r in read_jsonl(release / "corpus" / "provisions.jsonl")} \
        if (release / "corpus" / "provisions.jsonl").exists() else set()
    registry = {r["provision_id"] for r in read_jsonl(release / "corpus" / "provision_registry.jsonl")}
    if corpus:
        def base(p):
            import re
            act, sec = p.split(":", 1)
            m = re.match(r"^(\d+[A-Z]{0,3})", sec)
            return f"{act}:{m.group(1) if m else sec}"
        return corpus | {p for p in registry if base(p) in corpus}, "corpus"
    return registry, "registry"


def score(gold, pred, ref=None):
    ref, basis = ref or reference_set()
    P = by_key(pred, "sample_id")
    G, R = [], []
    all_pred = []
    for g in gold:
        r = P.get(g["sample_id"], {}).get("provisions", [])
        all_pred += r
        if g["annotations"]["provisions"]:
            G.append(set(g["annotations"]["provisions"]))
            R.append(r)
    valid = sum(p in ref for p in all_pred) / len(all_pred) if all_pred else 1.0
    return r4({"n": len(G), **{f"recall@{k}": recall_at_k(G, R, k) for k in (1, 3, 5, 10)},
               "ndcg@10": ndcg_at_k(G, R, 10), "citation_validity": valid, "hallucination_rate": 1 - valid,
               "validity_basis": basis})


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pred", required=True)
    ap.add_argument("--gold", default=str(DEFAULT_GOLD["narratives"]))
    a = ap.parse_args()
    print(json.dumps(score(read_jsonl(a.gold), read_jsonl(a.pred)), indent=2))
