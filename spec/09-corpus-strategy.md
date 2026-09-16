---
type: spec
title: tsubasa — Corpus Strategy and the Recognition Pipeline
desc: How the 238,250-filename catalogue, the 12,259-title answer key and the 10,526-file video-naming corpus are used for recognition. The two axes, the cost-ordered pipeline as re-scoped 2026-09-08, the three gates, what ships and what never does, and the one number a release is judged on.
date: 2026-09-08
---

# 09 — Corpus Strategy & Recognition

> **The corpus is three assets, not a pile of test files** — a *shape catalogue*, a
> *labelled training set*, and a *benchmark of real video↔subtitle pairs*. The 2026-09-07
> pack used only the first. This revision uses all three.

---

## What we actually have — counted on disk 2026-09-08

| Asset | Rows | Labelled with | Use |
| --- | --- | --- | --- |
| `naming/catalog.jsonl` | **238,250 filenames** (201,785 non-sealed) | jimaku entry id | **learning**: token distributions, per-show variation, alias variants |
| `naming/manifest.jsonl` | 28,133 downloaded, one per shape | entry id | the **parser gate's** test set |
| ⭐ `naming/titles.jsonl` | **12,259 entries** · 12,152 with romaji + Japanese · **10,762 with English** | AniList / TMDB ids | the **answer key**. ⚠ `titles.json` (4,620) was a mid-crawl artefact — every 2026-09-07 alias number was measured on a third of the key |
| `video-naming/` | 10,526 files, 229 shows (148 overlap jimaku) | user folder | the **video side**: real pairs, real cluster structure, the browser-duplicate `(N)` shape |
| `_work/probe_vn14_e2e.json` | 435 aligned pairs, 118 shows | show + episode | the ready-made **pairing benchmark** |

⚠ **The answer key never ships** (AniList/TMDB provenance — `02-data-model.md`). Rules
learned from it ship; tables derived from it are local to Sonic's private build.

---

## The two axes — they do not substitute for each other

| | **Axis 1 — Episode extraction** | **Axis 2 — Series identity** |
| --- | --- | --- |
| Question | *what episode is this?* | *are these two names the same show?* |
| Input | one filename | two names |
| Solved by | our parser · per-folder scheme · (lazy) anitopy · (lazy) guessit | normalisation + decoration vocabulary + kana bridge + alias table → **ranking**; the timing referee → **decision** |

**Resolve identity first and episode ambiguity becomes cheap** — a parser disagreement is
then a choice between two episodes of a known show, not of the whole library.

---

## The pipeline — ordered by cost, cheapest first

### Stage 0 — fingerprint and cache

Content hash (head + tail + size), cluster key (`scheme.tokenize` shape), cached cue
lists and VAD profiles. Enables skip-if-unchanged. Microseconds.

### Stage 1 — episode extraction: OURS FIRST, the others LAZY

