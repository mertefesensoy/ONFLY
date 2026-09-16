# -*- coding: utf-8 -*-
"""D-312: the external-clock guard on ACC-6.

WHAT IS BEING GUARDED, AND WHY A TEST IS NOT OBVIOUSLY NEEDED

`tools/mvsrun.py` reads ACC-6 from two numbers MVS reports: the STEP2
CPU time in IEF374I, and the step's own elapsed time. Both are derived
from a timer Hercules drives off the host clock, so across a host sleep
they advance while nothing executes. `mvsprf.trust()` records the
measurement that proved it: a contaminated job reported
`CPU 61MIN 21.92SEC` against 61 minutes 32 seconds elapsed -- a ratio of
1.00 -- with roughly 38 of those minutes spent in Modern Standby.

The tempting guard, comparing guest CPU against guest elapsed, is
therefore worthless. The real one compares host CPU charged to the
Hercules *process* against host wall clock, and refuses below 70% of one
core.

The reason this needs a test is that the guard's failure mode is
**silence**. If `herc_cpu()` returns None on some host -- no Hercules
process, a PowerShell that answers differently, a timeout -- an
unguarded implementation would sail past and certify nothing while
appearing to certify. So what is pinned here is that it REFUSES: on a
sleep, and on an unreadable clock.

These tests call trust() directly with synthetic numbers. They need no
mainframe, no Hercules and no network, and they run in milliseconds.

Run:  python tests/test_trust.py
"""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import mvsprf                                                 # noqa: E402


class Refuses(unittest.TestCase):
    """The cases where a timing result must not be believed."""

    def test_a_run_that_slept_is_rejected(self):
        # The real shape of the contaminated run: the guest believes it
        # worked for the whole hour, the host charged Hercules for a
        # fraction of it.
        self.assertFalse(mvsprf.trust(1000.0, 1000.0 + 22.0 * 60,
                                      61.0 * 60 + 32))

    def test_an_unreadable_clock_is_rejected_not_ignored(self):
        # The silent failure this test exists for.
        self.assertFalse(mvsprf.trust(None, 500.0, 300.0))
        self.assertFalse(mvsprf.trust(500.0, None, 300.0))
        self.assertFalse(mvsprf.trust(None, None, 300.0))

    def test_just_below_the_threshold_is_rejected(self):
        # 69% of one core.
        self.assertFalse(mvsprf.trust(0.0, 69.0, 100.0))

    def test_a_host_that_did_almost_nothing_is_rejected(self):
        self.assertFalse(mvsprf.trust(0.0, 1.0, 300.0))


class Certifies(unittest.TestCase):
    """The cases where the host really did execute the guest."""

    def test_a_compute_bound_run_is_certified(self):
        self.assertTrue(mvsprf.trust(0.0, 95.0, 100.0))

    def test_just_above_the_threshold_is_certified(self):
        # 71% of one core: above the 0.70 floor.
        self.assertTrue(mvsprf.trust(0.0, 71.0, 100.0))

    def test_the_measured_acc6_run_is_certified(self):
        # VL-102's real figures: 188.29 s of host CPU over 220.3 s of
        # host wall clock, ratio 0.855.  If the threshold is ever raised
        # above that, this is what will say so.
        self.assertTrue(mvsprf.trust(8386.44, 8386.44 + 188.29, 220.3))


class ItIsAFloorNotACeiling(unittest.TestCase):
    """The limit the guard's own docstring states, pinned so it is not
    forgotten: it detects a host that STOPPED, not one that was slow."""

    def test_a_slow_but_busy_host_is_still_certified(self):
        # Hercules got a full core the whole time; that it may have been
        # a slow core is not something this check can see, and ACC-6's
        # bound is what catches that instead.
        self.assertTrue(mvsprf.trust(0.0, 600.0, 600.0))


if __name__ == "__main__":
    unittest.main(verbosity=2)
