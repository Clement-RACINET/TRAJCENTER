# TrajCenter Validation Matrix

Project: TrajCenter v2.0  
Robot: ABB IRB 6640-180/2.55  
RobotWare: 6.x  
Transport: ABB Robot Web Services only  
Encoding: ASCII only  

Last update: YYYY-MM-DD  
Tester: TODO  
Cell / Station: TODO  

---

## 1. Status legend

Use only these values in the tables.

| Status | Meaning |
|---|---|
| NOT_STARTED | Not tested yet |
| PLANNED | Test planned but not executed |
| PARTIAL | Partially tested |
| SIM_OK | Tested successfully in RobotStudio / simulation |
| ROBOT_OK | Tested successfully on real robot |
| FAILED | Tested and failed |
| BLOCKED | Cannot be tested yet |
| NOT_SUPPORTED | Not supported by current TrajCenter version |
| N/A | Not applicable |

Suggested validation level:

| Level | Meaning |
|---|---|
| L0 | Not reviewed |
| L1 | Code reviewed only |
| L2 | Data transfer tested |
| L3 | Simulation motion tested |
| L4 | Real robot low-speed tested |
| L5 | Real robot production-like tested |

---

## 2. Global validation summary

| Area | Protocol support | RAPID support | PC support | Simulation | Real robot | Level | Notes |
|---|---|---|---|---|---|---|---|
| Metadata refresh | YES | YES | TODO | NOT_STARTED | NOT_STARTED | L0 | |
| Trajectory loading by index | YES | YES | TODO | NOT_STARTED | NOT_STARTED | L0 | |
| Trajectory loading by name | YES | YES | TODO | NOT_STARTED | NOT_STARTED | L0 | |
| MoveL execution | YES | YES | TODO | PARTIAL | NOT_STARTED | L2 | Basic trajectory demo only |
| MoveJ execution | YES | YES | TODO | PARTIAL | NOT_STARTED | L2 | Basic trajectory demo only |
| MoveC execution | YES | YES | TODO | PARTIAL | NOT_STARTED | L2 | Basic trajectory demo only |
| Tool selection by name/index | YES | YES | TODO | PARTIAL | NOT_STARTED | L2 | demoTool tested |
| Wobj selection by name/index | YES | YES | TODO | PARTIAL | NOT_STARTED | L2 | demoWobj tested |
| Default TCP speed fallback | YES | YES | TODO | PARTIAL | NOT_STARTED | L2 | defaultTcpSpeed=100 |
| Default zone fallback | YES | YES | TODO | PARTIAL | NOT_STARTED | L2 | defaultZoneType=255 |
| Default tool fallback | YES | YES | TODO | PARTIAL | NOT_STARTED | L2 | defaultToolName=demoTool |
| Default wobj fallback | YES | YES | TODO | PARTIAL | NOT_STARTED | L2 | defaultWobjName=demoWobj |
| Default readConfs fallback | YES | YES | TODO | PARTIAL | NOT_STARTED | L2 | defaultReadConfs=TRUE |
| Confdata / readConfs TRUE | YES | YES | TODO | NOT_STARTED | NOT_STARTED | L0 | To test next |
| Confdata / readConfs FALSE | YES | YES | TODO | NOT_STARTED | NOT_STARTED | L0 | To test next |
| External axes extax | YES | YES | TODO | NOT_STARTED | NOT_STARTED | L0 | Depends on cell config |
| Zone mapping standard ABB | YES | YES | TODO | NOT_STARTED | NOT_STARTED | L0 | z0..z200, fine |
| Custom zonedata | NO | NO | NO | N/A | N/A | N/A | Not supported |
| TCP speed per point | YES | YES | TODO | NOT_STARTED | NOT_STARTED | L0 | |
| Full speeddata per point | NO | NO | NO | N/A | N/A | N/A | ori/leax/reax are global |
| Process params transfer | YES | STORAGE_ONLY | TODO | NOT_STARTED | NOT_STARTED | L0 | Not applied in motion |
| Process execution ACF | RESERVED | NO | NO | N/A | N/A | N/A | Future |
| Process execution AAK | RESERVED | NO | NO | N/A | N/A | N/A | Future |
| Process execution PUSHCORP | RESERVED | NO | NO | N/A | N/A | N/A | Future |
| RWS timeout handling | YES | YES | TODO | NOT_STARTED | NOT_STARTED | L0 | |
| Python supervisor clean shutdown | N/A | N/A | TODO | NOT_STARTED | NOT_STARTED | L0 | Previous design topic |

