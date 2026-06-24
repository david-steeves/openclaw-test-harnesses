"""
test_system_ssn_block.py

Asserts: rows in hr-pii indices 0..49 (SSN+name+DOB) produce final_verdict BLOCK
with winning_layer = system.
"""

from __future__ import annotations

import asyncio

import pytest

from harness.policy_eval.composition import compose


def _evaluate(row, analysts):
    async def _run():
        out = []
        for a in analysts:
            try:
                out.append(await a.evaluate(0, row))
            except TypeError:
                out.append(await a.evaluate(0, row))
        return out
    return asyncio.run(_run())


def test_system_ssn_block_fires_for_block_range(hr_rows, pii_analysts):
    """Indices 0..49 must produce BLOCK with system as winning layer."""
    for i in range(50):
        verdicts = _evaluate(hr_rows[i], pii_analysts)
        result = compose(verdicts)
        assert result.final_verdict == "block", (
            f"row {i}: expected BLOCK, got {result.final_verdict}; verdicts={verdicts}"
        )
        assert result.winning_layer == "system", (
            f"row {i}: expected winning_layer=system, got {result.winning_layer}"
        )


def test_system_ssn_block_does_not_misfire_on_pass_rows(hr_rows, pii_analysts):
    """Indices 300..399 are PASS rows (employee_id + department only); no analyst should fire."""
    for i in range(300, 400):
        verdicts = _evaluate(hr_rows[i], pii_analysts)
        result = compose(verdicts)
        assert result.final_verdict == "pass", (
            f"row {i}: expected PASS, got {result.final_verdict}"
        )
