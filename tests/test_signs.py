# -*- coding: utf-8 -*-
"""TP-01: sign and weight assignment (FR-PRP-03, SR-MOD-05, D-54, D-55).

Two layers, deliberately:

  * Unit tests on a small hand-built fixture, so every branch of the mapping is
    exercised in a second and a failure points at one rule.
  * A spot check against the real MaleCNS data, so the fixture cannot drift away
    from what the pipeline actually processes.

The fixture is not a copy of the production mapping: expected signs are written
out literally, so a change to NT_SIGN has to be justified against a test that
states the intended answer independently. A test that imported the mapping and
compared it to itself would pass no matter what the mapping said.

Run:  python tests/test_signs.py
"""
import os
import sys
import unittest

# D-233: skip rather than fail when pandas is absent, the same way
# tests/run_cob.py skips when no cobc is found (D-156).  The s390x guest
# Phase D runs the suite in has no pandas, and this test exercises a
# pure-Python preparation pipeline whose result cannot depend on the host --
# so what matters is that the omission is announced, not that it is
# prevented.
try:
    import pandas as pd
except ImportError:
    print("test_signs: SKIP - pandas is not installed on this host "
          "(D-233); FR-PRP-03 sign assignment is host-side and is checked where it is")
    raise SystemExit(0)

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "prep"))

import signs  # noqa: E402


class TestMapping(unittest.TestCase):
    """The mapping itself, stated independently of the module."""

    def test_acetylcholine_is_excitatory(self):
        self.assertEqual(signs.NT_SIGN.get("acetylcholine"), +1)

    def test_gaba_is_inhibitory(self):
        self.assertEqual(signs.NT_SIGN.get("gaba"), -1)

    def test_histamine_is_inhibitory(self):
        self.assertEqual(signs.NT_SIGN.get("histamine"), -1)

    def test_glutamate_is_inhibitory_in_drosophila(self):
        # The one most likely to be got wrong by habit: glutamate is excitatory
        # in vertebrates but inhibitory in the fly through GluCl channels, and
        # it covers about 18% of neurons with a definite prediction (D-54).
        self.assertEqual(signs.NT_SIGN.get("glutamate"), -1)

    def test_monoamines_are_not_in_the_mapping(self):
        for nt in ("dopamine", "octopamine", "serotonin"):
            self.assertNotIn(nt, signs.NT_SIGN,
                             "%s is modulatory and must be excluded (D-54)" % nt)

    def test_unclear_is_not_in_the_mapping(self):
        self.assertNotIn("unclear", signs.NT_SIGN)

    def test_mapping_has_no_unexpected_entries(self):
        self.assertEqual(set(signs.NT_SIGN),
                         {"acetylcholine", "gaba", "glutamate", "histamine"})


class TestAssignment(unittest.TestCase):
    """Apply the mapping to a fixture covering every case."""

    def setUp(self):
        # pre 1 ACh (+1), 2 GABA (-1), 3 glutamate (-1), 4 histamine (-1),
        # 5 dopamine (excluded), 6 unclear (excluded), 7 absent (excluded)
        self.nt = pd.Series(
            {1: "acetylcholine", 2: "gaba", 3: "glutamate", 4: "histamine",
             5: "dopamine", 6: "unclear"})
        self.w = pd.DataFrame({
            "body_pre":  [1, 2, 3, 4, 5, 6, 7],
            "body_post": [10, 10, 10, 10, 10, 10, 10],
            "weight":    [5, 7, 11, 13, 17, 19, 23],
        })

    def assign(self):
        pre_nt = self.w["body_pre"].map(self.nt)
        w = self.w.assign(pre_nt=pre_nt.fillna(""))
        w["sign"] = w["pre_nt"].map(signs.NT_SIGN)
        kept = w[w["sign"].notna()].copy()
        kept["signed_weight"] = kept["weight"] * kept["sign"].astype(int)
        return kept, w[w["sign"].isna()]

    def test_kept_and_dropped_partition_the_input(self):
        kept, dropped = self.assign()
        self.assertEqual(len(kept) + len(dropped), len(self.w))

    def test_only_the_four_mapped_transmitters_survive(self):
        kept, _ = self.assign()
        self.assertEqual(sorted(kept["body_pre"]), [1, 2, 3, 4])

    def test_modulatory_unclear_and_absent_are_dropped(self):
        _, dropped = self.assign()
        self.assertEqual(sorted(dropped["body_pre"]), [5, 6, 7])

    def test_signed_weight_is_count_times_sign(self):
        kept, _ = self.assign()
        got = dict(zip(kept["body_pre"], kept["signed_weight"]))
        # SR-MOD-05: synapse count x sign.  W_syn is NOT applied here; it is a
        # calibrated free parameter (SR-CAL).
        self.assertEqual(got, {1: 5, 2: -7, 3: -11, 4: -13})

    def test_magnitude_is_never_altered_only_the_sign(self):
        kept, _ = self.assign()
        for _, r in kept.iterrows():
            self.assertEqual(abs(r["signed_weight"]), r["weight"])

    def test_dropping_removes_synapses_not_just_pairs(self):
        # The cost of D-55 must be visible as synapses, not only as row counts:
        # a dropped source may carry many synapses.
        _, dropped = self.assign()
        self.assertEqual(int(dropped["weight"].sum()), 17 + 19 + 23)


class TestAgainstRealData(unittest.TestCase):
    """Spot check that the fixture matches the real dataset's vocabulary."""

    @classmethod
    def setUpClass(cls):
        path = os.path.join(ROOT, "data", "malecns",
                            "body-neurotransmitters-male-cns-v1.0.feather")
        if not os.path.exists(path):
            raise unittest.SkipTest("MaleCNS data not retrieved")
        cls.nt = signs.load_nt_by_body()

    def test_every_mapped_name_occurs_in_the_real_data(self):
        present = set(self.nt.unique())
        for name in signs.NT_SIGN:
            self.assertIn(name, present,
                          "%r is in the mapping but not in the dataset; the "
                          "mapping may be using stale vocabulary" % name)

    def test_every_real_transmitter_is_either_mapped_or_deliberately_excluded(self):
        known = (set(signs.NT_SIGN)
                 | set(signs.NT_EXCLUDED_MODULATORY)
                 | set(signs.NT_EXCLUDED_UNKNOWN))
        unexpected = sorted(set(self.nt.unique()) - known)
        self.assertEqual(unexpected, [],
                         "the dataset contains transmitters the mapping does "
                         "not account for: %s. Silently excluding them would "
                         "be a decision nobody made." % unexpected)


if __name__ == "__main__":
    unittest.main(verbosity=2)
