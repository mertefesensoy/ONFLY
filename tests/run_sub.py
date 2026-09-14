# -*- coding: utf-8 -*-
"""Regression test for tools/mvsub.py's job-output summariser (D-249).

WHY THIS TEST EXISTS
--------------------
`summarise()` is what turns a few thousand lines of JES2 printer output
into the handful of lines that reach a person -- and, through the gate
tooling, into the lines that reach a gate record.  It had a bare `ABEND`
in its alternation, so any line merely CONTAINING those five letters was
reported as an abend.

That is not hypothetical.  Gate G0 (D-241) listed the members of
SYS2.JCLLIB, two of which are named `JOBABEND` and `ABEND0C1`, and the
summary of a job that ended cleanly read:

    IEF142I ONFG0CAT AMSLIST - STEP WAS EXECUTED - COND CODE 0004
      JOBABEND
      ABEND0C1

A false abend in a gate record is worse than silence: the reader has to
go and disprove it before trusting anything else in the record.

The fix is a word boundary on each side.  The risk of a fix like that is
the opposite failure -- silently dropping a REAL abend -- so this test
pins both directions: every form MVS actually uses must still be kept,
and the two member names must not be.

Run:  python tests/run_sub.py
Exit status 0 when every case passes, 1 otherwise.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import mvsub                                                   # noqa: E402

# (line, must_be_kept, why)
CASES = [
    # --- the D-249 false positives: member names, not abends ----------
    ("  JOBABEND", False, "SYS2.JCLLIB member name"),
    ("  ABEND0C1", False, "SYS2.JCLLIB member name"),
    ("  ABENDLIST", False, "a name merely starting with ABEND"),
    ("  TESTABEND", False, "a name merely ending with ABEND"),

    # --- real abends, which must survive the fix -----------------------
    ("IEF450I ONFG0CAT GO - ABEND S0C4 U0000", True, "IEF450I abend"),
    ("  ABEND=S806", True, "ABEND= form"),
    ("$HASP395 ONFG0CAT ENDED - ABENDED", True, "ABENDED"),
    ("IEF472I ONFJOB STEP1 - COMPLETION CODE - SYSTEM=0C1", True,
     "completion code, the word ABEND never appears"),
    ("  SYSTEM ABEND 0C1", True, "ABEND followed by a space"),

    # --- ordinary step results, unaffected ------------------------------
    ("IEF142I ONFG0CAT TSOLIST - STEP WAS EXECUTED - COND CODE 0000",
     True, "step result"),
    ("IEC501A M 480,ONFNET,NL,6250 BPI", True, "IEC message"),
    ("IEW0000     ENTRY ST000000", True, "linkage editor"),
    ("IEB352I WARNING : OUTPUT RECFM COPIED FROM INPUT", True, "warning"),

    # --- plain listing text, which must not be kept ---------------------
    ("  ARCHCOMP", False, "an ordinary member name"),
    ("       VOLSER------------TK5002", False, "catalog detail"),
]


def main():
    passed = failed = 0
    for line, want, why in CASES:
        got = bool(mvsub.KEEP_RE.search(line))
        if got == want:
            passed += 1
        else:
            failed += 1
            sys.stdout.write(
                "run_sub: FAIL  %-58s expected %s (%s)\n"
                % (repr(line), "kept" if want else "dropped", why))

    # And the whole-summary behaviour the defect actually showed up in.
    out = ("IEF142I ONFG0CAT AMSLIST - STEP WAS EXECUTED - COND CODE 0004\n"
           "  JOBABEND\n"
           "  ABEND0C1\n")
    got = mvsub.summarise(out)
    if len(got) == 1 and "COND CODE 0004" in got[0]:
        passed += 1
    else:
        failed += 1
        sys.stdout.write("run_sub: FAIL  clean job still summarised as %r\n"
                         % (got,))

    sys.stdout.write("run_sub: %d passed, %d failed\n" % (passed, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
