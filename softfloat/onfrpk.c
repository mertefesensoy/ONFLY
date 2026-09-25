/*
 * onfrpk.c - ONFLY's derived replacement for SoftFloat's s_roundPackToF64.c.
 *
 * Derived from Berkeley SoftFloat Release 3e, source/s_roundPackToF64.c, by
 * John R. Hauser.  Copyright 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018
 * The Regents of the University of California.  All rights reserved.
 * Redistributed and modified under the three-clause BSD licence, reproduced
 * in full after this comment exactly as upstream's own file carries it, and
 * in third_party/SoftFloat-3e/COPYING.txt (see NFR-LIC-01).  This file is a
 * modified version; the modifications are ONFLY's and are described below.
 *
 * Why this file exists (D-34, D-35).  Upstream s_roundPackToF64.c is the only
 * file in ONFLY's binary64 subset that touches SoftFloat's global state.  It
 * reads softfloat_roundingMode and softfloat_detectTininess and performs one
 * direct `softfloat_exceptionFlags |= softfloat_flag_inexact`.  NFR-MNT-02
 * forbids writable static data so the engine is reentrant for the CICS path,
 * so the state has to go.  D-35 chose a derived copy here over patching
 * third_party/, which keeps the vendored tree matching the digests in D-28.
 *
 * The three modifications, and why each is result-preserving:
 *
 *  1. The rounding mode is hard-wired to round-to-nearest-ties-to-even instead
 *     of read from softfloat_roundingMode.  NR-01 requires exactly that mode
 *     and NR-10 forbids ever changing it, so this removes a variable whose only
 *     permitted value is the one now compiled in.  It makes NR-10 structurally
 *     unviolable rather than merely mandated.  Upstream's roundIncrement for
 *     near-even is 0x200, which is what remains.
 *
 *  2. The `isTiny` computation and its softfloat_raiseFlags(underflow) call are
 *     removed.  isTiny feeds nothing but that flag -- it is not used in any
 *     arithmetic -- so with flags discarded (D-34) the whole computation is
 *     dead code, and removing it also removes the softfloat_detectTininess
 *     read.  No value that reaches the result depends on it.
 *
 *  3. The `softfloat_exceptionFlags |= softfloat_flag_inexact` write and the
 *     overflow raiseFlags call are removed.  Both are pure side effects on
 *     state NR-10 forbids ONFLY from reading.  In the overflow branch upstream
 *     computes `packToF64UI(sign, 0x7FF, 0) - !roundIncrement`; roundIncrement
 *     is 0x200 under near-even, so `!roundIncrement` is 0 and the expression is
 *     just positive or negative infinity.
 *
 *  The SOFTFLOAT_ROUND_ODD branch is not compiled: ONFLY does not define that
 *  macro, and round-odd is unreachable once the mode is fixed to near-even.
 *
 * Consequence: for round-to-nearest-ties-to-even this function returns exactly
 * what upstream returns, bit for bit.  That claim is not taken on trust -- as
 * ONFLY code this file is subject to the TestFloat vectors (TT-02, oracle O-5)
 * like any other part of the float layer.
 *
 * NR-05 note: `float64_t` here is SoftFloat's own type.  In the not-FAST_INT64
 * configuration it is a struct wrapping a 64-bit integer, not a C `double`.
 * No C floating-point type appears in this file.
 */

/*============================================================================

This C source file is part of the SoftFloat IEEE Floating-Point Arithmetic
Package, Release 3e, by John R. Hauser.

Copyright 2011, 2012, 2013, 2014, 2015, 2017 The Regents of the University of
California.  All rights reserved.

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

 1. Redistributions of source code must retain the above copyright notice,
    this list of conditions, and the following disclaimer.

 2. Redistributions in binary form must reproduce the above copyright notice,
    this list of conditions, and the following disclaimer in the documentation
    and/or other materials provided with the distribution.

 3. Neither the name of the University nor the names of its contributors may
    be used to endorse or promote products derived from this software without
    specific prior written permission.

THIS SOFTWARE IS PROVIDED BY THE REGENTS AND CONTRIBUTORS "AS IS", AND ANY
EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE, ARE
DISCLAIMED.  IN NO EVENT SHALL THE REGENTS OR CONTRIBUTORS BE LIABLE FOR ANY
DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
(INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
(INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

=============================================================================*/

#include <stdint.h>
#include "platform.h"
#include "internals.h"
#include "softfloat.h"

float64_t
 softfloat_roundPackToF64( bool sign, int_fast16_t exp, uint_fast64_t sig )
{
    uint_fast16_t roundIncrement, roundBits;
    uint_fast64_t uiZ;
    union ui64_f64 uZ;

    /*------------------------------------------------------------------------
    | Round to nearest, ties to even (NR-01).  Upstream derives this increment
    | from softfloat_roundingMode; here it is the only possibility.
    *------------------------------------------------------------------------*/
    roundIncrement = 0x200;
    roundBits = sig & 0x3FF;

    /*------------------------------------------------------------------------
    | Subnormal and overflow handling.  Upstream's isTiny computation is absent
    | because it fed only the underflow flag (see note 2 above).
    *------------------------------------------------------------------------*/
    if ( 0x7FD <= (uint16_t) exp ) {
        if ( exp < 0 ) {
            sig = softfloat_shiftRightJam64( sig, -exp );
            exp = 0;
            roundBits = sig & 0x3FF;
        } else if (
            (0x7FD < exp)
                || (UINT64_C( 0x8000000000000000 ) <= sig + roundIncrement)
        ) {
            /* Overflow.  Under near-even this rounds to infinity; upstream's
               `- !roundIncrement` term is zero here. */
            uiZ = packToF64UI( sign, 0x7FF, 0 );
            uZ.ui = uiZ;
            return uZ.f;
        }
    }

    /*------------------------------------------------------------------------
    | Round and pack.  The mask below is upstream's ties-to-even correction:
    | when the discarded bits are exactly one half (roundBits == 0x200), the
    | low bit of the significand is cleared, which is what "ties to even" means.
    | Upstream ands that with roundNearEven, which is true by construction here.
    *------------------------------------------------------------------------*/
    sig = (sig + roundIncrement) >> 10;
    sig &= ~(uint_fast64_t) (! (roundBits ^ 0x200));
    if ( ! sig ) exp = 0;

    uiZ = packToF64UI( sign, exp, sig );
    uZ.ui = uiZ;
    return uZ.f;
}
