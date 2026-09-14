# -*- coding: utf-8 -*-
"""Gate G0 environment inventory (SRS Section 9.1; D-235, D-237, D-238).

WHY THIS EXISTS
---------------
Gate G0 asks "Is every lab platform ready?" and its exit criterion names
four things: TK5 Update 5 running; GCCMVS and JCC inventory recorded;
Linux s390x with gcc under QEMU; x86 Python environment.

Every other gate in Section 9.1 carries a date, a decision number and its
measured evidence.  G0 carried none of the three.  The platforms were in
fact built and used -- Gate G1 compiled on TK5, Phase D built on s390x --
but a gate is closed by a record, not by the fact that later work happened
to succeed.  D-235 is the owner's instruction to close it properly.

WHAT "READY" MEANS HERE (D-238)
-------------------------------
The owner's standard is "present and working", not "present".  So this
tool does not read version strings out of filenames or configuration; it
asks each platform to RUN something and reports what came back:

  x86      a compiler, an interpreter and a build actually execute
  MVS      a job reaches COND CODE 0000 through the real card reader,
           and each C compiler prints its own version from a program
           IT compiled and the machine RAN
  s390x    the guest compiles and runs a probe that reports the byte
           order it observes, rather than the byte order we assume

WHAT THIS TOOL DOES NOT DO
--------------------------
It never starts, stops or reconfigures a lab.  Both labs are outside the
repository (D-89) and belong to the owner; `--mvs` and `--s390x` fail with
an instruction if their platform is not already up.  The one exception is
the codepage, which `tools/mvsub.py` already enforces on every submission
under D-103, and which a Hercules restart silently resets to `default`.

OUTPUT
------
Each section merges into data/g0/inventory.json under its own key, so the
four clauses can be gathered in any order, in one run or four.  Every
entry records the exact command and the raw first lines of its output, so
the JSON is evidence rather than a summary of evidence.

Run:
    python tools/g0.py --x86      [--maketest <log>]
    python tools/g0.py --mvs
    python tools/g0.py --s390x
    python tools/g0.py --report
Exit status 0 when every requested section was gathered, 1 otherwise.
"""
import base64
import io
import json
import os
import platform
import re
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "g0", "inventory.json")

sys.path.insert(0, os.path.join(ROOT, "tools"))
sys.path.insert(0, os.path.join(ROOT, "tests"))


def capture(args, env=None, cwd=None, timeout=300):
    """Run a command and return {command, rc, out}.  Never raises."""
    rec = {"command": " ".join(args)}
    try:
        p = subprocess.Popen(args, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, env=env, cwd=cwd)
        out, _ = p.communicate(timeout=timeout)
        rec["rc"] = p.returncode
        rec["out"] = out.decode("utf-8", "replace").strip()
    except Exception as exc:
        rec["rc"] = None
        rec["out"] = "%s: %s" % (type(exc).__name__, exc)
    return rec


def head(rec, n=4):
    """The first n lines of a captured output, for the printed report."""
    return "\n".join(rec.get("out", "").splitlines()[:n])


def probe_source():
    """The C every platform's compiler must build and its machine run.

    One probe, used by tools/mvsg0.py on MVS and by section_s390x() here,
    so the four clauses of Gate G0 produce directly comparable lines
    rather than four differently-worded answers.  It reports the compiler
    version, the integer widths NR-11 depends on, and the byte order --
    observed by shifting, never by casting a pointer over the bytes,
    which is FR-LOD-05's rule applied to the probe itself.

    C89 with no ONFLY header, and under 80 columns, because the MVS card
    reader truncates past column 80 without saying so (D-93).

    Not built with Python's `%` operator: every printf format below
    contains `%s` and `%d`, which that operator would try to substitute.

    `__VERSION__` is guarded.  It is a GCC macro; JCC is a different
    compiler and need not define it, and an unguarded reference would
    turn "JCC publishes no version macro" into "JCC cannot compile the
    probe", which is a different and much worse answer.
    """
    return [
        "#include <stdio.h>",
        "",
        "int main(void)",
        "{",
        "  unsigned long w;",
        "  unsigned int b0;",
        "  w = 0x01020304UL;",
        "  b0 = (unsigned int)((w >> 24) & 0xFFUL);",
        "#ifdef __VERSION__",
        '  printf("ONFG0 VERSION %s\\n", __VERSION__);',
        "#else",
        '  printf("ONFG0 VERSION (no __VERSION__ macro)\\n");',
        "#endif",
        '  printf("ONFG0 BUILT %s %s\\n", __DATE__, __TIME__);',
        '  printf("ONFG0 STDC %d\\n", (int)__STDC__);',
        '  printf("ONFG0 INTBITS %d\\n", (int)(sizeof(int) * 8));',
        '  printf("ONFG0 LONGBITS %d\\n", (int)(sizeof(long) * 8));',
        '  printf("ONFG0 TOPBYTE %02X\\n", (int)b0);',
        "  return 0;",
        "}",
    ]


