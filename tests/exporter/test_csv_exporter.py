#!/usr/bin/env python3
# tests/exporter/test_csv_exporter.py
"""Integration tests for :class:`~trajcenter.exporter.csv_exporter.CsvExporter`.

Author: Clement RACINET

Verifies the 4 produced files and the import/export symmetry with
:class:`~trajcenter.converter.csv_converter.CsvConverter`.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from trajcenter.converter.csv_converter import CsvConverter
from trajcenter.core.trajectory import Trajectory
from trajcenter.exporter.csv_exporter import CsvExporter
from trajcenter.exporter.options import ExportOptions


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _export(
    traj: Trajectory,
    dest: Path,
    options: ExportOptions | None = None,
) -> Path:
    """Run ``CsvExporter.export()`` and return the produced file path.

    Args:
        traj: Source trajectory to export.
        dest: Destination directory.
        options: Optional export options. Uses defaults when ``None``.

    Returns:
        Absolute path to the main exported CSV file.
    """
    return CsvExporter(options).export(traj, dest)


# ---------------------------------------------------------------------------
# Produced files
# ---------------------------------------------------------------------------


class TestCsvExporterOutput:
    """Tests verifying that the expected output files are created."""

    def test_main_csv_exists(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        """The main CSV file is created."""
        path = _export(traj_basic, tmp_path)
        assert path.exists()

    def test_main_csv_suffix(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        """The main file has a ``.csv`` extension."""
        path = _export(traj_basic, tmp_path)
        assert path.suffix == ".csv"

    def test_main_filename_matches_traj_name(
        self, traj_basic: Trajectory, tmp_path: Path
    ) -> None:
        """The main file stem matches the trajectory name."""
        path = _export(traj_basic, tmp_path)
        assert path.stem == traj_basic.meta.name

    def test_tools_csv_exists(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        """The ``<name>_tools.csv`` file is created."""
        _export(traj_basic, tmp_path)
        assert (tmp_path / f"{traj_basic.meta.name}_tools.csv").exists()

    def test_wobjs_csv_exists(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        """The ``<name>_wobjs.csv`` file is created."""
        _export(traj_basic, tmp_path)
        assert (tmp_path / f"{traj_basic.meta.name}_wobjs.csv").exists()

    def test_meta_csv_exists_by_default(
        self, traj_basic: Trajectory, tmp_path: Path
    ) -> None:
        """The ``<name>_meta.csv`` file is created by default."""
        _export(traj_basic, tmp_path)
        assert (tmp_path / f"{traj_basic.meta.name}_meta.csv").exists()

    def test_meta_csv_absent_when_disabled(
        self, traj_basic: Trajectory, tmp_path: Path
    ) -> None:
        """The ``<name>_meta.csv`` file is not created when ``include_meta=False``."""
        opts = ExportOptions(include_meta=False)
        _export(traj_basic, tmp_path, opts)
        assert not (tmp_path / f"{traj_basic.meta.name}_meta.csv").exists()

    def test_dest_dir_created_if_absent(
        self, traj_basic: Trajectory, tmp_path: Path
    ) -> None:
        """The destination directory is created when it does not exist."""
        dest = tmp_path / "nested" / "output"
        path = _export(traj_basic, dest)
        assert path.exists()

    def test_returns_absolute_path(
        self, traj_basic: Trajectory, tmp_path: Path
    ) -> None:
        """``export()`` returns an absolute path."""
        path = _export(traj_basic, tmp_path)
        assert path.is_absolute()


# ---------------------------------------------------------------------------
# Main file content
# ---------------------------------------------------------------------------


class TestCsvExporterMainFile:
    """Tests verifying the content of the main exported CSV file."""

    def test_row_count(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        """The exported file contains the same number of rows as the trajectory."""
        path = _export(traj_basic, tmp_path)
        df = pd.read_csv(path)
        assert len(df) == len(traj_basic.points)

    def test_xyz_columns_present(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        """The x, y, z columns are present in the exported file."""
        path = _export(traj_basic, tmp_path)
        df = pd.read_csv(path)
        for col in ["x", "y", "z"]:
            assert col in df.columns

    def test_tool_column_resolved(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        """The ``tool`` column contains string names, not integer indices."""
        path = _export(traj_basic, tmp_path)
        df = pd.read_csv(path)
        assert "tool" in df.columns
        # StringDtype (pandas 2.x) or object (pandas 1.x) — both are strings
        assert not pd.api.types.is_integer_dtype(df["tool"])
        assert df["tool"].iloc[0] == "tool0"

    def test_tool_index_not_present(
        self, traj_basic: Trajectory, tmp_path: Path
    ) -> None:
        """The raw ``tool_index`` column is not present in the exported file."""
        path = _export(traj_basic, tmp_path)
        df = pd.read_csv(path)
        assert "tool_index" not in df.columns

    def test_wobj_index_not_present(
        self, traj_basic: Trajectory, tmp_path: Path
    ) -> None:
        """The raw ``wobj_index`` column is not present in the exported file."""
        path = _export(traj_basic, tmp_path)
        df = pd.read_csv(path)
        assert "wobj_index" not in df.columns

    def test_multi_tools_names_in_main(
        self, traj_multi_tools: Trajectory, tmp_path: Path
    ) -> None:
        """All tool names appear in the main file when multiple tools are used."""
        path = _export(traj_multi_tools, tmp_path)
        df = pd.read_csv(path)
        assert set(df["tool"].unique()) == {"Tool_A", "Tool_B"}


# ---------------------------------------------------------------------------
# Encoding and separator
# ---------------------------------------------------------------------------


class TestCsvExporterEncoding:
    """Tests verifying encoding and separator options."""

    def test_default_encoding_utf8_sig(
        self, traj_basic: Trajectory, tmp_path: Path
    ) -> None:
        """The default output is encoded as UTF-8 with BOM (``utf-8-sig``)."""
        path = _export(traj_basic, tmp_path)
        raw = path.read_bytes()
        assert raw[:3] == b"\xef\xbb\xbf", "UTF-8 BOM expected"

    def test_custom_separator_semicolon(
        self, traj_basic: Trajectory, tmp_path: Path
    ) -> None:
        """A semicolon separator produces a readable CSV when parsed with ``sep=';'``."""
        opts = ExportOptions(csv_separator=";")
        path = _export(traj_basic, tmp_path, opts)
        df = pd.read_csv(path, sep=";", encoding="utf-8-sig")
        assert "x" in df.columns

    def test_custom_encoding_utf8(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        """Specifying ``utf-8`` encoding produces a file without a BOM."""
        opts = ExportOptions(csv_encoding="utf-8")
        path = _export(traj_basic, tmp_path, opts)
        raw = path.read_bytes()
        assert raw[:3] != b"\xef\xbb\xbf", "No BOM expected with utf-8"


# ---------------------------------------------------------------------------
# tools / wobjs files
# ---------------------------------------------------------------------------


class TestCsvExporterToolsWobjsFiles:
    """Tests verifying the content of the tools and wobjs CSV files."""

    def test_tools_file_name_column(
        self, traj_basic: Trajectory, tmp_path: Path
    ) -> None:
        """The tools file contains a ``name`` column."""
        _export(traj_basic, tmp_path)
        df = pd.read_csv(
            tmp_path / f"{traj_basic.meta.name}_tools.csv",
            encoding="utf-8-sig",
        )
        assert "name" in df.columns

    def test_tools_file_single_tool(
        self, traj_basic: Trajectory, tmp_path: Path
    ) -> None:
        """The tools file lists the single tool name correctly."""
        _export(traj_basic, tmp_path)
        df = pd.read_csv(
            tmp_path / f"{traj_basic.meta.name}_tools.csv",
            encoding="utf-8-sig",
        )
        assert df["name"].tolist() == ["tool0"]

    def test_tools_file_multi_tools(
        self, traj_multi_tools: Trajectory, tmp_path: Path
    ) -> None:
        """The tools file lists all tool names in order."""
        _export(traj_multi_tools, tmp_path)
        df = pd.read_csv(
            tmp_path / f"{traj_multi_tools.meta.name}_tools.csv",
            encoding="utf-8-sig",
        )
        assert df["name"].tolist() == ["Tool_A", "Tool_B"]

    def test_wobjs_file_single_wobj(
        self, traj_basic: Trajectory, tmp_path: Path
    ) -> None:
        """The wobjs file lists the single wobj name correctly."""
        _export(traj_basic, tmp_path)
        df = pd.read_csv(
            tmp_path / f"{traj_basic.meta.name}_wobjs.csv",
            encoding="utf-8-sig",
        )
        assert df["name"].tolist() == ["wobj0"]


# ---------------------------------------------------------------------------
# Meta file
# ---------------------------------------------------------------------------


class TestCsvExporterMetaFile:
    """Tests verifying the content of the metadata CSV file."""

    def test_meta_has_key_value_columns(
        self, traj_with_meta: Trajectory, tmp_path: Path
    ) -> None:
        """The meta file contains ``key`` and ``value`` columns."""
        _export(traj_with_meta, tmp_path)
        df = pd.read_csv(
            tmp_path / f"{traj_with_meta.meta.name}_meta.csv",
            encoding="utf-8-sig",
        )
        assert "key" in df.columns
        assert "value" in df.columns

    def test_meta_name_present(
        self, traj_with_meta: Trajectory, tmp_path: Path
    ) -> None:
        """The trajectory name is present in the meta file."""
        _export(traj_with_meta, tmp_path)
        df = pd.read_csv(
            tmp_path / f"{traj_with_meta.meta.name}_meta.csv",
            encoding="utf-8-sig",
        )
        assert "name" in df["key"].values

    def test_meta_extra_author(
        self, traj_with_meta: Trajectory, tmp_path: Path
    ) -> None:
        """The ``author`` extra field is correctly written to the meta file."""
        _export(traj_with_meta, tmp_path)
        df = pd.read_csv(
            tmp_path / f"{traj_with_meta.meta.name}_meta.csv",
            encoding="utf-8-sig",
        )
        row = df[df["key"] == "author"]
        assert row["value"].iloc[0] == "Jean Dupont"


# ---------------------------------------------------------------------------
# Export → import symmetry (roundtrip)
# ---------------------------------------------------------------------------


class TestCsvExporterRoundtrip:
    """Tests verifying the export → import roundtrip symmetry."""

    def test_roundtrip_point_count(
        self, traj_basic: Trajectory, tmp_path: Path
    ) -> None:
        """Reloading the exported CSV produces the same number of points."""
        path = _export(traj_basic, tmp_path)
        reloaded = CsvConverter().convert(path)
        assert len(reloaded.points) == len(traj_basic.points)

    def test_roundtrip_xyz_values(self, traj_basic: Trajectory, tmp_path: Path) -> None:
        """x, y, z values are preserved after export → import."""
        path = _export(traj_basic, tmp_path)
        reloaded = CsvConverter().convert(path)
        for col in ["x", "y", "z"]:
            pd.testing.assert_series_equal(
                reloaded.points[col].reset_index(drop=True),
                traj_basic.points[col].reset_index(drop=True),
                check_names=False,
                atol=1e-4,
            )

    def test_roundtrip_tool_names(
        self, traj_multi_tools: Trajectory, tmp_path: Path
    ) -> None:
        """Tool names are preserved after export → import roundtrip."""
        path = _export(traj_multi_tools, tmp_path)
        reloaded = CsvConverter().convert(path)
        assert reloaded.tools == traj_multi_tools.tools

    def test_roundtrip_wobj_names(
        self, traj_multi_tools: Trajectory, tmp_path: Path
    ) -> None:
        """Wobj names are preserved after export → import roundtrip."""
        path = _export(traj_multi_tools, tmp_path)
        reloaded = CsvConverter().convert(path)
        assert reloaded.wobjs == traj_multi_tools.wobjs
