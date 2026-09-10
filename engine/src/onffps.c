/*
 * onffps.c - SOFT backend: the ONFLY float API over Berkeley SoftFloat 3e.
 *
 * This is the reference backend (D-04).  It is correct on every platform,
 * including S/370, which has no IEEE floating point in hardware at all (C-02),
 * and it is what the determinism matrix in Section 8.3 compares everything
 * else against.
 *
 * NR-05 holds here: `float64_t` is SoftFloat's own type, which in the
 * not-FAST_INT64 configuration required by NR-02 is a struct wrapping a 64-bit
 * integer, not a C `double`.  No C floating-point type appears in this file.
 *
 * NR-04 permits 64-bit integers in the float layer, which is exactly and only
 * where uint64_t is used below: to reassemble the two halves of onf_f64 into
 * the single 64-bit pattern SoftFloat expects.
 */
#include <stdint.h>

#include "platform.h"
#include "softfloat.h"

#include "onffp.h"

/* onf_f64 (two 32-bit halves) -> SoftFloat float64_t. */
static float64_t onf_tosf(onf_f64 a)
{
    float64_t f;

    f.v = ((uint64_t)a.hi << 32) | (uint64_t)a.lo;
    return f;
}

/* SoftFloat float64_t -> onf_f64.  The shift and mask are explicit rather than
   a cast so the split does not depend on host byte order. */
static onf_f64 onf_frsf(float64_t f)
{
    onf_f64 z;

    z.hi = (onf_u32)((f.v >> 32) & 0xFFFFFFFFUL);
    z.lo = (onf_u32)(f.v & 0xFFFFFFFFUL);
    return z;
}

onf_f64 onffadd(onf_f64 a, onf_f64 b)
{
    return onf_frsf(f64_add(onf_tosf(a), onf_tosf(b)));
}

onf_f64 onffsub(onf_f64 a, onf_f64 b)
{
    return onf_frsf(f64_sub(onf_tosf(a), onf_tosf(b)));
}

onf_f64 onffmul(onf_f64 a, onf_f64 b)
{
    return onf_frsf(f64_mul(onf_tosf(a), onf_tosf(b)));
}

int onfflt(onf_f64 a, onf_f64 b)
{
    return f64_lt(onf_tosf(a), onf_tosf(b)) ? 1 : 0;
}

int onffle(onf_f64 a, onf_f64 b)
{
    return f64_le(onf_tosf(a), onf_tosf(b)) ? 1 : 0;
}
