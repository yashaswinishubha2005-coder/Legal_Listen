"""Rule-based multilingual NLU: language/script detection, dates, money, people, answer types
(yes / no / don't know), corrections, re-explanation requests and risk cues.

Works for English, Kannada, Hindi and romanised Kanglish / Hinglish. It is deliberately
conservative: anything it cannot read confidently is left for a clarifying question.
"""

from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass, field
from functools import lru_cache

from lexvaani.qc.langid import predict_variant
from lexvaani.render.lexicon import lexicon

from ..knowledge import kb

SENT_SPLIT = re.compile(r"(?<=[.!?।])\s+|\n+")


def sentences(text: str) -> list[str]:
    return [s.strip() for s in SENT_SPLIT.split(text) if s and s.strip()]


def detect_variant(text: str) -> str:
    try:
        return predict_variant(text).value
    except Exception:  # noqa: BLE001 - never fail on odd input
        return "en"


def base_lang(variant: str) -> str:
    return "kn" if variant.startswith("kn") else "hi" if variant.startswith("hi") else "en"


def _norm(text: str) -> str:
    return " " + re.sub(r"\s+", " ", text.lower()).strip() + " "


INDIC = "\u0C80-\u0CFF\u0900-\u097F"


def cue_pattern(c: str) -> str:
    """Latin cues match whole words; Kannada / Devanagari cues must start a word (suffixes allowed)."""
    c = c.lower()
    if c.endswith("*") and len(c) > 3:          # prefix cue for agglutinative romanised words: "kadd*"
        return r"(?<![a-z])" + re.escape(c[:-1])
    if re.match(r"^[a-z' -]+$", c):
        if len(c) >= 5:                          # longer words also match inflected forms: document → documentation
            return r"(?<![a-z])" + re.escape(c)
        return r"(?<![a-z])" + re.escape(c) + r"(?![a-z])"
    if re.match(rf"^[{INDIC}]", c):
        return rf"(?<![{INDIC}])" + re.escape(c)
    return re.escape(c)


def _has(text: str, cues) -> bool:
    t = _norm(text)
    return any(re.search(cue_pattern(c), t) for c in cues if c)


# ----------------------------------------------------------------- answer types
DONT_KNOW = ["don't know", "dont know", "do not know", "not sure", "no idea", "can't say", "cannot say",
             "ಗೊತ್ತಿಲ್ಲ", "ಗೊತ್ತಾಗ್ತಿಲ್ಲ", "ಖಚಿತವಿಲ್ಲ", "gottilla", "gotilla", "gothilla", "goth illa",
             "पता नहीं", "मालूम नहीं", "नहीं पता", "pata nahi", "pata nahin", "maloom nahi", "nahi pata"]
YES = ["yes", "yeah", "yep", "yes,", "correct", "right", "true", "sure", "haan", "ha ji", "haanji", "ji haan",
       "houdu", "haudu", "hauda", "ಹೌದು", "ಹೂಂ", "ಹೌದ", "हाँ", "हां", "जी हाँ", "जी", "सही"]
NO = ["no", "nope", "not at all", "never", "nahi", "nahin", "illa", "ಇಲ್ಲ", "ಇಲ್ಲಾ", "ಅಲ್ಲ", "नहीं", "नही", "ना",
      "जी नहीं", "bilkul nahi"]
CORRECTION = ["sorry, i said", "i said that wrong", "i said it wrong", "let me correct", "correction", "i mean",
              "i meant", "actually it was", "actually it is", "not that,", "ತಪ್ಪಾಗಿ ಹೇಳ್ದೆ", "ತಪ್ಪಾಗಿ ಹೇಳಿದೆ",
              "ಇಲ್ಲ ಇಲ್ಲ", "ಸರಿಯಾಗಿ ಹೇಳ್ತೀನಿ", "tappaagi helde", "tappagi helde", "illa illa", "sariyaagi heltini",
              "गलत बोला", "गलत कहा", "सही बताती", "सही बताता", "galat bola", "galat kaha", "sahi batati", "sahi batata",
              "nahi ruko", "नहीं रुकिए"]
