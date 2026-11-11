"""T6 Epistemic status + hedging / negation cues.
pred: {"sample_id", "facts": [{"start", "end", "status"}], "cues": [{"start", "end", "type": "neg"|"hedge"}]}
Each gold fact is paired with the predicted fact of maximal overlap; unmatched gold facts count
as status 'none' (wrong). Cue F1 is partial-match F1 evaluated inside gold fact spans."""
from eval.common import by_key, cli, r4
from eval.metrics import classification, prf

STATUSES = ["reported", "evidence_supported", "inferred", "conflicting", "unknown"]


def score(gold, pred):
    P = by_key(pred, "sample_id")
    gy, py = [], []
    c_tp = c_fp = c_fn = 0
    for g in gold:
        p = P.get(g["sample_id"], {})
        pf = p.get("facts", [])
        for f in g["annotations"]["facts"]:
            s, e = f["span"]["start"], f["span"]["end"]
            best, ov = None, 0
            for x in pf:
                o = min(e, x["end"]) - max(s, x["start"])
                if o > ov:
                    best, ov = x, o
            gy.append(f["status"])
            py.append(best["status"] if best else "none")
        gcues = [(c["start"], c["end"], "neg") for f in g["annotations"]["facts"] for c in f["negation_cues"]]
        gcues += [(c["start"], c["end"], "hedge") for f in g["annotations"]["facts"] for c in f["hedge_cues"]]
        fact_spans = [(f["span"]["start"], f["span"]["end"]) for f in g["annotations"]["facts"]]
        pc = [(c["start"], c["end"], c["type"]) for c in p.get("cues", [])
              if any(c["start"] < e and s < c["end"] for s, e in fact_spans)]
        used = set()
        for q in pc:
            k = next((i for i, x in enumerate(gcues) if i not in used and x[2] == q[2] and x[0] < q[1] and q[0] < x[1]), None)
            if k is None:
                c_fp += 1
            else:
                used.add(k); c_tp += 1
        c_fn += len(gcues) - len(used)
    cls = classification(gy, py, STATUSES)
    return r4({"n_facts": len(gy), "status_macro_f1": cls["macro_f1"], "status_accuracy": cls["accuracy"],
               "per_status_f1": {k: v["f1"] for k, v in cls["per_class"].items()}, "cue": prf(c_tp, c_fp, c_fn)})


if __name__ == "__main__":
    cli("T6 epistemic status", "narratives", score)
