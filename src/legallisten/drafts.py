"""Ready-to-file drafts built from the Legal Case Graph.

Every sentence in a draft is either fixed template wording, a fact the user stated (carrying the quote and
the message it came from, so the user can check where it came from), or a blank the user fills in. Nothing is
invented: unknown details stay blanks, and facts the user did not confirm are listed as open points instead.

Drafts are written in English (the language most police stations, banks and commissions accept for written
complaints); the explanation of what the draft is and where to submit it is in the user's language.
"""

from __future__ import annotations

import datetime as dt
import re

from .i18n import t
from .knowledge import kb
from .policy import identified
from .provisions import cards
from .state import CaseState

POLICE = ("crim.", "cyb.", "fam.domestic_violence", "fam.dowry_harassment", "fin.loan_recovery_harassment",
          "prop.forged_documents", "prop.encroachment")
CYBER = ("cyb.", "fin.unauthorized_bank_txn")
NOTICE = ("prop.",)
CONSUMER = ("con.",)
BANK = ("fin.unauthorized_bank_txn",)


def _starts(issue: str, prefixes: tuple[str, ...]) -> bool:
    return any(issue == p or (p.endswith(".") and issue.startswith(p)) for p in prefixes)


def _clean(label: str) -> str:
    s = re.sub(r"^(yes|no)\s*,\s*", "", label.strip(), flags=re.I)
    return s[:1].upper() + s[1:]


class _Doc:
    def __init__(self) -> None:
        self.blocks: list[dict] = []

    def text(self, v: str) -> "_Doc":
        self.blocks.append({"t": "text", "v": v})
        return self

    def head(self, v: str) -> "_Doc":
        self.blocks.append({"t": "h", "v": v})
        return self

    def blank(self, bid: str, label: str) -> "_Doc":
        self.blocks.append({"t": "blank", "id": bid, "label": label})
        return self

    def fact(self, v: str, quote: str | None, turn: int | None, ts: str | None) -> "_Doc":
        self.blocks.append({"t": "fact", "v": v, "quote": quote, "turn": turn, "ts": ts})
        return self

    def br(self) -> "_Doc":
        self.blocks.append({"t": "br"})
        return self


def _case_facts(state: CaseState, issues: list[str]) -> dict:
    """The material a draft may use, each piece with its source in the conversation."""
    k = kb()
    ts_of = {m.turn: m.ts for m in state.messages if m.role == "user"}
    facts, unconfirmed = [], []
    for iss in issues:
        for el in sorted((e for e in k.elements.values() if e.issue == iss), key=lambda e: (not e.critical, e.order)):
            es = state.elements.get(el.key)
            if es is None or es.value is None:
                if el.critical:
                    unconfirmed.append(el.question[state.lang])
                continue
            s = next((x for x in reversed(es.statements) if not x.corrected), None)
            if es.value == "satisfied" and s is not None:
                facts.append({"v": _clean(el.options["satisfied"]["en"]), "quote": s.quote, "turn": s.turn,
                              "ts": ts_of.get(s.turn)})
            elif es.value == "unknown" or es.status == "conflicting":
                unconfirmed.append(el.question[state.lang])
    people = [p for p in state.people if p.relation not in ("self", "client")]
    evidence = []
    for key, ev in state.evidence.items():
        if ev.availability == "held":
            info = k.evidence.get(key)
            evidence.append(info.label["en"] if info else ev.label)
    return {"facts": facts, "unconfirmed": unconfirmed, "people": people, "evidence": evidence,
            "money": list(dict.fromkeys(state.money)), "date": state.incident_date_text or state.incident_date,
            "date_iso": state.incident_date, "regime": state.law_regime,
            "date_turn": next((m.turn for m in state.messages if m.role == "user" and state.incident_date_text
                               and state.incident_date_text in m.text), None),
            "other": state.other_facts[-4:], "ts_of": ts_of}


def _when(text: str, iso: str | None, regime: str | None = None) -> str:
    """'in 2025', 'on 12-03-2025' or 'in March 2025', from the resolved date; never more precise than it is."""
    if iso and re.fullmatch(r"\d{4}", iso):
        return f"in {iso}"
    if iso and re.fullmatch(r"\d{4}-\d{2}", iso):
        return "in " + dt.date.fromisoformat(iso + "-01").strftime("%B %Y")
    if iso and re.fullmatch(r"\d{4}-\d{2}-\d{2}", iso):
        return "on " + dt.date.fromisoformat(iso).strftime("%d-%m-%Y")
    if regime:                                   # the date chip only tells us which side of 1 July 2024
        return "before 1 July 2024" if regime == "old" else "on or after 1 July 2024"
    return f"on / around {text}"


def _party(people) -> str:
    return ", ".join(f"my {p.label}" if not p.is_org else p.label for p in people[:3])


