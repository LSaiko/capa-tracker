import itertools
import json
from datetime import date
from pathlib import Path

import jsonschema
import pytest
from test_schemas import CAPA, CHECK, CLOSURE, NC, RCA_WHY

from app.export import SCHEMA_FILE, build_closure_bundle, export_json
from app.report import render_closure_report
from app.scheduler import schedule_effectiveness_check
from app.store import Store
from app.workflow import TRANSITIONS, InvalidTransition, apply_effectiveness, close, transition
from schemas import ClosureEvidence, EffectivenessCheck, NcStatus, Nonconformance

PATH = [
    NcStatus.OPEN,
    NcStatus.RCA_IN_PROGRESS,
    NcStatus.CAPA_ASSIGNED,
    NcStatus.EFFECTIVENESS_PENDING,
    NcStatus.CLOSED,
]


def at(status: NcStatus) -> Nonconformance:
    return NC.model_copy(update={"status": status})


VALID = [(a, b) for a in NcStatus for b in NcStatus if b in TRANSITIONS[a]]
INVALID = [(a, b) for a in NcStatus for b in NcStatus if b not in TRANSITIONS[a]]


def test_transition_table_is_the_five_step_path_plus_reopen() -> None:
    assert set(VALID) == {*itertools.pairwise(PATH), (PATH[3], PATH[2])}
    assert len(VALID) + len(INVALID) == len(NcStatus) ** 2 == 25


@pytest.mark.parametrize(("a", "b"), VALID, ids=[f"{a.value}->{b.value}" for a, b in VALID])
def test_valid_transition(a: NcStatus, b: NcStatus) -> None:
    assert transition(at(a), b).status is b


@pytest.mark.parametrize(("a", "b"), INVALID, ids=[f"{a.value}->{b.value}" for a, b in INVALID])
def test_invalid_transition_raises(a: NcStatus, b: NcStatus) -> None:
    with pytest.raises(InvalidTransition, match=f"{a.value} -> {b.value}"):
        transition(at(a), b)


def test_reopen_on_not_effective() -> None:
    nc = at(NcStatus.EFFECTIVENESS_PENDING)
    bad = CHECK.model_copy(update={"result": "not_effective"})
    assert apply_effectiveness(nc, bad).status is NcStatus.CAPA_ASSIGNED
    assert apply_effectiveness(nc, CHECK).status is NcStatus.EFFECTIVENESS_PENDING
    for blocked in (bad, CHECK.model_copy(update={"result": "pending"})):
        with pytest.raises(InvalidTransition, match="cannot close"):
            close(nc, blocked, CLOSURE)
    with pytest.raises(InvalidTransition, match="!="):
        close(nc, CHECK.model_copy(update={"capa_id": "CAPA-9"}), CLOSURE)


def run_to_closed() -> Store:
    store = Store()
    nc = transition(NC, NcStatus.RCA_IN_PROGRESS)
    store.rcas[nc.id] = RCA_WHY
    nc = transition(nc, NcStatus.CAPA_ASSIGNED)
    store.capas[CAPA.id] = CAPA
    nc = transition(nc, NcStatus.EFFECTIVENESS_PENDING)
    pending = schedule_effectiveness_check(CAPA, 30)
    assert pending.result == "pending"
    done: EffectivenessCheck = pending.model_copy(
        update={"result": "effective", "evidence_uri": "file://audit-2026-10.pdf"}
    )
    nc = close(apply_effectiveness(nc, done), done, CLOSURE)
    store.checks[CAPA.id] = done
    store.closures[CAPA.id] = CLOSURE
    store.nonconformances[nc.id] = nc
    return store


def test_full_run_and_pdf_and_json(tmp_path: Path) -> None:
    store = run_to_closed()
    assert store.nonconformances["NC-1"].status is NcStatus.CLOSED
    bundle = build_closure_bundle(store, "NC-1")
    assert bundle.evidence_id == "CAPA-1" and bundle.requirement_ids == ["REQ-7"]

    pdf = render_closure_report(bundle, tmp_path / "closure.pdf")
    raw = pdf.read_bytes()
    assert pdf.exists() and len(raw) > 1024
    for needle in (b"NC-1", b"820.100", b"CAPA-1", b"REQ-7", b"AMBIGUOUS"):
        assert needle in raw

    out = export_json(bundle, tmp_path / "closure.json")
    payload = json.loads(out.read_text(encoding="utf-8"))
    schema = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
    jsonschema.validate(payload, schema, cls=jsonschema.Draft202012Validator)
    assert payload["evidence_id"] == bundle.evidence_id == "CAPA-1"
    assert payload["requirement_ids"] == bundle.requirement_ids == ["REQ-7"]
    assert payload["cfr_citation"] == "21 CFR 820.100" and payload["source"] == "capa-tracker"
    assert ClosureEvidence.model_validate_json(out.read_text(encoding="utf-8")) == bundle


def test_fishbone_pdf(tmp_path: Path) -> None:
    from test_schemas import RCA_FISH

    store = run_to_closed()
    store.rcas["NC-1"] = RCA_FISH
    raw = render_closure_report(
        build_closure_bundle(store, "NC-1"), tmp_path / "f.pdf"
    ).read_bytes()
    assert b"Method" in raw and b"No torque spec" in raw


def test_bundle_missing_pieces() -> None:
    with pytest.raises(KeyError):
        build_closure_bundle(Store(), "NC-1")
    store = Store()
    store.nonconformances["NC-1"] = NC
    with pytest.raises(KeyError, match="no CAPA"):
        build_closure_bundle(store, "NC-1")


def test_json_schema_file_matches_model() -> None:
    """Regenerate with: python -m app.export (writes docs/closure-evidence.schema.json)."""
    assert json.loads(SCHEMA_FILE.read_text(encoding="utf-8")) == ClosureEvidence.model_json_schema(
        mode="serialization"
    )


def test_scheduler_feeds_workflow() -> None:
    assert schedule_effectiveness_check(CAPA, 1).check_date == date(2026, 9, 2)
