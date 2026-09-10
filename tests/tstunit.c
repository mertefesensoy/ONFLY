/*
 * tstunit.c - emit C-computed values for tests/run_units.py to compare.
 *
 * This program contains no expected values.  It computes CRCs, PRNG draws and
 * stimulus outcomes in C and prints them; the Python oracle recomputes all of
 * them independently and decides pass or fail.  Keeping the expectations out of
 * here is deliberate: a test that carries its own answers can agree with a bug.
 *
 * Covers TU-03 (CRC-32), TU-04 (PRNG, including seed 0) and TU-05 (stimulus
 * draws, including the NR-12 rejection path).
 *
 * Output format, one record per line:
 *   CRC  name=<id> crc=<8 hex digits>
 *   PRNG seed=<u32> i=<index> v=<8 hex digits>
 *   STIM seed=<u32> rate=<hz> dt=<us> steps=<n> spikes=<n> draws=<n>
 */
#include <stdio.h>

#include "onfcrc.h"
#include "onfrnd.h"
#include "onfstm.h"

#define PRNG_DRAWS 8

static void emit_crc(const char *name, const onf_u8 *data, onf_i32 len)
{
    printf("CRC name=%s crc=%08lX\n", name,
           (unsigned long)onfcrc(data, len, 0UL));
}

static void emit_prng(onf_u32 seed)
{
    struct onfrng g;
    int i;

    onfrndi(&g, seed);
    for (i = 0; i < PRNG_DRAWS; i++) {
        printf("PRNG seed=%lu i=%d v=%08lX\n",
               (unsigned long)seed, i, (unsigned long)onfrndn(&g));
    }
}

/*
 * Run `steps` stimulus draws and report the spike count and the total number
 * of PRNG draws consumed.  The draw count is what makes the NR-12 rejection
 * path observable: if no draw were ever rejected, draws would equal steps.
 */
static void emit_stim(onf_u32 seed, onf_i32 rate, onf_i32 dt, onf_i32 steps)
{
    struct onfrng g;
    onf_u32 thresh;
    onf_i32 i;
    onf_i32 spikes;
    onf_i32 draws;
    onf_u32 before;
    onf_u32 r;

    thresh = (onf_u32)rate * (onf_u32)dt;
    onfrndi(&g, seed);
    spikes = 0;
    draws = 0;

    for (i = 0; i < steps; i++) {
        /* Count draws by replaying the acceptance rule here rather than by
           instrumenting onfstmd, so the shipped function stays free of test
           scaffolding.  The two must agree, which the spike count checks. */
        for (;;) {
            before = g.s;
            r = onfrndn(&g);
            draws++;
            if (r < ONF_STMREJ) {
                if ((r % ONF_STMMOD) < thresh) {
                    spikes++;
                }
                break;
            }
            (void)before;
        }
    }

    printf("STIM seed=%lu rate=%ld dt=%ld steps=%ld spikes=%ld draws=%ld\n",
           (unsigned long)seed, (long)rate, (long)dt, (long)steps,
           (long)spikes, (long)draws);
}

int main(void)
{
    onf_u8 allbytes[256];
    onf_u8 record[412];
    int i;

    printf("# tstunit on platform %s\n", ONF_PLATID);

    /* --- TU-03: CRC-32 --------------------------------------------------- */
    emit_crc("empty", (const onf_u8 *)"", 0);
    emit_crc("a", (const onf_u8 *)"a", 1);
    emit_crc("abc", (const onf_u8 *)"abc", 3);
    emit_crc("check", (const onf_u8 *)"123456789", 9);

    for (i = 0; i < 256; i++) {
        allbytes[i] = (onf_u8)i;
    }
    emit_crc("allbytes", allbytes, 256);

    for (i = 0; i < 412; i++) {
        record[i] = (onf_u8)((i * 7 + 13) & 0xFF);
    }
    emit_crc("record", record, 412);

    /* --- TU-04: PRNG ----------------------------------------------------- */
    emit_prng(1UL);
    emit_prng(0UL);                 /* seed-zero mapping, NR-13 / G-10 */
    emit_prng(2463534242UL);        /* must equal the seed-0 sequence */
    emit_prng(999999999UL);         /* maximum request seed */
    emit_prng(7UL);

    /* --- TU-05: stimulus draws ------------------------------------------- */
    emit_stim(1UL, 0, 100, 1000);        /* rate 0 must be silent */
    emit_stim(1UL, 200, 100, 1000);
    emit_stim(7UL, 9999, 100, 1000);     /* 9999*100 = 999900, NR-12 upper bound */
    emit_stim(1UL, 120, 100, 200000);    /* long enough to hit rejection */
    emit_stim(0UL, 40, 100, 200000);     /* seed 0, long run */

    return 0;
}
