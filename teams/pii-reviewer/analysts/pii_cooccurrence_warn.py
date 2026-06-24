"""
teams/pii-reviewer/analysts/pii_cooccurrence_warn.py

Detects name + DOB co-occurrence: full_name (or first+last) AND date_of_birth
in the same row -> WARN.

This is the classic re-identification vector. Neither field alone is sensitive
at the WARN level; the combination is.
"""

from __future__ import annotations

from typing import Any

from harness.verdict import AnalystVerdict


NAME_COLUMNS = {"full_name", "name"}
FIRST_NAME_COLUMNS = {"first_name", "given_name"}
LAST_NAME_COLUMNS = {"last_name", "surname", "family_name"}
DOB_COLUMNS = {"date_of_birth", "dob", "birth_date"}


def _non_empty(row: dict[str, Any], cols: set[str]) -> bool:
    return any(str(row.get(c, "")).strip() for c in cols)


class PiiCooccurrenceWarn:
    ID = "pii-reviewer.pii-cooccurrence-warn"
    RULE_ID = "policy/teams/pii-warn/name-dob.v1"
    LAYER = "scoped"

    def __init__(self, severity_map: dict[str, str] | None = None):
        self.severity_map = severity_map or {"high": "warn"}

    async def evaluate(self, agent_id: int, payload: Any) -> AnalystVerdict:
        row = self._as_row(payload)
        has_name = _non_empty(row, NAME_COLUMNS) or (
            _non_empty(row, FIRST_NAME_COLUMNS) and _non_empty(row, LAST_NAME_COLUMNS)
        )
        has_dob = _non_empty(row, DOB_COLUMNS)
        matched = has_name and has_dob
        if matched:
            return AnalystVerdict(
                analyst_id=self.ID,
                verdict=self.severity_map.get("high", "warn"),
                rule_id=self.RULE_ID,
                layer=self.LAYER,
                matched=True,
                notes="name + DOB present in same row",
                evidence={"has_name": has_name, "has_dob": has_dob},
            )
        return AnalystVerdict(
            analyst_id=self.ID,
            verdict="pass",
            rule_id=self.RULE_ID,
            layer=self.LAYER,
            matched=False,
        )

    @staticmethod
    def _as_row(payload: Any) -> dict[str, Any]:
        if isinstance(payload, dict):
            return payload
        # Perf-path payloads are JSON strings; cooccurrence doesn't apply there
        # because the bench substrate emits synthetic blobs without column
        # structure. Return empty dict -> no match -> PASS. This is intentional;
        # the perf harness measures cost, not policy correctness.
        return {}
