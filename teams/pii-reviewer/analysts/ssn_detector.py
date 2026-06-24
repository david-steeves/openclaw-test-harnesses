"""
teams/pii-reviewer/analysts/ssn_detector.py

Detects US-format SSN (\\d{3}-\\d{2}-\\d{4}) anywhere in payload. Emits BLOCK.

Wire-up to actually load the YAML rule (policies/system/block-ssn.yaml) at
runtime is a Stage-2 concern; in this reference implementation the regex is
duplicated as a constant for clarity.

Interface matches openclaw-pipeline-bench's PassAnalyst/BlockingAnalyst shape:
    async evaluate(agent_id, payload) -> AnalystVerdict

Verdict shape is the typed `AnalystVerdict` dataclass from harness/verdict.py.
The perf adapter (harness/perf/runner.py) coerces this to the bench's string
contract when delegating to the bench substrate.
"""

from __future__ import annotations

import re
from typing import Any

from harness.verdict import AnalystVerdict


# Constant mirrors policies/system/block-ssn.yaml (rule.pattern). The rule is
# system-wide; this analyst surfaces it inside the pii-reviewer team because
# pii-reviewer is the team that publishes evidence on HR data. The composition
# engine still tags the verdict's layer as "system" so the rule cannot be
# downgraded by other scoped policies.
SSN_PATTERN = re.compile(r"\d{3}-\d{2}-\d{4}")


class SsnDetector:
    """Analyst skill: BLOCK on any SSN-shape match."""

    ID = "pii-reviewer.ssn-detector"
    RULE_ID = "policy/system/block-ssn.v1"
    LAYER = "system"

    def __init__(self, severity_map: dict[str, str] | None = None):
        self.severity_map = severity_map or {"critical": "block", "high": "warn"}

    async def evaluate(self, agent_id: int, payload: Any) -> AnalystVerdict:
        """
        payload may be:
          - a JSON-shaped string (perf path; bench substrate hands us strings)
          - a dict of column -> value (policy-eval path; ingester hands us rows)
        We treat both as text for the regex scan.
        """
        text = self._stringify(payload)
        matched = bool(SSN_PATTERN.search(text))
        if matched:
            return AnalystVerdict(
                analyst_id=self.ID,
                verdict=self.severity_map.get("critical", "block"),
                rule_id=self.RULE_ID,
                layer=self.LAYER,
                matched=True,
                notes="SSN-shape regex matched",
                evidence={"pattern": SSN_PATTERN.pattern},
            )
        return AnalystVerdict(
            analyst_id=self.ID,
            verdict="pass",
            rule_id=self.RULE_ID,
            layer=self.LAYER,
            matched=False,
        )

    @staticmethod
    def _stringify(payload: Any) -> str:
        if isinstance(payload, str):
            return payload
        if isinstance(payload, dict):
            return " ".join(str(v) for v in payload.values())
        return str(payload)
