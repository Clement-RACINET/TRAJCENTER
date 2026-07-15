#!/usr/bin/env python3
# scripts/examples/export_excel.py
"""Trajectory import and re-export to Excel (``.xlsx``) example.

Author: Clement RACINET

Demonstrates two export scenarios:

1. **Import from ``.trajcenter``** → export to Excel.
2. **Import from ``.xlsx``** → re-export to Excel.

Edit the variables in the "Configuration" section below, then run
directly::

    python scripts/examples/export_excel_example.py
"""

from __future__ import annotations

from pathlib import Path

from trajcenter.converter.excel_converter import ExcelConverter
from trajcenter.core.trajectory import Trajectory
from trajcenter.exporter.excel_exporter import ExcelExporter
from trajcenter.exporter.options import ExportOptions

# ---------------------------------------------------------------------------
# Configuration — adjust to your context
# ---------------------------------------------------------------------------

# Case 1 — source: already converted .trajcenter file
SOURCE_TRAJCENTER = Path("trajectory_store/test_basic.trajcenter")

# Case 2 — source: original Excel file (direct re-export)
SOURCE_XLSX = Path("trajectory_files/test_basic.xlsx")

OUTPUT_DIR = Path("trajectory_exports")

# Export options:
#   float_precision : number of decimal places for XYZ and quaternions
#   include_meta    : adds a "meta" sheet with trajectory metadata
EXPORT_OPTIONS = ExportOptions(
    float_precision=6,
    include_meta=True,
)

# ---------------------------------------------------------------------------
# Case 1 — import .trajcenter → export .xlsx
# ---------------------------------------------------------------------------

print("=" * 60)
print("Case 1 — Import .trajcenter → Export Excel")
print("=" * 60)

traj: Trajectory = Trajectory.load(SOURCE_TRAJCENTER)

print(traj)
print(f"  tools         : {traj.tools}")
print(f"  wobjs         : {traj.wobjs}")
print(f"  autocompleted : {traj.meta.autocompleted}")
print(f"  is_complete   : {traj.is_complete}")
print()
print(traj.points.head())

dest = ExcelExporter(options=EXPORT_OPTIONS).export(traj, OUTPUT_DIR)
print(f"\nExported → {dest}")

# ---------------------------------------------------------------------------
# Case 2 — import .xlsx → re-export .xlsx
# ---------------------------------------------------------------------------

print()
print("=" * 60)
print("Case 2 — Import Excel → Re-export Excel")
print("=" * 60)

traj_from_xlsx: Trajectory = ExcelConverter().convert(SOURCE_XLSX)

print(traj_from_xlsx)
print(f"  tools         : {traj_from_xlsx.tools}")
print(f"  wobjs         : {traj_from_xlsx.wobjs}")
print(f"  autocompleted : {traj_from_xlsx.meta.autocompleted}")
print(f"  is_complete   : {traj_from_xlsx.is_complete}")
print()
print(traj_from_xlsx.points.head())

dest = ExcelExporter(options=EXPORT_OPTIONS).export(traj_from_xlsx, OUTPUT_DIR)
print(f"\nRe-exported → {dest}")
