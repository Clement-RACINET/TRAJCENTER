#!/usr/bin/env python3
# utils/fix_init.py
"""Audit and auto-fix all ``__init__.py`` files in a Python project.

Author: Clement RACINET

For each Python package directory (containing ``.py`` files or
sub-packages):

- Creates ``__init__.py`` if missing.
- Rewrites each sub-package ``__init__.py`` with correct imports and
  ``__all__``, discovered automatically via AST scanning.
- Creates minimal ``__init__.py`` markers in ``tests/`` sub-directories
  (no imports).

Design goals
------------
- **Zero hard-coded dictionaries** — all public names are discovered
  automatically via AST.  The only manual knob is an optional
  per-directory *private name blocklist* (``PRIVATE_NAMES_BY_DIR``)
  used to prevent internal helpers from leaking into the public API.
- **Fully generic** — point ``PKG_ROOT`` and ``TESTS_ROOT`` at any
  project and the script works without further edits.
- **Idempotent** — running twice produces no changes.
- **ruff-clean output** — import blocks are sorted (isort / ruff I001),
  line length ≤ 88 chars, no F811 redefinition.

Configuration
-------------
Edit the ``# --- PROJECT CONFIGURATION ---`` section below to adapt
the script to a different project.  No other section needs to change.

Usage:
    python utils/fix_init.py
    python utils/fix_init.py --dry-run
    python utils/fix_init.py --skip-tests

Args:
    --dry-run:     Print what would be written without touching the
                   filesystem.
    --skip-tests:  Skip processing of ``tests/`` sub-directories.
"""

from __future__ import annotations

import argparse
import ast
import io
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# --- PROJECT CONFIGURATION --------------------------------------------------
# ---------------------------------------------------------------------------
# These are the only values that need to change when adapting this script
# to a different project.

#: Absolute path to the repository root.
REPO_ROOT: Path = Path(__file__).parent.parent

#: Root package directory (the one that contains ``__init__.py``).
PKG_ROOT: Path = REPO_ROOT / "trajcenter"

#: Root of the test suite.
TESTS_ROOT: Path = REPO_ROOT / "tests"

#: Package version string injected into the top-level ``__init__.py``.
PKG_VERSION: str = "2.0.0"

#: One-line description injected into the top-level ``__init__.py``.
PKG_DESCRIPTION: str = (
    "TrajCenter v2 — trajectory management and RWS transfer for ABB robots."
)

#: Per-directory blocklist of names that must NOT be re-exported even
#: though they are technically public (no leading underscore).
#:
#: Keys are paths **relative to PKG_ROOT** (e.g. ``"_core"``).
#: Values are sets of names to suppress.
#:
#: Leave empty (``{}``) for full auto-discovery with no filtering.
PRIVATE_NAMES_BY_DIR: dict[str, set[str]] = {
    # Example — uncomment and adapt if needed:
    # "_core": {"build_auth", "raise_for_status"},
}

#: Directories inside PKG_ROOT that should be treated as **leaf**
#: packages (no recursive sub-package discovery).  The default covers
#: the common case where every first-level sub-package is flat.
#: Add nested paths (e.g. ``"rws/rapid"``) to handle deeper trees.
FLAT_SUBDIRS: set[str] = set()

# ---------------------------------------------------------------------------
# --- END OF CONFIGURATION ---------------------------------------------------
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# AST helpers
# ---------------------------------------------------------------------------


