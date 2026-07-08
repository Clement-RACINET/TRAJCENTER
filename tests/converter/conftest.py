# tests/converter/conftest.py
"""
Fixtures partagées entre tous les modules de tests TrajCenter.

Contient les fixtures de bas niveau (DataFrames, métadonnées)
réutilisables par test_trajectory.py, test_mod_converter.py,
test_excel_converter.py, test_csv_converter.py, etc.
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import pandas as pd
import pytest
from openpyxl import Workbook

from trajcenter.core.trajectory import (
    ExternalAxisConfig,
    SourceFormat,
    Trajectory,
    TrajectoryMeta,
)


# ---------------------------------------------------------------------------
# Fixtures — fichiers .mod synthétiques
# ---------------------------------------------------------------------------


@pytest.fixture
def mod_simple(tmp_path: Path) -> Path:
    """Fichier .mod minimal avec deux MoveL et une vitesse variable."""
    content = dedent("""\
        MODULE TestModule
            PROC TestProc()
                MoveL [[100.0,200.0,300.0],[1.0,0.0,0.0,0.0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]],vitesse,z0,Tool_formage\\wobj:=Wobj_SerreFlan;
                MoveL [[150.0,250.0,350.0],[1.0,0.0,0.0,0.0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]],vitesse,z0,Tool_formage\\wobj:=Wobj_SerreFlan;
            ENDPROC
        ENDMODULE
    """)
    p = tmp_path / "simple.mod"
    p.write_text(content, encoding="utf-8")
    return p


@pytest.fixture
def mod_with_literal_speed(tmp_path: Path) -> Path:
    """Fichier .mod avec vitesse littérale RAPID (v500)."""
    content = dedent("""\
        MODULE TestModule
            PROC TestProc()
                MoveL [[10.0,20.0,30.0],[1.0,0.0,0.0,0.0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]],v500,z10,Tool_formage\\wobj:=Wobj_SerreFlan;
                MoveJ [[40.0,50.0,60.0],[1.0,0.0,0.0,0.0],[-1,0,1,0],[9E9,9E9,9E9,9E9,9E9,9E9]],v1000,fine,Tool_formage\\wobj:=Wobj_SerreFlan;
            ENDPROC
        ENDMODULE
    """)
    p = tmp_path / "literal_speed.mod"
    p.write_text(content, encoding="utf-8")
    return p


@pytest.fixture
def mod_with_eax(tmp_path: Path) -> Path:
    """Fichier .mod avec un axe externe actif (eax_a = 45.0)."""
    content = dedent("""\
        MODULE TestModule
            PROC TestProc()
                MoveL [[100.0,200.0,300.0],[1.0,0.0,0.0,0.0],[0,0,0,0],[45.0,9E9,9E9,9E9,9E9,9E9]],vitesse,z0,Tool_formage\\wobj:=Wobj_SerreFlan;
            ENDPROC
        ENDMODULE
    """)
    p = tmp_path / "eax.mod"
    p.write_text(content, encoding="utf-8")
    return p


@pytest.fixture
def mod_multiline(tmp_path: Path) -> Path:
    """Fichier .mod avec un robtarget formaté sur plusieurs lignes."""
    content = dedent("""\
        MODULE TestModule
            PROC TestProc()
                MoveL [[100.0,200.0,300.0],
                       [1.0,0.0,0.0,0.0],
                       [0,0,0,0],
                       [9E9,9E9,9E9,9E9,9E9,9E9]],vitesse,z0,Tool_formage\\wobj:=Wobj_SerreFlan;
            ENDPROC
        ENDMODULE
    """)
    p = tmp_path / "multiline.mod"
    p.write_text(content, encoding="utf-8")
    return p


@pytest.fixture
def mod_multiple_tools(tmp_path: Path) -> Path:
    """Fichier .mod avec deux tools et deux wobjs différents."""
    content = dedent("""\
        MODULE TestModule
            PROC TestProc()
                MoveL [[1.0,2.0,3.0],[1.0,0.0,0.0,0.0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]],vitesse,z0,Tool_A\\wobj:=Wobj_A;
                MoveL [[4.0,5.0,6.0],[1.0,0.0,0.0,0.0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]],vitesse,z0,Tool_B\\wobj:=Wobj_B;
                MoveL [[7.0,8.0,9.0],[1.0,0.0,0.0,0.0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]],vitesse,z0,Tool_A\\wobj:=Wobj_A;
            ENDPROC
        ENDMODULE
    """)
    p = tmp_path / "multi_tools.mod"
    p.write_text(content, encoding="utf-8")
    return p


@pytest.fixture
def mod_empty(tmp_path: Path) -> Path:
    """Fichier .mod sans aucune instruction Move."""
    content = dedent("""\
        MODULE TestModule
            PROC TestProc()
                ! Aucune instruction Move ici
            ENDPROC
        ENDMODULE
    """)
    p = tmp_path / "empty.mod"
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Fixtures — classeurs Excel synthétiques
# ---------------------------------------------------------------------------


def _make_xlsx(path: Path, sheets: dict[str, list[dict]]) -> Path:
    """Crée un fichier .xlsx à partir d'un dict {nom_feuille: [lignes]}.

    La première ligne de chaque feuille est utilisée comme en-tête
    (clés du premier dict de la liste).
    """
    wb = Workbook()
    first = True
    for sheet_name, rows in sheets.items():
        ws = wb.active if first else wb.create_sheet()
        assert ws is not None
        ws.title = sheet_name
        first = False
        if not rows:
            continue
        headers = list(rows[0].keys())
        ws.append(headers)
        for row in rows:
            ws.append([row.get(h) for h in headers])
    wb.save(path)
    return path


@pytest.fixture
def xlsx_simple(tmp_path: Path) -> Path:
    """Classeur minimal : une feuille XYZ + quaternions."""
    return _make_xlsx(tmp_path / "simple.xlsx", {
        "traj": [
            {"x": 100.0, "y": 200.0, "z": 300.0,
             "q1": 1.0, "q2": 0.0, "q3": 0.0, "q4": 0.0},
            {"x": 150.0, "y": 250.0, "z": 350.0,
             "q1": 1.0, "q2": 0.0, "q3": 0.0, "q4": 0.0},
        ],
    })


@pytest.fixture
def xlsx_xyz_only(tmp_path: Path) -> Path:
    """Classeur XYZ sans quaternions → orientation identité par défaut."""
    return _make_xlsx(tmp_path / "xyz_only.xlsx", {
        "traj": [
            {"x": 10.0, "y": 20.0, "z": 30.0},
            {"x": 40.0, "y": 50.0, "z": 60.0},
        ],
    })


@pytest.fixture
def xlsx_aliases(tmp_path: Path) -> Path:
    """Classeur avec noms de colonnes non canoniques (alias + accents + casse)."""
    return _make_xlsx(tmp_path / "aliases.xlsx", {
        "traj": [
            {"PosX": 1.0, "PosY": 2.0, "PosZ": 3.0,
             "Vitesse": "v500", "Répère": "Wobj_A", "Outil": "Tool_A"},
        ],
    })


@pytest.fixture
def xlsx_multi_traj(tmp_path: Path) -> Path:
    """Classeur avec deux feuilles trajectoire."""
    return _make_xlsx(tmp_path / "multi_traj.xlsx", {
        "traj_A": [
            {"x": 1.0, "y": 2.0, "z": 3.0},
        ],
        "traj_B": [
            {"x": 4.0, "y": 5.0, "z": 6.0},
            {"x": 7.0, "y": 8.0, "z": 9.0},
        ],
    })


@pytest.fixture
def xlsx_with_tools_sheet(tmp_path: Path) -> Path:
    """Classeur avec feuille trajectoire + feuille tools + feuille wobjs."""
    return _make_xlsx(tmp_path / "with_refs.xlsx", {
        "traj": [
            {"x": 1.0, "y": 2.0, "z": 3.0, "tool": "Tool_A", "wobj": "Wobj_A"},
            {"x": 4.0, "y": 5.0, "z": 6.0, "tool": "Tool_B", "wobj": "Wobj_A"},
        ],
        "tools": [
            {"name": "Tool_A"},
            {"name": "Tool_B"},
        ],
        "wobjs": [
            {"name": "Wobj_A"},
        ],
    })


@pytest.fixture
def xlsx_missing_xyz(tmp_path: Path) -> Path:
    """Classeur sans colonnes XYZ → doit lever ValueError."""
    return _make_xlsx(tmp_path / "missing_xyz.xlsx", {
        "traj": [
            {"speed": "v500", "zone": "z0"},
        ],
    })


@pytest.fixture
def xlsx_with_meta_sheet(tmp_path: Path) -> Path:
    """Classeur avec une feuille meta (doit être ignorée silencieusement)."""
    return _make_xlsx(tmp_path / "with_meta.xlsx", {
        "traj": [
            {"x": 1.0, "y": 2.0, "z": 3.0},
        ],
        "meta": [
            {"key": "author", "value": "test"},
        ],
    })


@pytest.fixture
def xlsx_empty_rows(tmp_path: Path) -> Path:
    """Classeur avec des lignes entièrement vides intercalées."""
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.title = "traj"
    ws.append(["x", "y", "z"])
    ws.append([1.0, 2.0, 3.0])
    ws.append([None, None, None])  # ligne vide
    ws.append([4.0, 5.0, 6.0])
    wb.save(tmp_path / "empty_rows.xlsx")
    return tmp_path / "empty_rows.xlsx"


# ---------------------------------------------------------------------------
# Helpers — fichiers CSV synthétiques
# ---------------------------------------------------------------------------


def _write_csv(path: Path, content: str, encoding: str = "utf-8") -> Path:
    """Écrit un fichier CSV synthétique et retourne son chemin."""
    path.write_text(content, encoding=encoding)
    return path


# ---------------------------------------------------------------------------
# Fixtures — fichiers CSV synthétiques
# ---------------------------------------------------------------------------


@pytest.fixture
def csv_simple(tmp_path: Path) -> Path:
    """CSV minimal : XYZ + quaternions, séparateur virgule."""
    return _write_csv(
        tmp_path / "simple.csv",
        "x,y,z,q1,q2,q3,q4\n"
        "100.0,200.0,300.0,1.0,0.0,0.0,0.0\n"
        "150.0,250.0,350.0,1.0,0.0,0.0,0.0\n",
    )


@pytest.fixture
def csv_semicolon(tmp_path: Path) -> Path:
    """CSV avec séparateur point-virgule (export Excel français)."""
    return _write_csv(
        tmp_path / "semicolon.csv",
        "x;y;z;q1;q2;q3;q4\n"
        "10.0;20.0;30.0;1.0;0.0;0.0;0.0\n"
        "40.0;50.0;60.0;1.0;0.0;0.0;0.0\n",
    )


@pytest.fixture
def csv_xyz_only(tmp_path: Path) -> Path:
    """CSV XYZ sans quaternions → orientation identité par défaut."""
    return _write_csv(
        tmp_path / "xyz_only.csv",
        "x,y,z\n"
        "10.0,20.0,30.0\n"
        "40.0,50.0,60.0\n",
    )


@pytest.fixture
def csv_aliases(tmp_path: Path) -> Path:
    """CSV avec noms de colonnes non canoniques (alias + casse)."""
    return _write_csv(
        tmp_path / "aliases.csv",
        "PosX,PosY,PosZ,VITESSE\n"
        "1.0,2.0,3.0,v500\n",
    )


@pytest.fixture
def csv_with_tools(tmp_path: Path) -> Path:
    """CSV avec colonnes tool et wobj."""
    return _write_csv(
        tmp_path / "with_tools.csv",
        "x,y,z,tool,wobj\n"
        "1.0,2.0,3.0,Tool_A,Wobj_A\n"
        "4.0,5.0,6.0,Tool_B,Wobj_A\n",
    )


@pytest.fixture
def csv_missing_xyz(tmp_path: Path) -> Path:
    """CSV sans colonnes XYZ → doit lever ValueError."""
    return _write_csv(
        tmp_path / "missing_xyz.csv",
        "speed,zone\n"
        "v500,z0\n",
    )


@pytest.fixture
def csv_empty_rows(tmp_path: Path) -> Path:
    """CSV avec des lignes entièrement vides intercalées."""
    return _write_csv(
        tmp_path / "empty_rows.csv",
        "x,y,z\n"
        "1.0,2.0,3.0\n"
        ",,\n"
        "4.0,5.0,6.0\n",
    )


@pytest.fixture
def csv_with_bom(tmp_path: Path) -> Path:
    """CSV encodé UTF-8 avec BOM (export Excel Windows)."""
    return _write_csv(
        tmp_path / "bom.csv",
        "x,y,z\n1.0,2.0,3.0\n",
        encoding="utf-8-sig",
    )


@pytest.fixture
def csv_full(tmp_path: Path) -> Path:
    """CSV complet avec toutes les colonnes canoniques."""
    return _write_csv(
        tmp_path / "full.csv",
        "x,y,z,q1,q2,q3,q4,move_type,speed,zone,tool,wobj\n"
        "100.0,200.0,300.0,1.0,0.0,0.0,0.0,MoveL,v500,z10,Tool_formage,Wobj_SerreFlan\n"
        "150.0,250.0,350.0,1.0,0.0,0.0,0.0,MoveJ,v1000,fine,Tool_formage,Wobj_SerreFlan\n",
    )

@pytest.fixture
def xlsx_with_full_meta(tmp_path: Path) -> Path:
    """Classeur avec feuille meta complète (name, robot_model, champ custom)."""
    return _make_xlsx(tmp_path / "full_meta.xlsx", {
        "traj": [{"x": 1.0, "y": 2.0, "z": 3.0}],
        "meta": [
            {"key": "name",        "value": "Trajectoire_Soudure"},
            {"key": "robot_model", "value": "IRB6700-205/2.80"},
            {"key": "author",      "value": "Jean Dupont"},
        ],
    })
