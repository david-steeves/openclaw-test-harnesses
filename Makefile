# openclaw-test-harnesses Makefile
# Stage-1 evidence harness for RFC 0010 (openclaw/rfcs#11).

SHELL := /bin/bash
TIMESTAMP := $(shell date -u +%Y%m%dT%H%M%SZ)
RESULTS_DIR := bench/results/$(TIMESTAMP)
CONTAINER_RESULTS_DIR := /results/$(TIMESTAMP)

# Sibling pipeline-bench checkout used by perf-test-vs-bench.
BENCH_REPO ?= $(HOME)/projects/openclaw-pipeline-bench
# Pick the most recent bench results dir under it.
BENCH_LATEST_RESULTS := $(shell ls -dt $(BENCH_REPO)/bench/results/*/ 2>/dev/null | head -n1)

PERF_VARIANTS := pipeline-real-claws pipeline-real-claws-pass-only

.PHONY: help install gen-data policy-test perf-test perf-test-vs-bench all clean smoke build $(addprefix perf-,$(PERF_VARIANTS))

help:
	@echo "Targets:"
	@echo "  install              Verify python3.13 + uv + orb + docker"
	@echo "  gen-data             Regenerate mock-data/*/data.csv.gz from seeds"
	@echo "  policy-test          Run policy-eval functional harness + asserts"
	@echo "  perf-test            Run pipeline-real-claws variant via docker compose"
	@echo "  perf-test-vs-bench   Run pipeline-real-claws + diff vs openclaw-pipeline-bench"
	@echo "  all                  policy-test + perf-test-vs-bench"
	@echo "  smoke                In-memory smoke perf run, no docker"
	@echo "  clean                Tear down compose + rm bench/results/*"

install:
	@command -v python3.13 >/dev/null || (echo "Python 3.13 missing: brew install python@3.13" && exit 1)
	@command -v uv >/dev/null || (echo "uv missing: brew install uv" && exit 1)
	@command -v orb >/dev/null  || (echo "OrbStack missing: brew install --cask orbstack" && exit 1)
	@command -v docker >/dev/null || (echo "Docker missing — start OrbStack first" && exit 1)
	@echo "All required tools present."

gen-data:
	uv run --with faker python mock-data/generators/gen_hr.py --seed 42 --rows 10000
	uv run --with faker python mock-data/generators/gen_phi.py --seed 42 --rows 5000

policy-test:
	uv run --with pyyaml --with faker python -m harness.policy_eval.runner
	uv run --with pyyaml --with faker --with pytest pytest harness/policy_eval/asserts/ -v

build:
	docker compose build

smoke:
	cd harness/perf && uv run --with psutil --with pyyaml python runner.py \
	    --variant pipeline-real-claws --duration 10 --in-memory --manifest manifest.yaml

perf-pipeline-real-claws:
	@mkdir -p $(RESULTS_DIR)/pipeline-real-claws
	docker compose run --rm pipeline-real-claws --duration 360 --output $(CONTAINER_RESULTS_DIR)/pipeline-real-claws/run-1.json
	docker compose run --rm pipeline-real-claws --duration 360 --output $(CONTAINER_RESULTS_DIR)/pipeline-real-claws/run-2.json
	docker compose run --rm pipeline-real-claws --duration 360 --output $(CONTAINER_RESULTS_DIR)/pipeline-real-claws/run-3.json

perf-pipeline-real-claws-pass-only:
	@mkdir -p $(RESULTS_DIR)/pipeline-real-claws-pass-only
	docker compose run --rm pipeline-real-claws-pass-only --duration 360 --output $(CONTAINER_RESULTS_DIR)/pipeline-real-claws-pass-only/run-1.json
	docker compose run --rm pipeline-real-claws-pass-only --duration 360 --output $(CONTAINER_RESULTS_DIR)/pipeline-real-claws-pass-only/run-2.json
	docker compose run --rm pipeline-real-claws-pass-only --duration 360 --output $(CONTAINER_RESULTS_DIR)/pipeline-real-claws-pass-only/run-3.json

perf-test: build perf-pipeline-real-claws

perf-test-vs-bench: build $(addprefix perf-,$(PERF_VARIANTS))
	@if [ -z "$(BENCH_LATEST_RESULTS)" ]; then \
		echo "ERROR: no openclaw-pipeline-bench results found under $(BENCH_REPO)/bench/results/"; \
		echo "Clone + run that bench first, then re-run this target."; \
		exit 1; \
	fi
	uv run --with pyyaml python scripts/generate_comparison_report.py \
	    --results-dir $(RESULTS_DIR) \
	    --bench-results $(BENCH_LATEST_RESULTS)
	@echo ""
	@echo "==============================================="
	@echo "Comparison: $(RESULTS_DIR)/COMPARISON.md"
	@echo "Write the headline paragraph by hand."
	@echo "==============================================="

all: policy-test perf-test-vs-bench

clean:
	docker compose down -v 2>/dev/null || true
	rm -rf bench/results/[0-9]* 2>/dev/null || true
	rm -rf harness/policy_eval/verdict-tape/[0-9]* 2>/dev/null || true
	@echo "Cleaned."
