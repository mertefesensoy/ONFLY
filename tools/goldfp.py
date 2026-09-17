# -*- coding: utf-8 -*-
"""The Section 8.4 golden fingerprints, written out, in one place.

WHY THIS FILE EXISTS RATHER THAN A CONSTANT IN EACH CALLER
----------------------------------------------------------
Three things now need the `srext` half of the golden suite as DATA: TU-11
(`tests/test_strm.py`), the Stage 5 fingerprint panel (`tools/liveview.py`)
and the MVS stream comparison (`tools/mvsstm.py`).  Two copies of a table
of constants is the condition that produced D-289 and then D-360 -- the same
ACC-3 defect, twice, silently -- and the answer both times was one
implementation with the callers pointing at it.

WHY THE VALUES ARE WRITTEN OUT AND NOT COMPUTED
-----------------------------------------------
These are the fingerprints SRS Section 8.3 rows 6 and 7 RECORD, produced on
TK5 MVS 3.8j under GCCMVS and under JCC on 2026-09-15 (VL-91, VL-93) and
matching x86-64 and Linux s390x before that.  A table this file derived by
running the engine could not contradict a defect it shared with the engine,
so it would check nothing.  Changing a value here is changing what ACC-5
claims, and should be as visible as that deserves.

Keyed by stimulus rate, which is what distinguishes the five `srext`
requests: they share a stimulus, a duration and a seed.
"""

#: G-15 to G-19, the five srext golden requests.  All SUGR, 1000 ms, seed 1.
SREXT = {
    0: "6C3F7272",         # G-15, silence on the shipped network (ACC-2)
    40: "BAF81D91",        # G-16, a rate Appendix C step 0 samples exactly
    200: "F9C7EE77",       # G-17, the top row of the compensating table
    9999: "4FD0ED1E",      # G-18, beyond the table; selection clamps (D-191)
    100: "C4C320BC",       # G-19, D-191's tie rule, resolving to 80 Hz
}

#: The Section 8.4 identifier for each, for reports that name the request
#: rather than its rate.
SREXT_ID = {0: "G-15", 40: "G-16", 200: "G-17", 9999: "G-18", 100: "G-19"}
