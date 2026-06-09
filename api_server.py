#!/usr/bin/env python3
"""FastAPI wrapper for the Gaokao volunteer application Agent data service."""

from __future__ import annotations

import csv
import io
from html import escape
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel, Field, field_validator

from gaokao_recommender import (
    DEFAULT_DB_PATH,
    StudentProfile,
    connect,
    recommend,
)
from report_renderer import build_official_checks, render_report
from validate_data import GAP_COLUMNS, collect_data_gaps, render_gap_markdown, summarize_counts, validate_database


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
    accepted_admission_types: list[str] = Field(
        default_factory=list,
        description="Special admission types explicitly accepted, e.g. 民族班 / 预科 / 专项.",
    )

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

    @field_validator("accepted_admission_types")
    @classmethod
    def validate_accepted_admission_types(cls, value: list[str]) -> list[str]:
        allowed = {"中外合作", "民族班", "预科", "专项"}
        invalid = [item for item in value if item not in allowed]
        if invalid:
            raise ValueError(f"accepted_admission_types contains invalid values: {invalid}")
        return value


class RecommendResponse(BaseModel):
    student_profile: dict[str, Any]
    warnings: list[str]
    candidates: list[dict[str, Any]]
    excluded: list[dict[str, Any]]


class ReportResponse(BaseModel):
    recommendation: dict[str, Any]
    official_checks: dict[str, Any]
    markdown_report: str


class DataQualityResponse(BaseModel):
    ok: bool
    database: str
    table_counts: dict[str, int]
    error_count: int
    warning_count: int
    issues: list[dict[str, Any]]


