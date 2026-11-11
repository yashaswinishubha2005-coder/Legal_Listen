# LegalListen — system documentation (v0.1)

LegalListen is a lawyer-like, multilingual (Kannada · English · Hindi, plus romanised / mixed Kanglish and
Hinglish) legal pre-consultation web application. It listens to a client's story by voice or text,
cross-questions adaptively, builds a **Legal Case Graph**, identifies potentially applicable provisions,
explains them in the client's language and produces a final consultation. It is built on the
**LexVaani-IN** benchmark in this repository: the issue library, element definitions, provision registry,
multilingual lexicon, Bayesian question oracle and the dataset used to train its offline NLU.

> Preliminary legal information only — not legal advice. All provision mappings are **TO_VERIFY** until a
> lawyer checks them against the official text (see §9).

## 1. Run it

```bash
make setup                 # Python 3.11 venv + pinned dependencies
make train-nlu             # trains the offline NLU on LexVaani-IN (≈3 min; models/legallisten_nlu.joblib)
cp .env.example .env       # optional: add GEMINI_API_KEY=... for LLM mode and server speech recognition
make serve                 # http://localhost:8000
```

Docker: `docker build -t legallisten . && docker run -p 8000:8000 --env-file .env legallisten`.

Without an API key, LegalListen runs fully offline (rule + trained-classifier NLU, template explanations,
browser speech recognition). With `GEMINI_API_KEY`, the client can opt in (consent checkbox) to LLM
extraction, natural question phrasing, plain-language explanations, case summaries and server-side speech
recognition (Gemini audio input).

## 2. The client journey → where it is implemented

