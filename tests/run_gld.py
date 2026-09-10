# -*- coding: utf-8 -*-
"""Golden request suite against the oracle (SRS 8.4, ACC-5, IR-COM-05).

Writes a network file, runs the C golden-suite binary on it, then recomputes
every request independently in Python -- the kernel from the oracle and the
fingerprint from its own reading of IR-COM-05 -- and compares fingerprints.

What this establishes and what it does not: agreement here shows the C engine
and the oracle produce identical fingerprints on this host. ACC-5 additionally
requires the same fingerprints on Linux s390x, MVS 3.8j and z/OS, none of which
is available here, so rows 4 to 8 of the Section 8.3 matrix stay unrun. VL-05
also applies: identical fingerprints prove consistency, not correctness.

The durations come from D-37 and D-42 and are PROVISIONAL. Gate G3 fixes the
real values, and changing a duration changes every fingerprint below.

Run:  python tests/run_gld.py <path-to-tstgld-executable>
"""
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for sub in ("layout", "generated", "oracle"):
    sys.path.insert(0, os.path.join(ROOT, sub))

import netwrite                                  # noqa: E402
import onfcom_py as L                            # noqa: E402
from onfly_oracle import kernel as okernel       # noqa: E402
from onfly_oracle.crc32 import crc32             # noqa: E402
from onfly_oracle.fingerprint import fingerprint  # noqa: E402

STD_MS, SHORT_MS = 1000, 100          # D-37, D-42 -- provisional
RC_OK, RC_WARN, RC_ERR = 0, 4, 8      # Appendix E RC column, proposal P-08

DT_US, DELAY, REFRACT, MAX_MS = 100, 18, 22, 5000
P11, P12, P22 = 0.9950124791926823, 0.004937935295309022, 0.9801986733067553
U_TH, U_RESET, G_EPS = 7.0, 0.0, 1e-300

SUITE = [
    ("G-01", "SUGR", 1,    0, STD_MS,        1),
    ("G-02", "SUGR", 1,   10, STD_MS,        1),
    ("G-03", "SUGR", 1,   40, STD_MS,        1),
    ("G-04", "SUGR", 1,  120, STD_MS,        1),
    ("G-05", "SUGR", 1,  200, STD_MS,        1),
    ("G-06", "SUGR", 1,  200, STD_MS, 999999999),
    ("G-07", "SUGR", 1, 9999, SHORT_MS,      7),
    ("G-08", "SUGR", 1,  120, 1,             7),
    ("G-09", "SUGR", 1,  120, MAX_MS,        7),
    ("G-10", "SUGR", 1,  120, STD_MS,        0),
    ("G-11", "WATR", 2,  120, STD_MS,        1),
    ("G-12", "XXXX", 0,  120, STD_MS,        1),
    ("G-13", "SUGR", 1,   -1, STD_MS,        1),
]


def make_network():
    """A 32-neuron synthetic network, plus the oracle view of it."""
    n = 32
    rowptr, target, weight = [0], [], []
    for i in range(n):
        row = sorted(set(((i + 1 + k * 5) % n) for k in range(4)))
        target.extend(row)
        for j, _t in enumerate(row):
            w = 0.275 * ((i + j) % 7 + 1)
            weight.append(-w if (i % 3 == 0) else w)   # SR-MOD-05 sign
        rowptr.append(len(target))
    stim, readout = [0, 1, 2, 3], [24, 25, 26, 27, 28, 29, 30, 31]
    blob = netwrite.build(
        n=n, rowptr=rowptr, target=target, weight=weight,
        stim=stim, readout=readout, dt_us=DT_US, delay=DELAY,
        refract=REFRACT, max_ms=MAX_MS, u_th=U_TH, u_reset=U_RESET,
        p11=P11, p12=P12, p22=P22, g_eps=G_EPS, w_syn=0.275, v_rest=-52.0)
    net = okernel.Network(
        n=n, rowptr=rowptr, target=target, weight=weight, stim=stim,
        readout=readout, dt_us=DT_US, delay=DELAY, refract=REFRACT,
        u_th=U_TH, u_reset=U_RESET, p11=P11, p12=P12, p22=P22, g_eps=G_EPS)
    paycrc = crc32(blob[L.NETHDR_LEN:L.NETHDR_LEN
                        + int.from_bytes(blob[152:156], "big")])
    return blob, net, paycrc