def build_profile(payload: RecommendRequest) -> StudentProfile:
    return StudentProfile(
        score=payload.score,
        rank=payload.rank,
        subject_type=payload.subject_type,
        second_subjects=set(payload.second_subjects),
        major_interest=payload.major_interest,
        risk_level=payload.risk_level,
        accept_sino_foreign=payload.accept_sino_foreign,
        accepted_admission_types=set(payload.accepted_admission_types),
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


@app.get("/data-quality", response_model=DataQualityResponse)
def data_quality(strict_warnings: bool = Query(False)) -> dict[str, Any]:
    return build_data_quality_payload(strict_warnings)


def build_data_quality_payload(strict_warnings: bool = False) -> dict[str, Any]:
    ensure_db_exists()
    issues = validate_database(DEFAULT_DB_PATH)
    table_counts = summarize_counts(DEFAULT_DB_PATH)
    error_count = sum(1 for issue in issues if issue.severity == "ERROR")
    warning_count = sum(1 for issue in issues if issue.severity == "WARN")
    return {
        "ok": error_count == 0 and (warning_count == 0 or not strict_warnings),
        "database": str(DEFAULT_DB_PATH),
        "table_counts": table_counts,
        "error_count": error_count,
        "warning_count": warning_count,
        "issues": [
            {
                "severity": issue.severity,
                "code": issue.code,
                "message": issue.message,
                "count": issue.count,
                "sample": issue.sample or [],
            }
            for issue in issues
        ],
    }


def data_gaps_csv(gaps: list[dict[str, Any]]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=GAP_COLUMNS)
    writer.writeheader()
    writer.writerows(gaps)
    return buffer.getvalue()


def render_local_form(markdown_report: str | None = None, download_url: str | None = None) -> str:
    report_html = ""
    if markdown_report is not None:
        download_html = ""
        if download_url is not None:
            download_html = f"""
          <p><a class="download" href="{escape(download_url, quote=True)}">下载 Markdown 报告</a></p>
            """
        report_html = f"""
        <section class="report">
          <h2>报告草稿</h2>
          {download_html}
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
    .download {{
      display: inline-block;
      margin: 0 0 12px;
      color: #1d4ed8;
      font-weight: 700;
      text-decoration: none;
    }}
    .download:hover {{
      text-decoration: underline;
    }}
    .report {{
      margin-top: 24px;
      padding: 20px;
      background: #fff;
      border: 1px solid #dfe4ea;
      border-radius: 8px;
    }}
    .links {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin: 0 0 20px;
    }}
    .links a {{
      color: #1d4ed8;
      font-weight: 700;
      text-decoration: none;
    }}
    .links a:hover {{
      text-decoration: underline;
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
    <nav class="links">
      <a href="/web/data-quality">查看数据质量</a>
      <a href="/data-quality">数据质量 JSON</a>
    </nav>
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
      <label class="full">其他可接受招生类型（用逗号分隔）
        <input name="accepted_admission_types" value="">
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


def render_data_quality_page(payload: dict[str, Any], gaps: list[dict[str, Any]]) -> str:
    status_text = "通过" if payload["ok"] else "需处理"
    table_rows = "\n".join(
        f"<tr><td>{escape(table)}</td><td>{count}</td></tr>"
        for table, count in payload["table_counts"].items()
    )
    issue_rows = "\n".join(
        "<tr>"
        f"<td>{escape(issue['severity'])}</td>"
        f"<td>{escape(issue['code'])}</td>"
        f"<td>{issue['count']}</td>"
        f"<td>{escape(issue['message'])}</td>"
        "</tr>"
        for issue in payload["issues"]
    ) or "<tr><td colspan=\"4\">暂无质量问题。</td></tr>"
    gap_rows = "\n".join(
        "<tr>"
        f"<td>{escape(gap['priority'])}</td>"
        f"<td>{escape(gap['target_table'])}</td>"
        f"<td>{escape(gap['school_name'])}</td>"
        f"<td>{escape(gap['major_name'])}</td>"
        f"<td>{escape(gap['suggested_action'])}</td>"
        "</tr>"
        for gap in gaps[:20]
    ) or "<tr><td colspan=\"5\">当前没有补数缺口。</td></tr>"

    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>数据质量 - 重庆高考志愿填报 Agent</title>
  <style>
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: #172026;
      background: #f7f8fa;
    }}
    main {{
      max-width: 1080px;
      margin: 0 auto;
      padding: 32px 20px 48px;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 28px;
    }}
    h2 {{
      margin-top: 28px;
      font-size: 20px;
    }}
    .subtitle, .meta {{
      color: #5a6672;
    }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
      margin-top: 20px;
    }}
    .metric {{
      padding: 16px;
      background: #fff;
      border: 1px solid #dfe4ea;
      border-radius: 8px;
    }}
    .metric strong {{
      display: block;
      margin-top: 6px;
      font-size: 24px;
    }}
    .links {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin-top: 20px;
    }}
    .links a {{
      color: #1d4ed8;
      font-weight: 700;
      text-decoration: none;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      background: #fff;
      border: 1px solid #dfe4ea;
      border-radius: 8px;
      overflow: hidden;
    }}
    th, td {{
      padding: 10px 12px;
      border-bottom: 1px solid #edf0f3;
      text-align: left;
      vertical-align: top;
      font-size: 14px;
    }}
    th {{
      background: #f0f3f7;
    }}
    @media (max-width: 760px) {{
      .summary {{
        grid-template-columns: 1fr 1fr;
      }}
    }}
  </style>
</head>
<body>
  <main>
    <h1>数据质量</h1>
    <p class="subtitle">本页面读取本地 SQLite 数据库，展示当前质量门禁和待补数据缺口。</p>
    <p class="meta">数据库：{escape(payload['database'])}</p>
    <div class="summary">
      <div class="metric">状态<strong>{status_text}</strong></div>
      <div class="metric">ERROR<strong>{payload['error_count']}</strong></div>
      <div class="metric">WARN<strong>{payload['warning_count']}</strong></div>
      <div class="metric">补数缺口<strong>{len(gaps)}</strong></div>
    </div>
    <nav class="links">
      <a href="/">返回推荐页</a>
      <a href="/data-quality">JSON</a>
      <a href="/web/data-gaps.csv">下载 CSV</a>
      <a href="/web/data-gaps.md">下载 Markdown</a>
    </nav>
    <h2>表记录数</h2>
    <table><thead><tr><th>表</th><th>记录数</th></tr></thead><tbody>{table_rows}</tbody></table>
    <h2>质量问题</h2>
    <table><thead><tr><th>级别</th><th>代码</th><th>数量</th><th>说明</th></tr></thead><tbody>{issue_rows}</tbody></table>
    <h2>补数清单预览</h2>
    <table><thead><tr><th>优先级</th><th>目标表</th><th>学校</th><th>专业</th><th>建议动作</th></tr></thead><tbody>{gap_rows}</tbody></table>
  </main>
</body>
</html>"""


@app.get("/web/data-quality", response_class=HTMLResponse)
def local_data_quality() -> HTMLResponse:
    payload = build_data_quality_payload()
    gaps = collect_data_gaps(DEFAULT_DB_PATH)
    return HTMLResponse(render_data_quality_page(payload, gaps))


@app.get("/web/data-gaps.csv")
def local_data_gaps_csv() -> Response:
    ensure_db_exists()
    gaps = collect_data_gaps(DEFAULT_DB_PATH)
    return Response(
        content="\ufeff" + data_gaps_csv(gaps),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="data_gaps.csv"'},
    )


@app.get("/web/data-gaps.md")
def local_data_gaps_markdown() -> Response:
    ensure_db_exists()
    gaps = collect_data_gaps(DEFAULT_DB_PATH)
    return Response(
        content=render_gap_markdown(gaps),
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="data_gaps.md"'},
    )


def build_payload_from_web_query(
    score: int = Query(..., ge=0, le=750),
    rank: int | None = Query(None, gt=0),
    subject_type: str = Query(..., pattern="^(物理|历史)$"),
    second_subjects: str = Query(...),
    major_interest: str = Query(""),
    risk_level: str = Query("均衡", pattern="^(保守|均衡|激进)$"),
    accept_sino_foreign: bool = Query(False),
    accepted_admission_types: str = Query(""),
) -> RecommendRequest:
    return RecommendRequest(
        score=score,
        rank=rank,
        subject_type=subject_type,
        second_subjects=[part.strip() for part in second_subjects.replace("，", ",").split(",") if part.strip()],
        major_interest=major_interest,
        risk_level=risk_level,
        accept_sino_foreign=accept_sino_foreign,
        accepted_admission_types=[
            part.strip()
            for part in accepted_admission_types.replace("，", ",").split(",")
            if part.strip()
        ],
    )


def web_report_download_url(payload: RecommendRequest) -> str:
    query = urlencode(
        {
            "score": payload.score,
            "rank": payload.rank if payload.rank is not None else "",
            "subject_type": payload.subject_type,
            "second_subjects": ",".join(payload.second_subjects),
            "major_interest": payload.major_interest,
            "risk_level": payload.risk_level,
            "accept_sino_foreign": str(payload.accept_sino_foreign).lower(),
            "accepted_admission_types": ",".join(payload.accepted_admission_types),
        }
    )
    return f"/web/report.md?{query}"


def generate_report_bundle(payload: RecommendRequest) -> dict[str, Any]:
    ensure_db_exists()
    with connect(DEFAULT_DB_PATH) as conn:
        recommendation = recommend(conn, build_profile(payload))
    official_checks = build_official_checks(recommendation)
    return {
        "recommendation": recommendation,
        "official_checks": official_checks,
        "markdown_report": render_report(recommendation, official_checks),
    }


def generate_markdown_report(payload: RecommendRequest) -> str:
    return generate_report_bundle(payload)["markdown_report"]


@app.get("/web/report", response_class=HTMLResponse)
def local_report(payload: RecommendRequest = Depends(build_payload_from_web_query)) -> HTMLResponse:
    markdown_report = generate_markdown_report(payload)
    return HTMLResponse(render_local_form(markdown_report, web_report_download_url(payload)))


@app.get("/web/report.md")
def local_report_markdown(payload: RecommendRequest = Depends(build_payload_from_web_query)) -> Response:
    markdown_report = generate_markdown_report(payload)
    return Response(
        content=markdown_report,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="gaokao_report.md"'},
    )


@app.post("/recommend", response_model=RecommendResponse)
def recommend_endpoint(payload: RecommendRequest) -> dict[str, Any]:
    ensure_db_exists()
    with connect(DEFAULT_DB_PATH) as conn:
        return recommend(conn, build_profile(payload))


@app.post("/report", response_model=ReportResponse)
def report_endpoint(payload: RecommendRequest) -> dict[str, Any]:
    return generate_report_bundle(payload)


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
    accepted_admission_types: str = Query(""),
    limit: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    ensure_db_exists()
    keyword = f"%{major_keyword.strip()}%" if major_keyword.strip() else "%"
    params: list[Any] = [subject_type, keyword, keyword, keyword]
    rank_filter = ""
    rank_params: list[Any] = []
    if rank is not None:
        rank_filter = "AND min_rank BETWEEN ? AND ?"
        rank_params.extend([int(rank * 0.7), int(rank * 1.6)])

    accepted_types = {
        part.strip()
        for part in accepted_admission_types.replace("，", ",").split(",")
        if part.strip()
    }
    if accept_sino_foreign:
        accepted_types.add("中外合作")
    allowed_types = {"普通类"} | accepted_types
    type_placeholders = ", ".join("?" for _ in allowed_types)
    params.extend(sorted(allowed_types))
    params.extend(rank_params)

    params.append(limit)
    sql = f"""
        SELECT year, school_name, major_name, major_group_code, admission_type,
               min_score, min_rank, plan_count, risk_notes, source_url, confidence
        FROM admission_history
        WHERE year = 2025
          AND subject_type = ?
          AND batch = '本科批'
          AND (major_name LIKE ? OR major_category LIKE ? OR discipline_category LIKE ?)
          AND admission_type IN ({type_placeholders})
          {rank_filter}
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
