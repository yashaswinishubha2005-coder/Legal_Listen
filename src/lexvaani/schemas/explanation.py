"""T11 plain-language explanation references."""

from __future__ import annotations

from enum import Enum

from pydantic import Field, model_validator

from .common import Language, StrictModel, Verification


class ExplanationStatus(str, Enum):
    COMPLETE = "complete"
    PENDING_CORPUS_TEXT = "pending_corpus_text"   # provision not yet in the parsed corpus


class ExplanationRef(StrictModel):
    explanation_id: str
    spec_id: str
    provision_id: str
    language: Language
    what_it_says: str | None = Field(None, description="verbatim corpus excerpt ONLY")
    what_it_means: str
    why_it_may_apply: str
    conditions: list[str] = Field(min_length=1)
    where_to_verify: str
    status: ExplanationStatus
    verification: Verification = Verification.TO_VERIFY

    @model_validator(mode="after")
    def _status(self) -> "ExplanationRef":
        if (self.status == ExplanationStatus.COMPLETE) != (self.what_it_says is not None):
            raise ValueError(f"{self.explanation_id}: what_it_says must be set iff status=complete")
        return self
