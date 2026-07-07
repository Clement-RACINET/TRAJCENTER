# trajcenter/converter/base.py

"""
Classe abstraite commune à tous les convertisseurs TrajCenter.

Un convertisseur transforme un fichier source (RAPID ``.mod``, Excel, APT…)
en objet :class:`~trajcenter.core.trajectory.Trajectory` **toujours complet**,
prêt à être sauvegardé en ``.trajcenter``.

Principe d'autocomplétion
--------------------------
La méthode :meth:`BaseConverter._autocomplete` garantit que toutes les
colonnes de :data:`~trajcenter.core.trajectory.CONVERTER_COLUMNS` sont
présentes dans le DataFrame avant la construction de la trajectoire.
Les colonnes manquantes sont remplies avec les valeurs de
:class:`~trajcenter.converter.defaults.ConversionDefaults` et leurs noms
sont retournés pour être stockés dans
:attr:`~trajcenter.core.trajectory.TrajectoryMeta.autocompleted`.

Les colonnes ``eax_*`` ne sont **jamais** autocomplétées — leur absence
signifie que l'axe n'existe pas sur ce robot.

Example:
    ::

        from pathlib import Path
        from trajcenter.converter.mod_converter import ModConverter
        from trajcenter.converter.defaults import ConversionDefaults

        converter = ModConverter()
        traj = converter.convert(Path("trajectory_files/soudure.mod"))
        traj.save("trajectory_store/soudure.trajcenter")

        # Avec des defaults personnalisés
        converter_slow = ModConverter(
            defaults=ConversionDefaults(speed="v100", zone="fine")
        )
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

import pandas as pd

from trajcenter.converter.defaults import ConversionDefaults
from trajcenter.core.trajectory import CONVERTER_COLUMNS, CONFDATA_COLUMNS, Trajectory


class BaseConverter(ABC):
    """Convertisseur de fichier source vers :class:`~trajcenter.core.trajectory.Trajectory`.

    Toutes les sous-classes doivent implémenter :meth:`convert`.
    Les méthodes utilitaires :meth:`_autocomplete` et
    :meth:`convert_and_save` sont fournies par cette classe de base.

    Attributes:
        defaults: Valeurs par défaut utilisées pour l'autocomplétion.

    Example:
        ::

            from trajcenter.converter.mod_converter import ModConverter
            from trajcenter.converter.defaults import ConversionDefaults

            traj = ModConverter(
                defaults=ConversionDefaults(speed="v200", zone="fine")
            ).convert(Path("trajectory_files/soudure.mod"))
    """

    def __init__(self, defaults: ConversionDefaults | None = None) -> None:
        """Initialise le convertisseur avec des valeurs par défaut optionnelles.

        Args:
            defaults: Valeurs par défaut pour l'autocomplétion.
                      Si ``None``, :class:`~trajcenter.converter.defaults.ConversionDefaults`
                      est instancié avec ses propres valeurs par défaut.
        """
        self.defaults: ConversionDefaults = defaults or ConversionDefaults()

    @abstractmethod
    def convert(self, source: Path) -> Trajectory:
        """Convertit un fichier source en objet :class:`~trajcenter.core.trajectory.Trajectory`.

        La trajectoire retournée doit être **complète** : toutes les colonnes
        de :data:`~trajcenter.core.trajectory.CONVERTER_COLUMNS` doivent
        être présentes (garantie par l'appel à :meth:`_autocomplete`).

        Args:
            source: Chemin vers le fichier source à convertir.

        Returns:
            Objet :class:`~trajcenter.core.trajectory.Trajectory` valide
            et complet, non sauvegardé.

        Raises:
            FileNotFoundError: Si le fichier source n'existe pas.
            ValueError:        Si le fichier est invalide ou mal formé.
        """
        ...

    # ------------------------------------------------------------------
    # Autocomplétion
    # ------------------------------------------------------------------

    def _autocomplete(
        self,
        df: pd.DataFrame,
        tools: list[str],
        wobjs: list[str],
    ) -> tuple[pd.DataFrame, list[str]]:
        """Complète les colonnes manquantes avec les valeurs de ``self.defaults``.

        Parcourt :data:`~trajcenter.core.trajectory.CONVERTER_COLUMNS` et
        ajoute chaque colonne absente avec la valeur correspondante dans
        :attr:`defaults`. Les colonnes ``eax_*`` ne sont jamais touchées.

        Si ``tools`` est vide, un tool par défaut (``defaults.tool``) est
        ajouté à la liste et ``tool_index`` est autocomplété à ``0``.
        Même logique pour ``wobjs`` / ``wobj_index``.

        Args:
            df:    DataFrame partiellement rempli (après parsing de la source).
            tools: Liste des noms de tools construite par le convertisseur.
                   Modifiée **en place** si vide.
            wobjs: Liste des noms de wobjs construite par le convertisseur.
                   Modifiée **en place** si vide.

        Returns:
            Tuple ``(df_complet, autocompleted)`` où :

            - ``df_complet``    : DataFrame avec toutes les colonnes présentes.
            - ``autocompleted`` : liste des noms de colonnes qui ont été
                                  inférées (non présentes dans la source).
        """
        df = df.copy()
        autocompleted: list[str] = []
        n = len(df)

        # --- Tables tools / wobjs vides → default ---
        if not tools:
            tools.append(self.defaults.tool)
        if not wobjs:
            wobjs.append(self.defaults.wobj)

        # --- Mapping colonne → valeur de remplissage (str uniquement) ---
        # Les confdata sont gérés séparément (Int8 nullable)
        _fill_str: dict[str, str] = {
            "move_type": self.defaults.move_type,
            "speed":     self.defaults.speed,
            "zone":      self.defaults.zone,
        }
        _fill_int: dict[str, int] = {
            "tool_index": 0,
            "wobj_index": 0,
        }

        for col in CONVERTER_COLUMNS:
            if col in df.columns:
                continue

            if col in CONFDATA_COLUMNS:
                # Int8 nullable — pd.Series est le seul chemin propre
                df[col] = pd.Series(
                    [self.defaults.cf_value] * n,
                    dtype=pd.Int8Dtype(),
                )
                autocompleted.append(col)

            elif col in _fill_str:
                df[col] = _fill_str[col]
                autocompleted.append(col)

            elif col in _fill_int:
                df[col] = _fill_int[col]
                autocompleted.append(col)

        return df, autocompleted

    # ------------------------------------------------------------------
    # Conversion + sauvegarde
    # ------------------------------------------------------------------

    def convert_and_save(
        self,
        source: Path,
        dest_dir: Path,
        stem: str | None = None,
    ) -> Path:
        """Convertit un fichier source et sauvegarde le résultat en ``.trajcenter``.

        Args:
            source:   Chemin du fichier source.
            dest_dir: Dossier de destination (créé si absent).
            stem:     Nom du fichier sans extension.
                      Par défaut : même stem que le fichier source.

        Returns:
            Chemin absolu du fichier ``.trajcenter`` créé.

        Example:
            ::

                path = ModConverter().convert_and_save(
                    source=Path("trajectory_files/soudure.mod"),
                    dest_dir=Path("trajectory_store"),
                )
                # → trajectory_store/soudure.trajcenter
        """
        traj = self.convert(Path(source))
        name = stem or Path(source).stem
        dest = Path(dest_dir)
        dest.mkdir(parents=True, exist_ok=True)
        return traj.save(dest / f"{name}.trajcenter")
