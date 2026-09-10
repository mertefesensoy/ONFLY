/*
 * onfstm.h - integer-only stimulus draws (NR-12, FR-SIM-03, proposal P-02).
 *
 * NR-12: draw a 32-bit value r; if r >= 4,294,000,000 discard it and draw
 * again; the neuron spikes if (r mod 1,000,000) < rate_hz * dt_us.
 *
 * The rejection removes modulo bias.  2**32 is not a multiple of 1,000,000, so
 * reducing the whole 32-bit range would make low residues slightly more likely
 * than high ones.  Discarding the tail leaves exactly 4,294 whole cycles of
 * 1,000,000, so every residue is equally likely.
 *
 * No floating point is involved, which is the entire point: this behaves
 * identically on a host with no IEEE floating-point hardware (C-02).
 */
#ifndef ONFSTM_H
#define ONFSTM_H

#include "onfplat.h"
#include "onfrnd.h"

/* Smallest rejected draw: 4,294 whole cycles of ONF_STMMOD. */
#define ONF_STMREJ 4294000000UL

/* Denominator of the per-step spike probability. */
#define ONF_STMMOD 1000000UL

/*
 * onfstmd - one stimulus draw.
 *   g       generator; advanced by at least one draw
 *   thresh  rate_hz * dt_us, which NR-12 requires to be <= ONF_STMMOD.
 *           The caller validates this; a request that violates it is a request
 *           error (ONF202E) and never reaches here.
 * Returns 1 if the neuron spikes this step, 0 otherwise.
 *
 * Appendix C requires exactly one ACCEPTED draw per stimulus neuron per step,
 * whether or not that neuron is refractory, so the stream stays aligned across
 * platforms regardless of network state (FR-SIM-04).
 */
int onfstmd(struct onfrng *g, onf_u32 thresh);

#endif /* ONFSTM_H */