def _facts_section(d: _Doc, cf: dict, start: int = 1) -> int:
    n = start
    if not cf["date"] and cf["regime"]:          # only "before / after 1 July 2024" was answered
        cf = {**cf, "date": t("date_before" if cf["regime"] == "old" else "date_after", "en")}
    if cf["date"]:
        d.fact(f"{n}. The incident took place {_when(cf['date'], cf['date_iso'], cf['regime'])}.", cf["date"], cf["date_turn"],
               cf["ts_of"].get(cf["date_turn"]))
        d.text(" Exact date: ").blank("incident_date", "exact date, if known").text(".")
    else:
        d.text(f"{n}. The incident took place on ").blank("incident_date", "date of the incident").text(" at ") \
            .blank("incident_place", "place")
    d.br()
    n += 1
    if cf["people"]:
        p0 = cf["people"][0]
        d.fact(f"{n}. Person(s) concerned: {_party(cf['people'])}", p0.label, p0.turns[0] if p0.turns else None,
               cf["ts_of"].get(p0.turns[0]) if p0.turns else None)
        d.text(" — name: ").blank("other_name", "full name of the other person").text(", address: ") \
            .blank("other_address", "address, if known").text(".")
        d.br()
        n += 1
    for f in cf["facts"]:
        d.fact(f"{n}. {f['v']}.", f["quote"], f["turn"], f["ts"]).br()
        n += 1
    if cf["money"]:
        d.fact(f"{n}. Amount involved: {', '.join(cf['money'])}.", ", ".join(cf["money"]), None, None).br()
        n += 1
    for x in cf["other"]:
        d.fact(f"{n}. In my own words: “{x}”", x, None, None).br()
        n += 1
    return n


def _evidence_section(d: _Doc, cf: dict) -> None:
    d.head("Documents / proof I am attaching")
    if cf["evidence"]:
        for i, e in enumerate(cf["evidence"], 1):
            d.text(f"{i}. {e}").br()
    d.text(f"{len(cf['evidence']) + 1}. ").blank("more_docs", "any other document").br()


def _sign(d: _Doc) -> None:
    d.br().text("Yours faithfully,").br().blank("sign", "signature").br().text("Name: ").blank("name", "your full name") \
        .br().text("Phone: ").blank("phone", "phone number").br().text("Date: " + dt.date.today().strftime("%d-%m-%Y"))


def police_complaint(state: CaseState, issues: list[str], cf: dict, provs: list) -> _Doc:
    d = _Doc()
    titles = ", ".join(kb().issue_title(i, "en") for i in issues)
    d.text("To,").br().text("The Station House Officer,").br().blank("ps", "name of the police station") \
        .text(" Police Station,").br().blank("district", "district / city").br().br()
    d.head(f"Subject: Complaint regarding {titles.lower()}")
    d.text("Respected Sir / Madam,").br()
    d.text("I, ").blank("name", "your full name").text(", aged ").blank("age", "age").text(", residing at ") \
        .blank("address", "your address").text(", wish to report the following facts:").br().br()
    _facts_section(d, cf)
    crim = [p for p in provs if p["act"] in ("BNS", "IPC", "ITA", "DPA")]
    if crim:
        d.br().text("These facts may disclose offences under " +
                    "; ".join(f"{p['act']} section {p['section']}" for p in crim[:5]) +
                    " (to be examined by the police).").br()
    fir = next((p for p in provs if p["provision_id"] in ("BNSS:173", "CrPC:154")), None)
    d.br().text("I request you to register an FIR" + (f" under section {fir['section']} of the {fir['act']}" if fir else "")
                + ", investigate the matter and take action as per law. I also request a free copy of the FIR.").br()
    if any(_starts(i, CYBER) for i in issues):
        d.text("I am also reporting this on the National Cyber Crime Reporting Portal (cybercrime.gov.in) / helpline 1930.").br()
    d.br()
    _evidence_section(d, cf)
    _sign(d)
    return d


def bank_complaint(state: CaseState, issues: list[str], cf: dict, provs: list) -> _Doc:
    d = _Doc()
    d.text("To,").br().text("The Branch Manager / Grievance Redressal Officer,").br().blank("bank", "name of the bank") \
        .text(", ").blank("branch", "branch").br().br()
    d.head("Subject: Unauthorised transaction(s) in my account — request to block, investigate and reverse")
    d.text("Respected Sir / Madam,").br()
    d.text("I, ").blank("name", "your full name").text(", hold account number ").blank("account", "account number") \
        .text(" with your bank. I report the following:").br().br()
    n = _facts_section(d, cf)
    d.text(f"{n}. Transaction reference number(s): ").blank("txn", "UTR / transaction IDs").text(", date and time: ") \
        .blank("txn_time", "date and time").text(".").br().br()
    d.text("I request you to immediately block my card / account access, investigate these transactions, and credit "
           "the amount back to my account as per the bank's policy on unauthorised electronic transactions. Please "
           "give me a written acknowledgement with a complaint number.").br()
    d.text("I have also reported this on cybercrime.gov.in / helpline 1930. Complaint number: ").blank("cyber_no", "if any").br().br()
    _evidence_section(d, cf)
    _sign(d)
    return d


