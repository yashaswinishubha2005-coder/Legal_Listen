"""Narrative sample with all span-level and case-level annotations (Phase 3)."""

from __future__ import annotations

from enum import Enum

from pydantic import Field, model_validator

from .common import Domain, EpistemicStatus, IssueId, LangVariant, Span, StrictModel, Timex
from .issue_library import RiskFlag, Triage
from .metadata import Provenance, SpeakerMetadata
from .ontology import CaseGraph, ElementValue
from .spec import Difficulty, Variation


class EntityType(str, Enum):
    PERSON = "PERSON"
    ORGANIZATION = "ORGANIZATION"
    LOCATION = "LOCATION"
    ASSET = "ASSET"
    MONEY = "MONEY"
    TIME = "TIME"
    ACCOUNT = "ACCOUNT"
    IDENTIFIER = "IDENTIFIER"     # txn id, phone number, survey number
    EVIDENCE = "EVIDENCE"


class MentionKind(str, Enum):
    NAME = "name"
    NOMINAL = "nominal"     # "my uncle", "the owner", "maava"
    PRONOUN = "pronoun"
    VALUE = "value"         # money, time, id numbers


class EntityMention(StrictModel):
    mention_id: str
    type: EntityType
    span: Span
    kind: MentionKind
    entity_id: str | None = None   # graph node id this mention refers to


class EventArgument(StrictModel):
    role: str                 # agent | patient | instrument | beneficiary | recipient | witness | time | place
    mention_id: str | None = None
    entity_id: str | None = None


class EventAnnotation(StrictModel):
    event_id: str
    event_type: str
    trigger: Span
    arguments: list[EventArgument] = Field(default_factory=list)
    time_id: str | None = None
    negated: bool = False
    hypothetical: bool = False


class TLinkRel(str, Enum):
    BEFORE = "BEFORE"
    AFTER = "AFTER"
    OVERLAP = "OVERLAP"


class TLink(StrictModel):
    source: str
    target: str
    relation: TLinkRel


class CorefCluster(StrictModel):
    entity_id: str
    mention_ids: list[str] = Field(min_length=1)


class FactAnnotation(StrictModel):
    claim_id: str
    span: Span
    status: EpistemicStatus
    issue_id: IssueId | None = None
    element_id: str | None = None
    polarity: ElementValue
    hedged: bool = False
    hedge_cues: list[Span] = Field(default_factory=list)
    negation_cues: list[Span] = Field(default_factory=list)


class ElementLabel(StrictModel):
    issue_id: IssueId
    element_id: str
    critical: bool
    value: ElementValue


class Annotations(StrictModel):
    issues: list[IssueId] = Field(min_length=1)                    # T1
    domains: list[Domain] = Field(default_factory=list)           # T1
    entities: list[EntityMention] = Field(default_factory=list)   # T2
    events: list[EventAnnotation] = Field(default_factory=list)   # T3
    timexes: list[Timex] = Field(default_factory=list)            # T4
    tlinks: list[TLink] = Field(default_factory=list)             # T4
    coref: list[CorefCluster] = Field(default_factory=list)       # T5
    facts: list[FactAnnotation] = Field(default_factory=list)     # T6
    elements: list[ElementLabel] = Field(default_factory=list)    # T7
    case_graph: CaseGraph                                         # T8
    provisions: list[str] = Field(default_factory=list)           # T10
    triage: Triage                                                # T13
    risk_flags: list[RiskFlag] = Field(default_factory=list)      # T13


class NoiseInfo(StrictModel):
    clean_sample_id: str
    ops: list[dict] = Field(default_factory=list)
    word_error_rate: float
    dropped_mentions: list[str] = Field(default_factory=list)


class SoftLabel(StrictModel):
    """Annotator label distribution for an ambiguous item (filled by Phase 4 humans)."""

    task: str
    item_ref: str
    distribution: dict[str, float]
    n_annotators: int


class NarrativeSample(StrictModel):
    sample_id: str
    spec_id: str
    family_id: str
    lang_variant: LangVariant
    variation: Variation
    difficulty: Difficulty
    conversation_date: str
    text: str = Field(min_length=1)
    annotations: Annotations
    noise: NoiseInfo | None = None
    soft_labels: list[SoftLabel] = Field(default_factory=list)
    qc: dict = Field(default_factory=dict)
    metadata: SpeakerMetadata
    provenance: Provenance

    @model_validator(mode="after")
    def _spans(self) -> "NarrativeSample":
        a = self.annotations
        spans: list[Span] = [m.span for m in a.entities]
        spans += [e.trigger for e in a.events]
        spans += [t.span for t in a.timexes if t.span]
        for f in a.facts:
            spans += [f.span, *f.hedge_cues, *f.negation_cues]
        for s in spans:
            if s.unit_id != self.sample_id:
                raise ValueError(f"{self.sample_id}: span unit_id {s.unit_id}")
            s.verify_against(self.text)
        mids = {m.mention_id for m in a.entities}
        for c in a.coref:
            if set(c.mention_ids) - mids:
                raise ValueError(f"{self.sample_id}: coref references unknown mention")
        return self
