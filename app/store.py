"""In-memory record store.

# ponytail: in-memory dict store, swap for SQLite when persistence is needed (same Store
# attribute names become tables; the service functions only touch these dicts).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from schemas import (
    ClosureRecord,
    CorrectiveAction,
    EffectivenessCheck,
    Nonconformance,
    RootCauseAnalysis,
)


@dataclass
class Store:
    nonconformances: dict[str, Nonconformance] = field(default_factory=dict)  # by nc id
    rcas: dict[str, RootCauseAnalysis] = field(default_factory=dict)  # by nonconformance_id
    capas: dict[str, CorrectiveAction] = field(default_factory=dict)  # by capa id
    checks: dict[str, EffectivenessCheck] = field(default_factory=dict)  # by capa_id
    closures: dict[str, ClosureRecord] = field(default_factory=dict)  # by capa_id

    def capa_for(self, nc_id: str) -> CorrectiveAction:
        # ponytail: one CAPA per NC; a list per NC is the upgrade when multi-action plans arrive.
        try:
            return next(c for c in self.capas.values() if c.nonconformance_id == nc_id)
        except StopIteration:
            raise KeyError(f"no CAPA for {nc_id}") from None


store = Store()
