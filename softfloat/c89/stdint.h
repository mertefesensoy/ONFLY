/*
 * stdint.h - ONFLY's C89 shim for SoftFloat (NR-04, D-98, D-104).
 *
 * NR-04 fixes the dialect as "C89 plus long long" and requires the project
 * to supply stdint.h and stdbool.h shims for SoftFloat.  Measured on TK5 on
 * 2026-09-11: PDPCLIB, the C library GCCMVS uses on MVS 3.8j, supplies
 * neither -- `#include <stdint.h>` ends in "stdint.h: An error has
 * occurred".  Both headers are C99 and PDPCLIB is C89, so this is expected;
 * it is stated as a measurement because the same session found two
 * expectations wrong.
 *
 * This header is NOT on the include path of a host that has its own.  It is
 * added with -I only where the platform lacks one, so on x86 the real
 * stdint.h is used and this file is inert.  It is nonetheless verified on
 * x86: building the whole SoftFloat test suite with -Isoftfloat/c89 ahead
 * of the system path forces every translation unit through these
 * definitions, and TT-02 and the 2426 fp vectors must still pass unchanged.
 * A shim that is only ever exercised on the platform it was written for is
 * a shim nobody has checked.
 *
 * WIDTHS
 * ------
 * Exact-width types must be exactly that wide, so each is checked below at
 * compile time rather than trusted.  On both targets int is 32 bits (NR-11
 * already requires that to be verified) and long long is 64.
 *
 * The _fast types need only be AT LEAST as wide as their name, and the
 * fastest such type on a 32-bit machine is the machine word.  So
 * uint_fast8_t, uint_fast16_t and uint_fast32_t are all unsigned int here,
 * where glibc on x86-64 makes some of them unsigned char or unsigned long.
 * That difference is deliberate and harmless: SoftFloat uses these only for
 * counts and small flags, and every value it puts in one is inside the
 * range both spellings represent exactly.  The one place the width could
 * bite is `a << (-dist & 63)` in s_shiftRightJam64.c, where dist is
 * uint_fast32_t: negating it wraps modulo 2**32 here and modulo 2**64 on
 * x86-64, and masking with 63 gives the same count either way.
 *
 * NO FLOATING POINT
 * -----------------
 * Nothing here declares float or double (NR-05).  The lint enforces it.
 */
#ifndef ONFLY_C89_STDINT_H
#define ONFLY_C89_STDINT_H

typedef signed char             int8_t;
typedef unsigned char           uint8_t;
typedef short                   int16_t;
typedef unsigned short          uint16_t;
typedef int                     int32_t;
typedef unsigned int            uint32_t;
typedef long long               int64_t;
typedef unsigned long long      uint64_t;

typedef signed char             int_least8_t;
typedef unsigned char           uint_least8_t;
typedef short                   int_least16_t;
typedef unsigned short          uint_least16_t;
typedef int                     int_least32_t;
typedef unsigned int            uint_least32_t;
typedef long long               int_least64_t;
typedef unsigned long long      uint_least64_t;

typedef int                     int_fast8_t;
typedef unsigned int            uint_fast8_t;
typedef int                     int_fast16_t;
typedef unsigned int            uint_fast16_t;
typedef int                     int_fast32_t;
typedef unsigned int            uint_fast32_t;
typedef long long               int_fast64_t;
typedef unsigned long long      uint_fast64_t;

/*
 * Integer constant macros.  C89 has ## , so these need no C99 feature.
 * SoftFloat uses UINT64_C for every 64-bit mask and INT64_C for four
 * exponent bounds.
 */
#define INT64_C(c)      c ## LL
#define UINT64_C(c)     c ## ULL

#define INT8_MAX        127
#define INT8_MIN        (-128)
#define UINT8_MAX       255U
#define INT16_MAX       32767
#define INT16_MIN       (-32767 - 1)
#define UINT16_MAX      65535U
#define INT32_MAX       2147483647
#define INT32_MIN       (-2147483647 - 1)
#define UINT32_MAX      4294967295U
#define INT64_MAX       INT64_C(9223372036854775807)
#define INT64_MIN       (-INT64_MAX - INT64_C(1))
#define UINT64_MAX      UINT64_C(18446744073709551615)

/*
 * Compile-time width checks.  A wrong width here would not fail loudly at
 * run time: it would change rounding deep inside SoftFloat and show up as a
 * fingerprint mismatch on one platform only, which is the hardest kind of
 * defect this project can have.  The negative-array-size idiom is the C89
 * way to assert, and each name says what failed.
 */
typedef int onfi_chk8[(sizeof(uint8_t) == 1) ? 1 : -1];
typedef int onfi_chk16[(sizeof(uint16_t) == 2) ? 1 : -1];
typedef int onfi_chk32[(sizeof(uint32_t) == 4) ? 1 : -1];
typedef int onfi_chk64[(sizeof(uint64_t) == 8) ? 1 : -1];
typedef int onfi_chkf64[(sizeof(uint_fast64_t) >= 8) ? 1 : -1];
typedef int onfi_chkf32[(sizeof(uint_fast32_t) >= 4) ? 1 : -1];

#endif /* ONFLY_C89_STDINT_H */
