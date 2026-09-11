/*
 * tstprf.c - Gate G3: how long does one request take on TK5?
 *
 * G3 asks "how large can N and the duration be within 5 minutes?", and
 * NFR-PERF-01 bounds one request at the standard duration to 5 minutes
 * of wall-clock time on the TK5 reference host.  SR-EXT-03 says N is
 * the smallest of 250, 500, 1000, 2000, 4000 that satisfies it.
 *
 * So this does not micro-benchmark.  It runs the actual workload the
 * requirement is written about -- one onfrun() call at the provisional
 * standard duration (D-37: 1000 ms, which at dt=100us is 10,000 steps)
 * -- at each N in SR-EXT-03's sequence, and times it.  A synthetic
 * inner-loop benchmark would have to be argued to be representative;
 * this one is the thing itself.
 *
 * WHY THE REPEAT LOOP
 *   tests/tstclk.c measured what clocks exist here (VL-40): clock() is
 *   a PDPCLIB stub returning -1, and time() has one-second resolution.
 *   One second of error on a two-second run is 50%.  So each
 *   configuration is repeated until at least MINSECS have elapsed, and
 *   the per-request time is the total divided by the repeat count.
 *   The loop also waits for a tick boundary before starting, which
 *   removes the up-to-one-second error at the front.
 *
 * WHY IT PRINTS SPIKE COUNTS
 *   A timing loop whose result is discarded can be optimised away, and
 *   -O1 is in force (D-96).  Printing a checksum of the work makes
 *   that impossible, and doubles as evidence the run did something:
 *   a configuration reporting zero spikes everywhere would be timing
 *   an empty network, not a simulation.
 */
#include <stdio.h>
#include <stdlib.h>
#include <time.h>

#include "onfker.h"
#include "onfrnd.h"

#define MAXN 4000
#define MAXDEG 8
#define MAXEDGE (MAXN * MAXDEG)

/* Matches tests/tstker.c: timestep 0.1 ms, delay 1.8 ms, refractory
   2.2 ms (SR-MOD-02, Appendix C). */
#define DT_US 100
#define DELAY 18
#define REFRACT 22

/* D-37's provisional standard duration, 1000 ms, in steps. */
#define STDSTEPS 10000

/* Minimum seconds per configuration, given time()'s one-second
   resolution.  Twenty seconds holds the quantisation error near 5%. */
#define MINSECS 20

/* Stop adding repeats past this, so a slow configuration cannot run
   the job into a time-out.  A single repeat is always performed. */
#define MAXSECS 150

#define RATE_HZ 50
#define SEED 20260911UL

static const onf_u32 wtab[20][2] = {
    { 0x3FD19999UL, 0x9999999AUL }, { 0x3FE19999UL, 0x9999999AUL },
    { 0x3FEA6666UL, 0x66666667UL }, { 0x3FF19999UL, 0x9999999AUL },
    { 0x3FF60000UL, 0x00000000UL }, { 0x3FFA6666UL, 0x66666667UL },
    { 0x3FFECCCCUL, 0xCCCCCCCEUL }, { 0x40019999UL, 0x9999999AUL },
    { 0x4003CCCCUL, 0xCCCCCCCDUL }, { 0x40060000UL, 0x00000000UL },
    { 0x40083333UL, 0x33333334UL }, { 0x400A6666UL, 0x66666667UL },
    { 0x400C9999UL, 0x9999999AUL }, { 0x400ECCCCUL, 0xCCCCCCCEUL },
    { 0x40108000UL, 0x00000000UL }, { 0x40119999UL, 0x9999999AUL },
    { 0x4012B333UL, 0x33333334UL }, { 0x4013CCCCUL, 0xCCCCCCCDUL },
    { 0x4014E666UL, 0x66666667UL }, { 0x40160000UL, 0x00000000UL }
};

/*
 * Allocated, not static.  At MAXN these arrays are about 1.1 MB, and
 * as statics that became an object deck the assembler could not punch:
 * the first attempt abended SB37 on SYSPUNCH at the ASM step for this
 * unit.  malloc also matches how the real thing will get its storage --
 * onfker.h's contract already anticipates "the future CICS path where
 * per-task storage is at a premium" -- so this is the shape the
 * measurement should have had anyway.
 */
static onf_u32 *rowptr;
static onf_u32 *target;
static onf_f64 *weight;
static onf_u32 stimlist[8];
static onf_u32 readlist[8];

static onf_f64 *su, *sg, *sring;
static onf_i32 *srfr, *sspk, *sfst, *sfrc, *sstm;

/* Allocate or report precisely which one failed.  A blanket "out of
 * memory" would leave the next reader guessing at REGION. */
static void *need(long bytes, const char *what)
{
    void *p = malloc((size_t)bytes);
    if (p == NULL) {
        printf("# tstprf: malloc of %ld bytes for %s FAILED\n",
               bytes, what);
    }
    return p;
}

