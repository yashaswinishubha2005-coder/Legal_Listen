"""One command for any task:  python -m eval.run --task t07 --pred preds.jsonl [--gold ...]"""
import argparse
import importlib
import json

from eval.common import DEFAULT_GOLD, read_jsonl

TASKS = {"t01": ("t01_issues", "narratives"), "t02": ("t02_entities", "narratives"),
         "t03": ("t03_events", "narratives"), "t04": ("t04_temporal", "narratives"),
         "t05": ("t05_coref", "narratives"), "t06": ("t06_epistemic", "narratives"),
         "t07": ("t07_elements", "narratives"), "t08": ("t08_graph", "narratives"),
         "t09": ("t09_next_question", "dialogues"), "t10": ("t10_retrieval", "narratives"),
         "t11": ("t11_explanation", "explanations"), "t12": ("t12_clarification", "dialogues"),
         "t13": ("t13_triage", "narratives")}

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--task", required=True, choices=sorted(TASKS))
    ap.add_argument("--pred", required=True)
    ap.add_argument("--gold", default=None)
    a = ap.parse_args()
    mod, kind = TASKS[a.task]
    m = importlib.import_module(f"eval.{mod}")
    gold = read_jsonl(a.gold or DEFAULT_GOLD[kind])
    print(json.dumps(m.score(gold, read_jsonl(a.pred)), indent=2, ensure_ascii=False))
