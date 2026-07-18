#!/usr/bin/env python3
# utils/fix_init.py
"""Audit and auto-fix all ``__init__.py`` files in a Python project.

Author: Clement RACINET

For each Python package directory containing Python files or sub-packages, this
script can:

- Create ``__init__.py`` files when missing.
- Rewrite package ``__init__.py`` files with public re-exports discovered by AST.
- Generate stable ``__all__`` declarations.
- Create minimal ``tests/**/__init__.py`` markers with no imports.

Design goals:
    - Zero project-specific import dictionaries.
    - Public names are discovered automatically through AST parsing.
    - Optional per-directory blocklists can hide public-looking internal names.
    - Generated files are idempotent.
    - Generated imports are Ruff/isort-friendly.
    - Duplicate public names across modules are resolved deterministically to
      avoid Ruff ``F811`` redefinition errors.

Collision policy:
    When several modules export the same public name, the first module wins
    according to the deterministic order used by the generator:

    - alphabetical module order inside a package;
    - alphabetical sub-package order at the top level.

Configuration:
    Edit only the ``PROJECT CONFIGURATION`` section to adapt this script to
    another project.

Usage:
    python utils/fix_init.py
    python utils/fix_init.py --dry-run
    python utils/fix_init.py --skip-tests

ABB Route:
    N/A — local development utility.

ABB Constraints:
    No ABB controller access. No RAPID variable is read or written.

Raises:
    SystemExit: If CLI argument parsing fails.
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
# to another project.

#: Absolute path to the repository root.
REPO_ROOT: Path = Path(__file__).parent.parent

#: Root package directory, i.e. the directory that contains package code.
PKG_ROOT: Path = REPO_ROOT / "trajcenter"

#: Root of the test suite.
TESTS_ROOT: Path = REPO_ROOT / "tests"

#: Package version string injected into the top-level ``__init__.py``.
PKG_VERSION: str = "2.0.0"

#: One-line description injected into the top-level ``__init__.py``.
PKG_DESCRIPTION: str = (
    "TrajCenter v2 — trajectory management and RWS transfer for ABB robots."
)

#: Per-directory blocklist of names that must not be re-exported even though
#: they are technically public because they do not start with ``_``.
#:
#: Keys are paths relative to ``PKG_ROOT``:
#:     - ``"."`` for the root package;
#:     - ``"rws"`` for ``trajcenter/rws``;
#:     - ``"converter"`` for ``trajcenter/converter``;
#:     - ``"some/nested/package"`` for nested packages.
#:
#: Values are sets of names to suppress.
#:
#: Leave empty for full auto-discovery with no filtering.
PRIVATE_NAMES_BY_DIR: dict[str, set[str]] = {
    # Example:
    # "rws": {"internal_helper_name"},
}

#: Directories inside ``PKG_ROOT`` that should be treated as flat packages even
#: if they contain sub-directories. Paths are relative to ``PKG_ROOT``.
FLAT_SUBDIRS: set[str] = set()

# ---------------------------------------------------------------------------
# --- END OF CONFIGURATION ---------------------------------------------------
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# AST helpers
# ---------------------------------------------------------------------------


def _is_public_name(name: str) -> bool:
    """Return whether a name should be considered public by convention.

    ABB Route:
        N/A — local AST helper.

    ABB Constraints:
        No ABB controller access.

    Args:
        name: Python identifier to inspect.

    Returns:
        ``True`` when the name does not start with an underscore.

    Raises:
        None.

    Example:
        >>> _is_public_name("Trajectory")
        True
        >>> _is_public_name("_helper")
        False
    """
    return not name.startswith("_")


def _is_get_logger_call(node: ast.AST) -> bool:
    """Return whether an AST node represents a ``get_logger(...)`` call.

    ABB Route:
        N/A — local AST helper.

    ABB Constraints:
        No ABB controller access.

    Args:
        node: AST node to inspect.

    Returns:
        ``True`` when the node is a call to ``get_logger`` or to an attribute
        named ``get_logger``.

    Raises:
        None.

    Example:
        >>> expr = ast.parse("logger = get_logger(__name__)").body[0]
        >>> isinstance(expr, ast.Assign) and _is_get_logger_call(expr.value)
        True
    """
    if not isinstance(node, ast.Call):
        return False

    func = node.func
    return (isinstance(func, ast.Name) and func.id == "get_logger") or (
        isinstance(func, ast.Attribute) and func.attr == "get_logger"
    )


def _extract_all_from_assignment(node: ast.Assign) -> list[str] | None:
    """Extract names from a simple top-level ``__all__`` assignment.

    Supported form:
        ``__all__ = ["NameA", "NameB"]``

    Dynamic forms are intentionally ignored because they cannot be safely
    resolved by static AST scanning.

    ABB Route:
        N/A — local AST helper.

    ABB Constraints:
        No ABB controller access.

    Args:
        node: Assignment node to inspect.

    Returns:
        List of names when the assignment is a supported ``__all__`` declaration,
        otherwise ``None``.

    Raises:
        None.

    Example:
        >>> assign = ast.parse('__all__ = ["A", "B"]').body[0]
        >>> isinstance(assign, ast.Assign) and _extract_all_from_assignment(assign)
        ['A', 'B']
    """
    is_all_assignment = any(
        isinstance(target, ast.Name) and target.id == "__all__"
        for target in node.targets
    )
    if not is_all_assignment:
        return None

    if not isinstance(node.value, ast.List):
        return None

    names: list[str] = []
    for element in node.value.elts:
        if isinstance(element, ast.Constant) and isinstance(element.value, str):
            names.append(element.value)

    return names


def _dedupe_names(names: list[str], blocklist: set[str]) -> list[str]:
    """Deduplicate names while applying a blocklist.

    The first occurrence wins. The returned list is sorted to provide stable
    import and ``__all__`` output.

    ABB Route:
        N/A — local formatting helper.

    ABB Constraints:
        No ABB controller access.

    Args:
        names: Raw names, possibly containing duplicates.
        blocklist: Names to remove.

    Returns:
        Sorted deduplicated list.

    Raises:
        None.

    Example:
        >>> _dedupe_names(["B", "A", "B", "C"], {"C"})
        ['A', 'B']
    """
    seen: set[str] = set()
    result: list[str] = []

    for name in names:
        if name in seen or name in blocklist:
            continue
        seen.add(name)
        result.append(name)

    return sorted(result)


def _collect_public_names(py_file: Path, blocklist: set[str]) -> list[str]:
    """Return public names declared in a Python file.

    Resolution order:
        1. Explicit top-level ``__all__`` if present and statically readable.
        2. Heuristic fallback collecting public top-level classes, functions,
           async functions and assignments.

    The heuristic deliberately ignores imported names. This prevents dependency
    symbols imported into a module from leaking into generated package APIs.

    Logger instances created with ``get_logger(...)`` are also ignored.

    ABB Route:
        N/A — local AST scanning.

    ABB Constraints:
        No ABB controller access.

    Args:
        py_file: Python source file to inspect.
        blocklist: Public-looking names to suppress.

    Returns:
        Deduplicated, sorted list of public names.

    Raises:
        None. Syntax errors are reported on stderr and produce an empty result.

    Example:
        >>> names = _collect_public_names(Path("trajcenter/rws/writer.py"), set())
        >>> "logger" not in names
        True
    """
    try:
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
    except SyntaxError as exc:
        print(f"  [WARN] Cannot parse {py_file}: {exc}", file=sys.stderr)
        return []

    for node in tree.body:
        if isinstance(node, ast.Assign):
            explicit_all = _extract_all_from_assignment(node)
            if explicit_all is not None:
                return _dedupe_names(explicit_all, blocklist)

    names: list[str] = []

    for node in tree.body:
        match node:
            case ast.FunctionDef(name=name) | ast.AsyncFunctionDef(name=name):
                if _is_public_name(name):
                    names.append(name)

            case ast.ClassDef(name=name):
                if _is_public_name(name):
                    names.append(name)

            case ast.Assign(targets=targets):
                if _is_get_logger_call(node.value):
                    continue

                for target in targets:
                    if isinstance(target, ast.Name) and _is_public_name(target.id):
                        names.append(target.id)

            case ast.AnnAssign(target=ast.Name(id=name)):
                if _is_public_name(name):
                    names.append(name)

            case ast.Import() | ast.ImportFrom():
                continue

            case _:
                continue

    return _dedupe_names(names, blocklist)


def _module_files_in_dir(pkg_dir: Path) -> list[Path]:
    """Return Python module files directly contained in a package directory.

    ``__init__.py`` is excluded.

    ABB Route:
        N/A — local filesystem helper.

    ABB Constraints:
        No ABB controller access.

    Args:
        pkg_dir: Package directory to inspect.

    Returns:
        Sorted list of Python module files.

    Raises:
        OSError: If the directory cannot be read.

    Example:
        >>> files = _module_files_in_dir(Path("trajcenter/core"))
        >>> all(path.name != "__init__.py" for path in files)
        True
    """
    return sorted(
        path
        for path in pkg_dir.iterdir()
        if path.is_file() and path.suffix == ".py" and path.name != "__init__.py"
    )


def _blocklist_for_dir(pkg_dir: Path) -> set[str]:
    """Return the configured private-name blocklist for a package directory.

    ABB Route:
        N/A — local configuration helper.

    ABB Constraints:
        No ABB controller access.

    Args:
        pkg_dir: Package directory inside ``PKG_ROOT``.

    Returns:
        Configured blocklist for this directory, or an empty set.

    Raises:
        ValueError: If ``pkg_dir`` is not relative to ``PKG_ROOT``.

    Example:
        >>> _blocklist_for_dir(PKG_ROOT) == PRIVATE_NAMES_BY_DIR.get(".", set())
        True
    """
    if pkg_dir == PKG_ROOT:
        rel_key = "."
    else:
        rel_key = pkg_dir.relative_to(PKG_ROOT).as_posix()

    return PRIVATE_NAMES_BY_DIR.get(rel_key, set())


def _collect_dir_public_names(pkg_dir: Path) -> list[str]:
    """Collect public names from all modules directly contained in a directory.

    This function is non-recursive. It is used for top-level package aggregation
    and therefore intentionally mirrors the public surface generated for flat
    sub-packages.

    ABB Route:
        N/A — local AST scanning.

    ABB Constraints:
        No ABB controller access.

    Args:
        pkg_dir: Package directory to scan.

    Returns:
        Deduplicated, sorted list of public names.

    Raises:
        OSError: If the directory cannot be read.

    Example:
        >>> names = _collect_dir_public_names(Path("trajcenter/core"))
        >>> isinstance(names, list)
        True
    """
    blocklist = _blocklist_for_dir(pkg_dir)
    all_names: list[str] = []

    for py_file in _module_files_in_dir(pkg_dir):
        all_names.extend(_collect_public_names(py_file, blocklist))

    return _dedupe_names(all_names, set())


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------


def _dedupe_import_entries(
    entries: list[tuple[str, list[str]]],
) -> list[tuple[str, list[str]]]:
    """Remove public-name collisions across import entries.

    The first occurrence wins according to the input order. This prevents
    generated ``__init__.py`` files from importing the same public name from
    multiple modules, which would trigger Ruff ``F811`` redefinition errors.

    ABB Route:
        N/A — local import-generation helper.

    ABB Constraints:
        No ABB controller access.

    Args:
        entries: Import entries as ``(module, names)`` pairs. The module string
            must be directly usable in ``from {module} import ...``.

    Returns:
        Deduplicated entries, preserving input order and removing empty entries.

    Raises:
        None.

    Example:
        >>> _dedupe_import_entries([
        ...     (".reader", ["DEFAULT_TASK", "read"]),
        ...     (".writer", ["DEFAULT_TASK", "write"]),
        ... ])
        [('.reader', ['DEFAULT_TASK', 'read']), ('.writer', ['write'])]
    """
    seen: set[str] = set()
    deduped: list[tuple[str, list[str]]] = []

    for module, names in entries:
        unique_names = [name for name in names if name not in seen]
        seen.update(unique_names)

        if unique_names:
            deduped.append((module, unique_names))

    return deduped


def _format_import(module: str, names: list[str]) -> str:
    """Format a single ``from ... import ...`` statement.

    Names are sorted alphabetically to keep generated output compatible with
    Ruff/isort. Lines longer than 88 characters are wrapped with parentheses.

    ABB Route:
        N/A — local formatting helper.

    ABB Constraints:
        No ABB controller access.

    Args:
        module: Module to import from, for example ``".converter"``.
        names: Names to import from the module.

    Returns:
        Formatted import statement, or an empty string when ``names`` is empty.

    Raises:
        None.

    Example:
        >>> _format_import(".core", ["Trajectory", "MoveType"])
        'from .core import MoveType, Trajectory'
    """
    if not names:
        return ""

    sorted_names = sorted(names)
    single_line = f"from {module} import {', '.join(sorted_names)}"

    if len(single_line) <= 88:
        return single_line

    lines = [f"from {module} import ("]
    for name in sorted_names:
        lines.append(f"    {name},")
    lines.append(")")

    return "\n".join(lines)


def _format_all(names: list[str]) -> str:
    """Format names for a generated ``__all__`` declaration.

    ABB Route:
        N/A — local formatting helper.

    ABB Constraints:
        No ABB controller access.

    Args:
        names: Raw list of public names.

    Returns:
        Indented string of quoted names with trailing commas. Returns an empty
        string when no public name exists.

    Raises:
        None.

    Example:
        >>> _format_all(["B", "A", "A"])
        '"A",\\n    "B",'
    """
    unique_names = sorted(set(names))
    if not unique_names:
        return ""

    return "\n    ".join(f'"{name}",' for name in unique_names)


def _render_init_file(
    *,
    path_comment: str,
    docstring: str,
    imports_block: str,
    all_names: list[str],
    version: str | None = None,
) -> str:
    """Render a complete generated ``__init__.py`` file.

    ABB Route:
        N/A — local file-generation helper.

    ABB Constraints:
        No ABB controller access.

    Args:
        path_comment: First-line comment describing the generated file path.
        docstring: Module docstring content.
        imports_block: Already formatted import block.
        all_names: Names to expose through ``__all__``.
        version: Optional package version to append as ``__version__``.

    Returns:
        Complete file content.

    Raises:
        None.

    Example:
        >>> content = _render_init_file(
        ...     path_comment="# pkg/__init__.py",
        ...     docstring="Package API.",
        ...     imports_block="# No public symbols",
        ...     all_names=[],
        ... )
        >>> "from __future__ import annotations" in content
        True
    """
    version_block = "" if version is None else f'\n__version__ = "{version}"\n'

    return f'''\
{path_comment}
"""{docstring}

