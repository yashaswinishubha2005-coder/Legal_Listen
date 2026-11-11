"""Provision registry: every provision id the benchmark references, checked against the corpus.

A reference like ``BNS:115(2)`` is checked by its base section ``115``. The
registry also proposes old<->new mappings (IPC<->BNS, CrPC<->BNSS) when the
issue library lists both for the same issue with the same title hint; every
mapping is TO_VERIFY.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from lexvaani.schemas.common import IssueId, Verification
from lexvaani.schemas.corpus import ProvisionRecord, RegistryEntry
from lexvaani.schemas.issue_library import IssueSchema

OLD_NEW = {"IPC": "BNS", "CrPC": "BNSS", "IEA": "BSA"}


def split_id(pid: str) -> tuple[str, str, str]:
    act, sec = pid.split(":", 1)
    m = re.match(r"^(\d+[A-Z]{0,3})(.*)$", sec)
    base = m.group(1) if m else sec
    return act, sec, base


def _tokens(s: str | None) -> set[str]:
    return {w for w in re.findall(r"[a-z]+", (s or "").lower()) if len(w) > 3}


def build_registry(lib: dict[IssueId, IssueSchema], corpus: dict[str, ProvisionRecord]) -> list[RegistryEntry]:
    entries: dict[str, dict] = {}
    for issue in lib.values():
        for cp in issue.candidate_provisions:
            e = entries.setdefault(cp.provision_id, {"hint": cp.title_hint, "refs": [], "notes": set()})
            e["refs"].append(issue.issue_id.value)
            if cp.note:
                e["notes"].add(cp.note)
    # old/new mapping proposals
    maps: dict[str, set[str]] = {}
    for issue in lib.values():
        cps = issue.candidate_provisions
        for a in cps:
            for b in cps:
                aa, _, _ = split_id(a.provision_id)
                bb, _, _ = split_id(b.provision_id)
                ta, tb = _tokens(a.title_hint), _tokens(b.title_hint)
                if OLD_NEW.get(aa) == bb and ta and tb and len(ta & tb) / len(ta | tb) >= 0.6:
                    maps.setdefault(a.provision_id, set()).add(b.provision_id)
                    maps.setdefault(b.provision_id, set()).add(a.provision_id)
    out = []
    for pid, e in sorted(entries.items()):
        act, sec, base = split_id(pid)
        rec = corpus.get(f"{act}:{base}")
        title_match = None
        if rec is not None and e["hint"]:
            title_match = len(_tokens(rec.title) & _tokens(e["hint"])) >= 1
        out.append(RegistryEntry(
            provision_id=pid, act=act, section_id=sec, title_hint=e["hint"], in_corpus=rec is not None,
            title_match=title_match, verification=Verification.TO_VERIFY,
            maps_to=sorted(maps.get(pid, [])), referenced_by=sorted(set(e["refs"])),
            note="; ".join(sorted(e["notes"])) or None))
    return out


def write_registry(entries: list[RegistryEntry], path: Path, report: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for e in entries:
            f.write(e.model_dump_json() + "\n")
    n_in = sum(e.in_corpus for e in entries)
    lines = ["# Provision verification checklist (Gate 1)", "",
             "Every provision the benchmark cites is listed here. **All are TO_VERIFY.** A human must open the "
             "official text, confirm that the section exists, that its heading matches the hint, and that it "
             "applies to the issue, and only then mark it `verified` in `data/corpus/provision_registry.jsonl`.",
             "", f"- Provisions referenced: **{len(entries)}**",
             f"- Found in the parsed corpus: **{n_in}** (the corpus is empty until the Act PDFs are added)", "",
             "| Provision | Title hint (expected heading) | In corpus | Heading match | Old/new mapping | Used by | Note | Verified by | Date |",
             "|---|---|---|---|---|---|---|---|---|"]
    for e in entries:
        lines.append(f"| `{e.provision_id}` | {e.title_hint or ''} | {'yes' if e.in_corpus else 'no'} | "
                     f"{'' if e.title_match is None else ('yes' if e.title_match else '**NO**')} | "
                     f"{', '.join(e.maps_to)} | {', '.join(e.referenced_by)} | {e.note or ''} |  |  |")
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_registry(path: Path) -> dict[str, RegistryEntry]:
    if not path.exists():
        return {}
    return {e.provision_id: e for e in (RegistryEntry.model_validate_json(l) for l in path.read_text().splitlines() if l.strip())}


def reference_set(corpus: dict[str, ProvisionRecord], registry: dict[str, RegistryEntry]) -> tuple[set[str], str]:
    """The closed set of citable ids for T10 citation validity.

    With a parsed corpus: every corpus section, plus subsection references whose
    base section is in the corpus. Without one: the registry (documented fallback)."""
    if corpus:
        ids = set(corpus)
        ids |= {pid for pid in registry if f"{split_id(pid)[0]}:{split_id(pid)[2]}" in corpus}
        return ids, "corpus"
    return set(registry), "registry"


def dump_json(obj, path: Path) -> None:
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
