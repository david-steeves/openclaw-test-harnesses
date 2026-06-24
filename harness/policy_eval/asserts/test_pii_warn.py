"""
test_pii_warn.py

Asserts:
  - hr-pii indices 50..199 (name + DOB, no SSN) -> WARN, scoped layer
  - hr-pii indices 200..299 (salary, no name/DOB/SSN) -> WARN, scoped layer
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


def test_name_dob_cooccurrence_warns(hr_rows, pii_analysts):
    for i in range(50, 200):
        verdicts = _evaluate(hr_rows[i], pii_analysts)
        result = compose(verdicts)
        assert result.final_verdict == "warn", (
            f"row {i}: expected WARN, got {result.final_verdict}"
        )
        assert result.winning_layer == "scoped", (
            f"row {i}: expected scoped winning layer, got {result.winning_layer}"
        )


def test_salary_warns(hr_rows, pii_analysts):
    for i in range(200, 300):
        verdicts = _evaluate(hr_rows[i], pii_analysts)
        result = compose(verdicts)
        assert result.final_verdict == "warn", (
            f"row {i}: expected WARN, got {result.final_verdict}"
        )
