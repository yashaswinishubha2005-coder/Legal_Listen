# Datasheet for LexVaani-IN v0.1.0 (after Gebru et al., 2021)

## Motivation
- **Purpose:** evaluate whether NLP systems can support *legal pre-consultation* for Indian users who describe
  problems in English, Kannada, Hindi or code-mixed Kanglish/Hinglish: understanding facts, knowing what is still
  unknown, asking the right next question, and triaging urgency. No existing benchmark combines Indian legal
  issues, Kannada, code-mixing and dialogue.
- **Creators / funding:** the LexVaani-IN project. No external funding is recorded for v0.1.

## Composition
- **Instances:** 724 scenario specs → 4,344 clean narratives (6 language variants each), 2,003 ASR-noisy
  narratives, 4,344 dialogues with oracle decision points, 7,224 explanation references.
- **Content:** synthetic first-person descriptions of 25 legal issues (criminal, family, property, cyber,
  consumer/financial) plus out-of-scope legal and non-legal scenarios.
- **Labels:** issues, entities, events, TIMEX, temporal links, coreference, epistemic status, element
  satisfaction, Case Graph, next-question sets, provisions, triage and risk flags — all **derived by
  construction** from the spec, with exact character offsets.
- **Personal data:** none. Names, places and amounts are synthetic draws; demographic metadata (gender, age group,
  region, religion, settlement, literacy proxy) is sampled and does not describe real people.
- **Sensitive content:** domestic violence, dowry harassment, sexual image abuse, self-harm mentions (as risk
  flags). No graphic descriptions.
- **Splits:** by scenario family, stratified by domain × variation; test subsets for contrastive pairs, ASR noise,
  code-mixing, out-of-scope and high-risk items.

## Collection process
- Specs are sampled from a hand-written issue library (`resources/issues/*.yaml`) with a fixed seed (13); minimal
  pairs flip one element, one evidence item, the incident date across 2024-07-01, or one risk fact.
- Text is rendered from multilingual templates and a lexicon; spans are recorded during rendering, never searched.
- ASR noise is simulated (substitutions, deletions, homophones, romanisation drift) with labels re-projected.
- No LLM generation was used in v0.1 (the LLM paraphrase/judge pipeline exists but was not run).

## Preprocessing / QC
Unicode NFC; span verification; language-ID and CMI checks; cross-lingual label consistency; legal-term leakage
check; near-duplicate removal. Reports in `reports/`.

## Uses
- **Intended:** benchmarking research models; error analysis on Kannada/code-mixed legal language; training and
  evaluating prototype assistants such as LegalListen (this repository), whose offline NLU is trained on the
  train split and evaluated on the test split (reports/legallisten_eval.md).
- **Not intended:** giving legal advice to real people; training production legal assistants without human
  review; any decision about real persons. Provisions are TO_VERIFY.

## Distribution
CC BY 4.0 for data; code under the repository licence. Versioned with SHA256 checksums.

## Maintenance
Planned v0.2: official corpus text and provision verification (Gate 1), native-speaker review, a human-written
`test_human/` set (docs/recording_protocol.md), LLM paraphrases with judge filtering, inter-annotator agreement.

## Known limitations and biases
- Template text is more regular than real speech; results may overestimate real-world performance.
- Kannada and Hindi text not yet reviewed by native speakers; dialect coverage is limited (Bengaluru/Mysuru
  Kannada, standard Hindi).
- Heteronormative spouse assumption in family templates; honorific-plural convention for all adults.
- The issue library covers 25 issues; personal laws other than Hindu/SMA are routed to "lawyer" without
  provisions.
- Legal mappings reflect the creators' reading of the statutes and must be verified by a lawyer.
