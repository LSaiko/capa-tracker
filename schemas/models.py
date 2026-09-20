"""Pydantic v2 schemas for capa-tracker (21 CFR 820.100 corrective and preventive action)."""

from __future__ import annotations

from datetime import date
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator


class ConfidenceBand(StrEnum):
    HIGH = "HIGH"
    AMBIGUOUS = "AMBIGUOUS"
    LOW = "LOW"


def band_for(confidence: float) -> ConfidenceBand:
    """Three-band routing: >=0.80 HIGH, 0.55-0.79 AMBIGUOUS, <0.55 LOW."""
    if confidence >= 0.80:
        return ConfidenceBand.HIGH
    if confidence >= 0.55:
        return ConfidenceBand.AMBIGUOUS
    return ConfidenceBand.LOW


class FishboneCategory(StrEnum):
    """Ishikawa 6M categories."""

    METHOD = "Method"
    MACHINE = "Machine"
    MATERIAL = "Material"
    MANPOWER = "Manpower"
    MEASUREMENT = "Measurement"
    ENVIRONMENT = "Environment"


class NcStatus(StrEnum):
    """820.100 lifecycle: intake -> investigation -> action -> verification -> closure."""

    OPEN = "open"
    RCA_IN_PROGRESS = "rca_in_progress"
    CAPA_ASSIGNED = "capa_assigned"
    EFFECTIVENESS_PENDING = "effectiveness_pending"
    CLOSED = "closed"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Nonconformance(_Strict):
    id: str = Field(pattern=r"^NC-\d+$")
    description: str = Field(min_length=1)
    source: Literal["audit", "complaint", "internal", "supplier"]
    severity: Literal["minor", "major", "critical"]
    detected_date: date
    status: NcStatus = NcStatus.OPEN


class WhyStep(_Strict):
    question: str
    answer: str


class FishboneEntry(_Strict):
    category: FishboneCategory
    cause: str


class RootCauseAnalysis(_Strict):
    nonconformance_id: str = Field(pattern=r"^NC-\d+$")
    method: Literal["5-why", "fishbone"]
    steps: list[WhyStep] | list[FishboneEntry] = Field(default_factory=list)
    suggested_category: FishboneCategory | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    root_cause_text: str = ""  # human-entered final call (Explainer never fills this)

    @model_validator(mode="before")
    @classmethod
    def _drop_band(cls, data: Any) -> Any:
        """Accept our own dumps back: confidence_band is derived, never an input."""
        return (
            {k: v for k, v in data.items() if k != "confidence_band"}
            if isinstance(data, dict)
            else data
        )

    @model_validator(mode="after")
    def _method_matches_steps(self) -> RootCauseAnalysis:
        expected = WhyStep if self.method == "5-why" else FishboneEntry
        if any(not isinstance(s, expected) for s in self.steps):
            raise ValueError(f"method {self.method!r} requires {expected.__name__} steps")
        return self

    @computed_field  # type: ignore[prop-decorator]
    @property
    def confidence_band(self) -> ConfidenceBand | None:
        return None if self.confidence is None else band_for(self.confidence)


class CorrectiveAction(_Strict):
    id: str = Field(pattern=r"^CAPA-\d+$")
    nonconformance_id: str = Field(pattern=r"^NC-\d+$")
    action_description: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    due_date: date
    status: Literal["planned", "in_progress", "done"] = "planned"


class EffectivenessCheck(_Strict):
    capa_id: str = Field(pattern=r"^CAPA-\d+$")
    check_date: date
    method: str = Field(min_length=1)
    result: Literal["effective", "not_effective", "pending"] = "pending"
    evidence_uri: str | None = None


class ClosureRecord(_Strict):
    capa_id: str = Field(pattern=r"^CAPA-\d+$")
    closed_date: date
    closed_by: str = Field(min_length=1)
    linked_requirement_ids: list[str] = Field(default_factory=list)  # traceability hub keys
