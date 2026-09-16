# -*- coding: utf-8 -*-
"""Bit-exact reference implementation of the ONFLY simulation kernel (oracle O-1).

This is the answer to "is the code right?".  It implements SRS Appendix C
exactly, in plain Python floats, which are IEEE 754 binary64 with
round-to-nearest-ties-to-even -- precisely what NR-01 specifies.

Rules this file obeys, from SRS section 8.2:

  * plain Python floats only; no NumPy anywhere
  * no ``sum()``: since Python 3.12 it uses compensated (Neumaier) summation,
    which would make this disagree with a straightforward left-to-right
    accumulation in C.  Every accumulation below is an explicit loop.
  * operations happen in Appendix C's order and are never reassociated (NR-07)

Status.  Appendix C is NORMATIVE as of D-71: the 2026-09-11 session reconciled
it against Shiu et al.'s published model.py and closed TBC-01.  Four semantics
were corrected in the process (D-67, D-68, D-69), each marked at its point of
use below.  The C engine implements the same algorithm independently, so a
disagreement between the two is a coding error, not a modelling question.

The model (SR-MOD-01).  With u = v - V_rest, each neuron follows

    du/dt = (g - u) / tau_mbr        dg/dt = -g / tau_syn

Both exact integration and forward Euler reduce to the same linear update with
different coefficients, which is why the method changes constants and not code
(SR-MOD-03, proposal P-04):

    u' = P11*u + P12*g              g' = P22*g

A spike from neuron j raises g of each target i by w_ji, arriving D steps later.
When u > U_th the neuron spikes (strict, D-69), u is set to U_reset, g is reset
to +0.0 (D-67), and the neuron is refractory for REFRACTORY_STEPS during which u
is held and g is FROZEN (D-67).  Stimulus neurons never become refractory
(D-68).  All four of those follow Shiu et al.'s published model.py, read in this
session; before D-66..D-69 Appendix C differed from it on every one.
"""

from . import prng as _prng
from . import stimulus as _stimulus


class Network(object):
    """A decoded network, in the form the kernel consumes.

    Attributes mirror the network file's payload sections (IR-NET) but are
    plain Python lists here; the file format is decoded elsewhere.

      n           neuron count
      rowptr      CSR row pointers, length n + 1
      target      CSR target indices, length e, strictly ascending within a row
                  (IR-NET-06 -- this order is normative for accumulation)
      weight      per-edge weights, length e, as float
      stim        stimulus neuron indices, ascending
      readout     readout neuron indices, ascending
      dt_us       timestep in microseconds
      delay       synaptic delay in steps, at least 1
      refract     refractory period in steps
      u_th        firing threshold, relative to V_rest
      u_reset     reset potential, relative to V_rest
      p11, p12, p22   propagator coefficients
      g_eps       subnormal clamp threshold (NR-08)
      bias_rates  sampled stimulus rates of the v1.1 compensating-input
                  table, strictly ascending and starting at 0; empty when the
                  network carries no table (D-190, D-191)
      bias_rows   one list of n binary64 values per entry of bias_rates
    """

    def __init__(self, n, rowptr, target, weight, stim, readout,
                 dt_us, delay, refract, u_th, u_reset, p11, p12, p22, g_eps,
                 bias_rates=(), bias_rows=()):
        assert len(rowptr) == n + 1
        assert delay >= 1, "Appendix C requires D >= 1"
        self.n = n
        self.rowptr = list(rowptr)
        self.target = list(target)
        self.weight = list(weight)
        self.stim = list(stim)
        self.readout = list(readout)
        self.dt_us = dt_us
        self.delay = delay
        self.refract = refract
        self.u_th = u_th
        self.u_reset = u_reset
        self.p11 = p11
        self.p12 = p12
        self.p22 = p22
        self.g_eps = g_eps
        self.bias_rates = list(bias_rates)
        self.bias_rows = [list(r) for r in bias_rows]
        assert len(self.bias_rates) == len(self.bias_rows), \
            "one bias row per sampled rate"
        if self.bias_rates:
            assert self.bias_rates == sorted(set(self.bias_rates)), \
                "bias rates must be strictly ascending"
            assert self.bias_rates[0] == 0, "the table must start at rate 0"
            assert all(w == 0.0 for w in self.bias_rows[0]), \
                "ACC-2: the rate 0 row must be exactly zero everywhere"
            assert all(len(r) == n for r in self.bias_rows), \
                "each bias row needs one value per neuron"

    def bias_row(self, rate_hz):
        """Appendix C step 0: the compensating-input row for this request.

        D-191 selects by NEAREST sampled rate, with ties going to the lower
        rate, and a rate beyond either end clamping to that end.  Selection is
        by integer comparison only: interpolating instead would need an
        integer-to-binary64 conversion, which the onf_fp API does not have and
        NR-07 does not list.

        Returns None when the network carries no table, which is what the full
        brain and every uncompensated network carry.
        """
        if not self.bias_rates:
            return None
        best, bestd = 0, None
        for k, r in enumerate(self.bias_rates):
            d = r - rate_hz if r >= rate_hz else rate_hz - r
            # strict >: the first (lowest) rate at the minimum distance wins,
            # which is the tie rule.
            if bestd is None or d < bestd:
                best, bestd = k, d
        return self.bias_rows[best]


