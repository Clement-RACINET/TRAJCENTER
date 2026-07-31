#!/usr/bin/env python3
# trajcenter/rws/errors/codes.py
"""Concrete TrajCenter protocol error codes.

> **Author**: Clément RACINET

One class per error code documented in ``routes/TRAJCENTER.md`` section
12 (codes ``400001``-``504001``). Status codes ``200000``/``200001``/
``200002`` are successes, not exceptions -- they remain plain integer
constants in :mod:`trajcenter.rws.writer`
(``STATUS_OK``/``STATUS_METADATA_REFRESHED``/``STATUS_TRAJECTORY_TRANSFERRED``).

Each class only declares ``code`` and ``default_message``: all behaviour
(``to_rapid``, message formatting, ``cause`` chaining) is inherited from
:class:`trajcenter.rws.errors.base.TrajCenterError`.

This module contains no HTTP or RWS translation logic -- see
:mod:`trajcenter.rws.errors.translate` for that.
"""

from __future__ import annotations

from trajcenter.rws.errors.base import (
    TrajCenterAuthError,
    TrajCenterConflictError,
    TrajCenterError,
    TrajCenterForbiddenError,
    TrajCenterInternalError,
    TrajCenterNotFoundError,
    TrajCenterTimeoutError,
    TrajCenterUpstreamError,
    TrajCenterValidationError,
)

# ---------------------------------------------------------------------------
# 400xxx -- Validation errors
# ---------------------------------------------------------------------------


class SelectedTrajIndexOutOfBounds(TrajCenterValidationError):
    """``selectedTrajIndex`` is 0, negative, or exceeds ``nbTrajAvailable``.

    ABB Constraints:
        Valid range is ``1..nbTrajAvailable`` (§7.1 of the protocol).

    Example:
        ::

            raise SelectedTrajIndexOutOfBounds(detail="index=99, available=3")
    """

    code = 400001
    default_message = "selectedTrajIndex out of bounds"


class TrajectoryFileNotFound(TrajCenterValidationError):
    """The ``.trajcenter`` file referenced by the store metadata is missing.

    Example:
        ::

            raise TrajectoryFileNotFound(detail="trajectory_store/Traj1.trajcenter")
    """

    code = 400002
    default_message = "Trajectory file not found"


class InvalidTrajcenterFormat(TrajCenterValidationError):
    """The ``.trajcenter`` archive is corrupted or violates the format.

    Example:
        ::

            raise InvalidTrajcenterFormat(detail="missing points.parquet entry")
    """

    code = 400003
    default_message = "Invalid .trajcenter format"


class TooManyPoints(TrajCenterValidationError):
    """The trajectory exceeds ``maxTrajPointCount`` (100000).

    Example:
        ::

            raise TooManyPoints(detail="120000 points, max 100000")
    """

    code = 400004
    default_message = "Trajectory has too many points"


class InvalidZoneType(TrajCenterValidationError):
    """A ``zone_type`` value is outside the allowed ABB zone set.

    ABB Constraints:
        Allowed values: ``0, 1, 5, 10, 15, 20, 30, 40, 50, 60, 80, 100,
        150, 200, 255`` (§9.4).

    Example:
        ::

            raise InvalidZoneType(detail="zone_type=42")
    """

    code = 400005
    default_message = "Invalid zone_type value"


class InvalidMoveType(TrajCenterValidationError):
    """A ``move_type`` value is not one of ``MoveL``/``MoveJ``/``MoveC``.

    Example:
        ::

            raise InvalidMoveType(detail="move_type='MoveX'")
    """

    code = 400006
    default_message = "Invalid move_type value"


class InvalidMoveCPair(TrajCenterValidationError):
    """A ``MoveC`` instruction is not paired correctly.

    ABB Constraints:
        ``MoveC`` points must come in consecutive pairs sharing
        ``tcpSpeed``, ``toolIndex``, ``wobjIndex``, ``zoneType``,
        ``readConfs`` and ``processParamIndex`` (§9.7).

    Example:
        ::

            raise InvalidMoveCPair(detail="unpaired MoveC at point 12")
    """

    code = 400007
    default_message = "Invalid MoveC pair"


