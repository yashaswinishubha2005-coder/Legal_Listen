<!-- prompt: paraphrase_v1 · used by src/lexvaani/llm/paraphrase.py · change => bump version -->
You are helping build a research dataset of how ordinary people in Karnataka describe
legal problems. Rewrite the narrative below so it sounds like a real person speaking
informally in the language/script variant **{{VARIANT}}**:

- en = Indian English; kn = Kannada script; hi = Devanagari Hindi;
  kn-en_latn = Kanglish in Latin script; kn-en_mixed = Kannada script with English words
  in Latin script; hi-en_latn = Hinglish in Latin script.
- Keep every fact exactly the same. Do not add facts, people, dates, amounts or legal terms.
- Do NOT mention laws, sections or legal terms the speaker did not already use.
- You may reorder sentences, add fillers ("ಅಂದ್ರೆ", "matlab", "actually"), hesitations and
  natural code-switching.
- Every segment written as ⟦k|text⟧ MUST appear in your output exactly once, copied
  character-for-character including the brackets and the number. You may move it, but you
  must not change the text inside it.
- Output only the rewritten narrative.

Narrative:
{{TEXT}}
