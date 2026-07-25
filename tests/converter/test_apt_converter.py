#!/usr/bin/env python3
# tests/converter/test_apt_converter.py
"""Unit tests for :mod:`trajcenter.converter.apt_converter`.

> **Author**: Clément RACINET
"""

from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from trajcenter.converter.apt_converter import (
    AptConverter,
    _normalise_tprint_tool_name,
    _parse_catia_matrix,
    _tool_vector_to_quaternion,
)
from trajcenter.converter.defaults import ConversionDefaults
from trajcenter.core.trajectory import SourceFormat, Trajectory

_APT_HEADER_WITH_MATRIX = """\
$$ -----------------------------------------------------------------
$$     Généré le jeudi 30 novembre 2023 08:46:00
$$     CATIA APT VERSION 1.0
$$ -----------------------------------------------------------------
$$     1.00000     0.00000     0.00000  -220.00000
$$     0.00000     1.00000     0.00000  -170.00000
$$     0.00000     0.00000     1.00000    20.00000
PARTNO PART TO BE MACHINED
"""

_APT_HEADER_NO_MATRIX = """\
$$ -----------------------------------------------------------------
$$     Généré le jeudi 30 novembre 2023 08:46:00
$$ -----------------------------------------------------------------
PARTNO PART TO BE MACHINED
"""

_ONE_GOTO = (
    "RAPID\nGOTO  /   10.00000,  20.00000,  30.00000, 0.000000, 0.000000, 1.000000\n"
)

_TWO_GOTOS = (
    "RAPID\n"
    "GOTO  /   10.00000,  20.00000,  30.00000, 0.000000, 0.000000, 1.000000\n"
    "FEDRAT/  300.0000,MMPM\n"
    "GOTO  /   40.00000,  50.00000,  60.00000, 0.000000, 0.000000, 1.000000\n"
)


def _write_apt(tmp_path: Path, name: str, body: str) -> Path:
    """Write a synthetic APT file and return its path."""
    path = tmp_path / name
    path.write_text(body, encoding="utf-8")
    return path


@pytest.fixture
def apt_simple(tmp_path: Path) -> Path:
    """Minimal APT file with one RAPID GOTO and one FEDRAT GOTO."""
    return _write_apt(
        tmp_path,
        "simple.aptsource",
        _APT_HEADER_NO_MATRIX + _TWO_GOTOS,
    )


@pytest.fixture
def apt_with_matrix(tmp_path: Path) -> Path:
    """APT file with a CATIA matrix and one GOTO."""
    return _write_apt(
        tmp_path,
        "with_matrix.aptsource",
        _APT_HEADER_WITH_MATRIX + _ONE_GOTO,
    )


@pytest.fixture
def apt_with_tprint(tmp_path: Path) -> Path:
    """APT file with a TPRINT directive for the tool name."""
    body = _APT_HEADER_NO_MATRIX + "TPRINT/T1 PointeurD10\n" + _TWO_GOTOS
    return _write_apt(tmp_path, "with_tprint.aptsource", body)


@pytest.fixture
def apt_empty(tmp_path: Path) -> Path:
    """APT file with no GOTO instructions."""
    return _write_apt(
        tmp_path,
        "empty.aptsource",
        _APT_HEADER_NO_MATRIX + "SPINDL/OFF\nEND\n",
    )


@pytest.fixture
def apt_full(tmp_path: Path) -> Path:
    """Full synthetic APT file close to a real-world file."""
    body = (
        _APT_HEADER_WITH_MATRIX
        + "TPRINT/T1 PointeurD10\n"
        + "LOADTL/2,1\n"
        + "SPINDL/ 2546.4790,RPM,CLW\n"
        + "RAPID\n"
        + "GOTO  /   98.00000,  100.00000,  120.00000, 0.000000, 0.000000, 1.000000\n"
        + "RAPID\n"
        + "GOTO  /   98.00000,  100.00000,   35.00000, 0.000000, 0.000000, 1.000000\n"
        + "FEDRAT/  300.0000,MMPM\n"
        + "GOTO  /   98.00000,  100.00000,   25.00000, 0.000000, 0.000000, 1.000000\n"
        + "CYCLE/DRILL,    3.000000,    5.000000\n"
        + "GOTO  /   98.00000,  100.00000,   20.00000, 0.000000, 0.000000, 1.000000\n"
        + "CYCLE/OFF\n"
        + "RAPID\n"
        + "GOTO  /   98.00000,  100.00000,   40.00000, 0.000000, 0.000000, 1.000000\n"
        + "SPINDL/OFF\n"
        + "END\n"
    )
    return _write_apt(tmp_path, "full.aptsource", body)


