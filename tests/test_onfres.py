# -*- coding: utf-8 -*-
"""The test-result plumbing of P-44's group 1: `tools/onfres.py`,
`tools/lastln.py` and `tools/testrun.py` (D-546, D-548, D-549).

WHY THESE THREE ARE TESTED BEFORE ANYTHING USES THEM

Each one exists because the build used to report less than it knew.

`lastln.py` replaces `prog | tail -1` in four Makefile recipes.  In a
pipeline the recipe's status is tail's, so for the two of those recipes
that `make test` runs, the test program's own exit status never reached
make (P-44 S1).  The property that matters is therefore the status, and it
is pinned here with programs that exit 0 and 3.

`onfres.py` is the one way a check says it did not run.  Before it, 18
files printed skip lines in four spellings (P-44 S4), so no strict mode
could be added in one place.  What is pinned: the line format the runner
counts, that `ONFLY_NOSKIP=1` turns a skip into a failure, that D-548's
exempt checks stay exempt under it, and that every exemption cites a
decision row that really exists in the SRS.

`testrun.py` produces `make test`'s closing line.  Its PASS is a target
whose own sub-make exited 0 having printed no SKIP line (D-549), so what is
pinned is that a failing target stops the run with its status, that a
skipped target is not counted as a PASS, and that a target already made is
passed to later sub-makes with `-o` rather than run twice.

Run:

    python tests/test_onfres.py [MAKE]

MAKE is the make program to drive the runner's end-to-end case with; the
Makefile passes "$(MAKE)".  Without it the end-to-end case is reported
through onfres itself, which is exactly the path it tests.
"""
import io
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "tools"))

import onfres                          # noqa: E402
import testrun                         # noqa: E402

LASTLN = os.path.join(ROOT, "tools", "lastln.py")
SRS = os.path.join(ROOT, "docs", "ONFLY-SRS.md")

ok = bad = 0


def check(label, cond, detail=""):
    global ok, bad
    # The details quote demo marker lines, and `make test`'s runner counts
    # any `ONFRES SKIP ...` it sees, so the first full run through it
    # counted this file's demo skips as real ones.  Break the token in
    # anything printed: "ONFRES_SKIP" is not a marker.
    detail = str(detail).replace("ONFRES ", "ONFRES_")
    if cond:
        ok += 1
        print("  ok   %-52s %s" % (label, detail))
    else:
        bad += 1
        print("  FAIL %-52s %s" % (label, detail))


# --- onfres: the line format and the strict mode ---------------------------

def t_onfres():
    lax, strict = {}, {"ONFLY_NOSKIP": "1"}

    text, fatal = onfres.skipline("demo/check", "no widget", env=lax)
    check("a skip line has the counted form",
          text == "ONFRES SKIP demo/check: no widget", repr(text))
    check("a skip is not fatal without ONFLY_NOSKIP", fatal is False)

    text, fatal = onfres.skipline("demo/check", "no widget", env=strict)
    check("ONFLY_NOSKIP=1 makes a skip fatal", fatal is True)
    check("the fatal skip still prints as SKIP",
          text.startswith("ONFRES SKIP demo/check: "), repr(text))

    other = {"ONFLY_NOSKIP": "0"}
    check("only the value 1 turns strict mode on",
          onfres.skipline("demo/check", "x", env=other)[1] is False)

    name = sorted(onfres.EXEMPT)[0]
    text, fatal = onfres.skipline(name, "absent here", env=strict)
    check("an exempt check prints as EXEMPT with its D-row",
          text == "ONFRES EXEMPT %s: absent here [%s]"
          % (name, onfres.EXEMPT[name]), repr(text))
    check("an exempt check is not fatal even under ONFLY_NOSKIP=1",
          fatal is False)

    text = onfres.pendingline("demo/rec", "recording absent")
    check("a pending line has the counted form",
          text == "ONFRES PENDING demo/rec: recording absent", repr(text))

    # skip() prints, and exits 1 only when the skip is fatal.
    buf = io.StringIO()
    kind = onfres.skip("demo/check", "no widget", out=buf, env=lax)
    check("skip() returns SKIP and prints one line when lax",
          kind == "SKIP" and buf.getvalue()
          == "ONFRES SKIP demo/check: no widget\n", repr(buf.getvalue()))
    buf = io.StringIO()
    try:
        onfres.skip("demo/check", "no widget", out=buf, env=strict)
        code = None
    except SystemExit as exc:
        code = exc.code
    check("skip() exits 1 under ONFLY_NOSKIP=1", code == 1, "code=%r" % code)
    check("and says why before it exits",
          "ONFLY_NOSKIP=1" in buf.getvalue() and "D-548" in buf.getvalue(),
          repr(buf.getvalue()[-80:]))
    buf = io.StringIO()
    kind = onfres.skip(name, "absent here", out=buf, env=strict)
    check("skip() of an exempt check returns EXEMPT under strict mode",
          kind == "EXEMPT")
    buf = io.StringIO()
    onfres.skip("demo/check", "no widget", out=buf, env=lax, indent="  ")
    check("skip() indents the marker when asked, and the runner still "
          "finds it", buf.getvalue() == "  ONFRES SKIP demo/check: no "
          "widget\n" and testrun.scan(buf.getvalue()) is not None,
          repr(buf.getvalue()))

    # Every exemption must cite a decision the owner actually made.
    rows = set(re.findall(r"^\| (D-\d+) \|",
                          io.open(SRS, encoding="utf-8").read(), re.M))
    for check_id, drow in sorted(onfres.EXEMPT.items()):
        check("exemption %s cites a real A.1 row" % check_id,
              drow in rows, drow)
    check("the table holds D-548's five checks and D-555's sixth",
          len(onfres.EXEMPT) == 6, "%d entries" % len(onfres.EXEMPT))


