"""
Pytest fixtures shared across all asserts.

Loads:
  - hr-pii and phi-snowflakey mock datasets (slimmed for fast iteration)
  - pii-reviewer and phi-reviewer analyst chains
  - annotations YAML for each dataset
"""

from __future__ import annotations

from pathlib import Path

import pytest

from harness.policy_eval.loader import (
    iter_dataset_rows,
    load_analysts_for_team,
    load_annotations,
)


REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session")
def hr_rows():
    return list(iter_dataset_rows(REPO_ROOT / "mock-data" / "hr-pii" / "data.csv.gz",
                                  max_rows=500))


@pytest.fixture(scope="session")
def phi_rows():
    return list(iter_dataset_rows(REPO_ROOT / "mock-data" / "phi-snowflakey" / "data.csv.gz",
                                  max_rows=700))


@pytest.fixture(scope="session")
def hr_annotations():
    return load_annotations(REPO_ROOT / "mock-data" / "hr-pii" / "annotations.yaml")


@pytest.fixture(scope="session")
def phi_annotations():
    return load_annotations(REPO_ROOT / "mock-data" / "phi-snowflakey" / "annotations.yaml")


@pytest.fixture(scope="session")
def pii_analysts():
    return load_analysts_for_team(REPO_ROOT, "pii-reviewer")


@pytest.fixture(scope="session")
def phi_analysts():
    return load_analysts_for_team(REPO_ROOT, "phi-reviewer")
