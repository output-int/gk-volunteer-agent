#!/usr/bin/env python3
"""Smoke tests for CSV import_data.py."""

from __future__ import annotations

import sqlite3
import tempfile
from pathlib import Path

from import_data import import_csv


ROOT = Path(__file__).resolve().parent
INIT_SQL = ROOT / "db" / "init.sql"
ADMISSION_SAMPLE = ROOT / "data" / "samples" / "admission_history_sample.csv"
SCORE_RANK_SAMPLE = ROOT / "data" / "samples" / "score_rank_table_sample.csv"


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


def count_rows(db_path: Path, table: str, where_sql: str = "", params: tuple = ()) -> int:
    sql = f"SELECT COUNT(*) FROM {table} {where_sql}"
    conn = sqlite3.connect(db_path)
    try:
        return int(conn.execute(sql, params).fetchone()[0])
    finally:
        conn.close()


def main() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = Path(temp_dir) / "test_gaokao_agent.db"
        initialize_temp_db(db_path)

        admission_dry_run = import_csv(
            db_path,
            ADMISSION_SAMPLE,
            "admission_history",
            dry_run=True,
        )
        assert_true(admission_dry_run.row_count == 2, "Admission dry-run should validate 2 rows.")

        score_rank_dry_run = import_csv(
            db_path,
            SCORE_RANK_SAMPLE,
            "score_rank_table",
            dry_run=True,
        )
        assert_true(score_rank_dry_run.row_count == 2, "Score-rank dry-run should validate 2 rows.")

        before_admission = count_rows(db_path, "admission_history")
        import_csv(db_path, ADMISSION_SAMPLE, "admission_history")
        after_admission = count_rows(db_path, "admission_history")
        assert_true(after_admission == before_admission + 2, "Admission import should append 2 rows.")

        before_score_rank = count_rows(db_path, "score_rank_table")
        import_csv(db_path, SCORE_RANK_SAMPLE, "score_rank_table")
        after_score_rank = count_rows(db_path, "score_rank_table")
        assert_true(after_score_rank == before_score_rank + 2, "Score-rank import should append 2 rows.")

        import_csv(db_path, ADMISSION_SAMPLE, "admission_history", replace_scope=True)
        replaced_admission = count_rows(
            db_path,
            "admission_history",
            "WHERE year = 2025 AND province = '重庆' AND subject_type = '物理' AND batch = '本科批'",
        )
        assert_true(replaced_admission == 2, "replace-scope should leave only the 2 imported admission rows.")

        import_csv(db_path, SCORE_RANK_SAMPLE, "score_rank_table", replace_scope=True)
        replaced_score_rank = count_rows(
            db_path,
            "score_rank_table",
            "WHERE year = 2025 AND province = '重庆' AND subject_type = '物理'",
        )
        assert_true(replaced_score_rank == 2, "replace-scope should leave only the 2 imported score-rank rows.")

    print("All importer smoke tests passed.")


if __name__ == "__main__":
    main()
