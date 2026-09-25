# -*- coding: utf-8 -*-
"""Everything about the 3270 transaction path that can be judged here.

`tools/ic3270.py` drives a real terminal emulator against the emulated
MVS lab and `tools/mvsicom.py` starts and stops a real region, so
what they *do* can only be judged on TK5.  What can be judged on this
host is everything whose failure would waste a lab session -- and, more
importantly, the three facts VL-129 paid for, each of which looks like
a detail and is not.

WHAT IS CHECKED, AND WHY EACH ONE EARNED A TEST
-----------------------------------------------
**The verb is comma-terminated.**  Without the comma every verb is
answered `NO VERB FOUND`, including verbs the same region accepts from
the MVS console -- which is what made this look for an hour like a
terminal that was not defined.  The rule lives in one place,
`Session.command`, and this pins it there.  If someone later "tidies"
the comma away, the failure will be an hour of the same confusion on a
running lab; here it is one line of output.

**The logon is `APPLID=`, not `APPLID(...)`.**  The parenthesised form
is what every modern reference gives.  On TK5 it is passed to TSO and
answered `IKJ56710I INVALID USERID`.  Nothing about the failure
suggests the syntax; it suggests the application is down.

**A device is named, and it is not 00C0.**  TK5 gives 00C0 to TSO at
startup.  A driver that connects without naming a device gets 00C0 and
can never reach any other application, no matter what it types.

**The protocol reader terminates on `ok` and `error`, not on a
timeout.**  It is driven here against a scripted emulator, including
the case that deadlocked a real run -- the process exiting mid-answer.

**The region deck is submittable, and it EXECs rather than restates.**
80 columns (D-93), and no copy of the shipped procedure's body, which
would be exactly the material D-132 keeps out of this repository.

No Hercules, no emulator, no network.  Milliseconds.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import goldfp                                         # noqa: E402
import ic3270                                         # noqa: E402
import mvsicom                                        # noqa: E402
import mvstx                                          # noqa: E402

PASS, FAIL = [0], [0]


def check(name, ok, detail=""):
    (PASS if ok else FAIL)[0] += 1
    sys.stdout.write("  %-4s %-54s %s\n"
                     % ("ok" if ok else "FAIL", name, detail))


class FakeProc(object):
    """A scripted stand-in for the emulator's script protocol.

    It records what was written and answers each action from a queue,
    so the reader can be driven over the exact shapes a real session
    produces: data lines, a status line, `ok`, `error`, and the
    process going away mid-answer.
    """

    def __init__(self, answers):
        self.answers = list(answers)
        self.written = []
        self._out = []
        self.stdin = self
        self.stdout = self
        self.killed = False

    # stdin side
    def write(self, text):
        self.written.append(text.rstrip("\n"))
        if self.answers:
            self._out.extend(self.answers.pop(0))

    def flush(self):
        pass

    # stdout side
    def readline(self):
        return self._out.pop(0) if self._out else ""

    def wait(self, timeout=None):
        return 0

    def kill(self):
        self.killed = True


def session_with(answers):
    s = ic3270.Session(log=None)
    s.proc = FakeProc(answers)
    return s


OK = ["U F U C(h) I 4 24 80 0 0 0x0 -\n", "ok\n"]


def main():
    sys.stdout.write("run_ic3270: the 3270 transaction path, off-lab\n")

    # --- the protocol reader ----------------------------------------
    s = session_with([["data: one\n", "data: two\n"] + OK])
    check("reader returns data lines and stops at ok",
          s.do("Ascii()") == ["one", "two"])

    s = session_with([["data: boom\n", "error\n"]])
    try:
        s.do("Bad()")
        check("reader raises on error", False, "no exception")
    except ic3270.ActionFailed as exc:
        check("reader raises on error", "boom" in str(exc))

    s = session_with([[]])          # process gone: readline returns ""
    try:
        s.do("Gone()")
        check("reader raises when the emulator goes away", False)
    except ic3270.ActionFailed as exc:
        check("reader raises when the emulator goes away",
              "without answering" in str(exc))

    # --- the three facts VL-129 paid for -----------------------------
    s = session_with([OK, OK, OK, OK, OK, OK, OK, OK])
    s.settle = 0
    s.command("VTST")
    typed = [w for w in s.proc.written if w.startswith("String(")]
    check("a verb is sent comma-terminated",
          typed and typed[-1] == 'String("VTST,")',
          typed[-1] if typed else "nothing typed")

    s = session_with([OK, OK, OK, OK, OK, OK, OK, OK])
    s.settle = 0
    s.command("SUGR,40,1000,1")
    typed = [w for w in s.proc.written if w.startswith("String(")]
    check("a command that already has commas is not doubled",
          typed and typed[-1] == 'String("SUGR,40,1000,1")',
          typed[-1] if typed else "nothing typed")

    # logon spelling: drive it past to_vtam by answering with a prompt
    prompt = (["data: Logon ===>\n"] + OK)
    s = session_with([prompt, OK, OK, OK, OK, OK, OK])
    s.settle = 0
    s.logon("INTERCOM")
    typed = [w for w in s.proc.written if w.startswith("String(")]
    check("logon uses APPLID= and not APPLID(...)",
          typed and typed[0] == 'String("LOGON APPLID=INTERCOM")',
          typed[0] if typed else "nothing typed")

    check("the default device is not 00C0, which TSO owns",
          ic3270.DEFAULT_DEVICE not in ("", None, "0C0", "00C0"),
          "device %r" % ic3270.DEFAULT_DEVICE)

    # the device becomes the logical-unit name in front of the host
    s = ic3270.Session(log=None, device="0C1")
    s.proc = FakeProc([OK, OK])
    try:
        exe_missing = ic3270.find_ws3270() is None
    except Exception:
        exe_missing = True
    s.do("Connect(%s@%s:%d)" % (s.device, s.host, s.port))
    check("the device is given as the logical-unit name",
          s.proc.written[0] == "Connect(0C1@127.0.0.1:3270)",
          s.proc.written[0])
    if exe_missing:
        sys.stdout.write("  note ws3270 is not installed on this host; "
                         "only off-lab behaviour is covered\n")

    # --- quoting, so a screen value can never break the protocol -----
    s = session_with([OK, OK, OK, OK, OK, OK])
    s.settle = 0
    s.send('A"B\\C')
    typed = [w for w in s.proc.written if w.startswith("String(")]
    check("quotes and backslashes are escaped when typed",
          typed and typed[0] == 'String("A\\"B\\\\C")',
          typed[0] if typed else "nothing typed")

    # --- the region deck ---------------------------------------------
    deck = mvsicom.deck()
    check("every card fits in 80 columns (D-93)",
          all(len(c) <= 80 for c in deck),
          "%d cards, longest %d" % (len(deck), max(len(c) for c in deck)))
    check("the deck EXECs the shipped procedure, not a copy of it",
          sum(1 for c in deck if " EXEC " in c) == 1
          and any(mvsicom.PROC in c for c in deck)
          and not any(c.startswith("//STEPLIB") for c in deck),
          "%d EXEC card(s)" % sum(1 for c in deck if " EXEC " in c))
    check("the job is ONFLY's own name, not the shipped one",
          deck[0].startswith("//%s " % mvsicom.JOBNAME),
          mvsicom.JOBNAME)
    check("the region is the 8M ceiling TBD-14 measured",
          mvsicom.REGION == "8192K", mvsicom.REGION)
    check("shutdown replies with the close-down verb VL-32 measured",
          mvsicom.SHUTDOWN == "NRCD", mvsicom.SHUTDOWN)

    # --- the display command is the MVS 3.8j spelling ----------------
    src = open(os.path.join(ROOT, "tools", "mvsicom.py"),
               encoding="utf-8").read()
    check("outstanding replies are read with `d r`, not `d r,r`",
          '"d r"' in src and '"d r,r"' not in src,
          "D R,R is answered IEE305I COMMAND INVALID on 3.8j")
    check("whether the region runs is asked of JES2, not of the log",
          '"$da"' in src,
          "a log scan answered 'not running' for a region that was")
    check("the ready message is matched against this run's job number",
          "job_numbers" in src and "before = job_numbers()" in src,
          "a stale ready gave APPLICATION IS INACTIVE")
    check("no 3270 device is hard-coded for the lab runs",
          "def free_device" in src and '"0C0"' not in src,
          "TK5 gives 00C0 to TSO, and a failed logon leaves a unit "
          "with TSO afterwards")

    # --- the build decks ---------------------------------------------
    # These are only buildable where local/onflytx exists, which D-132
    # keeps out of the tree.  A clone must still run this file, so the
    # local-dependent checks skip out loud -- the pattern D-233 set.
    try:
        decks = {"backup": mvsicom.backup_deck(),
                 "restore": mvsicom.restore_deck(),
                 "install": mvsicom.install_deck(),
                 "build": mvsicom.build_deck()}
    except mvsicom.MissingLocal:
        decks = {"backup": mvsicom.backup_deck(),
                 "restore": mvsicom.restore_deck()}
        sys.stdout.write("  skip local/onflytx is not on this host "
                         "(D-132); install and build decks not checked\n")

    for name, deck in sorted(decks.items()):
        check("%s deck: every card fits in 80 columns" % name,
              all(len(c) <= 80 for c in deck),
              "%d cards, longest %d"
              % (len(deck), max(len(c) for c in deck)))
        check("%s deck: the job title fits the JOB statement" % name,
              all(len(c) <= 71 or not c.startswith("//") for c in deck)
              and "'" in deck[0],
              "IEF642I EXCESSIVE PARAMETER LENGTH stops the job dead")

    check("the backup is written outside the shipped libraries",
          not mvsicom.BACKUP_DSN.startswith("INT."),
          mvsicom.BACKUP_DSN)
    check("the backup covers the core as well as the two tables",
          set(mvsicom.BACKUP_MEMBERS) >= {mvsicom.CORE, "BTVRBTB",
                                          "INTSCT"},
          ", ".join(mvsicom.BACKUP_MEMBERS))

    if "build" in decks:
        b = "\n".join(decks["build"])
        check("the core's control statements go to SYSLIN, not SYSIN",
              "LKED.SYSLIN" in b and "LKED.SYSIN" not in b,
              "DDNAME=SYSIN carries only the first of a concatenation")
        check("the core link raises the table size the shipped proc sets",
              "SIZE=(512K" in b and "REGION.LKED" in b,
              "IEW0664 at SIZE=(190K,20K) with one module added")
        check("the shipped link deck is concatenated, never rewritten",
              ("%s(%s)" % (mvsicom.SYMINCL, mvsicom.LINKDECK)) in b,
              "219 INCLUDEs that are not ONFLY's to edit")

    # --- the job the terminal starts ---------------------------------
    region = "\n".join(mvsicom.deck())
    for dd, why in (("ONFRDR", "the internal reader: CLOSE submits"),
                    ("ONFJCL", "the skeleton the subsystem rewrites"),
                    ("ONFXRSP", "the response the BUZZ half reads")):
        check("the region allocates %s" % dd, dd in region, why)
    check("the region's DDs are added to the procedure's step",
          region.count("//ICOM.") == 3
          and "//ICOM     EXEC" in region,
          "the shipped procedure needs no change")

    try:
        skel = mvsicom.skeleton()
    except Exception as exc:
        skel = None
        sys.stdout.write("  skip skeleton unavailable: %s\n" % exc)
    if skel:
        marker = [c for c in skel if c.startswith("*ONFCARD")]
        check("the skeleton carries exactly one marker card",
              len(marker) == 1,
              "%d marker(s) in %d cards" % (len(marker), len(skel)))
        check("the marker is a COMMENT card",
              marker and marker[0].startswith("*"),
              "unreplaced, it yields no requests rather than a wrong one")
        j = "\n".join(skel)
        check("the job reads the INSTALLED network, not the reader",
              "//ONFNET   DD DSN=" in j and "//ONFNET   DD UNIT=" not in j,
              "an internal reader carries JCL and nothing else")
        check("the job does not scratch the datasets the region holds",
              "SCRATCH  EXEC" not in j,
              "deleting them would strand the region's allocation")
        check("the job is FR-BAT-01's three steps",
              all(("//STEP%d " % n) in j for n in (1, 2, 3)),
              "STEP1 driver, STEP2 engine, STEP3 report")

    # --- the subsystem's reply address -------------------------------
    cbl = os.path.join(mvsicom.LOCAL, "onflytx.cbl")
    if os.path.isfile(cbl):
        text = open(cbl, encoding="ascii", errors="replace").read()
        # Code only: comment lines carry an asterisk in column 7, and
        # everything before the ENVIRONMENT DIVISION is the REMARKS
        # paragraph, which names the dialect rules in order to say it
        # obeys them.  Matching those words there failed the check and
        # would have taught the next reader to delete it.
        after = text.split("ENVIRONMENT DIVISION.", 1)[-1]
        body = "\n".join(l for l in after.splitlines()
                         if l[6:7] != "*")
        check("the reply is addressed to the output utility",
              "MOVE 'U' TO OMSGH-RSC." in body
              and "MOVE LOW-VALUES TO OMSGH-RSC." not in body,
              "X'00E4' is the full-message output code; clearing it "
              "gives INVALID SUB CODE ... RSC=0000")
        for banned, why in (("END-IF", "C-03: no scope terminators"),
                            ("COMP-5", "C-03: no COMP-5")):
            check("subsystem stays in the MVT dialect: no %s" % banned,
                  banned not in body.upper(), why)
    else:
        sys.stdout.write("  skip local/onflytx/onflytx.cbl is not on "
                         "this host (D-132); reply address not checked\n")

    # --- the unattended end-to-end check -----------------------------
    # tools/mvstx.py needs TK5 to do anything, but what it ASSERTS can
    # be judged here: the request it types, the comparand it uses, and
    # that it refuses to assert against a request Section 8.4 does not
    # define.  A check that quietly compared a 100 ms run against a
    # 1000 ms golden value would pass for the wrong reason.
    check("the default request is G-16 (D-430)",
          (mvstx.RATE, mvstx.MS, mvstx.SEED) == (40, 1000, 1),
          "rate %d, %d ms, seed %d" % (mvstx.RATE, mvstx.MS, mvstx.SEED))
    want, gid = mvstx.golden_for(mvstx.RATE, mvstx.MS, mvstx.SEED)
    check("its comparand is Section 8.4's published value",
          (want, gid) == (goldfp.SREXT[40], goldfp.SREXT_ID[40]),
          "%s %s" % (gid, want))
    check("a non-golden request is reported, not asserted",
          mvstx.golden_for(40, 100, 1) == (None, None)
          and mvstx.golden_for(40, 1000, 7) == (None, None),
          "the five srext requests differ only in rate")
    check("the typed command is the fixed-column form",
          mvstx.command_text(40, 1000, 1) == "SUGR,0040,1000,000000001",
          mvstx.command_text(40, 1000, 1))
    fp_line = ("ONF420I SUGR     RATE=  40 MS=1000 SEED=        1 "
               "RC=   0 FP=BAF81D91")
    m = mvstx.FP_RE.search(fp_line)
    check("the fingerprint is read off the screen",
          m is not None and m.group(1) == "BAF81D91")
    pos = mvstx.ROW_RE.search(
        "READOUT  1 ID=        9 LAT-US=     25800  SPIKES=  27 HZ=  27.0")
    neg = mvstx.ROW_RE.search(
        "READOUT  2 ID=       88 LAT-US=         1- SPIKES=   0 HZ=   0.0")
    check("a readout row parses, with and without a trailing sign",
          pos is not None and neg is not None
          and pos.group(5) == "27" and neg.group(4) == "-",
          "a latency of -1 means the neuron never fired (FR-SIM-05)")

    sys.stdout.write("run_ic3270: %d passed, %d failed\n"
                     % (PASS[0], FAIL[0]))
    return 1 if FAIL[0] else 0


if __name__ == "__main__":
    sys.exit(main())
