
# TRAJCENTER v2.0 — Protocole RWS PC ↔ Robot

> **Version :** 2.2 draft  
> **Date :** 2026-07-17  
> **RobotWare :** 6.x  
> **Transport :** ABB Robot Web Services uniquement  
> **TCP custom / watchdog / polling nominal :** supprimés  

---

## 1. Objectif

TrajCenter v2.0 utilise uniquement ABB Robot Web Services pour échanger entre le PC et le contrôleur ABB.

Le robot déclenche les actions en écrivant des variables RAPID `PERS` abonnées par le PC.  
Le PC écrit ensuite les métadonnées, les trajectoires et les états dans les variables RAPID.

Ce document définit :

- les flux de communication ;
- les variables RAPID partagées ;
- le format `.trajcenter` ;
- les règles d’indexation et d’encodage ;
- les pipelines nominales ;
- les validations et erreurs.

---

## 2. Flux général

| Flux | Déclencheur | Direction | Mécanisme | Résultat |
|---|---|---|---|---|
| Refresh metadata | `RefreshMetaRequest = TRUE` | Robot → PC | RWS subscription | Le PC rescane le store et met à jour la liste des trajectoires |
| Envoi trajectoire | `SendTrajRequest = TRUE` | Robot → PC | RWS subscription | Le PC lit `SelectedTrajIndex`, charge la trajectoire et remplit les tableaux RAPID |
| Écriture données | Action PC | PC → Robot | RWS write + Mastership | Variables RAPID mises à jour |
| Lecture contexte robot | Action PC | Robot → PC | RWS read | Defaults, `toolNames`, `wobjNames`, état courant |
| État / erreur | Action PC | PC → Robot | RWS write + Mastership | `TrajReady`, `TransferError`, `LastErrorCode`, etc. |

Règles générales :

- le PC s’abonne au démarrage à `SendTrajRequest` et `RefreshMetaRequest` ;
- seuls les événements `TRUE` déclenchent une action ;
- les événements `FALSE` sont ignorés ;
- le PC remet la requête traitée à `FALSE`, en succès comme en erreur ;
- au démarrage ou après reconnexion, le PC relit les deux requêtes pour traiter une demande déjà pendante.

---

## 3. Variables RAPID

### 3.1 Commandes robot → PC

| Nom | Type RAPID | Déclaration | Défaut | Rôle |
|---|---|---|---|---|
| `SendTrajRequest` | `bool` | `PERS` | `FALSE` | Demande d’envoi de la trajectoire sélectionnée |
| `RefreshMetaRequest` | `bool` | `PERS` | `FALSE` | Demande de refresh de la liste des trajectoires |
| `SelectedTrajIndex` | `num` | `PERS` | `0` | Index de trajectoire à envoyer |

Convention :

```text
SelectedTrajIndex = 0 : aucune sélection
SelectedTrajIndex = 1..NbTrajDispo : trajectoire valide
```

---

### 3.2 Métadonnées store

| Nom | Type RAPID | Déclaration | Taille | Rôle |
|---|---|---|---:|---|
| `NbTrajDispo` | `num` | `VAR` | 1 | Nombre de trajectoires disponibles |
| `NomsTraj` | `string[]` | `VAR` | 256 | Noms affichables |
| `NbPointsTraj` | `num[]` | `VAR` | 256 | Nombre de points par trajectoire |

Constante :

```text
MAX_TRAJ = 256
```

---

### 3.3 Données trajectoire

| Nom | Type RAPID | Déclaration | Taille | Format / valeurs | Rôle |
|---|---|---|---:|---|---|
| `NbRobtargetsTraj` | `num` | `VAR` | 1 | `0..100000` | Nombre de points envoyés |
| `RobtTRAJCENTER` | `robtarget[]` | `VAR` | 100000 | robtarget ABB | Points trajectoire |
| `vitesses` | `num[]` | `VAR` | 100000 | TCP mm/s, `> 0` | Vitesse par point |
| `toolIndex` | `num[]` | `VAR` | 100000 | index robot, base 1 | Outil par point |
| `wobjIndex` | `num[]` | `VAR` | 100000 | index robot, base 1 | Wobj par point |
| `zoneType` | `num[]` | `VAR` | 100000 | liste autorisée | Zone par point |
| `mvtType` | `string[]` | `VAR` | 100000 | `"J"`, `"L"`, `"C"` | Type de mouvement |
| `readconfs` | `bool[]` | `VAR` | 100000 | `TRUE/FALSE` | Prise en compte confdata |

