# trajcenter/converter/tabular_converter.py

"""
Convertisseur tabulaire abstrait — logique commune Excel et CSV.

Ce module factorise toute la logique de conversion de données tabulaires
(résolution des colonnes, gestion des feuilles, tables tools/wobjs,
autocomplétion) dans une classe abstraite :class:`_TabularConverter`.

Les sous-classes n'ont qu'une seule méthode à implémenter :
:meth:`_read_sheets` qui retourne un ``dict[str, pd.DataFrame]``
(nom de feuille → DataFrame brut).

Architecture
-------------
::

    BaseConverter (ABC)
        └── _TabularConverter (ABC)
                ├── ExcelConverter   → _read_sheets() via pd.ExcelFile
                └── CsvConverter     → _read_sheets() via pd.read_csv

Feuilles réservées
-------------------
- ``tools`` / ``tool``    : table des noms de tools (colonne ``name``)
- ``wobjs`` / ``wobj``    : table des noms de wobjs (colonne ``name``)
- ``meta`` / ``metadata`` : métadonnées clé/valeur (lues, pas une trajectoire)

Toute autre feuille est traitée comme une feuille trajectoire.

Feuille meta
-------------
La feuille ``meta`` est attendue avec deux colonnes ``key`` et ``value``.
Les champs reconnus (``name``, ``robot_model``) alimentent :class:`TrajectoryMeta`.
Les champs inconnus sont stockés dans :attr:`TrajectoryMeta.extra`.
Les champs recalculés à l'import (``source_format``, ``autocompleted``,
``created_at``, ``version``, ``point_count``) sont ignorés silencieusement.

Colonnes obligatoires
----------------------
Seules ``x``, ``y``, ``z`` sont strictement obligatoires.
Les quaternions absents sont remplacés par l'orientation identité ``[1,0,0,0]``.
Toutes les autres colonnes sont autocomplétées depuis
:class:`~trajcenter.converter.defaults.ConversionDefaults`.
"""

from __future__ import annotations

import warnings
from abc import abstractmethod
from pathlib import Path

import pandas as pd

from trajcenter.converter.base import BaseConverter
from trajcenter.converter.column_mapper import resolve_columns
from trajcenter.converter.defaults import ConversionDefaults
from trajcenter.core.trajectory import SourceFormat, Trajectory, TrajectoryMeta


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

_SHEET_TOOLS: frozenset[str] = frozenset({"tools", "tool"})
_SHEET_WOBJS: frozenset[str] = frozenset({"wobjs", "wobj"})
_SHEET_META:  frozenset[str] = frozenset({"meta", "metadata"})
_SHEET_RESERVED: frozenset[str] = _SHEET_TOOLS | _SHEET_WOBJS | _SHEET_META

#: Seules x, y, z sont strictement obligatoires.
_REQUIRED_COLS: frozenset[str] = frozenset({"x", "y", "z"})

#: Quaternion identité (scalar-first : q1=qw=1, q2=qi=q3=qj=q4=qk=0).
_IDENTITY_QUATERNION: dict[str, float] = {
    "q1": 1.0, "q2": 0.0, "q3": 0.0, "q4": 0.0,
}

#: Noms de feuilles "par défaut" — le nom de feuille ne sera pas suffixé au stem.
_SHEET_DEFAULT_NAMES: frozenset[str] = frozenset({
    "feuil1", "sheet1", "traj", "trajectoire", "sheet",
})

#: Champs de TrajectoryMeta directement applicables depuis la feuille meta.
#: Tout champ inconnu va dans extra{}.
_META_APPLICABLE_FIELDS: frozenset[str] = frozenset({
    "name", "robot_model",
})

#: Champs de TrajectoryMeta à ignorer explicitement à la relecture
#: (recalculés à l'import ou non pertinents).
_META_IGNORED_FIELDS: frozenset[str] = frozenset({
    "source_format", "autocompleted", "created_at", "version",
    "point_count", "external_axes", "source_file",
})


