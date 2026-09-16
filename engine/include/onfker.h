/*
 * onfker.h - the ONFLY simulation kernel (FR-SIM-01, SRS Appendix C).
 *
 * Appendix C is the normative step algorithm, and it is now genuinely
 * normative: D-71 closed TBC-01 after the 2026-09-11 session reconciled it
 * against Shiu et al.'s published model.py.  Four semantics were corrected in
 * the process -- g frozen while refractory and reset on spike (D-67), stimulus
 * neurons exempt from refractoriness (D-68), and a strict firing threshold
 * (D-69).  The Python oracle implements the same algorithm independently, so a
 * disagreement between them is a coding error, not a modelling question.
 *
 * The model (SR-MOD-01).  With u = v - V_rest,
 *     du/dt = (g - u) / tau_mbr        dg/dt = -g / tau_syn
 * One step of length dt is the linear update
 *     u' = P11*u + P12*g               g' = P22*g
 * Exact integration and forward Euler differ only in P11, P12 and P22
 * (SR-MOD-03, proposal P-04), so the integration method changes constants and
 * not code.
 *
 * NR-07 is the reason this is spelled out operation by operation: the sequence
 * of floating-point operations in Appendix C is normative, and implementations
 * may not reassociate, fuse or reorder them.
 */
#ifndef ONFKER_H
#define ONFKER_H

#include "onfplat.h"
#include "onffp.h"
#include "onfrnd.h"     /* struct onfrng: the run's PRNG lives in onfsta */

/*
 * A decoded network.  The arrays mirror the network file's payload sections
 * (IR-NET) and are owned by the caller; the kernel never allocates and never
 * performs I/O (FR-SIM-07).
 *
 * Invariants the kernel relies on and does not re-check per step:
 *   rowptr has n + 1 entries and is non-decreasing
 *   target indices are strictly ascending within each row (IR-NET-06).  That
 *     order is normative, not cosmetic: floating-point addition is not
 *     associative, so visiting a row's targets in a different order is a
 *     different answer.
 *   delay >= 1 (Appendix C)
 *   stim and readout indices are ascending and less than n
 */
struct onfnet {
    onf_i32 n;                  /* neuron count */
    onf_i32 e;                  /* edge count */
    const onf_u32 *rowptr;      /* n + 1 CSR row pointers */
    const onf_u32 *target;      /* e CSR target indices */
    const onf_f64 *weight;      /* e edge weights */
    const onf_u32 *stim;        /* ns stimulus neuron indices */
    onf_i32 ns;
    const onf_u32 *readout;     /* nr readout neuron indices */
    onf_i32 nr;
    onf_i32 dtus;               /* timestep in microseconds */
    onf_i32 delay;              /* synaptic delay in steps, >= 1 */
    onf_i32 refract;            /* refractory period in steps */
    onf_f64 uth;                /* firing threshold, relative to V_rest */
    onf_f64 ureset;             /* reset potential, relative to V_rest */
    onf_f64 p11;
    onf_f64 p12;
    onf_f64 p22;
    onf_f64 geps;               /* subnormal clamp threshold (NR-08) */
    /*
     * v1.1 compensating-input table (D-190, D-191).  nbias is the number of
     * sampled stimulus rates; brate points at nbias rates, strictly
     * ascending and beginning with 0; bias points at nbias * n binary64
     * values, row r covering neurons 0..n-1 at rate brate[r].
     *
     * nbias == 0 means the network carries no table and the kernel adds
     * nothing -- which is what the full brain and every pre-v1.1 network
     * carry, since a network that drops nothing has nothing to compensate
     * for.  The kernel must then behave exactly as it did before v1.1, so
     * the two cases are separate loops rather than one loop adding zero.
     *
     * The rate 0 row is required to be zero everywhere, so that ACC-2 -- a
     * request with rate 0 produces zero spikes in every neuron -- stays a
     * deterministic property rather than an accident of the table.
     */
    onf_i32 nbias;
    const onf_u32 *brate;       /* nbias sampled rates, ascending from 0 */
    const onf_f64 *bias;        /* nbias * n compensating inputs */
};

/*
 * Mutable simulation state.  Every array is caller-allocated and at least the
 * indicated length; the kernel initialises them itself, so a caller may reuse
 * one allocation across requests (FR-SIM-07, and the future CICS path where
 * per-task storage is at a premium).
 *
 * The scalars below were locals of onfrun until D-366 approved the resumable
 * split.  They are here, and not there, for one reason: FR-SIM-10 requires a
 * run divided into chunks to produce the identical response, and that is only
 * testable if what one chunk hands the next is a THING rather than a set of
 * locals that vanish when the function returns.  The oracle's _State carries
 * the same five for the same reason.
 *
 * Three of them are what a naive chunked driver gets wrong, and each is wrong
 * silently rather than loudly (TU-10 names this threat):
 *
 *   gen    re-seeding per chunk restarts the stimulus stream, and FR-SIM-04
 *          requires exactly one stream per request
 *   step   the ABSOLUTE step index.  It is read three times per step --
 *          step % delay picks the arrival slot, the same slot is where
 *          emissions are written, and (step + 1) * dtus is the first-spike
 *          latency of FR-SIM-05.  A driver that restarted it per chunk would
 *          rotate the delay ring and mis-date every latency
 *   steps  the request's total, recorded so that onfcont can clamp (D-367)
 *
 * thresh and brow are derived from the request's rate once, in onfinit, and
 * are then read-only.  Keeping them here rather than passing them is what
 * makes it impossible for a caller to change the rate mid-run: onfcont has no
 * parameter through which to do it.
 */
