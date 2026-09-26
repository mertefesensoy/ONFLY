# Contributing to ONFLY

ONFLY is a personal project by Mert Efe Şensoy with one maintainer. This
file says how the project is run, how to take part, and the terms under which
contributions are accepted.

## How decisions are made

The contract is the specification, [`docs/ONFLY-SRS.md`](docs/ONFLY-SRS.md).
Every requirement has an ID (FR-, IR-, NR-, SR-, ACC-, NFR-), and three kinds
of record sit beside the requirements:

- **D-rows** (Appendix A.1) are decisions. Only the owner makes them, and each
  records the alternatives that were offered.
- **P-rows** (Appendix A.2) are proposals. A proposal stays a P-row until the
  owner decides it; it is never adopted by silence.
- **VL-rows** (Appendix D) are verification limits: what a result shows and,
  as plainly, what it does not.

Contributors never write D-rows. A change that needs a decision is proposed,
and the owner records the answer.

## Where to start

- **A question:** GitHub Discussions.
- **Something ONFLY does wrong:** an issue, using the bug report form.
- **Results from your own machine**, matching or not: an issue, using the
  replication report form. A report is a candidate for the determinism matrix
  (SRS Section 8.3), never an entry by itself.
- **A change to behaviour, a requirement or a recorded result:** an issue,
  using the proposal form. It carries the `proposal` label; the owner may
  record it as a P-row and decide it as a D-row.
- **A security problem:** privately, as [`SECURITY.md`](SECURITY.md) says,
  never in a public issue.

[`SUPPORT.md`](SUPPORT.md) says what is supported and how quickly to expect
an answer.

## Rules the code follows

These come from the specification and are checked by `make test` where a
check exists.

- **C dialect:** C89 plus `long long` (NR-04). The engine and the soft float
  layer contain no `float` or `double` and no floating-point literals
  (NR-05); every floating-point operation goes through the `onf_fp` API in
  the order Appendix C gives (NR-07).
- **Integers:** no reliance on signed overflow; shifts and divisions only on
  non-negative values (NR-11). Multi-byte fields are decoded with explicit
  byte shifts, never pointer casts over buffers (FR-LOD-05).
- **Names and lines:** external names are at most 8 characters, unique
  ignoring case (C-04), and source that must reach MVS stays within 80
  columns (D-93).
- **`third_party/`** is byte-identical to the published upstream archives
  (D-28, D-35). Pull requests that edit it are declined.
- **`generated/`** is produced from the master definition in `layout/` and is
  never edited by hand (IR-COM-01). Change the master definition and
  regenerate.
- **Bottom-up testing** (SRS Section 8.1): a level is tested only when the
  level below it passes on the platform concerned.
- **One name is kept out of this repository's text** by a committed guard,
  `tools/lint_name.py`, run by `make namelint` and by the `name-guard` CI
  job. If it reports your change, it prints only the path and line; rewrite
  that text.

## Before you open a pull request

Run the tests in strict mode, so that a missing package or file fails
instead of passing quietly:

    mingw32-make testfloat                          (Windows, MinGW)
    ONFLY_NOSKIP=1 mingw32-make test-nonet

    ONFLY_NOSKIP=1 make ONFPLAT=x86l PYTHON=python3 test-nonet   (Linux x86-64)

`test-nonet` needs no network file. With the two networks staged, as
[`REPLICATING.md`](REPLICATING.md) describes, run `test` instead. Either
target ends with a counted line, `ONFLY test: <p> PASS, <s> SKIP,
<q> PENDING, <e> EXEMPT`; paste it into the pull request with the platform,
compiler and version, and float backend it ran on.

A meaningful change comes with an implementation doc,
`docs/implementations/YYYY-MM-DD-<slug>.md`, written from
[`docs/implementations/_TEMPLATE.md`](docs/implementations/_TEMPLATE.md).
It says what changed, why, how it was verified, and what it does not prove.

A result is reported only from a command that was run, on the platform it
was run on. A pass on one compiler or platform is never reported as a pass on
another.

## Contribution terms

Under section D.6 of GitHub's Terms of Service, "Contributions Under
Repository License", a contribution to this repository is licensed under the
terms of the path it changes: the MIT licence in [`LICENSE`](LICENSE) for
ONFLY's own files, and the terms
[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) names for the paths it
lists (SRS D-581). No commit sign-off is required.

Two kinds of material are not accepted: anything under a non-commercial
licence, and third-party material without a licence that allows it here.
The first is why nothing derived from INTERCOMM enters this tree (SRS
D-132).

This section states the project's terms; it is not legal advice.

## Conduct

Everyone taking part follows the [code of conduct](CODE_OF_CONDUCT.md).
