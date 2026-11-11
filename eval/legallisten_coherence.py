"""Conversation coherence check: does LegalListen stay on the client's problem?

    python -m eval.legallisten_coherence     -> reports/legallisten_coherence.md

For 40 hand-written, natural client messages (formal and informal, en / kn / hi / romanised;
eval/legallisten_coherence.jsonl) the opening message is sent and every question is answered neutrally
("I don't know" for facts, first option otherwise). Measured:
  * issue_ok      — a gold issue is among the identified / considered issues (or the client is asked to choose
                    and a gold issue is offered)
  * off_topic     — share of asked fact questions that belong to an issue outside the client's legal area
  * asked_again   — facts the client already stated that were asked again
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from legallisten.engine import Engine  # noqa: E402
from legallisten.knowledge import kb  # noqa: E402


def run_case(engine: Engine, case: dict) -> dict:
    k = kb()
    st = engine.start(case["lang"], conversation_date="2026-10-27")
    engine.handle(st, case["text"])
    stated = {key for key, es in st.elements.items() if es.value in ("satisfied", "contradicted")}
    offered = [c.id.split(":", 1)[1] for c in (st.pending.chips if st.pending and st.pending.kind == "issue_choice" else [])]
    asked, again = [], 0
    for _ in range(20):
        p = st.pending
        if p is None:
            break
        if p.kind == "issue_choice":
            pick = next((i for i in offered if i in case["issues"]), offered[0] if offered else "other")
            engine.handle(st, "", chip=f"issue:{pick}")
            continue
        if p.kind == "element":
            asked.append(p.key)
            again += p.key in stated
            engine.handle(st, "", chip="dk")
        else:
            engine.handle(st, "", chip=p.chips[0].id)
    considered = set(st.issue_prior)
    issue_ok = bool(considered & set(case["issues"])) or bool(set(offered) & set(case["issues"]))
    off = [a for a in asked if k.domain(a.split("|")[0]) != case["domain"]]
    return {"id": case["id"], "lang": case["lang"], "gold": case["issues"], "considered": sorted(considered),
            "offered_choice": offered, "issue_ok": issue_ok, "asked": len(asked), "off_topic": len(off),
            "off_topic_keys": off, "asked_again": again}


def main() -> None:
    cases = [json.loads(l) for l in open(ROOT / "eval" / "legallisten_coherence.jsonl", encoding="utf-8") if l.strip()]
    engine = Engine(None)
    rows = [run_case(engine, c) for c in cases]
    n = len(rows)
    asked = sum(r["asked"] for r in rows)
    res = {"n": n, "issue_ok": round(sum(r["issue_ok"] for r in rows) / n, 3),
           "off_topic_rate": round(sum(r["off_topic"] for r in rows) / max(1, asked), 3),
           "asked_again": sum(r["asked_again"] for r in rows), "questions_mean": round(asked / n, 2),
           "asked_choice": sum(bool(r["offered_choice"]) for r in rows)}
    L = ["# LegalListen conversation coherence (offline mode)", "",
         f"{n} hand-written natural client messages (eval/legallisten_coherence.jsonl). Written by the developers; "
         "used to find and fix off-topic questioning, so the scores are optimistic — not a blind test.", "",
         f"- Correct issue identified or offered for the client to choose: **{res['issue_ok']}**",
         f"- Fact questions outside the client's legal area: **{res['off_topic_rate']}**",
         f"- Facts already stated that were asked again: **{res['asked_again']}**",
         f"- Mean fact questions: {res['questions_mean']} · cases where the client was asked to pick the problem: {res['asked_choice']}", "",
         "| id | lang | gold | considered | offered choice | ok | asked | off-topic |", "|---|---|---|---|---|---|---|---|"]
    L += [f"| {r['id']} | {r['lang']} | {', '.join(r['gold'])} | {', '.join(r['considered'])} | {', '.join(r['offered_choice'])} | "
          f"{'✓' if r['issue_ok'] else '✗'} | {r['asked']} | {r['off_topic']} |" for r in rows]
    (ROOT / "reports" / "legallisten_coherence.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print(json.dumps(res, indent=1))
    for r in rows:
        if not r["issue_ok"] or r["off_topic"]:
            print("FAIL", r["id"], r["gold"], r["considered"], r["offered_choice"], r["off_topic_keys"])


if __name__ == "__main__":
    main()
