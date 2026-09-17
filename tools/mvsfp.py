# -*- coding: utf-8 -*-
"""Run tests/tstfp.c under GCCMVS on TK5 (D-421).

WHY THIS EXISTS, AND WHY IT DID NOT BEFORE
------------------------------------------
Until 2026-09-17 no ONFLY job had ever run the float SELF-TEST on MVS.
Gate G1 ran SoftFloat's own integer self-test and TestFloat there (VL-29,
VL-30), and tools/mvssfs.py ran the D-104 shift probe, but `tests/tstfp.c`
-- the file that checks ONFLY's own onf_fp layer against the host's
arithmetic -- ran on x86 only.

That gap had a consequence.  `onffzer()` returned a subnormal instead of
+0.0 under GCCMVS (VL-122), every "+0.0" in the MVS kernel was that
subnormal, and it passed every suite ONFLY had, three MVS runs in a row,
because nothing on that platform ever looked at the constant's bits.
D-420 removed the function; D-421 asks for the check to run where the
defect happened, which is what this does.

WHAT IT RUNS, AND WHAT IT CANNOT
--------------------------------
The SOFT2C build of the Makefile's `fp` target -- tstfp.c, onffpc.c,
onffp2.c, onfrnd.c and the 2c library -- and the output goes through
`tests/run_fp.py`'s own checker, so the MVS run is judged by exactly the
rule the x86 runs are judged by rather than by a second opinion written
here.

It does NOT run the SOFT3E or NATIVE builds: NR-03's fallback puts 2c on
MVS, and neither of the others is what the engine there is made of.

usage:
    python tools/mvsfp.py              build, run, and check
    python tools/mvsfp.py --print      emit the deck, submit nothing
    python tools/mvsfp.py --zero-only  report only the D-421 line
"""
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "tests"))

import mvsbld                                            # noqa: E402
import mvseng                                            # noqa: E402
import mvsrun                                            # noqa: E402
import mvsub                                             # noqa: E402

JOB = "ONFGTFP"


def sources(opt=None):
    """The Makefile's SOFT2C `fp` build, as MVS translation units.

    Taken apart from mvsrun._sources() rather than written afresh: the
    library units there are the ones the engine on MVS is built from, and
    a self-test built from a differently-compiled copy of the library
    would be testing a library the engine does not have.
    """
    if opt is None:
        opt = mvsbld.OPT
    eng = list(mvsrun._sources(opt))
    # ONFCRCC is here because the link needs it, not because the
    # self-test calls it: measured, the first attempt ended LKED at
    # COND CODE 0008 with IEW0132 ONFCRC unresolved.
    want = ("SF2C", "ONFFP2C", "ONFFPCC", "ONFFPRC", "ONFCRCC",
            "ONFRNDC", "ONFI32C")
    keep = [u for u in eng if u[1] in want]
    got = tuple(u[1] for u in keep)
    if got != want:
        raise RuntimeError("unit set changed: %s" % (got,))

    def onfly(relpath):
        return mvsbld.with_defines(relpath, ["ONF_FP_SOFT2C"])

    keep.append((onfly("tests/tstfp.c"), "TSTFP"))
    return keep


def deck(opt=None):
    return mvsbld.build(JOB, "ONFLY D421 TSTFP", sources(opt),
                        headers=mvsrun.HEADERS, region="8M")


def check(out, zero_only):
    """Judge the MVS output by tests/run_fp.py's own rule."""
    body = []
    for line in (out or "").splitlines():
        s = line.rstrip()
        # The printer carries the compile listing too, which echoes the
        # source -- including the printf format strings.  Only lines that
        # START with a tag are output; a listing line never does.
        if re.match(r"^(FPZERO|FPADD|FPSUB|FPMUL|FPABS|FPCMP|FPSELF|"
                    r"NONFIN|BACKEND) ", s):
            body.append(s)

    zero = [l for l in body if l.startswith("FPZERO ")]
    sys.stdout.write("mvsfp: %d self-test lines, %d FPZERO\n"
                     % (len(body), len(zero)))
    ok = False
    for l in zero:
        got = l.split("=", 1)[1].strip()
        ok = (got == "00000000:00000000")
        sys.stdout.write("mvsfp: D-421 zero constant is %s -- %s\n"
                         % (got, "+0.0, as NR-06 requires" if ok
                            else "NOT +0.0"))
    if not zero:
        sys.stdout.write("mvsfp: no FPZERO line -- the job did not reach "
                         "it; see the listing\n")
    if zero_only or not body:
        return 0 if ok else 1

    # The other 2,018 lines, judged by comparison with the x86 SOFT2C build
    # of the same self-test.  That is a stronger check than re-deriving the
    # expected answers here and a much smaller one: tests/run_fp.py already
    # judges the x86 output against Python's arithmetic, so if MVS agrees
    # with x86 line for line it has passed the same rule, transitively.
    #
    # It is also the only check available without refactoring run_fp.py's
    # checker to take lines instead of an executable, which is a change to
    # a file this work has no business touching.
    exe = os.path.join(ROOT, "build", "tstfp_2c.exe")
    if not os.path.exists(exe):
        sys.stdout.write("mvsfp: no %s -- build it with `make fp` to compare "
                         "the other %d lines\n" % (exe, len(body) - 1))
        return 0 if ok else 1
    import subprocess
    got = subprocess.check_output([exe]).decode("ascii", "replace")
    x86 = [l.rstrip() for l in got.splitlines()
           if re.match(r"^(FPZERO|FPADD|FPSUB|FPMUL|FPABS|FPCMP|FPSELF|"
                       r"NONFIN|BACKEND) ", l.rstrip())]
    same = (x86 == body)
    sys.stdout.write("mvsfp: %d lines on MVS, %d on x86-64 SOFT2C -- %s\n"
                     % (len(body), len(x86),
                        "IDENTICAL" if same else "they DIFFER"))
    if not same:
        for i in range(min(len(x86), len(body))):
            if x86[i] != body[i]:
                sys.stdout.write("   first difference at line %d\n"
                                 "   MVS %s\n   x86 %s\n"
                                 % (i + 1, body[i][:90], x86[i][:90]))
                break
    return 0 if (ok and same) else 1


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
    sys.stdout.write("mvsfp: %s, %d cards, SOFT2C under GCCMVS\n"
                     % (JOB, len(d)))
    out = mvsub.run(d, JOB, timeout=3600)
    for line in (out or "").splitlines():
        if "COND CODE" in line and "STEP WAS EXECUTED" in line:
            sys.stdout.write("  %s\n" % line.strip()[:90])
    rc = check(out, "--zero-only" in argv)
    with open(os.path.join(ROOT, "build", "mvs-tstfp.txt"), "w") as fh:
        fh.write(out or "")
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
