# mock-data/phi-snowflakey/ — schema

Synthea-shaped wide-table datamart (patient + encounter + diagnosis + lab +
medication, denormalized to a single wide table). 24 columns.

**Seed:** `42` (default).

**Default size:** 5,000 rows. The parent plan calls for 250,000 rows
(~1 MB gzipped). The functional harness only needs ~5k for the assertion
ladder + realistic distribution; the perf bench replays the file multiple
times for volume. Override with `--rows 250000` to produce the canonical
~1 MB file.

**Pragmatic deviation from plan, documented here for the reader:** generating
250k rows takes ~20 min wall-clock with Faker (clinical-vocabulary heavy
fields). The 5k default keeps `make gen-data` fast for the dev loop; the
M4 Pro session regenerates at 250k for the citable artifact.

## Columns

| # | Column | Type | Notes |
|---|---|---|---|
| 1 | `patient_id` | string | `P00000000`-style |
| 2 | `last_name` | string | optional |
| 3 | `first_name` | string | optional |
| 4 | `birth_date` | ISO date | optional |
| 5 | `gender` | enum | `M` \| `F` \| `U` |
| 6 | `address` | string | optional |
| 7 | `city` | string | optional |
| 8 | `state` | 2-letter | optional |
| 9 | `zip_code` | string | optional |
| 10 | `phone_number` | string | optional |
| 11 | `email` | string | optional |
| 12 | `ssn` | string | populated on system-block rows |
| 13 | `mrn` | string | `MRN######` — populated on phi-marker rows |
| 14 | `encounter_id` | string | `ENC#########` |
| 15 | `encounter_date` | ISO date | optional |
| 16 | `diagnosis_code` | ICD-10 | populated on phi-marker rows |
| 17 | `diagnosis_description` | string | lookup-driven (illustrative-only) |
| 18 | `procedure_code` | CPT-shape | optional |
| 19 | `medication_code` | RxNorm-shape | optional |
| 20 | `medication_name` | string | optional |
| 21 | `lab_value` | number-as-string | optional |
| 22 | `lab_code` | LOINC-shape | optional |
| 23 | `lab_code_description` | string | optional |
| 24 | `diagnosis_notes` | free-text | populated on free-text-warn rows |

## Verdict-shape distribution (default 5,000-row seed)

| Row indices | Category | Verdict | Trigger |
|---|---|---|---|
| 0..99 | BLOCK (system) | BLOCK | system SSN block + scoped phi block; system wins |
| 100..299 | BLOCK (scoped phi) | BLOCK | mrn or diagnosis_code, no SSN; phi-marker-block fires |
| 300..499 | WARN (re-identification) | WARN | patient_id + birth_date + city; patient-id-warn fires |
| 500..599 | WARN (free-text) | WARN | diagnosis_notes with date / name pattern; free-text-phi-scan fires |
| 600..699 | PASS | PASS | billing codes only |
| 700..4999 | mixed | varies | ~10% SSN, ~25% PHI marker |

## Regen

```sh
cd mock-data/generators
uv run --with faker python gen_phi.py --seed 42 --rows 5000      # dev loop
uv run --with faker python gen_phi.py --seed 42 --rows 250000    # canonical artifact
```
