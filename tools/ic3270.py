# -*- coding: utf-8 -*-
"""Drive a 3270 session on TK5 interactively, and capture every screen.

WHY THIS EXISTS, GIVEN tools/tn3270.py ALREADY DRIVES A 3270
------------------------------------------------------------
`tools/tn3270.py` answers TBD-17: it proves a 3270 client is installed
and reaches VTAM's `Logon ===>`.  It does that by writing a whole
action script to `ws3270`'s stdin at once and reading the result after
the process exits.  That is the right shape for a one-shot measurement
and the wrong shape for Phase G's transaction flow.

D-426 made the transaction two entries: `SUGR` starts a real engine run
and `BUZZ` shows the result once ONFLYENG has written it.  Between them
is a batch job that VL-104 measured at 169 s of TK5 CPU.  A fixed script
cannot wait for that, because what it is waiting for is a condition
Python evaluates -- a response record whose request echo matches what
was typed -- not a 3270 event `ws3270` knows about.

So this module keeps the emulator ALIVE and talks to it turn by turn.
The session becomes an object with a screen you can read, type into,
and read again, which is also what lets slice 5 assert on a fingerprint
instead of a human reading one off a window.

THE SCRIPTING PROTOCOL, WHICH IS NOT OBVIOUS FROM THE MAN PAGE
--------------------------------------------------------------
`ws3270` in script mode reads one action per line on stdin and answers
with, in order:

    data: <text>          zero or more, the action's output
    <status line>         twelve blank-separated fields
    ok                    or `error`

Nothing else terminates an answer, so the reader blocks on `ok`/`error`
and never guesses at a sleep.  That is the whole protocol and it is why
this works at all.

INHERITED FROM tn3270.py, AND STILL TRUE
----------------------------------------
Passing the host on the command line hangs: `ws3270` connects but never
reads stdin.  `Connect(host:port)` issued as the first ACTION works.
That cost a round of debugging once already and is not rediscovered
here.

WHAT THIS DOES NOT DO
---------------------
It knows nothing about ONFLY, nothing about any transaction monitor,
and nothing about what the screens mean.  It connects, types, presses
keys and returns text.  Reading a response off a screen belongs to the
caller.

usage:  python tools/ic3270.py [--host H] [--port P] [--device NNN]
                               [--applid NAME] [--send TEXT]...
                               [--settle SEC] [--release] [--quiet]

        --device NNN   which Hercules 3270 to land on (default 0C1;
                       see the note below -- 0C0 belongs to TSO)
        --applid NAME  log on to that VTAM application after connecting
        --send TEXT    send TEXT as a command and show the screen;
                       repeatable, in order.  A trailing comma is added
                       if there is none -- see Session.command
        --settle SEC   seconds to let the host paint after each Enter
                       (default 2); the host is also waited on with
                       Wait(Output), this is the belt to that's braces
        --release      send the release verb before disconnecting
"""
import os
import subprocess
import sys
import tempfile
import time

# Installed by the wc3270 package.  ws3270 is the scriptable build;
# wc3270.exe is the windowed one and cannot be driven this way.
CANDIDATES = (
    r"C:\Program Files\wc3270\ws3270.exe",
    r"C:\Program Files (x86)\wc3270\ws3270.exe",
    r"C:\Program Files\wc3270\s3270.exe",
    "/usr/bin/s3270",
    "/usr/local/bin/s3270",
)

DEFAULT_HOST = "127.0.0.1"
# tk5.cnf: CNSLPORT ${CNSLPORT:=3270}.  The local 3270 devices at
# 00C0..00C6 are VTAM's; 03C0.. are TCAM's.
DEFAULT_PORT = 3270
MODEL = "3279-2"
SETTLE = 2

