#!/usr/bin/env python3
# scripts/benchmark_rws_writer.py
"""Benchmark TrajCenter RWS trajectory writer.

This script measures the time required to write synthetic resolved trajectories
to the ABB RAPID TRAJCENTER module through Robot Web Services.

It benchmarks the writer layer directly:

    ResolvedTrajectory -> write_resolved_trajectory -> RWS writes

This intentionally bypasses:
    - local .trajcenter loading;
    - robot context reads;
    - resolver;
    - supervisor subscriptions;
    - RAPID request flags.

The goal is to isolate transfer/write time as a function of point count.
"""

from __future__ import annotations

import argparse
import asyncio
import statistics
from dataclasses import asdict, dataclass
from pathlib import Path
from time import perf_counter

import pandas as pd
from abb_rws_client_python_rw6 import RWSClient, configure_logging, load_env
from abb_rws_client_python_rw6.core.exceptions import RWSError

from trajcenter.robot.constants import DEFAULT_TASK, TRAJCENTER_MODULE
from trajcenter.robot.models import (
    ResolvedPoint,
    ResolvedProcessParam,
    ResolvedProcessParamSet,
    ResolvedRobTarget,
    ResolvedTrajectory,
)
from trajcenter.robot.writer import (
    MAX_PROCESS_PARAM_PER_SET,
    write_resolved_trajectory,
)


@dataclass(frozen=True)
class BenchmarkSample:
    """One benchmark measurement."""

    points: int
    process_sets: int
    repetition: int
    duration_s: float
    points_per_s: float
    estimated_variables: int
    success: bool
    error: str


@dataclass(frozen=True)
class BenchmarkSummary:
    """Aggregated benchmark result for one point count and process set count."""

    points: int
    process_sets: int
    repetitions: int
    success_count: int
    error_count: int
    min_s: float
    mean_s: float
    median_s: float
    max_s: float
    stdev_s: float
    mean_points_per_s: float
    estimated_variables: int


def make_robtarget(index: int) -> ResolvedRobTarget:
    """Build one deterministic synthetic robtarget."""
    return ResolvedRobTarget(
        x=float(index),
        y=0.0,
        z=500.0,
        q1=1.0,
        q2=0.0,
        q3=0.0,
        q4=0.0,
        cf1=0,
        cf4=0,
        cf6=0,
        cfx=0,
        eax=(None, None, None, None, None, None),
    )


def make_point(index: int, process_param_index: int = 0) -> ResolvedPoint:
    """Build one deterministic resolved point."""
    return ResolvedPoint(
        move_type=0,
        robtarget=make_robtarget(index),
        tcp_speed=500.0,
        zone_type=10,
        read_confs=True,
        tool_index=1,
        wobj_index=1,
        process_param_index=process_param_index,
    )


def make_process_param_set(index: int) -> ResolvedProcessParamSet:
    """Build one synthetic process parameter set with exactly 10 slots."""
    params = tuple(
        ResolvedProcessParam(
            name=f"p{slot_index}",
            value=float(index * 100 + slot_index),
        )
        for slot_index in range(1, MAX_PROCESS_PARAM_PER_SET + 1)
    )

    return ResolvedProcessParamSet(index=index, params=params)  # type: ignore[arg-type]


def make_trajectory(
    *,
    points: int,
    process_sets: int,
    name: str,
) -> ResolvedTrajectory:
    """Build one synthetic resolved trajectory."""
    if points < 1:
        raise ValueError("points must be >= 1")
    if process_sets < 0:
        raise ValueError("process_sets must be >= 0")

    param_sets = tuple(
        make_process_param_set(index) for index in range(1, process_sets + 1)
    )

    resolved_points: list[ResolvedPoint] = []
    for i in range(1, points + 1):
        if process_sets > 0:
            process_index = ((i - 1) % process_sets) + 1
        else:
            process_index = 0

        resolved_points.append(
            make_point(
                index=i,
                process_param_index=process_index,
            )
        )

    return ResolvedTrajectory(
        name=name,
        process_type=1 if process_sets > 0 else 0,
        points=tuple(resolved_points),
        process_param_sets=param_sets,
    )


