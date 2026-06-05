#!/usr/bin/env python3
"""Import cleaned official/verified CSV data into the Gaokao Agent SQLite DB.

This importer intentionally expects already-cleaned CSV files. PDF/Excel parsing
is a separate extraction step; this script is the final validation and load gate.
"""

from __future__ import annotations

import argparse
import csv
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DEFAULT_DB_PATH = ROOT / "gaokao_agent.db"

SUBJECT_TYPES = {"物理", "历史"}
BATCHES = {"本科批", "专科批", "提前批"}
ADMISSION_TYPES = {"普通类", "中外合作", "民族班", "预科", "专项"}
SOURCE_TYPES = {"official", "third_party", "manual_verified"}
CONFIDENCE_LEVELS = {"high", "medium", "low"}

ADMISSION_COLUMNS = [
    "year",
    "province",
    "subject_type",
    "batch",
    "school_code",
    "school_name",
    "major_group_code",
    "major_code",
    "major_name",
    "major_category",
    "discipline_category",
    "admission_type",
    "min_score",
    "min_rank",
    "plan_count",
    "source_url",
    "source_type",
    "confidence",
    "risk_notes",
]

SCORE_RANK_COLUMNS = [
    "year",
    "province",
    "subject_type",
    "score",
    "rank_min",
    "rank_max",
    "same_score_count",
    "cumulative_count",
    "batch_line_score",
    "above_batch_line_count",
    "source_url",
]


@dataclass(frozen=True)
class ImportResult:
    table: str
    csv_path: Path
    row_count: int
    dry_run: bool


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def parse_int(value: str, field_name: str, row_number: int, *, allow_empty: bool = False) -> int | None:
    stripped = (value or "").strip()
    if allow_empty and stripped == "":
        return None
    try:
        return int(stripped)
    except ValueError as exc:
        raise ValueError(f"Row {row_number}: {field_name} must be an integer, got {value!r}") from exc


def require_text(value: str, field_name: str, row_number: int) -> str:
    stripped = (value or "").strip()
    if not stripped:
        raise ValueError(f"Row {row_number}: {field_name} is required")
    return stripped


def optional_text(value: str | None) -> str | None:
    stripped = (value or "").strip()
    return stripped or None


def validate_columns(actual: list[str], expected: list[str], table: str) -> None:
    if actual != expected:
        missing = [column for column in expected if column not in actual]
        extra = [column for column in actual if column not in expected]
        raise ValueError(
            f"{table} CSV columns do not match template.\n"
            f"Expected: {expected}\n"
            f"Actual:   {actual}\n"
            f"Missing:  {missing}\n"
            f"Extra:    {extra}"
        )


def read_csv(csv_path: Path, expected_columns: list[str], table: str) -> list[dict[str, str]]:
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"{csv_path} has no header row")
        validate_columns(reader.fieldnames, expected_columns, table)
        return [dict(row) for row in reader]


