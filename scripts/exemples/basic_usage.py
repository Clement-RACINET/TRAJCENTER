#!/usr/bin/env python3
# scripts/exemples/basic_usage.py
"""Basic TrajCenter v2.4 save/load roundtrip example.

Author: Clement RACINET

This script creates a minimal ABB geometry trajectory with one active external
axis, saves it as a ``.trajcenter`` archive, reloads it, and validates data
integrity.

Run:
    python scripts/exemples/basic_usage.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from _demo_utils import active_external_axes, point_count
from trajcenter.core.trajectory import ExternalAxisConfig, Trajectory, TrajectoryMeta


OUTPUT_DIR = Path("trajectory_store")
OUTPUT_FILE = OUTPUT_DIR / "demo_basic_usage.trajcenter"


def build_demo_trajectory() -> Trajectory:
    """Build a minimal demonstration trajectory.

    ABB Route:
        N/A — local TrajCenter v2.4 archive generation.

    ABB Constraints:
        No ABB controller access. External axis inactivity sentinel ``9E9`` is
        not stored in the ``.trajcenter`` file.

    Args:
        None.

    Returns:
        Demonstration trajectory with two points and one active external axis.

    Raises:
        ValueError: If the trajectory data model validation fails.

    Example:
        ::

            traj = build_demo_trajectory()
    """
    points = pd.DataFrame(
        {
            "x": [100.0, 200.0],
            "y": [150.0, 250.0],
            "z": [50.0, 60.0],
            "q1": [1.0, 1.0],
            "q2": [0.0, 0.0],
            "q3": [0.0, 0.0],
            "q4": [0.0, 0.0],
            "eax_a": [45.0, 90.0],
        }
    )

    meta = TrajectoryMeta(
        name="demo_basic_usage",
        robot_model="IRB6700",
        external_axes={
            "eax_a": ExternalAxisConfig(
                axis_type="rotational",
                unit="deg",
                label="Positionneur A",
            )
        },
    )

    return Trajectory(meta=meta, points=points)


def main() -> None:
    """Run the basic save/load roundtrip demonstration.

    ABB Route:
        N/A — local file demonstration.

    ABB Constraints:
        No ABB controller access.

    Args:
        None.

    Returns:
        None.

    Raises:
        AssertionError: If the roundtrip integrity checks fail.
        OSError: If the output archive cannot be written or read.

    Example:
        ::

            main()
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    traj = build_demo_trajectory()
    saved = traj.save(OUTPUT_FILE)
    loaded = Trajectory.load(saved)

    assert point_count(loaded) == 2
    assert loaded.meta.name == "demo_basic_usage"
    assert "eax_a" in active_external_axes(loaded)
    assert list(loaded.points.columns) == list(traj.points.columns)

    print("=" * 72)
    print("TrajCenter v2.4 — basic save/load roundtrip")
    print("=" * 72)
    print(loaded)
    print()
    print(f"Saved archive : {saved}")
    print(f"Point count   : {point_count(loaded)}")
    print(f"External axes : {active_external_axes(loaded)}")
    print(f"Columns       : {list(loaded.points.columns)}")
    print()
    print(loaded.points.to_string(index=False))
    print()
    print("OK — roundtrip validated.")


if __name__ == "__main__":
    main()