def _collect_public_names(py_file: Path, blocklist: set[str]) -> list[str]:
    """Return the public names declared in *py_file*.

    Resolution order (first match wins):

    1. **``__all__``** — if the module declares ``__all__`` at the top
       level, it is the authoritative source of truth.  Only those names
       are returned, minus the *blocklist*.
    2. **Heuristic fallback** — if no ``__all__`` is found, top-level
       definitions whose names do not start with ``_`` are collected,
       with the following automatic exclusions:

       - Assignments whose right-hand side is a call to ``get_logger``
         (bare or attribute form) — logger instances are internal
         implementation details and must never be re-exported.
       - Import statements (``import`` / ``from … import``) — re-exported
         names from dependencies must not pollute ``__all__``.

    Args:
        py_file: Path to the Python source file to inspect.
        blocklist: Set of names to suppress even if declared public.
            Applied to both the ``__all__`` path and the heuristic path.

    Returns:
        Deduplicated, sorted list of public names.

    Example:
        >>> names = _collect_public_names(Path("trajcenter/rws/reader.py"), set())
        >>> "logger" not in names
        True
    """
    try:
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        print(f"  [WARN] Cannot parse {py_file}: {exc}", file=sys.stderr)
        return []

    # ------------------------------------------------------------------
    # Priority 1 — explicit __all__
    # ------------------------------------------------------------------
    for node in tree.body:
        match node:
            case ast.Assign(targets=targets, value=ast.List(elts=elts)):
                for t in targets:
                    if isinstance(t, ast.Name) and t.id == "__all__":
                        names = [
                            e.value
                            for e in elts
                            if isinstance(e, ast.Constant) and isinstance(e.value, str)
                        ]
                        return sorted(n for n in names if n not in blocklist)

    # ------------------------------------------------------------------
    # Priority 2 — heuristic fallback (no __all__ in module)
    # ------------------------------------------------------------------
    names: list[str] = []

    for node in tree.body:
        match node:
            case ast.FunctionDef(name=n) | ast.AsyncFunctionDef(name=n):
                if not n.startswith("_"):
                    names.append(n)
            case ast.ClassDef(name=n):
                if not n.startswith("_"):
                    names.append(n)
            case ast.Assign(targets=targets):
                # Exclude logger instances: logger = get_logger(...)
                if isinstance(node.value, ast.Call):
                    func = node.value.func
                    is_get_logger = (
                        isinstance(func, ast.Name) and func.id == "get_logger"
                    ) or (isinstance(func, ast.Attribute) and func.attr == "get_logger")
                    if is_get_logger:
                        continue
                for t in targets:
                    if isinstance(t, ast.Name) and not t.id.startswith("_"):
                        names.append(t.id)
            case ast.AnnAssign(target=ast.Name(id=n)):
                if not n.startswith("_"):
                    names.append(n)
            # ast.ImportFrom / ast.Import → intentionally ignored

    seen: set[str] = set()
    result: list[str] = []
    for n in names:
        if n not in seen and n not in blocklist:
            seen.add(n)
            result.append(n)
    return sorted(result)


def _collect_dir_public_names(pkg_dir: Path) -> list[str]:
    """Collect all public names from every ``.py`` file in *pkg_dir*.

    Applies the blocklist declared in :data:`PRIVATE_NAMES_BY_DIR` for
    this directory.

    Args:
        pkg_dir: Package directory to scan (non-recursive).

    Returns:
        Deduplicated, sorted list of public names.
    """
    rel_key = pkg_dir.relative_to(PKG_ROOT).as_posix()
    blocklist = PRIVATE_NAMES_BY_DIR.get(rel_key, set())

    all_names: list[str] = []
    for py_file in sorted(pkg_dir.iterdir()):
        if (
            py_file.is_file()
            and py_file.suffix == ".py"
            and py_file.name != "__init__.py"
        ):
            all_names.extend(_collect_public_names(py_file, blocklist))

    # Deduplicate preserving first-occurrence order, then sort
    seen: set[str] = set()
    result: list[str] = []
    for n in all_names:
        if n not in seen:
            seen.add(n)
            result.append(n)
    return sorted(result)


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _format_import(module: str, names: list[str]) -> str:
    """Format a single ``from … import …`` statement.

    Names are sorted alphabetically (isort / ruff I001 compliant).
    Lines longer than 88 characters are wrapped with parentheses.

    Args:
        module: The module to import from (e.g. ``".converter"``).
        names: List of names to import.

    Returns:
        Formatted import string, or empty string when *names* is empty.
    """
    if not names:
        return ""

    sorted_names = sorted(names)
    single = f"from {module} import {', '.join(sorted_names)}"
    if len(single) <= 88:
        return single

    lines = [f"from {module} import ("]
    for name in sorted_names:
        lines.append(f"    {name},")
    lines.append(")")
    return "\n".join(lines)


def _format_all(names: list[str]) -> str:
    """Format a sorted, deduplicated list of names for ``__all__``.

    Args:
        names: Raw list of names (may contain duplicates).

    Returns:
        Indented string of quoted names with trailing commas, ready
        to be embedded inside ``__all__ = [\\n    ...\\n]``.
        Empty string when *names* is empty.
    """
    unique = sorted(set(names))
    if not unique:
        return ""
    return "\n    ".join(f'"{n}",' for n in unique)


# ---------------------------------------------------------------------------
# Filesystem helpers
# ---------------------------------------------------------------------------


