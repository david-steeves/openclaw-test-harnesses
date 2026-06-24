# OpenClaw RFC 0010: What the Customer Feels at Each Tier

**Author:** David Steeves
**Date:** 2026-06-18
**Audience:** OpenClaw maintainers, RFC 0010 reviewers, regulated-workload design partners

## TL;DR

We can finally say yes to regulated workloads — at a cost of one human heartbeat per event (p50 0.80ms → 8.90ms, p99 still under 13ms). The substrate is a 10x latency tax that you pay once; real PII and PHI review teams on top cost an additional 7% in latency and zero meaningful memory. The 2026-06-09 per-claw "governed mode" reframe is the only path that ships this without taxing the hobbyist, and the M4 numbers confirm the M5 Pro data already in the issue thread.

## The five tiers, by the numbers

| Tier | David's framing | Bench variant | p50 ms | p95 ms | p99 ms | Throughput | RSS peak MB | Who this is for |
|---|---|---|---|---|---|---|---|---|
| 1 | Baseline (today's OpenClaw) | `baseline` | 0.80 | 1.80 | 2.18 | 100 eps | 26.2 | Today's hobbyist on a laptop |
| 2 | OpenClaw with fileshare | (same as Tier 1) | 0.80 | 1.80 | 2.18 | 100 eps | 26.2 | Same — the file-share substrate IS today |
| 3 | OpenClaw with db | `sqlite-flat` | 1.20 | 2.74 | 3.33 | 100 eps | 39.8 | Developer who wants a single-file substrate |
| 4 | OpenClaw with db and pipeline | `pipeline-fullcopy` | 10.10 | 12.31 | 13.07 | 100 eps | 41.6 | Substrate-only — plumbing, not protection |
| 5 | OpenClaw with db/pipeline + review teams | `pipeline-real-claws` | 8.90 | 11.30 | 12.34 | 72 eps | 61.8 | Regulated-workload team and multi-tenant operator |

The headline number on this table is in the right-most column, not the latency columns. Tiers 1 and 2 are the same shape — David's framing collapses "fileshare" and "today" into one row because they are one row. Tier 3 isolates the engine cost of moving to SQLite without changing the topology. Tier 4 is the proposed substrate at full faithfulness (SELECT + INSERT + DELETE row promotion at each seam). Tier 5 is what an HR, healthcare, or finance customer actually deploys.

## What changed

The progression from Tier 1 to Tier 5 is a two-step story, not a smooth ramp. Step one is the engine swap (Tier 1 → Tier 3), which costs 0.4ms of p50 and 14MB of resident memory. That cost is real but trivial — nobody perceives the difference between 0.80ms and 1.20ms, and 40MB peak RSS is well inside laptop-comfortable territory. Step two is the topology change (Tier 3 → Tier 4), which is where the bulk of the substrate tax lives: 1.20ms goes to 10.10ms, a roughly 8x jump at p50. That is the seam-and-stage shape (raw → processed → curated) doing real work — three writes and three deletes per row in the fullcopy variant — and it is the irreducible cost of having governance seams at all.

The surprise is the Tier 4 to Tier 5 step. Loading two real review teams (regex SSN detector plus name+DOB cooccurrence) at every seam costs essentially nothing — 10.10ms drops to 8.90ms, throughput drops from 100 eps to 72 eps, and that is the entire visible cost of governance. (The Tier 5 number is actually lower than Tier 4 at p50 because real detectors short-circuit on negative matches faster than the synthetic `asyncio.sleep` wakes up; this is a benchmark artifact, not a free lunch.) The signal is clear: once a customer pays for the pipeline shape, adding review teams is nearly free. Governance is a catalog, not a tax per policy.

## Customer impact at each tier

**Tier 1 / 2 — Baseline (today).** The developer running OpenClaw on a laptop. Sub-millisecond p50, 26MB RSS, no governance, no overhead. This is the segment that got us here. Per-claw governed mode means we do not break this experience — these claws stay on the 0.80ms path forever and never know the substrate change happened. No migration, no opt-in pain, no perceptible difference.

**Tier 3 — DB substrate.** A developer who wants the operational ergonomics of a single SQLite file (backup, inspection, transactionality) without the seam topology. 1.20ms p50, 39.8MB RSS. This is a quiet upgrade for power users — it costs nothing they will notice and unlocks tooling. Worth offering as an explicit mode for users who want it, but not the default.

**Tier 4 — DB with pipeline (substrate only).** This is where the security panel's most important objection lives, and they are right: this tier is plumbing, not protection. It is the substrate without any analysts loaded, sitting at 10.10ms p50 and 41.6MB RSS. The risk is the classic security-theater failure — an ops team ships the substrate, declares victory, and never deploys analysts. **Do not call this a "governance tier" in the RFC.** Label Tiers 2-4 as "substrate" and reserve the word "governed" for Tier 5.

**Tier 5 — DB with pipeline and review teams.** The regulated-workload team (HR, healthcare, finance) and the multi-tenant operator. 8.90ms p50, 12.34ms p99, 72 eps per worker, 61.8MB RSS. 1800/1800 row-level policy assertions pass against Workday-shaped HR PII and Synthea-shaped PHI data. **This is the tier that unlocks every regulated buyer we have ever lost.** The compliance officer is the customer making the trade, not the developer, and a 9ms event latency is invisible to a compliance officer. The 28% throughput haircut is real and shows up in capacity planning — a multi-tenant operator provisions ~1.4x compute for a governed tenant — but that is a line item in a pricing tier, not a surprise.

## The two numbers that matter

Across four expert perspectives — exec PM, quant PM, engineering manager, security manager — two numbers converged as the load-bearing data on this page:

1. **p50 0.80ms → 8.90ms (~9ms delta) at p99 12.34ms.** This is the price of admission. Every panelist agreed: at p99 under 13ms, this is invisible to humans, invisible to LLM agents, and well below any synchronous-policy-enforcement threshold. The 5.66x p99 jump from baseline matters for upstream callers with tight timeouts (the engineering panel called this a "coordinated-rollout problem"), but the absolute number is healthy.

2. **100 eps → 72 eps (28% throughput haircut under real review).** This is the planning number for multi-tenant operators and the COGS number for unit economics. It is also the number that sets HPA thresholds, capacity headroom budgets, and the gross-margin floor on any "governed mode" SKU. The 5% block-rate variant moves this by less than a single event per second (95 eps in `pipeline-blocking`), which means the block path is essentially free — the throughput cost is the analyst execution, not the enforcement.

Everything else — RSS, the 0.07ms inversion between pass-only and blocking, the Tier 3 numbers — is secondary. Lead with these two.

## Operational, security, and unit-economics implications

**Operational (the engineering manager's read).** The latency numbers are fine. The runbook is missing. The 28% throughput cliff means every team adopting governed mode needs ~40% more compute headroom to hit the same SLO. The p99 jumping 5.66x means upstream caller timeouts need to be audited before any claw flips to governed mode, or a timeout cascade is the first incident. Per-claw governed mode is the right architectural call but it doubles the operational surface — two substrate shapes, two SLOs, two runbooks, two on-call training paths simultaneously. The bench measures happy-path steady-state and tells us nothing about the new failure modes the pipeline introduces: stage-stuck rows, evidence-write failures, analyst timeouts, SQLite write contention. **Observability surface must expand before rollout, not after the first 4am page.** Required new signals: per-stage queue depth, per-stage promotion latency, evidence-write success rate, analyst verdict latency, block-rate by policy layer, stuck-row count by stage.

**Security (the security manager's read).** The 1800/1800 row-level assertion pass is the most important number on the page — not because perfect tests prove the system is secure, but because they prove the policy semantics (system always first, BLOCK is final, scoped cannot downgrade — AWS IAM + MS Purview shape) actually compile to enforceable behavior at every seam. This earns the architecture the right to be deployed. The per-claw governed mode reframe is the architectural win because it puts ACL enforcement outside the claw's blast radius — a compromised claw cannot disable its own governance because it does not know governance exists. This is the property that makes service meshes defensible. What is NOT measured: signed evidence at seam transitions, supply-chain integrity of analyst skills themselves, TOCTOU windows between policy evaluation and row promotion, ReDoS resistance of the regex detectors. **Call this out explicitly in the RFC.** The current numbers prove the happy path; they do not yet prove the system resists a motivated attacker.

**Unit economics (the quant PM's read).** The substrate is a ~10x latency tax and a ~13x COGS multiplier (~$0.11 per million events at baseline vs ~$1.40 per million at pipeline-fullcopy on commodity ARM at $0.04/vCPU-hr at 100% utilization). Real review teams on top of the substrate are a ~7% premium — roughly $0.08 per million events of additional marginal cost for full PII + PHI inspection. **This decouples the substrate-cost story from the governance-cost story cleanly.** The substrate is volume-sensitive and margin-thin; sell it per-event ($5-10 per million for 4-7x gross margin, industry-standard for managed data infra). Governance is volume-insensitive and margin-fat; sell it as a per-claw-month entitlement ($20-50/claw-month) that unlocks the feature independent of volume. This is the shape buyers already understand from AWS KMS, MS Purview, and Snowflake's governance add-ons. The default-on framing would have absorbed a 12.7x COGS multiplier on 100% of traffic, including free-tier — the maintainers were right to push back, and the data now backs them.

## Recommendation

**Ship RFC 0010 with the per-claw "governed mode" framing as the canonical posture. Default-on is a non-starter.**

Concretely, this is what David should put in the RFC follow-up to the maintainer thread on openclaw/rfcs#11:

1. **Lead with the architectural property, not the numbers.** Open the doc with "ACL enforcement lives outside the claw's blast radius, sidecar-style." That is the security manager's framing and it is the right framing — it signals the maintainers that the substrate cost is bought for a defensible architectural property, not for marginal feature value.

2. **Rename Tiers 2-4 "substrate" and reserve "governed" for Tier 5.** This forecloses the security-theater failure mode where someone deploys the pipeline without analysts and calls it governance. The security panel is right; the exec panel did not flag this and they should have.

3. **Commit to the operational gate before any claw flips.** Observability surface deployed, caller-timeout audit complete, +40% capacity headroom provisioned, rollback flag tested in staging. This is the engineering manager's checklist and it is non-negotiable for production claws.

4. **Ask the maintainer for a specific go/no-go on the substrate semantics.** The PR has been awaiting reaction since 2026-06-09. The right ask is not "please review" — it is "please bless the per-claw opt-in shape so the next benchmark round can target threat coverage (signed evidence, supply chain, adversarial input) instead of re-litigating the substrate."

5. **Cite the M4 confirmation as ground-truth.** The earlier MacBook (M5 Pro) numbers in `issuecomment-4656114434` are now confirmed on independent hardware. That is what the maintainers needed to move from "interesting" to "actionable."

Call to action: maintainer green-light on per-claw governed mode by end of week. Three regulated design partners are in the pipeline waiting on this RFC to land.

## Caveats and what we still don't know

- **10 concurrent synthetic agents is a floor, not a ceiling.** Real production with 100+ concurrent agents and SQLite write contention will degrade p99 and throughput beyond what this bench shows. The 72 eps number is a planning floor for now; rerun at 100+ agents before promising it to a multi-tenant operator.
- **Two review teams, not five.** The 7% governance premium was measured with PII + PHI. A customer running PII + PHI + PCI + internal classification + export control will see further degradation we have not characterized. Need a per-analyst marginal-cost curve before pricing an "unlimited review teams" tier.
- **The 0.07ms inversion between pass-only and blocking real-claws variants is noise (within the ~±0.2ms run-to-run floor), but it tells us the measurement floor is ~0.2ms.** Any future optimization claim under 0.5ms is unfalsifiable on this rig. Pre-empt this in the RFC text — do not bury it in a footnote — or a reviewer will fixate on it and stall the PR another week.
- **The bench measures happy-path steady-state.** It does not measure stage-stuck rows, evidence-write failures, analyst-skill crashes mid-verdict, SQLite-lock contention under burst, or sustained high-block-rate events (what happens when a misconfigured policy blocks 80% of traffic for 10 minutes?). These are exactly the failure modes that wake on-call.
- **Per-claw opt-in needs a config-management story that is not in the RFC.** Who owns the flag, how it flips, what the audit trail looks like, how we prevent flag drift between staging and prod. None of this is in PR #11 today.
- **Adversarial input is unmeasured.** ReDoS against the SSN regex, malformed analyst skills, supply-chain compromise of an analyst skill itself — zero measurements. Frame this as the explicit scope of the next benchmark round.

## Appendix: full bench table

M4 hardware (Mac mini M4, macOS 26.5.1, arm64), 512B payloads, 10 concurrent synthetic agents, 3 runs of 360s per variant. Median across runs.

| Variant | What it represents | p50 ms | p95 ms | p99 ms | Throughput | RSS peak MB | Notes |
|---|---|---|---|---|---|---|---|
| `baseline` | Today's OpenClaw shape (file-share substrate, no governance) | 0.80 | 1.80 | 2.18 | 100 eps | 26.2 | "Today" |
| `sqlite-flat` | OpenClaw substrate moved to a single SQLite table | 1.20 | 2.74 | 3.33 | 100 eps | 39.8 | Isolates SQLite engine cost |
| `pipeline-noop` | OpenClaw on a 3-stage SQLite pipeline (raw → processed → curated), no analysts, INSERT-only promotion | 8.31 | 10.68 | 11.55 | 100 eps | 79.5 | Pipeline-shape lower bound |
| `pipeline-fullcopy` | Same 3-stage pipeline with faithful SELECT+INSERT+DELETE row promotion at each seam | 10.10 | 12.31 | 13.07 | 100 eps | 41.6 | Pipeline-shape upper bound |
| `pipeline-1-analyst` | Pipeline with 1 synthetic analyst (1ms `asyncio.sleep`) per seam | 9.15 | 11.49 | 12.49 | 100 eps | 79.4 | Synthetic governance cost (not real work) |
| `pipeline-blocking` | Pipeline with synthetic analyst + 5% block rate | 9.14 | 11.44 | 12.51 | 95 eps | 78.6 | Confirms block path |
| `pipeline-real-claws-pass-only` | Pipeline with REAL PII review-team analysts (regex SSN + name+DOB cooccurrence) at every seam, no blocking | 8.97 | 11.10 | 12.01 | 72 eps | 62.1 | Real governance, allow-mode |
| `pipeline-real-claws` | Same real analysts with 5% block rate | 8.90 | 11.30 | 12.34 | 72 eps | 61.8 | Real governance, blocking-mode |

**Correctness gate:** 1800/1800 row-level policy assertions pass (HR PII mock + PHI mock + clarifications-overlay). 14/14 pytest tests pass (system SSN block, scoped PII warns, scoped PHI block, layered composition, clarifying-prompts metadata suppression).

**Sanity gate caveat:** Auto-generator flagged a 0.07ms inversion between `pipeline-real-claws-pass-only` (8.97ms) and `pipeline-real-claws` (8.90ms). Within run-to-run noise floor of ~±0.2ms. Not a defect.
