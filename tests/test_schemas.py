from datetime import date

import pytest
from pydantic import BaseModel, ValidationError

from schemas import (
    ClosureRecord,
    ConfidenceBand,
    CorrectiveAction,
    EffectivenessCheck,
    FishboneCategory,
    FishboneEntry,
    NcStatus,
    Nonconformance,
    RootCauseAnalysis,
    WhyStep,
    band_for,
)

D = date(2026, 9, 1)
NC = Nonconformance(
    id="NC-1",
    description="Bracket torque out of spec on line 3",
    source="internal",
    severity="major",
    detected_date=D,
)
WHYS = [
    WhyStep(question="Why did the torque go out of spec?", answer="Operator used the wrong value"),
    WhyStep(question="Why the wrong value?", answer="The work instruction lacks a torque spec"),
]
RCA_WHY = RootCauseAnalysis(
    nonconformance_id="NC-1",
    method="5-why",
    steps=WHYS,
    suggested_category=FishboneCategory.METHOD,
    confidence=0.6,
    root_cause_text="Torque spec missing from WI-42",
)
RCA_FISH = RootCauseAnalysis(
    nonconformance_id="NC-1",
    method="fishbone",
    steps=[FishboneEntry(category=FishboneCategory.METHOD, cause="No torque spec on WI")],
)
CAPA = CorrectiveAction(
    id="CAPA-1",
    nonconformance_id="NC-1",
    action_description="Add torque spec to WI-42 and retrain",
    owner="qe@example.com",
    due_date=D,
)
CHECK = EffectivenessCheck(
    capa_id="CAPA-1", check_date=D, method="30-day torque audit", result="effective"
)
CLOSURE = ClosureRecord(
    capa_id="CAPA-1", closed_date=D, closed_by="qa-mgr", linked_requirement_ids=["REQ-7"]
)


@pytest.mark.parametrize("model", [NC, RCA_WHY, RCA_FISH, CAPA, CHECK, CLOSURE])
def test_round_trip(model: BaseModel) -> None:
    assert type(model).model_validate_json(model.model_dump_json()) == model


@pytest.mark.parametrize(
    ("conf", "band"),
    [(0.6, ConfidenceBand.AMBIGUOUS), (0.8, ConfidenceBand.HIGH), (0.54, ConfidenceBand.LOW)],
)
def test_confidence_band(conf: float, band: ConfidenceBand) -> None:
    rca = RCA_WHY.model_copy(update={"confidence": conf})
    assert rca.confidence_band == band == band_for(conf)


def test_band_none_without_confidence() -> None:
    assert RCA_FISH.confidence_band is None
    assert "confidence_band" in RCA_FISH.model_dump()


def test_extra_fields_rejected() -> None:
    with pytest.raises(ValidationError):
        Nonconformance(**NC.model_dump(), extra="nope")  # type: ignore[arg-type]


def test_method_steps_mismatch_rejected() -> None:
    with pytest.raises(ValidationError, match="requires FishboneEntry"):
        RootCauseAnalysis(nonconformance_id="NC-1", method="fishbone", steps=WHYS)
    with pytest.raises(ValidationError, match="requires WhyStep"):
        RootCauseAnalysis(nonconformance_id="NC-1", method="5-why", steps=RCA_FISH.steps)


def test_id_patterns_and_defaults() -> None:
    assert NC.status is NcStatus.OPEN and CAPA.status == "planned" and CHECK.result == "effective"
    for bad in ({"id": "NC1"}, {"description": ""}, {"severity": "fatal"}):
        with pytest.raises(ValidationError):
            Nonconformance(**{**NC.model_dump(), **bad})
