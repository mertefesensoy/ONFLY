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

Every substitution is asserted: if upstream's text is not exactly what is
expected, this script fails rather than producing a file that merely looks
right.  A silent partial substitution would leave a `!!!` in a header and
the compiler would say so, but a silent WRONG substitution would not.

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


def derive(name, edits=()):
    src = io.open(os.path.join(TPL, name), encoding="latin-1").read()
    text = src
    for placeholder, real in TYPES:
        text = text.replace(placeholder, real)
    if name == "milieu.h":
        old = '#include "../../../processors/!!!processor.h"'
        if old not in src:
            raise SystemExit("derive2c: milieu.h template has changed: "
                             "the processor include was not found")
        text = text.replace(old, '#include "onfproc.h"')
    for old, new in edits:
        if old not in text:
            raise SystemExit(
                "derive2c: %s does not contain the expected text:\n%s"
                % (name, old[:120]))
        text = text.replace(old, new, 1)
    if "!!!" in text:
        raise SystemExit("derive2c: %s still has a !!! placeholder" % name)
    return NOTICE % name + text


TARGETS = [
    ("milieu.h", ()),
    ("softfloat.h", ()),
    ("softfloat-specialize", EDITS),
]


def main(argv):
    check = "--check" in argv
    bad = 0
    for name, edits in TARGETS:
        want = derive(name, edits)
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
