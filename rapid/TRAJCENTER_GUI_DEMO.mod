MODULE TRAJCENTER_GUI_DEMO

!------------------------------------------------------------------------------
! DATE:          15/09/2026
! AUTHORS:       C. RACINET
! VERSION:       TrajCenter GUI Demo v2.2
!
! DESCRIPTION FR:
!   Interface operateur TrajCenter pour FlexPendant.
!
!   Cette version utilise UIListView et l'API publique unique
!   TRAJCENTER_ExecuteLoaded.
!
!   Le type de process est transfere par le superviseur Python dans
!   loadedProcessType. L'execution RAPID selectionne automatiquement le
!   dispatcher correspondant.
!
!   Les actions sont affichees dynamiquement selon l'etat de TrajCenter :
!
!       - Rafraichir est toujours disponible ;
!       - Parcourir est disponible si des metadata existent ;
!       - Charger est disponible si une trajectoire est selectionnee ;
!       - Executer est disponible si une trajectoire est chargee ;
!       - Quitter est toujours disponible.
!
! DESCRIPTION EN:
!   TrajCenter operator interface for the FlexPendant.
!
!   This version uses UIListView and the single public
!   TRAJCENTER_ExecuteLoaded API.
!
!   The Python supervisor transfers the process type into loadedProcessType.
!   RAPID execution automatically selects the corresponding dispatcher.
!
! ABB REQUIREMENTS:
!   UIListView and UIMsgBox must be available on the target RobotWare system.
!
! CURRENT PROCESS CATALOG:
!   The current development controller publishes only process NONE.
!   Process trajectories are rejected during resolution until their RAPID
!   implementation is added to processTypes.
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

    CONST num guiMaxDisplayedTraj := 256;


!==============================================================================
! IDENTIFIANTS ACTIONS / ACTION IDENTIFIERS
!==============================================================================

    CONST num guiActionNone := 0;
    CONST num guiActionRefresh := 1;
    CONST num guiActionBrowse := 2;
    CONST num guiActionLoad := 3;
    CONST num guiActionExecute := 4;
    CONST num guiActionExit := 5;


!==============================================================================
! ETAT INTERFACE / INTERFACE STATE
!==============================================================================

    VAR num guiSelTrajIdx := 0;
    VAR string guiSelTrajName := "";
    VAR num guiSelProcessType := processNone;
    VAR bool guiTrajLoaded := FALSE;


!==============================================================================
! OUTIL ET REPERE DEMO / DEMO TOOL AND WORKOBJECT
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

            CASE guiActionRefresh:
                TCGUI_RefreshMeta;

            CASE guiActionBrowse:
                TCGUI_BrowseTraj;

            CASE guiActionLoad:
                TCGUI_LoadSelTraj;

            CASE guiActionExecute:
                TCGUI_ExecLoaded;

            CASE guiActionExit:
                TPWrite "TrajCenter GUI: fermeture demandee";
                RETURN;

            CASE guiActionNone:
                TPWrite "Aucune action selectionnee";

            DEFAULT:
                TPWrite "Action de menu inconnue";

            ENDTEST

        ENDWHILE

    ERROR

        TPWrite "TrajCenter GUI: erreur RAPID";
        TPWrite "ERRNO:" \Num:=ERRNO;
        TPWrite "Dernier code TrajCenter:" \Num:=lastErrorCode;
        TPWrite lastError;

        Stop;

    ENDPROC


!==============================================================================
! INITIALISATION / INITIALIZATION
!==============================================================================

    PROC TCGUI_Init()

        TPWrite "";
        TPWrite "=== DEMARRAGE TRAJCENTER GUI ===";

        TPWrite "Initialisation des erreurs";
        TRAJCENTER_InitErrors;

        TPWrite "Initialisation de la cellule";
        TRAJCENTER_InitCellConfig;

        TPWrite "Configuration outil et repere";
        TRAJCENTER_UpsertTool "demoTool", guiDemoTool;
        TRAJCENTER_UpsertWobj "demoWobj", guiDemoWobj;

        TPWrite "Configuration des valeurs par defaut";

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

        TCGUI_ResetSelection;

        TPWrite "TrajCenter GUI initialise";

    ENDPROC


!==============================================================================
! REINITIALISATION SELECTION / SELECTION RESET
!==============================================================================

    PROC TCGUI_ResetSelection()

        guiSelTrajIdx := 0;
        guiSelTrajName := "";
        guiSelProcessType := processNone;
        guiTrajLoaded := FALSE;

    ENDPROC


