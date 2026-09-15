# -*- coding: utf-8 -*-
"""Everything about Phase E slice 1 that can be judged without TK5.

`tools/mvsrun.py` is submitted to a mainframe, so most of what it does
cannot be tested here.  What CAN be tested is everything that would waste
a mainframe run if it were wrong, and two regressions that the additive
changes to `tools/mvsbld.py` and `tools/mvscob.py` could have introduced
in other callers.

The division is deliberate.  A deck that fails on MVS costs minutes at
best and a misattributed failure at worst -- Gate G2's log shows what a
deck defect looks like from the listing, and it does not look like a deck
defect.  So the column limits, the delimiter collisions, the member-name
rules and the link order are all checked here, where a failure costs a
second and names itself.

Cases:
  1-2   The two decks pass mvsub.check_cards: 80 columns, no card equal
        to the IEBUPDTE delimiter, JCL inside column 71.
  3     UNIT_MEMBERS matches what run_deck() actually links, and every
        member is unique ignoring case (C-04) and at most 8 characters.
  4     The five units mvseng.py omits are present, and ONFLYENG is last.
  5-6   The GO step carries IR-JCL-01's three DD names, and no PARM --
        onfeisv() reads anything that is not VERIFY as SIMULATE.
  7     The DUMP step follows GO and reads the dataset GO wrote.
  8     The control cards are the Section 8.4 `srext` requests, in the
        suite's order, and MODE=REQ is first (D-158).
  9     The records those cards must produce are byte-identical to
        data/phase-d/x86w/req-srext.bin -- the file the x86-64 recording
        was made from.  This is what makes D-260's risk bounded.
  10    write_cards() pads to a whole number of 80-byte cards and leaves
        the network's own bytes untouched at the front (FR-LOD-03).
  11    REGRESSION: mvscob.deck() with no keywords is unchanged.
  12    REGRESSION: mvsbld.build() with post=() adds no card.
  13    The IDCAMS dump parser round-trips a 412-byte record.
"""
import io
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for sub in ("tools", "tests", "generated"):
    sys.path.insert(0, os.path.join(ROOT, sub))

import mkreq                                          # noqa: E402
import mvsbld                                         # noqa: E402
import mvscob                                         # noqa: E402
import mvsrun                                         # noqa: E402
import mvsub                                          # noqa: E402

PASS, FAIL = [0], [0]


def check(name, ok, detail=""):
    (PASS if ok else FAIL)[0] += 1
    sys.stdout.write("  %-4s %-52s %s\n"
                     % ("ok" if ok else "FAIL", name, detail))


def step_cards(deck, stepname):
    """The cards of one job step: its EXEC card and the DDs after it."""
    out = []
    started = False
    for card in deck:
        if card.startswith("//%s " % stepname) or \
           card.startswith("//%-8s " % stepname):
            started = True
            out.append(card)
            continue
        if started:
            if card.startswith("//*") or card == "//":
                break
            if card.startswith("//") and not card.startswith("//  ") and \
               " EXEC " in card:
                break
            out.append(card)
    return out


