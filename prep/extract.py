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

  --diag     D-180 diagnostic, not an SR-EXT-01 rule: each top-N set plus
             every presynaptic partner of both MN9 neurons, emitted under
             data/calibration/ and put through the same ACC-3 comparison;
             results in acc3-partners.json.

  --acc3-file <network> --label <name>
             D-181 diagnostic: the same ACC-3 comparison on any existing
             network file (the D-75 path fixture, the hop2 neighbourhood);
             results in acc3-<label>.json.

  --fitbias  D-194, D-199: the compensating input FITTED rather than
             measured.  F1 scales every median-bias row by a + b*R, two
             parameters fitted on the CALIBRATION rates {20, 80, 160}, and
             is then judged by ACC-3 on the VALIDATION rates it never saw.
             F2 gives each validation row its own free multiplier, which is
             five parameters against ACC-3's five constraints -- a pass
             there is calibration, not truncation fidelity, and says only
             whether the mechanism has the freedom.  Results in
             data/calibration/acc3-fitbias.json.  Diagnostic only (D-189).

  --constbias
             D-200: F3, one CONSTANT multiplier on the median-bias rows,
             fitted on the D-165 calibration rates {20, 80, 160} against
             SR-CAL-03's own objective and judged out of sample by ACC-3 on
             the validation rates.  One parameter against five test points,
             which is the form VL-73's flat per-rate multipliers support.
             Results in data/calibration/acc3-constbias.json.  Diagnostic
             only (D-189).

  --refixture
             D-192 step 7: re-emit data/networks/ at format version 1.1.
             A v1.0 file is unreadable to a v1.1 engine (ONF103E), so every
             fixture has to be rewritten.  The truncated ones carry a real
             compensating table, the full brain carries none, and the
             SR-EXT-01 subcircuits carry none because they are SR-EXT-02 as
             written.  Needs --ratebias first.

  --biasnet  D-190..D-192: the construction the owner chose to resolve
             SR-EXT-03's escalation.  The SR-EXT-01 top-N sets, emitted at
             network format version 1.1 with a per-rate compensating-input
             table standing for the drive their dropped presynaptic
             neurons used to supply, then put through the VL-66 ACC-3
             comparison into data/calibration/acc3-biasnet.json.  Needs
             --ratebias first.  Diagnostic only (D-189).

  --compensate
             D-186..D-189 diagnostic, three compared constructions for
             N in {250, 500, 1000}: A, selection only with part of the
             budget spent on the readouts' inhibitory partners so that
             SR-EXT-02's unchanged weights hold; B1, the SR-EXT-01 top-N
             sets with per-target gains restoring each kept neuron's
             expected drive; B2, B1's gains refined by self-consistent
             rate matching on interior neurons only.  Every one goes
             through the VL-66 ACC-3 comparison into
             data/calibration/acc3-compensated.json.  Diagnostic only:
             the networks live under data/calibration/ and nothing here
             amends SR-EXT-01 or SR-EXT-02 (D-189).

  --closure  D-182 diagnostic: from top-N (500, 1000) + stimulus + readouts,
             add every inhibitory presynaptic partner of every kept neuron,
             repeat to a fixed point or past 4,000 neurons, for a minimum
             synapse count of 5 and of 1; ACC-3 on each result under the
             cap; results in acc3-closure.json.

Run (repository root):

    python prep/extract.py --rank    [--jobs 14]
    python prep/extract.py --extract
    python prep/extract.py --acc3    [--jobs 14]
    python prep/extract.py --diag    [--jobs 14]
    python prep/extract.py --acc3-file data/networks/<file>.bin --label path
    python prep/extract.py --compensate [--jobs 14]
    python prep/extract.py --ratebias   [--jobs 8]
    python prep/extract.py --refixture
    python prep/extract.py --biasnet    [--jobs 14]
    python prep/extract.py --fitbias    [--jobs 14]
    python prep/extract.py --constbias  [--jobs 14]
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
    """Run runnet for every (path, rate, seed), ``jobs`` at a time.

    Output goes to a file per run, not a pipe: a ``--all`` run prints one
    line per neuron (about 7 MB on the full brain), and a pipe that is read
    only after exit fills up and blocks the engine forever -- measured on
    2026-09-12, fourteen runs stuck for twenty minutes after finishing.
    """
    tmp = os.path.join(cal.CAL_DIR, "tmp")
    if not os.path.isdir(tmp):
        os.makedirs(tmp)
    todo = list(jobs_list)
    procs = {}
    while todo or procs:
        while todo and len(procs) < jobs:
            path, r, s = todo.pop(0)
            out = os.path.join(tmp, "%s-%d-%d.txt"
                               % (os.path.basename(path), r, s))
            fh = io.open(out, "w")
            p = subprocess.Popen([cal.RUNNET, path, str(r), str(cal.SIM_MS),
                                  str(s)] + extra, stdout=fh,
                                 stderr=subprocess.STDOUT)
            procs[(path, r, s)] = (p, fh, out)
        for k, (p, fh, out) in list(procs.items()):
            if p.poll() is not None:
                fh.close()
                text = io.open(out, encoding="utf-8",
                               errors="replace").read()
                os.remove(out)
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


# --- D-180 diagnostic: top-N plus the readouts' presynaptic partners -------
def diag(jobs):
    ranking = load_json(RANKING, None)
    full = load_json(ACC4, None)
    if ranking is None or full is None:
        raise SystemExit("need activity-ranking.json (--rank) and acc4.json")
    arrays, stim, read = cal.load_cache()
    pre, post = arrays["body_pre"], arrays["body_post"]
    partners = np.unique(pre[np.isin(post, read)])
    print("MN9 presynaptic partners (both readouts): %d" % len(partners))
    subs = {}
    for n in N_SEQ:
        top = np.array([t["body"] for t in ranking["top1000"][:n]],
                       dtype=np.int64)
        nodes = np.union1d(np.union1d(np.union1d(top, partners), stim), read)
        blob, nn, e = emit.build_network(arrays, nodes, stim, read,
                                         "n%d+partners" % n)
        path = os.path.join(cal.CAL_DIR, "diag-n%d-partners.bin" % n)
        io.open(path, "wb").write(blob)
        subs[n] = {"file": path, "neurons": int(nn), "edges": int(e),
                   "added_partners": int(len(np.setdiff1d(partners, top))),
                   "sha256": hashlib.sha256(blob).hexdigest()}
    del arrays

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

    jobs_list = [(subs[n]["file"], r, s) for n in N_SEQ
                 for r in VAL_RATES for s in SEEDS]
    t0 = time.time()
    run_pool(jobs_list, jobs, [], on_done)

    out = {"decision": "D-180", "rule": "top-N by activity + every "
           "presynaptic partner of both MN9 + stimulus + readout; "
           "DIAGNOSTIC, not SR-EXT-01", "subcircuits": {}}
    print("%6s %6s %10s %10s %8s %6s" % ("N", "rate", "subcirc", "full",
                                        "tol", "ACC-3"))
    for n in N_SEQ:
        per_rate, ok_all, need = {}, True, None
        for r in VAL_RATES:
            means = []
            for sd in SEEDS:
                res, need = results[(subs[n]["file"], r, sd)]
                sp = [x["spikes"] for x in res["readouts"]]
                means.append(sum(sp) * 1000.0 / cal.SIM_MS / len(sp))
            mean = sum(means) / len(means)
            fb = full["per_rate"][str(r)]["onfly_mean_hz"]
            tol = max(REL_TOL * fb, ABS_FLOOR)
            ok = abs(mean - fb) <= tol
            ok_all = ok_all and ok
            per_rate[str(r)] = {"sub_mean_hz": mean, "full_mean_hz": fb,
                                "tolerance_hz": tol, "pass": ok}
            print("%6d %6d %10.2f %10.2f %8.2f %6s"
                  % (n, r, mean, fb, tol, "PASS" if ok else "FAIL"))
        out["subcircuits"][str(n)] = {
            "neurons": subs[n]["neurons"], "edges": subs[n]["edges"],
            "added_partners": subs[n]["added_partners"],
            "sha256": subs[n]["sha256"], "need_bytes": need,
            "per_rate": per_rate, "acc3_pass": ok_all,
            "nfr_mem_01_pass": need is not None and need <= REGION_BYTES}
        print("N=%d+partners: %d neurons, %d edges, ACC-3 %s, need=%s"
              % (n, subs[n]["neurons"], subs[n]["edges"],
                 "PASS" if ok_all else "FAIL", need))
    out["elapsed_s"] = round(time.time() - t0)
    save_json(os.path.join(cal.CAL_DIR, "acc3-partners.json"), out)
    print("wrote acc3-partners.json (%d s)" % out["elapsed_s"])


