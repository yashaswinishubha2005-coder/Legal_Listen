"""LLM naturalisation of template narratives with exact span preservation.

Every gold span is wrapped in a numbered marker ⟦k|...⟧. The model may rewrite
everything else but must copy markers verbatim (it may move them). After
generation the markers are located and stripped, and every gold span is
re-projected from marker positions. Any missing, duplicated or altered marker
means the sample is REJECTED (regenerate or keep the template version) —
offsets are never guessed.

Run (asks before spending): python -m lexvaani.llm.paraphrase --n 20 --variant kn-en_latn
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from lexvaani.schemas.common import Span
from lexvaani.schemas.sample import NarrativeSample

from .provider import ROOT, from_env

PROMPT = (ROOT / "prompts" / "paraphrase_v1.md")
MARK_RE = re.compile(r"⟦(\d+)\|([^⟧]*)⟧")


def collect_spans(s: NarrativeSample) -> list[Span]:
    a = s.annotations
    spans = [m.span for m in a.entities] + [e.trigger for e in a.events]
    for f in a.facts:
        spans += f.negation_cues + f.hedge_cues
    # keep non-overlapping, outermost-first, unique spans
    uniq = sorted({(x.start, x.end): x for x in spans}.values(), key=lambda x: (x.start, -x.end))
    out, last_end = [], -1
    for x in uniq:
        if x.start >= last_end:
            out.append(x)
            last_end = x.end
    return out


def mark(s: NarrativeSample) -> tuple[str, list[Span]]:
    spans = collect_spans(s)
    text, pos = "", 0
    for k, sp in enumerate(spans):
        text += s.text[pos:sp.start] + f"⟦{k}|{sp.text}⟧"
        pos = sp.end
    return text + s.text[pos:], spans


def unmark(generated: str, spans: list[Span]) -> tuple[str, dict[int, tuple[int, int]]] | None:
    found = MARK_RE.findall(generated)
    ids = [int(k) for k, _ in found]
    if sorted(ids) != list(range(len(spans))):
        return None
    for k, inner in found:
        if inner != spans[int(k)].text:
            return None
    out, pos, where = "", 0, {}
    for m in MARK_RE.finditer(generated):
        out += generated[pos:m.start()]
        where[int(m.group(1))] = (len(out), len(out) + len(m.group(2)))
        out += m.group(2)
        pos = m.end()
    out += generated[pos:]
    return out, where


def build_prompt(s: NarrativeSample, marked: str) -> str:
    tpl = PROMPT.read_text(encoding="utf-8")
    return tpl.replace("{{VARIANT}}", s.lang_variant.value).replace("{{TEXT}}", marked)


def paraphrase(s: NarrativeSample, provider) -> dict:
    marked, spans = mark(s)
    c = provider.complete(build_prompt(s, marked), tag=f"paraphrase:{s.sample_id}")
    res = unmark(c.text.strip(), spans)
    if res is None:
        return {"sample_id": s.sample_id, "status": "rejected", "reason": "marker mismatch", "raw": c.text}
    new_text, where = res
    mapping = {(sp.start, sp.end): where[k] for k, sp in enumerate(spans)}
    return {"sample_id": s.sample_id, "status": "ok", "text": new_text, "span_map": [[a, b, *mapping[(a, b)]] for a, b in mapping]}


def main() -> None:  # pragma: no cover - CLI
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--variant", default=None)
    ap.add_argument("--yes", action="store_true", help="skip the cost confirmation")
    args = ap.parse_args()
    prov = from_env("GEN", temperature=0.7)
    src = ROOT / "data" / "samples" / "narratives.jsonl"
    samples = []
    for line in open(src, encoding="utf-8"):
        s = NarrativeSample.model_validate_json(line)
        if args.variant is None or s.lang_variant.value == args.variant:
            samples.append(s)
        if len(samples) >= args.n:
            break
    if not args.yes:
        ans = input(f"About to send {len(samples)} prompts to {prov.name}/{prov.model}. Continue? [y/N] ")
        if ans.lower() != "y":
            return
    out = ROOT / "data" / "samples" / "paraphrase_pilot.jsonl"
    with open(out, "w", encoding="utf-8") as f:
        for s in samples:
            f.write(json.dumps(paraphrase(s, prov), ensure_ascii=False) + "\n")
    print("wrote", out)


if __name__ == "__main__":  # pragma: no cover
    main()
