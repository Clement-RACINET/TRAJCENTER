# trajcenter/converter/column_mapper.py
"""Normalisation des noms de colonnes pour les convertisseurs TrajCenter.

La résolution est insensible à la casse et aux diacritiques via
:func:`_normalize`. Les alias dans :data:`COLUMN_ALIASES` doivent être
écrits sous leur forme *normalisée* (minuscules, sans accent, underscores
conservés) — c'est-à-dire tels qu'ils sortent de ``_normalize()``.
"""

from __future__ import annotations

import unicodedata
import warnings

import pandas as pd


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------


def _normalize(s: str) -> str:
    """Casefold + suppression des diacritiques (NFD → ASCII).

    Les underscores et chiffres sont conservés.

    Args:
        s: Chaîne brute.

    Returns:
        Chaîne normalisée, minuscule, sans accent.

    Example:
        ::

            _normalize("Répère")  # → "repere"
            _normalize("VITESSE") # → "vitesse"
            _normalize("PosX")    # → "posx"
            _normalize("pos_x")   # → "pos_x"  ← underscore conservé
    """
    return (
        unicodedata.normalize("NFD", s.casefold())
        .encode("ascii", "ignore")
        .decode()
    )


# ---------------------------------------------------------------------------
# Table des alias
# ---------------------------------------------------------------------------

#: Chaque alias doit être écrit tel qu'il sort de ``_normalize()``.
#: Règle pratique : minuscules, sans accent, underscores conservés.
#: Si un utilisateur peut écrire "PosX" ou "pos_x", il faut les DEUX
#: formes normalisées : "posx" et "pos_x".
COLUMN_ALIASES: dict[str, frozenset[str]] = {
    # ── Position ────────────────────────────────────────────────────────────
    "x": frozenset({
        "x", "posx", "pos_x", "positionx", "position_x",
        "tx", "transx", "trans_x",
    }),
    "y": frozenset({
        "y", "posy", "pos_y", "positiony", "position_y",
        "ty", "transy", "trans_y",
    }),
    "z": frozenset({
        "z", "posz", "pos_z", "positionz", "position_z",
        "tz", "transz", "trans_z",
    }),
    # ── Orientation (quaternion scalar-first : q1=qw, q2=qi, q3=qj, q4=qk) ─
    "q1": frozenset({"q1", "qw", "quaternionw", "quaternion_w", "rotw", "rot_w"}),
    "q2": frozenset({"q2", "qi", "qx", "quaternionx", "quaternion_x", "rotx", "rot_x"}),
    "q3": frozenset({"q3", "qj", "qy", "quaterniony", "quaternion_y", "roty", "rot_y"}),
    "q4": frozenset({"q4", "qk", "qz", "quaternionz", "quaternion_z", "rotz", "rot_z"}),
    # ── Confdata (configuration axes robot ABB — robtarget.confdata) ────────
    # Représentent les quadrants de configuration articulaire du robtarget.
    # cf1 : quadrant de l'axe 1  (Int8 nullable)
    # cf4 : quadrant de l'axe 4  (Int8 nullable)
    # cf6 : quadrant de l'axe 6  (Int8 nullable)
    # cfx : configuration étendue (Int8 nullable, bit-field)
    "cf1": frozenset({"cf1", "confdata1", "conf1", "config1", "configdata1"}),
    "cf4": frozenset({"cf4", "confdata4", "conf4", "config4", "configdata4"}),
    "cf6": frozenset({"cf6", "confdata6", "conf6", "config6", "configdata6"}),
    "cfx": frozenset({"cfx", "confdatax", "confx", "configx", "configdatax"}),
    # ── Mouvement ───────────────────────────────────────────────────────────
    "move_type": frozenset({"move_type", "movetype", "type", "mouvement", "motion"}),
    "speed":     frozenset({"speed", "vitesse", "feedrate", "feed"}),
    "zone":      frozenset({"zone", "precision", "accuracy", "blend"}),
    # ── Références outil / repère ────────────────────────────────────────────
    "tool": frozenset({"tool", "outil", "toolname", "tool_name"}),
    "wobj": frozenset({"wobj", "workobject", "repere", "frame", "wobj_name", "wobjectname"}),
    # ── Axes externes ────────────────────────────────────────────────────────
    "eax_a": frozenset({"eax_a", "eaxa", "eax1", "externala", "external_a", "exta", "ext_a"}),
    "eax_b": frozenset({"eax_b", "eaxb", "eax2", "externalb", "external_b", "extb", "ext_b"}),
    "eax_c": frozenset({"eax_c", "eaxc", "eax3", "externalc", "external_c", "extc", "ext_c"}),
    "eax_d": frozenset({"eax_d", "eaxd", "eax4", "externald", "external_d", "extd", "ext_d"}),
    "eax_e": frozenset({"eax_e", "eaxe", "eax5", "externe", "external_e", "exte", "ext_e"}),
    "eax_f": frozenset({"eax_f", "eaxf", "eax6", "externalf", "external_f", "extf", "ext_f"}),
}

# Index inverse : alias normalisé → nom canonique.
# _normalize() est appliqué sur les alias À LA CONSTRUCTION pour garantir
# que la lookup (aussi normalisée) trouve toujours ses entrées.
_ALIAS_INDEX: dict[str, str] = {
    _normalize(alias): canonical
    for canonical, aliases in COLUMN_ALIASES.items()
    for alias in aliases
}


# ---------------------------------------------------------------------------
# API publique
# ---------------------------------------------------------------------------


def canonical_name(col: str) -> str | None:
    """Retourne le nom canonique d'une colonne, ou ``None`` si non reconnue.

    Args:
        col: Nom de colonne tel qu'il apparaît dans le fichier source.

    Returns:
        Nom canonique TrajCenter, ou ``None``.

    Example:
        ::

            canonical_name("PosX")    # → "x"
            canonical_name("pos_x")   # → "x"
            canonical_name("REPÈRE")  # → "wobj"
            canonical_name("CF1")     # → "cf1"
            canonical_name("Cf4")     # → "cf4"
            canonical_name("CONFDATA6") # → "cf6"
            canonical_name("foobar")  # → None
    """
    return _ALIAS_INDEX.get(_normalize(col))


def resolve_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Renomme les colonnes d'un DataFrame vers leurs noms canoniques.

    Les colonnes non reconnues sont laissées intactes et retournées dans
    la liste ``unresolved``. Si deux colonnes résolvent vers le même
    canonique, la première est conservée et un ``UserWarning`` est émis.

    Args:
        df: DataFrame source.

    Returns:
        Tuple ``(df_renommé, non_reconnues)``.
    """
    rename_map: dict[str, str] = {}
    seen_canonical: dict[str, str] = {}
    unresolved: list[str] = []

    for col in df.columns:
        col_str = str(col)
        canon = canonical_name(col_str)
        if canon is None:
            unresolved.append(col_str)
            continue
        if canon in seen_canonical:
            warnings.warn(
                f"Deux colonnes résolvent vers '{canon}' : "
                f"'{seen_canonical[canon]}' (conservée) et '{col_str}' (ignorée).",
                UserWarning,
                stacklevel=2,
            )
            continue
        seen_canonical[canon] = col_str
        rename_map[col_str] = canon

    return df.rename(columns=rename_map), unresolved
