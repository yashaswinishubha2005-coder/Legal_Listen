"""Token-level script / language tagging, sample-level variant ID, and the
Code-Mixing Index (Das & Gambäck 2014).

This is a *consistency check* built from the project's own vocabularies, not an
independent LID model. For an independent check plug in IndicLID / fastText
(see qc/external.py); both need model downloads.

CMI = 100 * (1 - max_i w_i / (n - u))  if n > u else 0
  n = tokens, u = language-independent tokens (numbers, punctuation, names,
  acronyms), w_i = tokens tagged with language i.
"""

from __future__ import annotations

import re
import unicodedata
from functools import lru_cache

from lexvaani.render.markup import TOKEN_RE
from lexvaani.schemas.common import LangVariant

V = LangVariant
WORD_RE = re.compile(r"[\wಀ-೿ऀ-ॿ'’-]+")


def script_of(tok: str) -> str:
    for ch in tok:
        cp = ord(ch)
        if 0x0C80 <= cp <= 0x0CFF:
            return "Knda"
        if 0x0900 <= cp <= 0x097F:
            return "Deva"
        if ch.isalpha() and ch.isascii():
            return "Latn"
    return "Zyyy"   # digits / symbols


def _strip_markup(t: str) -> str:
    t = TOKEN_RE.sub(lambda m: m.group("lit") or " ", t)
    return t


@lru_cache(maxsize=1)
def vocabularies() -> dict[str, set[str]]:
    """Latin-script vocabularies harvested from the English and romanized templates."""
    from lexvaani.resources import issue_library, other_scenarios
    import yaml
    from lexvaani.render.lexicon import RES
    voc = {"en": set(), "kn_latn": set(), "hi_latn": set()}
    texts: dict[str, list[str]] = {"en": [], "kn_latn": [], "hi_latn": []}
    key = {V.EN: "en", V.KN_EN_LATN: "kn_latn", V.HI_EN_LATN: "hi_latn"}

    def harvest(d, variant_key):
        if variant_key in key:
            texts[key[variant_key]].append(d)

    for issue in issue_library().values():
        for v in (V.EN, V.KN_EN_LATN, V.HI_EN_LATN):
            harvest(issue.setup[v], v)
            for el in issue.elements:
                harvest(el.satisfied[v], v)
                harvest(el.contradicted[v], v)
            for ev in issue.evidence:
                harvest(ev.held[v], v)
                harvest(ev.missing[v], v)
            for rf in issue.risk_facts:
                harvest(rf.template[v], v)
    lex = yaml.safe_load(open(RES / "lexicon.yaml", encoding="utf-8"))

    def walk(o, vk=None):
        if isinstance(o, dict):
            for k, x in o.items():
                walk(x, k if k in ("en", "kn-en_latn", "hi-en_latn") else vk)
        elif isinstance(o, list):
            for x in o:
                walk(x, vk)
        elif isinstance(o, str) and vk:
            texts[{"en": "en", "kn-en_latn": "kn_latn", "hi-en_latn": "hi_latn"}[vk]].append(o)
    walk(lex)
    for k, ts in texts.items():
        for t in ts:
            for w in WORD_RE.findall(_strip_markup(t)):
                if script_of(w) == "Latn":
                    voc[k].add(w.lower())
    # words appearing in English text are English unless they are core romanized function words
    voc["kn_only"] = voc["kn_latn"] - voc["en"]
    voc["hi_only"] = voc["hi_latn"] - voc["en"]
    return voc


def tag_tokens(text: str, variant: LangVariant, names: set[str] = frozenset()) -> list[tuple[str, str]]:
    voc = vocabularies()
    out = []
    for w in WORD_RE.findall(unicodedata.normalize("NFC", text)):
        sc = script_of(w)
        low = w.lower()
        if sc == "Knda":
            lang = "kn"
        elif sc == "Deva":
            lang = "hi"
        elif sc == "Zyyy" or w.isdigit():
            lang = "univ"
        elif w in names or (w.isupper() and len(w) > 1):
            lang = "univ"
        elif low in voc["kn_only"] and variant in (V.KN_EN_LATN, V.KN_EN_MIXED):
            lang = "kn"
        elif low in voc["hi_only"] and variant == V.HI_EN_LATN:
            lang = "hi"
        elif low in voc["en"]:
            lang = "en"
        elif low in voc["kn_only"]:
            lang = "kn"
        elif low in voc["hi_only"]:
            lang = "hi"
        else:
            lang = "unk"
        out.append((w, lang))
    return out


def cmi(tags: list[tuple[str, str]]) -> float:
    n = len(tags)
    u = sum(1 for _, l in tags if l in ("univ", "unk"))
    if n - u <= 0:
        return 0.0
    counts: dict[str, int] = {}
    for _, l in tags:
        if l not in ("univ", "unk"):
            counts[l] = counts.get(l, 0) + 1
    return round(100.0 * (1 - max(counts.values()) / (n - u)), 2)


def predict_variant(text: str) -> LangVariant:
    """Heuristic sample-level variant identification from script + vocabulary mix."""
    toks = WORD_RE.findall(text)
    sc = [script_of(t) for t in toks]
    knda, deva, latn = sc.count("Knda"), sc.count("Deva"), sc.count("Latn")
    tot = max(1, knda + deva + latn)
    if deva / tot > 0.5:
        return V.HI
    if knda / tot > 0.5:
        return V.KN if latn / tot < 0.08 else V.KN_EN_MIXED
    if knda > 0:
        return V.KN_EN_MIXED
    voc = vocabularies()
    lw = [t.lower() for t, s in zip(toks, sc) if s == "Latn"]
    kn = sum(w in voc["kn_only"] for w in lw)
    hi = sum(w in voc["hi_only"] for w in lw)
    if kn == hi == 0 or max(kn, hi) / max(1, len(lw)) < 0.1:
        return V.EN
    return V.KN_EN_LATN if kn >= hi else V.HI_EN_LATN
