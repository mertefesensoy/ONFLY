      *Stimulus codes, generated from layout/master.py STIM_CODES
      *(FR-BAT-05, D-270, D-271).  Membership only: the numeric ids
      *live in the fingerprint (IR-COM-05), never in the report.
       01  ONF-STIM-CODES.
      *  SUGR = 1, implemented
           05  FILLER                 PIC X(4)
               VALUE 'SUGR'.
      *  WATR = 2, reserved, ONF201W
           05  FILLER                 PIC X(4)
               VALUE 'WATR'.
      *  BITR = 3, reserved, ONF201W
           05  FILLER                 PIC X(4)
               VALUE 'BITR'.
       01  ONF-STIM-TAB REDEFINES ONF-STIM-CODES.
           05  ONF-STIM-TEXT          PIC X(4)
               OCCURS 3 TIMES.
       01  ONF-STIM-COUNT             PIC S9(4) COMP
               VALUE +3.
