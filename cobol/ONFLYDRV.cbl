      *ONFLYDRV - ONFLY batch driver (FR-BAT-01, FR-BAT-03, D-17).
      *
      *ONE SOURCE, TWO COMPILERS
      *  This file must compile unchanged under the OS/360 MVT ANS
      *  COBOL compiler (IKFCBL00 on MVS 3.8j) and under Enterprise
      *  COBOL, checked here by the GnuCOBOL IBM-dialect proxy
      *  (VL-02).  So it is written in the intersection C-03 names:
      *  no END-IF or other scope terminator, no inline PERFORM, no
      *  COMP-5, no reference modification, no STRING or UNSTRING,
      *  no INITIALIZE, no EVALUATE, relational operators spelled as
      *  words, and IF nesting kept to ELSE-IF chains.
      *
      *MODES (D-158)
      *  The first ONFCTL card selects the mode: MODE=REQ builds
      *  request records from the cards that follow (IR-JCL-02) and
      *  writes them to ONFREQ; MODE=RPT reads ONFRSP and prints the
      *  FR-BAT-04 report to ONFRPT.
      *
      *  The report was the Gate G4 skeleton (D-155) until Phase E
      *  slice 2 completed it on 2026-09-15: each readout's NAME,
      *  mapped through ONFNAM because IR-COM-06 forbids the response
      *  from carrying one; the firing rate in Hz to one decimal,
      *  ROUNDED by D-272; the return code with its Appendix E
      *  message, RC 8 resolved between ONF202E and ONF203E by D-270;
      *  and the response fingerprint in hexadecimal.
      *
      *  The rate column of a control card is signed (D-265), so that
      *  Section 8.4's G-13 reaches the ENGINE, which owes it ONF202E.
      *  A driver that rejected the card would answer ONF401E instead
      *  and the engine would never see the request.
      *
      *THE LAYOUT IS COPIED, NEVER SPELLED OUT (IR-COM-01, D-157)
      *  generated/ONFCOM.cpy is the only description of the 412-byte
      *  record this program may use.  It is copied once, into
      *  WORKING-STORAGE, because an FD record area on OS COBOL exists
      *  only while its file is open and RPT mode never opens ONFREQ.
      *  The FDs describe the record as PIC X(412) and the program
      *  moves through it with WRITE FROM and READ INTO.
      *
      *THIS FILE IS A TEMPLATE (D-161, Gate G4)
      *  MVT COBOL accepts COPY only in its COBOL-68 spelling, which
      *  Enterprise COBOL and GnuCOBOL refuse (VL-57).  So the COPY
      *  statement below is kept as honest COBOL, and
      *  layout/generate.py expands it into generated/ONFLYDRV.cbl,
      *  the single source that every compiler actually builds.
      *  Compile THAT file; this one is what you edit.
      *
      *CONTROL CARDS (IR-JCL-02, D-159, D-160)
      *  Columns 1-4 stimulus code, 6-9 rate in Hz, 11-14 duration in
      *  ms, 16-24 seed.  Numeric fields may be right-justified with
      *  leading blanks or zero-padded; an all-blank numeric field, a
      *  blank stimulus code, a non-digit, or a blank card is
      *  ONF401E.  An asterisk in column 1 is a comment.
      *
      *RETURN CODE (IR-JCL-04)
      *  0 when every card was accepted; 8 when at least one was not.
      *
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ONFLYDRV.
      *
       ENVIRONMENT DIVISION.
       CONFIGURATION SECTION.
       SOURCE-COMPUTER. IBM-370.
       OBJECT-COMPUTER. IBM-370.
       INPUT-OUTPUT SECTION.
       FILE-CONTROL.
      *DD names per IR-JCL-01.  UT-S is the OS sequential system
      *name; GnuCOBOL's IBM dialect maps the same spelling to DD_name.
           SELECT ONFCTL ASSIGN TO UT-S-ONFCTL.
           SELECT ONFREQ ASSIGN TO UT-S-ONFREQ.
           SELECT ONFRSP ASSIGN TO UT-S-ONFRSP.
           SELECT ONFNAM ASSIGN TO UT-S-ONFNAM.
           SELECT ONFRPT ASSIGN TO UT-S-ONFRPT.
      *
       DATA DIVISION.
       FILE SECTION.
      *Control cards: FB, LRECL=80.
       FD  ONFCTL
           LABEL RECORDS ARE OMITTED
           BLOCK CONTAINS 0 RECORDS
           RECORDING MODE IS F
           RECORD CONTAINS 80 CHARACTERS.
       01  CTL-REC                    PIC X(80).
      *Request records: FB, LRECL=412 (IR-JCL-03).
       FD  ONFREQ
           LABEL RECORDS ARE STANDARD
           BLOCK CONTAINS 0 RECORDS
           RECORDING MODE IS F
           RECORD CONTAINS 412 CHARACTERS.
       01  REQ-REC                    PIC X(412).
      *Response records: FB, LRECL=412, the same layout.
       FD  ONFRSP
           LABEL RECORDS ARE STANDARD
           BLOCK CONTAINS 0 RECORDS
           RECORDING MODE IS F
           RECORD CONTAINS 412 CHARACTERS.
       01  RSP-REC                    PIC X(412).
      *Names: FB, LRECL=80 (IR-NAM-01).  Declared for Phase E; the
      *G4 skeleton never opens it, so no DD is needed yet.
       FD  ONFNAM
           LABEL RECORDS ARE STANDARD
           BLOCK CONTAINS 0 RECORDS
           RECORDING MODE IS F
           RECORD CONTAINS 80 CHARACTERS.
       01  NAM-REC                    PIC X(80).
      *Report: FBA, LRECL=133.  Byte 1 is the ANSI carriage-control
      *character and the program writes it itself.  WRITE ... AFTER
      *ADVANCING is NOT used: Gate G4 measured that MVT COBOL takes
      *the record's first byte as the control character while
      *Enterprise COBOL (ADV) and GnuCOBOL prepend one, so the same
      *source would print differently on the two (VL-59).  A plain
      *WRITE of a 133-byte record behaves identically everywhere.
       FD  ONFRPT
           LABEL RECORDS ARE OMITTED
           BLOCK CONTAINS 0 RECORDS
           RECORDING MODE IS F
           RECORD CONTAINS 133 CHARACTERS.
       01  RPT-REC.
           05  RPT-CC                 PIC X.
           05  RPT-TEXT               PIC X(132).
      *
       WORKING-STORAGE SECTION.
      *The one copy of the COMMAREA layout (IR-COM-01, D-157).
       COPY ONFCOM.
      *The stimulus codes, generated from the same master definition
      *(D-271).  FR-BAT-04 makes this program name the Appendix E
      *message for a return code, and RC 8 is ambiguous between
      *ONF202E and ONF203E; D-270 resolves it by asking whether the
      *code is one of these.
       COPY ONFSTM.
      *
      *The control card, broken into IR-JCL-02's columns.  Each
      *numeric field is a table of characters so that leading blanks
      *can be turned into zeros before the class test (D-159).
       01  W-CARD.
           05  W-CARD-CODE            PIC X(4).
           05  FILLER                 PIC X.
           05  W-CARD-RATE.
               10  W-CARD-RATE-C      PIC X OCCURS 4 TIMES.
           05  FILLER                 PIC X.
           05  W-CARD-MS.
               10  W-CARD-MS-C        PIC X OCCURS 4 TIMES.
           05  FILLER                 PIC X.
           05  W-CARD-SEED.
               10  W-CARD-SEED-C      PIC X OCCURS 9 TIMES.
           05  FILLER                 PIC X(56).
       01  W-CARD-ALT REDEFINES W-CARD.
           05  W-CARD-COL1            PIC X.
           05  FILLER                 PIC X(79).
       01  W-CARD-MODE REDEFINES W-CARD.
           05  W-MODE-WORD            PIC X(8).
           05  FILLER                 PIC X(72).
      *
      *Conversion areas: the characters are cleaned in the X form and
      *read back through the numeric REDEFINES only after the class
      *test has passed, so a bad card can never reach a PACK of
      *non-digits (S0C7 on MVS).
       01  W-NUM4-X.
           05  W-NUM4-C               PIC X OCCURS 4 TIMES.
       01  W-NUM4 REDEFINES W-NUM4-X  PIC 9(4).
       01  W-NUM9-X.
           05  W-NUM9-C               PIC X OCCURS 9 TIMES.
       01  W-NUM9 REDEFINES W-NUM9-X  PIC 9(9).
      *
       01  W-FLAGS.
           05  W-MODE                 PIC X VALUE 'N'.
           05  W-CTL-EOF              PIC X VALUE 'N'.
           05  W-RSP-EOF              PIC X VALUE 'N'.
           05  W-NAM-EOF              PIC X VALUE 'N'.
           05  W-NAM-OVER             PIC X VALUE 'N'.
           05  W-CARD-OK              PIC X VALUE 'Y'.
           05  W-NUM-OK               PIC X VALUE 'Y'.
           05  W-LEAD                 PIC X VALUE 'Y'.
      *A leading minus was seen in the field CONV4 just read (D-265).
      *CONV4 only REPORTS it; whether a sign is legal is the caller's
      *business, because it is legal in the rate column and not in
      *the duration column.
           05  W-NUM-NEG              PIC X VALUE 'N'.
       01  W-COUNTS.
           05  W-CARD-NO              PIC 9(4) VALUE 0.
           05  W-REQ-COUNT            PIC 9(4) VALUE 0.
           05  W-ERR-COUNT            PIC 9(4) VALUE 0.
           05  W-RSP-COUNT            PIC 9(4) VALUE 0.
           05  W-NAM-COUNT            PIC S9(4) COMP VALUE +0.
           05  W-RC                   PIC S9(4) COMP VALUE +0.
      *Signed VALUEs: MVT COBOL warns (IKF2190I-W) when a signed
      *PICTURE carries an unsigned literal.
       01  W-VALUES.
           05  W-I                    PIC S9(4) COMP VALUE +0.
           05  W-K                    PIC S9(4) COMP VALUE +0.
      *Which column the minus stood in, so that a field holding a
      *sign and no digits at all is rejected (D-265).
           05  W-NUM-SGN              PIC S9(4) COMP VALUE +0.
      *FR-BAT-04 working values.
           05  W-J                    PIC S9(4) COMP VALUE +0.
           05  W-N                    PIC S9(4) COMP VALUE +0.
           05  W-NIB-HI               PIC S9(4) COMP VALUE +0.
           05  W-NIB-LO               PIC S9(4) COMP VALUE +0.
      *Firing rate: spikes x 1000 / duration_ms, rounded to the
      *nearest tenth (D-272).  This is COBOL fixed-point DECIMAL, not
      *floating point, so NR-05 and NR-07 are not engaged.  Seven
      *integer digits because 9999 spikes in 1 ms is 9,999,000 Hz --
      *not a rate any real run produces, but the widest the record's
      *own PIC digits admit (IR-COM-02).
           05  W-HZ                   PIC S9(7)V9 VALUE +0.
           05  W-RATE                 PIC S9(4) COMP VALUE +0.
           05  W-MS                   PIC S9(4) COMP VALUE +0.
           05  W-SEED                 PIC S9(9) COMP VALUE +0.
      *
      *---- FR-BAT-04 working storage ------------------------------
      *
      *The names table (IR-NAM-01, IR-COM-06).  A response entry
      *carries a numeric identifier and never a name, so the report
      *has to map it through ONFNAM.  256 entries is far above the 32
      *readouts IR-COM allows and the 16 rows the shipped files hold;
      *a file with more is truncated and SAID SO, because a report
      *that silently dropped names would be worse than a short one.
       01  W-NAM-TABLE.
           05  W-NAM-ENTRY OCCURS 256 TIMES.
               10  W-NAM-ID           PIC 9(5).
               10  W-NAM-TEXT         PIC X(34).
       01  W-NAM-IN.
           05  W-NAM-IN-ID            PIC X(5).
           05  FILLER                 PIC X.
           05  W-NAM-IN-TEXT          PIC X(34).
           05  FILLER                 PIC X(40).
       01  W-NAM-IN-NUM REDEFINES W-NAM-IN.
           05  W-NAM-IN-NID           PIC 9(5).
           05  FILLER                 PIC X(75).
      *
      *Hexadecimal conversion of the 4-byte fingerprint (IR-COM-05).
      *A byte is moved into the LOW half of a halfword whose HIGH
      *half is binary zero, so the halfword's value is 0 to 255 and
      *always positive.  That keeps the whole conversion inside
      *IR-COM-02's rule that a value always fits its PIC digits, and
      *needs no bit operation -- COBOL has none in this intersection.
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
      *Appendix E texts for the return codes a RESPONSE can carry.
      *RC 8 is ambiguous between ONF202E and ONF203E and is resolved
      *from the stimulus code (D-270), which is why the table has two
      *entries for it and the code below chooses between them.
       01  W-MSG-ID                   PIC X(8) VALUE SPACES.
       01  W-MSG-TX                   PIC X(48) VALUE SPACES.
      *
      *Report lines (FR-BAT-04).
       01  RL-HEAD.
           05  FILLER                 PIC X(40)
               VALUE 'ONFLY REPORT (FR-BAT-04)'.
           05  FILLER                 PIC X(92) VALUE SPACES.
      *The Appendix E message line, with the fingerprint in
      *hexadecimal beside it (FR-BAT-04, IR-COM-05).
       01  RL-MSG.
           05  FILLER                 PIC X(2) VALUE SPACES.
           05  RL-MSGID               PIC X(8).
           05  FILLER                 PIC X VALUE SPACE.
           05  RL-MSGTX               PIC X(48).
           05  FILLER                 PIC X(4) VALUE ' FP='.
           05  RL-FP                  PIC X(8).
           05  FILLER                 PIC X(61) VALUE SPACES.
      *A names file with more rows than the table can hold.
       01  RL-NAMOV.
           05  FILLER                 PIC X(52)
               VALUE '  ONFNAM TRUNCATED; SOME NAMES MAY BE MISSING'.
           05  FILLER                 PIC X(80) VALUE SPACES.
       01  RL-REQ.
           05  FILLER                 PIC X(8) VALUE 'REQUEST '.
           05  RL-NO                  PIC ZZZ9.
           05  FILLER                 PIC X(6) VALUE ' CODE='.
           05  RL-CODE                PIC X(8).
           05  FILLER                 PIC X(6) VALUE ' RATE='.
      *D-330: SIGNED.  ONF-STIM-RATE is PIC S9(4) COMP and G-13 carries
      *-1 deliberately (out of range, ONF202E).  An unsigned ZZZ9 here
      *drops the sign on the MOVE, so the report printed RATE= 1 for a
      *request the engine correctly rejected as -1 -- the fingerprint
      *A30B1F03 matched Section 8.4 throughout, so only the report was
      *wrong.  Five characters, not four: rate 9999 (G-07) needs all
      *four digits AND a sign position.  The trailing FILLER below drops
      *from 40 to 39 so the record stays 132 characters.
      *
      *D-338: FLOATING, not fixed.  The first fix used PIC -ZZZ9, whose
      *sign is a FIXED insertion in column one while ZZZ9 right-
      *justifies the digit -- so -1 came out as '-   1', measured on
      *TK5 (VL-110).  A floating PIC ----9 puts the sign immediately
      *left of the first digit: '   -1', ' 9999', '-9999'.  Same width.
           05  RL-RATE                PIC ----9.
           05  FILLER                 PIC X(4) VALUE ' MS='.
           05  RL-MS                  PIC ZZZ9.
           05  FILLER                 PIC X(6) VALUE ' SEED='.
           05  RL-SEED                PIC Z(8)9.
           05  FILLER                 PIC X(4) VALUE ' RC='.
           05  RL-RC                  PIC ZZZ9.
           05  FILLER                 PIC X(5) VALUE ' OUT='.
           05  RL-OUT                 PIC ZZZ9.
           05  FILLER                 PIC X(7) VALUE ' STEPS='.
           05  RL-STEPS               PIC Z(8)9.
      *39, not 40: RL-RATE above widened by one for its sign (D-330),
      *and this record must stay 132 characters to fit RPT-TEXT.
           05  FILLER                 PIC X(39) VALUE SPACES.
      *RL-OUT and RL-K are four digits wide although their values
      *never exceed 32: a narrower edited item draws IKF5011I-W
      *(possible high-order truncation) from MVT COBOL.
       01  RL-OUTL.
           05  FILLER                 PIC X(12) VALUE '  READOUT '.
           05  RL-K                   PIC ZZZ9.
           05  FILLER                 PIC X(4) VALUE ' ID='.
           05  RL-ID                  PIC Z(8)9.
           05  FILLER                 PIC X VALUE SPACE.
           05  RL-NAME                PIC X(34).
           05  FILLER                 PIC X(8) VALUE ' LAT-US='.
           05  RL-LAT                 PIC -(9)9.
           05  FILLER                 PIC X(8) VALUE ' SPIKES='.
           05  RL-SPK                 PIC ZZZ9.
           05  FILLER                 PIC X(4) VALUE ' HZ='.
           05  RL-HZ                  PIC Z(6)9.9.
           05  FILLER                 PIC X(25) VALUE SPACES.
      *
       PROCEDURE DIVISION.
       MAIN-PARA.
           OPEN INPUT ONFCTL.
           PERFORM READ-CARD.
           IF W-CTL-EOF = 'Y'
               MOVE 'N' TO W-MODE
           ELSE IF W-MODE-WORD = 'MODE=REQ'
               MOVE 'Q' TO W-MODE
           ELSE IF W-MODE-WORD = 'MODE=RPT'
               MOVE 'P' TO W-MODE
           ELSE
               MOVE 'N' TO W-MODE.
           IF W-MODE = 'N'
               PERFORM CARD-INVALID.
           IF W-MODE = 'Q'
               PERFORM REQ-MODE.
           IF W-MODE = 'P'
               PERFORM RPT-MODE.
           CLOSE ONFCTL.
           DISPLAY 'ONF302I STEP SUMMARY: ' W-REQ-COUNT ' OK, '
               W-ERR-COUNT ' ERROR, ' W-RSP-COUNT ' ECHOED'.
           MOVE W-RC TO RETURN-CODE.
           STOP RUN.
      *
      *---- shared -------------------------------------------------
       READ-CARD.
           READ ONFCTL INTO W-CARD
               AT END MOVE 'Y' TO W-CTL-EOF.
           IF W-CTL-EOF NOT = 'Y'
               ADD 1 TO W-CARD-NO.
      *
       CARD-INVALID.
           DISPLAY 'ONF401E CONTROL CARD INVALID AT CARD ' W-CARD-NO.
           ADD 1 TO W-ERR-COUNT.
           IF W-RC IS LESS THAN 8
               MOVE 8 TO W-RC.
      *
      *---- request mode -------------------------------------------
       REQ-MODE.
           OPEN OUTPUT ONFREQ.
           PERFORM READ-CARD.
           PERFORM REQ-ONE-CARD UNTIL W-CTL-EOF = 'Y'.
           CLOSE ONFREQ.
      *
       REQ-ONE-CARD.
           IF W-CARD-COL1 NOT = '*'
               PERFORM REQ-BUILD.
           PERFORM READ-CARD.
      *
       REQ-BUILD.
           MOVE 'Y' TO W-CARD-OK.
           IF W-CARD-CODE = SPACES
               MOVE 'N' TO W-CARD-OK.
      *The rate is the one signed column (D-265).  Section 8.4's
      *G-13 is a rate of -1, and FR-SIM-06 makes it the ENGINE's job
      *to answer ONF202E; a driver that rejected the card would
      *answer ONF401E instead and the engine would never see it.
           MOVE W-CARD-RATE TO W-NUM4-X.
           PERFORM CONV4.
           IF W-NUM-OK = 'Y'
               MOVE W-NUM4 TO W-RATE.
           IF W-NUM-OK = 'Y' AND W-NUM-NEG = 'Y'
               SUBTRACT W-NUM4 FROM ZERO GIVING W-RATE.
      *The duration is NOT signed.  CONV4 now accepts a leading
      *minus in any field, so this refuses one here and the column
      *behaves exactly as it did before D-265.
           MOVE W-CARD-MS TO W-NUM4-X.
           PERFORM CONV4.
           IF W-NUM-NEG = 'Y'
               MOVE 'N' TO W-CARD-OK.
           IF W-NUM-OK = 'Y' AND W-NUM-NEG = 'N'
               MOVE W-NUM4 TO W-MS.
           MOVE W-CARD-SEED TO W-NUM9-X.
           PERFORM CONV9.
           IF W-NUM-OK = 'Y'
               MOVE W-NUM9 TO W-SEED.
           IF W-CARD-OK = 'Y'
               PERFORM REQ-WRITE
           ELSE
               PERFORM CARD-INVALID.
      *
      *Leading blanks become zeros; then the field must be all
      *digits and must have held at least one non-blank (D-159).
      *
      *D-265 adds one case: a minus may stand where the first
      *non-blank character goes.  It is replaced by a zero so the
      *class test still sees four digits, and the fact is reported in
      *W-NUM-NEG for the caller to accept or refuse.  The magnitude
      *is therefore converted by exactly the code that converted it
      *before, which is the point -- a second conversion path for
      *negative numbers would be a second place for S0C7 to live.
      *
      *A minus in column 4 leaves no digits behind it, so "   -"
      *would otherwise convert to 0000 and pass.  W-NUM-SGN records
      *the column and the test below refuses that one case.  A minus
      *anywhere but the leading position is already refused, because
      *W-LEAD is 'N' by then and the character survives into the
      *class test.
       CONV4.
           MOVE 'Y' TO W-LEAD.
           MOVE 'N' TO W-NUM-NEG.
           MOVE ZERO TO W-NUM-SGN.
           PERFORM CONV4-CHAR VARYING W-I FROM 1 BY 1
               UNTIL W-I IS GREATER THAN 4.
           MOVE 'Y' TO W-NUM-OK.
           IF W-LEAD = 'Y'
               MOVE 'N' TO W-NUM-OK
           ELSE IF W-NUM4 IS NOT NUMERIC
               MOVE 'N' TO W-NUM-OK
           ELSE IF W-NUM-SGN = 4
               MOVE 'N' TO W-NUM-OK.
           IF W-NUM-OK = 'N'
               MOVE 'N' TO W-CARD-OK.
       CONV4-CHAR.
           IF W-LEAD = 'Y' AND W-NUM4-C (W-I) = SPACE
               MOVE '0' TO W-NUM4-C (W-I)
           ELSE IF W-LEAD = 'Y' AND W-NUM4-C (W-I) = '-'
               MOVE '0' TO W-NUM4-C (W-I)
               MOVE 'Y' TO W-NUM-NEG
               MOVE W-I TO W-NUM-SGN
               MOVE 'N' TO W-LEAD
           ELSE
               MOVE 'N' TO W-LEAD.
      *
       CONV9.
           MOVE 'Y' TO W-LEAD.
           PERFORM CONV9-CHAR VARYING W-I FROM 1 BY 1
               UNTIL W-I IS GREATER THAN 9.
           MOVE 'Y' TO W-NUM-OK.
           IF W-LEAD = 'Y'
               MOVE 'N' TO W-NUM-OK
           ELSE IF W-NUM9 IS NOT NUMERIC
               MOVE 'N' TO W-NUM-OK.
           IF W-NUM-OK = 'N'
               MOVE 'N' TO W-CARD-OK.
       CONV9-CHAR.
           IF W-LEAD = 'Y' AND W-NUM9-C (W-I) = SPACE
               MOVE '0' TO W-NUM9-C (W-I)
           ELSE
               MOVE 'N' TO W-LEAD.
      *
      *The whole record is zeroed first, so the response portion
      *and every ONF-OUT entry are binary zero (IR-JCL-03), then the
      *request fields are set.  The stimulus code is left-justified
      *and blank-padded to 8 in the host code page (IR-COM table).
       REQ-WRITE.
           MOVE LOW-VALUES TO ONF-COMMAREA.
           MOVE W-CARD-CODE TO ONF-STIM-CODE.
           MOVE W-SEED TO ONF-SEED.
           MOVE W-RATE TO ONF-STIM-RATE.
           MOVE W-MS TO ONF-SIM-MS.
           MOVE ZERO TO ONF-RC.
           MOVE ZERO TO ONF-OUT-COUNT.
           MOVE ZERO TO ONF-STEPS.
           WRITE REQ-REC FROM ONF-COMMAREA.
           ADD 1 TO W-REQ-COUNT.
      *
      *---- report mode --------------------------------------------
       RPT-MODE.
           OPEN INPUT ONFRSP.
           OPEN OUTPUT ONFRPT.
      *'1' skips to a new page before the title; ' ' single-spaces.
           MOVE '1' TO RPT-CC.
           MOVE RL-HEAD TO RPT-TEXT.
           WRITE RPT-REC.
           PERFORM LOAD-NAMES.
           IF W-NAM-OVER = 'Y'
               MOVE ' ' TO RPT-CC
               MOVE RL-NAMOV TO RPT-TEXT
               WRITE RPT-REC.
           PERFORM READ-RSP.
           PERFORM RPT-ONE UNTIL W-RSP-EOF = 'Y'.
           CLOSE ONFRSP.
           CLOSE ONFRPT.
      *
      *---- the names table (IR-NAM-01, IR-COM-06) ------------------
      *
      *A row is taken only when columns 1-5 are digits.  Anything
      *else is skipped rather than rejected: IR-NAM-01 fixes the
      *columns but says nothing about comments, and a report that
      *abended on an unexpected row would be a worse failure than one
      *that printed an unnamed readout.
       LOAD-NAMES.
           MOVE ZERO TO W-NAM-COUNT.
           MOVE 'N' TO W-NAM-OVER.
           MOVE 'N' TO W-NAM-EOF.
           OPEN INPUT ONFNAM.
           PERFORM READ-NAM.
           PERFORM LOAD-ONE-NAME UNTIL W-NAM-EOF = 'Y'.
           CLOSE ONFNAM.
      *
       READ-NAM.
           READ ONFNAM INTO W-NAM-IN
               AT END MOVE 'Y' TO W-NAM-EOF.
      *
       LOAD-ONE-NAME.
           IF W-NAM-IN-ID IS NUMERIC
               PERFORM STORE-NAME.
           PERFORM READ-NAM.
      *
       STORE-NAME.
           IF W-NAM-COUNT IS LESS THAN 256
               ADD 1 TO W-NAM-COUNT
               MOVE W-NAM-IN-NID TO W-NAM-ID (W-NAM-COUNT)
               MOVE W-NAM-IN-TEXT TO W-NAM-TEXT (W-NAM-COUNT)
           ELSE
               MOVE 'Y' TO W-NAM-OVER.
      *
      *Linear search.  The table holds 16 rows for the shipped
      *networks and at most 256; a response carries at most 32
      *entries, so the worst case is 8,192 comparisons per request,
      *which is nothing beside a simulation that took minutes.
       FIND-NAME.
           MOVE '*UNNAMED*' TO RL-NAME.
           MOVE ZERO TO W-N.
           PERFORM FIND-NAME-ONE VARYING W-J FROM 1 BY 1
               UNTIL W-J IS GREATER THAN W-NAM-COUNT
               OR W-N = 1.
      *
       FIND-NAME-ONE.
           IF W-NAM-ID (W-J) = ONF-OUT-ID (W-K)
               MOVE W-NAM-TEXT (W-J) TO RL-NAME
               MOVE 1 TO W-N.
      *
       READ-RSP.
           READ ONFRSP INTO ONF-COMMAREA
               AT END MOVE 'Y' TO W-RSP-EOF.
      *
       RPT-ONE.
           ADD 1 TO W-RSP-COUNT.
           MOVE W-RSP-COUNT TO RL-NO.
           MOVE ONF-STIM-CODE TO RL-CODE.
           MOVE ONF-STIM-RATE TO RL-RATE.
           MOVE ONF-SIM-MS TO RL-MS.
           MOVE ONF-SEED TO RL-SEED.
           MOVE ONF-RC TO RL-RC.
           MOVE ONF-OUT-COUNT TO RL-OUT.
           MOVE ONF-STEPS TO RL-STEPS.
           MOVE ' ' TO RPT-CC.
           MOVE RL-REQ TO RPT-TEXT.
           WRITE RPT-REC.
           PERFORM RPT-MESSAGE.
           PERFORM RPT-OUT-ENTRY VARYING W-K FROM 1 BY 1
               UNTIL W-K IS GREATER THAN ONF-OUT-COUNT
               OR W-K IS GREATER THAN 32.
           PERFORM READ-RSP.
      *
      *---- FR-BAT-04: the return code with its Appendix E message,
      *---- and the fingerprint in hexadecimal.
      *
      *Only the four return codes a RESPONSE record can carry are
      *listed: ONFR_OK, ONFR_WARN, ONFR_ERR and ONFR_SEV in
      *engine/include/onfreq.h.  Anything else means the record did
      *not come from this engine, and saying so is better than
      *printing a message that was never emitted.
       RPT-MESSAGE.
           MOVE 'ONF???' TO W-MSG-ID.
           MOVE 'UNRECOGNISED RETURN CODE' TO W-MSG-TX.
           IF ONF-RC = 0
               MOVE 'ONF301I' TO W-MSG-ID
               MOVE 'REQUEST COMPLETE' TO W-MSG-TX.
           IF ONF-RC = 4
               MOVE 'ONF201W' TO W-MSG-ID
               MOVE 'STIMULUS CODE RESERVED, NOT SIMULATED'
                   TO W-MSG-TX.
           IF ONF-RC = 8
               PERFORM RPT-MSG-RC8.
           IF ONF-RC = 16
               MOVE 'ONF903S' TO W-MSG-ID
               MOVE 'NON-FINITE STATE VALUE, REQUEST ABORTED'
                   TO W-MSG-TX.
           PERFORM FP-HEX.
           MOVE W-MSG-ID TO RL-MSGID.
           MOVE W-MSG-TX TO RL-MSGTX.
           MOVE W-FPX TO RL-FP.
           MOVE ' ' TO RPT-CC.
           MOVE RL-MSG TO RPT-TEXT.
           WRITE RPT-REC.
      *
      *D-270.  RC 8 is ONF202E or ONF203E and the record does not say
      *which.  engine/src/onfreq.c tests for an unknown stimulus code
      *FIRST, before any range check, so a request that reached RC 8
      *with a code this table knows can only have failed a range
      *check.  The two cannot disagree.
       RPT-MSG-RC8.
           MOVE 'ONF203E' TO W-MSG-ID.
           MOVE 'UNKNOWN STIMULUS CODE' TO W-MSG-TX.
           MOVE ZERO TO W-N.
           PERFORM RPT-MSG-KNOWN VARYING W-J FROM 1 BY 1
               UNTIL W-J IS GREATER THAN ONF-STIM-COUNT
               OR W-N = 1.
           IF W-N = 1
               MOVE 'ONF202E' TO W-MSG-ID
               MOVE 'REQUEST FIELD OUT OF RANGE' TO W-MSG-TX.
      *
       RPT-MSG-KNOWN.
           IF ONF-STIM-TEXT (W-J) = ONF-STIM-CODE
               MOVE 1 TO W-N.
      *
      *The 4 fingerprint bytes as 8 hexadecimal characters.  See the
      *note on W-BYTEW: the byte goes into the low half of a halfword
      *whose high half is binary zero, so the value is 0 to 255.
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
      *
       RPT-OUT-ENTRY.
           MOVE W-K TO RL-K.
           MOVE ONF-OUT-ID (W-K) TO RL-ID.
           MOVE ONF-OUT-LAT-US (W-K) TO RL-LAT.
           MOVE ONF-OUT-SPIKES (W-K) TO RL-SPK.
           PERFORM FIND-NAME.
      *ROUNDED, to the nearest tenth (D-272).  The guard is not
      *theatre: a rejected request carries no output entries, so this
      *is only reached with a duration the engine accepted, but a
      *zero here would be a divide-by-zero abend in the middle of a
      *report rather than a wrong number.
           MOVE ZERO TO W-HZ.
           IF ONF-SIM-MS IS GREATER THAN ZERO
               COMPUTE W-HZ ROUNDED =
                   (ONF-OUT-SPIKES (W-K) * 1000) / ONF-SIM-MS.
           MOVE W-HZ TO RL-HZ.
           MOVE ' ' TO RPT-CC.
           MOVE RL-OUTL TO RPT-TEXT.
           WRITE RPT-REC.
