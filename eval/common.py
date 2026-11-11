"""Shared I/O for task evaluators. Every evaluator is callable as

    python -m eval.tNN_<name> --pred preds.jsonl [--gold release/<...>/narratives/test.jsonl]

and prints a JSON metrics report. Gold defaults to the clean test split."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
RELEASE = ROOT / "release" / "lexvaani-in-v0.1.0"
DEFAULT_GOLD = {
    "narratives": RELEASE / "narratives" / "test.jsonl",
    "dialogues": RELEASE / "dialogues" / "test.jsonl",
    "explanations": RELEASE / "explanations" / "test.jsonl",
}


def read_jsonl(path: Path | str) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def by_key(rows: list[dict], key: str) -> dict:
    return {r[key]: r for r in rows}


def cli(name: str, gold_kind: str, score: Callable[[list[dict], list[dict]], dict]) -> None:
    ap = argparse.ArgumentParser(description=f"LexVaani-IN evaluator: {name}")
    ap.add_argument("--pred", required=True)
    ap.add_argument("--gold", default=str(DEFAULT_GOLD[gold_kind]))
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    res = score(read_jsonl(a.gold), read_jsonl(a.pred))
    txt = json.dumps(res, indent=2, ensure_ascii=False)
    print(txt)
    if a.out:
        Path(a.out).write_text(txt, encoding="utf-8")


def r4(d):
    if isinstance(d, dict):
        return {k: r4(v) for k, v in d.items()}
    if isinstance(d, float):
        return round(d, 4)
    return d
