/*
 * onflyeng.c - ONFLYENG, the simulation engine program.
 *
 * This is the minimal engine level of decision D-78.  It does exactly three
 * things, and deliberately not a fourth:
 *
 *   NR-14, D-79   run the integer self-test before anything else, and
 *                 report ONF901S with return code 16 if the compiler's
 *                 synthesized arithmetic is wrong.  D-142 selects the
 *                 WIDTH by backend: 32-bit (TT-01/32) where NR-03's
 *                 fallback to SoftFloat 2c is in force and the engine
 *                 uses no 64-bit integer, 64-bit (TT-01) otherwise
 *   FR-LOD-01..05 read the network dataset and verify it, in the order
 *                 FR-LOD-02 fixes, reporting the first failing check
 *   NFR-OBS-01    print the run manifest to SYSPRINT before any work
 *   IR-TRN-03     under PARM='VERIFY', stop there and report ONF003I
 *
 *   FR-BAT-01     STEP2: read ONFREQ, run each request, write ONFRSP, and
 *                 set the step return code of IR-JCL-04
 *
 * The request/response loop was NOT here until D-221.  Section 9.2 places
 * ONFLYDRV, the JCL and the BUZZ demonstration in Phase E, so D-78 built only
 * what IR-TRN-03 and NFR-OBS-01 name and a run without PARM='VERIFY' ended
 * with ONF905S (NFR-REL-01, D-81).  Phase D needed TX-01 to compare real
 * response records between x86 and s390x, and no build on any platform
 * produced one, so the owner authorised bringing STEP2 forward (D-221).
 * ONFLYDRV, the JCL and the report remain Phase E.
 *
 * ------------------------------------------------------------------------
 * Why verify-only is worth its own mode
 * ------------------------------------------------------------------------
 * IR-TRN-02 asks Spike S2 to run at least ten transfers per transport method
 * and check each one.  Without this mode, checking a transferred file means
 * running a simulation to find out whether the bytes survived, which on TK5
 * costs minutes per attempt.  With it, the check is the load path alone:
 * magic, sentinel, version, header CRC, declared length, payload CRC (P-06).
 *
 * ------------------------------------------------------------------------
 * Return codes, from IR-JCL-04
 * ------------------------------------------------------------------------
 *    0   the network verified; under VERIFY the step succeeded, and in
 *        SIMULATE mode every request succeeded
 *    4   at least one request warned (ONF201W)
 *    8   at least one request was rejected (ONF202E, ONF203E)
 *   12   network integrity failure (ONF101E..ONF109E)
 *   16   environment or self-test failure (ONF901S, ONF903S, ONF906S)
 *
 * Invocation.  argv[1] is the PARM, argv[2] the network dataset, argv[3] the
 * request dataset and argv[4] the response dataset (D-223).  D-86: when an
 * argument is absent the program opens the corresponding "DD:" name, which is
 * how PDPCLIB spells the DDs IR-JCL-01 allocates, so the same source serves
 * the JCL that Phase E will write and the command line this host tests it
 * with.  FR-LNX-01's "ordinary files" are exactly those positional arguments.
 *
 * NR-05: no floating-point type and no floating-point literal appears here.
 * The manifest reports binary64 header values as their bit patterns, which is
 * what the onf_fp API carries and what a reader can compare exactly.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "onfplat.h"
#include "onfdec.h"
#include "onfker.h"
#include "onffp.h"
#include "onfnhd.h"
#include "onfreq.h"   /* D-221, D-224: the request/response loop */
/* D-142: only the width this platform's engine actually uses is
   compiled in.  On a 2c platform the 64-bit header must not be
   included at all -- VL-45 measured GCCMVS unable to compile its
   implementation, so linking it is not an option there. */
#ifdef ONF_FP_SOFT2C
#include "onfi32.h"
#else
#include "onfint.h"
#endif

/* IR-JCL-04 return codes. */
#define RC_OK       0
#define RC_WARN     4
#define RC_REQ      8
#define RC_INTEG   12
#define RC_ENV     16

/* Appendix E, added by D-85: the dataset could not be read at all. */
#define ONFD_READ 108

