"""
Modèle de données central pour une trajectoire robot ABB.

Ce module définit la structure de données principale du projet TrajCenter.
Une trajectoire est composée de métadonnées (:class:`TrajectoryMeta`),
d'un ensemble de points stockés dans un ``pandas.DataFrame``,
et de tables de nommage pour les tools et wobjs.

Format de fichier `.trajcenter`
--------------------------------
Archive ZIP contenant quatre entrées :

- ``meta.json``      : métadonnées sérialisées (Pydantic → JSON)
- ``points.parquet`` : points de trajectoire (PyArrow, compression zstd)
- ``tools.json``     : liste ordonnée des noms de tools (index → nom)
- ``wobjs.json``     : liste ordonnée des noms de wobjs (index → nom)

Les colonnes ``tool_index`` et ``wobj_index`` du DataFrame référencent
les entrées de ces listes par leur position (entier ``int16``).
Ces listes sont **toujours présentes** dans l'archive (tableau vide ``[]``
si non applicable).

Conventions ABB RAPID
----------------------
- Quaternions : ``[q1, q2, q3, q4]`` = ``[w, x, y, z]`` (scalaire en premier)
- Axes externes : ``eax_a`` … ``eax_f`` (présence dans le DataFrame = axe actif)
- La valeur sentinelle ``9E9`` pour les axes inactifs est injectée
  uniquement à la sérialisation RWS, jamais stockée dans le Parquet.
- Unités : positions en mm, rotations en degrés (axes linéaires en mm)

Autocomplétion
--------------
À la sortie de n'importe quel convertisseur, le ``.trajcenter`` est
**toujours complet** : toute colonne absente dans la source est comblée
par les valeurs de :class:`~trajcenter.converter.defaults.ConversionDefaults`.
Les colonnes autocomplétées sont listées dans :attr:`TrajectoryMeta.autocompleted`.
Ce module ne connaît pas ``ConversionDefaults`` — la logique d'autocomplétion
appartient au package ``converter``.

Example:
    Création et sauvegarde d'une trajectoire minimale::

        import pandas as pd
        from trajcenter.core.trajectory import Trajectory, TrajectoryMeta

        df = pd.DataFrame({
            "x": [100.0], "y": [200.0], "z": [300.0],
            "q1": [1.0], "q2": [0.0], "q3": [0.0], "q4": [0.0],
            "move_type":  ["MoveL"],
            "speed":      ["v500"],
            "zone":       ["z10"],
            "cf1": [0], "cf4": [0], "cf6": [0], "cfx": [0],
            "tool_index": [0],
            "wobj_index": [0],
        })
        meta = TrajectoryMeta(
            name="ma_trajectoire",
            robot_model="IRB6700",
            autocompleted=["move_type", "speed", "zone", "cf1", "cf4", "cf6", "cfx"],
        )
        traj = Trajectory(
            meta=meta,
            points=df,
            tools=["Tool_formage"],
            wobjs=["Wobj_SerreFlan"],
        )
        traj.save("trajectory_store/ma_trajectoire.trajcenter")
"""

from __future__ import annotations

import io
import json
import zipfile
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path

from typing_extensions import override

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from pydantic import BaseModel, Field, model_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class SourceFormat(StrEnum):
    """Format d'origine du fichier source ayant produit la trajectoire.

    Attributes:
        EXCEL:  Fichier Microsoft Excel (.xlsx / .xls).
        APT:    Fichier APT source CATIA (.aptsource).
        CSV:    Fichier texte délimité (.csv / .txt).
        RAPID:  Module RAPID ABB (.mod).
        MANUAL: Créé programmatiquement, sans fichier source.
    """

    EXCEL  = "excel"
    APT    = "apt"
    CSV    = "csv"
    RAPID  = "rapid"
    MANUAL = "manual"
    TRAJCENTER = "trajcenter"


class MoveType(StrEnum):
    """Type de mouvement RAPID associé à un point.

    Attributes:
        MOVE_J: Mouvement articulaire (MoveJ).
        MOVE_L: Mouvement linéaire cartésien (MoveL).
        MOVE_C: Mouvement circulaire (MoveC).
    """

    MOVE_J = "MoveJ"
    MOVE_L = "MoveL"
    MOVE_C = "MoveC"


# ---------------------------------------------------------------------------
# Schéma Parquet
# ---------------------------------------------------------------------------