# CHOOSING WHICH DEVICE TO LAND ON, WHICH IS NOT OPTIONAL HERE.
#
# A plain connection to the reader port takes the first device
# Hercules has free, which is 00C0 -- and on TK5, VTAM has already
# given 00C0 to TSO: `D NET,ID=CUU0C0,E` answers `ALLOC TO= TSO0001`.
# Every logon typed there is read by TSO's LOGON command processor,
# which answers `IKJ56710I INVALID USERID`, and no amount of getting
# the syntax right will reach any other application.  Measured on
# 2026-09-17; it cost most of an afternoon before the display command
# was run.
#
# 00C1 through 00C6 answer `ALLOC TO= NETSOL`, the network solicitor,
# and those are the ones a session can log on from.  A device is
# chosen by giving its number as the LU name in front of the host,
# `0C1@127.0.0.1:3270`, which Hercules honours.  The `L:` prefix form
# -- the documented way to suppress TN3270E -- is refused by the
# emulator here and must not be used.
DEFAULT_DEVICE = "0C1"

# A sentinel distinct from None, so that log=None can mean silence.
_SAY = object()


class NoClient(Exception):
    pass


class ActionFailed(Exception):
    pass


def find_ws3270():
    for path in CANDIDATES:
        if os.path.isfile(path):
            return path
    return None


