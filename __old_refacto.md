
# TRAJCENTER v2.0 — Plan de Refacto Architecture RWS

> **Date :** 2026-07-07
> **Auteurs :** J. SCHUMACKER / C. RACINET
> **Contexte :** Remplacement du protocole TCP/IP custom par ABB Robot Web Services (RWS)
> **RobotWare :** 6.x

---

## 🎯 Objectif

Remplacer le protocole TCP/IP custom (serveur Python ↔ client RAPID) par des appels HTTP REST via **ABB Robot Web Services (RWS)**. Le serveur Python écrit directement les variables RAPID dans le contrôleur, sans que le robot ait à gérer un protocole réseau custom.

### Ce qui change

| Aspect              | Avant                                  | Après                                   |
| ------------------- | -------------------------------------- | --------------------------------------- |
| Transport           | TCP custom, protocole texte            | HTTP REST (RWS)                         |
| Sens du flux        | Robot demande → Python répond          | Python pousse → Robot attend            |
| Conversion données  | INT32 little-endian dans RAPID         | Faite côté Python, format texte RWS     |
| Gestion paquets     | 15 robtargets par requête              | Chunks configurables, écriture directe  |
| Format source       | Multiples formats gérés à la volée     | Conversion préalable en `.trajcenter`   |
| Interface robot     | Menu FlexPendant + socket TCP          | Menu FlexPendant + signal RWS           |

### Ce qui ne change pas

- La variable `RobtTRAJCENTER{100000}` reste statique côté RAPID (contrainte RW6)
- La taille réelle est gérée via `NbRobtargetsTraj`
- L'interface FlexPendant est conservée
- `TRAJCENTER_Move` reste inchangée (ou enrichie en Phase 7)

---

## 📦 Structure du dépôt

```
trajcenter/
│
├── pixi.toml
├── pixi.lock
├── pyproject.toml
├── README.md
│
├── trajcenter/
│   ├── __init__.py
│   │
│   ├── converter/
│   │   ├── __init__.py
│   │   ├── base.py                 # Classe abstraite BaseConverter
│   │   ├── mod_converter.py        # Convertisseur RAPID .mod
│   │   ├── xlsx_converter.py       # Convertisseur Excel .xlsx
│   │   ├── aptsource_converter.py  # Convertisseur APT source CATIA
│   │   └── txt_converter.py        # Convertisseur texte délimité
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── trajectory.py           # Trajectory + TrajectoryMeta + ConversionDefaults
│   │   └── trajectory_store.py     # Gestion du dossier de trajectoires
│   │
│   ├── rws/
│   │   ├── __init__.py
│   │   ├── client.py               # Client HTTP RWS (auth digest, session ABBCX)
│   │   ├── rapid_writer.py         # Écriture variables RAPID via RWS
│   │   └── mastership.py           # Context manager RequestMastership
│   │
│   ├── server/
│   │   ├── __init__.py
│   │   └── app.py                  # API FastAPI optionnelle
│   │
│   └── utils/
│       ├── __init__.py
│       └── logging.py              # Logger Rich
│
├── trajectory_files/               # Fichiers sources bruts (.mod, .xlsx, .aptsource)
├── trajectory_store/               # Fichiers .trajcenter convertis
│
├── scripts/
│   └── doc/
│       ├── config.py               # DocConfig (Pydantic)
│       ├── generate_api.py         # Génération pages MkDocs API
│       └── run_docs.py             # Point d'entrée pipeline doc
│
├── docs/
│   ├── index.md                    # --8<-- "README.md"
│   └── api/                        # Généré automatiquement
│
├── mkdocs.yml
│
├── rapid/
│   ├── TRAJCENTER.sys
│   └── MainModule.mod
│
└── tests/
    ├── test_converters.py
    ├── test_trajectory.py
    └── test_rws_client.py
```

---

## 🗂️ Format `.trajcenter`

### Pourquoi un format intermédiaire ?

