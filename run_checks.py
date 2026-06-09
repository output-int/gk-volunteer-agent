#!/usr/bin/env python3
"""Run the project's smoke checks in the same order used by CI."""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def run(command: list[str]) -> None:
    print(f"\n$ {' '.join(command)}")
    subprocess.run(command, cwd=ROOT, check=True)


def verify_static_files() -> None:
    print("\n$ verify JSON/CSV/text fixtures")
    for path in sorted(ROOT.glob("examples/*.json")) + sorted(ROOT.glob("data/**/*.json")):
        text = path.read_text(encoding="utf-8-sig")
        if "\ufffd" in text:
            raise ValueError(f"Replacement character found in {path}")
        json.loads(text)
        print(f"JSON OK: {path.relative_to(ROOT)}")

    for path in sorted(ROOT.glob("data/**/*.csv")):
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
        print(f"CSV OK: {path.relative_to(ROOT)} rows={len(rows)}")

    for path in [
        ROOT / "README.md",
        ROOT / "docs" / "data_import.md",
        ROOT / "docs" / "report_template.md",
        ROOT / "examples" / "recommend_report.md",
    ]:
        text = path.read_text(encoding="utf-8-sig")
        if "\ufffd" in text:
            raise ValueError(f"Replacement character found in {path}")
        print(f"TEXT OK: {path.relative_to(ROOT)} chars={len(text)}")


def main() -> None:
    python = sys.executable
    run([python, "init_db.py"])
    run([python, "validate_data.py"])
    run([python, "verify_importer.py"])
    run([python, "verify_recommender.py"])
    run([python, "verify_api.py"])
    run([python, "verify_local_agent.py"])
    run([python, "evaluate_cases.py"])
    run(
        [
            python,
            "report_renderer.py",
            "--recommendation-json",
            "examples/recommend_response.json",
            "--official-checks-json",
            "examples/official_checks_sample.json",
            "--output",
            "examples/recommend_report.md",
        ]
    )
    verify_static_files()
    print("\nAll checks passed.")


if __name__ == "__main__":
    main()
