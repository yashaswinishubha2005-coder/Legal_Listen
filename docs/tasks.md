# LexVaani-IN — task definitions (v0.1)

Every task has a fixed input, output format and official metric. Evaluators live in
`eval/tNN_*.py` and run with one command:

```bash
python -m eval.run --task t07 --pred my_preds.jsonl            # default gold = release test split
python -m eval.run --task t07 --pred p.jsonl --gold release/lexvaani-in-v0.1.0/test_subsets/test_contrastive.jsonl
```

Notation: a **sample** is one narrative (`narratives/*.jsonl`); a **dialogue** is one simulated
consultation (`dialogues/*.jsonl`). Character offsets are Python string indices over NFC text,
half-open `[start, end)`. The conversation date is given with every sample (`conversation_date`)
and is the anchor for relative time expressions.

| # | Task | Input | Output | Official metric (primary in bold) |
|---|---|---|---|---|
| T1 | Legal issue identification | narrative | set of issue ids (+ optional ranking, domains) | **micro-F1**, macro-F1, top-1/top-3 accuracy, domain micro-F1 |
| T2 | Entity extraction | narrative | typed character spans | **strict span F1**, partial span F1, per-type partial F1 |
| T3 | Event & argument extraction | narrative | events with trigger span, type, typed argument spans | **argument F1**, trigger F1, trigger-type accuracy |
| T4 | Temporal normalisation & ordering | narrative | TIMEX values per time span; BEFORE/AFTER/OVERLAP links between events | **TIMEX value accuracy**, **TLINK F1** |
| T5 | Coreference | narrative or dialogue | clusters of PERSON/ORG mention spans | **CoNLL-F1** (mean of MUC, B³, CEAF-e) |
| T6 | Epistemic status | narrative | status per fact span; hedge / negation cue spans | **macro-F1 over 5 statuses**, cue span F1 |
| T7 | Legal element satisfaction | narrative | value per (issue, element) | **macro-F1** (satisfied / contradicted / unknown), critical-only macro-F1, ECE if probabilities |
| T8 | Case Graph construction | narrative | typed graph (ontology.md) | **edge F1**, node F1, normalised graph edit distance |
| T9 | Next-question selection | dialogue state | ranked candidate question ids | **Hit@1** (acceptable set), strict Hit@1, MRR; interactive: case completeness after N turns |
| T10 | Provision retrieval | narrative | ranked provision ids | **Recall@5**, Recall@{1,3,10}, nDCG@10, **citation validity** |
| T11 | Plain-language explanation | spec + provision + language | explanation text | chrF vs reference, readability, **human faithfulness rating** |
| T12 | Clarification detection | user turn (+ context) | new_fact / correction / reexplain_request | **macro-F1** |
| T13 | Triage & risk | narrative | self_help / lawyer / urgent + risk flags | **urgent-class recall**, accuracy, macro-F1, risk-flag micro-F1 |

---

## T1 Legal issue identification

- **Input:** `text`, `lang_variant`, `conversation_date`.
- **Output:** `{"sample_id", "issues": [...], "ranked_issues": [...]?, "domains": [...]?}`.
  Issue ids are the 25 library ids plus the routing labels `x.out_of_scope` (legal problem
  outside the library, must be routed to a lawyer) and `x.non_legal`.
- **Gold:** `annotations.issues` (1–2 issues; multi-issue specs have 2).
- **Metrics:** micro/macro F1 over issues (multi-label; macro averages over labels present in gold);
  top-k accuracy = at least one gold issue within the top k of `ranked_issues`.

## T2 Entity extraction

- **Types:** PERSON, ORGANIZATION, LOCATION, ASSET, MONEY, TIME, ACCOUNT, IDENTIFIER, EVIDENCE
  (definitions and boundary rules: guidelines §T2).
- **Output:** `{"sample_id", "entities": [{"start", "end", "type"}]}`.
- **Strict:** exact boundaries and type. **Partial:** overlap and same type, one-to-one greedy matching.

## T3 Event & argument extraction

