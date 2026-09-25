# Reading guide

`ONFLY-SRS.md` is the specification and the project's whole record in one
file, about 860 KB. Nobody should start by reading it top to bottom. This
page suggests where to start, depending on what you want.

## If you have ten minutes

1. [`overview.md`](overview.md): what ONFLY is, what has been shown and on
   what, and what it does not show.
2. The repository's [`README.md`](../README.md): status, the commands you can
   run today, the limits and the licence.

## If you want to check a result

Every result in the specification names the command that produced it, the
platform, the compiler and the floating-point backend, and what it does not
prove. The places to look, in [`ONFLY-SRS.md`](ONFLY-SRS.md):

| Section | What it holds |
|---|---|
| 6.4 | The acceptance criteria ACC-1 to ACC-7, including the two changed after the results were seen |
| 8.3 | The determinism matrix: which platform, backend and compiler produced which fingerprints |
| 8.4 | The nineteen golden requests |
| 9 | The gates and phases, and what each one's completion rests on |
| Appendix A.1 | Every owner decision, D-01 onwards, with the alternatives that were offered |
| Appendix A.2 | The engineer's proposals, P-01 onwards, kept apart until decided |
| Appendix B | Open items, TBC and TBD |
| Appendix C | The normative simulation kernel, operation by operation |
| Appendix D | The verification limits, VL-01 onwards: what each result cannot show |

The recordings those results rest on are under [`../data/`](../data/README.md).

## If you want to know why something is the way it is

| Directory | What it holds |
|---|---|
| [`plan/`](plan/) | Plans drafted before work started, each approved or changed by the owner before any code was written |
| [`implementations/`](implementations/) | One record per piece of work: what changed, why, how it was verified, and what it did not prove |
| [`status/`](status/) | Dated status snapshots |
| [`media/`](media/) | Animations of the live view |

`malecns-celltype-mapping.md` and the three `malecns-*.json` files record how
the sugar-sensing and MN9 neurons were identified in the MaleCNS data and how
connection signs were assigned. `ONFLY-SRS.docx` is an export of the
specification; the Markdown file is the source of truth.

## Words used in a particular way

"Mainframe", in this repository's older records, means the emulated
System/370 running MVS 3.8j under Hercules on an x86-64 laptop, never IBM Z
hardware. Appendix F of the specification defines this and the other terms.
