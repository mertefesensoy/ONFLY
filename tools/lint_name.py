# -*- coding: utf-8 -*-
"""Keep one name out of ONFLY's public text (D-479, D-484, D-507).

WHY THIS EXISTS
---------------
From 2026-09-24 no new ONFLY text names the hosted IBM Z access program
that Phase F depends on (D-479), and slice B of the open-source launch
plan (P-41, D-488) took the existing occurrences out of the current tree
by a forward scrub (D-484).  The scrub fixes what the tree says today; a
rule kept only in prose is broken by the next paste.  So it is checked.

This is NOT the IR-NAM names-file check.  That is the `names` target,
tests/run_names.py.  This one is the `namelint` target (D-507).

HOW IT MATCHES WITHOUT STORING THE WORD (D-503)
-----------------------------------------------
Text is decoded one line at a time the way P-41's scan 11.0 decodes it --
NFKC, casefold, HTML entities unescaped, %XX unquoted -- and then folded
once more, so a letter written as an entity or an escape is caught too.
A *word* is a run of [a-z0-9] in the decoded text.  The *stream* is every
word joined, across lines, so a name split by a line break, a soft
hyphen, a zero-width space, Markdown emphasis or an entity is still one
run in the stream.  Every window of the token's length is hashed with a
fixed salt and compared with one stored SHA-256 digest.  A salted digest
of one known word can be reversed by brute force: this keeps the word out
of the text, not secret.

A few ordinary words contain the token.  They are stored the same way,
as salted digests, and a hit passes only when it lies wholly inside ONE
word whose digest is on that list.  A hit spanning two words never
passes, which is what fails "the" run together with the name although
the stream joins the two.

MODES
-----
--tree         Every tracked path and file, Office files member by
               member; the `namelint` target.  A SKIP, not a failure,
               when git cannot read the tree (D-233, D-510).
--staged       Added lines of the index, joined per hunk, every added
               path, and the whole index blob of any staged binary or
               Office file.  The pre-commit hook.
--message F    A commit message, up to git's scissors line.  The
               commit-msg hook.
--install-hooks
               Copies this file into the common git directory and writes
               pre-commit and commit-msg hooks that run the copy, so every
               worktree is checked, including one whose branch predates
               this file.  Re-run it after changing this file.
--self-test    The engine against a synthetic token built at run time, so
               it needs no secret and states no word (D-506).  With
               ONFLY_NAME_B64 set it also checks the stored digest and the
               real token; with ONFLY_ALLOW_B64 set (comma-separated
               base64 words) it checks the allowlist the same way.
--extra-env V  Also match the comma-separated base64 terms held in the
               environment variable V, with no allowlist.  Fails closed
               when V is unset (D-509): this is for the owner's private
               local hook, not for the committed ones.

Output is a path, a line and a count, never the matched text, because CI
logs are public (P-41).  Exit 0 clean, 1 on a finding, 2 on an error.
The hook modes fail closed: any git, read or unzip error is exit 2.

WHAT IT CANNOT DO
-----------------
It recognises the token, not a description of the program.  Hooks do not
run for commits made in the GitHub web UI, and commit-msg does not run
for messages carried over by cherry-pick or rebase.  --staged sees added
lines only, so a name split across an unchanged line and an added one is
missed there; --tree sees it.  Images are scanned as bytes, not read.

usage:  python tools/lint_name.py --tree | --staged | --message FILE
                                  | --install-hooks | --self-test
                                  [--extra-env VAR]
"""
import base64
import bisect
import hashlib
import html
import io
import os
import re
import shutil
import subprocess
import sys
import unicodedata
import urllib.parse
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Where git runs.  --tree and --install-hooks work on the repository this
# file is in.  The hook modes run a COPY that lives in the git directory,
# so there they use the directory git starts the hook in, which is the
# top of the worktree being committed, with git's own GIT_INDEX_FILE.
GIT_CWD = [ROOT]

# D-503.  The token and the allowlisted words, as salted SHA-256 digests.
SALT = bytes.fromhex("afff6f38851552250de80e52387aa6be")
TOKEN_LEN = 6
TOKEN_DIGEST = ("70880f4d9c125eafcc41d41a1116ee08"
                "20fb918c7a824771468cbe687b26646b")
