---
type: spec
title: tsubasa — The Probes
desc: Every measurement that shaped this build, with its method and verdict. Six probes on 2026-09-07 reversed four decisions; fourteen more on 2026-09-08 (eight from the corpus review, six from the adjudication) reversed or settled another seven. Read this before proposing anything the spec rules out.
date: 2026-09-08
---

# 08 — The Probes

> ⭐ **The working rule:** *measure the path before scoping the work.* Twenty probes have
> now run. Eleven changed the plan. Every threshold and every cut in this pack points at a
> row below.

Probe scripts live in `tsubasa-corpus/_work/` and write their own `.out` beside
themselves. None reads the sealed slice; the material each used is named.

---

## Summary

| # | Question | Answer | Effect |
| --- | --- | --- | --- |
| **A** | Does a CRC32 identity index pay? | 1.11% ceiling | ⛔ cancelled |
| **B** | Where does the runtime go? | 93% in one loop; 37× available | Rust optional |
| **C** | Does a romaji alias table pay? | 47.3% ceiling *(on a third of the key)* | added, gated |
| **D** | Can split detection be borrowed? | subsync 4/4, engines 0/4 | keep ours |
| **E** | How often is there no subtitle track? | 37.5% of a real library | VAD is core |
| **F** | Does the verdict work on a speech mask? | empty band 1.42–2.63× | holds; constants separate |
| **G** | Does Wikidata cover the aliases? | 55.2% **with failed controls** | ⚠ re-run required |
| **O1–O8** | What can the catalogue teach recognition? | 4 defects, 5 mechanisms | Stage 1, 2, 4 re-scoped |
| **J1** | What do the two cheapest parser fixes buy? | unknown 10.6 → 2.4%; `(N)` 2,108 → 0 | A2 first |
| **J2** | One primitive for offset + cut + walk? | 29/29 offsets, 135× cheaper | ⭐ Track B re-based, and BUILT |
| **J3** | Split detection on a speech mask? | break invisible; cuts correctly refused | VAD single-offset at launch |
| **J4** | Can clusters replace title ranking? | 60,161 candidate pairs from episode sets alone | ranking stays; probing confirms |
| **J5/J6** | Can the fast path drop ffmpeg? | Cues-indexed MKV read **0.085 s** vs 3.0 s | ⭐ native reader (decision D2) |

---

## A — the CRC32 index. ⛔ CANCELLED

15,378 files; 36% fail the pattern parser; 4.2% carry a CRC32; **170 of the failures do
(1.11%)**. The failures are films, date-stamped broadcasts and two parser gaps — a parser
problem, not a database problem.

## B — where the time goes

`cProfile`: **93%** in one Python loop calling numpy 75,000 times. Batched 3.1×;
coarse-to-fine + batched **37×** (0.436 s → 0.012 s), safe because `MR_TOL = 0.35` makes
every real peak ≥ 0.70 s wide. **Superseded by J2**, which removes the scan entirely.

## C — the alias table

19,034 files: 40.4% of parsed files have an **empty** ASCII slug; ceiling 47.3%. ⚠
Measured against `titles.json` (4,620 rows) — the mid-crawl artefact. The full key has
12,259 rows (O1). Problem size, not solution coverage.

## D — split detection. KEEP OURS

Four real broadcast cuts: subsync exact on all four; ffsubsync and lapse finished none,
and one ffsubsync setting made a file worse than untouched with nothing in its output to
say so. **The engines can produce an answer; they cannot tell you when they have.**

## E — no subtitle track: 37.5%

120 videos across three real libraries: text track 45.8% · bitmap only 16.7% · **none
37.5%** (movies 52.5%). Bitmap timing brings 62.5% within the unchanged verdict.

## F — the verdict on a speech mask

Silero, real negatives only: correct 2.63 · 2.77 · 3.09 · 3.37 · (19.38); wrong 1.27 ·
1.31 · 1.33 · 1.41 · 1.42. **Empty band 1.42–2.63×.** Mechanism proven on 5/5; constants
still to be fitted — J3 now shows a correct uncut pair at **2.42×**, so the cue-vs-cue
2.5 cannot be inherited.

## G — Wikidata coverage

