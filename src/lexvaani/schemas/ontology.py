"""Legal Case Graph ontology. Human-readable spec: docs/ontology.md.

A CaseGraph is valid only if:
  1. node ids are unique and carry the prefix of their type,
  2. every edge connects existing nodes with an allowed (source, target) type pair,
  3. BEFORE edges form a DAG (no temporal cycles),
  4. epistemic status agrees with structure:
       evidence_supported claim  -> has an incoming SUPPORTS from Evidence
       conflicting claim         -> takes part in at least one CONTRADICTS edge
  5. each Element's ``value`` agrees with its SATISFIES / REFUTES / LACKS edges.
"""

from __future__ import annotations

from collections import defaultdict
from enum import Enum
from typing import Annotated, Any, Literal, Union

from pydantic import Field, model_validator

from .common import (
    Confidence,
    EpistemicStatus,
    IssueId,
    Span,
    StrictModel,
    Timex,
    Verification,
)

# ------------------------------------------------------------------- types --


class NodeType(str, Enum):
    PERSON = "Person"
    ORGANIZATION = "Organization"
    EVENT = "Event"
    CLAIM = "Claim"
    EVIDENCE = "Evidence"
    ASSET = "Asset"          # property / asset: land, house, gold, phone, vehicle
    ACCOUNT = "Account"      # bank / UPI / social-media / email account
    ISSUE = "Issue"
    ELEMENT = "Element"
    PROVISION = "Provision"
    QUESTION = "Question"


ID_PREFIX: dict[NodeType, str] = {
    NodeType.PERSON: "per",
    NodeType.ORGANIZATION: "org",
    NodeType.EVENT: "evt",
    NodeType.CLAIM: "clm",
    NodeType.EVIDENCE: "evd",
    NodeType.ASSET: "ast",
    NodeType.ACCOUNT: "acc",
    NodeType.ISSUE: "iss",
    NodeType.ELEMENT: "elm",
    NodeType.PROVISION: "prv",
    NodeType.QUESTION: "qst",
}


class EdgeType(str, Enum):
    KIN_OF = "KIN_OF"
    AFFILIATED_WITH = "AFFILIATED_WITH"
    PARTICIPANT_IN = "PARTICIPANT_IN"
    OWNS = "OWNS"
    HOLDS = "HOLDS"
    BEFORE = "BEFORE"
    OVERLAP = "OVERLAP"
    CAUSES = "CAUSES"
    ASSERTS = "ASSERTS"
    ABOUT = "ABOUT"
    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"
    CORRECTS = "CORRECTS"
    INDICATES = "INDICATES"
    HAS_ELEMENT = "HAS_ELEMENT"
    SATISFIES = "SATISFIES"
    REFUTES = "REFUTES"
    LACKS = "LACKS"
    APPLIES_TO = "APPLIES_TO"
    TARGETS = "TARGETS"


N = NodeType
_ENTITIES = {N.PERSON, N.ORGANIZATION}
_THINGS = {N.PERSON, N.ORGANIZATION, N.EVENT, N.ASSET, N.ACCOUNT}

# edge type -> (allowed source types, allowed target types)
EDGE_CONSTRAINTS: dict[EdgeType, tuple[set[NodeType], set[NodeType]]] = {
    EdgeType.KIN_OF: ({N.PERSON}, {N.PERSON}),
    EdgeType.AFFILIATED_WITH: ({N.PERSON}, {N.ORGANIZATION}),
    EdgeType.PARTICIPANT_IN: (_ENTITIES | {N.ASSET, N.ACCOUNT}, {N.EVENT}),
    EdgeType.OWNS: (_ENTITIES, {N.ASSET, N.ACCOUNT}),
    EdgeType.HOLDS: (_ENTITIES, {N.EVIDENCE}),
    EdgeType.BEFORE: ({N.EVENT}, {N.EVENT}),
    EdgeType.OVERLAP: ({N.EVENT}, {N.EVENT}),
    EdgeType.CAUSES: ({N.EVENT}, {N.EVENT}),
    EdgeType.ASSERTS: ({N.PERSON}, {N.CLAIM}),
    EdgeType.ABOUT: ({N.CLAIM}, _THINGS),
    EdgeType.SUPPORTS: ({N.EVIDENCE}, {N.CLAIM, N.EVENT}),
    EdgeType.CONTRADICTS: ({N.CLAIM, N.EVIDENCE}, {N.CLAIM, N.EVIDENCE}),
    EdgeType.CORRECTS: ({N.CLAIM}, {N.CLAIM}),
    EdgeType.INDICATES: ({N.EVENT, N.CLAIM}, {N.ISSUE}),
    EdgeType.HAS_ELEMENT: ({N.ISSUE}, {N.ELEMENT}),
    EdgeType.SATISFIES: ({N.CLAIM, N.EVIDENCE, N.EVENT}, {N.ELEMENT}),
    EdgeType.REFUTES: ({N.CLAIM, N.EVIDENCE, N.EVENT}, {N.ELEMENT}),
    EdgeType.LACKS: ({N.ISSUE}, {N.ELEMENT}),
    EdgeType.APPLIES_TO: ({N.PROVISION}, {N.ISSUE}),
    EdgeType.TARGETS: ({N.QUESTION}, {N.ELEMENT}),
}