class TestToolVectorToQuaternion:
    """Tests for tool vector to ABB quaternion conversion."""

    def test_identity_z_up(self) -> None:
        """Vector up produces identity quaternion."""
        q1, q2, q3, q4 = _tool_vector_to_quaternion(0.0, 0.0, 1.0)
        assert q1 == pytest.approx(1.0)
        assert q2 == pytest.approx(0.0)
        assert q3 == pytest.approx(0.0)
        assert q4 == pytest.approx(0.0)

    def test_z_down_180_around_x(self) -> None:
        """Vector down produces 180 degrees around X."""
        q1, q2, q3, q4 = _tool_vector_to_quaternion(0.0, 0.0, -1.0)
        assert q1 == pytest.approx(0.0)
        assert q2 == pytest.approx(1.0)
        assert q3 == pytest.approx(0.0)
        assert q4 == pytest.approx(0.0)

    def test_unit_norm(self) -> None:
        """The resulting quaternion has unit norm."""
        for i, j, k in [(1, 0, 0), (0, 1, 0), (1, 1, 0), (0.5, 0.5, 0.707)]:
            q = _tool_vector_to_quaternion(float(i), float(j), float(k))
            norm = sum(value**2 for value in q) ** 0.5
            assert norm == pytest.approx(1.0, abs=1e-9)

    def test_x_axis(self) -> None:
        """Vector X produces +90 degrees around +Y."""
        q1, q2, q3, q4 = _tool_vector_to_quaternion(1.0, 0.0, 0.0)
        assert q1 == pytest.approx(np.cos(np.pi / 4), abs=1e-9)
        assert q2 == pytest.approx(0.0, abs=1e-9)
        assert q3 == pytest.approx(np.sin(np.pi / 4), abs=1e-9)
        assert q4 == pytest.approx(0.0, abs=1e-9)

    def test_unnormalized_input_handled(self) -> None:
        """An unnormalized input vector is normalized."""
        q_norm = _tool_vector_to_quaternion(0.0, 0.0, 1.0)
        q_unnorm = _tool_vector_to_quaternion(0.0, 0.0, 5.0)
        for expected, actual in zip(q_norm, q_unnorm, strict=True):
            assert actual == pytest.approx(expected, abs=1e-9)


class TestParseCatiaMatrix:
    """Tests for CATIA matrix extraction."""

    def test_matrix_found(self) -> None:
        """The matrix is extracted from comment rows."""
        matrix = _parse_catia_matrix(list(_APT_HEADER_WITH_MATRIX.splitlines()))
        assert matrix is not None
        assert matrix.shape == (4, 4)

    def test_matrix_values(self) -> None:
        """Matrix values are parsed."""
        matrix = _parse_catia_matrix(list(_APT_HEADER_WITH_MATRIX.splitlines()))
        assert matrix is not None
        assert matrix[0, 0] == pytest.approx(1.0)
        assert matrix[0, 3] == pytest.approx(-220.0)
        assert matrix[2, 3] == pytest.approx(20.0)
        assert matrix[3, 3] == pytest.approx(1.0)

    def test_matrix_not_found_returns_none(self) -> None:
        """None is returned when no matrix exists."""
        assert _parse_catia_matrix(list(_APT_HEADER_NO_MATRIX.splitlines())) is None

    def test_empty_file_returns_none(self) -> None:
        """None is returned for an empty file."""
        assert _parse_catia_matrix([]) is None


