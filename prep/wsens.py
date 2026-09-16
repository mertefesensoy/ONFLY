# -*- coding: utf-8 -*-
"""W_syn sensitivity probe for a stimulus-set variant (D-302, D-306).

What question this answers
--------------------------
VL-65 measured D-176's stimulus-set variants at the *shipped* W_syn and
recorded, explicitly as not proven, that "a W_syn recalibrated for the
taste-peg-only or the unilateral set would pass ACC-4 in full (no
recalibration was run)".

A full recalibration plus an ACC-4 evaluation is about five hours. This
probe answers the same question for about a tenth of that, by measuring
the thing the answer actually turns on: **how fast does the MN9 rate at
each validation rate move when W_syn moves?**

Why that is sufficient
----------------------
At the shipped W_syn the tpgrn variant is 7.78 Hz at 40 Hz and must
reach 6.73 to pass -- a 13.5% fall. At the same time 60 Hz sits 2.0%
above its ACC-4 floor and 120 Hz 1.6% above its own. So ACC-4 can pass
only if the 40 Hz response is roughly seven to eight times more
sensitive to W_syn than the 60 and 120 Hz responses are. That is a
statement about d(rate)/d(W_syn), and it is measurable directly.

What this is NOT
----------------
* It is **not** a calibration. It does not search, it does not optimise,
  and it produces no recommended W_syn. It samples a few points.
* It is **not** ACC-4. ACC-4 is 30 seeds (D-135) over five validation
  rates; this runs a handful of seeds over three. Its per-rate means
  therefore carry real sampling noise -- at 40 Hz VL-64 measured a
  standard deviation of 8.45 Hz across seeds -- and a difference between
  two W_syn points smaller than that noise means nothing. The output
  prints the standard error so the reader can see which differences are
  real.
* It **cannot change anything that ships.** It writes one file of its
  own, `data/calibration/wsens-<variant>.json`. It never opens a search
  log, never writes an `acc4*.json`, and the networks it emits carry the
  variant in their names and are deleted after use.

Usage
-----
    python prep/wsens.py --variant tpgrn \\
        --w-syn 0.26,0.28,0.2969,0.32 --rates 40,60,120 \\
        --seeds 4 --jobs 10
"""
import argparse
import io
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import calibrate as cal                                       # noqa: E402
import acc4                                                   # noqa: E402


def mean_hz(res):
    """MN9 rate in Hz, averaged over the readout neurons.

    Same reduction acc4.py uses: spikes over the simulated window,
    converted with cal.SIM_MS, then averaged across the two readouts.
    """
    sp = [x["spikes"] for x in res["readouts"]]
    return sum(sp) * 1000.0 / cal.SIM_MS / len(sp)


def stdev(xs):
    if len(xs) < 2:
        return 0.0
    m = sum(xs) / len(xs)
    return (sum((x - m) ** 2 for x in xs) / (len(xs) - 1)) ** 0.5