!==============================================================================
! VALIDATION DE L'ETAT GUI / GUI STATE VALIDATION
!==============================================================================

    FUNC bool TCGUI_HasMetadata()

        RETURN nbTrajAvailable > 0;

    ENDFUNC


    FUNC bool TCGUI_HasValidSelection()

        IF guiSelTrajIdx < 1 THEN
            RETURN FALSE;
        ENDIF

        IF guiSelTrajIdx > nbTrajAvailable THEN
            RETURN FALSE;
        ENDIF

        IF guiSelTrajName = "" THEN
            RETURN FALSE;
        ENDIF

        IF trajectories{guiSelTrajIdx}.name <> guiSelTrajName THEN
            RETURN FALSE;
        ENDIF

        IF trajectories{guiSelTrajIdx}.processType <> guiSelProcessType THEN
            RETURN FALSE;
        ENDIF

        RETURN TRUE;

    ENDFUNC


    FUNC bool TCGUI_CanExecute()

        IF trajReady = FALSE THEN
            RETURN FALSE;
        ENDIF

        IF guiTrajLoaded = FALSE THEN
            RETURN FALSE;
        ENDIF

        IF TCGUI_HasValidSelection() = FALSE THEN
            RETURN FALSE;
        ENDIF

        IF loadedProcessType <> guiSelProcessType THEN
            RETURN FALSE;
        ENDIF

        IF nbLoadedTrajPoints < 1 THEN
            RETURN FALSE;
        ENDIF

        RETURN TRUE;

    ENDFUNC


!==============================================================================
! AFFICHAGE ETAT / STATE DISPLAY
!==============================================================================

    PROC TCGUI_ShowStatus()

        TPWrite "";
        TPWrite "=== ETAT TRAJCENTER ===";

        TPWrite "Trajectoires disponibles:" \Num:=nbTrajAvailable;

        IF TCGUI_HasValidSelection() = TRUE THEN

            TPWrite "Trajectoire selectionnee:";
            TPWrite guiSelTrajName;
            TPWrite "Process selectionne:" \Num:=guiSelProcessType;

        ELSE

            TPWrite "Trajectoire selectionnee: aucune";

        ENDIF

        IF TCGUI_CanExecute() = TRUE THEN

            TPWrite "Trajectoire chargee: oui";
            TPWrite "Nombre de points:" \Num:=nbLoadedTrajPoints;
            TPWrite "Process charge:" \Num:=loadedProcessType;

        ELSE

            TPWrite "Trajectoire chargee: non";

        ENDIF

    ENDPROC


!==============================================================================
! MENU PRINCIPAL DYNAMIQUE / DYNAMIC MAIN MENU
!==============================================================================

    FUNC num TCGUI_MainMenu()
        VAR listitem menuItems{5};
        VAR num actionMap{5};
        VAR num itemCount;
        VAR num selectedItem;
        VAR num i;
        VAR btnres buttonAnswer;

        TCGUI_ShowStatus;

        FOR i FROM 1 TO 5 DO
            menuItems{i} := [stEmpty, stEmpty];
            actionMap{i} := guiActionNone;
        ENDFOR

        itemCount := 0;

        itemCount := itemCount + 1;
        menuItems{itemCount}.text := "Rafraichir les metadata";
        actionMap{itemCount} := guiActionRefresh;

        IF TCGUI_HasMetadata() = TRUE THEN

            itemCount := itemCount + 1;
            menuItems{itemCount}.text := "Parcourir les trajectoires";
            actionMap{itemCount} := guiActionBrowse;

        ENDIF

        IF TCGUI_HasValidSelection() = TRUE THEN

            itemCount := itemCount + 1;
            menuItems{itemCount}.text := "Charger la trajectoire";
            actionMap{itemCount} := guiActionLoad;

        ENDIF

        IF TCGUI_CanExecute() = TRUE THEN

            itemCount := itemCount + 1;
            menuItems{itemCount}.text := "Executer la trajectoire";
            actionMap{itemCount} := guiActionExecute;

        ENDIF

        itemCount := itemCount + 1;
        menuItems{itemCount}.text := "Quitter TrajCenter";
        actionMap{itemCount} := guiActionExit;

        selectedItem := UIListView(
            \Result:=buttonAnswer
            \Header:="Menu TrajCenter",
            menuItems
            \Buttons:=btnOK
            \Icon:=iconInfo);

        IF buttonAnswer <> resOK THEN
            RETURN guiActionNone;
        ENDIF

        IF selectedItem < 1 OR selectedItem > itemCount THEN
            RETURN guiActionNone;
        ENDIF

        RETURN actionMap{selectedItem};

    ENDFUNC


