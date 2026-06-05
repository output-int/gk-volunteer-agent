#!/usr/bin/env python3
"""Local terminal Agent for generating Gaokao volunteer reports.

Run without arguments for an interactive interview, or pass arguments for
scriptable local use.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from gaokao_recommender import DEFAULT_DB_PATH, StudentProfile, connect, parse_subjects, recommend
from report_renderer import render_report


ROOT = Path(__file__).resolve().parent


def ask(prompt: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default is not None else ""
    value = input(f"{prompt}{suffix}: ").strip()
    if value:
        return value
    if default is not None:
        return default
    return ask(prompt, default)


def ask_int(prompt: str, default: int | None = None, *, required: bool = True) -> int | None:
    default_text = str(default) if default is not None else None
    raw = ask(prompt, default_text) if required or default is not None else input(f"{prompt}（可空）: ").strip()
    if not raw and not required:
        return None
    try:
        return int(raw)
    except ValueError:
        print("请输入数字。")
        return ask_int(prompt, default, required=required)


def ask_choice(prompt: str, choices: set[str], default: str) -> str:
    value = ask(prompt, default)
    if value in choices:
        return value
    print(f"可选值：{' / '.join(sorted(choices))}")
    return ask_choice(prompt, choices, default)


def ask_bool(prompt: str, default: bool = False) -> bool:
    default_text = "y" if default else "n"
    value = ask(prompt, default_text).lower()
    return value in {"y", "yes", "true", "1", "是", "接受"}


def interactive_profile() -> StudentProfile:
    print("重庆高考志愿填报 Agent 本地终端版")
    print("当前使用 Mock 数据，仅用于开发测试。\n")
    score = ask_int("高考分数", 596)
    rank = ask_int("重庆同科类位次", 20000, required=False)
    subject_type = ask_choice("首选科目（物理/历史）", {"物理", "历史"}, "物理")
    second_subjects = parse_subjects(ask("再选科目（逗号分隔）", "化学,生物"))
    major_interest = ask("专业兴趣（可多个，逗号分隔）", "计算机,电子信息")
    risk_level = ask_choice("风险偏好（保守/均衡/激进）", {"保守", "均衡", "激进"}, "均衡")
    accept_sino_foreign = ask_bool("是否接受中外合作/高学费项目？y/n", False)
    return StudentProfile(
        score=score or 0,
        rank=rank,
        subject_type=subject_type,
        second_subjects=second_subjects,
        major_interest=major_interest,
        risk_level=risk_level,
        accept_sino_foreign=accept_sino_foreign,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the local Gaokao volunteer Agent.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--score", type=int)
    parser.add_argument("--rank", type=int)
    parser.add_argument("--subject-type", choices=["物理", "历史"])
    parser.add_argument("--second-subjects")
    parser.add_argument("--major-interest", default="")
    parser.add_argument("--risk-level", choices=["保守", "均衡", "激进"], default="均衡")
    parser.add_argument("--accept-sino-foreign", action="store_true")
    parser.add_argument("--json", action="store_true", help="Print recommendation JSON instead of Markdown.")
    parser.add_argument("--output", type=Path, help="Write output to a file instead of stdout.")
    return parser.parse_args()


def profile_from_args(args: argparse.Namespace) -> StudentProfile | None:
    provided = [args.score, args.subject_type, args.second_subjects]
    if not any(value is not None for value in provided):
        return None
    missing = [
        name
        for name, value in (
            ("--score", args.score),
            ("--subject-type", args.subject_type),
            ("--second-subjects", args.second_subjects),
        )
        if value is None
    ]
    if missing:
        raise SystemExit(f"非交互模式缺少必要参数：{', '.join(missing)}")
    return StudentProfile(
        score=args.score,
        rank=args.rank,
        subject_type=args.subject_type,
        second_subjects=parse_subjects(args.second_subjects),
        major_interest=args.major_interest,
        risk_level=args.risk_level,
        accept_sino_foreign=args.accept_sino_foreign,
    )


def write_output(content: str, output: Path | None) -> None:
    if output is None:
        print(content)
        return
    path = output if output.is_absolute() else ROOT / output
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"Wrote {path}")


def main() -> None:
    args = parse_args()
    db_path = args.db if args.db.is_absolute() else ROOT / args.db
    profile = profile_from_args(args) or interactive_profile()
    with connect(db_path) as conn:
        recommendation = recommend(conn, profile)
    if args.json:
        output = json.dumps(recommendation, ensure_ascii=False, indent=2) + "\n"
    else:
        output = render_report(recommendation)
    write_output(output, args.output)


if __name__ == "__main__":
    main()
