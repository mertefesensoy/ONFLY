/*
 * onfcics.c - the CICS adapter (D-395, P-22 approved by D-396).
 *
 * See engine/include/onfcics.h for the contract and for why the anchor is a
 * handle rather than a file-scope pointer.
 *
 * C89 plus long long (NR-04).  No float, no double, no floating-point literal
 * anywhere in this file (NR-05): onf_f64 values are only ever allocated,
 * passed and freed here, never computed on.  Every multi-byte field that this
 * file reads out of the network header is read by explicit byte shift
 * (FR-LOD-05); the COMMAREA is not decoded here at all -- onfrqg and onfrqp
 * in engine/src/onfreq.c do that, so there is one implementation of the
 * record layout and not two (IR-COM-01, D-224).
 */
#include <stdio.h>
#include <stdlib.h>

#include "onfplat.h"
#include "onfcics.h"
#include "onfdec.h"
#include "onfker.h"
#include "onfnhd.h"
#include "onfreq.h"

/*
 * A network file larger than this is refused before malloc is asked for it.
 * The same reasoning as engine/src/onflyeng.c: the header has not been
 * verified yet at the point the file is read, so its declared length is not
 * yet trustworthy, and an unbounded malloc driven by an unverified number is
 * how a corrupt file becomes a crash rather than a diagnosed rejection.
 */
#define ONFC_MAXFILE 67108864L  /* 64 MB */

/*
 * The anchor.  Everything onfcini obtained, so that onfcend can give it all
 * back and onfcrun can be pure with respect to storage.
 *
 * buf must outlive net: onfdec leaves net's array pointers aimed into it
 * until onfldp re-points them at the host-order copies, and the header
 * scalars are read from buf again in onfcini.
 */
struct onfcic {
    onf_u8 *buf;                /* the network file as read */
    struct onfnet net;
    struct onfsta st;

    /* host-order payload (onfldp) */
    onf_u32 *rowptr;
    onf_u32 *target;
    onf_f64 *weight;
    onf_u32 *stim;
    onf_u32 *readout;
    onf_u32 *brate;
    onf_f64 *bias;

    /* simulation state (struct onfsta's arrays) */
    onf_f64 *su;
    onf_f64 *sg;
    onf_f64 *sring;
    onf_i32 *srfr;
    onf_i32 *sspk;
    onf_i32 *sfst;
    onf_i32 *sfrc;
    onf_i32 *sstm;

    onf_u32 paycrc;             /* IR-COM-05 carries it into the fingerprint */
    onf_i32 maxms;              /* FR-SIM-06 bounds the duration by it */
};

/*
 * onfchdr - one big-endian u32 out of the network header.
 *
 * A private copy of what engine/src/onflyeng.c calls onfehdr, because that
 * one is static to the batch adapter.  Four shifts are not a second
 * implementation of anything: what they read is a fixed offset in a header
 * the CRC has already proved intact, and there is no ordering or arithmetic
 * here that could drift from the other copy.
 */
static onf_u32 onfchdr(const onf_u8 *buf, int off)
{
    return ((onf_u32)buf[off] << 24)
         | ((onf_u32)buf[off + 1] << 16)
         | ((onf_u32)buf[off + 2] << 8)
         | (onf_u32)buf[off + 3];
}

/*
 * onfcrd - read a whole file.
 *
 * Returns the byte count and sets *out, or returns a negative ONFC_* code and
 * leaves *out null.  The caller owns the storage.
 */
static long onfcrd(const char *path, onf_u8 **out)
{
    FILE *f;
    long len;
    onf_u8 *buf;
    size_t got;

    *out = NULL;
    f = fopen(path, "rb");
    if (f == NULL) {
        return ONFC_EFILE;
    }
    if (fseek(f, 0L, SEEK_END) != 0) {
        fclose(f);
        return ONFC_EFILE;
    }
    len = ftell(f);
    rewind(f);
    if (len < (long)ONF_NHDR_LEN || len > ONFC_MAXFILE) {
        fclose(f);
        return ONFC_EFILE;
    }
    buf = (onf_u8 *)malloc((size_t)len);
    if (buf == NULL) {
        fclose(f);
        return ONFC_EMEM;
    }
    got = fread(buf, 1, (size_t)len, f);
    fclose(f);
    if (got != (size_t)len) {
        free(buf);
        return ONFC_EFILE;
    }
    *out = buf;
    return len;
}

/*
 * onfcfre - give back everything an anchor holds, including the anchor.
 *
 * Written so that it is correct on a partly built handle: onfcini calloc's
 * the struct, so every pointer is null until it is set, and free(NULL) is
 * defined.  That is what lets the allocation failure path below be a single
 * goto-free rather than an unwinding ladder.
 */
static void onfcfre(struct onfcic *h)
{
    if (h == NULL) {
        return;
    }
    free(h->rowptr);
    free(h->target);
    free(h->weight);
    free(h->stim);
    free(h->readout);
    free(h->brate);
    free(h->bias);
    free(h->su);
    free(h->sg);
    free(h->sring);
    free(h->srfr);
    free(h->sspk);
    free(h->sfst);
    free(h->sfrc);
    free(h->sstm);
    free(h->buf);
    free(h);
}

struct onfcic *onfcini(const char *netpath, onf_i32 *rc)
{
    struct onfcic *h;
    long len;
    int drc;
    onf_i32 need;

