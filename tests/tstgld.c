/*
 * tstgld.c - the golden request suite (SRS section 8.4, ACC-5).
 *
 * Loads a network file, runs all thirteen golden requests through the full
 * path -- validate, simulate, fingerprint -- and prints one line per request.
 * tests/run_gld.py recomputes every fingerprint with the Python oracle and
 * compares.
 *
 * This is the artifact ACC-5 is defined against: "every golden-suite request
 * yields the same fingerprint on every combination listed in Section 8.3".
 * Rows 1, 2 and 3 of that matrix are what this session can produce.
 *
 * Durations come from decisions D-37 (standard 1000 ms, maximum 5000 ms) and
 * D-42 (G-07's "Short" is 100 ms), both recorded as PROVISIONAL: TBD-06 is
 * still open and Gate G3 fixes the real values by measuring Hercules. The
 * fingerprints below are therefore provisional too -- changing a duration
 * changes every one of them.
 *
 * usage: tstgld <network file>
 */
#include <stdio.h>
#include <stdlib.h>

#include "onfcom.h"
#include "onfdec.h"
#include "onfnhd.h"  /* header offsets, generated (NFR-MNT-01) */
#include "onffpr.h"
#include "onfker.h"

/*
 * Storage is sized from the file and its header, not fixed at compile time.
 * D-70 points this suite at the real 2-hop MaleCNS network -- 13,521 neurons
 * and 1,704,385 edges -- which no reasonable static array would hold on a
 * 32-bit host.  FR-SIM-07's ban on allocation applies to the simulation core,
 * which still receives caller-owned storage.
 */

/* D-37 and D-42: provisional, x86 Phase B only. */
#define STD_MS 1000
#define SHORT_MS 100

/* Appendix E return codes (RC column), per proposal P-08. */
#define RC_OK 0
#define RC_WARN 4
#define RC_ERR 8

static onf_u8 *buf;
static onf_u32 *rowptr, *target, *stim, *readout, *brate;
static onf_f64 *weight, *su, *sg, *sring, *bias;
static onf_i32 *srfr, *sspk, *sfst, *sfrc, *sstm;
static onf_i32 oid[ONF_MAXOUT], olat[ONF_MAXOUT], ospk[ONF_MAXOUT];

/* malloc that reports which array failed rather than a bare null. */
static void *xalloc(size_t bytes, const char *what)
{
    void *p = malloc(bytes);
    if (p == NULL) {
        fprintf(stderr, "cannot allocate %lu bytes for %s\n",
                (unsigned long)bytes, what);
        exit(2);
    }
    return p;
}

struct gold {
    const char *id;
    const char *code;
    onf_i32 stimid;         /* D-39 mapping; 0 for an unrecognised code */
    onf_i32 rate;
    onf_i32 ms;             /* -1 means "header maximum" */
    onf_i32 seed;
    onf_i32 net;            /* D-212: 0 = path fixture, 1 = srext subcircuit */
};

/* D-212: the suite now spans two networks, and a fingerprint carries the
   network's payload CRC (IR-COM-05), so a request is only meaningful against
   the one it was written for.  The caller passes the network file AND which
   set to run; entries for the other set are skipped rather than run against
   the wrong file, which would produce a valid-looking fingerprint for a
   request Section 8.4 does not define. */
#define NET_PATH  0
#define NET_SREXT 1

