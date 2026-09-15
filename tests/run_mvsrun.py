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

WHAT IS CHECKED, IN FOUR GROUPS
-------------------------------
**The decks, before a mainframe sees them.**  Both pass
`mvsub.check_cards` (80 columns, no card equal to the IEBUPDTE
delimiter, JCL inside column 71).  `UNIT_MEMBERS` matches what
`run_deck()` actually links, every member is at most 8 characters and
unique ignoring case (C-04), and the five units `mvseng.py` omits are
there with ONFLYENG last.  The GO step carries IR-JCL-01's three DD
names and no PARM -- `onfeisv()` reads anything that is not VERIFY as
SIMULATE.  DUMP reads the dataset GO wrote, and SCRATCH deletes it
first, so the job reruns.

**The requests.**  ONFCTL is MODE=REQ (D-158) then the Section 8.4
cards in the suite's order, and the records they must produce are
byte-identical to `data/phase-d/x86w/req-srext.bin` -- the file the
x86-64 recording was made from.  That is what bounds the risk the owner
accepted in D-260.

**The recorded TK5 runs**, for `srext` and `path` both: TX-01's MVS
half under D-261's translated identity, ACC-5 row 6 against what
Section 8.4 says the fingerprints must BE, and IR-JCL-04's return codes
on the `path` half, where G-11 warns and G-12 and G-13 error.