# --- D-181 diagnostic: ACC-3 on an existing network file -------------------
def acc3_file(path, label, jobs):
    full = load_json(ACC4, None)
    if full is None:
        raise SystemExit("need acc4.json")
    results = {}

    def on_done(k, text):
        res = cal.parse_run(text)
        need, n, e = None, None, None
        for line in text.splitlines():
            if line.startswith("NET "):
                f = dict(t.split("=", 1) for t in line.split()[1:]
                         if "=" in t)
                need, n, e = int(f["need"]), int(f["n"]), int(f["e"])
        if res["rc"] != 0 or len(res["readouts"]) != 2:
            raise SystemExit("run %s failed:\n%s" % (k, text))
        results[k] = (res, need, n, e)

    t0 = time.time()
    run_pool([(path, r, sd) for r in VAL_RATES for sd in SEEDS], jobs, [],
             on_done)
    per_rate, ok_all = {}, True
    need = n = e = None
    print("%6s %10s %10s %8s %6s" % ("rate", "subcirc", "full", "tol",
                                    "ACC-3"))
    for r in VAL_RATES:
        means = []
        for sd in SEEDS:
            res, need, n, e = results[(path, r, sd)]
            sp = [x["spikes"] for x in res["readouts"]]
            means.append(sum(sp) * 1000.0 / cal.SIM_MS / len(sp))
        mean = sum(means) / len(means)
        fb = full["per_rate"][str(r)]["onfly_mean_hz"]
        tol = max(REL_TOL * fb, ABS_FLOOR)
        ok = abs(mean - fb) <= tol
        ok_all = ok_all and ok
        per_rate[str(r)] = {"sub_mean_hz": mean, "full_mean_hz": fb,
                            "tolerance_hz": tol, "pass": ok}
        print("%6d %10.2f %10.2f %8.2f %6s"
              % (r, mean, fb, tol, "PASS" if ok else "FAIL"))
    out = {"decision": "D-181", "network": os.path.basename(path),
           "sha256": hashlib.sha256(io.open(path, "rb").read()).hexdigest(),
           "neurons": n, "edges": e, "need_bytes": need,
           "nfr_mem_01_pass": need is not None and need <= REGION_BYTES,
           "per_rate": per_rate, "acc3_pass": ok_all,
           "elapsed_s": round(time.time() - t0)}
    save_json(os.path.join(cal.CAL_DIR, "acc3-%s.json" % label), out)
    print("%s: %d neurons, %d edges, need=%d (NFR-MEM-01 %s), ACC-3 %s "
          "(%d s)" % (label, n, e, need,
                      "PASS" if out["nfr_mem_01_pass"] else "FAIL",
                      "PASS" if ok_all else "FAIL", out["elapsed_s"]))


# --- D-182 diagnostic: inhibitory closure ---------------------------------
CLOSURE_CAP = 4000                 # SR-EXT-03's largest candidate size


def inhibitory_closure(pre, post, sw, seed_nodes, min_syn, cap):
    """Grow ``seed_nodes`` by inhibitory presynaptic partners to a fixed
    point or until the set exceeds ``cap``.  Returns (nodes, history)."""
    inh = sw <= -min_syn                      # inhibitory, at least min_syn
    pre_i, post_i = pre[inh], post[inh]
    nodes = np.array(sorted(set(int(x) for x in seed_nodes)), dtype=np.int64)
    history = [int(len(nodes))]
    while True:
        new = np.unique(pre_i[np.isin(post_i, nodes)])
        grown = np.union1d(nodes, new)
        if len(grown) == len(nodes):
            break
        nodes = grown
        history.append(int(len(nodes)))
        if len(nodes) > cap:
            break
    return nodes, history


def closure(jobs):
    ranking = load_json(RANKING, None)
    full = load_json(ACC4, None)
    if ranking is None or full is None:
        raise SystemExit("need activity-ranking.json (--rank) and acc4.json")
    arrays, stim, read = cal.load_cache()
    pre, post, sw = (arrays["body_pre"], arrays["body_post"],
                     arrays["signed_weight"])
    cases = {}
    for n in (500, 1000):
        top = np.array([t["body"] for t in ranking["top1000"][:n]],
                       dtype=np.int64)
        seed_nodes = np.union1d(np.union1d(top, stim), read)
        for min_syn in (5, 1):
            nodes, hist = inhibitory_closure(pre, post, sw, seed_nodes,
                                             min_syn, CLOSURE_CAP)
            label = "n%d-s%d" % (n, min_syn)
            print("closure %s: %s%s" % (label, " -> ".join(str(h) for h
                                                          in hist),
                                        "  (over cap, not run)"
                                        if len(nodes) > CLOSURE_CAP else ""))
            entry = {"start_N": n, "min_syn": min_syn, "history": hist,
                     "neurons": int(len(nodes)),
                     "over_cap": bool(len(nodes) > CLOSURE_CAP)}
            if not entry["over_cap"]:
                blob, nn, e = emit.build_network(arrays, nodes, stim, read,
                                                 "closure-" + label)
                path = os.path.join(cal.CAL_DIR,
                                    "diag-closure-%s.bin" % label)
                io.open(path, "wb").write(blob)
                entry.update({"file": path, "edges": int(e),
                              "sha256": hashlib.sha256(blob).hexdigest()})
            cases[label] = entry
    del arrays

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

    jobs_list = [(c["file"], r, sd) for c in cases.values()
                 if not c["over_cap"] for r in VAL_RATES for sd in SEEDS]
    t0 = time.time()
    run_pool(jobs_list, jobs, [], on_done)

    print("%10s %6s %10s %10s %8s %6s" % ("case", "rate", "subcirc", "full",
                                         "tol", "ACC-3"))
    for label, c in cases.items():
        if c["over_cap"]:
            continue
        per_rate, ok_all, need = {}, True, None
        for r in VAL_RATES:
            means = []
            for sd in SEEDS:
                res, need = results[(c["file"], r, sd)]
                sp = [x["spikes"] for x in res["readouts"]]
                means.append(sum(sp) * 1000.0 / cal.SIM_MS / len(sp))
            mean = sum(means) / len(means)
            fb = full["per_rate"][str(r)]["onfly_mean_hz"]
            tol = max(REL_TOL * fb, ABS_FLOOR)
            ok = abs(mean - fb) <= tol
            ok_all = ok_all and ok
            per_rate[str(r)] = {"sub_mean_hz": mean, "full_mean_hz": fb,
                                "tolerance_hz": tol, "pass": ok}
            print("%10s %6d %10.2f %10.2f %8.2f %6s"
                  % (label, r, mean, fb, tol, "PASS" if ok else "FAIL"))
        c.update({"per_rate": per_rate, "acc3_pass": ok_all,
                  "need_bytes": need,
                  "nfr_mem_01_pass": need is not None
                  and need <= REGION_BYTES})
        print("%s: %d neurons, %d edges, need=%s (NFR-MEM-01 %s), ACC-3 %s"
              % (label, c["neurons"], c["edges"], need,
                 "PASS" if c["nfr_mem_01_pass"] else "FAIL",
                 "PASS" if ok_all else "FAIL"))
    out = {"decision": "D-182", "cap": CLOSURE_CAP, "cases": cases,
           "elapsed_s": round(time.time() - t0)}
    save_json(os.path.join(cal.CAL_DIR, "acc3-closure.json"), out)
    print("wrote acc3-closure.json (%d s)" % out["elapsed_s"])


# --- D-190..D-192: per-rate full-brain activity, the input to the bias ----
# The compensating input of D-190 stands for the drive a kept neuron's
# DROPPED presynaptic neurons used to supply, which is proportional to how
# often those neurons themselves fire.  SR-EXT-01's ranking sums firing over
# all eight rates and cannot answer that per rate, and D-191 measured why one
# number will not do: the population changes by recruitment, not by scaling.
#
# So this stage measures, for every neuron and every sampled rate, the mean
# spike count per run.  Rate 0 is not run: ACC-2 fixes its answer at exactly
# zero everywhere, and running it would only risk contradicting a criterion
# that is true by construction.
#
# Fifteen seeds per rate, and the estimator is the per-neuron MEDIAN over
# seeds (D-193, raised from D-192's three seeds and mean).
#
# Why the median.  A full-brain run either ignites the hyperactive population
# VL-66 found -- 191 neurons sustaining 250 to 280 Hz -- or it does not, so
# each neuron's spike count over seeds is bimodal rather than clustered
# around its mean.  A mean of a bimodal quantity sits between the two modes
# and, with the ignition tail far above the quiet mode, above the typical
# run: VL-71 measured the consequence directly, an N = 1000 bias of 18.55 in
# the 160 Hz row against 0.16 to 0.59 at every rate up to 120 Hz, with U_th
# at 7.0 mV, and every compensated network overshooting from 60 Hz up.  The
# median ignores the tail instead of averaging it in.
#
# Both estimators are stored, so the three-seed mean that produced VL-71
# stays auditable and that result reproducible.
RATEACT = os.path.join(cal.CAL_DIR, "rate-activity.npz")
BIAS_SEEDS = tuple(range(1, 16))                    # D-193
BIAS_RATES = (0,) + ALL_RATES                       # rate 0 row is zeros


