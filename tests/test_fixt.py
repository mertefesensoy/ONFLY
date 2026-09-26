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
import contextlib
import hashlib
import inspect
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "prep"))

import fixtures                                        # noqa: E402
import onfres                                          # noqa: E402

# D-591: prep/extract.py imports numpy at module level, so on a checkout
# without the packages of requirements.txt this import used to end the
# whole file in ModuleNotFoundError.  Only the two classes that call
# `extract` need it; they skip through onfres, and the rest still run.
try:
    import extract                                     # noqa: E402
except ImportError:
    extract = None
NO_EXTRACT = ("prep/extract.py imports numpy and this host has none "
              "(D-233, D-591)")


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


@unittest.skipIf(extract is None, NO_EXTRACT)
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


@unittest.skipIf(extract is None, NO_EXTRACT)
class AdmitRefuses(unittest.TestCase):
    """P-41 E7 (replication X3): `--admit` refuses BEFORE it writes.

    It used to write the srext .bin first and compare afterwards, and it
    skipped the comparison without a word when the measured artifact was
    absent, so an admission could overwrite the shipped network unverified.
    """

    def test_an_absent_comparand_refuses_and_names_its_producer(self):
        missing = os.path.join(tempfile.gettempdir(), "onfly-no-such.bin")
        with self.assertRaises(SystemExit) as cm:
            extract.verify_comparand(missing, "0" * 64)
        self.assertIn("--constbias", str(cm.exception))
        self.assertIn("nothing was written", str(cm.exception))

    def test_a_differing_comparand_refuses(self):
        fd, path = tempfile.mkstemp()
        os.close(fd)
        try:
            io.open(path, "wb").write(b"measured")
            other = hashlib.sha256(b"emitted").hexdigest()
            with self.assertRaises(SystemExit) as cm:
                extract.verify_comparand(path, other)
            self.assertIn("nothing was written", str(cm.exception))
        finally:
            os.unlink(path)

    def test_a_matching_comparand_passes(self):
        fd, path = tempfile.mkstemp()
        os.close(fd)
        try:
            io.open(path, "wb").write(b"same")
            with contextlib.redirect_stdout(io.StringIO()):
                extract.verify_comparand(path,
                                         hashlib.sha256(b"same").hexdigest())
        finally:
            os.unlink(path)

    def test_admit_verifies_before_it_writes(self):
        src = inspect.getsource(extract.admit)
        check = src.find("verify_comparand(")
        write = src.find('io.open(path, "wb")')
        self.assertTrue(0 <= check < write,
                        "admit() must verify (at %d) before it writes the "
                        "network (at %d)" % (check, write))


class Distributed(unittest.TestCase):
    """P-41 E3, D-545: `--from`, the distributed set, NOT DISTRIBUTED."""

    NETS = {"alpha": (b"alpha network bytes", True),
            "beta": (b"beta network", True),
            "gamma": (b"gamma, regenerate-only", False),
            "delta": (b"delta, regenerate-only", False)}

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="onfly_fixt_")
        self.netdir = os.path.join(self.tmp, "networks")
        self.stage = os.path.join(self.tmp, "stage")
        self.empty = os.path.join(self.tmp, "empty")
        for d in (self.netdir, self.stage, self.empty):
            os.makedirs(d)
        nets = {}
        for key, (blob, dist) in self.NETS.items():
            name = "onfnet-%s.bin" % key
            entry = {"file": name, "bytes": len(blob),
                     "crc32": "%08X" % (zlib.crc32(blob) & 0xFFFFFFFF),
                     "sha256": hashlib.sha256(blob).hexdigest()}
            if dist:
                entry["distributed"] = True
                io.open(os.path.join(self.stage, name), "wb").write(blob)
            nets[key] = entry
        self.manifest = os.path.join(self.netdir, "MANIFEST.json")
        io.open(self.manifest, "w", encoding="utf-8").write(
            json.dumps({"networks": nets}))
        self.notice = os.path.join(self.netdir, "NETWORKS-NOTICE.md")
        io.open(self.notice, "w", encoding="utf-8").write("THE NOTICE\n")
        self.saved = (fixtures.NETDIR, fixtures.MANIFEST, fixtures.NOTICE)
        fixtures.NETDIR, fixtures.MANIFEST, fixtures.NOTICE = \
            self.netdir, self.manifest, self.notice
        self.env = os.environ.pop("ONFLY_FIXTURES", None)

    def tearDown(self):
        fixtures.NETDIR, fixtures.MANIFEST, fixtures.NOTICE = self.saved
        if self.env is not None:
            os.environ["ONFLY_FIXTURES"] = self.env
        else:
            os.environ.pop("ONFLY_FIXTURES", None)
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_main(self, argv):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = fixtures.main(argv)
        return rc, buf.getvalue()

    def test_from_places_the_distributed_set_and_prints_the_notice(self):
        rc, out = self.run_main(["--from", self.stage])
        self.assertEqual(rc, 0, out)
        for key in ("alpha", "beta"):
            self.assertTrue(os.path.isfile(
                os.path.join(self.netdir, "onfnet-%s.bin" % key)))
        self.assertEqual(out.count(
            "NOT DISTRIBUTED (regenerate with prep/emit.py)"), 2, out)
        self.assertIn("THE NOTICE", out)

    def test_check_passes_with_only_the_distributed_set(self):
        self.run_main(["--from", self.stage])
        rc, out = self.run_main(["--check"])
        self.assertEqual(rc, 0, out)
        self.assertEqual(out.count(" OK "), 2, out)
        self.assertEqual(out.count("NOT DISTRIBUTED"), 2, out)

    def test_check_fails_when_a_distributed_network_is_absent(self):
        rc, out = self.run_main(["--check"])
        self.assertEqual(rc, 1, out)

    def test_a_wrong_undistributed_file_still_fails(self):
        # Never trust a filename: an undistributed network may be absent,
        # but one that is present must still be the file the manifest names.
        self.run_main(["--from", self.stage])
        io.open(os.path.join(self.netdir, "onfnet-gamma.bin"), "wb").write(
            b"stale bytes")
        rc, out = self.run_main(["--check"])
        self.assertEqual(rc, 1, out)

    def test_from_searches_only_the_directory_it_names(self):
        os.environ["ONFLY_FIXTURES"] = self.stage
        rc, out = self.run_main(["--from", self.empty])
        self.assertEqual(rc, 1, out)
        self.assertFalse(os.path.isfile(
            os.path.join(self.netdir, "onfnet-alpha.bin")))


class Notice(unittest.TestCase):
    """The network notice names exactly the distributed files, correctly."""

    def test_the_notice_table_matches_the_manifest(self):
        man = json.loads(io.open(os.path.join(
            ROOT, "data", "networks", "MANIFEST.json"),
            encoding="utf-8").read())["networks"]
        text = io.open(os.path.join(ROOT, "data", "networks",
                                    "NETWORKS-NOTICE.md"),
                       encoding="utf-8").read()
        rows = {}
        for line in text.splitlines():
            cells = [c.strip().strip("`") for c in line.strip("|").split("|")]
            if len(cells) == 3 and cells[0].endswith(".bin"):
                rows[cells[0]] = (int(cells[1].replace(",", "")), cells[2])
        want = dict((e["file"], (e["bytes"], e["sha256"]))
                    for e in man.values() if e.get("distributed") is True)
        self.assertEqual(rows, want)


if __name__ == "__main__":
    # D-555: skips are reported through onfres so that make test counts them.
    sys.exit(onfres.unittest_main("test_fixt"))
