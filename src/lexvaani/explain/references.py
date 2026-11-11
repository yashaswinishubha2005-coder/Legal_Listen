"""T11 reference explanations per (spec, gold provision, language).

Structure: what it says / what it means / why it may apply here / conditions /
where to verify. "What it says" is ONLY a verbatim excerpt from the parsed
corpus; when the provision is not in the corpus the reference is marked
``pending_corpus_text`` and the field stays empty. The other parts are built
from the issue library (issue-level plain summary, element questions) and from
the user's own statements in the narrative, never from remembered legal text.
"""

from __future__ import annotations

from lexvaani.corpus.acts import BY_CODE
from lexvaani.corpus.registry import split_id
from lexvaani.schemas.common import IssueId, Language, LangVariant
from lexvaani.schemas.explanation import ExplanationRef, ExplanationStatus
from lexvaani.schemas.issue_library import IssueSchema
from lexvaani.schemas.ontology import ElementValue
from lexvaani.schemas.sample import NarrativeSample
from lexvaani.schemas.spec import ScenarioSpec

VARIANT_OF = {Language.EN: LangVariant.EN, Language.KN: LangVariant.KN, Language.HI: LangVariant.HI}
EXCERPT_CHARS = 600

FRAMES = {
    Language.EN: {
        "means": "In simple words: {summary}",
        "why": "From what you told us: {facts}",
        "why_none": "You have not yet described facts that clearly match this provision.",
        "cond": "{q} — {status}",
        "status": {ElementValue.SATISFIED: "you said yes", ElementValue.CONTRADICTED: "you said no",
                   ElementValue.UNKNOWN: "not known yet"},
        "verify": "Read the official text of section {sec} of the {act} ({year}) on India Code (indiacode.nic.in), "
                  "or ask the District Legal Services Authority for free legal help. This is not legal advice.",
    },
    Language.KN: {
        "means": "ಸರಳವಾಗಿ ಹೇಳಬೇಕಂದ್ರೆ: {summary}",
        "why": "ನೀವು ಹೇಳಿದ ಪ್ರಕಾರ: {facts}",
        "why_none": "ಈ ನಿಯಮಕ್ಕೆ ಸ್ಪಷ್ಟವಾಗಿ ಹೊಂದುವ ವಿಷಯವನ್ನು ನೀವು ಇನ್ನೂ ಹೇಳಿಲ್ಲ.",
        "cond": "{q} — {status}",
        "status": {ElementValue.SATISFIED: "ನೀವು ಹೌದು ಅಂದಿದ್ದೀರಿ", ElementValue.CONTRADICTED: "ನೀವು ಇಲ್ಲ ಅಂದಿದ್ದೀರಿ",
                   ElementValue.UNKNOWN: "ಇನ್ನೂ ಗೊತ್ತಿಲ್ಲ"},
        "verify": "{act} ({year}) ರ ಸೆಕ್ಷನ್ {sec} ರ ಅಧಿಕೃತ ಪಠ್ಯವನ್ನು ಇಂಡಿಯಾ ಕೋಡ್‌ನಲ್ಲಿ (indiacode.nic.in) ಓದಿ, "
                  "ಅಥವಾ ಉಚಿತ ಕಾನೂನು ನೆರವಿಗೆ ಜಿಲ್ಲಾ ಕಾನೂನು ಸೇವೆಗಳ ಪ್ರಾಧಿಕಾರವನ್ನು ಸಂಪರ್ಕಿಸಿ. ಇದು ಕಾನೂನು ಸಲಹೆ ಅಲ್ಲ.",
    },
    Language.HI: {
        "means": "आसान शब्दों में: {summary}",
        "why": "आपने जो बताया उसके अनुसार: {facts}",
        "why_none": "आपने अभी तक ऐसे तथ्य नहीं बताए जो इस प्रावधान से साफ़ मेल खाते हों।",
        "cond": "{q} — {status}",
        "status": {ElementValue.SATISFIED: "आपने हाँ कहा", ElementValue.CONTRADICTED: "आपने ना कहा",
                   ElementValue.UNKNOWN: "अभी पता नहीं"},
        "verify": "{act} ({year}) की धारा {sec} का आधिकारिक पाठ इंडिया कोड (indiacode.nic.in) पर पढ़ें, "
                  "या मुफ़्त कानूनी सहायता के लिए ज़िला विधिक सेवा प्राधिकरण से संपर्क करें। यह कानूनी सलाह नहीं है।",
    },
}


def build_explanations(spec: ScenarioSpec, lib: dict[IssueId, IssueSchema], narratives: dict[LangVariant, NarrativeSample],
                       corpus: dict) -> list[ExplanationRef]:
    out: list[ExplanationRef] = []
    for pid in spec.gold_provisions:
        issue_id = next((i for i in spec.issues if i in lib and
                         any(cp.provision_id == pid for cp in lib[i].candidate_provisions)), None)
        if issue_id is None:
            continue
        issue = lib[issue_id]
        act_code, sec, base = split_id(pid)
        act = BY_CODE.get(act_code)
        rec = corpus.get(f"{act_code}:{base}")
        for lang in Language:
            fr = FRAMES[lang]
            smp = narratives.get(VARIANT_OF[lang])
            facts = []
            if smp is not None:
                for f in smp.annotations.facts:
                    if f.issue_id == issue_id and f.element_id and f.polarity == ElementValue.SATISFIED:
                        facts.append(f.span.text)
            labels = {(e.issue_id, e.element_id): e.value for e in (smp.annotations.elements if smp else [])}
            conds = []
            for el in sorted(issue.elements, key=lambda e: (not e.critical, e.order)):
                val = labels.get((issue_id, el.element_id), ElementValue.UNKNOWN)
                conds.append(fr["cond"].format(q=el.question[lang], status=fr["status"][val]))
            said = None
            if rec is not None:                       # verbatim excerpt, cut at a word boundary and marked as cut
                said = rec.text if len(rec.text) <= EXCERPT_CHARS else rec.text[:EXCERPT_CHARS].rsplit(" ", 1)[0] + " …"
            out.append(ExplanationRef(
                explanation_id=f"exp_{spec.spec_id}_{pid}_{lang.value}",
                spec_id=spec.spec_id, provision_id=pid, language=lang, what_it_says=said,
                what_it_means=fr["means"].format(summary=issue.plain_summary[lang]),
                why_it_may_apply=fr["why"].format(facts=" ".join(facts)) if facts else fr["why_none"],
                conditions=conds,
                where_to_verify=fr["verify"].format(sec=sec, act=act.title if act else act_code,
                                                    year=act.year if act else ""),
                status=ExplanationStatus.COMPLETE if said else ExplanationStatus.PENDING_CORPUS_TEXT))
    return out
