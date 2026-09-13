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

/* Largest value an onf_i32 can hold.  Written as a subtraction so the source
   contains no constant that would itself overflow while being parsed. */
#define ONF_I32MAX (2147483646L + 1L)

/*
 * Saturating 32-bit helpers for the memory calculation.
 *
 * NR-04 confines 64-bit integer types to SoftFloat and the float layer, so the
 * decoder cannot simply widen to a 64-bit accumulator; and NR-11 forbids
 * relying on signed overflow.  These check before they compute, and saturate to
 * a sentinel that the caller treats as "does not fit".
 *
 * onfmul returns -1 on overflow, onfadd returns 0 on overflow, so a chain of
 * them short-circuits on the first term that does not fit.
 */
static onf_i32 onfmul(onf_i32 a, onf_i32 b)
{
    if (a < 0 || b < 0) {
        return -1;
    }
    if (a != 0 && b > ONF_I32MAX / a) {
        return -1;
    }
    return a * b;
}

static int onfadd(onf_i32 *acc, onf_i32 term)
{
    if (term < 0 || *acc > ONF_I32MAX - term) {
        return 0;
    }
    *acc += term;
    return 1;
}

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
    onf_i32 n, e, ns, nr, delay, nbias;
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
    nbias = (onf_i32)g32(buf, ONF_N_NBIAS);
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
    /* FR-LOD-04 asks for the memory needed by the decoded network AND the
       simulation state.  Both halves are counted:

         decoded network   rowptr (n+1) u32, targets e u32, weights e binary64
         simulation state  u and g (8 bytes each per neuron), the delay ring
                           (8 bytes per neuron per delay slot), and four int32
                           arrays per neuron

       The network half dominates by an order of magnitude on a real connectome
       -- tens of millions of edges against a few hundred thousand neurons -- so
       omitting it would make the memory gate report a figure far below the true
       requirement and let an oversized network through. On a 24-bit region
       (C-01, NFR-MEM-01) that is the difference between a clean refusal and an
       abend.

       Computed in a 64-bit accumulator and range-checked before narrowing,
       because e * 12 alone overflows a signed 32-bit value once the edge count
       passes about 179 million (NR-11 forbids relying on overflow). */
    if (n < 0 || e < 0 || ns < 0 || nr < 0 || nbias < 0) {
        /* A header count whose u32 value exceeds INT32_MAX arrives here
           negative.  Such a network cannot be addressed on any ONFLY target
           and is refused rather than wrapped into a small positive size. */
        return ONFD_MEM;
    }

    bytes = 0;
    if (!onfadd(&bytes, onfmul(n + 1, 4))          /* rowptr  */
        || !onfadd(&bytes, onfmul(e, 4))           /* target  */
        || !onfadd(&bytes, onfmul(e, 8))           /* weight  */
        || !onfadd(&bytes, onfmul(n, 8))           /* u       */
        || !onfadd(&bytes, onfmul(n, 8))           /* g       */
        || !onfadd(&bytes, onfmul(onfmul(delay, n), 8))   /* ring */
        || !onfadd(&bytes, onfmul(n, 16))          /* rfr/spk/fst/frc */
        || !onfadd(&bytes, onfmul(nbias, 4))       /* bias rates (v1.1) */
        || !onfadd(&bytes, onfmul(onfmul(nbias, n), 8))) {  /* bias rows */
        /* The requirement does not fit in a 32-bit byte count, so it exceeds
           any limit a caller could have configured. */
        if (need != 0) {
            *need = ONF_I32MAX;
        }
        return ONFD_MEM;
    }
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
    net->nbias = nbias;
    net->rowptr = 0;
    net->target = 0;
    net->weight = 0;
    net->stim = 0;
    net->readout = 0;
    net->brate = 0;
    net->bias = 0;

    return ONFD_OK;
}

