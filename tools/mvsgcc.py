# -*- coding: utf-8 -*-
"""Measure what GCCMVS actually does on TK5 (VL-17, VL-18, VL-19).

Gate G1 asks whether GCCMVS can build and run ONFLY's arithmetic.  Three
separate things had to be measured to answer that, and each was found by
being bitten rather than by reading documentation, so each is reproducible
here rather than left as a claim in the register.

  --chars    Which characters survive the card reader into the compiler.
             ONFLY source uses `|=` and `||`; on Hercules' `default`
             codepage `|` arrives as EBCDIC 0x6A and GCCMVS will not lex
             it, so no ONFLY source compiles at all.  819/037 fixes `|`
             and breaks `^`, `[` and `]`.  819/1047 carries all thirteen
             (D-101, VL-18).

  --levels   Which optimisation level compiles a 64-bit addition.  Exactly
             one does.  -O0 dies in the reload pass and -O2, -O3 and -Os
             die elsewhere, so ONFLY is pinned to -O1 (D-100, VL-17).

  --ops      Which 64-bit operations are correct at -O1.  This is the one
             that matters: multiply and left shift compile, link, run and
             return WRONG ANSWERS with no diagnostic (VL-19).

Every check compares against a value computed here on x86 and prints both,
because a job that runs and prints something is not the same as a job that
is right -- which is precisely how the multiply defect hid.

The probes need the codepage already set to 819/1047; --chars is the one
that tells you whether it is.  Run:

    python tools/mvsgcc.py              all three
    python tools/mvsgcc.py --ops        the 64-bit matrix only
"""
import os
import socket
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import mvsub  # noqa: E402

OPT = "-O1"
MASK = (1 << 64) - 1

# Operands with every nibble distinct, so a dropped or duplicated half is
# visible in the printed value rather than hidden by symmetry.
A = 0x0123456789ABCDEF
B = 0x00000000FEDCBA98

# The EBCDIC-variant set.  `|` is the one ONFLY cannot do without.
VARIANT = "|!^[]{}~#@$\\`"


def head(job, title):
    return [
        "//%-8s JOB (001),'%s',CLASS=A,MSGCLASS=A," % (job, title[:20]),
        "//             USER=HERC01,PASSWORD=CUL8TR,",
        # REGION is not optional: without one a compile can spin at 100%
        # of a core instead of failing.
        "//             REGION=8M,TIME=1440,MSGLEVEL=(1,1)",
        "//*",
    ]


def gcc_step(opt):
    return [
        "//S1       EXEC GCCCLG,COPTS='-Wno-long-long %s'" % opt,
        "//COMP.SYSIN DD *",
    ]


def run_job(job, deck, timeout=300):
    mvsub.check_cards(deck)
    before = mvsub.submit(deck)
    return mvsub.collect(job, before, timeout=timeout, poll=4)


def probe_chars():
    """Report every variant character the compiler will not lex."""
    job = "ONFGCHR"
    prologue = head(job, "ONFLY CHAR PROBE") + gcc_step(OPT)
    # The compiler numbers the inline stream from 1, so a card at deck
    # position i (0-based) is C line i - len(prologue) + 1.
    base = len(prologue)
    deck = prologue + ["int main(void) { return 0; }"]
    index = {}
    for ch in VARIANT:
        index[len(deck) - base + 1] = ch
        deck.append(ch)
        # A declaration after each probe character gives the parser a
        # place to resynchronise, so line numbers stay attributable.
        deck.append("int pad%d;" % ord(ch))
    deck += ["/*", "//"]

    out = run_job(job, deck)
    if out is None:
        print("chars: job did not finish")
        return 1

    import re
    bad = {}
    for line in out.splitlines():
        m = re.search(r"<stdin>:(\d+): stray '\\(\d+)' in program",
                      line.rstrip())
        if m:
            bad.setdefault(int(m.group(1)), int(m.group(2), 8))

    print("=== characters the compiler cannot lex ===")
    fails = 0
    for ln, octal in sorted(bad.items()):
        ch = index.get(ln, "?")
        print("  %r arrives as EBCDIC 0x%02X and is rejected" % (ch, octal))
        fails += 1
    if not fails:
        print("  none: all %d variant characters lex" % len(VARIANT))
    return 1 if fails else 0


