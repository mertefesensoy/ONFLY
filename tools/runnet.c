/*
 * runnet.c - run one request against a network file (FR-PRP-04, oracle O-2).
 *
 * The full-brain reference runner. SR-CAL-01 requires W_syn to be calibrated on
 * the full-brain model rather than on a subcircuit, and SR-EXT-01 defines the
 * MVP subcircuit as the N most active neurons *in a full-brain run*, so both
 * need per-neuron spike totals over the whole network.
 *
 * usage: runnet <network> <rate_hz> <sim_ms> <seed> [--top N] [--all]
 *
 *   --top N   print the N most active neurons, which is what SR-EXT-01 needs
 *   --all     print every neuron's spike count and first-spike latency
 *   default   print only the summary and the readout neurons
 *
 * Memory. The file buffer is released as soon as the payload has been converted
 * into host-order arrays. Holding both costs 630 MB on the full MaleCNS network
 * against 330 MB once the buffer is freed, and this host is 32-bit, so the
 * difference decides whether the run happens at all.
 *
 * This is a tool, not the engine: FR-SIM-07's ban on I/O and allocation applies
 * to the simulation core, which still receives caller-owned storage and touches
 * neither.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

#include "onfdec.h"
#include "onfker.h"

struct rank {
    onf_i32 index;
    onf_i32 spikes;
};

static int bysp(const void *a, const void *b)
{
    const struct rank *x = (const struct rank *)a;
    const struct rank *y = (const struct rank *)b;

    /* Descending by spike count.  SR-EXT-01 breaks ties by ascending neuron
       identifier, so equal counts fall back to the index and the selection is
       reproducible rather than dependent on the sort's stability. */
    if (x->spikes != y->spikes) {
        return (y->spikes > x->spikes) ? 1 : -1;
    }
    if (x->index != y->index) {
        return (x->index > y->index) ? 1 : -1;
    }
    return 0;
}

