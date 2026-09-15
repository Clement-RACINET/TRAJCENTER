MODULE TRAJCENTER_DEMO

!------------------------------------------------------------------------------
! DATE:          15/09/2026
! AUTHORS:       J. SCHUMACKER, C. RACINET
! VERSION:       TrajCenter Demo v2.1
!
! DESCRIPTION FR:
!   Exemple d'utilisation classique du module systeme TRAJCENTER.
!
!   Ce module montre comment :
!       - initialiser l'API RAPID TrajCenter ;
!       - declarer un tool et un workobject utilisateur ;
!       - les exposer a TrajCenter avec Upsert ;
!       - configurer les valeurs par defaut robot ;
!       - demander un rafraichissement des metadata ;
!       - demander le chargement d'une trajectoire ;
!       - verifier le process transfere ;
!       - executer la trajectoire avec l'API publique unique.
!
!   TRAJCENTER_ExecuteLoaded utilise automatiquement loadedProcessType :
!       - processNone execute uniquement les mouvements ;
!       - un autre process utilise le dispatcher RAPID correspondant.
!
! DESCRIPTION EN:
!   Example of regular usage of the TRAJCENTER system module.
!
!   This module shows how to:
!       - initialize the TrajCenter RAPID API;
!       - declare a user tool and workobject;
!       - expose them to TrajCenter with Upsert;
!       - configure robot defaults;
!       - request metadata refresh;
!       - request trajectory loading;
!       - verify the transferred process;
!       - execute the trajectory through the single public API.
!
!   TRAJCENTER_ExecuteLoaded automatically uses loadedProcessType:
!       - processNone executes motion only;
!       - any other process uses the corresponding RAPID dispatcher.
!
! CURRENT PROCESS CATALOG:
!   The current development controller publishes only process NONE.
!   ACF, AAK and PUSHCORP must be implemented before being published in
!   processTypes.
!
! ENCODING:
!   ASCII only. Do not use accents or non-ASCII characters.
!------------------------------------------------------------------------------


!==============================================================================
! CONFIGURATION DEMO / DEMO CONFIGURATION
!==============================================================================

    CONST string demoTrajectoryName := "000_trajectory_demo";

    CONST num demoRefreshTimeout := 30;
    CONST num demoTransferTimeout := 120;

    CONST num demoOriSpeed := 500;
    CONST num demoLeaxSpeed := 5000;
    CONST num demoReaxSpeed := 1000;


!==============================================================================
! TOOL ET WOBJ DEMO / DEMO TOOL AND WOBJ
!==============================================================================

    PERS tooldata demoTool := [
        TRUE,
        [[0, 0, 0], [1, 0, 0, 0]],
        [1, [0, 0, 50], [1, 0, 0, 0], 0.01, 0.01, 0.01]
    ];


    PERS wobjdata demoWobj := [
        FALSE,
        TRUE,
        "",
        [[0, 0, 0], [1, 0, 0, 0]],
        [[0, 0, 0], [1, 0, 0, 0]]
    ];


