# -*- coding: utf-8 -*-
"""Compare two golden-suite builds on one shared network file (ACC-5).

cmpback.py runs a binary with no arguments; tstgld needs a network file, so
this writes one, runs both builds against it, and requires their GOLD and GOUT
lines to be identical.  That is rows 2 and 3 of the Section 8.3 determinism
matrix -- x86 native and x86 soft -- agreeing on every golden fingerprint.

Rows 4 to 8 need Linux s390x, MVS 3.8j and z/OS and are not run here.

Run:  python tools/cmpgld.py <soft exe> <native exe>
"""
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import run_gld  # noqa: E402


def run(exe, path):
    proc = subprocess.Popen([os.path.abspath(exe), path], stdout=subprocess.PIPE)
    out, _ = proc.communicate()
    if proc.returncode != 0:
        sys.stderr.write("%s exited %d\n" % (exe, proc.returncode))
        sys.exit(2)
    # Drop the banner: it names the backend, so it differs by design.
    return [l for l in out.decode("ascii", "replace").splitlines()
            if not l.startswith("#")]


def main():
    if len(sys.argv) < 3:
        sys.stderr.write("usage: cmpgld.py <soft exe> <native exe>\n")
        return 2
    blob, _net, _crc = run_gld.make_network()
    tmp = tempfile.mkdtemp(prefix="onfly_cmpgld_")
    path = os.path.join(tmp, "golden.net")
    with open(path, "wb") as fh:
        fh.write(blob)

    a, b = run(sys.argv[1], path), run(sys.argv[2], path)
    if a != b:
        print("cmpgld: FAIL - the two backends disagree")
        for i, (x, y) in enumerate(zip(a, b)):
            if x != y:
                print("  line %d\n    soft:   %s\n    native: %s" % (i + 1, x, y))
                break
        return 1
    golds = len([l for l in a if l.startswith("GOLD")])
    print("cmpgld: soft and native agree on all %d golden requests "
          "(%d output lines)" % (golds, len(a)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
