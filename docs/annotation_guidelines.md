# LexVaani-IN Annotation Guidelines (v0.1)

**Who this is for:** annotators, adjudicators and reviewers who label, check or correct LexVaani-IN data,
including the human-written `test_human/` set. You should be able to label any item **without asking
anyone**: every label has a definition, decision rules, edge cases, and positive (✔) and negative (✘)
examples. When this document and the schema code disagree, the code is a bug: report it.

Read §0 to §2 once fully; then use the task sections (§T1 to §T13) as a reference while labelling.

---

## 0. Golden rules

1. **Label what the text says, not what you believe happened.** If the user says "I think he took it",
   the claim is hedged and *reported*; you do not decide whether it is true.
2. **Never use outside legal knowledge to add facts.** Legal knowledge is used only to decide which
   *element* a stated fact bears on (§T7) and which provision *candidate* applies (§T10).
3. **When unsure between two labels, apply the decision rules in order; if still unsure, choose the
   more conservative label** (`unknown` over `satisfied`, `reported` over `evidence_supported`,
   `lawyer` over `self_help`, `urgent` over `lawyer`) **and flag the item** (`needs_adjudication`).
4. **Spans are exact.** Copy offsets, never retype text. Spans never start or end with whitespace.
5. **No real personal data.** All names are synthetic. If you ever see something that looks like a real
   person, phone number, address or account number, stop and flag the item.
6. **Provisions are TO_VERIFY** until a human has checked them against the official text (Gate 1).

---

## 1. Global conventions

### 1.1 Text units and offsets
- A **text unit** is one narrative (`sample_id`) or one dialogue turn (`<dialogue_id>#t<index>`).
- Text is Unicode **NFC**. Offsets are Python string indices (Unicode code points), half-open `[start, end)`.
  Kannada and Devanagari conjuncts are several code points: always select with the tool, never count by eye.
- Every span must satisfy `text[start:end] == span.text`; QC rejects anything else.

### 1.2 Span boundaries
- **Whole orthographic words.** A span starts and ends at word boundaries, except for cues/triggers inside a
  word when the language fuses them (see 1.3).
- **Fused case suffixes are inside the span**; **separate postposition words are outside**:

