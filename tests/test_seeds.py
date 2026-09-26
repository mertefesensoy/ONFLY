# -*- coding: utf-8 -*-
"""TP-09: the TBD-06 seed-sensitivity tool states the criteria correctly.

WHY THIS TEST EXISTS
--------------------
`prep/seeds.py` answers "how many seeds per rate" by asking how often each
acceptance clause would change its verdict.  To do that it has to evaluate
ACC-1 and ACC-3 itself, thousands of times per candidate seed count, on
resampled data -- and that means a SECOND implementation of two criteria that
already have one.

D-289 is the cautionary case.  `prep/extract.py --acc3-file` had been written
before D-202 amended ACC-3 and still tested the rate the criterion now
excludes, so its headline said FAIL while every rate ACC-3 actually tests
passed.  That is worse than a wrong number: a tool whose verdict contradicts
the requirement it names.  The conclusion drawn there was that one criterion
should have one implementation.

Where `seeds.py` can share, it shares -- D-202's exclusion rule is asked of
`extract.acc3_excluded()`, and the tolerances and the 90% fraction are
imported rather than retyped.  What cannot be shared is the verdict itself,
because `extract.py` computes it over a list of runs and `seeds.py` needs it
over a (rate, B, n) array of resamples.  So this test pins the array form
against the recorded artefacts the list form produced:

  * ACC-1's verdict, per rate and overall, must equal `acc1-candidate.json`,
    which is VL-105's record.
  * ACC-3's verdict, per rate and overall, must equal `acc3-srext.json`,
    which is VL-98's record -- including which rate D-202 excludes.

If the array form ever drifts from the criterion, these fail with the rate
named, rather than a seed-count recommendation quietly resting on the wrong
test.

Two further properties are pinned because getting them wrong would silently
misreport the answer rather than break anything:

  * The correlation bracket is ordered.  |s_full - s_sub| <= sqrt(s_sub^2 +
    s_full^2) must hold at every rate; if it ever did not, the "best case"
    column would be worse than the bound and the table would read backwards.
  * The bootstrap is reproducible.  The generator is seeded from a constant
    recorded in the output, so two analyses of one sweep must agree exactly.

Everything here reads committed artefacts, so it runs on a bare checkout with
no network fixtures and no engine build.

Run:  python tests/test_seeds.py
"""
import ast
import io
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "prep"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import onfres  # noqa: E402

# P-41 E5: this import used to be unconditional, so a host without numpy
# failed here with an ImportError rather than skipping as D-233 intends for
# the prep tests.
try:
    import numpy as np  # noqa: E402
except ImportError:
    onfres.skip("test_seeds/numpy", "numpy is not installed on this host "
                "(D-233); the TBD-06 seed tool is host-side preparation")
    raise SystemExit(0)

import seeds as S  # noqa: E402
import extract as ext  # noqa: E402

CAL = os.path.join(ROOT, "data", "calibration")
ACC1 = os.path.join(CAL, "acc1-candidate.json")
ACC3 = os.path.join(CAL, "acc3-srext.json")
ACC4 = os.path.join(CAL, "acc4.json")
SWEEP = os.path.join(CAL, "seeds.json")


def load(path):
    with open(path) as fh:
        return json.load(fh)


def sweep_rates(doc, first=None):
    """The per-seed subcircuit rates as a (rate, n) array, optionally cut."""
    rows = [doc["per_rate"][str(r)] for r in S.VAL_RATES]
    if first is not None:
        rows = [row[:first] for row in rows]
    return np.array(rows, dtype=float)