---

## 3. Detailed validation items

### 3.1 RWS communication and protocol

| ID | Feature | Expected behavior | Test method | Status | Level | Evidence | Notes |
|---|---|---|---|---|---|---|---|
| RWS-001 | Metadata refresh request | Robot sets refreshMetaRequest TRUE, PC writes trajectories and resets flag | TRAJCENTER_RequestMetaRefresh + WaitRequestDone | PARTIAL | L2 | Demo executed until metadata | |
| RWS-002 | Trajectory request by index | Robot sets selectedTrajIndex and sendTrajRequest TRUE | TRAJCENTER_RequestTrajectory | NOT_STARTED | L0 | | |
| RWS-003 | Trajectory request by name | Robot finds trajectory name then requests by index | TRAJCENTER_RequestTrajByName | PARTIAL | L2 | demoTrajectoryName="000_trajectory_demo" | |
| RWS-004 | transferError handling | RAPID detects transferError TRUE | Force PC-side error | NOT_STARTED | L0 | | |
| RWS-005 | lastErrorCode propagation | PC writes correct code, RAPID displays it | Force validation error | NOT_STARTED | L0 | | |
| RWS-006 | timeout handling | RAPID raises ERR_TRAJCENTER_TIMEOUT | Stop PC supervisor before request | NOT_STARTED | L0 | | |
| RWS-007 | mastership write sequence | PC writes variables under Mastership | Observe PC logs / RobotStudio | NOT_STARTED | L0 | | |
| RWS-008 | request flags reset | PC resets request flags to FALSE | Observe variables after request | PARTIAL | L2 | Demo passed request wait | |

---

### 3.2 Motion type validation

| ID | Feature | Expected behavior | Test method | Status | Level | Evidence | Notes |
|---|---|---|---|---|---|---|---|
| MOT-001 | MoveL basic execution | Execute linear point-to-point motion | trajectory with MoveL only | PARTIAL | L2 | 000_trajectory_demo | Need dedicated test |
| MOT-002 | MoveJ basic execution | Execute joint motion | trajectory with MoveJ only | PARTIAL | L2 | 000_trajectory_demo | Need dedicated test |
| MOT-003 | MoveC basic execution | Execute circular motion using paired MoveC points | trajectory with MoveC pairs | PARTIAL | L2 | 000_trajectory_demo | Need dedicated test |
| MOT-004 | MoveC odd point count error | Raise BAD_MOVEC_PAIR if last MoveC has no pair | invalid trajectory | NOT_STARTED | L0 | | |
| MOT-005 | MoveC pair type mismatch | Raise BAD_MOVEC_PAIR if second point is not MoveC | invalid trajectory | NOT_STARTED | L0 | | |
| MOT-006 | MoveC pair speed mismatch | Raise BAD_MOVEC_PAIR if paired points have different tcpSpeed | invalid trajectory | NOT_STARTED | L0 | | |
| MOT-007 | MoveC pair tool mismatch | Raise BAD_MOVEC_PAIR if paired points have different toolIndex | invalid trajectory | NOT_STARTED | L0 | | |
| MOT-008 | MoveC pair wobj mismatch | Raise BAD_MOVEC_PAIR if paired points have different wobjIndex | invalid trajectory | NOT_STARTED | L0 | | |
| MOT-009 | MoveC pair zone mismatch | Raise BAD_MOVEC_PAIR if paired points have different zoneType | invalid trajectory | NOT_STARTED | L0 | | |
| MOT-010 | MoveC pair readConfs mismatch | Raise BAD_MOVEC_PAIR if paired points have different readConfs | invalid trajectory | NOT_STARTED | L0 | | |
| MOT-011 | Invalid moveType | Raise BAD_MOVE_TYPE or PC rejects transfer | invalid trajectory | NOT_STARTED | L0 | | |

