#!/usr/bin/env python3
# trajcenter/converter/column_mapper.py
"""Column name normalisation for TrajCenter converters.

> **Author**: Clément RACINET

Resolution is case-insensitive and diacritic-insensitive via
:func:`_normalize`.

TrajCenter v2 canonical names
-----------------------------
Legacy user aliases are still accepted, but they now resolve to the v2
canonical names:

- ``speed`` / ``vitesse`` -> ``tcp_speed``
- ``zone`` / ``precision`` -> ``zone_type``
- ``tool`` / ``outil`` -> ``tool_name``
- ``wobj`` / ``repere`` -> ``wobj_name``

ABB Route:
    N/A — local column mapping, no RWS route.

ABB Constraints:
    This module does not read or write RAPID data. It only normalises
    tabular source headers.

Example:
    ::

        canonical_name("Vitesse")  # "tcp_speed"
        canonical_name("Répère")   # "wobj_name"
"""

from __future__ import annotations

import unicodedata
import warnings

import pandas as pd

from trajcenter.core.messages import msg


def _normalize(s: str) -> str:
    """Casefold and strip diacritics.

    Underscores and digits are preserved.

    ABB Route:
        N/A.

    ABB Constraints:
        No ABB controller access.

    Args:
        s: Raw string to normalise.

    Returns:
        Normalised string: lowercase and accent-free.

    Raises:
        UnicodeError: If Python unicode normalisation fails.

    Example:
        ::

            _normalize("Répère") == "repere"
    """
    return unicodedata.normalize("NFD", s.casefold()).encode("ascii", "ignore").decode()


COLUMN_ALIASES: dict[str, frozenset[str]] = {
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
    "q1": frozenset({"q1", "qw", "quaternionw", "quaternion_w", "rotw", "rot_w"}),
    "q2": frozenset({"q2", "qi", "qx", "quaternionx", "quaternion_x", "rotx", "rot_x"}),
    "q3": frozenset({"q3", "qj", "qy", "quaterniony", "quaternion_y", "roty", "rot_y"}),
    "q4": frozenset({"q4", "qk", "qz", "quaternionz", "quaternion_z", "rotz", "rot_z"}),
    "move_type": frozenset({"move_type", "movetype", "type", "mouvement", "motion"}),
    "tcp_speed": frozenset(
        {
            "tcp_speed",
            "tcpspeed",
            "speed",
            "vitesse",
            "feedrate",
            "feed",
        }
    ),
    "zone_type": frozenset(
        {
            "zone_type",
            "zonetype",
            "zone",
            "precision",
            "accuracy",
            "blend",
        }
    ),
    "tool_name": frozenset(
        {
            "tool_name",
            "toolname",
            "tool",
            "outil",
        }
    ),
    "wobj_name": frozenset(
        {
            "wobj_name",
            "wobjname",
            "wobjectname",
            "wobj",
            "wobjs",
            "workobject",
            "workobjects",
            "repere",
            "frame",
        }
    ),
    "readconfs": frozenset(
        {
            "readconfs",
            "readconf",
            "confread",
            "conf_read",
            "read_confs",
            "read_conf",
        }
    ),
    "process_param_index": frozenset(
        {
            "process_param_index",
            "processparamindex",
            "process_index",
            "processindex",
            "param_index",
            "paramindex",
            "process",
        }
    ),
    "cf1": frozenset(
        {
            "cf1",
            "confdata1",
            "conf1",
            "config1",
            "configdata1",
        }
    ),
    "cf4": frozenset(
        {
            "cf4",
            "confdata4",
            "conf4",
            "config4",
            "configdata4",
        }
    ),
    "cf6": frozenset(
        {
            "cf6",
            "confdata6",
            "conf6",
            "config6",
            "configdata6",
        }
    ),
    "cfx": frozenset(
        {
            "cfx",
            "confdatax",
            "confx",
            "configx",
            "configdatax",
        }
    ),
    "eax_a": frozenset(
        {
            "eax_a",
            "eaxa",
            "eax1",
            "externala",
            "external_a",
            "exta",
            "ext_a",
        }
    ),
    "eax_b": frozenset(
        {
            "eax_b",
            "eaxb",
            "eax2",
            "externalb",
            "external_b",
            "extb",
            "ext_b",
        }
    ),
    "eax_c": frozenset(
        {
            "eax_c",
            "eaxc",
            "eax3",
            "externalc",
            "external_c",
            "extc",
            "ext_c",
        }
    ),
    "eax_d": frozenset(
        {
            "eax_d",
            "eaxd",
            "eax4",
            "externald",
            "external_d",
            "extd",
            "ext_d",
        }
    ),
    "eax_e": frozenset(
        {
            "eax_e",
            "eaxe",
            "eax5",
            "externe",
            "external_e",
            "exte",
            "ext_e",
        }
    ),
    "eax_f": frozenset(
        {
            "eax_f",
            "eaxf",
            "eax6",
            "externalf",
            "external_f",
            "extf",
            "ext_f",
        }
    ),
}

_ALIAS_INDEX: dict[str, str] = {
    _normalize(alias): canonical
    for canonical, aliases in COLUMN_ALIASES.items()
    for alias in aliases
}


def canonical_name(col: str) -> str | None:
    """Return the canonical column name.

    ABB Route:
        N/A.

    ABB Constraints:
        No ABB controller access.

    Args:
        col: Column name as it appears in the source file.

    Returns:
        Canonical TrajCenter name, or ``None`` if unrecognised.

    Raises:
        UnicodeError: If unicode normalisation fails.

    Example:
        ::

            canonical_name("Vitesse") == "tcp_speed"
            canonical_name("REPÈRE") == "wobj_name"
    """
    return _ALIAS_INDEX.get(_normalize(col))


def resolve_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    """Rename DataFrame columns to their canonical names.

    Unrecognised columns are left intact and returned in ``unresolved``.
    When two columns resolve to the same canonical name, the first one is
    kept and a :class:`UserWarning` is emitted.

    ABB Route:
        N/A — local DataFrame header mapping.

    ABB Constraints:
        No ABB controller access.

    Args:
        df: Source DataFrame.

    Returns:
        Tuple ``(renamed_df, unresolved_columns)``.

    Raises:
        UserWarning: Emitted when duplicate aliases resolve to the same
            canonical column.

    Example:
        ::

            df_out, unknown = resolve_columns(df)
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
                msg(
                    "DUPLICATE_CANONICAL",
                    canon=canon,
                    kept=seen_canonical[canon],
                    ignored=col_str,
                ),
                UserWarning,
                stacklevel=2,
            )
            continue
        seen_canonical[canon] = col_str
        rename_map[col_str] = canon

    return df.rename(columns=rename_map), unresolved
