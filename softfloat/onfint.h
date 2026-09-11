/*
 * onfint.h - TT-01, the 64-bit integer known-answer self-test (NR-04, NR-14).
 *
 * Assumption A-05 says GCCMVS synthesizes correct 64-bit integer arithmetic
 * for `long long` on S/370, and records it as Unverified pending Gate G1.
 * S/370 has 32-bit registers and no 64-bit integer instructions, so every
 * 64-bit multiply, divide, shift and carry is built out of 32-bit pieces by
 * the compiler.  Risk R-01 is that some of that construction is wrong.
 *
 * A wrong 64-bit shift would not crash anything.  SoftFloat's binary64
 * significand arithmetic is 64-bit, so the failure would surface as a slightly
 * different number, and a slightly different number is a different fly.
 *
 * ------------------------------------------------------------------------
 * Why this file lives beside SoftFloat and depends on none of it
 * ------------------------------------------------------------------------
 * NR-04 confines 64-bit integer types to SoftFloat and the float layer, so a
 * 64-bit self-test cannot live in engine logic; this directory is where such
 * types are permitted.  But R-01's mitigation is that "TT-01 isolates integer
 * bugs from float bugs", and that only works if TT-01 can run when SoftFloat
 * cannot.  So nothing here includes a SoftFloat header, and nothing here needs
 * the <stdint.h> shim NR-04 promises: the one 64-bit typedef is made locally
 * out of `long long`, which is the whole of what NR-04 permits beyond C89.
 *
 * D-79 gives this test two callers from one vector table: tests/tstint.c runs
 * it as the TT-01 binary for Gate G1, and ONFLYENG calls onfitst at startup
 * and reports ONF901S with return code 16 on failure.  One table means the two
 * cannot drift apart.
 *
 * ------------------------------------------------------------------------
 * Contract
 * ------------------------------------------------------------------------
 * No function here performs I/O, allocates, or touches writable static data.
 * The vector table is const, so onfitst is reentrant and safe for the future
 * CICS path (NFR-MNT-02).  Nothing here uses floating point of any kind
 * (NR-05), and every arithmetic vector is unsigned, so no result depends on
 * signed overflow and nothing negative is shifted or divided (NR-11).
 */
#ifndef ONFINT_H
#define ONFINT_H

#include "onfplat.h"

/* Failure codes from onfirun. */
#define ONFI_OK      0   /* result computed and written */
#define ONFI_RANGE   1   /* op or idx outside the table */
#define ONFI_SPLIT   2   /* the two high-half extractions disagreed */
#define ONFI_SIGNED  3   /* unsigned-to-signed round trip was not faithful */

/*
 * Run one vector and report what the compiler actually computed.
 *
 * op is an ONFI_OP_* constant, idx is 0-based within that group.  On return
 * *rhi and *rlo hold the computed result's high and low 32-bit halves; for
 * the comparison groups *rlo is the ONFI_CMP_* bit set and *rhi is zero.
 * Both are written whenever op and idx are in range, including when the
 * return value reports a cross-check failure, so a caller can print what was
 * produced rather than only that something was wrong.
 *
 * Returns ONFI_OK, or one of the other ONFI_* codes above.
 */
int onfirun(int op, int idx, onf_u32 *rhi, onf_u32 *rlo);

/*
 * Run every vector in every group and compare against the table.
 *
 * Returns 0 when all pass.  Otherwise returns op * 1000 + (idx + 1), which
 * identifies the first failing vector; the 1-based index keeps the code
 * non-zero for vector 0 of group 0.  Cross-check failures from onfirun are
 * reported the same way, because the vector is equally untrustworthy either
 * way.
 */
int onfitst(void);

/*
 * The name of an operation group, for an ONF901S message.  Eight characters
 * or fewer so the message needs no continuation line (IR-MSG-01).  Returns a
 * pointer to static const text, or "?" when op is out of range.
 */
const char *onfignm(int op);

/* The number of vectors in a group, or 0 when op is out of range. */
int onfignc(int op);

#endif /* ONFINT_H */
