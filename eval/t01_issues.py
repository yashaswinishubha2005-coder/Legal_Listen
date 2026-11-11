"""T1 Legal issue identification.
pred: {"sample_id", "issues": [issue ids], "ranked_issues": [optional ranked list], "domains": [optional]}"""
from eval.common import by_key, cli, r4
from eval.metrics import multilabel_f1, top_k_accuracy


def score(gold, pred):
    P = by_key(pred, "sample_id")
    g_sets, p_sets, ranks, gd, pd = [], [], [], [], []
    for g in gold:
        p = P.get(g["sample_id"], {})
        g_sets.append(set(g["annotations"]["issues"]))
        p_sets.append(set(p.get("issues", [])))
        ranks.append(p.get("ranked_issues") or p.get("issues", []))
        gd.append(set(g["annotations"]["domains"]))
        pd.append(set(p.get("domains", [])))
    ml = multilabel_f1(g_sets, p_sets)
    return r4({"n": len(gold), "micro_f1": ml["micro_f1"], "macro_f1": ml["macro_f1"],
               "top1_accuracy": top_k_accuracy(g_sets, ranks, 1), "top3_accuracy": top_k_accuracy(g_sets, ranks, 3),
               "domain_micro_f1": multilabel_f1(gd, pd)["micro_f1"], "coverage": sum(g["sample_id"] in P for g in gold) / max(1, len(gold))})


if __name__ == "__main__":
    cli("T1 issue identification", "narratives", score)
