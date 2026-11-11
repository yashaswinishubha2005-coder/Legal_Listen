"""Temporal expression rendering with TIMEX3-style gold values.

Expressions are chosen so that they are TRUE for the hidden event date relative
to the conversation date, and the gold value is what a careful annotator would
resolve from the text alone (e.g. "2 months back" -> month, approximate).
"""

from __future__ import annotations

import datetime as dt
import random
from dataclasses import dataclass

from lexvaani.schemas.common import LangVariant

from .lexicon import HINDI, KANNADA, lexicon, number_word

V = LangVariant
REGIME_CUTOFF = dt.date(2024, 7, 1)


@dataclass
class DateExpr:
    pre: str
    core: str
    post: str
    style: str
    value: str
    approximate: bool = False
    type: str = "date"


def d(s: str) -> dt.date:
    return dt.date.fromisoformat(s)


def _month_name(m: int, variant: LangVariant) -> str:
    months = lexicon()["months"]
    if variant in (V.KN,):
        return months["kn"][m - 1]
    if variant == V.HI:
        return months["hi"][m - 1]
    return months["en"][m - 1]


def _abs_day(ev: dt.date, conv: dt.date, v: LangVariant, with_year: bool) -> DateExpr:
    mon = _month_name(ev.month, v)
    y = f" {ev.year}" if with_year else ""
    yc = f", {ev.year}" if with_year else ""
    val = ev.isoformat()
    if v == V.EN:
        return DateExpr("on ", f"{ev.day} {mon}{y}", "", "abs_day", val)
    if v in (V.KN, V.KN_EN_MIXED):
        return DateExpr("", f"{mon} {ev.day}{yc}", " ರಂದು", "abs_day", val)
    if v == V.KN_EN_LATN:
        return DateExpr("", f"{mon} {ev.day}{yc}", " ralli", "abs_day", val)
    if v == V.HI:
        return DateExpr("", f"{ev.day} {mon}{y}", " को", "abs_day", val)
    return DateExpr("", f"{ev.day} {mon}{y}", " ko", "abs_day", val)


def _abs_month(ev: dt.date, v: LangVariant) -> DateExpr:
    mon = _month_name(ev.month, v)
    val = f"{ev.year:04d}-{ev.month:02d}"
    core = f"{mon} {ev.year}"
    post = {V.EN: "", V.KN: " ರಲ್ಲಿ", V.KN_EN_MIXED: " ರಲ್ಲಿ", V.KN_EN_LATN: " alli",
            V.HI: " में", V.HI_EN_LATN: " mein"}[v]
    return DateExpr("in " if v == V.EN else "", core, post, "abs_month", val)


SIMPLE = {
    "today": {V.EN: "today", V.KN: "ಇವತ್ತು", V.KN_EN_MIXED: "ಇವತ್ತು", V.KN_EN_LATN: "ivattu",
              V.HI: "आज", V.HI_EN_LATN: "aaj"},
    "yesterday": {V.EN: "yesterday", V.KN: "ನಿನ್ನೆ", V.KN_EN_MIXED: "ನಿನ್ನೆ", V.KN_EN_LATN: "ninne",
                  V.HI: "कल", V.HI_EN_LATN: "kal"},
    "day_before": {V.EN: "the day before yesterday", V.KN: "ಮೊನ್ನೆ", V.KN_EN_MIXED: "ಮೊನ್ನೆ",
                   V.KN_EN_LATN: "monne", V.HI: "परसों", V.HI_EN_LATN: "parson"},
    "last_week": {V.EN: "last week", V.KN: "ಹೋದ ವಾರ", V.KN_EN_MIXED: "ಹೋದ week",
                  V.KN_EN_LATN: "hoda vaara", V.HI: "पिछले हफ़्ते", V.HI_EN_LATN: "pichhle hafte"},
    "last_year": {V.EN: "last year", V.KN: "ಹೋದ ವರ್ಷ", V.KN_EN_MIXED: "ಹೋದ year",
                  V.KN_EN_LATN: "hoda varsha", V.HI: "पिछले साल", V.HI_EN_LATN: "pichhle saal"},
    "vague": {V.EN: "some time back", V.KN: "ಸ್ವಲ್ಪ ದಿನದ ಹಿಂದೆ", V.KN_EN_MIXED: "ಸ್ವಲ್ಪ ದಿನದ ಹಿಂದೆ",
              V.KN_EN_LATN: "swalpa dinada hinde", V.HI: "कुछ समय पहले", V.HI_EN_LATN: "kuch time pehle"},
}


