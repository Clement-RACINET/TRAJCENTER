#!/usr/bin/env python3
# tests/rws/errors/test_translate.py
"""Unit tests for :mod:`trajcenter.rws.errors.translate`.

> **Author**: Clément RACINET

All exceptions from ``abb_rws_client_python_rw6`` are instantiated
directly (no HTTP traffic, no mocks needed beyond the exception objects
themselves).
"""

from __future__ import annotations

import logging

import pytest
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
)

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
from trajcenter.rws.errors.translate import from_rws_exception


class TestMastershipTranslation:
    """Tests for Mastership-related exception translation."""

    def test_mastership_denied_maps_to_403001(self) -> None:
        """``MastershipDenied`` maps to :class:`MastershipDeniedError`."""
        original = MastershipDenied("denied by controller")
        result = from_rws_exception(original)
        assert isinstance(result, MastershipDeniedError)
        assert result.code == 403001
        assert result.__cause__ is original

    def test_mastership_not_held_maps_to_403002(self) -> None:
        """``MastershipNotHeld`` maps to :class:`RWSWriteForbidden`."""
        original = MastershipNotHeld()
        result = from_rws_exception(original)
        assert isinstance(result, RWSWriteForbidden)
        assert result.code == 403002
        assert result.__cause__ is original

    def test_unknown_mastership_subtype_falls_back_and_logs(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """An unrecognised ``MastershipError`` subtype falls back to 403001."""

        class _CustomMastershipError(MastershipError):
            pass

        original = _CustomMastershipError("custom")
        with caplog.at_level(logging.WARNING):
            result = from_rws_exception(original)
        assert isinstance(result, MastershipDeniedError)
        assert any("Unmapped MastershipError" in msg for msg in caplog.messages)


class TestAuthenticationTranslation:
    """Tests for authentication exception translation."""

    def test_authentication_error_maps_to_401001(self) -> None:
        """``RWSAuthenticationError`` maps to :class:`RWSAuthenticationRefused`."""
        original = RWSAuthenticationError()
        result = from_rws_exception(original)
        assert isinstance(result, RWSAuthenticationRefused)
        assert result.code == 401001
        assert result.__cause__ is original


class TestNotFoundTranslation:
    """Tests for ``RWSNotFoundError`` context-based disambiguation."""

    def test_default_context_maps_to_generic_symbol_not_found(self) -> None:
        """No context supplied falls back to :class:`RapidSymbolNotFound`."""
        original = RWSNotFoundError("RAPID/T_ROB1/M/unknownVar")
        result = from_rws_exception(original)
        assert isinstance(result, RapidSymbolNotFound)
        assert result.code == 404001
        assert result.detail == "RAPID/T_ROB1/M/unknownVar"

    def test_context_traj_tools_maps_to_404002(self) -> None:
        """``context="trajTools"`` maps to :class:`TrajToolsNotFound`."""
        original = RWSNotFoundError("RAPID/T_ROB1/TRAJCENTER_CellConfig/trajTools")
        result = from_rws_exception(original, context="trajTools")
        assert isinstance(result, TrajToolsNotFound)
        assert result.code == 404002

    def test_context_traj_wobjs_maps_to_404003(self) -> None:
        """``context="trajWobjs"`` maps to :class:`TrajWobjsNotFound`."""
        original = RWSNotFoundError("RAPID/T_ROB1/TRAJCENTER_CellConfig/trajWobjs")
        result = from_rws_exception(original, context="trajWobjs")
        assert isinstance(result, TrajWobjsNotFound)
        assert result.code == 404003

    def test_context_trajectory_store_maps_to_404004(self) -> None:
        """``context="trajectory_store"`` maps to :class:`TrajectoryStoreNotFound`."""
        original = RWSNotFoundError("trajectory_store/")
        result = from_rws_exception(original, context="trajectory_store")
        assert isinstance(result, TrajectoryStoreNotFound)
        assert result.code == 404004

    def test_context_robot_default_maps_to_404005(self) -> None:
        """``context="robot_default"`` maps to :class:`RobotDefaultNotFound`."""
        original = RWSNotFoundError("defaultTcpSpeed")
        result = from_rws_exception(original, context="robot_default")
        assert isinstance(result, RobotDefaultNotFound)
        assert result.code == 404005

    def test_context_process_types_maps_to_404006(self) -> None:
        """``context="process_types"`` maps to :class:`ProcessTypesNotFound`."""
        original = RWSNotFoundError("processTypes")
        result = from_rws_exception(original, context="process_types")
        assert isinstance(result, ProcessTypesNotFound)
        assert result.code == 404006

    def test_unknown_context_falls_back_to_generic(self) -> None:
        """An unrecognised context string falls back to :class:`RapidSymbolNotFound`."""
        original = RWSNotFoundError("something")
        result = from_rws_exception(original, context="totally_unknown")
        assert isinstance(result, RapidSymbolNotFound)


class TestNetworkTranslation:
    """Tests for connection and timeout exception translation."""

    def test_connection_error_maps_to_503001(self) -> None:
        """``RWSConnectionError`` maps to :class:`ControllerUnavailable`."""
        original = RWSConnectionError("connect failed")
        result = from_rws_exception(original)
        assert isinstance(result, ControllerUnavailable)
        assert result.code == 503001
        assert result.__cause__ is original

    def test_timeout_default_context_maps_to_408001(self) -> None:
        """No context supplied falls back to :class:`RWSRequestTimeout`."""
        original = RWSTimeoutError("timed out")
        result = from_rws_exception(original)
        assert isinstance(result, RWSRequestTimeout)
        assert result.code == 408001

    def test_timeout_request_context_maps_to_408001(self) -> None:
        """``context="request"`` explicitly maps to :class:`RWSRequestTimeout`."""
        original = RWSTimeoutError("timed out")
        result = from_rws_exception(original, context="request")
        assert isinstance(result, RWSRequestTimeout)
        assert result.code == 408001

    def test_timeout_transfer_context_maps_to_408002(self) -> None:
        """``context="transfer"`` maps to :class:`TransferTimeout`."""
        original = RWSTimeoutError("timed out")
        result = from_rws_exception(original, context="transfer")
        assert isinstance(result, TransferTimeout)
        assert result.code == 408002

    def test_timeout_unknown_context_falls_back_to_request_timeout(self) -> None:
        """An unrecognised context falls back to :class:`RWSRequestTimeout`."""
        original = RWSTimeoutError("timed out")
        result = from_rws_exception(original, context="unknown")
        assert isinstance(result, RWSRequestTimeout)


class TestHttpErrorTranslation:
    """Tests for generic ``RWSHTTPError`` translation."""

    def test_generic_http_error_maps_to_internal_client_error(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """An unmapped ``RWSHTTPError`` maps to :class:`InternalClientError`."""
        original = RWSHTTPError("bad request", status_code=400, ctrl_code=-1073445879)
        with caplog.at_level(logging.ERROR):
            result = from_rws_exception(original)
        assert isinstance(result, InternalClientError)
        assert result.code == 500001
        assert result.__cause__ is original
        assert any("Unmapped RWSHTTPError" in msg for msg in caplog.messages)

    def test_http_error_without_ctrl_code_does_not_raise(self) -> None:
        """An ``RWSHTTPError`` with ``ctrl_code=None`` is still handled safely."""
        original = RWSHTTPError("server error", status_code=500)
        result = from_rws_exception(original)
        assert isinstance(result, InternalClientError)

    def test_http_error_detail_contains_original_message(self) -> None:
        """The translated error's detail carries the original HTTP message."""
        original = RWSHTTPError("some failure", status_code=409)
        result = from_rws_exception(original)
        assert "some failure" in str(result)


class TestValueErrorTranslation:
    """Tests for value/serialization error translation."""

    def test_rws_value_error_maps_to_serialization_error(self) -> None:
        """``RWSValueError`` maps to :class:`SerializationError` (500002)."""
        original = RWSValueError("cannot serialize robtarget")
        result = from_rws_exception(original)
        assert isinstance(result, SerializationError)
        assert result.code == 500002
        assert result.__cause__ is original

    def test_plain_value_error_maps_to_invalid_rws_response(self) -> None:
        """A plain ``ValueError`` (parsing helper failure) maps to 502001."""
        original = ValueError("Cannot parse symbol value from response: ...")
        result = from_rws_exception(original)
        assert isinstance(result, InvalidRWSResponse)
        assert result.code == 502001
        assert result.__cause__ is original


class TestFallbackTranslation:
    """Tests for exceptions not explicitly mapped."""

    def test_unmapped_rws_error_subtype_falls_back(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """An unrecognised direct ``RWSError`` subtype falls back to 500001."""

        class _CustomRWSError(RWSError):
            pass

        original = _CustomRWSError("custom failure")
        with caplog.at_level(logging.WARNING):
            result = from_rws_exception(original)
        assert isinstance(result, InternalClientError)
        assert any("Unmapped RWSError" in msg for msg in caplog.messages)

    def test_completely_unexpected_exception_maps_to_internal_error(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A totally unrelated exception type still yields a safe fallback."""
        original = RuntimeError("something exploded")
        with caplog.at_level(logging.ERROR):
            result = from_rws_exception(original)
        assert isinstance(result, InternalClientError)
        assert result.code == 500001
        assert "RuntimeError" in str(result)
        assert result.__cause__ is original

    def test_fallback_never_raises_itself(self) -> None:
        """``from_rws_exception`` never raises, even for pathological input."""
        result = from_rws_exception(BaseException("edge case"))
        assert isinstance(result, InternalClientError)
