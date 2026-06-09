#!/usr/bin/env python3
"""Render deterministic Markdown reports from recommendation JSON."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
DEFAULT_OFFICIAL_SOURCE_URLS = [
    "https://www.cqksy.cn/",
    "https://www.cqzk.com.cn/",
    "https://gaokao.chsi.com.cn/",
]


def text_or_dash(value: Any) -> str:
    if value is None or value == "":
        return "-"
    return str(value)


def group_candidates(candidates: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped = {"冲": [], "稳": [], "保": [], "待定位": []}
    for item in candidates:
        grouped.setdefault(item.get("tier", "待定位"), []).append(item)
    return grouped


def render_candidate(item: dict[str, Any], index: int) -> str:
    history = item.get("history", [])
    history_bits = []
    for row in history:
        history_bits.append(
            f"{row.get('year')} 年最低分 {row.get('min_score')}，"
            f"原始位次 {row.get('min_rank')}，等效位次 {row.get('equivalent_min_rank', '-')}"
        )
    history_text = "；".join(history_bits) if history_bits else "暂无历史明细"

    return "\n".join(
        [
            f"{index}. **{item.get('school_name')} - {item.get('major_name')}**",
            f"   - 档位：{item.get('tier')}",
            f"   - 招生类型：{item.get('admission_type')}",
            f"   - 最新年份：{item.get('latest_year')}，最低分：{item.get('latest_min_score')}，"
            f"原始最低位次：{item.get('latest_min_rank')}，等效最低位次：{item.get('latest_equivalent_min_rank')}",
            f"   - 位次差：{text_or_dash(item.get('rank_gap'))}，趋势：{text_or_dash(item.get('trend'))}，"
            f"波动等级：{text_or_dash(item.get('volatility_level'))}，波动值：{text_or_dash(item.get('volatility_score'))}",
            f"   - 选科说明：{text_or_dash(item.get('subject_requirement_note'))}",
            f"   - 就业方向：{text_or_dash(item.get('employment_direction'))}",
            f"   - 历史参考：{history_text}",
            f"   - 风险标签：{'、'.join(item.get('risk_flags', [])) or '-'}",
            f"   - 风险提示：{text_or_dash(item.get('risk_notes'))}",
            f"   - 来源：{text_or_dash(item.get('source_url'))}，置信度：{text_or_dash(item.get('confidence'))}",
        ]
    )


def build_official_checks(recommendation: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    checks: list[dict[str, Any]] = []
    for item in recommendation.get("candidates", []):
        findings = [
            "核验 2026 招生章程中的院校专业组、专业代码、计划数、校区和学费。",
            f"核验选科要求：{text_or_dash(item.get('subject_requirement_note'))}",
            "核验近年最低分/最低位次是否来自官方投档表，并确认专业组是否发生调整。",
        ]
        if item.get("admission_type") != "普通类":
            findings.append(f"核验 {item.get('admission_type')} 的报考资格、录取规则和退出/转专业限制。")
        if item.get("admission_type") == "中外合作":
            findings.append("重点核验中外合作办学学费、外方课程、培养模式和毕业证书说明。")
        if item.get("risk_flags"):
            findings.append(f"复核风险标签：{'、'.join(item.get('risk_flags', []))}")

        source_urls = list(DEFAULT_OFFICIAL_SOURCE_URLS)
        source_url = item.get("source_url")
        if source_url and source_url not in source_urls:
            source_urls.append(source_url)

        checks.append(
            {
                "school_name": item.get("school_name"),
                "major_name": item.get("major_name"),
                "admission_type": item.get("admission_type"),
                "status": "pending",
                "findings": findings,
                "source_urls": source_urls,
                "manual_check_required": True,
            }
        )
    return {"official_checks": checks}


def render_report(recommendation: dict[str, Any], official_checks: dict[str, Any] | None = None) -> str:
    profile = recommendation.get("student_profile", {})
    warnings = recommendation.get("warnings", [])
    candidates = recommendation.get("candidates", [])
    excluded = recommendation.get("excluded", [])
    official_checks = official_checks or build_official_checks(recommendation)
    checks = official_checks.get("official_checks", [])

    lines: list[str] = [
        "# 重庆高考志愿填报辅助报告",
        "",
        "## 考生画像",
        "",
        f"- 分数：{text_or_dash(profile.get('score'))}",
        f"- 位次：{text_or_dash(profile.get('rank'))}",
        f"- 科类：{text_or_dash(profile.get('subject_type'))}",
        f"- 再选科目：{'、'.join(profile.get('second_subjects', [])) or '-'}",
        f"- 专业兴趣：{text_or_dash(profile.get('major_interest'))}",
        f"- 风险偏好：{text_or_dash(profile.get('risk_level'))}",
        f"- 接受中外合作：{'是' if profile.get('accept_sino_foreign') else '否'}",
        f"- 其他接受招生类型：{'、'.join(profile.get('accepted_admission_types', [])) or '-'}",
        f"- 位次参考年份：{text_or_dash(profile.get('rank_reference_year'))}",
        "",
        "## 核心结论",
        "",
    ]

    if candidates:
        lines.append(
            "系统已根据结构化历史库、选科要求、招生类型偏好和等效位次规则生成候选清单。"
        )
    else:
        lines.append("当前输入和 Mock 数据范围下，未找到可进入推荐池的候选。")

    if excluded:
        lines.append("部分院校专业已被硬规则过滤，原因见“被过滤项目”。")
    lines.extend(["", "## 冲稳保候选", ""])

    grouped = group_candidates(candidates)
    for tier in ["冲", "稳", "保", "待定位"]:
        lines.append(f"### {tier}")
        tier_items = grouped.get(tier, [])
        if not tier_items:
            lines.extend(["", "当前数据下暂无合适候选。", ""])
            continue
        lines.append("")
        for index, item in enumerate(tier_items, start=1):
            lines.append(render_candidate(item, index))
            lines.append("")

    lines.extend(["## 被过滤项目", ""])
    if excluded:
        for index, item in enumerate(excluded, start=1):
            lines.append(
                f"{index}. **{item.get('school_name')} - {item.get('major_name')}**：{item.get('reason')}"
            )
    else:
        lines.append("暂无被过滤项目。")

    lines.extend(["", "## 官方核验清单", ""])
    if checks:
        for index, check in enumerate(checks, start=1):
            findings = "；".join(check.get("findings", [])) or "暂无核验发现"
            source_urls = "；".join(check.get("source_urls", [])) or "暂无官方链接"
            lines.append(
                f"{index}. **{check.get('school_name')} - {check.get('major_name')}**："
                f"状态 {check.get('status')}；{findings}；来源：{source_urls}"
            )
    else:
        lines.append("尚未完成官方实时核验。正式填报前必须核验 2026 招生章程、选科、校区、学费和体检限制。")

    lines.extend(
        [
            "",
            "## 下一步行动",
            "",
            "1. 补全或确认重庆同科类位次。",
            "2. 到重庆市教育考试院、重庆招考信息网、阳光高考和高校招生网核验最新章程。",
            "3. 对中外合作、民族班、预科、专项计划等特殊类型逐项确认资格和费用。",
            "4. 将候选清单放回官方志愿填报辅助系统中复核。",
            "",
            "## 风险声明",
            "",
        ]
    )
    for warning in warnings:
        lines.append(f"- {warning}")
    lines.append("- 本报告不承诺录取结果，不替代官方志愿填报系统。")

    return "\n".join(lines).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Render a Markdown report from recommendation JSON.")
    parser.add_argument("--recommendation-json", type=Path, required=True)
    parser.add_argument("--official-checks-json", type=Path)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    resolved = path if path.is_absolute() else ROOT / path
    return json.loads(resolved.read_text(encoding="utf-8-sig"))


def main() -> None:
    args = parse_args()
    recommendation = read_json(args.recommendation_json)
    official_checks = read_json(args.official_checks_json) if args.official_checks_json else None
    markdown = render_report(recommendation, official_checks)
    if args.output:
        output = args.output if args.output.is_absolute() else ROOT / args.output
        output.write_text(markdown, encoding="utf-8")
    else:
        print(markdown)


if __name__ == "__main__":
    main()
