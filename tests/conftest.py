import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))


@pytest.fixture(scope="session")
def lib():
    from lexvaani.resources import issue_library
    return issue_library()


@pytest.fixture(scope="session")
def bank():
    from lexvaani.resources import other_scenarios
    return other_scenarios()


@pytest.fixture(scope="session")
def specs(lib, bank):
    from lexvaani.specs.generate import generate_all
    return generate_all(lib, bank, seed=13, per_cell=2, others_per_variation=16)