ALLOW_DIGESTS = frozenset((
    "1dc679e7797e0b962dc23c2d6d4bbb289531a51d1bf5805f6c0c83f95cb1c07e",
    "55cb21fdc29cd806a3d32e56ba7abbda26ca783bbaa99bfa43a8bb542231f411",
    "8b217ad911a4861f87e13c6f1257c092776711faf753031000166babb05b3e77",
    "a06bef6eede1547393567c6e712df34b37f3161e24494155a3ba5089a2161fd9",
    "ce0b9d9a01e4a4bf47f67aa5a24e971c7a3f45a5c9778b65ec544b7b16c1d4af",
    "fe8fa9233515e3dce41ab0722ec1f04c6c4b6e06c1fa95b8a73ccf1d35d32288",
))

OFFICE = (".docx", ".xlsx", ".pptx")
# Closing tags that end a Word or slide paragraph, a shared string or a
# cell.  Every other tag is dropped with no separator, so the runs of one
# paragraph join into one line.
PARA_END = re.compile(r"</(?:w:p|a:p|si|is|c|w:tc|a:tc)>")
TAG = re.compile(r"<[^>]*>")
WORD = re.compile(r"[a-z0-9]+")
NONWORD = re.compile(r"[^a-z0-9]")
HUNK = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")
SCISSORS = "# ------------------------ >8 ------------------------"
MARK = "# onfly-lint-name hook (D-507)"


class LintError(Exception):
    """A failure to read something; the hook modes fail closed on it."""


def decode(line):
    """One line as 11.0 decodes it, then folded again.

    11.0 casefolds before it unescapes, so a letter written as `&#88;` or
    `%58` comes out upper case and 11.0's [a-z0-9] filter drops it.  The
    second NFKC and casefold close that gap; they can only add hits.
    """
    t = unicodedata.normalize("NFKC", line).casefold()
    t = urllib.parse.unquote(html.unescape(t))
    return unicodedata.normalize("NFKC", t).casefold()


class Matcher(object):
    """The token by digest, the allowlist by digest, extra terms plain."""

    def __init__(self, salt, length, digest, allow, extra=()):
        self.salt = salt
        self.length = length
        self.digest = digest
        self.allow = frozenset(allow)
        self.extra = tuple(extra)

    def hashed(self, s):
        return hashlib.sha256(self.salt + s.encode("ascii")).hexdigest()

    def hits(self, stream):
        """(start, length, allowable) for every match in the stream.

        Each DISTINCT window is hashed once, which is what keeps a scan
        of the whole tree to seconds.  A window whose digest matches is
        the token itself, held only in memory, and every place it occurs
        is then found by plain search.
        """
        out = []
        n, k = len(stream), self.length
        if n >= k:
            wins = set(map(stream.__getitem__,
                           map(slice, range(n - k + 1), range(k, n + 1))))
            for w in wins:
                if self.hashed(w) == self.digest:
                    i = stream.find(w)
                    while i >= 0:
                        out.append((i, k, True))
                        i = stream.find(w, i + 1)
        for term in self.extra:
            i = stream.find(term)
            while i >= 0:
                out.append((i, len(term), False))
                i = stream.find(term, i + 1)
        return out


def scan_lines(m, lines):
    """Count unallowed hits per label over (label, text) pairs.

    The stream is built line by line so that each hit can be traced to
    its line and its word; it must equal the stream of the whole text
    decoded at once, or the per-line decoding has lost something and
    that is an error, not a pass.
    """
    lines = list(lines)
    words, starts, labels = [], [], []
    pos = 0
    for label, text in lines:
        for w in WORD.findall(decode(text)):
            words.append(w)
            starts.append(pos)
            labels.append(label)
            pos += len(w)
    stream = "".join(words)
    whole = NONWORD.sub("", decode("\n".join(t for _, t in lines)))
    if whole != stream:
        raise LintError("line-by-line decoding differs from whole-text")
    found = {}
    for start, length, allowable in m.hits(stream):
        a = bisect.bisect_right(starts, start) - 1
        b = bisect.bisect_right(starts, start + length - 1) - 1
        if allowable and a == b and m.hashed(words[a]) in m.allow:
            continue
        found[labels[a]] = found.get(labels[a], 0) + 1
    return found