def _write(path: Path, content: str, dry_run: bool) -> None:
    """Write *content* to *path*, or print it in dry-run mode.

    Reports one of three statuses:

    - ``[NEW]``       — file did not exist.
    - ``[UNCHANGED]`` — content is identical, no write performed.
    - ``[UPDATED]``   — content changed, file rewritten.

    Args:
        path: Destination file path.
        content: File content to write.
        dry_run: When ``True``, only print; do not write.
    """
    rel = path.relative_to(REPO_ROOT)

    if dry_run:
        print(f"\n{'=' * 60}")
        print(f"[DRY-RUN] Would write: {rel}")
        print(f"{'=' * 60}")
        print(content)
        return

    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        existing = path.read_text(encoding="utf-8")
        if existing == content:
            print(f"  [UNCHANGED] {rel}")
            return
        status = "UPDATED"
    else:
        status = "NEW"

    path.write_text(content, encoding="utf-8")
    print(f"  [{status}] {rel}")


def _is_package_dir(directory: Path) -> bool:
    """Return ``True`` if *directory* qualifies as a Python package.

    A directory qualifies when it contains at least one ``.py`` file
    (excluding ``__init__.py``) or at least one sub-package.

    Args:
        directory: Directory to inspect.

    Returns:
        ``True`` if the directory qualifies as a Python package.
    """
    if not directory.is_dir():
        return False
    has_py = any(
        f.suffix == ".py" and f.name != "__init__.py"
        for f in directory.iterdir()
        if f.is_file()
    )
    has_subpkg = any(
        (d / "__init__.py").exists() or _is_package_dir(d)
        for d in directory.iterdir()
        if d.is_dir() and not d.name.startswith(".")
    )
    return has_py or has_subpkg


def _collect_test_dirs(root: Path) -> list[Path]:
    """Recursively collect all ``tests/`` sub-directories with ``.py`` files.

    Ignores hidden directories and ``__pycache__``.

    Args:
        root: Root of the ``tests/`` directory.

    Returns:
        Sorted list of directories containing at least one ``.py``
        file.
    """
    result: list[Path] = []
    for d in sorted(root.rglob("*")):
        if not d.is_dir():
            continue
        if any(part.startswith((".", "__")) for part in d.parts):
            continue
        if any(f.suffix == ".py" for f in d.iterdir() if f.is_file()):
            result.append(d)
    return result


# ---------------------------------------------------------------------------
# __init__.py generators
# ---------------------------------------------------------------------------


def _gen_subpkg_init(pkg_dir: Path) -> str:
    """Generate ``__init__.py`` for a flat sub-package via AST auto-discovery.

    Scans all ``.py`` files (excluding ``__init__.py``) in *pkg_dir*,
    extracts public names via AST, and generates imports + ``__all__``.
    Applies :data:`PRIVATE_NAMES_BY_DIR` blocklist for this directory.

    Args:
        pkg_dir: Path to the sub-package directory.

    Returns:
        Complete ``__init__.py`` content as a string.
    """
    rel = pkg_dir.relative_to(PKG_ROOT).as_posix()
    rel_key = rel
    blocklist = PRIVATE_NAMES_BY_DIR.get(rel_key, set())

    py_files = sorted(
        f
        for f in pkg_dir.iterdir()
        if f.is_file() and f.suffix == ".py" and f.name != "__init__.py"
    )

    import_blocks: list[str] = []
    all_names: list[str] = []

    for py_file in py_files:
        names = _collect_public_names(py_file, blocklist)
        if names:
            block = _format_import(f".{py_file.stem}", names)
            if block:
                import_blocks.append(block)
            all_names.extend(names)

    imports_block = "\n".join(import_blocks) if import_blocks else "# No public symbols"
    pkg_name = PKG_ROOT.name

    return f"""\
# {pkg_name}/{rel}/__init__.py
\"\"\"Public re-exports for the {rel} sub-package.

Auto-generated by utils/fix_init.py — do not edit manually.
\"\"\"

from __future__ import annotations

{imports_block}

__all__ = [
    {_format_all(all_names)}
]
"""


