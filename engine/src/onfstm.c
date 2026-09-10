/*
 * onfstm.c - integer-only stimulus draws (NR-12).
 */
#include "onfstm.h"

int onfstmd(struct onfrng *g, onf_u32 thresh)
{
    onf_u32 r;

    for (;;) {
        r = onfrndn(g);
        if (r < ONF_STMREJ) {
            if ((r % ONF_STMMOD) < thresh) {
                return 1;
            }
            return 0;
        }
        /* Rejected: outside the last whole cycle.  Draw again. */
    }
}
