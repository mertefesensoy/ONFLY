# -*- coding: utf-8 -*-
"""Run the ONFLY kernel on MVS 3.8j through the SOFT2C backend (D-121, D-122).

tools/mvsunit.py got ONFLY's integer units onto MVS.  This is the other
half: the simulation kernel itself (FR-SIM-01, Appendix C), the onf_fp
float API, and the SoftFloat 2c backend underneath it.  It is the first
binary64 arithmetic ONFLY has performed on MVS through its own API rather
than through a SoftFloat test driver, and the first time the kernel has
run anywhere other than x86.

HOW IT IS JUDGED
----------------
tests/tstker.c builds a 64-neuron synthetic network, PRINTS it, runs the
kernel on it and prints the per-neuron results.  tests/run_ker.py parses
the printed network, runs the independent Python oracle (O-1) on that very
network, and compares the results.  So the network travels from MVS to the
oracle: the oracle simulates exactly what MVS simulated, and neither side
can see the other's answers.

That is why no vector table is shipped here, the same argument
tools/mvsunit.py makes.  It is stronger than a shipped table, because the
comparison is against an oracle rather than against an earlier x86 run.

WHY THE 2c UNIT IS AMALGAMATED AND RENAMED
------------------------------------------
Both carried over from tools/mvs2c.py, and both are measured constraints,
not preferences.  D-110: GCCMVS resolves a quoted include to a PDS member
named by the first eight characters of the name with its extension
dropped, so softfloat.h, softfloat-macros and softfloat-specialize all
collide on SOFTFLOA (VL-23, VL-24) -- the library reaches the compiler as
one amalgamated unit assembled at submit time and never written to disk.
D-111: 38 of 2c's externals collide at eight characters and Assembler XF
rejects them (VL-25), so a generated #define prologue renames them.

engine/src/onffp2.c calls into the library, so it carries the same
prologue: caller and callee agree by construction rather than by care.

A SYNTHETIC NETWORK, NOT THE REAL ONE
-------------------------------------
The MVP network is 885 KB of binary and reaching MVS with it needs a
binary-transparent transport, which is Gate G2 and is not done.  What this
job can therefore establish is that the kernel computes Appendix C exactly
on MVS -- which is independent of which network it is fed, exactly as
tests/tstker.c argues for Phase B.

Run:  python tools/mvsker.py [--print]
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
import run_ker  # noqa: E402

JOB = "ONFKER"

# The include-name to file mapping for the amalgamation.  Stated by the
# caller, never derived (D-110).
B32 = "third_party/SoftFloat-2c/softfloat/bits32/"
INCLUDES = {
    "milieu.h": "softfloat/c2c/milieu.h",
    "softfloat.h": "softfloat/c2c/softfloat.h",
    "softfloat-macros": B32 + "softfloat-macros",
    "softfloat-specialize": "softfloat/c2c/softfloat-specialize",
    "onfproc.h": "softfloat/c2c/onfproc.h",
}
UNIT = "softfloat/c2c/softfloat.c"

# Quoted includes.  ONFLY's own header names are unique in eight characters
# by C-04 discipline, so unlike SoftFloat's they need no amalgamation.
HEADERS = [
    ("engine/include/onfplat.h", "ONFPLAT"),
    ("engine/include/onffp.h", "ONFFP"),
    ("engine/include/onfker.h", "ONFKER"),
    ("engine/include/onfrnd.h", "ONFRND"),
    ("engine/include/onfstm.h", "ONFSTM"),
    ("softfloat/c2c/milieu.h", "MILIEU"),
    ("softfloat/c2c/softfloat.h", "SOFTFLOA"),
    ("softfloat/c2c/onfproc.h", "ONFPROC"),
]

# The record shapes tstker.c prints: the network it built, then the results.
# Anything else in the listing is JES2's, not the program's.
#
# The banner needs its own alternative rather than sharing the others' \b:
# it opens "# tstker ...", and there is no word boundary between "#" and a
# space, so "#\b" never matches it.  Without the banner the report cannot
# name the backend the run used, and naming it from a string here instead
# is how an MVS result gets attributed to the wrong float library.
RESULT = re.compile(
    r"^\s*(?:#\s|NET\b|CONST\b|PROP\b|ROW\b|EDGE\b|STIM\b|READ\b|RUN\b|OUT\b)")


def main(argv):
    prologue = mvsbld.cards_of("generated/onf2cnm.h")
    library = prologue + mvsbld.amalgamate(UNIT, INCLUDES)
    order = mvsbld.amalgamated_order(UNIT, INCLUDES)
    backend = mvsbld.with_defines("engine/src/onffp2.c",
                                  ["ONF_FP_SOFT2C"], prologue)

    # Every ONFLY unit is preceded by `#define ONF_FP_SOFT2C 1`, which
    # is what -DONF_FP_SOFT2C does on x86.  It cannot be an option here:
    # the compile PARM card is 67 columns and a JCL field ends at 71.
    # Without it the program links 2c and then reports SOFT3E in its
    # manifest, which NFR-OBS-01 and D-124 both forbid.
    def onfly(relpath):
        return mvsbld.with_defines(relpath, ["ONF_FP_SOFT2C"])

    sources = [
        # The vendored unit compiles without -pedantic-errors, exactly as the
        # x86 Makefile's C2CFLAGS does and for the same reason: 2c warns in
        # float64_rem about pointer signedness, -pedantic-errors makes that
        # fatal, and third_party is not edited (D-28, D-35).
        (library, "SF2C", mvsbld.CC_FLAGS_VENDOR),
        (backend, "ONFFP2C"),
        (onfly("engine/src/onffpc.c"), "ONFFPCC"),
        (onfly("engine/src/onfrnd.c"), "ONFRNDC"),
        (onfly("engine/src/onfstm.c"), "ONFSTMC"),
        (onfly("engine/src/onfker.c"), "ONFKERC"),
        (onfly("tests/tstker.c"), "TSTKERC"),
    ]

    deck = mvsbld.build(JOB, "ONFLY KERNEL 2C", sources, headers=HEADERS)
    mvsub.check_cards(deck)
    if "--print" in argv:
        sys.stdout.write("\n".join(deck) + "\n")
        return 0

    sys.stdout.write("mvsker: amalgamated %s -> %d cards, inlining %s\n"
                     % (UNIT, len(library), ", ".join(order)))
    sys.stdout.write("mvsker: %d cards, longest %d columns, GCCMVS %s\n"
                     % (len(deck), max(len(c) for c in deck), mvsbld.OPT))

    before = mvsub.submit(deck)
    out = mvsub.collect(JOB, before, timeout=3600, poll=5)
    if out is None:
        sys.stderr.write("mvsker: %s did not finish in 3600 s\n" % JOB)
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

    lines = [l.rstrip().strip() for l in out.splitlines()
             if RESULT.match(l.rstrip())]
    sys.stdout.write("=== kernel vs oracle on MVS 3.8j ===\n")
    sys.stdout.write("  %d result lines recovered from the job listing\n"
                     % len(lines))
    if not lines:
        sys.stderr.write("mvsker: the program printed nothing; see above\n")
        return 1

    r = run_ker.compare("\n".join(lines))
    # The backend and platform come from the program's own banner,
    # never from a string written here.
    sys.stdout.write("  run_ker [%s backend, %s]: %d passed, %d failed\n"
                     % (r.backend, mvsbld.PLATFORM, r.passed, r.failed))
    for line in r.lines[:20]:
        sys.stdout.write("  %s\n" % line)
    return 1 if r.failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
