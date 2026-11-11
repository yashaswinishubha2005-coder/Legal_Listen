"""Consultation state: everything LegalListen has learned in one session (serialisable)."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field

Value = Literal["satisfied", "contradicted", "unknown"]
Status = Literal["reported", "evidence_supported", "inferred", "conflicting", "unknown"]


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


class Chip(BaseModel):
    id: str
    label: str


class Message(BaseModel):
    role: Literal["user", "assistant"]
    text: str
    turn: int
    ts: str = Field(default_factory=now)
    lang: str | None = None
    variant: str | None = None
    source: Literal["text", "voice", "option", "system"] = "text"
    asr_confidence: float | None = None
    kind: str = "message"            # message | question | alert | clarify | consultation | explain
    chips: list[Chip] = Field(default_factory=list)
    target: str | None = None        # element / evidence key the question is about
    why: str | None = None


class Statement(BaseModel):
    turn: int
    quote: str                       # the user's own words (original language) or the option chosen
    value: Value
    source: Literal["narrative", "answer", "option", "llm"] = "answer"
    hedged: bool = False
    corrected: bool = False          # superseded by a later correction
    gloss_en: str | None = None      # English gloss when produced by the LLM (meaning check)


class ElementState(BaseModel):
    key: str
    value: Value | None = None       # None = not discussed yet
    status: Status = "unknown"
    statements: list[Statement] = Field(default_factory=list)
    asked: bool = False
    date: str | None = None
    date_text: str | None = None


class Person(BaseModel):
    id: str
    label: str
    relation: str
    noun: str
    is_org: bool = False
    name: str | None = None
    turns: list[int] = Field(default_factory=list)


class EvidenceState(BaseModel):
    key: str                         # "<issue>|<evidence_id>" or "free|<slug>"
    label: str
    availability: Literal["held", "missing", "unknown"] = "unknown"
    supports: list[str] = Field(default_factory=list)
    quote: str | None = None
    turn: int | None = None
    asked: bool = False


class Contradiction(BaseModel):
    id: str
    key: str                         # element key or "date"
    a: Statement
    b: Statement
    resolved: bool = False
    resolution: str | None = None    # first | second | unsure


class RiskState(BaseModel):
    flag: str
    quote: str
    turn: int
    alerted: bool = False


class Pending(BaseModel):
    kind: Literal["element", "evidence", "date", "personal_law", "safety", "contradiction", "confirm_transcript",
                  "issue_choice"]
    key: str | None = None
    chips: list[Chip] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=dict)
    reask: int = 0


class CaseState(BaseModel):
    session_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    created: str = Field(default_factory=now)
    updated: str = Field(default_factory=now)
    lang: str = "en"                 # preferred output language: en | kn | hi
    input_variant: str | None = None
    use_llm: bool = False
    conversation_date: str = Field(default_factory=lambda: dt.date.today().isoformat())
    turn: int = 0
    messages: list[Message] = Field(default_factory=list)
    issue_prior: dict[str, float] = Field(default_factory=dict)
    beliefs: dict[str, float] = Field(default_factory=dict)
    out_of_scope: float = 0.0
    non_legal: float = 0.0
    elements: dict[str, ElementState] = Field(default_factory=dict)
    people: list[Person] = Field(default_factory=list)
    evidence: dict[str, EvidenceState] = Field(default_factory=dict)
    contradictions: list[Contradiction] = Field(default_factory=list)
    risks: dict[str, RiskState] = Field(default_factory=dict)
    money: list[str] = Field(default_factory=list)
    other_facts: list[str] = Field(default_factory=list)   # things the client said that fit no question yet
    incident_date: str | None = None
    incident_date_text: str | None = None
    law_regime: Literal["old", "new"] | None = None
    personal_law: str | None = None  # hindu | muslim | christian | interfaith_sma | skipped
    asked: list[str] = Field(default_factory=list)
    announced: list[str] = Field(default_factory=list)
    pending: Pending | None = None
    safety_checked: bool = False
    safety_unsafe: bool = False
    questions_asked: int = 0
    consultation_ready: bool = False
    consultation_version: int = 0
    last_explained: str | None = None
    card_signature: str | None = None    # what the last consultation card in the chat was based on
    last_issue_asked: str | None = None
    llm_calls: int = 0
    notes: list[str] = Field(default_factory=list)

    def element(self, key: str) -> ElementState:
        if key not in self.elements:
            self.elements[key] = ElementState(key=key)
        return self.elements[key]

    def say(self, text: str, **kw) -> Message:
        m = Message(role="assistant", text=text, turn=self.turn, lang=self.lang, **kw)
        self.messages.append(m)
        return m
