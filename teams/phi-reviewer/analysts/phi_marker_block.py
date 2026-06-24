"""
teams/phi-reviewer/analysts/phi_marker_block.py

Detects presence of PHI markers (MRN or diagnosis_code columns non-empty) ->
BLOCK. Scoped to phi-reviewer.

Honors `clarifications.phi-detection == "no"` as an operator-asserted
exemption — recorded in evidence, not enforced. See
clarifying-prompts/README.md §"Why suppresses is dangerous".
"""

from __future__ import annotations

from typing import Any

from harness.verdict import AnalystVerdict


PHI_MARKER_COLUMNS = {
    "mrn",
    "medical_record",
    "medical_record_number",
    "diagnosis",
    "diagnosis_code",
}


class PhiMarkerBlock:
    ID = "phi-reviewer.phi-marker-block"
    RULE_ID = "policy/teams/phi-block/marker.v1"
    LAYER = "scoped"

    def __init__(self, severity_map: dict[str, str] | None = None):
        self.severity_map = severity_map or {"critical": "block"}

    async def evaluate(self, agent_id: int, payload: Any,
                       clarifications: dict[str, str] | None = None) -> AnalystVerdict:
        clarifications = clarifications or {}
        # Operator-asserted exemption path. Logged via evidence, not enforced.
        if clarifications.get("phi-detection") == "no":
            return AnalystVerdict(
                analyst_id=self.ID,
                verdict="pass",
                rule_id=self.RULE_ID,
                layer=self.LAYER,
                matched=False,
                notes="skipped: clarifications.phi-detection = no (operator-asserted exemption)",
                evidence={"suppressed_by": "phi-detection=no"},
            )

        row = payload if isinstance(payload, dict) else {}
        matched_cols = [c for c in PHI_MARKER_COLUMNS if str(row.get(c, "")).strip()]
        if matched_cols:
            return AnalystVerdict(
                analyst_id=self.ID,
                verdict=self.severity_map.get("critical", "block"),
                rule_id=self.RULE_ID,
                layer=self.LAYER,
                matched=True,
                notes=f"PHI marker present in column(s): {', '.join(matched_cols)}",
                evidence={"matched_columns": matched_cols},
            )
        return AnalystVerdict(
            analyst_id=self.ID,
            verdict="pass",
            rule_id=self.RULE_ID,
            layer=self.LAYER,
            matched=False,
        )
