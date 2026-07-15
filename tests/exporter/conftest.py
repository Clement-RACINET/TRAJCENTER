#!/usr/bin/env python3
# tests/exporter/conftest.py
"""Shared fixtures for exporter tests.

Author: Clement RACINET

Provides ready-to-use ``Trajectory`` objects built directly without going
through a converter.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest

from trajcenter.core.trajectory import SourceFormat, Trajectory, TrajectoryMeta


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------


def _make_traj(
    name: str,
    rows: list[dict],
    tools: list[str] | None = None,
    wobjs: list[str] | None = None,
    robot_model: str | None = None,
    extra: dict | None = None,
) -> Trajectory:
    """Build a test ``Trajectory`` directly from a list of row dicts.

    Args:
        name: Trajectory name (also used as the source file stem).
        rows: List of dicts, each representing one trajectory point.
        tools: Tool name list. Defaults to ``["tool0"]``.
        wobjs: Work-object name list. Defaults to ``["wobj0"]``.
        robot_model: Optional robot model string stored in metadata.
        extra: Optional extra metadata dict.

    Returns:
        A fully constructed :class:`~trajcenter.core.trajectory.Trajectory`.
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
        tools=tools or ["tool0"],
        wobjs=wobjs or ["wobj0"],
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def traj_basic() -> Trajectory:
    """Minimal trajectory: 3 points, tool0/wobj0, all columns present."""
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
                "speed": "v500",
                "zone": "z10",
                "tool_index": 0,
                "wobj_index": 0,
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
                "speed": "v250",
                "zone": "z5",
                "tool_index": 0,
                "wobj_index": 0,
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
                "speed": "v500",
                "zone": "z0",
                "tool_index": 0,
                "wobj_index": 0,
            },
        ],
    )


@pytest.fixture
def traj_multi_tools() -> Trajectory:
    """Trajectory with 2 tools and 2 wobjs; ``tool_index`` alternates between 0 and 1."""
    return _make_traj(
        name="traj_multi_tools",
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
                "speed": "v500",
                "zone": "z10",
                "tool_index": 0,
                "wobj_index": 0,
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
                "speed": "v250",
                "zone": "z5",
                "tool_index": 1,
                "wobj_index": 1,
            },
        ],
        tools=["Tool_A", "Tool_B"],
        wobjs=["Wobj_A", "Wobj_B"],
    )


@pytest.fixture
def traj_with_meta() -> Trajectory:
    """Trajectory with ``robot_model`` and ``extra{}`` populated."""
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
                "cf1": 0,
                "cf4": 0,
                "cf6": 0,
                "cfx": 0,
                "move_type": "MoveL",
                "speed": "v500",
                "zone": "z10",
                "tool_index": 0,
                "wobj_index": 0,
            },
        ],
        robot_model="IRB6700-205/2.80",
        extra={"author": "Jean Dupont", "project": "Soudure_V2"},
    )


@pytest.fixture
def traj_no_meta() -> Trajectory:
    """Trajectory without ``robot_model`` or ``extra{}`` — tests ``include_meta=False``."""
    return _make_traj(
        name="traj_no_meta",
        rows=[
            {
                "x": 1.0,
                "y": 2.0,
                "z": 3.0,
                "q1": 1.0,
                "q2": 0.0,
                "q3": 0.0,
                "q4": 0.0,
                "cf1": 0,
                "cf4": 0,
                "cf6": 0,
                "cfx": 0,
                "move_type": "MoveL",
                "speed": "v500",
                "zone": "z10",
                "tool_index": 0,
                "wobj_index": 0,
            },
        ],
    )
