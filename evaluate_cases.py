#!/usr/bin/env python3
"""Run local evaluation cases stored in recommendation_case."""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from typing import Any

from gaokao_recommender import DEFAULT_DB_PATH, StudentProfile, connect, parse_subjects, recommend
from report_renderer import render_report


ROOT = Path(__file__).resolve().parent


def row_to_profile(row: sqlite3.Row) -> StudentProfile:
    return StudentProfile(
        score=int(row["score"]),
        rank=int(row["rank"]) if row["rank"] is not None else None,
        subject_type=row["subject_type"],
        second_subjects=parse_subjects(row["second_subjects"]),
        major_interest=row["major_interest"] or "",
        risk_level=row["risk_level"],
        accept_sino_foreign=bool(row["accept_sino_foreign"]),
    )


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def assert_candidate(result: dict[str, Any], major_name: str, message: str) -> None:
    assert_true(
        any(item["major_name"] == major_name for item in result["candidates"]),
        message,
    )


def assert_excluded_reason(result: dict[str, Any], text: str, message: str) -> None:
    assert_true(
        any(text in item["reason"] for item in result["excluded"]),
        message,
    )


def verify_case(case_name: str, result: dict[str, Any], report: str) -> None:
    if case_name == "物理不选化学想报计算机":
        assert_true(result["candidates"] == [], "No-Chemistry computer case should have no candidates.")
        assert_excluded_reason(result, "缺少 化学", "No-Chemistry case should explain missing Chemistry.")
    elif case_name == "物理化学考生位次两万附近":
        assert_candidate(result, "计算机类", "Physics+Chemistry case should include Computer.")
        assert_candidate(result, "电子信息类", "Physics+Chemistry case should include Electronic Information.")
        assert_true(
            all(item["admission_type"] != "中外合作" for item in result["candidates"]),
            "Sino-foreign programs should be filtered when not accepted.",
        )
    elif case_name == "历史类师范方向":
        assert_candidate(result, "汉语言文学(师范)", "History teacher case should include Chinese teacher-training.")
        assert_candidate(result, "思想政治教育(师范)", "History teacher case should include Political Education.")
        assert_true("历史" in report and "师范" in report, "History teacher report should mention track and teacher-training.")
    elif case_name == "接受中外合作的物理考生":
        assert_true(
            any(item["admission_type"] == "中外合作" for item in result["candidates"]),
            "Accepted Sino-foreign case should include Sino-foreign candidates.",
        )
        assert_true("中外合作" in report, "Sino-foreign report should mention Sino-foreign programs.")
    else:
        assert_true(result["warnings"], f"{case_name} should return warnings.")
        assert_true("风险声明" in report, f"{case_name} report should contain risk statement.")


def write_case_outputs(output_dir: Path, case_id: int, result: dict[str, Any], report: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / f"case_{case_id}.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / f"case_{case_id}.md").write_text(report, encoding="utf-8")


def run_evaluations(db_path: Path, output_dir: Path | None = None) -> int:
    with connect(db_path) as conn:
        rows = conn.execute("SELECT * FROM recommendation_case ORDER BY id").fetchall()
        assert_true(bool(rows), "recommendation_case table has no rows.")
        for row in rows:
            result = recommend(conn, row_to_profile(row))
            report = render_report(result)
            verify_case(row["case_name"], result, report)
            if output_dir is not None:
                write_case_outputs(output_dir, int(row["id"]), result, report)
            print(f"CASE OK: {row['id']} {row['case_name']}")
    return len(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate recommendation_case rows.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--output-dir", type=Path)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    db_path = args.db if args.db.is_absolute() else ROOT / args.db
    output_dir = None
    if args.output_dir is not None:
        output_dir = args.output_dir if args.output_dir.is_absolute() else ROOT / args.output_dir
    count = run_evaluations(db_path, output_dir)
    print(f"All evaluation cases passed. cases={count}")


if __name__ == "__main__":
    main()
