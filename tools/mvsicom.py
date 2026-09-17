# -*- coding: utf-8 -*-
"""Bring TK5's transaction region up and down, and see what it did.

WHY A TOOL AND NOT A NOTE
-------------------------
Phase G's second component (D-424, plan P-30 approved by D-428) shows
ONFLY's transaction flow on a real 3270.  The monitor that drives that
3270 is the one D-131 chose, and it runs as a long-lived MVS job: it
starts, it holds the region, it answers an operator reply, and it shuts
down.  None of that fits `tools/mvsub.py`, whose whole contract is
"submit a deck and wait for the END banner" -- here the END banner is
the thing we are trying NOT to reach until the demonstration is over.

So this module drives the region's lifecycle instead: submit without
waiting, watch the system log for the messages that mean it is ready,
and shut it down by replying to its operator message.  VL-32 measured
every one of those messages on 2026-09-11; what was not measured, and
is the whole point of slice 1, is whether a 3270 can log on to it.

D-132 AND WHAT IS NOT IN THIS FILE
----------------------------------
The repository is MIT and the monitor's licence is non-commercial-only
including derivative works (VL-38), so D-132 keeps everything derived
from it out of the tree: the subsystem, its verb entry, its driver and
its JCL live under `local/` and on TK5.  This file holds none of that.
It names datasets and messages, which is description and not
derivation, and `tools/lint_lic.py` checks that the line has not been
crossed.

THE CONSOLE PATH, MEASURED
--------------------------
Hercules' HTTP console at :8038 takes a command and returns the log.
A command prefixed with `/` is passed to the guest as an MVS operator
command -- measured on 2026-09-17, `/d t` answered `IEE136I LOCAL:
TIME=...`.  That is how the region is shut down, because its shutdown
is an operator reply and nothing else can issue one on this host.

usage:  python tools/mvsicom.py --backup    save what will be replaced
        python tools/mvsicom.py --install   table sources into SYMUSR
        python tools/mvsicom.py --build     assemble, compile, relink
        python tools/mvsicom.py --start [--timeout SEC]
        python tools/mvsicom.py --status
        python tools/mvsicom.py --stop
        python tools/mvsicom.py --restore   undo: shipped members back
        python tools/mvsicom.py --log [--lines N]
"""
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import mvsub                                          # noqa: E402
import mvsbld                                         # noqa: E402

try:
    from urllib.request import urlopen
    from urllib.parse import quote
except ImportError:                                       # Python 2
    from urllib2 import urlopen                           # noqa: F401
    from urllib import quote                              # noqa: F401

# The job that runs the region.  Named so that it is unmistakably
# ONFLY's own submission and not the shipped one, which is a member of
# a dataset this repository does not own.
JOBNAME = "ONFICOM"
PROC = "ICOMEXEC"
REGION = "8192K"           # the 8M ceiling TBD-14 measured
JOBCLASS = "C"             # the class the shipped run job uses

# --- the installation's libraries ----------------------------------
# Named, not copied.  Naming a dataset is description; D-132 is about
# derivation, and tools/lint_lic.py draws the line mechanically.
SYMREL = "INT.SYMREL"      # release source, read only
SYMUSR = "INT.SYMUSR"      # user source -- ASMPCL searches it FIRST
SYMINCL = "INT.SYMINCL"    # the core's link-edit control statements
MODUSR = "INT.MODUSR"      # user load modules; the core lives here too
ASMPROC = "ASMPCL"         # assemble + link one module
LKEDPROC = "LKEDP"         # link-edit the core
CORE = "ICOMCR"            # the region's core load module
LINKDECK = "ILINKCR"       # its INCLUDE deck, 219 statements
# The shipped procedure's XREF,LIST,LET,OVLY,NCAL, with only the
# sizes raised -- see build_deck.
CORE_PARM = "XREF,LIST,LET,OVLY,NCAL,SIZE=(512K,64K)"
CORE_REGION = "1024K"