REEXPLAIN = ["don't understand", "dont understand", "did not understand", "didn't understand", "not understand",
             "what do you mean", "explain again", "explain simply", "simpler", "in simple words", "what does that mean",
             "meaning?", "ಅರ್ಥ ಆಗ್ಲಿಲ್ಲ", "ಅರ್ಥ ಆಗಲಿಲ್ಲ", "ಅರ್ಥವಾಗಲಿಲ್ಲ", "ಅಂದ್ರೆ ಏನು", "ಸುಲಭವಾಗಿ ಹೇಳಿ", "artha aaglilla",
             "artha agalilla", "andre enu", "समझ नहीं आया", "समझ में नहीं आया", "मतलब क्या", "आसान भाषा", "samajh nahi aaya",
             "matlab kya", "simple mein", "simple aagi"]
SHORT_REPLY = 12      # words; longer messages are narratives, not bare answers or meta-requests
SAFE_NO = ["not safe", "unsafe", "danger", "ಸುರಕ್ಷಿತವಿಲ್ಲ", "ಅಪಾಯ", "सुरक्षित नहीं", "खतरा", "surakshit nahi", "khatra"]


def answer_type(text: str) -> str | None:
    """yes | no | dont_know | None for a short reply. Long replies are content, not bare answers."""
    words = re.findall(r"[\wಀ-೿ऀ-ॿ']+", text.lower())
    if len(words) > SHORT_REPLY:
        return None
    if _has(text, DONT_KNOW):
        return "dont_know"
    if len(words) > 8:
        return None
    first = " ".join(words[:2])
    if any(_has(" " + first + " ", [y]) for y in YES):
        return "yes"
    if any(_has(" " + first + " ", [n]) for n in NO):
        return "no"
    return None


def is_correction(text: str) -> bool:
    return _has(text, CORRECTION)


def is_reexplain(text: str) -> bool:
    return len(text.split()) <= SHORT_REPLY and _has(text, REEXPLAIN)


# ----------------------------------------------------------------------- dates
@dataclass
class DateMention:
    text: str
    iso: str            # YYYY-MM-DD, YYYY-MM or YYYY
    granularity: str    # day | month | year
    approximate: bool = False

    def as_date(self) -> dt.date:
        parts = [int(p) for p in self.iso.split("-")]
        while len(parts) < 3:
            parts.append(1)
        return dt.date(*parts)


@lru_cache(maxsize=1)
def _month_table() -> dict[str, int]:
    m = {}
    months = lexicon()["months"]
    for lang, names in months.items():
        for i, n in enumerate(names, start=1):
            m[n.lower()] = i
    for i, n in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1):
        m[n] = i
    m.update({"sept": 9, "ಫೆಬ್ರುವರಿ": 2, "फरवरी": 2, "सितम्बर": 9, "aktubar": 10})
    return m


@lru_cache(maxsize=1)
def _number_words() -> dict[str, int]:
    out = {}
    for n, words in lexicon()["numbers"].items():
        for w in words:
            out[str(w).lower()] = int(n)
    out.update({"a": 1, "an": 1, "one": 1, "couple of": 2, "few": 3, "several": 3, "ondu": 1, "ek": 1, "do": 2,
                "teen": 3, "char": 4, "chaar": 4, "paanch": 5, "ಒಂದು": 1, "ಎರಡು": 2, "ಮೂರು": 3, "ನಾಲ್ಕು": 4,
                "ಐದು": 5, "ಆರು": 6, "eradu": 2, "mooru": 3, "naalku": 4, "aidu": 5, "seven": 7, "eight": 8, "nine": 9,
                "eleven": 11, "थोड़े": 3, "कुछ": 3})
    return out


UNITS = {
    "day": ("day", "days", "din", "dinon", "ದಿನ", "ದಿನದ", "ದಿನಗಳ", "दिन", "दिनों"),
    "week": ("week", "weeks", "hafte", "hafta", "vaara", "ವಾರ", "ವಾರದ", "हफ़्ते", "हफ्ते", "हफ़्ता", "सप्ताह"),
    "month": ("month", "months", "mahine", "mahina", "tingalu", "tingala", "ತಿಂಗಳು", "ತಿಂಗಳ", "ತಿಂಗಳಿನ", "महीने", "महीना"),
    "year": ("year", "years", "saal", "varsha", "varshada", "ವರ್ಷ", "ವರ್ಷದ", "ವರ್ಷಗಳ", "साल", "वर्ष"),
}
AGO = ("ago", "back", "before", "pehle", "पहले", "hinde", "ಹಿಂದೆ", "ಮುಂಚೆ", "munche")


