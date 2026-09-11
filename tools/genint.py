# -*- coding: utf-8 -*-
"""Generate the TT-01 64-bit integer known-answer vectors (NR-14, D-79).

Why this test exists
--------------------
S/370 has 32-bit registers and no 64-bit integer instructions, so GCCMVS and
JCC must *synthesise* every 64-bit operation out of 32-bit ones.  Risk R-01
says that synthesis may be wrong, and assumption A-05 ("GCCMVS synthesizes
correct 64-bit integer arithmetic for `long long` on S/370") is recorded as
Unverified, to be settled at Gate G1.  SoftFloat's binary64 significand
arithmetic is 64-bit, so a wrong shift or a lost carry would not announce
itself as a crash: it would come out as a slightly different fly.

TT-01 is deliberately the *lowest* level of Section 8.1.  Risk R-01's
mitigation is that "TT-01 isolates integer bugs from float bugs", which only
works if TT-01 can run before SoftFloat does.  So the generated table and the
checker it feeds depend on no SoftFloat header, no <stdint.h> shim, and no
floating point of any kind.

How the expectations are produced
---------------------------------
Python integers are exact and unbounded.  Every expectation below is computed
in Python and then reduced modulo 2**64, which is what an unsigned 64-bit type
must do.  This makes Python the oracle, in the sense of SRS Section 8.2, for
the integer layer as well as for the float layer.

NR-11 says the project must not rely on signed overflow, and must shift and
divide only non-negative values.  Every arithmetic vector here is therefore
unsigned.  Signed 64-bit values appear in exactly one group, CMPS, and only
under comparison, which cannot overflow.

No 64-bit literal is ever emitted.  Operands and expectations are stored as
pairs of 32-bit halves and reassembled by the C side, so that the generated
header needs no LL/ULL suffix and no UINT64_C macro -- neither of which C89
has, and neither of which PDPCLIB provides (C-06).

Run:  python tools/genint.py
Writes generated/onfivec.h.  Never edit that file by hand (IR-COM-01).
"""
import hashlib
import io
import os
import sys

M64 = (1 << 64) - 1
M32 = (1 << 32) - 1
TWO32 = 1 << 32
SIGN = 1 << 63

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "generated", "onfivec.h")


# ---------------------------------------------------------------------------
# The operations, and the oracle for each.
#
# Each takes two unsigned 64-bit values and returns an unsigned 64-bit value.
# For the shift groups, b is the shift count: C leaves a shift by the operand
# width undefined, so counts stay in 0..63 and the generator enforces it.
# For the comparison groups the result is a bit set, described at CMP_BITS.
# ---------------------------------------------------------------------------

def op_mul(a, b):
    return (a * b) & M64


def op_div(a, b):
    return a // b


def op_mod(a, b):
    return a % b


def op_shl(a, n):
    return (a << n) & M64


def op_shr(a, n):
    return a >> n


def op_add(a, b):
    return (a + b) & M64


def op_sub(a, b):
    return (a - b) & M64


# Bit positions in the comparison result word.  Every relational operator is
# checked, not just "<": a compiler that synthesises "<" correctly and ">="
# as its wrong negation is a real failure mode.
CMP_BITS = ("lt", "le", "eq", "gt", "ge", "ne")


def _cmpword(a, b):
    r = 0
    if a < b:
        r |= 1
    if a <= b:
        r |= 2
    if a == b:
        r |= 4
    if a > b:
        r |= 8
    if a >= b:
        r |= 16
    if a != b:
        r |= 32
    return r


def op_cmpu(a, b):
    return _cmpword(a, b)


def _signed(v):
    """Interpret an unsigned 64-bit bit pattern as two's-complement signed."""
    return v - (1 << 64) if (v & SIGN) else v


def op_cmps(a, b):
    return _cmpword(_signed(a), _signed(b))


# ---------------------------------------------------------------------------
# The cases.
#
# Values are written as whole 64-bit Python integers here for readability and
# split into halves on the way out.  Each group's comment says which synthesis
# failure the cases are aimed at.
# ---------------------------------------------------------------------------

LOMAX = 0x00000000FFFFFFFF
HIMAX = 0xFFFFFFFF00000000
ALL1 = 0xFFFFFFFFFFFFFFFF
W = TWO32

# A 64x64 multiply is built from four 32x32 partial products whose carries
# must propagate across the word boundary.  These pairs drive each partial
# product in turn, then all of them together, then the cases that wrap.
MUL = [
    (0, 0),
    (1, 1),
    (LOMAX, 1),
    (1, LOMAX),
    (LOMAX, LOMAX),                       # 0xFFFFFFFE00000001: no carry out
    (W, W),                               # wraps to zero
    (W, 1),
    (ALL1, 3),
    (0x00000001FFFFFFFF, LOMAX),
    (0x123456789ABCDEF0, 0x0FEDCBA987654321),
    (SIGN, 2),                            # wraps to zero
    (LOMAX, 0x0000000100000001),
    (0x0000000080000000, 0x0000000080000000),   # 0x4000000000000000
    (ALL1, ALL1),                         # 1 after reduction
]

