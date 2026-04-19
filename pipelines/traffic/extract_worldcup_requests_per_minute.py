#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import re
import struct
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path


RECORD_STRUCT = struct.Struct(">IIII4B")
WORLDCUP_LOCAL_TZ = timezone(timedelta(hours=2))
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = Path("dataset/raw/worldcup98_may_1998")
DEFAULT_OUTPUT = Path("dataset/processed/traffic/worldcup98_may_1998")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract continuous per-minute request count series from World Cup 98 binary access logs."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help="Path to a World Cup log file or directory, relative to the project root by default.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Path to an output CSV file or directory, relative to the project root by default.",
    )
    return parser.parse_args()


def resolve_project_path(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def natural_sort_key(path: Path) -> list[int | str]:
    return [int(part) if part.isdigit() else part.lower() for part in re.split(r"(\d+)", path.name)]


def iter_input_files(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    return sorted(input_path.glob("wc_day*_1"), key=natural_sort_key)


def extract_counts(input_path: Path) -> tuple[Counter, datetime, datetime, int]:
    counts: Counter = Counter()
    min_ts: datetime | None = None
    max_ts: datetime | None = None
    skipped_records = 0

    with input_path.open("rb") as f:
        while True:
            chunk = f.read(RECORD_STRUCT.size)
            if not chunk:
                break
            if len(chunk) != RECORD_STRUCT.size:
                skipped_records += 1
                break

            timestamp, _, _, _, _, _, _, _ = RECORD_STRUCT.unpack(chunk)
            ts = datetime.fromtimestamp(timestamp, tz=timezone.utc).astimezone(WORLDCUP_LOCAL_TZ)
            minute_ts = ts.replace(second=0, microsecond=0)
            counts[minute_ts] += 1

            if min_ts is None or minute_ts < min_ts:
                min_ts = minute_ts
            if max_ts is None or minute_ts > max_ts:
                max_ts = minute_ts

    if min_ts is None or max_ts is None:
        raise ValueError(f"No valid records found in {input_path}")

    return counts, min_ts, max_ts, skipped_records


def write_series(output_path: Path, counts: Counter, min_ts: datetime, max_ts: datetime) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    current = min_ts
    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "request_count"])

        while current <= max_ts:
            writer.writerow([current.isoformat(), counts.get(current, 0)])
            current += timedelta(minutes=1)


def build_output_path(input_file: Path, output_path: Path, is_input_dir: bool) -> Path:
    if is_input_dir:
        return output_path / f"{input_file.stem}_requests_per_minute.csv"
    if output_path.suffix.lower() != ".csv":
        return output_path / f"{input_file.stem}_requests_per_minute.csv"
    return output_path


def main() -> None:
    args = parse_args()
    input_path = resolve_project_path(args.input)
    output_path = resolve_project_path(args.output)
    input_files = iter_input_files(input_path)

    if not input_files:
        raise FileNotFoundError(f"No World Cup log files found in {input_path}")

    is_input_dir = input_path.is_dir()
    for input_file in input_files:
        current_output = build_output_path(input_file, output_path, is_input_dir)
        counts, min_ts, max_ts, skipped_records = extract_counts(input_file)
        write_series(current_output, counts, min_ts, max_ts)

        span_minutes = int((max_ts - min_ts).total_seconds() // 60) + 1
        print(f"input={input_file}")
        print(f"output={current_output}")
        print(f"start={min_ts.isoformat()}")
        print(f"end={max_ts.isoformat()}")
        print(f"minutes={span_minutes}")
        print(f"nonzero_minutes={len(counts)}")
        print(f"skipped_records={skipped_records}")
        print("-")


if __name__ == "__main__":
    main()
