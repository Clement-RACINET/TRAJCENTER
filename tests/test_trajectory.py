# tests/test_trajectory.py

"""
Tests unitaires pour :mod:`trajcenter.core.trajectory`.

Couvre :
- La validation des colonnes obligatoires
- Le cast des types pandas
- La validation des bornes tool_index / wobj_index
- La sérialisation / désérialisation ``.trajcenter``
- Les propriétés utilitaires
- La représentation ``__repr__``
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pandas as pd
import pytest

from trajcenter.core.trajectory import (
    CONVERTER_COLUMNS,
    EXTERNAL_AXIS_COLUMNS,
    REQUIRED_COLUMNS,
    ExternalAxisConfig,
    MoveType,
    SourceFormat,
    Trajectory,
    TrajectoryMeta,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def minimal_df() -> pd.DataFrame:
    """DataFrame minimal avec uniquement les colonnes obligatoires."""
    return pd.DataFrame({
        "x": [100.0, 200.0],
        "y": [150.0, 250.0],
        "z": [50.0,  60.0],
        "q1": [1.0, 1.0],
        "q2": [0.0, 0.0],
        "q3": [0.0, 0.0],
        "q4": [0.0, 0.0],
    })


@pytest.fixture
def complete_df() -> pd.DataFrame:
    """DataFrame complet avec toutes les colonnes CONVERTER_COLUMNS."""
    return pd.DataFrame({
        "x": [100.0, 200.0],
        "y": [150.0, 250.0],
        "z": [50.0,  60.0],
        "q1": [1.0, 1.0],
        "q2": [0.0, 0.0],
        "q3": [0.0, 0.0],
        "q4": [0.0, 0.0],
        "cf1": [0, 0],
        "cf4": [0, 0],
        "cf6": [0, 0],
        "cfx": [0, 0],
        "move_type":  ["MoveL", "MoveL"],
        "speed":      ["v500", "v500"],
        "zone":       ["z10",  "z10"],
        "tool_index": [0, 0],
        "wobj_index": [0, 0],
    })


@pytest.fixture
def complete_df_with_eax() -> pd.DataFrame:
    """DataFrame complet avec un axe externe actif (eax_a)."""
    return pd.DataFrame({
        "x": [100.0], "y": [150.0], "z": [50.0],
        "q1": [1.0], "q2": [0.0], "q3": [0.0], "q4": [0.0],
        "cf1": [0], "cf4": [0], "cf6": [0], "cfx": [0],
        "move_type":  ["MoveL"],
        "speed":      ["v500"],
        "zone":       ["z10"],
        "tool_index": [0],
        "wobj_index": [0],
        "eax_a":      [45.0],
    })


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


@pytest.fixture
def simple_trajectory(minimal_meta: TrajectoryMeta, complete_df: pd.DataFrame) -> Trajectory:
    """Trajectoire simple sans axes externes."""
    return Trajectory(
        meta=minimal_meta,
        points=complete_df,
        tools=["Tool_formage"],
        wobjs=["Wobj_SerreFlan"],
    )


# ---------------------------------------------------------------------------
# Tests — TrajectoryMeta
# ---------------------------------------------------------------------------


class TestTrajectoryMeta:
    """Tests du modèle Pydantic TrajectoryMeta."""

    def test_defaults(self) -> None:
        """Les valeurs par défaut sont correctement initialisées."""
        meta = TrajectoryMeta(name="traj")
        assert meta.version == "1.0"
        assert meta.source_format == SourceFormat.MANUAL
        assert meta.point_count == 0
        assert meta.external_axes == {}
        assert meta.autocompleted == []
        assert meta.extra == {}

    def test_valid_eax_keys(self) -> None:
        """Les clés eax_a…eax_f sont acceptées."""
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
        """Une clé d'axe externe invalide lève ValueError."""
        with pytest.raises(ValueError, match="Clé axe externe invalide"):
            TrajectoryMeta(
                name="traj",
                external_axes={
                    "eax_z": ExternalAxisConfig(axis_type="rotational", unit="deg")
                },
            )

    def test_autocompleted_stored(self) -> None:
        """Le champ autocompleted est correctement stocké."""
        meta = TrajectoryMeta(
            name="traj",
            autocompleted=["speed", "move_type", "cf1"],
        )
        assert "speed" in meta.autocompleted
        assert "move_type" in meta.autocompleted
        assert len(meta.autocompleted) == 3

    def test_serialization_roundtrip(self) -> None:
        """Sérialisation JSON → désérialisation Pydantic est sans perte."""
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
    """Tests de validation à l'instanciation de Trajectory."""

    def test_missing_required_column_raises(self, minimal_meta: TrajectoryMeta) -> None:
        """Une colonne obligatoire manquante lève ValueError."""
        df = pd.DataFrame({"x": [1.0], "y": [2.0], "z": [3.0]})  # q1..q4 absents
        with pytest.raises(ValueError, match="Colonnes obligatoires manquantes"):
            Trajectory(meta=minimal_meta, points=df)

    def test_all_required_columns_missing_raises(self, minimal_meta: TrajectoryMeta) -> None:
        """Un DataFrame vide de colonnes lève ValueError."""
        df = pd.DataFrame({"foo": [1.0]})
        with pytest.raises(ValueError, match="Colonnes obligatoires manquantes"):
            Trajectory(meta=minimal_meta, points=df)

    def test_float_cast(self, minimal_meta: TrajectoryMeta, minimal_df: pd.DataFrame) -> None:
        """Les colonnes float64 sont correctement castées depuis int."""
        df = minimal_df.copy()
        df["x"] = df["x"].astype(int)
        traj = Trajectory(meta=minimal_meta, points=df)
        assert traj.points["x"].dtype == "float64"

    def test_confdata_cast_to_int8_nullable(
        self, minimal_meta: TrajectoryMeta, complete_df: pd.DataFrame
    ) -> None:
        """Les colonnes confdata sont castées en Int8 nullable."""
        traj = Trajectory(meta=minimal_meta, points=complete_df)
        for col in ["cf1", "cf4", "cf6", "cfx"]:
            assert traj.points[col].dtype == pd.Int8Dtype()

    def test_tool_index_out_of_bounds_raises(
        self, minimal_meta: TrajectoryMeta, complete_df: pd.DataFrame
    ) -> None:
        """Un tool_index hors bornes lève ValueError."""
        df = complete_df.copy()
        df["tool_index"] = 5  # tools ne contiendra qu'un seul élément
        with pytest.raises(ValueError, match="tool_index max"):
            Trajectory(meta=minimal_meta, points=df, tools=["Tool_formage"])

    def test_wobj_index_out_of_bounds_raises(
        self, minimal_meta: TrajectoryMeta, complete_df: pd.DataFrame
    ) -> None:
        """Un wobj_index hors bornes lève ValueError."""
        df = complete_df.copy()
        df["wobj_index"] = 3
        with pytest.raises(ValueError, match="wobj_index max"):
            Trajectory(meta=minimal_meta, points=df, wobjs=["Wobj_SerreFlan"])

    def test_valid_index_bounds_pass(
        self, minimal_meta: TrajectoryMeta, complete_df: pd.DataFrame
    ) -> None:
        """Des index dans les bornes ne lèvent pas d'erreur."""
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
        """tools et wobjs valent [] si non fournis."""
        traj = Trajectory(meta=minimal_meta, points=minimal_df)
        assert traj.tools == []
        assert traj.wobjs == []