### G1 — ⛔ NOT A MEASUREMENT. Superseded 2026-09-08

400 sampled shows: 55.2% strict, 59.5% with partial. **Its own controls failed** (ナルト →
`narutomaki`), two implementations disagreed **symmetrically** on identical input, and a
failed request was scored as a measured zero (`LEDGER.md` §Harness). Kept as the record;
`_work/probe_g.py` carries a banner saying so. **Do not cite these numbers.**

### G2 — the rebuilt instrument, 2026-09-08 · `_work/probe_g2_alias.py`

Every one of §G1's four conditions is met, and diagnosing the control failure turned up a
**fifth** fault nobody had named:

| Fault | Fix |
| --- | --- |
| 🚨 A failed request scored as a measured zero — *"no alias exists"* and *"I never got an answer"* were the same number | `Unanswered` is its own outcome, **never falsy-checked into the same branch**, and the count is printed beside the result |
| 🚨 No type filter, so any entity sharing a spelling competed — `narutomaki`, a **fish cake**, scored 0.75 | candidates filtered by **P31** against a broad work-class whitelist. ⚠ Broad on purpose: a false reject understates coverage, biasing the gate towards CUT, which is the safe direction |
| 🚨 **NEW — `wbsearchentities` matches a PREFIX.** Wikidata stores the anime as `NARUTO -ナルト-`, so `ナルト` never returned it at all | a **full-text second pass** (`list=search`), run only for titles whose prefix search produced no candidate that is a work |
| The answer key was a 4,620-row mid-crawl artefact | rebuilt to **12,259** at RUNBOOK 0c |
| Only the Japanese↔romaji bridge was measured | **English measured too** — `D6` ships the table three-way |
| The run reported while its own control resolved to a fish cake | ⭐ **the controls GATE the run.** A failing control aborts before any coverage number is printed |

⭐ **Two faults were stacked and each hid the other.** Fixing only the type filter turns the
false positive into an honest MISS — coverage *drops* and reads as a regression. Fixing only
the search leaves the fish cake competing. Both together give `Naruto` at **1.00**, and all
seven controls pass.

### ⭐ THE MEASUREMENT — 2026-09-08, 400 shows, seed 20260907

| Bridge | RESOLVED | PARTIAL | ABSENT | **UNANSWERED** | realised |
| --- | --- | --- | --- | --- | --- |
| Japanese → romaji | 155 | 16 | 229 | **0 of 400** | **38.8%** |
| Japanese → English | 157 | 13 | 170 | **0 of 340** | **46.2%** |

430 requests · 2 retries · 669 entities · 231 s. Sampled from the **12,120** eligible rows
(both titles present, sealed excluded) of the rebuilt 12,259-row key.

✅ **GATE: 38.8% against a 15% kill threshold → A7 is KEEP.** The threshold was set before
this number existed and was not renegotiated after seeing it.

⚠ **38.8% is NOT comparable to §G1's 55.2%, and the drop is not all instrument.** Two
things changed at once:

1. **The population.** §G1 sampled a 4,620-row key built from the cached *index* — 4,524
   mostly well-known shows. This samples 12,120, which is the long tail, and Wikidata
   covers famous shows far better than obscure ones. **This alone would lower the figure.**
2. **The false positives are gone.** §G1 counted fish-cake-class matches as coverage.

⭐ **And the number is a FLOOR, which is the safe direction for a gate.** The ABSENT
examples show why: `はぶらし／女友だち` found `Haburashi` and scored it ABSENT because the
key's romaji carries the full compound title `Haburashi / Onna Tomodachi`; two Crayon
Shin-chan and Anpanman *films* returned nothing at all, their titles being long
subtitled compounds. **Normalising the query title — dropping a trailing subtitle, splitting
on `／` — is untested headroom** and is the first thing to try inside A7's one-day box.
⛔ Do not tune it into the gate retroactively; the gate has already passed.

⛔ **Kill threshold stays at 15% realised**, set before the number existed and not
renegotiated after seeing it.

---

## O1–O8 — the corpus review, 2026-09-08

Full method and numbers: `CORPUS-OPPORTUNITIES.md`. One line each:

