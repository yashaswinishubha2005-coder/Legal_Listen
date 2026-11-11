"""T7 Legal element satisfaction.
pred: {"sample_id", "elements": [{"issue_id", "element_id", "value", "probs": {satisfied, contradicted, unknown}?}]}
Missing predictions count as wrong. If probs are given, ECE (10 bins) is reported."""
from eval.common import by_key, cli, r4
from eval.metrics import classification, ece

LABELS = ["satisfied", "contradicted", "unknown"]


def score(gold, pred):
    P = by_key(pred, "sample_id")
    gy, py, conf, corr = [], [], [], []
    crit_g, crit_p = [], []
    for g in gold:
        pm = {(e["issue_id"], e["element_id"]): e for e in P.get(g["sample_id"], {}).get("elements", [])}
        for e in g["annotations"]["elements"]:
            q = pm.get((e["issue_id"], e["element_id"]))
            v = q["value"] if q else "missing"
            gy.append(e["value"]); py.append(v)
            if e["critical"]:
                crit_g.append(e["value"]); crit_p.append(v)
            if q and q.get("probs"):
                c = max(q["probs"].values())
                conf.append(c); corr.append(v == e["value"])
    cls = classification(gy, py, LABELS)
    out = {"n": len(gy), "macro_f1": cls["macro_f1"], "accuracy": cls["accuracy"],
           "per_class_f1": {k: v["f1"] for k, v in cls["per_class"].items()},
           "critical_macro_f1": classification(crit_g, crit_p, LABELS)["macro_f1"]}
    if conf:
        out["ece"] = ece(conf, corr)
    return r4(out)


if __name__ == "__main__":
    cli("T7 element satisfaction", "narratives", score)
