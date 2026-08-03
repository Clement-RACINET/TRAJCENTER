#!/usr/bin/env python3
# trajcenter/rws/reader.py
"""RWS reader — reads TrajCenter v2 RAPID variables from the ABB controller.

Author: Clement RACINET

This module is the TrajCenter read access layer for the
``TRAJCENTER_WebServices``, ``TRAJCENTER_CellConfig`` and
``TRAJCENTER_ProcessConfig`` RAPID modules.

All simple-variable reads use ``GET /rw/rapid/symbol/data/{symbolurl}`` via
``get_variable`` from ``abb_rws_client_python_rw6.highlevel.variables``.
Array-length discovery uses ``GET /rw/rapid/symbol/properties/{symbolurl}``
via ``get_array_length`` from ``abb_rws_client_python_rw6.highlevel.symbol``.

ABB Route:
    - ``GET /rw/rapid/symbol/data/{symbolurl}``
    - ``GET /rw/rapid/symbol/properties/{symbolurl}``

ABB Constraints:
    - RAPID arrays are one-based.
    - RAPID array braces are percent-encoded in RWS symbol URLs.
    - RAPID bool values are returned as ``TRUE`` or ``FALSE``.
    - No Mastership is required for reads.
    - ``trajTools`` and ``trajWobjs`` sizes are cell-dependent and discovered
      through symbol properties.

Example:
    ```python
    defaults = await read_robot_defaults(client)
    tools = await read_traj_tool_names(client)
    wobjs = await read_traj_wobj_names(client)
    process_types = await read_process_types(client)
    ```
"""

from __future__ import annotations

import re
from typing import Final

from abb_rws_client_python_rw6 import RWSClient
from abb_rws_client_python_rw6.highlevel.symbol import get_array_length
from abb_rws_client_python_rw6.highlevel.variables import get_variable

from trajcenter.core.logger import get_logger
from trajcenter.rws._utils import symbol, symbol_array_element
from trajcenter.rws.constants import (
    CELL_MODULE,
    DEFAULT_TASK,
    MAX_TRAJ,
    PROCESS_MODULE,
    WEB_MODULE,
)
from trajcenter.rws.models import ProcessTypeEntry, RobotContext, RobotDefaults

logger = get_logger(__name__)

_TRAJ_META_NAME_RE: Final[re.Pattern[str]] = re.compile(r'^\s*\[\s*"([^"]*)"')
_PROCESS_TYPE_RECORD_RE: Final[re.Pattern[str]] = re.compile(
    r'^\s*\[\s*(-?\d+(?:\.\d+)?)\s*,\s*"([^"]*)"'
)


def _parse_bool(raw: str, *, name: str) -> bool:
    """Parse a RAPID bool returned by RWS.

    ABB Route:
        N/A — local parsing helper.

    ABB Constraints:
        RAPID bool values are expected as ``TRUE`` or ``FALSE``.

    Args:
        raw: Raw RWS value.
        name: Variable name used in error messages.

    Returns:
        Parsed boolean.

    Raises:
        ValueError: If the value is not a valid RAPID boolean.

    Example:
        ```python
        assert _parse_bool("TRUE", name="flag") is True
        ```
    """
    normalized = raw.strip().upper()
    if normalized == "TRUE":
        return True
    if normalized == "FALSE":
        return False
    raise ValueError(f"Unexpected {name} value {raw!r}: expected 'TRUE' or 'FALSE'")


def _parse_int(raw: str, *, name: str) -> int:
    """Parse a RAPID ``num`` as an integer.

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
        ValueError: If the value cannot be converted to an integer.

    Example:
        ```python
        assert _parse_int("3.0", name="selectedTrajIndex") == 3
        ```
    """
    try:
        return int(float(raw))
    except ValueError as exc:
        raise ValueError(f"Cannot parse {name} value {raw!r} as int") from exc


def _parse_float(raw: str, *, name: str) -> float:
    """Parse a RAPID ``num`` as a float.

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
        ValueError: If the value cannot be converted to float.

    Example:
        ```python
        assert _parse_float("500", name="defaultTcpSpeed") == 500.0
        ```
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
        RAPID strings are commonly returned with surrounding double quotes.

    Args:
        raw: Raw RWS string value.

    Returns:
        Unquoted string value.

    Raises:
        None.

    Example:
        ```python
        assert _parse_rapid_string('"Tool_A"') == "Tool_A"
        ```
    """
    stripped = raw.strip()
    if len(stripped) >= 2 and stripped[0] == '"' and stripped[-1] == '"':
        return stripped[1:-1]
    return stripped