Découpler **la source** (mod, xlsx, aptsource…) de **l'exécution**. Le serveur ne connaît que le format `.trajcenter`. Les convertisseurs ne connaissent que leur format source.

### Structure de l'archive

Le fichier `.trajcenter` est une **archive ZIP** contenant quatre entrées :

```
archive.trajcenter  (ZIP)
├── meta.json        ← TrajectoryMeta (Pydantic → JSON)
├── points.parquet   ← DataFrame (PyArrow, compression zstd)
├── tools.json       ← Liste ordonnée des noms de tools  (index → nom)
└── wobjs.json       ← Liste ordonnée des noms de wobjs  (index → nom)
```

`tools.json` et `wobjs.json` sont des tableaux JSON simples :
```json
["Tool_formage", "tool0"]
```
`tools[0]` est le tool d'index 0, référencé par la colonne `tool_index` du Parquet.
Ces deux fichiers sont **toujours présents** (tableau vide `[]` si non applicable).

> La spec JSON plate initiale (champs `metadata`, `defaults`, `points` en JSON) est **abandonnée**
> au profit de cette archive binaire pour des raisons de performance et de typage.

### Pourquoi ZIP + Parquet ?

| Critère          | JSON initial              | ZIP + Parquet retenu              |
| ---------------- | ------------------------- | --------------------------------- |
| **Performance**  | Lent sur 100k points      | Parquet vectorisé, zstd rapide    |
| **Types**        | Tout en string/float      | Schéma typé (float64, Int8…)      |
| **Axes externes**| `"eax": [9e9, …]` fixe   | Colonnes optionnelles (présence = actif) |
| **Extensibilité**| Champs figés              | Colonnes OPTIONAL_COLUMNS libres  |

### Métadonnées (`meta.json`) — `TrajectoryMeta`

Modèle Pydantic sérialisé en JSON UTF-8.

| Champ             | Type                              | Défaut        | Note                                      |
| ----------------- | --------------------------------- | ------------- | ----------------------------------------- |
| `name`            | `str`                             | —             | Obligatoire — identifiant humain          |
| `version`         | `str`                             | `"1.0"`       | Version du format `.trajcenter`           |
| `created_at`      | `datetime`                        | UTC now       | Horodatage de création                    |
| `source_file`     | `str \| None`                     | `None`        | Nom/chemin du fichier source d'origine    |
| `source_format`   | `SourceFormat`                    | `MANUAL`      | Enum : `excel`, `apt`, `csv`, `rapid`, `manual` |
| `robot_model`     | `str \| None`                     | `None`        | Ex. `"IRB6700-205/2.80"`                  |
| `point_count`     | `int`                             | auto          | Mis à jour automatiquement à `save()`     |
| `external_axes`   | `dict[str, ExternalAxisConfig]`   | `{}`          | Clés : `eax_a`…`eax_f`. Absent = inactif |
| `defaults`        | `ConversionDefaults`              | voir ci-dessous | Valeurs utilisées pour l'autocomplétion |
| `autocompleted`   | `list[str]`                       | `[]`          | Colonnes autocomplétées depuis `defaults` |
| `extra`           | `dict`                            | `{}`          | Champ libre pour métadonnées projet       |

#### `ConversionDefaults`

Valeurs par défaut appliquées lors de la conversion pour les colonnes
absentes du fichier source. Toujours tracées dans `meta.json`.

| Champ        | Type  | Défaut     | Note                                         |
| ------------ | ----- | ---------- | -------------------------------------------- |
| `move_type`  | `str` | `"MoveL"`  | Type de mouvement RAPID par défaut           |
| `speed`      | `str` | `"v500"`   | Vitesse RAPID par défaut                     |
| `zone`       | `str` | `"z10"`    | Zone RAPID par défaut                        |
| `tool`       | `str` | `"tool0"`  | Nom du tool par défaut (→ `tools[0]`)        |
| `wobj`       | `str` | `"wobj0"`  | Nom du wobj par défaut (→ `wobjs[0]`)        |
| `cf_value`   | `int` | `0`        | Valeur confdata par défaut (0 = conf off)    |

