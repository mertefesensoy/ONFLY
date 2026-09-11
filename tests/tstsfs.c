/*
 * tstsfs.c - do SoftFloat's variable 64-bit left shifts survive GCCMVS?
 *
 * D-104.  VL-19 measured that GCCMVS's VARIABLE-count 64-bit left shift
 * always writes zero into bit 63, while constant counts are correct.
 * VL-20 then read ONFLY's SoftFloat 3e build and found variable-count
 * shifts in the normalisation, rounding and sticky-bit paths.  That was
 * analysis; this is the measurement.  The same source runs on x86 and on
 * MVS and the two outputs are compared.
 *
 * WHAT IS TESTED, AND WHY THESE TWO FUNCTIONS
 * -------------------------------------------
 * softfloat_shiftRightJam64 computes, for dist < 63,
 *
 *     a >> dist  |  ((uint64_t) (a << (-dist & 63)) != 0)
 *
 * The left shift is a VARIABLE-count shift whose only use is the sticky
 * bit: nonzero means "bits were lost". For dist in 1..63 the shift moves
 * a's low `dist` bits up to the top, so bit 63 of that intermediate is
 * bit dist-1 of a. If bit 63 is forced to zero and that was the only bit
 * set, the sticky bit reads 0 when it should read 1 -- the function
 * reports an exact result where the true one was inexact, and SoftFloat
 * rounds the wrong way with no diagnostic anywhere.
 *
 * The vectors drive exactly that case. For each dist, a is the single bit
 * dist-1, so a >> dist is 0 and the whole answer IS the sticky bit:
 *
 *     every result must be 1.  A zero is the defect, and nothing else.
 *
 * softfloat_shortShiftRightJam64 is the control. It also shifts by a
 * variable count -- ((uint_fast64_t) 1 << dist) - 1 -- but only dist = 63
 * puts a bit in position 63, and there the wrong mask 0xFFFF...F instead
 * of 0x7FFF...F can only add bit 63 of a, which is set only when
 * a >> 63 is already 1 and the result is 1 either way. It should therefore
 * pass everywhere, and if it fails the model of the defect is wrong.
 *
 * BUILDING THE OPERAND WITHOUT THE DEFECT UNDER TEST
 * --------------------------------------------------
 * a is built as `a = 1; while (...) a = a << 1;` -- a CONSTANT-count
 * shift, measured correct. The obvious `(u64) 1 << (dist - 1)` is a
 * variable shift, so the test would then be built out of the very defect
 * it is hunting, which is the mistake the first operation matrix made
 * (VL-19, withdrawn). 64-bit `+` is avoided for the same reason: it ICEs
 * on this compiler.
 *
 * The operand is printed for every vector so that a miscompiled setup is
 * visible as a wrong `a` rather than as a wrong verdict.
 *
 * Dialect: C89 plus long long (NR-04). No float, no double (NR-05).
 */
#include <stdio.h>
#include <stdint.h>

/*
 * Declared here rather than by including "primitives.h". That header has
 * lines of 121 columns and internals.h has 133; the TK5 card reader
 * truncates at column 80 and says nothing (D-93), so pulling them through
 * this transport would corrupt them silently. These two prototypes are
 * copied verbatim from primitives.h lines 53 and 98.
 */
uint64_t softfloat_shortShiftRightJam64( uint64_t a, uint_fast8_t dist );
uint64_t softfloat_shiftRightJam64( uint64_t a, uint_fast32_t dist );

#define ONFS_LO 1
#define ONFS_HI 63

static unsigned long onfshi(uint64_t v)
{
    return (unsigned long)((v >> 32) & 0xFFFFFFFFUL);
}

static unsigned long onfslo(uint64_t v)
{
    return (unsigned long)(v & 0xFFFFFFFFUL);
}

int main(void)
{
    int dist;
    int i;
    int bad;
    uint64_t a;
    uint64_t r;

    bad = 0;
    printf("# tstsfs SoftFloat variable-shift check (D-104)\n");

    for (dist = ONFS_LO; dist <= ONFS_HI; dist++) {
        /* a = bit (dist-1), built by repeated constant shifts. */
        a = (uint64_t)1U;
        for (i = 1; i < dist; i++) {
            a = a << 1;
        }

        r = softfloat_shiftRightJam64(a, (uint_fast32_t)dist);
        printf("SFS JAM  %02d a=%08lX%08lX r=%08lX%08lX\n",
               dist, onfshi(a), onfslo(a), onfshi(r), onfslo(r));
        if (r != (uint64_t)1U) {
            bad++;
        }

        r = softfloat_shortShiftRightJam64(a, (uint_fast8_t)dist);
        printf("SFS SHRT %02d a=%08lX%08lX r=%08lX%08lX\n",
               dist, onfshi(a), onfslo(a), onfshi(r), onfslo(r));
        if (r != (uint64_t)1U) {
            bad++;
        }
    }

    printf("# tstsfs %d of %d results wrong\n",
           bad, (ONFS_HI - ONFS_LO + 1) * 2);
    return (bad == 0) ? 0 : 1;
}
