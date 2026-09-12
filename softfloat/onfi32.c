/*
 * onfi32.c - TT-01/32, the 32-bit integer self-test (D-142, D-118, NR-14).
 *
 * The vectors and the reasoning behind them are in generated/onf32v.h
 * and in tests/tst32.c, which was where this loop lived until D-142
 * needed ONFLYENG to run it too.  Moving it here rather than copying it
 * is the point: the program and the test now prove the same thing by
 * construction.
 *
 * WIDTH
 * -----
 * `unsigned long` is used because C89 guarantees it is at least 32 bits
 * and PDPCLIB offers nothing else.  It is 32 bits on MVS and on the x86
 * host, but every result is masked to 32 bits anyway rather than
 * trusted to be -- an unmasked test would quietly pass on a 64-bit host
 * while testing something other than what it claims.
 *
 * Dialect: C89 (NR-04).  No 64-bit integer type appears, which is the
 * property under test.  No float or double (NR-05).  No writable static
 * data (NFR-MNT-02), so ONFLYENG stays reentrant for the CICS path.
 */
#include "onfi32.h"
#include "onf32v.h"

#define M32 0xFFFFFFFFUL

/* The comparison result bits, matching what tools/gen32v.py emits. */
#define C_LT 1UL
#define C_LE 2UL
#define C_EQ 4UL
#define C_GT 8UL
#define C_GE 16UL
#define C_NE 32UL

/*
 * Reinterpret a masked 32-bit value as signed, without relying on the
 * implementation-defined conversion of a value above LONG_MAX.  C89
 * leaves that conversion implementation-defined rather than undefined,
 * but "implementation-defined" is exactly what a self-test may not
 * assume about the compiler it is testing.
 */
static long onf32sg(unsigned long v)
{
    v &= M32;
    if (v & 0x80000000UL) {
        /* Two's complement, computed rather than cast. */
        return -(long)((~v & M32) + 1UL);
    }
    return (long)v;
}

static unsigned long onf32cu(unsigned long a, unsigned long b)
{
    unsigned long f = 0UL;

    if (a < b) {
        f |= C_LT;
    }
    if (a <= b) {
        f |= C_LE;
    }
    if (a == b) {
        f |= C_EQ;
    }
    if (a > b) {
        f |= C_GT;
    }
    if (a >= b) {
        f |= C_GE;
    }
    if (a != b) {
        f |= C_NE;
    }
    return f;
}

static unsigned long onf32cs(long a, long b)
{
    unsigned long f = 0UL;

    if (a < b) {
        f |= C_LT;
    }
    if (a <= b) {
        f |= C_LE;
    }
    if (a == b) {
        f |= C_EQ;
    }
    if (a > b) {
        f |= C_GT;
    }
    if (a >= b) {
        f |= C_GE;
    }
    if (a != b) {
        f |= C_NE;
    }
    return f;
}

int onf32rn(int i, unsigned long *r, int *extra)
{
    const struct onf32v *v;
    unsigned long a;
    unsigned long b;

    if (i < 0 || i >= ONF32_NVEC) {
        return ONF32_RANGE;
    }

    v = &onf32vec[i];
    a = v->a & M32;
    b = v->b & M32;
    *extra = 0;

    switch (v->op) {
    case ONF32_MUL:
        *r = (a * b) & M32;
        break;
    case ONF32_DIV:
        *r = (a / b) & M32;
        break;
    case ONF32_MOD:
        *r = (a % b) & M32;
        break;
    case ONF32_SHL:
        /* NR-11: the count is masked, never left undefined, and the
           value is unsigned so no shift here is on a negative. */
        *r = (a << (b & 31UL)) & M32;
        break;
    case ONF32_SHR:
        *r = (a >> (b & 31UL)) & M32;
        break;
    case ONF32_ADDC:
        *r = (a + b) & M32;
        *extra = (*r < a) ? 1 : 0;
        break;
    case ONF32_SUBB:
        *r = (a - b) & M32;
        *extra = (a < b) ? 1 : 0;
        break;
    case ONF32_CMPU:
        *r = onf32cu(a, b);
        break;
    default:
        *r = onf32cs(onf32sg(a), onf32sg(b));
        break;
    }
    return ONF32_OK;
}

int onf32ts(void)
{
    int i;
    int extra;
    unsigned long r;
    const struct onf32v *v;

    for (i = 0; i < ONF32_NVEC; i++) {
        if (onf32rn(i, &r, &extra) != ONF32_OK) {
            continue;
        }
        v = &onf32vec[i];
        if (r != (v->r & M32) || extra != v->extra) {
            /* The same encoding onfitst() uses, so ONFLYENG reports
               both widths through one message shape (D-142). */
            return v->op * 1000 + (i + 1);
        }
    }
    return 0;
}

const char *onf32nm(int op)
{
    switch (op) {
    case ONF32_MUL:
        return "MUL";
    case ONF32_DIV:
        return "DIV";
    case ONF32_MOD:
        return "MOD";
    case ONF32_SHL:
        return "SHL";
    case ONF32_SHR:
        return "SHR";
    case ONF32_ADDC:
        return "ADDC";
    case ONF32_SUBB:
        return "SUBB";
    case ONF32_CMPU:
        return "CMPU";
    case ONF32_CMPS:
        return "CMPS";
    default:
        return "?";
    }
}
