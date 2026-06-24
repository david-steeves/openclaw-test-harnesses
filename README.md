# openclaw-test-harnesses

Reference implementations + test harness for [openclaw/rfcs#11](https://github.com/openclaw/rfcs/pull/11)
(RFC 0010 — Analyst-skill seams on a pipeline-shaped session substrate).

Stage-1 evidence track. This repo is **not** a new RFC — it's the
reference-implementation sibling that accompanies the open PR. Maintainers can
clone it, run the harness, and see exactly what a layered policy-composition +
clarifying-prompts surface costs on top of the bench numbers already posted in
that PR thread.

Related repos:
- **[openclaw/rfcs](https://github.com/openclaw/rfcs)** — the RFC docs (RFC 0010 in flight).
- **[openclaw-pipeline-bench](https://github.com/david-steeves/openclaw-pipeline-bench)** — the perf bench whose substrate this harness re-uses (`pipeline-real-claws` variant delegates to it).

## Dependencies

- **Python 3.13** (matches openclaw-pipeline-bench).
- **uv** — dependency management (`brew install uv`).
- **OrbStack** + **Docker** (for the perf harness; policy-eval runs locally).
- A sibling checkout of `openclaw-pipeline-bench` at `~/projects/openclaw-pipeline-bench/` (only needed for `make perf-test-vs-bench`).

## Quickstart (5 commands)

```sh
make install                 # verify python3.13 + uv + orb + docker
make gen-data                # regenerate mock-data/*/data.csv.gz from seeds
make policy-test             # functional: ingest mock data, assert verdicts
make perf-test               # perf: pipeline-real-claws variant in a container
make perf-test-vs-bench      # side-by-side comparison vs pipeline-bench reference
```

After `make policy-test`, look at `harness/policy-eval/verdict-tape/<ts>/REPORT.md`
for the human-readable trace. After `make perf-test-vs-bench`, look at the
comparison report in `bench/results/<ts>/COMPARISON.md`.

## Layout

```
control-plane/         — openclaw.config.yaml schema + paste-in example
clarifying-prompts/    — decision-tree schema + upload / analyze prompt examples
policies/              — system + shared-lib + team-scoped policy YAML
  system/              — always-evaluated, system-wide (SSN, API-key)
  shared-lib/          — composable rule snippets re-used by team-scoped policies
  teams/               — scoped to a single review team (pii-warn, phi-block)
teams/                 — reference review teams: pii-reviewer, phi-reviewer
                         each with team.yaml + analysts/*.py + README.md
mock-data/             — synthetic public-safe HR-PII and PHI fixtures (~1MB gz each)
  generators/          — deterministic Faker/Synthea-shaped seed-driven generators
harness/
  policy-eval/         — functional test harness: ingest + assert vs annotations
    composition.py     — the layered composition rule (BLOCK > WARN > PASS, scoped cannot downgrade system BLOCK)
    asserts/           — pytest-style assertions per category
    verdict-tape/      — human-readable per-run transcripts (gitignored)
  perf/                — perf harness: pipeline-real-claws variant
    manifest.yaml      — extends openclaw-pipeline-bench manifest
    workload-from-mock.py — replays mock CSV rows as the bench event stream
scripts/               — comparison report generator
Makefile               — install / gen-data / policy-test / perf-test / perf-test-vs-bench / all / clean
docker-compose.yml     — container for perf runs
```

## Policy composition rule (one paragraph)

```
final_verdict = max(system_verdicts ∪ scoped_verdicts)
ordering:      PASS < WARN < BLOCK
constraint:    scoped layer can ADD warns/blocks; cannot downgrade system verdicts
audit_trail:   every layer that fired is recorded; the winning layer is named
```

Precedent: AWS IAM explicit-deny + Microsoft Purview most-restrictive-policy-wins.
Implementation lives in `harness/policy-eval/composition.py`. Citations in
[`policies/README.md`](./policies/README.md).

## Sanity gates (mirror plan §"Sanity gates")

Before posting numbers in the follow-up PR comment, all of these must hold:

1. **All annotated mock rows produce the documented verdict.** Verdict tape
   matches every `annotations.yaml`.
2. **Policy composition tests are green.** A row hitting both `system/block-ssn`
   and `policies/teams/pii-warn` returns BLOCK with both verdicts in the audit
   trail (system layer wins; scoped recorded as advisory).
3. **Clarifying-prompt metadata routes correctly.** A row uploaded with
   `clarifications.phi-detection = no` does NOT trigger the PHI block analyst
   even if the row contains MRN-shaped data (operator-asserted exemption path;
   logged but not enforced).
4. **Perf monotonicity:** `pipeline-noop ≤ pipeline-real-claws-pass-only ≤ pipeline-real-claws-mixed`.
   If real claws beat synthetic pass-analysts, instrumentation is wrong.
5. **Cost delta is citable:** the difference between `pipeline-noop` and
   `pipeline-real-claws` is the headline number for the follow-up PR comment.

## Status

- **2026-06-24:** Initial commit per
  [`plans/2026-06-19-policy-harness-extension.md`](https://github.com/david-steeves/openclaw-pipeline-bench/blob/main/plans/2026-06-19-policy-harness-extension.md)
  in the openclaw-pipeline-bench repo.
- Tag `rfc-0010-v1` will be cut once the M5 Pro session has all 5 sanity gates
  green; that's the SHA cited in the follow-up PR comment.

## License

MIT. See [`LICENSE`](./LICENSE).
