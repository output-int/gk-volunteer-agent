#!/usr/bin/env python3
"""Smoke tests for validate_data.py."""

from __future__ import annotations

import csv
import json
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

from import_data import import_csv
from validate_data import collect_data_gaps


ROOT = Path(__file__).resolve().parent
INIT_SQL = ROOT / "db" / "init.sql"
SUBJECT_REQUIREMENT_SAMPLE = ROOT / "data" / "samples" / "subject_requirement_sample.csv"
SCHOOL_MAJOR_PROFILE_SAMPLE = ROOT / "data" / "samples" / "school_major_profile_sample.csv"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def initialize_temp_db(db_path: Path) -> None:
    sql = INIT_SQL.read_text(encoding="utf-8")
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(sql)
        conn.commit()
    finally:
        conn.close()


def has_gap(gaps: list[dict[str, object]], gap_type: str, school_name: str, major_name: str) -> bool:
    return any(
        gap["gap_type"] == gap_type
        and gap["school_name"] == school_name
        and gap["major_name"] == major_name
        for gap in gaps
    )


def main() -> None:
    json_result = subprocess.run(
        [sys.executable, "validate_data.py", "--json"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    payload = json.loads(json_result.stdout)
    assert_true(payload["ok"] is True, "Default data validation should pass with warnings.")
    assert_true(payload["error_count"] == 0, "Mock data should have no validation errors.")
    assert_true(payload["warning_count"] >= 1, "Mock data should expose known warnings.")

    with tempfile.TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir) / "data_gaps"
        export_result = subprocess.run(
            [sys.executable, "validate_data.py", "--export-gaps", str(output_dir), "--json"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        export_payload = json.loads(export_result.stdout)
        gap_export = export_payload["gap_export"]
        csv_path = Path(gap_export["csv_path"])
        markdown_path = Path(gap_export["markdown_path"])
        assert_true(csv_path.exists(), "Data gap CSV should be written.")
        assert_true(markdown_path.exists(), "Data gap Markdown should be written.")
        with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        assert_true(rows, "Data gap CSV should contain known Mock gaps.")
        assert_true(
            any(row["gap_type"] == "missing_2026_subject_requirement" for row in rows),
            "Data gap CSV should include missing subject requirements.",
        )
        assert_true(
            any(row["target_table"] == "school_major_profile" for row in rows),
            "Data gap CSV should include missing school-major profiles.",
        )
        markdown = markdown_path.read_text(encoding="utf-8")
        assert_true("高考志愿填报 Agent 数据补全清单" in markdown, "Data gap Markdown title missing.")
        assert_true("subject_requirement" in markdown, "Data gap Markdown should mention target tables.")

    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "test_gaokao_agent.db"
        initialize_temp_db(db_path)
        before_gaps = collect_data_gaps(db_path)
        assert_true(
            has_gap(before_gaps, "missing_2026_subject_requirement", "西南大学", "数学类"),
            "Initial gaps should include Southwest University Mathematics subject requirement.",
        )
        assert_true(
            has_gap(before_gaps, "missing_school_major_profile", "西南大学", "数学类"),
            "Initial gaps should include Southwest University Mathematics profile.",
        )
        import_csv(db_path, SUBJECT_REQUIREMENT_SAMPLE, "subject_requirement", replace_scope=True)
        import_csv(db_path, SCHOOL_MAJOR_PROFILE_SAMPLE, "school_major_profile", replace_scope=True)
        after_gaps = collect_data_gaps(db_path)
        assert_true(
            not has_gap(after_gaps, "missing_2026_subject_requirement", "西南大学", "数学类"),
            "Imported subject requirement should close the matching data gap.",
        )
        assert_true(
            not has_gap(after_gaps, "missing_school_major_profile", "西南大学", "数学类"),
            "Imported school-major profile should close the matching data gap.",
        )
        assert_true(len(after_gaps) < len(before_gaps), "Data gap count should decrease after enrichment imports.")

    print("All data quality smoke tests passed.")


if __name__ == "__main__":
    main()
