"""Génération automatique des pages API MkDocs pour TrajCenter.

Scan le package `trajcenter/`, génère un `.md` par module avec
directive `:::` mkdocstrings, puis injecte le bloc `nav` dans
`mkdocs.yml` entre les balises AUTOGEN.
"""
from __future__ import annotations

import fnmatch
from pathlib import Path

from scripts.doc.config import DocConfig, build_config


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_excluded(name: str, cfg: DocConfig, is_file: bool = False) -> bool:
    """Indique si un nom de dossier ou fichier doit être ignoré.

    Args:
        name: Nom de l'entrée à tester (sans chemin).
        cfg: Configuration du pipeline documentaire.
        is_file: Si True, utilise le matching fnmatch pour les fichiers.

    Returns:
        True si l'entrée doit être ignorée.
    """
    if not is_file:
        return name in cfg.exclude_dirs
    return any(fnmatch.fnmatch(name, pat) for pat in cfg.exclude_files)


def _human_title(name: str) -> str:
    """Transforme un nom de fichier/dossier en titre lisible.

    Args:
        name: Nom brut (ex. ``"my_module"``).

    Returns:
        Titre formaté (ex. ``"My Module"``).
    """
    return name.replace("_", " ").replace("-", " ").strip().title()


def _module_path(py_file: Path, project_root: Path) -> str:
    """Convertit un chemin fichier en chemin de module Python pointé.

    Args:
        py_file: Chemin absolu vers le fichier ``.py``.
        project_root: Racine du projet.

    Returns:
        Chemin de module pointé (ex. ``"trajcenter.core.trajectory"``).
    """
    rel = py_file.relative_to(project_root).with_suffix("")
    return ".".join(rel.parts)


# ---------------------------------------------------------------------------
# Génération récursive
# ---------------------------------------------------------------------------

def _walk(
    src: Path,
    dst: Path,
    indent: int,
    cfg: DocConfig,
) -> list[str]:
    """Parcourt récursivement un dossier source et génère les pages Markdown.

    Pour chaque fichier ``.py`` non exclu, génère un ``.md`` avec la
    directive ``:::`` mkdocstrings. Injecte optionnellement le contenu
    de ``<module>.pre.md`` et ``<module>.post.md`` si présents.
    Les sous-dossiers vides (sans modules) sont ignorés du nav.

    Args:
        src: Dossier source Python à parcourir.
        dst: Dossier de destination pour les fichiers Markdown générés.
        indent: Niveau d'indentation YAML courant (2 espaces par niveau).
        cfg: Configuration du pipeline documentaire.

    Returns:
        Liste de lignes YAML de navigation pour ce niveau.
    """
    dst.mkdir(parents=True, exist_ok=True)
    pad = "  " * indent
    lines: list[str] = []

    # --- Modules Python ---
    py_files = sorted(
        [
            p for p in src.iterdir()
            if p.is_file() and p.suffix == ".py"
            and not _is_excluded(p.name, cfg, is_file=True)
        ],
        key=lambda p: p.name.lower(),
    )
    for py in py_files:
        module  = _module_path(py, cfg.project_root)
        title   = _human_title(py.stem)
        dst_md  = dst / f"{py.stem}.md"
        content = f"# {title}\n\n::: {module}\n"

        pre  = src / f"{py.stem}.pre.md"
        post = src / f"{py.stem}.post.md"
        if pre.exists():
            content = pre.read_text(encoding="utf-8") + "\n\n" + content
        if post.exists():
            content = content + "\n\n" + post.read_text(encoding="utf-8")

        dst_md.write_text(content, encoding="utf-8")
        rel = dst_md.relative_to(cfg.docs_src_dir).as_posix()
        lines.append(f"{pad}- {title}: {rel}")
        print(f"  ✅ {module} → {rel}")

    # --- Sous-dossiers récursifs ---
    subdirs = sorted(
        [p for p in src.iterdir() if p.is_dir() and not _is_excluded(p.name, cfg)],
        key=lambda p: p.name.lower(),
    )
    for sub in subdirs:
        sub_lines = _walk(sub, dst / sub.name, indent + 1, cfg)
        if sub_lines:  # dossier ignoré s'il ne contient aucun module
            lines.append(f"{pad}- {_human_title(sub.name)}:")
            lines.extend(sub_lines)

    return lines


# ---------------------------------------------------------------------------
# Point d'entrée principal
# ---------------------------------------------------------------------------

def generate_api_docs(cfg: DocConfig) -> str:
    """Génère les pages Markdown API et retourne le bloc nav YAML.

    Args:
        cfg: Configuration du pipeline documentaire.

    Returns:
        Bloc YAML de navigation sans indentation de base (indent=0).
    """
    print(f"📁 Génération API → {cfg.docs_api_dir}")
    cfg.docs_api_dir.mkdir(parents=True, exist_ok=True)

    nav_lines: list[str] = []

    for pkg in cfg.packages_to_scan:
        src_root = cfg.project_root / pkg
        dst_root = cfg.docs_api_dir / pkg
        pkg_lines = _walk(src_root, dst_root, indent=1, cfg=cfg)  # ← indent=1
        if pkg_lines:
            nav_lines.append(f"- {_human_title(pkg)}:")           # ← 0 espace
            nav_lines.extend(pkg_lines)

    return "\n".join(nav_lines)

# ---------------------------------------------------------------------------
# Injection mkdocs.yml
# ---------------------------------------------------------------------------

def update_mkdocs_nav(cfg: DocConfig, nav_block: str) -> None:
    """Injecte le bloc nav dans mkdocs.yml entre les balises AUTOGEN.

    Détecte l'indentation de la balise de début et l'applique à chaque
    ligne du bloc injecté pour respecter la hiérarchie YAML.

    Args:
        cfg: Configuration du pipeline documentaire.
        nav_block: Bloc YAML sans indentation de base.

    Raises:
        ValueError: Si les balises AUTOGEN sont absentes de mkdocs.yml.
    """
    lines = cfg.mkdocs_path.read_text(encoding="utf-8").splitlines()

    start_i = end_i = None
    balise_indent = "" 
    for i, line in enumerate(lines):
        if cfg.balise_api_debut in line:
            start_i = i
            # Indentation = celle de la balise (ex: "    # ---" → "    ")
            balise_indent = " " * (len(line) - len(line.lstrip()))
        if cfg.balise_api_fin in line:
            end_i = i
            break

    if start_i is None or end_i is None:
        raise ValueError(
            f"Balises AUTOGEN introuvables dans {cfg.mkdocs_path}.\n"
            f"Attendu : {cfg.balise_api_debut} … {cfg.balise_api_fin}"
        )

    # Applique l'indentation de la balise à chaque ligne non vide
    indented_lines = [
        balise_indent + l if l.strip() else ""
        for l in nav_block.splitlines()
    ]

    new_lines = (
        lines[:start_i + 1]
        + indented_lines
        + lines[end_i:]
    )
    cfg.mkdocs_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    print("📝 mkdocs.yml mis à jour.")
