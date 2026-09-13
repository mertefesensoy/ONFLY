/*
 * tstdec.c - decode one network file and report the outcome (TE-01..TE-08).
 *
 * Prints a single line: RESULT rc=<n> need=<bytes>.  It carries no expected
 * values; tests/run_dec.py builds each file, knows which check it corrupted,
 * and decides pass or fail.
 *
 * File I/O lives here rather than in the engine: FR-SIM-07 forbids I/O in the
 * simulation core, and onfdec itself only ever reads a caller-supplied buffer.
 *
 * With a third argument "run", it also loads the payload into host-order
 * arrays and simulates, so the whole path from a file on disk to per-neuron
 * results is exercised end to end.  run_dec.py then checks those results
 * against the Python oracle running on the network it wrote in the first place.
 *
 * usage: tstdec <file> [memory-limit-bytes] [run]
 */
#include <stdio.h>
#include <stdlib.h>

#include "onfdec.h"
#include "onfker.h"

/*
 * Buffers are allocated from the heap and sized from the file and its header,
 * not fixed at compile time.  A real MaleCNS network is tens or hundreds of
 * megabytes, and a static array large enough for one would not link on a
 * 32-bit host.  This is harness code: FR-SIM-07's ban on allocation applies to
 * the simulation core, which still receives caller-owned storage.
 */
static onf_u8 *buf;

int main(int argc, char **argv)
{
    FILE *f;
    struct onfnet net;
    onf_i32 len, limit, need;
    int rc;

    if (argc < 2) {
        fprintf(stderr, "usage: tstdec <file> [limit]\n");
        return 2;
    }
    limit = (argc > 2) ? (onf_i32)atol(argv[2]) : 0;

    f = fopen(argv[1], "rb");
    if (f == NULL) {
        fprintf(stderr, "cannot open %s\n", argv[1]);
        return 2;
    }
    if (fseek(f, 0L, SEEK_END) != 0) {
        fprintf(stderr, "cannot size %s\n", argv[1]);
        fclose(f);
        return 2;
    }
    len = (onf_i32)ftell(f);
    rewind(f);
    buf = (onf_u8 *)malloc((size_t)len);
    if (buf == NULL) {
        fprintf(stderr, "cannot allocate %ld bytes for %s\n",
                (long)len, argv[1]);
        fclose(f);
        return 2;
    }
    len = (onf_i32)fread(buf, 1, (size_t)len, f);
    fclose(f);

    need = 0;
    rc = onfdec(buf, len, limit, &net, &need);
    printf("RESULT rc=%d need=%ld len=%ld\n", rc, (long)need, (long)len);
    if (rc == ONFD_OK) {
        printf("DECODED n=%ld e=%ld ns=%ld nr=%ld dtus=%ld"
               " delay=%ld refract=%ld\n",
               (long)net.n, (long)net.e, (long)net.ns, (long)net.nr,
               (long)net.dtus, (long)net.delay, (long)net.refract);
        printf("CONSTS uth=%08lX:%08lX p11=%08lX:%08lX p22=%08lX:%08lX\n",
               (unsigned long)net.uth.hi, (unsigned long)net.uth.lo,
               (unsigned long)net.p11.hi, (unsigned long)net.p11.lo,
               (unsigned long)net.p22.hi, (unsigned long)net.p22.lo);
    }

    if (rc == ONFD_OK && argc > 3) {
        onf_u32 *rowptr, *target, *stim, *readout, *brate;
        onf_f64 *weight, *su, *sg, *sring, *bias;
        onf_i32 *srfr, *sspk, *sfst, *sfrc, *sstm;
        struct onfsta st;
        onf_i32 i;
        int lrc, krc;

        rowptr  = (onf_u32 *)malloc(sizeof(onf_u32) * (size_t)(net.n + 1));
        target  = (onf_u32 *)malloc(sizeof(onf_u32) * (size_t)net.e);
        weight  = (onf_f64 *)malloc(sizeof(onf_f64) * (size_t)net.e);
        stim    = (onf_u32 *)malloc(sizeof(onf_u32) * (size_t)net.ns);
        readout = (onf_u32 *)malloc(sizeof(onf_u32) * (size_t)net.nr);
        su   = (onf_f64 *)malloc(sizeof(onf_f64) * (size_t)net.n);
        sg   = (onf_f64 *)malloc(sizeof(onf_f64) * (size_t)net.n);
        sring = (onf_f64 *)malloc(sizeof(onf_f64)
                                  * (size_t)net.delay * (size_t)net.n);
        srfr = (onf_i32 *)malloc(sizeof(onf_i32) * (size_t)net.n);
        sspk = (onf_i32 *)malloc(sizeof(onf_i32) * (size_t)net.n);
        sfst = (onf_i32 *)malloc(sizeof(onf_i32) * (size_t)net.n);
        sfrc = (onf_i32 *)malloc(sizeof(onf_i32) * (size_t)net.n);
        sstm = (onf_i32 *)malloc(sizeof(onf_i32) * (size_t)net.n);
        /* v1.1 compensating-input table (D-190); nbias is 0 when the
           network carries none. */
        brate = NULL;
        bias = NULL;
        if (net.nbias > 0) {
            brate = (onf_u32 *)malloc(sizeof(onf_u32) * (size_t)net.nbias);
            bias = (onf_f64 *)malloc(sizeof(onf_f64) * (size_t)net.nbias
                                     * (size_t)net.n);
            if (brate == NULL || bias == NULL) {
                printf("ALLOC failed for nbias=%ld n=%ld\n",
                       (long)net.nbias, (long)net.n);
                return 2;
            }
        }
        if (rowptr == NULL || target == NULL || weight == NULL
            || stim == NULL || readout == NULL || su == NULL || sg == NULL
            || sring == NULL || srfr == NULL || sspk == NULL
            || sfst == NULL || sfrc == NULL || sstm == NULL) {
            printf("ALLOC failed for n=%ld e=%ld delay=%ld\n",
                   (long)net.n, (long)net.e, (long)net.delay);
            return 2;
        }

        lrc = onfldp(buf, &net, rowptr, target, weight, stim, readout,
                     brate, bias);
        printf("LOAD rc=%d\n", lrc);
        if (lrc != ONFD_OK) {
            return 0;
        }
        st.u = su; st.g = sg; st.rfr = srfr; st.spikes = sspk;
        st.first = sfst; st.force = sfrc; st.isstim = sstm; st.ring = sring;
        krc = onfrun(&net, &st, 1UL, 120, 500);
        printf("RUN seed=1 rate=120 steps=500 rc=%d\n", krc);
        for (i = 0; i < net.n; i++) {
            printf("OUT i=%ld s=%ld f=%ld\n", (long)i,
                   (long)st.spikes[i], (long)st.first[i]);
        }
    }

    return 0;
}
