#!/usr/bin/env python3
"""Local terminal Agent for generating Gaokao volunteer reports.

Run without arguments for an interactive interview, or pass arguments for
scriptable local use.
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from gaokao_recommender import DEFAULT_DB_PATH, StudentProfile, connect, parse_subjects, recommend
from report_renderer import render_report


ROOT = Path(__file__).resolve().parent
SAFE_NAME_RE = re.compile(r"[^0-9A-Za-z\u4e00-\u9fff._-]+")


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
    accepted_admission_types = parse_subjects(ask("其他接受的特殊招生类型（可空，逗号分隔）", ""))
    return StudentProfile(
        score=score or 0,
        rank=rank,
        subject_type=subject_type,
        second_subjects=second_subjects,
        major_interest=major_interest,
        risk_level=risk_level,
        accept_sino_foreign=accept_sino_foreign,
        accepted_admission_types=accepted_admission_types,
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
    parser.add_argument(
        "--accepted-admission-types",
        default="",
        help="Comma-separated special admission types to allow, e.g. 民族班,预科,专项.",
    )
    parser.add_argument("--json", action="store_true", help="Print recommendation JSON instead of Markdown.")
    parser.add_argument("--output", type=Path, help="Write output to a file instead of stdout.")
    parser.add_argument(
        "--save-run",
        type=Path,
        help=(
            "Save a reproducible run snapshot under this directory. "
            "Each run includes input_profile.json, recommendation.json, report.md, and metadata.json."
        ),
    )
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
        accepted_admission_types=parse_subjects(args.accepted_admission_types),
    )


def write_output(content: str, output: Path | None) -> None:
    if output is None:
        print(content)
        return
    path = output if output.is_absolute() else ROOT / output
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    print(f"Wrote {path}")


def resolve_output_path(path: Path) -> Path:
    return path if path.is_absolute() else ROOT / path


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def safe_name(value: Any, fallback: str = "run") -> str:
    cleaned = SAFE_NAME_RE.sub("-", str(value or fallback)).strip(".-_")
    return cleaned or fallback


def save_run_snapshot(
    snapshot_root: Path,
    *,
    db_path: Path,
    args: argparse.Namespace,
    recommendation: dict[str, Any],
    markdown_report: str,
) -> Path:
    resolved_root = resolve_output_path(snapshot_root)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    profile = recommendation.get("student_profile", {})
    subject_type = safe_name(profile.get("subject_type"), "unknown")
    major_interest = safe_name(profile.get("major_interest"), "all")
    run_dir = resolved_root / f"{timestamp}-{subject_type}-{major_interest}"
    suffix = 1
    while run_dir.exists():
        suffix += 1
        run_dir = resolved_root / f"{timestamp}-{subject_type}-{major_interest}-{suffix}"
    run_dir.mkdir(parents=True, exist_ok=True)

    write_json(run_dir / "input_profile.json", profile)
    write_json(run_dir / "recommendation.json", recommendation)
    (run_dir / "report.md").write_text(markdown_report, encoding="utf-8")
    write_json(
        run_dir / "metadata.json",
        {
            "created_at": datetime.now().isoformat(timespec="seconds"),
            "db_path": str(db_path),
            "mode": "json" if args.json else "markdown",
            "output_path": str(resolve_output_path(args.output)) if args.output else None,
            "mock_data_notice": "当前数据仅用于开发测试，不代表真实录取结果。",
        },
    )
    return run_dir


def main() -> None:
    args = parse_args()
    db_path = args.db if args.db.is_absolute() else ROOT / args.db
    profile = profile_from_args(args) or interactive_profile()
    with connect(db_path) as conn:
        recommendation = recommend(conn, profile)
    markdown_report = render_report(recommendation)
    if args.save_run:
        snapshot_dir = save_run_snapshot(
            args.save_run,
            db_path=db_path,
            args=args,
            recommendation=recommendation,
            markdown_report=markdown_report,
        )
        print(f"Saved run snapshot: {snapshot_dir}")
    if args.json:
        output = json.dumps(recommendation, ensure_ascii=False, indent=2) + "\n"
    else:
        output = markdown_report
    write_output(output, args.output)


if __name__ == "__main__":
    main()
