# ONFLY: an overview

## Not run on IBM Z

> **ONFLY has not run on IBM Z hardware. The project does not have IBM Z
> access yet.** Every MVS result in this repository comes from MVS 3.8j
> running under the Hercules emulator, and every s390x result from Linux
> running under QEMU, both on one x86-64 laptop. Nothing here has run on
> z/OS or on IBM CICS Transaction Server.

The owner confirmed this on 2026-09-24, and the specification keeps it as a
standing limit (`docs/ONFLY-SRS.md`, VL-139, citing D-491 and D-492).

## What ONFLY is

ONFLY simulates the sugar-to-feeding circuit of the male fruit fly: a
501-neuron subcircuit taken from the MaleCNS v1.0 connectome, run with the
leaky integrate-and-fire model of Shiu et al. (2024) in a portable C89 engine
with a COBOL batch driver.

A request names a stimulus, a rate, a duration and a random seed. The answer
gives, for each feeding motor neuron (MN9), its spike count and its first
spike latency, with a fingerprint of the whole response. The engine does its
IEEE 754 arithmetic in software (Berkeley SoftFloat) where the platform has
no IEEE floating point, as MVS does not, so that the same request can be
compared byte for byte across platforms.

The subcircuit is drawn from the 184,099-neuron annotated MaleCNS network,
which holds 39.0% of the dataset's synapses, and it carries one fitted input
term standing in for the neurons it leaves out. It is not a whole brain.

## What has been shown, and on what

**Determinism across platforms.** All 19 golden requests produce identical
fingerprints and response records on x86-64 (a Python reference and three C
floating-point builds) and on Linux s390x under QEMU. On MVS 3.8j under
Hercules with the GCCMVS compiler the fingerprints are identical, and the
response records are identical byte for byte apart from one text field that
MVS stores in EBCDIC. With a second MVS compiler, JCC, all 19 reproduce the
same way. The z/OS row of the matrix is empty. Identical fingerprints show
that the platforms agree; they do not show that any of them is correct.

**The science, measured on x86-64 only.** Sugar at 40, 60, 120 and 200 Hz
made the MN9 neurons fire in all 30 seeds at every rate, and zero sugar
produced zero spikes in all 501 neurons. The subcircuit stays within 10% of
the full annotated network's MN9 rate at 40, 60, 120 and 200 Hz; 10 Hz is
excluded because the full network's rate is too variable there to test
against. At 40 Hz the margin is smaller than the reference's own standard
error, and a campaign re-measured with new seeds is estimated to pass 52 to
60% of the time.

**Agreement with Shiu et al.** Compared with their model of the female
FlyWire connectome, re-run from their published code, ONFLY's model on the
184,099-neuron annotated MaleCNS network, with the synaptic weight
re-calibrated to 0.2969 mV and a pharyngeal and taste-peg sugar input, rises
with sugar in the same shape but fires more at low rates: 3.67 Hz at 10 Hz
where the reference is silent, and 14.35 Hz against 4.73 Hz at 40 Hz. No
single synaptic weight removes that gap, so the agreement shows consistency
of shape, not identity.

**Two acceptance criteria were changed after we saw the results:** ACC-3 no
longer tests 10 Hz, and ACC-4 no longer tests magnitude. Both changes and the
failing numbers are recorded in the specification (D-202, D-340, D-341).

## The emulated platforms

The s390x results come from Ubuntu 24.04 running under QEMU's
instruction-by-instruction emulation, so they show the code gives the same
results on a big-endian system, but say nothing about floating point on real
s390x hardware.

The three-step BUZZ batch job (COBOL driver, C engine, COBOL report) ran end
to end on emulated MVS 3.8j with return code 0 and printed the five
shipped-network golden fingerprints. Under Hercules 4.9.1 on an Intel Core
i7-13650HX laptop, one standard 1000 ms request on the shipped network used
161 s of emulated CPU, inside the project's 10-minute budget; this is an
emulator figure from one run and says nothing about IBM Z performance.

The emulated MVS job streams its spike data to the host while it is still
running, and for the five shipped-network golden requests that stream is
byte-identical to the x86-64 one once line endings are normalised. Comparing
the two streams line by line exposed a GCCMVS code-generation fault that had
turned every +0.0 in the MVS kernel into a tiny subnormal, a difference no
fingerprint had ever caught; the fault is worked around, not fully
characterised.

## The transaction demonstrator

The transaction is written in real `EXEC CICS` and runs on x86-64 Windows
under Raincode's CICS-compatible runtime, not under IBM CICS; its menu-screen
program has never executed for lack of a licence, and running it
concurrently is untested.

On the emulated MVS 3.8j lab, typing a request on a 3270 session under
INTERCOMM, a transaction monitor that is not CICS, starts an ONFLY batch run
and then shows its result and golden fingerprint. This part cannot be
reproduced from the repository, because INTERCOMM's licence keeps its code
out.

## What someone else can reproduce

The C engine, the Python reference and the x86-64 test suite are public. The
two network files the suite runs on are not distributed yet, so today a
reader can check the recorded evidence against itself but cannot re-run the
suite from a clone. The MVS results need your own TK5 and Hercules setup and
hours of emulated CPU. The README lists the commands.

## What comes next

Phase F, z/OS, waits on IBM Z access, which the project does not have yet.
Phase H, IBM CICS, waits on Phase F and on a CICS environment. Until then,
the work is making what exists easy for someone else to check.

## Where to read more

* `README.md`: status, commands, limits, licence.
* `docs/ONFLY-SRS.md`: the specification; Section 8.3 is the determinism
  matrix, Section 6.4 the acceptance criteria, Appendix A the decisions and
  Appendix D what each result does not prove.
* `THIRD_PARTY_NOTICES.md`: third-party components and data terms.

ONFLY is a personal project by Mert Efe Şensoy and is not affiliated with or
endorsed by IBM or by any organisation whose data, software or tools it uses;
the trademark notices are in `README.md` and `THIRD_PARTY_NOTICES.md`.
