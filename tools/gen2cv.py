# -*- coding: utf-8 -*-
"""Generate known-answer binary64 vectors for SoftFloat 2c (D-108).

The question D-108 puts first is whether SoftFloat 2c, which NR-03 and
D-105 chose precisely because it uses no 64-bit integers, actually builds
and computes correctly under GCCMVS.  Building is not enough: GCCMVS has
already been measured producing a silently wrong answer once (VL-19), so
the unit has to be run against values whose answers are known.

WHERE THE EXPECTED ANSWERS COME FROM
------------------------------------
Python floats.  Section 8.2 makes plain Python floating point the oracle
for this project, and for these six operations that is exactly right:
CPython's float is IEEE 754 binary64 and its `+`, `-`, `*` and ordered
comparisons are the correctly rounded operations SoftFloat implements.
So the expected values are produced by an implementation that shares no
code with SoftFloat, which is what makes this a check rather than an echo.

NR-06: no target converts between decimal text and binary floating point.
Every value below is emitted as a pair of 32-bit patterns, which is also
the shape 2c's float64 has, so nothing in the generated header or the test
needs a 64-bit integer type (NR-04).

NaN is excluded throughout (FR-SIM-08, VL-11).  Infinities are kept: they
are represented identically everywhere and are real cases.

Output: generated/onf2cv.h.  Never edit it by hand (IR-COM-01).

Run:  python tools/gen2cv.py [--check]
"""
import io
import os
import struct
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "generated", "onf2cv.h")

OPS = ["ADD", "SUB", "MUL", "LT", "LE", "EQ"]

INF = float("inf")

# Operands chosen to reach the places where a 32-bit-limbed implementation
# can go wrong: carry and borrow across the halfword boundary, rounding
# ties, cancellation to zero, subnormals at both ends of the range, and the
# exponent extremes.  Plain decimal-looking values are included too, since
# most real kernel arithmetic is unremarkable and a test made only of
# corner cases would miss an ordinary mistake.
VALUES = [
    0.0, -0.0, 1.0, -1.0, 2.0, 0.5, -0.5,
    3.0, 10.0, 0.1, -0.1, 1e-3, 1e3,
    1.5, 2.5, 1.0000000000000002,      # ties and the ulp above one
    4503599627370496.0,                # 2**52, where the ulp becomes 1
    9007199254740993.0,                # 2**53 + 1, not representable
    1.7976931348623157e308,            # max finite
    2.2250738585072014e-308,           # min normal
    5e-324,                            # min subnormal
    1.1125369292536007e-308,           # a subnormal boundary
    -52.0, -45.0, 0.275, 20.0,         # ONFLY's own kernel constants
    0.9950124791926823,                # P11 from Appendix C
    0.004937935295309022,              # P12
    0.9801986733067553,                # P22
    INF, -INF,
]


def bits(x):
    hi, lo = struct.unpack(">II", struct.pack(">d", x))
    return hi, lo


def pairs():
    """Operand pairs: every value against a spread of others."""
    out = []
    n = len(VALUES)
    for i, a in enumerate(VALUES):
        for j in (0, 1, 2, 5, 7, 11, 13, 17, 19, 23):
            b = VALUES[(i + j) % n]
            out.append((a, b))
    return out


def apply_op(op, a, b):
    """Returns (kind, value) where kind is 'f' for a float or 'c' for 0/1."""
    if op == "ADD":
        return "f", a + b
    if op == "SUB":
        return "f", a - b
    if op == "MUL":
        return "f", a * b
    if op == "LT":
        return "c", 1 if a < b else 0
    if op == "LE":
        return "c", 1 if a <= b else 0
    return "c", 1 if a == b else 0


