#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import math
import os
import re
import shutil
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path


BUCKET_MS = 60_000
DAY_SECONDS = 86_400
DEFAULT_RUN_ID = "ali2022-callgraph-v1"
DEFAULT_SCENARIO_ID = "ali2022-callgraph-minute-v1"
DEFAULT_APP_NAME = "alibaba_microservices_2022"
UNKNOWN_SERVICE = "UNKNOWN"


@dataclass
class EdgeAggregate:
    call_count: int = 0
    rt_sum: float = 0.0
    rt_max: float = 0.0
    rt_values: list[float] = field(default_factory=list)

    def add(self, rt: float) -> None:
        self.call_count += 1
        self.rt_sum += rt
        if rt > self.rt_max:
            self.rt_max = rt
        self.rt_values.append(rt)


@dataclass
class ServiceStats:
    first_seen_timestamp_bucket_s: int | None = None
    last_seen_timestamp_bucket_s: int | None = None
    total_active_minutes: int = 0
    total_in_calls: float = 0.0
    total_out_calls: float = 0.0
    nonzero_in_minutes: int = 0
    max_in_calls: float = 0.0

    def update(self, bucket_s: int, in_calls: float, out_calls: float) -> None:
        if self.first_seen_timestamp_bucket_s is None or bucket_s < self.first_seen_timestamp_bucket_s:
            self.first_seen_timestamp_bucket_s = bucket_s
        if self.last_seen_timestamp_bucket_s is None or bucket_s > self.last_seen_timestamp_bucket_s:
            self.last_seen_timestamp_bucket_s = bucket_s
        self.total_active_minutes += 1
        self.total_in_calls += float(in_calls)
        self.total_out_calls += float(out_calls)
        if in_calls > 0:
            self.nonzero_in_minutes += 1
        if in_calls > self.max_in_calls:
            self.max_in_calls = float(in_calls)

    def merge(self, other: "ServiceStats") -> None:
        if other.first_seen_timestamp_bucket_s is not None:
            if (
                self.first_seen_timestamp_bucket_s is None
                or other.first_seen_timestamp_bucket_s < self.first_seen_timestamp_bucket_s
            ):
                self.first_seen_timestamp_bucket_s = other.first_seen_timestamp_bucket_s
        if other.last_seen_timestamp_bucket_s is not None:
            if (
                self.last_seen_timestamp_bucket_s is None
                or other.last_seen_timestamp_bucket_s > self.last_seen_timestamp_bucket_s
            ):
                self.last_seen_timestamp_bucket_s = other.last_seen_timestamp_bucket_s
        self.total_active_minutes += other.total_active_minutes
        self.total_in_calls += other.total_in_calls
        self.total_out_calls += other.total_out_calls
        self.nonzero_in_minutes += other.nonzero_in_minutes
        self.max_in_calls = max(self.max_in_calls, other.max_in_calls)


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def default_trace_root() -> Path:
    return repo_root() / "dataset/raw/clusterdata/cluster-trace-microservices-v2022"


def default_output_root() -> Path:
    return repo_root() / "dataset/processed/ali2022_callgraph"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build first-pass Ali2022 minute-level service and edge tables from CallGraph."
    )
    parser.add_argument("--trace-root", type=Path, default=default_trace_root())
    parser.add_argument("--output-root", type=Path, default=default_output_root())
    parser.add_argument("--run-id", default=DEFAULT_RUN_ID)
    parser.add_argument("--scenario-id", default=DEFAULT_SCENARIO_ID)
    parser.add_argument("--app-name", default=DEFAULT_APP_NAME)
    parser.add_argument("--max-files", type=int, default=None)
    parser.add_argument(
        "--workers",
        type=int,
        default=min(16, max(1, (os.cpu_count() or 1))),
        help="Number of worker processes for parallel CallGraph parsing.",
    )
    parser.add_argument(
        "--clean-output",
        action="store_true",
        help="Remove existing run output directory before writing.",
    )
    return parser.parse_args()


