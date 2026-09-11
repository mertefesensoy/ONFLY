# -*- coding: utf-8 -*-
"""Find out what clock an ONFLY program has on MVS 3.8j (Gate G3).

Gate G3 must produce a measured time per neuron-step on TK5, and
NFR-PERF-01 states its five-minute limit in wall-clock time.  Both need
a clock, and what PDPCLIB actually implements of <time.h> is not
something to assume -- D-92 records what guessing at an interface
costs.

This submits tests/tstclk.c on its own: one small translation unit, no
ONFLY headers, no SoftFloat.  A full engine deck takes minutes to
compile, and this question deserves a fast answer before that cost is
paid.

It also records the host wall-clock time around the submission.  That
is the second half of the answer: if the guest's clocks turn out to be
unusable, host-side timing of a job whose work varies is still a valid
route to a marginal cost per neuron-step, and knowing the round-trip
overhead is what makes that route practical.

Run:  python tools/mvsclk.py [--print]
"""
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import mvsbld  # noqa: E402
import mvsub  # noqa: E402

JOB = "ONFCLK"

# The program's own output, plus the MVS step accounting message.
# IEF374I carries the step's CPU time at centisecond resolution and is
# issued by MVS itself, so it is a cross-check on whatever the C
# library reports -- two independent clocks disagreeing is worth
# knowing before either is used for G3.
RESULT = re.compile(r"^\s*(?:#\s|CPS\b|T0\b|T1\b|TICK\b|DIFF\b|GUARD\b)")
STEPACC = re.compile(r"IEF374I|IEF373I|CPU\s+\d+MIN")


def main(argv):
    sources = [(mvsbld.cards_of("tests/tstclk.c"), "TSTCLKC")]
    deck = mvsbld.build(JOB, "ONFLY CLOCK PROBE", sources)
    mvsub.check_cards(deck)
    if "--print" in argv:
        sys.stdout.write("\n".join(deck) + "\n")
        return 0

    sys.stdout.write("mvsclk: %d cards, longest %d columns, GCCMVS %s\n"
                     % (len(deck), max(len(c) for c in deck), mvsbld.OPT))

    t0 = time.time()
    before = mvsub.submit(deck)
    out = mvsub.collect(JOB, before, timeout=1800, poll=3)
    elapsed = time.time() - t0
    if out is None:
        sys.stderr.write("mvsclk: %s did not finish in 1800 s\n" % JOB)
        return 1

    sys.stdout.write("mvsclk: host wall clock for the whole round trip: "
                     "%.1f s\n" % elapsed)

    sys.stdout.write("=== step results ===\n")
    for line in mvsub.summarise(out):
        sys.stdout.write("  %s\n" % line[:116])

    sys.stdout.write("=== MVS step accounting ===\n")
    acct = [l.rstrip() for l in out.splitlines() if STEPACC.search(l)]
    for line in acct[:12]:
        sys.stdout.write("  %s\n" % line.strip()[:116])
    if not acct:
        sys.stdout.write("  none found -- IEF374I is not in this "
                         "listing, so MVS step CPU time is not "
                         "available as a cross-check\n")

    sys.stdout.write("=== program output ===\n")
    lines = [l.rstrip().strip() for l in out.splitlines()
             if RESULT.match(l.rstrip())]
    if not lines:
        sys.stderr.write("mvsclk: the program printed nothing\n")
        return 1
    for line in lines:
        sys.stdout.write("  %s\n" % line[:116])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
