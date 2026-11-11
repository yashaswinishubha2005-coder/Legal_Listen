"""Family-level splits. A family = a base spec + its minimal-pair siblings; every
language version, dialogue, noisy copy and explanation of a family lands in the
same split, so nothing about a test case is visible in train."""

from __future__ import annotations

from collections import defaultdict

from lexvaani.schemas.issue_library import Triage
from lexvaani.schemas.spec import ScenarioSpec, Variation
from lexvaani.specs.generate import rng_for



def assign_splits(specs: list[ScenarioSpec], seed: int = 13) -> dict[str, str]:
    """Return family_id -> split.

    Strata are (primary issue, variation) for library specs and (template) for
    out-of-library specs. In every stratum one family goes to test; one goes to
    dev in every other stratum (alternating), the rest to train. This keeps
    every issue x variation cell represented in test (~25% test, ~10% dev, ~65% train).
    """
    strata: dict[tuple, list[str]] = defaultdict(list)
    for s in specs:
        if s.minimal_pair is None:
            key = (s.other_template,) if s.other_template else (s.issues[0].value, s.variation.value)
            strata[key].append(s.family_id)
    out: dict[str, str] = {}
    for n, key in enumerate(sorted(strata)):
        fams = sorted(strata[key])
        rng_for(seed, "split", *key).shuffle(fams)
        for i, f in enumerate(fams):
            if i == 0:
                out[f] = "test"
            elif i == 1 and n % 2 == 0 and len(fams) >= 3:
                out[f] = "dev"
            else:
                out[f] = "train"
    return out


def check_no_leakage(spec_split: dict[str, str], specs: list[ScenarioSpec]) -> list[str]:
    """Every spec of a family must be in one split; siblings never cross splits."""
    problems = []
    by_fam: dict[str, set[str]] = defaultdict(set)
    for s in specs:
        by_fam[s.family_id].add(spec_split[s.spec_id])
        if s.minimal_pair:
            base = next(x for x in specs if x.spec_id == s.minimal_pair.base_spec_id)
            if spec_split[base.spec_id] != spec_split[s.spec_id]:
                problems.append(f"{s.spec_id}: sibling in a different split from {base.spec_id}")
    problems += [f"family {f} spans splits {sorted(v)}" for f, v in by_fam.items() if len(v) > 1]
    return problems


def test_subset_membership(spec: ScenarioSpec, variant_is_code_mixed: bool, has_noise: bool) -> list[str]:
    subsets = []
    if spec.minimal_pair is not None or spec.family_id in _families_with_pairs:
        subsets.append("test_contrastive")
    if has_noise:
        subsets.append("test_asr_noise")
    if variant_is_code_mixed and not has_noise:
        subsets.append("test_code_mixed")
    if spec.variation == Variation.OUT_OF_SCOPE:
        subsets.append("test_out_of_scope")
    if spec.triage == Triage.URGENT:
        subsets.append("test_high_risk")
    return subsets


_families_with_pairs: set[str] = set()


def register_pair_families(specs: list[ScenarioSpec]) -> None:
    _families_with_pairs.clear()
    _families_with_pairs.update(s.family_id for s in specs if s.minimal_pair is not None)
