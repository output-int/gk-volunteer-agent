#!/usr/bin/env python3
"""Download, extract, and import 2023 Chongqing public gaokao data."""

from __future__ import annotations

import argparse
import re
import sys
from io import StringIO
from pathlib import Path
from typing import Any

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import import_cq_2025_real_data as base

YEAR = 2023
RAW_DIR = ROOT / "data" / "raw" / "cq" / str(YEAR)
CLEAN_DIR = ROOT / "data" / "cleaned" / "cq" / str(YEAR)
DEFAULT_DB_PATH = ROOT / "gaokao_agent.db"
BATCH_LINES = {"物理": 406, "历史": 407}

DOWNLOADS = {
    "admission_physics": {
        "path": RAW_DIR / "2023_cq_benke_physics.pdf",
        "download_url": "https://cdn.zizzs.com/zixunzhan/202310/384e9fe4-c36a-4c08-8fde-a75f012112d0.pdf",
        "source_url": "https://www.cqksy.cn/site/infopub/2023/gk/lqxx/2023zsxxxb-bkp-wl_pxzy0725.pdf",
    },
    "admission_history": {
        "path": RAW_DIR / "2023_cq_benke_history.pdf",
        "download_url": "https://cdn.zizzs.com/zixunzhan/202310/87846af1-a47c-42a8-a3b3-6e743ce5d150.pdf",
        "source_url": "https://www.cqksy.cn/site/infopub/2023/gk/lqxx/2023zsxxxb-bkp-ls_pxzy0725.pdf",
    },
    "score_rank_physics": {
        "path": RAW_DIR / "2023_cq_score_rank_physics.html",
        "download_url": "https://gaokao.eol.cn/chong_qing/dongtai/202306/t20230624_2446728.shtml",
        "source_url": "https://gaokao.eol.cn/chong_qing/dongtai/202306/t20230624_2446728.shtml",
    },
    "score_rank_history": {
        "path": RAW_DIR / "2023_cq_score_rank_history.html",
        "download_url": "https://gaokao.eol.cn/chong_qing/dongtai/202306/t20230624_2446726.shtml",
        "source_url": "https://gaokao.eol.cn/chong_qing/dongtai/202306/t20230624_2446726.shtml",
    },
}

base.SKIP_LINES.update(
    {
        "2023年重庆市普通高校招生信息表",
        "本科批-物理-平行志愿",
        "本科批-历史-平行志愿",
        "院校专业投档",
    }
)


def download_sources(*, force: bool = False) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    headers = {"User-Agent": "Mozilla/5.0"}
    for name, meta in DOWNLOADS.items():
        path = meta["path"]
        if path.exists() and path.stat().st_size > 1000 and not force:
            print(f"Using existing raw file: {path}")
            continue
        response = requests.get(meta["download_url"], headers=headers, timeout=120)
        response.raise_for_status()
        path.write_bytes(response.content)
        print(f"Downloaded {name}: {path} bytes={path.stat().st_size}")


def parse_score_label(label: str) -> tuple[int, int]:
    text = str(label).strip()
    match = re.match(r"^(\d+)-(\d+)", text)
    if match:
        return int(match.group(1)), int(match.group(2))
    match = re.match(r"^(\d+)及以上", text)
    if match:
        return int(match.group(1)), 750
    match = re.match(r"^(\d+)", text)
    if match:
        score = int(match.group(1))
        return score, score
    raise ValueError(f"Cannot parse score label: {label!r}")


def parse_score_rank(subject_type: str, html_path: Path, source_url: str) -> base.ScoreRankData:
    html = html_path.read_text(encoding="utf-8", errors="ignore")
    table = pd.read_html(StringIO(html))[0]
    raw_rows = table.copy()
    first_label = str(raw_rows.iloc[0, 0]).strip()
    if first_label in {"分数", "分数段"}:
        raw_rows = raw_rows.iloc[1:].copy()
    parsed_rows: list[dict[str, Any]] = []
    score_to_rank: dict[int, int] = {}
    batch_line_score = BATCH_LINES[subject_type]
    above_batch_line_count: int | None = None

    for _, row in raw_rows.iterrows():
        score_low, score_high = parse_score_label(str(row.iloc[0]))
        cumulative_count = int(row.iloc[2])
        same_score_text = str(row.iloc[1]).strip()
        same_score_count = cumulative_count if "及以上" in same_score_text else int(same_score_text)
        if same_score_count == 0:
            continue
        rank_min = cumulative_count - same_score_count + 1
        rank_max = cumulative_count
        if score_low == batch_line_score:
            above_batch_line_count = cumulative_count
        parsed_rows.append(
            {
                "year": YEAR,
                "province": "重庆",
                "subject_type": subject_type,
                "score": score_low,
                "rank_min": rank_min,
                "rank_max": rank_max,
                "same_score_count": same_score_count,
                "cumulative_count": cumulative_count,
                "batch_line_score": batch_line_score,
                "above_batch_line_count": 0,
                "source_url": source_url,
            }
        )
        for score in range(score_low, score_high + 1):
            score_to_rank[score] = cumulative_count

    if above_batch_line_count is None:
        raise ValueError(f"Cannot find 2023 {subject_type} batch-line row in {html_path}")
    for row in parsed_rows:
        row["above_batch_line_count"] = above_batch_line_count
    return base.ScoreRankData(rows=parsed_rows, score_to_rank=score_to_rank)