# ---------------------------------------------------------------------------
# Tests — propriétés
# ---------------------------------------------------------------------------


class TestTrajectoryProperties:
    """Tests des propriétés utilitaires de Trajectory."""

    def test_point_count(self, simple_trajectory: Trajectory) -> None:
        """point_count retourne le nombre de lignes du DataFrame."""
        assert simple_trajectory.point_count == 2

    def test_active_external_axes_none(self, simple_trajectory: Trajectory) -> None:
        """active_external_axes est vide si aucune colonne eax_* présente."""
        assert simple_trajectory.active_external_axes == []

    def test_active_external_axes_with_eax(
        self, minimal_meta: TrajectoryMeta, complete_df_with_eax: pd.DataFrame
    ) -> None:
        """active_external_axes retourne les colonnes eax_* présentes."""
        traj = Trajectory(
            meta=minimal_meta,
            points=complete_df_with_eax,
            tools=["Tool_formage"],
            wobjs=["Wobj_SerreFlan"],
        )
        assert traj.active_external_axes == ["eax_a"]

    def test_has_confdata_true(self, simple_trajectory: Trajectory) -> None:
        """has_confdata est True si cf1 est présente."""
        assert simple_trajectory.has_confdata is True

    def test_has_confdata_false(
        self, minimal_meta: TrajectoryMeta, minimal_df: pd.DataFrame
    ) -> None:
        """has_confdata est False si cf1 est absente."""
        traj = Trajectory(meta=minimal_meta, points=minimal_df)
        assert traj.has_confdata is False

    def test_has_move_type_true(self, simple_trajectory: Trajectory) -> None:
        """has_move_type est True si move_type est présente."""
        assert simple_trajectory.has_move_type is True

    def test_has_tool_table_true(self, simple_trajectory: Trajectory) -> None:
        """has_tool_table est True si tools non vide et tool_index présente."""
        assert simple_trajectory.has_tool_table is True

    def test_has_tool_table_false_no_tools(
        self, minimal_meta: TrajectoryMeta, complete_df: pd.DataFrame
    ) -> None:
        """has_tool_table est False si tools est vide."""
        traj = Trajectory(meta=minimal_meta, points=complete_df)
        assert traj.has_tool_table is False

    def test_has_wobj_table_true(self, simple_trajectory: Trajectory) -> None:
        """has_wobj_table est True si wobjs non vide et wobj_index présente."""
        assert simple_trajectory.has_wobj_table is True

    def test_is_complete_true(self, simple_trajectory: Trajectory) -> None:
        """is_complete est True si toutes les CONVERTER_COLUMNS sont présentes."""
        assert simple_trajectory.is_complete is True

    def test_is_complete_false(
        self, minimal_meta: TrajectoryMeta, minimal_df: pd.DataFrame
    ) -> None:
        """is_complete est False si des CONVERTER_COLUMNS sont absentes."""
        traj = Trajectory(meta=minimal_meta, points=minimal_df)
        assert traj.is_complete is False

    def test_repr(self, simple_trajectory: Trajectory) -> None:
        """__repr__ contient les informations clés."""
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
    """Tests de sérialisation / désérialisation .trajcenter."""

    def test_save_creates_file(
        self, tmp_path: Path, simple_trajectory: Trajectory
    ) -> None:
        """save() crée bien le fichier .trajcenter."""
        dest = tmp_path / "test.trajcenter"
        result = simple_trajectory.save(dest)
        assert result.exists()
        assert result.suffix == ".trajcenter"

    def test_save_returns_absolute_path(
        self, tmp_path: Path, simple_trajectory: Trajectory
    ) -> None:
        """save() retourne un chemin absolu."""
        dest = tmp_path / "test.trajcenter"
        result = simple_trajectory.save(dest)
        assert result.is_absolute()

    def test_save_creates_parent_dirs(
        self, tmp_path: Path, simple_trajectory: Trajectory
    ) -> None:
        """save() crée les répertoires parents si nécessaire."""
        dest = tmp_path / "subdir" / "nested" / "test.trajcenter"
        simple_trajectory.save(dest)
        assert dest.exists()

    def test_save_zip_contains_required_entries(
        self, tmp_path: Path, simple_trajectory: Trajectory
    ) -> None:
        """L'archive ZIP contient les quatre entrées attendues."""
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
        """save() met à jour meta.point_count avant l'écriture."""
        dest = tmp_path / "test.trajcenter"
        simple_trajectory.save(dest)
        with zipfile.ZipFile(dest, "r") as zf:
            meta_raw = json.loads(zf.read("meta.json"))
        assert meta_raw["point_count"] == 2

    def test_save_tools_wobjs_json(
        self, tmp_path: Path, simple_trajectory: Trajectory
    ) -> None:
        """tools.json et wobjs.json contiennent les bonnes listes."""
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
        """save() + load() reconstituent une trajectoire identique."""
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
        """Les valeurs numériques sont préservées après save/load."""
        dest = tmp_path / "test.trajcenter"
        simple_trajectory.save(dest)
        loaded = Trajectory.load(dest)

        pd.testing.assert_series_equal(
            loaded.points["x"].reset_index(drop=True),
            simple_trajectory.points["x"].reset_index(drop=True),
            check_names=False,
        )

    def test_load_autocompleted_preserved(
        self, tmp_path: Path, minimal_meta: TrajectoryMeta, complete_df: pd.DataFrame
    ) -> None:
        """Le champ autocompleted est préservé après save/load."""
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
        """load() lève FileNotFoundError si le fichier n'existe pas."""
        with pytest.raises(FileNotFoundError, match="Fichier introuvable"):
            Trajectory.load(tmp_path / "inexistant.trajcenter")

    def test_load_invalid_archive_raises(self, tmp_path: Path) -> None:
        """load() lève ValueError si l'archive est incomplète."""
        dest = tmp_path / "bad.trajcenter"
        with zipfile.ZipFile(dest, "w") as zf:
            zf.writestr("meta.json", "{}")
            # points.parquet absent intentionnellement
        with pytest.raises(ValueError, match="entrées manquantes"):
            Trajectory.load(dest)

    def test_load_backward_compat_no_tools_wobjs(
        self,
        tmp_path: Path,
        minimal_meta: TrajectoryMeta,
        complete_df: pd.DataFrame,
    ) -> None:
        """load() tolère l'absence de tools.json et wobjs.json (anciens fichiers)."""
        import io
        import pyarrow as pa
        import pyarrow.parquet as pq

        dest = tmp_path / "old.trajcenter"
        traj = Trajectory(meta=minimal_meta, points=complete_df)

        # Écriture manuelle sans tools.json / wobjs.json
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
        """Les colonnes eax_* sont préservées après save/load."""
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