def _gen_nested_subpkg_init(pkg_dir: Path) -> str:
    """Generate ``__init__.py`` for a nested sub-package (sub-packages + files).

    Collects public names from:

    1. All ``.py`` files directly in *pkg_dir* (excluding
       ``__init__.py``).
    2. All immediate sub-packages (one level deep).

    Names are deduplicated: when the same name appears in multiple
    modules, the first occurrence in alphabetical module order wins
    (avoids ruff F811 redefinition errors).

    Args:
        pkg_dir: Path to the nested sub-package directory.

    Returns:
        Complete ``__init__.py`` content as a string.
    """
    rel = pkg_dir.relative_to(PKG_ROOT).as_posix()
    rel_key = rel
    blocklist = PRIVATE_NAMES_BY_DIR.get(rel_key, set())
    pkg_name = PKG_ROOT.name

    entries: list[tuple[str, list[str]]] = []

    # Sub-packages (directories)
    for sub in sorted(pkg_dir.iterdir()):
        if not sub.is_dir() or sub.name.startswith(("_", ".")):
            continue
        sub_names: list[str] = []
        for py_file in sorted(sub.iterdir()):
            if (
                py_file.is_file()
                and py_file.suffix == ".py"
                and py_file.name != "__init__.py"
            ):
                sub_names.extend(_collect_public_names(py_file, blocklist))
        if sub_names:
            entries.append((sub.name, sorted(set(sub_names))))

    # Flat .py files directly in pkg_dir
    for py_file in sorted(pkg_dir.iterdir()):
        if (
            py_file.is_file()
            and py_file.suffix == ".py"
            and py_file.name != "__init__.py"
        ):
            names = _collect_public_names(py_file, blocklist)
            if names:
                entries.append((py_file.stem, names))

    # Sort alphabetically → ruff I001 compliant
    entries.sort(key=lambda x: x[0])

    # Deduplicate — first module (alpha order) wins
    seen_names: set[str] = set()
    deduped: list[tuple[str, list[str]]] = []
    for stem, names in entries:
        unique = [n for n in names if n not in seen_names]
        seen_names.update(unique)
        if unique:
            deduped.append((stem, unique))

    import_blocks: list[str] = []
    all_names: list[str] = []
    for stem, names in deduped:
        block = _format_import(f".{stem}", names)
        if block:
            import_blocks.append(block)
        all_names.extend(names)

    imports_block = "\n".join(import_blocks) if import_blocks else "# No public symbols"

    return f"""\
# {pkg_name}/{rel}/__init__.py
\"\"\"Public re-exports for the {rel} sub-package.

Auto-generated by utils/fix_init.py — do not edit manually.
\"\"\"

from __future__ import annotations

{imports_block}

__all__ = [
    {_format_all(all_names)}
]
"""


def _gen_package_init() -> str:
    """Generate the top-level ``{PKG_ROOT.name}/__init__.py``.

    Aggregates all public names from every immediate sub-package via
    AST auto-discovery.  Import blocks are sorted alphabetically
    (isort / ruff I001 compliant).  Applies
    :data:`PRIVATE_NAMES_BY_DIR` blocklist per sub-package.

    Returns:
        Complete top-level ``__init__.py`` content as a string.
    """
    pkg_name = PKG_ROOT.name
    import_blocks: list[str] = []
    all_names: list[str] = []

    # Collect from immediate sub-packages, sorted alphabetically
    for sub in sorted(PKG_ROOT.iterdir()):
        if not sub.is_dir() or sub.name.startswith("."):
            continue
        if not _is_package_dir(sub):
            continue
        names = _collect_dir_public_names(sub)
        if names:
            block = _format_import(f".{sub.name}", names)
            if block:
                import_blocks.append(block)
            all_names.extend(names)

    # Also collect from flat .py files directly in PKG_ROOT
    blocklist_root = PRIVATE_NAMES_BY_DIR.get(".", set())
    for py_file in sorted(PKG_ROOT.iterdir()):
        if (
            py_file.is_file()
            and py_file.suffix == ".py"
            and py_file.name != "__init__.py"
        ):
            names = _collect_public_names(py_file, blocklist_root)
            if names:
                block = _format_import(f".{py_file.stem}", names)
                if block:
                    import_blocks.append(block)
                all_names.extend(names)

    imports_block = "\n".join(import_blocks) if import_blocks else "# No public symbols"

    return f"""\
# {pkg_name}/__init__.py
\"\"\"{PKG_DESCRIPTION}

Auto-generated by utils/fix_init.py — do not edit manually.
\"\"\"

from __future__ import annotations

{imports_block}

__all__ = [
    {_format_all(all_names)}
]

__version__ = "{PKG_VERSION}"
"""