#: Colonnes géométriques toujours présentes dans ``points.parquet``.
#: Ce sont les seules colonnes que ``Trajectory`` exige à l'instanciation.
#: Toutes les autres colonnes sont garanties complètes **par les convertisseurs**.
REQUIRED_COLUMNS: list[str] = ["x", "y", "z", "q1", "q2", "q3", "q4"]

#: Colonnes complétées par les convertisseurs via ``ConversionDefaults``.
#: Toujours présentes dans un ``.trajcenter`` produit par un convertisseur.
#: Absentes uniquement si la trajectoire est créée manuellement (``SourceFormat.MANUAL``).
CONVERTER_COLUMNS: list[str] = [
    "cf1", "cf4", "cf6", "cfx",
    "speed",
    "zone",
    "move_type",
    "tool_index",
    "wobj_index",
]

#: Colonnes optionnelles pures — présence = axe externe actif sur ce robot.
#: Jamais autocomplétées. Absentes = axe inexistant (9E9 injecté côté RWS).
EXTERNAL_AXIS_COLUMNS: list[str] = [
    "eax_a", "eax_b", "eax_c",
    "eax_d", "eax_e", "eax_f",
]

#: Union de toutes les colonnes reconnues (hors REQUIRED).
OPTIONAL_COLUMNS: list[str] = CONVERTER_COLUMNS + EXTERNAL_AXIS_COLUMNS

#: Mapping colonne → dtype numpy pour le cast à la validation.
COLUMN_DTYPES: dict[str, np.dtype[np.generic]] = {
    "x":          np.dtype("float64"),
    "y":          np.dtype("float64"),
    "z":          np.dtype("float64"),
    "q1":         np.dtype("float64"),
    "q2":         np.dtype("float64"),
    "q3":         np.dtype("float64"),
    "q4":         np.dtype("float64"),
    "eax_a":      np.dtype("float64"),
    "eax_b":      np.dtype("float64"),
    "eax_c":      np.dtype("float64"),
    "eax_d":      np.dtype("float64"),
    "eax_e":      np.dtype("float64"),
    "eax_f":      np.dtype("float64"),
    "tool_index": np.dtype("int16"),
    "wobj_index": np.dtype("int16"),
    # cf* → Int8 nullable pandas  (géré séparément via CONFDATA_COLUMNS)
    # speed, zone, move_type → str (pas de cast numpy)
}

#: Colonnes confdata — Int8 nullable pandas (supporte NaN, contrairement à np.int8).
CONFDATA_COLUMNS: frozenset[str] = frozenset({"cf1", "cf4", "cf6", "cfx"})

#: Mapping colonne → type PyArrow pour la construction du schéma Parquet.
#: Colonnes absentes de ce dict → ``pa.string()``.
_PA_TYPE_MAP: dict[str, pa.DataType] = {
    "x":          pa.float64(),
    "y":          pa.float64(),
    "z":          pa.float64(),
    "q1":         pa.float64(),
    "q2":         pa.float64(),
    "q3":         pa.float64(),
    "q4":         pa.float64(),
    "cf1":        pa.int8(),
    "cf4":        pa.int8(),
    "cf6":        pa.int8(),
    "cfx":        pa.int8(),
    "eax_a":      pa.float64(),
    "eax_b":      pa.float64(),
    "eax_c":      pa.float64(),
    "eax_d":      pa.float64(),
    "eax_e":      pa.float64(),
    "eax_f":      pa.float64(),
    "speed":      pa.string(),
    "zone":       pa.string(),
    "move_type":  pa.string(),
    "tool_index": pa.int16(),
    "wobj_index": pa.int16(),
}

#: Entrées ZIP obligatoires pour qu'un fichier soit un ``.trajcenter`` valide.
_REQUIRED_ZIP_ENTRIES: frozenset[str] = frozenset({"meta.json", "points.parquet"})


# ---------------------------------------------------------------------------
# Modèles Pydantic — métadonnées
# ---------------------------------------------------------------------------