!==============================================================================
! RAFRAICHISSEMENT METADATA / METADATA REFRESH
!==============================================================================

    PROC TCGUI_RefreshMeta()

        TPWrite "";
        TPWrite "Rafraichissement des metadata";

        TCGUI_ResetSelection;

        TRAJCENTER_RequestMetaRefresh;
        TRAJCENTER_WaitRequestDone guiRefreshTimeout;

        IF transferError = TRUE THEN

            TPWrite "Erreur de rafraichissement";
            TPWrite "Code:" \Num:=lastErrorCode;
            TPWrite lastError;

            UIMsgBox
                \Header:="ERREUR TRAJCENTER",
                "Le rafraichissement a echoue."
                \MsgLine2:=lastError
                \Buttons:=btnOK
                \Icon:=iconWarning;

            RETURN;

        ENDIF

        TPWrite "Metadata rafraichies";
        TPWrite "Trajectoires disponibles:" \Num:=nbTrajAvailable;

        IF nbTrajAvailable < 1 THEN

            UIMsgBox
                \Header:="TRAJCENTER",
                "Aucune trajectoire disponible."
                \MsgLine2:="Verifier le dossier de stockage."
                \Buttons:=btnOK
                \Icon:=iconInfo;

        ELSE

            UIMsgBox
                \Header:="TRAJCENTER",
                "Metadata rafraichies."
                \MsgLine2:="Trajectoires disponibles:"
                \MsgLine3:=ValToStr(nbTrajAvailable)
                \Buttons:=btnOK
                \Icon:=iconInfo;

        ENDIF

    ENDPROC


!==============================================================================
! SELECTION TRAJECTOIRE / TRAJECTORY SELECTION
!==============================================================================

    PROC TCGUI_BrowseTraj()
        VAR listitem trajectoryItems{256};
        VAR num displayedCount;
        VAR num selectedItem;
        VAR num i;
        VAR btnres buttonAnswer;
        VAR btnres confirmAnswer;

        IF TCGUI_HasMetadata() = FALSE THEN

            UIMsgBox
                \Header:="TRAJCENTER",
                "Aucune metadata disponible."
                \MsgLine2:="Rafraichir les metadata."
                \Buttons:=btnOK
                \Icon:=iconInfo;

            RETURN;

        ENDIF

        FOR i FROM 1 TO 256 DO
            trajectoryItems{i} := [stEmpty, stEmpty];
        ENDFOR

        displayedCount := nbTrajAvailable;

        IF displayedCount > guiMaxDisplayedTraj THEN
            displayedCount := guiMaxDisplayedTraj;
            TPWrite "Liste limitee a:" \Num:=guiMaxDisplayedTraj;
        ENDIF

        FOR i FROM 1 TO displayedCount DO
            trajectoryItems{i}.text := trajectories{i}.name;
        ENDFOR

        selectedItem := UIListView(
            \Result:=buttonAnswer
            \Header:="Choix trajectoire",
            trajectoryItems
            \Buttons:=btnOKCancel
            \Icon:=iconInfo);

        IF buttonAnswer <> resOK THEN
            RETURN;
        ENDIF

        IF selectedItem < 1 OR selectedItem > displayedCount THEN
            RETURN;
        ENDIF

        UIMsgBox
            \Header:="CONFIRMATION",
            "Trajectoire selectionnee:"
            \MsgLine2:=trajectoryItems{selectedItem}.text
            \MsgLine3:="Nombre de points:"
            \MsgLine4:=ValToStr(trajectories{selectedItem}.pointCount)
            \MsgLine5:="Process: "+ValToStr(trajectories{selectedItem}.processType)
            \Buttons:=btnOKCancel
            \Icon:=iconWarning
            \Result:=confirmAnswer;

        IF confirmAnswer <> resOK THEN
            TPWrite "Selection annulee";
            RETURN;
        ENDIF

        guiSelTrajIdx := selectedItem;
        guiSelTrajName := trajectories{selectedItem}.name;
        guiSelProcessType := trajectories{selectedItem}.processType;
        guiTrajLoaded := FALSE;

        TPWrite "";
        TPWrite "Trajectoire selectionnee:";
        TPWrite guiSelTrajName;
        TPWrite "Nombre de points:" \Num:=trajectories{selectedItem}.pointCount;
        TPWrite "Type de process:" \Num:=guiSelProcessType;

    ENDPROC


