import copy

import pytest
from pydantic import ValidationError

from lexvaani.schemas import CaseGraph, Domain, IssueId, LangVariant, Span

from fixtures import TEXT, UNIT, example_graph_dict


def mutate(fn):
    g = copy.deepcopy(example_graph_dict())
    fn(g)
    return g


def node(g, nid):
    return next(n for n in g["nodes"] if n["id"] == nid)


# ------------------------------------------------------------------ common --

def test_issue_inventory():
    legal = [i for i in IssueId if not i.is_routing_label]
    assert len(legal) == 25
    for d in Domain:
        assert sum(i.domain == d for i in legal) == 5


def test_lang_variants():
    assert len(LangVariant) == 6
    assert {v for v in LangVariant if v.is_code_mixed} == {
        LangVariant.KN_EN_LATN, LangVariant.KN_EN_MIXED, LangVariant.HI_EN_LATN}


def test_span_ok_and_verify():
    i = TEXT.index("Ramesh")
    Span(unit_id=UNIT, start=i, end=i + 6, text="Ramesh").verify_against(TEXT)


@pytest.mark.parametrize("kw", [
    dict(start=5, end=5, text="x"),          # empty
    dict(start=0, end=3, text="ab"),         # length mismatch
    dict(start=0, end=6, text=" Nanna"),     # surrounding whitespace
])
def test_span_rejects(kw):
    with pytest.raises(ValidationError):
        Span(unit_id=UNIT, **kw)


def test_span_verify_detects_wrong_offsets():
    s = Span(unit_id=UNIT, start=0, end=6, text="Ramesh")
    with pytest.raises(ValueError):
        s.verify_against(TEXT)


def test_unicode_kannada_span():
    text = "ನಮ್ಮ ಚಿಕ್ಕಪ್ಪ ಜಮೀನು ಮಾರಿದರು"
    w = "ಚಿಕ್ಕಪ್ಪ"
    i = text.index(w)
    Span(unit_id="k", start=i, end=i + len(w), text=w).verify_against(text)


# ------------------------------------------------------------------- graph --

def test_example_graph_valid():
    g = CaseGraph.model_validate(example_graph_dict())
    assert len(g.nodes) == 10 and len(g.edges) == 13
    for n in g.nodes:
        for s in n.source_spans:
            s.verify_against(TEXT)


def test_roundtrip_json():
    g = CaseGraph.model_validate(example_graph_dict())
    assert CaseGraph.model_validate_json(g.model_dump_json()) == g


@pytest.mark.parametrize("name,fn", [
    ("bad id prefix", lambda g: node(g, "per_2").update(id="x_2")),
    ("unknown field", lambda g: node(g, "per_1").update(foo=1)),
    ("dup node id", lambda g: g["nodes"].append(copy.deepcopy(node(g, "per_1")))),
    ("dangling edge", lambda g: g["edges"].append(
        {"id": "e_99", "type": "ABOUT", "source_id": "clm_1", "target_id": "per_9", "status": "reported"})),
    ("illegal edge types", lambda g: g["edges"].append(
        {"id": "e_99", "type": "KIN_OF", "source_id": "per_1", "target_id": "ast_1",
         "status": "reported", "attributes": {"relation": "father"}})),
    ("KIN_OF w/o relation", lambda g: g["edges"][0]["attributes"].pop("relation")),
    ("bad kin relation", lambda g: g["edges"][0]["attributes"].update(relation="maava")),
    ("PARTICIPANT_IN w/o role", lambda g: g["edges"][1]["attributes"].clear()),
    ("self loop", lambda g: g["edges"].append(
        {"id": "e_99", "type": "CAUSES", "source_id": "evt_1", "target_id": "evt_1", "status": "inferred"})),
    ("supported w/o SUPPORTS", lambda g: g.update(edges=[e for e in g["edges"] if e["type"] != "SUPPORTS"])),
    ("conflicting w/o CONTRADICTS", lambda g: node(g, "clm_1").update(status="conflicting")),
    ("element value vs edges", lambda g: node(g, "elm_2").update(value="satisfied")),
    ("confidence > 1", lambda g: node(g, "per_1").update(confidence=1.5)),
    ("bad provision id", lambda g: node(g, "prv_1").update(provision_id="section 318")),
])
def test_graph_rejects(name, fn):
    with pytest.raises(ValidationError):
        CaseGraph.model_validate(mutate(fn))


def _two_events(g):
    g["nodes"].append({"type": "Event", "id": "evt_2", "label": "threat", "event_type": "threat",
                       "status": "reported"})


def test_before_cycle_rejected():
    def fn(g):
        _two_events(g)
        g["edges"] += [
            {"id": "e_90", "type": "BEFORE", "source_id": "evt_1", "target_id": "evt_2", "status": "reported"},
            {"id": "e_91", "type": "BEFORE", "source_id": "evt_2", "target_id": "evt_1", "status": "reported"},
        ]
    with pytest.raises(ValidationError, match="cycle"):
        CaseGraph.model_validate(mutate(fn))


def test_symmetric_edge_canonical_order():
    def ok(g):
        _two_events(g)
        g["edges"].append({"id": "e_90", "type": "OVERLAP", "source_id": "evt_1", "target_id": "evt_2",
                           "status": "reported"})
    CaseGraph.model_validate(mutate(ok))

    def bad(g):
        _two_events(g)
        g["edges"].append({"id": "e_90", "type": "OVERLAP", "source_id": "evt_2", "target_id": "evt_1",
                           "status": "reported"})
    with pytest.raises(ValidationError, match="symmetric"):
        CaseGraph.model_validate(mutate(bad))
