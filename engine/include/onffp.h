/*
 * onffp.h - the ONFLY binary64 floating-point API (NR-01, D-04, D-05).
 *
 * Every floating-point operation in ONFLY goes through this API, in the exact
 * order Appendix C specifies (NR-07).  Three backends implement it:
 *
 *   SOFT3E  Berkeley SoftFloat 3e, binary64 subset, flags-free (D-33, D-34).
 *           The reference backend, and the one every x86 and s390x result so
 *           far was produced with.
 *   SOFT2C  Berkeley SoftFloat 2c, bits32 build, flags-free (D-105, D-123).
 *           The backend MVS uses, because Gate G1 measured that GCCMVS
 *           cannot build 3e (VL-19, VL-21) and 2c needs no 64-bit integer at
 *           all.  NR-03's fallback.
 *   NATIVE  the host's own IEEE binary64.  Admissible only where NR-09's
 *           conditions are proven, never assumed.
 *
 * Select with -DONF_FP_NATIVE or -DONF_FP_SOFT2C.  Release 3e is the default,
 * deliberately: a build that forgets to state its backend gets a portable one
 * rather than the host's hardware.
 *
 * The two soft backends are different libraries, so they are named apart
 * (D-124).  A fingerprint that cannot say which library produced it proves
 * nothing about determinism, which is the property this project exists to
 * demonstrate.
 *
 * ------------------------------------------------------------------------
 * Why values are carried as two 32-bit halves
 * ------------------------------------------------------------------------
 * onf_f64 is an opaque bit pattern, not a number the engine can do arithmetic
 * on.  It is stored as two unsigned 32-bit halves rather than one 64-bit
 * integer for two reasons:
 *
 *   NR-04 confines 64-bit integer types to SoftFloat and the float layer.  The
 *   engine holds simulation state of this type, so if onf_f64 contained a
 *   `long long`, 64-bit integers would leak into engine data structures.  With
 *   two halves the engine never names a 64-bit type at all.
 *
 *   NR-05 forbids `float` and `double` anywhere in the engine and the soft
 *   float layer.  A struct of two unsigned ints cannot be accidentally used as
 *   a number: there is no operator that does anything useful to it.  On MVS,
 *   where a stray `double` would silently become hexadecimal floating point,
 *   that is the difference between a wrong answer and a compile error.
 *
 * `hi` is the half containing the sign and exponent -- the first four bytes of
 * the big-endian on-disk representation (IR-NET-01).  This is a logical layout,
 * independent of host byte order.
 *
 * ------------------------------------------------------------------------
 * Contract common to every operation
 * ------------------------------------------------------------------------
 * No operation has side effects, allocates, performs I/O, or touches static
 * data (FR-SIM-07, NFR-MNT-02).  Rounding is round-to-nearest-ties-to-even and
 * is never changed (NR-01, NR-10).  No operation reads or reports IEEE
 * exception flags; conditions that matter are detected explicitly instead
 * (FR-SIM-08 for non-finite values, NR-08 for the subnormal clamp).
 */
#ifndef ONFFP_H
#define ONFFP_H

#include "onfplat.h"

/* An IEEE 754 binary64 value as an opaque bit pattern. */
struct onff64 {
    onf_u32 hi;     /* sign, exponent, and the top 20 significand bits */
    onf_u32 lo;     /* the low 32 significand bits */
};
typedef struct onff64 onf_f64;

/* Backend identification for the run manifest (NFR-OBS-01).  Every reported
   result must name the backend it was produced with. */
#if defined(ONF_FP_NATIVE) && defined(ONF_FP_SOFT2C)
#error "ONF_FP_NATIVE and ONF_FP_SOFT2C are mutually exclusive"
#endif

#ifdef ONF_FP_NATIVE
#define ONF_FPID "NATIVE"
#else
#ifdef ONF_FP_SOFT2C
#define ONF_FPID "SOFT2C"
#else
#define ONF_FPID "SOFT3E"
#endif
#endif

/*
 * onffadd - correctly rounded binary64 addition, Appendix C's (+).
 * onffsub - correctly rounded binary64 subtraction.
 * onffmul - correctly rounded binary64 multiplication, Appendix C's (x).
 *
 * Operands are not modified.  NR-07 forbids reassociating, fusing or reordering
 * these, which is why the kernel calls them one at a time rather than writing
 * compound expressions.
 */
onf_f64 onffadd(onf_f64 a, onf_f64 b);
onf_f64 onffsub(onf_f64 a, onf_f64 b);
onf_f64 onffmul(onf_f64 a, onf_f64 b);

/*
 * onfflt - returns 1 if a < b, else 0.
 * onffle - returns 1 if a <= b, else 0.
 *
 * IEEE ordered comparisons: if either operand is NaN the result is 0.  ONFLY
 * never expects a NaN (FR-SIM-08 aborts first), so this is a defensive
 * definition rather than a relied-upon behaviour.
 */
int onfflt(onf_f64 a, onf_f64 b);
int onffle(onf_f64 a, onf_f64 b);

/*
 * onffabs - a with the sign bit cleared.
 *
 * Pure bit manipulation, identical under both backends, so it is implemented
 * once here rather than per backend.  NR-08's clamp compares |g| against G_EPS
 * and needs exactly this.
 */
onf_f64 onffabs(onf_f64 a);

/*
 * onffnf - returns 1 if a is NaN or infinity, else 0.
 *
 * FR-SIM-08 requires this to be detected "from exponent bits, not by float
 * comparison".  A comparison-based test would depend on the very arithmetic
 * being validated; reading the exponent field cannot.  All-ones exponent means
 * NaN or infinity in binary64.
 */
int onffnf(onf_f64 a);

/*
 * onffzer - the constant +0.0.
 *
 * NR-06 forbids any target platform converting decimal text to binary floating
 * point, so constants may not be written as literals.  +0.0 is all-zero bits,
 * which is the one value that can be stated without a conversion.  Every other
 * constant arrives as a bit pattern in the network header (FR-PRP-06).
 */
onf_f64 onffzer(void);

/*
 * onffbit - build a value from its big-endian bit pattern halves.
 *
 * This is how propagator coefficients, thresholds and weights enter the engine:
 * computed once on x86 and shipped as bit patterns (FR-PRP-06, NR-06).
 */
onf_f64 onffbit(onf_u32 hi, onf_u32 lo);

#endif /* ONFFP_H */
