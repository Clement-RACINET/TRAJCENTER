MODULE TRAJCENTER_GUI_DEMO

!------------------------------------------------------------------------------
! DATE:          30/08/2026
! AUTHORS:       C. RACINET
! VERSION:       TrajCenter GUI Demo v2.0
!
! DESCRIPTION FR:
!   Interface operateur simple sur FlexPendant pour TrajCenter.
!
!   Ce module permet de :
!       - initialiser TrajCenter ;
!       - rafraichir les metadata trajectoires ;
!       - parcourir les trajectoires disponibles ;
!       - selectionner une trajectoire par nom ;
!       - charger la trajectoire selectionnee ;
!       - executer la trajectoire chargee sans process.
!
!   L'interface utilise les fonctions RAPID standards TPWrite et TPReadFK.
!   Ce n'est pas une application FlexPendant custom ScreenMaker.
!
! DESCRIPTION EN:
!   Simple FlexPendant operator interface for TrajCenter.
!
!   This module allows the operator to:
!       - initialize TrajCenter;
!       - refresh trajectory metadata;
!       - browse available trajectories;
!       - select a trajectory by name;
!       - load the selected trajectory;
!       - execute the loaded trajectory without process.
!
!   The interface uses standard RAPID TPWrite and TPReadFK functions.
!   It is not a custom ScreenMaker FlexPendant application.
!------------------------------------------------------------------------------


!==============================================================================
! CONFIGURATION GUI DEMO / GUI DEMO CONFIGURATION
!==============================================================================

    CONST num guiRefreshTimeout := 30;
    CONST num guiTransferTimeout := 120;

    CONST num guiOriSpeed := 500;
    CONST num guiLeaxSpeed := 5000;
    CONST num guiReaxSpeed := 1000;


!==============================================================================
! ETAT INTERFACE / INTERFACE STATE
!==============================================================================

    VAR num guiSelectedTrajIndex := 0;
    VAR string guiSelectedTrajName := "";
    VAR bool guiTrajectoryLoaded := FALSE;