def text_lines(raw):
    """(line number, text) for a file read as UTF-8, as 11.1 reads it."""
    text = raw.decode("utf-8", "ignore")
    return [(i, t) for i, t in enumerate(text.split("\n"), 1)]


def office_lines(raw):
    """(member:paragraph, text) for every member of an Office zip.

    Every member, whatever its extension: the .rels files hold hyperlink
    targets.  Two views of each.  The text view drops tags with no
    separator and breaks only at a paragraph, string or cell end, so a
    name split across two runs of one paragraph is one word.  The markup
    view keeps attributes, where hyperlink targets and alt text live.
    """
    z = zipfile.ZipFile(io.BytesIO(raw))
    out = []
    for name in z.namelist():
        xml = z.read(name).decode("utf-8", "ignore")
        text = TAG.sub("", PARA_END.sub("\n", xml))
        for i, t in enumerate(text.split("\n"), 1):
            out.append(("%s:%d" % (name, i), t))
        out.append(("%s:markup" % name, xml.replace("\n", " ")))
    return out


def added_hunks(diff):
    """[[(line, text), ...], ...]: the added lines of a -U0 diff.

    One list per hunk, numbered in the new file.  Lines of one hunk are
    contiguous, so they are scanned as one stream and a name split over
    two added lines is caught; separate hunks are not joined.
    """
    hunks, cur, n = [], None, 0
    for line in diff.split("\n"):
        m = HUNK.match(line)
        if m:
            cur = []
            hunks.append(cur)
            n = int(m.group(1))
            continue
        if cur is None or line.startswith("+++"):
            continue
        if line.startswith("+"):
            cur.append((n, line[1:].rstrip("\r")))
            n += 1
    return [h for h in hunks if h]


def message_lines(text):
    """A commit message up to git's scissors line, numbered."""
    out = []
    for i, t in enumerate(text.split("\n"), 1):
        if t.rstrip("\r") == SCISSORS:
            break
        out.append((i, t))
    return out


def file_lines(path, raw):
    """What a file contributes: its path, then its content."""
    lines = [("path", path)]
    if path.lower().endswith(OFFICE):
        try:
            lines.extend(office_lines(raw))
        except (zipfile.BadZipFile, KeyError, ValueError) as exc:
            raise LintError("%s: cannot unzip (%s)"
                            % (path, type(exc).__name__))
    else:
        lines.extend(text_lines(raw))
    return lines


def git(args, text=True):
    try:
        out = subprocess.run(["git", "-c", "core.quotepath=off"] + args,
                             cwd=GIT_CWD[0], stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, timeout=120)
    except Exception as exc:
        raise LintError("cannot run git: %s" % type(exc).__name__)
    if out.returncode != 0:
        raise LintError("git %s failed" % args[0])
    return out.stdout.decode("utf-8", "replace") if text else out.stdout


def where(label):
    if label == "path":
        return "in the path"
    if isinstance(label, int):
        return "line %d" % label
    return "at %s" % label


def report(path, found):
    n = 0
    order = lambda x: (isinstance(x, str), x if isinstance(x, int) else 0,
                       str(x))
    for label in sorted(found, key=order):
        print("lint_name: %s: %s: %d occurrence(s)"
              % (path, where(label), found[label]))
        n += found[label]
    return n