/*
 * Appendix E codes this program prints that are not load failures.
 *
 * They are numbered here rather than in onfdec.h because they belong to the
 * request loop, not to the decoder: onfdec.h's ONFD_* values double as its
 * return codes, and a request-level code has no meaning there.
 */
#define ONFM_RSVD 201           /* ONF201W, FR-BAT-05 */
#define ONFM_FLD  202           /* ONF202E */
#define ONFM_CODE 203           /* ONF203E */
#define ONFM_NFIN 903           /* ONF903S, FR-SIM-08 */
#define ONFM_RQDS 906           /* ONF906S, D-226 */

/*
 * ONF_MAXPAY, the largest payload onferead() will allocate for, moved to
 * engine/include/onfplat.h by D-231 and is platform-dependent there.
 *
 * D-147 set it at 64 MB on the reasoning that the declared length is read
 * from a header FR-LOD-02 has not yet validated, so it cannot be handed to
 * malloc unchecked.  That reasoning is unchanged and 64 MB still applies on
 * MVS.  It moved because D-216 requires the full MaleCNS network -- about a
 * 299 MB payload -- to be read on x86 and s390x, where the bound refused it
 * outright, and because NFR-PRT-01 makes onfplat.h the only file allowed to
 * vary by platform.
 */

/*
 * Engine version.  Reported by the manifest so that a recorded result names
 * the engine that produced it (NFR-OBS-01).  Bumped by hand, deliberately:
 * it identifies a build of the engine, not of the network format.
 */
#define ONF_ENGVER "0.5.0"

/*
 * Compiler identification for the manifest.
 *
 * NFR-OBS-01 requires it because the same source produces different object
 * code under GCCMVS, JCC, gcc and clang, and assumption A-05 says the 64-bit
 * arithmetic of at least one of them is unproven.  A result that does not name
 * its compiler cannot be compared with another.
 */
#if defined(__GNUC__)
#define ONF_CCID "GCC"
#elif defined(__IBMC__)
#define ONF_CCID "IBMC"
#elif defined(__CMS__) || defined(__MVS__)
#define ONF_CCID "MVSC"
#else
#define ONF_CCID "UNKNOWN"
#endif

/* The DD names IR-JCL-01 allocates, in PDPCLIB's spelling (D-86, D-223). */
#define ONF_NETDD "DD:ONFNET"
#define ONF_REQDD "DD:ONFREQ"
#define ONF_RSPDD "DD:ONFRSP"

/*
 * Map a decoder result to its Appendix E message text.  The decoder's result
 * codes are the message numbers themselves, so the two cannot fall out of step
 * with each other.
 */
static const char *onfemsg(int rc)
{
    switch (rc) {
    case ONFD_MAGIC: return "MAGIC CONSTANT MISMATCH";
    case ONFD_SENT:  return "BYTE-ORDER SENTINEL MISMATCH";
    case ONFD_VER:   return "UNSUPPORTED FORMAT VERSION";
    case ONFD_HCRC:  return "HEADER CRC MISMATCH";
    case ONFD_MEM:   return "NETWORK EXCEEDS MEMORY LIMIT";
    case ONFD_PLEN:  return "PAYLOAD LENGTH INCONSISTENT";
    case ONFD_PCRC:  return "PAYLOAD CRC MISMATCH";
    case ONFD_READ:  return "NETWORK DATASET UNREADABLE";
    case ONFD_BIAS:  return "COMPENSATION TABLE INVALID";
    case ONFM_RSVD:  return "STIMULUS CODE RESERVED, NOT SIMULATED";
    case ONFM_FLD:   return "REQUEST FIELD OUT OF RANGE";
    case ONFM_CODE:  return "UNKNOWN STIMULUS CODE";
    case ONFM_NFIN:  return "NON-FINITE STATE VALUE, REQUEST ABORTED";
    case ONFM_RQDS:  return "REQUEST DATASET UNREADABLE OR NOT A "
                            "MULTIPLE OF 412";
    default:         return "UNKNOWN LOAD FAILURE";
    }
}

