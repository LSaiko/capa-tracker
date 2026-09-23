import json
from collections.abc import Iterator

import jsonschema
import pytest
from fastapi.testclient import TestClient

from app.export import SCHEMA_FILE
from app.main import app, get_store
from app.store import Store

client = TestClient(app)

NC_BODY = {
    "description": "Bracket torque out of spec on line 3; work instruction lacks a torque spec",
    "source": "internal",
    "severity": "major",
    "detected_date": "2026-09-01",
}
WHYS = [
    {"question": "Why did the nonconformance happen?", "answer": "Operator used the wrong value"},
    {"question": "Why did that happen?", "answer": "The work instruction lacks a torque spec"},
]
CAPA_BODY = {
    "nonconformance_id": "NC-1",
    "action_description": "Add torque spec to WI-42",
    "owner": "qe",
    "due_date": "2026-09-10",
}


@pytest.fixture(autouse=True)
def _fresh_store() -> Iterator[None]:
    # ponytail: the fast suite runs on the in-memory Store; SQLite is covered by
    # tests/test_sqlite_store.py and tests/test_sqlite_integration.py.
    memory = Store()
    app.dependency_overrides[get_store] = lambda: memory
    yield
    app.dependency_overrides.clear()


def test_health() -> None:
    assert client.get("/health").json() == {"status": "ok"}


def run_to_pending() -> str:
    client.post("/nonconformance", json=NC_BODY)
    assert (
        client.post("/rca", json={"nonconformance_id": "NC-1", "method": "5-why"}).status_code
        == 200
    )
    capa = client.post("/capa", json=CAPA_BODY).json()
    return str(capa["capa"]["id"])


def test_happy_path_to_closure() -> None:
    nc = client.post("/nonconformance", json=NC_BODY).json()
    assert nc["id"] == "NC-1" and nc["status"] == "open"

    r = client.post("/rca", json={"nonconformance_id": "NC-1", "method": "5-why", "steps": WHYS})
    body = r.json()
    assert r.status_code == 200
    assert (
        body["rca"]["confidence_band"] == "HIGH" and body["rca"]["suggested_category"] == "Method"
    )
    assert body["suggestion"]["band"] == "HIGH" and body["suggestion"]["suggested"] == "Method"
    assert (
        client.get("/nonconformance/NC-1").json()["nonconformance"]["status"] == "rca_in_progress"
    )

    r = client.post("/capa", json=CAPA_BODY)
    assert r.status_code == 200
    assert r.json()["capa"]["id"] == "CAPA-1"
    assert r.json()["scheduled_check"] == {
        "capa_id": "CAPA-1",
        "check_date": "2026-10-10",
        "method": "30-day post-implementation effectiveness review",
        "result": "pending",
        "evidence_uri": None,
    }
    open_capas = client.get("/open-capas").json()
    assert len(open_capas) == 1 and open_capas[0]["pending_check"]["result"] == "pending"
    assert open_capas[0]["nonconformance"]["status"] == "effectiveness_pending"

    r = client.post(
        "/effectiveness-check",
        json={
            "capa_id": "CAPA-1",
            "check_date": "2026-10-10",
            "method": "torque audit",
            "result": "effective",
            "evidence_uri": "file://audit.pdf",
        },
    )
    assert r.status_code == 200 and r.json()["nonconformance"]["status"] == "effectiveness_pending"

    r = client.post(
        "/close",
        json={
            "capa_id": "CAPA-1",
            "closed_date": "2026-10-12",
            "closed_by": "qa-mgr",
            "linked_requirement_ids": ["REQ-7"],
        },
    )
    assert r.status_code == 200
    evidence = r.json()
    schema = json.loads(SCHEMA_FILE.read_text(encoding="utf-8"))
    jsonschema.validate(evidence, schema, cls=jsonschema.Draft202012Validator)
    assert evidence["evidence_id"] == "CAPA-1" and evidence["requirement_ids"] == ["REQ-7"]
    assert evidence["nonconformance"]["status"] == "closed"
    assert client.get("/closure/CAPA-1/evidence.json").json()["evidence_id"] == "CAPA-1"

    pdf = client.get("/closure/CAPA-1/report.pdf")
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf"
    assert pdf.content.startswith(b"%PDF") and b"820.100" in pdf.content

    detail = client.get("/nonconformance/NC-1").json()
    assert detail["closure"]["closed_by"] == "qa-mgr" and len(detail["checks"]) == 1
    assert [f["reads_systemic"] for f in detail["why_flags"]] == [False, True]
    assert client.get("/open-capas").json() == []
    assert client.get("/metrics").json() == {
        "open": 0,
        "closed": 1,
        "by_status": {
            "open": 0,
            "rca_in_progress": 0,
            "capa_assigned": 0,
            "effectiveness_pending": 0,
            "closed": 1,
        },
        "opened_by_month": {"2026-09": 1},
        "closed_by_month": {"2026-10": 1},
        "reopened": 0,
    }