def ratebias(jobs):
    """Mean per-neuron spike count at each sampled rate, on the full brain."""
    acc, order = {}, []

    def on_done(k, text):
        _p, r, s = k
        res = parse_all(text)
        if res["rc"] != 0 or res["counts"] is None:
            raise SystemExit("run %s failed:\n%s" % ((r, s), text[-2000:]))
        acc.setdefault(r, []).append(res["counts"])
        order.append((r, s))
        print("  %d of %d: rate=%d seed=%d"
              % (len(order), len(ALL_RATES) * len(BIAS_SEEDS), r, s))
        sys.stdout.flush()

    t0 = time.time()
    run_pool([(FULL, r, s) for r in ALL_RATES for s in BIAS_SEEDS],
             jobs, ["--all"], on_done)

    n = len(acc[ALL_RATES[0]][0])
    out = {"rates": np.array(BIAS_RATES, dtype=np.int64)}
    means = np.zeros((len(BIAS_RATES), n), dtype=np.float64)
    medians = np.zeros((len(BIAS_RATES), n), dtype=np.float64)
    for idx, r in enumerate(BIAS_RATES):
        if r == 0:
            continue                                # ACC-2: exactly zero
        seen = np.array(acc[r], dtype=np.float64)
        means[idx] = np.mean(seen, axis=0)
        medians[idx] = np.median(seen, axis=0)
    out["mean_spikes"] = means
    out["median_spikes"] = medians
    out["seeds"] = np.array(BIAS_SEEDS, dtype=np.int64)
    np.savez(RATEACT, **out)

    # Print both, because the gap between them IS the finding: where the mean
    # stands far above the median, the ignition tail of VL-66's hyperactive
    # population is what a three-seed mean was reporting (D-193).
    print("")
    print("%6s %14s %14s %10s %12s"
          % ("rate", "total (mean)", "total (median)", "neurons>0",
             "mean/median"))
    for idx, r in enumerate(BIAS_RATES):
        tm, td = means[idx].sum(), medians[idx].sum()
        print("%6d %14.1f %14.1f %10d %12s"
              % (r, tm, td, int((medians[idx] > 0).sum()),
                 "%.2f" % (tm / td) if td > 0 else "-"))
    print("wrote %s (%d neurons, %d rates, %d seeds, %d s)"
          % (RATEACT.replace("\\", "/"), n, len(BIAS_RATES),
             len(BIAS_SEEDS), round(time.time() - t0)))


# --- D-186..D-189: the compared truncation constructions -------------------
# Three constructions, all diagnostic (D-189): their networks live under
# data/calibration/ and nothing here amends SR-EXT-01 or SR-EXT-02.
#
#   A   selection only, SR-EXT-02 intact.  The activity ranking with part of
#       the budget spent on the readouts' inhibitory presynaptic partners,
#       until inhibition onto each readout is retained at least as well as
#       excitation.  No weight is touched.
#   B1  one-shot mean-field compensation, SR-EXT-02 amended.  The exact
#       SR-EXT-01 top-N sets, with the retained edges onto each kept neuron
#       scaled so that neuron's EXPECTED drive matches the full brain's.
#   B2  self-consistent rate matching, SR-EXT-02 amended.  B1's gains
#       refined by measuring each kept neuron's own firing inside the
#       subcircuit and damping its excitatory gain toward the rate it has in
#       the full brain.
#
# Why B2 exists.  Measured this session: at N = 1000 the top-N set already
# retains 91% of the left MN9's rate-weighted excitatory drive and 97% of
# its inhibitory drive, so B1's gains there are 1.1 and 1.0 and cannot
# explain a 126% overshoot.  The overshoot is the kept INTERIOR neurons
# firing faster than they do in the full brain, because their own inputs are
# truncated (VL-67's reading).  B1 corrects expected input; only B2 closes
# the loop on realised output.
#
# The readouts and the stimulus neurons are deliberately excluded from B2's
# update.  Tuning MN9's own gain toward MN9's full-brain rate would be
# fitting the very quantity ACC-3 measures, which would make the ACC-3
# result meaningless; leaving them out keeps ACC-3 an out-of-sample check
# that matching interior rates reproduces the readout.  The stimulus neurons
# are driven externally and have no synaptic input to scale.
GAIN_CAP = 20.0        # D-188 engineer's choice; binds nothing
DAMPING = 0.5          # exponent applied to the rate ratio each iteration
ITERATIONS = 4         # D-188 engineer's choice
B2_N = (500, 1000)     # D-188: B2 runs on these only
MATCH_SEEDS = (1, 2, 3)   # seeds for the cheap rate-matching runs
MATCH_EPS = 0.5           # half a spike, so a zero count is not a division
COMP = os.path.join(cal.CAL_DIR, "acc3-compensated.json")


def drive_model(arrays, totals):
    """Rate-weighted synaptic drive onto every neuron of the full brain.

    A presynaptic neuron's 'rate' here is its total spike count over the
    240-run SR-EXT-01 ranking (all eight TBD-07 rates, seeds 1..30).  Only
    ratios of these numbers ever matter, so no conversion to Hz is needed.
    One number per neuron rather than one per rate is what D-188 fixes: a
    per-rate gain would mean a different network file per rate, and MVS
    ships one file.
    """
    pre, post = arrays["body_pre"], arrays["body_post"]
    sw = arrays["signed_weight"]
    bodies = np.union1d(np.unique(pre), np.unique(post))
    if len(bodies) != len(totals):
        raise SystemExit("activity-totals.npy has %d entries but the network "
                         "has %d neurons" % (len(totals), len(bodies)))
    ipre = np.searchsorted(bodies, pre)
    ipost = np.searchsorted(bodies, post)
    rate = totals.astype(np.float64)
    mass = np.abs(sw).astype(np.float64) * rate[ipre]
    exc, inh = sw > 0, sw < 0
    nb = len(bodies)
    return {"bodies": bodies, "ipre": ipre, "ipost": ipost, "mass": mass,
            "exc": exc, "inh": inh, "rate": rate,
            "E_full": np.bincount(ipost[exc], weights=mass[exc], minlength=nb),
            "I_full": np.bincount(ipost[inh], weights=mass[inh], minlength=nb)}


def retained_drive(dm, arrays, nodes):
    """Drive onto every neuron counting only edges inside ``nodes``."""
    keep = (np.isin(arrays["body_pre"], nodes)
            & np.isin(arrays["body_post"], nodes))
    nb = len(dm["bodies"])
    ke, ki = keep & dm["exc"], keep & dm["inh"]
    return (np.bincount(dm["ipost"][ke], weights=dm["mass"][ke], minlength=nb),
            np.bincount(dm["ipost"][ki], weights=dm["mass"][ki], minlength=nb))


def meanfield_gains(dm, arrays, nodes):
    """B1's gains: restore each kept neuron's expected drive.

    A neuron whose excitatory (or inhibitory) input is entirely gone keeps a
    gain of 1: there is no edge left to scale, and inventing one would be a
    different construction.
    """
    e_sub, i_sub = retained_drive(dm, arrays, nodes)
    k = np.searchsorted(dm["bodies"], np.sort(nodes))
    ge = np.where(e_sub[k] > 0, dm["E_full"][k] / np.where(e_sub[k] > 0,
                                                           e_sub[k], 1.0), 1.0)
    gi = np.where(i_sub[k] > 0, dm["I_full"][k] / np.where(i_sub[k] > 0,
                                                           i_sub[k], 1.0), 1.0)
    return (np.clip(ge, 1.0 / GAIN_CAP, GAIN_CAP),
            np.clip(gi, 1.0 / GAIN_CAP, GAIN_CAP))


def readout_inputs(dm, arrays, read):
    """Per readout: its presynaptic partners, their mass and their sign.

    Construction A only ever needs the readouts' own incoming edges -- a few
    hundred of the 24.7 million -- so the budget scan below is cheap.
    """
    pre, post = arrays["body_pre"], arrays["body_post"]
    out = {}
    for r in np.sort(read):
        m = post == int(r)
        out[int(r)] = {"pre": pre[m], "mass": dm["mass"][m],
                       "exc": dm["exc"][m], "inh": dm["inh"][m]}
    return out


def balanced_nodes(dm, arrays, ranking, stim, read, n, rin):
    """Construction A's node set for budget ``n``.

    Spend the smallest k of the N slots on the readouts' inhibitory partners
    -- heaviest rate-weighted mass first, ties by ascending body id -- that
    makes inhibition onto every readout retained at least as well as
    excitation, and give the remaining N-k slots to the activity ranking.
    Returns (nodes, k, fractions).
    """
    top = np.array([t["body"] for t in ranking["top1000"]], dtype=np.int64)
    cand = []
    for r in sorted(rin):
        d = rin[r]
        for p, w in zip(d["pre"][d["inh"]], d["mass"][d["inh"]]):
            cand.append((-float(w), int(p)))
    cand.sort()
    seen, order = set(), []
    for _w, p in cand:
        if p not in seen:
            seen.add(p)
            order.append(p)

    def one_fraction(d, mask, members):
        tot = float(d["mass"][mask].sum())
        if tot <= 0:
            return 1.0
        got = float(sum(w for p, w in zip(d["pre"][mask], d["mass"][mask])
                        if int(p) in members))
        return got / tot

    def fractions(members):
        """(min excitatory fraction, min inhibitory fraction) over readouts."""
        fe, fi = 1.0, 1.0
        for r in sorted(rin):
            d = rin[r]
            fe = min(fe, one_fraction(d, d["exc"], members))
            fi = min(fi, one_fraction(d, d["inh"], members))
        return fe, fi

    base = set(int(x) for x in np.union1d(stim, read))
    chosen_k, frac = None, None
    for k in range(0, min(len(order), n) + 1):
        members = set(base)
        members.update(order[:k])
        members.update(int(x) for x in top[:max(n - k, 0)])
        fe, fi = fractions(members)
        if fi >= fe:
            chosen_k, frac = k, (fe, fi)
            break
    if chosen_k is None:                       # never balanced: spend it all
        k = min(len(order), n)
        members = set(base)
        members.update(order[:k])
        members.update(int(x) for x in top[:max(n - k, 0)])
        chosen_k, frac = k, fractions(members)
    nodes = np.array(sorted(members), dtype=np.int64)
    return nodes, chosen_k, {"exc_fraction": frac[0], "inh_fraction": frac[1]}