| # | Finding | Effect |
| --- | --- | --- |
| O1 | the answer key is **12,259** entries, not 4,620; 20.1% of entries carry both a Latin and a CJK filename; 10.3% carry a far Latin alias | every alias number re-measured; three-way table |
| O2 | 663 high-frequency decoration tokens the hand list misses; 361 release groups | decoration vocabulary |
| O3 | within-show episode slot is 100% unanimous (6,732/6,734 shapes); an offline shape table transfers to 25% and agrees 38–42% | keep A4 at runtime; no shipped table. **guessit: 95% of its disagreements are a resolution or year** |
| O4 | kana phonetic bridge: 22.7% strict → **80.6% rank-1 / 99.1% in-folder**; fabricated max 0.83 | ships as a rule |
| O5 | 345 real pairs: SAME 42% · cross-script UNSURE 40% · **DIFFERENT 9.9%, all English↔romaji**; fan-out median 8; **0 wrong-show SAME**; 7 shows need an episode-set offset | benchmark; three-way table; hypotheses |
| O6 | cluster coherence ≥ 0.60: 24/44 correct kept, **0/60 wrong** accepted; offsets cluster at 0, ±1 s, +9.5–10 s, ±90 s | second signal; offset prior |
| O7 | 84 entries hold both spellings of one show; film titles 37.2% polluted | signature = tiebreak |
| O8 | bare `E##` is the third most common scheme on the site — **14.7% of series keys carry an episode token**, 77.2% of our unknowns | A2 fix |

Plus the four defects the gate could not see: bare `E##`, the ` (N)` suffix (81% wrong on
2,602 real files), full-width digits invisible to `tokenize()`, and two-file schemes
believed at 0.75.

---

## J1 — the two cheapest parser fixes, at catalogue scale

`probe_adj1_parserfix.py`, wrapper over the vault parser (source untouched), 201,785
non-sealed catalogue files + 8,618 non-sealed video-naming files.

| | before | after |
| --- | --- | --- |
| catalogue `unknown` | 10.6% | **2.4%** |
| series key still carrying an `E##` token | 9.1% | **0.9%** |
| video files whose episode the ` (N)` suffix changed | 2,108 of 2,602 (81.0%) | **0** |

**Effect:** A2 fixes are the first build step. They cost hours and they are worth more
than the alias table's whole ceiling.

## J2 — one primitive for offset, cut and verification

`probe_adj2_hist2d.py` (take 1), `probe_adj2b` (take 2), `probe_adj2c` (take 3), against
subsync's 29-pair megatest ground truth (10 sub-vs-sub, 19 sub-vs-video-track, 5
`MUST_REFUSE`, 4 synthetic controls). Full design in `12-alignment.md`.

| Take | Change | Result |
| --- | --- | --- |
| 1 | global difference histogram; bucket-level split | 21/29; 140× faster |
| 2 | plateau centre; cue-level split over global candidates; subsync's guards | 23/29; minority segments still missed |
| **3** | **+ per-bucket candidates** | 29/29 offsets · 26/29 cue-correct · 23/29 exact break time · all 5 refusals refused · all controls right · 31 ms/pair vs 6.6 s |
| ⭐ **BUILT** | **+ one-hit tie tolerance · refinement against the OBJECTIVE, not the histogram · the measurability floor** | ⭐ **29/29 offsets · 29/29 cue-correct outside declared spans · 29/29 breaks inside their own uncertainty · 49 ms/pair.** Six mutations, six kills. `tests/test_alignment_oracle.py`, `tests/test_negative_controls.py` |

**Why take 2 missed:** a minority segment's ~23 hits are inside the noise of 4,800
candidate bins (expected ~60 hits at a random offset). The second dimension fixes it by
construction. The three residuals (boundary in a quiet gap, a 0.2 s estimator
disagreement on identical-source pairs, tie-break) are ruled in `12-alignment.md` §3.5.

## J3 — split detection on a speech mask

`probe_adj3_vadsplit.py`. Yomi no Tsugai ep18 (dev slice), real audio → Silero onsets
(765, 49% speech, 21 s to compute); six subtitles; both engines.

