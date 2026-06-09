#!/usr/bin/env python3
"""Deterministic recommendation/query layer for the Gaokao Agent mock DB.

The module intentionally keeps hard facts outside the LLM:
- admission history comes from SQLite
- subject eligibility is checked before ranking
- Sino-foreign and special admission types are filtered by explicit user choice
- output is JSON so Coze, a code node, or a thin API wrapper can consume it
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from statistics import mean, pstdev
from typing import Any


ROOT = Path(__file__).resolve().parent
DEFAULT_DB_PATH = ROOT / "gaokao_agent.db"
REQUIREMENT_YEAR = 2026


@dataclass(frozen=True)
class StudentProfile:
    score: int
    rank: int | None
    subject_type: str
    second_subjects: set[str]
    major_interest: str
    risk_level: str
    accept_sino_foreign: bool
    accepted_admission_types: set[str] = field(default_factory=set)
    batch: str = "本科批"
    province: str = "重庆"


def connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def parse_subjects(raw: str) -> set[str]:
    separators = [",", "，", "、", "/", " "]
    normalized = raw
    for separator in separators:
        normalized = normalized.replace(separator, ",")
    return {part.strip() for part in normalized.split(",") if part.strip()}


def parse_keywords(raw: str) -> list[str]:
    separators = [",", "，", "、", "/", " "]
    normalized = raw
    for separator in separators:
        normalized = normalized.replace(separator, ",")
    seen: set[str] = set()
    keywords: list[str] = []
    for part in normalized.split(","):
        keyword = part.strip()
        if keyword and keyword not in seen:
            seen.add(keyword)
            keywords.append(keyword)
    return keywords


def expand_keywords(keywords: list[str]) -> list[str]:
    expansions = {
        "计算机": ["计算机", "软件工程", "人工智能", "数据科学"],
        "电子信息": ["电子信息", "通信工程", "信息工程"],
        "临床医学": ["临床医学", "医学"],
        "汉语言文学": ["汉语言文学", "中国语言文学"],
        "思想政治教育": ["思想政治教育", "马克思主义理论"],
        "软件工程": ["软件工程", "计算机"],
    }
    expanded: list[str] = []
    seen: set[str] = set()
    for keyword in keywords:
        candidates = [keyword]
        for trigger, values in expansions.items():
            if trigger in keyword:
                candidates.extend(values)
        for candidate in candidates:
            if candidate and candidate not in seen:
                seen.add(candidate)
                expanded.append(candidate)
    return expanded


def row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def fetch_requirement(
    conn: sqlite3.Connection, school_name: str, major_name: str
) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT *
        FROM subject_requirement
        WHERE school_name = ?
          AND major_name = ?
          AND requirement_year = ?
        ORDER BY effective_from DESC
        LIMIT 1
        """,
        (school_name, major_name, REQUIREMENT_YEAR),
    ).fetchone()


def requirement_status(
    profile: StudentProfile, requirement: sqlite3.Row | None
) -> tuple[bool, str]:
    if requirement is None:
        return True, "未找到 2026 选科要求 Mock 记录，需人工核验。"

    first_required = requirement["first_subject_required"]
    if first_required != "物理或历史均可" and first_required != profile.subject_type:
        return False, f"首选科目不符：要求 {first_required}，考生为 {profile.subject_type}。"

    second_required = requirement["second_subjects_required"]
    if second_required == "不限":
        return True, requirement["requirement_text"]

    required_subjects = parse_subjects(second_required)
    missing_subjects = sorted(required_subjects - profile.second_subjects)
    if missing_subjects:
        return False, f"再选科目不符：缺少 {'、'.join(missing_subjects)}。{requirement['requirement_text']}"

    return True, requirement["requirement_text"]


def admission_type_allowed(profile: StudentProfile, admission_type: str) -> tuple[bool, str]:
    if admission_type == "普通类":
        return True, "招生类型符合当前偏好。"
    if admission_type == "中外合作" and (profile.accept_sino_foreign or admission_type in profile.accepted_admission_types):
        return True, "用户已接受中外合作/高学费项目。"
    if admission_type in profile.accepted_admission_types:
        return True, f"用户已显式接受 {admission_type}，仍需核验资格。"
    if admission_type == "中外合作":
        return False, "用户未接受中外合作/高学费项目。"
    if admission_type in {"民族班", "预科", "专项"}:
        return False, f"{admission_type} 有资格限制，未显式接受时默认过滤。"
    return False, f"未知招生类型 {admission_type}，默认过滤。"


