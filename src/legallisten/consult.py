"""Final consultation: case summary, issues, graph insights, laws with explanations, options,
evidence checklist, next steps, unresolved questions, risks — in the client's language."""

from __future__ import annotations

from .graph import insights
from .i18n import risk_name, t
from .knowledge import is_urgent, kb
from .llm import LLM, LLMError, lang_kw, prompt
from .policy import identified
from .provisions import card_dict, cards, fallback_explanation
from .state import CaseState


def triage(state: CaseState) -> str:
    k = kb()
    ids = identified(state)
    if any(is_urgent(f) for f in state.risks) or "cyb.morphed_intimate_image" in ids or state.safety_unsafe:
        return "urgent"
    if not ids:
        return "lawyer" if state.out_of_scope >= 0.5 else "self_help"
    if len(ids) >= 2 or state.personal_law in ("muslim", "christian"):
        return "lawyer"
    if any(k.issues[i].default_triage.value == "lawyer" for i in ids):
        return "lawyer"
    return "self_help"


def _facts(state: CaseState) -> list[str]:
    k = kb()
    lang = state.lang
    out = []
    for key, es in state.elements.items():
        if key not in k.elements or not es.statements:
            continue
        s = next((x for x in reversed(es.statements) if not x.corrected), None)
        if s is None:
            continue
        status = t(f"status_{es.status}", lang)
        out.append(f"{s.quote} [{status}]")
    return out


def _summary_text(state: CaseState, llm: LLM | None) -> str:
    k = kb()
    lang = state.lang
    ids = identified(state)
    issues = ", ".join(k.issue_title(i, lang) for i in ids) or (
        k.issue_title("x.out_of_scope", lang) if state.out_of_scope >= 0.5 else t("no_issue_yet", lang))
    facts = _facts(state)
    if llm is not None and facts:
        try:
            ins = insights(state)
            open_q = [c.a.quote + " / " + c.b.quote for c in state.contradictions if not c.resolved] + ins["missing"]
            r = llm.json(prompt("legallisten_summary_v1", **lang_kw(lang), facts="; ".join(facts), people=ins["people"],
                                timeline=ins["timeline"], evidence=ins["evidence"], open="; ".join(open_q) or "none",
                                risks=", ".join(state.risks) or "none"), "summary")
            state.llm_calls += 1
            if r.get("summary"):
                return str(r["summary"])
        except (LLMError, KeyError, ValueError, TypeError):
            pass
    lines = [t("summary_lead", lang, issues=issues)]
    if facts:
        lines.append(t("summary_facts", lang) + " " + " · ".join(facts[:12]))
    if state.other_facts:
        lines.append(t("other_facts", lang) + " " + " · ".join(f"“{x}”" for x in state.other_facts[:8]))
    return "\n".join(lines)


