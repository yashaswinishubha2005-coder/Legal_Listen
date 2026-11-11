import math

from eval import metrics as M


def test_prf_and_multilabel():
    assert M.prf(1, 1, 1)["f1"] == 0.5
    r = M.multilabel_f1([{"a"}, {"a", "b"}], [{"a"}, {"b"}])
    assert math.isclose(r["micro_f1"], 0.8)


def test_span_f1_modes():
    g = [(0, 5, "PER"), (10, 15, "ORG")]
    p = [(0, 5, "PER"), (11, 14, "ORG"), (20, 22, "PER")]
    assert math.isclose(M.span_f1(g, p, "strict")["f1"], 0.4)
    assert math.isclose(M.span_f1(g, p, "partial")["f1"], 0.8)


def test_conll_perfect_and_degenerate():
    key = [{1, 2, 3}, {4, 5}]
    assert math.isclose(M.conll_f1(key, key)["conll_f1"], 1.0)
    sing = [{1}, {2}, {3}, {4}, {5}]
    r = M.conll_f1(key, sing)
    assert r["muc"]["recall"] == 0.0 and r["conll_f1"] < 1


def test_muc_known_value():
    # Vilain et al. example: key {A,B,C,D}, response {A,B},{C,D} -> recall 2/3, precision 1
    r, p = M._muc([{"A", "B", "C", "D"}], [{"A", "B"}, {"C", "D"}])
    assert math.isclose(r, 2 / 3) and p == 1.0


def test_hungarian():
    assert sorted(M.hungarian([[4, 1, 3], [2, 0, 5], [3, 2, 2]])) == [(0, 1), (1, 0), (2, 2)]


def test_ranking():
    assert M.mrr([{"b"}], [["a", "b"]]) == 0.5
    assert M.recall_at_k([{"a", "b"}], [["a", "c"]], 1) == 0.5
    assert math.isclose(M.ndcg_at_k([{"a"}], [["a"]], 10), 1.0)


def test_chrf_and_ece():
    assert math.isclose(M.chrf("ಇದು ಒಂದು ವಾಕ್ಯ", "ಇದು ಒಂದು ವಾಕ್ಯ"), 100.0)
    assert M.chrf("abc", "xyz") == 0.0
    assert M.ece([1.0, 1.0], [True, True]) == 0.0
    assert math.isclose(M.ece([0.9, 0.9], [False, False]), 0.9)


def test_classification_macro():
    r = M.classification(["a", "a", "b"], ["a", "b", "b"], ["a", "b"])
    assert math.isclose(r["accuracy"], 2 / 3)


def test_iaa():
    from lexvaani.annotation.iaa import cohen_kappa, fleiss_kappa, weighted_kappa, compute
    assert cohen_kappa(["a", "b", "a"], ["a", "b", "a"]) == 1.0
    assert math.isclose(cohen_kappa(["a", "a", "b", "b"], ["a", "b", "a", "b"]), 0.0)
    assert fleiss_kappa([["a", "a"], ["b", "b"]]) == 1.0
    assert weighted_kappa([1, 2, 3], [1, 2, 3], [1, 2, 3]) == 1.0
    res = compute([{"item_id": 1, "task": "t", "label": "x"}], [{"item_id": 1, "task": "t", "label": "y"}])
    assert res["adjudication_queue"]