# --- onfres.unittest_main: unittest's own skips are counted too ------------

def t_unittest():
    # D-555: a unittest skip used to reach the build output only as
    # "OK (skipped=1)", which neither a grep nor the runner could count.
    import types
    import unittest
    mod = types.ModuleType("onfres_fake")

    class Plain(unittest.TestCase):
        def test_runs(self):
            pass

        def test_skips(self):
            self.skipTest("no gadget")

    class Whole(unittest.TestCase):
        @classmethod
        def setUpClass(cls):
            raise unittest.SkipTest("no dataset")

        def test_never(self):
            pass

    mod.Plain, mod.Whole = Plain, Whole
    sys.modules["onfres_fake"] = mod
    try:
        out, err = io.StringIO(), io.StringIO()
        rc = onfres.unittest_main("fake", module="onfres_fake", out=out,
                                  stream=err, env={})
        lines = out.getvalue().splitlines()
        check("a method skip is reported as a counted SKIP line",
              "ONFRES SKIP fake/Plain.test_skips: no gadget" in lines,
              repr(lines))
        check("a class-level skip is reported under the class name",
              "ONFRES SKIP fake/Whole: no dataset" in lines, repr(lines))
        check("skips alone do not fail a lax run", rc == 0, "rc=%d" % rc)
        rc = onfres.unittest_main("fake", module="onfres_fake",
                                  out=io.StringIO(), stream=io.StringIO(),
                                  env={"ONFLY_NOSKIP": "1"})
        check("ONFLY_NOSKIP=1 fails a run with an unexempt skip",
              rc == 1, "rc=%d" % rc)
    finally:
        del sys.modules["onfres_fake"]


# --- lastln: the exit status survives --------------------------------------

