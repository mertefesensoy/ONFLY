# -*- coding: utf-8 -*-
"""D-320: prep/acc4.py cleans up the network it emits.

WHY THIS NEEDED FIXING, AND HOW IT WAS FOUND

`prep/calibrate.py` has always deleted its candidate networks --
`if not keep: os.remove(path)` at the end of evaluate(). `prep/acc4.py`
emits the same 299 MB network through the same `cal.emit_candidate()`
and never deleted it. Every ACC-4 run therefore abandoned 299 MB.

It was found by accident on 2026-09-16: `tools/progress.py` gained the
ability to infer a job's state from the networks on disk, and promptly
reported a file ACC-4 had abandoned 15.8 hours earlier as a job 15.8
hours into its current W_syn point. The leftover was not the bug the
tool was written to find; it was a bug the tool tripped over.

WHAT IS PINNED HERE

Three things, and the third is the one that matters most:

  * it deletes by default;
  * `--keep` keeps, so a run being debugged can retain its exact input;
  * **a failure to delete does not raise.** A three-hour ACC-4 run whose
    science is complete and whose JSON is written must not fail because
    a file was locked or already gone. The cleanup is housekeeping and
    must behave like it.

These call discard() directly with temporary files. No network is
emitted, no run is made, and the test takes milliseconds.

Run:  python tests/test_disc.py
"""
import io
import os
import shutil
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "prep"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import onfres                                                 # noqa: E402

try:
    import pandas  # noqa: F401
except ImportError:
    onfres.skip("test_disc/pandas", "prep/acc4.py imports pandas through "
                "prep/calibrate.py and this host has none (D-233)")
    raise SystemExit(0)

import acc4                                                   # noqa: E402


class Discard(unittest.TestCase):

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="onfly-disc-")
        self.path = os.path.join(self.dir, "net-0.2969.bin")
        io.open(self.path, "wb").write(b"x" * 1024)

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_it_deletes_by_default(self):
        acc4.discard(self.path, keep=False)
        self.assertFalse(os.path.exists(self.path))

    def test_keep_keeps_it(self):
        acc4.discard(self.path, keep=True)
        self.assertTrue(os.path.exists(self.path))

    def test_a_missing_file_does_not_raise(self):
        # The run is over and its JSON is written; a second call, or a
        # file something else removed, must not turn a finished run into
        # a failed one.
        os.remove(self.path)
        acc4.discard(self.path, keep=False)          # must not raise

    def test_an_undeletable_file_does_not_raise(self):
        # A directory in place of the file: os.remove refuses it on every
        # platform, which is a stand-in for the locked-file case that is
        # awkward to arrange portably.
        os.remove(self.path)
        os.mkdir(self.path)
        acc4.discard(self.path, keep=False)          # must not raise
        self.assertTrue(os.path.isdir(self.path))

    def test_keep_on_a_missing_file_does_not_raise(self):
        os.remove(self.path)
        acc4.discard(self.path, keep=True)           # must not raise


class MatchesCalibrate(unittest.TestCase):
    """The two emitters must not diverge in how they clean up."""

    def test_both_tools_offer_keep(self):
        # A --keep in one and not the other is how two tools that emit
        # the same file end up behaving differently under the same
        # instruction.
        import calibrate as cal
        self.assertTrue(hasattr(cal, "emit_candidate"))
        src = io.open(os.path.join(ROOT, "prep", "acc4.py"),
                      encoding="utf-8").read()
        self.assertIn('"--keep"', src)
        csrc = io.open(os.path.join(ROOT, "prep", "calibrate.py"),
                       encoding="utf-8").read()
        self.assertIn('"--keep"', csrc)


if __name__ == "__main__":
    unittest.main(verbosity=2)
