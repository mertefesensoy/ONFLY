      *ONFLY probe 1a of 3 (D-129): EXEC CICS LINK with the COMMAREA.
      *
      *WHAT THIS ANSWERS
      *  Section 3.7 says "ONFLYENG will be LINKed with the COMMAREA of
      *  IR-COM".  This is that sentence, compiled.  It builds a real
      *  ONFLY request in the real generated record, LINKs to ONFCENG,
      *  and checks that the reply came back in the same 412 bytes.
      *
      *  Three things pass or fail independently here, so read the
      *  failure before concluding anything:
      *    1. COPY ONFCOM          - does Raincode find and expand the
      *                              generated copybook at all?
      *    2. EXEC CICS LINK       - does the compiler accept it?
      *    3. the round trip       - does the 412-byte record survive?
      *
      *  If it fails on COPY, that is a finding about COPY and says
      *  nothing about CICS: paste the copybook inline and run again.
      *
      *WHY DISPLAY AND NOT SEND TEXT
      *  Deliberately no terminal.  This probe isolates LINK; ONFCTRM
      *  is where the terminal is put on trial.
      *
      *DIALECT
      *  Written in the MVT / Enterprise COBOL intersection D-17 fixes:
      *  no scope terminators, no inline PERFORM, no COMP-5.  That is
      *  free extra signal - if Raincode rejects this style, ONFLYDRV
      *  cannot be one source across both worlds.
      *
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ONFCLNK.
      *
       ENVIRONMENT DIVISION.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
      *
      *The generated layout, not a copy of it (IR-COM-01, D-18).
       COPY ONFCOM.
      *
       01  ONF-LEN                    PIC S9(4) COMP VALUE 412.
       01  ONF-BAD                    PIC S9(4) COMP VALUE 0.
       01  ONF-SHOW                   PIC ----9.
      *
       PROCEDURE DIVISION.
       ONFCLNK-MAIN.
           MOVE SPACES TO ONF-COMMAREA.
           MOVE 'SUGR    ' TO ONF-STIM-CODE.
           MOVE 12345 TO ONF-SEED.
           MOVE 80 TO ONF-STIM-RATE.
           MOVE 1000 TO ONF-SIM-MS.
           MOVE 0 TO ONF-RC.
           MOVE 0 TO ONF-OUT-COUNT.
           MOVE 0 TO ONF-STEPS.
           MOVE LOW-VALUES TO ONF-FPRINT.
      *
           DISPLAY 'ONFCLNK request  code=' ONF-STIM-CODE.
      *
           EXEC CICS LINK
                PROGRAM('ONFCENG')
                COMMAREA(ONF-COMMAREA)
                LENGTH(ONF-LEN)
           END-EXEC.
      *
      *ONFCENG sets these three.  Anything else means the record did
      *not survive the round trip, which is the interesting failure.
           IF ONF-RC NOT = 7
               MOVE 1 TO ONF-BAD
               DISPLAY 'ONFCLNK FAIL rc not 7'.
           IF ONF-OUT-COUNT NOT = 2
               MOVE 1 TO ONF-BAD
               DISPLAY 'ONFCLNK FAIL count not 2'.
           IF ONF-STEPS NOT = 10000
               MOVE 1 TO ONF-BAD
               DISPLAY 'ONFCLNK FAIL steps not 10000'.
      *
      *The request fields must come back untouched.  A layout that
      *shifts by a byte shows up here and nowhere else.
           IF ONF-STIM-CODE NOT = 'SUGR    '
               MOVE 1 TO ONF-BAD
               DISPLAY 'ONFCLNK FAIL stim code changed'.
           IF ONF-SEED NOT = 12345
               MOVE 1 TO ONF-BAD
               DISPLAY 'ONFCLNK FAIL seed changed'.
      *
           MOVE ONF-OUT-SPIKES (1) TO ONF-SHOW.
           DISPLAY 'ONFCLNK reply    spikes(1)=' ONF-SHOW.
           MOVE ONF-OUT-LAT-US (1) TO ONF-SHOW.
           DISPLAY 'ONFCLNK reply    lat(1)   =' ONF-SHOW.
      *
           IF ONF-BAD = 0
               DISPLAY 'ONFCLNK PASS link and commarea intact'
           ELSE
               DISPLAY 'ONFCLNK FAIL see above'.
      *
           EXEC CICS RETURN
           END-EXEC.
      *
           GOBACK.