    if (rc != NULL) {
        *rc = ONFC_EARG;
    }
    if (netpath == NULL) {
        return NULL;
    }

    h = (struct onfcic *)calloc((size_t)1, sizeof(struct onfcic));
    if (h == NULL) {
        if (rc != NULL) {
            *rc = ONFC_EMEM;
        }
        return NULL;
    }

    len = onfcrd(netpath, &h->buf);
    if (len < 0L) {
        if (rc != NULL) {
            *rc = (onf_i32)len;
        }
        onfcfre(h);
        return NULL;
    }

    /* FR-LOD-02's ordered checks, and FR-LOD-04's sizing, before anything
       is allocated for the payload.  0 is "no limit": the region's own
       malloc is the limit on this platform, exactly as in the batch
       adapter. */
    drc = onfdec(h->buf, (onf_i32)len, 0, &h->net, &need);
    if (drc != ONFD_OK) {
        if (rc != NULL) {
            *rc = (onf_i32)drc;
        }
        onfcfre(h);
        return NULL;
    }

    h->paycrc = onfchdr(h->buf, ONF_N_PAYCRC);
    h->maxms  = (onf_i32)onfchdr(h->buf, ONF_N_MAXMS);

    h->rowptr  = (onf_u32 *)malloc(sizeof(onf_u32) * (size_t)(h->net.n + 1));
    h->target  = (onf_u32 *)malloc(sizeof(onf_u32) * (size_t)h->net.e);
    h->weight  = (onf_f64 *)malloc(sizeof(onf_f64) * (size_t)h->net.e);
    h->stim    = (onf_u32 *)malloc(sizeof(onf_u32) * (size_t)h->net.ns);
    h->readout = (onf_u32 *)malloc(sizeof(onf_u32) * (size_t)h->net.nr);
    if (h->net.nbias > 0) {
        h->brate = (onf_u32 *)malloc(sizeof(onf_u32)
                                     * (size_t)h->net.nbias);
        h->bias  = (onf_f64 *)malloc(sizeof(onf_f64)
                                     * (size_t)h->net.nbias
                                     * (size_t)h->net.n);
    }
    h->su    = (onf_f64 *)malloc(sizeof(onf_f64) * (size_t)h->net.n);
    h->sg    = (onf_f64 *)malloc(sizeof(onf_f64) * (size_t)h->net.n);
    h->sring = (onf_f64 *)malloc(sizeof(onf_f64) * (size_t)h->net.delay
                                 * (size_t)h->net.n);
    h->srfr  = (onf_i32 *)malloc(sizeof(onf_i32) * (size_t)h->net.n);
    h->sspk  = (onf_i32 *)malloc(sizeof(onf_i32) * (size_t)h->net.n);
    h->sfst  = (onf_i32 *)malloc(sizeof(onf_i32) * (size_t)h->net.n);
    h->sfrc  = (onf_i32 *)malloc(sizeof(onf_i32) * (size_t)h->net.n);
    h->sstm  = (onf_i32 *)malloc(sizeof(onf_i32) * (size_t)h->net.n);

    if (h->rowptr == NULL || h->target == NULL || h->weight == NULL
        || h->stim == NULL || h->readout == NULL
        || h->su == NULL || h->sg == NULL || h->sring == NULL
        || h->srfr == NULL || h->sspk == NULL || h->sfst == NULL
        || h->sfrc == NULL || h->sstm == NULL
        || (h->net.nbias > 0 && (h->brate == NULL || h->bias == NULL))) {
        if (rc != NULL) {
            *rc = ONFC_EMEM;
        }
        onfcfre(h);
        return NULL;
    }

    drc = onfldp(h->buf, &h->net, h->rowptr, h->target, h->weight,
                 h->stim, h->readout, h->brate, h->bias);
    if (drc != ONFD_OK) {
        if (rc != NULL) {
            *rc = (onf_i32)drc;
        }
        onfcfre(h);
        return NULL;
    }

    /* The state arrays are wired once.  The kernel initialises their
       contents itself at the start of every run (FR-SIM-02), which is what
       makes one allocation reusable across every LINK -- and is the property
       ACC-5 rests on: a fingerprint must not depend on what ran before it. */
    h->st.u      = h->su;
    h->st.g      = h->sg;
    h->st.rfr    = h->srfr;
    h->st.spikes = h->sspk;
    h->st.first  = h->sfst;
    h->st.force  = h->sfrc;
    h->st.isstim = h->sstm;
    h->st.ring   = h->sring;

    if (rc != NULL) {
        *rc = (onf_i32)ONFD_OK;
    }
    return h;
}

onf_i32 onfcrun(struct onfcic *h, onf_u8 *ca, onf_i32 len)
{
    struct onfrq q;
    struct onfrz z;

    if (h == NULL || ca == NULL || len != (onf_i32)ONF_RECLEN) {
        return (onf_i32)ONFC_EARG;
    }

    onfrqg(ca, &q);
    onfrq1(&h->net, &h->st, h->paycrc, h->maxms, &q, &z);
    onfrqp(ca, &z);

    return z.rc;
}

void onfcend(struct onfcic *h)
{
    onfcfre(h);
}

onf_i32 onfclen(void)
{
    return (onf_i32)ONF_RECLEN;
}
