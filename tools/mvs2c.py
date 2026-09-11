# -*- coding: utf-8 -*-
"""Compile SoftFloat 2c under GCCMVS and run TestFloat-derived vectors.

D-105 invokes NR-03 and vendors Release 2c because Gate G1 measured that
GCCMVS cannot build Release 3e: four independent defects, one of them
silent (VL-19, VL-21).  2c's `bits32` build uses only 32-bit integers, so
none of the four has anything to act on -- and D-108 put testing that on
GCCMVS ahead of every other piece of work, because it is the claim the
whole fallback rests on and it had never been tested.

D-106 already proved on x86 that 2c agrees with TestFloat on all six
operations ONFLY uses, 260,376 cases, zero mismatches (VL-22).  This is the
same arithmetic on the machine it was chosen for.

THE AMALGAMATION (D-110)
------------------------
2c's softfloat.c contains

    #include "milieu.h"
    #include "softfloat.h"
    #include "softfloat-macros"
    #include "softfloat-specialize"

and GCCMVS resolves an include to the PDS member named by the first EIGHT
characters of the name (VL-23), so the last three all name SOFTFLOA and
three files cannot occupy one member.  D-109's probe read the compiler's
own option list and tested `-remap`, GCC's mechanism for exactly this
situation, which is accepted and inert on this port (VL-24).  There is no
way to present these four names to a PDS build.

So the unit is amalgamated: the quoted includes are inlined in order,
recursively, from the unmodified vendored and generated files.  The map
below is stated rather than derived, and an include it does not name is an
error -- if upstream ever grows another `#include`, this stops rather than
leaving it to resolve against the wrong member.

Nothing is written to disk.  The expansion is built into the deck on every
run, so there is never a second copy of the source to drift from the first.
`--print` writes the whole deck to stdout for inspection.

Run:  python tools/mvs2c.py [--print]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import mvsbld  # noqa: E402
import mvsub  # noqa: E402

JOB = "ONF2C"
B32 = "third_party/SoftFloat-2c/softfloat/bits32/"

# Include spelling -> repository file.  Stated, never derived (D-110).
INCLUDES = {
    "milieu.h": "softfloat/c2c/milieu.h",
    "softfloat.h": "softfloat/c2c/softfloat.h",
    "softfloat-macros": B32 + "softfloat-macros",
    "softfloat-specialize": "softfloat/c2c/softfloat-specialize",
    "onfproc.h": "softfloat/c2c/onfproc.h",
}

UNIT = B32 + "softfloat.c"


def main(argv):
    # D-111: the C-04 renames go in front of upstream's source, so the
    # externals GCCMVS emits are eight characters and unique.  Without
    # them Assembler XF rejects the unit with "IFO196 FLOAT64@ HAS BEEN
    # PREVIOUSLY DEFINED" and two siblings (VL-25).  Prepending rather
    # than #including keeps the amalgamated unit self-contained, which is
    # the whole point of amalgamating it.
    body = (mvsbld.cards_of("generated/onf2cnm.h")
            + mvsbld.amalgamate(UNIT, INCLUDES))
    order = mvsbld.amalgamated_order(UNIT, INCLUDES)

    # The amalgamated unit needs no headers -- everything is inlined.  The
    # driver needs the two declaration headers and the vector table, and
    # those four names have distinct first-eight characters, so they do not
    # run into VL-23.
    deck = mvsbld.build(
        JOB, "ONFLY SOFTFLOAT 2C",
        # The vendored unit compiles without -pedantic-errors, exactly as
        # the x86 Makefile's C2CFLAGS does and for the same reason: 2c
        # warns in float64_rem about pointer signedness, -pedantic-errors
        # makes that fatal, and third_party is not edited (D-28, D-35).
        # ONFLY's own driver stays strict.
        [(body, "SF2C", mvsbld.CC_FLAGS_VENDOR),
         ("tests/tst2c.c", "TST2C")],
        headers=[("softfloat/c2c/milieu.h", "MILIEU"),
                 ("softfloat/c2c/softfloat.h", "SOFTFLOA"),
                 ("softfloat/c2c/onfproc.h", "ONFPROC"),
                 ("generated/onf2cnm.h", "ONF2CNM"),
                 ("generated/onf2cv.h", "ONF2CV")])
    mvsub.check_cards(deck)

    if "--print" in argv:
        sys.stdout.write("\n".join(deck) + "\n")
        return 0

    sys.stdout.write("mvs2c: amalgamated %s -> %d cards, inlining %s\n"
                     % (UNIT, len(body), ", ".join(order)))
    sys.stdout.write("mvs2c: %d cards in the deck, longest %d columns, "
                     "GCCMVS %s\n"
                     % (len(deck), max(len(c) for c in deck), mvsbld.OPT))

    before = mvsub.submit(deck)
    out = mvsub.collect(JOB, before, timeout=1200, poll=5)
    if out is None:
        sys.stderr.write("mvs2c: %s did not finish in 1200 s\n" % JOB)
        return 1

    sys.stdout.write("=== step results ===\n")
    for line in mvsub.summarise(out):
        sys.stdout.write("  %s\n" % line[:116])

    sys.stdout.write("=== compiler and assembler diagnostics ===\n")
    seen = set()
    for line in out.splitlines():
        s = line.strip()
        if (s.startswith("<stdin>") or "Internal compiler" in s
                or "IFO1" in s or "IEW0" in s or "UNRESOLVED" in s):
            if s not in seen:
                sys.stdout.write("  %s\n" % s[:112])
                seen.add(s)
    if not seen:
        sys.stdout.write("  (none)\n")

    sys.stdout.write("=== tst2c on MVS ===\n")
    shown = 0
    for line in out.splitlines():
        s = line.strip()
        if s.startswith("SF2C ") or s.startswith("# tst2c"):
            sys.stdout.write("  %s\n" % s[:112])
            shown += 1
    if not shown:
        sys.stdout.write("  (no result lines; the unit did not run)\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
