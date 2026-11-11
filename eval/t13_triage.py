"""T13 Triage & risk. pred: {"sample_id", "triage": self_help|lawyer|urgent, "risk_flags": [...]}
Primary metric: recall of the 'urgent' class (missing an urgent case is the costliest error)."""
from eval.common import by_key, cli, r4
from eval.metrics import classification, multilabel_f1

LABELS = ["self_help", "lawyer", "urgent"]


def score(gold, pred):
    P = by_key(pred, "sample_id")
    gy, py, gr, pr = [], [], [], []
    for g in gold:
        p = P.get(g["sample_id"], {})
        gy.append(g["annotations"]["triage"]); py.append(p.get("triage", "missing"))
        gr.append(set(g["annotations"]["risk_flags"])); pr.append(set(p.get("risk_flags", [])))
    c = classification(gy, py, LABELS)
    return r4({"n": len(gy), "urgent_recall": c["per_class"]["urgent"]["recall"], "accuracy": c["accuracy"],
               "macro_f1": c["macro_f1"], "per_class": c["per_class"],
               "risk_flag_micro_f1": multilabel_f1(gr, pr)["micro_f1"]})


if __name__ == "__main__":
    cli("T13 triage & risk", "narratives", score)
