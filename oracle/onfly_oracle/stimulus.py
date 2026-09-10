# -*- coding: utf-8 -*-
"""Integer-only stimulus draws (NR-12, FR-SIM-03, proposal P-02).

NR-12 verbatim: draw a 32-bit value r; if r >= 4,294,000,000, discard it and
draw again; the stimulus neuron spikes if (r mod 1,000,000) < rate_hz * dt_us.
This is exactly uniform and requires rate_hz * dt_us <= 1,000,000.

Why rejection sampling.  2**32 is not a multiple of 1,000,000, so taking
r mod 1,000,000 over the whole 32-bit range would make the low residues very
slightly more likely than the high ones -- a modulo bias.  Discarding the tail
above 4,294,000,000 leaves exactly 4,294 complete cycles of 1,000,000, so every
residue is equally likely.  No floating point is involved anywhere, which is
the point: this runs identically on a host with no IEEE hardware.

Why the rate bound.  rate_hz * dt_us is the numerator of the per-step spike
probability out of 1,000,000.  dt_us is the timestep in microseconds, so
rate_hz * dt_us / 1,000,000 = rate_hz * dt_seconds, the expected spikes per
step.  Above 1,000,000 the probability would exceed 1 and the Bernoulli
approximation to a Poisson process would silently saturate instead of failing.

Appendix C requires exactly one *accepted* draw per stimulus neuron per step,
whether or not that neuron is refractory, so the PRNG stream stays aligned
across platforms regardless of network state (FR-SIM-04).

Contract:
    draw(gen, threshold) -> bool
      gen        an object with .next_u32(); consumed until a draw is accepted
      threshold  rate_hz * dt_us, an int in [0, 1_000_000]
      returns    True if the neuron spikes this step
      Side effects: advances ``gen`` by at least one draw.
"""

#: Largest acceptable draw plus one.  4,294 whole cycles of MODULUS.
REJECT_AT = 4294000000

#: Denominator of the per-step spike probability.
MODULUS = 1000000

#: NR-12's bound on rate_hz * dt_us.
MAX_THRESHOLD = MODULUS


def check_threshold(rate_hz, dt_us):
    """Return rate_hz * dt_us, refusing values NR-12 forbids.

    Raising here rather than clamping is deliberate: a rate the model cannot
    represent is a request error (ONF202E), not something to silently round.
    """
    threshold = rate_hz * dt_us
    if rate_hz < 0:
        raise ValueError("negative rate_hz %r" % (rate_hz,))
    if dt_us <= 0:
        raise ValueError("non-positive dt_us %r" % (dt_us,))
    if threshold > MAX_THRESHOLD:
        raise ValueError(
            "NR-12 requires rate_hz * dt_us <= %d, got %d * %d = %d"
            % (MAX_THRESHOLD, rate_hz, dt_us, threshold))
    return threshold


def draw(gen, threshold):
    """One stimulus draw: True if the neuron spikes this step."""
    while True:
        r = gen.next_u32()
        if r < REJECT_AT:
            return (r % MODULUS) < threshold
        # else: rejected, draw again.  Unbiased at the cost of a rare extra draw.


def draw_with_count(gen, threshold):
    """Like :func:`draw` but also reports how many draws were consumed.

    Used by the tests to prove the rejection path is actually exercised rather
    than merely present (TU-05).
    """
    consumed = 0
    while True:
        r = gen.next_u32()
        consumed += 1
        if r < REJECT_AT:
            return ((r % MODULUS) < threshold), consumed
