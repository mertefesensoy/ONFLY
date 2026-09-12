# -*- coding: utf-8 -*-
"""Is IND$FILE present on TK5 at all?  (Gate G2, IR-TRN-02)

A-07 names IND$FILE as one of three candidate transports and D-141
recorded its presence on TK5 as unverified.  Before any effort goes
into scripting a TSO logon and a 3270 file transfer, this asks the
cheap question: does the module exist?

HOW IT ANSWERS
--------------
A job step that names a program MVS cannot find abends **S806**.  So a
step of `EXEC PGM=IND$FILE` distinguishes the cases without a terminal,
without TSO and without a transfer:

  S806              the module is not in any searched library --
                    IND$FILE is not available on this system
  anything else     the module exists and was entered; it will very
                    likely fail, because IND$FILE expects to be called
                    under TSO with a terminal attached, and that
                    failure is not interesting.  What matters is that
                    it was FOUND.

This cannot prove IND$FILE is usable, only whether it is there.  A
module that loads may still be unusable from batch, and one that is
absent from the batch search order could in principle live somewhere
only TSO sees.  Both limits are stated rather than glossed: the test
is cheap and narrow, and is worth exactly what it measures.

usage:  python tools/mvsind.py [--print]
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import mvsbld  # noqa: E402
import mvsub  # noqa: E402

JOB = "ONFIND"


def deck():
    d = []

    def a(card):
        if card.startswith("//") and len(card) > mvsbld.JCL_FIELD:
            raise mvsbld.DeckError("JCL past column %d: %r"
                                   % (mvsbld.JCL_FIELD, card))
        d.append(card)

    a("//%-8s JOB (001),'ONFLY INDFILE PROBE',CLASS=A,MSGCLASS=A,"
      % JOB)
    a("//             USER=%s,PASSWORD=CUL8TR," % mvsbld.USER)
    a("//             REGION=4M,TIME=1,MSGLEVEL=(1,1)")
    a("//*")
    # TIME=1 caps it at a minute: if the module exists and waits for a
    # terminal that will never answer, the step ends on its own rather
    # than holding an initiator on a lab the parallel session shares.
    a("//PROBE    EXEC PGM=IND$FILE")
    a("//SYSPRINT DD SYSOUT=*")
    a("//SYSTERM  DD SYSOUT=*")
    a("//SYSIN    DD DUMMY")
    a("//")
    return d


def main(argv):
    try:
        sys.stdout.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass

    d = deck()
    mvsub.check_cards(d)
    if "--print" in argv:
        sys.stdout.write("\n".join(d) + "\n")
        return 0

    before = mvsub.submit(d)
    out = mvsub.collect(JOB, before, timeout=600, poll=3)
    if out is None:
        sys.stderr.write("mvsind: %s did not finish\n" % JOB)
        return 1

    sys.stdout.write("=== step results ===\n")
    for line in mvsub.summarise(out):
        sys.stdout.write("  %s\n" % line[:116])

    if re.search(r"ABEND S806|806-", out):
        sys.stdout.write("\nmvsind: S806 -- IND$FILE is NOT present in "
                         "the batch search order on this system.\n")
        return 1
    sys.stdout.write("\nmvsind: no S806 -- the module was FOUND. "
                     "Whatever it did next is a separate question.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
