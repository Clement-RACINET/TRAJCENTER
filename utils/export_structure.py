#!/usr/bin/env python3
# contrib/export_structure.py
"""Repository tree exporter.

Author: Clement RACINET

Walks the repository from its root, respects ``.gitignore`` patterns
via stdlib only (fnmatch + re), and writes a Unicode tree representation
to ``structure_repo.txt``.

No third-party dependencies — safe to run with any Python 3.11+
interpreter, including the system Python used by Git hooks.

Usage:
    python export_structure.py

Output:
    /structure_repo.txt
"""

from __future__ import annotations

from pathlib import Path
import re

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

#: Absolute path to the repository root (resolved from the working directory)
ROOT_DIR: Path = Path(".").resolve()

#: Output file written at the project root
OUTPUT_FILE: Path = ROOT_DIR / "structure_repo.txt"

#: Hard-coded exclusions applied regardless of ``.gitignore`` content
EXTRA_IGNORE: set[str] = {
    ".git",
    OUTPUT_FILE.name,
    "site",
    "docs",
}

# ---------------------------------------------------------------------------
# Minimal .gitignore parser
# ---------------------------------------------------------------------------


def _parse_gitignore_patterns(root: Path) -> list[str]:
    """Read raw patterns from .gitignore, stripping comments and blanks.

    Args:
        root: Absolute path to the repository root.

    Returns:
        List of raw gitignore pattern strings.
    """
    gitignore_path = root / ".gitignore"
    if not gitignore_path.exists():
        return []
    # Read the file as UTF-8 and split into individual lines
    lines = gitignore_path.read_text(encoding="utf-8").splitlines()
    # Keep only non-empty lines that are not comments
    return [
        line
        for line in lines
        if line.strip() and not line.startswith("#")
    ]


def _pattern_to_regex(pattern: str) -> re.Pattern[str]:
    """Convert a single gitignore pattern to a compiled regex.

    Handles the most common gitignore rules:
    - Leading ``/``  → anchored to root
    - Trailing ``/`` → directories only (matched as prefix)
    - ``*``          → any chars except ``/``
    - ``**``         → any chars including ``/``
    - ``?``          → any single char except ``/``

    Args:
        pattern: Raw gitignore pattern string.

    Returns:
        Compiled regex pattern.
    """
    # Strip trailing spaces (not escaped)
    pattern = pattern.rstrip(" ")

    # A trailing slash means the pattern only applies to directories
    dir_only = pattern.endswith("/")
    if dir_only:
        pattern = pattern[:-1]  # Remove the trailing slash before processing

    # A leading slash means the pattern is anchored to the repo root
    anchored = pattern.startswith("/")
    if anchored:
        pattern = pattern[1:]  # Remove the leading slash before processing

    # Convert gitignore glob to regex
    regex = ""
    i = 0
    while i < len(pattern):
        if pattern[i : i + 2] == "**":
            # '**' matches any path segment, including directory separators
            regex += ".*"
            i += 2
            # Skip optional surrounding slashes
            if i < len(pattern) and pattern[i] == "/":
                i += 1
        elif pattern[i] == "*":
            # '*' matches anything except a path separator
            regex += "[^/]*"
            i += 1
        elif pattern[i] == "?":
            # '?' matches exactly one character, but not a path separator
            regex += "[^/]"
            i += 1
        else:
            # Escape any regex special character in literal path segments
            regex += re.escape(pattern[i])
            i += 1

    # Anchored patterns must match from the root; others can match anywhere
    regex = "^" + regex if anchored else "(^|/)" + regex

    if dir_only:
        # Must match a directory: followed by '/' or end of string
        regex += "(/|$)"
    else:
        # May match a file or directory: optionally followed by a sub-path
        regex += "(/.*)?$"

    return re.compile(regex)


class GitIgnoreSpec:
    """Minimal gitignore matcher using stdlib only.

    Replaces ``pathspec.PathSpec`` without any third-party dependency.
    Suitable for use in Git hooks where only the system Python is available.

    Args:
        root: Absolute path to the repository root.

    Example:
        >>> spec = GitIgnoreSpec(Path("/my/project"))
        >>> spec.match_file("__pycache__/")
        True
    """

    def __init__(self, root: Path) -> None:
        patterns = _parse_gitignore_patterns(root)
        # Pre-compile every pattern into a regex for efficient repeated matching
        self._regexes: list[re.Pattern[str]] = [
            _pattern_to_regex(p) for p in patterns
        ]

    def match_file(self, rel_path: str) -> bool:
        """Return True if rel_path matches any gitignore pattern.

        Args:
            rel_path: Relative POSIX path from the repository root.
                      Directories should include a trailing ``/``.

        Returns:
            True if the path is ignored.
        """
        # Short-circuit as soon as one pattern matches (lazy evaluation)
        return any(rx.search(rel_path) for rx in self._regexes)


