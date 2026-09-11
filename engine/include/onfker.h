/*
 * onfker.h - the ONFLY simulation kernel (FR-SIM-01, SRS Appendix C).
 *
 * Appendix C is the normative step algorithm.  It is marked *draft*: its
 * ordering becomes final only when TBC-01 is resolved against Shiu et al.'s
 * published code in Phase C.  Until then it is the working hypothesis, used
 * identically here and in the Python oracle, so any disagreement between the
 * two is a coding error rather than a modelling question.
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
};

/*
 * Mutable simulation state.  Every array is caller-allocated and at least the
 * indicated length; the kernel initialises them itself, so a caller may reuse
 * one allocation across requests (FR-SIM-07, and the future CICS path where
 * per-task storage is at a premium).
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
 */
int onfrun(const struct onfnet *net, struct onfsta *st,
           onf_u32 seed, onf_i32 rate, onf_i32 steps);

#endif /* ONFKER_H */
