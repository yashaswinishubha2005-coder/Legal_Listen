"""Lexicon access: names, role nouns with case forms, pronouns, numbers, items."""

from __future__ import annotations

import random
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from lexvaani.schemas.common import LangVariant

ROOT = Path(__file__).resolve().parents[3]
RES = ROOT / "resources"

V = LangVariant
NAME_SCRIPT = {V.EN: 0, V.KN_EN_LATN: 0, V.HI_EN_LATN: 0, V.KN: 1, V.KN_EN_MIXED: 1, V.HI: 2}
NUM_COL = {V.EN: 0, V.KN: 1, V.KN_EN_MIXED: 1, V.KN_EN_LATN: 2, V.HI: 3, V.HI_EN_LATN: 4}
HINDI = {V.HI, V.HI_EN_LATN}
KANNADA = {V.KN, V.KN_EN_LATN, V.KN_EN_MIXED}


@lru_cache(maxsize=1)
def lexicon() -> dict[str, Any]:
    with open(RES / "lexicon.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def variant_entry(table: dict, variant: LangVariant, speaker_gender: str | None = None) -> Any:
    """Look up a variant, preferring '<variant>_m' for male speakers (Hindi agreement)."""
    if speaker_gender == "male" and f"{variant.value}_m" in table:
        return table[f"{variant.value}_m"]
    return table[variant.value]


def norm_case(case: str | None, variant: LangVariant) -> str:
    case = case or "nom"
    if variant in HINDI:
        return "gen_pl" if case == "gen" else case
    return "gen" if case.startswith("gen") else case


def case_form(form: Any, variant: LangVariant, case: str, name: str | None) -> tuple[str, str] | None:
    """Return (span_text, suffix) for a role-noun form in a case, or None if unavailable."""
    case = norm_case(case, variant)
    if isinstance(form, str):
        base = form.replace("{N}", name or "").strip()
        marker = lexicon()["case_markers"][variant.value].get(case)
        if marker is None:
            return None
        return base, marker
    value = form.get(case)
    if value is None and case == "erg" and variant not in HINDI:
        value = form.get("nom")
    if value is None:
        return None
    if isinstance(value, list):
        return value[0].replace("{N}", name or ""), value[1]
    return value.replace("{N}", name or ""), ""


def noun_forms(noun: str, gender: str, variant: LangVariant) -> tuple[Any, Any]:
    entry = lexicon()["role_nouns"][noun]
    g = {"male": "m", "female": "f"}.get(gender, "any")
    for key in (g, "any", "m", "f"):
        block = entry.get(key)
        if block and variant.value in block:
            bare, named = block[variant.value]
            return bare, named
    raise KeyError(f"role noun {noun!r} has no forms for {variant.value}")


def noun_kin(noun: str, gender: str) -> str | None:
    entry = lexicon()["role_nouns"][noun]
    g = {"male": "m", "female": "f"}.get(gender, "any")
    block = entry.get(g) or {}
    return block.get("kin") or entry.get("kin")


def noun_surface_term(noun: str, variant: LangVariant) -> str | None:
    return (lexicon()["role_nouns"][noun].get("surface") or {}).get(variant.value)


def pronoun(variant: LangVariant, gender: str, case: str) -> str:
    table = lexicon()["pronouns"]["honorific"][variant.value]
    if variant == V.EN:
        table = table[{"male": "m", "female": "f"}.get(gender, "n")]
    case = norm_case(case, variant)
    return table.get(case) or table["nom"]


def name_in_script(name_triplet: list[str], variant: LangVariant) -> str:
    return name_triplet[NAME_SCRIPT[variant]]


def pick_name(rng: random.Random, group: str, gender: str, exclude: set[str]) -> list[str]:
    pool = lexicon()["names"][group]["m" if gender == "male" else "f"]
    choices = [n for n in pool if n[0] not in exclude] or pool
    return rng.choice(choices)


def number_word(n: int, variant: LangVariant) -> str:
    return lexicon()["numbers"][n][NUM_COL[variant]]


def money_unit(unit: str, variant: LangVariant) -> str:
    return lexicon()["money_units"][unit][NUM_COL[variant]]


def indian_grouping(n: int) -> str:
    s = str(n)
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return ",".join(parts + [tail])


def render_amount(amount: int, variant: LangVariant, style: str) -> str:
    rupees = money_unit("rupees", variant)
    if style == "digits":
        if variant == V.EN:
            return f"₹{indian_grouping(amount)}"
        return f"{indian_grouping(amount)} {rupees}"
    if amount % 100000 == 0:
        n, unit = amount // 100000, "lakh"
    else:
        n, unit = amount // 1000, "thousand"
    return f"{number_word(n, variant)} {money_unit(unit, variant)} {rupees}"


def item(key: str) -> dict[str, Any]:
    return lexicon()["items"][key]


def place(key: str) -> dict[str, Any]:
    return lexicon()["places"][key]


def phrase_bank(group: str, name: str) -> dict:
    return lexicon()[group][name]