def probe_levels():
    """Report which optimisation levels compile a 64-bit addition."""
    print("=== 64-bit addition by optimisation level ===")
    bad = 0
    for opt in ["-O0", "-O1", "-O2", "-O3", "-Os"]:
        job = ("ONFGL" + opt[-2:]).upper()
        deck = head(job, "ONFLY OPT PROBE") + gcc_step(opt) + [
            "typedef unsigned long long u64;",
            "",
            "int main(void)",
            "{",
            "    u64 v;",
            "    unsigned long hi;",
            "    unsigned long lo;",
            "",
            "    v = (u64)0xFFFFFFFFUL;",
            "    v = v + (u64)1UL;",
            "    hi = (unsigned long)((v >> 32) & 0xFFFFFFFFUL);",
            "    lo = (unsigned long)(v & 0xFFFFFFFFUL);",
            '    printf("LVL hi=%08lX lo=%08lX\\n", hi, lo);',
            "    return 0;",
            "}",
            "/*",
            "//",
        ]
        out = run_job(job, deck)
        ok = out is not None and "LVL hi=00000001 lo=00000000" in out
        why = ""
        if not ok and out:
            for line in out.splitlines():
                if "Internal compiler error" in line:
                    why = line.strip()[-28:]
                    break
        print("  %-4s %-5s %s" % (opt, "ok" if ok else "FAIL", why))
        if not ok:
            bad += 1
    return 1 if bad > 4 else 0


