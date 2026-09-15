# -*- coding: utf-8 -*-
"""Emit the ONFNAM names file (IR-NAM-01 … IR-NAM-03, FR-PRP-07, D-269).

WHY THIS EXISTS AND WHY IT IS A SEPARATE TOOL
---------------------------------------------
FR-PRP-07 requires the pipeline to emit "the names file (IR-NAM)", and
until 2026-09-15 none existed: no file, no manifest entry, and
`grep -rn 'IR-NAM'` matched only the DD declaration in
`cobol/ONFLYDRV.cbl`, which says "Declared for Phase E".  FR-BAT-04
requires the report to print "each readout neuron's name" while IR-COM-06
forbids the response from carrying names, so the report could not be
written at all.

The obvious home would be `prep/emit.py`, which is literally "the
pipeline".  D-269 rules otherwise, for a measured reason: `emit.py`
re-derives the networks from the MaleCNS source data, so running it
rewrites `data/networks/*.bin` -- and the response fingerprint includes
the network's payload CRC (IR-COM-05), so a single differing byte would
invalidate every Section 8.4 fingerprint and the MVS results taken on
2026-09-15.  This module reads the networks that already exist and
writes beside them.

HOW AN INDEX BECOMES A BODY ID WITHOUT THE 1 GB WEIGHTS FILE
------------------------------------------------------------
The identifier a response carries is the neuron's INDEX in the network,
not its MaleCNS body id (IR-COM-06; `readout: [9, 88]` for `srext`).
Recovering the body id looks as though it needs the network's whole node
list, which lives only in the connectome weights -- 1,051,241,946 bytes.

It does not.  `prep/emit.py` assigns indices as

    searchsorted(nodes, sort(body_ids))        with `nodes` ascending

so the indices come out ascending in the same order as the body ids.
**The k-th smallest index is therefore the k-th smallest body id**, and
both lists are already to hand: the indices in the network header, the
body ids in the reviewed FR-PRP-02 mapping.  The pairing is exact, not
approximate, and it holds for any network that contains every stimulus
and readout neuron -- which SR-EXT-01 requires by construction.

That is a derivation, so it is CHECKED rather than trusted.
`data/networks/SUBCIRCUIT.json` carries the full 501-entry body list for
the N=500 extraction, and `verify_against_subcircuit()` confirms
`bodies[9] == 10331` and `bodies[88] == 16949` and every stimulus index
besides.  When the list is unavailable -- as it is for the `path`
fixture -- the derivation still holds but the check cannot run, and that
is reported rather than passed over.

THE RECORD FORMAT (IR-NAM-01)
-----------------------------
    columns  1-5   neuron index, zero-padded decimal
    column   6     blank
    columns  7-40  name, left-aligned
    columns 41-80  blank

Padded to a full 80 columns because IR-NAM-01 specifies LRECL=80 and a
file whose records are already that length cannot be mis-blocked on
arrival.  IR-NAM-03 sends it in TEXT mode, so the ASCII written here
becomes EBCDIC in transport; nothing in this file may therefore depend
on a byte value.

Rows are in ascending index order -- the order the driver can search
linearly against a response whose entries are themselves in index order.

Run:
    python prep/names.py                 write for srext and path
    python prep/names.py --check         verify what is on disk, write nothing
    python prep/names.py srext           one network
"""
import hashlib
import io
import json
import os
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "layout"))

import netread                                         # noqa: E402

NETDIR = os.path.join(ROOT, "data", "networks")
MAPPING = os.path.join(ROOT, "docs", "malecns-celltype-mapping.json")
ANNOT = os.path.join(ROOT, "data", "malecns",
                     "body-annotations-male-cns-v1.0-minconf-0.5.feather")
SUBCIRCUIT = os.path.join(NETDIR, "SUBCIRCUIT.json")

RECLEN = 80
ID_COLS = 5
NAME_OFF, NAME_COLS = 6, 34

#: IR-NAM-02's alphabet.  Everything else becomes an underscore.
ALLOWED = set("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-.")

DEFAULT_NETS = ("srext", "path")


class NamesError(Exception):
    pass


def netpath(label):
    return os.path.join(NETDIR, "onfnet-malecns-v1.0-%s.bin" % label)


def namepath(label):
    return os.path.join(NETDIR, "onfnam-malecns-v1.0-%s.txt" % label)


def sanitise(name):
    """IR-NAM-02: uppercase, and any other character becomes '_'.

    Returns (clean, changed) so the caller can record the original in
    the manifest, which IR-NAM-02 requires when a name is altered.
    """
    up = name.upper()
    clean = "".join(c if c in ALLOWED else "_" for c in up)
    return clean, clean != name