def emit_diag(arrays, nodes, stim, read, label, ge=None, gi=None):
    """Emit one diagnostic network under data/calibration/ (D-189)."""
    blob, nn, e = emit.build_network(arrays, nodes, stim, read, label,
                                     gain_exc=ge, gain_inh=gi)
    path = os.path.join(cal.CAL_DIR, "diag-%s.bin" % label)
    io.open(path, "wb").write(blob)
    return path, int(nn), int(e), hashlib.sha256(blob).hexdigest()


def match_once(path, jobs):
    """Sum per-neuron spike counts over ALL_RATES x MATCH_SEEDS."""
    acc = {"totals": None, "need": None}

    def on_done(_k, text):
        res = parse_all(text)
        if res["rc"] != 0 or res["counts"] is None:
            raise SystemExit("rate-matching run failed:\n%s" % text[-2000:])
        if acc["totals"] is None:
            acc["totals"] = np.zeros(res["n"], dtype=np.int64)
        acc["totals"] += res["counts"]
        acc["need"] = res["need"]

    run_pool([(path, r, s) for r in ALL_RATES for s in MATCH_SEEDS],
             jobs, ["--all"], on_done)
    return acc["totals"], acc["need"]


def rate_match(arrays, dm, nodes, ge, gi, stim, read, totals, label, jobs):
    """Construction B2: damp each interior neuron's excitatory gain toward
    the firing rate that neuron has in the full brain.

    Returns (ge, gi, history).  The readouts and the stimulus neurons are
    never updated -- see the note at the head of this section.
    """
    srt = np.sort(nodes)
    k = np.searchsorted(dm["bodies"], srt)
    full_mean = totals[k].astype(np.float64) / float(len(ALL_RATES)
                                                     * len(SEEDS))
    frozen = np.isin(srt, np.union1d(stim, read))
    history = []
    for it in range(ITERATIONS):
        path, nn, e, _sha = emit_diag(arrays, nodes, stim, read,
                                      "%s-it%d" % (label, it), ge, gi)
        sub, _need = match_once(path, jobs)
        sub_mean = sub.astype(np.float64) / float(len(ALL_RATES)
                                                  * len(MATCH_SEEDS))
        ratio = np.clip((full_mean + MATCH_EPS) / (sub_mean + MATCH_EPS),
                        0.1, 10.0)
        # log how far the interior is from the full brain before updating
        live = (~frozen) & ((full_mean > 0) | (sub_mean > 0))
        med = None
        if live.any():
            err = (np.abs(sub_mean[live] - full_mean[live])
                   / np.maximum(full_mean[live], MATCH_EPS))
            med = float(np.median(err))
        history.append({"iteration": it, "neurons": nn, "edges": e,
                        "interior_compared": int(live.sum()),
                        "median_rel_err": med})
        print("  %s it%d: %d interior neurons, median relative rate error %s"
              % (label, it, int(live.sum()),
                 "n/a" if med is None else "%.3f" % med))
        upd = np.where(frozen, 1.0, ratio ** DAMPING)
        ge = np.clip(ge * upd, 1.0 / GAIN_CAP, GAIN_CAP)
    return ge, gi, history


def acc3_eval(cases, full, jobs):
    """The VL-66 ACC-3 comparison, run over several networks at once."""
    results = {}

    def on_done(k, text):
        res = cal.parse_run(text)
        need = None
        for line in text.splitlines():
            if line.startswith("NET "):
                need = int(dict(t.split("=", 1) for t in line.split()[1:]
                                if "=" in t)["need"])
        if res["rc"] != 0 or len(res["readouts"]) != 2:
            raise SystemExit("run %s failed:\n%s" % (k, text[-2000:]))
        results[k] = (res, need)

    jobs_list = [(c["file"], r, s) for c in cases.values()
                 for r in VAL_RATES for s in SEEDS]
    run_pool(jobs_list, jobs, [], on_done)
    for label, c in cases.items():
        per_rate, ok_all, need = {}, True, None
        for r in VAL_RATES:
            means = []
            for s in SEEDS:
                res, need = results[(c["file"], r, s)]
                sp = [x["spikes"] for x in res["readouts"]]
                means.append(sum(sp) * 1000.0 / cal.SIM_MS / len(sp))
            mean = sum(means) / len(means)
            fb = full["per_rate"][str(r)]["onfly_mean_hz"]
            tol = max(REL_TOL * fb, ABS_FLOOR)
            ok = abs(mean - fb) <= tol
            ok_all = ok_all and ok
            per_rate[str(r)] = {"sub_mean_hz": mean, "full_mean_hz": fb,
                                "tolerance_hz": tol, "pass": ok}
        c["per_rate"] = per_rate
        c["acc3_pass"] = ok_all
        c["need_bytes"] = need
        c["nfr_mem_01_pass"] = need is not None and need <= REGION_BYTES
    return cases


def compensate(jobs):
    ranking = load_json(RANKING, None)
    full = load_json(ACC4, None)
    if ranking is None or full is None:
        raise SystemExit("need activity-ranking.json (--rank) and acc4.json")
    if not os.path.isfile(TOTALS):
        raise SystemExit("need %s (--rank)" % TOTALS)
    totals = np.load(TOTALS)
    arrays, stim, read = cal.load_cache()
    dm = drive_model(arrays, totals)
    rin = readout_inputs(dm, arrays, read)
    top1000 = np.array([t["body"] for t in ranking["top1000"]],
                       dtype=np.int64)

    t0 = time.time()
    cases, notes = {}, {}

    # --- A: selection only, weights unchanged ---------------------------
    for n in N_SEQ:
        nodes, k, frac = balanced_nodes(dm, arrays, ranking, stim, read, n,
                                        rin)
        label = "A-n%d" % n
        path, nn, e, sha = emit_diag(arrays, nodes, stim, read, label)
        cases[label] = {"construction": "A", "N": n, "file": path,
                        "neurons": nn, "edges": e, "sha256": sha,
                        "weights_changed": False,
                        "inhibitory_partners_added": k,
                        "readout_drive_fraction": frac}
        print("A  N=%d: %d neurons, %d edges, k=%d inhibitory partners, "
              "readout fractions exc %.3f inh %.3f"
              % (n, nn, e, k, frac["exc_fraction"], frac["inh_fraction"]))

    # --- B1: one-shot mean-field compensation ---------------------------
    b1_gains = {}
    for n in N_SEQ:
        nodes = np.union1d(np.union1d(top1000[:n], stim), read)
        ge, gi = meanfield_gains(dm, arrays, nodes)
        b1_gains[n] = (nodes, ge, gi)
        label = "B1-n%d" % n
        path, nn, e, sha = emit_diag(arrays, nodes, stim, read, label, ge, gi)
        cases[label] = {"construction": "B1", "N": n, "file": path,
                        "neurons": nn, "edges": e, "sha256": sha,
                        "weights_changed": True,
                        "gain_exc": {"median": float(np.median(ge)),
                                     "max": float(ge.max()),
                                     "min": float(ge.min())},
                        "gain_inh": {"median": float(np.median(gi)),
                                     "max": float(gi.max()),
                                     "min": float(gi.min())}}
        print("B1 N=%d: %d neurons, %d edges, alpha median %.2f max %.2f, "
              "beta median %.2f max %.2f"
              % (n, nn, e, np.median(ge), ge.max(), np.median(gi), gi.max()))

    # --- B2: self-consistent rate matching ------------------------------
    for n in B2_N:
        nodes, ge, gi = b1_gains[n]
        ge, gi, hist = rate_match(arrays, dm, nodes, ge.copy(), gi.copy(),
                                  stim, read, totals, "B2-n%d" % n, jobs)
        label = "B2-n%d" % n
        path, nn, e, sha = emit_diag(arrays, nodes, stim, read, label, ge, gi)
        cases[label] = {"construction": "B2", "N": n, "file": path,
                        "neurons": nn, "edges": e, "sha256": sha,
                        "weights_changed": True, "iterations": ITERATIONS,
                        "damping": DAMPING, "gain_cap": GAIN_CAP,
                        "history": hist,
                        "gain_exc": {"median": float(np.median(ge)),
                                     "max": float(ge.max()),
                                     "min": float(ge.min())}}

    notes["construction_A"] = ("selection only; SR-EXT-02's unchanged "
                               "weights intact")
    notes["construction_B1"] = ("SR-EXT-01 top-N with per-target gains so "
                                "each kept neuron's expected drive matches "
                                "the full brain; SR-EXT-02 deviated from")
    notes["construction_B2"] = ("B1's gains refined by rate matching on "
                                "interior neurons only; readouts and "
                                "stimulus neurons are never tuned, so ACC-3 "
                                "stays an out-of-sample check")
    cases = acc3_eval(cases, full, jobs)

    out = {"decisions": ["D-135", "D-165", "D-166", "D-186", "D-187",
                         "D-188", "D-189"],
           "full_brain_source": "data/calibration/acc4.json (same seeds)",
           "diagnostic_only": True, "notes": notes,
           "parameters": {"gain_cap": GAIN_CAP, "damping": DAMPING,
                          "iterations": ITERATIONS,
                          "match_seeds": list(MATCH_SEEDS),
                          "b2_N": list(B2_N)},
           "cases": cases, "elapsed_s": round(time.time() - t0)}
    save_json(COMP, out)

    print("")
    print("%-10s %6s %7s %8s %8s %8s %8s %8s  %s"
          % ("case", "N", "neurons", "10Hz", "40Hz", "60Hz", "120Hz",
             "200Hz", "ACC-3"))
    print("%-10s %6s %7s %8.2f %8.2f %8.2f %8.2f %8.2f  %s"
          % ("full brain", "-", 184099,
             *[full["per_rate"][str(r)]["onfly_mean_hz"] for r in VAL_RATES],
             "reference"))
    for label in sorted(cases):
        c = cases[label]
        print("%-10s %6d %7d %8.2f %8.2f %8.2f %8.2f %8.2f  %s"
              % (label, c["N"], c["neurons"],
                 *[c["per_rate"][str(r)]["sub_mean_hz"] for r in VAL_RATES],
                 "PASS" if c["acc3_pass"] else "FAIL"))
    passing = [l for l in sorted(cases) if cases[l]["acc3_pass"]]
    print("")
    print("ACC-3 passing constructions: %s"
          % (", ".join(passing) if passing else "none"))
    print("wrote %s (%d s)" % (COMP.replace("\\", "/"), out["elapsed_s"]))


