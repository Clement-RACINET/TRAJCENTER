#!/usr/bin/env python3
# trajcenter/converter/column_mapper.py
"""Column name normalisation for TrajCenter converters.

Author: Clement RACINET

Resolution is case-insensitive and diacritic-insensitive via
:func:`_normalize`. Aliases in :data:`COLUMN_ALIASES` must be written
in their *normalised* form (lowercase, no accent, underscores preserved)
— i.e. exactly as they come out of ``_normalize()``.
"""

from __future__ import annotations

import unicodedata
import warnings

import pandas as pd


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------


def _normalize(s: str) -> str:
    """Casefold and strip diacritics (NFD → ASCII).

    Underscores and digits are preserved.

    Args:
        s: Raw string.

    Returns:
        Normalised string: lowercase, no accent.

    Example:
        ::

            _normalize("Répère")  # → "repere"
            _normalize("VITESSE") # → "vitesse"
            _normalize("PosX")    # → "posx"
            _normalize("pos_x")   # → "pos_x"  ← underscore preserved
    """
    return unicodedata.normalize("NFD", s.casefold()).encode("ascii", "ignore").decode()


# ---------------------------------------------------------------------------
# Alias table
# ---------------------------------------------------------------------------

#: Every alias must be written exactly as it comes out of ``_normalize()``.
#: Practical rule: lowercase, no accent, underscores preserved.
#: If a user may write both ``"PosX"`` and ``"pos_x"``, both normalised
#: forms must be listed: ``"posx"`` and ``"pos_x"``.
COLUMN_ALIASES: dict[str, frozenset[str]] = {
    # ── Position ────────────────────────────────────────────────────────────
    "x": frozenset(
        {
            "x",
            "posx",
            "pos_x",
            "positionx",
            "position_x",
            "tx",
            "transx",
            "trans_x",
        }
    ),
    "y": frozenset(
        {
            "y",
            "posy",
            "pos_y",
            "positiony",
            "position_y",
            "ty",
            "transy",
            "trans_y",
        }
    ),
    "z": frozenset(
        {
            "z",
            "posz",
            "pos_z",
            "positionz",
            "position_z",
            "tz",
            "transz",
            "trans_z",
        }
    ),
    # ── Orientation (quaternion scalar-first: q1=qw, q2=qi, q3=qj, q4=qk) ─
    "q1": frozenset({"q1", "qw", "quaternionw", "quaternion_w", "rotw", "rot_w"}),
    "q2": frozenset({"q2", "qi", "qx", "quaternionx", "quaternion_x", "rotx", "rot_x"}),
    "q3": frozenset({"q3", "qj", "qy", "quaterniony", "quaternion_y", "roty", "rot_y"}),
    "q4": frozenset({"q4", "qk", "qz", "quaternionz", "quaternion_z", "rotz", "rot_z"}),
    # ── Confdata (ABB robot axis configuration — robtarget.confdata) ────────
    # Represent the joint configuration quadrants of the robtarget.
    # cf1 : axis 1 quadrant  (nullable Int8)
    # cf4 : axis 4 quadrant  (nullable Int8)
    # cf6 : axis 6 quadrant  (nullable Int8)
    # cfx : extended configuration (nullable Int8, bit-field)
    "cf1": frozenset({"cf1", "confdata1", "conf1", "config1", "configdata1"}),
    "cf4": frozenset({"cf4", "confdata4", "conf4", "config4", "configdata4"}),
    "cf6": frozenset({"cf6", "confdata6", "conf6", "config6", "configdata6"}),
    "cfx": frozenset({"cfx", "confdatax", "confx", "configx", "configdatax"}),
    # ── Movement ────────────────────────────────────────────────────────────
    "move_type": frozenset({"move_type", "movetype", "type", "mouvement", "motion"}),
    "speed": frozenset({"speed", "vitesse", "feedrate", "feed"}),
    "zone": frozenset({"zone", "precision", "accuracy", "blend"}),
    # ── Tool / work-object references ───────────────────────────────────────
    "tool": frozenset({"tool", "outil", "toolname", "tool_name"}),
    "wobj": frozenset(
        {"wobj", "workobject", "repere", "frame", "wobj_name", "wobjectname"}
    ),
    # ── External axes ────────────────────────────────────────────────────────
    "eax_a": frozenset(
        {"eax_a", "eaxa", "eax1", "externala", "external_a", "exta", "ext_a"}
    ),
    "eax_b": frozenset(
        {"eax_b", "eaxb", "eax2", "externalb", "external_b", "extb", "ext_b"}
    ),
    "eax_c": frozenset(
        {"eax_c", "eaxc", "eax3", "externalc", "external_c", "extc", "ext_c"}
    ),
    "eax_d": frozenset(
        {"eax_d", "eaxd", "eax4", "externald", "external_d", "extd", "ext_d"}
    ),
    "eax_e": frozenset(
        {"eax_e", "eaxe", "eax5", "externe", "external_e", "exte", "ext_e"}
    ),
    "eax_f": frozenset(
        {"eax_f", "eaxf", "eax6", "externalf", "external_f", "extf", "ext_f"}
    ),
}

# Reverse index: normalised alias → canonical name.
# ``_normalize()`` is applied to aliases AT BUILD TIME to guarantee that
# the lookup (also normalised) always finds its entries.
_ALIAS_INDEX: dict[str, str] = {
    _normalize(alias): canonical
    for canonical, aliases in COLUMN_ALIASES.items()
    for alias in aliases
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def canonical_name(col: str) -> str | None:
    """Return the canonical name of a column, or ``None`` if unrecognised.

    Args:
        col: Column name as it appears in the source file.

    Returns:
        TrajCenter canonical name, or ``None``.

    Example:
        ::

            canonical_name("PosX")      # → "x"
            canonical_name("pos_x")     # → "x"
            canonical_name("REPÈRE")    # → "wobj"
            canonical_name("CF1")       # → "cf1"
            canonical_name("Cf4")       # → "cf4"
            canonical_name("CONFDATA6") # → "cf6"
            canonical_name("foobar")    # → None
    """
    return _ALIAS_INDEX.get(_normalize(col))


def resolve_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Rename ``DataFrame`` columns to their canonical names.

    Unrecognised columns are left intact and returned in the
    ``unresolved`` list. If two columns resolve to the same canonical
    name, the first one is kept and a ``UserWarning`` is emitted.

    Args:
        df: Source ``DataFrame``.

    Returns:
        Tuple ``(renamed_df, unresolved)`` where ``unresolved`` is the
        list of column names that could not be mapped to a canonical name.
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
                f"Two columns resolve to '{canon}': "
                f"'{seen_canonical[canon]}' (kept) and '{col_str}' (ignored).",
                UserWarning,
                stacklevel=2,
            )
            continue
        seen_canonical[canon] = col_str
        rename_map[col_str] = canon

    return df.rename(columns=rename_map), unresolved
