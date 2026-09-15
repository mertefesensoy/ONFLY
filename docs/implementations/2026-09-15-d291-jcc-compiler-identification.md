# 2026-09-15 — D-291: the manifest names the compiler on the row that varies it

| Field | Value |
|---|---|
| Date | 2026-09-15 |
| Author | ONFLY senior engineer |
| Phase / gate | Phase E — MVS MVP (D-296) |
| Owner decisions relied on | D-291, D-296, D-297, D-298 |
| Requirements touched | NFR-OBS-01, ACC-5 (Section 8.3 row 7), NR-04, A-04 |
| Open items closed | none |

## 1. Problem / motivation

NFR-OBS-01 requires ONFLYENG to print, at the start of every run, a
manifest naming among other things its **compiler identification**. The
reason is not bookkeeping. Section 8.3 is a determinism matrix: each row
is the same source built by a different toolchain, and a fingerprint that
matches across rows is evidence only if each row can say which toolchain
produced it. `engine/src/onflyeng.c` carried that identification as a
preprocessor chain over `__GNUC__`, `__IBMC__`, `__MVS__` and `__CMS__`,
and `engine/include/onfplat.h` carried the platform over `__MVS__`,
`__CMS__`, `__s390x__`, `__s390__` and `_WIN32`.

JCC defines none of those. So when row 7 was filled on 2026-09-15
(D-281…D-286, VL-93), its own manifest read:

    ONF002I   COMPILER        UNKNOWN
    ONF002I   PLATFORM        UNKNOWN

The one row in the whole matrix that exists to **vary the compiler** was
the row that could not name it. The failure this leaves behind is not a
wrong number — the five `srext` fingerprints were right — it is that the
artifact proving cross-compiler determinism does not, on its face,
identify the compiler it is evidence about. A reader six months from now
has to take the surrounding prose's word for it.

D-291 chose the fix: ask JCC which macros it actually defines, then key
the branches on those, rather than passing `-DONF_CCID=...` from the
build tool (which would make the manifest report what the *tool* was told,
not what the *compiler* is).

## 2. What changed

| File | Change |
|---|---|
| `tools/mvsjcc.py` | `ccprobe_source()` stringifies through a two-level `XSTR`/`STR` pair, so the probe's expansion column reports macro **values** instead of macro **names**. |
| `engine/src/onflyeng.c` | `ONF_CCID` gains a final `#elif defined(JCC)` branch yielding `"JCC"`. |
| `engine/include/onfplat.h` | `ONF_PLATID` gains a final `#elif defined(JCC)` branch yielding `"MVS38J"`. |

## 3. Implementation approach

### 3.1 Measure before branching

The probe compiles a C program that, for each of the nineteen candidates
in `mvsjcc.CCMACROS`, prints either `DEFINED <expansion>` or `-`. Every
candidate is printed either way: in a 1,500-line MVS listing, "absent"
and "not defined" look identical, and the whole point is to find the one
macro that *is* there.

Its contract: no side effects, no input, exit 0 always; the deck passes
**no `-D` of its own**, which is what makes the result a statement about
JCC rather than about the job. I verified that by reading
`ccprobe_deck()` — its only `PARM` is the linkage editor's
`'NCAL,MAP,LIST,XREF,NORENT'`.

### 3.2 The probe was lying about expansions, and had to be fixed first

The first run reported:

    CCPROBE JCC                  DEFINED  <JCC>
    CCPROBE __STDC__             DEFINED  <__STDC__>

`__STDC__` is required by C89 to expand to `1`. Reporting it as
`__STDC__` is therefore self-evidently wrong, and the cause is a classic
one: in a function-like macro, the `#` operator **suppresses expansion of
its argument**. `#define STR(x) #x` applied directly to a macro name
stringises the name. The docstring claimed the column distinguished
`-D FOO` from `-D FOO=1`; it could not, because both print `<FOO>`.

The fix is the standard two-level idiom:

```c
#define STR(x) #x
#define XSTR(x) STR(x)
```

`XSTR`'s argument is expanded on substitution into `STR`, which then
stringises the expanded result. I verified this on the development host
**before** spending TK5 time on a re-run, by generating the probe source
from the same function and compiling it with the host gcc (§6.1).

This mattered to the outcome and not only to the tool's honesty: under
the old probe, `JCC` read `<JCC>`, which is consistent with `-D JCC` (no
value) *and* with any value. The corrected probe shows `JCC` is `1`.

### 3.3 The branches, and why they go last

Both new branches sit **immediately before the `#else`**, not first.

`JCC` is an un-prefixed, unreserved identifier — exactly the kind of name
another project or a build script might use. Placing the test last means
it is consulted only when every better-known macro is absent, so:

