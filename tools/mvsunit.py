# -*- coding: utf-8 -*-
"""Run TU-03, TU-04 and TU-05 on MVS 3.8j under GCCMVS (D-121, D-122).

This is the first ONFLY ENGINE code to be compiled on MVS.  Everything the
project has run there so far -- TT-01/32 (VL-30), TT-02 (VL-29), the 2c
known answers (VL-26) -- was the float library and its drivers.  The three
units here are engine sources: the CRC-32 the network integrity checks rest
on (IR-NET-07, FR-LOD-02), the xorshift32 PRNG that makes every request
reproducible (NR-13, FR-SIM-04), and the integer-only stimulus draw
(NR-12, FR-SIM-03).

WHY THE EXPECTED ANSWERS ARE NOT SHIPPED
----------------------------------------
tools/mvs32.py and tools/mvstf2.py both carry a generated vector table to
MVS, because their subjects are arithmetic primitives whose inputs have to
be enumerated.  These three units need no such table: tests/tstunit.c
computes and PRINTS its results, and tests/run_units.py recomputes every
one of them in the Python oracle.  So the MVS job's own printed output is
captured from the job listing and handed to the same comparison that
judges the x86 build.

That is worth more than a shipped table.  A table proves MVS agrees with
values x86 computed earlier; this proves MVS agrees with an oracle that
shares no code with either build, and it uses the identical comparison on
both platforms, so the two cannot drift.

WHAT IT DOES NOT COVER
----------------------
No floating point.  onfcrc, onfrnd and onfstm are integer-only by
construction -- NR-12 exists precisely so the stimulus needs no float --
so this says nothing about the kernel or the onf_fp backend on MVS.

Run:  python tools/mvsunit.py [--print]
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tests"))

import mvsbld  # noqa: E402
import mvsub  # noqa: E402
import run_units  # noqa: E402

JOB = "ONFUNIT"

# The engine units, in link order, with the PDS member each becomes.  Stated
# rather than derived, for the reason mvsbld.build() gives.
#
# The trailing C distinguishes each translation unit's member from its
# header's below.  mvsbld keeps member names unique across both libraries
# even though they are separate datasets, and that check is worth more than
# the convenience of matching names: a header and a source that share a name
# would otherwise differ only by which DD found them.  Only the header names
# are forced -- they are what #include resolves to (VL-23) -- so these are
# the ones that move.
SOURCES = [
    ("tests/tstunit.c", "TSTUNITC"),
    ("engine/src/onfcrc.c", "ONFCRCC"),
    ("engine/src/onfrnd.c", "ONFRNDC"),
    ("engine/src/onfstm.c", "ONFSTMC"),
]

# Quoted includes.  GCCMVS resolves #include "onfcrc.h" to the member given
# by the name with its extension dropped, uppercased and truncated to eight
# characters (VL-23), so these member names are what the sources already ask
# for.  Unlike SoftFloat's, ONFLY's header names are unique in eight
# characters by C-04 discipline, so no amalgamation is needed here.
HEADERS = [
    ("engine/include/onfplat.h", "ONFPLAT"),
    ("engine/include/onfcrc.h", "ONFCRC"),
    ("engine/include/onfrnd.h", "ONFRND"),
    ("engine/include/onfstm.h", "ONFSTM"),
]

# tstunit.c prints one record per line in these three shapes, plus a banner
# naming the platform.  Anything else in the listing is JES2's, not the
# program's.
#
# The banner needs its own alternative: it opens "# tstunit ...", and there
# is no word boundary between "#" and a space.  It is anchored at the start
# of a line for a reason that cost a job to learn -- GCCMVS echoes the
# SOURCE into the listing too, so the printf format string that produces
# this banner appears there as well, and a pattern that matched anywhere on
# a line found `%s` and reported it as the platform.
RESULT = re.compile(r"^\s*(?:#\s|CRC\s|PRNG\s|STIM\s)")


def harvest(out):
    """The program's own output lines, taken out of the job listing."""
    lines = []
    for line in out.splitlines():
        # The listing is column-oriented and printf output arrives with the
        # ASA carriage-control character in column 1, so both a leading
        # blank and the record's own indentation have to go.
        s = line.rstrip()
        if RESULT.match(s):
            lines.append(s.strip())
    return lines


def main(argv):
    deck = mvsbld.build(JOB, "ONFLY TU-03/04/05", SOURCES, headers=HEADERS)
    mvsub.check_cards(deck)
    if "--print" in argv:
        sys.stdout.write("\n".join(deck) + "\n")
        return 0

    sys.stdout.write("mvsunit: %d cards, longest %d columns, GCCMVS %s\n"
                     % (len(deck), max(len(c) for c in deck), mvsbld.OPT))
    before = mvsub.submit(deck)
    out = mvsub.collect(JOB, before, timeout=1800, poll=5)
    if out is None:
        sys.stderr.write("mvsunit: %s did not finish in 1800 s\n" % JOB)
        return 1

    sys.stdout.write("=== step results ===\n")
    for line in mvsub.summarise(out):
        sys.stdout.write("  %s\n" % line[:116])

    sys.stdout.write("=== diagnostics ===\n")
    seen = {}
    for line in out.splitlines():
        s = line.strip()
        # A real Assembler XF message starts the line.  The D-111
        # prologue quotes IFO196 inside a comment block, and GCCMVS
        # echoes the source into the listing, so an unanchored search
        # reports the explanation as the failure.
        if (s.startswith("<stdin>") or "Internal compiler" in s
                or re.match(r"IFO\d{3}\b", s)):
            if s not in seen:
                seen[s] = 1
                sys.stdout.write("  %s\n" % s[:116])
    if not seen:
        sys.stdout.write("  none\n")

    lines = harvest(out)
    sys.stdout.write("=== TU-03, TU-04, TU-05 on MVS 3.8j ===\n")
    sys.stdout.write("  %d result lines recovered from the job listing\n"
                     % len(lines))
    if not lines:
        sys.stderr.write("mvsunit: the program printed nothing; see above\n")
        return 1

    # The platform comes from the program's own banner, never from a string
    # written here.  tstunit prints "# tstunit on platform <id>", which is
    # onfplat.h's ONF_PLATID for whatever it was compiled on (NFR-OBS-01).
    # Labelling a result from this file instead is how a run gets reported
    # for a platform it never touched.
    #
    # Searched in the HARVESTED lines, not the raw listing: the listing also
    # contains the source, so the printf that produces this banner is in it
    # too, and searching the raw text once reported the platform as `%s`.
    platform = "?"
    for line in lines:
        m = re.match(r"#\s+tstunit on platform (\S+)", line)
        if m:
            platform = m.group(1)
            break

    r = run_units.compare("\n".join(lines))
    sys.stdout.write("  run_units [%s]: %d passed, %d failed\n"
                     % (platform, r.passed, r.failed))
    for line in r.lines:
        sys.stdout.write("  %s\n" % line)
    return 1 if r.failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
