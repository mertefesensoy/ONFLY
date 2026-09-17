/*
 * tstfp.c - TU-02: emit float-API results for tests/run_fp.py to check.
 *
 * As with tstunit.c, this program holds no expected values.  It computes and
 * prints; the Python oracle recomputes with plain Python floats -- which are
 * IEEE binary64 -- and decides pass or fail.
 *
 * Operands are generated from the ONFLY PRNG rather than hard-coded, so the C
 * side and the oracle can agree on a large operand set without shipping a
 * vector file.  Both sides run the same xorshift32 (D-32) from the same seed
 * and build operands by the same rule.
 *
 * Why the exponent is constrained.  Uniformly random 64-bit patterns are mostly
 * NaN or infinity, and NaN results would legitimately differ between backends:
 * the soft backend uses the ARM-VFPv2-defaultNaN specialization chosen in D-31,
 * which returns a fixed default NaN, while a native host propagates operand
 * payloads instead.  ONFLY never produces a NaN -- FR-SIM-08 aborts the request
 * first -- so agreement on NaN payloads is not required and testing for it
 * would assert something the design deliberately does not promise.  Operands
 * are therefore drawn as finite values in a range whose sums and products stay
 * finite, and non-finite handling is tested separately through onffnf.
 */
#include <stdio.h>

#include "onffp.h"
#include "onfrnd.h"

#define NPAIRS 400

/* Exponent field range for generated operands: about 1e-19 to 1e15, chosen so
   that neither a sum nor a product can overflow or underflow to subnormal. */
#define EXP_LO 0x3C0UL
#define EXP_SPAN 0x71UL

static onf_f64 gen_operand(struct onfrng *g)
{
    onf_u32 r1, r2, sign, exp, frac;

    r1 = onfrndn(g);
    r2 = onfrndn(g);

    sign = (r1 >> 31) & 1UL;
    exp = EXP_LO + ((r1 >> 8) % EXP_SPAN);
    frac = r1 & 0xFFFFFUL;          /* low 20 bits of the high half */

    return onffbit((sign << 31) | (exp << 20) | frac, r2);
}

static void emit(const char *kind, int i, onf_f64 a, onf_f64 b, onf_f64 z)
{
    printf("%s i=%d a=%08lX:%08lX b=%08lX:%08lX z=%08lX:%08lX\n",
           kind, i,
           (unsigned long)a.hi, (unsigned long)a.lo,
           (unsigned long)b.hi, (unsigned long)b.lo,
           (unsigned long)z.hi, (unsigned long)z.lo);
}

static void emit_nonfin(const char *name, onf_f64 v)
{
    printf("NONFIN name=%s v=%08lX:%08lX nf=%d\n",
           name, (unsigned long)v.hi, (unsigned long)v.lo, onffnf(v));
}

int main(void)
{
    struct onfrng g;
    onf_f64 a, b;
    int i;

    printf("# tstfp backend=%s platform=%s\n", ONF_FPID, ONF_PLATID);

    /* --- generated finite operands ------------------------------------- */
    onfrndi(&g, 12345UL);
    for (i = 0; i < NPAIRS; i++) {
        a = gen_operand(&g);
        b = gen_operand(&g);
        emit("FPADD", i, a, b, onffadd(a, b));
        emit("FPSUB", i, a, b, onffsub(a, b));
        emit("FPMUL", i, a, b, onffmul(a, b));
        printf("FPCMP i=%d a=%08lX:%08lX b=%08lX:%08lX lt=%d le=%d\n",
               i, (unsigned long)a.hi, (unsigned long)a.lo,
               (unsigned long)b.hi, (unsigned long)b.lo,
               onfflt(a, b), onffle(a, b));
        emit("FPABS", i, a, b, onffabs(a));
    }

    /* --- x - x must be exactly +0.0, never -0.0 -------------------------
       This is the case the derived softfloat/onfsub.c changed: upstream picks
       the sign from the global rounding mode, and the derivation fixes it to
       the round-to-nearest answer.  If that derivation were wrong, this is
       where it shows up as 80000000:00000000 instead of 00000000:00000000. */
    onfrndi(&g, 999UL);
    for (i = 0; i < 8; i++) {
        a = gen_operand(&g);
        emit("FPSELF", i, a, a, onffsub(a, a));
    }

    /*
     * --- D-421: the zero constant's BIT PATTERN --------------------------
     *
     * This file already used the zero constant and never checked what it
     * was, which is exactly how a wrong one reached three MVS runs and
     * every suite without being noticed.  On TK5 under GCCMVS the old
     * onffzer() returned a subnormal of the order of 1e-318 instead of
     * +0.0 (VL-122), and because onfinit seeded every u, every g and the
     * whole ring from it, every "+0.0" in the MVS kernel was that
     * subnormal.  No fingerprint moved, because 1e-318 is swamped by
     * everything it meets -- so no fingerprint test could have caught it.
     *
     * The line below is what catches it: the constant is printed as bits
     * and the checker requires 00000000:00000000 exactly.  It runs
     * wherever this self-test runs, which includes GCCMVS on TK5, so this
     * class of defect now fails on the platform where it happens.
     */
    a = onffbit(0UL, 0UL);
    printf("FPZERO z=%08lX:%08lX\n",
           (unsigned long)a.hi, (unsigned long)a.lo);

    /* --- FR-SIM-08: non-finite detection from exponent bits -------------- */
    emit_nonfin("pluszero", onffbit(0UL, 0UL));
    emit_nonfin("one", onffbit(0x3FF00000UL, 0x00000000UL));
    emit_nonfin("minusone", onffbit(0xBFF00000UL, 0x00000000UL));
    emit_nonfin("maxfinite", onffbit(0x7FEFFFFFUL, 0xFFFFFFFFUL));
    emit_nonfin("minnormal", onffbit(0x00100000UL, 0x00000000UL));
    emit_nonfin("subnormal", onffbit(0x00000000UL, 0x00000001UL));
    emit_nonfin("plusinf", onffbit(0x7FF00000UL, 0x00000000UL));
    emit_nonfin("minusinf", onffbit(0xFFF00000UL, 0x00000000UL));
    emit_nonfin("quietnan", onffbit(0x7FF80000UL, 0x00000000UL));
    emit_nonfin("signalnan", onffbit(0x7FF00000UL, 0x00000001UL));

    return 0;
}
