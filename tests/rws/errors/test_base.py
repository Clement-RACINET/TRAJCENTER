#!/usr/bin/env python3
# tests/rws/errors/test_base.py
"""Unit tests for :mod:`trajcenter.rws.errors.base`.

> **Author**: Clément RACINET
"""

from __future__ import annotations

import pytest

from trajcenter.rws.errors.base import RAPID_STRMAX, TrajCenterError


class _DummyError(TrajCenterError):
    """Minimal concrete error used to exercise the base class in isolation."""

    code = 999999
    default_message = "Dummy error"


class TestTrajCenterErrorConstruction:
    """Tests for :class:`TrajCenterError` message construction."""

    def test_no_detail_uses_default_message(self) -> None:
        """Without ``detail``, the message equals ``default_message``."""
        exc = _DummyError()
        assert str(exc) == "Dummy error"

    def test_with_detail_appends_ascii_separator(self) -> None:
        """With ``detail``, the message is ``default - detail``."""
        exc = _DummyError(detail="extra context")
        assert str(exc) == "Dummy error - extra context"

    def test_detail_attribute_stored(self) -> None:
        """``detail`` is stored verbatim on the instance."""
        exc = _DummyError(detail="foo")
        assert exc.detail == "foo"

    def test_detail_none_by_default(self) -> None:
        """``detail`` defaults to ``None`` when not supplied."""
        exc = _DummyError()
        assert exc.detail is None

    def test_no_ascii_incompatible_separator(self) -> None:
        """The separator is a plain ASCII hyphen, never an em-dash.

        RAPID modules require ISO-8859-1 encoding; a non-Latin-1
        character here would silently corrupt the ``lastError`` write.
        """
        exc = _DummyError(detail="x")
        assert "\u2014" not in str(exc)
        assert " - " in str(exc)


class TestTrajCenterErrorCauseChaining:
    """Tests for exception cause chaining."""

    def test_cause_is_chained(self) -> None:
        """Supplying ``cause`` sets ``__cause__`` on the instance."""
        original = ValueError("root cause")
        exc = _DummyError(cause=original)
        assert exc.__cause__ is original

    def test_no_cause_leaves_cause_unset(self) -> None:
        """Without ``cause``, ``__cause__`` remains ``None``."""
        exc = _DummyError()
        assert exc.__cause__ is None

    def test_raise_from_preserves_chain(self) -> None:
        """The error can still be raised with an explicit ``from`` clause."""
        original = ValueError("root cause")
        with pytest.raises(_DummyError) as excinfo:
            try:
                raise original
            except ValueError as exc:
                raise _DummyError(cause=exc) from exc
        assert excinfo.value.__cause__ is original


class TestTrajCenterErrorToRapid:
    """Tests for :meth:`TrajCenterError.to_rapid`."""

    def test_short_message_not_truncated(self) -> None:
        """A message shorter than ``RAPID_STRMAX`` is returned unchanged."""
        exc = _DummyError()
        code, text = exc.to_rapid()
        assert code == 999999
        assert text == "Dummy error"

    def test_message_at_exact_limit_not_truncated(self) -> None:
        """A message exactly ``RAPID_STRMAX`` characters long is untouched."""
        detail = "x" * (RAPID_STRMAX - len("Dummy error - "))
        exc = _DummyError(detail=detail)
        _, text = exc.to_rapid()
        assert len(text) == RAPID_STRMAX
        assert not text.endswith("...")

    def test_long_message_truncated_with_ellipsis(self) -> None:
        """A message longer than ``RAPID_STRMAX`` is truncated with ``...``."""
        exc = _DummyError(detail="y" * 200)
        _, text = exc.to_rapid()
        assert len(text) == RAPID_STRMAX
        assert text.endswith("...")

    def test_truncated_message_has_no_non_latin1_char(self) -> None:
        """Truncation never introduces a character outside Latin-1."""
        exc = _DummyError(detail="z" * 200)
        _, text = exc.to_rapid()
        text.encode("latin-1")  # Raises UnicodeEncodeError on failure.

    def test_returns_tuple_of_int_and_str(self) -> None:
        """The return type is exactly ``(int, str)``."""
        code, text = _DummyError().to_rapid()
        assert isinstance(code, int)
        assert isinstance(text, str)


class TestTrajCenterErrorRepr:
    """Tests for :meth:`TrajCenterError.__repr__`."""

    def test_repr_contains_class_name_code_and_detail(self) -> None:
        """``repr`` shows the class name, numeric code and detail."""
        exc = _DummyError(detail="ctx")
        representation = repr(exc)
        assert "_DummyError" in representation
        assert "999999" in representation
        assert "ctx" in representation

    def test_repr_with_no_detail(self) -> None:
        """``repr`` handles a ``None`` detail without raising."""
        representation = repr(_DummyError())
        assert "detail=None" in representation
