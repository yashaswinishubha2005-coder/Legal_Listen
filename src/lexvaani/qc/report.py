"""Phase 4 automatic QC. Writes reports/qc_report.md and per-check JSON.

Checks: schema validation · offset alignment · script/language ID · CMI ·
near-duplicates · cross-lingual label consistency · citation validity ·
label leakage · dialogue/oracle consistency · LLM-judge status · human-annotation status.
"""

from __future__ import annotations

import json
import re
import statistics
from collections import Counter, defaultdict
from pathlib import Path

from lexvaani.corpus.parse import load_corpus
from lexvaani.corpus.registry import load_registry, reference_set
from lexvaani.schemas.common import LangVariant
from lexvaani.schemas.dialogue import Dialogue
from lexvaani.schemas.sample import NarrativeSample
from lexvaani.schemas.spec import ScenarioSpec

from .langid import cmi, predict_variant, tag_tokens

STATUTE_PATTERNS = [r"\bsection\s+\d", r"\bBNS\b", r"\bBNSS\b", r"\bIPC\b", r"\bCrPC\b", r"\bIT Act\b",
                    r"ಸೆಕ್ಷನ್\s*\d", r"ಕಲಂ\s*\d", r"धारा\s*\d", r"\bdhara\s*\d", r"\bAct\b"]


def _iter(path: Path, model):
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield line, model


def shingles(text: str, k: int = 3) -> set[tuple]:
    w = re.findall(r"\w+", text.lower())
    return {tuple(w[i:i + k]) for i in range(max(0, len(w) - k + 1))}


def jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def run_qc(root: Path, P: dict) -> dict:
    from lexvaani.resources import glossary
    reports = root / "reports"
    reports.mkdir(exist_ok=True)
    res: dict = {}

    # ---------------------------------------------------- schema + alignment
    counts = Counter()
    fails: list[str] = []
    narratives: list[NarrativeSample] = []
    for path, model, key in [(P["specs"], ScenarioSpec, "specs"), (P["narr"], NarrativeSample, "narratives"),
                             (P["asr"], NarrativeSample, "asr"), (P["dlg"], Dialogue, "dialogues")]:
        with open(path, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                counts[key] += 1
                try:
                    obj = model.model_validate_json(line)   # validators re-verify every span offset
                    if key == "narratives":
                        narratives.append(obj)
                except Exception as e:  # noqa: BLE001
                    counts[key + "_fail"] += 1
                    fails.append(f"{key}: {str(e)[:200]}")
    n_spans = sum(len(s.annotations.entities) + len(s.annotations.events) + len(s.annotations.facts)
                  + len(s.annotations.timexes) for s in narratives)
    res["schema"] = {k: v for k, v in counts.items()}
    res["alignment"] = {"spans_checked_in_clean_narratives": n_spans, "misaligned": counts["narratives_fail"]}

    # ------------------------------------------------------- language / CMI
    lid_ok = Counter()
    lid_tot = Counter()
    cmis: dict[str, list[float]] = defaultdict(list)
    for s in narratives:
        names = {m.span.text for m in s.annotations.entities if m.kind.value == "name"}
        c = cmi(tag_tokens(s.text, s.lang_variant, names))
        s.qc["cmi"] = c
        cmis[s.lang_variant.value].append(c)
        lid_tot[s.lang_variant.value] += 1
        lid_ok[s.lang_variant.value] += predict_variant(s.text) == s.lang_variant
    res["langid_accuracy"] = {k: round(lid_ok[k] / lid_tot[k], 4) for k in lid_tot}
    res["cmi"] = {k: {"mean": round(statistics.mean(v), 2), "median": round(statistics.median(v), 2),
                      "min": min(v), "max": max(v)} for k, v in cmis.items()}
    _cmi_hist(cmis, reports / "figures" / "cmi_histogram.png")

    # ------------------------------------------------------- near duplicates
    groups: dict[tuple, list[NarrativeSample]] = defaultdict(list)
    for s in narratives:
        groups[(s.lang_variant.value, s.annotations.issues[0].value)].append(s)
    dup_pairs, sims = [], []
    for g in groups.values():
        sh = [(s, shingles(s.text)) for s in g]
        for i in range(len(sh)):
            for j in range(i + 1, len(sh)):
                a, b = sh[i], sh[j]
                if a[0].family_id == b[0].family_id:
                    continue
                sim = jaccard(a[1], b[1])
                sims.append(sim)
                if sim >= 0.9:
                    dup_pairs.append((a[0].sample_id, b[0].sample_id, round(sim, 3)))
    res["near_duplicates"] = {"pairs_compared": len(sims), "threshold": 0.9, "pairs_over_threshold": len(dup_pairs),
                              "mean_jaccard_word3": round(statistics.mean(sims), 3) if sims else 0,
                              "examples": dup_pairs[:10]}

    # --------------------------------------- cross-lingual label consistency
    by_spec: dict[str, list[NarrativeSample]] = defaultdict(list)
    for s in narratives:
        by_spec[s.spec_id].append(s)
    incons = []
    for sid, ss in by_spec.items():
        sigs = {}
        for s in ss:
            a = s.annotations
            sigs[s.lang_variant.value] = json.dumps({
                "issues": sorted(i.value for i in a.issues), "triage": a.triage.value,
                "provisions": sorted(a.provisions), "risk": sorted(r.value for r in a.risk_flags),
                "elements": sorted((e.issue_id.value, e.element_id, e.value.value) for e in a.elements),
                "events": sorted((e.event_id, e.negated, e.hypothetical) for e in a.events),
                "timex_values": sorted(t.value for t in a.timexes),
                "facts": sorted((f.element_id or "", f.polarity.value, f.status.value) for f in a.facts),
                "graph_nodes": sorted(Counter(n.type.value for n in a.case_graph.nodes).items()),
                "graph_edges": sorted(Counter(e.type.value for e in a.case_graph.edges).items()),
            }, sort_keys=True)
        if len(set(sigs.values())) > 1:
            incons.append(sid)
    res["crosslingual_label_consistency"] = {
        "specs": len(by_spec), "consistent": len(by_spec) - len(incons), "inconsistent_examples": incons[:10],
        "embedding_and_backtranslation_check": "not run: needs LaBSE / IndicTrans2 downloads (see qc/external.py)"}

    # ---------------------------------------------------- citation validity
    corpus = load_corpus(P["corpus"])
    registry = load_registry(P["registry"])
    ref, basis = reference_set(corpus, registry)
    cited = [p for s in narratives for p in s.annotations.provisions]
    in_ref = sum(p in ref for p in cited)
    in_corpus_ref, _ = reference_set(corpus, {}) if corpus else (set(), "corpus")
    res["citation_validity"] = {
        "basis": basis, "gold_citations": len(cited), "valid_against_basis": in_ref,
        "found_in_parsed_corpus": sum(p in in_corpus_ref for p in cited),
        "registry_size": len(registry), "corpus_sections": len(corpus),
        "verified_by_human": sum(e.verification.value == "verified" for e in registry.values())}

    # --------------------------------------------------------- label leakage
    legal_terms = []
    for g in glossary():
        if g.is_legal_term:
            for lang, term in (("en", g.en), ("kn", g.kn), ("hi", g.hi)):
                t = re.split(r"\s*/\s*|\s*\(", term)[0].strip(" )")   # formal term only, not colloquial alternates
                if len(t) > 3:
                    legal_terms.append((g.term_id, lang, t.lower()))
    leaks = Counter()
    leak_examples = []
    stat_hits = 0
    for s in narratives:
        low = s.text.lower()
        for tid, lang, t in legal_terms:
            if re.search(r"(?<![\w\u0900-\u097F\u0C80-\u0CFF])" + re.escape(t) + r"(?![\w\u0900-\u097F\u0C80-\u0CFF])", low):
                leaks[tid] += 1
                if len(leak_examples) < 15:
                    leak_examples.append((s.sample_id, tid, t))
        if any(re.search(p, s.text, flags=re.I) for p in STATUTE_PATTERNS):
            stat_hits += 1
    res["label_leakage"] = {"samples": len(narratives), "statute_or_section_mentions": stat_hits,
                            "legal_term_hits_by_term": dict(leaks.most_common()),
                            "examples": leak_examples}

    # ------------------------------------------------- dialogue / oracle
    n_dp = n_dlg = 0
    clar = Counter()
    comp_end = []
    with open(P["dlg"], encoding="utf-8") as f:
        for line in f:
            d = Dialogue.model_validate_json(line)
            n_dlg += 1
            n_dp += len(d.decision_points)
            for t in d.turns:
                if t.clarification:
                    clar[t.clarification.value] += 1
            if d.decision_points:
                comp_end.append(d.decision_points[-1].state_after.completeness)
    res["dialogues"] = {"dialogues": n_dlg, "decision_points": n_dp, "clarification_labels": dict(clar),
                        "mean_final_completeness": round(statistics.mean(comp_end), 3) if comp_end else None}

    res["llm_judge"] = {"status": "not run",
                        "reason": "requires GEN/JUDGE API keys; code in src/lexvaani/llm/judge.py, prompts/judge_v1.md"}
    res["human_annotation"] = {"status": "pending",
                               "subset_exported": "annotation/labelstudio/tasks_double.json (>=15%, 2 annotators each)",
                               "iaa": "to be computed with `python -m lexvaani.annotation.iaa` once annotations exist"}
    res["failures"] = fails[:50]
    (reports / "qc_results.json").write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_md(res, reports / "qc_report.md")
    print("qc:", json.dumps({k: res[k] for k in ("schema", "alignment", "langid_accuracy")}, ensure_ascii=False))
    return res


def _cmi_hist(cmis: dict[str, list[float]], path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    path.parent.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7, 3.6))
    keys = [k for k in ("kn-en_latn", "kn-en_mixed", "hi-en_latn") if k in cmis]
    colors = ["#2a78d6", "#d68a2a", "#3a9e5f"]
    for k, c in zip(keys, colors):
        ax.hist(cmis[k], bins=20, range=(0, 60), alpha=0.55, label=k, color=c)
    ax.set_xlabel("Code-Mixing Index (Das & Gambäck)")
    ax.set_ylabel("narratives")
    ax.spines[["top", "right"]].set_visible(False)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _write_md(r: dict, path: Path) -> None:
    L = ["# LexVaani-IN QC report (v0.1, automatic checks)", "",
         "Generated by `make qc`. Raw numbers: `reports/qc_results.json`.", "",
         "## 1. Schema validation and offset alignment", "",
         "| Object | Count | Failed validation |", "|---|---|---|"]
    for k in ("specs", "narratives", "asr", "dialogues"):
        L.append(f"| {k} | {r['schema'].get(k, 0)} | {r['schema'].get(k + '_fail', 0)} |")
    L += ["", f"Every span (entities, triggers, timexes, facts, cues) is re-verified against the text on load: "
          f"**{r['alignment']['spans_checked_in_clean_narratives']}** spans in clean narratives, "
          f"**{r['alignment']['misaligned']}** misaligned. Offsets are produced during rendering, never searched for.", "",
          "## 2. Script / language ID", "",
          "Heuristic variant identification (script ratios + project vocabularies). This is a consistency check, "
          "not an independent LID model.", "", "| Variant | Accuracy |", "|---|---|"]
    L += [f"| {k} | {v:.3f} |" for k, v in r["langid_accuracy"].items()]
    L += ["", "## 3. Code-Mixing Index", "", "| Variant | mean | median | min | max |", "|---|---|---|---|---|"]
    L += [f"| {k} | {v['mean']} | {v['median']} | {v['min']} | {v['max']} |" for k, v in r["cmi"].items()]
    L += ["", "![CMI histogram](figures/cmi_histogram.png)", "",
          "## 4. Near-duplicates", "",
          f"Word-trigram Jaccard between narratives of the same issue and variant from *different* families: "
          f"{r['near_duplicates']['pairs_compared']} pairs, mean {r['near_duplicates']['mean_jaccard_word3']}, "
          f"**{r['near_duplicates']['pairs_over_threshold']}** pairs ≥ {r['near_duplicates']['threshold']}.", "",
          "Template-based generation makes narratives of the same issue lexically similar by design; the split is "
          "by family so this does not leak labels, but it limits lexical diversity (see DATASHEET, limitations).", "",
          "## 5. Cross-lingual meaning preservation", "",
          f"All six variants of a spec must carry identical labels (issues, elements, events, timex values, facts, "
          f"triage, provisions, graph shape): **{r['crosslingual_label_consistency']['consistent']} / "
          f"{r['crosslingual_label_consistency']['specs']}** specs consistent.", "",
          f"Embedding similarity / back-translation: {r['crosslingual_label_consistency']['embedding_and_backtranslation_check']}.", "",
          "## 6. Citation validity", ""]
    c = r["citation_validity"]
    L += [f"- Basis for validity: **{c['basis']}** ({'parsed official corpus' if c['basis'] == 'corpus' else 'provision registry — the corpus is empty until the Act PDFs are added'})",
          f"- Gold citations: {c['gold_citations']}; valid against basis: {c['valid_against_basis']}",
          f"- Found in the parsed corpus: **{c['found_in_parsed_corpus']}** (corpus sections: {c['corpus_sections']})",
          f"- Registry entries verified by a human: **{c['verified_by_human']} / {c['registry_size']}** — Gate 1 pending", "",
          "## 7. Label leakage", "",
          f"- Narratives mentioning a statute / section number: **{r['label_leakage']['statute_or_section_mentions']}** "
          f"of {r['label_leakage']['samples']}",
          f"- Glossary legal-term hits (informal narratives should rarely use these): "
          f"{json.dumps(r['label_leakage']['legal_term_hits_by_term'], ensure_ascii=False)}", "",
          "## 8. Dialogues", "",
          f"- {r['dialogues']['dialogues']} dialogues, {r['dialogues']['decision_points']} oracle decision points",
          f"- T12 labels: {json.dumps(r['dialogues']['clarification_labels'])}",
          f"- Mean case completeness after the dialogue: {r['dialogues']['mean_final_completeness']}", "",
          "## 9. LLM-as-judge", "", f"Status: **{r['llm_judge']['status']}** — {r['llm_judge']['reason']}.", "",
          "## 10. Human annotation and IAA", "",
          f"Status: **{r['human_annotation']['status']}**. {r['human_annotation']['subset_exported']}. "
          f"IAA: {r['human_annotation']['iaa']}. No agreement numbers are reported until real annotations exist.", ""]
    if r["failures"]:
        L += ["## Validation failures", ""] + [f"- {x}" for x in r["failures"]]
    path.write_text("\n".join(L) + "\n", encoding="utf-8")