class _State(object):
    """Everything the step loop carries from one step to the next.

    This exists for D-140.  A run is driven in chunks -- the caller loops
    the kernel for K steps at a time -- and TBD-19 closed requiring the
    response fingerprint to be independent of K and of where the chunk
    boundaries fall.  That is only testable if the state a chunk hands to
    the next one is a THING rather than a set of locals, so it is named
    here and nowhere else.

    `t` is the GLOBAL step index, and it is the subtle one.  The loop body
    uses it three times -- `t % net.delay` to pick the arrival slot,
    `(t + net.delay) % net.delay` to pick the emission slot, and
    `(t + 1) * net.dt_us` for the first-spike latency.  A driver that
    restarted `t` at zero each chunk would rotate the delay ring and
    mis-date every latency, and would do so silently.  tests/test_chunk.py
    is what says so.
    """

    __slots__ = ("u", "g", "rfr", "spikes", "first", "force", "is_stim",
                 "ring", "gen", "threshold", "bias", "t")


def _init(net, seed, rate_hz):
    """Build the initial state.  Pure; no I/O."""
    n = net.n
    threshold = _stimulus.check_threshold(rate_hz, net.dt_us)
    gen = _prng.Xorshift32(seed)

    # All binary64 state starts at +0.0; rfr at 0; first at -1 (Appendix C).
    u = [0.0] * n
    g = [0.0] * n
    rfr = [0] * n
    spikes = [0] * n
    first = [-1] * n
    force = [False] * n
    # D-68: stimulus neurons have no refractory period, matching Shiu's
    # rfc = 0 for Poisson targets.
    is_stim = [False] * n
    for s in net.stim:
        is_stim[s] = True

    # Delay ring: ring[slot][i].  Spikes emitted at step t arrive at the start
    # of step t + D, because slot (t + D) mod D is the slot consumed at step t.
    ring = [[0.0] * n for _ in range(net.delay)]

    # --- 0. COMPENSATING INPUT (D-190, D-191) --------------------------
    # Selected once, before the first step, from the request's rate.  It is
    # added to g in ARRIVALS below, after the delayed arrivals and before
    # anything reads g, which is the order Appendix C fixes.
    bias = net.bias_row(rate_hz)


    st = _State()
    st.u, st.g, st.rfr = u, g, rfr
    st.spikes, st.first, st.force = spikes, first, force
    st.is_stim, st.ring, st.gen = is_stim, ring, gen
    st.threshold, st.bias, st.t = threshold, bias, 0
    return st


