---
type: spec
title: tsubasa — Alignment
desc: The alignment design in one place — the objective (unchanged from subsync), the ONE primitive that answers offset, cut and whole-runtime verification in a single pass, the guards (unchanged), the verdict band, and the VAD path as measured on 2026-09-08. Supersedes the alignment parts of 06-edge-cases §5, 08-probes §B and the subsync docs as the build authority.
date: 2026-09-08
---

# 12 — Alignment

> **What Sonic asked for:** *"every part of the episode locks in well"* — including the
> breaks some versions carry and some subtitles do not — *"with extreme efficiency"*, so
> the whole thing feels like magic and can sit inside another package.
>
> **What this part rules:** the objective stays subsync's (it is the strongest idea in the
> space and was never the slow part). The *search* is replaced by one primitive that
> answers three questions at once. The guards stay, to the constant. The VAD path ships
> single-offset and refuses cuts, because that is what the measurement says.

`Workshop/subsync/` remains the **oracle**. Every claim below was measured against its
29-pair megatest ground truth on 2026-09-08 (`08-probes.md` §J2) — nothing here is argued
from taste.

---

## 1 — Vocabulary and sign convention

| Term | Meaning |
| --- | --- |
| **R** | the *reference* spike train, in seconds, sorted: cue starts of the video's text track, ON-times of a PGS/VobSub track, or Silero speech onsets |
| **A** | the subtitle's cue starts, sorted |
| **offset** | the number of seconds **added** to every subtitle timestamp. Subs that appear **late** need a **negative** offset. `d = r − a` is a candidate offset |
| `MR_TOL` | 0.35 s — a reference cue "lands" if a subtitle cue is within this |
| `CLUSTER_TOL` | 0.15 s — starts closer than this are one moment (bilingual tracks, speaker-name cues) |
| **segment** | a stretch of reference time with one offset. A cut file has ≥ 2 |
| **chance** | the match rate cue density alone produces: `min(1, 2·MR_TOL·\|A\| / span)` |

`unique_starts()` and `dialogue_only()` are inherited unchanged.

---

## 2 — The objective, unchanged

> **Match rate at an offset = the fraction of reference cues that find a subtitle cue
> within `MR_TOL` — judged against what density alone would produce.**

Everything subsync recorded under *"tried and discarded"* stands: correlation as the
objective put the peak 9–30 s from the truth; the audio envelope gets no vote; two
references agreeing passes cut files. **Do not rebuild them.**

---

## 3 — ⭐ The primitive: the 2-D difference histogram

### 3.1 What it is

Every pair `(r, a)` with `|r − a| ≤ window` contributes one difference `d = r − a`.
Histogram those differences at 10 ms bins and box-smooth by `2·MR_TOL`: the value at bin
`o` is then **exactly the match count at offset `o`** — the same objective as scanning
4,800 offsets, computed for every offset at once, from the differences themselves.

**Then add the second dimension.** Bucket the same differences by the reference cue's
time (120 s buckets). Inside one bucket the offset that governs that stretch is the
majority, so a break's minority offset — invisible in the global histogram — is the
plain peak of its own buckets.

```
candidates = global top-6 peaks  ∪  per-bucket top-2 peaks       (deduped within 0.5 s)
each peak  = plateau CENTRE of the smoothed histogram
final value = the OBJECTIVE, scored on a fine local grid -- not the histogram (3.5)
```

### 3.2 🚨 Why the second dimension is not optional — measured

`08-probes.md` §J2, take 2: with a **global** histogram only, the pre-break segment of a
broadcast cut was missed on both Clevatess files. The reason is arithmetic, not tuning:
at a random offset the expected hit count is `chance · |R|` ≈ 60 for 300 cues at 20%; a
pre-break segment carrying 8% of the cues contributes ~23 hits, which is inside the
noise of 4,800 candidate bins. subsync only sees such a segment because its split search
rescans **every** offset per split position. The per-bucket histogram sees it because
within its 120 s it is the majority. Take 3 (bucketed candidates) found it.

### 3.3 The split search — subsync's, over the candidate set