def load_types(body_ids):
    """{body id: cell type} from the MaleCNS annotations (FR-PRP-01).

    pandas and pyarrow are needed only to emit; the emitted file is
    committed, so a checkout that cannot read a feather can still build
    and test everything.  The import is therefore local and its failure
    is reported as what it is.
    """
    if not os.path.isfile(ANNOT):
        raise NamesError(
            "no annotations at %s -- fetch it with\n"
            "    python tools/fixtures.py --malecns annotations"
            % os.path.basename(ANNOT))
    try:
        import pandas
    except ImportError:
        raise NamesError("pandas is needed to read the annotations feather")
    frame = pandas.read_feather(ANNOT)
    wanted = set(int(b) for b in body_ids)
    hit = frame[frame["bodyId"].isin(wanted)]
    out = {}
    for body, kind in zip(hit["bodyId"], hit["type"]):
        out[int(body)] = "" if kind is None else str(kind)
    missing = sorted(wanted - set(out))
    if missing:
        raise NamesError("no annotation row for body id(s) %s" % missing)
    blank = sorted(b for b, k in out.items() if not k)
    if blank:
        raise NamesError("empty cell type for body id(s) %s" % blank)
    return out


def rows_for(label, mapping, types):
    """[(index, name, body id, cell type)] for one network, index order.

    The pairing rule is the one the module docstring derives: indices
    ascending correspond to body ids ascending, because `prep/emit.py`
    builds them with searchsorted over a sorted node array.
    """
    spec = netread.read(netpath(label))
    read_bodies = sorted(int(b) for b in mapping["readout"]["bodyIds"])
    stim_bodies = sorted(int(b) for b in mapping["stimulus_set"]["bodyIds"])
    read_idx = sorted(int(i) for i in spec["readout"])
    stim_idx = sorted(int(i) for i in (spec.get("stim")
                                       or spec.get("stimulus") or []))

    for what, idx, bodies in (("readout", read_idx, read_bodies),
                              ("stimulus", stim_idx, stim_bodies)):
        if len(idx) != len(bodies):
            raise NamesError(
                "%s: network has %d %s neurons but the mapping names %d; "
                "the rank pairing is only valid when the network contains "
                "every one of them (SR-EXT-01)"
                % (label, len(idx), what, len(bodies)))

    rows = []
    for idx, bodies in ((read_idx, read_bodies), (stim_idx, stim_bodies)):
        for i, body in zip(idx, bodies):
            kind = types[body]
            clean, _changed = sanitise("%s-%d" % (kind, body))
            if len(clean) > NAME_COLS:
                raise NamesError("name %r is %d columns, limit %d"
                                 % (clean, len(clean), NAME_COLS))
            rows.append((i, clean, body, kind))
    rows.sort()
    seen = set(i for i, _n, _b, _k in rows)
    if len(seen) != len(rows):
        raise NamesError("%s: a neuron index appears twice" % label)
    return rows


def render(rows):
    """The file's bytes, IR-NAM-01's columns, ASCII (IR-NAM-03)."""
    out = []
    for index, name, _body, _kind in rows:
        if index >= 10 ** ID_COLS:
            raise NamesError("index %d does not fit %d columns"
                             % (index, ID_COLS))
        line = ("%0*d " % (ID_COLS, index)) + name
        out.append(line.ljust(RECLEN))
    return ("\n".join(out) + "\n").encode("ascii")


def records(label):
    """The names file as fixed 80-byte records, with NO line ends.

    The committed file is TEXT -- IR-NAM-01 says so, and IR-NAM-03 has
    it "transferred in text mode so that ASCII-to-EBCDIC conversion
    happens in transport" -- so it carries a newline after each 80-column
    row.  A reader on MVS never sees those: the transport (or IEBGENER
    from card images) frames the file as RECFM=FB,LRECL=80 and the
    newline is not part of a record.

    **A program reading the committed file directly on x86 does see
    them**, and ONFLYDRV's FD says `RECORDING MODE IS F`.  So record 2
    begins one byte late, its first five columns are not digits, and the
    row is silently skipped -- which is how `srext` readout 88 came back
    `*UNNAMED*` while readout 9 was named correctly.  Exactly the trap
    `write_deck` in tests/run_cob.py documents for ONFCTL.

    This function is the framing step, named so that a caller cannot
    forget it exists.
    """
    text = io.open(namepath(label), encoding="ascii").read()
    out = []
    for line in text.split("\n"):
        if not line.strip():
            continue
        if len(line.rstrip()) > RECLEN:
            raise NamesError("%s: a row is %d columns, limit %d"
                             % (label, len(line.rstrip()), RECLEN))
        out.append(line.rstrip().ljust(RECLEN).encode("ascii"))
    return out


