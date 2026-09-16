/*
 * onfreq.c - one request, processed (FR-BAT, IR-JCL-03, IR-COM-05).
 *
 * See engine/include/onfreq.h for the contract and for why this sequence
 * exists in exactly one place (D-224).
 *
 * NR-05: no float, no double, no floating-point literal.  Every binary64
 * value here is an opaque onf_f64 carried through the kernel, never operated
 * on by this file.
 */
#include "onfreq.h"
#include "onffpr.h"

/* NR-12's bound.  rate_hz * dt_us must not exceed one million, or the
   integer draw in onfstm.c cannot be exactly uniform. */
#define ONFR_DRAW 1000000UL

onf_i32 onfsid(const onf_u8 *code)
{
    /* Section 4.3: X(8), padded with spaces in the host code page.  Compare
       the four significant characters and require the rest to be blank, so
       that "SUGRIOUS" is not accepted as "SUGR". */
    /* const data, not writable static state: NFR-MNT-02 keeps the engine
       free of anything a reentrant CICS build could not share (Section 3.7). */
    static const struct onfnm {
        const char *nm;
        onf_i32 id;
    } tab[3] = {
        { "SUGR", ONF_STIM_SUGR },
        { "WATR", ONF_STIM_WATR },
        { "BITR", ONF_STIM_BITR }
    };
    int i, k;

    for (i = 4; i < 8; i++) {
        if (code[i] != (onf_u8)' ') {
            return ONF_STIM_UNKNOWN;
        }
    }
    for (k = 0; k < 3; k++) {
        if (code[0] == (onf_u8)tab[k].nm[0]
         && code[1] == (onf_u8)tab[k].nm[1]
         && code[2] == (onf_u8)tab[k].nm[2]
         && code[3] == (onf_u8)tab[k].nm[3]) {
            return tab[k].id;
        }
    }
    return ONF_STIM_UNKNOWN;
}

void onfrqg(const onf_u8 *rec, struct onfrq *q)
{
    q->stimid = onfsid(rec + ONF_O_STIMCODE);
    q->seed   = onfg32(rec, ONF_O_SEED);
    q->rate   = (onf_i32)onfg16(rec, ONF_O_STIMRATE);
    q->ms     = (onf_i32)onfg16(rec, ONF_O_SIMMS);
}

void onfrqp(onf_u8 *rec, const struct onfrz *z)
{
    onf_i32 i, off;

    onfp16(rec, ONF_O_RC,       (onf_i16)z->rc);
    onfp16(rec, ONF_O_OUTCOUNT, (onf_i16)z->outcount);
    onfp32(rec, ONF_O_STEPS,    z->steps);

    /* ONF-FPRINT is X(4), four raw big-endian bytes rather than a signed
       binary field, because a CRC-32 does not fit S9(9) COMP and must not be
       reinterpreted as a negative number by COBOL (IR-COM-05). */
    rec[ONF_O_FPRINT]     = (onf_u8)((z->fp >> 24) & 0xFFUL);
    rec[ONF_O_FPRINT + 1] = (onf_u8)((z->fp >> 16) & 0xFFUL);
    rec[ONF_O_FPRINT + 2] = (onf_u8)((z->fp >>  8) & 0xFFUL);
    rec[ONF_O_FPRINT + 3] = (onf_u8)( z->fp        & 0xFFUL);

    for (i = 0; i < ONF_MAXOUT; i++) {
        off = ONF_HEADLEN + i * ONF_OUTLEN;
        if (i < z->outcount) {
            onfp32(rec, off + ONF_OE_ID,     z->oid[i]);
            onfp32(rec, off + ONF_OE_LATUS,  z->olat[i]);
            onfp16(rec, off + ONF_OE_SPIKES, (onf_i16)z->ospk[i]);
        } else {
            onfp32(rec, off + ONF_OE_ID,     0);
            onfp32(rec, off + ONF_OE_LATUS,  0);
            onfp16(rec, off + ONF_OE_SPIKES, 0);
        }
        rec[off + ONF_OE_FILLER]     = 0;
        rec[off + ONF_OE_FILLER + 1] = 0;
    }
}

