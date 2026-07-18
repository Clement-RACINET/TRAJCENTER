#!/usr/bin/env python3
# tests/core/test_trajectory.py
"""Unit tests for :mod:`trajcenter.core.trajectory`.

Author: Clement RACINET
"""

from __future__ import annotations

import io
import json
import re
import zipfile
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from trajcenter.core.messages import raw
from trajcenter.core.trajectory import (
    ExternalAxisConfig,
    SourceFormat,
    Trajectory,
    TrajectoryMeta,
    TrajectoryProcess,
)


class TestTrajectoryProcess:
    """Tests for process metadata."""

    def test_default_process(self) -> None:
        """Default process means no process data."""
        process = TrajectoryProcess()
        assert process.process_type == 0
        assert process.process_param_names == []

    def test_process_with_names(self) -> None:
        """Process metadata accepts ordered parameter names."""
        process = TrajectoryProcess(
            process_type=1,
            process_param_names=["force", "travel_speed"],
        )
        assert process.process_type == 1
        assert process.process_param_names == ["force", "travel_speed"]

    def test_process_type_zero_with_names_raises(self) -> None:
        """Parameter names are forbidden when process_type is 0."""
        with pytest.raises(ValueError, match="process_param_names"):
            TrajectoryProcess(process_type=0, process_param_names=["force"])

    def test_too_many_process_param_names_raises(self) -> None:
        """More than 10 parameter names is invalid."""
        with pytest.raises(ValueError, match="more than 10"):
            TrajectoryProcess(
                process_type=1,
                process_param_names=[f"p{i}" for i in range(11)],
            )

    def test_duplicate_process_param_names_raises(self) -> None:
        """Duplicated process parameter names are invalid."""
        with pytest.raises(ValueError, match="unique"):
            TrajectoryProcess(
                process_type=1,
                process_param_names=["force", "force"],
            )

    def test_empty_process_param_name_raises(self) -> None:
        """Empty process parameter names are invalid."""
        with pytest.raises(ValueError, match="empty"):
            TrajectoryProcess(
                process_type=1,
                process_param_names=["force", " "],
            )


class TestTrajectoryMeta:
    """Tests for ``TrajectoryMeta``."""

    def test_defaults(self) -> None:
        """Default values are correctly initialised."""
        meta = TrajectoryMeta(name="traj")
        assert meta.version == "2.0"
        assert meta.source_format == SourceFormat.MANUAL
        assert meta.point_count == 0
        assert meta.external_axes == {}
        assert meta.autocompleted == []
        assert meta.process.process_type == 0
        assert meta.process.process_param_names == []
        assert meta.extra == {}

    def test_valid_eax_keys(self) -> None:
        """Keys ``eax_a`` through ``eax_f`` are accepted."""
        meta = TrajectoryMeta(
            name="traj",
            external_axes={
                "eax_a": ExternalAxisConfig(axis_type="rotational", unit="deg"),
                "eax_f": ExternalAxisConfig(axis_type="linear", unit="mm"),
            },
        )
        assert "eax_a" in meta.external_axes
        assert "eax_f" in meta.external_axes

    def test_invalid_eax_key_raises(self) -> None:
        """Invalid external axis keys raise ``ValueError``."""
        with pytest.raises(
            ValueError, match=re.escape(raw("INVALID_EAX_KEY").split(":")[0])
        ):
            TrajectoryMeta(
                name="traj",
                external_axes={
                    "eax_z": ExternalAxisConfig(axis_type="rotational", unit="deg")
                },
            )

    def test_autocompleted_stored(self) -> None:
        """The ``autocompleted`` field is stored."""
        meta = TrajectoryMeta(
            name="traj",
            autocompleted=["move_type", "cf1"],
        )
        assert meta.autocompleted == ["move_type", "cf1"]

    def test_serialization_roundtrip(self) -> None:
        """JSON serialisation roundtrip preserves metadata."""
        meta = TrajectoryMeta(
            name="traj",
            source_format=SourceFormat.RAPID,
            autocompleted=["move_type"],
            process=TrajectoryProcess(
                process_type=1,
                process_param_names=["force"],
            ),
        )
        meta2 = TrajectoryMeta.model_validate_json(meta.model_dump_json())
        assert meta2.name == meta.name
        assert meta2.source_format == meta.source_format
        assert meta2.autocompleted == meta.autocompleted
        assert meta2.process.process_type == 1
        assert meta2.process.process_param_names == ["force"]


