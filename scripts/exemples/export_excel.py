#!/usr/bin/env python3
# scripts/exemples/export_excel.py
"""TrajCenter v2.4 Excel export demonstration.

Author: Clement RACINET

This script demonstrates:

1. Loading a ``.trajcenter`` archive and exporting it to Excel.
2. Converting an Excel source and re-exporting it to Excel.
3. Re-reading the exported Excel files to validate roundtrip compatibility.

Run:
    python scripts/exemples/export_excel.py
"""

from __future__ import annotations

from pathlib import Path

from _demo_utils import point_count
from trajcenter.converter.excel_converter import ExcelConverter
from trajcenter.core.trajectory import Trajectory
from trajcenter.exporter.excel_exporter import ExcelExporter
from trajcenter.exporter.options import ExportOptions


SOURCE_TRAJCENTER = Path("trajectory_store/test_basic.trajcenter")
SOURCE_XLSX = Path("trajectory_files/test_basic.xlsx")
OUTPUT_DIR = Path("trajectory_exports")

EXPORT_OPTIONS = ExportOptions(
    float_precision=6,
    include_meta=True,
)


def export_and_validate(traj: Trajectory, output_dir: Path) -> Path:
    """Export a trajectory to Excel and validate it can be read again.

    ABB Route:
        N/A — local Excel export validation.

    ABB Constraints:
        No ABB controller access.

    Args:
        traj: Trajectory to export.
        output_dir: Directory where the Excel workbook is written.

    Returns:
        Path to the exported workbook.

    Raises:
        AssertionError: If the reloaded Excel trajectory is inconsistent.
        OSError: If the workbook cannot be written or read.
        ValueError: If the exported workbook cannot be converted.

    Example:
        ::

            path = export_and_validate(traj, Path("trajectory_exports"))
    """
    exported = ExcelExporter(options=EXPORT_OPTIONS).export(traj, output_dir)
    reloaded = ExcelConverter().convert(exported)

    assert point_count(reloaded) == point_count(traj)

    return exported


def print_summary(title: str, traj: Trajectory) -> None:
    """Print an export demonstration summary.

    ABB Route:
        N/A — local export demonstration.

    ABB Constraints:
        No ABB controller access.

    Args:
        title: Section title.
        traj: Trajectory to display.

    Returns:
        None.

    Raises:
        None.

    Example:
        ::

            print_summary("Export", traj)
    """
    print("=" * 72)
    print(title)
    print("=" * 72)
    print(traj)
    print(f"  name          : {traj.meta.name}")
    print(f"  points        : {point_count(traj)}")
    print(f"  autocompleted : {traj.meta.autocompleted}")
    print(f"  columns       : {list(traj.points.columns)}")
    print()
    print(traj.points.head(5).to_string(index=False))
    print()


def main() -> None:
    """Run Excel export demonstrations.

    ABB Route:
        N/A — local Excel export demonstration.

    ABB Constraints:
        No ABB controller access.

    Args:
        None.

    Returns:
        None.

    Raises:
        FileNotFoundError: If an input file is missing.
        AssertionError: If an export validation fails.
        ValueError: If conversion or export preparation fails.

    Example:
        ::

            main()
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not SOURCE_TRAJCENTER.exists():
        raise FileNotFoundError(f"TrajCenter archive not found: {SOURCE_TRAJCENTER}")
    if not SOURCE_XLSX.exists():
        raise FileNotFoundError(f"Excel source not found: {SOURCE_XLSX}")

    from_archive = Trajectory.load(SOURCE_TRAJCENTER)
    print_summary("Case 1 — loaded .trajcenter archive", from_archive)

    exported_from_archive = export_and_validate(from_archive, OUTPUT_DIR)
    print(f"Exported and validated → {exported_from_archive}")
    print()

    from_excel = ExcelConverter().convert(SOURCE_XLSX)
    print_summary("Case 2 — converted Excel source", from_excel)

    reexported = export_and_validate(from_excel, OUTPUT_DIR)
    print(f"Re-exported and validated → {reexported}")
    print()

    print("OK — Excel export scenarios validated.")


if __name__ == "__main__":
    main()
