# -*- coding: utf-8 -*-
"""TP-07: the D-187 weight-compensation hook in prep/emit.py.

Why this test exists.  SR-EXT-02 requires a subcircuit to keep its
connections "with unchanged weights".  D-187 authorises a deviation for the
compared truncation constructions, and that deviation is implemented as two
optional gain arrays on ``emit.build_network``.  A hook like that is
dangerous in exactly one way: if it were ever *not* a no-op when nobody
asked for it, every network file in the repository -- the golden fixtures
included -- would change silently and every ACC-5 fingerprint with them.

So the contract under test is:

  1. No gain argument and an all-ones gain produce byte-identical files.
     This is what keeps data/networks/ safe from the hook's mere existence.
  2. A gain applies to the edges whose TARGET is that neuron, split by the
     edge's sign, and to no other edge.
  3. A gain array of the wrong length is rejected rather than broadcast.

The fixture is a hand-built six-neuron network, so no MaleCNS data is
needed and this runs on a bare checkout.

Run:  python tests/test_gain.py
"""
import os
import struct
import sys
import unittest

# D-233: skip rather than fail when numpy is absent, the same way
# tests/run_cob.py skips when no cobc is found (D-156).  The s390x guest
# Phase D runs the suite in has no numpy, and this test exercises a
# pure-Python preparation pipeline whose result cannot depend on the host --
# so what matters is that the omission is announced, not that it is
# prevented.
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "tools"))
import onfres                                                 # noqa: E402

try:
    import numpy as np
except ImportError:
    onfres.skip("test_gain/numpy", "numpy is not installed on this host "
                "(D-233); the emit gain check is host-side and is checked "
                "where it is")
    raise SystemExit(0)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "prep"))

import emit  # noqa: E402


# Six neurons, body ids deliberately not 0..5 and not in ascending order in
# the edge list, so that any dependence on edge order or on identifier
# values would show up.  Signs: positive counts are excitatory, negative
# inhibitory, exactly as prep/signs.py leaves them (SR-MOD-05).
BODIES = [70, 10, 40, 20, 60, 30]
EDGES = [
    # (pre, post, signed synapse count)
    (10, 40, 5),
    (20, 40, -3),
    (30, 40, 7),
    (10, 60, 2),
    (40, 60, -9),
    (70, 30, 4),
    (20, 30, -6),
]
STIM = np.array([10, 20], dtype=np.int64)
READ = np.array([60], dtype=np.int64)


def arrays():
    return {"body_pre": np.array([e[0] for e in EDGES], dtype=np.int64),
            "body_post": np.array([e[1] for e in EDGES], dtype=np.int64),
            "signed_weight": np.array([e[2] for e in EDGES], dtype=np.int64)}


def nodes():
    return np.array(sorted(BODIES), dtype=np.int64)


def build(ge=None, gi=None):
    blob, n, e = emit.build_network(arrays(), nodes(), STIM, READ, "t",
                                    gain_exc=ge, gain_inh=gi)
    return blob, n, e


def weights_of(blob):
    """Pull the weight section out of a network file (IR-NET-01 layout).

    Read from the header's own offsets rather than from a computed guess, so
    the test does not silently start reading the wrong bytes if a section
    moves.
    """
    e = struct.unpack(">I", blob[24:28])[0]
    off = struct.unpack(">I", blob[140:144])[0]
    return list(struct.unpack(">%dd" % e, blob[off:off + 8 * e]))


class GainHook(unittest.TestCase):

    def test_absent_and_unit_gain_are_identical(self):
        """Contract 1: the hook is a no-op unless a caller uses it."""
        base, n, _e = build()
        ones = np.ones(n)
        self.assertEqual(base, build(ge=ones, gi=ones)[0])
        self.assertEqual(base, build(ge=ones)[0])
        self.assertEqual(base, build(gi=ones)[0])

    def test_gain_hits_only_its_target_and_sign(self):
        """Contract 2: per target neuron, per edge sign, and nothing else."""
        base, n, _e = build()
        srt = sorted(BODIES)
        j = srt.index(40)                      # scale excitation into 40 only
        ge = np.ones(n)
        ge[j] = 2.0
        got = weights_of(build(ge=ge)[0])
        want = weights_of(base)
        # Recompute the expectation from the fixture rather than from the
        # code under test: every excitatory edge into body 40 doubles.
        expect = []
        order = sorted(EDGES, key=lambda t: (srt.index(t[0]),
                                             srt.index(t[1])))
        for pre, post, s in order:
            w = s * emit.W_SYN
            if post == 40 and s > 0:
                w *= 2.0
            expect.append(w)
        self.assertEqual(len(want), len(expect))
        for a, b in zip(got, expect):
            self.assertEqual(a, b)
        # and the untouched edges really are untouched
        for k, (pre, post, s) in enumerate(order):
            if not (post == 40 and s > 0):
                self.assertEqual(got[k], want[k])

    def test_inhibitory_gain_is_separate(self):
        """A beta on a target leaves that target's excitation alone."""
        base, n, _e = build()
        srt = sorted(BODIES)
        gi = np.ones(n)
        gi[srt.index(40)] = 3.0
        got, want = weights_of(build(gi=gi)[0]), weights_of(base)
        order = sorted(EDGES, key=lambda t: (srt.index(t[0]),
                                             srt.index(t[1])))
        for k, (pre, post, s) in enumerate(order):
            if post == 40 and s < 0:
                self.assertEqual(got[k], want[k] * 3.0)
            else:
                self.assertEqual(got[k], want[k])

    def test_wrong_length_is_rejected(self):
        """Contract 3: a short array must not be broadcast into place."""
        _b, n, _e = build()
        self.assertRaises(ValueError, build, np.ones(n - 1), None)
        self.assertRaises(ValueError, build, None, np.ones(n + 1))


if __name__ == "__main__":
    unittest.main(verbosity=2)
