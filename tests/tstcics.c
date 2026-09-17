/*
 * tstcics.c - the CICS adapter over a request dataset (P-22 V4, D-400).
 *
 * WHAT IT PROVES
 * --------------
 * That engine/src/onfcics.c -- the LINK target's engine side -- produces
 * EXACTLY the response records the batch engine produces.  It reads the same
 * ONFREQ the batch path reads and writes the same ONFRSP, so the comparison
 * the runner makes is `fc /b` between two files, not an interpretation.
 *
 * WHY IT EXISTS AS A C PROGRAM
 * ----------------------------
 * D-399 first tried to read the bytes back out of a QIX run unit and D-400
 * records the measurement that killed it: QIX copies the COMMAREA INTO the
 * run unit and never back, exactly as real CICS does for a transaction with
 * no caller.  So the byte comparison is made where the bytes exist -- at the
 * adapter -- and the COBOL transaction is separately required to report the
 * golden fingerprint, which is IR-COM-05's CRC-32 over every response field.
 *
 * This is NOT a second implementation of anything.  It calls onfcini and
 * onfcrun, which call onfrq1, which is the one request sequence D-224
 * established (engine/src/onfreq.c).  What it adds is a loop over a dataset
 * and two fopen calls.
 *
 * C89 plus long long (NR-04).  No float, no double, no floating-point
 * literal (NR-05).
 *
 * usage:  tstcics <network> <requests> <responses>
 * exit:   0 on success; 2 on a usage or I/O failure; 3 if the network could
 *         not be loaded, with the ONF code printed.
 */
#include <stdio.h>
#include <stdlib.h>

#include "onfplat.h"
#include "onfcics.h"
#include "onfcom.h"

int main(int argc, char **argv)
{
    struct onfcic *h;
    FILE *fq;
    FILE *fs;
    onf_u8 rec[ONF_RECLEN];
    onf_i32 rc;
    size_t got;
    long n;

    if (argc != 4) {
        printf("usage: tstcics <network> <requests> <responses>\n");
        return 2;
    }

    if (onfclen() != (onf_i32)ONF_RECLEN) {
        /* The adapter and this test disagree about the record length, which
           can only mean one of them was built against a stale generated
           header.  Loud rather than a confusing byte mismatch later. */
        printf("tstcics: onfclen %ld, expected %ld\n",
               (long)onfclen(), (long)ONF_RECLEN);
        return 2;
    }

    rc = 0;
    h = onfcini(argv[1], &rc);
    if (h == NULL) {
        printf("tstcics: network load failed, rc %ld: %s\n",
               (long)rc, argv[1]);
        return 3;
    }

    fq = fopen(argv[2], "rb");
    if (fq == NULL) {
        printf("tstcics: cannot read %s\n", argv[2]);
        onfcend(h);
        return 2;
    }
    fs = fopen(argv[3], "wb");
    if (fs == NULL) {
        printf("tstcics: cannot write %s\n", argv[3]);
        fclose(fq);
        onfcend(h);
        return 2;
    }

    n = 0L;
    for (;;) {
        got = fread(rec, 1, (size_t)ONF_RECLEN, fq);
        if (got == 0) {
            break;
        }
        if (got != (size_t)ONF_RECLEN) {
            printf("tstcics: short record at %ld\n", n);
            fclose(fq);
            fclose(fs);
            onfcend(h);
            return 2;
        }
        /* One LINK's worth of work, with the same handle every time: this is
           the "loaded once and anchored, transactions only read it" shape of
           Section 3.7, and it is also what makes the test meaningful --  a
           fingerprint must not depend on what ran before it (ACC-5). */
        rc = onfcrun(h, rec, (onf_i32)ONF_RECLEN);
        if (rc < 0) {
            printf("tstcics: adapter refused record %ld, rc %ld\n",
                   n, (long)rc);
            fclose(fq);
            fclose(fs);
            onfcend(h);
            return 2;
        }
        if (fwrite(rec, 1, (size_t)ONF_RECLEN, fs) != (size_t)ONF_RECLEN) {
            printf("tstcics: write failed at %ld\n", n);
            fclose(fq);
            fclose(fs);
            onfcend(h);
            return 2;
        }
        n++;
    }

    fclose(fq);
    fclose(fs);
    onfcend(h);

    printf("tstcics: %ld requests through the CICS adapter\n", n);
    return 0;
}