class TestTrajectoryValidation:
    """Tests for trajectory validation."""

    def test_missing_required_column_raises(self, minimal_meta: TrajectoryMeta) -> None:
        """Missing mandatory geometry columns raise ``ValueError``."""
        df = pd.DataFrame({"x": [1.0], "y": [2.0], "z": [3.0]})
        with pytest.raises(
            ValueError, match=re.escape(raw("MANDATORY_COLUMNS_MISSING").split(":")[0])
        ):
            Trajectory(meta=minimal_meta, points=df)

    def test_all_required_columns_missing_raises(
        self,
        minimal_meta: TrajectoryMeta,
    ) -> None:
        """A DataFrame without geometry columns raises ``ValueError``."""
        df = pd.DataFrame({"foo": [1.0]})
        with pytest.raises(
            ValueError, match=re.escape(raw("MANDATORY_COLUMNS_MISSING").split(":")[0])
        ):
            Trajectory(meta=minimal_meta, points=df)

    def test_float_cast(
        self,
        minimal_meta: TrajectoryMeta,
        minimal_df: pd.DataFrame,
    ) -> None:
        """Geometry columns are cast to float64."""
        df = minimal_df.copy()
        df["x"] = df["x"].astype(int)
        traj = Trajectory(meta=minimal_meta, points=df)
        assert traj.points["x"].dtype == "float64"

    def test_confdata_cast_to_int8_nullable(
        self,
        minimal_meta: TrajectoryMeta,
        complete_df: pd.DataFrame,
    ) -> None:
        """Confdata columns are cast to nullable Int8."""
        traj = Trajectory(meta=minimal_meta, points=complete_df)
        for col in ["cf1", "cf4", "cf6", "cfx"]:
            assert traj.points[col].dtype == pd.Int8Dtype()

    def test_zone_type_cast_to_int16_nullable(
        self,
        minimal_meta: TrajectoryMeta,
        complete_df: pd.DataFrame,
    ) -> None:
        """zone_type is cast to nullable Int16."""
        traj = Trajectory(meta=minimal_meta, points=complete_df)
        assert traj.points["zone_type"].dtype == pd.Int16Dtype()

    def test_readconfs_cast_to_boolean(
        self,
        minimal_meta: TrajectoryMeta,
        complete_df: pd.DataFrame,
    ) -> None:
        """readconfs is cast to pandas nullable boolean when present."""
        df = complete_df.copy()
        df["readconfs"] = [True, False]
        traj = Trajectory(meta=minimal_meta, points=df)
        assert str(traj.points["readconfs"].dtype) == "boolean"


class TestTrajectoryProcessValidation:
    """Tests for process consistency validation."""

    def test_process_type_zero_rejects_process_params(
        self,
        minimal_meta: TrajectoryMeta,
        complete_df: pd.DataFrame,
        process_params_df: pd.DataFrame,
    ) -> None:
        """process_params is forbidden when process_type is 0."""
        with pytest.raises(ValueError, match="process_type is 0"):
            Trajectory(
                meta=minimal_meta,
                points=complete_df,
                process_params=process_params_df,
            )

    def test_process_requires_param_index_column(
        self,
        process_meta: TrajectoryMeta,
        complete_df: pd.DataFrame,
        process_params_df: pd.DataFrame,
    ) -> None:
        """points.process_param_index is required when process is active."""
        with pytest.raises(ValueError, match="process_param_index"):
            Trajectory(
                meta=process_meta,
                points=complete_df,
                process_params=process_params_df,
            )

    def test_process_requires_process_params(
        self,
        process_meta: TrajectoryMeta,
        process_points_df: pd.DataFrame,
    ) -> None:
        """process_params is required when process is active."""
        with pytest.raises(ValueError, match="process_params is required"):
            Trajectory(meta=process_meta, points=process_points_df)

    def test_process_param_columns_must_match_meta(
        self,
        process_meta: TrajectoryMeta,
        process_points_df: pd.DataFrame,
    ) -> None:
        """process_params columns must match process_param_names."""
        bad_params = pd.DataFrame(
            {
                "process_param_index": [1],
                "force": [120.0],
                "bad_name": [35.0],
            }
        )
        with pytest.raises(ValueError, match="must match"):
            Trajectory(
                meta=process_meta,
                points=process_points_df,
                process_params=bad_params,
            )

    def test_process_params_referenced_index_must_exist(
        self,
        process_meta: TrajectoryMeta,
        process_params_df: pd.DataFrame,
        process_points_df: pd.DataFrame,
    ) -> None:
        """Used process_param_index values must exist in process_params."""
        df = process_points_df.copy()
        df["process_param_index"] = [1, 3]
        with pytest.raises(ValueError, match="missing process_param_index"):
            Trajectory(
                meta=process_meta,
                points=df,
                process_params=process_params_df,
            )

    def test_process_param_index_zero_allowed_on_points(
        self,
        process_meta: TrajectoryMeta,
        process_params_df: pd.DataFrame,
        process_points_df: pd.DataFrame,
    ) -> None:
        """A point may use process_param_index = 0 to mean no parameter set."""
        df = process_points_df.copy()
        df["process_param_index"] = [0, 2]
        traj = Trajectory(
            meta=process_meta,
            points=df,
            process_params=process_params_df,
        )
        assert traj.has_process is True
        assert traj.has_process_params is True

    def test_process_params_index_must_be_unique(
        self,
        process_meta: TrajectoryMeta,
        process_points_df: pd.DataFrame,
    ) -> None:
        """process_params.process_param_index values must be unique."""
        bad_params = pd.DataFrame(
            {
                "process_param_index": [1, 1],
                "force": [120.0, 180.0],
                "travel_speed": [35.0, 40.0],
            }
        )
        with pytest.raises(ValueError, match="unique"):
            Trajectory(
                meta=process_meta,
                points=process_points_df,
                process_params=bad_params,
            )


