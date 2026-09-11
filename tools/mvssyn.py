# -*- coding: utf-8 -*-
"""Run the whole ONFLY engine path on MVS 3.8j, over an embedded network.

This is the deepest ONFLY has reached on MVS.  tools/mvsunit.py took the
integer units there; tools/mvsker.py took the kernel and the SOFT2C
backend.  What was still missing was everything that touches the network
FILE FORMAT -- the decoder, the FR-LOD-02 integrity checks, the
big-endian payload load and the IR-COM-05 response fingerprint -- because
tstdec.c and tstgld.c both open a file and no file can reach MVS until
Gate G2 chooses and proves a binary-transparent transport.

tests/tstsyn.c carries a complete ONFNET image as a C array instead
(generated/onfsynt.h, from tools/gensyn.py).  It travels through the same
card reader as every other ONFLY source.

This does not stand in for Gate G2 and does not weaken it.  It answers a
different question: whether the DECODER is correct on a big-endian EBCDIC
host, as opposed to whether a file can be moved onto one intact.  Those
are exactly the two halves of risk R-07, and only the second is Gate G2's.

The parts of FR-LOD-02 that MVS is uniquely placed to test are the ones
worth having here: IR-NET-04's byte-order sentinel, which exists to catch a
text-mode transfer, and IR-NET-08's zero-padded FB dataset, which is what
every MVS dataset looks like and what no other platform produces.

Judged the same way as the other two: the program prints, the listing is
harvested, and tests/run_syn.py -- the identical comparison that judges the
x86 builds -- runs the Python oracle and decides.

Run:  python tools/mvssyn.py [--print]
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
import run_syn  # noqa: E402

JOB = "ONFSYN"

B32 = "third_party/SoftFloat-2c/softfloat/bits32/"
INCLUDES = {
    "milieu.h": "softfloat/c2c/milieu.h",
    "softfloat.h": "softfloat/c2c/softfloat.h",
    "softfloat-macros": B32 + "softfloat-macros",
    "softfloat-specialize": "softfloat/c2c/softfloat-specialize",
    "onfproc.h": "softfloat/c2c/onfproc.h",
}
UNIT = "softfloat/c2c/softfloat.c"

# Quoted includes.  ONFLY's own header names are unique in their first eight
# characters by C-04 discipline, so unlike SoftFloat's they need no
# amalgamation (VL-23).
HEADERS = [
    ("engine/include/onfplat.h", "ONFPLAT"),
    ("engine/include/onffp.h", "ONFFP"),
    ("engine/include/onfker.h", "ONFKER"),
    ("engine/include/onfrnd.h", "ONFRND"),
    ("engine/include/onfstm.h", "ONFSTM"),
    ("engine/include/onfdec.h", "ONFDEC"),
    ("engine/include/onfcrc.h", "ONFCRC"),
    ("engine/include/onffpr.h", "ONFFPR"),
    ("generated/onfcom.h", "ONFCOM"),
    ("generated/onfnhd.h", "ONFNHD"),
    ("generated/onfsynt.h", "ONFSYNT"),
    ("softfloat/c2c/milieu.h", "MILIEU"),
    ("softfloat/c2c/softfloat.h", "SOFTFLOA"),
    ("softfloat/c2c/onfproc.h", "ONFPROC"),
]

# The record shapes tstsyn.c prints, plus its banner, which is what names
# the backend and the platform.
#
# The banner needs its own alternative rather than sharing the others' \b:
# it opens "# tstsyn ...", and there is no word boundary between "#" and a
# space, so "#\b" never matches it.  The first run of this tool reported
# "[? backend, ?]" for exactly that reason -- which would have meant
# reporting an MVS result without the run itself saying it was MVS.
RESULT = re.compile(r"^\s*(?:#\s|DEC\b|BAD\b|HDR\b|SYN\b|SOUT\b|LOAD\b|RUN\b)")


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
        # third_party is not edited (D-28, D-35), and upstream 2c warns in
        # float64_rem about pointer signedness, which -pedantic-errors would
        # make fatal.  Same exception the x86 Makefile's C2CFLAGS makes.
        (library, "SF2C", mvsbld.CC_FLAGS_VENDOR),
        (backend, "ONFFP2C"),
        (onfly("engine/src/onffpc.c"), "ONFFPCC"),
        (onfly("engine/src/onfcrc.c"), "ONFCRCC"),
        (onfly("engine/src/onfrnd.c"), "ONFRNDC"),
        (onfly("engine/src/onfstm.c"), "ONFSTMC"),
        (onfly("engine/src/onfker.c"), "ONFKERC"),
        (onfly("engine/src/onfdec.c"), "ONFDECC"),
        (onfly("engine/src/onffpr.c"), "ONFFPRC"),
        (onfly("generated/onfcom.c"), "ONFCOMC"),
        (onfly("tests/tstsyn.c"), "TSTSYNC"),
    ]

    deck = mvsbld.build(JOB, "ONFLY ENGINE 2C", sources, headers=HEADERS)
    mvsub.check_cards(deck)
    if "--print" in argv:
        sys.stdout.write("\n".join(deck) + "\n")
        return 0

    sys.stdout.write("mvssyn: amalgamated %s -> %d cards, inlining %s\n"
                     % (UNIT, len(library), ", ".join(order)))
    sys.stdout.write("mvssyn: %d cards, %d translation units, longest %d "
                     "columns, GCCMVS %s\n"
                     % (len(deck), len(sources),
                        max(len(c) for c in deck), mvsbld.OPT))

    before = mvsub.submit(deck)
    out = mvsub.collect(JOB, before, timeout=3600, poll=5)
    if out is None:
        sys.stderr.write("mvssyn: %s did not finish in 3600 s\n" % JOB)
        return 1

    sys.stdout.write("=== step results ===\n")
    for line in mvsub.summarise(out):
        sys.stdout.write("  %s\n" % line[:116])

    sys.stdout.write("=== diagnostics ===\n")
    seen = {}
    for line in out.splitlines():
        s = line.strip()
        # A real Assembler XF message starts the line.  The D-111 prologue
        # quotes IFO196 inside a comment block and GCCMVS echoes the source
        # into the listing, so an unanchored search reports the explanation
        # as the failure.
        if (s.startswith("<stdin>") or "Internal compiler" in s
                or re.match(r"IFO\d{3}\b", s)):
            if s not in seen:
                seen[s] = 1
                sys.stdout.write("  %s\n" % s[:116])
    if not seen:
        sys.stdout.write("  none\n")

    lines = [l.rstrip().strip() for l in out.splitlines()
             if RESULT.match(l.rstrip())]
    sys.stdout.write("=== engine path on MVS 3.8j ===\n")
    sys.stdout.write("  %d result lines recovered from the job listing\n"
                     % len(lines))
    if not lines:
        sys.stderr.write("mvssyn: the program printed nothing; see above\n")
        return 1

    r = run_syn.compare("\n".join(lines))
    sys.stdout.write("  run_syn [%s backend, %s]: %d passed, %d failed\n"
                     % (r.backend, r.platform, r.passed, r.failed))
    for line in r.lines[:20]:
        sys.stdout.write("  %s\n" % line)
    return 1 if r.failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
