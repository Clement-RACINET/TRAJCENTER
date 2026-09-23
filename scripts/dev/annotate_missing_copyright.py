#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 C. RACINET
#
# SPDX-License-Identifier: X11

"""Annote les fichiers non couverts par REUSE ou par les règles Git."""

from __future__ import annotations

import fnmatch
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any

try:
    from reuse.project import Project
except ImportError:
    err_msg = (
        "Erreur : la bibliothèque 'reuse' n'est pas installée "
        "dans l'environnement courant.\n"
        "Installez-la via 'pip install reuse' ou activez "
        "votre environnement virtuel."
    )
    print(err_msg, file=sys.stderr)
    sys.exit(1)


COPYRIGHT_HOLDER = "C. RACINET"
LICENSE_ID = "X11"
YEAR = "2026"

# Limite volontaire pour éviter les commandes trop longues sous Windows.
ANNOTATION_BATCH_SIZE = 100


def find_project_root(start: Path) -> Path:
    """Trouve la racine Git du projet.

    Git constitue la source de vérité principale. Si Git n'est pas disponible
    ou si le script n'est pas exécuté dans un dépôt Git, la fonction recherche
    un dossier parent contenant à la fois reuse.toml et .gitignore.
    """
    start = start.resolve()

    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(start),
                "rev-parse",
                "--show-toplevel",
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError:
        result = None

    if result is not None and result.returncode == 0:
        root_text = result.stdout.strip()

        if root_text:
            return Path(root_text).resolve()

    # Solution de repli si Git n'est pas installé ou si le dépôt
    # n'est pas correctement initialisé.
    for candidate in (start, *start.parents):
        if (candidate / ".gitignore").is_file() and (
            candidate / "reuse.toml"
        ).is_file():
            return candidate

    raise RuntimeError(
        "Impossible de déterminer la racine du projet.\n"
        "Le script doit être exécuté dans un dépôt Git ou sous un dossier "
        "contenant .gitignore et reuse.toml."
    )


def load_reuse_toml(toml_path: Path) -> dict[str, Any]:
    """Charge et valide reuse.toml.

    Une erreur explicite est levée si le fichier TOML est invalide.
    """
    if not toml_path.is_file():
        raise FileNotFoundError(f"Le fichier REUSE est introuvable : {toml_path}")

    try:
        with toml_path.open("rb") as file:
            data = tomllib.load(file)
    except tomllib.TOMLDecodeError as exc:
        raise RuntimeError(
            f"Le fichier {toml_path} contient une erreur TOML :\n{exc}"
        ) from exc
    except OSError as exc:
        raise RuntimeError(
            f"Impossible de lire le fichier {toml_path} : {exc}"
        ) from exc

    if not isinstance(data, dict):
        raise TypeError(f"Le contenu de {toml_path} n'est pas une table TOML valide.")

    return data


def get_toml_annotated_patterns(data: dict[str, Any]) -> list[str]:
    """Extrait les chemins couverts par les annotations de reuse.toml."""
    patterns: list[str] = []
    annotations = data.get("annotations", [])

    if not isinstance(annotations, list):
        return patterns

    for entry in annotations:
        if not isinstance(entry, dict):
            continue

        path_value = entry.get("path")

        if isinstance(path_value, str):
            patterns.append(path_value)
            continue

        if isinstance(path_value, list):
            patterns.extend(path for path in path_value if isinstance(path, str))

    return patterns


