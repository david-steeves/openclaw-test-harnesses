"""
harness/policy_eval/composition.py

Layered policy composition. The one rule of OpenClaw policy:

    final_verdict = max(system_verdicts ∪ scoped_verdicts)
    ordering:      PASS < WARN < BLOCK
    constraint:    scoped layer can ADD warns/blocks; cannot downgrade system verdicts
    audit_trail:   every layer that fired is recorded; the winning layer is named

Precedent: AWS IAM explicit-deny + Microsoft Purview most-restrictive-policy-wins.
See policies/README.md for citation discussion.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from harness.verdict import AnalystVerdict


@dataclass
class CompositionResult:
    final_verdict: str            # "pass" | "warn" | "block"
    winning_layer: str            # "system" | "scoped" | "none"
    winning_analyst: str | None   # analyst_id of the winning verdict, or None
    verdicts: list[AnalystVerdict] = field(default_factory=list)
    advisory_after_system_block: list[AnalystVerdict] = field(default_factory=list)
    """Scoped verdicts that fired AFTER a system BLOCK landed. Recorded for audit
    completeness; not enforced (the system BLOCK already wins)."""


def compose(verdicts: list[AnalystVerdict]) -> CompositionResult:
    """
    Apply the composition rule. Inputs come in any order; we split by layer
    and apply the constraint.
    """
    if not verdicts:
        return CompositionResult(
            final_verdict="pass",
            winning_layer="none",
            winning_analyst=None,
            verdicts=[],
        )

    system_verdicts = [v for v in verdicts if v.layer == "system"]
    scoped_verdicts = [v for v in verdicts if v.layer == "scoped"]

    system_top = _top_verdict(system_verdicts)
    scoped_top = _top_verdict(scoped_verdicts)

    advisory: list[AnalystVerdict] = []

    if system_top and scoped_top:
        if system_top.rank() >= scoped_top.rank():
            winning = system_top
            winning_layer = "system"
            # If the system layer BLOCKed, every scoped verdict at WARN or BLOCK
            # is advisory — recorded but cannot change the outcome.
            if system_top.verdict == "block":
                advisory = [v for v in scoped_verdicts if v.verdict in ("warn", "block")]
        else:
            winning = scoped_top
            winning_layer = "scoped"
    elif system_top:
        winning = system_top
        winning_layer = "system"
    elif scoped_top:
        winning = scoped_top
        winning_layer = "scoped"
    else:
        winning = max(verdicts, key=lambda v: v.rank())
        winning_layer = winning.layer if winning.verdict != "pass" else "none"

    return CompositionResult(
        final_verdict=winning.verdict,
        winning_layer=winning_layer if winning.verdict != "pass" else "none",
        winning_analyst=winning.analyst_id if winning.verdict != "pass" else None,
        verdicts=verdicts,
        advisory_after_system_block=advisory,
    )


def _top_verdict(verdicts: list[AnalystVerdict]) -> AnalystVerdict | None:
    if not verdicts:
        return None
    return max(verdicts, key=lambda v: v.rank())


def format_audit_trail(result: CompositionResult) -> str:
    """Pretty-print the audit trail for a single row's composition."""
    lines = [
        f"final_verdict={result.final_verdict.upper()} "
        f"winning_layer={result.winning_layer} "
        f"winning_analyst={result.winning_analyst}",
    ]
    for v in result.verdicts:
        marker = "*" if v.analyst_id == result.winning_analyst else " "
        lines.append(
            f"  {marker} layer={v.layer:6s} analyst={v.analyst_id:42s} "
            f"verdict={v.verdict:5s} rule={v.rule_id}"
            + (f"  ({v.notes})" if v.notes else "")
        )
    if result.advisory_after_system_block:
        lines.append("  advisory (recorded but not enforced; system BLOCK already won):")
        for v in result.advisory_after_system_block:
            lines.append(f"    - {v.analyst_id} -> {v.verdict} ({v.notes})")
    return "\n".join(lines)
