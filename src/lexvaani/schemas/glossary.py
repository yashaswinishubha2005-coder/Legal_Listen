"""Term-aligned en/kn/hi legal glossary."""

from __future__ import annotations

from enum import Enum

from pydantic import Field

from .common import StrictModel, Verification


class TermCategory(str, Enum):
    PROCEDURE = "procedure"      # FIR, complaint, bail, summons
    FAMILY = "family"
    PROPERTY = "property"        # khata, RTC/pahani, partition
    CRIMINAL = "criminal"
    CYBER = "cyber"
    CONSUMER = "consumer"
    INSTITUTION = "institution"  # police station, district commission
    GENERAL = "general"


class GlossaryEntry(StrictModel):
    term_id: str = Field(pattern=r"^[a-z0-9_]+$")
    category: TermCategory
    en: str
    kn: str
    hi: str
    kn_latn: str | None = None   # common romanization users type
    hi_latn: str | None = None
    colloquial: dict[str, list[str]] = Field(
        default_factory=dict, description="everyday words users say instead, per language")
    plain_definition_en: str
    is_legal_term: bool = True   # used by the label-leakage check
    verification: Verification = Verification.TO_VERIFY
    notes: str | None = None
