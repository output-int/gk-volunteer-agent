#!/usr/bin/env python3
"""Validate SQLite data quality for the local Gaokao Agent."""

from __future__ import annotations

import argparse
import csv
import json
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DEFAULT_DB_PATH = ROOT / "gaokao_agent.db"
REQUIRED_TABLES = [
    "admission_history",
    "score_rank_table",
    "subject_requirement",
    "school_major_profile",
    "recommendation_case",
]

GAP_COLUMNS = [
    "gap_type",
    "priority",
    "target_table",
    "school_name",
    "major_name",
    "source_year",
    "suggested_action",
]


@dataclass(frozen=True)
class DataIssue:
    severity: str
    code: str
    message: str
    count: int = 0
    sample: list[dict[str, Any]] | None = None


def resolve_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def connect(db_path: Path) -> sqlite3.Connection:
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}. Run python init_db.py first.")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    return [{key: row[key] for key in row.keys()} for row in rows]


def query_issue(
    conn: sqlite3.Connection,
    *,
    severity: str,
    code: str,
    message: str,
    sql: str,
    params: tuple[Any, ...] = (),
    sample_limit: int = 5,
) -> DataIssue | None:
    rows = conn.execute(sql, params).fetchall()
    if not rows:
        return None
    return DataIssue(
        severity=severity,
        code=code,
        message=message,
        count=len(rows),
        sample=rows_to_dicts(rows[:sample_limit]),
    )


def validate_required_tables(conn: sqlite3.Connection) -> list[DataIssue]:
    existing = {
        row["name"]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()
    }
    issues: list[DataIssue] = []
    missing = [table for table in REQUIRED_TABLES if table not in existing]
    if missing:
        issues.append(
            DataIssue(
                severity="ERROR",
                code="missing_required_tables",
                message="Required tables are missing.",
                count=len(missing),
                sample=[{"table": table} for table in missing],
            )
        )
        return issues

    empty_tables = []
    for table in REQUIRED_TABLES:
        count = int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        if count == 0:
            empty_tables.append({"table": table})
    if empty_tables:
        issues.append(
            DataIssue(
                severity="ERROR",
                code="empty_required_tables",
                message="Required tables must contain seed or imported data.",
                count=len(empty_tables),
                sample=empty_tables,
            )
        )
    return issues


def validate_admission_history(conn: sqlite3.Connection) -> list[DataIssue]:
    issues: list[DataIssue] = []
    duplicate_issue = query_issue(
        conn,
        severity="ERROR",
        code="duplicate_admission_natural_key",
        message="Admission history contains duplicate natural keys.",
        sql="""
            SELECT year, province, subject_type, batch, school_code,
                   COALESCE(major_group_code, '') AS major_group_code,
                   major_code, admission_type, COUNT(*) AS duplicate_count
            FROM admission_history
            GROUP BY year, province, subject_type, batch, school_code,
                     COALESCE(major_group_code, ''), major_code, admission_type
            HAVING COUNT(*) > 1
            ORDER BY duplicate_count DESC
        """,
    )
    if duplicate_issue:
        issues.append(duplicate_issue)

    special_type_issue = query_issue(
        conn,
        severity="ERROR",
        code="special_type_missing_risk_notes",
        message="Special admission types must carry risk notes for filtering and report warnings.",
        sql="""
            SELECT year, school_name, major_name, admission_type
            FROM admission_history
            WHERE admission_type != '普通类'
              AND (risk_notes IS NULL OR TRIM(risk_notes) = '')
            ORDER BY year DESC, school_name, major_name
        """,
    )
    if special_type_issue:
        issues.append(special_type_issue)

    profile_gap_issue = query_issue(
        conn,
        severity="WARN",
        code="missing_school_major_profile",
        message="Some 2025 admission records have no school_major_profile enrichment.",
        sql="""
            SELECT DISTINCT a.school_name, a.major_name
            FROM admission_history a
            LEFT JOIN school_major_profile p
              ON p.school_name = a.school_name
             AND p.major_name = a.major_name
            WHERE a.year = 2025
              AND p.id IS NULL
            ORDER BY a.school_name, a.major_name
        """,
    )
    if profile_gap_issue:
        issues.append(profile_gap_issue)

    requirement_gap_issue = query_issue(
        conn,
        severity="WARN",
        code="missing_2026_subject_requirement",
        message="Some 2025 admission records have no 2026 subject requirement row.",
        sql="""
            SELECT DISTINCT a.school_name, a.major_name
            FROM admission_history a
            LEFT JOIN subject_requirement r
              ON r.school_name = a.school_name
             AND r.major_name = a.major_name
             AND r.requirement_year = 2026
            WHERE a.year = 2025
              AND r.id IS NULL
            ORDER BY a.school_name, a.major_name
        """,
    )
    if requirement_gap_issue:
        issues.append(requirement_gap_issue)

    return issues


