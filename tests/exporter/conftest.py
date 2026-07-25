#!/usr/bin/env python3
# tests/exporter/conftest.py
"""Shared fixtures for exporter tests.

> **Author**: Clément RACINET

Provides ready-to-use v2 ``Trajectory`` objects built directly without
going through a converter.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd
import pytest

from trajcenter.core.trajectory import SourceFormat, Trajectory, TrajectoryMeta


def _make_traj(
    name: str,
    rows: list[dict[str, Any]],
    robot_model: str | None = None,
    extra: dict[str, str | int | float | bool] | None = None,
) -> Trajectory:
    """Build a test Trajectory directly from row dictionaries.

    ABB Route:
        N/A — test fixture only.

    ABB Constraints:
        No ABB controller access.

    Args:
        name: Trajectory name.
        rows: List of point rows.
        robot_model: Optional robot model stored in metadata.
        extra: Optional extra metadata.

    Returns:
        Constructed trajectory.

    Raises:
        pydantic.ValidationError: If the trajectory is invalid.

    Example:
        ::

            traj = _make_traj("sample", [{"x": 0.0, "y": 0.0, "z": 0.0}])
    """
    return Trajectory(
        meta=TrajectoryMeta(
            name=name,
            source_file=f"{name}.trajcenter",
            source_format=SourceFormat.TRAJCENTER,
            robot_model=robot_model,
            extra=extra or {},
            created_at=datetime(2026, 7, 8, 12, 0, 0, tzinfo=timezone.utc),
        ),
        points=pd.DataFrame(rows),
    )


@pytest.fixture
def traj_basic() -> Trajectory:
    """Return a basic v2 trajectory with all common columns present."""
    return _make_traj(
        name="traj_basic",
        rows=[
            {
                "x": 0.0,
                "y": 0.0,
                "z": 0.0,
                "q1": 1.0,
                "q2": 0.0,
                "q3": 0.0,
                "q4": 0.0,
                "cf1": 0,
                "cf4": 0,
                "cf6": 0,
                "cfx": 0,
                "move_type": "MoveL",
                "tcp_speed": 500.0,
                "zone_type": 10,
                "tool_name": "tool0",
                "wobj_name": "wobj0",
            },
            {
                "x": 100.0,
                "y": 0.0,
                "z": 0.0,
                "q1": 1.0,
                "q2": 0.0,
                "q3": 0.0,
                "q4": 0.0,
                "cf1": 0,
                "cf4": 0,
                "cf6": 0,
                "cfx": 0,
                "move_type": "MoveJ",
                "tcp_speed": 250.5,
                "zone_type": 5,
                "tool_name": "tool0",
                "wobj_name": "wobj0",
            },
            {
                "x": 200.0,
                "y": 50.0,
                "z": 10.0,
                "q1": 1.0,
                "q2": 0.0,
                "q3": 0.0,
                "q4": 0.0,
                "cf1": 0,
                "cf4": 0,
                "cf6": 0,
                "cfx": 0,
                "move_type": "MoveL",
                "tcp_speed": 500.0,
                "zone_type": 255,
                "tool_name": "tool0",
                "wobj_name": "wobj0",
            },
        ],
    )


@pytest.fixture
def traj_multi_names() -> Trajectory:
    """Return a trajectory with multiple inline tool and wobj names."""
    return _make_traj(
        name="traj_multi_names",
        rows=[
            {
                "x": 0.0,
                "y": 0.0,
                "z": 0.0,
                "q1": 1.0,
                "q2": 0.0,
                "q3": 0.0,
                "q4": 0.0,
                "move_type": "MoveL",
                "tcp_speed": 500.0,
                "zone_type": 10,
                "tool_name": "Tool_A",
                "wobj_name": "Wobj_A",
            },
            {
                "x": 100.0,
                "y": 0.0,
                "z": 0.0,
                "q1": 1.0,
                "q2": 0.0,
                "q3": 0.0,
                "q4": 0.0,
                "move_type": "MoveJ",
                "tcp_speed": 250.0,
                "zone_type": 5,
                "tool_name": "Tool_B",
                "wobj_name": "Wobj_B",
            },
        ],
    )


@pytest.fixture
def traj_with_meta() -> Trajectory:
    """Return a trajectory with robot model and extra metadata."""
    return _make_traj(
        name="traj_with_meta",
        rows=[
            {
                "x": 1.0,
                "y": 2.0,
                "z": 3.0,
                "q1": 1.0,
                "q2": 0.0,
                "q3": 0.0,
                "q4": 0.0,
                "move_type": "MoveL",
                "tcp_speed": 500.0,
                "zone_type": 10,
                "tool_name": "tool0",
                "wobj_name": "wobj0",
            },
        ],
        robot_model="IRB6700-205/2.80",
        extra={"author": "Jean Dupont", "project": "Soudure_V2"},
    )


@pytest.fixture
def traj_minimal() -> Trajectory:
    """Return a trajectory containing only required geometry columns."""
    return _make_traj(
        name="traj_minimal",
        rows=[
            {
                "x": 1.0,
                "y": 2.0,
                "z": 3.0,
                "q1": 1.0,
                "q2": 0.0,
                "q3": 0.0,
                "q4": 0.0,
            },
        ],
    )


@pytest.fixture
def traj_with_unknown_column() -> Trajectory:
    """Return a trajectory containing one direct unknown point column."""
    return _make_traj(
        name="traj_with_unknown_column",
        rows=[
            {
                "x": 1.0,
                "y": 2.0,
                "z": 3.0,
                "q1": 1.0,
                "q2": 0.0,
                "q3": 0.0,
                "q4": 0.0,
                "operator_comment": "not exported by default",
            },
        ],
    )
