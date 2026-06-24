"""
scripts/generate_comparison_report.py

Reads:
  - <results_dir>/pipeline-real-claws/run-*.json (this repo's perf output)
  - <results_dir>/pipeline-real-claws-pass-only/run-*.json (optional)
  - <openclaw-pipeline-bench results>/<variant>/run-*.json (reference)

Emits:
  - <results_dir>/COMPARISON.md — side-by-side table for the follow-up PR comment.

USAGE:
    uv run --with pyyaml python scripts/generate_comparison_report.py \\
        --results-dir bench/results/<ts> \\
        --bench-results ~/projects/openclaw-pipeline-bench/bench/results/<latest>
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
from pathlib import Path


VARIANT_ORDER_FROM_BENCH = [
    "baseline",
    "sqlite-flat",
    "pipeline-noop",
    "pipeline-fullcopy",
    "pipeline-1-analyst",
    "pipeline-blocking",
]
LOCAL_VARIANTS = [
    "pipeline-real-claws-pass-only",
    "pipeline-real-claws",
]


def load_variant_results(results_dir: Path, variant: str) -> dict | None:
    v_dir = results_dir / variant
    if not v_dir.exists():
        return None
    runs = sorted(v_dir.glob("run-*.json"))
    if not runs:
        return None
    p50s, p95s, p99s, rss_peaks, tputs = [], [], [], [], []
    for r in runs:
        data = json.loads(r.read_text())
        lat = data.get("latency_ms", {})
        if lat.get("p50") is not None:
            p50s.append(lat["p50"])
        if lat.get("p95") is not None:
            p95s.append(lat["p95"])
        if lat.get("p99") is not None:
            p99s.append(lat["p99"])
        rss = data.get("rss_mb", {})
        if rss.get("peak") is not None:
            rss_peaks.append(rss["peak"])
        if data.get("throughput_eps") is not None:
            tputs.append(data["throughput_eps"])

    def med_or_none(xs):
        return round(statistics.median(xs), 3) if xs else None

    return {
        "variant": variant,
        "runs": len(runs),
        "p50": med_or_none(p50s),
        "p95": med_or_none(p95s),
        "p99": med_or_none(p99s),
        "rss_peak_mb": med_or_none(rss_peaks),
        "throughput_eps": med_or_none(tputs),
    }


def fmt(x):
    return "-" if x is None else f"{x}"


def build_report(local_dir: Path, bench_dir: Path | None) -> str:
    lines = [
        "# pipeline-real-claws vs openclaw-pipeline-bench reference",
        "",
        f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}",
        "",
        f"- Local results: `{local_dir}`",
        f"- Bench reference: `{bench_dir or '(not provided)'}`",
        "",
        "## Headline paragraph",
        "",
        "TODO: write this by hand once the numbers are in. Suggested shape:",
        "",
        "> *The substrate cost from RFC 0010 is X (pipeline-noop). With one synthetic",
        "> pass-analyst per seam, it's X + S. With the real review teams loaded",
        "> (pii-reviewer + phi-reviewer), it's X + R. The 'governed mode' opt-in",
        "> design pays for X + R only on claws that need it; other claws stay on the",
        "> baseline substrate cost.*",
        "",
        "## Latency p50 / p95 / p99 (medians across runs)",
        "",
        "| Variant | Source | Runs | p50 (ms) | p95 (ms) | p99 (ms) | RSS peak (MB) | Throughput (eps) |",
        "|---|---|---|---|---|---|---|---|",
    ]

    if bench_dir is not None:
        for v in VARIANT_ORDER_FROM_BENCH:
            r = load_variant_results(bench_dir, v)
            if r is None:
                continue
            lines.append(
                f"| {v} | bench | {r['runs']} | {fmt(r['p50'])} | {fmt(r['p95'])} | "
                f"{fmt(r['p99'])} | {fmt(r['rss_peak_mb'])} | {fmt(r['throughput_eps'])} |"
            )

    for v in LOCAL_VARIANTS:
        r = load_variant_results(local_dir, v)
        if r is None:
            continue
        lines.append(
            f"| {v} | this repo | {r['runs']} | {fmt(r['p50'])} | {fmt(r['p95'])} | "
            f"{fmt(r['p99'])} | {fmt(r['rss_peak_mb'])} | {fmt(r['throughput_eps'])} |"
        )

    # Monotonicity gate
    lines += [
        "",
        "## Sanity gates",
        "",
        "| Gate | Status |",
        "|---|---|",
    ]
    noop = load_variant_results(bench_dir, "pipeline-noop") if bench_dir else None
    pass_only = load_variant_results(local_dir, "pipeline-real-claws-pass-only")
    mixed = load_variant_results(local_dir, "pipeline-real-claws")
    monotonic = "n/a"
    if noop and pass_only and mixed:
        p50s = [noop["p50"], pass_only["p50"], mixed["p50"]]
        if all(p is not None for p in p50s):
            monotonic = "PASS" if p50s == sorted(p50s) else f"FAIL ({p50s})"
    lines.append(f"| Perf monotonicity (noop ≤ real-claws-pass-only ≤ real-claws) | {monotonic} |")

    if noop and mixed and noop.get("p50") is not None and mixed.get("p50") is not None:
        delta = round(mixed["p50"] - noop["p50"], 3)
        lines.append(f"| Real-claw cost delta (p50) | {delta} ms |")

    return "\n".join(lines) + "\n"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--results-dir", type=Path, required=True,
                   help="this repo's results dir (contains pipeline-real-claws/run-*.json)")
    p.add_argument("--bench-results", type=Path, default=None,
                   help="openclaw-pipeline-bench results dir (e.g. ~/projects/openclaw-pipeline-bench/bench/results/<ts>)")
    p.add_argument("--out", type=Path, default=None,
                   help="output path (default: <results-dir>/COMPARISON.md)")
    args = p.parse_args()

    report = build_report(args.results_dir, args.bench_results)
    out = args.out or (args.results_dir / "COMPARISON.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(report)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
