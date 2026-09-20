# ClosureEvidence JSON export

`docs/closure-evidence.schema.json` is generated from `schemas.ClosureEvidence` with
`python -m app.export` in Pydantic **serialization** mode (so the derived `rca.confidence_band`
appears as an emitted field); `tests/test_workflow.py` asserts the file is in sync with the model.
Both the closure report PDF and this JSON are rendered from the same
`build_closure_bundle(store, nc_id)` result, so they cannot disagree.

## Top-level fields

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | const `"1.0"` | Bump on any breaking change to this contract |
| `generated_at` | date-time | When the bundle was assembled |
| `source` | const `"capa-tracker"` | Producing system |
| `evidence_id` | `CAPA-\d+` | The closed CAPA id (`closure.capa_id`) |
| `requirement_ids` | string[] | `closure.linked_requirement_ids`: DHF requirement ids this closure evidences |
| `nonconformance` | object | Intake record (id, description, source, severity, detected_date, status) |
| `rca` | object | Method, 5-why chain or fishbone entries, Explainer suggestion + band, human root cause |
| `capa` | object | Corrective action (id, description, owner, due_date, status) |
| `effectiveness_check` | object | Verification per 820.100(a)(4): date, method, result, evidence_uri |
| `closure` | object | closed_date, closed_by, linked_requirement_ids |
| `cfr_citation` | const `"21 CFR 820.100"` | Regulatory basis |

All objects are `additionalProperties: false`.

## Linkage to the traceability-matrix-dhf hub

The sibling hub (`../traceability-matrix-dhf`, `schemas/validation-evidence.schema.json`)
ingests `ValidationEvidence` from `ml-samd-validator` keyed by `evidence_id` +
`requirement_ids`, with `schema_version` and `generated_at` alongside. `ClosureEvidence` uses
the **same four binding keys with the same names and types** so the hub can add a
`from_capa_closure` adapter that maps a closed CAPA onto its requirements as design-control
evidence (21 CFR 820.30 <- 820.100 linkage).

Status: the adapter is **planned, not yet built**. Until it lands, this file is the contract
the hub will validate against; keep the binding keys stable and bump `schema_version` if they
change.
