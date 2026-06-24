"""
teams/phi-reviewer/analysts/patient_id_warn.py

Detects patient_id + birth_date + city co-occurrence (re-identification
vector) -> WARN. Scoped to phi-reviewer.

Not suppressible by clarifications. Re-identification vectors are too
high-stakes to allow operator-asserted exemption at the scoped layer; the
operator should instead correct the data-class declaration if this is
misrouted.
"""

from __future__ import annotations

from typing import Any

from harness.verdict import AnalystVerdict


REQUIRED_COLUMNS = ["patient_id", "birth_date", "city"]


class PatientIdWarn:
    ID = "phi-reviewer.patient-id-warn"
    RULE_ID = "policy/teams/phi-block/reid.v1"
    LAYER = "scoped"

    def __init__(self, severity_map: dict[str, str] | None = None):
        self.severity_map = severity_map or {"high": "warn"}

    async def evaluate(self, agent_id: int, payload: Any,
                       clarifications: dict[str, str] | None = None) -> AnalystVerdict:
        row = payload if isinstance(payload, dict) else {}
        all_present = all(str(row.get(c, "")).strip() for c in REQUIRED_COLUMNS)
        if all_present:
            return AnalystVerdict(
                analyst_id=self.ID,
                verdict=self.severity_map.get("high", "warn"),
                rule_id=self.RULE_ID,
                layer=self.LAYER,
                matched=True,
                notes="patient_id + birth_date + city all present (re-identification vector)",
                evidence={"required_columns": REQUIRED_COLUMNS},
            )
        return AnalystVerdict(
            analyst_id=self.ID,
            verdict="pass",
            rule_id=self.RULE_ID,
            layer=self.LAYER,
            matched=False,
        )
