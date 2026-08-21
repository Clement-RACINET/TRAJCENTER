MODULE TRAJCENTER_DefaultValues

    PROC InitTrajCenterDefaultValues()
        ! Reset request flags to avoid triggering an old pending request.
        TRAJCENTER_WebServices::refreshMetaRequest := FALSE;
        TRAJCENTER_WebServices::sendTrajRequest := FALSE;

        ! Select the first trajectory by default.
        TRAJCENTER_WebServices::selectedTrajIndex := 1;

        ! Enable a safe TCP speed fallback when the .trajcenter file has no speed.
        TRAJCENTER_WebServices::hasDefaultTcpSpeed := TRUE;
        TRAJCENTER_WebServices::defaultTcpSpeed := 100;

        ! Enable a zone fallback when the .trajcenter file has no zone.
        TRAJCENTER_WebServices::hasDefaultZoneType := TRUE;
        TRAJCENTER_WebServices::defaultZoneType := 0;

        ! Enable default tool fallback.
        ! These names must exist in TRAJCENTER_CellConfig/trajTools.
        TRAJCENTER_WebServices::hasDefaultToolName := TRUE;
        TRAJCENTER_WebServices::defaultToolName := "tool0";

        ! Enable default workobject fallback.
        ! These names must exist in TRAJCENTER_CellConfig/trajWobjs.
        TRAJCENTER_WebServices::hasDefaultWobjName := TRUE;
        TRAJCENTER_WebServices::defaultWobjName := "wobj0";

        ! Default motion type used when not provided by the trajectory file.
        TRAJCENTER_WebServices::defaultMoveType := 0;

        ! Read robot configurations when available.
        TRAJCENTER_WebServices::defaultReadConfs := TRUE;

        ! Reset transfer status.
        TRAJCENTER_WebServices::transferError := FALSE;
        TRAJCENTER_WebServices::transferProgress := 0;
        TRAJCENTER_WebServices::lastErrorCode := 200001;
        TRAJCENTER_WebServices::lastError := "";

    ENDPROC

ENDMODULE