def _n_ago(n: int, unit: str, v: LangVariant) -> str:
    w = number_word(n, v) if v != V.KN_EN_MIXED else number_word(n, V.KN)
    if v == V.EN:
        if n == 1:
            return {"day": "a day ago", "month": "a month ago"}[unit]
        return f"{w} {unit}s ago" if unit == "day" else f"{w} months back"
    table = {
        V.KN: {"day": "ದಿನದ ಹಿಂದೆ", "month": "ತಿಂಗಳ ಹಿಂದೆ"},
        V.KN_EN_MIXED: {"day": "ದಿನದ ಹಿಂದೆ", "month": "months ಹಿಂದೆ"},
        V.KN_EN_LATN: {"day": "dina hinde", "month": "tingala hinde"},
        V.HI: {"day": "दिन पहले", "month": "महीने पहले"},
        V.HI_EN_LATN: {"day": "din pehle", "month": "mahine pehle"},
    }
    return f"{w} {table[v][unit]}"


def _festival(ev: dt.date, conv: dt.date, v: LangVariant) -> DateExpr | None:
    fest = lexicon()["festivals"]
    keys = ["ugadi", "sankranti"]   # same festival in every language so all versions share one gold value
    for k in keys:
        f = fest[k]
        # most recent occurrence strictly before the conversation date
        occ = sorted(d(x) for x in f["dates"].values() if d(x) < conv)
        if not occ:
            continue
        last = occ[-1]
        if abs((ev - last).days) <= 7:
            name = {V.EN: f["en"], V.KN: f["kn"], V.KN_EN_MIXED: f["latn"], V.KN_EN_LATN: f["latn"],
                    V.HI: f["hi"], V.HI_EN_LATN: f["latn"]}[v]
            if v == V.EN:
                return DateExpr("around ", f"last {name}", "", "festival", last.isoformat(), True)
            if v in (V.KN, V.KN_EN_MIXED):
                post = " ಟೈಮಲ್ಲಿ" if v == V.KN else " time ಅಲ್ಲಿ"
                return DateExpr("", f"ಹೋದ {name}", post, "festival", last.isoformat(), True)
            if v == V.KN_EN_LATN:
                return DateExpr("", f"hoda {name}", " time alli", "festival", last.isoformat(), True)
            if v == V.HI:
                return DateExpr("", f"पिछली {name}", " के आसपास", "festival", last.isoformat(), True)
            return DateExpr("", f"pichhli {name}", " ke aaspaas", "festival", last.isoformat(), True)
    return None


def candidates(ev: dt.date, conv: dt.date, v: LangVariant) -> dict[str, DateExpr]:
    delta = (conv - ev).days
    out: dict[str, DateExpr] = {}
    if delta < 0:
        raise ValueError("event after conversation date")
    if delta == 0:
        out["today"] = DateExpr("", SIMPLE["today"][v], "", "today", ev.isoformat())
    if delta == 1:
        out["yesterday"] = DateExpr("", SIMPLE["yesterday"][v], "", "yesterday", ev.isoformat())
    if delta == 2:
        out["day_before"] = DateExpr("", SIMPLE["day_before"][v], "", "day_before", ev.isoformat())
    if 3 <= delta <= 6:
        out["n_days"] = DateExpr("", _n_ago(delta, "day", v), "", "n_days", ev.isoformat())
    if 7 <= delta <= 13:
        y, w, _ = ev.isocalendar()
        cy, cw, _ = conv.isocalendar()
        if (dt.date.fromisocalendar(cy, cw, 1) - dt.date.fromisocalendar(y, w, 1)).days == 7:
            out["last_week"] = DateExpr("", SIMPLE["last_week"][v], "", "last_week", f"{y}-W{w:02d}")
    months = (conv.year * 12 + conv.month) - (ev.year * 12 + ev.month)
    if 1 <= months <= 6 and delta >= 20:
        out["n_months"] = DateExpr("", _n_ago(months, "month", v), "", "n_months",
                                   f"{ev.year:04d}-{ev.month:02d}", True)
    if ev.year == conv.year - 1:
        out["last_year"] = DateExpr("", SIMPLE["last_year"][v], "", "last_year", f"{ev.year:04d}")
    fest = _festival(ev, conv, v)
    if fest:
        out["festival"] = fest
    out["abs_day"] = _abs_day(ev, conv, v, with_year=True)
    if ev.year == conv.year:
        out["abs_day_noyear"] = _abs_day(ev, conv, v, with_year=False)
    out["abs_month"] = _abs_month(ev, v)
    if delta >= 30:
        out["vague"] = DateExpr("", SIMPLE["vague"][v], "", "vague", "PAST_REF", True)
    return out


