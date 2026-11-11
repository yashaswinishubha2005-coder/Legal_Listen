"""T3 Event & argument extraction.
pred: {"sample_id", "events": [{"trigger": [s, e], "event_type", "arguments": [{"role", "start", "end"}]}]}
An argument is correct if its event's trigger overlaps a gold trigger, the role matches, and its span
overlaps the gold argument's mention span (time = the event's timex span, place = LOCATION mention)."""
from eval.common import by_key, cli, r4
from eval.metrics import prf


def _gold_args(g):
    ann = g["annotations"]
    ments = {m["mention_id"]: m["span"] for m in ann["entities"]}
    tx = {t["id"]: t["span"] for t in ann["timexes"] if t.get("span")}
    out = []
    for e in ann["events"]:
        trig = (e["trigger"]["start"], e["trigger"]["end"])
        args = [(a["role"], ments[a["mention_id"]]["start"], ments[a["mention_id"]]["end"])
                for a in e["arguments"] if a.get("mention_id") in ments]
        if e.get("time_id") in tx:
            args.append(("time", tx[e["time_id"]]["start"], tx[e["time_id"]]["end"]))
        out.append({"trigger": trig, "type": e["event_type"], "args": args})
    return out


def score(gold, pred):
    P = by_key(pred, "sample_id")
    t_tp = t_fp = t_fn = 0
    a_tp = a_fp = a_fn = 0
    ty_ok = 0
    for g in gold:
        gev = _gold_args(g)
        pev = [{"trigger": tuple(e["trigger"]), "type": e.get("event_type"),
                "args": [(a["role"], a["start"], a["end"]) for a in e.get("arguments", [])]}
               for e in P.get(g["sample_id"], {}).get("events", [])]
        used = set()
        for pe in pev:
            m = next((i for i, ge in enumerate(gev) if i not in used and ge["trigger"][0] < pe["trigger"][1]
                      and pe["trigger"][0] < ge["trigger"][1]), None)
            if m is None:
                t_fp += 1; a_fp += len(pe["args"]); continue
            used.add(m); t_tp += 1
            ge = gev[m]
            ty_ok += pe["type"] == ge["type"]
            gu = set()
            for (role, s, e) in pe["args"]:
                k = next((j for j, (r2, s2, e2) in enumerate(ge["args"]) if j not in gu and r2 == role and s < e2 and s2 < e), None)
                if k is None:
                    a_fp += 1
                else:
                    gu.add(k); a_tp += 1
            a_fn += len(ge["args"]) - len(gu)
        for i, ge in enumerate(gev):
            if i not in used:
                t_fn += 1; a_fn += len(ge["args"])
    return r4({"trigger": prf(t_tp, t_fp, t_fn), "trigger_type_accuracy": ty_ok / max(1, t_tp),
               "argument": prf(a_tp, a_fp, a_fn)})


if __name__ == "__main__":
    cli("T3 event & argument extraction", "narratives", score)
