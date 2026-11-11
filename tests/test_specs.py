from lexvaani.schemas.issue_library import URGENT_FLAGS
from lexvaani.schemas.ontology import ElementValue
from lexvaani.schemas.spec import Variation


def test_variation_semantics(specs):
    for s in specs:
        if s.variation == Variation.INCOMPLETE:
            assert any(e.critical and e.gold_value == ElementValue.UNKNOWN for e in s.elements)
        if s.variation == Variation.HIGH_RISK:
            assert set(s.risk_flags) & URGENT_FLAGS and s.triage.value == "urgent"
        if s.variation == Variation.MULTI_ISSUE:
            assert len(s.issues) == 2
        for ev in s.events:
            assert ev.date <= s.conversation_date


def test_regime_routing(specs, lib):
    """Provisions conditioned on the regime must follow the incident date. (Unconditioned
    procedural provisions such as BNSS:144 apply at filing time and are exempt.)"""
    for s in specs:
        if s.law_regime is None:
            continue
        conditioned = {cp.provision_id: cp.when["law_regime"] for i in s.issues if i in lib
                       for cp in lib[i].candidate_provisions if "law_regime" in cp.when}
        for p in s.gold_provisions:
            if p in conditioned:
                assert s.law_regime.value in conditioned[p], (s.spec_id, p)


def test_synthetic_names_only(specs):
    from lexvaani.render.lexicon import lexicon
    pool = {n[0] for g in lexicon()["names"].values() for k in ("m", "f") for n in g[k]}
    for s in specs:
        for p in s.cast:
            assert p.name is None or p.name in pool
