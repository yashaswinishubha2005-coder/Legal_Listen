PY := .venv/bin/python
PIPE := $(PY) -m lexvaani.pipeline
STAGES := corpus specs splits render dialogues noise explanations qc export stats
PORT ?= 8000

.PHONY: setup test all baselines zip zip-app zip-dataset clean train-nlu serve eval-legallisten $(STAGES)
setup:
	python3.11 -m venv .venv && .venv/bin/pip install -r requirements.txt && .venv/bin/pip install -e .
test:
	$(PY) -m pytest -q
$(STAGES):
	$(PIPE) $@
all:
	$(PIPE) all
baselines:
	$(PY) -m eval.baselines
# ---- LegalListen
train-nlu:
	$(PY) -m legallisten.nlu.train
serve:
	set -a; [ -f .env ] && . ./.env; set +a; .venv/bin/uvicorn legallisten.app:app --host 0.0.0.0 --port $(PORT)
eval-legallisten:
	$(PY) -m eval.legallisten_eval
zip:
	mkdir -p dist && rm -f dist/lexvaani-in.zip && cd .. && zip -qr lexvaani-in/dist/lexvaani-in.zip lexvaani-in \
	  -x 'lexvaani-in/.venv/*' 'lexvaani-in/.cache/*' 'lexvaani-in/dist/*' 'lexvaani-in/.git/*' '*/__pycache__/*' \
	  'lexvaani-in/.env' '*.egg-info/*' 'lexvaani-in/.pytest_cache/*' 'lexvaani-in/data/legallisten/*'
# Two smaller downloads: the app (runs on its own) and the dataset release.
zip-app:
	mkdir -p dist && rm -f dist/legallisten-app.zip && cd .. && zip -q -9 -r lexvaani-in/dist/legallisten-app.zip lexvaani-in \
	  -x 'lexvaani-in/.venv/*' 'lexvaani-in/.cache/*' 'lexvaani-in/dist/*' 'lexvaani-in/.git/*' '*/__pycache__/*' \
	  'lexvaani-in/.env' '*.egg-info/*' 'lexvaani-in/.pytest_cache/*' 'lexvaani-in/data/legallisten/*' \
	  'lexvaani-in/release/*' 'lexvaani-in/data/samples/*' 'lexvaani-in/data/dialogues/*' 'lexvaani-in/data/explanations/*' \
	  'lexvaani-in/data/specs/*' 'lexvaani-in/data/raw/acts/*.pdf' 'lexvaani-in/eval/preds/*'
zip-dataset:
	mkdir -p dist && rm -f dist/lexvaani-dataset.zip && cd release && zip -q -9 -r ../dist/lexvaani-dataset.zip lexvaani-in-v0.1.0 \
	  -x 'lexvaani-in-v0.1.0/csv/*' 'lexvaani-in-v0.1.0/lexvaani_in_narratives_all.jsonl'
clean:
	rm -rf dist .pytest_cache
