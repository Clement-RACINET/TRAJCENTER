# tests/conftest.py

"""
Fixtures globales partagées entre converter/, core/ et exporter/.

- DataFrames et TrajectoryMeta utilisés par test_trajectory.py ET les converters.
- Les fixtures fichiers (xlsx_*, csv_*, mod_*) restent dans converter/conftest.py.
- Les fixtures Trajectory pour l'export restent dans exporter/conftest.py.
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
    """DataFrame minimal avec uniquement les colonnes obligatoires."""
    return pd.DataFrame({
        "x":  [100.0, 200.0],
        "y":  [150.0, 250.0],
        "z":  [50.0,  60.0],
        "q1": [1.0,   1.0],
        "q2": [0.0,   0.0],
        "q3": [0.0,   0.0],
        "q4": [0.0,   0.0],
    })


@pytest.fixture
def complete_df() -> pd.DataFrame:
    """DataFrame complet avec toutes les colonnes CONVERTER_COLUMNS."""
    return pd.DataFrame({
        "x":  [100.0, 200.0],
        "y":  [150.0, 250.0],
        "z":  [50.0,  60.0],
        "q1": [1.0,   1.0],
        "q2": [0.0,   0.0],
        "q3": [0.0,   0.0],
        "q4": [0.0,   0.0],
        "cf1": [0, 0],
        "cf4": [0, 0],
        "cf6": [0, 0],
        "cfx": [0, 0],
        "move_type":  ["MoveL", "MoveL"],
        "speed":      ["v500",  "v500"],
        "zone":       ["z10",   "z10"],
        "tool_index": [0, 0],
        "wobj_index": [0, 0],
    })


@pytest.fixture
def complete_df_with_eax() -> pd.DataFrame:
    """DataFrame complet avec un axe externe actif (eax_a)."""
    return pd.DataFrame({
        "x":  [100.0], "y": [150.0], "z": [50.0],
        "q1": [1.0],   "q2": [0.0],  "q3": [0.0], "q4": [0.0],
        "cf1": [0], "cf4": [0], "cf6": [0], "cfx": [0],
        "move_type":  ["MoveL"],
        "speed":      ["v500"],
        "zone":       ["z10"],
        "tool_index": [0],
        "wobj_index": [0],
        "eax_a":      [45.0],
    })


# ---------------------------------------------------------------------------
# Fixtures — métadonnées
# ---------------------------------------------------------------------------


@pytest.fixture
def minimal_meta() -> TrajectoryMeta:
    """Métadonnées minimales valides."""
    return TrajectoryMeta(name="test_traj")


@pytest.fixture
def complete_meta() -> TrajectoryMeta:
    """Métadonnées complètes avec axes externes et autocomplétion."""
    return TrajectoryMeta(
        name="test_complet",
        source_format=SourceFormat.RAPID,
        source_file="sphere05mm.mod",
        robot_model="IRB6700-205/2.80",
        autocompleted=["speed"],
        external_axes={
            "eax_a": ExternalAxisConfig(
                axis_type="rotational", unit="deg", label="Positionneur A"
            )
        },
    )


# ---------------------------------------------------------------------------
# Fixtures — trajectoires partagées
# ---------------------------------------------------------------------------


@pytest.fixture
def simple_trajectory(
    minimal_meta: TrajectoryMeta,
    complete_df: pd.DataFrame,
) -> Trajectory:
    """Trajectoire simple sans axes externes."""
    return Trajectory(
        meta=minimal_meta,
        points=complete_df,
        tools=["Tool_formage"],
        wobjs=["Wobj_SerreFlan"],
    )