class ExternalAxisConfig(BaseModel):
    """Description d'un axe externe actif dans la trajectoire.

    Cette configuration est indépendante de la cellule cible.
    Le mapping vers un actionneur physique est résolu au moment
    du transfert RWS.

    Attributes:
        axis_type: Type cinématique de l'axe. Valeurs : ``"rotational"`` ou ``"linear"``.
        unit:      Unité de la valeur stockée. ``"deg"`` pour rotatif, ``"mm"`` pour linéaire.
        label:     Nom lisible optionnel (ex. ``"Positionneur A"``).

    Example:
        ::

            ExternalAxisConfig(axis_type="rotational", unit="deg", label="Positionneur A")
    """

    axis_type: str = Field(..., description="'rotational' ou 'linear'")
    unit: str      = Field(..., description="'deg' ou 'mm'")
    label: str | None = Field(None, description="Nom lisible, ex. 'Positionneur A'")


class TrajectoryMeta(BaseModel):
    """Métadonnées d'une trajectoire ABB — stockées dans ``meta.json``.

    Ces métadonnées sont **indépendantes de la cellule cible**.
    Elles décrivent l'origine, la configuration des axes externes
    et la traçabilité de l'autocomplétion effectuée lors de la conversion.

    La logique d'autocomplétion (valeurs par défaut appliquées aux colonnes
    absentes dans la source) appartient au package ``converter`` via
    :class:`~trajcenter.converter.defaults.ConversionDefaults`.
    Ce modèle se contente de **stocker le résultat** dans ``autocompleted``.

    Attributes:
        name:          Nom de la trajectoire (identifiant humain).
        version:       Version du format ``.trajcenter``.
        created_at:    Horodatage de création (UTC).
        source_file:   Chemin ou nom du fichier source d'origine.
        source_format: Format du fichier source (:class:`SourceFormat`).
        robot_model:   Modèle de robot ABB cible (ex. ``"IRB6700-205/2.80"``).
        point_count:   Nombre de points. Mis à jour automatiquement à ``save()``.
        external_axes: Dict des axes externes actifs. Clés : ``"eax_a"`` … ``"eax_f"``.
        autocompleted: Liste des colonnes dont les valeurs ont été inférées
                       depuis ``ConversionDefaults`` (non présentes dans la source).
                       Vide si toutes les colonnes proviennent de la source.
        extra:         Champ libre pour métadonnées spécifiques au projet.

    Example:
        ::

            meta = TrajectoryMeta(
                name="Pointage_Flan_A",
                robot_model="IRB6700",
                autocompleted=["speed", "move_type"],
                external_axes={
                    "eax_a": ExternalAxisConfig(
                        axis_type="rotational", unit="deg", label="Positionneur A"
                    )
                },
            )
    """

    name: str = Field(..., description="Nom de la trajectoire")
    version: str = Field("1.0", description="Version du format .trajcenter")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Horodatage de création (UTC)",
    )
    source_file: str | None = Field(None, description="Fichier source d'origine")
    source_format: SourceFormat = Field(SourceFormat.MANUAL)
    robot_model: str | None = Field(None, description="Ex. 'IRB6700-205/2.80'")
    point_count: int = Field(
        0, description="Mis à jour automatiquement à la sauvegarde"
    )
    external_axes: dict[str, ExternalAxisConfig] = Field(
        default_factory=dict,
        description="Axes externes actifs. Clés : 'eax_a'…'eax_f'. Absent = inactif.",
    )
    autocompleted: list[str] = Field(
        default_factory=list,
        description=(
            "Colonnes dont les valeurs ont été autocomplétées depuis ConversionDefaults. "
            "Ex. : ['speed', 'move_type', 'cf1']. "
            "Vide si toutes les colonnes proviennent de la source."
        ),
    )
    extra: dict[str, str | int | float | bool | None] = Field(
        default_factory=dict,
        description="Champ libre pour métadonnées spécifiques au projet.",
    )

    @model_validator(mode="after")
    def _validate_eax_keys(self) -> TrajectoryMeta:
        """Vérifie que les clés d'axes externes sont dans l'ensemble valide.

        Returns:
            L'instance validée.

        Raises:
            ValueError: Si une clé ne correspond pas à ``eax_a``…``eax_f``.
        """
        valid = {f"eax_{c}" for c in "abcdef"}
        for key in self.external_axes:
            if key not in valid:
                raise ValueError(
                    f"Clé axe externe invalide : '{key}'. "
                    f"Attendu parmi : {sorted(valid)}"
                )
        return self


# ---------------------------------------------------------------------------
# Classe principale
# ---------------------------------------------------------------------------


