from pathlib import Path

from lexvaani.schemas.corpus import ActInfo


def _make_pdf(path: Path) -> None:
    from fpdf import FPDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("helvetica", size=11)
    body = [
        "CHAPTER I", "PRELIMINARY",
        "1. Short title.-This is a synthetic test act used only for unit tests.",
        "2. Definitions.-In this Act, unless the context otherwise requires, words have their meaning.",
        "CHAPTER II", "OFFENCES",
        "3. Test offence.-(1) Whoever does a test thing shall be liable.",
        "(2) This sub-section continues the same section.",
        "5. Another offence.-Whoever does another thing.",
    ]
    for line in body:
        pdf.multi_cell(0, 6, line, new_x="LMARGIN", new_y="NEXT")
    pdf.output(str(path))


def test_parse_synthetic_act(tmp_path):
    from lexvaani.corpus.parse import parse_act
    pdf = tmp_path / "test_act.pdf"
    try:
        _make_pdf(pdf)
    except Exception:                       # font without em-dash support: fall back to ASCII
        import pytest
        pytest.skip("fpdf could not render the test PDF")
    act = ActInfo(code="TEST", title="Test Act", year=2025, file_glob="test_act")
    res = parse_act(pdf, act)
    ids = [r.section_id for r in res.records]
    assert ids[:3] == ["1", "2", "3"] and "5" in ids
    s3 = next(r for r in res.records if r.section_id == "3")
    assert "sub-section continues" in s3.text           # text copied, nothing invented
    assert s3.chapter and s3.chapter.startswith("II")
    assert any("missing section numbers" in w for w in res.warnings)   # section 4 is reported, not guessed


def test_registry_against_corpus(lib):
    from lexvaani.corpus.registry import build_registry, reference_set
    from lexvaani.schemas.corpus import ProvisionRecord
    rec = ProvisionRecord(provision_id="BNS:303", act="BNS", act_title="x", year=2023, section_id="303",
                          title="Theft", text="(verbatim text would be here)", jurisdiction="IN", source_file="t.pdf")
    reg = build_registry(lib, {"BNS:303": rec})
    e = next(x for x in reg if x.provision_id == "BNS:303(2)")
    assert e.in_corpus and e.title_match
    ids, basis = reference_set({"BNS:303": rec}, {x.provision_id: x for x in reg})
    assert basis == "corpus" and "BNS:303(2)" in ids and "IPC:379" not in ids
