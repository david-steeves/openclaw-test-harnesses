"""
test_clarifying_prompts_metadata.py

Asserts: when an event arrives with `clarifications.phi-detection = "no"`, the
phi-marker-block analyst is suppressed even on rows with MRN-shaped data.

This is the operator-asserted exemption path — the system layer (SSN block)
still fires because system policies ignore clarifications.
"""

from __future__ import annotations

import asyncio

from harness.policy_eval.composition import compose


def _evaluate(row, analysts, clarifications):
    async def _run():
        out = []
        for a in analysts:
            try:
                out.append(await a.evaluate(0, row, clarifications=clarifications))
            except TypeError:
                out.append(await a.evaluate(0, row))
        return out
    return asyncio.run(_run())


def test_phi_marker_block_suppressed_by_clarification(phi_rows, phi_analysts):
    """
    With clarifications.phi-detection = no, indices 100..299 (MRN/diag, no SSN,
    with demographics) drop from BLOCK -> WARN. The phi-marker-block analyst is
    suppressed, but patient-id-warn (re-identification vector) is NOT
    suppressible — see policies/teams/phi-block.yaml suppressible_by_clarifications: [].
    """
    clarifications = {"phi-detection": "no"}
    for i in range(100, 300):
        verdicts = _evaluate(phi_rows[i], phi_analysts, clarifications)
        result = compose(verdicts)
        assert result.final_verdict == "warn", (
            f"row {i}: expected WARN with phi-detection=no suppression "
            f"(phi-marker-block suppressed, patient-id-warn still fires), "
            f"got {result.final_verdict}; verdicts={verdicts}"
        )


def test_system_ssn_block_not_suppressed_by_clarification(phi_rows, phi_analysts):
    """
    With clarifications.phi-detection = no, indices 0..99 (SSN + MRN/diag)
    must STILL be BLOCK because the system SSN policy ignores clarifications.
    """
    clarifications = {"phi-detection": "no"}
    for i in range(100):
        verdicts = _evaluate(phi_rows[i], phi_analysts, clarifications)
        result = compose(verdicts)
        assert result.final_verdict == "block", (
            f"row {i}: clarifications must not suppress system SSN block; "
            f"got {result.final_verdict}"
        )
        assert result.winning_layer == "system"
