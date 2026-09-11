/*
 * onfproc.h - ONFLY's processor definitions for Berkeley SoftFloat 2c.
 *
 * DERIVATIVE WORK.  This file states the integer types Release 2c asks a
 * target to supply.  Upstream ships 386-GCC.h and SPARC-GCC.h as examples;
 * this is ONFLY's, written rather than copied because both of upstream's
 * `#define BITS64`, and BITS64 is the one thing this build exists to avoid.
 * The original examples are in third_party/SoftFloat-2c/processors/ and are
 * unmodified.  Release 2c's legal notice is reproduced in
 * softfloat/c2c/milieu.h and in third_party/MANIFEST.md.
 *
 * WHY BITS64 IS NOT DEFINED
 * -------------------------
 * Measured on TK5 on 2026-09-11 (VL-19, VL-21): GCCMVS fails on 64-bit
 * integers in four independent ways.  It ICEs at four distinct points; its
 * variable-count 64-bit left shift silently writes zero into bit 63; the
 * helpers it calls for 64-bit compare, divide and modulo -- @@UCMPDI,
 * @@UDIVDI, @@UMODDI -- are not in PDPCLIB at all; and it asks for them
 * with an A-type constant where an external routine needs a V-type.
 *
 * With BITS64 undefined, SoftFloat 2c's bits32 build carries a float64 as
 * two 32-bit halves and never forms a 64-bit integer, so none of those four
 * defects has anything to act on.  That is the whole argument for NR-03 and
 * D-105, and it is why this file is short and why it must stay short.
 *
 * Verified by inspection, not assumed: bits32/softfloat.c,
 * bits32/softfloat-macros and the two templates contain no occurrence of
 * `bits64`, `sbits64`, `long long` or `LIT64`.
 *
 * WIDTHS
 * ------
 * Release 2c asks for "the most convenient type that holds integers of at
 * least" the stated width, so uint16 and int16 are `int` here exactly as
 * upstream's own examples have them -- that is not a mistake carried over,
 * it is what the type is for.  The `bitsNN` types are different: those must
 * hold EXACTLY that many bits, so each is checked below rather than trusted.
 * NR-11 already requires int to be verified as 32 bits.
 *
 * No float or double appears here (NR-05).
 */
#ifndef ONFLY_C2C_ONFPROC_H
#define ONFLY_C2C_ONFPROC_H

/*----------------------------------------------------------------------------
| BITS64 is deliberately NOT defined.  See the note above.
*----------------------------------------------------------------------------*/

/*----------------------------------------------------------------------------
| Each of the following `typedef's defines the most convenient type that
| holds integers of at least as many bits as specified.
*----------------------------------------------------------------------------*/
typedef char flag;
typedef unsigned char uint8;
typedef signed char int8;
typedef int uint16;
typedef int int16;
typedef unsigned int uint32;
typedef signed int int32;

/*----------------------------------------------------------------------------
| Each of the following `typedef's defines a type that holds integers of
| exactly the number of bits specified.
*----------------------------------------------------------------------------*/
typedef unsigned char bits8;
typedef signed char sbits8;
typedef unsigned short int bits16;
typedef signed short int sbits16;
typedef unsigned int bits32;
typedef signed int sbits32;

/*----------------------------------------------------------------------------
| The `INLINE' macro. C89 has no `inline', and GCCMVS is an old GCC whose
| `extern inline' follows GNU rather than C99 semantics, so `static' is the
| one spelling that behaves identically on every platform ONFLY builds for.
| This mirrors softfloat/platform.h, which makes the same choice for 3e for
| the same reason.
*----------------------------------------------------------------------------*/
#define INLINE static

/*----------------------------------------------------------------------------
| Exact-width checks. A wrong width here would not fail loudly: it would
| change rounding inside SoftFloat and surface as a fingerprint mismatch on
| one platform only, which is the hardest defect this project can have. The
| negative-array-size idiom is the C89 way to assert.
*----------------------------------------------------------------------------*/
typedef int onf2c_chk8[(sizeof(bits8) == 1) ? 1 : -1];
typedef int onf2c_chk16[(sizeof(bits16) == 2) ? 1 : -1];
typedef int onf2c_chk32[(sizeof(bits32) == 4) ? 1 : -1];

#endif /* ONFLY_C2C_ONFPROC_H */
