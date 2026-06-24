# teams/phi-reviewer

Reference review team for healthcare-warehouse-shaped PHI.

Renamed from `snowflake-reviewer` per the parent plan §"Design decisions" Q2.
Mock data dir keeps the source-shape name (`mock-data/phi-snowflakey/`).

## Analysts

| Analyst | Module | Severity | Verdict | Layer |
|---|---|---|---|---|
| phi-marker-block | `analysts/phi_marker_block.py` | critical | BLOCK if MRN or diagnosis_code non-empty | scoped |
| patient-id-warn | `analysts/patient_id_warn.py` | high | WARN if patient_id + birth_date + city co-occur | scoped |
| free-text-phi-scan | `analysts/free_text_phi_scan.py` | high | WARN on date or name patterns in `diagnosis_notes` | scoped |

## Scope

`data_classes: [warehouse, snowflake, healthcare]`. Events whose
`metadata.data_class` is not in this set bypass this team.

## Clarifying-prompt wiring

`team.yaml` references the upload prompts (PHI detection, jurisdiction,
data-class declaration). The `phi-marker-block` analyst honors
`clarifications.phi-detection == "no"` as an operator-asserted exemption:

```python
if clarifications.get("phi-detection") == "no":
    return AnalystVerdict(..., verdict="pass", notes="skipped: operator-asserted exemption", ...)
```

This is logged in the verdict tape with an explicit `suppressed_by` evidence
key so the audit trail captures the attestation. See
`clarifying-prompts/README.md` §"Why `suppresses` is dangerous (and why we
ship it anyway)" for the full rationale.

`patient_id_warn` and `free_text_phi_scan` do NOT honor any suppression.
Re-identification vectors are too high-stakes for operator self-attestation
at this layer; if the data is misrouted, the right fix is `data_class`
correction, not suppression.

## Why `free_text_phi_scan` is a basic heuristic

In RFC 0010, free-text scanning is the LLM-analyst seam — exactly the case
where regex-only analysts fall down. This file is the regex placeholder; it
fires on date patterns and capitalized-two-word "looks-like-a-name" patterns.
False-positive prone by design. The production replacement is an LLM-backed
analyst doing named-entity-recognition over clinical notes.

We ship the regex version because:
1. It produces *some* cost in the perf bench delta (vs. an unloaded analyst).
2. It demonstrates the seam without requiring an LLM dependency in the
   harness.
3. It documents the expected failure mode for maintainers reviewing the RFC.
