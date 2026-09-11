# -*- coding: utf-8 -*-
"""Drive a 3270 session against TK5 and capture the screen (TBD-17).

WHY THIS EXISTS
---------------
TBD-17 asked for a 3270 client on the development host, because every
MVS interaction so far has gone through the card reader, the printer
and the Hercules console, and D-127's transaction flow cannot be shown
or even driven without a terminal.

wc3270 supplies one.  What makes it worth a tool rather than a note is
that it also ships `ws3270.exe`, the scriptable build: a 3270 session
can be driven and its screen captured without a human watching a
window.  That matters twice over -- it lets TBD-17 close on a
measurement instead of on someone's say-so, and it is how Phase G's
demonstration can be regression-tested rather than merely performed.

THE NON-OBVIOUS PART
--------------------
Passing the host on ws3270's command line hangs: it connects but never
reads stdin, and the script times out with nothing on stdout.  Issuing
`Connect(host:port)` as the first *action* instead works immediately.
That cost a round of debugging and is the kind of fact that is
invisible once it is working, so it is written down here rather than
rediscovered.

WHAT IT DOES NOT DO
-------------------
It does not log on.  Reaching VTAM's `Logon ===>` prompt is the proof
that the terminal path works end to end; consuming a TSO session to go
further would change lab state for no extra evidence.  Driving an
actual transaction is Phase G's job, and needs INTERCOMM running.

usage:  python tools/tn3270.py [--host H] [--port P] [--enter N]
                               [--raw]
        --enter N   press Enter N times before capturing (default 1,
                    which moves Hercules' device banner on to VTAM)
        --raw       keep ws3270's status lines in the output
"""
import os
import subprocess
import sys

# Installed by the wc3270 package.  ws3270 is the scriptable build;
# wc3270.exe is the windowed one and cannot be driven this way.
CANDIDATES = (
    r"C:\Program Files\wc3270\ws3270.exe",
    r"C:\Program Files (x86)\wc3270\ws3270.exe",
    r"C:\Program Files\wc3270\s3270.exe",
)

DEFAULT_HOST = "127.0.0.1"
# tk5.cnf: CNSLPORT ${CNSLPORT:=3270}.  The local 3270 devices at
# 00C0..00C6 are VTAM's; 03C0.. are TCAM's.
DEFAULT_PORT = 3270
MODEL = "3279-2"


def find_ws3270():
    for path in CANDIDATES:
        if os.path.isfile(path):
            return path
    return None


def capture(host, port, enters, raw):
    """Connect, optionally press Enter, return the screen as text.

    Side effect: occupies one of TK5's local 3270 devices for the
    duration, and releases it on Quit.  No state on the guest changes.
    """
    exe = find_ws3270()
    if exe is None:
        sys.stderr.write(
            "tn3270: ws3270.exe not found.  Install wc3270 from\n"
            "        https://x3270.miraheze.org/wiki/Wc3270\n"
            "        Looked in: %s\n" % ", ".join(CANDIDATES))
        return None

    # Connect as an ACTION, not as a command-line argument -- see the
    # module docstring.  Wait(3270Mode) blocks until the host has
    # negotiated 3270 rather than guessing at a sleep.
    actions = ["Connect(%s:%d)" % (host, port), "Wait(10,3270Mode)"]
    for _ in range(enters):
        actions += ["Enter()", "Wait(10,Output)"]
    actions += ["Ascii()", "Quit()"]

    script = ("\n".join(actions) + "\n").encode("ascii")
    try:
        p = subprocess.run([exe, "-model", MODEL], input=script,
                           stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, timeout=120)
    except Exception as exc:
        sys.stderr.write("tn3270: could not run ws3270: %s\n" % exc)
        return None

    out = p.stdout.decode("latin-1", "replace")
    if raw:
        return out
    # ws3270 prefixes screen rows with "data: " and interleaves a
    # status line and an "ok" after every action.  Strip both so what
    # comes back is the screen a person would see.
    rows = []
    for line in out.splitlines():
        if line.startswith("data: "):
            rows.append(line[6:])
        elif line.startswith("U ") or line.startswith("L ") \
                or line.strip() in ("ok", "error"):
            continue
        elif line.strip():
            rows.append(line)
    return "\n".join(rows)


def main(argv):
    host, port, enters, raw = DEFAULT_HOST, DEFAULT_PORT, 1, False
    for i, a in enumerate(argv):
        if a == "--host" and i + 1 < len(argv):
            host = argv[i + 1]
        elif a == "--port" and i + 1 < len(argv):
            port = int(argv[i + 1])
        elif a == "--enter" and i + 1 < len(argv):
            enters = int(argv[i + 1])
        elif a == "--raw":
            raw = True

    screen = capture(host, port, enters, raw)
    if screen is None:
        return 2
    print(screen)
    # "Logon ===>" is VTAM's prompt.  Its presence is what TBD-17
    # actually wanted proved: not that a client is installed, but that
    # it reaches the thing INTERCOMM will run under as a VTAM APPL.
    if "Logon ===>" in screen:
        print()
        print("tn3270: reached VTAM (Logon prompt present)")
        return 0
    print()
    print("tn3270: connected, but no VTAM Logon prompt in the screen")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
