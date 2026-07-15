#!/usr/bin/env python3
# trajcenter/rws/_utils.py
"""Shared low-level utilities for the RWS integration layer.

Author: Clement RACINET
"""

from __future__ import annotations


def symbol(task: str, module: str, var: str) -> str:
    """Build a RWS RAPID symbol URL path.

    Args:
        task: RAPID task name, e.g. ``"T_ROB1"``.
        module: RAPID module name, e.g. ``"TRAJCENTER"``.
        var: Variable name, e.g. ``"NbTrajDispo"`` or
            ``"NomsTraj/[1]"``.

    Returns:
        Symbol URL path, e.g.
        ``"RAPID/T_ROB1/TRAJCENTER/NbTrajDispo"``.

    Example:
        ::

            >>> symbol("T_ROB1", "TRAJCENTER", "TrajReady")
            'RAPID/T_ROB1/TRAJCENTER/TrajReady'
            >>> symbol("T_ROB1", "TRAJCENTER", "NomsTraj/[1]")
            'RAPID/T_ROB1/TRAJCENTER/NomsTraj/[1]'
    """
    return f"RAPID/{task}/{module}/{var}"
