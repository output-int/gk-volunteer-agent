#!/usr/bin/env python3
"""Smoke tests for validate_data.py."""

from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


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

    print("All data quality smoke tests passed.")


if __name__ == "__main__":
    main()
