# -*- coding: utf-8 -*-
"""The TX-01/TX-02 comparator must DETECT a difference, not just report none.

tests/run_tx.py --compare carries Phase D's headline claim: that the response
records and golden fingerprints produced on Linux s390x are byte-identical to
those produced on x86-64.  A comparator that always printed "identical" would
pass that comparison, and every future one, while proving nothing.

So this checks the failing direction explicitly, on the two artifact kinds
that matter:

  a response record   one bit flipped inside the ONF-FPRINT field, which is
                      the IR-COM-05 fingerprint itself -- the smallest change
                      that must never go unnoticed
  a recorded gold line  one return code altered, which is what a divergent
                      request validation would look like

Both must be reported, with their location, and the exit status must be
non-zero.  Comparing a recording against itself must still be clean, so that
the test cannot pass by the comparator simply failing everything.

Skipped, with a message, when no recording exists yet: the artifacts are
produced by `run_tx.py --record`, which needs built binaries and the network
fixtures, and a bare checkout has neither (the D-156 and D-233 pattern).

Run:  python tests/test_txcmp.py
Exit status 0 when the comparator behaves as specified, 1 otherwise.
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REC = os.path.join(ROOT, "data", "phase-d", "x86w")
TOOL = os.path.join(HERE, "run_tx.py")
sys.path.insert(0, os.path.join(ROOT, "tools"))

import onfres                                          # noqa: E402

#: Offset of ONF-FPRINT within a 412-byte record (generated/onfcom.h).
FPRINT_OFF = 20


def compare(a, b):
    proc = subprocess.Popen([sys.executable, TOOL, "--compare", a, b],
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    out, _ = proc.communicate()
    return proc.returncode, out.decode("ascii", "replace")


def main():
    if not os.path.isdir(REC):
        onfres.skip("req/txcmp-recording", "no recording at "
                    "data/phase-d/x86w; run `python tests/run_tx.py "
                    "--record` first")
        return 0
    needed = ("rsp-srext-nat.bin", "gold-path-soft.txt")
    for name in needed:
        if not os.path.exists(os.path.join(REC, name)):
            onfres.skip("req/txcmp-recording",
                        "%s missing from the recording" % name)
            return 0

    tmp = tempfile.mkdtemp(prefix="onfly-txcmp-")
    ok = bad = 0
    try:
        a = os.path.join(tmp, "A")
        b = os.path.join(tmp, "B")
        shutil.copytree(REC, a)
        shutil.copytree(REC, b)

        rc, out = compare(a, a)
        if rc == 0 and "0 differing" in out:
            ok += 1
            print("  ok   a recording compares clean against itself")
        else:
            bad += 1
            print("  FAIL self-comparison reported a difference (rc=%d)" % rc)

        p = os.path.join(b, "rsp-srext-nat.bin")
        with open(p, "rb") as f:
            raw = bytearray(f.read())
        raw[FPRINT_OFF] ^= 0x01
        with open(p, "wb") as f:
            f.write(bytes(raw))

        q = os.path.join(b, "gold-path-soft.txt")
        with open(q, "rb") as f:
            text = f.read()
        with open(q, "wb") as f:
            f.write(text.replace(b"rc=0", b"rc=4", 1))

        rc, out = compare(a, b)
        for what, token in (
                ("a one-bit change in ONF-FPRINT is reported",
                 "FAIL rsp-srext-nat.bin"),
                ("its location is given to the byte",
                 "offset %d" % FPRINT_OFF),
                ("a changed return code in a gold line is reported",
                 "FAIL gold-path-soft.txt")):
            if token in out:
                ok += 1
                print("  ok   %s" % what)
            else:
                bad += 1
                print("  FAIL %s (not in output)" % what)
        if rc != 0:
            ok += 1
            print("  ok   the comparator exits non-zero on a difference")
        else:
            bad += 1
            print("  FAIL the comparator exited 0 despite a difference")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("test_txcmp: %d passed, %d failed" % (ok, bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