/* Read a u32 from the raw header by explicit byte shifts (FR-LOD-05). */
static onf_u32 onfehdr(const onf_u8 *buf, int off)
{
    onf_u32 v;

    v =  (onf_u32)buf[off]     << 24;
    v |= (onf_u32)buf[off + 1] << 16;
    v |= (onf_u32)buf[off + 2] << 8;
    v |= (onf_u32)buf[off + 3];
    return v;
}

static onf_u32 onfehd16(const onf_u8 *buf, int off)
{
    onf_u32 v;

    v =  (onf_u32)buf[off] << 8;
    v |= (onf_u32)buf[off + 1];
    return v;
}

/*
 * Does the PARM ask for verify-only mode?
 *
 * MVS delivers PARM text in the job's own case, and an operator who types
 * PARM='verify' means the same thing as one who types PARM='VERIFY', so the
 * comparison is case-insensitive.  Written out rather than using strcasecmp,
 * which is neither C89 nor provided by PDPCLIB (C-06).
 */
static int onfeisv(const char *parm)
{
    static const char want[] = "VERIFY";
    int i;
    char c;

    if (parm == NULL) {
        return 0;
    }
    for (i = 0; i < 6; i++) {
        c = parm[i];
        if (c >= 'a' && c <= 'z') {
            c = (char)(c - 'a' + 'A');
        }
        if (c != want[i]) {
            return 0;
        }
    }
    return parm[6] == '\0';
}

/*
 * NFR-OBS-01: the run manifest.
 *
 * Everything the requirement names, and nothing that would differ between two
 * runs of the same build on the same network, so two manifests can be compared
 * line by line.  Binary64 header values are printed as their 16 hexadecimal
 * digits: NR-05 forbids this program from holding a binary64 as a number, and
 * a bit pattern is in any case the only form in which two platforms can be
 * compared exactly.
 */
static void onfemft(const onf_u8 *buf, const struct onfnet *net,
                    onf_i32 len, onf_i32 need, int verify)
{
    printf("ONF002I RUN MANIFEST\n");
    printf("ONF002I   ENGINE VERSION  %s\n", ONF_ENGVER);
    printf("ONF002I   FLOAT BACKEND   %s\n", ONF_FPID);
    printf("ONF002I   COMPILER        %s\n", ONF_CCID);
    printf("ONF002I   PLATFORM        %s\n", ONF_PLATID);
    printf("ONF002I   MODE            %s\n", verify ? "VERIFY" : "SIMULATE");
    printf("ONF002I   NET FORMAT      %lu.%lu\n",
           (unsigned long)onfehd16(buf, ONF_N_VMAJOR),
           (unsigned long)onfehd16(buf, ONF_N_VMINOR));
    printf("ONF002I   HEADER CRC      %08lX\n",
           (unsigned long)onfehdr(buf, ONF_N_HDRCRC));
    printf("ONF002I   PAYLOAD CRC     %08lX\n",
           (unsigned long)onfehdr(buf, ONF_N_PAYCRC));
    printf("ONF002I   N               %ld\n", (long)net->n);
    printf("ONF002I   E               %ld\n", (long)net->e);
    printf("ONF002I   NS NR           %ld %ld\n",
           (long)net->ns, (long)net->nr);
    printf("ONF002I   DT              %ld US\n", (long)net->dtus);
    printf("ONF002I   DT BITS         %08lX%08lX\n",
           (unsigned long)onfehdr(buf, ONF_N_DT),
           (unsigned long)onfehdr(buf, ONF_N_DT + 4));
    printf("ONF002I   DELAY REFRACT   %ld %ld STEPS\n",
           (long)net->delay, (long)net->refract);
    /* v1.1 (D-190): how many compensating-input rows this network carries.
       0 means none, which is what the full brain and every uncompensated
       network carry.  It belongs in the manifest for the same reason the
       float backend does (NFR-OBS-01): a run whose numbers differ from
       another's must be able to say, on its own face, what it was running. */
    printf("ONF002I   BIAS ROWS       %ld\n", (long)net->nbias);
    printf("ONF002I   BYTES NEED      %ld %ld\n", (long)len, (long)need);
}