def consumer_complaint(state: CaseState, issues: list[str], cf: dict, provs: list) -> _Doc:
    d = _Doc()
    d.head("BEFORE THE DISTRICT CONSUMER DISPUTES REDRESSAL COMMISSION, ").blank("district", "district").br()
    d.text("Complainant: ").blank("name", "your full name").text(", ").blank("address", "your address").br()
    d.text("Opposite party: ").blank("opposite", "seller / company name and address").br().br()
    d.head("Complaint under the Consumer Protection Act, 2019")
    d.text("The complainant states as follows:").br()
    n = _facts_section(d, cf)
    d.text(f"{n}. Invoice / order number ").blank("invoice", "invoice or order number").text(" dated ") \
        .blank("invoice_date", "purchase date").text(".").br().br()
    d.head("Relief sought")
    d.text("The complainant requests the Commission to direct the opposite party to ").blank(
        "relief", "e.g. replace the product / refund ₹ ___ / pay compensation ₹ ___").text(", with costs.").br().br()
    d.text("This complaint can be filed online on e-Daakhil (edaakhil.nic.in).").br().br()
    _evidence_section(d, cf)
    _sign(d)
    return d


def legal_notice(state: CaseState, issues: list[str], cf: dict, provs: list) -> _Doc:
    d = _Doc()
    titles = ", ".join(kb().issue_title(i, "en") for i in issues)
    d.text("To,").br().blank("other_name", "full name of the other person").br().blank("other_address", "their address").br().br()
    d.head(f"Subject: Notice regarding {titles.lower()}")
    d.text("I, ").blank("name", "your full name").text(", residing at ").blank("address", "your address") \
        .text(", state the following:").br().br()
    _facts_section(d, cf)
    d.br().text("You are hereby called upon to ").blank("demand", "what you want them to do, e.g. stop the sale / remove the encroachment") \
        .text(" within ").blank("days", "15").text(" days of receiving this notice, failing which I will take "
                                                 "appropriate legal action at your risk as to costs.").br()
    d.text("(A notice is stronger when sent through an advocate by registered post. Keep the postal receipt.)").br().br()
    _evidence_section(d, cf)
    _sign(d)
    return d


def legal_aid(state: CaseState, issues: list[str], cf: dict, provs: list) -> _Doc:
    d = _Doc()
    titles = ", ".join(kb().issue_title(i, "en") for i in issues) or "my legal problem"
    d.text("To,").br().text("The Member Secretary,").br().text("District Legal Services Authority, ") \
        .blank("district", "district").br().br()
    d.head("Subject: Application for free legal aid")
    d.text("Respected Sir / Madam,").br()
    d.text("I, ").blank("name", "your full name").text(", aged ").blank("age", "age").text(", residing at ") \
        .blank("address", "your address").text(", request free legal aid and advice under the Legal Services "
                                                  "Authorities Act, 1987, in the following matter: " + titles.lower() + ".").br().br()
    d.head("Brief facts")
    _facts_section(d, cf)
    d.br().text("I am eligible for free legal aid because: ").blank(
        "eligible", "e.g. I am a woman / child / SC or ST / my annual income is below the limit").br()
    d.text("I request that a panel lawyer be assigned to advise and represent me.").br()
    _sign(d)
    return d


KINDS = [
    ("police", police_complaint, POLICE),
    ("bank", bank_complaint, BANK),
    ("consumer", consumer_complaint, CONSUMER),
    ("notice", legal_notice, NOTICE),
]


def build(state: CaseState) -> dict:
    """All drafts that fit this case, plus the free-legal-aid application (useful in every case)."""
    lang = state.lang
    issues = identified(state)
    cf = _case_facts(state, issues)
    provs = [{"provision_id": c.provision_id, "act": c.provision_id.split(":")[0], "section": c.section}
             for c in cards(state)]
    out = []
    for kind, fn, prefixes in KINDS:
        mine = [i for i in issues if _starts(i, prefixes)]
        if mine:
            out.append((kind, fn(state, mine, cf, provs)))
    out.append(("aid", legal_aid(state, issues, cf, provs)))
    drafts = []
    for kind, d in out:
        drafts.append({"kind": kind, "title": t(f"dr_{kind}", lang), "what": t(f"dr_{kind}_what", lang),
                       "where": t(f"dr_{kind}_where", lang), "blocks": d.blocks,
                       "n_facts": sum(1 for b in d.blocks if b["t"] == "fact"),
                       "n_blanks": len({b["id"] for b in d.blocks if b["t"] == "blank"})})
    return {"drafts": drafts, "unconfirmed": cf["unconfirmed"][:6], "ready": bool(issues),
            "labels": {x: t(x, lang) for x in ("dr_intro", "dr_from_you", "dr_fill", "dr_check", "dr_unconfirmed",
                                               "dr_download", "dr_print", "dr_copy", "dr_said", "dr_none",
                                               "dr_disclaimer", "dr_progress")}}
