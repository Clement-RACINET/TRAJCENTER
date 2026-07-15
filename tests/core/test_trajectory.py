#!/usr/bin/env python3
# tests/core/test_trajectory.py
"""Unit tests for :mod:`trajcenter.core.trajectory`.

Author: Clement RACINET

Covers:

- Required column validation
- Pandas type casting
- ``tool_index`` / ``wobj_index`` bounds validation
- ``.trajcenter`` serialisation / deserialisation
- Utility properties
- ``__repr__`` representation
"""

from __future__ import annotations

import io
import json
import zipfile
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from trajcenter.core.trajectory import (
    ExternalAxisConfig,
    SourceFormat,
    Trajectory,
    TrajectoryMeta,
)


# ---------------------------------------------------------------------------
# Tests — TrajectoryMeta
# ---------------------------------------------------------------------------


class TestTrajectoryMeta:
    """Tests for the ``TrajectoryMeta`` Pydantic model."""

    def test_defaults(self) -> None:
        """Default values are correctly initialised."""
        meta = TrajectoryMeta(name="traj")
        assert meta.version == "1.0"
        assert meta.source_format == SourceFormat.MANUAL
        assert meta.point_count == 0
        assert meta.external_axes == {}
        assert meta.autocompleted == []
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
        """An invalid external axis key raises ValueError."""
        with pytest.raises(ValueError, match=r"[Ee]xternal axis|[Cc]l[eé].*axe"):
            TrajectoryMeta(
                name="traj",
                external_axes={
                    "eax_z": ExternalAxisConfig(axis_type="rotational", unit="deg")
                },
            )

    def test_autocompleted_stored(self) -> None:
        """The ``autocompleted`` field is correctly stored."""
        meta = TrajectoryMeta(
            name="traj",
            autocompleted=["speed", "move_type", "cf1"],
        )
        assert "speed" in meta.autocompleted
        assert "move_type" in meta.autocompleted
        assert len(meta.autocompleted) == 3

    def test_serialization_roundtrip(self) -> None:
        """JSON serialisation → Pydantic deserialisation is lossless."""
        meta = TrajectoryMeta(
            name="traj",
            source_format=SourceFormat.RAPID,
            autocompleted=["speed"],
        )
        json_str = meta.model_dump_json()
        meta2 = TrajectoryMeta.model_validate_json(json_str)
        assert meta2.name == meta.name
        assert meta2.source_format == meta.source_format
        assert meta2.autocompleted == meta.autocompleted


# ---------------------------------------------------------------------------
# Tests — Trajectory.__init__ / validation
# ---------------------------------------------------------------------------


