# tests/test_apt_converter.py

"""
Tests unitaires pour :mod:`trajcenter.converter.apt_converter`.

Couvre :
- :class:`~trajcenter.converter.apt_converter.AptConverter`
- :func:`~trajcenter.converter.apt_converter._tool_vector_to_quaternion`
- :func:`~trajcenter.converter.apt_converter._parse_catia_matrix`
"""
from __future__ import annotations

import warnings
from collections.abc import Sequence
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
    "RAPID\n"
    "GOTO  /   10.00000,  20.00000,  30.00000, 0.000000, 0.000000, 1.000000\n"
)

_TWO_GOTOS = (
    "RAPID\n"
    "GOTO  /   10.00000,  20.00000,  30.00000, 0.000000, 0.000000, 1.000000\n"
    "FEDRAT/  300.0000,MMPM\n"
    "GOTO  /   40.00000,  50.00000,  60.00000, 0.000000, 0.000000, 1.000000\n"
)


def _write_apt(tmp_path: Path, name: str, body: str) -> Path:
    """Écrit un fichier APT synthétique et retourne son chemin."""
    p = tmp_path / name
    p.write_text(body, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def apt_simple(tmp_path: Path) -> Path:
    """Fichier APT minimal : 1 RAPID GOTO + 1 FEDRAT GOTO, sans matrice."""
    return _write_apt(
        tmp_path, "simple.aptsource",
        _APT_HEADER_NO_MATRIX + _TWO_GOTOS,
    )


@pytest.fixture
def apt_with_matrix(tmp_path: Path) -> Path:
    """Fichier APT avec matrice CATIA et 1 GOTO."""
    return _write_apt(
        tmp_path, "with_matrix.aptsource",
        _APT_HEADER_WITH_MATRIX + _ONE_GOTO,
    )


@pytest.fixture
def apt_with_tprint(tmp_path: Path) -> Path:
    """Fichier APT avec directive TPRINT pour le nom d'outil."""
    body = (
        _APT_HEADER_NO_MATRIX
        + "TPRINT/T1 PointeurD10\n"
        + _TWO_GOTOS
    )
    return _write_apt(tmp_path, "with_tprint.aptsource", body)


@pytest.fixture
def apt_empty(tmp_path: Path) -> Path:
    """Fichier APT sans aucune instruction GOTO."""
    return _write_apt(
        tmp_path, "empty.aptsource",
        _APT_HEADER_NO_MATRIX + "SPINDL/OFF\nEND\n",
    )


@pytest.fixture
def apt_full(tmp_path: Path) -> Path:
    """Fichier APT complet proche du fichier réel (plusieurs GOTO, CYCLE, etc.)."""
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
    """Tests de la conversion vecteur outil → quaternion ABB."""

    def test_identity_z_up(self) -> None:
        """Vecteur (0,0,1) → quaternion identité [1,0,0,0]."""
        q1, q2, q3, q4 = _tool_vector_to_quaternion(0.0, 0.0, 1.0)
        assert q1 == pytest.approx(1.0)
        assert q2 == pytest.approx(0.0)
        assert q3 == pytest.approx(0.0)
        assert q4 == pytest.approx(0.0)

    def test_z_down_180_around_x(self) -> None:
        """Vecteur (0,0,-1) → rotation 180° autour de X : [0,1,0,0]."""
        q1, q2, q3, q4 = _tool_vector_to_quaternion(0.0, 0.0, -1.0)
        assert q1 == pytest.approx(0.0)
        assert q2 == pytest.approx(1.0)
        assert q3 == pytest.approx(0.0)
        assert q4 == pytest.approx(0.0)

    def test_unit_norm(self) -> None:
        """Le quaternion résultant est toujours de norme 1."""
        for i, j, k in [(1, 0, 0), (0, 1, 0), (1, 1, 0), (0.5, 0.5, 0.707)]:
            q = _tool_vector_to_quaternion(float(i), float(j), float(k))
            norm = sum(v ** 2 for v in q) ** 0.5
            assert norm == pytest.approx(1.0, abs=1e-9)

    def test_x_axis(self) -> None:
        """Vecteur (1,0,0) → rotation +90° autour de +Y."""
        q1, q2, q3, q4 = _tool_vector_to_quaternion(1.0, 0.0, 0.0)
        # z_ref × (1,0,0) = (0,0,1) × (1,0,0) = (0,+1,0) → axe +Y
        # Rotation +90° autour de +Y : w=cos(45°), y=+sin(45°)
        assert q1 == pytest.approx(np.cos(np.pi / 4), abs=1e-9)
        assert q2 == pytest.approx(0.0, abs=1e-9)
        assert q3 == pytest.approx(+np.sin(np.pi / 4), abs=1e-9)
        assert q4 == pytest.approx(0.0, abs=1e-9)

    def test_unnormalized_input_handled(self) -> None:
        """Un vecteur non normalisé est normalisé avant conversion."""
        q_norm = _tool_vector_to_quaternion(0.0, 0.0, 1.0)
        q_unnorm = _tool_vector_to_quaternion(0.0, 0.0, 5.0)
        for a, b in zip(q_norm, q_unnorm):
            assert a == pytest.approx(b, abs=1e-9)


# ---------------------------------------------------------------------------
# Tests — _parse_catia_matrix
# ---------------------------------------------------------------------------


class TestParseCatiaMatrix:
    """Tests de l'extraction de la matrice CATIA."""

    def test_matrix_found(self) -> None:
        """La matrice est correctement extraite depuis les commentaires $$."""
        lines: list[str] = list(_APT_HEADER_WITH_MATRIX.splitlines())
        mat = _parse_catia_matrix(lines)
        assert mat is not None
        assert mat.shape == (4, 4)

    def test_matrix_values(self) -> None:
        """Les valeurs de la matrice sont correctement parsées."""
        lines: list[str] = list(_APT_HEADER_WITH_MATRIX.splitlines())
        mat = _parse_catia_matrix(lines)
        assert mat is not None
        assert mat[0, 0] == pytest.approx(1.0)
        assert mat[0, 3] == pytest.approx(-220.0)
        assert mat[2, 3] == pytest.approx(20.0)
        assert mat[3, 3] == pytest.approx(1.0)

    def test_matrix_not_found_returns_none(self) -> None:
        """Retourne None si aucune matrice n'est présente."""
        lines: list[str] = list(_APT_HEADER_NO_MATRIX.splitlines())
        assert _parse_catia_matrix(lines) is None

    def test_empty_file_returns_none(self) -> None:
        """Retourne None sur un fichier vide."""
        assert _parse_catia_matrix([]) is None


# ---------------------------------------------------------------------------
# Tests — AptConverter
# ---------------------------------------------------------------------------


class TestAptConverter:
    """Tests du convertisseur AptConverter."""

    # --- Erreurs de base ---

    def test_file_not_found_raises(self, tmp_path: Path) -> None:
        """convert() lève FileNotFoundError si le fichier n'existe pas."""
        with pytest.raises(FileNotFoundError, match="Fichier introuvable"):
            AptConverter().convert(tmp_path / "inexistant.aptsource")

    def test_empty_apt_raises(self, apt_empty: Path) -> None:
        """convert() lève ValueError si aucune instruction GOTO n'est trouvée."""
        with pytest.raises(ValueError, match="Aucune instruction GOTO"):
            AptConverter().convert(apt_empty)

    # --- Métadonnées ---

    def test_source_format(self, apt_simple: Path) -> None:
        """source_format est APT."""
        assert AptConverter().convert(apt_simple).meta.source_format == SourceFormat.APT

    def test_source_file(self, apt_simple: Path) -> None:
        """source_file contient le nom du fichier."""
        assert AptConverter().convert(apt_simple).meta.source_file == "simple.aptsource"

    def test_name(self, apt_simple: Path) -> None:
        """name est le stem du fichier."""
        assert AptConverter().convert(apt_simple).meta.name == "simple"

    # --- Contenu ---

    def test_point_count(self, apt_simple: Path) -> None:
        """2 GOTO → 2 points."""
        assert AptConverter().convert(apt_simple).point_count == 2

    def test_is_complete(self, apt_simple: Path) -> None:
        """La trajectoire produite est complète."""
        assert AptConverter().convert(apt_simple).is_complete is True

    def test_coordinates(self, apt_simple: Path) -> None:
        """Les coordonnées x, y, z du premier point sont correctes."""
        traj = AptConverter().convert(apt_simple)
        assert traj.points["x"].iloc[0] == pytest.approx(10.0)
        assert traj.points["y"].iloc[0] == pytest.approx(20.0)
        assert traj.points["z"].iloc[0] == pytest.approx(30.0)

    def test_quaternions_z_up(self, apt_simple: Path) -> None:
        """Vecteur (0,0,1) → quaternion identité [1,0,0,0]."""
        traj = AptConverter().convert(apt_simple)
        assert traj.points["q1"].iloc[0] == pytest.approx(1.0)
        assert traj.points["q2"].iloc[0] == pytest.approx(0.0)
        assert traj.points["q3"].iloc[0] == pytest.approx(0.0)
        assert traj.points["q4"].iloc[0] == pytest.approx(0.0)

    # --- MoveJ / MoveL ---

    def test_rapid_gives_movej(self, apt_simple: Path) -> None:
        """Un GOTO précédé de RAPID est MoveJ."""
        traj = AptConverter().convert(apt_simple)
        assert traj.points["move_type"].iloc[0] == "MoveJ"

    def test_fedrat_gives_movel(self, apt_simple: Path) -> None:
        """Un GOTO après FEDRAT est MoveL."""
        traj = AptConverter().convert(apt_simple)
        assert traj.points["move_type"].iloc[1] == "MoveL"

    def test_rapid_is_not_modal(self, tmp_path: Path) -> None:
        """RAPID n'est pas modal : deux GOTO consécutifs après RAPID → MoveJ + MoveL."""
        body = (
            "RAPID\n"
            "GOTO  /   1.0,  2.0,  3.0, 0.0, 0.0, 1.0\n"
            "GOTO  /   4.0,  5.0,  6.0, 0.0, 0.0, 1.0\n"
        )
        apt = _write_apt(tmp_path, "non_modal.aptsource", body)
        traj = AptConverter().convert(apt)
        assert traj.points["move_type"].iloc[0] == "MoveJ"
        assert traj.points["move_type"].iloc[1] == "MoveL"

    # --- Outils ---

    def test_default_tool_used_when_no_tprint(self, apt_simple: Path) -> None:
        """Sans TPRINT, defaults.tool est utilisé."""
        traj = AptConverter(defaults=ConversionDefaults(tool="myTool")).convert(apt_simple)
        assert traj.tools == ["myTool"]

    def test_tprint_tool_name_extracted(self, apt_with_tprint: Path) -> None:
        """Le nom d'outil extrait de TPRINT est utilisé comme tools[0]."""
        traj = AptConverter().convert(apt_with_tprint)
        assert traj.tools == ["T1 PointeurD10"]

    def test_tool_index_always_zero(self, apt_with_tprint: Path) -> None:
        """tool_index est toujours 0 (un seul outil en APT)."""
        traj = AptConverter().convert(apt_with_tprint)
        assert (traj.points["tool_index"] == 0).all()

    def test_default_wobj(self, apt_simple: Path) -> None:
        """wobjs[0] est defaults.wobj."""
        traj = AptConverter(defaults=ConversionDefaults(wobj="myWobj")).convert(apt_simple)
        assert traj.wobjs == ["myWobj"]

    # --- Autocomplétion ---

    def test_autocompleted_contains_speed(self, apt_simple: Path) -> None:
        """speed est autocomplétée (absente du format APT)."""
        traj = AptConverter().convert(apt_simple)
        assert "speed" in traj.meta.autocompleted

    def test_autocompleted_contains_zone(self, apt_simple: Path) -> None:
        """zone est autocomplétée (absente du format APT)."""
        traj = AptConverter().convert(apt_simple)
        assert "zone" in traj.meta.autocompleted

    def test_move_type_not_autocompleted(self, apt_simple: Path) -> None:
        """move_type n'est PAS autocomplété — il est calculé depuis RAPID/FEDRAT."""
        traj = AptConverter().convert(apt_simple)
        assert "move_type" not in traj.meta.autocompleted

    def test_custom_default_speed(self, apt_simple: Path) -> None:
        """La vitesse autocomplétée utilise le default personnalisé."""
        traj = AptConverter(defaults=ConversionDefaults(speed="v200")).convert(apt_simple)
        assert (traj.points["speed"] == "v200").all()

    # --- Matrice CATIA ---

    def test_no_transform_by_default(self, apt_with_matrix: Path) -> None:
        """Sans apply_catia_transform, les coordonnées sont brutes."""
        traj = AptConverter().convert(apt_with_matrix)
        # Coordonnées brutes du GOTO : x=10, y=20, z=30
        assert traj.points["x"].iloc[0] == pytest.approx(10.0)

    def test_transform_applied(self, apt_with_matrix: Path) -> None:
        """Avec apply_catia_transform=True, la translation est appliquée."""
        traj = AptConverter(apply_catia_transform=True).convert(apt_with_matrix)
        # Matrice : identité + translation (-220, -170, +20)
        # x=10 + (-220) = -210
        assert traj.points["x"].iloc[0] == pytest.approx(10.0 + (-220.0))
        assert traj.points["y"].iloc[0] == pytest.approx(20.0 + (-170.0))
        assert traj.points["z"].iloc[0] == pytest.approx(30.0 + 20.0)

    def test_transform_missing_warns(self, apt_simple: Path) -> None:
        """apply_catia_transform=True sans matrice émet un UserWarning."""
        with pytest.warns(UserWarning, match="matrice CATIA"):
            AptConverter(apply_catia_transform=True).convert(apt_simple)

    def test_transform_missing_coords_unchanged(self, apt_simple: Path) -> None:
        """Sans matrice trouvée, les coordonnées restent brutes malgré le flag."""
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            traj = AptConverter(apply_catia_transform=True).convert(apt_simple)
        assert traj.points["x"].iloc[0] == pytest.approx(10.0)

    # --- Fichier réel ---

    def test_full_apt_point_count(self, apt_full: Path) -> None:
        """Le fichier APT complet produit le bon nombre de points."""
        traj = AptConverter().convert(apt_full)
        assert traj.point_count == 5  # 2 RAPID + 3 FEDRAT/CYCLE GOTO

    def test_full_apt_tprint_extracted(self, apt_full: Path) -> None:
        """Le nom d'outil est extrait depuis TPRINT dans le fichier complet."""
        traj = AptConverter().convert(apt_full)
        assert traj.tools == ["T1 PointeurD10"]

    def test_full_apt_move_types(self, apt_full: Path) -> None:
        """Les 2 premiers points sont MoveJ, les 3 suivants MoveL."""
        traj = AptConverter().convert(apt_full)
        assert traj.points["move_type"].iloc[0] == "MoveJ"
        assert traj.points["move_type"].iloc[1] == "MoveJ"
        assert traj.points["move_type"].iloc[2] == "MoveL"
        assert traj.points["move_type"].iloc[3] == "MoveL"
        assert traj.points["move_type"].iloc[4] == "MoveJ"

    # --- Roundtrip ---

    def test_full_roundtrip(self, tmp_path: Path, apt_simple: Path) -> None:
        """convert → save → load produit une trajectoire identique."""
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
        """convert_and_save() crée bien le fichier .trajcenter."""
        result = AptConverter().convert_and_save(source=apt_simple, dest_dir=tmp_path)
        assert result.exists()
        assert result.name == "simple.trajcenter"

    def test_convert_and_save_custom_stem(self, tmp_path: Path, apt_simple: Path) -> None:
        """convert_and_save() utilise le stem personnalisé."""
        result = AptConverter().convert_and_save(
            source=apt_simple, dest_dir=tmp_path, stem="ma_trajectoire"
        )
        assert result.name == "ma_trajectoire.trajcenter"
