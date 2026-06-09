#!/usr/bin/env python3
"""Smoke test for local_agent.py non-interactive mode."""

from __future__ import annotations

import json
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
        snapshot_root = Path(temp_dir) / "runs"
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
                "--save-run",
                str(snapshot_root),
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
        snapshot_dirs = list(snapshot_root.iterdir())
        assert_true(len(snapshot_dirs) == 1, f"Expected one snapshot directory, got {snapshot_dirs}")
        snapshot_dir = snapshot_dirs[0]
        assert_true((snapshot_dir / "input_profile.json").exists(), "Snapshot input_profile.json missing.")
        assert_true((snapshot_dir / "recommendation.json").exists(), "Snapshot recommendation.json missing.")
        assert_true((snapshot_dir / "report.md").exists(), "Snapshot report.md missing.")
        assert_true((snapshot_dir / "metadata.json").exists(), "Snapshot metadata.json missing.")
        profile = json.loads((snapshot_dir / "input_profile.json").read_text(encoding="utf-8"))
        recommendation = json.loads((snapshot_dir / "recommendation.json").read_text(encoding="utf-8"))
        metadata = json.loads((snapshot_dir / "metadata.json").read_text(encoding="utf-8"))
        assert_true(profile["rank"] == 20000, "Snapshot profile rank mismatch.")
        assert_true(recommendation["candidates"], "Snapshot recommendation candidates missing.")
        assert_true(metadata["mock_data_notice"], "Snapshot metadata notice missing.")
        assert_true("Saved run snapshot:" in result.stdout, "Snapshot path should be printed.")

        special_report_path = Path(temp_dir) / "agent_special_report.md"
        subprocess.run(
            [
                sys.executable,
                "local_agent.py",
                "--score",
                "598",
                "--rank",
                "25000",
                "--subject-type",
                "物理",
                "--second-subjects",
                "化学,生物",
                "--major-interest",
                "建筑",
                "--accepted-admission-types",
                "民族班",
                "--output",
                str(special_report_path),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        special_report = special_report_path.read_text(encoding="utf-8")
        assert_true("民族班" in special_report, "Accepted special admission type should appear in report.")

    print("All local Agent smoke tests passed.")


if __name__ == "__main__":
    main()
