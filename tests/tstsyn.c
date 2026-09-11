/*
 * tstsyn.c - the whole engine path over an EMBEDDED network (D-121, D-122).
 *
 * Decode, integrity-check, big-endian load, simulate, fingerprint -- driven
 * from a network that is part of the program rather than read from a file.
 *
 * ------------------------------------------------------------------------
 * Why a network in the source, and what it is not
 * ------------------------------------------------------------------------
 * tstdec.c and tstgld.c both open a file.  On MVS 3.8j that is a dead end
 * until Gate G2 chooses and proves a binary-transparent transport
 * (IR-TRN-01, IR-TRN-02), so onfdec, the FR-LOD-02 integrity checks and the
 * IR-COM-05 fingerprint had never run on the one platform whose byte order
 * and code page could break them.
 *
 * An embedded image travels through the card reader like any other source.
 * This does NOT stand in for Gate G2 and does not weaken it: what it
 * establishes is that the DECODER is correct on a big-endian EBCDIC host,
 * which is a different question from whether a file can be moved onto one
 * intact.  A real network still cannot reach MVS.
 *
 * generated/onfsynt.h comes from tools/gensyn.py, which serialises the very
 * network tests/run_dec.py uses for TE-01..TE-08 on x86, so the C side, the
 * oracle and the x86 decode tests cannot drift apart.
 *
 * ------------------------------------------------------------------------
 * It carries no expected values
 * ------------------------------------------------------------------------
 * Every number below is computed and printed; tests/run_syn.py recomputes
 * all of them from the Python oracle and decides pass or fail.  A test that
 * carries its own answers can agree with a bug.
 *
 * ------------------------------------------------------------------------
 * Storage
 * ------------------------------------------------------------------------
 * Static arrays sized from the generated header, not malloc.  The image is
 * under a kilobyte, and this way the program needs no heap at all -- which
 * matters on a 24-bit host with a measured 8M region (C-01, TBD-14).
 * FR-SIM-07's ban on allocation applies to the simulation core, which still
 * receives caller-owned storage either way.
 *
 * NR-05: no float or double appears in this file.
 */
#include <stdio.h>

#include "onfcom.h"     /* ONF_MAXOUT, the COMMAREA's output limit (IR-COM) */
#include "onfcrc.h"
#include "onfdec.h"
#include "onffpr.h"
#include "onfker.h"
#include "onfsynt.h"

/* Appendix E return codes (RC column). */
#define RC_OK 0

/* Header field offsets read directly, as tstgld.c does (FR-LOD-05: explicit
   byte shifts, never a pointer cast over the buffer). */
#define OFF_MAXMS 48
#define OFF_PAYCRC 156

static onf_u32 rowptr[ONFSYN_N + 1];
static onf_u32 target[ONFSYN_E];
static onf_f64 weight[ONFSYN_E];
static onf_u32 stim[ONFSYN_NS];
static onf_u32 readout[ONFSYN_NR];

static onf_f64 su[ONFSYN_N], sg[ONFSYN_N];
static onf_f64 sring[ONFSYN_DELAY * ONFSYN_N];
static onf_i32 srfr[ONFSYN_N], sspk[ONFSYN_N];
static onf_i32 sfst[ONFSYN_N], sfrc[ONFSYN_N], sstm[ONFSYN_N];

static onf_i32 oid[ONF_MAXOUT], olat[ONF_MAXOUT], ospk[ONF_MAXOUT];

/* A mutable copy, for the corruption cases.  The image itself is const:
   onfdec's contract says net's array pointers point into the buffer, so the
   buffer must not be modified while a decoded net refers to it.
   The slack is for TE-07's zero padding, which makes the file LONGER. */
#define WORKPAD 80
static onf_u8 work[ONFSYN_LEN + WORKPAD];

/* Header field offsets this file patches, from SRS section 4.1. */
#define OFF_MAGIC 0
#define OFF_SENT 4
#define OFF_VMAJOR 8
#define OFF_REFRACT 44
#define OFF_PAYLEN 152
#define OFF_HDRCRC 160
#define HDRCRC_COVER 160

