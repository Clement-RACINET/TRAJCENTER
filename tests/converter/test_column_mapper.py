# tests/converter/test_column_mapper.py
"""Tests unitaires pour :mod:`trajcenter.converter.column_mapper`.

Couvre :
- _normalize()
- canonical_name() — cas nominaux, casse, accents, confdata, eax, inconnu
- resolve_columns() — renommage, conflit de colonnes, colonnes inconnues
"""

from __future__ import annotations

import warnings

import pandas as pd
import pytest

from trajcenter.converter.column_mapper import (
    COLUMN_ALIASES,
    _ALIAS_INDEX,
    _normalize,
    canonical_name,
    resolve_columns,
)


# ---------------------------------------------------------------------------
# _normalize
# ---------------------------------------------------------------------------


class TestNormalize:
    """Tests de la fonction _normalize."""

    def test_lowercase(self) -> None:
        """Les majuscules sont converties en minuscules."""
        assert _normalize("VITESSE") == "vitesse"

    def test_diacritics_removed(self) -> None:
        """Les accents sont supprimés."""
        assert _normalize("Répère") == "repere"
        assert _normalize("précision") == "precision"

    def test_underscore_preserved(self) -> None:
        """Les underscores sont conservés."""
        assert _normalize("pos_x") == "pos_x"
        assert _normalize("eax_a") == "eax_a"

    def test_digits_preserved(self) -> None:
        """Les chiffres sont conservés."""
        assert _normalize("cf1") == "cf1"
        assert _normalize("eax3") == "eax3"

    def test_mixed(self) -> None:
        """Combinaison casse + accent + underscore."""
        assert _normalize("PosX") == "posx"
        assert _normalize("Trans_X") == "trans_x"


# ---------------------------------------------------------------------------
# canonical_name — colonnes géométriques
# ---------------------------------------------------------------------------


class TestCanonicalNameGeometry:
    """Tests canonical_name pour les colonnes de position et orientation."""

    @pytest.mark.parametrize(
        "alias,expected",
        [
            ("x", "x"),
            ("PosX", "x"),
            ("pos_x", "x"),
            ("POSITIONX", "x"),
            ("y", "y"),
            ("PosY", "y"),
            ("TransY", "y"),
            ("z", "z"),
            ("PosZ", "z"),
            ("position_z", "z"),
            ("q1", "q1"),
            ("QW", "q1"),
            ("quaternionw", "q1"),
            ("q2", "q2"),
            ("qi", "q2"),
            ("QX", "q2"),
            ("q3", "q3"),
            ("qj", "q3"),
            ("RotY", "q3"),
            ("q4", "q4"),
            ("qk", "q4"),
            ("ROTZ", "q4"),
        ],
    )
    def test_geometry_aliases(self, alias: str, expected: str) -> None:
        """Les alias géométriques (position + quaternion) sont correctement résolus."""
        assert canonical_name(alias) == expected


# ---------------------------------------------------------------------------
# canonical_name — confdata  ← NOUVELLES ENTRÉES
# ---------------------------------------------------------------------------


class TestCanonicalNameConfdata:
    """Tests canonical_name pour les colonnes confdata ABB.

    Ces colonnes représentent la configuration articulaire d'un robtarget
    (cf1, cf4, cf6, cfx). Elles doivent être reconnues sous leur forme
    canonique ET sous les alias longs.
    """

    @pytest.mark.parametrize(
        "alias,expected",
        [
            # Forme canonique directe
            ("cf1", "cf1"),
            ("cf4", "cf4"),
            ("cf6", "cf6"),
            ("cfx", "cfx"),
            # Casse variée
            ("CF1", "cf1"),
            ("Cf4", "cf4"),
            ("CF6", "cf6"),
            ("CFX", "cfx"),
            # Alias longs
            ("confdata1", "cf1"),
            ("CONFDATA1", "cf1"),
            ("conf1", "cf1"),
            ("config1", "cf1"),
            ("configdata1", "cf1"),
            ("confdata4", "cf4"),
            ("conf4", "cf4"),
            ("config4", "cf4"),
            ("confdata6", "cf6"),
            ("conf6", "cf6"),
            ("config6", "cf6"),
            ("confdatax", "cfx"),
            ("confx", "cfx"),
            ("configx", "cfx"),
            ("configdatax", "cfx"),
        ],
    )
    def test_confdata_aliases(self, alias: str, expected: str) -> None:
        """Tous les alias confdata (casse insensible) résolvent vers le canonique."""
        assert canonical_name(alias) == expected

    def test_confdata_not_in_unresolved_after_export(self) -> None:
        """Après export tabulaire, les colonnes cf* ne tombent pas dans unresolved.

        Simule le DataFrame produit par tabular_exporter._build_traj_df()
        et vérifie que resolve_columns() ne génère aucun UserWarning.
        """
        df = pd.DataFrame(
            {
                "x": [100.0],
                "y": [200.0],
                "z": [300.0],
                "q1": [1.0],
                "q2": [0.0],
                "q3": [0.0],
                "q4": [0.0],
                "cf1": [0],
                "cf4": [0],
                "cf6": [0],
                "cfx": [0],
                "move_type": ["MoveL"],
                "speed": ["v500"],
                "zone": ["z10"],
                "tool": ["tool0"],
                "wobj": ["wobj0"],
            }
        )
        with warnings.catch_warnings():
            warnings.simplefilter("error", UserWarning)
            # Ne doit pas lever de UserWarning
            _, unresolved = resolve_columns(df)

        assert "cf1" not in unresolved
        assert "cf4" not in unresolved
        assert "cf6" not in unresolved
        assert "cfx" not in unresolved


# ---------------------------------------------------------------------------
# canonical_name — axes externes
# ---------------------------------------------------------------------------


