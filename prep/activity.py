# -*- coding: utf-8 -*-
"""Aggregate full-brain runs into an activity ranking (FR-PRP-04, SR-EXT-01).

SR-EXT-01 defines the MVP subcircuit as "the N most active neurons by total
spike count in the full-brain run (calibrated W_syn, all calibration and
validation rates, all seeds), plus every stimulus and readout neuron", with ties
broken by ascending neuron identifier.

This produces exactly that ranking from the runs on disk, and is careful to say
what the ranking is **not**:

  * W_syn is **not calibrated** -- it is still the FlyWire 0.275 mV of
    SR-MOD-02, pending SR-CAL-01.
  * The runs are **one seed**, not the thirty TBD-06 proposes (D-63).
  * Every SR-MOD-02 parameter is still TBC-02.

So the output is a provisional ranking that shows the method works and gives a
first look at the rate-response curve. It is not the SR-EXT-01 selection and the
module refuses to call it one.

It also reports the MN9 rate-response curve, which is the shape ACC-1 and ACC-4
will eventually be judged on -- again, not an evaluation of either.

Run:  python prep/activity.py
"""
import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

RUN_DIR = os.path.join(ROOT, "data", "fullbrain")
OUT_JSON = os.path.join(ROOT, "docs", "malecns-activity-ranking.json")

#: SR-EXT-01's candidate sizes, smallest first.
N_SEQUENCE = (250, 500, 1000, 2000, 4000)


def parse_run(path):
    """Return (meta, {index: (spikes, first_us)}, readouts) from one run file."""
    meta, spikes, readouts = {}, {}, []
    for line in io.open(path, encoding="ascii", errors="replace"):
        parts = line.split()
        if not parts:
            continue
        kind = parts[0]
        f = dict(t.split("=", 1) for t in parts[1:] if "=" in t)
        if kind in ("NET", "RUN"):
            meta.update(f)
        elif kind == "TOP":
            spikes[int(f["n"])] = (int(f["spikes"]), int(f["first"]))
        elif kind == "READOUT":
            readouts.append((int(f["n"]), int(f["spikes"]), int(f["first"])))
    return meta, spikes, readouts


def main():
    if not os.path.isdir(RUN_DIR):
        sys.stderr.write("no run directory: %s\n" % RUN_DIR)
        return 2
    files = sorted(f for f in os.listdir(RUN_DIR) if f.endswith(".txt"))
    if not files:
        sys.stderr.write("no run files in %s; run tools/fullbrain.sh first\n"
                         % RUN_DIR)
        return 2

    totals = {}
    per_rate = {}
    n_neurons = None
    for name in files:
        meta, spikes, readouts = parse_run(os.path.join(RUN_DIR, name))
        if "rate" not in meta:
            print("  skipping %s: no RUN line (still being written?)" % name)
            continue
        rate = int(meta["rate"])
        n_neurons = int(meta.get("n", n_neurons or 0))
        for idx, (s, _first) in spikes.items():
            totals[idx] = totals.get(idx, 0) + s
        per_rate[rate] = {
            "spikes": int(meta.get("spikes", 0)),
            "active": int(meta.get("active", 0)),
            "seconds": float(meta.get("seconds", 0.0)),
            "steps": int(meta.get("steps", 0)),
            "readouts": [{"neuron": n, "spikes": s, "first_us": fu}
                         for n, s, fu in readouts],
        }
        print("  %-24s rate=%-4d spikes=%-8s active=%-7s %ss"
              % (name, rate, meta.get("spikes"), meta.get("active"),
                 meta.get("seconds")))

    if not per_rate:
        sys.stderr.write("no complete runs yet\n")
        return 2

    # SR-EXT-01: most active by total spike count, ties by ascending index.
    ranked = sorted(totals.items(), key=lambda kv: (-kv[1], kv[0]))
    ranked = [(i, s) for i, s in ranked if s > 0]

    print("\nMN9 rate-response (the shape ACC-1 and ACC-4 will judge, "
          "NOT an evaluation of either):")
    print("  %-8s %-14s %-14s %s" % ("rate", "MN9 #1 spikes", "MN9 #2 spikes",
                                     "network spikes"))
    for rate in sorted(per_rate):
        r = per_rate[rate]
        outs = r["readouts"]
        a = outs[0]["spikes"] if len(outs) > 0 else "-"
        b = outs[1]["spikes"] if len(outs) > 1 else "-"
        print("  %-8d %-14s %-14s %d" % (rate, a, b, r["spikes"]))

    print("\nprovisional activity ranking: %d neurons spiked at least once"
          % len(ranked))
    for n in N_SEQUENCE:
        if len(ranked) >= n:
            cut = ranked[n - 1][1]
            print("  top %-5d would require >= %d total spikes" % (n, cut))
        else:
            print("  top %-5d unavailable: only %d neurons spiked" % (n, len(ranked)))

    out = {
        "status": "PROVISIONAL - NOT the SR-EXT-01 selection",
        "why_provisional": [
            "W_syn is the uncalibrated FlyWire value 0.275 mV (SR-CAL-01 "
            "requires recalibration on the full-brain model)",
            "one seed per rate, not the 30 TBD-06 proposes (D-63)",
            "every SR-MOD-02 parameter is still TBC-02",
        ],
        "decisions": ["D-56", "D-59", "D-61", "D-63"],
        "limits": ["VL-12", "VL-13"],
        "neurons_in_network": n_neurons,
        "rates": per_rate,
        "neurons_that_spiked": len(ranked),
        "top_200": [{"neuron": i, "total_spikes": s} for i, s in ranked[:200]],
        "cut_for_n": {str(n): (ranked[n - 1][1] if len(ranked) >= n else None)
                      for n in N_SEQUENCE},
    }
    io.open(OUT_JSON, "w", encoding="utf-8", newline="\n").write(
        json.dumps(out, indent=2, sort_keys=True) + "\n")
    print("\nwrote %s" % OUT_JSON.replace("\\", "/"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