Constante :

```text
MAX_POINTS = 100000
```

---

### 3.4 Tools / wobjs robot

Les tools et wobjs sont définis côté robot. Le PC lit leurs noms pour faire le mapping :

```text
tool_name (.trajcenter) -> toolIndex RAPID
wobj_name (.trajcenter) -> wobjIndex RAPID
```

| Nom | Type RAPID | Déclaration | Taille | Rôle |
|---|---|---|---:|---|
| `toolValues` | `tooldata[]` | `PERS` | variable cellule | Données outils |
| `toolNames` | `string[]` | `VAR` ou `CONST` | variable cellule | Noms outils lisibles par PC |
| `wobjValues` | `wobjdata[]` | `PERS` | variable cellule | Données wobjs |
| `wobjNames` | `string[]` | `VAR` ou `CONST` | variable cellule | Noms wobjs lisibles par PC |

---

### 3.5 États PC → robot

| Nom | Type RAPID | Déclaration | Défaut | Rôle |
|---|---|---|---|---|
| `TrajReady` | `bool` | `PERS` | `FALSE` | La trajectoire est prête à être exécutée |
| `TransferError` | `bool` | `PERS` | `FALSE` | Le dernier transfert ou refresh a échoué |
| `LastErrorCode` | `num` | `PERS` | `200000` | Code état/erreur à 6 chiffres |
| `LastError` | `string` | `PERS` | `""` | Message court affichable |
| `TransferProgress` | `num` | `PERS` | `0` | Progression d’envoi, `0..100` |

---

### 3.6 Defaults robot

Les defaults sont lus côté robot au moment de l’envoi. Ils servent à transformer une trajectoire exportable en trajectoire envoyable.

| Nom | Type | Rôle |
|---|---|---|
| `HasDefaultTcpSpeed` | `bool` | Autorise un fallback vitesse |
| `DefaultTcpSpeed` | `num` | Vitesse TCP par défaut |
| `HasDefaultZoneType` | `bool` | Autorise un fallback zone |
| `DefaultZoneType` | `num` | Zone par défaut |
| `HasDefaultToolName` | `bool` | Autorise un fallback tool |
| `DefaultToolName` | `string` | Tool par défaut |
| `HasDefaultWobjName` | `bool` | Autorise un fallback wobj |
| `DefaultWobjName` | `string` | Wobj par défaut |
| `DefaultMoveType` | `string` | Mouvement par défaut, recommandé `"L"` |
| `DefaultReadConfs` | `bool` | Valeur par défaut si applicable |

Règle : aucun default `tool`, `wobj`, `speed` ou `zone` ne doit être inventé silencieusement côté PC.

---

## 4. Format `.trajcenter`

### 4.1 Structure recommandée

Un fichier `.trajcenter` est une archive contenant au minimum :

```text
meta.json
points.parquet
```

Les noms tools/wobjs peuvent être stockés directement dans `points.parquet`.  
Des fichiers ou champs dérivés peuvent lister les sets utilisés, mais ils ne doivent pas remplacer la vérité point par point.

---

### 4.2 Colonnes `points.parquet`

| Colonne | Obligatoire export | Obligatoire envoi | Défaut / résolution |
|---|---:|---:|---|
| `x` | oui | oui | — |
| `y` | oui | oui | — |
| `z` | oui | oui | — |
| `q1` | oui | oui | quaternion ABB `[w]` |
| `q2` | oui | oui | quaternion ABB `[x]` |
| `q3` | oui | oui | quaternion ABB `[y]` |
| `q4` | oui | oui | quaternion ABB `[z]` |
| `cf1` | non | oui | `0` si absent |
| `cf4` | non | oui | `0` si absent |
| `cf6` | non | oui | `0` si absent |
| `cfx` | non | oui | `0` si absent |
| `eax_a..eax_f` | non | non | absent = axe inactif |
| `tcp_speed` | non | oui | erreur sauf default robot explicite |
| `zone_type` | non | oui | erreur sauf default robot explicite |
| `move_type` | non | oui | default robot, recommandé `"L"` |
| `tool_name` | non | oui | erreur sauf default robot explicite validé |
| `wobj_name` | non | oui | erreur sauf default robot explicite validé |
| `readconfs` | non | oui | voir règle ci-dessous |