def run_tree(m):
    try:
        listing = git(["ls-files", "-z"])
    except LintError:
        # D-510, on D-233's precedent: the Linux s390x guest reads this
        # tree over 9p, where .git is a file naming a Windows path, and
        # git reports "not a git repository".  The rule is repository
        # content, identical wherever the tree is checked out, and the
        # development host always runs it in full.
        # Imported here, so the guard's normal path and its hook modes
        # depend on nothing they did not depend on before.
        import onfres
        onfres.skip("namelint/git", "git cannot read this tree, so the "
                    "tracked file list is unavailable (D-233, D-510)")
        return 0
    paths = [p for p in listing.split("\0") if p]
    total = files = 0
    for path in paths:
        full = os.path.join(ROOT, path)
        try:
            with open(full, "rb") as f:
                raw = f.read()
        except (IOError, OSError):
            raw = git(["cat-file", "blob", ":" + path], text=False)
        found = scan_lines(m, file_lines(path, raw))
        if found:
            files += 1
            total += report(path, found)
    if total:
        print("lint_name: %d occurrence(s) in %d file(s)" % (total, files))
        return 1
    print("lint_name: tree clean, %d tracked files" % len(paths))
    return 0


def run_staged(m):
    listing = git(["diff", "--cached", "--name-only", "-z",
                   "--diff-filter=ACMR"])
    total = 0
    for path in [p for p in listing.split("\0") if p]:
        blob = git(["cat-file", "blob", ":" + path], text=False)
        if path.lower().endswith(OFFICE) or b"\0" in blob[:8000]:
            found = scan_lines(m, file_lines(path, blob))
            total += report(path, found)
            continue
        total += report(path, scan_lines(m, [("path", path)]))
        diff = git(["diff", "--cached", "-U0", "--no-color",
                    "--no-ext-diff", "--no-renames", "--", path])
        for hunk in added_hunks(diff):
            total += report(path, scan_lines(m, hunk))
    if total:
        print("lint_name: commit refused, %d occurrence(s) staged" % total)
        return 1
    return 0


def run_message(m, path):
    try:
        with open(path, "rb") as f:
            text = f.read().decode("utf-8", "replace")
    except (IOError, OSError):
        raise LintError("cannot read the commit message")
    total = report("commit message", scan_lines(m, message_lines(text)))
    if total:
        print("lint_name: commit refused, %d occurrence(s) in the "
              "message" % total)
        return 1
    return 0


HOOK = """#!/bin/sh
%s
# Written by tools/lint_name.py --install-hooks.  Fails closed.
g=$(git rev-parse --git-common-dir) || exit 1
command -v python >/dev/null 2>&1 || {
    echo "lint_name: python not found, so the commit is refused" >&2
    exit 1
}
exec python "$g/hooks/onfly_lint_name.py" %s
"""


def install_hooks():
    try:
        hp = git(["config", "--get-all", "core.hooksPath"]).strip()
    except LintError:
        hp = ""
    if hp:
        raise LintError("core.hooksPath is set; hooks there are not ours")
    common = git(["rev-parse", "--git-common-dir"]).strip()
    hooks = os.path.join(ROOT, common, "hooks")
    if not os.path.isdir(hooks):
        os.makedirs(hooks)
    bodies = {"pre-commit": "--staged", "commit-msg": '--message "$1"'}
    for name in bodies:
        p = os.path.join(hooks, name)
        if os.path.exists(p):
            with open(p, "rb") as f:
                if MARK.encode("ascii") not in f.read():
                    raise LintError("%s exists and is not ours" % name)
    shutil.copyfile(os.path.abspath(__file__),
                    os.path.join(hooks, "onfly_lint_name.py"))
    for name, arg in bodies.items():
        p = os.path.join(hooks, name)
        with open(p, "wb") as f:
            f.write((HOOK % (MARK, arg)).encode("ascii"))
        os.chmod(p, 0o755)
        print("lint_name: installed %s" % name)
    return 0


def extra_terms(var):
    """D-509: terms from an environment variable; unset fails closed."""
    val = os.environ.get(var, "")
    if not val.strip():
        raise LintError("%s is unset, so the private check fails closed"
                        % var)
    terms = []
    for item in val.split(","):
        try:
            t = base64.b64decode(item.strip()).decode("utf-8")
        except Exception:
            raise LintError("%s holds an entry that is not base64" % var)
        t = NONWORD.sub("", decode(t))
        if not t:
            raise LintError("%s holds an empty entry" % var)
        terms.append(t)
    return terms


# ---------------------------------------------------------------- self-test

