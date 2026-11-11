"""Issue library: one schema per legal issue (Phase 1).

Templates use a small markup, parsed by ``lexvaani.render.markup``:

    {SLOT}            entity mention, nominative      e.g. {RESP}
    {SLOT.case}       entity mention, case form       {RESP.dat} {RESP.erg} {RESP.gen_f}
    {DATE} {AMOUNT} {ITEM} {PLACE} {ACCOUNT} {IDNUM}  value slots (spans recorded)
    [text](TRIG)      event trigger of the fact's event
    [text](NEG)       negation cue
    [text](EVD)       evidence mention
    {g:SLOT|m:..|f:..|n:..}  form agreeing with SLOT's gender (n = organisation/plural)
"""

from __future__ import annotations

from enum import Enum

from pydantic import Field, model_validator

from .common import Domain, IssueId, Language, LangVariant, StrictModel, Verification
from .ontology import EvidenceAvailability, EvidenceType, ParticipantRole

ML6 = dict[LangVariant, str]   # one template per language/script variant
ML3 = dict[Language, str]      # en / kn / hi


def _need(d: dict, keys, where: str) -> None:
    missing = [k.value for k in keys if k not in d or not str(d[k]).strip()]
    if missing:
        raise ValueError(f"{where}: missing {missing}")


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RiskFlag(str, Enum):
    IMMINENT_VIOLENCE = "imminent_violence"
    ONGOING_ABUSE = "ongoing_abuse"
    THREAT_TO_LIFE = "threat_to_life"
    SELF_HARM = "self_harm"
    MINOR_INVOLVED = "minor_involved"
    IMAGE_CIRCULATION = "image_circulation"
    GOLDEN_HOUR_FRAUD = "golden_hour_fraud"           # money lost within ~24h
    IMMINENT_PROPERTY_TRANSFER = "imminent_property_transfer"
    EVICTION_IMMINENT = "eviction_imminent"
    LIMITATION_NEAR_EXPIRY = "limitation_near_expiry"
    EVIDENCE_AT_RISK = "evidence_at_risk"
    CHILD_REMOVAL_IMMINENT = "child_removal_imminent"


URGENT_FLAGS = {
    RiskFlag.IMMINENT_VIOLENCE, RiskFlag.ONGOING_ABUSE, RiskFlag.THREAT_TO_LIFE,
    RiskFlag.SELF_HARM, RiskFlag.IMAGE_CIRCULATION, RiskFlag.GOLDEN_HOUR_FRAUD,
    RiskFlag.IMMINENT_PROPERTY_TRANSFER, RiskFlag.EVICTION_IMMINENT, RiskFlag.CHILD_REMOVAL_IMMINENT,
    RiskFlag.LIMITATION_NEAR_EXPIRY,
}


class Triage(str, Enum):
    SELF_HELP = "self_help"
    LAWYER = "lawyer"
    URGENT = "urgent"


class CastSlot(StrictModel):
    """A participant the issue's templates refer to."""

    slot: str = Field(pattern=r"^[A-Z][A-Z0-9_]*$")
    role: str                           # PersonRole value or "organization"
    nouns: list[str] = Field(default_factory=list, description="keys into resources/lexicon role_nouns")
    genders: list[str] = Field(default_factory=lambda: ["male", "female"])
    kind: str = Field("person", pattern=r"^(person|organization|account|asset)$")
    named: bool = True                  # may carry a synthetic name
    pronominal: bool = True             # may be referred to by a pronoun
    kin_relation: str | None = None     # KinRelation of this person TO the speaker
    affiliated_with: str | None = None  # slot of an organization (AFFILIATED_WITH edge)
    surface: dict[LangVariant, str] = Field(
        default_factory=dict, description="literal surface per variant for org/account/asset slots")


