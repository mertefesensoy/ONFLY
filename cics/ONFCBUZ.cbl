      *ONFLY: the BUZZ menu transaction (Phase G, D-393, P-22).
      *
      *Section 3.7: "BUZZ will be a menu transaction (BMS screen) that
      *lets the user pick a stimulus, rate, duration and seed."
      *
      *WHAT IS VERIFIED AND WHAT IS NOT
      *  Verified (P-22 V6): rcbms assembles ONFCBUZ.bms into a
      *  physical and a symbolic map, and cobrc compiles this program
      *  against the symbolic map, in the MVT / Enterprise COBOL
      *  intersection C-03 and D-17 fix.
      *
      *  NOT verified, and it cannot be here: this program has never
      *  been EXECUTED.  SEND MAP and RECEIVE MAP return INVREQ,
      *  RESP2 999, on this installation -- the free Raincode edition
      *  holds no terminal facility and QIX.TerminalServerRunner
      *  refuses to start without a licence file the download does not
      *  include (VL-37).  Phase G's 3270 half is D-131's INTERCOMM
      *  work on TK5.  Nothing below may be reported as working.
      *
      *WHAT IT SHARES WITH ONFCSUG
      *  The COMMAREA and the LINK, which is the point: the menu and
      *  the direct transaction differ only in where the request comes
      *  from and where the answer is shown.  Both build the SAME
      *  412-byte record (IR-COM) and both LINK to the same ONFLYENG.
      *
      *DIALECT
      *  MVT / Enterprise intersection: no scope terminators, no
      *  inline PERFORM, no COMP-5, flat control flow.  Held to 72
      *  columns, because cobrc truncates past 72 in silence (VL-37).
      *
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ONFCBUZ.
      *
       ENVIRONMENT DIVISION.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
      *
      *The generated layout, not a copy of it (IR-COM-01, D-18).
       COPY ONFCOM.
      *
      *The symbolic map rcbms generates from ONFCBUZ.bms.  Generated,
      *never edited (IR-COM-01 applies to it for the same reason).
       COPY ONFCBUZ.
      *
       01  W-LEN                      PIC S9(4) COMP VALUE +412.
       01  W-RESP                     PIC S9(9) COMP VALUE +0.
       01  W-BAD                      PIC S9(4) COMP VALUE +0.
       01  W-FIRST                    PIC S9(4) COMP VALUE +0.
       01  W-I                        PIC S9(4) COMP VALUE +0.
       01  W-J                        PIC S9(4) COMP VALUE +0.
       01  W-NIB-HI                   PIC S9(4) COMP VALUE +0.
       01  W-NIB-LO                   PIC S9(4) COMP VALUE +0.
       01  W-HZ                       PIC S9(7)V9 VALUE +0.
       01  W-NUM                      PIC S9(9) COMP VALUE +0.
       01  W-HZE                      PIC Z(6)9.9.
       01  W-SPKE                     PIC Z(3)9.
       01  W-LATE                     PIC --------9.
       01  W-RCE                      PIC Z(3)9.
      *
       01  W-FP.
           05  W-FP-C                 PIC X OCCURS 4 TIMES.
       01  W-FPX.
           05  W-FPX-C                PIC X OCCURS 8 TIMES.
       01  W-BYTEW.
           05  FILLER                 PIC X VALUE LOW-VALUE.
           05  W-BYTE-LO              PIC X.
       01  W-BYTEH REDEFINES W-BYTEW  PIC S9(4) COMP.
       01  W-HEXTAB.
           05  FILLER                 PIC X(16)
               VALUE '0123456789ABCDEF'.
       01  W-HEXT REDEFINES W-HEXTAB.
           05  W-HEXC                 PIC X OCCURS 16 TIMES.
      *
       PROCEDURE DIVISION.
       ONFCBUZ-MAIN.
      *EIBCALEN zero means the transaction was started from the
      *terminal rather than re-entered after a screen: send the empty
      *menu and return with the transaction identifier so the next
      *AID comes back here.
           IF EIBCALEN = ZERO
               PERFORM BUZZ-SEND-EMPTY
           ELSE
               PERFORM BUZZ-HANDLE.
      *
           EXEC CICS RETURN
                TRANSID('BUZZ')
                COMMAREA(ONF-COMMAREA)
                LENGTH(W-LEN)
           END-EXEC.
           GOBACK.
      *
       BUZZ-SEND-EMPTY.
           MOVE LOW-VALUES TO ONFCBMPO.
           MOVE SPACES TO ONF-COMMAREA.
           MOVE 'Enter stimulus, rate, duration and seed'
               TO BZINFOO.
           EXEC CICS SEND MAP('ONFCBMP')
                MAPSET('ONFCBUZ')
                ERASE
                RESP(W-RESP)
           END-EXEC.
      *
       BUZZ-HANDLE.
           EXEC CICS RECEIVE MAP('ONFCBMP')
                MAPSET('ONFCBUZ')
                RESP(W-RESP)
           END-EXEC.
      *
           MOVE ZERO TO W-BAD.
           MOVE SPACES TO ONF-COMMAREA.
           MOVE BZSTIMI TO ONF-STIM-CODE.
      *
      *The screen fields are character; the record's are binary
      *(IR-COM-02).  A non-numeric field is refused here rather than
      *turned into a request the engine would reject anyway, because
      *the operator gets a better message from the program that saw
      *what was typed.
           IF BZRATEI IS NUMERIC
               MOVE BZRATEI TO ONF-STIM-RATE
           ELSE
               MOVE 1 TO W-BAD.
           IF BZMSI IS NUMERIC
               MOVE BZMSI TO ONF-SIM-MS
           ELSE
               MOVE 1 TO W-BAD.
           IF BZSEEDI IS NUMERIC
               MOVE BZSEEDI TO ONF-SEED
           ELSE
               MOVE 1 TO W-BAD.
      *
           IF W-BAD NOT = ZERO
               PERFORM BUZZ-BADFIELD
           ELSE
               PERFORM BUZZ-RUN.
      *
       BUZZ-BADFIELD.
           MOVE 'Rate, duration and seed must be numeric'
               TO BZINFOO.
           EXEC CICS SEND MAP('ONFCBMP')
                MAPSET('ONFCBUZ')
                RESP(W-RESP)
           END-EXEC.
      *
       BUZZ-RUN.
           MOVE ZERO TO ONF-RC.
           MOVE ZERO TO ONF-OUT-COUNT.
           MOVE ZERO TO ONF-STEPS.
           MOVE LOW-VALUES TO ONF-FPRINT.
      *
      *Section 3.7's LINK, the same one ONFCSUG makes.
           EXEC CICS LINK
                PROGRAM('ONFLYENG')
                COMMAREA(ONF-COMMAREA)
                LENGTH(W-LEN)
           END-EXEC.
      *
           PERFORM FP-HEX.
           MOVE W-FPX TO BZFPO.
           MOVE ONF-RC TO W-RCE.
           MOVE W-RCE TO BZRCO.
      *
      *IR-COM-06: the record carries a numeric identifier, never a
      *name.  ONFNAM is what maps it, and this transaction has no
      *ONFNAM -- so the identifier is shown as itself rather than a
      *name being invented for it.
           MOVE SPACES TO BZNAMEO.
           MOVE SPACES TO BZSPKO.
           MOVE SPACES TO BZLATO.
           MOVE SPACES TO BZHZO.
           IF ONF-OUT-COUNT IS GREATER THAN ZERO
               PERFORM BUZZ-FIRSTOUT.
      *
           MOVE 'LINK complete' TO BZINFOO.
           EXEC CICS SEND MAP('ONFCBMP')
                MAPSET('ONFCBUZ')
                RESP(W-RESP)
           END-EXEC.
      *
      *The first readout entry.  The menu shows one; the full set is
      *what the batch report prints (FR-BAT-04).
       BUZZ-FIRSTOUT.
           MOVE ONF-OUT-ID (1) TO W-NUM.
           MOVE W-NUM TO W-LATE.
           MOVE W-LATE TO BZNAMEO.
           MOVE ONF-OUT-SPIKES (1) TO W-SPKE.
           MOVE W-SPKE TO BZSPKO.
           MOVE ONF-OUT-LAT-US (1) TO W-LATE.
           MOVE W-LATE TO BZLATO.
           MOVE ZERO TO W-HZ.
           IF ONF-SIM-MS IS GREATER THAN ZERO
               COMPUTE W-HZ ROUNDED =
                   (ONF-OUT-SPIKES (1) * 1000) / ONF-SIM-MS.
           MOVE W-HZ TO W-HZE.
           MOVE W-HZE TO BZHZO.
      *
      *The 4 fingerprint bytes as 8 hexadecimal characters.
       FP-HEX.
           MOVE ONF-FPRINT TO W-FP.
           MOVE 1 TO W-J.
           PERFORM FP-HEX-BYTE VARYING W-I FROM 1 BY 1
               UNTIL W-I IS GREATER THAN 4.
      *
       FP-HEX-BYTE.
           MOVE W-FP-C (W-I) TO W-BYTE-LO.
           DIVIDE W-BYTEH BY 16 GIVING W-NIB-HI
               REMAINDER W-NIB-LO.
           ADD 1 TO W-NIB-HI.
           ADD 1 TO W-NIB-LO.
           MOVE W-HEXC (W-NIB-HI) TO W-FPX-C (W-J).
           ADD 1 TO W-J.
           MOVE W-HEXC (W-NIB-LO) TO W-FPX-C (W-J).
           ADD 1 TO W-J.
