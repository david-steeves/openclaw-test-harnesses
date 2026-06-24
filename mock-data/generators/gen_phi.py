"""
mock-data/generators/gen_phi.py

Deterministic PHI mock data generator. Synthea-shaped wide-table datamart
(patient + encounter + diagnosis + lab + medication).

USAGE:
    uv run --with faker python gen_phi.py --seed 42 --rows 250000 --out ../phi-snowflakey/data.csv.gz

Annotation trigger plan (same shape as gen_hr.py):
   indices 0..99               BLOCK rows: ssn + (mrn OR diagnosis_code) -> system BLOCK
                                            (system layer wins over scoped phi BLOCK)
   indices 100..299            BLOCK rows: mrn or diagnosis_code, no ssn -> scoped phi-marker BLOCK
   indices 300..499            WARN rows: patient_id + birth_date + city, no PHI markers -> WARN
   indices 500..599            WARN rows: diagnosis_notes free-text with date/name patterns -> WARN
   indices 600..699            PASS rows: billing codes only, no demographics
   indices 700..N-1            mixed (fill rows)
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
    "patient_id", "last_name", "first_name", "birth_date", "gender", "address",
    "city", "state", "zip_code", "phone_number", "email", "ssn", "mrn",
    "encounter_id", "encounter_date", "diagnosis_code", "diagnosis_description",
    "procedure_code", "medication_code", "medication_name", "lab_value",
    "lab_code", "lab_code_description", "diagnosis_notes",
]

# Illustrative-only vocabularies. Real ICD-10/LOINC/RxNorm lookups are out of
# scope; we use plausible-shaped values so analyst regexes hit the same shapes
# they would in production.
ICD10_CODES = ["J18.9", "I10", "E11.9", "M54.5", "F32.9", "K21.9", "N39.0", "R51"]
LOINC_CODES = ["2160-0", "718-7", "33914-3", "2345-7", "789-8", "4544-3"]
RXNORM_CODES = ["198440", "313782", "856528", "197361", "308136"]

DIAGNOSIS_DESCRIPTIONS = {
    "J18.9": "Pneumonia, unspecified organism",
    "I10": "Essential hypertension",
    "E11.9": "Type 2 diabetes mellitus without complications",
    "M54.5": "Low back pain",
    "F32.9": "Major depressive disorder, single episode, unspecified",
    "K21.9": "Gastro-esophageal reflux disease without esophagitis",
    "N39.0": "Urinary tract infection, site not specified",
    "R51": "Headache",
}

MEDICATION_NAMES = {
    "198440": "Amoxicillin 500 mg oral capsule",
    "313782": "Lisinopril 10 mg oral tablet",
    "856528": "Metformin 500 mg oral tablet",
    "197361": "Atorvastatin 20 mg oral tablet",
    "308136": "Ibuprofen 200 mg oral tablet",
}

LAB_DESCRIPTIONS = {
    "2160-0": "Creatinine [Mass/volume] in Serum or Plasma",
    "718-7": "Hemoglobin [Mass/volume] in Blood",
    "33914-3": "Glomerular filtration rate",
    "2345-7": "Glucose [Mass/volume] in Serum or Plasma",
    "789-8": "Erythrocytes [#/volume] in Blood",
    "4544-3": "Hematocrit [Volume Fraction] of Blood",
}


def _common_demographics(i: int, fake: Faker) -> dict:
    return {
        "patient_id": f"P{i:08d}",
        "last_name": fake.last_name(),
        "first_name": fake.first_name(),
        "birth_date": fake.date_of_birth(minimum_age=1, maximum_age=95).isoformat(),
        "gender": fake.random_element(["M", "F", "U"]),
        "address": fake.street_address(),
        "city": fake.city(),
        "state": fake.state_abbr(),
        "zip_code": fake.postcode(),
        "phone_number": fake.phone_number(),
        "email": fake.email(),
    }


def make_system_block_row(i: int, fake: Faker) -> dict:
    """ssn + mrn or diagnosis_code -> system BLOCK wins."""
    base = _common_demographics(i, fake)
    icd = fake.random_element(ICD10_CODES)
    return {
        **base,
        "ssn": fake.ssn(),
        "mrn": f"MRN{fake.random_int(100000, 999999)}",
        "encounter_id": f"ENC{i:09d}",
        "encounter_date": fake.date_between(start_date="-3y", end_date="today").isoformat(),
        "diagnosis_code": icd,
        "diagnosis_description": DIAGNOSIS_DESCRIPTIONS[icd],
        "procedure_code": fake.random_element(["99213", "99214", "99215", "92002"]),
        "medication_code": fake.random_element(RXNORM_CODES),
        "medication_name": "",
        "lab_value": str(fake.pyfloat(left_digits=2, right_digits=1, positive=True)),
        "lab_code": fake.random_element(LOINC_CODES),
        "lab_code_description": "",
        "diagnosis_notes": "",
    }


def make_scoped_phi_block_row(i: int, fake: Faker) -> dict:
    """mrn or diagnosis_code present, no ssn -> scoped phi-marker BLOCK."""
    row = make_system_block_row(i, fake)
    row["ssn"] = ""
    return row


def make_patient_reid_warn_row(i: int, fake: Faker) -> dict:
    """patient_id + birth_date + city, no mrn/diag/ssn -> scoped WARN."""
    base = _common_demographics(i, fake)
    return {
        **base,
        "ssn": "",
        "mrn": "",
        "encounter_id": f"ENC{i:09d}",
        "encounter_date": "",
        "diagnosis_code": "",
        "diagnosis_description": "",
        "procedure_code": "",
        "medication_code": "",
        "medication_name": "",
        "lab_value": "",
        "lab_code": "",
        "lab_code_description": "",
        "diagnosis_notes": "",
    }


def make_freetext_warn_row(i: int, fake: Faker) -> dict:
    """diagnosis_notes contains date or name pattern -> scoped WARN (free-text scan)."""
    notes_templates = [
        "Patient seen on 2024-03-15 for follow-up.",
        "Mr. John Smith reports improvement since 01/15/2025.",
        "Discussed with Jane Doe on Mar 20, 2025.",
        "Repeat labs on 2024-11-02.",
    ]
    row = {
        "patient_id": f"P{i:08d}",
        "last_name": "",
        "first_name": "",
        "birth_date": "",
        "gender": "",
        "address": "",
        "city": "",
        "state": "",
        "zip_code": "",
        "phone_number": "",
        "email": "",
        "ssn": "",
        "mrn": "",
        "encounter_id": f"ENC{i:09d}",
        "encounter_date": "",
        "diagnosis_code": "",
        "diagnosis_description": "",
        "procedure_code": "",
        "medication_code": "",
        "medication_name": "",
        "lab_value": "",
        "lab_code": "",
        "lab_code_description": "",
        "diagnosis_notes": fake.random_element(notes_templates),
    }
    return row


def make_pass_billing_row(i: int, fake: Faker) -> dict:
    """billing codes only, no demographics -> PASS."""
    icd = fake.random_element(ICD10_CODES)
    return {
        "patient_id": "",
        "last_name": "",
        "first_name": "",
        "birth_date": "",
        "gender": "",
        "address": "",
        "city": "",
        "state": "",
        "zip_code": "",
        "phone_number": "",
        "email": "",
        "ssn": "",
        "mrn": "",
        "encounter_id": f"ENC{i:09d}",
        "encounter_date": "",
        # NOTE: deliberately leaving diagnosis_code blank to keep this a PASS
        # row (a populated diagnosis_code would trigger scoped phi BLOCK).
        "diagnosis_code": "",
        "diagnosis_description": "",
        "procedure_code": fake.random_element(["99213", "99214", "99215"]),
        "medication_code": "",
        "medication_name": "",
        "lab_value": "",
        "lab_code": "",
        "lab_code_description": "",
        "diagnosis_notes": "",
    }


def make_mixed_row(i: int, fake: Faker) -> dict:
    """Realistic distribution; ~10% SSN, ~25% PHI-marker, common demographics."""
    base = _common_demographics(i, fake)
    has_ssn = (i % 10) == 3
    has_marker = (i % 4) == 0
    icd = fake.random_element(ICD10_CODES) if has_marker else ""
    return {
        **base,
        "ssn": fake.ssn() if has_ssn else "",
        "mrn": f"MRN{fake.random_int(100000, 999999)}" if has_marker else "",
        "encounter_id": f"ENC{i:09d}",
        "encounter_date": fake.date_between(start_date="-3y", end_date="today").isoformat(),
        "diagnosis_code": icd,
        "diagnosis_description": DIAGNOSIS_DESCRIPTIONS.get(icd, ""),
        "procedure_code": fake.random_element(["99213", "99214", "99215"]),
        "medication_code": fake.random_element(RXNORM_CODES) if has_marker else "",
        "medication_name": "",
        "lab_value": str(fake.pyfloat(left_digits=2, right_digits=1, positive=True)),
        "lab_code": fake.random_element(LOINC_CODES),
        "lab_code_description": "",
        "diagnosis_notes": "",
    }


def generate(seed: int, rows: int) -> list[dict]:
    fake = Faker()
    Faker.seed(seed)
    fake.seed_instance(seed)

    out: list[dict] = []
    for i in range(rows):
        if i < 100:
            out.append(make_system_block_row(i, fake))
        elif i < 300:
            out.append(make_scoped_phi_block_row(i, fake))
        elif i < 500:
            out.append(make_patient_reid_warn_row(i, fake))
        elif i < 600:
            out.append(make_freetext_warn_row(i, fake))
        elif i < 700:
            out.append(make_pass_billing_row(i, fake))
        else:
            out.append(make_mixed_row(i, fake))
    return out


def write_csv_gz(rows: list[dict], out_path: Path):
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    data = buf.getvalue().encode("utf-8")
    with gzip.GzipFile(filename=str(out_path), mode="wb", mtime=0) as gz:
        gz.write(data)


def write_csv_stdout(rows: list[dict]):
    writer = csv.DictWriter(sys.stdout, fieldnames=COLUMNS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--seed", type=int, default=42)
    # NOTE: 250k from the plan, but our annotation harness only needs ~5k for
    # the full assertion ladder + realistic distribution. Default lowered to
    # 5000 to keep generator wall-clock under 30s; the perf bench replays
    # multiple times for volume. Override --rows for the canonical 250k file.
    p.add_argument("--rows", type=int, default=5000)
    p.add_argument("--out", type=Path, default=None)
    p.add_argument("--stdout", action="store_true")
    args = p.parse_args()

    rows = generate(args.seed, args.rows)
    if args.stdout:
        write_csv_stdout(rows)
        return

    out_path = args.out or Path(__file__).parent.parent / "phi-snowflakey" / "data.csv.gz"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_csv_gz(rows, out_path)
    print(f"wrote {out_path} ({len(rows)} rows, seed={args.seed})", file=sys.stderr)


if __name__ == "__main__":
    main()