static int allocate(void)
{
    rowptr = (onf_u32 *)need((long)(MAXN + 1) * 4L, "rowptr");
    target = (onf_u32 *)need((long)MAXEDGE * 4L, "target");
    weight = (onf_f64 *)need((long)MAXEDGE * 8L, "weight");
    su = (onf_f64 *)need((long)MAXN * 8L, "u");
    sg = (onf_f64 *)need((long)MAXN * 8L, "g");
    sring = (onf_f64 *)need((long)DELAY * MAXN * 8L, "ring");
    srfr = (onf_i32 *)need((long)MAXN * 4L, "rfr");
    sspk = (onf_i32 *)need((long)MAXN * 4L, "spikes");
    sfst = (onf_i32 *)need((long)MAXN * 4L, "first");
    sfrc = (onf_i32 *)need((long)MAXN * 4L, "force");
    sstm = (onf_i32 *)need((long)MAXN * 4L, "isstim");
    return (rowptr && target && weight && su && sg && sring
            && srfr && sspk && sfst && sfrc && sstm);
}

/*
 * Build a deterministic synthetic network of n neurons.
 *
 * Identical in construction to tests/tstker.c's build(), parameterised
 * on n: targets are produced by walking forward and skipping so that
 * IR-NET-06's strict ascent holds by construction.  Keeping the two
 * the same matters -- it means the cost measured here is the cost of
 * the network shape the kernel has already been verified against on
 * this platform (VL-33), not of some other shape invented for timing.
 */
static onf_i32 build(struct onfnet *net, onf_i32 n)
{
    struct onfrng g;
    onf_i32 i, k, deg, tgt, edges;
    onf_u32 r;

    onfrndi(&g, 20260910UL);
    edges = 0;

    for (i = 0; i < n; i++) {
        rowptr[i] = (onf_u32)edges;
        deg = (onf_i32)(onfrndn(&g) % (onf_u32)(MAXDEG + 1));
        tgt = -1;
        for (k = 0; k < deg; k++) {
            tgt = tgt + 1 + (onf_i32)(onfrndn(&g) % 7UL);
            if (tgt >= n) {
                break;
            }
            r = onfrndn(&g);
            weight[edges] = onffbit(wtab[r % 20UL][0], wtab[r % 20UL][1]);
            if ((onfrndn(&g) % 3UL) == 0UL) {
                weight[edges].hi ^= 0x80000000UL;
            }
            target[edges] = (onf_u32)tgt;
            edges++;
        }
    }
    rowptr[n] = (onf_u32)edges;

    for (i = 0; i < 8; i++) {
        stimlist[i] = (onf_u32)i;
        readlist[i] = (onf_u32)(n - 8 + i);
    }

    net->n = n;
    net->e = edges;
    net->rowptr = rowptr;
    net->target = target;
    net->weight = weight;
    net->stim = stimlist;
    net->ns = 8;
    net->readout = readlist;
    net->nr = 8;
    net->dtus = DT_US;
    net->delay = DELAY;
    net->refract = REFRACT;
    net->uth = onffbit(0x401C0000UL, 0x00000000UL);
    net->ureset = onffbit(0x00000000UL, 0x00000000UL);
    net->p11 = onffbit(0x3FEFD724UL, 0x6927D28BUL);
    net->p12 = onffbit(0x3F7439CCUL, 0xE9A65D55UL);
    net->p22 = onffbit(0x3FEF5DC9UL, 0x9BADEC5BUL);
    net->geps = onffbit(0x01A56E1FUL, 0xC2F8F359UL);
    return edges;
}

static const onf_i32 sizes[] = { 250, 500, 1000, 2000, 4000 };
#define NSIZES (int)(sizeof sizes / sizeof sizes[0])

int main(void)
{
    struct onfnet net;
    struct onfsta st;
    onf_i32 n, edges, i;
    long reps, totspk;
    time_t t0, t1, mark;
    int rc;
    int ci;

    if (!allocate()) {
        printf("# tstprf: allocation failed, nothing measured\n");
        return 1;
    }

    st.u = su;
    st.g = sg;
    st.rfr = srfr;
    st.spikes = sspk;
    st.first = sfst;
    st.force = sfrc;
    st.isstim = sstm;
    st.ring = sring;

    printf("# tstprf: Gate G3, one request at the standard duration\n");
    printf("# steps=%d dtus=%d rate=%dHz seed=%lu minsecs=%d\n",
           STDSTEPS, DT_US, RATE_HZ, SEED, MINSECS);

    for (ci = 0; ci < NSIZES; ci++) {
        n = sizes[ci];
        edges = build(&net, n);

        /* Start on a tick boundary: time() has one-second resolution,
           so beginning mid-second costs up to a full second. */
        mark = time(NULL);
        do {
            t0 = time(NULL);
        } while (t0 == mark);

        reps = 0;
        totspk = 0;
        rc = ONFK_OK;
        do {
            rc = onfrun(&net, &st, SEED, RATE_HZ, STDSTEPS);
            reps++;
            if (rc != ONFK_OK) {
                break;
            }
            for (i = 0; i < n; i++) {
                totspk += (long)sspk[i];
            }
            t1 = time(NULL);
        } while ((long)(t1 - t0) < MINSECS
                 && (long)(t1 - t0) < MAXSECS);

        t1 = time(NULL);
        printf("PERF n=%ld e=%ld reps=%ld secs=%ld spikes=%ld rc=%d\n",
               (long)n, (long)edges, reps, (long)(t1 - t0), totspk, rc);
        fflush(stdout);
        if (rc != ONFK_OK) {
            printf("# tstprf: kernel returned %d at n=%ld\n",
                   rc, (long)n);
        }
    }

    printf("# tstprf done\n");
    return 0;
}
