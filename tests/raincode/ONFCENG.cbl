      *ONFLY probe 1b of 3 (D-129): the LINKed-to side of the COMMAREA.
      *
      *This stands in for ONFLYENG.  It computes nothing - the engine is
      *C and lives elsewhere - it only proves that a program reached by
      *EXEC CICS LINK can read ONFLY's request and write ONFLY's reply
      *into the same 412 bytes.
      *
      *WHY THE LAYOUT IS INLINE HERE AND COPIED IN ONFCLNK
      *  CICS requires the linkage item to be called DFHCOMMAREA, and
      *  generated/ONFCOM.cpy declares its 01 as ONF-COMMAREA.  Bridging
      *  that needs COPY ... REPLACING, which C-03 warns MVT COBOL
      *  supports only partially and which would be a second unknown in
      *  a probe that already has one.  So the caller exercises COPY and
      *  this side spells the record out.  The duplication is deliberate
      *  and confined to a probe; it must NOT survive into ONFLYDRV,
      *  where IR-COM-01 forbids a hand-written second copy of a
      *  generated layout.
      *
      *  Whether Raincode supports COPY ... REPLACING is worth its own
      *  probe later.  It is the clean answer for the real driver.
      *
      *The values below are arbitrary but fixed, and ONFCLNK checks for
      *exactly them: rc 7, two readouts, 10000 steps.  They are chosen
      *so that a zeroed or shifted record cannot pass by accident.
      *
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ONFCENG.
      *
       ENVIRONMENT DIVISION.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  ONF-I                      PIC S9(4) COMP VALUE 0.
      *
       LINKAGE SECTION.
      *Must match generated/ONFCOM.cpy exactly.  412 bytes:
      *  28 fixed + 32 occurrences of 12.
       01  DFHCOMMAREA.
           05  ONF-STIM-CODE          PIC X(8).
           05  ONF-SEED               PIC S9(9) COMP.
           05  ONF-STIM-RATE          PIC S9(4) COMP.
           05  ONF-SIM-MS             PIC S9(4) COMP.
           05  ONF-RC                 PIC S9(4) COMP.
           05  ONF-OUT-COUNT          PIC S9(4) COMP.
           05  ONF-FPRINT             PIC X(4).
           05  ONF-STEPS              PIC S9(9) COMP.
           05  ONF-OUT OCCURS 32 TIMES.
               10  ONF-OUT-ID         PIC S9(9) COMP.
               10  ONF-OUT-LAT-US     PIC S9(9) COMP.
               10  ONF-OUT-SPIKES     PIC S9(4) COMP.
               10  FILLER             PIC X(2).
      *
       PROCEDURE DIVISION.
       ONFCENG-MAIN.
           DISPLAY 'ONFCENG entered  code=' ONF-STIM-CODE.
      *
      *A real engine would simulate here.  This one answers.
           MOVE 7 TO ONF-RC.
           MOVE 2 TO ONF-OUT-COUNT.
           MOVE 10000 TO ONF-STEPS.
           MOVE 'FPRT' TO ONF-FPRINT.
      *
           MOVE 1 TO ONF-I.
           PERFORM ONFCENG-FILL UNTIL ONF-I > 2.
      *
           EXEC CICS RETURN
           END-EXEC.
      *
           GOBACK.
      *
      *No inline PERFORM: D-17 pins the dialect to the MVT and
      *Enterprise intersection, and MVT has no inline PERFORM.
       ONFCENG-FILL.
           MOVE 900 TO ONF-OUT-ID (ONF-I).
           MOVE 26200 TO ONF-OUT-LAT-US (ONF-I).
           MOVE 138 TO ONF-OUT-SPIKES (ONF-I).
           ADD 1 TO ONF-I.
