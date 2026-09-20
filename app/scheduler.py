"""Effectiveness verification scheduling (21 CFR 820.100(a)(4): verify or validate the CAPA)."""

from __future__ import annotations

import os
from datetime import timedelta

from schemas import CorrectiveAction, EffectivenessCheck


def schedule_effectiveness_check(
    capa: CorrectiveAction, interval_days: int | None = None
) -> EffectivenessCheck:
    """Pending check at due_date + interval (CAPA_EFFECTIVENESS_INTERVAL_DAYS, default 30).

    The env var is read at call time (not as a def-time default) so overrides take effect
    without re-importing the module.
    """
    if interval_days is None:
        interval_days = int(os.getenv("CAPA_EFFECTIVENESS_INTERVAL_DAYS", "30"))
    return EffectivenessCheck(
        capa_id=capa.id,
        check_date=capa.due_date + timedelta(days=interval_days),
        method=f"{interval_days}-day post-implementation effectiveness review",
        result="pending",
    )
