# Running LexVaani-IN and LegalListen in VS Code

## 1. Install once
- **Python 3.11** (or newer) — https://www.python.org/downloads/ (Windows: tick *Add python.exe to PATH*).
- **VS Code** — https://code.visualstudio.com/ with the **Python** extension (by Microsoft).
- Optional for the browser test: **Node.js** (https://nodejs.org).

## 2. Open the project
1. Unzip `legallisten-app.zip` (e.g. to `C:\projects\lexvaani-in` or `~/projects/lexvaani-in`). This is all
   you need to run the website.
   *Optional (only to retrain the model or re-run the evaluation):* unzip `lexvaani-dataset.zip` and move its
   `lexvaani-in-v0.1.0` folder into `lexvaani-in/release/`.
2. VS Code → **File → Open Folder…** → choose the `lexvaani-in` folder (the one containing `README.md`).
3. If VS Code asks "Do you trust the authors?", click **Yes**.

## 3. Set up (one time, ~3–5 minutes)
Open the terminal: **Terminal → New Terminal**, then run:

| Windows (PowerShell / cmd) | macOS / Linux |
|---|---|
| `.\setup.bat` | `bash setup.sh` |

This creates `.venv`, installs the pinned packages and creates `.env`.
Then pick the interpreter: **Ctrl+Shift+P → "Python: Select Interpreter" → `.venv`**.

> PowerShell error "running scripts is disabled"? Use `cmd /c setup.bat`, or run once:
> `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`.

## 4. Run the LegalListen website
Either:
- **Run and Debug** (Ctrl+Shift+D) → choose **"LegalListen website (http://localhost:8000)"** → ▶, or
- terminal: `.\run.bat` (Windows) / `bash run.sh` (macOS/Linux).

Open **http://localhost:8000** in Chrome or Edge (best for microphone input). Stop with **Ctrl+C** (or the
red ■ in the debugger).

The first page is the **sign-in page**. Create an account (your consultations are then saved to it and open on
any device) or click **Continue as guest** (saved only in that browser). **http://localhost:8000/about**
explains how the system works — useful for a demo.

### Optional: use Gemini (your API key)
Open `.env` in VS Code and set:
```
GEMINI_API_KEY=your-key-here
```
Save and restart the website. The badge at the top shows **"AI: on · gemini-2.5-flash"**, and each client is
asked for consent before their text is sent to Gemini. Never share or commit `.env`.

## 5. The LexVaani-IN dataset (earlier deliverable)
The dataset is already built inside the project — nothing to run to use it:

| What | Where |
|---|---|
| Spreadsheet-friendly CSVs | `release/lexvaani-in-v0.1.0/csv/narratives.csv`, `dialogue_turns.csv`, `next_question.csv`, `specs.csv` |
| Full JSON records per split | `release/lexvaani-in-v0.1.0/narratives/{train,dev,test}.jsonl` (also `dialogues/`, `explanations/`, `narratives_asr/`, `specs/`) |
| All narratives in one file | `release/lexvaani-in-v0.1.0/lexvaani_in_narratives_all.jsonl` |
| Dataset card / datasheet | `release/lexvaani-in-v0.1.0/README.md`, `DATASHEET.md` |
| Reports | `reports/` (statistics, QC, baselines, evaluations) |

Tip: install the **Rainbow CSV** extension to view the CSVs, or open them in Excel (UTF-8).

Load it in Python (e.g. in a new file or a Jupyter notebook in VS Code):
```python
import json, pandas as pd
df = pd.read_csv("release/lexvaani-in-v0.1.0/csv/narratives.csv")   # pip install pandas first
rows = [json.loads(l) for l in open("release/lexvaani-in-v0.1.0/narratives/test.jsonl", encoding="utf-8")]
print(len(df), rows[0]["text"], rows[0]["annotations"]["issues"])
```

Rebuild / evaluate the dataset (optional) — **Run and Debug** configurations:
- **"LexVaani-IN: rebuild whole dataset"** (regenerates everything deterministically, a few minutes)
- **"LexVaani-IN: dataset baselines"** → `reports/baselines.md`
- **"LegalListen: evaluate on test split"** → `reports/legallisten_eval.md`
- **"LegalListen: retrain offline NLU"** → `models/legallisten_nlu.joblib`

Or from the terminal (Windows uses `.venv\Scripts\python`, macOS/Linux `.venv/bin/python`):
```
.venv\Scripts\python -m lexvaani.pipeline all
.venv\Scripts\python -m lexvaani.pipeline export
.venv\Scripts\python -m eval.baselines
```

## 6. Run the tests
**Testing** panel (flask icon) → ▶ *Run All Tests*, or terminal:
`.venv\Scripts\python -m pytest -q` (Windows) / `.venv/bin/python -m pytest -q` (macOS/Linux). Expected: all pass.

Browser smoke test (needs Node.js, website running):
```
npm install playwright@1.48.2
npx playwright install chromium
node scripts/e2e_browser.js http://localhost:8000
```

## 7. Common problems
| Problem | Fix |
|---|---|
| `py` / `python3.11` not found | Install Python 3.11+, reopen VS Code |
| `ModuleNotFoundError: legallisten` | Select the `.venv` interpreter; re-run setup |
| Port 8000 already in use | change `8000` in `run.bat` / `run.sh` / `.vscode/launch.json` |
| Microphone does nothing | Use Chrome/Edge on `http://localhost` and allow microphone access; Kannada speech recognition depends on the browser |
| Kannada/Hindi letters look broken in the terminal | harmless; the website and files are UTF-8 (setup sets `PYTHONUTF8=1`) |