class ElementDef(StrictModel):
    element_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    critical: bool
    description: str
    question: ML3
    proposition: dict[str, str]          # {"satisfied": "...", "contradicted": "..."} English
    satisfied: ML6
    contradicted: ML6
    implicit: ML6 | None = None          # indirect statement -> claim status 'inferred'
    caused_by: str | None = None         # element whose event CAUSES this one
    date_slot_required: bool = False     # regime-determining incident: date must be resolvable
    may_be_unknown: bool = False         # plausible for the user not to know (used by 'incomplete')
    event_type: str | None = None
    hypothetical_when_contradicted: bool = False   # "threatened to sell" pattern
    args: dict[str, str] = Field(default_factory=dict, description="slot -> ParticipantRole value or 'place'")
    order: int = 0                       # chronological order in the default timeline

    @model_validator(mode="after")
    def _complete(self) -> "ElementDef":
        allowed = {r.value for r in ParticipantRole} | {"place"}
        bad = set(self.args.values()) - allowed
        if bad:
            raise ValueError(f"{self.element_id}.args: unknown roles {bad}")
        if self.implicit is not None:
            _need(self.implicit, list(LangVariant), f"{self.element_id}.implicit")
        _need(self.question, list(Language), f"{self.element_id}.question")
        _need(self.satisfied, list(LangVariant), f"{self.element_id}.satisfied")
        _need(self.contradicted, list(LangVariant), f"{self.element_id}.contradicted")
        if set(self.proposition) != {"satisfied", "contradicted"}:
            raise ValueError(f"{self.element_id}.proposition needs satisfied+contradicted")
        return self


class EvidenceDef(StrictModel):
    evidence_id: str = Field(pattern=r"^[a-z][a-z0-9_]*$")
    evidence_type: EvidenceType
    supports: list[str] = Field(min_length=1)
    held: ML6
    missing: ML6
    default_availability: EvidenceAvailability = EvidenceAvailability.HELD

    @model_validator(mode="after")
    def _complete(self) -> "EvidenceDef":
        _need(self.held, list(LangVariant), f"{self.evidence_id}.held")
        _need(self.missing, list(LangVariant), f"{self.evidence_id}.missing")
        return self


class RiskFactDef(StrictModel):
    flag: RiskFlag
    template: ML6

    @model_validator(mode="after")
    def _complete(self) -> "RiskFactDef":
        _need(self.template, list(LangVariant), f"risk.{self.flag.value}")
        return self


class RoutingVariable(StrictModel):
    name: str
    values: list[str]
    description: str


class CandidateProvision(StrictModel):
    provision_id: str
    when: dict[str, list[str]] = Field(
        default_factory=dict, description="routing condition, e.g. {'law_regime': ['new']}")
    title_hint: str | None = None
    verification: Verification = Verification.TO_VERIFY
    note: str | None = None


class IssueSchema(StrictModel):
    issue_id: IssueId
    domain: Domain
    title: ML3
    plain_summary: ML3
    risk_level: RiskLevel
    default_triage: Triage
    cast: list[CastSlot]
    setup: ML6
    elements: list[ElementDef] = Field(min_length=2)
    evidence: list[EvidenceDef] = Field(default_factory=list)
    risk_facts: list[RiskFactDef] = Field(min_length=1)
    routing_variables: list[RoutingVariable] = Field(default_factory=list)
    candidate_provisions: list[CandidateProvision] = Field(min_length=1)
    limitation_notes: str
    confusable_with: list[IssueId] = Field(default_factory=list)
    co_occurs_with: list[IssueId] = Field(default_factory=list)
    speaker_genders: list[str] = Field(default_factory=lambda: ["female", "male"])
    value_slots: dict[str, list[str]] = Field(
        default_factory=dict, description="slot -> lexicon keys / ranges, e.g. ITEM: [gold_chain]")

    @model_validator(mode="after")
    def _checks(self) -> "IssueSchema":
        if self.issue_id.domain != self.domain:
            raise ValueError(f"{self.issue_id.value}: domain mismatch")
        _need(self.setup, list(LangVariant), f"{self.issue_id.value}.setup")
        ids = [e.element_id for e in self.elements]
        if len(set(ids)) != len(ids):
            raise ValueError(f"{self.issue_id.value}: duplicate element ids")
        if not any(e.critical for e in self.elements):
            raise ValueError(f"{self.issue_id.value}: needs at least one critical element")
        if not any(e.critical and e.may_be_unknown for e in self.elements):
            raise ValueError(f"{self.issue_id.value}: needs a critical element with may_be_unknown")
        for ev in self.evidence:
            unknown = set(ev.supports) - set(ids)
            if unknown:
                raise ValueError(f"{self.issue_id.value}.{ev.evidence_id}: supports unknown {unknown}")
        return self
