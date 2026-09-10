# -*- coding: utf-8 -*-
"""Signed connectivity: neurotransmitter to synaptic sign (FR-PRP-03, SR-MOD-05).

FR-PRP-03 requires the pipeline to aggregate synapses into directed neuron-pair
counts and assign each pair a sign from the presynaptic neuron's predicted
neurotransmitter. SR-MOD-05 fixes the weight as
``synapse count x sign x W_syn``.

The aggregation half is already done upstream: the flat-connectome file holds
one row per ordered (pre, post) pair with a summed weight. That property is
verified rather than assumed, because a file that turned out to hold one row per
*synapse* would silently produce a network whose weights were all 1.

Three owner decisions shape what survives, and they are applied in this order:

**D-56 -- scope.** Only annotated-neuron to annotated-neuron edges. A LIF node
needs a cell type and a transmitter to be simulated at all, and a body absent
from the annotation file has neither. This is where the volume goes: it keeps
40.2% of the connectome's synapses, and the discarded 59.8% is recorded here
and carried into ACC-3 as VL-13.

**D-54 -- sign.** acetylcholine +1; GABA, glutamate and histamine -1; dopamine,
octopamine and serotonin excluded as modulatory rather than fast synaptic.
Glutamate is inhibitory *in Drosophila*, through GluCl channels, unlike the
vertebrate default. It covers about 18% of neurons with a definite prediction,
so getting it backwards would shift the network's whole excitation/inhibition
balance rather than perturb it.

**D-55 -- unknown means excluded.** Neurons with no definite prediction have
their outgoing edges dropped. Calling them excitatory because acetylcholine is
the majority would apply one guess to a fifth of the network at once. Measured
after D-56 this costs only a further 1.2 points, 40.2% to 39.0%.

Implementation note. Everything below works on numpy arrays rather than pandas
frames. An earlier version built a body-to-transmitter *string* column over 152
million rows and died with "Unable to allocate 1.00 GiB ... dtype object"; the
transmitter name is needed only to describe the far smaller dropped subset, so
bodies are mapped straight to an int8 sign.

Contract:
    build_signs() -> (dict of numpy arrays, stats dict)
      Arrays body_pre, body_post, weight, sign, signed_weight, where
      signed_weight is ``weight * sign`` -- the synapse count carrying its sign,
      before W_syn is applied. W_syn is a calibrated free parameter (SR-CAL) and
      is deliberately NOT applied here.
    Side effects: none. Reads the retrieved files only.

Run:  python prep/signs.py
"""
import io
import json
import os
import sys

import numpy as np
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
    """Return a Series {bodyId: consensus_nt}, one entry per body."""
    path = os.path.join(DATA_DIR, sources.FILES["neurotransmitters"][0])
    n = pd.read_feather(path, columns=["body", "consensus_nt"])
    n["consensus_nt"] = n["consensus_nt"].astype(str).str.lower()
    return n.drop_duplicates("body").set_index("body")["consensus_nt"]


def load_neuron_ids():
    """Body ids of annotated neurons, sorted (D-56)."""
    path = os.path.join(DATA_DIR, sources.FILES["annotations"][0])
    a = pd.read_feather(path, columns=["bodyId"])
    return np.sort(a["bodyId"].to_numpy())