Auto-generated by utils/fix_init.py — do not edit manually.
"""

from __future__ import annotations

{imports_block}

__all__ = [
    {_format_all(all_names)}
]
{version_block}'''


# ---------------------------------------------------------------------------
# Filesystem helpers
# ---------------------------------------------------------------------------


def _write(path: Path, content: str, dry_run: bool) -> None:
    """Write content to a path, or print it in dry-run mode.

    ABB Route:
        N/A — local filesystem operation.

    ABB Constraints:
        No ABB controller access.

    Args:
        path: Destination file path.
        content: File content to write.
        dry_run: When ``True``, print content without touching the filesystem.

    Returns:
        None.

    Raises:
        OSError: If the file cannot be written.

    Example:
        >>> _write(Path("tmp.py"), "# content\\n", dry_run=True)
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
    """Return whether a directory qualifies as a Python package.

    A directory qualifies when it contains at least one Python module file
    excluding ``__init__.py`` or at least one nested package-like directory.

    ABB Route:
        N/A — local filesystem inspection.

    ABB Constraints:
        No ABB controller access.

    Args:
        directory: Directory to inspect.

    Returns:
        ``True`` when the directory contains package-like Python content.

    Raises:
        OSError: If the directory cannot be read.

    Example:
        >>> _is_package_dir(PKG_ROOT)
        True
    """
    if not directory.is_dir():
        return False

    has_py_file = any(
        path.suffix == ".py" and path.name != "__init__.py"
        for path in directory.iterdir()
        if path.is_file()
    )
    if has_py_file:
        return True

    return any(
        _is_package_dir(path)
        for path in directory.iterdir()
        if path.is_dir() and not path.name.startswith(".")
    )