def _parse_traj_meta_name(raw: str) -> str:
    """Extract a trajectory name from a ``trajCenterTrajMeta`` record.

    ABB Route:
        N/A — local parsing helper.

    ABB Constraints:
        Expected record layout is ``["name", pointCount, processType]``.

    Args:
        raw: Raw RWS record value.

    Returns:
        Trajectory display name.

    Raises:
        ValueError: If the name cannot be parsed.

    Example:
        ```python
        assert _parse_traj_meta_name('["Traj1",320,0]') == "Traj1"
        ```
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
        Applies to ``trajCenterTool`` and ``trajCenterWobj`` records.

    Args:
        raw: Raw RWS record value.
        name: Variable name used in error messages.

    Returns:
        Extracted display name.

    Raises:
        ValueError: If the leading string cannot be parsed.

    Example:
        ```python
        assert _parse_leading_string_field('["Tool_A",[TRUE]]', name="tool") == "Tool_A"
        ```
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
        Expected RAPID record layout is ``[num id, string name]``.

    Args:
        raw: Raw RWS record value.

    Returns:
        Parsed process type entry.

    Raises:
        ValueError: If the record cannot be parsed.

    Example:
        ```python
        entry = _parse_process_type_record('[1,"ACF"]')
        assert entry == ProcessTypeEntry(id=1, name="ACF")
        ```
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
        No Mastership is required for reads.

    Args:
        client: Open RWS client.
        task: RAPID task name.
        module: RAPID module name.
        variable: Simple RAPID variable name.

    Returns:
        Raw RAPID value returned by RWS.

    Raises:
        RWSHTTPError: On controller HTTP errors.
        ValueError: If the response cannot be parsed by the client library.

    Example:
        ```python
        raw = await _read_raw(
            client,
            task="T_ROB1",
            module="TRAJCENTER_WebServices",
            variable="trajReady",
        )
        ```
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
    """Read ``selectedTrajIndex``.

    ABB Route:
        ``GET /rw/rapid/symbol/data/RAPID/{task}/{module}/selectedTrajIndex``.

    ABB Constraints:
        ``0`` means no selected trajectory. Positive values are one-based.

    Args:
        client: Open RWS client.
        task: RAPID task name.
        module: RAPID module name.

    Returns:
        Selected trajectory index.

    Raises:
        RWSHTTPError: On controller HTTP errors.
        ValueError: If the value cannot be parsed as integer.

    Example:
        ```python
        index = await read_selected_traj_index(client)
        ```
    """
    raw = await _read_raw(
        client,
        task=task,
        module=module,
        variable="selectedTrajIndex",
    )
    return _parse_int(raw, name="selectedTrajIndex")


async def read_send_traj_request(
    client: RWSClient,
    *,
    task: str = DEFAULT_TASK,
    module: str = WEB_MODULE,
) -> bool:
    """Read ``sendTrajRequest``.

    ABB Route:
        ``GET /rw/rapid/symbol/data/RAPID/{task}/{module}/sendTrajRequest``.

    ABB Constraints:
        Only ``TRUE`` events trigger a trajectory transfer.

    Args:
        client: Open RWS client.
        task: RAPID task name.
        module: RAPID module name.

    Returns:
        Request flag.

    Raises:
        RWSHTTPError: On controller HTTP errors.
        ValueError: If the value is not a RAPID bool.

    Example:
        ```python
        should_send = await read_send_traj_request(client)
        ```
    """
    raw = await _read_raw(client, task=task, module=module, variable="sendTrajRequest")
    return _parse_bool(raw, name="sendTrajRequest")


async def read_refresh_meta_request(
    client: RWSClient,
    *,
    task: str = DEFAULT_TASK,
    module: str = WEB_MODULE,
) -> bool:
    """Read ``refreshMetaRequest``.

    ABB Route:
        ``GET /rw/rapid/symbol/data/RAPID/{task}/{module}/refreshMetaRequest``.

    ABB Constraints:
        Only ``TRUE`` events trigger metadata refresh.

    Args:
        client: Open RWS client.
        task: RAPID task name.
        module: RAPID module name.

    Returns:
        Request flag.

    Raises:
        RWSHTTPError: On controller HTTP errors.
        ValueError: If the value is not a RAPID bool.

    Example:
        ```python
        refresh = await read_refresh_meta_request(client)
        ```
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
    """Read ``trajReady``.

    ABB Route:
        ``GET /rw/rapid/symbol/data/RAPID/{task}/{module}/trajReady``.

    ABB Constraints:
        ``trajReady`` is ``TRUE`` only after a complete transfer.

    Args:
        client: Open RWS client.
        task: RAPID task name.
        module: RAPID module name.

    Returns:
        Parsed flag.

    Raises:
        RWSHTTPError: On controller HTTP errors.
        ValueError: If the value is not a RAPID bool.

    Example:
        ```python
        ready = await read_traj_ready(client)
        ```
    """
    raw = await _read_raw(client, task=task, module=module, variable="trajReady")
    return _parse_bool(raw, name="trajReady")


