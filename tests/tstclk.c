/*
 * tstclk.c - what clock is available to an ONFLY program on MVS 3.8j?
 *
 * Gate G3 asks for measured time per neuron-step on TK5, and
 * NFR-PERF-01 states its limit in WALL-CLOCK time.  Neither can be
 * answered without knowing what a C program compiled by GCCMVS can
 * actually read, and PDPCLIB's coverage of <time.h> is not something
 * to assume -- D-92 is on record for exactly that failure mode.
 *
 * So this is a probe, not a test.  It is deliberately one small
 * translation unit with no ONFLY dependencies, because a compile that
 * drags in SoftFloat costs minutes and this question needs a fast
 * round trip.
 *
 * WHAT IT ASKS
 *   - does time() return something that advances?
 *   - does clock() exist, and what is CLOCKS_PER_SEC?
 *   - what resolution does clock() actually deliver, as opposed to
 *     what CLOCKS_PER_SEC claims?  A clock that advertises
 *     microseconds and ticks once a second is worse than useless for
 *     G3, because it would silently quantise every measurement.
 *
 * The busy loop is integer-only on purpose: this must not depend on
 * the float backend, which is the thing G3 will go on to measure.
 */
#include <stdio.h>
#include <time.h>

/* Enough integer work to take a visible amount of time under Hercules
 * without risking a job time-out if it turns out to be fast. */
static long spin(long n)
{
    long i;
    long acc = 0;
    for (i = 0; i < n; i++) {
        acc += (i ^ (acc >> 3)) & 0xFFFF;
    }
    return acc;
}

int main(void)
{
    time_t t0, t1;
    clock_t c0, c1;
    long guard;
    int i;

    printf("# tstclk: clock availability probe for Gate G3\n");

#ifdef CLOCKS_PER_SEC
    printf("CPS  CLOCKS_PER_SEC=%ld\n", (long)CLOCKS_PER_SEC);
#else
    printf("CPS  CLOCKS_PER_SEC undefined\n");
#endif

    t0 = time(NULL);
    c0 = clock();
    printf("T0   time=%ld clock=%ld\n", (long)t0, (long)c0);

    /* Ten chunks, reporting after each, so the listing shows whether
     * the clocks advance smoothly or in jumps.  Resolution is read off
     * the sequence rather than trusted from CLOCKS_PER_SEC. */
    guard = 0;
    for (i = 0; i < 10; i++) {
        guard += spin(200000L);
        t1 = time(NULL);
        c1 = clock();
        printf("TICK %2d time=%ld clock=%ld\n",
               i, (long)t1, (long)c1);
    }

    t1 = time(NULL);
    c1 = clock();
    printf("T1   time=%ld clock=%ld\n", (long)t1, (long)c1);
    printf("DIFF secs=%ld clocks=%ld\n",
           (long)(t1 - t0), (long)(c1 - c0));
    /* Printed so the optimiser cannot discard the loop; the value
     * itself is meaningless. */
    printf("GUARD %ld\n", guard);
    printf("# tstclk done\n");
    return 0;
}
