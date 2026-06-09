#!/usr/bin/env python3
"""Download, extract, and import 2025 Chongqing public gaokao data.

The admission PDFs list the official filing minimum score and same-score
sorting fields, but do not directly expose a rank field. For this project
schema, min_rank is derived from the 2025 score-rank table cumulative count at
the filing minimum score. Rows using that derived rank are marked
manual_verified with a risk note.
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from dataclasses import dataclass
from io import StringIO
from pathlib import Path
from typing import Any

import fitz
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw" / "cq" / "2025"
CLEAN_DIR = ROOT / "data" / "cleaned" / "cq" / "2025"
DEFAULT_DB_PATH = ROOT / "gaokao_agent.db"

ADMISSION_COLUMNS = [
    "year",
    "province",
    "subject_type",
    "batch",
    "school_code",
    "school_name",
    "major_group_code",
    "major_code",
    "major_name",
    "major_category",
    "discipline_category",
    "admission_type",
    "min_score",
    "min_rank",
    "plan_count",
    "source_url",
    "source_type",
    "confidence",
    "risk_notes",
]

SCORE_RANK_COLUMNS = [
    "year",
    "province",
    "subject_type",
    "score",
    "rank_min",
    "rank_max",
    "same_score_count",
    "cumulative_count",
    "batch_line_score",
    "above_batch_line_count",
    "source_url",
]

DOWNLOADS = {
    "admission_physics": {
        "path": RAW_DIR / "2025_cq_benke_physics.pdf",
        "download_url": "https://cdn.gaokzx.com/zixunzhan/1753323564725%E7%89%A9%E7%90%86.pdf",
        "source_url": "https://www.cqksy.cn/uploadFile/infopub/202507/1947199748985856000.pdf?fileName=2025xxb-Bkp_WLPx0721.pdf&fileSize=1033364",
    },
    "admission_history": {
        "path": RAW_DIR / "2025_cq_benke_history.pdf",
        "download_url": "https://img.gaokaozhitongche.com/uploads/file/2025/0721/1753084774657802.pdf",
        "source_url": "https://www.cqksy.cn/uploadFile/infopub/202507/1947199599647662080.pdf?fileName=2025xxb-Bkp_LSPx0721.pdf&fileSize=446211",
    },
    "score_rank_physics": {
        "path": RAW_DIR / "2025_cq_score_rank_physics.html",
        "download_url": "https://gaokao.eol.cn/chong_qing/dongtai/202506/t20250624_2676788.shtml",
        "source_url": "https://gaokao.eol.cn/chong_qing/dongtai/202506/t20250624_2676788.shtml",
    },
    "score_rank_history": {
        "path": RAW_DIR / "2025_cq_score_rank_history.html",
        "download_url": "https://gaokao.eol.cn/chong_qing/dongtai/202506/t20250624_2676749.shtml",
        "source_url": "https://gaokao.eol.cn/chong_qing/dongtai/202506/t20250624_2676749.shtml",
    },
}

SKIP_LINES = {
    "2025年重庆市普通高校招生信息表",
    "本科批-物理-平行志愿",
    "本科批-历史-平行志愿",
    "投档最低分同分排序项",
    "（前4项）",
    "院校",
    "代号",
    "院校名称",
    "专业",
    "专业名称",
    "投档",
    "最低分",
    "语数",
    "之和",
    "最高",
    "外语",
    "首选",
    "科目",
    "重庆市教育考试院",
}

WATERMARK_LINES = {"重", "庆", "市", "教", "育", "考", "试", "院"}


@dataclass(frozen=True)
class ScoreRankData:
    rows: list[dict[str, Any]]
    score_to_rank: dict[int, int]


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
    match = re.match(r"^(\d+)", text)
    if match:
        score = int(match.group(1))
        return score, score
    raise ValueError(f"Cannot parse score label: {label!r}")


def parse_score_rank(subject_type: str, html_path: Path, source_url: str) -> ScoreRankData:
    html = html_path.read_text(encoding="utf-8", errors="ignore")
    title_match = re.search(r"(\d+)人超本科线", html)
    if not title_match:
        raise ValueError(f"Cannot find above-batch count in {html_path}")
    above_batch_line_count = int(title_match.group(1))

    table = pd.read_html(StringIO(html))[0]
    raw_rows = table.iloc[1:].copy()
    parsed_rows: list[dict[str, Any]] = []
    score_to_rank: dict[int, int] = {}
    batch_line_score: int | None = None

    for _, row in raw_rows.iterrows():
        score_low, score_high = parse_score_label(str(row.iloc[0]))
        same_score_count = int(row.iloc[1])
        cumulative_count = int(row.iloc[2])
        rank_min = cumulative_count - same_score_count + 1
        rank_max = cumulative_count
        if cumulative_count == above_batch_line_count:
            batch_line_score = score_low
        parsed_rows.append(
            {
                "year": 2025,
                "province": "重庆",
                "subject_type": subject_type,
                "score": score_low,
                "rank_min": rank_min,
                "rank_max": rank_max,
                "same_score_count": same_score_count,
                "cumulative_count": cumulative_count,
                "batch_line_score": 0,
                "above_batch_line_count": above_batch_line_count,
                "source_url": source_url,
            }
        )
        for score in range(score_low, score_high + 1):
            score_to_rank[score] = cumulative_count

    if batch_line_score is None:
        raise ValueError(f"Cannot map above-batch count to batch line score in {html_path}")
    for row in parsed_rows:
        row["batch_line_score"] = batch_line_score
    return ScoreRankData(rows=parsed_rows, score_to_rank=score_to_rank)


def normalize_line(line: str) -> str:
    return re.sub(r"\s+", "", line.strip())


def extract_pdf_lines(pdf_path: Path) -> list[str]:
    doc = fitz.open(pdf_path)
    lines: list[str] = []
    for page in doc:
        for raw_line in page.get_text("text").splitlines():
            line = normalize_line(raw_line)
            if not line:
                continue
            if line in SKIP_LINES or line in WATERMARK_LINES:
                continue
            if re.match(r"^\d+/\d+$", line):
                continue
            lines.append(line)
    return lines


def looks_like_school_code(line: str) -> bool:
    return bool(re.match(r"^[0-9A-Z]{4}$", line))


def looks_like_major_code(line: str) -> bool:
    return bool(re.match(r"^[0-9A-Z]{3}$", line))


def parse_major_code_line(line: str) -> tuple[str, str] | None:
    match = re.match(r"^([0-9A-Z]{3})(.*)$", line)
    if not match:
        return None
    return match.group(1), match.group(2)


def looks_like_score(line: str) -> bool:
    if not re.match(r"^\d{3}$", line):
        return False
    value = int(line)
    return 180 <= value <= 750


def admission_type_for(school_name: str, major_name: str) -> str:
    combined = f"{school_name}{major_name}"
    if "中外合作" in combined:
        return "中外合作"
    if "民族班" in combined:
        return "民族班"
    if "预科" in combined:
        return "预科"
    if "专项" in combined:
        return "专项"
    return "普通类"


def parse_admission_pdf(
    subject_type: str,
    pdf_path: Path,
    source_url: str,
    score_to_rank: dict[int, int],
) -> list[dict[str, Any]]:
    lines = extract_pdf_lines(pdf_path)
    rows: list[dict[str, Any]] = []
    index = 0
    while index < len(lines):
        if not looks_like_school_code(lines[index]):
            index += 1
            continue
        school_code = lines[index]
        if index + 2 >= len(lines):
            break
        school_name = lines[index + 1]
        parsed_major_code = parse_major_code_line(lines[index + 2])
        if parsed_major_code is None:
            index += 1
            continue
        major_code, major_name_prefix = parsed_major_code

        name_parts: list[str] = []
        if major_name_prefix:
            name_parts.append(major_name_prefix)
        cursor = index + 3
        while cursor < len(lines) and not looks_like_score(lines[cursor]):
            name_parts.append(lines[cursor])
            cursor += 1
        if cursor >= len(lines):
            break
        major_name = "".join(name_parts)
        min_score = int(lines[cursor])
        min_rank = score_to_rank.get(min_score)
        if min_rank is None:
            raise ValueError(f"No score-rank mapping for {subject_type} score {min_score}")

        rows.append(
            {
                "year": 2025,
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
                "admission_type": admission_type_for(school_name, major_name),
                "min_score": min_score,
                "min_rank": min_rank,
                "plan_count": "",
                "source_url": source_url,
                "source_type": "manual_verified",
                "confidence": "medium",
                "risk_notes": "真实PDF抽取；min_rank按2025一分一段表中投档最低分对应累计人数折算，非官方逐人精确位次。",
            }
        )

        cursor += 1
        consumed_sort_fields = 0
        while cursor < len(lines) and consumed_sort_fields < 4 and re.match(r"^\d{1,3}$", lines[cursor]):
            cursor += 1
            consumed_sort_fields += 1
        index = cursor
    return rows


def write_csv(path: Path, columns: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows: {path}")


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

    score_path = CLEAN_DIR / "score_rank_table_2025_chongqing.csv"
    admission_path = CLEAN_DIR / "admission_history_2025_chongqing_benke.csv"
    write_csv(score_path, SCORE_RANK_COLUMNS, score_rows)
    write_csv(admission_path, ADMISSION_COLUMNS, admission_rows)
    return score_path, admission_path


def import_into_db(score_path: Path, admission_path: Path, db_path: Path, *, dry_run: bool) -> None:
    sys.path.insert(0, str(ROOT))
    from import_data import import_csv

    for table, path in [
        ("score_rank_table", score_path),
        ("admission_history", admission_path),
    ]:
        result = import_csv(
            db_path,
            path,
            table,
            replace_scope=True,
            dry_run=dry_run,
        )
        action = "Validated" if dry_run else "Imported"
        print(f"{action} {result.row_count} rows for {table}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import 2025 Chongqing real public data into SQLite.")
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
