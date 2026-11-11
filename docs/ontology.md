# LexVaani-IN Case Graph Ontology (v0.1.0)

The **Legal Case Graph** is the structured state of one user's case: who is
involved, what happened and when, what is claimed, what evidence exists, which
legal issues and elements are in play, which provisions may apply, and what is
still missing.

The machine-checked schema is `src/lexvaani/schemas/ontology.py`. If this
document and the code disagree, the code wins and the mismatch is a bug.

---

## 1. Universal fields

Every node and every edge carries these fields:

| Field | Type | Meaning |
|---|---|---|
| `status` | `reported` \| `evidence_supported` \| `inferred` \| `conflicting` \| `unknown` | How we know it (§4) |
| `confidence` | float in [0, 1] | **Gold data:** how certain the annotator is (default 1.0; soft labels are stored elsewhere). **Predictions:** the model's confidence. |
| `source_spans` | list of `Span` | The text that grounds the fact. Each span is `unit_id`, `start`, `end`, `text`, with half-open offsets over NFC text. Empty is allowed only for `inferred` or `unknown` items. |
| `attributes` | dict | Type-specific extras such as `relation` or `surface_term` |

## 2. Node types

| Type | ID prefix | Key fields | What it represents |
|---|---|---|---|
| **Person** | `per_` | `role` (speaker / complainant / respondent / witness / other), `gender`, `is_minor`, `synthetic_name` | A human in the case. The narrator is always the person with `role = speaker`. |
| **Organization** | `org_` | `org_type` (bank, police, court, govt_office, company, platform, lender, other) | An institution acting in the case |
| **Event** | `evt_` | `event_type`, `trigger` span, `time` (Timex), `place`, `negated`, `hypothetical` | Something that happened, or was threatened or planned |
| **Claim** | `clm_` | `proposition` (normalized English), `polarity`, `hedged`, `hedge_cues`, `negation_cues`, `turn_index` | An assertion someone makes. The unit that carries epistemic status. |
| **Evidence** | `evd_` | `evidence_type`, `availability` (held / missing / obtainable / unknown) | A document, record, witness or object that could prove something |
| **Asset** | `ast_` | `asset_type`, `ancestral` | Land, a house, gold, a phone, a product… |
| **Account** | `acc_` | `account_type`, `institution` (generic) | A bank, UPI, card, wallet, social-media, email, phone or loan account |
| **Issue** | `iss_` | `issue_id` (one of the 25 issues, or `x.out_of_scope` / `x.non_legal`) | A candidate legal issue |
| **Element** | `elm_` | `issue_id`, `element_id`, `critical`, `value` (satisfied / contradicted / unknown) | One legal ingredient of an issue, taken from the issue library |
| **Provision** | `prv_` | `provision_id` `"<ACT>:<section>"`, `verification` | A section of an Act. **It must exist in the corpus.** Its status is `to_verify` until a human checks it. |
| **Question** | `qst_` | `text`, `template_id` | A clarifying question the system may ask |

### Event vs. Claim

- An **Event** is the world-level occurrence ("the sale of the farm").
- A **Claim** is what someone *says* about the world ("Ramesh sold it without my consent").
- One event can have several claims about it, including contradictory ones.
- Epistemic status matters most on claims. Events and edges inherit the status of their strongest supporting claim.

### Negated and hypothetical events

- **"He did not sign"** becomes an Event with `negated = true`. The event is
  kept because whether it happened can be a legal element (e.g. consent).
- **"He threatened to sell"** becomes an Event with `hypothetical = true` for the
  sale, plus a separate `threat` Event that did happen. This is the classic
  minimal pair: "threatened to sell" vs. "already sold".

## 3. Edge types

Edges are directed `source → target` unless marked **symmetric**. Symmetric
edges are stored with `source_id < target_id` so that edge-F1 is well-defined.

| Edge | Source → Target | Required attributes | Meaning |
|---|---|---|---|
| `KIN_OF` | Person → Person | `relation` (KinRelation), `surface_term` (optional) | Source is the target's `relation` (A KIN_OF B with relation=father means A is B's father) |
| `AFFILIATED_WITH` | Person → Organization | – | Employee, agent or officer of the organization |
| `PARTICIPANT_IN` | Person / Org / Asset / Account → Event | `role`: agent / patient / instrument / beneficiary / witness / recipient | An event argument (T3) |
| `OWNS` | Person / Org → Asset / Account | – | Ownership or holding as asserted. Disputes are expressed through Claims. |
| `HOLDS` | Person / Org → Evidence | – | Who currently has the evidence |
| `BEFORE` | Event → Event | – | Source ends before target starts. **Must be acyclic.** |
| `OVERLAP` | Event ↔ Event (symmetric) | – | The two time intervals intersect |
| `CAUSES` | Event → Event | – | Source caused or led to target |
| `ASSERTS` | Person → Claim | – | Who made the claim |
| `ABOUT` | Claim → Person / Org / Event / Asset / Account | – | What the claim is about |
| `SUPPORTS` | Evidence → Claim / Event | – | The evidence backs it |
| `CONTRADICTS` | Claim / Evidence ↔ Claim / Evidence (symmetric) | – | The two cannot both be true |
| `CORRECTS` | Claim → Claim | – | The user's later claim replaces an earlier one (T12 "correction") |
| `INDICATES` | Event / Claim → Issue | – | This fact raises the issue |
| `HAS_ELEMENT` | Issue → Element | – | The element belongs to this issue |
| `SATISFIES` | Claim / Evidence / Event → Element | – | The element is met |
| `REFUTES` | Claim / Evidence / Event → Element | – | The element is contradicted by the facts |
| `LACKS` | Issue → Element | – | The element is still unknown (missing information) |
| `APPLIES_TO` | Provision → Issue | – | The provision is a candidate for this issue |
| `TARGETS` | Question → Element | – | The question seeks the value of this element |