#### Principe d'autocomplétion

> **Règle :** à la sortie de n'importe quel convertisseur, le `.trajcenter`
> est **toujours complet**. Toute colonne absente dans la source est
> comblée par la valeur correspondante de `ConversionDefaults`.
> Les colonnes autocomplétées sont listées dans `meta.autocompleted`.

Exemple pour une conversion depuis un `.csv` sans type de mouvement ni vitesse :
```json
{
  "source_format": "csv",
  "defaults": { "move_type": "MoveL", "speed": "v500", "zone": "z10",
                "tool": "tool0", "wobj": "wobj0", "cf_value": 0 },
  "autocompleted": ["move_type", "speed", "zone", "cf1", "cf4", "cf6", "cfx",
                    "tool_index", "wobj_index"]
}
```

Exemple pour une conversion depuis un `.mod` (toutes les infos présentes,
sauf la vitesse qui est une variable RAPID non résolue) :
```json
{
  "source_format": "rapid",
  "defaults": { "speed": "v500", ... },
  "autocompleted": ["speed"]
}
```

#### `ExternalAxisConfig`

```python
class ExternalAxisConfig(BaseModel):
    axis_type: str   # "rotational" ou "linear"
    unit: str        # "deg" ou "mm"
    label: str | None
```

### Schéma points (`points.parquet`)

**Colonnes obligatoires** — toujours présentes en sortie de convertisseur :

| Colonne      | Type PyArrow | Description                                          |
| ------------ | ------------ | ---------------------------------------------------- |
| `x`          | `float64`    | Position X (mm)                                      |
| `y`          | `float64`    | Position Y (mm)                                      |
| `z`          | `float64`    | Position Z (mm)                                      |
| `q1`         | `float64`    | Quaternion w (scalaire en premier — convention ABB)  |
| `q2`         | `float64`    | Quaternion x                                         |
| `q3`         | `float64`    | Quaternion y                                         |
| `q4`         | `float64`    | Quaternion z                                         |
| `cf1`        | `int8`       | Confdata axe 1 — autocomplétion à `0` si absent      |
| `cf4`        | `int8`       | Confdata axe 4 — autocomplétion à `0` si absent      |
| `cf6`        | `int8`       | Confdata axe 6 — autocomplétion à `0` si absent      |
| `cfx`        | `int8`       | Confdata axe externe — autocomplétion à `0` si absent|
| `move_type`  | `string`     | `"MoveJ"`, `"MoveL"`, `"MoveC"` — autocomplétion    |
| `speed`      | `string`     | Vitesse RAPID par point — autocomplétion             |
| `zone`       | `string`     | Zone RAPID par point — autocomplétion                |
| `tool_index` | `int16`      | Index dans `tools.json` — autocomplétion à `0`       |
| `wobj_index` | `int16`      | Index dans `wobjs.json` — autocomplétion à `0`       |

**Colonnes optionnelles** — présence = axe externe actif sur ce robot :

| Colonne         | Type PyArrow | Description                      |
| --------------- | ------------ | -------------------------------- |
| `eax_a`…`eax_f` | `float64`    | Axes externes actifs (mm ou deg) |

> **Convention axes externes :** la présence de la colonne `eax_a` dans le
> DataFrame signifie que l'axe A est actif. Il n'y a **pas** de valeur
> sentinelle `9E9` dans le Parquet. La valeur `9E9` est injectée
> **uniquement à la sérialisation RWS** pour les axes déclarés inactifs.

> **Confdata :** stocké en `Int8 nullable` pandas (supporte NaN,
> contrairement à `np.int8`).

### Correspondance ROUTES.md → colonnes `.trajcenter`