def build_signs(verbose=True):
    wpath = os.path.join(DATA_DIR, sources.FILES["weights"][0])
    w = pd.read_feather(wpath, columns=["body_pre", "body_post", "weight"])
    pre = w["body_pre"].to_numpy()
    post = w["body_post"].to_numpy()
    wt = w["weight"].to_numpy()
    del w
    n_rows = len(pre)
    total_syn = int(wt.sum())

    # --- D-56: neuron to neuron only ------------------------------------
    neurons = load_neuron_ids()
    keep = np.isin(pre, neurons) & np.isin(post, neurons)
    scoped_rows = int(keep.sum())
    scoped_syn = int(wt[keep].sum())

    pre, post, wt = pre[keep], post[keep], wt[keep]
    del keep

    # --- aggregation check, now on the far smaller scoped set -----------
    pair = np.stack([pre, post], axis=1)
    n_pairs = len(np.unique(pair, axis=0))
    already_aggregated = (n_pairs == len(pre))
    del pair
    if not already_aggregated:
        raise SystemExit(
            "connectome-weights holds %d rows for %d distinct (pre,post) pairs; "
            "FR-PRP-03 expects one aggregated row per pair. Aggregate before "
            "assigning signs." % (len(pre), n_pairs))

    # --- D-54 and D-55: sign from the presynaptic transmitter -----------
    nt = load_nt_by_body()
    signed_nt = nt[nt.isin(NT_SIGN)]
    body_to_sign = signed_nt.map(NT_SIGN).astype("int8")
    sign_series = pd.Series(pre).map(body_to_sign)
    has_sign = sign_series.notna().to_numpy()

    dropped_pre = pre[~has_sign]
    dropped_wt = wt[~has_sign]
    drop_by_nt = (pd.Series(dropped_pre).map(nt).fillna("(absent)")
                  .value_counts())

    sign = sign_series[has_sign].to_numpy().astype(np.int8)
    pre, post, wt = pre[has_sign], post[has_sign], wt[has_sign]
    signed_weight = wt.astype(np.int64) * sign

    exc = sign > 0
    stats = {
        "decisions": ["D-54", "D-55", "D-56"],
        "mapping": {k: int(v) for k, v in NT_SIGN.items()},
        "excluded_modulatory": list(NT_EXCLUDED_MODULATORY),
        "connectome_rows": n_rows,
        "connectome_synapses": total_syn,
        "scope_neuron_to_neuron": {
            "rows": scoped_rows,
            "synapses": scoped_syn,
            "percent_of_synapses": round(100.0 * scoped_syn / total_syn, 3),
            "synapses_discarded": total_syn - scoped_syn,
            "percent_discarded": round(
                100.0 * (total_syn - scoped_syn) / total_syn, 3),
            "limit": "VL-13",
        },
        "already_aggregated_upstream": bool(already_aggregated),
        "pairs_kept": int(len(pre)),
        "pairs_dropped_no_sign": int(len(dropped_pre)),
        "synapses_kept": int(wt.sum()),
        "synapses_dropped_no_sign": int(dropped_wt.sum()),
        "percent_of_connectome_synapses_kept": round(
            100.0 * int(wt.sum()) / total_syn, 3),
        "dropped_by_nt": {str(k): int(v) for k, v in drop_by_nt.items()},
        "excitatory_pairs": int(exc.sum()),
        "inhibitory_pairs": int((~exc).sum()),
        "excitatory_synapses": int(wt[exc].sum()),
        "inhibitory_synapses": int(wt[~exc].sum()),
        "distinct_presynaptic_kept": int(len(np.unique(pre))),
        "distinct_postsynaptic_kept": int(len(np.unique(post))),
    }

    if verbose:
        sc = stats["scope_neuron_to_neuron"]
        print("connectome                %12d rows  %12d synapses"
              % (n_rows, total_syn))
        print("D-56 neuron->neuron       %12d rows  %12d synapses (%.1f%%)"
              % (sc["rows"], sc["synapses"], sc["percent_of_synapses"]))
        print("   discarded (VL-13)      %12s       %12d synapses (%.1f%%)"
              % ("", sc["synapses_discarded"], sc["percent_discarded"]))
        print("aggregated upstream: %s (%d distinct pairs)"
              % (already_aggregated, n_pairs))
        print("D-54/55 signed            %12d rows  %12d synapses (%.1f%% of "
              "connectome)" % (stats["pairs_kept"], stats["synapses_kept"],
                               stats["percent_of_connectome_synapses_kept"]))
        print("   dropped, no sign       %12d rows  %12d synapses"
              % (stats["pairs_dropped_no_sign"],
                 stats["synapses_dropped_no_sign"]))
        print("   excitatory             %12d rows  %12d synapses"
              % (stats["excitatory_pairs"], stats["excitatory_synapses"]))
        print("   inhibitory             %12d rows  %12d synapses"
              % (stats["inhibitory_pairs"], stats["inhibitory_synapses"]))
        print("distinct neurons: %d presynaptic, %d postsynaptic"
              % (stats["distinct_presynaptic_kept"],
                 stats["distinct_postsynaptic_kept"]))
        print("dropped sources by predicted transmitter:")
        for k, v in sorted(drop_by_nt.items(), key=lambda kv: -kv[1])[:6]:
            print("    %-14s %10d pairs" % (str(k)[:14], v))

    return ({"body_pre": pre, "body_post": post, "weight": wt,
             "sign": sign, "signed_weight": signed_weight}, stats)


def main():
    _arrays, stats = build_signs()
    io.open(OUT_STATS, "w", encoding="utf-8", newline="\n").write(
        json.dumps(stats, indent=2, sort_keys=True) + "\n")
    print("\nwrote %s" % OUT_STATS.replace("\\", "/"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
