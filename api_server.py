#!/usr/bin/env python3
"""FastAPI wrapper for the Gaokao volunteer application Agent data service."""

from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, field_validator

from gaokao_recommender import (
    DEFAULT_DB_PATH,
    StudentProfile,
    connect,
    recommend,
)
from report_renderer import render_report


app = FastAPI(
    title="Gaokao Volunteer Agent Data API",
    version="0.1.0",
    description=(
        "Deterministic SQLite-backed data API for a Chongqing Gaokao volunteer "
        "application Agent. Mock data only; official verification is required."
    ),
)


class RecommendRequest(BaseModel):
    score: int = Field(..., ge=0, le=750, description="Gaokao score.")
    rank: int | None = Field(None, gt=0, description="Same-track Chongqing rank.")
    subject_type: str = Field(..., description="物理 or 历史.")
    second_subjects: list[str] = Field(..., min_length=1, description="Second-choice subjects.")
    major_interest: str = Field("", description="Major keyword, e.g. 计算机.")
    risk_level: str = Field("均衡", description="保守 / 均衡 / 激进.")
    accept_sino_foreign: bool = Field(False, description="Whether Sino-foreign programs are accepted.")

    @field_validator("subject_type")
    @classmethod
    def validate_subject_type(cls, value: str) -> str:
        if value not in {"物理", "历史"}:
            raise ValueError("subject_type must be 物理 or 历史")
        return value

    @field_validator("risk_level")
    @classmethod
    def validate_risk_level(cls, value: str) -> str:
        if value not in {"保守", "均衡", "激进"}:
            raise ValueError("risk_level must be 保守, 均衡, or 激进")
        return value


class RecommendResponse(BaseModel):
    student_profile: dict[str, Any]
    warnings: list[str]
    candidates: list[dict[str, Any]]
    excluded: list[dict[str, Any]]


class ReportResponse(BaseModel):
    recommendation: dict[str, Any]
    markdown_report: str


def build_profile(payload: RecommendRequest) -> StudentProfile:
    return StudentProfile(
        score=payload.score,
        rank=payload.rank,
        subject_type=payload.subject_type,
        second_subjects=set(payload.second_subjects),
        major_interest=payload.major_interest,
        risk_level=payload.risk_level,
        accept_sino_foreign=payload.accept_sino_foreign,
    )


def ensure_db_exists(db_path: Path = DEFAULT_DB_PATH) -> None:
    if not db_path.exists():
        raise HTTPException(
            status_code=503,
            detail=f"Database not found: {db_path}. Run python init_db.py first.",
        )


@app.get("/health")
def health() -> dict[str, Any]:
    db_exists = DEFAULT_DB_PATH.exists()
    table_count = 0
    if db_exists:
        with connect(DEFAULT_DB_PATH) as conn:
            table_count = int(
                conn.execute(
                    """
                    SELECT COUNT(*)
                    FROM sqlite_master
                    WHERE type = 'table'
                      AND name NOT LIKE 'sqlite_%'
                    """
                ).fetchone()[0]
            )
    return {
        "ok": db_exists and table_count >= 5,
        "database": str(DEFAULT_DB_PATH),
        "database_exists": db_exists,
        "table_count": table_count,
        "data_scope": "重庆普通类本科批 Mock 数据",
    }


