/*
 * onffpr.c - the response fingerprint (IR-COM-05, FR-SIM-09).
 *
 * The fingerprint is the CRC-32 of a canonical byte string: the network payload
 * CRC, then the numeric stimulus ID, seed, rate, duration, return code, output
 * count and step count, then each output entry (ID, latency, spike count) for
 * entries below the output count -- every one of them a big-endian 32-bit
 * integer.
 *
 * Why it is built this way, and why it matters more than it looks.
 *
 * Text fields are excluded entirely.  The stimulus code is four characters, and
 * those four characters are different bytes on an ASCII host and on an EBCDIC
 * one.  Including them would make the same request fingerprint differently on
 * MVS than on Linux, which would break ACC-5 for a reason that has nothing to
 * do with the simulation.  So the code travels as a number instead (D-39).
 *
 * Everything is big-endian regardless of host, for the same reason: the
 * fingerprint must depend on the *values*, never on how a host happens to store
 * them.
 *
 * Only entries below the output count are included.  The record always carries
 * 32 output slots, but the unused tail is not part of the answer, and hashing
 * it would make the fingerprint depend on whatever happened to be left in
 * memory.
 *
 * The network payload CRC is the first thing in the string, so a fingerprint
 * identifies the network as well as the request.  Two identical requests
 * against different networks must not collide.
 *
 * NR-05: no float or double appears here.  The fingerprint is computed entirely
 * from integers -- which is also why it is comparable across platforms whose
 * floating-point hardware differs.
 */
#include "onffpr.h"
#include "onfcrc.h"

/* Append one big-endian 32-bit integer to the canonical string. */
static onf_i32 put(onf_u8 *b, onf_i32 at, onf_u32 v)
{
    b[at]     = (onf_u8)((v >> 24) & 0xFFUL);
    b[at + 1] = (onf_u8)((v >> 16) & 0xFFUL);
    b[at + 2] = (onf_u8)((v >>  8) & 0xFFUL);
    b[at + 3] = (onf_u8)( v        & 0xFFUL);
    return at + 4;
}

/* Signed to two's complement without relying on signed overflow (NR-11).
   Latency is -1 when a readout neuron never spiked, so this path is normal
   operation rather than an edge case. */
static onf_u32 twos(onf_i32 v)
{
    if (v < 0) {
        return 0xFFFFFFFFUL - (onf_u32)(-(v + 1));
    }
    return (onf_u32)v;
}

onf_u32 onffpr(onf_u32 paycrc, onf_i32 stimid, onf_i32 seed, onf_i32 rate,
               onf_i32 simms, onf_i32 rc, onf_i32 outcount, onf_i32 steps,
               const onf_i32 *ids, const onf_i32 *lat, const onf_i32 *spk)
{
    onf_u8 canon[ONF_FPR_MAXLEN];
    onf_i32 at, k;

    at = 0;
    at = put(canon, at, paycrc);
    at = put(canon, at, twos(stimid));
    at = put(canon, at, twos(seed));
    at = put(canon, at, twos(rate));
    at = put(canon, at, twos(simms));
    at = put(canon, at, twos(rc));
    at = put(canon, at, twos(outcount));
    at = put(canon, at, twos(steps));

    for (k = 0; k < outcount; k++) {
        at = put(canon, at, twos(ids[k]));
        at = put(canon, at, twos(lat[k]));
        at = put(canon, at, twos(spk[k]));
    }

    return onfcrc(canon, at, 0UL);
}