| Subtitle | subsync | histogram | Verdict |
| --- | --- | --- | --- |
| own track | +0.350 · 2.77× | +0.320 · 2.74× | accept, 0 failing buckets |
| ABEMA | +0.125 · 2.77× | +0.058 · 2.70× | accept |
| Netflix | −0.700 · 2.60× | −0.877 · **2.42×** | accept / borderline |
| **NanakoRaws AT-X, cut** (truth +0.400 / −9.825 @3:42) | −9.550 · 1.94× | −9.529 · 1.96× | **REFUSED**, opening bucket fails |
| **shincaps AT-X, cut** | −42.775 · 1.94× | −42.755 · 1.96× | **REFUSED**, opening bucket fails |
| wrong episode | −40.850 · 1.36× | −40.820 · 1.36× | REFUSED |

Pre-break stretch: 117 onsets, 0.26 at the true offset vs 0.22 at the wrong one —
**margin 0.04 vs 0.35 required**; segment rate 0.26 < `MIN_EXCESS × chance` 0.37. The true
offset was a candidate; no guard could take it.

**Effect:** the VAD path ships **single-offset and refuses on a failing bucket**; mask-path
constants are fitted separately; mask-path split detection → evolution. The pack's
"highest-risk gap" is closed by measurement rather than by silence.

## J4 — can cluster structure replace title ranking?

`probe_adj4_clusters.py`, the 116-show overlap pool. 5,840 video files in 327 clusters
(**97.0% in clusters of ≥ 3**); 985 jimaku files in 856 clusters (750 singletons — an
artefact of the one-file-per-shape download, not of real folders). Episode-set overlap
alone: **60,161 candidate cluster pairs, 674 same-show**; median 47 candidates per video
cluster. **Effect:** title ranking stays primary; cluster probing is the confirmation
step; coherence (O6) is the second signal.

## J5 / J6 — the fast path without ffmpeg

`probe_adj5_mkvdemux.py`, `probe_adj6_mkvcues.py`, a real 1.44 GB SubsPlease MKV.

| Method | Wall | Bytes read | Cues vs ffmpeg extraction |
| --- | --- | --- | --- |
| ffmpeg extract (cold / warm) + ffprobe | 3.04 s / 0.82 s + 0.32 s | 1.4 GB | — |
| pure-Python block walk | 7.96 s cold / 1.02 s warm | 0.2 MB, 88,340 seeks | 323/323, max diff 0.0000 s |
| ⭐ **Cues-indexed walk** (SeekHead → Cues → subtitle blocks) | **0.085 s** | **30.5 KB, 5,056 seeks** | **323/323, max diff 0.0000 s** |

mkvmerge writes a CuePoint for every subtitle block by default; the reader jumps straight
to them. Fallback order: Cues → block walk → ffmpeg. **Effect:** decision D2 — a native
container reader on the fast path removes ffmpeg from 62.5% of the library and from the
importable module, and makes *24 episodes in ~3 s* the measured target rather than a
hope.

✅ **BUILT 2026-09-08, RUNBOOK 1d, and the probe's numbers held.** Ten real 1.44 GB files:
**0.087 s median / 0.110 s worst**, ~30 KB each, **0.000000 s** from both the block walk
and the ffmpeg-extracted `.ass`. Ep 18 reads **323 cues** — the probe's exact figure.
24 episodes ≈ **2.1 s** of container reading.

🚨 **One thing the probe did not ask, and it is the thing that had to be built.** *"mkvmerge
writes a CuePoint for every subtitle block by default"* is a statement about **one muxer's
default**, and the probe measured **one file**. A muxer that indexes sparsely returns a
well-formed subtitle **missing lines**, with a plausible count and nothing on screen to say
so. The shipped reader therefore **verifies the index** — a contiguous run of two clusters
walked and counted — before trusting it. ⭐ *A probe measures that the shortcut works here;
it cannot measure that it is safe everywhere.*

---

## What the 2026-09-08 probes changed in the pack

