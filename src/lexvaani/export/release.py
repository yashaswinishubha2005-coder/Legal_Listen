"""Release export: per-split JSONL, test subsets, flat CSVs, HF loader, checksums."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
from collections import Counter, defaultdict
from pathlib import Path

from lexvaani.schemas.dialogue import Dialogue
from lexvaani.schemas.issue_library import Triage
from lexvaani.schemas.sample import NarrativeSample
from lexvaani.schemas.spec import ScenarioSpec, Variation

VERSION = "0.1.0"
NAME = f"lexvaani-in-v{VERSION}"


def _read(path: Path, model):
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield model.model_validate_json(line)


def _write(path: Path, objs) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with open(path, "w", encoding="utf-8") as f:
        for o in objs:
            f.write((o.model_dump_json() if hasattr(o, "model_dump_json") else json.dumps(o, ensure_ascii=False)) + "\n")
            n += 1
    return n


def find_duplicate_specs(narratives: list[NarrativeSample], specs: dict[str, ScenarioSpec]) -> set[str]:
    """Spec ids whose English narrative is identical to an earlier spec from another family."""
    seen: dict[str, str] = {}
    drop: set[str] = set()
    for s in sorted((n for n in narratives if n.lang_variant.value == "en" and n.noise is None),
                    key=lambda n: n.spec_id):
        key = " ".join(s.text.split())
        if key in seen and specs[seen[key]].family_id != specs[s.spec_id].family_id:
            drop.add(s.spec_id)
        else:
            seen.setdefault(key, s.spec_id)
    # a dropped base spec takes its minimal-pair siblings with it
    for sid in list(drop):
        drop |= {x.spec_id for x in specs.values() if x.family_id == specs[sid].family_id}
    return drop


def subsets_for(smp: NarrativeSample, spec: ScenarioSpec, pair_families: set[str]) -> list[str]:
    out = []
    if spec.family_id in pair_families:
        out.append("test_contrastive")
    if smp.noise is not None:
        out.append("test_asr_noise")
    elif smp.lang_variant.is_code_mixed:
        out.append("test_code_mixed")
    if spec.variation == Variation.OUT_OF_SCOPE:
        out.append("test_out_of_scope")
    if spec.triage == Triage.URGENT:
        out.append("test_high_risk")
    return out


def flat_row(smp: NarrativeSample, split: str, subsets: list[str]) -> dict:
    a = smp.annotations
    m = smp.metadata
    dump = lambda xs: json.dumps([x.model_dump(mode="json") for x in xs], ensure_ascii=False)  # noqa: E731
    return {
        "sample_id": smp.sample_id, "spec_id": smp.spec_id, "family_id": smp.family_id, "split": split,
        "test_subsets": "|".join(subsets), "lang_variant": smp.lang_variant.value, "variation": smp.variation.value,
        "difficulty": smp.difficulty.value, "conversation_date": smp.conversation_date, "text": smp.text,
        "issues": "|".join(i.value for i in a.issues), "domains": "|".join(d.value for d in a.domains),
        "triage": a.triage.value, "risk_flags": "|".join(r.value for r in a.risk_flags),
        "provisions": "|".join(a.provisions),
        "elements": json.dumps([[e.issue_id.value, e.element_id, e.critical, e.value.value] for e in a.elements]),
        "entities": dump(a.entities), "events": dump(a.events), "timexes": dump(a.timexes), "tlinks": dump(a.tlinks),
        "coref": dump(a.coref), "facts": dump(a.facts),
        "case_graph": a.case_graph.model_dump_json(),
        "is_asr_noisy": smp.noise is not None, "clean_sample_id": smp.noise.clean_sample_id if smp.noise else "",
        "word_error_rate": smp.noise.word_error_rate if smp.noise else 0.0,
        "cmi": smp.qc.get("cmi", ""),
        "speaker_gender": m.gender.value, "age_group": m.age_group.value, "settlement": m.settlement.value,
        "region": m.region.value, "religion": m.religion.value, "literacy_proxy": m.literacy_proxy.value,
    }


def export_release(root: Path, P: dict) -> None:
    from lexvaani.qc.langid import cmi, tag_tokens
    out = root / "release" / NAME
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    split_spec = json.loads(P["splits"].read_text())["spec"]
    specs = {s.spec_id: s for s in _read(P["specs"], ScenarioSpec)}
    narr = list(_read(P["narr"], NarrativeSample))
    asr = list(_read(P["asr"], NarrativeSample))
    drop = find_duplicate_specs(narr, specs)
    pair_fams = {s.family_id for s in specs.values() if s.minimal_pair is not None}
    keep = lambda sid: sid not in drop  # noqa: E731

    for s in narr + asr:
        names = {m.span.text for m in s.annotations.entities if m.kind.value == "name"}
        s.qc["cmi"] = cmi(tag_tokens(s.text, s.lang_variant, names))

    by_split: dict[str, list] = defaultdict(list)
    for s in narr:
        if keep(s.spec_id):
            by_split[split_spec[s.spec_id]].append(s)
    asr_split: dict[str, list] = defaultdict(list)
    for s in asr:
        if keep(s.spec_id):
            asr_split[split_spec[s.spec_id]].append(s)
    counts = {}
    for sp in ("train", "dev", "test"):
        counts[f"narratives/{sp}"] = _write(out / "narratives" / f"{sp}.jsonl", by_split[sp])
        counts[f"narratives_asr/{sp}"] = _write(out / "narratives_asr" / f"{sp}.jsonl", asr_split[sp])
    spec_rows = defaultdict(list)
    for s in specs.values():
        if keep(s.spec_id):
            spec_rows[split_spec[s.spec_id]].append(s)
    for sp in ("train", "dev", "test"):
        counts[f"specs/{sp}"] = _write(out / "specs" / f"{sp}.jsonl", spec_rows[sp])
    dlg_split: dict[str, list] = defaultdict(list)
    for d in _read(P["dlg"], Dialogue):
        if keep(d.spec_id):
            dlg_split[split_spec[d.spec_id]].append(d)
    for sp in ("train", "dev", "test"):
        counts[f"dialogues/{sp}"] = _write(out / "dialogues" / f"{sp}.jsonl", dlg_split[sp])
    exp_split: dict[str, list] = defaultdict(list)
    with open(P["exp"], encoding="utf-8") as f:
        for line in f:
            e = json.loads(line)
            if keep(e["spec_id"]):
                exp_split[split_spec[e["spec_id"]]].append(e)
    for sp in ("train", "dev", "test"):
        counts[f"explanations/{sp}"] = _write(out / "explanations" / f"{sp}.jsonl", exp_split[sp])

    # test subsets (full records)
    subsets: dict[str, list] = defaultdict(list)
    for s in by_split["test"] + asr_split["test"]:
        for name in subsets_for(s, specs[s.spec_id], pair_fams):
            subsets[name].append(s)
    for name in ("test_contrastive", "test_asr_noise", "test_code_mixed", "test_out_of_scope", "test_high_risk"):
        counts[f"test_subsets/{name}"] = _write(out / "test_subsets" / f"{name}.jsonl", subsets[name])
    th = out / "test_human"
    th.mkdir()
    (th / "README.md").write_text(TEST_HUMAN_README, encoding="utf-8")

    # corpus + resources
    (out / "corpus").mkdir()
    shutil.copy(P["corpus"], out / "corpus" / "provisions.jsonl")
    shutil.copy(P["registry"], out / "corpus" / "provision_registry.jsonl")
    from lexvaani.resources import glossary, issue_library
    (out / "resources").mkdir()
    _write(out / "resources" / "issue_library.jsonl", issue_library().values())
    _write(out / "resources" / "glossary.jsonl", glossary())

    # flat CSVs (the "one file" views)
    csv_dir = out / "csv"
    csv_dir.mkdir()
    rows = []
    for sp in ("train", "dev", "test"):
        for s in by_split[sp]:
            rows.append(flat_row(s, sp, subsets_for(s, specs[s.spec_id], pair_fams) if sp == "test" else []))
        for s in asr_split[sp]:
            rows.append(flat_row(s, sp, subsets_for(s, specs[s.spec_id], pair_fams) if sp == "test" else []))
    _csv(csv_dir / "narratives.csv", rows)
    turn_rows, dp_rows = [], []
    for sp in ("train", "dev", "test"):
        for d in dlg_split[sp]:
            for t in d.turns:
                turn_rows.append({"dialogue_id": d.dialogue_id, "spec_id": d.spec_id, "split": sp,
                                  "lang_variant": d.lang_variant.value, "turn": t.index, "speaker": t.speaker.value,
                                  "text": t.text, "question_id": t.question_id or "",
                                  "clarification_label": t.clarification.value if t.clarification else ""})
            for dp in d.decision_points:
                dp_rows.append({"dialogue_id": d.dialogue_id, "split": sp, "system_turn": dp.system_turn,
                                "gold_best": dp.gold_best, "acceptable_set": "|".join(dp.acceptable_set),
                                "candidates": "|".join(c.question_id for c in dp.candidates),
                                "completeness_before": dp.state_before.completeness,
                                "completeness_after": dp.state_after.completeness})
    _csv(csv_dir / "dialogue_turns.csv", turn_rows)
    _csv(csv_dir / "next_question.csv", dp_rows)
    spec_csv = [{"spec_id": s.spec_id, "family_id": s.family_id, "split": split_spec[s.spec_id],
                 "variation": s.variation.value, "difficulty": s.difficulty.value,
                 "issues": "|".join(i.value for i in s.issues), "triage": s.triage.value,
                 "risk_flags": "|".join(r.value for r in s.risk_flags), "law_regime": s.law_regime.value if s.law_regime else "",
                 "conversation_date": s.conversation_date, "incident_date": s.incident_date or "",
                 "gold_provisions": "|".join(s.gold_provisions),
                 "minimal_pair_of": s.minimal_pair.base_spec_id if s.minimal_pair else "",
                 "flip_type": s.minimal_pair.flip_type if s.minimal_pair else ""}
                for s in specs.values() if keep(s.spec_id)]
    _csv(csv_dir / "specs.csv", spec_csv)
    # one combined JSON-lines file of all clean narratives for convenience
    counts["all_narratives"] = _write(out / "lexvaani_in_narratives_all.jsonl",
                                      [s for sp in ("train", "dev", "test") for s in by_split[sp]])

    shutil.copy(root / "src" / "lexvaani" / "export" / "hf_loader.py", out / "lexvaani_in.py")
    for doc in ("DATASHEET.md",):
        if (root / doc).exists():
            shutil.copy(root / doc, out / doc)
    if (root / "docs" / "dataset_card.md").exists():
        shutil.copy(root / "docs" / "dataset_card.md", out / "README.md")
    meta = {"name": "LexVaani-IN", "version": VERSION, "counts": counts, "dropped_duplicate_specs": sorted(drop),
            "splits_by_spec": dict(Counter(split_spec[s] for s in specs if keep(s)))}
    (out / "release_info.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    sums = []
    for p in sorted(out.rglob("*")):
        if p.is_file() and p.name != "SHA256SUMS":
            sums.append(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(out)}")
    (out / "SHA256SUMS").write_text("\n".join(sums) + "\n", encoding="utf-8")
    print("export:", json.dumps(meta["counts"]), "dropped duplicates:", len(drop))


def _csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


TEST_HUMAN_README = """# test_human/ — human-written test set (intentionally empty)

This split is reserved for narratives and dialogues **written or spoken by real
people** (team members, consenting volunteers) following `docs/recording_protocol.md`.

Rules:
1. Write from imagination or from the scenario prompt card only — never real personal data.
2. Never look at, or tune prompts/models on, these items. They are used ONLY for final evaluation.
3. Annotate with the same guidelines (`docs/annotation_guidelines.md`), two annotators per item,
   adjudicate disagreements, and report inter-annotator agreement alongside results.
4. Store items as `narratives.jsonl` / `dialogues.jsonl` in this folder using the release schema.
"""
