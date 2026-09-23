"""FastAPI surface for the Explainer: CAPA records in, closure evidence out.

# ponytail: one module-level Store, CORS allow-all (Vite dev server), no auth; the upgrade path
# is a Store dependency + SQLite once persistence or multi-user is needed.
"""

from __future__ import annotations

import os
import tempfile
from collections import Counter
from collections.abc import Callable
from datetime import date
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import Field

from app.export import build_closure_bundle
from app.rca import CategorySuggestion, looks_like_root_cause, suggest_category
from app.report import render_closure_report
from app.scheduler import schedule_effectiveness_check
from app.store import store
from app.workflow import InvalidTransition, apply_effectiveness, close, transition
from schemas import (
    ClosureEvidence,
    ClosureRecord,
    CorrectiveAction,
    EffectivenessCheck,
    NcStatus,
    Nonconformance,
    RootCauseAnalysis,
    WhyStep,
)
from schemas.models import _Strict

app = FastAPI(title="capa-tracker")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("ALLOWED_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(InvalidTransition)
def _conflict(_: Request, exc: InvalidTransition) -> JSONResponse:
    return JSONResponse({"detail": str(exc)}, status_code=409)


@app.exception_handler(KeyError)
def _not_found(_: Request, exc: KeyError) -> JSONResponse:
    # ponytail: the store raises KeyError for unknown ids; one handler beats a lookup helper.
    return JSONResponse({"detail": f"not found: {exc}"}, status_code=404)


def _next_id(prefix: str, existing: list[str]) -> str:
    return f"{prefix}-{1 + max((int(k.rsplit('-', 1)[1]) for k in existing), default=0)}"


def _opt[T](get: Callable[[str], T], key: str) -> T | None:
    """Optional read: the store only does KeyError, and some records are legitimately absent."""
    try:
        return get(key)
    except KeyError:
        return None


class NonconformanceIn(_Strict):
    description: str = Field(min_length=1)
    source: Literal["audit", "complaint", "internal", "supplier"]
    severity: Literal["minor", "major", "critical"]
    detected_date: date


class CorrectiveActionIn(_Strict):
    nonconformance_id: str = Field(pattern=r"^NC-\d+$")
    action_description: str = Field(min_length=1)
    owner: str = Field(min_length=1)
    due_date: date


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/nonconformance")
def create_nonconformance(body: NonconformanceIn) -> Nonconformance:
    nc = Nonconformance(id=_next_id("NC", [n.id for n in store.list_ncs()]), **body.model_dump())
    store.put_nc(nc)
    return nc


@app.get("/nonconformances")
def list_nonconformances() -> list[Nonconformance]:
    return store.list_ncs()


@app.get("/nonconformance/{nc_id}")
def get_nonconformance(nc_id: str) -> dict[str, Any]:
    nc = store.get_nc(nc_id)
    rca = _opt(store.get_rca, nc_id)
    capa = _opt(store.capa_for, nc_id)
    check = _opt(store.get_check, capa.id) if capa else None
    whys = [s for s in (rca.steps if rca else []) if isinstance(s, WhyStep)]
    return {
        "nonconformance": nc,
        "rca": rca,
        # Heuristic per 5-why answer: does it read systemic? Advisory only (docs/rca-heuristics).
        "why_flags": [
            dict(zip(("reads_systemic", "reason"), looks_like_root_cause(s.answer), strict=True))
            for s in whys
        ],
        "capa": capa,
        "checks": [check] if check else [],
        "closure": _opt(store.get_closure, capa.id) if capa else None,
    }


@app.get("/rca/suggest")
def rca_suggest(description: str) -> CategorySuggestion:
    return suggest_category(description)


@app.post("/rca")
def create_rca(body: RootCauseAnalysis) -> dict[str, Any]:
    nc = store.get_nc(body.nonconformance_id)
    suggestion = suggest_category(nc.description)
    if body.suggested_category is None and body.confidence is None:
        # HIGH -> suggested filled; AMBIGUOUS/LOW -> suggested stays None, confidence kept.
        body = body.model_copy(
            update={"confidence": suggestion.confidence, "suggested_category": suggestion.suggested}
        )
    store.put_nc(transition(nc, NcStatus.RCA_IN_PROGRESS))
    store.put_rca(body)
    return {"rca": body, "suggestion": suggestion}


@app.post("/capa")
def create_capa(body: CorrectiveActionIn) -> dict[str, Any]:
    nc = store.get_nc(body.nonconformance_id)
    capa = CorrectiveAction(
        id=_next_id("CAPA", [c.id for c in store.list_capas()]), **body.model_dump()
    )
    if nc.status is NcStatus.CAPA_ASSIGNED:
        # Reopened NC: the revised CAPA replaces the one found not effective (one CAPA per NC).
        store.drop_capa(store.capa_for(nc.id).id)
    else:
        nc = transition(nc, NcStatus.CAPA_ASSIGNED)
    check = schedule_effectiveness_check(capa)
    store.put_capa(capa)
    store.put_check(check)
    store.put_nc(transition(nc, NcStatus.EFFECTIVENESS_PENDING))
    return {"capa": capa, "scheduled_check": check}


@app.post("/effectiveness-check")
def record_effectiveness(body: EffectivenessCheck) -> dict[str, Any]:
    capa = store.get_capa(body.capa_id)
    nc = apply_effectiveness(store.get_nc(capa.nonconformance_id), body)
    if body.result == "not_effective":
        store.bump_reopens()
    store.put_check(body)  # replaces the scheduled pending check
    store.put_nc(nc)
    return {"nonconformance": nc, "check": body}


@app.post("/close")
def close_capa(body: ClosureRecord) -> ClosureEvidence:
    capa = store.get_capa(body.capa_id)
    nc = store.get_nc(capa.nonconformance_id)
    store.put_nc(close(nc, store.get_check(capa.id), body))
    store.put_closure(body)
    return build_closure_bundle(store, nc.id)


@app.get("/closure/{capa_id}/evidence.json")
def closure_evidence(capa_id: str) -> ClosureEvidence:
    return build_closure_bundle(store, store.get_capa(capa_id).nonconformance_id)


@app.get("/closure/{capa_id}/report.pdf")
def closure_report(capa_id: str) -> Response:
    bundle = closure_evidence(capa_id)
    out = render_closure_report(bundle, Path(tempfile.gettempdir()) / f"{capa_id}-closure.pdf")
    return Response(out.read_bytes(), media_type="application/pdf")


@app.get("/open-capas")
def open_capas() -> list[dict[str, Any]]:
    out = []
    for capa in store.list_capas():
        nc = store.get_nc(capa.nonconformance_id)
        if nc.status is not NcStatus.CLOSED:
            chk = _opt(store.get_check, capa.id)
            pending = chk if chk and chk.result == "pending" else None
            out.append({"nonconformance": nc, "capa": capa, "pending_check": pending})
    return out


def _by_month(dates: list[date]) -> dict[str, int]:
    return dict(sorted(Counter(d.strftime("%Y-%m") for d in dates).items()))


@app.get("/metrics")
def metrics() -> dict[str, Any]:
    ncs = store.list_ncs()
    by_status = Counter(nc.status.value for nc in ncs)
    return {
        "open": sum(1 for nc in ncs if nc.status is not NcStatus.CLOSED),
        "closed": by_status[NcStatus.CLOSED.value],
        "by_status": {s.value: by_status[s.value] for s in NcStatus},
        "opened_by_month": _by_month([nc.detected_date for nc in ncs]),
        "closed_by_month": _by_month([c.closed_date for c in store.list_closures()]),
        "reopened": store.reopens(),
    }
