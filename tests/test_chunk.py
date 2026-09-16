# -*- coding: utf-8 -*-
"""D-316, D-317 stage 1: the fingerprint must not depend on chunking.

WHAT OBLIGATION THIS DISCHARGES

D-140 decided that a run is driven in chunks -- the caller loops the
kernel for K steps at a time and emits between calls -- and that K
travels in the request. The decisive argument was not streaming at all:
VL-43 measured one request at N=1000 taking 507 seconds, and Phase H
runs ONFLY under CICS, where holding a task that long is exactly what
Section 3.7's runaway-task note forbids. The work has to be breakable
whether or not anything is ever drawn on a screen.

TBD-19 closed carrying one obligation, and it is load-bearing:

    D-140 requires the response fingerprint to be independent of K and
    of chunk boundaries, which needs a requirement ID and a test before
    Phase G is built.

ACC-5 is the project's spine -- nineteen fingerprints reproduced across
seven platform, compiler and backend rows. A chunk-dependent fingerprint
would not cost a feature; it would cost the determinism claim, and it
would be found in Phase G with Phase E's evidence already published.

WHAT THIS FILE PROVES, AND WHAT IT DELIBERATELY DOES NOT

Nothing in the tree can currently run in chunks: kernel.run() builds u,
g, rfr, the delay ring and the generator internally and loops over
steps, with no step() and no way to resume. So this stage does not
assert the whole property. It asserts the part that can be asserted
today with **no change to O-1, the bit-exact reference** -- and it
targets the likeliest way a chunked driver would break:

  * the PRNG stream (FR-SIM-04 requires one stream per request, drawn in
    Appendix C's order, identical on every platform);
  * the stimulus draws layered on it, including the rejection path,
    whose variable consumption is what makes chunk boundaries
    non-obvious;
  * the fingerprint's dependence on its documented inputs only.

Each also has a NEGATIVE case. A test that only shows the right thing
passing cannot tell you it would have caught the wrong thing, and the
specific wrong thing here -- a driver that re-seeds per chunk -- looks
entirely reasonable until you see the stream diverge.

Stage 2 (D-317) makes the oracle's state resumable and proves the whole
property against kernel.run().

WHERE THE ENGINE HALF LIVES, SINCE 2026-09-16

The paragraph above beginning "Nothing in the tree can currently run in
chunks" described the tree as it was until D-366. It no longer holds, and
it is left standing because it is what the stages were written against:
engine/src/onfker.c now has onfinit and onfcont, with onfrun defined as
their composition, and engine/src/onfreq.c has onfrq1k beside onfrq1
(D-368). So the sentence to read it by is this one --

    this file is the ORACLE half of FR-SIM-10, and tools/cmpchk.py is the
    ENGINE half.

They are deliberately not the same test. This one runs the reference
implementation over a small fixture and can afford a negative case for
every threat. cmpchk drives the real nineteen Section 8.4 requests through
the compiled engine at several chunk sizes, because FR-SIM-10's own text
requires the property to be shown against that suite and not a fixture --
the suite is what ACC-5's determinism claim rests on.

Run:  python tests/test_chunk.py
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "oracle"))

from onfly_oracle import fingerprint as _fp                   # noqa: E402
from onfly_oracle import prng as _prng                        # noqa: E402
from onfly_oracle import stimulus as _stim                    # noqa: E402

SEEDS = (0, 1, 7, 12345, 999999999)
CHUNKS = (1, 2, 3, 7, 10, 100, 997)
TOTAL = 1000

# A rate and dt whose product exercises the rejection path: draw()
# retries whenever the raw draw lands above REJECT_AT, so the number of
# u32 values consumed per step is NOT fixed.  That is precisely what
# makes "resume at a chunk boundary" a real question rather than an
# arithmetic one.
RATE_HZ, DT_US = 200, 100


def _chunked(seed, total, k, consume):
    """Consume `total` items in chunks of `k`, carrying ONE generator.

    This is what a correct chunked driver does: the generator outlives
    the chunk. It is written here, in the test, rather than in the
    product -- D-316 proposes the requirement, it does not enact D-140.
    """
    gen = _prng.Xorshift32(seed)
    out = []
    left = total
    while left > 0:
        n = min(k, left)
        for _ in range(n):
            out.append(consume(gen))
        left -= n
    return out


def _reseeded(seed, total, k, consume):
    """The plausible WRONG driver: a fresh generator per chunk."""
    out = []
    left = total
    while left > 0:
        gen = _prng.Xorshift32(seed)
        n = min(k, left)
        for _ in range(n):
            out.append(consume(gen))
        left -= n
    return out


def _u32(gen):
    return gen.next_u32()


class PrngStream(unittest.TestCase):
    """FR-SIM-04: one stream per request, whatever the chunking."""

    def test_the_stream_is_the_same_at_every_chunk_size(self):
        for seed in SEEDS:
            whole = _prng.sequence(seed, TOTAL)
            for k in CHUNKS:
                self.assertEqual(_chunked(seed, TOTAL, k, _u32), whole,
                                 "seed %d, K=%d" % (seed, k))

    def test_reseeding_per_chunk_would_break_it(self):
        # The negative case. Without this, the test above would pass
        # just as happily against a stream that could not tell the two
        # drivers apart.
        for seed in (1, 7):
            whole = _prng.sequence(seed, TOTAL)
            for k in (1, 10, 100):
                self.assertNotEqual(_reseeded(seed, TOTAL, k, _u32), whole,
                                    "seed %d, K=%d" % (seed, k))

    def test_seed_zero_is_chunk_invariant_too(self):
        # NR-13/D-32 remaps seed 0; G-10 exists for it. A remap applied
        # per chunk rather than per request would be invisible at K=total.
        whole = _prng.sequence(0, TOTAL)
        for k in CHUNKS:
            self.assertEqual(_chunked(0, TOTAL, k, _u32), whole, "K=%d" % k)


class StimulusDraws(unittest.TestCase):
    """The draws layered on the stream, rejection path included."""

    def setUp(self):
        self.threshold = _stim.check_threshold(RATE_HZ, DT_US)

    def test_draws_are_the_same_at_every_chunk_size(self):
        def consume(gen):
            return _stim.draw(gen, self.threshold)
        for seed in SEEDS:
            whole = _chunked(seed, TOTAL, TOTAL, consume)
            for k in CHUNKS:
                self.assertEqual(_chunked(seed, TOTAL, k, consume), whole,
                                 "seed %d, K=%d" % (seed, k))

    def test_the_rejection_path_is_actually_exercised(self):
        # If it never rejected, every step would consume exactly one u32
        # and chunk invariance would be arithmetically trivial. TU-05
        # makes the same point about draw_with_count; it is repeated here
        # because this file's claim depends on it.
        gen = _prng.Xorshift32(1)
        extra = 0
        for _ in range(20000):
            _v, consumed = _stim.draw_with_count(gen, self.threshold)
            extra += consumed - 1
        self.assertGreater(extra, 0,
                           "no draw was ever rejected, so chunk "
                           "invariance here proves nothing")

    def test_draws_consume_a_variable_number_of_u32(self):
        # The same fact from the other side: the mapping from steps to
        # stream position is not a multiplication, so a driver cannot
        # reconstruct position from a step count.
        gen = _prng.Xorshift32(1)
        counts = set()
        for _ in range(20000):
            _v, consumed = _stim.draw_with_count(gen, self.threshold)
            counts.add(consumed)
        self.assertGreater(len(counts), 1)


class FingerprintInputs(unittest.TestCase):
    """IR-COM-05: the fingerprint is a function of its arguments."""

    ARGS = (0x4577D74E, 1, 1, 200, 1000, 0,
            ((9, 8600, 165), (88, 43400, 15)), 10000)

    def test_it_is_a_pure_function_of_its_arguments(self):
        first = _fp.fingerprint(*self.ARGS)
        for _ in range(5):
            self.assertEqual(_fp.fingerprint(*self.ARGS), first)

    def test_total_steps_is_an_input(self):
        # So a chunked run MUST report the total, not the last chunk's
        # count. This is the one place where chunking could change a
        # fingerprint without any state being mishandled at all.
        a = list(self.ARGS)
        b = list(self.ARGS)
        b[7] = 100                      # as if only the last chunk counted
        self.assertNotEqual(_fp.fingerprint(*a), _fp.fingerprint(*b))

    def test_the_outputs_are_totals_not_per_chunk(self):
        # Spike counts accumulate across chunks; a per-chunk count would
        # be a different fingerprint.
        a = list(self.ARGS)
        b = list(self.ARGS)
        b[6] = ((9, 8600, 16), (88, 43400, 1))
        self.assertNotEqual(_fp.fingerprint(*a), _fp.fingerprint(*b))

    def test_it_matches_the_shipped_g17_value(self):
        # Anchors the arguments above to a real Section 8.4 entry, so a
        # change to IR-COM-05's canonical string fails here and not only
        # on a mainframe.  G-17: srext, SUGR, 200 Hz, 1000 ms, seed 1.
        self.assertEqual("%08X" % _fp.fingerprint(*self.ARGS), "F9C7EE77")


from onfly_oracle import kernel as _kernel                    # noqa: E402

# Shiu's constants, as tests/test_bias.py uses them.
NK = 8
STEPS = 900


def _net(bias_rates=None, bias_rows=None):
    """A small but fully exercised network.

    A ring 0 -> 1 -> ... -> 7 -> 0, so spikes propagate through the delay
    ring and the CSR accumulation order matters; neuron 0 is the stimulus
    and neuron 4 the readout. Weights are large enough that downstream
    neurons really fire -- a chunk test in which nothing ever spikes
    would pass against almost any bug.
    """
    rowptr = list(range(NK + 1))          # exactly one edge per neuron
    target = [(i + 1) % NK for i in range(NK)]
    weight = [9.0] * NK
    return _kernel.Network(
        n=NK, rowptr=rowptr, target=target, weight=weight,
        stim=[0], readout=[4], dt_us=DT_US, delay=18, refract=22,
        u_th=7.0, u_reset=0.0,
        p11=0.9950124791926823, p12=0.004937935295309022,
        p22=0.9801986733067553, g_eps=1e-300,
        bias_rates=bias_rates or (), bias_rows=bias_rows or ())


def _naive_chunked(net, seed, rate_hz, steps, k):
    """The plausible WRONG driver: `t` restarts at zero every chunk.

    This is not a strawman. `t` is a loop variable; a driver written by
    someone who has not noticed that the body uses it for the delay-ring
    slot and for the first-spike latency would naturally write exactly
    this, and it produces a full, plausible-looking answer.
    """
    st = _kernel._init(net, seed, rate_hz)
    left = steps
    while left > 0:
        n = min(k, left)
        st.t = 0                          # the bug
        _kernel._advance(net, st, n)
        left -= n
    return st.spikes, st.first


class KernelChunkInvariance(unittest.TestCase):
    """D-317 stage 2: the whole property, against kernel.run()."""

    def test_the_fixture_actually_spikes(self):
        spikes, _first = _kernel.run(_net(), 1, RATE_HZ, STEPS)
        self.assertGreater(sum(spikes), 0)
        self.assertGreater(len([s for s in spikes if s > 0]), 1,
                           "spikes never propagated past the stimulus "
                           "neuron, so the delay ring is untested")

    def test_chunked_equals_whole_at_every_k(self):
        net = _net()
        for seed in (0, 1, 7):
            whole = _kernel.run(net, seed, RATE_HZ, STEPS)
            for k in (1, 2, 17, 18, 19, 100, STEPS, STEPS + 5):
                got = _kernel.run_chunked(net, seed, RATE_HZ, STEPS, k)
                self.assertEqual(got, whole, "seed %d, K=%d" % (seed, k))

    def test_k_around_the_delay_is_covered(self):
        # delay = 18. K equal to, just below and just above the delay is
        # where a ring-phase error would show first, so those are in the
        # list above deliberately rather than by chance.
        self.assertEqual(_net().delay, 18)

    def test_the_naive_driver_is_caught(self):
        # The negative case. Without it, the test above could not
        # distinguish a kernel that carries state correctly from one
        # where chunking happens not to matter.
        net = _net()
        whole = _kernel.run(net, 1, RATE_HZ, STEPS)
        differed = False
        for k in (1, 7, 100):
            if _naive_chunked(net, 1, RATE_HZ, STEPS, k) != whole:
                differed = True
        self.assertTrue(differed,
                        "a driver that restarts t each chunk produced the "
                        "same answer, so this suite cannot detect the "
                        "error it exists to detect")

    def test_chunking_with_a_compensating_table(self):
        # v1.1's bias row is selected ONCE, before the first step
        # (D-190, D-191).  A driver that re-selected per chunk would be
        # correct only while the rate never changed -- which is exactly
        # the kind of latent error that survives until it does not.
        rates = [0, 40, 120, 200]
        rows = [[0.0] * NK, [0.10] * NK, [0.20] * NK, [0.30] * NK]
        net = _net(rates, rows)
        whole = _kernel.run(net, 1, RATE_HZ, STEPS)
        for k in (1, 18, 100, STEPS):
            self.assertEqual(_kernel.run_chunked(net, 1, RATE_HZ, STEPS, k),
                             whole, "K=%d" % k)

    def test_zero_and_negative_k_are_refused(self):
        net = _net()
        self.assertRaises(ValueError, _kernel.run_chunked,
                          net, 1, RATE_HZ, STEPS, 0)
        self.assertRaises(ValueError, _kernel.run_chunked,
                          net, 1, RATE_HZ, STEPS, -1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
