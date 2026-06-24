"""
harness/perf/workload_from_mock.py

Adapter that feeds mock-data/<dataset>/data.csv.gz rows as the bench's
synthetic event stream. Each row becomes a JSON-encoded payload string of
shape compatible with the bench's substrate.

USAGE: imported by harness/perf/runner.py; iterates rows in a loop and yields
       JSON strings for the agent_loop to emit.
"""

from __future__ import annotations

import csv
import gzip
import itertools
import json
from pathlib import Path
from typing import Iterator


def stream_payloads(csv_gz_path: Path, repeat: bool = True) -> Iterator[str]:
    """
    Yield JSON-encoded payload strings from a gzipped CSV.

    If repeat=True, loops the file forever — gives the bench a stable stream
    for `--duration N`-bounded runs without exhausting after the first pass.
    """
    if not csv_gz_path.exists():
        raise FileNotFoundError(f"mock data not found: {csv_gz_path}; run `make gen-data`")

    def _read():
        with gzip.open(csv_gz_path, "rt", newline="") as gz:
            for row in csv.DictReader(gz):
                yield json.dumps(row, separators=(",", ":"))

    if repeat:
        # itertools-style cycle, but we re-open the file each pass so we don't
        # buffer 250k rows in memory.
        while True:
            yield from _read()
    else:
        yield from _read()