async def read_transfer_error(
    client: RWSClient,
    *,
    task: str = DEFAULT_TASK,
    module: str = WEB_MODULE,
) -> bool:
    """Read ``transferError``.

    ABB Route:
        ``GET /rw/rapid/symbol/data/RAPID/{task}/{module}/transferError``.

    ABB Constraints:
        ``TRUE`` means the latest refresh or transfer failed.

    Args:
        client: Open RWS client.
        task: RAPID task name.
        module: RAPID module name.

    Returns:
        Parsed flag.

    Raises:
        RWSHTTPError: On controller HTTP errors.
        ValueError: If the value is not a RAPID bool.

    Example:
        ```python
        has_error = await read_transfer_error(client)
        ```
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
        Status and error codes follow the TrajCenter protocol.

    Args:
        client: Open RWS client.
        task: RAPID task name.
        module: RAPID module name.

    Returns:
        Status or error code.

    Raises:
        RWSHTTPError: On controller HTTP errors.
        ValueError: If the value cannot be parsed as integer.

    Example:
        ```python
        code = await read_last_error_code(client)
        ```
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
        Human-readable error message.

    Raises:
        RWSHTTPError: On controller HTTP errors.

    Example:
        ```python
        message = await read_last_error(client)
        ```
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
        Progress convention is ``0..100``.

    Args:
        client: Open RWS client.
        task: RAPID task name.
        module: RAPID module name.

    Returns:
        Transfer progress percentage.

    Raises:
        RWSHTTPError: On controller HTTP errors.
        ValueError: If the value cannot be parsed as integer.

    Example:
        ```python
        progress = await read_transfer_progress(client)
        ```
    """
    raw = await _read_raw(client, task=task, module=module, variable="transferProgress")
    return _parse_int(raw, name="transferProgress")