def verify_against_subcircuit(label, rows):
    """Check the rank pairing against a recorded body list, if there is one.

    Returns a human-readable line.  `data/networks/SUBCIRCUIT.json`
    holds the full body list for each SR-EXT-03 candidate N; the shipped
    `srext` network is the N=500 extraction, whose selection D-205 left
    unchanged when it added the compensating table.  The `path` fixture
    of D-75 has no such list, so the check reports that it could not run
    rather than reporting a pass.
    """
    if not os.path.isfile(SUBCIRCUIT):
        return "no SUBCIRCUIT.json; pairing unchecked"
    sub = json.loads(io.open(SUBCIRCUIT, encoding="utf-8").read())
    spec = netread.read(netpath(label))
    for _key, entry in sorted(sub.get("subcircuits", {}).items()):
        bodies = entry.get("bodies")
        if not bodies or len(bodies) != spec["n"]:
            continue
        wrong = [(i, b, bodies[i]) for i, _n, b, _k in rows
                 if bodies[i] != b]
        if wrong:
            raise NamesError(
                "%s: rank pairing disagrees with SUBCIRCUIT.json at "
                "index %d (derived body %d, recorded %d)"
                % ((label,) + wrong[0]))
        return ("pairing CHECKED against SUBCIRCUIT.json N=%s, %d of %d "
                "rows" % (entry.get("N"), len(rows), len(bodies)))
    return "no recorded body list of length %d; pairing unchecked" % spec["n"]


def manifest_entry(label, rows, blob, note, readout_bodies):
    """What MANIFEST.json records for one names file (D-269).

    `type` is the cell type AS THE DATASET SPELLS IT, before IR-NAM-02's
    uppercasing and substitution -- `dorsal_tpGRN`, not
    `DORSAL_TPGRN`.  That is not decoration: IR-NAM-02 requires the
    original name to be recorded in the manifest whenever it is altered,
    and ten of these sixteen rows are altered.
    """
    return {
        "file": os.path.basename(namepath(label)),
        "rows": len(rows),
        "bytes": len(blob),
        "crc32": "%08X" % (zlib.crc32(blob) & 0xFFFFFFFF),
        "sha256": hashlib.sha256(blob).hexdigest(),
        "decisions": ["D-267", "D-268", "D-269"],
        "pairing": note,
        "entries": [
            {"index": i, "name": n, "bodyId": b, "type": k,
             "role": "readout" if b in readout_bodies else "stimulus"}
            for i, n, b, k in rows
        ],
    }


def register(summary):
    """Merge the names section into data/networks/MANIFEST.json.

    Additive: `tools/fixtures.py` and everything else read `networks`,
    which is untouched.  **A later `prep/emit.py` run rewrites this file
    and would drop the section**, so `prep/names.py` must be re-run after
    any re-emission -- which is the same order the pipeline already
    implies, since the names are derived from the networks.
    """
    path = os.path.join(NETDIR, "MANIFEST.json")
    man = json.loads(io.open(path, encoding="utf-8").read())
    man.setdefault("names", {})
    man["names"].update(summary)
    # indent=2, sort_keys=True: the same spelling `prep/manifest.py` and
    # `prep/emit.py` use.  Writing it any other way reformats all 140
    # lines and buries the actual change in the diff.
    io.open(path, "w", encoding="utf-8", newline="").write(
        json.dumps(man, indent=2, sort_keys=True) + "\n")
    return path


def emit(labels, check_only=False):
    mapping = json.loads(io.open(MAPPING, encoding="utf-8").read())
    readout_bodies = set(int(b) for b in mapping["readout"]["bodyIds"])
    bodies = sorted(readout_bodies
                    | set(int(b) for b
                          in mapping["stimulus_set"]["bodyIds"]))
    types = load_types(bodies)
    bad = 0
    summary = {}
    for label in labels:
        rows = rows_for(label, mapping, types)
        blob = render(rows)
        note = verify_against_subcircuit(label, rows)
        path = namepath(label)
        if check_only:
            have = io.open(path, "rb").read() if os.path.isfile(path) else b""
            ok = have == blob
            sys.stdout.write("names: %-6s %s  %d rows, %d bytes; %s\n"
                             % (label, "OK     " if ok else "DIFFERS",
                                len(rows), len(blob), note))
            bad += 0 if ok else 1
        else:
            io.open(path, "wb").write(blob)
            sys.stdout.write("names: %-6s WROTE   %s, %d rows, %d bytes; "
                             "%s\n" % (label, os.path.basename(path),
                                       len(rows), len(blob), note))
        summary[label] = manifest_entry(label, rows, blob, note,
                                        readout_bodies)
    if not check_only and summary:
        sys.stdout.write("names: registered %d file(s) in %s\n"
                         % (len(summary),
                            os.path.basename(register(summary))))
    return bad, summary


def main(argv):
    check_only = "--check" in argv
    labels = [a for a in argv if not a.startswith("--")] or list(DEFAULT_NETS)
    try:
        bad, summary = emit(labels, check_only=check_only)
    except NamesError as exc:
        sys.stderr.write("names: %s\n" % exc)
        return 2
    for label, info in sorted(summary.items()):
        for r in info["entries"]:
            if r["role"] != "readout":
                continue
            sys.stdout.write("names:   %-6s readout index %5d -> %s "
                             "(body %d, type %s)\n"
                             % (label, r["index"], r["name"], r["bodyId"],
                                r["type"]))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