def run_lastln(code, lines):
    prog = ("import sys\n"
            "for i in range(%d): print('line %%d' %% i)\n"
            "sys.exit(%d)\n" % (lines, code))
    fd, path = tempfile.mkstemp(suffix=".py")
    os.close(fd)
    try:
        io.open(path, "w", encoding="utf-8").write(prog)
        p = subprocess.run([sys.executable, LASTLN, sys.executable, path],
                           stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    finally:
        os.remove(path)
    return (p.returncode, p.stdout.decode("utf-8", "replace"),
            p.stderr.decode("utf-8", "replace"))


def t_lastln():
    rc, out, _ = run_lastln(0, 30)
    check("lastln passes status 0 through", rc == 0, "rc=%d" % rc)
    check("and prints only the last line, as tail -1 did",
          out.splitlines() == ["line 29"], repr(out[:60]))

    rc, out, err = run_lastln(3, 30)
    check("lastln passes a nonzero status through", rc == 3, "rc=%d" % rc)
    got = out.splitlines()
    check("and prints the last 20 lines so the failure is readable",
          got == ["line %d" % i for i in range(10, 30)],
          "%d lines" % len(got))
    check("and names the status on stderr", "exited 3" in err, repr(err))

    rc, out, _ = run_lastln(0, 0)
    check("a program with no output prints nothing and passes",
          rc == 0 and out == "", "rc=%d out=%r" % (rc, out))

    # The Makefile names programs as `build/tstxxx.exe`: relative, with a
    # forward slash.  Windows process creation did not find that spelling
    # when the first unmasked run tried it, so lastln resolves a program
    # path that exists before running it.
    import lastln
    d = tempfile.mkdtemp(prefix="onfly_ll_")
    here = os.getcwd()
    try:
        os.mkdir(os.path.join(d, "build"))
        io.open(os.path.join(d, "build", "prog.exe"), "wb").write(b"")
        os.chdir(d)
        got = lastln.resolve("build/prog.exe")
        check("a relative build/ path resolves to the file itself",
              os.path.isabs(got) and os.path.samefile(
                  got, os.path.join(d, "build", "prog.exe")), got)
        check("a name that is not a path is left for PATH to find",
              lastln.resolve("gcc") == "gcc")
    finally:
        os.chdir(here)
        os.remove(os.path.join(d, "build", "prog.exe"))
        os.rmdir(os.path.join(d, "build"))
        os.rmdir(d)


# --- testrun: counting, stopping and not repeating -------------------------

def t_testrun_scan():
    check("scan finds a SKIP marker mid-line",
          testrun.scan("  ok   label   ONFRES SKIP a/b: why")
          == ("SKIP", "a/b"))
    check("scan finds an EXEMPT marker",
          testrun.scan("ONFRES EXEMPT c/d: why [D-132]") == ("EXEMPT", "c/d"))
    check("scan finds a PENDING marker",
          testrun.scan("ONFRES PENDING e/f: why") == ("PENDING", "e/f"))
    check("scan ignores an ordinary line",
          testrun.scan("  ok   TE-01 bad magic") is None)
    check("scan ignores the word SKIP without the prefix",
          testrun.scan("test_x: SKIP - pandas absent") is None)

    line = testrun.closing(3, 1, 0, 2)
    check("the closing line carries all four counts",
          line == "ONFLY test: 3 PASS, 1 SKIP, 0 PENDING, 2 EXEMPT "
                  "(PASS counts targets; SKIP, PENDING and EXEMPT count "
                  "checks; D-548, D-549)", repr(line))


MAKEFILE = """\
.PHONY: good exempt skipper later bad needsgood
good:
\t@echo good-ran
exempt:
\t@echo "ONFRES EXEMPT %(ex)s: absent [x]"
skipper:
\t@echo "ONFRES SKIP demo/skip: no widget"
needsgood: good
\t@echo needsgood-ran
bad:
\t@echo bad-ran
\t@exit 5
later:
\t@echo later-ran
"""


def t_testrun_make(make):
    if not make:
        # Reported through onfres itself: the one path this case would test.
        text, fatal = onfres.skipline(
            "onfres/runner-end-to-end", "no MAKE program given on the "
            "command line")
        print("  " + text)
        if fatal:
            check("runner end to end (strict mode requires a MAKE)", False)
        return
    d = tempfile.mkdtemp(prefix="onfly_tr_")
    try:
        io.open(os.path.join(d, "Makefile"), "w", encoding="utf-8",
                newline="\n").write(MAKEFILE % {"ex": sorted(onfres.EXEMPT)[0]})
        env = dict(os.environ)
        env.pop("MAKEFLAGS", None)
        env.pop("MAKELEVEL", None)
        env.pop("ONFLY_NOSKIP", None)

        def drive(targets):
            p = subprocess.run([sys.executable,
                                os.path.join(ROOT, "tools", "testrun.py"),
                                make] + targets, cwd=d, env=env,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            return p.returncode, p.stdout.decode("utf-8", "replace")

        rc, out = drive(["good", "exempt", "skipper", "needsgood"])
        last = out.rstrip().splitlines()[-1]
        check("a clean run exits 0", rc == 0, "rc=%d" % rc)
        check("PASS counts targets, a skipped target is not a PASS",
              last.startswith("ONFLY test: 3 PASS, 1 SKIP, 0 PENDING, "
                              "1 EXEMPT"), repr(last))
        runs = [ln.strip() for ln in out.splitlines()]
        check("a target already made is not run again (-o)",
              runs.count("good-ran") == 1 and "needsgood-ran" in runs,
              "good-ran x%d" % runs.count("good-ran"))

        # The recipe exits 5, and make reports any failed recipe as its
        # own status 2; the runner must hand on make's status, not 0.
        rc, out = drive(["good", "bad", "later"])
        check("a failing target stops the run with make's status",
              rc == 2, "rc=%d" % rc)
        check("nothing after the failure runs", "later-ran" not in out)
        check("and the failure is named",
              "FAILED bad" in out, repr(out.rstrip().splitlines()[-1]))
    finally:
        for name in os.listdir(d):
            os.remove(os.path.join(d, name))
        os.rmdir(d)


def make_list(name):
    """The words of a `NAME = ...` assignment in the Makefile, joined
    across backslash continuations."""
    text = io.open(os.path.join(ROOT, "Makefile"), encoding="utf-8").read()
    m = re.search(r"^%s\s*=\s*((?:.*\\\n)*.*)$" % name, text, re.M)
    return m.group(1).replace("\\\n", " ").split() if m else None


def t_makefile():
    # P-41 E9: test-nonet is the subset of `test` that needs no network,
    # fixed by the group 2 measurement of P-44.  Pinned here so that the
    # two lists cannot drift apart: every NONET target is a TESTS target,
    # in the same order, and none of the targets that measurement showed
    # needing a network is in it.
    tests, nonet = make_list("TESTS"), make_list("NONET")
    check("the Makefile defines TESTS and NONET",
          bool(tests) and bool(nonet),
          "TESTS %s, NONET %s" % (len(tests or []), len(nonet or [])))
    if not tests or not nonet:
        return
    check("NONET is TESTS' targets in TESTS' order",
          nonet == [t for t in tests if t in nonet]
          and set(nonet) <= set(tests), " ".join(nonet))
    needs = {"mvsrun", "names", "req", "golden", "prep"}
    check("NONET holds none of the targets that need a network",
          not (set(nonet) & needs), sorted(set(nonet) & needs))
    check("NONET is the 23 targets measured network-free",
          len(nonet) == 23, "%d" % len(nonet))


def main(argv):
    make = argv[1] if len(argv) > 1 else None
    t_onfres()
    t_makefile()
    t_unittest()
    t_lastln()
    t_testrun_scan()
    t_testrun_make(make)
    print("test_onfres: %d passed, %d failed" % (ok, bad))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
