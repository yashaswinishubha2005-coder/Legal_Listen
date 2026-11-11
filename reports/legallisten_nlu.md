# LegalListen offline NLU (trained on LexVaani-IN train split)

Training narratives: 3328 (clean + ASR-noisy) · sentence examples: 15057 · sentence classes: 247 · training time: 169.9 s

| Model | Split | Metric | Score |
|---|---|---|---|
| Issue identification (T1) | dev | micro-F1 / macro-F1 | 1.000 / 1.000 |
| Issue identification (T1) | test | micro-F1 / macro-F1 | 1.000 / 1.000 |
| Issue identification (T1) | test ASR-noisy | micro-F1 / macro-F1 | 0.999 / 0.999 |
| Claim → element + polarity (T6/T7) | dev | accuracy (n=1698) | 0.984 |
| Claim → element + polarity (T6/T7) | test | accuracy (n=3030) | 0.964 |
| Claim → element + polarity (T6/T7) | test ASR-noisy | accuracy (n=4013) | 0.962 |

T1 micro-F1 on test by language variant:

| variant | micro-F1 |
|---|---|
| en | 1.000 |
| hi | 0.998 |
| hi-en_latn | 1.000 |
| kn | 1.000 |
| kn-en_latn | 1.000 |
| kn-en_mixed | 1.000 |

Keyword baseline for comparison (reports/baselines.md): T1 micro-F1 0.655.

**Caveat.** Train and test are template-generated (different scenario families, same template inventory), so these scores overestimate accuracy on real user language. The models are a fallback for when no LLM is configured; with Gemini enabled, extraction is done by the LLM and validated against the issue library.
