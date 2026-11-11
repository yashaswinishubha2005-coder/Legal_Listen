"""Rule-based ASR-noise channel with label-preserving re-alignment.

The text is tokenised on whitespace; every gold span is a set of whole tokens or
lies inside one token. Operations are applied token-by-token and each output
token keeps a pointer to its source token, so gold spans are re-projected
exactly. A span whose tokens are all dropped is removed and listed in
``NoiseInfo.dropped_mentions``; a span is never guessed.

Operations (rates scale with ``level``):
  phonetic   language-specific confusions (v/w, sh/s, ಷ/ಶ, ण/न, aspirates ...)
  drop       delete a short function word / filler
  merge      join two adjacent tokens (wrong word boundary)
  split      split a long token in two
  number     swap confusable number words (fifty<->fifteen, ಐವತ್ತು<->ಹದಿನೈದು ...)
  script     transliteration inconsistency in code-mixed text (Latin<->Kannada for loanwords)
"""

from __future__ import annotations

import random
import re
from dataclasses import dataclass

from lexvaani.schemas.common import LangVariant, Span
from lexvaani.schemas.sample import NarrativeSample, NoiseInfo

V = LangVariant

PHONETIC = {
    "latin": [("v", "w"), ("w", "v"), ("sh", "s"), ("ph", "f"), ("th", "t"), ("aa", "a"), ("ee", "i"),
              ("oo", "u"), ("z", "j"), ("ks", "x")],
    "knda": [("ಷ", "ಶ"), ("ಶ", "ಸ"), ("ಳ", "ಲ"), ("ಣ", "ನ"), ("ಖ", "ಕ"), ("ಘ", "ಗ"), ("ಢ", "ಡ"), ("ಥ", "ತ")],
    "deva": [("ण", "न"), ("ष", "श"), ("श", "स"), ("ज़", "ज"), ("फ़", "फ"), ("ढ़", "ड़"), ("क्ष", "छ"), ("ं", "")],
}
NUMBER_SWAPS = {
    "fifty": "fifteen", "fifteen": "fifty", "forty": "fourteen", "fourteen": "forty",
    "eighty": "eighteen", "eighteen": "eighty", "sixty": "sixteen", "thirty": "thirteen",
    "ಐವತ್ತು": "ಹದಿನೈದು", "ಹದಿನೈದು": "ಐವತ್ತು", "ನಲವತ್ತು": "ಹದಿನಾಲ್ಕು", "ಹದಿನಾಲ್ಕು": "ನಲವತ್ತು",
    "ಎಂಬತ್ತು": "ಹದಿನೆಂಟು", "ಹದಿನೆಂಟು": "ಎಂಬತ್ತು",
    "aivattu": "hadinaidu", "hadinaidu": "aivattu", "nalavattu": "hadinaalku", "hadinaalku": "nalavattu",
    "पचास": "पंद्रह", "पंद्रह": "पचास", "चालीस": "चौदह", "चौदह": "चालीस", "अस्सी": "अठारह", "अठारह": "अस्सी",
    "pachaas": "pandrah", "pandrah": "pachaas", "chaalees": "chaudah", "chaudah": "chaalees",
}
DROPPABLE = {"the", "a", "an", "and", "to", "of", "so", "that", "ಅಂತ", "ಮತ್ತು", "ಅದು", "antha", "mattu",
             "और", "कि", "तो", "ने", "aur", "ki", "to", "ne", "hi", "bhi", "ಕೂಡ", "kooda", "भी"}
LOANWORD_KN = {"police": "ಪೊಲೀಸ್", "bank": "ಬ್ಯಾಂಕ್", "phone": "ಫೋನ್", "mobile": "ಮೊಬೈಲ್", "complaint": "ಕಂಪ್ಲೇಂಟ್",
               "station": "ಸ್ಟೇಷನ್", "money": "ಮನಿ", "account": "ಅಕೌಂಟ್", "message": "ಮೆಸೇಜ್", "app": "ಆಪ್",
               "case": "ಕೇಸ್", "land": "ಲ್ಯಾಂಡ್", "house": "ಹೌಸ್", "report": "ರಿಪೋರ್ಟ್"}
