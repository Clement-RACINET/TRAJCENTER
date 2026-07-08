# trajcenter/converter/apt_converter.py

"""
Convertisseur de fichiers APT source CATIA (``.aptsource``) vers ``.trajcenter``.

Un fichier APT CATIA contient des instructions ``GOTO`` avec position et
vecteur outil, précédées de modificateurs ``RAPID`` ou ``FEDRAT``.

Format d'une ligne GOTO attendu
---------------------------------
::

    GOTO  /   x,  y,  z,  i,  j,  k

Où ``(x, y, z)`` est la position en mm et ``(i, j, k)`` le vecteur
de direction de l'outil (normalisé).

Règles de parsing
------------------
- ``RAPID`` est **non modal** : s'applique uniquement au ``GOTO`` suivant
  (→ ``MoveJ``). Tout autre ``GOTO`` est ``MoveL``.
- ``FEDRAT`` remet le mode en ``MoveL`` (usinage).
- ``TPRINT`` fournit le nom lisible de l'outil (ex. ``T1 PointeurD10``).
  Ce nom est utilisé comme entrée ``tools[0]``. Si absent, ``defaults.tool``
  est utilisé.
- Le vecteur outil ``(i, j, k)`` est converti en quaternion ABB
  ``[q1, q2, q3, q4] = [w, x, y, z]`` via la rotation minimale
  depuis ``(0, 0, 1)``.
- La matrice de transformation CATIA (3 lignes de commentaires ``$$``
  en tête de fichier) peut être appliquée optionnellement via
  ``apply_catia_transform=True``.
- Les wobjs ne sont pas présents dans le format APT :
  ``wobjs[0]`` est initialisé depuis ``defaults.wobj``.
- Lignes ``$$``, ``PARTNO``, ``COOLNT``, ``CUTCOM``, ``MULTAX``,
  ``SPINDL``, ``CYCLE``, ``CUTTER``, ``TOOLNO``,
  ``LOADTL``, ``REWIND``, ``END`` → ignorées.

Example:
    ::

        from pathlib import Path
        from trajcenter.converter.apt_converter import AptConverter

        traj = AptConverter().convert(Path("PrepaFlans_Pointage.aptsource"))
        print(traj)
        # Trajectory(name='PrepaFlans_Pointage', points=N, tools=1, wobjs=1, ...)

        # Avec transformation CATIA
        traj = AptConverter(apply_catia_transform=True).convert(
            Path("PrepaFlans_Pointage.aptsource")
        )
"""

from __future__ import annotations

import re
import warnings
from collections.abc import Sequence
from pathlib import Path
from typing import TypedDict

import numpy as np
import pandas as pd

from trajcenter.converter.base import BaseConverter
from trajcenter.converter.defaults import ConversionDefaults
from trajcenter.core.trajectory import MoveType, SourceFormat, Trajectory, TrajectoryMeta


# ---------------------------------------------------------------------------
# TypedDicts internes
# ---------------------------------------------------------------------------


class _RawPoint(TypedDict):
    """Point brut extrait du fichier APT, avant conversion en quaternion."""

    x: float
    y: float
    z: float
    i: float
    j: float
    k: float
    is_rapid: bool


# ---------------------------------------------------------------------------
# Regex
# ---------------------------------------------------------------------------

#: Ligne GOTO : capture x, y, z, i, j, k (espaces et signes tolérés)
_RE_GOTO: re.Pattern[str] = re.compile(
    r"^\s*GOTO\s*/\s*"
    r"([+-]?\d+(?:\.\d+)?)\s*,\s*"   # x
    r"([+-]?\d+(?:\.\d+)?)\s*,\s*"   # y
    r"([+-]?\d+(?:\.\d+)?)\s*,\s*"   # z
    r"([+-]?\d+(?:\.\d+)?)\s*,\s*"   # i
    r"([+-]?\d+(?:\.\d+)?)\s*,\s*"   # j
    r"([+-]?\d+(?:\.\d+)?)",          # k
    re.IGNORECASE,
)

