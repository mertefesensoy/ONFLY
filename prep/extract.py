# -*- coding: utf-8 -*-
"""Subcircuit extraction (SR-EXT-01..03) and ACC-3, on x86 (D-178, D-179).

Stages, each resumable from what the previous one left on disk:

  --rank     Run the calibrated v1.0 full network (data/networks/
             onfnet-malecns-v1.0-full.bin: W_syn 0.2969 mV, D-52 stimulus
             set) at every TBD-07 rate {10,20,40,60,80,120,160,200} Hz for
             seeds 1..30 (D-135) -- 240 full-brain runs of 1000 ms -- and sum
             each neuron's spike count over all of them as the runs complete.
             SR-EXT-01: "the N most active neurons by total spike count in
             the full-brain run (calibrated W_syn, all calibration and
             validation rates, all seeds)".  Per-run MN9 counts are logged.
  --extract  For N in 250, 500, 1000 (SR-EXT-03 as narrowed by Gate G3):
             the top N by total, ties broken by ascending body id
             (SR-EXT-01), plus every stimulus and readout neuron; every
             MaleCNS connection among them with unchanged weights
             (SR-EXT-02), emitted through emit.build_network.
  --acc3     Each subcircuit at the validation rates {10,40,60,120,200} Hz,
             seeds 1..30 -- the same seeds as the full-brain acc4.json --
             compared as mean MN9 rate (D-170) within +-10% of the full
             brain, or +-1 Hz (D-166), whichever is larger.  Then SR-EXT-03:
             the smallest N passing ACC-3 and NFR-MEM-01 (the decoded need
             reported by the runner against TBD-14's 8M) and NFR-PERF-01
             (Gate G3: N up to 1000 fits).  If none passes ACC-3 the tool
             says so and stops; escalation is the owner's.

Outputs (data/calibration/): rank-progress.json (per-run MN9 counts and the
list of completed runs), activity-totals.npy (the 184,099 totals),
activity-ranking.json (top 1000 with body ids), acc3.json (the ACC-3
evaluation and the SR-EXT-03 choice).  Subcircuit networks go to
data/networks/onfnet-malecns-v1.0-n<N>.bin with data/networks/SUBCIRCUIT.json
recording digests and the selected body ids.

Run (repository root):

    python prep/extract.py --rank    [--jobs 14]
    python prep/extract.py --extract
    python prep/extract.py --acc3    [--jobs 14]
"""
import argparse
import hashlib
import io
import json
import math
import os
import subprocess
import sys
import time
import zlib

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import calibrate as cal                       # noqa: E402
import emit                                   # noqa: E402

FULL = os.path.join(ROOT, "data", "networks", "onfnet-malecns-v1.0-full.bin")
NET_DIR = os.path.join(ROOT, "data", "networks")
PROGRESS = os.path.join(cal.CAL_DIR, "rank-progress.json")
TOTALS = os.path.join(cal.CAL_DIR, "activity-totals.npy")
RANKING = os.path.join(cal.CAL_DIR, "activity-ranking.json")
ACC3 = os.path.join(cal.CAL_DIR, "acc3.json")
ACC4 = os.path.join(cal.CAL_DIR, "acc4.json")
SUBMAN = os.path.join(NET_DIR, "SUBCIRCUIT.json")

ALL_RATES = (10, 20, 40, 60, 80, 120, 160, 200)     # D-165, both sets
VAL_RATES = (10, 40, 60, 120, 200)                  # D-165
SEEDS = tuple(range(1, 31))                         # D-135
N_SEQ = (250, 500, 1000)                            # SR-EXT-03, Gate G3
REL_TOL = 0.10                                      # ACC-3
ABS_FLOOR = 1.0                                     # D-166
REGION_BYTES = 8 * 1024 * 1024                      # TBD-14, D-116


def load_json(path, default):
    if os.path.isfile(path):
        return json.load(io.open(path, encoding="utf-8"))
    return default


def save_json(path, obj):
    io.open(path, "w", encoding="utf-8", newline="\n").write(
        json.dumps(obj, indent=2, sort_keys=True) + "\n")


def parse_all(text):
    """RUN, READOUT and TOP lines of a --all run."""
    out = {"readouts": [], "rc": None, "need": None, "n": None,
           "counts": None}
    counts = None
    for line in text.splitlines():
        parts = line.split()
        if not parts:
            continue
        f = dict(t.split("=", 1) for t in parts[1:] if "=" in t)
        if parts[0] == "NET":
            out["n"] = int(f["n"])
            out["need"] = int(f["need"])
            counts = np.zeros(out["n"], dtype=np.int64)
        elif parts[0] == "RUN":
            out["rc"] = int(f["rc"])
        elif parts[0] == "READOUT":
            out["readouts"].append({"n": int(f["n"]),
                                    "spikes": int(f["spikes"])})
        elif parts[0] == "TOP":
            counts[int(f["n"])] = int(f["spikes"])
    out["counts"] = counts
    return out


