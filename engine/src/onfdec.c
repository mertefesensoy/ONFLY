/*
 * onfdec.c - network file integrity checks and decode (FR-LOD-01..05).
 *
 * NR-05: no float or double appears here.  binary64 values are lifted straight
 * out of the file as bit patterns and handed to onffbit; nothing in this file
 * can perform arithmetic on them.
 */
#include "onfdec.h"
#include "onfcrc.h"
#include "onffp.h"
#include "onfnhd.h"

/* Read a big-endian unsigned 32-bit field by explicit shifts (FR-LOD-05). */
static onf_u32 g32(const onf_u8 *b, onf_i32 o)
{
    onf_u32 v;

    v  = (onf_u32)b[o]     << 24;
    v |= (onf_u32)b[o + 1] << 16;
    v |= (onf_u32)b[o + 2] <<  8;
    v |= (onf_u32)b[o + 3];
    return v;
}

static onf_u32 g16(const onf_u8 *b, onf_i32 o)
{
    onf_u32 v;

    v  = (onf_u32)b[o] << 8;
    v |= (onf_u32)b[o + 1];
    return v;
}

/* Read a big-endian binary64 field as its two 32-bit halves. */
static onf_f64 gf64(const onf_u8 *b, onf_i32 o)
{
    return onffbit(g32(b, o), g32(b, o + 4));
}

int onfdec(const onf_u8 *buf, onf_i32 len, onf_i32 limit,
           struct onfnet *net, onf_i32 *need)
{
    onf_u32 paylen, paycrc, hdrcrc;
    onf_i32 n, e, ns, nr, delay;
    onf_i32 bytes;

    if (need != 0) {
        *need = 0;
    }

    /* The file must at least contain a header before any field is read.  This
       is not one of FR-LOD-02's six checks; it is the precondition that makes
       reading them safe at all.  A file this short cannot carry a valid magic
       either, so reporting ONF101E is both true and actionable. */
    if (len < ONF_NHDR_LEN) {
        return ONFD_MAGIC;
    }

    /* --- FR-LOD-02 check 1: magic (IR-NET-03) --------------------------- */
    if (g32(buf, ONF_N_MAGIC) != ONF_NET_MAGIC) {
        return ONFD_MAGIC;
    }

    /* --- check 2: byte-order sentinel (IR-NET-04) -----------------------
       This is the check that catches a text-mode transfer, an EBCDIC
       translation, or a byte-swapped transport, and says so specifically. */
    if (g32(buf, ONF_N_SENTINEL) != ONF_NET_SENTINEL) {
        return ONFD_SENT;
    }

    /* --- check 3: format version ---------------------------------------- */
    if (g16(buf, ONF_N_VMAJOR) != (onf_u32)ONF_NET_VMAJOR
        || g16(buf, ONF_N_VMINOR) != (onf_u32)ONF_NET_VMINOR) {
        return ONFD_VER;
    }

    /* --- check 4: header CRC over bytes 0..ONF_NHDR_CRCLEN-1 (IR-NET-07) - */
    hdrcrc = g32(buf, ONF_N_HDRCRC);
    if (onfcrc(buf, ONF_NHDR_CRCLEN, 0UL) != hdrcrc) {
        return ONFD_HCRC;
    }

    /* Header is trustworthy from here on, so its counts may be used. */
    n     = (onf_i32)g32(buf, ONF_N_N);
    e     = (onf_i32)g32(buf, ONF_N_E);
    ns    = (onf_i32)g32(buf, ONF_N_NS);
    nr    = (onf_i32)g32(buf, ONF_N_NR);
    delay = (onf_i32)g32(buf, ONF_N_DELAY);
    paylen = g32(buf, ONF_N_PAYLEN);

    /* --- check 5: declared payload length (FR-LOD-03, IR-NET-08) --------
       The header's declared length is authoritative; the dataset is padded to
       an 80-byte record boundary on MVS, so its size is nearly always larger.
       A file SHORTER than the declaration is a truncated transfer. */
    if ((onf_i32)paylen < 0
        || (onf_i32)paylen > len - ONF_NHDR_LEN) {
        return ONFD_PLEN;
    }

    /* --- FR-LOD-04: memory budget, computed from header counts BEFORE any
       allocation.  Checked here rather than after the payload CRC so that an
       oversized network is rejected without first checksumming megabytes of
       it.  This sits between two of FR-LOD-02's checks but does not reorder
       them relative to one another. -------------------------------------- */
    if (delay < 1) {
        return ONFD_PLEN;       /* Appendix C requires D >= 1 */
    }
    /* Decoded network plus simulation state: u and g (8 bytes each), the ring
       (8 bytes per neuron per delay slot), and four int32 arrays per neuron. */
    bytes = n * 8 + n * 8 + delay * n * 8 + n * 4 * 4;
    if (need != 0) {
        *need = bytes;
    }
    if (limit > 0 && bytes > limit) {
        return ONFD_MEM;
    }

    /* --- check 6: payload CRC over exactly the declared length ---------- */
    paycrc = g32(buf, ONF_N_PAYCRC);
    if (onfcrc(buf + ONF_NHDR_LEN, (onf_i32)paylen, 0UL) != paycrc) {
        return ONFD_PCRC;
    }

    /* --- decode ---------------------------------------------------------
       Section pointers are absolute file offsets.  The arrays are big-endian
       u32 and binary64 in the file; on a big-endian host they could be used in
       place, but the kernel is handed onf_u32/onf_f64 arrays, so the caller
       converts.  Here only the scalar header fields are lifted. */
    net->n = n;
    net->e = e;
    net->ns = ns;
    net->nr = nr;
    net->dtus = (onf_i32)g32(buf, ONF_N_DTUS);
    net->delay = delay;
    net->refract = (onf_i32)g32(buf, ONF_N_REFRACT);
    net->uth = gf64(buf, ONF_N_UTH);
    net->ureset = gf64(buf, ONF_N_URESET);
    net->p11 = gf64(buf, ONF_N_P11);
    net->p12 = gf64(buf, ONF_N_P12);
    net->p22 = gf64(buf, ONF_N_P22);
    net->geps = gf64(buf, ONF_N_GEPS);

    /* Array pointers are left null: the payload is big-endian and the kernel
       needs host-order onf_u32 and onf_f64 arrays, so the caller performs that
       conversion into its own storage.  Leaving them null rather than pointing
       at raw file bytes means a caller that forgets to convert crashes
       immediately instead of simulating byte-swapped nonsense. */
    net->rowptr = 0;
    net->target = 0;
    net->weight = 0;
    net->stim = 0;
    net->readout = 0;

    return ONFD_OK;
}
