"""Diversity / fairness metadata and provenance (used for slice evaluation)."""

from __future__ import annotations

from enum import Enum

from pydantic import Field

from .common import StrictModel


class Gender(str, Enum):
    FEMALE = "female"
    MALE = "male"
    OTHER = "other"


class AgeGroup(str, Enum):
    A18_25 = "18-25"
    A26_40 = "26-40"
    A41_60 = "41-60"
    A60P = "60+"


class Settlement(str, Enum):
    URBAN = "urban"
    RURAL = "rural"


class KarnatakaRegion(str, Enum):
    """Coarse administrative/cultural regions; used for dialect and slices."""

    BENGALURU = "bengaluru"            # Bengaluru Urban/Rural
    OLD_MYSURU = "old_mysuru"          # Mysuru, Mandya, Hassan, Chamarajanagar
    KITTUR = "kittur_karnataka"        # Dharwad, Belagavi, Haveri, Gadag (north)
    KALYANA = "kalyana_karnataka"      # Kalaburagi, Raichur, Bidar, Ballari (north-east)
    COASTAL = "coastal"                # Dakshina Kannada, Udupi, Uttara Kannada
    MALNAD = "malnad"                  # Shivamogga, Chikkamagaluru, Kodagu


class Religion(str, Enum):
    """Recorded ONLY when legally relevant (personal law routing)."""

    HINDU = "hindu"
    MUSLIM = "muslim"
    CHRISTIAN = "christian"
    SIKH = "sikh"
    JAIN = "jain"
    BUDDHIST = "buddhist"
    INTERFAITH_SMA = "interfaith_sma"   # marriage under the Special Marriage Act
    NOT_RECORDED = "not_recorded"


class Literacy(str, Enum):
    """Proxy only (self-described schooling); never inferred from text style."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class SpeakerMetadata(StrictModel):
    gender: Gender
    age_group: AgeGroup
    settlement: Settlement
    region: KarnatakaRegion
    religion: Religion = Religion.NOT_RECORDED
    literacy_proxy: Literacy


class Provenance(StrictModel):
    generator: str = Field(description="e.g. 'template-v1' or 'llm:<provider>/<model>'")
    generator_version: str
    seed: int
    template_ids: list[str] = Field(default_factory=list)
    prompt_version: str | None = None
    created: str  # ISO date