With K candidates (measured K = 15–21 on real pairs) build the hit matrix `H[k, i]` =
*does reference cue i land at candidate k*. Then **exactly subsync's greedy cue-level
search**: for each current segment, the best single cut is the cue index maximising
`head[c1, k] + tail[c2, k]` over candidate pairs — one cumulative sum, vectorised — and a
cut is kept only if it earns itself under every guard below. Repeat until nothing earns
itself. **Uncapped**: a 12-episode batch file with 11 breaks is 11 accepted cuts.

| Guard | Value | Status |
| --- | --- | --- |
| break size | `MIN_BREAK` 1.0 s ≤ jump ≤ `MAX_BREAK` 60 s | **unchanged** |
| overall gain | `MIN_SPLIT_GAIN` 0.02 | **unchanged** |
| local margin | `MIN_LOCAL_MARGIN` 0.35 on the smaller segment | **unchanged** |
| both segments | each ≥ `MIN_EXCESS` × chance | **unchanged** |
| smallest segment | `MIN_CUES` 12 reference cues | **unchanged** |

⛔ **Do not loosen a guard to make a cut detectable** (LEDGER-HOT). The 2-D histogram
changes *where candidates come from*, never *what earns a cut*.

### 3.4 What it measured — the 29-pair megatest oracle

✅ **BUILT AND GREEN 2026-09-08** (`tests/test_alignment_oracle.py`). Final numbers, on
the shipped code rather than the probe:

| Claim | Result |
| --- | --- |
| offsets within the corpus's own per-pair tolerance | **29 / 29** |
| every cue OUTSIDE a declared undetermined span gets the truth's offset | **29 / 29** |
| the truth's break lies INSIDE the span we declare undetermined | **29 / 29** |
| every cut file found cut · every uncut file left whole | **9 / 9 · 20 / 20** |
| `MUST_REFUSE` pairs scoring below the segment floor | **4 / 4** |

| Engine | 29 pairs | per pair |
| --- | --- | --- |
| subsync scan + greedy split, as written (rate hypotheses ×9) | 192 s | 6.6 s |
| subsync after Probe B's coarse-to-fine (projected) | ~6 s | ~0.2 s |
| **2-D histogram + cue-level split + local objective refinement** | **1.4 s** | **49 ms** |

⚠ The probe reported 23/29 exact and 26/29 cue-correct. Three things closed the gap, all
found by building it for real: the tie tolerance (§3.5), refinement against the objective
rather than the histogram (§3.5), and the measurability floor (§3.6).

Every `MUST_REFUSE` pair refused (1.28–2.02×). Negative controls: time-reversed 1.25×,
σ = 4 s jitter 1.18×, a different show 1.39× — all refused; **deleted opening cues →
one segment at the right offset, no phantom break.**

### 3.5 The three residuals, and who decides them

| Residual | What was seen | ✅ Resolved as |
| --- | --- | --- |
| **Boundary inside a quiet gap** | Both Clevatess-vs-video cuts and one sub-vs-sub cut put the break at the *other* end of the opening-song gap | ⭐ **A tie is resolved to a POINT PLUS ITS SPAN, and the tie is tolerant of one hit.** Measured on Clevatess 07: the truth cuts at 52.1 s, the best-scoring position is 165.0 s on the far side of the same silence, and the whole argument between them is **one cue landing** — 203 hits against 202. A cue contributes at most one hit, so a one-hit margin is exactly the resolution at which a single cue's membership cannot be established. `TIE_SLACK = 1.0`, the point is the earliest tie (subsync's convention, which the truth was measured with), and `Fit.gaps` carries the span. ⚠ Three conventions were tried: the gap's **midpoint** moved breaks by up to 57 s and cost three answers; the **widest gap** fixed both Clevatess cases and broke all three Re:Zero ones |
| **Sub-tolerance estimator** | On 3 identical-source pairs the estimate sat 0.20–0.21 s from truth, just outside the corpus's 0.20 s tolerance | ⭐ **`D3b` resolved, and the median turned out to be the wrong tool entirely.** The ruling's spirit — plateau centre — was right; the diagnosis was not. **A histogram bin counts every (reference, subtitle) PAIR whose difference falls in it; the objective counts every reference CUE that finds a neighbour, at most once.** Where a cue has two subtitle cues inside the tolerance the histogram counts both and its peak drifts. So the histogram FINDS the peak and the **real objective sets the value**, on a ±0.6 s grid at 0.01 s, plateau-centred. That is subsync's own estimator, which is what the truth was measured with. It costs ~120 evaluations against a ±120 s search, so the accuracy is free — and it took offsets from 26/29 to **29/29** |
| **Tie-break between equal candidates** | none seen; specified for completeness | prefer the candidate closer to zero, then the one with more supporting differences |