# ---------------------------------------------------------------------------
# Convertisseur tabulaire abstrait
# ---------------------------------------------------------------------------


class _TabularConverter(BaseConverter):
    """Convertisseur abstrait pour les formats tabulaires (Excel, CSV).

    Sous-classes concrètes : :class:`~trajcenter.converter.excel_converter.ExcelConverter`
    et :class:`~trajcenter.converter.csv_converter.CsvConverter`.

    Les sous-classes doivent implémenter :meth:`_read_sheets` et
    :attr:`_source_format`.

    Attributes:
        defaults: Valeurs par défaut pour l'autocomplétion.
    """

    def __init__(self, defaults: ConversionDefaults | None = None) -> None:
        super().__init__(defaults)

    # ------------------------------------------------------------------
    # Interface à implémenter
    # ------------------------------------------------------------------

    @property
    @abstractmethod
    def _source_format(self) -> SourceFormat:
        """Format source à inscrire dans :class:`~trajcenter.core.trajectory.TrajectoryMeta`."""
        ...

    @abstractmethod
    def _read_sheets(self, source: Path) -> dict[str, pd.DataFrame]:
        """Lit le fichier source et retourne un dict ``{nom_feuille: DataFrame brut}``.

        Args:
            source: Chemin vers le fichier source (déjà vérifié existant).

        Returns:
            Dictionnaire ordonné ``{nom_feuille: DataFrame}``.
            Pour les formats mono-feuille (CSV), retourner ``{"sheet": df}``.
        """
        ...

    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------

    def convert(self, source: Path) -> Trajectory:
        """Convertit un fichier tabulaire à feuille unique en trajectoire.

        Args:
            source: Chemin vers le fichier source.

        Returns:
            Objet :class:`~trajcenter.core.trajectory.Trajectory` valide.

        Raises:
            FileNotFoundError: Si le fichier n'existe pas.
            ValueError: Si plusieurs feuilles trajectoire sont présentes
                        (utiliser :meth:`convert_all`).
        """
        trajs = self.convert_all(source)
        if len(trajs) > 1:
            names = [t.meta.name for t in trajs]
            raise ValueError(
                f"Le fichier contient {len(trajs)} feuilles trajectoire : "
                f"{names}. Utilisez convert_all() pour les traiter toutes."
            )
        return trajs[0]

    def convert_all(self, source: Path) -> list[Trajectory]:
        """Convertit toutes les feuilles trajectoire d'un fichier tabulaire.

        Args:
            source: Chemin vers le fichier source.

        Returns:
            Liste de :class:`~trajcenter.core.trajectory.Trajectory`.

        Raises:
            FileNotFoundError: Si le fichier n'existe pas.
            ValueError: Si aucune feuille trajectoire valide n'est trouvée.
        """
        source = Path(source).resolve()
        if not source.exists():
            raise FileNotFoundError(f"Fichier introuvable : {source}")

        all_sheets = self._read_sheets(source)
        sheet_names = list(all_sheets.keys())

        shared_tools    = self._extract_ref_table(all_sheets, _SHEET_TOOLS, "name")
        shared_wobjs    = self._extract_ref_table(all_sheets, _SHEET_WOBJS, "name")
        meta_overrides  = self._extract_meta_overrides(all_sheets)

        traj_sheets = [
            s for s in sheet_names
            if s.casefold() not in _SHEET_RESERVED
        ]

        if not traj_sheets:
            raise ValueError(
                f"Aucune feuille trajectoire trouvée dans : {source.name}. "
                f"Feuilles présentes : {sheet_names}"
            )

        trajectories: list[Trajectory] = []
        for sheet in traj_sheets:
            try:
                traj = self._convert_sheet(
                    raw_df=all_sheets[sheet],
                    sheet_name=sheet,
                    source=source,
                    shared_tools=shared_tools,
                    shared_wobjs=shared_wobjs,
                    meta_overrides=meta_overrides,
                )
                trajectories.append(traj)
            except ValueError as exc:
                if "obligatoires manquantes" in str(exc):
                    raise
                warnings.warn(
                    f"Feuille '{sheet}' ignorée — erreur : {exc}",
                    UserWarning,
                    stacklevel=2,
                )
            except Exception as exc:
                warnings.warn(
                    f"Feuille '{sheet}' ignorée — erreur : {exc}",
                    UserWarning,
                    stacklevel=2,
                )

        if not trajectories:
            raise ValueError(
                f"Aucune trajectoire valide extraite de : {source.name}"
            )

        return trajectories

    # ------------------------------------------------------------------
    # Étapes internes
    # ------------------------------------------------------------------

    def _convert_sheet(
        self,
        raw_df: pd.DataFrame,
        sheet_name: str,
        source: Path,
        shared_tools: list[str],
        shared_wobjs: list[str],
        meta_overrides: dict[str, str],
    ) -> Trajectory:
        """Convertit un DataFrame brut en :class:`~trajcenter.core.trajectory.Trajectory`.

        Args:
            raw_df:         DataFrame brut issu de la lecture du fichier.
            sheet_name:     Nom de la feuille (pour les messages d'erreur et le nommage).
            source:         Chemin du fichier source (pour les métadonnées).
            shared_tools:   Table tools partagée (feuille dédiée), peut être vide.
            shared_wobjs:   Table wobjs partagée (feuille dédiée), peut être vide.
            meta_overrides: Dict clé/valeur issu de la feuille meta, peut être vide.

        Returns:
            Objet :class:`~trajcenter.core.trajectory.Trajectory` valide et complet.

        Raises:
            ValueError: Si les colonnes obligatoires x, y, z sont absentes.
        """
        df = raw_df.dropna(how="all").reset_index(drop=True)
        df, unresolved = resolve_columns(df)

        if unresolved:
            warnings.warn(
                f"Feuille '{sheet_name}' — colonnes non reconnues "
                f"(ignorées) : {unresolved}",
                UserWarning,
                stacklevel=4,
            )

        missing = _REQUIRED_COLS - set(df.columns)
        if missing:
            raise ValueError(
                f"Feuille '{sheet_name}' — colonnes obligatoires manquantes : "
                f"{sorted(missing)}"
            )

        # Quaternion identité si absent
        autocompleted_quat: list[str] = []
        for col, val in _IDENTITY_QUATERNION.items():
            if col not in df.columns:
                df[col] = val
                autocompleted_quat.append(col)

        tools, wobjs = self._build_ref_tables(df, shared_tools, shared_wobjs)
        df = self._resolve_tool_wobj_indices(df, tools, wobjs)
        df, autocompleted = self._autocomplete(df, tools, wobjs)

        all_autocompleted = autocompleted_quat + [
            c for c in autocompleted if c not in autocompleted_quat
        ]

        # Nom : meta_overrides["name"] > nom calculé depuis stem + sheet
        traj_name: str = meta_overrides.get("name") or (
            source.stem
            if sheet_name.casefold() in _SHEET_DEFAULT_NAMES
            else f"{source.stem}_{sheet_name}"
        )

        # Champs directs applicables depuis meta
        robot_model: str | None = meta_overrides.get("robot_model") or None

        # Champs inconnus → extra{} (ni applicables, ni ignorés explicitement)
        extra: dict[str, str | int | float | bool | None] = {
            k: v for k, v in meta_overrides.items()
            if k not in _META_APPLICABLE_FIELDS
            and k not in _META_IGNORED_FIELDS
        }

        meta = TrajectoryMeta(
            name=traj_name,
            source_file=source.name,
            source_format=self._source_format,
            autocompleted=all_autocompleted,
            robot_model=robot_model,
            extra=extra,
        )

        return Trajectory(meta=meta, points=df, tools=tools, wobjs=wobjs)

    @staticmethod
    def _extract_meta_overrides(
        all_sheets: dict[str, pd.DataFrame],
    ) -> dict[str, str]:
        """Lit la feuille meta (format clé/valeur) et retourne un dict ``{key: value}``.

        La feuille est attendue avec deux colonnes ``key`` et ``value``
        (insensible à la casse). Les lignes avec clé ou valeur vide sont ignorées.
        Si la feuille est absente ou mal formée, retourne un dict vide
        silencieusement.

        Args:
            all_sheets: Toutes les feuilles du fichier source.

        Returns:
            Dict ``{clé_normalisée: valeur_str}``, jamais ``None``.
        """
        for sheet_name, df in all_sheets.items():
            if sheet_name.casefold() not in _SHEET_META:
                continue

            df_meta = df.copy()
            df_meta.columns = pd.Index([str(c).casefold() for c in df_meta.columns])

            if "key" not in df_meta.columns or "value" not in df_meta.columns:
                return {}

            result: dict[str, str] = {}
            for _, row in df_meta.iterrows():
                k = str(row["key"]).strip().casefold() if pd.notna(row["key"]) else ""
                v = str(row["value"]).strip() if pd.notna(row["value"]) else ""
                if k and v:
                    result[k] = v

            return result

        return {}

    @staticmethod
    def _extract_ref_table(
        all_sheets: dict[str, pd.DataFrame],
        target_names: frozenset[str],
        name_col: str,
    ) -> list[str]:
        """Extrait une table de référence (tools ou wobjs) depuis les feuilles chargées.

        Args:
            all_sheets:   Toutes les feuilles du fichier.
            target_names: Noms de feuilles réservés à chercher (ex. ``_SHEET_TOOLS``).
            name_col:     Nom de la colonne contenant les valeurs (``"name"``).

        Returns:
            Liste des noms extraits, ou liste vide si la feuille est absente.
        """
        for sheet_name, df in all_sheets.items():
            if sheet_name.casefold() in target_names:
                df_ref = df.copy()
                df_ref.columns = pd.Index([str(c).casefold() for c in df_ref.columns])
                if name_col in df_ref.columns:
                    return df_ref[name_col].dropna().astype(str).tolist()
        return []

    @staticmethod
    def _build_ref_tables(
        df: pd.DataFrame,
        shared_tools: list[str],
        shared_wobjs: list[str],
    ) -> tuple[list[str], list[str]]:
        """Construit les tables tools/wobjs depuis le DataFrame ou les feuilles partagées.

        Priorité : feuille partagée > colonne ``tool``/``wobj`` dans le DataFrame.

        Args:
            df:            DataFrame de la feuille trajectoire.
            shared_tools:  Table tools issue d'une feuille dédiée.
            shared_wobjs:  Table wobjs issue d'une feuille dédiée.

        Returns:
            Tuple ``(tools, wobjs)``.
        """
        def _extract_unique(col: str) -> list[str]:
            if col in df.columns:
                return list(dict.fromkeys(df[col].dropna().astype(str).tolist()))
            return []

        tools = shared_tools or _extract_unique("tool")
        wobjs = shared_wobjs or _extract_unique("wobj")
        return tools, wobjs

    @staticmethod
    def _resolve_tool_wobj_indices(
        df: pd.DataFrame,
        tools: list[str],
        wobjs: list[str],
    ) -> pd.DataFrame:
        """Remplace les colonnes ``tool``/``wobj`` (noms) par ``tool_index``/``wobj_index`` (int).

        Args:
            df:    DataFrame de la feuille trajectoire.
            tools: Table des noms de tools.
            wobjs: Table des noms de wobjs.

        Returns:
            DataFrame avec colonnes ``tool_index`` et ``wobj_index`` si applicable.
        """
        df = df.copy()
        for col, table, idx_col in [
            ("tool", tools, "tool_index"),
            ("wobj", wobjs, "wobj_index"),
        ]:
            if col in df.columns and table:
                name_to_idx = {name: i for i, name in enumerate(table)}
                df[idx_col] = (
                    df[col].astype(str).map(name_to_idx).fillna(0).astype(int)
                )
                df = df.drop(columns=[col])
        return df
