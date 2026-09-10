# -*- coding: utf-8 -*-
"""NR-05 build-time lint: no float, no double, no floating-point literals.

NR-05 requires that the engine and the soft float layer contain no `float` or
`double` types and no floating-point literals, and that a build-time lint
enforce it.  The threat is specific and quiet: GCCMVS on S/370 has no IEEE
hardware, so a stray `double` compiles happily to *hexadecimal* floating point.
Nothing fails.  The program just produces different numbers on MVS than
everywhere else, which is precisely the failure ONFLY exists to rule out.

Binary64 values travel as opaque bit patterns through the onf_fp API instead.

Method.  Comments and string literals are removed first, then the remaining
text is searched for:
  * the keywords `float` and `double` as whole words.  SoftFloat's own
    `float64_t` and `float32_t` typedef names are not matches, because the
    character after `float` is a word character and the word boundary fails.
  * floating-point constants: 1.0, .5, 1e10, 1.0f, and hex floats like 0x1p3.

`a.b` and `arr[0].f` are not matched: a decimal literal requires a digit
immediately adjacent to the point.

Run:  python tools/lint_nr05.py <path> [<path> ...]
Exit status 0 when clean, 1 when any violation is found.
"""
import io
import os
import re
import sys

# A floating-point constant in C89, plus the C99 hex form for completeness.
FP_LITERAL = re.compile(r"""
      (?<![\w.])                      # not glued to an identifier or another dot
      (?:
          0[xX][0-9a-fA-F]*\.?[0-9a-fA-F]*[pP][+-]?\d+   # hex float: 0x1p3
        | \d+\.\d*(?:[eE][+-]?\d+)?                      # 1.  1.5  1.5e3
        | \.\d+(?:[eE][+-]?\d+)?                         # .5  .5e3
        | \d+[eE][+-]?\d+                                # 1e5
      )
      [fFlL]?
""", re.VERBOSE)

KEYWORD = re.compile(r"\b(float|double)\b")

C_EXT = (".c", ".h")


def strip_comments_and_strings(text):
    """Blank out comments and string/char literals, preserving line structure.

    Replacing rather than deleting keeps reported line numbers correct.
    """
    out = []
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        two = text[i:i + 2]
        if two == "/*":
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            out.append("".join(c if c == "\n" else " " for c in text[i:j]))
            i = j
        elif two == "//":
            j = text.find("\n", i)
            j = n if j < 0 else j
            out.append(" " * (j - i))
            i = j
        elif ch in "\"'":
            quote = ch
            j = i + 1
            while j < n:
                if text[j] == "\\":
                    j += 2
                    continue
                if text[j] == quote:
                    j += 1
                    break
                j += 1
            out.append("".join(c if c == "\n" else " " for c in text[i:j]))
            i = j
        else:
            out.append(ch)
            i += 1
    return "".join(out)


def lint_file(path):
    raw = io.open(path, encoding="utf-8", errors="replace").read()
    code = strip_comments_and_strings(raw)
    problems = []
    for lineno, line in enumerate(code.split("\n"), 1):
        for m in KEYWORD.finditer(line):
            problems.append((lineno, "keyword '%s'" % m.group(1), line.strip()))
        for m in FP_LITERAL.finditer(line):
            problems.append((lineno, "float literal '%s'" % m.group(0), line.strip()))
    return problems


def iter_sources(paths):
    for p in paths:
        if os.path.isfile(p):
            yield p
        else:
            for root, dirs, files in os.walk(p):
                dirs.sort()
                for f in sorted(files):
                    if f.endswith(C_EXT):
                        yield os.path.join(root, f)


def main(argv):
    if len(argv) < 2:
        sys.stderr.write("usage: lint_nr05.py <path> [<path> ...]\n")
        return 2
    total = 0
    scanned = 0
    for path in iter_sources(argv[1:]):
        scanned += 1
        problems = lint_file(path)
        for lineno, what, text in problems:
            total += 1
            print("NR-05 %s:%d: %s" % (path.replace("\\", "/"), lineno, what))
            print("      %s" % text[:100])
    print("lint_nr05: %d files scanned, %d violations" % (scanned, total))
    return 1 if total else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