def estimate_variables(points: int, process_sets: int) -> int:
    """Estimate number of RAPID symbol writes performed by writer.

    Current writer phases:
        start:
            trajReady
            transferError
            lastErrorCode
            lastError
            transferProgress
            nbLoadedTrajPoints
            = 6

        payload:
            process_sets * 10 processParams
            points trajData
            nbLoadedTrajPoints
            = process_sets * 10 + points + 1

        finish:
            transferProgress
            lastErrorCode
            lastError
            transferError
            trajReady
            sendTrajRequest
            = 6
    """
    return 6 + (process_sets * MAX_PROCESS_PARAM_PER_SET + points + 1) + 6


async def run_one_sample(
    *,
    client: RWSClient,
    points: int,
    process_sets: int,
    repetition: int,
    task: str,
    module: str,
    mastership_retries: int,
) -> BenchmarkSample:
    """Run one benchmark sample."""
    trajectory = make_trajectory(
        points=points,
        process_sets=process_sets,
        name=f"bench_{points}_pts_{process_sets}_proc_rep_{repetition}",
    )

    t0 = perf_counter()
    try:
        await write_resolved_trajectory(
            client,
            trajectory,
            task=task,
            module=module,
            mastership_retries=mastership_retries,
            progress_step_percent=0,
        )
        t1 = perf_counter()

        duration_s = t1 - t0
        return BenchmarkSample(
            points=points,
            process_sets=process_sets,
            repetition=repetition,
            duration_s=duration_s,
            points_per_s=points / duration_s if duration_s > 0 else 0.0,
            estimated_variables=estimate_variables(points, process_sets),
            success=True,
            error="",
        )

    except (RWSError, ValueError, RuntimeError, OSError) as exc:
        t1 = perf_counter()
        return BenchmarkSample(
            points=points,
            process_sets=process_sets,
            repetition=repetition,
            duration_s=t1 - t0,
            points_per_s=0.0,
            estimated_variables=estimate_variables(points, process_sets),
            success=False,
            error=f"{type(exc).__name__}: {exc}",
        )


def summarize(samples: list[BenchmarkSample]) -> list[BenchmarkSummary]:
    """Aggregate successful samples."""
    groups: dict[tuple[int, int], list[BenchmarkSample]] = {}

    for sample in samples:
        groups.setdefault((sample.points, sample.process_sets), []).append(sample)

    summaries: list[BenchmarkSummary] = []

    for (points, process_sets), group in sorted(groups.items()):
        successful = [sample for sample in group if sample.success]
        durations = [sample.duration_s for sample in successful]
        speeds = [sample.points_per_s for sample in successful]

        if durations:
            stdev_s = statistics.stdev(durations) if len(durations) > 1 else 0.0
            summaries.append(
                BenchmarkSummary(
                    points=points,
                    process_sets=process_sets,
                    repetitions=len(group),
                    success_count=len(successful),
                    error_count=len(group) - len(successful),
                    min_s=min(durations),
                    mean_s=statistics.mean(durations),
                    median_s=statistics.median(durations),
                    max_s=max(durations),
                    stdev_s=stdev_s,
                    mean_points_per_s=statistics.mean(speeds),
                    estimated_variables=estimate_variables(points, process_sets),
                )
            )
        else:
            summaries.append(
                BenchmarkSummary(
                    points=points,
                    process_sets=process_sets,
                    repetitions=len(group),
                    success_count=0,
                    error_count=len(group),
                    min_s=0.0,
                    mean_s=0.0,
                    median_s=0.0,
                    max_s=0.0,
                    stdev_s=0.0,
                    mean_points_per_s=0.0,
                    estimated_variables=estimate_variables(points, process_sets),
                )
            )

    return summaries


def parse_points(text: str) -> list[int]:
    """Parse comma-separated point counts."""
    values = [int(part.strip()) for part in text.split(",") if part.strip()]
    if not values:
        raise argparse.ArgumentTypeError("at least one point count is required")
    if any(value < 1 for value in values):
        raise argparse.ArgumentTypeError("point counts must be >= 1")
    return values


