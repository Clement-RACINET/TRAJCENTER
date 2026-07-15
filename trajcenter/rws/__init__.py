# trajcenter/rws/__init__.py
"""RWS integration layer for TrajCenter.

Public exports:
    - :func:`write_store_metadata`     — push W1/W2/W3 to the controller
    - :func:`write_trajectory`         — push W4→W10 to the controller
    - :func:`read_selected_traj_index` — read TrajSelectedIndex
    - :func:`read_traj_ready`          — read TrajReady flag
    - :func:`read_nb_robtargets`       — read NbRobtargetsTraj
    - :func:`read_nb_traj_dispo`       — read NbTrajDispo
    - :func:`read_traj_names`          — read NomsTraj[1..n]
    - :data:`MAX_TRAJ`
    - :data:`MAX_TOOLS`
    - :data:`MAX_WOBJS`
"""

from __future__ import annotations

from trajcenter.rws.reader import (
    read_nb_robtargets,
    read_nb_traj_dispo,
    read_selected_traj_index,
    read_traj_names,
    read_traj_ready,
)
from trajcenter.rws.writer import (
    MAX_TRAJ,
    MAX_TOOLS,
    MAX_WOBJS,
    write_store_metadata,
    write_trajectory,
)

__all__ = [
    "MAX_TRAJ",
    "MAX_TOOLS",
    "MAX_WOBJS",
    "read_nb_robtargets",
    "read_nb_traj_dispo",
    "read_selected_traj_index",
    "read_traj_names",
    "read_traj_ready",
    "write_store_metadata",
    "write_trajectory",
]