# ----------------------------------------------------------------- host


def section_host():
    """Facts NFR-PERF-02 requires of any timing recorded against this box."""
    sec = {"gathered": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "platform": platform.platform(),
           "machine": platform.machine(),
           "processor": platform.processor()}
    if os.name == "nt":
        sec["cpu_name"] = capture(
            ["powershell", "-NoProfile", "-Command",
             "(Get-CimInstance Win32_Processor).Name"])
        sec["memory_gb"] = capture(
            ["powershell", "-NoProfile", "-Command",
             "[math]::Round((Get-CimInstance Win32_ComputerSystem)."
             "TotalPhysicalMemory/1GB,1)"])
    return sec


# ------------------------------------------------------------------ x86


def section_x86(maketest_log=None):
    """Clause 4: the x86 Python environment (prep pipeline, oracle, build).

    The Python packages listed are the ones the prep pipeline and the
    scientific tests actually import, not everything installed: an
    inventory of a site-packages directory would age badly and prove
    nothing about whether the pipeline can run.
    """
    sec = {"tools": {}, "python_packages": {}}
    sec["tools"]["python"] = capture([sys.executable, "--version"])
    sec["tools"]["gcc"] = capture(["gcc", "--version"])
    sec["tools"]["make"] = capture(["mingw32-make", "--version"])
    sec["tools"]["git"] = capture(["git", "--version"])

    try:
        import run_cob
        cobc = run_cob.find_cobc()
        if cobc:
            sec["tools"]["cobc"] = capture([cobc, "--version"],
                                           env=run_cob.cobc_env(cobc))
            sec["tools"]["cobc_path"] = cobc
        else:
            sec["tools"]["cobc"] = {"command": "cobc --version", "rc": None,
                                    "out": "not found (PATH, ONFLY_COBC, "
                                           "MSYS2 hints)"}
    except Exception as exc:
        sec["tools"]["cobc"] = {"command": "cobc --version", "rc": None,
                                "out": "%s: %s" % (type(exc).__name__, exc)}

    for mod in ("zlib", "numpy", "pandas", "pyarrow"):
        code = ("import %s,sys;"
                "sys.stdout.write(getattr(%s,'__version__','(stdlib)'))"
                % (mod, mod))
        rec = capture([sys.executable, "-c", code])
        sec["python_packages"][mod] = (rec["out"] if rec["rc"] == 0
                                       else "ABSENT")

    # brian2 is deliberately NOT in the session interpreter.  It is the
    # Shiu re-run's dependency (SR-CAL-04, D-164) and lives in a separate
    # `.venv` beside the main checkout, because it pulls a large stack
    # that nothing else in the build needs.  Reporting it simply "ABSENT"
    # would be misleading, so the venv is probed where it actually is.
    sec["brian2"] = {}
    for label, base in (("worktree", ROOT),
                        ("main-checkout",
                         os.path.dirname(os.path.dirname(
                             os.path.dirname(ROOT))))):
        exe = os.path.join(base, ".venv", "Scripts", "python.exe")
        if os.path.exists(exe):
            rec = capture([exe, "-c", "import brian2,sys;"
                                      "sys.stdout.write(brian2.__version__)"])
            sec["brian2"][label] = {"python": exe, "version": rec["out"],
                                    "rc": rec["rc"]}
        else:
            sec["brian2"][label] = {"python": exe, "version": "no .venv here"}

    if maketest_log and os.path.exists(maketest_log):
        text = io.open(maketest_log, encoding="utf-8",
                       errors="replace").read()
        lines = text.splitlines()
        sec["maketest"] = {
            "command": "mingw32-make test",
            "log": os.path.basename(maketest_log),
            "lines": len(lines),
            "exit": next((l for l in lines if l.startswith("EXIT=")), None),
            "start": next((l for l in lines if l.startswith("start:")), None),
            "end": next((l for l in lines if l.startswith("end:")), None),
            "tail": "\n".join(lines[-25:]),
        }
    return sec


# ------------------------------------------------------------------ MVS


def hercules_syslog(msgcount=0):
    """The whole Hercules system log, tags stripped.

    The console's default view is the last 22 lines, which is fewer than
    the version banner alone occupies -- reading that view for the
    version recorded `Hercules System Log` as the version string.  This
    asks for the full log instead and lets the caller select.
    """
    from urllib.request import urlopen
    import mvsub
    host, port = mvsub.console_addr()
    url = ("http://%s:%d/cgi-bin/tasks/syslog?msgcount=%d"
           % (host, port, msgcount))
    try:
        body = urlopen(url, timeout=30).read().decode("latin-1")
    except Exception:
        return None
    return re.sub(r"<[^>]+>", "", body)


