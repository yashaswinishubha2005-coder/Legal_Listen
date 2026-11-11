"""Follow-up questions after (or during) the consultation, answered in the chat.

"What should I do next?", "Which documents do I need?", "Where should I go?", "Which law applies?",
"How long do I have?", "Do I need a lawyer?", "Will I win?", "What is a khata?", "Explain BNS 318" …
Answers are built from the case's own consultation (offline) or, in LLM mode, written by the LLM strictly from
that consultation. Nothing outside the consultation and the glossary is stated.
"""

from __future__ import annotations

import json
import re

from .i18n import t
from .knowledge import kb
from .llm import LLM, LLMError, lang_kw
from .nlu.rules import _has

INTENTS: dict[str, list[str]] = {
    "next_steps": ["what should i do", "what can i do", "what to do", "what do i do", "next step", "how to proceed",
                   "how do i proceed", "what now", "help me", "advice", "advise", "options",
                   "ಏನು ಮಾಡಬೇಕು", "ಏನ್ ಮಾಡ್ಬೇಕು", "ಮುಂದೇನು", "ಮುಂದೆ ಏನು", "ಏನು ಮಾಡಲಿ", "en maadbeku", "enu maadbeku", "mundenu",
                   "क्या करूँ", "क्या करूं", "क्या करना चाहिए", "आगे क्या", "क्या कर सकता", "क्या कर सकती", "kya karu",
                   "kya karna chahiye", "aage kya"],
    "documents": ["document", "papers", "proof", "evidence", "what do i need", "which records", "what should i collect",
                  "ದಾಖಲೆ", "ಸಾಕ್ಷ್ಯ", "ಪುರಾವೆ", "ಕಾಗದ", "दस्तावेज़", "दस्तावेज", "कागज़", "कागज", "सबूत", "प्रमाण",
                  "daakhale", "kaagaz", "saboot"],
    "laws": ["which law", "what law", "section", "which act", "ipc", "bns", "bnss", "legal provision", "provisions",
             "ಕಾನೂನು", "ಸೆಕ್ಷನ್", "ಕಲಂ", "ಕಾಯ್ದೆ", "कानून", "धारा", "अधिनियम", "kaanoonu", "kanoon", "dhara"],
    "where": ["where should i go", "where do i go", "where to go", "which court", "which office", "who should i contact",
              "whom should i", "who can help", "authority", "where to complain", "where can i complain",
              "ಎಲ್ಲಿಗೆ ಹೋಗ", "ಯಾರನ್ನು ಸಂಪರ್ಕ", "ಯಾವ ನ್ಯಾಯಾಲಯ", "ಯಾವ ಕೋರ್ಟ್", "ಎಲ್ಲಿ ದೂರು", "कहाँ जाऊँ", "कहाँ जाएँ", "किससे संपर्क",
              "कौन सी कोर्ट", "कौन-सी अदालत", "कहाँ शिकायत", "kahan jau", "kahan jaye", "elli hogli"],
    "time": ["how long", "time limit", "deadline", "limitation", "how much time", "how soon", "when should i",
             "ಎಷ್ಟು ಸಮಯ", "ಕಾಲಮಿತಿ", "ಎಷ್ಟು ದಿನ", "ಯಾವಾಗ", "कितना समय", "समय सीमा", "कितने दिन", "कब तक", "kitna time"],
    "lawyer": ["lawyer", "advocate", "legal aid", "cost", "fee", "fees", "afford", "free help", "money for case",
               "ವಕೀಲ", "ಉಚಿತ", "ಖರ್ಚು", "ಫೀಸ್", "वकील", "फीस", "फ़ीस", "खर्च", "मुफ़्त", "मुफ्त", "vakeel", "vakil"],
    "outcome": ["will i win", "chance", "chances", "can i win", "what will happen", "will i get", "how strong",
                "ಗೆಲ್ತೀನಾ", "ಗೆಲ್ಲ", "ಏನಾಗುತ್ತೆ", "जीत", "क्या होगा", "मिलेगा", "jeet"],
    "summary": ["summary", "my case", "what did you understand", "what have you noted", "recap", "consultation",
                "ಸಾರಾಂಶ", "ನನ್ನ ಪ್ರಕರಣ", "सारांश", "मेरा केस", "मेरा मामला", "saaraamsha"],
    "urgent": ["urgent", "danger", "is it safe", "emergency", "immediately", "ತುರ್ತು", "ಅಪಾಯ", "तुरंत", "ख़तरा", "खतरा", "आपात"],
}
QUESTION_WORDS = ["what", "how", "which", "where", "when", "who", "whom", "why", "can i", "should i", "do i", "will i",
                  "is it", "is there", "ಏನು", "ಹೇಗೆ", "ಎಲ್ಲಿ", "ಯಾವ", "ಯಾರು", "ಎಷ್ಟು", "ಏಕೆ", "ಯಾಕೆ", "ಅಂದರೆ", "ಅಂದ್ರೆ",
                  "क्या", "कैसे", "कहाँ", "कौन", "कितना", "कितने", "क्यों", "कब", "मतलब", "kya", "kaise", "kahan", "kaun",
                  "kitna", "kyun", "yenu", "enu", "hege", "elli", "yaava"]