def tier_from_rank_gap(rank: int, comparison_rank: int, risk_level: str) -> tuple[str | None, int]:
    gap = comparison_rank - rank
    # Positive gap means the student's rank is better than the historical minimum rank.
    if risk_level == "保守":
        challenge_floor = -0.10
        stable_ceiling = 0.25
        safe_floor = 0.25
    elif risk_level == "激进":
        challenge_floor = -0.35
        stable_ceiling = 0.45
        safe_floor = 0.45
    else:
        challenge_floor = -0.25
        stable_ceiling = 0.35
        safe_floor = 0.35

    relative_gap = gap / rank
    if challenge_floor <= relative_gap < 0:
        return "冲", gap
    if 0 <= relative_gap <= stable_ceiling:
        return "稳", gap
    if relative_gap > safe_floor:
        return "保", gap
    return None, gap


def volatility_level(volatility: float) -> str:
    if volatility >= 5000:
        return "high"
    if volatility >= 2000:
        return "medium"
    return "low"


def build_risk_flags(
    *,
    tier: str,
    rank_gap: int | None,
    rank: int | None,
    volatility: float,
    admission_type: str,
    confidence: str,
) -> list[str]:
    flags: list[str] = []
    level = volatility_level(volatility)
    if level == "high":
        flags.append("近年等效位次波动高")
    elif level == "medium":
        flags.append("近年等效位次波动中等")

    if tier == "冲":
        flags.append("冲刺档存在滑档风险")
    if tier == "保" and level != "low":
        flags.append("波动非低，不宜作为唯一保底")
    if rank_gap is not None and rank is not None and rank > 0:
        ratio = rank_gap / rank
        if -0.1 < ratio < 0:
            flags.append("与历史等效位次差距很小")
        if 0 <= ratio < 0.08:
            flags.append("稳妥余量较窄")
    if admission_type != "普通类":
        flags.append("特殊招生类型需核验资格")
    if confidence != "high":
        flags.append("数据置信度需复核")
    return flags


def fetch_reference_year(conn: sqlite3.Connection, profile: StudentProfile) -> int | None:
    row = conn.execute(
        """
        SELECT MAX(year) AS reference_year
        FROM score_rank_table
        WHERE province = ?
          AND subject_type = ?
        """,
        (profile.province, profile.subject_type),
    ).fetchone()
    return int(row["reference_year"]) if row and row["reference_year"] is not None else None


def fetch_above_batch_line_count(
    conn: sqlite3.Connection, year: int, province: str, subject_type: str
) -> int | None:
    row = conn.execute(
        """
        SELECT MAX(above_batch_line_count) AS above_count
        FROM score_rank_table
        WHERE year = ?
          AND province = ?
          AND subject_type = ?
        """,
        (year, province, subject_type),
    ).fetchone()
    return int(row["above_count"]) if row and row["above_count"] is not None else None


def equivalent_rank(
    raw_rank: int,
    source_above_count: int | None,
    target_above_count: int | None,
) -> int:
    if not source_above_count or not target_above_count:
        return raw_rank
    return max(1, round(raw_rank / source_above_count * target_above_count))


def fetch_history_rows(conn: sqlite3.Connection, profile: StudentProfile) -> list[sqlite3.Row]:
    keywords = expand_keywords(parse_keywords(profile.major_interest))
    keyword_sql = "1 = 1"
    keyword_params: list[str] = []
    if keywords:
        keyword_clauses = []
        for keyword in keywords:
            keyword_clauses.append(
                "(major_name LIKE ? OR major_category LIKE ? OR discipline_category LIKE ?)"
            )
            like_keyword = f"%{keyword}%"
            keyword_params.extend([like_keyword, like_keyword, like_keyword])
        keyword_sql = "(" + " OR ".join(keyword_clauses) + ")"

    return conn.execute(
        f"""
        SELECT *
        FROM admission_history
        WHERE province = ?
          AND subject_type = ?
          AND batch = ?
          AND year IN (2024, 2025)
          AND {keyword_sql}
        ORDER BY school_name, major_name, year
        """,
        [
            profile.province,
            profile.subject_type,
            profile.batch,
            *keyword_params,
        ],
    ).fetchall()