---

### 3.3 Confdata / readConfs validation

Goal: validate that trajData{i}.point.robconf and trajData{i}.readConfs are correctly transferred and applied.

| ID | Feature | Expected behavior | Test method | Status | Level | Evidence | Notes |
|---|---|---|---|---|---|---|---|
| CONF-001 | readConfs TRUE transfer | trajData{i}.readConfs is TRUE after loading | Print/debug loaded points | NOT_STARTED | L0 | | |
| CONF-002 | readConfs FALSE transfer | trajData{i}.readConfs is FALSE after loading | Print/debug loaded points | NOT_STARTED | L0 | | |
| CONF-003 | robtarget confdata transfer | cf1/cf4/cf6/cfx are preserved from source file | Compare source vs RAPID trajData | NOT_STARTED | L0 | | |
| CONF-004 | ConfJ On for MoveJ | MoveJ uses target configuration when readConfs TRUE | Dedicated two-configuration MoveJ trajectory | NOT_STARTED | L0 | | |
| CONF-005 | ConfJ Off for MoveJ | MoveJ may ignore target configuration when readConfs FALSE | Same points, readConfs FALSE | NOT_STARTED | L0 | | |
| CONF-006 | ConfL On for MoveL | MoveL respects linear configuration constraints when readConfs TRUE | Dedicated MoveL trajectory | NOT_STARTED | L0 | | |
| CONF-007 | ConfL Off for MoveL | MoveL may ignore some configuration constraints when readConfs FALSE | Same points, readConfs FALSE | NOT_STARTED | L0 | | |
| CONF-008 | Safe reset after execution | ConfL and ConfJ are reset to On after execution | Inspect code / run small test | L1 | L1 | Code has ConfL On, ConfJ On at end | |
| CONF-009 | Mixed readConfs by point | Each point can switch readConfs independently | Trajectory alternating TRUE/FALSE | NOT_STARTED | L0 | | |
| CONF-010 | MoveC readConfs pair consistency | Pair mismatch is rejected by RAPID | Invalid MoveC pair test | NOT_STARTED | L0 | | |

Recommended first test trajectories:

| Test file | Purpose | Expected result | Status |
|---|---|---|---|
| TC_CONF_J_ON.trajcenter | MoveJ with readConfs TRUE | Robot respects target robconf or errors if impossible | NOT_STARTED |
| TC_CONF_J_OFF.trajcenter | MoveJ with readConfs FALSE | Robot may choose nearest valid configuration | NOT_STARTED |
| TC_CONF_L_ON.trajcenter | MoveL with readConfs TRUE | Linear move respects constraints or errors | NOT_STARTED |
| TC_CONF_L_OFF.trajcenter | MoveL with readConfs FALSE | Linear move may pass with relaxed configuration checking | NOT_STARTED |

---

### 3.4 Zone validation

Current support: numeric zoneType mapped to ABB standard zonedata.

Supported values:

| zoneType | ABB zone | Status | Notes |
|---|---|---|---|
| 0 | z0 | NOT_STARTED | |
| 1 | z1 | NOT_STARTED | |
| 5 | z5 | NOT_STARTED | |
| 10 | z10 | NOT_STARTED | |
| 15 | z15 | NOT_STARTED | |
| 20 | z20 | NOT_STARTED | |
| 30 | z30 | NOT_STARTED | |
| 40 | z40 | NOT_STARTED | |
| 50 | z50 | NOT_STARTED | |
| 60 | z60 | NOT_STARTED | |
| 80 | z80 | NOT_STARTED | |
| 100 | z100 | NOT_STARTED | |
| 150 | z150 | NOT_STARTED | |
| 200 | z200 | NOT_STARTED | |
| 255 | fine | PARTIAL | defaultZoneType=255 in demo |

