#!/usr/bin/env python3
# trajcenter/rws/errors/base.py
"""Base exception hierarchy for the TrajCenter RWS transfer protocol.

> **Author**: Clément RACINET

This module defines the root :class:`TrajCenterError` and its eight
category-level subclasses, mirroring the code ranges documented in
``routes/TRAJCENTER.md`` section 12 (status and error codes).

Concrete leaf exceptions (one per protocol error code) are declared in
:mod:`trajcenter.rws.errors.codes`. Translation from
``abb_rws_client_python_rw6`` exceptions into this hierarchy is handled
in :mod:`trajcenter.rws.errors.translate`.

Design principle
-----------------
This hierarchy is a *protocol-level* taxonomy, distinct from the
transport-level ``RWSError`` hierarchy of ``abb_rws_client_python_rw6``
and distinct from the conversion-level messages in
``trajcenter.core.messages``. Transport errors are translated into this
hierarchy at the boundary (``rws/reader.py`` / ``rws/writer.py``); they
are never re-raised as-is toward the orchestrator or toward RAPID.

ABB constraints
----------------
- All four TrajCenter RAPID modules must be saved as ISO-8859-1. Error
  messages built here therefore use only ASCII separators (``"-"``,
  ``"..."``) so :meth:`TrajCenterError.to_rapid` never produces a string
  that cannot be encoded when written to the RAPID ``lastError``
  variable.
- RAPID ``string`` values have a maximum length of 80 characters
  (``RAPID_STRMAX``). Longer messages are truncated by
  :meth:`TrajCenterError.to_rapid`.
"""

from __future__ import annotations

from typing import ClassVar, Final

#: Maximum length of a RAPID ``string`` value (ABB RAPID language
#: reference). Messages longer than this are truncated before being
#: written to ``TRAJCENTER/lastError``.
RAPID_STRMAX: Final[int] = 80


class TrajCenterError(Exception):
    """Root of the TrajCenter RWS transfer protocol error hierarchy.

    Every concrete error in :mod:`trajcenter.rws.errors.codes` subclasses
    one of the eight category classes defined below, which themselves
    subclass ``TrajCenterError``. Catching ``TrajCenterError`` catches
    every protocol error raised by the ``rws`` layer.

    ABB Route:
        N/A -- internal exception hierarchy, not an RWS route.

    ABB Constraints:
        Instances are converted to a ``(code, message)`` pair via
        :meth:`to_rapid` before being written to the RAPID
        ``lastErrorCode`` (``num``) and ``lastError`` (``string``)
        variables declared in ``TRAJCENTER``.

    Attributes:
        code: Numeric protocol status code, one of the values documented
            in ``routes/TRAJCENTER.md`` section 12. Set by each leaf
            subclass in :mod:`trajcenter.rws.errors.codes`.
        default_message: Short human-readable description used when no
            ``detail`` is supplied at raise time.
        detail: Optional contextual detail supplied at raise time, e.g.
            the offending value or resource name.

    Example:
        ::

            raise MastershipDeniedError(detail="attempt 3/3")
    """

    code: ClassVar[int]
    default_message: ClassVar[str]

    def __init__(
        self,
        detail: str | None = None,
        *,
        cause: BaseException | None = None,
    ) -> None:
        """Build a TrajCenter protocol error.

        Args:
            detail: Optional contextual detail appended to
                ``default_message`` after an ASCII ``" - "`` separator.
            cause: Optional originating exception. Chained as
                ``__cause__`` so the full traceback stays visible in
                logs, without leaking transport-layer detail into the
                RAPID-facing message.

        Returns:
            None.

        Example:
            ::

                TrajToolsNotFound(detail="RAPID/T_ROB1/.../trajTools")
        """
        self.detail = detail
        message = (
            f"{self.default_message} - {detail}" if detail else self.default_message
        )
        super().__init__(message)
        if cause is not None:
            self.__cause__ = cause

    def to_rapid(self) -> tuple[int, str]:
        """Convert this error to a ``(lastErrorCode, lastError)`` pair.

        ABB Route:
            Result is written via
            ``POST /rw/rapid/symbol/data/RAPID/{task}/TRAJCENTER/lastErrorCode``
            and the equivalent ``.../lastError`` call.

        ABB Constraints:
            RAPID ``string`` values are limited to ``RAPID_STRMAX`` (80)
            characters. Longer messages are truncated with an ASCII
            ``"..."`` suffix. Only ASCII/Latin-1-safe characters are
            ever produced, since the RAPID modules require ISO-8859-1
            encoding.

        Returns:
            Tuple of ``(code, message)`` ready to write to RAPID.

        Example:
            ::

                code, message = MastershipDeniedError().to_rapid()
                assert code == 403001
        """
        text = str(self)
        if len(text) > RAPID_STRMAX:
            text = text[: RAPID_STRMAX - 3] + "..."
        return self.code, text

    def __repr__(self) -> str:
        """Return a concise debug representation.

        Returns:
            String showing the class name, numeric code and detail.
        """
        return f"{self.__class__.__name__}(code={self.code}, detail={self.detail!r})"


class TrajCenterValidationError(TrajCenterError):
    """Category base for trajectory/content validation errors (400xxx).

    Raised by :mod:`trajcenter.rws.resolver` when a ``.trajcenter``
    trajectory fails validation before transfer -- never by a translated
    RWS transport error.
    """


class TrajCenterAuthError(TrajCenterError):
    """Category base for RWS authentication errors (401xxx).

    Raised only via :func:`trajcenter.rws.errors.translate.from_rws_exception`
    when the underlying ``abb_rws_client_python_rw6`` session rejects
    Digest authentication.
    """


class TrajCenterForbiddenError(TrajCenterError):
    """Category base for RWS permission errors (403xxx).

    Covers both a denied Mastership acquisition and a write attempt
    rejected by the controller for policy reasons.
    """


class TrajCenterNotFoundError(TrajCenterError):
    """Category base for missing-resource errors (404xxx).

    Covers RAPID symbols, cell configuration arrays (``trajTools``,
    ``trajWobjs``), the local trajectory store, robot defaults and the
    process catalog.
    """


class TrajCenterTimeoutError(TrajCenterError):
    """Category base for client-perceived timeout errors (408xxx).

    Raised when an RWS request or a full trajectory transfer does not
    complete within the operation's own timeout budget. Distinct from
    :class:`TrajCenterUpstreamError` (504001), which represents a
    controller-side gateway timeout reported by RWS itself.
    """


class TrajCenterConflictError(TrajCenterError):
    """Category base for state-conflict errors (409xxx).

    Raised by the service orchestrator (not by ``reader``/``writer``)
    when a transfer is requested while one is already running, or when
    the robot controller state is incompatible with the request.
    """


class TrajCenterInternalError(TrajCenterError):
    """Category base for internal client-side errors (500xxx).

    Covers unexpected client failures, serialization failures in
    ``abb_rws_client_python_rw6``, and trajectory conversion failures.
    Never expected in normal operation; always logged at ERROR level
    with full context when raised.
    """


class TrajCenterUpstreamError(TrajCenterError):
    """Category base for controller/upstream availability errors.

    Covers an invalid or unparsable RWS response (502001), an
    unreachable controller (503001), and a controller-side gateway
    timeout (504001). These mirror HTTP 502/503/504 semantics applied to
    the ABB controller as the upstream service.
    """