# ONFLY's own names.
SUBSYS = "ONFLYTX"         # the subsystem load module and source member
BACKUP_DSN = "HERC01.ONFLY.ICOMBKUP"   # D-432, on a work volume
BACKUP_MEMBERS = (CORE, "BTVRBTB", "INTSCT")

# The members ONFLY copies from the release library into the user
# library before changing anything.  The first two are appended to;
# the last two are copied unchanged, because ASMPCL reads its SYSIN
# from the USER library and would otherwise not find them at all.
REPRO_MEMBERS = ("USRBTVRB", "USRSCTS", "BTVRBTB", "INTSCT")

# Where the material D-132 keeps out of this repository lives.
LOCAL = os.path.join(os.path.dirname(HERE), "local", "onflytx")


class MissingLocal(Exception):
    pass


def local_cards(name):
    """Read one card image file out of local/onflytx.

    D-132 puts the subsystem, its verb entry and its subsystem entry
    under an ignored directory, so a fresh clone does not have them
    and this raises rather than inventing something.  The message says
    what is missing and why it is not in the tree, because "file not
    found" on its own would send the reader looking for a bug.
    """
    path = os.path.join(LOCAL, name)
    if not os.path.isfile(path):
        raise MissingLocal(
            "%s is not here.  D-132 keeps the transaction subsystem and "
            "its table entries out of this MIT repository -- they live "
            "under local/onflytx, which .gitignore excludes in full.  "
            "See local/onflytx/README.txt on a host that has them."
            % path)
    with open(path, "r", encoding="ascii", errors="strict") as fh:
        cards = fh.read().splitlines()
    over = [c for c in cards if len(c) > 80]
    if over:
        raise MissingLocal(
            "%s has %d card(s) past column 80; the TK5 reader truncates "
            "silently (D-93)" % (path, len(over)))
    return cards

# What the region says when it is up.  All four were measured at VL-32.
READY = "INTERCOMM IS READY"
STARTING = re.compile(r"INTMI007I")
VTAM_UP = re.compile(r"INTVT001I")
SUBTASKS = re.compile(r"INTTS001I")

# The reply that closes it down cleanly (VL-32).
SHUTDOWN = "NRCD"

# MVS asks for a reply with a two-digit identifier; `d r,r` lists the
# outstanding ones.  The region's is the one naming this job.
REPLY_RE = re.compile(r"^\s*(\d+)\s+(.*)$")


def console(command, lines=200):
    """Issue one Hercules console command; return the syslog text."""
    host, port = mvsub.console_addr()
    url = ("http://%s:%d/cgi-bin/tasks/syslog?command=%s&msgcount=%d"
           % (host, port, quote(command), lines))
    body = urlopen(url, timeout=30).read().decode("latin-1")
    return re.sub(r"<[^>]+>", "", body)


def mvs(command, lines=200, settle=4.0):
    """Issue one MVS operator command through Hercules' `/` prefix.

    THE TIMING, WHICH COST A ROUND OF DEBUGGING.  The console page
    returns the log as it stands when the request is served, which is
    before MVS has answered the command just issued.  Reading that
    reply means issuing, waiting, and reading AGAIN -- a caller that
    trusts the first body sees the PREVIOUS command's output and
    concludes the current one produced nothing.  Measured on
    2026-09-17 against `d r`.
    """
    console("/" + command, lines=lines)
    if settle:
        time.sleep(settle)
    return console("", lines=lines)


def log(lines=200):
    return console("", lines=lines)


#: The JOB statement's programmer-name field holds twenty characters.
#: Twenty-one is not a warning: MVS answers `IEF642I EXCESSIVE
#: PARAMETER LENGTH ON THE JOB STATEMENT` and the job does not run at
#: all -- `IEF452I JOB NOT RUN - JCL ERROR`.  Measured 2026-09-17 on a
#: title reading "ONFLY TX BACKUP CHECK".  The title is a comment, so
#: it is trimmed here rather than raising; what must not happen is a
#: lab run lost to a caption.
TITLE_MAX = 20