def validate_admission_row(raw: dict[str, str], row_number: int) -> dict[str, Any]:
    year = parse_int(raw["year"], "year", row_number)
    min_score = parse_int(raw["min_score"], "min_score", row_number)
    min_rank = parse_int(raw["min_rank"], "min_rank", row_number)
    plan_count = parse_int(raw["plan_count"], "plan_count", row_number, allow_empty=True)

    subject_type = require_text(raw["subject_type"], "subject_type", row_number)
    batch = require_text(raw["batch"], "batch", row_number)
    admission_type = require_text(raw["admission_type"], "admission_type", row_number)
    source_type = require_text(raw["source_type"], "source_type", row_number)
    confidence = require_text(raw["confidence"], "confidence", row_number)

    if year is None or not 2021 <= year <= 2026:
        raise ValueError(f"Row {row_number}: year must be between 2021 and 2026")
    if subject_type not in SUBJECT_TYPES:
        raise ValueError(f"Row {row_number}: subject_type must be one of {sorted(SUBJECT_TYPES)}")
    if batch not in BATCHES:
        raise ValueError(f"Row {row_number}: batch must be one of {sorted(BATCHES)}")
    if admission_type not in ADMISSION_TYPES:
        raise ValueError(f"Row {row_number}: admission_type must be one of {sorted(ADMISSION_TYPES)}")
    if source_type not in SOURCE_TYPES:
        raise ValueError(f"Row {row_number}: source_type must be one of {sorted(SOURCE_TYPES)}")
    if confidence not in CONFIDENCE_LEVELS:
        raise ValueError(f"Row {row_number}: confidence must be one of {sorted(CONFIDENCE_LEVELS)}")
    if min_score is None or not 0 <= min_score <= 750:
        raise ValueError(f"Row {row_number}: min_score must be between 0 and 750")
    if min_rank is None or min_rank <= 0:
        raise ValueError(f"Row {row_number}: min_rank must be positive")
    if plan_count is not None and plan_count < 0:
        raise ValueError(f"Row {row_number}: plan_count cannot be negative")

    return {
        "year": year,
        "province": require_text(raw["province"], "province", row_number),
        "subject_type": subject_type,
        "batch": batch,
        "school_code": require_text(raw["school_code"], "school_code", row_number),
        "school_name": require_text(raw["school_name"], "school_name", row_number),
        "major_group_code": optional_text(raw["major_group_code"]),
        "major_code": require_text(raw["major_code"], "major_code", row_number),
        "major_name": require_text(raw["major_name"], "major_name", row_number),
        "major_category": optional_text(raw["major_category"]),
        "discipline_category": optional_text(raw["discipline_category"]),
        "admission_type": admission_type,
        "min_score": min_score,
        "min_rank": min_rank,
        "plan_count": plan_count,
        "source_url": require_text(raw["source_url"], "source_url", row_number),
        "source_type": source_type,
        "confidence": confidence,
        "risk_notes": optional_text(raw["risk_notes"]),
    }


def validate_score_rank_row(raw: dict[str, str], row_number: int) -> dict[str, Any]:
    year = parse_int(raw["year"], "year", row_number)
    score = parse_int(raw["score"], "score", row_number)
    rank_min = parse_int(raw["rank_min"], "rank_min", row_number)
    rank_max = parse_int(raw["rank_max"], "rank_max", row_number)
    same_score_count = parse_int(raw["same_score_count"], "same_score_count", row_number)
    cumulative_count = parse_int(raw["cumulative_count"], "cumulative_count", row_number)
    batch_line_score = parse_int(raw["batch_line_score"], "batch_line_score", row_number)
    above_batch_line_count = parse_int(raw["above_batch_line_count"], "above_batch_line_count", row_number)

    subject_type = require_text(raw["subject_type"], "subject_type", row_number)
    if year is None or not 2021 <= year <= 2026:
        raise ValueError(f"Row {row_number}: year must be between 2021 and 2026")
    if subject_type not in SUBJECT_TYPES:
        raise ValueError(f"Row {row_number}: subject_type must be one of {sorted(SUBJECT_TYPES)}")
    if score is None or not 0 <= score <= 750:
        raise ValueError(f"Row {row_number}: score must be between 0 and 750")
    if rank_min is None or rank_min <= 0:
        raise ValueError(f"Row {row_number}: rank_min must be positive")
    if rank_max is None or rank_max < rank_min:
        raise ValueError(f"Row {row_number}: rank_max must be >= rank_min")
    if same_score_count is None or same_score_count < 0:
        raise ValueError(f"Row {row_number}: same_score_count cannot be negative")
    if cumulative_count is None or cumulative_count < rank_max:
        raise ValueError(f"Row {row_number}: cumulative_count must be >= rank_max")
    if batch_line_score is None or not 0 <= batch_line_score <= 750:
        raise ValueError(f"Row {row_number}: batch_line_score must be between 0 and 750")
    if above_batch_line_count is None or above_batch_line_count <= 0:
        raise ValueError(f"Row {row_number}: above_batch_line_count must be positive")

    return {
        "year": year,
        "province": require_text(raw["province"], "province", row_number),
        "subject_type": subject_type,
        "score": score,
        "rank_min": rank_min,
        "rank_max": rank_max,
        "same_score_count": same_score_count,
        "cumulative_count": cumulative_count,
        "batch_line_score": batch_line_score,
        "above_batch_line_count": above_batch_line_count,
        "source_url": require_text(raw["source_url"], "source_url", row_number),
    }


