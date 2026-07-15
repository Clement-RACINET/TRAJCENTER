#!/usr/bin/env python3
# scripts/examples/convert_mod_example.py
"""Minimal RAPID ``.mod`` to ``.trajcenter`` conversion example.

Author: Clement RACINET

Edit the variables in the "Configuration" section below, then run
directly::

    python scripts/examples/convert_mod_example.py
"""

from __future__ import annotations

from pathlib import Path

from trajcenter.converter.defaults import ConversionDefaults
from trajcenter.converter.mod_converter import ModConverter
from trajcenter.core.trajectory import Trajectory

# ---------------------------------------------------------------------------
# Configuration — adjust to your context
# ---------------------------------------------------------------------------

SOURCE_FILE = Path("trajectory_files/mod_exemple.mod")
OUTPUT_DIR = Path("trajectory_store")

# Fallback values for columns absent from the .mod file
# (e.g. "speed" is a RAPID variable → will be autocompleted)
DEFAULTS = ConversionDefaults(
    speed="v500",
    zone="z0",
    move_type="MoveL",
)

# ---------------------------------------------------------------------------
# Conversion
# ---------------------------------------------------------------------------

traj: Trajectory = ModConverter(defaults=DEFAULTS).convert(SOURCE_FILE)

print(traj)
print(f"  tools          : {traj.tools}")
print(f"  wobjs          : {traj.wobjs}")
print(f"  autocompleted  : {traj.meta.autocompleted}")
print(f"  is_complete    : {traj.is_complete}")
print()
print(traj.points.head())

# ---------------------------------------------------------------------------
# Save
# ---------------------------------------------------------------------------

dest = traj.save(OUTPUT_DIR / f"{traj.meta.name}.trajcenter")
print(f"\nSaved → {dest}")
