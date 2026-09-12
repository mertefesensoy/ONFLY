# -*- coding: utf-8 -*-
"""Drive a TSO session over a scripted 3270 (Gate G2, IND$FILE).

VL-54 established the two prerequisites: IND$FILE is in TK5's batch
search order, and tools/tn3270.py reaches VTAM's `Logon ===>` prompt.
IND$FILE runs *under TSO*, so a session has to be logged on before a
transfer can be attempted.

WHY THIS READS BEFORE IT TYPES
------------------------------
The first version sent a fixed list of actions in one go and failed in
a way worth recording.  The screen sequence is not fixed: one run
needed an Enter to get past Hercules' device banner and another was
already at VTAM, where an empty Enter answers `INPUT NOT RECOGNIZED`.
That one difference put every later keystroke a screen out of step,
so the user id was typed before TSO asked for one and the PASSWORD
then landed in the user id field -- `IKJ56420I USERID CUL8TR NOT
AUTHORIZED TO USE TSO`, which reads like a credentials problem and was
nothing of the kind.

So this drives ws3270 through its script port instead, one action at a
time, looking at the screen between each.  `until()` waits for the text
a step actually expects rather than for "some output", which is what
makes a wrong screen a named failure instead of a silent
desynchronisation.

WHAT IT DOES NOT DO
-------------------
It does not transfer anything.  Reaching TSO READY is a prerequisite
worth confirming on its own: everything after depends on it, and
confirming it separately is what makes a later transfer failure
attributable to the transfer.

usage:
    python tools/tso3270.py [--user U] [--pass P] [--keep]
"""
import os
import socket
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

CANDIDATES = (
    r"C:\Program Files\wc3270\ws3270.exe",
    r"C:\Program Files (x86)\wc3270\ws3270.exe",
)

HOST = "127.0.0.1"
PORT = 3270
MODEL = "3279-2"
SCRIPTPORT = 4017

USER = "HERC01"
PASSWORD = "CUL8TR"
TSOAPPL = "TSO"


def find_ws3270():
    for path in CANDIDATES:
        if os.path.isfile(path):
            return path
    return None


