# Baselines and evaluator sanity checks (test split)

`gold` rows feed the gold labels back as predictions; they must score 1.0 (or 0 GED) and verify the evaluators. Other rows are simple reference baselines.

| Task | System | Metrics |
|---|---|---|
| T1 | keyword | micro_f1=0.655, macro_f1=0.640, top3_accuracy=0.850 |
| T1 | gold | micro_f1=1.000, macro_f1=1.000 |
| T2 | regex(TIME,MONEY) | strict.f1=0.124, partial.f1=0.124 |
| T2 | gold | strict.f1=1.000 |
| T3 | gold | trigger.f1=1.000, argument.f1=1.000 |
| T4 | gold | timex_value_accuracy=1.000, tlink.f1=1.000 |
| T5 | singletons(gold mentions) | conll_f1=0.421 |
| T5 | gold | conll_f1=1.000 |
| T6 | all-reported+neg-lexicon | status_macro_f1=0.312, cue.f1=0.765 |
| T7 | all-unknown | macro_f1=0.157, critical_macro_f1=0.164 |
| T7 | all-satisfied | macro_f1=0.252, critical_macro_f1=0.264 |
| T8 | gold | node.f1=1.000, edge.f1=1.000, normalised_graph_edit_distance=0.000 |
| T9 | random | hit@1=0.554, hit@1_strict=0.280, mrr=0.734 |
| T9 | critical-first | hit@1=0.668, hit@1_strict=0.500, mrr=0.791 |
| T10 | keyword-issue->all-candidates (+1 fake id) | recall@5=0.705, ndcg@10=0.754, citation_validity=0.859 |
| T11 | summary-only | en.chrf=17.922, kn.chrf=17.934, hi.chrf=17.348 |
| T12 | majority(new_fact) | macro_f1=0.309, accuracy=0.865 |
| T12 | keyword | macro_f1=0.945, accuracy=0.978 |
| T13 | keyword-urgency+issue-default | urgent_recall=0.575, accuracy=0.704, macro_f1=0.703 |
| T13 | always-lawyer | urgent_recall=0.000, accuracy=0.462, macro_f1=0.210 |

## T9 interactive: case completeness after N questions

| Policy | N=1 | N=3 |
|---|---|---|
| oracle | 0.684 | 0.916 |
| random | 0.730 | 0.813 |
