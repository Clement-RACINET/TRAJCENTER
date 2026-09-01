#!/usr/bin/env python3
# scripts/exemples/_demo_utils.py
"""Shared helpers for TrajCenter v2.4 demonstration scripts.

> **Author**: Clément RACINET
"""

from __future__ import annotations

from trajcenter.core.trajectory import EXTERNAL_AXIS_COLUMNS, Trajectory


def point_count(traj: Trajectory) -> int:
    """Return trajectory point count.

    ABB Route:
        N/A — local demonstration helper.

    ABB Constraints:
        No ABB controller access.

    Args:
        traj: Trajectory instance.

    Returns:
        Number of points.

    Raises:
        TypeError: If the runtime attribute exists but is not an integer.

    Example:
        ::

            count = point_count(traj)
    """
    value = getattr(traj, "point_count", None)
    if value is None:
        return len(traj.points)
    if not isinstance(value, int):
        raise TypeError(f"Invalid point_count attribute type: {type(value)!r}")
    return value


def active_external_axes(traj: Trajectory) -> list[str]:
    """Return active external axis column names.

    ABB Route:
        N/A — local demonstration helper.

    ABB Constraints:
        No ABB controller access. Inactive RAPID sentinel ``9E9`` is not
        stored in ``.trajcenter`` files.

    Args:
        traj: Trajectory instance.

    Returns:
        Active external axis columns.

    Raises:
        TypeError: If the runtime attribute is neither absent nor a list.

    Example:
        ::

            axes = active_external_axes(traj)
    """
    value = getattr(traj, "active_external_axes", None)
    if value is None:
        return [
            column for column in EXTERNAL_AXIS_COLUMNS if column in traj.points.columns
        ]
    if not isinstance(value, list):
        raise TypeError(f"Invalid active_external_axes type: {type(value)!r}")
    return [str(item) for item in value]


def preview_columns(traj: Trajectory, columns: list[str]) -> list[str]:
    """Return available columns for preview display.

    ABB Route:
        N/A — local display helper.

    ABB Constraints:
        No ABB controller access.

    Args:
        traj: Trajectory instance.
        columns: Preferred columns.

    Returns:
        Existing columns only.

    Example:
        ::

            cols = preview_columns(traj, ["x", "y", "z"])
    """
    return [column for column in columns if column in traj.points.columns]


def assert_same_geometry(left: Trajectory, right: Trajectory) -> None:
    """Assert basic geometry roundtrip invariants between two trajectories.

    ABB Route:
        N/A — local validation helper.

    ABB Constraints:
        No ABB controller access.

    Args:
        left: Reference trajectory.
        right: Reloaded or reconverted trajectory.

    Returns:
        None.

    Raises:
        AssertionError: If a basic invariant differs.

    Example:
        ::

            assert_same_geometry(original, loaded)
    """
    assert point_count(right) == point_count(left)
    assert right.meta.name == left.meta.name
    assert list(right.points.columns) == list(left.points.columns)