void onfrq1(const struct onfnet *net, struct onfsta *st,
            onf_u32 paycrc, onf_i32 maxms,
            const struct onfrq *q, struct onfrz *z)
{
    /* D-368: one whole chunk.  This is not a wrapper that reimplements
       anything -- it is the same sequence with k pinned, which is what makes
       chunk invariance structural at this level too. */
    onfrq1k(net, st, paycrc, maxms, q, z, 0);
}

void onfrq1k(const struct onfnet *net, struct onfsta *st,
             onf_u32 paycrc, onf_i32 maxms,
             const struct onfrq *q, struct onfrz *z, onf_i32 k)
{
    onf_i32 i;
    int krc;

    z->rc = ONFR_OK;
    z->bad = ONFR_F_NONE;
    z->outcount = 0;
    z->steps = 0;

    /* --- request validation, in the order the SRS fixes ----------------- */
    if (q->stimid == ONF_STIM_UNKNOWN) {
        /* ONF203E UNKNOWN STIMULUS CODE.  Section 8.4 originally said
           ONF202E here; D-41 settled that Appendix E governs. */
        z->rc = ONFR_ERR;
        z->bad = ONFR_F_CODE;
    } else if (q->stimid != ONF_STIM_SUGR) {
        /* FR-BAT-05: WATR and BITR are reserved, ONF201W, not simulated. */
        z->rc = ONFR_WARN;
    } else if (q->rate < 0 || q->rate > 9999) {
        z->rc = ONFR_ERR;                       /* ONF202E */
        z->bad = ONFR_F_RATE;
    } else if ((onf_u32)q->rate * (onf_u32)net->dtus > ONFR_DRAW) {
        /* NR-12's bound.  Still a rate problem: the rate is in range for the
           record but too high for THIS network's timestep, so naming the
           rate is what tells an operator what to change. */
        z->rc = ONFR_ERR;
        z->bad = ONFR_F_RATE;
    } else if (q->ms < 1 || q->ms > maxms) {
        z->rc = ONFR_ERR;                       /* FR-SIM-06, ONF202E */
        z->bad = ONFR_F_MS;
    } else {
        z->steps = q->ms * 1000 / net->dtus;
        /* D-368.  k <= 0 is one whole chunk, which is onfrun's own shape; a
           positive k drives the identical loop through onfcont.  The chunk
           loop carries nothing across iterations except st itself, because
           everything a step needs to know about where it is in the request
           lives there (D-366) -- no re-seeding, no restarted step index, no
           rate passed a second time.  onfcont clamps its own last chunk
           (D-367), so the caller does not compute min() and cannot overrun. */
        krc = onfinit(net, st, (onf_u32)q->seed, q->rate, z->steps);
        if (krc == ONFK_OK) {
            if (k <= 0) {
                krc = onfcont(net, st, z->steps);
            } else {
                while (st->step < z->steps) {
                    krc = onfcont(net, st, k);
                    if (krc != ONFK_OK) {
                        break;
                    }
                }
            }
        }
        if (krc != ONFK_OK) {
            z->rc = ONFR_SEV;                   /* ONF903S, FR-SIM-08 */
            z->steps = 0;
        } else {
            z->outcount = net->nr;
            if (z->outcount > ONF_MAXOUT) {
                z->outcount = ONF_MAXOUT;
            }
            for (i = 0; i < z->outcount; i++) {
                onf_i32 nix = (onf_i32)net->readout[i];
                z->oid[i]  = nix;
                z->olat[i] = st->first[nix];
                z->ospk[i] = st->spikes[nix];
            }
        }
    }

    /* A rejected request is fingerprinted too: FR-BAT-04 prints the
       fingerprint on every report line, and ACC-5 compares all of them. */
    z->fp = onffpr(paycrc, q->stimid, q->seed, q->rate, q->ms, z->rc,
                   z->outcount, z->steps, z->oid, z->olat, z->ospk);
}
