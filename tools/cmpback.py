# -*- coding: utf-8 -*-
"""Compare float-backend builds byte for byte (NR-09 evidence).

NR-09 admits a native backend on a host only if, among other conditions, it
produces byte-identical results to the soft backend on that host.  This script
runs every executable given and requires their output to match exactly.

Two or more may be given.  Since D-121 there are three backends -- SOFT3E,
SOFT2C and NATIVE (D-124) -- and comparing them pairwise in three separate
runs would report a disagreement three times without saying which backend is
the odd one out.  Each build is compared against the first, and the report
names the backend each executable declares in its own banner rather than the
file it was built into.

It proves the bit-identity condition on the operand set tstfp.c exercises, and
nothing more.  Full NR-09 admission additionally needs the TestFloat vectors
(TT-02) and byte-identical golden-suite fingerprints.

Run:  python tools/cmpback.py <exe> <exe> [<exe> ...]
"""
import os
import re
import subprocess
import sys


def label_of(banner, path):
    """The backend a build declares, or its file name if it declares none."""
    for line in banner:
        m = re.search(r"backend=(\S+)", line)
        if m:
            return m.group(1)
    return os.path.basename(path)


def run(path):
    path = os.path.abspath(path)
    proc = subprocess.Popen([path], stdout=subprocess.PIPE)
    out, _ = proc.communicate()
    if proc.returncode != 0:
        sys.stderr.write("%s exited %d\n" % (path, proc.returncode))
        sys.exit(2)
    lines = out.decode("ascii", "replace").splitlines()
    # The banner names the backend, so it differs by design and is not
    # compared; it is what labels the build in the report instead.
    banner = [l for l in lines if l.startswith("#")]
    return label_of(banner, path), [l for l in lines if not l.startswith("#")]


def main():
    if len(sys.argv) < 3:
        sys.stderr.write("usage: cmpback.py <exe> <exe> [<exe> ...]\n")
        return 2
    runs = [run(p) for p in sys.argv[1:]]
    ref_name, ref = runs[0]
    bad = 0
    for name, got in runs[1:]:
        if len(got) != len(ref):
            print("cmpback: FAIL %s - %d lines vs %s's %d"
                  % (name, len(got), ref_name, len(ref)))
            bad += 1
            continue
        diffs = [i for i, (x, y) in enumerate(zip(ref, got)) if x != y]
        if not diffs:
            continue
        bad += 1
        print("cmpback: FAIL %s differs from %s on %d of %d lines"
              % (name, ref_name, len(diffs), len(ref)))
        for i in diffs[:5]:
            print("  line %d\n    %-8s %s\n    %-8s %s"
                  % (i + 1, ref_name + ":", ref[i], name + ":", got[i]))
    if bad:
        return 1
    print("cmpback: %s agree bit-for-bit on %d result lines"
          % (", ".join(n for n, _ in runs), len(ref)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
