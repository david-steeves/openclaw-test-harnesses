"""
test_policy_composition.py

The headline policy composition gate:
  - When a system BLOCK fires alongside a scoped WARN/BLOCK, the final verdict
    is BLOCK with winning_layer = system, AND both verdicts are recorded in
    the audit trail.

Tested at the composition level (synthetic AnalystVerdict inputs) so the test
is independent of any specific mock data.
"""

from __future__ import annotations

from harness.policy_eval.composition import compose
from harness.verdict import AnalystVerdict


def _v(analyst_id, verdict, layer, rule_id="policy/test.v0", matched=True):
    return AnalystVerdict(
        analyst_id=analyst_id,
        verdict=verdict,
        rule_id=rule_id,
        layer=layer,
        matched=matched,
    )


def test_system_block_trumps_scoped_warn():
    verdicts = [
        _v("ssn-detector", "block", "system"),
        _v("pii-cooccurrence", "warn", "scoped"),
    ]
    result = compose(verdicts)
    assert result.final_verdict == "block"
    assert result.winning_layer == "system"
    assert result.winning_analyst == "ssn-detector"
    # Audit trail must include both verdicts.
    assert len(result.verdicts) == 2
    # The scoped WARN is advisory (it fired but didn't win).
    assert any(v.analyst_id == "pii-cooccurrence" for v in result.advisory_after_system_block)


def test_system_block_trumps_scoped_block():
    """Two BLOCKs from different layers — system wins; scoped becomes advisory."""
    verdicts = [
        _v("ssn-detector", "block", "system"),
        _v("phi-marker", "block", "scoped"),
    ]
    result = compose(verdicts)
    assert result.final_verdict == "block"
    assert result.winning_layer == "system"
    assert any(v.analyst_id == "phi-marker" for v in result.advisory_after_system_block)


def test_scoped_block_wins_when_no_system_verdict_above_pass():
    verdicts = [
        _v("ssn-detector", "pass", "system"),
        _v("phi-marker", "block", "scoped"),
    ]
    result = compose(verdicts)
    assert result.final_verdict == "block"
    assert result.winning_layer == "scoped"
    # No advisory: system layer didn't BLOCK, nothing to suppress.
    assert result.advisory_after_system_block == []


def test_two_scoped_warns_remain_warn():
    """Stacking WARNs from the scoped layer does NOT escalate to BLOCK."""
    verdicts = [
        _v("pii-cooccurrence", "warn", "scoped"),
        _v("salary-warn", "warn", "scoped"),
    ]
    result = compose(verdicts)
    assert result.final_verdict == "warn"
    assert result.winning_layer == "scoped"


def test_all_pass_yields_pass():
    verdicts = [
        _v("ssn-detector", "pass", "system"),
        _v("pii-cooccurrence", "pass", "scoped"),
    ]
    result = compose(verdicts)
    assert result.final_verdict == "pass"
    assert result.winning_layer == "none"
    assert result.winning_analyst is None


def test_empty_verdicts_yields_pass():
    result = compose([])
    assert result.final_verdict == "pass"
    assert result.winning_layer == "none"