async def async_main(args: argparse.Namespace) -> int:
    """Run benchmark."""
    load_env(args.env_file, override=args.env_override)
    configure_logging(args.log_level)

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    samples: list[BenchmarkSample] = []

    async with RWSClient(
        host=args.host,
        username=args.username,
        password=args.password,
        port=args.port,
        timeout=args.timeout,
    ) as client:
        for process_sets in args.process_sets:
            for points in args.points:
                for repetition in range(1, args.repetitions + 1):
                    print(
                        f"Benchmark: points={points}, "
                        f"process_sets={process_sets}, "
                        f"repetition={repetition}/{args.repetitions}"
                    )

                    sample = await run_one_sample(
                        client=client,
                        points=points,
                        process_sets=process_sets,
                        repetition=repetition,
                        task=args.task,
                        module=args.module,
                        mastership_retries=args.mastership_retries,
                    )
                    samples.append(sample)

                    if sample.success:
                        print(
                            f"  OK: {sample.duration_s:.3f}s "
                            f"({sample.points_per_s:.1f} points/s, "
                            f"{sample.estimated_variables} variables)"
                        )
                    else:
                        print(f"  ERROR after {sample.duration_s:.3f}s: {sample.error}")

                    if args.cooldown_s > 0:
                        await asyncio.sleep(args.cooldown_s)

    summaries = summarize(samples)

    samples_df = pd.DataFrame(asdict(sample) for sample in samples)
    summary_df = pd.DataFrame(asdict(summary) for summary in summaries)

    csv_path = output_dir / args.csv_name
    xlsx_path = output_dir / args.xlsx_name

    samples_df.to_csv(csv_path, index=False, encoding="utf-8")

    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        summary_df.to_excel(writer, sheet_name="summary", index=False)
        samples_df.to_excel(writer, sheet_name="samples", index=False)

    print()
    print(f"CSV written:   {csv_path}")
    print(f"Excel written: {xlsx_path}")

    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build command-line parser."""
    parser = argparse.ArgumentParser(
        description="Benchmark TrajCenter RWS writer transfer time.",
    )

    parser.add_argument(
        "--points",
        type=parse_points,
        default=parse_points("1,2,6,10,20,50,100,200,500,1000"),
        help="Comma-separated point counts, e.g. 1,6,10,50,100",
    )
    parser.add_argument(
        "--process-sets",
        type=int,
        nargs="+",
        default=[0],
        help="Process parameter set counts to test, e.g. 0 1 5",
    )
    parser.add_argument(
        "--repetitions",
        type=int,
        default=3,
        help="Number of repetitions per point count.",
    )
    parser.add_argument(
        "--cooldown-s",
        type=float,
        default=0.2,
        help="Delay between samples.",
    )

    parser.add_argument("--task", default=DEFAULT_TASK)
    parser.add_argument("--module", default=TRAJCENTER_MODULE)
    parser.add_argument("--mastership-retries", type=int, default=3)

    parser.add_argument("--env-file", type=Path, default=None)
    parser.add_argument("--env-override", action="store_true")
    parser.add_argument("--host", default=None)
    parser.add_argument("--username", default=None)
    parser.add_argument("--password", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--timeout", type=float, default=None)
    parser.add_argument("--log-level", default="WARNING")

    parser.add_argument(
        "--output-dir",
        default="trajectory_exports",
        help="Directory where CSV/XLSX benchmark files are written.",
    )
    parser.add_argument(
        "--csv-name",
        default="rws_writer_benchmark.csv",
    )
    parser.add_argument(
        "--xlsx-name",
        default="rws_writer_benchmark.xlsx",
    )

    return parser


def main() -> int:
    """CLI entry point."""
    parser = build_parser()
    args = parser.parse_args()

    if args.repetitions < 1:
        parser.error("--repetitions must be >= 1")

    if any(value < 0 for value in args.process_sets):
        parser.error("--process-sets values must be >= 0")

    return asyncio.run(async_main(args))


if __name__ == "__main__":
    raise SystemExit(main())
