# -*- coding: utf-8 -*-
"""TP-08: the v1.1 compensating-input table (IR-NET-09, D-190, D-191).

Two things are pinned here, both of which are easy to get subtly wrong and
neither of which any other test would catch.

**Row selection.**  Appendix C step 0 picks the row whose sampled rate is
nearest the request's, ties to the LOWER rate, clamping beyond either end.
The C kernel and the Python oracle implement that independently, so the rule
has to be stated somewhere a reader can check it against both.  A tie rule
that differed between them would show up only as a fingerprint mismatch on
one rate, most likely on the platform hardest to debug.

**The rate 0 row.**  ACC-2 says a request with rate 0 produces zero spikes in
every neuron, on every platform and backend, and calls that deterministic.
Once a network can add a constant input to every neuron at every step, that
criterion stops being free: a table whose first row were non-zero would make
neurons fire with no stimulus at all.  So the writer asserts it, the Python
reader re-checks it, and the C decoder re-checks it on the raw bytes.  The
tests below hold the writer and the oracle to it.

The fixture is hand-built, so this runs on a bare checkout.

Run:  python tests/test_bias.py
"""
import os
import struct
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _sub in ("layout", "generated", "oracle"):
    sys.path.insert(0, os.path.join(ROOT, _sub))

import netwrite  # noqa: E402
import onfcom_py as L  # noqa: E402
from onfly_oracle import kernel as okernel  # noqa: E402

N = 4
RATES = [0, 40, 120, 200]


def rows(scale=1.0):
    """One distinguishable constant per rate, so a wrong row is obvious."""
    return [[0.0] * N,
            [scale * 1.0] * N,
            [scale * 2.0] * N,
            [scale * 3.0] * N]


def net(bias_rates=None, bias_rows=None):
    return okernel.Network(
        n=N, rowptr=[0] * (N + 1), target=[], weight=[],
        stim=[0], readout=[N - 1], dt_us=100, delay=18, refract=22,
        u_th=7.0, u_reset=0.0,
        p11=0.9950124791926823, p12=0.004937935295309022,
        p22=0.9801986733067553, g_eps=1e-300,
        bias_rates=bias_rates or (), bias_rows=bias_rows or ())


def blob(bias_rates=None, bias_rows=None):
    return netwrite.build(
        n=N, rowptr=[0] * (N + 1), target=[], weight=[],
        stim=[0], readout=[N - 1], dt_us=100, delay=18, refract=22,
        max_ms=1300, u_th=7.0, u_reset=0.0,
        p11=0.9950124791926823, p12=0.004937935295309022,
        p22=0.9801986733067553, g_eps=1e-300, w_syn=0.275, v_rest=-52.0,
        bias_rates=bias_rates, bias_rows=bias_rows)


class RowSelection(unittest.TestCase):

    def setUp(self):
        self.net = net(RATES, rows())

    def which(self, rate):
        """Index of the row the kernel would select for ``rate``."""
        row = self.net.bias_row(rate)
        return None if row is None else self.net.bias_rows.index(row)

    def test_exact_rates_select_their_own_row(self):
        for k, r in enumerate(RATES):
            self.assertEqual(self.which(r), k, "rate %d" % r)

    def test_nearest_row_wins(self):
        self.assertEqual(self.which(30), 1)     # 40 is nearer than 0
        self.assertEqual(self.which(50), 1)     # 40 is nearer than 120
        self.assertEqual(self.which(100), 2)    # 120 is nearer than 40
        self.assertEqual(self.which(190), 3)

    def test_ties_go_to_the_lower_rate(self):
        """D-191's tie rule, the one place the two implementations could
        silently disagree."""
        self.assertEqual(self.which(20), 0)     # equidistant from 0 and 40
        self.assertEqual(self.which(80), 1)     # equidistant from 40 and 120
        self.assertEqual(self.which(160), 2)    # equidistant from 120 and 200

    def test_out_of_range_clamps_to_the_nearer_end(self):
        self.assertEqual(self.which(9999), 3)   # golden request G-07's rate
        self.assertEqual(self.which(0), 0)

    def test_no_table_selects_nothing(self):
        self.assertIsNone(net().bias_row(120))


class RateZeroRow(unittest.TestCase):
    """ACC-2 must not depend on anyone remembering to zero the first row."""

    def test_writer_rejects_a_non_zero_rate_zero_row(self):
        bad = rows()
        bad[0] = [0.0, 0.0, 1e-300, 0.0]
        self.assertRaises(AssertionError, blob, RATES, bad)

    def test_oracle_rejects_a_non_zero_rate_zero_row(self):
        bad = rows()
        bad[0][1] = -1.0
        self.assertRaises(AssertionError, net, RATES, bad)

    def test_writer_requires_the_table_to_start_at_zero(self):
        self.assertRaises(AssertionError, blob, [40, 120, 200, 240], rows())

    def test_writer_requires_ascending_rates(self):
        self.assertRaises(AssertionError, blob, [0, 120, 40, 200], rows())

    def test_rate_zero_adds_nothing_so_a_silent_request_stays_silent(self):
        """The property ACC-2 actually asserts, run through the kernel."""
        spikes, _first = okernel.run(net(RATES, rows(scale=1e6)), 1, 0, 200)
        self.assertEqual(sum(spikes), 0)

    def test_a_non_zero_row_would_have_fired_neurons(self):
        """The previous test would pass trivially if the bias never mattered;
        this shows the same network firing when a non-zero row is selected."""
        spikes, _first = okernel.run(net(RATES, rows(scale=1e6)), 1, 200, 200)
        self.assertGreater(sum(spikes), 0)


class Header(unittest.TestCase):

    def test_nbias_and_offset_are_written(self):
        b = blob(RATES, rows())
        nbias = struct.unpack_from(">I", b, L.NETHDR["nbias"][1])[0]
        off = struct.unpack_from(">I", b, L.NETHDR["offbias"][1])[0]
        self.assertEqual(nbias, len(RATES))
        self.assertEqual(off % L.NET_ALIGN, 0)
        self.assertEqual(
            list(struct.unpack_from(">%dI" % nbias, b, off)), RATES)

    def test_absent_table_writes_zeroes(self):
        b = blob()
        self.assertEqual(
            struct.unpack_from(">I", b, L.NETHDR["nbias"][1])[0], 0)
        self.assertEqual(
            struct.unpack_from(">I", b, L.NETHDR["offbias"][1])[0], 0)

    def test_version_is_one_one(self):
        b = blob(RATES, rows())
        self.assertEqual(struct.unpack_from(">H", b, L.NETHDR["vmajor"][1])[0], 1)
        self.assertEqual(struct.unpack_from(">H", b, L.NETHDR["vminor"][1])[0], 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