!==============================================================================
! TOOL ET WOBJ DEMO / DEMO TOOL AND WOBJ
!==============================================================================

    PERS tooldata guiDemoTool := [
        TRUE,
        [[0, 0, 0], [1, 0, 0, 0]],
        [1, [0, 0, 50], [1, 0, 0, 0], 0.01, 0.01, 0.01]
    ];


    PERS wobjdata guiDemoWobj := [
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
        VAR num action;

        TRAJCENTER_GUI_Init;

        WHILE TRUE DO
            action := TRAJCENTER_GUI_MainMenu();

            TEST action
            CASE 1:
                TRAJCENTER_GUI_RefreshMetadata;

            CASE 2:
                TRAJCENTER_GUI_BrowseTrajectories;

            CASE 3:
                TRAJCENTER_GUI_LoadSelectedTrajectory;

            CASE 4:
                TRAJCENTER_GUI_ExecuteLoadedTrajectory;

            CASE 5:
                TPWrite "TrajCenter GUI: exit requested";
                RETURN;

            DEFAULT:
                TPWrite "Unknown menu action";
            ENDTEST
        ENDWHILE

    ERROR
        TPWrite "TrajCenter GUI: RAPID error";
        TPWrite "ERRNO:" \Num:=ERRNO;
        TPWrite "Last TrajCenter code:" \Num:=lastErrorCode;
        TPWrite lastError;
        Stop;

    ENDPROC


!==============================================================================
! INITIALISATION / INITIALIZATION
!==============================================================================

    PROC TRAJCENTER_GUI_Init()
        TPWrite "=== TrajCenter GUI START ===";

        TPWrite "Init TrajCenter errors";
        TRAJCENTER_InitErrors;

        TPWrite "Init TrajCenter cell config";
        TRAJCENTER_InitCellConfig;

        TPWrite "Expose GUI demo tool/wobj";
        TRAJCENTER_UpsertTool "demoTool", guiDemoTool;
        TRAJCENTER_UpsertWobj "demoWobj", guiDemoWobj;

        TPWrite "Configure robot defaults";
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

        guiSelectedTrajIndex := 0;
        guiSelectedTrajName := "";
        guiTrajectoryLoaded := FALSE;

        TPWrite "TrajCenter GUI initialized";
    ENDPROC


!==============================================================================
! MENU PRINCIPAL / MAIN MENU
!==============================================================================

    FUNC num TRAJCENTER_GUI_MainMenu()
        VAR num answer;

        TPWrite "";
        TPWrite "=== TrajCenter Menu ===";
        TPWrite "Available trajectories:" \Num:=nbTrajAvailable;

        IF guiSelectedTrajIndex > 0 THEN
            TPWrite "Selected trajectory:";
            TPWrite guiSelectedTrajName;
        ELSE
            TPWrite "Selected trajectory: none";
        ENDIF

        IF trajReady = TRUE THEN
            TPWrite "Loaded trajectory: ready";
            TPWrite "Loaded points:" \Num:=nbLoadedTrajPoints;
        ELSE
            TPWrite "Loaded trajectory: not ready";
        ENDIF

        TPReadFK answer, "Choose action", "Refresh", "Browse", "Load", "Exec", "Exit";

        RETURN answer;
    ENDFUNC


!==============================================================================
! REFRESH METADATA / METADATA REFRESH
!==============================================================================

    PROC TRAJCENTER_GUI_RefreshMetadata()
        TPWrite "";
        TPWrite "Refreshing trajectory metadata...";

        guiTrajectoryLoaded := FALSE;
        guiSelectedTrajIndex := 0;
        guiSelectedTrajName := "";

        TRAJCENTER_RequestMetaRefresh;
        TRAJCENTER_WaitRequestDone guiRefreshTimeout;

        IF transferError = TRUE THEN
            TPWrite "TrajCenter refresh error";
            TPWrite "Code:" \Num:=lastErrorCode;
            TPWrite lastError;
            RETURN;
        ENDIF

        TPWrite "Metadata refreshed";
        TPWrite "Available trajectories:" \Num:=nbTrajAvailable;

        IF nbTrajAvailable < 1 THEN
            TPWrite "No trajectory available";
        ENDIF
    ENDPROC


!==============================================================================
! NAVIGATION TRAJECTOIRES / TRAJECTORY BROWSING
!==============================================================================

    PROC TRAJCENTER_GUI_BrowseTrajectories()
        VAR num currentIndex;
        VAR num answer;
        VAR bool browsing;

        IF nbTrajAvailable < 1 THEN
            TPWrite "No metadata available";
            TPWrite "Use Refresh first";
            RETURN;
        ENDIF

        IF guiSelectedTrajIndex >= 1 AND guiSelectedTrajIndex <= nbTrajAvailable THEN
            currentIndex := guiSelectedTrajIndex;
        ELSE
            currentIndex := 1;
        ENDIF

        browsing := TRUE;

        WHILE browsing = TRUE DO
            TRAJCENTER_GUI_ShowTrajectory currentIndex;

            TPReadFK answer, "Browse trajectories", "Prev", "Next", "Select", "Refresh", "Back";

            TEST answer
            CASE 1:
                IF currentIndex > 1 THEN
                    currentIndex := currentIndex - 1;
                ELSE
                    currentIndex := nbTrajAvailable;
                ENDIF

            CASE 2:
                IF currentIndex < nbTrajAvailable THEN
                    currentIndex := currentIndex + 1;
                ELSE
                    currentIndex := 1;
                ENDIF

            CASE 3:
                guiSelectedTrajIndex := currentIndex;
                guiSelectedTrajName := trajectories{currentIndex}.name;
                guiTrajectoryLoaded := FALSE;

                TPWrite "Selected trajectory:";
                TPWrite guiSelectedTrajName;

            CASE 4:
                TRAJCENTER_GUI_RefreshMetadata;

                IF nbTrajAvailable < 1 THEN
                    browsing := FALSE;
                ELSE
                    currentIndex := 1;
                ENDIF

            CASE 5:
                browsing := FALSE;

            DEFAULT:
                TPWrite "Unknown browse action";
            ENDTEST
        ENDWHILE
    ENDPROC


    PROC TRAJCENTER_GUI_ShowTrajectory(num trajIndex)
        TPWrite "";
        TPWrite "=== Trajectory ===";
        TPWrite "Index:" \Num:=trajIndex;
        TPWrite "Total:" \Num:=nbTrajAvailable;

        IF trajIndex < 1 OR trajIndex > nbTrajAvailable THEN
            TPWrite "Invalid trajectory index";
            RETURN;
        ENDIF

        TPWrite "Name:";
        TPWrite trajectories{trajIndex}.name;

        TPWrite "Point count:" \Num:=trajectories{trajIndex}.pointCount;
        TPWrite "Process type:" \Num:=trajectories{trajIndex}.processType;
    ENDPROC


!==============================================================================
! CHARGEMENT TRAJECTOIRE / TRAJECTORY LOADING
!==============================================================================

    PROC TRAJCENTER_GUI_LoadSelectedTrajectory()
        IF guiSelectedTrajIndex < 1 THEN
            TPWrite "No trajectory selected";
            TPWrite "Use Browse and Select first";
            RETURN;
        ENDIF

        TPWrite "";
        TPWrite "Loading selected trajectory:";
        TPWrite guiSelectedTrajName;

        TRAJCENTER_RequestTrajectoryByName guiSelectedTrajName;
        TRAJCENTER_WaitTrajectoryReady guiTransferTimeout;

        IF transferError = TRUE THEN
            TPWrite "TrajCenter transfer error";
            TPWrite "Code:" \Num:=lastErrorCode;
            TPWrite lastError;
            guiTrajectoryLoaded := FALSE;
            RETURN;
        ENDIF

        guiTrajectoryLoaded := TRUE;

        TPWrite "Trajectory loaded";
        TPWrite "Loaded points:" \Num:=nbLoadedTrajPoints;
        TPWrite "Last status code:" \Num:=lastErrorCode;
    ENDPROC


!==============================================================================
! EXECUTION TRAJECTOIRE / TRAJECTORY EXECUTION
!==============================================================================

    PROC TRAJCENTER_GUI_ExecuteLoadedTrajectory()
        VAR num answer;

        IF trajReady = FALSE THEN
            TPWrite "No trajectory ready";
            TPWrite "Load a trajectory first";
            RETURN;
        ENDIF

        IF guiTrajectoryLoaded = FALSE THEN
            TPWrite "GUI state: no trajectory loaded";
            TPWrite "Load a trajectory first";
            RETURN;
        ENDIF

        TPWrite "";
        TPWrite "Ready to execute trajectory:";
        TPWrite guiSelectedTrajName;
        TPWrite "Loaded points:" \Num:=nbLoadedTrajPoints;

        TPReadFK answer, "Start motion?", "Start", "Cancel", "", "", "";

        IF answer <> 1 THEN
            TPWrite "Execution cancelled";
            RETURN;
        ENDIF

        TPWrite "Executing trajectory without process...";
        TRAJCENTER_ExecLoadedNoProc guiOriSpeed, guiLeaxSpeed, guiReaxSpeed;

        TPWrite "Trajectory execution done";
    ENDPROC

ENDMODULE