class TestNormaliseTprintToolName:
    """Tests for CATIA APT TPRINT tool name normalisation."""

    def test_strips_catian_t_prefix(self) -> None:
        """A leading CATIA tool identifier is removed."""
        assert _normalise_tprint_tool_name("T1 PointeurD10") == "PointeurD10"

    def test_strips_multi_digit_t_prefix(self) -> None:
        """A multi-digit CATIA tool identifier is removed."""
        assert _normalise_tprint_tool_name("T12 ForetD6") == "ForetD6"

    def test_keeps_plain_tool_name(self) -> None:
        """A plain tool name is preserved."""
        assert _normalise_tprint_tool_name("PointeurD10") == "PointeurD10"

    def test_keeps_lonely_tool_identifier(self) -> None:
        """A lonely T-number is preserved because no name follows it."""
        assert _normalise_tprint_tool_name("T1") == "T1"

    def test_keeps_identifier_without_whitespace(self) -> None:
        """A compact name is preserved when no separator exists."""
        assert _normalise_tprint_tool_name("T1_PointeurD10") == "T1_PointeurD10"

    def test_strips_surrounding_whitespace(self) -> None:
        """Surrounding whitespace is removed."""
        assert _normalise_tprint_tool_name("  T1 PointeurD10  ") == "PointeurD10"