# --- D-190..D-192: the compensated subcircuits -----------------------------
# The construction the owner chose to resolve SR-EXT-03's escalation.  Every
# earlier attempt (VL-66..VL-70) worked on the NETWORK -- which neurons to
# keep, what to do with the weights that survive -- and all eleven failed for
# one measured reason: a subcircuit small enough for the MVS region loses the
# neurons that DRIVE most of its own neurons, so 70% of a 500-neuron set and
# 54% of a 1000-neuron set never fire at all inside it.  No selection rule
# and no rescaling of a surviving edge can supply an input whose source is
# gone.
#
# This construction changes the MODEL instead: each kept neuron receives, at
# every step, the mean input its dropped presynaptic neurons used to deliver.
# That is a mean-field closure, the standard way to truncate a network, and
# it is why D-190 amends Appendix C rather than SR-EXT-01 or SR-EXT-02.
BIASNET = os.path.join(cal.CAL_DIR, "acc3-biasnet.json")
FIT_N = (500, 1000)     # D-199 engineer's choice


def bias_table(arrays, nodes, rate_act):
    """The v1.1 compensating-input table for one kept set.

    Returns ``(rates, rows)`` in the form netwrite.build wants: ``rates`` is
    the sampled stimulus rates ascending from 0, and ``rows[r][k]`` is the
    value added to the synaptic variable of the k-th kept neuron (in
    ascending body-id order) at every step of a request that selects row r.

    The arithmetic.  Neuron j fires S_j(rate) times in a run of ``steps``
    steps, measured on the full brain by --ratebias.  Each of those spikes
    adds w_ji to neuron i's synaptic variable, where w_ji is the signed
    synapse count times W_syn.  So the mean addition per step from a dropped
    presynaptic neuron j is w_ji * S_j(rate) / steps, and the row entry is
    that summed over every dropped presynaptic neuron of i:

        bias[rate][i] = sum over j not in S, j -> i of
                        w_ji * S_j(rate) / steps

    Dividing by the measurement's own step count is what makes the value a
    per-step expectation rather than a per-run one, so a request of any
    duration gets the same input per step.

    Rate 0's row is zero because --ratebias never runs rate 0: ACC-2 fixes
    its answer, and a measurement could only contradict a criterion that is
    true by construction.

    Every kept neuron gets a row entry, stimulus neurons included.  In the
    full brain a stimulus neuron receives synaptic input like any other, and
    omitting it would make the truncation less faithful, not more careful --
    its Poisson drive is delivered by ``force``, not through g.
    """
    pre, post = arrays["body_pre"], arrays["body_post"]
    sw = arrays["signed_weight"]
    rates = [int(r) for r in rate_act["rates"]]
    # D-193: the median over seeds, where the file has one.  A file written
    # before D-193 carries only the mean, and falling back to it keeps VL-71
    # reproducible from the artifact that produced it.
    key = ("median_spikes" if "median_spikes" in rate_act.files
           else "mean_spikes")
    mean = rate_act[key]                    # (len(rates), N_full)

    bodies = np.union1d(np.unique(pre), np.unique(post))
    srt = np.sort(nodes)
    # Edges whose TARGET is kept but whose SOURCE was dropped: exactly the
    # input the truncation removed.  An edge with both ends kept is still in
    # the network and must not be counted twice.
    keep_post = np.isin(post, srt)
    drop_pre = ~np.isin(pre, srt)
    lost = keep_post & drop_pre
    ipre = np.searchsorted(bodies, pre[lost])
    ipost = np.searchsorted(srt, post[lost])
    w = sw[lost].astype(np.float64) * emit.W_SYN

    steps = float(int(round(cal.SIM_MS / emit.DT_MS)))
    nk = len(srt)
    rows = []
    for r_i, r in enumerate(rates):
        if r == 0:
            rows.append([0.0] * nk)
            continue
        contrib = w * (mean[r_i][ipre] / steps)
        row = np.bincount(ipost, weights=contrib, minlength=nk)
        rows.append([float(x) for x in row])
    return rates, rows


def biasnet(jobs):
    """Emit the compensated subcircuits and put them through ACC-3."""
    ranking = load_json(RANKING, None)
    full = load_json(ACC4, None)
    if ranking is None or full is None:
        raise SystemExit("need activity-ranking.json (--rank) and acc4.json")
    if not os.path.isfile(RATEACT):
        raise SystemExit("need %s (--ratebias)" % RATEACT)
    rate_act = np.load(RATEACT)
    arrays, stim, read = cal.load_cache()
    top1000 = np.array([t["body"] for t in ranking["top1000"]],
                       dtype=np.int64)

    t0 = time.time()
    cases = {}
    for n in N_SEQ:
        nodes = np.union1d(np.union1d(top1000[:n], stim), read)
        rates, rows = bias_table(arrays, nodes, rate_act)
        label = "C-n%d" % n
        blob, nn, e = emit.build_network(arrays, nodes, stim, read, label,
                                         bias_rates=rates, bias_rows=rows)
        path = os.path.join(cal.CAL_DIR, "diag-%s.bin" % label)
        io.open(path, "wb").write(blob)
        mags = [max(abs(x) for x in row) if row else 0.0 for row in rows]
        cases[label] = {
            "construction": "C", "N": n, "file": path, "neurons": int(nn),
            "edges": int(e), "sha256": hashlib.sha256(blob).hexdigest(),
            "bias_rates": rates, "nbias": len(rates),
            "bias_max_abs_per_rate": mags,
        }
        print("C  N=%d: %d neurons, %d edges, %d bias rows, max |bias| "
              "per rate %s"
              % (n, nn, e, len(rates),
                 " ".join("%.4g" % m for m in mags)))
        sys.stdout.flush()

    cases = acc3_eval(cases, full, jobs)
    out = {"decisions": ["D-135", "D-165", "D-166", "D-190", "D-191",
                         "D-192"],
           "full_brain_source": "data/calibration/acc4.json (same seeds)",
           "diagnostic_only": True,
           "rate_activity": os.path.basename(RATEACT),
           "cases": cases, "elapsed_s": round(time.time() - t0)}
    save_json(BIASNET, out)

    print("")
    print("%-8s %6s %7s %8s %8s %8s %8s %8s  %s"
          % ("case", "N", "neurons", "10Hz", "40Hz", "60Hz", "120Hz",
             "200Hz", "ACC-3"))
    print("%-8s %6s %7s %8.2f %8.2f %8.2f %8.2f %8.2f  %s"
          % ("full", "-", 184099,
             *[full["per_rate"][str(r)]["onfly_mean_hz"] for r in VAL_RATES],
             "reference"))
    for label in sorted(cases):
        c = cases[label]
        print("%-8s %6d %7d %8.2f %8.2f %8.2f %8.2f %8.2f  %s"
              % (label, c["N"], c["neurons"],
                 *[c["per_rate"][str(r)]["sub_mean_hz"] for r in VAL_RATES],
                 "PASS" if c["acc3_pass"] else "FAIL"))
    for label in sorted(cases):
        c = cases[label]
        worst = max(abs(c["per_rate"][str(r)]["sub_mean_hz"]
                        - c["per_rate"][str(r)]["full_mean_hz"])
                    / c["per_rate"][str(r)]["full_mean_hz"]
                    for r in VAL_RATES)
        print("%-8s worst relative deviation %.0f%%  need=%s bytes "
              "(NFR-MEM-01 %s)"
              % (label, 100.0 * worst, c["need_bytes"],
                 "PASS" if c["nfr_mem_01_pass"] else "FAIL"))
    passing = [l for l in sorted(cases) if cases[l]["acc3_pass"]]
    print("")
    print("ACC-3 passing: %s" % (", ".join(passing) if passing else "none"))
    print("wrote %s (%d s)" % (BIASNET.replace("\\", "/"), out["elapsed_s"]))


# --- D-192 step 7: re-emit every fixture at network format version 1.1 -----
# Version 1.1 moved three header fields, so a v1.0 file is not merely older,
# it is unreadable: ONF103E.  Every network in the repository therefore has
# to be re-emitted, and this is the step that does it.
#
# It runs from data/calibration/signed.npz rather than from the MaleCNS
# feather files, because that cache IS prep/signs.build_signs's output --
# prep/calibrate.build_cache writes nothing else into it -- and the feather
# files are large, gitignored and absent from a fresh worktree.  The result
# is byte-identical either way; only the input path differs.
#
# Who gets a compensating table, and why:
#
#   full     none.  It drops nothing, so there is nothing to compensate for,
#            and nbias = 0 makes it run exactly the version 1.0 arithmetic.
#            That is what keeps data/calibration/acc4.json usable as ACC-3's
#            full-brain reference across the format change.
#   path     a real one.  This is the golden fixture ACC-5 is evaluated on,
#            so giving it a table is what makes `make test` exercise the new
#            code path rather than only its absence.  A path exercised only
#            on the platform hardest to test is a path nobody has tested.
#   hop2     a real one, for the same reason: it is a truncation.
#   n250/500/1000  none.  They are SR-EXT-01's sets under SR-EXT-02 as
#            WRITTEN, and D-189 keeps every compensated construction under
#            data/calibration/.  Mixing the two in data/networks/ would make
#            the directory ambiguous about which rule produced what.
FIXTURES = ("full", "hop2", "path")