PREFS = {
    "easy": ["abs_day", "abs_month", "today", "yesterday"],
    "medium": ["yesterday", "n_days", "abs_day_noyear", "last_week", "n_months", "abs_day", "abs_month", "last_year"],
    "hard": ["festival", "yesterday", "n_months", "day_before", "n_days", "last_week", "vague", "last_year", "abs_day_noyear", "today"],
}


def choose(ev: dt.date, conv: dt.date, v: LangVariant, difficulty: str, rng: random.Random,
           style: str | None = None, must_resolve_regime: bool = False) -> DateExpr:
    """Pick an expression. ``style`` (when given and valid) forces the style so all
    language versions of a spec use the same temporal granularity."""
    cands = candidates(ev, conv, v)
    if must_resolve_regime:
        cands = {k: c for k, c in cands.items() if _resolves_regime(c, ev)}
    if style and style in cands:
        return cands[style]
    prefs = [p for p in PREFS[difficulty] if p in cands]
    if not prefs:
        prefs = list(cands)
    weights = [len(prefs) - i for i in range(len(prefs))]
    return cands[rng.choices(prefs, weights=weights, k=1)[0]]


def choose_style(ev: dt.date, conv: dt.date, difficulty: str, rng: random.Random,
                 must_resolve_regime: bool = False) -> str:
    """Language-independent style choice (validity does not depend on language)."""
    expr = choose(ev, conv, V.EN, difficulty, rng, must_resolve_regime=must_resolve_regime)
    return expr.style


def _resolves_regime(c: DateExpr, ev: dt.date) -> bool:
    """Can the old/new criminal-law regime be decided from this expression?"""
    if c.value == "PAST_REF":
        return False
    if len(c.value) == 4:   # year only
        return int(c.value) != 2024
    if len(c.value) == 7 and c.value[4] == "-":   # month
        return c.value != "2024-07" and not (c.value.startswith("2024-0") and False)
    return True


def special_timex(rel: str, conv: dt.date) -> tuple[str, str]:
    """Values for literal time words tagged in templates: (type, value)."""
    if rel == "today":
        return "date", conv.isoformat()
    if rel == "tonight":
        return "time", f"{conv.isoformat()}TNI"
    if rel == "tomorrow":
        return "date", (conv + dt.timedelta(days=1)).isoformat()
    if rel == "now":
        return "date", "PRESENT_REF"
    if rel == "this_morning":
        return "time", f"{conv.isoformat()}TMO"
    if rel == "last_night":
        return "time", f"{(conv - dt.timedelta(days=1)).isoformat()}TNI"
    if rel == "every_month":
        return "set", "P1M"
    if rel.startswith("dur_"):
        return "duration", rel[4:]
    if rel == "hour_ago":
        return "time", f"{conv.isoformat()}TXX"
    if rel == "next_week":
        y, w, _ = (conv + dt.timedelta(days=7)).isocalendar()
        return "date", f"{y}-W{w:02d}"
    if rel == "this_week":
        y, w, _ = conv.isocalendar()
        return "date", f"{y}-W{w:02d}"
    if rel == "every_day":
        return "set", "P1D"
    if rel == "past_ref":
        return "date", "PAST_REF"
    raise ValueError(f"unknown TIMEX tag {rel}")


__all__ = ["DateExpr", "candidates", "choose", "choose_style", "special_timex", "REGIME_CUTOFF", "KANNADA"]
