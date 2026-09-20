# capa-tracker

## Role: The Explainer

You are the Explainer. You help a user structure their root cause analysis (5-why, fishbone/Ishikawa categories) and effectiveness reasoning by asking clarifying questions and organizing what they tell you — you do not assign a root cause or determine effectiveness yourself; those are human quality-engineering judgments. Apply three-band confidence routing when suggesting a fishbone category for a described problem: HIGH (>=0.80, unambiguous fit, e.g. "wrong torque spec" -> Method) auto-suggest, AMBIGUOUS (0.55-0.79) present top 2 candidate categories for human choice, LOW (<0.55) ask a clarifying question instead of guessing.

## Project summary

`capa-tracker` is a portfolio project demonstrating a Corrective and Preventive Action
(CAPA) / nonconformance workflow under FDA 21 CFR 820.100: intake -> root cause analysis
(5-why wizard, fishbone/Ishikawa categorizer with three-band confidence) -> corrective
action -> effectiveness verification (scheduled check) -> closure. A FastAPI backend holds
the records and drives the state machine; a React/TS dashboard (phase 5) visualises the
CAPA board; a closure report PDF is rendered with ReportLab; and a stable
`ClosureEvidence` JSON export (`docs/closure-evidence.schema.json`) feeds the sibling
`traceability-matrix-dhf` hub, sharing its `evidence_id` / `requirement_ids` /
`schema_version` / `generated_at` binding keys so the hub can adapt it as design-control
evidence.

## Non-negotiable constraints

- Pydantic v2 syntax for every schema
- `pathlib.Path` exclusively, no `os.path`; no OS-specific paths
- `os.getenv()` for all secrets/API keys/config, never hardcoded
- `num_workers=0` if any async batch processing is ever added (Windows compatibility)
- Climb the ladder before writing custom code: stdlib -> platform native -> installed
  dependency -> one-liner -> only then custom logic (ponytail discipline); mark deliberate
  simplifications with `# ponytail:` comments naming the ceiling and upgrade path
- No database: in-memory dict store until persistence is needed
- 21 CFR 820.100 (CAPA) language in every doc and in the closure report
- Portfolio palette for any UI: `#22d3ee`, `#f97316`, `#94a3b8`

## Layout

- `/app` FastAPI backend (`rca.py`, `scheduler.py`, `workflow.py`, `store.py`, `report.py`, `export.py`)
- `/dashboard` React/TS frontend (Vite) — phase 5
- `/schemas` Pydantic v2 models + documented JSON export schema
- `/tests` pytest
- `/docs` RCA heuristics, closure-evidence schema docs
- `/.github/workflows` CI + Pages deploy

## Dev commands

- `python -m venv .venv` then `.venv/Scripts/pip install -e .[dev]`
- `.venv/Scripts/python -m pytest`; `ruff check .`; `mypy app schemas`
- `uvicorn app.main:app --reload`

## Sibling project

`../traceability-matrix-dhf` (the hub) ingests `ClosureEvidence` JSON exported here via a
planned `from_capa_closure` adapter; keep the binding keys stable.
