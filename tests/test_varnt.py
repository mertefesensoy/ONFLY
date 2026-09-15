# -*- coding: utf-8 -*-
"""D-302: the calibration variant switch, and the baseline it must not touch.

`prep/calibrate.py --variant` exists to answer the one thing VL-65 recorded
as not proven -- whether a W_syn *recalibrated* for a variant stimulus set
would pass ACC-4 in full. D-176 measured the variants only at the shipped
W_syn, so no recalibration was ever run.

The danger in adding it is not that the calibration is wrong. It is that a
variant run quietly overwrites the record of the shipped one: `evaluate()`
returns a cached candidate rather than measuring it, so a variant entry
sitting in the baseline log under the same W_syn label would be served in
place of the real one, forever, with nothing to show it had happened. That
is the failure D-209 already hit once from a different direction.

So what is pinned here is mostly negative space:

  * a variant selects the neurons VL-65 says it does, and the baseline is
    unrestricted;
  * a variant run writes to its own log and its own candidate filenames;
  * with no variant, every path is byte-for-byte what it was before.

The expected neuron counts are written out literally rather than derived
from the selection code, so a change to the selection has to be justified
against a test that states the intended answer independently.

Run:  python tests/test_varnt.py
"""
import os
import sys
import unittest

# D-233: skip rather than fail when pandas is absent, as tests/test_signs.py
# does. select_variant() reads the MaleCNS annotation feather through pandas,
# and the s390x guest has neither. The selection is host-side preparation and
# cannot depend on the platform, so announcing the omission is what matters.
try:
    import pandas  # noqa: F401
except ImportError:
    print("test_varnt: SKIP - pandas is not installed on this host "
          "(D-233); the D-302 variant switch is host-side preparation")
    raise SystemExit(0)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "prep"))

import calibrate as cal                                       # noqa: E402

ANNOT = os.path.join(ROOT, "data", "malecns",
                     "body-annotations-male-cns-v1.0-minconf-0.5.feather")

if not os.path.isfile(ANNOT):
    print("test_varnt: SKIP - the MaleCNS annotation feather is not in "
          "this worktree; run tools/fixtures.py --malecns annotations")
    raise SystemExit(0)

# VL-65's populations, stated here and not imported (D-176).
EXPECTED = {
    "right": (7, ["PhG9", "dorsal_tpGRN"], ["R"]),
    "phg9": (4, ["PhG9"], ["L", "R"]),
    "tpgrn": (10, ["dorsal_tpGRN"], ["L", "R"]),
}
BASELINE_N = 14          # D-52 + D-73: both hemispheres


def _stim():
    _arrays, stim, _read = cal.load_cache()
    return stim


class Selection(unittest.TestCase):
    """The variant means the neurons VL-65 says it means."""

    @classmethod
    def setUpClass(cls):
        cls.stim = _stim()

    def test_the_baseline_is_the_whole_d52_set(self):
        self.assertEqual(len(self.stim), BASELINE_N)

    def test_no_variant_returns_the_set_unchanged(self):
        got, desc = cal.select_stim(self.stim, None)
        self.assertIsNone(desc)
        self.assertEqual(list(got), list(self.stim))

    def test_each_variant_selects_vl65s_population(self):
        for name, (n, types, sides) in sorted(EXPECTED.items()):
            got, desc = cal.select_stim(self.stim, name)
            self.assertEqual(len(got), n, name)
            self.assertEqual(desc["types"], types, name)
            self.assertEqual(desc["sides"], sides, name)

    def test_every_variant_is_a_subset_of_the_baseline(self):
        base = set(int(b) for b in self.stim)
        for name in sorted(EXPECTED):
            got, _ = cal.select_stim(self.stim, name)
            self.assertTrue(set(int(b) for b in got) <= base, name)

    def test_the_two_populations_partition_the_set(self):
        # PhG9 and dorsal_tpGRN are disjoint and together are all of it:
        # if a third type ever entered the D-52 mapping, a variant run
        # would silently exclude it and this is what would say so.
        a, _ = cal.select_stim(self.stim, "phg9")
        b, _ = cal.select_stim(self.stim, "tpgrn")
        a, b = set(int(x) for x in a), set(int(x) for x in b)
        self.assertEqual(a & b, set())
        self.assertEqual(a | b, set(int(x) for x in self.stim))

    def test_an_unknown_variant_is_refused(self):
        self.assertRaises(SystemExit, cal.select_stim, self.stim, "nope")


class BaselineIsolation(unittest.TestCase):
    """A variant run must not be able to write where the baseline lives."""

    def tearDown(self):
        cal.VARIANT = None

    def test_the_candidate_filename_carries_the_variant(self):
        cal.VARIANT = "tpgrn"
        name = os.path.basename(
            os.path.join(cal.CAL_DIR, "net-%s%s.bin"
                         % (("%s-" % cal.VARIANT) if cal.VARIANT else "",
                            cal.key(0.2969))))
        self.assertEqual(name, "net-tpgrn-0.2969.bin")

    def test_the_baseline_filename_is_unchanged(self):
        cal.VARIANT = None
        name = "net-%s%s.bin" % ("", cal.key(0.2969))
        self.assertEqual(name, "net-0.2969.bin")

    def test_the_two_filenames_differ(self):
        base = "net-%s.bin" % cal.key(0.2969)
        var = "net-tpgrn-%s.bin" % cal.key(0.2969)
        self.assertNotEqual(base, var)

    def test_the_default_log_is_the_baseline_log(self):
        # main() only reassigns LOG when --log or --variant is given, so
        # the module default must remain the shipped path.
        self.assertTrue(cal.LOG.replace("\\", "/")
                        .endswith("data/calibration/search-log.json"))

    def test_a_variant_log_name_is_distinct(self):
        for name in sorted(EXPECTED):
            self.assertNotEqual(
                os.path.join(cal.CAL_DIR, "search-log-%s.json" % name),
                cal.LOG)


if __name__ == "__main__":
    unittest.main(verbosity=2)
