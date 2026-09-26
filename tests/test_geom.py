# -*- coding: utf-8 -*-
"""The committed geometry sidecar, against the network it describes (D-385).

WHY THIS GUARDS THE ARTEFACT RATHER THAN THE TOOL
--------------------------------------------------
`prep/geom.py` needs the 14.5 MB annotations feather, which is gitignored, so
a test that regenerated the sidecar would skip on most checkouts -- including
the one a viewer is run from.  What has to be true is a property of the
COMMITTED file: that its rows correspond, index by index, to the neurons of
`onfnet-malecns-v1.0-srext.bin`.

That mapping is the whole basis of the live view.  The stream carries neuron
INDICES (IR-STM-02) and the sidecar turns an index into a position; if the
correspondence slipped, the picture would still look like a fly CNS and would
simply light the wrong cells.  Nothing downstream could notice.

So the check is made against witnesses that are independent of the sidecar:

    the network header       which indices are stimulus and readout
    the annotations' types   carried in the sidecar, cross-checked against
                             the committed ONFNAM file, which is what the
                             MVS driver prints (IR-NAM-01)

`python prep/geom.py --check` is the other half, for a checkout that does have
the feather: it rebuilds and compares.  This file does not duplicate it.

Run:  python tests/test_geom.py
Exit status 0 when the sidecar describes the shipped network, 1 otherwise.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "layout"))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import onfres                                      # noqa: E402

import netread                                     # noqa: E402

GEOM = os.path.join(ROOT, "data", "geom", "srext-geom.json")
BACKDROP = os.path.join(ROOT, "data", "geom", "backdrop.csv")
NETDIR = os.path.join(ROOT, "data", "networks")
NETFILE = os.path.join(NETDIR, "onfnet-malecns-v1.0-srext.bin")
NAMES = os.path.join(NETDIR, "onfnam-malecns-v1.0-srext.txt")

ALLOWED = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-.")


def check(label, ok, detail=""):
    print("  %-4s %-54s %s" % ("ok" if ok else "FAIL", label, detail))
    return (1, 0) if ok else (0, 1)


def main():
    ok = bad = 0
    if not os.path.exists(GEOM):
        sys.stderr.write("test_geom: %s is absent; run prep/geom.py\n" % GEOM)
        return 1
    doc = json.loads(open(GEOM, "r").read())
    rows = doc["neurons"]

    a, b = check("indices are 0..n-1 in order",
                 [r["index"] for r in rows] == list(range(len(rows))))
    ok += a
    bad += b
    a, b = check("bodyIds are distinct",
                 len(set(r["bodyId"] for r in rows)) == len(rows))
    ok += a
    bad += b
    a, b = check("the header counts agree with the rows",
                 doc["n"] == len(rows)
                 and doc["measured"] + doc["placed"] == len(rows)
                 and doc["measured"] == sum(1 for r in rows
                                            if not r["placed"]),
                 "n=%d measured=%d placed=%d"
                 % (doc["n"], doc["measured"], doc["placed"]))
    ok += a
    bad += b
    a, b = check("every imputed position records its basis",
                 all(r["placed"] == (r["basis"] != "measured")
                     for r in rows),
                 "an imputed position must never read as measured")
    ok += a
    bad += b

    if not os.path.exists(NETFILE):
        onfres.skip("test_geom/network", "the network comparison: %s is "
                    "absent (run `make fixtures`)"
                    % os.path.basename(NETFILE), indent="  ")
        print("test_geom: %d passed, %d failed" % (ok, bad))
        return 1 if bad else 0

    spec = netread.read(NETFILE)
    a, b = check("the sidecar has one row per network neuron",
                 spec["n"] == len(rows),
                 "network %d, sidecar %d" % (spec["n"], len(rows)))
    ok += a
    bad += b

    stim = sorted(int(i) for i in spec["stim"])
    readout = sorted(int(i) for i in spec["readout"])
    a, b = check("roles match the network header",
                 sorted(r["index"] for r in rows
                        if r["role"] == "stimulus") == stim
                 and sorted(r["index"] for r in rows
                            if r["role"] == "readout") == readout,
                 "stim %s, readout %s" % (stim, readout))
    ok += a
    bad += b

    # The witness that the ORDER is right: the indices the header calls
    # readout must be the MN9 neurons, and the ones it calls stimulus must be
    # the D-52 sugar sensors.  A rotated or shuffled body list fails here.
    a, b = check("D-52 every readout index is an MN9",
                 all((rows[i]["type"] or "").upper().startswith("MN9")
                     for i in readout),
                 ", ".join("%d=%s" % (i, rows[i]["type"]) for i in readout))
    ok += a
    bad += b
    bads = [(i, rows[i]["type"]) for i in stim
            if not ((rows[i]["type"] or "").upper().startswith("PHG9")
                    or "TPGRN" in (rows[i]["type"] or "").upper())]
    a, b = check("D-52 every stimulus index is PhG9 or dorsal_tpGRN",
                 not bads, "offenders: %s" % (bads or "none"))
    ok += a
    bad += b

    if os.path.exists(NAMES):
        wrong = []
        seen = 0
        for line in open(NAMES, "r"):
            if not line.strip():
                continue
            index = int(line[:5])
            name = line[6:40].strip()
            want = "%s-%d" % ((rows[index]["type"] or "?"),
                              rows[index]["bodyId"])
            clean = "".join(c if c in ALLOWED else "_"
                            for c in want.upper())
            if name != clean:
                wrong.append((index, name, clean))
            seen += 1
        # ONFNAM names only the neurons the FR-BAT-04 report prints -- the
        # stimulus and readout sets, 16 rows for srext -- not all 501, so
        # what is required is that every row it does carry agrees.
        a, b = check("IR-NAM-01 ONFNAM and the sidecar name the same neurons",
                     not wrong and seen > 0,
                     "%d rows compared; %s" % (seen, wrong[:2] or "all agree"))
        ok += a
        bad += b

    # The projection the viewer uses, as measured rather than assumed.
    p = doc["projection"]
    a, b = check("the projection axes are distinct and recorded",
                 len({p["body_axis"], p["side_axis"], p["depth_axis"]}) == 3,
                 "body %s, side %s, depth %s, brain at %s end"
                 % (p["body_axis"], p["side_axis"], p["depth_axis"],
                    "low" if p["brain_at_low_end"] else "high"))
    ok += a
    bad += b
    a, b = check("the body axis separates brain from VNC by the most",
                 all(p["axes"][p["body_axis"]]["brain_vnc_separation"]
                     >= p["axes"][x]["brain_vnc_separation"]
                     for x in ("x", "y", "z")),
                 "%.0f" % p["axes"][p["body_axis"]]["brain_vnc_separation"])
    ok += a
    bad += b

    if os.path.exists(BACKDROP):
        n = 0
        outside = 0
        lo = [min(r[k] for r in rows) for k in ("x", "y", "z")]
        hi = [max(r[k] for r in rows) for k in ("x", "y", "z")]
        for line in open(BACKDROP, "r"):
            if line.startswith("#") or line.startswith("bodyId"):
                continue
            parts = line.split(",")
            if len(parts) != 4:
                outside += 1
                continue
            n += 1
        a, b = check("the backdrop parses as bodyId,x,y,z",
                     n > 0 and outside == 0,
                     "%d points, network spans %s..%s" % (n, lo, hi))
        ok += a
        bad += b

    print("test_geom: %d passed, %d failed" % (ok, bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
