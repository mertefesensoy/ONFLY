/*
 * onffpn.c - NATIVE backend: the ONFLY float API over the host's own IEEE
 * binary64 hardware.
 *
 * ------------------------------------------------------------------------
 * NR-05 EXCLUSION - read this before adding the file to a lint run
 * ------------------------------------------------------------------------
 * NR-05 forbids `float` and `double` "in the engine and the soft float layer".
 * This file is neither: it is the native backend, whose entire purpose is to
 * use the host's `double`.  It is the ONE file in ONFLY excluded from the NR-05
 * lint, and tools/lint_nr05.py is therefore never pointed at it.  Nothing else
 * in the engine may name a floating-point type.
 *
 * ------------------------------------------------------------------------
 * Admission is not automatic (NR-09)
 * ------------------------------------------------------------------------
 * Compiling this file does not make the native backend usable.  NR-09 admits it
 * on a host only when ALL of the following are proven on that host:
 *
 *   - IEEE binary64 with round-to-nearest-ties-to-even
 *   - fused multiply-add contraction disabled (-ffp-contract=off)
 *   - no fast-math
 *   - no x87 extended precision; on x86 that means SSE2
 *   - no flush-to-zero and no denormals-are-zero
 *   - only + - * / and comparison, and no libm
 *   - the TestFloat vectors pass for the operations used
 *   - golden-suite fingerprints are byte-identical to the soft backend
 *
 * On this project's development host that matters concretely: the compiler is
 * 32-bit mingw32, where x87 extended precision is the DEFAULT and would quietly
 * compute intermediate results to 64 significand bits instead of 53.  D-30
 * requires -msse2 -mfpmath=sse -ffp-contract=off, and the Makefile passes them.
 * A native build without those flags is not an admitted backend; it is a bug.
 *
 * Note what this file does NOT do: it never divides and never converts between
 * integers and binary64.  Appendix C's kernel needs only addition,
 * multiplication and comparison, so those are the only operations offered, and
 * the NR-09 admission burden shrinks to exactly what is used.
 *
 * ------------------------------------------------------------------------
 * Why memcpy rather than a union or a pointer cast
 * ------------------------------------------------------------------------
 * Reinterpreting a double's bits through a union member is unspecified in C89,
 * and through a cast pointer it violates aliasing rules that modern compilers
 * actively exploit.  memcpy is the one spelling that is defined everywhere and
 * that every compiler turns back into a register move.  It also matches
 * FR-LOD-05's rule against pointer casts over buffers.
 */
#include <string.h>

#include "onffp.h"

/*
 * Assemble a double from the two halves of an onf_f64.
 *
 * The halves are combined into a byte array in big-endian order first, then
 * byte-swapped if the host is little-endian, so the mapping is stated
 * explicitly rather than inherited from the host's layout.
 */
static double onf_todb(onf_f64 a)
{
    unsigned char bytes[8];
    double d;

    bytes[0] = (unsigned char)((a.hi >> 24) & 0xFFUL);
    bytes[1] = (unsigned char)((a.hi >> 16) & 0xFFUL);
    bytes[2] = (unsigned char)((a.hi >>  8) & 0xFFUL);
    bytes[3] = (unsigned char)( a.hi        & 0xFFUL);
    bytes[4] = (unsigned char)((a.lo >> 24) & 0xFFUL);
    bytes[5] = (unsigned char)((a.lo >> 16) & 0xFFUL);
    bytes[6] = (unsigned char)((a.lo >>  8) & 0xFFUL);
    bytes[7] = (unsigned char)( a.lo        & 0xFFUL);

#ifdef ONF_FP_LITTLE
    {
        unsigned char t;
        int i;
        for (i = 0; i < 4; i++) {
            t = bytes[i];
            bytes[i] = bytes[7 - i];
            bytes[7 - i] = t;
        }
    }
#endif

    memcpy(&d, bytes, 8);
    return d;
}

/* The inverse of onf_todb. */
static onf_f64 onf_frdb(double d)
{
    unsigned char bytes[8];
    onf_f64 z;

    memcpy(bytes, &d, 8);

#ifdef ONF_FP_LITTLE
    {
        unsigned char t;
        int i;
        for (i = 0; i < 4; i++) {
            t = bytes[i];
            bytes[i] = bytes[7 - i];
            bytes[7 - i] = t;
        }
    }
#endif

    z.hi = ((onf_u32)bytes[0] << 24) | ((onf_u32)bytes[1] << 16)
         | ((onf_u32)bytes[2] <<  8) |  (onf_u32)bytes[3];
    z.lo = ((onf_u32)bytes[4] << 24) | ((onf_u32)bytes[5] << 16)
         | ((onf_u32)bytes[6] <<  8) |  (onf_u32)bytes[7];
    return z;
}

onf_f64 onffadd(onf_f64 a, onf_f64 b)
{
    return onf_frdb(onf_todb(a) + onf_todb(b));
}

onf_f64 onffsub(onf_f64 a, onf_f64 b)
{
    return onf_frdb(onf_todb(a) - onf_todb(b));
}

onf_f64 onffmul(onf_f64 a, onf_f64 b)
{
    return onf_frdb(onf_todb(a) * onf_todb(b));
}

int onfflt(onf_f64 a, onf_f64 b)
{
    return (onf_todb(a) < onf_todb(b)) ? 1 : 0;
}

int onffle(onf_f64 a, onf_f64 b)
{
    return (onf_todb(a) <= onf_todb(b)) ? 1 : 0;
}
