/*
 * onfflag.c - ONFLY's no-op replacement for SoftFloat's softfloat_raiseFlags.
 *
 * D-34: the soft backend holds no writable static data, so that the engine is
 * reentrant for the future CICS path (NFR-MNT-02, Section 3.7).  SoftFloat's
 * own softfloat_raiseFlags accumulates into the global
 * softfloat_exceptionFlags;
 * this replacement discards the notification instead, and the specialization's
 * softfloat_raiseFlags.c is not compiled.
 *
 * Discarding is safe rather than merely convenient.  NR-10 states that no logic
 * shall depend on floating-point exception flags, so nothing in ONFLY may read
 * what this would have recorded.  The conditions the flags would report are
 * handled where they actually matter instead:
 *
 *   invalid / NaN, infinity  FR-SIM-08 aborts the request with ONF903S after
 *                            testing the exponent bits directly, which is a
 *                            stronger check than a sticky flag because it
 *                            names the request that failed.
 *   underflow, subnormals    NR-08 clamps any synaptic value below G_EPS to
 *                            exactly +0.0, which removes subnormal arithmetic
 *                            from the kernel altogether.
 *   inexact                  expected on essentially every operation; it
 *                            carries no information for this workload.
 *
 * This file contains no floating-point type and no static storage (NR-05).
 */
#include <stdint.h>
#include "platform.h"
#include "softfloat.h"

void softfloat_raiseFlags( uint_fast8_t flags )
{
    /* Deliberately empty.  The cast keeps strict compilers quiet about an
       unused parameter without introducing storage. */
    (void) flags;
}
