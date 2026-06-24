"""
harness/policy_eval/runner.py

Functional test harness for the layered policy composition surface.

Reads:
  - mock-data/<dataset>/data.csv.gz
  - mock-data/<dataset>/annotations.yaml
  - teams/<team>/team.yaml (which analysts to load, in what severity_map)

Runs each row through the analyst chain for the team scoped to the dataset's
`data_class`. Composes verdicts via harness/policy_eval/composition.py.

Writes:
  - harness/policy_eval/verdict-tape/<ts>/REPORT.md (human-readable)
  - harness/policy_eval/verdict-tape/<ts>/<dataset>.jsonl (machine-readable;
    one verdict object per row)

USAGE:
    uv run --with pyyaml --with faker python -m harness.policy_eval.runner \\
        --dataset hr-pii --team pii-reviewer

If --dataset and --team omitted, runs the full default ladder.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import time
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any

from harness.policy_eval.composition import compose
from harness.policy_eval.loader import (
    iter_dataset_rows,
    load_analysts_for_team,
    load_annotations,
)
from harness.verdict import AnalystVerdict


DEFAULT_LADDER = [
    ("hr-pii", "pii-reviewer"),
    ("phi-snowflakey", "phi-reviewer"),
]


async def evaluate_row(row: dict[str, Any], analysts: list,
                       clarifications: dict[str, str] | None = None):
    """Run a single row through every analyst; return the AnalystVerdict list."""
    verdicts: list[AnalystVerdict] = []
    for analyst in analysts:
        # Some analysts accept clarifications kwarg; others don't.
        try:
            verdict = await analyst.evaluate(0, row, clarifications=clarifications)
        except TypeError:
            verdict = await analyst.evaluate(0, row)
        verdicts.append(verdict)
    return verdicts


def expected_verdict_for_row(row_index: int, annotations: dict,
                             clarifications: dict[str, str] | None = None) -> str | None:
    """
    Returns the documented expected verdict for the row index, taking
    clarification overlays into account. Returns None for "mixed" rows.
    """
    if clarifications:
        overlays = annotations.get("clarification_overlays", []) or []
        for overlay in overlays:
            if overlay.get("clarifications") == clarifications:
                for entry in overlay.get("expected_verdict_overrides", []):
                    lo, hi = entry["row_indices_range"]
                    if lo <= row_index <= hi:
                        v = entry["expected_verdict"]
                        return v if v.lower() != "mixed" else None

    for entry in annotations["annotations"]:
        lo, hi = entry["row_indices_range"]
        if lo <= row_index <= hi:
            v = entry["expected_verdict"]
            return v if v.lower() != "mixed" else None
    return None


async def run_dataset(dataset: str, team: str, out_dir: Path,
                      clarifications: dict[str, str] | None = None,
                      max_rows: int | None = None) -> dict:
    repo_root = Path(__file__).resolve().parents[2]
    data_path = repo_root / "mock-data" / dataset / "data.csv.gz"
    annotations = load_annotations(repo_root / "mock-data" / dataset / "annotations.yaml")
    analysts = load_analysts_for_team(repo_root, team)
    if not analysts:
        raise RuntimeError(f"no analysts loaded for team {team!r}")

    out_dir.mkdir(parents=True, exist_ok=True)
    label = dataset
    if clarifications:
        label = f"{dataset}_clar_{'_'.join(f'{k}={v}' for k, v in clarifications.items())}"
    jsonl_path = out_dir / f"{label}.jsonl"

    counts: Counter[str] = Counter()
    asserted_pass = 0
    asserted_fail = 0
    failures: list[tuple[int, str, str]] = []

    start = time.monotonic()
    with open(jsonl_path, "w") as f:
        for row_index, row in enumerate(iter_dataset_rows(data_path, max_rows=max_rows)):
            verdicts = await evaluate_row(row, analysts, clarifications=clarifications)
            result = compose(verdicts)
            counts[result.final_verdict] += 1

            expected = expected_verdict_for_row(row_index, annotations, clarifications)
            assertion = None
            if expected is not None:
                expected_l = expected.lower()
                if result.final_verdict == expected_l:
                    assertion = "ok"
                    asserted_pass += 1
                else:
                    assertion = f"FAIL expected={expected_l} got={result.final_verdict}"
                    asserted_fail += 1
                    failures.append((row_index, expected_l, result.final_verdict))

            f.write(json.dumps({
                "row_index": row_index,
                "final_verdict": result.final_verdict,
                "winning_layer": result.winning_layer,
                "winning_analyst": result.winning_analyst,
                "verdicts": [asdict(v) for v in result.verdicts],
                "advisory": [asdict(v) for v in result.advisory_after_system_block],
                "expected": expected,
                "assertion": assertion,
            }) + "\n")

    elapsed = time.monotonic() - start
    return {
        "dataset": dataset,
        "label": label,
        "team": team,
        "rows": sum(counts.values()),
        "counts": dict(counts),
        "asserted_pass": asserted_pass,
        "asserted_fail": asserted_fail,
        "failures": failures[:20],
        "elapsed_s": round(elapsed, 2),
        "clarifications": clarifications,
    }


def write_report(out_dir: Path, summaries: list[dict]):
    lines = [
        "# policy-eval verdict tape",
        "",
        f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}",
        "",
        "## Summary",
        "",
        "| Run | Team | Rows | PASS | WARN | BLOCK | Asserts (ok/fail) | Elapsed |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for s in summaries:
        c = s["counts"]
        lines.append(
            f"| {s['label']} | {s['team']} | {s['rows']} | "
            f"{c.get('pass', 0)} | {c.get('warn', 0)} | {c.get('block', 0)} | "
            f"{s['asserted_pass']} / {s['asserted_fail']} | {s['elapsed_s']}s |"
        )

    lines += ["", "## Sanity gates", "", "| Gate | Status |", "|---|---|"]
    all_pass = all(s["asserted_fail"] == 0 for s in summaries)
    lines.append(f"| 1. Annotated rows match documented verdicts | {'PASS' if all_pass else 'FAIL'} |")

    if any(s["failures"] for s in summaries):
        lines += ["", "## Failure samples (first 20 per run)", ""]
        for s in summaries:
            if not s["failures"]:
                continue
            lines.append(f"### {s['label']} / {s['team']}")
            lines.append("")
            lines.append("| Row | Expected | Got |")
            lines.append("|---|---|---|")
            for row_index, expected, got in s["failures"]:
                lines.append(f"| {row_index} | {expected} | {got} |")
            lines.append("")

    (out_dir / "REPORT.md").write_text("\n".join(lines) + "\n")


async def main_async(args):
    ts = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    out_dir = args.out / ts
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.dataset and args.team:
        ladder = [(args.dataset, args.team)]
    else:
        ladder = DEFAULT_LADDER

    summaries = []
    for dataset, team in ladder:
        summary = await run_dataset(dataset, team, out_dir, max_rows=args.max_rows)
        summaries.append(summary)
        print(
            f"[{dataset}/{team}] rows={summary['rows']} "
            f"asserts_pass={summary['asserted_pass']} "
            f"asserts_fail={summary['asserted_fail']}"
        )

    # Clarification overlay run for phi-snowflakey (suppression sanity gate).
    if any(d == "phi-snowflakey" for d, _ in ladder):
        clar = await run_dataset(
            "phi-snowflakey", "phi-reviewer", out_dir,
            clarifications={"phi-detection": "no"}, max_rows=args.max_rows,
        )
        summaries.append(clar)
        print(
            f"[clar phi-detection=no] rows={clar['rows']} "
            f"asserts_pass={clar['asserted_pass']} "
            f"asserts_fail={clar['asserted_fail']}"
        )

    write_report(out_dir, summaries)
    print(f"wrote {out_dir}/REPORT.md")
    if any(s["asserted_fail"] > 0 for s in summaries):
        print("FAIL: some assertions did not match documented verdicts.")
        raise SystemExit(1)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dataset", choices=["hr-pii", "phi-snowflakey"], default=None)
    p.add_argument("--team", choices=["pii-reviewer", "phi-reviewer"], default=None)
    p.add_argument("--out", type=Path,
                   default=Path(__file__).resolve().parent / "verdict-tape")
    p.add_argument("--max-rows", type=int, default=None,
                   help="cap rows per dataset for fast iteration")
    args = p.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
