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
          mvsjcc.JRSP_DSN != mvsrun.RSP_DSN
          and any(mvsjcc.JRSP_DSN in c for c in g7),
          "%s vs %s" % (mvsjcc.JRSP_DSN, mvsrun.RSP_DSN))
    check("SCRATCH2 deletes it first, so the job reruns",
          any(c.startswith("//D1") and mvsjcc.JRSP_DSN in c
              and "DISP=(MOD,DELETE)" in c for c in run),
          "DISP=(MOD,DELETE)")

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
