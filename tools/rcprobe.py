# -*- coding: utf-8 -*-
"""Drive the Raincode probes in tests/raincode (D-129).

VL-36 established, by reading the installer's File table, that the free
Raincode edition ships cobrc.exe, the QIX terminal and processing
servers, and the BMS toolchain.  That is an inventory: it shows the parts
exist, not that they work.  This turns it into a measurement.

Steps, in the order tests/raincode/README.md argues for, because each
adds exactly one unknown:

  --inventory   find the installation and confirm what is actually on
                disk, rather than what the installer claimed
  --cols        check the probe sources against column 72 (see below)
  --bms         assemble ONFCMS.bms into a physical and symbolic map
  --compile     compile all four probe programs and report
  --run         run them under `rclrun -Qix=true` and report
  --howrun      read the installed samples for the C# host recipe

WHY --cols EXISTS
-----------------
cobrc silently truncates source past column 72 with no diagnostic.  A
VALUE literal starting in column 55 was cut to its first 17 characters
and compiled clean; the loss surfaced only as short data coming back off
a TS queue, two runs later (VL-37).  D-93 holds ONFLY's source to 80
columns because of a different tool; this checks the boundary that this
one cares about, mechanically, before the compiler gets a chance to
swallow it.

WHY --howrun EXISTS
-------------------
Raincode's Getting Started says CICS statements "translate to calls to
the legacy program execution context" and that context "must be
initialized in QIX mode" -- set by a .NET host, not by the COBOL.  The
package ships a worked example of exactly that, `qix_factory`, with
Program.cs, CustomLink.cs, CustomSend.cs and CustomReceive.cs.  Reading
those is how the run step was answered from evidence rather than from a
guess at a command line, which is the failure D-92 is on record for.
It turned out `rclrun -Qix=true` reaches the same place with no host to
write, so --run uses that; --howrun is kept because the host route is
the one that survives if a program ever needs a custom QIX factory.

usage:  python tools/rcprobe.py [--rcbin DIR] [STEP...]
        with no step given, all of them run in that order.
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROBES = os.path.join(ROOT, "tests", "raincode")
COPYBOOKS = os.path.join(ROOT, "generated")
# rcbms writes here and cobrc reads it back; generated, never edited,
# and not committed.
BMSOUT = os.path.join(PROBES, "bmsout")

# Compile order matters for the first two: ONFCLNK LINKs to ONFCENG.
# ONFCMAP must follow --bms, since it COPYs the generated symbolic map.
SOURCES = ("ONFCENG.cbl", "ONFCLNK.cbl", "ONFCTRM.cbl", "ONFCMAP.cbl")

# (program, what a clean run would mean).  Probe 1 is expected to pass;
# 2 and 3 are expected to abend INVREQ on this installation (VL-37).
RUNS = (
    ("ONFCLNK", "probe 1: LINK and the 412-byte COMMAREA"),
    ("ONFCTRM", "probe 2: terminal I/O without BMS"),
    ("ONFCMAP", "probe 3: BMS SEND MAP and RECEIVE MAP"),
)

# Variables the Raincode installer sets machine-wide.  cobrc refuses to
# run without RCDIR, with "RCDIR environment variable not set".
RC_VARS = ("RCDIR", "RCBIN", "RCBATCHDIR", "RCTARGET", "RCDIR_NET80")


def machine_env(name):
    """Read a machine-level environment variable from the registry.

    A shell started before the installer ran does not have these, and
    telling someone to reboot to run a test is a poor answer.  Reading
    them where Windows actually keeps them makes the tool work in the
    session that installed the product, which is the session anyone
    will be in the first time.
    """
    try:
        import winreg
    except ImportError:
        return None
    key = (r"SYSTEM\CurrentControlSet\Control\Session Manager"
           r"\Environment")
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key) as k:
            return winreg.QueryValueEx(k, name)[0]
    except OSError:
        return None


def rc_environment():
    """The environment cobrc needs, filled in from the registry."""
    env = dict(os.environ)
    for name in RC_VARS:
        if not env.get(name):
            value = machine_env(name)
            if value:
                env[name] = value
    return env

# Looked for in this order.  RCBIN is what Raincode's own documentation
# calls the binary directory.
CANDIDATES = [
    os.environ.get("RCBIN", ""),
    machine_env("RCBIN") or "",
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


def check_columns(limit=72):
    """Refuse to compile source that runs past the fixed-format margin.

    cobrc will not tell you.  It truncates and carries on, so a literal
    can lose its tail and the program still compiles clean -- which is
    exactly how VL-37's wrong answer was produced.  Cheap to check here,
    expensive to find later.
    """
    print("=== column %d check ===" % limit)
    bad = 0
    for src in sorted(os.listdir(PROBES)):
        if not src.lower().endswith((".cbl", ".bms")):
            continue
        path = os.path.join(PROBES, src)
        with open(path, encoding="latin-1") as fh:
            for n, line in enumerate(fh, 1):
                text = line.rstrip("\n").rstrip("\r")
                if len(text) > limit:
                    print("  OVER    %s:%d  %d columns" % (src, n,
                                                           len(text)))
                    bad += 1
    if not bad:
        print("  ok      every probe source ends by column %d" % limit)
    return bad


def bms(rcbin):
    """Assemble the mapset.  ONFCMAP.cbl COPYs what this produces.

    -GenBasedSymbolicMap is not decoration.  The default writes two
    copybooks, an input one and an output one; IBM's TYPE=DSECT writes
    one, whose output structure REDEFINES its input structure.  ONFCMAP
    says `COPY ONFCMS` once, as a program written for MVS would, so it
    needs the IBM shape.
    """
    print("=== assembling ONFCMS.bms ===")
    cmd = [os.path.join(rcbin, "rcbms.exe"),
           "-Language=cobol",
           "-GenBasedSymbolicMap=true",
           "-CopybooksOutputDirectory=%s" % BMSOUT,
           "-MapsOutputDirectory=%s" % BMSOUT,
           os.path.join(PROBES, "ONFCMS.bms")]
    print("  $ %s" % " ".join(cmd))
    try:
        p = subprocess.run(cmd, cwd=PROBES, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, timeout=300,
                           env=rc_environment())
    except Exception as exc:
        print("     could not run rcbms: %s" % exc)
        return 1
    for line in p.stdout.decode("latin-1", "replace").splitlines()[:15]:
        print("     %s" % line.rstrip()[:110])
    print("     exit %d" % p.returncode)
    return 1 if p.returncode else 0


def compile_probe(rcbin):
    """Compile the probes.  ONFCENG first: ONFCLNK LINKs to it."""
    cobrc = os.path.join(rcbin, "cobrc.exe")
    print("=== compiling ===")
    print("  copybook path: %s" % COPYBOOKS)
    bad = 0
    for src in SOURCES:
        path = os.path.join(PROBES, src)
        # Options read out of cobrc's own help, not guessed:
        #   :IncludeSearchPath  where COPY ONFCOM is looked for.
        #   :CopyBookExtension  already defaults to .cpy, which is what
        #                       generated/ONFCOM.cpy is, so it is left
        #                       alone rather than restated.
        #   :FatalMissingIncludes  off by default, which would let a
        #                       missing copybook pass quietly and then
        #                       fail as a mysterious undefined name.
        #                       This project does not accept silent
        #                       omissions (D-93, D-70).
        #   :QIX                "generate code for QIX, even in the
        #                       absence of any QIX statement".  Set
        #                       explicitly so the probe does not depend
        #                       on the compiler inferring it.
        cmd = [cobrc,
               ":IncludeSearchPath=%s;%s" % (BMSOUT, COPYBOOKS),
               ":FatalMissingIncludes=TRUE",
               ":QIX=TRUE",
               path]
        print("  $ %s" % " ".join(cmd))
        try:
            p = subprocess.run(cmd, cwd=PROBES, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, timeout=300,
                               env=rc_environment())
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


def run_probes(rcbin):
    """Run each probe and report what the runtime actually did.

    A non-zero exit is not automatically a failure of the probe: on this
    installation probes 2 and 3 abend INVREQ "not implemented" because
    the standalone runner holds no terminal facility, and that abend is
    the measurement, not an accident.  So this prints the deciding line
    rather than reducing everything to pass/fail.
    """
    print("=== running under rclrun -Qix=true ===")
    rclrun = os.path.join(rcbin, "rclrun.exe")
    bad = 0
    for prog, what in RUNS:
        print("  --- %s (%s)" % (prog, what))
        cmd = [rclrun, "-Qix=true", prog]
        try:
            p = subprocess.run(cmd, cwd=PROBES, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, timeout=300,
                               input=b"", env=rc_environment())
        except Exception as exc:
            print("     could not run rclrun: %s" % exc)
            bad += 1
            continue
        out = p.stdout.decode("latin-1", "replace")
        shown = 0
        for line in out.splitlines():
            s = line.rstrip()
            # Stack frames are noise; the verdict is in the program's
            # own output and in the abend line.
            if s.startswith("   at ") or s.startswith(" ---> "):
                continue
            # Any ONFC* line is a probe program's own output -- which
            # includes "ONFCENG entered", the line that proves the LINK
            # dispatched rather than the caller answering itself.
            if s.startswith("ONFC") or "not implemented" in s \
                    or "INVREQ" in s or "PASS" in s or "FAIL" in s:
                print("     %s" % s[:120])
                shown += 1
                if shown >= 8:
                    break
        print("     exit %d" % p.returncode)
        if "PASS" not in out and p.returncode != 0:
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
    # Tool output is decoded latin-1, which maps every byte to some
    # character -- including ones the console codepage cannot encode
    # back out.  This repository's own path contains a u-umlaut, and
    # rcbms echoes its arguments, so printing its output raised
    # UnicodeEncodeError before this line existed.  Losing a character
    # from a transcript is acceptable; losing the step is not.
    try:
        sys.stdout.reconfigure(errors="replace")
        sys.stderr.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass

    explicit = None
    for i, a in enumerate(argv):
        if a == "--rcbin" and i + 1 < len(argv):
            explicit = argv[i + 1]
    order = ["--inventory", "--cols", "--bms", "--compile", "--run",
             "--howrun"]
    steps = [a for a in order if a in argv]
    if not steps:
        steps = order

    rcbin = find_install(explicit)
    if rcbin is None:
        sys.stderr.write(
            "rcprobe: could not find cobrc.exe.\n"
            "Searched: %s\n"
            "Pass the directory with --rcbin.\n"
            % ", ".join(c for c in CANDIDATES if c))
        return 2

    if not os.path.isdir(BMSOUT):
        os.makedirs(BMSOUT)

    rc = 0
    if "--inventory" in steps:
        rc |= 1 if inventory(rcbin) else 0
        print()
    if "--cols" in steps:
        rc |= 2 if check_columns() else 0
        print()
    if "--bms" in steps:
        rc |= 4 if bms(rcbin) else 0
        print()
    if "--compile" in steps:
        rc |= 8 if compile_probe(rcbin) else 0
        print()
    if "--run" in steps:
        # Deliberately not folded into rc: on this installation probes
        # 2 and 3 are *expected* to abend, so a non-zero run is the
        # documented outcome rather than a build failure (VL-37).
        run_probes(rcbin)
        print()
    if "--howrun" in steps:
        howrun(rcbin)
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
