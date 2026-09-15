# -*- coding: utf-8 -*-
"""Derive ONFLY's SoftFloat 2c configuration from upstream's templates.

D-105 vendors Berkeley SoftFloat Release 2c because Gate G1 measured that
GCCMVS cannot build Release 3e (VL-19, VL-21).  2c's `bits32` build uses
only 32-bit integers, which is the property that matters.

Release 2c is not configured by a single platform.h the way 3e is.  Its
supported customisation path, stated in SoftFloat-source.txt, is to copy
the files in `bits32/templates/` and substitute the `!!!` placeholders for
the target's types.  This script does that substitution instead of a person
doing it by hand, for the same reason `softfloat/derive.py` exists for 3e:
a hand copy is a second source that drifts, and nobody notices until a
result changes.

WHAT IS CHANGED, AND WHY EACH CHANGE
------------------------------------
1. `milieu.h` -- the processor include is pointed at ONFLY's own header
   instead of `!!!processor.h`.  Upstream ships 386-GCC.h and SPARC-GCC.h
   and BOTH `#define BITS64`, which would pull 64-bit integer types back
   into a build chosen precisely to avoid them.

2. `softfloat.h` -- the placeholder types are substituted.  Nothing else.

3. `softfloat-specialize` -- the placeholders are substituted AND the NaN
   conventions are set to ARM-VFPv2 default-NaN, matching the 3e backend
   (D-31, D-107).  The template ships 0xFFFFFFFF placeholders for the
   default NaN patterns, so this file cannot be used unmodified in any
   case.  Keeping the two backends on one NaN convention means that if
   the D-106 identity check finds a disagreement, it is a disagreement
   about arithmetic and not about NaN policy.

4. `softfloat.c` -- the three pieces of writable static state are removed
   (D-123, NFR-MNT-02).  This is the same change D-34 and D-35 made to
   Release 3e, where `softfloat/onfsub.c` and `softfloat/onfrpk.c` carry
   it; 2c keeps its whole library in one file, so the derivation lands
   here instead.

   Measured on 2026-09-11, not assumed.  Upstream's
   bits32/softfloat.c defines `float_rounding_mode` and
   `float_exception_flags` at lines 32 and 33, and the binary64 add,
   subtract and multiply path ONFLY actually calls reaches all three
   globals: `roundAndPackFloat64` writes the inexact flag (line 187 of
   the float32 twin, 407 of the float64 one) and reads
   `float_detect_tininess` (386), and `subFloat64Sigs` reads
   `float_rounding_mode` for the x - x sign rule (1668).

   Every substitution below is a constant the specification already
   fixes, so no result can change:

     NR-01 fixes the rounding mode to round-to-nearest-ties-to-even and
     NR-10 forbids ever changing it, so `float_rounding_mode` is that
     constant by construction -- exactly the argument D-35 made for 3e.

     The tininess mode is `float_tininess_after_rounding`, which is what
     upstream's own specialize file statically initialises it to, so the
     comparison against `float_tininess_before_rounding` is false by
     construction.

     NR-10 forbids any ONFLY logic depending on the exception flags, so
     the accumulating writes become calls to `float_raise`, which D-34
     already made a no-op.  The call sites keep upstream's shape; what
     disappears is the storage behind them.

   The declarations and definitions go too, in `softfloat.h` and
   `softfloat-specialize`, so that a future reference fails at compile
   time rather than quietly reintroducing the state at link time.

   That the results did not change is not argued, it is measured: `make
   c2c` re-runs the TestFloat identity check of VL-22 over all six
   operations, against Release 3e through the same generator.

Every substitution is asserted: if upstream's text is not exactly what is
expected, this script fails rather than producing a file that merely looks
right.  A silent partial substitution would leave a `!!!` in a header and
the compiler would say so, but a silent WRONG substitution would not.  An
edit that carries an expected occurrence count is checked against it, so
a substitution that upstream duplicated or dropped fails loudly.

LICENCE
-------
Release 2c's notice expressly permits inclusion in a derivative work
provided the work says prominently that it is derivative and reproduces
the three legal paragraphs.  Every file this script writes therefore
begins with that notice.  See third_party/MANIFEST.md.

Run:  python softfloat/derive2c.py [--check]
      --check verifies the committed files match what would be generated.
"""
import io
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TPL = os.path.join(ROOT, "third_party", "SoftFloat-2c", "softfloat",
                   "bits32", "templates")