def _collect_test_dirs(root: Path) -> list[Path]:
    """Collect all test directories containing Python files.

    Hidden directories and ``__pycache__`` directories are ignored.

    ABB Route:
        N/A — local filesystem inspection.

    ABB Constraints:
        No ABB controller access.

    Args:
        root: Root tests directory.

    Returns:
        Sorted list of directories containing at least one ``.py`` file.

    Raises:
        OSError: If the test tree cannot be read.

    Example:
        >>> isinstance(_collect_test_dirs(TESTS_ROOT), list)
        True
    """
    result: list[Path] = []

    for directory in sorted(root.rglob("*")):
        if not directory.is_dir():
            continue

        if any(part.startswith((".", "__")) for part in directory.parts):
            continue

        has_python_file = any(
            path.suffix == ".py" for path in directory.iterdir() if path.is_file()
        )
        if has_python_file:
            result.append(directory)

    return result


def _iter_immediate_package_dirs(root: Path) -> list[Path]:
    """Return immediate package-like directories contained in a root directory.

    ABB Route:
        N/A — local filesystem inspection.

    ABB Constraints:
        No ABB controller access.

    Args:
        root: Directory whose direct children must be inspected.

    Returns:
        Sorted list of direct child directories qualifying as packages.

    Raises:
        OSError: If the directory cannot be read.

    Example:
        >>> dirs = _iter_immediate_package_dirs(PKG_ROOT)
        >>> all(path.is_dir() for path in dirs)
        True
    """
    return sorted(
        path
        for path in root.iterdir()
        if path.is_dir() and not path.name.startswith(".") and _is_package_dir(path)
    )