- x86-64 matches `__GNUC__` / `_WIN32` first;
- Linux s390x matches `__GNUC__` / `__s390x__` first;
- GCCMVS on TK5 matches `__GNUC__` and `__MVS__` first;
- only a build in which none of those is defined — which on this project
  means JCC — reaches the new branch.

That ordering is what converts "this change should be neutral" into
something checkable, and §6.2 checks it, including against a deliberate
`-DJCC=1` collision.

### 3.4 The platform branch infers more than it measures

`ONF_CCID` keying off a compiler macro is exact: `JCC` means JCC.
`ONF_PLATID` keying off the same macro is an **inference**, and the code
says so. JCC predefines no platform macro at all — not `__MVS__`, not
`__370__`, not `__EBCDIC__` — so there is nothing else to key on. The
inference is sound only because the one target ONFLY ever builds with JCC
is MVS 3.8j on TK5 (A-04, Section 8.3 row 7). Pointed at another target,
that line would print a falsehood. It is recorded as a limit, not hidden.

### 3.5 No version in the identifier

`ONF_CCID` is `"JCC"`, not `"JCC150"`. JCC exposes no version to the
preprocessor — the probe looked for `__JCC__`, `__LCC__`, `__lcc__` and
`__STDC_VERSION__` and found none of them. The string `1.50.00` is known
only from the comment JCC writes into its generated assembler (A-04),
which is a build artifact the engine cannot read. Encoding it in the
source would be asserting from the outside something the compiler never
told us — the precise failure mode D-291 rejected when it ruled out
passing `-DONF_CCID` from `tools/mvsjcc.py`. This also keeps the four
identifiers stylistically uniform: `GCC`, `IBMC`, `MVSC`, `JCC` all name a
compiler and none carries a version.

## 4. Mathematical / numerical details

None. This change is preprocessor text selection only. It introduces no
arithmetic, touches no `onf_fp` operation, and cannot alter a fingerprint:
`ONF_CCID` and `ONF_PLATID` are consumed by two `printf` calls in the
manifest and by nothing else. §6.3 is the measurement that confirms it.

## 5. Design decisions

| Choice | Made by | Note |
|---|---|---|
| Probe JCC and key branches on what it defines, rather than pass `-DONF_CCID` from the build tool | **Owner, D-291** | The manifest must report what the compiler is, not what the tool was told |
| Phase E is this session's phase | **Owner, D-296** | Asked afresh; not inherited from the previous session |
| D-291 is taken first | **Owner, D-297** | Smallest unfinished piece in Phase E |
| Both labs brought up | **Owner, D-298** | TK5 for this work; the guest for D-290 later |
| Branch placed last in each chain | Architect | Makes neutrality checkable rather than merely intended; guards an un-prefixed macro name |
| `"JCC"` without a version | Architect | The compiler exposes none; inventing one would repeat the mistake D-291 rejected |
| Fix the probe's stringification | Architect | It printed a column its own docstring described wrongly. Not an SRS deviation and not a design choice the SRS leaves open — a tool defect |

## 6. Verification

### 6.1 The two-level stringify, on x86 first

Platform x86-64 Windows, gcc (`__GNUC__` = 6), no ONFLY backend involved.
Source generated from the same `ccprobe_source()` the MVS deck uses:

    gcc -std=c89 -o ccprobe.exe ccprobe.c && ./ccprobe.exe

    CCPROBE __GNUC__             DEFINED  <6>
    CCPROBE __STDC__             DEFINED  <1>

Values, not names. Under the previous one-level version these same two
lines would have read `<__GNUC__>` and `<__STDC__>`.

### 6.2 Neutrality of the branches on x86

Platform x86-64 Windows, gcc, compiling the identical `#if` chain against
the edited `engine/include/onfplat.h`:

    gcc -std=c89 -Iengine/include -Igenerated ...      -> CCID=GCC PLATID=WIN32
    gcc -std=c89 -DJCC=1 -Iengine/include -Igenerated  -> CCID=GCC PLATID=WIN32

The second line is the collision probe: even when `JCC` **is** defined, a
platform carrying its own macros is unaffected, because the JCC branch is
last.

### 6.3 The probe on TK5, corrected

Platform MVS 3.8j TK5 under Hercules 4.9.1, compiler JCC 1.50.00,
codepage 819/1047, no float backend involved:

    python tools/mvsjcc.py --ccprobe

    mvsjcc: ccprobe 187 cards, 19 candidate macros
    CCPROBE JCC                  DEFINED  <1>
    CCPROBE __STDC__             DEFINED  <1>
    mvsjcc: 2 of 19 candidate macros defined

The other seventeen — including `__JCC__`, `__MVS__`, `__370__`,
`__S370__`, `__EBCDIC__`, `__BIG_ENDIAN__`, `__IBMC__`, `__GNUC__` and
`__STDC_VERSION__` — all report `-`.

