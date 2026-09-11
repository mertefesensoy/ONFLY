# -*- coding: utf-8 -*-
"""Drive the Raincode probes in tests/raincode (D-129).

VL-36 established, by reading the installer's File table, that the free
Raincode edition ships cobrc.exe, the QIX terminal and processing
servers, and the BMS toolchain.  That is an inventory: it shows the parts
exist, not that they work.  This turns it into a measurement.

Three steps, in the order tests/raincode/README.md argues for, because
each adds exactly one unknown:

  --inventory   find the installation and confirm what is actually on
                disk, rather than what the installer claimed
  --compile     compile probe 1 (ONFCENG then ONFCLNK) and report
  --howrun      read the installed samples to work out how a CICS
                program is actually started, instead of guessing

WHY --howrun EXISTS
-------------------
Raincode's Getting Started says CICS statements "translate to calls to
the legacy program execution context" and that context "must be
initialized in QIX mode" -- set by a .NET host, not by the COBOL.  The
package ships a worked example of exactly that, `qix_factory`, with
Program.cs, CustomLink.cs, CustomSend.cs and CustomReceive.cs.  Reading
those is how the run step gets answered from evidence rather than from a
guess at a command line, which is the failure D-92 is on record for.

usage:  python tools/rcprobe.py [--rcbin DIR] [--inventory] [--compile]
                                [--howrun]
        with no step given, all three run in that order.
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROBES = os.path.join(ROOT, "tests", "raincode")
COPYBOOKS = os.path.join(ROOT, "generated")

# Looked for in this order.  RCBIN is what Raincode's own documentation
# calls the binary directory.
CANDIDATES = [
    os.environ.get("RCBIN", ""),
    r"C:\Program Files\Raincode\Crossbow",
    r"C:\Program Files\Raincode",
    r"C:\Program Files (x86)\Raincode\Crossbow",
    r"C:\Raincode",
]

# (filename, what its absence would mean)
WANTED = [
    ("cobrc.exe", "the COBOL compiler - nothing can be built without it"),
    ("rclrun.exe", "the runner"),
    ("QIX.TerminalServerRunner.exe", "the TN3270 terminal server (D-127)"),
    ("QIX.ProcessingServerRunner.exe", "transactional processing"),
    ("QIX.Cmd.exe", "the QIX command tool"),
    ("rcbms.exe", "the BMS map compiler (probe 3)"),
]


def find_install(explicit):
    """Locate the Raincode binaries.  Searches, never assumes."""
    roots = [explicit] if explicit else CANDIDATES
    for root in roots:
        if not root or not os.path.isdir(root):
            continue
        for dirpath, _dirs, files in os.walk(root):
            if "cobrc.exe" in files:
                return dirpath
    return None


def inventory(rcbin):
    print("=== installation ===")
    print("  %s" % rcbin)
    missing = 0
    for name, why in WANTED:
        path = os.path.join(rcbin, name)
        if os.path.exists(path):
            print("  ok      %-32s %d bytes"
                  % (name, os.path.getsize(path)))
        else:
            # Not fatal on its own: Raincode ships some tools as a .dll
            # run through the dotnet host rather than as an .exe.
            alt = os.path.join(rcbin, name.replace(".exe", ".dll"))
            if os.path.exists(alt):
                print("  ok      %-32s (as .dll)" % name)
            else:
                print("  MISSING %-32s %s" % (name, why))
                missing += 1
    return missing


def compile_probe(rcbin):
    """Compile probe 1.  ONFCENG first: ONFCLNK LINKs to it."""
    cobrc = os.path.join(rcbin, "cobrc.exe")
    print("=== compiling probe 1 ===")
    print("  copybook path: %s" % COPYBOOKS)
    bad = 0
    for src in ("ONFCENG.cbl", "ONFCLNK.cbl"):
        path = os.path.join(PROBES, src)
        # -I is the usual spelling for a copybook path; if Raincode
        # spells it differently the error will say so, and that is a
        # finding about the command line rather than about the COBOL.
        cmd = [cobrc, "-I", COPYBOOKS, path]
        print("  $ %s" % " ".join(cmd))
        try:
            p = subprocess.run(cmd, cwd=PROBES, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, timeout=300)
        except Exception as exc:
            print("     could not run cobrc: %s" % exc)
            return 1
        out = p.stdout.decode("latin-1", "replace")
        for line in out.splitlines()[:25]:
            print("     %s" % line.rstrip()[:110])
        print("     exit %d" % p.returncode)
        if p.returncode != 0:
            bad += 1
    return bad


def howrun(rcbin):
    """Read the shipped QIX sample rather than guessing at a host."""
    print("=== how a CICS program is started (from the samples) ===")
    root = os.path.dirname(rcbin)
    hits = []
    for dirpath, _dirs, files in os.walk(root):
        for f in files:
            if f in ("Program.cs", "CustomLink.cs", "buildbms.ps1") \
                    or f.endswith(".bms"):
                hits.append(os.path.join(dirpath, f))
    if not hits:
        print("  no QIX samples found under %s" % root)
        return 1
    for h in sorted(hits)[:12]:
        print("  %s" % h)
    for h in sorted(hits):
        if h.endswith("Program.cs"):
            print("  --- %s ---" % h)
            try:
                text = open(h, encoding="latin-1").read()
            except Exception:
                continue
            for line in text.splitlines():
                s = line.strip()
                if ("Qix" in s or "ExecutionContext" in s
                        or "Args" in s) and not s.startswith("//"):
                    print("     %s" % s[:104])
            break
    return 0


def main(argv):
    explicit = None
    for i, a in enumerate(argv):
        if a == "--rcbin" and i + 1 < len(argv):
            explicit = argv[i + 1]
    steps = [a for a in argv if a in ("--inventory", "--compile",
                                      "--howrun")]
    if not steps:
        steps = ["--inventory", "--compile", "--howrun"]

    rcbin = find_install(explicit)
    if rcbin is None:
        sys.stderr.write(
            "rcprobe: could not find cobrc.exe.\n"
            "Searched: %s\n"
            "Pass the directory with --rcbin.\n"
            % ", ".join(c for c in CANDIDATES if c))
        return 2

    rc = 0
    if "--inventory" in steps:
        rc |= 1 if inventory(rcbin) else 0
        print()
    if "--compile" in steps:
        rc |= 2 if compile_probe(rcbin) else 0
        print()
    if "--howrun" in steps:
        howrun(rcbin)
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