| Route ROUTES.md | Colonne `points.parquet`     | Type pandas              |
| --------------- | ---------------------------- | ------------------------ |
| `mvt[i;j]`      | `move_type`                  | `string` (`MoveType`)    |
| `zone[i;j]`     | `zone`                       | `string` RAPID           |
| `speed[i;j]`    | `speed`                      | `string` RAPID           |
| `tool[i;j]`     | `tool_index` → `tools.json`  | `int16`                  |
| `wobj[i;j]`     | `wobj_index` → `wobjs.json`  | `int16`                  |
| `conf[i;j]`     | `cf1, cf4, cf6, cfx`         | `Int8 nullable`          |
| `toolval[i]`    | *(non implémenté — Phase 7)* | —                        |
| `wobjval[i]`    | *(non implémenté — Phase 7)* | —                        |

---

## 🔄 Convertisseurs

### Principe

Chaque convertisseur hérite de `BaseConverter` et implémente `convert()`.
`BaseConverter` fournit la méthode utilitaire `_autocomplete()` qui comble
les colonnes manquantes et retourne la liste des colonnes autocomplétées.

```python
class BaseConverter(ABC):

    @abstractmethod
    def convert(self, source: Path) -> Trajectory:
        """Convertit un fichier source en objet Trajectory."""
        ...

    def _autocomplete(
        self,
        df: pd.DataFrame,
        defaults: ConversionDefaults,
        tools: list[str],
        wobjs: list[str],
    ) -> tuple[pd.DataFrame, list[str]]:
        """Complète les colonnes manquantes avec les valeurs par défaut.
        Retourne (df_complet, colonnes_autocomplétées).
        """
        ...

    def convert_and_save(
        self, source: Path, dest_dir: Path, stem: str | None = None
    ) -> Path:
        """Convertit et sauvegarde en .trajcenter. Retourne le chemin absolu."""
        ...
```

Le convertisseur est responsable de :
1. Parser le fichier source dans son format natif
2. Construire le `DataFrame` avec les colonnes disponibles
3. Appeler `_autocomplete()` pour garantir un fichier complet
4. Renseigner `TrajectoryMeta` (notamment `source_file`, `source_format`,
   `defaults`, `autocompleted`)
5. Retourner un objet `Trajectory` valide

La sauvegarde en `.trajcenter` est toujours déléguée à `Trajectory.save()`.

### Convertisseurs prévus

| Classe               | Fichier                    | Format source         | Priorité |
| -------------------- | -------------------------- | --------------------- | -------- |
| `ModConverter`       | `mod_converter.py`         | RAPID `.mod`          | 🔴 P1   |
| `XlsxConverter`      | `xlsx_converter.py`        | Excel `.xlsx`         | 🟡 P2   |
| `AptSourceConverter` | `aptsource_converter.py`   | APT source CATIA      | 🟡 P2   |
| `TxtConverter`       | `txt_converter.py`         | Texte délimité `.csv` | 🟢 P3   |

---

## 🔌 Couche RWS

### Principe général (RobotWare 6)

- **Protocole :** HTTP REST, auth Digest, cookie de session `ABBCX`
- **Format :** JSON (`?json=1`) ou XML (défaut)
- **Écriture variable RAPID :**

```
PUT /rw/rapid/symbol/data/RAPID/T_ROB1/TRAJCENTER/RobtTRAJCENTER
Content-Type: application/x-www-form-urlencoded

value=[[423.12,-112.5,890.0],[0.0,0.0,1.0,0.0],[0,0,0,0],[9E9,9E9,9E9,9E9,9E9,9E9]],[[...]],...
```

### Sérialisation robtarget → format texte RWS

Format attendu par RWS pour un robtarget RAPID :

```
[[x,y,z],[q1,q2,q3,q4],[cf1,cf4,cf6,cfx],[eax_a,eax_b,eax_c,eax_d,eax_e,eax_f]]
```