| ID | Feature | Expected behavior | Test method | Status | Level | Evidence | Notes |
|---|---|---|---|---|---|---|---|
| ZONE-001 | fine / zoneType 255 | Robot stops precisely at point | dedicated trajectory | PARTIAL | L2 | defaultZoneType=255 | |
| ZONE-002 | z0 | Minimal blending | dedicated trajectory | NOT_STARTED | L0 | | |
| ZONE-003 | z10 | Visible small blending | dedicated trajectory | NOT_STARTED | L0 | | |
| ZONE-004 | z50 | Visible blending | dedicated trajectory | NOT_STARTED | L0 | | |
| ZONE-005 | z100 | Larger blending | dedicated trajectory | NOT_STARTED | L0 | | |
| ZONE-006 | invalid zoneType | PC rejects or RAPID raises BAD_ZONE_TYPE | invalid trajectory | NOT_STARTED | L0 | | |
| ZONE-007 | custom zonedata | Not supported | N/A | NOT_SUPPORTED | N/A | | Only numeric standard zoneType supported |

---

### 3.5 Speed validation

Current support:
- tcpSpeed per point.
- oriSpeed, leaxSpeed, reaxSpeed are global parameters of TRAJCENTER_ExecLoadedNoProc.

| ID | Feature | Expected behavior | Test method | Status | Level | Evidence | Notes |
|---|---|---|---|---|---|---|---|
| SPD-001 | default tcpSpeed fallback | Missing tcp_speed uses defaultTcpSpeed if enabled | trajectory without tcp_speed | PARTIAL | L2 | defaultTcpSpeed=100 | |
| SPD-002 | tcpSpeed per point | Each point uses its own tcpSpeed | trajectory with 50/100/200 mm/s | NOT_STARTED | L0 | | |
| SPD-003 | invalid tcpSpeed zero | PC rejects or robot errors | invalid trajectory | NOT_STARTED | L0 | | |
| SPD-004 | invalid tcpSpeed negative | PC rejects or robot errors | invalid trajectory | NOT_STARTED | L0 | | |
| SPD-005 | oriSpeed global | Same oriSpeed applied to all points | run with different demoOriSpeed values | NOT_STARTED | L0 | | |
| SPD-006 | leaxSpeed global | Same leaxSpeed applied to all points | external axis test | NOT_STARTED | L0 | | Needs external axis |
| SPD-007 | reaxSpeed global | Same reaxSpeed applied to all points | external axis test | NOT_STARTED | L0 | | Needs external axis |
| SPD-008 | full speeddata per point | Not supported | N/A | NOT_SUPPORTED | N/A | | Current protocol stores only tcpSpeed |

---

### 3.6 Tool and workobject validation

| ID | Feature | Expected behavior | Test method | Status | Level | Evidence | Notes |
|---|---|---|---|---|---|---|---|
| TW-001 | Init tool0 | TRAJCENTER_InitCellConfig creates or updates tool0 | Run init and inspect trajTools | PARTIAL | L2 | Demo Step 2 | |
| TW-002 | Init wobj0 | TRAJCENTER_InitCellConfig creates or updates wobj0 | Run init and inspect trajWobjs | PARTIAL | L2 | Demo Step 2 | |
| TW-003 | Upsert demoTool | demoTool is stored in trajTools | Run demo Step 3 | PARTIAL | L2 | Demo Step 3 | |
| TW-004 | Upsert demoWobj | demoWobj is stored in trajWobjs | Run demo Step 3 | PARTIAL | L2 | Demo Step 3 | |
| TW-005 | tool_name resolution | PC resolves tool_name to toolIndex | trajectory with demoTool | PARTIAL | L2 | 000_trajectory_demo | |
| TW-006 | wobj_name resolution | PC resolves wobj_name to wobjIndex | trajectory with demoWobj | PARTIAL | L2 | 000_trajectory_demo | |
| TW-007 | missing tool_name without default | PC rejects transfer | disable hasDefaultToolName | NOT_STARTED | L0 | | |
| TW-008 | missing wobj_name without default | PC rejects transfer | disable hasDefaultWobjName | NOT_STARTED | L0 | | |
| TW-009 | unknown tool_name | PC rejects with errorToolNameNotFound | invalid trajectory | NOT_STARTED | L0 | | |
| TW-010 | unknown wobj_name | PC rejects with errorWobjNameNotFound | invalid trajectory | NOT_STARTED | L0 | | |
| TW-011 | Delete tool invalidates trajectory | trajReady becomes FALSE | TRAJCENTER_DeleteTool | NOT_STARTED | L0 | | |
| TW-012 | Delete wobj invalidates trajectory | trajReady becomes FALSE | TRAJCENTER_DeleteWobj | NOT_STARTED | L0 | | |
| TW-013 | Clear tools invalidates trajectory | trajReady becomes FALSE | TRAJCENTER_ClearTools | NOT_STARTED | L0 | | |
| TW-014 | Clear wobjs invalidates trajectory | trajReady becomes FALSE | TRAJCENTER_ClearWobjs | NOT_STARTED | L0 | | |

