# 2026-09-11 — TBD-17 closed: a 3270 that reaches VTAM

| Field | Value |
|---|---|
| Date | 2026-09-11 |
| Author | Claude (ONFLY senior engineer session) |
| Phase / gate | Phase G (transaction demonstrator, second MVP) |
| Owner decisions relied on | D-127, D-131 |
| Requirements touched | Section 3.7 (BUZZ) |
| Open items closed | **TBD-17** |

## 1. Problem / motivation

TBD-17 asked for a 3270 client on the development host. Every MVS interaction in
this project so far has gone through the card reader, the printer and the
Hercules HTTP console — none of which is a terminal. D-127 requires Phase G's
transaction flow to be shown on a real 3270, and D-131 puts that 3270 behind
INTERCOMM. Without a terminal, Phase G could not be demonstrated **or driven**.

The owner installed wc3270 4.5ga6 from `x3270.miraheze.org`. That alone does not
close TBD-17: a package being present is not evidence that a session reaches the
thing Phase G needs.

## 2. What changed

| File | Change |
|---|---|
| `tools/tn3270.py` | New. Connects to TK5, drives a 3270 session and captures the screen; reports whether VTAM's logon prompt was reached. |
| `docs/ONFLY-SRS.md` | Added VL-39; struck TBD-17 in Appendix B; removed it from the Phase G blocker list. |

## 3. Implementation approach

`ws3270.exe` — the scriptable build shipped alongside the windowed `wc3270.exe` —
reads actions on stdin and writes screen rows prefixed `data: `, interleaved with
a status line and `ok` after each action.

`capture(host, port, enters, raw)` issues `Connect`, `Wait(3270Mode)`, *N* ×
(`Enter`, `Wait(Output)`), `Ascii`, `Quit`, then strips the status noise so what
comes back is the screen a person would see. Contract: returns the screen as a
string, or `None` if `ws3270.exe` cannot be found or run. Side effect: occupies
one of TK5's local 3270 devices for the duration and releases it on `Quit`; no
state on the guest changes.

**The one non-obvious fact, recorded in the module docstring so it is not
rediscovered:** passing the host on `ws3270`'s command line *hangs* — it
connects but never reads stdin, and the script times out with nothing on stdout.
Issuing `Connect(host:port)` as the first **action** works immediately. This cost
a debugging round and is invisible once it works.

`Wait(10,3270Mode)` and `Wait(10,Output)` are used rather than sleeps, so the
tool blocks on the actual protocol state instead of guessing a duration.

## 4. Mathematical / numerical details

None.

## 5. Design decisions

**Closing on the logon prompt, not on the connection.** Hercules answers a
connection with its own device banner (`Device number: 0:00C0`). Stopping there
would only have shown that a socket opened. Pressing Enter moves to VTAM's
screen — `Terminal CUU0C0`, `RUNNING TK5`, `Logon ===>` — and *that* is the path
Phase G needs, because D-131 puts the demonstration behind INTERCOMM and
INTERCOMM runs as a VTAM APPL a terminal logs on to. The tool's exit code keys
on `Logon ===>` for exactly this reason.

**Deliberately not logging on.** Consuming a TSO session would change lab state
and produce no additional evidence about whether the terminal path works.

**Why a tool rather than a one-off command.** Two reasons, and the second is
worth more than TBD-17. First, it lets the closure be re-checked instead of
trusted. Second, `ws3270` being scriptable means Phase G's 3270 flow can be
**regression-tested rather than only performed** — a demonstration that can be
asserted against is a different kind of artefact from one that has to be shown
live, and that possibility was not evident when D-127 was written.

**Not wired into `make test`.** It requires a running TK5, and the suite must
stay runnable on a bare checkout — the same rule that keeps `tests/raincode`
out of the build.

## 6. Verification

With TK5 running:

```bash
python tools/tn3270.py
```

Expected, and observed on 2026-09-11: the VTAM screen ending

```
Logon ===>
                                                            RUNNING  TK5
tn3270: reached VTAM (Logon prompt present)
```

exit 0. `--enter 0` stops at Hercules' device banner instead, which is the useful
contrast: it shows the connection is real before VTAM is involved at all.

Failure modes are distinguished rather than collapsed: exit 2 means `ws3270.exe`
was not found (with the install URL printed), exit 1 means the session connected
but no VTAM prompt appeared.

**What this does not verify** is in VL-39: no logon was performed, INTERCOMM was
not running so nothing here shows it accepting a session, and no transaction, BMS
map or ONFLY screen is involved. Raincode's QIX terminal server speaks TN3270 to
the same client, but VL-37 established it will not start without a licence, so
that half stays untestable here.

## 7. Related docs

- `docs/ONFLY-SRS.md` — VL-39, D-127, D-131, Appendix B TBD-17 (struck).
- `docs/implementations/2026-09-11-tbc18-closed-intercomm-out-of-tree.md` — the
  other Phase G blocker closed the same day.
