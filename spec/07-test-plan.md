---
type: spec
title: tsubasa — Test Plan
desc: The corpus split (done), where ground truth comes from for pairing, alignment and VAD, the suites and what each structurally cannot cover, the oracle rule, and the three environment answers. Probes moved to 08-probes.md.
date: 2026-09-08
---

# 07 — Test Plan

> **The cost of this project is not the code. It is the evidence.** Every threshold sits in
> a measured empty band, and every speedup is admissible only because a suite re-ran.

---

## ⛔ Where the corpus lives — a standing rule

`C:\Users\Michael\Documents\InfiniteVoid\WorldDominationLite\tsubasa-corpus\` — never
inside TheForge (`LEDGER-HOT.md`). The Desktop Yomi folder and `subsync/SubtitleMegaTest`
are *outside* the corpus and the suite must never reference them directly; what a test
needs is copied into `video-derived/` or already lives in `subsync/tests/fixtures/`.

## The corpus split — done

60 / 20 / 20 by **show**, hashed on a canonical split key that folds ordinals and release
tags so one show cannot land in two slices across `naming/` and `video-naming/`. The
sealed slice is refused by `tsubasa.dev.corpus.shows()` unless `TSUBASA_UNSEAL` carries
the token. **Opened once, at the end.** Every number in this pack excludes it.

---

## Ground truth — three kinds, three prices

### Pairing truth — free, and now a benchmark

| Source | Rows | What it labels |
| --- | --- | --- |
| `naming/catalog.jsonl` | 201,785 non-sealed filenames | show (jimaku entry) — the title gate's truth |
| `naming/titles.jsonl` | 12,259 entries | romaji · Japanese · English — the alias answer key (never ships) |
| `video-naming/` × jimaku overlap | **345 real video↔subtitle pairs, 116-show pool** | the pairing benchmark (`probe_opp5`); label noise: `Tensei Kizoku, Kantei Skill…`, `Still to Watch/` |
| `_work/probe_vn14_e2e.json` | 435 aligned pairs | timing-confirmed same-episode pairs |

### Alignment truth — the oracle

**`subsync/tests/corpus.py` — 29 pairs with measured truth**, 10 subtitle-vs-subtitle and
19 subtitle-vs-video-track, five of them real broadcast cuts and one a Netflix eyecatch
trim, plus 5 `MUST_REFUSE` pairs. Derived two independent ways that agree. Runs
media-free from `subsync/tests/fixtures/vidref/` (384 KB). ⭐ **This is the acceptance
suite for Track B** (`12-alignment.md` §8): offsets within the truth tolerance, every cue
outside a declared quiet gap within `MR_TOL`, refusals refused.

`subssuite/` adds the BLEACH AT-X cuts (−10.1 s @1:18, −9.8 s @3:25) and 364
cross-platform pairs for the verdict band.

### VAD truth — the expensive one, and it now exists

✅ **`video-derived/yomi18/` — STAGED 2026-09-08.** The video's audio (`audio16k.opus`),
its own track (`track_2.ass`, 323 cues — the same count the container reader reads from the
real MKV), two uncut streaming subtitles, two cut broadcast subtitles and a wrong-episode
subtitle, with the measured outcomes from `12-alignment.md` §5 written into the folder's own
`README.md`. ⭐ **THREE of the six must be REFUSED — on the MASK path**, which is what the
set is really for. ⚠ *"Four"* stood here until 3c-0 counted them; the README said it too,
and `RUNBOOK.md` 3c-0's Prove line inherited it as *"the four `MUST_REFUSE` pairs"* —
which compounded the error, since `MUST_REFUSE` is a defined identifier in
`subsync/tests/corpus.py` naming **five** oracle pairs, none of them a yomi18 file.
⛔ **And the refusal is a MASK-path statement.** On the cue-vs-cue path the two AT-X cut
files are **solved**, not refused, because §5's *"the break is invisible on a speech mask"*
does not apply — `test_e2e.py` measures both offsets within 7 ms and 46 ms of truth. Only
the wrong episode is refused on both paths. Plus Probe F's Naruto and Sintel
material. **Mask-path constants are fitted on this set and its negative controls before
any mask verdict ships.**

---

## The suites, and what each STRUCTURALLY cannot cover

| Suite | Covers | ⛔ Structurally cannot cover | State |
| --- | --- | --- | --- |
| wiring · runner · corpus-split | config, registration, the seal | anything about the product | ✅ green |
| encoding · parsing · rewrite · corpus-roundtrip | every format in, byte-exact out, codec preserved | whether the timing is right | ✅ green |
| cache | head/tail hashing, miss-not-wrong | — | ✅ green |
| normalize · naming · series · scheme | Track A units | whether the pair actually matches | ✅ green; **A2-fix and A4-fix landed 2026-09-08** |
| bitmap | PGS/VobSub timing | OCR (never) | ✅ green; 2 vn17 controls to inspect |
| **container** | Cues-indexed / block-walk / ffmpeg readers agree to 1 ms; the completeness guard; chapters; duration vs ffprobe | a **partial** Cues index in the wild — no real specimen exists, both muxers seen index every block | ✅ **green 2026-09-08**, 55 checks, 23/23 mutants |
| ⭐ **titlegate** | an episode **MARKER** surviving in the series key, **and** its number being the one the parser called the episode — the defect `parsergate` cannot see, because it scores the UNION and the episode comes out right | a title that is wrong without carrying a marker; and ⛔ same-show key AGREEMENT, which was measured and rejected — 21.6% of entries carry two scripts, so it would measure the corpus | ✅ **green 2026-09-08**, 28 checks, **12/12 mutants**. ⭐ Found **6.45% → 0.15%** on its first run, and moved the release number 69.1% → 80.0% |
| **decoration** | the 176 learned tokens; that a real title is never eaten | film pollution beyond the catalogue's shape | ✅ **green 2026-09-08**, 33 checks, 13/13 mutants |
| **kana** | the kana table, the shared fold, the 0.85 empty band | kanji titles — `fugashi`+UniDic is the ceiling and is a separate decision | ✅ **green 2026-09-08**, 40 checks, 14/14 mutants |
| **layouts** | all eight directory shapes, on real temp trees | a ninth shape — which is the point: none is enumerated in the code | ✅ **green 2026-09-08**, 19 checks |
| **pairing** | the (season, episode) index; 500×1500 is not a nested loop; duration | whether the pair is actually right — that is timing's | ✅ **green 2026-09-08**, 13 checks |
| **arbitration** | cluster coherence against the probe's own 44 correct / 60 wrong | a cluster shape the corpus does not contain | ✅ **green 2026-09-08**, 20 checks, reproduces 104/104 |
| ⭐ **vn_bench** | **350 alignment-confirmed pairs; fan-out before and after identity** | pairs the corpus does not contain; a user-sized library (this is catalogue scale, the adversarial case) | ✅ **green 2026-09-08**, 8 checks — ⭐ **candidate recall 92.3%**, the release number (`D8`) |
| ⭐ **alias** | ⛔ mostly the **REFUSAL**, not the coverage: the two-sided intersection rule, the containment guard, the fail-open, and that the table can only ever turn a verdict INTO `same` | a wrong row IN Wikidata — the table inherits its source's mistakes, and no local check can see one. Coverage lives in `alias --grade` | ✅ **green 2026-09-08**, 60 checks, **27/27 mutants** — 19 of them, and 19 more checks, added after an adversarial pass returned **seven** findings against the green suite |
| ⭐ **alignment_oracle** | the 29 pairs, cue-level, the undetermined span | material unlike the corpus | ✅ **green 2026-09-08**, 10 checks |
| **negative_controls** | reversed, jittered, different show, sequel, deleted opening, thin input, and the break-size guard | — | ✅ **green 2026-09-08**, 11 checks |
| nsplit · timeline | uncapped cuts; the walk | a real 3+-break specimen (derive it) | ⚠ the mechanism landed with B1; **a synthetic 3-break file is still owed** |
| **vad** *(new)* | the Yomi set + Probe F material | languages and genres not in it | B6 |
| perf | 29 pairs < 2 s; 24 episodes < 5 s | other hardware — re-baseline on move | B5 |
| ⭐ **verdict** | the three outcomes and the ORDER they are decided in (cue count → holds-throughout → band); the one-directional coherence lift; that a refusal carries no confidence word; that a speech-mask verdict RAISES until B6 fits its band | ⛔ whether the band's numbers are *right* — that is `LEDGER.md` §Logic's 364 measured pairs, not this suite; and the mask band, which does not exist yet | ✅ **green 2026-09-09**, 63 checks, **39/39 mutants** |
| ⭐ **sidecar** | the language reader hato imports, against **two defects live in shipped software and failing in opposite directions**; NAME_MAX in bytes; the Windows rules; a real-data pass over 24,315 corpus filenames; ⭐ **the bracketed and hyphenated tag forms** (`[cc]`, `[sdh]`, `ja-jp`) **and the guard that refuses to read `[E27C3F25]` as a language** | ⛔ a three-letter-only language (no ISO 639-1 code) — it reads as `und`, which costs a duplicate and never a wrong file; a filename convention the corpus does not contain; and 🚨 **a defect the corpus's own composition makes impossible** — `.ja[cc].srt` vs `.en[cc].srt` sharing one `und` slot was invisible to 78 green checks **and** to a 24,315-name real-data pass, because this corpus is Japanese-only. It took RUNBOOK 3c-0 constructing a bilingual library | ✅ **green 2026-09-09**, 80 checks, **56/56 mutants** |
| ⭐ **dedupe** | that deletion is **structurally impossible** (an AST walk over the module) — 🚨 **and read that claim narrowly: it answers *does this module delete*, never *can this module cause a deletion*.** An adversarial pass destroyed a user's subtitle through `os.replace` inside `formats.write_file`, one module away, while this check stayed green (`LEDGER.md`: *the structural proof is true and the property is false*). The behaviour is now guarded by checks that hash the tree; that rule 1 is a GATE not a sort key; the trash's dry-run default, its move-not-remove fallback and its no-overwrite rule; `--keep-all` | ⛔ **whether the ranking picks the file a person would have picked** — it is a robustness backstop, and no corpus labels the "better" of two correct subtitles; also the real `send2trash` behaviour, which is driven through an injected sender because the package is absent here | ✅ **green 2026-09-09**, 30 checks, **34/34 mutants** |
| ⭐ **apply** | the WRITE path: a zero shift is byte-identical on every writable format **and on real corpus files** (the cheapest proof the field whitelist holds); cue-block REMOVAL, with each format's own span rule; ⭐ `D9`'s arithmetic against §5's measured cut; dry-run by default; write-before-trash; the written-over guard; the original codec on a real Shift-JIS file | ⛔ **player rendering** — nothing here opens a video. Also the mixed-timestamp-shape defect, which needs 400+ real files to appear at all and belongs to `corpus-roundtrip` | ✅ **green 2026-09-09**, 50 checks, **36/36 mutants** |
| ⭐ **api** | `scan()` **opens nothing inside the tree it was given** — asserted by making `open()` raise there, with its own control proving the guard can fire; junk ignored SILENTLY; the two-folder rule including **nested** roots; NCOP/NCED on both sides; the rank's four keys each pinned by a fixture where every LOWER key points the other way; `Result`'s five constructor invariants | ⛔ **whether the RANKING is any good** — it orders hypotheses and timing decides, so no fixture here can be wrong about a pair; and anything needing a real container, which is `pipeline`'s | ✅ **green 2026-09-09**, 57 checks, part of **95/95 mutants** |
| ⭐ **pipeline** | `sync()` end to end on a real synthetic Matroska: the tuple path **through `explicit_pairs()`**, proved by feeding it the five refusals A11 exists for and requiring each one back; **nothing written unless `write=True`**, proved by hashing every byte in the tree; `output_path` and `superseded` set only when something actually MOVED; the reference choice; the runtime gate BEFORE the aligner; `--force`; `vad=True`. ⭐ **And the CROSS-SLOT rules** — a two-show library keeps every subtitle, one file is never two videos' answer, a slot that wrote nothing trashes nothing, `--out` mirrors, a failed write is not a dry run | ⛔ **a REAL user library** — every video here is synthetic and every subtitle generated, so the timing is exact where real pairs jitter. `vn_bench` is catalogue scale but measures NAMES, not `sync()`. ⭐ **Nothing yet measures the product end to end on real media** — that gap is why the two-folder output-directory defect survived to a dry run, and why ten more waited for an adversary | ✅ **green 2026-09-09**, 66 checks, part of **95/95 mutants** |

> 🚨 **AND MUTATION TESTING COULD NOT HAVE FOUND THE WORST OF THEM.** The second
> adversarial pass ran against `pipeline` at 49 green checks and **77 killed mutants** and
> returned ten findings, two of which destroy user data on default flags. Its own closing
> note is the finding about the method: *"none of these is a wrong constant or an inverted
> comparison. They are missing checks, cross-slot state, and reports composed from the
> plan instead of from what happened — the classes mutation testing over this suite cannot
> reach."*
>
> ⭐ **Layer 1 proves a check can fail. It says nothing about a check that was never
> written, and nothing at all about a defect that lives BETWEEN two correct modules.**
> Budget the adversarial pass by the size of the new *surface*, and review the SEAMS
> yourself — that is where every 3b finding was.

| ⭐ **e2e** *(3c-0)* | **the PRODUCT, end to end, on real media** — nine real library shapes in a temp directory, `scan()` → `sync(write=True)`, asserted on the resulting TREE **by content hash**. A real broadcast cut SOLVED to within 7 ms and 46 ms of measured truth with `D9` firing; a self-extraction at exactly 0.000; the wrong episode refused on both paths with nothing changed on disk; a two-show bare-episode library keeping every source; `--out` leaving the library alone; `--keep-all` on two real releases superseding nothing; and the measured offset agreeing with one derived from §5's mask numbers | ⛔ **one episode of one show plus Sintel** — a SHAPE benchmark, not a coverage one; `vn_bench` is the population number · ⛔ **the runtime gate's real work**, because `track_2.mkv` is subtitle-only so its duration echoes its own track and every yomi pair sits at ratio 0.93–1.00 · the mask path (B6) · whether a player renders anything · ⛔ **two independent witnesses to the cut** — `shincaps` is `nanakoraws` shifted by a constant 33.233 s, so the pair tests offset-INVARIANCE | ✅ **green 2026-09-09**, 22 checks, **40/40 mutants**, no skips. 🚨 Three adversaries returned ~**50** findings against its first version, and it **found a real defect on its first run** — see below |

> 🚨 **AND ITS OWN MUTATION RUN SAID 20 OF 20 KILLED WHILE FIFTEEN ADVERSARIAL MUTATIONS
> SURVIVED**, each proven to have fired. ⭐ One shape did most of it: **`tree()` compared
> names and SIZES, and a retime is length-preserving** — `00:00:01,918` and `00:00:00,888`
> are the same byte count — so a dry run that rewrote every candidate in place, a REFUSED
> file that was mangled, and a library modified under `--out` were all invisible to checks
> written specifically to catch them.
>
> ⭐ **Four claims in this project's own prose were false and are amended**: the two
> containers are not different **muxers** (both `Lavf59.16.100`) · the cut truth was not
> *"measured on the audio by two engines"* but by **subsync, cue-vs-cue against a file
> byte-identical to the reference** · Sintel reads `strong` from the **excess ladder**, not
> from a runtime cap · and `shincaps` is not an independent capture. **The full record is
> `RUNBOOK.md` §3c-0.**
| gui | output painted right, then **looked at** | macOS UX · **anything that is a claim about what a person SEES** | 3d |

⭐ **THAT ROW SPLITS IN TWO, AND 3d IS BUILT ALONG THE SPLIT.** `tests/test_gui.py`
(36 checks, 32 mutants / 0 survivors) covers the half with no pixels in it — the
subprocess, the decoding, the NDJSON parse, the counts and the DPI arithmetic — and
imports no tkinter, so it runs without a display. The window itself is answered by a
capture that is **looked at**: `_work/probe_3d_1_layouts.py`. ⛔ **A check can assert the
window is 2646×1647 and can never assert the button is inside it.** The first capture run
found three defects no assertion reached; `LEDGER.md` §Interface has them.

### Non-negotiable guards

1. Every harness row carries a marker identifying it as test data
2. Teardown is verified, not assumed — and the suite never writes inside the corpus
3. ⛔ No assertion hardcodes a production count; baselines are recorded and compared
4. A test not in the runner does not exist — the runner enumerates files and fails on an
   unregistered harness (proven by `test_runner.py`)
5. Break the fix and watch it fail before believing a green test — three mutations once
   killed nothing (`LEDGER.md` §Harness)

### Property and fuzz tests

- Round-trip identity per format (done at 1a, 33,717 real files)
- Fuzzed parsers produce ERROR, never a crash and never a silent zero-cue
- **Alignment identity:** `align(R, R)` returns exactly one segment at 0.000
- Performance regression is a test, so an optimisation cannot silently un-optimise

### Negative controls — one per positive class

| Control | Must be |
| --- | --- |
| time-reversed subtitle | REFUSED (measured 1.25×) |
| per-cue jitter σ = 4 s | REFUSED (1.18×) |
| a different show's subtitle | REFUSED (1.39×) |
| sequel season sharing an episode number | REFUSED (1.28×) |
| opening cues **deleted**, not shifted | **one segment, no phantom break** (3.21×, −1.00 s) |
| broadcast cut on a speech mask | REFUSED with the failing-bucket reason (1.94×) |
| wrong episode on a speech mask | REFUSED (1.36×) |

---

## The three environment answers

| Question | Answer |
| --- | --- |
| **What is this judged on?** | Laptop hardware, Windows and Linux. The VAD constants and the perf baselines are re-measured when build moves to the stronger machine (`10-deployment.md` §migration) |
| **What cannot be verified locally?** | macOS UX beyond the automated suite (GitHub Actions covers build + test) |
| **Is a display/scale layer in scope?** | Yes — the GUI ships at launch (RUNBOOK 3d). DPI-aware geometry, and `"11 confident, 1 refused"` contains "confident" |

## Code that never runs in the local configuration

None — and as of 2026-09-08 that is **measured, not asserted.** The Rust path is cut, so
there is no second implementation to rot. ffmpeg is a fallback that every real file in the
corpus avoids, so it was reachable only in principle until
`TSUBASA_NO_NATIVE_DEMUX=1` shipped at 0c; the container suite now sets it and requires the
fallback's cues to match the native reader's **to 1 ms** on a real file.

⭐ **How to give this project ffmpeg:** `TSUBASA_FFMPEG=<folder holding ffmpeg and ffprobe>`.
On the build machine that is `TheForge/Workshop/media-kit/bin`. ⛔ **The resolver must never
hardcode it** — PATH, then `$TSUBASA_FFMPEG`, then the cache directory, and nothing else;
`subsync` hardcodes a local install and this ships to other people. Checks needing ffprobe
**SKIP with the reason and the variable name printed** when it is absent.

## Test environment

The same environment, a dedicated corpus directory, verified teardown. Nothing is
destructive, nothing reaches the network, nothing contacts a person. ⛔ The suite must
never write inside the corpus.

## Related

`08-probes.md` — every probe and its verdict · `12-alignment.md` §8 — the oracle
acceptance · `09-corpus-strategy.md` — the three gates · `LEDGER.md` §Harness