def probe_ops():
    """Report which 64-bit operations are CORRECT, not merely buildable."""
    cases = [
        ("ONFGMUL", "MUL", "a * b", (A * B) & MASK),
        ("ONFGDIV", "DIV", "a / b", A // B),
        ("ONFGMOD", "MOD", "a % b", A % B),
        ("ONFGSHL", "SHL", "a << 7", (A << 7) & MASK),
        ("ONFGSHR", "SHR", "a >> 7", A >> 7),
        ("ONFGADD", "ADD", "a + b", (A + B) & MASK),
        ("ONFGSUB", "SUB", "a - b", (A - B) & MASK),
        ("ONFGAND", "AND", "a & b", A & B),
        ("ONFGOR", "OR", "a | b", A | B),
    ]
    print("=== 64-bit operations at %s ===" % OPT)
    print("  a = 0x%016X" % A)
    print("  b = 0x%016X" % B)
    wrong = 0
    for job, tag, expr, want in cases:
        deck = head(job, "ONFLY OP PROBE") + gcc_step(OPT) + [
            "typedef unsigned long long u64;",
            "",
            "int main(void)",
            "{",
            "    u64 a;",
            "    u64 b;",
            "    u64 r;",
            "    unsigned long hi;",
            "    unsigned long lo;",
            "",
        ] + _mk_a("OP") + [
            "    b = (u64)0xFEDCBA98UL;",
            "    r = %s;" % expr,
            "    hi = (unsigned long)((r >> 32) & 0xFFFFFFFFUL);",
            "    lo = (unsigned long)(r & 0xFFFFFFFFUL);",
            '    printf("OP %s hi=%%08lX lo=%%08lX\\n", hi, lo);' % tag,
            "    return 0;",
            "}",
            "/*",
            "//",
        ]
        out = run_job(job, deck)
        if out is not None:
            ok_a, why_a = _check(out, "OP", "a", A)
            # "no output" here just means the job never ran, which the
            # verdict below reports properly; only a job that ran and
            # printed a WRONG operand invalidates its own result.
            if not ok_a and why_a != "no output":
                print("  %-4s OPERAND  %s -- result not trusted"
                      % (tag, why_a))
        if out is None:
            verdict, detail = "TIMEOUT", ""
        else:
            ok, why = _check(out, "OP", tag, want)
            if ok:
                verdict, detail = "ok", ""
            elif why != "no output":
                verdict, detail = "WRONG", why
            else:
                verdict, detail = "no run", ""
                for line in out.splitlines():
                    if "Internal compiler error" in line:
                        detail = "ICE" + line.strip()[-12:]
                        break
                    if "IFOX" in line and "RC= 0008" in line:
                        detail = "assembler rejected the output (RC 8)"
        if verdict != "ok":
            wrong += 1
        print("  %-4s %-7s %s" % (tag, verdict, detail))
    return 1 if wrong else 0


def _mk_a(tag="SH"):
    """Cards building a = 0x0123456789ABCDEF, then printing it back.

    The obvious `(a << 32) + lo` is deliberately NOT used.  The first
    version of the operation matrix built the operand that way and then
    reported that `a * b` returned zero and `a << 7` dropped bit 63 --
    both of which turned out to depend on the *setup* rather than on the
    operation under test, because 64-bit `+` is itself defective here.  A
    probe whose scaffolding shares a defect with its subject cannot tell
    you which one failed.

    OR is one of the operations measured correct, so the operand is built
    with it, and the program prints `a` back before touching it.  If the
    construction is ever miscompiled the check on `a` fails first and every
    result after it is known to be meaningless rather than quietly wrong.
    """
    return [
        "    a = (u64)0x01234567UL;",
        "    a = (a << 32) | (u64)0x89ABCDEFUL;",
        "    hi = (unsigned long)((a >> 32) & 0xFFFFFFFFUL);",
        "    lo = (unsigned long)(a & 0xFFFFFFFFUL);",
        '    printf("%s a hi=%%08lX lo=%%08lX\\n", hi, lo);' % tag,
    ]


def _check(out, tag, label, want):
    line = "%s %s hi=%08X lo=%08X" % (tag, label,
                                      (want >> 32) & 0xFFFFFFFF,
                                      want & 0xFFFFFFFF)
    if line in out:
        return True, ""
    got = ""
    for cand in out.splitlines():
        if cand.strip().startswith("%s %s hi=" % (tag, label)):
            got = cand.strip()
    if not got:
        return False, "no output"
    return False, "got %s want hi=%08X lo=%08X" % (
        got.split("hi=", 1)[-1][:22], (want >> 32) & 0xFFFFFFFF,
        want & 0xFFFFFFFF)


def probe_shifts():
    """D-102: is the 64-bit left-shift defect confined to one count?

    VL-19 measured `a << 7` and found bit 63 dropped.  ONFLY's SoftFloat 3e
    build shifts 64-bit significands by 1, 9, 10 and 11 (s_addMagsF64.c,
    f64_mul.c) and by a variable count (s_shiftRightJam64.c), so whether
    those particular shifts are affected decides whether Spike S1 can work
    at all.  Both forms are measured, because a compiler can get one right
    and the other wrong: a constant count is folded into an instruction
    pair, a variable one goes through a synthesised routine.
    """
    bad = 0

    # --- variable count, every value 0..63, in one job -------------------
    job = "ONFGSHV"
    deck = head(job, "ONFLY SHIFT SWEEP") + gcc_step(OPT) + [
        "typedef unsigned long long u64;",
        "",
        "int main(void)",
        "{",
        "    u64 a;",
        "    u64 r;",
        "    int n;",
        "    unsigned long hi;",
        "    unsigned long lo;",
        "",
    ] + _mk_a() + [
        "    for (n = 0; n < 64; n++) {",
        "        r = a << n;",
        "        hi = (unsigned long)((r >> 32) & 0xFFFFFFFFUL);",
        "        lo = (unsigned long)(r & 0xFFFFFFFFUL);",
        '        printf("SH %02d hi=%08lX lo=%08lX\\n", n, hi, lo);',
        "    }",
        "    return 0;",
        "}",
        "/*",
        "//",
    ]
    out = run_job(job, deck, timeout=420)
    print("=== 64-bit left shift, VARIABLE count, at %s ===" % OPT)
    if out is None:
        print("  job did not finish")
        bad += 1
    else:
        ok, why = _check(out, "SH", "a", A)
        if not ok:
            print("  the operand itself is wrong: %s" % why)
            print("  every result below is therefore meaningless")
            bad += 1
        wrong = []
        for n in range(64):
            ok, why = _check(out, "SH", "%02d" % n, (A << n) & MASK)
            if not ok:
                wrong.append((n, why))
        if not wrong:
            print("  all 64 counts correct")
        else:
            print("  %d of 64 counts WRONG:" % len(wrong))
            for n, why in wrong[:8]:
                print("    n=%-2d %s" % (n, why))
            if len(wrong) > 8:
                print("    ... and %d more" % (len(wrong) - 8))
            bad += 1

    # --- constant counts, including the ones SoftFloat uses --------------
    counts = [0, 1, 7, 9, 10, 11, 31, 32, 33, 63]
    job = "ONFGSHC"
    body = []
    for n in counts:
        body += [
            "    r = a << %d;" % n,
            "    hi = (unsigned long)((r >> 32) & 0xFFFFFFFFUL);",
            "    lo = (unsigned long)(r & 0xFFFFFFFFUL);",
            '    printf("SH %02d hi=%%08lX lo=%%08lX\\n", hi, lo);' % n,
        ]
    deck = head(job, "ONFLY SHIFT CONST") + gcc_step(OPT) + [
        "typedef unsigned long long u64;",
        "",
        "int main(void)",
        "{",
        "    u64 a;",
        "    u64 r;",
        "    unsigned long hi;",
        "    unsigned long lo;",
        "",
    ] + _mk_a() + body + [
        "    return 0;",
        "}",
        "/*",
        "//",
    ]
    out = run_job(job, deck, timeout=420)
    print("=== 64-bit left shift, CONSTANT count, at %s ===" % OPT)
    print("  (1, 9, 10 and 11 are the counts SoftFloat 3e actually uses)")
    if out is None:
        print("  job did not finish")
        bad += 1
    else:
        any_wrong = False
        for n in counts:
            ok, why = _check(out, "SH", "%02d" % n, (A << n) & MASK)
            print("  n=%-2d %-5s %s" % (n, "ok" if ok else "WRONG",
                                        "" if ok else why))
            any_wrong = any_wrong or not ok
        bad += 1 if any_wrong else 0

    # --- the widening multiply SoftFloat's mul64To128M relies on ---------
    a32, b32 = 0x89ABCDEF, 0xFEDCBA98
    job = "ONFGMLW"
    deck = head(job, "ONFLY WIDE MUL") + gcc_step(OPT) + [
        "typedef unsigned long long u64;",
        "",
        "int main(void)",
        "{",
        "    unsigned long p;",
        "    unsigned long q;",
        "    u64 r;",
        "    unsigned long hi;",
        "    unsigned long lo;",
        "",
        "    p = 0x%08XUL;" % a32,
        "    q = 0x%08XUL;" % b32,
        "    r = (u64)p * (u64)q;",
        "    hi = (unsigned long)((r >> 32) & 0xFFFFFFFFUL);",
        "    lo = (unsigned long)(r & 0xFFFFFFFFUL);",
        '    printf("MW r hi=%08lX lo=%08lX\\n", hi, lo);',
        "    return 0;",
        "}",
        "/*",
        "//",
    ]
    out = run_job(job, deck)
    print("=== 32x32 -> 64 multiply at %s ===" % OPT)
    print("  (this is what s_mul64To128M.c does, four times per f64 mul)")
    if out is None:
        print("  job did not finish")
        bad += 1
    else:
        ok, why = _check(out, "MW", "r", a32 * b32)
        print("  0x%08X * 0x%08X  %s  %s"
              % (a32, b32, "ok" if ok else "WRONG", "" if ok else why))
        bad += 0 if ok else 1

    return 1 if bad else 0


def main(argv):
    want = [a for a in argv if a.startswith("--")]
    if not want:
        want = ["--chars", "--levels", "--ops", "--shifts"]
    rc = 0
    if "--chars" in want:
        rc |= probe_chars()
    if "--levels" in want:
        rc |= probe_levels()
    if "--ops" in want:
        rc |= probe_ops()
    if "--shifts" in want:
        rc |= probe_shifts()
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