> Les axes externes inactifs (absents du DataFrame) sont sérialisés en `9E9`
> **exactement** — pas `9000000000.0`. Cette injection se fait dans
> `rapid_writer.py` à partir des colonnes présentes et de `meta.external_axes`.

### Stratégie d'écriture par chunks

```
1. RequestMastership (RAPID)
2. PUT NbRobtargetsTraj        → variable num RAPID
3. Pour chaque chunk de N points (départ recommandé : 50, à calibrer) :
       PUT slice du tableau RobtTRAJCENTER
4. ReleaseMastership
5. PUT TrajReady = TRUE        → signal de synchronisation Python → RAPID
```

### Responsabilités des modules Python

| Module                | Responsabilité                                                            |
| --------------------- | ------------------------------------------------------------------------- |
| `rws/client.py`       | Session HTTP authentifiée (digest + cookie ABBCX), GET / PUT / POST      |
| `rws/mastership.py`   | Context manager `async with RAPIDMastership(client)`                     |
| `rws/rapid_writer.py` | Écriture `NbRobtargetsTraj`, chunks `RobtTRAJCENTER`, signal `TrajReady` |

---

## 🤖 Refacto RAPID

### Ce qui est supprimé

- Toute la gestion socket TCP (`SocketCreate`, `SocketConnect`, `SocketSend`, `SocketReceive`)
- La réception par paquets de 15 robtargets
- Les conversions INT32 → float dans RAPID
- La boucle de décodage `UnpackRawBytes`

### Ce qui est ajouté

```rapid
VAR bool TrajReady := FALSE;        ! Signal écrit par Python via RWS
VAR num SelectedTrajIndex := 0;     ! Choix utilisateur lu par Python via RWS
```

### Nouveau flux `TRAJCENTER_GetValues` (simplifié)

```rapid
PROC TRAJCENTER_GetValues()
    ! 1. Affichage menu FlexPendant (inchangé)
    ! 2. Écriture du choix utilisateur
    SelectedTrajIndex := selectedTraj;
    ! 3. Attente du signal de fin de transfert Python
    WaitUntil TrajReady = TRUE \MaxTime:=120 \TimeFlag:=timeout_flag;
    TrajReady := FALSE;
    ! 4. Récapitulatif (inchangé)
ENDPROC
```

### Diagramme de synchronisation

```
Robot (RAPID)                          Python (RWS)
─────────────────────────────────────────────────────────
Affiche menu FlexPendant
Utilisateur sélectionne traj N
Écrit SelectedTrajIndex = N   ───────► Poll GET SelectedTrajIndex
                                        Détecte changement
                                        Charge .trajcenter N
                                        Écrit NbRobtargetsTraj
                                        Écrit RobtTRAJCENTER par chunks
                              ◄───────  Écrit TrajReady = TRUE
WaitUntil TrajReady = TRUE ✓
Lance TRAJCENTER_Move
```

---

## 🖥️ API FastAPI (optionnelle — Phase 8)

```
GET  /trajectories              → liste des .trajcenter disponibles
POST /trajectories/convert      → convertit un fichier source en .trajcenter
POST /transfer/{name}           → transfère une trajectoire vers le robot
GET  /robot/status              → état RWS du contrôleur
```

---

## 🗓️ Séquence de développement — état d'avancement

