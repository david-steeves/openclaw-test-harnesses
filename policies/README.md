# policies

Layered policy YAML, organized by layer:

```
policies/
  system/      — always-evaluated, never-downgraded floor
  shared-lib/  — composable rule snippets; no verdict on their own
  teams/       — scoped to a single review team; can add but never subtract
```

## Composition rule (the one rule)

```
final_verdict = max(system_verdicts ∪ scoped_verdicts)
ordering:      PASS < WARN < BLOCK
constraint:    scoped layer can ADD warns/blocks; cannot downgrade system verdicts
audit_trail:   every layer that fired is recorded; the winning layer is named
```

**System-layer policies always run first.** Their verdicts are unconditional —
they ignore `clarifications` and they cannot be downgraded by a scoped policy.

**Scoped-layer policies still evaluate after a system BLOCK** for audit
completeness — their verdicts become *advisory* (recorded in evidence, not
enforced). This is intentional: when a system BLOCK fires, we still want the
audit record of what the scoped layer would have said, because that informs
downstream investigation of the leak.

**Scoped layers can stack.** Two scoped policies both firing WARN do not
escalate to BLOCK; the verdict is still WARN. Escalation requires a BLOCK from
either layer.

## Precedent

This rule is borrowed (and is meant to be obviously familiar) from:

| System | Rule | Why this maps |
|---|---|---|
| **AWS IAM** | Explicit deny always wins over any allow. | Our system-layer BLOCK is the explicit-deny analog. |
| **Microsoft Purview** | Most-restrictive policy wins on a labeled artifact. | Our `max(verdicts)` ordering. |
| **Kubernetes admission controllers** | Validating chain — any "deny" rejects, mutating chain composes left-to-right. | Our two-layer separation (system = validating; scoped = additional validating). |
| **OPA / Rego** | `default allow = false`; rules add denials. | Our scoped layer additivity (can add BLOCKs, cannot subtract them). |

We cite AWS IAM + Microsoft Purview in the follow-up PR comment because they're
the two best-known landmarks; the rule is not novel and that's the point.

## Layer details

### `system/`

| File | Detects | Verdict |
|---|---|---|
| `block-ssn.yaml` | `\d{3}-\d{2}-\d{4}` anywhere in payload | BLOCK |
| `block-api-key.yaml` | `api[_-]?key\s*[=:]` (case-insensitive) | BLOCK |

System policies have `honors_clarifications: false` — operator self-attestation
cannot disable them.

### `shared-lib/`

Composable rule snippets, no verdict by themselves. Imported by team-scoped
policies via `imports: shared-lib/<name>`.

| File | What it describes |
|---|---|
| `ssn-detector.yaml` | SSN regex (same pattern as system; available to scoped layers that want non-BLOCK semantics) |
| `phi-detector.yaml` | Column-presence: mrn / diagnosis_code / patient_id non-empty |
| `pii-cooccurrence.yaml` | Column-cooccurrence: full_name (or first+last) AND date_of_birth in same row |

### `teams/`

Scoped to a single team via `scope.team`. Evaluated only for events matching
the team's `scope.data_classes` (from `team.yaml`).

| File | Scoped to | Rules |
|---|---|---|
| `pii-warn.yaml` | pii-reviewer | name+DOB cooccurrence -> WARN; salary presence -> WARN |
| `phi-block.yaml` | phi-reviewer | PHI marker (mrn/diag/patient_id) -> BLOCK; patient_id+birth_date+city -> WARN |

Scoped policies have `honors_clarifications: true`; specifically the
`phi-marker-block` rule is `suppressible_by_clarifications` when
`phi-detection = no` (operator-asserted exemption — logged, not enforced).

## Worked example: SSN + DOB + name row in HR mock data

Row: `{first_name: "Jane", last_name: "Roe", date_of_birth: "1980-05-12", ssn: "123-45-6789", ...}`

Evaluation:

1. **System layer:** `block-ssn` matches `123-45-6789` -> BLOCK.
2. **System layer:** `block-api-key` no match -> PASS.
3. **Scoped layer (pii-warn):** `name-dob-cooccurrence` matches -> WARN
   (advisory because system already BLOCKed).
4. **Scoped layer (pii-warn):** `salary-presence` matches (if salary col present)
   -> WARN (advisory).

`max({BLOCK, PASS, WARN, WARN}) = BLOCK`. Final verdict = BLOCK. Winning layer
= system. Audit trail records all four verdicts. Composition rule satisfied.

## Why `system_policies` is append-only across `extends`

Per `control-plane/README.md`, an `extends` chain cannot remove a system
policy that an earlier layer added. This is the same principle as
container-image USER directives: lower layers can't unprivilege higher
layers.