!==============================================================================
! CHARGEMENT TRAJECTOIRE / TRAJECTORY LOADING
!==============================================================================

    PROC TCGUI_LoadSelTraj()
        VAR btnres confirmAnswer;

        IF TCGUI_HasValidSelection() = FALSE THEN

            UIMsgBox
                \Header:="TRAJCENTER",
                "Aucune trajectoire selectionnee."
                \MsgLine2:="Parcourir puis selectionner."
                \Buttons:=btnOK
                \Icon:=iconInfo;

            RETURN;

        ENDIF

        UIMsgBox
            \Header:="CHARGEMENT",
            "Charger la trajectoire:"
            \MsgLine2:=guiSelTrajName
            \MsgLine3:="Nombre de points:"
            \MsgLine4:=ValToStr(trajectories{guiSelTrajIdx}.pointCount)
            \MsgLine5:="Process: "+ValToStr(guiSelProcessType)
            \Buttons:=btnOKCancel
            \Icon:=iconWarning
            \Result:=confirmAnswer;

        IF confirmAnswer <> resOK THEN
            TPWrite "Chargement annule";
            RETURN;
        ENDIF

        guiTrajLoaded := FALSE;

        TPWrite "";
        TPWrite "Chargement de la trajectoire:";
        TPWrite guiSelTrajName;

        TRAJCENTER_RequestTrajByName guiSelTrajName;
        TRAJCENTER_WaitTrajectoryReady guiTransferTimeout;

        IF transferError = TRUE THEN

            TPWrite "Erreur de transfert TrajCenter";
            TPWrite "Code:" \Num:=lastErrorCode;
            TPWrite lastError;

            UIMsgBox
                \Header:="ERREUR TRANSFERT",
                "Le chargement a echoue."
                \MsgLine2:=lastError
                \Buttons:=btnOK
                \Icon:=iconWarning;

            RETURN;

        ENDIF

        IF trajReady = FALSE OR nbLoadedTrajPoints < 1 THEN

            UIMsgBox
                \Header:="ERREUR TRAJECTOIRE",
                "La trajectoire n'est pas prete."
                \MsgLine2:="Verifier le superviseur."
                \Buttons:=btnOK
                \Icon:=iconWarning;

            RETURN;

        ENDIF

        IF loadedProcessType <> guiSelProcessType THEN

            TPWrite "Incoherence du type de process";
            TPWrite "Selection:" \Num:=guiSelProcessType;
            TPWrite "Charge:" \Num:=loadedProcessType;

            UIMsgBox
                \Header:="ERREUR PROCESS",
                "Le process charge est incoherent."
                \MsgLine2:="Rafraichir les metadata."
                \Buttons:=btnOK
                \Icon:=iconWarning;

            RETURN;

        ENDIF

        guiTrajLoaded := TRUE;

        TPWrite "Trajectoire chargee";
        TPWrite "Points charges:" \Num:=nbLoadedTrajPoints;
        TPWrite "Process charge:" \Num:=loadedProcessType;
        TPWrite "Dernier code:" \Num:=lastErrorCode;

        UIMsgBox
            \Header:="CHARGEMENT TERMINE",
            "Trajectoire chargee:"
            \MsgLine2:=guiSelTrajName
            \MsgLine3:="Nombre de points:"
            \MsgLine4:=ValToStr(nbLoadedTrajPoints)
            \MsgLine5:="Process: "+ValToStr(loadedProcessType)
            \Buttons:=btnOK
            \Icon:=iconInfo;

    ENDPROC


!==============================================================================
! EXECUTION TRAJECTOIRE / TRAJECTORY EXECUTION
!==============================================================================

    PROC TCGUI_ExecLoaded()
        VAR btnres confirmAnswer;

        IF TCGUI_CanExecute() = FALSE THEN

            UIMsgBox
                \Header:="TRAJCENTER",
                "Aucune trajectoire chargee."
                \MsgLine2:="Charger une trajectoire."
                \Buttons:=btnOK
                \Icon:=iconInfo;

            RETURN;

        ENDIF

        UIMsgBox
            \Header:="CONFIRMATION MOUVEMENT",
            "Executer la trajectoire:"
            \MsgLine2:=guiSelTrajName
            \MsgLine3:="Nombre de points:"
            \MsgLine4:=ValToStr(nbLoadedTrajPoints)
            \MsgLine5:="Process: "+ValToStr(loadedProcessType)
            \Buttons:=btnOKCancel
            \Icon:=iconWarning
            \Result:=confirmAnswer;

        IF confirmAnswer <> resOK THEN
            TPWrite "Execution annulee";
            RETURN;
        ENDIF

        TPWrite "";
        TPWrite "Execution de la trajectoire:";
        TPWrite guiSelTrajName;
        TPWrite "Process actif:" \Num:=loadedProcessType;

        TRAJCENTER_ExecuteLoaded
            guiOriSpeed,
            guiLeaxSpeed,
            guiReaxSpeed;

        TPWrite "Execution terminee";

        UIMsgBox
            \Header:="TRAJECTOIRE TERMINEE",
            "Execution terminee."
            \MsgLine2:=guiSelTrajName
            \Buttons:=btnOK
            \Icon:=iconInfo;

    ENDPROC

ENDMODULE
