#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INPUT = Path("dataset/processed/traffic")
DEFAULT_OUTPUT = Path("analysis")
DATASET_ALIASES = {
    "clarknet": "ClarkNet-HTTP",
    "nasa": "NASA-HTTP",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Plot per-day minute curves from processed traffic CSV files by aggregating rows into minute bins."
    )
    parser.add_argument(
        "--data",
        dest="dataset_name",
        help="Optional dataset name under dataset/processed/traffic, e.g. clarknet.",
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=None,
        help="Path to a processed traffic CSV file or a directory containing CSV files.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Path to an output image file or directory.",
    )
    parser.add_argument(
        "--max-days",
        type=int,
        default=31,
        help="Maximum number of days to plot from the start of each series. Use 0 to disable the limit.",
    )
    return parser.parse_args()


def resolve_project_path(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def resolve_dataset_name(name: str) -> str:
    return DATASET_ALIASES.get(name.lower(), name)


def resolve_paths(args: argparse.Namespace) -> tuple[Path, Path]:
    if args.dataset_name is not None:
        dataset_dir = Path("dataset/processed/traffic") / resolve_dataset_name(args.dataset_name)
        input_path = resolve_project_path(args.input or dataset_dir)
        output_path = resolve_project_path(args.output or dataset_dir)
        return input_path, output_path

    input_path = resolve_project_path(args.input or DEFAULT_INPUT)
    output_path = resolve_project_path(args.output or DEFAULT_OUTPUT)
    return input_path, output_path


def iter_input_files(input_path: Path) -> list[Path]:
    if input_path.is_file():
        return [input_path]
    return sorted(input_path.rglob("*.csv"))


def load_daily_series(input_path: Path, max_days: int) -> tuple[list[str], list[np.ndarray]]:
    days: dict[str, np.ndarray] = defaultdict(lambda: np.zeros(1440, dtype=int))

    with input_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            ts = datetime.fromisoformat(row["timestamp"])
            day = ts.date().isoformat()
            minute_of_day = ts.hour * 60 + ts.minute
            days[day][minute_of_day] += int(row["request_count"])

    ordered_days = sorted(days)
    if max_days > 0:
        ordered_days = ordered_days[:max_days]
    series = [days[day] for day in ordered_days]
    return ordered_days, series


def build_output_path(input_file: Path, output_path: Path, is_input_dir: bool) -> Path:
    stem = input_file.stem
    stem = stem.replace("_requests_per_second", "")
    stem = stem.replace("_requests_per_minute", "")
    filename = f"{stem}_daily_minute_curves.png"
    if is_input_dir:
        return output_path / filename
    if output_path.suffix.lower() == ".png":
        return output_path
    return output_path / filename


def plot_daily_curves(input_path: Path, output_path: Path, max_days: int) -> None:
    ordered_days, series = load_daily_series(input_path, max_days)
    if not series:
        raise ValueError(f"No data rows found in {input_path}")

    max_y = max(int(s.max()) for s in series)
    fig, axes = plt.subplots(len(ordered_days), 1, figsize=(14, max(8, len(ordered_days) * 1.6)), sharex=True)
    if len(ordered_days) == 1:
        axes = [axes]

    x = np.arange(1440)
    xticks = np.arange(0, 1441, 240)
    xticklabels = ["00:00", "04:00", "08:00", "12:00", "16:00", "20:00", "24:00"]

    for ax, day, s in zip(axes, ordered_days, series):
        ax.plot(x, s, color="tab:blue", linewidth=0.9)
        ax.set_ylim(0, max_y * 1.02)
        ax.set_ylabel(day, rotation=0, labelpad=38, fontsize=8, va="center")
        ax.grid(True, axis="y", alpha=0.25, linewidth=0.5)
        peak_idx = int(s.argmax())
        peak_val = int(s.max())
        ax.scatter([peak_idx], [peak_val], color="tab:red", s=10, zorder=3)
        ax.text(peak_idx, peak_val, f" {peak_val}", fontsize=6, va="bottom", ha="left")

    title = f"{input_path.stem} by day"
    if max_days > 0 and len(ordered_days) == max_days:
        title += f" (first {max_days} days)"
    axes[0].set_title(title, fontsize=14)
    axes[-1].set_xticks(xticks)
    axes[-1].set_xticklabels(xticklabels)
    axes[-1].set_xlabel("Time of day")
    fig.supylabel("Date")
    fig.tight_layout(rect=(0.06, 0.03, 1, 0.98))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=180)
    plt.close(fig)


def main() -> None:
    args = parse_args()
    input_path, output_path = resolve_paths(args)
    input_files = iter_input_files(input_path)

    if not input_files:
        raise FileNotFoundError(f"No processed traffic CSV files found in {input_path}")

    is_input_dir = input_path.is_dir()
    for input_file in input_files:
        current_output = build_output_path(input_file, output_path, is_input_dir)
        plot_daily_curves(input_file, current_output, args.max_days)
        print(f"input={input_file}")
        print(f"output={current_output}")
        print("-")


if __name__ == "__main__":
    main()
