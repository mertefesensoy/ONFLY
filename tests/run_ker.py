# -*- coding: utf-8 -*-
"""Kernel comparison: the C engine against the Python oracle (L2 of SRS 8.1).

The C program prints the synthetic network it built and the per-neuron results
it computed.  This script rebuilds that network in Python, runs the independent
oracle kernel on it, and compares spike counts and first-spike latencies exactly.

The network crosses from C to Python so both sides demonstrably simulate the
same thing.  The results do not: the oracle recomputes them from scratch, so
agreement is evidence rather than an echo.

Run:  python tests/run_ker.py <path-to-tstker-executable>
"""
import os
import struct
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "oracle"))

from onfly_oracle import kernel as okernel   # noqa: E402


def bits_to_float(text):
    hi, lo = text.split(":")
    return struct.unpack(">d", struct.pack(">II", int(hi, 16), int(lo, 16)))[0]


def fields(parts):
    out = {}
    for p in parts:
        if "=" in p:
            k, v = p.split("=", 1)
            out[k] = v
    return out


def main():
    if len(sys.argv) < 2:
        sys.stderr.write("usage: run_ker.py <tstker executable>\n")
        return 2
    exe = os.path.abspath(sys.argv[1])
    if not os.path.exists(exe):
        sys.stderr.write("not found: %s\n" % exe)
        return 2

    proc = subprocess.Popen([exe], stdout=subprocess.PIPE)
    out, _ = proc.communicate()
    if proc.returncode != 0:
        sys.stderr.write("tstker exited %d\n" % proc.returncode)
        return 2

    backend = "?"
    meta = {}
    rowptr, target, weight, stim, read = {}, {}, {}, {}, {}
    consts = {}
    runs = {}          # case -> dict(seed, rate, steps, rc)
    cout = {}          # case -> {i: (spikes, first)}

    for line in out.decode("ascii", "replace").splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("#"):
            for tok in line.split():
                if tok.startswith("backend="):
                    backend = tok.split("=", 1)[1]
            continue
        parts = line.split()
        kind, f = parts[0], fields(parts[1:])
        if kind == "NET":
            meta = {k: int(v) for k, v in f.items()}
        elif kind in ("CONST", "PROP"):
            for k, v in f.items():
                consts[k] = bits_to_float(v)
        elif kind == "ROW":
            rowptr[int(f["i"])] = int(f["p"])
        elif kind == "EDGE":
            k = int(f["k"])
            target[k] = int(f["t"])
            weight[k] = bits_to_float(f["w"])
        elif kind == "STIM":
            stim[int(f["i"])] = int(f["v"])
        elif kind == "READ":
            read[int(f["i"])] = int(f["v"])
        elif kind == "RUN":
            runs[int(f["c"])] = {"seed": int(f["seed"]), "rate": int(f["rate"]),
                                 "steps": int(f["steps"]), "rc": int(f["rc"])}
        elif kind == "OUT":
            cout.setdefault(int(f["c"]), {})[int(f["i"])] = (int(f["s"]), int(f["f"]))

    n = meta["n"]
    net = okernel.Network(
        n=n,
        rowptr=[rowptr[i] for i in range(n + 1)],
        target=[target[k] for k in range(meta["e"])],
        weight=[weight[k] for k in range(meta["e"])],
        stim=[stim[i] for i in range(meta["ns"])],
        readout=[read[i] for i in range(meta["nr"])],
        dt_us=meta["dtus"], delay=meta["delay"], refract=meta["refract"],
        u_th=consts["uth"], u_reset=consts["ureset"],
        p11=consts["p11"], p12=consts["p12"], p22=consts["p22"],
        g_eps=consts["geps"])

    passed = failed = 0
    msgs = []
    total_spikes = {}

    for c in sorted(runs):
        r = runs[c]
        spikes, first = okernel.run(net, r["seed"], r["rate"], r["steps"])
        tot = 0
        for i in range(n):
            got = cout[c][i]
            want = (spikes[i], first[i])
            tot += spikes[i]
            if got == want:
                passed += 1
            else:
                failed += 1
                if len(msgs) < 10:
                    msgs.append(
                        "  FAIL case %d neuron %d: C=(spikes=%d,first=%d) "
                        "oracle=(spikes=%d,first=%d)"
                        % (c, i, got[0], got[1], want[0], want[1]))
        total_spikes[c] = tot

        # ACC-2 in miniature: rate 0 has no other noise source, so silence is
        # exact, not statistical.
        if r["rate"] == 0:
            if tot == 0:
                passed += 1
            else:
                failed += 1
                msgs.append("  FAIL case %d: rate 0 produced %d spikes "
                            "(ACC-2 requires exact silence)" % (c, tot))

    print("run_ker [%s backend]: %d passed, %d failed" % (backend, passed, failed))
    for c in sorted(runs):
        r = runs[c]
        print("    case %d seed=%-9d rate=%-5d steps=%-4d rc=%d  total spikes=%d"
              % (c, r["seed"], r["rate"], r["steps"], r["rc"], total_spikes[c]))
    for m in msgs:
        print(m)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
