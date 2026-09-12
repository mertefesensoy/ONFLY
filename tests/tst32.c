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
 * WHERE THE LOOP LIVES NOW
 * ------------------------
 * D-142 moved the suite itself into softfloat/onfi32.c so that
 * ONFLYENG can run the same check at startup.  This file is the
 * standalone driver: it reports every disagreement and a total, which
 * a startup check has no room for, while onf32ts() returns only the
 * first.  Both call onf32rn(), so the program and the test cannot
 * prove different things.
 *
 * The printed shapes are unchanged.  tools/mvs32.py greps for
 * "# tst32 N of M vectors wrong" and VL-30 quotes it, so altering it
 * would invalidate a recorded result for no gain.
 *
 * Dialect: C89 (NR-04).  No 64-bit integer type appears, which is the
 * property under test.  No float or double (NR-05).
 */
#include <stdio.h>

#include "onfi32.h"
#include "onf32v.h"

#define M32 0xFFFFFFFFUL

int main(void)
{
    int i;
    int bad;
    int extra;
    unsigned long r;
    const struct onf32v *v;

    bad = 0;
    printf("# tst32 TT-01/32, the 32-bit integer self-test (NR-14)\n");

    for (i = 0; i < ONF32_NVEC; i++) {
        if (onf32rn(i, &r, &extra) != ONF32_OK) {
            printf("T32 BAD i=%d rejected by onf32rn\n", i);
            bad++;
            continue;
        }
        v = &onf32vec[i];
        if (r != (v->r & M32) || extra != v->extra) {
            bad++;
            if (bad <= 8) {
                printf("T32 BAD i=%d op=%d a=%08lX b=%08lX\n",
                       i, v->op, v->a & M32, v->b & M32);
                printf("T32     got=%08lX/%d want=%08lX/%d\n",
                       r, extra, v->r & M32, v->extra);
            }
        }
    }

    printf("# tst32 %d of %d vectors wrong\n", bad, ONF32_NVEC);
    return (bad == 0) ? 0 : 1;
}
