from pathlib import Path

import pytest
from test_schemas import CAPA, CHECK, CLOSURE, NC, RCA_FISH, RCA_WHY

from app.sqlite_store import SqliteStore
from app.store import CapaStore
from schemas import NcStatus


@pytest.fixture
def store() -> SqliteStore:
    return SqliteStore(":memory:")


def test_round_trip_every_record_type(store: SqliteStore) -> None:
    store.put_nc(NC)
    store.put_rca(RCA_WHY)
    store.put_capa(CAPA)
    store.put_check(CHECK)
    store.put_closure(CLOSURE)
    assert store.get_nc(NC.id) == NC
    assert store.get_rca(RCA_WHY.nonconformance_id) == RCA_WHY
    assert store.get_capa(CAPA.id) == CAPA
    assert store.get_check(CHECK.capa_id) == CHECK
    assert store.get_closure(CLOSURE.capa_id) == CLOSURE
    assert store.list_ncs() == [NC] and store.list_capas() == [CAPA]
    assert store.list_closures() == [CLOSURE]


def test_fishbone_steps_survive_the_json_column(store: SqliteStore) -> None:
    store.put_rca(RCA_FISH)
    assert store.get_rca(RCA_FISH.nonconformance_id) == RCA_FISH


def test_put_replaces_in_place(store: SqliteStore) -> None:
    store.put_nc(NC)
    closed = NC.model_copy(update={"status": NcStatus.CLOSED})
    store.put_nc(closed)
    assert store.list_ncs() == [closed]


def test_missing_ids_raise_key_error(store: SqliteStore) -> None:
    for get in (store.get_nc, store.get_rca, store.get_capa, store.get_check, store.get_closure):
        with pytest.raises(KeyError):
            get("NC-99")
    with pytest.raises(KeyError, match="no CAPA"):
        store.capa_for("NC-99")


def test_capa_for_hit(store: SqliteStore) -> None:
    store.put_capa(CAPA)
    assert store.capa_for(CAPA.nonconformance_id) == CAPA


def test_reopen_replaces_the_capa_and_drops_its_check(store: SqliteStore) -> None:
    """The documented ceiling: one CAPA per NC, the revised one replaces the ineffective one."""
    store.put_capa(CAPA)
    store.put_check(CHECK)
    revised = CAPA.model_copy(update={"id": "CAPA-2", "action_description": "poka-yoke driver"})
    store.drop_capa(CAPA.id)
    store.put_capa(revised)
    assert store.capa_for(CAPA.nonconformance_id) == revised
    assert store.list_capas() == [revised]
    with pytest.raises(KeyError):
        store.get_capa(CAPA.id)
    with pytest.raises(KeyError):
        store.get_check(CAPA.id)  # old check dropped with the CAPA it verified


def test_reopens_counter(store: SqliteStore) -> None:
    assert store.reopens() == 0
    store.bump_reopens()
    store.bump_reopens()
    assert store.reopens() == 2


def test_data_survives_close_and_reopen(tmp_path: Path) -> None:
    db = tmp_path / "capa.db"
    first = SqliteStore(db)
    first.put_nc(NC)
    first.put_rca(RCA_WHY)
    first.put_capa(CAPA)
    first.put_check(CHECK)
    first.put_closure(CLOSURE)
    first.bump_reopens()
    first.close()

    second: CapaStore = SqliteStore(db)
    assert second.get_nc(NC.id) == NC
    assert second.get_rca(RCA_WHY.nonconformance_id) == RCA_WHY
    assert second.capa_for(NC.id) == CAPA
    assert second.get_check(CHECK.capa_id) == CHECK
    assert second.get_closure(CLOSURE.capa_id) == CLOSURE
    assert second.reopens() == 1


def test_path_defaults_to_env_var(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CAPA_DB_PATH", str(tmp_path / "from-env.db"))
    store = SqliteStore()
    assert store.path == tmp_path / "from-env.db" and store.path.exists()
    store.close()
