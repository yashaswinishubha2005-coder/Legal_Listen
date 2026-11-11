"""Element cue matching: recognise legal elements the client has already stated in their own words.

Cues live in resources/legallisten/element_cues.yaml (en / kn / hi / romanised). A satisfied cue next to a
negation word (not, never, ಇಲ್ಲ, नहीं, nahi …) is read as contradicted, unless the cue itself is negative.
Used only for issues that are already hypotheses, so a cue never invents a new legal issue on its own.
"""

from __future__ import annotations

import re
from functools import lru_cache

import yaml

from ..knowledge import ROOT, kb
from .rules import cue_pattern

NEG_LATN = r"(?<![a-z])(not|never|no|didn't|don't|doesn't|haven't|hasn't|won't|isn't|wasn't|nahi|nahin|illa|alla)(?![a-z'])"
NEG_INDIC = (r"((?<![\u0900-\u097F])(नहीं|नही|ना|मत)(?![\u0900-\u097F])"
             r"|ಇಲ್ಲ|ಅಲ್ಲ|(?<!ಎ)ಲ್ಲ(?![\u0C80-\u0CFF])|(?<![\u0C80-\u0CFF])ಬೇಡ)")
WINDOW = 22


@lru_cache(maxsize=1)
def cue_table() -> dict[str, dict[str, list]]:
    raw = yaml.safe_load((ROOT / "resources" / "legallisten" / "element_cues.yaml").read_text(encoding="utf-8"))
    k = kb()
    return {key: {"sat": v.get("sat") or [], "con": v.get("con") or []}
            for key, v in raw.items() if key in k.elements and isinstance(v, dict)}


def _norm(s: str) -> str:
    return " " + re.sub(r"\s+", " ", s.lower()).strip() + " "


def _find(text: str, cue) -> tuple[int, int] | None:
    parts = cue if isinstance(cue, list) else [cue]
    span = None
    for p in parts:
        m = re.search(cue_pattern(str(p)), text)
        if not m:
            return None
        span = (m.start(), m.end()) if span is None else (min(span[0], m.start()), max(span[1], m.end()))
    return span


def _is_negative(s: str) -> bool:
    return bool(re.search(NEG_LATN, s) or re.search(NEG_INDIC, s))


def match(sentence: str, key: str) -> tuple[str, str] | None:
    """('satisfied'|'contradicted', cue) for one sentence and element key, or None."""
    cues = cue_table().get(key)
    if not cues:
        return None
    t = _norm(sentence)
    for c in cues["con"]:
        if _find(t, c):
            return "contradicted", str(c)
    hits = []
    for c in cues["sat"]:
        sp = _find(t, c)
        if sp:
            hits.append((" ".join(c) if isinstance(c, list) else str(c), sp))
    if not hits:
        return None
    # a cue that is itself negative ("never shared", "ಉತ್ತರ ಇಲ್ಲ") already carries the meaning
    neg_cues = [h for h in hits if _is_negative(" " + h[0].lower() + " ")]
    if neg_cues:
        return "satisfied", neg_cues[0][0]
    cue_text, (a, b) = max(hits, key=lambda h: h[1][1] - h[1][0])
    window = t[max(0, a - WINDOW): b + WINDOW]
    if _is_negative(window):
        return "contradicted", cue_text
    return "satisfied", cue_text


def elements_in(sentence: str, issues) -> list[tuple[str, str, str]]:
    """All (key, value, cue) found in a sentence for the given issues."""
    out = []
    k = kb()
    for issue in issues:
        for el in k.elements_of(issue):
            r = match(sentence, el.key)
            if r:
                out.append((el.key, r[0], r[1]))
    return out
