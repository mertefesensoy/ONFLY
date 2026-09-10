# -*- coding: utf-8 -*-
"""TT-02: Berkeley TestFloat vectors through the onf_fp API (NR-14, NR-09).

Runs TestFloat's generated vectors for every operation SRS Appendix C uses --
addition, subtraction, multiplication and the ordered comparisons -- through
both float backends and requires zero mismatches.

For the SOFT backend this is a correctness check on the vendored library as
ONFLY builds it, including the two ONFLY-owned derived files (D-35).

For the NATIVE backend it is one of NR-09's admission conditions: "passing the
TestFloat vectors for the used operations". The other conditions -- SSE2 rather
than x87, no FMA contraction, no fast-math, no flush-to-zero, and byte-identical
golden fingerprints against the soft backend -- are enforced by the Makefile's
NATFLAGS and checked by tools/cmpgld.py.

Exclusions, both declared rather than silent:
  NaN cases are skipped (VL-11, D-46). TestFloat's reference is built against
  the 8086 specialization because ARM-VFPv2-defaultNaN cannot build a complete
  library. They share their arithmetic cores verbatim and differ only in NaN
  handling, and ONFLY aborts on any NaN anyway (FR-SIM-08).
  Exception flags are ignored: NR-10 forbids depending on them and D-34 removed
  the storage they would accumulate into.

Run:  python tests/run_tt02.py <soft exe> <native exe> <testfloat_gen exe>
"""
import os
import subprocess
import sys

OPS = [("add", "f64_add"), ("sub", "f64_sub"), ("mul", "f64_mul"),
       ("lt", "f64_lt"), ("le", "f64_le"), ("eq", "f64_eq")]


def run_op(gen, exe, short, full):
    """Generate vectors for one operation and pipe them through one backend."""
    p1 = subprocess.Popen([gen, "-rnear_even", "-level", "1", full],
                          stdout=subprocess.PIPE,
                          stderr=open(os.devnull, "wb"))
    p2 = subprocess.Popen([exe, short], stdin=p1.stdout,
                          stdout=subprocess.PIPE)
    p1.stdout.close()
    out, _ = p2.communicate()
    p1.wait()
    fields = {}
    for line in out.decode("ascii", "replace").splitlines():
        if line.startswith("TT02"):
            for tok in line.split()[1:]:
                if "=" in tok:
                    k, v = tok.split("=", 1)
                    fields[k] = v
    return fields, p2.returncode


def main():
    if len(sys.argv) < 4:
        sys.stderr.write(
            "usage: run_tt02.py <soft exe> <native exe> <testfloat_gen exe>\n")
        return 2
    soft, native, gen = (os.path.abspath(a) for a in sys.argv[1:4])
    for path, what in ((soft, "soft"), (native, "native"), (gen, "testfloat_gen")):
        if not os.path.exists(path):
            sys.stderr.write("%s not found: %s\n" % (what, path))
            if what == "testfloat_gen":
                sys.stderr.write(
                    "Build it with:  mingw32-make testfloat\n")
            return 2

    failed = 0
    total_checked = total_skipped = 0
    rows = []
    for exe, label in ((soft, "SOFT"), (native, "NATIVE")):
        for short, full in OPS:
            f, rc = run_op(gen, exe, short, full)
            if not f:
                failed += 1
                rows.append("  FAIL %-6s %-4s produced no result" % (label, short))
                continue
            checked = int(f.get("checked", 0))
            skipped = int(f.get("skipped_nan", 0))
            bad = int(f.get("mismatch", -1))
            total_checked += checked
            total_skipped += skipped
            if bad == 0 and rc == 0:
                rows.append("  ok   %-6s %-4s checked=%-6d skipped_nan=%-5d"
                            % (label, short, checked, skipped))
            else:
                failed += 1
                rows.append("  FAIL %-6s %-4s checked=%-6d mismatch=%d"
                            % (label, short, checked, bad))

    print("run_tt02: %d of %d operation runs passed, %d cases checked, "
          "%d NaN cases skipped (VL-11)"
          % (len(OPS) * 2 - failed, len(OPS) * 2, total_checked, total_skipped))
    for r in rows:
        print(r)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
