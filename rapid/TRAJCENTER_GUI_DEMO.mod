MODULE TRAJCENTER_GUI_DEMO

!------------------------------------------------------------------------------
! DATE:          14/09/2026
! AUTHORS:       C. RACINET
! VERSION:       TrajCenter GUI Demo v2.1
!
! DESCRIPTION FR:
!   Interface operateur TrajCenter pour FlexPendant.
!
!   Cette version utilise UIListView afin de proposer une navigation plus
!   ergonomique que les menus TPReadFK.
!
!   Les actions sont affichees dynamiquement selon l'etat de TrajCenter :
!
!       - Rafraichir est toujours disponible ;
!       - Parcourir est disponible si des metadata existent ;
!       - Charger est disponible si une trajectoire est selectionnee ;
!       - Executer est disponible si une trajectoire est chargee ;
!       - Quitter est toujours disponible.
!
!   Les actions indisponibles ne sont pas affichees. Elles ne peuvent donc
!   pas etre selectionnees par l'operateur.
!
! DESCRIPTION EN:
!   TrajCenter operator interface for the FlexPendant.
!
!   This version uses UIListView to provide a more ergonomic navigation
!   experience than TPReadFK menus.
!
!   Actions are displayed dynamically according to the TrajCenter state:
!
!       - Refresh is always available;
!       - Browse is available when metadata exists;
!       - Load is available when a trajectory is selected;
!       - Execute is available when a trajectory is loaded;
!       - Exit is always available.
!
!   Unavailable actions are not displayed and therefore cannot be selected
!   by the operator.
!
! ABB REQUIREMENTS:
!   UIListView and UIMsgBox must be available on the target RobotWare system.
!
! ENCODING:
!   ASCII only. Do not use accents or non-ASCII characters.
!------------------------------------------------------------------------------


!==============================================================================
! CONFIGURATION GUI DEMO / GUI DEMO CONFIGURATION
!==============================================================================

    ! Maximum wait time for a metadata refresh request.
    ! Temps d'attente maximal pour un rafraichissement des metadata.
    CONST num guiRefreshTimeout := 30;

    ! Maximum wait time for a trajectory transfer.
    ! Temps d'attente maximal pour un transfert de trajectoire.
    CONST num guiTransferTimeout := 120;

    ! Motion execution speed parameters.
    ! Parametres de vitesse pour l'execution du mouvement.
    CONST num guiOriSpeed := 500;
    CONST num guiLeaxSpeed := 5000;
    CONST num guiReaxSpeed := 1000;

    ! Maximum number of trajectories displayed by the GUI.
    ! Nombre maximal de trajectoires affichees par la GUI.
    CONST num guiMaxDisplayedTraj := 256;


!==============================================================================
! IDENTIFIANTS ACTIONS / ACTION IDENTIFIERS
!==============================================================================

    ! Internal identifiers used by the dynamic main menu.
    ! Identifiants internes utilises par le menu principal dynamique.

    CONST num guiActionNone := 0;
    CONST num guiActionRefresh := 1;
    CONST num guiActionBrowse := 2;
    CONST num guiActionLoad := 3;
    CONST num guiActionExecute := 4;
    CONST num guiActionExit := 5;


!==============================================================================
! ETAT INTERFACE / INTERFACE STATE
!==============================================================================

    ! Selected trajectory index in the metadata array.
    ! Index de la trajectoire selectionnee dans le tableau de metadata.
    VAR num guiSelTrajIdx := 0;

    ! Selected trajectory name.
    ! Nom de la trajectoire selectionnee.
    VAR string guiSelTrajName := "";

    ! TRUE when the trajectory selected by this GUI has been loaded.
    ! TRUE lorsque la trajectoire selectionnee par cette GUI est chargee.
    VAR bool guiTrajLoaded := FALSE;