/* SRS section 8.4, with D-37 and D-42 supplying the durations. */
static const struct gold suite[] = {
    { "G-01", "SUGR", ONF_STIM_SUGR,    0, STD_MS,        1, NET_PATH },
    { "G-02", "SUGR", ONF_STIM_SUGR,   10, STD_MS,        1, NET_PATH },
    { "G-03", "SUGR", ONF_STIM_SUGR,   40, STD_MS,        1, NET_PATH },
    { "G-04", "SUGR", ONF_STIM_SUGR,  120, STD_MS,        1, NET_PATH },
    { "G-05", "SUGR", ONF_STIM_SUGR,  200, STD_MS,        1, NET_PATH },
    { "G-06", "SUGR", ONF_STIM_SUGR,  200, STD_MS, 999999999, NET_PATH },
    { "G-07", "SUGR", ONF_STIM_SUGR, 9999, SHORT_MS,      7, NET_PATH },
    { "G-08", "SUGR", ONF_STIM_SUGR,  120, 1,             7, NET_PATH },
    { "G-09", "SUGR", ONF_STIM_SUGR,  120, -1,            7, NET_PATH },
    { "G-10", "SUGR", ONF_STIM_SUGR,  120, STD_MS,        0, NET_PATH },
    { "G-11", "WATR", ONF_STIM_WATR,  120, STD_MS,        1, NET_PATH },
    { "G-12", "XXXX", ONF_STIM_UNKNOWN, 120, STD_MS,      1, NET_PATH },
    { "G-13", "SUGR", ONF_STIM_SUGR,   -1, STD_MS,        1, NET_PATH },
    /* D-212: G-14 closes proposal P-09 -- D-165 added 60 Hz to SR-CAL-02's
       validation set after this suite was drafted, and ACC-5 is evaluated
       on the suite, so the rate had no determinism evidence. */
    { "G-14", "SUGR", ONF_STIM_SUGR,   60, STD_MS,        1, NET_PATH },
    /* D-212: the MVP subcircuit admitted by D-205.  These five are the only
       golden requests that exercise the format v1.1 compensating-input
       table, and each selects a different branch of Appendix C step 0:
       the mandatory zero row at rate 0, an exactly sampled row, the top
       row, a rate beyond the table that clamps, and a rate equidistant
       between two rows that must resolve to the lower (D-191, and
       D-213 for why that one is at 100 Hz). */
    { "G-15", "SUGR", ONF_STIM_SUGR,    0, STD_MS,        1, NET_SREXT },
    { "G-16", "SUGR", ONF_STIM_SUGR,   40, STD_MS,        1, NET_SREXT },
    { "G-17", "SUGR", ONF_STIM_SUGR,  200, STD_MS,        1, NET_SREXT },
    { "G-18", "SUGR", ONF_STIM_SUGR, 9999, STD_MS,        1, NET_SREXT },
    { "G-19", "SUGR", ONF_STIM_SUGR,  100, STD_MS,        1, NET_SREXT }
};
#define NGOLD (int)(sizeof suite / sizeof suite[0])