def must_catch(tok):
    """(case, lines) that must each count exactly one hit, built from tok.

    Built at run time from whatever token is given, so the committed file
    states no word (D-503, D-506).
    """
    t = tok
    fw = chr(0xFF41 + ord(t[0]) - 97)
    return [
        ("plain", [(1, t)]),
        ("after 'the '", [(1, "the " + t)]),
        ("run into 'the'", [(1, "the" + t)]),
        ("upper case", [(1, t.upper())]),
        ("prefixed Z", [(1, "Z" + t)]),
        ("after 'IBM Z '", [(1, "IBM Z " + t.capitalize())]),
        ("no-break space", [(1, t[:2] + u" " + t[2:])]),
        ("zero-width space", [(1, t[:2] + u"​" + t[2:])]),
        ("soft hyphen", [(1, t[:3] + u"­" + t[3:])]),
        ("line break", [(1, "a " + t[:3]), (2, t[3:] + " b")]),
        ("emphasis *", [(1, "*" + t[:2] + "*" + t[2:])]),
        ("emphasis **", [(1, "**" + t[:1] + "**" + t[1:])]),
        ("emphasis _", [(1, "_" + t[:3] + "_" + t[3:])]),
        ("entity between", [(1, t[:2] + "&shy;" + t[2:])]),
        ("decimal entity", [(1, "&#%d;" % ord(t[0]) + t[1:])]),
        ("hex entity, upper", [(1, "&#x%X;" % ord(t[0].upper()) + t[1:])]),
        ("percent escape", [(1, "%%%02X" % ord(t[0]) + t[1:])]),
        ("fullwidth letter", [(1, fw + t[1:])]),
        ("in a URL", [(1, "https://example.org/" + t + "/x")]),
    ]


