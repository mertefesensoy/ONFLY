# Third-party components

Recorded per NFR-LIC-01 and owner decision D-28.

## Provenance

Both archives were downloaded over HTTPS from the upstream site on 2026-09-10
and extracted here. The `.zip` files themselves are not committed — they are
redundant next to their extracted contents — but their digests are recorded so
any copy can be verified against what this repository was built from.

| Archive | Bytes | SHA-256 |
|---|---|---|
| `SoftFloat-3e.zip` | 729637 | `21130ce885d35c1fe73fc1e1bf2244178167e05c6747cad5f450cc991714c746` |
| `TestFloat-3e.zip` | 429806 | `6d4bdf0096b48a653aa59fc203a9e5fe18b5a58d7a1b715107c7146776a0aad6` |
| `SoftFloat-2c.zip` | 108086 | `84c3adb85517c1bcaee580e8960eea8a6ff2e1049c7a0cabe1073622c17e33fd` |

Source: `https://www.jhauser.us/arithmetic/SoftFloat-3e.zip` and
`https://www.jhauser.us/arithmetic/TestFloat-3e.zip`
(SRS Appendix G, reference 5).

`SoftFloat-2c.zip` was downloaded on 2026-09-11 from
`http://www.jhauser.us/arithmetic/SoftFloat-2c.zip` — the same author and site,
which is why it was chosen over any redistribution. It was added under D-105,
which invokes NR-03 after Gate G1 measured that GCCMVS cannot build Release 3e
(SRS Appendix D, VL-19 and VL-21).

## Why two releases of SoftFloat are vendored

Release 3e is the soft backend on hosts that can build it, and its results are
what every ACC-5 fingerprint in the golden suite was computed with.

Release 2c is here for MVS. Its `bits32` build implements binary64 using only
32-bit integers — verified by inspection, not assumed: `bits32/softfloat.c`,
`bits32/softfloat-macros`, `bits32/templates/softfloat.h` and
`bits32/templates/softfloat-specialize` contain no occurrence of `bits64`,
`sbits64`, `long long` or `LIT64`. That matters because GCCMVS fails on 64-bit
integers in four independent ways, one of them silently (VL-19, VL-21), and a
build that never uses a 64-bit integer cannot meet any of them.

Whether 2c and 3e agree bit-for-bit on ONFLY's six binary64 operations is the
question D-106 front-loads. Until that is answered, **no claim is made here
that the two are interchangeable.**

## Licence

Berkeley SoftFloat Release 3e and TestFloat Release 3e, by John R. Hauser.
Copyright 2011–2018 The Regents of the University of California.
Three-clause BSD licence; full text in `SoftFloat-3e/COPYING.txt` and
`TestFloat-3e/COPYING.txt`. Permissive, and compatible with this repository
being public.

**Release 2c is under different terms and they are not BSD.** Its notice is in
`SoftFloat-2c/softfloat/README.txt` and repeated at the head of every source
file. In substance: the software is distributed as is and for free; use is
restricted to those who will tolerate all losses without recompense and who
indemnify the author and the International Computer Science Institute; and
distribution in whole or in part, and inclusion in a derivative work, are
**expressly permitted, even commercially**, provided the legal notices remain
prominent, a partial distribution says prominently that it is a subset, and the
documentation requirements stated in the source are met.

Two consequences for this repository, both acted on:

- The release is vendored **whole and verbatim**, so no "subset" notice is
  required and every notice remains where upstream put it.
- ONFLY's own 2c configuration files under `softfloat/c2c/` are a derivative
  work of upstream's templates. Each therefore carries a prominent notice that
  it is derivative and reproduces the three legal paragraphs, which is what
  clause (2) requires.

This is compatible with the repository's MIT licence (D-62) in the sense that
matters — MIT governs ONFLY's own code, and `third_party/` is redistributed
under its own terms, unchanged — but the terms differ from 3e's and are
recorded here rather than glossed as "BSD like the rest".

## Integrity

Nothing under `third_party/` is edited. ONFLY's flags-free requirement (D-34)
is met by ONFLY-owned files under `softfloat/` — a no-op `softfloat_raiseFlags`,
a hand-derived `roundPackToF64`, and a mechanically derived `subMagsF64` — so
this tree stays byte-identical to the upstream release (D-35).

## Known upstream defect

`SoftFloat-3e/source/ARM-VFPv2-defaultNaN/s_propagateNaNF128M.c` does not
compile: a stray semicolon terminates the `if` condition at line 57. It is
float128 code, unreachable from the binary64 operations ONFLY uses, and D-33
resolves this by compiling only the binary64 subset. The file is left exactly
as shipped.

## Build scope actually used (D-33, D-36)

Only the binary64 subset is compiled. `Makefile` lists it explicitly in
`SFSRCS`. `softfloat_state.c` and the specialization's `softfloat_raiseFlags.c`
are deliberately **not** built. Gate G1's record must state this scope rather
than claiming "SoftFloat 3e builds under GCCMVS".

TestFloat is vendored for TT-02 / oracle O-5 but is **not yet used**; no
TestFloat vector has been run in any session so far.
