"""
mock-data/generators/gen_hr.py

Deterministic HR/PII mock data generator. Faker-shaped Workday-style employee
master.

USAGE:
    uv run --with faker python gen_hr.py --seed 42 --rows 10000 --out ../hr-pii/data.csv.gz

Determinism contract: same --seed produces byte-identical output. Test:
    diff <(zcat data.csv.gz) <(python gen_hr.py --seed 42 --rows 10000 --stdout)

Annotation contract: row indices 0..N-1 in the emitted CSV (after header row)
match annotations.yaml. The annotated trigger rows are placed at deterministic
positions defined here, so the test harness can assert per-row verdicts.

Columns: employee_id, first_name, last_name, date_of_birth, ssn, email, phone,
         street_address, city, state, zip, department, job_title, salary,
         hire_date, employment_status
"""

from __future__ import annotations

import argparse
import csv
import gzip
import io
import sys
from pathlib import Path

from faker import Faker


COLUMNS = [
    "employee_id", "first_name", "last_name", "date_of_birth", "ssn", "email",
    "phone", "street_address", "city", "state", "zip", "department",
    "job_title", "salary", "hire_date", "employment_status",
]

# Annotation trigger plan. We emit rows in deterministic categories so
# annotations.yaml can name index ranges. Default: 10000 rows total.
#
#   indices 0..49           BLOCK rows: SSN + full_name present
#   indices 50..199         WARN rows: name + DOB co-occurrence, no SSN
#   indices 200..299        WARN rows: salary present, no SSN/DOB
#   indices 300..399        PASS rows: employee_id + department only
#   indices 400..N-1        mixed (fill rows, realistic distribution)
#
# These ranges are documented in annotations.yaml and in schema.md.

DEPARTMENTS = [
    "Engineering", "Sales", "Marketing", "Finance", "Operations",
    "Customer Success", "Legal", "HR", "Product", "Research",
]
JOB_TITLES = [
    "Software Engineer", "Senior Engineer", "Manager", "Director",
    "Analyst", "Account Executive", "Designer", "Researcher",
]


def make_block_row(i: int, fake: Faker) -> dict:
    """SSN + full name + dob -> system BLOCK."""
    return {
        "employee_id": f"E{i:07d}",
        "first_name": fake.first_name(),
        "last_name": fake.last_name(),
        "date_of_birth": fake.date_of_birth(minimum_age=22, maximum_age=65).isoformat(),
        "ssn": fake.ssn(),
        "email": fake.email(),
        "phone": fake.phone_number(),
        "street_address": fake.street_address(),
        "city": fake.city(),
        "state": fake.state_abbr(),
        "zip": fake.postcode(),
        "department": fake.random_element(DEPARTMENTS),
        "job_title": fake.random_element(JOB_TITLES),
        "salary": str(fake.random_int(50000, 250000)),
        "hire_date": fake.date_between(start_date="-15y", end_date="-1d").isoformat(),
        "employment_status": "active",
    }


def make_warn_cooccur_row(i: int, fake: Faker) -> dict:
    """name + DOB present, no SSN -> scoped WARN (name-dob-cooccurrence)."""
    row = make_block_row(i, fake)
    row["ssn"] = ""
    row["salary"] = ""  # isolate the trigger to the cooccurrence rule
    return row


def make_warn_salary_row(i: int, fake: Faker) -> dict:
    """salary present, no name/DOB/SSN -> scoped WARN (salary-presence)."""
    return {
        "employee_id": f"E{i:07d}",
        "first_name": "",
        "last_name": "",
        "date_of_birth": "",
        "ssn": "",
        "email": "",
        "phone": "",
        "street_address": "",
        "city": "",
        "state": "",
        "zip": "",
        "department": fake.random_element(DEPARTMENTS),
        "job_title": fake.random_element(JOB_TITLES),
        "salary": str(fake.random_int(50000, 250000)),
        "hire_date": "",
        "employment_status": "active",
    }


def make_pass_row(i: int, fake: Faker) -> dict:
    """employee_id + department only -> PASS."""
    return {
        "employee_id": f"E{i:07d}",
        "first_name": "",
        "last_name": "",
        "date_of_birth": "",
        "ssn": "",
        "email": "",
        "phone": "",
        "street_address": "",
        "city": "",
        "state": "",
        "zip": "",
        "department": fake.random_element(DEPARTMENTS),
        "job_title": "",
        "salary": "",
        "hire_date": "",
        "employment_status": "active",
    }


def make_mixed_row(i: int, fake: Faker) -> dict:
    """Realistic distribution — most rows have name+contact, ~30% have SSN."""
    has_ssn = (i % 10) < 3
    has_dob = (i % 10) < 7
    return {
        "employee_id": f"E{i:07d}",
        "first_name": fake.first_name(),
        "last_name": fake.last_name(),
        "date_of_birth": fake.date_of_birth(minimum_age=22, maximum_age=65).isoformat() if has_dob else "",
        "ssn": fake.ssn() if has_ssn else "",
        "email": fake.email(),
        "phone": fake.phone_number(),
        "street_address": fake.street_address(),
        "city": fake.city(),
        "state": fake.state_abbr(),
        "zip": fake.postcode(),
        "department": fake.random_element(DEPARTMENTS),
        "job_title": fake.random_element(JOB_TITLES),
        "salary": str(fake.random_int(50000, 250000)),
        "hire_date": fake.date_between(start_date="-15y", end_date="-1d").isoformat(),
        "employment_status": fake.random_element(["active", "active", "active", "terminated"]),
    }


def generate(seed: int, rows: int) -> list[dict]:
    fake = Faker()
    Faker.seed(seed)
    fake.seed_instance(seed)

    out: list[dict] = []
    for i in range(rows):
        if i < 50:
            out.append(make_block_row(i, fake))
        elif i < 200:
            out.append(make_warn_cooccur_row(i, fake))
        elif i < 300:
            out.append(make_warn_salary_row(i, fake))
        elif i < 400:
            out.append(make_pass_row(i, fake))
        else:
            out.append(make_mixed_row(i, fake))
    return out


def write_csv_gz(rows: list[dict], out_path: Path):
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    data = buf.getvalue().encode("utf-8")
    # mtime=0 keeps gzip output byte-identical for the same input.
    with gzip.GzipFile(filename=str(out_path), mode="wb", mtime=0) as gz:
        gz.write(data)


def write_csv_stdout(rows: list[dict]):
    writer = csv.DictWriter(sys.stdout, fieldnames=COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--rows", type=int, default=10000)
    p.add_argument("--out", type=Path, default=None,
                   help="output gzipped CSV path (default: write to mock-data/hr-pii/data.csv.gz)")
    p.add_argument("--stdout", action="store_true",
                   help="write CSV to stdout instead of gzipped file (for determinism check)")
    args = p.parse_args()

    rows = generate(args.seed, args.rows)
    if args.stdout:
        write_csv_stdout(rows)
        return

    out_path = args.out or Path(__file__).parent.parent / "hr-pii" / "data.csv.gz"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_csv_gz(rows, out_path)
    print(f"wrote {out_path} ({len(rows)} rows, seed={args.seed})", file=sys.stderr)


if __name__ == "__main__":
    main()
