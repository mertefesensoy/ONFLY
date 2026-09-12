/*
 * onfi32.h - TT-01/32 as a linkable self-test (D-142, D-118, NR-14).
 *
 * NR-14, as D-118 amended it, requires an integer self-test "for each
 * integer width that platform's engine actually uses".  Where NR-03's
 * fallback to SoftFloat Release 2c is in force the engine uses no
 * 64-bit integer at all and the width is 32 bits, which is TT-01/32.
 *
 * tests/tst32.c already ran those vectors on MVS (VL-30), but only as
 * a standalone program with its own main().  ONFLYENG needs to run the
 * same check at startup, so the suite lives here and tst32.c drives it
 * -- one implementation, two callers, and no chance of the program and
 * the test proving different things.
 *
 * WHY THIS EXISTS RATHER THAN A WIDTH SWITCH INSIDE onfint.c
 * ----------------------------------------------------------
 * D-142 keeps the two widths behind two names deliberately.  Hiding
 * both behind onfitst() would make a passing result ambiguous about
 * the thing NR-14 exists to establish: a reader could not tell from
 * the call site which width was actually proven.
 *
 * It is not merely a tidiness argument.  VL-45 measured GCCMVS failing
 * to compile the 64-bit suite at every optimisation level -- "unable
 * to generate reloads" in a 64-bit addition -- so on MVS the 64-bit
 * suite cannot be built at all, let alone run.  The names must be
 * separable at link time, not only at run time.
 *
 * Dialect: C89 (NR-04).  No 64-bit integer type appears anywhere
 * behind this header, which is the property under test.  No float
 * (NR-05).
 */
#ifndef ONFI32_H
#define ONFI32_H

/*
 * onf32rn - compute one vector.
 *
 *   i      vector index, 0 .. ONF32_NVEC-1
 *   r      the 32-bit result, masked
 *   extra  the carry (ADDC) or borrow (SUBB) bit, 0 otherwise
 *
 * Returns 0, or ONF32_RANGE if i is outside the table.  No I/O, no
 * allocation, no writable static data (NFR-MNT-02).
 */
#define ONF32_OK     0
#define ONF32_RANGE  1

int onf32rn(int i, unsigned long *r, int *extra);

/*
 * onf32ts - run the whole suite.
 *
 * Returns 0 if every vector agrees with its known answer, otherwise
 * op * 1000 + (index + 1) for the FIRST disagreement.  That encoding
 * is the same one onfitst() uses, so ONFLYENG reports both widths
 * through one message shape and the two cannot drift.
 */
int onf32ts(void);

/*
 * onf32nm - the name of an operation code, for a failure message.
 * Returns a fixed string, never NULL, "?" for an unknown code.
 */
const char *onf32nm(int op);

#endif /* ONFI32_H */