### Temporal relations

- The graph stores only `BEFORE` and `OVERLAP`.
- An `AFTER(a, b)` from the T4 annotation is normalized to `BEFORE(b, a)`, so
  scoring never counts the same relation twice.
- The T4 evaluator accepts all three labels and normalizes them before scoring.

### Kinship

`KinRelation` has 27 normalized values: father … daughter_in_law, plus
`other_relative` and `unresolved`. The surface term is kept in
`surface_term`. Several Indian kinship terms are ambiguous, and the guidelines
give the decision rules for them. Examples:

| Surface term | Possible relations | Rule |
|---|---|---|
| maava (kn) | maternal_uncle, father_in_law | Decide from context, e.g. marriage was mentioned. If unclear, use `unresolved` and raise a missing-info question. |
| chikkappa / doddappa (kn) | paternal_uncle (father's younger / elder brother) | `paternal_uncle`; record younger/elder in `attributes.seniority` |
| devar (hi) | brother_in_law (husband's younger brother) | `brother_in_law` |
| jija / bhaava | brother_in_law (sister's husband) | `brother_in_law` |

## 4. Epistemic status

| Status | Use when | Structural rule (enforced) |
|---|---|---|
| `reported` | The user asserts it and mentions no evidence for it | – |
| `evidence_supported` | The user asserts it **and** says they hold or can obtain evidence | A Claim needs ≥1 incoming `SUPPORTS` from an Evidence node |
| `inferred` | Not stated, but follows from stated facts (e.g. Issue nodes, Element links) | Usually has no source spans |
| `conflicting` | Another claim or evidence contradicts it (including the user contradicting themselves) | A Claim needs ≥1 `CONTRADICTS` edge |
| `unknown` | Legally relevant but not known; the user said "gottilla / pata nahi" or it was never asked | – |

The full decision tree (precedence: conflicting > evidence_supported >
reported > inferred > unknown) and the hedging/negation cue rules are in
`annotation_guidelines.md`, task T6.

## 5. Element consistency (enforced)

Every Element node must be consistent with its edges:

| `value` | Required incoming edges |
|---|---|
| `satisfied` | ≥1 `SATISFIES`, no `REFUTES`, no `LACKS` |
| `contradicted` | ≥1 `REFUTES`, no `SATISFIES`, no `LACKS` |
| `unknown` | `LACKS` from its Issue, no `SATISFIES`, no `REFUTES` |

If the evidence is mixed (both satisfying and refuting), the element is
**unknown** in gold. The underlying claims are marked `conflicting`, and the
annotator records the reason in `attributes.note`.

## 6. Other validity rules

1. Node ids are unique and use their type's prefix.
2. Edge ids are unique (`e_…`), and edges have no self-loops.
3. Every edge connects nodes of an allowed type pair (§3 table).
4. `BEFORE` edges form a DAG.
5. Provision ids match `^[A-Z][A-Za-z0-9_]*:[0-9A-Za-z().\-]+$`. Checking that
   the id exists in the corpus happens in QC (Phase 4), once the corpus exists.

## 7. Worked example (Kanglish, romanized)

> **Nanna chikkappa Ramesh namma thota na nanna sign illade maaridru. Sale deed copy nanna hatra ide.**
> *"My paternal uncle Ramesh sold our farm without my signature. I have the sale deed copy."*

```
per_2 "Ramesh" ──KIN_OF{paternal_uncle, "chikkappa"}──► per_1 speaker
per_2 ──PARTICIPANT_IN{agent}──► evt_1 sale_transfer (trigger "maaridru")
ast_1 farm ──PARTICIPANT_IN{patient}──► evt_1
per_1 ──ASSERTS──► clm_1 "sold without consent"  [evidence_supported, negation cue "illade"]
evd_1 sale deed (held) ──SUPPORTS──► clm_1        per_1 ──HOLDS──► evd_1
evt_1 ──INDICATES──► iss_1 prop.coheir_sale_without_consent [inferred]
iss_1 ──HAS_ELEMENT──► elm_1 transfer_by_coowner   ◄──SATISFIES── clm_1
iss_1 ──HAS_ELEMENT──► elm_2 claimant_has_share    ◄──LACKS────── iss_1   (unknown, critical)
prv_1 ──APPLIES_TO──► iss_1
```

- `elm_2` is unknown and critical. That makes it the natural target for the
  next question (T9), e.g. "Is the farm ancestral, and are you one of the heirs?"
- The full JSON for this example is in `tests/fixtures.py`. It is a test
  fixture: `prv_1` uses a placeholder act (`TEST_ACT:1`) on purpose. Real
  provisions appear only after the Phase 1 corpus exists.

## 8. Scoring hooks (detail in `tasks.md`)

- **Node F1:** nodes are matched by (type, normalized key attributes). Ids are
  never compared.
- **Edge F1:** edges are matched by (type, matched-source, matched-target).
  Symmetric edges are compared without regard to direction.
- **Graph edit distance:** the cost of node and edge insertions, deletions and
  relabelings. A wrong `status` counts as a relabel.

## 9. Changelog

- **0.1.0:** first draft for Gate 0.
