/*
 * onfrnd.h - xorshift32 pseudo-random generator (NR-13, FR-SIM-04, D-32).
 *
 * D-32 fixes the algorithm completely: Marsaglia's shifts 13, 17, 5 in that
 * order; the state is updated and the NEW state returned; a request seed of 0
 * maps to 2463534242 (0x92D68CA2), Marsaglia's own published seed.
 *
 * The zero mapping is not cosmetic.  xorshift is a linear map over GF(2), so a
 * zero state maps to zero forever.  Seed 0 is a legal request value and golden
 * request G-10 uses it.
 *
 * The state lives in a caller-owned struct rather than in a static, so the
 * engine holds no writable static data (NFR-MNT-02) and is reentrant for the
 * future CICS path.
 */
#ifndef ONFRND_H
#define ONFRND_H

#include "onfplat.h"

/* NR-13's "fixed non-zero constant", fixed by D-32. */
#define ONF_SEED0 2463534242UL

struct onfrng {
    onf_u32 s;
};

/*
 * onfrndi - seed a generator.
 *   g     generator to initialise; must not be null
 *   seed  request seed; 0 is remapped to ONF_SEED0
 * Side effects: sets g->s.  The state is never zero on return.
 */
void onfrndi(struct onfrng *g, onf_u32 seed);

/*
 * onfrndn - advance the state and return the new value.
 * Returns a value in [1, 2**32): zero is unreachable from a non-zero state.
 * Side effects: mutates g->s only.
 */
onf_u32 onfrndn(struct onfrng *g);

#endif /* ONFRND_H */
