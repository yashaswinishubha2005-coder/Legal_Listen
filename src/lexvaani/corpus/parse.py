"""PDF -> section-level JSONL. Text is ONLY copied from the PDF; nothing is filled in.

India Code bare-act PDFs typically print sections as

    303. Theft.—(1) Whoever, intending to take dishonestly ...

with chapter headings such as "CHAPTER XVII" followed by a title line. The
parser is deliberately conservative: anything it cannot segment confidently is
reported in the parse report instead of being guessed.
"""

from __future__ import annotations

import fnmatch
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from pypdf import PdfReader

from lexvaani.schemas.corpus import ActInfo, ProvisionRecord

from .acts import ACTS

SECTION_RE = re.compile(
    r"(?m)^\s*(?:\d{1,2}\s?\[)?(?P<num>\d{1,3}[A-Z]{0,3})\s?\.\s+"     # optional amendment marker such as "2["
    r"(?P<head>[^\n]{2,220}?(?:\n(?=\s*[a-z])[^\n]{1,120}?)?)"            # a heading may wrap onto one more (lower-case) line
    r"(?:\s*\.?\s*[—–―]+|\.-{1,2})\s*(?P<rest>.*)$")
CHAPTER_RE = re.compile(r"(?m)^\s*CHAPTER\s+(?P<num>[IVXLC]+[A-Z]?)\s*$")


@dataclass
class ParseResult:
    act: str
    source_file: str
    records: list[ProvisionRecord] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    pages: int = 0


FOOT_START = re.compile(r"^\s*\d{1,3}\s?\.\s+\S")
FOOT_WORDS = re.compile(r"\b(?:Ins|Subs|Rep|Omitted|Added|Inserted|Substituted|Renumbered)\b\.?\s+(?:by|vide|ibid)|"
                        r"\bw\.e\.f\.|\bby Act \d+ of \d{4}|\bibid\b")
PAGE_STAMP = re.compile(r"^\s*(?:IndiaCode|\d{1,4})\s*$")


def clean_page(text: str) -> str:
    """Drop the India Code page stamp and the amendment footnotes printed at the foot of a page.

    A footnote block is cut only when it runs to the end of the page and every note in it reads like an
    amendment note ("1. Subs. by Act 26 of 1955 … (w.e.f. …)"), with at most two wrapped lines per note;
    otherwise the page is kept as it is. The law text itself is never changed.
    """
    lines = text.split("\n")
    while lines and (not lines[-1].strip() or PAGE_STAMP.match(lines[-1])):
        lines.pop()
    while lines and (not lines[0].strip() or PAGE_STAMP.match(lines[0])):
        lines.pop(0)
    cut = None
    for k in range(len(lines)):
        if not (FOOT_START.match(lines[k]) and FOOT_WORDS.search(lines[k][:90])):
            continue
        ok, run = True, 0
        for ln in lines[k + 1:]:
            if not ln.strip():
                continue
            if FOOT_START.match(ln) and FOOT_WORDS.search(ln[:90]):
                run = 0
            elif FOOT_START.match(ln):           # a numbered line that is not an amendment note: real text follows
                ok = False
                break
            else:
                run += 1
                if run > 2:
                    ok = False
                    break
        if ok:
            cut = k
            break
    if cut is not None:
        lines = lines[:cut]
    return "\n".join(lines)


def extract_pages(path: Path) -> list[str]:
    reader = PdfReader(str(path))
    return [clean_page(p.extract_text() or "") for p in reader.pages]


def _clean(t: str) -> str:
    t = t.replace("­", "")
    t = re.sub(r"(?<![\w(\[])\d{1,2}\s?\[", "[", t)      # amendment markers such as "4[imprisonment" -> "[imprisonment"
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"-\n(?=[a-z])", "", t)          # hyphenated line breaks
    return t.strip()


