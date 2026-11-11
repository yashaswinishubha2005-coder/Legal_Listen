from collections import defaultdict


def test_family_split_no_leakage(specs):
    from lexvaani.splits.make_splits import assign_splits, check_no_leakage
    fam = assign_splits(specs, seed=13)
    spec_split = {s.spec_id: fam[s.family_id] for s in specs}
    assert check_no_leakage(spec_split, specs) == []
    by_fam = defaultdict(set)
    for s in specs:
        by_fam[s.family_id].add(spec_split[s.spec_id])
    assert all(len(v) == 1 for v in by_fam.values())


def test_siblings_share_split_and_differ_in_one_fact(specs):
    from lexvaani.splits.make_splits import assign_splits
    fam = assign_splits(specs, seed=13)
    by_id = {s.spec_id: s for s in specs}
    sibs = [s for s in specs if s.minimal_pair]
    assert sibs
    for s in sibs:
        base = by_id[s.minimal_pair.base_spec_id]
        assert fam[s.family_id] == fam[base.family_id] and s.family_id == base.family_id
        changed = 0
        changed += s.law_regime != base.law_regime
        changed += [f.polarity for f in s.facts] != [f.polarity for f in base.facts]
        changed += [e.availability for e in s.evidence] != [e.availability for e in base.evidence]
        changed += s.risk_flags != base.risk_flags
        assert changed >= 1


def test_every_cell_in_test(specs):
    from lexvaani.splits.make_splits import assign_splits
    fam = assign_splits(specs, seed=13)
    cells = {(s.issues[0].value, s.variation.value) for s in specs if not s.other_template and not s.minimal_pair}
    test_cells = {(s.issues[0].value, s.variation.value) for s in specs
                  if not s.other_template and not s.minimal_pair and fam[s.family_id] == "test"}
    assert cells == test_cells
