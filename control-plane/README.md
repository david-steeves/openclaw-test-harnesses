# control-plane

The `openclaw.config.yaml` surface — the **one file** a consumer edits to turn
review teams on/off. Renovate-style preset composition: drop in
`example.config.yaml`, flip `enabled: true` on the teams you want, override
1-2 fields, ship.

## Files

| File | Purpose |
|---|---|
| `config-schema.yaml` | JSON Schema (expressed in YAML, draft-07) for the config file. Validates any `openclaw.config.yaml`. |
| `example.config.yaml` | Paste-in default that wires up `pii-reviewer` + `phi-reviewer` with sensible scope and severity defaults. |

## How resolution works

Every preset reference uses the form `<repo-id>:<path-from-repo-root>`. The
repo-id `openclaw-test-harnesses` resolves to this repo. A downstream
consumer's own `openclaw.config.yaml` might also `extends:` a corporate
internal preset like `acme-platform:configs/openclaw-base.yaml` — the engine
resolves repos via its own checkout map, independent of this schema.

## Composition order (`extends`)

```
default (no extends)
  ↓
extends[0] applied
  ↓
extends[1] applied (overrides extends[0])
  ↓
...
extends[n] applied
  ↓
this file's inline fields applied (overrides all extends)
```

This mirrors Renovate's preset composition model. Last-write-wins per key,
except `system_policies` and `teams[].analysts` which are **append-only**
across extends — adding analysts is additive, never subtractive (an `extends`
chain cannot remove a system policy that an earlier layer added).

## Why `enabled` is a hard switch (not implicit)

Forcing every team to declare `enabled: true|false` makes it impossible to
silently inherit a team you didn't realize was on. A new team added to a
preset has to be acknowledged in the consumer's config before it evaluates
anything.

## Scope filter semantics

`scope.data_classes` is an allow-list. An event with
`metadata.data_class = "hr"` routes to `pii-reviewer` (allowed) but bypasses
`phi-reviewer` (not in its scope). Events with no data_class go to all
enabled teams — fail-safe default; if you want strict routing, set
`metadata.data_class` upstream.

## Validating a config

Any YAML or JSON Schema validator. Example:

```sh
pip install yamale check-jsonschema
check-jsonschema --schemafile control-plane/config-schema.yaml my-openclaw.config.yaml
```

The `make policy-test` target validates the bundled `example.config.yaml`
against the schema as part of its conftest fixtures.

## Why this lives here (not in `openclaw-rfcs`)

Per the parent plan, RFC docs stay docs. Executable schemas live in the
test-harnesses repo. If maintainers ask for the schema to be formalized,
that's a future RFC 0013-shaped surface; until then, this is the working
contract.