# TK5's local 3270s.  00C0 is TSO's from startup; the rest begin with
# the network solicitor and are the ones a session can log on from.
DEVICES = ("0C1", "0C2", "0C3", "0C4", "0C5", "0C6")
FREE_OWNERS = ("NETSOL",)


def free_device(want=None):
    """A 3270 device that is free to log on, asked of VTAM.

    Returns the device number, or None if every one is taken.

    WHY THIS IS NOT A CONSTANT.  A logical unit stays allocated to
    whatever last held it.  A logon that fails -- because the
    application's network half was not open yet, say -- falls through
    to TSO, and TSO then keeps the unit: measured 2026-09-17, `D
    NET,ID=CUU0C1,E` answered `ALLOC TO= TSO0002` afterwards and every
    later run on that device was answered by TSO's logon processor.
    Choosing by state instead of by number makes one bad run cost one
    device rather than every run after it.
    """
    for dev in ([want] if want else []) + list(DEVICES):
        if dev is None:
            continue
        owner = lu_owner("CUU%s" % dev)
        if owner in FREE_OWNERS:
            return dev
    return None


def job_card(name, title):
    title = title[:TITLE_MAX]
    return ["//%-8s JOB (001),'%s',CLASS=A,MSGCLASS=A," % (name, title),
            "//             USER=%s,PASSWORD=CUL8TR," % mvsbld.USER,
            "//             REGION=8M,TIME=1440,MSGLEVEL=(1,1)",
            "//*"]


def copy_deck(jobname, src, dst, members, allocate):
    """IEBCOPY `members` from one library to another.

    `allocate` is true for the direction that may have to create the
    target.  DISP=(MOD,CATLG) on a partitioned dataset allocates on
    the first run and reuses afterwards, so --backup is re-runnable
    without a separate allocate step that would fail the second time.
    DCB is modelled on the source library rather than restated: the
    core is a load module and getting RECFM wrong would produce a
    backup that cannot be restored, which is the one failure a backup
    must not have.
    """
    d = job_card(jobname, "ONFLY TX BACKUP")
    a = d.append
    a("//COPY     EXEC PGM=IEBCOPY")
    a("//SYSPRINT DD SYSOUT=*")
    a("//SYSUT3   DD UNIT=SYSDA,SPACE=(TRK,(10,10))")
    a("//SYSUT4   DD UNIT=SYSDA,SPACE=(TRK,(10,10))")
    a("//IN       DD DSN=%s,DISP=SHR" % src)
    if allocate:
        a("//OUT      DD DSN=%s,DISP=(MOD,CATLG)," % dst)
        a("//            UNIT=SYSDA,SPACE=(CYL,(10,5,20)),")
        a("//            DCB=%s" % src)
    else:
        a("//OUT      DD DSN=%s,DISP=SHR" % dst)
    a("//SYSIN    DD *")
    a("  COPY OUTDD=OUT,INDD=IN")
    a("  SELECT MEMBER=(%s)" % ",".join(members))
    a("/*")
    return d


def backup_deck():
    """D-427 and D-432: save what is about to be replaced."""
    return copy_deck("ONFICBK", MODUSR, BACKUP_DSN, BACKUP_MEMBERS, True)


def restore_deck():
    """Put the shipped members back, exactly as found."""
    return copy_deck("ONFICRS", BACKUP_DSN, MODUSR, BACKUP_MEMBERS, False)


