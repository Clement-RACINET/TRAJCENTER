#!/usr/bin/env python3
# tests/conftest.py
"""Global fixtures shared across ``converter/``, ``core/`` and ``exporter/``.

Author: Clement RACINET

- ``DataFrame`` objects and ``TrajectoryMeta`` instances used by
  ``test_trajectory.py`` and the converter tests.
- File fixtures (``xlsx_*``, ``csv_*``, ``mod_*``) remain in
  ``converter/conftest.py``.
- ``Trajectory`` fixtures for exporters remain in ``exporter/conftest.py``.
"""

from __future__ import annotations

import pandas as pd
import pytest

from trajcenter.core.trajectory import (
    ExternalAxisConfig,
    SourceFormat,
    Trajectory,
    TrajectoryMeta,
)


# ---------------------------------------------------------------------------
# Fixtures — DataFrames
# ---------------------------------------------------------------------------


@pytest.fixture
def minimal_df() -> pd.DataFrame:
    """Minimal ``DataFrame`` containing only the mandatory columns."""
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
    """Complete ``DataFrame`` with all ``CONVERTER_COLUMNS`` present."""
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
            "speed": ["v500", "v500"],
            "zone": ["z10", "z10"],
            "tool_index": [0, 0],
            "wobj_index": [0, 0],
        }
    )


@pytest.fixture
def complete_df_with_eax() -> pd.DataFrame:
    """Complete ``DataFrame`` with one active external axis (``eax_a``)."""
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
            "speed": ["v500"],
            "zone": ["z10"],
            "tool_index": [0],
            "wobj_index": [0],
            "eax_a": [45.0],
        }
    )


# ---------------------------------------------------------------------------
# Fixtures — metadata
# ---------------------------------------------------------------------------


@pytest.fixture
def minimal_meta() -> TrajectoryMeta:
    """Minimal valid :class:`~trajcenter.core.trajectory.TrajectoryMeta`."""
    return TrajectoryMeta(name="test_traj")


@pytest.fixture
def complete_meta() -> TrajectoryMeta:
    """Complete :class:`~trajcenter.core.trajectory.TrajectoryMeta` with external axes and autocomplete info."""
    return TrajectoryMeta(
        name="test_complet",
        source_format=SourceFormat.RAPID,
        source_file="sphere05mm.mod",
        robot_model="IRB6700-205/2.80",
        autocompleted=["speed"],
        external_axes={
            "eax_a": ExternalAxisConfig(
                axis_type="rotational",
                unit="deg",
                label="Positionneur A",
            )
        },
    )


# ---------------------------------------------------------------------------
# Fixtures — shared trajectories
# ---------------------------------------------------------------------------


@pytest.fixture
def simple_trajectory(
    minimal_meta: TrajectoryMeta,
    complete_df: pd.DataFrame,
) -> Trajectory:
    """Simple :class:`~trajcenter.core.trajectory.Trajectory` without external axes."""
    return Trajectory(
        meta=minimal_meta,
        points=complete_df,
        tools=["Tool_formage"],
        wobjs=["Wobj_SerreFlan"],
    )
