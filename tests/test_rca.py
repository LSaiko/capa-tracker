from app.rca import looks_like_root_cause, next_why_prompt, suggest_category
from schemas import ConfidenceBand, FishboneCategory, WhyStep


def test_high_method() -> None:
    s = suggest_category("Operator used wrong torque spec on the work instruction")
    assert s.band is ConfidenceBand.HIGH and s.suggested is FishboneCategory.METHOD
    assert s.candidates[0][0] is FishboneCategory.METHOD and s.prompt is None
    assert suggest_category("wrong torque spec").band is ConfidenceBand.HIGH  # CLAUDE.md example


def test_ambiguous_two_candidates() -> None:
    s = suggest_category("gauge calibration was overdue and the fixture was worn")
    assert s.band is ConfidenceBand.AMBIGUOUS and s.suggested is None and s.prompt is None
    assert {c for c, _ in s.candidates} == {FishboneCategory.MEASUREMENT, FishboneCategory.MACHINE}
    assert 0.55 <= s.confidence < 0.80


def test_low_asks_question() -> None:
    s = suggest_category("part came back bad")
    assert s.band is ConfidenceBand.LOW and s.suggested is None and s.candidates == []
    assert s.prompt is not None and s.prompt.endswith("?")
    assert suggest_category("the operator noticed it").band is ConfidenceBand.LOW  # lone weak hit


def test_round_trip_suggestion() -> None:
    s = suggest_category("humidity in the cleanroom")
    assert type(s).model_validate_json(s.model_dump_json()) == s


def test_five_why_chain() -> None:
    problem = "the bracket torque was out of spec"
    answers = [
        "the operator applied the wrong torque",
        "the torque value displayed was wrong",
        "the tool setting had drifted",
        "the tool was not calibrated on schedule",
        "no procedure defines the calibration interval for hand tools",
    ]
    steps: list[WhyStep] = []
    for answer in answers:
        prompt = next_why_prompt(steps, problem)
        assert prompt.startswith("Why did ") and prompt.endswith(" happen?")
        steps.append(WhyStep(question=prompt, answer=answer))
    assert steps[0].question == f"Why did {problem} happen?"
    assert steps[1].question == f"Why did {answers[0]} happen?"
    flags = [looks_like_root_cause(s.answer)[0] for s in steps]
    assert flags == [False, False, False, False, True]
    assert "symptom" in looks_like_root_cause("it was wrong")[1]
    assert "ask why again" in looks_like_root_cause("the shift changed")[1]