def is_path_matching_patterns(
    relative_posix_path: str,
    patterns: list[str],
) -> bool:
    """Vérifie si un chemin correspond à une annotation de reuse.toml."""
    relative_posix_path = relative_posix_path.removeprefix("./")

    for pattern in patterns:
        normalized_pattern = pattern.replace("\\", "/")
        normalized_pattern = normalized_pattern.removeprefix("./")
        normalized_pattern = normalized_pattern.rstrip("/")

        if not normalized_pattern:
            continue

        # Correspondance exacte ou via un glob.
        if fnmatch.fnmatch(relative_posix_path, normalized_pattern):
            return True

        # Gestion explicite des motifs récursifs du type "directory/**".
        if normalized_pattern.endswith("/**"):
            prefix = normalized_pattern[:-3].rstrip("/")

            if relative_posix_path == prefix or relative_posix_path.startswith(
                f"{prefix}/"
            ):
                return True

        # Une annotation visant un dossier couvre son contenu.
        if not any(
            character in normalized_pattern for character in ("*", "?", "[")
        ) and relative_posix_path.startswith(f"{normalized_pattern}/"):
            return True

    return False


def get_git_ignored_paths(
    root_dir: Path,
    relative_paths: list[str],
) -> set[str]:
    """Demande à Git quels chemins sont couverts par les règles d'exclusion.

    L'option --no-index permet d'appliquer les règles même à un fichier déjà
    suivi par Git. Cela correspond au comportement souhaité ici : si un chemin
    correspond au .gitignore, le script REUSE ne le traite pas.
    """
    if not relative_paths:
        return set()

    git_input = "\0".join(relative_paths) + "\0"

    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(root_dir),
                "check-ignore",
                "--no-index",
                "--stdin",
                "-z",
            ],
            input=git_input.encode("utf-8"),
            capture_output=True,
            check=False,
        )
    except FileNotFoundError:
        print(
            "[-] Avertissement : Git n'est pas disponible. "
            "Les règles de .gitignore ne seront pas appliquées.",
            file=sys.stderr,
        )
        return set()

    # git check-ignore retourne :
    # - 0 lorsqu'au moins un chemin correspond ;
    # - 1 lorsqu'aucun chemin ne correspond ;
    # - une autre valeur en cas d'erreur réelle.
    if result.returncode not in (0, 1):
        stderr = result.stderr.decode(
            "utf-8",
            errors="replace",
        ).strip()

        print(
            "[-] Avertissement : impossible d'analyser les règles Git."
            + (f"\n{stderr}" if stderr else ""),
            file=sys.stderr,
        )
        return set()

    if not result.stdout:
        return set()

    output = result.stdout.decode(
        "utf-8",
        errors="surrogateescape",
    )

    return {path.replace("\\", "/") for path in output.split("\0") if path}


def has_reuse_information(
    project: Project,
    file_path: Path,
) -> bool:
    """Indique si un fichier possède déjà des informations SPDX."""
    info_getter = getattr(project, "reuse_info_of", None)

    if not callable(info_getter):
        info_getter = getattr(project, "spdx_info_of", None)

    if not callable(info_getter):
        return False

    try:
        info = info_getter(file_path)
    except Exception as exc:  # noqa: BLE001
        print(
            f"[-] Avertissement : analyse REUSE impossible pour {file_path}: {exc}",
            file=sys.stderr,
        )
        return False

    if info is None:
        return False

    spdx_expressions = getattr(info, "spdx_expressions", None)

    if spdx_expressions:
        return True

    # Compatibilité avec certaines versions ou structures de REUSE.
    copyright_lines = getattr(info, "copyright_lines", None)
    license_expressions = getattr(info, "license_expressions", None)

    return bool(copyright_lines or license_expressions)


