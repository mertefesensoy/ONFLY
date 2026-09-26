# Support

ONFLY is a personal project by Mert Efe Şensoy, its one maintainer. Every
channel below is answered by the maintainer personally.

## Where to go

| For | Use |
|---|---|
| A question | GitHub Discussions |
| Something ONFLY does wrong | An issue, with the bug report form |
| Your results, matching or not | An issue, with the replication report form |
| A change to behaviour, a requirement or a recorded result | An issue, with the proposal form |
| A security problem | Private vulnerability reporting, as [`SECURITY.md`](SECURITY.md) says |
| A conduct report | Email, as [`CODE_OF_CONDUCT.md`](CODE_OF_CONDUCT.md) says |

The maintainer aims to answer each issue within **14 days** (SRS D-580).

## What is supported

| Tier | What |
|---|---|
| Supported | The x86-64 build and test suite (`make test`, `test-nonet`, `quick`), and the evidence audit: the committed records and the checks that read them ([`REPLICATING.md`](REPLICATING.md), rung R0) |
| Best effort | Linux s390x under QEMU, and MVS 3.8j (the TK5 system under the Hercules emulator) |
| Unsupported | The `EXEC CICS` transaction under Raincode, the 3270 demonstration under INTERCOMM, and z/OS |

ONFLY has not run on IBM Z hardware, and the project does not have IBM Z
access yet (SRS VL-139).

## Tested platforms

As the [README](README.md) states them: x86-64 Windows 11 with 32-bit MinGW
gcc 6.3.0; Linux x86-64 (Ubuntu 26.04 under WSL2, gcc 15.2.0); Linux s390x
(Ubuntu 24.04, gcc 13.3.0) under QEMU; MVS 3.8j under SDL Hercules 4.9.1
with GCCMVS and JCC. macOS and arm64 are untested; a replication report from
either is welcome.

## What CI runs

Continuous integration runs the checks that need no network file on
GitHub-hosted runners, one Ubuntu and one Windows, with the compilers those
runners provide. Those are not the recorded toolchains, so a green run is a
smoke test: it is never evidence for the determinism matrix of SRS Section
8.3 (SRS D-586, VL-142).
