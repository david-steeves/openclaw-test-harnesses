"""
test_phi_block.py

Asserts:
  - phi-snowflakey indices 0..99 (SSN + MRN/diag) -> BLOCK with winning_layer = system
  - phi-snowflakey indices 100..299 (MRN/diag, no SSN) -> BLOCK with winning_layer = scoped
"""

from __future__ import annotations

import asyncio

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


def test_system_block_wins_when_ssn_and_phi_both_present(phi_rows, phi_analysts):
    for i in range(100):
        verdicts = _evaluate(phi_rows[i], phi_analysts)
        result = compose(verdicts)
        assert result.final_verdict == "block", f"row {i}: expected BLOCK, got {result.final_verdict}"
        assert result.winning_layer == "system", (
            f"row {i}: expected winning_layer=system (SSN dominates), got {result.winning_layer}"
        )


def test_scoped_phi_block_fires_without_ssn(phi_rows, phi_analysts):
    for i in range(100, 300):
        verdicts = _evaluate(phi_rows[i], phi_analysts)
        result = compose(verdicts)
        assert result.final_verdict == "block", f"row {i}: expected BLOCK, got {result.final_verdict}"
        assert result.winning_layer == "scoped", (
            f"row {i}: expected scoped winning layer, got {result.winning_layer}"
        )
