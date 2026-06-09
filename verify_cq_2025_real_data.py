#!/usr/bin/env python3
"""Verify the imported 2025 Chongqing public data snapshot."""

from __future__ import annotations

import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "gaokao_agent.db"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def fetch_count(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> int:
    row = conn.execute(sql, params).fetchone()
    return int(row[0])


def main() -> None:
    assert_true(DB_PATH.exists(), f"Database does not exist: {DB_PATH}. Run python init_db.py first.")
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        physics_rows = fetch_count(
            conn,
            """
            SELECT COUNT(*)
            FROM admission_history
            WHERE year = 2025 AND province = '重庆' AND subject_type = '物理' AND batch = '本科批'
            """,
        )
        history_rows = fetch_count(
            conn,
            """
            SELECT COUNT(*)
            FROM admission_history
            WHERE year = 2025 AND province = '重庆' AND subject_type = '历史' AND batch = '本科批'
            """,
        )
        assert_true(physics_rows == 11464, f"Unexpected 2025 physics admission rows: {physics_rows}")
        assert_true(history_rows == 3786, f"Unexpected 2025 history admission rows: {history_rows}")

        score_rows = {
            row["subject_type"]: row
            for row in conn.execute(
                """
                SELECT subject_type, COUNT(*) AS row_count, MAX(above_batch_line_count) AS above_count,
                       MIN(batch_line_score) AS batch_line
                FROM score_rank_table
                WHERE year = 2025 AND province = '重庆'
                GROUP BY subject_type
                """
            )
        }
        assert_true(score_rows["物理"]["row_count"] == 502, "2025 physics score-rank row count mismatch.")
        assert_true(score_rows["物理"]["above_count"] == 103219, "2025 physics above-batch count mismatch.")
        assert_true(score_rows["物理"]["batch_line"] == 425, "2025 physics batch line mismatch.")
        assert_true(score_rows["历史"]["row_count"] == 473, "2025 history score-rank row count mismatch.")
        assert_true(score_rows["历史"]["above_count"] == 35253, "2025 history above-batch count mismatch.")
        assert_true(score_rows["历史"]["batch_line"] == 438, "2025 history batch line mismatch.")

        cqupt_computer = conn.execute(
            """
            SELECT school_name, major_name, min_score, min_rank
            FROM admission_history
            WHERE year = 2025
              AND school_name = '重庆邮电大学'
              AND major_name = '计算机科学与技术'
            """
        ).fetchone()
        assert_true(cqupt_computer is not None, "重庆邮电大学 计算机科学与技术 row missing.")
        assert_true(cqupt_computer["min_score"] == 595, "重庆邮电大学 计算机科学与技术 score mismatch.")
        assert_true(cqupt_computer["min_rank"] == 13287, "重庆邮电大学 计算机科学与技术 rank mismatch.")

        clinical = conn.execute(
            """
            SELECT school_name, major_name, min_score, min_rank
            FROM admission_history
            WHERE year = 2025
              AND school_name = '重庆医科大学'
              AND major_name = '临床医学'
            """
        ).fetchone()
        assert_true(clinical is not None, "重庆医科大学 临床医学 row missing.")
        assert_true(clinical["min_score"] == 599, "重庆医科大学 临床医学 score mismatch.")
        assert_true(clinical["min_rank"] == 12008, "重庆医科大学 临床医学 rank mismatch.")

        sino_foreign_rows = fetch_count(
            conn,
            """
            SELECT COUNT(*)
            FROM admission_history
            WHERE year = 2025 AND admission_type = '中外合作'
            """,
        )
        assert_true(sino_foreign_rows > 0, "2025 Sino-foreign rows should be present.")

        ordinary_cqupt = fetch_count(
            conn,
            """
            SELECT COUNT(*)
            FROM admission_history
            WHERE year = 2025
              AND school_name LIKE '重庆邮电大学%'
              AND major_name LIKE '%计算机%'
              AND admission_type != '中外合作'
            """,
        )
        assert_true(ordinary_cqupt > 0, "Non-Sino-foreign CQUPT computer rows should be queryable.")
    finally:
        conn.close()
    print("All 2025 Chongqing real-data checks passed.")


if __name__ == "__main__":
    main()
