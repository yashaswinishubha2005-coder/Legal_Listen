"""Label Studio configs + task export (>=15% subset, two annotators per item).

    python -m lexvaani.annotation.labelstudio      -> annotation/labelstudio/*
"""

from __future__ import annotations

import json
from pathlib import Path

from lexvaani.schemas.common import IssueId
from lexvaani.schemas.ontology import ElementValue
from lexvaani.schemas.sample import EntityType, NarrativeSample
from lexvaani.specs.generate import rng_for

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "annotation" / "labelstudio"
FRACTION = 0.16
ANNOTATORS = ["annotator_1", "annotator_2", "annotator_3"]


def _choices(name: str, to: str, values: list[str], multiple: bool = False) -> str:
    opts = "\n".join(f'      <Choice value="{v}"/>' for v in values)
    choice = ' choice="multiple"' if multiple else ""
    return f'    <Choices name="{name}" toName="{to}"{choice}>\n{opts}\n    </Choices>'


def configs() -> dict[str, str]:
    issues = [i.value for i in IssueId]
    ents = [e.value for e in EntityType]
    return {
        "t1_t13_issue_triage.xml": f"""<View>
  <Header value="Read the narrative. Select ALL legal issues raised, then triage."/>
  <Text name="text" value="$text"/>
{_choices("issues", "text", issues, multiple=True)}
{_choices("triage", "text", ["self_help", "lawyer", "urgent"])}
{_choices("risk_flags", "text", ["imminent_violence", "ongoing_abuse", "threat_to_life", "self_harm", "minor_involved", "image_circulation", "golden_hour_fraud", "imminent_property_transfer", "eviction_imminent", "limitation_near_expiry", "evidence_at_risk", "child_removal_imminent"], multiple=True)}
</View>""",
        "t2_entities.xml": f"""<View>
  <Header value="Mark every entity mention of a case participant or value (see guidelines T2)."/>
  <Labels name="ent" toName="text">
{chr(10).join(f'    <Label value="{e}"/>' for e in ents)}
    <Label value="TRIGGER"/><Label value="NEG_CUE"/><Label value="HEDGE_CUE"/>
  </Labels>
  <Text name="text" value="$text"/>
  <Relations><Relation value="COREF"/><Relation value="ARG_agent"/><Relation value="ARG_patient"/><Relation value="ARG_recipient"/><Relation value="ARG_instrument"/><Relation value="ARG_place"/><Relation value="ARG_time"/></Relations>
</View>""",
        "t6_epistemic.xml": f"""<View>
  <Header value="For the highlighted claim, choose its epistemic status (guidelines T6 decision tree)."/>
  <Text name="text" value="$text"/>
  <Labels name="claim" toName="text"><Label value="CLAIM"/></Labels>
{_choices("status", "text", ["reported", "evidence_supported", "inferred", "conflicting", "unknown"])}
{_choices("hedged", "text", ["yes", "no"])}
</View>""",
        "t7_elements.xml": f"""<View>
  <Header value="For each listed element of the issue, decide: satisfied / contradicted / unknown (guidelines T7)."/>
  <Text name="text" value="$text"/>
  <Text name="element" value="$element_description"/>
{_choices("value", "element", [v.value for v in ElementValue])}
</View>""",
        "t12_clarification.xml": f"""<View>
  <Text name="context" value="$previous_turns"/>
  <Text name="turn" value="$user_turn"/>
{_choices("label", "turn", ["new_fact", "correction", "reexplain_request"])}
</View>""",
    }


def export(narratives_path: Path) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, xml in configs().items():
        (OUT / name).write_text(xml + "\n", encoding="utf-8")
    tasks = []
    with open(narratives_path, encoding="utf-8") as f:
        for line in f:
            s = NarrativeSample.model_validate_json(line)
            if rng_for("annot", s.family_id).random() >= FRACTION:
                continue
            r = rng_for("assign", s.sample_id)
            pair = r.sample(ANNOTATORS, 2)
            tasks.append({"data": {"sample_id": s.sample_id, "text": s.text, "lang_variant": s.lang_variant.value},
                          "meta": {"assigned_to": pair, "double_annotation": True}})
    (OUT / "tasks_double.json").write_text(json.dumps(tasks, ensure_ascii=False, indent=1), encoding="utf-8")
    return {"tasks": len(tasks)}


if __name__ == "__main__":  # pragma: no cover
    print(export(ROOT / "data" / "samples" / "narratives.jsonl"))