!==============================================================================
! OUTIL ET REPERE DEMO / DEMO TOOL AND WORKOBJECT
!==============================================================================

    ! Demonstration tool exposed to TrajCenter.
    ! Outil de demonstration expose a TrajCenter.
    PERS tooldata guiDemoTool := [
        TRUE,
        [[0, 0, 0], [1, 0, 0, 0]],
        [1, [0, 0, 50], [1, 0, 0, 0], 0.01, 0.01, 0.01]
    ];


    ! Demonstration workobject exposed to TrajCenter.
    ! Repere de demonstration expose a TrajCenter.
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
        
        !DeactUnit M7DM1

        TRAJCENTER_InitErrors;
        TRAJCENTER_InitCellConfig;

        ! Initialize TrajCenter and the local GUI state.
        ! Initialiser TrajCenter et l'etat local de la GUI.
        TCGUI_Init;

        WHILE TRUE DO

            ! Build and display the menu according to the current state.
            ! Construire et afficher le menu selon l'etat courant.
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
                ! No valid action was selected.
                ! Aucune action valide n'a ete selectionnee.
                TPWrite "Aucune action selectionnee";

            DEFAULT:
                TPWrite "Action de menu inconnue";

            ENDTEST

        ENDWHILE

    ERROR

        ! Display the RAPID and TrajCenter error information.
        ! Afficher les informations d'erreur RAPID et TrajCenter.
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

        ! Reset TrajCenter error variables.
        ! Reinitialiser les variables d'erreur TrajCenter.
        TPWrite "Initialisation des erreurs";
        TRAJCENTER_InitErrors;

        ! Reset the TrajCenter cell configuration.
        ! Reinitialiser la configuration cellule TrajCenter.
        TPWrite "Initialisation de la cellule";
        TRAJCENTER_InitCellConfig;

        ! Expose the demonstration tool and workobject.
        ! Exposer l'outil et le repere de demonstration.
        TPWrite "Configuration outil et repere";
        TRAJCENTER_UpsertTool "demoTool", guiDemoTool;
        TRAJCENTER_UpsertWobj "demoWobj", guiDemoWobj;

        ! Configure the default trajectory execution parameters.
        ! Configurer les parametres par defaut d'execution.
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

        ! Reset the local GUI selection and loading state.
        ! Reinitialiser la selection et l'etat de chargement local.
        TCGUI_ResetSelection;

        TPWrite "TrajCenter GUI initialise";

    ENDPROC


!==============================================================================
! REINITIALISATION SELECTION / SELECTION RESET
!==============================================================================

    PROC TCGUI_ResetSelection()

        ! Clear the selected and loaded trajectory state.
        ! Effacer l'etat de selection et de chargement.
        guiSelTrajIdx := 0;
        guiSelTrajName := "";
        guiTrajLoaded := FALSE;

    ENDPROC


