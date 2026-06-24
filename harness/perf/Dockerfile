# harness/perf/Dockerfile
# Container for the pipeline-real-claws perf variant. Mirrors the
# openclaw-pipeline-bench Dockerfile shape so docker compose semantics are
# consistent across both repos.

FROM python:3.13-slim-bookworm

WORKDIR /app

RUN pip install --no-cache-dir psutil pyyaml

# Copy everything the runner imports:
#   - harness/ (package: verdict.py, perf/, policy_eval/)
#   - teams/ (the analyst module files loaded by path)
#   - mock-data/<dataset>/data.csv.gz (the workload source)
# Per-file COPY is cleaner than tarball-the-world; if the layout changes,
# update this list.
COPY harness /app/harness
COPY teams /app/teams
COPY mock-data /app/mock-data

# Volume for results.
VOLUME ["/data", "/results"]

ENV PYTHONPATH=/app

ENTRYPOINT ["python", "-m", "harness.perf.runner", "--manifest", "/app/harness/perf/manifest.yaml"]