def run_pool(jobs_list, jobs, extra, on_done):
    """Run runnet for every (path, rate, seed), ``jobs`` at a time."""
    todo = list(jobs_list)
    procs = {}
    while todo or procs:
        while todo and len(procs) < jobs:
            path, r, s = todo.pop(0)
            p = subprocess.Popen([cal.RUNNET, path, str(r), str(cal.SIM_MS),
                                  str(s)] + extra, stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, text=True)
            procs[(path, r, s)] = p
        for k, p in list(procs.items()):
            if p.poll() is not None:
                text = p.stdout.read()
                del procs[k]
                on_done(k, text)
        time.sleep(2)


# --- stage 1: ranking ------------------------------------------------------
def rank(jobs):
    prog = load_json(PROGRESS, {"done": [], "mn9": {}, "need": None,
                                "network": os.path.basename(FULL),
                                "sha256": hashlib.sha256(
                                    io.open(FULL, "rb").read()).hexdigest()})
    totals = np.load(TOTALS) if os.path.isfile(TOTALS) else None
    done = set(tuple(x) for x in prog["done"])
    todo = [(FULL, r, s) for r in ALL_RATES for s in SEEDS
            if (r, s) not in done]
    print("ranking: %d of %d runs already done" % (len(done),
                                                   len(ALL_RATES) * len(SEEDS)))
    state = {"totals": totals, "n_done": len(done), "t0": time.time()}

    def on_done(k, text):
        _path, r, s = k
        res = parse_all(text)
        if res["rc"] != 0 or res["counts"] is None:
            raise SystemExit("run %s failed:\n%s" % ((r, s), text[-2000:]))
        if state["totals"] is None:
            state["totals"] = np.zeros(res["n"], dtype=np.int64)
        state["totals"] += res["counts"]
        prog["need"] = res["need"]
        prog["mn9"]["%d/%d" % (r, s)] = [x["spikes"] for x in res["readouts"]]
        prog["done"].append([r, s])
        state["n_done"] += 1
        np.save(TOTALS, state["totals"])
        save_json(PROGRESS, prog)
        if state["n_done"] % 10 == 0:
            print("  %d runs done, %.0f s" % (state["n_done"],
                                              time.time() - state["t0"]))

    run_pool(todo, jobs, ["--all"], on_done)
    totals = state["totals"]
    order = np.lexsort((np.arange(len(totals)), -totals))   # SR-EXT-01 ties
    arrays, stim, read = cal.load_cache()
    nodes = np.union1d(np.unique(arrays["body_pre"]),
                       np.unique(arrays["body_post"]))
    assert len(nodes) == len(totals), "ranking must cover the full network"
    top = [{"rank": int(i), "index": int(order[i]),
            "body": int(nodes[order[i]]), "spikes": int(totals[order[i]])}
           for i in range(1000)]
    active = int((totals > 0).sum())
    ranking = {
        "decisions": ["D-135", "D-165", "D-173", "D-178", "D-179"],
        "requirement": "SR-EXT-01: total spikes over all rates and seeds, "
                       "ties by ascending body id",
        "rates_hz": list(ALL_RATES), "seeds": list(SEEDS),
        "runs": len(prog["done"]), "neurons": int(len(totals)),
        "active_neurons": active, "total_spikes": int(totals.sum()),
        "cut": {str(n): int(totals[order[n - 1]]) for n in N_SEQ},
        "top1000": top,
    }
    save_json(RANKING, ranking)
    print("ranked %d neurons, %d active, cuts %s"
          % (len(totals), active, ranking["cut"]))


# --- stage 2: subcircuits --------------------------------------------------
def extract():
    ranking = load_json(RANKING, None)
    if ranking is None:
        raise SystemExit("run --rank first")
    arrays, stim, read = cal.load_cache()
    man = load_json(SUBMAN, {"subcircuits": {}})
    for n in N_SEQ:
        top = np.array([t["body"] for t in ranking["top1000"][:n]],
                       dtype=np.int64)
        nodes = np.union1d(np.union1d(top, stim), read)
        blob, nn, e = emit.build_network(arrays, nodes, stim, read,
                                         "n%d" % n)
        path = os.path.join(NET_DIR, "onfnet-malecns-v1.0-n%d.bin" % n)
        io.open(path, "wb").write(blob)
        man["subcircuits"][str(n)] = {
            "file": os.path.basename(path), "N": n, "neurons": int(nn),
            "edges": int(e), "bytes": len(blob),
            "sha256": hashlib.sha256(blob).hexdigest(),
            "crc32": "%08X" % (zlib.crc32(blob) & 0xFFFFFFFF),
            "bodies": [int(b) for b in nodes],
            "stimulus_added": int(len(np.setdiff1d(stim, top))),
            "readout_added": int(len(np.setdiff1d(read, top))),
        }
    man["w_syn"] = emit.W_SYN
    man["max_ms"] = emit.MAX_MS
    man["source"] = "SR-EXT-01 ranking data/calibration/activity-ranking.json"
    save_json(SUBMAN, man)
    print("wrote %s" % SUBMAN.replace("\\", "/"))