!==============================================================================
! VALIDATION DE L'ETAT GUI / GUI STATE VALIDATION
!==============================================================================

    FUNC bool TCGUI_HasMetadata()

        ! Metadata is available when at least one trajectory is exposed.
        ! Les metadata sont disponibles lorsqu'au moins une trajectoire existe.
        RETURN nbTrajAvailable > 0;

    ENDFUNC


    FUNC bool TCGUI_HasValidSelection()

        ! Verify that the selected index still belongs to the metadata array.
        ! Verifier que l'index selectionne appartient toujours aux metadata.

        IF guiSelTrajIdx < 1 THEN
            RETURN FALSE;
        ENDIF

        IF guiSelTrajIdx > nbTrajAvailable THEN
            RETURN FALSE;
        ENDIF

        IF guiSelTrajName = "" THEN
            RETURN FALSE;
        ENDIF

        RETURN TRUE;

    ENDFUNC


    FUNC bool TCGUI_CanExecute()

        ! Motion is allowed only when TrajCenter and the GUI both confirm
        ! that a valid trajectory has been loaded.
        !
        ! Le mouvement est autorise uniquement lorsque TrajCenter et la GUI
        ! confirment qu'une trajectoire valide a ete chargee.

        IF trajReady = FALSE THEN
            RETURN FALSE;
        ENDIF

        IF guiTrajLoaded = FALSE THEN
            RETURN FALSE;
        ENDIF

        IF TCGUI_HasValidSelection() = FALSE THEN
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

        ! Display metadata status.
        ! Afficher l'etat des metadata.
        TPWrite "Trajectoires disponibles:" \Num:=nbTrajAvailable;

        ! Display selection status.
        ! Afficher l'etat de la selection.
        IF TCGUI_HasValidSelection() = TRUE THEN

            TPWrite "Trajectoire selectionnee:";
            TPWrite guiSelTrajName;

        ELSE

            TPWrite "Trajectoire selectionnee: aucune";

        ENDIF

        ! Display loading status.
        ! Afficher l'etat du chargement.
        IF TCGUI_CanExecute() = TRUE THEN

            TPWrite "Trajectoire chargee: oui";
            TPWrite "Nombre de points:" \Num:=nbLoadedTrajPoints;

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

        ! Display the current TrajCenter state.
        ! Afficher l'etat courant de TrajCenter.
        TCGUI_ShowStatus;

        ! Clear the fixed-size menu arrays.
        ! Vider les tableaux de menu de taille fixe.
        FOR i FROM 1 TO 5 DO
            menuItems{i} := [stEmpty, stEmpty];
            actionMap{i} := guiActionNone;
        ENDFOR

        itemCount := 0;

        ! Refresh is always available.
        ! Le rafraichissement est toujours disponible.
        itemCount := itemCount + 1;
        menuItems{itemCount}.text := "Rafraichir les metadata";
        actionMap{itemCount} := guiActionRefresh;

        ! Browse is available only when metadata exists.
        ! Le parcours est disponible uniquement si les metadata existent.
        IF TCGUI_HasMetadata() = TRUE THEN

            itemCount := itemCount + 1;
            menuItems{itemCount}.text := "Parcourir les trajectoires";
            actionMap{itemCount} := guiActionBrowse;

        ENDIF

        ! Load is available only after a valid selection.
        ! Le chargement est disponible uniquement apres une selection valide.
        IF TCGUI_HasValidSelection() = TRUE THEN

            itemCount := itemCount + 1;
            menuItems{itemCount}.text := "Charger la trajectoire";
            actionMap{itemCount} := guiActionLoad;

        ENDIF

        ! Execute is available only after a successful load.
        ! L'execution est disponible uniquement apres un chargement reussi.
        IF TCGUI_CanExecute() = TRUE THEN

            itemCount := itemCount + 1;
            menuItems{itemCount}.text := "Executer la trajectoire";
            actionMap{itemCount} := guiActionExecute;

        ENDIF

        ! Exit is always available.
        ! La fermeture est toujours disponible.
        itemCount := itemCount + 1;
        menuItems{itemCount}.text := "Quitter TrajCenter";
        actionMap{itemCount} := guiActionExit;

        ! Display the dynamically generated action list.
        ! Afficher la liste dynamique des actions.
        !
        ! btnOK is a standard ABB button set. When the operator validates
        ! the selected row, buttonAnswer contains resOK.
        !
        ! btnOK est un jeu de boutons ABB standard. Lorsque l'operateur
        ! valide la ligne selectionnee, buttonAnswer contient resOK.
        selectedItem := UIListView(
            \Result:=buttonAnswer
            \Header:="Menu TrajCenter",
            menuItems
            \Buttons:=btnOK
            \Icon:=iconInfo);

        ! Reject the selection if the list was not validated.
        ! Refuser la selection si la liste n'a pas ete validee.
        IF buttonAnswer <> resOK THEN
            RETURN guiActionNone;
        ENDIF

        ! Protect against an invalid or empty list selection.
        ! Proteger le programme contre une selection invalide ou vide.
        IF selectedItem < 1 THEN
            RETURN guiActionNone;
        ENDIF

        IF selectedItem > itemCount THEN
            RETURN guiActionNone;
        ENDIF

        ! Convert the displayed row into an internal action identifier.
        ! Convertir la ligne affichee en identifiant d'action interne.
        RETURN actionMap{selectedItem};

    ENDFUNC