B32 = os.path.join(ROOT, "third_party", "SoftFloat-2c", "softfloat", "bits32")
OUT = os.path.join(ROOT, "softfloat", "c2c")

NOTICE = """\
/*
 * DERIVATIVE WORK.  This file is ONFLY's configuration of Berkeley
 * SoftFloat Release 2c, by John R. Hauser, generated from upstream's
 * %s by softfloat/derive2c.py.  Do not edit it by hand:
 * edit the script.  The original template is in
 * third_party/SoftFloat-2c/softfloat/bits32/templates/ and is unmodified.
 *
 * Release 2c's legal notice, reproduced as its terms require:
 *
 *   THIS SOFTWARE IS DISTRIBUTED AS IS, FOR FREE.  Although reasonable
 *   effort has been made to avoid it, THIS SOFTWARE MAY CONTAIN FAULTS
 *   THAT WILL AT TIMES RESULT IN INCORRECT BEHAVIOR.  USE OF THIS
 *   SOFTWARE IS RESTRICTED TO PERSONS AND ORGANIZATIONS WHO CAN AND WILL
 *   TOLERATE ALL LOSSES, COSTS, OR OTHER PROBLEMS THEY INCUR DUE TO THE
 *   SOFTWARE WITHOUT RECOMPENSE FROM JOHN HAUSER OR THE INTERNATIONAL
 *   COMPUTER SCIENCE INSTITUTE, AND WHO FURTHERMORE EFFECTIVELY INDEMNIFY
 *   JOHN HAUSER AND THE INTERNATIONAL COMPUTER SCIENCE INSTITUTE
 *   (possibly via similar legal notice) AGAINST ALL LOSSES, COSTS, OR
 *   OTHER PROBLEMS INCURRED BY THEIR CUSTOMERS AND CLIENTS DUE TO THE
 *   SOFTWARE, OR INCURRED BY ANYONE DUE TO A DERIVATIVE WORK THEY CREATE
 *   USING ANY PART OF THE SOFTWARE.
 *
 *   The following are expressly permitted, even for commercial purposes:
 *   (1) distribution of SoftFloat in whole or in part, as long as this and
 *   other legal notices remain and are prominent, and provided also that,
 *   for a partial distribution, prominent notice is given that it is a
 *   subset of the original; and (2) inclusion or use of SoftFloat in whole
 *   or in part in a derivative work, provided that the use restrictions
 *   above are met and the minimal documentation requirements stated in the
 *   source code are satisfied.
 */
"""

# The placeholder substitutions upstream's SoftFloat-source.txt prescribes.
# `flag`, `int8`, `int32` and `bits32` are the names ONFLY's processor
# header defines, so each placeholder loses its marker and nothing else.
TYPES = [
    ("!!!bits32", "bits32"),
    ("!!!int32", "int32"),
    ("!!!int8", "int8"),
    ("!!!flag", "flag"),
]

