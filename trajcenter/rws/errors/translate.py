#!/usr/bin/env python3
# trajcenter/rws/errors/translate.py
"""Translation of transport-layer RWS exceptions into TrajCenter errors.

> **Author**: Clément RACINET

This module is the single point of contact between
``abb_rws_client_python_rw6.core.exceptions`` and the TrajCenter protocol
error hierarchy (:mod:`trajcenter.rws.errors.codes`). If the RW6 client
library changes its exception hierarchy, only this module is affected.

Usage pattern (``rws/reader.py`` / ``rws/writer.py``)
------------------------------------------------------
::

    try:
        raw = await get_variable(client, symbolurl=symbol(...))
    except Exception as exc:
        raise from_rws_exception(exc, context="trajTools") from exc

Design principle
-----------------
Validation failures produced locally by :mod:`trajcenter.rws.resolver`
(e.g. an out-of-bounds index, an unresolvable tool name) are raised
directly as :mod:`trajcenter.rws.errors.codes` exceptions -- they never
pass through this module, since no ``abb_rws_client_python_rw6``
exception is involved in that case.

Context discriminant
---------------------
Several transport exceptions (``RWSNotFoundError``, ``RWSTimeoutError``)
map to more than one TrajCenter code depending on *what* was being read
or written. The caller passes a short ``context`` string to disambiguate;
an unrecognised or empty context falls back to the most generic code in
that category (``404001`` for not-found, ``408001`` for timeout).

Known ``context`` values:
    - ``"trajTools"`` -- reading the cell tool configuration array.
    - ``"trajWobjs"`` -- reading the cell workobject configuration array.
    - ``"trajectory_store"`` -- scanning the local trajectory store.
    - ``"robot_default"`` -- reading a ``TRAJCENTER`` default.
    - ``"process_types"`` -- reading the ``TRAJCENTER`` catalog.
    - ``"transfer"`` -- the overall trajectory transfer operation.
    - ``"request"`` (default) -- a single RWS request with no more
      specific context.
"""

from __future__ import annotations

from typing import Final

from abb_rws_client_python_rw6 import MastershipDenied, MastershipNotHeld
from abb_rws_client_python_rw6.core.exceptions import (
    MastershipError,
    RWSAuthenticationError,
    RWSConnectionError,
    RWSError,
    RWSHTTPError,
    RWSNotFoundError,
    RWSTimeoutError,
    RWSValueError,
    ctrl_code_name,
)

from trajcenter.core.logger import get_logger
from trajcenter.rws.errors.base import TrajCenterError
from trajcenter.rws.errors.codes import (
    ControllerUnavailable,
    InternalClientError,
    InvalidRWSResponse,
    MastershipDeniedError,
    ProcessTypesNotFound,
    RapidSymbolNotFound,
    RobotDefaultNotFound,
    RWSAuthenticationRefused,
    RWSRequestTimeout,
    RWSWriteForbidden,
    SerializationError,
    TrajectoryStoreNotFound,
    TrajToolsNotFound,
    TrajWobjsNotFound,
    TransferTimeout,
)

logger = get_logger(__name__)

#: Context discriminant -> not-found exception class, used to disambiguate
#: ``RWSNotFoundError`` into the correct 404xxx TrajCenter code. Any
#: context not listed here falls back to ``RapidSymbolNotFound`` (404001).
_NOT_FOUND_BY_CONTEXT: Final[dict[str, type[TrajCenterError]]] = {
    "trajTools": TrajToolsNotFound,
    "trajWobjs": TrajWobjsNotFound,
    "trajectory_store": TrajectoryStoreNotFound,
    "robot_default": RobotDefaultNotFound,
    "process_types": ProcessTypesNotFound,
}

#: Context discriminant -> timeout exception class, used to disambiguate
#: ``RWSTimeoutError`` into the correct 408xxx TrajCenter code. Any
#: context not listed here falls back to ``RWSRequestTimeout`` (408001).
_TIMEOUT_BY_CONTEXT: Final[dict[str, type[TrajCenterError]]] = {
    "transfer": TransferTimeout,
    "request": RWSRequestTimeout,
}


