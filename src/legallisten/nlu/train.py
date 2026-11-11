"""Train LegalListen's offline NLU on the LexVaani-IN train split; report dev / test scores.

    python -m legallisten.nlu.train          -> models/legallisten_nlu.joblib, reports/legallisten_nlu.md

Sentence training data: (a) claim spans of the train narratives, labelled with their element and
polarity; (b) every library template (elements, evidence, risk facts, setup, discourse) rendered in
all six language variants with generic mentions. Dev/test narratives are never used for training.
"""

from __future__ import annotations

import json
import random
import time
from collections import Counter

import joblib
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import f1_score
from sklearn.multiclass import OneVsRestClassifier
from sklearn.pipeline import FeatureUnion
from sklearn.preprocessing import MultiLabelBinarizer

from lexvaani.render.lexicon import lexicon
from lexvaani.schemas.common import LangVariant

from ..knowledge import ROOT, kb, render_generic, strip_markup
from .model import MODEL_PATH

REL = ROOT / "release" / "lexvaani-in-v0.1.0"


def _read(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def vectorizer() -> FeatureUnion:
    return FeatureUnion([
        ("char", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), min_df=2, sublinear_tf=True, max_features=60000, dtype=np.float32)),
        ("word", TfidfVectorizer(analyzer="word", ngram_range=(1, 2), min_df=2, sublinear_tf=True, token_pattern=r"(?u)[\wಀ-೿ऀ-ॿ']+", max_features=30000, dtype=np.float32)),
    ])


def library_sentences() -> list[tuple[str, str]]:
    k = kb()
    out = []
    for iid, issue in k.issues.items():
        for v in LangVariant:
            out.append((render_generic(issue.setup[v], issue, v), "none"))
            for el in issue.elements:
                for val in ("satisfied", "contradicted"):
                    out.append((render_generic(getattr(el, val)[v], issue, v), f"el|{iid}|{el.element_id}|{val}"))
                if el.implicit:
                    out.append((render_generic(el.implicit[v], issue, v), f"el|{iid}|{el.element_id}|satisfied"))
            for ev in issue.evidence:
                out.append((render_generic(ev.held[v], issue, v), f"ev|{iid}|{ev.evidence_id}|held"))
                out.append((render_generic(ev.missing[v], issue, v), f"ev|{iid}|{ev.evidence_id}|missing"))
            for rf in issue.risk_facts:
                out.append((render_generic(rf.template[v], issue, v), f"risk|{rf.flag.value}"))
    lex = lexicon()
    for group in ("fillers", "emotion"):
        for v, items in lex["discourse"][group].items():
            for s in items:
                out.append((strip_markup(s), "none"))
    for group in ("dont_know", "reexplain", "correction"):
        for v, items in lex["dialogue"][group].items():
            for s in items:
                out.append((strip_markup(s), "none"))
    return [(t, lab) for t, lab in out if t.strip()]


SENT_KEEP = 0.06     # share of sentence-classifier weights kept; on the dev split this changes no prediction


def compact(sclf, keep: float = SENT_KEEP):
    """Keep only the largest sentence-classifier weights, stored sparse (49 MB of weights -> about 4 MB)."""
    w = np.asarray(sclf.coef_.toarray() if hasattr(sclf.coef_, "toarray") else sclf.coef_, dtype=np.float32)
    thr = np.quantile(np.abs(w), 1 - keep)
    sclf.coef_ = np.where(np.abs(w) >= thr, w, 0).astype(np.float32)
    sclf.sparsify()
    return sclf


def narrative_sentences(rows) -> list[tuple[str, str]]:
    out = []
    for r in rows:
        for f in r["annotations"]["facts"]:
            if f.get("element_id") and f["issue_id"] and not f["issue_id"].startswith("x."):
                out.append((f["span"]["text"], f"el|{f['issue_id']}|{f['element_id']}|{f['polarity']}"))
    return out