### 3.6 🚨 The measurability floor — found by the negative controls

**A subtitle containing ONE cue scored 5.15× chance against a real reference.** The
arithmetic is not a bug: chance falls linearly with cue count, while the best of thousands
of candidate offsets always places that one cue on top of something.

⭐ **So a fit carries `measurable`, and `excess` is ZERO when it is false.** Two conditions,
both from the same small-sample argument the bucket walk already makes: at least
`MIN_ALIGNABLE_CUES = 5` on each side, and the achieved rate must beat the noise floor at
that cue count, computed on the **smaller** side because that bounds how many matches are
even possible.

⚠ **Zeroed, not merely flagged.** A caller reading `excess` alone must not be handed a
confident number built out of one cue. `raw_excess` keeps it for diagnostics.

🚨 **`measurable is False` means ERROR, not REFUSED** — *could not be measured*, not
*measured and rejected*. `03-permissions.md` forbids conflating them; subsync shipped that
confusion twice.

### 🚨 AMENDED BY MEASUREMENT AT B8 — that sentence is right about `excess` and wrong about the OUTCOME

**Probe B8/1, 2026-09-09.** Built literally, the line above routes **every wrong pair this
project has** to ERROR:

| Pair | cues | raw excess | `measurable` |
| --- | --- | --- | --- |
| `diamondact2_01` vs `diamond01` (sequel season) | 354 / 340 | 1.28× | **False** |
| `atelier03_haruhana` vs `katainaka03` (different show) | 205 / 266 | 1.64× | **False** |
| `memole_1985` vs `seihantai01` (1985 OVA vs 2025 TV) | 377 / 164 | 1.47× | **False** |
| time-reversed `rezero53` | 391 / 528 | 0.09× | **False** |
| a different show (`gurren01`) | 391 / 452 | 1.38× | **False** |

⛔ **A time-reversed subtitle with 528 cues was measured perfectly well.** It matched 2% of
the reference. Reporting *"could not be read at all"* for that is the REFUSED/ERROR
conflation `03-permissions.md` forbids, **running in the other direction** — and it would
have hit every wrong pair a user ever hands the tool.

⭐ **The cause is that one name answers two questions.** `measurable` bundles *is there
enough input* with *did the rate beat luck*. Both correctly zero `excess` — a caller must
never read a confident number out of either — but they are **different outcomes**:

| Condition | Outcome |
| --- | --- |
| fewer than `MIN_ALIGNABLE_CUES` on a side | **ERROR** — nothing was measured |
| plenty of cues, rate at the noise floor | **REFUSED** — measured, and it is not a match |

⛔ **`Fit.measurable` is NOT changed and the aligner is untouched**, so the 29-pair oracle
is unaffected. It answers *"does `excess` mean anything"* and answers it correctly. The
distinction belongs to the **verdict**, which is the layer whose job is to say which of the
three outcomes a pair got. `tsubasa/verdict.py`, and
`test_the_real_wrong_pairs_are_REFUSED_and_not_reported_as_unreadable` drives it on all
five real specimens.

⚠ **A useful second-order fact fell out of the same probe:** at a 0.15 chance level an
excess of 1.2× is indistinguishable from luck below **~2,300 cues** — three times what a
real episode carries. So a wrong pair at a realistic cue count does **not** land below the
1.5× floor; it lands in *not measurable*. The bottom of the band is barely reachable on
real files, and that is why the not-a-match branch has to exist at all.

### 3.7 ⚠ Which inherited guards are still reachable — measured, and mostly NOT

Each guard was removed in turn and the answer re-measured across **39 cases**: the 29
oracle pairs plus 10 adversarial controls, including a synthetic tempter that displaces
4–20 opening cues far enough to form their own histogram peak.

| Guard | Answers changed by removing it |
| --- | --- |
| ⭐ **`MAX_BREAK`** | **2** — Gurren Lagann, both directions. The documented orphaned-OP-karaoke case: 15 reference cues the subtitle lacks find a "home" ~108 s away |
| `MIN_LOCAL_MARGIN` · `MIN_SPLIT_GAIN` · `MIN_EXCESS` · `MIN_BREAK` · `MIN_CUES` | **0 each** |