# ---------------------------------------------------------------------------
# __init__.py generators
# ---------------------------------------------------------------------------


def _entries_from_flat_package(pkg_dir: Path) -> list[tuple[str, list[str]]]:
    """Build import entries for a flat package directory.

    ABB Route:
        N/A — local AST scanning.

    ABB Constraints:
        No ABB controller access.

    Args:
        pkg_dir: Package directory to scan non-recursively.

    Returns:
        Import entries as ``(".module", public_names)`` pairs.

    Raises:
        OSError: If the directory cannot be read.

    Example:
        >>> entries = _entries_from_flat_package(Path("trajcenter/core"))
        >>> all(module.startswith(".") for module, _ in entries)
        True
    """
    blocklist = _blocklist_for_dir(pkg_dir)
    entries: list[tuple[str, list[str]]] = []

    for py_file in _module_files_in_dir(pkg_dir):
        names = _collect_public_names(py_file, blocklist)
        if names:
            entries.append((f".{py_file.stem}", names))

    return entries


def _entries_from_nested_package(pkg_dir: Path) -> list[tuple[str, list[str]]]:
    """Build import entries for a package with immediate sub-packages.

    This function inspects:

    - immediate sub-directories that qualify as packages;
    - Python modules directly contained in ``pkg_dir``.

    Nested sub-packages are represented by their generated package import,
    for example ``from .rws import ...`` at the top level of another package.

    ABB Route:
        N/A — local AST scanning.

    ABB Constraints:
        No ABB controller access.

    Args:
        pkg_dir: Package directory to inspect.

    Returns:
        Import entries as ``(".module_or_subpackage", public_names)`` pairs.

    Raises:
        OSError: If the directory tree cannot be read.

    Example:
        >>> entries = _entries_from_nested_package(PKG_ROOT)
        >>> all(module.startswith(".") for module, _ in entries)
        True
    """
    entries: list[tuple[str, list[str]]] = []

    for sub_dir in _iter_immediate_package_dirs(pkg_dir):
        names = _collect_dir_public_names(sub_dir)
        if names:
            entries.append((f".{sub_dir.name}", names))

    blocklist = _blocklist_for_dir(pkg_dir)

    for py_file in _module_files_in_dir(pkg_dir):
        names = _collect_public_names(py_file, blocklist)
        if names:
            entries.append((f".{py_file.stem}", names))

    return entries


