#!/usr/bin/env python3
# scripts/exemples/convert_excel.py
"""Excel to TrajCenter v2.4 conversion demonstration.

> **Author**: Clément RACINET

This script demonstrates:

1. Single trajectory extraction from an Excel workbook.
2. Multiple trajectory extraction from a multi-sheet Excel workbook.
3. Save/load roundtrip validation for every generated ``.trajcenter`` file.

Run:
    python scripts/exemples/convert_excel.py
"""

from __future__ import annotations

from pathlib import Path

from _demo_utils import assert_same_geometry, point_count

from trajcenter.convert.excel_converter import ExcelConverter
from trajcenter.core.trajectory import Trajectory

SOURCE_SINGLE = Path("trajectory_files/trajectoires_mono.xlsx")
SOURCE_MULTI = Path("trajectory_files/trajectoires_multi.xlsx")
OUTPUT_DIR = Path("trajectory_store")


def print_trajectory_summary(traj: Trajectory) -> None:
    """Print a compact Excel conversion summary.

    ABB Route:
        N/A — local Excel conversion demonstration.

    ABB Constraints:
        No ABB controller access.

    Args:
        traj: Trajectory to display.

    Returns:
        None.

    Example:
        ::

            print_trajectory_summary(traj)
    """
    print(traj)
    print(f"  name          : {traj.meta.name}")
    print(f"  points        : {point_count(traj)}")
    print(f"  autocompleted : {traj.meta.autocompleted}")
    print(f"  columns       : {list(traj.points.columns)}")
    print()
    print(traj.points.head(5).to_string(index=False))
    print()


def save_and_validate(traj: Trajectory, output_dir: Path) -> Path:
    """Save a trajectory and validate the ``.trajcenter`` roundtrip.

    ABB Route:
        N/A — local archive validation.

    ABB Constraints:
        No ABB controller access.

    Args:
        traj: Trajectory to save.
        output_dir: Directory where the archive is written.

    Returns:
        Path to the saved ``.trajcenter`` archive.

    Raises:
        AssertionError: If the loaded archive differs from the source.
        OSError: If the archive cannot be written or read.

    Example:
        ::

            path = save_and_validate(traj, Path("trajectory_store"))
    """
    path = traj.save(output_dir / f"{traj.meta.name}.trajcenter")
    loaded = Trajectory.load(path)

    assert_same_geometry(traj, loaded)

    return path


def main() -> None:
    """Run Excel conversion examples.

    ABB Route:
        N/A — local Excel conversion demonstration.

    ABB Constraints:
        No ABB controller access.

    Args:
        None.

    Returns:
        None.

    Raises:
        FileNotFoundError: If an input workbook does not exist.
        AssertionError: If a save/load check fails.
        ValueError: If a workbook cannot be converted.

    Example:
        ::

            main()
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not SOURCE_SINGLE.exists():
        raise FileNotFoundError(f"Excel source not found: {SOURCE_SINGLE}")
    if not SOURCE_MULTI.exists():
        raise FileNotFoundError(f"Excel source not found: {SOURCE_MULTI}")

    converter = ExcelConverter()

    print("=" * 72)
    print("Case 1 — Excel single-sheet conversion")
    print("=" * 72)

    single = converter.convert(SOURCE_SINGLE)
    print_trajectory_summary(single)
    single_path = save_and_validate(single, OUTPUT_DIR)
    print(f"Saved and validated → {single_path}")
    print()

    print("=" * 72)
    print("Case 2 — Excel multi-sheet conversion")
    print("=" * 72)

    trajectories = converter.convert_all(SOURCE_MULTI)
    print(f"Extracted trajectories: {len(trajectories)}")
    print()

    for traj in trajectories:
        print_trajectory_summary(traj)
        path = save_and_validate(traj, OUTPUT_DIR)
        print(f"Saved and validated → {path}")
        print()

    print("OK — Excel conversion scenarios validated.")


if __name__ == "__main__":
    main()
