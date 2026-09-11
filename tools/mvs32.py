# -*- coding: utf-8 -*-
"""Run TT-01/32, the 32-bit integer self-test, under GCCMVS (D-118).

NR-14, as D-118 amended it, requires an integer self-test for each width
the platform's engine actually uses.  Under NR-03 and D-105 the MVS engine
is SoftFloat 2c, which uses no 64-bit integer at all, so 32 bits is the
width that matters there and this is the test Gate G1's exit criterion
names for MVS.

It is not a formality.  GCCMVS has been measured compiling, linking,
running and returning a WRONG answer for a variable 64-bit left shift
(VL-19), and nothing in that measurement says anything about its 32-bit
code generation.

The expected answers come from Python with explicit 32-bit masking
(tools/gen32v.py), so they share no code with what they check.  The same
binary runs on x86 as `make tt0132`; a disagreement between the two is a
platform difference, which is what the test exists to find.

Run:  python tools/mvs32.py [--print]
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import mvsbld  # noqa: E402
import mvsub  # noqa: E402

JOB = "ONF32"


def main(argv):
    deck = mvsbld.build(JOB, "ONFLY TT-01/32",
                        [("tests/tst32.c", "TST32")],
                        headers=[("generated/onf32v.h", "ONF32V")])
    mvsub.check_cards(deck)
    if "--print" in argv:
        sys.stdout.write("\n".join(deck) + "\n")
        return 0

    sys.stdout.write("mvs32: %d cards, longest %d columns, GCCMVS %s\n"
                     % (len(deck), max(len(c) for c in deck), mvsbld.OPT))
    before = mvsub.submit(deck)
    out = mvsub.collect(JOB, before, timeout=900, poll=5)
    if out is None:
        sys.stderr.write("mvs32: %s did not finish in 900 s\n" % JOB)
        return 1

    sys.stdout.write("=== step results ===\n")
    for line in mvsub.summarise(out):
        sys.stdout.write("  %s\n" % line[:116])

    sys.stdout.write("=== diagnostics ===\n")
    seen = set()
    for line in out.splitlines():
        s = line.strip()
        if (s.startswith("<stdin>") or "Internal compiler" in s
                or re.search(r"IFO\d{3} ", s)):
            if s not in seen:
                sys.stdout.write("  %s\n" % s[:112])
                seen.add(s)
    if not seen:
        sys.stdout.write("  (none)\n")

    sys.stdout.write("=== TT-01/32 on MVS ===\n")
    wrong = None
    for line in out.splitlines():
        s = line.strip()
        if s.startswith("T32 ") or s.startswith("# tst32"):
            sys.stdout.write("  %s\n" % s[:112])
        m = re.search(r"# tst32 (\d+) of (\d+) vectors wrong", s)
        if m:
            wrong = int(m.group(1))
    if wrong is None:
        sys.stdout.write("  (no result lines; it did not run)\n")
        return 1
    return 0 if wrong == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
