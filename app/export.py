"""ClosureEvidence bundle: the single source both the PDF and the JSON export render from."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from app.store import Store
from schemas import ClosureEvidence

SCHEMA_FILE = Path(__file__).resolve().parents[1] / "docs" / "closure-evidence.schema.json"


def build_closure_bundle(store: Store, nc_id: str) -> ClosureEvidence:
    """Assemble NC + RCA + CAPA + check + closure into one ClosureEvidence (KeyError if missing)."""
    nc = store.nonconformances[nc_id]
    capa = store.capa_for(nc_id)
    closure = store.closures[capa.id]
    return ClosureEvidence(
        generated_at=datetime.now(UTC),
        evidence_id=closure.capa_id,
        requirement_ids=list(closure.linked_requirement_ids),
        nonconformance=nc,
        rca=store.rcas[nc_id],
        capa=capa,
        effectiveness_check=store.checks[capa.id],
        closure=closure,
    )


def export_json(bundle: ClosureEvidence, out: Path) -> Path:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(bundle.model_dump_json(indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":  # python -m app.export -> refresh docs/closure-evidence.schema.json
    SCHEMA_FILE.write_text(
        json.dumps(ClosureEvidence.model_json_schema(mode="serialization"), indent=2) + "\n",
        encoding="utf-8",
    )
    print(SCHEMA_FILE)