def test_reopen_on_not_effective() -> None:
    capa_id = run_to_pending()
    r = client.post(
        "/effectiveness-check",
        json={
            "capa_id": capa_id,
            "check_date": "2026-10-10",
            "method": "audit",
            "result": "not_effective",
        },
    )
    assert r.status_code == 200 and r.json()["nonconformance"]["status"] == "capa_assigned"
    assert client.get("/metrics").json()["reopened"] == 1
    # closing a reopened NC is blocked by the closure gate
    r = client.post(
        "/close", json={"capa_id": capa_id, "closed_date": "2026-10-12", "closed_by": "qa"}
    )
    assert r.status_code == 409
    # a revised CAPA replaces the ineffective one and re-enters verification
    r = client.post("/capa", json={**CAPA_BODY, "action_description": "Revised: poka-yoke driver"})
    assert r.status_code == 200 and r.json()["capa"]["id"] == "CAPA-2"
    detail = client.get("/nonconformance/NC-1").json()
    assert detail["nonconformance"]["status"] == "effectiveness_pending"
    assert detail["capa"]["id"] == "CAPA-2" and detail["checks"][0]["result"] == "pending"


@pytest.mark.parametrize(
    ("description", "band"),
    [
        ("gauge calibration was overdue and the fixture was worn", "AMBIGUOUS"),
        ("operator on shift used gauge", "LOW"),
    ],
)
def test_rca_non_high_leaves_suggested_none(description: str, band: str) -> None:
    client.post("/nonconformance", json={**NC_BODY, "description": description})
    body = client.post("/rca", json={"nonconformance_id": "NC-1", "method": "fishbone"}).json()
    assert body["rca"]["suggested_category"] is None and body["rca"]["confidence"] is not None
    assert body["rca"]["confidence_band"] == band == body["suggestion"]["band"]
    assert len(body["suggestion"]["candidates"]) == 2
    assert (body["suggestion"]["prompt"] is not None) == (band == "LOW")


def test_rca_explicit_confidence_is_kept() -> None:
    client.post("/nonconformance", json=NC_BODY)
    body = client.post(
        "/rca",
        json={"nonconformance_id": "NC-1", "method": "5-why", "confidence": 0.5},
    ).json()
    assert body["rca"]["confidence"] == 0.5 and body["rca"]["confidence_band"] == "LOW"
    assert body["rca"]["suggested_category"] is None and body["suggestion"]["band"] == "HIGH"


def test_rca_suggest_endpoint() -> None:
    high = client.get("/rca/suggest", params={"description": "wrong torque spec"}).json()
    assert high["band"] == "HIGH" and high["suggested"] == "Method"
    low = client.get("/rca/suggest", params={"description": "it broke"}).json()
    assert low["band"] == "LOW" and low["prompt"]


def test_409_out_of_order() -> None:
    client.post("/nonconformance", json=NC_BODY)
    r = client.post("/capa", json=CAPA_BODY)
    assert r.status_code == 409 and "open -> capa_assigned" in r.json()["detail"]


def test_404_unknown_ids() -> None:
    assert client.get("/nonconformance/NC-99").status_code == 404
    assert (
        client.post("/rca", json={"nonconformance_id": "NC-99", "method": "5-why"}).status_code
        == 404
    )
    assert client.get("/closure/CAPA-99/report.pdf").status_code == 404
    assert client.get("/closure/CAPA-99/evidence.json").status_code == 404


def test_list_and_metrics_shape() -> None:
    client.post("/nonconformance", json=NC_BODY)
    client.post("/nonconformance", json={**NC_BODY, "detected_date": "2026-08-15"})
    assert [n["id"] for n in client.get("/nonconformances").json()] == ["NC-1", "NC-2"]
    m = client.get("/metrics").json()
    assert m["open"] == 2 and m["closed"] == 0 and m["by_status"]["open"] == 2
    assert m["opened_by_month"] == {"2026-08": 1, "2026-09": 1} and m["closed_by_month"] == {}
