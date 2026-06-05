#!/usr/bin/env python3
"""Smoke test for local_agent.py non-interactive mode."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        report_path = Path(temp_dir) / "agent_report.md"
        result = subprocess.run(
            [
                sys.executable,
                "local_agent.py",
                "--score",
                "596",
                "--rank",
                "20000",
                "--subject-type",
                "物理",
                "--second-subjects",
                "化学,生物",
                "--major-interest",
                "计算机,电子信息",
                "--output",
                str(report_path),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        assert_true(report_path.exists(), f"Report was not written: {result.stdout} {result.stderr}")
        report = report_path.read_text(encoding="utf-8")
        assert_true("重庆高考志愿填报辅助报告" in report, "Report title missing.")
        assert_true("重庆邮电大学" in report, "Expected candidate missing.")
        assert_true("电子信息类" in report, "Multi-keyword candidate missing.")

    print("All local Agent smoke tests passed.")


if __name__ == "__main__":
    main()
