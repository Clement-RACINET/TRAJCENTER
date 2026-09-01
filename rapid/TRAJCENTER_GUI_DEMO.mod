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
!
! ENCODING:
!   ASCII only. Do not use accents or non-ASCII characters.
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

    VAR num guiSelTrajIdx := 0;
    VAR string guiSelTrajName := "";
    VAR bool guiTrajLoaded := FALSE;


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

        TCGUI_Init;

        WHILE TRUE DO
            action := TCGUI_MainMenu();

            TEST action
            CASE 1:
                TCGUI_RefreshMeta;

            CASE 2:
                TCGUI_BrowseTraj;

            CASE 3:
                TCGUI_LoadSelTraj;

            CASE 4:
                TCGUI_ExecLoaded;

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

    PROC TCGUI_Init()
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

        guiSelTrajIdx := 0;
        guiSelTrajName := "";
        guiTrajLoaded := FALSE;

        TPWrite "TrajCenter GUI initialized";
    ENDPROC


!==============================================================================
! MENU PRINCIPAL / MAIN MENU
!==============================================================================

    FUNC num TCGUI_MainMenu()
        VAR num answer;

        TPWrite "";
        TPWrite "=== TrajCenter Menu ===";
        TPWrite "Available trajectories:" \Num:=nbTrajAvailable;

        IF guiSelTrajIdx > 0 THEN
            TPWrite "Selected trajectory:";
            TPWrite guiSelTrajName;
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

    PROC TCGUI_RefreshMeta()
        TPWrite "";
        TPWrite "Refreshing trajectory metadata";

        guiTrajLoaded := FALSE;
        guiSelTrajIdx := 0;
        guiSelTrajName := "";

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

    PROC TCGUI_BrowseTraj()
        VAR num curIdx;
        VAR num answer;
        VAR bool browsing;

        IF nbTrajAvailable < 1 THEN
            TPWrite "No metadata available";
            TPWrite "Use Refresh first";
            RETURN;
        ENDIF

        IF guiSelTrajIdx >= 1 AND guiSelTrajIdx <= nbTrajAvailable THEN
            curIdx := guiSelTrajIdx;
        ELSE
            curIdx := 1;
        ENDIF

        browsing := TRUE;

        WHILE browsing = TRUE DO
            TCGUI_ShowTraj curIdx;

            TPReadFK answer, "Browse trajectories", "Prev", "Next", "Select", "Refresh", "Back";

            TEST answer
            CASE 1:
                IF curIdx > 1 THEN
                    curIdx := curIdx - 1;
                ELSE
                    curIdx := nbTrajAvailable;
                ENDIF

            CASE 2:
                IF curIdx < nbTrajAvailable THEN
                    curIdx := curIdx + 1;
                ELSE
                    curIdx := 1;
                ENDIF

            CASE 3:
                guiSelTrajIdx := curIdx;
                guiSelTrajName := trajectories{curIdx}.name;
                guiTrajLoaded := FALSE;

                TPWrite "Selected trajectory:";
                TPWrite guiSelTrajName;

            CASE 4:
                TCGUI_RefreshMeta;

                IF nbTrajAvailable < 1 THEN
                    browsing := FALSE;
                ELSE
                    curIdx := 1;
                ENDIF

            CASE 5:
                browsing := FALSE;

            DEFAULT:
                TPWrite "Unknown browse action";
            ENDTEST
        ENDWHILE
    ENDPROC


    PROC TCGUI_ShowTraj(num trajIdx)
        TPWrite "";
        TPWrite "=== Trajectory ===";
        TPWrite "Index:" \Num:=trajIdx;
        TPWrite "Total:" \Num:=nbTrajAvailable;

        IF trajIdx < 1 OR trajIdx > nbTrajAvailable THEN
            TPWrite "Invalid trajectory index";
            RETURN;
        ENDIF

        TPWrite "Name:";
        TPWrite trajectories{trajIdx}.name;

        TPWrite "Point count:" \Num:=trajectories{trajIdx}.pointCount;
        TPWrite "Process type:" \Num:=trajectories{trajIdx}.processType;
    ENDPROC


!==============================================================================
! CHARGEMENT TRAJECTOIRE / TRAJECTORY LOADING
!==============================================================================

    PROC TCGUI_LoadSelTraj()
        IF guiSelTrajIdx < 1 THEN
            TPWrite "No trajectory selected";
            TPWrite "Use Browse and Select first";
            RETURN;
        ENDIF

        TPWrite "";
        TPWrite "Loading selected trajectory:";
        TPWrite guiSelTrajName;

        TRAJCENTER_RequestTrajByName guiSelTrajName;
        TRAJCENTER_WaitTrajectoryReady guiTransferTimeout;

        IF transferError = TRUE THEN
            TPWrite "TrajCenter transfer error";
            TPWrite "Code:" \Num:=lastErrorCode;
            TPWrite lastError;
            guiTrajLoaded := FALSE;
            RETURN;
        ENDIF

        guiTrajLoaded := TRUE;

        TPWrite "Trajectory loaded";
        TPWrite "Loaded points:" \Num:=nbLoadedTrajPoints;
        TPWrite "Last status code:" \Num:=lastErrorCode;
    ENDPROC


!==============================================================================
! EXECUTION TRAJECTOIRE / TRAJECTORY EXECUTION
!==============================================================================

    PROC TCGUI_ExecLoaded()
        VAR num answer;

        IF trajReady = FALSE THEN
            TPWrite "No trajectory ready";
            TPWrite "Load a trajectory first";
            RETURN;
        ENDIF

        IF guiTrajLoaded = FALSE THEN
            TPWrite "GUI state: no trajectory loaded";
            TPWrite "Load a trajectory first";
            RETURN;
        ENDIF

        TPWrite "";
        TPWrite "Ready to execute trajectory:";
        TPWrite guiSelTrajName;
        TPWrite "Loaded points:" \Num:=nbLoadedTrajPoints;

        TPReadFK answer, "Start motion?", "Start", "Cancel", "", "", "";

        IF answer <> 1 THEN
            TPWrite "Execution cancelled";
            RETURN;
        ENDIF

        TPWrite "Executing trajectory without process";
        TRAJCENTER_ExecLoadedNoProc guiOriSpeed, guiLeaxSpeed, guiReaxSpeed;

        TPWrite "Trajectory execution done";
    ENDPROC

ENDMODULE