---

### 3.7 External axes validation

Current RAPID support: robtarget includes extax.  
Actual validation depends on cell configuration and PC export/import.

| ID | Feature | Expected behavior | Test method | Status | Level | Evidence | Notes |
|---|---|---|---|---|---|---|---|
| EXT-001 | extax transfer with 9E9 | Unused external axes remain 9E9 | inspect trajData point.extax | NOT_STARTED | L0 | | |
| EXT-002 | extax transfer with real value | External axis value is preserved | dedicated external axis trajectory | BLOCKED | L0 | | Needs configured external axis |
| EXT-003 | MoveJ with extax | Robot moves external axis with target | dedicated trajectory | BLOCKED | L0 | | |
| EXT-004 | MoveL with extax | Robot moves external axis during linear motion | dedicated trajectory | BLOCKED | L0 | | |
| EXT-005 | leaxSpeed effect | Linear external axis speed uses leaxSpeed | compare speed values | BLOCKED | L0 | | |
| EXT-006 | reaxSpeed effect | Rotational external axis speed uses reaxSpeed | compare speed values | BLOCKED | L0 | | |

---

### 3.8 Default values validation

| ID | Feature | Expected behavior | Test method | Status | Level | Evidence | Notes |
|---|---|---|---|---|---|---|---|
| DEF-001 | hasDefaultTcpSpeed TRUE | Missing tcp_speed uses defaultTcpSpeed | omit tcp_speed | PARTIAL | L2 | Demo config only | Need dedicated trajectory |
| DEF-002 | hasDefaultTcpSpeed FALSE | Missing tcp_speed rejects transfer | omit tcp_speed | NOT_STARTED | L0 | | |
| DEF-003 | hasDefaultZoneType TRUE | Missing zone_type uses defaultZoneType | omit zone_type | PARTIAL | L2 | Demo config only | Need dedicated trajectory |
| DEF-004 | hasDefaultZoneType FALSE | Missing zone_type rejects transfer | omit zone_type | NOT_STARTED | L0 | | |
| DEF-005 | hasDefaultToolName TRUE | Missing tool_name uses defaultToolName | omit tool_name | PARTIAL | L2 | Demo config only | Need dedicated trajectory |
| DEF-006 | hasDefaultToolName FALSE | Missing tool_name rejects transfer | omit tool_name | NOT_STARTED | L0 | | |
| DEF-007 | hasDefaultWobjName TRUE | Missing wobj_name uses defaultWobjName | omit wobj_name | PARTIAL | L2 | Demo config only | Need dedicated trajectory |
| DEF-008 | hasDefaultWobjName FALSE | Missing wobj_name rejects transfer | omit wobj_name | NOT_STARTED | L0 | | |
| DEF-009 | defaultMoveType | Missing move_type uses defaultMoveType if supported by PC | omit move_type | NOT_STARTED | L0 | | Verify PC rule |
| DEF-010 | defaultReadConfs | Missing readconfs uses defaultReadConfs if supported by PC | omit readconfs | NOT_STARTED | L0 | | Verify PC rule |

---

### 3.9 Process parameter validation

Current state:
- Process metadata is supported.
- processParams are transferred and stored.
- Process execution is not implemented in RAPID.