# D-107 / D-31: ARM-VFPv2 default NaN.  3e's specialize.h gives
# defaultNaNF32UI 0x7FC00000 and defaultNaNF64UI 0x7FF8000000000000, and
# its s_propagateNaNF64UI.c returns that pattern unconditionally rather
# than selecting an operand.  These edits reproduce both in 2c's idiom,
# where a float64 is a pair of 32-bit halves.
EDITS = [
    # D-34 / NFR-MNT-02: the exception flags are writable static state the
    # engine must not keep, and NR-10 already forbids any logic depending on
    # them.  The 3e path neutralises softfloat_raiseFlags the same way, by
    # supplying a no-op rather than by editing anything upstream.  A no-op
    # function holds no state, which is the whole point.
    ("void float_raise( int8 flags )\n"
     "{\n"
     "\n"
     "    float_exception_flags |= flags;\n"
     "\n"
     "}\n",
     "void float_raise( int8 flags )\n"
     "{\n"
     "\n"
     "    /* D-34, NFR-MNT-02, NR-10: discarded, not accumulated. */\n"
     "    (void) flags;\n"
     "\n"
     "}\n"),
    ("    float32_default_nan = 0xFFFFFFFF\n",
     "    float32_default_nan = 0x7FC00000\n"),
    ("    float64_default_nan_high = 0xFFFFFFFF,\n"
     "    float64_default_nan_low  = 0xFFFFFFFF\n",
     "    float64_default_nan_high = 0x7FF80000,\n"
     "    float64_default_nan_low  = 0x00000000\n"),
    # Default-NaN propagation: any NaN operand yields the default NaN.
    # The signaling-NaN test is kept so the invalid flag is still raised
    # exactly where upstream raises it; only the returned value changes.
    ("    a.high |= 0x00080000;\n"
     "    b.high |= 0x00080000;\n"
     "    if ( aIsSignalingNaN | bIsSignalingNaN )"
     " float_raise( float_flag_invalid );\n"
     "    if ( aIsNaN ) {\n"
     "        return ( aIsSignalingNaN & bIsNaN ) ? b : a;\n"
     "    }\n"
     "    else {\n"
     "        return b;\n"
     "    }\n",
     "    if ( aIsSignalingNaN | bIsSignalingNaN )"
     " float_raise( float_flag_invalid );\n"
     "    /* ARM-VFPv2 default NaN (D-31, D-107): the result of any NaN\n"
     "       operand is the default NaN, never a propagated payload. */\n"
     "    (void) aIsNaN;\n"
     "    (void) bIsNaN;\n"
     "    a.high = float64_default_nan_high;\n"
     "    a.low = float64_default_nan_low;\n"
     "    return a;\n"),
]


# D-123 / NFR-MNT-02: remove the declarations of the three globals from the
# public header as well.  Leaving an `extern` for a symbol that no longer
# exists would turn a future reference into a link failure on whichever
# platform linked last; removing it turns the same mistake into a compile
# error on the first one.  The enums that follow each declaration stay --
# the substitutions in softfloat.c are written in terms of them.
EDITS_H = [
    ("extern int8 float_detect_tininess;\n", "", 1),
    ("extern int8 float_rounding_mode;\n", "", 1),
    ("extern int8 float_exception_flags;\n", "", 1),
]

# The definition of the tininess mode lives in the specialize file rather
# than in softfloat.c, so it is removed here (D-123).
EDITS_SPEC_STATE = [
    ("int8 float_detect_tininess = float_tininess_after_rounding;\n",
     "/* D-123, NFR-MNT-02: removed.  The mode is\n"
     "   float_tininess_after_rounding, which is what this line set it to\n"
     "   and what every use in softfloat.c is now substituted with. */\n",
     1),
]

