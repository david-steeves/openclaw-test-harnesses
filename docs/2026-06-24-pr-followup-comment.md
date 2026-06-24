Coming back to this thread with more evidence rather than letting it drop. Earlier in the discussion I posted bench numbers from a MacBook rig and the per-claw "governed mode" reframe; I've since built reference review teams against that design, reproduced the numbers on independent hardware, and — more importantly — spent some time on the argument I think the RFC actually needs to be making. Trying to lead with that part this time instead of the table.

## Where governance lives

The architectural claim under RFC 0010 is narrower than I phrased it the first time, and I want to restate it cleanly.

Data governance in a claw runtime has to live somewhere. There are three honest places to put it: inside each claw (every claw author re-implements policy), inside OpenClaw proper (the runtime grows a governance surface), or inside the substrate the claws sit on. Each has a different cost-of-change shape. Per-claw is O(claws × policies) to maintain and audit, and the blast radius of a policy bug is the claw itself. In-runtime couples policy evolution to runtime release cadence and puts policy code in the same trust boundary as orchestration. Substrate factors the concern out once and lets it evolve on its own clock, with enforcement outside the claw's blast radius.

RFC 0010 picks the substrate. The reasoning is architectural before it is empirical: this is the same factoring move as IAM versus per-service ACLs, VPC security groups versus per-host iptables, or S3 server-side encryption versus per-caller crypto. Cross-cutting concerns belong in cross-cutting layers.

The contribution of this RFC is not that OpenClaw should have governance — that need is uncontroversial. The contribution is *where the seam goes*. The per-claw "governed mode" reframe from the earlier comment is load-bearing here: the Gateway substitutes a pipe-end for the claw's storage handle, the claw is unaware it is governed, and ACL enforcement lives outside the claw process. Hobbyist claws keep their file-share shape with zero overhead. Governed claws inherit the policy plane without code changes.

That's the whole proposal. Everything below is just trying to show I haven't waved my hands at the cost.

## What it costs (M4, reproduced)

End-to-end, single-process, 512B payloads, 10 concurrent synthetic agents, 100 events/sec offered load:

| Variant | p50 ms | p95 ms | p99 ms | Throughput | RSS MB |
|---|---|---|---|---|---|
| baseline (file-share, today's OpenClaw) | 0.80 | 1.80 | 2.18 | 100 eps | 26.2 |
| sqlite-flat substrate | 1.20 | 2.74 | 3.33 | 100 eps | 39.8 |
| pipeline-noop (3-stage, no analysts) | 8.31 | 10.68 | 11.55 | 100 eps | 79.5 |
| pipeline-fullcopy (faithful row promotion) | 10.10 | 12.31 | 13.07 | 100 eps | 41.6 |
| pipeline + real PII analysts, pass-only | 8.97 | 11.10 | 12.01 | 72 eps | 62.1 |
| pipeline + real PII analysts, 5% block | 8.90 | 11.30 | 12.34 | 72 eps | 61.8 |

Roughly 8 ms p50 at the pipeline boundary, climbing to ~9 ms p50 with real PII review-team analysts (regex SSN, name+DOB cooccurrence) in the loop. p99 stays under 13 ms. Throughput drops from 100 eps to 72 eps once analysts are doing actual work.

Correctness ground: 1800/1800 row-level policy assertions pass against Workday-shaped HR PII + Synthea-shaped PHI mock data, 14/14 pytest tests pass. The (slight) p50 inversion between pass-only and 5% block is inside the ~±0.2 ms run-to-run floor — not a free lunch, just noise.

These are the same numbers I posted from the earlier rig. Independent hardware, same shape. I'll take that as cheap confirmation that the bench isn't a hardware artifact.

## What I did not measure

Honest about this part. I have not benchmarked the per-claw or in-runtime factorings on the same workload, and I'm not going to estimate their cost — I don't trust hand-wavy comparisons against my own preferred design. If anyone runs governance-in-the-runtime or governance-per-claw against the same offered load with comparable analyst work, I'll publish the three tables next to each other and we can discuss on data. (Genuinely an invitation — I'd rather find out the substrate placement is wrong now than after someone builds against it.)

Also unmeasured: signed evidence at seam transitions, supply-chain integrity of analyst skills themselves, TOCTOU windows between policy evaluation and row promotion, ReDoS resistance of the regex detectors, behavior under sustained high-block-rate, SQLite write contention beyond 10 concurrent agents. The current numbers prove the happy path. They do not prove the system resists a motivated attacker, and I don't want to pretend otherwise.

## Why the substrate placement pays back over time

The thing I keep coming back to is the evolution shape. The substrate defines the analyst interface; detection logic is a skill that conforms to it. Today the review team ships regex SSN detection and a name+DOB cooccurrence rule. Tomorrow that same seam carries an ML-based PII classifier, a federated policy bundle for a regulated tenant, or a new analyst class for a new claw category — and each lands as an additive registry change, not a runtime fork and not a coordinated claw upgrade.

The substrate stays boring. The policy plane is where work compounds. People who improve detection never touch claw code, never cut a runtime release, and never coordinate with claw authors. The cost of a better detector is a PR against a skill.

That's the cost-of-governance curve I think this project wants to be on over the next several years, and the substrate is the only one of the three factorings I've named that produces it. (If there's a fourth factoring I haven't named — I'm a first-time contributor here, I might well have missed prior art — I'd genuinely like the pointer.)

## The narrow ask

I'm not asking for a ship decision. I'm asking for direction on one specific question:

**Do you accept the substrate as the governance seam for OpenClaw, given that per-claw "governed mode" is opt-in and leaves the hobbyist file-share path unchanged?**

If yes, I'll sequence the implementation work against the RFC and come back with a staged plan. If no, please tell me which seam you would take instead — runtime, per-claw, or somewhere I haven't named — and I'll redesign against it. Either answer is useful to me. I'd rather hear "wrong seam, here's the right one" than spend another round building against the wrong factoring.

I'll hold here until I hear which factoring you want to own.

## Repo references

- Reference review teams + policy/perf harness: https://github.com/david-steeves/openclaw-test-harnesses — pinned at `openclaw-test-harnesses@23a42f8`. MIT, synthetic data only, no service to sell.
- Bench harness: https://github.com/david-steeves/openclaw-pipeline-bench — pinned at `openclaw-pipeline-bench@0c38e2a`. Methodology is open to direct critique; the `make` targets reproduce the table above.

Both repos are public. Happy to walk through any specific row in the table, any specific assertion in the policy-eval harness, or any specific architectural call if it'd help — just say where to point.
