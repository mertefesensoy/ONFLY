/*
 * onffpr.h - response fingerprint (IR-COM-05, FR-SIM-09).
 *
 * ACC-5 is satisfied when every golden request yields the same fingerprint on
 * every row of the Section 8.3 determinism matrix.  This is the function that
 * decides that, so its input must contain everything that could legitimately
 * differ between runs and nothing that could differ merely between hosts.
 *
 * VL-05 applies: fingerprint agreement proves cross-platform consistency, not
 * scientific correctness.  Two platforms agreeing on a wrong answer still
 * agree.  Correctness rests on ACC-1 to ACC-4.
 */
#ifndef ONFFPR_H
#define ONFFPR_H

#include "onfplat.h"

/* Eight scalars plus three values per output entry, four bytes each, with
   ONF_MAXOUT capped at 32 by the record layout (IR-COM 4.3). */
#define ONF_FPR_MAXLEN (8 * 4 + 32 * 3 * 4)

/*
 * onffpr - compute the response fingerprint.
 *
 *   paycrc    the network payload CRC, so the fingerprint identifies the
 *             network as well as the request
 *   stimid    numeric stimulus ID (D-39): SUGR 1, WATR 2, BITR 3, unknown 0
 *   seed, rate, simms   the request as submitted
 *   rc        the return code this request produced
 *   outcount  number of valid output entries, 0 to 32
 *   steps     timesteps actually simulated
 *   ids, lat, spk   parallel arrays of at least outcount entries; latency is
 *             -1 where a readout neuron never spiked
 *
 * Returns the CRC-32 of the canonical byte string.  No side effects, no static
 * data, no I/O.
 */
onf_u32 onffpr(onf_u32 paycrc, onf_i32 stimid, onf_i32 seed, onf_i32 rate,
               onf_i32 simms, onf_i32 rc, onf_i32 outcount, onf_i32 steps,
               const onf_i32 *ids, const onf_i32 *lat, const onf_i32 *spk);

#endif /* ONFFPR_H */
