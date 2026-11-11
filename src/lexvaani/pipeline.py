"""End-to-end build CLI:  python -m lexvaani.pipeline <stage> [--seed N]

Stages: corpus | specs | splits | render | dialogues | noise | explanations | qc | export | stats | all
Every stage is deterministic given the seed and the resources; outputs are hashed
into data/MANIFEST.sha256 (data versioning without DVC).
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from lexvaani.schemas.common import LangVariant
from lexvaani.schemas.spec import ScenarioSpec

ROOT = Path(__file__).resolve().parents[2]
D = ROOT / "data"
P = {
    "raw_acts": D / "raw" / "acts",
    "corpus": D / "corpus" / "provisions.jsonl",
    "registry": D / "corpus" / "provision_registry.jsonl",
    "specs": D / "specs" / "specs.jsonl",
    "narr": D / "samples" / "narratives.jsonl",
    "asr": D / "samples" / "narratives_asr.jsonl",
    "dlg": D / "dialogues" / "dialogues.jsonl",
    "exp": D / "explanations" / "explanations.jsonl",
    "splits": D / "splits" / "splits.json",
}


def write_jsonl(path: Path, rows) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write((r if isinstance(r, str) else r.model_dump_json(exclude_none=False)) + "\n")
            n += 1
    return n


def read_jsonl(path: Path, model=None):
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield model.model_validate_json(line) if model else json.loads(line)


def lib_and_bank():
    from lexvaani.resources import issue_library, other_scenarios
    return issue_library(), other_scenarios()


def stage_corpus(args) -> None:
    from lexvaani.corpus.parse import build_corpus, load_corpus
    from lexvaani.corpus.registry import build_registry, write_registry
    r = build_corpus(P["raw_acts"], P["corpus"], ROOT / "reports" / "corpus_parse_report.md")
    lib, _ = lib_and_bank()
    reg = build_registry(lib, load_corpus(P["corpus"]))
    write_registry(reg, P["registry"], ROOT / "reports" / "provision_verification.md")
    print(f"corpus: {r['sections']} sections; missing PDFs: {len(r['missing'])}; registry: {len(reg)} ids")


def stage_specs(args) -> None:
    from lexvaani.specs.generate import generate_all
    from lexvaani.specs.coverage import write_coverage
    lib, bank = lib_and_bank()
    specs = generate_all(lib, bank, seed=args.seed, per_cell=args.per_cell)
    n = write_jsonl(P["specs"], specs)
    write_coverage(specs, lib, ROOT / "reports" / "coverage.md")
    print(f"specs: {n}")


def load_specs() -> list[ScenarioSpec]:
    return list(read_jsonl(P["specs"], ScenarioSpec))


def stage_splits(args) -> None:
    from lexvaani.splits.make_splits import assign_splits, check_no_leakage
    specs = load_specs()
    fam = assign_splits(specs, seed=args.seed)
    spec_split = {s.spec_id: fam[s.family_id] for s in specs}
    problems = check_no_leakage(spec_split, specs)
    if problems:
        raise SystemExit("split leakage: " + "; ".join(problems[:5]))
    P["splits"].parent.mkdir(parents=True, exist_ok=True)
    P["splits"].write_text(json.dumps({"family": fam, "spec": spec_split}, indent=1), encoding="utf-8")
    from collections import Counter
    print("splits:", dict(Counter(spec_split.values())))


def stage_render(args) -> None:
    from lexvaani.render.narrative import render_narrative
    lib, bank = lib_and_bank()
    rows = (render_narrative(s, lib, v, bank) for s in load_specs() for v in LangVariant)
    print(f"narratives: {write_jsonl(P['narr'], rows)}")


def stage_dialogues(args) -> None:
    from lexvaani.dialogue.simulate import simulate
    lib, bank = lib_and_bank()
    rows = (simulate(s, lib, v, bank) for s in load_specs() for v in LangVariant)
    print(f"dialogues: {write_jsonl(P['dlg'], rows)}")


def stage_noise(args) -> None:
    from lexvaani.noise.asr import corrupt
    from lexvaani.schemas.sample import NarrativeSample
    from lexvaani.specs.generate import rng_for
    split = json.loads(P["splits"].read_text())["spec"]

    def gen():
        for smp in read_jsonl(P["narr"], NarrativeSample):
            sp = split[smp.spec_id]
            r = rng_for(args.seed, "noise", smp.sample_id).random()
            if sp == "test":
                yield corrupt(smp, "medium", args.seed)
                if r < 0.33:
                    yield corrupt(smp, "high", args.seed)
            elif r < 0.2:
                yield corrupt(smp, "medium", args.seed)
    print(f"asr-noisy narratives: {write_jsonl(P['asr'], gen())}")


def stage_explanations(args) -> None:
    from collections import defaultdict
    from lexvaani.corpus.parse import load_corpus
    from lexvaani.explain.references import build_explanations
    from lexvaani.schemas.sample import NarrativeSample
    lib, _ = lib_and_bank()
    corpus = load_corpus(P["corpus"])
    by_spec: dict[str, dict] = defaultdict(dict)
    for smp in read_jsonl(P["narr"], NarrativeSample):
        if smp.lang_variant in (LangVariant.EN, LangVariant.KN, LangVariant.HI):
            by_spec[smp.spec_id][smp.lang_variant] = smp
    rows = (e for s in load_specs() for e in build_explanations(s, lib, by_spec[s.spec_id], corpus))
    print(f"explanation references: {write_jsonl(P['exp'], rows)}")


def stage_qc(args) -> None:
    from lexvaani.qc.report import run_qc
    run_qc(ROOT, P)


def stage_export(args) -> None:
    from lexvaani.export.release import export_release
    export_release(ROOT, P)


def stage_stats(args) -> None:
    from lexvaani.qc.stats import write_stats
    write_stats(ROOT)


def write_manifest() -> None:
    lines = []
    for path in sorted(D.rglob("*")):
        if path.is_file() and path.suffix in (".jsonl", ".json", ".csv") and "raw" not in path.parts:
            h = hashlib.sha256(path.read_bytes()).hexdigest()
            lines.append(f"{h}  {path.relative_to(ROOT)}")
    (D / "MANIFEST.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")


STAGES = {"corpus": stage_corpus, "specs": stage_specs, "splits": stage_splits, "render": stage_render,
          "dialogues": stage_dialogues, "noise": stage_noise, "explanations": stage_explanations,
          "qc": stage_qc, "export": stage_export, "stats": stage_stats}
ORDER = ["corpus", "specs", "splits", "render", "dialogues", "noise", "explanations", "qc", "export", "stats"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("stage", choices=list(STAGES) + ["all"])
    ap.add_argument("--seed", type=int, default=13)
    ap.add_argument("--per-cell", type=int, default=4)
    args = ap.parse_args()
    for st in (ORDER if args.stage == "all" else [args.stage]):
        STAGES[st](args)
    write_manifest()


if __name__ == "__main__":
    main()
