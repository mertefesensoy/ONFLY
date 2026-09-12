# -*- coding: utf-8 -*-
"""ACC-4 (and previews of ACC-1, ACC-2) at the calibrated W_syn, on x86.

What this evaluates
-------------------
SR-CAL-05 asks whether the calibrated W_syn satisfies ACC-4 on the validation
rates {10, 40, 60, 120, 200} Hz (D-165), and if not, that the result is
reported as a finding rather than tolerances widened.  Each validation rate is
run with 30 seeds (D-135), 1000 ms (D-73), on the full MaleCNS brain via
``build/runnet.exe`` -- the same network `prep/calibrate.py` chose.

ACC-4 as written (Section 6.4, floors from D-166):

  shape      the MN9 rate does not decrease between successive validation
             rates by more than one standard error, and the onset rate (the
             lowest validation rate with mean above 1 Hz) is within one
             sampled rate of the reference's onset;
  magnitude  each validation point is within +-25% of the reference, or
             within +-2 Hz, whichever is larger.

Interpretation recorded as proposal P-11 (the SRS does not say which standard
error): the allowed decrease from rate r_i to r_{i+1} is the standard error of
ONFLY's own mean at r_i, sd_i / sqrt(30).

ACC-1 (qualitative feeding) and ACC-2 (silence at rate 0) are computed too,
but ACC-1 is defined on the MVS subcircuit, so its value here is a preview of
the full-brain x86 model, not a pass.  ACC-2 on x86 NATIVE is one row of the
platforms it must hold on.

Run (repository root, after calibrate.py --refine):

    python prep/acc4.py [--jobs 9] [--w-syn 0.2345]
"""
import argparse
import io
import json
import math
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import calibrate as cal                       # noqa: E402

VAL_RATES = (10, 40, 60, 120, 200)           # D-165
N_SEEDS = 30                                 # D-135
REL_TOL = 0.25                               # ACC-4
ABS_FLOOR = 2.0                              # D-166
ONSET_HZ = 1.0                               # ACC-4 onset definition
OUT = os.path.join(cal.CAL_DIR, "acc4.json")


def run_many(path, jobs, rates, seeds):
    todo = [(r, s) for r in rates for s in seeds]
    procs, results = {}, {}
    while todo or procs:
        while todo and len(procs) < jobs:
            r, s = todo.pop(0)
            p = subprocess.Popen([cal.RUNNET, path, str(r), str(cal.SIM_MS),
                                  str(s)], stdout=subprocess.PIPE,
                                 stderr=subprocess.STDOUT, text=True)
            procs[(r, s)] = p
        for k, p in list(procs.items()):
            if p.poll() is not None:
                text = p.stdout.read()
                res = cal.parse_run(text)
                if res["rc"] != 0 or len(res["readouts"]) != 2:
                    raise SystemExit("run %s failed:\n%s" % (k, text))
                results[k] = res
                del procs[k]
                done = len(results)
                if done % 10 == 0:
                    print("  %d of %d runs done" % (done, done + len(todo)
                                                    + len(procs)))
        time.sleep(2)
    return results