# Edges whose direction carries no meaning; stored with source_id < target_id.
SYMMETRIC_EDGES = {EdgeType.OVERLAP, EdgeType.CONTRADICTS}


# -------------------------------------------------------- attribute enums --


class PersonRole(str, Enum):
    SPEAKER = "speaker"            # the user narrating
    COMPLAINANT = "complainant"    # aggrieved party (may be the speaker)
    RESPONDENT = "respondent"      # alleged wrongdoer
    WITNESS = "witness"
    OTHER = "other"


class KinRelation(str, Enum):
    """Normalized kinship relation of ``source`` *to* ``target``:
    (A KIN_OF B, relation=father) means A is B's father.
    Surface terms (maava, chikkappa, devar, jija ...) are kept in
    ``Edge.attributes['surface_term']``; the mapping is in the guidelines."""

    FATHER = "father"
    MOTHER = "mother"
    SON = "son"
    DAUGHTER = "daughter"
    BROTHER = "brother"
    SISTER = "sister"
    HUSBAND = "husband"
    WIFE = "wife"
    PATERNAL_UNCLE = "paternal_uncle"
    MATERNAL_UNCLE = "maternal_uncle"
    PATERNAL_AUNT = "paternal_aunt"
    MATERNAL_AUNT = "maternal_aunt"
    GRANDFATHER = "grandfather"
    GRANDMOTHER = "grandmother"
    GRANDSON = "grandson"
    GRANDDAUGHTER = "granddaughter"
    COUSIN = "cousin"
    NEPHEW = "nephew"
    NIECE = "niece"
    FATHER_IN_LAW = "father_in_law"
    MOTHER_IN_LAW = "mother_in_law"
    BROTHER_IN_LAW = "brother_in_law"
    SISTER_IN_LAW = "sister_in_law"
    SON_IN_LAW = "son_in_law"
    DAUGHTER_IN_LAW = "daughter_in_law"
    OTHER_RELATIVE = "other_relative"
    UNRESOLVED = "unresolved"  # term is ambiguous in context (e.g. "maava")


class ParticipantRole(str, Enum):
    AGENT = "agent"            # did the act
    PATIENT = "patient"        # act was done to them / it
    INSTRUMENT = "instrument"  # used to do the act (phone, UPI account, stick)
    BENEFICIARY = "beneficiary"
    WITNESS = "witness"
    RECIPIENT = "recipient"    # e.g. received money / notice


class OrgType(str, Enum):
    BANK = "bank"
    POLICE = "police"
    COURT = "court"
    GOVT_OFFICE = "govt_office"   # tahsildar, sub-registrar, panchayat ...
    COMPANY = "company"
    PLATFORM = "platform"         # e-commerce, social media, payment app
    LENDER = "lender"             # NBFC / loan app / money lender
    OTHER = "other"


class EvidenceType(str, Enum):
    DOCUMENT = "document"           # sale deed, will, RTC, khata, invoice, FIR copy
    DIGITAL_RECORD = "digital_record"  # UPI txn id, bank SMS, statement
    SCREENSHOT = "screenshot"
    CHAT_MESSAGE = "chat_message"
    CALL_RECORDING = "call_recording"
    PHOTO_VIDEO = "photo_video"
    MEDICAL_RECORD = "medical_record"
    WITNESS = "witness"
    PHYSICAL_OBJECT = "physical_object"
    OFFICIAL_RECEIPT = "official_receipt"  # complaint acknowledgement, cybercrime ack no.
    OTHER = "other"


class EvidenceAvailability(str, Enum):
    HELD = "held"          # user has it now
    MISSING = "missing"    # does not exist / lost / never obtained
    OBTAINABLE = "obtainable"  # exists, user can get it (bank statement, RTC copy)
    UNKNOWN = "unknown"


class AssetType(str, Enum):
    AGRICULTURAL_LAND = "agricultural_land"
    HOUSE_SITE = "house_site"
    BUILDING = "building"
    MOVABLE_VALUABLE = "movable_valuable"   # gold, cash
    DEVICE = "device"
    VEHICLE = "vehicle"
    PRODUCT = "product"                     # consumer good
    OTHER = "other"