| ID | Feature | Expected behavior | Test method | Status | Level | Evidence | Notes |
|---|---|---|---|---|---|---|---|
| PROC-001 | processTypes readable by PC | PC reads processTypes | PC logs / RWS read | NOT_STARTED | L0 | | |
| PROC-002 | known process accepted | processType NONE/ACF/AAK/PUSHCORP accepted | trajectory metadata | NOT_STARTED | L0 | | |
| PROC-003 | unknown process rejected | PC rejects unknown process | invalid trajectory | NOT_STARTED | L0 | | |
| PROC-004 | processParams transfer | processParams table is written by PC | inspect RAPID variables | NOT_STARTED | L0 | | |
| PROC-005 | processParamIndex per point | point references processParams row | inspect trajData | NOT_STARTED | L0 | | |
| PROC-006 | process execution | No process logic applied in ExecLoadedNoProc | code review + motion test | L1 | L1 | Section 9.8 ignores process | Expected behavior |

---

### 3.10 Error handling validation

| ID | Feature | Expected behavior | Test method | Status | Level | Evidence | Notes |
|---|---|---|---|---|---|---|---|
| ERR-001 | BAD_TRAJ_INDEX | RAISE on invalid trajectory index | call TRAJCENTER_RequestTrajectory 0 | NOT_STARTED | L0 | | |
| ERR-002 | TRAJ_NOT_FOUND | RAISE when name not found | call RequestTrajectoryByName with invalid name | NOT_STARTED | L0 | | |
| ERR-003 | BAD_POINT_INDEX | RAISE when GetPoint index invalid | call GetPoint 0 | NOT_STARTED | L0 | | |
| ERR-004 | BAD_TOOL_INDEX | RAISE when tool index invalid | call LoadExecTool invalid | NOT_STARTED | L0 | | |
| ERR-005 | BAD_WOBJ_INDEX | RAISE when wobj index invalid | call LoadExecWobj invalid | NOT_STARTED | L0 | | |
| ERR-006 | BAD_ZONE_TYPE | RAISE when zoneType invalid | call MakeZone 999 | NOT_STARTED | L0 | | |
| ERR-007 | BAD_MOVE_TYPE | RAISE when moveType invalid | invalid trajectory | NOT_STARTED | L0 | | |
| ERR-008 | BAD_MOVEC_PAIR | RAISE on invalid MoveC pair | invalid trajectory | NOT_STARTED | L0 | | |
| ERR-009 | TIMEOUT | RAISE when PC does not respond | disconnect/stop PC supervisor | NOT_STARTED | L0 | | |
| ERR-010 | NOT_READY | RAISE when executing without loaded trajectory | call ExecLoadedNoProc before load | NOT_STARTED | L0 | | |

---

## 4. Current demo coverage

Demo module: TRAJCENTER_DEMO  
Demo trajectory: 000_trajectory_demo  

| Demo step | Description | Covered items | Status | Notes |
|---|---|---|---|---|
| Step 1 | TRAJCENTER_InitErrors | ERR init | PARTIAL | |
| Step 2 | TRAJCENTER_InitCellConfig | tool0, wobj0 | PARTIAL | |
| Step 3 | Upsert demoTool/demoWobj | tool/wobj exposure | PARTIAL | |
| Step 4 | Configure defaults | default speed/zone/tool/wobj/readConfs | PARTIAL | Config only |
| Step 5 | Metadata refresh | RWS-001 | PARTIAL | |
| Step 6 | Load trajectory by name | RWS-003 | PARTIAL | |
| Step 7 | ExecLoadedNoProc | MoveL/MoveJ/MoveC basic | PARTIAL | Need dedicated separation |

Current statement:
- The demo is useful as an integration smoke test.
- It is not sufficient as a complete validation test.
- Dedicated trajectories are required for confdata, zones, speeds, errors, defaults, and external axes.

---

## 5. Recommended dedicated test trajectories