class MissingTcpSpeedNoDefault(TrajCenterValidationError):
    """``tcp_speed`` is missing and ``hasDefaultTcpSpeed`` is ``FALSE``.

    Example:
        ::

            raise MissingTcpSpeedNoDefault(detail="point 5")
    """

    code = 400008
    default_message = "tcp_speed missing and no robot default available"


class MissingZoneTypeNoDefault(TrajCenterValidationError):
    """``zone_type`` is missing and ``hasDefaultZoneType`` is ``FALSE``.

    Example:
        ::

            raise MissingZoneTypeNoDefault(detail="point 5")
    """

    code = 400009
    default_message = "zone_type missing and no robot default available"


class MissingToolNameNoDefault(TrajCenterValidationError):
    """``tool_name`` is missing and ``hasDefaultToolName`` is ``FALSE``.

    Example:
        ::

            raise MissingToolNameNoDefault(detail="point 5")
    """

    code = 400010
    default_message = "tool_name missing and no robot default available"


class MissingWobjNameNoDefault(TrajCenterValidationError):
    """``wobj_name`` is missing and ``hasDefaultWobjName`` is ``FALSE``.

    Example:
        ::

            raise MissingWobjNameNoDefault(detail="point 5")
    """

    code = 400011
    default_message = "wobj_name missing and no robot default available"


class ToolNameNotFoundOnRobot(TrajCenterValidationError):
    """The requested ``tool_name`` does not exist in ``trajTools``.

    Example:
        ::

            raise ToolNameNotFoundOnRobot(detail="tool_name='Tool_Missing'")
    """

    code = 400012
    default_message = "tool_name not found on robot"


class WobjNameNotFoundOnRobot(TrajCenterValidationError):
    """The requested ``wobj_name`` does not exist in ``trajWobjs``.

    Example:
        ::

            raise WobjNameNotFoundOnRobot(detail="wobj_name='Wobj_Missing'")
    """

    code = 400013
    default_message = "wobj_name not found on robot"


class InvalidTcpSpeed(TrajCenterValidationError):
    """A resolved ``tcp_speed`` value is not strictly positive.

    Example:
        ::

            raise InvalidTcpSpeed(detail="tcp_speed=-10.0")
    """

    code = 400014
    default_message = "Invalid tcp_speed value"


class InvalidReadConfs(TrajCenterValidationError):
    """A resolved ``readconfs`` value is not a valid boolean.

    Example:
        ::

            raise InvalidReadConfs(detail="readconfs='maybe'")
    """

    code = 400015
    default_message = "Invalid readConfs value"


class InvalidRobtarget(TrajCenterValidationError):
    """A trajectory point cannot be serialized into a valid ``robtarget``.

    Example:
        ::

            raise InvalidRobtarget(detail="point 8: NaN in quaternion")
    """

    code = 400016
    default_message = "Invalid robtarget"


class UnknownProcessType(TrajCenterValidationError):
    """The trajectory's ``process_type`` is not in the robot process catalog.

    Example:
        ::

            raise UnknownProcessType(detail="process_type=42")
    """

    code = 400017
    default_message = "Unknown process type"


class TooManyProcessParamSets(TrajCenterValidationError):
    """More than ``maxProcessParamSetCount`` (256) distinct process sets.

    Example:
        ::

            raise TooManyProcessParamSets(detail="300 sets, max 256")
    """

    code = 400018
    default_message = "Too many process parameter sets"


class InvalidProcessParams(TrajCenterValidationError):
    """Process parameters are malformed (bad JSON, empty name, non-numeric).

    Example:
        ::

            raise InvalidProcessParams(detail="empty parameter name at set 3")
    """

    code = 400019
    default_message = "Invalid process parameters"


# ---------------------------------------------------------------------------
# 401xxx -- Authentication errors
# ---------------------------------------------------------------------------


class RWSAuthenticationRefused(TrajCenterAuthError):
    """RWS Digest authentication was refused by the controller.

    Example:
        ::

            raise RWSAuthenticationRefused(cause=original_exc)
    """

    code = 401001
    default_message = "RWS authentication refused"


