/*
 * tstint.c - TT-01: the 64-bit integer self-test binary (NR-04, NR-14, A-05).
 *
 * Gate G1's exit criterion is that TT-01 and TT-02 pass under GCCMVS.  This is
 * TT-01's program.  It has two jobs, and they check different things:
 *
 *   1. It calls onfitst, which compares every vector against the generated
 *      table in the engine's own words.  This is the check ONFLYENG performs
 *      at startup (D-79), so running it here exercises exactly the code path
 *      that will report ONF901S on a real machine.
 *
 *   2. It prints what the compiler actually computed for every vector, so
 *      tests/run_tt01.py can recompute all of them in Python and compare.
 *      That second path matters because it does not trust the generated table:
 *      if tools/genint.py itself were wrong, step 1 would happily agree with
 *      it and step 2 would not.
 *
 * Output is the project's usual "KIND key=value" lines.  Nothing here does
 * arithmetic of its own; it only reports.
 *
 * Exit status 0 when the self-test passes, 1 when it does not.  Printing
 * continues either way, so a failing run still shows every value and a reader
 * can see the shape of the damage rather than only its first symptom.
 */
#include <stdio.h>

#include "onfint.h"
#include "onfivec.h"

int main(void)
{
    int op;
    int idx;
    int rc;
    int self;
    int bad;
    onf_u32 rhi;
    onf_u32 rlo;

    printf("# tstint on platform %s\n", ONF_PLATID);
    printf("# TT-01: %d operation groups\n", (int)ONFI_NOPS);

    bad = 0;
    for (op = 0; op < ONFI_NOPS; op++) {
        for (idx = 0; idx < onfignc(op); idx++) {
            rhi = 0U;
            rlo = 0U;
            rc = onfirun(op, idx, &rhi, &rlo);
            printf("IVEC op=%s idx=%d rhi=%08lX rlo=%08lX rc=%d\n",
                   onfignm(op), idx,
                   (unsigned long)rhi, (unsigned long)rlo, rc);
            if (rc != ONFI_OK) {
                bad++;
            }
        }
    }

    self = onfitst();
    printf("SELF rc=%d\n", self);
    if (self != 0) {
        printf("# ONF901S 64-BIT INTEGER SELF-TEST FAILED: %s vector %d\n",
               onfignm(self / 1000), (self % 1000) - 1);
    }
    printf("# cross-check failures reported by onfirun: %d\n", bad);

    return (self == 0 && bad == 0) ? 0 : 1;
}
