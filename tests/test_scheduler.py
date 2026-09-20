from datetime import date

import pytest

from app.scheduler import schedule_effectiveness_check
from schemas import CorrectiveAction

CAPA = CorrectiveAction(
    id="CAPA-1",
    nonconformance_id="NC-1",
    action_description="Add torque spec",
    owner="qe",
    due_date=date(2026, 9, 1),
)


def test_default_30_days(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CAPA_EFFECTIVENESS_INTERVAL_DAYS", raising=False)
    check = schedule_effectiveness_check(CAPA)
    assert check.check_date == date(2026, 10, 1) and check.result == "pending"
    assert check.capa_id == "CAPA-1"


def test_env_override_and_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CAPA_EFFECTIVENESS_INTERVAL_DAYS", "45")
    assert schedule_effectiveness_check(CAPA).check_date == date(2026, 10, 16)
    assert schedule_effectiveness_check(CAPA, interval_days=7).check_date == date(2026, 9, 8)
