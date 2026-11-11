"""LLM-as-judge with a model different from the generator; scores are validated
against human ratings on a subset (agreement reported in the QC report).

    python -m lexvaani.llm.judge --n 50     (asks before spending)
"""

from __future__ import annotations

import argparse
import json
import os
import re

from lexvaani.schemas.sample import NarrativeSample

from .provider import ROOT, from_env

PROMPT = ROOT / "prompts" / "judge_v1.md"
LOW = 3   # any score below this goes to human review


def spec_summary(s: NarrativeSample) -> str:
    a = s.annotations
    facts = [f"- [{f.status.value}{', hedged' if f.hedged else ''}] {f.element_id or 'context'}: {f.polarity.value}"
             for f in a.facts]
    return "\n".join([f"issues: {', '.join(i.value for i in a.issues)}", f"triage: {a.triage.value}",
                      f"risk flags: {', '.join(r.value for r in a.risk_flags) or 'none'}", "facts:", *facts])


def judge(s: NarrativeSample, provider) -> dict:
    prompt = PROMPT.read_text(encoding="utf-8").replace("{{VARIANT}}", s.lang_variant.value) \
        .replace("{{SPEC}}", spec_summary(s)).replace("{{TEXT}}", s.text)
    c = provider.complete(prompt, tag=f"judge:{s.sample_id}")
    m = re.search(r"\{.*\}", c.text, flags=re.S)
    try:
        d = json.loads(m.group(0)) if m else {}
        scores = {k: int(d[k]) for k in ("naturalness", "faithfulness", "label_correctness")}
    except (ValueError, KeyError, TypeError):
        return {"sample_id": s.sample_id, "status": "unparseable", "raw": c.text}
    return {"sample_id": s.sample_id, "status": "ok", **scores, "comment": d.get("comment", ""),
            "needs_human_review": min(scores.values()) < LOW}


def check_independence() -> None:
    gen = (os.environ.get("LLM_PROVIDER"), os.environ.get("GEN_MODEL"))
    jud = (os.environ.get("JUDGE_PROVIDER"), os.environ.get("JUDGE_MODEL"))
    if jud[0] and gen[0] and jud[0] == gen[0]:
        raise SystemExit(f"judge provider {jud[0]} must differ from generator provider {gen[0]}")


def agreement(judge_scores: list[int], human_scores: list[int]) -> dict:
    """Quadratic-weighted kappa + exact agreement between judge and human ratings (1-5)."""
    from lexvaani.annotation.iaa import weighted_kappa
    exact = sum(a == b for a, b in zip(judge_scores, human_scores)) / max(1, len(human_scores))
    return {"n": len(human_scores), "exact": round(exact, 3),
            "qwk": round(weighted_kappa(judge_scores, human_scores, labels=[1, 2, 3, 4, 5]), 3)}


def main() -> None:  # pragma: no cover - CLI
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=50)
    ap.add_argument("--yes", action="store_true")
    args = ap.parse_args()
    check_independence()
    prov = from_env("JUDGE", temperature=0.0)
    src = ROOT / "data" / "samples" / "narratives.jsonl"
    samples = [NarrativeSample.model_validate_json(l) for _, l in zip(range(args.n), open(src, encoding="utf-8"))]
    if not args.yes and input(f"Judge {len(samples)} samples with {prov.name}/{prov.model}? [y/N] ").lower() != "y":
        return
    out = ROOT / "data" / "samples" / "judge_scores.jsonl"
    with open(out, "w", encoding="utf-8") as f:
        for s in samples:
            f.write(json.dumps(judge(s, prov), ensure_ascii=False) + "\n")
    print("wrote", out)


if __name__ == "__main__":  # pragma: no cover
    main()
