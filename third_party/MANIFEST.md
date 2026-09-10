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

Source: `https://www.jhauser.us/arithmetic/SoftFloat-3e.zip` and
`https://www.jhauser.us/arithmetic/TestFloat-3e.zip`
(SRS Appendix G, reference 5).

## Licence

Berkeley SoftFloat Release 3e and TestFloat Release 3e, by John R. Hauser.
Copyright 2011–2018 The Regents of the University of California.
Three-clause BSD licence; full text in `SoftFloat-3e/COPYING.txt` and
`TestFloat-3e/COPYING.txt`. Permissive, and compatible with this repository
being public.

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
