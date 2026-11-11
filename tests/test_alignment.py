import pytest

from lexvaani.schemas.common import LangVariant


@pytest.fixture(scope="module")
def samples(specs, lib, bank):
    from lexvaani.render.narrative import render_narrative
    return [render_narrative(s, lib, v, bank) for s in specs[::7] for v in LangVariant]


def test_spans_match_text(samples):
    for smp in samples:
        a = smp.annotations
        for m in a.entities:
            assert smp.text[m.span.start:m.span.end] == m.span.text
        for e in a.events:
            assert smp.text[e.trigger.start:e.trigger.end] == e.trigger.text
        for f in a.facts:
            for c in f.negation_cues + f.hedge_cues:
                assert f.span.start <= c.start and c.end <= f.span.end   # cues lie inside their claim


def test_graph_spans_match_text(samples):
    for smp in samples:
        for n in smp.annotations.case_graph.nodes:
            for sp in n.source_spans:
                sp.verify_against(smp.text)


def test_asr_noise_reprojects_exactly(samples):
    from lexvaani.noise.asr import corrupt
    for smp in samples[:60]:
        for lvl in ("low", "high"):
            noisy = corrupt(smp, lvl)          # NarrativeSample validator re-verifies every span
            assert noisy.noise.clean_sample_id == smp.sample_id
            kept = {m.mention_id for m in noisy.annotations.entities}
            assert kept | set(noisy.noise.dropped_mentions) >= {m.mention_id for m in smp.annotations.entities}


def test_crosslingual_labels_identical(specs, lib, bank):
    from lexvaani.render.narrative import render_narrative
    for s in specs[::9]:
        sigs = set()
        for v in LangVariant:
            a = render_narrative(s, lib, v, bank).annotations
            sigs.add((tuple(sorted((e.element_id, e.value.value) for e in a.elements)),
                      tuple(sorted(t.value for t in a.timexes)), a.triage.value, tuple(a.provisions)))
        assert len(sigs) == 1, s.spec_id


def test_paraphrase_marker_roundtrip(samples):
    from lexvaani.llm.paraphrase import mark, unmark
    smp = samples[0]
    marked, spans = mark(smp)
    text, where = unmark(marked, spans)
    assert text == smp.text
    for k, sp in enumerate(spans):
        a, b = where[k]
        assert text[a:b] == sp.text
    # an altered marker must be rejected, never repaired
    broken = marked.replace("⟦0|", "⟦0|x", 1)
    assert unmark(broken, spans) is None


def test_fake_provider_paraphrase(samples, tmp_path, monkeypatch):
    from lexvaani.llm import provider as P
    from lexvaani.llm.paraphrase import mark, paraphrase
    monkeypatch.setattr(P, "CACHE", tmp_path / "cache")
    monkeypatch.setattr(P, "USAGE_LOG", tmp_path / "usage.jsonl")
    smp = samples[1]
    marked, _ = mark(smp)
    fake = P.Fake("fake-model")
    P.Fake.script = ["Actually, " + marked]
    res = paraphrase(smp, fake)
    assert res["status"] == "ok" and res["text"].startswith("Actually, ")
    P.Fake.script = ["totally different text"]
    fake2 = P.Fake("fake-model-2")
    assert paraphrase(smp, fake2)["status"] == "rejected"
