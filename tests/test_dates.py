import datetime as dt

from lexvaani.render.dates import candidates, special_timex
from lexvaani.schemas.common import LangVariant as V


def test_relative_expressions_are_true():
    conv = dt.date(2025, 9, 10)
    assert "yesterday" in candidates(dt.date(2025, 9, 9), conv, V.EN)
    assert candidates(dt.date(2025, 9, 9), conv, V.HI)["yesterday"].core == "कल"
    c = candidates(dt.date(2025, 7, 2), conv, V.KN_EN_LATN)
    assert c["n_months"].value == "2025-07" and c["n_months"].approximate
    assert "yesterday" not in candidates(dt.date(2025, 9, 1), conv, V.EN)


def test_regime_safe_choice():
    from lexvaani.render.dates import choose
    import random
    conv = dt.date(2025, 3, 1)
    for d in (dt.date(2024, 3, 3), dt.date(2024, 9, 3)):
        e = choose(d, conv, V.EN, "hard", random.Random(0), must_resolve_regime=True)
        assert e.value not in ("2024", "PAST_REF")


def test_special_timex():
    conv = dt.date(2025, 1, 31)
    assert special_timex("tomorrow", conv) == ("date", "2025-02-01")
    assert special_timex("tonight", conv)[1] == "2025-01-31TNI"
    assert special_timex("dur_P3W", conv) == ("duration", "P3W")