#: Ligne RAPID (seule sur sa ligne)
_RE_RAPID: re.Pattern[str] = re.compile(r"^\s*RAPID\s*$", re.IGNORECASE)

#: Ligne FEDRAT : reset du mode rapide
_RE_FEDRAT: re.Pattern[str] = re.compile(r"^\s*FEDRAT\s*/", re.IGNORECASE)

#: Ligne TPRINT : capture le nom de l'outil (ex. "T1 PointeurD10")
_RE_TPRINT: re.Pattern[str] = re.compile(r"^\s*TPRINT\s*/\s*(.+)", re.IGNORECASE)

#: Matrice CATIA : ligne de commentaire $$ avec exactement 4 flottants
_RE_CATIA_MATRIX_ROW: re.Pattern[str] = re.compile(
    r"^\s*\$\$\s+"
    r"([+-]?\d+\.\d+)\s+"
    r"([+-]?\d+\.\d+)\s+"
    r"([+-]?\d+\.\d+)\s+"
    r"([+-]?\d+\.\d+)\s*$"
)


# ---------------------------------------------------------------------------
# Utilitaires géométriques
# ---------------------------------------------------------------------------


def _tool_vector_to_quaternion(
    i: float, j: float, k: float
) -> tuple[float, float, float, float]:
    """Convertit un vecteur outil APT en quaternion ABB ``[w, x, y, z]``.

    Calcule la rotation minimale (angle minimal) qui amène le vecteur
    de référence ``(0, 0, 1)`` vers le vecteur outil ``(i, j, k)``.

    Convention ABB RAPID : ``[q1, q2, q3, q4] = [w, x, y, z]``
    (scalaire en premier).

    Args:
        i: Composante X du vecteur outil.
        j: Composante Y du vecteur outil.
        k: Composante Z du vecteur outil.

    Returns:
        Tuple ``(q1, q2, q3, q4)`` = ``(w, x, y, z)``.
    """
    tool = np.array([i, j, k], dtype=np.float64)
    norm = float(np.linalg.norm(tool))
    if norm > 1e-10:
        tool = tool / norm

    z_ref = np.array([0.0, 0.0, 1.0])
    dot = float(np.clip(np.dot(z_ref, tool), -1.0, 1.0))

    # Cas dégénéré : vecteur identique à z_ref → quaternion identité
    if dot >= 1.0 - 1e-10:
        return (1.0, 0.0, 0.0, 0.0)

    # Cas dégénéré : vecteur opposé à z_ref → rotation 180° autour de X
    if dot <= -1.0 + 1e-10:
        return (0.0, 1.0, 0.0, 0.0)

    axis = np.cross(z_ref, tool)
    axis = axis / np.linalg.norm(axis)
    angle = np.arccos(dot)

    half = angle / 2.0
    w = float(np.cos(half))
    x = float(axis[0] * np.sin(half))
    y = float(axis[1] * np.sin(half))
    z = float(axis[2] * np.sin(half))

    return (w, x, y, z)


def _parse_catia_matrix(lines: Sequence[str]) -> np.ndarray | None:
    """Extrait la matrice de transformation CATIA depuis les lignes du fichier.

    Cherche 3 lignes consécutives de commentaires ``$$`` contenant
    chacune 4 flottants (matrice 3×4 : rotation 3×3 + translation 3×1).
    La recherche s'arrête dès qu'une ligne non-commentaire est rencontrée
    après avoir commencé l'accumulation.

    Args:
        lines: Toutes les lignes du fichier APT.

    Returns:
        Matrice homogène ``(4, 4)`` numpy si trouvée, ``None`` sinon.
    """
    matrix_rows: list[list[float]] = []

    for line in lines:
        stripped = line.strip()

        if not stripped.startswith("$$") and not stripped.upper().startswith("PARTNO"):
            if matrix_rows:
                break
            continue

        m = _RE_CATIA_MATRIX_ROW.match(stripped)
        if m:
            matrix_rows.append([float(m.group(g)) for g in range(1, 5)])
            if len(matrix_rows) == 3:
                break
        elif matrix_rows:
            break

    if len(matrix_rows) != 3:
        return None

    mat = np.eye(4, dtype=np.float64)
    for row_idx, row in enumerate(matrix_rows):
        mat[row_idx, :3] = row[:3]   # rotation
        mat[row_idx, 3]  = row[3]    # translation
    return mat


