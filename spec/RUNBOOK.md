---
type: runbook
title: tsubasa — Build Order
desc: Dependency-ordered and re-sequenced 2026-09-08 against twenty probes. Every step carries what it builds, the command that proves it landed, and the traps already paid for. Steps marked DONE are built and green; do not rebuild them.
date: 2026-09-08
---

# tsubasa — Build Order

> Walk top to bottom. **Advance as far as possible**; stop only for a credential a human
> must mint, a decision the spec genuinely lacks, or a destructive action.
>
> ⛔ **A step with no PROOF command is not a step. It is a wish.**
>
> ⚠️ **RE-SEQUENCED 2026-09-08.** Fourteen new probes (`08-probes.md` §O, §J) re-based
> Track B on one primitive, moved the parser fixes to the front, and settled the VAD path.
> ✅ **Decisions `D1`–`D9` were RULED the same day (`HANDOFF.md`) — every lean taken.** A
> `D#` marker below is a citation to that ruling, not a question. Build to it.

---

## The dependency graph

```
LAYER 0 — probes complete (A–G, O1–O8, J1–J6). Only 0b remains (needs Sonic).
  ├── 0a  ✅ corpus split by show, sealed slice mechanically guarded
  ├── 0b  ⛔ CI skeleton: 3-OS matrix — needs the GitHub repo (Sonic)
  └── 0c  ✅ answer key rebuilt (12,259); Yomi VAD set + a real .mkv staged

LAYER 1 — foundations
  ├── 1a  ✅ Parse/IO: every format in, byte-exact round-trip, encoding preserved
  ├── 1b  ✅ Cache: content-hash keyed, per-user location
  ├── 1c  ✅ PGS/VobSub TIMING reader (2 of 22 vn17 controls to inspect)
  └── 1d  ✅ D2  Native container reader: Cues-indexed MKV → block walk → ffmpeg fallback

LAYER 2 — three tracks, GENUINELY CONCURRENT
  ├── TRACK A · RECOGNITION   filenames + duration + cluster probes
  ├── TRACK B · ALIGNMENT     the 2-D histogram primitive; VAD single-offset
  └── TRACK F · TRANSFORMS    cue lists only

LAYER 3 — needs A + B
  ├── 3a  ✅ Rename / dedupe / trash + language field + existing-subtitle reader (hato)
  ├── 3a-bis ✅ Results DB — hash-and-skip. The 35th suite, 29 checks. A settled
  │           24-episode folder re-runs in 0.84 s with ZERO container reads
  ├── 3b  ✅ Library API   ← surasura and hato consume this; shapes freeze here
  ├── 3c-0 ✅ ⭐ END-TO-END BENCHMARK on real media — the 34th suite, 22 checks,
  │           40 mutants / 0 survivors. ~50 adversarial findings, all fixed
  ├── 3c  ✅ CLI — `python -m tsubasa`. The 36th suite, 50 checks, 45 mutants /
  │           0 survivors. ⭐ Six defects came from LOOKING, not from a check
  └── 3d  ✅ GUI — `python -m tsubasa.gui`. The TABLE, ruled 2026-09-10.
  │           `gui/run.py` + `scale.py` + `settings.py` + `app.py`; the 37th
  │           suite, 93 checks, 79 mutants / 0 survivors. Drag a folder on and
  │           it runs; every option is in one organized panel; the RECKLESS
  │           group is the only thing that asks before writing.
  │           🚨 SEVEN defects came from LOOKING, none reachable by a check

  └── 3f  ✅ `embedded_subs()` — the "Japanese track already inside" check
              hato needs, public. SHIPPED in 0.1.3 (2026-09-17), verified from PyPI

LAYER 4
  ├── 4a  ✅ Release — PyPI `tsubasa-sync`, a `v*` tag through Trusted Publishing.
  │           0.1.0 (yanked) · 0.1.1 · 0.1.2 · 0.1.3. Frozen binaries were NOT built
  ├── 3g  ⏳ `tsubasa setup --ffmpeg` — the installer, ruled INSTEAD of bundling
  │           ffmpeg in the standalone (Sonic, 2026-09-17)
  ├── 4c  ⏳ STANDALONE — a WINDOWS zip with no Python in it, GUI first, unsigned,
  │           on the same `v*` tag as PyPI (Sonic, 2026-09-17).
  │           Scope: `STANDALONE-BUILD-SCOPE.md`. Linux = a wrapper, spec'd not
  │           built (§8a); macOS = ⏸ HALTED with its flow recorded (§8b)
  └── 4b  ⏸ Rust — unjustified: the primitive runs at 49 ms/pair in numpy
```

### Why A and B stay concurrent

They share no code and meet at one function: `align(R, A, dur) -> Fit` (the primitive).
Track A builds against a stub returning a constant; Track B builds the real one.
⛔ Two agents on Layer 2 read [[Development Doctrine/workflows/dev-parallel]] first.

---

## ✅ BUILD STATUS — 2026-09-08

| Step | State | Proof actually run |
| --- | --- | --- |
| **0** wiring | ✅ | oracle 651 passed / 25 skipped; runner green (13 suites, 2026-09-08 03:48) |
| **0a** corpus split | ✅ | `corpus --verify-split` — 5,902 shows, 60.0/19.8/20.2 |
| **1a** parse / IO | ✅ | 33,717 real files round-tripped, 99.25% byte-identical, 0 mismatches |
| **1b** cache | ✅ | `cache --bench` — 0.284 s, 24/24 hits |
| **1c** bitmap timing | ✅ | 382 `.sup` + 46 `.idx` parse for timing |
| ⭐ **1d** container reader | ✅ **done 2026-09-08** | 10 real 1.44 GB MKVs: **0.087 s median / 0.110 s worst**, ~30 KB, **0.000000 s** against both the block walk and ffmpeg's own extraction. **55 checks, 23 mutations / 23 kills.** See the block below |
| ⭐ **0c** answer key + fixtures | ✅ **done 2026-09-08** | `corpus --stat` — **12,259 title rows** (12,152 ja / 10,762 en); `video-derived/yomi18/` staged; `video/Sintel-60s.mkv` staged, so the real-container checks run on a fresh clone |
| **A1** normalisation | ✅ | 49 checks; Gintama seasons distinct, Naruto/Shippuuden separable |
| **A2** parser (first version) | ✅ | superseded by A2-fix |
| ⭐ **A2-fix** | ✅ **done 2026-09-08** | see the block below |
| **A2b** gate | ✅ | re-recorded from a FULL run: `parser-gate-baseline.json`, **96.78% accounted over 33,757 files** (the old 97.38% was a 800-file sample taken before the builder's own parser rewrite, so it was never comparable) |
| **A3** identity | ✅ | same-show SAME 66.5% · diff-show SAME **4.2%** (corrected) |
| **A4** scheme inference | ✅ | superseded by A4-fix |
| ⭐ **A4-fix** | ✅ **done 2026-09-08** | see the block below |
| ⭐ **B1** the aligner | ✅ **done 2026-09-08** | `tsubasa/align/` + `test_alignment_oracle.py` (10 checks) + `test_negative_controls.py` (11 checks). **29/29 offsets, 29/29 cue-correct, 29/29 break-inside-span, at 49 ms/pair against subsync's 6.6 s.** Six mutations, six kills |
| ⭐ **B2** estimator (`D3b`) | ✅ **done 2026-09-08** | resolved inside B1 — the histogram finds the peak, the OBJECTIVE sets the value (`12-alignment.md` §3.5) |
| **B3** uncapped splits | ✅ **done 2026-09-08** | the greedy cue-level search is uncapped; the quiet-gap convention and `TIE_SLACK` land with it. ⚠ A real 3+-break specimen is still owed (derive one) |
| **B4** bucket walk | ✅ **done 2026-09-08** | computed from the same pass, no second sweep; `Fit.holds_throughout` |
| ⭐ **B8** the verdict | ✅ **done 2026-09-09** | `tsubasa/verdict.py` — **63 checks, 39/39 mutants.** Drives the 5 real `MUST_REFUSE` pairs and the real drifting TV edit. 🚨 Amended `12-alignment.md` §3.6 by measurement. ⛔ Has no caller yet |
| ⭐ **3a** naming + dedupe + write | ✅ **done 2026-09-09** | `sidecar.py` **66 / 42** · `dedupe.py` **30 / 34** · `apply.py` **50 / 36**, and ⭐ **`D9` with it**. ⛔ Still no CALLER — that is 3b |
| ⭐ **3c-0** the END-TO-END benchmark | ✅ **done 2026-09-09** | `tsubasa/dev/e2ebench.py` + `test_e2e.py` — the **34th suite**, 22 checks, **40/40 mutants**, floor in `e2e-baseline.json`. ⭐ The first thing that measures the PRODUCT: nine real library shapes, `scan()` → `sync(write=True)`, asserted on the tree **by content hash**. Solves a real AT-X broadcast cut to **7 ms / 46 ms**. 🚨 Three adversaries returned ~**50** findings against its first version — fifteen of them mutations that survived checks named after the exact thing they broke — and it **found a real defect in `sidecar`, fixed the same day**. See the block below |
| ⭐ **3b** the library API | ✅ **done 2026-09-09** | `api.py` (`scan`, `Scan`, `Candidacy`, `Result`) + `pipeline.py` (`sync`, `SyncReport`) — `test_api.py` **57** · `test_pipeline.py` **66**, **95/95 mutants**. ⭐ **Everything below it now has a caller.** Two adversarial passes; the first returned **14 findings against 33 green checks**, three of which lost or mangled a user's file. See the block below |

### ⭐ A2-fix / A4-fix — landed 2026-09-08, measured on the shipped parser

| Claim | Was | Now |
| --- | --- | --- |
| catalogue `unknown` (201,785 non-sealed files) | 10.6% | **2.44%** |
| series keys still carrying an `E##` token | 9.1% | **0.00%** (5 files) |
| video files whose episode the ` (N)` suffix changed | 2,108 of 2,602 (81.0%) | **0** |
| files sent to arbitration (full corpus) | 28.4% | **0.0%** |
| ours missed and another parser succeeded | 13.2% | **0.6%** |
| ours succeeded where every other parser failed | — | **6.2%** |
| parse cost per name | 28.0 ms | **1.6 ms** (17.6×) |
| coverage given up by running the others lazily | — | **0 of 800 files** |

⚠ **The headline gate number barely moves (96.78%) and that is expected**: the gate
scores the UNION, and anitopy was already rescuing the `E##` episodes. What it could
never see is that our own TITLE stayed wrong on every one of them, which is what series
identity consumes. That is the 9.1% → 0.00% row, and it is why the **title gate (A2b+)
exists**.

⚠ **Verified by mutation, not by reading**: seven mutations, seven kills. One test —
a full-width fixture built with `u"（０%d）" % i` — was found to be **ASCII in disguise**
and was passing against the broken code. `LEDGER.md` §Harness.

Nothing below this line is built.

---

## Step 0c — ✅ Rebuild the answer key; stage the VAD material — DONE 2026-09-08

**surfaces:** `harness` · **depends on:** nothing

| | |
| --- | --- |
| **Build** | ✅ `node jimaku-corpus.mjs --titles --root <corpus>/naming` — ⚠ a purely LOCAL collapse of `titles.jsonl`, **not a crawl**; it uses the cached `_index.json` unless `--refresh-index` is passed, which it must not be · ✅ `_work/stage_yomi18.py` copied the audio + six subtitles into `video-derived/yomi18/` · ✅ `video/Sintel-60s.mkv` + `.srt` staged |
| **Prove** | ✅ `corpus --stat` → **12,259 title rows** (the row it prints was added at 0c; before that the number lived only in a report) · ✅ `ls video-derived/yomi18` → audio + 6 subtitles + README · ✅ `corpus --verify-split` → 5,902 shows, **60.0/19.8/20.2**, unchanged · ✅ `pytest tests/test_container.py` → **55 passed, 0 skipped** |
| **Measured** | 12,259 rows · **12,152** with Japanese · **10,762** with English — matching the Expected line exactly |

### What landed

- **The answer key is rebuilt.** `titles.json` was a 4,620-row mid-crawl artefact; it is now
  the full 12,259.
- **`video-derived/yomi18/`** — the VAD ground truth: `audio16k.opus`, the video's own
  track, two uncut streaming subtitles, two cut broadcast subtitles, one wrong episode, and
  a `README.md` carrying the measured answer for each (`12-alignment.md` §5). ⭐ **Four of
  the six are things the tool must REFUSE**, which is what makes the set worth its size.
  Cross-check: the staged own-track `.ass` parses to **323 cues**, the same count the
  container reader reads from the real ep18 MKV.
- **`video/Sintel-60s.mkv`** — a 60 s CC-BY clip, streams copied, with a subtitle track
  muxed in, beside `Sintel-60s.srt`, which is **ffmpeg's own extraction of that track** and
  therefore an independent answer key. ⭐ **It is ffmpeg-muxed, so it is a SECOND MUXER** —
  `S_TEXT/UTF8` where the ten SubsPlease files are mkvmerge's `S_TEXT/ASS`. Measured: ffmpeg
  also writes a CuePoint for every subtitle block (24 of 24, index verified complete), so
  the fast path holds across two muxers rather than one muxer's default.
- **`corpus --stat` prints the answer key**, with the tombstone arithmetic inline.

🚨 **`titles.jsonl` and `titles.json` are different counts and both are right.** The
`.jsonl` is the append-only crawl log **including tombstones** — entries whose id later
redirected to the homepage; `titles.json` is the deduped view with tombstones applied.
**12,589 logged − 330 tombstoned = 12,259 live.** Reading the log's line count as the key
size overstates it by exactly those 330, and it is the first number anyone reaches for.

⚠ The Desktop folder is *outside* the corpus; the suite must never reference it. The
staging script copies **out** of it and nothing reads it afterwards.

---

## Step 1d — ✅ D2 · Native container reader — DONE 2026-09-08

**surfaces:** `logic` · **depends on:** 1a · ✅ **D2 ruled: build it**

| | |
| --- | --- |
| **Build** | `tsubasa/container/` — `mkv.py` (EBML walk → Info, Tracks, **Cues-indexed block timestamps**, block-walk fallback, Chapters), `ffmpeg.py` (the fallback and its refusal), `__init__.py` (the one accessor, `Track` / `ContainerInfo`, the ladder). Plus `tsubasa/dev/containerbench.py` → `container --bench` |
| **Prove** | `python -m pytest tests/test_container.py` — **53 checks: 49 hermetic, plus 4 real-container that SKIP (not pass) without `TSUBASA_MEDIA`**. Registered as the `container` suite · `python -m tsubasa.dev container --bench --walk` |
| **Measured** | 10 real 1.44 GB SubsPlease MKVs: index path **0.087 s median, 0.110 s worst**, **~30 KB** and ~13,600 seeks per file, against a block walk at **0.8–9.7 s** and ~90,000 seeks. Cue starts **0.000000 s** from the block walk on all 10, and **0.000000 s** from the ffmpeg-extracted `.ass` on the 8 that have one in the corpus. Ep 18 reads **323 cues**, matching probe J6 exactly. Header-only read: **315 bytes, 104 seeks** |
| **Mutation** | **19 mutants, 19 kills** — `_work/probe_adj10_containermutants.py` |

### What this step added beyond the line above, and why

- 🚨 **A completeness guard on the Cues index.** A muxer is not obliged to index every
  subtitle block, and a sparse index returns a well-formed subtitle **missing lines**,
  with a plausible count and no warning — Rule 2 arriving through the door opened for
  speed. Before the index is trusted, a **contiguous run of two clusters** is walked and
  its blocks counted. ⚠ One cluster is not enough: the busiest indexed cluster is by
  construction one the indexer did not skip. Both failure shapes are in the suite.
- ⚠ **`index_verified` is tri-state** — `True` / `False` / **`None` for "could not be
  checked"**. An absent answer and an unanswered question are different results.
- **Chapters are read** (`06-edge-cases.md` §5.2 calls them free split-point hints).
  🚨 `ChapterTimeStart` is in **nanoseconds** and does not take `TimestampScale` — the one
  Matroska time field that does not.
  ⛔ **RULED 2026-09-08: chapters are DATA, not a decision, and must stay that way.** They
  are read into a list and **nothing consumes them**. A chapter marker is *not* evidence
  that a cut exists — plenty of files are chaptered and uncut, and plenty of cut files
  carry no chapters. The moment anything treats a marker as a break, it becomes exactly
  the confidently wrong answer Rule 2 exists to prevent. If the split search ever uses
  them, it may only **seed candidate offsets that the objective must then earn**.
- **`use_index=False`** forces the block walk on the same bytes. It is a product option
  because the suite, the bench and a probe had each grown a private copy of it.
- **`media` config section + `paths.media_root()`** — how a machine says where its real
  videos are, so no check hardcodes one. Guarded by `test_media_root_is_outside_the_repo`.

### ✅ Closed at 0c

- **"duration equal to ffprobe's" — RUN AND PASSING.** It was recorded unrun because
  ffprobe was believed absent; it ships with [[media-kit]] at `Workshop/media-kit/bin/`.
  All ten real files agree with ffprobe to < 0.05 s. `test_the_duration_matches_ffprobe`.
- **The ffmpeg fallback EXECUTES and agrees.** `TSUBASA_NO_NATIVE_DEMUX=1` disables the
  native reader so a Matroska file routes to ffmpeg — required by `07-test-plan.md`,
  because without it the fallback is *code that never runs in the local configuration*.
  Native and ffmpeg agree to **≤ 1 ms** on the same file, and the switch announces itself
  in `ContainerInfo.warnings` rather than silently making every read 35× slower.
- **The corpus `.mkv` fixture exists** — `video/Sintel-60s.mkv`, staged at 0c. The four
  real-container checks now run on a fresh clone with **no configuration at all**.

⭐ **How to give this project ffmpeg** (needed for the VAD path, non-Matroska containers,
and the two checks above):

```
TSUBASA_FFMPEG=<folder containing ffmpeg and ffprobe>
# on this machine: TheForge/Workshop/media-kit/bin
```

⛔ **The resolver must never hardcode that path.** It looks on PATH, then
`$TSUBASA_FFMPEG`, then the cache directory — in that order, and nothing else. `subsync`
hardcodes a local install; this ships to other people. Checks that need ffprobe **SKIP with
the reason printed** when it is absent, and say exactly which variable would supply it.

### ⚠ Still unchecked, and named as unchecked

- **Only two muxers' output has been read** — mkvmerge (the ten SubsPlease files,
  `S_TEXT/ASS`) and ffmpeg (`Sintel-60s.mkv`, `S_TEXT/UTF8`). **Both index every subtitle
  block**, so the partial-index path still has **no real specimen** — it is covered
  synthetically only, and nothing in the wild has yet produced one.