def install_deck():
    """Put ONFLY's table entries into the user source library.

    Two steps, and the order matters.

    The first copies four members from the RELEASE library into the
    USER library.  Two of them -- the user verb member and the user
    subsystem member -- are the ones ONFLY appends to; copying them
    fresh each time is what makes this whole command idempotent, and
    it is also why no line of the shipped content is ever written down
    off the mainframe (D-132).  The other two are the table sources
    themselves, copied unchanged, because the assembly procedure reads
    its input from the USER library and would otherwise not find them.

    The second appends ONFLY's own records, which carry sequence
    numbers above the shipped ones so that the update inserts rather
    than replaces.  Those records are the ones that name the
    installation's macros, so they come from local/onflytx and not
    from this file.
    """
    d = job_card("ONFICIN", "ONFLY TX INSTALL")
    a = d.append
    a("//REPRO    EXEC PGM=IEBUPDTE")
    a("//SYSPRINT DD SYSOUT=*")
    a("//SYSUT1   DD DSN=%s,DISP=SHR" % SYMREL)
    a("//SYSUT2   DD DSN=%s,DISP=OLD" % SYMUSR)
    a("//SYSIN    DD *")
    for m in REPRO_MEMBERS:
        a("./ REPRO NAME=%s" % m)
    a("./ ENDUP")
    a("/*")
    a("//*")
    a("//ADDONF   EXEC PGM=IEBUPDTE,PARM=MOD,COND=(4,LT,REPRO)")
    a("//SYSPRINT DD SYSOUT=*")
    a("//SYSUT1   DD DSN=%s,DISP=OLD" % SYMUSR)
    a("//SYSUT2   DD DSN=%s,DISP=OLD" % SYMUSR)
    a("//SYSIN    DD *")
    d.extend(local_cards("usrbtvrb.upd"))
    d.extend(local_cards("usrscts.upd"))
    a("./ ENDUP")
    a("/*")
    return d


def build_deck(parm="LOAD,SUPMAP,SIZE=2048K,BUF=1024K,LIB"):
    """Assemble the two tables, compile the subsystem, relink the core.

    WHY THE SUBSYSTEM SOURCE IS INLINE AND NOT A LIBRARY MEMBER.  It
    would have to be added the first time and replaced afterwards, and
    a command that behaves differently on its second run is a command
    that will be run twice by someone who then reads a confusing
    failure.  The compiler reads a card stream perfectly well.

    WHY THE SUBSYSTEM IS LINKED WITH NCAL.  The assembly procedure
    links every other module of this system that way, leaving the
    runtime to be resolved when the core is linked -- where the COBOL
    runtime library is on SYSLIB, which is how the generation
    jobstream itself links the core.  Resolving it twice would put
    duplicate control sections into the core.

    WHY THE CORE'S CONTROL STATEMENTS ARE CONCATENATED, NOT EDITED.
    The shipped deck is 219 INCLUDE statements and is not ONFLY's to
    rewrite; one extra card after it adds ONFLY's subsystem and leaves
    the original untouched, so a restore needs no undo (D-431).
    """
    d = job_card("ONFICBD", "ONFLY TX BUILD")
    a = d.append
    a("//*  the two tables ONFLY's entries were added to")
    a("//ASMVRB   EXEC %s,P='INT',Q=USR,NAME=BTVRBTB,LMOD=BTVRBTB"
      % ASMPROC)
    a("//ASMSCT   EXEC %s,P='INT',Q=USR,NAME=INTSCT,LMOD=INTSCT"
      % ASMPROC)
    a("//*")
    a("//*  the subsystem itself")
    a("//COB      EXEC PGM=IKFCBL00,")
    a("//            PARM='%s'" % parm)
    a("//SYSPRINT DD SYSOUT=*")
    a("//SYSPUNCH DD DUMMY")
    for n in range(1, 5):
        a("//SYSUT%d   DD UNIT=SYSDA,SPACE=(460,(700,100))" % n)
    a("//SYSLIN   DD DSN=&&LOADSET,DISP=(MOD,PASS),UNIT=SYSDA,")
    a("//            SPACE=(80,(500,100))")
    a("//SYSLIB   DD DSN=%s,DISP=SHR" % SYMREL)
    a("//SYSIN    DD DATA,DLM='@@'")
    d.extend(local_cards("onflytx.cbl"))
    a("@@")
    a("//*")
    a("//LKSUB    EXEC PGM=IEWL,PARM='LIST,XREF,LET,NCAL',")
    a("//            COND=(5,LT,COB)")
    a("//SYSLIN   DD DSN=&&LOADSET,DISP=(OLD,DELETE)")
    a("//SYSLMOD  DD DSN=%s(%s),DISP=SHR" % (MODUSR, SUBSYS))
    a("//SYSLIB   DD DSN=SYS1.COBLIB,DISP=SHR")
    a("//SYSUT1   DD UNIT=SYSDA,SPACE=(1024,(50,20))")
    a("//SYSPRINT DD SYSOUT=*")
    a("//*")
    a("//*  the core, relinked so the new tables and subsystem are in")
    a("//CORE     EXEC %s,P='INT',Q=USR,LMOD=%s," % (LKEDPROC, CORE))
    # WHY THE SIZE AND REGION ARE OVERRIDDEN.  The shipped procedure
    # asks the linkage editor for SIZE=(190K,20K) in a 200K region,
    # which is enough for the 219 modules the generation jobstream
    # links and not enough for 220.  Measured 2026-09-17: adding one
    # subsystem ended the step at `IEW0664 ERROR - SIZE VALUE
    # SPECIFIED NOT LARGE ENOUGH FOR TABLE REQUIREMENTS - LINKAGE
    # EDITOR PROCESSING TERMINATED`, COND CODE 0016, with no module
    # written.  Only the sizes are changed; the option list is
    # otherwise the shipped one, so the core is linked the way its own
    # generation links it.
    a("//            PARM.LKED='%s'," % CORE_PARM)
    a("//            REGION.LKED=%s" % CORE_REGION)
    a("//LKED.SYSLIB  DD")
    a("//             DD")
    a("//             DD")
    a("//             DD")
    a("//             DD  DSN=SYS1.COBLIB,DISP=SHR")
    # SYSLIN, NOT SYSIN.  The shipped procedure writes
    # `SYSLIN DD DDNAME=SYSIN`, and on MVS 3.8j that indirection
    # carries only the FIRST dataset of a concatenation: measured
    # 2026-09-17, an extra `INCLUDE SYSLIB(ONFLYTX)` card supplied
    # under SYSIN was never read, the link listing still showed
    # `ONFLYTX $UNRESOLVED`, and the step ended COND CODE 0008 with
    # nothing to say it had ignored the card.  Overriding SYSLIN
    # replaces the indirection with the real concatenation.
    a("//LKED.SYSLIN  DD  DSN=%s(%s),DISP=SHR" % (SYMINCL, LINKDECK))
    a("//             DD  *")
    a("  INCLUDE SYSLIB(%s)" % SUBSYS)
    a("/*")
    return d