def _gen_test_init(directory: Path) -> str:
    """Generate a minimal ``__init__.py`` for a ``tests/`` sub-directory.

    Test ``__init__.py`` files must remain free of imports to avoid
    circular dependencies and pytest collection conflicts.  They only
    serve as package markers for relative imports in ``conftest.py``.

    Args:
        directory: The test sub-directory.

    Returns:
        Minimal ``__init__.py`` content as a string.
    """
    rel = directory.relative_to(REPO_ROOT).as_posix()
    return f"""\
# {rel}/__init__.py
# Package marker — do not add imports here.
# Auto-generated by utils/fix_init.py — do not edit manually.
"""


# ---------------------------------------------------------------------------
# Fix functions
# ---------------------------------------------------------------------------


def _fix_subpackage(sub: Path, dry_run: bool) -> None:
    """Rewrite ``__init__.py`` for a single sub-package of PKG_ROOT.

    Chooses between :func:`_gen_subpkg_init` (flat) and
    :func:`_gen_nested_subpkg_init` (nested) based on whether the
    directory contains sub-packages.

    Args:
        sub: Sub-package directory (direct child of PKG_ROOT).
        dry_run: When ``True``, only print without writing.
    """
    rel_key = sub.relative_to(PKG_ROOT).as_posix()
    has_subpkgs = any(
        d.is_dir() and not d.name.startswith(("_", "."))
        for d in sub.iterdir()
        if d.is_dir()
    )
    is_forced_flat = rel_key in FLAT_SUBDIRS

    if has_subpkgs and not is_forced_flat:
        content = _gen_nested_subpkg_init(sub)
    else:
        content = _gen_subpkg_init(sub)

    _write(sub / "__init__.py", content, dry_run)


def fix_all_subpackages(dry_run: bool) -> None:
    """Rewrite ``__init__.py`` for every sub-package of PKG_ROOT.

    Iterates over all immediate sub-directories of PKG_ROOT that
    qualify as Python packages and rewrites their ``__init__.py``.

    Args:
        dry_run: When ``True``, only print without writing.
    """
    print(f"\n── {PKG_ROOT.name}/ sub-packages ──────────────────────────────")
    for sub in sorted(PKG_ROOT.iterdir()):
        if not sub.is_dir() or sub.name.startswith("."):
            continue
        if not _is_package_dir(sub):
            continue
        _fix_subpackage(sub, dry_run)


def fix_package_root(dry_run: bool) -> None:
    """Rewrite the top-level ``{PKG_ROOT.name}/__init__.py``.

    Args:
        dry_run: When ``True``, only print without writing.
    """
    print(f"\n── {PKG_ROOT.name}/__init__.py ──────────────────────────────────")
    _write(PKG_ROOT / "__init__.py", _gen_package_init(), dry_run)


def fix_tests(dry_run: bool) -> None:
    """Create minimal ``__init__.py`` markers in all ``tests/`` sub-directories.

    Args:
        dry_run: When ``True``, only print without writing.
    """
    if not TESTS_ROOT.exists():
        print("\n[SKIP] tests/ not found — skipping.")
        return

    print("\n── tests/ sub-directories ──────────────────────────────────")
    sub_dirs = _collect_test_dirs(TESTS_ROOT)

    if not sub_dirs:
        print("  [SKIP] No sub-directories with .py files found in tests/.")
        return

    for directory in sub_dirs:
        _write(directory / "__init__.py", _gen_test_init(directory), dry_run)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point.

    Raises:
        SystemExit: On argument parsing error.
    """
    stdout = sys.stdout
    if isinstance(stdout, io.TextIOWrapper):
        stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(
        description=(
            f"Audit and fix all __init__.py files in {PKG_ROOT.name}/ and tests/."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would be written without touching the filesystem.",
    )
    parser.add_argument(
        "--skip-tests",
        action="store_true",
        help="Skip processing of tests/ sub-directories.",
    )
    args = parser.parse_args()

    dry = args.dry_run
    print(
        "🔍 DRY-RUN mode — no files will be written.\n"
        if dry
        else "Fixing __init__.py files...\n"
    )

    fix_all_subpackages(dry)
    fix_package_root(dry)

    if not args.skip_tests:
        fix_tests(dry)

    print("\n Dry-run complete." if dry else "\n Done.")


if __name__ == "__main__":
    main()
