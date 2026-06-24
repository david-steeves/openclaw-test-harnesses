# teams/pii-reviewer

Reference review team for HR/payroll-shaped PII.

Renamed from `hr-reviewer` per the parent plan §"Design decisions" Q2 — name
describes *what's reviewed*, not *source format*. Mock data dir keeps the
source-shape name (`mock-data/hr-pii/`).

## Analysts

| Analyst | Module | Severity | Verdict | Layer |
|---|---|---|---|---|
| ssn-detector | `analysts/ssn_detector.py` | critical | BLOCK on `\d{3}-\d{2}-\d{4}` match | system |
| pii-cooccurrence-warn | `analysts/pii_cooccurrence_warn.py` | high | WARN on name + DOB in same row | scoped |
| salary-warn | `analysts/salary_warn.py` | high | WARN on salary column non-empty | scoped |

## Scope

`data_classes: [hr, payroll]`. Events whose
`metadata.data_class` is not in this set bypass this team.

## Why `ssn_detector` lives in this team but reports `layer = system`

The system-wide SSN block rule is conceptually owned by the
`policies/system/` layer. We host the *implementation* inside the pii-reviewer
team because pii-reviewer is the team that surfaces it in evidence on HR data.
The composition engine tags the verdict's `layer = "system"` so the rule
cannot be downgraded by other scoped policies, regardless of which team's
analyst raised it.

This split is intentional — system policies are not their own team. They're a
*layer* that any team can carry an implementation of.

## Clarifying-prompt wiring

`team.yaml` references:

```
clarifying_prompts:
  upload: openclaw-test-harnesses:clarifying-prompts/upload-prompts.example.yaml
  analyze: openclaw-test-harnesses:clarifying-prompts/analyze-prompts.example.yaml
```

The pii-reviewer team does NOT honor `phi-detection = no` suppression — that's
phi-reviewer's surface. The `data-class-declaration` answer routes events to
this team (`hr`, `payroll`) vs. phi-reviewer (`healthcare`, `warehouse`,
`snowflake`).