# ---------------------------------------------------------------------------
# 403xxx -- Forbidden errors
# ---------------------------------------------------------------------------


class MastershipDeniedError(TrajCenterForbiddenError):
    """RAPID Mastership could not be acquired by the client.

    Example:
        ::

            raise MastershipDeniedError(detail="attempt 3/3")
    """

    code = 403001
    default_message = "Mastership denied by controller"


class RWSWriteForbidden(TrajCenterForbiddenError):
    """A write operation was rejected by the controller for policy reasons.

    Example:
        ::

            raise RWSWriteForbidden(detail="write attempted without mastership")
    """

    code = 403002
    default_message = "RWS write forbidden"


# ---------------------------------------------------------------------------
# 404xxx -- Not found errors
# ---------------------------------------------------------------------------


class RapidSymbolNotFound(TrajCenterNotFoundError):
    """A generic RAPID symbol referenced by the protocol does not exist.

    Example:
        ::

            raise RapidSymbolNotFound(detail="RAPID/T_ROB1/.../unknownVar")
    """

    code = 404001
    default_message = "RAPID symbol not found"


class TrajToolsNotFound(TrajCenterNotFoundError):
    """The ``trajTools`` cell configuration array could not be read.

    Example:
        ::

            raise TrajToolsNotFound(cause=original_exc)
    """

    code = 404002
    default_message = "trajTools not found"


class TrajWobjsNotFound(TrajCenterNotFoundError):
    """The ``trajWobjs`` cell configuration array could not be read.

    Example:
        ::

            raise TrajWobjsNotFound(cause=original_exc)
    """

    code = 404003
    default_message = "trajWobjs not found"


class TrajectoryStoreNotFound(TrajCenterNotFoundError):
    """The local trajectory store directory does not exist or is empty.

    Example:
        ::

            raise TrajectoryStoreNotFound(detail="trajectory_store/")
    """

    code = 404004
    default_message = "Trajectory store not found"


class RobotDefaultNotFound(TrajCenterNotFoundError):
    """A robot default variable could not be read from the controller.

    Example:
        ::

            raise RobotDefaultNotFound(detail="defaultTcpSpeed")
    """

    code = 404005
    default_message = "Robot default not found"


class ProcessTypesNotFound(TrajCenterNotFoundError):
    """The ``processTypes`` catalog could not be read from the controller.

    Example:
        ::

            raise ProcessTypesNotFound(cause=original_exc)
    """

    code = 404006
    default_message = "processTypes not found"


# ---------------------------------------------------------------------------
# 408xxx -- Timeout errors
# ---------------------------------------------------------------------------


class RWSRequestTimeout(TrajCenterTimeoutError):
    """A single RWS request exceeded the client's own timeout budget.

    Example:
        ::

            raise RWSRequestTimeout(cause=original_exc)
    """

    code = 408001
    default_message = "RWS request timed out"


class TransferTimeout(TrajCenterTimeoutError):
    """The full trajectory transfer exceeded its overall timeout budget.

    Example:
        ::

            raise TransferTimeout(detail="35s elapsed, limit 30s")
    """

    code = 408002
    default_message = "Trajectory transfer timed out"


# ---------------------------------------------------------------------------
# 409xxx -- Conflict errors
# ---------------------------------------------------------------------------


class TransferAlreadyInProgress(TrajCenterConflictError):
    """A new transfer was requested while one is already running.

    ABB Constraints:
        Raised by the service orchestrator, never by ``reader``/``writer``
        directly -- see ``routes/TRAJCENTER.md`` §2.

    Example:
        ::

            raise TransferAlreadyInProgress(detail="selectedTrajIndex=2")
    """

    code = 409001
    default_message = "A transfer is already in progress"


class IncompatibleRobotState(TrajCenterConflictError):
    """The robot controller state is incompatible with the requested action.

    Example:
        ::

            raise IncompatibleRobotState(detail="RAPID is running")
    """

    code = 409002
    default_message = "Incompatible robot state"


# ---------------------------------------------------------------------------
# 500xxx -- Internal errors
# ---------------------------------------------------------------------------


