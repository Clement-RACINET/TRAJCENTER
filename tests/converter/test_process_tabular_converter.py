#!/usr/bin/env python3
# tests/converter/test_process_tabular_converter.py
"""Process import tests for tabular converters.

Author: Clement RACINET

These tests validate process-aware imports from Excel workbooks and CSV
sidecars:

- ``meta`` sheet/sidecar with ``process_type`` and
  ``process_param_names``;
- ``process_param_index`` in point tables;
- ``process_params`` sheet/sidecar;
- strict validation errors when process data is incomplete.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from trajcenter.converter.csv_converter import CsvConverter
from trajcenter.converter.excel_converter import ExcelConverter
from trajcenter.core.trajectory import Trajectory


def _write_process_workbook(
    path: Path,
    *,
    include_process_params: bool = True,
    include_process_param_index: bool = True,
    process_param_names: str = "force;travel_speed",
) -> Path:
    """Write an Excel workbook with optional process data.

    ABB Route:
        N/A — test helper.

    ABB Constraints:
        No ABB controller access.

    Args:
        path: Workbook destination path.
        include_process_params: Whether to write the ``process_params`` sheet.
        include_process_param_index: Whether to include point process indexes.
        process_param_names: Metadata value for process parameter names.

    Returns:
        Created workbook path.

    Raises:
        OSError: If the workbook cannot be written.

    Example:
        ::

            path = _write_process_workbook(tmp_path / "process.xlsx")
    """
    traj_data: dict[str, list[float | int]] = {
        "x": [100.0, 200.0, 300.0],
        "y": [10.0, 20.0, 30.0],
        "z": [1.0, 2.0, 3.0],
        "q1": [1.0, 1.0, 1.0],
        "q2": [0.0, 0.0, 0.0],
        "q3": [0.0, 0.0, 0.0],
        "q4": [0.0, 0.0, 0.0],
    }
    if include_process_param_index:
        traj_data["process_param_index"] = [1, 2, 0]

    meta_df = pd.DataFrame(
        {
            "key": ["name", "process_type", "process_param_names"],
            "value": ["process_excel", "1", process_param_names],
        }
    )
    traj_df = pd.DataFrame(traj_data)
    process_params_df = pd.DataFrame(
        {
            "process_param_index": [1, 2],
            "force": [120.0, 150.0],
            "travel_speed": [35.0, 40.0],
        }
    )

    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        traj_df.to_excel(writer, sheet_name="traj", index=False)
        meta_df.to_excel(writer, sheet_name="meta", index=False)
        if include_process_params:
            process_params_df.to_excel(
                writer,
                sheet_name="process_params",
                index=False,
            )

    return path


def _write_process_csv_set(
    path: Path,
    *,
    include_meta: bool = True,
    include_process_params: bool = True,
    include_process_param_index: bool = True,
    process_param_names: str = "force;travel_speed",
) -> Path:
    """Write a CSV file with optional process sidecars.

    ABB Route:
        N/A — test helper.

    ABB Constraints:
        No ABB controller access.

    Args:
        path: Main CSV destination path.
        include_meta: Whether to write ``{stem}_meta.csv``.
        include_process_params: Whether to write
            ``{stem}_process_params.csv``.
        include_process_param_index: Whether to include point process
            indexes in the main CSV.
        process_param_names: Metadata value for process parameter names.

    Returns:
        Main CSV path.

    Raises:
        OSError: If a CSV file cannot be written.

    Example:
        ::

            path = _write_process_csv_set(tmp_path / "process.csv")
    """
    traj_data: dict[str, list[float | int]] = {
        "x": [100.0, 200.0, 300.0],
        "y": [10.0, 20.0, 30.0],
        "z": [1.0, 2.0, 3.0],
        "q1": [1.0, 1.0, 1.0],
        "q2": [0.0, 0.0, 0.0],
        "q3": [0.0, 0.0, 0.0],
        "q4": [0.0, 0.0, 0.0],
    }
    if include_process_param_index:
        traj_data["process_param_index"] = [1, 2, 0]

    pd.DataFrame(traj_data).to_csv(path, index=False, encoding="utf-8")

    if include_meta:
        pd.DataFrame(
            {
                "key": ["name", "process_type", "process_param_names"],
                "value": ["process_csv", "1", process_param_names],
            }
        ).to_csv(
            path.with_name(f"{path.stem}_meta.csv"),
            index=False,
            encoding="utf-8",
        )

    if include_process_params:
        pd.DataFrame(
            {
                "process_param_index": [1, 2],
                "force": [120.0, 150.0],
                "travel_speed": [35.0, 40.0],
            }
        ).to_csv(
            path.with_name(f"{path.stem}_process_params.csv"),
            index=False,
            encoding="utf-8",
        )

    return path


class TestExcelProcessImport:
    """Tests for Excel process import."""

    def test_excel_import_process_workbook(self, tmp_path: Path) -> None:
        """A complete process workbook is imported as a process trajectory."""
        path = _write_process_workbook(tmp_path / "process.xlsx")

        with pytest.warns(UserWarning, match="force|travel_speed|Unknown|inconnue"):
            traj = ExcelConverter().convert(path)

        assert traj.meta.name == "process_excel"
        assert traj.has_process is True
        assert traj.has_process_params is True
        assert traj.meta.process.process_type == 1
        assert traj.meta.process.process_param_names == ["force", "travel_speed"]
        assert "process_param_index" in traj.points.columns
        assert traj.points["process_param_index"].tolist() == [1, 2, 0]
        assert traj.process_params is not None
        assert traj.process_params["force"].tolist() == pytest.approx([120.0, 150.0])
        assert traj.process_params["travel_speed"].tolist() == pytest.approx(
            [35.0, 40.0]
        )

    def test_excel_import_process_missing_params_fails(
        self,
        tmp_path: Path,
    ) -> None:
        """An active process without process_params sheet raises ValueError."""
        path = _write_process_workbook(
            tmp_path / "process_missing_params.xlsx",
            include_process_params=False,
        )

        with pytest.raises(ValueError, match="process_params is required"):
            ExcelConverter().convert(path)

    def test_excel_import_process_missing_index_fails(
        self,
        tmp_path: Path,
    ) -> None:
        """An active process without point process_param_index raises ValueError."""
        path = _write_process_workbook(
            tmp_path / "process_missing_index.xlsx",
            include_process_param_index=False,
        )

        with pytest.warns(UserWarning, match="force|travel_speed|Unknown|inconnue"):
            with pytest.raises(ValueError, match="process_param_index"):
                ExcelConverter().convert(path)

    def test_excel_import_process_missing_param_names_fails(
        self,
        tmp_path: Path,
    ) -> None:
        """An active process without process_param_names raises ValueError."""
        path = _write_process_workbook(
            tmp_path / "process_missing_names.xlsx",
            process_param_names="",
        )

        with pytest.warns(UserWarning, match="force|travel_speed|Unknown|inconnue"):
            with pytest.raises(ValueError, match="process_param_names"):
                ExcelConverter().convert(path)

    def test_excel_process_save_load_roundtrip(self, tmp_path: Path) -> None:
        """Imported Excel process trajectory survives .trajcenter save/load."""
        path = _write_process_workbook(tmp_path / "process.xlsx")

        with pytest.warns(UserWarning, match="force|travel_speed|Unknown|inconnue"):
            traj = ExcelConverter().convert(path)

        archive = tmp_path / "process.trajcenter"
        traj.save(archive)
        loaded = Trajectory.load(archive)

        assert loaded.has_process is True
        assert loaded.meta.process.process_type == 1
        assert loaded.meta.process.process_param_names == ["force", "travel_speed"]
        assert loaded.process_params is not None
        assert loaded.process_params["process_param_index"].tolist() == [1, 2]


class TestCsvProcessImport:
    """Tests for CSV process import through sidecars."""

    def test_csv_import_process_sidecars(self, tmp_path: Path) -> None:
        """A complete CSV process set is imported as a process trajectory."""
        path = _write_process_csv_set(tmp_path / "process.csv")

        with pytest.warns(UserWarning, match="force|travel_speed|Unknown|inconnue"):
            traj = CsvConverter().convert(path)

        assert traj.meta.name == "process_csv"
        assert traj.has_process is True
        assert traj.has_process_params is True
        assert traj.meta.process.process_type == 1
        assert traj.meta.process.process_param_names == ["force", "travel_speed"]
        assert "process_param_index" in traj.points.columns
        assert traj.points["process_param_index"].tolist() == [1, 2, 0]
        assert traj.process_params is not None
        assert traj.process_params["force"].tolist() == pytest.approx([120.0, 150.0])

    def test_csv_import_process_missing_process_sidecar_fails(
        self,
        tmp_path: Path,
    ) -> None:
        """An active CSV process without process sidecar raises ValueError."""
        path = _write_process_csv_set(
            tmp_path / "process.csv",
            include_process_params=False,
        )

        with pytest.raises(ValueError, match="process_params is required"):
            CsvConverter().convert(path)

    def test_csv_import_process_missing_meta_is_no_process(
        self,
        tmp_path: Path,
    ) -> None:
        """Without meta sidecar, process_params sidecar alone is rejected by core."""
        path = _write_process_csv_set(
            tmp_path / "process.csv",
            include_meta=False,
            include_process_params=True,
        )

        with pytest.warns(UserWarning, match="force|travel_speed|Unknown|inconnue"):
            with pytest.raises(ValueError, match="process_type is 0"):
                CsvConverter().convert(path)

    def test_csv_import_process_missing_index_fails(self, tmp_path: Path) -> None:
        """An active CSV process without point process_param_index raises."""
        path = _write_process_csv_set(
            tmp_path / "process.csv",
            include_process_param_index=False,
        )

        with pytest.warns(UserWarning, match="force|travel_speed|Unknown|inconnue"):
            with pytest.raises(ValueError, match="process_param_index"):
                CsvConverter().convert(path)

    def test_csv_import_process_missing_param_names_fails(
        self,
        tmp_path: Path,
    ) -> None:
        """An active CSV process without process_param_names raises ValueError."""
        path = _write_process_csv_set(
            tmp_path / "process.csv",
            process_param_names="",
        )

        with pytest.warns(UserWarning, match="force|travel_speed|Unknown|inconnue"):
            with pytest.raises(ValueError, match="process_param_names"):
                CsvConverter().convert(path)

    def test_csv_process_save_load_roundtrip(self, tmp_path: Path) -> None:
        """Imported CSV process trajectory survives .trajcenter save/load."""
        path = _write_process_csv_set(tmp_path / "process.csv")

        with pytest.warns(UserWarning, match="force|travel_speed|Unknown|inconnue"):
            traj = CsvConverter().convert(path)

        archive = tmp_path / "process.trajcenter"
        traj.save(archive)
        loaded = Trajectory.load(archive)

        assert loaded.has_process is True
        assert loaded.meta.process.process_type == 1
        assert loaded.meta.process.process_param_names == ["force", "travel_speed"]
        assert loaded.process_params is not None
        assert loaded.process_params["process_param_index"].tolist() == [1, 2]
