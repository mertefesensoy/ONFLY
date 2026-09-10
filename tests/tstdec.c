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

#define MAXFILE (4 * 1024 * 1024)
#define MAXN 4096
#define MAXE 65536
#define MAXD 64

static onf_u8 buf[MAXFILE];

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
    len = (onf_i32)fread(buf, 1, MAXFILE, f);
    fclose(f);

    need = 0;
    rc = onfdec(buf, len, limit, &net, &need);
    printf("RESULT rc=%d need=%ld len=%ld\n", rc, (long)need, (long)len);
    if (rc == ONFD_OK) {
        printf("DECODED n=%ld e=%ld ns=%ld nr=%ld dtus=%ld delay=%ld refract=%ld\n",
               (long)net.n, (long)net.e, (long)net.ns, (long)net.nr,
               (long)net.dtus, (long)net.delay, (long)net.refract);
        printf("CONSTS uth=%08lX:%08lX p11=%08lX:%08lX p22=%08lX:%08lX\n",
               (unsigned long)net.uth.hi, (unsigned long)net.uth.lo,
               (unsigned long)net.p11.hi, (unsigned long)net.p11.lo,
               (unsigned long)net.p22.hi, (unsigned long)net.p22.lo);
    }

    if (rc == ONFD_OK && argc > 3) {
        static onf_u32 rowptr[MAXN + 1], target[MAXE], stim[MAXN], readout[MAXN];
        static onf_f64 weight[MAXE];
        static onf_f64 su[MAXN], sg[MAXN], sring[MAXD * MAXN];
        static onf_i32 srfr[MAXN], sspk[MAXN], sfst[MAXN], sfrc[MAXN];
        struct onfsta st;
        onf_i32 i;
        int lrc, krc;

        lrc = onfldp(buf, &net, rowptr, target, weight, stim, readout);
        printf("LOAD rc=%d\n", lrc);
        if (lrc != ONFD_OK) {
            return 0;
        }
        st.u = su; st.g = sg; st.rfr = srfr; st.spikes = sspk;
        st.first = sfst; st.force = sfrc; st.ring = sring;
        krc = onfrun(&net, &st, 1UL, 120, 500);
        printf("RUN seed=1 rate=120 steps=500 rc=%d\n", krc);
        for (i = 0; i < net.n; i++) {
            printf("OUT i=%ld s=%ld f=%ld\n", (long)i,
                   (long)st.spikes[i], (long)st.first[i]);
        }
    }

    return 0;
}