- **PGS-in-MKV was proved synthetically, not on a real disc rip.** Block timestamps are a
  container fact and know nothing about the codec, so the mechanism is codec-agnostic by
  construction — but no real MKV carrying a PGS track was available to confirm it.

### ✅ RESTATED, not chased — the block-walk target (`ruled 2026-09-08`)

The old line read *"the block-walk path within 2× of ffmpeg"*, and it was ambiguous rather
than wrong. Measured both ways:

| | block walk | ffmpeg | ratio |
| --- | --- | --- | --- |
| **warm** | 1.02 s | 0.82 s | **1.24× — inside the bar** |
| **cold** | 7.96 s | 3.04 s | **2.6× — accepted** |

⛔ **Do not chase the cold number.** The walk is the fallback for a file whose subtitle
track carries **no cue points**; it has never run on a real file; and its cost is
**syscall-bound at 88,340 seeks**, where `mmap` already measured *slower* (probe J5).
Optimising it is work with no measured demand. ⭐ **The target is: within 2× warm, about
2.6× cold, accepted with the reason.**

⚠ **The text payload is never read on this path** — the reference is timing only. Text
is read only when the track is being *extracted* as a subtitle file (hato's use); the seam
is `_block_header`, which already returns where the payload begins.
⚠ MP4 (`moov` sample tables) is **evolution**; ffmpeg covers it until then.

---

## TRACK A — Recognition

**surfaces:** `logic` `data` · **depends on:** 1a · **concurrent with:** B, F

| # | Build | Prove |
| --- | --- | --- |
| **A2-fix** | ⭐ **FIRST.** Strip trailing ` (N)` (N ≤ 99) before parsing; bare `E##` pattern below `S##E##`; year/resolution/codec sanity on every parser's candidate; **ours first, anitopy lazy, guessit lazy** (`09-corpus-strategy.md` §Stage 1) | `test_naming.py` gains the O-defect cases; `parsergate --all --no-guessit` accounted-for ≥ baseline and **unknown ≤ 3%** on the catalogue; the ` (N)` script from `probe_adj1` reports **0** changed episodes |
| **A4-fix** | NFKC inside `tokenize()`; `MIN_FILES = 3`; a constant column never wins | `test_scheme.py`: the NHK `（０１）` shape resolves; `Show - 05` ×2 returns nothing |
| ~~**A2b+**~~ | ✅ **DONE 2026-09-08.** `tsubasa/dev/titlegate.py` → `titlegate --all --baseline`, floor in `title-gate-baseline.json`. ⚠ The metric asked for here — *same-show key agreement* — was **measured and rejected**; see the block below | ✅ `test_titlegate.py` **28 checks**, **12/12 mutants**. ⭐ It found a live defect on its first run: **contaminated 6.45% → 0.15%**, and the release number **69.1% → 80.0%** |
| ~~**A2c**~~ | ✅ **DONE 2026-09-08.** `tsubasa/naming/decoration.py` (tokeniser + applier, ships) · `tsubasa/data/decoration.json` (**176 tokens**, bundled) · `tsubasa/dev/decoration.py` → `decoration --derive` / `--grade`. Derived over **203,591 non-sealed rows / 11,210 shows**; independently reproduces §3.1's rates and all 56 of its named tokens | ✅ `test_decoration.py` **33 checks**, 13/13 mutants. **Film pollution 39.9% → 2.7%** (target < 5%), unknown 23.4% → 3.6%. Every `LEDGER.md` title-destruction case survives |
| ~~**A3b**~~ | ✅ **DONE 2026-09-08.** `tsubasa/naming/kana.py` — kana table, the shared fold, Jaccard-prefiltered ranking, accept ≥ 0.85 with a 0.10 margin. `tsubasa/dev/kanagate.py` → `kanagate --all` | ✅ `test_kana.py` **40 checks**, 14/14 mutants. Full population (2,160 kana titles vs 11,210): **rank-1 75.2%** (gate ≥ 75%), rank ≤ 5 88.1%, ⭐ **folder rank-1 99.2%**, **0 of 300 fabricated accepted** |
| **A3-fix** | Signature is a **tiebreak**: DIFFERENT only when two candidates share the key and differ in signature | `test_series.py`: `Toradora`/`Toradora!` pair when alone; Gintama seasons still separate |
| ~~**A5**~~ | ✅ **DONE 2026-09-08.** `tsubasa/discover.py` — one walk whatever the layout, proximity as a SCORE never a rule, films and episodes separated by parsing, candidates from a `(season, episode)` index | ✅ `test_layouts.py` **19 checks** (all eight shapes) + `test_pairing.py` **13 checks**. 500×1500 stays an index; 🚨 the index reintroduced the 305-false-pair defect once and this suite caught it |
| ~~**A5b**~~ | ✅ **DONE 2026-09-08.** `tsubasa/dev/vnbench.py` → `vnbench --baseline`, floor in `vn-bench-baseline.json` | ✅ `test_vn_bench.py` **8 checks**. Over **350 pairs confirmed by ALIGNMENT**: ⭐ **candidate recall 92.3%**, settled-by-name 49.7%. Fan-out at catalogue scale **282 → 103 after identity**, still ~13× over the 8 budget — which is the number that justifies A6 |
| ~~**A6**~~ | ✅ **DONE 2026-09-08** (`D7`). `tsubasa/arbitrate.py` — coherence, the one-directional lift, episode-set offset hypotheses | ✅ `test_arbitration.py` **20 checks**. Reproduces **all 104 recorded clusters exactly**; at ≥ 0.60 **24/44 correct kept, 0/60 wrong accepted**, wrong max 0.50. The renumbered shows resolve |
| ~~**A7**~~ | ✅ **DONE 2026-09-08** (`D6`). `tsubasa/naming/alias.py` + `tsubasa/data/aliases.tsv.gz` (**221,258 keys**, CC0) · `tsubasa/dev/alias.py` → `alias --harvest` / `--derive` / `--grade` / `--grade --sweep`. Wired into `same_series`. See the block below | ✅ `test_alias.py` **60 checks**, **27/27 mutants** (`_work/probe_adj15_aliasmutants.py`). ⭐ **settled-by-name 49.7% → 69.1%, +19.4 points**, recorded in `vn-bench-baseline.json` |
| ~~**A9**~~ | ✅ **DONE 2026-09-08.** `tsubasa/duration.py` — every constant measured with its population. ⛔ **The spec's `shorter by >15% -> reject` was measured and NOT BUILT**; see `06-edge-cases.md` §3.45 | ✅ `test_duration.py` **54 checks, 42/42 mutants** |
| ~~**A10**~~ | ✅ **DONE 2026-09-08.** `tsubasa/movies.py` — stem / title+year / sole-video rungs, edition as a **second value**, three injectable seams | ✅ `test_movies.py` **122 checks, 41/41 mutants**. Stem carries **99.91%** of the easy half, **37.49%** of the hard half; **0 false pairs in 19,996** draws |
| ~~**A11**~~ | ✅ **DONE 2026-09-08.** `tsubasa/explicit.py` — the verdict is **structurally unbypassable**, not merely un-bypassed | ✅ `test_explicit_pair.py` **76 checks, 56/56 mutants** |

⚠ 🚨 **Group candidates on season AND episode.** Made three times. ⚠ **DIFFERENT is not
terminal below the fan-out budget** — 9.9% of real pairs are DIFFERENT-by-title and right.
⚠ **Never ship a table mined from jimaku filenames** — private build only.

### ⭐ A2b+ — the title gate, done 2026-09-08

| | |
| --- | --- |
| ⭐ **What it found on its first run** | **6.45% of the catalogue** (13,137 files) carried an episode marker in the series key. One branch fix took it to **0.15%** (299) |
| ⭐ **What that bought** | the release number, `settled by name`, **69.1% → 80.0%** — and the pre-A7 arm rose too, 49.7% → 51.4% |
| **No regression** | parser gate 96.78% → **96.83%**; the runner green at 675 checks *as it stood at A2b+*; parser, alias and title-gate mutants all 0 survivors |
| **Baseline** | `title-gate-baseline.json` — ⚠ a **CEILING**, not a floor. The suite fails when the number RISES |

🚨 **The defect, and why `parsergate` could not see it.** The `第N話` branch
searches the **raw** filename so noise stripping cannot eat it — so its match
position indexes a different string from the one the title is sliced from, and
`cut` was never assigned there at all. The title was returned whole:

```
ワンピース.S10E026.第1025話 最悪の世代全滅！   ->   episode 1025  ✅
                                              title 'ワンピース S10E026 第1025話 …'  ⛔
```

⭐ **The episode came out right, so a gate scoring the UNION saw nothing.**
⚠ And cutting at the marker that *produced* the number is not enough: One Piece
takes its episode from `第1025話` while `S10E026` sits earlier, so **the series
name ends at the FIRST marker**, not the source one.

⛔ **`S01E01-The Harvest Festival…` is still contaminated, deliberately.** The name
begins with the marker, so there is no series title in it; cutting at 0 would
trade a contaminated key for an **empty** one, which pairs with every video
sharing an episode number (`08-probes.md` §C, 4,133 files). That is most of the
residual 0.15%.

### ⚠ The metric this row originally asked for was rejected, with numbers

*"Share of same-show files whose series key differs"* was measured by probe
A2b+/1 **before** the gate was written:

- **21.6% of entries carry more than one script.** `Heroic Age` and
  `ヒロイック・エイジ` are one entry and key differently **correctly**
- `(entry, script)` does not save it: `Space Ironmen Kyodyne` and
  `Uchuu Tetsujin Kyoudain` are both Latin, both one entry, both right
- the 19.25% disagreement is mostly release-name typos, entries holding several
  works, and English-against-romaji

⛔ **Kept as a trend line, NOT gated** — tuning against it is tuning against the
corpus. ⭐ The gate is instead **self-referential**: an episode MARKER still in the
title **and** its number being the one the parser called the episode. Both halves
are load-bearing — number-only accused `５→９` and `ラスト・コップ2nd` in its first
five accusations.

### ⭐ A7 — the alias table, done 2026-09-08

| | |
| --- | --- |
| **The number `D6` asked for** | ⭐ **settled-by-name 49.7% → 69.1%** on the 350 alignment-confirmed pairs: **+19.4 points, +39.0% relative**, 73 SAME verdicts from the table. `vnbench` prints both arms in one run |
| **Gate** | `D6` cuts A7 below a **15% realised gain**. ⚠ **The spec does not say 15% *of what*** — a Part 1 defect, recorded rather than decided. It clears both readings: +19.4 points and +39.0% relative |
| **Source** | Wikidata **CC0**, enumerated by P31 work class: **113,845 entities in 13 SPARQL queries + 2,277 batch fetches, 0 unanswered**, 58 min. Resumable and append-only |
| **Derived** | **95,443** entities carry both a CJK and a Latin name → **221,258 keys**, 4.03 MB gzipped, **0.77 s to load** |
| **Coverage** | `alias --grade`: **~35%** ja→romaji, **~46%** ja→English over 11,110 eligible key rows. ⭐ Probe G's *live search* measured 38.8% / 46.2% — two unrelated instruments landing within four points, which is the closest thing to independent confirmation this project has |
| **Precision** | **0 of 4,000** uniform cross-pairs — ⚠ **and that number is nearly free**, it draws the failure shape 0.08% of the time. ⭐ The one that costs something is the **hard** control: a title against a different row whose romaji contains it, **13 of 6,692 (0.19%)** through the shipped path |

⛔ **ENUMERATED, NEVER SEEDED FROM THE ANSWER KEY**, and the reason is the licence, not
the clock. Searching per show would make the AniList-derived key the **selection
function**, so the shipped row set would be AniList-derived even though every field came
from Wikidata. `02-data-model.md`.

🚨 **The spec asked for a column that does not exist.** It specified a **three-way table
(romaji ↔ Japanese ↔ English)**; Wikidata has **no romaji field**. Measured: `ja` 100%,
`en` 100%, `mul` **0%**, English aliases 90% — with the romaji *inside those aliases*
beside abbreviations and different English titles (`Star Blazers` for `宇宙戦艦ヤマト`).
⭐ **A row is one entity and N names, each tagged by script**, which is strictly better
and is what `D6`'s ranking-only ruling wants. Amended in `09-corpus-strategy.md` §Stage 2.4,
`02-data-model.md` and `01-scope.md`.

⭐ **The safety property, and everything else follows from it:** **both** titles must
independently reach a **common** entity. A one-sided hit answers nothing — which is what
stops the abbreviation alias `Eva` attaching Evangelion to anything Eva-shaped, the exact
class of error that made Probe G resolve `ナルト` to a fish cake at 0.75.
⛔ **And it never returns DIFFERENT.** A series and its own season are separate Wikidata
entities, so a non-intersection is an **absent answer, not a negative one**.

### ⚠ Three defects found during the build, and none by the new suite

1. **The bridge sat above the character score.** The total was right either way, but
   **155 of 259 reported "rescues" scored ≥ 0.80** — pairs the score settles alone. A
   feature credited with work it did not do is a number nobody can act on. The check that
   pins it asserts the **CALL**, not the verdict, because the verdict is SAME either way.
2. 🚨 **`Dr Stone` / `Dr Stone Ryuusui` → SAME**, then `Naruto` / `Naruto Shippuuden` →
   SAME. Wikidata lists specials and sequels among a franchise's names. A score gate
   caught the first and the second went through it at **0.36, BELOW the band**. Fixed by
   `one_contains_the_other` — exact, no threshold — which `series.py` had named on day
   one: *ask about the LEFTOVER, not the overlap.* **Found by a pre-existing check about
   the UNSURE band.**
3. 🚨 **The fan-out cap was re-fitted three times and never once moved a precision
   number.** Set at 4 from the key-size distribution, it blocked `ナルト` (13 entities),
   `進撃の巨人` (9) and `宇宙戦艦ヤマト` (5) — franchises, not ambiguity. Raised to 24, it
   blocked `ナルト` again at **35** once the Naruto *games* arrived in a later harvest
   batch. The sweep is flat at **0.00% false positives from cap 1 to 256**, so it is a
   **bound on a pathological key, not a precision guard**, and it is named as one at 64.

⭐ **A guard was also DELETED on measurement.** A mutation removing the score gate
survived; rather than keep it on faith or drop it on taste, both arms were measured over
the same 20,000 adversarial pairs — **+2 correct bridges, 0 false positives**. The gate
went and the mutant went with it, replaced by a check that pins the decision.

### 🚨 The adversarial pass found three more, and one root cause explained two

`doctrine/verification` Layer 2 ran against a feature that was green at 41 checks and
19/19 mutants. It returned **seven findings**. Full record: `LEDGER.md` §Logic.

1. 🚨 **The mixed-script run split was unsound — a run of a COMPOUND title is a
   fragment, not a name.** `NARUTO -ナルト- 疾風伝` made `ナルト` a name of *Shippuuden*;
   `不思議の国のアリス OVA` made `ova` a key naming 12 entities, so
   `bridge("OVA", "1988")` returned SAME — **reachable from an ordinary directory name**.
   ⭐ Fixed by splitting only when a label is *one title written twice*. **That one fix
   closed three findings, dropped max-entities-per-key 189 → 41, and halved the load.**
2. 🚨 **`zlib.error` derives straight from `Exception`**, so the narrow catch in `_read`
   did not fail open — it **crashed the tool**, on 307 of 400 single-byte flips.
3. 🚨 **The negative control drew uniformly and could not see the failure shape** — 3 of
   3,999 pairs were even a containment pair. A hard control now ships inside `--grade`.

⭐ **Two guards were built for cross-script containment and both were rejected by
measurement**: a phonetic arm changed 0 of 9 cases and unrestricted refused a *correct*
bridge; an entity-subset rule fired on 4 of 5 pairs that must be kept. **Fixing the
deriver removed the need for either.**

⚠ **Still open, and named as open**

- **The table inherits Wikidata's mistakes** and no local check can see a wrong row there.
  Rule 1 holds — it ranks, and timing decides.
- ⚠ **Cross-script sequel pairs are NOT guarded**, where Wikidata genuinely lists a base
  title among a sequel's names — `ドラゴンボール` / `Dragon Ball Z`. **13 of 6,692
  (0.19%)** on a deliberately adversarial construction, and the cost is a wrong REPORT,
  not a wrong file: SAME only makes the pair a candidate, and `align()` refuses a
  wrong-show pair at 1.3–1.9× chance.
- **0.77 s to load** against B5's ~2.9 s remaining budget — down from 1.84 s once the
  fragment keys went. ⭐ **The real answer is still an on-disk index** (a run makes a few
  hundred lookups against 221,258 keys), and that is **B5's** call. Probe A7/4 has the
  breakdown.
- **The `names` map is 95,443 entries and exists only for the reason string.** Loading it
  lazily is untested headroom.

---

## TRACK B — Alignment

**surfaces:** `logic` · **depends on:** 1a, 1b · **concurrent with:** A, F ·
**authority:** `12-alignment.md`

| # | Build | Prove |
| --- | --- | --- |
| ~~B1~~ | ✅ **DONE.** `align(R, A, dur)` in `tsubasa/align/` | ✅ 21 checks green |
| ~~B2~~ | ✅ **DONE** (`D3b`) | ✅ |
| ~~B3~~ | ✅ **DONE** — uncapped, quiet-gap convention, `TIE_SLACK`. ✅ **The cut-gap cue drop (`D9`) landed at 3a**, where the writer is. ⚠ **Still owed:** a synthetic 3-break file (`test_nsplit.py`) | `test_nsplit.py` |
| ~~B4~~ | ✅ **DONE** — the walk is free from the same pass | ✅ |
| **B5** | Perf: 29 pairs under 2 s; 24-episode folder under 5 s with 1d. ⭐ **1d's half is now measured: 0.087 s/file × 24 ≈ 2.1 s of container reading**, so the budget left for everything else is ~2.9 s | `test_perf.py`, baseline recorded, never pinned |
| **B6** | 🚨 **Silero VAD, built in** (onnxruntime, 576-sample input). **Single offset + refuse on a failing bucket.** Fit the mask-path constants on the Yomi material + Probe F's controls **before** any mask verdict ships; refuse if the decoded sample count is short of the container duration by > 3% | `test_vad.py` (`12-alignment.md` §8) |
| ~~B6b~~ | ⏸ **EVOLUTION** — split detection on a mask; route written in `12-alignment.md` §5 | — |
| ~~**B8**~~ | ✅ **DONE 2026-09-09.** `tsubasa/verdict.py` — the three outcomes, the band, the one-directional coherence lift, the hand-back sentences, and the mask band left **structurally absent** until B6. See the block below | ✅ `test_verdict.py` **63 checks, 39/39 mutants** (`_work/probe_adj22_verdictmutants.py`) |

⚠ 🚨 **The Silero trap** — 512 samples returns ~0.001 uniformly with no error; feed 576.
⚠ ⛔ **Do not touch a guard while optimising.** The primitive changes candidates, not guards.
⚠ **Rule 4 note:** the mask FFT is the wrong transform (measured 9–30 s); the difference
histogram is the right one. Recorded in `12-alignment.md` §9 so it is not re-proposed.

### ⭐ B8 — the verdict, done 2026-09-09

| | |
| --- | --- |
| **What it is** | `tsubasa/verdict.py` — `verdict(fit, cluster=None, reference_kind=...) -> Verdict`. The object `ExplicitPair.decide()` already expected: an `outcome`, a `reason`, and **no write flag** |
| ⭐ **The order, and it is load-bearing** | **cue count → holds-throughout → the band.** Not the obvious order: a band-first reading calls a never-measured pair *refused*, and it **writes a cut file that is confidently mis-timed for its opening minutes** — the defect that hit four megatest files and was then repeated on a second folder |
| ⭐ **One vocabulary owner** | `CONFIDENT`/`REFUSED`/`ERROR` moved here and `explicit.py` now imports them. They were literals in both files, which is the two-copies-of-an-enumeration drift `doctrine/architecture` rule 4 describes |
| **The band** | `arbitrate.verdict()` is **called, not reimplemented** — one writer for ≥ 2.5 accept / 1.5–2.5 escalate / < 1.5 refuse, and for the coherence lift |
| 🚨 **An escalate with no second signal is REFUSED** | *"Only refuse if that also fails"* — an **absent** second signal is not a passing one. Wrong pairs measured 1.37–1.95×, inside this band, so accepting on a bare escalate writes exactly the file Rule 2 exists to prevent. The refusal says to sync the whole folder, which is what supplies the signal |
| ⭐ **The mask band is ABSENT, not borrowed** | `MASK_BAND = None`, and a speech-mask verdict **raises `MaskBandNotFitted`** naming B6. A comment saying *"fit these at B6"* beside a copied 2.5 is the version that does not hold — and 2.5 would silently refuse the **2.42×** uncut pair §5 measured as correct |
| **The hand-back** | Every refusal states what was measured, why it fell short, and what would change it. The cut/drift diagnosis needs **no new constant**: a cut is a contiguous run wanting one offset, drift is a monotonic series wanting a growing one |
| ⚠ **Reported, not repaired** | A short file's runtime check is `weak`, not `held` — `06-edge-cases.md` §5.1's ~1.5-bucket case. Scaling `BUCKET` would change a guard the oracle is fitted against |

🚨 **A spec claim was disproved and amended** — `12-alignment.md` §3.6's *"`measurable is
False` means ERROR"*. Probe B8/1 measured it: **all five `MUST_REFUSE` pairs and all three
constructed controls** come back `measurable=False` at 164–528 cues a side, so the literal
reading reports *"could not be read at all"* for a time-reversed 528-cue subtitle. The
split is the **cue count**, not the score. `Fit.measurable` is unchanged; the oracle is
untouched.

⚠ **Three defects the suite found in its own module while it was being written**, all by a
check refusing to pass: a refusal sentence containing the word *certain* (the exact
substring `LEDGER.md` §Interface records a GUI matching on); an incoherent-cluster refusal
that explained *why* and offered **no next move**; and a `+10.0 s` expectation that was
really the absolute offset rather than the shift from the applied one.

---

## TRACK F — Transforms

**surfaces:** `logic` · **depends on:** 1a

| # | Build | Prove |
| --- | --- | --- |
| F1 | `--merge-lines` | `test_merge.py` |
| F2 | Cleanup **shell** + registry + one worked example | `test_cleanup.py` |

---

## Step 3a — Rename / dedupe / trash · the existing-subtitle reader

**surfaces:** `logic` `data` · **depends on:** A, B

| | |
| --- | --- |
| **Build** | ✅ `tsubasa/sidecar.py` — the language reader, the canonical ISO-639 table, `output_name` with NAME_MAX and the Windows rules · ✅ `tsubasa/dedupe.py` — the five ranking rules, `--keep-all`, the trash with its local fallback · ✅ `tsubasa/apply.py` — **the write path**, and ⭐ **`D9` is built**: `cues.drop_cues` + a `block_span` from every writable parser |
| **Prove** | ✅ `--dry-run` over the corpus — `_work/probe_3a_2_dedupe_dryrun.py`, **and it found a defect nothing else did** (below) · ✅ a real run on scratch copies, in `test_apply.py`'s tmp trees |
| **Test** | ✅ `test_sidecar.py` **66 checks, 42/42 mutants** · ✅ `test_dedupe.py` **30 checks, 34/34 mutants** · ✅ `test_apply.py` **50 checks, 36/36 mutants** |

### ⭐ 3a's write half — done 2026-09-09

| | |
| --- | --- |
| ⭐ **The missing primitive** | `cues.retime` replaces timestamp SPANS and structurally cannot remove a block — so the two removals the whitelist permits were unbuildable. Every writable parser now reports a **`block_span`**, and `cues.drop_cues` removes and retimes **in ONE pass** (two passes would apply the second to offsets the first had moved) |
| 🚨 **Each format defines its block span DIFFERENTLY, and must** | **SRT** runs to the next block — safe *only* because SRT has no comment syntax — and its survivors are **renumbered**, the one thing the whitelist explicitly adds for a drop. **VTT** stops at the cue's own extent, because a `NOTE`/`STYLE`/`REGION` may sit between two cues and dropping one turns a valid file invalid. **ASS** is one event line |
| ⭐ **`D9` is arithmetic, not a heuristic** | `segments` lives on the REFERENCE axis and the writer holds a SUBTITLE time; the boundary is `split − offset` and the removed span is `[split − off_before, split − off_after)`, whose width is exactly the jump. Pinned against §5's own measured cut (`+0.400 / −9.825 @3:42`). ⛔ A **positive** jump removes nothing — it inserts time and leaves no cue homeless |
| **The write rules** | dry-run by default · **write first, trash second** · a file written *over* is never then trashed · a per-pair failure is recorded and the folder continues · the original codec goes back, proved on a real Shift-JIS file |

🚨 **A file can read PERFECTLY and contain zero cues**, and the writer would have produced
an empty subtitle under the name a player loads. Found by a check aimed at something else.
Refused in the writer rather than trusted to the verdict, because the verdict judged the
file at *discovery* and §7 lists *edited since last sync* as a real case — which is why the
write path re-reads at all.

⚠ **Eleven of 39 mutants survived the first run, and not one was a defect in the code** —
they were weak checks, wrong fixtures and no-op mutants. `LEDGER.md` §Harness has all of
them; the two most transferable are *a guard re-checked downstream is untestable on the
path you chose* and *`import a.b.c as X` hands you the FUNCTION when the package rebinds
the name, and the mutation then succeeds silently*.

### 🚨 THE ADVERSARIAL PASS — three agents, THIRTY-ONE findings, all fixed

⭐ **`doctrine/verification` Layer 2, run against 1,140 green checks and 151 killed
mutants.** Four of the findings each produced a wrong file. The full record is
`LEDGER.md`; the ones that change how this project is built:

| Found | Why nothing caught it |
| --- | --- |
| 🚨 **A coherent cluster lifted the one pair that did NOT agree with it** — 52 s from its own group's consensus, two different shows, written CONFIDENT | ⛔ **The check was asserting the defect**, and `arbitrate.consensus_offset()` existed unused. `agrees_with()` now owns the question *and* the ms/s conversion |
| 🚨 **`holds_throughout` is vacuously True when every bucket was too thin** | `_runtime_check` detected it exactly (`absent`) and the verdict recorded the string without reading it |
| 🚨 **`all()` over an empty range is True**, so one failing bucket was always a "commercial break" — including the corpus's own *drifting* edit, with wrong advice | A one-element `_contiguous` cannot return False. Now also requires the jump to be **break-sized** |
| 🚨 **A dropped-everything write produced a 0-byte file, `ok=True`** | The zero-cue refusal existed on the INPUT side only |
| 🚨 **`find("\n\n")` misses `\r\n\r\n`** — WebVTT deleted `NOTE`/`STYLE` blocks on **66% of the corpus** | ⛔ **There are ZERO `.vtt` files in the corpus**, so no real-data check could ever see it |
| 🚨 **A cue whose TEXT is a number was deleted as an index line** | The SRT fixture was blank-line separated with alphabetic text |
| 🚨 **A cue straddling the break was written `end` before `start`** | D9 was tested *inside* the gap; the boundary crossing was not |
| 🚨 **`apply_plan` wrote a REFUSED verdict** (found by my own seam review) | `dedupe.plan()` gated it; the module that touches user files did not |

⛔ **Two claims in this pack's own prose were false and are corrected:** *"telling a cut
from drift needs NO new constant"* (it was comparing a spread to a magnitude — a taste
threshold), and `dedupe.py`'s *"`shutil.rmtree` is not imported and must never be"* (true
of the file, false of the behaviour — `shutil.move` reaches it on a cross-device move of a
directory). ⭐ **When a docstring claims a design needs no threshold, grep for the one it
is using.**

⚠ **One finding is NOT fixed and is Sonic's to rule:** `"certain"` is a substring of
`"uncertain"`, so the weakest word this tool writes contains the strongest — re-arming
`LEDGER.md` §Interface's GUI defect for any consumer that substring-matches. The
vocabulary is `05-interface.md`'s. Pinned by a check; surfaced as a ruling.

### ⭐ 3a — what landed 2026-09-09, and what it cost to find

| | |
| --- | --- |
| ⭐ **The reader is aimed at two LIVE defects** | subliminal 2.7.1 reads `.ja.forced.srt` as `und` (it expects `.ja.fo.`), so a correctly-named forced subtitle is re-downloaded **forever**; Bazarr matches flags as **substrings**, so `Show.chi.srt` is Chinese-**and**-hearing-impaired. They fail in **opposite directions**, so a check for one passes against the other. hato imports this reader rather than writing its own |
| **The algorithm, and it is one sentence** | the LEFTMOST dot token that is a language code **and** has nothing but known flags to its right. Both of hato's one-line rules fall out of it rather than being bolted on |
| ⭐ **ONE language table now** | `movies._LANG2` and `episode._SOFT` were two private copies; the second had no European codes, which `HANDOFF.md` already carried as an open item (`.es`, `.fr.forced`, `.pt-BR` at **0%**). `sidecar.ISO_639_1` is the one owner and `movies.py` imports it — byte-identical, 256 neighbouring checks unchanged |
| ⛔ **Nothing is ever deleted, structurally** | `test_dedupe.py` walks `dedupe.py`'s **AST** and fails if it calls `remove`, `unlink`, `rmdir`, `removedirs` or `rmtree`. `trash()` is dry-run by default; the fallback is a **move** into `.tsubasa-trash/` that keeps the original name and never overwrites |
| ⛔ **Rule 1 is a GATE, not a sort key** | *A refused candidate never wins* — sorted, the least-bad refusal wins whenever every candidate was refused, which writes the best of several rejected files. With nothing confident there is **no winner, no write and no trash**, and the reason says so |

🚨 **THE DRY RUN FOUND WHAT 94 GREEN CHECKS COULD NOT.** `output_name` wrote the language
tag unconditionally, so **95.8% of real slots — 5,980 of 6,192 files — would have been
renamed to `.und.`**, a token no player understands, on files the user never asked us to
touch. It also made the namer non-idempotent. After the fix: **48 renames**, every one a
`.JA.` → `.ja.` case normalisation. ⚠ **No fixture could have found it**, because a
fixture is written by someone thinking about languages and therefore always has one.

⚠ **A guard was DELETED on measurement.** `sidecar.WINDOW` bounded how far back the tag
scan looked; its mutation **survived**, and probe 3a/1 measured both arms over **24,315
real filenames** at **0 differences**. The right-hand constraint was the guard all along,
and on the one shape the bound could change it gave the *worse* answer. Same sequence as
the alias score gate.

⚠ **Two spec gaps recorded, not decided:** `05-interface.md` never says what `<lang>` is
when there is no language (95.8% of real files), and its `--keep-all` form
`<video>.<lang>.<tag>` **does not round-trip through this project's own reader** — a tag
after the language makes every file we write read back as `und`. The tag goes before it.

⚠ **`send2trash` is not installed on the build machine.** The OS path is reached through an
injected sender and `TSUBASA_NO_OS_TRASH=1` — the same seam shape as
`TSUBASA_NO_NATIVE_DEMUX=1` — so it is not *code that never runs in the local
configuration*, which `07-test-plan.md` forbids by name.

## Step 3a-bis — ✅ The results DB — DONE 2026-09-09

**surfaces:** `data` · **depends on:** 3a · **authority:** `02-data-model.md` §*The
results DB*, `06-edge-cases.md` §7

🚨 **A GAP IN THIS RUNBOOK, NOT IN THE SPEC — Sonic, 2026-09-09:** *"'Every run re-does
the work' is the results DB's job, and **no runbook step builds it.** That is a gap I
introduced when I rewrote the runbook."*

`02-data-model.md` lists it as **one of the four stores** and specifies it fully — keyed on
the **content hash of the subtitle**, so it survives renaming, and it exists because Sonic
ruled **no `.synced` marker in the filename**. Two ruled behaviours depended on it and
neither could hold:

| `06-edge-cases.md` §7 | Was | Now |
| --- | --- | --- |
| **Re-run, nothing changed** → hash-and-skip, **≤ 1 s for 24 episodes**, zero decoding | ⛔ Every run re-aligned everything | ✅ **0.26 s, 0 container reads** — `$TSUBASA_CORPUS/_work/probe_3abis_1_rerun_cost.py`. 🚨 **The corpus's `_work/`, not the repo's** — every probe in this project lives there, outside TheForge, and the bare path cost a session |
| **DB says synced, file says otherwise** → 🚨 **the file always wins**; the DB is advisory | ⛔ Nothing to win against | ✅ An edited output and a deleted one are both re-measured |

⚠ **It is the real answer to a question 3b could only paper over.** Dedupe rule 5 was
promoted at 3b so a retimed output stops ranking below its own source — that is right on
its own merits and it is a **symptom fix**. What actually identifies *"this is the file we
wrote last time"* is the hash, and only the DB has it.

| | |
| --- | --- |
| **Built** | `tsubasa/results.py` — `Results` (the store), `Record`, `Considered`, `Settled`, `settled()`. Keyed on the content hash of the file this tool **WROTE**, under `paths.cache_root()/synced`. ⛔ Never beside the media |
| **Wired** | `pipeline.sync(..., results=)` — the skip read at the top of the per-video loop in `_sync_scan`, **before `reference_for`**; `_record_slot` after `_perform_slot`; `SyncReport.settled`; `_resolve_ownership(protected=)` |
| **Proved** | `tests/test_results.py`, the **35th suite**, **35 checks**, registered in `tsubasa.config.json` · `probe_adj29_resultsmutants.py` — **34 mutants, 0 survivors, 4 controls held**. ⚠ It was 29 checks and **11 survivors** first; see below |
| **Measured** | 24 distinct episodes: run 3 in **0.84 s**, **0 container reads**, 24 records. The O(1) claim on a real **92 MB** video: **128 KB read, 0.14% of it**. ⚠ The clock is weather; **bytes-read per file** is the number that transfers |
| ⚠ **It was 0.26 s before subtitles were hashed WHOLE** | The ruled budget is ≤ 1 s and it still holds, **with much less room**. That is the price of *the file always wins* being true above 128 KB, and it is worth knowing before anything else is added to the settled path. ⭐ One memo already recovered part of it: a subtitle offered to several videos is hashed once per RUN, not once per offer |

⛔ **Advisory, never authoritative.** `06-edge-cases.md` is explicit and it is the whole
safety property: if the DB and the file disagree, the file is right. A DB that can veto a
re-sync is a DB that can make the tool refuse to fix something it broke. Every question the
module answers is asked **of files it has hashed this run** — there is no
`get_by_digest(str)`.

### 🚨 THE LOAD-BEARING INVENTION IS `Record.stable`, AND A RED SUITE FOUND IT

**The first run over a folder leaves work undone.** It sees one candidate, writes it out
under the video's basename, and leaves the original — a winner is never superseded. So the
folder now holds **two** subtitles where `05-interface.md` rules one. **Run 2 is what fixes
that**: the canonical file is now a candidate, it wins on rule 5, and the stale original
goes to the trash.

⛔ **A store that called run 1's state *settled* skips run 2, and the folder keeps both
files FOREVER — a ruled property defeated by the cache meant to make it cheap.** Built
that way first, and
`test_pipeline.py::test_ONE_FOLDER_mode_converges_and_never_trashes_its_own_output` went
red with the original still sitting in the folder. ⭐ **That check is the reason this is
right, and it is exactly the collision `3c-0` predicted** when it removed an `xfail`
calling the second run a defect: *"it would have gone red the moment 3a-bis fixed it."*

⭐ **The test that separates them: was the run's own output already something it had
CONSIDERED?** Run 1 wrote a file that was not among its candidates, so the next run has an
input it has never weighed — not settled. Run 2 rewrites a file that **was** among its
candidates and trashes the rest, so nothing new exists — settled, and run 3 is the cheap
one. A record therefore carries the slot from **both sides**: `offered()` is what the plan
was made from, `expected()` is what should still be on disk, and `stable` is
`expected() <= offered()`.

⚠ **The one behaviour change to an existing check.** `test_ONE_FOLDER_mode_converges…`
asserted `third.written and third.written[0].superseded == []`; run 3 now skips, so it
asserts the skip instead — `third.written == []`, one entry in `third.settled`, and
`"already in sync"` in the summary. Every other claim in it is untouched and still green:
one subtitle at the name a player loads, the original recoverable in the trash, run 3
changing nothing.

### The three conditions for a skip

1. ⭐ At least one candidate on disk **is** a recorded output for this video —
   `06-edge-cases.md`'s *"the synced file's hash is in the DB"*, and also the check that
   the DB and the disk agree.
2. 🚨 Every such record is `stable`.
3. ⭐ The digests present now are **exactly** what those records expect. Not a subset — a
   missing file is the DB and the disk disagreeing. Not a superset — an extra file might
   be the better subtitle.

⛔ And nothing about paths, which is the point of a content key.

### ⚠ FOUR CONSEQUENCES, NAMED RATHER THAN HIDDEN

| | |
| --- | --- |
| 🚨 **A skipped video still OWNS its files** | `_resolve_ownership` rule 1 is computed from the slots of THIS run and a skipped video contributes none, so its answer would be an ordinary losing candidate of whichever neighbour also matched it — **the 3b library-losing shape through a new door.** `Settled.protected` is that rule extended to the videos that are not here |
| 🚨 **A new episode in a settled folder gets a THINNER CLUSTER** | `clusters_for` sees only what was measured this run, so an episode added beside twenty-three skipped ones has no neighbours to cohere with — and coherence is `D7`, the escalation band's second signal. It errs safe (REFUSED where a full run would have lifted it). ⛔ **NOT quietly patched by feeding remembered offsets into the cluster**: `D7` is a Sonic ruling about what evidence may lift a pair, and changing its inputs is not a cache's decision to make |
| ⚠ **A settled FILM library still pays for `pair_movies`** | The film pairing runs before the loop and its `duration_of` seam reads containers — lazily, so television pays nothing, but a film set reaching the runtime veto is opened whatever the store says. *Zero decoding* is measured and true for episodes; for films it is *fewer* |
| ✅ ~~**`--out` never settles**~~ | **Fixed.** The record now carries the run's SHAPE, so a settled library asked for `--out` does the work instead of reporting success over a directory it never created. ⚠ The original note here was **false in the direction that matters** — it described the `--out` run RECORDING, not a library settled earlier and then run with `--out` |
| ⚠ **`--keep-all` does not settle** | Each run's outputs become the next run's candidates and the flag never trashes, so the set grows until two byte-identical candidates collide on the distinguishing tag and the slot writes nothing. Safe — no loss, no wrong file, `NOT WRITTEN` reported — but `06-edge-cases.md` §7's *zero decoding* is false for this flag, and that section now says so. ⛔ **Wants a ruling:** *keep every candidate* most likely means *every distinct **subtitle***, which is consistent with *trashes nothing* and would converge |

### ⛔ What it deliberately does NOT do

- **The explicit path RECORDS but never SKIPS.** The user typed those pairs; naming a pair
  is an instruction to act on it, and answering an instruction with *"I did that last
  week"* is the same silence `--force` on a `Scan` is refused for. It is also what would
  leave `plan.writable()` with an undecided pair, which raises — so the structure says it
  too. ⭐ It records, because a file synced explicitly that a later discovery run then
  re-aligned would be *"every run re-does the work"* with an extra step.
- **A dry run records nothing**, and a forced write is **deliberately** not recorded — a
  forced write is reported as REFUSED because it is the most dangerous thing this tool
  does, and recording it would make the next ordinary run skip it **in silence**.

### ⭐ TWO THINGS THIS STEP FIXED THAT WERE NOT ITS JOB

| | |
| --- | --- |
| 🚨 **The suite was writing into the developer's real per-user store** | `sync()` falls back to `_default_trash_root()` under `paths.cache_root()` whenever a check forgets `trash_root=`, so this has been true all along. `conftest.py` now points `TSUBASA_CACHE` at a throwaway directory for the whole session. ⚠ The four checks that assert something about the REAL default (`test_cache.py` ×2, `test_wiring.py` ×2) clear it themselves — *"the cache is not inside the repo"* is a claim about the shipped resolver and a temp directory satisfies it vacuously |
| 🚨 **`e2ebench` scenarios shared state its own docstring forbids** | *"Its own tree per scenario: a shared one lets scenario N's leftovers decide scenario N+1"* — and the tree stopped being the only shared state the moment `sync()` learned to remember. Measured: `out_dir` runs before `keep_all`, both stage Sintel, and `out_dir`'s output is byte-identical to `keep_all`'s freshly staged source, so `keep_all` recognised a file it had never synced and wrote **2 outputs instead of 3** against a green floor. Each scenario now gets its own `TSUBASA_CACHE`. ⛔ **A bench whose answer depends on whether it has been run before is not an instrument** |

### 🚨 TWO ADVERSARIAL PASSES — ~27 findings, four of which lost or corrupted a file

⭐ **`doctrine/verification` Layer 2, run as it prescribes: fresh agents whose only job
was to defeat the checks.** Three ran against 3a-bis; one then ran against the **fixes**.
Both rounds returned defects in checks written the same session — which the doctrine says
to expect, and budget for.

#### Round 1 — three agents, ~20 findings against 35 green checks

| Found | Why nothing caught it |
| --- | --- |
| ⛔ **A SETTLED VIDEO'S SUBTITLE DESTROYED IN PLACE, no trash copy, on DEFAULT FLAGS** — found independently by **all three** | `Settled.protected` was wired into `_resolve_ownership` **rule 1** (never superseded) and rule 2 (never written over in place) is computed forty lines earlier from `slots`, which a skipped video has none of. ⛔ **This RUNBOOK carried the same scoping error**: *"rule 1 is computed from the slots of THIS run… `protected` is that rule extended."* Rule 2 was never asked |
| 🚨 **The check named for it could not fail, for TWO independent reasons** | Different stems mean the twin writes a different NAME, so no overwrite is possible; and both rips were built from one `MKV_CUES`, so even on an overwrite the offset is identical and **the byte assertion is satisfied by the defect**. Only *same stem + different timing* is red |
| 🚨 **`Record.stable` was True after run 1 whenever the offset was ZERO** | `apply` writes back the bytes it read, so the output hashes to its own source. As SETS that is `{d} <= {d}` — a fixed point, with two subtitles in the folder, for ever. ⭐ The input is the ordinary one: a subtitle already correct for that release, which is exactly what hato fetches. Every fixture hardcoded a 2.0 s delay |
| 🚨 ***"The file always wins"* was FALSE above 128 KB** | `content_key` is head+tail+size and a retime is length-preserving. And the guard claiming to catch it — *"the SIZE is the independent witness"* — was **unreachable for any file that exists**, because the size is hashed INTO the digest |
| 🚨 **A record carried no trace of the run's SHAPE** | Settle a library, then ask for `--out elsewhere`: `1 already in sync`, **output directory never created**. ⛔ No check could catch it — every check re-ran with identical flags |
| 🚨 **A user's file DESTROYED on a plain first run** — not the results DB at all | A better subtitle wins on cue count and `output_name` names the output the LOSER's own path. `os.replace` obliterates it; the trash loop skips it as *"written over"*. ⛔ `test_apply_owns_no_deletion_primitive` **passes** — the deletion is `os.replace` one module away. **The structural proof is true and the property is false** |
| ⚠ **One check was asserting the defect** | `test_a_loser_the_winner_is_written_OVER_is_never_trashed` required the user's 60-cue subtitle *not* to be trashed while it was being destroyed. Its docstring reasoned correctly about the identity case and wrongly about this one |

#### Round 2 — against the fixes. Seven findings, and one was a regression the fix caused

| Found | |
| --- | --- |
| 🚨 **THE FIX MADE THE STORE WORSE THAN NOT HAVING ONE** | `protected` was *every candidate*, so a settled video stood in as an owner of its live **neighbour's own output** and rule 2 refused that neighbour's ordinary in-place re-sync — **permanently**, because the settled twin's candidates never change. The correction was measured and never applied. ⭐ The counterfactual is the finding: same library, `results=False` corrects it, a fresh store corrects it, the settled store does not |
| 🚨 **Two slots, one TARGET — a confidently wrong file, then frozen** | Rule 2 guards a shared SOURCE; nothing guarded a shared TARGET. `Show S01E01.mkv` + `Show S01E01.mp4` — an ordinary re-download — both resolve to `Show S01E01.ja.srt`: `2 synced`, one video **5 s wrong**, reported `CONFIDENT · locked`. Pre-existing since 3b |
| 🚨 **The trash succeeded and the write then failed** | Folder left with **neither** file, and two notes in one report contradicting each other — the second being the sentence the *previous* fix added to promise it could not happen |
| 🚨 **`--keep-all` counted every survivor once per kept file** | N writes in ONE slot mint N records sharing one `considered` list. The comment said the slots *"are disjoint by construction"* — true of SLOTS, **false of RECORDS**, and `--keep-all` is the one flag whose meaning is several records per slot |
| 🚨 **The explicit path still hashed subtitles with the SAMPLED video key** | Every explicit record was keyed on a digest `settled()` can never compute. ⚠ And the check crediting it was hollow: it called `settle()` afterwards, so two discovery runs did the work it named the explicit run for. **The same shape this file already records for `settle(runs=3)`** |
| ⚠ **The dry run described the design the fix removed** | The trash-first branch was gated on `not dry_run` while `written_paths` is populated either way, so the plan promised in writing the destruction the branch exists to end |

### ⭐ WHAT THE FIXES ARE

| | |
| --- | --- |
| ⛔ **Two ownership rules, two sets** | Rule 2 gets the settled videos' **answers** — the files they wrote. Rule 1 gets **everything they were offered**. Conflating them cost a defect in EACH direction: outputs-only let a neighbour trash a surviving source, everything-offered let a settled video veto a live re-sync. ⚠ And a record's answer is attributed to **the video that wrote it**, because two rips retimed alike produce byte-identical outputs and a digest lookup handed both to everyone |
| ⛔ **A superseded file at the winner's target is trashed FIRST** | The order inverts **for that case only**, and its justification inverts with it: *write first, trash second* exists so a failed trash after a good write leaves the user both files — when the target **is** the file, a good write leaves them **neither**. ⭐ And if the write then fails, the occupant is **put back** |
| ⛔ **Two slots may not write to one path — NEITHER is written** | There is no output name that serves both: a player loads `<video-basename>`, both videos share one, so `Show S01E01.mp4.ja.srt` is a name nothing loads. The clash is in the library, not the code, and the only honest answers are *refuse both* or *be confidently wrong about one* |
| ⭐ **`expected()` / `offered()` COUNT — they are not sets** | `{digest: how many files}`. One change fixed the zero-offset false fixed point AND the invisible duplicate deletion, because both were a set failing to count. ⚠ The output is counted once, keyed by PATH: an in-place retime makes it one of the survivors |
| ⭐ **A record carries the run's SHAPE** | `rename` · `out_dir` · `keep_all` · `dedupe`, compared as a whole. Reasoning about which flags may safely differ is how the first version had none |
| ⭐ **Subtitles are hashed WHOLE; videos stay sampled** | The two questions were never the same question. `RESULTS_VERSION` → 2 |
| ⭐ **`store.get` and `store.record` fail open** | *A store that can break a run is worse than no store* — the rule `Results.get` had held alone |
| ⭐ **One hash per file per run** | A subtitle offered to several videos was hashed once per offer. ⚠ Safe because the discovery loop completes before any slot is performed; the memo is the run's and dies with it |

⭐ **The ratchet is closed.** Twelve new checks, and `probe_adj29` is **53 mutants / 0 survivors / 7 controls held**. Seven of those mutants exist only because an adversary found the gap they guard.

⚠ **Two mutants are recorded as EXPECTED SURVIVORS with their reasons** rather than deleted — `LEDGER.md`'s rule that a survivor is information either way. The interesting one: **keying a record on the source versus the output is now unkillable, because at the fixed point the winner IS the output** — same path, same digest. What output-keying buys is rename-survival, which has its own check.

### 🚨 THE MUTATION RUN — ELEVEN SURVIVORS AGAINST 29 GREEN CHECKS

⛔ **Not one was a wrong constant or an inverted comparison**, which is the same closing
note 3b's adversary left. They were fixtures that could not tell two behaviours apart.
Full record in `LEDGER.md`; the four that change how a suite gets written:

| Found | Why nothing caught it |
| --- | --- |
| 🚨 **The suite's own `settle()` helper ran `sync` THREE times over a folder that converges in TWO** — so a mutant that corrupted what run 2 recorded was overwritten by run 3, a run with nothing left to get wrong, and the measured fourth run skipped normally. **Four mutants survived through it** | ⭐ **A fixture that iterates more than the claim requires lets the system route around the defect.** Ask what the extra iteration is for; if the answer is *"to be safe"*, it is hiding something |
| 🚨 **The `gone` arm is unreachable while dedupe is on** — records are FOUND through the candidates on disk, so deleting the output means no record is found and *"no completed sync is recorded"* answers first | ⛔ A guard answered by a different guard looks covered. It needs `dedupe=False`, where a losing SOURCE survives, is recorded as a survivor, and can then be deleted while the output stays |
| 🚨 **Byte-equality cannot see a missing skip** — a re-run of a converged folder writes at an offset of ~0, so *it skipped* and *it did the work again and got the same answer* are byte-identical | ⭐ Same family as `{name: size}` being blind to a retime, one level up: the OUTCOME was identical, so only the WORK could tell them apart. The check now asserts zero container reads |
| ⚠ **A check that monkeypatches the thing under test cannot see a mutant that replaces it** — the atomicity check patches `atomic_write_bytes`, overwriting the mutation | ⭐ Kept as an **expected survivor with its reason**; what guards it instead is a SOURCE check, the same shape as `dedupe.py`'s AST check for deletion primitives |

⚠ **Two more, both about the instrument rather than the code:** the `textwrap.dedent` trap
bit again — a **method's** anchor sits at four spaces, not eight, and **ten mutants
faulted** on it in the first run, which cost nothing only because the harness gives FAULT
its own verdict. And a mutant that compared `r.outcome != 'confident'` when the constant is
`'CONFIDENT'` fired **zero times** and reported SURVIVED. ⛔ *A non-zero exit is not
evidence* has an inverse: **a zero exit is not evidence either.**

### ⚠ AND A FIXTURE DEFECT THE PROBE FOUND THAT 29 GREEN CHECKS COULD NOT

The 24-episode check was built from **24 identical copies** — same video bytes, same
subtitle bytes — so the store held **ONE record for twenty-four episodes**. Every skip was
matching an episode against a record made for a different one, and a version keyed on the
wrong thing entirely would have passed. ⭐ The probe printed `1 records`; the suite printed
`PASS`. The fixtures now vary the cue TEXT and `per_cluster` — two knobs that move the
bytes without moving a single timestamp — and the check asserts **24 distinct records**
before it measures anything.

---

## Step 3b — Library API

**surfaces:** `logic` · **depends on:** 3a

🚨 **RULED 2026-09-08 — `sync()` TAKES A `PairPlan`, NOT RAW TUPLES. This is binding.**

`05-interface.md` promises `sync([(video, subtitle), ...], write=True)` natively. ⛔ **If
`sync()` consumes those tuples directly, the tuple path silently skips every refusal A11
built** — the missing path, the swapped arguments, the same subtitle claimed twice, the
duplicate that is refused on *both* sides. Sonic's words: *"a tuple path that silently
skips every refusal is the one shape the whole project exists to prevent."*

⭐ **`sync()` converts its argument through `explicit.explicit_pairs()`** and works from the
resulting `PairPlan`. The tuple signature stays — the guarantee comes with it.
⚠ And `--force` routes to `decide()`, **never** to `explicit_pairs()`; that routing *is*
the mechanism, not a convention.

`scan()` returns **candidate sets** (no media I/O); `sync()` probes, aligns, decides,
and only writes when told (`05-interface.md`). ⚠ **hato consumes four surfaces from
here** — parser, discovery, sidecar reader, `align()` — and their shapes freeze at this
step. Integration test mimics surasura: junk-filled sub folder, separate video folder,
library prints nothing and writes nothing unless `write=True`.

### 🚨 A SPEC CONFLICT ABOUT `scan()`, RESOLVED AND RECORDED (Part 1 defect)

`05-interface.md`'s code comment said `scan()` reads *"filenames, stat and the container
INDEX only (30 KB per MKV)"*; the line above says **no media I/O**. Those are different
contracts — **30 KB per MKV is 1d's Cues-indexed TIMING read**, measured at 0.087 s a
file, so on a 1,500-file library the two readings differ by minutes of work done before a
single decision exists.

⭐ **Built to the tighter one: `scan()` opens nothing.** `sync()` must read the track
anyway, so a read in `scan()` is either duplicated or cached; and *"opens nothing"* is the
version a check can enforce, which *"reads about 30 KB"* is not. Amended in
`05-interface.md`, which now carries the reasoning.
⚠ **The consequence is named, not hidden:** `Scan.films` is **provisional** — without
runtimes the movie path has neither the duration veto nor the runtime tiebreak, so it
refuses a film set it cannot separate on name and folder alone. `sync()` re-runs the same
`movies.pair_movies()` with the durations it has opened. One authority, called twice with
different evidence.

### ⭐ What 3b is built from, and what it added

| | |
| --- | --- |
| **Build** | `tsubasa/api.py` — `scan()`, `Scan`, `Candidacy`, **`Result`** (the shape hato pins) · `tsubasa/pipeline.py` — `sync()`, `SyncReport`, `reference_for()`, `measure()`, `clusters_for()`, `judge()` · `tsubasa/__init__.py` exports `scan`, `sync`, `align`, `Result` |
| **Prove** | `python -m pytest tests/test_api.py -q` · the mutation probe `_work/probe_adj26_apimutants.py` |
| ⭐ **The split** | `api.py` is *what is here*; `pipeline.py` is *what happens to it*. It is a real seam — `scan()` is the half a caller runs over a whole library and it has to stay free |
| ⭐ **Two passes, and the cluster is why** | Every pair is measured, **then** judged. A cluster's coherence is the escalation band's second signal (`09-corpus-strategy.md` Stage 4) and it does not exist until every episode is aligned — judging as we go would decide the weak pairs before the evidence that lifts them was in hand |
| ⭐ **One `Result` per (video × language) slot** | The same unit dedupe works in, and the same unit `05-interface.md`'s ruled output prints. Losers are `superseded`; candidates that never became plausible are `notes`. ⚠ `--keep-all` is the exception and produces one per kept file, because the flag's whole meaning is that there is no single winner |
| ⚠ **A video with nothing to try is NOT a `Result`** | It is not a pair, so it has no outcome — `03-permissions.md` says there is no fourth and inventing one would be a lie. It is `SyncReport.unpaired`, and `summary()` leads with it |
| ⛔ **`force` is explicit-pairs-only** | On a `Scan` it would mean *write the best of several REFUSED candidates*, which is exactly what `dedupe.py`'s rule 1 is a GATE rather than a sort key to prevent. `sync(scan, force=True)` **raises**; ignoring it would leave the user believing they had overridden something |
| ⛔ **`vad=True` neither works silently nor raises from four frames down** | `MASK_BAND` is `None` until B6. The run carries a note saying the band has never been fitted and that borrowing the cue-vs-cue 2.5× would silently refuse the 2.42× uncut pair §5 measured as **correct** |
| **The reference** | The subtitle track with the **most cues** wins, then `default`, then non-`forced`, then index. A forced track is signs-only, so ranking on cue count deprioritises it without excluding it — Rule 1 says the embedded track is an accelerator, and a thin accelerator beats none. ⚠ A thin one is not silently trusted: every bucket comes back too thin, `runtime_check` is `absent`, and the verdict caps the word at `fair` |
| **The trash root** | `paths.cache_root()/.tsubasa-trash`. ⛔ `dedupe.py` deliberately has no default *"that could quietly be the media folder"*; `sync()` is the caller that has to supply one |
| ⭐ **Three handoff items closed here** | `Item.set_content_end()` is the one writer for `Item.cues` and uses `duration.content_end`, never `max()` · **NCOP/NCED is refused on BOTH sides** at discovery (`movies.is_creditless` was reachable only from the film path, so a creditless opening carrying an episode number went straight down the TV path) · **`cues.clamp_negative` DELETED** — zero callers, and it asked the before-zero question on the **raw** axis where `apply._render` asks it through the mapper. Not duplicates: one of them was simply wrong, and it was the `duration_verdict` shape at A9 — *a public helper nothing called, so it cost nothing, and a landmine wired to its first caller* |

### 🚨 3b's ADVERSARIAL PASS — 14 findings against 33 green checks, 3 of them file-losing

⭐ **Budget this as its own session; the 2026-09-09 note in `dev-build` is right.** One agent,
30 minutes, against the READ-ONLY half only. **Twelve mutants survived every suite in the
project.** The full record is `LEDGER.md`; the ones that change how this gets built:

| Found | Why nothing caught it |
| --- | --- |
| 🚨 **`is_creditless` fires on the ordinary word `cleaned`** — swept over **40,993 real corpus filenames**: 28 hits, **3 real subtitles**, and `cleaned` is a community convention for a sub with ads stripped | `clean[\s._\-]*(?:op\|ed)` accepts ZERO separators. Every existing check used `NCOP`/`NCED`. ⭐ The same sweep found `NCOP1v2` — the commonest real creditless form — being MISSED |
| 🚨 **`os.path.commonpath` raises on two UNC shares**, so `\\nas\media` + `\\nas\subs` threw out of the library | The guard was `da[:1] == db[:1]` and **both UNC paths start with a backslash**. No fixture in the project has one |
| 🚨 **`walk()`'s file-root branch skipped the `seen` dedupe** → one file, two `Item`s → `dedupe` supersedes the duplicate → the user's only copy is trashed | Deleting the `seen` set **entirely** survived every suite |
| 🚨 **The check written for an exception was testing the hole.** `Result` accepted REFUSED + `output_path` with `forced=False`; the comment said the exception was `forced`, the code said `outcome == ERROR`, and the check never set `forced` | ⭐ **When a comment names an exception, grep the code for it.** This is the same class as *grep for the threshold the docstring says is not there* |
| 🚨 **The two-folder rule was false whenever the roots NEST** | ⛔ **Both checks for it used DISJOINT roots.** A rule tested only on the easy geometry |
| ⚠ **`_parsed_of` was a dead seam** — keyed on basename, called with the full path, **0 hits out of 0/2** | Two mutants survived every suite. A Rule 4 optimisation nobody measured |

⭐ **The transferable lesson, and it is not "run adversaries":** every finding sat on a
boundary, and **the boundaries were new**. `proximity`, `is_creditless` and `walk`'s
file-root branch had all been correct-by-not-being-called. A step whose whole job is to
make things reachable should expect its findings to be about reachability.

### 🚨 THE SECOND PASS — the RUN half, ten findings, and it lost a whole library

⭐ **A different surface, run separately, and it found worse than the first.** One agent
against `sync()` at **49 green checks and 77 killed mutants**. Two of the ten destroy user
data on **default flags**.

> 🚨 **An ordinary library of two shows using bare episode numbers lost EVERY subtitle it
> had, and the report said `2 synced`.** The episode index correctly offers each video
> both shows' `01.ja.srt`; the foreign one is correctly REFUSED; and `dedupe.plan`
> supersedes every non-winner **in its slot** — which is another slot's **winner**.

⛔ **Every layer was individually right.** `dedupe.plan` decides one slot from the
candidates it was given and cannot see the run. `sync()` sees the run and never asked.
**The defect lived in the gap, so no unit check and no mutant could reach it.**

The others, in one line each: a shared subtitle **retimed twice** in one run (−4.0 s for a
true −2.0 s, both CONFIDENT); the trash loop running **after every write failed**, leaving
neither file; a `write=True` run whose writes all failed being **byte-identical in its
report to a dry run**; **`--out` flattening** two shows into one file; two explicit pairs
collapsing into one Result with the other trashed; `Result.forced` true for **every** pair
whenever the flag was passed; `superseded` copied from the plan rather than from what
moved; cluster coherence **0.50** in an ordinary downloads folder.

🚨 **AND THE ADVERSARY'S CLOSING NOTE IS THE FINDING ABOUT THE METHOD:**

> *"None of these is a wrong constant or an inverted comparison. They are missing checks,
> cross-slot state, and reports composed from the plan instead of from what happened — the
> classes mutation testing over this suite cannot reach."*

⭐ **77/77 mutants was true and it was not evidence about any of it.** Layer 1 proves a
check *can fail*; it says nothing about a check nobody wrote, and nothing at all about a
defect between two correct modules. ⛔ **Do not read a clean mutation run as permission to
skip Layer 2** — on this step it was the weaker of the two by a wide margin.
⚠ Three of these were also **hollow green checks**: the `--out` one asserted
`dirname(output) == out_dir` on a ONE-video fixture, which is precisely what flattening
looks like.

## Step 3c-0 — ⭐ THE END-TO-END BENCHMARK, ON REAL MEDIA — BEFORE the GUI

**surfaces:** `harness` · **depends on:** 3b · **authority:** `07-test-plan.md`

🚨 **RULED BY SONIC 2026-09-09, and *"it is not close"*:**

> *"The GUI shells out to the CLI, so a wrong CLI is a wrong GUI debugged through two
> layers. If it lands after the GUI, the GUI becomes the first thing that ever exercised
> the whole path."*

⛔ **NOTHING MEASURES THE PRODUCT END TO END.** `vnbench` — the release number — scores
**names** through `same_series`, not `sync()`. It sat at **80.0% through the whole of 3a
and 3b** and would have done so if every one of them were broken. It is why the two-folder
output-directory defect survived to a dry run, and why ten more waited for an adversary.

⭐ **The defect class it catches is precisely the one units cannot see**: cross-slot state,
reports composed from the plan, a write landing in the wrong folder. And it is cheap now —
`video/Sintel-60s.mkv` and the `video-derived/yomi18/` set both exist.

| | |
| --- | --- |
| **Build** | `tsubasa/dev/e2ebench.py` → `e2e --all`. Assembles a real library in a **temp directory** from the staged media, runs `scan()` → `sync(write=True)`, and asserts on the resulting TREE: which files exist, where, and with what first-cue times |
| ~~**Prove**~~ | ~~the four `MUST_REFUSE` pairs write nothing · a correct pair lands **beside its video** with the measured offset · a two-show folder keeps every source · a second run is idempotent~~ — **three of these four were wrong. See below.** |
| ⛔ **Where it writes** | Sonic: *"It writes files, so a temp directory, never the corpus."* `Rule 3` already forbids media in TheForge; this adds that the corpus is read-only to it |
| **Register** | as a suite, and record its floor the way `vnbench` does — a **floor**, never a target |

### ✅ DONE 2026-09-09 — and the Prove line above was wrong three ways

`tsubasa/dev/e2ebench.py` + `tests/test_e2e.py` (the **34th suite**, `e2e`) +
`e2e-baseline.json`. Nine scenarios, **22 checks**, 4.2 s, and
`_work/probe_adj27_e2emutants.py` — **40 mutants, 0 survivors**, plus three controls that
must survive and one expected survivor carrying its reason.

🚨 **A new fixture was staged**: `video-derived/yomi18/track_2.mkv`, that folder's own
`track_2.ass` remuxed into a real Matroska so the benchmark drives the **real container
reader** rather than the injected double the `pipeline` suite has to use. Verified faithful
on **every run**, not once: 323 cues, worst cue disagreement **0.000000 s**. The ffmpeg
line that rebuilds it is in that folder's README.

**What the Prove line got wrong, all corrected in place:**

| Written | Measured |
| --- | --- |
| 🚨 *"the four `MUST_REFUSE` pairs write nothing"* | ⛔ **Wrong three ways.** `MUST_REFUSE` is a defined identifier in `subsync/tests/corpus.py` naming **five** oracle pairs, **none of them a yomi18 file**; the yomi18 set has **three** refusals; and `07-test-plan.md` and the folder's README both say *"Four of the six"*. ⭐ And on the **cue-vs-cue** path only the wrong episode is refused at all — the two AT-X cut files are **SOLVED**, because §5's refusal is a statement about the **speech mask**, where the break is invisible. **Asserting they write nothing would have been a check asserting the defect.** |
| *"a second run is idempotent"* | 🚨 **It is not, and that is a RULING.** `test_pipeline.py::test_ONE_FOLDER_mode_converges_and_never_trashes_its_own_output` is green over three runs asserting the opposite: run 2 sends the stale original **to the trash — recoverable, never deleted**. ⛔ An `xfail` calling this a defect was written and removed the same day; it would have gone red the moment 3a-bis "fixed" it and taken `test_pipeline.py` with it. **Two suites contradicting each other about one run is worse than either being wrong.** The check now asserts the ruling: everything that moved is recoverable **by content hash**, and run 3 changes nothing. ⭐ **THE PREDICTION CAME TRUE AT 3a-bis, and removing the xfail is why it cost nothing.** Building the store to call run 1 *settled* took `test_pipeline.py` red with both subtitles still in the folder — so the ruling held the line and `Record.stable` is the shape that satisfies both. What did change: **run 3 now SKIPS** rather than re-doing work it changes nothing by, so that check asserts the skip. `taken_by_the_second_run` in `e2e-baseline.json` is **untouched** |
| *"a two-show folder keeps every source"* | ✅ Holds, and is asserted |
| *"a correct pair lands beside its video with the measured offset"* | ✅ Holds — and needed a **two-folder** scenario to mean anything. In one folder *beside the video* and *where the subtitle was* are the same directory |

### 🚨 THE ADVERSARIAL PASS — three agents, ~FIFTY findings, against 20 green checks and 20 killed mutants

⛔ **The mutation run said 20 of 20 killed. An adversary then aimed fifteen mutations at
the exact thing each check was named after and ALL FIFTEEN SURVIVED**, each proven to have
fired. One shape was behind most of them:

> ⭐ **`tree()` compared names and SIZES, and a retime is length-preserving** —
> `00:00:01,918` and `00:00:00,888` are the same byte count. So a dry run that rewrote
> every candidate in place, a REFUSED file mangled, and a library modified under `--out`
> were all invisible to checks written specifically to catch them. It carries a **content
> hash** now.

The rest, each recorded at its site: the Sintel fixture's **source and output were the
same path**, so several checks compared a file with itself and a mutant writing one byte
passed · `source_first_cue` was read **after** the write · `_observe` keyed rows by
**basename**, collapsing `Alpha/01.srt` and `Bravo/01.srt` into one row *in the scenario
built for cross-slot state* · an `assert X or True` · `derived_check` validated **one**
number because dedupe supersedes the other · a `for` over a mapping with **no length
check** · and the floor hand-enumerated which keys to compare, so any key added under
`one_folder` or `broadcast_cut` **was never compared at all**.

⭐ **Four claims in this project's own prose were false and are amended:** the two
containers are **not different muxers** (both `Lavf59.16.100`; `track_2.mkv` was made here
with ffmpeg) · the cut truth was **not** *"measured on the audio by two engines"* — it is
subsync's, measured **cue-vs-cue against a file byte-identical to this reference** · Sintel
reads `strong` from the **excess ladder** (3.57× against `locked`'s 4.0×), not from any
runtime cap · and `shincaps` is **not an independent capture**: 300 of its 303 cue starts
are exactly **33.233 s** from `nanakoraws`, so the pair tests offset-**invariance**, not
agreement between two recordings.

### ⭐ What it measures, on real media, for the first time

| | |
| --- | --- |
| ⭐ **a real broadcast cut is SOLVED** | `[NanakoRaws]` AT-X against the streaming video's own track: two segments, **first offset within 7 ms and second within 46 ms** of the truth, `D9` drops the one stranded cue, 303 → 302, and the file parses. ⚠ **The OFFSETS are the claim.** `Fit.gaps` returns `[(222.4, 336.34)]` — the aligner calls the crossing **undetermined across 113.9 s** — and `_boundary_time` returns a reference cue start, so 222.4 is a grid position, not a 0.4 s measurement |
| the instrument agrees with something else | end-to-end **−1.0295** (Netflix) and **−0.3230** (ABEMA) against **−1.0500** and **−0.2200** derived from §5's mask offsets. ⚠ §5's *"both engines agree"* hides a **0.177 s** spread; these are subsync's column, and that spread is why the tolerance is 0.25 |
| a self-extraction aligns at zero | Sintel: **0.0000**, 100% match, first cue unmoved |
| the wrong episode | refused on **both** paths — filtered by name on discovery, refused by the verdict when the user asserts the pair — and nothing on disk changes, **by content** |
| `--keep-all` + `--out` on real files | ✅ **the `HANDOFF.md` item owed to this step.** Two real releases of one episode: 3 distinct outputs, nothing superseded, trash empty, library untouched, and it **mirrors** — which needs two shows to be distinguishable from flattening at all |

### ✅ ONE REAL DEFECT FOUND — AND FIXED THE SAME DAY

**A bracketed language tag read `und`.** `sidecar.parse_path` read only DOT-separated
tokens, so `.ja[cc].srt`, `.en[cc].srt`, `.ja-jp[sdh].srt` and `.ja-jp.srt` — every form
`05-interface.md` §*Filename tags* names, and the ones ABEMA, Netflix and Amazon actually
write — resolved to `und`. **Two different languages then shared one slot and dedupe
trashed one of them.**

⭐ **Measured before it was reported, and again after it was fixed:**

| | |
| --- | --- |
| real corpus filenames reading `und` while carrying a resolvable code | **4,677 of 40,572 (11.53%)** → **8 (0.02%)** |
| what the remaining 8 are | shapes the guard refuses **on purpose** — `ja[no-sdh]`, `ja[cc][no furigana]`. ⛔ A filename is full of brackets that are not flags, and turning `[E27C3F25]` into English is worse than reading `und` |
| slots in the corpus that could exhibit the **loss** | 🚨 **ZERO, before and after** — it is Japanese-only, so no episode has both a `ja[cc]` and an `en[cc]` |

🚨 **AND THAT LAST ROW IS THE FINDING ABOUT THE METHOD.** The corpus **structurally cannot
contain** this defect, so no real-data sweep could ever have found it; it took the
benchmark constructing a bilingual library. ⭐ `07-test-plan.md`'s own rule, arriving from
the side nobody watches: *a fixture cannot show a failure only real data produces* has a
mirror image — **real data cannot show a failure it does not contain.**

⚠ **It was held as `xfail(strict=True)` for one session** on the ground that `sidecar` is
one of the four shapes hato pins and 3b froze them. ⭐ **Ruled: the freeze is on the SHAPE.**
`Sidecar`'s fields are unchanged; only values move, and they move toward what a written
spec line already required — that is a conformance defect, not a design change.

**Landed:** `sidecar._peel_brackets` and `sidecar._language_of`, `test_sidecar.py` +2
checks, **56/56 mutants** (six new). ⚠ Three pre-existing mutants **FAULTED** because the
fix moved their anchors — *"a fault reads as a kill from the exit code alone"* — and were
re-anchored. `_work/probe_3c0_2_bracket_lang.py` is the before/after measurement.

---

## Step 3d — GUI ✅ DONE 2026-09-10

**surfaces:** `ui` · **depends on:** 3c · **authority:** `05-interface.md`,
`01-scope.md` item 17, `07-test-plan.md`

⚠ **THIS STEP IS THIN IN THE SPEC, AND THAT IS THE FIRST THING TO NOTICE.** It is four
constraints — *tkinter*, *shells out to the CLI*, *DPI-aware geometry*, and the
`"confident"` substring — with **no ruled layout**, unlike the CLI, whose worked
example `05-interface.md` marks *RULED, do not redesign*. ⛔ **Do not invent a design
and write it up as ruled.** Bring Sonic a proposal first; that asymmetry is the reason.

⭐ **MEASURED ON THIS MACHINE 2026-09-09, so nobody re-derives it:**

| | |
| --- | --- |
| `tkinter` | **8.6**, present |
| `PIL.ImageGrab` | **present** — so a real window CAN be screenshotted and LOOKED at |
| `mss`, `pyautogui` | absent, and not needed |

🚨 **THE SCREENSHOT IS NOT OPTIONAL, AND THE LEDGER SAYS WHY TWICE.** A DPI-aware window
clipped its own button off the screen — **every assertion passed** and one image showed it
immediately; and a GUI painted a run containing refusals **green**, because
`"11 confident, 1 refused"` contains the word `confident`. ⭐ 3c paid the same
lesson again a third time: fifty green checks sat over a header running to column 100, a
`-0.00s` offset, and a `--verbose` line at 150 cells — all obvious on screen,
none visible to a check. **`$TSUBASA_CORPUS/_work/probe_3c_1_look_at_it.py` is the
shape that found them** — a real Japanese library under its original release names, driven
end to end, with a **column ruler printed above the output.** The GUI's version of that
ruler is an image.

⚠ **What cannot be checked here:** macOS UX (`07-test-plan.md`). GitHub Actions covers
build and test only.

### ⭐ THE NON-VISUAL HALF LANDED 2026-09-09 — the layout is still Sonic's

The step splits exactly where `07-test-plan.md` splits it (*"output painted right, then
**looked at**"*), and everything under the paint is built, because it is identical under
every candidate layout and it is where the failures actually live:

| Landed | What it is |
| --- | --- |
| `tsubasa/gui/run.py` | Spawns `python -m tsubasa --json`, reads NDJSON on a thread, hands rows back without blocking the event loop. ⛔ No tkinter in the file, so all of it is checkable without a display |
| `tsubasa/gui/scale.py` | Constraint 3. `Scale.px` / `.window` / `.fits` / `.pin`, and `make_process_dpi_aware()` |
| `tests/test_gui.py` | **The 37th suite**, registered in `tsubasa.config.json`. ⚠ It was 69 checks when only this half existed; **93 once the window landed** |
| `_work/probe_adj31_guimutants.py` | 57 mutants at this point; **79 / 0 survivors / 0 faults** once the window landed, 3 controls held |
| `_work/probe_3d_1_layouts.py` | The three candidate windows, drawn for real and captured **at 10 and 24 episodes**, with the capture harness's own checks |

⭐ **`run.counts` IS constraint 4, as code.** Every number a person reads at a glance is
computed from the `outcome` field, and the check feeds it *"11 confident, 1 refused"* —
`LEDGER.md` §Interface's exact string — beside a real refusal, so a reader that matched
the word would report a clean run and go red.

### 🚨 THE ADVERSARIAL PASS — two agents, 29 findings against 36 green checks

**And the worst of them were the `"confident"` defect REBUILT OUT OF CORRECT FIELDS.**
A failed write read `1 synced`; a **dry run** read `1 synced`; three videos with no
subtitle read *"everything here is already in sync"*; a cancelled run read `3 synced`;
and a repaired cut was counted twice, so ten files read as eleven on the one line a
person reads at a glance. Every individual number was right. Full record in
`LEDGER.md` §Interface — the four rules that came out of it are **partition the
categories**, **`CONFIDENT` is not `written`**, **quote the layer that can see what you
cannot**, and **a row nobody counts is a row that vanished**.

⚠ **Two lifecycle defects with nothing to do with counting:** `drain()` — whose docstring
says ⛔ NEVER BLOCKS — froze for **20.00 s**, because both pipes reaching EOF is not the
process exiting; and `wait(timeout=2)` was still spinning at fifteen seconds, because the
timeout went to `Thread.join` and nowhere else. **Every shipped check passed a timeout it
never reached.**

🚨 **`fits()` was optimistic by 88 px and `pin()` never called it**, so a window could be
pinned 995 px past the bottom of the desktop — unresizable, because `min == max`. And the
capture harness passed a window reading **"THIS IS SOMEBODY ELSE'S APPLICATION"**, because
its identity check sampled the two pixels every layout shares. Both in `LEDGER.md`.

### ⭐ WHAT THE MUTATION RUNS FOUND THAT READING COULD NOT — five checks that could not fail

| The check | Why it could not fail |
| --- | --- |
| the package is prepended to an existing `PYTHONPATH` | the fixture had **no** `PYTHONPATH`, so both branches produced one string |
| the summary is the **last** stderr line | the fixture was **one line** long |
| `fits()` counts the origin | the only failing case tripped the **height** term, so the width term was unguarded |
| `no_rows` accounts for faults | every faults fixture **had rows**, so the property was False either way |
| the run is collected only after the child is reaped | the double **died instantly**, so EOF and exit landed in one sweep |

⭐ **All five are one shape** — *a fixture whose value is the identity element of the
operation under test* — now in `LEDGER.md` §Harness beside the three older instances it
belongs with (*an ASCII fixture cannot test an encoding rule*, *`all()` over an empty
range is True*, *a ranking check rescued by its own tiebreaks*).

⚠ **And one mutant was a NO-OP, not a survivor:** putting `proc.wait()` back into
`_collect` changes nothing while the guard above it means `_collect` only runs after the
reaper has reaped. It took **both** substitutions to restore the historical defect.
*A survivor is a claim that needs its own proof, every time.*

### 🚨 A PART 1 DEFECT — the spec never says how the GUI is LAUNCHED

`01-scope.md` item 17 names it, `07-test-plan.md` covers it, and `10-deployment.md`
describes a PyInstaller `--onedir` bundle **and names no entry point for it.**
`python -m tsubasa.gui` is what is built, mirroring `python -m tsubasa`, and it is
recorded here rather than decided quietly because **4a has to resolve it deliberately**:
a Windows bundle wants a `gui_scripts` entry point, not a `console_scripts` one, or the
app opens with a console window attached for the life of the process — which is
`LEDGER.md`'s *every ffprobe call flashed a console window that stole focus*, made
permanent.

### ✅ THE LAYOUT IS RULED — 2026-09-10

Three mechanisms were built as real windows and captured at 10 and 24 episodes — console,
table, triage — and posted with a ⭐ lean on the table. **Sonic ruled the table:**

> *"Table is best. Cleanest and easiest to digest."*
> *"Auto-run on drop unless setting is toggled. Write without confirm unless reckless
> toggled in settings."*
> *"The window must look clean as it does, and the settings organized but the settings
> would likely be powerful for various features."*

⭐ **So the main window gains nothing.** It is the mockup — folder row, table, detail
pane, counts strip — and every option lives behind one button. A feature that wants a
control on that window needs a ruling, not a commit.

| Also landed | What it is |
| --- | --- |
| `tsubasa/gui/app.py` | The window. Table with refusals pinned at index 0 as they arrive, a detail pane, the partitioned counts strip, real OS drag-and-drop |
| `tsubasa/gui/settings.py` | Every option, in four groups. ⭐ **The panel is GENERATED from `SCHEMA`** — `doctrine/architecture`'s *inert control* defect is a settings panel waiting to happen, so the window does not know the name of a single option |
| `tsubasa/gui/__main__.py` | `python -m tsubasa.gui`. ⛔ DPI-aware **before** the first `Tk()` |
| `_work/probe_3d_2_look_at_the_app.py` | Drives the shipped window over a real 8-episode library and captures four states |

⭐ **`RECKLESS` is one group and it is the only thing that changes the write behaviour.**
Nothing in it is on by default, so the ordinary path never confirms; the moment one is
on, the app asks — because those are the options that change a file rather than adding
one. Today that is exactly one: **turning renaming off**, which writes the new timing
over the file the user already had.

### 🚨 SEVEN DEFECTS CAME FROM LOOKING AT THE REAL WINDOW, NOT FROM A CHECK

**Every one was green under the suite as it stood — 91 checks and 76 killed mutants at the
moment of discovery; 93 and 79 now.** This is the fourth time
this project has paid the same tuition, and the list is the point:

| On screen | Why no check could see it |
| --- | --- |
| the window **1089 px tall instead of 1647**, then **1647 on the next run with nothing changed** | ⛔ Non-determinism. `pin`'s `min == max` was the only thing holding the height and `_allow_resize` handed it straight back to the geometry manager. The capture harness said `CAPTURES OK` to **both** |
| the **counts strip starved to zero height** | A `middle` packed `expand=True` **before** the footer takes the whole cavity. Fixed structurally — header, footer, then the scroller that takes what is left — so it cannot recur at any window size |
| **`+0.00s` on the ERROR row** | A file with zero cues that was never measured, showing a confident-looking number. The CLI's own `-0.00s` defect at 3c, in a table |
| `✓ 4 would sync` beside `6 would sync` **in the same footer** | The chips partition; the headline totals. Both correct, together incoherent |
| **Browse and Sync swapped** from the approved mockup | `pack(side="right")` reverses creation order. The picture Sonic ruled on had Browse first |
| **`…[Multiple].s—`** | ttk clips at the column edge with no gap, so a filename and the next column's em-dash read as one token. Now fitted by **measuring** the font |
| a hollow **☆** mid-sentence and literal **`*would sync*`** in the settings panel | This project's own doctrine markers and markdown leaking into prose written for a person |

⭐ **The last one became a static check** rather than seven fixes — `ast` over `app.py`
and `settings.py` for markers in any non-docstring literal, plus a runtime twin over the
loaded schema. ⚠ **Both are needed and a mutation run proved it:** mutating a `why` in
memory *survived* the static check by construction.

---

## Step 3e — ✅ Absolute episode numbering — DONE 2026-09-10

**surfaces:** `logic` · **authority:** `05-interface.md`, `09-corpus-strategy.md`

⭐ **THE FIRST DEFECT FOUND BY POINTING THE FINISHED TOOL AT A REAL LIBRARY**, reported
by Sonic within minutes of the GUI opening. `[SubsPlease] Hell Mode S2 - 10` and
`ヘルモード…S02E22…ABEMA.ja[cc].srt` are the same episode and nothing was ever offered
for the video. Both names parsed correctly and the alias table already linked the titles
at **1.0**; only the number disagreed. **ABEMA and DMMTV write a per-season SEASON tag
with an ABSOLUTE episode number** — measured `E17 → ep 5`, `E18 → ep 6`, `E22 → ep 10`,
a constant −12 over a twelve-episode season 1.

Full reasoning in `LEDGER.md` §Logic. What landed:

| | |
| --- | --- |
| `discover.py` | The fallback, the disjointness trigger, the `speculative` marking |
| `api.py` | `Candidacy.speculative`, ONE builder for both callers, the identity filter |
| `pipeline.py` | The flag carried across the `measure()` seam |
| `dedupe.py` | ⛔ **A speculative loser is never superseded** |

⭐ **Three properties make it safe to ship**, and each is a check:

1. **It cannot change an answer that already exists.** It fires only where the ordinary
   lookup came back empty.
2. **Same season only.** `LEDGER-HOT.md`'s 305-false-pair guard is not reopened.
3. ⛔ **Nothing new is ever trashed.**

🚨 **TWO CORRECTIONS DURING THE BUILD, AND AN EXISTING CHECK MADE THE FIRST ONE.** The
trigger was originally *"the video was offered nothing"* — the **ordinary** state of a
partly-subtitled library — and `test_a_video_with_nothing_to_pair_is_unpaired_not_a_result`
went red. And two guards that looked load-bearing were **dead code**, found by their
mutants surviving, and were removed rather than covered.

### 🚨 THE FIRST VERSION FAILED ON A COMPLETE SEASON — fixed the same day

**Found by Sonic asking whether episodes-per-season would help.** Measuring the answer
showed the first fix worked only on his sparse folder: a **complete** absolute-numbered
season overlaps the per-season one (`S02E01–E24` against `S02E13–E36`), so twelve videos
paired by number with the **wrong** subtitle and twelve were offered nothing. Nothing was
written wrongly — `align()` refuses them — but the feature failed on the case it exists
for.

⭐ **The fix is a DERIVED OFFSET, and coverage is the signal — not a difference
histogram.** The histogram was proposed first and measured wrong: on that season the true
offset wins by **one vote** (24 against 23 for each neighbour), because two contiguous
integer runs overlap almost as well at ±1. Coverage needs no threshold: a single argmax,
non-zero, over at least two videos.

| | |
| --- | --- |
| `discover.episode_offset` | The primitive. Pure, and refuses ambiguity with `None` |
| `Candidates.set_offsets` / `for_video` | Offers **both** readings when a shift exists |
| `api.Scan._derive_offsets` | The grouping — ⛔ needs SERIES IDENTITY, because the video says `Hell Mode` and the subtitle says `ヘルモード` |

⛔ **A derived shift makes the BY-NUMBER pair speculative too.** The numbers are not
trustworthy for that group, so trashing the loser would destroy either a real subtitle
for another episode or the one the user has.

**Measured:** 24 mutants / 0 survivors, 3 controls held. ⭐ `vnbench` **unmoved** —
candidate recall 92.3% against a 92.3% baseline, settled-by-name 80.0% against 80.0% —
which is the right result: the fallback fires only on disjoint numbering, a shape the
benchmark corpus does not contain.

---

## Step 3c — ✅ CLI — DONE 2026-09-09

**surfaces:** `ui` · **depends on:** 3b, 3c-0 · **authority:** `05-interface.md`
§*The CLI output — RULED, do not redesign*

⚠ 🚨 `"11 confident, 1 refused"` contains the word "confident". ⚠ A DPI-aware window
scales its own geometry. ⚠ Assert the output, then **look** at it.

| | |
| --- | --- |
| **Built** | `tsubasa/cli.py` — `main`, `parse`, `render`, `as_json`, `Usage` · `tsubasa/__main__.py`, a launcher and nothing else so `python -m tsubasa` and the console script at 4a cannot differ |
| **Flags** | `--subs` · `--out` · `--no-recurse` · `--no-rename` · `--keep-all` · `--pair` (repeatable) · `--pairs` · `--force` · `--dry-run` · `--json` · `--verbose` · `--no-results`. ⛔ `--lang` is NOT built: `05-interface.md` rules it an **evolution** feature and only the FIELD is launch. ⛔ `--merge-lines` is Track F, never started |
| **Proved** | `tests/test_cli.py`, the **36th suite**, **50 checks** · `probe_adj30_climutants.py` — **45 mutants, 0 survivors, 4 controls held** |
| **Exit codes** | `0` decided and written (or would be) · `1` something REFUSED, ERRORED or failed to write · `2` the command cannot be run as typed. 🚨 A refusal is non-zero: a script piping this has to be able to tell |

### 🚨 THE DEFAULT WRITES, AND `--dry-run` OPTS OUT — a spec tension, resolved

`sync()` defaults to `write=False` (`doctrine/robustness`: a library call that forgets an
argument must not move a user's bytes) and the CLI defaults to writing. ⭐ **A CLI is a
different actor: the person typed the command and named the folder.** And
`05-interface.md` rules `--dry-run` as a MODE — *"every intended action printed, nothing
written, nothing trashed"* — which is not a flag a tool can offer if it already describes
the default; its ruled output block ends `23 synced` and `2 subtitles superseded → trash`.
⛔ The safety property is not the default, it is `03-permissions.md`: nothing this tool
does is unrecoverable. ⚠ **Named here because the spec states it only by implication.**

### ⭐ SIX DEFECTS CAME FROM LOOKING AT A REAL RUN, NOT FROM A CHECK

`LEDGER.md` §Interface says it twice — *"assert the output, then LOOK at it"* — and
`$TSUBASA_CORPUS/_work/probe_3c_1_look_at_it.py` is that instrument: a real Japanese
library, staged under its original release names, run through `main()` five times with a
column ruler above it.

| Seen | |
| --- | --- |
| The header ran to **column 100** on a real path | The ruled example is `~/Anime/Katainaka S2`; a real one is 62 cells before the counts start. Clipped from the LEFT now — a path's tail is its identifying end, the opposite of a filename |
| `-0.00s` on a re-run | A converged folder aligns at about `-1e-9` and `%+.2f` renders that as a small NEGATIVE shift, on the line that means nothing moved. ⛔ `x + 0.0 or 0.0` does **not** fix it: that catches an exact `-0.0` and `-1e-9` is truthy |
| `x → x` on an in-place retime | Noise on the one line whose job is *the user sees what happened to their folder* |
| *"1 cue … **were** dropped"*, said **twice** | The noun pluralised and the verb did not — and `apply` already puts a full sentence in `Result.notes`. The COUNT moved onto the evidence line, where `05-interface.md` rules it belongs, and the note explains |
| `…HEVC AAC).srtREFUSED` | `_pad` adds nothing when the text already fills the column, so the separator has to be its own |
| A `--verbose` line at **150 cells** | Past the edge of every terminal, so the part a bug report needs was the part that scrolled off. It folds now |

### 🚨 AND TWO WERE IN THE LIBRARY, VISIBLE ONLY FROM HERE

| | |
| --- | --- |
| ⛔ **`summary()` said `0 would sync` over a folder that was entirely already in sync** | *would sync* is the dry-run voice — *here is what I would do*. A run that measured nothing did not consider anything and decline it; it did not consider anything at all. A user reading the first goes looking for the pairs it rejected. Checked now in `test_pipeline.py`, where `summary()` lives |
| 🚨 **THREE layers each composed *"written under force"* independently** and the CLI printed all three in one block | Two are right to: `explicit.Decision.reason` states the DECISION and `apply` states that the bytes MOVED. The third said *"is written"* at PLAN time — a claim about the future, the shape already fixed once for `output_path` and found again next door for `superseded`. Removed |

### ⛔ `Result` GAINED ONE FIELD, AND ITS OWN CHECK CAUGHT THE OMISSION

The ruled output has an **episode column**, and the CLI was calling `naming.episode` to
fill it — a second answer to a question the run had already settled, with better evidence
(it had the whole folder and the scheme it inferred from it). ⭐ **Caught by the CLI
suite's own source check**, which refuses an import of any decision-making module from the
wrapper. `Result.episode` carries it now — *added, never renamed* — and
`test_json_carries_EVERY_field_Result_carries` reads `Result.__slots__`, so it went red
the moment the field landed and `--json` had not been updated.

### 🚨 THE MUTATION RUN — SEVEN SURVIVORS, AND ONE IS A TRAP THIS PROJECT ALREADY KNEW

| Found | |
| --- | --- |
| 🚨 **The width check computed its expectation with the code under test** | `LEDGER.md` trap 10, textbook. Both sides of *"the arrow lands in the same column"* were measured with `CLI._width`, so replacing it with `len` kept them agreeing — against the single most important layout property in the file. It measures with an **independent** width function now |
| ⚠ **The width fixture had no FULLWIDTH character at all** | Every character of `片田舎のおっさん` is East_Asian_Width `W`, so a mutant that dropped the `F` class survived a check named for counting cells. ⭐ Same shape as `LEDGER-HOT.md`'s *an ASCII fixture cannot test an encoding rule*, and the fix is the same: **explicit fullwidth literals**, never a format string |
| ⚠ **The settled check passed on the SUMMARY line**, which also says *already in sync* | So deleting the dedicated block entirely survived it |
| ⚠ Four more were **no-op mutants** | A match rate that rounds the same either way; a refusal branch that never calls `_evidence` at all (a real structural property, now asserted); a dry-run substitution that landed in the in-place branch; and an episode re-parse aimed at a source check that cannot see it |

---



## Step 3f — ✅ `embedded_subs()` — the embedded-track check hato needs — SHIPPED IN 0.1.3, 2026-09-17

**surfaces:** `logic` `harness` `delivery` · **depends on:** 1d, 3b, and 0.1.2 PUBLISHED
first · **authority:** `05-interface.md` §*For code built on tsubasa* · hato
`06-edge-cases.md` §6 and `03-permissions.md` §*The read rule*

hato's read rule opens `if has_embedded_text_track(video, lang): SKIP` — a video that
already carries a Japanese text track needs no fetch. tsubasa reads every video's tracks
(`container.read`, 1d) and exposes no public way to ask. **One public function, added and
never renamed.**

| | |
| --- | --- |
| **Build** | `tsubasa/embedded.py`: `embedded_subs(video, lang=None)` → `EmbeddedSubtitles` (`ok`, `reason`, `tracks`) of `EmbeddedSubtitle` (`index`, `lang`, `tag`, `codec`, `text`, `bitmap`, `forced`, `default`, `name`). A header-only read (`timing=False`) through the one accessor |
| **Rules** | ⛔ **Unreadable is not "none":** `ok=False` with the reader's reason, and `.tracks` RAISES — nobody can read *"no tracks"* off a file nobody opened. A readable video with no subtitle track is `ok=True`, `tracks=[]` · `lang=` resolves exactly as `unpaired(lang=)` does, and an unrecognised tag raises · ⭐ **text is an ALLOW-list:** an unrecognised codec is neither text nor bitmap, because a bitmap track called text makes hato skip a fetch the user needed, while the reverse costs one download · `forced` is reported, never filtered — hato's own rule decides (*"A forced sub is not a full sub"*) |
| 🚨 **Measured first** | `_work/probe_3f_1_language_parity.py`, one file through both readers (ffprobe from `media-kit/bin`): **a TrackEntry with no `Language` element read `""` natively and `eng` through ffmpeg** — `eng` is the Matroska default, so the native reader takes it. Explicit `und` reads `und` / `""` (both undetermined). ⚠ **ffmpeg IGNORES `LanguageBCP47`**: `ja-JP` beside a legacy `und` read `ja-JP` natively and `""` through ffmpeg — the native reader is right and is the one that reads Matroska. And **`S_DVBSUB` / `dvb_subtitle` were missing from `pipeline._BITMAP_CODECS`**, so a DVB track was labelled text. The vocabulary moves to `container/`, one owner, both readers' names |
| **Test** | `tests/test_embedded.py`, its own suite — synthetic Matroska through the real reader, both directions of every rule; plus the absent-`Language` default in `test_container.py` and DVB in `test_pipeline.py` |
| **Prove** | the suite + the full runner green · mutants: `lang` filter ignored · a bitmap codec called text · unreadable returns `[]` · a subtitle-less container reported unreadable · the `eng` default removed · `forced` dropped · container position replaced by subtitle position · then the installed wheel, outside a checkout, on real media |
| **Ship** | 0.1.3 through [[Development Doctrine/PYPI-PUBLISHING-DRAFT-2026-09-16]] §2.5–2.7. ⛔ **The tag waits for Sonic's go, and the NAME is his to veto before it** — once published it is a compatibility promise |
| 🚨 **The adversarial pass** | One agent, ~50 minutes, against 14 green checks and 16 killed mutants. **One HIGH, and it broke the function's central claim:** a Matroska file CUT OFF — a download in progress — or with a DAMAGED header read as *readable, with no (or fewer) subtitle tracks*: 582 of 588 truncations of the real Sintel file came back `ok=True, []`, and a cut at 2,000 bytes returned a Japanese track. Cause: `mkv._children` clamps an element that runs past its parent or the file and stops quietly, and `mkv.read` never recorded that the track list was cut, damaged or never reached. **Fixed at the reader:** a clamped, short-stopping or unknown-size track list, or NO track list, raises `ContainerError` — so the ladder falls back to ffmpeg as it does for any walk that cannot finish — and a file that ends before its own Segment does sets `ContainerInfo.incomplete`, whichever rung answered (ffprobe reads such a file with exit 0). ⚠ **And eight checks that could not fail**, each now a check that can: track numbers written 1, 2, 3 so `TrackNumber - 1` passed as the index; 3 of 12 bitmap names pinned; `japanese` the only bad tag; the ffmpeg rung's `forced`/`language` checked only where ffprobe existed (now against a RECORDED ffprobe output, `_work/probe_3f_4_record_ffprobe.py`, on every machine); a byte ceiling a full read never reached (now measured against a full read of the same file). Plus: empty `Language`/`FlagDefault` elements take their EBML defaults, `S_VOBSUB/ZLIB` is bitmap, a WebVTT METADATA stream is not a subtitle on the ffmpeg rung, a bytes path works, and a header read no longer seeks to the end of the file for the Cues. ⚠ **Not fixed, and said so:** `index` equals ffmpeg's stream index on ordinary files only — ffmpeg drops button/logo/control entries and entries with no type or codec (documented, not aligned). 🚨 **Round 2 — the adversary's own reproductions re-run against the fix:** 2,400 of 2,400 truncations `ok=False`, and the defect found one rung down — ffprobe reads several damaged files as exit 0 with NO streams, so a file with no readable track of any kind is now `ok=False` too |
| **hato** | ⚠ **hato's spec was being edited by a concurrent session while this was built** (its read rule already called *"`track_reader(video)` — T4, tsubasa's public reader"*, name unknown), so nothing was edited from here at the time. ⭐ **Sonic then renamed the function to `embedded_subs` (2026-09-17), and by then hato had BUILT against the old name** — `hato/doctor.py` and `tests/test_doctor.py` both used it. That session had been idle nine hours, so the rename was carried into hato's four files as well and its doctor suite re-run: **28 checks, green.** The call it needs: `subs = tsubasa.embedded_subs(video)` → `if not subs.ok:` (its rule has no branch for an unreadable video yet) → `tracks = subs.tracks` → `has_text_track` is `any(t.text and not t.forced and t.lang == "ja" for t in tracks)` — forced excluded by hato's own `.ja.forced.srt` rule — and `not tracks` is its no-track skip. ⛔ `if not subs:` raises, by design. ⚠ **Two traps the adversary found in hato's use, not in tsubasa:** the no-track skip must use the UNFILTERED call — filtered by `lang="ja"`, *English only* and *none* both come back empty, and every video without Japanese would be skipped; and a Japanese text track that is not a full subtitle but is not flagged forced either (`name="OP/ED Kanji Karaoke"`) passes `text and not forced` — the name is on the track for hato to judge |

---

## Step 4a — ✅ Release — PyPI, not frozen binaries

**surfaces:** `delivery` · **authority:** `10-deployment.md`

⚠ **What shipped differs from this step's original plan, and the plan is kept honest here
rather than silently rewritten.** It asked for PyInstaller binaries on GitHub Releases; the
release became a **pip package**, `tsubasa-sync` on PyPI, published by a `v*` tag through
Trusted Publishing. 0.1.0 was yanked (`sync()` on a folder raised `ConfigError` for every
installed copy); 0.1.1 and 0.1.2 followed. `10-deployment.md` §*Proving a release* claim 3,
*"runs on a clean machine"*, **translates to "the installed package runs outside any
checkout"** — dropping it instead of translating it is what shipped 0.1.0 broken.

⭐ **The process and every pitfall:** [[Development Doctrine/PYPI-PUBLISHING-DRAFT-2026-09-16]].
The steps for a given version: `RELEASE-0.1.2-NEXT.md`. ffmpeg is found on PATH or through `$TSUBASA_FFMPEG` — ⏸ the
`tsubasa setup --ffmpeg` downloader was never built, and the refusal stopped naming it at
0.1.4. It is needed only for audio (VAD) and for containers the native reader cannot read. ⚠ **Read `doctrine/release` first. Pipe nothing
inside the block.**

## Step 3g — ⏳ `tsubasa setup --ffmpeg` — the installer, ruled 2026-09-17

**surfaces:** `delivery` `logic` `harness` · **authority:** `10-deployment.md`
§*Acquiring ffmpeg* (the design is already written there) · **depends on:** nothing

⛔ **Sonic ruled it, asked for the standalone:** *"No to bundle ffmpeg, just have an
installer for it if you can."* So the zip stays ~40–90 MB and a user who needs
ffmpeg — an MP4, or the VAD path later — runs one command once. ⭐ **Downloading is
not redistributing:** we take on none of ffmpeg's licence obligations by fetching a
stock build, which bundling would have brought with it.

| | |
| --- | --- |
| **Build** | `tsubasa setup --ffmpeg` in `cli.py`: fetch a pinned build for this platform, verify a **pinned sha256**, extract ONLY `ffmpeg` and `ffprobe` into the cache directory, `chmod +x` on POSIX. Idempotent: already installed and matching the hash → say so, exit 0 |
| 🚨 **The wiring gap it must close FIRST** | **`find()`'s cache rung is dead today.** It looks in `<cache>/`, `<cache>/ffmpeg/` and `<cache>/bin/` — but only when a caller passes `cache_dir`, and **nothing in the product does**: `pipeline._default_reader` and `embedded_subs` both call `container.read(path, …)` without one (measured 2026-09-17). Installing into the cache directory would therefore change nothing. `find()` must default `cache_dir` to `paths.cache_root()`, with a check that the rung is reachable from a real `sync()` |
| ⛔ **Never during a run** | `10-deployment.md` rule. A tool that downloads a binary mid-run behaves differently on its second use than its first. The library never downloads and never prompts |
| 🚨 **Verify before it becomes findable** | Download to a temp file, hash it, and only then move it into place. A half-written `ffmpeg.exe` in the cache directory is a file `find()` will hand to `subprocess` — the resolver cannot tell a partial download from a tool |
| ⚠ **A pinned URL rots** | Vendors rotate "latest" links; pin a VERSIONED release URL and its hash, per platform (Windows zip, macOS zip, Linux tar.xz). When it 404s, fail with the same sentence the refusal uses — *put ffmpeg on PATH, or set `TSUBASA_FFMPEG`* — never with a traceback |
| ⚠ **The suite makes no network calls** | Stub the fetch; assert the hash check REFUSES a corrupted download (flip a byte) and that a refusal leaves nothing behind. One opt-in live check, excluded from the default run — hato's `07-test-plan.md` has the shape |
| **Then** | Put the command back in the refusal sentence (`container/ffmpeg.py::missing_reason`) — it named this command until 0.1.4, when it was removed **because the command did not exist** (`LEDGER.md` §Interface). `test_ffmpeg_absence_refuses_with_a_sentence_the_user_can_act_on` checks every backticked `tsubasa <command>` against `cli.USAGE`, so it will pass the moment the command is real |
| **Prove** | `tsubasa setup --ffmpeg` on a machine with no ffmpeg → an MP4 that was refused now syncs, in the same shell, with nothing else changed |

## Step 4c — ✅ The standalone app — a Windows zip with no Python in it — BUILT 2026-09-17

**surfaces:** `delivery` `ui` · **depends on:** 4a · **authority:**
`10-deployment.md` §*Freezing*, and ⭐ **`STANDALONE-BUILD-SCOPE.md`, which is the
whole step** — written to be read by an agent with no other context.

⛔ **Ruled by Sonic 2026-09-17: WINDOWS ONLY for now, NO code signing, and the zip
rides the SAME `v*` tag as the PyPI release.** The barrier this removes is Python
itself — measured, the pip install pulls numpy automatically and costs 75 MB, so the
dependency was never the problem. ⛔ **ffmpeg is not bundled**; Step 3g installs it.

⚠ **The other two platforms are written down, not queued** (`STANDALONE-BUILD-SCOPE.md`
§8): **Linux is a wrapper** — a venv plus a `.desktop` file, because a Linux user
already has Python, and the one thing freezing would fix is the separate `python3-tk`
package. **macOS is ⏸ HALTED**: unsigned, a downloaded app is blocked by Gatekeeper and
CI cannot reproduce that, so it would ship having been opened by nobody. Its full flow
is recorded for whoever resumes it.

⭐ **Most of it already exists:** the PyInstaller hook ships inside the package
(`tsubasa/__pyinstaller/`), CI's `frozen` job proves a frozen build keeps its data
on ubuntu, and `gui/run.py::cli_argv()` already has a frozen branch. 🚨 **That
branch has never run, and it decides the build:** a frozen GUI looks for
`tsubasa.exe` BESIDE itself, so both executables must land in one folder.

### ✅ BUILT 2026-09-17 — what landed, and the numbers

| | |
| --- | --- |
| **The zip** | **29.0 MB** — well under `10-deployment.md`'s 40–90 MB estimate. `--onedir`, `tsubasa.exe` (console) + `tsubasa-gui.exe` (windowed) + `_internal/` + `LICENSE` + `THIRD_PARTY_LICENSES.md` + `README-FIRST.txt` |
| **Cold start** | **0.30–0.32 s** to a printed `--help`, measured in the smoke test rather than estimated |
| **`self_check()` inside the frozen app** | `ok`, **aliases 221258/221258, vocabulary 176/176** — the shipped hook needed no `--add-data` |
| **The tooling, all clone-only** | `packaging/tsubasa.spec` (two `Analysis`, one `COLLECT`) · `entry_cli.py` · `entry_gui.py` · `package_standalone.py` (zip + `SHA256SUMS` + the licences) · `smoke_standalone.py` (drives the artefact) · `_work/release/build_standalone.sh` (the local driver) |
| **CI** | ✅ **GREEN on `6c6edef`, 16/16 jobs**, including a new `standalone` job in **`ci.yml`** that freezes, packages, extracts and drives the zip on `windows-latest` **on every push** — ⛔ because `release.yml` fires only on a tag, so without it the frozen build would first run at the one moment being wrong is most expensive. `release.yml` gains its own `standalone`, `needs: build`, **freezing the very wheel the `build` job made** — which is what makes *one version number* true rather than merely intended |
| **The release DAG** | `build` → `standalone` → `publish` → `attach`. ⛔ `publish` **needs** `standalone`, so a broken zip stops the PyPI upload (the safe direction — an unpublished version burns nothing). `attach` runs last, so nothing public exists until both halves passed. **No `--clobber`**: a released artefact is immutable, because PyInstaller is not reproducible and a re-run would replace bytes somebody already checksummed. `gh release upload`, not a third-party action, so §4 step 5's Node-20 runtime trap cannot apply to it — ⚠ though it still applies to the four JS actions the workflow uses, and none of their `runs.using` is recorded anywhere. Open, and named |

⭐ **TRAP 1 IS CLOSED, WITH THE WINDOW'S OWN EVIDENCE.** The frozen GUI was
launched against a disposable library with `TSUBASA_CACHE` redirected, **Sync was
pressed by mouse**, and it wrote `[SubsPlease] Yomi no Tsugai - 18 (1080p)
[DD1CA4BC].ja.cc.srt` — `✓ 1 synced`, `CONFIDENT`, `-0.32s`, `93% match · locked`,
Japanese rendering clean in the rows. ⚠ **And a control run**, same launch without
the click, wrote nothing — so the button is what did it.

### 🚨 A CLAIM THIS STEP MADE AND MEASUREMENT DISPROVED — `MERGE` does nothing

⛔ **This section first said the 29 MB was `MERGE`'s doing. It is not.** An
adversary rebuilt the identical spec with only the `MERGE(...)` call removed:
**30,369,361 bytes vs 30,368,860, 1262 files either way.** The dedup is done by
the **single `COLLECT`**, which keys on `dest_name`; `MERGE` contributes nothing
here, because it processes only `analysis.binaries` and `analysis.datas` —
`analysis.pure` is untouched, and the `DEPENDENCY` entries it produces land in
`analysis.dependencies`, which this spec never passes to either `EXE`.

⚠ **So the thing it was credited with is still happening:** both PYZ archives
carry the same 572 shared modules (numpy 141, guessit 74, rebulk 36, babelfish
15), ~3.6 MB duplicated on disk — which the zip's compression largely absorbs.
⛔ **And wiring `dependencies` up the documented way would make each executable
gain onefile semantics**, unpacking on every launch, which `10-deployment.md`
ruled against. The call was removed rather than fixed.

⭐ The general lesson: **a number being good is not evidence that the thing you
credit for it did anything.** The control was one rebuild.

### 🚨 Four things the build found, and two were defects in checks written this session

1. ⭐ **A check that could not fail, caught by its own control.** A cross-script
   pair (`Yomi no Tsugai` / `黄泉のツガイ`) was about to become the CI-runnable
   proof that the alias table shipped — **and it still paired with the table
   deleted from the bundle**, because candidates are indexed on (season,
   episode) and the note about a waiting subtitle says nothing about names.
   ⭐ Replaced with the one that does work: **take the table away from the built
   bundle and require `--version` to say `NOT ok` and exit 1.**
2. 🚨 **`kept = before - after` is a set difference over NAMES**, so a smoke
   check written to prove an unpaired episode was not written over could never
   have seen it retimed in place — same byte count, same name. Now asserted by
   content hash. `LEDGER-HOT.md` trap 0d, found in this session's own work.
3. ⚠ **A whole build holds `loaded` and `declared` equal**, so the `--version`
   counts check was blind to a line printing one of them twice. The broken
   build is the only state where they differ, and the check now drives it.
4. ⚠ **`GetWindowRect` and a screen capture disagreed** because the driving
   script was DPI-unaware while the app calls `make_process_dpi_aware`: it
   answered `40,40 1071x694` for a window really at `100,100 2678x1735`. A
   confident number about the wrong thing, and a click would have landed
   somewhere else entirely.

### 🚨 THE ADVERSARIAL PASS — three agents, 40 findings, THREE HIGH

Split by surface (`--version` · the frozen build and trap 1 · packaging and
release), against **~30 green checks and 19 killed mutants**. ⭐ **Every one of
the three HIGHs was invisible from inside the work**, and two were in the
product rather than in the checks:

| | Finding |
| --- | --- |
| **HIGH** | 🚨 **The Sync button was a SILENT NO-OP and then wedged the app for ever.** With `tsubasa.exe` gone, `Popen` raised out of an unguarded `start()`, `self.runner` had already been assigned so `running` stayed True permanently, and `console=False` means `sys.stderr` is None so Tk printed the traceback nowhere. **Putting the file back did not help** — only killing the app did. Every check had driven trap 1 POSITIVELY |
| **HIGH** | 🚨 **The packager shipped a build its own instrument had just failed.** It read the version off `--version`'s stdout and ignored the return code: a bundle with no alias table produced a correctly-named, correctly-checksummed 29 MB zip and exit 0. Only the workflow's step ORDER kept it off a release page |
| **HIGH** | 🚨 **The ASCII check went RED for a correct build under a Japanese path** — the check written to protect Japanese users. The `PROBLEM:` sentences embed the DATA FILE's path, not just the data directory, and only the latter was stripped |
| **MEDIUM** | **A count is not a table**: every key reversed — count and header untouched — and all 18 smoke checks stayed green over a table where nothing resolves. ⛔ **The second unfalsifiable data check in one day**; see below |
| **MEDIUM** | **The zip was never opened.** Everything drove the output FOLDER, and `tsubasa-gui.exe` was never executed at all |
| **MEDIUM** | `MERGE` does nothing (below) · a truncated GPL passed the licence check · `THIRD_PARTY_LICENSES` had the needle `u""` · a released artefact was mutable under `--clobber` · the release DAG let PyPI and the zip diverge · the smoke test **crashed on the exact defect it exists to detect** |

⭐ **All fixed, each with a check that would have caught it, and the gaps are
now 37 permanent mutants — `37/37 killed`, restored byte-identical.**

⛔ **Not done, and it is the acceptance test:** §4 step 4 — **a Windows machine or
account with NO Python**. Everything mechanical is closed; that one needs a
person, and it is the only test that can fail for the reason the deliverable
exists.

## Step 4b — Rust ⏸

Unjustified: B1 runs at 49 ms/pair in numpy, measured. Revisit only if B5 misses its target on the
reference laptop after 1d.

---

## Order by value per hour

1. ~~**A2-fix + A4-fix**~~ ✅ done (the largest single accuracy gain in the pack)
2. ~~**B1 + oracle suite**~~ ✅ done (re-bases Track B on measured ground)
3. ~~**1d**~~ ✅ **done 2026-09-08** — measured 0.087 s/file, so 24 episodes ≈ **2.1 s**, no ffmpeg
4. ~~**0c**~~ ✅ **done 2026-09-08** — key rebuilt, VAD set + a real `.mkv` staged. **Next: run Probe G** as a
   measurement only (a day). ⚠ Probe G is the *gate*; **A7 the build waits for step 6**
5. A2c decoration vocabulary → A3b kana bridge (a day each)
6. A5/A5b/A6 — discovery, **the benchmark**, cluster probing
7. ~~**A7**~~ ✅ **done 2026-09-08** — the alias table. settled-by-name **49.7% → 69.1%**, +19.4 points
8. B6 (the VAD constants — the first step that needs the stronger machine)
9. everything else in graph order