class TestTrajectoryValidation:
    """Tests for validation at ``Trajectory`` instantiation."""

    def test_missing_required_column_raises(self, minimal_meta: TrajectoryMeta) -> None:
        """A missing required column raises ValueError."""
        df = pd.DataFrame({"x": [1.0], "y": [2.0], "z": [3.0]})
        with pytest.raises(
            ValueError, match=r"[Mm]issing.*columns|[Cc]olonn.*obligatoire"
        ):
            Trajectory(meta=minimal_meta, points=df)

    def test_all_required_columns_missing_raises(
        self, minimal_meta: TrajectoryMeta
    ) -> None:
        """An empty DataFrame raises ValueError."""
        df = pd.DataFrame({"foo": [1.0]})
        with pytest.raises(
            ValueError, match=r"[Mm]issing.*columns|[Cc]olonn.*obligatoire"
        ):
            Trajectory(meta=minimal_meta, points=df)

    def test_float_cast(
        self, minimal_meta: TrajectoryMeta, minimal_df: pd.DataFrame
    ) -> None:
        """Float64 columns are correctly cast from integer input."""
        df = minimal_df.copy()
        df["x"] = df["x"].astype(int)
        traj = Trajectory(meta=minimal_meta, points=df)
        assert traj.points["x"].dtype == "float64"

    def test_confdata_cast_to_int8_nullable(
        self, minimal_meta: TrajectoryMeta, complete_df: pd.DataFrame
    ) -> None:
        """Confdata columns are cast to nullable ``Int8``."""
        traj = Trajectory(meta=minimal_meta, points=complete_df)
        for col in ["cf1", "cf4", "cf6", "cfx"]:
            assert traj.points[col].dtype == pd.Int8Dtype()

    def test_tool_index_out_of_bounds_raises(
        self, minimal_meta: TrajectoryMeta, complete_df: pd.DataFrame
    ) -> None:
        """A ``tool_index`` out of bounds raises ``ValueError``."""
        df = complete_df.copy()
        df["tool_index"] = 5
        with pytest.raises(ValueError, match="tool_index max"):
            Trajectory(meta=minimal_meta, points=df, tools=["Tool_formage"])

    def test_wobj_index_out_of_bounds_raises(
        self, minimal_meta: TrajectoryMeta, complete_df: pd.DataFrame
    ) -> None:
        """A ``wobj_index`` out of bounds raises ``ValueError``."""
        df = complete_df.copy()
        df["wobj_index"] = 3
        with pytest.raises(ValueError, match="wobj_index max"):
            Trajectory(meta=minimal_meta, points=df, wobjs=["Wobj_SerreFlan"])

    def test_valid_index_bounds_pass(
        self, minimal_meta: TrajectoryMeta, complete_df: pd.DataFrame
    ) -> None:
        """Indices within bounds do not raise an error."""
        traj = Trajectory(
            meta=minimal_meta,
            points=complete_df,
            tools=["Tool_formage"],
            wobjs=["Wobj_SerreFlan"],
        )
        assert traj.tools == ["Tool_formage"]
        assert traj.wobjs == ["Wobj_SerreFlan"]

    def test_empty_tools_wobjs_default(
        self, minimal_meta: TrajectoryMeta, minimal_df: pd.DataFrame
    ) -> None:
        """``tools`` and ``wobjs`` default to ``[]`` when not provided."""
        traj = Trajectory(meta=minimal_meta, points=minimal_df)
        assert traj.tools == []
        assert traj.wobjs == []


# ---------------------------------------------------------------------------
# Tests — properties
# ---------------------------------------------------------------------------


class TestTrajectoryProperties:
    """Tests for ``Trajectory`` utility properties."""

    def test_point_count(self, simple_trajectory: Trajectory) -> None:
        """``point_count`` returns the number of DataFrame rows."""
        assert simple_trajectory.point_count == 2

    def test_active_external_axes_none(self, simple_trajectory: Trajectory) -> None:
        """``active_external_axes`` is empty when no ``eax_*`` column is present."""
        assert simple_trajectory.active_external_axes == []

    def test_active_external_axes_with_eax(
        self, minimal_meta: TrajectoryMeta, complete_df_with_eax: pd.DataFrame
    ) -> None:
        """``active_external_axes`` returns the ``eax_*`` columns that are present."""
        traj = Trajectory(
            meta=minimal_meta,
            points=complete_df_with_eax,
            tools=["Tool_formage"],
            wobjs=["Wobj_SerreFlan"],
        )
        assert traj.active_external_axes == ["eax_a"]

    def test_has_confdata_true(self, simple_trajectory: Trajectory) -> None:
        """``has_confdata`` is ``True`` when ``cf1`` is present."""
        assert simple_trajectory.has_confdata is True

    def test_has_confdata_false(
        self, minimal_meta: TrajectoryMeta, minimal_df: pd.DataFrame
    ) -> None:
        """``has_confdata`` is ``False`` when ``cf1`` is absent."""
        traj = Trajectory(meta=minimal_meta, points=minimal_df)
        assert traj.has_confdata is False

    def test_has_move_type_true(self, simple_trajectory: Trajectory) -> None:
        """``has_move_type`` is ``True`` when ``move_type`` is present."""
        assert simple_trajectory.has_move_type is True

    def test_has_tool_table_true(self, simple_trajectory: Trajectory) -> None:
        """``has_tool_table`` is ``True`` when ``tools`` is non-empty and ``tool_index`` is present."""
        assert simple_trajectory.has_tool_table is True

    def test_has_tool_table_false_no_tools(
        self, minimal_meta: TrajectoryMeta, complete_df: pd.DataFrame
    ) -> None:
        """``has_tool_table`` is ``False`` when ``tools`` is empty."""
        traj = Trajectory(meta=minimal_meta, points=complete_df)
        assert traj.has_tool_table is False

    def test_has_wobj_table_true(self, simple_trajectory: Trajectory) -> None:
        """``has_wobj_table`` is ``True`` when ``wobjs`` is non-empty and ``wobj_index`` is present."""
        assert simple_trajectory.has_wobj_table is True

    def test_is_complete_true(self, simple_trajectory: Trajectory) -> None:
        """``is_complete`` is ``True`` when all ``CONVERTER_COLUMNS`` are present."""
        assert simple_trajectory.is_complete is True

    def test_is_complete_false(
        self, minimal_meta: TrajectoryMeta, minimal_df: pd.DataFrame
    ) -> None:
        """``is_complete`` is ``False`` when some ``CONVERTER_COLUMNS`` are absent."""
        traj = Trajectory(meta=minimal_meta, points=minimal_df)
        assert traj.is_complete is False

    def test_repr(self, simple_trajectory: Trajectory) -> None:
        """``__repr__`` contains the key trajectory information."""
        r = repr(simple_trajectory)
        assert "test_traj" in r
        assert "points=2" in r
        assert "tools=1" in r
        assert "wobjs=1" in r
        assert "complete=True" in r


