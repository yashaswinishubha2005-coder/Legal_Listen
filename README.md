# LexVaani-IN + LegalListen

This repository contains two things that build on each other:

1. **LexVaani-IN** — a multilingual Indian legal pre-consultation **benchmark dataset** (English, Kannada,
   Hindi, Kanglish romanised / mixed-script, Hinglish) with 13 tasks, from issue identification to triage.
   Release: `release/lexvaani-in-v0.1.0/` (JSONL + CSV). Datasheet: `DATASHEET.md`. Tasks: `docs/tasks.md`.
2. **LegalListen** — a working **web application**: a lawyer-like, multilingual voice + text legal consultation
   system with adaptive cross-questioning, a live **Legal Case Graph**, provision identification with the
   **verbatim official text** (parsed from India Code PDFs), a final consultation report, **ready-to-file
   drafts** (police complaint, bank complaint, consumer complaint, legal notice, legal-aid application) whose
   every fact links back to the user's own words, and optional **accounts** to continue on any device.
   Documentation: `docs/legallisten.md`. Pages: `/` (app), `/login`, `/about` (how it works).

> Research prototype. Preliminary legal information, **not legal advice**. All provision mappings are
> TO_VERIFY until checked by a lawyer against the official text.

## Quick start (LegalListen website)

**VS Code users (Windows / macOS / Linux): follow `RUN_IN_VSCODE.md`** (`setup.bat` / `run.bat` on Windows).

```bash
make setup              # Python 3.11 virtualenv + pinned dependencies
make serve              # open http://localhost:8000
```

The trained offline NLU model ships in `models/` (rebuild with `make train-nlu`). Optional LLM mode:
`cp .env.example .env`, set `GEMINI_API_KEY=...`, restart `make serve`; clients opt in with a consent box.
Docker: `docker build -t legallisten . && docker run -p 8000:8000 --env-file .env legallisten`.

## What is used

| | |
|---|---|
| Dataset (built here) | **LexVaani-IN v0.1.0** — 724 scenario specs → 4,344 narratives in 6 language variants, 2,003 ASR-noisy narratives, 4,344 dialogues with next-question labels, 7,224 explanation references (93.5% with the verbatim official text); family-level train/dev/test splits |
| Law corpus | **2,811 sections** parsed from 18 official India Code bare-act PDFs (BNS, BNSS, BSA, IPC, Evidence Act, IT Act, Consumer Protection, Hindu Marriage / Succession, Special Marriage, Domestic Violence, Dowry, Guardians and Wards, Transfer of Property, Registration, Specific Relief, Limitation, Karnataka Land Revenue). 73 of the 79 cited provisions have official text. Footnotes and page stamps are removed; nothing else is changed. CrPC is not loaded: the copy supplied was a 1974 OCR scan with garbled text |
| Offline NLU (built here) | character + word n-gram logistic-regression classifiers trained on the LexVaani-IN **train** split (`models/legallisten_nlu.joblib`) + multilingual rules |
| Question selection | LexVaani-IN Bayesian oracle (information gain over issue hypotheses), extended with safety, contradiction, date-regime, personal-law and evidence questions |
| LLM (optional) | **Google Gemini** (`gemini-2.5-flash` by default, set `LEGALLISTEN_MODEL`) via its REST API for extraction, phrasing, explanations, summaries and speech transcription; Anthropic / OpenAI also supported. Not required — everything works offline |
| Speech | Browser Web Speech API (kn-IN / hi-IN / en-IN) or Gemini audio transcription; browser speech synthesis for read-aloud |
| No pretrained neural model is bundled | the external QC hooks (IndicLID, LaBSE, IndicTrans2) are optional stubs in `src/lexvaani/qc/external.py` |

## Results (see `reports/`)

* `reports/legallisten_eval.md` — LegalListen on the LexVaani-IN test split (interactive simulation, all six
  language variants): issue identification, fact finding, triage, regime routing, provision retrieval, graph
  validity; adaptive policy vs a fixed questionnaire; plus a small hand-written free-form probe.
* `reports/legallisten_nlu.md` — offline NLU scores; `reports/baselines.md` — dataset baselines;
  `reports/qc_report.md`, `reports/dataset_stats.md` — dataset quality and statistics.

## Repository map

```
src/lexvaani/        dataset generator: schemas, rendering, specs, dialogue oracle, ASR noise, corpus, QC, export
src/legallisten/     web app: engine, NLU (rules, trained models, LLM), policy, case graph, provisions,
                     consultation, encrypted store, FastAPI app, static/ (HTML/CSS/JS frontend)
resources/           issue library (25 issues), lexicon, glossary, LegalListen guidance (en/kn/hi)
eval/                LexVaani-IN task evaluators, baselines, LegalListen system evaluation
tests/               pytest suite (dataset + LegalListen)
docs/                ontology, tasks, annotation guidelines, recording protocol, dataset card, LegalListen
prompts/             LLM prompts (dataset paraphrase / judge; LegalListen extraction / reply / explain / summary)
release/             LexVaani-IN v0.1.0 release files
```

## Common commands

```bash
make test                 # full test suite
make all                  # rebuild the dataset deterministically (seed 13)
make train-nlu            # retrain LegalListen's offline NLU on the train split
make eval-legallisten     # system evaluation -> reports/legallisten_eval.md
make zip                  # dist/lexvaani-in.zip
```

## Known limitations

Template-generated dataset text; Kannada/Hindi strings pending native-speaker review; CrPC text not loaded
(add a clean India Code PDF named `criminal_procedure.pdf` to `data/raw/acts/` and run `make corpus`), and the
Limitation Act schedule articles are not parsed; drafts are in English and must be reviewed before filing;
no inter-annotator agreement or real-user study yet; LLM mode tested with a scripted fake model, not against the
live Gemini API in this build.