class InternalClientError(TrajCenterInternalError):
    """An unexpected client-side failure occurred.

    ABB Constraints:
        Catch-all for any exception not otherwise mapped. Always logged
        at ERROR level with full context by
        :func:`trajcenter.rws.errors.translate.from_rws_exception`.

    Example:
        ::

            raise InternalClientError(detail=str(original_exc), cause=original_exc)
    """

    code = 500001
    default_message = "Internal client error"


class SerializationError(TrajCenterInternalError):
    """A value could not be serialized to, or parsed from, RWS format.

    Example:
        ::

            raise SerializationError(detail="RobTarget serialization failed")
    """

    code = 500002
    default_message = "Serialization error"


class TrajectoryConversionError(TrajCenterInternalError):
    """A trajectory could not be converted between internal representations.

    Example:
        ::

            raise TrajectoryConversionError(detail="process_params row 4")
    """

    code = 500003
    default_message = "Trajectory conversion error"


# ---------------------------------------------------------------------------
# 502xxx / 503xxx / 504xxx -- Upstream (controller) errors
# ---------------------------------------------------------------------------


class InvalidRWSResponse(TrajCenterUpstreamError):
    """The controller returned a response that could not be parsed.

    ABB Constraints:
        Maps a plain ``ValueError`` raised by
        ``abb_rws_client_python_rw6.highlevel`` parsing helpers (e.g.
        ``_parse_symbol_value``), which is distinct from
        :class:`SerializationError` (client-side serialization failure).

    Example:
        ::

            raise InvalidRWSResponse(cause=original_value_error)
    """

    code = 502001
    default_message = "Invalid RWS response"


class ControllerUnavailable(TrajCenterUpstreamError):
    """The ABB controller could not be reached over the network.

    Example:
        ::

            raise ControllerUnavailable(cause=original_exc)
    """

    code = 503001
    default_message = "Controller unavailable"


class ControllerTimeout(TrajCenterUpstreamError):
    """The controller itself reported or caused a gateway-level timeout.

    ABB Constraints:
        Distinct from :class:`trajcenter.rws.errors.codes.RWSRequestTimeout`
        (408001): this code is reserved for controller-side timeout
        conditions explicitly identified by the caller, not for generic
        client-perceived timeouts.

    Example:
        ::

            raise ControllerTimeout(cause=original_exc)
    """

    code = 504001
    default_message = "Controller timeout"


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

#: All concrete leaf exception classes, used to build the code registry and
#: to verify (in tests) that no two classes share the same numeric code.
_ALL_ERROR_CLASSES: tuple[type[TrajCenterError], ...] = (
    SelectedTrajIndexOutOfBounds,
    TrajectoryFileNotFound,
    InvalidTrajcenterFormat,
    TooManyPoints,
    InvalidZoneType,
    InvalidMoveType,
    InvalidMoveCPair,
    MissingTcpSpeedNoDefault,
    MissingZoneTypeNoDefault,
    MissingToolNameNoDefault,
    MissingWobjNameNoDefault,
    ToolNameNotFoundOnRobot,
    WobjNameNotFoundOnRobot,
    InvalidTcpSpeed,
    InvalidReadConfs,
    InvalidRobtarget,
    UnknownProcessType,
    TooManyProcessParamSets,
    InvalidProcessParams,
    RWSAuthenticationRefused,
    MastershipDeniedError,
    RWSWriteForbidden,
    RapidSymbolNotFound,
    TrajToolsNotFound,
    TrajWobjsNotFound,
    TrajectoryStoreNotFound,
    RobotDefaultNotFound,
    ProcessTypesNotFound,
    RWSRequestTimeout,
    TransferTimeout,
    TransferAlreadyInProgress,
    IncompatibleRobotState,
    InternalClientError,
    SerializationError,
    TrajectoryConversionError,
    InvalidRWSResponse,
    ControllerUnavailable,
    ControllerTimeout,
)

#: Numeric code -> exception class lookup, e.g. for reverse-mapping a code
#: read back from ``lastErrorCode`` to its originating exception class.
ERROR_CODE_REGISTRY: dict[int, type[TrajCenterError]] = {
    cls.code: cls for cls in _ALL_ERROR_CLASSES
}