def find_files_to_annotate(root_dir: Path) -> list[str]:
    """Retourne les fichiers qui nécessitent une annotation SPDX."""
    reuse_toml_path = root_dir / "reuse.toml"

    # Valider le fichier avant que REUSE tente lui-même de le charger.
    toml_data = load_reuse_toml(reuse_toml_path)
    toml_patterns = get_toml_annotated_patterns(toml_data)

    try:
        project = Project.from_directory(root_dir)
    except Exception as exc:
        raise RuntimeError(
            f"REUSE n'a pas pu initialiser le projet.\nDétail : {exc}"
        ) from exc

    project_files: list[tuple[Path, str]] = []

    for file_path_value in project.all_files():
        file_path = Path(file_path_value)

        relative_path = project.relative_from_root(file_path)
        relative_posix = relative_path.as_posix()

        project_files.append((file_path, relative_posix))

    all_relative_paths = [relative_path for _, relative_path in project_files]

    git_ignored_paths = get_git_ignored_paths(
        root_dir,
        all_relative_paths,
    )

    files_to_annotate: list[str] = []

    for file_path, relative_posix in project_files:
        # 1. Ignorer les chemins couverts par .gitignore.
        if relative_posix in git_ignored_paths:
            continue

        # 2. Ignorer les chemins couverts par reuse.toml.
        if is_path_matching_patterns(
            relative_posix,
            toml_patterns,
        ):
            continue

        # 3. Ignorer les fichiers qui possèdent déjà des informations SPDX,
        # directement ou par l'intermédiaire d'un fichier .license.
        if has_reuse_information(project, file_path):
            continue

        files_to_annotate.append(relative_posix)

    return sorted(files_to_annotate)


def split_into_batches(
    paths: list[str],
    batch_size: int,
) -> list[list[str]]:
    """Découpe une liste de chemins en groupes de taille limitée."""
    return [
        paths[index : index + batch_size] for index in range(0, len(paths), batch_size)
    ]


def annotate_files(
    root_dir: Path,
    targets: list[str],
) -> int:
    """Exécute reuse annotate sur les fichiers indiqués."""
    batches = split_into_batches(
        targets,
        ANNOTATION_BATCH_SIZE,
    )

    total_batches = len(batches)

    for batch_number, batch in enumerate(batches, start=1):
        if total_batches > 1:
            print(
                f"\n[*] Traitement du groupe "
                f"{batch_number}/{total_batches} "
                f"({len(batch)} fichier(s))..."
            )

        command = [
            "reuse",
            "annotate",
            "--copyright",
            COPYRIGHT_HOLDER,
            "--license",
            LICENSE_ID,
            "--year",
            YEAR,
            "--skip-unrecognised",
            *batch,
        ]

        try:
            result = subprocess.run(
                command,
                cwd=root_dir,
                check=False,
            )
        except FileNotFoundError:
            print(
                "[-] Erreur : la commande 'reuse' est introuvable.",
                file=sys.stderr,
            )
            return 127

        if result.returncode != 0:
            return result.returncode

    return 0


def main() -> None:
    """Point d'entrée principal du script."""
    script_dir = Path(__file__).resolve().parent

    try:
        root_dir = find_project_root(script_dir)
    except RuntimeError as exc:
        print(f"[-] Erreur : {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"[*] Racine Git détectée : {root_dir}")

    gitignore_path = root_dir / ".gitignore"

    if gitignore_path.is_file():
        print(f"[*] Règles Git utilisées : {gitignore_path}")
    else:
        print(
            "[-] Avertissement : aucun .gitignore à la racine du dépôt.",
            file=sys.stderr,
        )

    try:
        targets = find_files_to_annotate(root_dir)
    except (FileNotFoundError, RuntimeError) as exc:
        print(f"[-] Erreur : {exc}", file=sys.stderr)
        sys.exit(1)

    if not targets:
        print(
            "[+] Aucun fichier à annoter. "
            "Tous les fichiers sont ignorés, couverts ou conformes."
        )
        return

    print(f"[*] {len(targets)} fichier(s) à annoter détecté(s) :")

    for target in targets:
        print(f"  - {target}")

    print("\n[*] Application des annotations SPDX...")

    return_code = annotate_files(root_dir, targets)

    if return_code == 0:
        print(
            "\n[+] Opération terminée avec succès. Vous pouvez exécuter 'reuse lint'."
        )
        return

    print(
        f"\n[-] Erreur lors de l'annotation (code {return_code}).",
        file=sys.stderr,
    )
    sys.exit(return_code)


if __name__ == "__main__":
    main()