def build(state: CaseState, llm: LLM | None = None, explain_with_llm: bool = True) -> dict:
    k = kb()
    lang = state.lang
    ids = identified(state)
    level = triage(state)
    ins = insights(state)
    prov = cards(state)
    prov_out = []
    listed: set[str] = set()
    for c in prov:
        if c.provision_id in listed:
            continue
        listed.add(c.provision_id)
        d = card_dict(c, lang)
        d["explanation"] = None
        if llm is not None and explain_with_llm:
            d["explanation"] = explain(c, state, llm, "standard")
        if not d["explanation"]:
            d["explanation"] = fallback_explanation(c, lang, "standard")
        prov_out.append(d)
    domains = []
    for i in ids:
        dmn = k.domain(i)
        if dmn not in domains:
            domains.append(dmn)
    steps, authorities, options = [], [], []
    for flag in state.risks:
        alert = k.guidance["risk_alerts"].get(flag)
        if alert:
            authorities += [a for a in alert["authorities"] if a not in authorities]
    for i in ids:
        g = k.guidance["issues"].get(i, {})
        if g.get("step"):
            steps.append(g["step"][lang])
        if g.get("help"):
            options.append(f"{k.issue_title(i, lang)}: {g['help'][lang]}")
    for dmn in domains:
        dg = k.guidance["domains"][dmn]
        steps += [s[lang] for s in dg["steps"] if s[lang] not in steps]
        authorities += [a for a in dg["authorities"] if a not in authorities]
    if state.out_of_scope >= 0.5 and not ids:
        options.append(k.guidance["out_of_scope"]["help"][lang])
        authorities += ["legal_aid_15100", "lawyer"]
    if level != "self_help" and "legal_aid_15100" not in authorities:
        authorities.append("legal_aid_15100")
    evidence = []
    for ev in k.evidence.values():
        if ev.issue in ids:
            st = state.evidence.get(ev.key)
            evidence.append({"label": ev.label[lang], "status": st.availability if st else "unknown",
                             "why": "; ".join(k.elements[s].question[lang] for s in ev.supports if s in k.elements)})
    for key, st in state.evidence.items():
        if key.startswith("free|"):
            evidence.append({"label": st.label, "status": st.availability, "why": ""})
    unresolved = list(dict.fromkeys(ins["missing"]))
    if state.law_regime is None and any(c["regime_note"] and "IPC" in (c["regime_note"] or "") for c in prov_out):
        unresolved.append(t("q_date", lang, event=t("the_incident", lang)).split("?")[0] + "?")
    contradictions = [{"a": c.a.quote, "b": c.b.quote, "resolved": c.resolved, "resolution": c.resolution}
                      for c in state.contradictions]
    risks = []
    for flag, r in state.risks.items():
        alert = k.guidance["risk_alerts"].get(flag, {})
        risks.append({"flag": flag, "name": risk_name(flag, lang), "urgent": is_urgent(flag), "quote": r.quote, "advice": alert.get(lang, ""),
                      "authorities": [k.guidance["authorities"][a][lang] for a in alert.get("authorities", [])]})
    for i in ids:
        note = k.issues[i].limitation_notes
        if note:
            risks.append({"flag": "time_limit", "name": risk_name("time_limit", lang), "urgent": False, "quote": "", "advice": note + " (English, TO_VERIFY)",
                          "authorities": []})
    out = {
        "version": state.consultation_version + 1,
        "lang": lang,
        "labels": {key: t(key, lang) for key in ("c_title", "c_summary", "c_issues", "c_graph", "c_laws", "c_options",
                                                 "c_evidence", "c_steps", "c_unresolved", "c_risks", "c_authorities",
                                                 "c_contradictions", "lawyer_summary", "held", "missing",
                                                 "status_unknown", "c_options_note", "disclaimer")},
        "triage": level,
        "triage_text": t(f"triage_{level}", lang),
        "summary": _summary_text(state, llm),
        "issues": [{"id": i, "title": k.issue_title(i, lang), "summary": k.summary(i, lang),
                    "belief": state.beliefs.get(i), "domain": k.domain(i)} for i in ids],
        "out_of_scope": state.out_of_scope >= 0.5 and not ids,
        "graph_insights": ins,
        "provisions": prov_out,
        "options": options,
        "options_note": t("c_options_note", lang),
        "evidence": evidence,
        "steps": steps,
        "authorities": [k.guidance["authorities"][a][lang] for a in authorities if a in k.guidance["authorities"]],
        "unresolved": unresolved,
        "contradictions": contradictions,
        "risks": risks,
        "no_urgent": t("no_urgent", lang) if not any(r["urgent"] for r in risks) else None,
        "disclaimer": t("disclaimer", lang),
        "law_regime": state.law_regime,
        "incident_date": state.incident_date,
        "personal_law": state.personal_law,
    }
    out["lawyer_summary"] = lawyer_summary(state, out)
    return out


def explain(card, state: CaseState, llm: LLM | None, mode: str) -> str:
    lang = state.lang
    k = kb()
    if llm is not None:
        try:
            r = llm.json(prompt("legallisten_explain_v1", **lang_kw(lang), mode=mode, act_title=card.act_title,
                                section=card.section, title_hint=card.title_hint or "",
                                official_text=card.official_text or "", issue_title=k.issue_title(card.issue, "en"),
                                issue_summary=k.summary(card.issue, "en"), facts="; ".join(card.why) or "none",
                                conditions="; ".join(card.conditions) or "none"), "explain")
            state.llm_calls += 1
            text = str(r.get("explanation") or "").strip()
            if text:
                return text
        except (LLMError, KeyError, ValueError, TypeError):
            pass
    return fallback_explanation(card, lang, mode)


