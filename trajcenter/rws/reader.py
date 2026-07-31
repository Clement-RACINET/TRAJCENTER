#!/usr/bin/env python3
# trajcenter/rws/reader.py
"""RWS reader — reads TrajCenter v2 RAPID variables from the ABB controller.

> **Author**: Clément RACINET

This module is the TrajCenter read access layer for the
``TRAJCENTER_WebServices``, ``TRAJCENTER_CellConfig`` and
``TRAJCENTER_ProcessConfig`` RAPID modules.

All simple-variable reads use ``GET /rw/rapid/symbol/data/{symbolurl}`` via
``get_variable`` from ``abb_rws_client_python_rw6.highlevel.variables``.
Array-length discovery uses ``GET /rw/rapid/symbol/properties/{symbolurl}``
via ``get_array_length`` from ``abb_rws_client_python_rw6.highlevel.symbol``.

RAPID variable map
------------------

Request and status variables (``TRAJCENTER_WebServices``):

=====  ======================  ===========  ================================
Ref    RAPID variable          RAPID type   Python return
=====  ======================  ===========  ================================
R1     selectedTrajIndex       num          ``int``
R2     sendTrajRequest         bool         ``bool``
R3     refreshMetaRequest      bool         ``bool``
R4     trajReady               bool         ``bool``
R5     transferError           bool         ``bool``
R6     lastErrorCode           num          ``int``
R7     lastError               string       ``str``
R8     transferProgress        num          ``int``
R9     nbLoadedTrajPoints      num          ``int``
R10    nbTrajAvailable         num          ``int``
R11    trajectories{i}         record       ``list[str]`` names
=====  ======================  ===========  ================================

Default variables read before trajectory transfer (``TRAJCENTER_WebServices``):

====================  =========================
RAPID variable         Python field
====================  =========================
hasDefaultTcpSpeed     ``RobotDefaults.has_tcp_speed``
defaultTcpSpeed        ``RobotDefaults.tcp_speed``
hasDefaultZoneType     ``RobotDefaults.has_zone_type``
defaultZoneType        ``RobotDefaults.zone_type``
hasDefaultToolName     ``RobotDefaults.has_tool_name``
defaultToolName        ``RobotDefaults.tool_name``
hasDefaultWobjName     ``RobotDefaults.has_wobj_name``
defaultWobjName        ``RobotDefaults.wobj_name``
defaultMoveType        ``RobotDefaults.move_type``
defaultReadConfs       ``RobotDefaults.read_confs``
====================  =========================

Cell configuration (``TRAJCENTER_CellConfig``):

=====  ======================  ===========  ================================
Ref    RAPID variable          RAPID type   Python return
=====  ======================  ===========  ================================
R12    trajTools{i}            record       ``list[str]`` names, 1-based -> toolIndex
R13    trajWobjs{i}            record       ``list[str]`` names, 1-based -> wobjIndex
=====  ======================  ===========  ================================

Process catalog (``TRAJCENTER_ProcessConfig``):

=====  ======================  ===========  ================================
Ref    RAPID variable          RAPID type   Python return
=====  ======================  ===========  ================================
R14    processTypeCount        CONST num    ``int``
R15    processTypes{i}         record       ``list[ProcessTypeEntry]``
=====  ======================  ===========  ================================

ABB constraints
---------------
- Symbol URL format for simple variables:
  ``RAPID/{task}/{module}/{var}``
- RAPID arrays are one-based.
- RAPID array braces are percent-encoded in RWS symbol URLs:
  ``trajectories{1}`` becomes ``trajectories%7B1%7D``.
- RAPID booleans are returned as ``TRUE`` or ``FALSE``.
- ``trajTools`` and ``trajWobjs`` are cell-dependent arrays whose size is
  not known in advance; their length is discovered via RWS symbol
  properties (``GET /rw/rapid/symbol/properties``) rather than hardcoded.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from abb_rws_client_python_rw6 import RWSClient
from abb_rws_client_python_rw6.highlevel.symbol import get_array_length
from abb_rws_client_python_rw6.highlevel.variables import get_variable

from trajcenter.core.logger import get_logger
from trajcenter.rws._utils import symbol, symbol_array_element

logger = get_logger(__name__)

DEFAULT_TASK: Final[str] = "T_ROB1"
WEB_MODULE: Final[str] = "TRAJCENTER_WebServices"
CELL_MODULE: Final[str] = "TRAJCENTER_CellConfig"
PROCESS_MODULE: Final[str] = "TRAJCENTER_ProcessConfig"
MAX_TRAJ: Final[int] = 256

# Shared pattern for RAPID records whose FIRST field is a quoted display
# name, e.g. trajCenterTrajMeta ["name", pointCount, processType],
# trajCenterTool ["name", tooldata], trajCenterWobj ["name", wobjdata].
# Does NOT apply to trajCenterProcessType, whose first field is a numeric
# id — see _PROCESS_TYPE_RECORD_RE.
_TRAJ_META_NAME_RE: Final[re.Pattern[str]] = re.compile(r'^\s*\[\s*"([^"]*)"')

# trajCenterProcessType record shape is [id, "name"] — id (unquoted number)
# comes BEFORE the name, unlike the name-first records above. A dedicated
# pattern is required.
_PROCESS_TYPE_RECORD_RE: Final[re.Pattern[str]] = re.compile(
    r'^\s*\[\s*(-?\d+(?:\.\d+)?)\s*,\s*"([^"]*)"'
)


@dataclass(frozen=True)
class RobotDefaults:
    """Robot-side default values used before trajectory transfer.

    ABB Route:
        ``GET /rw/rapid/symbol/data/{symbolurl}`` for each default
        variable in ``TRAJCENTER_WebServices``.

    ABB Constraints:
        Missing point columns may be completed with these defaults only
        when the corresponding ``hasDefault*`` flag is ``TRUE``. If a
        required point column is missing and the matching flag is
        ``FALSE``, the PC transfer layer must refuse the transfer.

    Attributes:
        has_tcp_speed: Whether ``defaultTcpSpeed`` is valid.
        tcp_speed: Default TCP speed in mm/s, or ``None`` when disabled.
        has_zone_type: Whether ``defaultZoneType`` is valid.
        zone_type: Default zone code, or ``None`` when disabled.
        has_tool_name: Whether ``defaultToolName`` is valid.
        tool_name: Default tool name, or ``None`` when disabled.
        has_wobj_name: Whether ``defaultWobjName`` is valid.
        wobj_name: Default workobject name, or ``None`` when disabled.
        move_type: Default movement type code.
        read_confs: Default ``readConfs`` value.

    Example:
        ::

            defaults = await read_robot_defaults(client)
            if defaults.has_tcp_speed:
                print(defaults.tcp_speed)
    """

    has_tcp_speed: bool
    tcp_speed: float | None
    has_zone_type: bool
    zone_type: int | None
    has_tool_name: bool
    tool_name: str | None
    has_wobj_name: bool
    wobj_name: str | None
    move_type: int
    read_confs: bool


@dataclass(frozen=True)
class ProcessTypeEntry:
    """One entry of the robot-side process catalog.

    ABB Route:
        N/A — parsed from a ``trajCenterProcessType`` record value read
        via ``GET /rw/rapid/symbol/data/{symbolurl}``.

    ABB Constraints:
        The record layout is ``[num id, string name]``. ``id`` is the
        numeric process type convention defined in ``TRAJCENTER_Types``
        (``0=NONE``, ``1=ACF``, ``2=AAK``, ``3=PUSHCORP``,
        ``4..255=RESERVED``). ``id`` must not be assumed to equal the
        array position minus one: the catalog may be extended arbitrarily
        by the robot programmer.

    Attributes:
        id: Numeric process type identifier.
        name: Human-readable process name.

    Example:
        ::

            entry = ProcessTypeEntry(id=1, name="ACF")
    """

    id: int
    name: str


def _parse_bool(raw: str, *, name: str) -> bool:
    """Parse a RAPID bool returned by RWS.

    ABB Route:
        N/A — local parsing helper.

    ABB Constraints:
        RAPID bool values are expected to be returned as ``TRUE`` or
        ``FALSE`` by RobotWare.

    Args:
        raw: Raw RWS value.
        name: Variable name used in error messages.

    Returns:
        Parsed boolean.

    Raises:
        ValueError: If *raw* is not ``TRUE`` or ``FALSE``.

    Example:
        ::

            assert _parse_bool("TRUE", name="trajReady") is True
    """
    normalized = raw.strip().upper()
    if normalized == "TRUE":
        return True
    if normalized == "FALSE":
        return False
    raise ValueError(f"Unexpected {name} value {raw!r}: expected 'TRUE' or 'FALSE'")


def _parse_int(raw: str, *, name: str) -> int:
    """Parse a RAPID num as an integer.

    ABB Route:
        N/A — local parsing helper.

    ABB Constraints:
        RAPID ``num`` may be returned as ``"3"`` or ``"3.0"``.

    Args:
        raw: Raw RWS value.
        name: Variable name used in error messages.

    Returns:
        Parsed integer.

    Raises:
        ValueError: If *raw* cannot be converted to an integer.

    Example:
        ::

            assert _parse_int("3.0", name="selectedTrajIndex") == 3
    """
    try:
        return int(float(raw))
    except ValueError as exc:
        raise ValueError(f"Cannot parse {name} value {raw!r} as int") from exc


def _parse_float(raw: str, *, name: str) -> float:
    """Parse a RAPID num as a float.

    ABB Route:
        N/A — local parsing helper.

    ABB Constraints:
        RAPID ``num`` values are decimal strings.

    Args:
        raw: Raw RWS value.
        name: Variable name used in error messages.

    Returns:
        Parsed float.

    Raises:
        ValueError: If *raw* cannot be converted to a float.

    Example:
        ::

            assert _parse_float("500", name="defaultTcpSpeed") == 500.0
    """
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"Cannot parse {name} value {raw!r} as float") from exc


def _parse_rapid_string(raw: str) -> str:
    """Parse a RAPID string literal returned by RWS.

    ABB Route:
        N/A — local parsing helper.

    ABB Constraints:
        RAPID strings are commonly returned with surrounding double
        quotes. If quotes are absent, the stripped value is returned.

    Args:
        raw: Raw RWS string value.

    Returns:
        Unquoted string value.

    Example:
        ::

            assert _parse_rapid_string('"Tool_A"') == "Tool_A"
    """
    stripped = raw.strip()
    if len(stripped) >= 2 and stripped[0] == '"' and stripped[-1] == '"':
        return stripped[1:-1]
    return stripped


def _parse_traj_meta_name(raw: str) -> str:
    """Extract the trajectory name from a ``trajCenterTrajMeta`` record.

    ABB Route:
        N/A — local parsing helper.

    ABB Constraints:
        The expected RAPID record literal is ``["name", pointCount,
        processType]``. Only the first string field is extracted.

    Args:
        raw: Raw RWS record value, e.g. ``'["Traj1",320,0]'``.

    Returns:
        Trajectory name.

    Raises:
        ValueError: If no leading string field can be extracted.

    Example:
        ::

            assert _parse_traj_meta_name('["Traj1",320,0]') == "Traj1"
    """
    match = _TRAJ_META_NAME_RE.search(raw)
    if match:
        return match.group(1)
    raise ValueError(f"Cannot parse trajectory metadata record name from {raw!r}")


def _parse_leading_string_field(raw: str, *, name: str) -> str:
    """Extract the leading string field of a name-first RAPID record.

    ABB Route:
        N/A — local parsing helper.

    ABB Constraints:
        Applies to ``trajCenterTool`` and ``trajCenterWobj`` records,
        whose first field is the display name, e.g. ``["Tool_A", ...]``.
        Does not apply to ``trajCenterProcessType``, whose first field is
        a numeric id — use ``_parse_process_type_record`` for that record.

    Args:
        raw: Raw RWS record value, e.g. ``'["Tool_A",[TRUE,...]]'``.
        name: Variable name used in error messages.

    Returns:
        The extracted display name.

    Raises:
        ValueError: If no leading string field can be extracted.

    Example:
        ::

            assert _parse_leading_string_field(
                '["Tool_A",[TRUE]]', name="trajTools"
            ) == "Tool_A"
    """
    match = _TRAJ_META_NAME_RE.search(raw)
    if match:
        return match.group(1)
    raise ValueError(f"Cannot parse leading string field of {name} from {raw!r}")


def _parse_process_type_record(raw: str) -> ProcessTypeEntry:
    """Parse a ``trajCenterProcessType`` record value.

    ABB Route:
        N/A — local parsing helper.

    ABB Constraints:
        The expected RAPID record literal is ``[id, "name"]``, e.g.
        ``[1,"ACF"]``. ``id`` precedes ``name`` in this record, unlike
        other TrajCenter records.

    Args:
        raw: Raw RWS record value, e.g. ``'[1,"ACF"]'``.

    Returns:
        Parsed process type entry.

    Raises:
        ValueError: If the record cannot be parsed.

    Example:
        ::

            assert _parse_process_type_record('[1,"ACF"]') == ProcessTypeEntry(
                id=1, name="ACF"
            )
    """
    match = _PROCESS_TYPE_RECORD_RE.search(raw)
    if not match:
        raise ValueError(f"Cannot parse trajCenterProcessType record from {raw!r}")
    return ProcessTypeEntry(id=int(float(match.group(1))), name=match.group(2))


async def _read_raw(
    client: RWSClient,
    *,
    task: str,
    module: str,
    variable: str,
) -> str:
    """Read a simple RAPID variable and return its raw value.

    ABB Route:
        ``GET /rw/rapid/symbol/data/{symbolurl}``.

    ABB Constraints:
        No mastership is required for reads.

    Args:
        client: Open RWS client.
        task: RAPID task name.
        module: RAPID module name.
        variable: Simple RAPID variable name.

    Returns:
        Raw RAPID value as returned by RWS.

    Raises:
        RWSHTTPError: On any unexpected HTTP error from the controller.
        ValueError: If the RWS response cannot be parsed by the client
            library.

    Example:
        ::

            raw = await _read_raw(
                client,
                task="T_ROB1",
                module="TRAJCENTER_WebServices",
                variable="trajReady",
            )
    """
    symbolurl = symbol(task, module, variable)
    raw = await get_variable(client, symbolurl=symbolurl)
    logger.debug("%s = %r", variable, raw)
    return raw


async def read_selected_traj_index(
    client: RWSClient,
    *,
    task: str = DEFAULT_TASK,
    module: str = WEB_MODULE,
) -> int:
    """Read the trajectory index currently selected by RAPID.

    ABB Route:
        ``GET /rw/rapid/symbol/data/RAPID/{task}/{module}/selectedTrajIndex``.

    ABB Constraints:
        ``selectedTrajIndex`` is a RAPID ``num``. ``0`` means no
        selected trajectory. Positive values are one-based indexes in
        ``trajectories``.

    Args:
        client: Open RWS client.
        task: RAPID task name.
        module: RAPID module name. Defaults to
            ``TRAJCENTER_WebServices``.

    Returns:
        Selected trajectory index as an integer.

    Raises:
        RWSHTTPError: On controller HTTP errors.
        ValueError: If the raw value cannot be parsed as int.

    Example:
        ::

            idx = await read_selected_traj_index(client)
    """
    raw = await _read_raw(
        client, task=task, module=module, variable="selectedTrajIndex"
    )
    return _parse_int(raw, name="selectedTrajIndex")


async def read_send_traj_request(
    client: RWSClient,
    *,
    task: str = DEFAULT_TASK,
    module: str = WEB_MODULE,
) -> bool:
    """Read the ``sendTrajRequest`` flag.

    ABB Route:
        ``GET /rw/rapid/symbol/data/RAPID/{task}/{module}/sendTrajRequest``.

    ABB Constraints:
        ``TRUE`` events request a trajectory transfer. ``FALSE`` events
        must be ignored by the PC service loop.

    Args:
        client: Open RWS client.
        task: RAPID task name.
        module: RAPID module name.

    Returns:
        Parsed request flag.

    Raises:
        RWSHTTPError: On controller HTTP errors.
        ValueError: If the raw value is not a RAPID bool.

    Example:
        ::

            if await read_send_traj_request(client):
                ...
    """
    raw = await _read_raw(client, task=task, module=module, variable="sendTrajRequest")
    return _parse_bool(raw, name="sendTrajRequest")


async def read_refresh_meta_request(
    client: RWSClient,
    *,
    task: str = DEFAULT_TASK,
    module: str = WEB_MODULE,
) -> bool:
    """Read the ``refreshMetaRequest`` flag.

    ABB Route:
        ``GET /rw/rapid/symbol/data/RAPID/{task}/{module}/refreshMetaRequest``.

    ABB Constraints:
        ``TRUE`` events request a PC store metadata refresh.

    Args:
        client: Open RWS client.
        task: RAPID task name.
        module: RAPID module name.

    Returns:
        Parsed request flag.

    Raises:
        RWSHTTPError: On controller HTTP errors.
        ValueError: If the raw value is not a RAPID bool.

    Example:
        ::

            refresh = await read_refresh_meta_request(client)
    """
    raw = await _read_raw(
        client,
        task=task,
        module=module,
        variable="refreshMetaRequest",
    )
    return _parse_bool(raw, name="refreshMetaRequest")


async def read_traj_ready(
    client: RWSClient,
    *,
    task: str = DEFAULT_TASK,
    module: str = WEB_MODULE,
) -> bool:
    """Read the ``trajReady`` flag.

    ABB Route:
        ``GET /rw/rapid/symbol/data/RAPID/{task}/{module}/trajReady``.

    ABB Constraints:
        ``trajReady`` becomes ``TRUE`` only after a full trajectory
        transfer is complete.

    Args:
        client: Open RWS client.
        task: RAPID task name.
        module: RAPID module name.

    Returns:
        Parsed ``trajReady`` flag.

    Raises:
        RWSHTTPError: On controller HTTP errors.
        ValueError: If the raw value is not a RAPID bool.

    Example:
        ::

            ready = await read_traj_ready(client)
    """
    raw = await _read_raw(client, task=task, module=module, variable="trajReady")
    return _parse_bool(raw, name="trajReady")


async def read_transfer_error(
    client: RWSClient,
    *,
    task: str = DEFAULT_TASK,
    module: str = WEB_MODULE,
) -> bool:
    """Read the ``transferError`` flag.

    ABB Route:
        ``GET /rw/rapid/symbol/data/RAPID/{task}/{module}/transferError``.

    ABB Constraints:
        ``TRUE`` indicates that the latest refresh or trajectory
        transfer failed.

    Args:
        client: Open RWS client.
        task: RAPID task name.
        module: RAPID module name.

    Returns:
        Parsed error flag.

    Raises:
        RWSHTTPError: On controller HTTP errors.
        ValueError: If the raw value is not a RAPID bool.

    Example:
        ::

            has_error = await read_transfer_error(client)
    """
    raw = await _read_raw(client, task=task, module=module, variable="transferError")
    return _parse_bool(raw, name="transferError")


async def read_last_error_code(
    client: RWSClient,
    *,
    task: str = DEFAULT_TASK,
    module: str = WEB_MODULE,
) -> int:
    """Read ``lastErrorCode``.

    ABB Route:
        ``GET /rw/rapid/symbol/data/RAPID/{task}/{module}/lastErrorCode``.

    ABB Constraints:
        Status code convention is defined in ``TRAJCENTER_Types``.

    Args:
        client: Open RWS client.
        task: RAPID task name.
        module: RAPID module name.

    Returns:
        Last status/error code as integer.

    Raises:
        RWSHTTPError: On controller HTTP errors.
        ValueError: If the raw value cannot be parsed as int.

    Example:
        ::

            code = await read_last_error_code(client)
    """
    raw = await _read_raw(client, task=task, module=module, variable="lastErrorCode")
    return _parse_int(raw, name="lastErrorCode")


async def read_last_error(
    client: RWSClient,
    *,
    task: str = DEFAULT_TASK,
    module: str = WEB_MODULE,
) -> str:
    """Read ``lastError``.

    ABB Route:
        ``GET /rw/rapid/symbol/data/RAPID/{task}/{module}/lastError``.

    ABB Constraints:
        RAPID string quotes are stripped.

    Args:
        client: Open RWS client.
        task: RAPID task name.
        module: RAPID module name.

    Returns:
        Last human-readable error message.

    Raises:
        RWSHTTPError: On controller HTTP errors.

    Example:
        ::

            message = await read_last_error(client)
    """
    raw = await _read_raw(client, task=task, module=module, variable="lastError")
    return _parse_rapid_string(raw)


async def read_transfer_progress(
    client: RWSClient,
    *,
    task: str = DEFAULT_TASK,
    module: str = WEB_MODULE,
) -> int:
    """Read ``transferProgress``.

    ABB Route:
        ``GET /rw/rapid/symbol/data/RAPID/{task}/{module}/transferProgress``.

    ABB Constraints:
        Progress convention is ``0`` to ``100``.

    Args:
        client: Open RWS client.
        task: RAPID task name.
        module: RAPID module name.

    Returns:
        Transfer progress percentage as integer.

    Raises:
        RWSHTTPError: On controller HTTP errors.
        ValueError: If the raw value cannot be parsed as int.

    Example:
        ::

            progress = await read_transfer_progress(client)
    """
    raw = await _read_raw(client, task=task, module=module, variable="transferProgress")
    return _parse_int(raw, name="transferProgress")


async def read_nb_robtargets(
    client: RWSClient,
    *,
    task: str = DEFAULT_TASK,
    module: str = WEB_MODULE,
) -> int:
    """Read the number of loaded trajectory points.

    ABB Route:
        ``GET /rw/rapid/symbol/data/RAPID/{task}/{module}/nbLoadedTrajPoints``.

    ABB Constraints:
        ``nbLoadedTrajPoints`` is the valid entry count for
        ``trajData``.

    Args:
        client: Open RWS client.
        task: RAPID task name.
        module: RAPID module name.

    Returns:
        Number of loaded trajectory points.

    Raises:
        RWSHTTPError: On controller HTTP errors.
        ValueError: If the raw value cannot be parsed as int.

    Example:
        ::

            n = await read_nb_robtargets(client)
    """
    raw = await _read_raw(
        client,
        task=task,
        module=module,
        variable="nbLoadedTrajPoints",
    )
    return _parse_int(raw, name="nbLoadedTrajPoints")


async def read_nb_traj_dispo(
    client: RWSClient,
    *,
    task: str = DEFAULT_TASK,
    module: str = WEB_MODULE,
) -> int:
    """Read the number of trajectories available in PC metadata.

    ABB Route:
        ``GET /rw/rapid/symbol/data/RAPID/{task}/{module}/nbTrajAvailable``.

    ABB Constraints:
        Valid range is ``0..256``. Valid metadata entries are
        ``trajectories{1..nbTrajAvailable}``.

    Args:
        client: Open RWS client.
        task: RAPID task name.
        module: RAPID module name.

    Returns:
        Number of available trajectories.

    Raises:
        RWSHTTPError: On controller HTTP errors.
        ValueError: If the raw value cannot be parsed as int.

    Example:
        ::

            n = await read_nb_traj_dispo(client)
    """
    raw = await _read_raw(client, task=task, module=module, variable="nbTrajAvailable")
    return _parse_int(raw, name="nbTrajAvailable")


async def read_traj_names(
    client: RWSClient,
    *,
    task: str = DEFAULT_TASK,
    module: str = WEB_MODULE,
    count: int | None = None,
) -> list[str]:
    """Read trajectory display names from ``trajectories`` metadata.

    ABB Route:
        ``GET /rw/rapid/symbol/data/RAPID/{task}/{module}/trajectories%7Bi%7D``.

    ABB Constraints:
        ``trajectories`` is a one-based RAPID array of
        ``trajCenterTrajMeta`` records. This reader expects each record
        value to be returned as ``["name", pointCount, processType]``
        and extracts the first string field.

    Args:
        client: Open RWS client.
        task: RAPID task name.
        module: RAPID module name.
        count: Number of names to read. If ``None``,
            ``nbTrajAvailable`` is read first.

    Returns:
        Ordered list of trajectory names.

    Raises:
        RWSHTTPError: On controller HTTP errors.
        ValueError: If ``count`` exceeds ``MAX_TRAJ`` or if a metadata
            record cannot be parsed.

    Example:
        ::

            names = await read_traj_names(client, count=3)
    """
    if count is None:
        count = await read_nb_traj_dispo(client, task=task, module=module)

    if count > MAX_TRAJ:
        raise ValueError(f"Requested {count} names but MAX_TRAJ={MAX_TRAJ}")

    if count == 0:
        return []

    names: list[str] = []
    for index in range(1, count + 1):
        symbolurl = symbol_array_element(
            task=task,
            module=module,
            variable="trajectories",
            index=index,
        )
        raw = await get_variable(client, symbolurl=symbolurl)
        names.append(_parse_traj_meta_name(raw))

    logger.debug("Read %d trajectory names from controller", len(names))
    return names


async def read_robot_defaults(
    client: RWSClient,
    *,
    task: str = DEFAULT_TASK,
    module: str = WEB_MODULE,
) -> RobotDefaults:
    """Read robot-side default values for trajectory transfer.

    ABB Route:
        Multiple ``GET /rw/rapid/symbol/data/{symbolurl}`` calls in
        ``TRAJCENTER_WebServices``.

    ABB Constraints:
        The writer may use defaults only when the corresponding
        ``hasDefault*`` flag is ``TRUE``. ``defaultMoveType`` and
        ``defaultReadConfs`` are always read.

    Args:
        client: Open RWS client.
        task: RAPID task name.
        module: RAPID module name.

    Returns:
        Robot defaults dataclass.

    Raises:
        RWSHTTPError: On controller HTTP errors.
        ValueError: If any raw value cannot be parsed.

    Example:
        ::

            defaults = await read_robot_defaults(client)
    """
    has_tcp_speed = _parse_bool(
        await _read_raw(
            client, task=task, module=module, variable="hasDefaultTcpSpeed"
        ),
        name="hasDefaultTcpSpeed",
    )
    tcp_speed_raw = await _read_raw(
        client,
        task=task,
        module=module,
        variable="defaultTcpSpeed",
    )

    has_zone_type = _parse_bool(
        await _read_raw(
            client, task=task, module=module, variable="hasDefaultZoneType"
        ),
        name="hasDefaultZoneType",
    )
    zone_type_raw = await _read_raw(
        client,
        task=task,
        module=module,
        variable="defaultZoneType",
    )

    has_tool_name = _parse_bool(
        await _read_raw(
            client, task=task, module=module, variable="hasDefaultToolName"
        ),
        name="hasDefaultToolName",
    )
    tool_name_raw = await _read_raw(
        client,
        task=task,
        module=module,
        variable="defaultToolName",
    )

    has_wobj_name = _parse_bool(
        await _read_raw(
            client, task=task, module=module, variable="hasDefaultWobjName"
        ),
        name="hasDefaultWobjName",
    )
    wobj_name_raw = await _read_raw(
        client,
        task=task,
        module=module,
        variable="defaultWobjName",
    )

    move_type = _parse_int(
        await _read_raw(client, task=task, module=module, variable="defaultMoveType"),
        name="defaultMoveType",
    )
    read_confs = _parse_bool(
        await _read_raw(client, task=task, module=module, variable="defaultReadConfs"),
        name="defaultReadConfs",
    )

    return RobotDefaults(
        has_tcp_speed=has_tcp_speed,
        tcp_speed=(
            _parse_float(tcp_speed_raw, name="defaultTcpSpeed")
            if has_tcp_speed
            else None
        ),
        has_zone_type=has_zone_type,
        zone_type=(
            _parse_int(zone_type_raw, name="defaultZoneType") if has_zone_type else None
        ),
        has_tool_name=has_tool_name,
        tool_name=_parse_rapid_string(tool_name_raw) if has_tool_name else None,
        has_wobj_name=has_wobj_name,
        wobj_name=_parse_rapid_string(wobj_name_raw) if has_wobj_name else None,
        move_type=move_type,
        read_confs=read_confs,
    )


# ---------------------------------------------------------------------------
# RWS-4 — Cell configuration (TRAJCENTER_CellConfig)
# ---------------------------------------------------------------------------


async def read_traj_tools_count(
    client: RWSClient,
    *,
    task: str = DEFAULT_TASK,
    module: str = CELL_MODULE,
) -> int:
    """Read the declared size of the ``trajTools`` array.

    ABB Route:
        ``GET /rw/rapid/symbol/properties/RAPID/{task}/{module}/trajTools``.

    ABB Constraints:
        ``trajTools`` is cell-dependent; its size is not known in advance
        and must be discovered via RWS symbol properties (``ndim``/``dim``).

    Args:
        client: Open RWS client.
        task: RAPID task name.
        module: RAPID module name. Defaults to ``TRAJCENTER_CellConfig``.

    Returns:
        Number of declared entries in ``trajTools``.

    Raises:
        RWSHTTPError: On controller HTTP errors.
        ValueError: If ``trajTools`` is not declared as an array.

    Example:
        ::

            n = await read_traj_tools_count(client)
    """
    return await get_array_length(client, symbolurl=symbol(task, module, "trajTools"))


async def read_traj_wobjs_count(
    client: RWSClient,
    *,
    task: str = DEFAULT_TASK,
    module: str = CELL_MODULE,
) -> int:
    """Read the declared size of the ``trajWobjs`` array.

    ABB Route:
        ``GET /rw/rapid/symbol/properties/RAPID/{task}/{module}/trajWobjs``.

    ABB Constraints:
        ``trajWobjs`` is cell-dependent; its size is not known in advance
        and must be discovered via RWS symbol properties (``ndim``/``dim``).

    Args:
        client: Open RWS client.
        task: RAPID task name.
        module: RAPID module name. Defaults to ``TRAJCENTER_CellConfig``.

    Returns:
        Number of declared entries in ``trajWobjs``.

    Raises:
        RWSHTTPError: On controller HTTP errors.
        ValueError: If ``trajWobjs`` is not declared as an array.

    Example:
        ::

            n = await read_traj_wobjs_count(client)
    """
    return await get_array_length(client, symbolurl=symbol(task, module, "trajWobjs"))


async def read_traj_tool_names(
    client: RWSClient,
    *,
    task: str = DEFAULT_TASK,
    module: str = CELL_MODULE,
    count: int | None = None,
) -> list[str]:
    """Read tool display names from the ``trajTools`` cell configuration.

    ABB Route:
        ``GET /rw/rapid/symbol/data/RAPID/{task}/{module}/trajTools%7Bi%7D``.

    ABB Constraints:
        ``trajTools`` is a one-based RAPID array of ``trajCenterTool``
        records. Position ``i`` maps to ``toolIndex = i`` in
        ``trajCenterPointData``.

    Args:
        client: Open RWS client.
        task: RAPID task name.
        module: RAPID module name. Defaults to ``TRAJCENTER_CellConfig``.
        count: Number of entries to read. If ``None``,
            ``read_traj_tools_count`` is called first.

    Returns:
        Ordered list of tool names, index ``i-1`` corresponds to
        ``toolIndex = i``.

    Raises:
        RWSHTTPError: On controller HTTP errors.
        ValueError: If a record cannot be parsed.

    Example:
        ::

            names = await read_traj_tool_names(client)
    """
    if count is None:
        count = await read_traj_tools_count(client, task=task, module=module)

    names: list[str] = []
    for index in range(1, count + 1):
        symbolurl = symbol_array_element(
            task=task, module=module, variable="trajTools", index=index
        )
        raw = await get_variable(client, symbolurl=symbolurl)
        names.append(_parse_leading_string_field(raw, name="trajTools"))

    logger.debug("Read %d tool names from controller", len(names))
    return names


async def read_traj_wobj_names(
    client: RWSClient,
    *,
    task: str = DEFAULT_TASK,
    module: str = CELL_MODULE,
    count: int | None = None,
) -> list[str]:
    """Read workobject display names from ``trajWobjs`` cell configuration.

    ABB Route:
        ``GET /rw/rapid/symbol/data/RAPID/{task}/{module}/trajWobjs%7Bi%7D``.

    ABB Constraints:
        ``trajWobjs`` is a one-based RAPID array of ``trajCenterWobj``
        records. Position ``i`` maps to ``wobjIndex = i`` in
        ``trajCenterPointData``.

    Args:
        client: Open RWS client.
        task: RAPID task name.
        module: RAPID module name. Defaults to ``TRAJCENTER_CellConfig``.
        count: Number of entries to read. If ``None``,
            ``read_traj_wobjs_count`` is called first.

    Returns:
        Ordered list of workobject names, index ``i-1`` corresponds to
        ``wobjIndex = i``.

    Raises:
        RWSHTTPError: On controller HTTP errors.
        ValueError: If a record cannot be parsed.

    Example:
        ::

            names = await read_traj_wobj_names(client)
    """
    if count is None:
        count = await read_traj_wobjs_count(client, task=task, module=module)

    names: list[str] = []
    for index in range(1, count + 1):
        symbolurl = symbol_array_element(
            task=task, module=module, variable="trajWobjs", index=index
        )
        raw = await get_variable(client, symbolurl=symbolurl)
        names.append(_parse_leading_string_field(raw, name="trajWobjs"))

    logger.debug("Read %d workobject names from controller", len(names))
    return names


# ---------------------------------------------------------------------------
# RWS-4 — Process catalog (TRAJCENTER_ProcessConfig)
# ---------------------------------------------------------------------------


async def read_process_type_count(
    client: RWSClient,
    *,
    task: str = DEFAULT_TASK,
    module: str = PROCESS_MODULE,
) -> int:
    """Read ``processTypeCount`` from the robot process catalog.

    ABB Route:
        ``GET /rw/rapid/symbol/data/RAPID/{task}/{module}/processTypeCount``.

    ABB Constraints:
        ``processTypeCount`` is a RAPID ``CONST num``. The RWS symbol data
        endpoint is expected to serve ``CONST`` symbols identically to
        ``VAR``/``PERS`` (both are plain data symbols per ABB's symbol type
        model, ``symtyp`` including ``"con"``). Not yet confirmed on real
        hardware — verify during the next controller test session.

    Args:
        client: Open RWS client.
        task: RAPID task name.
        module: RAPID module name. Defaults to ``TRAJCENTER_ProcessConfig``.

    Returns:
        Number of declared entries in ``processTypes``.

    Raises:
        RWSHTTPError: On controller HTTP errors.
        ValueError: If the raw value cannot be parsed as int.

    Example:
        ::

            n = await read_process_type_count(client)
    """
    raw = await _read_raw(client, task=task, module=module, variable="processTypeCount")
    return _parse_int(raw, name="processTypeCount")


async def read_process_types(
    client: RWSClient,
    *,
    task: str = DEFAULT_TASK,
    module: str = PROCESS_MODULE,
    count: int | None = None,
) -> list[ProcessTypeEntry]:
    """Read the robot-side process catalog from ``processTypes``.

    ABB Route:
        ``GET /rw/rapid/symbol/data/RAPID/{task}/{module}/processTypes%7Bi%7D``.

    ABB Constraints:
        ``processTypes`` is a one-based RAPID array of
        ``trajCenterProcessType`` records, ``[id, name]``. ``id`` is the
        authoritative numeric process type; it must not be assumed to
        equal the array position.

    Args:
        client: Open RWS client.
        task: RAPID task name.
        module: RAPID module name. Defaults to ``TRAJCENTER_ProcessConfig``.
        count: Number of entries to read. If ``None``,
            ``read_process_type_count`` is called first.

    Returns:
        Ordered list of process catalog entries, as declared on the robot.

    Raises:
        RWSHTTPError: On controller HTTP errors.
        ValueError: If a record cannot be parsed.

    Example:
        ::

            catalog = await read_process_types(client)
    """
    if count is None:
        count = await read_process_type_count(client, task=task, module=module)

    entries: list[ProcessTypeEntry] = []
    for index in range(1, count + 1):
        symbolurl = symbol_array_element(
            task=task, module=module, variable="processTypes", index=index
        )
        raw = await get_variable(client, symbolurl=symbolurl)
        entries.append(_parse_process_type_record(raw))

    logger.debug("Read %d process type entries from controller", len(entries))
    return entries
