"""The full 820.100 lifecycle through the API, against a SqliteStore on disk."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from test_api import CAPA_BODY, NC_BODY, WHYS

from app.main import app, get_store
from app.sqlite_store import SqliteStore

CHECK_BODY = {
    "capa_id": "CAPA-1",
    "check_date": "2026-10-10",
    "method": "torque audit",
    "result": "effective",
}


@pytest.fixture
def client(tmp_path: Path) -> Iterator[TestClient]:
    store = SqliteStore(tmp_path / "capa.db")
    app.dependency_overrides[get_store] = lambda: store
    yield TestClient(app)
    app.dependency_overrides.clear()
    store.close()


def test_lifecycle_to_closure_on_sqlite(client: TestClient) -> None:
    assert client.post("/nonconformance", json=NC_BODY).json()["id"] == "NC-1"
    assert (
        client.post(
            "/rca", json={"nonconformance_id": "NC-1", "method": "5-why", "steps": WHYS}
        ).status_code
        == 200
    )
    assert client.post("/capa", json=CAPA_BODY).json()["capa"]["id"] == "CAPA-1"
    assert client.post("/effectiveness-check", json=CHECK_BODY).status_code == 200

    evidence = client.post(
        "/close",
        json={
            "capa_id": "CAPA-1",
            "closed_date": "2026-10-12",
            "closed_by": "qa-mgr",
            "linked_requirement_ids": ["REQ-7"],
        },
    ).json()
    assert evidence["evidence_id"] == "CAPA-1" and evidence["nonconformance"]["status"] == "closed"
    reread = client.get("/closure/CAPA-1/evidence.json").json()
    assert {k: v for k, v in reread.items() if k != "generated_at"} == {
        k: v for k, v in evidence.items() if k != "generated_at"
    }
    pdf = client.get("/closure/CAPA-1/report.pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF") and b"820.100" in pdf.content
    assert client.get("/metrics").json()["closed"] == 1


def test_reopen_replaces_the_capa_on_sqlite(client: TestClient) -> None:
    client.post("/nonconformance", json=NC_BODY)
    client.post("/rca", json={"nonconformance_id": "NC-1", "method": "5-why"})
    client.post("/capa", json=CAPA_BODY)
    r = client.post("/effectiveness-check", json={**CHECK_BODY, "result": "not_effective"})
    assert r.json()["nonconformance"]["status"] == "capa_assigned"
    assert client.get("/metrics").json()["reopened"] == 1

    revised = client.post("/capa", json={**CAPA_BODY, "action_description": "poka-yoke driver"})
    assert revised.json()["capa"]["id"] == "CAPA-2"
    detail = client.get("/nonconformance/NC-1").json()
    assert detail["capa"]["id"] == "CAPA-2" and detail["checks"][0]["result"] == "pending"
    assert client.get("/closure/CAPA-1/report.pdf").status_code == 404  # old CAPA is gone


def test_records_outlive_the_process(tmp_path: Path) -> None:
    first = SqliteStore(tmp_path / "capa.db")
    app.dependency_overrides[get_store] = lambda: first
    TestClient(app).post("/nonconformance", json=NC_BODY)
    app.dependency_overrides.clear()
    first.close()

    second = SqliteStore(tmp_path / "capa.db")
    app.dependency_overrides[get_store] = lambda: second
    assert [n["id"] for n in TestClient(app).get("/nonconformances").json()] == ["NC-1"]
    app.dependency_overrides.clear()
    second.close()


def test_get_store_defaults_to_sqlite(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CAPA_DB_PATH", str(tmp_path / "default.db"))
    get_store.cache_clear()
    store = get_store()
    assert isinstance(store, SqliteStore) and store.path.exists()
    store.close()
    get_store.cache_clear()
