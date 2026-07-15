# trajcenter/rws/__init__.py
"""RWS integration layer for TrajCenter.

Public exports:
    - :func:`write_store_metadata` — push W1/W2/W3 to the controller
    - :func:`write_trajectory`     — push W4→W10 to the controller
    - :data:`MAX_TRAJ`
    - :data:`MAX_TOOLS`
    - :data:`MAX_WOBJS`
"""

from __future__ import annotations

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
    "write_store_metadata",
    "write_trajectory",
]