def stats(values):
    n = len(values)
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / (n - 1) if n > 1 else 0.0
    sd = math.sqrt(var)
    return mean, sd, sd / math.sqrt(n)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=9)
    ap.add_argument("--w-syn", type=float, default=None,
                    help="override the calibrate.py choice")
    a = ap.parse_args()

    log = cal.load_log()
    if a.w_syn is None:
        if not log.get("chosen"):
            raise SystemExit("no chosen W_syn: run calibrate.py --refine")
        w_syn = log["chosen"]["w_syn"]
    else:
        w_syn = a.w_syn
    ref = cal.load_reference()
    if ref is None:
        raise SystemExit("no reference: run reference/shiu/rerun.py")

    arrays, stim, read = cal.load_cache()
    print("emitting the full network at W_syn = %s mV" % cal.key(w_syn))
    path, n, e, sha, crc = cal.emit_candidate(w_syn, arrays, stim, read)
    del arrays

    seeds = list(range(1, N_SEEDS + 1))
    t0 = time.time()
    print("running %d validation rates x %d seeds, plus rate 0"
          % (len(VAL_RATES), N_SEEDS))
    res = run_many(path, a.jobs, VAL_RATES, seeds)
    res0 = run_many(path, a.jobs, (0,), (1,))
    elapsed = time.time() - t0

    per_rate = {}
    for r in VAL_RATES:
        means = []            # D-170 quantity per seed
        any_spike = 0
        for s in seeds:
            ro = res[(r, s)]["readouts"]
            spikes = [x["spikes"] for x in ro]
            means.append(sum(spikes) * 1000.0 / cal.SIM_MS / len(spikes))
            if max(spikes) > 0:
                any_spike += 1
        mean, sd, se = stats(means)
        t = ref[str(r)]
        tol = max(REL_TOL * t, ABS_FLOOR)
        per_rate[str(r)] = {
            "onfly_mean_hz": mean, "onfly_sd_hz": sd, "onfly_se_hz": se,
            "reference_hz": t, "tolerance_hz": tol,
            "magnitude_pass": abs(mean - t) <= tol,
            "seeds_with_mn9_spike": any_spike,
            "acc1_preview_pass": (t <= 0) or
                                 (any_spike >= 0.9 * N_SEEDS and mean > 0),
        }

    # shape: no decrease beyond one SE of the earlier point (P-11)
    shape_ok = True
    decreases = []
    rates = list(VAL_RATES)
    for i in range(len(rates) - 1):
        a_, b_ = per_rate[str(rates[i])], per_rate[str(rates[i + 1])]
        drop = a_["onfly_mean_hz"] - b_["onfly_mean_hz"]
        if drop > a_["onfly_se_hz"]:
            shape_ok = False
            decreases.append([rates[i], rates[i + 1], drop, a_["onfly_se_hz"]])

    def onset(curve):
        for r in rates:
            if curve(r) > ONSET_HZ:
                return r
        return None
    onset_onfly = onset(lambda r: per_rate[str(r)]["onfly_mean_hz"])
    onset_ref = onset(lambda r: ref[str(r)])
    if onset_onfly is None or onset_ref is None:
        onset_ok = onset_onfly == onset_ref
    else:
        onset_ok = abs(rates.index(onset_onfly) - rates.index(onset_ref)) <= 1

    magnitude_ok = all(v["magnitude_pass"] for v in per_rate.values())
    acc4 = shape_ok and onset_ok and magnitude_ok

    ro0 = res0[(0, 1)]["readouts"]
    acc2 = all(x["spikes"] == 0 for x in ro0)

    out = {
        "w_syn": w_syn, "network": {"neurons": n, "edges": e, "sha256": sha,
                                    "crc32": crc},
        "seeds": N_SEEDS, "sim_ms": cal.SIM_MS, "elapsed_s": round(elapsed),
        "per_rate": per_rate,
        "acc4": {"shape_pass": shape_ok, "decreases_beyond_se": decreases,
                 "onset_onfly_hz": onset_onfly, "onset_reference_hz": onset_ref,
                 "onset_pass": onset_ok, "magnitude_pass": magnitude_ok,
                 "pass": acc4, "interpretation": "P-11"},
        "acc2_x86_native": {"readout_spikes_at_rate_0": [x["spikes"]
                                                         for x in ro0],
                            "pass": acc2},
        "acc1_preview_full_brain_x86": all(v["acc1_preview_pass"]
                                           for v in per_rate.values()),
        "platform": "x86 mingw32 gcc 6.3.0, NATIVE backend (D-30), "
                    "full MaleCNS brain; not the MVS subcircuit",
    }
    io.open(OUT, "w", encoding="utf-8", newline="\n").write(
        json.dumps(out, indent=2, sort_keys=True) + "\n")

    print("%6s %10s %8s %8s %10s %8s %6s"
          % ("rate", "onfly", "sd", "se", "reference", "tol", "mag"))
    for r in rates:
        v = per_rate[str(r)]
        print("%6d %10.2f %8.2f %8.2f %10.2f %8.2f %6s"
              % (r, v["onfly_mean_hz"], v["onfly_sd_hz"], v["onfly_se_hz"],
                 v["reference_hz"], v["tolerance_hz"],
                 "PASS" if v["magnitude_pass"] else "FAIL"))
    print("ACC-4 shape %s (onset onfly %s Hz, reference %s Hz: %s); "
          "magnitude %s; ACC-4 %s"
          % ("PASS" if shape_ok else "FAIL", onset_onfly, onset_ref,
             "PASS" if onset_ok else "FAIL",
             "PASS" if magnitude_ok else "FAIL", "PASS" if acc4 else "FAIL"))
    print("ACC-2 x86 NATIVE rate 0: readout spikes %s -> %s"
          % ([x["spikes"] for x in ro0], "PASS" if acc2 else "FAIL"))
    print("ACC-1 preview (full brain, x86, not the subcircuit): %s"
          % ("PASS" if out["acc1_preview_full_brain_x86"] else "FAIL"))
    print("wrote %s (%d s)" % (OUT.replace("\\", "/"), elapsed))
    return 0


if __name__ == "__main__":
    sys.exit(main())
