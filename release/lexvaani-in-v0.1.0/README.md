---
language: [en, kn, hi]
license: cc-by-4.0
multilinguality: multilingual
task_categories: [text-classification, token-classification, question-answering, text-generation]
tags: [legal, india, code-mixing, kannada, hindi, synthetic, benchmark]
pretty_name: LexVaani-IN
size_categories: [1K<n<10K]
---

# LexVaani-IN v0.1.0

A **multilingual Indian legal pre-consultation benchmark**: users describe a legal problem in plain language
(English, Kannada, Hindi, Kanglish romanised / mixed-script, Hinglish romanised) and systems must understand it
the way a paralegal would — identify issues, extract facts, judge what is known, ask the next question, retrieve
provisions, explain, and triage.

> **Synthetic data, research use only. Not legal advice.** All text is generated from structured specs by a
> template engine; all names are synthetic. Every provision mapping is **TO_VERIFY** until checked against the
> official text (see Limitations).

## Contents

| Split | Specs | Narratives | ASR-noisy narratives | Dialogues | Explanation refs |
|---|---|---|---|---|---|
| train | 463 | 2,778 | 550 | 2,778 | 4,530 |
| dev | 92 | 552 | 110 | 552 | 990 |
| test | 169 | 1,014 | 1,343 | 1,014 | 1,704 |

Each spec is rendered in all 6 language variants. Splits are by **scenario family** (a base spec plus its
minimal-pair siblings), so no family crosses splits.

Test subsets (`test_subsets/`): contrastive minimal pairs (782), ASR noise (1,343), code-mixed (507),
out-of-scope / non-legal (113), high-risk (589).

25 issues across 5 domains: criminal, family, property, cyber, consumer/financial (`resources/issue_library.jsonl`).

## Tasks (details: `docs/tasks.md`)
T1 issue identification · T2 entities · T3 events · T4 TIMEX + temporal links · T5 coreference ·
T6 epistemic status / hedging / negation · T7 legal element satisfaction · T8 Case Graph · T9 next question ·
T10 provision retrieval · T11 explanation · T12 clarification type · T13 triage + risk flags.

## Files
- `narratives/{split}.jsonl`, `narratives_asr/`, `dialogues/`, `explanations/`, `specs/` — full JSON records
  (Pydantic schemas in `src/lexvaani/schemas/`).
- `csv/narratives.csv` (one row per narrative, nested labels as JSON strings), `csv/dialogue_turns.csv`,
  `csv/next_question.csv`, `csv/specs.csv`.
- `lexvaani_in_narratives_all.jsonl` — all clean narratives with a `split` field.
- `corpus/` — provision corpus (empty in v0.1) and the provision registry.
- `lexvaani_in.py` — Hugging Face `datasets` loader. `SHA256SUMS` — checksums.

## Loading
```python
import json
rows = [json.loads(l) for l in open("narratives/test.jsonl", encoding="utf-8")]
# or
import pandas as pd; df = pd.read_csv("csv/narratives.csv")
# or
from datasets import load_dataset; ds = load_dataset("./lexvaani_in.py", "narratives")
```

## Quality control (reports/qc_report.md)
0 misaligned spans out of 68,787; rule-based language ID agrees with the intended variant on 100%;
cross-lingual label consistency 730/730 specs; CMI ≈ 15 (Kanglish romanised), ≈ 33 (Kanglish mixed),
≈ 14 (Hinglish); near-duplicates removed (6 specs).

## Baselines (reports/baselines.md)
Keyword T1 micro-F1 0.655 · keyword T13 urgent recall 0.575 · random T9 Hit@1 0.554 (strict 0.280).

## Limitations
- **Template-generated text**: less diverse than real user language; models can exploit template regularities.
  Report results on `test_human/` once it exists.
- **No native-speaker review yet** of the Kannada/Hindi/code-mixed text.
- **Law corpus is empty**: official bare-act PDFs could not be downloaded in the build environment. Provision ids
  come from a registry, all marked TO_VERIFY; explanation references are `pending_corpus_text`.
- **No inter-annotator agreement yet**; labels are produced by construction from specs.
- Simplifying assumptions: spouses are opposite-sex in the templates; honorific-plural pronouns for all adults
  in kn/hi; festival dates are approximate.

## Citation
```
@misc{lexvaani_in_2026, title={LexVaani-IN: A Multilingual Indian Legal Pre-consultation Benchmark}, year={2026}, note={v0.1.0}}
```
