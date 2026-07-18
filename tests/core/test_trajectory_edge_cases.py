#!/usr/bin/env python3
# tests/core/test_trajectory_edge_cases.py
"""Edge-case tests for :mod:`trajcenter.core.trajectory`.

Author: Clement RACINET

These tests target validation and serialization branches not covered by
the nominal trajectory test suite.
"""

from __future__ import annotations

import io
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import pytest

from trajcenter.core.trajectory import (
    SourceFormat,
    Trajectory,
    TrajectoryMeta,
    TrajectoryProcess,
)


def _minimal_points() -> pd.DataFrame:
    """Build a minimal valid points DataFrame.

    ABB Route:
        N/A — test helper.

    ABB Constraints:
        No ABB controller access.

    Args:
        None.

    Returns:
        Minimal valid point table.

    Raises:
        None.

    Example:
        ::

            points = _minimal_points()
    """
    return pd.DataFrame(
        {
            "x": [1.0],
            "y": [2.0],
            "z": [3.0],
            "q1": [1.0],
            "q2": [0.0],
            "q3": [0.0],
            "q4": [0.0],
        }
    )


def _process_meta() -> TrajectoryMeta:
    """Build process metadata for validation tests.

    ABB Route:
        N/A — test helper.

    ABB Constraints:
        No ABB controller access.

    Args:
        None.

    Returns:
        Trajectory metadata with active process.

    Raises:
        pydantic.ValidationError: If metadata is invalid.

    Example:
        ::

            meta = _process_meta()
    """
    return TrajectoryMeta(
        name="process",
        source_format=SourceFormat.MANUAL,
        created_at=datetime(2026, 7, 8, 12, 0, 0, tzinfo=timezone.utc),
        process=TrajectoryProcess(
            process_type=1,
            process_param_names=["force", "travel_speed"],
        ),
    )


def _process_points() -> pd.DataFrame:
    """Build valid process-aware points.

    ABB Route:
        N/A — test helper.

    ABB Constraints:
        No ABB controller access.

    Args:
        None.

    Returns:
        Point table with ``process_param_index``.

    Raises:
        None.

    Example:
        ::

            points = _process_points()
    """
    points = _minimal_points()
    points["process_param_index"] = [1]
    return points


def _process_params() -> pd.DataFrame:
    """Build valid process parameter table.

    ABB Route:
        N/A — test helper.

    ABB Constraints:
        No ABB controller access.

    Args:
        None.

    Returns:
        Process parameter DataFrame.

    Raises:
        None.

    Example:
        ::

            params = _process_params()
    """
    return pd.DataFrame(
        {
            "process_param_index": [1],
            "force": [120.0],
            "travel_speed": [35.0],
        }
    )


class TestTrajectoryPointCastErrors:
    """Tests for point dtype casting error branches."""

    def test_invalid_float_column_raises(self) -> None:
        """Invalid geometry values raise a cast error."""
        points = pd.DataFrame(
            {
                "x": ["not-a-float"],
                "y": [2.0],
                "z": [3.0],
                "q1": [1.0],
                "q2": [0.0],
                "q3": [0.0],
                "q4": [0.0],
            }
        )

        with pytest.raises(ValueError, match="Cannot cast column 'x'"):
            Trajectory(meta=TrajectoryMeta(name="bad_float"), points=points)

    def test_invalid_confdata_column_raises(self) -> None:
        """Invalid confdata values raise a cast error."""
        points = _minimal_points()
        points["cf1"] = ["bad"]

        with pytest.raises(ValueError, match="Cannot cast column 'cf1'"):
            Trajectory(meta=TrajectoryMeta(name="bad_cf"), points=points)

    def test_invalid_zone_type_column_raises(self) -> None:
        """Invalid zone_type values raise a cast error."""
        points = _minimal_points()
        points["zone_type"] = ["bad"]

        with pytest.raises(ValueError, match="Cannot cast column 'zone_type'"):
            Trajectory(meta=TrajectoryMeta(name="bad_zone"), points=points)

    def test_invalid_process_param_index_column_raises(self) -> None:
        """Invalid point process_param_index values raise a cast error."""
        points = _minimal_points()
        points["process_param_index"] = ["bad"]

        meta = _process_meta()
        params = _process_params()

        with pytest.raises(
            ValueError, match="Cannot cast column 'process_param_index'"
        ):
            Trajectory(meta=meta, points=points, process_params=params)

    def test_invalid_readconfs_column_raises(self) -> None:
        """Invalid readconfs values raise a boolean cast error."""
        points = _minimal_points()
        points["readconfs"] = ["not-a-bool"]

        with pytest.raises(ValueError, match="Cannot cast column 'readconfs'"):
            Trajectory(meta=TrajectoryMeta(name="bad_bool"), points=points)


