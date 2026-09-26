# Security policy

## Reporting a vulnerability

Report it privately through GitHub's private vulnerability reporting: the
repository's **Security** tab, then **Report a vulnerability**
(https://github.com/mertefesensoy/ONFLY/security/advisories/new). Please do
not open a public issue for it (SRS D-582).

ONFLY has one maintainer and no security team. [`SUPPORT.md`](SUPPORT.md)
says how the project is supported.

## What is in scope

**Files that reach the engine.** ONFLYENG reads two inputs it cannot trust:
the network file (ONFNET) and the request records (ONFREQ). Before it
simulates anything it checks the network's magic constant, byte-order
sentinel, format version, header CRC-32, declared length and payload CRC-32
(SRS FR-LOD-02) and, on MVS 3.8j, the memory the network needs against a
configured limit (FR-LOD-04; no limit is configured on other platforms). Every abnormal outcome is meant to end with an `ONFnnn` message
and a defined return code (NFR-REL-01, Appendix E). A file that makes the
engine crash, hang, read or write outside its buffers, or return a wrong
answer instead of an `ONFnnn` message is in scope.

**The local lab tooling.** The scripts under `tools/` that build and submit
jobs to the emulated MVS system, drive the Linux s390x virtual machine, or
drive 3270 sessions, for example if one could be made to run a command it
was not meant to.

## What is not in scope

- `third_party/`: vendored upstream code, reported to its upstream.
- The emulators, the TK5 system, the compilers and other tools ONFLY uses
  but does not include (listed in
  [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)).
- Whether the model is scientifically right: open an ordinary issue.

## Supported versions

There is no release yet. Until the first one, only the `main` branch is
supported.