def validate_rows(table: str, raw_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    if not raw_rows:
        raise ValueError("CSV has no data rows")
    validator = validate_admission_row if table == "admission_history" else validate_score_rank_row
    return [validator(raw, index + 2) for index, raw in enumerate(raw_rows)]


def delete_scope(conn: sqlite3.Connection, table: str, rows: list[dict[str, Any]]) -> int:
    deleted = 0
    scopes = {(row["year"], row["province"], row["subject_type"]) for row in rows}
    for year, province, subject_type in scopes:
        if table == "admission_history":
            batches = {row["batch"] for row in rows if row["year"] == year and row["province"] == province and row["subject_type"] == subject_type}
            for batch in batches:
                cursor = conn.execute(
                    """
                    DELETE FROM admission_history
                    WHERE year = ? AND province = ? AND subject_type = ? AND batch = ?
                    """,
                    (year, province, subject_type, batch),
                )
                deleted += cursor.rowcount
        else:
            cursor = conn.execute(
                """
                DELETE FROM score_rank_table
                WHERE year = ? AND province = ? AND subject_type = ?
                """,
                (year, province, subject_type),
            )
            deleted += cursor.rowcount
    return deleted


def insert_rows(conn: sqlite3.Connection, table: str, rows: list[dict[str, Any]]) -> None:
    columns = ADMISSION_COLUMNS if table == "admission_history" else SCORE_RANK_COLUMNS
    placeholders = ", ".join("?" for _ in columns)
    column_sql = ", ".join(columns)
    sql = f"INSERT INTO {table} ({column_sql}) VALUES ({placeholders})"
    conn.executemany(sql, [[row[column] for column in columns] for row in rows])


def import_csv(
    db_path: Path,
    csv_path: Path,
    table: str,
    *,
    replace_scope: bool = False,
    dry_run: bool = False,
) -> ImportResult:
    expected_columns = ADMISSION_COLUMNS if table == "admission_history" else SCORE_RANK_COLUMNS
    raw_rows = read_csv(csv_path, expected_columns, table)
    rows = validate_rows(table, raw_rows)

    if dry_run:
        return ImportResult(table=table, csv_path=csv_path, row_count=len(rows), dry_run=True)

    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}. Run python init_db.py first.")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        with conn:
            if replace_scope:
                deleted = delete_scope(conn, table, rows)
                print(f"Deleted {deleted} existing rows from {table} matching imported scope.")
            insert_rows(conn, table, rows)
    finally:
        conn.close()

    return ImportResult(table=table, csv_path=csv_path, row_count=len(rows), dry_run=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import cleaned CSV data into gaokao_agent.db.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--csv", type=Path, required=True, dest="csv_path")
    parser.add_argument("--table", choices=["admission_history", "score_rank_table"], required=True)
    parser.add_argument(
        "--replace-scope",
        action="store_true",
        help="Delete existing rows for the imported year/province/subject/batch scope before insert.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Validate only; do not write to the database.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    db_path = resolve_path(args.db)
    csv_path = resolve_path(args.csv_path)
    result = import_csv(
        db_path,
        csv_path,
        args.table,
        replace_scope=args.replace_scope,
        dry_run=args.dry_run,
    )
    action = "Validated" if result.dry_run else "Imported"
    print(f"{action} {result.row_count} rows for {result.table} from {result.csv_path}")


if __name__ == "__main__":
    main()
