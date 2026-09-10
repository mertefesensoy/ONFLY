# -*- coding: utf-8 -*-
"""Cross-language unit comparison: C engine primitives against the oracle.

Covers TU-03 (CRC-32), TU-04 (PRNG including seed 0) and TU-05 (stimulus draws
including the rejection path), per SRS section 8.5.

How it works.  tests/tstunit.c computes each quantity in C and prints one
result per line in a trivial text format.  This script recomputes every one of
them with the Python oracle and compares.  Neither side can see the other's
answer, so agreement is evidence of bit-exactness rather than of shared code.

Run:  python tests/run_units.py [path-to-tstunit-executable]

Exit status is 0 only if every comparison matches, so this is usable directly
as a build gate.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "oracle"))

from onfly_oracle import crc32 as ocrc          # noqa: E402
from onfly_oracle import prng as oprng          # noqa: E402
from onfly_oracle import stimulus as ostim      # noqa: E402

DEFAULT_EXE = os.path.join(ROOT, "build", "tstunit.exe")

# ---------------------------------------------------------------------------
# The vectors.  These are shared with the C side only as *inputs*; the expected
# outputs exist solely here.
# ---------------------------------------------------------------------------
CRC_VECTORS = [
    ("empty", b""),
    ("a", b"a"),
    ("abc", b"abc"),
    ("check", b"123456789"),          # standard CRC-32 check value CBF43926
    ("allbytes", bytes(bytearray(range(256)))),
    ("record", bytes(bytearray([(i * 7 + 13) & 0xFF for i in range(412)]))),
]

PRNG_SEEDS = [1, 0, 2463534242, 999999999, 7]
PRNG_DRAWS = 8

# (seed, rate_hz, dt_us, steps).  The large step counts are there to make the
# NR-12 rejection path actually occur: it fires for roughly 1 draw in 4440.
STIM_VECTORS = [
    (1, 0, 100, 1000),          # rate 0: must never spike (ACC-2 in miniature)
    (1, 200, 100, 1000),
    (7, 9999, 100, 1000),       # 9999 * 100 = 999900, just inside NR-12's bound
    (1, 120, 100, 200000),      # long enough to exercise rejection
    (0, 40, 100, 200000),       # seed 0 remapping, long run
]


class Result(object):
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.lines = []

    def check(self, label, got, want):
        if got == want:
            self.passed += 1
        else:
            self.failed += 1
            self.lines.append("  FAIL %-34s C=%s oracle=%s" % (label, got, want))


def run_c(exe):
    # Absolute: CreateProcess on Windows fails on a relative path when the
    # working directory contains non-ASCII characters, as this project's does.
    exe = os.path.abspath(exe)
    if not os.path.exists(exe):
        sys.stderr.write(
            "tstunit executable not found: %s\n"
            "Build it first:  mingw32-make tstunit\n" % exe)
        return None
    proc = subprocess.Popen([exe], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = proc.communicate()
    if proc.returncode != 0:
        sys.stderr.write("tstunit exited %d\n%s\n" % (proc.returncode,
                                                      err.decode("ascii", "replace")))
        return None
    return out.decode("ascii", "replace")


def parse(text):
    """Parse 'KIND key=value ...' lines into {kind: {key: value}}."""
    table = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        kind = parts[0]
        fields = {}
        for p in parts[1:]:
            if "=" in p:
                k, v = p.split("=", 1)
                fields[k] = v
        table.setdefault(kind, []).append(fields)
    return table


def main():
    exe = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_EXE
    text = run_c(exe)
    if text is None:
        return 2
    table = parse(text)
    r = Result()

    # --- TU-03: CRC-32 -----------------------------------------------------
    c_crc = {f["name"]: f["crc"].upper() for f in table.get("CRC", [])}
    for name, data in CRC_VECTORS:
        want = "%08X" % ocrc.crc32(data)
        r.check("TU-03 crc %s" % name, c_crc.get(name), want)

    # --- TU-04: PRNG -------------------------------------------------------
    c_prng = {}
    for f in table.get("PRNG", []):
        c_prng.setdefault(int(f["seed"]), []).append(f["v"].upper())
    for seed in PRNG_SEEDS:
        want = ["%08X" % v for v in oprng.sequence(seed, PRNG_DRAWS)]
        r.check("TU-04 prng seed=%d" % seed, c_prng.get(seed), want)

    # --- TU-05: stimulus draws --------------------------------------------
    c_stim = {}
    for f in table.get("STIM", []):
        key = (int(f["seed"]), int(f["rate"]), int(f["dt"]), int(f["steps"]))
        c_stim[key] = (int(f["spikes"]), int(f["draws"]))
    for seed, rate, dt, steps in STIM_VECTORS:
        threshold = ostim.check_threshold(rate, dt)
        gen = oprng.Xorshift32(seed)
        spikes = 0
        draws = 0
        for _ in range(steps):
            fired, used = ostim.draw_with_count(gen, threshold)
            if fired:
                spikes += 1
            draws += used
        key = (seed, rate, dt, steps)
        r.check("TU-05 stim seed=%d rate=%d n=%d" % (seed, rate, steps),
                c_stim.get(key), (spikes, draws))
        if rate == 0:
            r.check("TU-05 rate 0 is silent (seed=%d)" % seed,
                    c_stim.get(key, (None, None))[0], 0)
        # Prove the rejection path was actually taken, not merely present.
        if steps >= 200000:
            r.check("TU-05 rejection path exercised (seed=%d)" % seed,
                    draws > steps, True)

    print("run_units: %d passed, %d failed" % (r.passed, r.failed))
    for line in r.lines:
        print(line)
    return 1 if r.failed else 0


if __name__ == "__main__":
    sys.exit(main())