- **Output:** `{"sample_id", "events": [{"trigger": [s, e], "event_type", "arguments": [{"role", "start", "end"}]}]}`.
- Roles: agent, patient, recipient, instrument, beneficiary, witness, place, time.
- **Matching:** a predicted event matches a gold event if their triggers overlap (one-to-one). An
  argument is correct if its event matched, its role is identical and its span overlaps the gold
  argument mention (time = the event's TIMEX span; place = a LOCATION mention).
- **Argument F1** counts arguments of unmatched events as false positives / negatives.
  Negated and hypothetical events are events too (flags are part of the gold; not scored in v0.1).

## T4 Temporal normalisation & ordering

- **Output:** `{"sample_id", "timexes": [{"start", "end", "value"}], "tlinks": [{"source": [s, e], "target": [s, e], "relation"}]}`.
  Event endpoints of TLINKs are given by trigger spans.
- **Values** follow TIMEX3: `2025-03-14`, `2025-03`, `2025`, `2025-W11`, `P3W`, `2025-03-14TNI`, `PAST_REF`, `P1D` (set).
  Relative expressions resolve against `conversation_date` (guidelines §T4).
- **Value accuracy:** fraction of gold TIMEX spans for which an overlapping predicted TIMEX has exactly the gold value.
- **TLINK F1:** links between gold events (asserted events only), after normalising `AFTER(a,b)` → `BEFORE(b,a)` and
  ordering OVERLAP pairs. Gold links come from the hidden absolute timeline, restricted to events mentioned in the text.

## T5 Coreference

- Mentions: PERSON and ORGANIZATION mentions (names, nominals such as "maava", "the owner", pronouns).
  The speaker (first person) is not annotated.
- Narratives: `{"sample_id", "clusters": [[[s, e], ...], ...]}`; dialogues: `{"dialogue_id", "clusters": [[[turn, s, e], ...]]}`
  (`python -m eval.t05_coref --dialogues`).
- **CoNLL-F1** = mean of MUC, B³ and entity-based CEAF (CEAF-e, Kuhn–Munkres alignment). Singletons are kept.
  MUC is defined as 1.0 for a side without any links.

## T6 Epistemic status

- **Statuses:** `reported`, `evidence_supported`, `inferred`, `conflicting`, `unknown` (decision tree: guidelines §T6).
- **Output:** `{"sample_id", "facts": [{"start", "end", "status"}], "cues": [{"start", "end", "type": "neg"|"hedge"}]}`.
- Each gold fact is paired with the predicted fact of maximal character overlap; unpaired gold facts are wrong.
  **Macro-F1** over the five statuses (labels absent from gold are excluded from the average).
- **Cue F1:** partial-match F1 for negation and hedge cues lying inside gold fact spans.

## T7 Legal element satisfaction

- **Output:** `{"sample_id", "elements": [{"issue_id", "element_id", "value", "probs"?}]}` for every element of every
  gold issue (element inventory: `resources/issue_library.jsonl`).
- **Gold rule** (guidelines §T7): `satisfied` / `contradicted` if the text establishes it; `unknown` if not stated,
  if the user says they do not know, or if the user contradicts themself.
- Narrative-level labels reflect only the narrative; facts revealed later in the dialogue are `unknown` here.
- **Macro-F1** over {satisfied, contradicted, unknown}; missing predictions count as errors. **ECE** (10 bins) when
  `probs` are supplied; soft human labels (Phase 4) enable calibration analysis against label distributions.

## T8 Case Graph construction

- **Output:** a graph in the release `CaseGraph` format (`docs/ontology.md`). Node ids are free.
- **Node matching:** same type and same key attribute (Person: synthetic name/role; Event: event_type; Evidence:
  evidence_type; Issue: issue_id; Element: (issue_id, element_id); Provision: provision_id; …), then source-span overlap.
- **Edge F1:** edges compared as (type, matched source, matched target); symmetric edges unordered.
- **Normalised GED:** (unmatched gold nodes + unmatched predicted nodes + edge symmetric difference + status/value relabels)
  / (gold nodes + gold edges). Exact GED is NP-hard; this assignment-based upper bound is the official v0.1 metric.

## T9 Next-question selection

- **Input:** dialogue up to a system decision point: `state_before` (known element values, asked questions, issue beliefs)
  and `candidates` (question ids `"<issue_id>|<element_id>"` with their question text).
- **Output:** `{"dialogue_id", "system_turn", "ranking": [question ids]}`.
- **Hit@1:** top-ranked id ∈ `acceptable_set`; **strict Hit@1:** top = `gold_best`; **MRR:** reciprocal rank of the first
  acceptable id.
- **Interactive:** `python -m eval.t09_next_question --policy mymodule:policy --turns 3` runs the policy against the
  spec-grounded user simulator and reports **case completeness after N turns** = fraction of critical gold elements whose
  value is known.

### The oracle (how `gold_best` is computed)

Hypotheses H = gold issues ∪ the first confusable issue of each gold issue (issue library `confusable_with`).
Each hypothesis h has an independent belief b_h = P(h applies), prior 0.5, updated by Bayes' rule from every known
element value of h, with likelihoods

```
P(e = satisfied | h present) = 0.9 if e is critical else 0.7
P(e = satisfied | h absent)  = 0.2
```

("unknown" answers do not update). For each candidate element e of issue h:

```
p_sat  = b_h · P(sat | present) + (1 − b_h) · P(sat | absent)
IG(e)  = H(b_h) − [ p_sat · H(b_h | sat) + (1 − p_sat) · H(b_h | contradicted) ]
score(e) = w(e) · ( IG(e) + b_h · H₂(p_sat) ),     w(e) = 2 if critical else 1
```

`H` and `H₂` are binary entropies in bits. IG is the expected reduction of entropy over the issue distribution;
the second term is the remaining uncertainty about the element itself, counted in proportion to how likely its issue is
(so elements of unlikely issues stop being asked). `gold_best = argmax(score − 0.001·order(e))` (ties broken by the issue
library's interview order); `acceptable_set = {e : score(e) ≥ 0.9 · max score}`. The oracle uses only the dialogue
state, never the hidden answer, so a model with the same state can in principle match it. Implementation:
`src/lexvaani/dialogue/oracle.py`. The dialogue stops after 6 questions or when the best score falls below 0.2.

## T10 Provision retrieval

- **Output:** `{"sample_id", "provisions": [ranked ids]}` using ids `"<ACT>:<section>"` such as `BNS:318(4)`.
- **Gold:** `annotations.provisions` — candidate provisions of the gold issues filtered by routing variables:
  **law regime** (incident before 2024-07-01 → IPC/CrPC; on/after → BNS/BNSS), **personal law** (Hindu → HMA/HSA;
  inter-faith registered marriage → SMA; Muslim/Christian personal law is outside the corpus → no provision, lawyer),
  and **risk** (e.g. threat to life). Out-of-scope and non-legal samples have no gold provisions and are excluded
  from Recall/nDCG (but count for citation validity).
- **Citation validity** = share of all predicted ids that exist in the reference set; **hallucination rate** = 1 −
  validity. Reference set = the parsed official corpus (plus subsection references whose base section is in it).
  **While the corpus is empty (v0.1), the provision registry is used and the result is labelled `basis: registry`.**
- **All gold provisions are TO_VERIFY** until Gate 1 human verification (`reports/provision_verification.md`).

## T11 Plain-language explanation

- **Input:** a spec's narrative (in en / kn / hi), one gold provision, the official text (when parsed).
- **Output:** `{"explanation_id", "text"}`. Required structure: *what it says / what it means / why it may apply here /
  conditions / where to verify*.
- **Reference:** `explanations/*.jsonl`. *What it says* is a verbatim corpus excerpt only; in v0.1 it is empty
  (`status: pending_corpus_text`) because the corpus is not parsed yet, and chrF is computed on the other sections.
- **Metrics:** chrF (character n-gram F-β, β = 2, n ≤ 6) per language; readability (Flesch reading ease for English;
  words per sentence and characters per word for kn/hi — no validated formula exists); **human faithfulness rating**
  (1–5, two raters; pass `--human ratings.json`). Faithfulness is the primary metric: an explanation that cites a
  section or condition not in the corpus text is unfaithful regardless of chrF.

## T12 Clarification detection

- **Input:** a user turn after the opening narrative, with the preceding turns.
- **Labels:** `new_fact` (adds information, including "I don't know"), `correction` (revises an earlier statement),
  `reexplain_request` (asks the system to repeat or simplify).
- **Output:** `{"dialogue_id", "turn", "label"}`. **Macro-F1.**

## T13 Triage & risk

- **Labels:** `urgent` if any urgent risk flag is present (imminent violence, ongoing abuse, threat to life, self-harm,
  image circulation, golden-hour fraud, imminent property transfer, eviction imminent, child removal imminent,
  limitation near expiry) or the issue is urgent by default (intimate-image misuse); otherwise `lawyer` for
  out-of-scope, multi-issue, personal-law-outside-corpus, or issues whose default is lawyer; otherwise `self_help`.
- **Output:** `{"sample_id", "triage", "risk_flags": [...]}`.
- **Urgent-class recall is primary**: missing an urgent case is the costliest error. Report accuracy and macro-F1 too.

---

## Test subsets

| Subset | Content | Purpose |
|---|---|---|
| `test_contrastive` | test families containing a minimal pair (base + sibling, all variants) | does the model reason over the one changed fact? Report paired accuracy: both members correct |
| `test_asr_noise` | ASR-noised copies of test narratives (medium for all, high for ~⅓) | robustness; compare with the clean counterpart via `clean_sample_id` |
| `test_code_mixed` | clean test narratives in kn-en_latn, kn-en_mixed, hi-en_latn | code-mixing |
| `test_out_of_scope` | out-of-library legal problems | must be routed to a lawyer, no provisions cited |
| `test_high_risk` | test narratives whose gold triage is urgent | urgent recall |
| `test_human/` | empty; to be written by humans only | final, uncontaminated evaluation |

## Reporting

Report every metric per language variant and per difficulty, and for the fairness slices in
`reports/dataset_stats.md` (speaker gender, age group, urban/rural, region, religion where recorded, literacy proxy).
Reference baselines and evaluator sanity checks: `reports/baselines.md`.