/* Read a big-endian 32-bit field by explicit shifts (FR-LOD-05). */
static onf_u32 be32(const onf_u8 *p, onf_i32 at)
{
    return ((onf_u32)p[at] << 24) | ((onf_u32)p[at + 1] << 16)
         | ((onf_u32)p[at + 2] << 8) | (onf_u32)p[at + 3];
}

static void put32(onf_u8 *p, onf_i32 at, onf_u32 v)
{
    p[at]     = (onf_u8)((v >> 24) & 0xFFUL);
    p[at + 1] = (onf_u8)((v >> 16) & 0xFFUL);
    p[at + 2] = (onf_u8)((v >> 8) & 0xFFUL);
    p[at + 3] = (onf_u8)(v & 0xFFUL);
}

/* Reset work[] to the good image and return its length. */
static onf_i32 fresh(void)
{
    onf_i32 i;

    for (i = 0; i < (onf_i32)ONFSYN_LEN; i++) {
        work[i] = onfsynt[i];
    }
    return (onf_i32)ONFSYN_LEN;
}

/*
 * Recompute the header CRC over bytes 0..159 and store it at 160
 * (IR-NET-07).
 *
 * Half the integrity cases need this and half must NOT have it, and that
 * split is the whole point.  A field inside the header CRC's coverage
 * cannot be tested on its own by flipping a bit: the header CRC check runs
 * first in FR-LOD-02's order and would catch it, so the case would prove
 * only that something was wrong.  Resealing models a PRODUCER that wrote an
 * inconsistent file; leaving the CRC broken models a TRANSPORT that damaged
 * a good one.  An operator needs to be told which happened -- rebuild the
 * network, or re-send it in binary (NFR-REL-01, R-07).
 */
static void reseal(void)
{
    put32(work, OFF_HDRCRC, onfcrc(work, HDRCRC_COVER, 0UL));
}

/* Decode work[] and print the code that came back. */
static void report(const char *name, onf_i32 len, onf_i32 limit)
{
    struct onfnet net;
    onf_i32 need;
    int rc;

    rc = onfdec(work, len, limit, &net, &need);
    printf("BAD name=%s rc=%d\n", name, rc);
}

