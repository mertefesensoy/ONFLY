# -*- coding: utf-8 -*-
"""FR-SIM-10 over the Section 8.4 golden suite: the fingerprint must not
depend on the chunk size (D-366, D-367, D-368).

WHAT THIS DISCHARGES, AND WHY IT IS THE SUITE AND NOT A FIXTURE

TBD-19 closed on 2026-09-12 carrying exactly one obligation: D-140 drives a
run in chunks, and the response fingerprint has to be independent of the
chunk size K and of where the boundaries fall. D-318 gave that obligation a
requirement ID, FR-SIM-10, and a test-catalogue entry, TU-10. Both were met
at the ORACLE level by tests/test_chunk.py (VL-107) and left open against the
engine, because engine/src/onfker.c had no chunked entry point at all.

FR-SIM-10's own text says where the engine half has to be shown:

    Phase G must show this against the Section 8.4 golden suite.

That wording is doing real work. The suite is what ACC-5 is defined against --
nineteen fingerprints reproduced across the rows of Section 8.3 -- so showing
chunk invariance anywhere else would leave the question "but does it hold for
the requests the determinism claim actually rests on?" unanswered. D-368 is
why tests/tstgld.c grew a chunk argument rather than a new test program being
written: the suite already runs through onfrq1, which D-224 made the single
shared request sequence, and a second copy of that sequence in a test would
have proved the copy.

WHAT A PASS HERE MEANS, AND WHAT IT DOES NOT

A pass means: for this executable, on this platform with this float backend,
every GOLD and GOUT line of all nineteen requests is BYTE-IDENTICAL at every
chunk size swept, including the reference run that uses no chunking at all.
Not just the fingerprint -- the readout triples and the step count too, since
a difference in any of them would be a difference the fingerprint might
happen not to catch.

It does not prove anything about a platform this was not run on. Chunk
invariance is a property of the kernel's state handling, which is the same C
on every target, but "the same source" is an argument and this tool produces
evidence. Run it under each backend and, when a build exists there, on each
platform.

WHICH K VALUES, AND WHY

The sweep has to include more than round numbers, because a K that divides
the step count exactly never exercises a short final chunk, and a K that is a
multiple of the synaptic delay never rotates the delay ring to an unusual
offset. The default set is therefore:

  1        every step its own chunk -- the maximum number of boundaries
  2, 3, 7  small values, two of which divide neither 10,000 nor 13,000
  13       lands mid-ring for a delay that is not 13
  250      divides 10,000 but not 13,000 (G-09 runs 13,000 steps)
  1000     divides both
  100000   larger than every request in the suite, so the very first chunk is
           clamped by onfcont (D-367) and the loop ends after one call

Run:  python tools/cmpchk.py <tstgld executable> [...] [--chunks 1,7,250]
Exit status 0 when every sweep agrees with its reference run.
"""
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import run_gld  # noqa: E402

#: D-366's plan named {1, 7, 250, full}; the rest are the same argument
#: carried further, and cost only runtime.
DEFAULT_CHUNKS = (1, 2, 3, 7, 13, 250, 1000, 100000)


def run(exe, path, suite, chunk):
    """One tstgld run; returns its GOLD and GOUT lines.

    The banner is dropped: it names the backend and now the chunk size, both
    of which differ by design. Everything else must not.
    """
    argv = [os.path.abspath(exe), path, str(suite), str(chunk)]
    proc = subprocess.Popen(argv, stdout=subprocess.PIPE)
    out, _ = proc.communicate()
    if proc.returncode != 0:
        sys.stderr.write("%s exited %d at chunk=%d\n"
                         % (exe, proc.returncode, chunk))
        sys.exit(2)
    lines = out.decode("ascii", "replace").splitlines()
    body = [l for l in lines if not l.startswith("#")]
    if not body:
        sys.stderr.write("%s produced no GOLD lines at chunk=%d\n"
                         % (exe, chunk))
        sys.exit(2)
    return body


def backend(exe, path, suite):
    """The backend name the build reports, for labelling the report."""
    argv = [os.path.abspath(exe), path, str(suite), "0"]
    proc = subprocess.Popen(argv, stdout=subprocess.PIPE)
    out, _ = proc.communicate()
    for line in out.decode("ascii", "replace").splitlines():
        if line.startswith("#"):
            m = re.search(r"backend=(\S+)", line)
            if m:
                return m.group(1)
    return os.path.basename(exe)


def main():
    argv = sys.argv[1:]
    chunks = list(DEFAULT_CHUNKS)
    if "--chunks" in argv:
        i = argv.index("--chunks")
        chunks = [int(c) for c in argv[i + 1].split(",")]
        del argv[i:i + 2]
    if not argv:
        sys.stderr.write("usage: cmpchk.py <tstgld exe> [...] "
                         "[--chunks 1,7,250]\n")
        return 2
    if min(chunks) < 1:
        sys.stderr.write("cmpchk: a chunk size must be >= 1; 0 is the "
                         "reference run and is always made\n")
        return 2

    ok = bad = 0
    report = []
    for exe in argv:
        if not os.path.exists(exe):
            sys.stderr.write("cmpchk: not found: %s\n" % exe)
            return 2
        for tag in sorted(run_gld.NETWORKS):
            name, path = run_gld.NETWORKS[tag]
            if not os.path.exists(path):
                sys.stderr.write("cmpchk: missing network %s\n" % path)
                return 2
            label = backend(exe, path, tag)
            # The reference is chunk=0: one whole chunk, which is the path
            # every caller predating D-368 takes. Comparing the sweep against
            # it is what makes this a statement about a CHANGE in behaviour
            # rather than about the chunked path agreeing with itself.
            ref = run(exe, path, tag, 0)
            ngold = len([l for l in ref if l.startswith("GOLD")])
            for k in chunks:
                got = run(exe, path, tag, k)
                if got == ref:
                    ok += 1
                    report.append("  ok   %-7s %-5s K=%-7d %d requests, "
                                  "%d lines identical"
                                  % (label, name, k, ngold, len(ref)))
                else:
                    bad += 1
                    report.append("  FAIL %-7s %-5s K=%-7d differs from the "
                                  "whole-run reference" % (label, name, k))
                    for a, b in zip(ref, got):
                        if a != b:
                            report.append("       whole: %s" % a)
                            report.append("       K=%-4d %s" % (k, b))
                            break
                    if len(ref) != len(got):
                        report.append("       line counts differ: %d vs %d"
                                      % (len(ref), len(got)))

    print("cmpchk [FR-SIM-10 chunk invariance]: %d passed, %d failed"
          % (ok, bad))
    for line in report:
        print(line)
    if bad == 0:
        print("  ok   the Section 8.4 fingerprints do not depend on K "
              "(chunks swept: %s)"
              % ", ".join(str(c) for c in chunks))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
