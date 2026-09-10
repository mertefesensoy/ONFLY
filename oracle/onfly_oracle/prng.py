# -*- coding: utf-8 -*-
"""xorshift32 pseudo-random generator (NR-13, FR-SIM-04, decision D-32).

D-32 fixes every degree of freedom the SRS left open:

  * shifts 13, 17, 5, in Marsaglia's canonical order (reference 9 of the SRS)
  * the state is updated and the **new** state is returned, so the seed itself
    is never handed out as a draw
  * a request seed of 0 maps to 2463534242 (0x92D68CA2), Marsaglia's own
    published seed

Why the zero mapping exists at all: xorshift is a linear map over GF(2), so a
zero state maps to zero forever.  Seed 0 is a legal request value (golden
request G-10 uses it), so it has to be redirected to a non-zero state.

All arithmetic is unsigned 32-bit (NR-11).  Python integers do not wrap, so
every shift is followed by an explicit mask; this is the one place where the
oracle has to work to reproduce what C does for free.

Contract:
    Xorshift32(seed) -> generator object
      seed  int in [0, 2**32); 0 is remapped to SEED_ZERO_MAPS_TO
    .next_u32() -> int in [1, 2**32)
      advances the state and returns it.  Never returns 0: a zero state is
      unreachable from a non-zero one under this map.
    Side effects: mutates the generator's own state only.
"""

MASK32 = 0xFFFFFFFF

#: NR-13's "fixed non-zero constant", fixed by D-32 to Marsaglia's own seed.
SEED_ZERO_MAPS_TO = 2463534242          # 0x92D68CA2

SHIFT_A = 13
SHIFT_B = 17
SHIFT_C = 5


class Xorshift32(object):
    """Marsaglia xorshift32, update-then-return (D-32)."""

    __slots__ = ("state",)

    def __init__(self, seed):
        if not (0 <= seed <= MASK32):
            raise ValueError("seed %r outside [0, 2**32)" % (seed,))
        self.state = SEED_ZERO_MAPS_TO if seed == 0 else seed

    def next_u32(self):
        """Advance the state and return the new value."""
        x = self.state
        x ^= (x << SHIFT_A) & MASK32
        x ^= x >> SHIFT_B
        x ^= (x << SHIFT_C) & MASK32
        x &= MASK32
        self.state = x
        return x


def sequence(seed, count):
    """Return the first ``count`` draws for ``seed`` as a list.

    Used to generate cross-language vectors for the C implementation.
    """
    gen = Xorshift32(seed)
    return [gen.next_u32() for _ in range(count)]
