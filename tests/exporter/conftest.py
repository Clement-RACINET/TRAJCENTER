# tests/exporter/conftest.py

"""
Fixtures partagées pour les tests des exporters.

Fournit des objets Trajectory prêts à l'emploi, construits directement
sans passer par un converter.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import pytest

from trajcenter.core.trajectory import SourceFormat, Trajectory, TrajectoryMeta


# ---------------------------------------------------------------------------
# Helper interne
# ---------------------------------------------------------------------------


def _make_traj(
    name: str,
    rows: list[dict],
    tools: list[str] | None = None,
    wobjs: list[str] | None = None,
    robot_model: str | None = None,
    extra: dict | None = None,
) -> Trajectory:
    """Construit une Trajectory de test directement depuis des dicts."""
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
    """Trajectoire minimale : 3 points, tool0/wobj0, toutes colonnes présentes."""
    return _make_traj(
        name="traj_basic",
        rows=[
            {"x": 0.0,   "y": 0.0,  "z": 0.0,
             "q1": 1.0, "q2": 0.0, "q3": 0.0, "q4": 0.0,
             "cf1": 0, "cf4": 0, "cf6": 0, "cfx": 0,
             "move_type": "MoveL", "speed": "v500", "zone": "z10",
             "tool_index": 0, "wobj_index": 0},
            {"x": 100.0, "y": 0.0,  "z": 0.0,
             "q1": 1.0, "q2": 0.0, "q3": 0.0, "q4": 0.0,
             "cf1": 0, "cf4": 0, "cf6": 0, "cfx": 0,
             "move_type": "MoveJ", "speed": "v250", "zone": "z5",
             "tool_index": 0, "wobj_index": 0},
            {"x": 200.0, "y": 50.0, "z": 10.0,
             "q1": 1.0, "q2": 0.0, "q3": 0.0, "q4": 0.0,
             "cf1": 0, "cf4": 0, "cf6": 0, "cfx": 0,
             "move_type": "MoveL", "speed": "v500", "zone": "z0",
             "tool_index": 0, "wobj_index": 0},
        ],
    )


@pytest.fixture
def traj_multi_tools() -> Trajectory:
    """Trajectoire avec 2 tools et 2 wobjs, tool_index alterne entre 0 et 1."""
    return _make_traj(
        name="traj_multi_tools",
        rows=[
            {"x": 0.0,   "y": 0.0, "z": 0.0,
             "q1": 1.0, "q2": 0.0, "q3": 0.0, "q4": 0.0,
             "cf1": 0, "cf4": 0, "cf6": 0, "cfx": 0,
             "move_type": "MoveL", "speed": "v500", "zone": "z10",
             "tool_index": 0, "wobj_index": 0},
            {"x": 100.0, "y": 0.0, "z": 0.0,
             "q1": 1.0, "q2": 0.0, "q3": 0.0, "q4": 0.0,
             "cf1": 0, "cf4": 0, "cf6": 0, "cfx": 0,
             "move_type": "MoveJ", "speed": "v250", "zone": "z5",
             "tool_index": 1, "wobj_index": 1},
        ],
        tools=["Tool_A", "Tool_B"],
        wobjs=["Wobj_A", "Wobj_B"],
    )


@pytest.fixture
def traj_with_meta() -> Trajectory:
    """Trajectoire avec robot_model et extra{} renseignés."""
    return _make_traj(
        name="traj_with_meta",
        rows=[
            {"x": 1.0, "y": 2.0, "z": 3.0,
             "q1": 1.0, "q2": 0.0, "q3": 0.0, "q4": 0.0,
             "cf1": 0, "cf4": 0, "cf6": 0, "cfx": 0,
             "move_type": "MoveL", "speed": "v500", "zone": "z10",
             "tool_index": 0, "wobj_index": 0},
        ],
        robot_model="IRB6700-205/2.80",
        extra={"author": "Jean Dupont", "project": "Soudure_V2"},
    )


@pytest.fixture
def traj_no_meta() -> Trajectory:
    """Trajectoire sans robot_model ni extra{} — teste include_meta=False."""
    return _make_traj(
        name="traj_no_meta",
        rows=[
            {"x": 1.0, "y": 2.0, "z": 3.0,
             "q1": 1.0, "q2": 0.0, "q3": 0.0, "q4": 0.0,
             "cf1": 0, "cf4": 0, "cf6": 0, "cfx": 0,
             "move_type": "MoveL", "speed": "v500", "zone": "z10",
             "tool_index": 0, "wobj_index": 0},
        ],
    )
