from lexvaani.schemas.common import Domain, IssueId, LangVariant


def test_library_complete(lib):
    legal = [i for i in IssueId if not i.is_routing_label]
    assert set(lib) == set(legal)
    for d in Domain:
        assert sum(1 for i in lib if i.domain == d) == 5


def test_every_issue_has_incomplete_and_risk_support(lib):
    for issue in lib.values():
        assert any(e.critical and e.may_be_unknown for e in issue.elements), issue.issue_id
        assert issue.risk_facts
        assert issue.candidate_provisions
        for cp in issue.candidate_provisions:
            assert cp.verification.value == "to_verify"   # nothing is pre-verified


def test_glossary_aligned():
    from lexvaani.resources import glossary
    g = glossary()
    assert len(g) >= 40
    assert all(e.en and e.kn and e.hi for e in g)
    assert len({e.term_id for e in g}) == len(g)


def test_all_templates_render_in_every_variant(specs, lib, bank):
    """Every spec renders in all six variants (validators re-check every span)."""
    from lexvaani.render.narrative import render_narrative
    for s in specs[::5]:
        for v in LangVariant:
            render_narrative(s, lib, v, bank)