class TestTrajectoryProperties:
    """Tests for trajectory properties."""

    def test_point_count(self, simple_trajectory: Trajectory) -> None:
        """point_count returns number of rows."""
        assert simple_trajectory.point_count == 2

    def test_active_external_axes_none(self, simple_trajectory: Trajectory) -> None:
        """No eax column means no active external axis."""
        assert simple_trajectory.active_external_axes == []

    def test_active_external_axes_with_eax(
        self,
        minimal_meta: TrajectoryMeta,
        complete_df_with_eax: pd.DataFrame,
    ) -> None:
        """active_external_axes returns present eax columns."""
        traj = Trajectory(meta=minimal_meta, points=complete_df_with_eax)
        assert traj.active_external_axes == ["eax_a"]

    def test_has_confdata_true(self, simple_trajectory: Trajectory) -> None:
        """has_confdata is true when all cf columns are present."""
        assert simple_trajectory.has_confdata is True

    def test_has_confdata_false(
        self,
        minimal_meta: TrajectoryMeta,
        minimal_df: pd.DataFrame,
    ) -> None:
        """has_confdata is false when cf columns are absent."""
        traj = Trajectory(meta=minimal_meta, points=minimal_df)
        assert traj.has_confdata is False

    def test_has_move_type_true(self, simple_trajectory: Trajectory) -> None:
        """has_move_type is true when move_type is present."""
        assert simple_trajectory.has_move_type is True

    def test_is_exportable(self, simple_trajectory: Trajectory) -> None:
        """Constructed trajectories are exportable."""
        assert simple_trajectory.is_exportable is True

    def test_has_converter_columns_true(self, simple_trajectory: Trajectory) -> None:
        """has_converter_columns is true when converter-safe columns are present."""
        assert simple_trajectory.has_converter_columns is True

    def test_has_converter_columns_false(
        self,
        minimal_meta: TrajectoryMeta,
        minimal_df: pd.DataFrame,
    ) -> None:
        """has_converter_columns is false on minimal geometry-only data."""
        traj = Trajectory(meta=minimal_meta, points=minimal_df)
        assert traj.has_converter_columns is False

    def test_repr(self, simple_trajectory: Trajectory) -> None:
        """repr contains key trajectory information."""
        r = repr(simple_trajectory)
        assert "test_traj" in r
        assert "points=2" in r
        assert "process_type=0" in r
        assert "exportable=True" in r


