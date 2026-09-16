/*
 * onfreq.h - one request, processed (FR-BAT, IR-JCL-03, IR-COM-05).
 *
 * D-221 brings the request/response loop forward from Phase E so that TX-01
 * has something real to compare across platforms.  D-224 makes this module
 * the single copy of the sequence: tests/tstgld.c calls it rather than
 * keeping its own.
 *
 * ------------------------------------------------------------------------
 * Why the sequence lives in one place
 * ------------------------------------------------------------------------
 * What this module encodes is an ORDERING, not a calculation:
 *
 *   unknown stimulus  ->  reserved stimulus  ->  rate range  ->  NR-12's
 *   rate * dt <= 1,000,000 bound  ->  duration range  ->  simulate
 *
 * and then a fingerprint computed over whatever that ordering produced.
 * Two copies of an ordering do not diverge loudly.  A drift would surface
 * as a changed fingerprint on one path only -- which is the very class of
 * defect the golden suite exists to catch, and would instead be caused by.
 *
 * ------------------------------------------------------------------------
 * Contract
 * ------------------------------------------------------------------------
 * onfrq1 is a pure function of (net, paycrc, maxms, request) except that it
 * uses *st as scratch: onfrun resets the state at the start of every run
 * (FR-SIM-02), so the same st may be reused across requests and the results
 * do not depend on the order requests are processed in.  That property is
 * what lets ONFLYENG loop over a dataset with one allocation, and it is
 * relied on by ACC-5: a fingerprint must not depend on what ran before it.
 *
 * onfrq1 never fails.  Every rejection is reported as a return code in the
 * result, because a rejected request still has to produce a response record
 * and a fingerprint (FR-BAT-04 prints both).
 */
#ifndef ONFREQ_H
#define ONFREQ_H

#include "onfcom.h"
#include "onfker.h"

/* Return codes, from IR-JCL-04 and Appendix E's RC column. */
#define ONFR_OK    0    /* ONF301I */
#define ONFR_WARN  4    /* ONF201W, reserved stimulus, not simulated */
#define ONFR_ERR   8    /* ONF202E or ONF203E, request rejected */
#define ONFR_SEV  16    /* ONF903S, non-finite state (FR-SIM-08) */

/*
 * A request, independent of where it came from.
 *
 * ms is ALREADY RESOLVED.  Section 8.4's G-09 asks for "the header maximum"
 * and tests/tstgld.c spells that as a negative sentinel in its own table,
 * but resolving it is the caller's business, not this module's: a record
 * read from ONFREQ carries a signed halfword, and a negative value there is
 * a malformed request that must be REJECTED, not silently reinterpreted as
 * the maximum.  Keeping the sentinel out of here is what keeps those two
 * readings apart.
 */
struct onfrq {
    onf_i32 stimid;             /* ONF_STIM_* (generated/onfcom.h) */
    onf_i32 rate;               /* stimulus rate in Hz */
    onf_i32 ms;                 /* duration in ms, resolved */
    onf_i32 seed;               /* PRNG seed; 0 is mapped by NR-13 */
};

/*
 * Which field a rejection was about.
 *
 * Appendix E's ONF202E is "REQUEST FIELD OUT OF RANGE: field", so the caller
 * has to name a field.  It is reported from here rather than re-derived by
 * the caller: re-deriving it would put a second copy of the validation
 * conditions outside this module, which is exactly what D-224 forbids.  It
 * takes no part in the fingerprint -- IR-COM-05's canonical string carries
 * the return code, not the diagnosis.
 */
#define ONFR_F_NONE 0
#define ONFR_F_CODE 1           /* ONF-STIM-CODE, reported as ONF203E */
#define ONFR_F_RATE 2           /* ONF-STIM-RATE */
#define ONFR_F_MS   3           /* ONF-SIM-MS */