### 6.4 ACC-5 row 7 re-run — the manifest, evidenced

Platform MVS 3.8j TK5 under Hercules 4.9.1.11612-SDL-gee86c4de, compiler
**JCC 1.50.00**, backend **SOFT2C**, Hercules codepage 819/1047, network
`srext` read from the installed dataset `HERC01.ONFLY.ENET` (D-286).

    python tools/mvsjcc.py --run --out data/phase-e/jcc

    mvsjcc: ONFJRUN, 8416 cards, 13 translation units, longest 80 columns,
            network srext from HERC01.ONFLY.ENET
    mvsjcc: ONFJRUN finished in 940.9 s
    13.38.00 JOB 307 $HASP373 ONFJRUN STARTED - INIT 1 - CLASS A - SYS TK5R
    13.53.40 JOB 307 $HASP395 ONFJRUN ENDED

All 22 steps at `COND CODE 0000` (SCRATCH, ALLOC, WRITEH, WRITEC,
COMP1…COMP13, PRELINK, LKED, SCRATCH2, GO, DUMP).

**The result D-291 exists for**, read out of `data/phase-e/jcc/ONFJRUN.txt`:

    ONF001I NETWORK LOADED N=501 E=10783 CRC=4577D74E
    ONF002I RUN MANIFEST
    ONF002I   ENGINE VERSION  0.5.0
    ONF002I   FLOAT BACKEND   SOFT2C
    ONF002I   COMPILER        JCC
    ONF002I   PLATFORM        MVS38J

Before this change those last two lines read `UNKNOWN` and `UNKNOWN`.

And the fingerprints are unmoved — which is the other half of the claim,
since a manifest fix that perturbed a result would be worse than the gap:

    python tools/mvsjcc.py --compare data/phase-e/jcc data/phase-d/x86w

    === ACC-5 row 7 vs the Section 8.4 fingerprints ===
      ok   G-15  fp=6C3F7272  golden=6C3F7272
      ok   G-16  fp=BAF81D91  golden=BAF81D91
      ok   G-17  fp=F9C7EE77  golden=F9C7EE77
      ok   G-18  fp=4FD0ED1E  golden=4FD0ED1E
      ok   G-19  fp=C4C320BC  golden=C4C320BC
    mvsjcc: ACC-5 row 7 PASS

The same run re-evidences TX-01 for `srext` under D-261's rule — all five
records `binary(8..411) yes` and `translated yes`, with `raw NO` on the
one `'chr'` field alone:

      note record 1: raw NO   binary(8..411) yes  translated yes
             chr[0:8] got e2e4c7d940404040 ('SUGR    ' as EBCDIC),
                      want 5355475220202020
      raw=False  binary=True  translated=True

### 6.5 What this does **not** prove

- **`ONF_CCID` = `"JCC"` is proven only where `JCC` is the sole macro
  defined.** It is a statement about which branch the preprocessor took,
  not about which binary ran. Nothing in the engine cross-checks the
  manifest against the object code.
- **No version is proven.** The manifest says `JCC`, not `JCC 1.50.00`.
  The version in this document comes from Gate G0's inventory (A-04), not
  from anything the engine observed.
- **`ONF_PLATID` = `"MVS38J"` under JCC is an inference from a compiler
  macro, not a platform measurement** (§3.4). It is correct for every
  build ONFLY performs and would be wrong for a JCC build targeting
  anything else. This is the one claim in this document that is true by
  project convention rather than by measurement.
- **Neutrality is measured on x86-64 only** (§6.2, gcc 6, Windows). That
  the GCCMVS and s390x builds are unaffected follows from the branch
  ordering and from `__GNUC__` being defined there, which Gate G0
  measured (`GCCMVS 3.2.3`) — but no GCCMVS or s390x build was run in
  this session to confirm it empirically.
- **The 940.9 s elapsed is not a performance figure.** It is wall clock
  on a host that was also building TestFloat; NFR-PERF-01 and ACC-6 are
  measured by TX-04 on a quiet host (D-288), not by this job.
- **Row 7 stands on the `srext` half of Section 8.4 only.** G-01…G-14
  have no JCC counterpart; that remains true after this change.

## 7. Related docs

- SRS Section 7 (NFR-OBS-01), Section 8.3 rows 6 and 7 (ACC-5),
  Section 2.6 (A-04), Appendix A.1 (D-291, D-296, D-297, D-298)
- `docs/implementations/2026-09-15-phase-e-slice-4-jcc-row-7.md` — the
  session that filled row 7 and found the `UNKNOWN`
- `docs/implementations/2026-09-15-phase-e-handover.md` §7 — the statement
  of this gap as "the single smallest piece of unfinished work"