class TestTrajectorySaveLoad:
    """Tests for archive serialisation and deserialisation."""

    def test_save_creates_file(
        self,
        tmp_path: Path,
        simple_trajectory: Trajectory,
    ) -> None:
        """save creates a .trajcenter file."""
        dest = tmp_path / "test.trajcenter"
        result = simple_trajectory.save(dest)
        assert result.exists()
        assert result.suffix == ".trajcenter"

    def test_save_returns_absolute_path(
        self,
        tmp_path: Path,
        simple_trajectory: Trajectory,
    ) -> None:
        """save returns an absolute path."""
        result = simple_trajectory.save(tmp_path / "test.trajcenter")
        assert result.is_absolute()

    def test_save_creates_parent_dirs(
        self,
        tmp_path: Path,
        simple_trajectory: Trajectory,
    ) -> None:
        """save creates parent directories."""
        dest = tmp_path / "subdir" / "nested" / "test.trajcenter"
        simple_trajectory.save(dest)
        assert dest.exists()

    def test_save_zip_contains_required_entries(
        self,
        tmp_path: Path,
        simple_trajectory: Trajectory,
    ) -> None:
        """Archive contains meta.json and points.parquet only for no process."""
        dest = tmp_path / "test.trajcenter"
        simple_trajectory.save(dest)
        with zipfile.ZipFile(dest, "r") as zf:
            names = set(zf.namelist())
        assert "meta.json" in names
        assert "points.parquet" in names
        assert "tools.json" not in names
        assert "wobjs.json" not in names
        assert "process_params.parquet" not in names

    def test_save_zip_contains_process_params_when_process_active(
        self,
        tmp_path: Path,
        process_trajectory: Trajectory,
    ) -> None:
        """Archive contains process_params.parquet when process is active."""
        dest = tmp_path / "process.trajcenter"
        process_trajectory.save(dest)
        with zipfile.ZipFile(dest, "r") as zf:
            names = set(zf.namelist())
        assert "process_params.parquet" in names

    def test_save_updates_point_count(
        self,
        tmp_path: Path,
        simple_trajectory: Trajectory,
    ) -> None:
        """save updates meta.point_count."""
        dest = tmp_path / "test.trajcenter"
        simple_trajectory.save(dest)
        with zipfile.ZipFile(dest, "r") as zf:
            meta_raw = json.loads(zf.read("meta.json"))
        assert meta_raw["point_count"] == 2

    def test_load_roundtrip(
        self,
        tmp_path: Path,
        simple_trajectory: Trajectory,
    ) -> None:
        """save + load reconstructs trajectory metadata and points."""
        dest = tmp_path / "test.trajcenter"
        simple_trajectory.save(dest)
        loaded = Trajectory.load(dest)
        assert loaded.meta.name == simple_trajectory.meta.name
        assert loaded.point_count == simple_trajectory.point_count
        assert loaded.process_params is None
        assert set(loaded.points.columns) == set(simple_trajectory.points.columns)

    def test_load_process_roundtrip(
        self,
        tmp_path: Path,
        process_trajectory: Trajectory,
    ) -> None:
        """save + load preserves process metadata and process params."""
        dest = tmp_path / "process.trajcenter"
        process_trajectory.save(dest)
        loaded = Trajectory.load(dest)
        assert loaded.meta.process.process_type == 1
        assert loaded.meta.process.process_param_names == ["force", "travel_speed"]
        assert loaded.process_params is not None
        assert set(loaded.process_params.columns) == {
            "process_param_index",
            "force",
            "travel_speed",
        }

    def test_load_points_values(
        self,
        tmp_path: Path,
        simple_trajectory: Trajectory,
    ) -> None:
        """Point numeric values are preserved after save/load."""
        dest = tmp_path / "test.trajcenter"
        simple_trajectory.save(dest)
        loaded = Trajectory.load(dest)
        pd.testing.assert_series_equal(
            loaded.points["x"].reset_index(drop=True),
            simple_trajectory.points["x"].reset_index(drop=True),
            check_names=False,
        )

    def test_load_autocompleted_preserved(
        self,
        tmp_path: Path,
        complete_df: pd.DataFrame,
    ) -> None:
        """autocompleted metadata is preserved."""
        meta = TrajectoryMeta(name="traj", autocompleted=["move_type", "cf1"])
        traj = Trajectory(meta=meta, points=complete_df)
        dest = tmp_path / "traj.trajcenter"
        traj.save(dest)
        loaded = Trajectory.load(dest)
        assert loaded.meta.autocompleted == ["move_type", "cf1"]

    def test_load_file_not_found_raises(self, tmp_path: Path) -> None:
        """load raises FileNotFoundError on missing archive."""
        with pytest.raises(
            FileNotFoundError, match=re.escape(raw("FILE_NOT_FOUND").split(":")[0])
        ):
            Trajectory.load(tmp_path / "missing.trajcenter")

    def test_load_invalid_archive_raises(self, tmp_path: Path) -> None:
        """load raises on corrupt archive."""
        bad = tmp_path / "bad.trajcenter"
        bad.write_bytes(b"not a zip")
        with pytest.raises((ValueError, zipfile.BadZipFile)):
            Trajectory.load(bad)

    def test_load_missing_required_entries_raises(
        self,
        tmp_path: Path,
        minimal_meta: TrajectoryMeta,
        complete_df: pd.DataFrame,
    ) -> None:
        """load raises if mandatory archive entries are absent."""
        dest = tmp_path / "bad.trajcenter"
        with zipfile.ZipFile(dest, "w") as zf:
            zf.writestr("meta.json", minimal_meta.model_dump_json())
            buf = io.BytesIO()
            table = pa.Table.from_pandas(complete_df, preserve_index=False)
            pq.write_table(table, buf, compression="zstd")
            zf.writestr("wrong.parquet", buf.getvalue())

        with pytest.raises(ValueError, match="missing entries"):
            Trajectory.load(dest)

    def test_save_with_eax(
        self,
        tmp_path: Path,
        minimal_meta: TrajectoryMeta,
        complete_df_with_eax: pd.DataFrame,
    ) -> None:
        """eax columns are preserved after save/load."""
        traj = Trajectory(meta=minimal_meta, points=complete_df_with_eax)
        dest = tmp_path / "eax.trajcenter"
        traj.save(dest)
        loaded = Trajectory.load(dest)
        assert "eax_a" in loaded.points.columns
        assert loaded.points["eax_a"].iloc[0] == pytest.approx(45.0)