def hercules_console(command):
    """Issue one Hercules console command and return the syslog text.

    Same mechanism tools/mvsub.py uses for its codepage check: the HTTP
    console on 8038.  Returns None when the console cannot be reached,
    which is how "the lab is not running" arrives here.
    """
    from urllib.request import urlopen
    from urllib.parse import quote
    import mvsub
    host, port = mvsub.console_addr()
    url = ("http://%s:%d/cgi-bin/tasks/syslog?command=%s"
           % (host, port, quote(command)))
    try:
        body = urlopen(url, timeout=15).read().decode("latin-1")
    except Exception:
        return None
    # The console answers with a whole HTML page, form controls and all.
    # Returning that raw put `<title>Hercules</title>` into the gate
    # record where the version string belonged, so the tags come off
    # here rather than at each call site.
    return re.sub(r"<[^>]+>", "", body)


def section_mvs(deck_fn=None, jobname=None, timeout=300):
    """Clauses 1 and 2: TK5 running, and the GCCMVS / JCC inventory.

    `deck_fn` builds the inventory deck; it is a parameter so that the
    caller owns the JCL and this module owns only the gathering.  When it
    is None only the liveness half (clause 1) is gathered.
    """
    import mvsub
    sec = {}
    body = hercules_console("version")
    if body is None:
        sec["error"] = ("the Hercules console at %s:%d did not answer: TK5 "
                        "is not running" % mvsub.console_addr())
        return sec
    log = hercules_syslog() or body
    want = ("HHC01413I", "HHC01414I", "HHC01415I", "HHC01417I ** The SDL",
            "HHC01417I Build type", "HHC01417I Built with",
            "HHC01417I Modes")
    keep = []
    for line in log.splitlines():
        s = line.strip()
        if any(s.startswith(w) for w in want):
            keep.append(s)
    sec["hercules_version"] = "\n".join(dict.fromkeys(keep))
    # What the guest says about ITSELF at IPL: the one in-system
    # statement of which operating system this is.
    sec["mvs_ipl"] = "\n".join(
        s.strip() for s in log.splitlines()
        if "system initialization complete" in s
        or "MVS038J" in s)[-600:]
    sec["codepage"] = mvsub.current_codepage()
    rate = hercules_console("maxrates")
    if rate:
        sec["maxrates"] = "\n".join(
            l.strip() for l in rate.splitlines() if "MIPS" in l)[-2000:]

    if deck_fn is not None:
        cards = deck_fn()
        out = mvsub.run(cards, jobname, timeout=timeout)
        sec["job"] = {"jobname": jobname,
                      "finished": out is not None,
                      "summary": mvsub.summarise(out),
                      "output": out}
    return sec


# ---------------------------------------------------------------- s390x


def section_s390x(distro="Ubuntu", port=2222, key=None, user="onfly",
                  probe=None):
    """Clause 3: Linux s390x with gcc under QEMU (D-215).

    The guest is reached the way Phase D reached it: ssh on a forwarded
    host port, from WSL, using the key that lives beside the image.  The
    probe is compiled and run IN the guest, so what comes back is the
    byte order the platform actually has rather than the one we expect.
    """
    sec = {}
    key = key or "~/onfly-s390x/id_ed25519"
    ssh = ("ssh -i %s -p %d -o StrictHostKeyChecking=no "
           "-o UserKnownHostsFile=/dev/null -o LogLevel=ERROR "
           "%s@127.0.0.1" % (key, port, user))

    def guest(cmd, timeout=300):
        return capture(["wsl.exe", "-d", distro, "--", "bash", "-lc",
                        "%s %s" % (ssh, json_quote(cmd))], timeout=timeout)

    sec["uname"] = guest("uname -a")
    if sec["uname"].get("rc") != 0:
        sec["error"] = ("the s390x guest did not answer on 127.0.0.1:%d "
                        "from WSL %s: it is not booted" % (port, distro))
        return sec
    sec["os_release"] = guest("grep PRETTY /etc/os-release")
    sec["gcc"] = guest("gcc --version | head -1")
    sec["make"] = guest("make --version | head -1")
    sec["python3"] = guest("python3 --version")
    sec["share_9p"] = guest("ls /onfly/Makefile && mount | grep -c onfly")

    # Build and run the same probe MVS builds.  The source travels
    # base64-encoded: it contains quotes, backslashes and percent signs,
    # and it has to survive PowerShell, WSL's bash, ssh and the guest's
    # own shell.  Encoding removes every quoting question at once, which
    # is cheaper than getting four levels of escaping right.
    src = "\n".join(probe or probe_source()) + "\n"
    b64 = base64.b64encode(src.encode("ascii")).decode("ascii")
    cmd = ("printf %s " + b64 + " | base64 -d > /tmp/g0probe.c && "
           "gcc -ansi -pedantic -Wall -o /tmp/g0probe /tmp/g0probe.c && "
           "/tmp/g0probe") % "%s"
    sec["probe"] = guest(cmd, timeout=600)
    sec["probe_lines"] = [l.strip() for l in sec["probe"].get("out", "")
                          .splitlines() if l.strip().startswith("ONFG0 ")]

    # The probe proves the toolchain; this proves the toolchain can build
    # THIS repository on THIS platform, which is what "ready" has to mean
    # for a platform Phase D already depends on.  `units` is chosen as the
    # cheapest target that compiles ONFLY C under -Werror and then runs
    # it: a full `make test` in the guest costs hours under TCG (VL-82).
    # BUILD is guest-local so object writes stay off the 9p share.
    if sec["share_9p"].get("rc") == 0:
        sec["make_units"] = guest(
            "cd /onfly && make ONFPLAT=s390x CC=gcc PYTHON=python3 "
            "BUILD=/tmp/b390g0 units 2>&1 | tail -5", timeout=1800)
    return sec


