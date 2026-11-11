<!-- prompt: judge_v1 · used by src/lexvaani/llm/judge.py · the judge model must differ from the generator -->
You are a careful annotator. Rate the narrative (variant **{{VARIANT}}**) against the
hidden case specification. Use integers 1-5.

- naturalness: does it read like a real person speaking this variant? (5 = fully natural)
- faithfulness: does it state exactly the facts in the spec, with no additions or omissions?
- label_correctness: are the listed epistemic statuses / polarities right for what the text says?

Case specification:
{{SPEC}}

Narrative:
{{TEXT}}

Reply with JSON only:
{"naturalness": n, "faithfulness": n, "label_correctness": n, "comment": "<one sentence>"}
