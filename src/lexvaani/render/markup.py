"""Template markup parser and offset-tracking sentence builder.

Every annotation is produced *while* text is assembled, so offsets are exact
by construction; nothing is ever located by searching the finished text.
Markup reference: ``lexvaani.schemas.issue_library`` module docstring.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable

TOKEN_RE = re.compile(
    r"\{g:(?P<gslot>[A-Z][A-Z0-9_]*)\|(?P<gopts>[^}]*)\}"     # gender alternation
    r"|\{(?P<slot>[A-Z][A-Z0-9_]*)(?:\.(?P<case>[a-z_]+))?\}"  # slot
    r"|\[(?P<lit>[^\]]+)\]\((?P<tags>[^)]+)\)"                 # tagged literal
)


@dataclass
class RSpan:
    """Span relative to the text of the object that holds it."""

    start: int
    end: int
    kind: str                       # mention | trigger | neg | evd | timex | hedge
    meta: dict[str, Any] = field(default_factory=dict)

    def shifted(self, d: int) -> "RSpan":
        return RSpan(self.start + d, self.end + d, self.kind, dict(self.meta))


@dataclass
class Sentence:
    text: str = ""
    spans: list[RSpan] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    def add(self, text: str) -> None:
        self.text += text

    def add_span(self, text: str, kind: str, **meta: Any) -> RSpan:
        # spans never include outer whitespace
        lead = len(text) - len(text.lstrip())
        core = text.strip()
        self.text += text[:lead]
        s = RSpan(len(self.text), len(self.text) + len(core), kind, meta)
        self.text += core + text[lead + len(core):]
        if core:
            self.spans.append(s)
        return s

    def prepend(self, text: str, span_kind: str | None = None, **meta: Any) -> None:
        d = len(text)
        self.spans = [s.shifted(d) for s in self.spans]
        if span_kind:
            core = text.rstrip()
            self.spans.insert(0, RSpan(0, len(core), span_kind, meta))
        self.text = text + self.text

    def insert_before_final_punct(self, text: str, span_kind: str | None = None, **meta: Any) -> None:
        m = re.search(r"[.?!।]+\s*$", self.text)
        pos = m.start() if m else len(self.text)
        for s in self.spans:
            if s.start >= pos:
                s.start += len(text)
                s.end += len(text)
        if span_kind:
            lead = len(text) - len(text.lstrip())
            self.spans.append(RSpan(pos + lead, pos + len(text.rstrip()), span_kind, meta))
        self.text = self.text[:pos] + text + self.text[pos:]

    def capitalize_first(self) -> None:
        for i, ch in enumerate(self.text):
            if ch.isalpha():
                if "a" <= ch <= "z":
                    self.text = self.text[:i] + ch.upper() + self.text[i + 1 :]
                return

    def span_text(self, s: RSpan) -> str:
        return self.text[s.start : s.end]


SlotRenderer = Callable[[Sentence, str, str | None], None]
GenderOf = Callable[[str], str]


def parse_gender_options(opts: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in opts.split("|"):
        k, _, v = part.partition(":")
        out[k.strip()] = v
    return out


def render(template: str, slot_renderer: SlotRenderer, gender_of: GenderOf,
           literal_tag: Callable[[Sentence, str, list[str]], None]) -> Sentence:
    """Render one template into a Sentence.

    slot_renderer(sentence, SLOT, case) appends the slot's text + spans.
    literal_tag(sentence, text, tags) appends a tagged literal + spans.
    """
    sent = Sentence()
    pos = 0
    for m in TOKEN_RE.finditer(template):
        sent.add(template[pos : m.start()])
        if m.group("gslot"):
            opts = parse_gender_options(m.group("gopts"))
            g = gender_of(m.group("gslot"))
            if g not in opts:
                g = "m" if "m" in opts else next(iter(opts))
            # a gendered alternative may itself contain markup (e.g. a trigger)
            inner = render(opts[g], slot_renderer, gender_of, literal_tag)
            d = len(sent.text)
            sent.text += inner.text
            sent.spans += [s.shifted(d) for s in inner.spans]
        elif m.group("slot"):
            slot_renderer(sent, m.group("slot"), m.group("case"))
        else:
            tags = [t.strip() for t in m.group("tags").split(",")]
            literal_tag(sent, m.group("lit"), tags)
        pos = m.end()
    sent.add(template[pos:])
    return sent


def slots_in(template: str) -> set[str]:
    out = set()
    for m in TOKEN_RE.finditer(template):
        if m.group("slot"):
            out.add(m.group("slot"))
        elif m.group("gslot"):
            out.add(m.group("gslot"))
            for v in parse_gender_options(m.group("gopts")).values():
                out |= slots_in(v)
        else:
            for t in m.group("tags").split(","):
                t = t.strip()
                if t.startswith("@"):
                    out.add(t[1:].split(":")[0])
    return out


def tags_in(template: str) -> list[str]:
    out = []
    for m in TOKEN_RE.finditer(template):
        if m.group("tags"):
            out += [t.strip() for t in m.group("tags").split(",")]
        if m.group("gopts"):
            for v in parse_gender_options(m.group("gopts")).values():
                out += tags_in(v)
    return out