class TestTrajectoryProcessParamValidationEdges:
    """Tests for process parameter validation branches."""

    def test_process_params_missing_index_column_raises(self) -> None:
        """process_params without process_param_index is rejected."""
        params = pd.DataFrame({"force": [120.0], "travel_speed": [35.0]})

        with pytest.raises(ValueError, match="process_param_index"):
            Trajectory(
                meta=_process_meta(),
                points=_process_points(),
                process_params=params,
            )

    def test_process_params_too_many_rows_raises(self) -> None:
        """More than 256 process parameter rows is rejected."""
        params = pd.DataFrame(
            {
                "process_param_index": list(range(1, 258)),
                "force": [120.0] * 257,
                "travel_speed": [35.0] * 257,
            }
        )
        points = _process_points()
        points["process_param_index"] = [1]

        with pytest.raises(ValueError, match="max is 256|257"):
            Trajectory(meta=_process_meta(), points=points, process_params=params)

    def test_process_params_invalid_index_cast_raises(self) -> None:
        """Non-integer process parameter indexes are rejected."""
        params = pd.DataFrame(
            {
                "process_param_index": ["bad"],
                "force": [120.0],
                "travel_speed": [35.0],
            }
        )

        with pytest.raises(ValueError, match="Int16|process_param_index"):
            Trajectory(
                meta=_process_meta(),
                points=_process_points(),
                process_params=params,
            )

    def test_process_params_index_out_of_range_low_raises(self) -> None:
        """process_params index below 1 is rejected."""
        params = pd.DataFrame(
            {
                "process_param_index": [0],
                "force": [120.0],
                "travel_speed": [35.0],
            }
        )

        with pytest.raises(ValueError, match="1..256"):
            Trajectory(
                meta=_process_meta(),
                points=_process_points(),
                process_params=params,
            )

    def test_process_params_index_out_of_range_high_raises(self) -> None:
        """process_params index above 256 is rejected."""
        params = pd.DataFrame(
            {
                "process_param_index": [257],
                "force": [120.0],
                "travel_speed": [35.0],
            }
        )

        with pytest.raises(ValueError, match="1..256"):
            Trajectory(
                meta=_process_meta(),
                points=_process_points(),
                process_params=params,
            )

    def test_process_params_too_many_parameter_columns_raises(self) -> None:
        """More than 10 process parameter columns is rejected."""
        params_data: dict[str, list[float | int]] = {"process_param_index": [1]}
        for idx in range(11):
            params_data[f"p{idx}"] = [float(idx)]

        meta = TrajectoryMeta(
            name="too_many_params",
            process=TrajectoryProcess(
                process_type=1,
                process_param_names=[f"p{idx}" for idx in range(10)],
            ),
        )
        points = _process_points()

        with pytest.raises(ValueError, match="more than 10"):
            Trajectory(
                meta=meta,
                points=points,
                process_params=pd.DataFrame(params_data),
            )

    def test_process_params_invalid_parameter_value_raises(self) -> None:
        """Non-float process parameter values are rejected."""
        params = pd.DataFrame(
            {
                "process_param_index": [1],
                "force": ["bad"],
                "travel_speed": [35.0],
            }
        )

        with pytest.raises(ValueError, match="force|float64"):
            Trajectory(
                meta=_process_meta(),
                points=_process_points(),
                process_params=params,
            )

    def test_point_process_param_index_out_of_range_low_raises(self) -> None:
        """Point process_param_index below 0 is rejected."""
        points = _process_points()
        points["process_param_index"] = [-1]

        with pytest.raises(ValueError, match="0..256"):
            Trajectory(
                meta=_process_meta(),
                points=points,
                process_params=_process_params(),
            )

    def test_point_process_param_index_out_of_range_high_raises(self) -> None:
        """Point process_param_index above 256 is rejected."""
        points = _process_points()
        points["process_param_index"] = [257]

        with pytest.raises(ValueError, match="0..256"):
            Trajectory(
                meta=_process_meta(),
                points=points,
                process_params=_process_params(),
            )


class TestTrajectorySerializationEdges:
    """Tests for serialization branches."""

    def test_load_archive_with_unexpected_process_params_for_type_zero_raises(
        self,
        tmp_path: Path,
    ) -> None:
        """Loading archive with process_params but process_type zero raises."""
        traj = Trajectory(meta=TrajectoryMeta(name="base"), points=_minimal_points())
        archive = tmp_path / "base.trajcenter"
        traj.save(archive)

        params = _process_params()

        with zipfile.ZipFile(archive, "a") as zf:
            buffer = io.BytesIO()
            params.to_parquet(buffer, index=False)
            zf.writestr("process_params.parquet", buffer.getvalue())

        with pytest.raises(ValueError, match="process_type is 0"):
            Trajectory.load(archive)

    def test_dataframe_to_table_unsupported_dtype_raises(self) -> None:
        """Unsupported DataFrame dtypes raise ValueError during table conversion."""
        df = pd.DataFrame(
            {
                "unsupported": pd.Series([1.0 + 2.0j], dtype="complex128"),
            }
        )

        with pytest.raises(ValueError, match="Cannot infer PyArrow type|unsupported"):
            Trajectory._dataframe_to_table(df)