def summarize_group(
    conn: sqlite3.Connection,
    profile: StudentProfile,
    rows: list[sqlite3.Row],
    reference_year: int | None,
    reference_above_count: int | None,
) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    latest = max(rows, key=lambda row: row["year"])
    excluded: list[dict[str, Any]] = []

    allowed, reason = admission_type_allowed(profile, latest["admission_type"])
    if not allowed:
        excluded.append(
            {
                "school_name": latest["school_name"],
                "major_name": latest["major_name"],
                "reason": reason,
            }
        )
        return None, excluded

    requirement = fetch_requirement(conn, latest["school_name"], latest["major_name"])
    subject_ok, subject_note = requirement_status(profile, requirement)
    if not subject_ok:
        excluded.append(
            {
                "school_name": latest["school_name"],
                "major_name": latest["major_name"],
                "reason": subject_note,
            }
        )
        return None, excluded

    equivalent_rows = []
    for row in sorted(rows, key=lambda history_row: history_row["year"]):
        source_above_count = fetch_above_batch_line_count(
            conn,
            int(row["year"]),
            row["province"],
            row["subject_type"],
        )
        equivalent_rows.append(
            {
                "row": row,
                "source_above_batch_line_count": source_above_count,
                "equivalent_min_rank": equivalent_rank(
                    int(row["min_rank"]),
                    source_above_count,
                    reference_above_count,
                ),
            }
        )

    latest_equivalent = next(item for item in equivalent_rows if item["row"]["id"] == latest["id"])

    if profile.rank is None:
        tier = "待定位"
        rank_gap = None
        rank_gap_ratio = None
        comparison_rank = latest_equivalent["equivalent_min_rank"]
    else:
        comparison_rank = latest_equivalent["equivalent_min_rank"]
        tier, rank_gap = tier_from_rank_gap(profile.rank, comparison_rank, profile.risk_level)
        if tier is None:
            return None, []
        rank_gap_ratio = round(rank_gap / profile.rank, 4) if profile.rank > 0 else None

    ranks = [int(row["min_rank"]) for row in rows]
    equivalent_ranks = [int(item["equivalent_min_rank"]) for item in equivalent_rows]
    scores = [int(row["min_score"]) for row in rows]
    volatility = round(pstdev(equivalent_ranks), 2) if len(equivalent_ranks) > 1 else 0.0
    volatility_label = volatility_level(volatility)
    trend = "趋难" if len(equivalent_ranks) > 1 and equivalent_ranks[-1] < equivalent_ranks[0] else "趋稳或趋易"
    volatility_note = ""
    if len(ranks) > 1 and volatility > 2500:
        volatility_note = "近年最低位次波动较大，不宜作为保底志愿。"

    profile_row = conn.execute(
        """
        SELECT employment_direction, postgraduate_direction, risk_notes
        FROM school_major_profile
        WHERE school_name = ?
          AND major_name = ?
        LIMIT 1
        """,
        (latest["school_name"], latest["major_name"]),
    ).fetchone()

    item = {
        "tier": tier,
        "school_name": latest["school_name"],
        "major_name": latest["major_name"],
        "major_group_code": latest["major_group_code"],
        "admission_type": latest["admission_type"],
        "latest_year": latest["year"],
        "latest_min_score": latest["min_score"],
        "latest_min_rank": latest["min_rank"],
        "rank_method": "equivalent_rank" if reference_year and reference_above_count else "raw_rank",
        "reference_year": reference_year,
        "reference_above_batch_line_count": reference_above_count,
        "latest_equivalent_min_rank": comparison_rank,
        "rank_gap": rank_gap,
        "rank_gap_ratio": rank_gap_ratio,
        "avg_min_rank": round(mean(ranks), 2),
        "avg_equivalent_min_rank": round(mean(equivalent_ranks), 2),
        "avg_min_score": round(mean(scores), 2),
        "volatility_score": volatility,
        "volatility_level": volatility_label,
        "trend": trend,
        "subject_requirement_note": subject_note,
        "risk_flags": build_risk_flags(
            tier=tier,
            rank_gap=rank_gap,
            rank=profile.rank,
            volatility=volatility,
            admission_type=latest["admission_type"],
            confidence=latest["confidence"],
        ),
        "risk_notes": "；".join(
            note
            for note in [latest["risk_notes"], volatility_note, profile_row["risk_notes"] if profile_row else ""]
            if note
        ),
        "employment_direction": profile_row["employment_direction"] if profile_row else None,
        "source_url": latest["source_url"],
        "confidence": latest["confidence"],
        "history": [
            {
                "year": item["row"]["year"],
                "min_score": item["row"]["min_score"],
                "min_rank": item["row"]["min_rank"],
                "source_above_batch_line_count": item["source_above_batch_line_count"],
                "equivalent_min_rank": item["equivalent_min_rank"],
                "source_type": item["row"]["source_type"],
            }
            for item in equivalent_rows
        ],
    }
    return item, excluded