class AccountType(str, Enum):
    BANK = "bank"
    UPI = "upi"
    CARD = "card"
    WALLET = "wallet"
    SOCIAL_MEDIA = "social_media"
    EMAIL = "email"
    PHONE_NUMBER = "phone_number"
    LOAN = "loan"
    OTHER = "other"


class ElementValue(str, Enum):
    SATISFIED = "satisfied"
    CONTRADICTED = "contradicted"
    UNKNOWN = "unknown"


# ------------------------------------------------------------------- nodes --


class _NodeBase(StrictModel):
    id: str
    label: str = Field(min_length=1, description="short human-readable name")
    status: EpistemicStatus
    confidence: Confidence = 1.0
    source_spans: list[Span] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _prefix(self) -> "_NodeBase":
        prefix = ID_PREFIX[NodeType(self.type)]  # type: ignore[attr-defined]
        if not self.id.startswith(prefix + "_"):
            raise ValueError(f"{NodeType(self.type).value} id {self.id!r} must start with '{prefix}_'")
        return self


class PersonNode(_NodeBase):
    type: Literal[NodeType.PERSON] = NodeType.PERSON
    role: PersonRole
    gender: Literal["female", "male", "other", "unknown"] = "unknown"
    is_minor: bool | None = None
    synthetic_name: str | None = None  # synthetic only; never a real person


class OrganizationNode(_NodeBase):
    type: Literal[NodeType.ORGANIZATION] = NodeType.ORGANIZATION
    org_type: OrgType


class EventNode(_NodeBase):
    type: Literal[NodeType.EVENT] = NodeType.EVENT
    event_type: str = Field(description="from the event inventory in guidelines T3")
    trigger: Span | None = None
    time: Timex | None = None
    place: str | None = None
    negated: bool = False      # "he did NOT sign" -> event exists as negated
    hypothetical: bool = False # threatened / planned, not yet happened


class ClaimNode(_NodeBase):
    type: Literal[NodeType.CLAIM] = NodeType.CLAIM
    proposition: str = Field(min_length=1, description="normalized English statement")
    polarity: Literal["positive", "negative"] = "positive"
    hedged: bool = False
    hedge_cues: list[Span] = Field(default_factory=list)
    negation_cues: list[Span] = Field(default_factory=list)
    turn_index: int | None = None  # dialogue turn where first asserted


class EvidenceNode(_NodeBase):
    type: Literal[NodeType.EVIDENCE] = NodeType.EVIDENCE
    evidence_type: EvidenceType
    availability: EvidenceAvailability


class AssetNode(_NodeBase):
    type: Literal[NodeType.ASSET] = NodeType.ASSET
    asset_type: AssetType
    ancestral: bool | None = None  # matters for partition / succession


class AccountNode(_NodeBase):
    type: Literal[NodeType.ACCOUNT] = NodeType.ACCOUNT
    account_type: AccountType
    institution: str | None = None  # synthetic / generic ("a nationalised bank")


class IssueNode(_NodeBase):
    type: Literal[NodeType.ISSUE] = NodeType.ISSUE
    issue_id: IssueId


class ElementNode(_NodeBase):
    type: Literal[NodeType.ELEMENT] = NodeType.ELEMENT
    issue_id: IssueId
    element_id: str = Field(description="key from the issue library, e.g. 'dishonest_intention'")
    critical: bool
    value: ElementValue


class ProvisionNode(_NodeBase):
    type: Literal[NodeType.PROVISION] = NodeType.PROVISION
    provision_id: str = Field(
        pattern=r"^[A-Z][A-Za-z0-9_]*:[0-9A-Za-z().\-]+$",
        description="'<ACT_CODE>:<section>', e.g. 'BNS:318'; must exist in the corpus",
    )
    verification: Verification = Verification.TO_VERIFY


class QuestionNode(_NodeBase):
    type: Literal[NodeType.QUESTION] = NodeType.QUESTION
    text: str = Field(min_length=1)
    template_id: str | None = None


Node = Annotated[
    Union[
        PersonNode, OrganizationNode, EventNode, ClaimNode, EvidenceNode,
        AssetNode, AccountNode, IssueNode, ElementNode, ProvisionNode, QuestionNode,
    ],
    Field(discriminator="type"),
]


# ------------------------------------------------------------------- edges --