| File name | Purpose | Priority | Status | Notes |
|---|---|---|---|---|
| TC_SMOKE_MOVES.trajcenter | Basic MoveJ/MoveL/MoveC integration | HIGH | PARTIAL | Current 000_trajectory_demo may cover this |
| TC_CONF_J_ON.trajcenter | MoveJ with readConfs TRUE | HIGH | NOT_STARTED | Next test |
| TC_CONF_J_OFF.trajcenter | MoveJ with readConfs FALSE | HIGH | NOT_STARTED | Next test |
| TC_CONF_L_ON.trajcenter | MoveL with readConfs TRUE | MEDIUM | NOT_STARTED | After MoveJ tests |
| TC_CONF_L_OFF.trajcenter | MoveL with readConfs FALSE | MEDIUM | NOT_STARTED | After MoveJ tests |
| TC_ZONE_FINE.trajcenter | fine / zoneType 255 | HIGH | PARTIAL | |
| TC_ZONE_BLEND.trajcenter | z10/z50/z100 comparison | HIGH | NOT_STARTED | |
| TC_SPEED_TCP.trajcenter | tcpSpeed per point | HIGH | NOT_STARTED | 50/100/200 mm/s |
| TC_DEFAULTS_OK.trajcenter | Missing fields with defaults enabled | MEDIUM | NOT_STARTED | |
| TC_DEFAULTS_FAIL.trajcenter | Missing fields with defaults disabled | MEDIUM | NOT_STARTED | |
| TC_MOVEC_ERRORS.trajcenter | Invalid MoveC pairs | MEDIUM | NOT_STARTED | |
| TC_TOOL_WOBJ_ERRORS.trajcenter | Unknown tool/wobj names | MEDIUM | NOT_STARTED | |
| TC_PROCESS_PARAMS.trajcenter | Process params transfer only | LOW | NOT_STARTED | No process execution |
| TC_EXTAX.trajcenter | External axes | LOW | BLOCKED | Requires external axis configuration |

---

## 6. Test log

Add one line per executed test.

| Date | Tester | Robot/Station | Test ID | Trajectory | Result | Level reached | Notes |
|---|---|---|---|---|---|---|---|
| YYYY-MM-DD | TODO | RobotStudio | RWS-001 | 000_trajectory_demo | PARTIAL | L2 | Metadata refresh passed |
| YYYY-MM-DD | TODO | RobotStudio | RWS-003 | 000_trajectory_demo | PARTIAL | L2 | Load by name passed |
| YYYY-MM-DD | TODO | RobotStudio | MOT-001/002/003 | 000_trajectory_demo | PARTIAL | L2 | Basic motion smoke test |

---

## 7. Open issues

| ID | Issue | Impact | Owner | Status | Notes |
|---|---|---|---|---|---|
| OI-001 | Comments still contain some ASCII-transliterated typos: cete/e/a | LOW | TODO | OPEN | Does not affect RAPID |
| OI-002 | RAPID does not validate tcpSpeed > 0 | MEDIUM | TODO | OPEN | PC should validate; RAPID guard recommended |
| OI-003 | Custom zonedata not supported | LOW | TODO | ACCEPTED | By design in v2.0 |
| OI-004 | Full speeddata per point not supported | LOW | TODO | ACCEPTED | By design in v2.0 |
| OI-005 | Process execution not implemented | MEDIUM | TODO | OPEN | Process params are stored only |

---

## 8. Acceptance criteria for v2.0 motion-only release

Minimum recommended criteria before considering TrajCenter v2.0 motion-only validated:

| Criterion | Required level | Current status |
|---|---|---|
| Metadata refresh works reliably | L4 | NOT_STARTED |
| Trajectory loading by name works reliably | L4 | NOT_STARTED |
| MoveJ executes safely from TrajCenter | L4 | PARTIAL |
| MoveL executes safely from TrajCenter | L4 | PARTIAL |
| MoveC executes safely from TrajCenter | L4 | PARTIAL |
| readConfs TRUE tested on real robot | L4 | NOT_STARTED |
| readConfs FALSE tested on real robot | L4 | NOT_STARTED |
| fine and at least one blended zone tested | L4 | NOT_STARTED |
| tcpSpeed per point tested | L4 | NOT_STARTED |
| tool/wobj name resolution tested | L4 | PARTIAL |
| transfer timeout tested | L3 | NOT_STARTED |
| invalid trajectory rejected cleanly | L3 | NOT_STARTED |

---

## 9. Notes for next test campaign

Next focus: CONFDATA.

Recommended order:
1. Create two known robtargets with different confdata.
2. Test native ABB RAPID with ConfJ On and Off.
3. Export the same targets to TrajCenter.
4. Validate readConfs TRUE transfer.
5. Validate readConfs FALSE transfer.
6. Run first in RobotStudio.
7. Run on real IRB 6640 at reduced speed.