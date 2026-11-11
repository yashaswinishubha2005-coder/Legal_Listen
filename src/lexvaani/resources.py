"""Load and validate authored resources (issue library, glossary, other-scenario bank)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml

from lexvaani.schemas.common import IssueId, LangVariant
from lexvaani.schemas.glossary import GlossaryEntry
from lexvaani.schemas.issue_library import IssueSchema

from .render.markup import slots_in, tags_in

ROOT = Path(__file__).resolve().parents[2]
RES = ROOT / "resources"
BUILTIN_SLOTS = {"SPK", "DATE", "AMOUNT", "ITEM", "PLACE", "IDNUM", "AMOUNT2"}


def _load_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


@lru_cache(maxsize=1)
def issue_library() -> dict[IssueId, IssueSchema]:
    out: dict[IssueId, IssueSchema] = {}
    for path in sorted((RES / "issues").glob("*.yaml")):
        doc = _load_yaml(path)
        for raw in doc.get("issues", []):
            issue = IssueSchema.model_validate(raw)
            if issue.issue_id in out:
                raise ValueError(f"duplicate issue {issue.issue_id.value} in {path.name}")
            check_issue_templates(issue)
            out[issue.issue_id] = issue
    return out


def check_issue_templates(issue: IssueSchema) -> None:
    """Static checks: every slot a template uses is declared; facts with an event
    have exactly the triggers they need; DATE only where an event exists."""
    declared = {c.slot for c in issue.cast} | BUILTIN_SLOTS | set(issue.value_slots)
    where = issue.issue_id.value

    def check(tpl: str, ctx: str) -> None:
        unknown = slots_in(tpl) - declared
        if unknown:
            raise ValueError(f"{where}/{ctx}: undeclared slots {sorted(unknown)} in {tpl!r}")
        for t in tags_in(tpl):
            base = t.split(":")[0]
            if base not in {"TRIG", "NEG", "EVD", "TIMEX"} and not base.startswith("@"):
                raise ValueError(f"{where}/{ctx}: unknown tag {t!r}")

    for v in LangVariant:
        check(issue.setup[v], f"setup.{v.value}")
        for el in issue.elements:
            for pol in ("satisfied", "contradicted"):
                tpl = getattr(el, pol)[v]
                check(tpl, f"{el.element_id}.{pol}.{v.value}")
                if el.event_type and "TRIG" not in tags_in(tpl):
                    raise ValueError(f"{where}/{el.element_id}.{pol}.{v.value}: event fact without TRIG")
                if not el.event_type and "TRIG" in tags_in(tpl):
                    raise ValueError(f"{where}/{el.element_id}.{pol}.{v.value}: TRIG without event_type")
                if "{DATE" in tpl and not el.event_type:
                    raise ValueError(f"{where}/{el.element_id}: DATE without event")
        for ev in issue.evidence:
            for pol in ("held", "missing"):
                tpl = getattr(ev, pol)[v]
                check(tpl, f"{ev.evidence_id}.{pol}.{v.value}")
                if "EVD" not in tags_in(tpl):
                    raise ValueError(f"{where}/{ev.evidence_id}.{pol}.{v.value}: no EVD mention")
        for rf in issue.risk_facts:
            check(rf.template[v], f"risk.{rf.flag.value}.{v.value}")
    # date_slot_required elements must actually carry a DATE in every variant
    for el in issue.elements:
        if el.date_slot_required:
            for v in LangVariant:
                if "{DATE" not in el.satisfied[v]:
                    raise ValueError(f"{where}/{el.element_id}: date_slot_required but no DATE ({v.value})")


@lru_cache(maxsize=1)
def glossary() -> list[GlossaryEntry]:
    doc = _load_yaml(RES / "glossary.yaml")
    return [GlossaryEntry.model_validate(e) for e in doc["terms"]]


@lru_cache(maxsize=1)
def other_scenarios() -> dict:
    return _load_yaml(RES / "other_scenarios.yaml")
