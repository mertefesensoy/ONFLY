# -*- coding: utf-8 -*-
"""The ONFNAM names file against IR-NAM-01 … IR-NAM-03 (D-267 … D-269).

The file is committed, so almost every check here reads it rather than
regenerating it.  That is deliberate: regenerating needs pandas, pyarrow
and a 14.5 MB gitignored feather, and a bare checkout must still be able
to prove that what it holds is well formed.  The one case that does
regenerate prints a skip line and passes when its prerequisites are
absent -- the pattern D-233 set for `liclint` and the `prep` tests.

What is checked, and against what:

  IR-NAM-01  every record is exactly 80 columns; columns 1-5 a
             zero-padded decimal index; column 6 blank; the name
             left-aligned in 7-40; 41-80 blank
  IR-NAM-02  every name character is A-Z, 0-9, underscore, hyphen or
             period, and no lowercase survives
  IR-NAM-03  the file is pure ASCII, so text-mode transport can
             translate it to EBCDIC without loss
  IR-COM-06  the indices in the file are exactly the readout and
             stimulus indices the NETWORK carries -- read independently
             with layout/netread.py, not from the names file
  D-267      a readout row names its cell type and body id
  D-269      for `srext`, the rank pairing agrees with the independent
             501-entry body list in SUBCIRCUIT.json
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for sub in ("prep", "layout", "tools"):
    sys.path.insert(0, os.path.join(ROOT, sub))

import names                                           # noqa: E402
import netread                                         # noqa: E402
import onfres                                          # noqa: E402

PASS, FAIL = [0], [0]


def check(name, ok, detail=""):
    (PASS if ok else FAIL)[0] += 1
    sys.stdout.write("  %-4s %-54s %s\n"
                     % ("ok" if ok else "FAIL", name, detail))


def parse(path):
    """[(index, name)] read strictly by IR-NAM-01's columns."""
    raw = io.open(path, "rb").read()
    text = raw.decode("ascii")
    out = []
    for lineno, line in enumerate(text.split("\n"), 1):
        if line == "":
            continue
        if len(line) != names.RECLEN:
            raise AssertionError("%s:%d is %d columns, not %d"
                                 % (path, lineno, len(line), names.RECLEN))
        ident = line[:names.ID_COLS]
        if not ident.isdigit():
            raise AssertionError("%s:%d columns 1-5 are %r" % (path, lineno,
                                                               ident))
        if line[names.ID_COLS] != " ":
            raise AssertionError("%s:%d column 6 is not blank" % (path,
                                                                  lineno))
        field = line[names.NAME_OFF:names.NAME_OFF + names.NAME_COLS]
        tail = line[names.NAME_OFF + names.NAME_COLS:]
        if tail.strip():
            raise AssertionError("%s:%d columns 41-80 are not blank"
                                 % (path, lineno))
        if field != field.rstrip().ljust(names.NAME_COLS):
            raise AssertionError("%s:%d name is not left-aligned"
                                 % (path, lineno))
        out.append((int(ident), field.rstrip()))
    return out