**Reversed 2026-09-08.** The previous pack ran three parsers on every file ("do not pick a
parser"). Measured since:

| | ours | anitopy | guessit |
| --- | --- | --- | --- |
| resolves an episode (gate sample) | **91.9%** | 85.4% | 80.1% |
| cost per name | **0.22 ms** | 1.79 ms | **27.5 ms** |
| when ours = anitopy and guessit differs, guessit's value is a resolution or year | | | **95%** (537 of 565) |
| unknown verdicts after the two fixes below | **2.4%** | | |

Guessit was manufacturing the arbitration load (28.4% of files against a 9.3% budget) and
41 s of parse time per 1,500-file library. **Order now:**

1. **Ours**, with the two fixes measured in `08-probes.md` §J1: strip a trailing ` (N)`
   collision suffix before parsing (2,108 wrong episodes → **0** on the video corpus);
   a bare `E##` pattern below `S##E##` (catalogue unknowns **10.6% → 2.4%**; series keys
   still carrying an episode token **9.1% → 0.9%**)
2. **Per-folder scheme inference** (A4) as the independent second opinion — with NFKC
   inside `tokenize()` (full-width episode markers are 6.2% of the catalogue) and
   `MIN_FILES = 3`
3. **anitopy only when ours returns UNKNOWN or disagrees with the folder scheme**
4. **guessit only for Western-shaped names** — dotted, trailing `-GROUP`, no CJK — and
   only when 1–3 left ambiguity. Its candidates are discarded when equal to a known
   resolution, codec number or year **before** they count as a disagreement
5. A strict majority is an answer; the minority stays in `candidates` for arbitration

A refusal from ours (BATCH, CONJUNCTION) is authoritative and is never voted away.

### Stage 2 — series identity: a RANKING, then a decision made by timing

1. **Normalise** — NFC, NFKC, quotes, diacritics, romanisation folding, CJK variants,
   signature (trailing punctuation) — as built in A1
2. ✅ **Decoration vocabulary — BUILT 2026-09-08 (A2c).** `tsubasa/naming/decoration.py`
   + `tsubasa/data/decoration.json`, **176 tokens** learned by *df ≥ 25 shows and
   canonical-title rate < 5%* over 203,591 non-sealed catalogue rows: release groups,
   broadcasters, streaming services, caption markers. Re-derive with
   `python -m tsubasa.dev decoration --derive`. **Own work product; ships**
   ⚠ **Two rules the §3.1 statement does not contain and cannot work without.**
   **(a) Episode-shaped tokens are excluded** — `001`, `e07`, `s01e05`, `第三話` all satisfy
   the rule perfectly and are what the *parser* extracts; without this the vocabulary is
   264 digits of 664 and eats `Gundam 0080`. **(b) Membership never strips on its own** —
   a token is removed only when it is *separator-bounded* or in the *trailing run*, because
   `ja`, `anime` and `studio` are decoration **and** are real titles (`Ja Ja Uma`,
   `Anime Gataris`). Measured film pollution **39.9% → 2.7%**.
3. ✅ **Kana phonetic bridge — BUILT 2026-09-08 (A3b).** `tsubasa/naming/kana.py` — fold
   kana and romaji to one phonetic skeleton and **rank**, never test equality (equality
   matched 22.7%). Accept at **≥ 0.85 with a 0.10 margin**: fabricated kana never exceed
   0.83, and 0 of 300 are accepted. A shipped rule, no dictionary.
   ⭐ **The folder number is the one the product lives on** — **99.2% rank-1 inside a
   five-show folder**, against ~76% across the whole 11k pool. A user's library holds the
   shows they own, and the whole-pool figure exists to show what the bridge can do with no
   other signal at all. Grade with `python -m tsubasa.dev kanagate --all`.
   ⚠ **`rank()` and `best()` do different jobs.** A loanword like `ブラッククローバー` /
   `Black Clover` scores 0.74 — it *ranks* first and is **not** auto-accepted. Ranking
   narrows candidates for the timing referee; `best()` only speaks when the answer is
   beyond argument.
4. ✅ **Alias table — BUILT 2026-09-08 (A7).** `tsubasa/naming/alias.py` +
   `tsubasa/data/aliases.json`, enumerated from Wikidata's own P31 work classes (CC0).
   34 of 345 real pairs (9.9%) were refused before it and **every one is English ↔
   romaji** (`Assassination Classroom`/`Ansatsu Kyoushitsu`, `Solo Leveling`/`Ore dake
   Level Up na Ken` …). **Ranking only** (`D6`) — see the semantics below. Gated by
   Probe G at 38.8% against a 15% kill threshold (`08-probes.md` §G2).

   🚨 **AMENDED BY THE BUILD — "three-way" was not buildable, and the shape that
   replaced it is better.** This line said *romaji ↔ Japanese ↔ **English***.
   ⛔ **Wikidata has no romaji field.** Probe A7/1, 40 anime-television-series rows:
   `ja` label **100%**, `en` label **100%**, `mul` label **0%**, English aliases
   **90%** — and the romaji is *inside those aliases*, mixed with abbreviations
   (`Eva`, `NGE`, `TTGL`), macron spellings (`Uchū Senkan Yamato`) and different
   English titles altogether:

   ```
   宇宙戦艦ヤマト        en: Space Battleship Yamato
                     ~ Uchū Senkan Yamato      <- the romaji
                     ~ Star Blazers            <- a DIFFERENT English title
   科学救助隊テクノボイジャー en: Thunderbirds 2086
                     ~ Kagaku Kyūjo Tai Techno Voyager
   ```

   ⭐ **So the row is one ENTITY and N NAMES, each tagged by script**, not three
   columns. It holds `Star Blazers`, which no romaji column could, and it is exactly
   what `D6`'s ranking-only ruling wants. ⚠ **Japanese aliases matter too**
   (`エヴァ`, `グレンラガン`) — a filename can use any of them, so the ja side is a
   set as well.

   🚨 **The safety property, and it is the whole design:** *both* titles must
   independently reach a **common** entity. A one-sided hit answers nothing — which
   is what stops `Eva` attaching Evangelion to anything Eva-shaped, the exact class
   of error that made Probe G resolve `ナルト` to a fish cake at 0.75.
   ⛔ **And it never returns DIFFERENT.** Wikidata gives a series and each of its
   seasons separate entity ids, so a non-intersection is an **absent answer, not a
   negative one** (`00-INDEX.md` Rule 2).

   ⛔ **Enumerated, never seeded from the answer key.** Searching per show would make
   the AniList-derived key the *selection function*, and the shipped row set would be
   AniList-derived even though every field is Wikidata's. Enumeration by P31 has no
   such thread — **113,845 entities in thirteen queries** — and the key stays what
   `02-data-model.md` says it is: the thing that **grades** coverage.
5. **Signature is a tiebreak, not a verdict.** 84 jimaku entries (0.8%) hold both
   `Toradora` and `Toradora!`; when only one candidate carries the key, pair it; when two
   share the key and differ in signature, prefer the exact one

**The semantics that changed:**

| Verdict | Was | Now |
| --- | --- | --- |
| SAME | pair | pair — and measured **0 wrong-show SAME** across 5,645 videos against a 116-show pool |
| UNSURE | arbitrate | arbitrate |
| **DIFFERENT** | drop | **drop only at library scale.** Below a fan-out budget (≤ 8 surviving candidates, the measured median) a DIFFERENT candidate is still *probed* by timing — because 9.9% of real pairs are DIFFERENT-by-title and correct |

⚠ **Episode-set overlap cannot replace the title ranking.** Measured (`08-probes.md`
§J4): with no title filter, 327 video clusters against 856 subtitle clusters produce
**60,161** candidate pairs sharing ≥ 3 episode numbers, of which 674 are the right show —
every 1–12 season looks like every other. Ranking stays primary; probing confirms.

### Stage 3 — structural constraints

Season **and** episode agree (never episode alone — 305 false pairs); duration hard-reject
(subtitle longer than the video, or shorter by > 15%); directory proximity as a score.
One `stat` and one container read.

### Stage 4 — timing: probe at CLUSTER level, confirm per pair

✅ **BUILT 2026-09-08 (A6, `D7`)** — `tsubasa/arbitrate.py`. The implementation reproduces
**all 104 of the probe's recorded clusters exactly**, and the threshold behaves as measured:
at ≥ 0.60, **24 of 44 correct kept and 0 of 60 wrong accepted**, wrong topping out at 0.50.

🚨 **Coherence is agreement with a COMMON REFERENCE, not a transitive chain.** A sliding
window groups offsets 666 ms apart because a chain of near-neighbours can span twice the
tolerance end to end; the measurement does not. That definition error disagreed with 4 of
the 104 clusters and was found only by requiring the code to reproduce every recorded value.

Files come in clusters — one release group's episodes share a `tokenize()` shape (97.0%
of the video corpus sits in clusters of ≥ 3). So:

