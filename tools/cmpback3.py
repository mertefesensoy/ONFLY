# -*- coding: utf-8 -*-
"""Run one network on every float backend this host has and require exact
agreement (D-204, ACC-2, ACC-5's spirit).

Why this exists.  ACC-2 says a rate 0 request produces zero spikes in every
neuron "on every platform and backend", and ACC-5 requires identical
fingerprints across the Section 8.3 determinism matrix.  Both are claims
about backends, and until D-204 the format v1.1 compensating-input table had
only ever been decoded by the native x86 build -- so a candidate MVS
subcircuit carrying one had been verified on exactly one of the three
backends available on this host.

What agreement means here is bit-exact, not approximate: the per-readout
spike count and first-spike latency must be identical integers across
backends.  That is stronger than comparing mean rates, which could agree to
two decimals while the underlying trajectories differed.

SOFT2C matters most of the three.  It is the library MVS uses (D-105,
NR-03), so an x86 SOFT2C result on this network is the only thing a later
MVS result can be compared against on equal terms.

This does NOT discharge ACC-2 or ACC-5: every backend here is x86-64, and
nothing is proven for s390x, MVS or z/OS.

Run:  python tools/cmpback3.py <network> [--rates 10,40,60,120,200]
                               [--seeds 30] [--jobs 14]
"""
import argparse
import io
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

BACKENDS = [
    ("NATIVE", os.path.join(ROOT, "build", "runnet.exe")),
    ("SOFT3E", os.path.join(ROOT, "build", "runnet_soft.exe")),
    ("SOFT2C", os.path.join(ROOT, "build", "runnet_2c.exe")),
]
SIM_MS = 1000


def parse(text):
    """(rc, [(neuron, spikes, first), ...], total_spikes_or_None)."""
    rc, outs, total = None, [], None
    for line in text.splitlines():
        p = line.split()
        if not p:
            continue
        f = dict(t.split("=", 1) for t in p[1:] if "=" in t)
        if p[0] == "RUN":
            rc = int(f["rc"])
        elif p[0] == "READOUT":
            outs.append((int(f["n"]), int(f["spikes"]), int(f["first"])))
        elif p[0] == "TOP":
            total = (total or 0) + int(f["spikes"])
    return rc, outs, total


def run(exe, net, rate, seed, extra=()):
    proc = subprocess.Popen([exe, net, str(rate), str(SIM_MS), str(seed)]
                            + list(extra),
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True)
    return proc.communicate()[0]


def pool(tasks, jobs):
    """Run (key, argv) tasks at most ``jobs`` at a time; return {key: text}."""
    out, procs, todo = {}, {}, list(tasks)
    while todo or procs:
        while todo and len(procs) < jobs:
            k, argv = todo.pop(0)
            procs[k] = subprocess.Popen(argv, stdout=subprocess.PIPE,
                                        stderr=subprocess.STDOUT, text=True)
        for k, pr in list(procs.items()):
            if pr.poll() is not None:
                out[k] = pr.communicate()[0]
                del procs[k]
        if procs and not todo:
            time.sleep(0.05)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("network")
    ap.add_argument("--rates", default="10,40,60,120,200")
    ap.add_argument("--seeds", type=int, default=30)
    ap.add_argument("--jobs", type=int, default=14)
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    net = os.path.abspath(a.network)
    if not os.path.isfile(net):
        sys.stderr.write("no such network: %s\n" % net)
        return 2
    for name, exe in BACKENDS:
        if not os.path.isfile(exe):
            sys.stderr.write("%s runner missing: %s\n"
                             "Build it with:  mingw32-make runners\n"
                             % (name, exe))
            return 2

    rates = [int(x) for x in a.rates.split(",") if x.strip()]
    seeds = list(range(1, a.seeds + 1))

    print("network: %s" % os.path.basename(net))
    print("backends: %s" % ", ".join(n for n, _ in BACKENDS))
    print("rates: %s   seeds: 1..%d" % (rates, a.seeds))
    sys.stdout.flush()

    t0 = time.time()
    results = {}
    for name, exe in BACKENDS:
        tasks = [((name, r, s),
                  [exe, net, str(r), str(SIM_MS), str(s)])
                 for r in rates for s in seeds]
        got = pool(tasks, a.jobs)
        for k, text in got.items():
            rc, outs, _ = parse(text)
            if rc != 0 or len(outs) != 2:
                sys.stderr.write("run %s failed:\n%s\n" % (k, text[-1500:]))
                return 1
            results[k] = tuple(outs)
        print("  %-6s %d runs done, %.0f s"
              % (name, len(got), time.time() - t0))
        sys.stdout.flush()

    # --- exact agreement, per (rate, seed) -------------------------------
    mismatches = []
    for r in rates:
        for s in seeds:
            ref = results[(BACKENDS[0][0], r, s)]
            for name, _exe in BACKENDS[1:]:
                if results[(name, r, s)] != ref:
                    mismatches.append({
                        "rate": r, "seed": s, "backend": name,
                        "native": ref, "other": results[(name, r, s)]})

    # --- ACC-2 on every backend: rate 0, every neuron --------------------
    acc2 = {}
    for name, exe in BACKENDS:
        text = run(exe, net, 0, 1, ("--all",))
        rc, _outs, total = parse(text)
        acc2[name] = {"rc": rc, "total_spikes": total}

    print("")
    print("%-8s %10s %s" % ("backend", "rate0 rc", "rate 0 spikes, all neurons"))
    for name, _exe in BACKENDS:
        e = acc2[name]
        print("%-8s %10s %d   %s"
              % (name, e["rc"], e["total_spikes"],
                 "ACC-2 PASS" if e["total_spikes"] == 0 else "ACC-2 FAIL"))

    n_cmp = len(rates) * len(seeds) * (len(BACKENDS) - 1)
    print("")
    if mismatches:
        print("MISMATCH: %d of %d comparisons differ" % (len(mismatches),
                                                         n_cmp))
        for m in mismatches[:5]:
            print("  rate=%d seed=%d %s: %s vs NATIVE %s"
                  % (m["rate"], m["seed"], m["backend"], m["other"],
                     m["native"]))
    else:
        print("EXACT AGREEMENT: %s agree bit-for-bit on all %d comparisons "
              "(%d rate/seed pairs, readout spike counts and first-spike "
              "latencies)"
              % (", ".join(n for n, _ in BACKENDS), n_cmp,
                 len(rates) * len(seeds)))

    ok = (not mismatches) and all(e["total_spikes"] == 0
                                  for e in acc2.values())
    if a.out:
        io.open(a.out, "w", encoding="utf-8", newline="\n").write(
            json.dumps({
                "network": os.path.basename(net),
                "backends": [n for n, _ in BACKENDS],
                "rates": rates, "seeds": seeds,
                "comparisons": n_cmp, "mismatches": mismatches,
                "acc2_per_backend": acc2,
                "agree": not mismatches,
                "acc2_pass_all_backends": all(e["total_spikes"] == 0
                                              for e in acc2.values()),
                "platform": "x86-64 Windows 11, mingw32 gcc 6.3.0",
                "not_proven": ("All three backends are x86-64. Nothing here "
                               "is proven for s390x, MVS 3.8j or z/OS."),
                "elapsed_s": round(time.time() - t0),
            }, indent=2, sort_keys=True) + "\n")
        print("wrote %s" % a.out.replace("\\", "/"))
    print("%.0f s" % (time.time() - t0))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
