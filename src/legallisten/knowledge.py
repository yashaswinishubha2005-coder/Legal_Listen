"""Knowledge base: the LexVaani-IN issue library, provision registry, law corpus, glossary and
LegalListen guidance, plus multilingual renderings used as answer options.

Nothing here is legal text: provision *text* is only ever taken from the parsed official corpus
(data/corpus/provisions.jsonl). When the corpus has no entry, LegalListen says so.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import yaml

from lexvaani.corpus.acts import BY_CODE
from lexvaani.render.lexicon import item, lexicon, pronoun
from lexvaani.render.markup import TOKEN_RE, render
from lexvaani.resources import glossary, issue_library
from lexvaani.schemas.common import IssueId, LangVariant
from lexvaani.schemas.issue_library import URGENT_FLAGS, IssueSchema

ROOT = Path(__file__).resolve().parents[2]
V = LangVariant
LANG_VARIANT = {"en": V.EN, "kn": V.KN, "hi": V.HI}
OLD_ACTS = {"IPC", "CrPC", "IEA"}
NEW_ACTS = {"BNS", "BNSS", "BSA"}
INDIA_CODE = "https://www.indiacode.nic.in/"
GENERIC = {
    "AMOUNT": {V.EN: "the money", V.KN: "ಹಣ", V.HI: "पैसे", V.KN_EN_LATN: "duddu", V.KN_EN_MIXED: "money",
               V.HI_EN_LATN: "paise"},
    "PLACE": {V.EN: "that place", V.KN: "ಆ ಜಾಗ", V.HI: "उस जगह", V.KN_EN_LATN: "aa jaaga", V.KN_EN_MIXED: "ಆ place",
              V.HI_EN_LATN: "us jagah"},
}
_THEY_FIX = [(r"\b([Tt]hey) is\b", r"\1 are"), (r"\b([Tt]hey) has\b", r"\1 have"), (r"\b([Tt]hey) was\b", r"\1 were"),
             (r"\b([Tt]hey) does\b", r"\1 do"), (r"\b([Tt]hey) ([a-z]+[^s\W])s\b", r"\1 \2"),
             (r"\btheir\.", "theirs."), (r"\bis their\b(?=[.,;])", "is theirs")]


def _clean(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+([,.?!।;:])", r"\1", text).strip(" ,;")
    text = re.sub(r"^[,;]\s*", "", text)
    for a, b in _THEY_FIX:
        text = re.sub(a, b, text)
    if re.match(r"(?i)they\b", text):   # coordinated verbs keep the plural subject
        text = re.sub(r"\b(and|but) has\b", r"\1 have", text)
        text = re.sub(r"\b(and|but) is\b", r"\1 are", text)
        text = re.sub(r"\b(and|but) ([a-z]+[^s\W])s\b(?! [a-z]+ing)", r"\1 \2", text)
    return text[:1].upper() + text[1:] if text else text


def render_generic(template: str, issue: IssueSchema, variant: LangVariant) -> str:
    """Render a library template with generic mentions (pronouns for people, no dates)."""
    def slot(sent, name, case):
        if name == "DATE" or name == "IDNUM":
            return
        if name.startswith("AMOUNT") or name == "PLACE":
            sent.add(GENERIC["AMOUNT" if name.startswith("AMOUNT") else "PLACE"][variant])
            return
        if name == "ITEM":
            keys = issue.value_slots.get("ITEM") or []
            sent.add(item(keys[0])[variant.value][1] if keys else "")
            return
        c = case or "nom"
        if c.startswith("pron"):
            c = c[5:] or "nom"
        sent.add(pronoun(variant, "n", c))

    def gender(name):
        if name == "ITEM":
            keys = issue.value_slots.get("ITEM") or []
            return item(keys[0])["g"] if keys else "m"
        return "n" if name not in ("SPK",) else "m"

    def literal(sent, text, tags):
        sent.add(text)

    return _clean(render(template, slot, gender, literal).text)


def strip_markup(template: str) -> str:
    return TOKEN_RE.sub(lambda m: m.group("lit") or "", template)


def evd_label(template: str) -> str | None:
    for m in TOKEN_RE.finditer(template):
        if m.group("tags") and "EVD" in [t.strip() for t in m.group("tags").split(",")]:
            return m.group("lit")
    return None


# Yes/no questions where a bare "yes" means the element is NOT met, or where "yes" is ambiguous.
YES_MEANS = {
    "fin.unauthorized_bank_txn|txn_not_authorised": "contradicted",     # "Did you make these transactions?"
    "fin.unauthorized_bank_txn|no_customer_negligence": "contradicted", # "Did you share your PIN / OTP?"
    "crim.theft|without_consent": "contradicted",                       # "Did you give anyone permission?"
    "cyb.morphed_intimate_image|without_consent": "contradicted",       # "Did you ever agree?"
    "fam.maintenance|neglect_or_refusal": "contradicted",               # "Is your husband giving you money?"
    "fam.maintenance|unable_to_maintain_self": "contradicted",          # "Do you have a job or income?"
    "prop.coheir_sale_without_consent|no_consent": "contradicted",      # "Did you sign or agree to this sale?"
    "prop.forged_documents|signature_forged": "contradicted",           # "Is the signature genuine?"
    "prop.coheir_sale_without_consent|claimant_has_share": None,        # two questions in one: use the options
}


@dataclass
class ElementInfo:
    key: str
    issue: str
    element_id: str
    critical: bool
    description: str
    question: dict[str, str]
    options: dict[str, dict[str, str]]          # value -> lang -> text
    proposition: dict[str, str]
    may_be_unknown: bool
    date_slot_required: bool
    event_type: str | None
    order: int
    yes_means_satisfied: dict[str, bool]
    yes_value: str | None = None          # what a bare 'yes' means: satisfied | contradicted | None (ambiguous)
    topic: dict[str, str] = field(default_factory=dict)


@dataclass
class EvidenceInfo:
    key: str
    issue: str
    evidence_id: str
    evidence_type: str
    supports: list[str]
    label: dict[str, str]
    held: dict[str, str]
    missing: dict[str, str]


@dataclass
class ProvisionInfo:
    provision_id: str
    act: str
    act_title: str
    section: str
    title_hint: str | None
    verification: str
    in_corpus: bool
    text: str | None
    maps_to: list[str]
    official_url: str
    regime: str | None                          # old | new | None
    text_section: str | None = None             # the section the text was copied from (parent of a sub-section)
    source_file: str | None = None              # official PDF the text was copied from
    source_pages: list[int] = field(default_factory=list)


@dataclass
class KB:
    issues: dict[str, IssueSchema]
    elements: dict[str, ElementInfo]
    evidence: dict[str, EvidenceInfo]
    provisions: dict[str, ProvisionInfo]
    guidance: dict
    glossary: list
    keywords: dict[str, list[str]] = field(default_factory=dict)

    def issue_title(self, issue: str, lang: str) -> str:
        if issue in self.issues:
            return self.issues[issue].title[_lang(lang)]
        return {"x.out_of_scope": {"en": "a legal matter outside my five areas", "kn": "ನನ್ನ ಐದು ಕ್ಷೇತ್ರಗಳ ಹೊರಗಿನ ಕಾನೂನು ವಿಷಯ",
                                   "hi": "मेरे पाँच क्षेत्रों से बाहर का कानूनी मामला"},
                "x.non_legal": {"en": "a non-legal matter", "kn": "ಕಾನೂನೇತರ ವಿಷಯ", "hi": "गैर-कानूनी विषय"}}[issue][lang]

    def summary(self, issue: str, lang: str) -> str:
        return self.issues[issue].plain_summary[_lang(lang)]

    def domain(self, issue: str) -> str | None:
        return self.issues[issue].domain.value if issue in self.issues else None

    def elements_of(self, issue: str) -> list[ElementInfo]:
        return sorted((e for e in self.elements.values() if e.issue == issue), key=lambda e: (e.order, e.key))


def _lang(lang: str):
    from lexvaani.schemas.common import Language
    return Language(lang)


def _yes_polarity(question_en: str) -> bool:
    """True for a yes/no question where 'yes' means the element is satisfied.

    Alternative questions ("Did it come down in the family, or did someone buy it?") and
    wh-questions have no yes/no reading; for those only the answer options are used.
    """
    q = question_en.strip().lower()
    if not re.match(r"(did|has|have|is|are|was|were|do|does|can|could|will|would|had)\b", q):
        return False
    return not re.search(r", or |\bor (did|was|is|were|has|have|do|does|someone|somebody)\b", q)


@lru_cache(maxsize=1)
def kb() -> KB:
    lib = {k.value: v for k, v in issue_library().items()}
    elements: dict[str, ElementInfo] = {}
    evidence: dict[str, EvidenceInfo] = {}
    for iid, issue in lib.items():
        for el in issue.elements:
            key = f"{iid}|{el.element_id}"
            opts = {val: {lg: render_generic(getattr(el, val)[LANG_VARIANT[lg]], issue, LANG_VARIANT[lg])
                          for lg in ("en", "kn", "hi")} for val in ("satisfied", "contradicted")}
            q = {lg.value: txt for lg, txt in el.question.items()}
            elements[key] = ElementInfo(
                key=key, issue=iid, element_id=el.element_id, critical=el.critical, description=el.description,
                question=q, options=opts, proposition=dict(el.proposition), may_be_unknown=el.may_be_unknown,
                date_slot_required=el.date_slot_required, event_type=el.event_type, order=el.order,
                yes_means_satisfied={lg: _yes_polarity(q["en"]) for lg in q})
        for ev in issue.evidence:
            key = f"{iid}|{ev.evidence_id}"
            label = {lg: (evd_label(ev.held[LANG_VARIANT[lg]]) or strip_markup(ev.held[LANG_VARIANT[lg]]))
                     for lg in ("en", "kn", "hi")}
            evidence[key] = EvidenceInfo(
                key=key, issue=iid, evidence_id=ev.evidence_id, evidence_type=ev.evidence_type.value,
                supports=[f"{iid}|{s}" for s in ev.supports], label=label,
                held={lg: render_generic(ev.held[LANG_VARIANT[lg]], issue, LANG_VARIANT[lg]) for lg in ("en", "kn", "hi")},
                missing={lg: render_generic(ev.missing[LANG_VARIANT[lg]], issue, LANG_VARIANT[lg]) for lg in ("en", "kn", "hi")})
    for key, el in elements.items():
        el.yes_value = YES_MEANS.get(key, "satisfied" if el.yes_means_satisfied.get("en") else None)
    labels = yaml.safe_load((ROOT / "resources" / "legallisten" / "element_labels.yaml").read_text(encoding="utf-8"))
    for key, lab in (labels.get("_evidence") or {}).items():
        if key in evidence:
            evidence[key].label = dict(lab)
    for key, el in elements.items():
        lab = labels.get(key)
        if lab:                      # neutral, case-independent wording for the interface
            el.topic = dict(lab["topic"])
            el.options = {"satisfied": dict(lab["sat"]), "contradicted": dict(lab["con"])}
        else:
            el.topic = {lg: el.options["satisfied"][lg] for lg in ("en", "kn", "hi")}
    guidance = yaml.safe_load((ROOT / "resources" / "legallisten" / "guidance.yaml").read_text(encoding="utf-8"))
    provisions = _load_provisions(lib)
    import sys
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from eval.baselines import KEYWORDS
    keywords = {i: [k.lower() for k in KEYWORDS.get(i, []) + guidance["issues"].get(i, {}).get("keywords", [])]
                for i in lib}
    return KB(issues=lib, elements=elements, evidence=evidence, provisions=provisions, guidance=guidance,
              glossary=glossary(), keywords=keywords)


def _load_provisions(lib: dict[str, IssueSchema]) -> dict[str, ProvisionInfo]:
    reg_path = ROOT / "data" / "corpus" / "provision_registry.jsonl"
    corpus_path = ROOT / "data" / "corpus" / "provisions.jsonl"
    registry = {}
    if reg_path.exists():
        for line in reg_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                registry[r["provision_id"]] = r
    corpus = {}
    if corpus_path.exists():
        for line in corpus_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                corpus.setdefault(r["provision_id"], r)     # first occurrence is the section itself, later ones are schedules
    out: dict[str, ProvisionInfo] = {}
    ids = set(registry) | {p.provision_id for i in lib.values() for p in i.candidate_provisions}
    hints = {p.provision_id: p.title_hint for i in lib.values() for p in i.candidate_provisions}
    for pid in sorted(ids):
        act, _, sec = pid.partition(":")
        r = registry.get(pid, {})
        info = BY_CODE.get(act)
        # A sub-section such as BNS:318(4) is shown with the full text of section 318, never a guessed excerpt.
        c = corpus.get(pid) or corpus.get(re.sub(r"\(.*$", "", pid))
        out[pid] = ProvisionInfo(
            provision_id=pid, act=act, act_title=f"{info.title}, {info.year}" if info else act, section=sec,
            title_hint=(corpus.get(pid) or {}).get("title") or r.get("title_hint") or hints.get(pid) or (c or {}).get("title"),
            verification=r.get("verification", "to_verify"), in_corpus=bool(c), text=(c or {}).get("text"),
            maps_to=r.get("maps_to", []), official_url=(info.official_url if info and info.official_url else INDIA_CODE),
            regime="old" if act in OLD_ACTS else "new" if act in NEW_ACTS else None,
            text_section=(c or {}).get("section_id"), source_file=(c or {}).get("source_file"),
            source_pages=(c or {}).get("source_pages") or [])
    return out


def is_urgent(flag: str) -> bool:
    return any(f.value == flag for f in URGENT_FLAGS)


def lexicon_terms() -> dict:
    return lexicon()


ISSUE_IDS = [i.value for i in IssueId if not i.value.startswith("x.")]
