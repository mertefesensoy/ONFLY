# -*- coding: utf-8 -*-
"""W_syn calibration on the full MaleCNS brain (SR-CAL-01..03, D-168..D-171).

What is calibrated, and against what
------------------------------------
SR-CAL-01: on the full-brain model, never on a subcircuit.  Every candidate
W_syn is a complete 184,099-neuron network emitted by ``emit.build_network``,
run by ``build/runnet.exe`` (the x86 engine, NATIVE backend, oracle O-2).

SR-CAL-02 / D-165: calibration rates {20, 80, 160} Hz.  The validation rates
{10, 40, 60, 120, 200} Hz are never used by the search.

SR-CAL-03: the objective is the mean, over the calibration rates, of the
relative error between ONFLY's MN9 rate and the Shiu reference at that rate.
D-170 fixes "MN9 rate" as the mean over both MN9 neurons; D-169 fixes three
seeds (1, 2, 3) per rate, so ONFLY's value at one rate is the mean of six
numbers (two readouts x three seeds), each ``spikes / 1.0 s``.

SR-CAL-04 / D-164: the reference is ``reference/shiu/results/mn9-reference.csv``
produced by ``reference/shiu/rerun.py``.

D-171: coarse scan over {0.10, 0.15, 0.20, 0.25, 0.275, 0.30, 0.35, 0.40} mV,
then golden-section inside the bracket around the best scan point until the
bracket is narrower than 0.005 mV.  The chosen value is the candidate with the
smallest error among everything evaluated, and every candidate is kept in
``data/calibration/search-log.json`` (SR-CAL-03: "the search log shall be
kept").

Calibration rates with a zero reference (D-172)
------------------------------------------------
The D-164 re-run found Shiu's MN9 silent at 20 Hz in all 30 trials, so the
relative error there is undefined.  Per D-172 such rates are excluded from the
objective -- the mean is taken over the calibration rates whose reference is
above zero -- and ONFLY's rate at the excluded rates is still recorded in the
log and reported as a finding.

Determinism
-----------
With fixed seeds the engine is deterministic, so the objective is a function
of W_syn alone and the whole search is reproducible from the log.

Run (repository root):

    python prep/calibrate.py --cache          # signed counts, once (~2 min)
    python prep/calibrate.py --scan           # D-171 scan, reference not needed
    python prep/calibrate.py --refine         # golden-section, needs reference
    python prep/calibrate.py --status
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

import emit                                   # noqa: E402

CAL_DIR = os.path.join(ROOT, "data", "calibration")
CACHE = os.path.join(CAL_DIR, "signed.npz")
LOG = os.path.join(CAL_DIR, "search-log.json")
REFERENCE = os.path.join(ROOT, "reference", "shiu", "results",
                         "mn9-reference.csv")
RUNNET = os.path.join(ROOT, "build", "runnet.exe")

CAL_RATES = (20, 80, 160)            # D-165
SEEDS = (1, 2, 3)                    # D-169
SIM_MS = 1000                        # D-73 standard duration
SCAN = (0.10, 0.15, 0.20, 0.25, 0.275, 0.30, 0.35, 0.40)   # D-171
RESOLUTION = 0.005                   # D-171, mV
GOLD = (math.sqrt(5.0) - 1.0) / 2.0


def key(w):
    return "%.4f" % w


def load_log():
    if os.path.isfile(LOG):
        return json.load(io.open(LOG, encoding="utf-8"))
    return {"candidates": {}, "scan": [], "refine": [], "chosen": None,
            "decisions": ["D-164", "D-165", "D-166", "D-169", "D-170",
                          "D-171"],
            "objective": "D-172: mean over CAL_RATES with ref > 0 of "
                         "|onfly-ref|/ref",
            "cal_rates_hz": list(CAL_RATES), "seeds": list(SEEDS),
            "sim_ms": SIM_MS}


def save_log(log):
    if not os.path.isdir(CAL_DIR):
        os.makedirs(CAL_DIR)
    io.open(LOG, "w", encoding="utf-8", newline="\n").write(
        json.dumps(log, indent=2, sort_keys=True) + "\n")


# --- signed counts cache -------------------------------------------------
def build_cache():
    import signs
    print("building the signed-count cache (D-54, D-55, D-56) ...")
    t0 = time.time()
    arrays, stats = signs.build_signs(verbose=False)
    mapping = json.load(io.open(emit.MAPPING, encoding="utf-8"))
    stim = np.array(mapping["stimulus_set"]["bodyIds"], dtype=np.int64)
    read = np.array(mapping["readout"]["bodyIds"], dtype=np.int64)
    if not os.path.isdir(CAL_DIR):
        os.makedirs(CAL_DIR)
    np.savez(CACHE, body_pre=arrays["body_pre"], body_post=arrays["body_post"],
             signed_weight=arrays["signed_weight"], stim=stim, read=read)
    print("  %d pairs, %d synapses, %.0f s -> %s"
          % (len(arrays["body_pre"]), stats["synapses_kept"],
             time.time() - t0, CACHE.replace("\\", "/")))


def load_cache():
    if not os.path.isfile(CACHE):
        build_cache()
    z = np.load(CACHE)
    arrays = {"body_pre": z["body_pre"], "body_post": z["body_post"],
              "signed_weight": z["signed_weight"]}
    return arrays, z["stim"], z["read"]


# --- one candidate --------------------------------------------------------
def emit_candidate(w_syn, arrays, stim, read):
    nodes = np.union1d(np.unique(arrays["body_pre"]),
                       np.unique(arrays["body_post"]))
    blob, n, e = emit.build_network(arrays, nodes, stim, read,
                                    "w=%s" % key(w_syn), w_syn=w_syn,
                                    max_ms=emit.MAX_MS)
    path = os.path.join(CAL_DIR, "net-%s.bin" % key(w_syn))
    io.open(path, "wb").write(blob)
    return path, n, e, hashlib.sha256(blob).hexdigest(), \
        "%08X" % (zlib.crc32(blob) & 0xFFFFFFFF)


def parse_run(text):
    out = {"readouts": [], "rc": None, "steps": None}
    for line in text.splitlines():
        parts = line.split()
        if not parts:
            continue
        f = dict(t.split("=", 1) for t in parts[1:] if "=" in t)
        if parts[0] == "RUN":
            out["rc"] = int(f["rc"])
            out["steps"] = int(f["steps"])
        elif parts[0] == "READOUT":
            out["readouts"].append({"n": int(f["n"]),
                                    "spikes": int(f["spikes"]),
                                    "first": int(f["first"])})
    return out


def run_candidate(path, jobs):
    """Nine engine runs (3 rates x 3 seeds), at most ``jobs`` at a time."""
    todo = [(r, s) for r in CAL_RATES for s in SEEDS]
    procs, results = {}, {}
    while todo or procs:
        while todo and len(procs) < jobs:
            r, s = todo.pop(0)
            p = subprocess.Popen([RUNNET, path, str(r), str(SIM_MS), str(s)],
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, text=True)
            procs[(r, s)] = p
        for k, p in list(procs.items()):
            if p.poll() is not None:
                text = p.stdout.read()
                res = parse_run(text)
                if res["rc"] != 0 or len(res["readouts"]) != 2:
                    raise SystemExit("run %s failed:\n%s" % (k, text))
                results[k] = res
                del procs[k]
        time.sleep(2)
    return results


def onfly_rates(results):
    """D-170 / D-169: mean over both readouts and all seeds, per rate."""
    rates = {}
    for r in CAL_RATES:
        vals = []
        for s in SEEDS:
            for ro in results[(r, s)]["readouts"]:
                vals.append(ro["spikes"] * 1000.0 / SIM_MS)
        rates[str(r)] = sum(vals) / len(vals)
    return rates


def evaluate(w_syn, log, arrays, stim, read, jobs, keep):
    k = key(w_syn)
    if k in log["candidates"] and "onfly_hz" in log["candidates"][k]:
        return log["candidates"][k]
    print("candidate W_syn = %s mV" % k)
    t0 = time.time()
    path, n, e, sha, crc = emit_candidate(w_syn, arrays, stim, read)
    t1 = time.time()
    results = run_candidate(path, jobs)
    t2 = time.time()
    entry = {
        "w_syn": float(k), "network": {"file": os.path.basename(path),
                                       "neurons": int(n), "edges": int(e),
                                       "sha256": sha, "crc32": crc,
                                       "max_ms": emit.MAX_MS},
        "runs": {"%d/%d" % k2: v for k2, v in results.items()},
        "onfly_hz": onfly_rates(results),
        "emit_s": round(t1 - t0, 1), "run_s": round(t2 - t1, 1),
    }
    log["candidates"][k] = entry
    save_log(log)
    if not keep:
        os.remove(path)
    print("  MN9 %s  (emit %.0f s, runs %.0f s)"
          % (" ".join("%s Hz: %.2f" % (r, v)
                      for r, v in sorted(entry["onfly_hz"].items(),
                                         key=lambda kv: int(kv[0]))),
             t1 - t0, t2 - t1))
    return entry


# --- objective -------------------------------------------------------------
def load_reference():
    if not os.path.isfile(REFERENCE):
        return None
    ref = {}
    lines = io.open(REFERENCE, encoding="utf-8").read().splitlines()
    cols = lines[0].split(",")
    for line in lines[1:]:
        f = dict(zip(cols, line.split(",")))
        ref[str(int(f["rate_hz"]))] = float(f["mn9_mean_hz"])
    return ref


def error(entry, ref):
    """D-172: mean relative error over the calibration rates whose reference
    is above zero; the excluded rates are returned for the record."""
    errs, excluded = [], []
    for r in CAL_RATES:
        o = entry["onfly_hz"][str(r)]
        t = ref[str(r)]
        if t <= 0.0:
            excluded.append(r)
            continue
        errs.append(abs(o - t) / t)
    if not errs:
        raise SystemExit("every calibration rate has a zero reference")
    return sum(errs) / len(errs), excluded


def score_all(log, ref):
    for k, entry in log["candidates"].items():
        if "onfly_hz" in entry:
            e, excluded = error(entry, ref)
            entry["error"] = e
            entry["excluded_rates"] = excluded
    log["reference"] = ref
    if "D-172" not in log["decisions"]:
        log["decisions"].append("D-172")
    save_log(log)


# --- search ------------------------------------------------------------------
def scan(log, arrays, stim, read, jobs, keep):
    for w in SCAN:
        evaluate(w, log, arrays, stim, read, jobs, keep)
        if key(w) not in log["scan"]:
            log["scan"].append(key(w))
            save_log(log)


def refine(log, arrays, stim, read, jobs, keep, ref):
    score_all(log, ref)
    scanned = [(log["candidates"][key(w)]["error"], w) for w in SCAN]
    best_i = min(range(len(SCAN)), key=lambda i: (scanned[i][0], i))
    a = SCAN[max(best_i - 1, 0)]
    b = SCAN[min(best_i + 1, len(SCAN) - 1)]
    print("scan minimum at %s mV (error %.4f); bracket [%s, %s]"
          % (key(SCAN[best_i]), scanned[best_i][0], key(a), key(b)))

    def f(w):
        entry = evaluate(w, log, arrays, stim, read, jobs, keep)
        e, _ = error(entry, ref)
        entry["error"] = e
        save_log(log)
        return e

    c = b - GOLD * (b - a)
    d = a + GOLD * (b - a)
    fc, fd = f(c), f(d)
    while (b - a) > RESOLUTION:
        if fc < fd:
            b, d, fd = d, c, fc
            c = b - GOLD * (b - a)
            fc = f(c)
        else:
            a, c, fc = c, d, fd
            d = a + GOLD * (b - a)
            fd = f(d)
        log["refine"].append({"a": key(a), "b": key(b)})
        save_log(log)
    score_all(log, ref)
    best = min(log["candidates"].values(),
               key=lambda e: (e["error"], e["w_syn"]))
    log["chosen"] = {"w_syn": best["w_syn"], "error": best["error"],
                     "onfly_hz": best["onfly_hz"],
                     "bracket_final": [key(a), key(b)]}
    save_log(log)
    return log["chosen"]


def status(log):
    ref = log.get("reference")
    print("%-8s %8s %8s %8s %8s" % ("W_syn", "20Hz", "80Hz", "160Hz", "error"))
    for k in sorted(log["candidates"], key=float):
        e = log["candidates"][k]
        o = e.get("onfly_hz", {})
        print("%-8s %8.2f %8.2f %8.2f %8s"
              % (k, o.get("20", float("nan")), o.get("80", float("nan")),
                 o.get("160", float("nan")),
                 ("%.4f" % e["error"]) if "error" in e else "-"))
    if ref:
        print("%-8s %8.2f %8.2f %8.2f   (Shiu reference, D-170 mean)"
              % ("ref", ref["20"], ref["80"], ref["160"]))
    if log.get("chosen"):
        print("chosen: W_syn = %.4f mV, error %.4f"
              % (log["chosen"]["w_syn"], log["chosen"]["error"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache", action="store_true")
    ap.add_argument("--scan", action="store_true")
    ap.add_argument("--refine", action="store_true")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--jobs", type=int, default=3)
    ap.add_argument("--keep", action="store_true",
                    help="keep the emitted candidate networks on disk")
    a = ap.parse_args()
    log = load_log()
    if a.status:
        status(log)
        return 0
    if a.cache:
        build_cache()
        return 0
    if not os.path.isfile(RUNNET):
        raise SystemExit("build the runner first: mingw32-make runner")
    arrays, stim, read = load_cache()
    if a.scan:
        scan(log, arrays, stim, read, a.jobs, a.keep)
    if a.refine:
        ref = load_reference()
        if ref is None:
            raise SystemExit("no reference yet: run reference/shiu/rerun.py")
        chosen = refine(log, arrays, stim, read, a.jobs, a.keep, ref)
        print("chosen W_syn = %.4f mV, error %.4f"
              % (chosen["w_syn"], chosen["error"]))
    status(log)
    return 0


if __name__ == "__main__":
    sys.exit(main())