def main():
    req = mvsrun.req_deck()
    run = mvsrun.run_deck()

    # 1-2
    for name, deck in (("ONFEREQ", req), ("ONFERUN", run)):
        try:
            mvsub.check_cards(deck)
            check("%s deck passes mvsub.check_cards" % name, True,
                  "%d cards, longest %d"
                  % (len(deck), max(len(c) for c in deck)))
        except Exception as exc:                      # noqa: BLE001
            check("%s deck passes mvsub.check_cards" % name, False, str(exc))

    # 3
    members = mvsrun.UNIT_MEMBERS
    lowered = [m.lower() for m in members]
    check("C-04: members unique ignoring case, <= 8 chars",
          len(set(lowered)) == len(members)
          and all(len(m) <= 8 for m in members),
          "%d units" % len(members))

    # 4
    added = ("ONFRNDC", "ONFSTMC", "ONFKERC", "ONFREQC", "ONFCOMC")
    check("the five units mvseng.py omits are linked",
          all(m in members for m in added) and members[-1] == "ONFLYENG",
          ", ".join(added))

    # 5-6
    go = step_cards(run, "GO")
    dds = [c.split()[0][2:] for c in go if " DD " in c]
    check("GO carries IR-JCL-01's ONFNET, ONFREQ, ONFRSP",
          all(n in dds for n in ("ONFNET", "ONFREQ", "ONFRSP")),
          " ".join(dds))
    check("GO carries no PARM, so onfeisv() reads SIMULATE",
          "PARM=" not in go[0], go[0].strip())

    # 7
    dump = step_cards(run, "DUMP")
    check("DUMP follows GO and reads &&ONFRSP",
          bool(dump) and any("&&ONFRSP" in c for c in dump)
          and run.index(dump[0]) > run.index(go[0]),
          dump[0].strip() if dump else "absent")

    # 8
    cards = [t for t, _ in mvsrun.request_cards()]
    want = mkreq.golden_cards(mvsrun.NETNAME).splitlines()
    check("ONFCTL is MODE=REQ then the Section 8.4 srext cards",
          cards[0] == "MODE=REQ" and cards[1:] == want,
          "%d cards" % len(cards))

    # 9
    recs = mvsrun.expected_records()
    ref = os.path.join(ROOT, "data", "phase-d", "x86w", "req-srext.bin")
    blob = b"".join(recs)
    with open(ref, "rb") as f:
        want_blob = f.read()
    check("expected ONFREQ == data/phase-d/x86w/req-srext.bin",
          blob == want_blob,
          "%d records, %d bytes" % (len(recs), len(blob)))

    # 10
    if os.path.isfile(mvsrun.NETFILE):
        n, pad, ncards = mvsrun.write_cards()
        with open(mvsrun.NETFILE, "rb") as f:
            net = f.read()
        with open(mvsrun.CARDFILE, "rb") as f:
            deckbytes = f.read()
        check("card file: network unchanged, padded to whole cards",
              deckbytes[:n] == net and len(deckbytes) % mvsbld.CARD == 0
              and len(deckbytes) == ncards * mvsbld.CARD
              and set(deckbytes[n:]) <= set([0]),
              "%d bytes + %d pad = %d cards" % (n, pad, ncards))
    else:
        check("card file: network unchanged, padded to whole cards", True,
              "SKIP: no %s; run `make fixtures`"
              % os.path.basename(mvsrun.NETFILE))

    # 10b  The bug this case exists for: write_cards() once took its
    #      defaults in the signature, so select("path") changed where
    #      the deck was written without changing which network was
    #      read.  The wrong bytes under the right name reach MVS and
    #      fail the payload CRC as though transport had corrupted them.
    try:
        mvsrun.select("path")
        if os.path.isfile(mvsrun.NETFILE):
            n, _pad, _c = mvsrun.write_cards()
            want = os.path.getsize(mvsrun.NETFILE)
            with open(mvsrun.CARDFILE, "rb") as f:
                head = f.read(len(open(mvsrun.NETFILE, "rb").read(64)))
            with open(mvsrun.NETFILE, "rb") as f:
                net64 = f.read(64)
            check("select() changes which network write_cards reads",
                  n == want and head[:64] == net64,
                  "%s -> %d bytes" % (os.path.basename(mvsrun.CARDFILE), n))
        else:
            check("select() changes which network write_cards reads", True,
                  "SKIP: no path fixture")
    finally:
        mvsrun.select("srext")

    # 11
    check("regression: mvscob.deck() default is unchanged",
          mvscob.deck() == mvscob.deck(cards=mvscob.CARDS,
                                       req_dsn=mvscob.REQ_DSN,
                                       job=mvscob.JOB),
          "%d cards" % len(mvscob.deck()))

    # 12
    src = [(["int main(void){return 0;}"], "TSTONE")]
    check("regression: mvsbld.build(post=()) adds no card",
          mvsbld.build("T", "T", src) == mvsbld.build("T", "T", src,
                                                      post=()),
          "%d cards" % len(mvsbld.build("T", "T", src)))

    # 13
    rec = recs[0]
    listing = ["RECORD SEQUENCE NUMBER - 1"]
    for off in range(0, len(rec), 32):
        chunk = rec[off:off + 32]
        groups = " ".join(chunk[i:i + 4].hex().upper()
                          for i in range(0, len(chunk), 4))
        listing.append("%06X  %s  *................*" % (off, groups))
    back = mvscob.parse_dump("\n".join(listing))
    check("IDCAMS dump parser round-trips a 412-byte record",
          len(back) == 1 and back[0] == rec, "%d bytes" % len(back[0]))

    # --- the recorded MVS run (D-261, D-262) ---------------------------
    mvsdir = os.path.join(ROOT, "data", "phase-e", "mvs")
    refdir = os.path.join(ROOT, "data", "phase-d", "x86w")
    name = "rsp-%s-2c.bin" % mvsrun.NETNAME
    mvspath = os.path.join(mvsdir, name)

    # 14
    have = os.path.isfile(mvspath)
    check("the TK5 recording is present", have,
          "%d bytes" % os.path.getsize(mvspath) if have else "absent")

    if have:
        got = mvsrun.read_records(mvspath)
        ref = mvsrun.read_records(os.path.join(refdir, name))

        # 15  TX-01's MVS half, exactly as D-261 defines it.
        views, _ = mvsrun.compare_records(got, ref, "ONFRSP")
        check("TX-01: MVS == x86-64 under D-261 translated identity",
              views["translated"],
              "%d records; raw=%s binary=%s"
              % (len(got), views["raw"], views["binary"]))

        # 16  ACC-5 row 6, against what Section 8.4 says the fingerprint
        #     must be rather than against the other recording.
        gold = mvsrun.golden_fingerprints(refdir)
        pairs = [(gid, want, r[20:24].hex().upper())
                 for (gid, want), r in zip(gold, got)]
        check("ACC-5 row 6: MVS fingerprints == Section 8.4",
              len(gold) == len(got)
              and all(w == g for _, w, g in pairs),
              " ".join("%s=%s" % (gid, g) for gid, _, g in pairs))

        # 17  The negative case.  D-261 rejected judging on bytes 8..411
        #     alone because under that rule MVS could write anything in
        #     the stimulus code and TX-01 would still pass.  That is not
        #     an argument unless the chosen rule actually catches it.
        spoiled = [b"XXXXXXXX" + r[8:] for r in got]
        bad, _ = mvsrun.compare_records(spoiled, ref, "spoiled")
        check("D-261 has teeth: a wrong chr field fails translated",
              bad["binary"] and not bad["translated"],
              "binary=%s translated=%s"
              % (bad["binary"], bad["translated"]))

    sys.stdout.write("run_mvsrun: %d passed, %d failed\n"
                     % (PASS[0], FAIL[0]))
    return 1 if FAIL[0] else 0


if __name__ == "__main__":
    sys.exit(main())
