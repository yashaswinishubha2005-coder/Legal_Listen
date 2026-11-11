"""T4 Temporal normalisation & ordering.
pred: {"sample_id", "timexes": [{"start", "end", "value"}],
       "tlinks": [{"source": [s, e], "target": [s, e], "relation": BEFORE|AFTER|OVERLAP}]}
Events in tlinks are identified by trigger spans. AFTER(a,b) is normalised to BEFORE(b,a)."""
from eval.common import by_key, cli, r4
from eval.metrics import prf


def _norm(src, tgt, rel):
    if rel == "AFTER":
        return tgt, src, "BEFORE"
    if rel == "OVERLAP" and src > tgt:
        return tgt, src, rel
    return src, tgt, rel


def score(gold, pred):
    P = by_key(pred, "sample_id")
    v_ok = v_n = 0
    l_tp = l_fp = l_fn = 0
    for g in gold:
        ann = g["annotations"]
        p = P.get(g["sample_id"], {})
        for t in ann["timexes"]:
            if not t.get("span"):
                continue
            v_n += 1
            s, e = t["span"]["start"], t["span"]["end"]
            m = next((x for x in p.get("timexes", []) if x["start"] < e and s < x["end"]), None)
            v_ok += bool(m and m.get("value") == t["value"])
        trig = {}
        for ev in ann["events"]:
            trig.setdefault(ev["event_id"], (ev["trigger"]["start"], ev["trigger"]["end"]))

        def to_event(span):
            for eid, (s, e) in trig.items():
                if span[0] < e and s < span[1]:
                    return eid
            return None
        gl = {_norm(l["source"], l["target"], l["relation"]) for l in ann["tlinks"]}
        pl = set()
        for l in p.get("tlinks", []):
            a, b = to_event(l["source"]), to_event(l["target"])
            if a and b and a != b:
                pl.add(_norm(a, b, l["relation"]))
        l_tp += len(gl & pl); l_fp += len(pl - gl); l_fn += len(gl - pl)
    return r4({"timex_value_accuracy": v_ok / max(1, v_n), "n_timex": v_n, "tlink": prf(l_tp, l_fp, l_fn)})


if __name__ == "__main__":
    cli("T4 temporal", "narratives", score)
