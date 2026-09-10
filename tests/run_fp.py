# -*- coding: utf-8 -*-
"""TU-02: check the ONFLY float API against plain Python floats.

Python floats are IEEE 754 binary64 with round-to-nearest-ties-to-even, which
is exactly what NR-01 specifies, so they are the oracle (O-1).  This script
reads the operands the C program used, recomputes every result here, and
compares bit patterns -- not decimal renderings, which would hide a
one-ulp difference.

Run:  python tests/run_fp.py <path-to-tstfp-executable>

Exit status 0 only if every comparison matches.
"""
import os
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def bits_to_float(hi, lo):
    return struct.unpack(">d", struct.pack(">II", hi, lo))[0]


def float_to_bits(x):
    hi, lo = struct.unpack(">II", struct.pack(">d", x))
    return hi, lo


def parse_pair(text):
    hi, lo = text.split(":")
    return int(hi, 16), int(lo, 16)


def fmt(bits):
    return "%08X:%08X" % bits


class Result(object):
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.msgs = []

    def check(self, label, got, want, extra=""):
        if got == want:
            self.passed += 1
        else:
            self.failed += 1
            if len(self.msgs) < 12:
                self.msgs.append("  FAIL %-22s C=%s oracle=%s %s"
                                 % (label, got, want, extra))


def main():
    if len(sys.argv) < 2:
        sys.stderr.write("usage: run_fp.py <tstfp executable>\n")
        return 2
    # Absolute: CreateProcess on Windows fails on a relative path when the
    # working directory contains non-ASCII characters, as this project's does.
    exe = os.path.abspath(sys.argv[1])
    if not os.path.exists(exe):
        sys.stderr.write("not found: %s\n" % exe)
        return 2

    proc = subprocess.Popen([exe], stdout=subprocess.PIPE)
    out, _ = proc.communicate()
    if proc.returncode != 0:
        sys.stderr.write("tstfp exited %d\n" % proc.returncode)
        return 2
    text = out.decode("ascii", "replace")

    backend = "?"
    r = Result()

    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("#"):
            for tok in line.split():
                if tok.startswith("backend="):
                    backend = tok.split("=", 1)[1]
            continue

        parts = line.split()
        kind = parts[0]
        f = {}
        for p in parts[1:]:
            k, v = p.split("=", 1)
            f[k] = v

        if kind == "NONFIN":
            hi, lo = parse_pair(f["v"])
            x = bits_to_float(hi, lo)
            # "Non-finite" is NaN or infinity; Python says so directly.
            want = 1 if (x != x or x in (float("inf"), float("-inf"))) else 0
            r.check("nonfin %s" % f["name"], int(f["nf"]), want)
            continue

        a = bits_to_float(*parse_pair(f["a"]))
        b = bits_to_float(*parse_pair(f["b"]))

        if kind == "FPCMP":
            r.check("lt[%s]" % f["i"], int(f["lt"]), 1 if a < b else 0)
            r.check("le[%s]" % f["i"], int(f["le"]), 1 if a <= b else 0)
            continue

        got = parse_pair(f["z"])
        if kind == "FPADD":
            want = float_to_bits(a + b)
        elif kind == "FPSUB":
            want = float_to_bits(a - b)
        elif kind == "FPMUL":
            want = float_to_bits(a * b)
        elif kind == "FPABS":
            want = float_to_bits(abs(a))
        elif kind == "FPSELF":
            # x - x must be exactly +0.0.  Comparing bit patterns matters here:
            # -0.0 == +0.0 is true in Python, so a value check would pass even
            # if the sign were wrong.  The derived softfloat/onfsub.c is what
            # this exercises.
            want = float_to_bits(a - b)
            r.check("selfsub sign[%s]" % f["i"], fmt(got), "00000000:00000000",
                    "(x - x must be +0.0, not -0.0)")
        else:
            continue

        r.check("%s[%s]" % (kind.lower(), f["i"]), fmt(got), fmt(want),
                "a=%s b=%s" % (f["a"], f["b"]))

    print("run_fp [%s backend]: %d passed, %d failed" % (backend, r.passed, r.failed))
    for m in r.msgs:
        print(m)
    return 1 if r.failed else 0


if __name__ == "__main__":
    sys.exit(main())
