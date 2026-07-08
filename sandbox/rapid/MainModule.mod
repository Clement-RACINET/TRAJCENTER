MODULE MainModule

  PROC main()
    TRAJCENTER_GetValues;   ! utilise SelectedTrajIndex, TrajReady
    TRAJCENTER_Move;        ! utilise RobtTRAJCENTER, NbRobtargetsTraj
  ENDPROC

  PROC TRAJCENTER_GetValues()
    ! Affiche NomsTraj sur FlexPendant
    ! Écrit SelectedTrajIndex
    ! WaitUntil TrajReady
  ENDPROC

ENDMODULE