def _apply_transform(
    points: list[_RawPoint],
    matrix: np.ndarray,
) -> list[_RawPoint]:
    """Applique la matrice homogène 4×4 aux positions et vecteurs outils.

    La translation s'applique aux positions ``(x, y, z)``.
    Seule la rotation (3×3) s'applique aux vecteurs outils ``(i, j, k)``.

    Args:
        points: Liste de :class:`_RawPoint`.
        matrix: Matrice homogène ``(4, 4)``.

    Returns:
        Nouvelle liste de :class:`_RawPoint` avec positions et vecteurs transformés.
    """
    R = matrix[:3, :3]
    transformed: list[_RawPoint] = []

    for pt in points:
        pos = np.array([pt["x"], pt["y"], pt["z"], 1.0])
        new_pos = matrix @ pos
        vec = np.array([pt["i"], pt["j"], pt["k"]])
        new_vec = R @ vec
        transformed.append(_RawPoint(
            x=float(new_pos[0]),
            y=float(new_pos[1]),
            z=float(new_pos[2]),
            i=float(new_vec[0]),
            j=float(new_vec[1]),
            k=float(new_vec[2]),
            is_rapid=pt["is_rapid"],
        ))

    return transformed


# ---------------------------------------------------------------------------
# Convertisseur
# ---------------------------------------------------------------------------


