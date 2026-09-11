# -*- coding: utf-8 -*-
"""D-106: check SoftFloat 2c against TestFloat, operation by operation.

D-105 invokes NR-03 and vendors Release 2c because Gate G1 measured that
GCCMVS cannot build Release 3e (VL-19, VL-21).  D-106 front-loads the
question that decides whether the swap is cheap or expensive: does 2c
compute the same binary64 results as 3e?

Every ACC-5 fingerprint in the golden suite was produced with 3e.  If the
two libraries disagree on any of ONFLY's six operations, every fingerprint
changes, and that is a much larger decision than choosing a library.

The check is against TestFloat's reference rather than against 3e directly,
because two libraries agreeing with an independent oracle is a stronger
statement than two libraries agreeing with each other -- and because it is
the check NR-14 already demands.  tests/run_tt02.py runs 3e against these
same vectors, so agreement with 3e follows from both passing.

The per-operation runner is imported from run_tt02 rather than copied: the
vector generation, parsing and NaN accounting must be identical for the two
results to be comparable at all.

usage: run_c2c.py <tstc2c.exe> <testfloat_gen>
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import run_tt02  # noqa: E402


def main():
    if len(sys.argv) < 3:
        sys.stderr.write("usage: run_c2c.py <tstc2c.exe> <testfloat_gen>\n")
        return 2
    exe, gen = (os.path.abspath(a) for a in sys.argv[1:3])
    for path, what in ((exe, "tstc2c"), (gen, "testfloat_gen")):
        if not os.path.exists(path):
            sys.stderr.write("%s not found: %s\n" % (what, path))
            if what == "testfloat_gen":
                sys.stderr.write("Build it with:  make testfloat\n")
            return 2

    rows = []
    failed = 0
    total_checked = 0
    total_skipped = 0
    for short, full in run_tt02.OPS:
        fields, rc = run_tt02.run_op(gen, exe, short, full)
        if not fields:
            failed += 1
            rows.append("  FAIL %-4s produced no result" % short)
            continue
        checked = int(fields.get("checked", 0))
        skipped = int(fields.get("skipped_nan", 0))
        bad = int(fields.get("mismatch", -1))
        total_checked += checked
        total_skipped += skipped
        if bad == 0 and rc == 0:
            rows.append("  ok   %-4s checked=%-6d skipped_nan=%-5d"
                        % (short, checked, skipped))
        else:
            failed += 1
            rows.append("  FAIL %-4s checked=%-6d mismatch=%d"
                        % (short, checked, bad))

    n = len(run_tt02.OPS)
    print("run_c2c: SoftFloat 2c bits32 vs TestFloat -- %d of %d operations "
          "passed, %d cases checked, %d NaN cases skipped (VL-11)"
          % (n - failed, n, total_checked, total_skipped))
    for r in rows:
        print(r)
    if failed:
        print("run_c2c: 2c does NOT match the reference 3e was checked "
              "against; every ACC-5 fingerprint is in question (D-106)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
