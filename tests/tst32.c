/*
 * tst32.c - TT-01/32: the 32-bit integer self-test (D-118, NR-14).
 *
 * NR-14 requires an integer self-test for each width the platform's
 * engine actually uses, before any engine test runs.  On MVS, under NR-03
 * and D-105, the float backend is SoftFloat 2c and it uses no 64-bit
 * integer at all -- everything it does is 32-bit -- so this is the check
 * that matters there.  The 64-bit TT-01 keeps running where the type is
 * used, which is x86 today and the s390x and z/OS paths later.
 *
 * It is not a formality.  GCCMVS has already been measured compiling,
 * linking, running and returning a WRONG answer for a variable 64-bit
 * left shift (VL-19).  Nothing about that measurement says its 32-bit
 * code generation is sound, and until this runs there, nobody knows.
 *
 * WHY CARRY AND BORROW ARE TESTED SEPARATELY
 * ------------------------------------------
 * SoftFloat 2c never asks the machine for a carry flag.  It writes
 *
 *     z1 = a1 + b1;  z0 = a0 + b0 + (z1 < a1);
 *
 * so the carry is a comparison.  If either the wrapping addition or that
 * comparison is wrong, every wide value the library builds is wrong, and
 * a float test would report it far from its cause.  ADDC and SUBB check
 * that idiom itself.
 *
 * WIDTH
 * -----
 * `unsigned long` is used because C89 guarantees it is at least 32 bits
 * and PDPCLIB has no others to offer.  It is 32 bits on MVS and on this
 * host, but every result is masked to 32 bits anyway rather than trusted
 * to be -- an unmasked test would quietly pass on a 64-bit host while
 * testing something else.
 *
 * Dialect: C89 (NR-04).  No 64-bit integer type appears, which is the
 * property under test.  No float or double (NR-05).
 */
#include <stdio.h>

#include "onf32v.h"

#define M32 0xFFFFFFFFUL

/* Comparison result bits; the same encoding softfloat/onfint.c uses, so
   the two self-tests report failures in one vocabulary. */
#define C_LT 1UL
#define C_LE 2UL
#define C_EQ 4UL
#define C_GT 8UL
#define C_GE 16UL
#define C_NE 32UL

static long onf32sg(unsigned long v)
{
    /* C89 leaves the unsigned-to-signed conversion of a value above the
       signed maximum implementation-defined, so the sign is reconstructed
       by arithmetic instead of by casting.  Every ONFLY target is two's
       complement; this does not depend on that either. */
    if (v & 0x80000000UL) {
        return -(long)((~v & M32) + 1UL);
    }
    return (long)v;
}

static unsigned long onf32cu(unsigned long a, unsigned long b)
{
    unsigned long m;

    m = 0UL;
    if (a < b) { m |= C_LT; }
    if (a <= b) { m |= C_LE; }
    if (a == b) { m |= C_EQ; }
    if (a > b) { m |= C_GT; }
    if (a >= b) { m |= C_GE; }
    if (a != b) { m |= C_NE; }
    return m;
}

static unsigned long onf32cs(long a, long b)
{
    unsigned long m;

    m = 0UL;
    if (a < b) { m |= C_LT; }
    if (a <= b) { m |= C_LE; }
    if (a == b) { m |= C_EQ; }
    if (a > b) { m |= C_GT; }
    if (a >= b) { m |= C_GE; }
    if (a != b) { m |= C_NE; }
    return m;
}

int main(void)
{
    int i;
    int bad;
    int extra;
    unsigned long a;
    unsigned long b;
    unsigned long r;
    const struct onf32v *v;

    bad = 0;
    printf("# tst32 TT-01/32, the 32-bit integer self-test (NR-14)\n");

    for (i = 0; i < ONF32_NVEC; i++) {
        v = &onf32vec[i];
        a = v->a & M32;
        b = v->b & M32;
        extra = 0;

        switch (v->op) {
        case ONF32_MUL:
            r = (a * b) & M32;
            break;
        case ONF32_DIV:
            r = (a / b) & M32;
            break;
        case ONF32_MOD:
            r = (a % b) & M32;
            break;
        case ONF32_SHL:
            /* NR-11: the count is masked, never left undefined, and the
               value is unsigned so no shift here is on a negative. */
            r = (a << (b & 31UL)) & M32;
            break;
        case ONF32_SHR:
            r = (a >> (b & 31UL)) & M32;
            break;
        case ONF32_ADDC:
            r = (a + b) & M32;
            extra = (r < a) ? 1 : 0;
            break;
        case ONF32_SUBB:
            r = (a - b) & M32;
            extra = (a < b) ? 1 : 0;
            break;
        case ONF32_CMPU:
            r = onf32cu(a, b);
            break;
        default:
            r = onf32cs(onf32sg(a), onf32sg(b));
            break;
        }

        if (r != (v->r & M32) || extra != v->extra) {
            bad++;
            if (bad <= 8) {
                printf("T32 BAD i=%d op=%d a=%08lX b=%08lX\n",
                       i, v->op, a, b);
                printf("T32     got=%08lX/%d want=%08lX/%d\n",
                       r, extra, v->r & M32, v->extra);
            }
        }
    }

    printf("# tst32 %d of %d vectors wrong\n", bad, ONF32_NVEC);
    return (bad == 0) ? 0 : 1;
}
