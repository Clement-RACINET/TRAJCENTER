#!/usr/bin/env python3
# trajcenter/core/messages.py
"""Central registry of all user-facing error and warning messages.

> **Author**: Clément RACINET

Messages are loaded **once** at import time from ``messages.json``
(located in the same directory as this module).

Use :func:`msg` to produce a formatted message, and :func:`raw` to
retrieve the unformatted template (useful in tests for ``match=``
patterns).

Example:
    ::

        import warnings
        from trajcenter.core.messages import msg

        raise FileNotFoundError(msg("FILE_NOT_FOUND", path=p))
        warnings.warn(msg("DUPLICATE_CANONICAL", canon="x", kept="x", ignored="PosX"))

    In tests::

        from trajcenter.core.messages import raw
        import re

        with pytest.raises(FileNotFoundError, match=re.escape(raw("FILE_NOT_FOUND").split(":")[0])):
            ...
"""

from __future__ import annotations

import json
from pathlib import Path

_MESSAGES: dict[str, str] = json.loads(
    (Path(__file__).parent / "messages.json").read_text(encoding="utf-8")
)


def msg(_key: str, **kwargs: object) -> str:
    """Return the formatted message for *_key*.

    The first parameter is named ``_key`` (with leading underscore) to
    avoid collisions with message placeholders that may also be named
    ``key`` (e.g. ``INVALID_EAX_KEY`` uses ``{key}`` as a placeholder).

    Args:
        _key: Message key defined in ``messages.json``.
        **kwargs: Format arguments interpolated into the message
            template via :meth:`str.format`.

    Returns:
        Formatted message string ready to be passed to an exception
        or :func:`warnings.warn`.

    Raises:
        KeyError: If *_key* is not defined in ``messages.json``.
        KeyError: If a required placeholder is missing from *kwargs*.

    Example:
        ::

            msg("FILE_NOT_FOUND", path="/tmp/foo.mod")
            # → "File not found: /tmp/foo.mod"

            msg("INVALID_EAX_KEY", key="eax_z")
            # → "Invalid external axis key: 'eax_z'. Expected eax_a … eax_f."
    """
    return _MESSAGES[_key].format(**kwargs)


def raw(key: str) -> str:
    """Return the raw (unformatted) template string for *key*.

    Useful in tests to build ``match=`` patterns without duplicating
    the string literal.  The returned string may contain
    ``{placeholder}`` tokens.

    Args:
        key: Message key defined in ``messages.json``.

    Returns:
        Raw template string.

    Raises:
        KeyError: If *key* is not defined in ``messages.json``.

    Example:
        ::

            raw("FILE_NOT_FOUND")
            # → "File not found: {path}"

            raw("MANDATORY_COLUMNS_MISSING")
            # → "Mandatory columns missing: {cols}"
    """
    return _MESSAGES[key]