LOANWORD_KN_REV = {v: k for k, v in LOANWORD_KN.items()}

LEVELS = {"low": 0.04, "medium": 0.08, "high": 0.14}


@dataclass
class Tok:
    text: str
    src: list[int]          # source token indices
    start: int = 0
    end: int = 0


def tokenize(text: str) -> list[tuple[int, int]]:
    return [(m.start(), m.end()) for m in re.finditer(r"\S+", text)]


def _script(variant: LangVariant) -> str:
    return {V.KN: "knda", V.KN_EN_MIXED: "knda", V.HI: "deva"}.get(variant, "latin")


def _phonetic(word: str, rules, rng) -> str:
    cands = [(a, b) for a, b in rules if a in word]
    if not cands:
        return word
    a, b = rng.choice(cands)
    i = word.find(a)
    return word[:i] + b + word[i + len(a):]


def corrupt(sample: NarrativeSample, level: str = "medium", seed: int = 0) -> NarrativeSample:
    rng = random.Random(f"{sample.sample_id}|{level}|{seed}")
    rate = LEVELS[level]
    text = sample.text
    spans = tokenize(text)
    words = [text[s:e] for s, e in spans]
    out: list[Tok] = []
    ops: list[dict] = []
    i = 0
    script = _script(sample.lang_variant)
    while i < len(words):
        w = words[i]
        core = w.strip(".,?!।")
        def hit(weight: float) -> bool:
            return rng.random() < rate * weight
        if core.lower() in NUMBER_SWAPS and hit(3.0):
            sw = NUMBER_SWAPS[core.lower()]
            new = w.replace(core, sw if core.islower() else sw.capitalize())
            out.append(Tok(new, [i])); ops.append({"op": "number", "token": i, "from": w, "to": new}); i += 1
            continue
        if core in DROPPABLE and hit(1.5):
            ops.append({"op": "drop", "token": i, "from": w}); i += 1
            continue
        if len(core) > 3 and hit(1.0):
            new = _phonetic(w, PHONETIC[script] + (PHONETIC["latin"] if sample.lang_variant.is_code_mixed else []), rng)
            if new != w:
                out.append(Tok(new, [i])); ops.append({"op": "phonetic", "token": i, "from": w, "to": new}); i += 1
                continue
        if i + 1 < len(words) and not re.search(r"[.?!।,]$", w) and hit(0.4):
            new = w + words[i + 1]
            out.append(Tok(new, [i, i + 1])); ops.append({"op": "merge", "token": i, "from": f"{w} {words[i+1]}", "to": new})
            i += 2
            continue
        if len(core) >= 8 and w.isalpha() and hit(0.3):
            k = len(w) // 2
            out.append(Tok(w[:k], [i])); out.append(Tok(w[k:], [i]))
            ops.append({"op": "split", "token": i, "from": w, "to": f"{w[:k]} {w[k:]}"}); i += 1
            continue
        if sample.lang_variant == V.KN_EN_MIXED and (core.lower() in LOANWORD_KN or core in LOANWORD_KN_REV) and hit(2.0):
            rep = LOANWORD_KN.get(core.lower()) or LOANWORD_KN_REV[core]
            new = w.replace(core, rep)
            out.append(Tok(new, [i])); ops.append({"op": "script", "token": i, "from": w, "to": new}); i += 1
            continue
        out.append(Tok(w, [i]))
        i += 1
    # rebuild text
    pos = 0
    parts = []
    for t in out:
        if parts:
            parts.append(" ")
            pos += 1
        t.start, t.end = pos, pos + len(t.text)
        parts.append(t.text)
        pos = t.end
    new_text = "".join(parts)
    src_to_out: dict[int, list[Tok]] = {}
    for t in out:
        for s in t.src:
            src_to_out.setdefault(s, []).append(t)
    noisy_id = f"{sample.sample_id}_asr{level[0]}"
    dropped: list[str] = []

    def project(sp: Span, ref: str) -> Span | None:
        toks = [k for k, (s, e) in enumerate(spans) if s < sp.end and e > sp.start]
        mapped = [t for k in toks for t in src_to_out.get(k, [])]
        if not mapped:
            dropped.append(ref)
            return None
        # exact sub-token span when the token was untouched
        if len(toks) == 1 and len(mapped) == 1 and mapped[0].text == words[toks[0]]:
            s0, _ = spans[toks[0]]
            a = mapped[0].start + (sp.start - s0)
            b = a + (sp.end - sp.start)
        else:
            a, b = min(t.start for t in mapped), max(t.end for t in mapped)
            # trim punctuation that the original span did not include
            while b > a and new_text[b - 1] in ".,?!।" and not sp.text.endswith(new_text[b - 1]):
                b -= 1
        seg = new_text[a:b].strip()
        if not seg:
            dropped.append(ref)
            return None
        lead = len(new_text[a:b]) - len(new_text[a:b].lstrip())
        a += lead
        return Span(unit_id=noisy_id, start=a, end=a + len(seg), text=seg)

    ann = sample.annotations
    data = ann.model_dump()

    def remap_list(items, key, ref_key):
        res = []
        for it in items:
            sp = project(Span(**it[key]), it.get(ref_key, key))
            if sp is None:
                continue
            it = dict(it, **{key: sp.model_dump()})
            res.append(it)
        return res

    data["entities"] = remap_list(data["entities"], "span", "mention_id")
    kept_m = {m["mention_id"] for m in data["entities"]}
    data["coref"] = [dict(c, mention_ids=[m for m in c["mention_ids"] if m in kept_m]) for c in data["coref"]]
    data["coref"] = [c for c in data["coref"] if c["mention_ids"]]
    evs = []
    for e in data["events"]:
        sp = project(Span(**e["trigger"]), e["event_id"])
        if sp is None:
            continue
        e = dict(e, trigger=sp.model_dump(),
                 arguments=[a for a in e["arguments"] if a.get("mention_id") is None or a["mention_id"] in kept_m])
        evs.append(e)
    data["events"] = evs
    tx = []
    for t in data["timexes"]:
        if t.get("span"):
            sp = project(Span(**t["span"]), t["id"])
            if sp is None:
                continue
            t = dict(t, span=sp.model_dump())
        tx.append(t)
    data["timexes"] = tx
    kept_t = {t["id"] for t in tx}
    data["events"] = [dict(e, time_id=e["time_id"] if e["time_id"] in kept_t else None) for e in data["events"]]
    facts = []
    for f in data["facts"]:
        sp = project(Span(**f["span"]), f["claim_id"])
        if sp is None:
            continue
        f = dict(f, span=sp.model_dump(),
                 hedge_cues=[x.model_dump() for x in (project(Span(**h), f["claim_id"] + "/hedge") for h in f["hedge_cues"]) if x],
                 negation_cues=[x.model_dump() for x in (project(Span(**h), f["claim_id"] + "/neg") for h in f["negation_cues"]) if x])
        facts.append(f)
    data["facts"] = facts
    # graph spans are not re-projected: the noisy sample keeps the clean graph structure (T8 scored on clean text)
    data["case_graph"] = _strip_graph_spans(data["case_graph"])
    n_src = max(len(words), 1)
    wer = sum(1 for o in ops if o["op"] in ("drop", "phonetic", "number", "script")) + \
        sum(2 for o in ops if o["op"] in ("merge",)) + sum(1 for o in ops if o["op"] == "split")
    return NarrativeSample.model_validate({
        **sample.model_dump(exclude={"annotations", "noise", "sample_id", "text"}),
        "sample_id": noisy_id, "text": new_text, "annotations": data,
        "noise": NoiseInfo(clean_sample_id=sample.sample_id, ops=ops, word_error_rate=round(min(1.0, wer / n_src), 4),
                           dropped_mentions=sorted(set(dropped))).model_dump(),
    })


def _strip_graph_spans(g: dict) -> dict:
    g = dict(g)
    nodes = []
    for n in g["nodes"]:
        n = dict(n, source_spans=[])
        for k in ("trigger",):
            if n.get(k):
                n[k] = None
        for k in ("hedge_cues", "negation_cues"):
            if k in n:
                n[k] = []
        nodes.append(n)
    g["nodes"] = nodes
    g["edges"] = [dict(e, source_spans=[]) for e in g["edges"]]
    return g
