      *ONFLY probe 2 of 3 (D-129): terminal I/O, without BMS.
      *
      *WHAT THIS ANSWERS
      *  Whether a 3270 can be talked to at all under Raincode's QIX,
      *  separately from whether BMS works.  Their documentation says
      *  the Terminal Server handles "TN3270 connections" and includes
      *  "the primary mapping support component (BMS)" - two claims, and
      *  BMS is the one more likely to be missing from a free edition.
      *  SEND TEXT needs no map, so this probe fails only if the
      *  terminal path itself is absent.
      *
      *  That split matters for D-127.  The transaction flow on a real
      *  3270 is half of what the owner asked for; if SEND TEXT works
      *  and SEND MAP does not, the demonstrator is still possible, just
      *  uglier - character output instead of a formatted screen.
      *
      *HOW TO DRIVE IT
      *  Point a 3270 client at QIX's Terminal Server and invoke the
      *  transaction this program is defined under.  Type anything; it
      *  is echoed back with a fixed banner.
      *
      *  The same client works against TK5's VTAM, which is why TBD-17
      *  is one install rather than two (VL-34).
      *
       IDENTIFICATION DIVISION.
       PROGRAM-ID. ONFCTRM.
      *
       ENVIRONMENT DIVISION.
       DATA DIVISION.
       WORKING-STORAGE SECTION.
       01  ONF-IN-BUF                 PIC X(80) VALUE SPACES.
       01  ONF-IN-LEN                 PIC S9(4) COMP VALUE 80.
       01  ONF-OUT-MSG.
           05  FILLER                 PIC X(22)
               VALUE 'ONFLY terminal probe: '.
           05  ONF-ECHO               PIC X(50).
       01  ONF-OUT-LEN                PIC S9(4) COMP VALUE 72.
      *
       PROCEDURE DIVISION.
       ONFCTRM-MAIN.
           MOVE SPACES TO ONF-IN-BUF.
           MOVE 80 TO ONF-IN-LEN.
      *
           EXEC CICS RECEIVE
                INTO(ONF-IN-BUF)
                LENGTH(ONF-IN-LEN)
           END-EXEC.
      *
           MOVE ONF-IN-BUF (1:50) TO ONF-ECHO.
      *
           EXEC CICS SEND TEXT
                FROM(ONF-OUT-MSG)
                LENGTH(ONF-OUT-LEN)
                ERASE
           END-EXEC.
      *
           EXEC CICS RETURN
           END-EXEC.
      *
           GOBACK.
