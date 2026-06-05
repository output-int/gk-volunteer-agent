#!/usr/bin/env python3
"""Initialize the Gaokao volunteer Agent SQLite database.

This script uses only Python's standard library. By default it recreates
gaokao_agent.db from db/init.sql so repeated development runs stay predictable.
"""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DEFAULT_DB_PATH = ROOT / "gaokao_agent.db"
DEFAULT_SQL_PATH = ROOT / "db" / "init.sql"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create and populate the Gaokao Agent SQLite database."
    )
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB_PATH,
        help=f"SQLite database path. Default: {DEFAULT_DB_PATH}",
    )
    parser.add_argument(
        "--sql",
        type=Path,
        default=DEFAULT_SQL_PATH,
        help=f"SQL initialization script path. Default: {DEFAULT_SQL_PATH}",
    )
    parser.add_argument(
        "--no-overwrite",
        action="store_true",
        help="Fail if the target database already exists.",
    )
    return parser.parse_args()


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def print_rows(title: str, columns: list[str], rows: list[sqlite3.Row]) -> None:
    print(f"\n{title}")
    print("-" * len(title))
    if not rows:
        print("(no rows)")
        return

    print(" | ".join(columns))
    print(" | ".join("-" * len(column) for column in columns))
    for row in rows:
        print(" | ".join(str(row[column]) for column in columns))


def run_scalar(conn: sqlite3.Connection, sql: str, params: tuple = ()) -> int:
    value = conn.execute(sql, params).fetchone()[0]
    return int(value)


def run_verification(conn: sqlite3.Connection) -> None:
    print("\nDatabase summary")
    print("----------------")
    table_count = run_scalar(
        conn,
        """
        SELECT COUNT(*)
        FROM sqlite_master
        WHERE type = 'table'
          AND name NOT LIKE 'sqlite_%'
        """,
    )
    print(f"User tables: {table_count}")

    for table_name in (
        "admission_history",
        "score_rank_table",
        "subject_requirement",
        "school_major_profile",
        "recommendation_case",
    ):
        count = run_scalar(conn, f"SELECT COUNT(*) FROM {table_name}")
        print(f"{table_name}: {count} rows")

    rows = conn.execute(
        """
        SELECT year, school_name, major_name, admission_type, min_score, min_rank
        FROM admission_history
        WHERE year = 2025
          AND subject_type = '物理'
          AND batch = '本科批'
          AND min_rank BETWEEN 15000 AND 26000
          AND admission_type != '中外合作'
        ORDER BY min_rank
        """
    ).fetchall()
    print_rows(
        "Verification 1: Physics candidates around rank 20000",
        ["year", "school_name", "major_name", "admission_type", "min_score", "min_rank"],
        rows,
    )

    rows = conn.execute(
        """
        SELECT year, school_name, major_name, min_score, min_rank, source_type, confidence
        FROM admission_history
        WHERE school_name = '重庆邮电大学'
          AND major_name = '计算机类'
        ORDER BY year
        """
    ).fetchall()
    print_rows(
        "Verification 2: Chongqing University of Posts and Telecommunications computer trend",
        ["year", "school_name", "major_name", "min_score", "min_rank", "source_type", "confidence"],
        rows,
    )

    rows = conn.execute(
        """
        SELECT school_name, major_name, requirement_year, requirement_text
        FROM subject_requirement
        WHERE major_name = '临床医学'
          AND requirement_year = 2026
        """
    ).fetchall()
    print_rows(
        "Verification 3: Clinical Medicine 2026 subject requirement",
        ["school_name", "major_name", "requirement_year", "requirement_text"],
        rows,
    )

    rows = conn.execute(
        """
        SELECT school_name, major_name, admission_type, min_score, min_rank
        FROM admission_history
        WHERE year = 2025
          AND subject_type = '物理'
          AND admission_type != '中外合作'
        ORDER BY min_rank
        LIMIT 10
        """
    ).fetchall()
    print_rows(
        "Verification 4: Sino-foreign programs filtered out",
        ["school_name", "major_name", "admission_type", "min_score", "min_rank"],
        rows,
    )


def main() -> None:
    args = parse_args()
    db_path = resolve_path(args.db)
    sql_path = resolve_path(args.sql)

    if not sql_path.exists():
        raise FileNotFoundError(f"SQL script not found: {sql_path}")

    if db_path.exists():
        if args.no_overwrite:
            raise FileExistsError(f"Database already exists: {db_path}")
        db_path.unlink()

    db_path.parent.mkdir(parents=True, exist_ok=True)
    sql_script = sql_path.read_text(encoding="utf-8")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(sql_script)
        conn.commit()
        print(f"Created SQLite database: {db_path}")
        print(f"Executed SQL script: {sql_path}")
        run_verification(conn)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
