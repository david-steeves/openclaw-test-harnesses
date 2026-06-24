"""
harness/policy_eval/loader.py

Loaders for: mock data CSVs, annotations YAML, and analyst modules (loaded by
file path because team directories use hyphens — `teams/pii-reviewer/` —
which Python's package import system can't address).
"""

from __future__ import annotations

import csv
import gzip
import importlib.util
import io
from pathlib import Path
from typing import Any, Iterator

import yaml


# Mapping of team-id -> ordered list of (analyst-class-name, module-file-path).
# The team.yaml could be parsed for this, but the team.yaml schema uses repo-
# qualified paths and that's overkill for the harness. Hardcode here; if the
# team.yaml shape becomes load-bearing, switch to YAML-driven discovery.
TEAM_ANALYSTS = {
    "pii-reviewer": [
        ("SsnDetector", "teams/pii-reviewer/analysts/ssn_detector.py"),
        ("PiiCooccurrenceWarn", "teams/pii-reviewer/analysts/pii_cooccurrence_warn.py"),
        ("SalaryWarn", "teams/pii-reviewer/analysts/salary_warn.py"),
    ],
    "phi-reviewer": [
        # SSN detection is system-layer; reuse the same analyst class.
        ("SsnDetector", "teams/pii-reviewer/analysts/ssn_detector.py"),
        ("PhiMarkerBlock", "teams/phi-reviewer/analysts/phi_marker_block.py"),
        ("PatientIdWarn", "teams/phi-reviewer/analysts/patient_id_warn.py"),
        ("FreeTextPhiScan", "teams/phi-reviewer/analysts/free_text_phi_scan.py"),
    ],
}


def load_analysts_for_team(repo_root: Path, team: str) -> list[Any]:
    """Instantiate each analyst class for the team. Returns the instance list."""
    specs = TEAM_ANALYSTS.get(team)
    if specs is None:
        raise KeyError(f"unknown team {team!r}; known: {sorted(TEAM_ANALYSTS)}")
    out = []
    for class_name, rel_path in specs:
        module = _load_module(repo_root / rel_path)
        cls = getattr(module, class_name)
        out.append(cls())
    return out


def _load_module(path: Path):
    """Dynamically load a Python module from a file path."""
    if not path.exists():
        raise FileNotFoundError(f"analyst module not found: {path}")
    # Use a unique synthetic module name. Replace / with . and strip .py.
    mod_name = str(path).replace("/", ".").replace("-", "_").rsplit(".py", 1)[0]
    spec = importlib.util.spec_from_file_location(mod_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not build module spec for {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_annotations(annotations_path: Path) -> dict:
    with open(annotations_path) as f:
        return yaml.safe_load(f)


def iter_dataset_rows(data_csv_gz_path: Path, max_rows: int | None = None) -> Iterator[dict]:
    """Iterate rows of a gzipped CSV. Yields each row as a dict."""
    if not data_csv_gz_path.exists():
        raise FileNotFoundError(
            f"dataset not found: {data_csv_gz_path}\n"
            "Run `make gen-data` to regenerate."
        )
    with gzip.open(data_csv_gz_path, "rt", newline="") as gz:
        reader = csv.DictReader(gz)
        for i, row in enumerate(reader):
            if max_rows is not None and i >= max_rows:
                break
            yield row
