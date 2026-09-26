# -*- coding: utf-8 -*-
"""The one way a check reports that it did not run (P-44 E1, D-548).

WHY THIS EXISTS

D-233 lets a check whose prerequisite is absent print a skip line and pass,
so that a bare checkout stays runnable.  That is right for a bare checkout
and wrong for a replication: a replicator who is missing pandas gets a
green `make test` that did not run the pandas checks, and nothing in the
closing line said so.  Before this module the skip lines came in at least
four spellings from 18 files (P-44 S4), so neither a count nor a strict
mode could be added in one place.

Every skip now goes through `skipline()` or `skip()`, which print exactly

    ONFRES SKIP <check>: <reason>
    ONFRES EXEMPT <check>: <reason> [<D-row>]
    ONFRES PENDING <check>: <reason>

and `tools/testrun.py` counts those lines for `make test`'s closing line
(D-549).  The reason text each site printed before is kept word for word
after the prefix.

STRICT MODE

With `ONFLY_NOSKIP=1` in the environment a skip is a failure: `skip()`
prints the line and exits 1, and `skipline()` returns `fatal` so that a
site which collects rows can count it as a failed check.  Only the value
`1` turns it on.

THE EXEMPTION TABLE (D-548)

Some skips no clone can clear, because a decision keeps the prerequisite
out of every clone.  They are listed here with that decision, print as
EXEMPT rather than SKIP, and stay non-fatal under strict mode.  A skip is
exempt only under its own check name: a site distinguishes causes by name,
so that the same check skipped for a missing Python package is an ordinary
SKIP and still fails strict mode.  `tests/test_onfres.py` asserts every
entry cites a row that exists in SRS Appendix A.1.

Contract: pure functions over their arguments, plus `skip()`'s one write
to `out` and its possible `sys.exit(1)`.  No state is kept between calls.
"""
import os
import sys

PREFIX = "ONFRES"

#: check name -> the decision that makes its skip permanent in a clone.
EXEMPT = {
    # D-132 keeps the INTERCOMM subsystem out of this MIT tree, so the
    # decks it builds and the reply address it serves exist only on the
    # owner's host, under the ignored local/ directory.
    "ic3270/onflytx-decks": "D-132",
    "ic3270/onflytx-reply": "D-132",
    # D-545 distributes srext and path only; the two MaleCNS feathers these
    # checks read (one of them 1,051,241,946 bytes) are not distributed.
    "names/regenerate-feather": "D-545",
    "test_varnt/feathers": "D-545",
    # D-555: the same cause, found after D-548 because unittest reported it
    # only as "OK (skipped=1)".  Needs the 43,282,834 B neurotransmitters
    # feather.
    "test_signs/TestAgainstRealData": "D-545",
    # TE-08 through the whole program needs ONFLYENG to expose FR-LOD-04's
    # limit, which it does not; D-548 exempts the replay until the owner
    # decides whether it should.  The decoder-level TE-08 cases in
    # tests/run_dec.py run and pass.
    "eng/TE-08": "D-548",
}


def strict(env=None):
    """True when `ONFLY_NOSKIP` is exactly "1" in `env` (default: os.environ)."""
    env = os.environ if env is None else env
    return env.get("ONFLY_NOSKIP") == "1"


def skipline(check, reason, env=None):
    """(line, fatal) for a check that did not run.  Writes nothing.

    `line` is the counted marker; `fatal` is True only when strict mode is
    on and the check is not exempt.
    """
    if check in EXEMPT:
        return ("%s EXEMPT %s: %s [%s]" % (PREFIX, check, reason,
                                           EXEMPT[check]), False)
    return "%s SKIP %s: %s" % (PREFIX, check, reason), strict(env)


def pendingline(check, reason):
    """The counted marker for a check waiting on a recorded input."""
    return "%s PENDING %s: %s" % (PREFIX, check, reason)


def skip(check, reason, out=None, env=None, indent=""):
    """Print the marker for a skipped check; exit 1 if strict mode fails it.

    `indent` is written before the marker, for a site whose skip line sits
    in an indented table of results; the runner finds the marker anywhere
    in a line.  Returns "SKIP" or "EXEMPT" when it returns at all, so a
    caller that carries on after a skip can say which it was.
    """
    out = sys.stdout if out is None else out
    line, fatal = skipline(check, reason, env)
    out.write(indent + line + "\n")
    if fatal:
        out.write("%s%s FAIL %s: ONFLY_NOSKIP=1 turns this skip into a "
                  "failure (D-548)\n" % (indent, PREFIX, check))
        out.flush()
        sys.exit(1)
    return "EXEMPT" if check in EXEMPT else "SKIP"


def _test_name(prefix, test):
    """The check name for one skipped unittest test.

    A method skip is `<prefix>/<Class>.<method>`.  A skip raised in
    setUpClass reaches the result as a placeholder whose description reads
    "setUpClass (module.Class)", and is named `<prefix>/<Class>`, because
    the whole class did not run.
    """
    desc = getattr(test, "description", None)
    if desc:
        inner = desc[desc.find("(") + 1:desc.rfind(")")] if "(" in desc \
            else desc
        return "%s/%s" % (prefix, inner.split(".")[-1])
    return "%s/%s.%s" % (prefix, type(test).__name__,
                         getattr(test, "_testMethodName", "?"))


def unittest_main(prefix, module="__main__", out=None, stream=None,
                  env=None):
    """Run a file's unittest tests and report every skip through this module.

    Replaces `unittest.main(verbosity=2)` in a test file (D-555).  The
    tests run exactly as before, at verbosity 2 on `stream` (stderr by
    default).  Then one marker per skipped test or class is written to
    `out`.  Returns the exit status: 1 if a test failed or errored, or if
    strict mode fails an unexempt skip; else 0.
    """
    import unittest
    out = sys.stdout if out is None else out
    skipped = []

    class Result(unittest.TextTestResult):
        def addSkip(self, test, reason):
            super(Result, self).addSkip(test, reason)
            skipped.append((_test_name(prefix, test), reason))

    runner = unittest.TextTestRunner(stream=stream or sys.stderr,
                                     verbosity=2, resultclass=Result)
    prog = unittest.main(module=module, argv=[prefix], testRunner=runner,
                         exit=False)
    fatal = []
    for check, reason in skipped:
        line, f = skipline(check, reason, env)
        out.write(line + "\n")
        if f:
            fatal.append(check)
    for check in fatal:
        out.write("%s FAIL %s: ONFLY_NOSKIP=1 turns this skip into a "
                  "failure (D-548)\n" % (PREFIX, check))
    out.flush()
    return 0 if prog.result.wasSuccessful() and not fatal else 1
