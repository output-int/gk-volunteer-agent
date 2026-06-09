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

    data_quality = client.get("/data-quality")
    assert_true(data_quality.status_code == 200, data_quality.text)
    data_quality_data = data_quality.json()
    assert_true(data_quality_data["ok"] is True, f"data quality should pass with warnings: {data_quality_data}")
    assert_true(data_quality_data["error_count"] == 0, "Mock data should have no data-quality errors.")
    assert_true(data_quality_data["warning_count"] >= 1, "Mock data should expose known enrichment warnings.")
    assert_true(
        "admission_history" in data_quality_data["table_counts"],
        "Data quality response should include table counts.",
    )

    strict_data_quality = client.get("/data-quality", params={"strict_warnings": True})
    assert_true(strict_data_quality.status_code == 200, strict_data_quality.text)
    assert_true(
        strict_data_quality.json()["ok"] is False,
        "Strict data quality should fail while Mock enrichment warnings remain.",
    )

    home = client.get("/")
    assert_true(home.status_code == 200, home.text)
    assert_true("重庆高考志愿填报 Agent 本地原型" in home.text, "Local web home title missing.")
    assert_true('action="/web/report"' in home.text, "Local web form action missing.")

    web_report = client.get(
        "/web/report",
        params={
            "score": 596,
            "rank": 20000,
            "subject_type": "物理",
            "second_subjects": "化学,生物",
            "major_interest": "计算机",
            "risk_level": "均衡",
            "accept_sino_foreign": False,
        },
    )
    assert_true(web_report.status_code == 200, web_report.text)
    assert_true("报告草稿" in web_report.text, "Local web report section missing.")
    assert_true("/web/report.md?" in web_report.text, "Local Markdown download link missing.")
    assert_true("重庆邮电大学" in web_report.text, "Local web report should include candidate details.")

    markdown_download = client.get(
        "/web/report.md",
        params={
            "score": 596,
            "rank": 20000,
            "subject_type": "物理",
            "second_subjects": "化学,生物",
            "major_interest": "计算机",
            "risk_level": "均衡",
            "accept_sino_foreign": False,
        },
    )
    assert_true(markdown_download.status_code == 200, markdown_download.text)
    assert_true(
        markdown_download.headers["content-type"].startswith("text/markdown"),
        "Markdown download should use text/markdown.",
    )
    assert_true(
        'filename="gaokao_report.md"' in markdown_download.headers["content-disposition"],
        "Markdown download filename missing.",
    )
    assert_true("# 重庆高考志愿填报辅助报告" in markdown_download.text, "Downloaded report title missing.")
    assert_true("重庆邮电大学" in markdown_download.text, "Downloaded report should include candidate details.")

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
