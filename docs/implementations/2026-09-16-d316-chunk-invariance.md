# 2026-09-16 — D-316, D-317: the fingerprint must not depend on chunking

| Field | Value |
|---|---|
| Date | 2026-09-16 |
| Author | ONFLY senior engineer |
| Phase / gate | Phase E — MVS MVP (D-296); discharges an obligation Phase G inherits |
| Owner decisions relied on | D-316, D-317; and D-128, D-139, D-140, TBD-19 as context |
| Requirements touched | FR-SIM-04, IR-COM-05, NR-12, NR-13; ACC-5 indirectly |
| Open items closed | none — TBD-19 was already closed; this discharges the obligation it carried |

## 1. Problem / motivation

TBD-19 closed on 2026-09-12 with one sentence carried forward:

> D-140 requires the response fingerprint to be independent of K and of
> chunk boundaries, which **needs a requirement ID and a test before
> Phase G is built**.

It is worth being precise about why that matters, because "streaming a
picture of the fly's brain" sounds like a feature and this is not a
feature question.

D-140 did not choose chunking for visualisation. It chose it because
**VL-43 measured one request at N=1000 taking 507 seconds**, and Phase H
runs ONFLY under CICS, where holding a task that long is exactly what
Section 3.7's runaway-task note forbids. The work has to be breakable
into pieces whether or not anything is ever drawn on a screen.

And ACC-5 is this project's spine: nineteen golden fingerprints
reproduced across seven platform, compiler and backend rows, including
two different compilers on MVS 3.8j. **If dividing a run can change a
fingerprint by one bit, chunking does not cost a feature — it costs the
determinism claim**, and it would be discovered in Phase G with Phase E's
evidence already published.

## 2. What changed

| File | Change |
|---|---|
| `tests/test_chunk.py` | New. Sixteen tests in two stages, each with a negative case. |
| `oracle/onfly_oracle/kernel.py` | `_State`, `_init()`, `_advance()`, `run_chunked()`; `run()` delegates. The loop body is untouched. |
| `Makefile` | Runs `tests/test_chunk.py` in the `prep` target. |
| `docs/ONFLY-SRS.md` | P-15 proposes the requirement wording; VL-107 records the measurement. |

## 3. Implementation approach

### 3.1 Why it had to be staged

Nothing in the tree could run in chunks at all. `kernel.run()` built
`u`, `g`, `rfr`, the delay ring and the generator internally and looped
over `steps`; there was no `step()` and no way to resume. So the whole
property could not be asserted without something carrying state across a
boundary — which means editing O-1, the bit-exact reference.

D-317 therefore staged it: everything provable without touching O-1
first, then the refactor.

### 3.2 Stage 1 — what is provable with no change at all

Three properties, each with a **negative case**:

- **The PRNG stream.** FR-SIM-04 requires one stream per request, drawn
  in Appendix C's order, identical on every platform. Asserted identical
  whether drawn whole or in chunks of K ∈ {1, 2, 3, 7, 10, 100, 997},
  for seeds 0, 1, 7, 12345 and 999999999 — including the D-32 seed-0
  remap, which a per-chunk implementation would apply repeatedly.
- **The stimulus draws** layered on it, same chunk sizes. Two supporting
  assertions matter more than they look: that the rejection path
  actually fires, and that a draw consumes a **variable** number of u32.
  If a step always consumed exactly one, chunk invariance here would be
  arithmetically trivial and would prove nothing.
- **`fingerprint()`'s inputs.** It depends on total steps and on
  accumulated spike counts, so a chunked run must report totals, not a
  final chunk's. This is the one way chunking could change a fingerprint
  with no state mishandled at all.

The negative cases exist because a test that only shows the right thing
passing cannot tell you it would have caught the wrong thing. The
specific wrong thing — a driver that re-seeds per chunk — looks entirely
reasonable until you watch the stream diverge.

### 3.3 Stage 2 — the refactor, and the one subtle variable

`kernel.py` gained:

- `_State`, with `__slots__` naming exactly what a chunk hands to the
  next one: `u, g, rfr, spikes, first, force, is_stim, ring, gen,
  threshold, bias, t`.
- `_init(net, seed, rate_hz)` — the old initialisation block, verbatim.
- `_advance(net, st, nsteps)` — the old loop, with the locals rebound
  from the state.
- `run_chunked(net, seed, rate_hz, steps, k)`.

