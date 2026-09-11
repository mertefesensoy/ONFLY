/*
 * tst2c.c - known-answer check for SoftFloat 2c (D-108).
 *
 * NR-03 and D-105 chose Release 2c for MVS because its bits32 build uses
 * no 64-bit integers, and GCCMVS fails on 64-bit integers in four
 * independent ways (VL-19, VL-21).  D-108 put testing that on GCCMVS
 * ahead of everything else, because it is the claim the whole fallback
 * rests on.
 *
 * Building is not enough.  GCCMVS has already been measured compiling,
 * linking, running and returning a WRONG answer (VL-19, the variable
 * left shift), so the library is run here against values whose answers
 * are known independently.  Those come from Python floats, which Section
 * 8.2 makes this project's oracle and which share no code with SoftFloat.
 *
 * The same binary runs on x86, where it must also pass: a vector table
 * that fails on both platforms is a bad table, and one that passes on x86
 * and fails on MVS is the finding this test exists to produce.
 *
 * Dialect: C89 plus long long (NR-04) -- and in fact no 64-bit integer
 * type appears here at all, which is the property being tested.  No float
 * or double either (NR-05): every value is a pair of 32-bit patterns.
 */
#include <stdio.h>

/*
 * The renames come first, before softfloat.h declares anything, so the
 * declarations this file sees and the definitions the library compiles
 * are the same symbols.  C-04 allows eight characters and 2c's own names
 * collide well before that (VL-25, D-111).
 */
#include "onf2cnm.h"

#include "milieu.h"
#include "softfloat.h"
#include "onf2cv.h"

static float64 mk(unsigned long hi, unsigned long lo)
{
    float64 z;

    z.high = (bits32)hi;
    z.low = (bits32)lo;
    return z;
}

int main(void)
{
    int i;
    int bad;
    int cmp;
    float64 a;
    float64 b;
    float64 r;
    const struct onf2cv *v;

    bad = 0;
    printf("# tst2c SoftFloat 2c known-answer check (D-108)\n");

    for (i = 0; i < ONF2C_NVEC; i++) {
        v = &onf2cvec[i];
        a = mk(v->ahi, v->alo);
        b = mk(v->bhi, v->blo);

        if (v->op == ONF2C_LT || v->op == ONF2C_LE || v->op == ONF2C_EQ) {
            if (v->op == ONF2C_LT) {
                cmp = float64_lt(a, b) ? 1 : 0;
            } else if (v->op == ONF2C_LE) {
                cmp = float64_le(a, b) ? 1 : 0;
            } else {
                cmp = float64_eq(a, b) ? 1 : 0;
            }
            if ((unsigned long)cmp != v->rlo) {
                bad++;
                if (bad <= 8) {
                    printf("SF2C BAD i=%d op=%d got=%d want=%lu\n",
                           i, v->op, cmp, v->rlo);
                }
            }
            continue;
        }

        if (v->op == ONF2C_ADD) {
            r = float64_add(a, b);
        } else if (v->op == ONF2C_SUB) {
            r = float64_sub(a, b);
        } else {
            r = float64_mul(a, b);
        }

        if ((unsigned long)r.high != v->rhi
            || (unsigned long)r.low != v->rlo) {
            bad++;
            if (bad <= 8) {
                printf("SF2C BAD i=%d op=%d a=%08lX%08lX b=%08lX%08lX\n",
                       i, v->op, v->ahi, v->alo, v->bhi, v->blo);
                printf("SF2C     got=%08lX%08lX want=%08lX%08lX\n",
                       (unsigned long)r.high, (unsigned long)r.low,
                       v->rhi, v->rlo);
            }
        }
    }

    printf("# tst2c %d of %d vectors wrong\n", bad, ONF2C_NVEC);
    return (bad == 0) ? 0 : 1;
}