class Session(object):
    """A live 3270 session.  Use as a context manager.

    Contract: `open()` starts the emulator and connects; every action
    goes through `do()`, which raises ActionFailed rather than
    returning a value nobody checks; `close()` always quits the
    emulator, including on an exception, so a TK5 3270 device is never
    left occupied by a crashed script.

    Side effect: occupies one of TK5's local 3270 devices between
    open() and close().  No state on the guest changes unless the
    caller types something that changes it.
    """

    # `log=None` SILENCES the session; it does not mean "use the
    # default".  The two were the same thing once, and `--quiet`
    # printed anyway.
    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT,
                 model=MODEL, settle=SETTLE, log=_SAY,
                 device=DEFAULT_DEVICE):
        self.host = host
        self.device = device
        self.port = port
        self.model = model
        self.settle = settle
        self.proc = None
        self.errfile = None
        self.log = sys.stdout if log is _SAY else log
        self.screens = []

    def _stderr_tail(self, limit=300):
        """Whatever the emulator complained about, for a message."""
        if self.errfile is None:
            return ""
        try:
            with open(self.errfile.name, "r", errors="replace") as fh:
                text = fh.read().strip()
        except OSError:
            return ""
        return (" [ws3270 stderr: %s]" % text[-limit:]) if text else ""

    # -- plumbing ---------------------------------------------------

    def _say(self, text):
        if self.log is not None:
            self.log.write("ic3270: %s\n" % text)
            self.log.flush()

    def do(self, action, quiet=False):
        """Issue one action; return its `data:` lines as a list."""
        if self.proc is None:
            raise ActionFailed("session is not open")
        self.proc.stdin.write(action + "\n")
        self.proc.stdin.flush()
        data = []
        while True:
            line = self.proc.stdout.readline()
            if line == "":
                raise ActionFailed(
                    "%s: the emulator exited without answering%s"
                    % (action, self._stderr_tail()))
            line = line.rstrip("\r\n")
            if line == "ok":
                return data
            if line == "error":
                raise ActionFailed("%s: the emulator answered error%s"
                                   % (action,
                                      (": " + " / ".join(data)) if data
                                      else ""))
            if line.startswith("data: "):
                data.append(line[6:])
            # anything else is the status line; it is not output

    def open(self):
        exe = find_ws3270()
        if exe is None:
            raise NoClient(
                "ws3270 not found. Install wc3270 from "
                "https://x3270.miraheze.org/wiki/Wc3270 . Looked in: %s"
                % ", ".join(CANDIDATES))
        # stderr GOES TO A FILE, NOT TO A PIPE.  A pipe nobody reads
        # fills, and when it fills the emulator blocks inside write()
        # -- so the next action's `ok` never arrives and the driver
        # hangs on readline with no diagnosis at all.  Measured on
        # 2026-09-17: a probe sat for two minutes and produced nothing
        # until the process was killed.  It cannot be merged into
        # stdout either, because stdout carries the protocol and one
        # stray warning line would be read as an action's answer.  A
        # file has no buffer to fill, and it keeps the text for the
        # failure message below, which DEVNULL would throw away.
        self.errfile = tempfile.NamedTemporaryFile(
            prefix="ic3270-", suffix=".err", delete=False)
        self.proc = subprocess.Popen(
            [exe, "-model", self.model],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=self.errfile, universal_newlines=True, bufsize=1)
        # Connect as an ACTION, never as a command-line argument.
        spec = "%s:%d" % (self.host, self.port)
        if self.device:
            spec = "%s@%s" % (self.device, spec)
        self.do("Connect(%s)" % spec)
        self.do("Wait(10,3270Mode)")
        self._say("connected to %s as a %s" % (spec, self.model))
        return self

    def close(self):
        if self.proc is None:
            return
        try:
            self.do("Disconnect")
        except Exception:
            pass
        try:
            self.proc.stdin.write("Quit()\n")
            self.proc.stdin.flush()
        except Exception:
            pass
        try:
            self.proc.wait(timeout=10)
        except Exception:
            self.proc.kill()
        self.proc = None
        if self.errfile is not None:
            try:
                self.errfile.close()
                os.unlink(self.errfile.name)
            except OSError:
                pass
            self.errfile = None
        self._say("session closed; the 3270 device is released")

    def __enter__(self):
        return self.open()

    def __exit__(self, *exc):
        self.close()
        return False

    # -- using the terminal -----------------------------------------

    def screen(self, label=None):
        """The 24x80 screen as a list of stripped lines."""
        rows = [r.rstrip() for r in self.do("Ascii()")]
        self.screens.append((label or "", rows))
        return rows

    def enter(self, settle=None):
        self.do("Enter")
        try:
            self.do("Wait(10,Output)")
        except ActionFailed:
            # No output within the timeout is a legitimate outcome: a
            # screen that is already painted does not repaint.  The
            # settle below still runs, and the caller reads the screen
            # and decides.  Swallowing this is deliberate; raising
            # would turn "nothing changed" into a failure.
            pass
        time.sleep(self.settle if settle is None else settle)

    def send(self, text, settle=None):
        """Type a line and press Enter."""
        self.do('String("%s")' % text.replace('\\', '\\\\')
                                     .replace('"', '\\"'))
        self.enter(settle=settle)

    def clear(self):
        self.do("Clear")
        time.sleep(self.settle)

    def command(self, text, settle=None):
        """Send one transaction-monitor command and return the screen.

        THE COMMA IS NOT PUNCTUATION, IT IS THE DELIMITER.  A verb
        typed on its own is not recognised: `VTST` is answered `NO
        VERB FOUND IN PREVIOUS MSG STARTING VTST`, and so is every
        other verb, including ones the same monitor accepts from the
        MVS console.  With a trailing comma the identical text is
        routed -- `VTST,` reaches the status subsystem and `SNBK,TEXT`
        is echoed back.  Measured on 2026-09-17 after the wrong
        conclusion had already been drawn twice, that the terminal was
        not defined to the monitor.

        The evidence that settles it is in the monitor's own network
        definition, where every canned program-function-key command is
        written with the verb comma-terminated: `RLSE,`, `PAGE,N,1`,
        `COMM,STATUS,ALL`.

        So this helper appends the comma when the caller has not, and
        callers stop having to remember.
        """
        if "," not in text:
            text = text + ","
        self.clear()
        self.send(text, settle=settle)
        return self.screen(text)

    def to_vtam(self, tries=3, settle=None):
        """Reach VTAM's `Logon ===>` prompt, however the device starts.

        MEASURED, NOT ASSUMED.  `tools/tn3270.py` presses Enter exactly
        once, because on a device freshly attached to the session that
        is what moves Hercules' own banner on to VTAM's USSMSG screen.
        But the device is one of TK5's local 3270s and it keeps
        whatever the last session left on it: connect to one that is
        already showing the logon screen, press Enter blindly, and
        VTAM answers `INPUT NOT RECOGNIZED` to the empty command.
        Measured on 2026-09-17, the first time this module ran.

        So the prompt is a condition to reach, not a number of Enters
        to press: read first, press only if it is not there yet.
        """
        for _ in range(tries):
            rows = self.screen("reach-vtam")
            if any("Logon ===>" in r for r in rows):
                return rows
            self.clear()
        rows = self.screen("reach-vtam")
        return rows if any("Logon ===>" in r for r in rows) else None

    def logon(self, applid, settle=None):
        """Reach VTAM and log on to one application.

        `APPLID=name`, NOT `APPLID(name)`.  The parenthesised form is
        what every modern reference gives and it does not work here:
        TK5's logon screen passes it to TSO, whose LOGON command
        processor answers `IKJ56710I INVALID USERID,
        APPLID(INTERCOM)`.  With an equals sign the same screen starts
        the session.  Measured on 2026-09-17.
        """
        before = self.to_vtam(settle=settle)
        if before is None:
            # The LU keeps its session across a TCP disconnect, so a
            # second run finds itself already logged on.  That is not
            # a failure; say so and hand back the screen as it is.
            self._say("already in session; no logon prompt to answer")
            return None, self.screen("already-in-session")
        self.send("LOGON APPLID=%s" % applid, settle=settle)
        after = self.screen("after-logon")
        self._say("logon applid=%s sent" % applid)
        return before, after

    def release(self, settle=None):
        """Hand the terminal back to VTAM, leaving the lab as found.

        The monitor's own network definition maps the CLEAR key to
        `RLSE,`, so that is its release verb.  Without it the logical
        unit stays allocated to the application after the emulator
        disconnects -- `D NET,ID=CUU0C1,E` still answers `ALLOC TO=
        INTERCOM` -- and the next run has no logon to perform.
        """
        try:
            rows = self.command("RLSE", settle=settle)
            self._say("terminal released")
            return rows
        except ActionFailed as exc:
            self._say("release failed: %s" % exc)
            return None