!==============================================================================
! RAFRAICHISSEMENT METADATA / METADATA REFRESH
!==============================================================================

    PROC TCGUI_RefreshMeta()

        TPWrite "";
        TPWrite "Rafraichissement des metadata";

        ! Existing selections become invalid when metadata is refreshed.
        ! Les selections existantes deviennent invalides apres rafraichissement.
        TCGUI_ResetSelection;

        ! Send the refresh request to the Python supervisor.
        ! Envoyer la demande de rafraichissement au superviseur Python.
        TRAJCENTER_RequestMetaRefresh;

        ! Wait until the Python supervisor acknowledges the request.
        ! Attendre l'acquittement du superviseur Python.
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

        ! Defensive check. This action should normally be hidden when no
        ! metadata exists.
        !
        ! Verification defensive. Cette action devrait normalement etre
        ! masquee lorsqu'aucune metadata n'existe.
        IF TCGUI_HasMetadata() = FALSE THEN

            TPWrite "Aucune metadata disponible";

            UIMsgBox
                \Header:="TRAJCENTER",
                "Aucune metadata disponible."
                \MsgLine2:="Rafraichir les metadata."
                \Buttons:=btnOK
                \Icon:=iconInfo;

            RETURN;

        ENDIF

        ! Clear the fixed-size trajectory list.
        ! Vider la liste de trajectoires de taille fixe.
        FOR i FROM 1 TO 256 DO
            trajectoryItems{i} := [stEmpty, stEmpty];
        ENDFOR

        ! Limit the number of displayed items to the UI capacity.
        ! Limiter le nombre d'elements affiches a la capacite de l'interface.
        displayedCount := nbTrajAvailable;

        IF displayedCount > guiMaxDisplayedTraj THEN

            displayedCount := guiMaxDisplayedTraj;
            TPWrite "Liste limitee a:" \Num:=guiMaxDisplayedTraj;

        ENDIF

        ! Fill the list with trajectory names obtained from metadata.
        ! Remplir la liste avec les noms obtenus depuis les metadata.
        FOR i FROM 1 TO displayedCount DO
            trajectoryItems{i}.text := trajectories{i}.name;
        ENDFOR

        ! Display the scrollable trajectory list.
        ! Display the scrollable trajectory list.
        !
        ! btnOKCancel uses the standard results resOK and resCancel.
        ! btnOKCancel utilise les resultats standards resOK et resCancel.
        selectedItem := UIListView(
            \Result:=buttonAnswer
            \Header:="Choix trajectoire",
            trajectoryItems
            \Buttons:=btnOKCancel
            \Icon:=iconInfo);

        ! Return to the main menu when Cancel is pressed.
        ! Retourner au menu principal lorsque Annuler est presse.
        IF buttonAnswer = resCancel THEN
            RETURN;
        ENDIF

        ! Continue only when the standard OK button was pressed.
        ! Continuer uniquement lorsque le bouton standard OK a ete presse.
        IF buttonAnswer <> resOK THEN
            RETURN;
        ENDIF

        ! Reject invalid list selections.
        ! Refuser les selections invalides.
        IF selectedItem < 1 THEN
            RETURN;
        ENDIF

        IF selectedItem > displayedCount THEN
            RETURN;
        ENDIF

        ! Ask for confirmation before changing the current selection.
        ! Demander confirmation avant de modifier la selection courante.
        UIMsgBox
            \Header:="CONFIRMATION",
            "Trajectoire selectionnee:"
            \MsgLine2:=trajectoryItems{selectedItem}.text
            \MsgLine3:="Nombre de points:"
            \MsgLine4:=ValToStr(trajectories{selectedItem}.pointCount)
            \Buttons:=btnOKCancel
            \Icon:=iconWarning
            \Result:=confirmAnswer;

        IF confirmAnswer <> resOK THEN
            TPWrite "Selection annulee";
            RETURN;
        ENDIF

        ! Store the selected metadata entry.
        ! Memoriser l'entree de metadata selectionnee.
        guiSelTrajIdx := selectedItem;
        guiSelTrajName := trajectories{selectedItem}.name;

        ! A new selection is not loaded yet.
        ! Une nouvelle selection n'est pas encore chargee.
        guiTrajLoaded := FALSE;

        TPWrite "";
        TPWrite "Trajectoire selectionnee:";
        TPWrite guiSelTrajName;
        TPWrite "Nombre de points:" \Num:=trajectories{selectedItem}.pointCount;
        TPWrite "Type de procede:" \Num:=trajectories{selectedItem}.processType;

    ENDPROC


