# -*- coding: utf-8 -*-
"""Golden request suite against the oracle (SRS 8.4, ACC-5, IR-COM-05).

Writes a network file, runs the C golden-suite binary on it, then recomputes
every request independently in Python -- the kernel from the oracle and the
fingerprint from its own reading of IR-COM-05 -- and compares fingerprints.

What this establishes and what it does not: agreement here shows the C engine
and the oracle produce identical fingerprints on the host it runs on. ACC-5
additionally requires the same fingerprints on the other Section 8.3 rows.
Rows 4 and 5, Linux s390x under QEMU, run this same script in the guest;
rows 6 and 7, MVS 3.8j under the Hercules emulator, are recorded in
data/phase-e/ and checked by tests/run_mvsrun.py and tests/run_mvsjcc.py;
row 8, z/OS, is empty, because the project does not have IBM Z access yet
(VL-139). VL-05 also applies: identical fingerprints prove consistency, not
correctness.

The 1000 ms standard duration is fixed by D-73 and the 1300 ms maximum by
D-138. G-07's 100 ms "short" duration is D-42's, and every Section 8.3 row was
recorded with it, so changing any duration would change the fingerprints
below and every recording that holds them.
(Brought up to date 2026-09-25 by P-41 slice D, D-531: this docstring still
described the Phase B harness, when rows 4 to 8 were unrun and the durations
provisional.)

Run:  python tests/run_gld.py <path-to-tstgld-executable>
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for sub in ("layout", "generated", "oracle"):
    sys.path.insert(0, os.path.join(ROOT, sub))

import netread                                   # noqa: E402
import netwrite                                  # noqa: E402
import onfcom_py as L                            # noqa: E402
from onfly_oracle import kernel as okernel       # noqa: E402
from onfly_oracle.crc32 import crc32             # noqa: E402
from onfly_oracle.fingerprint import fingerprint  # noqa: E402

STD_MS, SHORT_MS = 1000, 100          # D-37, D-42; standard fixed by D-73
RC_OK, RC_WARN, RC_ERR = 0, 4, 8      # Appendix E RC column, proposal P-08

#: The real network the suite runs against (D-70).  Its parameters are read
#: from the file rather than restated here, so this module cannot disagree with
#: the artifact under test.
NETWORK = os.path.join(ROOT, "data", "networks",
                       "onfnet-malecns-v1.0-path.bin")

#: D-212: Section 8.4 now spans two networks.  ``NETWORK`` stays the path
#: fixture so that anything holding a reference to it still means what it
#: meant; ``NETWORKS`` is the suite's own list, indexed by the ``net`` tag
#: each request carries.  The fingerprint includes the network's payload CRC
#: (IR-COM-05), so a request is only meaningful against the network it was
#: written for -- running one against the other would produce a valid-looking
#: fingerprint for a request Section 8.4 does not define.
NET_PATH, NET_SREXT = 0, 1
NETWORKS = {
    NET_PATH: ("path", NETWORK),
    NET_SREXT: ("srext", os.path.join(ROOT, "data", "networks",
                                      "onfnet-malecns-v1.0-srext.bin")),
}
MAX_MS = 1300                          # D-138; read back from the file and asserted

SUITE = [
    ("G-01", "SUGR", 1,    0, STD_MS,        1, NET_PATH),
    ("G-02", "SUGR", 1,   10, STD_MS,        1, NET_PATH),
    ("G-03", "SUGR", 1,   40, STD_MS,        1, NET_PATH),
    ("G-04", "SUGR", 1,  120, STD_MS,        1, NET_PATH),
    ("G-05", "SUGR", 1,  200, STD_MS,        1, NET_PATH),
    ("G-06", "SUGR", 1,  200, STD_MS, 999999999, NET_PATH),
    ("G-07", "SUGR", 1, 9999, SHORT_MS,      7, NET_PATH),
    ("G-08", "SUGR", 1,  120, 1,             7, NET_PATH),
    ("G-09", "SUGR", 1,  120, MAX_MS,        7, NET_PATH),
    ("G-10", "SUGR", 1,  120, STD_MS,        0, NET_PATH),
    ("G-11", "WATR", 2,  120, STD_MS,        1, NET_PATH),
    ("G-12", "XXXX", 0,  120, STD_MS,        1, NET_PATH),
    ("G-13", "SUGR", 1,   -1, STD_MS,        1, NET_PATH),
    # D-212: closes proposal P-09.  D-165 added 60 Hz to SR-CAL-02's
    # validation set after this suite was drafted, and ACC-5 is evaluated on
    # the suite, so until now that rate had no determinism evidence.
    ("G-14", "SUGR", 1,   60, STD_MS,        1, NET_PATH),
    # D-212: the MVP subcircuit admitted by D-205.  These five are the only
    # golden requests that exercise the format v1.1 compensating-input table,
    # and each picks a different branch of Appendix C step 0 -- the zero row
    # IR-NET-09 mandates, an exactly sampled row, the top row, a rate beyond
    # the table that clamps, and a rate equidistant between two rows, which
    # D-191 resolves to the lower (at 100 Hz, not 30, per D-213:
    # at 30 Hz the readouts gave one spike, too thin a margin to
    # discriminate a wrongly selected row).
    ("G-15", "SUGR", 1,    0, STD_MS,        1, NET_SREXT),
    ("G-16", "SUGR", 1,   40, STD_MS,        1, NET_SREXT),
    ("G-17", "SUGR", 1,  200, STD_MS,        1, NET_SREXT),
    ("G-18", "SUGR", 1, 9999, STD_MS,        1, NET_SREXT),
    ("G-19", "SUGR", 1,  100, STD_MS,        1, NET_SREXT),
]


def make_network(path=None):
    """Load the real path fixture: 913 MaleCNS neurons (D-70, D-74, D-75).

    Why this fixture and not the two earlier ones.

    The suite originally used a synthetic 32-neuron network whose readouts never
    fired -- all 80 output entries came back spk=0, lat=-1 -- so every
    fingerprint depended only on request fields and eight constant entries.
    Four kernel semantics changed under D-67, D-68 and D-69 and **not one
    fingerprint moved**.  A determinism test that cannot detect a kernel change
    is not testing determinism.

    D-70 moved the suite to the real 2-hop network, which fixed that but cost
    the oracle over 35 minutes without finishing: about 1.9 billion neuron-steps
    across the suite.

    D-74 then proposed restricting to neurons on a stimulus-to-MN9 path.  Taken
    literally that is 28 neurons, and MN9 never fires in it: MN9 has 321
    presynaptic partners and needs their summed input to cross threshold.  So
    D-75 settled on stimulus + hop-1 successors + every MN9 input + MN9: 913
    neurons in which MN9 fires 138 to 194 spikes with latency falling as rate
    rises, and which the oracle can run in minutes rather than hours.

    Parameters are read from the file, not restated here, so this module cannot
    disagree with the artifact under test.

    D-212 gave this a ``path`` argument: the suite now also runs against the
    admitted srext subcircuit, whose compensating-input table no request on
    the path fixture exercises.
    """
    if path is None:
        path = NETWORK
    spec = netread.read(path)
    return spec, netread.as_oracle_network(spec), spec["paycrc"]


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

    backend, cgold, oracles = "?", {}, {}
    for tag, (label, path) in sorted(NETWORKS.items()):
        if not os.path.exists(path):
            sys.stderr.write("network not found: %s\n" % path)
            sys.stderr.write("Emit it first:  python prep/emit.py path   "
                             "(or prep/extract.py --admit for srext)\n")
            return 2
        spec, net, paycrc = make_network(path)
        assert spec["max_ms"] == MAX_MS, (
            "%s's maximum duration is %d but this suite assumes %d"
            % (label, spec["max_ms"], MAX_MS))
        oracles[tag] = (net, paycrc)

        # One invocation per network, each running only its own half of the
        # suite (D-212).  The C side skips the rest rather than running them
        # against the wrong file.
        proc = subprocess.Popen([exe, path, str(tag)], stdout=subprocess.PIPE)
        out, _ = proc.communicate()
        if proc.returncode != 0:
            sys.stderr.write("tstgld exited %d on %s\n"
                             % (proc.returncode, label))
            return 2
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
    for gid, code, stimid, rate, ms, seed, tag in SUITE:
        net, paycrc = oracles[tag]
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
            rows.append("  ok   %s %-5s %-4s rate=%-5d ms=%-5d seed=%-9d "
                        "rc=%-2d steps=%-6d fp=%08X"
                        % (gid, NETWORKS[tag][0], code, rate, ms, seed,
                           want_rc, want_steps, want_fp))
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
