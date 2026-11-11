"""Gold-as-prediction must score perfectly in every evaluator (on freshly rendered data)."""
import pytest

from lexvaani.schemas.common import LangVariant


@pytest.fixture(scope="module")
def gold(specs, lib, bank):
    import json
    from lexvaani.render.narrative import render_narrative
    from lexvaani.dialogue.simulate import simulate
    narr = [json.loads(render_narrative(s, lib, v, bank).model_dump_json()) for s in specs[::6] for v in (LangVariant.EN, LangVariant.KN)]
    dlg = [json.loads(simulate(s, lib, LangVariant.HI_EN_LATN, bank).model_dump_json()) for s in specs[::6]]
    return narr, dlg


def test_t01_t02_t07_t08_t13(gold):
    from eval import t01_issues, t02_entities, t07_elements, t08_graph, t13_triage
    narr, _ = gold
    assert t01_issues.score(narr, [{"sample_id": g["sample_id"], "issues": g["annotations"]["issues"]} for g in narr])["micro_f1"] == 1.0
    p2 = [{"sample_id": g["sample_id"], "entities": [{"start": m["span"]["start"], "end": m["span"]["end"], "type": m["type"]}
           for m in g["annotations"]["entities"]]} for g in narr]
    assert t02_entities.score(narr, p2)["strict"]["f1"] == 1.0
    p7 = [{"sample_id": g["sample_id"], "elements": g["annotations"]["elements"]} for g in narr]
    assert t07_elements.score(narr, p7)["accuracy"] == 1.0
    p8 = [{"sample_id": g["sample_id"], "graph": g["annotations"]["case_graph"]} for g in narr]
    r8 = t08_graph.score(narr, p8)
    assert r8["node"]["f1"] == 1.0 and r8["edge"]["f1"] == 1.0 and r8["normalised_graph_edit_distance"] == 0.0
    p13 = [{"sample_id": g["sample_id"], "triage": g["annotations"]["triage"], "risk_flags": g["annotations"]["risk_flags"]} for g in narr]
    assert t13_triage.score(narr, p13)["accuracy"] == 1.0


def test_t05_t06(gold):
    from eval import t05_coref, t06_epistemic
    narr, dlg = gold
    p5 = [{"sample_id": g["sample_id"], "clusters": [[[m["span"]["start"], m["span"]["end"]] for m in g["annotations"]["entities"]
           if m["mention_id"] in c["mention_ids"]] for c in g["annotations"]["coref"]]} for g in narr]
    assert t05_coref.score(narr, p5)["conll_f1"] == 1.0
    p6 = [{"sample_id": g["sample_id"], "facts": [{"start": f["span"]["start"], "end": f["span"]["end"], "status": f["status"]} for f in g["annotations"]["facts"]],
           "cues": [{"start": c["start"], "end": c["end"], "type": "neg"} for f in g["annotations"]["facts"] for c in f["negation_cues"]]
           + [{"start": c["start"], "end": c["end"], "type": "hedge"} for f in g["annotations"]["facts"] for c in f["hedge_cues"]]} for g in narr]
    r6 = t06_epistemic.score(narr, p6)
    assert r6["status_accuracy"] == 1.0 and r6["cue"]["f1"] == 1.0


def test_t09_t12(gold):
    from eval import t09_next_question, t12_clarification
    _, dlg = gold
    p9 = [{"dialogue_id": d["dialogue_id"], "system_turn": dp["system_turn"], "ranking": [dp["gold_best"]]}
          for d in dlg for dp in d["decision_points"]]
    r9 = t09_next_question.score(dlg, p9)
    assert r9["hit@1"] == 1.0 and r9["hit@1_strict"] == 1.0
    p12 = [{"dialogue_id": d["dialogue_id"], "turn": t["index"], "label": t["clarification"]} for d in dlg for t in d["turns"] if t.get("clarification")]
    assert t12_clarification.score(dlg, p12)["accuracy"] == 1.0


def test_t10_validity(gold):
    from eval import t10_retrieval
    narr, _ = gold
    ref = ({p for g in narr for p in g["annotations"]["provisions"]}, "test")
    p10 = [{"sample_id": g["sample_id"], "provisions": g["annotations"]["provisions"]} for g in narr]
    r = t10_retrieval.score(narr, p10, ref)
    assert r["recall@10"] == 1.0 and r["citation_validity"] == 1.0
    bad = [{"sample_id": g["sample_id"], "provisions": ["BNS:9999"]} for g in narr]
    assert t10_retrieval.score(narr, bad, ref)["hallucination_rate"] == 1.0