!==============================================================================
! CHARGEMENT TRAJECTOIRE / TRAJECTORY LOADING
!==============================================================================

    PROC TCGUI_LoadSelTraj()
        VAR btnres confirmAnswer;

        ! Defensive check. The menu normally hides this action when no
        ! trajectory is selected.
        !
        ! Verification defensive. Le menu masque normalement cette action
        ! lorsqu'aucune trajectoire n'est selectionnee.
        IF TCGUI_HasValidSelection() = FALSE THEN

            TPWrite "Aucune trajectoire selectionnee";

            UIMsgBox
                \Header:="TRAJCENTER",
                "Aucune trajectoire selectionnee."
                \MsgLine2:="Parcourir puis selectionner."
                \Buttons:=btnOK
                \Icon:=iconInfo;

            RETURN;

        ENDIF

        ! Ask for confirmation before starting the transfer.
        ! Demander confirmation avant de lancer le transfert.
        UIMsgBox
            \Header:="CHARGEMENT",
            "Charger la trajectoire:"
            \MsgLine2:=guiSelTrajName
            \MsgLine3:="Nombre de points:"
            \MsgLine4:=ValToStr(trajectories{guiSelTrajIdx}.pointCount)
            \Buttons:=btnOKCancel
            \Icon:=iconWarning
            \Result:=confirmAnswer;

        IF confirmAnswer <> resOK THEN
            TPWrite "Chargement annule";
            RETURN;
        ENDIF

        TPWrite "";
        TPWrite "Chargement de la trajectoire:";
        TPWrite guiSelTrajName;

        ! Clear the local loaded state before starting a new request.
        ! Effacer l'etat de chargement local avant une nouvelle demande.
        guiTrajLoaded := FALSE;

        ! Request the trajectory by its metadata name.
        ! Demander la trajectoire en utilisant son nom de metadata.
        TRAJCENTER_RequestTrajByName guiSelTrajName;

        ! Wait until the transfer is complete and the trajectory is ready.
        ! Attendre la fin du transfert et la disponibilite de la trajectoire.
        TRAJCENTER_WaitTrajectoryReady guiTransferTimeout;

        IF transferError = TRUE THEN

            TPWrite "Erreur de transfert TrajCenter";
            TPWrite "Code:" \Num:=lastErrorCode;
            TPWrite lastError;

            guiTrajLoaded := FALSE;

            UIMsgBox
                \Header:="ERREUR TRANSFERT",
                "Le chargement a echoue."
                \MsgLine2:=lastError
                \Buttons:=btnOK
                \Icon:=iconWarning;

            RETURN;

        ENDIF

        ! Validate both the local GUI state and shared TrajCenter state.
        ! Valider l'etat local et l'etat partage TrajCenter.
        IF trajReady = FALSE THEN

            TPWrite "Transfert termine sans trajectoire prete";
            guiTrajLoaded := FALSE;

            UIMsgBox
                \Header:="ERREUR TRAJECTOIRE",
                "La trajectoire n'est pas prete."
                \MsgLine2:="Verifier le superviseur."
                \Buttons:=btnOK
                \Icon:=iconWarning;

            RETURN;

        ENDIF

        guiTrajLoaded := TRUE;

        TPWrite "Trajectoire chargee";
        TPWrite "Points charges:" \Num:=nbLoadedTrajPoints;
        TPWrite "Dernier code:" \Num:=lastErrorCode;

        UIMsgBox
            \Header:="CHARGEMENT TERMINE",
            "Trajectoire chargee:"
            \MsgLine2:=guiSelTrajName
            \MsgLine3:="Nombre de points:"
            \MsgLine4:=ValToStr(nbLoadedTrajPoints)
            \Buttons:=btnOK
            \Icon:=iconInfo;

    ENDPROC


!==============================================================================
! EXECUTION TRAJECTOIRE / TRAJECTORY EXECUTION
!==============================================================================

    PROC TCGUI_ExecLoaded()
        VAR btnres confirmAnswer;

        ! Defensive check. The menu normally hides this action until a
        ! trajectory has been loaded successfully.
        !
        ! Verification defensive. Le menu masque normalement cette action
        ! tant qu'une trajectoire n'a pas ete chargee correctement.
        IF TCGUI_CanExecute() = FALSE THEN

            TPWrite "Aucune trajectoire prete a executer";

            UIMsgBox
                \Header:="TRAJCENTER",
                "Aucune trajectoire chargee."
                \MsgLine2:="Charger une trajectoire."
                \Buttons:=btnOK
                \Icon:=iconInfo;

            RETURN;

        ENDIF

        ! Display the execution summary and request operator confirmation.
        ! Afficher le recapitulatif et demander confirmation a l'operateur.
        UIMsgBox
            \Header:="CONFIRMATION MOUVEMENT",
            "Executer la trajectoire:"
            \MsgLine2:=guiSelTrajName
            \MsgLine3:="Nombre de points:"
            \MsgLine4:=ValToStr(nbLoadedTrajPoints)
            \MsgLine5:="Le robot va se deplacer."
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

        ! Execute the loaded trajectory without process control.
        ! Executer la trajectoire chargee sans gestion de procede.
        TRAJCENTER_ExecLoadedNoProc guiOriSpeed, guiLeaxSpeed, guiReaxSpeed;

        TPWrite "Execution terminee";

        UIMsgBox
            \Header:="TRAJECTOIRE TERMINEE",
            "Execution terminee."
            \MsgLine2:=guiSelTrajName
            \Buttons:=btnOK
            \Icon:=iconInfo;

    ENDPROC

ENDMODULE
