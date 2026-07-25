#!/usr/bin/env python3
# tests/conftest.py
"""Global fixtures shared across ``converter/``, ``core/`` and ``exporter/``.

> **Author**: Clément RACINET
"""

from __future__ import annotations

import pandas as pd
import pytest

from trajcenter.core.trajectory import (
    Trajectory,
    TrajectoryMeta,
    TrajectoryProcess,
)


@pytest.fixture
def minimal_df() -> pd.DataFrame:
    """Minimal ``DataFrame`` containing only mandatory geometry columns."""
    return pd.DataFrame(
        {
            "x": [100.0, 200.0],
            "y": [150.0, 250.0],
            "z": [50.0, 60.0],
            "q1": [1.0, 1.0],
            "q2": [0.0, 0.0],
            "q3": [0.0, 0.0],
            "q4": [0.0, 0.0],
        }
    )


@pytest.fixture
def complete_df() -> pd.DataFrame:
    """DataFrame with converter-safe columns and send metadata columns."""
    return pd.DataFrame(
        {
            "x": [100.0, 200.0],
            "y": [150.0, 250.0],
            "z": [50.0, 60.0],
            "q1": [1.0, 1.0],
            "q2": [0.0, 0.0],
            "q3": [0.0, 0.0],
            "q4": [0.0, 0.0],
            "cf1": [0, 0],
            "cf4": [0, 0],
            "cf6": [0, 0],
            "cfx": [0, 0],
            "move_type": ["MoveL", "MoveL"],
            "tcp_speed": [500.0, 500.0],
            "zone_type": [10, 10],
            "tool_name": ["Tool_formage", "Tool_formage"],
            "wobj_name": ["Wobj_SerreFlan", "Wobj_SerreFlan"],
        }
    )


@pytest.fixture
def complete_df_with_eax() -> pd.DataFrame:
    """Complete point DataFrame with one active external axis."""
    return pd.DataFrame(
        {
            "x": [100.0],
            "y": [150.0],
            "z": [50.0],
            "q1": [1.0],
            "q2": [0.0],
            "q3": [0.0],
            "q4": [0.0],
            "cf1": [0],
            "cf4": [0],
            "cf6": [0],
            "cfx": [0],
            "move_type": ["MoveL"],
            "tcp_speed": [500.0],
            "zone_type": [10],
            "tool_name": ["Tool_formage"],
            "wobj_name": ["Wobj_SerreFlan"],
            "eax_a": [45.0],
        }
    )


@pytest.fixture
def process_points_df(complete_df: pd.DataFrame) -> pd.DataFrame:
    """Point DataFrame referencing process parameter sets."""
    df = complete_df.copy()
    df["process_param_index"] = [1, 2]
    return df


@pytest.fixture
def process_params_df() -> pd.DataFrame:
    """Human-readable process parameter table."""
    return pd.DataFrame(
        {
            "process_param_index": [1, 2],
            "force": [120.0, 180.0],
            "travel_speed": [35.0, 40.0],
        }
    )


@pytest.fixture
def minimal_meta() -> TrajectoryMeta:
    """Minimal valid trajectory metadata."""
    return TrajectoryMeta(name="test_traj")


@pytest.fixture
def process_meta() -> TrajectoryMeta:
    """Metadata for a trajectory with process parameters."""
    return TrajectoryMeta(
        name="process_traj",
        process=TrajectoryProcess(
            process_type=1,
            process_param_names=["force", "travel_speed"],
        ),
    )


@pytest.fixture
def simple_trajectory(
    minimal_meta: TrajectoryMeta,
    complete_df: pd.DataFrame,
) -> Trajectory:
    """Simple trajectory without process data."""
    return Trajectory(
        meta=minimal_meta,
        points=complete_df,
    )


@pytest.fixture
def process_trajectory(
    process_meta: TrajectoryMeta,
    process_points_df: pd.DataFrame,
    process_params_df: pd.DataFrame,
) -> Trajectory:
    """Trajectory with process parameter data."""
    return Trajectory(
        meta=process_meta,
        points=process_points_df,
        process_params=process_params_df,
    )