| Text | Span | Why |
|---|---|---|
| ನಮ್ಮ ಚಿಕ್ಕಪ್ಪನಿಗೆ ಹೇಳಿದೆ | `ನಮ್ಮ ಚಿಕ್ಕಪ್ಪನಿಗೆ` | dative suffix ‑ಗೆ is fused |
| ರಮೇಶ್ ಅವರಿಗೆ ಹೇಳಿದೆ | `ರಮೇಶ್` | ಅವರಿಗೆ is a separate (honorific pronoun) word |
| रमेश ने मारा | `रमेश` | ने is a separate postposition |
| उन्होंने मारा | `उन्होंने` | pronoun + ergative are one word |
| police station ge hode | `police station` | ge written separately |
| my uncle's house | `my uncle` | the English possessive `'s` stays outside |

- **Determiners and possessives belong to nominal mentions**: `my neighbour Sunanda`, `the shopkeeper`,
  `ನಮ್ಮ ಚಿಕ್ಕಪ್ಪ`, `मेरे पति`. Prepositions do not: in `near the market` the span is `the market`.
- **Trailing punctuation is outside** every span except a whole-sentence claim span (§T6), which includes
  its final punctuation.

### 1.3 Fused negation and light verbs
Kannada fuses negation into the verb (`ಹೊಡೆಯಲಿಲ್ಲ` = did not hit, `ಗೊತ್ತಿಲ್ಲ` = do not know). Then the
**whole word** is both the event trigger (§T3) and the negation cue (§T6). In Hindi the negator is a separate
word (`मारा नहीं`): the trigger is `मारा`, the cue is `नहीं`.

### 1.4 Who and what is annotated
- **The speaker (first person) is never an entity mention**: `I`, `ನಾನು`, `मैं`, `my` are not tagged.
- **Case participants only.** PERSON/ORGANIZATION spans are annotated for people and institutions that take part
  in the case (respondents, the police station the user went to, the bank, the buyer, the child in a custody case).
  **Incidental mentions of non-participants are not annotated** (e.g. "my relatives" in "sent it to my relatives",
  "my friends", "my mother" mentioned once as background).
- **Generic mentions are not annotated** ("a hospital", "any senior officer", "the courier company" in a scam
  pretext, "social media").
- **Apps used as a medium are not entities** ("on WhatsApp", "through UPI"); a platform that *acts* in the case
  (refuses a refund, receives a report) is an ORGANIZATION ("the online shopping app refused").
- **Witnesses cited as proof are EVIDENCE**, not PERSON ("two people from the tea shop saw everything").

### 1.5 Language variants
| Code | Variant | Notes |
|---|---|---|
| `en` | Indian English | |
| `kn` | Kannada, Kannada script | colloquial Bengaluru/Mysuru register |
| `hi` | Hindi, Devanagari | |
| `kn-en_latn` | Kanglish, Latin script | spellings vary (*hodedru / hodedaru*); do not normalise |
| `kn-en_mixed` | Kannada script + English words in Latin | e.g. `ನನ್ನ complaint ಕೊಟ್ಟೆ` |
| `hi-en_latn` | Hinglish, Latin script | |

**Honorific plural.** In Kannada and Hindi, adults and organisations are referred to with the honorific
plural (`ಅವರು ಮಾಡಿದರು`, `वो आए`, `उन्होंने`), which is gender-neutral in Kannada. A plural form therefore does
**not** imply several people; resolve it by coreference (§T5).

### 1.6 Kinship terms
Normalise the relation of the person **to the speaker** (`KIN_OF` edge, ontology §3). Keep the surface term.

| Surface | Relation | Rule |
|---|---|---|
| ಚಿಕ್ಕಪ್ಪ / ದೊಡ್ಡಪ್ಪ, chikkappa / doddappa, चाचा / ताऊ | paternal_uncle | record younger/elder in `seniority` if stated |
| ಸೋದರಮಾವ, मामा | maternal_uncle | |
| **ಮಾವ / maava** | father_in_law **or** maternal_uncle | father_in_law if a marriage of the speaker is in context ("my husband's father", in-laws, dowry); maternal_uncle if the mother's side is in context; otherwise `unresolved` and flag a missing-info question |
| ಅತ್ತೆ / atte | mother_in_law **or** paternal aunt | same rule as maava |
| ಮೈದುನ, देवर | brother_in_law (husband's younger brother) | |
| ಭಾವ / bhaava, जीजा | brother_in_law (sister's husband) | |
| ಅಣ್ಣ / ತಮ್ಮ, भाई | brother (elder / younger) | |
| ಅಕ್ಕ / ತಂಗಿ, बहन / दीदी | sister | |
| ದೊಡ್ಡಪ್ಪನ ಮಗ, चचेरा भाई, cousin | cousin | |
| ಗಂಡ, पति, husband / ಹೆಂಡತಿ, पत्नी, wife | husband / wife | |

✘ Do not infer kinship from a shared surname or from living in the same house.

---

## T1 Legal issue identification

**Label:** the set of library issues the narrative *raises*, plus `x.out_of_scope` or `x.non_legal` when no
library issue applies. An issue is raised when the user states facts that fall within the issue's subject
matter, **even if an element is unknown or contradicted** (element status is T7's job).

| Issue id | Raise when the user describes… | Do NOT raise when… |
|---|---|---|
| crim.hurt_assault | someone hitting/pushing/injuring them | only shouting / argument (→ check intimidation) |
| crim.criminal_intimidation | a threat to harm person, reputation or property | a joke nobody took seriously is still raised (element contradicted); vague dislike without a threat |
| crim.theft | movable property taken without consent | the user handed it over because of a lie (→ cheating) |
| crim.cheating | a false promise/representation that got them to hand over money/property | an honest business loss is still raised (element contradicted) |
| crim.police_refusal_fir | police refusing to register their complaint | the user has not gone to the police yet |
| fam.divorce | wanting to end a marriage | separation without any wish to end the marriage (→ maintenance?) |
| fam.maintenance | spouse not supporting them financially | |
| fam.custody | dispute over who keeps a child | |
| fam.domestic_violence | abuse by husband/his relatives in a domestic relationship | violence by a stranger (→ hurt) |
| fam.dowry_harassment | demand of money/property connected to marriage, harassment for it | gifts given voluntarily with no demand or harassment (element contradicted) |
| prop.inheritance_partition | wanting a share of family/ancestral property | |
| prop.encroachment | someone occupying/building on their land | only a disagreement about the line (→ boundary) |
| prop.coheir_sale_without_consent | a co-owner selling (or threatening to sell) joint property | a sale by the sole owner |
| prop.boundary_dispute | dispute about where the boundary lies / moved boundary marks | |
| prop.forged_documents | fake will/deed/signature used to claim property | |
| cyb.upi_payment_fraud | being tricked into authorising a digital payment | an unauthorised debit without the user's action (→ fin.unauthorized_bank_txn) |
| cyb.phishing_account_takeover | fake link/message stealing credentials, account taken over | |
| cyb.impersonation | a fake profile/identity of the user | |
| cyb.cyberstalking | repeated unwanted online contact/monitoring of a woman | one message (still raised; element contradicted) |
| cyb.morphed_intimate_image | morphed/intimate images made or shared without consent | |
| con.defective_product | a defective product bought for own use | |
| con.deficiency_in_service | a paid service falling short | |
| fin.unauthorized_bank_txn | transactions the user did not make | |
| con.refund_refusal | refusal to refund a returned product | |
| fin.loan_recovery_harassment | abusive/shaming recovery tactics | |
| **x.out_of_scope** | a *legal* problem not in the library: tenancy/eviction, wages, cheque bounce, motor accident, RTI, termination, pension, adoption | — |
| **x.non_legal** | no legal angle: exams, diet, a friendly quarrel without threats, phone problems | — |

**Multi-issue.** Label every issue raised (cross-domain is common: DV + dowry; UPI fraud + police refusal).
**Never** combine `x.*` with library issues.

✔ "My neighbour hit me with a stick and said he'll come back tonight" → `crim.hurt_assault` (+ a risk flag; the
threat may also raise `crim.criminal_intimidation` if it is a threat of harm — here it is, so label both).
✘ "My friend and I had a small argument about cricket" → not intimidation: `x.non_legal`.

**Domain** = the domain(s) of the labelled issues (criminal, family, property, cyber, consumer_financial).

---

## T2 Entity extraction

| Type | Definition | ✔ Examples | ✘ Not this type |
|---|---|---|---|
| PERSON | a case participant (name, nominal, or third-person pronoun referring to one) | `my neighbour Sunanda`, `ನಮ್ಮ ಚಿಕ್ಕಪ್ಪ`, `उन्होंने`, `avru`, `someone` (an unknown thief) | the speaker; `my relatives` (incidental) |
| ORGANIZATION | an institution acting in the case | `the police station`, `ಬ್ಯಾಂಕ್‌ನವರು`, `the app` (that refused), `[They]` = the police | "a hospital" (generic) |
| LOCATION | a place where an event happened | `the market`, `ನಮ್ಮ ಮನೆ`, `बस स्टैंड` | "at home" inside "I found it at home" is not annotated (not an event location in v0.1 templates) |
| ASSET | property/goods in the case | `my gold chain`, `ನಮ್ಮ ಮನೆ ಸೈಟ್`, `a washing machine` | "it", "ಅದು" (asset pronouns are not annotated) |
| MONEY | an amount | `₹45,000`, `ನಲವತ್ತೈದು ಸಾವಿರ ರೂಪಾಯಿ`, `pachaas hazaar rupaye` | "some money" |
| TIME | a temporal expression (same spans as T4) | `yesterday`, `ಹೋದ ಯುಗಾದಿ`, `14 March 2025`, `every day`, `three weeks` | "later", "then", "yet", "as soon as" |
| ACCOUNT | a bank/UPI/social account of the user | `my UPI account`, `[ನನ್ನ ಅಕೌಂಟ್‌ನಿಂದ]` | "net banking" as a concept |
| IDENTIFIER | an ID number | the transaction number `482910375512`, survey number `45/2` | "the 1930 helpline" (part of an ORG name) |
| EVIDENCE | a mention of proof the user has or lacks | `the doctor's report`, `screenshots of the fake profile`, `[no] witnesses` | the act of recording ("I recorded it") |

