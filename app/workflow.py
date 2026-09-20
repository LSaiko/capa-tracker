"""Nonconformance state machine and closure gate (21 CFR 820.100(a)(4): verify effectiveness)."""

from __future__ import annotations

from schemas import ClosureRecord, EffectivenessCheck, NcStatus, Nonconformance

# open -> rca_in_progress -> capa_assigned -> effectiveness_pending -> closed,
# with one loop back: a not_effective check reopens the action phase.
TRANSITIONS: dict[NcStatus, set[NcStatus]] = {
    NcStatus.OPEN: {NcStatus.RCA_IN_PROGRESS},
    NcStatus.RCA_IN_PROGRESS: {NcStatus.CAPA_ASSIGNED},
    NcStatus.CAPA_ASSIGNED: {NcStatus.EFFECTIVENESS_PENDING},
    NcStatus.EFFECTIVENESS_PENDING: {NcStatus.CLOSED, NcStatus.CAPA_ASSIGNED},
    NcStatus.CLOSED: set(),
}


class InvalidTransition(ValueError):
    pass


def transition(nc: Nonconformance, to: NcStatus) -> Nonconformance:
    if to not in TRANSITIONS[nc.status]:
        raise InvalidTransition(f"{nc.id}: {nc.status.value} -> {to.value} is not allowed")
    return nc.model_copy(update={"status": to})


def apply_effectiveness(nc: Nonconformance, check: EffectivenessCheck) -> Nonconformance:
    """A not_effective verification reopens the action phase; anything else leaves the NC as is."""
    if check.result == "not_effective":
        return transition(nc, NcStatus.CAPA_ASSIGNED)
    return nc


def close(nc: Nonconformance, check: EffectivenessCheck, record: ClosureRecord) -> Nonconformance:
    """Closure gate: only an *effective* check for the same CAPA may close the NC."""
    if check.result != "effective":
        raise InvalidTransition(f"{nc.id}: cannot close, effectiveness result is {check.result!r}")
    if check.capa_id != record.capa_id:
        raise InvalidTransition(f"{nc.id}: check {check.capa_id} != closure {record.capa_id}")
    return transition(nc, NcStatus.CLOSED)