struct onfsta {
    onf_f64 *u;                 /* n */
    onf_f64 *g;                 /* n */
    onf_i32 *rfr;               /* n, refractory steps remaining */
    onf_i32 *spikes;            /* n */
    onf_i32 *first;             /* n, first-spike latency in us, -1 if none */
    onf_i32 *force;             /* n, stimulus-driven spike flags */
    onf_i32 *isstim;            /* n, non-zero for stimulus neurons (D-68) */
    onf_f64 *ring;              /* delay * n, delayed synaptic input */
    struct onfrng gen;          /* NR-13 stream, one per request */
    onf_i32 step;               /* absolute step index, 0 before the first */
    onf_i32 steps;              /* total steps this request asked for */
    onf_u32 thresh;             /* rate * dtus, NR-12; fixed by onfinit */
    onf_i32 brow;               /* bias row offset, or -1 for no table */
};

/* Return codes. */
#define ONFK_OK      0
#define ONFK_NONFIN  1          /* FR-SIM-08: a state value went non-finite */

/*
 * onfrun - simulate one request.
 *
 *   net    decoded network; not modified
 *   st     state arrays; fully initialised by this call, then used as scratch
 *   seed   request seed; 0 is remapped per NR-13 / D-32
 *   rate   stimulus rate in Hz.  The caller must already have validated that
 *          rate * net->dtus <= 1,000,000 (NR-12); an out-of-range rate is a
 *          request error (ONF202E) and never reaches here.
 *   steps  number of timesteps
 *
 * Returns ONFK_OK, or ONFK_NONFIN if any membrane or synaptic value became NaN
 * or infinity, in which case the caller reports ONF903S and abandons the
 * request (FR-SIM-08).  Detection reads the exponent bits rather than comparing
 * floats, because a comparison would depend on the arithmetic being validated.
 *
 * Side effects: writes only through st.  No I/O, no allocation, no static data
 * (FR-SIM-07, NFR-MNT-02).
 *
 * Since D-366 this is DEFINED as onfinit followed by onfcont over the whole
 * step count, and is not a separate implementation of the loop.  That is the
 * point: bit-identity between a whole run and a chunked one is structural,
 * because there is only one loop, rather than a property two copies of the
 * algorithm happen to share.  Every caller that predates the split -- onfrq1,
 * tstker, tstsyn, tstprf, tstdec, runnet -- is unaffected.
 */
int onfrun(const struct onfnet *net, struct onfsta *st,
           onf_u32 seed, onf_i32 rate, onf_i32 steps);

/*
 * onfinit - begin a request without simulating any of it (FR-SIM-10, D-366).
 *
 *   net    decoded network; not modified
 *   st     state arrays; fully initialised by this call
 *   seed   request seed; 0 is remapped per NR-13 / D-32
 *   rate   stimulus rate in Hz, validated by the caller exactly as for onfrun
 *   steps  the request's total number of timesteps, recorded in st->steps
 *
 * Returns ONFK_OK.  It cannot fail today -- there is no arithmetic to go
 * non-finite before the first step -- but it returns int so that onfrun stays
 * the composition below without a special case, and so that a future check
 * here does not change every caller.
 *
 * After this call st->step is 0 and nothing has been simulated.
 *
 * Side effects: writes only through st.  No I/O, no allocation, no static
 * data (FR-SIM-07, NFR-MNT-02).
 *
 * onfcont - simulate up to k more steps of a request onfinit began.
 *
 *   k      steps to advance.  D-367: the kernel clamps to what is left, so
 *          onfcont advances min(k, st->steps - st->step) and a driver cannot
 *          overrun the request by choosing a chunk size that does not divide
 *          the step count.  k <= 0 advances nothing and returns ONFK_OK.
 *
 * Returns ONFK_OK, or ONFK_NONFIN exactly as onfrun does.  Note that a
 * ONFK_NONFIN return leaves st mid-step: the state is abandoned, not resumed,
 * because FR-SIM-08 requires the request itself to be abandoned (ONF903S).
 *
 * The caller may read st->spikes, st->first and st->u between calls; that is
 * how the D-139 stream is produced without the kernel doing any I/O of its
 * own, and it is why the MVS engine needs no kernel change to stream.
 *
 * FR-SIM-10: for every k >= 1 and every placement of chunk boundaries, driving
 * a request to completion through onfcont must leave st identical to what
 * onfrun leaves.  That is a property of this file, and tests/tstgld.c at a
 * non-zero chunk size is what measures it over the Section 8.4 suite.
 */
int onfinit(const struct onfnet *net, struct onfsta *st,
            onf_u32 seed, onf_i32 rate, onf_i32 steps);
int onfcont(const struct onfnet *net, struct onfsta *st, onf_i32 k);

#endif /* ONFKER_H */
