#!/usr/bin/env python3
# scripts/exemples/convert_apt_example.py
"""APT source to TrajCenter v2.4 conversion demonstration.

Author: Clement RACINET

This script demonstrates APT source conversion and validates local
``.trajcenter`` save/load roundtrip.

Run:
    python scripts/exemples/convert_apt_example.py
"""

from __future__ import annotations

from pathlib import Path

from _demo_utils import (
    active_external_axes,
    assert_same_geometry,
    point_count,
    preview_columns,
)
from trajcenter.converter.apt_converter import AptConverter
from trajcenter.core.trajectory import Trajectory


SOURCE = Path("trajectory_files/PrepaFlans_Pointage.aptsource")
OUTPUT_DIR = Path("trajectory_store")


def print_summary(title: str, traj: Trajectory) -> None:
    """Print a compact trajectory summary.

    ABB Route:
        N/A — local conversion demonstration.

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

            print_summary("APT", traj)
    """
    columns = preview_columns(
        traj,
        [
            "x",
            "y",
            "z",
            "q1",
            "q2",
            "q3",
            "q4",
            "move_type",
            "speed",
            "zone",
            "cf1",
            "cf4",
            "cf6",
            "cfx",
        ],
    )

    print("=" * 72)
    print(title)
    print("=" * 72)
    print(traj)
    print(f"  points        : {point_count(traj)}")
    print(f"  external axes : {active_external_axes(traj)}")
    print(f"  autocompleted : {traj.meta.autocompleted}")
    print(f"  columns       : {list(traj.points.columns)}")
    print()
    print(traj.points[columns].head(5).to_string(index=False))
    print()


def assert_valid_roundtrip(traj: Trajectory, path: Path) -> None:
    """Validate save/load roundtrip for a trajectory.

    ABB Route:
        N/A — local archive validation.

    ABB Constraints:
        No ABB controller access.

    Args:
        traj: Source trajectory.
        path: Destination archive path.

    Returns:
        None.

    Raises:
        AssertionError: If roundtrip validation fails.
        OSError: If the archive cannot be written or read.

    Example:
        ::

            assert_valid_roundtrip(traj, Path("out.trajcenter"))
    """
    saved = traj.save(path)
    loaded = Trajectory.load(saved)

    assert_same_geometry(traj, loaded)

    print(f"Roundtrip OK → {saved}")
    print()


def main() -> None:
    """Run APT conversion demonstration scenarios.

    ABB Route:
        N/A — local APT parsing demonstration.

    ABB Constraints:
        No ABB controller access.

    Args:
        None.

    Returns:
        None.

    Raises:
        FileNotFoundError: If the APT source file does not exist.
        AssertionError: If a conversion roundtrip check fails.
        ValueError: If the source cannot be converted.

    Example:
        ::

            main()
    """
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not SOURCE.exists():
        raise FileNotFoundError(f"APT source not found: {SOURCE}")

    standard = AptConverter().convert(SOURCE)
    print_summary("Case 1 — APT standard conversion", standard)
    assert_valid_roundtrip(
        standard,
        OUTPUT_DIR / f"{standard.meta.name}.trajcenter",
    )

    transformed = AptConverter(apply_catia_transform=True).convert(SOURCE)
    print_summary("Case 2 — APT with CATIA transform", transformed)
    assert_valid_roundtrip(
        transformed,
        OUTPUT_DIR / f"{transformed.meta.name}_transformed.trajcenter",
    )

    raw_pt = standard.points.iloc[0]
    transformed_pt = transformed.points.iloc[0]

    print("First point comparison:")
    print(
        f"  raw         : x={raw_pt['x']:.3f}, y={raw_pt['y']:.3f}, z={raw_pt['z']:.3f}"
    )
    print(
        "  transformed : "
        f"x={transformed_pt['x']:.3f}, "
        f"y={transformed_pt['y']:.3f}, "
        f"z={transformed_pt['z']:.3f}"
    )
    print()

    print("OK — APT conversion scenarios validated.")


if __name__ == "__main__":
    main()