# D-123 / NFR-MNT-02: softfloat.c's own writable static state.  Each entry
# carries the number of occurrences expected, so upstream changing the shape
# of the file is a failure rather than a partial substitution.
EDITS_C = [
    # The storage itself.
    ("int8 float_rounding_mode = float_round_nearest_even;\n"
     "int8 float_exception_flags = 0;\n",
     "/* D-123, NFR-MNT-02: removed, so that this library holds no\n"
     "   writable static data and the engine built on it is reentrant for\n"
     "   the CICS path of Section 3.7.  NR-01 fixes the rounding mode and\n"
     "   NR-10 forbids changing it or depending on the flags, so every use\n"
     "   below becomes the constant the specification already requires. */\n",
     1),
    # Reads of the rounding mode into a local.  Seven sites, four of them in
    # float32 paths ONFLY never calls; all are substituted so that no
    # reference to the global survives anywhere in the translation unit.
    ("roundingMode = float_rounding_mode;",
     "roundingMode = float_round_nearest_even; /* D-123, NR-01 */",
     7),
    # The tininess mode, read inside the underflow test of each
    # roundAndPack routine.
    ("float_detect_tininess == float_tininess_before_rounding",
     "0 /* D-123: after rounding */                      ",
     2),
    # Accumulating writes of the inexact flag.  float_raise is already the
    # no-op D-34 installed, so the notification is discarded exactly as it
    # is on the 3e backend.
    ("float_exception_flags |= float_flag_inexact;",
     "float_raise( float_flag_inexact ); /* D-123 */",
     12),
    # Rounding-mode switches in the round-to-integer routines.
    ("switch ( float_rounding_mode ) {",
     "switch ( (int8) float_round_nearest_even ) { /* D-123 */",
     2),
    # The x - x sign rule: the difference of two equal finite values is -0
    # only when rounding toward negative infinity, which NR-01 excludes.
    ("float_rounding_mode == float_round_down",
     "0 /* D-123: never round-down, NR-01 */",
     2),
    # D-285.  float64_rem declares `sbits32 sigMean0` and then passes its
    # address to add64, whose fifth parameter is `bits32 *`.  GCCMVS, gcc
    # and clang all accept it -- which is why the vendor unit is compiled
    # without -pedantic-errors -- but JCC 1.50 rejects it and, having
    # rejected it, writes NO OBJECT AT ALL for the translation unit.  The
    # whole float API disappears with it: F64ADD, F64SUB, F64MUL, F64LT
    # and F64LE were all unresolved at link, over one dead function ONFLY
    # never calls.  The cast is semantically null on a two's-complement
    # host -- same address, same width -- and the datum is read back
    # through the signed lvalue two lines later exactly as before.
    # Measured on TK5 2026-09-15 by `tools/mvsjcc.py --mini`: the same
    # code shape without the cast gives JCC-RC:1 and no object, with it
    # gives JCC-RC:0 and a program that runs.
    ("alternateASig0, alternateASig1, &sigMean0, &sigMean1 );",
     "alternateASig0, alternateASig1,\n"
     "        (bits32 *) &sigMean0, /* D-285: JCC writes no object\n"
     "                                 without this cast */\n"
     "        &sigMean1 );",
     1),
]


def derive(name, edits=(), srcdir=None):
    src = io.open(os.path.join(srcdir or TPL, name),
                  encoding="latin-1").read()
    text = src
    for placeholder, real in TYPES:
        text = text.replace(placeholder, real)
    if name == "milieu.h":
        old = '#include "../../../processors/!!!processor.h"'
        if old not in src:
            raise SystemExit("derive2c: milieu.h template has changed: "
                             "the processor include was not found")
        text = text.replace(old, '#include "onfproc.h"')
    for edit in edits:
        old, new = edit[0], edit[1]
        want = edit[2] if len(edit) > 2 else 1
        got = text.count(old)
        if got != want:
            raise SystemExit(
                "derive2c: %s contains the expected text %d times, not %d:\n%s"
                % (name, got, want, old[:120]))
        text = text.replace(old, new, want)
    if "!!!" in text:
        raise SystemExit("derive2c: %s still has a !!! placeholder" % name)
    return NOTICE % name + text


TARGETS = [
    ("milieu.h", (), None),
    ("softfloat.h", EDITS_H, None),
    ("softfloat-specialize", EDITS + EDITS_SPEC_STATE, None),
    # Not from templates/: softfloat.c is the library itself, already typed,
    # so it is derived from the vendored bits32 source (D-123).
    ("softfloat.c", EDITS_C, B32),
]


def main(argv):
    check = "--check" in argv
    bad = 0
    for name, edits, srcdir in TARGETS:
        want = derive(name, edits, srcdir)
        path = os.path.join(OUT, name)
        if check:
            have = (io.open(path, encoding="latin-1").read()
                    if os.path.exists(path) else None)
            if have != want:
                sys.stderr.write("derive2c: %s is stale or edited by hand\n"
                                 % path)
                bad += 1
            continue
        if not os.path.isdir(OUT):
            os.makedirs(OUT)
        io.open(path, "w", encoding="latin-1", newline="\n").write(want)
        sys.stdout.write("derive2c: wrote %s (%d bytes)\n"
                         % (path, len(want)))
    if check and not bad:
        sys.stdout.write("derive2c: %d generated files match the templates\n"
                         % len(TARGETS))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
