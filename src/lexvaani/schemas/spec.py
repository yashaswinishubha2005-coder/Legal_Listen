"""Scenario spec: the complete hidden truth of one synthetic case (Phase 2)."""

from __future__ import annotations

from enum import Enum

from pydantic import Field, model_validator

from .common import IssueId, StrictModel
from .issue_library import RiskFlag, Triage
from .metadata import Provenance, SpeakerMetadata
from .ontology import CaseGraph, ElementValue, EvidenceAvailability, ParticipantRole


class Variation(str, Enum):
    COMPLETE = "complete"
    INCOMPLETE = "incomplete"          # >=1 critical element unknown
    CONTRADICTORY = "contradictory"    # user contradicts themself on an element
    MULTI_ISSUE = "multi_issue"        # two issues, often cross-domain
    HIGH_RISK = "high_risk"            # >=1 urgent risk flag
    OUT_OF_SCOPE = "out_of_scope"      # legal, not in library -> lawyer
    NON_LEGAL = "non_legal"


class Difficulty(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class Reveal(str, Enum):
    NARRATIVE = "narrative"   # stated in the opening narrative
    DIALOGUE = "dialogue"     # only revealed if asked
    NEVER = "never"           # user does not know


class LawRegime(str, Enum):
    OLD = "old"   # incident before 2024-07-01: IPC / CrPC / IEA
    NEW = "new"   # on/after 2024-07-01: BNS / BNSS / BSA


class SpecPerson(StrictModel):
    slot: str
    node_id: str
    role: str
    gender: str
    name: str | None = None
    noun: str                          # lexicon role-noun key
    kin_relation: str | None = None    # relation TO the speaker
    is_minor: bool = False
    is_org: bool = False
    refs: list[str] = Field(default_factory=list, description="'<issue_id>:<SLOT>' this entity fills")


class SpecValue(StrictModel):
    slot: str
    node_id: str | None = None   # asset/account node if any
    kind: str                    # amount | item | place | account | idnum
    key: str                     # lexicon key or canonical value
    value: str                   # normalized gold value (e.g. "45000" INR)
    refs: list[str] = Field(default_factory=list)


class SpecEvent(StrictModel):
    event_id: str
    issue_id: IssueId
    element_id: str
    event_type: str
    date: str                     # ISO date (hidden truth, always absolute)
    hypothetical: bool = False
    negated: bool = False
    args: dict[str, str] = Field(default_factory=dict)   # slot -> participant role or "place"


class SpecFact(StrictModel):
    fact_id: str
    issue_id: IssueId
    element_id: str
    polarity: ElementValue        # satisfied | contradicted (what the user says)
    reveal: Reveal
    hedged: bool = False
    self_contradicted: bool = False   # also asserted with the opposite polarity
    event_id: str | None = None


class ElementTruth(StrictModel):
    issue_id: IssueId
    element_id: str
    critical: bool
    world_value: ElementValue      # what actually happened (hidden)
    gold_value: ElementValue       # T7 label: what the user's account establishes


class SpecEvidence(StrictModel):
    evidence_id: str
    issue_id: IssueId
    def_id: str
    availability: EvidenceAvailability
    supports: list[str]
    reveal: Reveal


class MinimalPair(StrictModel):
    base_spec_id: str
    flip_type: str               # element_flip | evidence_flip | date_regime_flip | risk_flip
    changed: str                 # human-readable description of the ONE change
    flipped_tasks: list[str]     # e.g. ["T7", "T13"]


class ScenarioSpec(StrictModel):
    spec_id: str = Field(pattern=r"^spc_\d{4}[a-z]?$")
    family_id: str
    variation: Variation
    difficulty: Difficulty
    issues: list[IssueId] = Field(min_length=1)
    conversation_date: str
    incident_date: str | None = None
    law_regime: LawRegime | None = None
    routing: dict[str, str] = Field(default_factory=dict)
    cast: list[SpecPerson] = Field(default_factory=list)
    values: list[SpecValue] = Field(default_factory=list)
    events: list[SpecEvent] = Field(default_factory=list)
    facts: list[SpecFact] = Field(default_factory=list)
    elements: list[ElementTruth] = Field(default_factory=list)
    evidence: list[SpecEvidence] = Field(default_factory=list)
    risk_flags: list[RiskFlag] = Field(default_factory=list)
    triage: Triage
    gold_provisions: list[str] = Field(default_factory=list)
    provision_notes: list[str] = Field(default_factory=list)
    other_template: str | None = None    # out-of-scope / non-legal template id
    metadata: SpeakerMetadata
    minimal_pair: MinimalPair | None = None
    case_graph: CaseGraph
    provenance: Provenance

    @model_validator(mode="after")
    def _checks(self) -> "ScenarioSpec":
        routing_only = {IssueId.OUT_OF_SCOPE, IssueId.NON_LEGAL}
        if self.variation in (Variation.OUT_OF_SCOPE, Variation.NON_LEGAL):
            if set(self.issues) - routing_only:
                raise ValueError(f"{self.spec_id}: {self.variation.value} spec must not carry library issues")
        elif set(self.issues) & routing_only:
            raise ValueError(f"{self.spec_id}: routing label on an in-library spec")
        if self.variation == Variation.MULTI_ISSUE and len(self.issues) < 2:
            raise ValueError(f"{self.spec_id}: multi_issue needs >=2 issues")
        if self.variation == Variation.INCOMPLETE and not any(
            e.critical and e.gold_value == ElementValue.UNKNOWN for e in self.elements
        ):
            raise ValueError(f"{self.spec_id}: incomplete spec needs an unknown critical element")
        if self.variation == Variation.CONTRADICTORY and not any(f.self_contradicted for f in self.facts):
            raise ValueError(f"{self.spec_id}: contradictory spec needs a self-contradicted fact")
        if self.variation == Variation.HIGH_RISK and self.triage != Triage.URGENT:
            raise ValueError(f"{self.spec_id}: high_risk spec must triage as urgent")
        if self.conversation_date < (self.incident_date or ""):
            raise ValueError(f"{self.spec_id}: incident after conversation date")
        for ev in self.events:
            if ev.date > self.conversation_date:
                raise ValueError(f"{self.spec_id}: event {ev.event_id} after conversation date")
        return self
