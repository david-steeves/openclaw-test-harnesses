# HANDOFF — M4 Pro / M5 Pro execution

**Authored:** 2026-06-24 (MacBook implementation session)
**Target executor:** Mac mini M4 Pro (perf gates) — policy-eval runs anywhere
**Origin:** `github.com/david-steeves/openclaw-test-harnesses`

Landing pad. Mirrors the HANDOFF style of openclaw-pipeline-bench. Read this,
then glance at `README.md` and the parent plan
([`plans/2026-06-19-policy-harness-extension.md`](https://github.com/david-steeves/openclaw-pipeline-bench/blob/main/plans/2026-06-19-policy-harness-extension.md)
in the bench repo).

---

## TL;DR

```sh
git clone git@github.com:david-steeves/openclaw-test-harnesses.git ~/projects/openclaw-test-harnesses
cd ~/projects/openclaw-test-harnesses
make install          # verify python3.13 + uv + orb + docker
make gen-data         # deterministic — seeds documented in mock-data/*/schema.md
make policy-test      # functional, runs locally — should be green out of the box
make perf-test        # perf, runs in a container
make perf-test-vs-bench  # needs sibling ~/projects/openclaw-pipeline-bench/ checkout with recent bench/results/<ts>/
```

After `make policy-test` is green, look at
`harness/policy-eval/verdict-tape/<ts>/REPORT.md`. After
`make perf-test-vs-bench`, write the headline paragraph by hand at the top of
`bench/results/<ts>/COMPARISON.md`. That paragraph is the seed of the follow-up
PR comment.

---

## Pre-flight state (verified on MacBook, 2026-06-24)

| Check                                  | State |
|----------------------------------------|-------|
| `make install` passes                  | check on M4 Pro |
| `make gen-data` produces both csv.gz   | verified at commit time |
| `make policy-test` runs to green       | verified at commit time |
| `docker compose build`                 | check on M4 Pro |
| Smoke: `cd harness/perf && uv run --with psutil --with pyyaml python runner.py --variant pipeline-real-claws --duration 10 --in-memory --manifest manifest.yaml` returns a RESULT line | verified at commit time |

Anything marked **check on M4 Pro** is hardware-dependent — orb/docker may not
have been smoke-tested on a fresh Mac mini before clone. Run `make install`
first; if it complains, that's the gate.

---

## What this repo is for (one paragraph)

The bench repo (openclaw-pipeline-bench) measured **substrate cost** — what
does the file-share → 3-stage SQLite pipeline transition cost in latency, with
and without synthetic analysts? Those numbers are posted in
[openclaw/rfcs#11](https://github.com/openclaw/rfcs/pull/11). This repo measures
**real-claw cost** — what does it cost when the analysts at each seam do *actual
work* (regex SSN detection, PII co-occurrence checks, PHI marker scans) instead
of `await asyncio.sleep(1ms)`? The headline number is the delta between
`pipeline-1-analyst` (bench) and `pipeline-real-claws` (this repo).

Plus it ships the **policy composition + clarifying-prompts surface** as
documented YAML + a working functional harness. So the follow-up PR comment
cites both a number (real-claw cost delta) and a working design (the YAML +
Python here).

---

## Sanity gates (required before tagging `rfc-0010-v1`)

From the parent plan §"Sanity gates":

1. All annotated mock rows produce the documented verdict (verdict tape matches
   every annotations.yaml).
2. Policy composition tests are green — a row hitting both system block-ssn AND
   scoped pii-warn returns BLOCK with both verdicts in the audit trail.
3. Clarifying-prompt metadata routes correctly — `clarifications.phi-detection = no`
   suppresses PHI block analyst even on MRN-shaped data.
4. Perf monotonicity holds: `pipeline-noop ≤ pipeline-real-claws-pass-only ≤ pipeline-real-claws-mixed`.
5. Cost delta is citable — `pipeline-real-claws` minus `pipeline-noop` is the
   headline number.

---

## What can go wrong (and what to look at)

- **`make gen-data` says faker missing** → `uv` should grab it via
  `uv run --with faker python ...`; verify `mock-data/generators/requirements.txt`
  is intact.
- **`make policy-test` red on a single assertion** → check the verdict tape at
  `harness/policy-eval/verdict-tape/<ts>/REPORT.md` for which row produced an
  unexpected verdict, then either fix the analyst or update the annotation (the
  annotations are the contract; mismatch usually means analyst regression).
- **`make perf-test` hangs in docker** → same pattern as bench repo;
  `docker ps`, then `docker kill <id>`, then check `harness/perf/runner.py`
  for unbounded await.
- **`make perf-test-vs-bench` errors with "no bench results"** → assumes
  sibling `~/projects/openclaw-pipeline-bench/bench/results/<latest>/` exists.
  If not, pull the bench repo and `make bench-all` over there first.

---

## What this repo is NOT

- **Not an OpenClaw fork.** It does not implement governed-mode runtime
  substitution; it demonstrates the policy + prompt surface that would sit on
  top of one. If maintainers ask for a minimum reference runtime, that's
  Stage-2 work in a follow-up.
- **Not a vendor SDK.** No PyPI publish, no API stability promise. The
  manifest, YAML schemas, and policy composition rule are the contract.

---

## Where to post numbers

Comment on [openclaw/rfcs#11](https://github.com/openclaw/rfcs/pull/11). The
draft comment lives at
[`plans/pr-comment-when-impl-ships.md`](https://github.com/david-steeves/openclaw-pipeline-bench/blob/main/plans/pr-comment-when-impl-ships.md)
in the openclaw-pipeline-bench repo. Replace placeholders with real numbers,
include the Proof Shape table linking to specific test files at the
`rfc-0010-v1` tag's SHA.

---

If anything in this doc is wrong, fix it in place and commit. This file is the
contract between MacBook-implementation-Claude and M4-Pro-execution-Claude.