def show(rows, title="", out=None):
    out = out or sys.stdout
    if title:
        out.write("---- %s ----\n" % title)
    for r in rows:
        if r.strip():
            out.write("  %s\n" % r)
    out.write("\n")


def main(argv):
    host, port, applid, settle = DEFAULT_HOST, DEFAULT_PORT, None, SETTLE
    device = DEFAULT_DEVICE
    sends, quiet, rel = [], False, False
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--host":
            i += 1
            host = argv[i]
        elif a == "--port":
            i += 1
            port = int(argv[i])
        elif a == "--device":
            i += 1
            device = argv[i]
        elif a == "--applid":
            i += 1
            applid = argv[i]
        elif a == "--send":
            i += 1
            sends.append(argv[i])
        elif a == "--settle":
            i += 1
            settle = int(argv[i])
        elif a == "--release":
            rel = True
        elif a == "--quiet":
            quiet = True
        else:
            sys.stderr.write("ic3270: unknown argument %s\n" % a)
            return 2
        i += 1

    try:
        with Session(host, port, settle=settle, device=device,
                     log=None if quiet else sys.stdout) as s:
            if applid:
                before, after = s.logon(applid)
                if before is not None:
                    show(before, "VTAM prompt")
                show(after, "after LOGON APPLID=%s" % applid)
            else:
                rows = s.to_vtam()
                show(rows if rows else s.screen("host"), "screen")
            for text in sends:
                show(s.command(text), 'after "%s"' % text)
            if rel:
                show(s.release() or [], "after RLSE,")
    except NoClient as exc:
        sys.stderr.write("ic3270: %s\n" % exc)
        return 2
    except ActionFailed as exc:
        sys.stderr.write("ic3270: %s\n" % exc)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
