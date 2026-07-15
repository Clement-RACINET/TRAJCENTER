#!/usr/bin/env python3
# tests/test_apt_converter.py
"""Unit tests for :mod:`trajcenter.converter.apt_converter`.

Author: Clement RACINET

Covers:

- :class:`~trajcenter.converter.apt_converter.AptConverter`
- :func:`~trajcenter.converter.apt_converter._tool_vector_to_quaternion`
- :func:`~trajcenter.converter.apt_converter._parse_catia_matrix`
"""

from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from trajcenter.converter.apt_converter import (
    AptConverter,
    _parse_catia_matrix,
    _tool_vector_to_quaternion,
)
from trajcenter.converter.defaults import ConversionDefaults
from trajcenter.core.trajectory import SourceFormat, Trajectory

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

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
    """Write a synthetic APT file and return its path.

    Args:
        tmp_path: Temporary directory provided by pytest.
        name: File name (including extension).
        body: Raw APT content to write.

    Returns:
        Path to the written APT file.
    """
    p = tmp_path / name
    p.write_text(body, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def apt_simple(tmp_path: Path) -> Path:
    """Minimal APT file: 1 RAPID GOTO + 1 FEDRAT GOTO, no matrix."""
    return _write_apt(
        tmp_path,
        "simple.aptsource",
        _APT_HEADER_NO_MATRIX + _TWO_GOTOS,
    )


@pytest.fixture
def apt_with_matrix(tmp_path: Path) -> Path:
    """APT file with a CATIA matrix and 1 GOTO."""
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
    """Full APT file close to a real-world file (multiple GOTOs, CYCLE, etc.)."""
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


# ---------------------------------------------------------------------------
# Tests — _tool_vector_to_quaternion
# ---------------------------------------------------------------------------


class TestToolVectorToQuaternion:
    """Tests for the tool vector → ABB quaternion conversion."""

    def test_identity_z_up(self) -> None:
        """Vector (0, 0, 1) → identity quaternion [1, 0, 0, 0]."""
        q1, q2, q3, q4 = _tool_vector_to_quaternion(0.0, 0.0, 1.0)
        assert q1 == pytest.approx(1.0)
        assert q2 == pytest.approx(0.0)
        assert q3 == pytest.approx(0.0)
        assert q4 == pytest.approx(0.0)

    def test_z_down_180_around_x(self) -> None:
        """Vector (0, 0, -1) → 180° rotation around X: [0, 1, 0, 0]."""
        q1, q2, q3, q4 = _tool_vector_to_quaternion(0.0, 0.0, -1.0)
        assert q1 == pytest.approx(0.0)
        assert q2 == pytest.approx(1.0)
        assert q3 == pytest.approx(0.0)
        assert q4 == pytest.approx(0.0)

    def test_unit_norm(self) -> None:
        """The resulting quaternion always has unit norm."""
        for i, j, k in [(1, 0, 0), (0, 1, 0), (1, 1, 0), (0.5, 0.5, 0.707)]:
            q = _tool_vector_to_quaternion(float(i), float(j), float(k))
            norm = sum(v**2 for v in q) ** 0.5
            assert norm == pytest.approx(1.0, abs=1e-9)

    def test_x_axis(self) -> None:
        """Vector (1, 0, 0) → +90° rotation around +Y."""
        q1, q2, q3, q4 = _tool_vector_to_quaternion(1.0, 0.0, 0.0)
        # z_ref × (1,0,0) = (0,0,1) × (1,0,0) = (0,+1,0) → axis +Y
        # +90° rotation around +Y: w=cos(45°), y=+sin(45°)
        assert q1 == pytest.approx(np.cos(np.pi / 4), abs=1e-9)
        assert q2 == pytest.approx(0.0, abs=1e-9)
        assert q3 == pytest.approx(+np.sin(np.pi / 4), abs=1e-9)
        assert q4 == pytest.approx(0.0, abs=1e-9)

    def test_unnormalized_input_handled(self) -> None:
        """An unnormalized input vector is normalized before conversion."""
        q_norm = _tool_vector_to_quaternion(0.0, 0.0, 1.0)
        q_unnorm = _tool_vector_to_quaternion(0.0, 0.0, 5.0)
        for a, b in zip(q_norm, q_unnorm):
            assert a == pytest.approx(b, abs=1e-9)


# ---------------------------------------------------------------------------
# Tests — _parse_catia_matrix
# ---------------------------------------------------------------------------


class TestParseCatiaMatrix:
    """Tests for CATIA matrix extraction from APT comment lines."""

    def test_matrix_found(self) -> None:
        """The matrix is correctly extracted from ``$$`` comment lines."""
        lines: list[str] = list(_APT_HEADER_WITH_MATRIX.splitlines())
        mat = _parse_catia_matrix(lines)
        assert mat is not None
        assert mat.shape == (4, 4)

    def test_matrix_values(self) -> None:
        """Matrix values are correctly parsed."""
        lines: list[str] = list(_APT_HEADER_WITH_MATRIX.splitlines())
        mat = _parse_catia_matrix(lines)
        assert mat is not None
        assert mat[0, 0] == pytest.approx(1.0)
        assert mat[0, 3] == pytest.approx(-220.0)
        assert mat[2, 3] == pytest.approx(20.0)
        assert mat[3, 3] == pytest.approx(1.0)

    def test_matrix_not_found_returns_none(self) -> None:
        """Returns ``None`` when no matrix is present."""
        lines: list[str] = list(_APT_HEADER_NO_MATRIX.splitlines())
        assert _parse_catia_matrix(lines) is None

    def test_empty_file_returns_none(self) -> None:
        """Returns ``None`` on an empty file."""
        assert _parse_catia_matrix([]) is None


# ---------------------------------------------------------------------------
# Tests — AptConverter
# ---------------------------------------------------------------------------


class TestAptConverter:
    """Tests for the AptConverter class."""

    # --- Basic errors ---

    def test_file_not_found_raises(self, tmp_path: Path) -> None:
        """``convert()`` raises ``FileNotFoundError`` when the file does not exist."""
        with pytest.raises(FileNotFoundError, match=r"[Ff]ile not found|introuvable"):
            AptConverter().convert(tmp_path / "inexistant.aptsource")

    def test_empty_apt_raises(self, apt_empty: Path) -> None:
        """``convert()`` raises ``ValueError`` when no GOTO instruction is found."""
        with pytest.raises(ValueError, match=r"[Nn]o.*GOTO|[Aa]ucune instruction"):
            AptConverter().convert(apt_empty)

    # --- Metadata ---

    def test_source_format(self, apt_simple: Path) -> None:
        """``source_format`` is ``APT``."""
        assert AptConverter().convert(apt_simple).meta.source_format == SourceFormat.APT

    def test_source_file(self, apt_simple: Path) -> None:
        """``source_file`` contains the file name."""
        assert AptConverter().convert(apt_simple).meta.source_file == "simple.aptsource"

    def test_name(self, apt_simple: Path) -> None:
        """``name`` is the file stem."""
        assert AptConverter().convert(apt_simple).meta.name == "simple"

    # --- Content ---

    def test_point_count(self, apt_simple: Path) -> None:
        """2 GOTO instructions → 2 points."""
        assert AptConverter().convert(apt_simple).point_count == 2

    def test_is_complete(self, apt_simple: Path) -> None:
        """The produced trajectory is complete."""
        assert AptConverter().convert(apt_simple).is_complete is True

    def test_coordinates(self, apt_simple: Path) -> None:
        """x, y, z coordinates of the first point are correct."""
        traj = AptConverter().convert(apt_simple)
        assert traj.points["x"].iloc[0] == pytest.approx(10.0)
        assert traj.points["y"].iloc[0] == pytest.approx(20.0)
        assert traj.points["z"].iloc[0] == pytest.approx(30.0)

    def test_quaternions_z_up(self, apt_simple: Path) -> None:
        """Vector (0, 0, 1) → identity quaternion [1, 0, 0, 0]."""
        traj = AptConverter().convert(apt_simple)
        assert traj.points["q1"].iloc[0] == pytest.approx(1.0)
        assert traj.points["q2"].iloc[0] == pytest.approx(0.0)
        assert traj.points["q3"].iloc[0] == pytest.approx(0.0)
        assert traj.points["q4"].iloc[0] == pytest.approx(0.0)

    # --- MoveJ / MoveL ---

    def test_rapid_gives_movej(self, apt_simple: Path) -> None:
        """A GOTO preceded by RAPID is mapped to MoveJ."""
        traj = AptConverter().convert(apt_simple)
        assert traj.points["move_type"].iloc[0] == "MoveJ"

    def test_fedrat_gives_movel(self, apt_simple: Path) -> None:
        """A GOTO following FEDRAT is mapped to MoveL."""
        traj = AptConverter().convert(apt_simple)
        assert traj.points["move_type"].iloc[1] == "MoveL"

    def test_rapid_is_not_modal(self, tmp_path: Path) -> None:
        """RAPID is not modal: two consecutive GOTOs after RAPID → MoveJ + MoveL."""
        body = (
            "RAPID\n"
            "GOTO  /   1.0,  2.0,  3.0, 0.0, 0.0, 1.0\n"
            "GOTO  /   4.0,  5.0,  6.0, 0.0, 0.0, 1.0\n"
        )
        apt = _write_apt(tmp_path, "non_modal.aptsource", body)
        traj = AptConverter().convert(apt)
        assert traj.points["move_type"].iloc[0] == "MoveJ"
        assert traj.points["move_type"].iloc[1] == "MoveL"

    # --- Tools ---

    def test_default_tool_used_when_no_tprint(self, apt_simple: Path) -> None:
        """Without TPRINT, ``defaults.tool`` is used."""
        traj = AptConverter(defaults=ConversionDefaults(tool="myTool")).convert(
            apt_simple
        )
        assert traj.tools == ["myTool"]

    def test_tprint_tool_name_extracted(self, apt_with_tprint: Path) -> None:
        """The tool name extracted from TPRINT is used as ``tools[0]``."""
        traj = AptConverter().convert(apt_with_tprint)
        assert traj.tools == ["T1 PointeurD10"]

    def test_tool_index_always_zero(self, apt_with_tprint: Path) -> None:
        """``tool_index`` is always 0 (single tool in APT)."""
        traj = AptConverter().convert(apt_with_tprint)
        assert (traj.points["tool_index"] == 0).all()

    def test_default_wobj(self, apt_simple: Path) -> None:
        """``wobjs[0]`` equals ``defaults.wobj``."""
        traj = AptConverter(defaults=ConversionDefaults(wobj="myWobj")).convert(
            apt_simple
        )
        assert traj.wobjs == ["myWobj"]

    # --- Autocompletion ---

    def test_autocompleted_contains_speed(self, apt_simple: Path) -> None:
        """``speed`` is autocompleted (absent from the APT format)."""
        traj = AptConverter().convert(apt_simple)
        assert "speed" in traj.meta.autocompleted

    def test_autocompleted_contains_zone(self, apt_simple: Path) -> None:
        """``zone`` is autocompleted (absent from the APT format)."""
        traj = AptConverter().convert(apt_simple)
        assert "zone" in traj.meta.autocompleted

    def test_move_type_not_autocompleted(self, apt_simple: Path) -> None:
        """``move_type`` is NOT autocompleted — it is derived from RAPID/FEDRAT."""
        traj = AptConverter().convert(apt_simple)
        assert "move_type" not in traj.meta.autocompleted

    def test_custom_default_speed(self, apt_simple: Path) -> None:
        """The autocompleted speed uses the custom default value."""
        traj = AptConverter(defaults=ConversionDefaults(speed="v200")).convert(
            apt_simple
        )
        assert (traj.points["speed"] == "v200").all()

    # --- CATIA matrix ---

    def test_no_transform_by_default(self, apt_with_matrix: Path) -> None:
        """Without ``apply_catia_transform``, coordinates are raw."""
        traj = AptConverter().convert(apt_with_matrix)
        # Raw GOTO coordinates: x=10, y=20, z=30
        assert traj.points["x"].iloc[0] == pytest.approx(10.0)

    def test_transform_applied(self, apt_with_matrix: Path) -> None:
        """With ``apply_catia_transform=True``, the translation is applied."""
        traj = AptConverter(apply_catia_transform=True).convert(apt_with_matrix)
        # Matrix: identity + translation (-220, -170, +20)
        # x=10 + (-220) = -210
        assert traj.points["x"].iloc[0] == pytest.approx(10.0 + (-220.0))
        assert traj.points["y"].iloc[0] == pytest.approx(20.0 + (-170.0))
        assert traj.points["z"].iloc[0] == pytest.approx(30.0 + 20.0)

    def test_transform_missing_warns(self, apt_simple: Path) -> None:
        """``apply_catia_transform=True`` without matrix emits a warning."""
        with pytest.warns(UserWarning, match=r"[Mm]atrix|transform|matrice"):
            AptConverter(apply_catia_transform=True).convert(apt_simple)

    def test_transform_missing_coords_unchanged(self, apt_simple: Path) -> None:
        """Without a matrix, coordinates remain raw despite the flag."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            traj = AptConverter(apply_catia_transform=True).convert(apt_simple)
        assert traj.points["x"].iloc[0] == pytest.approx(10.0)

    # --- Full file ---

    def test_full_apt_point_count(self, apt_full: Path) -> None:
        """The full APT file produces the correct number of points."""
        traj = AptConverter().convert(apt_full)
        assert traj.point_count == 5  # 2 RAPID + 3 FEDRAT/CYCLE GOTOs

    def test_full_apt_tprint_extracted(self, apt_full: Path) -> None:
        """The tool name is extracted from TPRINT in the full file."""
        traj = AptConverter().convert(apt_full)
        assert traj.tools == ["T1 PointeurD10"]

    def test_full_apt_move_types(self, apt_full: Path) -> None:
        """The first 2 points are MoveJ, the next 3 are MoveL."""
        traj = AptConverter().convert(apt_full)
        assert traj.points["move_type"].iloc[0] == "MoveJ"
        assert traj.points["move_type"].iloc[1] == "MoveJ"
        assert traj.points["move_type"].iloc[2] == "MoveL"
        assert traj.points["move_type"].iloc[3] == "MoveL"
        assert traj.points["move_type"].iloc[4] == "MoveJ"

    # --- Roundtrip ---

    def test_full_roundtrip(self, tmp_path: Path, apt_simple: Path) -> None:
        """``convert → save → load`` produces an identical trajectory."""
        traj = AptConverter().convert(apt_simple)
        dest = tmp_path / "simple.trajcenter"
        traj.save(dest)
        loaded = Trajectory.load(dest)

        assert loaded.point_count == traj.point_count
        assert loaded.tools == traj.tools
        assert loaded.wobjs == traj.wobjs
        assert loaded.is_complete is True
        pd.testing.assert_series_equal(
            loaded.points["x"].reset_index(drop=True),
            traj.points["x"].reset_index(drop=True),
            check_names=False,
        )

    def test_convert_and_save(self, tmp_path: Path, apt_simple: Path) -> None:
        """``convert_and_save()`` creates the ``.trajcenter`` file."""
        result = AptConverter().convert_and_save(source=apt_simple, dest_dir=tmp_path)
        assert result.exists()
        assert result.name == "simple.trajcenter"

    def test_convert_and_save_custom_stem(
        self, tmp_path: Path, apt_simple: Path
    ) -> None:
        """``convert_and_save()`` uses the custom stem when provided."""
        result = AptConverter().convert_and_save(
            source=apt_simple, dest_dir=tmp_path, stem="ma_trajectoire"
        )
        assert result.name == "ma_trajectoire.trajcenter"
