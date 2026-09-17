---
type: spec
title: tsubasa — Scope
desc: The objective in Sonic's words, the launch list as re-scoped 2026-09-08 against twenty probes, the ratified stack, the licence, and the performance target as measured numbers. Supersedes the 2026-09-07 version.
date: 2026-09-08
---

# 01 — Scope

> ⚠️ **RE-SCOPED 2026-09-08.** Fourteen probes ran after the 2026-09-07 sign-off; seven of
> them reversed or settled something in this file. The evidence is `08-probes.md`; this
> file carries only the conclusions. Decisions still Sonic's are marked `D#` and listed
> in `HANDOFF.md`.

## The objective, in Sonic's words

> *"Every subtitle and video file paired correctly, and the subtitles perfectly in sync
> with the audio, all quite quickly and extremely accurate on laptop hardware. Most cases
> will include an existing subtitle, but that can't be the crutch. And my use case is
> japanese but works for all languages. And all subs renamed / replaced so everything is
> clean without dupes (unless user wants). This also needs to integrate into my surasura
> app… so asking it to look at 2 folders if the video and subs are in a different place is
> important as well."*

And, 2026-09-08: *"rather than offer the tool like other services offer, we automatically
do it… so it's more like magic and just works. This includes breaks during the episode
that some versions have that some subs don't… every part of the episode locks in well.
This section needs to be optimized as well… really fast so it can be included in other
packages."*

**In one line:** *the only subtitle tool that pairs files nothing else can pair — across
release groups, scripts and naming schemes — locks every stretch of the episode, and tells
you when it doesn't know.*

---

## Licence: GPL-3.0 — ruled 2026-09-07, applied everywhere 2026-09-08

tsubasa and surasura are GPL-3.0. It costs nothing (a licence binds recipients, not the
author; contributions need a CLA before any relicensing), protects the pairing layer, and
unlocks lapse, alass and AutoSubSync as references or source.

⚠ **The 2026-09-07 pack still said "MIT" in `10-deployment.md`, `COMPARISON.md`,
`CONTEXT.md` and the whole of `11-ffmpeg-build.md`.** Corrected 2026-09-08. ✅ **`D1`
RULED: GPL-3.0 is final**, which strikes an entire spec part — under GPL a stock ffmpeg
build may ship or be downloaded, so the minimal LGPL build is unnecessary work.

---

## What the tool is, architecturally

> **A librarian and a referee — and now the referee is also the fastest part.**

| Role | Why it is ours |
| --- | --- |
| **Librarian** — which subtitle belongs to which video | Nothing else pairs across groups and scripts. Measured on 5,645 real videos against a 116-show pool: **0 wrong-show pairs called SAME** |
| **Referee** — is this alignment trustworthy? | The chance-baseline verdict, the whole-runtime walk, and refusal with a reason. No engine tells you which of its own runs to trust |
| **Aligner** | ⭐ One primitive answers offset, cut and verification in one pass at **49 ms per pair**, matching the oracle on all 29 ground-truth pairs (`12-alignment.md`). ✅ Built 2026-09-08 |
| **Split detection** | Ours, unchanged guards; subsync 4/4 where engines were 0/4 |

---

## LAUNCH

1. **Recognition, ours-first** — the parser with the two measured fixes (` (N)` suffix,
   bare `E##`), per-folder scheme inference (full-width folded, three files minimum),
   anitopy and guessit **lazy**. `09-corpus-strategy.md` §Stage 1
2. **Series identity as a ranking** — normalisation (NFC, width, macrons, CJK variants,
   trailing-punctuation signature as a *tiebreak*), the **decoration vocabulary**, the
   **kana phonetic bridge**, and the **Wikidata alias table** (`D6`, gated by Probe G).
   ⚠ Described here as *three-way* until A7 built it: **Wikidata has no romaji field**,
   so a row is one entity and N names tagged by script — `09-corpus-strategy.md` §Stage 2.4
3. **Layout-agnostic discovery** — eight real shapes; proximity a signal, never a rule;
   two-folder mode; explicit `--pair` (skips the pairer, never the verdict)
4. **Duration as a pairing signal** — hard-reject impossible pairs, discriminate cuts
5. **Movie libraries** — stem match through the decoration vocabulary, title + year,
   one-video-per-folder
6. **Cluster-level arbitration** — probe candidate clusters with two alignments;
   **coherence ≥ 0.60** as the escalation band's second signal; episode-set offset
   hypotheses
7. **Universal subtitle reading** — timing from everything; write back the common formats
8. **PGS / VobSub timing as a reference** — 16.7% of the library
9. ⭐ **Native container reader** (`D2`) — Cues-indexed MKV subtitle timing in 0.085 s, no
   ffmpeg on the fast path; block-walk and ffmpeg as fallbacks
10. ⭐ **The 2-D difference-histogram aligner** — offset, uncapped cuts and the
    whole-runtime walk from one pass; guards unchanged; the 29-pair oracle suite
11. **Silero VAD, built in, single-offset** — refuses on a failing bucket with an
    actionable CM-break reason; mask-path constants fitted separately (`12-alignment.md` §5)
