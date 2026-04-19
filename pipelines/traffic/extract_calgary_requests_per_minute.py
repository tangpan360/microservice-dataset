#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import re
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path


TIMESTAMP_RE = re.compile(r"\[(\d{2}/[A-Za-z]{3}/\d{4}:\d{2}:\d{2}:\d{2} [+-]\d{4})\]")
TIMESTAMP_FMT = "%d/%b/%Y:%H:%M:%S %z"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = Path("dataset/raw/Calgary-HTTP/calgary_access_log")
DEFAULT_OUTPUT = Path("dataset/processed/traffic/Calgary-HTTP/calgary_access_log_requests_per_minute.csv")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract a continuous per-minute request count series from Calgary HTTP access logs."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help="Path to the raw Calgary access log file, relative to the project root by default.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Path to the output CSV file, relative to the project root by default.",
    )
    return parser.parse_args()


def resolve_project_path(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def extract_counts(input_path: Path) -> tuple[Counter, datetime, datetime, int]:
    counts: Counter = Counter()
    min_ts: datetime | None = None
    max_ts: datetime | None = None
    skipped_lines = 0

    with input_path.open("r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            match = TIMESTAMP_RE.search(line)
            if match is None:
                skipped_lines += 1
                continue

            try:
                ts = datetime.strptime(match.group(1), TIMESTAMP_FMT)
            except ValueError:
                skipped_lines += 1
                continue

            minute_ts = ts.replace(second=0, microsecond=0)
            counts[minute_ts] += 1

            if min_ts is None or minute_ts < min_ts:
                min_ts = minute_ts
            if max_ts is None or minute_ts > max_ts:
                max_ts = minute_ts

    if min_ts is None or max_ts is None:
        raise ValueError(f"No valid timestamps found in {input_path}")

    return counts, min_ts, max_ts, skipped_lines


def write_series(output_path: Path, counts: Counter, min_ts: datetime, max_ts: datetime) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    current = min_ts
    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "request_count"])

        while current <= max_ts:
            writer.writerow([current.isoformat(), counts.get(current, 0)])
            current += timedelta(minutes=1)


def main() -> None:
    args = parse_args()
    input_path = resolve_project_path(args.input)
    output_path = resolve_project_path(args.output)

    counts, min_ts, max_ts, skipped_lines = extract_counts(input_path)
    write_series(output_path, counts, min_ts, max_ts)

    span_minutes = int((max_ts - min_ts).total_seconds() // 60) + 1
    print(f"input={input_path}")
    print(f"output={output_path}")
    print(f"start={min_ts.isoformat()}")
    print(f"end={max_ts.isoformat()}")
    print(f"minutes={span_minutes}")
    print(f"nonzero_minutes={len(counts)}")
    print(f"skipped_lines={skipped_lines}")


if __name__ == "__main__":
    main()
