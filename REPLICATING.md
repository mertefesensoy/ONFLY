# Replicating ONFLY

This is the ladder of things a reader can re-run, from checking the recorded
evidence to repeating the emulated-MVS runs. Each rung says what it proves
and, as plainly, what it does not. Wall clocks are **as recorded on the
owner's host** (Intel Core i7-13650HX, 15.6 GB RAM), not predictions for
other machines.

ONFLY has not run on IBM Z hardware, and the project does not have IBM Z
access yet (SRS VL-139). Every s390x and MVS result comes from emulators,
QEMU and Hercules, on one x86-64 laptop.

## Before you start

- **Python.** Make a fresh virtual environment and install
  `requirements.txt` into it. The pins are the versions the recorded results
  were produced with; Python 3.14 gets one different pin, pyarrow 22.0.0,
  because pyarrow 21.0.0 has no Python 3.14 wheel (SRS D-547).
- **A C compiler and GNU Make.** The recorded Windows toolchain is
  MinGW.org GCC 6.3.0 (32-bit i686) with `mingw32-make`. Any other compiler
  is a new data point, not a reproduction of a recorded row.
- **The two networks.** `srext` and `path` are not in git: they are data,
  to be distributed beside the code as release assets of the first tag,
  `v0.5.0` (SRS D-544, D-545). **No release has been published yet**, so
  until one is, this step needs the files from another source. Put the two
  `.bin` files and their `SHA256SUMS` in one directory, check them, and
  place them:

      (cd <dir> && sha256sum -c SHA256SUMS)
      python tools/fixtures.py --from <dir>
      python tools/fixtures.py --check

  `--check` must end with both networks `OK`; `hop2` and `full` report
  `NOT DISTRIBUTED`, which is expected. Read `data/networks/NETWORKS-NOTICE.md`
  before using the files: it carries their attribution and licence terms.

## Strict mode

`make test` ends with a counted line:

    ONFLY test: <p> PASS, <s> SKIP, <q> PENDING, <e> EXEMPT (...)

PASS counts make targets; SKIP, PENDING and EXEMPT count checks that did not
run. **Run with `ONFLY_NOSKIP=1`** to turn every skip into a failure, so that
a missing package or file cannot pass quietly. Eleven checks are exempt,
because a decision keeps what they need out of every clone (SRS D-548,
D-555): two need the INTERCOMM subsystem that D-132 keeps out of this MIT
tree; three need MaleCNS source files, which are not distributed (D-545);
and six are TE-08's whole-program replay on the three backends, which needs
a memory limit ONFLYENG does not expose. They print as EXEMPT and are
listed at the end of every run.

## The ladder

### R0. Check the committed evidence (seconds)

    python tests/run_tx.py --compare data/phase-d/x86w data/phase-d/s390x
    python tests/run_mvsrun.py

**Proves** that the owner's recordings agree with each other: the x86-64 and
Linux s390x response records are byte-identical, and the MVS decks and
recordings pass their structural checks. **Does not prove** that anything
was run: this rung only reads files.

### R1. Build and test on x86-64 (about 11 minutes on Windows)

On Windows with MinGW:

    mingw32-make testfloat
    ONFLY_NOSKIP=1 mingw32-make test

On Linux x86-64 (SRS D-550 names the platform `x86l`):

    make ONFPLAT=x86l PYTHON=python3 testfloat
    ONFLY_NOSKIP=1 make ONFPLAT=x86l PYTHON=python3 test

Two shorter targets exist. `test-nonet` runs the 23 targets that need no
network file (109 s on the owner's Windows host, in a clone with no
network), so it can run before the networks are staged. `quick` builds the
engine and checks the 19 golden fingerprints only (392 s there).

**Proves** that this build reproduces the recorded fingerprints of all 19
golden requests on your toolchain, across the three floating-point backends
(SOFT3E, SOFT2C, NATIVE). **Does not prove** correctness: identical outputs
show consistency, not that the model is right (SRS VL-05). It says nothing
about MVS, and on any compiler but the recorded one it is a new data point.

### R2a. The science checks, re-measured (minutes)

    mingw32-make runner                  (Linux: make ONFPLAT=x86l PYTHON=python3 runner)
    python prep/extract.py --acc1 data/networks/onfnet-malecns-v1.0-srext.bin --label srext --jobs 8
    python prep/extract.py --acc3-file data/networks/onfnet-malecns-v1.0-srext.bin --label srext --jobs 8
    python prep/acc4.py --reeval data/calibration/acc4.json