# ---------------------------------------------------------------------------
# Tests — save / load
# ---------------------------------------------------------------------------


class TestTrajectorySaveLoad:
    """Tests for ``.trajcenter`` serialisation / deserialisation."""

    def test_save_creates_file(
        self, tmp_path: Path, simple_trajectory: Trajectory
    ) -> None:
        """``save()`` creates the ``.trajcenter`` file."""
        dest = tmp_path / "test.trajcenter"
        result = simple_trajectory.save(dest)
        assert result.exists()
        assert result.suffix == ".trajcenter"

    def test_save_returns_absolute_path(
        self, tmp_path: Path, simple_trajectory: Trajectory
    ) -> None:
        """``save()`` returns an absolute path."""
        dest = tmp_path / "test.trajcenter"
        result = simple_trajectory.save(dest)
        assert result.is_absolute()

    def test_save_creates_parent_dirs(
        self, tmp_path: Path, simple_trajectory: Trajectory
    ) -> None:
        """``save()`` creates parent directories when they do not exist."""
        dest = tmp_path / "subdir" / "nested" / "test.trajcenter"
        simple_trajectory.save(dest)
        assert dest.exists()

    def test_save_zip_contains_required_entries(
        self, tmp_path: Path, simple_trajectory: Trajectory
    ) -> None:
        """The ZIP archive contains the four expected entries."""
        dest = tmp_path / "test.trajcenter"
        simple_trajectory.save(dest)
        with zipfile.ZipFile(dest, "r") as zf:
            names = set(zf.namelist())
        assert "meta.json" in names
        assert "points.parquet" in names
        assert "tools.json" in names
        assert "wobjs.json" in names

    def test_save_updates_point_count(
        self, tmp_path: Path, simple_trajectory: Trajectory
    ) -> None:
        """``save()`` updates ``meta.point_count`` before writing."""
        dest = tmp_path / "test.trajcenter"
        simple_trajectory.save(dest)
        with zipfile.ZipFile(dest, "r") as zf:
            meta_raw = json.loads(zf.read("meta.json"))
        assert meta_raw["point_count"] == 2

    def test_save_tools_wobjs_json(
        self, tmp_path: Path, simple_trajectory: Trajectory
    ) -> None:
        """``tools.json`` and ``wobjs.json`` contain the correct lists."""
        dest = tmp_path / "test.trajcenter"
        simple_trajectory.save(dest)
        with zipfile.ZipFile(dest, "r") as zf:
            tools = json.loads(zf.read("tools.json"))
            wobjs = json.loads(zf.read("wobjs.json"))
        assert tools == ["Tool_formage"]
        assert wobjs == ["Wobj_SerreFlan"]

    def test_load_roundtrip(
        self, tmp_path: Path, simple_trajectory: Trajectory
    ) -> None:
        """``save()`` + ``load()`` reconstruct an identical trajectory."""
        dest = tmp_path / "test.trajcenter"
        simple_trajectory.save(dest)
        loaded = Trajectory.load(dest)

        assert loaded.meta.name == simple_trajectory.meta.name
        assert loaded.point_count == simple_trajectory.point_count
        assert loaded.tools == simple_trajectory.tools
        assert loaded.wobjs == simple_trajectory.wobjs
        assert set(loaded.points.columns) == set(simple_trajectory.points.columns)

    def test_load_points_values(
        self, tmp_path: Path, simple_trajectory: Trajectory
    ) -> None:
        """Numeric values are preserved after save/load."""
        dest = tmp_path / "test.trajcenter"
        simple_trajectory.save(dest)
        loaded = Trajectory.load(dest)
        pd.testing.assert_series_equal(
            loaded.points["x"].reset_index(drop=True),
            simple_trajectory.points["x"].reset_index(drop=True),
            check_names=False,
        )

    def test_load_autocompleted_preserved(
        self, tmp_path: Path, complete_df: pd.DataFrame
    ) -> None:
        """The ``autocompleted`` field is preserved after save/load."""
        meta = TrajectoryMeta(
            name="traj",
            autocompleted=["speed", "move_type"],
        )
        traj = Trajectory(
            meta=meta,
            points=complete_df,
            tools=["Tool_formage"],
            wobjs=["Wobj_SerreFlan"],
        )
        dest = tmp_path / "traj.trajcenter"
        traj.save(dest)
        loaded = Trajectory.load(dest)
        assert loaded.meta.autocompleted == ["speed", "move_type"]

    def test_load_file_not_found_raises(self, tmp_path: Path) -> None:
        """``Trajectory.load()`` raises ``FileNotFoundError`` on missing file."""
        with pytest.raises(FileNotFoundError, match=r"[Ff]ile not found|introuvable"):
            Trajectory.load(tmp_path / "inexistant.trajcenter")

    def test_load_invalid_archive_raises(self, tmp_path: Path) -> None:
        """``Trajectory.load()`` raises ``ValueError`` on a corrupt archive."""
        bad = tmp_path / "bad.trajcenter"
        bad.write_bytes(b"not a zip")
        with pytest.raises(
            (ValueError, zipfile.BadZipFile), match=r"[Ii]nvalid|[Cc]orrupt|archive"
        ):
            Trajectory.load(bad)

    def test_load_backward_compat_no_tools_wobjs(
        self,
        tmp_path: Path,
        minimal_meta: TrajectoryMeta,
        complete_df: pd.DataFrame,
    ) -> None:
        """``load()`` tolerates missing ``tools.json`` and ``wobjs.json`` (legacy files)."""
        dest = tmp_path / "old.trajcenter"
        traj = Trajectory(meta=minimal_meta, points=complete_df)
        with zipfile.ZipFile(dest, "w") as zf:
            zf.writestr("meta.json", traj.meta.model_dump_json())
            buf = io.BytesIO()
            table = pa.Table.from_pandas(traj.points, preserve_index=False)
            pq.write_table(table, buf, compression="zstd")
            zf.writestr("points.parquet", buf.getvalue())
        loaded = Trajectory.load(dest)
        assert loaded.tools == []
        assert loaded.wobjs == []

    def test_save_with_eax(
        self,
        tmp_path: Path,
        minimal_meta: TrajectoryMeta,
        complete_df_with_eax: pd.DataFrame,
    ) -> None:
        """``eax_*`` columns are preserved after save/load."""
        traj = Trajectory(
            meta=minimal_meta,
            points=complete_df_with_eax,
            tools=["Tool_formage"],
            wobjs=["Wobj_SerreFlan"],
        )
        dest = tmp_path / "eax.trajcenter"
        traj.save(dest)
        loaded = Trajectory.load(dest)
        assert "eax_a" in loaded.points.columns
        assert loaded.points["eax_a"].iloc[0] == pytest.approx(45.0)
