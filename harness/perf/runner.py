"""
harness/perf/runner.py

Perf runner for openclaw-test-harnesses' pipeline-real-claws variant.

Architecture: this module owns the substrate (SQLite 3-stage pipeline,
identical pragmas to openclaw-pipeline-bench/bench/harness/substrates/sqlite_pipeline.py)
but plugs in *real* analysts from teams/pii-reviewer + teams/phi-reviewer at the
seams. Workload events come from harness/perf/workload_from_mock.py (replays
mock CSV rows) instead of synthetic filler strings.

Why not just import the bench substrate?
  - The bench substrate's PassAnalyst expects a (cost_ms, evidence_conn) ctor.
    Our real-claw analysts have a richer interface and don't sleep.
  - We adapt by writing a thin substrate here that mirrors the bench's seam
    contract (await analyst.evaluate -> "pass" | "block") but invokes our
    analysts. The latency profile is directly comparable to bench's
    pipeline-1-analyst because the only thing that changes is the analyst body.

USAGE (smoke):
    cd harness/perf
    uv run --with psutil --with pyyaml python runner.py \\
        --variant pipeline-real-claws --duration 10 --in-memory \\
        --manifest manifest.yaml

The output mirrors the bench's RESULT line so scripts/generate_comparison_report.py
can ingest both.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib.util
import json
import os
import sqlite3
import statistics
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import psutil
import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]


# -----------------------------------------------------------------------------
# Config dataclasses
# -----------------------------------------------------------------------------

@dataclass
class WorkloadConfig:
    agents: int
    events_per_agent_per_sec: int
    event_payload_bytes: int
    read_back_window: int
    warmup_seconds: int
    steady_state_seconds: int


@dataclass
class VariantConfig:
    id: str
    substrate: str
    pipeline_stages: list[str]
    analysts: list[dict[str, Any]] = field(default_factory=list)


def load_manifest(manifest_path: Path) -> dict[str, Any]:
    with open(manifest_path) as f:
        return yaml.safe_load(f)


def get_workload(manifest: dict[str, Any]) -> WorkloadConfig:
    w = manifest["workload"]
    return WorkloadConfig(
        agents=w["agents"],
        events_per_agent_per_sec=w["events_per_agent_per_sec"],
        event_payload_bytes=w["event_payload_bytes"],
        read_back_window=w["read_back_window"],
        warmup_seconds=w["warmup_seconds"],
        steady_state_seconds=w["steady_state_seconds"],
    )


def get_variant(manifest: dict[str, Any], variant_id: str) -> VariantConfig:
    for v in manifest["variants"]:
        if v["id"] == variant_id:
            return VariantConfig(
                id=v["id"],
                substrate=v["substrate"],
                pipeline_stages=v.get("pipeline_stages", []),
                analysts=v.get("analysts", []),
            )
    raise KeyError(f"variant {variant_id!r} not in manifest")


# -----------------------------------------------------------------------------
# Analyst dynamic loader (file-path based; teams/ uses hyphens)
# -----------------------------------------------------------------------------

ANALYST_CLASSES = {
    "teams/pii-reviewer/analysts/ssn_detector.py": "SsnDetector",
    "teams/pii-reviewer/analysts/pii_cooccurrence_warn.py": "PiiCooccurrenceWarn",
    "teams/pii-reviewer/analysts/salary_warn.py": "SalaryWarn",
    "teams/phi-reviewer/analysts/phi_marker_block.py": "PhiMarkerBlock",
    "teams/phi-reviewer/analysts/patient_id_warn.py": "PatientIdWarn",
    "teams/phi-reviewer/analysts/free_text_phi_scan.py": "FreeTextPhiScan",
}


def _load_analyst(rel_module_path: str):
    abs_path = REPO_ROOT / rel_module_path
    if not abs_path.exists():
        raise FileNotFoundError(abs_path)
    mod_name = rel_module_path.replace("/", ".").replace("-", "_").rsplit(".py", 1)[0]
    spec = importlib.util.spec_from_file_location(mod_name, abs_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    class_name = ANALYST_CLASSES[rel_module_path]
    return getattr(module, class_name)()


# -----------------------------------------------------------------------------
# Substrate — mirrors openclaw-pipeline-bench/bench/harness/substrates/sqlite_pipeline.py
# but plugs in our analysts.
# -----------------------------------------------------------------------------

def _open_db(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("PRAGMA cache_size=-64000")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id INTEGER NOT NULL,
            payload TEXT NOT NULL,
            ts REAL NOT NULL
        )
    """)
    return conn