!==============================================================================
! PROGRAMME PRINCIPAL / MAIN PROGRAM
!==============================================================================

    PROC main()
        VAR num selectedIndex;
        VAR num selectedProcessType;

        TPWrite "=== TrajCenter Demo START ===";


        !----------------------------------------------------------------------
        ! Initialisation API et configuration cellule
        !----------------------------------------------------------------------

        TPWrite "Step 1: init errors";
        TRAJCENTER_InitErrors;

        TPWrite "Step 2: init cell config";
        TRAJCENTER_InitCellConfig;

        TPWrite "Step 3: expose demo tool/wobj";
        TRAJCENTER_UpsertTool "demoTool", demoTool;
        TRAJCENTER_UpsertWobj "demoWobj", demoWobj;

        TPWrite "Step 4: configure defaults";

        hasDefaultTcpSpeed := TRUE;
        defaultTcpSpeed := 100;

        hasDefaultZoneType := TRUE;
        defaultZoneType := 255;

        hasDefaultToolName := TRUE;
        defaultToolName := "demoTool";

        hasDefaultWobjName := TRUE;
        defaultWobjName := "demoWobj";

        defaultMoveType := moveTypeL;
        defaultReadConfs := TRUE;

        TPWrite "CHECKPOINT 1: config done";
        TPWrite "Press START to request metadata";
        Stop;


        !----------------------------------------------------------------------
        ! Refresh metadata
        !----------------------------------------------------------------------

        TPWrite "Step 5: refresh metadata request";

        TRAJCENTER_RequestMetaRefresh;
        TRAJCENTER_WaitRequestDone demoRefreshTimeout;

        IF transferError = TRUE THEN
            TPWrite "TrajCenter refresh error";
            TPWrite "Code:" \Num:=lastErrorCode;
            TPWrite lastError;
            Stop;
        ENDIF

        TPWrite "Step 5 OK: metadata refreshed";
        TPWrite "Available trajectories:" \Num:=nbTrajAvailable;

        IF nbTrajAvailable < 1 THEN
            TPWrite "No trajectory available";
            Stop;
        ENDIF

        selectedIndex := TRAJCENTER_FindTrajectoryIndex(
            demoTrajectoryName
        );

        IF selectedIndex = 0 THEN
            TPWrite "Demo trajectory not found";
            TPWrite demoTrajectoryName;
            Stop;
        ENDIF

        selectedProcessType := trajectories{selectedIndex}.processType;

        TPWrite "Selected metadata index:" \Num:=selectedIndex;
        TPWrite "Selected process type:" \Num:=selectedProcessType;

        TPWrite "CHECKPOINT 2: metadata OK";
        TPWrite "Press START to load trajectory";
        Stop;


        !----------------------------------------------------------------------
        ! Chargement trajectoire
        !----------------------------------------------------------------------

        TPWrite "Step 6: trajectory load request";
        TPWrite "Trajectory name:";
        TPWrite demoTrajectoryName;

        TRAJCENTER_RequestTrajectory selectedIndex;
        TRAJCENTER_WaitTrajectoryReady demoTransferTimeout;

        IF transferError = TRUE THEN
            TPWrite "TrajCenter transfer error";
            TPWrite "Code:" \Num:=lastErrorCode;
            TPWrite lastError;
            Stop;
        ENDIF

        IF trajReady = FALSE THEN
            TPWrite "Trajectory transfer ended without ready state";
            Stop;
        ENDIF

        IF nbLoadedTrajPoints < 1 THEN
            TPWrite "Loaded trajectory contains no point";
            Stop;
        ENDIF

        IF loadedProcessType <> selectedProcessType THEN
            TPWrite "Loaded process type mismatch";
            TPWrite "Metadata process:" \Num:=selectedProcessType;
            TPWrite "Loaded process:" \Num:=loadedProcessType;
            Stop;
        ENDIF

        TPWrite "Step 6 OK: trajectory ready";
        TPWrite "Loaded points:" \Num:=nbLoadedTrajPoints;
        TPWrite "Loaded process:" \Num:=loadedProcessType;
        TPWrite "Last status code:" \Num:=lastErrorCode;

        TPWrite "CHECKPOINT 3: before motion";
        TPWrite "Verify robot position, then START";
        Stop;


        !----------------------------------------------------------------------
        ! Execution trajectoire
        !----------------------------------------------------------------------

        TPWrite "Step 7: execute loaded trajectory";
        TPWrite "Active process:" \Num:=loadedProcessType;

        TRAJCENTER_ExecuteLoaded
            demoOriSpeed,
            demoLeaxSpeed,
            demoReaxSpeed;

        TPWrite "=== TrajCenter Demo DONE ===";


    ERROR

        TPWrite "TrajCenter Demo: RAPID error";
        TPWrite "ERRNO:" \Num:=ERRNO;
        TPWrite "Last TrajCenter code:" \Num:=lastErrorCode;
        TPWrite lastError;
        TPWrite "Check event log for details";

        Stop;

    ENDPROC

ENDMODULE
