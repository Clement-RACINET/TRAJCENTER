#!/usr/bin/env python3
# scripts/doc/generate_api.py
"""
Automatic MkDocs API page generator for abb_rws_client_python_rw6.

Author: Clement RACINET

Scans ``abb_rws_client/``, generates one ``.md`` file per module using
the ``:::`` mkdocstrings directive, then injects the ``nav`` block into
``mkdocs.yml`` between the AUTOGEN marker tags.
"""

from __future__ import annotations

import fnmatch
from pathlib import Path

from scripts.doc.config import DocConfig

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_excluded(name: str, cfg: DocConfig, is_file: bool = False) -> bool:
    """Return whether a directory or file name should be skipped.

    Args:
        name: Entry name to test (no path component).
        cfg: Documentation pipeline configuration.
        is_file: If ``True``, use fnmatch pattern matching for files.

    Returns:
        ``True`` if the entry must be excluded from the scan.
    """
    if not is_file:
        return name in cfg.exclude_dirs
    return any(fnmatch.fnmatch(name, pat) for pat in cfg.exclude_files)


def _human_title(name: str) -> str:
    """Convert a file or directory name into a human-readable title.

    Args:
        name: Raw name (e.g. ``"my_module"``).

    Returns:
        Formatted title (e.g. ``"My Module"``).
    """
    return name.replace("_", " ").replace("-", " ").strip().title()


def _module_path(py_file: Path, project_root: Path) -> str:
    """Convert a file path to a dotted Python module path.

    Args:
        py_file: Absolute path to the ``.py`` file.
        project_root: Absolute path to the project root.

    Returns:
        Dotted module path (e.g. ``"abb_rws_client_python_rw6.rws.rapid.execution"``).
    """
    rel = py_file.relative_to(project_root).with_suffix("")
    return ".".join(rel.parts)


# ---------------------------------------------------------------------------
# Recursive walk
# ---------------------------------------------------------------------------


def _walk(
    src: Path,
    dst: Path,
    indent: int,
    cfg: DocConfig,
) -> list[str]:
    """Recursively walk a source directory and generate Markdown pages.

    For each non-excluded ``.py`` file, generates a ``.md`` file containing
    the ``:::`` mkdocstrings directive. Optionally prepends/appends the
    content of ``<module>.pre.md`` and ``<module>.post.md`` if present.
    Sub-directories that contain no modules are omitted from the nav.

    Args:
        src: Python source directory to walk.
        dst: Destination directory for generated Markdown files.
        indent: Current YAML indentation level (2 spaces per level).
        cfg: Documentation pipeline configuration.

    Returns:
        List of YAML navigation lines for this level.
    """
    dst.mkdir(parents=True, exist_ok=True)
    pad = "  " * indent
    lines: list[str] = []

    # --- Python modules ---
    py_files = sorted(
        [
            p
            for p in src.iterdir()
            if p.is_file()
            and p.suffix == ".py"
            and not _is_excluded(p.name, cfg, is_file=True)
        ],
        key=lambda p: p.name.lower(),
    )
    for py in py_files:
        module = _module_path(py, cfg.project_root)
        title = _human_title(py.stem)
        dst_md = dst / f"{py.stem}.md"
        content = f"# {title}\n\n::: {module}\n"

        pre = src / f"{py.stem}.pre.md"
        post = src / f"{py.stem}.post.md"
        if pre.exists():
            content = pre.read_text(encoding="utf-8") + "\n\n" + content
        if post.exists():
            content = content + "\n\n" + post.read_text(encoding="utf-8")

        dst_md.write_text(content, encoding="utf-8")
        rel = dst_md.relative_to(cfg.docs_src_dir).as_posix()
        lines.append(f"{pad}- {title}: {rel}")
        print(f"  ✓ {module} → {rel}")

    # --- Recursive sub-directories ---
    subdirs = sorted(
        [p for p in src.iterdir() if p.is_dir() and not _is_excluded(p.name, cfg)],
        key=lambda p: p.name.lower(),
    )
    for sub in subdirs:
        sub_lines = _walk(sub, dst / sub.name, indent + 1, cfg)
        if sub_lines:  # skip directory if it contains no modules
            lines.append(f"{pad}- {_human_title(sub.name)}:")
            lines.extend(sub_lines)

    return lines


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def generate_api_docs(cfg: DocConfig) -> str:
    """Generate API Markdown pages and return the YAML nav block.

    Args:
        cfg: Documentation pipeline configuration.

    Returns:
        YAML navigation block with no base indentation (indent=0).
    """
    print(f"📁 Generating API pages → {cfg.docs_api_dir}")
    cfg.docs_api_dir.mkdir(parents=True, exist_ok=True)

    nav_lines: list[str] = []

    for pkg in cfg.packages_to_scan:
        src_root = cfg.project_root / pkg
        dst_root = cfg.docs_api_dir / pkg
        pkg_lines = _walk(src_root, dst_root, indent=1, cfg=cfg)
        if pkg_lines:
            nav_lines.append(f"- {_human_title(pkg)}:")
            nav_lines.extend(pkg_lines)

    return "\n".join(nav_lines)


# ---------------------------------------------------------------------------
# mkdocs.yml injection
# ---------------------------------------------------------------------------


def update_mkdocs_nav(cfg: DocConfig, nav_block: str) -> None:
    """Inject the nav block into ``mkdocs.yml`` between the AUTOGEN tags.

    Detects the indentation of the opening tag and applies it to every
    injected line to preserve the YAML hierarchy.

    Args:
        cfg: Documentation pipeline configuration.
        nav_block: YAML block with no base indentation.

    Raises:
        ValueError: If the AUTOGEN tags are missing from ``mkdocs.yml``.
    """
    lines = cfg.mkdocs_path.read_text(encoding="utf-8").splitlines()

    start_i = end_i = None
    balise_indent = ""
    for i, line in enumerate(lines):
        if cfg.balise_api_debut in line:
            start_i = i
            # Indentation = leading whitespace of the tag line
            balise_indent = " " * (len(line) - len(line.lstrip()))
        if cfg.balise_api_fin in line:
            end_i = i
            break

    if start_i is None or end_i is None:
        raise ValueError(
            f"AUTOGEN tags not found in {cfg.mkdocs_path}.\n"
            f"Expected: {cfg.balise_api_debut} … {cfg.balise_api_fin}"
        )

    # Apply the tag indentation to every non-empty line
    indented_lines = [
        balise_indent + line if line.strip() else "" for line in nav_block.splitlines()
    ]

    new_lines = lines[: start_i + 1] + indented_lines + lines[end_i:]
    cfg.mkdocs_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    print("mkdocs.yml updated.")
