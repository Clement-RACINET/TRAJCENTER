MODULE TRAJCENTER_CellConfig

! ==============================================================================
! Module: TRAJCENTER_CellConfig
! Purpose:
!   Cell-level persistent tool and workobject configuration for TrajCenter v2.0.
!
! Encoding:
!   This file must be saved as ISO-8859-1, not UTF-8.
!
! PERS policy:
!   trajTools and trajWobjs are PERS because they are cell-level shared data.
!   Maintenance temporary variables are also PERS.
! ==============================================================================


! ==============================================================================
! CELL WORKOBJECTS
! ==============================================================================

    ! Workobjects available for TrajCenter.
    !
    ! The size is cell-dependent and can be modified by the robot programmer.
    ! The PC maps .trajcenter wobj_name values to indexes in this array.
    !
    ! Index convention:
    !   trajWobjs{1} -> wobjIndex = 1
    !   trajWobjs{2} -> wobjIndex = 2
    PERS trajCenterWobj trajWobjs{2}:=[
        [
            "nom1",
            [FALSE, TRUE, "", [[0, 0, 0], [1, 0, 0, 0]], [[0, 0, 0], [1, 0, 0, 0]]]
        ],
        [
            "nom2",
            [FALSE, TRUE, "", [[0, 0, 0], [1, 0, 0, 0]], [[0, 0, 0], [1, 0, 0, 0]]]
        ]
    ];


! ==============================================================================
! CELL TOOLS
! ==============================================================================

    ! Tools available for TrajCenter.
    !
    ! The size is cell-dependent and can be modified by the robot programmer.
    ! The PC maps .trajcenter tool_name values to indexes in this array.
    !
    ! Index convention:
    !   trajTools{1} -> toolIndex = 1
    !   trajTools{2} -> toolIndex = 2
    PERS trajCenterTool trajTools{2}:=[
        [
            "nom3",
            [TRUE, [[0, 0, 0], [1, 0, 0, 0]], [0, [0, 0, 0], [1, 0, 0, 0], 0, 0, 0]]
        ],
        [
            "nom4",
            [TRUE, [[0, 0, 0], [1, 0, 0, 0]], [0, [0, 0, 0], [1, 0, 0, 0], 0, 0, 0]]
        ]
    ];


! ==============================================================================
! MAINTENANCE VARIABLES
! ==============================================================================

    ! Temporary tooldata used by maintenance routines.
    !
    ! This variable is not part of the PC transfer protocol.
    PERS tooldata tempTool := [
        TRUE,
        [[0, 0, 0], [1, 0, 0, 0]],
        [0, [0, 0, 0], [1, 0, 0, 0], 0, 0, 0]
    ];


    ! Temporary wobjdata used by maintenance routines.
    !
    ! This variable is not part of the PC transfer protocol.
    PERS wobjdata tempWobj := [
        FALSE,
        TRUE,
        "",
        [[0, 0, 0], [1, 0, 0, 0]],
        [[0, 0, 0], [1, 0, 0, 0]]
    ];


ENDMODULE
