# clarifying-prompts

Decision-tree YAML for **interactive intent capture** at the upload and
analyze seams. This surface is **novel** — none of the surveyed prior-art
(Presidio, Purview, Macie, Cloud DLP) does interactive intent-capture at
upload/analyze. Closest analog is Stripe Radar's 4-action model (block /
allow / review / challenge). Worth surfacing as an OpenClaw differentiator in
the follow-up PR comment.

## Files

| File | Purpose |
|---|---|
| `schema.yaml` | JSON Schema for decision-tree prompt sets. |
| `upload-prompts.example.yaml` | 2 upload-time prompts: PHI detection (with PHI -> jurisdiction follow-up) + data-class declaration. |
| `analyze-prompts.example.yaml` | 2 analyze-time prompts: output destination (external -> DPA follow-up; public -> disclosure review) + analysis depth (skipped on public output). |

## Decision-tree semantics

A prompt has:
- `id` — stable identifier; operator answer attaches at
  `event.metadata.clarifications.<id>`.
- `type` — `yesNo`, `yesNoWithContext` (yes/no/uncertain), `singleSelect`,
  `multiSelect`.
- `answers[]` — closed answer set; UI surfaces these verbatim.
- `followUp[]` — conditional sub-prompts triggered when the operator's
  answer matches a given `when`. Recursive — follow-ups can have their own
  follow-ups.
- `skipCondition` — short-circuit; if the referenced earlier prompt answered
  the named way, this prompt is skipped.
- `enforcement` — declares how the answer feeds policy evaluation:
  - **advisory** — answer recorded; policies may read it but no automatic
    verdict change.
  - **suppresses** — if operator picks the `whenAnswerId`, named analysts
    are skipped for this event (operator-asserted exemption).
  - **escalates** — if operator picks the `whenAnswerId`, event is routed
    to named teams for review before proceeding.

## Skip-logic example

In `analyze-prompts.example.yaml`, the `analysis-depth` prompt has:

```yaml
skipCondition:
  whenPromptId: output-destination
  whenAnswerId: public
```

If the operator selected `output-destination = public`, the `analysis-depth`
prompt does not fire (aggregate-only is implied at publication). This avoids
forcing the operator to answer prompts whose answers are determined by
earlier choices.

## Metadata attachment

After the prompt set completes, the engine attaches answers to the event:

```python
event.metadata.clarifications = {
    "phi-detection": "no",
    "data-class-declaration": "hr",
    # skipped prompts are absent from the dict (not null)
}
```

The policy engine reads `event.metadata.clarifications.<prompt-id>` during
evaluation. See `policies/system/block-ssn.yaml` for an example of a policy
that does NOT consult clarifications (system layer is unconditional) and
`teams/phi-reviewer/analysts/phi_marker_block.py` for an analyst that DOES
honor `clarifications["phi-detection"] == "no"` as a suppression signal.

## Why `suppresses` is dangerous (and why we ship it anyway)

`enforcement.mode = suppresses` is the operator-asserted exemption path. It
exists because HIPAA covered entities, SOC2 auditors, and ISO27001
implementers all rely on attestation patterns where the operator certifies
something the engine can't independently verify ("this dataset has been
de-identified by my hand"). Without it, the surface is non-adoptable in
regulated environments.

But: it's the most common attack vector. Mitigation in this design:

1. Suppressions are **always logged to evidence** (the verdict tape shows
   "skipped because clarifications.phi-detection = no, attested by
   operator=$user, ts=$ts").
2. System-layer policies (`policies/system/`) ignore `clarifications`
   entirely. An SSN policy fires regardless of the operator claiming "no
   PII".
3. The composition rule (see `policies/README.md`) says the scoped layer
   cannot downgrade a system BLOCK; suppression at the scoped layer cannot
   override a system-layer block.

## Why this is **not** an RFC yet

The parent plan keeps this in evidence track. If maintainers reply "yes,
formalize this clarifying-prompt seam", the schema here gets lifted to RFC
0014 with versioning + ABI guarantees. Until then, it's reference shape, not
normative.