**Boundaries.** MONEY includes number words, unit and currency (`forty-five thousand rupees`). TIME excludes
prepositions/postpositions (`on 14 March 2025` → `14 March 2025`; `ಮಾರ್ಚ್ 14, 2025 ರಂದು` → `ಮಾರ್ಚ್ 14, 2025`).
EVIDENCE excludes negation words when they are separate (`[no](NEG) [medical report](EVD)`).

**Mention kinds** (attribute): `name`, `nominal`, `pronoun`, `value`.

---

## T3 Event and argument extraction

An **event** is a legally relevant happening or state change: an assault, a threat, a payment, a sale, a refusal, a
report to the police… Each mention is labelled with its trigger, type and arguments.

**Trigger:** the minimal predicate expressing the event, including light-verb constructions and fused negation:
`[hit]`, `[ಹೊಡೆದರು]`, `[गया]`, `[ಗಾಯ ಆಯ್ತು]` (got injured), `[complaint kotte]` (gave a complaint),
`[stopped answering]`, `[मना कर दिया]` (refused).

**Event types used in v0.1** (inventory; extend only through the issue library):
physical_assault, injury, threat, theft, false_promise, payment, evasion, police_complaint, approach_police, refusal,
written_complaint, marriage, separation, support_stopped, child_taken, physical_abuse, dowry_given, dowry_demand,
harassment, share_denial, encroachment, sale_transfer, boundary_marks_moved, forgery, khata_change, fraud_call, debit,
cyber_report, phishing_message, credential_entry, account_takeover, fake_profile, deceptive_messages, platform_report,
repeated_messaging, image_morphing, image_sharing, product_failure, remedy_refusal, service_outage, provider_complaint,
bank_report, reversal_refusal, product_return, refund_refusal, harassment_calls, contact_shaming,
and for out-of-library scenarios eviction_demand, cheque_dishonour, road_accident, rti_filed, termination.

