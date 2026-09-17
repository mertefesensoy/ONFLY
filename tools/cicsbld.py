# -*- coding: utf-8 -*-
"""Build and verify Phase G's EXEC CICS transaction (P-22, D-394).

The whole chain, in the order each step adds exactly one unknown:

    --cols      check the COBOL against column 72 (see below)
    --dll       the C89 engine as a shared library, 64-bit
    --module    the .NET LINK target
    --tst       tests/tstcics.c, the byte-identity driver
    --bms       ONFCBUZ.bms into a physical and a symbolic map
    --compile   ONFCSUG.cbl and ONFCBUZ.cbl
    --run       tests/run_cics.py

With no step named, all of them run in that order.

SKIPPING, AND WHY IT IS LOUD
----------------------------
D-394 keeps this out of `make test`: a bare checkout has neither Raincode nor
the .NET SDK and must stay buildable, the same rule D-156 set for the
GnuCOBOL proxy.  A missing toolchain therefore prints what was missing and
exits 0.  It names the piece: a skip that does not say what it skipped has
stopped protecting anything, which is the failure D-390 records.

WHY --cols EXISTS
-----------------
cobrc truncates source past column 72 with no diagnostic (VL-37).  A VALUE
literal beginning in column 55 was cut to its first 17 characters and
compiled clean, and the loss surfaced two runs later as short data off a TS
queue.  D-93 holds ONFLY's sources to 80 columns because of the TK5 card
reader; this is a different boundary and a different tool, and it is checked
mechanically because this compiler will not report crossing it.

WHY THE 64-BIT COMPILER IS NOT THE MAKEFILE'S
---------------------------------------------
The Makefile's CC on this host is MinGW 6.3.0, whose -dumpmachine is
`mingw32`.  .NET is 64-bit, and a 32-bit DLL cannot be P/Invoked from it
(VL-117, finding 7).  So this target compiles the DLL with an x86_64 gcc,
found in this order: $ONFCC64, then the msys2 mingw64 gcc, then plain `gcc`
if it reports an x86_64 target.  That is a SECOND compiler over the same
engine sources and it is the price D-395 accepted; what keeps it honest is
that the DLL's answers are compared byte for byte against the batch engine's
in tests/run_cics.py, so a divergence between the two compilers fails the
build rather than hiding in it.

Its own trap: the msys2 gcc exits 1 printing NOTHING at all unless its bin
directory is on PATH, because the driver cannot then load cc1 (VL-117,
finding 8).  This tool puts it there.

usage:  python tools/cicsbld.py <build-dir> [STEP...]
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CICS = os.path.join(ROOT, "cics")
GEN = os.path.join(ROOT, "generated")

# The COBOL the CICS compiler reads.  Both are held to 72 columns.
COBOL = ("ONFCSUG.cbl", "ONFCBUZ.cbl")
COL_LIMIT = 72

# Mirrors the Makefile's ENGREQ plus the native backend, with onfcics.c in
# place of onflyeng.c: same engine, different adapter.
ENGSRC = [
    "engine/src/onfdec.c", "engine/src/onfcrc.c", "engine/src/onffpc.c",
    "engine/src/onffpr.c", "engine/src/onfker.c", "engine/src/onfrnd.c",
    "engine/src/onfstm.c", "engine/src/onfreq.c", "generated/onfcom.c",
    "engine/src/onffpn.c", "softfloat/onfint.c",
]

# The Makefile's CFLAGS, NATFLAGS (x86w) and SFFLAGS, restated here because
# this target is not driven by the Makefile's own rules.  Any change there
# must be mirrored here; run_cics.py is what would catch a drift, by the
# responses ceasing to be byte-identical.
CFLAGS = ["-std=c89", "-pedantic", "-Wall", "-Wextra", "-Werror", "-O2"]
NATFLAGS = ["-msse2", "-mfpmath=sse", "-ffp-contract=off",
            "-DONF_FP_NATIVE", "-DONF_FP_LITTLE"]
SFFLAGS = ["-O2", "-Wall", "-Wno-unused-function",
           "-include", "generated/onf3enm.h"]
INC = ["-Iengine/include", "-Igenerated"]

MSYS64 = r"C:\msys64\mingw64\bin"
RC_VARS = ("RCDIR", "RCBIN")


def machine_env(name):
    """A machine-level environment variable, read where Windows keeps it.

    The Raincode installer sets RCDIR and RCBIN machine-wide and a shell
    started before the install does not have them.  tools/rcprobe.py reads
    them the same way and for the same reason.
    """
    value = os.environ.get(name)
    if value:
        return value
    if os.name != "nt":
        return None
    try:
        import winreg
    except ImportError:
        return None
    path = r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path) as key:
            return winreg.QueryValueEx(key, name)[0]
    except OSError:
        return None


def rc_environment():
    env = dict(os.environ)
    for name in RC_VARS:
        value = machine_env(name)
        if value:
            env[name] = value
    if os.path.isdir(MSYS64) and MSYS64 not in env.get("PATH", ""):
        env["PATH"] = MSYS64 + os.pathsep + env.get("PATH", "")
    return env


def rcbin(env):
    value = env.get("RCBIN")
    if value and os.path.isdir(value):
        return value
    top = env.get("RCDIR")
    if top:
        cand = os.path.join(top, "bin")
        if os.path.isdir(cand):
            return cand
    return None


def gcc64(env):
    """An x86_64 gcc, or None.  See the module docstring."""
    candidates = []
    if env.get("ONFCC64"):
        candidates.append(env["ONFCC64"])
    candidates.append(os.path.join(MSYS64, "gcc.exe"))
    candidates.append("gcc")
    for cc in candidates:
        try:
            proc = subprocess.Popen([cc, "-dumpmachine"], env=env,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT)
            out = proc.communicate()[0].decode("latin-1", "replace").strip()
        except Exception:
            continue
        if proc.returncode == 0 and out.startswith("x86_64"):
            return cc
    return None


def have_dotnet(env):
    try:
        proc = subprocess.Popen(["dotnet", "--version"], env=env,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT)
        out = proc.communicate()[0].decode("latin-1", "replace").strip()
    except Exception:
        return None
    return out if proc.returncode == 0 else None


def safe(text):
    """Printable on this console.

    Tool output can carry bytes that the Windows console code page has no
    character for -- rcbms prints a path through one, and the traceback that
    caused was reported as a build failure that had not happened.  A
    diagnostic that crashes the thing reading it is worse than no
    diagnostic.
    """
    enc = getattr(sys.stdout, "encoding", None) or "ascii"
    return text.encode(enc, "replace").decode(enc, "replace")


def sh(cmd, env, cwd=None, quiet=False):
    if not quiet:
        print("  $ %s" % safe(" ".join(str(c) for c in cmd)))
    proc = subprocess.Popen(cmd, cwd=cwd or ROOT, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    out = proc.communicate()[0].decode("latin-1", "replace")
    if out.strip():
        for line in out.rstrip().splitlines():
            print("    %s" % safe(line))
    return proc.returncode


def step_cols():
    print("=== column %d check (VL-37) ===" % COL_LIMIT)
    bad = 0
    for name in COBOL:
        path = os.path.join(CICS, name)
        with open(path, "r", encoding="utf-8") as handle:
            for n, line in enumerate(handle, start=1):
                text = line.rstrip("\r\n")
                if len(text) > COL_LIMIT:
                    print("  FAIL %s:%d is %d columns" % (name, n, len(text)))
                    bad += 1
    if bad == 0:
        print("  OK   %d sources within %d columns" % (len(COBOL), COL_LIMIT))
    return bad


def step_dll(env, build, cc):
    print("=== the engine as a 64-bit shared library ===")
    obj = os.path.join(build, "onfcics.o")
    dll = os.path.join(build, "onflyeng.dll")
    rc = sh([cc] + CFLAGS + NATFLAGS + INC + ["-Isoftfloat", "-c",
             "-o", obj, "engine/src/onfcics.c"], env)
    if rc != 0:
        return rc
    return sh([cc] + SFFLAGS + NATFLAGS + INC +
              ["-shared", "-o", dll, obj] + ENGSRC, env)


def step_module(env, build):
    print("=== the .NET LINK target ===")
    return sh(["dotnet", "build", os.path.join("cics", "onfcics.csproj"),
               "-v", "q", "--nologo", "-o", os.path.join(build, "net")], env)


def step_tst(env, build, cc):
    print("=== tests/tstcics.c ===")
    exe = os.path.join(build, "tstcics.exe")
    return sh([cc] + SFFLAGS + NATFLAGS + INC + ["-Itests", "-o", exe,
               "tests/tstcics.c", "engine/src/onfcics.c"] + ENGSRC, env)


def step_bms(env, build, bin_dir):
    print("=== the BUZZ mapset ===")
    out = os.path.abspath(os.path.join(build, "bmsout"))
    if not os.path.isdir(out):
        os.makedirs(out)
    return sh([os.path.join(bin_dir, "rcbms.exe"),
               "-Language=cobol",
               "-GenBasedSymbolicMap=true",
               "-CopybooksOutputDirectory=%s" % out,
               "-MapsOutputDirectory=%s" % out,
               os.path.join(CICS, "ONFCBUZ.bms")], env)


def step_compile(env, build, bin_dir):
    print("=== the transactions ===")
    # Absolute: cobrc runs with cwd set to the build directory, so a
    # relative search path would resolve inside it and the symbolic map
    # would be reported as a missing copybook.
    out = os.path.abspath(os.path.join(build, "bmsout"))
    bad = 0
    for name in COBOL:
        rc = sh([os.path.join(bin_dir, "cobrc.exe"),
                 ":IncludeSearchPath=%s;%s" % (out, GEN),
                 ":FatalMissingIncludes=TRUE",
                 ":QIX=TRUE",
                 os.path.join(CICS, name)], env, cwd=build)
        if rc != 0:
            print("  FAIL %s did not compile" % name)
            bad += 1
    return bad


def step_run(env, build):
    print("=== verification (P-22 V3, V4) ===")
    # The module and the DLL must sit where rclrun and the loader look.
    net = os.path.join(build, "net", "onfcics.dll")
    if os.path.exists(net):
        import shutil
        shutil.copy(net, os.path.join(build, "onfcics.dll"))
    # The batch engine lives in the Makefile's own BUILD directory, one
    # level above this target's; `make cics` depends on `eng` to put it
    # there.  It is the comparand for V4 and there is no point running
    # anything without it.
    batch = os.path.join(os.path.dirname(os.path.abspath(build)),
                         "onflyeng_nat.exe")
    if not os.path.exists(batch):
        print("  SKIP no %s; run `make eng` first" % safe(batch))
        return 0
    return sh([sys.executable, os.path.join("tests", "run_cics.py"),
               batch, os.path.join(build, "tstcics.exe"),
               os.path.join(build, "cicsrun")], env)


def main(argv):
    if len(argv) < 2:
        print(__doc__.strip().splitlines()[-1])
        return 2
    build = argv[1]
    steps = argv[2:] or ["--cols", "--dll", "--module", "--tst",
                         "--bms", "--compile", "--run"]
    if not os.path.isdir(build):
        os.makedirs(build)

    env = rc_environment()
    bin_dir = rcbin(env)
    cc = gcc64(env)
    dotnet = have_dotnet(env)

    missing = []
    if bin_dir is None:
        missing.append("Raincode (neither RCBIN nor RCDIR names a directory)")
    if cc is None:
        missing.append("an x86_64 gcc (set ONFCC64, or install msys2 mingw64)")
    if dotnet is None:
        missing.append("the .NET SDK (`dotnet --version` failed)")
    if missing:
        print("cicsbld: SKIP - this host is missing:")
        for item in missing:
            print("  - %s" % item)
        print("cicsbld: D-394 keeps this target out of `make test`, so a "
              "bare checkout skips here and exits 0.")
        return 0

    print("cicsbld: Raincode %s" % bin_dir)
    print("cicsbld: gcc      %s" % cc)
    print("cicsbld: dotnet   %s" % dotnet)

    bad = 0
    if "--cols" in steps:
        bad += step_cols()
    if bad == 0 and "--dll" in steps:
        bad += 1 if step_dll(env, build, cc) else 0
    if bad == 0 and "--module" in steps:
        bad += 1 if step_module(env, build) else 0
    if bad == 0 and "--tst" in steps:
        bad += 1 if step_tst(env, build, cc) else 0
    if bad == 0 and "--bms" in steps:
        bad += 1 if step_bms(env, build, bin_dir) else 0
    if bad == 0 and "--compile" in steps:
        bad += step_compile(env, build, bin_dir)
    if bad == 0 and "--run" in steps:
        bad += 1 if step_run(env, build) else 0

    print("cicsbld: %s" % ("FAILED" if bad else "OK"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