def lu_owner(lu):
    """Which VTAM application currently holds a logical unit.

    Returns the name from `IST082I ... ALLOC TO= name`, or None.
    This is how a terminal's state is checked rather than inferred:
    TK5 gives 00C0 to TSO at startup and leaves 00C1..00C6 with the
    network solicitor, and after a session the unit stays with the
    application until the region ends.  A display changes nothing.
    """
    text = mvs("d net,id=%s,e" % lu, lines=40)
    found = None
    for m in re.finditer(r"ALLOC TO=\s*(\S+)", text):
        found = m.group(1)
    return found


def deck():
    """The region job.

    It EXECs the shipped procedure rather than restating it, so that
    nothing about the monitor's own JCL is copied into this repository
    (D-132).  Later slices add `//ICOM.xxx DD` overrides here for
    ONFLY's own datasets; the procedure reserves a place for them and
    needs no change.
    """
    return ["//%s  JOB (001),'ONFLY TX REGION',CLASS=%s,MSGCLASS=X,"
            % (JOBNAME, JOBCLASS),
            "//             USER=%s,PASSWORD=CUL8TR," % mvsbld.USER,
            "//             MSGLEVEL=(1,1)",
            "//*",
            "//ICOM     EXEC %s,IREGSIZ=%s" % (PROC, REGION)]


def running():
    """True if the region job is executing, asked of JES2 itself.

    THIS USED TO READ THE LOG AND IT WAS WRONG.  Scanning the last few
    hundred console messages for a start banner without a matching end
    banner fails the moment either scrolls out of the window, and it
    failed silently: on 2026-09-17 it answered "not running" for a
    region that was up, so a caller skipped its shutdown and started a
    second one.  `$DA` asks JES2 what is executing now and cannot go
    stale.
    """
    # A short settle: this is polled in a loop, and four seconds an
    # iteration made a 120 s shutdown window expire on a region that
    # had in fact ended (measured 2026-09-17, "still running 120 s
    # after the reply" printed beside a logical unit already handed
    # back to the network solicitor).
    text = mvs("$da", lines=80, settle=2.0)
    return bool(re.search(r"\$HASP000 %s\s+EXECUTING" % JOBNAME, text))


