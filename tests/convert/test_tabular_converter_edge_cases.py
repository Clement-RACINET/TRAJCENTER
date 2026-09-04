#!/usr/bin/env python3
# tests/convert/test_tabular_converter_edge_cases.py
"""Edge-case tests for :mod:`trajcenter.convert.tabular_converter`.

> **Author**: Clément RACINET

These tests target branch coverage for shared tabular conversion logic:
metadata parsing, literal parsing, boolean parsing, process sheet
selection and multi-sheet conversion.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from trajcenter.convert.csv_converter import CsvConverter
from trajcenter.convert.tabular_converter import _TabularConverter
from trajcenter.core.trajectory import SourceFormat


def _write_csv(path: Path, content: str) -> Path:
    """Write CSV content to disk.

    ABB Route:
        N/A — test helper.

    ABB Constraints:
        No ABB controller access.

    Args:
        path: Destination path.
        content: CSV text.

    Returns:
        Written path.

    Raises:
        OSError: If writing fails.

    Example:
        ::

            path = _write_csv(tmp_path / "a.csv", "x,y,z\\n1,2,3\\n")
    """
    path.write_text(content, encoding="utf-8")
    return path


class _ReservedOnlyConverter(_TabularConverter):
    """Concrete test converter returning only reserved sheets."""

    @property
    def _source_format(self) -> SourceFormat:
        """Return dummy CSV source format.

        ABB Route:
            N/A — test helper.

        ABB Constraints:
            No ABB controller access.


        Returns:
            CSV source format.


        Example:
            ::

                fmt = converter._source_format
        """
        return SourceFormat.CSV

    def _read_sheets(self, source: Path) -> dict[str, pd.DataFrame]:
        """Return only reserved sheets.

        ABB Route:
            N/A — test helper.

        ABB Constraints:
            No ABB controller access.

        Args:
            source: Ignored source path.

        Returns:
            Mapping containing only a reserved meta sheet.


        Example:
            ::

                sheets = converter._read_sheets(Path("dummy.csv"))
        """
        return {
            "meta": pd.DataFrame(
                {
                    "key": ["name"],
                    "value": ["demo"],
                }
            )
        }


class TestTabularConvertErrors:
    """Tests for converter high-level error branches."""

    def test_convert_no_trajectory_sheet_raises(self, tmp_path: Path) -> None:
        """A source containing only reserved sheets has no trajectory sheet."""
        source = tmp_path / "dummy.csv"
        source.write_text("ignored", encoding="utf-8")

        with pytest.raises(ValueError, match="No trajectory sheet"):
            _ReservedOnlyConverter().convert(source)

    def test_csv_sidecar_meta_loaded(self, tmp_path: Path) -> None:
        """CSV meta sidecar overrides trajectory metadata."""
        main = _write_csv(tmp_path / "traj.csv", "x,y,z\n1,2,3\n")
        (tmp_path / "traj_meta.csv").write_text(
            "key,value\nname,sidecar_name\nrobot_model,IRB6700\n",
            encoding="utf-8",
        )

        traj = CsvConverter().convert(main)

        assert traj.meta.name == "sidecar_name"
        assert traj.meta.robot_model == "IRB6700"

    def test_csv_process_sidecar_without_meta_raises(self, tmp_path: Path) -> None:
        """process_params sidecar alone is rejected because process_type is zero."""
        main = _write_csv(
            tmp_path / "traj.csv",
            "x,y,z,process_param_index\n1,2,3,1\n",
        )
        (tmp_path / "traj_process_params.csv").write_text(
            "process_param_index,force\n1,120.0\n",
            encoding="utf-8",
        )

        with (
            pytest.warns(UserWarning, match="force|Unknown|inconnue"),
            pytest.raises(ValueError, match="process_type is 0"),
        ):
            CsvConverter().convert(main)


class TestTabularValueParsers:
    """Tests for shared literal parser edge cases."""

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("v500", 500.0),
            ("V250,5", 250.5),
            ("750.25", 750.25),
            (100, 100.0),
            (100.5, 100.5),
            ("", None),
            (None, None),
        ],
    )
    def test_parse_tcp_speed_valid(self, value: object, expected: float | None) -> None:
        """Valid TCP speed values are parsed."""
        result = _TabularConverter._parse_tcp_speed(value)
        if expected is None:
            assert result is None
        else:
            assert result == pytest.approx(expected)

    def test_parse_tcp_speed_invalid_raises(self) -> None:
        """Invalid TCP speed literal raises ValueError."""
        with pytest.raises(ValueError, match="Invalid tcp_speed"):
            _TabularConverter._parse_tcp_speed("vitesse")

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("z10", 10),
            ("Z-1", -1),
            ("fine", 255),
            ("255", 255),
            (10, 10),
            (10.0, 10),
            ("", None),
            (None, None),
        ],
    )
    def test_parse_zone_type_valid(self, value: object, expected: int | None) -> None:
        """Valid zone values are parsed."""
        assert _TabularConverter._parse_zone_type(value) == expected

    def test_parse_zone_type_invalid_float_raises(self) -> None:
        """Non-integer float zone raises ValueError."""
        with pytest.raises(ValueError, match="Invalid zone_type"):
            _TabularConverter._parse_zone_type(10.5)

    def test_parse_zone_type_invalid_text_raises(self) -> None:
        """Invalid zone literal raises ValueError."""
        with pytest.raises(ValueError, match="Invalid zone_type"):
            _TabularConverter._parse_zone_type("ma_zone")

    def test_parse_zone_type_numeric_text_non_integer_raises(self) -> None:
        """Numeric text that is not an integer zone raises ValueError."""
        with pytest.raises(ValueError, match="Invalid zone_type"):
            _TabularConverter._parse_zone_type("10.5")

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            ("true", True),
            ("t", True),
            ("yes", True),
            ("y", True),
            ("oui", True),
            ("o", True),
            ("1", True),
            (1, True),
            (1.0, True),
            ("false", False),
            ("f", False),
            ("no", False),
            ("n", False),
            ("non", False),
            ("0", False),
            (0, False),
            (0.0, False),
            ("", None),
            (None, None),
        ],
    )
    def test_parse_bool_like_valid(self, value: object, expected: bool | None) -> None:
        """Boolean-like values are parsed."""
        assert _TabularConverter._parse_bool_like(value) is expected

    def test_parse_bool_like_invalid_raises(self) -> None:
        """Invalid boolean-like value raises ValueError."""
        with pytest.raises(ValueError, match="Invalid readconfs"):
            _TabularConverter._parse_bool_like("maybe")

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (None, 0),
            ("", 0),
            ("  ", 0),
            ("1", 1),
            (" 2 ", 2),
        ],
    )
    def test_parse_process_type_valid(self, value: str | None, expected: int) -> None:
        """Valid process_type metadata is parsed."""
        assert _TabularConverter._parse_process_type(value) == expected

    def test_parse_process_type_invalid_raises(self) -> None:
        """Invalid process_type metadata raises ValueError."""
        with pytest.raises(ValueError, match="Invalid process_type"):
            _TabularConverter._parse_process_type("abc")

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (None, []),
            ("", []),
            ("force;travel_speed", ["force", "travel_speed"]),
            ("force,travel_speed", ["force", "travel_speed"]),
            ("force|travel_speed", ["force", "travel_speed"]),
            (" force ; travel_speed ", ["force", "travel_speed"]),
        ],
    )
    def test_parse_process_param_names(
        self,
        value: str | None,
        expected: list[str],
    ) -> None:
        """process_param_names supports several separators."""
        assert _TabularConverter._parse_process_param_names(value) == expected


class TestTabularMetaExtraction:
    """Tests for metadata extraction branches."""

    def test_extract_meta_empty_when_no_meta_sheet(self) -> None:
        """No meta sheet returns an empty metadata dictionary."""
        sheets = {"traj": pd.DataFrame({"x": [1.0], "y": [2.0], "z": [3.0]})}

        assert _TabularConverter._extract_meta(sheets) == {}

    def test_extract_meta_ignores_malformed_meta_sheet(self) -> None:
        """A meta sheet without key/value columns is ignored."""
        sheets = {"meta": pd.DataFrame({"foo": ["name"], "bar": ["demo"]})}

        assert _TabularConverter._extract_meta(sheets) == {}

    def test_extract_meta_cleans_empty_values(self) -> None:
        """Empty metadata values are converted to empty strings."""
        sheets = {
            "meta": pd.DataFrame(
                {
                    "key": ["name", "robot_model", None],
                    "value": [" demo ", None, "ignored"],
                }
            )
        }

        assert _TabularConverter._extract_meta(sheets) == {
            "name": "demo",
            "robot_model": "",
        }

    def test_clean_meta_value_handles_non_empty_value(self) -> None:
        """Metadata cell values are stripped and stringified."""
        assert _TabularConverter._clean_meta_value(" demo ") == "demo"
        assert _TabularConverter._clean_meta_value(123) == "123"


class TestTabularProcessParamExtraction:
    """Tests for process parameter sheet extraction branches."""

    def test_extract_process_params_absent_returns_none(self) -> None:
        """Missing process_params sheet returns None."""
        sheets = {"traj": pd.DataFrame({"x": [1.0]})}

        assert _TabularConverter._extract_process_params(sheets) is None

    def test_extract_process_params_duplicate_sheets_raise(self) -> None:
        """Multiple process parameter sheets raise ValueError."""
        sheets = {
            "process_params": pd.DataFrame({"process_param_index": [1]}),
            "process": pd.DataFrame({"process_param_index": [2]}),
        }

        with pytest.raises(ValueError, match="Multiple process parameter sheets"):
            _TabularConverter._extract_process_params(sheets)

    def test_extract_process_params_drops_empty_rows(self) -> None:
        """Fully empty rows are dropped from process_params."""
        sheets = {
            "process_params": pd.DataFrame(
                {
                    "process_param_index": [1, None, 2],
                    "force": [120.0, None, 150.0],
                }
            )
        }

        with pytest.warns(UserWarning, match="force|Unknown|inconnue"):
            result = _TabularConverter._extract_process_params(sheets)

        assert result is not None
        assert len(result) == 2
        assert result["process_param_index"].tolist() == [1, 2]


class TestTabularConvertAll:
    """Tests for convert_all process-aware branches."""

    def test_convert_all_ignores_reserved_sheets(self, tmp_path: Path) -> None:
        """Reserved sheets are ignored by convert_all."""
        workbook = tmp_path / "multi.xlsx"

        with pd.ExcelWriter(workbook, engine="openpyxl") as writer:
            pd.DataFrame({"x": [1.0], "y": [2.0], "z": [3.0]}).to_excel(
                writer,
                sheet_name="traj_a",
                index=False,
            )
            pd.DataFrame({"x": [4.0], "y": [5.0], "z": [6.0]}).to_excel(
                writer,
                sheet_name="traj_b",
                index=False,
            )
            pd.DataFrame({"key": ["name"], "value": ["meta_name"]}).to_excel(
                writer,
                sheet_name="meta",
                index=False,
            )
            pd.DataFrame({"name": ["Tool_A"]}).to_excel(
                writer,
                sheet_name="tools",
                index=False,
            )

        from trajcenter.convert.excel_converter import ExcelConverter

        trajectories = ExcelConverter().convert_all(workbook)

        assert len(trajectories) == 2
        assert {traj.meta.name for traj in trajectories} == {"meta_name"}