**Arguments** (only if expressed in the same sentence): `agent`, `patient`, `recipient`, `instrument`, `beneficiary`,
`witness`, `place` (a LOCATION), `time` (the TIMEX of this event).

**Negated / hypothetical.**
- *Negated:* the user says it did **not** happen: "he [never] actually [hit] me" → event `physical_assault`,
  negated. Still annotate it: the negation is legally decisive.
- *Hypothetical:* threatened or planned, not yet happened: "he is threatening to [sell] the site but has not sold it"
  → `sale_transfer`, hypothetical. (The threat is a separate fact.)

✔ "{DATE} my cousin Nagaraj threatened that he would break my legs" → trigger `threatened`, type threat,
agent = `my cousin Nagaraj`, time = the date.
✘ Do not annotate "I am really scared" or "What should I do now?" as events.

---

## T4 Temporal normalisation and ordering

### 4.1 TIMEX values (TIMEX3 style)
Resolve relative expressions against the **conversation date** (given with each item).

| Expression | Value | Example (conversation date 2025-09-10) |
|---|---|---|
| absolute date | `YYYY-MM-DD` | "14 March 2025" → `2025-03-14`; "on 14 March" (no year) → current year `2025-03-14` |
| month | `YYYY-MM` | "in March 2025", "ಮಾರ್ಚ್ 2025 ರಲ್ಲಿ" → `2025-03` |
| year | `YYYY` | "last year", "ಹೋದ ವರ್ಷ", "पिछले साल" → `2024` |
| today / yesterday / day before | exact date | "ninne", "kal" (past context), "ಮೊನ್ನೆ", "परसों" (past) |
| N days ago | exact date | "three days ago", "ಮೂರು ದಿನದ ಹಿಂದೆ" → `2025-09-07` |
| last week | ISO week | "last week", "ಹೋದ ವಾರ" → `2025-W36` |
| N months back | `YYYY-MM`, **approximate** | "2 months back", "do mahine pehle" → `2025-07` |
| festival | date of the most recent occurrence, **approximate** | "around last Ugadi" → `2025-03-30` |
| vague past | `PAST_REF`, approximate | "some time back", "kuch time pehle" |
| night / morning | `YYYY-MM-DDTNI` / `TMO` | "tonight", "ಇವತ್ತು ರಾತ್ರಿ" → `2025-09-10TNI` |
| future | resolved date / week | "tomorrow", "ನಾಳೆ" → `2025-09-11`; "next week" → `2025-W38` |
| now | `PRESENT_REF` | "right now", "ಈಗ", "अभी" |
| duration | ISO duration (type duration) | "three weeks" → `P3W`; "48 hours" → `PT48H`; "two years" → `P2Y` |
| set | ISO duration (type set) | "every day", "ಪ್ರತಿ ದಿನ" → `P1D`; "every month" → `P1M` |