def self_test():
    checks = [0, 0]

    def check(name, ok):
        checks[0] += 1
        if not ok:
            checks[1] += 1
            print("lint_name: self-test FAIL: %s" % name)

    salt = b"onfly-self-test!"
    tok = "".join(chr(97 + (7 * i + 11) % 26) for i in range(TOKEN_LEN))
    word = "q" + tok + "s"
    syn = Matcher(salt, len(tok),
                  hashlib.sha256(salt + tok.encode()).hexdigest(),
                  [hashlib.sha256(salt + word.encode()).hexdigest()])
    check("the synthetic token is not the real one",
          Matcher(SALT, TOKEN_LEN, TOKEN_DIGEST, ()).hashed(tok)
          != TOKEN_DIGEST)

    def count(m, lines):
        return sum(scan_lines(m, lines).values())

    for name, lines in must_catch(tok):
        check("caught: " + name, count(syn, lines) == 1)
    for name, text in (("allowlisted word", word),
                       ("capitalised", word.capitalize()),
                       ("upper case", word.upper()),
                       ("after 'the '", "the " + word),
                       ("in a sentence", "we " + word + ", then stop."),
                       ("ordinary text", "an ordinary sentence")):
        check("passed: " + name, count(syn, [(1, text)]) == 0)
    check("allowlisted word then the token counts one",
          count(syn, [(1, word + " " + tok)]) == 1)
    check("allowlisted word run into 'the' is not the word",
          count(syn, [(1, "the" + word)]) == 1)
    check("allowlisted word split over two lines is caught",
          count(syn, [(1, word[:3]), (2, word[3:])]) == 1)
    check("reported on the line the hit starts",
          scan_lines(syn, [(1, "a"), (2, "b " + tok), (3, "c")])
          == {2: 1})
    check("in a path", count(syn, [("path", "docs/" + tok + ".md")]) == 1)

    # Office: a name split across two runs, and one in a hyperlink target.
    runs = ("<w:document><w:body><w:p><w:r><w:t>%s</w:t></w:r><w:r>"
            "<w:t>%s</w:t></w:r></w:p></w:body></w:document>"
            % (tok[:2], tok[2:]))
    rels = ('<Relationships><Relationship Id="rId1" '
            'Target="https://example.org/%s" TargetMode="External"/>'
            '</Relationships>' % tok)
    clean = ("<w:document><w:body><w:p><w:r><w:t>%s</w:t></w:r></w:p>"
             "</w:body></w:document>" % word)
    for name, member, xml, want in (
            ("docx, split across runs", "word/document.xml", runs, True),
            ("docx, hyperlink target", "word/_rels/document.xml.rels",
             rels, True),
            ("docx, allowlisted word only", "word/document.xml", clean,
             False)):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as z:
            z.writestr(member, xml)
        got = count(syn, file_lines("x.docx", buf.getvalue()))
        check(("caught: " if want else "passed: ") + name,
              (got > 0) == want)

    diff = ("diff --git a/f b/f\n--- a/f\n+++ b/f\n"
            "@@ -3,0 +4,2 @@\n+keep " + tok[:3] + "\n+" + tok[3:] + "\n"
            "@@ -9 +11 @@\n-" + tok + " was here\n+gone\n")
    hunks = added_hunks(diff)
    check("diff: two hunks of added lines",
          [[n for n, _ in h] for h in hunks] == [[4, 5], [11]])
    check("diff: a name split over added lines is caught",
          sum(count(syn, h) for h in hunks) == 1)
    msg = "Subject\n\nBody.\n" + SCISSORS + "\n-" + tok + "\n"
    check("message: text after the scissors is not scanned",
          count(syn, message_lines(msg)) == 0)
    check("message: text before the scissors is",
          count(syn, message_lines(tok + "\n" + SCISSORS + "\n")) == 1)

    var = "ONFLY_LINT_NAME_SELF_TEST"
    other = "".join(chr(97 + (5 * i + 3) % 26) for i in range(7))
    os.environ[var] = base64.b64encode(other.encode()).decode()
    ext = Matcher(salt, len(tok), syn.digest, syn.allow, extra_terms(var))
    check("extra term caught", count(ext, [(1, "x " + other + " y")]) == 1)
    del os.environ[var]
    try:
        extra_terms(var)
        check("extra-env unset fails closed", False)
    except LintError:
        check("extra-env unset fails closed", True)

    real = os.environ.get("ONFLY_NAME_B64", "")
    if real:
        rt = base64.b64decode(real).decode().lower()
        rm = Matcher(SALT, TOKEN_LEN, TOKEN_DIGEST, ALLOW_DIGESTS)
        check("real: stored digest is the token's",
              len(rt) == TOKEN_LEN and rm.hashed(rt) == TOKEN_DIGEST)
        for name, lines in must_catch(rt):
            check("real, caught: " + name, count(rm, lines) == 1)
        allow = os.environ.get("ONFLY_ALLOW_B64", "")
        for item in [a for a in allow.split(",") if a]:
            w = base64.b64decode(item).decode().lower()
            check("real: an allowlisted word's digest is stored",
                  rm.hashed(w) in ALLOW_DIGESTS)
            for form in (w, w.capitalize(), w.upper()):
                check("real, passed: an allowlisted word",
                      count(rm, [(1, form)]) == 0)
        print("lint_name: real token checked%s"
              % (", allowlist checked" if allow else ""))
    else:
        print("lint_name: real token not checked (ONFLY_NAME_B64 unset)")
    print("lint_name: self-test %d checks, %d failed" % tuple(checks))
    return 1 if checks[1] else 0


def main(argv):
    args = list(argv)
    extra = ()
    if "--extra-env" in args:
        i = args.index("--extra-env")
        if i + 1 >= len(args):
            print("lint_name: --extra-env needs a variable name")
            return 2
        var = args[i + 1]
        del args[i:i + 2]
    else:
        var = None
    try:
        if var:
            extra = extra_terms(var)
        m = Matcher(SALT, TOKEN_LEN, TOKEN_DIGEST, ALLOW_DIGESTS, extra)
        if args == ["--self-test"]:
            return self_test()
        if args == ["--tree"]:
            return run_tree(m)
        if args == ["--staged"]:
            GIT_CWD[0] = None
            return run_staged(m)
        if len(args) == 2 and args[0] == "--message":
            GIT_CWD[0] = None
            return run_message(m, args[1])
        if args == ["--install-hooks"]:
            return install_hooks()
    except LintError as exc:
        print("lint_name: ERROR %s" % exc)
        return 2
    sys.stderr.write(__doc__[__doc__.index("usage:"):])
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
