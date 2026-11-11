"""Shared primitives used by every LexVaani-IN schema.

Conventions (see docs/annotation_guidelines.md, "Global conventions"):
- All text is Unicode NFC. Offsets are Python ``str`` indices (code points),
  half-open ``[start, end)``.
- Enum values are lowercase snake_case and are part of the public format;
  changing one is a breaking dataset version bump.
"""

from __future__ import annotations

import unicodedata
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

SCHEMA_VERSION = "0.1.0"

Confidence = Annotated[float, Field(ge=0.0, le=1.0)]


class StrictModel(BaseModel):
    """Base for all schemas: unknown fields are errors, models are immutable."""

    model_config = ConfigDict(extra="forbid", frozen=True, use_enum_values=False)


# ---------------------------------------------------------------- language --


class Language(str, Enum):
    EN = "en"
    KN = "kn"
    HI = "hi"


class Script(str, Enum):
    LATN = "Latn"
    KNDA = "Knda"
    DEVA = "Deva"


class LangVariant(str, Enum):
    """The six language/script conditions of the benchmark."""

    EN = "en"                  # English, Latin script
    KN = "kn"                  # Kannada, Kannada script
    HI = "hi"                  # Hindi, Devanagari
    KN_EN_LATN = "kn-en_latn"  # Kanglish, fully romanized
    KN_EN_MIXED = "kn-en_mixed"  # Kanglish, Kannada script + Latin English words
    HI_EN_LATN = "hi-en_latn"  # Hinglish, fully romanized

    @property
    def is_code_mixed(self) -> bool:
        return "-" in self.value


# -------------------------------------------------------------- epistemics --


class EpistemicStatus(str, Enum):
    """How the system knows a fact. Decision tree in the guidelines, T6."""

    REPORTED = "reported"                      # user asserts it, no evidence mentioned
    EVIDENCE_SUPPORTED = "evidence_supported"  # user asserts it AND cites evidence held
    INFERRED = "inferred"                      # not stated; follows from stated facts
    CONFLICTING = "conflicting"                # contradicted by another fact/turn
    UNKNOWN = "unknown"                        # asked or relevant, but not known


class Verification(str, Enum):
    """Legal-accuracy flag. Anything not checked by a human against the
    official text is TO_VERIFY. Nothing is VERIFIED by default."""

    VERIFIED = "verified"
    TO_VERIFY = "to_verify"


# ------------------------------------------------------------------ issues --


class Domain(str, Enum):
    CRIMINAL = "criminal"
    FAMILY = "family"
    PROPERTY = "property"
    CYBER = "cyber"
    CONSUMER_FINANCIAL = "consumer_financial"


class IssueId(str, Enum):
    # Criminal
    CRIM_HURT = "crim.hurt_assault"
    CRIM_INTIMIDATION = "crim.criminal_intimidation"
    CRIM_THEFT = "crim.theft"
    CRIM_CHEATING = "crim.cheating"
    CRIM_POLICE_REFUSAL = "crim.police_refusal_fir"
    # Family
    FAM_DIVORCE = "fam.divorce"
    FAM_MAINTENANCE = "fam.maintenance"
    FAM_CUSTODY = "fam.custody"
    FAM_DOMESTIC_VIOLENCE = "fam.domestic_violence"
    FAM_DOWRY = "fam.dowry_harassment"
    # Property
    PROP_PARTITION = "prop.inheritance_partition"
    PROP_ENCROACHMENT = "prop.encroachment"
    PROP_COHEIR_SALE = "prop.coheir_sale_without_consent"
    PROP_BOUNDARY = "prop.boundary_dispute"
    PROP_FORGERY = "prop.forged_documents"
    # Cyber
    CYB_UPI_FRAUD = "cyb.upi_payment_fraud"
    CYB_PHISHING = "cyb.phishing_account_takeover"
    CYB_IMPERSONATION = "cyb.impersonation"
    CYB_STALKING = "cyb.cyberstalking"
    CYB_IMAGE_ABUSE = "cyb.morphed_intimate_image"
    # Consumer & Financial
    CON_DEFECTIVE = "con.defective_product"
    CON_SERVICE = "con.deficiency_in_service"
    FIN_UNAUTH_TXN = "fin.unauthorized_bank_txn"
    CON_REFUND = "con.refund_refusal"
    FIN_LOAN_HARASS = "fin.loan_recovery_harassment"
    # Routing labels (not legal issues in the library)
    OUT_OF_SCOPE = "x.out_of_scope"   # legal, but not one of the 25 -> lawyer
    NON_LEGAL = "x.non_legal"         # no legal angle

    @property
    def domain(self) -> Domain | None:
        prefix = self.value.split(".", 1)[0]
        return {
            "crim": Domain.CRIMINAL,
            "fam": Domain.FAMILY,
            "prop": Domain.PROPERTY,
            "cyb": Domain.CYBER,
            "con": Domain.CONSUMER_FINANCIAL,
            "fin": Domain.CONSUMER_FINANCIAL,
        }.get(prefix)

    @property
    def is_routing_label(self) -> bool:
        return self.value.startswith("x.")


# ------------------------------------------------------------------- spans --


class Span(StrictModel):
    """A character span inside one text unit (a narrative, or one dialogue turn).

    ``unit_id`` names the text unit: the sample id for narratives, or
    ``<sample_id>#t<turn_index>`` for dialogue turns.
    """

    unit_id: str
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    text: str = Field(min_length=1)

    @model_validator(mode="after")
    def _check(self) -> "Span":
        if self.end <= self.start:
            raise ValueError(f"span end ({self.end}) must be > start ({self.start})")
        if self.end - self.start != len(self.text):
            raise ValueError(
                f"span length {self.end - self.start} != len(text) {len(self.text)}"
            )
        if self.text != self.text.strip():
            raise ValueError("span text must not begin or end with whitespace")
        return self

    def verify_against(self, source: str) -> None:
        """Raise if this span does not match ``source`` exactly. Used by the
        alignment QC; we never guess or repair offsets."""
        if unicodedata.normalize("NFC", source) != source:
            raise ValueError(f"{self.unit_id}: source text is not NFC")
        got = source[self.start : self.end]
        if got != self.text:
            raise ValueError(
                f"{self.unit_id}[{self.start}:{self.end}] is {got!r}, expected {self.text!r}"
            )


# ---------------------------------------------------------------- temporal --


class TimexType(str, Enum):
    DATE = "date"
    TIME = "time"
    DURATION = "duration"
    SET = "set"


class Timex(StrictModel):
    """TIMEX3-style normalized time expression.

    ``value`` follows TIMEX3/ISO-8601 conventions, including partial and
    underspecified values: ``2025-03-14``, ``2025-03``, ``2025-W11``,
    ``2025-XX-XX`` (year known only), ``P2M`` (duration), ``PAST_REF``.
    ``anchor`` is the conversation date (or another timex id) that a relative
    expression such as "ninne" / "kal" / "2 months back" resolves against.
    """

    id: str
    type: TimexType
    value: str = Field(min_length=1)
    anchor: str | None = None
    approximate: bool = False   # "around", "maybe last Ugadi"
    span: Span | None = None    # None only for spec-level (hidden) times
