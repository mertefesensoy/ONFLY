# -*- coding: utf-8 -*-
"""Signed connectivity: neurotransmitter to synaptic sign (FR-PRP-03, SR-MOD-05).

FR-PRP-03 requires the pipeline to aggregate synapses into directed neuron-pair
counts and assign each pair a sign from the presynaptic neuron's predicted
neurotransmitter. SR-MOD-05 fixes the weight as
``synapse count x sign x W_syn``.

The aggregation half is already done upstream: the flat-connectome file is one
row per ordered (pre, post) pair with a summed weight, so this module verifies
that property rather than recomputing it, and then applies the sign.

The mapping is the owner's, decided in D-54 and D-55, closing TBC-04:

    acetylcholine                       +1
    GABA, glutamate, histamine          -1
    dopamine, octopamine, serotonin     excluded (modulatory, not fast synaptic)
    unclear or absent                   excluded

Two of those deserve their reasons stated, because both are places where a
plausible-looking default would be wrong:

**Glutamate is inhibitory here.** In *Drosophila* glutamate acts through GluCl
channels and is inhibitory, unlike the vertebrate default. It covers 29,443
neurons, about 18% of those with a definite prediction, so getting this backwards
would not be a small error -- it would systematically shift the network's whole
excitation/inhibition balance.

**Unknown means excluded, not assumed.** 47,206 neurons (22.3%) have no definite
prediction. Calling them excitatory because acetylcholine is the majority would
apply one guess to a fifth of the network at once. Excluding them keeps guesses
out of the model, at a cost that is real and therefore measured and recorded
rather than hidden.

Contract:
    build_signs()  -> (DataFrame of signed pairs, stats dict)
      The frame has columns body_pre, body_post, weight, sign, signed_weight,
      where signed_weight is ``weight * sign`` -- the synapse count carrying its
      sign, before W_syn is applied. W_syn is a calibrated free parameter
      (SR-CAL) and is deliberately NOT applied here.
    Side effects: none. Reads the retrieved files only.

Run:  python prep/signs.py
"""
import io
import json
import os
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)

import sources  # noqa: E402

DATA_DIR = os.path.join(ROOT, "data", "malecns")
OUT_STATS = os.path.join(ROOT, "docs", "malecns-sign-assignment.json")

#: D-54, closing TBC-04 part 1.  Anything not named here is excluded.
NT_SIGN = {
    "acetylcholine": +1,
    "gaba": -1,
    "glutamate": -1,
    "histamine": -1,
}

#: D-54: named explicitly so exclusion is a decision on the record rather than
#: the silent consequence of a missing dictionary key.
NT_EXCLUDED_MODULATORY = ("dopamine", "octopamine", "serotonin")

#: D-55: no definite prediction.
NT_EXCLUDED_UNKNOWN = ("unclear", "nan", "none", "")


def load_nt_by_body():
    """Return {bodyId: consensus_nt} with one entry per body."""
    path = os.path.join(DATA_DIR, sources.FILES["neurotransmitters"][0])
    n = pd.read_feather(path, columns=["body", "consensus_nt"])
    n["consensus_nt"] = n["consensus_nt"].astype(str).str.lower()
    return n.drop_duplicates("body").set_index("body")["consensus_nt"]


