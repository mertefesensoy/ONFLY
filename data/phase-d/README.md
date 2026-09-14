# Phase D cross-platform evidence

These are the artifacts TX-01 and TX-02 are decided on: the same requests,
run on two platforms, recorded so the bytes can be compared rather than
described.

One directory per row of the SRS Section 8.3 determinism matrix:

| Directory | Platform | Compiler | Backends |
|---|---|---|---|
| `x86w/` | x86-64 Windows 11 | mingw32 gcc 6.3.0 | SOFT3E, SOFT2C, NATIVE |
| `s390x/` | Linux s390x, Ubuntu 24.04, under `qemu-system-s390x` (TCG) | gcc 13.3.0 | SOFT3E, SOFT2C, NATIVE |

## What each file is

| Name | Contents |
|---|---|
| `req-<net>.bin` | The ONFREQ dataset: 412-byte request records with the response portion zeroed (IR-JCL-03), built from IR-JCL-02 control cards by `tools/mkreq.py` |
| `rsp-<net>-<backend>.bin` | The ONFRSP dataset ONFLYENG wrote — the same records with the response portion filled in. **TX-01** |
| `gold-<net>-<backend>.txt` | The `GOLD` and `GOUT` lines of `tests/tstgld.c`, one per Section 8.4 request. **TX-02** |
| `PLATFORM.txt` | The NFR-OBS-01 run manifest. **Recorded but never compared** — `ONF_PLATID` and the compiler identifier are supposed to differ between rows; that is how a reader knows the two recordings came from different machines |

`<net>` is `path`, `srext`, `hop2` or `full`; `<backend>` is `soft` (SOFT3E),
`2c` (SOFT2C) or `nat` (NATIVE).

## What is compared, and what that means

```
python tests/run_tx.py --compare data/phase-d/x86w data/phase-d/s390x
```

Every file except `PLATFORM.txt` must be byte-identical. The comparator
reports the first differing byte of a record as a record number and an
offset, so a disagreement names a field rather than a file.

`path` and `srext` carry Section 8.4's golden requests, so agreement on them
is an **ACC-5** result. `hop2` and `full` do not: Section 8.4 defines no
request against either, and the three used here (SUGR at 0, 40 and 200 Hz,
seed 1) are a Phase D comparison set fixed by D-229. Agreement on those two
is cross-platform evidence, **not** a standing golden fingerprint — see
VL-84.

Durations: the standard 1000 ms everywhere except `full`, which runs at
100 ms (D-232). That is a floor rather than a preference — below about 40 ms
the full network's readouts never fire, and a run whose readouts never fire
cannot detect a kernel difference.

## Regenerating

```
python tests/run_tx.py --record     <outdir> <builddir>
python tests/run_tx.py --record-big <outdir> <builddir> 1000 100
```

`<builddir>` must contain `tstgld_*` and `onflyeng_*` for all three
backends; on s390x that means
`make ONFPLAT=s390x CC=gcc PYTHON=python3 BUILD=<builddir> test` first.

`tests/test_txcmp.py` checks that the comparator detects a one-bit change in
an ONF-FPRINT field and a changed return code in a gold line, so that a
clean comparison means something.

## What these files do not show

Nothing about MVS 3.8j or z/OS. TX-01 is defined against MVS response
records, no MVS engine exists yet, and it is therefore reported PARTIAL for
the whole of Phase D (D-219, VL-83). And the s390x row is a QEMU TCG
emulation, not hardware (VL-82).