def oracle_request(net, paycrc, stimid, rate, ms, seed):
    """Recompute one golden request: validation, simulation, fingerprint."""
    outputs, steps, rc = [], 0, RC_OK
    if stimid == 0:
        rc = RC_ERR                                    # ONF203E (D-41)
    elif stimid != 1:
        rc = RC_WARN                                   # ONF201W, FR-BAT-05
    elif rate < 0 or rate > 9999:
        rc = RC_ERR                                    # ONF202E
    elif rate * net.dt_us > 1000000:
        rc = RC_ERR                                    # NR-12 bound
    elif ms < 1 or ms > MAX_MS:
        rc = RC_ERR                                    # FR-SIM-06
    else:
        steps = ms * 1000 // net.dt_us
        spikes, first = okernel.run(net, seed, rate, steps)
        outputs = [(i, first[i], spikes[i]) for i in net.readout]
    return fingerprint(paycrc, stimid, seed, rate, ms, rc, outputs, steps), rc, steps


def main():
    if len(sys.argv) < 2:
        sys.stderr.write("usage: run_gld.py <tstgld executable>\n")
        return 2
    exe = os.path.abspath(sys.argv[1])
    if not os.path.exists(exe):
        sys.stderr.write("not found: %s\n" % exe)
        return 2

    blob, net, paycrc = make_network()
    tmp = tempfile.mkdtemp(prefix="onfly_gld_")
    path = os.path.join(tmp, "golden.net")
    with open(path, "wb") as fh:
        fh.write(blob)

    proc = subprocess.Popen([exe, path], stdout=subprocess.PIPE)
    out, _ = proc.communicate()
    if proc.returncode != 0:
        sys.stderr.write("tstgld exited %d\n" % proc.returncode)
        return 2

    backend, cgold = "?", {}
    for line in out.decode("ascii", "replace").splitlines():
        if line.startswith("#"):
            for tok in line.split():
                if tok.startswith("backend="):
                    backend = tok.split("=", 1)[1]
            continue
        if line.startswith("GOLD"):
            f = dict(t.split("=", 1) for t in line.split()[1:])
            cgold[f["id"]] = f

    passed = failed = 0
    rows = []
    for gid, code, stimid, rate, ms, seed in SUITE:
        want_fp, want_rc, want_steps = oracle_request(
            net, paycrc, stimid, rate, ms, seed)
        got = cgold.get(gid)
        if got is None:
            failed += 1
            rows.append("  FAIL %s missing from C output" % gid)
            continue
        ok = (int(got["fp"], 16) == want_fp
              and int(got["rc"]) == want_rc
              and int(got["steps"]) == want_steps)
        if ok:
            passed += 1
            rows.append("  ok   %s %-4s rate=%-5d ms=%-5d seed=%-9d rc=%-2d "
                        "steps=%-6d fp=%08X"
                        % (gid, code, rate, ms, seed, want_rc, want_steps,
                           want_fp))
        else:
            failed += 1
            rows.append("  FAIL %s C fp=%s rc=%s steps=%s | oracle fp=%08X "
                        "rc=%d steps=%d"
                        % (gid, got["fp"], got["rc"], got["steps"],
                           want_fp, want_rc, want_steps))

    # Distinct requests must not share a fingerprint; a constant would pass
    # every comparison above while proving nothing.
    fps = [int(cgold[g[0]]["fp"], 16) for g in SUITE if g[0] in cgold]
    distinct = len(set(fps))
    if distinct == len(fps):
        passed += 1
        rows.append("  ok   all %d fingerprints are distinct" % len(fps))
    else:
        failed += 1
        rows.append("  FAIL only %d distinct fingerprints among %d requests"
                    % (distinct, len(fps)))

    print("run_gld [%s backend]: %d passed, %d failed" % (backend, passed, failed))
    for r in rows:
        print(r)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