def validate_score_rank_table(conn: sqlite3.Connection) -> list[DataIssue]:
    issues: list[DataIssue] = []
    duplicate_issue = query_issue(
        conn,
        severity="ERROR",
        code="duplicate_score_rank_key",
        message="Score-rank table contains duplicate year/province/subject/score rows.",
        sql="""
            SELECT year, province, subject_type, score, COUNT(*) AS duplicate_count
            FROM score_rank_table
            GROUP BY year, province, subject_type, score
            HAVING COUNT(*) > 1
            ORDER BY duplicate_count DESC
        """,
    )
    if duplicate_issue:
        issues.append(duplicate_issue)

    inconsistent_count_issue = query_issue(
        conn,
        severity="ERROR",
        code="score_rank_span_mismatch",
        message="same_score_count must match rank_max - rank_min + 1.",
        sql="""
            SELECT year, province, subject_type, score, rank_min, rank_max, same_score_count
            FROM score_rank_table
            WHERE same_score_count != rank_max - rank_min + 1
            ORDER BY year DESC, subject_type, score DESC
        """,
    )
    if inconsistent_count_issue:
        issues.append(inconsistent_count_issue)

    monotonic_issues = []
    groups = conn.execute(
        """
        SELECT DISTINCT year, province, subject_type
        FROM score_rank_table
        ORDER BY year, province, subject_type
        """
    ).fetchall()
    for group in groups:
        rows = conn.execute(
            """
            SELECT score, cumulative_count
            FROM score_rank_table
            WHERE year = ? AND province = ? AND subject_type = ?
            ORDER BY score DESC
            """,
            (group["year"], group["province"], group["subject_type"]),
        ).fetchall()
        previous = None
        for row in rows:
            if previous is not None and row["cumulative_count"] < previous["cumulative_count"]:
                monotonic_issues.append(
                    {
                        "year": group["year"],
                        "province": group["province"],
                        "subject_type": group["subject_type"],
                        "score": row["score"],
                        "cumulative_count": row["cumulative_count"],
                        "previous_higher_score_cumulative_count": previous["cumulative_count"],
                    }
                )
            previous = row
    if monotonic_issues:
        issues.append(
            DataIssue(
                severity="ERROR",
                code="score_rank_cumulative_not_monotonic",
                message="Cumulative counts must not decrease as scores go down.",
                count=len(monotonic_issues),
                sample=monotonic_issues[:5],
            )
        )
    return issues


def validate_subject_requirements(conn: sqlite3.Connection) -> list[DataIssue]:
    issues: list[DataIssue] = []
    duplicate_issue = query_issue(
        conn,
        severity="ERROR",
        code="duplicate_subject_requirement",
        message="Subject requirements contain duplicate rows for the same school/major/year/effective range.",
        sql="""
            SELECT school_name, major_name, requirement_year, effective_from,
                   COALESCE(effective_to, 9999) AS effective_to, COUNT(*) AS duplicate_count
            FROM subject_requirement
            GROUP BY school_name, major_name, requirement_year, effective_from, COALESCE(effective_to, 9999)
            HAVING COUNT(*) > 1
            ORDER BY duplicate_count DESC
        """,
    )
    if duplicate_issue:
        issues.append(duplicate_issue)

    stem_requirement_issue = query_issue(
        conn,
        severity="ERROR",
        code="stem_medicine_2026_missing_physics_chemistry",
        message="2026 computer/electronic/medicine/engineering mock requirements must enforce physics plus chemistry.",
        sql="""
            SELECT school_name, major_name, major_category, first_subject_required, second_subjects_required
            FROM subject_requirement
            WHERE requirement_year = 2026
              AND (
                    major_category LIKE '%计算机%'
                 OR major_category LIKE '%电子%'
                 OR major_category LIKE '%临床%'
                 OR major_category LIKE '%药学%'
                 OR major_category LIKE '%机械%'
              )
              AND (
                    first_subject_required != '物理'
                 OR second_subjects_required NOT LIKE '%化学%'
              )
            ORDER BY school_name, major_name
        """,
    )
    if stem_requirement_issue:
        issues.append(stem_requirement_issue)

    return issues


def validate_database(db_path: Path) -> list[DataIssue]:
    with connect(db_path) as conn:
        issues = validate_required_tables(conn)
        if any(issue.severity == "ERROR" and issue.code == "missing_required_tables" for issue in issues):
            return issues
        issues.extend(validate_admission_history(conn))
        issues.extend(validate_score_rank_table(conn))
        issues.extend(validate_subject_requirements(conn))
        return issues