**Why:** the search proposes ~18 candidates that are real histogram peaks rather than
4,800 arbitrary offsets, so the spurious far-offset those guards reject is usually not a
candidate at all — and `_best_boundary` returns nothing outright when one candidate is
best for both sides everywhere, which is the uncut case.

⛔ **They are kept.** They cost nothing, subsync measured them load-bearing against a
4,800-offset scan, and Rule 2 makes a confidently wrong answer the thing to avoid.
**What is not true is that this suite proves them** — so nobody may cite it as evidence
that they can go. `MAX_BREAK` alone is pinned by a test that removes it and watches the
answer change.

---

## 4 — The verdict, unchanged, computed from the same pass

The band in `05-interface.md` stands: ≥ 2.5× accept · 1.5–2.5× escalate · < 1.5× refuse,
with **cluster coherence** (`09-corpus-strategy.md` §Stage 4) as the escalation band's
measured second signal.

**The whole-runtime bucket walk is no longer a separate computation.** The per-bucket
histograms already hold each bucket's best offset and rate; `failing_buckets()` reads
them. Constants unchanged: `BUCKET` 120 s, `MIN_BUCKET_CUES` 8, `BUCKET_RATE_SLACK` 0.15,
`MAX_BUCKET_DRIFT` 0.75, `BUCKET_NOISE_Z` 4.0.

**Rate and drift.** Named framerate ratios are still tested on the single-offset fit
only. A linear trend across the per-bucket offsets is the unnamed-drift detector — refuse
rather than snap to a wrong ratio.

---

## 5 — 🚨 The VAD path — measured, and single-offset at launch

`08-probes.md` §J3 ran the test the previous pack said was mandatory before B6: Yomi no
Tsugai ep18, the video's real audio (Silero onsets: 765 over 1,420 s, 49% speech) against
six subtitles, on both engines.

| Subtitle | Truth / expectation | Result (both engines agree) |
| --- | --- | --- |
| the video's own track | one offset ≈ 0 | **+0.35 · 2.77×** · 0 failing buckets |
| ABEMA (streaming, uncut) | one offset | **+0.13 · 2.77×** · 0 failing |
| Netflix (streaming, uncut) | one offset | **−0.70 · 2.60×** (histogram 2.42×) · 0 failing |
| 🚨 NanakoRaws AT-X (broadcast, **cut** — truth `+0.400 / −9.825 @3:42`) | a 10 s break | **one offset −9.55 at 1.94× → REFUSED**, 1 failing bucket (the opening) |
| 🚨 shincaps AT-X (broadcast, cut) | a 10 s break | **one offset −42.78 at 1.94× → REFUSED**, 1 failing bucket |
| wrong episode (S01E15) | refuse | **1.36× → REFUSED** |

**Why the break is invisible on a mask:** the pre-break stretch (117 onsets) matches 26%
at its true offset and 22% at the post-break offset — a margin of **0.04 against the 0.35
the guard requires**, and a segment rate below `MIN_EXCESS × chance` (0.26 < 0.37). The
true pre-break offset *was* among the histogram's candidates; no guard could accept it.
On a speech mask the matched rate is ~0.3–0.5 even when correct, so every margin that was
calibrated on 60–95% cue-vs-cue rates is out of reach.

### The ruling this produces

1. ⭐ **At launch the VAD path fits ONE offset and REFUSES when the bucket walk fails.**
   The refusal is actionable: *"the first 3:42 want a different offset (about +10 s) — a
   broadcast recording with a commercial break; a subtitle from the streaming release of
   this episode will pair."*
2. ⛔ **The cue-vs-cue constants do not transfer.** Correct uncut pairs sat at
   **2.42–2.77×** on this episode — straddling `MIN_EXCESS` 2.5 — while the cut files sat
   at 1.94× and the wrong episode at 1.36×. Probe F's band was 1.42–2.63×. **The mask-path
   thresholds are fitted separately, with negative controls, before any mask verdict
   ships** (RUNBOOK B6).
