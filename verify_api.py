#!/usr/bin/env python3
"""Smoke tests for the FastAPI wrapper."""

from __future__ import annotations

from fastapi.testclient import TestClient

from api_server import app


client = TestClient(app)


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    health = client.get("/health")
    assert_true(health.status_code == 200, f"health failed: {health.text}")
    assert_true(health.json()["ok"] is True, f"database is not healthy: {health.json()}")

    no_chemistry = client.post(
        "/recommend",
        json={
            "score": 590,
            "rank": 22000,
            "subject_type": "物理",
            "second_subjects": ["生物", "地理"],
            "major_interest": "计算机",
            "risk_level": "均衡",
            "accept_sino_foreign": False,
        },
    )
    assert_true(no_chemistry.status_code == 200, no_chemistry.text)
    no_chemistry_data = no_chemistry.json()
    assert_true(no_chemistry_data["candidates"] == [], "Computer candidates must be blocked without Chemistry.")
    assert_true(
        any("缺少 化学" in item["reason"] for item in no_chemistry_data["excluded"]),
        "Missing Chemistry exclusion reason should be present.",
    )

    recommendation = client.post(
        "/recommend",
        json={
            "score": 596,
            "rank": 20000,
            "subject_type": "物理",
            "second_subjects": ["化学", "生物"],
            "major_interest": "计算机",
            "risk_level": "均衡",
            "accept_sino_foreign": False,
        },
    )
    assert_true(recommendation.status_code == 200, recommendation.text)
    recommendation_data = recommendation.json()
    assert_true(
        recommendation_data["student_profile"]["rank_reference_year"] == 2025,
        "Recommendation should expose equivalent-rank reference year.",
    )
    assert_true(
        any(item["rank_method"] == "equivalent_rank" for item in recommendation_data["candidates"]),
        "Recommendation candidates should expose equivalent-rank method.",
    )

    report = client.post(
        "/report",
        json={
            "score": 596,
            "rank": 20000,
            "subject_type": "物理",
            "second_subjects": ["化学", "生物"],
            "major_interest": "计算机",
            "risk_level": "均衡",
            "accept_sino_foreign": False,
        },
    )
    assert_true(report.status_code == 200, report.text)
    report_data = report.json()
    assert_true("# 重庆高考志愿填报辅助报告" in report_data["markdown_report"], "Report title missing.")
    assert_true("重庆邮电大学" in report_data["markdown_report"], "Report should include candidate details.")
    assert_true("风险声明" in report_data["markdown_report"], "Report should include risk statement.")

    trend = client.get(
        "/admissions/trend",
        params={
            "school_name": "重庆邮电大学",
            "major_name": "计算机类",
            "subject_type": "物理",
        },
    )
    assert_true(trend.status_code == 200, trend.text)
    assert_true(len(trend.json()["history"]) == 2, "CQUPT Computer trend should have two mock years.")

    requirement = client.get(
        "/subject-requirements",
        params={
            "school_name": "重庆医科大学",
            "major_name": "临床医学",
            "requirement_year": 2026,
        },
    )
    assert_true(requirement.status_code == 200, requirement.text)
    requirements = requirement.json()["requirements"]
    assert_true(requirements, "Clinical Medicine subject requirement should exist.")
    assert_true(requirements[0]["second_subjects_required"] == "化学", "Clinical Medicine should require Chemistry.")

    search = client.get(
        "/search/admissions",
        params={
            "subject_type": "物理",
            "rank": 20000,
            "major_keyword": "计算机",
            "accept_sino_foreign": False,
        },
    )
    assert_true(search.status_code == 200, search.text)
    assert_true(
        all(item["admission_type"] != "中外合作" for item in search.json()["items"]),
        "Sino-foreign records should be filtered from search when not accepted.",
    )

    print("All API smoke tests passed.")


if __name__ == "__main__":
    main()
