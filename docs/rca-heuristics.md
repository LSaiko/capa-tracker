# RCA heuristics (Explainer role)

`app/rca.py` helps a quality engineer *structure* a root cause analysis under
21 CFR 820.100(a)(2) ("investigating the cause of nonconformities relating to product,
processes, and the quality system"). It does **not** assign a root cause or judge
effectiveness: those remain human quality-engineering decisions, recorded in
`RootCauseAnalysis.root_cause_text` and `EffectivenessCheck.result`.

## 5-why wizard

- `next_why_prompt(steps, problem)` produces `Why did <last answer> happen?` (or chains off the
  problem statement for the first step).
- `looks_like_root_cause(answer)` is a keyword heuristic, not a claim of certainty:
  - reads as **root/systemic** when the answer contains `no procedure`, `not defined`,
    `not trained`, `no requirement`, `not specified`, `missing`, `never`, `lacks`, `absence of`;
  - reads as **symptom** when it contains `because it broke`, `failed`, `was wrong`, `defective`;
  - otherwise "no systemic marker found; ask why again".

  The flag only suggests the chain may be deep enough. The QE decides when to stop.

## Fishbone (Ishikawa 6M) categorizer

`suggest_category(description)` scores the six categories by a keyword-weight table
(3 = strong phrase such as `torque spec`, 2 = typical, 1 = weak/generic such as `operator`),
matched as whole words on the lower-cased description.

```
confidence = (top_score / sum_of_all_scores) * min(1, top_score / 3)
```

Three-band routing (`band_for`):

| Band | Threshold | Behaviour |
|---|---|---|
| HIGH | >= 0.80 | `suggested` set, auto-suggest |
| AMBIGUOUS | 0.55 - 0.79 | top 2 `candidates` presented for human choice, `suggested` None |
| LOW | < 0.55 | `prompt` holds a clarifying question; nothing is asserted |

Worked examples: "Operator used wrong torque spec on the work instruction" scores Method 7 vs
Manpower 1 (0.875, HIGH); "gauge calibration was overdue and the fixture was worn" scores
Measurement 5 vs Machine 3 (0.625, AMBIGUOUS); "part came back bad" has no hits (0.0, LOW).

Ceiling: exact vocabulary, no synonyms or negation handling. Upgrade path: embeddings or an
LLM classifier behind the same `CategorySuggestion` contract (see the `# ponytail:` comment).
