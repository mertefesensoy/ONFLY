# -*- coding: utf-8 -*-
"""Compare golden-suite builds on one shared network file (ACC-5).

cmpback.py runs a binary with no arguments; tstgld needs a network file, so
this runs every build given against the same one and requires their GOLD and
GOUT lines to be identical.

Two or more may be given.  With three backends since D-121 -- SOFT3E, SOFT2C
and NATIVE (D-124) -- each is compared against the first and the report names
the backend each build declares, so a disagreement says which one is the odd
one out instead of merely that a pair differed.

That covers rows 2 and 3 of the Section 8.3 determinism matrix -- x86 NATIVE
and x86 SOFT3E -- plus x86 SOFT2C, which is not a row of that matrix: D-124
renamed the matrix's backend values without adding rows, and P-08 proposes
adding one.  Rows 4 to 8 need Linux s390x, MVS 3.8j and z/OS and are not run
here.

Run:  python tools/cmpgld.py <exe> <exe> [<exe> ...]
"""
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import run_gld  # noqa: E402


def run(exe, path):
    proc = subprocess.Popen([os.path.abspath(exe), path], stdout=subprocess.PIPE)
    out, _ = proc.communicate()
    if proc.returncode != 0:
        sys.stderr.write("%s exited %d\n" % (exe, proc.returncode))
        sys.exit(2)
    lines = out.decode("ascii", "replace").splitlines()
    # The banner names the backend, so it differs by design and is not
    # compared; it is what labels the build in the report instead.
    label = os.path.basename(exe)
    for line in lines:
        if line.startswith("#"):
            m = re.search(r"backend=(\S+)", line)
            if m:
                label = m.group(1)
                break
    return label, [l for l in lines if not l.startswith("#")]


def main():
    if len(sys.argv) < 3:
        sys.stderr.write("usage: cmpgld.py <exe> <exe> [<exe> ...]\n")
        return 2
    # Both backends run against the same emitted artifact (D-75), not a network
    # rebuilt here: comparing two builds against two separately generated files
    # would leave a difference in the file as a possible explanation for a
    # difference in the output.
    path = run_gld.NETWORK
    if not os.path.exists(path):
        sys.stderr.write("network not found: %s\n" % path)
        sys.stderr.write("Emit it first:  python prep/emit.py path\n")
        return 2

    runs = [run(exe, path) for exe in sys.argv[1:]]
    ref_name, ref = runs[0]
    bad = 0
    for name, got in runs[1:]:
        if got == ref:
            continue
        bad += 1
        print("cmpgld: FAIL - %s disagrees with %s" % (name, ref_name))
        if len(got) != len(ref):
            print("  %d output lines vs %d" % (len(got), len(ref)))
        for i, (x, y) in enumerate(zip(ref, got)):
            if x != y:
                print("  line %d\n    %-8s %s\n    %-8s %s"
                      % (i + 1, ref_name + ":", x, name + ":", y))
                break
    if bad:
        return 1
    golds = len([l for l in ref if l.startswith("GOLD")])
    print("cmpgld: %s agree on all %d golden requests (%d output lines)"
          % (", ".join(n for n, _ in runs), golds, len(ref)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
