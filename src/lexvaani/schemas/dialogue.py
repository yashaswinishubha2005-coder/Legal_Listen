"""Simulated pre-consultation dialogues (T5 across turns, T9, T12)."""

from __future__ import annotations

from enum import Enum

from pydantic import Field, model_validator

from .common import LangVariant, StrictModel
from .metadata import Provenance
from .ontology import ElementValue
from .sample import EntityMention, FactAnnotation, CorefCluster


class Speaker(str, Enum):
    USER = "user"
    SYSTEM = "system"


class ClarificationLabel(str, Enum):
    """T12: what the user turn does."""

    NEW_FACT = "new_fact"               # adds information (incl. "I don't know")
    CORRECTION = "correction"           # revises something the user said earlier
    REEXPLAIN_REQUEST = "reexplain_request"  # asks the system to repeat / simplify


class Turn(StrictModel):
    index: int = Field(ge=0)
    speaker: Speaker
    text: str = Field(min_length=1)
    unit_id: str                          # "<dialogue_id>#t<index>"
    question_id: str | None = None        # system turns
    clarification: ClarificationLabel | None = None   # user turns after the opening
    entities: list[EntityMention] = Field(default_factory=list)
    facts: list[FactAnnotation] = Field(default_factory=list)


class DialogueState(StrictModel):
    known: dict[str, ElementValue] = Field(default_factory=dict)   # "issue|element" -> value
    asked: list[str] = Field(default_factory=list)                # question ids
    belief: dict[str, float] = Field(default_factory=dict)        # issue -> P(present)
    completeness: float = Field(ge=0.0, le=1.0)                   # known critical gold elements / all


class CandidateQuestion(StrictModel):
    question_id: str           # "<issue>|<element>"
    issue_id: str
    element_id: str
    critical: bool
    text: str
    oracle_score: float


class DecisionPoint(StrictModel):
    system_turn: int
    state_before: DialogueState
    candidates: list[CandidateQuestion] = Field(min_length=1)
    gold_best: str
    acceptable_set: list[str] = Field(min_length=1)
    answer_turn: int
    state_after: DialogueState

    @model_validator(mode="after")
    def _gold_in_candidates(self) -> "DecisionPoint":
        ids = {c.question_id for c in self.candidates}
        if self.gold_best not in ids or not set(self.acceptable_set) <= ids:
            raise ValueError("gold_best / acceptable_set must be candidate ids")
        if self.gold_best not in self.acceptable_set:
            raise ValueError("gold_best must be in acceptable_set")
        return self


class Dialogue(StrictModel):
    dialogue_id: str
    spec_id: str
    family_id: str
    lang_variant: LangVariant
    turns: list[Turn] = Field(min_length=1)
    decision_points: list[DecisionPoint] = Field(default_factory=list)
    coref: list[CorefCluster] = Field(default_factory=list)   # clusters across turns
    provenance: Provenance

    @model_validator(mode="after")
    def _spans(self) -> "Dialogue":
        for t in self.turns:
            if t.unit_id != f"{self.dialogue_id}#t{t.index}":
                raise ValueError(f"{self.dialogue_id}: bad unit_id {t.unit_id}")
            for m in t.entities:
                m.span.verify_against(t.text)
            for f in t.facts:
                f.span.verify_against(t.text)
        return self