class TestAptConverter:
    """Tests for the APT converter."""

    def test_file_not_found_raises(self, tmp_path: Path) -> None:
        """convert raises FileNotFoundError when source does not exist."""
        with pytest.raises(FileNotFoundError, match=r"[Ff]ile not found|introuvable"):
            AptConverter().convert(tmp_path / "inexistant.aptsource")

    def test_empty_apt_raises(self, apt_empty: Path) -> None:
        """convert raises ValueError when no GOTO instruction is found."""
        with pytest.raises(ValueError, match=r"[Nn]o.*GOTO|[Aa]ucune instruction"):
            AptConverter().convert(apt_empty)

    def test_source_format(self, apt_simple: Path) -> None:
        """source_format is APT."""
        assert AptConverter().convert(apt_simple).meta.source_format == SourceFormat.APT

    def test_source_file(self, apt_simple: Path) -> None:
        """source_file contains the source file name."""
        assert AptConverter().convert(apt_simple).meta.source_file == "simple.aptsource"

    def test_name(self, apt_simple: Path) -> None:
        """name is the source file stem."""
        assert AptConverter().convert(apt_simple).meta.name == "simple"

    def test_point_count(self, apt_simple: Path) -> None:
        """Two GOTO instructions produce two points."""
        assert AptConverter().convert(apt_simple).point_count == 2

    def test_required_geometry_columns_present(self, apt_simple: Path) -> None:
        """The produced trajectory contains required geometry columns."""
        traj = AptConverter().convert(apt_simple)

        for col in ["x", "y", "z", "q1", "q2", "q3", "q4"]:
            assert col in traj.points.columns

    def test_coordinates(self, apt_simple: Path) -> None:
        """Coordinates of the first point are parsed."""
        traj = AptConverter().convert(apt_simple)
        assert traj.points["x"].iloc[0] == pytest.approx(10.0)
        assert traj.points["y"].iloc[0] == pytest.approx(20.0)
        assert traj.points["z"].iloc[0] == pytest.approx(30.0)

    def test_quaternions_z_up(self, apt_simple: Path) -> None:
        """Tool vector up produces identity quaternion."""
        traj = AptConverter().convert(apt_simple)
        assert traj.points["q1"].iloc[0] == pytest.approx(1.0)
        assert traj.points["q2"].iloc[0] == pytest.approx(0.0)
        assert traj.points["q3"].iloc[0] == pytest.approx(0.0)
        assert traj.points["q4"].iloc[0] == pytest.approx(0.0)

    def test_rapid_gives_movej(self, apt_simple: Path) -> None:
        """A GOTO preceded by RAPID is mapped to MoveJ."""
        traj = AptConverter().convert(apt_simple)
        assert traj.points["move_type"].iloc[0] == "MoveJ"

    def test_fedrat_gives_movel(self, apt_simple: Path) -> None:
        """A GOTO following FEDRAT is mapped to MoveL."""
        traj = AptConverter().convert(apt_simple)
        assert traj.points["move_type"].iloc[1] == "MoveL"

    def test_rapid_is_not_modal(self, tmp_path: Path) -> None:
        """RAPID applies only to the next GOTO."""
        body = (
            "RAPID\n"
            "GOTO  /   1.0,  2.0,  3.0, 0.0, 0.0, 1.0\n"
            "GOTO  /   4.0,  5.0,  6.0, 0.0, 0.0, 1.0\n"
        )
        apt = _write_apt(tmp_path, "non_modal.aptsource", body)
        traj = AptConverter().convert(apt)
        assert traj.points["move_type"].iloc[0] == "MoveJ"
        assert traj.points["move_type"].iloc[1] == "MoveL"

    def test_no_tprint_creates_no_tool_name_without_default(
        self,
        apt_simple: Path,
    ) -> None:
        """Without TPRINT and explicit default, no tool_name column is created."""
        traj = AptConverter().convert(apt_simple)
        assert "tool_name" not in traj.points.columns

    def test_default_tool_name_used_when_no_tprint(self, apt_simple: Path) -> None:
        """Explicit requested default tool_name is applied when TPRINT is absent."""
        traj = AptConverter(
            defaults=ConversionDefaults(
                autocomplete_columns={"tool_name"},
                tool_name="myTool",
            )
        ).convert(apt_simple)

        assert "tool_name" in traj.points.columns
        assert (traj.points["tool_name"] == "myTool").all()
        assert "tool_name" in traj.meta.autocompleted

    def test_tprint_tool_name_extracted(self, apt_with_tprint: Path) -> None:
        """TPRINT is stored as inline tool_name."""
        traj = AptConverter().convert(apt_with_tprint)
        assert "tool_name" in traj.points.columns
        assert (traj.points["tool_name"] == "PointeurD10").all()
        assert "tool_index" not in traj.points.columns

    def test_default_wobj_name(self, apt_simple: Path) -> None:
        """Explicit requested default wobj_name is applied to APT trajectories."""
        traj = AptConverter(
            defaults=ConversionDefaults(
                autocomplete_columns={"wobj_name"},
                wobj_name="myWobj",
            )
        ).convert(apt_simple)

        assert "wobj_name" in traj.points.columns
        assert (traj.points["wobj_name"] == "myWobj").all()
        assert "wobj_name" in traj.meta.autocompleted
        assert "wobj_index" not in traj.points.columns

    def test_no_tcp_speed_without_default(self, apt_simple: Path) -> None:
        """APT does not create tcp_speed by default."""
        traj = AptConverter().convert(apt_simple)
        assert "tcp_speed" not in traj.points.columns
        assert "tcp_speed" not in traj.meta.autocompleted

    def test_no_zone_type_without_default(self, apt_simple: Path) -> None:
        """APT does not create zone_type by default."""
        traj = AptConverter().convert(apt_simple)
        assert "zone_type" not in traj.points.columns
        assert "zone_type" not in traj.meta.autocompleted

    def test_move_type_not_autocompleted(self, apt_simple: Path) -> None:
        """move_type is derived from RAPID/FEDRAT, not autocompleted."""
        traj = AptConverter().convert(apt_simple)
        assert "move_type" not in traj.meta.autocompleted

    def test_custom_default_tcp_speed(self, apt_simple: Path) -> None:
        """Explicit requested tcp_speed default is applied."""
        traj = AptConverter(
            defaults=ConversionDefaults(
                autocomplete_columns={"tcp_speed"},
                tcp_speed=200.0,
            )
        ).convert(apt_simple)

        assert traj.points["tcp_speed"].tolist() == pytest.approx([200.0, 200.0])
        assert "tcp_speed" in traj.meta.autocompleted

    def test_custom_default_zone_type(self, apt_simple: Path) -> None:
        """Explicit requested zone_type default is applied."""
        traj = AptConverter(
            defaults=ConversionDefaults(
                autocomplete_columns={"zone_type"},
                zone_type=255,
            )
        ).convert(apt_simple)

        assert (traj.points["zone_type"] == 255).all()
        assert "zone_type" in traj.meta.autocompleted

    def test_no_transform_by_default(self, apt_with_matrix: Path) -> None:
        """Without apply_catia_transform, coordinates are raw."""
        traj = AptConverter().convert(apt_with_matrix)
        assert traj.points["x"].iloc[0] == pytest.approx(10.0)

    def test_transform_applied(self, apt_with_matrix: Path) -> None:
        """With apply_catia_transform=True, translation is applied."""
        traj = AptConverter(apply_catia_transform=True).convert(apt_with_matrix)
        assert traj.points["x"].iloc[0] == pytest.approx(-210.0)
        assert traj.points["y"].iloc[0] == pytest.approx(-150.0)
        assert traj.points["z"].iloc[0] == pytest.approx(50.0)

    def test_transform_missing_warns(self, apt_simple: Path) -> None:
        """Missing CATIA matrix emits a warning when transform is requested."""
        with pytest.warns(UserWarning, match=r"[Mm]atrix|transform|matrice"):
            AptConverter(apply_catia_transform=True).convert(apt_simple)

    def test_transform_missing_coords_unchanged(self, apt_simple: Path) -> None:
        """Coordinates remain raw when matrix is absent."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            traj = AptConverter(apply_catia_transform=True).convert(apt_simple)
        assert traj.points["x"].iloc[0] == pytest.approx(10.0)

    def test_full_apt_point_count(self, apt_full: Path) -> None:
        """The full APT fixture produces five points."""
        traj = AptConverter().convert(apt_full)
        assert traj.point_count == 5

    def test_full_apt_tprint_extracted(self, apt_full: Path) -> None:
        """The tool name is extracted from TPRINT in the full file."""
        traj = AptConverter().convert(apt_full)
        assert "tool_name" in traj.points.columns
        assert (traj.points["tool_name"] == "PointeurD10").all()

    def test_full_apt_move_types(self, apt_full: Path) -> None:
        """Legacy RAPID/FEDRAT movement logic is preserved."""
        traj = AptConverter().convert(apt_full)
        assert traj.points["move_type"].iloc[0] == "MoveJ"
        assert traj.points["move_type"].iloc[1] == "MoveJ"
        assert traj.points["move_type"].iloc[2] == "MoveL"
        assert traj.points["move_type"].iloc[3] == "MoveL"
        assert traj.points["move_type"].iloc[4] == "MoveJ"

    def test_no_legacy_tool_wobj_columns(self, apt_with_tprint: Path) -> None:
        """APT v2 output has no legacy index columns."""
        traj = AptConverter().convert(apt_with_tprint)
        assert "tool_index" not in traj.points.columns
        assert "wobj_index" not in traj.points.columns

    def test_full_roundtrip(self, tmp_path: Path, apt_simple: Path) -> None:
        """convert -> save -> load produces an equivalent trajectory."""
        traj = AptConverter().convert(apt_simple)
        dest = tmp_path / "simple.trajcenter"
        traj.save(dest)
        loaded = Trajectory.load(dest)

        assert loaded.point_count == traj.point_count
        assert list(loaded.points.columns) == list(traj.points.columns)
        pd.testing.assert_series_equal(
            loaded.points["x"].reset_index(drop=True),
            traj.points["x"].reset_index(drop=True),
            check_names=False,
        )

    def test_convert_and_save(self, tmp_path: Path, apt_simple: Path) -> None:
        """convert_and_save creates the trajcenter file."""
        result = AptConverter().convert_and_save(source=apt_simple, dest_dir=tmp_path)
        assert result.exists()
        assert result.name == "simple.trajcenter"

    def test_convert_and_save_custom_stem(
        self,
        tmp_path: Path,
        apt_simple: Path,
    ) -> None:
        """convert_and_save uses the custom stem when provided."""
        result = AptConverter().convert_and_save(
            source=apt_simple,
            dest_dir=tmp_path,
            stem="ma_trajectoire",
        )
        assert result.name == "ma_trajectoire.trajcenter"
