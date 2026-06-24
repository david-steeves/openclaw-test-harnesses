## Where governance lives, and what we measured

Data governance in a claw runtime has to live somewhere. There are three honest places to put it: inside each claw (every claw author re-implements policy), inside OpenClaw proper (the runtime grows a governance surface), or inside the substrate the claws sit on. Each has a different cost-of-change shape. Per-claw is O(claws × policies) to maintain and audit, and the blast radius of a policy bug is the claw itself. In-runtime couples policy evolution to runtime release cadence and puts policy code in the same trust boundary as orchestration. Substrate factors the concern out once and lets it evolve on its own clock, with enforcement outside the claw's blast radius. RFC 0010 picks the substrate. The reasoning is architectural before it is empirical: this is the same factoring move as IAM versus per-service ACLs, VPC versus per-host iptables, or S3 server-side encryption versus per-caller crypto. Cross-cutting concerns belong in cross-cutting layers. The contribution of this RFC is not that OpenClaw should have governance — that need is uncontroversial. The contribution is where the seam goes, and the per-claw "governed mode" reframe is load-bearing: the Gateway substitutes a pipe-end for the claw's storage handle, the claw is unaware it is governed, and ACL enforcement lives outside the claw process. Hobbyist claws keep their file-share shape with zero overhead. Governed claws inherit the policy plane without code changes.

### Our cost

On M4 hardware, end-to-end, single-process, 100 events/sec offered load:

| Variant | p50 ms | p95 ms | p99 ms | Throughput | RSS MB |
|---|---|---|---|---|---|
| baseline (file-share, today's OpenClaw) | 0.80 | 1.80 | 2.18 | 100 eps | 26.2 |
| sqlite-flat substrate | 1.20 | 2.74 | 3.33 | 100 eps | 39.8 |
| pipeline-noop (3-stage, no analysts) | 8.31 | 10.68 | 11.55 | 100 eps | 79.5 |
| pipeline-fullcopy (faithful row promotion) | 10.10 | 12.31 | 13.07 | 100 eps | 41.6 |
| pipeline + real PII analysts, pass-only | 8.97 | 11.10 | 12.01 | 72 eps | 62.1 |
| pipeline + real PII analysts, 5% block | 8.90 | 11.30 | 12.34 | 72 eps | 61.8 |

This is what factoring governance into the substrate costs in this implementation: roughly 8 ms p50 at the pipeline boundary, climbing to ~9 ms p50 with real PII review-team analysts (regex SSN, name+DOB cooccurrence) in the loop, p99 under 13 ms, and throughput drops from 100 eps to 72 eps when the analysts are doing actual work. Correctness ground: 1800/1800 row-level policy assertions pass, 14/14 pytest tests pass. The bench harness and the analyst skills are in the PR; methodology is open to direct critique.

### What we did not measure

We have not benchmarked the per-claw or in-runtime factorings on the same workload, and we are not going to estimate their cost. If anyone runs governance-in-the-runtime or governance-per-claw against the same offered load with comparable analyst work, we will publish the three tables next to each other and discuss the comparison on data.

### Why this design pays back: evolution

The substrate placement gives us a stable analyst-skill extension point. The substrate defines the analyst interface; detection logic is a skill that conforms to it. Today the review team ships regex SSN detection and a name+DOB cooccurrence rule. Tomorrow that same seam carries an ML-based PII classifier, a federated policy bundle for a regulated tenant, or a new analyst class for a new claw category — and each lands as an additive registry change, not a runtime fork and not a coordinated claw upgrade. The substrate stays boring. The policy plane is where work compounds. People who improve detection never touch claw code, never cut a runtime release, and never coordinate with claw authors. The cost of a better detector is a PR against a skill. That is the cost-of-governance curve we want this project to be on over the next several years, and the substrate is the only one of the three factorings that produces it.

### Ask of maintainers

We are not asking for a ship decision. We are asking for direction on a specific question: do you accept the substrate as the governance seam for OpenClaw, given that per-claw "governed mode" is opt-in and leaves the hobbyist file-share path unchanged? If yes, we will sequence the implementation work against the RFC and come back with a staged plan. If no, tell us which seam you would take instead — runtime, per-claw, or somewhere we have not named — and we will redesign against it. Either answer is useful. We will hold here until we hear which factoring you want to own.