class AptConverter(BaseConverter):
    """Convertisseur de fichiers APT source CATIA vers :class:`~trajcenter.core.trajectory.Trajectory`.

    Parse toutes les instructions ``GOTO`` d'un fichier ``.aptsource``
    en tenant compte des modificateurs ``RAPID`` (→ ``MoveJ``) et
    ``FEDRAT`` (→ ``MoveL``).

    Le nom de l'outil est extrait depuis la directive ``TPRINT`` si présente,
    sinon ``defaults.tool`` est utilisé.

    Attributes:
        defaults:               Valeurs par défaut pour l'autocomplétion.
        apply_catia_transform:  Si ``True``, applique la matrice de
                                transformation CATIA si elle est présente
                                en tête de fichier. Par défaut ``False``.

    Example:
        ::

            from pathlib import Path
            from trajcenter.converter.apt_converter import AptConverter

            traj = AptConverter().convert(Path("Pointage.aptsource"))
            traj.save("trajectory_store/Pointage.trajcenter")
    """

    def __init__(
        self,
        defaults: ConversionDefaults | None = None,
        apply_catia_transform: bool = False,
    ) -> None:
        """Initialise le convertisseur APT.

        Args:
            defaults:              Valeurs par défaut pour l'autocomplétion.
            apply_catia_transform: Applique la matrice CATIA si présente.
                                   Par défaut ``False``.
        """
        super().__init__(defaults)
        self.apply_catia_transform: bool = apply_catia_transform

    def convert(self, source: Path) -> Trajectory:
        """Convertit un fichier ``.aptsource`` en :class:`~trajcenter.core.trajectory.Trajectory`.

        Args:
            source: Chemin vers le fichier ``.aptsource`` à convertir.

        Returns:
            Objet :class:`~trajcenter.core.trajectory.Trajectory` valide,
            complet et non sauvegardé.

        Raises:
            FileNotFoundError: Si le fichier source n'existe pas.
            ValueError:        Si aucune instruction GOTO n'est trouvée.
        """
        source = Path(source)
        if not source.exists():
            raise FileNotFoundError(f"Fichier introuvable : {source}")

        lines: Sequence[str] = source.read_text(
            encoding="utf-8", errors="replace").splitlines()

        # --- Matrice CATIA optionnelle ---
        catia_matrix: np.ndarray | None = None
        if self.apply_catia_transform:
            catia_matrix = _parse_catia_matrix(lines)
            if catia_matrix is None:
                warnings.warn(
                    f"{source.name} : apply_catia_transform=True mais aucune "
                    f"matrice CATIA trouvée — coordonnées brutes conservées.",
                    UserWarning,
                    stacklevel=2,
                )

        # --- Parsing : GOTO + nom outil ---
        raw_points, tool_name = self._parse_lines(lines)

        if not raw_points:
            raise ValueError(
                f"Aucune instruction GOTO trouvée dans : {source}"
            )

        # --- Transformation optionnelle ---
        if catia_matrix is not None:
            raw_points = _apply_transform(raw_points, catia_matrix)

        # --- Conversion vecteur → quaternion + construction DataFrame ---
        rows: list[dict[str, float | str]] = []
        for pt in raw_points:
            q1, q2, q3, q4 = _tool_vector_to_quaternion(pt["i"], pt["j"], pt["k"])
            move_type = MoveType.MOVE_J.value if pt["is_rapid"] else MoveType.MOVE_L.value
            rows.append({
                "x":         pt["x"],
                "y":         pt["y"],
                "z":         pt["z"],
                "q1":        q1,
                "q2":        q2,
                "q3":        q3,
                "q4":        q4,
                "move_type": move_type,
            })

        df = pd.DataFrame(rows)

        # --- Tables tools / wobjs ---
        # L'outil APT (TPRINT) est recensé en tools[0].
        # Le wobj n'existe pas en APT → defaults.wobj.
        tools: list[str] = [tool_name or self.defaults.tool]
        wobjs: list[str] = [self.defaults.wobj]

        df, autocompleted = self._autocomplete(df, tools, wobjs)

        meta = TrajectoryMeta(
            name=source.stem,
            source_file=source.name,
            source_format=SourceFormat.APT,
            autocompleted=autocompleted,
        )

        return Trajectory(meta=meta, points=df, tools=tools, wobjs=wobjs)

    # ------------------------------------------------------------------
    # Parsing interne
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_lines(
        lines: Sequence[str],
    ) -> tuple[list[_RawPoint], str | None]:
        """Parcourt les lignes et extrait les points GOTO et le nom d'outil.

        Machine à états pour ``move_type`` :

        - ``RAPID``  → prochain GOTO sera ``MoveJ`` (non modal)
        - ``FEDRAT`` → remet le mode à ``MoveL``
        - ``GOTO``   → crée un point, reset ``is_rapid`` à ``False``
        - ``TPRINT`` → capture le nom de l'outil (premier trouvé)

        Args:
            lines: Lignes brutes du fichier APT.

        Returns:
            Tuple ``(raw_points, tool_name)`` où ``tool_name`` est le nom
            extrait de ``TPRINT`` (ou ``None`` si absent).
        """
        points: list[_RawPoint] = []
        is_rapid: bool = False
        tool_name: str | None = None

        for line in lines:
            # --- TPRINT : nom de l'outil (premier trouvé) ---
            if tool_name is None:
                m_tprint = _RE_TPRINT.match(line)
                if m_tprint:
                    tool_name = m_tprint.group(1).strip()
                    continue

            # --- RAPID : non modal ---
            if _RE_RAPID.match(line):
                is_rapid = True
                continue

            # --- FEDRAT : reset mode rapide ---
            if _RE_FEDRAT.match(line):
                is_rapid = False
                continue

            # --- GOTO : point de trajectoire ---
            m = _RE_GOTO.match(line)
            if m:
                points.append(_RawPoint(
                    x=float(m.group(1)),
                    y=float(m.group(2)),
                    z=float(m.group(3)),
                    i=float(m.group(4)),
                    j=float(m.group(5)),
                    k=float(m.group(6)),
                    is_rapid=is_rapid,
                ))
                is_rapid = False  # non modal : reset après consommation

        return points, tool_name