def _advance(net, st, nsteps):
    """Run `nsteps` more steps from `st`, in place.

    The locals below are bound from the state so that the step loop reads
    exactly as it did when it was inline -- they are the same list
    objects, so `u[i] = ...` still mutates the state.  Rebinding them is
    not an optimisation; it is what keeps this refactor free of
    transcription risk in a kernel whose every line is normative
    (Appendix C).
    """
    n = net.n
    u, g, rfr = st.u, st.g, st.rfr
    spikes, first, force = st.spikes, st.first, st.force
    is_stim, ring, gen = st.is_stim, st.ring, st.gen
    threshold, bias = st.threshold, st.bias

    for t in range(st.t, st.t + nsteps):
        # --- 1. ARRIVALS ------------------------------------------------
        slot = t % net.delay
        row = ring[slot]
        if bias is None:
            for i in range(n):
                g[i] = g[i] + row[i]
                row[i] = 0.0
        else:
            for i in range(n):
                g[i] = g[i] + row[i]
                row[i] = 0.0
                g[i] = g[i] + bias[i]

        # --- 2. STIMULUS DRAWS ------------------------------------------
        # Exactly one accepted draw per stimulus neuron per step, whether or
        # not that neuron is refractory, so the PRNG stream stays aligned
        # across platforms regardless of network state (FR-SIM-04).
        for s in net.stim:
            force[s] = _stimulus.draw(gen, threshold)

        # --- 3. INTEGRATE, DETECT, EMIT ---------------------------------
        for i in range(n):
            if rfr[i] > 0:
                rfr[i] = rfr[i] - 1
                # D-67: g is FROZEN while refractory, matching Shiu's
                # "(unless refractory)" on dg/dt.  u is held at U_reset.
                was_refractory = True
            else:
                a = net.p11 * u[i]
                b = net.p12 * g[i]
                u[i] = a + b
                g[i] = net.p22 * g[i]
                was_refractory = False

            # NR-08: remove subnormal arithmetic, and with it any host
            # difference in subnormal handling, from the kernel.
            if abs(g[i]) < net.g_eps:
                g[i] = 0.0

            # D-69: the threshold is STRICT, matching Shiu's eq_th 'v > v_th'.
            if (not was_refractory) and (u[i] > net.u_th or force[i]):
                u[i] = net.u_reset
                # D-67: g is reset on every spike (Shiu's eq_rst 'g = 0*mV').
                g[i] = 0.0
                # D-68: stimulus neurons never become refractory.
                rfr[i] = 0 if is_stim[i] else net.refract
                spikes[i] = spikes[i] + 1
                if first[i] < 0:
                    first[i] = (t + 1) * net.dt_us
                # Accumulate into the arrival slot in CSR order.  IR-NET-06
                # makes that order normative: floating-point addition is not
                # associative, so a different visit order is a different answer.
                arrive = ring[(t + net.delay) % net.delay]
                for k in range(net.rowptr[i], net.rowptr[i + 1]):
                    tgt = net.target[k]
                    arrive[tgt] = arrive[tgt] + net.weight[k]

            force[i] = False

    st.t += nsteps


def run(net, seed, rate_hz, steps):
    """Run the kernel and return (spikes, first_us) for every neuron.

    Arguments:
      net       a :class:`Network`
      seed      request seed; 0 is remapped per NR-13/D-32
      rate_hz   stimulus rate in Hz
      steps     number of timesteps to simulate

    Returns:
      spikes    list of int, length net.n
      first_us  list of int, length net.n; first-spike latency in
                microseconds, or -1 if the neuron never spiked
                (FR-SIM-05)

    Side effects: none.  The generator is created internally so a run is
    fully determined by (net, seed, rate_hz, steps).
    """
    st = _init(net, seed, rate_hz)
    _advance(net, st, steps)
    return st.spikes, st.first


def run_chunked(net, seed, rate_hz, steps, k):
    """Exactly :func:`run`, driven in chunks of `k` steps (D-140).

    Returns the same (spikes, first_us) for every k >= 1, which is the
    property TBD-19 carried forward and tests/test_chunk.py asserts.

    This is the REFERENCE shape of D-140's mechanism, not its
    implementation: the engine's chunked entry point is Phase G's, and
    nothing here emits anything between chunks.  What it establishes is
    that the algorithm itself carries no hidden per-call state, so a
    Phase G driver that gets the carry right cannot change a fingerprint.
    """
    if k < 1:
        raise ValueError("chunk size k must be >= 1, got %r" % (k,))
    st = _init(net, seed, rate_hz)
    left = steps
    while left > 0:
        n = min(k, left)
        _advance(net, st, n)
        left -= n
    return st.spikes, st.first