1. **Probe** the top-ranked (video-cluster, subtitle-cluster) pairs with **two
   alignments** each (first and middle shared episode) — ~50 ms per alignment once the
   track is read
2. ⭐ **Coherence** = the share of a cluster's episode-matched pairs whose offsets agree
   within ±500 ms. Measured on 44 correct and 60 wrong clusters: **at ≥ 0.60, 24 of 44
   correct kept and 0 of 60 wrong accepted**; wrong clusters never exceed 0.50. This is
   the escalation band's **second signal**: a weak per-pair score (the Hulu 1.5–2.5×
   case) inside a coherent cluster is a correct pair; the same score alone is not
3. **Episode-set offset hypotheses** — `Blue Lock S2 25…38` vs jimaku `1…24` is a constant
   −24; range-start alignment yields a hypothesis set, one alignment confirms it, the
   remaining episodes pair by arithmetic and are *verified*, not searched
4. Every pair still gets its own verdict. Coherence lifts the band; it never writes a
   file by itself

### 🚨 WHAT MAY VOTE IN A CLUSTER — added 3b, 2026-09-09, by measurement

⛔ **Only a MEASURABLE fit is evidence.** Built without that rule, `sync()` fed every
aligned pair into the cluster, including the ones `Fit.measurable` says cannot be scored
at all. Measured on four episodes each carrying one correct subtitle and one wrong one:

