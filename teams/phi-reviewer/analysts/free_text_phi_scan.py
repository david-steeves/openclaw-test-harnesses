"""
teams/phi-reviewer/analysts/free_text_phi_scan.py

Basic heuristic regex scan of `diagnosis_notes` free-text field. Emits WARN on
any match of:
  - date patterns (likely DOB or visit date embedded in narrative)
  - capitalized two-word patterns that look like names

This is intentionally a *basic* heuristic. The LLM-analyst seam in RFC 0010 is
exactly the case where regex-only analysts fall down — the production answer
is an LLM-backed analyst that does named-entity-recognition over free-text
clinical notes. This file is the regex placeholder; the perf cost it adds is
what we measure in the bench delta.
"""

from __future__ import annotations

import re
from typing import Any

from harness.verdict import AnalystVerdict


# Date patterns: ISO (2026-01-15), US (01/15/2026), long form (Jan 15, 2026).
DATE_PATTERNS = [
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),
    re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b"),
    re.compile(
        r"\b(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{4}\b"
    ),
]
# Capitalized two-word pattern that looks like a name. False-positive prone;
# in production this is replaced by an LLM analyst.
NAME_PATTERN = re.compile(r"\b[A-Z][a-z]{2,}\s+[A-Z][a-z]{2,}\b")


class FreeTextPhiScan:
    ID = "phi-reviewer.free-text-phi-scan"
    RULE_ID = "policy/teams/phi-block/free-text-scan.v1"
    LAYER = "scoped"

    def __init__(self, severity_map: dict[str, str] | None = None):
        self.severity_map = severity_map or {"high": "warn"}

    async def evaluate(self, agent_id: int, payload: Any,
                       clarifications: dict[str, str] | None = None) -> AnalystVerdict:
        text = self._extract_notes(payload)
        if not text:
            return AnalystVerdict(
                analyst_id=self.ID,
                verdict="pass",
                rule_id=self.RULE_ID,
                layer=self.LAYER,
                matched=False,
            )

        date_hits = sum(1 for p in DATE_PATTERNS if p.search(text))
        name_hit = bool(NAME_PATTERN.search(text))
        matched = bool(date_hits) or name_hit
        if matched:
            return AnalystVerdict(
                analyst_id=self.ID,
                verdict=self.severity_map.get("high", "warn"),
                rule_id=self.RULE_ID,
                layer=self.LAYER,
                matched=True,
                notes=f"free-text scan: date_hits={date_hits} name_hit={name_hit}",
                evidence={
                    "date_pattern_hits": date_hits,
                    "name_pattern_hit": name_hit,
                    "scanned_field": "diagnosis_notes",
                },
            )
        return AnalystVerdict(
            analyst_id=self.ID,
            verdict="pass",
            rule_id=self.RULE_ID,
            layer=self.LAYER,
            matched=False,
        )

    @staticmethod
    def _extract_notes(payload: Any) -> str:
        if isinstance(payload, dict):
            return str(payload.get("diagnosis_notes", "") or "")
        if isinstance(payload, str):
            # Perf-path payloads are JSON-shaped; the bench substrate emits
            # filler strings without diagnosis_notes structure. We just scan the
            # whole string for the same patterns to keep the cost shape honest.
            return payload
        return ""