async def read_nb_robtargets(
    client: RWSClient,
    *,
    task: str = DEFAULT_TASK,
    module: str = WEB_MODULE,
) -> int:
    """Read ``nbLoadedTrajPoints``.

    ABB Route:
        ``GET /rw/rapid/symbol/data/RAPID/{task}/{module}/nbLoadedTrajPoints``.

    ABB Constraints:
        Valid loaded entries are ``trajData{1..nbLoadedTrajPoints}``.

    Args:
        client: Open RWS client.
        task: RAPID task name.
        module: RAPID module name.

    Returns:
        Number of loaded trajectory points.

    Raises:
        RWSHTTPError: On controller HTTP errors.
        ValueError: If the value cannot be parsed as integer.

    Example:
        ```python
        count = await read_nb_robtargets(client)
        ```
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
    """Read ``nbTrajAvailable``.

    ABB Route:
        ``GET /rw/rapid/symbol/data/RAPID/{task}/{module}/nbTrajAvailable``.

    ABB Constraints:
        Valid metadata entries are ``trajectories{1..nbTrajAvailable}``.

    Args:
        client: Open RWS client.
        task: RAPID task name.
        module: RAPID module name.

    Returns:
        Number of available trajectories.

    Raises:
        RWSHTTPError: On controller HTTP errors.
        ValueError: If the value cannot be parsed as integer.

    Example:
        ```python
        count = await read_nb_traj_dispo(client)
        ```
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
    """Read trajectory display names from ``trajectories``.

    ABB Route:
        ``GET /rw/rapid/symbol/data/RAPID/{task}/{module}/trajectories%7Bi%7D``.

    ABB Constraints:
        ``trajectories`` is a one-based RAPID array of metadata records.

    Args:
        client: Open RWS client.
        task: RAPID task name.
        module: RAPID module name.
        count: Number of entries to read. If ``None``, ``nbTrajAvailable``
            is read first.

    Returns:
        Ordered list of trajectory names.

    Raises:
        RWSHTTPError: On controller HTTP errors.
        ValueError: If count exceeds ``MAX_TRAJ`` or a record cannot be parsed.

    Example:
        ```python
        names = await read_traj_names(client, count=3)
        ```
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
    """Read robot-side defaults used by the resolver.

    ABB Route:
        Multiple ``GET /rw/rapid/symbol/data/{symbolurl}`` calls in
        ``TRAJCENTER_WebServices``.

    ABB Constraints:
        Speed, zone, tool and wobj defaults may only be applied when their
        matching ``hasDefault*`` flag is ``TRUE``.

    Args:
        client: Open RWS client.
        task: RAPID task name.
        module: RAPID module name.

    Returns:
        Robot defaults.

    Raises:
        RWSHTTPError: On controller HTTP errors.
        ValueError: If one raw value cannot be parsed.

    Example:
        ```python
        defaults = await read_robot_defaults(client)
        ```
    """
    has_tcp_speed = _parse_bool(
        await _read_raw(
            client,
            task=task,
            module=module,
            variable="hasDefaultTcpSpeed",
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
            client,
            task=task,
            module=module,
            variable="hasDefaultZoneType",
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
            client,
            task=task,
            module=module,
            variable="hasDefaultToolName",
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
            client,
            task=task,
            module=module,
            variable="hasDefaultWobjName",
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
        await _read_raw(
            client,
            task=task,
            module=module,
            variable="defaultMoveType",
        ),
        name="defaultMoveType",
    )
    read_confs = _parse_bool(
        await _read_raw(
            client,
            task=task,
            module=module,
            variable="defaultReadConfs",
        ),
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


async def read_traj_tools_count(
    client: RWSClient,
    *,
    task: str = DEFAULT_TASK,
    module: str = CELL_MODULE,
) -> int:
    """Read declared size of ``trajTools``.

    ABB Route:
        ``GET /rw/rapid/symbol/properties/RAPID/{task}/{module}/trajTools``.

    ABB Constraints:
        ``trajTools`` is cell-dependent and must not be hardcoded.

    Args:
        client: Open RWS client.
        task: RAPID task name.
        module: RAPID module name.

    Returns:
        Number of declared tool entries.

    Raises:
        RWSHTTPError: On controller HTTP errors.
        ValueError: If the symbol is not an array.

    Example:
        ```python
        count = await read_traj_tools_count(client)
        ```
    """
    return await get_array_length(client, symbolurl=symbol(task, module, "trajTools"))


async def read_traj_wobjs_count(
    client: RWSClient,
    *,
    task: str = DEFAULT_TASK,
    module: str = CELL_MODULE,
) -> int:
    """Read declared size of ``trajWobjs``.

    ABB Route:
        ``GET /rw/rapid/symbol/properties/RAPID/{task}/{module}/trajWobjs``.

    ABB Constraints:
        ``trajWobjs`` is cell-dependent and must not be hardcoded.

    Args:
        client: Open RWS client.
        task: RAPID task name.
        module: RAPID module name.

    Returns:
        Number of declared workobject entries.

    Raises:
        RWSHTTPError: On controller HTTP errors.
        ValueError: If the symbol is not an array.

    Example:
        ```python
        count = await read_traj_wobjs_count(client)
        ```
    """
    return await get_array_length(client, symbolurl=symbol(task, module, "trajWobjs"))


async def read_traj_tool_names(
    client: RWSClient,
    *,
    task: str = DEFAULT_TASK,
    module: str = CELL_MODULE,
    count: int | None = None,
) -> list[str]:
    """Read tool names from ``trajTools``.

    ABB Route:
        ``GET /rw/rapid/symbol/data/RAPID/{task}/{module}/trajTools%7Bi%7D``.

    ABB Constraints:
        Position ``i`` maps to ``toolIndex = i``.

    Args:
        client: Open RWS client.
        task: RAPID task name.
        module: RAPID module name.
        count: Number of entries to read. If ``None``, array length is read.

    Returns:
        Ordered tool names.

    Raises:
        RWSHTTPError: On controller HTTP errors.
        ValueError: If a record cannot be parsed.

    Example:
        ```python
        tools = await read_traj_tool_names(client)
        ```
    """
    if count is None:
        count = await read_traj_tools_count(client, task=task, module=module)

    names: list[str] = []
    for index in range(1, count + 1):
        symbolurl = symbol_array_element(
            task=task,
            module=module,
            variable="trajTools",
            index=index,
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
    """Read workobject names from ``trajWobjs``.

    ABB Route:
        ``GET /rw/rapid/symbol/data/RAPID/{task}/{module}/trajWobjs%7Bi%7D``.

    ABB Constraints:
        Position ``i`` maps to ``wobjIndex = i``.

    Args:
        client: Open RWS client.
        task: RAPID task name.
        module: RAPID module name.
        count: Number of entries to read. If ``None``, array length is read.

    Returns:
        Ordered workobject names.

    Raises:
        RWSHTTPError: On controller HTTP errors.
        ValueError: If a record cannot be parsed.

    Example:
        ```python
        wobjs = await read_traj_wobj_names(client)
        ```
    """
    if count is None:
        count = await read_traj_wobjs_count(client, task=task, module=module)

    names: list[str] = []
    for index in range(1, count + 1):
        symbolurl = symbol_array_element(
            task=task,
            module=module,
            variable="trajWobjs",
            index=index,
        )
        raw = await get_variable(client, symbolurl=symbolurl)
        names.append(_parse_leading_string_field(raw, name="trajWobjs"))

    logger.debug("Read %d workobject names from controller", len(names))
    return names


async def read_process_type_count(
    client: RWSClient,
    *,
    task: str = DEFAULT_TASK,
    module: str = PROCESS_MODULE,
) -> int:
    """Read ``processTypeCount``.

    ABB Route:
        ``GET /rw/rapid/symbol/data/RAPID/{task}/{module}/processTypeCount``.

    ABB Constraints:
        This reads a RAPID ``CONST num``. Real-hardware confirmation is still
        required, but the symbol data route is expected to work for constants.

    Args:
        client: Open RWS client.
        task: RAPID task name.
        module: RAPID module name.

    Returns:
        Number of process catalog entries.

    Raises:
        RWSHTTPError: On controller HTTP errors.
        ValueError: If the value cannot be parsed as integer.

    Example:
        ```python
        count = await read_process_type_count(client)
        ```
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
    """Read robot-side process catalog.

    ABB Route:
        ``GET /rw/rapid/symbol/data/RAPID/{task}/{module}/processTypes%7Bi%7D``.

    ABB Constraints:
        ``processTypes`` record layout is ``[id, name]``. The id field is
        authoritative and must not be inferred from array position.

    Args:
        client: Open RWS client.
        task: RAPID task name.
        module: RAPID module name.
        count: Number of entries to read. If ``None``, ``processTypeCount``
            is read first.

    Returns:
        Ordered process catalog entries.

    Raises:
        RWSHTTPError: On controller HTTP errors.
        ValueError: If a record cannot be parsed.

    Example:
        ```python
        catalog = await read_process_types(client)
        ```
    """
    if count is None:
        count = await read_process_type_count(client, task=task, module=module)

    entries: list[ProcessTypeEntry] = []
    for index in range(1, count + 1):
        symbolurl = symbol_array_element(
            task=task,
            module=module,
            variable="processTypes",
            index=index,
        )
        raw = await get_variable(client, symbolurl=symbolurl)
        entries.append(_parse_process_type_record(raw))

    logger.debug("Read %d process type entries from controller", len(entries))
    return entries


async def read_robot_context(
    client: RWSClient,
    *,
    task: str = DEFAULT_TASK,
) -> RobotContext:
    """Read all robot-side context required by the resolver.

    ABB Route:
        Multiple RWS reads from:
        - ``TRAJCENTER_WebServices``;
        - ``TRAJCENTER_CellConfig``;
        - ``TRAJCENTER_ProcessConfig``.

    ABB Constraints:
        This function performs reads only. No Mastership is required.
        Tool and workobject arrays are converted to immutable tuples so their
        base-1 mapping stays stable during resolution.

    Args:
        client: Open RWS client.
        task: RAPID task name.

    Returns:
        Robot context model.

    Raises:
        RWSHTTPError: On controller HTTP errors.
        ValueError: If one response cannot be parsed.

    Example:
        ```python
        context = await read_robot_context(client)
        ```
    """
    defaults = await read_robot_defaults(client, task=task)
    tool_names = await read_traj_tool_names(client, task=task)
    wobj_names = await read_traj_wobj_names(client, task=task)
    process_types = await read_process_types(client, task=task)

    return RobotContext(
        defaults=defaults,
        tool_names=tuple(tool_names),
        wobj_names=tuple(wobj_names),
        process_types=tuple(process_types),
    )
