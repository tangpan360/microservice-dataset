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
DEFAULT_INPUT = Path("dataset/raw/ClarkNet-HTTP")
DEFAULT_OUTPUT = Path("dataset/processed/traffic/ClarkNet-HTTP/clarknet_access_log_aug28_sep10_requests_per_second.csv")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract continuous per-second request count series from ClarkNet HTTP access logs."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help="Path to a ClarkNet log file or directory, relative to the project root by default.",
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
    return sorted(
        [
            path
            for path in input_path.glob("clarknet_access_log_*")
            if path.is_file() and path.suffix.lower() != ".gz"
        ],
        key=natural_sort_key,
    )


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

            second_ts = ts.replace(microsecond=0)
            counts[second_ts] += 1

            if min_ts is None or second_ts < min_ts:
                min_ts = second_ts
            if max_ts is None or second_ts > max_ts:
                max_ts = second_ts

    if min_ts is None or max_ts is None:
        raise ValueError(f"No valid timestamps found in {input_path}")

    return counts, min_ts, max_ts, skipped_lines


def merge_results(
    results: list[tuple[Counter, datetime, datetime, int]],
) -> tuple[Counter, datetime, datetime, int]:
    merged_counts: Counter = Counter()
    min_ts: datetime | None = None
    max_ts: datetime | None = None
    skipped_lines = 0

    for counts, current_min_ts, current_max_ts, current_skipped_lines in results:
        merged_counts.update(counts)
        skipped_lines += current_skipped_lines

        if min_ts is None or current_min_ts < min_ts:
            min_ts = current_min_ts
        if max_ts is None or current_max_ts > max_ts:
            max_ts = current_max_ts

    if min_ts is None or max_ts is None:
        raise ValueError("No valid timestamps found in merged ClarkNet inputs")

    return merged_counts, min_ts, max_ts, skipped_lines


def write_series(output_path: Path, counts: Counter, min_ts: datetime, max_ts: datetime) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    current = min_ts
    with output_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "request_count"])

        while current <= max_ts:
            writer.writerow([current.isoformat(), counts.get(current, 0)])
            current += timedelta(seconds=1)


def main() -> None:
    args = parse_args()
    input_path = resolve_project_path(args.input)
    output_path = resolve_project_path(args.output)
    input_files = iter_input_files(input_path)

    if not input_files:
        raise FileNotFoundError(f"No ClarkNet log files found in {input_path}")

    if output_path.suffix.lower() != ".csv":
        raise ValueError("output must be a .csv file path")

    results = [extract_counts(input_file) for input_file in input_files]
    counts, min_ts, max_ts, skipped_lines = merge_results(results)
    write_series(output_path, counts, min_ts, max_ts)

    span_seconds = int((max_ts - min_ts).total_seconds()) + 1
    print(f"input={input_path}")
    print(f"output={output_path}")
    print(f"start={min_ts.isoformat()}")
    print(f"end={max_ts.isoformat()}")
    print(f"seconds={span_seconds}")
    print(f"nonzero_seconds={len(counts)}")
    print(f"skipped_lines={skipped_lines}")


if __name__ == "__main__":
    main()