def parse_act(path: Path, act: ActInfo) -> ParseResult:
    res = ParseResult(act=act.code, source_file=path.name)
    pages = extract_pages(path)
    res.pages = len(pages)
    if not any(p.strip() for p in pages):
        res.warnings.append("no extractable text (scanned PDF?) — needs OCR; nothing parsed")
        return res
    full = ""
    page_of: list[int] = []
    for i, p in enumerate(pages, start=1):
        p = p + "\n"
        full += p
        page_of += [i] * len(p)
    chapters = [(m.start(), m.group("num"), _next_line(full, m.end())) for m in CHAPTER_RE.finditer(full)]
    matches = list(SECTION_RE.finditer(full))
    if not matches:
        res.warnings.append("no section headings matched the expected '<n>. <title>.—' pattern")
        return res
    seen: set[str] = set()
    prev_num = 0
    for k, m in enumerate(matches):
        num = m.group("num")
        start = m.start()
        end = matches[k + 1].start() if k + 1 < len(matches) else len(full)
        body = _clean(m.group("rest") + full[m.end():end])
        head = re.sub(r"\s*\n\s*", " ", _clean(m.group("head")))
        n_int = int(re.match(r"\d+", num).group())
        warn = []
        if num in seen:
            warn.append(f"duplicate section number {num} (cross-reference or schedule?)")
        if n_int < prev_num and not num[-1].isalpha():
            warn.append(f"section {num} after {prev_num}: out of order")
        if not body:
            warn.append("empty body")
            res.warnings.append(f"{act.code} s.{num}: empty body, skipped")
            continue
        seen.add(num)
        prev_num = max(prev_num, n_int)
        chap = next((f"{c[1]} {c[2]}".strip() for c in reversed(chapters) if c[0] < start), None)
        res.records.append(ProvisionRecord(
            provision_id=f"{act.code}:{num}", act=act.code, act_title=act.title, year=act.year, section_id=num,
            title=head or None, text=body, chapter=chap, jurisdiction=act.jurisdiction,
            effective_from=act.effective_from, source_file=path.name,
            source_pages=sorted({page_of[min(start, len(page_of) - 1)], page_of[min(end - 1, len(page_of) - 1)]}),
            official_url=act.official_url, parse_warnings=warn))
        if warn:
            res.warnings += [f"{act.code} s.{num}: {w}" for w in warn]
    gaps = _gaps([int(re.match(r"\d+", r.section_id).group()) for r in res.records])
    if gaps:
        res.warnings.append(f"missing section numbers (not found in PDF text): {gaps[:40]}{'…' if len(gaps) > 40 else ''}")
    return res


def _next_line(text: str, pos: int) -> str:
    rest = text[pos:].lstrip("\n")
    return rest.split("\n", 1)[0].strip()[:120]


def _gaps(nums: list[int]) -> list[int]:
    if not nums:
        return []
    s = set(nums)
    return [n for n in range(1, max(nums) + 1) if n not in s]


def find_pdf(raw_dir: Path, act: ActInfo) -> Path | None:
    for p in sorted(raw_dir.glob("*.pdf")):
        if fnmatch.fnmatch(p.name.lower(), act.file_glob.lower() + ".pdf") or \
                fnmatch.fnmatch(p.name.lower(), act.file_glob.lower()):
            return p
    return None


def build_corpus(raw_dir: Path, out_jsonl: Path, report_md: Path) -> dict:
    out_jsonl.parent.mkdir(parents=True, exist_ok=True)
    rows, lines = [], ["# Law corpus parse report", "",
                       "Text is copied from the PDFs only. Nothing is written from memory.", "",
                       "| Act | File | Pages | Sections parsed | Warnings |", "|---|---|---|---|---|"]
    details = []
    missing = []
    for act in ACTS:
        pdf = find_pdf(raw_dir, act)
        if pdf is None:
            missing.append(act)
            lines.append(f"| {act.code} | **missing** (expected `{act.file_glob}.pdf`) | – | 0 | – |")
            continue
        try:
            res = parse_act(pdf, act)
        except Exception as e:  # noqa: BLE001 — report every failure, never crash the batch
            lines.append(f"| {act.code} | {pdf.name} | ? | 0 | parse error: {type(e).__name__}: {e} |")
            continue
        rows += [r.model_dump() for r in res.records]
        lines.append(f"| {act.code} | {pdf.name} | {res.pages} | {len(res.records)} | {len(res.warnings)} |")
        if res.warnings:
            details += [f"### {act.code}", ""] + [f"- {w}" for w in res.warnings[:200]] + [""]
    with open(out_jsonl, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    lines += ["", f"**Total sections:** {len(rows)}", ""]
    if missing:
        lines += ["## Missing PDFs", "", "Place the official bare-act PDFs (e.g. from indiacode.nic.in) in "
                  "`data/raw/acts/` with names matching the patterns below, then run `make corpus`.", ""]
        lines += [f"- {a.code} — {a.title}, {a.year} (`{a.file_glob}.pdf`)" for a in missing] + [""]
    if details:
        lines += ["## Warnings", ""] + details
    report_md.parent.mkdir(parents=True, exist_ok=True)
    report_md.write_text("\n".join(lines), encoding="utf-8")
    return {"sections": len(rows), "missing": [a.code for a in missing]}


def load_corpus(path: Path) -> dict[str, ProvisionRecord]:
    if not path.exists():
        return {}
    out = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                r = ProvisionRecord.model_validate_json(line)
                out.setdefault(r.provision_id, r)   # first occurrence is the section; later repeats are schedules
    return out