def _open_evidence(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path, isolation_level=None, check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS evidence (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            seam TEXT NOT NULL,
            analyst TEXT NOT NULL,
            verdict TEXT NOT NULL,
            rule TEXT,
            ts REAL NOT NULL
        )
    """)
    return conn


class RealClawSubstrate:
    """3-stage SQLite pipeline with real-claw analysts at seams."""

    def __init__(self, stages: list[str], analyst_specs: list[dict],
                 in_memory: bool = False):
        self.stages = stages or ["raw", "processed", "curated"]
        self.in_memory = in_memory
        if in_memory:
            self._tmpdir = tempfile.TemporaryDirectory(prefix="real-claws-")
            root_dir = Path(self._tmpdir.name)
        else:
            self._tmpdir = None
            root_dir = Path(os.environ.get("PIPELINE_ROOT", "/data"))
            root_dir.mkdir(parents=True, exist_ok=True)

        def db_path(name: str) -> str:
            return str(root_dir / f"{name}.db")

        self._conns = {stage: _open_db(db_path(stage)) for stage in self.stages}
        self._locks = {stage: threading.Lock() for stage in self.stages}
        self._evidence = _open_evidence(db_path("evidence"))
        self._evidence_lock = threading.Lock()

        # Register analysts per seam.
        self._seam_analysts: dict[str, list] = {}
        for spec in analyst_specs:
            seam = spec["seam"]
            module_path = spec["module"]
            analyst = _load_analyst(module_path)
            self._seam_analysts.setdefault(seam, []).append(analyst)

    async def emit(self, agent_id: int, payload: str) -> dict:
        await asyncio.to_thread(self._insert, "raw", agent_id, payload)

        for i in range(len(self.stages) - 1):
            src, dst = self.stages[i], self.stages[i + 1]
            seam = f"{src}_to_{dst}"
            # Parse payload once per seam (analysts may need dict form).
            payload_dict = self._maybe_dict(payload)
            for analyst in self._seam_analysts.get(seam, []):
                # Real-claw evaluate -> AnalystVerdict
                verdict_obj = await analyst.evaluate(agent_id, payload_dict)
                await asyncio.to_thread(self._write_evidence, seam, verdict_obj)
                if verdict_obj.verdict == "block":
                    return {"verdict": "block", "seam": seam}
            if not self._seam_analysts.get(seam):
                await asyncio.to_thread(self._stamp_empty, seam)
            await asyncio.to_thread(self._insert, dst, agent_id, payload)

        return {"verdict": "pass"}

    @staticmethod
    def _maybe_dict(payload: str):
        # The bench's old payload shape is a synthetic JSON-shaped string; our
        # workload_from_mock.py emits a real JSON dict-of-strings. Try to parse.
        try:
            obj = json.loads(payload)
            if isinstance(obj, dict):
                return obj
        except Exception:
            pass
        return payload

    def _insert(self, stage: str, agent_id: int, payload: str):
        with self._locks[stage]:
            self._conns[stage].execute(
                "INSERT INTO items (agent_id, payload, ts) VALUES (?, ?, ?)",
                (agent_id, payload, time.time()),
            )

    def _write_evidence(self, seam: str, v):
        with self._evidence_lock:
            self._evidence.execute(
                "INSERT INTO evidence (seam, analyst, verdict, rule, ts) VALUES (?, ?, ?, ?, ?)",
                (seam, v.analyst_id, v.verdict, v.rule_id, time.time()),
            )

    def _stamp_empty(self, seam: str):
        with self._evidence_lock:
            self._evidence.execute(
                "INSERT INTO evidence (seam, analyst, verdict, rule, ts) VALUES (?, ?, ?, ?, ?)",
                (seam, "<none>", "<empty-stamp>", None, time.time()),
            )

    async def close(self):
        for c in self._conns.values():
            c.close()
        self._evidence.close()
        if self._tmpdir is not None:
            self._tmpdir.cleanup()


# -----------------------------------------------------------------------------
# Workload stream — pulls from mock data OR generates synthetic filler
# -----------------------------------------------------------------------------

def make_payload_stream(payload_bytes: int, mock_data: Path | None):
    if mock_data is not None:
        from harness.perf.workload_from_mock import stream_payloads
        return stream_payloads(mock_data, repeat=True)
    # Fallback: synthetic filler payload (matches bench shape).
    def synthetic():
        filler = "x" * max(0, payload_bytes - 128)
        seq = 0
        while True:
            seq += 1
            yield f'{{"seq":{seq},"data":"{filler}"}}'
    return synthetic()


async def agent_loop(agent_id: int, substrate, stream, cadence_s: float,
                     stop_at: float, latencies: list[float], blocks: list[int]):
    seq = 0
    next_tick = time.monotonic()
    while time.monotonic() < stop_at:
        seq += 1
        payload = next(stream)
        emit_ts = time.monotonic()
        result = await substrate.emit(agent_id, payload)
        durable_ts = time.monotonic()
        if result.get("verdict") == "block":
            blocks.append(seq)
        else:
            latencies.append((durable_ts - emit_ts) * 1000)
        next_tick += cadence_s
        sleep_for = next_tick - time.monotonic()
        if sleep_for > 0:
            await asyncio.sleep(sleep_for)
        else:
            next_tick = time.monotonic()


async def rss_sampler(stop_event: asyncio.Event, samples: list[float]):
    proc = psutil.Process()
    while not stop_event.is_set():
        samples.append(proc.memory_info().rss / (1024 * 1024))
        await asyncio.sleep(1.0)


# -----------------------------------------------------------------------------
# Main run
# -----------------------------------------------------------------------------

async def run(variant_id: str, duration_override: int | None, output: Path | None,
              in_memory: bool, manifest_path: Path, mock_data: Path | None):
    manifest = load_manifest(manifest_path)
    workload = get_workload(manifest)
    variant = get_variant(manifest, variant_id)

    duration = duration_override or (workload.warmup_seconds + workload.steady_state_seconds)
    cadence_s = 1.0 / workload.events_per_agent_per_sec

    print(f"variant={variant.id} substrate={variant.substrate} "
          f"stages={variant.pipeline_stages} analysts={len(variant.analysts)} "
          f"payload_bytes={workload.event_payload_bytes} "
          f"eps_per_agent={workload.events_per_agent_per_sec} "
          f"duration={duration}s in_memory={in_memory} "
          f"mock_data={mock_data}")

    cold_start_begin = time.monotonic()
    substrate = RealClawSubstrate(
        stages=variant.pipeline_stages,
        analyst_specs=variant.analysts,
        in_memory=in_memory,
    )
    cold_start_ms = (time.monotonic() - cold_start_begin) * 1000

    latencies: list[float] = []
    blocks: list[int] = []
    rss_samples: list[float] = []
    stop_event = asyncio.Event()

    sampler_task = asyncio.create_task(rss_sampler(stop_event, rss_samples))

    # Build a stream PER agent (each agent has its own iterator state so they
    # don't race on the same generator).
    stop_at = time.monotonic() + duration
    agent_tasks = [
        asyncio.create_task(
            agent_loop(
                i,
                substrate,
                make_payload_stream(workload.event_payload_bytes, mock_data),
                cadence_s,
                stop_at,
                latencies,
                blocks,
            )
        )
        for i in range(workload.agents)
    ]

    await asyncio.gather(*agent_tasks)
    stop_event.set()
    await sampler_task
    await substrate.close()

    metrics = {
        "variant": variant.id,
        "substrate": variant.substrate,
        "analysts": len(variant.analysts),
        "duration_s": duration,
        "events_completed": len(latencies),
        "events_blocked": len(blocks),
        "throughput_eps": len(latencies) / duration if duration > 0 else 0,
        "latency_ms": {
            "p50": statistics.median(latencies) if latencies else None,
            "p95": statistics.quantiles(latencies, n=20)[18] if len(latencies) >= 20 else None,
            "p99": statistics.quantiles(latencies, n=100)[98] if len(latencies) >= 100 else None,
            "max": max(latencies) if latencies else None,
            "min": min(latencies) if latencies else None,
        },
        "rss_mb": {
            "peak": max(rss_samples) if rss_samples else None,
            "mean": statistics.mean(rss_samples) if rss_samples else None,
        },
        "cold_start_ms": cold_start_ms,
    }

    print(f"RESULT variant={variant.id} "
          f"p50={metrics['latency_ms']['p50']} "
          f"p95={metrics['latency_ms']['p95']} "
          f"p99={metrics['latency_ms']['p99']} "
          f"rss_peak_mb={metrics['rss_mb']['peak']} "
          f"throughput={metrics['throughput_eps']:.1f}")

    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        with open(output, "w") as f:
            json.dump(metrics, f, indent=2)
        print(f"wrote {output}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", default=os.environ.get("BENCH_VARIANT_ID"))
    parser.add_argument("--duration", type=int, default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--in-memory", action="store_true")
    parser.add_argument("--manifest", type=Path,
                        default=Path(__file__).resolve().parent / "manifest.yaml")
    parser.add_argument("--mock-data", type=Path,
                        default=REPO_ROOT / "mock-data" / "hr-pii" / "data.csv.gz",
                        help="csv.gz to replay as workload (use --no-mock-data for synthetic)")
    parser.add_argument("--no-mock-data", action="store_true",
                        help="use synthetic filler payloads instead of mock data")
    args = parser.parse_args()

    if not args.variant:
        parser.error("--variant required (or set BENCH_VARIANT_ID)")

    mock_data = None if args.no_mock_data else args.mock_data
    # If mock data is requested but missing, fall back to synthetic with a warning
    # rather than crashing — keeps `make perf-test` resilient when gen-data hasn't run.
    if mock_data is not None and not mock_data.exists():
        print(f"WARN: mock data {mock_data} missing; falling back to synthetic filler",
              file=sys.stderr)
        mock_data = None

    # Make `harness` importable when run as a script from within harness/perf/.
    if str(REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(REPO_ROOT))

    asyncio.run(run(args.variant, args.duration, args.output, args.in_memory,
                    args.manifest, mock_data))


if __name__ == "__main__":
    main()