def lawyer_summary(state: CaseState, c: dict) -> str:
    """Compact English summary for a lawyer (original quotes kept in the client's language)."""
    k = kb()
    lines = ["LegalListen — preliminary case notes (client-reported; not verified)",
             f"Consultation date: {state.conversation_date} · client language: {state.input_variant or state.lang}",
             f"Triage: {c['triage']}"]
    ids = identified(state)
    lines.append("Issues: " + (", ".join(f"{k.issue_title(i, 'en')} (belief {state.beliefs[i]:.2f})" for i in ids) or "unclear"))
    if state.incident_date or state.law_regime:
        lines.append(f"Incident date: {state.incident_date or 'unknown'} · criminal-law regime: {state.law_regime or 'unknown'}")
    if state.personal_law:
        lines.append(f"Personal law: {state.personal_law}")
    lines.append("People: " + (", ".join(f"{p.label} [{p.relation}]" for p in state.people) or "none named"))
    lines.append("Facts by element:")
    for i in ids:
        for el in k.elements_of(i):
            es = state.elements.get(el.key)
            if es and es.statements:
                s = next((x for x in reversed(es.statements) if not x.corrected), es.statements[-1])
                gloss = f" (EN: {s.gloss_en})" if s.gloss_en else ""
                lines.append(f"  - {el.element_id}: {es.value} [{es.status}] — “{s.quote}”{gloss}")
            else:
                lines.append(f"  - {el.element_id}: not established")
    if state.other_facts:
        lines.append("Other client statements: " + " | ".join(state.other_facts))
    if state.evidence:
        lines.append("Evidence: " + "; ".join(f"{e.label} ({e.availability})" for e in state.evidence.values()))
    if state.contradictions:
        lines.append("Contradictions: " + "; ".join(f"“{x.a.quote}” vs “{x.b.quote}” ({x.resolution or 'open'})"
                                                     for x in state.contradictions))
    if state.risks:
        lines.append("Risk flags: " + ", ".join(state.risks))
    lines.append("Candidate provisions (TO_VERIFY against official text): " +
                 (", ".join(sorted({p['provision_id'] for p in c['provisions']})) or "none"))
    return "\n".join(lines)


def to_markdown(c: dict) -> str:
    L = c["labels"]
    md = [f"# {L['c_title']}", "", f"**{c['triage_text']}**", "", f"## {L['c_summary']}", "", c["summary"], ""]
    md += [f"## {L['c_issues']}", ""] + [f"- **{i['title']}** — {i['summary']}" for i in c["issues"]] + [""]
    gi = c["graph_insights"]
    md += [f"## {L['c_graph']}", "", f"- {gi['people']}", f"- {gi['timeline']}", f"- {gi['claims']}", f"- {gi['evidence']}", ""]
    md += [f"## {L['c_laws']}", ""]
    for p in c["provisions"]:
        lb = p["labels"]
        md += [f"### {p['act_title']} — {p['section']}" + (f" ({p['title_hint']})" if p["title_hint"] else ""), "",
               f"*{p['issue_title']}* · verification: **{p['verification']}**", ""]
        if p.get("regime_note"):
            md += [f"_{p['regime_note']}_", ""]
        md += [f"**{lb['p_what']}:** " + (p["official_text"] or p["no_text_note"]), "",
               f"**{lb['p_means']}:** {p['explanation']}", "",
               f"**{lb['p_why']}:** " + ("; ".join(p["why"]) or "—"), "",
               f"**{lb['p_help']}:** {p['help']}", "",
               f"**{lb['p_conditions']}:** " + ("; ".join(p["conditions"]) or "—"), "",
               f"**{lb['p_verify']}:** {p['verify_text']} {p['official_url']}", ""]
    md += [f"## {L['c_options']}", ""] + [f"- {o}" for o in c["options"]] + ["", f"_{c['options_note']}_", ""]
    md += [f"## {L['c_evidence']}", ""] + [f"- [{'x' if e['status'] == 'held' else ' '}] {e['label']}" for e in c["evidence"]] + [""]
    md += [f"## {L['c_steps']}", ""] + [f"{n}. {s}" for n, s in enumerate(c["steps"], 1)] + [""]
    md += [f"## {L['c_authorities']}", ""] + [f"- {a}" for a in c["authorities"]] + [""]
    md += [f"## {L['c_unresolved']}", ""] + ([f"- {q}" for q in c["unresolved"]] or ["- —"]) + [""]
    if c["contradictions"]:
        md += [f"## {L['c_contradictions']}", ""] + [f"- “{x['a']}” ↔ “{x['b']}”" for x in c["contradictions"]] + [""]
    md += [f"## {L['c_risks']}", ""] + [f"- **{r['name']}**: {r['advice']}" for r in c["risks"]]
    if c.get("no_urgent"):
        md.append(f"- {c['no_urgent']}")
    md += ["", f"## {L['lawyer_summary']}", "", "```", c["lawyer_summary"], "```", "", f"> {c['disclaimer']}", ""]
    return "\n".join(md)