def _entries_to_imports_and_all(
    entries: list[tuple[str, list[str]]],
) -> tuple[str, list[str]]:
    """Convert import entries into a formatted import block and ``__all__`` names.

    Duplicate public names across entries are removed before import rendering.
    This is the central Ruff ``F811`` prevention point.

    ABB Route:
        N/A — local import-generation helper.

    ABB Constraints:
        No ABB controller access.

    Args:
        entries: Import entries as ``(module, names)`` pairs.

    Returns:
        Tuple ``(imports_block, all_names)``.

    Raises:
        None.

    Example:
        >>> block, names = _entries_to_imports_and_all([
        ...     (".a", ["X", "Y"]),
        ...     (".b", ["X", "Z"]),
        ... ])
        >>> names
        ['X', 'Y', 'Z']
        >>> "from .b import Z" in block
        True
    """
    deduped = _dedupe_import_entries(entries)

    import_blocks: list[str] = []
    all_names: list[str] = []

    for module, names in deduped:
        import_block = _format_import(module, names)
        if import_block:
            import_blocks.append(import_block)
        all_names.extend(names)

    imports_block = "\n".join(import_blocks) if import_blocks else "# No public symbols"

    return imports_block, all_names


def _gen_subpkg_init(pkg_dir: Path) -> str:
    """Generate ``__init__.py`` for a flat sub-package.

    ABB Route:
        N/A — local file generation.

    ABB Constraints:
        No ABB controller access.

    Args:
        pkg_dir: Sub-package directory to scan.

    Returns:
        Complete ``__init__.py`` content.

    Raises:
        OSError: If the directory cannot be read.

    Example:
        >>> content = _gen_subpkg_init(Path("trajcenter/core"))
        >>> "__all__" in content
        True
    """
    rel = pkg_dir.relative_to(PKG_ROOT).as_posix()
    entries = _entries_from_flat_package(pkg_dir)
    imports_block, all_names = _entries_to_imports_and_all(entries)

    return _render_init_file(
        path_comment=f"# {PKG_ROOT.name}/{rel}/__init__.py",
        docstring=f"Public re-exports for the {rel} sub-package.",
        imports_block=imports_block,
        all_names=all_names,
    )