| Was | Now | Probe |
| --- | --- | --- |
| three parsers on every file | ours first; anitopy, guessit lazy; two fixes first | O3, O8, J1 |
| alias table romaji ↔ Japanese, measured on 4,620 | ⭐ **one entity and N names** (Wikidata has no romaji field), enumerated by P31, ranking-only, built | O1, O5, G, **A7/1** |
| a fan-out cap fitted from the key-size distribution | ⛔ a **bound**, not a precision guard — the sweep is flat at 0.00% from cap 1 to 256 | **A7/3** |
| the alias table may answer any pair | ⛔ **never a CONTAINMENT pair** — `Naruto` / `Naruto Shippuuden` | **A7/3** |
| signature = verdict | signature = tiebreak | O7 |
| A4 trusts two files, blind to full-width | `MIN_FILES = 3`, NFKC in `tokenize()` | O3 |
| offset scan + coarse-to-fine + greedy split + separate walk | **2-D difference histogram**, guards unchanged | J2 |
| VAD path: split-on-mask "must be resolved" | single-offset + refuse; constants fitted separately; split → evolution | J3 |
| ffmpeg on every fast-path run | native Cues-indexed reader; ffmpeg fallback and audio only | J5/J6 |
| minimal LGPL ffmpeg build (`11-ffmpeg-build.md`) | struck — GPL-3.0 makes it moot | licence ruling |
| ≤ 3 s/episode VAD target | ~21 s measured on this laptop; restated | J3 |

---

## A7/1 – A7/4 — the alias table's own four, 2026-09-08

Run during the A7 build, all in `_work/`. Each answered a question the build could not
proceed past, and two of them changed the design.

| # | Question | Answer | Effect |
| --- | --- | --- | --- |
| **A7/1** `probe_a7_sparql.py` | Enumerate or search? And **where does a romaji form live?** | 113,845 entities in 13 queries against ~2 h of per-show search. ⛔ **`ja` 100% · `en` 100% · `mul` 0% · en-aliases 90%, and the romaji is INSIDE the aliases** | ⭐ the table is **one entity and N names**, not three columns. `D6` amended |
| **A7/2** `probe_a7_precision.py` | `vnbench` says +28 points — is that real? | ⛔ **The benchmark scores only CORRECT pairs, so it is recall with no precision term**, and fan-out cannot see A7 because the table turns UNSURE into SAME and both survive `!= DIFFERENT` | supplied the cross-pair control: **6 of 20,000, all label noise**. Also found the attribution bug: **155 of 259 "rescues" scored ≥ 0.80** |
| **A7/3** `probe_a7_lookup.py` | Why did one pair stop bridging and another start? | `ナルト` names **13** entities (later 35) and the cap of 4 refused it; `Dr Stone` reaches its own TV special | ⭐ the cap re-fitted as a **bound**; `one_contains_the_other` added |
| **A7/4** `probe_a7_loadcost.py` | Where do 1.7 s of table load go? | **1.55 s is the JSON parse**; decompression alone is 0.247 s; a flat line format is **1.9× per key** | the shipped format. ⚠ **An on-disk index is the real answer and it is B5's call** |
| **A7/5** `probe_a7_containment.py` | Does a phonetic containment arm earn its place? | **0 of 9 cases changed.** Unrestricted it refused a CORRECT bridge — `to_romaji` drops kanji, so `宇宙戦艦ヤマト` folds to `yamato`, inside `Space Battleship Yamato` | ⛔ the arm was **removed**; an entity-subset rule was rejected too (fired on 4 of 5 pairs that must be kept) |
| ⭐ **adj16** `probe_adj16_aliasadversary.py` | `doctrine/verification` Layer 2 — defeat every check | **7 findings against a green suite** (41 checks, 19/19 mutants), 3 of them shipping defects | the deriver rewritten; `except Exception` in `_read`; a HARD negative control; **60 checks, 27/27 mutants** |

⭐ **A7/2 is the one to re-read.** A benchmark whose ground truth is *pairs a human would
call correct* can only ever measure recall — and the guard that usually supplies precision
was **structurally blind** to this particular feature. **Ask which decisions your main
instrument never reaches**, before believing a number it gives you.

---

## B8/1 — does `measurable` separate *unreadable* from *not a match*? 2026-09-09

`_work/probe_b8_1_measurable_vs_refused.py` · **verdict: NO, and §3.6 was amended.**