/*
 * Read the whole dataset.
 *
 * FR-LOD-03 and IR-NET-08: an FB dataset is padded to a record boundary, so
 * what is read here is at least the payload and usually more.  The size is
 * passed to onfdec only as the bound on what is available; the header's
 * declared length is what onfdec trusts.
 *
 * On success *out holds a buffer the caller frees and the return value is its
 * length.  On failure the return value is negative.
 */
static onf_i32 onferead(const char *path, onf_u8 **out)
{
    FILE *f;
    onf_u8 *buf;
    onf_i32 len;
    long size;

    *out = NULL;
    f = fopen(path, "rb");
    if (f == NULL) {
        return -1;
    }

    /*
     * D-147, FR-LOD-03: the header's declared length governs the read,
     * not the dataset's size.  The previous version began with
     * fseek(SEEK_END) and ftell, which is the dataset size and is
     * exactly what the requirement forbids.  It also cannot work at
     * all on a device that does not seek: VL-52 measured the card
     * reader deliver all 11,068 cards of the network and ONFLYENG
     * reject it with ONF108E before a single header check ran, because
     * the very first statement failed.  A seekable dataset hides the
     * difference, which is how it survived this long.
     *
     * So: read the fixed-size header, take the payload length from it,
     * then read exactly that many more bytes.
     */
    buf = (onf_u8 *)malloc((size_t)ONF_NHDR_LEN);
    if (buf == NULL) {
        fclose(f);
        return -1;
    }
    len = (onf_i32)fread(buf, 1, (size_t)ONF_NHDR_LEN, f);
    if (len != (onf_i32)ONF_NHDR_LEN) {
        free(buf);
        fclose(f);
        return -1;
    }

    /*
     * This length comes from a header FR-LOD-02 has NOT yet checked, so
     * it is not to be trusted with malloc.  Bounding it here keeps a
     * corrupt or hostile header from asking for an absurd allocation
     * before the integrity checks get their turn; a value that passes
     * this bound but is still wrong is caught by the declared-length
     * and payload-CRC checks, which is where it belongs.
     */
    size = (long)onfehdr(buf, ONF_N_PAYLEN);
    if (size < 0 || size > ONF_MAXPAY) {
        free(buf);
        fclose(f);
        return -1;
    }

    {
        onf_u8 *whole = (onf_u8 *)realloc(buf,
                                          (size_t)ONF_NHDR_LEN
                                          + (size_t)size);
        if (whole == NULL) {
            free(buf);
            fclose(f);
            return -1;
        }
        buf = whole;
    }

    /*
     * A SHORT READ IS NOT AN UNREADABLE DATASET, and treating it as one
     * is a regression TE-06 caught.  If the header declares more
     * payload than actually arrives, that is precisely the
     * inconsistency FR-LOD-02's fifth check exists to report, as
     * ONF106E.  Returning -1 here would report ONF108E instead and
     * describe a truncated file as an I/O failure -- losing the
     * distinction between "the dataset could not be read" and "the
     * dataset disagrees with its own header", which are different
     * findings with different causes.
     *
     * So whatever arrived is returned, and the decoder compares it
     * against the declared length.
     */
    len = 0;
    if (size > 0) {
        len = (onf_i32)fread(buf + ONF_NHDR_LEN, 1, (size_t)size, f);
        if (len < 0) {
            len = 0;
        }
    }
    fclose(f);

    *out = buf;
    return (onf_i32)ONF_NHDR_LEN + len;
}

#ifndef ONF_NOREQ
/*
 * onfefld - the field name ONF202E prints (Appendix E).
 *
 * The COBOL field names of Section 4.3 are used rather than C identifiers,
 * because the operator reading SYSPRINT is looking at a control card and a
 * copybook, not at this source.
 */
static const char *onfefld(onf_i32 bad)
{
    if (bad == ONFR_F_RATE) {
        return "ONF-STIM-RATE";
    }
    if (bad == ONFR_F_MS) {
        return "ONF-SIM-MS";
    }
    if (bad == ONFR_F_CODE) {
        return "ONF-STIM-CODE";
    }
    return "UNKNOWN";
}

