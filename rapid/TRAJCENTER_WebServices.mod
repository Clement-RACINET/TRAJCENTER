MODULE TRAJCENTER_WebServices

!------------------------------------------------------------------------------
!DATE:          03/08/2026
!AUTHORS:       J. SCHUMACKER, C. RACINET
!DESCRIPTION:   This module declares the ABB Robot Web Services exchange
!               variables used by TrajCenter v2.0.
!               The robot raises persistent request flags for metadata refresh
!               and trajectory transfer. The PC subscribes to these flags,
!               reads the robot context, resolves local .trajcenter archives,
!               and writes metadata, trajectory data, process parameters,
!               progress and status variables under Mastership.
!               This module replaces the obsolete TCP/IP communication used in
!               TrajCenter v1.
!------------------------------------------------------------------------------

! ==============================================================================
! Module: TRAJCENTER_WebServices
! Purpose:
!   RWS communication variables for TrajCenter v2.0.
!
! Encoding:
!   This file must be saved as ISO-8859-1, not UTF-8.
!
! Communication model:
!   - The robot raises request flags.
!   - The PC subscribes to these PERS flags through RWS.
!   - The PC writes metadata, trajectory data, process parameters and status.
!   - All PC writes must be performed under Mastership.
!
! PERS policy:
!   Only RWS subscription flags are PERS in this module.
!   Runtime exchange variables are VAR.
! ==============================================================================


! ==============================================================================
! RWS REQUEST VARIABLES
! ==============================================================================

    ! Request trajectory loading from PC.
    !
    ! Robot writes:
    !   selectedTrajIndex := k;
    !   sendTrajRequest := TRUE;
    !
    ! PC behavior:
    !   - receives TRUE event through RWS subscription;
    !   - reads selectedTrajIndex;
    !   - loads and writes the trajectory;
    !   - writes sendTrajRequest := FALSE at the end.
    !
    ! FALSE events must be ignored by the PC.
    PERS bool sendTrajRequest := FALSE;


    ! Request metadata refresh from PC.
    !
    ! Robot writes:
    !   refreshMetaRequest := TRUE;
    !
    ! PC behavior:
    !   - receives TRUE event through RWS subscription;
    !   - scans the PC trajectory store;
    !   - writes nbTrajAvailable and trajectories;
    !   - writes refreshMetaRequest := FALSE at the end.
    !
    ! FALSE events must be ignored by the PC.
    PERS bool refreshMetaRequest := FALSE;


! ==============================================================================
! REQUEST CONTEXT
! ==============================================================================

    ! Selected trajectory index.
    !
    ! Convention:
    !   0 = no selected trajectory.
    !   1..nbTrajAvailable = valid trajectory index.
    VAR num selectedTrajIndex := 0;


! ==============================================================================
! OPERATION STATUS VARIABLES
! ==============================================================================

    ! TRUE only when the content of trajData is complete and executable.
    VAR bool trajReady := FALSE;

    ! TRUE when the latest refresh or transfer failed.
    VAR bool transferError := FALSE;

    ! Last status or error code.
    !
    ! Code format:
    !   XXXYYY
    !
    ! Examples:
    !   200000 = OK
    !   200001 = metadata refreshed
    !   200002 = trajectory transferred
    VAR num lastErrorCode := 200000;

    ! Short human-readable error message.
    VAR string lastError := "";

    ! Transfer progress in percent.
    !
    ! Convention:
    !   0   = not started
    !   100 = completed
    VAR num transferProgress := 0;


! ==============================================================================
! TRAJECTORY METADATA WRITTEN BY PC
! ==============================================================================

    ! Number of valid entries in trajectories.
    !
    ! Valid range:
    !   0..256
    !
    ! Valid entries:
    !   trajectories{1..nbTrajAvailable}
    VAR num nbTrajAvailable := 0;


    ! Metadata for trajectories available in the PC store.
    !
    ! Field:
    !   trajectories{i}.name       = display name
    !   trajectories{i}.pointCount = number of points
    !   trajectories{i}.processType = process type
    VAR trajCenterTrajMeta trajectories{256};


! ==============================================================================
! LOADED TRAJECTORY DATA WRITTEN BY PC
! ==============================================================================

    ! Number of valid entries in trajData for the currently loaded trajectory.
    !
    ! RAPID execution loops must use:
    !   FOR i FROM 1 TO nbLoadedTrajPoints DO
    !       ...
    !   ENDFOR
    VAR num nbLoadedTrajPoints := 0;


    ! Loaded trajectory point data.
    !
    ! Valid entries:
    !   trajData{1..nbLoadedTrajPoints}
    VAR trajCenterPointData trajData{100000};


    ! Process parameter table.
    !
    ! First dimension:
    !   process parameter set index, 1..256.
    !
    ! Second dimension:
    !   parameter slot, 1..10.
    !
    ! Convention:
    !   processParams{i,j}.name = "" means unused slot.
    !
    ! Point mapping:
    !   trajData{k}.processParamIndex = 0
    !       no process parameters for point k.
    !
    !   trajData{k}.processParamIndex = p
    !       process parameters are processParams{p,1..10}.
    VAR trajCenterProcessParameter processParams{256,10};


! ==============================================================================
! DEFAULTS READ BY PC BEFORE TRAJECTORY TRANSFER
! ==============================================================================

    ! Default TCP speed.
    !
    ! If hasDefaultTcpSpeed = FALSE and tcp_speed is missing in .trajcenter,
    ! the PC must refuse the transfer.
    VAR bool hasDefaultTcpSpeed := FALSE;
    VAR num defaultTcpSpeed := 0;


    ! Default zone type.
    !
    ! If hasDefaultZoneType = FALSE and zone_type is missing in .trajcenter,
    ! the PC must refuse the transfer.
    !
    ! Allowed values:
    !   0, 1, 5, 10, 15, 20, 30, 40, 50, 60,
    !   80, 100, 150, 200, 255.
    VAR bool hasDefaultZoneType := FALSE;
    VAR num defaultZoneType := 255;


    ! Default tool name.
    !
    ! If hasDefaultToolName = TRUE, defaultToolName must exist in trajTools.
    ! Otherwise the PC must refuse the transfer when tool_name is missing.
    VAR bool hasDefaultToolName := FALSE;
    VAR string defaultToolName := "";


    ! Default workobject name.
    !
    ! If hasDefaultWobjName = TRUE, defaultWobjName must exist in trajWobjs.
    ! Otherwise the PC must refuse the transfer when wobj_name is missing.
    VAR bool hasDefaultWobjName := FALSE;
    VAR string defaultWobjName := "";


    ! Default movement type.
    !
    ! Convention:
    !   0 = MoveL
    !   1 = MoveJ
    !   2 = MoveC
    !
    ! Recommended default:
    !   0 = MoveL
    VAR num defaultMoveType := 0;


    ! Default readConfs value.
    !
    ! The PC may override this rule during import:
    !   - if confdata is present and read_confs is missing: TRUE
    !   - if confdata is missing and read_confs is missing: FALSE
    VAR bool defaultReadConfs := TRUE;


ENDMODULE
