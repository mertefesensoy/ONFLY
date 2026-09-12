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
 * The request/response loop is NOT here.  Section 9.2 puts ONFLYDRV, the JCL
 * and the BUZZ demonstration in Phase E, which depends on Phase C and Phase D,
 * and neither is finished.  D-78 therefore builds only what IR-TRN-03 and
 * NFR-OBS-01 name, and a run without PARM='VERIFY' ends with ONF905S and
 * return code 16 rather than quietly succeeding at nothing (NFR-REL-01, D-81).
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
 *    0   the network verified; under VERIFY the step succeeded
 *   12   network integrity failure (ONF101E..ONF108E)
 *   16   environment or self-test failure (ONF901S, ONF905S)
 *
 * Invocation.  argv[1] is the PARM, argv[2] the network dataset.  D-86: when
 * argv[2] is absent the program opens "DD:ONFNET", which is how PDPCLIB names
 * the DD that IR-JCL-01 allocates, so the same source serves the JCL that
 * Phase E will write and the command line this host tests it with.
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
#define RC_INTEG   12
#define RC_ENV     16

/* Appendix E, added by D-85: the dataset could not be read at all. */
#define ONFD_READ 108

/*
 * The largest payload onferead() will allocate for, in bytes.
 *
 * D-147: the declared length is read from a header FR-LOD-02 has not
 * yet validated, so it cannot be handed to malloc unchecked.  64 MB is
 * far above anything ONFLY produces -- the full-brain network is
 * 299 MB but is never loaded whole on MVS, and the MVP path network is
 * 885 KB (data/networks/MANIFEST.json) -- and far below a value that
 * would exhaust a sensible region.  It is a sanity bound, not the
 * memory limit: FR-LOD-04's check against the configured region runs
 * afterwards and is what actually governs.
 */
#define ONF_MAXPAY 67108864L

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

/* The DD name IR-JCL-01 allocates for the network, in PDPCLIB's spelling. */
#define ONF_NETDD "DD:ONFNET"

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

int main(int argc, char **argv)
{
    struct onfnet net;
    const char *parm;
    const char *path;
    onf_u8 *buf;
    onf_i32 len;
    onf_i32 need;
    int verify;
    int rc;
    int self;

    parm = (argc > 1) ? argv[1] : "";
    path = (argc > 2) ? argv[2] : ONF_NETDD;
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

    /* D-78 and D-81: this engine level has no request loop, and NFR-REL-01
       forbids ending a step successfully having done nothing. */
    printf("ONF905S REQUEST PROCESSING NOT BUILT AT THIS ENGINE LEVEL\n");
    free(buf);
    return RC_ENV;
}
