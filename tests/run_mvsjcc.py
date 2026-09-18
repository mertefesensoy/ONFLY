# -*- coding: utf-8 -*-
"""Everything about ACC-5 row 7 that can be judged without TK5.

`tools/mvsjcc.py` builds an 8,390-card deck and submits it to a
mainframe, so what it *produces* can only be judged there.  What can be
judged here is everything whose failure would waste that run, plus the
one property row 7 exists to have and could silently lose.

WHAT IS CHECKED
---------------
**Row 7 links what row 6 links.**  This is the whole point of the row.
A determinism row that varied the compiler *and* the set of translation
units, or their order, would not be evidence that the fingerprint is a
property of the source -- it would be two different programs agreeing by
luck.  `mvsjcc.run_deck()` derives its source list from
`mvsrun._sources()` rather than restating it, and the test asserts the
member sequence equals `mvsrun.UNIT_MEMBERS` and that the deck compiles
exactly those thirteen, in that order.

**Both rows read the same network.**  D-286 installed the network as a
catalogued dataset because JCC's `fopen` returns NULL on a unit-record
DD in every mode.  If row 6's `ONFNET` DD ever drifted back to the
reader, the two rows would differ in transport as well as compiler and
nobody would notice until someone read the JCL.  So the test asserts
both GO steps name `mvsrun.NET_DSN` and that neither names the reader
unit.

**The GO step carries D-284's PARM.**  Row 7 changes no engine source;
it passes the three dataset names as arguments instead.  The spelling
is `//DDN:` because that is the only one JCC's libc honours (measured,
`--ddprobe`), and the order is argv[2] network, argv[3] request,
argv[4] response, which is D-86 and D-223's convention.  A PARM with
the names in the wrong order would run, read the wrong datasets and
fail confusingly.

**The deck is submittable.**  80 columns, JCL inside column 71, no card
equal to the IEBUPDTE delimiter, member names at most 8 characters and
unique ignoring case (C-04).

**The probe programs are well-formed C.**  Every probe source is built
by string-joining lines in Python, which is exactly how an escaped
newline gets into the middle of a C string literal -- it happened once
in this session and cost a mainframe run.  So each generated source is
checked to contain no embedded newline and to have balanced braces.

Run:

    python tests/run_mvsjcc.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import mvsjcc                                         # noqa: E402
import mvsrun                                         # noqa: E402
import mvsub                                          # noqa: E402

PASS, FAIL = [0], [0]


def check(name, ok, detail=""):
    (PASS if ok else FAIL)[0] += 1
    sys.stdout.write("  %-4s %-52s %s\n"
                     % ("ok" if ok else "FAIL", name, detail))


def go_cards(deck, step="GO"):
    """One step's cards: its EXEC card, its continuation and its DDs."""
    out = []
    started = False
    for card in deck:
        if card.startswith("//%s " % step):
            started = True
            out.append(card)
            continue
        if started:
            if card == "//*" or card == "//":
                break
            if (card.startswith("//") and " EXEC " in card
                    and not card.startswith("//  ")):
                break
            out.append(card)
    return out