3. ⏸ **Split detection on a mask → EVOLUTION**, with a stated route: re-fit
   `MIN_LOCAL_MARGIN` and the per-segment excess for the mask regime, and seed the split
   search with the **offset prior** the corpus exposed (≈ +9.5–10 s CM block, ±90 s OP;
   `CORPUS-OPPORTUNITIES.md` §3.4).
4. **Cost, measured on this laptop:** Silero over a 24-minute episode is **~21 s** with
   sequential 32 ms chunks through onnxruntime. The previous target of ≤ 3 s/episode is
   **not achievable here** without a different runtime or file-level parallelism; it is
   restated in `01-scope.md`. The profile is cached per video, so it is paid once.

---

## 6 — Cues that fall inside a removed stretch

A broadcast subtitle applied to a streaming video needs a **negative** jump after the
break; cues timed inside the removed CM block (sponsor cards, eyecatch captions) then
map to time that no longer exists and would overlap the next segment's opening cues.

✅ **`D9` RULED 2026-09-08: drop them, count them, report the count.** They cannot render
correctly under any offset. The count surfaces on the result line and in
`Result.dropped_in_gap`; the whitelist addition is in `03-permissions.md`.

---

## 7 — Cost model

| | |
| --- | --- |
| **One pair, fast path** | histogram + split + walk **49 ms measured**; reading the track is the larger cost — see `10-deployment.md` §Container reader (**0.085 s** Cues-indexed vs **3.0 s** cold through ffmpeg) |
| **24 episodes, nothing cached** | ~3 s with the native reader; ~80 s through ffmpeg |
| **VAD path, first run** | ~21 s per episode on this laptop, cached after |
| **At 10×** | linear in pairs; memory bounded by the difference list (`\|R\| × candidates-in-window`, ~35 k floats for a 24-minute episode) |
| **Nothing changed** | one head/tail hash per file, no alignment |

---

## 8 — Acceptance — what "done" means for Track B

| Suite | Asserts | State |
| --- | --- | --- |
| `test_alignment_oracle.py` | the 29 megatest pairs: **offsets within the truth tolerance; every cue outside a declared undetermined span within `MR_TOL` of the truth's offset; the truth's break inside that span**; every cut file cut and every uncut file whole; `MUST_REFUSE` refused; self-align returns exactly 0.000. Media-free, from `subsync/tests/fixtures/vidref/` | ✅ **green**, 10 checks |
| `test_negative_controls.py` | reversed, jittered, different show, sequel season → REFUSED; deleted-opening → one segment, no phantom; a thin input is **not measurable**; `MAX_BREAK` proven load-bearing by removing it. Carries its own positive control first | ✅ **green**, 11 checks |
| `test_vad.py` | the Yomi ep18 material of §5 (copied into `tsubasa-corpus/video-derived/` — see RUNBOOK B6): uncut → one offset within 0.15 s of the track-derived truth; cut → REFUSED with the failing-bucket reason; wrong episode → REFUSED | ⏳ B6 |
| `test_nsplit.py` | a **synthetic 3-break file** — the corpus contains no real one, and the guards are what is being tested | ⏳ owed |
| `test_perf.py` | 29 pairs under 2 s total on the reference laptop — derived from a recorded baseline, never pinned. **Measured today: 1.4 s** | ⏳ B5 |

⭐ **The oracle stays.** Any change to the primitive re-runs the 29 and must match the
oracle cue-for-cue or beat it against the truth. *"Never accept a speedup without
re-running it"* (`00-INDEX.md` Rule 4).

---

## 9 — What Rule 4 actually found here

`00-INDEX.md` said the FFT was *"the elegant answer, do it last."* Measured, the FFT of
cue **masks** is the correlation objective subsync already rejected (9–30 s wrong). The
transform that fits this problem exactly is the **histogram of pairwise differences** —
the correlation of two *spike trains*, computed from the differences rather than from a
grid — because it keeps the individual differences, and those are what give the sub-bin
refinement and the second dimension for free. Recorded so nobody re-proposes the mask FFT.

## Related

`08-probes.md` §J2–J3 · `subsync/subsync.md` §*What was tried and discarded* ·
`06-edge-cases.md` §5 · `05-interface.md` §The verdict is a band ·
probe scripts `tsubasa-corpus/_work/probe_adj2c_hist2d.py`, `probe_adj3_vadsplit.py`