/* Everything a response record and a report line need. */
struct onfrz {
    onf_i32 rc;                 /* ONFR_* */
    onf_i32 bad;                /* ONFR_F_*, which field was rejected */
    onf_i32 outcount;           /* readout entries filled, 0..ONF_MAXOUT */
    onf_i32 steps;              /* timesteps simulated; 0 if not simulated */
    onf_u32 fp;                 /* IR-COM-05 fingerprint */
    onf_i32 oid[ONF_MAXOUT];    /* readout neuron identifiers */
    onf_i32 olat[ONF_MAXOUT];   /* first-spike latency in steps; -1 if none */
    onf_i32 ospk[ONF_MAXOUT];   /* spike counts */
};

/*
 * onfsid - map an 8-byte stimulus code to its numeric identifier.
 *
 * The code is text in the HOST code page (Section 4.3), so the comparison is
 * against C string literals and is therefore correct on an EBCDIC host
 * without any translation table.  Trailing spaces are ignored; anything not
 * recognised is ONF_STIM_UNKNOWN, which is 0 so that a record zeroed by a
 * truncated transfer cannot look like a valid SUGR request (D-39).
 */
onf_i32 onfsid(const onf_u8 *code);

/*
 * onfrqg - read the request fields out of a 412-byte record.
 *
 * Big-endian accessors only, never a pointer cast over the buffer
 * (FR-LOD-05, IR-COM-04).
 */
void onfrqg(const onf_u8 *rec, struct onfrq *q);

/*
 * onfrqp - write a result into the response portion of a record.
 *
 * IR-JCL-03: only the response portion is touched; offsets 0 to 15, the
 * request echo, are left exactly as they arrived.  Readout entries at or
 * above outcount are written as zero rather than left alone, so that the
 * bytes of a response record are a function of the result and nothing else
 * -- which is what makes a byte-for-byte comparison across platforms
 * (TX-01) mean something.
 */
void onfrqp(onf_u8 *rec, const struct onfrz *z);

/*
 * onfrq1 - validate one request, simulate it if it is valid, and fingerprint
 * the outcome either way.
 *
 * paycrc and maxms come from the network header: the fingerprint carries the
 * payload CRC so that the same request against a different network is a
 * different fingerprint (IR-COM-05), and maxms bounds the duration
 * (FR-SIM-06).
 */
void onfrq1(const struct onfnet *net, struct onfsta *st,
            onf_u32 paycrc, onf_i32 maxms,
            const struct onfrq *q, struct onfrz *z);

/*
 * onfrq1k - onfrq1, with the simulation driven in chunks of k steps (D-368).
 *
 * Since D-368, onfrq1 is DEFINED as onfrq1k at k <= 0, which means one whole
 * chunk.  There is therefore one implementation of the request sequence, not
 * two: the validation order, the readout extraction and the fingerprint are
 * literally the same code whichever entry point a caller uses.  D-224 put
 * that sequence in one place on purpose -- ONFLYENG, the MVS driver and
 * tests/tstgld.c all run it -- and a second copy of it in a test would have
 * proved the copy rather than the path.
 *
 *   k   chunk size in timesteps.  k <= 0 runs the request in a single chunk,
 *       exactly as onfrq1 always did.  k >= 1 drives it through onfinit and
 *       repeated onfcont calls; the final chunk is short whenever k does not
 *       divide the step count, because D-367 makes onfcont clamp.
 *
 * FR-SIM-10 is the requirement this exists to make measurable: for every
 * k >= 1, z must come back identical -- rc, outcount, steps, every readout
 * triple, and above all the fingerprint z->fp, which IR-COM-05 defines and
 * ACC-5 compares across platforms.  A chunk-dependent fingerprint would not
 * cost a feature; it would cost the determinism claim itself.
 *
 * A request that is REJECTED never reaches the kernel, so k is irrelevant to
 * it -- and that is worth testing too, because a rejected request is
 * fingerprinted as well (FR-BAT-04) and ACC-5 compares those fingerprints.
 */
void onfrq1k(const struct onfnet *net, struct onfsta *st,
             onf_u32 paycrc, onf_i32 maxms,
             const struct onfrq *q, struct onfrz *z, onf_i32 k);

#endif /* ONFREQ_H */