def recommend(conn: sqlite3.Connection, profile: StudentProfile) -> dict[str, Any]:
    history_rows = fetch_history_rows(conn, profile)
    reference_year = fetch_reference_year(conn, profile)
    reference_above_count = (
        fetch_above_batch_line_count(conn, reference_year, profile.province, profile.subject_type)
        if reference_year is not None
        else None
    )
    grouped: dict[tuple[str, str, str], list[sqlite3.Row]] = {}
    for row in history_rows:
        key = (row["school_name"], row["major_name"], row["admission_type"])
        grouped.setdefault(key, []).append(row)

    candidates: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for rows in grouped.values():
        item, excluded_items = summarize_group(
            conn,
            profile,
            rows,
            reference_year,
            reference_above_count,
        )
        excluded.extend(excluded_items)
        if item is not None:
            candidates.append(item)

    tier_order = {"冲": 0, "稳": 1, "保": 2, "待定位": 3}
    candidates.sort(
        key=lambda item: (
            tier_order.get(item["tier"], 9),
            abs(item["rank_gap"]) if item["rank_gap"] is not None else 0,
            item["latest_equivalent_min_rank"],
        )
    )

    warnings = [
        "Mock 数据仅用于开发测试，不代表真实录取数据。",
        "2026 正式填报前必须核验重庆市教育考试院、重庆招考信息网、阳光高考和高校招生章程。",
    ]
    if profile.rank is None:
        warnings.append("缺少位次，冲稳保只能降级为粗略候选，建议补充重庆同科类位次。")
    if reference_year is None or reference_above_count is None:
        warnings.append("缺少一分一段本科线上人数，当前推荐已退回原始位次比较。")
    else:
        warnings.append(f"冲稳保分档使用 {reference_year} 年同科类本科线上人数折算后的等效位次。")

    return {
        "student_profile": {
            "score": profile.score,
            "rank": profile.rank,
            "subject_type": profile.subject_type,
            "second_subjects": sorted(profile.second_subjects),
            "major_interest": profile.major_interest,
            "risk_level": profile.risk_level,
            "accept_sino_foreign": profile.accept_sino_foreign,
            "accepted_admission_types": sorted(profile.accepted_admission_types),
            "rank_reference_year": reference_year,
            "rank_reference_above_batch_line_count": reference_above_count,
        },
        "warnings": warnings,
        "candidates": candidates,
        "excluded": excluded,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Query mock Gaokao recommendations as JSON.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--score", type=int, required=True)
    parser.add_argument("--rank", type=int)
    parser.add_argument("--subject-type", choices=["物理", "历史"], required=True)
    parser.add_argument("--second-subjects", required=True, help="Comma-separated subjects, e.g. 化学,生物")
    parser.add_argument("--major-interest", default="", help="Major keyword, e.g. 计算机")
    parser.add_argument("--risk-level", choices=["保守", "均衡", "激进"], default="均衡")
    parser.add_argument("--accept-sino-foreign", action="store_true")
    parser.add_argument(
        "--accepted-admission-types",
        default="",
        help="Comma-separated special admission types to allow, e.g. 民族班,预科,专项.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    db_path = args.db if args.db.is_absolute() else ROOT / args.db
    profile = StudentProfile(
        score=args.score,
        rank=args.rank,
        subject_type=args.subject_type,
        second_subjects=parse_subjects(args.second_subjects),
        major_interest=args.major_interest,
        risk_level=args.risk_level,
        accept_sino_foreign=args.accept_sino_foreign,
        accepted_admission_types=parse_subjects(args.accepted_admission_types),
    )
    with connect(db_path) as conn:
        result = recommend(conn, profile)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