def main():
    run = mvsjcc.run_deck()
    row6 = mvsrun.run_deck()

    # --- the deck is submittable -------------------------------------
    try:
        mvsub.check_cards(run)
        check("ONFJRUN passes mvsub.check_cards", True,
              "%d cards, longest %d" % (len(run), max(len(c) for c in run)))
    except Exception as exc:                      # noqa: BLE001
        check("ONFJRUN passes mvsub.check_cards", False, str(exc))
    over = [c for c in run if c.startswith("//") and len(c) > 71]
    check("every JCL card is inside column 71", not over,
          "%d over" % len(over))

    # --- row 7 links what row 6 links --------------------------------
    # Matched on content, not on column: a DD name is padded to eight
    # and a test that counted the padding would fail on a rename rather
    # than on the thing it is checking.
    compiled = [c.split("(")[1].split(")")[0] for c in run
                if c.startswith("//SYSIN") and " DD DSN=" in c
                and "(" in c]
    check("ONFJRUN compiles UNIT_MEMBERS, in order",
          tuple(compiled) == mvsrun.UNIT_MEMBERS,
          "%d units, last %s"
          % (len(compiled), compiled[-1] if compiled else "-"))
    lower = [m.lower() for m in mvsrun.UNIT_MEMBERS]
    check("member names are <=8 and unique ignoring case (C-04)",
          len(set(lower)) == len(lower)
          and all(len(m) <= 8 for m in mvsrun.UNIT_MEMBERS),
          "%d members" % len(lower))
    check("one JCC compile step per unit",
          sum(1 for c in run if c.startswith("//COMP")
              and " EXEC PGM=JCC," in c) == len(mvsrun.UNIT_MEMBERS),
          "%d COMP steps" % sum(1 for c in run if c.startswith("//COMP")))

    # --- one PRELINK, reading every object ---------------------------
    # Scoped to the PRELINK step: "&&OBJ" also prefixes each compile's
    # own JCCOASM dataset and the "&&OBJMOD" PRELINK writes, so a
    # whole-deck count answers a different question than it looks like.
    pre = [c for c in go_cards(run, "PRELINK")
           if "DD DSN=&&OBJ" in c and "OBJMOD" not in c]
    check("PRELINK reads every object as one concatenation",
          len(pre) == len(mvsrun.UNIT_MEMBERS),
          "%d objects on the I DD" % len(pre))
    check("IEWL is given NCAL (PRELINK resolved the runtime)",
          any("NCAL" in c for c in run if "PGM=IEWL" in c
              or c.startswith("//            PARM='NCAL")),
          "SYS2.PROCLIB(JCCCL)'s own PARM")

    # --- both rows read the installed network (D-286) ----------------
    g7, g6 = go_cards(run), go_cards(row6)
    check("row 7 ONFNET is the installed dataset",
          any("//ONFNET   DD DSN=%s," % mvsrun.NET_DSN in c
              or "//ONFNET   DD DSN=%s,DISP=SHR" % mvsrun.NET_DSN == c
              for c in g7),
          mvsrun.NET_DSN)
    check("row 6 ONFNET is the same dataset",
          any(mvsrun.NET_DSN in c for c in g6 if c.startswith("//ONFNET")),
          mvsrun.NET_DSN)
    check("neither row names the reader unit",
          not any("UNIT=10C" in c for c in g6 + g7),
          "no unit-record DD in either GO step")

    # --- D-284's PARM ------------------------------------------------
    parm = [c for c in g7 if "PARM='" in c]
    want = ("RUN //DDN:ONFNET //DDN:ONFREQ //DDN:ONFRSP")
    check("GO carries D-284's three names, in argv order",
          len(parm) == 1 and want in parm[0],
          parm[0].strip() if parm else "no PARM card")
    check("the response dataset is row 7's own, not row 6's",
          mvsjcc.jcc_rsp_dsn() != mvsrun.RSP_DSN
          and any(mvsjcc.jcc_rsp_dsn() in c for c in g7),
          "%s vs %s" % (mvsjcc.jcc_rsp_dsn(), mvsrun.RSP_DSN))
    check("SCRATCH2 deletes it first, so the job reruns",
          any(c.startswith("//D1") and mvsjcc.jcc_rsp_dsn() in c
              and "DISP=(MOD,DELETE)" in c for c in run),
          "DISP=(MOD,DELETE)")

    # --- both halves of the suite, and nothing crossed over ----------
    # D-458 made the `path` half row 7's scope and D-462 gave each
    # network its own job name and response dataset.  Until then this
    # tool REFUSED --net, and the refusal named the failure it was
    # guarding: the wrong network under the right job name -- a run that
    # costs hours of TK5 and whose listing nobody can trust, because the
    # evidence of which network it read is the thing that went wrong.
    #
    # The refusal is gone, so these checks are what stands in its place.
    # Every one of them fails if any name leaks between the two halves.
    seen = {}
    for name in sorted(mvsjcc.JCC_NAMES):
        mvsrun.select(name)
        deck_n = mvsjcc.run_deck()
        go_n = go_cards(deck_n)
        job_n = mvsjcc.jcc_job()
        rsp_n = mvsjcc.jcc_rsp_dsn()
        seen[name] = (job_n, rsp_n, mvsrun.NET_DSN, mvsrun.REQ_DSN)

        check("%s: the job card names %s" % (name, job_n),
              deck_n[0].startswith("//%-8s JOB" % job_n),
              deck_n[0][:40])
        check("%s: GO reads its own network %s" % (name, mvsrun.NET_DSN),
              any("//ONFNET   DD DSN=%s,DISP=SHR" % mvsrun.NET_DSN == c
                  for c in go_n),
              mvsrun.NET_DSN)
        check("%s: GO reads its own requests %s" % (name, mvsrun.REQ_DSN),
              any("//ONFREQ   DD DSN=%s,DISP=SHR" % mvsrun.REQ_DSN == c
                  for c in go_n),
              mvsrun.REQ_DSN)
        check("%s: GO writes its own response %s" % (name, rsp_n),
              any(c.startswith("//ONFRSP   DD DSN=%s," % rsp_n)
                  for c in go_n),
              rsp_n)
        check("%s: links UNIT_MEMBERS, in order" % name,
              tuple(m for _s, m in
                    [(s, m) for (s, m, *_r) in
                     [tuple(e) + ((),) * (3 - len(e))
                      for e in mvsrun._sources()]])
              == mvsrun.UNIT_MEMBERS,
              "%d units" % len(mvsrun.UNIT_MEMBERS))
        try:
            mvsub.check_cards(deck_n)
            ok_n = True
        except Exception as exc:                      # noqa: BLE001
            ok_n = False
            check("%s: deck is submittable" % name, False, str(exc))
        if ok_n:
            check("%s: deck is submittable" % name, True,
                  "%d cards, longest %d"
                  % (len(deck_n), max(len(c) for c in deck_n)))

    check("the two halves share no name at all",
          len(set(seen["srext"])) == 4 and len(set(seen["path"])) == 4
          and not (set(seen["srext"]) & set(seen["path"])),
          "%s vs %s" % (seen["srext"], seen["path"]))
    check("srext keeps the names VL-93 recorded",
          seen["srext"][0] == "ONFJRUN"
          and seen["srext"][1].endswith(".ONFLY.JRSP"),
          "%s / %s" % (seen["srext"][0], seen["srext"][1]))
    check("row 7 never writes row 6's response dataset",
          all(seen[n][1] != "%s.ONFLY.%s" % (mvsjcc.USER, s["rsp"])
              for n in seen for s in mvsrun.NETS.values()),
          "JRSP/JPRSP vs ERSP/PRSP")

    # check_names() is the assertion the refusal became.  Prove it
    # REFUSES, not merely that it exists: a guard that cannot fail is
    # not a guard.  The failure mode it models is a caller that set the
    # module globals by hand instead of going through mvsrun.select().
    mvsrun.select("path")
    saved = mvsrun.NET_DSN
    try:
        mvsrun.NET_DSN = "%s.ONFLY.ENET" % mvsjcc.USER   # srext's
        try:
            mvsjcc.check_names()
            refused = False
        except mvsjcc.JccError:
            refused = True
    finally:
        mvsrun.NET_DSN = saved
    check("check_names refuses a crossed-over network DSN", refused,
          "path job with srext's ONFNET")

    check("take_net refuses an unknown network",
          mvsjcc.take_net(["--net", "nosuch", "--run"]) is None
          and mvsjcc.take_net(["--net"]) is None,
          "--net nosuch, and --net with no name")
    # D-465.  The run job outlives its submitter, so --recover has to
    # exist AND has to be reachable from the command line: a recover
    # function nothing dispatches to is the same as no recover at all,
    # and the moment it is needed is the moment it is too late to find
    # out.  Reading the printer is checked here only as far as "it
    # refuses cleanly when the job is not there"; what it recovers can
    # only be judged on TK5.
    check("--recover exists and is dispatched",
          callable(getattr(mvsjcc, "run_recover", None))
          and "--recover" in mvsjcc.USAGE,
          "mvsjcc.py --recover [--out DIR]")
    mvsrun.select("srext")
    check("no --net leaves srext selected (D-259)",
          mvsjcc.take_net(["--run", "--out", "x"]) == ["--run", "--out", "x"]
          and mvsrun.NETNAME == "srext",
          mvsrun.NETNAME)

    # --- the install job ---------------------------------------------
    inst = mvsrun.install_net_deck()
    try:
        mvsub.check_cards(inst)
        ok_inst = True
    except Exception:                             # noqa: BLE001
        ok_inst = False
    check("ONFENET passes mvsub.check_cards", ok_inst,
          "%d cards" % len(inst))
    check("ONFENET copies the reader into the installed dataset",
          any("UNIT=10C" in c for c in inst)
          and any("DSN=%s,DISP=(,CATLG,DELETE)" % mvsrun.NET_DSN in c
                  for c in inst),
          "IEBGENER reader -> %s" % mvsrun.NET_DSN)
    check("ONFENET writes FB/80, the record form FR-LOD-03 reads",
          any("RECFM=FB,LRECL=80" in c for c in inst),
          "DCB=(RECFM=FB,LRECL=80,BLKSIZE=3200)")

    # --- the recorded TK5 run ----------------------------------------
    # The same shape tests/run_mvsrun.py uses for row 6: the evidence
    # itself is checked from a clone, not just the deck that would
    # produce it.  A recording that silently went missing, or that
    # stopped agreeing with the golden suite, would otherwise be
    # noticed only the next time somebody spent ten minutes of
    # mainframe time.
    #
    # Both halves are required, not merely whichever happens to be on
    # disk: the whole point of D-458 is that row 7 covers all nineteen
    # Section 8.4 requests, and a test that quietly skipped a missing
    # recording would let the `path` half rot out of the repository
    # exactly as silently as it was missing before.
    for name in sorted(mvsjcc.JCC_NAMES):
        mvsrun.select(name)
        rec = os.path.join(ROOT, "data", "phase-e", "jcc",
                           "rsp-%s-2c.bin" % name)
        ref = os.path.join(ROOT, "data", "phase-d", "x86w",
                           "rsp-%s-2c.bin" % name)
        if not os.path.isfile(rec):
            check("%s: the TK5 JCC recording is present" % name,
                  False, rec)
            continue
        got = mvsrun.read_records(rec)
        want = mvsrun.read_records(ref)
        check("%s: the TK5 JCC recording is present" % name, True,
              "%d bytes" % os.path.getsize(rec))
        views, _lines = mvsrun.compare_records(got, want, "ONFRSP")
        check("%s: row 7 == x86-64, D-261 translated identity" % name,
              views["translated"] and views["binary"],
              "%d records; raw=%s binary=%s"
              % (len(got), views["raw"], views["binary"]))
        # golden_fingerprints resolves its network at call time, so this
        # follows the select() above; written `netname=NETNAME` in the
        # signature it would read gold-srext-2c.txt for both halves and
        # report fourteen records against five golden entries.
        gold = mvsrun.golden_fingerprints(
            os.path.join(ROOT, "data", "phase-d", "x86w"))
        off, bad = 20, []
        for (gid, wantfp), r in zip(gold, got):
            if r[off:off + 4].hex().upper() != wantfp:
                bad.append(gid)
        check("%s: row 7 == Section 8.4 fingerprints" % name,
              len(gold) == len(got) and not bad,
              "%d of %d: %s..%s" % (len(got), len(gold),
                                    gold[0][0], gold[-1][0])
              if gold else "no golden entries")
    mvsrun.select("srext")

    # --- the probe programs are well-formed C ------------------------
    sources = {"ddprobe": mvsjcc.ddprobe_source(), "rdrprobe": mvsjcc.RDR_SRC}
    for k, v in sorted(mvsjcc.MINI.items()):
        sources["mini/" + k] = v
    for name, src in sorted(sources.items()):
        nl = [l for l in src if "\n" in l or "\r" in l]
        text = "\n".join(src)
        check("%s: no embedded newline, braces balance" % name,
              not nl and text.count("{") == text.count("}"),
              "%d lines, %d braces" % (len(src), text.count("{")))

    sys.stdout.write("run_mvsjcc: %d passed, %d failed\n"
                     % (PASS[0], FAIL[0]))
    return 1 if FAIL[0] else 0


if __name__ == "__main__":
    sys.exit(main())
