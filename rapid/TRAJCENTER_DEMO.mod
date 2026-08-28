MODULE TRAJCENTER_DEMO

!------------------------------------------------------------------------------
! DATE:          03/08/2026
! AUTHORS:       J. SCHUMACKER, C. RACINET
! VERSION:       TrajCenter Demo v2.0
!
! DESCRIPTION FR:
!   Exemple d'utilisation classique du module systeme TRAJCENTER.
!
!   Ce module montre comment :
!       - initialiser l'API RAPID TrajCenter ;
!       - declarer un tool et un workobject utilisateur ;
!       - les exposer a TrajCenter avec Upsert ;
!       - configurer les defaults robot ;
!       - demander un refresh metadata ;
!       - demander le chargement d'une trajectoire ;
!       - executer la trajectoire chargee sans process.
!
!   Limite :
!       L'execution process n'est pas implementee dans cet exemple.
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
!       - execute the loaded trajectory without process.
!
!   Limitation:
!       Process execution is not implemented in this example.
!------------------------------------------------------------------------------


!==============================================================================
! CONFIGURATION DEMO / DEMO CONFIGURATION
!==============================================================================

    CONST num demoTrajectoryIndex := 1;
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

        TPWrite "CHECKPOINT 2: metadata OK";
        TPWrite "Press START to load trajectory";
        Stop;


        !----------------------------------------------------------------------
        ! Chargement trajectoire
        !----------------------------------------------------------------------
        TPWrite "Step 6: trajectory load request";
        TPWrite "Trajectory index:" \Num:=demoTrajectoryIndex;

        TRAJCENTER_RequestTrajectory demoTrajectoryIndex;
        TRAJCENTER_WaitTrajectoryReady demoTransferTimeout;

        IF transferError = TRUE THEN
            TPWrite "TrajCenter transfer error";
            TPWrite "Code:" \Num:=lastErrorCode;
            TPWrite lastError;
            Stop;
        ENDIF

        TPWrite "Step 6 OK: trajectory ready";
        TPWrite "Loaded points:" \Num:=nbLoadedTrajPoints;
        TPWrite "Last status code:" \Num:=lastErrorCode;

        TPWrite "CHECKPOINT 3: before motion";
        TPWrite "Verify robot position, then START";
        Stop;


        !----------------------------------------------------------------------
        ! Exécution mouvement
        !----------------------------------------------------------------------
        TPWrite "Step 7: execute without process";
        TRAJCENTER_ExecLoadedNoProc demoOriSpeed, demoLeaxSpeed, demoReaxSpeed;

        TPWrite "=== TrajCenter Demo DONE ===";

    ERROR
        TPWrite "TrajCenter Demo: RAPID error";
        TPWrite "ERRNO:" \Num:=ERRNO;
        TPWrite "Check event log for details";
        Stop;

    ENDPROC

ENDMODULE