# --- stage 3: ACC-3 and SR-EXT-03 -----------------------------------------
def acc3(jobs):
    man = load_json(SUBMAN, None)
    full = load_json(ACC4, None)
    if man is None or full is None:
        raise SystemExit("need SUBCIRCUIT.json (--extract) and acc4.json")
    results = {}

    def on_done(k, text):
        res = cal.parse_run(text)
        need = None
        for line in text.splitlines():
            if line.startswith("NET "):
                need = int(dict(t.split("=", 1) for t in line.split()[1:]
                                if "=" in t)["need"])
        if res["rc"] != 0 or len(res["readouts"]) != 2:
            raise SystemExit("run %s failed:\n%s" % (k, text))
        results[k] = (res, need)

    jobs_list = []
    for n in N_SEQ:
        path = os.path.join(NET_DIR, man["subcircuits"][str(n)]["file"])
        jobs_list += [(path, r, s) for r in VAL_RATES for s in SEEDS]
    t0 = time.time()
    run_pool(jobs_list, jobs, [], on_done)

    out = {"decisions": ["D-135", "D-165", "D-166", "D-178", "D-179"],
           "full_brain_source": "data/calibration/acc4.json (same seeds)",
           "subcircuits": {}, "chosen_N": None}
    chosen = None
    for n in N_SEQ:
        sub = man["subcircuits"][str(n)]
        path = os.path.join(NET_DIR, sub["file"])
        per_rate, ok_all = {}, True
        need = None
        for r in VAL_RATES:
            means = []
            for s in SEEDS:
                res, need = results[(path, r, s)]
                sp = [x["spikes"] for x in res["readouts"]]
                means.append(sum(sp) * 1000.0 / cal.SIM_MS / len(sp))
            mean = sum(means) / len(means)
            fb = full["per_rate"][str(r)]["onfly_mean_hz"]
            tol = max(REL_TOL * fb, ABS_FLOOR)
            ok = abs(mean - fb) <= tol
            ok_all = ok_all and ok
            per_rate[str(r)] = {"sub_mean_hz": mean, "full_mean_hz": fb,
                                "tolerance_hz": tol, "pass": ok}
        mem_ok = need is not None and need <= REGION_BYTES
        perf_ok = n <= 1000                       # Gate G3, VL-41, D-138
        out["subcircuits"][str(n)] = {
            "neurons": sub["neurons"], "edges": sub["edges"],
            "per_rate": per_rate, "acc3_pass": ok_all,
            "need_bytes": need, "nfr_mem_01_pass": mem_ok,
            "nfr_perf_01_pass_by_g3": perf_ok,
        }
        if chosen is None and ok_all and mem_ok and perf_ok:
            chosen = n
    out["chosen_N"] = chosen
    out["elapsed_s"] = round(time.time() - t0)
    save_json(ACC3, out)

    print("%6s %6s %10s %10s %8s %6s" % ("N", "rate", "subcirc", "full",
                                        "tol", "ACC-3"))
    for n in N_SEQ:
        e = out["subcircuits"][str(n)]
        for r in VAL_RATES:
            v = e["per_rate"][str(r)]
            print("%6d %6d %10.2f %10.2f %8.2f %6s"
                  % (n, r, v["sub_mean_hz"], v["full_mean_hz"],
                     v["tolerance_hz"], "PASS" if v["pass"] else "FAIL"))
        print("N=%d: ACC-3 %s; need=%s bytes vs %d (NFR-MEM-01 %s); "
              "NFR-PERF-01 by G3 %s"
              % (n, "PASS" if e["acc3_pass"] else "FAIL", e["need_bytes"],
                 REGION_BYTES, "PASS" if e["nfr_mem_01_pass"] else "FAIL",
                 "PASS" if e["nfr_perf_01_pass_by_g3"] else "FAIL"))
    if chosen is None:
        print("SR-EXT-03: no N in %s satisfies ACC-3, NFR-MEM-01 and "
              "NFR-PERF-01 -- escalate to the owner" % (N_SEQ,))
    else:
        print("SR-EXT-03: chosen N = %d" % chosen)
    print("wrote %s (%d s)" % (ACC3.replace("\\", "/"), out["elapsed_s"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rank", action="store_true")
    ap.add_argument("--extract", action="store_true")
    ap.add_argument("--acc3", action="store_true")
    ap.add_argument("--jobs", type=int, default=14)
    a = ap.parse_args()
    if not os.path.isfile(cal.RUNNET):
        raise SystemExit("build the runner first: mingw32-make runner")
    if a.rank:
        rank(a.jobs)
    if a.extract:
        extract()
    if a.acc3:
        acc3(a.jobs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
