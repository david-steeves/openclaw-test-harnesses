# mock-data/hr-pii/ — schema

Workday-shaped employee master. Synthesized via
`mock-data/generators/gen_hr.py` (Faker-shaped). 16 columns, one row per
employee.

**Seed:** `42` (default). Determinism contract: the same `--seed` produces
byte-identical `data.csv.gz`.

**Default size:** 10,000 rows. Override with `--rows N`.

## Columns

| # | Column | Type | Notes |
|---|---|---|---|
| 1 | `employee_id` | string | `E0000000`-style, always populated |
| 2 | `first_name` | string | empty on some PASS / salary-warn rows |
| 3 | `last_name` | string | empty on some PASS / salary-warn rows |
| 4 | `date_of_birth` | ISO date | empty on PASS / salary-warn rows |
| 5 | `ssn` | string | US SSN format `\d{3}-\d{2}-\d{4}`; populated on BLOCK rows |
| 6 | `email` | string | optional |
| 7 | `phone` | string | optional |
| 8 | `street_address` | string | optional |
| 9 | `city` | string | optional |
| 10 | `state` | 2-letter | optional |
| 11 | `zip` | string | optional |
| 12 | `department` | string | always populated |
| 13 | `job_title` | string | optional |
| 14 | `salary` | string-of-int | populated on salary-warn rows |
| 15 | `hire_date` | ISO date | optional |
| 16 | `employment_status` | enum | `active` \| `terminated` |

## Verdict-shape distribution (for 10,000-row default seed)

| Row indices | Category | Verdict | Trigger |
|---|---|---|---|
| 0..49 | BLOCK (system SSN + name + DOB) | BLOCK | `system/block-ssn` matches; pii-warn name-dob also fires (advisory) |
| 50..199 | WARN (cooccurrence) | WARN | scoped pii-warn name-dob fires; no SSN |
| 200..299 | WARN (salary) | WARN | scoped pii-warn salary fires; no name/DOB/SSN |
| 300..399 | PASS | PASS | only employee_id + department |
| 400..9999 | mixed | varies | realistic distribution; ~30% of rows carry SSN, ~70% carry DOB |

`annotations.yaml` enumerates the index ranges and the expected verdict per
range. The functional test harness loads this and asserts per-row.

## Regen

```sh
cd mock-data/generators
uv run --with faker python gen_hr.py --seed 42 --rows 10000
```

Output lands at `mock-data/hr-pii/data.csv.gz`.