int main(int argc, char **argv)
{
    FILE *f;
    struct onfnet net;
    struct onfsta st;
    onf_u8 *buf;
    onf_u32 *rowptr, *target, *stim, *readout;
    onf_f64 *weight, *su, *sg, *sring;
    onf_i32 *srfr, *sspk, *sfst, *sfrc, *sstm;
    struct rank *order;
    onf_i32 len, need, rate, simms, steps, i, topn;
    onf_u32 seed;
    long total, active;
    clock_t t0, t1;
    int rc, showall, k;

    if (argc < 5) {
        fprintf(stderr,
                "usage: runnet <network> <rate_hz> <sim_ms> <seed> "
                "[--top N] [--all]\n");
        return 2;
    }
    rate = (onf_i32)atol(argv[2]);
    simms = (onf_i32)atol(argv[3]);
    seed = (onf_u32)strtoul(argv[4], NULL, 10);
    topn = 0;
    showall = 0;
    for (k = 5; k < argc; k++) {
        if (strcmp(argv[k], "--top") == 0 && k + 1 < argc) {
            topn = (onf_i32)atol(argv[++k]);
        } else if (strcmp(argv[k], "--all") == 0) {
            showall = 1;
        }
    }

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
    buf = (onf_u8 *)malloc((size_t)len);
    if (buf == NULL) {
        fprintf(stderr, "cannot allocate %ld bytes\n", (long)len);
        fclose(f);
        return 2;
    }
    len = (onf_i32)fread(buf, 1, (size_t)len, f);
    fclose(f);

    need = 0;
    rc = onfdec(buf, len, 0, &net, &need);
    if (rc != ONFD_OK) {
        printf("DECODE rc=%d\n", rc);
        return 1;
    }
    printf("NET n=%ld e=%ld ns=%ld nr=%ld dtus=%ld delay=%ld refract=%ld "
           "need=%ld\n",
           (long)net.n, (long)net.e, (long)net.ns, (long)net.nr,
           (long)net.dtus, (long)net.delay, (long)net.refract, (long)need);

    rowptr  = (onf_u32 *)malloc(sizeof(onf_u32) * (size_t)(net.n + 1));
    target  = (onf_u32 *)malloc(sizeof(onf_u32) * (size_t)net.e);
    weight  = (onf_f64 *)malloc(sizeof(onf_f64) * (size_t)net.e);
    stim    = (onf_u32 *)malloc(sizeof(onf_u32) * (size_t)net.ns);
    readout = (onf_u32 *)malloc(sizeof(onf_u32) * (size_t)net.nr);
    if (rowptr == NULL || target == NULL || weight == NULL
        || stim == NULL || readout == NULL) {
        printf("ALLOC failed for the decoded network (n=%ld e=%ld)\n",
               (long)net.n, (long)net.e);
        return 2;
    }
    rc = onfldp(buf, &net, rowptr, target, weight, stim, readout);
    if (rc != ONFD_OK) {
        printf("LOAD rc=%d\n", rc);
        return 1;
    }

    /* The payload is now in host-order arrays; the file bytes are dead weight
       and holding them would nearly double peak memory. */
    free(buf);
    buf = NULL;

    su    = (onf_f64 *)malloc(sizeof(onf_f64) * (size_t)net.n);
    sg    = (onf_f64 *)malloc(sizeof(onf_f64) * (size_t)net.n);
    sring = (onf_f64 *)malloc(sizeof(onf_f64) * (size_t)net.delay
                              * (size_t)net.n);
    srfr  = (onf_i32 *)malloc(sizeof(onf_i32) * (size_t)net.n);
    sspk  = (onf_i32 *)malloc(sizeof(onf_i32) * (size_t)net.n);
    sfst  = (onf_i32 *)malloc(sizeof(onf_i32) * (size_t)net.n);
    sfrc  = (onf_i32 *)malloc(sizeof(onf_i32) * (size_t)net.n);
    sstm  = (onf_i32 *)malloc(sizeof(onf_i32) * (size_t)net.n);
    if (su == NULL || sg == NULL || sring == NULL || srfr == NULL
        || sspk == NULL || sfst == NULL || sfrc == NULL || sstm == NULL) {
        printf("ALLOC failed for simulation state (n=%ld delay=%ld)\n",
               (long)net.n, (long)net.delay);
        return 2;
    }
    st.u = su; st.g = sg; st.rfr = srfr; st.spikes = sspk;
    st.first = sfst; st.force = sfrc; st.isstim = sstm; st.ring = sring;

    steps = simms * 1000 / net.dtus;
    t0 = clock();
    rc = onfrun(&net, &st, seed, rate, steps);
    t1 = clock();

    total = 0;
    active = 0;
    for (i = 0; i < net.n; i++) {
        total += (long)st.spikes[i];
        if (st.spikes[i] > 0) {
            active++;
        }
    }
    /* Elapsed time is reported in whole milliseconds, computed with integer
       arithmetic.  NR-05 forbids floating-point types in engine code, and there
       is no reason for a tool that links the engine to introduce one merely to
       print a duration: an exception granted for convenience is an exception
       somebody later copies into a place where it matters. */
    printf("RUN rate=%ld ms=%ld steps=%ld seed=%lu rc=%d "
           "spikes=%ld active=%ld elapsed_ms=%ld\n",
           (long)rate, (long)simms, (long)steps, (unsigned long)seed, rc,
           total, active,
           (long)((t1 - t0) / (clock_t)(CLOCKS_PER_SEC / 1000)));

    for (i = 0; i < net.nr; i++) {
        onf_i32 nix = (onf_i32)net.readout[i];
        printf("READOUT k=%ld n=%ld spikes=%ld first=%ld\n",
               (long)i, (long)nix, (long)st.spikes[nix], (long)st.first[nix]);
    }

    if (topn > 0 || showall) {
        order = (struct rank *)malloc(sizeof(struct rank) * (size_t)net.n);
        if (order == NULL) {
            printf("ALLOC failed for the ranking\n");
            return 2;
        }
        for (i = 0; i < net.n; i++) {
            order[i].index = i;
            order[i].spikes = st.spikes[i];
        }
        qsort(order, (size_t)net.n, sizeof(struct rank), bysp);
        if (showall) {
            topn = net.n;
        }
        if (topn > net.n) {
            topn = net.n;
        }
        for (i = 0; i < topn; i++) {
            printf("TOP r=%ld n=%ld spikes=%ld first=%ld\n",
                   (long)i, (long)order[i].index, (long)order[i].spikes,
                   (long)st.first[order[i].index]);
        }
    }

    return (rc == ONFK_OK) ? 0 : 1;
}