# Division is the hardest operation to synthesise.  The cases separate the
# easy 64/32 path from the 64/64 path where the divisor exceeds 2**32, and
# include a divisor of 1, a dividend smaller than the divisor, and exact
# division.  No divisor is zero.
DIV = [
    (ALL1, 1),
    (ALL1, LOMAX),                        # 0x0000000100000001
    (ALL1, ALL1),
    (0x123456789ABCDEF0, 0x1000),
    (1, 2),                               # quotient zero
    (HIMAX, W),                           # 0xFFFFFFFF
    (SIGN, 3),
    (W, LOMAX),                           # quotient 1, remainder 1
    (0xDEADBEEFCAFEBABE, 0x00000000FEDCBA98),   # 64/32
    (0xDEADBEEFCAFEBABE, 0x0000000100000001),   # 64/64, divisor > 2**32
    (0x7FFFFFFFFFFFFFFF, 0x7FFFFFFFFFFFFFFE),
    (0, 7),
]

# Shifts on a 32-bit machine change shape at the word boundary: a count below
# 32 moves bits between words, a count of 32 exchanges the words, and a count
# above 32 does both.  Zero is included because a synthesised shift often
# implements it as "shift by 32-n" and gets n=0 wrong.
SHIFT_COUNTS = (0, 1, 7, 31, 32, 33, 63)
SHIFT_VALUES = (1, LOMAX, ALL1, 0x123456789ABCDEF0, SIGN, W)
SHL = [(v, n) for v in SHIFT_VALUES for n in SHIFT_COUNTS]
SHR = list(SHL)

# Carry out of the low word into the high word, and borrow the other way.
ADD = [
    (LOMAX, 1),                           # carry into the high word
    (ALL1, 1),                            # wraps to zero
    (LOMAX, LOMAX),
    (0x7FFFFFFFFFFFFFFF, 1),
    (HIMAX, W),                           # wraps to zero
    (0, 0),
    (0x00000000FFFFFFFE, 3),
]
SUB = [
    (W, 1),                               # borrow from the high word
    (0, 1),                               # wraps to all ones
    (W, W),
    (SIGN, 1),
    (ALL1, ALL1),
    (0x0000000100000001, 2),
]

# The classic synthesis bug is an unsigned comparison performed as a signed
# one, which only shows when bit 63 is set.  The first two pairs are exactly
# that case; the rest separate a difference in the high word from one in the
# low word, and pin the equal case.
CMPU = [
    (SIGN, 1),
    (1, SIGN),
    (ALL1, 0),
    (W, LOMAX),
    (LOMAX, 0x00000000FFFFFFFE),
    (LOMAX, LOMAX),
    (0, 0),
    (SIGN, SIGN),
]

# And the mirror image: a signed comparison performed as an unsigned one.
CMPS = [
    (ALL1, 0),                            # -1 < 0
    (SIGN, 0),                            # most negative < 0
    (SIGN, ALL1),                         # most negative < -1
    (0x7FFFFFFFFFFFFFFF, ALL1),           # most positive > -1
    (0xFFFFFFFF7FFFFFFF, 0xFFFFFFFF80000000),   # crosses the 32-bit boundary
    (ALL1, ALL1),
]

# Each row is (label, op macro, array symbol, cases, oracle, is_shift).
#
# The array symbol is stated rather than derived from the label, because C-04
# holds every name `nm` reports -- statics included -- to eight characters and
# to uniqueness within the first eight ignoring case.  Symbols built as
# "onfi_" + label would give onfi_cmpu and onfi_cmps: nine characters, and
# identical for the first eight.  To the MVS linkage editor those are one
# symbol, which is how a program links cleanly and reads the wrong table.
GROUPS = (
    ("MUL", "ONFI_OP_MUL", "onfvmul", MUL, op_mul, False),
    ("DIV", "ONFI_OP_DIV", "onfvdiv", DIV, op_div, False),
    ("MOD", "ONFI_OP_MOD", "onfvmod", DIV, op_mod, False),
    ("SHL", "ONFI_OP_SHL", "onfvshl", SHL, op_shl, True),
    ("SHR", "ONFI_OP_SHR", "onfvshr", SHR, op_shr, True),
    ("ADD", "ONFI_OP_ADD", "onfvadd", ADD, op_add, False),
    ("SUB", "ONFI_OP_SUB", "onfvsub", SUB, op_sub, False),
    ("CMPU", "ONFI_OP_CMPU", "onfvcmu", CMPU, op_cmpu, False),
    ("CMPS", "ONFI_OP_CMPS", "onfvcms", CMPS, op_cmps, False),
)