def build_signs(verbose=True):
    wpath = os.path.join(DATA_DIR, sources.FILES["weights"][0])
    w = pd.read_feather(wpath)

    # FR-PRP-03 asks for aggregation into directed pair counts.  Upstream has
    # already done it; verify rather than assume, because a file that turned out
    # to hold one row per synapse would silently produce a network whose weights
    # were all 1.
    n_rows = len(w)
    # `duplicated(...).any()` rather than drop_duplicates: the question is
    # whether a duplicate exists, and building a second 152-million-row frame
    # to answer it is not a reasonable way to find out.
    already_aggregated = not w.duplicated(
        subset=["body_pre", "body_post"]).any()
    n_pairs = n_rows if already_aggregated else -1
    if not already_aggregated:
        w = (w.groupby(["body_pre", "body_post"], observed=True)["weight"]
               .sum().reset_index())
        n_pairs = len(w)

    nt = load_nt_by_body()

    # Map body -> sign directly, never body -> transmitter name.  A string
    # column over 152 million rows would cost gigabytes and is not needed: only
    # the far smaller dropped subset is ever described by transmitter.
    body_sign = nt[nt.isin(NT_SIGN)].map(NT_SIGN).astype("int8")
    w["sign"] = w["body_pre"].map(body_sign)

    keep_mask = w["sign"].notna()
    kept = w[keep_mask].copy()
    kept["sign"] = kept["sign"].astype("int8")
    kept["signed_weight"] = kept["weight"].astype("int64") * kept["sign"]

    dropped = w.loc[~keep_mask, ["body_pre", "body_post", "weight"]].copy()
    drop_by_nt = (dropped["body_pre"].map(nt).fillna("(absent)")
                  .value_counts())

    stats = {
        "decisions": ["D-54", "D-55"],
        "mapping": {k: int(v) for k, v in NT_SIGN.items()},
        "excluded_modulatory": list(NT_EXCLUDED_MODULATORY),
        "input_rows": int(n_rows),
        "distinct_pairs": int(n_pairs),
        "already_aggregated_upstream": bool(already_aggregated),
        "pairs_kept": int(len(kept)),
        "pairs_dropped": int(len(dropped)),
        "percent_pairs_dropped": round(100.0 * len(dropped) / max(1, n_rows), 3),
        "synapses_kept": int(kept["weight"].sum()),
        "synapses_dropped": int(dropped["weight"].sum()),
        "percent_synapses_dropped": round(
            100.0 * dropped["weight"].sum() / max(1, int(w["weight"].sum())), 3),
        "dropped_by_nt": {str(k): int(v) for k, v in drop_by_nt.items()},
        "excitatory_pairs": int((kept["sign"] > 0).sum()),
        "inhibitory_pairs": int((kept["sign"] < 0).sum()),
        "excitatory_synapses": int(kept.loc[kept["sign"] > 0, "weight"].sum()),
        "inhibitory_synapses": int(kept.loc[kept["sign"] < 0, "weight"].sum()),
        "distinct_presynaptic_kept": int(kept["body_pre"].nunique()),
        "distinct_presynaptic_dropped": int(dropped["body_pre"].nunique()),
    }

    if verbose:
        print("input rows                %12d" % stats["input_rows"])
        print("distinct (pre,post) pairs %12d  (already aggregated: %s)"
              % (stats["distinct_pairs"], stats["already_aggregated_upstream"]))
        print("pairs kept                %12d" % stats["pairs_kept"])
        print("pairs dropped             %12d  (%.2f%%)"
              % (stats["pairs_dropped"], stats["percent_pairs_dropped"]))
        print("synapses kept             %12d" % stats["synapses_kept"])
        print("synapses dropped          %12d  (%.2f%%)"
              % (stats["synapses_dropped"], stats["percent_synapses_dropped"]))
        print("  excitatory pairs        %12d  synapses %d"
              % (stats["excitatory_pairs"], stats["excitatory_synapses"]))
        print("  inhibitory pairs        %12d  synapses %d"
              % (stats["inhibitory_pairs"], stats["inhibitory_synapses"]))
        print("dropped sources by predicted transmitter:")
        for k, v in sorted(drop_by_nt.items(), key=lambda kv: -kv[1])[:8]:
            print("    %-14s %10d pairs" % (str(k)[:14], v))

    return kept, stats


def main():
    kept, stats = build_signs()
    io.open(OUT_STATS, "w", encoding="utf-8", newline="\n").write(
        json.dumps(stats, indent=2, sort_keys=True) + "\n")
    print("\nwrote %s" % OUT_STATS.replace("\\", "/"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
