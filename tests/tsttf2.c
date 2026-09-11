/*
 * tsttf2.c - TT-02 on MVS: TestFloat vectors through SoftFloat 2c.
 *
 * NR-14 requires the TestFloat vector suite for the used operations to
 * pass on every compiler and platform.  On x86 that is tests/tstflt.c
 * driven by run_tt02.py, with testfloat_gen piped straight in.  MVS has
 * no testfloat_gen and no pipe, so tools/gentf2.py ships a sampled table
 * instead and this runs it (D-112, D-115).
 *
 * This is deliberately a separate driver from tst2c.c rather than the
 * same one parameterised.  The two check different things against
 * different references -- tst2c.c uses answers from Python floats,
 * Section 8.2's oracle, and this uses Berkeley TestFloat's -- and a
 * single driver switched by a macro would make it easy to report one
 * while having run the other.  The duplication is small and visible; the
 * confusion would not be.
 *
 * Every vector must match.  A mismatch on MVS where x86 agrees is a
 * platform difference, which is the entire reason TT-02 exists.
 *
 * Dialect: C89 plus long long (NR-04) -- and no 64-bit integer type
 * appears here at all, which is the property SoftFloat 2c was chosen for.
 * No float or double (NR-05): values are pairs of 32-bit patterns.
 */
#include <stdio.h>

#include "onf2cnm.h"

#include "milieu.h"
#include "softfloat.h"
#include "onftfv.h"

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
    int perop[6];
    float64 a;
    float64 b;
    float64 r;
    const struct onftfv *v;

    bad = 0;
    for (i = 0; i < 6; i++) {
        perop[i] = 0;
    }
    printf("# tsttf2 TT-02 TestFloat vectors on this platform\n");

    for (i = 0; i < ONFTF_NVEC; i++) {
        v = &onftfvec[i];
        a = mk(v->ahi, v->alo);
        b = mk(v->bhi, v->blo);

        if (v->op == ONFTF_LT || v->op == ONFTF_LE || v->op == ONFTF_EQ) {
            if (v->op == ONFTF_LT) {
                cmp = float64_lt(a, b) ? 1 : 0;
            } else if (v->op == ONFTF_LE) {
                cmp = float64_le(a, b) ? 1 : 0;
            } else {
                cmp = float64_eq(a, b) ? 1 : 0;
            }
            if ((unsigned long)cmp != v->rlo) {
                bad++;
                perop[v->op]++;
                if (bad <= 8) {
                    printf("TF2 BAD i=%d op=%d got=%d want=%lu\n",
                           i, v->op, cmp, v->rlo);
                }
            }
            continue;
        }

        if (v->op == ONFTF_ADD) {
            r = float64_add(a, b);
        } else if (v->op == ONFTF_SUB) {
            r = float64_sub(a, b);
        } else {
            r = float64_mul(a, b);
        }

        if ((unsigned long)r.high != v->rhi
            || (unsigned long)r.low != v->rlo) {
            bad++;
            perop[v->op]++;
            if (bad <= 8) {
                printf("TF2 BAD i=%d op=%d a=%08lX%08lX b=%08lX%08lX\n",
                       i, v->op, v->ahi, v->alo, v->bhi, v->blo);
                printf("TF2     got=%08lX%08lX want=%08lX%08lX\n",
                       (unsigned long)r.high, (unsigned long)r.low,
                       v->rhi, v->rlo);
            }
        }
    }

    printf("TF2 perop add=%d sub=%d mul=%d lt=%d le=%d eq=%d\n",
           perop[0], perop[1], perop[2], perop[3], perop[4], perop[5]);
    printf("# tsttf2 %d of %d vectors wrong\n", bad, ONFTF_NVEC);
    return (bad == 0) ? 0 : 1;
}
