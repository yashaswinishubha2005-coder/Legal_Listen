from lexvaani.dialogue import oracle


def test_belief_updates_direction():
    b = 0.5
    assert oracle.update(b, True, True) > b > oracle.update(b, True, False)


def test_critical_weighted_higher():
    b = {"x": 0.5}
    assert oracle.score("x|a", b, True) > oracle.score("x|b", b, False)


def test_acceptable_contains_best_and_ties():
    ranked = oracle.rank(["i|a", "i|b", "i|c"], {"i": 0.5}, {"i|a": True, "i|b": True, "i|c": False},
                         {"i|a": 2, "i|b": 1, "i|c": 0})
    acc = oracle.acceptable(ranked)
    assert ranked[0][0] == "i|b"            # tie broken by interview order
    assert {"i|a", "i|b"} <= set(acc) and "i|c" not in acc


def test_dialogues_respect_spec(specs, lib, bank):
    from lexvaani.dialogue.simulate import simulate
    from lexvaani.schemas.common import LangVariant
    for s in specs[::11]:
        d = simulate(s, lib, LangVariant.EN, bank)
        facts = {(f.issue_id.value, f.element_id): f for f in s.facts}
        for dp in d.decision_points:
            issue, el = dp.gold_best.split("|")
            f = facts.get((issue, el))
            ans = dp.state_after.known.get(dp.gold_best)
            if f is not None and f.reveal.value == "never":
                assert ans.value == "unknown"
            elif f is not None:
                assert ans.value == f.polarity.value