**Ambiguity rules.**
- Hindi **kal / कल** = yesterday *or* tomorrow; **parson / परसों** = day before yesterday *or* after tomorrow:
  decide by tense (past verb → past). ✔ "कल उन्होंने मारा" → yesterday. ✔ "[कल](tomorrow) तक घर छोड़ने को कहा" → tomorrow.
- Kannada **monne / ಮೊನ್ನೆ** literally "day before yesterday" but often "the other day": annotate the literal value
  and mark `approximate` if the context makes it vague.
- "Since then", "later", "as soon as", "yet", "already" are **not** TIMEX.
- Festival dates are approximate and must be checked against a panchanga (TO_VERIFY in the lexicon).

### 4.2 Temporal links
Between pairs of **asserted** events (not negated, not hypothetical) mentioned in the text, label `BEFORE`
(source ends before target starts) or `OVERLAP` (same day / overlapping). `AFTER(a,b)` is allowed in predictions and
normalised to `BEFORE(b,a)`. Use explicit dates first, then explicit connectives ("before all this", "ಅದಕ್ಕೂ ಮುಂಚೆ",
"उससे पहले", "after taking the money"), then narrative logic (an injury cannot precede the assault causing it).
✔ "I got a cut on my head… Oh, I forgot to say, before all this, she hit me" → hit BEFORE/OVERLAP injury (same day → OVERLAP).

---

## T5 Coreference

- **Mentions:** every PERSON and ORGANIZATION mention from T2 (names, nominals, pronouns, honorific pronouns such
  as `ಅವರು / avru / वो / उन्होंने`, organisation pronouns such as `[They]` referring to the police).
- **Clusters:** all mentions of the same participant, across the whole narrative or the whole dialogue.
- **Honorific plural** (`ಅವರು`, `वो`) usually refers to one adult; link it to the most recent compatible participant.
  If two participants are equally possible (DV cases with husband and mother-in-law), use verb agreement and
  content; if still ambiguous, link to the most recent and flag.