**Three bugs that actually happened**, each with a case so it cannot
happen again: `write_cards()` and `golden_fingerprints()` binding a
module global as a default argument (so `select()` changed half of what
they did), and the additive keyword arguments on `mvsbld.build()` and
`mvscob.deck()` altering an existing caller's deck.
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

    # 7  DUMP must read the dataset GO wrote, and SCRATCH must delete
    #    it first -- otherwise the second run of the job fails at
    #    allocation with NOT CATLGD 2, a JCL error reported nowhere
    #    near the DD that caused it.
    dump = step_cards(run, "DUMP")
    scratch = step_cards(run, "SCRATCH")
    rsp = mvsrun.RSP_DSN
    check("DUMP follows GO and reads the dataset GO wrote",
          bool(dump) and any(rsp in c for c in dump)
          and any(rsp in c for c in go)
          and run.index(dump[0]) > run.index(go[0]),
          rsp)
    check("SCRATCH deletes it first, so the job reruns",
          any(rsp in c and "DISP=(MOD,DELETE)" in c for c in scratch),
          "%d scratch DDs" % sum(1 for c in scratch if " DD " in c))

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
    check("regression: build(post=(), scratch=()) adds no card",
          mvsbld.build("T", "T", src)
          == mvsbld.build("T", "T", src, post=(), scratch=()),
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

    # --- slice 3: install, then BUZZ (FR-BAT-01, FR-BAT-06, D-273) -----
    buzz = mvsrun.buzz_deck()
    ieng = mvsrun.install_eng_deck()
    idrv = mvsrun.install_drv_deck()
    for name, deck in (("BUZZ", buzz), ("ONFIENG", ieng),
                       ("ONFIDRV", idrv)):
        try:
            mvsub.check_cards(deck)
            check("%s deck passes mvsub.check_cards" % name, True,
                  "%d cards" % len(deck))
        except Exception as exc:                      # noqa: BLE001
            check("%s deck passes mvsub.check_cards" % name, False,
                  str(exc))

    execs = [c.split()[0][2:] for c in buzz if " EXEC " in c]
    check("BUZZ is FR-BAT-01's THREE steps, plus a scratch",
          execs == ["SCRATCH", "STEP1", "STEP2", "STEP3"], " ".join(execs))

    # IR-JCL-04 transcribed, not interpreted: "STEP2 shall run only if
    # STEP1 ended below 8" and "STEP3 shall run only if STEP2 ended
    # below 12".
    check("BUZZ carries IR-JCL-04's conditioning",
          any("STEP2    EXEC PGM=ONFLYENG,COND=(8,LE,STEP1)" in c
              for c in buzz)
          and any("STEP3    EXEC PGM=ONFLYDRV,COND=(12,LE,STEP2)" in c
                  for c in buzz),
          "COND=(8,LE,STEP1) and COND=(12,LE,STEP2)")

    # A demonstration must not be a build.  If BUZZ ever grows a
    # compile step it stops being watchable and starts being 8,500
    # cards.
    check("BUZZ compiles nothing",
          not any(p in c for c in buzz
                  for p in ("PGM=GCC", "PGM=IKFCBL00", "PGM=IEWL",
                            "PGM=IFOX00")),
          "%d cards, no compiler or linkage editor" % len(buzz))

    # STEP1's ONFCTL stream only.  STEP3 has an ONFCTL of its own
    # carrying MODE=RPT, and a filter by card text would sweep it in.
    first = buzz.index("//ONFCTL   DD *")
    ctl = buzz[first + 1:buzz.index("/*", first)]
    want_cards = [t for t, _ in mvsrun.request_cards()]
    check("BUZZ runs the D-273 srext suite",
          ctl == want_cards,
          "%d control cards: %s" % (len(ctl), ctl[0] if ctl else "-"))

    # The install jobs put the programs where BUZZ looks for them, and
    # run nothing themselves.
    for name, deck, member in (("ONFIENG", ieng, "ONFLYENG"),
                               ("ONFIDRV", idrv, "ONFLYDRV")):
        check("%s links into %s(%s) and runs nothing"
              % (name, mvsrun.LOADLIB.split(".")[-1], member),
              any("SYSLMOD  DD DSN=%s(%s),DISP=SHR"
                  % (mvsrun.LOADLIB, member) in c for c in deck)
              and not any(c.startswith("//GO ") for c in deck),
              "%d cards" % len(deck))
    check("ONFIDRV installs ONFNAM alongside the program",
          any(mvsrun.NAM_DSN in c for c in idrv)
          and any("WRITEN" in c for c in idrv),
          mvsrun.NAM_DSN)
    check("BUZZ's STEPLIB and ONFNAM name what the installs created",
          all(any(dsn in c for c in buzz)
              for dsn in (mvsrun.LOADLIB, mvsrun.NAM_DSN)),
          "%s, %s" % (mvsrun.LOADLIB, mvsrun.NAM_DSN))

    # --- the report comparator, proven before it judges anything ------
    #
    # `compare_report()` decides whether MVT COBOL's FR-BAT-04 report
    # equals GnuCOBOL's.  A comparator whose only evidence is the run it
    # is judging is not evidence, so it is exercised here against the
    # x86 reference in four ways -- and the indent case matters because
    # a printer that indents everything it writes would otherwise be
    # reported as a COBOL difference.
    ref = os.path.join(ROOT, "data", "phase-e", "x86",
                       "rpt-srext-2c.txt")
    if os.path.isfile(ref):
        good = mvsrun.report_lines(io.open(ref, "rb").read())
        wrong = list(good)
        wrong[3] = wrong[3].replace("MN9-10331", "MN9-99999")
        cases = [
            ("identical", good, True),
            ("a uniform 2-column printer indent",
             ["  " + l for l in good], True),
            ("one wrong readout name", wrong, False),
            ("a missing line", good[:-1], False),
        ]
        for what, lines, want in cases:
            got, _out = mvsrun.compare_report(lines, ref)
            check("compare_report: %s" % what, got is want,
                  "%s (expected %s)" % (got, want))
    else:
        check("compare_report: exercised against the x86 reference", True,
              "SKIP: no %s; run `make cob`" % os.path.basename(ref))

    # --- the recorded MVS runs (D-261, D-262, D-264) -------------------
    #
    # Both networks, because they prove different things.  `srext` is
    # the network the MVP ships and its five requests are all valid;
    # `path` carries G-11, G-12 and G-13, whose ONF201W, ONF203E and
    # ONF202E paths the MVS engine reaches nowhere else.
    refdir = os.path.join(ROOT, "data", "phase-d", "x86w")
    mvsdir = os.path.join(ROOT, "data", "phase-e", "mvs")

    for label in ("srext", "path"):
        mvsrun.select(label)
        name = "rsp-%s-2c.bin" % label
        mvspath = os.path.join(mvsdir, name)
        have = os.path.isfile(mvspath)
        check("%s: the TK5 recording is present" % label, have,
              "%d bytes" % os.path.getsize(mvspath) if have else "absent")
        if not have:
            continue

        got = mvsrun.read_records(mvspath)
        ref = mvsrun.read_records(os.path.join(refdir, name))

        # TX-01's MVS half, exactly as D-261 defines it.
        views, _ = mvsrun.compare_records(got, ref, "ONFRSP")
        check("%s: TX-01 MVS == x86-64, D-261 translated identity" % label,
              views["translated"],
              "%d records; raw=%s binary=%s"
              % (len(got), views["raw"], views["binary"]))

        # ACC-5 row 6, against what Section 8.4 says the fingerprint
        # must BE rather than against the other recording.
        gold = mvsrun.golden_fingerprints(refdir)
        pairs = [(gid, want, r[20:24].hex().upper())
                 for (gid, want), r in zip(gold, got)]
        check("%s: ACC-5 row 6 == Section 8.4" % label,
              len(gold) == len(got) and bool(pairs)
              and all(w == g for _, w, g in pairs),
              "%d of %d: %s..%s"
              % (len(pairs), len(got),
                 pairs[0][0] if pairs else "-",
                 pairs[-1][0] if pairs else "-"))

        # THE BUG THIS CASE EXISTS FOR.  golden_fingerprints() once
        # took `netname=NETNAME` in its signature, so select("path")
        # left it reading gold-srext-2c.txt: five golden entries
        # against fourteen records, every fingerprint reported wrong,
        # and nothing whatever wrong with the mainframe.  The second
        # mutable-looking default to bite in one session.
        check("%s: golden_fingerprints follows select()" % label,
              len(gold) == len(got),
              "%d golden entries for %d records" % (len(gold), len(got)))

        if label == "path":
            # The error-path requests carry a fingerprint too, because
            # IR-COM-05's canonical string includes the return code.
            rcs = [int.from_bytes(r[16:18], "big", signed=True)
                   for r in got]
            check("path: G-11 warns and G-12, G-13 error (IR-JCL-04)",
                  rcs[10] == 4 and rcs[11] == 8 and rcs[12] == 8
                  and max(rcs) == 8,
                  "rc per record: %s" % rcs)

    mvsrun.select("srext")

    # D-261 has teeth: the rejected binary-only rule would pass a
    # record whose stimulus code had been replaced wholesale.
    got = mvsrun.read_records(os.path.join(mvsdir, "rsp-srext-2c.bin"))
    ref = mvsrun.read_records(os.path.join(refdir, "rsp-srext-2c.bin"))
    spoiled = [b"XXXXXXXX" + r[8:] for r in got]
    bad, _ = mvsrun.compare_records(spoiled, ref, "spoiled")
    check("D-261 has teeth: a wrong chr field fails translated",
          bad["binary"] and not bad["translated"],
          "binary=%s translated=%s" % (bad["binary"], bad["translated"]))

    sys.stdout.write("run_mvsrun: %d passed, %d failed\n"
                     % (PASS[0], FAIL[0]))
    return 1 if FAIL[0] else 0


if __name__ == "__main__":
    sys.exit(main())