def job_numbers():
    """The job numbers the log shows this job starting under."""
    return set(re.findall(r"JOB\s+(\d+)\s+\$HASP373 %s\b" % JOBNAME,
                          log(400)))


def reply_id(timeout=40):
    """The identifier of the region's outstanding operator message.

    Returns the digits as a string, or None.  `d r` is a display and
    changes nothing, so it is safe to poll.

    MVS 3.8j, NOT z/OS.  `D R,R` -- the spelling a modern reference
    gives -- is answered `IEE305I D COMMAND INVALID` here.  `D R`
    answers `IEE110I ... PENDING REQUEST` with a `SUMMARY: n REPLY ID`
    list.  Measured on 2026-09-17.

    The identifier is read from the region's OWN message rather than
    from that summary whenever it can be: the summary is just numbers,
    so with two outstanding requests it cannot say which is the
    region's, and replying to the wrong one would answer some other
    address space's question.  The summary is used only when exactly
    one request is outstanding, where it cannot be ambiguous.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        text = mvs("d r", lines=80)
        # The region re-issues its message with a fresh identifier
        # after every reply, prefixed `@nn`.
        found = None
        for m in re.finditer(r"@(\d+)\s+INTVT\d+R\s+%s\b" % JOBNAME, text):
            found = m.group(1)
        if found:
            return found
        m = re.search(r"SUMMARY:\s+1 REPLY ID\s*\n\s*/?\s*(\d+)", text)
        if m:
            return m.group(1)
        time.sleep(3)
    return None


def start(timeout=240, poll=3.0):
    """Submit the region and wait until it says it is ready.

    Returns True once the ready message appears.  Prints what it saw,
    because a region that comes up half way -- the monitor started but
    its terminal front end not -- is a real outcome and the log lines
    are the only evidence of which half failed.
    """
    if running():
        sys.stdout.write("mvsicom: %s is already running\n" % JOBNAME)
        return True
    cards = deck()
    # THE READY MESSAGE IS MATCHED AGAINST THIS RUN'S JOB NUMBER, NOT
    # AGAINST THE LOG AS A WHOLE.  The log is cumulative and every
    # earlier start left its own "INTERCOMM IS READY" in it, so a
    # plain substring search returns at once and the caller logs a
    # terminal on to an application whose network half has not opened
    # yet.  Measured 2026-09-17: the answer was `APPLICATION IS
    # INACTIVE`, three seconds before `INTVT001I VTAM STARTUP
    # COMPLETED`, and the terminal was then taken by TSO.
    before = job_numbers()
    sys.stdout.write("mvsicom: submitting %s (%s, REGION=%s)\n"
                     % (JOBNAME, PROC, REGION))
    mvsub.submit(cards)
    deadline = time.time() + timeout
    seen, jobno = {}, None
    while time.time() < deadline:
        text = log(400)
        if jobno is None:
            fresh = job_numbers() - before
            if fresh:
                jobno = sorted(fresh)[-1]
                sys.stdout.write("mvsicom: %s is JOB %s\n"
                                 % (JOBNAME, jobno))
        if jobno is not None:
            mine = [l for l in text.splitlines()
                    if re.search(r"JOB\s+%s\b" % jobno, l)]
            joined = "\n".join(mine)
            for name, pat in (("starting", STARTING), ("vtam", VTAM_UP),
                              ("subtasks", SUBTASKS)):
                if name not in seen:
                    for l in mine:
                        if pat.search(l):
                            seen[name] = l.strip()
                            sys.stdout.write("mvsicom: %s\n"
                                             % l.strip()[:100])
                            break
            if READY in joined:
                sys.stdout.write("mvsicom: %s\n" % READY)
                return True
        time.sleep(poll)
    sys.stdout.write("mvsicom: not ready within %d s; saw %d of 3 "
                     "startup messages\n" % (timeout, len(seen)))
    return False


def stop(timeout=300, poll=4.0):
    """Reply to the region's operator message so it closes cleanly."""
    if not running():
        sys.stdout.write("mvsicom: %s is not running\n" % JOBNAME)
        return True
    rid = reply_id()
    if rid is None:
        sys.stdout.write("mvsicom: no outstanding reply found for %s; "
                         "refusing to guess an identifier\n" % JOBNAME)
        return False
    sys.stdout.write("mvsicom: replying %s,%s\n" % (rid, SHUTDOWN))
    mvs("r %s,%s" % (rid, SHUTDOWN))
    deadline = time.time() + timeout
    while time.time() < deadline:
        if not running():
            sys.stdout.write("mvsicom: %s ended\n" % JOBNAME)
            return True
        time.sleep(poll)
    sys.stdout.write("mvsicom: %s still running %d s after the reply\n"
                     % (JOBNAME, timeout))
    return False


