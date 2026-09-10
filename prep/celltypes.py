# -*- coding: utf-8 -*-
"""Derive the sugar-GRN and MN9 cell-type mapping (FR-PRP-02, TBC-03, D-51).

FR-PRP-02 requires the stimulus set (sugar-sensing gustatory receptor neurons)
and the readout set (MN9) to be identified by cell type, written to a reviewed
table, and **approved by the owner before calibration**. This module produces
that table; it does not decide it.

Why the sugar set has to be derived rather than looked up. MaleCNS annotates no
GRN as sugar-sensing. All sixteen labellar-bristle gustatory types (LB1a…LB4b)
are predicted cholinergic, so neurotransmitter cannot separate sugar from
bitter. The only sugar-labelled neurons in the dataset are three *downstream*
types carrying the synonym "Yao & Scott 2022: Sugar SEL LN/PN" — GNG056,
GNG540 and GNG550.

So the evidence available is connectivity: a gustatory type that drives the
identified sugar-pathway neurons is a sugar GRN candidate, and one that does not
is not. This ranks every gustatory type by that drive and leaves the cut to the
owner.

A finding worth carrying: the drive comes overwhelmingly from *pharyngeal* and
*taste-peg* types, not from the labellar-bristle types this module originally
assumed. Whether that reflects real biology in the male CNS, or means the marker
neurons anchor a different sub-pathway than Shiu et al. stimulate, is a question
for the owner and for TBC-05.

What this deliberately does NOT do: pick a threshold, or assert from outside
knowledge which types are the sugar ones. Both would be exactly the guess TBC-03
exists to prevent, and SR-CAL-05's warning that tolerances must not be widened
after the fact applies just as much to set membership.

Run:  python prep/celltypes.py
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
OUT_JSON = os.path.join(ROOT, "docs", "malecns-celltype-mapping.json")
OUT_MD = os.path.join(ROOT, "docs", "malecns-celltype-mapping.md")

#: The readout set. Unambiguous: MaleCNS types exactly two neurons as MN9,
#: subclass "pm" (proboscis motor), superclass "cb_motor".
READOUT_TYPE = "MN9"

#: Downstream sugar-pathway neurons, identified by their published synonym.
#: These are the evidence anchor, not the stimulus set.
SUGAR_MARKER = "Sugar"

#: Candidate stimulus pool: EVERY gustatory receptor neuron.
#:
#: An earlier version of this module restricted candidates to labellar-bristle
#: GRNs, assuming the sugar pathway is labellar as in the FlyWire work. The data
#: contradicted that: input to the sugar-pathway marker neurons is dominated by
#: pharyngeal (PhG) and taste-peg types, while labellar types contribute
#: single-digit synapse counts. The pool is therefore the whole gustatory class,
#: and the ranking is left to say which types actually matter.
GRN_CLASS = "gustatory"
GRN_SUBCLASS = None      # None means "do not restrict by subclass"


def load_annotations():
    path = os.path.join(DATA_DIR, sources.FILES["annotations"][0])
    a = pd.read_feather(path)
    for c in ("type", "class", "subclass", "superclass", "synonyms",
              "flywireType", "somaSide"):
        if c in a.columns:
            a[c] = a[c].astype(str).replace("nan", "")
    return a


def load_weights():
    """Load the pairwise synapse counts, normalising the column names.

    The flat-connectome file names its columns for the release rather than for
    us, so the pre/post/weight columns are detected rather than assumed; a
    rename upstream should fail loudly here instead of silently selecting the
    wrong column.
    """
    path = os.path.join(DATA_DIR, sources.FILES["weights"][0])
    w = pd.read_feather(path)
    cols = {c.lower(): c for c in w.columns}

    def pick(*names):
        for n in names:
            if n in cols:
                return cols[n]
        raise KeyError("none of %s in connectome-weights columns %s"
                       % (list(names), list(w.columns)))

    pre = pick("bodyid_pre", "body_pre", "pre", "bodyidpre", "pre_id")
    post = pick("bodyid_post", "body_post", "post", "bodyidpost", "post_id")
    wt = pick("weight", "count", "syn_count", "synapses", "n")
    return w, pre, post, wt


def main():
    a = load_annotations()

    readout = a[a["type"] == READOUT_TYPE]
    sugar_marker = a[a["synonyms"].str.contains(SUGAR_MARKER, case=False,
                                                na=False)]
    grns = a[a["class"] == GRN_CLASS]
    if GRN_SUBCLASS is not None:
        grns = grns[grns["subclass"] == GRN_SUBCLASS]
    grns = grns[grns["type"] != ""]

    print("readout  %-6s %d neurons" % (READOUT_TYPE, len(readout)))
    print("sugar-pathway marker neurons: %d (types %s)"
          % (len(sugar_marker), ", ".join(sorted(set(sugar_marker["type"])))))
    print("candidate GRNs (class=%s%s): %d neurons in %d types"
          % (GRN_CLASS,
             "" if GRN_SUBCLASS is None else ", subclass=%s" % GRN_SUBCLASS,
             len(grns), grns["type"].nunique()))

    w, pre, post, wt = load_weights()
    print("connectome-weights: %d rows, columns pre=%s post=%s weight=%s"
          % (len(w), pre, post, wt))

    marker_ids = set(sugar_marker["bodyId"].tolist())
    grn_ids = dict(zip(grns["bodyId"], grns["type"]))

    # The connectome has ~152 million rows, so every step below is vectorised;
    # a per-row Python loop over it would take hours and is not an option.
    grn_series = pd.Series(grn_ids, name="grntype")
    from_grn = w[w[pre].isin(grn_series.index)].copy()
    from_grn["grntype"] = from_grn[pre].map(grn_series)

    # Direct drive from each candidate GRN type onto the sugar-pathway neurons.
    onto_sugar = from_grn[from_grn[post].isin(marker_ids)]
    agg = onto_sugar.groupby("grntype", observed=True).agg(
        synapses=(wt, "sum"), edges=(wt, "size"),
        neurons=(pre, "nunique"))
    by_type = {t: {"synapses": int(r["synapses"]),
                   "edges": int(r["edges"]),
                   "neurons": set(range(int(r["neurons"])))}
               for t, r in agg.iterrows()}

    # Total outgoing synapses per type, so drive can be read as a share rather
    # than an absolute that merely reflects how big or how busy a type is.
    out_tot = from_grn.groupby("grntype", observed=True)[wt].sum()

    rows = []
    for t in sorted(set(grns["type"])):
        e = by_type.get(t, {"synapses": 0, "edges": 0, "neurons": set()})
        n_type = int((grns["type"] == t).sum())
        total_out = int(out_tot.get(t, 0))
        share = (100.0 * e["synapses"] / total_out) if total_out else 0.0
        rows.append({
            "type": t,
            "neurons": n_type,
            "flywireType": grns[grns["type"] == t].iloc[0]["flywireType"],
            "subclass": grns[grns["type"] == t].iloc[0]["subclass"],
            "synapses_onto_sugar_pathway": e["synapses"],
            "contributing_neurons": len(e["neurons"]),
            "total_outgoing_synapses": total_out,
            "percent_of_output": round(share, 3),
        })
    rows.sort(key=lambda r: (-r["synapses_onto_sugar_pathway"], r["type"]))

    print("\n%-14s %5s %8s %9s %8s  %s"
          % ("type", "n", "syn->SEL", "cells", "%out", "subclass"))
    shown = [r for r in rows if r["synapses_onto_sugar_pathway"] > 0]
    for r in shown:
        print("%-14s %5d %8d %9d %7.2f%%  %s"
              % (r["type"], r["neurons"], r["synapses_onto_sugar_pathway"],
                 r["contributing_neurons"], r["percent_of_output"],
                 r["subclass"]))
    print("(%d further candidate types contribute zero synapses; they are in "
          "the JSON but omitted here)" % (len(rows) - len(shown)))

    mapping = {
        "dataset": sources.DATASET,
        "dataset_uuid": sources.DATASET_UUID,
        "status": "AWAITING OWNER APPROVAL (FR-PRP-02, TBC-03)",
        "readout": {
            "type": READOUT_TYPE,
            "neurons": int(len(readout)),
            "bodyIds": sorted(int(b) for b in readout["bodyId"]),
        },
        "sugar_pathway_marker": {
            "types": sorted(set(sugar_marker["type"])),
            "note": "Yao & Scott 2022 Sugar SEL neurons; evidence anchor, "
                    "not the stimulus set",
            "bodyIds": sorted(int(b) for b in sugar_marker["bodyId"]),
        },
        "candidates_ranked": rows,
        # Stays null until the owner approves a set.  Writing a provisional
        # value here would be the guess FR-PRP-02 and TBC-03 exist to prevent,
        # and a downstream stage could pick it up without anyone noticing.
        "stimulus_set": None,
    }
    io.open(OUT_JSON, "w", encoding="utf-8", newline="\n").write(
        json.dumps(mapping, indent=2, sort_keys=True) + "\n")
    print("\nwrote %s" % OUT_JSON.replace("\\", "/"))
    print("stimulus_set is null: it stays null until the owner approves "
          "a set (FR-PRP-02).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