int onfldp(const onf_u8 *buf, struct onfnet *net,
           onf_u32 *rowptr, onf_u32 *target, onf_f64 *weight,
           onf_u32 *stim, onf_u32 *readout,
           onf_u32 *brate, onf_f64 *bias)
{
    onf_i32 i, j, orow, otgt, owgt, ostm, ordo, obia, orow0, nb;
    onf_u32 prev;

    orow = (onf_i32)g32(buf, ONF_N_OFFROW);
    otgt = (onf_i32)g32(buf, ONF_N_OFFTGT);
    owgt = (onf_i32)g32(buf, ONF_N_OFFWGT);
    ostm = (onf_i32)g32(buf, ONF_N_OFFSTIM);
    ordo = (onf_i32)g32(buf, ONF_N_OFFREAD);
    obia = (onf_i32)g32(buf, ONF_N_OFFBIAS);

    /* IR-NET-05: every section starts on an 8-byte boundary.  A violation
       means the file was not produced by a conforming writer, so refuse it
       rather than reading at an offset the format forbids. */
    if ((orow % ONF_NET_ALIGN) != 0 || (otgt % ONF_NET_ALIGN) != 0
        || (owgt % ONF_NET_ALIGN) != 0 || (ostm % ONF_NET_ALIGN) != 0
        || (ordo % ONF_NET_ALIGN) != 0) {
        return ONFD_PLEN;
    }

    /* CSR row pointers must be non-decreasing, start at 0 and end at e. */
    prev = 0UL;
    for (i = 0; i <= net->n; i++) {
        rowptr[i] = g32(buf, orow + i * 4);
        if (rowptr[i] < prev || (onf_i32)rowptr[i] > net->e) {
            return ONFD_PLEN;
        }
        prev = rowptr[i];
    }
    if (rowptr[0] != 0UL || (onf_i32)rowptr[net->n] != net->e) {
        return ONFD_PLEN;
    }

    /* Targets must lie inside the network and ascend strictly within a row
       (IR-NET-06).  The ascent is normative, not cosmetic: floating-point
       addition does not associate, so a row visited in another order is a
       different answer, and a file that got this wrong would produce results
       that differ between hosts for no visible reason. */
    for (i = 0; i < net->n; i++) {
        onf_i32 k;
        for (k = (onf_i32)rowptr[i]; k < (onf_i32)rowptr[i + 1]; k++) {
            target[k] = g32(buf, otgt + k * 4);
            if ((onf_i32)target[k] >= net->n) {
                return ONFD_PLEN;
            }
            if (k > (onf_i32)rowptr[i] && target[k] <= target[k - 1]) {
                return ONFD_PLEN;
            }
        }
    }

    for (i = 0; i < net->e; i++) {
        weight[i] = gf64(buf, owgt + i * 8);
    }
    for (i = 0; i < net->ns; i++) {
        stim[i] = g32(buf, ostm + i * 4);
        if ((onf_i32)stim[i] >= net->n) {
            return ONFD_PLEN;
        }
    }
    for (i = 0; i < net->nr; i++) {
        readout[i] = g32(buf, ordo + i * 4);
        if ((onf_i32)readout[i] >= net->n) {
            return ONFD_PLEN;
        }
    }

    /* --- v1.1 compensating-input table (D-190, D-191) ------------------
       Laid out as nbias big-endian u32 rates, padded to the 8-byte boundary,
       then nbias rows of n binary64 values.  Three invariants are checked
       here rather than trusted, for the same reason the CSR structure is: a
       correct CRC proves the bytes arrived, not that the producer wrote a
       sane table (VL-08).

       The rate 0 row is checked on the RAW BYTES.  ACC-2 says a rate 0
       request produces zero spikes in every neuron on every platform and
       backend, and that guarantee should not rest on a floating-point
       comparison performed by the very arithmetic under test. */
    nb = net->nbias;
    if (nb > 0) {
        if ((obia % ONF_NET_ALIGN) != 0) {
            return ONFD_PLEN;
        }
        for (i = 0; i < nb; i++) {
            brate[i] = g32(buf, obia + i * 4);
            if (i > 0 && brate[i] <= brate[i - 1]) {
                return ONFD_BIAS;   /* rates not strictly ascending */
            }
        }
        if (brate[0] != 0UL) {
            return ONFD_BIAS;       /* the table must start at rate 0 */
        }
        /* Rates occupy nb * 4 bytes, then padding up to ONF_NET_ALIGN. */
        orow0 = obia + ((nb * 4 + ONF_NET_ALIGN - 1) / ONF_NET_ALIGN)
                * ONF_NET_ALIGN;
        for (j = 0; j < net->n * 8; j++) {
            if (buf[orow0 + j] != (onf_u8)0) {
                return ONFD_BIAS;   /* ACC-2: rate 0 row is not zero */
            }
        }
        for (i = 0; i < nb * net->n; i++) {
            bias[i] = gf64(buf, orow0 + i * 8);
        }
        net->brate = brate;
        net->bias = bias;
    } else {
        net->brate = 0;
        net->bias = 0;
    }

    net->rowptr = rowptr;
    net->target = target;
    net->weight = weight;
    net->stim = stim;
    net->readout = readout;
    return ONFD_OK;
}