def render_local_form(markdown_report: str | None = None) -> str:
    report_html = ""
    if markdown_report is not None:
        report_html = f"""
        <section class="report">
          <h2>报告草稿</h2>
          <pre>{escape(markdown_report)}</pre>
        </section>
        """

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>重庆高考志愿填报 Agent 本地原型</title>
  <style>
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: #172026;
      background: #f7f8fa;
    }}
    main {{
      max-width: 980px;
      margin: 0 auto;
      padding: 32px 20px 48px;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 28px;
    }}
    .subtitle {{
      margin: 0 0 24px;
      color: #5a6672;
    }}
    form {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 16px;
      padding: 20px;
      background: #fff;
      border: 1px solid #dfe4ea;
      border-radius: 8px;
    }}
    label {{
      display: grid;
      gap: 6px;
      font-size: 14px;
      font-weight: 600;
    }}
    input, select {{
      width: 100%;
      box-sizing: border-box;
      padding: 10px 12px;
      border: 1px solid #c8d0d9;
      border-radius: 6px;
      font: inherit;
      background: #fff;
    }}
    .full {{
      grid-column: 1 / -1;
    }}
    .check {{
      display: flex;
      align-items: center;
      gap: 8px;
      font-weight: 500;
    }}
    .check input {{
      width: auto;
    }}
    button {{
      justify-self: start;
      padding: 10px 16px;
      border: 0;
      border-radius: 6px;
      background: #1d4ed8;
      color: #fff;
      font: inherit;
      font-weight: 700;
      cursor: pointer;
    }}
    .report {{
      margin-top: 24px;
      padding: 20px;
      background: #fff;
      border: 1px solid #dfe4ea;
      border-radius: 8px;
    }}
    pre {{
      white-space: pre-wrap;
      word-break: break-word;
      line-height: 1.6;
      font-family: "SFMono-Regular", Consolas, monospace;
      font-size: 14px;
    }}
    @media (max-width: 720px) {{
      form {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <main>
    <h1>重庆高考志愿填报 Agent 本地原型</h1>
    <p class="subtitle">本页面使用本地 Mock 数据和确定性 Python 规则生成冲稳保报告，不代表真实录取结果。</p>
    <form method="get" action="/web/report">
      <label>分数
        <input name="score" type="number" min="0" max="750" value="596" required>
      </label>
      <label>位次
        <input name="rank" type="number" min="1" value="20000">
      </label>
      <label>首选科目
        <select name="subject_type">
          <option value="物理" selected>物理</option>
          <option value="历史">历史</option>
        </select>
      </label>
      <label>再选科目（用逗号分隔）
        <input name="second_subjects" value="化学,生物" required>
      </label>
      <label>专业兴趣
        <input name="major_interest" value="计算机">
      </label>
      <label>风险偏好
        <select name="risk_level">
          <option value="保守">保守</option>
          <option value="均衡" selected>均衡</option>
          <option value="激进">激进</option>
        </select>
      </label>
      <label class="check full">
        <input name="accept_sino_foreign" type="checkbox" value="true">
        接受中外合作/高学费项目
      </label>
      <button class="full" type="submit">生成报告</button>
    </form>
    {report_html}
  </main>
</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def local_home() -> HTMLResponse:
    return HTMLResponse(render_local_form())


@app.get("/web/report", response_class=HTMLResponse)
def local_report(
    score: int = Query(..., ge=0, le=750),
    rank: int | None = Query(None, gt=0),
    subject_type: str = Query(..., pattern="^(物理|历史)$"),
    second_subjects: str = Query(...),
    major_interest: str = Query(""),
    risk_level: str = Query("均衡", pattern="^(保守|均衡|激进)$"),
    accept_sino_foreign: bool = Query(False),
) -> HTMLResponse:
    ensure_db_exists()
    payload = RecommendRequest(
        score=score,
        rank=rank,
        subject_type=subject_type,
        second_subjects=[part.strip() for part in second_subjects.replace("，", ",").split(",") if part.strip()],
        major_interest=major_interest,
        risk_level=risk_level,
        accept_sino_foreign=accept_sino_foreign,
    )
    with connect(DEFAULT_DB_PATH) as conn:
        recommendation = recommend(conn, build_profile(payload))
    return HTMLResponse(render_local_form(render_report(recommendation)))


@app.post("/recommend", response_model=RecommendResponse)
def recommend_endpoint(payload: RecommendRequest) -> dict[str, Any]:
    ensure_db_exists()
    with connect(DEFAULT_DB_PATH) as conn:
        return recommend(conn, build_profile(payload))


@app.post("/report", response_model=ReportResponse)
def report_endpoint(payload: RecommendRequest) -> dict[str, Any]:
    ensure_db_exists()
    with connect(DEFAULT_DB_PATH) as conn:
        recommendation = recommend(conn, build_profile(payload))
    return {
        "recommendation": recommendation,
        "markdown_report": render_report(recommendation),
    }


@app.get("/admissions/trend")
def admission_trend(
    school_name: str = Query(..., description="School name, e.g. 重庆邮电大学."),
    major_name: str = Query(..., description="Major name, e.g. 计算机类."),
    subject_type: str = Query(..., pattern="^(物理|历史)$"),
) -> dict[str, Any]:
    ensure_db_exists()
    with connect(DEFAULT_DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT year, school_name, major_name, major_group_code, admission_type,
                   min_score, min_rank, plan_count, source_url, source_type, confidence
            FROM admission_history
            WHERE school_name = ?
              AND major_name = ?
              AND subject_type = ?
            ORDER BY year
            """,
            (school_name, major_name, subject_type),
        ).fetchall()

    return {
        "school_name": school_name,
        "major_name": major_name,
        "subject_type": subject_type,
        "history": [{key: row[key] for key in row.keys()} for row in rows],
        "warning": "Mock 数据仅用于开发测试，真实使用需替换为官方数据。",
    }


@app.get("/subject-requirements")
def subject_requirements(
    school_name: str = Query(...),
    major_name: str = Query(...),
    requirement_year: int = Query(2026, ge=2021, le=2030),
) -> dict[str, Any]:
    ensure_db_exists()
    with connect(DEFAULT_DB_PATH) as conn:
        rows = conn.execute(
            """
            SELECT school_name, major_name, major_category, requirement_year,
                   first_subject_required, second_subjects_required,
                   requirement_text, source_url, effective_from, effective_to
            FROM subject_requirement
            WHERE school_name = ?
              AND major_name = ?
              AND requirement_year = ?
            ORDER BY effective_from DESC
            """,
            (school_name, major_name, requirement_year),
        ).fetchall()

    return {
        "school_name": school_name,
        "major_name": major_name,
        "requirement_year": requirement_year,
        "requirements": [{key: row[key] for key in row.keys()} for row in rows],
        "warning": "正式填报前必须以阳光高考和高校招生章程为准。",
    }


@app.get("/search/admissions")
def search_admissions(
    subject_type: str = Query(..., pattern="^(物理|历史)$"),
    rank: int | None = Query(None, gt=0),
    major_keyword: str = Query(""),
    accept_sino_foreign: bool = Query(False),
    limit: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    ensure_db_exists()
    keyword = f"%{major_keyword.strip()}%" if major_keyword.strip() else "%"
    params: list[Any] = [subject_type, keyword, keyword, keyword]
    rank_filter = ""
    if rank is not None:
        rank_filter = "AND min_rank BETWEEN ? AND ?"
        params.extend([int(rank * 0.7), int(rank * 1.6)])

    sino_filter = ""
    if not accept_sino_foreign:
        sino_filter = "AND admission_type != '中外合作'"

    params.append(limit)
    sql = f"""
        SELECT year, school_name, major_name, major_group_code, admission_type,
               min_score, min_rank, plan_count, risk_notes, source_url, confidence
        FROM admission_history
        WHERE year = 2025
          AND subject_type = ?
          AND batch = '本科批'
          AND (major_name LIKE ? OR major_category LIKE ? OR discipline_category LIKE ?)
          {rank_filter}
          {sino_filter}
        ORDER BY min_rank
        LIMIT ?
    """

    with connect(DEFAULT_DB_PATH) as conn:
        rows = conn.execute(sql, params).fetchall()

    return {
        "items": [{key: row[key] for key in row.keys()} for row in rows],
        "warning": "该接口仅做结构化历史数据搜索，不替代完整推荐和官方实时核验。",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api_server:app", host="127.0.0.1", port=8000, reload=False)
