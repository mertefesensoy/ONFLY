# -*- coding: utf-8 -*-
"""Run tests/tstsfs.c under GCCMVS: does SoftFloat's shift survive? (D-104)

VL-19 measured GCCMVS's variable-count 64-bit left shift and found it
always writes zero into bit 63.  VL-20 then read ONFLY's SoftFloat 3e
build and found variable-count shifts in the normalisation, rounding and
sticky-bit paths.  VL-20 is analysis; this job is the measurement, and it
compiles the actual vendored SoftFloat sources rather than a model of
them.

This is also the first use of the NR-04 shims.  PDPCLIB supplies neither
<stdint.h> nor <stdbool.h> -- measured, not assumed -- and GCCMVS does not
fall back to the INCLUDE DD for an angle-bracket include, so the shims go
into a VB/255 library concatenated after PDPCLIB.INCLUDE on SYSINCL.  See
tools/mvsbld.py for why that library cannot simply be the FB/80 one.

Every result must be 1.  A zero is the defect and nothing else; the same
binary on x86 prints 126 ones.  Run the x86 side with:

    gcc -std=c89 -pedantic -Wall -Wextra -Werror -O2 -Wno-long-long \\
        -Isoftfloat -Ithird_party/SoftFloat-3e/source/include \\
        -o build/tstsfs.exe tests/tstsfs.c \\
        third_party/SoftFloat-3e/source/s_shiftRightJam64.c \\
        third_party/SoftFloat-3e/source/s_shortShiftRightJam64.c

Run:  python tools/mvssfs.py [--print]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import mvsbld  # noqa: E402
import mvsub  # noqa: E402

JOB = "ONFSFS"
SF = "third_party/SoftFloat-3e/source/"

# repository file -> PDS member.  Stated, never derived (mvsbld.build).
HEADERS = [
    ("softfloat/platform.h", "PLATFORM"),
]
VB_HEADERS = [
    ("softfloat/c89/stdint.h", "STDINT"),
    ("softfloat/c89/stdbool.h", "STDBOOL"),
]
SOURCES = [
    ("tests/tstsfs.c", "TSTSFS"),
    (SF + "s_shiftRightJam64.c", "SSRJ64"),
    (SF + "s_shortShiftRightJam64.c", "SSSRJ64"),
]


def main(argv):
    deck = mvsbld.build(JOB, "ONFLY SOFTFLOAT SHIFT", SOURCES,
                        headers=HEADERS, vb_headers=VB_HEADERS)
    mvsub.check_cards(deck)
    if "--print" in argv:
        sys.stdout.write("\n".join(deck) + "\n")
        return 0

    sys.stdout.write("mvssfs: %d cards, longest %d columns, GCCMVS %s\n"
                     % (len(deck), max(len(c) for c in deck), mvsbld.OPT))
    before = mvsub.submit(deck)
    out = mvsub.collect(JOB, before, timeout=900, poll=5)
    if out is None:
        sys.stderr.write("mvssfs: %s did not finish in 900 s\n" % JOB)
        return 1

    sys.stdout.write("=== step results ===\n")
    for line in mvsub.summarise(out):
        sys.stdout.write("  %s\n" % line[:116])

    jam_bad, shrt_bad, seen = [], [], 0
    diag = []
    for line in out.splitlines():
        s = line.strip()
        if s.startswith("<stdin>") or "Internal compiler" in s:
            diag.append(s[:110])
            continue
        if not s.startswith("SFS "):
            continue
        parts = s.split()
        if len(parts) < 5:
            continue
        kind, dist, rfield = parts[1], parts[2], parts[4]
        seen += 1
        if rfield != "r=0000000000000001":
            (jam_bad if kind == "JAM" else shrt_bad).append((dist, rfield))

    sys.stdout.write("=== compiler diagnostics ===\n")
    for s in diag[:12]:
        sys.stdout.write("  %s\n" % s)
    if not diag:
        sys.stdout.write("  (none)\n")

    sys.stdout.write("=== tstsfs on MVS ===\n")
    sys.stdout.write("  %d result lines read; x86 prints 126, all r=1\n"
                     % seen)
    sys.stdout.write("  shiftRightJam64      : %d wrong\n" % len(jam_bad))
    for dist, rfield in jam_bad[:8]:
        sys.stdout.write("      dist=%s %s (should be r=...01)\n"
                         % (dist, rfield))
    if len(jam_bad) > 8:
        sys.stdout.write("      ... and %d more\n" % (len(jam_bad) - 8))
    sys.stdout.write("  shortShiftRightJam64 : %d wrong\n" % len(shrt_bad))
    for dist, rfield in shrt_bad[:8]:
        sys.stdout.write("      dist=%s %s\n" % (dist, rfield))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