def halves(v):
    return (v >> 32) & M32, v & M32


def emit():
    for name, _mac, _sym, cases, _fn, isshift in GROUPS:
        for a, b in cases:
            if not (0 <= a <= M64 and 0 <= b <= M64):
                raise ValueError("%s: operand out of range" % name)
            if isshift and not (0 <= b <= 63):
                raise ValueError("%s: shift count %d outside 0..63" % (name, b))
            if name in ("DIV", "MOD") and b == 0:
                raise ValueError("%s: divisor is zero" % name)

    src = io.open(os.path.abspath(__file__), "rb").read()
    digest = hashlib.sha256(src).hexdigest()

    out = []
    w = out.append
    w("/*")
    w(" * ONFLY generated file - DO NOT EDIT (IR-COM-01, D-79).")
    w(" * Generated by tools/genint.py.")
    w(" * genint.py sha256 %s" % digest)
    w(" * Edit tools/genint.py and regenerate.")
    w(" * Hand edits are lost and are a requirements violation.")
    w(" *")
    w(" * TT-01 known-answer vectors for 64-bit integer arithmetic (NR-04,")
    w(" * NR-14, A-05).  Expectations were computed with exact Python integers")
    w(" * on x86, which is what NR-14 means by \"vectors generated on x86\".")
    w(" *")
    w(" * Every value is a pair of 32-bit halves so that no 64-bit literal and")
    w(" * no LL suffix appears here: C89 has neither, and PDPCLIB ships no")
    w(" * <stdint.h> to supply UINT64_C (C-06, NR-04).")
    w(" */")
    w("#ifndef ONFIVEC_H")
    w("#define ONFIVEC_H")
    w("")
    w("#include \"onfplat.h\"")
    w("")
    w("/* One vector: operands a and b, and the expected result r, each as a")
    w("   high and a low 32-bit half.  For SHL and SHR, blo is the shift count")
    w("   and bhi is zero.  For CMPU and CMPS, rlo is the bit set described by")
    w("   the ONFI_CMP_* macros below and rhi is zero. */")
    w("struct onfiv {")
    w("    onf_u32 ahi;")
    w("    onf_u32 alo;")
    w("    onf_u32 bhi;")
    w("    onf_u32 blo;")
    w("    onf_u32 rhi;")
    w("    onf_u32 rlo;")
    w("};")
    w("")
    for i, bit in enumerate(CMP_BITS):
        w("#define ONFI_CMP_%-3s 0x%02XU" % (bit.upper(), 1 << i))
    w("")
    for i, (_name, mac, _sym, _cases, _fn, _s) in enumerate(GROUPS):
        w("#define %-14s %d" % (mac, i))
    w("#define %-14s %d" % ("ONFI_NOPS", len(GROUPS)))
    w("")

    for name, _mac, arr, cases, fn, _isshift in GROUPS:
        w("static const struct onfiv %s[%d] = {" % (arr, len(cases)))
        for a, b in cases:
            r = fn(a, b)
            if not (0 <= r <= M64):
                raise ValueError("%s: result out of range" % name)
            ah, al = halves(a)
            bh, bl = halves(b)
            rh, rl = halves(r)
            w("    { 0x%08XU, 0x%08XU, 0x%08XU, 0x%08XU, 0x%08XU, 0x%08XU },"
              % (ah, al, bh, bl, rh, rl))
        w("};")
        w("")

    w("/* One row per operation, in ONFI_OP_* order.  The name is eight")
    w("   characters or fewer so it can be reported in an ONF901S message")
    w("   without a continuation line (IR-MSG-01). */")
    w("struct onfivg {")
    w("    const char *name;")
    w("    onf_u32 count;")
    w("    const struct onfiv *vec;")
    w("};")
    w("")
    w("static const struct onfivg onfvgrp[ONFI_NOPS] = {")
    for name, _mac, arr, cases, _fn, _isshift in GROUPS:
        w("    { \"%s\", %dU, %s }," % (name, len(cases), arr))
    w("};")
    w("")
    w("#endif /* ONFIVEC_H */")

    text = "\n".join(out) + "\n"
    io.open(OUT, "w", encoding="ascii", newline="\n").write(text)
    total = sum(len(c) for _n, _m, _s, c, _f, _i in GROUPS)
    sys.stdout.write("genint: wrote %s\n" % os.path.relpath(OUT, ROOT))
    sys.stdout.write("genint: %d groups, %d vectors\n" % (len(GROUPS), total))
    for name, _mac, _sym, cases, _fn, _isshift in GROUPS:
        sys.stdout.write("genint:   %-5s %3d\n" % (name, len(cases)))


if __name__ == "__main__":
    emit()