def load_gitignore_spec(root: Path) -> GitIgnoreSpec:
    """Load ``.gitignore`` patterns and return a ``GitIgnoreSpec``.

    Drop-in replacement for the former ``pathspec``-based loader.
    If no ``.gitignore`` file is found, returns an empty spec
    (nothing is ignored by default).

    Args:
        root: Absolute path to the repository root.

    Returns:
        A ``GitIgnoreSpec`` instance compiled from ``.gitignore`` patterns.

    Example:
        >>> spec = load_gitignore_spec(Path("/my/project"))
        >>> spec.match_file("__pycache__/")
        True
    """
    return GitIgnoreSpec(root)


# ---------------------------------------------------------------------------
# Exclusion predicate
# ---------------------------------------------------------------------------


def should_ignore(path: Path, spec: GitIgnoreSpec, root: Path) -> bool:
    """Return whether a path should be excluded from the tree.

    Applies both ``EXTRA_IGNORE`` hard-coded names and the compiled
    ``.gitignore`` spec. Directories are matched with a trailing ``/``
    to correctly trigger directory-specific gitignore rules.

    Args:
        path: Absolute path to the file or directory to test.
        spec: ``GitIgnoreSpec`` instance built from ``.gitignore``.
        root: Absolute path to the repository root.

    Returns:
        ``True`` if the path must be excluded.

    Example:
        >>> should_ignore(Path("/project/.git"), spec, Path("/project"))
        True
    """
    if path.name in EXTRA_IGNORE:
        return True
    # Also ignore hidden files/dirs (starting with .)
    if path.name.startswith("."):
        return True
    # Build a POSIX-style relative path for gitignore matching (e.g. "src/foo.py")
    rel_str = path.relative_to(root).as_posix()
    if path.is_dir():
        # Append trailing slash so directory-specific patterns trigger correctly
        rel_str += "/"
    return spec.match_file(rel_str)


# ---------------------------------------------------------------------------
# Tree generator
# ---------------------------------------------------------------------------


def generate_tree(
    directory: Path,
    spec: GitIgnoreSpec,
    root: Path,
    prefix: str = "",
) -> list[str]:
    """Recursively generate a Unicode tree representation of a directory.

    Directories are listed before files at each level.
    Entries ignored by ``should_ignore()`` are skipped entirely.

    Args:
        directory: Directory to render.
        spec: ``GitIgnoreSpec`` instance built from ``.gitignore``.
        root: Absolute path to the repository root.
        prefix: Current line prefix (box-drawing characters accumulated
                through recursion). Defaults to ``""``.

    Returns:
        List of formatted tree lines for ``directory`` and all its
        non-excluded descendants.

    Example:
        >>> lines = generate_tree(Path("/project"), spec, Path("/project"))
        >>> lines[0]
        '├── abb_rws_client'
    """
    # List filtered entries; sort dirs before files, then alphabetically
    entries = sorted(
        [p for p in directory.iterdir() if not should_ignore(p, spec, root)],
        key=lambda p: (p.is_file(), p.name.lower()),  # False < True → dirs first
    )
    lines: list[str] = []
    for index, entry in enumerate(entries):
        # Use '└──' for the last entry, '├──' for all others
        connector = "└── " if index == len(entries) - 1 else "├── "
        lines.append(f"{prefix}{connector}{entry.name}")
        if entry.is_dir():
            # Last entry gets blank indent; others get a vertical bar to continue the tree
            extension = "    " if index == len(entries) - 1 else "│   "
            lines.extend(generate_tree(entry, spec, root, prefix + extension))
    return lines


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Generate the repository tree and write it to ``structure_repo.txt``.

    Loads ``.gitignore``, walks the full repository tree, and writes
    the result to ``OUTPUT_FILE``. Any pre-existing output file is
    removed before writing.
    """
    spec = load_gitignore_spec(ROOT_DIR)
    # Seed the tree with the root directory name as the top-level label
    tree_lines = [ROOT_DIR.name]
    tree_lines.extend(generate_tree(ROOT_DIR, spec, ROOT_DIR))

    if OUTPUT_FILE.exists():
        # Remove the old file to avoid appending to stale content
        OUTPUT_FILE.unlink()

    # Join all lines with newlines and write as UTF-8
    OUTPUT_FILE.write_text("\n".join(tree_lines), encoding="utf-8")
    print(f"Repository structure exported to: {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