| Spec step | Implementation |
|---|---|
| 1. Explain the problem (voice / text, any supported language) | `static/app.js` (Web Speech API `kn-IN` / `hi-IN` / `en-IN`, or recording → `/api/transcribe` → Gemini); `nlu/rules.py` detects script/variant (`kn`, `hi`, `en`, `kn-en_latn`, `kn-en_mixed`, `hi-en_latn`) |
| 2. Understand before advising | `nlu/extract.py` → issue hypotheses, element statements, evidence, risks, people, dates, money. No provision is shown until an issue is *identified* (posterior ≥ 0.5) |
| 3. Ask like a lawyer | `policy.py` (adaptive cross-questioning, §4); answer options rendered from the issue library in the client's language; free-text answers understood |
| 4. Build the Legal Case Graph | `graph.py` (§5), updated after every turn; shown live as a left-to-right **case map** (People → What happened & evidence → Legal requirements → Legal issues → Laws) with status colours, click-to-highlight, zoom, full-screen and an optional statements column |
| 5. Identify laws and sections | `provisions.py`: candidate provisions of identified issues, routed by incident date (IPC/CrPC before 1 July 2024, BNS/BNSS after), personal law and risk |
| 6. Explain the law clearly | provision cards: what the law says (official text **only** from the parsed corpus), what it means, why it may apply (linked facts + their status), how it could help, conditions still open, where to verify; buttons *Explain more simply* (with a hypothetical example) and *Why this section?* |
| 7. Final consultation | `consult.py`: summary, issues, graph insights, laws, options (marked as possibilities, not outcomes), evidence checklist, next steps, authorities, unresolved questions, contradictions, risks/urgency, lawyer summary; download `.md` / `.json`, print to PDF |
| 8. Continue with new information | every new message updates the state, graph and consultation; when the consultation is ready a **compact consultation card appears in the chat** (and again, only when something changed). Follow-up questions — *what should I do next, which documents, where to go, which laws, explain <section>, time limits, lawyer / legal aid, what is <term>* — are **answered in the chat** (`followup.py`, from the case's own consultation; LLM-written but grounded in LLM mode). Questions during the interview are answered and the pending question is asked again. **My consultations** (📁) lists every consultation saved on this device; any of them can be reopened with its full chat, graph and consultation and continued |

## 3. Understanding the client (NLU)

**LLM mode (Gemini, opt-in).** `prompts/legallisten_extract_v1.md` asks for strict JSON; every issue /
element / evidence / risk id is validated against the LexVaani-IN issue library; each fact must quote the
client's own words (kept in the original language and script, with an English gloss for the lawyer); a fact
whose quote is not in the message is downgraded to `inferred`. Rule-detected risks are always kept as a
safety net. Any LLM error falls back to the offline NLU.

**Offline mode.** Two classifiers trained on the LexVaani-IN *train* split (`nlu/train.py`,
character 2–5-grams + word 1–2-grams, logistic regression):
* issue model (25 issues + out-of-scope + non-legal; multi-label), and
* sentence model (247 classes: element × polarity, evidence held/missing, risk facts, none),
plus multilingual rules (`nlu/rules.py`): dates (absolute, relative, Kannada/Hindi month names, number words,
`kal`/`ನಿನ್ನೆ`/`परसों` …), money, kinship and role nouns from the lexicon, yes / no / don't-know answers,
corrections, "I did not understand" requests, risk cues and co-occurrence issue cues
(`resources/legallisten/guidance.yaml`). Kannada/Devanagari cues must start a word, so `ಮಗ` (son) never
matches inside `ನಮಗೆ`.

**Preserving meaning.** Voice input is always shown as editable text before sending; low recogniser
confidence (< 0.6) or an LLM "unclear" flag makes LegalListen read back what it understood and ask for
confirmation instead of guessing. Facts store the client's original words.

## 4. Adaptive cross-questioning (core innovation)

**Listening first.** Before choosing a question, every sentence the client wrote is matched against
multilingual cue phrases for each legal element (`resources/legallisten/element_cues.yaml`, negation-aware:
"he did not hit me" ≠ "he hit me"). Recognised facts are confirmed back in the client's language
("Here is what I understood: • Injury: Yes, I was injured … tell me if anything is wrong") and are **never asked
again**. Only issues the client's own words point to are explored: every issue has anchor words (`guidance.yaml: anchors`) — e.g. a bank issue needs bank / account / card words, so "unauthorised sale of land" can never lead to questions about card PINs. A new issue raised later in the conversation needs a stronger cue (same legal area 0.6, other area 0.7). Each issue is opened with its defining event ("has the land been sold, or only threatened?") before detail questions. When the client's words point to a legal area but not to one problem, LegalListen asks which problem is closest instead of guessing. Statements that answer no question are noted in the case and shown in the consultation. For yes/no questions where "yes" means the requirement is *not* met ("Did you sign the sale?"), the meaning is fixed per question.
Answer buttons use short neutral labels (`element_labels.yaml`), and typed answers are understood too.


`policy.py` ranks every possible next question each turn:

1. **Unresolved contradictions** first ("Earlier you said … Now you said … Which is correct?").
2. **Safety check** after a personal-safety risk (imminent violence, ongoing abuse, threat to life, self-harm,
   child removal); risk alerts with helplines are shown immediately for every risk flag.
3. **Information value** of element questions — the LexVaani-IN Bayesian oracle
   (`lexvaani/dialogue/oracle.py`, `docs/tasks.md` §T9): expected reduction in uncertainty about which issue
   applies + uncertainty about the element weighted by the issue's probability, doubled for critical elements.
   Hypotheses are the detected issues plus their *confusable* issues (e.g. inheritance vs co-heir sale vs forged
   documents), so a question that separates them scores high — "has the land already been sold, or only
   threatened?" changes which remedies apply.
4. **Routing questions** that change the applicable law: incident date (old vs new criminal laws) and personal
   law (Hindu / Muslim / Christian / Special Marriage Act; skippable).
5. **Evidence questions** that can turn a reported claim into an evidence-supported one.
6. **Stop** when no question is worth asking (score < 0.25) or after 16 questions; the client can ask for the
   consultation at any time and keep adding information afterwards.

Each question shows *why it is asked* ("this is one of the key facts the law looks at for …").

On the LexVaani-IN test split LegalListen asks on average **2.4 questions** at the same accuracy as a fixed questionnaire (issue F1 0.98), because facts the client already stated are recognised and not asked again (reports/legallisten_eval.md).
questionnaire with **about half the questions** (4.1 vs 8.6 on average; reports/legallisten_eval.md).

Conversation coherence on 40 natural, hand-written client messages (formal and informal, all languages): correct issue 40/40, off-topic questions 0 %, already-stated facts asked again 0 (`make` target: `python -m eval.legallisten_coherence` → reports/legallisten_coherence.md; developer-written, used for tuning).

## 5. Legal Case Graph

Node types: Person / Organization (client, relatives, respondents, police, bank …, with kinship to the client),
Event (with date, negated/hypothetical), Claim (the client's statement, original words), Evidence (held /
missing), Issue (with posterior probability), Element (legal requirement and its value), Provision,
Question (missing information), Contradiction, Risk.

Edges: `KIN_OF`, `INVOLVED_IN`, `ASSERTS`, `ABOUT`, `BEARS_ON`, `SUPPORTS`, `HOLDS`, `HAS_ELEMENT`, `MISSING`,
`APPLIES_TO`, `RELEVANT_BECAUSE`, `CONTRADICTS`, `BEFORE`, `RAISES`.

Claim status: `reported` · `evidence_supported` (held evidence supports it) · `inferred` (LLM, not in the
client's words) · `conflicting` (contradicted by another statement) · `unknown` · `corrected`. An edge records a
connection, never proof. `graph.validate()` checks edge types, dangling edges, temporal acyclicity, and that
every evidence-supported claim has a `SUPPORTS` edge and every conflicting claim a `CONTRADICTS` edge
(100 % of evaluated graphs pass).

## 6. Laws, accuracy and verification

* Provisions come **only** from the LexVaani-IN issue library / provision registry — never generated.
* Official section text is shown **only** if it was parsed from an official bare-act PDF into
  `data/corpus/provisions.jsonl` (2,811 sections from 18 India Code PDFs). Each card names the PDF and page.
  A sub-section citation (e.g. `BNS:318(4)`) shows the full parent section and says so. The parser removes
  only India Code page stamps and the amendment footnotes printed at the foot of a page (a block is cut only
  when every note in it reads like "Subs. by Act … (w.e.f. …)"); the law text itself is never altered.
  Sections without text (CrPC, Limitation Act schedule articles) say so and link to India Code.
* The LLM explanation prompt forbids stating section text, punishments, fines, time limits or case law that
  is not in the supplied official text, keeps the official Act name and section number verbatim, and must say
  "may apply" with the open conditions.
* To load official text: put the PDFs in `data/raw/acts/` (names in `reports/corpus_parse_report.md`), run
  `make corpus`, verify entries in `reports/provision_verification.md`, restart the server.

## 6a. Ready-to-file drafts (`drafts.py`, `GET /api/session/{id}/drafts`)

Built only from the Legal Case Graph: each sentence is fixed template wording, a fact the user stated
(carrying the quote and the message it came from — tap it in the Drafts tab to see and jump to it), or a blank.
Unconfirmed points are listed, never written in. Which drafts appear depends on the identified issues:
police complaint (criminal, cyber, domestic violence, dowry, loan-recovery harassment, forgery, encroachment),
bank complaint (unauthorised transactions), consumer complaint (e-Daakhil), legal notice (property), and a
free-legal-aid application (always). Old/new-law sections follow the incident date. Blanks the user fills stay
in their browser; a value typed once (name, address) fills every draft. Download as .txt or print / save as PDF.

## 6b. Accounts (optional)

`/login` offers sign-in, account creation, or "Continue as guest" (consultations saved on that device only).
Passwords are hashed with scrypt; the e-mail is stored as a keyed hash (lookup) and encrypted (display); the
name is encrypted; the login token is an HttpOnly, SameSite=Strict cookie stored only as a hash; login and
sign-up are rate-limited. A signed-in user's consultations are linked to the account and listed on any device;
guest consultations on the device are attached on sign-in; signing out removes the account's cases from the
device; "Delete my account" removes the account and every consultation. `/about` explains the system.

## 7. Languages

UI, questions, answer options, alerts, guidance and consultation are available in English, Kannada and Hindi
(language can be switched mid-consultation; the graph and consultation re-render). Input may be any of the six
LexVaani-IN variants. In LLM mode, replies and explanations are generated in the chosen language with simple
words; in offline mode they are template-based. Kannada/Hindi strings are **pending native-speaker review**.

## 8. Privacy and safety

* Session data is stored server-side in SQLite, **encrypted at rest** (Fernet; key from
  `LEGALLISTEN_SECRET_KEY` or a generated 0600 key file), accessible only with the session's random token
  (only its hash is stored), auto-deleted after `LEGALLISTEN_RETENTION_DAYS` (default 30), and deletable at
  any time ("Delete my data").
* Text is sent to an LLM provider only if a key is configured **and** the client ticks the consent box.
  LegalListen never caches consultation text from LLM calls and logs only token counts.
* Security headers (CSP, no framing, no referrer), no third-party scripts, rate limiting, input size limits.
* Risk alerts (112, 181, 1930, 1098, 14416, NALSA 15100, …) are shown before any other content.
* Urgent cases are triaged `urgent`; every consultation recommends a lawyer / free legal aid where relevant
  and states that it does not replace professional judgment.

## 9. Datasets, models and their limits

| Component | Source |
|---|---|
| Issue library, elements, questions, provision candidates, lexicon, glossary | LexVaani-IN `resources/` (hand-built; TO_VERIFY) |
| Offline NLU training data | LexVaani-IN v0.1.0 **train** split (2,778 clean + 550 ASR-noisy narratives) + rendered library templates |
| Evaluation data | LexVaani-IN **test** split (1,014 narratives, 6 variants) + 36 hand-written free-form narratives |
| Question selection | LexVaani-IN Bayesian oracle (`lexvaani/dialogue/oracle.py`) |
| LLM (optional) | Google Gemini via REST (`LEGALLISTEN_MODEL`, default `gemini-2.5-flash`); Anthropic / OpenAI also supported |
| Speech | Browser Web Speech API (offline mode) or Gemini audio transcription (LLM mode) |
| Speech output | Browser speech synthesis (Kannada voice availability depends on the device) |

Limits: the offline classifiers are trained on template text and are much weaker on free, real-world language
than the template test scores suggest; the free-form probe set was written by the developers and also used while
tuning the rule cues, so its scores are optimistic; Kannada/Hindi text needs native review; no official law text
is loaded yet; no real-user study or IAA has been done. LLM mode has been tested with a scripted fake model and
the request format follows the Gemini REST API, but it was not run against the live API in this build (no key in
the build environment).
