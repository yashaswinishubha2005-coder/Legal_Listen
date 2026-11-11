"""Provision identification and explanation cards.

A provision is suggested only if it is a candidate provision of an identified issue in the LexVaani-IN
issue library, and its routing conditions (law regime by incident date, personal law, risk) are met or
still open. The card links it to the facts in the Case Graph. Official text is quoted only from the
parsed corpus; otherwise the card says the text must be checked at the official source.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from .i18n import t
from .knowledge import kb
from .policy import identified
from .state import CaseState


@dataclass
class ProvisionCard:
    provision_id: str
    issue: str
    act_title: str
    section: str
    title_hint: str | None
    official_text: str | None
    verification: str
    official_url: str
    regime_note: str | None
    means: str
    why: list[str] = field(default_factory=list)
    supporting_elements: list[str] = field(default_factory=list)
    conditions: list[str] = field(default_factory=list)
    against: list[str] = field(default_factory=list)
    help: str = ""
    note: str | None = None
    conditional_on: str | None = None
    llm_explanation: str | None = None
    text_section: str | None = None
    source_file: str | None = None
    source_pages: list[int] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def _status_word(status: str, lang: str) -> str:
    return t(f"status_{status}", lang)


def _routing_ok(when: dict[str, list[str]], state: CaseState) -> tuple[bool, str | None]:
    """(include?, condition note). Unknown routing values keep the provision with a note."""
    cond = None
    for var, allowed in when.items():
        if var == "law_regime":
            if state.law_regime and state.law_regime not in allowed:
                return False, None
            if not state.law_regime:
                cond = "regime"
        elif var == "personal_law":
            if state.personal_law in (None, "skipped"):
                cond = cond or f"personal_law:{'/'.join(allowed)}"
            elif state.personal_law not in allowed:
                return False, None
        elif var == "risk":
            if not any(f in state.risks for f in allowed):
                return False, None
    return True, cond


def cards(state: CaseState) -> list[ProvisionCard]:
    k = kb()
    lang = state.lang
    out: list[ProvisionCard] = []
    seen: set[str] = set()
    for issue in identified(state):
        sch = k.issues[issue]
        g = k.guidance["issues"].get(issue, {})
        for cp in sch.candidate_provisions:
            ok, cond = _routing_ok(cp.when, state)
            if not ok or (cp.provision_id, issue) in seen:
                continue
            seen.add((cp.provision_id, issue))
            info = k.provisions.get(cp.provision_id)
            if info is None:
                continue
            why, sup, conditions, against = [], [], [], []
            for el in k.elements_of(issue):
                es = state.elements.get(el.key)
                if es and es.value == "satisfied" and es.status != "conflicting":
                    q = next((s.quote for s in reversed(es.statements) if not s.corrected and s.value == "satisfied"), "")
                    why.append(f"“{q}” ({_status_word(es.status, lang)})")
                    sup.append(el.key)
                elif es and es.value == "contradicted" and es.status != "conflicting":
                    q = next((s.quote for s in reversed(es.statements) if not s.corrected), "")
                    against.append(f"“{q}”")
                elif el.critical or (es and es.status == "conflicting"):
                    conditions.append(el.question[lang])
            regime_note = None
            if info.regime == "old":
                regime_note = t("p_regime_old", lang)
            elif info.regime == "new":
                regime_note = t("p_regime_new", lang)
            if cond == "regime":
                regime_note = (regime_note or "") + " " + t("p_regime_unknown", lang)
            cond_on = None
            if cond and cond.startswith("personal_law:"):
                cond_on = cond.split(":", 1)[1]
            out.append(ProvisionCard(
                provision_id=cp.provision_id, issue=issue, act_title=info.act_title, section=info.section,
                title_hint=info.title_hint, official_text=info.text, verification=info.verification,
                official_url=info.official_url, regime_note=regime_note.strip() if regime_note else None,
                means=k.summary(issue, lang), why=why, supporting_elements=sup, conditions=conditions,
                against=against, help=(g.get("help") or {}).get(lang, ""), note=cp.note, conditional_on=cond_on,
                text_section=info.text_section, source_file=info.source_file, source_pages=info.source_pages))
    return out


def card_dict(card: ProvisionCard, lang: str) -> dict:
    d = card.to_dict()
    d["labels"] = {x: t(x, lang) for x in ("p_what", "p_means", "p_why", "p_help", "p_conditions", "p_verify",
                                          "p_heading_hint")}
    d["no_text_note"] = None if card.official_text else t("p_no_text", lang)
    d["source_note"] = None
    if card.official_text:
        pages = ", ".join(str(x) for x in card.source_pages)
        d["source_note"] = t("p_source", lang, file=card.source_file or "", pages=pages)
        if card.text_section and card.text_section != card.section:
            d["source_note"] += " " + t("p_full_section", lang, sec=card.text_section, sub=card.section)
    d["verify_text"] = t("p_verify_text", lang, act=card.act_title, sec=card.section)
    d["issue_title"] = kb().issue_title(card.issue, lang)
    return d


def fallback_explanation(card: ProvisionCard, lang: str, mode: str) -> str:
    """Template explanation used when no LLM is configured (never states legal text not in the corpus)."""
    k = kb()
    g = k.guidance["issues"].get(card.issue, {})
    parts = []
    if mode == "why":
        parts.append(t("p_facts", lang, x="; ".join(card.why) if card.why else t("none", lang)))
        if card.conditions:
            parts.append(t("p_still_needed", lang, x=" · ".join(card.conditions)))
        if card.against:
            parts.append(t("p_against", lang, x="; ".join(card.against)))
        return "\n".join(parts)
    parts.append(f"{card.act_title} — {card.section}" + (f" ({card.title_hint})" if card.title_hint else ""))
    if mode == "simpler":
        parts.append(t("reexplain_intro", lang))
        parts.append(card.help or card.means)
        ex = (g.get("example") or {}).get(lang)
        if ex:
            parts.append(t("p_example_intro", lang) + " " + ex)
    else:
        parts.append(card.means)
        if card.help:
            parts.append(card.help)
    return "\n".join(parts)
