MODULE TRAJCENTER_Demo

!------------------------------------------------------------------------------
! DATE:          03/08/2026
! AUTHORS:       J. SCHUMACKER, C. RACINET
! VERSION:       TrajCenter Demo v2.0
!
! DESCRIPTION FR:
!   Exemple d’utilisation classique du module système TRAJCENTER.
!
!   Ce module montre comment :
!       - initialiser l’API RAPID TrajCenter ;
!       - déclarer un tool et un workobject utilisateur ;
!       - les exposer à TrajCenter avec Upsert ;
!       - configurer les defaults robot ;
!       - demander un refresh metadata ;
!       - demander le chargement d’une trajectoire ;
!       - exécuter la trajectoire chargée sans process.
!
!   Limite :
!       L’exécution process n’est pas implémentée dans cet exemple.
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
        [0, [0, 0, 0], [1, 0, 0, 0], 0, 0, 0]
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

        !----------------------------------------------------------------------
        ! FR:
        !   Initialisation des erreurs locales RAPID TrajCenter.
        !
        ! EN:
        !   Initialize TrajCenter local RAPID errors.
        !----------------------------------------------------------------------
        TRAJCENTER_InitErrors;


        !----------------------------------------------------------------------
        ! FR:
        !   Initialisation minimale de la configuration cellule TrajCenter.
        !   Ajoute ou met à jour tool0 et wobj0.
        !
        ! EN:
        !   Minimal initialization of TrajCenter cell configuration.
        !   Adds or updates tool0 and wobj0.
        !----------------------------------------------------------------------
        TRAJCENTER_InitCellConfig;


        !----------------------------------------------------------------------
        ! FR:
        !   Exposition du tool et du wobj de démonstration à TrajCenter.
        !
        !   Les fichiers .trajcenter pourront utiliser :
        !       tool_name = "demoTool"
        !       wobj_name = "demoWobj"
        !
        ! EN:
        !   Expose the demo tool and wobj to TrajCenter.
        !
        !   .trajcenter files may use:
        !       tool_name = "demoTool"
        !       wobj_name = "demoWobj"
        !----------------------------------------------------------------------
        TRAJCENTER_UpsertTool "demoTool", demoTool;
        TRAJCENTER_UpsertWobj "demoWobj", demoWobj;


        !----------------------------------------------------------------------
        ! FR:
        !   Configuration des defaults robot.
        !
        !   Ces valeurs seront utilisées par le PC uniquement si les champs
        !   correspondants sont absents dans le fichier .trajcenter.
        !
        ! EN:
        !   Configure robot defaults.
        !
        !   These values will be used by the PC only if corresponding fields are
        !   missing from the .trajcenter file.
        !----------------------------------------------------------------------
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


        !----------------------------------------------------------------------
        ! FR:
        !   Demande de refresh metadata.
        !
        !   Le supervisor PC doit être lancé et abonné à refreshMetaRequest.
        !
        ! EN:
        !   Request metadata refresh.
        !
        !   The PC supervisor must be running and subscribed to
        !   refreshMetaRequest.
        !----------------------------------------------------------------------
        TPWrite "TrajCenter: refresh metadata request";
        TRAJCENTER_RequestMetaRefresh;
        TRAJCENTER_WaitRequestDone demoRefreshTimeout;

        IF transferError THEN
            TPWrite "TrajCenter refresh error";
            TPWrite lastError;
            Stop;
        ENDIF

        TPWrite "TrajCenter: metadata refreshed";
        TPWrite "Available trajectories:" \Num:=nbTrajAvailable;


        !----------------------------------------------------------------------
        ! FR:
        !   Demande de chargement de la trajectoire demoTrajectoryIndex.
        !
        ! EN:
        !   Request loading of trajectory demoTrajectoryIndex.
        !----------------------------------------------------------------------
        TPWrite "TrajCenter: trajectory load request";
        TPWrite "Trajectory index:" \Num:=demoTrajectoryIndex;

        TRAJCENTER_RequestTrajectory demoTrajectoryIndex;
        TRAJCENTER_WaitTrajectoryReady demoTransferTimeout;

        IF transferError THEN
            TPWrite "TrajCenter transfer error";
            TPWrite "Code:" \Num:=lastErrorCode;
            TPWrite lastError;
            Stop;
        ENDIF

        TPWrite "TrajCenter: trajectory ready";
        TPWrite "Loaded points:" \Num:=nbLoadedTrajPoints;


        !----------------------------------------------------------------------
        ! FR:
        !   Exécution de la trajectoire chargée sans process.
        !
        !   Limite :
        !       Les paramètres process éventuellement présents sont ignorés.
        !
        ! EN:
        !   Execute the loaded trajectory without process.
        !
        !   Limitation:
        !       Process parameters, if any, are ignored.
        !----------------------------------------------------------------------
        TPWrite "TrajCenter: execute without process";

        TRAJCENTER_ExecuteLoadedTrajectoryWithoutProcess
            demoOriSpeed,
            demoLeaxSpeed,
            demoReaxSpeed;

        TPWrite "TrajCenter: execution done";

    ERROR
        TPWrite "TrajCenter Demo: RAPID error";
        TPWrite "ERRNO:" \Num:=ERRNO;
        Stop;

    ENDPROC

ENDMODULE
