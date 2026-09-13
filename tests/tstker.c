/*
 * tstker.c - kernel comparison against the Python oracle (FR-SIM-01..09).
 *
 * Builds a synthetic network, prints it, runs the kernel on it, and prints the
 * per-neuron results.  tests/run_ker.py parses the printed network, runs the
 * independent Python oracle on the very same network, and compares.  The
 * network travels from C to Python so that both sides provably simulate the
 * same thing; the *results* are what is compared, and neither side can see the
 * other's.
 *
 * A synthetic network rather than a real one, deliberately: the MaleCNS data,
 * the calibration of W_syn and the subcircuit extraction all belong to Phase C.
 * What Phase B has to establish is that the kernel computes Appendix C exactly,
 * and that question is independent of which network it is fed.
 *
 * NR-05: no float or double appears in this file.  Every constant is a binary64
 * bit pattern computed once on x86, exactly as FR-PRP-06 and NR-06 require of
 * the real network file.
 */
#include <stdio.h>

#include "onfker.h"
#include "onfrnd.h"

#define NEURONS 64
#define MAXDEG 8
#define MAXEDGE (NEURONS * MAXDEG)

/* Timestep 0.1 ms, so 100 microseconds (SR-MOD-02, TBC-02). */
#define DT_US 100
/* Synaptic delay 1.8 ms and refractory period 2.2 ms, in steps. */
#define DELAY 18
#define REFRACT 22

/* weight = synapse count x W_syn (0.275 mV), counts 1..20 (SR-MOD-05).
   Computed on x86 in binary64 and shipped as bit patterns; no target
   platform converts decimal to binary floating point (FR-PRP-06, NR-06). */
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

static onf_u32 rowptr[NEURONS + 1];
static onf_u32 target[MAXEDGE];
static onf_f64 weight[MAXEDGE];
static onf_u32 stimlist[8];
static onf_u32 readlist[8];

static onf_f64 su[NEURONS], sg[NEURONS], sring[DELAY * NEURONS];
static onf_i32 srfr[NEURONS], sspk[NEURONS], sfst[NEURONS], sfrc[NEURONS];
static onf_i32 sstm[NEURONS];

/*
 * Build a deterministic synthetic network.
 *
 * Targets within a row must be strictly ascending (IR-NET-06), so they are
 * produced by walking forward and skipping, never by sorting: that way the
 * invariant holds by construction rather than by a step that could be omitted.
 */
static onf_i32 build(struct onfnet *net)
{
    struct onfrng g;
    onf_i32 i, k, deg, tgt, edges;
    onf_u32 r;

    onfrndi(&g, 20260910UL);
    edges = 0;

    for (i = 0; i < NEURONS; i++) {
        rowptr[i] = (onf_u32)edges;
        deg = (onf_i32)(onfrndn(&g) % (onf_u32)(MAXDEG + 1));
        tgt = -1;
        for (k = 0; k < deg; k++) {
            /* Advance by at least one, so targets strictly ascend. */
            tgt = tgt + 1 + (onf_i32)(onfrndn(&g) % 7UL);
            if (tgt >= NEURONS) {
                break;
            }
            r = onfrndn(&g);
            weight[edges] = onffbit(wtab[r % 20UL][0], wtab[r % 20UL][1]);
            /* Sign from the presynaptic neuron's transmitter (SR-MOD-05):
               about one neuron in three is inhibitory here. */
            if ((onfrndn(&g) % 3UL) == 0UL) {
                weight[edges].hi ^= 0x80000000UL;
            }
            target[edges] = (onf_u32)tgt;
            edges++;
        }
    }
    rowptr[NEURONS] = (onf_u32)edges;

    for (i = 0; i < 8; i++) {
        stimlist[i] = (onf_u32)i;              /* stimulus set: neurons 0..7 */
        readlist[i] = (onf_u32)(NEURONS - 8 + i); /* readout: last eight */
    }

    net->n = NEURONS;
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
    net->uth = onffbit(0x401C0000UL, 0x00000000UL);    /* 7.0 mV  */
    net->ureset = onffbit(0x00000000UL, 0x00000000UL); /* +0.0    */
    net->p11 = onffbit(0x3FEFD724UL, 0x6927D28BUL);    /* exp(-dt/tau_mbr) */
    net->p12 = onffbit(0x3F7439CCUL, 0xE9A65D55UL);    /* exact propagator */
    net->p22 = onffbit(0x3FEF5DC9UL, 0x9BADEC5BUL);    /* exp(-dt/tau_syn) */
    net->geps = onffbit(0x01A56E1FUL, 0xC2F8F359UL);   /* 1e-300  */

    /* v1.1 (D-190): this network is built here rather than decoded from a
       file, so the compensating-input fields must be set explicitly.  Left
       uninitialised they are whatever was on the stack, and a non-zero
       nbias sends the kernel through a null bias pointer -- which is
       exactly what happened the first time this test met a v1.1 onfnet. */
    net->nbias = 0;
    net->brate = 0;
    net->bias = 0;
    return edges;
}

