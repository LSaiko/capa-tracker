"""SQLite implementation of `CapaStore` on stdlib `sqlite3` (no ORM, no migrations).

One table per record type, keyed exactly as the in-memory dicts were, with the Pydantic
JSON in a TEXT column.

# ponytail: the record JSON is stored whole rather than shredded into columns, so nothing
# can query *inside* it (an RCA's `steps`, a closure's `linked_requirement_ids`); the only
# field lifted out is `capas.nonconformance_id`, because `capa_for` needs it. Shred a field
# into its own column the day a report has to filter or aggregate on it.
# ponytail: no migrations framework — `CREATE TABLE IF NOT EXISTS` on construction is the
# whole schema story; a column change means writing the ALTER by hand.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from pydantic import BaseModel

from app.store import CapaStore
from schemas import (
    ClosureRecord,
    CorrectiveAction,
    EffectivenessCheck,
    Nonconformance,
    RootCauseAnalysis,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS nonconformances (id TEXT PRIMARY KEY, json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS rcas (nonconformance_id TEXT PRIMARY KEY, json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS capas (
    id TEXT PRIMARY KEY, nonconformance_id TEXT NOT NULL, json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS checks (capa_id TEXT PRIMARY KEY, json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS closures (capa_id TEXT PRIMARY KEY, json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value INTEGER NOT NULL);
INSERT OR IGNORE INTO meta (key, value) VALUES ('reopens', 0);
"""


class SqliteStore(CapaStore):
    """Persistent store; `KeyError` on unknown ids, same as the in-memory `Store`."""

    def __init__(self, path: Path | str | None = None) -> None:
        self.path = Path(os.getenv("CAPA_DB_PATH", "capa.db")) if path is None else Path(path)
        # ponytail: one shared connection for a single-process FastAPI app; the upgrade path
        # is a per-request connection (or a pool) once this runs multi-process or writes
        # start contending.
        self.conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self.conn.executescript(SCHEMA)

    def close(self) -> None:
        self.conn.close()

    def _get[M: BaseModel](self, model: type[M], sql: str, key: str) -> M:
        row = self.conn.execute(sql, (key,)).fetchone()
        if row is None:
            raise KeyError(key)
        return model.model_validate_json(row[0])

    def _list[M: BaseModel](self, model: type[M], sql: str) -> list[M]:
        return [model.model_validate_json(row[0]) for row in self.conn.execute(sql)]

    def _put(self, sql: str, *params: str) -> None:
        with self.conn:  # commit
            self.conn.execute(sql, params)

    def get_nc(self, nc_id: str) -> Nonconformance:
        return self._get(Nonconformance, "SELECT json FROM nonconformances WHERE id = ?", nc_id)

    def put_nc(self, nc: Nonconformance) -> None:
        self._put(
            "INSERT OR REPLACE INTO nonconformances (id, json) VALUES (?, ?)",
            nc.id,
            nc.model_dump_json(),
        )

    def list_ncs(self) -> list[Nonconformance]:
        return self._list(Nonconformance, "SELECT json FROM nonconformances ORDER BY rowid")

    def get_rca(self, nc_id: str) -> RootCauseAnalysis:
        return self._get(
            RootCauseAnalysis, "SELECT json FROM rcas WHERE nonconformance_id = ?", nc_id
        )

    def put_rca(self, rca: RootCauseAnalysis) -> None:
        self._put(
            "INSERT OR REPLACE INTO rcas (nonconformance_id, json) VALUES (?, ?)",
            rca.nonconformance_id,
            rca.model_dump_json(),
        )

    def get_capa(self, capa_id: str) -> CorrectiveAction:
        return self._get(CorrectiveAction, "SELECT json FROM capas WHERE id = ?", capa_id)

    def put_capa(self, capa: CorrectiveAction) -> None:
        self._put(
            "INSERT OR REPLACE INTO capas (id, nonconformance_id, json) VALUES (?, ?, ?)",
            capa.id,
            capa.nonconformance_id,
            capa.model_dump_json(),
        )

    def list_capas(self) -> list[CorrectiveAction]:
        return self._list(CorrectiveAction, "SELECT json FROM capas ORDER BY rowid")

    def capa_for(self, nc_id: str) -> CorrectiveAction:
        # ponytail: one CAPA per NC; a list per NC is the upgrade when multi-action plans arrive.
        row = self.conn.execute(
            "SELECT json FROM capas WHERE nonconformance_id = ? ORDER BY rowid", (nc_id,)
        ).fetchone()
        if row is None:
            raise KeyError(f"no CAPA for {nc_id}")
        return CorrectiveAction.model_validate_json(row[0])

    def drop_capa(self, capa_id: str) -> None:
        """Reopen path: the replaced CAPA takes its scheduled check with it."""
        with self.conn:
            self.conn.execute("DELETE FROM capas WHERE id = ?", (capa_id,))
            self.conn.execute("DELETE FROM checks WHERE capa_id = ?", (capa_id,))

    def get_check(self, capa_id: str) -> EffectivenessCheck:
        return self._get(EffectivenessCheck, "SELECT json FROM checks WHERE capa_id = ?", capa_id)

    def put_check(self, check: EffectivenessCheck) -> None:
        self._put(
            "INSERT OR REPLACE INTO checks (capa_id, json) VALUES (?, ?)",
            check.capa_id,
            check.model_dump_json(),
        )

    def get_closure(self, capa_id: str) -> ClosureRecord:
        return self._get(ClosureRecord, "SELECT json FROM closures WHERE capa_id = ?", capa_id)

    def put_closure(self, closure: ClosureRecord) -> None:
        self._put(
            "INSERT OR REPLACE INTO closures (capa_id, json) VALUES (?, ?)",
            closure.capa_id,
            closure.model_dump_json(),
        )

    def list_closures(self) -> list[ClosureRecord]:
        return self._list(ClosureRecord, "SELECT json FROM closures ORDER BY rowid")

    def bump_reopens(self) -> None:
        with self.conn:
            self.conn.execute("UPDATE meta SET value = value + 1 WHERE key = 'reopens'")

    def reopens(self) -> int:
        return int(self.conn.execute("SELECT value FROM meta WHERE key = 'reopens'").fetchone()[0])
