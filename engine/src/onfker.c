/*
 * onfker.c - the ONFLY simulation kernel, SRS Appendix C.
 *
 * Every floating-point operation goes through the onf_fp API in Appendix C's
 * exact order (NR-07).  That is why the integration below is written as four
 * separate statements rather than one expression: a compound expression invites
 * the compiler to contract or reassociate, and NR-07 forbids both.
 *
 * NR-05: no float or double appears here.  onf_f64 is an opaque pair of 32-bit
 * halves; nothing in this file can do arithmetic on it except through onf_fp.
 */
#include "onfker.h"
#include "onfrnd.h"
#include "onfstm.h"

int onfrun(const struct onfnet *net, struct onfsta *st,
           onf_u32 seed, onf_i32 rate, onf_i32 steps)
{
    struct onfrng gen;
    onf_f64 zero;
    onf_u32 thresh;
    onf_i32 t, i, k, s, slot, arrive, base;
    onf_f64 a, b;
    int was_rfr;

    zero = onffzer();
    thresh = (onf_u32)rate * (onf_u32)net->dtus;
    onfrndi(&gen, seed);

    /* Appendix C: all binary64 state starts at +0.0, rfr at 0, first at -1. */
    for (i = 0; i < net->n; i++) {
        st->u[i] = zero;
        st->g[i] = zero;
        st->rfr[i] = 0;
        st->spikes[i] = 0;
        st->first[i] = -1;
        st->force[i] = 0;
        st->isstim[i] = 0;
    }
    /* D-68: stimulus neurons have no refractory period, matching Shiu's
       rfc = 0 for Poisson targets.  Marked once here rather than searched for
       on every spike. */
    for (s = 0; s < net->ns; s++) {
        st->isstim[net->stim[s]] = 1;
    }
    for (i = 0; i < net->delay * net->n; i++) {
        st->ring[i] = zero;
    }

    for (t = 0; t < steps; t++) {

        /* --- 1. ARRIVALS ------------------------------------------------ */
        slot = t % net->delay;
        base = slot * net->n;
        for (i = 0; i < net->n; i++) {
            st->g[i] = onffadd(st->g[i], st->ring[base + i]);
            st->ring[base + i] = zero;
        }

        /* --- 2. STIMULUS DRAWS ------------------------------------------
           Exactly one accepted draw per stimulus neuron per step, whether or
           not that neuron is refractory.  That is what keeps the PRNG stream
           aligned across platforms regardless of network state (FR-SIM-04):
           if a refractory neuron skipped its draw, two hosts whose networks
           had diverged would consume different numbers of draws. */
        for (s = 0; s < net->ns; s++) {
            st->force[net->stim[s]] = onfstmd(&gen, thresh);
        }

        /* --- 3. INTEGRATE, DETECT, EMIT --------------------------------- */
        for (i = 0; i < net->n; i++) {

            if (st->rfr[i] > 0) {
                st->rfr[i] = st->rfr[i] - 1;
                /* D-67: g is FROZEN while refractory, matching Shiu's
                   "(unless refractory)" on dg/dt.  u is held at U_reset.
                   Appendix C decayed it here until that amendment. */
                was_rfr = 1;
            } else {
                a = onffmul(net->p11, st->u[i]);
                b = onffmul(net->p12, st->g[i]);
                st->u[i] = onffadd(a, b);
                st->g[i] = onffmul(net->p22, st->g[i]);
                was_rfr = 0;
            }

            /* NR-08: clamp below G_EPS to exactly +0.0.  This removes
               subnormal arithmetic -- and with it any host difference in
               subnormal handling -- from the kernel entirely. */
            if (onfflt(onffabs(st->g[i]), net->geps)) {
                st->g[i] = zero;
            }

            /* FR-SIM-08: detect NaN and infinity from the exponent bits.  A
               float comparison would depend on the arithmetic under test. */
            if (onffnf(st->u[i]) || onffnf(st->g[i])) {
                return ONFK_NONFIN;
            }

            /* D-69: the threshold is STRICT (u > U_th), matching Shiu's
               eq_th 'v > v_th'.  onfflt(uth, u) is exactly u > uth. */
            if (!was_rfr && (onfflt(net->uth, st->u[i]) || st->force[i])) {
                st->u[i] = net->ureset;
                /* D-67: g is reset on every spike (Shiu's
                   eq_rst 'g = 0*mV'). */
                st->g[i] = zero;
                /* D-68: stimulus neurons never become refractory. */
                st->rfr[i] = st->isstim[i] ? 0 : net->refract;
                st->spikes[i] = st->spikes[i] + 1;
                if (st->first[i] < 0) {
                    st->first[i] = (t + 1) * net->dtus;
                }
                /* Appendix C writes arrivals into slot (t + D) mod D, which is
                   the slot just consumed and zeroed above.  It is next read at
                   the start of step t + D, which is exactly the delay.
                   Targets are visited in CSR order because IR-NET-06 makes
                   that order normative: floating-point addition does not
                   associate, so a different order is a different answer. */
                arrive = base;
                for (k = (onf_i32)net->rowptr[i];
                     k < (onf_i32)net->rowptr[i + 1]; k++) {
                    onf_i32 tgt = (onf_i32)net->target[k];
                    st->ring[arrive + tgt] =
                        onffadd(st->ring[arrive + tgt], net->weight[k]);
                }
            }

            st->force[i] = 0;
        }
    }

    return ONFK_OK;
}