def numeric_suffix(path: Path) -> int:
    match = re.search(r"(\d+)(?=\.csv$)", path.name)
    return int(match.group(1)) if match else -1


def minute_bucket_s(timestamp_ms: int) -> int:
    return (timestamp_ms // BUCKET_MS) * 60


def day_index_from_bucket(bucket_s: int) -> int:
    return bucket_s // DAY_SECONDS


def day_label(day_index: int) -> str:
    return f"{day_index:04d}"


def hour_of_day(bucket_s: int) -> int:
    return (bucket_s % DAY_SECONDS) // 3600


def minute_of_day(bucket_s: int) -> int:
    return (bucket_s % DAY_SECONDS) // 60


def quantile_p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    pos = 0.95 * (len(ordered) - 1)
    low = math.floor(pos)
    high = math.ceil(pos)
    if low == high:
        return float(ordered[low])
    frac = pos - low
    return float(ordered[low] * (1 - frac) + ordered[high] * frac)


def safe_float(value: str | None, default: float = 0.0) -> float:
    if value is None:
        return default
    text = str(value).strip()
    if not text or text.lower() == "none":
        return default
    try:
        return float(text)
    except ValueError:
        return default


def write_csv(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def iter_callgraph_rows(path: Path):
    with path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.reader(fh)
        _header = next(reader, None)
        for row in reader:
            if len(row) < 7:
                continue
            yield {
                "timestamp": row[0],
                "caller_service": row[-6].strip(),
                "callee_service": row[-3].strip(),
                "rt": row[-1],
            }


def chunk_list(items: list[Path], n_chunks: int) -> list[list[Path]]:
    if not items:
        return []
    n_chunks = max(1, min(n_chunks, len(items)))
    chunk_size = math.ceil(len(items) / n_chunks)
    return [items[i : i + chunk_size] for i in range(0, len(items), chunk_size)]


def format_seconds(seconds: float | None) -> str:
    if seconds is None or math.isinf(seconds) or math.isnan(seconds):
        return "--:--"
    total_seconds = max(0, int(round(seconds)))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours > 0:
        return f"{hours:d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def print_progress(
    *,
    stage: str,
    completed_chunks: int,
    total_chunks: int,
    completed_files: int,
    total_files: int,
    started_at: float,
    final: bool = False,
) -> None:
    width = 28
    ratio = completed_files / total_files if total_files else 1.0
    ratio = min(max(ratio, 0.0), 1.0)
    filled = int(width * ratio)
    bar = "#" * filled + "-" * (width - filled)
    elapsed = time.monotonic() - started_at
    rate = completed_files / elapsed if elapsed > 0 else 0.0
    remaining_files = max(0, total_files - completed_files)
    eta_seconds = (remaining_files / rate) if rate > 0 else None
    message = (
        f"\r[{stage}] [{bar}] {completed_files}/{total_files} files "
        f"({completed_chunks}/{total_chunks} chunks) "
        f"elapsed={format_seconds(elapsed)} eta={format_seconds(eta_seconds)}"
    )
    end = "\n" if final else ""
    print(message, end=end, file=sys.stderr, flush=True)


def collect_services_from_files(files: list[Path]) -> list[str]:
    services: set[str] = set()
    for path in files:
        for row in iter_callgraph_rows(path):
            caller = row["caller_service"]
            callee = row["callee_service"]
            if caller and caller != UNKNOWN_SERVICE:
                services.add(caller)
            if callee and callee != UNKNOWN_SERVICE:
                services.add(callee)
    return sorted(services)


def build_rows_for_day(
    *,
    day_idx: int,
    run_id: str,
    scenario_id: str,
    service_idx_map: dict[str, int],
    edge_aggs: dict[tuple[int, str, str], EdgeAggregate],
    external_inflow: dict[tuple[int, str], int],
    service_stats: dict[str, ServiceStats],
) -> tuple[list[dict], list[dict], dict]:
    edge_rows: list[dict] = []
    incoming: dict[tuple[int, str], list[tuple[str, int]]] = defaultdict(list)
    outgoing: dict[tuple[int, str], list[tuple[str, int]]] = defaultdict(list)
    active_services: dict[int, set[str]] = defaultdict(set)
    minute_buckets: set[int] = set()

    for (bucket_s, caller, callee), agg in sorted(edge_aggs.items()):
        minute_buckets.add(bucket_s)
        active_services[bucket_s].add(caller)
        active_services[bucket_s].add(callee)
        incoming[(bucket_s, callee)].append((caller, agg.call_count))
        outgoing[(bucket_s, caller)].append((callee, agg.call_count))
        edge_rows.append(
            {
                "timestamp_bucket_s": bucket_s,
                "caller_service": caller,
                "callee_service": callee,
                "call_count": agg.call_count,
                "edge_rt_mean": agg.rt_sum / agg.call_count if agg.call_count else 0.0,
                "edge_rt_p95": quantile_p95(agg.rt_values),
                "edge_rt_max": agg.rt_max,
                "caller_idx": service_idx_map[caller],
                "callee_idx": service_idx_map[callee],
                "run_id": run_id,
                "scenario_id": scenario_id,
                "day": day_label(day_idx),
            }
        )

    for (bucket_s, callee), _count in external_inflow.items():
        minute_buckets.add(bucket_s)
        active_services[bucket_s].add(callee)

    service_rows: list[dict] = []
    for bucket_s in sorted(active_services):
        services = sorted(active_services[bucket_s], key=lambda s: service_idx_map[s])
        for service in services:
            incoming_rows = incoming.get((bucket_s, service), [])
            outgoing_rows = outgoing.get((bucket_s, service), [])
            explicit_in = sum(count for _caller, count in incoming_rows)
            external_in = external_inflow.get((bucket_s, service), 0)
            service_in = explicit_in + external_in
            service_out = sum(count for _callee, count in outgoing_rows)
            upstream_counts = sorted((count for _caller, count in incoming_rows), reverse=True)
            downstream_counts = sorted((count for _callee, count in outgoing_rows), reverse=True)
            hour = hour_of_day(bucket_s)
            minute_idx = minute_of_day(bucket_s)
            service_rows.append(
                {
                    "timestamp_bucket_s": bucket_s,
                    "service": service,
                    "service_in_calls_per_min": service_in,
                    "service_out_calls_per_min": service_out,
                    "external_inflow_calls": external_in,
                    "upstream_total_calls": explicit_in,
                    "upstream_service_count": len(incoming_rows),
                    "downstream_total_calls": service_out,
                    "downstream_service_count": len(outgoing_rows),
                    "top1_upstream_calls": upstream_counts[0] if len(upstream_counts) > 0 else 0,
                    "top2_upstream_calls": upstream_counts[1] if len(upstream_counts) > 1 else 0,
                    "top3_upstream_calls": upstream_counts[2] if len(upstream_counts) > 2 else 0,
                    "top1_downstream_calls": downstream_counts[0] if len(downstream_counts) > 0 else 0,
                    "top2_downstream_calls": downstream_counts[1] if len(downstream_counts) > 1 else 0,
                    "top3_downstream_calls": downstream_counts[2] if len(downstream_counts) > 2 else 0,
                    "day_index": day_idx,
                    "hour_of_day": hour,
                    "minute_of_day": minute_idx,
                    "hour_sin": math.sin(2 * math.pi * hour / 24.0),
                    "hour_cos": math.cos(2 * math.pi * hour / 24.0),
                    "service_idx": service_idx_map[service],
                    "run_id": run_id,
                    "scenario_id": scenario_id,
                    "day": day_label(day_idx),
                }
            )
            service_stats[service].update(bucket_s, service_in, service_out)

    day_summary = {}
    if minute_buckets:
        day_summary = {
            "start_time_s": min(minute_buckets),
            "end_time_s": max(minute_buckets) + 60,
            "services": sorted({row["service"] for row in service_rows}),
        }
    return edge_rows, service_rows, day_summary


def write_part_files(
    *,
    run_dir: Path,
    file_part_id: str,
    day_idx: int,
    edge_rows: list[dict],
    service_rows: list[dict],
) -> None:
    if edge_rows:
        write_csv(
            run_dir / "service_call_edge_minute" / f"day={day_label(day_idx)}" / f"part-{file_part_id}.csv",
            [
                "timestamp_bucket_s",
                "caller_service",
                "callee_service",
                "call_count",
                "edge_rt_mean",
                "edge_rt_p95",
                "edge_rt_max",
                "caller_idx",
                "callee_idx",
                "run_id",
                "scenario_id",
                "day",
            ],
            edge_rows,
        )
    if service_rows:
        write_csv(
            run_dir / "service_minute_features" / f"day={day_label(day_idx)}" / f"part-{file_part_id}.csv",
            [
                "timestamp_bucket_s",
                "service",
                "service_in_calls_per_min",
                "service_out_calls_per_min",
                "external_inflow_calls",
                "upstream_total_calls",
                "upstream_service_count",
                "downstream_total_calls",
                "downstream_service_count",
                "top1_upstream_calls",
                "top2_upstream_calls",
                "top3_upstream_calls",
                "top1_downstream_calls",
                "top2_downstream_calls",
                "top3_downstream_calls",
                "day_index",
                "hour_of_day",
                "minute_of_day",
                "hour_sin",
                "hour_cos",
                "service_idx",
                "run_id",
                "scenario_id",
                "day",
            ],
            service_rows,
        )


def process_file_chunk(
    *,
    files: list[Path],
    run_dir: Path,
    run_id: str,
    scenario_id: str,
    service_idx_map: dict[str, int],
) -> tuple[dict[str, tuple], dict[int, dict]]:
    local_stats: dict[str, ServiceStats] = defaultdict(ServiceStats)
    local_day_summary: dict[int, dict] = {}

    for path in files:
        part_id = f"{numeric_suffix(path):05d}"
        edge_aggs_by_day: dict[int, dict[tuple[int, str, str], EdgeAggregate]] = defaultdict(dict)
        external_by_day: dict[int, dict[tuple[int, str], int]] = defaultdict(lambda: defaultdict(int))

        for row in iter_callgraph_rows(path):
            bucket_s = minute_bucket_s(int(row["timestamp"]))
            day_idx = day_index_from_bucket(bucket_s)
            caller = row["caller_service"]
            callee = row["callee_service"]
            if not callee or callee == UNKNOWN_SERVICE:
                continue
            if caller == UNKNOWN_SERVICE:
                external_by_day[day_idx][(bucket_s, callee)] += 1
                continue
            if not caller:
                continue
            key = (bucket_s, caller, callee)
            agg = edge_aggs_by_day[day_idx].get(key)
            if agg is None:
                agg = EdgeAggregate()
                edge_aggs_by_day[day_idx][key] = agg
            agg.add(safe_float(row.get("rt")))

        for day_idx in sorted(set(edge_aggs_by_day.keys()) | set(external_by_day.keys())):
            edge_rows, service_rows, day_summary = build_rows_for_day(
                day_idx=day_idx,
                run_id=run_id,
                scenario_id=scenario_id,
                service_idx_map=service_idx_map,
                edge_aggs=edge_aggs_by_day.get(day_idx, {}),
                external_inflow=external_by_day.get(day_idx, {}),
                service_stats=local_stats,
            )
            write_part_files(
                run_dir=run_dir,
                file_part_id=part_id,
                day_idx=day_idx,
                edge_rows=edge_rows,
                service_rows=service_rows,
            )
            if day_summary:
                summary = local_day_summary.setdefault(
                    day_idx,
                    {"start_time_s": day_summary["start_time_s"], "end_time_s": day_summary["end_time_s"], "services": set()},
                )
                summary["start_time_s"] = min(summary["start_time_s"], day_summary["start_time_s"])
                summary["end_time_s"] = max(summary["end_time_s"], day_summary["end_time_s"])
                summary["services"].update(day_summary["services"])

    packed_stats = {
        service: (
            stats.first_seen_timestamp_bucket_s,
            stats.last_seen_timestamp_bucket_s,
            stats.total_active_minutes,
            stats.total_in_calls,
            stats.total_out_calls,
            stats.nonzero_in_minutes,
            stats.max_in_calls,
        )
        for service, stats in local_stats.items()
    }
    packed_days = {
        day_idx: {
            "start_time_s": summary["start_time_s"],
            "end_time_s": summary["end_time_s"],
            "services": sorted(summary["services"]),
        }
        for day_idx, summary in local_day_summary.items()
    }
    return packed_stats, packed_days


def build_service_metadata_rows(
    service_idx_map: dict[str, int],
    service_stats: dict[str, ServiceStats],
) -> list[dict]:
    rows = []
    for service in sorted(service_idx_map, key=lambda s: service_idx_map[s]):
        stats = service_stats.get(service, ServiceStats())
        active_minutes = stats.total_active_minutes
        avg_in = stats.total_in_calls / active_minutes if active_minutes else 0.0
        rows.append(
            {
                "service": service,
                "service_idx": service_idx_map[service],
                "first_seen_timestamp_bucket_s": stats.first_seen_timestamp_bucket_s or 0,
                "last_seen_timestamp_bucket_s": stats.last_seen_timestamp_bucket_s or 0,
                "total_active_minutes": active_minutes,
                "nonzero_in_minutes": stats.nonzero_in_minutes,
                "total_in_calls": stats.total_in_calls,
                "total_out_calls": stats.total_out_calls,
                "avg_in_calls": avg_in,
                "max_in_calls": stats.max_in_calls,
            }
        )
    return rows


def merge_service_stats(packed_stats_list: list[dict[str, tuple]]) -> dict[str, ServiceStats]:
    merged: dict[str, ServiceStats] = defaultdict(ServiceStats)
    for packed in packed_stats_list:
        for service, values in packed.items():
            first_seen, last_seen, active, total_in, total_out, nonzero, max_in = values
            stats = ServiceStats(
                first_seen_timestamp_bucket_s=first_seen,
                last_seen_timestamp_bucket_s=last_seen,
                total_active_minutes=active,
                total_in_calls=total_in,
                total_out_calls=total_out,
                nonzero_in_minutes=nonzero,
                max_in_calls=max_in,
            )
            merged[service].merge(stats)
    return merged


def merge_day_summaries(packed_days_list: list[dict[int, dict]]) -> list[dict]:
    merged: dict[int, dict] = {}
    for packed in packed_days_list:
        for day_idx, summary in packed.items():
            target = merged.setdefault(
                day_idx,
                {"start_time_s": summary["start_time_s"], "end_time_s": summary["end_time_s"], "services": set()},
            )
            target["start_time_s"] = min(target["start_time_s"], summary["start_time_s"])
            target["end_time_s"] = max(target["end_time_s"], summary["end_time_s"])
            target["services"].update(summary["services"])
    rows = []
    for day_idx in sorted(merged):
        rows.append(
            {
                "day": day_label(day_idx),
                "day_index": day_idx,
                "start_time_s": merged[day_idx]["start_time_s"],
                "end_time_s": merged[day_idx]["end_time_s"],
                "service_count": len(merged[day_idx]["services"]),
            }
        )
    return rows


def main() -> None:
    args = parse_args()
    callgraph_dir = args.trace_root / "data" / "CallGraph"
    if not callgraph_dir.exists():
        raise FileNotFoundError(f"CallGraph directory not found: {callgraph_dir}")

    files = sorted(callgraph_dir.glob("CallGraph_*.csv"), key=numeric_suffix)
    if args.max_files is not None:
        files = files[: args.max_files]
    if not files:
        raise RuntimeError("No CallGraph files found.")

    run_dir = args.output_root / "tables" / f"run_id={args.run_id}"
    if args.clean_output and run_dir.exists():
        shutil.rmtree(run_dir)

    file_chunks = chunk_list(files, args.workers)
    total_chunks = len(file_chunks)
    total_files = len(files)

    with ProcessPoolExecutor(max_workers=len(file_chunks)) as executor:
        service_futures = {
            executor.submit(collect_services_from_files, chunk): len(chunk) for chunk in file_chunks
        }
        services: set[str] = set()
        completed_chunks = 0
        completed_files = 0
        stage_started_at = time.monotonic()
        print_progress(
            stage="collect-services",
            completed_chunks=0,
            total_chunks=total_chunks,
            completed_files=0,
            total_files=total_files,
            started_at=stage_started_at,
        )
        for future in as_completed(service_futures):
            services.update(future.result())
            completed_chunks += 1
            completed_files += service_futures[future]
            print_progress(
                stage="collect-services",
                completed_chunks=completed_chunks,
                total_chunks=total_chunks,
                completed_files=completed_files,
                total_files=total_files,
                started_at=stage_started_at,
                final=completed_chunks == total_chunks,
            )

    if not services:
        raise RuntimeError("No services found in CallGraph input.")
    service_idx_map = {service: idx for idx, service in enumerate(sorted(services))}

    with ProcessPoolExecutor(max_workers=len(file_chunks)) as executor:
        futures = {
            executor.submit(
                process_file_chunk,
                files=chunk,
                run_dir=run_dir,
                run_id=args.run_id,
                scenario_id=args.scenario_id,
                service_idx_map=service_idx_map,
            ): len(chunk)
            for chunk in file_chunks
        }
        packed_stats_list = []
        packed_days_list = []
        completed_chunks = 0
        completed_files = 0
        stage_started_at = time.monotonic()
        print_progress(
            stage="process-chunks",
            completed_chunks=0,
            total_chunks=total_chunks,
            completed_files=0,
            total_files=total_files,
            started_at=stage_started_at,
        )
        for future in as_completed(futures):
            packed_stats, packed_days = future.result()
            packed_stats_list.append(packed_stats)
            packed_days_list.append(packed_days)
            completed_chunks += 1
            completed_files += futures[future]
            print_progress(
                stage="process-chunks",
                completed_chunks=completed_chunks,
                total_chunks=total_chunks,
                completed_files=completed_files,
                total_files=total_files,
                started_at=stage_started_at,
                final=completed_chunks == total_chunks,
            )

    service_stats = merge_service_stats(packed_stats_list)
    day_rows = merge_day_summaries(packed_days_list)

    write_csv(
        run_dir / "service_metadata" / "service_metadata.csv",
        [
            "service",
            "service_idx",
            "first_seen_timestamp_bucket_s",
            "last_seen_timestamp_bucket_s",
            "total_active_minutes",
            "nonzero_in_minutes",
            "total_in_calls",
            "total_out_calls",
            "avg_in_calls",
            "max_in_calls",
        ],
        build_service_metadata_rows(service_idx_map, service_stats),
    )
    write_csv(
        run_dir / "run_metadata" / "run_metadata.csv",
        [
            "run_id",
            "scenario_id",
            "app_name",
            "start_time_s",
            "end_time_s",
            "bucket_seconds",
            "service_count",
            "day",
            "day_index",
        ],
        [
            {
                "run_id": args.run_id,
                "scenario_id": args.scenario_id,
                "app_name": args.app_name,
                "start_time_s": row["start_time_s"],
                "end_time_s": row["end_time_s"],
                "bucket_seconds": 60,
                "service_count": row["service_count"],
                "day": row["day"],
                "day_index": row["day_index"],
            }
            for row in day_rows
        ],
    )

    print(
        f"[OK] services={len(service_idx_map)} files={len(files)} "
        f"workers={len(file_chunks)} output={run_dir}"
    )


if __name__ == "__main__":
    main()
