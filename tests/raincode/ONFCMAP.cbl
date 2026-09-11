      *ONFLY probe 3b of 3 (D-129): BMS SEND MAP and RECEIVE MAP.
      *
      *WHAT THIS ANSWERS
      *  Whether the formatted-screen half of D-127 is possible under
      *  Raincode.  ONFCTRM already asks whether a terminal exists at
      *  all; this asks the harder question, whether BMS does.
      *
      *  It depends on ONFCMS.bms having been assembled first, twice:
      *  once TYPE=MAP for the physical map and once TYPE=DSECT for the
      *  symbolic map this program COPYs.  If nothing in the free
      *  edition can assemble a BMS map, this probe cannot even be
      *  compiled - and that is the answer, not a tooling mistake.
      *
      *CONVERSATIONAL ON PURPOSE
      *  A real BUZZ would be pseudo-conversational: SEND, RETURN with
      *  TRANSID, RECEIVE on the next invocation.  This holds the task
      *  across the RECEIVE instead, which is worse practice and a much
      *  shorter probe.  Section 3.7's ICVR runaway-task note is about
      *  exactly this, so the real one must not copy this shape.
      *
      *IF RESP IS REJECTED
      *  RESP turns a MAPFAIL - what happens if the user presses enter
      *  without typing - into a value instead of an abend.  If the
      *  compiler will not take RESP, drop it and expect an abend on an
      *  empty screen; that is a finding about the subset, not a bug
      *  here.
      *
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ONFCMAP.
      *
       ENVIRONMENT DIVISION.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
      *
      *Produced by assembling ONFCMS.bms with TYPE=DSECT.
       COPY ONFCMS.
      *
       01  ONF-RESP                   PIC S9(8) COMP VALUE 0.
       01  ONF-ECHO-MSG.
           05  FILLER                 PIC X(10) VALUE 'you typed '.
           05  ONF-ECHO-STIM          PIC X(8)  VALUE SPACES.
           05  FILLER                 PIC X(7)  VALUE ' rate  '.
           05  ONF-ECHO-RATE          PIC X(4)  VALUE SPACES.
           05  FILLER                 PIC X(31) VALUE SPACES.
      *
       PROCEDURE DIVISION.
       ONFCMAP-MAIN.
           MOVE LOW-VALUES TO ONFCMPO.
           MOVE 'ONFLY BMS probe - type and press enter' TO MSGFO.
      *
           EXEC CICS SEND MAP('ONFCMP')
                MAPSET('ONFCMS')
                ERASE
           END-EXEC.
      *
           EXEC CICS RECEIVE MAP('ONFCMP')
                MAPSET('ONFCMS')
                RESP(ONF-RESP)
           END-EXEC.
      *
           MOVE LOW-VALUES TO ONFCMPO.
           IF ONF-RESP NOT = 0
               MOVE 'nothing entered - RESP was not zero' TO MSGFO
           ELSE
               MOVE STIMCI TO ONF-ECHO-STIM
               MOVE RATEFI TO ONF-ECHO-RATE
               MOVE ONF-ECHO-MSG TO MSGFO.
      *
           EXEC CICS SEND MAP('ONFCMP')
                MAPSET('ONFCMS')
                DATAONLY
           END-EXEC.
      *
           EXEC CICS RETURN
           END-EXEC.
      *
           GOBACK.
