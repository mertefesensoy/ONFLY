# -*- coding: utf-8 -*-
"""Compare two float-backend builds byte for byte (NR-09 evidence).

NR-09 admits a native backend on a host only if, among other conditions, it
produces byte-identical results to the soft backend on that host.  This script
runs both executables and requires their output to match exactly.

It proves the bit-identity condition on the operand set tstfp.c exercises, and
nothing more.  Full NR-09 admission additionally needs the TestFloat vectors
(TT-02) and byte-identical golden-suite fingerprints, neither of which exists
until the kernel and the network format are built.

Run:  python tools/cmpback.py <soft exe> <native exe>
"""
import os
import subprocess
import sys


def run(path):
    path = os.path.abspath(path)
    proc = subprocess.Popen([path], stdout=subprocess.PIPE)
    out, _ = proc.communicate()
    if proc.returncode != 0:
        sys.stderr.write("%s exited %d\n" % (path, proc.returncode))
        sys.exit(2)
    # Drop the banner: it names the backend, so it differs by design.
    return [l for l in out.decode("ascii", "replace").splitlines()
            if not l.startswith("#")]


def main():
    if len(sys.argv) < 3:
        sys.stderr.write("usage: cmpback.py <soft exe> <native exe>\n")
        return 2
    a = run(sys.argv[1])
    b = run(sys.argv[2])
    if len(a) != len(b):
        print("cmpback: FAIL - %d lines vs %d lines" % (len(a), len(b)))
        return 1
    bad = 0
    for i, (x, y) in enumerate(zip(a, b)):
        if x != y:
            bad += 1
            if bad <= 5:
                print("cmpback: FAIL line %d\n  soft:   %s\n  native: %s" % (i + 1, x, y))
    if bad:
        print("cmpback: %d of %d lines differ" % (bad, len(a)))
        return 1
    print("cmpback: soft and native agree bit-for-bit on %d result lines" % len(a))
    return 0


if __name__ == "__main__":
    sys.exit(main())