def _gen_nested_subpkg_init(pkg_dir: Path) -> str:
    """Generate ``__init__.py`` for a package with immediate sub-packages.

    ABB Route:
        N/A — local file generation.

    ABB Constraints:
        No ABB controller access.

    Args:
        pkg_dir: Package directory to scan.

    Returns:
        Complete ``__init__.py`` content.

    Raises:
        OSError: If the directory cannot be read.

    Example:
        >>> content = _gen_nested_subpkg_init(PKG_ROOT)
        >>> "from __future__ import annotations" in content
        True
    """
    rel = pkg_dir.relative_to(PKG_ROOT).as_posix()
    entries = _entries_from_nested_package(pkg_dir)
    imports_block, all_names = _entries_to_imports_and_all(entries)

    return _render_init_file(
        path_comment=f"# {PKG_ROOT.name}/{rel}/__init__.py",
        docstring=f"Public re-exports for the {rel} sub-package.",
        imports_block=imports_block,
        all_names=all_names,
    )


def _gen_package_init() -> str:
    """Generate the top-level package ``__init__.py``.

    ABB Route:
        N/A — local file generation.

    ABB Constraints:
        No ABB controller access.

    Args:
        None.

    Returns:
        Complete top-level ``__init__.py`` content.

    Raises:
        OSError: If the package directory cannot be read.

    Example:
        >>> content = _gen_package_init()
        >>> "__version__" in content
        True
    """
    entries = _entries_from_nested_package(PKG_ROOT)
    imports_block, all_names = _entries_to_imports_and_all(entries)

    return _render_init_file(
        path_comment=f"# {PKG_ROOT.name}/__init__.py",
        docstring=PKG_DESCRIPTION,
        imports_block=imports_block,
        all_names=all_names,
        version=PKG_VERSION,
    )


