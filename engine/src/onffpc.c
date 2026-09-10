/*
 * onffpc.c - backend-independent parts of the ONFLY float API.
 *
 * These three operations are pure bit manipulation, so they are identical
 * under the soft and native backends and are implemented once.  Keeping them
 * out of the backends means a backend cannot accidentally disagree with the
 * other about what +0.0 is or which bits hold the exponent.
 *
 * NR-05: no float or double appears in this file.
 */
#include "onffp.h"

/* Mask of the sign bit in the high half of a binary64 value. */
#define ONF_SIGNBIT 0x80000000UL

/* Mask of the 11-bit exponent field in the high half. */
#define ONF_EXPMASK 0x7FF00000UL

onf_f64 onffabs(onf_f64 a)
{
    onf_f64 z;

    z.hi = a.hi & ~ONF_SIGNBIT;
    z.lo = a.lo;
    return z;
}

int onffnf(onf_f64 a)
{
    /* FR-SIM-08: read the exponent field directly.  An all-ones exponent is
       infinity when the significand is zero and NaN otherwise; both are
       non-finite, and the caller treats them identically. */
    if ((a.hi & ONF_EXPMASK) == ONF_EXPMASK) {
        return 1;
    }
    return 0;
}

onf_f64 onffzer(void)
{
    onf_f64 z;

    /* NR-06: stated as bits, not as a decimal literal.  +0.0 is all zeros. */
    z.hi = 0UL;
    z.lo = 0UL;
    return z;
}

onf_f64 onffbit(onf_u32 hi, onf_u32 lo)
{
    onf_f64 z;

    z.hi = hi;
    z.lo = lo;
    return z;
}
