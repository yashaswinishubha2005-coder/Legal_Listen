"""Offline NLU models trained on LexVaani-IN (train split only).

* issue model    — narrative -> multi-label legal issues (+ x.out_of_scope / x.non_legal)
* sentence model — one sentence -> what it asserts:
      el|<issue>|<element>|satisfied|contradicted     a legal element
      ev|<issue>|<evidence>|held|missing             an evidence statement
      risk|<flag>                                    a risk fact
      none                                           anything else
Character n-grams (2–5) + word n-grams make the models script- and spelling-robust across
English, Kannada, Hindi and romanised code-mixed text. Train: python -m legallisten.nlu.train
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import joblib

from ..knowledge import ROOT

MODEL_PATH = ROOT / "models" / "legallisten_nlu.joblib"


@dataclass
class SentencePred:
    label: str
    prob: float
    alternatives: list[tuple[str, float]]


class NLUModels:
    def __init__(self, bundle: dict):
        self.issue_vec = bundle["issue_vec"]
        self.issue_clf = bundle["issue_clf"]
        self.issue_labels: list[str] = bundle["issue_labels"]
        self.sent_vec = bundle["sent_vec"]
        self.sent_clf = bundle["sent_clf"]
        self.meta = bundle.get("meta", {})

    def issue_probs(self, text: str) -> dict[str, float]:
        p = self.issue_clf.predict_proba(self.issue_vec.transform([text]))[0]
        return {lab: float(v) for lab, v in zip(self.issue_labels, p)}

    def sentence(self, text: str, top: int = 3) -> SentencePred:
        p = self.sent_clf.predict_proba(self.sent_vec.transform([text]))[0]
        order = p.argsort()[::-1][:top]
        alts = [(str(self.sent_clf.classes_[i]), float(p[i])) for i in order]
        return SentencePred(alts[0][0], alts[0][1], alts)

    def sentence_probs(self, text: str) -> dict[str, float]:
        p = self.sent_clf.predict_proba(self.sent_vec.transform([text]))[0]
        return {str(c): float(v) for c, v in zip(self.sent_clf.classes_, p)}


@lru_cache(maxsize=1)
def load(path: Path = MODEL_PATH) -> NLUModels | None:
    if not path.exists():
        return None
    return NLUModels(joblib.load(path))