Règle `readconfs` si absent :

```text
si cf1/cf4/cf6/cfx sont présents : readconfs = TRUE
sinon : readconfs = FALSE
```

---

### 4.3 Exportable vs envoyable

| Niveau | Définition |
|---|---|
| Exportable | Le fichier contient au minimum `x,y,z,q1,q2,q3,q4` |
| Envoyable | Tous les champs nécessaires au robot sont présents ou résolus via defaults robot valides |

Une trajectoire exportable peut donc être listée et stockée, mais refusée à l’envoi si elle ne peut pas être résolue pour le robot connecté.

---

## 5. Encodages et conventions

### 5.1 Indexation

| Élément | Convention |
|---|---|
| Tableaux RAPID | base 1 |
| `SelectedTrajIndex` | base 1, `0 = aucune sélection` |
| `toolIndex`, `wobjIndex` | base 1, `0 = non défini` |
| Points `.trajcenter` | ordre naturel du fichier, converti vers RAPID `{1..N}` |

---

### 5.2 Robtarget

Format RWS :

```text
[[x,y,z],[q1,q2,q3,q4],[cf1,cf4,cf6,cfx],[eax_a,eax_b,eax_c,eax_d,eax_e,eax_f]]
```

Règles :

- quaternion ABB : `[q1,q2,q3,q4] = [w,x,y,z]` ;
- axes externes absents : sérialisés `9E+9` ;
- `9E+9` n’est jamais stocké dans `.trajcenter`.

---

### 5.3 Zones

Valeurs autorisées :

```text
0, 1, 5, 10, 15, 20, 30, 40, 50, 60, 80, 100, 150, 200, 255
```

Avec :

```text
0   = z0
255 = fine
```

---

### 5.4 Vitesses

```text
tcp_speed -> vitesses{i}
```

Règles :

- valeur numérique ;
- en mm/s ;
- strictement positive.

---

### 5.5 Types de mouvement

Valeurs envoyées à RAPID :

```text
"J", "L", "C"
```

Alias acceptés à l’import :

```text
"MoveJ" -> "J"
"MoveL" -> "L"
"MoveC" -> "C"
```

---

### 5.6 MoveC

Un `MoveC` est toujours encodé par deux points consécutifs non chevauchants :

```text
C, C
```

Séquence valide :

```text
C,C,C,C = deux MoveC successifs
```

Séquence interdite :

```text
C,C,C
```

Pour une paire `C,C`, les paramètres suivants doivent être identiques :

```text
tcp_speed
tool_name / toolIndex
wobj_name / wobjIndex
zone_type
readconfs
```

---

## 6. Pipelines

### 6.1 Démarrage PC

```text
1. Ouvrir session RWS.
2. S’abonner à SendTrajRequest et RefreshMetaRequest.
3. Lire l’état courant des deux requêtes.
4. Lire defaults robot.
5. Lire toolNames et wobjNames.
6. Scanner trajectory_store/.
7. Écrire NbTrajDispo, NomsTraj, NbPointsTraj.
8. Traiter une requête pendante si une variable vaut TRUE.
```

---

### 6.2 Refresh metadata

Déclencheur RAPID :

```rapid
RefreshMetaRequest := TRUE;
```

PC :

```text
1. Reçoit RefreshMetaRequest = TRUE.
2. Scanne trajectory_store/.
3. Liste les fichiers .trajcenter exportables.
4. Écrit NbTrajDispo, NomsTraj, NbPointsTraj.
5. Écrit LastErrorCode = 200001.
6. Écrit TransferError = FALSE.
7. Remet RefreshMetaRequest = FALSE.
```

---

### 6.3 Envoi trajectoire

Déclencheur RAPID :

```rapid
SelectedTrajIndex := k;
SendTrajRequest := TRUE;
```

PC :