def parse_school_line(lines: list[str], index: int) -> tuple[str, str, int] | None:
    line = lines[index]
    combined = re.match(r"^([0-9A-Z]{4})(.+)$", line)
    if combined:
        return combined.group(1), combined.group(2), index + 1
    if base.looks_like_school_code(line) and index + 1 < len(lines):
        return line, lines[index + 1], index + 2
    return None


def split_major_line_score(line: str) -> tuple[str, int] | None:
    match = re.match(r"^(.+?)(\d{3})$", line)
    if not match:
        return None
    score = int(match.group(2))
    if 180 <= score <= 750:
        return match.group(1), score
    return None


def parse_admission_pdf(
    subject_type: str,
    pdf_path: Path,
    source_url: str,
    score_to_rank: dict[int, int],
) -> list[dict[str, Any]]:
    lines = base.extract_pdf_lines(pdf_path)
    rows: list[dict[str, Any]] = []
    index = 0
    while index < len(lines):
        parsed_school = parse_school_line(lines, index)
        if parsed_school is None:
            index += 1
            continue
        school_code, school_name, cursor = parsed_school
        if cursor >= len(lines):
            break
        parsed_major_code = base.parse_major_code_line(lines[cursor])
        if parsed_major_code is None:
            index += 1
            continue
        major_code, major_name_prefix = parsed_major_code

        name_parts: list[str] = []
        if major_name_prefix:
            name_parts.append(major_name_prefix)
        cursor += 1
        min_score: int | None = None
        while cursor < len(lines):
            if base.looks_like_score(lines[cursor]):
                min_score = int(lines[cursor])
                cursor += 1
                break
            split = split_major_line_score(lines[cursor])
            if split:
                name_part, min_score = split
                name_parts.append(name_part)
                cursor += 1
                break
            name_parts.append(lines[cursor])
            cursor += 1
        if min_score is None:
            break
        major_name = "".join(name_parts)
        min_rank = score_to_rank.get(min_score)
        if min_rank is None:
            raise ValueError(f"No score-rank mapping for {subject_type} score {min_score}")

        rows.append(
            {
                "year": YEAR,
                "province": "重庆",
                "subject_type": subject_type,
                "batch": "本科批",
                "school_code": school_code,
                "school_name": school_name,
                "major_group_code": "",
                "major_code": major_code,
                "major_name": major_name,
                "major_category": "",
                "discipline_category": "",
                "admission_type": base.admission_type_for(school_name, major_name),
                "min_score": min_score,
                "min_rank": min_rank,
                "plan_count": "",
                "source_url": source_url,
                "source_type": "manual_verified",
                "confidence": "medium",
                "risk_notes": "真实PDF抽取；min_rank按2023一分一段表中投档最低分对应累计人数折算，非官方逐人精确位次。",
            }
        )

        consumed_sort_fields = 0
        while cursor < len(lines) and consumed_sort_fields < 4 and re.match(r"^\d{1,3}$", lines[cursor]):
            cursor += 1
            consumed_sort_fields += 1
        index = cursor
    return rows


def build_csv_files() -> tuple[Path, Path]:
    physics_rank = parse_score_rank(
        "物理",
        DOWNLOADS["score_rank_physics"]["path"],
        DOWNLOADS["score_rank_physics"]["source_url"],
    )
    history_rank = parse_score_rank(
        "历史",
        DOWNLOADS["score_rank_history"]["path"],
        DOWNLOADS["score_rank_history"]["source_url"],
    )
    score_rows = physics_rank.rows + history_rank.rows

    admission_rows = parse_admission_pdf(
        "物理",
        DOWNLOADS["admission_physics"]["path"],
        DOWNLOADS["admission_physics"]["source_url"],
        physics_rank.score_to_rank,
    ) + parse_admission_pdf(
        "历史",
        DOWNLOADS["admission_history"]["path"],
        DOWNLOADS["admission_history"]["source_url"],
        history_rank.score_to_rank,
    )

    score_path = CLEAN_DIR / "score_rank_table_2023_chongqing.csv"
    admission_path = CLEAN_DIR / "admission_history_2023_chongqing_benke.csv"
    base.write_csv(score_path, base.SCORE_RANK_COLUMNS, score_rows)
    base.write_csv(admission_path, base.ADMISSION_COLUMNS, admission_rows)
    return score_path, admission_path


def import_into_db(score_path: Path, admission_path: Path, db_path: Path, *, dry_run: bool) -> None:
    sys.path.insert(0, str(ROOT))
    from import_data import import_csv

    for table, path in [
        ("score_rank_table", score_path),
        ("admission_history", admission_path),
    ]:
        result = import_csv(db_path, path, table, replace_scope=True, dry_run=dry_run)
        action = "Validated" if dry_run else "Imported"
        print(f"{action} {result.row_count} rows for {table}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import 2023 Chongqing real public data into SQLite.")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB_PATH)
    parser.add_argument("--force-download", action="store_true")
    parser.add_argument("--extract-only", action="store_true", help="Only write cleaned CSV files.")
    parser.add_argument("--dry-run", action="store_true", help="Validate CSV files without writing to SQLite.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    download_sources(force=args.force_download)
    score_path, admission_path = build_csv_files()
    if not args.extract_only:
        import_into_db(score_path, admission_path, args.db, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
