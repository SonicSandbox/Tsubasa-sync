---
type: spec
title: tsubasa — Spec Pack Index
desc: What each numbered part contains, the surfaces vocabulary, the four rules that outrank everything else in this pack, and Rule 4's worked examples as measured through 2026-09-08.
date: 2026-09-08
---

# tsubasa — Spec Pack

> **Read this file first, then load only the parts your step's `surfaces:` line names.**
> Part 2 is a fresh agent with only this pack. **Anything not written here is lost.**
> ✅ **Nine decisions (`D1`–`D9`) were RULED on 2026-09-08 and are recorded in
> `HANDOFF.md`. This pack is written to them — a `D#` marker in any part is a citation,
> not an open question.**

`tsubasa` pairs subtitle files to video files and retimes them to match, by cue timing
rather than text, so it works in any language. It is a **rebuild** of `Workshop/subsync/`,
which stays in place, untouched, as the reference implementation and the oracle.

---

## The FOUR rules that outrank the rest of this pack

| # | Rule | Consequence if broken |
| --- | --- | --- |
| **1** | **The embedded subtitle track is an ACCELERATOR, never a dependency.** So are the alias table and the native container reader. | *"Most cases will have an existing subtitle, but that can't be the crutch."* A design that assumes any of them is present fails the objective |
| **2** | **A confidently wrong answer is worse than no answer.** Refusal with a stated reason is a feature. | Every threshold in this pack sits in a **measured empty band**. A threshold set by taste breaks the whole value proposition. On 2026-09-08 this rule *refused two broadcast cuts on a speech mask* rather than guess — that is it working |
| **3** | ⛔ **No media, no corpora, no downloaded programs inside TheForge.** | The vault auto-commits. Media lives in `InfiniteVoid/WorldDominationLite/tsubasa-corpus/`. See `LEDGER-HOT.md` |
| **4** | ⭐ **Ask the efficiency question at EVERY level.** See below | Asked five times now; answered by measurement five times; guessed wrong every time it was guessed |

---

## ⭐ Rule 4 — the efficiency question, asked at every level

> **Before writing any loop, scan, search or sweep, ask:**
> **"Is there an algorithm that fits this scenario exactly — same accuracy, less work?"**

### The worked examples — all measured

| Level | Question | Naive | Answer | Gain |
| --- | --- | --- | --- | --- |
| plumbing | 4,800 numpy calls, one per offset | 0.436 s | batch into one matrix | 3.1× |
| algorithm | must every offset be scanned? | | coarse-to-fine, safe because `MR_TOL` makes peaks ≥ 0.70 s wide | 37× |
| ⭐ **transform** | *is scanning the right shape at all?* | 6.6 s/pair | **the histogram of pairwise differences** answers every offset at once and keeps the differences — `12-alignment.md` | **135× measured**, and the cut search and the walk come free |
| **I/O** | must the whole file be demuxed to read one track's timing? | ffmpeg 3.0 s | **the container's own Cues index** points at every subtitle block — `08-probes.md` §J6 | 35× · ✅ **shipped 1d: 0.087 s median over 10 real files, 0.000000 s from ffmpeg's answer** |
| work avoided | must three parsers run on every name? | 27.5 ms/name | ours first; the others only on doubt — `09-corpus-strategy.md` | 10× |
| **candidates** | must every video be compared to every subtitle? | 500×1500 = 750,000 | an index keyed on **(season, episode)** — `discover.py` | ~50× fewer pairs |
| ⭐ **recall, not speed** | the prefilter is already fast — is it *right*? | 16.0% of true answers **dropped, silently** | **Jaccard-normalise** the same 300 candidates — `naming/kana.py` | **7.4%**, at identical cost |

🚨 **The fifth row is the one to re-read.** Rule 4 usually buys time; here the same question
bought **correctness**. A bigram prefilter ranked by raw shared-count favours long titles
and threw away the right answer 16% of the time — a silent cap on rank-1 that no amount of
better scoring could recover. ⚠ **And widening it was the obvious fix and the wrong one:**
at 3,000 candidates rank-1 got *worse* and cost 2.6× more. **Ask the efficiency question
about the ANSWER, not only about the clock.**

### 🚨 Two corrections to what this file said on 2026-09-07

1. **"FFT — do it last; it changes the objective subtly."** Measured: the FFT of cue
   *masks* is the correlation objective subsync already rejected (peak 9–30 s from
   truth). The transform that fits *this* problem is the difference histogram, because it
   is exact and keeps the individual differences. Do not re-propose the mask FFT.
2. **"The offset search must brute-force."** Still true in spirit — there is no gradient
   — but the histogram makes *brute force over every offset* cost one pass. The reason
   iterative refinement cannot work (noise everywhere except the spike) stands; record it
   wherever the loop lives.

### The guard that makes it safe

⛔ **An efficiency change must not change the answer.** The 29-pair oracle suite
(`12-alignment.md` §8) is what makes that provable. **Never accept a speedup without
re-running it.** A "safe skip" needs a proof tied to a named constant.

---

## The parts

| File | Contains |
| --- | --- |
| `01-scope.md` | The objective in Sonic's words · launch vs evolution vs cut · the stack · the licence · the performance target as measured numbers |
| `02-data-model.md` | The four stores · canonicity · the cache cost model · the alias table and its provenance |
| `03-permissions.md` | The single non-human actor · **the field whitelist** · the three outcomes · the hand-back path |
| `05-interface.md` | CLI output (ruled) · the library API surasura and hato consume · naming, dedupe, language, trash |
| `06-edge-cases.md` | The catalog, by section, each with a defined behaviour |
| `07-test-plan.md` | Corpus split · ground truth · suites and what each **structurally cannot** cover · the oracle |
| ⭐ `08-probes.md` | **All twenty probes**, method and verdict. Read before proposing anything the spec rules out |
| ⭐ `09-corpus-strategy.md` | Recognition: the two axes, the cost-ordered pipeline as re-scoped, the three gates, what ships |
| `10-deployment.md` | Release shape (GPL-3.0) · ffmpeg acquisition · the container reader · the machine migration plan |
| ~~`11-ffmpeg-build.md`~~ | **Struck 2026-09-08** (`D1`): the minimal LGPL build is moot under GPL-3.0. Kept as the record |
| ⭐ `12-alignment.md` | **Alignment**: the objective, the one primitive, the guards, the verdict, the VAD path as measured, the acceptance oracle |
| `RUNBOOK.md` | Dependency-ordered build, re-sequenced, with the built steps marked DONE |

`04-identity.md` is **deliberately absent.** No accounts, no sign-in, no network during a
run.

---

## Surfaces vocabulary

| Surface | Means, in this project |
| --- | --- |
| `data` | The alias table, the decoration vocabulary, the cache, the results DB |
| `logic` | Parsing, identity, pairing, the container reader, alignment, the verdict |
| `ui` | CLI output **and the GUI — the GUI ships at LAUNCH** (RUNBOOK 3d) |
| `delivery` | Freezing, wheels, GitHub releases |
| `harness` | The corpus, the suites, the probes, the oracle |

`identity` never appears in this project.

---

## Related

`Workshop/subsync/` — the reference implementation and oracle · `HANDOFF.md` — the
decisions this pack assumes · [[Development Doctrine/workflows/dev-build]]