static void print_net(const struct onfnet *net)
{
    onf_i32 i;

    printf("NET n=%ld e=%ld ns=%ld nr=%ld dtus=%ld delay=%ld refract=%ld\n",
           (long)net->n, (long)net->e, (long)net->ns, (long)net->nr,
           (long)net->dtus, (long)net->delay, (long)net->refract);
    printf("CONST uth=%08lX:%08lX ureset=%08lX:%08lX geps=%08lX:%08lX\n",
           (unsigned long)net->uth.hi, (unsigned long)net->uth.lo,
           (unsigned long)net->ureset.hi, (unsigned long)net->ureset.lo,
           (unsigned long)net->geps.hi, (unsigned long)net->geps.lo);
    printf("PROP p11=%08lX:%08lX p12=%08lX:%08lX p22=%08lX:%08lX\n",
           (unsigned long)net->p11.hi, (unsigned long)net->p11.lo,
           (unsigned long)net->p12.hi, (unsigned long)net->p12.lo,
           (unsigned long)net->p22.hi, (unsigned long)net->p22.lo);
    for (i = 0; i <= net->n; i++) {
        printf("ROW i=%ld p=%lu\n", (long)i, (unsigned long)net->rowptr[i]);
    }
    for (i = 0; i < net->e; i++) {
        printf("EDGE k=%ld t=%lu w=%08lX:%08lX\n", (long)i,
               (unsigned long)net->target[i],
               (unsigned long)net->weight[i].hi,
               (unsigned long)net->weight[i].lo);
    }
    for (i = 0; i < net->ns; i++) {
        printf("STIM i=%ld v=%lu\n", (long)i, (unsigned long)net->stim[i]);
    }
    for (i = 0; i < net->nr; i++) {
        printf("READ i=%ld v=%lu\n", (long)i, (unsigned long)net->readout[i]);
    }
}

/* (seed, rate in Hz, steps).  Rate 0 must be exactly silent (ACC-2). */
static const onf_i32 cases[][3] = {
    {      1,   0,  200 },
    {      1,  40,  500 },
    {      1, 120,  500 },
    {      1, 200,  500 },
    {      0, 120,  500 },      /* seed-zero remapping, NR-13 / G-10 */
    { 999999999, 200, 300 },    /* maximum request seed, G-06 */
    {      7, 9999, 100 }       /* NR-12 upper bound, G-07 */
};
#define NCASES (int)(sizeof cases / sizeof cases[0])

int main(void)
{
    struct onfnet net;
    struct onfsta st;
    onf_i32 c, i;
    int rc;

    printf("# tstker backend=%s platform=%s\n", ONF_FPID, ONF_PLATID);
    (void)build(&net);
    print_net(&net);

    st.u = su; st.g = sg; st.rfr = srfr; st.spikes = sspk;
    st.first = sfst; st.force = sfrc; st.isstim = sstm; st.ring = sring;

    for (c = 0; c < NCASES; c++) {
        rc = onfrun(&net, &st, (onf_u32)cases[c][0], cases[c][1], cases[c][2]);
        printf("RUN c=%ld seed=%ld rate=%ld steps=%ld rc=%d\n",
               (long)c, (long)cases[c][0], (long)cases[c][1],
               (long)cases[c][2], rc);
        for (i = 0; i < net.n; i++) {
            printf("OUT c=%ld i=%ld s=%ld f=%ld\n", (long)c, (long)i,
                   (long)st.spikes[i], (long)st.first[i]);
        }
    }

    return 0;
}
