/*
 * onffp2.c - SOFT2C backend: the ONFLY float API over Berkeley SoftFloat 2c.
 *
 * This is the backend MVS uses (D-105, NR-03).  Gate G1 measured that GCCMVS
 * cannot build Release 3e: its 64-bit addition ends in an internal compiler
 * error, its 64-bit divide and modulo helpers are not supplied by PDPCLIB, and
 * its variable-count 64-bit left shift silently drops bit 63 (VL-15, VL-19,
 * VL-21).  Release 2c's bits32 build performs no 64-bit integer arithmetic at
 * all, which is the one property that makes it survivable there.
 *
 * ------------------------------------------------------------------------
 * Why this backend is almost nothing
 * ------------------------------------------------------------------------
 * The 3e backend has to reassemble onf_f64's two halves into the single
 * uint64_t that SoftFloat 3e's float64_t wraps, and split it again on the way
 * out.  Release 2c already carries a binary64 as
 *
 *     typedef struct { bits32 high, low; } float64;
 *
 * which is the same shape as
 *
 *     struct onff64 { onf_u32 hi; onf_u32 lo; };
 *
 * so the conversion is a field-by-field copy and no 64-bit type is named
 * anywhere.  NR-04 permits 64-bit integers in the float layer; this backend
 * does not need the permission, and on MVS it must not take it.
 *
 * The copy is written out field by field rather than done with a cast or a
 * memcpy.  A cast between two structurally identical structs is not legal C89
 * and would be a pointer pun over a buffer besides, which FR-LOD-05 rules out
 * as a decoding technique and which there is no reason to introduce here.  The
 * copy also states, in code, which half is which: `hi` is the half carrying the
 * sign and exponent, the first four bytes of the big-endian on-disk form
 * (IR-NET-01), and 2c calls that half `high`.
 *
 * ------------------------------------------------------------------------
 * NR-05 holds here
 * ------------------------------------------------------------------------
 * No `float`, no `double`, no floating-point literal.  2c's `float64` is a
 * struct of two unsigned ints, exactly like onf_f64.  On MVS a stray `double`
 * would silently be hexadecimal floating point (C-02), so the lint that
 * enforces this covers this file.
 *
 * ------------------------------------------------------------------------
 * No writable static data
 * ------------------------------------------------------------------------
 * Upstream 2c keeps a rounding mode, a tininess mode and sticky exception
 * flags in file-scope variables, and writes the inexact flag on essentially
 * every operation.  D-123 removes all three by derivation, the same way D-34
 * and D-35 removed 3e's, so this backend inherits the reentrancy NFR-MNT-02
 * requires for the future CICS path.  Nothing in this file needs to know that,
 * which is the point: the guarantee is in the library, not in its caller.
 */
#include "milieu.h"
#include "softfloat.h"

#include "onffp.h"

/* onf_f64 -> SoftFloat 2c float64.  Field by field; see the note above. */
static float64 onf_to2c(onf_f64 a)
{
    float64 f;

    f.high = (bits32)a.hi;
    f.low = (bits32)a.lo;
    return f;
}

/* SoftFloat 2c float64 -> onf_f64. */
static onf_f64 onf_fr2c(float64 f)
{
    onf_f64 z;

    z.hi = (onf_u32)f.high;
    z.lo = (onf_u32)f.low;
    return z;
}

onf_f64 onffadd(onf_f64 a, onf_f64 b)
{
    return onf_fr2c(float64_add(onf_to2c(a), onf_to2c(b)));
}

onf_f64 onffsub(onf_f64 a, onf_f64 b)
{
    return onf_fr2c(float64_sub(onf_to2c(a), onf_to2c(b)));
}

onf_f64 onffmul(onf_f64 a, onf_f64 b)
{
    return onf_fr2c(float64_mul(onf_to2c(a), onf_to2c(b)));
}

/* 2c's comparisons return `flag`, which is a char, so the result is narrowed
   to 0 or 1 explicitly rather than returned as-is.
 *
 * The signalling forms are used, not the _quiet ones, for two reasons.  They
 * are what the 3e backend calls -- f64_lt and f64_le are 3e's signalling
 * comparisons -- and they are the two functions VL-22's identity check
 * actually covers (tests/tstc2c.c calls float64_lt and float64_le).  A
 * backend built on functions the verification does not exercise would be
 * verified by association rather than by measurement.
 *
 * The choice cannot change a result.  The two forms differ only in whether a
 * quiet NaN operand raises the invalid flag, both return 0 for any NaN, and
 * D-123 left this library with nowhere to record a flag.  ONFLY never expects
 * a NaN in any case: FR-SIM-08 aborts the request first. */
int onfflt(onf_f64 a, onf_f64 b)
{
    return float64_lt(onf_to2c(a), onf_to2c(b)) ? 1 : 0;
}

int onffle(onf_f64 a, onf_f64 b)
{
    return float64_le(onf_to2c(a), onf_to2c(b)) ? 1 : 0;
}