def _shift(conv: dt.date, n: int, unit: str) -> tuple[str, str]:
    if unit == "day":
        return (conv - dt.timedelta(days=n)).isoformat(), "day"
    if unit == "week":
        return (conv - dt.timedelta(weeks=n)).isoformat(), "day"
    if unit == "month":
        y, m = conv.year, conv.month - n
        while m <= 0:
            m += 12
            y -= 1
        return f"{y:04d}-{m:02d}", "month"
    return f"{conv.year - n:04d}", "year"


def extract_dates(text: str, conv: dt.date) -> list[DateMention]:
    out: list[DateMention] = []
    low = text.lower()
    months = _month_table()
    mon_alt = "|".join(sorted((re.escape(k) for k in months), key=len, reverse=True))
    # ISO / numeric
    for m in re.finditer(r"\b(20\d\d)-(\d\d)-(\d\d)\b", low):
        out.append(DateMention(m.group(0), m.group(0), "day"))
    for m in re.finditer(r"\b(\d{1,2})[/.-](\d{1,2})[/.-](20\d\d|\d\d)\b", low):
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        y = y + 2000 if y < 100 else y
        if 1 <= mo <= 12 and 1 <= d <= 31:
            out.append(DateMention(m.group(0), f"{y:04d}-{mo:02d}-{d:02d}", "day"))
    # 14 March 2025 / March 14, 2025 / March 2025 / ಮಾರ್ಚ್ 14, 2025
    for m in re.finditer(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({mon_alt})[,\s]+(20\d\d)", low):
        out.append(DateMention(m.group(0), f"{int(m.group(3)):04d}-{months[m.group(2)]:02d}-{int(m.group(1)):02d}", "day"))
    for m in re.finditer(rf"({mon_alt})\s+(\d{{1,2}})(?:st|nd|rd|th)?,?\s+(20\d\d)", low):
        out.append(DateMention(m.group(0), f"{int(m.group(3)):04d}-{months[m.group(1)]:02d}-{int(m.group(2)):02d}", "day"))
    if not out:
        for m in re.finditer(rf"({mon_alt})[,\s]+(20\d\d)", low):
            out.append(DateMention(m.group(0), f"{int(m.group(2)):04d}-{months[m.group(1)]:02d}", "month"))
        for m in re.finditer(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({mon_alt})\b(?![,\s]+20\d\d)", low):
            y = conv.year
            cand = dt.date(y, months[m.group(2)], min(int(m.group(1)), 28))
            if cand > conv:
                y -= 1
            out.append(DateMention(m.group(0), f"{y:04d}-{months[m.group(2)]:02d}-{int(m.group(1)):02d}", "day"))
    if not out:
        for m in re.finditer(r"\b(?:in|year|since|of|ಇಸವಿ)?\s*(20[0-3]\d)\b", low):
            out.append(DateMention(m.group(0).strip(), m.group(1), "year"))
    # relative expressions
    rel = [
        (["yesterday", "ninne", "ನಿನ್ನೆ", "कल रात"], 1, "day"),
        (["day before yesterday", "monne", "ಮೊನ್ನೆ", "परसों", "parson"], 2, "day"),
        (["today", "this morning", "ivattu", "ಇವತ್ತು", "ಇಂದು", "आज", "aaj", "just now", "an hour ago", "hour ago",
          "ಗಂಟೆ ಹಿಂದೆ", "घंटे पहले", "ghante pehle"], 0, "day"),
        (["last week", "hoda vaara", "ಹೋದ ವಾರ", "ಕಳೆದ ವಾರ", "पिछले हफ़्ते", "पिछले हफ्ते", "pichhle hafte"], 7, "day"),
        (["last month", "hoda tingalu", "ಹೋದ ತಿಂಗಳು", "ಕಳೆದ ತಿಂಗಳು", "पिछले महीने", "pichhle mahine"], 30, "month"),
        (["last year", "hoda varsha", "ಹೋದ ವರ್ಷ", "ಕಳೆದ ವರ್ಷ", "पिछले साल", "pichhle saal"], 365, "year"),
    ]
    for cues, days, gran in rel:
        if _has(text, cues):
            if gran == "day":
                iso = (conv - dt.timedelta(days=days)).isoformat()
            elif gran == "month":
                d = conv.replace(day=1) - dt.timedelta(days=1)
                iso = f"{d.year:04d}-{d.month:02d}"
            else:
                iso = f"{conv.year - 1:04d}"
            if "कल" in text and gran == "day" and days == 1 and not re.search(r"(था|थी|थे|आया|गया|किया|दिया|मारा)", text):
                continue   # Hindi 'kal' with no past-tense verb may mean tomorrow
            out.append(DateMention(next(c for c in cues if c.lower() in low), iso, gran, approximate=(gran == "week")))
    wd = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6,
          "ಸೋಮವಾರ": 0, "ಮಂಗಳವಾರ": 1, "ಬುಧವಾರ": 2, "ಗುರುವಾರ": 3, "ಶುಕ್ರವಾರ": 4, "ಶನಿವಾರ": 5, "ಭಾನುವಾರ": 6,
          "सोमवार": 0, "मंगलवार": 1, "बुधवार": 2, "गुरुवार": 3, "शुक्रवार": 4, "शनिवार": 5, "रविवार": 6, "itvaar": 6,
          "ravivaar": 6, "somvaar": 0, "bhanuvaara": 6, "shanivaara": 5}
    for name, idx in wd.items():
        if re.search(cue_pattern(name), " " + low + " ") and not any(d.granularity == "day" for d in out):
            delta = (conv.weekday() - idx) % 7 or 7
            out.append(DateMention(name, (conv - dt.timedelta(days=delta)).isoformat(), "day", approximate=False))
            break
    nums = _number_words()
    num_alt = "|".join(sorted((re.escape(k) for k in nums), key=len, reverse=True))
    for unit, words in UNITS.items():
        w_alt = "|".join(re.escape(w) for w in words)
        for m in re.finditer(rf"(\d+|{num_alt})\s*({w_alt})\s*(?:\S+\s+)?({'|'.join(map(re.escape, AGO))})", low):
            n = int(m.group(1)) if m.group(1).isdigit() else nums.get(m.group(1), 0)
            if n:
                iso, gran = _shift(conv, n, unit)
                out.append(DateMention(m.group(0), iso, gran, approximate=unit in ("week", "month", "year") or n >= 3))
    # de-duplicate on iso
    seen, uniq = set(), []
    for d in out:
        if d.iso not in seen:
            seen.add(d.iso)
            uniq.append(d)
    return [d for d in uniq if d.as_date() <= conv + dt.timedelta(days=60)]


REGIME_CUTOFF = dt.date(2024, 7, 1)


def regime_of(d: DateMention) -> str | None:
    if d.granularity == "year":
        y = int(d.iso)
        return "old" if y < 2024 else "new" if y > 2024 else None
    if d.granularity == "month":
        y, m = map(int, d.iso.split("-"))
        return "old" if (y, m) < (2024, 7) else "new"
    return "old" if d.as_date() < REGIME_CUTOFF else "new"


# ----------------------------------------------------------------------- money
def extract_money(text: str) -> list[str]:
    out = []
    for m in re.finditer(r"(?:₹|rs\.?|inr)\s*([\d,]+)|([\d,]+)\s*(?:rupees|rupaye|rupay|ರೂಪಾಯಿ|रुपये|रुपए|rs)", text.lower()):
        v = (m.group(1) or m.group(2)).replace(",", "")
        if v.isdigit():
            out.append(f"INR {int(v)}")
    for m in re.finditer(r"(\d+(?:\.\d+)?)\s*(lakh|lakhs|ಲಕ್ಷ|लाख|thousand|ಸಾವಿರ|हज़ार|hazaar|saavira)", text.lower()):
        mult = 100000 if m.group(2) in ("lakh", "lakhs", "ಲಕ್ಷ", "लाख") else 1000
        out.append(f"INR {int(float(m.group(1)) * mult)}")
    return list(dict.fromkeys(out))


# ---------------------------------------------------------------------- people
@lru_cache(maxsize=1)
def _person_cues() -> list[tuple[str, str, str]]:
    """(surface, noun_key, relation) from the lexicon role nouns, all variants."""
    cues = []
    for noun, entry in lexicon()["role_nouns"].items():
        kin = entry.get("kin")
        for g in ("m", "f", "any"):
            block = entry.get(g)
            if not block:
                continue
            rel = block.get("kin") or kin or noun
            for v, forms in block.items():
                if v == "kin" or not isinstance(forms, list):
                    continue
                bare = forms[0]
                bare = bare.get("nom") if isinstance(bare, dict) else bare
                if isinstance(bare, str) and bare.strip():
                    for prefix in ("my ", "ನನ್ನ ", "ನಮ್ಮ ", "मेरे ", "मेरी ", "मेरा ", "nanna ", "namma ", "mere ", "meri ", "mera "):
                        if bare.lower().startswith(prefix):
                            bare = bare[len(prefix):]
                    cues.append((bare.lower(), noun, rel))
        for v, s in (entry.get("surface") or {}).items():
            cues.append((s.lower(), noun, kin or noun))
    extra = [("husband", "spouse", "husband"), ("wife", "spouse", "wife"), ("mother-in-law", "mother_in_law", "mother_in_law"),
             ("father-in-law", "father_in_law", "father_in_law"), ("uncle", "paternal_uncle", "uncle"),
             ("maava", "maternal_uncle", "maava (father-in-law or maternal uncle)"), ("ಮಾವ", "maternal_uncle", "maava (father-in-law or maternal uncle)"),
             ("father", "father", "father"), ("ಅಪ್ಪ", "father", "father"), ("ತಂದೆ", "father", "father"), ("पिता", "father", "father"),
             ("papa", "father", "father"), ("appa", "father", "father"), ("mother", "mother", "mother"), ("ಅಮ್ಮ", "mother", "mother"),
             ("माँ", "mother", "mother"), ("sister", "sister", "sister"), ("ಅಕ್ಕ", "sister", "sister"), ("बहन", "sister", "sister"),
             ("son", "child", "son"), ("daughter", "child", "daughter"), ("landlord", "landlord", "landlord"),
             ("employer", "employer", "employer"), ("police", "police", "police"), ("ಪೊಲೀಸ್", "police", "police"), ("पुलिस", "police", "police"),
             ("bank", "bank", "bank"), ("ಬ್ಯಾಂಕ್", "bank", "bank"), ("बैंक", "bank", "bank"), ("shop", "seller", "seller"),
             ("showroom", "seller", "seller"), ("company", "company", "company"), ("buyer", "buyer", "buyer")]
    cues += extra
    seen, out = set(), []
    for c in sorted(cues, key=lambda x: -len(x[0])):
        if len(c[0]) >= 2 and c[0] not in seen and c[0] not in ("someone", "a man", "somebody"):
            seen.add(c[0])
            out.append(c)
    return out


ORG_NOUNS = {"police", "bank", "seller", "company", "platform", "lender", "employer"}


@dataclass
class PersonMention:
    surface: str
    noun: str
    relation: str
    is_org: bool = False
    name: str | None = None


def extract_people(text: str) -> list[PersonMention]:
    low = _norm(text)
    found: list[PersonMention] = []
    taken: list[tuple[int, int]] = []
    for surface, noun, rel in _person_cues():
        pat = cue_pattern(surface)
        for m in re.finditer(pat, low):
            if any(a <= m.start() < b for a, b in taken):
                continue
            taken.append((m.start(), m.end()))
            name = None
            after = low[m.end(): m.end() + 30]
            nm = re.match(r"\s+(?:named\s+|called\s+)?([a-z][a-z]+)", after)
            if nm and nm.group(1).capitalize() in _known_names():
                name = nm.group(1).capitalize()
            found.append(PersonMention(surface, noun, rel, noun in ORG_NOUNS, name))
            break
    uniq: dict[str, PersonMention] = {}
    for p in found:
        uniq.setdefault(p.relation, p)
    return list(uniq.values())


@lru_cache(maxsize=1)
def _known_names() -> set[str]:
    out = set()
    for group in lexicon()["names"].values():
        for g in ("m", "f"):
            for trip in group[g]:
                out.add(trip[0])
    return out


# ------------------------------------------------------------------- risk cues
def risk_cues(text: str) -> dict[str, str]:
    out = {}
    for flag, cues in kb().guidance["risk_keywords"].items():
        for c in cues:
            if _has(text, [c]):
                out[flag] = c
                break
    for flag, rules in (kb().guidance.get("risk_combos") or {}).items():
        for groups in rules:
            hits = [next((w for w in g if _has(text, [str(w)])), None) for g in groups]
            if all(hits) and flag not in out:
                out[flag] = " … ".join(hits)
    return out


WEAK_KEYWORDS = {"threat", "threaten", "son", "daughter", "ಮಗ", "बेटा", "बेटी", "beta", "beti", "ನಕಲಿ", "नकली", "fake", "will", "son", "pin", "return", "job", "marriage", "income", "earn", "share", "sold", "sale",
                 "link", "statement", "promise", "promised", "maga", "beta", "beti", "connection", "location",
                 "every day", "हर दिन", "ಪ್ರತಿ ದಿನ", "har din", "survey", "ಮದುವೆ", "ಕೆಲಸ", "kelsa", "नौकरी", "naukri"}


def keyword_issue_scores(text: str) -> dict[str, float]:
    scores = {}
    for issue, kws in kb().keywords.items():
        hits = sum(1 for k in kws if k and k not in WEAK_KEYWORDS and _has(text, [k]))
        if hits:
            scores[issue] = min(0.9, 0.35 + 0.2 * hits)
    for issue, rules in (kb().guidance.get("combos") or {}).items():
        for groups in rules:
            if all(_has(text, [str(w) for w in g]) for g in groups):
                scores[issue] = max(scores.get(issue, 0.0), 0.5 + 0.1 * (len(groups) - 1))
    return scores


@lru_cache(maxsize=1)
def _anchors() -> dict[str, list[str]]:
    def flat(xs):
        for x in xs:
            if isinstance(x, list):
                yield from flat(x)
            else:
                yield str(x)
    return {i: list(flat(v)) for i, v in (kb().guidance.get("anchors") or {}).items() if not i.startswith("_")}


def anchored(issue: str, text: str) -> bool:
    """True if the client's words contain at least one anchor of the issue (no anchors defined: allowed)."""
    a = _anchors().get(issue)
    return True if not a else _has(text, a)


def domains_mentioned(text: str) -> list[str]:
    """Legal areas the client's words point to, most anchored issues first."""
    k = kb()
    count: dict[str, int] = {}
    for issue in _anchors():
        if issue in k.issues and anchored(issue, text):
            d = k.domain(issue)
            count[d] = count.get(d, 0) + 1
    return [d for d, _ in sorted(count.items(), key=lambda x: -x[1])]


def safety_negative(text: str) -> bool:
    return _has(text, SAFE_NO)


@dataclass
class RuleResult:
    variant: str
    dates: list[DateMention] = field(default_factory=list)
    money: list[str] = field(default_factory=list)
    people: list[PersonMention] = field(default_factory=list)
    answer: str | None = None
    correction: bool = False
    reexplain: bool = False
    risks: dict[str, str] = field(default_factory=dict)
    issue_kw: dict[str, float] = field(default_factory=dict)


def analyse(text: str, conv: dt.date) -> RuleResult:
    return RuleResult(variant=detect_variant(text), dates=extract_dates(text, conv), money=extract_money(text),
                      people=extract_people(text), answer=answer_type(text), correction=is_correction(text),
                      reexplain=is_reexplain(text), risks=risk_cues(text), issue_kw=keyword_issue_scores(text))
