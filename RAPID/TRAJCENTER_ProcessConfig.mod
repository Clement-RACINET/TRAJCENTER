MODULE TRAJCENTER_ProcessConfig

! ==============================================================================
! Module: TRAJCENTER_ProcessConfig
! Purpose:
!   Process catalog for TrajCenter v2.0.
!
! Encoding:
!   This file must be saved as ISO-8859-1, not UTF-8.
!
! Process convention:
!   0 = NONE
!   1 = ACF
!   2 = AAK
!   3 = PUSHCORP
!   4..255 = RESERVED
!
! Notes:
!   This module contains the robot-side process catalog.
!   Runtime process parameter values are stored in TRAJCENTER_WebServices.
! ==============================================================================


! ==============================================================================
! PROCESS CATALOG
! ==============================================================================

    ! Number of valid entries in processTypes.
    CONST num processTypeCount := 4;


    ! Known process types.
    !
    ! Valid entries:
    !   processTypes{1..processTypeCount}
    !
    ! The numeric id must match the protocol convention:
    !   0 = NONE
    !   1 = ACF
    !   2 = AAK
    !   3 = PUSHCORP
    !   ...
    !
    ! To add a future process:
    !   1. Increment processTypeCount.
    !   2. Add the new entry at the end of processTypes.
    !
    ! Example:
    !   [4, "NEW_PROCESS"]
    VAR trajCenterProcessType processTypes{processTypeCount}:=[
        [0, "NONE"],
        [1, "ACF"],
        [2, "AAK"],
        [3, "PUSHCORP"]
    ];

ENDMODULE