def collect_data_gaps(db_path: Path) -> list[dict[str, Any]]:
    with connect(db_path) as conn:
        profile_rows = conn.execute(
            """
            SELECT DISTINCT a.school_name, a.major_name, MAX(a.year) AS source_year
            FROM admission_history a
            LEFT JOIN school_major_profile p
              ON p.school_name = a.school_name
             AND p.major_name = a.major_name
            WHERE a.year = 2025
              AND p.id IS NULL
            GROUP BY a.school_name, a.major_name
            ORDER BY a.school_name, a.major_name
            """
        ).fetchall()
        requirement_rows = conn.execute(
            """
            SELECT DISTINCT a.school_name, a.major_name, MAX(a.year) AS source_year
            FROM admission_history a
            LEFT JOIN subject_requirement r
              ON r.school_name = a.school_name
             AND r.major_name = a.major_name
             AND r.requirement_year = 2026
            WHERE a.year = 2025
              AND r.id IS NULL
            GROUP BY a.school_name, a.major_name
            ORDER BY a.school_name, a.major_name
            """
        ).fetchall()

    gaps: list[dict[str, Any]] = []
    for row in profile_rows:
        gaps.append(
            {
                "gap_type": "missing_school_major_profile",
                "priority": "medium",
                "target_table": "school_major_profile",
                "school_name": row["school_name"],
                "major_name": row["major_name"],
                "source_year": row["source_year"],
                "suggested_action": "补充就业方向、考研方向、专业风险备注和来源链接。",
            }
        )
    for row in requirement_rows:
        gaps.append(
            {
                "gap_type": "missing_2026_subject_requirement",
                "priority": "high",
                "target_table": "subject_requirement",
                "school_name": row["school_name"],
                "major_name": row["major_name"],
                "source_year": row["source_year"],
                "suggested_action": "核验并补充 2026 选科要求、适用年份、来源链接和有效期。",
            }
        )
    return sorted(gaps, key=lambda item: (item["priority"] != "high", item["school_name"], item["major_name"]))


def render_gap_markdown(gaps: list[dict[str, Any]]) -> str:
    lines = [
        "# 高考志愿填报 Agent 数据补全清单",
        "",
        "该清单由本地 SQLite 数据质量校验生成，用于指导后续人工补录和官方来源核验。",
        "",
        "| 优先级 | 缺口类型 | 目标表 | 学校 | 专业 | 建议动作 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    if not gaps:
        lines.append("| - | - | - | - | - | 当前没有可导出的补数缺口。 |")
    else:
        for gap in gaps:
            lines.append(
                "| {priority} | {gap_type} | {target_table} | {school_name} | {major_name} | {suggested_action} |".format(
                    **gap
                )
            )
    lines.extend(
        [
            "",
            "## 使用建议",
            "",
            "1. 优先补 `subject_requirement` 中的 2026 选科要求，避免硬规则误判。",
            "2. 再补 `school_major_profile` 中的专业画像，用于解释报告和风险提示。",
            "3. 每次补录后运行 `python validate_data.py --strict-warnings` 复查。",
        ]
    )
    return "\n".join(lines).rstrip() + "\n"


def export_data_gaps(db_path: Path, output_dir: Path) -> dict[str, Any]:
    resolved_output = resolve_path(output_dir)
    resolved_output.mkdir(parents=True, exist_ok=True)
    gaps = collect_data_gaps(db_path)
    csv_path = resolved_output / "data_gaps.csv"
    markdown_path = resolved_output / "data_gaps.md"

    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=GAP_COLUMNS)
        writer.writeheader()
        writer.writerows(gaps)
    markdown_path.write_text(render_gap_markdown(gaps), encoding="utf-8")

    return {
        "gap_count": len(gaps),
        "csv_path": str(csv_path),
        "markdown_path": str(markdown_path),
    }


def summarize_counts(db_path: Path) -> dict[str, int]:
    with connect(db_path) as conn:
        return {
            table: int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in REQUIRED_TABLES
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate gaokao_agent.db data quality.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--json", action="store_true", help="Print machine-readable validation result.")
    parser.add_argument("--strict-warnings", action="store_true", help="Exit non-zero when warnings are present.")
    parser.add_argument("--export-gaps", type=Path, help="Write actionable data gap CSV/Markdown files.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    db_path = resolve_path(args.db)
    issues = validate_database(db_path)
    counts = summarize_counts(db_path)
    gap_export = export_data_gaps(db_path, args.export_gaps) if args.export_gaps else None
    error_count = sum(1 for issue in issues if issue.severity == "ERROR")
    warning_count = sum(1 for issue in issues if issue.severity == "WARN")

    if args.json:
        print(
            json.dumps(
                {
                    "ok": error_count == 0 and (warning_count == 0 or not args.strict_warnings),
                    "db_path": str(db_path),
                    "table_counts": counts,
                    "error_count": error_count,
                    "warning_count": warning_count,
                    "issues": [asdict(issue) for issue in issues],
                    "gap_export": gap_export,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    else:
        print(f"Data quality validation: {db_path}")
        print("Table counts")
        for table, count in counts.items():
            print(f"- {table}: {count}")
        if not issues:
            print("\nNo data quality issues found.")
        else:
            print(f"\nIssues: errors={error_count}, warnings={warning_count}")
            for issue in issues:
                print(f"- [{issue.severity}] {issue.code}: {issue.message} count={issue.count}")
                for sample in issue.sample or []:
                    print(f"  sample: {sample}")
        if gap_export is not None:
            print("\nData gap export")
            print(f"- gap_count: {gap_export['gap_count']}")
            print(f"- csv_path: {gap_export['csv_path']}")
            print(f"- markdown_path: {gap_export['markdown_path']}")

    if error_count or (args.strict_warnings and warning_count):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