```
Étape 1 ── Socle, structure dossiers + logger Rich                    ✅ DONE
    │
Étape 2 ── Format .trajcenter + dataclass Trajectory                  ✅ DONE
    │         ✅ TrajectoryMeta (Pydantic) + ExternalAxisConfig
    │         ✅ ConversionDefaults + champ autocompleted
    │         ✅ SourceFormat, MoveType (StrEnum)
    │         ✅ Trajectory(meta, points, tools, wobjs)
    │         ✅ Trajectory.save() → ZIP (meta + points + tools + wobjs)
    │         ✅ Trajectory.load() ← ZIP (rétrocompat. sans tools/wobjs)
    │         ✅ Validation colonnes obligatoires + cast types pandas
    │         ✅ Validation bornes tool_index / wobj_index
    │         ✅ Propriétés : point_count, active_external_axes,
    │                         has_confdata, has_move_type,
    │                         has_tool_table, has_wobj_table
    │         ⏳ Sérialiseur RWS (robtarget → texte RWS)              → Étape 5
    │         ⏳ Tests unitaires Trajectory                            → à compléter
    │
Étape 3 ── Convertisseurs (mod en priorité, xlsx, aptsource) + CLI    ⬅️ EN COURS
    │         ✅ BaseConverter (ABC) + _autocomplete() + convert_and_save()
    │         ✅ ModConverter (.mod RAPID)
    │         ⏳ XlsxConverter (.xlsx)
    │         ⏳ AptSourceConverter (.aptsource CATIA)
    │         ⏳ TxtConverter (.csv)
    │         ⏳ CLI de conversion (ex. pixi run convert)
    │
Étape 4 ── Client RWS : auth digest + session ABBCX + GET RAPID
    │         ⏳ RWSClient (httpx, auth Digest, cookie ABBCX)
    │         ⏳ GET variable RAPID (lecture SelectedTrajIndex)
    │
Étape 5 ── Écriture RWS : chunks + sérialiseur robtarget + TrajReady
    │         ⏳ Sérialiseur robtarget → texte RWS (9E9 pour eax inactifs)
    │         ⏳ RAPIDWriter : NbRobtargetsTraj + chunks + TrajReady
    │         ⏳ Calibration chunk size sur contrôleur réel
    │
Étape 6 ── Refacto RAPID : suppression TCP, WaitUntil + SelectedTrajIndex
    │
Étape 7 ── Intégration ROUTES.md complet (toolval, wobjval)
    │         + TRAJCENTER_Move enrichie
    │
Étape 8 ── API FastAPI + interface pilotage PC (optionnel)
    │
Étape 9 ── Tests d'intégration bout-en-bout + validation robot réel
```

---

## ⚠️ Points de vigilance

| # | Sujet                        | Détail                                                                                                        |
| - | ---------------------------- | ------------------------------------------------------------------------------------------------------------- |
| 1 | **Mastership RW6**           | Refusé si programme RAPID en cours en mode auto. Gérer l'état contrôleur avant écriture.                     |
| 2 | **Chunk size**               | Limite payload RWS non documentée sur RW6. À calibrer empiriquement (départ : 50 pts).                       |
| 3 | **Sérialisation 9E9**        | Les axes externes inactifs doivent être `9E9` exactement — pas `9000000000.0`. Injecté dans `rapid_writer.py`.|
| 4 | **Dimensionnement tableau**  | `RobtTRAJCENTER{100000}` statique côté RAPID — contrainte RW6, ne pas tenter de redimensionner à chaud.      |
| 5 | **Synchronisation menu**     | Le choix FlexPendant est communiqué à Python via `SelectedTrajIndex`, lu par polling RWS.                     |
| 6 | **Credentials**              | `Default User` / `robotics` — à externaliser dans un `.env` non versionné.                                   |
| 7 | **Quaternions ABB**          | Convention `[q1, q2, q3, q4]` = `[w, x, y, z]` (scalaire en premier). À respecter dans tous les convertisseurs. |
| 8 | **confdata Int8 nullable**   | Stocké en `pd.Int8Dtype()` (nullable) et non `np.int8` pour supporter les NaN.                               |
| 9 | **Autocomplétion traçée**    | Toute valeur inférée (non présente dans la source) est listée dans `meta.autocompleted`. Ne jamais compléter silencieusement. |

---

## 📚 Références

- [ABB RWS API Reference](https://developercenter.robotstudio.com/api/rwsApi/)
- ABB Application Manual — Robot Web Services `3HAC050973-001`
- Code source v1.0 : `TRAJCENTER_server_v1.py` + `TRAJCENTER.sys`
- Spécification protocole étendu : `ROUTES.md`
