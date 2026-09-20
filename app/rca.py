"""Explainer helpers: 5-why prompting and fishbone (Ishikawa) category suggestion.

Everything here is a keyword HEURISTIC that organises what the user says. It never decides the
root cause: `looks_like_root_cause` only signals that an answer *reads* systemic, and
`suggest_category` routes by three-band confidence (HIGH suggest / AMBIGUOUS offer two /
LOW ask). The human quality engineer makes the final call. See docs/rca-heuristics.md.
"""

from __future__ import annotations

import re

from pydantic import Field

from schemas import ConfidenceBand, FishboneCategory, WhyStep, band_for
from schemas.models import _Strict

# Answers that name a missing/undefined system element read as root (systemic) causes;
# answers that just restate the failure read as symptoms.
ROOT_MARKERS = (
    "no procedure",
    "not defined",
    "not trained",
    "no requirement",
    "not specified",
    "missing",
    "never",
    "lacks",
    "absence of",
)
SYMPTOM_MARKERS = ("because it broke", "failed", "was wrong", "defective")


def next_why_prompt(steps: list[WhyStep], problem: str = "the nonconformance") -> str:
    """Next wizard prompt: chains off the last answer, or the problem statement when empty."""
    last = steps[-1].answer.strip().rstrip(".") if steps else problem
    return f"Why did {last} happen?"


def looks_like_root_cause(answer: str) -> tuple[bool, str]:
    """Heuristic only: (reads_systemic, reason). The QE decides whether the chain is done."""
    text = answer.lower()
    for marker in ROOT_MARKERS:
        if marker in text:
            return True, f"'{marker}' names a missing system element (reads as root cause)"
    for marker in SYMPTOM_MARKERS:
        if marker in text:
            return False, f"'{marker}' restates the failure (reads as symptom); ask why again"
    return False, "no systemic marker found; ask why again"


# ponytail: keyword-weight table (3 = strong/unambiguous phrase, 2 = typical, 1 = weak/generic).
# Ceiling: whole-word hits on a hand-picked vocabulary, no synonyms or negation.
# Upgrade path: embeddings or an LLM classifier behind the same CategorySuggestion contract.
STRONG = 3
KEYWORDS: dict[FishboneCategory, dict[str, int]] = {
    FishboneCategory.METHOD: {
        "torque spec": 3, "work instruction": 3, "sop": 3, "procedure": 2,
        "process step": 2, "specification": 1, "spec": 1,
    },
    FishboneCategory.MACHINE: {
        "fixture": 3, "tool wear": 3, "spindle": 3, "calibration drift": 2,
        "machine": 2, "press": 2, "equipment": 1,
    },
    FishboneCategory.MATERIAL: {
        "supplier": 3, "raw material": 3, "contamination": 3, "lot": 2,
        "component": 2, "batch": 2,
    },
    FishboneCategory.MANPOWER: {
        "training": 3, "trained": 3, "fatigue": 3, "handover": 3, "shift": 2, "operator": 1,
    },
    FishboneCategory.MEASUREMENT: {
        "gauge": 3, "r&r": 3, "cmm": 3, "calibration": 2, "inspection": 2, "measurement": 2,
    },
    FishboneCategory.ENVIRONMENT: {
        "humidity": 3, "temperature": 3, "esd": 3, "lighting": 3, "vibration": 3,
        "cleanroom": 3,
    },
}  # fmt: skip

CLARIFY = (
    "I can't tell which category this is yet. Was the problem tied to how the work is done "
    "(Method), the equipment (Machine), the parts (Material), the people (Manpower), how it "
    "was measured (Measurement), or the surroundings (Environment)?"
)


class CategorySuggestion(_Strict):
    candidates: list[tuple[FishboneCategory, float]] = Field(default_factory=list)  # top 2
    confidence: float = Field(ge=0.0, le=1.0)
    band: ConfidenceBand
    suggested: FishboneCategory | None = None  # only when HIGH
    prompt: str | None = None  # clarifying question, only when LOW


def suggest_category(description: str) -> CategorySuggestion:
    """Score each 6M category by keyword weight; route the top hit through three bands.

    confidence = (top / sum of all category scores) * min(1, top / STRONG). The second factor
    keeps a lone weak hit (e.g. just "operator") from looking certain.
    """
    text = description.lower()
    scores = {
        cat: sum(w for kw, w in table.items() if re.search(rf"\b{re.escape(kw)}\b", text))
        for cat, table in KEYWORDS.items()
    }
    ranked = sorted(((c, s) for c, s in scores.items() if s), key=lambda cs: -cs[1])[:2]
    total = sum(scores.values())
    top = ranked[0][1] if ranked else 0
    confidence = round((top / total) * min(1.0, top / STRONG), 3) if total else 0.0
    band = band_for(confidence)
    return CategorySuggestion(
        candidates=[(c, round(s / total, 3)) for c, s in ranked],
        confidence=confidence,
        band=band,
        suggested=ranked[0][0] if band is ConfidenceBand.HIGH else None,
        prompt=CLARIFY if band is ConfidenceBand.LOW else None,
    )


__all__ = ["CategorySuggestion", "looks_like_root_cause", "next_why_prompt", "suggest_category"]
