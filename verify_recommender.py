#!/usr/bin/env python3
"""Smoke tests for the deterministic recommendation layer.

These are intentionally small and dependency-free. They protect the core
business constraints that must stay outside the LLM.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from gaokao_recommender import StudentProfile, connect, parse_subjects, recommend


ROOT = Path(__file__).resolve().parent
DB_PATH = ROOT / "gaokao_agent.db"


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def assert_any(items: list[dict], predicate, message: str) -> None:
    assert_true(any(predicate(item) for item in items), message)


def run_case(conn: sqlite3.Connection, profile: StudentProfile) -> dict:
    return recommend(conn, profile)


def main() -> None:
    assert_true(DB_PATH.exists(), f"Database does not exist: {DB_PATH}. Run python init_db.py first.")

    with connect(DB_PATH) as conn:
        no_chemistry = run_case(
            conn,
            StudentProfile(
                score=590,
                rank=22000,
                subject_type="物理",
                second_subjects=parse_subjects("生物,地理"),
                major_interest="计算机",
                risk_level="均衡",
                accept_sino_foreign=False,
            ),
        )
        assert_true(no_chemistry["candidates"] == [], "Computer candidates must be blocked without Chemistry.")
        assert_any(
            no_chemistry["excluded"],
            lambda item: "缺少 化学" in item["reason"],
            "Missing Chemistry reason should be visible.",
        )

        physics_chemistry = run_case(
            conn,
            StudentProfile(
                score=596,
                rank=20000,
                subject_type="物理",
                second_subjects=parse_subjects("化学,生物"),
                major_interest="计算机",
                risk_level="均衡",
                accept_sino_foreign=False,
            ),
        )
        assert_any(
            physics_chemistry["candidates"],
            lambda item: item["school_name"] == "重庆邮电大学" and item["major_name"] == "计算机类",
            "CQUPT Computer should be returned for a Physics+Chemistry candidate.",
        )
        assert_any(
            physics_chemistry["candidates"],
            lambda item: (
                item["school_name"] == "重庆邮电大学"
                and item["major_name"] == "计算机类"
                and item["rank_method"] == "equivalent_rank"
                and item["latest_equivalent_min_rank"] == 18500
                and item["history"][0]["equivalent_min_rank"] == 20160
            ),
            "CQUPT Computer should expose equivalent-rank calculations.",
        )
        assert_true(
            physics_chemistry["student_profile"]["rank_reference_year"] == 2025,
            "Rank reference year should come from score_rank_table.",
        )
        assert_true(
            all(item["admission_type"] != "中外合作" for item in physics_chemistry["candidates"]),
            "Sino-foreign programs must be filtered when not accepted.",
        )

        history_teacher = run_case(
            conn,
            StudentProfile(
                score=548,
                rank=8800,
                subject_type="历史",
                second_subjects=parse_subjects("政治,地理"),
                major_interest="师范",
                risk_level="保守",
                accept_sino_foreign=False,
            ),
        )
        assert_any(
            history_teacher["candidates"],
            lambda item: "师范" in item["major_name"],
            "History teacher-oriented case should return teacher-training candidates.",
        )

        accepts_sino_foreign = run_case(
            conn,
            StudentProfile(
                score=552,
                rank=40000,
                subject_type="物理",
                second_subjects=parse_subjects("化学,生物"),
                major_interest="软件",
                risk_level="激进",
                accept_sino_foreign=True,
            ),
        )
        assert_any(
            accepts_sino_foreign["candidates"],
            lambda item: item["admission_type"] == "中外合作",
            "Sino-foreign candidate should be allowed when explicitly accepted.",
        )

    print("All recommender smoke tests passed.")


if __name__ == "__main__":
    main()