Recorded: 48 s for ACC-1 (VL-105) and 80 s for ACC-3 (VL-98); the ACC-4
re-evaluation runs no simulation. **Proves** that the recorded ACC-1 and
ACC-3 numbers reproduce on your NATIVE build against the committed
reference, and that ACC-4's verdict follows from its recorded measurement.
**Does not prove** that a re-seeded campaign passes: ACC-3 at 40 Hz lies
within the reference's own precision, and a re-measured campaign passes 52
to 60% of the time (VL-114). Two criteria were changed after the results
were seen: ACC-3 no longer tests 10 Hz, and ACC-4 no longer tests magnitude
(D-202, D-340, D-341, D-448); both changes and the failing numbers are in
the SRS.

### R2b. The science, re-measured from the source data (hours)

Download MaleCNS v1.0 (1,109,008,094 bytes), regenerate the networks with
`prep/emit.py`, calibrate with `prep/calibrate.py`, and re-run ACC-4 with
`prep/acc4.py --jobs 14` (6,971 s recorded, VL-97) on a host of the 15.6 GB
RAM class. The recipe is below. **Proves** the science result as a
measurement. **Does not prove** anything on MVS or s390x.

**FlyWire's non-commercial terms.** The reference curve ONFLY calibrates
against was produced by re-running Shiu et al.'s code on FlyWire data, which
FlyWire's guidelines place under CC BY-NC 4.0; see `THIRD_PARTY_NOTICES.md`
section 6. The Shiu re-run itself needs brian2 (`requirements-shiu.txt`, in
a separate environment), which is no longer installed on the owner's host,
so that step has not been repeated since it was recorded (VL-88).

**The regeneration recipe.** This is the chain in the order the tools' own
documentation gives it (`prep/calibrate.py`, `prep/emit.py`,
`prep/extract.py`). It has not been re-run end to end since the networks
were admitted on 2026-09-13, so treat it as a recipe to check, not a tested
script. Work in a scratch clone: the chain rewrites both tracked manifests
and every network file, so it ends by checking the networks and restoring
the manifests.

    python tools/fixtures.py --malecns annotations neurotransmitters weights
    python prep/calibrate.py --cache
    python prep/emit.py both
    python prep/extract.py --rank --jobs 14
    python prep/extract.py --ratebias --jobs 8
    python prep/extract.py --refixture
    python prep/extract.py --constbias --jobs 14
    python prep/extract.py --admit
    python tools/fixtures.py --check
    git checkout -- data/networks/MANIFEST.json data/malecns/MANIFEST.json

The first line places the three MaleCNS files once you have downloaded them;
`data/malecns/MANIFEST.json` holds their digests. `--rank` alone is 240
full-brain runs of 1000 ms. `--refixture` writes `path`, `hop2` and `full`;
`--admit` writes `srext`, and refuses, before it writes anything, when the
measured subcircuit it must match is absent or differs. A regenerated
network is accepted only if `fixtures.py --check` reports it `OK` against
the committed digests.

### R3. Linux s390x under QEMU (hours)

See `docs/lab.md`. **Proves** the same results on a big-endian system, under
emulation. **Does not prove** anything about floating point on real s390x
hardware (VL-01, VL-82).

### R4. MVS 3.8j under Hercules (hours of emulated CPU)

See `docs/lab.md` for the archives, their digests, the codepage step and the
safety notes. **Proves** that GCCMVS and JCC each reproduce all 19 golden
fingerprints under emulation (VL-91, VL-138). **Does not prove** IBM Z
behaviour or performance.

### R5. The EXEC CICS transaction under Raincode

`mingw32-make cics`, on Windows with Raincode's free edition and .NET.
**Proves** that the EXEC CICS source runs in process under a CICS-compatible
runtime. **Does not prove** anything about IBM CICS: it is not IBM CICS, its
menu-screen program has never executed for lack of a licence, and running it
concurrently is untested (VL-37). Owner-demonstrated; not part of the tested
ladder.

### R6. The 3270 flow under INTERCOMM

Not reproducible from this repository, by design: INTERCOMM's licence keeps
its code out of this tree (SRS D-132).

### R7. The live view

    pip install -r requirements-live.txt
    python tools/liveview.py --engine build/onflyeng_nat.exe

About 20 s for the x86-64 half. **Proves** that the x86-64 stream renders.
The emulated MVS job's stream was shown byte-identical to the x86-64 one for
the five `srext` requests once line endings are normalised (D-414, VL-136),
which this rung does not repeat.
