#!/usr/bin/env python3
# scripts/exemples/convert_mod.py
"""RAPID MOD to TrajCenter v2.4 conversion demonstration.

> **Author**: Clément RACINET

This script converts a RAPID ``.mod`` file containing ABB MoveL/MoveJ/MoveC
instructions into a TrajCenter v2.4 ``.trajcenter`` archive and validates
the save/load roundtrip.

Run:
    python scripts/exemples/convert_mod.py
"""

from __future__ import annotations

from pathlib import Path

from _demo_utils import active_external_axes, assert_same_geometry, point_count

from trajcenter.convert.mod_converter import ModConverter
from trajcenter.core.trajectory import Trajectory

SOURCE_FILE = Path("trajectory_files/mod_exemple.mod")
OUTPUT_DIR = Path("trajectory_store")


def main() -> None:
    """Run RAPID MOD conversion demonstration.

    ABB Route:
        N/A — local RAPID module parsing demonstration.

    ABB Constraints:
        No ABB controller access. Inactive external axes encoded as RAPID
        ``9E9`` are not stored as active DataFrame columns in ``.trajcenter``.

    Args:
        None.

    Returns:
        None.

    Raises:
        FileNotFoundError: If the source ``.mod`` file does not exist.
        AssertionError: If the save/load roundtrip validation fails.
        ValueError: If the source file cannot be converted.

    Example:
        ::

            main()
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not SOURCE_FILE.exists():
        raise FileNotFoundError(f"MOD source not found: {SOURCE_FILE}")

    traj = ModConverter().convert(SOURCE_FILE)

    print("=" * 72)
    print("TrajCenter v2.4 — RAPID MOD conversion")
    print("=" * 72)
    print(traj)
    print(f"  name          : {traj.meta.name}")
    print(f"  points        : {point_count(traj)}")
    print(f"  external axes : {active_external_axes(traj)}")
    print(f"  autocompleted : {traj.meta.autocompleted}")
    print(f"  columns       : {list(traj.points.columns)}")
    print()
    print(traj.points.head(5).to_string(index=False))
    print()

    saved = traj.save(OUTPUT_DIR / f"{traj.meta.name}.trajcenter")
    loaded = Trajectory.load(saved)

    assert_same_geometry(traj, loaded)

    print(f"Saved and validated → {saved}")
    print("OK — RAPID MOD conversion validated.")


if __name__ == "__main__":
    main()
