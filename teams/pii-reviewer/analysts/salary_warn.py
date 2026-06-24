"""
teams/pii-reviewer/analysts/salary_warn.py

Detects salary (or base_pay / total_compensation) column with a non-empty
value. Emits WARN. Scoped to pii-reviewer.
"""

from __future__ import annotations

from typing import Any

from harness.verdict import AnalystVerdict


SALARY_COLUMNS = {"salary", "base_pay", "total_compensation", "annual_salary"}


class SalaryWarn:
    ID = "pii-reviewer.salary-warn"
    RULE_ID = "policy/teams/pii-warn/salary.v1"
    LAYER = "scoped"

    def __init__(self, severity_map: dict[str, str] | None = None):
        self.severity_map = severity_map or {"high": "warn"}

    async def evaluate(self, agent_id: int, payload: Any) -> AnalystVerdict:
        row = payload if isinstance(payload, dict) else {}
        matched = any(str(row.get(c, "")).strip() for c in SALARY_COLUMNS)
        if matched:
            return AnalystVerdict(
                analyst_id=self.ID,
                verdict=self.severity_map.get("high", "warn"),
                rule_id=self.RULE_ID,
                layer=self.LAYER,
                matched=True,
                notes="salary column non-empty",
            )
        return AnalystVerdict(
            analyst_id=self.ID,
            verdict="pass",
            rule_id=self.RULE_ID,
            layer=self.LAYER,
            matched=False,
        )
