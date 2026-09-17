      *ONFLY: the SUGR direct transaction (Phase G, D-393, P-22).
      *
      *WHAT IT IS
      *  Section 3.7: "SUGR, WATR and BITR will be direct transactions
      *  for each stimulus" and "ONFLYENG will be LINKed with the
      *  COMMAREA of IR-COM".  This is both sentences, compiled.
      *
      *  The request arrives in the COMMAREA -- from a bridge, from a
      *  START with data, from BUZZ's LINK, or on this host from
      *  rclrun -QixFile.  It is the SAME 412-byte record the batch
      *  path reads out of ONFREQ (IR-COM), so a request that runs
      *  here and the same request under JCL are the same bytes, and
      *  IR-COM-05's fingerprint is comparable between them.  That
      *  comparison is this component's exit criterion, not a bonus.
      *
      *WHY IT DOES NOT DECLARE THE RECORD'S FIELDS
      *  IR-COM-01: the layout is defined once and generated.  The
      *  fields come from COPY ONFCOM and nowhere else.  The linkage
      *  item has to be called DFHCOMMAREA, and bridging that to the
      *  copybook's own 01 would need COPY ... REPLACING, which C-03
      *  warns MVT COBOL supports only partially -- so DFHCOMMAREA is
      *  declared as an unnamed block of bytes, the LINK is given it
      *  directly, and the reply is copied into the generated record
      *  afterwards purely to be READ.  Nothing here restates a field.
      *  The one layout fact spelled out is the length, 412, which SRS
      *  Section 4.3 states normatively in its own text.
      *
      *DIALECT
      *  MVT / Enterprise COBOL intersection (C-03, D-17): no scope
      *  terminators, no inline PERFORM, no COMP-5, flat control flow.
      *  Held to 72 columns, not 80: cobrc truncates past column 72
      *  with no diagnostic at all (VL-37), and D-93's 80-column rule
      *  is about a different tool.
      *
      *WHERE THE RESULT GOES (D-397)
      *  WRITEQ TS, a real CICS statement that this installation
      *  executes, plus a DISPLAY trace for a human.  SEND TEXT is not
      *  used: it returns INVREQ here, because the free Raincode
      *  edition holds no terminal facility (VL-37).
      *
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ONFCSUG.
      *
       ENVIRONMENT DIVISION.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
      *
      *The generated layout, not a copy of it (IR-COM-01, D-18).
       COPY ONFCOM.
      *
       01  W-LEN                      PIC S9(4) COMP VALUE +412.
       01  W-QLEN                     PIC S9(4) COMP VALUE +80.
       01  W-QNAME                    PIC X(8) VALUE 'ONFLYQ  '.
       01  W-RESP                     PIC S9(9) COMP VALUE +0.
       01  W-BAD                      PIC S9(4) COMP VALUE +0.
       01  W-I                        PIC S9(4) COMP VALUE +0.
       01  W-J                        PIC S9(4) COMP VALUE +0.
       01  W-K                        PIC S9(4) COMP VALUE +0.
       01  W-NIB-HI                   PIC S9(4) COMP VALUE +0.
       01  W-NIB-LO                   PIC S9(4) COMP VALUE +0.
       01  W-HZ                       PIC S9(7)V9 VALUE +0.
      *
      *The fingerprint as 8 hexadecimal characters (FR-BAT-04).  The
      *byte goes into the low half of a halfword whose high half is
      *binary zero, so the value read is 0 to 255 and never negative.
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
      *The queue records, fixed at 80 bytes so that a reader can take
      *them apart by column as the batch report is taken apart.  The
      *rate and the latency are signed edits, not Z edits: G-13 sends
      *rate -1 and FR-SIM-05 reports latency -1 for a neuron that did
      *not spike, and a Z edit would print those without their sign
      *(the class of bug VL-111 records).
       01  W-QHDR.
           05  FILLER                 PIC X(8) VALUE 'ONFCSUG '.
           05  QH-CODE                PIC X(8).
           05  FILLER                 PIC X(6) VALUE ' RATE='.
           05  QH-RATE                PIC ----9.
           05  FILLER                 PIC X(4) VALUE ' MS='.
           05  QH-MS                  PIC Z(4)9.
           05  FILLER                 PIC X(6) VALUE ' SEED='.
           05  QH-SEED                PIC Z(8)9.
           05  FILLER                 PIC X(4) VALUE ' RC='.
           05  QH-RC                  PIC Z(3)9.
           05  FILLER                 PIC X(4) VALUE ' FP='.
           05  QH-FP                  PIC X(8).
           05  FILLER                 PIC X(9) VALUE SPACES.
       01  W-QOUT.
           05  FILLER                 PIC X(8) VALUE 'ONFCOUT '.
           05  FILLER                 PIC X(4) VALUE ' ID='.
           05  QO-ID                  PIC Z(8)9.
           05  FILLER                 PIC X(5) VALUE ' SPK='.
           05  QO-SPK                 PIC Z(3)9.
           05  FILLER                 PIC X(5) VALUE ' LAT='.
           05  QO-LAT                 PIC --------9.
           05  FILLER                 PIC X(4) VALUE ' HZ='.
           05  QO-HZ                  PIC Z(6)9.9.
           05  FILLER                 PIC X(23) VALUE SPACES.
      *
       LINKAGE SECTION.
      *No field names here, deliberately.  See the header comment.
       01  DFHCOMMAREA                PIC X(412).
      *
       PROCEDURE DIVISION.
       ONFCSUG-MAIN.
           MOVE ZERO TO W-BAD.
      *A COMMAREA of the wrong size is refused before anything is
      *LINKed.  The engine would refuse it too (ONFC_EARG), but only
      *after the record had been copied, and a transaction that
      *reports its own precondition is easier to diagnose than one
      *that reports the engine's.
           IF EIBCALEN NOT = W-LEN
               MOVE 1 TO W-BAD
               DISPLAY 'ONF908S COMMAREA LENGTH NOT 412'.
      *
           IF W-BAD = ZERO
               PERFORM ONFCSUG-RUN.
      *
           EXEC CICS RETURN
           END-EXEC.
           GOBACK.
      *
       ONFCSUG-RUN.
           MOVE DFHCOMMAREA TO ONF-COMMAREA.
           DISPLAY 'ONFCSUG request code=' ONF-STIM-CODE.
      *
      *Section 3.7's LINK.  The engine writes the response portion in
      *place; IR-JCL-03 leaves offsets 0 to 15, the request echo,
      *exactly as they arrived.
           EXEC CICS LINK
                PROGRAM('ONFLYENG')
                COMMAREA(DFHCOMMAREA)
                LENGTH(W-LEN)
           END-EXEC.
      *
           MOVE DFHCOMMAREA TO ONF-COMMAREA.
           PERFORM FP-HEX.
      *
           MOVE ONF-STIM-CODE TO QH-CODE.
           MOVE ONF-STIM-RATE TO QH-RATE.
           MOVE ONF-SIM-MS TO QH-MS.
           MOVE ONF-SEED TO QH-SEED.
           MOVE ONF-RC TO QH-RC.
           MOVE W-FPX TO QH-FP.
      *
           EXEC CICS WRITEQ TS
                QUEUE(W-QNAME)
                FROM(W-QHDR)
                LENGTH(W-QLEN)
                RESP(W-RESP)
           END-EXEC.
           DISPLAY W-QHDR.
           IF W-RESP NOT = ZERO
               DISPLAY 'ONF908S WRITEQ TS FAILED'.
      *
           MOVE 1 TO W-K.
           PERFORM ONFCSUG-OUT
               UNTIL W-K IS GREATER THAN ONF-OUT-COUNT.
      *
      *One readout neuron.  No inline PERFORM: MVT COBOL has none.
       ONFCSUG-OUT.
           MOVE ONF-OUT-ID (W-K) TO QO-ID.
           MOVE ONF-OUT-SPIKES (W-K) TO QO-SPK.
           MOVE ONF-OUT-LAT-US (W-K) TO QO-LAT.
      *ROUNDED, to the nearest tenth, exactly as ONFLYDRV does it
      *(D-272).  The guard is not theatre: a rejected request carries
      *no output entries, so this is only reached with a duration the
      *engine accepted -- but a zero here would be a divide-by-zero
      *abend inside a transaction rather than a wrong number.
           MOVE ZERO TO W-HZ.
           IF ONF-SIM-MS IS GREATER THAN ZERO
               COMPUTE W-HZ ROUNDED =
                   (ONF-OUT-SPIKES (W-K) * 1000) / ONF-SIM-MS.
           MOVE W-HZ TO QO-HZ.
      *
           EXEC CICS WRITEQ TS
                QUEUE(W-QNAME)
                FROM(W-QOUT)
                LENGTH(W-QLEN)
                RESP(W-RESP)
           END-EXEC.
           DISPLAY W-QOUT.
           ADD 1 TO W-K.
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