**The question.** `12-alignment.md` §3.6 rules that `measurable is False` means ERROR. Its
second condition is *the achieved rate beats the noise floor* — and a wrong pair with 500
real cues is, by construction, a pair whose rate does not. So does the rule as written send
the project's own negative controls to ERROR?

**Method.** Align all five `MUST_REFUSE` pairs and the three constructed controls the
negative-control suite uses; print `n`, chance, score, the noise floor, raw excess and
`measurable` for each. ⛔ Measure it rather than reason about it.

**Result — every one of the eight came back `measurable=False`**, at 164–528 cues a side:
1.28× · 1.64× · 1.47× · 1.38× · 0.09× (reversed) · 1.22× (jittered). Only
`diamond01_tv vs diamond01` was measurable (2.02×), and it is refused by the bucket walk
instead.

⭐ **So the outcome split cannot be `measurable`.** It is the **cue count** —
`min(n_ref, n_sub) < MIN_ALIGNABLE_CUES` is ERROR; anything above it that fails to beat its
noise floor is REFUSED, *measured and not a match*. `Fit.measurable` is unchanged and
correct about the question it actually answers, which is whether `excess` means anything.
Built in `tsubasa/verdict.py`; the amendment is in `12-alignment.md` §3.6.

⚠ **Second-order finding, and it explains the shape of the band on real files:** at a 0.15
chance level, an excess of **1.2× needs ~2,300 cues** to be distinguishable from luck.
Real episodes carry 300–900. So the *below the 1.5× floor* arm of the band is barely
reachable in practice — wrong pairs land in *not a match* instead, which is why that branch
had to exist.

---

## 3a/1 — is the tag-scan window load-bearing? 2026-09-09

`_work/probe_3a_1_window_is_load_bearing.py` · **verdict: NO. The guard was deleted.**

**The question.** `sidecar.WINDOW = 4` bounded how far back the language-tag scan looked,
on the reasoning that ordinary English words which are also ISO codes (`is`, `no`, `it`,
`am`) must be kept away from the extension. A mutation setting it to **999 survived** the
suite, and `doctrine/verification` says a survivor is information either way.

**Method.** Parse every real subtitle filename in the dev slice at both settings and
compare the full answer — stem, language, flags.

**Result: 0 differences over 24,315 filenames.** The right-hand constraint — *everything
after the candidate must be a known flag* — was doing the whole job; an ordinary word
loses because the words after it are not flags, not because it is far from the end.

⭐ **And on the one shape the bound could change, it gave the WORSE answer:**
`Show.no.forced.sdh.cc.hi.srt` read as `hi` with `no.forced.sdh.cc` swallowed into the
stem, where unbounded it is Norwegian with four flags — which is what the name says.

⛔ **The bound went and its two mutants went with it**, replaced by a check that attacks
the constraint actually holding the line. Same sequence as the alias score gate.

---

## 3a/2 — the dedupe dry run over a real library, 2026-09-09

`_work/probe_3a_2_dedupe_dryrun.py` · **verdict: it found a defect 94 green checks did
not.** ⛔ Writes nothing, moves nothing, trashes nothing.

**Method.** Walk the dev slice's `video-naming/` folders, group every subtitle into the
`(video × language)` slots 3a will use, and print what `plan()` would do. Alignment is
stubbed CONFIDENT on purpose — the question is whether the SLOTTING and NAMING behave, and
mixing in the aligner would make a wrong answer ambiguous between two layers.

| | before | after the fix |
| --- | --- | --- |
| slots seen | 6,192 | — |
| ⭐ **slots resolving to `und`** | **5,932 (95.8%)** | — |
| 🚨 **files that would be RENAMED** | **5,980 of 6,192** | **48** |
| files that would be trashed | 231 | 231 (verified genuine `.ass`/`.srt` duplicates) |

🚨 **`output_name` wrote the language tag unconditionally**, so every untagged file got
`.und.` — a token no player understands, on a file the user never asked us to touch — and
the namer was not idempotent, so a second run would do it again. The 48 that remain are
all `.JA.` → `.ja.` case normalisation.