```text
1. Reçoit SendTrajRequest = TRUE.
2. Lit SelectedTrajIndex.
3. Charge le .trajcenter correspondant.
4. Lit defaults, toolNames, wobjNames.
5. Résout la trajectoire pour le robot connecté.
6. Valide les limites et contraintes.
7. Écrit TrajReady = FALSE, TransferError = FALSE, TransferProgress = 0.
8. Écrit NbRobtargetsTraj.
9. Écrit RobtTRAJCENTER, vitesses, toolIndex, wobjIndex, zoneType, mvtType, readconfs.
10. Met à jour TransferProgress par blocs.
11. Écrit TransferProgress = 100.
12. Écrit LastErrorCode = 200002.
13. Écrit TrajReady = TRUE.
14. Remet SendTrajRequest = FALSE.
```

En erreur :

```text
TrajReady = FALSE
TransferError = TRUE
LastErrorCode = code
LastError = message court
SendTrajRequest ou RefreshMetaRequest = FALSE
```

---

## 7. Validation avant envoi

Le PC doit refuser l’envoi si l’une des conditions suivantes est vraie :

| Cas | Erreur |
|---|---|
| `SelectedTrajIndex` hors bornes | oui |
| fichier absent ou invalide | oui |
| `NbRobtargetsTraj > 100000` | oui |
| `tcp_speed` absent sans default | oui |
| `tcp_speed <= 0` | oui |
| `zone_type` absent sans default | oui |
| `zone_type` hors liste autorisée | oui |
| `move_type` non normalisable | oui |
| `tool_name` absent sans default | oui |
| `tool_name` introuvable côté robot | oui |
| `wobj_name` absent sans default | oui |
| `wobj_name` introuvable côté robot | oui |
| séquence `MoveC` invalide | oui |
| robtarget non sérialisable | oui |

---

## 8. Codes d’état et d’erreur

Format : `XXXYYY` où `XXX` reprend une famille inspirée HTTP.

| Code | Signification |
|---:|---|
| `200000` | OK |
| `200001` | Metadata refreshed |
| `200002` | Trajectory transferred |
| `400001` | `SelectedTrajIndex` hors bornes |
| `400002` | Fichier trajectoire introuvable |
| `400003` | Format `.trajcenter` invalide |
| `400004` | Trop de points |
| `400005` | `zone_type` invalide |
| `400006` | `move_type` invalide |
| `400007` | Paire `MoveC` invalide |
| `400008` | `tcp_speed` manquant sans default |
| `400009` | `zone_type` manquant sans default |
| `400010` | `tool_name` manquant sans default |
| `400011` | `wobj_name` manquant sans default |
| `400012` | `tool_name` introuvable côté robot |
| `400013` | `wobj_name` introuvable côté robot |
| `400014` | Vitesse invalide |
| `400015` | `readconfs` invalide |
| `400016` | Robtarget invalide |
| `401001` | Authentification RWS refusée |
| `403001` | Mastership refusé |
| `403002` | Écriture RWS interdite |
| `404001` | Symbole RAPID introuvable |
| `404002` | `toolNames` introuvable |
| `404003` | `wobjNames` introuvable |
| `404004` | Store trajectoire introuvable |
| `404005` | Default robot introuvable |
| `408001` | Timeout requête RWS |
| `408002` | Timeout transfert |
| `409001` | Transfert déjà en cours |
| `409002` | État robot incompatible |
| `500001` | Erreur interne client |
| `500002` | Erreur de sérialisation |
| `500003` | Erreur de conversion trajectoire |
| `502001` | Réponse RWS invalide |
| `503001` | Contrôleur indisponible |
| `504001` | Timeout contrôleur |

---

## 9. Règles de conformité

Un client TrajCenter conforme doit :

- utiliser uniquement ABB RWS ;
- s’abonner à `SendTrajRequest` et `RefreshMetaRequest` ;
- ignorer les événements `FALSE` ;
- traiter les événements `TRUE` ;
- remettre la requête traitée à `FALSE` ;
- écrire sous Mastership ;
- libérer le Mastership même en erreur ;
- lire les defaults robot avant l’envoi ;
- lire `toolNames` et `wobjNames` avant l’envoi ;
- ne pas inventer silencieusement `tool`, `wobj`, `speed` ou `zone` ;
- valider `MoveC` par paires non chevauchantes ;
- garder `TrajReady = FALSE` tant que l’envoi n’est pas complet ;
- écrire un code erreur en cas d’échec ;
- ne jamais stocker `9E+9` dans `.trajcenter`.

---
