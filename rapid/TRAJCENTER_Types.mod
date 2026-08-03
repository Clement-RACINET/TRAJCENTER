MODULE TRAJCENTER_Types

!------------------------------------------------------------------------------
!DATE:          03/08/2026
!AUTHORS:       J. SCHUMACKER, C. RACINET
!DESCRIPTION:   This module defines the shared protocol constants and RECORD
!               types used by TrajCenter v2.0.
!               It contains global transfer limits, process identifiers,
!               movement type codes, status codes, trajectory metadata records,
!               point transfer records, tool/workobject records and process
!               parameter records.
!               This module must be loaded before all other TrajCenter RAPID
!               modules.
!------------------------------------------------------------------------------

! ==============================================================================
! Module: TRAJCENTER_Types
! Purpose:
!   Shared constants and record definitions for TrajCenter v2.0.
!
! Encoding:
!   This file must be saved as ISO-8859-1, not UTF-8.
!
! Notes:
!   This module should be loaded before all other TrajCenter modules.
! ==============================================================================


! ==============================================================================
! GLOBAL LIMITS
! ==============================================================================

    CONST num maxTrajCount := 256;
    CONST num maxTrajPointCount := 100000;
    CONST num maxProcessParamSetCount := 256;
    CONST num maxProcessParamPerSet := 10;


! ==============================================================================
! PROCESS TYPE CONSTANTS
! ==============================================================================

    CONST num processNone := 0;
    CONST num processAcf := 1;
    CONST num processAak := 2;
    CONST num processPushcorp := 3;


! ==============================================================================
! MOVE TYPE CONSTANTS
! ==============================================================================

    CONST num moveTypeL := 0;
    CONST num moveTypeJ := 1;
    CONST num moveTypeC := 2;


! ==============================================================================
! STATUS CODES
! ==============================================================================

    CONST num statusOk := 200000;
    CONST num statusMetadataRefreshed := 200001;
    CONST num statusTrajectoryTransferred := 200002;


! ==============================================================================
! RECORD DEFINITIONS
! ==============================================================================

    ! Complete data for one trajectory point.
    !
    ! moveType:
    !   0 = MoveL
    !   1 = MoveJ
    !   2 = MoveC
    !
    ! tcpSpeed:
    !   TCP speed in mm/s.
    !
    ! zoneType:
    !   Allowed values:
    !   0, 1, 5, 10, 15, 20, 30, 40, 50, 60,
    !   80, 100, 150, 200, 255.
    !
    ! toolIndex:
    !   1-based index in trajTools.
    !   0 means undefined.
    !
    ! wobjIndex:
    !   1-based index in trajWobjs.
    !   0 means undefined.
    !
    ! processParamIndex:
    !   0 means no process parameter set.
    !   1..256 means row index in processParams.
    RECORD trajCenterPointData
        num moveType;
        robtarget point;
        num tcpSpeed;
        num zoneType;
        bool readConfs;
        num toolIndex;
        num wobjIndex;
        num processParamIndex;
    ENDRECORD


    ! Metadata for one trajectory available on the PC store.
    !
    ! pointCount:
    !   Number of points in this trajectory.
    !
    ! processType:
    !   0 = none
    !   1 = ACF
    !   2 = AAK
    !   3 = PUSHCORP
    !   4..255 = reserved
    RECORD trajCenterTrajMeta
        string name;
        num pointCount;
        num processType;
    ENDRECORD


    ! Workobject entry exposed to TrajCenter.
    RECORD trajCenterWobj
        string name;
        wobjdata value;
    ENDRECORD


    ! Tool entry exposed to TrajCenter.
    RECORD trajCenterTool
        string name;
        tooldata value;
    ENDRECORD


    ! One process parameter.
    !
    ! Convention:
    !   name = "" means unused parameter slot.
    !   value is numeric only.
    RECORD trajCenterProcessParameter
        string name;
        num value;
    ENDRECORD


    ! One known process type.
    !
    ! id:
    !   Numeric process type written in trajectory metadata.
    !
    ! name:
    !   Human-readable process name.
    RECORD trajCenterProcessType
        num id;
        string name;
    ENDRECORD


ENDMODULE
