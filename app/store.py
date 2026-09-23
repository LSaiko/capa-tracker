"""Record store: the `CapaStore` protocol the service layer talks to, plus the in-memory one.

# ponytail: the in-memory `Store` is the fast test double; `app/sqlite_store.py` is the
# persistent implementation of the same protocol and the default at runtime.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from schemas import (
    ClosureRecord,
    CorrectiveAction,
    EffectivenessCheck,
    Nonconformance,
    RootCauseAnalysis,
)


class CapaStore(Protocol):
    """Exactly what the service layer reads and writes — nothing speculative.

    Every getter raises `KeyError` for an unknown id (the API turns that into a 404).
    """

    def get_nc(self, nc_id: str) -> Nonconformance: ...
    def put_nc(self, nc: Nonconformance) -> None: ...
    def list_ncs(self) -> list[Nonconformance]: ...
    def get_rca(self, nc_id: str) -> RootCauseAnalysis: ...
    def put_rca(self, rca: RootCauseAnalysis) -> None: ...
    def get_capa(self, capa_id: str) -> CorrectiveAction: ...
    def put_capa(self, capa: CorrectiveAction) -> None: ...
    def list_capas(self) -> list[CorrectiveAction]: ...
    def capa_for(self, nc_id: str) -> CorrectiveAction: ...
    def drop_capa(self, capa_id: str) -> None: ...
    def get_check(self, capa_id: str) -> EffectivenessCheck: ...
    def put_check(self, check: EffectivenessCheck) -> None: ...
    def get_closure(self, capa_id: str) -> ClosureRecord: ...
    def put_closure(self, closure: ClosureRecord) -> None: ...
    def list_closures(self) -> list[ClosureRecord]: ...
    def bump_reopens(self) -> None: ...
    def reopens(self) -> int: ...


@dataclass
class Store(CapaStore):
    """In-memory implementation: one dict per record type."""

    nonconformances: dict[str, Nonconformance] = field(default_factory=dict)  # by nc id
    rcas: dict[str, RootCauseAnalysis] = field(default_factory=dict)  # by nonconformance_id
    capas: dict[str, CorrectiveAction] = field(default_factory=dict)  # by capa id
    checks: dict[str, EffectivenessCheck] = field(default_factory=dict)  # by capa_id
    closures: dict[str, ClosureRecord] = field(default_factory=dict)  # by capa_id
    _reopens: int = 0  # ponytail: a counter beats a per-NC history until an audit trail is needed

    def get_nc(self, nc_id: str) -> Nonconformance:
        return self.nonconformances[nc_id]

    def put_nc(self, nc: Nonconformance) -> None:
        self.nonconformances[nc.id] = nc

    def list_ncs(self) -> list[Nonconformance]:
        return list(self.nonconformances.values())

    def get_rca(self, nc_id: str) -> RootCauseAnalysis:
        return self.rcas[nc_id]

    def put_rca(self, rca: RootCauseAnalysis) -> None:
        self.rcas[rca.nonconformance_id] = rca

    def get_capa(self, capa_id: str) -> CorrectiveAction:
        return self.capas[capa_id]

    def put_capa(self, capa: CorrectiveAction) -> None:
        self.capas[capa.id] = capa

    def list_capas(self) -> list[CorrectiveAction]:
        return list(self.capas.values())

    def capa_for(self, nc_id: str) -> CorrectiveAction:
        # ponytail: one CAPA per NC; a list per NC is the upgrade when multi-action plans arrive.
        try:
            return next(c for c in self.capas.values() if c.nonconformance_id == nc_id)
        except StopIteration:
            raise KeyError(f"no CAPA for {nc_id}") from None

    def drop_capa(self, capa_id: str) -> None:
        """Reopen path: the replaced CAPA takes its scheduled check with it."""
        del self.capas[capa_id]
        self.checks.pop(capa_id, None)

    def get_check(self, capa_id: str) -> EffectivenessCheck:
        return self.checks[capa_id]

    def put_check(self, check: EffectivenessCheck) -> None:
        self.checks[check.capa_id] = check

    def get_closure(self, capa_id: str) -> ClosureRecord:
        return self.closures[capa_id]

    def put_closure(self, closure: ClosureRecord) -> None:
        self.closures[closure.capa_id] = closure

    def list_closures(self) -> list[ClosureRecord]:
        return list(self.closures.values())

    def bump_reopens(self) -> None:
        self._reopens += 1

    def reopens(self) -> int:
        return self._reopens


store = Store()
