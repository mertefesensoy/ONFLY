# -*- coding: utf-8 -*-
"""Soma geometry for the Phase G live view (D-346, P-21 Stage 3).

WHAT THIS PRODUCES
------------------
Two files, both committed, so that the viewer runs from a clean checkout
without the 14.5 MB annotations feather:

  data/geom/srext-geom.json     one row per network neuron, in NETWORK INDEX
                                order -- the order the stream's neuron
                                numbers are in, so the viewer needs no second
                                mapping
  data/geom/backdrop.csv        soma positions for the whole annotated CNS,
                                downsampled, as the faint point cloud D-346
                                asks the network to be drawn inside

WHERE THE COORDINATES COME FROM
-------------------------------
`somaLocation` in the MaleCNS v1.0 annotations (D-49, D-50).  They are SOMA
positions -- cell bodies -- not neurites, so the drawing is where the cells
sit, not what they look like.  That is a real limit and the viewer must not
imply otherwise.

The 13.1 GB syn-points file would give neurite positions and is deliberately
not retrieved (`data/malecns/MANIFEST.json`, `not_retrieved`).  Nothing here
needs it.

MEASURED, NOT ASSUMED: WHICH AXIS IS WHICH
------------------------------------------
`somaLocation` is a bare triple.  Nothing in the dataset says which entry is
left-right and which runs down the body, and guessing would produce a picture
that is wrong in a way no test would catch -- it would simply look like a
different fly.

So the axes are measured from labels that are independent of the coordinates,
and the measurement is written into the output for a reader to disagree with:

  * the brain-to-nerve-cord axis is the one whose mean differs most between
    somata labelled with a VNC neuromere (T1..T3, A1..A9) and those labelled
    with a brain neuromere (CG, LB, TC, DC, MX, MD, GNG, ...)
  * the left-right axis is the one whose mean differs most between somata
    labelled somaSide L and those labelled R

On MaleCNS v1.0 this session those came out z (brain-VNC, separation 73,713,
brain at LOW z) and x (left-right, separation 47,712), leaving y as depth.
The code does not hard-code that: it measures, and reports what it measured.

NEURONS WITHOUT A SOMA POSITION
-------------------------------
19 of the 501 `srext` bodies carry no `somaLocation`, and 14 of those are the
ENTIRE stimulus set.  That is biology, not a gap in the data: the sugar-
sensing GRNs of D-52 -- PhG9 and dorsal_tpGRN -- have peripheral cell bodies
in the proboscis, outside the imaged CNS volume, so there is no soma position
to find.

Three fallbacks, in order (D-384):

  1. a neuron with postsynaptic targets in this network sits at the centroid
     of those targets' measured positions.  For the GRNs this puts them in the
     SEZ beside MN9, which is where their axon terminals are -- the part of
     them that IS in the volume
  2. otherwise, the centroid of its `type` group
  3. otherwise, the centroid of the whole subcircuit

Every one of them is flagged `placed: true` and carries the `basis` that was
used.  They are never silently given an invented position, because a viewer
that cannot tell a measured position from an imputed one is a viewer that
lies about the data.

DETERMINISM
-----------
The backdrop is downsampled by a fixed stride over bodyId-sorted order, never
by a random sample, so two runs produce byte-identical files -- the property
FR-PRP-09 requires of the prep pipeline.

Run:
    python prep/geom.py                  write both files for srext
    python prep/geom.py --check          verify what is on disk, write nothing
    python prep/geom.py --backdrop N     downsample the backdrop to about N
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "layout"))

NETDIR = os.path.join(ROOT, "data", "networks")
GEOMDIR = os.path.join(ROOT, "data", "geom")
SUBCIRCUIT = os.path.join(NETDIR, "SUBCIRCUIT.json")
ANNOT = os.path.join(ROOT, "data", "malecns",
                     "body-annotations-male-cns-v1.0-minconf-0.5.feather")

#: The subcircuit SR-EXT-03 selected and D-205 admitted as the MVP network.
SUBKEY = "500"
NETFILE = "onfnet-malecns-v1.0-srext.bin"

#: Ventral nerve cord neuromeres, and brain ones.  Used ONLY to measure which
#: coordinate axis runs down the body; no coordinate is derived from them.
VNC = set(["T1", "T2", "T3"] + ["A%d" % i for i in range(1, 10)])
BRAIN = set(["CG", "LB", "TC", "DC", "MX", "MD", "GNG", "AMMC", "SAD",
             "PRW", "FLA", "CAN"])

#: Default backdrop size.  141,781 annotated somata exist; a stride is taken
#: over them so the cloud reads as anatomy rather than as a scatter of dots,
#: while the committed file stays small.
BACKDROP_N = 20000

AXES = ("x", "y", "z")


class GeomError(Exception):
    pass


def load_annotations():
    try:
        import pandas as pd
    except ImportError:
        raise GeomError("pandas is needed to read the annotations feather")
    if not os.path.exists(ANNOT):
        raise GeomError("annotations feather not found at %s\n"
                        "run: python tools/fixtures.py --malecns annotations"
                        % ANNOT)
    return pd.read_feather(ANNOT, columns=["bodyId", "type", "class",
                                           "somaSide", "somaNeuromere",
                                           "somaLocation"])


def coords(frame):
    """Split somaLocation into three integer columns, dropping rows without.

    The triples arrive as numpy arrays inside an object column, so they are
    unpacked explicitly rather than by a vectorised cast that would silently
    accept a row of the wrong length."""
    out = []
    for body, loc in zip(frame["bodyId"], frame["somaLocation"]):
        if loc is None:
            continue
        try:
            if len(loc) != 3:
                continue
        except TypeError:
            continue
        out.append((int(body), int(loc[0]), int(loc[1]), int(loc[2])))
    return out


def measure_axes(frame):
    """Which coordinate is left-right, and which runs brain to nerve cord.

    Returns a dict recording the separations, so the choice can be audited
    rather than taken on trust."""
    rows = []
    for body, loc, nm, side in zip(frame["bodyId"], frame["somaLocation"],
                                   frame["somaNeuromere"],
                                   frame["somaSide"]):
        if loc is None:
            continue
        try:
            if len(loc) != 3:
                continue
        except TypeError:
            continue
        rows.append((int(loc[0]), int(loc[1]), int(loc[2]), nm, side))

    def mean(sel, axis):
        vals = [r[axis] for r in rows if sel(r)]
        return (sum(vals) / float(len(vals))) if vals else None

    report = {"axes": {}, "n_with_soma": len(rows)}
    body_sep, side_sep = {}, {}
    for i, name in enumerate(AXES):
        b = mean(lambda r: r[3] in BRAIN, i)
        v = mean(lambda r: r[3] in VNC, i)
        left = mean(lambda r: r[4] == "L", i)
        right = mean(lambda r: r[4] == "R", i)
        body_sep[name] = abs(b - v) if (b is not None and v is not None) else 0
        side_sep[name] = abs(left - right) \
            if (left is not None and right is not None) else 0
        report["axes"][name] = {
            "brain_mean": b, "vnc_mean": v,
            "brain_vnc_separation": body_sep[name],
            "left_mean": left, "right_mean": right,
            "left_right_separation": side_sep[name],
        }

    body_axis = max(AXES, key=lambda a: body_sep[a])
    side_axis = max(AXES, key=lambda a: side_sep[a])
    if body_axis == side_axis:
        raise GeomError("the same axis %r separates brain/VNC and L/R; "
                        "the measurement is not trustworthy" % body_axis)
    depth_axis = [a for a in AXES if a not in (body_axis, side_axis)][0]

    # Which end of the body axis the brain is at.  The viewer draws the brain
    # at the top, so it needs the sign, and the sign is measured too.
    b = report["axes"][body_axis]["brain_mean"]
    v = report["axes"][body_axis]["vnc_mean"]
    report["body_axis"] = body_axis
    report["side_axis"] = side_axis
    report["depth_axis"] = depth_axis
    report["brain_at_low_end"] = bool(b < v)
    report["note"] = ("body and side axes measured from somaNeuromere and "
                      "somaSide labels, which are independent of the "
                      "coordinates; no axis order is assumed")
    return report


def check_order(rows, readout, stim):
    """Prove that SUBCIRCUIT.json's body order IS the network's index order.

    WHY THIS MATTERS MORE THAN IT LOOKS.  Everything the viewer draws hangs
    off this mapping: the stream carries neuron INDICES, and the sidecar turns
    an index into a position.  If the order were wrong the picture would still
    look like a fly brain -- it would simply light up the wrong cells, and
    nothing downstream could tell.  The Phase G plan recorded the mapping as
    "not independently re-verified against the .bin"; this is that check.

    Two independent witnesses are used, and neither is the body list itself:

      the network header      says which INDICES are stimulus and readout
      the annotations         say which BODIES are MN9 and which are the
                              D-52 sugar sensors

    They can only agree if the order is right.  The committed names file is
    checked too, because it is what the MVS driver prints: a viewer and a
    report that disagreed about which neuron is which would be worse than
    either being wrong alone."""
    # D-52's sets: readout MN9 (2 neurons), stimulus PhG9 + dorsal_tpGRN (14).
    for index in sorted(readout):
        typ = (rows[index]["type"] or "").upper()
        if not typ.startswith("MN9"):
            raise GeomError("index %d is a readout in %s but its body %d is "
                            "type %r, not MN9 -- the body order does not "
                            "match the network"
                            % (index, NETFILE, rows[index]["bodyId"],
                               rows[index]["type"]))
    for index in sorted(stim):
        typ = (rows[index]["type"] or "").upper()
        if not (typ.startswith("PHG9") or "TPGRN" in typ):
            raise GeomError("index %d is a stimulus neuron in %s but its "
                            "body %d is type %r, not PhG9 or dorsal_tpGRN "
                            "(D-52)" % (index, NETFILE,
                                        rows[index]["bodyId"],
                                        rows[index]["type"]))

    namefile = os.path.join(NETDIR, "onfnam-malecns-v1.0-srext.txt")
    if os.path.exists(namefile):
        seen = 0
        for line in open(namefile, "r"):
            if not line.strip():
                continue
            index = int(line[:5])
            name = line[6:40].strip()
            want = "%s-%d" % ((rows[index]["type"] or "?"),
                              rows[index]["bodyId"])
            clean = "".join(c if c in
                            "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-."
                            else "_" for c in want.upper())
            if name != clean:
                raise GeomError("ONFNAM index %d is %r, this sidecar makes "
                                "it %r" % (index, name, clean))
            seen += 1
        if seen == 0:
            raise GeomError("%s is empty" % namefile)
    return True


def build(backdrop_n=BACKDROP_N):
    frame = load_annotations()
    sub = json.loads(open(SUBCIRCUIT, "r").read())
    entry = sub["subcircuits"][SUBKEY]
    bodies = entry["bodies"]
    # `N` is SR-EXT-03's extraction TARGET; `neurons` is what the network
    # actually holds, which is one larger here because `readout_added` is 1 --
    # an MN9 outside the top 500 was added so the readout set is complete.
    if len(bodies) != entry["neurons"]:
        raise GeomError("SUBCIRCUIT.json: %d bodies for neurons=%d"
                        % (len(bodies), entry["neurons"]))

    axes = measure_axes(frame)

    # Index the annotations once, by bodyId.
    ann = {}
    for body, typ, cls, side, nm, loc in zip(
            frame["bodyId"], frame["type"], frame["class"],
            frame["somaSide"], frame["somaNeuromere"],
            frame["somaLocation"]):
        xyz = None
        if loc is not None:
            try:
                if len(loc) == 3:
                    xyz = (int(loc[0]), int(loc[1]), int(loc[2]))
            except TypeError:
                xyz = None
        ann[int(body)] = {"type": None if typ is None else str(typ),
                          "class": None if cls is None else str(cls),
                          "somaSide": None if side is None else str(side),
                          "somaNeuromere": None if nm is None else str(nm),
                          "xyz": xyz}

    missing = [b for b in bodies if b not in ann]
    if missing:
        raise GeomError("%d of %d bodies are not in the annotations: %s"
                        % (len(missing), len(bodies), missing[:5]))

    # The network is read BEFORE placement, because D-384's first fallback
    # needs its edges: a neuron with no soma sits where the neurons it drives
    # sit.
    import netread
    spec = netread.read(os.path.join(NETDIR, NETFILE))
    if spec["n"] != len(bodies):
        raise GeomError("%s holds %d neurons, SUBCIRCUIT.json lists %d"
                        % (NETFILE, spec["n"], len(bodies)))
    rowptr, target = spec["rowptr"], spec["target"]
    stim = set(int(i) for i in spec["stim"])
    readout = set(int(i) for i in spec["readout"])

    # Centroids over MEASURED positions only, at every level, so an imputed
    # position can never feed another imputed position.  Without that rule the
    # 14 GRNs -- which all lack a soma and all synapse onto one another's
    # targets -- could bootstrap each other into a position no measurement
    # supports.
    measured = {}
    by_type = {}
    for index, body in enumerate(bodies):
        a = ann[body]
        if a["xyz"] is not None:
            measured[index] = a["xyz"]
            by_type.setdefault(a["type"], []).append(a["xyz"])
    if not measured:
        raise GeomError("no body in the subcircuit has a soma position")

    def centroid(points):
        return [int(round(sum(p[i] for p in points) / float(len(points))))
                for i in range(3)]

    whole = centroid(list(measured.values()))

    rows = []
    n_placed = 0
    for index, body in enumerate(bodies):
        a = ann[body]
        if a["xyz"] is not None:
            x, y, z = a["xyz"]
            placed, basis = False, "measured"
        else:
            outs = [measured[t] for t in target[rowptr[index]:
                                                rowptr[index + 1]]
                    if t in measured]
            group = by_type.get(a["type"])
            if outs:
                x, y, z = centroid(outs)
                basis = "target centroid (%d measured targets)" % len(outs)
            elif group:
                x, y, z = centroid(group)
                basis = "type centroid (%d measured)" % len(group)
            else:
                x, y, z = whole
                basis = "subcircuit centroid"
            placed, n_placed = True, n_placed + 1
        rows.append({"index": index, "bodyId": body,
                     "x": x, "y": y, "z": z,
                     "somaSide": a["somaSide"],
                     "somaNeuromere": a["somaNeuromere"],
                     "class": a["class"], "type": a["type"],
                     "placed": placed, "basis": basis,
                     "role": ("readout" if index in readout else
                              "stimulus" if index in stim else
                              "interneuron")})

    check_order(rows, readout, stim)

    doc = {
        "network": NETFILE,
        "subcircuit": SUBKEY,
        "n": len(rows),
        "measured": len(rows) - n_placed,
        "placed": n_placed,
        "dataset": "male-cns:v1.0",
        "source": "somaLocation in "
                  "body-annotations-male-cns-v1.0-minconf-0.5.feather",
        "limits": ["soma positions only, not neurites",
                   "%d of %d positions are imputed and flagged placed"
                   % (n_placed, len(rows))],
        "projection": axes,
        "neurons": rows,
    }

    # The backdrop: a fixed stride over bodyId-sorted order.
    everything = sorted(coords(frame))
    stride = max(1, len(everything) // max(1, backdrop_n))
    cloud = everything[::stride]
    return doc, cloud, len(everything), stride


def write(doc, cloud, total, stride):
    if not os.path.isdir(GEOMDIR):
        os.makedirs(GEOMDIR)
    gpath = os.path.join(GEOMDIR, "srext-geom.json")
    with open(gpath, "w", newline="\n") as fh:
        json.dump(doc, fh, indent=1, sort_keys=True)
        fh.write("\n")
    bpath = os.path.join(GEOMDIR, "backdrop.csv")
    with open(bpath, "w", newline="\n") as fh:
        fh.write("# MaleCNS v1.0 soma positions, every %dth of %d by "
                 "bodyId order (deterministic, FR-PRP-09)\n"
                 % (stride, total))
        fh.write("bodyId,x,y,z\n")
        for body, x, y, z in cloud:
            fh.write("%d,%d,%d,%d\n" % (body, x, y, z))
    return gpath, bpath


def main(argv):
    backdrop_n = BACKDROP_N
    if "--backdrop" in argv:
        backdrop_n = int(argv[argv.index("--backdrop") + 1])

    try:
        doc, cloud, total, stride = build(backdrop_n)
    except GeomError as exc:
        sys.stderr.write("geom: %s\n" % exc)
        return 1

    p = doc["projection"]
    print("geom: %d neurons, %d measured, %d placed"
          % (doc["n"], doc["measured"], doc["placed"]))
    print("geom: body axis %s (brain-VNC separation %.0f, brain at %s end), "
          "side axis %s (L-R separation %.0f), depth axis %s"
          % (p["body_axis"],
             p["axes"][p["body_axis"]]["brain_vnc_separation"],
             "low" if p["brain_at_low_end"] else "high",
             p["side_axis"],
             p["axes"][p["side_axis"]]["left_right_separation"],
             p["depth_axis"]))
    print("geom: backdrop %d of %d somata (every %dth)"
          % (len(cloud), total, stride))

    if "--check" in argv:
        gpath = os.path.join(GEOMDIR, "srext-geom.json")
        if not os.path.exists(gpath):
            sys.stderr.write("geom: %s is absent\n" % gpath)
            return 1
        on_disk = json.loads(open(gpath, "r").read())
        same = json.dumps(on_disk, sort_keys=True) == \
            json.dumps(doc, sort_keys=True)
        print("geom: on-disk sidecar %s"
              % ("matches" if same else "DIFFERS from a fresh build"))
        return 0 if same else 1

    gpath, bpath = write(doc, cloud, total, stride)
    for path in (gpath, bpath):
        print("geom: wrote %s (%d bytes)" % (path, os.path.getsize(path)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