def _gen_test_init(directory: Path) -> str:
    """Generate a minimal ``__init__.py`` marker for a test directory.

    Test package markers intentionally contain no imports to avoid circular
    dependencies and pytest collection side effects.

    ABB Route:
        N/A — local file generation.

    ABB Constraints:
        No ABB controller access.

    Args:
        directory: Test directory.

    Returns:
        Minimal ``__init__.py`` content.

    Raises:
        ValueError: If ``directory`` is not relative to ``REPO_ROOT``.

    Example:
        >>> content = _gen_test_init(TESTS_ROOT)
        >>> "Package marker" in content
        True
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


def _has_immediate_subpackages(directory: Path) -> bool:
    """Return whether a directory contains immediate package-like subdirectories.

    ABB Route:
        N/A — local filesystem inspection.

    ABB Constraints:
        No ABB controller access.

    Args:
        directory: Directory to inspect.

    Returns:
        ``True`` when at least one immediate child is package-like.

    Raises:
        OSError: If the directory cannot be read.

    Example:
        >>> isinstance(_has_immediate_subpackages(PKG_ROOT), bool)
        True
    """
    return any(
        path.is_dir() and not path.name.startswith(("_", ".")) and _is_package_dir(path)
        for path in directory.iterdir()
    )


def _fix_subpackage(sub: Path, dry_run: bool) -> None:
    """Rewrite ``__init__.py`` for a direct sub-package of ``PKG_ROOT``.

    ABB Route:
        N/A — local filesystem operation.

    ABB Constraints:
        No ABB controller access.

    Args:
        sub: Direct child package of ``PKG_ROOT``.
        dry_run: When ``True``, print generated content without writing it.

    Returns:
        None.

    Raises:
        OSError: If the file cannot be written.

    Example:
        >>> _fix_subpackage(PKG_ROOT / "core", dry_run=True)
    """
    rel_key = sub.relative_to(PKG_ROOT).as_posix()
    is_forced_flat = rel_key in FLAT_SUBDIRS

    if _has_immediate_subpackages(sub) and not is_forced_flat:
        content = _gen_nested_subpkg_init(sub)
    else:
        content = _gen_subpkg_init(sub)

    _write(sub / "__init__.py", content, dry_run)


def fix_all_subpackages(dry_run: bool) -> None:
    """Rewrite ``__init__.py`` for every direct sub-package of ``PKG_ROOT``.

    ABB Route:
        N/A — local filesystem operation.

    ABB Constraints:
        No ABB controller access.

    Args:
        dry_run: When ``True``, print generated content without writing it.

    Returns:
        None.

    Raises:
        OSError: If package directories cannot be read or written.

    Example:
        >>> fix_all_subpackages(dry_run=True)
    """
    print(f"\n── {PKG_ROOT.name}/ sub-packages ──────────────────────────────")

    for sub in _iter_immediate_package_dirs(PKG_ROOT):
        _fix_subpackage(sub, dry_run)


def fix_package_root(dry_run: bool) -> None:
    """Rewrite the top-level package ``__init__.py``.

    ABB Route:
        N/A — local filesystem operation.

    ABB Constraints:
        No ABB controller access.

    Args:
        dry_run: When ``True``, print generated content without writing it.

    Returns:
        None.

    Raises:
        OSError: If the top-level ``__init__.py`` cannot be written.

    Example:
        >>> fix_package_root(dry_run=True)
    """
    print(f"\n── {PKG_ROOT.name}/__init__.py ──────────────────────────────────")
    _write(PKG_ROOT / "__init__.py", _gen_package_init(), dry_run)


def fix_tests(dry_run: bool) -> None:
    """Create minimal ``__init__.py`` markers in test sub-directories.

    ABB Route:
        N/A — local filesystem operation.

    ABB Constraints:
        No ABB controller access.

    Args:
        dry_run: When ``True``, print generated content without writing it.

    Returns:
        None.

    Raises:
        OSError: If test directories cannot be read or written.

    Example:
        >>> fix_tests(dry_run=True)
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
    """Run the command-line interface.

    ABB Route:
        N/A — local development utility.

    ABB Constraints:
        No ABB controller access.

    Args:
        None.

    Returns:
        None.

    Raises:
        SystemExit: If CLI argument parsing fails.
        OSError: If package or test files cannot be read or written.

    Example:
        >>> main()
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
    dry_run = bool(args.dry_run)

    print(
        "🔍 DRY-RUN mode — no files will be written.\n"
        if dry_run
        else "Fixing __init__.py files...\n"
    )

    fix_all_subpackages(dry_run)
    fix_package_root(dry_run)

    if not args.skip_tests:
        fix_tests(dry_run)

    print("\nDry-run complete." if dry_run else "\nDone.")


if __name__ == "__main__":
    main()