int main(int argc, char **argv)
{
    FILE *f;
    struct onfnet net;
    struct onfsta st;
    onf_i32 len, need, maxms, paycrc_i, want;
    onf_u32 paycrc;
    int rc, g;

    if (argc < 2) {
        fprintf(stderr, "usage: tstgld <network file> [suite]\n");
        return 2;
    }
    /* Which half of Section 8.4's suite this network is for (D-212).  It
       defaults to the path fixture, so an invocation written before the
       suite spanned two networks still does what it did. */
    want = (argc > 2) ? (onf_i32)atol(argv[2]) : (onf_i32)NET_PATH;
    f = fopen(argv[1], "rb");
    if (f == NULL) {
        fprintf(stderr, "cannot open %s\n", argv[1]);
        return 2;
    }
    if (fseek(f, 0L, SEEK_END) != 0) {
        fclose(f);
        return 2;
    }
    len = (onf_i32)ftell(f);
    rewind(f);
    buf = (onf_u8 *)xalloc((size_t)len, "the network file");
    len = (onf_i32)fread(buf, 1, (size_t)len, f);
    fclose(f);

    rc = onfdec(buf, len, 0, &net, &need);
    if (rc != ONFD_OK) {
        printf("DECODE rc=%d\n", rc);
        return 1;
    }
    rowptr  = (onf_u32 *)xalloc(sizeof(onf_u32) * (size_t)(net.n + 1),
                                "rowptr");
    target  = (onf_u32 *)xalloc(sizeof(onf_u32) * (size_t)net.e, "target");
    weight  = (onf_f64 *)xalloc(sizeof(onf_f64) * (size_t)net.e, "weight");
    stim    = (onf_u32 *)xalloc(sizeof(onf_u32) * (size_t)net.ns, "stim");
    readout = (onf_u32 *)xalloc(sizeof(onf_u32) * (size_t)net.nr, "readout");
    su    = (onf_f64 *)xalloc(sizeof(onf_f64) * (size_t)net.n, "u");
    sg    = (onf_f64 *)xalloc(sizeof(onf_f64) * (size_t)net.n, "g");
    sring = (onf_f64 *)xalloc(sizeof(onf_f64) * (size_t)net.delay
                              * (size_t)net.n, "ring");
    srfr  = (onf_i32 *)xalloc(sizeof(onf_i32) * (size_t)net.n, "rfr");
    sspk  = (onf_i32 *)xalloc(sizeof(onf_i32) * (size_t)net.n, "spikes");
    sfst  = (onf_i32 *)xalloc(sizeof(onf_i32) * (size_t)net.n, "first");
    sfrc  = (onf_i32 *)xalloc(sizeof(onf_i32) * (size_t)net.n, "force");
    sstm  = (onf_i32 *)xalloc(sizeof(onf_i32) * (size_t)net.n, "isstim");

    /* v1.1 compensating-input table (D-190); nbias is 0 when the network
       carries none, and then no storage is needed. */
    brate = NULL;
    bias = NULL;
    if (net.nbias > 0) {
        brate = (onf_u32 *)xalloc(sizeof(onf_u32) * (size_t)net.nbias,
                                  "brate");
        bias = (onf_f64 *)xalloc(sizeof(onf_f64) * (size_t)net.nbias
                                 * (size_t)net.n, "bias");
    }

    if (onfldp(buf, &net, rowptr, target, weight, stim, readout,
               brate, bias) != ONFD_OK) {
        printf("LOAD failed\n");
        return 1;
    }

    /* The payload CRC and the header's maximum duration are read straight from
       the file; the fingerprint carries the payload CRC so that two identical
       requests against different networks cannot collide (IR-COM-05). */
    paycrc  = (onf_u32)buf[ONF_N_PAYCRC] << 24;
    paycrc |= (onf_u32)buf[ONF_N_PAYCRC + 1] << 16;
    paycrc |= (onf_u32)buf[ONF_N_PAYCRC + 2] << 8;
    paycrc |= (onf_u32)buf[ONF_N_PAYCRC + 3];
    maxms  = (onf_i32)(((onf_u32)buf[ONF_N_MAXMS] << 24)
                     | ((onf_u32)buf[ONF_N_MAXMS + 1] << 16)
                     | ((onf_u32)buf[ONF_N_MAXMS + 2] << 8)
                     | (onf_u32)buf[ONF_N_MAXMS + 3]);
    paycrc_i = (onf_i32)net.nr;

    st.u = su; st.g = sg; st.rfr = srfr; st.spikes = sspk;
    st.first = sfst; st.force = sfrc; st.isstim = sstm; st.ring = sring;

    printf("# tstgld backend=%s platform=%s paycrc=%08lX maxms=%ld nr=%ld\n",
           ONF_FPID, ONF_PLATID, (unsigned long)paycrc, (long)maxms,
           (long)paycrc_i);

    for (g = 0; g < NGOLD; g++) {
        const struct gold *q = &suite[g];

        if (q->net != want) {
            continue;       /* belongs to the other network (D-212) */
        }
        onf_i32 ms, steps, outcount, i, reqrc;
        onf_u32 fp;

        ms = (q->ms < 0) ? maxms : q->ms;
        outcount = 0;
        steps = 0;
        reqrc = RC_OK;

        /* --- request validation, before any simulation ------------------ */
        if (q->stimid == ONF_STIM_UNKNOWN) {
            /* ONF203E UNKNOWN STIMULUS CODE.  Section 8.4 said ONF202E; D-41
               settled that Appendix E governs and corrected the table. */
            reqrc = RC_ERR;
        } else if (q->stimid != ONF_STIM_SUGR) {
            /* FR-BAT-05: WATR and BITR are reserved, ONF201W, not simulated. */
            reqrc = RC_WARN;
        } else if (q->rate < 0 || q->rate > 9999) {
            reqrc = RC_ERR;                     /* ONF202E, G-13 */
        } else if ((onf_u32)q->rate * (onf_u32)net.dtus > 1000000UL) {
            reqrc = RC_ERR;                     /* NR-12's bound */
        } else if (ms < 1 || ms > maxms) {
            reqrc = RC_ERR;                     /* FR-SIM-06, ONF202E */
        } else {
            steps = ms * 1000 / net.dtus;
            if (onfrun(&net, &st, (onf_u32)q->seed, q->rate, steps)
                != ONFK_OK) {
                reqrc = 16;                     /* ONF903S, FR-SIM-08 */
                steps = 0;
            } else {
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
            }
        }

        fp = onffpr(paycrc, q->stimid, q->seed, q->rate, ms, reqrc,
                    outcount, steps, oid, olat, ospk);

        printf("GOLD id=%s code=%s stimid=%ld rate=%ld ms=%ld seed=%ld "
               "rc=%ld out=%ld steps=%ld fp=%08lX\n",
               q->id, q->code, (long)q->stimid, (long)q->rate, (long)ms,
               (long)q->seed, (long)reqrc, (long)outcount, (long)steps,
               (unsigned long)fp);
        for (i = 0; i < outcount; i++) {
            printf("GOUT id=%s k=%ld n=%ld lat=%ld spk=%ld\n",
                   q->id, (long)i, (long)oid[i], (long)olat[i], (long)ospk[i]);
        }
    }

    return 0;
}