class Edge(StrictModel):
    id: str = Field(pattern=r"^e_[0-9A-Za-z_]+$")
    type: EdgeType
    source_id: str
    target_id: str
    status: EpistemicStatus
    confidence: Confidence = 1.0
    source_spans: list[Span] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _attrs(self) -> "Edge":
        if self.source_id == self.target_id:
            raise ValueError(f"edge {self.id}: self-loops are not allowed")
        if self.type in SYMMETRIC_EDGES and self.source_id > self.target_id:
            raise ValueError(f"edge {self.id}: symmetric {self.type.value} must have source_id < target_id")
        if self.type == EdgeType.KIN_OF:
            rel = self.attributes.get("relation")
            if rel is None:
                raise ValueError(f"edge {self.id}: KIN_OF needs attributes.relation")
            KinRelation(rel)
        if self.type == EdgeType.PARTICIPANT_IN:
            role = self.attributes.get("role")
            if role is None:
                raise ValueError(f"edge {self.id}: PARTICIPANT_IN needs attributes.role")
            ParticipantRole(role)
        return self

    def key(self) -> tuple[str, str, str]:
        """Identity used for edge-F1 (ids are not compared, structure is)."""
        return (self.type.value, self.source_id, self.target_id)


# ------------------------------------------------------------------- graph --


class CaseGraph(StrictModel):
    nodes: list[Node]
    edges: list[Edge] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate(self) -> "CaseGraph":
        by_id: dict[str, Any] = {}
        for n in self.nodes:
            if n.id in by_id:
                raise ValueError(f"duplicate node id {n.id!r}")
            by_id[n.id] = n

        edge_ids: set[str] = set()
        incoming: dict[tuple[str, EdgeType], list[Edge]] = defaultdict(list)
        touching: dict[tuple[str, EdgeType], list[Edge]] = defaultdict(list)
        for e in self.edges:
            if e.id in edge_ids:
                raise ValueError(f"duplicate edge id {e.id!r}")
            edge_ids.add(e.id)
            for end in (e.source_id, e.target_id):
                if end not in by_id:
                    raise ValueError(f"edge {e.id} references unknown node {end!r}")
            src_ok, tgt_ok = EDGE_CONSTRAINTS[e.type]
            s_t, t_t = NodeType(by_id[e.source_id].type), NodeType(by_id[e.target_id].type)
            if s_t not in src_ok or t_t not in tgt_ok:
                raise ValueError(
                    f"edge {e.id}: {e.type.value} not allowed from {s_t.value} to {t_t.value}"
                )
            incoming[(e.target_id, e.type)].append(e)
            touching[(e.source_id, e.type)].append(e)
            touching[(e.target_id, e.type)].append(e)

        self._check_temporal_dag()

        for n in self.nodes:
            if n.type == NodeType.CLAIM:
                if n.status == EpistemicStatus.EVIDENCE_SUPPORTED and not any(
                    by_id[e.source_id].type == NodeType.EVIDENCE
                    for e in incoming[(n.id, EdgeType.SUPPORTS)]
                ):
                    raise ValueError(f"claim {n.id} is evidence_supported but has no SUPPORTS edge")
                if n.status == EpistemicStatus.CONFLICTING and not touching[(n.id, EdgeType.CONTRADICTS)]:
                    raise ValueError(f"claim {n.id} is conflicting but has no CONTRADICTS edge")
            if n.type == NodeType.ELEMENT:
                sat = bool(incoming[(n.id, EdgeType.SATISFIES)])
                ref = bool(incoming[(n.id, EdgeType.REFUTES)])
                lack = bool(incoming[(n.id, EdgeType.LACKS)])
                expected = {
                    ElementValue.SATISFIED: (True, False, False),
                    ElementValue.CONTRADICTED: (False, True, False),
                    ElementValue.UNKNOWN: (False, False, True),
                }[n.value]
                if (sat, ref, lack) != expected:
                    raise ValueError(
                        f"element {n.id} value={n.value.value} inconsistent with edges "
                        f"(SATISFIES={sat}, REFUTES={ref}, LACKS={lack})"
                    )
        return self

    def _check_temporal_dag(self) -> None:
        adj: dict[str, list[str]] = defaultdict(list)
        for e in self.edges:
            if e.type == EdgeType.BEFORE:
                adj[e.source_id].append(e.target_id)
        WHITE, GREY, BLACK = 0, 1, 2
        color: dict[str, int] = defaultdict(int)

        def visit(u: str) -> None:
            color[u] = GREY
            for v in adj[u]:
                if color[v] == GREY:
                    raise ValueError(f"BEFORE edges form a cycle through {u!r} -> {v!r}")
                if color[v] == WHITE:
                    visit(v)
            color[u] = BLACK

        for u in list(adj):
            if color[u] == WHITE:
                visit(u)

    def node(self, node_id: str) -> Any:
        for n in self.nodes:
            if n.id == node_id:
                return n
        raise KeyError(node_id)