class Session(object):
    """A live ws3270 driven over its script port.

    subprocess pipes cannot do this: the whole point is to read the
    screen and then decide what to type, and a pipe fed from one
    buffer cannot interleave.  The script port is ws3270's own answer
    to that.
    """

    def __init__(self, port=SCRIPTPORT):
        exe = find_ws3270()
        if exe is None:
            raise RuntimeError("ws3270.exe not found")
        self.proc = subprocess.Popen(
            [exe, "-model", MODEL, "-scriptport", str(port)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.sock = None
        deadline = time.time() + 15
        while time.time() < deadline:
            try:
                self.sock = socket.create_connection(("127.0.0.1",
                                                      port), 2)
                break
            except OSError:
                time.sleep(0.3)
        if self.sock is None:
            self.close()
            raise RuntimeError("could not reach the ws3270 script port")
        self.buf = b""

    def do(self, action, timeout=20):
        """Send one action; return (status, data lines)."""
        self.sock.sendall((action + "\n").encode("ascii"))
        lines = []
        deadline = time.time() + timeout
        while time.time() < deadline:
            while b"\n" in self.buf:
                raw, self.buf = self.buf.split(b"\n", 1)
                text = raw.decode("latin-1").rstrip("\r")
                if text.startswith("data: "):
                    lines.append(text[6:])
                elif text in ("ok", "error"):
                    return text, lines
            chunk = self.sock.recv(65536)
            if not chunk:
                break
            self.buf += chunk
        return "timeout", lines

    def screen(self):
        _st, lines = self.do("Ascii()")
        return "\n".join(lines)

    def until(self, text, tries=20, delay=0.6):
        """Wait for `text` to appear on the screen.

        Returns the screen when it does, or None.  Waiting for the
        specific text a step expects is the whole difference between a
        named failure and a silent desynchronisation.
        """
        for _ in range(tries):
            s = self.screen()
            if text in s:
                return s
            time.sleep(delay)
        return None

    def logoff(self):
        """Log TSO off before dropping the connection.

        Dropping a 3270 session does NOT log TSO off: the user stays
        signed on and the next attempt is refused with `IKJ56425I
        LOGON REJECTED, USERID ... IN USE`.  That is almost certainly
        what VL-54 recorded as transient blank screens, since a stale
        session leaves the LU in a state a fresh connection lands in
        and cannot use.

        Leaving one behind on a lab a parallel session shares is not
        acceptable, so this is called from close() on every path,
        including failures.
        """
        try:
            # LOGOFF is a TSO command and ISPF does not accept it, so
            # a session sitting in ISPF must be walked out first.  The
            # first version typed LOGOFF at the ISPF option line, which
            # did nothing and left the user signed on -- so the very
            # next attempt was refused IKJ56425I and the failure looked
            # like a credentials problem again.
            for _ in range(8):
                cur = self.screen()
                if "READY" in cur:
                    break
                if "Option  ===>" in cur or "OPTION  ===>" in cur:
                    self.do("String(X)", timeout=5)
                elif "***" in cur:
                    pass
                else:
                    self.do("String(X)", timeout=5)
                self.do("Enter()", timeout=5)
                time.sleep(0.5)
            self.do("String(LOGOFF)", timeout=5)
            self.do("Enter()", timeout=5)
            time.sleep(1.5)
        except Exception:
            pass

    def close(self):
        try:
            if self.sock is not None:
                self.logoff()
                self.do("Quit()", timeout=3)
                self.sock.close()
        except Exception:
            pass
        try:
            self.proc.terminate()
        except Exception:
            pass


def show(title, screen, keep=14):
    print("  --- %s ---" % title)
    if screen is None:
        print("      (not reached)")
        return
    lines = [l.rstrip() for l in screen.splitlines() if l.strip()]
    for l in lines[:keep]:
        print("      %s" % l[:94])


def logon(user=USER, password=PASSWORD, keep=False):
    s = Session()
    try:
        s.do("Connect(%s:%d)" % (HOST, PORT))
        s.do("Wait(10,3270Mode)")

        # Hercules' device banner may or may not need clearing; an
        # empty Enter at VTAM answers INPUT NOT RECOGNIZED, so look
        # first and only press Enter if the prompt is not there yet.
        scr = s.screen()
        if "Logon ===>" not in scr:
            s.do("Enter()")
            scr = s.until("Logon ===>")
        show("VTAM", scr)
        if scr is None:
            print("\ntso3270: never reached VTAM's Logon prompt")
            return False

        s.do("String(%s)" % TSOAPPL)
        s.do("Enter()")
        scr = s.until("ENTER USERID")
        show("TSO asks for a user id", scr)
        if scr is None:
            print("\ntso3270: TSO did not ask for a user id")
            return False

        s.do("String(%s)" % user)
        s.do("Enter()")
        # TSO puts up its own panel next; the password prompt is what
        # matters and its wording differs between systems, so accept
        # either the explicit prompt or the logon panel.
        scr = s.until("PASSWORD", tries=15)
        if scr is None:
            scr = s.screen()
        show("after the user id", scr)

        s.do("String(%s)" % password)
        s.do("Enter()")

        # TSO shows a welcome panel and holds it with `***`, its
        # "press Enter to continue" marker.  READY is one keystroke
        # past that, and up to a few panels can queue up behind each
        # other, so clear them until READY appears rather than
        # assuming a fixed number.
        # TK5's logon proc is ISPLOGON, so a successful logon lands in
        # ISPF, not at a bare READY prompt -- there is no READY text to
        # wait for.  IND$FILE needs a TSO command environment, so ISPF
        # has to be left: `X` on the option line exits one panel, and
        # the primary menu exits to READY.
        #
        # `***` is TSO's "press Enter to continue" on the welcome
        # panels before ISPF appears, and several can queue up, so both
        # cases are handled in one loop rather than assuming an order
        # or a count.
        scr = None
        for _ in range(10):
            scr = s.until("READY", tries=4)
            if scr is not None:
                break
            cur = s.screen()
            if "***" in cur:
                s.do("Enter()")
            elif "Option  ===>" in cur or "OPTION  ===>" in cur:
                s.do("String(X)")
                s.do("Enter()")
            else:
                time.sleep(0.6)
        if scr is None:
            scr = s.screen()
            show("final", scr)
            print("\ntso3270: did NOT reach READY -- the screen above "
                  "is what it actually saw")
            return False
        show("logged on", scr)
        print("\ntso3270: reached TSO READY as %s" % user)
        return True
    finally:
        if not keep:
            s.close()


def send(local, dsname, user=USER, password=PASSWORD):
    """Log on, send one file with IND$FILE, log off (D-148).

    `Transfer()` is ws3270's IND$FILE client: it issues the host
    command and runs the protocol itself, so the session must be at a
    TSO READY prompt when it is called.

    Mode=binary is the whole point for IR-TRN-01 -- the ASCII mode
    would translate the code page, which is the first thing the
    requirement forbids.  The host dataset is allocated fixed 80-byte
    records to match IR-NET-08 and what tests/tstxfr.c expects to read
    back.
    """
    s = Session()
    try:
        if not _reach_ready(s, user, password):
            return False
        dsn = "'%s.%s'" % (user, dsname)
        action = ("Transfer(Direction=send,HostFile=%s,LocalFile=%s,"
                  "Host=tso,Mode=binary,Exist=replace,Recfm=fixed,"
                  "Lrecl=80,BlockSize=80,AllocationUnit=tracks,"
                  "PrimarySpace=10,SecondarySpace=5)"
                  % (dsn, local.replace("\\", "/")))
        print("  sending %s -> %s" % (local, dsn))
        status, lines = s.do(action, timeout=300)
        for l in lines[:8]:
            print("      %s" % l[:94])
        scr = s.screen()
        show("after the transfer", scr, keep=8)
        ok = status == "ok"
        print()
        print("tso3270: IND$FILE transfer %s"
              % ("reported success" if ok else "FAILED (%s)" % status))
        return ok
    finally:
        s.close()


def _reach_ready(s, user, password):
    """The logon sequence, factored out so send() can reuse it."""
    s.do("Connect(%s:%d)" % (HOST, PORT))
    s.do("Wait(10,3270Mode)")
    scr = s.screen()
    if "Logon ===>" not in scr:
        s.do("Enter()")
        scr = s.until("Logon ===>")
    if scr is None:
        print("tso3270: never reached VTAM's Logon prompt")
        return False
    s.do("String(%s)" % TSOAPPL)
    s.do("Enter()")
    if s.until("ENTER USERID") is None:
        print("tso3270: TSO did not ask for a user id")
        return False
    s.do("String(%s)" % user)
    s.do("Enter()")
    s.until("PASSWORD", tries=15)
    s.do("String(%s)" % password)
    s.do("Enter()")
    for _ in range(10):
        if s.until("READY", tries=4) is not None:
            return True
        cur = s.screen()
        if "***" in cur:
            s.do("Enter()")
        elif "Option  ===>" in cur or "OPTION  ===>" in cur:
            s.do("String(X)")
            s.do("Enter()")
        else:
            time.sleep(0.6)
    show("final", s.screen())
    print("tso3270: did NOT reach READY")
    return False


def main(argv):
    try:
        sys.stdout.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass

    user, password = USER, PASSWORD
    local, dsname = None, "ONFTST"
    for i, a in enumerate(argv):
        if a == "--user" and i + 1 < len(argv):
            user = argv[i + 1]
        if a == "--pass" and i + 1 < len(argv):
            password = argv[i + 1]
        if a == "--send" and i + 1 < len(argv):
            local = argv[i + 1]
        if a == "--as" and i + 1 < len(argv):
            dsname = argv[i + 1]

    try:
        if local is not None:
            return 0 if send(local, dsname, user, password) else 1
        return 0 if logon(user, password, "--keep" in argv) else 1
    except RuntimeError as exc:
        sys.stderr.write("tso3270: %s\n" % exc)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
