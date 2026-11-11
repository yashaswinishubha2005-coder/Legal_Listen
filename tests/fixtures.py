"""Worked example used by tests and docs/ontology.md (Kanglish, romanized).

Gloss: "My paternal uncle Ramesh sold our farm without my signature.
        I have the sale deed copy."
"""

from __future__ import annotations

from lexvaani.schemas.common import Span

UNIT = "ex_0001"
TEXT = (
    "Nanna chikkappa Ramesh namma thota na nanna sign illade maaridru. "
    "Sale deed copy nanna hatra ide."
)


def span(s: str) -> dict:
    i = TEXT.index(s)
    return Span(unit_id=UNIT, start=i, end=i + len(s), text=s).model_dump()


def example_graph_dict() -> dict:
    return {
        "nodes": [
            {"type": "Person", "id": "per_1", "label": "speaker", "role": "speaker",
             "status": "reported", "source_spans": [span("Nanna")]},
            {"type": "Person", "id": "per_2", "label": "Ramesh", "role": "respondent",
             "gender": "male", "synthetic_name": "Ramesh",
             "status": "reported", "source_spans": [span("Ramesh")]},
            {"type": "Asset", "id": "ast_1", "label": "family farm", "asset_type": "agricultural_land",
             "status": "reported", "source_spans": [span("thota")]},
            {"type": "Event", "id": "evt_1", "label": "sale of farm", "event_type": "sale_transfer",
             "trigger": span("maaridru"), "status": "evidence_supported",
             "source_spans": [span("maaridru")]},
            {"type": "Claim", "id": "clm_1", "label": "sold without consent",
             "proposition": "Ramesh sold the farm without the speaker's consent.",
             "status": "evidence_supported", "negation_cues": [span("illade")],
             "source_spans": [span("nanna sign illade maaridru")]},
            {"type": "Evidence", "id": "evd_1", "label": "sale deed copy", "evidence_type": "document",
             "availability": "held", "status": "reported",
             "source_spans": [span("Sale deed copy nanna hatra ide")]},
            {"type": "Issue", "id": "iss_1", "label": "co-heir sale", "issue_id": "prop.coheir_sale_without_consent",
             "status": "inferred"},
            {"type": "Element", "id": "elm_1", "label": "sale occurred", "issue_id": "prop.coheir_sale_without_consent",
             "element_id": "transfer_by_coowner", "critical": True, "value": "satisfied", "status": "evidence_supported"},
            {"type": "Element", "id": "elm_2", "label": "speaker is co-heir", "issue_id": "prop.coheir_sale_without_consent",
             "element_id": "claimant_has_share", "critical": True, "value": "unknown", "status": "unknown"},
            {"type": "Provision", "id": "prv_1", "label": "placeholder", "provision_id": "TEST_ACT:1",
             "status": "inferred"},
        ],
        "edges": [
            {"id": "e_1", "type": "KIN_OF", "source_id": "per_2", "target_id": "per_1", "status": "reported",
             "attributes": {"relation": "paternal_uncle", "surface_term": "chikkappa"},
             "source_spans": [span("chikkappa")]},
            {"id": "e_2", "type": "PARTICIPANT_IN", "source_id": "per_2", "target_id": "evt_1",
             "status": "reported", "attributes": {"role": "agent"}},
            {"id": "e_3", "type": "PARTICIPANT_IN", "source_id": "ast_1", "target_id": "evt_1",
             "status": "reported", "attributes": {"role": "patient"}},
            {"id": "e_4", "type": "ASSERTS", "source_id": "per_1", "target_id": "clm_1", "status": "reported"},
            {"id": "e_5", "type": "ABOUT", "source_id": "clm_1", "target_id": "evt_1", "status": "reported"},
            {"id": "e_6", "type": "SUPPORTS", "source_id": "evd_1", "target_id": "clm_1", "status": "reported"},
            {"id": "e_7", "type": "HOLDS", "source_id": "per_1", "target_id": "evd_1", "status": "reported"},
            {"id": "e_8", "type": "INDICATES", "source_id": "evt_1", "target_id": "iss_1", "status": "inferred"},
            {"id": "e_9", "type": "HAS_ELEMENT", "source_id": "iss_1", "target_id": "elm_1", "status": "inferred"},
            {"id": "e_10", "type": "HAS_ELEMENT", "source_id": "iss_1", "target_id": "elm_2", "status": "inferred"},
            {"id": "e_11", "type": "SATISFIES", "source_id": "clm_1", "target_id": "elm_1", "status": "evidence_supported"},
            {"id": "e_12", "type": "LACKS", "source_id": "iss_1", "target_id": "elm_2", "status": "unknown"},
            {"id": "e_13", "type": "APPLIES_TO", "source_id": "prv_1", "target_id": "iss_1", "status": "inferred"},
        ],
    }