def main():
    mapping_readouts = {10331, 16949}

    for label in names.DEFAULT_NETS:
        path = names.namepath(label)
        if not os.path.isfile(path):
            check("%s: names file present" % label, False, "absent")
            continue

        raw = io.open(path, "rb").read()

        # IR-NAM-03
        try:
            raw.decode("ascii")
            ascii_ok = True
        except UnicodeDecodeError:
            ascii_ok = False
        check("%s: IR-NAM-03 pure ASCII" % label, ascii_ok,
              "%d bytes" % len(raw))

        # IR-NAM-01
        try:
            rows = parse(path)
            check("%s: IR-NAM-01 record shape" % label, True,
                  "%d rows of %d columns" % (len(rows), names.RECLEN))
        except AssertionError as exc:
            check("%s: IR-NAM-01 record shape" % label, False, str(exc))
            continue

        # IR-NAM-02
        offenders = [n for _i, n in rows
                     if set(n) - names.ALLOWED or n != n.upper()]
        check("%s: IR-NAM-02 alphabet and case" % label, not offenders,
              "%d names" % len(rows) if not offenders
              else "offending: %s" % offenders[:3])

        # unique names and ascending indices
        got = [i for i, _n in rows]
        check("%s: indices ascending and unique" % label,
              got == sorted(set(got)) and len(got) == len(set(got)),
              "%d..%d" % (got[0], got[-1]) if got else "empty")
        check("%s: names unique" % label,
              len(set(n for _i, n in rows)) == len(rows),
              "%d distinct" % len(set(n for _i, n in rows)))

        # IR-COM-06: the indices are the network's, read independently.
        #
        # `data/networks/*.bin` is gitignored (322 MB), so a bare clone
        # has the names files but not the networks they were derived
        # from.  Skip rather than fail, the pattern D-233 set for
        # `liclint` and the `prep` tests: everything above this line
        # still runs, and the skip line says why.
        if not os.path.isfile(names.netpath(label)):
            text, fatal = onfres.skipline(
                "names/network", "no network fixture; run `make fixtures`")
            check("%s: indices == the network's readout+stimulus" % label,
                  not fatal, text)
            text, fatal = onfres.skipline("names/network",
                                          "no network fixture")
            check("%s: D-267 readout rows are MN9-<bodyId>" % label,
                  not fatal, text)
            continue
        spec = netread.read(names.netpath(label))
        want = sorted([int(i) for i in spec["readout"]]
                      + [int(i) for i in (spec.get("stim")
                                          or spec.get("stimulus") or [])])
        check("%s: indices == the network's readout+stimulus" % label,
              got == want,
              "readout %s" % sorted(int(i) for i in spec["readout"]))

        # D-267: the readout rows name type and body id
        read_idx = sorted(int(i) for i in spec["readout"])
        named = dict(rows)
        good = all(named.get(i, "").startswith("MN9-")
                   and int(named[i].split("-")[1]) in mapping_readouts
                   for i in read_idx)
        check("%s: D-267 readout rows are MN9-<bodyId>" % label, good,
              ", ".join("%d=%s" % (i, named.get(i)) for i in read_idx))

    # D-269: regenerate and compare, when the prerequisites are here.
    try:
        bad, _summary = names.emit(list(names.DEFAULT_NETS), check_only=True)
        check("D-269: regenerating reproduces the committed files", bad == 0,
              "%d differing" % bad)
    except names.NamesError as exc:
        # D-548 exempts only the cause D-545 makes permanent, the feather
        # that is not distributed.  A missing pandas is an ordinary
        # dependency skip, and any other NamesError is reported under its
        # own name so that strict mode fails it.  (Before P-44 every
        # NamesError here, a real regeneration fault included, printed as
        # a passing row; that is recorded as a finding, not changed here.)
        if not os.path.isfile(names.ANNOT):
            cid = "names/regenerate-feather"
        else:
            try:
                import pandas                           # noqa: F401
                cid = "names/regenerate"
            except ImportError:
                cid = "names/regenerate-pandas"
        text, fatal = onfres.skipline(cid, str(exc).splitlines()[0])
        check("D-269: regenerating reproduces the committed files",
              not fatal, text)

    # The framing trap.  The committed file is TEXT (IR-NAM-01) and
    # carries a newline after each 80-column row; ONFLYDRV's FD says
    # RECORDING MODE IS F.  Read raw on x86, record 2 begins one byte
    # late and every row after the first is silently skipped -- which
    # is how `srext` readout 88 came back *UNNAMED* on 2026-09-15 while
    # readout 9 was named correctly.  names.records() is the framing
    # step; this case exists so that nobody removes it.
    for label in names.DEFAULT_NETS:
        if not os.path.isfile(names.namepath(label)):
            continue
        raw = io.open(names.namepath(label), "rb").read()
        framed = names.records(label)
        naive = [raw[i:i + names.RECLEN]
                 for i in range(0, len(raw), names.RECLEN)]
        check("%s: raw bytes are NOT %d-byte records" % (label,
                                                         names.RECLEN),
              len(raw) % names.RECLEN != 0
              or any(not r[:5].decode("ascii", "replace").isdigit()
                     for r in naive),
              "%d bytes, %d rows x %d + newlines"
              % (len(raw), len(framed), names.RECLEN))
        check("%s: records() frames them correctly" % label,
              len(b"".join(framed)) == len(framed) * names.RECLEN
              and all(r[:5].decode("ascii").isdigit() for r in framed)
              and b"\n" not in b"".join(framed),
              "%d records, %d bytes"
              % (len(framed), len(b"".join(framed))))

    # IR-NAM-02's substitution rule, exercised directly.
    clean, changed = names.sanitise("dorsal_tpGRN+9")
    check("IR-NAM-02 sanitise() uppercases and substitutes",
          clean == "DORSAL_TPGRN_9" and changed, clean)
    clean2, changed2 = names.sanitise("MN9-10331")
    check("IR-NAM-02 sanitise() leaves a legal name alone",
          clean2 == "MN9-10331" and not changed2, clean2)

    sys.stdout.write("run_names: %d passed, %d failed\n" % (PASS[0], FAIL[0]))
    return 1 if FAIL[0] else 0


if __name__ == "__main__":
    sys.exit(main())
