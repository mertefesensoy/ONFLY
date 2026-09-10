/*
 * onfrnd.c - xorshift32 (NR-13, D-32).
 *
 * Shifts are applied to an unsigned 32-bit value, so the left shifts discard
 * high bits by defined unsigned wraparound and the right shift is applied to a
 * non-negative value (NR-11).  There is no signed arithmetic here at all.
 */
#include "onfrnd.h"

void onfrndi(struct onfrng *g, onf_u32 seed)
{
    if (seed == 0UL) {
        g->s = ONF_SEED0;
    } else {
        g->s = seed;
    }
}

onf_u32 onfrndn(struct onfrng *g)
{
    onf_u32 x;

    x = g->s;
    x ^= x << 13;
    x ^= x >> 17;
    x ^= x << 5;
    g->s = x;
    return x;
}
