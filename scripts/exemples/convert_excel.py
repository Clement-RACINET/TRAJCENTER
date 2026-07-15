#!/usr/bin/env python3
# scripts/examples/convert_excel_example.py
"""Excel (``.xlsx``) to ``.trajcenter`` conversion example.

Author: Clement RACINET

Demonstrates two conversion scenarios for an Excel workbook:

1. **Single-sheet workbook** — :meth:`~trajcenter.converter.excel_converter.ExcelConverter.convert`.
2. **Multi-sheet workbook** — :meth:`~trajcenter.converter.excel_converter.ExcelConverter.convert_all`.

Edit the variables in the "Configuration" section below, then run
directly::

    python scripts/examples/convert_excel_example.py
"""

from __future__ import annotations

from pathlib import Path

from trajcenter.converter.defaults import ConversionDefaults
from trajcenter.converter.excel_converter import ExcelConverter
from trajcenter.core.trajectory import Trajectory

# ---------------------------------------------------------------------------
# Configuration — adjust to your context
# ---------------------------------------------------------------------------

# Case 1 — single-sheet workbook (XYZ + optional columns)
SOURCE_SINGLE = Path("trajectory_files/trajectoires_mono.xlsx")

# Case 2 — multi-sheet workbook (one trajectory per sheet)
SOURCE_MULTI = Path("trajectory_files/trajectoires_multi.xlsx")

OUTPUT_DIR = Path("trajectory_store")

# Fallback values for columns absent from the Excel file.
# Useful when the workbook contains only XYZ columns
# (quaternions will be filled with the identity orientation).
DEFAULTS = ConversionDefaults(
    move_type="MoveL",
    speed="v10",
    zone="z0",
)

# ---------------------------------------------------------------------------
# Case 1 — single sheet
# ---------------------------------------------------------------------------

print("=" * 60)
print("Case 1 — Single-sheet workbook")
print("=" * 60)

traj: Trajectory = ExcelConverter(defaults=DEFAULTS).convert(SOURCE_SINGLE)

print(traj)
print(f"  tools         : {traj.tools}")
print(f"  wobjs         : {traj.wobjs}")
print(f"  autocompleted : {traj.meta.autocompleted}")
print(f"  is_complete   : {traj.is_complete}")
print()
print(traj.points.head())

dest = traj.save(OUTPUT_DIR / f"{traj.meta.name}.trajcenter")
print(f"\nSaved → {dest}")

# ---------------------------------------------------------------------------
# Case 2 — multi-sheet
# ---------------------------------------------------------------------------

print()
print("=" * 60)
print("Case 2 — Multi-sheet workbook")
print("=" * 60)

trajs: list[Trajectory] = ExcelConverter(defaults=DEFAULTS).convert_all(SOURCE_MULTI)

print(f"{len(trajs)} trajectory/trajectories extracted:\n")

for traj in trajs:
    print(
        f"  [{traj.meta.name}]  {traj.point_count} points  "
        f"| tools={traj.tools}  wobjs={traj.wobjs}"
    )
    dest = traj.save(OUTPUT_DIR / f"{traj.meta.name}.trajcenter")
    print(f"    → Saved: {dest}")