⚠ **No fixture could have found this**, and that is the finding worth keeping: every
fixture in the suite had a language, because a fixture is written by somebody thinking
about languages. `doctrine/robustness` calls the first dry run *a design review*; this is
the second time in this project that review has returned something nothing else saw.

---

## 3b/1 — does the creditless guard fire on real files it must not? 2026-09-09

**Method.** `_work/probe_3b_1_creditless_sweep.py` runs `movies.is_creditless` over every
filename in the corpus except the sealed slice — **46,733 names** — with the pre-fix regex
beside the post-fix one, then a table of constructed MUST / MUST-NOT cases the sweep
cannot contain.

**Why it exists.** `is_creditless` was written at A10 and reachable only from the FILM
path. 3b made discovery call it on every file, on both sides. ⛔ A guard that skips a file
with a stated reason is not free once it fires on the wrong ones: the user is told the
file *"carries no dialogue"*, and `unpaired()` then says no subtitle carries that episode.
**Both sentences are false and the file is invisible.**

| | Before | After |
| --- | --- | --- |
| hits over 46,733 real names | **28** | **25** |
| of those, real subtitles wrongly refused | 🚨 **3 (10.7%)** | **0** |
| real NCOP/NCED still refused | 25 | **25 — none lost** |
| constructed MUST-refuse shapes passing | 12 of 18 | **18 of 18** |

🚨 **The defect: `clean[\s._\-]*(?:op|ed)` accepts ZERO separators, so `clean` + `ed` is
`cleaned`.** And `cleaned` is a subtitle-community convention for a sub with ads and
typesetting stripped — *precisely the file this tool exists to sync*:

```
Hibike! Euphonium S3 - 01 (NHKE 1440x1080i MPEG2 AAC)[cleaned-retimed].srt
[Anon][QYQ][Kanon][DVDRIP][22][AVC_AAC][A8E2A2B3] (cleaned).ass
[Cleaned] Megaton-kyuu Musashi - 03 (TOKYO MX).srt
```

⭐ **The same sweep found six FALSE NEGATIVES**, including `NCOP1v2` and `NCOP01v2` — the
commonest way a creditless file actually arrives, missed because the trailing
`(?:[\s._\-]*\d{1,2})?` ate the digit and the lookahead then met `v`. Also `NC-OP`,
`NC OP 01`, `NC_ED` and the whole `Textless` vocabulary. A missed one is offered to every
episode in the folder.

**Verdict.** Two-letter forms require a separator; spelled-out ones do not; `v\d` is part
of the token; `textless` joins the alternation.
⚠ **One trade accepted with its measurement:** `Clean ED` with a separator is a real
creditless convention, so `Clean Ed <person>` still fires. That shape occurs **zero times
in 46,733 real names**, and `00-INDEX.md` Rule 2 makes the costs asymmetric — a missed
creditless file can produce a phantom alignment; a false positive is one file skipped with
a stated reason.

⭐ **The transferable finding is not the regex.** An alternation with an optional
separator matches the CONCATENATION, and nothing about reading it says so. **Sweep a guard
over the real corpus the first time anything calls it on every file.**

---

## Still open, honestly

| Gap | Route |
| --- | --- |
| ~~Probe G re-run on the full key with controls passing~~ | ✅ §G2, and A7 is built on it |
| **The alias table inherits Wikidata's own errors** — no local check can see a wrong row there | accepted; Rule 1 holds — it ranks, timing decides |
| **0.77 s to load 221,258 keys** against B5's ~2.9 s remaining budget | B5, with A7/4's breakdown. ⚠ It was 1.84 s at 233,507 keys until the adversarial pass removed the fragment keys |
| mask-path constants | B6, with the Yomi material as the first negative-control set |
| non-Japanese cross-platform pairs (3 exist) | Sonic, if convenient |
| a real 3+-break specimen | derive synthetically; the guards are what is tested |
| PGS ON/OFF pairing on Fate HF and Evangelion (`probe_vn17`: 2 of 22 disagree) | 1c follow-up |

## Related

`CORPUS-OPPORTUNITIES.md` · `12-alignment.md` · `09-corpus-strategy.md` · `LEDGER.md`
§Harness — the instrument faults these probes caught
