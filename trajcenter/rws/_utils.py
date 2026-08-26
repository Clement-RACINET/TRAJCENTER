#!/usr/bin/env python3
# trajcenter/rws/_utils.py
"""Shared low-level utilities for the RWS integration layer.

> **Author**: Clément RACINET
"""

from __future__ import annotations

from urllib.parse import quote


def symbol(task: str, module: str, var: str) -> str:
    """Build a RWS RAPID symbol URL path for a simple variable.

    ABB Route:
        Used with ``GET /rw/rapid/symbol/data/{symbolurl}`` and
        ``POST /rw/rapid/symbol/data/{symbolurl}?action=set``.

    ABB Constraints:
        The returned path uses ABB RWS symbol URL notation. For simple
        variables, no percent-encoding is required.

    Args:
        task: RAPID task name, e.g. ``"T_ROB1"``.
        module: RAPID module name, e.g. ``"TRAJCENTER"``.
        var: Variable name, e.g. ``"selectedTrajIndex"``.

    Returns:
        Symbol URL path, e.g.
        ``"RAPID/T_ROB1/TRAJCENTER/selectedTrajIndex"``.

    Example:
        ::

            url = symbol(
                "T_ROB1",
                "TRAJCENTER",
                "trajReady",
            )
            assert url == "RAPID/T_ROB1/TRAJCENTER/trajReady"
    """
    return f"RAPID/{task}/{module}/{var}"


def symbol_array_element(
    task: str,
    module: str,
    variable: str,
    index: int,
) -> str:
    """Build a RWS symbol URL for one RAPID array element.

    ABB Route:
        Used with ``GET /rw/rapid/symbol/data/{symbolurl}`` and
        ``POST /rw/rapid/symbol/data/{symbolurl}?action=set``.

    ABB Constraints:
        RAPID arrays use braces, e.g. ``trajData{1}``. In the RWS URL,
        braces must be percent-encoded as ``%7B`` and ``%7D``.

    Args:
        task: RAPID task name, e.g. ``"T_ROB1"``.
        module: RAPID module name, e.g. ``"TRAJCENTER"``.
        variable: RAPID array variable name, e.g. ``"trajData"``.
        index: One-based RAPID array index.

    Returns:
        URL-safe RWS symbol path, e.g.
        ``"RAPID/T_ROB1/TRAJCENTER/trajData%7B1%7D"``.

    Raises:
        ValueError: If ``index`` is lower than ``1``.

    Example:
        ::

            url = symbol_array_element(
                "T_ROB1",
                "TRAJCENTER",
                "trajData",
                1,
            )
            assert url == (
                "RAPID/T_ROB1/TRAJCENTER/trajData%7B1%7D"
            )
    """
    if index < 1:
        raise ValueError(f"RAPID array index must be >= 1, got {index}")

    raw_symbolurl = f"RAPID/{task}/{module}/{variable}{{{index}}}"
    return quote(raw_symbolurl, safe="/")


def symbol_record_array_field(
    task: str,
    module: str,
    variable: str,
    index: int,
    field: str,
) -> str:
    """Build a RWS symbol URL for a field of a RAPID record array element.

    ABB Route:
        Used with ``GET /rw/rapid/symbol/data/{symbolurl}`` and
        ``POST /rw/rapid/symbol/data/{symbolurl}?action=set``.

    ABB Constraints:
        RAPID array braces are percent-encoded. The resulting RAPID
        symbolic path is conceptually ``variable{index}.field``.
        Field-level record access must be validated on the target
        RobotWare version before being used for production writes.

    Args:
        task: RAPID task name, e.g. ``"T_ROB1"``.
        module: RAPID module name, e.g. ``"TRAJCENTER"``.
        variable: RAPID array variable name, e.g. ``"trajData"``.
        index: One-based RAPID array index.
        field: RAPID record field name, e.g. ``"moveType"``.

    Returns:
        URL-safe RWS symbol path, e.g.
        ``"RAPID/T_ROB1/TRAJCENTER/trajData%7B1%7D.moveType"``.

    Raises:
        ValueError: If ``index`` is lower than ``1`` or if ``field`` is
            empty.

    Example:
        ::

            url = symbol_record_array_field(
                "T_ROB1",
                "TRAJCENTER",
                "trajData",
                1,
                "moveType",
            )
            assert url == (
                "RAPID/T_ROB1/TRAJCENTER/"
                "trajData%7B1%7D.moveType"
            )
    """
    if index < 1:
        raise ValueError(f"RAPID array index must be >= 1, got {index}")
    if not field:
        raise ValueError("RAPID record field name must not be empty")

    raw_symbolurl = f"RAPID/{task}/{module}/{variable}{{{index}}}.{field}"
    return quote(raw_symbolurl, safe="/.")