- **Kin nominals** corefer with names: `ನಮ್ಮ ಚಿಕ್ಕಪ್ಪ ರಮೇಶ್` … `ರಮೇಶ್` … `ನಮ್ಮ ಚಿಕ್ಕಪ್ಪ` … `ಅವರು` → one cluster.
- **The speaker is not annotated**, so there is no speaker cluster.
✘ Do not link "the police" with "the SP office" (different organisations); do not link "someone" (thief) with a later
named suspect unless the user says they are the same person.

---

## T6 Epistemic status, hedging and negation

A **fact** (claim) is one assertion, usually one sentence (the claim span includes the hedge but excludes a leading
filler such as "Actually," or a flashback marker such as "Oh, I forgot to say, before all this,").

### 6.1 Decision tree (apply in order)
1. Does another statement in the same text/dialogue say the opposite about the same fact (self-contradiction, or
   contradicting evidence)? → **conflicting** (both claims), linked by CONTRADICTS.
2. Is the claim a user statement of not knowing ("I don't know", "ಗೊತ್ತಿಲ್ಲ", "पता नहीं")? → **unknown**.
3. Does the user say they **hold or can obtain** evidence that supports *this* claim (same element), and the claim is
   positive (the thing happened)? → **evidence_supported**. Missing evidence ("I have no receipt") does **not** support.
4. Is the claim stated (directly or hedged) by the user? → **reported**.
5. Is it not stated but follows necessarily from stated facts (system-level: Issue and Element nodes)? → **inferred**.

✔ "I paid through UPI, so I have the transaction details" + "Believing him, I paid ₹45,000" → the payment claim is
**evidence_supported**. ✔ Same story with "I paid in cash, and I have no receipt" → **reported** (this is a
minimal pair). ✔ "Nobody has asked us for any dowry" + later "{DATE} my mother-in-law demanded…" → both **conflicting**.

### 6.2 Hedging
`hedged = true` when the user marks uncertainty: *I think, maybe, I'm not fully sure, but*, `ಅನ್ಸುತ್ತೆ`, `ಬಹುಶಃ`,
`anstide`, `मुझे लगता है`, `शायद`, `shayad`. Annotate the cue span. A hedged claim keeps its status (usually
reported); hedging is **not** "unknown".

