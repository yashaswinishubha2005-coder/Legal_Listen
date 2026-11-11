"""Law corpus records (Phase 1).

Two layers:
- ``ProvisionRecord``: one section parsed from an official PDF. ``text`` is
  ONLY ever copied from the source file, never written by hand or by a model.
- ``RegistryEntry``: every provision id the benchmark *references* (issue
  library, gold labels). It records whether the id was found in the parsed
  corpus. Citation validity (T10) is computed against the corpus, and the
  registry makes the gap visible when the corpus is incomplete.
"""

from __future__ import annotations

from pydantic import Field, model_validator

from .common import StrictModel, Verification

PROVISION_ID_PATTERN = r"^[A-Z][A-Za-z0-9_]*:[0-9A-Za-z().\-]+$"


class ActInfo(StrictModel):
    code: str = Field(pattern=r"^[A-Z][A-Za-z0-9_]*$")    # e.g. BNS, HMA, KLRA
    title: str
    year: int
    jurisdiction: str = "IN"          # "IN" central, "IN-KA" Karnataka
    effective_from: str | None = None  # ISO date; TO_VERIFY unless checked
    file_glob: str                     # filename pattern in data/raw/acts/
    official_url: str | None = None    # placeholder, filled manually


class ProvisionRecord(StrictModel):
    provision_id: str = Field(pattern=PROVISION_ID_PATTERN)
    act: str
    act_title: str
    year: int
    section_id: str
    title: str | None
    text: str = Field(min_length=1)
    chapter: str | None = None
    jurisdiction: str
    effective_from: str | None = None
    replaces: list[str] = Field(default_factory=list)
    replaced_by: list[str] = Field(default_factory=list)
    mapping_verification: Verification = Verification.TO_VERIFY
    source_file: str
    source_pages: list[int] = Field(default_factory=list)
    official_url: str | None = None
    parse_warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _id(self) -> "ProvisionRecord":
        if self.provision_id != f"{self.act}:{self.section_id}":
            raise ValueError(f"provision_id {self.provision_id} != {self.act}:{self.section_id}")
        return self


class RegistryEntry(StrictModel):
    provision_id: str = Field(pattern=PROVISION_ID_PATTERN)
    act: str
    section_id: str
    title_hint: str | None = Field(
        None, description="what we EXPECT the heading to be; checked against the PDF, never used as text")
    in_corpus: bool = False
    title_match: bool | None = None   # heading in PDF matched title_hint
    verification: Verification = Verification.TO_VERIFY
    maps_to: list[str] = Field(default_factory=list, description="IPC<->BNS style equivalents, TO_VERIFY")
    referenced_by: list[str] = Field(default_factory=list)
    note: str | None = None