def main():
    ap = argparse.ArgumentParser()
    # Omitting --variant probes the SHIPPED stimulus set: D-52's fourteen
    # neurons on both hemispheres, as D-73 fixed it and D-177 kept it.
    # That is the configuration ACC-4 is actually evaluated on, so it is
    # the one whose W_syn sensitivity bears on Phase E rather than on a
    # road not taken.  It is labelled `d52` in outputs so that a run on
    # the shipped set is never mistaken for a variant run, and so that
    # its candidate networks cannot collide with a baseline calibration's
    # `net-<w>.bin`.
    ap.add_argument("--variant", default=None,
                    help="right, phg9 or tpgrn (D-176); omit for the "
                         "shipped D-52 set")
    ap.add_argument("--w-syn", required=True,
                    help="comma-separated W_syn values in mV")
    ap.add_argument("--rates", default="40,60,120",
                    help="comma-separated validation rates in Hz")
    ap.add_argument("--seeds", type=int, default=4)
    ap.add_argument("--jobs", type=int, default=8)
    a = ap.parse_args()

    ws = [float(x) for x in a.w_syn.split(",")]
    rates = [int(x) for x in a.rates.split(",")]
    seeds = list(range(1, a.seeds + 1))

    if not os.path.isfile(cal.RUNNET):
        raise SystemExit("build the runner first: mingw32-make runner")
    ref = cal.load_reference()
    if ref is None:
        raise SystemExit("no reference: run reference/shiu/rerun.py")

    arrays, stim, read = cal.load_cache()
    stim, desc = cal.select_stim(stim, a.variant)
    label = a.variant or "d52"
    if desc is None:
        desc = {"variant": "d52 (shipped set, D-52 + D-73)",
                "neurons": len(stim),
                "bodies": [int(b) for b in stim]}
        print("shipped stimulus set: %d neurons, both hemispheres "
              "(D-52, D-73, kept by D-177)" % len(stim))
    else:
        print("variant %s: %d stimulus neurons %s sides %s"
              % (a.variant, len(stim), desc["types"], desc["sides"]))
    print("  investigation only (D-302, D-306): no emitted network, no "
          "golden fingerprint and no shipped W_syn is affected")
    print("  %d W_syn x %d rates x %d seeds = %d full-brain runs"
          % (len(ws), len(rates), len(seeds), len(ws) * len(rates) * len(seeds)))

    # The variant is set on the module so emit_candidate() names the
    # candidate networks for it and cannot collide with a baseline run.
    cal.VARIANT = label

    out = {"variant": desc, "rates": rates, "seeds": seeds,
           "sim_ms": cal.SIM_MS, "reference_hz": {}, "points": []}
    # cal.load_reference() keys by the rate's STRING form.
    for r in rates:
        out["reference_hz"][str(r)] = ref.get(str(r))

    t_all = time.time()
    for w in ws:
        t0 = time.time()
        path, n, e, sha, crc = cal.emit_candidate(w, arrays, stim, read)
        # acc4.run_many() is reused rather than reimplemented: it already
        # raises on a non-zero rc or a readout count other than two, which
        # is the check that stops a silently broken run from becoming a
        # data point.  Its result is keyed (rate, seed).
        results = acc4.run_many(path, a.jobs, rates, seeds)

        entry = {"w_syn": float(w), "w_syn_hex": float.hex(float(w)),
                 "network": {"neurons": int(n), "edges": int(e),
                             "sha256": sha, "crc32": crc},
                 "per_rate": {}}
        for r in rates:
            vals = [mean_hz(results[(r, sd)]) for sd in seeds]
            m = sum(vals) / len(vals)
            sd_ = stdev(vals)
            entry["per_rate"][str(r)] = {
                "mean_hz": m, "sd_hz": sd_,
                "se_hz": sd_ / (len(vals) ** 0.5) if vals else 0.0,
                "per_seed_hz": vals}
        entry["elapsed_s"] = round(time.time() - t0, 1)
        out["points"].append(entry)
        os.remove(path)
        print("  W_syn %.4f : %s   (%.0f s)"
              % (w, "  ".join("%d Hz %.2f+-%.2f"
                              % (r, entry["per_rate"][str(r)]["mean_hz"],
                                 entry["per_rate"][str(r)]["se_hz"])
                              for r in rates), entry["elapsed_s"]))

    out["elapsed_s"] = round(time.time() - t_all, 1)
    # The SEED COUNT is part of the name, not just of the content.
    #
    # A probe's whole value is its error bars, so a 4-seed run and a
    # 30-seed run of the same variant are different evidence and must be
    # different files.  Writing both to `wsens-<variant>.json` would let
    # the second silently replace the first, leaving a verification-limit
    # entry citing a file that no longer holds the numbers it quotes --
    # the D-209 failure mode, and the one tests/test_varnt.py pins for
    # calibrate.py.  Caught here 2026-09-15 by stopping a 30-seed run a
    # minute after it started, having missed it when the tool was written.
    dst = os.path.join(cal.CAL_DIR,
                       "wsens-%s-s%d.json" % (label, len(seeds)))
    io.open(dst, "w", encoding="utf-8").write(
        json.dumps(out, indent=2, sort_keys=True))

    # --- the table the decision is read off ------------------------------
    print()
    print("%8s %s" % ("W_syn", "".join("%14s" % ("%d Hz" % r)
                                       for r in rates)))
    for entry in out["points"]:
        print("%8.4f %s"
              % (entry["w_syn"],
                 "".join("%14s" % ("%.2f+-%.2f"
                                   % (entry["per_rate"][str(r)]["mean_hz"],
                                      entry["per_rate"][str(r)]["se_hz"]))
                         for r in rates)))
    print()
    print("relative change per rate, against the highest W_syn probed:")
    base = max(out["points"], key=lambda p: p["w_syn"])
    for entry in out["points"]:
        if entry["w_syn"] == base["w_syn"]:
            continue
        parts = []
        for r in rates:
            b = base["per_rate"][str(r)]["mean_hz"]
            m = entry["per_rate"][str(r)]["mean_hz"]
            parts.append("%d Hz %+.1f%%"
                         % (r, 100.0 * (m - b) / b if b else 0.0))
        print("  W_syn %.4f (%+.1f%%): %s"
              % (entry["w_syn"],
                 100.0 * (entry["w_syn"] - base["w_syn"]) / base["w_syn"],
                 "   ".join(parts)))
    print()
    print("wrote %s (%.0f s)" % (dst.replace("\\", "/"), out["elapsed_s"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