12. **The verdict** — chance baseline, escalation band, coherence, hand-back reasons
13. **Rename / dedupe / trash** · language as a structured field · the existing-subtitle
    sidecar reader (hato's two rules)
14. **Library API** (`scan()` → candidate sets, `sync()` → results) · CLI · `--json`
15. **The pairing benchmark as the release metric** — recall/precision on 345 real pairs
16. **Line combining** (`--merge-lines`) · cleanup extension point (shell only)
17. **GUI** — tkinter, shelling out to the CLI
18. **Single-binary distribution** via GitHub releases

## EVOLUTION

- **Split detection on a speech mask** — margins re-fitted for the mask regime, seeded by
  the measured offset prior (+9.5–10 s CM block, ±90 s OP)
- MP4 (`moov`) native reader — ffmpeg covers it until then
- `--lang` filter · index refresh · library watcher · pip · cleanup transforms · writable
  bitmap formats
- External engines as candidate generators — no trigger condition, no cost bound

## ⛔ CUT — each by a measurement or a ruling

| Cut | Evidence |
| --- | --- |
| CRC32 identity index | Probe A — 1.11% |
| Rust hot path | Probe B, then J2 — **49 ms/pair in numpy, measured on the built code** |
| **Three parsers on every file** | O3, J1 — guessit manufactures 95% of its disagreements from resolutions and years; ours-first resolves 97.6% |
| **The minimal LGPL ffmpeg build** (`11-ffmpeg-build.md`) | the GPL-3.0 ruling makes it moot — `D1`, ruled 2026-09-08 |
| **The ≤ 3 s/episode VAD target** | J3 — Silero costs ~21 s per 24-minute episode on this laptop; restated below |
| Subtitle quality ranking · writable bitmaps · sub-50 ms on independent pairs · a commercial-drama corpus | unchanged from 2026-09-07 |

---

## Precedence: accuracy outranks speed

When an optimisation and a correct answer conflict, the correct answer wins. Speed work
must leave the answer the same within tolerance, proven by the oracle suite. **The
primitive was accepted on that basis and no other** (`08-probes.md` §J2).

## Rule 4 — the efficiency question, at every level

Asked three more times on 2026-09-08 and answered by measurement each time: the offset
search (135×, the histogram), the track read (35×, the container's own index), and the
parse (10×, guessit made lazy). See `00-INDEX.md`.

---

## The verdict, as measured

Unchanged: **≥ 2.5× accept · 1.5–2.5× escalate · < 1.5× refuse**, the escalation rung
structural because correct English pairs (1.70–2.12×) sit below wrong anime pairs
(1.37–1.95×). New: the escalation band's second signal is **cluster coherence**, measured
at 0 of 60 wrong clusters accepted at ≥ 0.60. **Mask-path constants are separate**: correct
uncut pairs measured at 2.42–2.77× on Yomi ep18 straddle the 2.5 line.

---

## Performance target — restated as measured numbers

| Path | 2026-09-07 target | Measured 2026-09-08 | Target now |
| --- | --- | --- | --- |
| **Fast** — text or bitmap track | ≤ 0.4 s/episode | track read 0.085 s (Cues) + align 0.03 s | **≤ 0.2 s/episode · 24 episodes ≤ 5 s cold** |
| **VAD** — no track, first run | ≤ 3 s/episode | Silero **~21 s** per 24-minute episode on this laptop, cached after | **≤ 30 s/episode first run**; the stronger machine re-baselines |
| Re-run, nothing changed | ≤ 1 s / 24 episodes | 0.284 s / 24 files (cache bench) | unchanged |

Baseline before this work: 8.1 s wall per pair (subsync).

## Scale

Hundreds per run, thousands in a library. Pairing is an indexed join on (season,
episode) and cluster key; probing is per cluster pair, not per file. At 10× everything
is linear in file count except the alias lookups, which are O(1).

## What is irreversible

Only writing to a user's subtitle files. Never overwrite without a confident verdict;
superseded originals go to trash; writes are atomic; `--dry-run` writes nothing; the text
encoding is preserved. ✅ **`D9` RULED:** cues falling inside a removed stretch are
dropped, counted and reported — a whitelist addition (`03-permissions.md`).

---

## The ratified stack

⭐ **Python + numpy.** No Rust.

| Choice | Licence | Why |
| --- | --- | --- |
| **Silero VAD** via `onnxruntime` | MIT | 2.2 MB, no PyTorch; band proven (F, J3) |
| **Wikidata** | CC0 | the shippable alias source |
| **anitopy · guessit** | permissive | **lazy second and third opinions**, never the first pass |
| `send2trash` | MIT | OS-native trash |
| **ffmpeg as a SUBPROCESS** | GPL build acceptable under GPL-3.0 | audio decode for VAD; container fallback; found on PATH or `$TSUBASA_FFMPEG` — **never during a sync run**. ⏸ `tsubasa setup --ffmpeg` (pinned sha256) is specified in `10-deployment.md` and was never built |
| Native MKV reader | ours | the fast path (`D2`) |

⛔ AniDB (CC BY-NC-SA), AniList and TMDB data never ship. `titles.jsonl` is the local
answer key only.

## Distribution

GitHub releases at launch, pip later; design the two-package split now (hato depends on
`tsubasa>=0.1`).

## Honest risk

**The pairing layer is now measured at library scale — on one library.** 116 shows, 5,645
videos, median fan-out 8, 0 wrong-show SAME, but 9.9% of real pairs refused by title until
the three-way table or the cluster probe rescues them. The sealed slice, opened once at the
end, is the only independent evidence and it has not been opened.
