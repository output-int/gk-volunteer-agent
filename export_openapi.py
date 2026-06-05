#!/usr/bin/env python3
"""Export the FastAPI OpenAPI schema for Coze/plugin-style imports."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from api_server import app


ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT = ROOT / "openapi" / "openapi.json"
REQUIRED_PATHS = {
    "/health",
    "/recommend",
    "/report",
    "/admissions/trend",
    "/subject-requirements",
    "/search/admissions",
}


def export_schema(output: Path = DEFAULT_OUTPUT) -> dict:
    schema = app.openapi()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return schema


def validate_schema(schema: dict) -> None:
    paths = set(schema.get("paths", {}).keys())
    missing = sorted(REQUIRED_PATHS - paths)
    if missing:
        raise ValueError(f"OpenAPI schema is missing required paths: {missing}")
    if schema.get("info", {}).get("title") != "Gaokao Volunteer Agent Data API":
        raise ValueError("OpenAPI title does not match FastAPI app title")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Export API OpenAPI schema.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true", help="Validate the exported schema after writing it.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    schema = export_schema(output)
    if args.check:
        validate_schema(schema)
    print(f"Exported OpenAPI schema to {output}")


if __name__ == "__main__":
    main()