DEFINE = ["what is", "what's", "what does", "meaning of", "means", "explain", "ಅಂದರೆ ಏನು", "ಅಂದ್ರೆ ಏನು", "ಅಂದರೆ", "ಅರ್ಥ",
          "क्या है", "क्या होता", "मतलब", "matlab", "andre enu"]


def is_question(text: str) -> bool:
    t_ = text.strip().lower()
    return t_.endswith("?") or t_.endswith("？") or _has(t_[:40], QUESTION_WORDS)


def detect(text: str) -> tuple[str, str | None] | None:
    """(intent, detail) for a follow-up question, or None when the message is not one."""
    low = text.lower()
    k = kb()
    # a provision mentioned by number: "explain BNS 318", "section 498A"
    m = re.search(r"\b(bns|bnss|bsa|ipc|crpc|hma|hsa|sma|tpa|sra|cpa|ita|pwdv|dpa|gwa|ra|lima|klra)\s*(?:s\.|sec\.?|section)?\s*(\d+[a-z]?)", low)
    if m:
        return "provision", f"{m.group(1).upper()}:{m.group(2)}"
    m = re.search(r"(?:section|sec\.?|धारा|ಸೆಕ್ಷನ್|ಕಲಂ)\s*(\d+[a-zA-Z]?)", text)
    if m:
        return "provision", m.group(1)
    if _has(low, DEFINE):
        for g in k.glossary:
            names = [g.en, g.kn, g.hi, g.kn_latn or "", g.hi_latn or "", g.term_id.replace("_", " ")]
            names += sum((v for v in (g.colloquial or {}).values()), [])
            for n in names:
                n = (n or "").split("(")[0].strip().lower()
                if len(n) >= 3 and n in low:
                    return "define", g.term_id
    if not is_question(text) and not _has(low, INTENTS["next_steps"]):
        return None
    for intent, cues in INTENTS.items():
        if _has(low, cues):
            return intent, None
    return ("general", None) if is_question(text) else None


def _bullets(items, n=6) -> str:
    return "\n".join(f"• {x}" for x in list(items)[:n])


