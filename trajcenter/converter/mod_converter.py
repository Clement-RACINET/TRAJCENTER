# trajcenter/converter/mod_converter.py

"""
Convertisseur de modules RAPID ABB (``.mod``) vers le format ``.trajcenter``.

Un fichier ``.mod`` RAPID contient une procédure avec des instructions
``MoveL``, ``MoveJ`` ou ``MoveC``. Chaque instruction encode un robtarget
inline avec ses paramètres de mouvement.

Format d'une ligne Move attendu
---------------------------------
::

    MoveL [[x,y,z],[q1,q2,q3,q4],[cf1,cf4,cf6,cfx],[eax_a,…,eax_f]],
          vitesse, zone, ToolName \\wobj:=WobjName ;

Règles de parsing
------------------
- Seules les lignes dont le premier token commence par ``MoveL``, ``MoveJ``
  ou ``MoveC`` (insensible à la casse) sont traitées.
- Les lignes physiques sont fusionnées sur le délimiteur ``;`` avant parsing,
  ce qui gère les robtargets formatés sur plusieurs lignes.
- La vitesse est un **nom de variable** RAPID (ex. ``vitesse``) dans les
  fichiers générés par CATIA. Elle n'est stockée que si c'est un littéral
  RAPID reconnu (ex. ``v500``). Sinon la colonne ``speed`` est autocomplétée
  depuis :class:`~trajcenter.converter.defaults.ConversionDefaults`.
- Les axes externes à ``9E9`` sont considérés **inactifs** et ne sont pas
  stockés dans le DataFrame (colonne ``eax_*`` absente = axe inexistant).
- Les tools et wobjs sont dédupliqués et indexés dans les tables
  ``Trajectory.tools`` et ``Trajectory.wobjs``.
- Toutes les colonnes de
  :data:`~trajcenter.core.trajectory.CONVERTER_COLUMNS` sont garanties
  présentes en sortie via :meth:`~trajcenter.converter.base.BaseConverter._autocomplete`.

Example:
    ::

        from pathlib import Path
        from trajcenter.converter.mod_converter import ModConverter
        from trajcenter.converter.defaults import ConversionDefaults

        # Conversion avec defaults standard
        traj = ModConverter().convert(Path("trajectory_files/sphere05mm.mod"))
        print(traj)
        # Trajectory(name='sphere05mm', points=17, tools=1, wobjs=1, eax=none, complete=True)

        # Conversion avec vitesse de secours personnalisée
        traj = ModConverter(
            defaults=ConversionDefaults(speed="v200")
        ).convert(Path("trajectory_files/sphere05mm.mod"))
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from trajcenter.converter.base import BaseConverter
from trajcenter.converter.defaults import ConversionDefaults
from trajcenter.core.trajectory import MoveType, SourceFormat, Trajectory, TrajectoryMeta


# ---------------------------------------------------------------------------
# Constantes & regex
# ---------------------------------------------------------------------------

#: Capture le type de mouvement en début de ligne (insensible à la casse).
_RE_MOVE_TYPE: re.Pattern[str] = re.compile(
    r"^\s*(MoveL|MoveJ|MoveC)\b", re.IGNORECASE
)

#: Capture le contenu brut du robtarget :
#: ``[[x,y,z],[q1,q2,q3,q4],[cf1,cf4,cf6,cfx],[eax_a,…,eax_f]]``
#: Le groupe 1 contient les quatre sous-listes sans les crochets externes.
_RE_ROBTARGET: re.Pattern[str] = re.compile(
    r"\[\s*"           # [ ouvrant du robtarget
    r"(\[.*?\]"        # [x,y,z]
    r"\s*,\s*\[.*?\]"  # [q1,q2,q3,q4]
    r"\s*,\s*\[.*?\]"  # [cf1,cf4,cf6,cfx]
    r"\s*,\s*\[.*?\])" # [eax_a…eax_f]
    r"\s*\]",          # ] fermant du robtarget
    re.DOTALL,
)

#: Capture vitesse, zone, tool et wobj après le dernier ]] du robtarget.
#: On cherche la séquence ]],  qui clôt le robtarget avant les paramètres.
_RE_PARAMS: re.Pattern[str] = re.compile(
    r"\]\]\s*,"                                        # ]] fermant le robtarget
    r"\s*(?P<speed>\S+?)\s*,"                          # vitesse
    r"\s*(?P<zone>fine|z\w*)\s*,"                      # zone (fine ou z0, z10…)
    r"\s*(?P<tool>\w+)"                                # tool
    r"(?:\s*\\wobj\s*:=\s*(?P<wobj>\w+))?",            # \wobj:=WobjName (optionnel)
    re.IGNORECASE,
)

#: Valeur sentinelle ABB pour un axe externe inactif.
_EAX_INACTIVE: float = 9e9

#: Seuil en dessous duquel une valeur eax est considérée active.
#: (9E9 peut légèrement dériver selon le formateur numérique du .mod)
_EAX_ACTIVE_THRESHOLD: float = 1e8

#: Noms des colonnes axes externes dans l'ordre du robtarget RAPID.
_EAX_COLS: list[str] = ["eax_a", "eax_b", "eax_c", "eax_d", "eax_e", "eax_f"]

#: Mapping type de mouvement (lowercase) → :class:`~trajcenter.core.trajectory.MoveType`.
_MOVE_TYPE_MAP: dict[str, MoveType] = {
    "movel": MoveType.MOVE_L,
    "movej": MoveType.MOVE_J,
    "movec": MoveType.MOVE_C,
}

#: Préfixe des vitesses RAPID littérales reconnues (ex. ``v500``, ``v1000``).
_RAPID_SPEED_PREFIX: str = "v"


# ---------------------------------------------------------------------------
# Convertisseur
# ---------------------------------------------------------------------------


class ModConverter(BaseConverter):
    """Convertisseur de modules RAPID ABB (``.mod``) vers :class:`~trajcenter.core.trajectory.Trajectory`.

    Parse toutes les instructions ``MoveL`` / ``MoveJ`` / ``MoveC``
    d'un fichier ``.mod`` et construit un objet
    :class:`~trajcenter.core.trajectory.Trajectory` complet avec :

    - les tables de tools et wobjs dédupliquées ;
    - toutes les colonnes de
      :data:`~trajcenter.core.trajectory.CONVERTER_COLUMNS` garanties
      présentes (autocomplétion via :attr:`~trajcenter.converter.base.BaseConverter.defaults`).

    Attributes:
        defaults: Valeurs par défaut pour l'autocomplétion
                  (héritées de :class:`~trajcenter.converter.base.BaseConverter`).

    Example:
        ::

            from pathlib import Path
            from trajcenter.converter.mod_converter import ModConverter

            traj = ModConverter().convert(Path("trajectory_files/sphere05mm.mod"))
            traj.save("trajectory_store/sphere05mm.trajcenter")
    """

    def __init__(self, defaults: ConversionDefaults | None = None) -> None:
        """Initialise le convertisseur RAPID.

        Args:
            defaults: Valeurs par défaut pour l'autocomplétion.
                      Si ``None``, :class:`~trajcenter.converter.defaults.ConversionDefaults`
                      est instancié avec ses valeurs standard.
        """
        super().__init__(defaults)

    def convert(self, source: Path) -> Trajectory:
        """Convertit un fichier ``.mod`` RAPID en :class:`~trajcenter.core.trajectory.Trajectory`.

        Args:
            source: Chemin vers le fichier ``.mod`` à convertir.

        Returns:
            Objet :class:`~trajcenter.core.trajectory.Trajectory` valide,
            complet et non sauvegardé.

        Raises:
            FileNotFoundError: Si le fichier source n'existe pas.
            ValueError:        Si aucune instruction Move n'est trouvée,
                               ou si le parsing d'une ligne échoue.
        """
        source = Path(source)
        if not source.exists():
            raise FileNotFoundError(f"Fichier introuvable : {source}")

        raw_lines = source.read_text(encoding="utf-8", errors="replace").splitlines()
        move_lines = self._extract_move_lines(raw_lines)

        if not move_lines:
            raise ValueError(
                f"Aucune instruction MoveL/MoveJ/MoveC trouvée dans : {source}"
            )

        rows, tools, wobjs = self._parse_move_lines(move_lines, source)

        df = pd.DataFrame(rows)
        df, autocompleted = self._autocomplete(df, tools, wobjs)

        meta = TrajectoryMeta(
            name=source.stem,
            source_file=source.name,
            source_format=SourceFormat.RAPID,
            autocompleted=autocompleted,
        )

        return Trajectory(meta=meta, points=df, tools=tools, wobjs=wobjs)

    # ------------------------------------------------------------------
    # Étapes internes
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_move_lines(lines: list[str]) -> list[str]:
        """Filtre et retourne uniquement les lignes contenant une instruction Move.

        Stratégie :
        - On n'accumule dans le buffer QUE les tokens qui appartiennent
          à une instruction Move (déclenchée par MoveL/MoveJ/MoveC).
        - Les lignes RAPID non-Move (MODULE, PROC, VAR…) sont ignorées
          même si elles ne contiennent pas de ";".
        - Le flush du buffer se fait sur ";".

        Args:
            lines: Lignes brutes du fichier ``.mod``.

        Returns:
            Liste d'instructions Move complètes, une par élément.
        """
        result: list[str] = []
        buffer: str = ""
        in_move: bool = False  # True dès qu'on a commencé à accumuler un Move

        for line in lines:
            stripped = line.strip()

            # Lignes vides et commentaires → ignorées dans tous les cas
            if not stripped or stripped.startswith("!"):
                continue

            if not in_move:
                # On n'entre en mode accumulation que si la ligne commence par Move*
                if _RE_MOVE_TYPE.match(stripped):
                    in_move = True
                    buffer = stripped
                # Sinon (MODULE, PROC, VAR, ENDPROC…) → ignoré
                else:
                    continue
            else:
                # On est dans un Move multiligne → on accumule
                buffer = buffer + " " + stripped

            # Flush dès qu'un ";" est présent dans le buffer
            if ";" in buffer:
                instruction, _, remainder = buffer.partition(";")
                instruction = instruction.strip()
                if instruction:
                    result.append(instruction)
                buffer = remainder.strip()
                in_move = bool(buffer) and bool(_RE_MOVE_TYPE.match(buffer))

        return result


    def _parse_move_lines(
        self,
        move_lines: list[str],
        source: Path,
    ) -> tuple[list[dict[str, str | int | float]], list[str], list[str]]:
        """Parse chaque ligne Move et construit les structures de données.

        Args:
            move_lines: Lignes Move fusionnées (une instruction par élément).
            source:     Chemin du fichier source (pour les messages d'erreur).

        Returns:
            Tuple ``(rows, tools, wobjs)`` où :

            - ``rows``  : liste de dicts, un par point.
            - ``tools`` : liste ordonnée des noms de tools (index → nom).
            - ``wobjs`` : liste ordonnée des noms de wobjs (index → nom).

        Raises:
            ValueError: Si le robtarget ou les paramètres d'une ligne
                        ne peuvent pas être parsés.
        """
        rows: list[dict[str, str | int | float]] = []
        tools_index: dict[str, int] = {}
        wobjs_index: dict[str, int] = {}

        for line_no, line in enumerate(move_lines, start=1):
            try:
                row = self._parse_single_move(line, tools_index, wobjs_index)
            except ValueError as exc:
                raise ValueError(
                    f"{source.name} — ligne Move n°{line_no} : {exc}\n"
                    f"  Contenu : {line[:120]!r}"
                ) from exc
            rows.append(row)

        tools = _index_to_list(tools_index)
        wobjs = _index_to_list(wobjs_index)

        return rows, tools, wobjs

    @staticmethod
    def _parse_single_move(
        line: str,
        tools_index: dict[str, int],
        wobjs_index: dict[str, int],
    ) -> dict[str, str | int | float]:
        """Parse une unique ligne Move et retourne un dict de point.

        Met à jour ``tools_index`` et ``wobjs_index`` en place
        si de nouveaux noms sont rencontrés.

        Args:
            line:         Ligne Move complète (une instruction).
            tools_index:  Dict mutable nom → index (mis à jour en place).
            wobjs_index:  Dict mutable nom → index (mis à jour en place).

        Returns:
            Dict avec les clés : ``x, y, z, q1, q2, q3, q4``,
            ``cf1, cf4, cf6, cfx``, ``move_type``, ``zone``,
            ``tool_index``, ``wobj_index``,
            optionnellement ``speed`` (si littéral RAPID reconnu)
            et ``eax_a``…``eax_f`` (axes actifs uniquement).

        Raises:
            ValueError: Si le robtarget ou les paramètres ne peuvent
                        pas être extraits ou convertis.
        """
        # --- Type de mouvement ---
        m_type = _RE_MOVE_TYPE.match(line)
        if not m_type:
            raise ValueError("Type de mouvement introuvable.")
        move_type = _MOVE_TYPE_MAP[m_type.group(1).lower()]

        # --- Robtarget ---
        m_robt = _RE_ROBTARGET.search(line)
        if not m_robt:
            raise ValueError("Robtarget introuvable.")

        # Extraction des 4 sous-listes : [trans],[rot],[conf],[eax]
        sublists = re.findall(r"\[([^\[\]]+)\]", m_robt.group(1))
        if len(sublists) < 4:
            raise ValueError(
                f"Robtarget mal formé — {len(sublists)} sous-liste(s) "
                f"trouvée(s), 4 attendues."
            )

        try:
            trans = [float(v) for v in sublists[0].split(",")]
            rot   = [float(v) for v in sublists[1].split(",")]
            conf  = [int(float(v)) for v in sublists[2].split(",")]
            eax   = [float(v) for v in sublists[3].split(",")]
        except ValueError as exc:
            raise ValueError(
                f"Conversion numérique échouée dans le robtarget : {exc}"
            ) from exc

        if len(trans) != 3:
            raise ValueError(f"trans doit avoir 3 valeurs, reçu {len(trans)}.")
        if len(rot) != 4:
            raise ValueError(f"rot doit avoir 4 valeurs, reçu {len(rot)}.")
        if len(conf) != 4:
            raise ValueError(f"conf doit avoir 4 valeurs, reçu {len(conf)}.")
        if len(eax) != 6:
            raise ValueError(f"eax doit avoir 6 valeurs, reçu {len(eax)}.")

        # --- Paramètres (vitesse, zone, tool, wobj) ---
        m_params = _RE_PARAMS.search(line)
        if not m_params:
            raise ValueError("Paramètres Move (vitesse/zone/tool) introuvables.")

        speed_raw: str = m_params.group("speed")
        zone_raw:  str = m_params.group("zone")
        tool_name: str = m_params.group("tool")
        wobj_name: str = m_params.group("wobj") or "wobj0"

        # --- Index tool / wobj ---
        if tool_name not in tools_index:
            tools_index[tool_name] = len(tools_index)
        if wobj_name not in wobjs_index:
            wobjs_index[wobj_name] = len(wobjs_index)

        # --- Construction du dict point ---
        row: dict[str, str | int | float] = {
            "x":          trans[0],
            "y":          trans[1],
            "z":          trans[2],
            "q1":         rot[0],
            "q2":         rot[1],
            "q3":         rot[2],
            "q4":         rot[3],
            "cf1":        conf[0],
            "cf4":        conf[1],
            "cf6":        conf[2],
            "cfx":        conf[3],
            "move_type":  move_type.value,
            "zone":       zone_raw,
            "tool_index": tools_index[tool_name],
            "wobj_index": wobjs_index[wobj_name],
        }

        # Vitesse : stockée uniquement si c'est un littéral RAPID (v500, v1000…)
        # Sinon absente → autocomplétée depuis defaults dans _autocomplete()
        if (
            speed_raw.lower().startswith(_RAPID_SPEED_PREFIX)
            and speed_raw[1:].isdigit()
        ):
            row["speed"] = speed_raw

        # Axes externes : stockés uniquement si actifs (valeur < seuil 9E9)
        for col, val in zip(_EAX_COLS, eax):
            if abs(val) < _EAX_ACTIVE_THRESHOLD:
                row[col] = val

        return row


# ---------------------------------------------------------------------------
# Utilitaire module-level
# ---------------------------------------------------------------------------


def _index_to_list(index: dict[str, int]) -> list[str]:
    """Convertit un dict ``nom → index`` en liste ordonnée ``index → nom``.

    Args:
        index: Dict mapping nom → position entière (0-based, dense).

    Returns:
        Liste où ``result[i]`` est le nom d'index ``i``.

    Example:
        ::

            _index_to_list({"Tool_formage": 0, "tool0": 1})
            # → ["Tool_formage", "tool0"]
    """
    result: list[str] = [""] * len(index)
    for name, idx in index.items():
        result[idx] = name
    return result
