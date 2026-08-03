#!/usr/bin/env python3
# trajcenter/rws/constants.py
"""Shared constants for the TrajCenter ABB RWS integration layer.

Author: Clement RACINET

This module centralizes the RAPID module names, protocol limits, status codes,
validation sets and default transfer settings used by the RWS reader, writer,
resolver, store scanner and service orchestrator.

ABB Route:
    N/A — local constants only.

ABB Constraints:
    Values mirror the RAPID declarations in:
    - TRAJCENTER_Types
    - TRAJCENTER_WebServices
    - TRAJCENTER_CellConfig
    - TRAJCENTER_ProcessConfig

Example:
    ```python
    from trajcenter.rws.constants import MAX_TRAJ_POINTS

    assert MAX_TRAJ_POINTS == 100000
    ```
"""

from __future__ import annotations

from typing import Final

DEFAULT_TASK: Final[str] = "T_ROB1"

TYPES_MODULE: Final[str] = "TRAJCENTER_Types"
WEB_MODULE: Final[str] = "TRAJCENTER_WebServices"
CELL_MODULE: Final[str] = "TRAJCENTER_CellConfig"
PROCESS_MODULE: Final[str] = "TRAJCENTER_ProcessConfig"

MAX_TRAJ: Final[int] = 256
MAX_TRAJ_POINTS: Final[int] = 100000
MAX_PROCESS_PARAM_SET_COUNT: Final[int] = 256
MAX_PROCESS_PARAM_PER_SET: Final[int] = 10

PROCESS_NONE: Final[int] = 0
PROCESS_ACF: Final[int] = 1
PROCESS_AAK: Final[int] = 2
PROCESS_PUSHCORP: Final[int] = 3

MOVE_TYPE_L: Final[int] = 0
MOVE_TYPE_J: Final[int] = 1
MOVE_TYPE_C: Final[int] = 2

STATUS_OK: Final[int] = 200000
STATUS_METADATA_REFRESHED: Final[int] = 200001
STATUS_TRAJECTORY_TRANSFERRED: Final[int] = 200002

ALLOWED_ZONE_TYPES: Final[frozenset[int]] = frozenset(
    {
        0,
        1,
        5,
        10,
        15,
        20,
        30,
        40,
        50,
        60,
        80,
        100,
        150,
        200,
        255,
    }
)

MOVE_TYPE_ALIASES: Final[dict[str, int]] = {
    "0": MOVE_TYPE_L,
    "l": MOVE_TYPE_L,
    "movel": MOVE_TYPE_L,
    "1": MOVE_TYPE_J,
    "j": MOVE_TYPE_J,
    "movej": MOVE_TYPE_J,
    "2": MOVE_TYPE_C,
    "c": MOVE_TYPE_C,
    "movec": MOVE_TYPE_C,
}

PROCESS_TYPE_ALIASES: Final[dict[str, int]] = {
    "": PROCESS_NONE,
    "0": PROCESS_NONE,
    "none": PROCESS_NONE,
    "1": PROCESS_ACF,
    "acf": PROCESS_ACF,
    "2": PROCESS_AAK,
    "aak": PROCESS_AAK,
    "3": PROCESS_PUSHCORP,
    "pushcorp": PROCESS_PUSHCORP,
}

ROBTARGET_COLUMNS: Final[tuple[str, ...]] = (
    "x",
    "y",
    "z",
    "q1",
    "q2",
    "q3",
    "q4",
)

CONFDATA_COLUMNS: Final[tuple[str, ...]] = (
    "cf1",
    "cf4",
    "cf6",
    "cfx",
)

EAX_COLUMNS: Final[tuple[str, ...]] = (
    "eax_a",
    "eax_b",
    "eax_c",
    "eax_d",
    "eax_e",
    "eax_f",
)

INACTIVE_EAX: Final[float] = 9e9

DEFAULT_MAX_RWS_PAYLOAD_BYTES: Final[int] = 90_000
DEFAULT_MASTERship_RETRIES: Final[int] = 3
DEFAULT_MASTERship_RETRY_DELAY_S: Final[float] = 1.0
DEFAULT_PROGRESS_UPDATE_STEP_PERCENT: Final[int] = 5

RAPID_STRING_MAX_LENGTH: Final[int] = 80