def refixture():
    if not os.path.isfile(RATEACT):
        raise SystemExit("need %s (--ratebias)" % RATEACT)
    rate_act = np.load(RATEACT)
    arrays, stim, read = cal.load_cache()
    pre, post = arrays["body_pre"], arrays["body_post"]

    nodes_of = {
        "full": np.union1d(np.unique(pre), np.unique(post)),
        "hop2": np.union1d(emit.two_hop(pre, post, stim), read),
        "path": emit.path_restricted(pre, post, stim, read),
    }

    man = load_json(os.path.join(NET_DIR, "MANIFEST.json"), None)
    if man is None:
        raise SystemExit("data/networks/MANIFEST.json is missing")

    for label in FIXTURES:
        nodes = nodes_of[label]
        if label == "full":
            rates, rows = None, None
        else:
            rates, rows = bias_table(arrays, nodes, rate_act)
        blob, n, e = emit.build_network(arrays, nodes, stim, read, label,
                                        bias_rates=rates, bias_rows=rows)
        path = os.path.join(NET_DIR, "onfnet-malecns-v1.0-%s.bin" % label)
        io.open(path, "wb").write(blob)
        man["networks"][label] = {
            "file": os.path.basename(path), "neurons": int(n),
            "edges": int(e), "bytes": len(blob),
            "sha256": hashlib.sha256(blob).hexdigest(),
            "crc32": "%08X" % (zlib.crc32(blob) & 0xFFFFFFFF),
            "format_version": "1.1",
            "nbias": 0 if rates is None else len(rates),
        }
        print("  %-5s n=%-7d e=%-9d %10d bytes  nbias=%d"
              % (label, n, e, len(blob), 0 if rates is None else len(rates)))

    # The SR-EXT-01 subcircuits keep SR-EXT-02's unchanged weights and carry
    # no table; they are re-emitted only so that they are readable at all.
    ranking = load_json(RANKING, None)
    subman = load_json(SUBMAN, None)
    if ranking is not None and subman is not None:
        top1000 = np.array([t["body"] for t in ranking["top1000"]],
                           dtype=np.int64)
        for nsz in N_SEQ:
            nodes = np.union1d(np.union1d(top1000[:nsz], stim), read)
            blob, n, e = emit.build_network(arrays, nodes, stim, read,
                                            "n%d" % nsz)
            path = os.path.join(NET_DIR,
                                "onfnet-malecns-v1.0-n%d.bin" % nsz)
            io.open(path, "wb").write(blob)
            ent = subman["subcircuits"][str(nsz)]
            ent.update({"neurons": int(n), "edges": int(e),
                        "bytes": len(blob),
                        "sha256": hashlib.sha256(blob).hexdigest(),
                        "crc32": "%08X" % (zlib.crc32(blob) & 0xFFFFFFFF),
                        "format_version": "1.1", "nbias": 0})
            print("  n%-4d n=%-7d e=%-9d %10d bytes  nbias=0"
                  % (nsz, n, e, len(blob)))
        subman["format_version"] = "1.1"
        save_json(SUBMAN, subman)

    man["format_version"] = "1.1"
    man["decisions"] = sorted(set(man.get("decisions", []))
                              | {"D-190", "D-191", "D-192"})
    man["compensating_input"] = (
        "Format version 1.1 (D-190, IR-NET-09). The truncated fixtures carry "
        "a per-rate compensating-input table standing for the drive their "
        "dropped presynaptic neurons supplied; the full brain drops nothing "
        "and carries none, so its results are unchanged by the format "
        "change. The SR-EXT-01 subcircuits carry none: they are SR-EXT-02 as "
        "written, and every compensated construction lives under "
        "data/calibration/ (D-189).")
    save_json(os.path.join(NET_DIR, "MANIFEST.json"), man)
    print("wrote %s" % os.path.join(NET_DIR, "MANIFEST.json").replace("\\", "/"))


# --- D-194, D-197..D-199: the FITTED compensating input --------------------
# VL-72 left the measured bias with a signed error that changes direction:
# C-n500 undershoots the full brain at 10 and 40 Hz and overshoots it at 60,
# 120 and 200 Hz.  No single global multiplier can repair that, so the
# correction has to be a function of rate.
#
# Two fits, and the difference between them is the whole point:
#
#   F1  OUT OF SAMPLE.  The multiplier is a + b*R, two parameters, fitted so
#       the subcircuit's MN9 rate matches the full brain at the three
#       CALIBRATION rates {20, 80, 160} (D-165).  ACC-3 is then evaluated on
#       the five VALIDATION rates, which the fit never saw.  Two parameters
#       fitted on three points and tested on five others: this one can carry
#       evidence.
#
#   F2  IN SAMPLE.  One free multiplier per validation row, fitted straight
#       at the ACC-3 targets.  Nearest-rate row selection (D-191) makes each
#       row independent, so this is five parameters against ACC-3's five
#       constraints.  **A pass here is calibration, not truncation fidelity,
#       and is never reported as an ACC-3 pass on its own.**  Its only job is
#       to say whether the mechanism has the freedom at all -- if even a free
#       multiplier per rate cannot reach the targets, no estimator of the
#       bias ever will, and that is a strong negative result.
#
# Everything here is diagnostic (D-189): the networks live under
# data/calibration/ and nothing amends SR-EXT-01, SR-EXT-02 or ACC-3.
FITBIAS = os.path.join(cal.CAL_DIR, "acc3-fitbias.json")
FIT_SEEDS = tuple(range(1, 11))     # D-199 engineer's choice, binds nothing
FIT_CAP = 20.0                      # multiplier clipped to [0, FIT_CAP]
FIT_ITERS = 12                      # bisection steps per 1-D fit


def full_brain_mn9(rate_act, arrays, read):
    """Full-brain MN9 rate per sampled rate, from the 15-seed measurement.

    Returns {rate_hz: Hz}, averaged over both readouts (D-170) and taken from
    the MEAN over seeds, because ACC-3's statistic is a mean.  This is the
    only place the calibration rates {20, 80, 160} are available at all:
    acc4.json holds the five validation rates only.
    """
    pre, post = arrays["body_pre"], arrays["body_post"]
    bodies = np.union1d(np.unique(pre), np.unique(post))
    k = np.searchsorted(bodies, np.sort(read))
    rates = [int(r) for r in rate_act["rates"]]
    est = rate_act["mean_spikes"]
    out = {}
    for i, r in enumerate(rates):
        # spike count over a SIM_MS run -> Hz
        out[r] = float(est[i][k].mean()) * 1000.0 / cal.SIM_MS
    return out


def scaled_rows(rows, rates, scale_of):
    """Apply a per-rate multiplier to every bias row.

    ``scale_of`` maps a rate in Hz to its multiplier.  Rate 0's row is left
    alone: it is zero already, and IR-NET-09 requires it to stay zero so that
    ACC-2's silence holds by construction.
    """
    out = []
    for r, row in zip(rates, rows):
        if r == 0:
            out.append(list(row))
            continue
        m = float(scale_of(r))
        out.append([v * m for v in row])
    return out


def mn9_at(path, rate, seeds, jobs):
    """Mean MN9 rate over ``seeds`` at one rate, for one network."""
    got = {}

    def on_done(k, text):
        res = cal.parse_run(text)
        if res["rc"] != 0 or len(res["readouts"]) != 2:
            raise SystemExit("run %s failed:\n%s" % (k, text[-2000:]))
        sp = [x["spikes"] for x in res["readouts"]]
        got[k] = sum(sp) * 1000.0 / cal.SIM_MS / len(sp)

    run_pool([(path, rate, s) for s in seeds], jobs, [], on_done)
    return sum(got.values()) / len(got)


#: Coarse grid for the multiplier search.  Dense where the interesting
#: behaviour is and sparse above it, because the measurement below found the
#: peak near 0.5 and flat silence from 5 upwards.
FIT_GRID = (0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 1.0, 1.25, 1.5,
            2.0, 3.0, 5.0, 20.0)