def from_rws_exception(
    exc: BaseException, *, context: str = "request"
) -> TrajCenterError:
    """Translate a transport-layer exception into a TrajCenter protocol error.

    ABB Route:
        N/A -- pure translation helper, no RWS call performed.

    ABB Constraints:
        This function must be the only place in ``trajcenter`` that
        imports exception types from
        ``abb_rws_client_python_rw6.core.exceptions``. Callers in
        ``rws/reader.py`` / ``rws/writer.py`` must always go through this
        function rather than re-raising a transport exception directly,
        so that ``lastErrorCode``/``lastError`` always carry a protocol
        code, never an ABB transport code.

    Args:
        exc: The exception caught from an ``abb_rws_client_python_rw6``
            call, or -- as a defensive fallback -- any other exception
            raised unexpectedly in that call site.
        context: Discriminant used to disambiguate ``RWSNotFoundError``
            and ``RWSTimeoutError`` into the correct TrajCenter code. See
            the module docstring for the list of known values. Defaults
            to ``"request"``.

    Returns:
        A :class:`~trajcenter.rws.errors.base.TrajCenterError` instance
        ready to be raised (with ``from exc`` at the call site) and later
        converted to a ``(code, message)`` pair via
        :meth:`~trajcenter.rws.errors.base.TrajCenterError.to_rapid`.

    Example:
        ::

            try:
                raw = await get_variable(client, symbolurl=url)
            except Exception as exc:
                raise from_rws_exception(exc, context="trajTools") from exc
    """
    # -- Mastership branch (MastershipError is a sibling of RWSHTTPError
    # under RWSError, not a subclass of it -- checked first, independently
    # of the HTTP branch below).
    if isinstance(exc, MastershipDenied):
        return MastershipDeniedError(detail=str(exc), cause=exc)

    if isinstance(exc, MastershipNotHeld):
        return RWSWriteForbidden(detail=str(exc), cause=exc)

    if isinstance(exc, MastershipError):
        # Defensive fallback for any future MastershipError subclass not
        # explicitly handled above.
        logger.warning("Unmapped MastershipError subtype: %s", type(exc).__name__)
        return MastershipDeniedError(detail=str(exc), cause=exc)

    # -- Authentication.
    if isinstance(exc, RWSAuthenticationError):
        return RWSAuthenticationRefused(detail=str(exc), cause=exc)

    # -- Not found (must be checked before the generic RWSHTTPError branch,
    # since RWSNotFoundError subclasses RWSHTTPError).
    if isinstance(exc, RWSNotFoundError):
        not_found_cls = _NOT_FOUND_BY_CONTEXT.get(context, RapidSymbolNotFound)
        return not_found_cls(detail=exc.resource, cause=exc)

    # -- Network / timeout (checked before the generic RWSHTTPError branch;
    # both are direct RWSError subclasses, not RWSHTTPError subclasses, but
    # grouped here for readability).
    if isinstance(exc, RWSConnectionError):
        return ControllerUnavailable(detail=str(exc), cause=exc)

    if isinstance(exc, RWSTimeoutError):
        timeout_cls = _TIMEOUT_BY_CONTEXT.get(context, RWSRequestTimeout)
        return timeout_cls(detail=str(exc), cause=exc)

    # -- Generic HTTP >= 400, not covered by a more specific exception
    # above. The ABB symbolic code name is logged for diagnosis but never
    # written to the RAPID-facing message (RAPID string is 80 chars max
    # and must stay human-readable for the FlexPendant operator).
    if isinstance(exc, RWSHTTPError):
        logger.error(
            "Unmapped RWSHTTPError [context=%s]: status=%s ctrl_code=%s message=%s",
            context,
            exc.status_code,
            exc.ctrl_code_name or ctrl_code_name(exc.ctrl_code or 0),
            exc.message,
        )
        return InternalClientError(detail=exc.message, cause=exc)

    # -- Client-side serialization failure (writing a Python value to a
    # RAPID literal). Distinct from InvalidRWSResponse below, which covers
    # a controller response that could not be parsed.
    if isinstance(exc, RWSValueError):
        return SerializationError(detail=str(exc), cause=exc)

    # -- Any other RWSError subtype not explicitly handled above.
    if isinstance(exc, RWSError):
        logger.warning("Unmapped RWSError subtype: %s", type(exc).__name__)
        return InternalClientError(detail=str(exc), cause=exc)

    # -- Plain ValueError raised by abb_rws_client_python_rw6 parsing
    # helpers (e.g. highlevel.variables._parse_symbol_value,
    # highlevel.symbol._parse_symbol_properties) when a controller
    # response body cannot be parsed. Not an RWSError instance, so it must
    # be checked explicitly and before the final catch-all.
    if isinstance(exc, ValueError):
        return InvalidRWSResponse(detail=str(exc), cause=exc)

    # -- Fully unexpected exception type: never silently swallowed, always
    # logged with its real type for future mapping.
    logger.error(
        "Unexpected exception type reached from_rws_exception [context=%s]: %s: %s",
        context,
        type(exc).__name__,
        exc,
    )
    return InternalClientError(detail=f"{type(exc).__name__}: {exc}", cause=exc)