| Fed to the clusterer | size | coherence | consensus |
| --- | --- | --- | --- |
| every measured pair | 7 | 🚨 **0.57 — below the 0.60 bar** | −2000 ms |
| ⭐ only **measurable** fits | 4 | **1.00** | **−2000 ms** |

**The failure is silent and it runs the wrong way:** a video's *rejected* candidates drag
the cluster under the bar, so it can no longer vouch for the correct pairs beside it — and
the pair that loses is exactly the weak-but-correct one in the 1.5–2.5× escalation band
this mechanism exists to rescue.

🚨 **`Fit.excess` was already zeroed for this reason** (*"a caller that reads `excess` and
nothing else must not be handed a confident number built out of one cue"*), and
`_own_offset` reads `single[0]`, which is not. ⭐ **When a value is deliberately neutered
for unmeasurable input, every other field derived from that same fit needs the same
question asked of it.**

⚠ **And the obvious alternative was measured and REJECTED.** *One alignment per episode*
suggests feeding the best-ranked candidate per video — but with identical names the rank
falls to its path tiebreak, so a wrong `.en.srt` sorts above the right `.ja.srt` and
best-per-video gives coherence **0.75 around the WRONG offset**. ⛔ **The candidate rank is
a hypothesis order, not a quality order.** Only the alignment says which is which, so only
the alignment may decide what counts as evidence.

---

## The three gates

| Gate | Asserts | Baseline |
| --- | --- | --- |
| **Parser gate** (`parsergate`) | union accounted-for does not regress; films are not failures; Western names reported **separately** | `parser-gate-baseline.json` |
| ⭐ **Title gate** (`titlegate`) | ✅ **BUILT A2b+.** An episode **MARKER** surviving in the series key, **and** its number being the one the parser extracted — the defect the parser gate cannot see, because it scores the UNION and the episode comes out right. ⚠ *Same-show key agreement* was measured and **rejected**: 21.6% of entries carry two scripts, so it would measure the corpus. Kept as an ungated trend line | `title-gate-baseline.json` — ⚠ a **CEILING**. **6.45% → 0.15%** at A2b+ |
| ⭐ **Pairing benchmark** (`test_vn_bench.py`, new) | **recall and precision on the 345 real pairs + fan-out on the 116-show pool.** Label noise excluded by name: `Tensei Kizoku, Kantei Skill…` (a different show in the folder) and `Still to Watch/` (a watch queue) | recorded at A5 |

> **The one number that matters:** of all pairs a human would call correct, what
> fraction is paired — and of the pairs produced, what fraction is wrong. Precision
> outranks recall; a wrong pair silently retimes a subtitle to the wrong episode.

⚠ Split by SHOW into dev / validation / SEALED before any of this — done (0a). Every
number above excludes the sealed slice; the split key folds ordinals and release tags so
one show cannot land in two slices across folders.

---

## What ships, what stays private

| Artefact | Ships? | Why |
| --- | --- | --- |
| parser patterns, normalisation rules, scheme inference | ✅ | own work product |
| **decoration vocabulary** (185 tokens) | ✅ | learned rule, re-derivable from a future crawl |
| **kana phonetic bridge** | ✅ | a rule, no data |
| Wikidata alias table (three-way) | ✅ | CC0 |
| `titles.jsonl` and any table mined from jimaku filenames | ⛔ | AniList/TMDB provenance; uploader filenames unruled — **local to Sonic's private build**, which is also the primary use case |

---

## What "perfect" can honestly mean

Not 100% episode extraction — ~8% of files legitimately have none. **Correct pairing**,
measured by the benchmark, on the sealed slice, opened once. The pipeline is designed so
no rung must be perfect: what one rung cannot decide, a costlier and more reliable rung
does. Perfection is a property of the ladder.

## Related

`CORPUS-OPPORTUNITIES.md` — the eight probes behind §Stage 2 and §Stage 4 ·
`08-probes.md` §J1, §J4 · `12-alignment.md` — the referee ·
`02-data-model.md` — the alias table and its provenance