class Trajectory:
    """Trajectoire robot ABB.

    Encapsule les métadonnées (:class:`TrajectoryMeta`), les points
    de trajectoire (``pandas.DataFrame``) et les tables de nommage
    des tools et wobjs dans un objet cohérent.

    Le format de fichier ``.trajcenter`` est une archive ZIP contenant :

    - ``meta.json``      : métadonnées JSON
    - ``points.parquet`` : points (PyArrow, compression zstd)
    - ``tools.json``     : liste ordonnée des noms de tools (index → nom)
    - ``wobjs.json``     : liste ordonnée des noms de wobjs (index → nom)

    Les colonnes ``tool_index`` et ``wobj_index`` du DataFrame sont des
    entiers ``int16`` référençant les listes ``tools`` et ``wobjs``.

    Un ``.trajcenter`` produit par un convertisseur est **toujours complet** :
    les colonnes ``cf1/cf4/cf6/cfx``, ``move_type``, ``speed``, ``zone``,
    ``tool_index``, ``wobj_index`` sont toujours présentes.
    Les colonnes ``eax_*`` restent optionnelles (présence = axe actif).

    Attributes:
        meta:   Métadonnées de la trajectoire.
        points: DataFrame des points. Colonnes obligatoires : x, y, z, q1, q2, q3, q4.
        tools:  Liste ordonnée des noms de tools. ``tools[i]`` = nom du tool d'index i.
        wobjs:  Liste ordonnée des noms de wobjs. ``wobjs[i]`` = nom du wobj d'index i.

    Example:
        Création, sauvegarde et rechargement::

            import pandas as pd
            from trajcenter.core.trajectory import Trajectory, TrajectoryMeta

            df = pd.DataFrame({
                "x": [100.0, 200.0], "y": [150.0, 250.0], "z": [50.0, 60.0],
                "q1": [1.0, 1.0], "q2": [0.0, 0.0],
                "q3": [0.0, 0.0], "q4": [0.0, 0.0],
                "move_type":  ["MoveL", "MoveL"],
                "speed":      ["v500", "v500"],
                "zone":       ["z0", "z0"],
                "cf1": [0, 0], "cf4": [0, 0], "cf6": [0, 0], "cfx": [0, 0],
                "tool_index": [0, 0],
                "wobj_index": [0, 0],
            })
            meta = TrajectoryMeta(name="test", autocompleted=["speed"])
            traj = Trajectory(
                meta=meta,
                points=df,
                tools=["Tool_formage"],
                wobjs=["Wobj_SerreFlan"],
            )
            traj.save("trajectory_store/test.trajcenter")

            traj2 = Trajectory.load("trajectory_store/test.trajcenter")
            print(traj2)
            # Trajectory(name='test', points=2, tools=1, wobjs=1, eax=none)
    """

    meta:   TrajectoryMeta
    points: pd.DataFrame
    tools:  list[str]
    wobjs:  list[str]

    def __init__(
        self,
        meta: TrajectoryMeta,
        points: pd.DataFrame,
        tools: list[str] | None = None,
        wobjs: list[str] | None = None,
    ) -> None:
        """Initialise la trajectoire avec validation et cast des types.

        Args:
            meta:   Métadonnées de la trajectoire.
            points: DataFrame des points. Doit contenir au minimum
                    les colonnes ``x, y, z, q1, q2, q3, q4``.
            tools:  Liste ordonnée des noms de tools (index → nom).
                    Si ``None``, initialisée à une liste vide.
            wobjs:  Liste ordonnée des noms de wobjs (index → nom).
                    Si ``None``, initialisée à une liste vide.

        Raises:
            ValueError: Si des colonnes obligatoires sont manquantes,
                        si un cast de type échoue, ou si un index
                        ``tool_index`` / ``wobj_index`` est hors bornes.
        """
        self.meta   = meta
        self.points = self._validate_and_cast(points)
        self.tools  = tools or []
        self.wobjs  = wobjs or []
        self._validate_index_bounds()

    # ------------------------------------------------------------------
    # Validation interne
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_and_cast(df: pd.DataFrame) -> pd.DataFrame:
        """Vérifie les colonnes obligatoires et normalise les types pandas.

        Args:
            df: DataFrame brut à valider.

        Returns:
            DataFrame avec types normalisés.

        Raises:
            ValueError: Si des colonnes obligatoires sont absentes
                        ou si un cast de type est impossible.
        """
        missing = set(REQUIRED_COLUMNS) - set(str(c) for c in df.columns)
        if missing:
            raise ValueError(
                f"Colonnes obligatoires manquantes : {sorted(missing)}"
            )

        df = df.copy()

        for col in df.columns:
            col_str = str(col)

            if col_str in COLUMN_DTYPES:
                target = COLUMN_DTYPES[col_str]
                try:
                    df[col] = df[col].astype(target)
                except (ValueError, TypeError) as exc:
                    raise ValueError(
                        f"Impossible de caster '{col_str}' vers {target}: {exc}"
                    ) from exc

            elif col_str in CONFDATA_COLUMNS:
                try:
                    df[col] = df[col].astype(pd.Int8Dtype())
                except (ValueError, TypeError) as exc:
                    raise ValueError(
                        f"Impossible de caster '{col_str}' vers Int8: {exc}"
                    ) from exc

        return df

    def _validate_index_bounds(self) -> None:
        """Vérifie que les index tool/wobj ne dépassent pas la taille des tables.

        Raises:
            ValueError: Si un index ``tool_index`` ou ``wobj_index`` est hors bornes.
        """
        if "tool_index" in self.points.columns and self.tools:
            max_idx = int(self.points["tool_index"].max())
            if max_idx >= len(self.tools):
                raise ValueError(
                    f"tool_index max ({max_idx}) hors bornes "
                    f"(tools contient {len(self.tools)} entrées)."
                )
        if "wobj_index" in self.points.columns and self.wobjs:
            max_idx = int(self.points["wobj_index"].max())
            if max_idx >= len(self.wobjs):
                raise ValueError(
                    f"wobj_index max ({max_idx}) hors bornes "
                    f"(wobjs contient {len(self.wobjs)} entrées)."
                )

    # ------------------------------------------------------------------
    # Propriétés utiles
    # ------------------------------------------------------------------

    @property
    def point_count(self) -> int:
        """Nombre de points dans la trajectoire."""
        return len(self.points)

    @property
    def active_external_axes(self) -> list[str]:
        """Liste des axes externes réellement présents dans le DataFrame.

        Returns:
            Liste triée des noms de colonnes ``eax_*`` présentes.

        Example:
            ::

                >>> traj.active_external_axes
                ['eax_a', 'eax_b']
        """
        eax_cols = set(EXTERNAL_AXIS_COLUMNS)
        return sorted(c for c in self.points.columns if str(c) in eax_cols)

    @property
    def has_confdata(self) -> bool:
        """Indique si les données de configuration robot (confdata) sont présentes."""
        return "cf1" in self.points.columns

    @property
    def has_move_type(self) -> bool:
        """Indique si la colonne ``move_type`` (MoveJ/MoveL/MoveC) est présente."""
        return "move_type" in self.points.columns

    @property
    def has_tool_table(self) -> bool:
        """Indique si une table de nommage des tools est définie.

        Returns:
            ``True`` si ``tools`` est non vide et que la colonne
            ``tool_index`` est présente dans le DataFrame.
        """
        return bool(self.tools) and "tool_index" in self.points.columns

    @property
    def has_wobj_table(self) -> bool:
        """Indique si une table de nommage des wobjs est définie.

        Returns:
            ``True`` si ``wobjs`` est non vide et que la colonne
            ``wobj_index`` est présente dans le DataFrame.
        """
        return bool(self.wobjs) and "wobj_index" in self.points.columns

    @property
    def is_complete(self) -> bool:
        """Indique si toutes les colonnes convertisseur sont présentes.

        Un ``.trajcenter`` complet contient ``cf1/cf4/cf6/cfx``,
        ``move_type``, ``speed``, ``zone``, ``tool_index``, ``wobj_index``
        en plus des colonnes géométriques obligatoires.

        Returns:
            ``True`` si toutes les :data:`CONVERTER_COLUMNS` sont présentes.
        """
        return all(c in self.points.columns for c in CONVERTER_COLUMNS)

    # ------------------------------------------------------------------
    # Sérialisation → .trajcenter
    # ------------------------------------------------------------------

    def save(self, path: str | Path) -> Path:
        """Sauvegarde la trajectoire dans un fichier ``.trajcenter``.

        Le fichier produit est une archive ZIP contenant :

        - ``meta.json``      : métadonnées (JSON, UTF-8)
        - ``points.parquet`` : points (PyArrow, compression zstd)
        - ``tools.json``     : liste ordonnée des noms de tools
        - ``wobjs.json``     : liste ordonnée des noms de wobjs

        Le répertoire parent est créé automatiquement si nécessaire.
        Le compteur :attr:`TrajectoryMeta.point_count` est mis à jour
        avant l'écriture.

        Args:
            path: Chemin de destination (str ou Path).
                  L'extension ``.trajcenter`` est recommandée.

        Returns:
            Chemin absolu du fichier créé.

        Example:
            ::

                saved_path = traj.save("trajectory_store/pointage.trajcenter")
        """
        dest = Path(path)
        dest.parent.mkdir(parents=True, exist_ok=True)

        self.meta.point_count = self.point_count

        pa_fields: list[pa.Field] = [
            pa.field(str(col), _PA_TYPE_MAP.get(str(col), pa.string()))
            for col in self.points.columns
        ]
        schema = pa.schema(pa_fields)
        table = pa.Table.from_pandas(
            self.points, schema=schema, preserve_index=False
        )

        with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("meta.json", self.meta.model_dump_json(indent=2))
            zf.writestr(
                "tools.json",
                json.dumps(self.tools, ensure_ascii=False, indent=2),
            )
            zf.writestr(
                "wobjs.json",
                json.dumps(self.wobjs, ensure_ascii=False, indent=2),
            )
            buf = io.BytesIO()
            pq.write_table(table, buf, compression="zstd")
            zf.writestr("points.parquet", buf.getvalue())

        return dest.resolve()

    # ------------------------------------------------------------------
    # Désérialisation ← .trajcenter
    # ------------------------------------------------------------------

    @classmethod
    def load(cls, path: str | Path) -> Trajectory:
        """Charge une trajectoire depuis un fichier ``.trajcenter``.

        Les entrées ``tools.json`` et ``wobjs.json`` sont optionnelles
        pour assurer la compatibilité avec d'éventuels fichiers anciens.

        Args:
            path: Chemin du fichier ``.trajcenter`` à charger.

        Returns:
            Instance :class:`Trajectory` reconstituée.

        Raises:
            FileNotFoundError: Si le fichier n'existe pas.
            ValueError:        Si l'archive ne contient pas les entrées
                               obligatoires (``meta.json``, ``points.parquet``).

        Example:
            ::

                traj = Trajectory.load("trajectory_store/pointage.trajcenter")
                print(traj.point_count)
                print(traj.tools)        # ['Tool_formage']
                print(traj.meta.autocompleted)  # ['speed']
        """
        src = Path(path)
        if not src.exists():
            raise FileNotFoundError(f"Fichier introuvable : {src}")

        with zipfile.ZipFile(src, "r") as zf:
            names = set(zf.namelist())
            missing = _REQUIRED_ZIP_ENTRIES - names
            if missing:
                raise ValueError(
                    f"Archive .trajcenter invalide — entrées manquantes "
                    f"{sorted(missing)} : {src}"
                )

            meta   = TrajectoryMeta.model_validate_json(zf.read("meta.json"))
            tools: list[str] = (
                json.loads(zf.read("tools.json")) if "tools.json" in names else []
            )
            wobjs: list[str] = (
                json.loads(zf.read("wobjs.json")) if "wobjs.json" in names else []
            )
            buf    = io.BytesIO(zf.read("points.parquet"))
            points = pq.read_table(buf).to_pandas()

        return cls(meta=meta, points=points, tools=tools, wobjs=wobjs)

    # ------------------------------------------------------------------
    # Représentation
    # ------------------------------------------------------------------

    @override
    def __repr__(self) -> str:
        """Représentation concise pour le débogage.

        Returns:
            Chaîne de la forme
            ``Trajectory(name='...', points=N, tools=T, wobjs=W, eax=[...], complete=bool)``.
        """
        eax = self.active_external_axes
        return (
            f"Trajectory("
            f"name={self.meta.name!r}, "
            f"points={self.point_count:,}, "
            f"tools={len(self.tools)}, "
            f"wobjs={len(self.wobjs)}, "
            f"eax={eax if eax else 'none'}, "
            f"complete={self.is_complete}"
            f")"
        )
