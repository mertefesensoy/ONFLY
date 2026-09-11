# -*- coding: utf-8 -*-
"""Run TT-02's TestFloat vectors on MVS, and measure how large a table fits.

D-112 runs TT-02 on MVS with a shipped table because testfloat_gen has no
MVS build.  D-115 settles the table size by measurement rather than by
picking a number: every size on offer rested on a single timing data point
and a guess about whether a large static table fits an 8M region, and this
session has twice had an estimate overturned by a measurement.

`--ramp` submits increasing sizes until MVS refuses, and reports the
largest that passed together with what the failure looked like.  That
figure is worth more than the table it sizes: it is what any future MVS
table, and Gate G3's performance work, will be sized against.

The unit under test is SoftFloat 2c, the MVS backend under NR-03 and
D-105, presented exactly as tools/mvs2c.py presents it -- the D-110
amalgamation and the D-111 rename prologue -- because a result from a
differently built library would not be a result about the engine's.

Run:  python tools/mvstf2.py [--per-op N]
      python tools/mvstf2.py --ramp
"""
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import mvsbld  # noqa: E402
import mvs2c  # noqa: E402
import mvsub  # noqa: E402

JOB = "ONFTF2"
RAMP = [500, 2000, 6000, 12000, 24000]


def regenerate(per_op):
    cmd = [sys.executable,
           os.path.join(mvsbld.ROOT, "tools", "gentf2.py"),
           "--per-op", str(per_op)]
    out = subprocess.check_output(cmd, stderr=subprocess.STDOUT)
    text = out.decode("ascii", "replace")
    m = re.search(r"(\d+) vectors, ", text)
    return int(m.group(1)) if m else -1


def run(per_op, verbose=True, region=mvsbld.REGION):
    """Build and submit one size.  Returns (nvec, cards, verdict, detail)."""
    nvec = regenerate(per_op)
    body = (mvsbld.cards_of("generated/onf2cnm.h")
            + mvsbld.amalgamate(mvs2c.UNIT, mvs2c.INCLUDES))
    deck = mvsbld.build(
        JOB, "ONFLY TT-02 ON MVS",
        [(body, "SF2C", mvsbld.CC_FLAGS_VENDOR),
         ("tests/tsttf2.c", "TSTTF2")],
        region=region,
        headers=[("softfloat/c2c/milieu.h", "MILIEU"),
                 ("softfloat/c2c/softfloat.h", "SOFTFLOA"),
                 ("softfloat/c2c/onfproc.h", "ONFPROC"),
                 ("generated/onf2cnm.h", "ONF2CNM"),
                 ("generated/onftfv.h", "ONFTFV")])
    mvsub.check_cards(deck)
    cards = len(deck)
    if verbose:
        sys.stdout.write("mvstf2: %d vectors, %d cards, REGION=%s ... "
                         % (nvec, cards, region))
        sys.stdout.flush()

    before = mvsub.submit(deck)
    out = mvsub.collect(JOB, before, timeout=2400, poll=6)
    if out is None:
        return nvec, cards, "TIMEOUT", "did not finish in 2400 s"

    wrong = None
    for line in out.splitlines():
        m = re.search(r"# tsttf2 (\d+) of (\d+) vectors wrong", line)
        if m:
            wrong = int(m.group(1))
    if wrong == 0:
        return nvec, cards, "PASS", ""
    if wrong is not None:
        return nvec, cards, "WRONG", "%d vectors wrong" % wrong

    detail = "no result line"
    for line in out.splitlines():
        s = line.strip()
        if "Internal compiler" in s or "IFO1" in s or "IEW0" in s:
            detail = s[:80]
            break
        m = re.search(r"(ONFTF2 \w+ - STEP WAS EXECUTED - COND CODE \d+)", s)
        if m and "0000" not in m.group(1):
            detail = m.group(1)
        if "ABEND" in s or "NOT RUN" in s or "SPACE" in s.upper()[:40]:
            detail = s[:80]
            break
    return nvec, cards, "FAIL", detail


def main(argv):
    if "--ramp" in argv:
        rows = []
        best = None
        for per_op in RAMP:
            nvec, cards, verdict, detail = run(per_op)
            sys.stdout.write("%s %s\n" % (verdict, detail))
            rows.append((nvec, cards, verdict, detail))
            if verdict == "PASS":
                best = (nvec, cards)
            else:
                break
        sys.stdout.write("=== D-115: largest TT-02 table MVS accepts ===\n")
        for nvec, cards, verdict, detail in rows:
            sys.stdout.write("  %6d vectors  %6d cards  %-7s %s\n"
                             % (nvec, cards, verdict, detail))
        if best:
            sys.stdout.write("  largest passing: %d vectors, %d cards\n"
                             % best)
        else:
            sys.stdout.write("  nothing passed\n")
        return 0

    per_op = 2000
    for i, a in enumerate(argv):
        if a == "--per-op" and i + 1 < len(argv):
            per_op = int(argv[i + 1])
    nvec, cards, verdict, detail = run(per_op)
    sys.stdout.write("%s %s\n" % (verdict, detail))
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
