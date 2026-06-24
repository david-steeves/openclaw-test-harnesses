"""
harness/verdict.py

Shared verdict dataclass used by every analyst across both review teams. Keeps
the analyst module shape stable while letting the composition engine consume a
typed structure (richer than the bench's "pass" | "block" string contract).

The perf adapter (harness/perf/runner.py) coerces this to the bench string
contract when delegating to the openclaw-pipeline-bench substrate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# Verdict ordering. The composition rule (policies/README.md) is:
#   final_verdict = max(verdicts) under PASS < WARN < BLOCK
VERDICT_ORDER = {"pass": 0, "warn": 1, "block": 2}


@dataclass
class AnalystVerdict:
    analyst_id: str
    verdict: str        # "pass" | "warn" | "block"
    rule_id: str
    layer: str          # "system" | "scoped"
    matched: bool
    notes: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)

    def rank(self) -> int:
        return VERDICT_ORDER[self.verdict]


def max_verdict(verdicts: list[AnalystVerdict]) -> str:
    """Returns the highest-severity verdict string from a list, or 'pass' if empty."""
    if not verdicts:
        return "pass"
    return max(verdicts, key=lambda v: v.rank()).verdict