def submit_and_report(deck, jobname, what, timeout=900):
    """Run one deck and print the lines a reader actually wants."""
    over = [c for c in deck if len(c) > 80]
    if over:
        sys.stdout.write("mvsicom: %d card(s) past column 80; refusing "
                         "to submit (D-93)\n" % len(over))
        return False
    sys.stdout.write("mvsicom: %s -- %s, %d cards\n"
                     % (what, jobname, len(deck)))
    out = mvsub.run(deck, jobname, timeout=timeout)
    if out is None:
        sys.stdout.write("mvsicom: %s did not finish in %d s\n"
                         % (jobname, timeout))
        return False
    worst = 0
    for line in mvsub.summarise(out):
        sys.stdout.write("  %s\n" % line[:112])
        m = re.search(r"COND CODE (\d+)", line)
        if m:
            worst = max(worst, int(m.group(1)))
    sys.stdout.write("mvsicom: %s worst COND CODE %04d\n"
                     % (jobname, worst))
    return worst <= 4


def main(argv):
    action, lines, timeout = None, 40, 240
    i = 0
    while i < len(argv):
        a = argv[i]
        if a in ("--start", "--stop", "--status", "--log",
                 "--backup", "--restore", "--install", "--build"):
            action = a
        elif a == "--lines":
            i += 1
            lines = int(argv[i])
        elif a == "--timeout":
            i += 1
            timeout = int(argv[i])
        else:
            sys.stderr.write("mvsicom: unknown argument %s\n" % a)
            return 2
        i += 1
    if action is None:
        sys.stderr.write(__doc__.split("usage:")[-1])
        return 2
    jobs = {"--backup": (backup_deck, "ONFICBK", "saving the shipped "
                         "members before anything replaces them"),
            "--restore": (restore_deck, "ONFICRS", "putting the shipped "
                          "members back"),
            "--install": (install_deck, "ONFICIN", "table sources into "
                          "the user library"),
            "--build": (build_deck, "ONFICBD", "assemble, compile, "
                        "relink the core")}
    if action in jobs:
        maker, jobname, what = jobs[action]
        if running():
            sys.stdout.write(
                "mvsicom: %s is RUNNING; it holds the libraries this "
                "would write.  Stop it first with --stop.\n" % JOBNAME)
            return 1
        try:
            deck = maker()
        except MissingLocal as exc:
            sys.stderr.write("mvsicom: %s\n" % exc)
            return 2
        return 0 if submit_and_report(deck, jobname, what) else 1
    if action == "--start":
        return 0 if start(timeout=timeout) else 1
    if action == "--stop":
        return 0 if stop() else 1
    if action == "--status":
        sys.stdout.write("mvsicom: %s is %s\n"
                         % (JOBNAME,
                            "RUNNING" if running() else "not running"))
        return 0
    for line in log(lines).splitlines():
        if line.strip():
            sys.stdout.write("%s\n" % line.rstrip()[:118])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