def fit_one_rate(arrays, nodes, stim, read, rates, rows, rate, target,
                 label, jobs, log):
    """Find the row multiplier whose MN9 rate is closest to ``target``.

    A coarse scan followed by refinement inside the bracket, which is the
    method D-171 chose for the W_syn calibration and for the same reason:
    **the response is not monotone in the multiplier, so bisection misreads
    it.**  Measured on N = 500 at 40 Hz, MN9 goes 8.50, 12.15, 15.80, 11.80,
    9.30, 6.00, 2.15, 0.00 Hz at multipliers 0, 0.25, 0.5, 0.75, 1, 2, 3, 5
    -- it rises to a peak near 0.5 and then collapses to silence.

    Why it collapses.  The compensating input's sign onto the readout changes
    with rate: at 40 Hz the left MN9's own bias is -0.45 while the sum over
    all 501 kept neurons is +50.68, so a large multiplier suppresses the
    readout directly even as it drives everything else harder.  At 120 Hz the
    same readout's bias is +0.45 and the response rises monotonically to 20x.
    A bisection that assumed monotonicity returned the cap, 20, which is the
    worst multiplier available at that rate.

    The whole scan is written to ``log``, so the curve is auditable and the
    choice reproducible rather than merely asserted.  Returns the multiplier.
    """
    def rate_at(m):
        rws = scaled_rows(rows, rates, lambda r: m if r == rate else 0.0)
        path, _n, _e, _sha = emit_diag_bias(arrays, nodes, stim, read,
                                            "%s-probe" % label, rates, rws)
        v = mn9_at(path, rate, FIT_SEEDS, jobs)
        log.append({"rate": rate, "multiplier": m, "mn9_hz": v})
        return v

    seen = [(m, rate_at(m)) for m in FIT_GRID]
    best = min(range(len(seen)), key=lambda k: abs(seen[k][1] - target))

    # Refine between the grid neighbours of the best point.  Inside one grid
    # cell the curve has no room for a second turning point at this
    # resolution, so bisection is sound HERE even though it is not globally.
    lo = seen[best - 1][0] if best > 0 else seen[0][0]
    hi = seen[best + 1][0] if best + 1 < len(seen) else seen[-1][0]
    for _ in range(FIT_ITERS):
        if hi - lo < 1e-4:
            break
        m1 = lo + (hi - lo) / 3.0
        m2 = hi - (hi - lo) / 3.0
        if abs(rate_at(m1) - target) <= abs(rate_at(m2) - target):
            hi = m2
        else:
            lo = m1
    mid = 0.5 * (lo + hi)
    got = rate_at(mid)
    # Never return something the scan already beat.
    if abs(seen[best][1] - target) < abs(got - target):
        return seen[best][0]
    return mid


def edges_within(arrays, nodes):
    """The connectivity restricted to edges with both ends in ``nodes``.

    A fit probes one multiplier at a time and emits a network per probe, and
    emit.build_network's first act is to select exactly these edges out of
    24.7 million.  Doing that selection once per node set instead of once per
    probe is the difference between seconds and milliseconds, and it changes
    nothing: build_network re-runs the same test, which is then a no-op, and
    the surviving edges arrive in the same order, so the file is byte for
    byte what the unfiltered call produces.
    """
    pre, post = arrays["body_pre"], arrays["body_post"]
    keep = np.isin(pre, nodes) & np.isin(post, nodes)
    return {"body_pre": pre[keep], "body_post": post[keep],
            "signed_weight": arrays["signed_weight"][keep]}


def emit_diag_bias(arrays, nodes, stim, read, label, rates, rows):
    """Emit one diagnostic network carrying a compensating table."""
    blob, nn, e = emit.build_network(arrays, nodes, stim, read, label,
                                     bias_rates=rates, bias_rows=rows)
    path = os.path.join(cal.CAL_DIR, "diag-%s.bin" % label)
    io.open(path, "wb").write(blob)
    return path, int(nn), int(e), hashlib.sha256(blob).hexdigest()


def fitbias(jobs):
    ranking = load_json(RANKING, None)
    full = load_json(ACC4, None)
    if ranking is None or full is None:
        raise SystemExit("need activity-ranking.json (--rank) and acc4.json")
    if not os.path.isfile(RATEACT):
        raise SystemExit("need %s (--ratebias)" % RATEACT)
    rate_act = np.load(RATEACT)
    arrays, stim, read = cal.load_cache()
    top1000 = np.array([t["body"] for t in ranking["top1000"]],
                       dtype=np.int64)
    fb = full_brain_mn9(rate_act, arrays, read)
    print("full-brain MN9 targets (Hz, 15-seed mean): %s"
          % "  ".join("%d:%.2f" % (r, fb[r]) for r in sorted(fb)))
    sys.stdout.flush()

    t0 = time.time()
    cases, fits = {}, {}
    for n in FIT_N:
        nodes = np.union1d(np.union1d(top1000[:n], stim), read)
        # The bias table needs the FULL connectivity -- its whole content is
        # the drive from neurons OUTSIDE the kept set -- so it is built from
        # `arrays`.  Only the emission can use the restricted copy.
        rates, rows = bias_table(arrays, nodes, rate_act)
        sub = edges_within(arrays, nodes)

        # --- F2 first: one free multiplier per rate.  Its by-product is the
        # multiplier the response actually needs at each rate, which is what
        # F1's two parameters are then fitted to approximate.
        log = []
        per_rate_m = {}
        print("N=%d  F2: fitting one multiplier per rate" % n)
        sys.stdout.flush()
        for r in sorted(set(VAL_RATES) | set(cal.CAL_RATES)):
            m = fit_one_rate(sub, nodes, stim, read, rates, rows, r,
                             fb[r], "F-n%d" % n, jobs, log)
            per_rate_m[r] = m
            print("    rate %3d: multiplier %.4f  (target %.2f Hz)"
                  % (r, m, fb[r]))
            sys.stdout.flush()

        # --- F1: a + b*R fitted on the CALIBRATION rates only (D-165).
        # Least squares on two points is a line through them; with three it
        # is the closed-form fit below, and no optimiser is needed.
        cr = list(cal.CAL_RATES)
        xs = [float(r) for r in cr]
        ys = [per_rate_m[r] for r in cr]
        mx = sum(xs) / len(xs)
        my = sum(ys) / len(ys)
        sxx = 0.0
        sxy = 0.0
        for x, y in zip(xs, ys):
            sxx += (x - mx) * (x - mx)
            sxy += (x - mx) * (y - my)
        b = sxy / sxx if sxx > 0 else 0.0
        a = my - b * mx
        print("N=%d  F1: multiplier = %.5f + %.7f * R, fitted on %s"
              % (n, a, b, cr))
        sys.stdout.flush()

        def f1_scale(r, a=a, b=b):
            return min(max(a + b * r, 0.0), FIT_CAP)

        f1_rows = scaled_rows(rows, rates, f1_scale)
        path, nn, e, sha = emit_diag_bias(sub, nodes, stim, read,
                                          "F1-n%d" % n, rates, f1_rows)
        cases["F1-n%d" % n] = {
            "construction": "F1", "N": n, "file": path, "neurons": nn,
            "edges": e, "sha256": sha, "in_sample": False,
            "form": "a + b*R", "a": a, "b": b,
            "fitted_on": cr,
            "multiplier_at": dict((str(r), f1_scale(r)) for r in VAL_RATES),
        }

        def f2_scale(r, m=per_rate_m):
            return min(max(m.get(r, 1.0), 0.0), FIT_CAP)

        f2_rows = scaled_rows(rows, rates, f2_scale)
        path, nn, e, sha = emit_diag_bias(sub, nodes, stim, read,
                                          "F2-n%d" % n, rates, f2_rows)
        cases["F2-n%d" % n] = {
            "construction": "F2", "N": n, "file": path, "neurons": nn,
            "edges": e, "sha256": sha, "in_sample": True,
            "form": "one free multiplier per rate",
            "multiplier_at": dict((str(r), f2_scale(r)) for r in VAL_RATES),
            "caveat": ("five parameters against ACC-3's five constraints; a "
                       "pass is calibration, not truncation fidelity"),
        }
        fits["n%d" % n] = {"per_rate_multiplier": per_rate_m,
                           "f1_a": a, "f1_b": b, "probe_log": log}

    cases = acc3_eval(cases, full, jobs)
    out = {"decisions": ["D-165", "D-166", "D-191", "D-193", "D-194",
                         "D-197", "D-198", "D-199"],
           "full_brain_source": "data/calibration/acc4.json (30 seeds)",
           "fit_targets": dict((str(r), fb[r]) for r in sorted(fb)),
           "fit_target_source": ("data/calibration/rate-activity.npz, "
                                 "15-seed mean, both readouts (D-170)"),
           "diagnostic_only": True, "fit_seeds": list(FIT_SEEDS),
           "cases": cases, "fits": fits,
           "elapsed_s": round(time.time() - t0)}
    save_json(FITBIAS, out)

    print("")
    print("%-8s %6s %8s %8s %8s %8s %8s  %-6s %s"
          % ("case", "N", "10Hz", "40Hz", "60Hz", "120Hz", "200Hz", "ACC-3",
             "evidence"))
    print("%-8s %6s %8.2f %8.2f %8.2f %8.2f %8.2f  %-6s %s"
          % ("full", "-",
             *[full["per_rate"][str(r)]["onfly_mean_hz"] for r in VAL_RATES],
             "ref", "30-seed reference"))
    for label in sorted(cases):
        c = cases[label]
        print("%-8s %6d %8.2f %8.2f %8.2f %8.2f %8.2f  %-6s %s"
              % (label, c["N"],
                 *[c["per_rate"][str(r)]["sub_mean_hz"] for r in VAL_RATES],
                 "PASS" if c["acc3_pass"] else "FAIL",
                 "IN-SAMPLE, not fidelity" if c["in_sample"]
                 else "out of sample"))
    for label in sorted(cases):
        c = cases[label]
        worst = max(abs(c["per_rate"][str(r)]["sub_mean_hz"]
                        - c["per_rate"][str(r)]["full_mean_hz"])
                    / c["per_rate"][str(r)]["full_mean_hz"]
                    for r in VAL_RATES)
        above = max(abs(c["per_rate"][str(r)]["sub_mean_hz"]
                        - c["per_rate"][str(r)]["full_mean_hz"])
                    / c["per_rate"][str(r)]["full_mean_hz"]
                    for r in VAL_RATES[1:])
        print("%-8s worst %3.0f%%   above the 10 Hz floor %3.0f%%   "
              "need=%s bytes (NFR-MEM-01 %s)"
              % (label, 100 * worst, 100 * above, c["need_bytes"],
                 "PASS" if c["nfr_mem_01_pass"] else "FAIL"))
    print("")
    print("wrote %s (%d s)" % (FITBIAS.replace("\\", "/"), out["elapsed_s"]))