def build():
    """Vectors, with every NaN case dropped and counted.

    NaN has to go, and not only because VL-11 says so.  The two oracles
    genuinely disagree about it: Python hands back a NaN carrying the sign
    of the operands, so `-inf * -0.0` is 0xFFF8000000000000, while the
    ARM-VFPv2 default-NaN convention D-31 and D-107 chose returns the one
    default pattern 0x7FF8000000000000 regardless.  Neither is wrong; they
    are different conventions, and a vector built from one and checked
    against the other would report a difference that is by design.

    ONFLY never observes this: FR-SIM-08 aborts on NaN before it can
    propagate.  The operands here contain no NaN either, so the only way
    one appears is as a RESULT -- inf minus inf, inf times zero -- which
    is exactly what the first version of this generator missed and what
    the six failures on x86 pointed at.
    """
    rows = []
    dropped = 0
    for op in OPS:
        for a, b in pairs():
            kind, r = apply_op(op, a, b)
            if kind == "f":
                if r != r:                      # NaN: the only value
                    dropped += 1                # that is not equal to
                    continue                    # itself
                rhi, rlo = bits(r)
            else:
                rhi, rlo = 0, r
            ahi, alo = bits(a)
            bhi, blo = bits(b)
            rows.append((op, ahi, alo, bhi, blo, rhi, rlo))
    return rows, dropped


BANNER = """\
/*
 * onf2cv.h - known-answer binary64 vectors for SoftFloat 2c (D-108).
 *
 * GENERATED by tools/gen2cv.py.  Do not edit by hand (IR-COM-01).
 *
 * Expected results come from Python floats, which Section 8.2 makes this
 * project's oracle and which for these six operations are the correctly
 * rounded IEEE 754 binary64 operations SoftFloat implements.  The oracle
 * shares no code with SoftFloat, so this is a check and not an echo.
 *
 * Values are 32-bit pattern pairs, never decimal text (NR-06), which is
 * also 2c's own float64 shape -- so nothing here needs a 64-bit integer
 * type (NR-04), which is the entire reason 2c is the MVS backend.
 *
 * NaN is excluded (FR-SIM-08, VL-11).  Infinities are kept.
 */
#ifndef ONFLY_ONF2CV_H
#define ONFLY_ONF2CV_H

#define ONF2C_ADD 0
#define ONF2C_SUB 1
#define ONF2C_MUL 2
#define ONF2C_LT  3
#define ONF2C_LE  4
#define ONF2C_EQ  5

struct onf2cv {
    int op;
    unsigned long ahi;
    unsigned long alo;
    unsigned long bhi;
    unsigned long blo;
    unsigned long rhi;
    unsigned long rlo;
};
"""


def render(rows, dropped):
    out = [BANNER, ""]
    out.append("/* %d NaN-result cases excluded (FR-SIM-08, VL-11). */"
               % dropped)
    out.append("#define ONF2C_NVEC %d" % len(rows))
    out.append("")
    out.append("static const struct onf2cv onf2cvec[ONF2C_NVEC] = {")
    for op, ahi, alo, bhi, blo, rhi, rlo in rows:
        # Two lines per vector so no card passes column 80 (D-93).
        out.append("    { ONF2C_%-3s 0x%08lXUL, 0x%08lXUL,"
                   % (op + ",", ahi, alo))
        out.append("      0x%08lXUL, 0x%08lXUL, 0x%08lXUL, 0x%08lXUL },"
                   % (bhi, blo, rhi, rlo))
    out.append("};")
    out.append("")
    out.append("#endif /* ONFLY_ONF2CV_H */")
    return "\n".join(out) + "\n"


def main(argv):
    rows, dropped = build()
    text = render(rows, dropped)
    for n, line in enumerate(text.splitlines(), 1):
        if len(line) > 80:
            raise SystemExit("gen2cv: line %d is %d columns" % (n, len(line)))
    if "--check" in argv:
        have = (io.open(OUT, encoding="ascii").read()
                if os.path.exists(OUT) else None)
        if have != text:
            sys.stderr.write("gen2cv: %s is stale or edited by hand\n" % OUT)
            return 1
        sys.stdout.write("gen2cv: %s matches the generator\n" % OUT)
        return 0
    io.open(OUT, "w", encoding="ascii", newline="\n").write(text)
    sys.stdout.write("gen2cv: wrote %s, %d vectors\n"
                     % (OUT, text.count("{ ONF2C_")))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