class TestCanonicalNameExternalAxes:
    """Tests canonical_name pour les colonnes eax_*."""

    @pytest.mark.parametrize(
        "alias,expected",
        [
            ("eax_a", "eax_a"),
            ("eaxa", "eax_a"),
            ("eax1", "eax_a"),
            ("EAX_A", "eax_a"),
            ("eax_b", "eax_b"),
            ("eaxb", "eax_b"),
            ("eax2", "eax_b"),
            ("eax_f", "eax_f"),
            ("eaxf", "eax_f"),
            ("eax6", "eax_f"),
        ],
    )
    def test_eax_aliases(self, alias: str, expected: str) -> None:
        """Les alias eax_* sont correctement résolus."""
        assert canonical_name(alias) == expected


# ---------------------------------------------------------------------------
# canonical_name — mouvement / références
# ---------------------------------------------------------------------------


class TestCanonicalNameMovement:
    """Tests canonical_name pour les colonnes de mouvement et références."""

    @pytest.mark.parametrize(
        "alias,expected",
        [
            ("move_type", "move_type"),
            ("movetype", "move_type"),
            ("MOUVEMENT", "move_type"),
            ("speed", "speed"),
            ("VITESSE", "speed"),
            ("feedrate", "speed"),
            ("zone", "zone"),
            ("PRECISION", "zone"),
            ("blend", "zone"),
            ("tool", "tool"),
            ("OUTIL", "tool"),
            ("tool_name", "tool"),
            ("wobj", "wobj"),
            ("workobject", "wobj"),
            ("REPÈRE", "wobj"),
        ],
    )
    def test_movement_aliases(self, alias: str, expected: str) -> None:
        """Les alias de mouvement et références sont correctement résolus."""
        assert canonical_name(alias) == expected


# ---------------------------------------------------------------------------
# canonical_name — inconnu
# ---------------------------------------------------------------------------


class TestCanonicalNameUnknown:
    """Tests canonical_name pour les colonnes non reconnues."""

    @pytest.mark.parametrize(
        "col",
        [
            "foobar",
            "unknown_col",
            "cf2",
            "cf3",
            "cf5",
            "eax_g",
            "eax_z",
            "q5",
            "q0",
        ],
    )
    def test_unknown_returns_none(self, col: str) -> None:
        """Une colonne non reconnue retourne None."""
        assert canonical_name(col) is None


# ---------------------------------------------------------------------------
# resolve_columns
# ---------------------------------------------------------------------------


class TestResolveColumns:
    """Tests de la fonction resolve_columns."""

    def test_rename_known_columns(self) -> None:
        """Les colonnes connues sont renommées vers leur canonique."""
        df = pd.DataFrame({"PosX": [1.0], "PosY": [2.0], "PosZ": [3.0]})
        result, unresolved = resolve_columns(df)
        assert "x" in result.columns
        assert "y" in result.columns
        assert "z" in result.columns
        assert unresolved == []

    def test_unknown_columns_in_unresolved(self) -> None:
        """Les colonnes inconnues sont retournées dans unresolved."""
        df = pd.DataFrame({"x": [1.0], "custom_col": [42]})
        result, unresolved = resolve_columns(df)
        assert "custom_col" in unresolved
        assert "x" in result.columns

    def test_confdata_columns_resolved(self) -> None:
        """Les colonnes cf1/cf4/cf6/cfx sont renommées sans warning."""
        df = pd.DataFrame({"cf1": [0], "cf4": [1], "cf6": [-1], "cfx": [0]})
        with warnings.catch_warnings():
            warnings.simplefilter("error", UserWarning)
            result, unresolved = resolve_columns(df)
        assert unresolved == []
        for col in ["cf1", "cf4", "cf6", "cfx"]:
            assert col in result.columns

    def test_confdata_alias_resolved(self) -> None:
        """Les alias longs confdata sont renommés vers le canonique."""
        df = pd.DataFrame(
            {
                "confdata1": [0],
                "confdata4": [1],
                "confdata6": [-1],
                "confdatax": [0],
            }
        )
        result, unresolved = resolve_columns(df)
        assert unresolved == []
        assert "cf1" in result.columns
        assert "cf4" in result.columns
        assert "cf6" in result.columns
        assert "cfx" in result.columns

    def test_duplicate_canonical_emits_warning(self) -> None:
        """Deux colonnes résolvant vers le même canonique émettent un UserWarning."""
        df = pd.DataFrame({"x": [1.0], "PosX": [2.0]})
        with pytest.warns(UserWarning, match="résolvent vers 'x'"):
            result, _ = resolve_columns(df)
        # La première colonne est conservée
        assert result["x"].iloc[0] == 1.0

    def test_no_columns_unchanged(self) -> None:
        """Un DataFrame sans colonnes reconnues est retourné intact."""
        df = pd.DataFrame({"foo": [1], "bar": [2]})
        result, unresolved = resolve_columns(df)
        assert list(result.columns) == ["foo", "bar"]
        assert unresolved == ["foo", "bar"]

    def test_empty_dataframe(self) -> None:
        """Un DataFrame vide est traité sans erreur."""
        df = pd.DataFrame()
        result, unresolved = resolve_columns(df)
        assert result.empty
        assert unresolved == []

    def test_alias_index_completeness(self) -> None:
        """Chaque alias de COLUMN_ALIASES est présent dans _ALIAS_INDEX."""
        for canonical, aliases in COLUMN_ALIASES.items():
            for alias in aliases:
                norm = _normalize(alias)
                assert norm in _ALIAS_INDEX, (
                    f"Alias '{alias}' (normalisé: '{norm}') absent de _ALIAS_INDEX "
                    f"pour le canonique '{canonical}'"
                )
                assert _ALIAS_INDEX[norm] == canonical