def json_quote(cmd):
    """Quote a command for the remote shell without a backslash in sight."""
    return "'" + cmd.replace("'", "'\"'\"'") + "'"


# ---------------------------------------------------------------- store


def merge(name, data, path=OUT):
    """Write one section into the inventory, keeping the others."""
    doc = {}
    if os.path.exists(path):
        doc = json.loads(io.open(path, encoding="utf-8").read())
    doc[name] = data
    doc["_generated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    d = os.path.dirname(path)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    io.open(path, "w", encoding="utf-8", newline="\n").write(
        json.dumps(doc, indent=2, sort_keys=True, ensure_ascii=False) + "\n")
    return path


def report(path=OUT):
    """Print the inventory as a person would want to read it."""
    if not os.path.exists(path):
        sys.stdout.write("g0: no inventory at %s\n" % path)
        return 1
    doc = json.loads(io.open(path, encoding="utf-8").read())
    for key in ("host", "x86", "mvs", "s390x"):
        sec = doc.get(key)
        sys.stdout.write("\n== %s ==\n" % key)
        if sec is None:
            sys.stdout.write("   NOT GATHERED\n")
            continue
        if "error" in sec:
            sys.stdout.write("   ERROR: %s\n" % sec["error"])
        for name, val in sorted(sec.items()):
            if name == "error":
                continue
            _line(name, val, 3)
    return 0


def _line(name, val, indent):
    """One report line per entry, recursing one level into plain maps.

    A captured command is printed as rc plus its first line, because that
    is what says whether the thing works; the raw output stays in the
    JSON, where the evidence belongs.
    """
    pad = " " * indent
    if isinstance(val, dict) and "command" in val:
        sys.stdout.write("%s%-14s rc=%s  %s\n"
                         % (pad, name, val.get("rc"), head(val, 1)))
    elif isinstance(val, dict):
        sys.stdout.write("%s%s:\n" % (pad, name))
        for sub, subval in sorted(val.items()):
            _line(sub, subval, indent + 3)
    else:
        first = str(val).splitlines()[:1]
        sys.stdout.write("%s%-14s %s\n" % (pad, name, first[0] if first
                                           else ""))


def main(argv):
    args = argv[1:]
    if not args:
        sys.stderr.write(__doc__.split("Run:")[-1])
        return 2
    maketest = None
    if "--maketest" in args:
        maketest = args[args.index("--maketest") + 1]
    rc = 0
    if "--x86" in args or "--all" in args:
        merge("host", section_host())
        merge("x86", section_x86(maketest))
    if "--mvs" in args or "--all" in args:
        sec = section_mvs()
        # Do not throw away the jobs tools/mvsg0.py recorded: `--mvs`
        # here gathers only the liveness half, and replacing the whole
        # section would silently delete the catalog and the two compiler
        # probes -- the same clobber that bit mvsg0 itself.
        try:
            prev = json.loads(io.open(OUT, encoding="utf-8").read())
            for k in ("jobs", "parsed"):
                if k in prev.get("mvs", {}):
                    sec.setdefault(k, prev["mvs"][k])
        except Exception:
            pass
        merge("mvs", sec)
        rc = rc or (1 if "error" in sec else 0)
    if "--s390x" in args or "--all" in args:
        sec = section_s390x()
        merge("s390x", sec)
        rc = rc or (1 if "error" in sec else 0)
    report()
    sys.stdout.write("\ng0: inventory at %s\n" % OUT)
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv))