class TestClausesMatchTheRecords(unittest.TestCase):
    """The array form of each clause reproduces the recorded verdict."""

    @classmethod
    def setUpClass(cls):
        for p in (ACC1, ACC3, ACC4, SWEEP):
            if not os.path.isfile(p):
                raise unittest.SkipTest("missing %s" % os.path.basename(p))
        cls.acc1 = load(ACC1)
        cls.acc3 = load(ACC3)
        cls.full = load(ACC4)
        cls.doc = load(SWEEP)
        cls.n = len(cls.acc1["seeds"])
        # The recorded run used seeds 1..30; the sweep starts at the same
        # seed and is a superset, so its first n columns are those runs.
        cls.rates = sweep_rates(cls.doc, cls.n)

    def test_sweep_reproduces_the_recorded_runs(self):
        """Seeds 1..30 of the sweep are the recorded runs, to the last bit."""
        self.assertEqual(self.doc["seeds"][:self.n], self.acc1["seeds"])
        for i, r in enumerate(S.VAL_RATES):
            rec = self.acc1["per_rate"][str(r)]
            self.assertAlmostEqual(float(self.rates[i].mean()),
                                   rec["mean_hz"], places=12,
                                   msg="%d Hz mean" % r)
            self.assertEqual(int((self.rates[i] > 0.0).sum()),
                             rec["seeds_with_mn9_spike"],
                             "%d Hz seeds with a spike" % r)

    def test_acc1_verdict_matches_vl105(self):
        applies = {r: self.full["per_rate"][str(r)]["reference_hz"] > 0.0
                   for r in S.VAL_RATES}
        for i, r in enumerate(S.VAL_RATES):
            self.assertEqual(applies[r],
                             self.acc1["per_rate"][str(r)]["applies"],
                             "%d Hz applicability" % r)
        rates = self.rates[:, None, :]
        spiking = (self.rates > 0.0).astype(float)[:, None, :]
        got = bool(S.acc1_verdict(rates, spiking, applies)[0])
        self.assertEqual(got, self.acc1["acc1_pass"])

    def test_acc1_fails_when_a_rate_falls_below_the_fraction(self):
        """The clause is not passing by accident: break it and it fails."""
        applies = {r: self.full["per_rate"][str(r)]["reference_hz"] > 0.0
                   for r in S.VAL_RATES}
        rates = self.rates.copy()
        i = S.VAL_RATES.index(40)
        # Silence a fifth of the seeds at 40 Hz: 80% < 90%.
        rates[i, :self.n // 5] = 0.0
        got = bool(S.acc1_verdict(rates[:, None, :],
                                  (rates > 0.0).astype(float)[:, None, :],
                                  applies)[0])
        self.assertFalse(got)

    def test_acc3_verdict_and_exclusion_match_vl98(self):
        excluded = {r: ext.acc3_excluded(self.full, r) for r in S.VAL_RATES}
        for r in S.VAL_RATES:
            self.assertEqual(excluded[r],
                             self.acc3["per_rate"][str(r)]["excluded"],
                             "%d Hz exclusion" % r)
        self.assertEqual([r for r in S.VAL_RATES if excluded[r]],
                         self.acc3["acc3_excluded_rates"])
        fm = np.array([self.full["per_rate"][str(r)]["onfly_mean_hz"]
                       for r in S.VAL_RATES], dtype=float)
        sub = self.rates.mean(axis=1)[:, None]
        got = bool(S.acc3_verdict(sub, fm[:, None], excluded)[0])
        self.assertEqual(got, self.acc3["acc3_pass"])

    def test_acc3_per_rate_matches_vl98(self):
        """Each rate's own verdict, excluded ones included, as recorded."""
        excluded = {r: ext.acc3_excluded(self.full, r) for r in S.VAL_RATES}
        for i, r in enumerate(S.VAL_RATES):
            rec = self.acc3["per_rate"][str(r)]
            one = {q: (q != r) for q in S.VAL_RATES}   # test this rate alone
            fm = np.array([self.full["per_rate"][str(q)]["onfly_mean_hz"]
                           for q in S.VAL_RATES], dtype=float)
            got = bool(S.acc3_verdict(self.rates.mean(axis=1)[:, None],
                                      fm[:, None], one)[0])
            self.assertEqual(got, rec["pass"], "%d Hz verdict" % r)
            self.assertAlmostEqual(float(self.rates[i].mean()),
                                   rec["sub_mean_hz"], places=12)
            self.assertEqual(excluded[r], rec["excluded"])


class TestAnalysisProperties(unittest.TestCase):
    """Properties the report's shape depends on."""

    @classmethod
    def setUpClass(cls):
        for p in (ACC4, SWEEP):
            if not os.path.isfile(p):
                raise unittest.SkipTest("missing %s" % os.path.basename(p))
        cls.full = load(ACC4)
        cls.doc = load(SWEEP)

    def test_correlation_bracket_is_ordered(self):
        """|s_full - s_sub| <= sqrt(s_sub^2 + s_full^2) at every rate."""
        c = self.doc["analysis"]["acc3_campaign"]["per_rate"]
        for r in S.VAL_RATES:
            e = c[str(r)]
            self.assertLessEqual(e["diff_sd_correlated_hz"],
                                 e["diff_sd_independent_hz"] + 1e-12,
                                 "%d Hz bracket" % r)
            self.assertGreaterEqual(e["diff_sd_correlated_hz"], 0.0)

    def test_pass_probability_rises_with_the_seed_count(self):
        """More seeds never makes the re-measurement less likely to pass."""
        j = self.doc["analysis"]["acc3_campaign"]["joint"]
        ns = self.doc["analysis"]["candidate_n"]
        for name in ("p_pass_floor", "p_pass_bound"):
            vals = [j[str(n)][name] for n in ns]
            for a, b in zip(vals, vals[1:]):
                self.assertLessEqual(a, b + 1e-12, name)

    def test_bootstrap_is_reproducible(self):
        """Two analyses of one sweep agree exactly: the seed is pinned."""
        a = S.analyse(self.doc["per_rate"], self.full, self.doc["seeds"])
        b = S.analyse(self.doc["per_rate"], self.full, self.doc["seeds"])
        for n in a["candidate_n"]:
            for k in ("acc1_flip_frac", "acc3_fixedref_flip_frac"):
                self.assertEqual(a["per_n"][str(n)][k],
                                 b["per_n"][str(n)][k], "%s at n=%d" % (k, n))

    def test_phi_is_the_normal_cdf(self):
        self.assertAlmostEqual(S.phi(0.0), 0.5, places=12)
        self.assertAlmostEqual(S.phi(1.959963985), 0.975, places=6)
        self.assertAlmostEqual(S.phi(-1.959963985), 0.025, places=6)
        self.assertTrue(all(S.phi(z) <= S.phi(z + 0.1)
                            for z in [x / 10.0 for x in range(-40, 40)]))

    def test_acc4_shape_gets_easier_with_more_seeds(self):
        """The bar falls as n^-0.5 and so does the noise; the drop does not.

        Stated as a test because the opposite is the natural guess, and a
        report that got this backwards would recommend fewer seeds for the
        wrong reason.  It holds only while the measured curve rises, which
        the first assertion checks rather than assumes.
        """
        a = self.doc["analysis"]["acc4"]
        m = a["means_hz"]
        self.assertTrue(all(x < y for x, y in zip(m, m[1:])),
                        "the measured curve is not monotonically rising; "
                        "the claim below does not apply to it")
        ns = self.doc["analysis"]["candidate_n"]
        p = [a["per_n"][str(n)]["p_shape_fail"] for n in ns]
        for x, y in zip(p, p[1:]):
            self.assertLessEqual(y, x + 1e-15)


class TestCriterionHasOneImplementation(unittest.TestCase):
    """ACC-3's rule lives in one place, and every verdict path calls it.

    D-289 was the first time one criterion with two implementations drifted:
    `--acc3-file` predated D-202's amendment and printed FAIL while every rate
    ACC-3 actually tests passed.  D-360 is the second: `acc3()` had gone
    through both D-202 and D-357 without being updated for either, so it
    tested the 10 Hz rate the criterion excludes and would have escalated a
    selection that passes.

    Twice is a pattern, so the property is pinned here rather than left to a
    reader noticing it a third time.
    """

    #: The functions that produce an ACC-3 VERDICT.  Each must go through
    #: acc3_row(), which is where D-202's exclusion and D-357's reporting
    #: live.
    VERDICT_PATHS = ("acc3", "acc3_file", "acc3_eval")

    #: Every function permitted to compute ACC-3's tolerance itself.
    #: acc3_row is the criterion; `diag` (D-180) and `closure` (D-182) are
    #: DIAGNOSTICS that borrow the same arithmetic for exploration and were
    #: deliberately left alone when D-360 fixed the verdict path -- the owner
    #: authorised the verdict path and not the diagnostics.  Listing them
    #: here states that boundary instead of hiding it: a fourth site added
    #: later fails this test and forces the same decision to be made again.
    TOLERANCE_SITES = {"acc3_row", "diag", "closure"}

    @classmethod
    def setUpClass(cls):
        with io.open(os.path.join(ROOT, "prep", "extract.py"),
                     encoding="utf-8") as fh:
            cls.src = fh.read()
        cls.tree = ast.parse(cls.src)
        cls.funcs = {n.name: n for n in ast.walk(cls.tree)
                     if isinstance(n, ast.FunctionDef)}

    def body(self, name):
        n = self.funcs[name]
        return "\n".join(self.src.split("\n")[n.lineno - 1:n.end_lineno])

    def test_every_verdict_path_goes_through_acc3_row(self):
        for name in self.VERDICT_PATHS:
            self.assertIn(name, self.funcs, "%s has gone" % name)
            self.assertIn("acc3_row(", self.body(name),
                          "%s no longer goes through acc3_row(), so D-202's "
                          "exclusion and D-357's reporting may not apply to "
                          "it -- this is how D-289 and D-360 happened" % name)

    def test_acc3_row_is_the_only_new_place_the_tolerance_is_computed(self):
        found = set()
        for name, n in self.funcs.items():
            if "REL_TOL *" in self.body(name):
                found.add(name)
        self.assertEqual(
            found, self.TOLERANCE_SITES,
            "the set of functions computing ACC-3's tolerance changed to %s; "
            "if a new one is an ACC-3 VERDICT it must call acc3_row() "
            "instead, and if it is a diagnostic it must be added to "
            "TOLERANCE_SITES deliberately" % sorted(found))

    def test_acc3_row_applies_d202_and_reports_p18(self):
        """On the recorded data: 10 Hz excluded, 40 Hz within precision."""
        for p in (ACC3, ACC4):
            if not os.path.isfile(p):
                self.skipTest("missing %s" % os.path.basename(p))
        full, rec = load(ACC4), load(ACC3)
        for r in S.VAL_RATES:
            e = rec["per_rate"][str(r)]
            row = ext.acc3_row(full, r, e["sub_mean_hz"])
            self.assertEqual(row["excluded"], e["excluded"],
                             "%d Hz exclusion" % r)
            self.assertEqual(row["pass"], e["pass"], "%d Hz verdict" % r)
            self.assertAlmostEqual(row["tolerance_hz"], e["tolerance_hz"],
                                   places=12)
            # P-18 (D-357): the reference's own precision travels with the
            # result, and the margin is what it must be read against.
            self.assertIsNotNone(row["reference_se_hz"], "%d Hz se" % r)
            self.assertAlmostEqual(
                row["margin_hz"],
                row["tolerance_hz"] - abs(row["difference_hz"]), places=12)
        r40 = ext.acc3_row(full, 40, rec["per_rate"]["40"]["sub_mean_hz"])
        self.assertTrue(r40["within_reference_precision"],
                        "40 Hz margin %.4f should be below the reference's "
                        "standard error %.4f (VL-114)"
                        % (r40["margin_hz"], r40["reference_se_hz"]))
        note = ext.acc3_precision_note(rec["per_rate"], S.VAL_RATES)
        self.assertIsNotNone(note)
        self.assertIn("40 Hz", note)


if __name__ == "__main__":
    # D-555: skips are reported through onfres so that make test counts them.
    sys.exit(onfres.unittest_main("test_seeds"))