# --- D-200: F3, one constant multiplier ------------------------------------
# The most parsimonious form VL-73's data supports.  Its per-rate multipliers
# at N = 500 are flat at about 0.58 from 60 Hz up -- 0.6032, 0.5519, 0.5781,
# 0.6455, 0.6235 -- and F1's two-parameter line leans away from them only
# because the 20 Hz calibration point wants 0.2570.  One parameter fitted on
# three calibration rates and tested on five validation rates carries MORE
# evidence than F1's two, not less.
CONSTBIAS = os.path.join(cal.CAL_DIR, "acc3-constbias.json")


def const_objective(arrays, nodes, stim, read, rates, rows, targets, m,
                    label, jobs, log):
    """Mean relative error over the calibration rates at multiplier ``m``.

    The objective is SR-CAL-03's own form -- the mean over calibration rates
    of |measured - target| / target.  No rate is excluded: D-172's exclusion
    applies to a zero REFERENCE, and none of {20, 80, 160} has one here
    (5.63, 46.20, 76.57 Hz).
    """
    rws = scaled_rows(rows, rates, lambda r, m=m: m)
    path, _n, _e, _sha = emit_diag_bias(arrays, nodes, stim, read,
                                        "%s-probe" % label, rates, rws)
    errs = []
    for r in cal.CAL_RATES:
        v = mn9_at(path, r, FIT_SEEDS, jobs)
        errs.append(abs(v - targets[r]) / targets[r])
        log.append({"multiplier": m, "rate": r, "mn9_hz": v,
                    "target_hz": targets[r]})
    return sum(errs) / len(errs)


def fit_constant(arrays, nodes, stim, read, rates, rows, targets, label,
                 jobs, log):
    """Coarse scan then refine, for the same reason D-171 gave and VL-73
    measured: the response is not monotone in the multiplier, so a search
    that assumes it is will return the cap."""
    seen = [(m, const_objective(arrays, nodes, stim, read, rates, rows,
                                targets, m, label, jobs, log))
            for m in FIT_GRID]
    for m, err in seen:
        print("    scan x%-6.3g mean relative error %.4f" % (m, err))
        sys.stdout.flush()
    best = min(range(len(seen)), key=lambda k: seen[k][1])
    lo = seen[best - 1][0] if best > 0 else seen[0][0]
    hi = seen[best + 1][0] if best + 1 < len(seen) else seen[-1][0]
    for _ in range(6):
        if hi - lo < 1e-3:
            break
        m1 = lo + (hi - lo) / 3.0
        m2 = hi - (hi - lo) / 3.0
        e1 = const_objective(arrays, nodes, stim, read, rates, rows, targets,
                             m1, label, jobs, log)
        e2 = const_objective(arrays, nodes, stim, read, rates, rows, targets,
                             m2, label, jobs, log)
        if e1 <= e2:
            hi = m2
        else:
            lo = m1
    mid = 0.5 * (lo + hi)
    emid = const_objective(arrays, nodes, stim, read, rates, rows, targets,
                           mid, label, jobs, log)
    if seen[best][1] < emid:
        return seen[best][0], seen[best][1]
    return mid, emid


def constbias(jobs):
    ranking = load_json(RANKING, None)
    full = load_json(ACC4, None)
    if ranking is None or full is None:
        raise SystemExit("need activity-ranking.json (--rank) and acc4.json")
    if not os.path.isfile(RATEACT):
        raise SystemExit("need %s (--ratebias)" % RATEACT)
    rate_act = np.load(RATEACT)
    arrays, stim, read = cal.load_cache()
    top1000 = np.array([t["body"] for t in ranking["top1000"]],
                       dtype=np.int64)
    fb = full_brain_mn9(rate_act, arrays, read)
    print("calibration targets (Hz): %s"
          % "  ".join("%d:%.2f" % (r, fb[r]) for r in cal.CAL_RATES))
    sys.stdout.flush()

    t0 = time.time()
    cases, fits = {}, {}
    for n in FIT_N:
        nodes = np.union1d(np.union1d(top1000[:n], stim), read)
        rates, rows = bias_table(arrays, nodes, rate_act)
        sub = edges_within(arrays, nodes)
        log = []
        print("N=%d  F3: fitting one constant multiplier on %s"
              % (n, list(cal.CAL_RATES)))
        sys.stdout.flush()
        m, err = fit_constant(sub, nodes, stim, read, rates, rows, fb,
                              "F3-n%d" % n, jobs, log)
        print("N=%d  F3: multiplier %.4f, mean relative error %.4f on the "
              "calibration rates" % (n, m, err))
        sys.stdout.flush()
        f3_rows = scaled_rows(rows, rates, lambda r, m=m: m)
        path, nn, e, sha = emit_diag_bias(sub, nodes, stim, read,
                                          "F3-n%d" % n, rates, f3_rows)
        cases["F3-n%d" % n] = {
            "construction": "F3", "N": n, "file": path, "neurons": nn,
            "edges": e, "sha256": sha, "in_sample": False,
            "form": "one constant multiplier", "multiplier": m,
            "fitted_on": list(cal.CAL_RATES),
            "calibration_mean_rel_err": err,
        }
        fits["n%d" % n] = {"multiplier": m, "calibration_error": err,
                           "probe_log": log}

    cases = acc3_eval(cases, full, jobs)
    out = {"decisions": ["D-165", "D-166", "D-171", "D-191", "D-193",
                         "D-199", "D-200"],
           "full_brain_source": "data/calibration/acc4.json (30 seeds)",
           "fit_targets": dict((str(r), fb[r]) for r in sorted(fb)),
           "fit_target_source": ("data/calibration/rate-activity.npz, "
                                 "15-seed mean, both readouts (D-170)"),
           "diagnostic_only": True, "fit_seeds": list(FIT_SEEDS),
           "cases": cases, "fits": fits,
           "elapsed_s": round(time.time() - t0)}
    save_json(CONSTBIAS, out)

    print("")
    print("%-8s %6s %8s %8s %8s %8s %8s  %-6s %s"
          % ("case", "N", "10Hz", "40Hz", "60Hz", "120Hz", "200Hz", "ACC-3",
             "rates inside"))
    print("%-8s %6s %8.2f %8.2f %8.2f %8.2f %8.2f  %-6s %s"
          % ("full", "-",
             *[full["per_rate"][str(r)]["onfly_mean_hz"] for r in VAL_RATES],
             "ref", "-"))
    for label in sorted(cases):
        c = cases[label]
        inside = sum(1 for r in VAL_RATES if c["per_rate"][str(r)]["pass"])
        print("%-8s %6d %8.2f %8.2f %8.2f %8.2f %8.2f  %-6s %d of 5"
              % (label, c["N"],
                 *[c["per_rate"][str(r)]["sub_mean_hz"] for r in VAL_RATES],
                 "PASS" if c["acc3_pass"] else "FAIL", inside))
    for label in sorted(cases):
        c = cases[label]
        worst = max(abs(c["per_rate"][str(r)]["sub_mean_hz"]
                        - c["per_rate"][str(r)]["full_mean_hz"])
                    / c["per_rate"][str(r)]["full_mean_hz"]
                    for r in VAL_RATES)
        above = max(abs(c["per_rate"][str(r)]["sub_mean_hz"]
                        - c["per_rate"][str(r)]["full_mean_hz"])
                    / c["per_rate"][str(r)]["full_mean_hz"]
                    for r in VAL_RATES[1:])
        print("%-8s multiplier %.4f   worst %3.0f%%   above the 10 Hz floor "
              "%3.0f%%   need=%s bytes (NFR-MEM-01 %s)"
              % (label, c["multiplier"], 100 * worst, 100 * above,
                 c["need_bytes"], "PASS" if c["nfr_mem_01_pass"] else "FAIL"))
    print("")
    print("wrote %s (%d s)" % (CONSTBIAS.replace("\\", "/"),
                               out["elapsed_s"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rank", action="store_true")
    ap.add_argument("--closure", action="store_true")
    ap.add_argument("--acc3-file", default=None)
    ap.add_argument("--label", default=None)
    ap.add_argument("--extract", action="store_true")
    ap.add_argument("--acc3", action="store_true")
    ap.add_argument("--diag", action="store_true")
    ap.add_argument("--compensate", action="store_true")
    ap.add_argument("--ratebias", action="store_true")
    ap.add_argument("--biasnet", action="store_true")
    ap.add_argument("--refixture", action="store_true")
    ap.add_argument("--fitbias", action="store_true")
    ap.add_argument("--constbias", action="store_true")
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
    if a.diag:
        diag(a.jobs)
    if a.acc3_file:
        acc3_file(a.acc3_file, a.label or "file", a.jobs)
    if a.closure:
        closure(a.jobs)
    if a.ratebias:
        ratebias(a.jobs)
    if a.compensate:
        compensate(a.jobs)
    if a.refixture:
        refixture()
    if a.biasnet:
        biasnet(a.jobs)
    if a.fitbias:
        fitbias(a.jobs)
    if a.constbias:
        constbias(a.jobs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