**The loop body did not move.** The rebinding matters: `u, g, rfr = st.u,
st.g, st.rfr` gives the *same list objects*, so `u[i] = ...` still
mutates the state and every line of the body reads exactly as it did.
That is not an optimisation — it is what keeps a refactor of a kernel
whose every line is normative (Appendix C) free of transcription risk.
The proof is the diff, which removes only four things:

    -def run(net, seed, rate_hz, steps):
    -    """Run the kernel and return (spikes, first_us) ...
    -    for t in range(steps):
    -    return spikes, first

**`t` is the subtle one, and it is the whole point.** The body uses it
three times — `t % net.delay` for the arrival slot, `(t + net.delay) %
net.delay` for the emission slot, and `(t + 1) * net.dt_us` for the
first-spike latency. `_advance` therefore iterates `range(st.t, st.t +
nsteps)`: `t` is a **global** step index, not a per-chunk one. A driver
that restarted it at zero each chunk would rotate the delay ring and
mis-date every latency, and would do so silently, returning a complete
and plausible answer.

`test_chunk.py` writes that driver — `_naive_chunked` — and asserts it is
caught. Without it, the suite could not distinguish a kernel that carries
state correctly from one where chunking happened not to matter.

### 3.4 What the fixture has to do to be worth anything

A chunk test on a network where nothing spikes would pass against almost
any bug. The fixture is a ring, 0 → 1 → … → 7 → 0, with weights large
enough that spikes really propagate, so the delay ring and IR-NET-06's
normative CSR accumulation order are both exercised — and there is an
explicit assertion that more than one neuron fired. K ∈ {17, 18, 19} is
in the list deliberately, bracketing the delay of 18, that being where a
ring-phase error surfaces first.

## 4. Mathematical / numerical details

No arithmetic changed. The claim is an algebraic one about the kernel,
and it is worth stating plainly:

Let `S(t)` be the loop-carried state after `t` steps and `F` the step
function. `run` computes `F^steps(S(0))`. `run_chunked` with chunk size
`k` computes `F^{n_m} ∘ … ∘ F^{n_1}(S(0))` where `Σ n_i = steps`. These
are equal **iff** `F` depends only on `S` and on the global step index
`t`, and `S` is carried in full. Stage 2 establishes both by
construction: `_State.__slots__` enumerates `S`, and `_advance` derives
`t` from `st.t` rather than from its own loop counter.

What remains unprovable at this level is whether a *different*
implementation — Phase G's C driver — carries `S` in full. That is what
P-15's wording would oblige and what a Phase G test must show against
the golden suite.

## 5. Design decisions

| Choice | Made by | Note |
|---|---|---|
| Close TBD-19's obligation now rather than in Phase G | **Owner, D-316** | ACC-5 is the spine; discovering this in Phase G means reopening it |
| Requirement ID **and** test, not one or the other | **Owner, D-316** | The ID is proposed in A.2, not enacted |
| Both stages: narrow first, then the refactor | **Owner, D-317** | Chosen over the narrow test alone and over the refactor alone |
| Rebind locals rather than rewrite the body | Architect | Every line of the kernel is normative; transcription risk is the hazard |
| A negative case per property | Architect | Otherwise the suite cannot demonstrate it would catch the error |
| A fixture that actually spikes | Architect | Chunk invariance on a silent network is vacuous |

## 6. Verification

### 6.1 The tests

Platform x86-64 Windows 11, CPython 3.13. **No float backend is
involved** — the oracle is plain Python floats (Section 8.2).

    python tests/test_chunk.py

    Ran 16 tests in 0.364s
    OK

Including `test_the_naive_driver_is_caught ... ok`, which is the one
that makes the rest evidence rather than decoration.

### 6.2 The refactor moved nothing

    mingw32-make kernel golden

    run_ker [SOFT3E backend]: 449 passed, 0 failed
    run_ker [NATIVE backend]: 449 passed, 0 failed
    run_ker [SOFT2C backend]: 449 passed, 0 failed
    run_gld [SOFT3E backend]: 20 passed, 0 failed
    run_gld [NATIVE backend]: 20 passed, 0 failed
    run_gld [SOFT2C backend]: 20 passed, 0 failed
    cmpgld: SOFT3E, NATIVE, SOFT2C agree on all 19 golden requests
            across 2 networks

That is the C engine agreeing with the refactored oracle bit-for-bit on
449 kernel cases per backend, and all nineteen Section 8.4 fingerprints
reproduced on three backends.

### 6.3 What this does **not** prove

- **This is the oracle, not the engine.** `engine/src/onfker.c` has no
  chunked entry point and none was added. What is established is that
  the *algorithm* carries no hidden per-call state — not that Phase G's
  C driver will carry it correctly.
- **No requirement text was changed.** P-15 proposes FR-SIM-10; until
  the owner accepts it, the property has a test and no ID.
- **x86-64 CPython only.** Nothing in this document was run on MVS 3.8j
  or Linux s390x. The `kernel golden` evidence covers SOFT3E, NATIVE and
  SOFT2C **on x86-64**.
- **Nothing was streamed.** D-139's spike events and membrane snapshots
  are not implemented, and `run_chunked` emits nothing between chunks.
  It is the reference shape of D-140's mechanism, not its
  implementation.
- **The fixture is synthetic**, eight neurons in a ring. The property is
  algebraic and does not depend on the network, but the assertion was
  not run against `srext` or `path`.

## 7. Related docs

- SRS Appendix B (TBD-19), Appendix A.1 (D-128, D-139, D-140, D-316,
  D-317), Appendix A.2 (P-15), Appendix D (VL-43, VL-107)
- SRS Section 3.3 (FR-SIM-04), 4.3 (IR-COM-05), 3.7 (the CICS
  runaway-task note), 8.3 (ACC-5)
- `docs/implementations/2026-09-16-d315-job-progress.md`