int main(void)
{
    struct onfnet net;
    struct onfsta st;
    onf_u32 paycrc;
    onf_i32 need, maxms, q;
    int rc;

    printf("# tstsyn backend=%s platform=%s len=%ld\n",
           ONF_FPID, ONF_PLATID, (long)ONFSYN_LEN);

    /* --- the good image: FR-LOD-02 must accept it --------------------- */
    rc = onfdec(onfsynt, (onf_i32)ONFSYN_LEN, 0, &net, &need);
    printf("DEC rc=%d need=%ld n=%ld e=%ld ns=%ld nr=%ld dtus=%ld\n",
           rc, (long)need, (long)net.n, (long)net.e, (long)net.ns,
           (long)net.nr, (long)net.dtus);
    if (rc != ONFD_OK) {
        return 1;
    }

    /* --- TE-08: FR-LOD-04's limit, checked from header counts before
           anything is allocated.  One byte under the requirement must fail
           and the requirement itself must pass. ------------------------- */
    fresh();
    report("limit", (onf_i32)ONFSYN_LEN, need - 1);
    report("limitok", (onf_i32)ONFSYN_LEN, need);

    /* --- TE-01, TE-02, TE-03: a field inside the header CRC's coverage,
           resealed, so the check being tested is the one that fires ----- */
    fresh();
    work[OFF_MAGIC] = (onf_u8)(work[OFF_MAGIC] ^ 0xFFU);
    reseal();
    report("magic", (onf_i32)ONFSYN_LEN, 0);

    fresh();
    put32(work, OFF_SENT, 0x04030201UL);       /* a text-mode transfer */
    reseal();
    report("sentinel", (onf_i32)ONFSYN_LEN, 0);

    fresh();
    work[OFF_VMAJOR + 1] = (onf_u8)9U;
    reseal();
    report("version", (onf_i32)ONFSYN_LEN, 0);

    /* --- TE-04: the header damaged in transport, CRC deliberately NOT
           repaired.  That is the whole point of this case. -------------- */
    fresh();
    work[OFF_REFRACT + 3] = (onf_u8)(work[OFF_REFRACT + 3] ^ 0xFFU);
    report("hdrcrc", (onf_i32)ONFSYN_LEN, 0);

    /* --- TE-06: a truncated transfer.  The declared length now exceeds
           what the file contains. -------------------------------------- */
    fresh();
    put32(work, OFF_PAYLEN, be32(work, OFF_PAYLEN) + 4096UL);
    reseal();
    report("paylen", (onf_i32)ONFSYN_LEN, 0);

    /* --- TE-05: the payload damaged in transport, header intact ------- */
    fresh();
    work[164 + 40] = (onf_u8)(work[164 + 40] ^ 0xFFU);
    report("paycrc", (onf_i32)ONFSYN_LEN, 0);

    /* --- TE-07: an FB dataset is zero-padded to an 80-byte record
           boundary, so the file is LONGER than the payload.  The engine
           must trust the header's declared length, not the dataset size
           (FR-LOD-03, IR-NET-08).  This is the case that matters most on
           MVS, where every dataset is padded and nowhere else is. ------- */
    {
        onf_i32 len = fresh();
        onf_i32 pad = (80 - (len % 80)) % 80;
        onf_i32 i;

        for (i = 0; i < pad; i++) {
            work[len + i] = (onf_u8)0U;
        }
        report("fbpad", len + pad, 0);
    }

    /* --- load the payload into host order ------------------------------ */
    if (onfldp(onfsynt, &net, rowptr, target, weight, stim, readout)
            != ONFD_OK) {
        printf("LOAD failed\n");
        return 1;
    }

    paycrc = be32(onfsynt, OFF_PAYCRC);
    maxms = (onf_i32)be32(onfsynt, OFF_MAXMS);
    printf("HDR paycrc=%08lX maxms=%ld\n", (unsigned long)paycrc, (long)maxms);

    st.u = su; st.g = sg; st.rfr = srfr; st.spikes = sspk;
    st.first = sfst; st.force = sfrc; st.isstim = sstm; st.ring = sring;

    /* --- the requests, through the same path tstgld.c uses ------------- */
    for (q = 0; q < (onf_i32)ONFSYN_NREQ; q++) {
        onf_i32 stimid = onfsynr[q][0];
        onf_i32 rate = onfsynr[q][1];
        onf_i32 ms = onfsynr[q][2];
        onf_i32 seed = onfsynr[q][3];
        onf_i32 steps, outcount, i;
        onf_u32 fp;

        steps = ms * 1000 / net.dtus;
        if (onfrun(&net, &st, (onf_u32)seed, rate, steps) != ONFK_OK) {
            printf("RUN q=%ld aborted\n", (long)q);
            return 1;
        }
        outcount = net.nr;
        if (outcount > ONF_MAXOUT) {
            outcount = ONF_MAXOUT;
        }
        for (i = 0; i < outcount; i++) {
            onf_i32 nix = (onf_i32)net.readout[i];
            oid[i] = nix;
            olat[i] = st.first[nix];
            ospk[i] = st.spikes[nix];
        }
        fp = onffpr(paycrc, stimid, seed, rate, ms, RC_OK,
                    outcount, steps, oid, olat, ospk);
        printf("SYN q=%ld stimid=%ld rate=%ld ms=%ld seed=%ld out=%ld "
               "steps=%ld fp=%08lX\n",
               (long)q, (long)stimid, (long)rate, (long)ms, (long)seed,
               (long)outcount, (long)steps, (unsigned long)fp);
        for (i = 0; i < outcount; i++) {
            printf("SOUT q=%ld i=%ld id=%ld lat=%ld spk=%ld\n",
                   (long)q, (long)i, (long)oid[i], (long)olat[i],
                   (long)ospk[i]);
        }
    }

    return 0;
}
