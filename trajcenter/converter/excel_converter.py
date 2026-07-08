# trajcenter/converter/excel_converter.py

"""
Convertisseur de fichiers Excel (``.xlsx``, ``.xls``) vers ``.trajcenter``.

Structure attendue du classeur
--------------------------------
- **Feuilles trajectoire** : toute feuille dont le nom n'est pas réservé.
  Chaque feuille produit un :class:`~trajcenter.core.trajectory.Trajectory`.
- **Feuille** ``tools`` : table des tools (colonne ``name``). Optionnelle.
- **Feuille** ``wobjs`` : table des wobjs (colonne ``name``). Optionnelle.
- **Feuille** ``meta``  : ignorée silencieusement.

Colonnes obligatoires : ``x``, ``y``, ``z``.
Toutes les autres colonnes (quaternions inclus) sont autocomplétées
depuis :class:`~trajcenter.converter.defaults.ConversionDefaults` si absentes.
Les quaternions absents sont remplacés par l'orientation identité ``[1,0,0,0]``.

Limitations connues
--------------------
- Les formules Excel ne sont pas évaluées (valeurs calculées uniquement).
- Les feuilles protégées sont ignorées avec un avertissement.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import pandas as pd

from trajcenter.converter.base import BaseConverter
from trajcenter.converter.column_mapper import resolve_columns
from trajcenter.converter.defaults import ConversionDefaults
from trajcenter.core.trajectory import SourceFormat, Trajectory, TrajectoryMeta


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

_SHEET_TOOLS    = frozenset({"tools"})
_SHEET_WOBJS    = frozenset({"wobjs", "wobj"})
_SHEET_META     = frozenset({"meta", "metadata"})
_SHEET_RESERVED = _SHEET_TOOLS | _SHEET_WOBJS | _SHEET_META

#: Seules x, y, z sont strictement obligatoires.
#: Les quaternions sont autocomplétés avec l'orientation identité si absents.
_REQUIRED_COLS: frozenset[str] = frozenset({"x", "y", "z"})

#: Quaternion identité (scalar-first : qw=1, qi=qj=qk=0).
_IDENTITY_QUATERNION: dict[str, float] = {
    "q1": 1.0, "q2": 0.0, "q3": 0.0, "q4": 0.0,
}

#: Noms de feuilles "par défaut" dont le nom ne sera pas suffixé au stem.
_SHEET_DEFAULT_NAMES = frozenset({"feuil1", "sheet1", "traj", "trajectoire"})


# ---------------------------------------------------------------------------
# Convertisseur
# ---------------------------------------------------------------------------


class ExcelConverter(BaseConverter):
    """Convertisseur de classeurs Excel vers Trajectory.

    Example:
        ::

            trajs = ExcelConverter().convert_all(Path("data/multi.xlsx"))
            traj  = ExcelConverter().convert(Path("data/single.xlsx"))
    """

    def __init__(self, defaults: ConversionDefaults | None = None) -> None:
        super().__init__(defaults)

    # ------------------------------------------------------------------
    # API publique
    # ------------------------------------------------------------------

    def convert(self, source: Path) -> Trajectory:
        """Convertit un classeur à feuille unique en trajectoire.

        Raises:
            FileNotFoundError: Si le fichier n'existe pas.
            ValueError: Si plusieurs feuilles trajectoire sont présentes.
        """
        trajs = self.convert_all(source)
        if len(trajs) > 1:
            names = [t.meta.name for t in trajs]
            raise ValueError(
                f"Le classeur contient {len(trajs)} feuilles trajectoire : "
                f"{names}. Utilisez convert_all() pour les traiter toutes."
            )
        return trajs[0]

    def convert_all(self, source: Path) -> list[Trajectory]:
        """Convertit toutes les feuilles trajectoire d'un classeur Excel.

        Raises:
            FileNotFoundError: Si le fichier n'existe pas.
            ValueError: Si aucune feuille trajectoire valide n'est trouvée.
        """
        source = Path(source).resolve()
        if not source.exists():
            raise FileNotFoundError(f"Fichier introuvable : {source}")

        xl = pd.ExcelFile(source, engine="openpyxl")
        sheet_names: list[str] = [str(s) for s in xl.sheet_names]

        shared_tools = self._load_ref_sheet(xl, sheet_names, _SHEET_TOOLS, "name")
        shared_wobjs = self._load_ref_sheet(xl, sheet_names, _SHEET_WOBJS, "name")

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
                    xl=xl,
                    sheet_name=sheet,
                    source=source,
                    shared_tools=shared_tools,
                    shared_wobjs=shared_wobjs,
                )
                trajectories.append(traj)
            except ValueError as exc:
                # Erreur de colonnes manquantes → fatale, on propage
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
        xl: pd.ExcelFile,
        sheet_name: str,
        source: Path,
        shared_tools: list[str],
        shared_wobjs: list[str],
    ) -> Trajectory:
        """Convertit une feuille trajectoire en objet Trajectory."""
        raw_df: pd.DataFrame = pd.read_excel(xl, sheet_name=sheet_name, header=0)
        raw_df = raw_df.dropna(how="all").reset_index(drop=True)

        df, unresolved = resolve_columns(raw_df)

        if unresolved:
            warnings.warn(
                f"Feuille '{sheet_name}' — colonnes non reconnues "
                f"(ignorées) : {unresolved}",
                UserWarning,
                stacklevel=3,
            )

        # Vérifie uniquement x, y, z
        missing = _REQUIRED_COLS - set(df.columns)
        if missing:
            raise ValueError(
                f"Feuille '{sheet_name}' — colonnes obligatoires manquantes : "
                f"{sorted(missing)}"
            )

        # Autocomplétion quaternion identité si absent
        autocompleted_quat: list[str] = []
        for col, val in _IDENTITY_QUATERNION.items():
            if col not in df.columns:
                df[col] = val
                autocompleted_quat.append(col)

        tools, wobjs = self._build_ref_tables(df, shared_tools, shared_wobjs)
        df = self._resolve_tool_wobj_indices(df, tools, wobjs)
        df, autocompleted = self._autocomplete(df, tools, wobjs)

        # Fusionne les colonnes autocomplétées (quaternions + reste)
        all_autocompleted = autocompleted_quat + [
            c for c in autocompleted if c not in autocompleted_quat
        ]

        traj_name = (
            source.stem
            if sheet_name.casefold() in _SHEET_DEFAULT_NAMES
            else f"{source.stem}_{sheet_name}"
        )

        meta = TrajectoryMeta(
            name=traj_name,
            source_file=source.name,
            source_format=SourceFormat.EXCEL,
            autocompleted=all_autocompleted,
        )

        return Trajectory(meta=meta, points=df, tools=tools, wobjs=wobjs)

    @staticmethod
    def _load_ref_sheet(
        xl: pd.ExcelFile,
        sheet_names: list[str],
        target_names: frozenset[str],
        name_col: str,
    ) -> list[str]:
        """Charge une feuille de référence (tools ou wobjs) si elle existe."""
        for sheet in sheet_names:
            if sheet.casefold() in target_names:
                df: pd.DataFrame = pd.read_excel(xl, sheet_name=sheet, header=0)
                df.columns = pd.Index([str(c).casefold() for c in df.columns])
                if name_col in df.columns:
                    return df[name_col].dropna().astype(str).tolist()
        return []

    @staticmethod
    def _build_ref_tables(
        df: pd.DataFrame,
        shared_tools: list[str],
        shared_wobjs: list[str],
    ) -> tuple[list[str], list[str]]:
        """Construit les tables tools/wobjs depuis le DataFrame ou les feuilles partagées."""
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
        """Remplace les colonnes tool/wobj (noms) par tool_index/wobj_index (int)."""
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
