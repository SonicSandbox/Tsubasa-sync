---
type: spec
title: tsubasa — The Actor and Its Field Whitelist
desc: There are no human roles. There is one non-human actor that writes to a user's files, and this is the exhaustive list of what it may touch.
date: 2026-09-08
---

# 03 — Permissions

**There are no accounts, no roles and no sign-in.** `04-identity.md` does not exist.

There is exactly **one actor** — tsubasa itself — and it writes to files a person cares
about and cannot easily replace. This part enumerates what it may change.

---

## 🚨 The field whitelist

**Everything not on the left is refused loudly. Never silently dropped** — a silent drop
makes the caller believe it wrote.

| MAY change | MUST NEVER change |
| --- | --- |
| `Start` / `End` on `Dialogue:` lines | 🚨 **Cue text. Ever.** |
| `Start` / `End` on `Comment:` lines | Styles, fonts, `[V4+ Styles]`, `[V4 Styles]` |
| SRT sequence numbers (renumbered after a drop) | `[Script Info]` — except the opt-in marker line |
| SRT/VTT cue **blocks** removed when they end before t=0 | `[Fonts]` / `[Graphics]` embedded binary data |
| ⭐ **`D9` — RULED 2026-09-08:** cue blocks removed when they fall **inside a removed stretch** (a CM block the video does not carry). They cannot render correctly under any offset, so they are dropped, **counted, and reported** on the result line and in `Result.dropped_in_gap` | |
| The **filename**, on rename | 🚨 **The text encoding.** Same codec in, same codec out |
| A marker line, **only where invisible** (see below) | Line endings — CRLF stays CRLF, LF stays LF |
| | VTT cue settings (`align:`, `position:`) |
| | VTT `NOTE` / `STYLE` / `REGION` blocks |

### Why the encoding rule is in red

This is the single worst bug this class of tool can have, and `subsync` shipped it:

> A Shift-JIS caption decoded with `errors="replace"` had **all 346 cues turn to U+FFFD**.
> The timestamps are ASCII, so they survived — the alignment scored 4× chance, the tool
> said CONFIDENT, and it wrote a file that plays with **perfect timing and no readable
> text.**

Sniff the codec, write the same one back. `latin-1` is the byte-exact last resort,
because decode-then-encode round-trips every byte even when the guess is wrong.

---

## The in-file marker

Sonic ruled: **no `.synced` in the filename**, and *"add it to the first sub if that's
not destructive."* The honest answer is format-dependent.

| Format | Marker | Why |
| --- | --- | --- |
| `.ass` / `.ssa` | ✅ A `Comment:` line, or a `[Script Info]` field | **Non-rendering.** Genuinely free |
| `.vtt` | ✅ A `NOTE` block | Non-rendering by spec |
| `.srt` | ⛔ **Never touched** | SRT has **no comment syntax**. Any cue is visible on screen |

**Default: no marker at all.** The results DB answers *"was this synced"* for every
format. The in-file marker is a portability bonus for files copied to another machine.

**`--mark-name`** (off by default) appends `.synced` to the filename for people who want
it visible.

---

## The three outcomes

Every pair resolves to exactly one. **There is no fourth, and no silent success.**

| Outcome | Means | Action |
| --- | --- | --- |
| **CONFIDENT** | Measured, and it holds across the whole runtime | Written |
| **REFUSED** | It aligned, but not well enough to trust | ⛔ **Left untouched, reason stated** |
| **ERROR** | Could not be read at all | ⛔ **Left untouched, reason stated** |

🚨 **REFUSED and ERROR are different and must never be conflated.** *"Parsed zero cues"*
is not *"could not read the file"* — `subsync` was bitten by exactly that confusion twice
(WebVTT routed to the ASS parser, and a legally-reordered ASS `Format:` line), and both
times a real failure disguised itself as a different one.

### ⭐ AMENDED 2026-09-09 AT 3b — the test is *is there an offset to stand behind*

⚠ **`ERROR` is broader than its one-line description above**, and reading it literally
produces a wrong file. The operative question is **not** *was the file readable* — it is
**was it measured**:

| Case | The file read | An offset exists | Outcome |
| --- | --- | --- | --- |
| unreadable bytes, or a format with no reader | ⛔ no | no | **ERROR** |
| reads perfectly, contains **zero cues** | ✅ yes | no | **ERROR** |
| reads perfectly, **three cues** (`verdict._too_thin`) | ✅ yes | no | **ERROR** |
| ⭐ **runtime makes the pair impossible** (Stage 3's gate) | ✅ yes | **no — it never aligned** | **ERROR** |
| aligned, and the score did not clear the band | ✅ yes | yes | **REFUSED** |
| aligned, and one stretch does not hold | ✅ yes | yes | **REFUSED** |

⭐ **This is what makes `--force` correct without a special case.** `--force` overrides a
REFUSAL and never an ERROR *because ERROR means there is no measured offset to stand
behind*. Built the other way round first, the runtime gate returned REFUSED, `--force`
authorised a write, and `apply._render` correctly refused it for having no segments —
leaving the user a forced write that **silently did nothing while the report said it had
happened.** A confidently wrong report is worse than the missing write.

⚠ **`REFUSED` therefore promises something specific: *it aligned, and the answer was not
good enough.*** Anything that never reached the aligner is ERROR, however cleanly it read.

Per Sonic's ruling on the surface: **refusals and errors surface FIRST**, above the
successes, with the reason inline. The one thing needing attention never sits below 23
things that worked.

---

## The hand-back path

A refusal is only useful if a person can act on it. Every refusal states:

1. **What was measured** — match percentage and the verdict word
2. **Why it fell short** — which specific guard failed, in plain language
3. **What would change it** — e.g. *"no subtitle track in the video; try `--vad`"*

*"It failed"* is not actionable and is not acceptable output.

**The refusal the VAD path issues most, as measured** (`12-alignment.md` §5): *"the first
3:42 want a different offset (about +10 s) — this looks like a broadcast recording with a
commercial break; a subtitle from the streaming release of this episode will pair."* It
names the stretch, the size, the likely cause, and the fix.

---

## Nothing here contacts a person

No email, no push, no telemetry, **no network during a sync run**. Index updates are
explicit and separate. That entire class of risk — including the documented case of a
test suite sending real notifications from fixtures — is absent by construction.
