"""LegalListen: engine, policy, graph, consultation, LLM contract, store and HTTP API."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from legallisten import graph as G
from legallisten.app import create_app
from legallisten.engine import Engine
from legallisten.knowledge import ROOT, kb
from legallisten.llm import Fake
from legallisten.nlu import rules as R
from legallisten.store import Store

CONV = "2026-10-25"


def run(engine, st, items):
    out = []
    for it in items:
        out += engine.handle(st, "", chip=it[1:]) if it.startswith("#") else engine.handle(st, it)
    return out


def answer_all(engine, st, chip="el:sat", limit=25):
    """Answer every question with the given element chip (or the first offered chip)."""
    for _ in range(limit):
        if st.pending is None:
            break
        ids = [c.id for c in st.pending.chips]
        engine.handle(st, "", chip=chip if chip in ids else ids[0])


@pytest.fixture(scope="module")
def engine():
    return Engine()


# ------------------------------------------------------------------ knowledge
def test_knowledge_options_all_languages():
    k = kb()
    assert len(k.elements) == 87 and len(k.evidence) == 31
    for el in k.elements.values():
        for val in ("satisfied", "contradicted"):
            for lang in ("en", "kn", "hi"):
                txt = el.options[val][lang]
                assert txt and "{" not in txt and "[" not in txt, (el.key, val, lang, txt)


def test_provisions_never_invent_text():
    k = kb()
    for p in k.provisions.values():
        assert (p.text is None) == (not p.in_corpus)
        assert p.verification in ("to_verify", "verified", "not_found")


# ------------------------------------------------------------------ rules
def test_dates_and_regime():
    conv = R.dt.date(2026, 10, 25)
    d = R.extract_dates("On 3 June 2024 he hit me", conv)[0]
    assert (d.iso, R.regime_of(d)) == ("2024-06-03", "old")
    d = R.extract_dates("ಮಾರ್ಚ್ 14, 2025 ರಂದು", conv)[0]
    assert d.iso == "2025-03-14" and R.regime_of(d) == "new"
    assert R.extract_dates("three days ago", conv)[0].iso == "2026-10-22"
    assert R.regime_of(R.DateMention("2024", "2024", "year")) is None   # ambiguous year -> ask


def test_answer_types_multilingual():
    assert R.answer_type("Gottilla") == "dont_know"
    assert R.answer_type("पता नहीं") == "dont_know"
    assert R.answer_type("ಹೌದು") == "yes"
    assert R.answer_type("nahi") == "no"
    assert R.is_reexplain("samajh nahi aaya") and R.is_reexplain("ಅರ್ಥ ಆಗಲಿಲ್ಲ")
    assert R.is_correction("Sorry, I said that wrong.")


def test_indic_cues_need_word_start():
    # 'ಮಗ' (son) must not match inside 'ನಮಗೆ' (to us)
    assert not any(p.relation == "son" for p in R.extract_people("ನಮ್ಮ ಜಮೀನು ನಮಗೆ ಕೇಳದೆ ಮಾರಿದರು"))
    assert any(p.relation == "paternal_uncle" for p in R.extract_people("ನಮ್ಮ ಚಿಕ್ಕಪ್ಪ ಜಮೀನು ಮಾರಿದರು"))


def test_risk_cues():
    r = R.risk_cues("He said he will come back tonight and kill me")
    assert {"imminent_violence", "threat_to_life"} <= set(r)
    assert "imminent_property_transfer" in R.risk_cues("ಮುಂದಿನ ವಾರ ರಿಜಿಸ್ಟ್ರೇಷನ್ ಅಂತೆ")


# ------------------------------------------------------------------ engine flows
def test_property_flow_english(engine):
    st = engine.start("en", conversation_date=CONV)
    msgs = engine.handle(st, "My father passed away last year. Now my uncle is trying to sell our family land "
                             "without asking us. The registration is fixed for next week.")
    kinds = [m.kind for m in msgs]
    assert "alert" in kinds                                    # imminent transfer flagged first
    assert st.pending is not None and st.pending.kind in ("element", "safety")
    assert "prop.coheir_sale_without_consent" in st.issue_prior
    answer_all(engine, st)
    assert st.consultation_ready
    c = engine.consultation(st)
    assert c["triage"] == "urgent"
    ids = {p["provision_id"] for p in c["provisions"]}
    assert "TPA:44" in ids
    corpus = {}
    for line in open(ROOT / "data" / "corpus" / "provisions.jsonl", encoding="utf-8"):
        r = json.loads(line)
        corpus.setdefault(r["provision_id"], r["text"])
    for p in c["provisions"]:
        if p["official_text"]:                                      # text only ever comes from the parsed official PDF
            base = p["provision_id"].split("(")[0]
            assert p["official_text"] in (corpus.get(p["provision_id"]), corpus.get(base))
            assert p["source_note"]
        else:
            assert p["no_text_note"]
        assert p["official_url"].startswith("https://")
    g = engine.graph(st)
    assert g["errors"] == []
    types = {n["type"] for n in g["nodes"]}
    assert {"Person", "Issue", "Element", "Claim", "Provision"} <= types


def test_kannada_flow_language_and_chips(engine):
    st = engine.start("kn", conversation_date=CONV)
    msgs = engine.handle(st, "ನನ್ನ ಗಂಡ ದಿನಾ ಹೊಡೀತಾರೆ, ಅತ್ತೆ ಇನ್ನೂ ವರದಕ್ಷಿಣೆ ಕೇಳ್ತಾರೆ.")
    assert any("ಀ" <= ch <= "೿" for m in msgs for ch in m.text)     # replies in Kannada
    assert {"fam.domestic_violence", "fam.dowry_harassment"} & set(st.issue_prior)
    q = next(m for m in msgs if m.kind == "question")
    assert q.chips and all(any("ಀ" <= ch <= "೿" for ch in c.label) for c in q.chips)
    answer_all(engine, st)
    c = engine.consultation(st)
    assert c["lang"] == "kn" and c["triage"] in ("lawyer", "urgent")
    assert G.validate(engine.graph(st)) == []


def test_hinglish_date_sets_old_regime(engine):
    st = engine.start("hi", conversation_date=CONV)
    engine.handle(st, "Mere padosi ne 3 June 2024 ko mujhe laathi se maara aur sar pe chot lagi.")
    assert st.incident_date == "2024-06-03" and st.law_regime == "old"
    answer_all(engine, st)
    ids = {p["provision_id"] for p in engine.consultation(st)["provisions"]}
    assert "IPC:323" in ids and not any(i.startswith("BNS:") for i in ids)


def test_contradiction_detected_and_resolved(engine):
    st = engine.start("en", conversation_date=CONV)
    engine.handle(st, "My neighbour hit me with a stick yesterday.")
    key = "crim.hurt_assault|act_of_force"
    from legallisten.nlu.extract import ElementUpdate
    engine._apply_element(st, ElementUpdate(key, "satisfied", "He hit me with a stick."), source="answer")
    engine._apply_element(st, ElementUpdate(key, "contradicted", "He only shouted, he never hit me."), source="answer")
    engine._recompute_status(st)
    assert st.elements[key].status == "conflicting" and st.elements[key].value == "unknown"
    assert G.validate(engine.graph(st)) == []
    st.pending = None
    msgs = engine.handle(st, "ok")
    clar = [m for m in msgs if m.kind == "clarify"]
    assert clar and "He only shouted" in clar[-1].text
    engine.handle(st, "", chip="c:first")
    assert st.elements[key].value == "satisfied" and st.elements[key].status != "conflicting"
    assert st.contradictions[0].resolved and st.contradictions[0].resolution == "first"


def test_correction_replaces_without_contradiction(engine):
    st = engine.start("en", conversation_date=CONV)
    engine.handle(st, "My neighbour hit me.")
    from legallisten.nlu.extract import ElementUpdate
    key = "crim.hurt_assault|injury_caused"
    engine._apply_element(st, ElementUpdate(key, "contradicted", "No injury."), source="answer")
    engine._apply_element(st, ElementUpdate(key, "satisfied", "Sorry, I said that wrong, I was bleeding."),
                          source="answer", correction=True)
    assert not st.contradictions
    assert st.elements[key].value == "satisfied"
    assert st.elements[key].statements[0].corrected


def test_evidence_makes_claim_evidence_supported(engine):
    st = engine.start("en", conversation_date=CONV)
    engine.handle(st, "Someone called saying he is from the bank, asked me to scan a QR code and 20000 rupees went from my UPI account.")
    from legallisten.nlu.extract import ElementUpdate
    engine._apply_element(st, ElementUpdate("cyb.upi_payment_fraud|money_debited", "satisfied", "20000 went"), source="answer")
    engine._apply_evidence(st, "cyb.upi_payment_fraud|debit_screenshot", "held", "I have the screenshot")
    assert st.elements["cyb.upi_payment_fraud|money_debited"].status == "evidence_supported"
    g = engine.graph(st)
    assert any(e["type"] == "SUPPORTS" for e in g["edges"]) and g["errors"] == []


def test_low_confidence_voice_is_confirmed_first(engine):
    st = engine.start("en", conversation_date=CONV)
    msgs = engine.handle(st, "my nay bore hit me", source="voice", asr_confidence=0.4)
    assert msgs[-1].kind == "clarify" and st.pending.kind == "confirm_transcript"
    assert not st.issue_prior                                      # nothing was analysed yet
    engine.handle(st, "", chip="tr:yes")
    assert st.issue_prior


def test_reexplain_repeats_question_simply(engine):
    st = engine.start("en", conversation_date=CONV)
    engine.handle(st, "My neighbour hit me with a stick and I was injured.")
    key = st.pending.key if st.pending else None
    msgs = engine.handle(st, "I don't understand, explain simply")
    assert msgs[-1].kind == "question" and msgs[-1].chips
    assert (st.pending.key if st.pending else None) == key


def test_dont_know_keeps_element_unknown(engine):
    st = engine.start("en", conversation_date=CONV)
    engine.handle(st, "My neighbour hit me with a stick.")
    while st.pending and st.pending.kind != "element":
        engine.handle(st, "", chip=st.pending.chips[0].id)
    key = st.pending.key
    engine.handle(st, "I don't know")
    assert st.elements[key].value == "unknown"


def test_out_of_scope_and_non_legal(engine):
    st = engine.start("en", conversation_date=CONV)
    msgs = engine.handle(st, "I failed my exam and I am sad. What diet should I follow?")
    assert msgs and st.questions_asked <= 1


def test_explain_modes(engine):
    st = engine.start("en", conversation_date=CONV)
    engine.handle(st, "Someone stole my gold chain from my house yesterday.")
    answer_all(engine, st)
    c = engine.consultation(st)
    pid = c["provisions"][0]["provision_id"]
    simple = engine.explain(st, pid, "simpler")
    why = engine.explain(st, pid, "why")
    assert "example" in simple.lower() and why


# ------------------------------------------------------------------ LLM contract
def test_llm_extraction_validated(engine):
    good = {"issues": [{"issue_id": "crim.hurt_assault", "confidence": 0.9}, {"issue_id": "made.up", "confidence": 1}],
            "out_of_scope": 0, "non_legal": 0,
            "elements": [{"key": "crim.hurt_assault|act_of_force", "value": "satisfied", "quote": "hit me with a stick",
                          "gloss_en": "hit me with a stick", "status_hint": "reported", "hedged": False},
                         {"key": "crim.hurt_assault|bogus", "value": "satisfied", "quote": "x"}],
            "evidence": [], "risks": [{"flag": "imminent_violence", "quote": "tonight"}, {"flag": "nonsense", "quote": ""}],
            "people": [{"label": "my neighbour", "relation": "neighbour"}],
            "dates": [{"text": "3 June 2024", "iso": "2024-06-03", "element_key": "crim.hurt_assault|act_of_force"}],
            "personal_law": None, "correction": False, "reexplain": False, "unclear": False, "unclear_reason": None}
    fake = Fake([good, {"reply": "I am sorry this happened. Are you safe right now?"}])
    eng = Engine(fake)
    st = eng.start("en", use_llm=True, conversation_date=CONV)
    eng.handle(st, "On 3 June 2024 my neighbour hit me with a stick and said he will come back tonight.")
    assert "made.up" not in st.issue_prior
    assert st.elements["crim.hurt_assault|act_of_force"].value == "satisfied"
    assert "crim.hurt_assault|bogus" not in st.elements
    assert "imminent_violence" in st.risks and "nonsense" not in st.risks
    assert st.incident_date == "2024-06-03" and st.law_regime == "old"
    assert "Catalog" in fake.prompts[0] and "crim.hurt_assault|act_of_force" in fake.prompts[0]


def test_llm_failure_falls_back_to_local(engine):
    eng = Engine(Fake(["not json at all"]))
    st = eng.start("en", use_llm=True, conversation_date=CONV)
    msgs = eng.handle(st, "My neighbour hit me with a stick.")
    assert msgs and "crim.hurt_assault" in st.issue_prior


# ------------------------------------------------------------------ store + API
def test_store_encrypts_and_checks_token(tmp_path, engine, monkeypatch):
    monkeypatch.setenv("LEGALLISTEN_SECRET_KEY", "x" * 43 + "=")
    from cryptography.fernet import Fernet
    monkeypatch.setenv("LEGALLISTEN_SECRET_KEY", Fernet.generate_key().decode())
    s = Store(tmp_path / "s.db")
    st = engine.start("en", conversation_date=CONV)
    engine.handle(st, "My neighbour hit me with a stick.")
    token = s.create(st)
    raw = (tmp_path / "s.db").read_bytes()
    assert b"neighbour" not in raw                                   # encrypted at rest
    assert s.load(st.session_id, "wrong") is None
    assert s.load(st.session_id, token).session_id == st.session_id
    assert s.delete(st.session_id, token) and s.load(st.session_id, token) is None


@pytest.fixture()
def client(tmp_path, monkeypatch):
    from cryptography.fernet import Fernet
    monkeypatch.setenv("LEGALLISTEN_SECRET_KEY", Fernet.generate_key().decode())
    return TestClient(create_app(Engine(None), Store(tmp_path / "api.db")))


def test_api_full_consultation(client):
    r = client.post("/api/session", json={"lang": "hi", "use_llm": False, "conversation_date": CONV}).json()
    sid, tok = r["session_id"], r["token"]
    h = {"X-Session-Token": tok}
    assert client.get(f"/api/session/{sid}").status_code == 404     # token required
    r = client.post(f"/api/session/{sid}/message", headers=h,
                    json={"text": "किसी ने बैंक वाला बनकर फ़ोन किया, क्यूआर कोड स्कैन करवाया और मेरे खाते से 20000 रुपये कट गए।"}).json()
    assert r["messages"] and r["graph"]["errors"] == []
    for _ in range(20):
        last = [m for m in r["messages"] if m["role"] == "assistant"][-1]
        if not last["chips"] or last["chips"][0]["id"] == "show:consultation":
            break
        r = client.post(f"/api/session/{sid}/message", headers=h, json={"chip": last["chips"][0]["id"]}).json()
    c = client.post(f"/api/session/{sid}/consultation", headers=h).json()
    assert c["consultation"]["lang"] == "hi" and "#" in c["markdown"]
    assert client.get(f"/api/session/{sid}/export?fmt=md", headers=h).text.startswith("# ")
    assert "consultation" in client.get(f"/api/session/{sid}/export?fmt=json", headers=h).json()
    pid = c["consultation"]["provisions"][0]["provision_id"]
    e = client.post(f"/api/session/{sid}/explain", headers=h, json={"provision_id": pid, "mode": "simpler"}).json()
    assert e["text"]
    assert client.patch(f"/api/session/{sid}", headers=h, json={"lang": "kn"}).json()["summary"]["lang"] == "kn"
    assert client.delete(f"/api/session/{sid}", headers=h).json()["deleted"]
    assert client.get(f"/api/session/{sid}", headers=h).status_code == 404


def test_api_security_headers_and_config(client):
    r = client.get("/api/config")
    assert r.json()["llm_available"] is False
    assert "Content-Security-Policy" in r.headers and r.headers["X-Frame-Options"] == "DENY"
    assert client.get("/").status_code == 200
    assert client.post("/api/transcribe", files={"audio": ("a.webm", b"x", "audio/webm")}).status_code == 501


def test_transcribe_endpoint_with_fake_gemini(tmp_path, monkeypatch):
    from cryptography.fernet import Fernet
    monkeypatch.setenv("LEGALLISTEN_SECRET_KEY", Fernet.generate_key().decode())

    class FakeGemini(Fake):
        name = "gemini"

    fake = FakeGemini([{"transcript": "ನನ್ನ ಪಕ್ಕದ ಮನೆಯವರು ಹೊಡೆದರು", "confidence": 0.9, "unclear": ["ಹೊಡೆದರು"]}])
    c = TestClient(create_app(Engine(fake), Store(tmp_path / "t.db")))
    assert c.get("/api/config").json()["server_transcription"] is True
    r = c.post("/api/transcribe", data={"lang": "kn"}, files={"audio": ("a.wav", b"RIFF....", "audio/wav")}).json()
    assert r["transcript"].startswith("ನನ್ನ") and r["confidence"] <= 0.55       # unclear words lower confidence


def test_llm_explanation_and_summary_used_in_consultation():
    script = [lambda p: {"issues": [{"issue_id": "crim.theft", "confidence": 0.9}], "elements": [
                  {"key": "crim.theft|property_taken", "value": "satisfied", "quote": "stole my gold chain",
                   "gloss_en": "stole my gold chain", "status_hint": "reported", "hedged": False}],
                  "evidence": [], "risks": [], "people": [], "dates": [], "personal_law": None, "correction": False,
                  "reexplain": False, "unclear": False}]
    script += [lambda p: ({"reply": "Did you allow anyone to take it?"} if "Next question" in p else
                          {"issues": [], "elements": [], "evidence": [], "risks": [], "people": [], "dates": []})] * 60
    eng = Engine(Fake(script))
    st = eng.start("en", use_llm=True, conversation_date=CONV)
    eng.handle(st, "Someone stole my gold chain from my house yesterday.")
    answer_all(eng, st)
    eng.llm.script = [lambda p: {"summary": "You said your gold chain was stolen."} if "case summary" in p else
                      {"explanation": "BNS section 303(2) may apply because you said it was taken without consent."}] * 40
    c = eng.consultation(st)
    assert c["summary"] == "You said your gold chain was stolen."
    assert any("may apply" in p["explanation"] for p in c["provisions"])
    assert any("Official text (may be empty):" in p and "do NOT state what the section says" in p for p in eng.llm.prompts)


def test_emotional_filler_is_not_a_reexplain_request(engine):
    # "समझ नहीं आ रहा क्या करूँ" = "I can't figure out what to do" inside a narrative, not "explain again"
    st = engine.start("hi", conversation_date=CONV)
    engine.handle(st, "मैंने एक ऑनलाइन शॉपिंग ऐप से एक मिक्सर ऑर्डर किया था। समझ नहीं आ रहा क्या करूँ। "
                      "खराब निकलने पर मैंने उसे वापस कर दिया, पिकअप भी हो गया, लेकिन ऐप रिफ़ंड देने से मना कर रहा है।")
    assert "con.refund_refusal" in st.issue_prior and st.questions_asked >= 1
    assert R.answer_type("I really don't know what to do, my husband took my son and I have no money left at all") is None


# ---- regressions from user testing: "the question asked is different from what I said"
LISTEN_CASES = [
    ("en", "Last Sunday my colleague attacked me outside the office with an iron rod after an argument about money. "
           "My arm is fractured and the hospital gave me a report.", "crim.hurt_assault", ["act_of_force", "injury_caused"]),
    ("hi", "मेरे पति पिछले आठ महीने से अलग रह रहे हैं और घर का कोई खर्चा नहीं देते। मेरी कोई नौकरी नहीं है और दो बच्चे हैं।",
     "fam.maintenance", ["neglect_or_refusal", "unable_to_maintain_self"]),
    ("kn", "ಪಕ್ಕದ ಹೊಲದವರು ರಾತ್ರೋರಾತ್ರಿ ನಮ್ಮ ಗಡಿ ಕಲ್ಲುಗಳನ್ನು ಸರಿಸಿ ನಮ್ಮ ಹೊಲದ ಒಂದು ಭಾಗ ತಮ್ಮದು ಅಂತಿದ್ದಾರೆ.",
     "prop.boundary_dispute", ["boundary_marks_moved", "respondent_claims_strip"]),
    ("en", "My bank statement shows two ATM withdrawals of 10,000 each from another city yesterday. My debit card is with "
           "me and I never shared the PIN.", "fin.unauthorized_bank_txn", ["txn_not_authorised", "no_customer_negligence"]),
    ("kn", "Nanna bike na yaaro night kaddkondu hogidaare, CCTV ide antha shop avru helidru.", "crim.theft", ["property_taken"]),
]


@pytest.mark.parametrize("lang,text,issue,stated", LISTEN_CASES)
def test_stated_facts_are_understood_not_reasked(engine, lang, text, issue, stated):
    st = engine.start(lang, conversation_date="2026-10-27")
    msgs = engine.handle(st, text)
    assert issue in st.issue_prior
    for el in stated:
        assert st.elements[f"{issue}|{el}"].value == "satisfied", el
    assert any(m.kind == "message" and "•" in m.text for m in msgs)          # "here is what I understood"
    asked = []
    for _ in range(12):
        if st.pending is None:
            break
        if st.pending.kind == "element":
            asked.append(st.pending.key)
        engine.handle(st, "", chip=st.pending.chips[-1].id if st.pending.kind == "element" else st.pending.chips[0].id)
    assert not any(k in asked for k in (f"{issue}|{e}" for e in stated))     # never re-asked
    assert all(k.startswith(issue + "|") for k in asked), asked              # stays on the client's issue


def test_no_false_violence_alert_for_tonight_in_sms(engine):
    st = engine.start("en", conversation_date=CONV)
    engine.handle(st, "I got an SMS saying my electricity would be cut tonight, with a link. I clicked it and entered "
                      "my net banking password. Now 40,000 rupees are gone from my account.")
    assert "imminent_violence" not in st.risks
    assert "cyb.phishing_account_takeover" in st.issue_prior


def test_free_text_negative_answer(engine):
    st = engine.start("en", conversation_date=CONV)
    engine.handle(st, "My neighbour slapped me yesterday.")
    while st.pending and st.pending.key != "crim.hurt_assault|injury_caused":
        engine.handle(st, "", chip=st.pending.chips[0].id)
    if st.pending:
        engine.handle(st, "no I was not injured")
        assert st.elements["crim.hurt_assault|injury_caused"].value == "contradicted"


def test_user_reported_land_forgery_conversation(engine):
    """Real user report: land dispute with a brother using fake documents produced bank / card questions."""
    st = engine.start("en", conversation_date="2026-10-27")
    engine.handle(st, "I am facing land issue among my own family. My brother is claiming that the land belongs to him "
                      "where he has fake documentation . But the land actually belongs to me and I have the original "
                      "documents . What should i do ?")
    assert "prop.forged_documents" in st.issue_prior
    engine.handle(st, "My brother is claiming ownership of a piece of land that I believe belongs to me. I have the original "
                      "property documents in my possession, but my brother is relying on documents that I believe may be "
                      "forged. I want to establish the legal ownership of the land and prevent any unauthorised sale or transfer.")
    asked = []
    for _ in range(12):
        if st.pending is None:
            break
        if st.pending.kind == "element":
            asked.append(st.pending.key)
        engine.handle(st, "", chip="dk" if st.pending.kind == "element" else st.pending.chips[0].id)
    assert all(kb().domain(i) == "property" for i in st.issue_prior), st.issue_prior
    assert all(k.startswith("prop.") for k in asked), asked
    assert "prop.forged_documents|false_document_made" not in asked          # already said


def test_yes_no_polarity_of_reversed_questions(engine):
    st = engine.start("en", conversation_date=CONV)
    engine.handle(st, "My cousin sold our family land without asking me.")
    st.pending = None
    from legallisten.state import Pending
    st.pending = Pending(kind="element", key="prop.coheir_sale_without_consent|no_consent", chips=[])
    engine.handle(st, "No")                       # "Did you sign or agree to this sale?" -> No = no consent
    assert st.elements["prop.coheir_sale_without_consent|no_consent"].value == "satisfied"


def test_coherence_set_stays_on_topic():
    import importlib
    import sys
    sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1]))
    mod = importlib.import_module("eval.legallisten_coherence")
    cases = [json.loads(l) for l in open(mod.ROOT / "eval" / "legallisten_coherence.jsonl", encoding="utf-8") if l.strip()]
    eng = Engine(None)
    rows = [mod.run_case(eng, c) for c in cases]
    assert sum(r["issue_ok"] for r in rows) >= 0.95 * len(rows)
    assert sum(r["off_topic"] for r in rows) <= 0.05 * max(1, sum(r["asked"] for r in rows))
    assert sum(r["asked_again"] for r in rows) == 0


# ---- follow-up questions, consultation in chat, resuming old consultations
def _finish(engine, st):
    for _ in range(25):
        if st.pending is None:
            break
        engine.handle(st, "", chip=st.pending.chips[0].id)


@pytest.mark.parametrize("lang,story,question,intent_word", [
    ("en", "My neighbour hit me with a stick yesterday and my arm is fractured.", "What should I do next?", "1."),
    ("en", "My neighbour hit me with a stick yesterday and my arm is fractured.", "Which documents do I need?", "•"),
    ("en", "My neighbour hit me with a stick yesterday and my arm is fractured.", "Where should I go?", "•"),
    ("kn", "ನಿನ್ನೆ ಪಕ್ಕದ ಮನೆಯವನು ಕೋಲಿನಿಂದ ಹೊಡೆದ, ತಲೆಗೆ ಗಾಯ ಆಯ್ತು.", "ಮುಂದೆ ಏನು ಮಾಡಬೇಕು?", "1."),
    ("hi", "कल मेरे पड़ोसी ने मुझे डंडे से मारा, मेरे हाथ में चोट आई।", "कौन-से कानून लागू होते हैं?", "•"),
])
def test_followup_answered_in_chat_after_consultation(engine, lang, story, question, intent_word):
    st = engine.start(lang, conversation_date=CONV)
    engine.handle(st, story)
    _finish(engine, st)
    assert st.consultation_ready
    assert any(m.kind == "consultation" and "\n" in m.text for m in st.messages)     # card in the chat
    msgs = engine.handle(st, question)
    ans = [m for m in msgs if m.kind == "answer"]
    assert ans and intent_word in ans[0].text, [m.text for m in msgs]
    assert not any("noted" in m.text.lower() for m in msgs)
    assert ans[0].chips                                                              # quick follow-up buttons


def test_followup_during_interview_keeps_question(engine):
    st = engine.start("en", conversation_date=CONV)
    engine.handle(st, "My brother made a fake will and changed the khata of our land into his name.")
    key = st.pending.key if st.pending else None
    msgs = engine.handle(st, "What documents do I need?")
    assert any(m.kind == "answer" for m in msgs)
    assert (st.pending.key if st.pending else None) == key                           # same question asked again
    assert msgs[-1].kind == "question"


def test_quick_chip_and_card_not_repeated(engine):
    st = engine.start("en", conversation_date=CONV)
    engine.handle(st, "Someone stole my gold chain from my house yesterday.")
    _finish(engine, st)
    n_cards = sum(m.kind == "consultation" for m in st.messages)
    msgs = engine.handle(st, "", chip="ask:where")
    assert msgs[-1].kind == "answer"
    engine.handle(st, "What should I do next?")
    assert sum(m.kind == "consultation" for m in st.messages) == n_cards          # no card spam


def test_questions_use_the_clients_words(engine):
    st = engine.start("en", conversation_date=CONV)
    engine.handle(st, "My brother made a fake will to take our land.")
    texts = []
    for _ in range(6):
        if st.pending is None:
            break
        texts.append(st.pending.data.get("text", ""))
        engine.handle(st, "", chip=st.pending.chips[-1].id)
    joined = " ".join(texts)
    assert "the will" in joined or "your brother" in joined, texts


def test_resume_old_consultation_via_api(client):
    a = client.post("/api/session", json={"lang": "en", "use_llm": False, "conversation_date": CONV}).json()
    h = {"X-Session-Token": a["token"]}
    client.post(f"/api/session/{a['session_id']}/message", headers=h, json={"text": "My neighbour hit me with a stick."})
    b = client.post("/api/session", json={"lang": "hi", "use_llm": False}).json()            # a second consultation
    r = client.get(f"/api/session/{a['session_id']}", headers=h).json()                     # reopen the first one
    assert r["summary"]["title"] and len(r["messages"]) >= 3
    r2 = client.post(f"/api/session/{a['session_id']}/message", headers=h, json={"text": "What should I do next?"}).json()
    assert any(m["kind"] == "answer" for m in r2["messages"])
    assert b["session_id"] != a["session_id"]


# ---------------------------------------------------------------- accounts
def test_accounts_register_login_and_sync(tmp_path, client):
    r = client.post("/api/auth/register", json={"name": "Asha", "email": "Asha@Example.com", "password": "short", "lang": "kn"})
    assert r.status_code == 422                                   # password too short
    r = client.post("/api/auth/register", json={"name": "Asha", "email": "asha@example.com", "password": "correct horse 1",
                                                "lang": "kn"})
    assert r.status_code == 200 and r.json()["user"]["name"] == "Asha"
    assert "httponly" in r.headers["set-cookie"].lower() and "samesite=strict" in r.headers["set-cookie"].lower()
    assert client.post("/api/auth/register", json={"name": "X", "email": "ASHA@example.com", "password": "another pass 2"}
                       ).status_code == 409                       # e-mail is case-insensitive and unique
    assert client.get("/api/auth/me").json()["user"]["email"] == "asha@example.com"
    # a consultation started while signed in is linked to the account
    s = client.post("/api/session", json={"lang": "en", "use_llm": False}).json()
    mine = client.get("/api/me/consultations").json()["consultations"]
    assert [x["id"] for x in mine] == [s["session_id"]] and mine[0]["token"] == s["token"]
    # sign out: the list is private
    client.post("/api/auth/logout")
    assert client.get("/api/auth/me").json()["user"] is None
    assert client.get("/api/me/consultations").status_code == 401
    # a guest consultation can be attached after signing in again (needs its own token)
    g = client.post("/api/session", json={"lang": "en", "use_llm": False}).json()
    assert client.post("/api/auth/login", json={"email": "asha@example.com", "password": "wrong"}).status_code == 401
    assert client.post("/api/auth/login", json={"email": "asha@example.com", "password": "correct horse 1"}).status_code == 200
    assert client.post(f"/api/me/consultations/{g['session_id']}/link", headers={"X-Session-Token": "bad"}).status_code == 404
    assert client.post(f"/api/me/consultations/{g['session_id']}/link", headers={"X-Session-Token": g["token"]}).status_code == 200
    assert len(client.get("/api/me/consultations").json()["consultations"]) == 2
    # deleting the account deletes its consultations
    assert client.delete("/api/me").json()["consultations_deleted"] == 2
    assert client.get(f"/api/session/{g['session_id']}", headers={"X-Session-Token": g["token"]}).status_code == 404
    assert client.post("/api/auth/login", json={"email": "asha@example.com", "password": "correct horse 1"}).status_code == 401


def test_store_keeps_account_data_encrypted(tmp_path, monkeypatch):
    from cryptography.fernet import Fernet
    monkeypatch.setenv("LEGALLISTEN_SECRET_KEY", Fernet.generate_key().decode())
    s = Store(tmp_path / "u.db")
    uid = s.register("priya@example.com", "s3cret password", "Priya Rao", "hi")
    raw = (tmp_path / "u.db").read_bytes()
    assert b"priya@example.com" not in raw and b"Priya Rao" not in raw and b"s3cret" not in raw
    assert s.authenticate("PRIYA@example.com", "s3cret password") == uid
    tok = s.login_token(uid)
    assert s.user_for_login(tok) == uid and s.user_for_login("nope") is None
    s.logout(tok)
    assert s.user_for_login(tok) is None


# ---------------------------------------------------------------- drafts
def test_drafts_are_grounded_in_what_the_user_said(engine):
    from legallisten import drafts
    st = engine.start("en", conversation_date=CONV)
    engine.handle(st, "My brother made fake documents and transferred our father's land into his name last year.")
    answer_all(engine, st)
    r = drafts.build(st)
    kinds = [d["kind"] for d in r["drafts"]]
    assert kinds[0] == "police" and "notice" in kinds and kinds[-1] == "aid"
    said = " ".join(m.text for m in st.messages if m.role == "user")
    for d in r["drafts"]:
        facts = [b for b in d["blocks"] if b["t"] == "fact"]
        assert facts and d["n_blanks"] > 0
        for f in facts:                              # every fact carries the user's own words as its source
            assert f["quote"] and (f["quote"].lower() in said.lower() or f["turn"] is not None)
        text = " ".join(b.get("v", "") for b in d["blocks"])
        assert "IPC" not in text                     # 2025 incident: new-law sections only
    police = r["drafts"][0]
    assert any(b["t"] == "blank" and b["id"] == "ps" for b in police["blocks"])


def test_drafts_in_kannada_and_for_consumer_cases(engine):
    from legallisten import drafts
    st = engine.start("kn", conversation_date=CONV)
    engine.handle(st, "I bought a fridge for my home for 40000 rupees, it stopped working in warranty, the showroom refused to repair it.")
    answer_all(engine, st)
    r = drafts.build(st)
    assert r["drafts"][0]["kind"] == "consumer"
    assert any("ಀ" <= ch <= "೿" for ch in r["drafts"][0]["title"] + r["drafts"][0]["where"])


def test_drafts_endpoint(client):
    s = client.post("/api/session", json={"lang": "en", "use_llm": False}).json()
    h = {"X-Session-Token": s["token"]}
    assert client.get(f"/api/session/{s['session_id']}/drafts").status_code == 404
    r = client.get(f"/api/session/{s['session_id']}/drafts", headers=h).json()
    assert r["ready"] is False and [d["kind"] for d in r["drafts"]] == ["aid"]
