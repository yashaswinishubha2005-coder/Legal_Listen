"""Coverage matrix issue x variation x language (balanced by construction)."""

from __future__ import annotations

from collections import Counter
from pathlib import Path

from lexvaani.schemas.common import LangVariant
from lexvaani.schemas.spec import ScenarioSpec, Variation

VARS = [v for v in Variation]


def write_coverage(specs: list[ScenarioSpec], lib, path: Path) -> None:
    base = Counter((s.issues[0].value, s.variation.value) for s in specs if s.minimal_pair is None)
    sib = Counter((s.issues[0].value, s.variation.value) for s in specs if s.minimal_pair is not None)
    n_lang = len(LangVariant)
    lines = ["# Coverage matrix", "",
             f"Each spec is rendered in all {n_lang} language/script variants "
             f"({', '.join(v.value for v in LangVariant)}), so the language axis is balanced by construction: "
             "every cell below has the same count in every variant.", "",
             "Cell = base specs (+ minimal-pair siblings).", "",
             "| Issue | " + " | ".join(v.value for v in VARS) + " | total |",
             "|---|" + "---|" * (len(VARS) + 1)]
    issues = [i.value for i in lib] + ["x.out_of_scope", "x.non_legal"]
    for i in issues:
        cells, tot = [], 0
        for v in VARS:
            b, s = base[(i, v.value)], sib[(i, v.value)]
            tot += b + s
            cells.append(f"{b}" + (f" (+{s})" if s else "") if b or s else "–")
        lines.append(f"| {i} | " + " | ".join(cells) + f" | {tot} |")
    n_specs = len(specs)
    lines += ["", f"**Specs:** {n_specs} ({sum(base.values())} base + {sum(sib.values())} minimal-pair siblings)",
              f"**Narratives:** {n_specs * n_lang}  ·  **Dialogues:** {n_specs * n_lang}", "",
              "## Minimal-pair flip types", ""]
    flips = Counter(s.minimal_pair.flip_type for s in specs if s.minimal_pair)
    lines += [f"- {k}: {v}" for k, v in sorted(flips.items())]
    lines += ["", "## Difficulty", ""]
    lines += [f"- {k}: {v}" for k, v in sorted(Counter(s.difficulty.value for s in specs).items())]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