/*
 * onferun - FR-BAT-01 STEP2: every request in ONFREQ, into ONFRSP.
 *
 * ------------------------------------------------------------------------
 * Why the records are streamed one at a time
 * ------------------------------------------------------------------------
 * A request record is 412 bytes and the response is the same record with its
 * response portion filled in (IR-JCL-03), so there is never a reason to hold
 * more than one.  On MVS that matters: C-01 gives the region single-digit
 * megabytes and the network already consumes most of it, so a design that
 * read the whole request dataset first would work on x86 and fail on the
 * platform the MVP targets.  Streaming also means ONFRSP is written in step
 * with ONFREQ, which is what makes the two files record-for-record aligned
 * for the report step.
 *
 * ------------------------------------------------------------------------
 * Return code
 * ------------------------------------------------------------------------
 * IR-JCL-04: 0 if every request succeeded, 4 if any warned, 8 if any was
 * rejected, 16 for an environment failure.  The worst outcome wins, and
 * every request is attempted regardless -- a rejected request must not
 * suppress the ones after it, because FR-BAT-04's report shows all of them.
 */
static int onferun(const onf_u8 *buf, struct onfnet *net,
                   const char *reqpath, const char *rsppath)
{
    onf_u32 *rowptr, *target, *stim, *readout, *brate;
    onf_f64 *weight, *su, *sg, *sring, *bias;
    onf_i32 *srfr, *sspk, *sfst, *sfrc, *sstm;
    struct onfsta st;
    struct onfrq rq;
    struct onfrz rz;
    onf_u8 rec[ONF_RECLEN];
    FILE *fq;
    FILE *fs;
    onf_u32 paycrc;
    onf_i32 maxms;
    long qlen, nreq, k;
    int step, nok, nwarn, nerr, rc;

    paycrc = onfehdr(buf, ONF_N_PAYCRC);
    maxms  = (onf_i32)onfehdr(buf, ONF_N_MAXMS);

    /* --- the request dataset, checked before anything is allocated ------ */
    fq = fopen(reqpath, "rb");
    if (fq == NULL) {
        printf("ONF906S %s: %s\n", onfemsg(ONFM_RQDS), reqpath);
        return RC_ENV;
    }
    if (fseek(fq, 0L, SEEK_END) != 0) {
        fclose(fq);
        printf("ONF906S %s: %s\n", onfemsg(ONFM_RQDS), reqpath);
        return RC_ENV;
    }
    qlen = ftell(fq);
    rewind(fq);
    if (qlen <= 0 || (qlen % (long)ONF_RECLEN) != 0) {
        fclose(fq);
        printf("ONF906S %s: %s (%ld BYTES)\n",
               onfemsg(ONFM_RQDS), reqpath, qlen);
        return RC_ENV;
    }
    nreq = qlen / (long)ONF_RECLEN;

    fs = fopen(rsppath, "wb");
    if (fs == NULL) {
        fclose(fq);
        printf("ONF906S %s: %s\n", onfemsg(ONFM_RQDS), rsppath);
        return RC_ENV;
    }

    /* --- the payload, in host order (FR-LOD-05 via onfldp) -------------- */
    rowptr  = (onf_u32 *)malloc(sizeof(onf_u32) * (size_t)(net->n + 1));
    target  = (onf_u32 *)malloc(sizeof(onf_u32) * (size_t)net->e);
    weight  = (onf_f64 *)malloc(sizeof(onf_f64) * (size_t)net->e);
    stim    = (onf_u32 *)malloc(sizeof(onf_u32) * (size_t)net->ns);
    readout = (onf_u32 *)malloc(sizeof(onf_u32) * (size_t)net->nr);
    brate = NULL;
    bias = NULL;
    if (net->nbias > 0) {
        brate = (onf_u32 *)malloc(sizeof(onf_u32) * (size_t)net->nbias);
        bias  = (onf_f64 *)malloc(sizeof(onf_f64)
                                  * (size_t)net->nbias * (size_t)net->n);
    }
    su    = (onf_f64 *)malloc(sizeof(onf_f64) * (size_t)net->n);
    sg    = (onf_f64 *)malloc(sizeof(onf_f64) * (size_t)net->n);
    sring = (onf_f64 *)malloc(sizeof(onf_f64) * (size_t)net->delay
                              * (size_t)net->n);
    srfr  = (onf_i32 *)malloc(sizeof(onf_i32) * (size_t)net->n);
    sspk  = (onf_i32 *)malloc(sizeof(onf_i32) * (size_t)net->n);
    sfst  = (onf_i32 *)malloc(sizeof(onf_i32) * (size_t)net->n);
    sfrc  = (onf_i32 *)malloc(sizeof(onf_i32) * (size_t)net->n);
    sstm  = (onf_i32 *)malloc(sizeof(onf_i32) * (size_t)net->n);

    if (rowptr == NULL || target == NULL || weight == NULL || stim == NULL
        || readout == NULL || su == NULL || sg == NULL || sring == NULL
        || srfr == NULL || sspk == NULL || sfst == NULL || sfrc == NULL
        || sstm == NULL || (net->nbias > 0 && (brate == NULL
                                               || bias == NULL))) {
        /* FR-LOD-04's limit check has already passed, so a failure here is
           the region actually running out rather than a network too large
           to have been accepted. */
        printf("ONF105E %s\n", onfemsg(ONFD_MEM));
        fclose(fq);
        fclose(fs);
        return RC_INTEG;
    }

    rc = onfldp(buf, net, rowptr, target, weight, stim, readout,
                brate, bias);
    if (rc != ONFD_OK) {
        printf("ONF%03dE %s\n", rc, onfemsg(rc));
        fclose(fq);
        fclose(fs);
        return RC_INTEG;
    }

    st.u = su; st.g = sg; st.rfr = srfr; st.spikes = sspk;
    st.first = sfst; st.force = sfrc; st.isstim = sstm; st.ring = sring;

    /* --- the loop ------------------------------------------------------- */
    step = RC_OK;
    nok = 0;
    nwarn = 0;
    nerr = 0;
    for (k = 0; k < nreq; k++) {
        if (fread(rec, 1, (size_t)ONF_RECLEN, fq)
            != (size_t)ONF_RECLEN) {
            printf("ONF906S %s: %s\n", onfemsg(ONFM_RQDS), reqpath);
            fclose(fq);
            fclose(fs);
            return RC_ENV;
        }

        onfrqg(rec, &rq);
        onfrq1(net, &st, paycrc, maxms, &rq, &rz);
        onfrqp(rec, &rz);

        if (rz.rc == ONFR_OK) {
            nok++;
            printf("ONF301I REQUEST %ld COMPLETE FP=%08lX\n",
                   k + 1, (unsigned long)rz.fp);
        } else if (rz.rc == ONFR_WARN) {
            nwarn++;
            printf("ONF201W %s\n", onfemsg(ONFM_RSVD));
            if (step < RC_WARN) {
                step = RC_WARN;
            }
        } else if (rz.rc == ONFR_SEV) {
            nerr++;
            printf("ONF903S %s\n", onfemsg(ONFM_NFIN));
            step = RC_ENV;
        } else if (rq.stimid == ONF_STIM_UNKNOWN) {
            nerr++;
            printf("ONF203E %s\n", onfemsg(ONFM_CODE));
            if (step < RC_REQ) {
                step = RC_REQ;
            }
        } else {
            nerr++;
            printf("ONF202E %s: %s\n", onfemsg(ONFM_FLD), onfefld(rz.bad));
            if (step < RC_REQ) {
                step = RC_REQ;
            }
        }

        if (fwrite(rec, 1, (size_t)ONF_RECLEN, fs)
            != (size_t)ONF_RECLEN) {
            printf("ONF906S %s: %s\n", onfemsg(ONFM_RQDS), rsppath);
            fclose(fq);
            fclose(fs);
            return RC_ENV;
        }
    }

    printf("ONF302I STEP SUMMARY: %d OK, %d WARN, %d ERROR\n",
           nok, nwarn, nerr);

    if (fclose(fs) != 0) {
        printf("ONF906S %s: %s\n", onfemsg(ONFM_RQDS), rsppath);
        return RC_ENV;
    }
    fclose(fq);
    return step;
}
#endif /* ONF_NOREQ */