### 6.3 Negation cues
Annotate every negation word inside a claim: *not, no, never, nothing, nobody, without, non-*, `ಇಲ್ಲ`, `ಅಲ್ಲ`,
fused negative verbs (`ಹೋಗಿಲ್ಲ`, `ಕೊಡಲಿಲ್ಲ`, `ಗೊತ್ತಿಲ್ಲ`, `ಬೇಡ`, `ಕೊಡದೆ`), `नहीं`, `न`, `बिना`, `nahi`, `na`, `bina`.
A negation cue does **not** by itself make the element contradicted ("he did it on purpose, it was **not** an
accident" *satisfies* intention).

---

## T7 Legal element satisfaction

For every element of every labelled issue (inventory: issue library), assign:

- **satisfied** — the text establishes the element (e.g. "my neighbour hit me" → act_of_force).
- **contradicted** — the text establishes that the element is **not** met ("he only shouted, but never hit me").
- **unknown** — not stated; or the user says they do not know; **or the user contradicts themself** about it.

Rules:
1. Judge **only from the given unit** (narrative, or the dialogue up to that point). A fact revealed later in the
   dialogue does not change the narrative-level label.
2. **A correction replaces** the corrected statement ("Sorry, I said it wrong — it was 50 thousand").
3. **Self-contradiction without correction → unknown** (and both claims conflicting).
4. Hedged statements count ("I think he took it" → satisfied, hedged).
5. Do not reason beyond the element definition: an injury being "minor" does not contradict `injury_caused`.

Critical elements are marked in the library. The `incomplete` variation always has at least one critical element
`unknown`.

---

## T8 Case Graph construction

Build the graph defined in `docs/ontology.md`:
1. Person/Organization/Asset/Account nodes for every participant (with mention spans); the speaker is `per_0`.
2. `KIN_OF` from each relative to the speaker (§1.6).
3. Event nodes for every event (trigger spans), `PARTICIPANT_IN` for arguments, `BEFORE`/`OVERLAP` between asserted
   events, `CAUSES` only where an element definition says so (injury caused by assault).
4. Claim nodes for every fact (§T6) with `ASSERTS` from the speaker and `ABOUT` to its event (or the respondent).
5. Evidence nodes for every evidence mention, `HOLDS` if held/obtainable, `SUPPORTS` to the claims it supports.
6. Issue nodes (§T1), Element nodes with their T7 value, `HAS_ELEMENT`, and `SATISFIES` / `REFUTES` from claims or
   `LACKS` from the issue for unknown elements.
7. Provision nodes (§T10) with `APPLIES_TO` their issue.
The validator enforces type constraints, a temporal DAG, and status/edge consistency; fix every error it reports.

---

## T9 Next-question selection (human review of the oracle)

When reviewing a decision point, mark each candidate question as **good** (a competent paralegal would ask it now),
**acceptable**, or **bad** (irrelevant, already answered, or premature). Disagreement with the oracle's
`acceptable_set` is recorded, not corrected, so the oracle itself can be evaluated. A good question:
targets an unknown *critical* element of a likely issue; distinguishes between plausible issues; is not answered
already; is safe (never asks the user to confront an abuser).

---

## T10 Provision retrieval (gold construction)

Gold provisions are the candidate provisions of the labelled issues filtered by routing variables (issue library):
- **law regime:** incident (the regime-determining event) **before 2024-07-01** → IPC / CrPC / IEA family;
  **on or after** → BNS / BNSS / BSA. Procedural provisions applied at filing time (e.g. BNSS maintenance) are not
  regime-filtered.
- **personal law** (recorded only where legally relevant): Hindu → HMA / HSA; inter-faith registered marriage → SMA;
  Muslim / Christian → their personal-law statutes are outside the corpus: no provision, triage lawyer.
- **risk:** some provisions apply only with a risk fact (e.g. threat to life).

**Never add a provision from memory.** Every id must be in the corpus or the registry; all are TO_VERIFY until a
human checks the official text and marks the registry entry `verified` (`reports/provision_verification.md`).

---

## T11 Explanation rating rubric

Rate each explanation 1–5 on **faithfulness** (primary), plus readability and helpfulness.

| Score | Faithfulness |
|---|---|
| 5 | Every legal statement is supported by the quoted official text; no invented section, punishment, deadline or case law |
| 4 | Fully supported; minor imprecision in paraphrase |
| 3 | One unsupported but harmless generalisation |
| 2 | An unsupported legal claim that could mislead |
| 1 | Invents law, cites a section not in the corpus, or gives dangerous advice |

Readability: short sentences, everyday words in the user's language, legal terms explained (use the glossary).
An explanation must always end with *where to verify* and must not promise outcomes.

---

## T12 Clarification labels (user turns after the opening)

| Label | Definition | ✔ Examples |
|---|---|---|
| new_fact | adds information, **including "I don't know"** and a plain "no, that is not my situation" | "Gottilla.", "I paid ₹45,000 on 14 March." |
| correction | revises something the user said earlier | "Sorry, I said that wrong. I paid fifty thousand…", "ಇಲ್ಲ ಇಲ್ಲ, ಸರಿಯಾಗಿ ಹೇಳ್ತೀನಿ…" |
| reexplain_request | asks the system to repeat or simplify | "Sorry, artha aaglilla. Innondsala simple aagi keltira?", "मतलब क्या?" |

✘ A correction must refer back to the user's own earlier statement; new information that contradicts nothing is
new_fact.

---

## T13 Triage and risk flags

**Risk flags** (label all that the text states):

| Flag | Definition | ✔ Example |
|---|---|---|
| imminent_violence | violence threatened for the near future | "he said he will come back tonight" |
| ongoing_abuse | abuse is continuing and the user is still exposed | "he beat me again last night and I am still in the same house" |
| threat_to_life | threat to kill / burn / stab, or a life-threatening hazard | "said they will burn me if the money does not come"; "it gives electric shocks" |
| self_harm | the user expresses thoughts of ending their life | "I feel there is no point in living" |
| minor_involved | a child is a victim or at risk | |
| image_circulation | intimate/morphed images are or will soon be shared | "he will post it tonight" |
| golden_hour_fraud | money lost within roughly the last day; funds may still be frozen | "this happened an hour ago" |
| imminent_property_transfer | sale/possession/irreversible construction about to happen | "registration is fixed for tomorrow" |
| eviction_imminent | the user is about to be thrown out of their home | "told me to get out by tomorrow" |
| child_removal_imminent | a child is about to be taken away / abroad | |
| limitation_near_expiry | the time limit to file is about to run out | "almost two years since then" |
| evidence_at_risk | evidence will soon be lost (CCTV overwritten) | |

**Triage** (apply in order):
1. **urgent** — any urgent flag (all flags above except minor_involved and evidence_at_risk), or intimate-image misuse.
2. **lawyer** — out-of-scope legal problem; two or more issues; personal law outside the corpus; or an issue whose
   default triage is lawyer (cheating, police refusal, family and most property issues).
3. **self_help** — otherwise (consumer complaints, cyber reporting, simple police complaints, non-legal).

When torn between two levels, choose the higher one and flag.

---

## 4. Soft labels, disagreements and adjudication

1. Each item in the double-annotation subset (≥15%) is labelled independently by two annotators.
2. `python -m lexvaani.annotation.iaa a.jsonl b.jsonl` computes agreement (Cohen's κ / Fleiss' κ for categorical
   labels, span F1 for spans, graph F1 for Case Graphs) and writes `adjudication_queue.jsonl`.
3. An adjudicator (a third person) resolves each disagreement with reference to this document, records the final
   label and a one-line reason, and updates the guidelines if a rule was missing.
4. **Genuinely ambiguous items** (both readings defensible under the rules) keep the **distribution** of annotator
   labels as a soft label (`soft_labels`), in addition to the adjudicated label. Do not force agreement.

## 5. Annotator checklist (per item)

- [ ] Spans: exact, no whitespace at the ends, suffix rule applied (§1.2)
- [ ] Only case participants are PERSON/ORG (§1.4); speaker not tagged
- [ ] Every negation word inside a claim tagged; hedges tagged
- [ ] TIMEX values resolved against the conversation date; ambiguous kal/parson decided by tense
- [ ] Element values from this unit only; self-contradiction → unknown; corrections applied
- [ ] Triage from flags first; flag anything uncertain
- [ ] No real personal data

## Appendix A. Hard cases

| Case | Decision |
|---|---|
| "He threatened to sell the land" vs "he already sold it" | threat = intimidation-type fact; sale event hypothetical vs asserted; `transfer_by_coowner` contradicted vs satisfied |
| Incident in **June 2024** vs **July 2024** | old vs new criminal-law regime; the TIMEX must be resolvable to the month (a bare "last year" in 2025 is ambiguous for 2024) |
| "Paid by UPI" vs "paid in cash, no receipt" | evidence_supported vs reported |
| "I think it was an accident" | `intentional` contradicted, claim hedged |
| Honorific `ಅವರು` with husband and mother-in-law both present | resolve by content; flag if still ambiguous |
| "maava" with no marriage context | relation `unresolved`; ask a clarifying question |
| "The police said they will 'look into it'" | refusal_to_register unknown (not satisfied) |
| A non-English app name ("WhatsApp") | medium, not an entity (§1.4) |
| Out-of-scope + library issue together | not allowed: label the library issue; note the other problem in comments |
