# The ONFLY labs: emulated MVS 3.8j and Linux s390x

ONFLY's MVS and s390x results come from emulators on one x86-64 laptop:
MVS 3.8j (TK5) under the Hercules emulator, and Ubuntu 24.04 for s390x
under QEMU. ONFLY has not run on IBM Z hardware, and the project does not
have IBM Z access yet (SRS VL-139). Nothing in this guide changes that.

This guide says what the labs are made of, how to check the downloads, and
how to run them safely. It is what `REPLICATING.md` rung R4 (MVS) and rung
R3 (s390x) rely on.

## Safety first

**The TK5 card reader runs any JCL sent to it by whoever can connect to its
port.** On a lab that another machine can reach, that is remote job
submission with no password.

- **Bind the card reader (port 3505), the Hercules console (8038) and the
  3270 port (3270) to 127.0.0.1, or firewall them, and never run the lab on
  an untrusted network.**
- **Change TK5's default password for the HERC01 user on any lab that
  another machine can reach.**
- The s390x guest listens for ssh on host port 2222. Keep it on localhost
  as well.

## MVS 3.8j (TK5) under Hercules

### What it is made of

| Archive | Bytes | SHA-256 |
|---|---|---|
| `Hercules-4.9.1-x64.zip` | 8,280,669 | `c94522f60139c43d08ecdfbd317be0a85a1f02b73cbb74df47a40040f73152c9` |
| `mvs-tk5.zip` | 498,312,872 | `710d002843631322810a276dd42c793fda458548dc64d86e2914a62db7425f84` |
| `mvstk5-update5.zip` | 350,462,458 | `c44fb64cc365a3a94fa9ce312394408d22a729b73797ef6b06d1688b05cc7212` |

These digests were computed on 2026-09-26 from the copies the ONFLY results
were produced with. Check a download against them before using it, for
example with `sha256sum <file>` or PowerShell's `Get-FileHash <file>`. A
different digest means a different build, whose results are a new data
point, not a reproduction.

Two limits travel with these files. The running TK5 does not report its own
Update level, so "Update 5" rests on which archive was installed, not on a
measurement (SRS VL-86). And the lab is an emulator: an MVS result shows
what this software does under Hercules, not on IBM Z hardware (VL-01,
VL-139).

### The codepage step, after every Hercules start

ONFLY's C source reaches the GCCMVS compiler through the card reader, and on
Hercules' `default` codepage one character of C, `|`, arrives as a byte
GCCMVS rejects (SRS VL-18). Set the codepage on the Hercules console after
every start, because a restart silently returns it to `default`:

    codepage 819/1047

`tools/mvsg0.py` and the MVS tools set it themselves before submitting a
job, and say so.

### Running the MVS rungs

With TK5 up and the codepage set:

| Command | What it runs | Recorded cost on the owner's host |
|---|---|---|
| `python tools/mvsrun.py --run` | ACC-5 row 6: the engine under GCCMVS, the five `srext` golden requests | 855.7 s wall for the whole job (VL-91) |
| `python tools/mvsrun.py --net path --run` | Row 6's `path` half, fourteen requests | GO step CPU 63 min 04.79 s (VL-91) |
| `python tools/mvsjcc.py --run` | ACC-5 row 7: the same under JCC, `srext` | 940.9 s wall (VL-96) |
| `python tools/mvsjcc.py --net path --run` | Row 7's `path` half | GO step CPU 79 min 51.84 s (VL-138) |
| `python tools/mvsrun.py --buzz` | ACC-7: the three-step BUZZ job | STEP2 14 min 04.18 s for five requests (VL-104) |

The figures are as recorded on the owner's host (Intel Core i7-13650HX,
SDL Hercules 4.9.1), one run each. They are emulator figures and say nothing
about IBM Z performance.

## Linux s390x under QEMU

The big-endian platform is a full s390x system VM, not a cross-compiler
(SRS D-215): the Ubuntu 24.04 s390x cloud image booted by
`qemu-system-s390x` with 4096 MB and two CPUs, reached by ssh on host port
2222, with the ONFLY tree shared into the guest at `/onfly`. Inside it the
build is the same Makefile:

    make ONFPLAT=s390x CC=gcc PYTHON=python3 BUILD=/tmp/b390 test

`BUILD` must be guest-local so that object files stay off the shared
folder. Under QEMU's instruction-by-instruction emulation, compiled C runs
roughly ten times slower than on the x86-64 host and Python slower still,
and the s390x results say nothing
about floating point on real s390x hardware (VL-01, VL-82).

**The guest's bring-up script and its cloud-init data are not in the
repository yet.** They are committed without keys once secret scanning is on
for the repository, which is slice F's step F7 of the launch plan (SRS
D-552).
