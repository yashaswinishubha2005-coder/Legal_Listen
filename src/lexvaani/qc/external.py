"""Optional QC with external models (not run in v0.1: huggingface.co was unreachable from the build host).

    IndicLID      language/script ID           -> compare with qc.langid.predict_variant
    LaBSE         cross-lingual embedding sim. -> en vs kn/hi narrative of the same spec (expect high)
    IndicTrans2   back-translation             -> chrF of kn/hi -> en against the en narrative

Each function returns None when the model or its dependencies are missing, so `make qc` never fails on them.
Install with:  pip install torch transformers sentence-transformers  (not pinned in requirements.txt).
"""

from __future__ import annotations


def _try_import(name: str):
    try:
        return __import__(name)
    except ImportError:
        return None


def labse_similarity(pairs: list[tuple[str, str]]) -> list[float] | None:
    st = _try_import("sentence_transformers")
    if st is None:
        return None
    model = st.SentenceTransformer("sentence-transformers/LaBSE")
    a = model.encode([p[0] for p in pairs], normalize_embeddings=True)
    b = model.encode([p[1] for p in pairs], normalize_embeddings=True)
    return [float((x * y).sum()) for x, y in zip(a, b)]


def indiclid_predict(texts: list[str]) -> list[str] | None:
    """Placeholder: IndicLID (AI4Bharat) ships as a separate package and checkpoint; wire it here."""
    return None


def indictrans2_backtranslate(texts: list[str], src_lang: str) -> list[str] | None:
    """Placeholder: IndicTrans2 (ai4bharat/indictrans2-indic-en-1B) via transformers; wire it here."""
    return None