int main(int argc, char **argv)
{
    struct onfnet net;
    const char *parm;
    const char *path;
    const char *reqpath;
    const char *rsppath;
    onf_u8 *buf;
    onf_i32 len;
    onf_i32 need;
    int verify;
    int rc;
    int self;

    parm = (argc > 1) ? argv[1] : "";
    path = (argc > 2) ? argv[2] : ONF_NETDD;
    reqpath = (argc > 3) ? argv[3] : ONF_REQDD;
    rsppath = (argc > 4) ? argv[4] : ONF_RSPDD;
    verify = onfeisv(parm);

    /*
     * NR-14 and Section 8.1: level L0 passes before anything above it runs.
     * If the compiler's integer arithmetic is wrong, every number this
     * program could go on to produce would be wrong too, and quietly so.
     *
     * D-142: NR-14, as D-118 amended it, requires the self-test "for each
     * integer width that platform's engine actually uses".  Where NR-03's
     * fallback to SoftFloat 2c is in force the engine uses no 64-bit
     * integer anywhere, so the width that matters is 32 bits (TT-01/32)
     * and the 64-bit suite is not merely redundant there -- VL-45 measured
     * GCCMVS unable to compile it at any optimisation level, so it must not
     * even be linked.  The two widths keep separate names so that a reader
     * of a passing run can tell which one was actually proven.
     */
#ifdef ONF_FP_SOFT2C
    self = onf32ts();
    if (self != 0) {
        printf("ONF901S 32-BIT INTEGER SELF-TEST FAILED: %s VECTOR %d\n",
               onf32nm(self / 1000), (self % 1000) - 1);
        return RC_ENV;
    }
#else
    self = onfitst();
    if (self != 0) {
        printf("ONF901S 64-BIT INTEGER SELF-TEST FAILED: %s VECTOR %d\n",
               onfignm(self / 1000), (self % 1000) - 1);
        return RC_ENV;
    }
#endif

    len = onferead(path, &buf);
    if (len < 0) {
        printf("ONF108E %s: %s\n", onfemsg(ONFD_READ), path);
        return RC_INTEG;
    }

    /*
     * FR-LOD-04 requires the memory check to happen before allocation, from
     * the header counts.  A limit of 0 means unlimited: TBD-14 has not yet
     * fixed the TK5 region, so imposing a number here would be inventing one.
     */
    need = 0;
    rc = onfdec(buf, len, 0, &net, &need);
    if (rc != ONFD_OK) {
        printf("ONF%03dE %s\n", rc, onfemsg(rc));
        free(buf);
        return RC_INTEG;
    }

    printf("ONF001I NETWORK LOADED N=%ld E=%ld CRC=%08lX\n",
           (long)net.n, (long)net.e,
           (unsigned long)onfehdr(buf, ONF_N_PAYCRC));
    onfemft(buf, &net, len, need, verify);

    if (verify) {
        /* IR-TRN-03: report and stop.  No payload conversion, no simulation,
           and above all no allocation proportional to E, which is what makes
           this cheap enough to run after every transport attempt (P-06). */
        printf("ONF003I VERIFY-ONLY: NETWORK OK\n");
        free(buf);
        return RC_OK;
    }

    /* FR-BAT-01 STEP2.  D-221 brought this forward from Phase E so that
       TX-01 has real response records to compare across platforms; before
       that, D-78 and D-81 ended here with ONF905S, which D-227 keeps in
       Appendix E as a historical entry no current build can emit. */
#ifdef ONF_NOREQ
    /* D-228: TE-09's structural half.  Built with the request loop compiled
       out, so that `nm` can still prove onfrun absent -- the argument D-221
       destroyed for the shipped engine.  This is the one build that can
       still emit ONF905S (D-227), which is why that message is tested
       rather than merely documented. */
    (void)reqpath;
    (void)rsppath;
    printf("ONF905S REQUEST PROCESSING NOT BUILT AT THIS ENGINE LEVEL\n");
    free(buf);
    return RC_ENV;
#else
    rc = onferun(buf, &net, reqpath, rsppath);
    free(buf);
    return rc;
#endif
}
