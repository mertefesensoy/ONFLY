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
 * usage: tstdec <file> [memory-limit-bytes]
 */
#include <stdio.h>
#include <stdlib.h>

#include "onfdec.h"

#define MAXFILE (4 * 1024 * 1024)

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
    return 0;
}
