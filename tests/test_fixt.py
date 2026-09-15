# -*- coding: utf-8 -*-
"""`tools/fixtures.py` digests, and `prep/extract.py`'s ACC-3 exclusion.

Two changes made on 2026-09-15 that nothing else in the suite covers.

**Streamed digests.**  `digests()` used to read a whole file into memory.
That could not verify the one file it most needed to: the MaleCNS
connectome weights are 1,051,241,946 bytes and a single read of that size
fails on Windows with `OSError: [Errno 22] Invalid argument`, raised four
frames inside `matches()` and naming neither the file nor its size.  It
now streams in 8 MiB blocks.  Both digests are incremental, so the result
must be **identical** to the whole-file version -- which is the property
tested here, over sizes on both sides of the block boundary.  A
chunked digest that silently differed would make every fixture
"corrupt", and the error it produced would point at the data.

**D-202's exclusion in the D-181 diagnostic.**  `--acc3-file` predates
D-202 and tested all five validation rates, including the one the amended
criterion excludes and reports.  On the shipped `srext` network that made
it print FAIL while every rate ACC-3 tests passed.  D-289 pointed it at
`acc3_excluded()`.  What is pinned here is the RULE, not the verdict:
that exclusion is decided by the reference's own dispersion (sd >= mean)
and not by naming 10 Hz, so it stays honest if a later W_syn or stimulus
set destabilises a different rate -- and that an excluded rate is
reported rather than silently dropped.

Run:

    python tests/test_fixt.py
"""
import hashlib
import io
import os
import sys
import tempfile
import unittest
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "prep"))

import fixtures                                        # noqa: E402
import extract                                         # noqa: E402


def whole_file_digests(path):
    """What `digests()` returned before it was made to stream."""
    data = io.open(path, "rb").read()
    return (len(data),
            "%08X" % (zlib.crc32(data) & 0xFFFFFFFF),
            hashlib.sha256(data).hexdigest())


class Digests(unittest.TestCase):
    """Streaming must be indistinguishable from reading the file whole."""

    def _roundtrip(self, nbytes):
        fd, path = tempfile.mkstemp()
        os.close(fd)
        try:
            # Not zeroes: a CRC over a constant byte is insensitive to
            # block boundaries, which is exactly what this is testing.
            blob = bytes(bytearray((i * 37 + 11) & 0xFF
                                   for i in range(nbytes)))
            with io.open(path, "wb") as fh:
                fh.write(blob)
            self.assertEqual(fixtures.digests(path),
                             whole_file_digests(path),
                             "chunked digests differ at %d bytes" % nbytes)
        finally:
            os.unlink(path)

    def test_empty_file(self):
        self._roundtrip(0)

    def test_one_byte(self):
        self._roundtrip(1)

    def test_spans_several_blocks(self):
        # The point of the test: more than one read, and a final partial
        # block, so an implementation that dropped either would fail.
        self.assertGreater(fixtures.CHUNK, 0)
        self._roundtrip(fixtures.CHUNK * 2 + 12345)

    def test_exactly_one_block(self):
        self._roundtrip(fixtures.CHUNK)

    def test_a_committed_file(self):
        path = os.path.join(ROOT, "data", "networks", "MANIFEST.json")
        if not os.path.isfile(path):
            self.skipTest("no manifest in this checkout")
        self.assertEqual(fixtures.digests(path), whole_file_digests(path))


class Matches(unittest.TestCase):
    """All three checks, not the cheap one alone."""

    def setUp(self):
        fd, self.path = tempfile.mkstemp()
        os.close(fd)
        with io.open(self.path, "wb") as fh:
            fh.write(b"onfly" * 1000)
        size, crc, sha = fixtures.digests(self.path)
        self.want = {"bytes": size, "crc32": crc, "sha256": sha}

    def tearDown(self):
        os.unlink(self.path)

    def test_accepts_the_file_it_describes(self):
        ok, why = fixtures.matches(self.path, self.want)
        self.assertTrue(ok, why)

    def test_rejects_a_wrong_size(self):
        w = dict(self.want, bytes=self.want["bytes"] + 1)
        ok, why = fixtures.matches(self.path, w)
        self.assertFalse(ok)
        self.assertIn("bytes", why)

    def test_rejects_a_wrong_crc(self):
        w = dict(self.want, crc32="DEADBEEF")
        ok, why = fixtures.matches(self.path, w)
        self.assertFalse(ok)
        self.assertIn("CRC", why)

    def test_rejects_a_wrong_sha(self):
        w = dict(self.want, sha256="0" * 64)
        ok, why = fixtures.matches(self.path, w)
        self.assertFalse(ok)
        self.assertIn("SHA-256", why)

    def test_reports_an_absent_file(self):
        ok, why = fixtures.matches(self.path + ".nope", self.want)
        self.assertFalse(ok)
        self.assertEqual(why, "absent")


class Acc3Exclusion(unittest.TestCase):
    """D-202's rule, as D-289 made the diagnostic apply it."""

    @staticmethod
    def _full(**rates):
        return {"per_rate": {str(r): {"onfly_mean_hz": m,
                                      "onfly_sd_hz": sd}
                             for r, (m, sd) in rates.items()}}

    def test_excluded_when_sd_reaches_the_mean(self):
        full = self._full(**{"10": (3.67, 4.22)})
        self.assertTrue(extract.acc3_excluded(full, 10))

    def test_not_excluded_when_the_mean_dominates(self):
        full = self._full(**{"40": (14.35, 8.45)})
        self.assertFalse(extract.acc3_excluded(full, 40))

    def test_the_boundary_is_inclusive(self):
        # ACC-3 as amended excludes a rate whose sd EQUALS its mean:
        # "standard deviation equals or exceeds its mean".
        full = self._full(**{"60": (5.0, 5.0)})
        self.assertTrue(extract.acc3_excluded(full, 60))

    def test_the_rule_is_on_dispersion_not_on_the_rate(self):
        # The point of writing the test on the condition: 10 Hz is
        # excluded on today's data, but nothing may hard-code it.  Give
        # 10 Hz a tight reference and 200 Hz a loose one, and the
        # exclusion must follow the dispersion.
        full = self._full(**{"10": (12.0, 1.0), "200": (4.0, 9.0)})
        self.assertFalse(extract.acc3_excluded(full, 10))
        self.assertTrue(extract.acc3_excluded(full, 200))

    def test_the_shipped_reference_excludes_exactly_one_rate(self):
        path = os.path.join(ROOT, "data", "calibration", "acc4.json")
        if not os.path.isfile(path):
            self.skipTest("no acc4.json in this checkout")
        import json
        full = json.loads(io.open(path, encoding="utf-8").read())
        excl = [r for r in extract.VAL_RATES
                if extract.acc3_excluded(full, r)]
        self.assertEqual(excl, [10],
                         "D-202 should exclude exactly 10 Hz on the "
                         "D-135 seeds, got %s" % excl)


if __name__ == "__main__":
    unittest.main(verbosity=2)
