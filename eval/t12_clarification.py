"""T12 Clarification detection. pred: {"dialogue_id", "turn", "label"} for user turns after the
opening; labels new_fact | correction | reexplain_request. Metric: macro-F1."""
from eval.common import cli, r4
from eval.metrics import classification

LABELS = ["new_fact", "correction", "reexplain_request"]


def score(gold, pred):
    P = {(p["dialogue_id"], p["turn"]): p["label"] for p in pred}
    gy, py = [], []
    for d in gold:
        for t in d["turns"]:
            if t.get("clarification"):
                gy.append(t["clarification"])
                py.append(P.get((d["dialogue_id"], t["index"]), "missing"))
    c = classification(gy, py, LABELS)
    return r4({"n": len(gy), "macro_f1": c["macro_f1"], "accuracy": c["accuracy"],
               "per_class_f1": {k: v["f1"] for k, v in c["per_class"].items()}})


if __name__ == "__main__":
    cli("T12 clarification detection", "dialogues", score)