def main() -> None:
    t0 = time.time()
    train = _read(REL / "narratives" / "train.jsonl") + _read(REL / "narratives_asr" / "train.jsonl")
    dev = _read(REL / "narratives" / "dev.jsonl")
    test = _read(REL / "narratives" / "test.jsonl")
    test_asr = _read(REL / "narratives_asr" / "test.jsonl")

    # ---------------- issue model
    mlb = MultiLabelBinarizer()
    y = mlb.fit_transform([r["annotations"]["issues"] for r in train])
    ivec = vectorizer()
    X = ivec.fit_transform([r["text"] for r in train])
    iclf = OneVsRestClassifier(LogisticRegression(C=8.0, max_iter=3000, class_weight="balanced"), n_jobs=-1).fit(X, y)

    def issue_pred(rows, thr=0.5):
        P = iclf.predict_proba(ivec.transform([r["text"] for r in rows]))
        preds = []
        for p in P:
            lab = [mlb.classes_[i] for i in np.where(p >= thr)[0]]
            if not lab:
                lab = [mlb.classes_[int(p.argmax())]]
            preds.append(lab)
        return preds

    def issue_f1(rows, preds):
        yt = mlb.transform([r["annotations"]["issues"] for r in rows])
        yp = mlb.transform(preds)
        return f1_score(yt, yp, average="micro", zero_division=0), f1_score(yt, yp, average="macro", zero_division=0)

    # ---------------- sentence model
    sents = narrative_sentences(train) + library_sentences() * 3
    random.Random(13).shuffle(sents)
    svec = vectorizer()
    Xs = svec.fit_transform([t for t, _ in sents])
    sclf = LogisticRegression(C=10.0, max_iter=3000).fit(Xs, [lab for _, lab in sents])

    def sent_acc(rows):
        data = narrative_sentences(rows)
        pred = sclf.predict(svec.transform([t for t, _ in data]))
        return float(np.mean([p == g for p, (_, g) in zip(pred, data)])), len(data)

    res = {
        "issue_dev": issue_f1(dev, issue_pred(dev)), "issue_test": issue_f1(test, issue_pred(test)),
        "issue_test_asr": issue_f1(test_asr, issue_pred(test_asr)),
        "sent_dev": sent_acc(dev), "sent_test": sent_acc(test), "sent_test_asr": sent_acc(test_asr),
        "n_train_narratives": len(train), "n_sentences": len(sents), "n_sentence_classes": len(sclf.classes_),
        "seconds": round(time.time() - t0, 1),
    }
    for est in [sclf] + list(iclf.estimators_):          # float32 weights: half the size, same predictions
        est.coef_ = est.coef_.astype(np.float32)
        est.intercept_ = est.intercept_.astype(np.float32)
    compact(sclf)
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump({"issue_vec": ivec, "issue_clf": iclf, "issue_labels": list(mlb.classes_), "sent_vec": svec,
                 "sent_clf": sclf, "meta": {k: v for k, v in res.items()}}, MODEL_PATH, compress=3)
    by_variant = {}
    for v in sorted({r["lang_variant"] for r in test}):
        rows = [r for r in test if r["lang_variant"] == v]
        by_variant[v] = issue_f1(rows, issue_pred(rows))[0]
    lines = ["# LegalListen offline NLU (trained on LexVaani-IN train split)", "",
             f"Training narratives: {len(train)} (clean + ASR-noisy) · sentence examples: {len(sents)} · "
             f"sentence classes: {len(sclf.classes_)} · training time: {res['seconds']} s", "",
             "| Model | Split | Metric | Score |", "|---|---|---|---|",
             f"| Issue identification (T1) | dev | micro-F1 / macro-F1 | {res['issue_dev'][0]:.3f} / {res['issue_dev'][1]:.3f} |",
             f"| Issue identification (T1) | test | micro-F1 / macro-F1 | {res['issue_test'][0]:.3f} / {res['issue_test'][1]:.3f} |",
             f"| Issue identification (T1) | test ASR-noisy | micro-F1 / macro-F1 | {res['issue_test_asr'][0]:.3f} / {res['issue_test_asr'][1]:.3f} |",
             f"| Claim → element + polarity (T6/T7) | dev | accuracy (n={res['sent_dev'][1]}) | {res['sent_dev'][0]:.3f} |",
             f"| Claim → element + polarity (T6/T7) | test | accuracy (n={res['sent_test'][1]}) | {res['sent_test'][0]:.3f} |",
             f"| Claim → element + polarity (T6/T7) | test ASR-noisy | accuracy (n={res['sent_test_asr'][1]}) | {res['sent_test_asr'][0]:.3f} |",
             "", "T1 micro-F1 on test by language variant:", "", "| variant | micro-F1 |", "|---|---|"]
    lines += [f"| {v} | {s:.3f} |" for v, s in by_variant.items()]
    lines += ["", "Keyword baseline for comparison (reports/baselines.md): T1 micro-F1 0.655.", "",
              "**Caveat.** Train and test are template-generated (different scenario families, same template "
              "inventory), so these scores overestimate accuracy on real user language. The models are a fallback "
              "for when no LLM is configured; with Gemini enabled, extraction is done by the LLM and validated "
              "against the issue library.", ""]
    (ROOT / "reports" / "legallisten_nlu.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(res, indent=1), Counter(lab.split("|")[0] for _, lab in sents))


if __name__ == "__main__":
    main()