def answer(intent: str, detail: str | None, c: dict, lang: str) -> str:
    """Offline answer built from the consultation dict `c` (see consult.build)."""
    L = c["labels"]
    if intent == "next_steps":
        parts = [t("fu_next", lang)]
        urgent = [r for r in c["risks"] if r.get("urgent")]
        if urgent:
            parts.append("⚠ " + urgent[0]["advice"])
        parts.append("\n".join(f"{i}. {s}" for i, s in enumerate(c["steps"][:6], 1)))
        if c["options"]:
            parts.append(L["c_options"] + ":\n" + _bullets(c["options"], 3))
        return "\n".join(p for p in parts if p)
    if intent == "documents":
        have = [e["label"] for e in c["evidence"] if e["status"] == "held"]
        need = [e["label"] for e in c["evidence"] if e["status"] != "held"]
        parts = [t("fu_documents", lang)]
        if have:
            parts.append(t("fu_have", lang) + "\n" + _bullets(have))
        if need:
            parts.append(t("fu_collect", lang) + "\n" + _bullets(need))
        parts.append(next((s for s in c["steps"] if any(w in s.lower() for w in ("record", "copy", "screenshot", "ದಾಖಲೆ", "प्रति", "कॉपी"))), ""))
        return "\n".join(p for p in parts if p)
    if intent in ("laws", "provision"):
        provs = c["provisions"]
        if intent == "provision" and detail:
            hit = [p for p in provs if p["provision_id"].upper() == detail.upper() or p["section"].split("(")[0] == detail.split(":")[-1]]
            if hit:
                p = hit[0]
                txt = p["explanation"] or p["means"]
                head = f"{p['act_title']} — {p['section']}" + (f" ({p['title_hint']})" if p["title_hint"] else "")
                if txt.startswith(head.split(" (")[0]):
                    txt = txt.split("\n", 1)[1] if "\n" in txt else ""
                why = (p["labels"]["p_why"] + ": " + "; ".join(p["why"])) if p["why"] else ""
                return (head + "\n" + txt + ("\n" + why if why else "") +
                        f"\n{p['verify_text']} {p['official_url']}")
            return t("fu_no_such_provision", lang)
        if not provs:
            return t("fu_no_laws", lang)
        lines = [t("fu_laws", lang)]
        for p in provs[:8]:
            lines.append(f"• {p['act_title']} — {p['section']}" + (f": {p['title_hint']}" if p["title_hint"] else "") +
                         (f" ({p['regime_note']})" if p.get("regime_note") else ""))
        lines.append(t("fu_laws_tail", lang))
        return "\n".join(lines)
    if intent == "where":
        return t("fu_where", lang) + "\n" + _bullets(c["authorities"], 8)
    if intent == "time":
        lim = [r["advice"] for r in c["risks"] if r["flag"] in ("time_limit", "limitation_near_expiry")]
        return t("fu_time", lang) + ("\n" + _bullets(lim) if lim else "") + "\n" + t("fu_time_tail", lang)
    if intent == "lawyer":
        return t("fu_lawyer", lang) + "\n" + c["triage_text"]
    if intent == "outcome":
        return t("fu_outcome", lang) + ("\n" + _bullets(c["options"], 3) if c["options"] else "")
    if intent == "summary":
        return c["summary"] + ("\n\n" + L["c_unresolved"] + ":\n" + _bullets(c["unresolved"], 4) if c["unresolved"] else "")
    if intent == "urgent":
        urgent = [r for r in c["risks"] if r.get("urgent")]
        if urgent:
            return "\n".join(f"⚠ {r['name']}: {r['advice']}\n" + _bullets(r["authorities"]) for r in urgent)
        return c.get("no_urgent") or t("no_urgent", lang)
    if intent == "define" and detail:
        g = next((g for g in kb().glossary if g.term_id == detail), None)
        if g:
            name = getattr(g, lang, None) or g.en
            return f"{name}: {g.plain_definition_en}" + ("" if lang == "en" else f"\n({t('fu_def_note', lang)})")
    return t("fu_general", lang) + "\n" + _bullets([t("fu_hint_" + x, lang) for x in ("next", "docs", "where", "laws")])


FOLLOWUP_PROMPT = """You are LegalListen. The client asked a follow-up question about their preliminary consultation.
Answer in {lang_name} ({script_note}), in 2–6 short sentences or bullet points, using ONLY the consultation JSON below.
Never invent laws, sections, punishments, deadlines or case law. If the answer is not in the consultation, say so and
suggest asking a lawyer or free legal aid (NALSA 15100). Never promise an outcome.

Consultation JSON: {consultation}

Client question: {question}

Return ONLY JSON: {{"answer": str}}"""


def answer_llm(llm: LLM, question: str, c: dict, lang: str) -> str | None:
    slim = {k: c[k] for k in ("triage_text", "summary", "issues", "options", "evidence", "steps", "authorities",
                              "unresolved", "risks", "law_regime", "incident_date")}
    slim["provisions"] = [{k: p[k] for k in ("provision_id", "act_title", "section", "title_hint", "official_text",
                                             "explanation", "why", "conditions", "help", "official_url")} for p in c["provisions"]]
    try:
        r = llm.json(FOLLOWUP_PROMPT.format(**lang_kw(lang), consultation=json.dumps(slim, ensure_ascii=False)[:12000],
                                            question=question[:1000]), "followup")
        return str(r.get("answer") or "").strip() or None
    except (LLMError, KeyError, ValueError, TypeError):
        return None


QUICK = ["next_steps", "documents", "where", "laws"]
