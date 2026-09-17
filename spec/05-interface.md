---
type: spec
title: tsubasa — Interface
desc: The ruled CLI output, the library API surasura consumes, and the naming, dedupe and trash rules.
date: 2026-09-08
---

# 05 — Interface

⭐ **Library-first.** The importable API is the product; the CLI is a thin wrapper over
it. This follows necessarily from surasura consuming tsubasa as a module.

---

## The CLI output — RULED, do not redesign

Sonic ruled this shape. Three properties are load-bearing.

```
tsubasa  ~/Anime/Katainaka S2                    24 videos · 26 subtitles

  ✗  04   [shincaps] Katainaka - 04 (AT-X).srt              REFUSED
          no subtitle track; on the audio the first 3:42 want a different
          offset (about +10 s) — a broadcast cut. The streaming release's
          subtitle will pair.

  ✓  01   片田舎のおっさん S02E01.ass      →  Katainaka no Ossan S2 - 01.ja.ass
          +0.13s          96% match · locked · holds throughout
  ✓  02   [Erai-raws] ... - 02.ass         →  Katainaka no Ossan S2 - 02.ja.ass
          +0.12s          95% match · locked · holds throughout
  ⚑  03   [shincaps] ... - 03 (AT-X).srt   →  Katainaka no Ossan S2 - 03.ja.srt
          -33.07 / -42.96 @3:18   CUT 9.9s
                          91% match · strong · 2 segments

  2 subtitles superseded → trash

  23 synced · 1 refused · 3.1 s
```

| Property | Why it is not negotiable |
| --- | --- |
| **Refusals and errors first** | The one thing needing attention must not sit below 23 successes |
| **Evidence on every line** | `96% match · locked`, never a bare tick |
| **`old → new` shown** | The user sees what happened to their folder before trusting it |

### The confidence words

Sonic ruled `96% match · [VERDICT]`. **Match percentage is the human-readable number** —
it means 96% of reference lines found a subtitle line within a third of a second. The
word carries the chance-adjusted judgement the percentage alone cannot.

| Word | Behind it |
| --- | --- |
| ⭐ **locked** | ≥ 4× the random baseline. 🚨 **Was `certain` until 2026-09-09** — it is a SUBSTRING of `uncertain`, so the weakest word this tool writes contained the strongest, re-arming `LEDGER.md` §Interface's GUI defect for any consumer that substring-matches. Found by an adversarial pass; Sonic ruled the swap. ⭐ `locked` is his own word for the outcome — *"every part of the episode locks in well"*. ⛔ **The four words must stay mutually non-substring** — enforced by `test_the_confidence_vocabulary_is_mutually_NON_SUBSTRING` |
| **strong** | 3–4× |
| **fair** | 2.5–3× |
| ⚠️ **uncertain** | **1.5–2.5× — ESCALATE, do not refuse.** Written only when a second signal lifts it, and it keeps this word rather than *fair*: the evidence that carried it is the cluster's agreement, not its own score |
| *refused* | below 1.5× — **not written.** ⚠ Not a confidence word: a refusal carries **no word at all** (`LEDGER.md` §Interface) |

> 🚨 **AMENDED 2026-09-09 AT B8 — the bottom two rows said 2.0.** They predated the
> escalation recorded three paragraphs below them **in this same file**, which widened the
> band to **1.5–2.5 escalate / < 1.5 refuse**; `12-alignment.md` §4, the build authority for
> Track B, has cited the wide band since. Two of the three measured English pairs
> (1.70× · 1.72×) are refused outright by the stale reading **while being correct**. The
> shipped code is built to the wide band and `test_the_band_is_the_WIDE_one_and_not_the_stale_word_table`
> pins it. ⭐ **This is the file the handoff named as where stale prose would hide, and it
> was.**

### 🚨 The verdict is a BAND, not a line — measured, not argued

⛔ **Do not implement a single 2.5× threshold.** Measured across **364 cross-platform
pairs**, that line **refuses 57 of them — 16% — while they are correct.**

| Platform pair | n | median |
| --- | --- | --- |
| Amazon / Netflix | 299 | **4.54** |
| Amazon / Hulu | 37 | **2.36** |
| 🚨 **Hulu / Netflix** | 27 | **1.58** |

**Netflix and Amazon evidently license the same Japanese caption track** — their pairs are
near-duplicates. **Hulu commissions its own transcription**, which is genuine independent
authoring, and the anime-calibrated threshold rejects it.

**The rule:**

| Excess over chance | Action |
| --- | --- |
| **≥ 2.5×** | Accept |
| ⚠️ **1.5 – 2.5×** | **Escalate to a second signal** — VAD, cue-*range* matching, or duration. Only refuse if that also fails |
| **< 1.5×** | Refuse |

### 🚨 The second signal is STRUCTURAL, not a refinement

**Widened 2026-09-07 after the first non-Japanese data.** Three Manifest episodes
(Netflix vs Amazon, English, cue counts 944/945 · 948/944 · 994/975 — unambiguously
correct) scored **1.72× · 1.70× · 2.12×**. All three would be refused at 2.5, two at 2.0.

⛔ **And the bands overlap:** correct English pairs span **1.70–2.12×** while *wrong* pairs
span **1.37–1.95×**. A correct English pair scores **below** a wrong anime pair.

> **No single number separates correct from incorrect once content types mix.**

Likely cause: English subtitles carry more cues (≈950 vs ≈600–800 Japanese), so density
lifts the chance baseline and depresses the ratio.

⛔ **Any design that ships a single threshold reproduces this defect.** The escalation rung
is load-bearing.

⚠ **"Different platform" is NOT a proxy for independent authoring** — it depends whether
that service licensed a caption track or paid for a new one. Three proxies have already
failed: different uploader, live-action vs anime, and different platform. **Do not add a
fourth; use the band.**

Full data and derivation: `LEDGER.md` §Logic. Raw scores:
`tsubasa-corpus/_work/pair_calibration.json`.

⚠ **Never show the raw multiple in the default output.** *"4.6× chance"* is the internal
decision statistic and means nothing to a person. It belongs in `--verbose` and the JSON,
because that is what a bug report needs.

### Other output modes

| Flag | Behaviour |
| --- | --- |
| `--json` | The same structure the library returns. NDJSON per pair |
| `--dry-run` | Every intended action printed, **nothing written, nothing trashed** |
| `--verbose` | Adds raw multiples, chance levels, per-bucket timeline |

---

## The GUI — RULED 2026-09-10, do not redesign

`python -m tsubasa.gui`. RUNBOOK 3d. Three mechanisms were built as real windows and
captured at 10 and 24 episodes; Sonic ruled the **table**:

> *"Table is best. Cleanest and easiest to digest."*
> *"Auto-run on drop unless setting is toggled. Write without confirm unless reckless
> toggled in settings."*
> *"The window must look clean as it does, and the settings organized but the settings
> would likely be powerful for various features."*

```
 Folder [ D:/Anime/片田舎のおっさん、剣聖になる S2      ]  Browse…  Sync  ☐ Dry run  ⚙

  ✗  08  [Erai-raws] Yomi no Tsugai - 08 [10…   —      -11.08s          REFUSED
  !  04  [SubsPlease] Yomi no Tsugai - 04 (1…   —      —                ERROR
  ✓  01  黄泉のツガイ.S01E01.WEBRip.ABEMA.ja…   —      -0.32s           93% match · locked
  ⚑  03  [shincaps] Yomi no Tsugai - 03 (AT-…   —      -32.83 / -43.02  53% match · strong

  CONFIDENT   ep 01   黄泉のツガイ.S01E01.WEBRip.ABEMA.ja[cc].srt
  (dry run — nothing was written)
  reference: track 0 (S_TEXT/ASS, jpn, 323 cues) · 5.26× chance · runtime held · language ja

  ✓ 4 would sync   ⚑ 2 repaired   ✗ 1 refused   ! 1 error      1 note   8 files looked at
```

| Property | Why it is not negotiable |
| --- | --- |
| **Refusals and errors first** | The same rule the CLI output is built on, and held **incrementally** — a non-confident row is inserted at index 0 as it arrives, so the ordering cannot be lost by a sort somebody deletes |
| ⭐ **The counts strip PARTITIONS** | `clean + cut + refused + errored + unknown` is the row count. ⛔ `cut` is a SUBSET of `confident`; printing both from `confident` made ten files read as eleven |
| ⭐ **The right of the strip may never restate the counts** | One window read `✓ 4 would sync` beside `6 would sync`. Both correct, together incoherent |
| **`would sync`, never `synced`, on a dry run** | Different claims about the user's folder |
| ⛔ **An unmeasured row shows no offset** | A file with zero cues displayed `+0.00s`. Same defect as the CLI's `-0.00s` at 3c |
| **Cell text is fitted by MEASURING the font** | ttk clips at the column edge with no gap, so a filename ran into the next column's em-dash and read as one token |
| ⛔ **No doctrine marker or markdown reaches a label** | ⭐/⛔/⚠ and backticks are for this project's documents. A Tk label renders them literally, and a hollow star mid-sentence reads as a typo. Enforced by a static check over the source **and** a runtime twin over the loaded schema |

### The settings — organized, and the only place options live

Four groups, **generated from `settings.SCHEMA`**. ⛔ The window does not know the name of
a single option: `doctrine/architecture` records a control whose identifier is missing
rendering perfectly and being *completely inert*, three times in one build, and a settings
panel written by hand is that defect with a checkbox on it.

| Group | Holds |
| --- | --- |
| **Running** | dry run · search sub-folders · remember what is already synced · keep the raw numbers |
| **Output** | subtitles from elsewhere · write elsewhere · keep every candidate |
| **Window** | auto-run on drop *(on)* · reopen on the last folder *(on)* |
| ⭐ **Reckless** | Off by default. **While any of these is on, tsubasa asks before it writes.** Today: turning renaming off, which writes the new timing **over the file the user already had** rather than beside it |

⚠ **`--force` can never appear on the folder path.** `sync()` refuses it — *writing the
best of several REFUSED candidates* — so `argv_for` refuses it too, in the same words,
before anything is spawned. So does `--out` with renaming off.

## The library API

surasura's likely call: subtitles sitting in a folder **alongside lots of `.txt` and
other junk**, videos in a separate location, results consumed programmatically as part of
a content-creation pipeline.

Three constraints that follow:

1. ⛔ **Never assumes it owns a directory.** Takes paths *or* iterables of paths
2. ⛔ **Ignores non-subtitle files silently.** Junk is expected input, not an error
3. ⛔ **Returns structured results. Prints nothing. Writes nothing unless told**

```python
from tsubasa import scan, sync, align, Result

# Discovery — filenames and stat ONLY. ⛔ Opens nothing. See the note below.
# Returns CANDIDATE SETS per video, ranked; never a final pair, never writes.
cands = scan(videos="/media/anime/s2", subs="/data/subs")
cands = scan(videos=[...paths...], subs=[...paths...])   # explicit lists
cands = scan("/media/anime/s2")                          # same folder for both

# Alignment — probes clusters, aligns, decides. Still writes nothing.
results: list[Result] = sync(cands, vad=True)

# Application — the ONLY call that touches the filesystem.
sync(cands, write=True, rename=True, dedupe=True)

# The primitive itself, for hato and for anyone with two cue lists.
fit = align(reference_starts, subtitle_starts, duration)   # -> segments, per-bucket rows, excess
```

⚠ **Changed 2026-09-08:** `scan()` used to promise final pairs. Pairing is decided by
timing (`09-corpus-strategy.md` §Stage 4), so `scan()` returns *hypotheses* and `sync()`
returns the pairs it made. **These four shapes — the parser, discovery, the sidecar
reader, `align()` — freeze at RUNBOOK 3b; hato pins them.**

### 🚨 AMENDED 2026-09-09 AT 3b — this file and the RUNBOOK disagreed about `scan()`

This file's comment read *"filenames, stat and the container INDEX only (30 KB per
MKV)"*; `RUNBOOK.md` step 3b said `scan()` returns candidate sets **"(no media I/O)"**.
Those are different contracts, and **30 KB per MKV is the Cues-indexed TIMING read** (1d
measured it at 0.087 s median), not a header peek — so on a 1,500-file library the two
readings differ by minutes of work done before a single decision is made.

⭐ **Built to the tighter one: `scan()` opens nothing.** Three reasons, in order:

1. `sync()` must read each video's track timing anyway, so a read in `scan()` is either
   **duplicated or cached**, and both are worse than not doing it.
2. `scan()` is the half a caller is invited to run on a whole library to see what is
   there. A contract that says *"free"* and costs two minutes is the wrong shape.
3. It is the **checkable** claim. `test_scan_opens_no_file_inside_the_tree_it_was_given`
   makes `open()` raise for any path inside the scanned tree, so the next person who adds
   a container read here finds out immediately. *"Only reads about 30 KB"* is not a
   contract anything can enforce.

⚠ **The contract is *nothing inside the tree it was given*, not *nothing at all*** — and
the looser wording was in the code until an adversarial pass spied on a real scan and
measured **0 opens inside the tree, 2 outside it**: the 4.2 MB gzipped alias table and the
decoration vocabulary, both under `tsubasa/data/`, loaded once per process by the identity
ranking. ⭐ **That is the program's own weight, not the user's media**, and the argument
for the tighter reading was always about per-file reads that scale with the library.

⚠ **The visible consequence, named:** without runtimes the movie path cannot use the
duration veto or the runtime tiebreak, so a set of films it cannot separate on name and
folder alone is **refused rather than guessed at** (Rule 2, working). `sync()` re-runs the
same `movies.pair_movies()` **with** the durations it has opened, and that second call is
the one that decides. One authority called twice with different evidence — never two
implementations.

⭐ **`Scan.films` is therefore PROVISIONAL and says so.** A caller wanting the final film
pairing calls `sync()`.

### `Result` carries

`video` · `subtitle` · `outcome` (CONFIDENT / REFUSED / ERROR) · `segments`
(offset per split, with the quiet-gap boundary where one exists) · `match_rate` ·
`excess_over_chance` · `verdict_word` · `reason` (populated on REFUSED and ERROR) ·
`holds_throughout` · `cluster_coherence` (when a cluster probe ran) · `dropped_in_gap`
(cues removed under `D9`) · `reference_kind` (text track / bitmap track / speech mask) ·
`output_path` (when written) · `superseded` (paths trashed)

**`reason` is never empty on a non-confident outcome.** See `03-permissions.md`
§hand-back.

⭐ **Built 2026-09-09 at 3b, and it also carries** — added, never renamed, because the
list above is what hato is written against:

| Also on `Result` | Why it had to exist |
| --- | --- |
| `lang` · `lang_tag` | The structured language field this file already requires, split into the **resolved code** and **what the file said** — `.jpn.` and `ja-jp` must dedupe together while the output name preserves what the user's other tooling expects |
| `raw_excess` | `excess_over_chance` is **zero** when the input was too thin to mean anything, which is the number the decision used. `--verbose` and every bug report need the un-zeroed one; it is what reads 5.15× on a one-cue subtitle |
| `runtime_check` | `held` / `failed` / `weak` / **`absent`**. ⚠ `holds_throughout` is `True` when every bucket was too thin to speak, and this is the only field that tells those apart — the adversarial pass found a `locked` verdict written off a walk that evaluated nothing |
| `dropped_before_zero` | The whitelist permits **two** removals and `dropped_in_gap` counts one of them. A cue dropped for ending before the video starts is not a `D9` drop and must not be reported as one |
| `reference` | Which track was aligned against, and its codec, in words. `reference_kind` is one of three labels; this is what a bug report needs |
| `forced` | ⚠ A forced write is reported as **REFUSED** and it does write. Nothing else on the object distinguishes it from a refusal that wrote nothing |
| `notes` | Everything a person must be told that is not a refusal — a name that had to be trimmed, a switch that made the read 35× slower |
| `match_percent` · `offset` | Derived, no storage. `match_percent` is the *96% match* this file rules; `offset` is `segments[0][1]` and is named for what it returns — ⚠ **a cut file has more than one** |

🚨 **Three invariants are enforced in the constructor, not documented.** `Result` has a
public constructor that hato and the CLI both call, so a `Result` can exist that no
`Verdict` ever produced: a non-confident outcome with no reason **raises**, a
non-confident outcome carrying a confidence word **raises** (`LEDGER.md` §Interface's GUI
defect), and an `ERROR` carrying an `output_path` **raises** — ERROR means never measured,
so there was no offset to have written.

### ⭐ For code built on tsubasa — ADDED 2026-09-16, never renamed

Two consumers were checked against the shipped API before 0.1.0: **hato** (spec only) and
**Anki Miner** (a GPL-3.0 PyQt app that freezes with PyInstaller). Both were found
reaching into internals for answers the library already had. These name them. ⛔ **All
additive:** nothing above changed shape, and hato's four pinned shapes are untouched.

```python
import tsubasa

check = tsubasa.self_check()                  # is this install whole?
video.title, video.season, video.episode      # a discovered video, read
video.episode_candidates                      # every episode the parsers proposed
subtitle.lang, subtitle.lang_tag              # "ja" and "jpn" — resolved, and as written
scan.unpaired(lang="ja")                      # videos with no JAPANESE subtitle

r = tsubasa.sync_to_reference(sub, other_sub) # a subtitle against a subtitle. Writes nothing
out = tsubasa.render(r)                       # the retimed bytes, original encoding
side = tsubasa.parse_subtitle_name("Show.ja[cc].srt")   # the sidecar reader, by name
```

| Added | Why it had to exist |
| --- | --- |
| `self_check()` → `SelfCheck` | 🚨 **Both data files fail open, so a broken install is silent.** Measured: a PyInstaller build of a plain `import tsubasa` ran with **0 alias entries**, exit 0. `ok` answers *is anything silently worse than it should be* — each table against the size its **own header declares**, so a truncated table fails where a floor would pass it. ffmpeg and the optional parsers are reported in `notes` and never counted: they fail loudly when needed |
| `Item.season` · `episode` · `episode_candidates` | Derived from `key`, never stored. ⛔ `13.5` stays a float — hato's `06-edge-cases.md` matches half episodes literally |
| `Item.lang` · `lang_tag` | The structured language field, on a *discovered* subtitle — `Result` had it and `Scan` did not. None for a video |
| `Scan.unpaired(lang=)` | 🚨 **Language-blind, a video carrying only an English subtitle read as covered**, so a Japanese fetcher never fetched for it. An untagged name is `und` and counts as no language (hato's rule). An unrecognised tag **raises** — resolving it to `und` would mark the whole library unpaired |
| `sync_to_reference(subtitle, reference)` | A subtitle against another subtitle FILE. ⭐ The same `measure` → `judge` → verdict as a video's track — the file becomes a `Reference` of kind `text track`, which is the population the bands were fitted on. **Writes nothing.** 🚨 A partial reference is judged on the part it covers — see its docstring and read `runtime_check` |
| `render(result, force=False)` → `Rendered` | The retimed bytes for any `Result`, through the renderer `sync(write=True)` uses: original encoding, cut-straddling cues anchored to their start, both whitelisted removals counted. ⛔ A path the caller names is where `os.replace` destroys a file, so this returns bytes and the caller writes |
| `parse_subtitle_name` · `Sidecar` | The sidecar reader was already one of hato's four frozen shapes, reachable only as `tsubasa.sidecar.parse` |
| `tsubasa/__pyinstaller/` | Registered under the `pyinstaller40` entry point, so an application freezing tsubasa changes nothing in its own build. The same build that carried 0 entries carried 221,258. ⚠ **PyInstaller only** — `self_check()` is how any other freezer finds out |

---

## Naming and dedupe

The point of renaming is that **media players auto-load a subtitle matching the video's
basename.** That is what "clean" means operationally.

### The rule

> Keep **one subtitle per (video × language)**. Name it exactly
> `<video-basename>.<lang>.<ext>`. Every other candidate for that slot goes to trash.

### Ranking, when there are several candidates

Sonic's note: *"most people won't have multiple subs of the same show… I just have it
here as an extra test to make this incredibly robust."* So this is a **robustness
backstop, not a core feature** — implement it correctly, do not over-invest.

1. Aligned confidently — **a refused candidate never wins**
2. Not SDH, unless SDH is the only one
3. Higher cue count and wider runtime coverage
4. Fewer segments needed — an uncut source is cleaner than a repaired broadcast
5. Tie → prefer the one already matching the video's name

### 🚨 THE SLOT DECIDES ITS WINNER. ONLY THE RUN DECIDES WHAT IS THROWN AWAY

**Added 3b, 2026-09-09, after an ordinary library lost every subtitle it had.**

The five rules above decide **one (video × language) slot** from the candidates it was
given, and they do that correctly. But the loser of one slot is routinely the **winner of
another** — the episode index offers each video every same-numbered subtitle in the walk,
which is exactly what it is for. Measured on two shows using bare episode numbers, on
default flags:

```
summary: '2 synced'
LOST from the library: Alpha/01.ja.srt  Alpha/02.ja.srt
                       Bravo/01.ja.srt  Bravo/02.ja.srt
```

⛔ **Every layer was individually right**, and the defect lived in the gap between them —
which is why no unit check and no mutant reached it. `sync()` is the only layer that sees
the whole run, so the cross-slot question is its own:

| Rule | Why |
| --- | --- |
| ⭐ **A file that any slot WRITES is never superseded by another slot** | This is what makes *"REFUSED → left untouched, reason stated"* (`03-permissions.md`) literally true |
| 🚨 **A file two slots would both write belongs to NEITHER** — both refused, order-independently | One subtitle cannot be two videos' answer and there is no basis to prefer either. ⛔ And `apply._render` re-reads the source at write time — correctly, *the file always wins* — so two slots writing from one source means the second retimes the bytes the first just shifted: **−4.0 s applied for a true offset of −2.0 s, both reported CONFIDENT** |
| ⭐ **Nothing is trashed for a slot that wrote nothing** | *"Write first, trash second"* is an **order**, not a condition; with every write failing the trash ran anyway and left the user with neither file |
| ⭐ **On the explicit path nothing is ever superseded** | The user asserted every pair. Dedupe still decides which one is *written* — two writes to one name is data loss — but not what is thrown away |

⚠ **`--out` MIRRORS THE LIBRARY'S SHAPE**, and `sync()` is the layer that has to make that
true: `apply_plan` states the obligation and assigns it to its caller. Flattened, two
shows' `Season 1/01.mkv` produce **one** output file and the second reports CONFIDENT.
⛔ **`--out` with `--no-rename` is a contradiction and is refused** — in-place and
somewhere-else cannot both hold.

### `--keep-all`

Writes every candidate as `<video>.<lang>.<tag>.<ext>` and **trashes nothing.**

### ⭐ Language must be a STRUCTURED FIELD at launch — the filter ships later

**Ruled 2026-09-07.** Per-language syncing (`--lang ja`) is an **evolution** feature, but
the field it filters on is **launch**, because the output name already depends on it.

⛔ **Do not store language as an opaque filename suffix.** Parse it into a real field on
`Result`, resolved in this order:

1. **Filename tags** — `.en.` `.ja.` `.jpn.` `ja-jp` `[cc]` `[sdh]` `.forced.`
2. **Container track metadata** — `tags.language` on the subtitle stream
3. **Script detection from content** — CJK vs Latin vs Cyrillic vs Arabic vs Hangul.
   Cheap, and reliable for the coarse case where no tag exists

With the field present, `--lang` is a one-line filter later. **Without it, language is a
string re-derived at every call site** — pairing, dedupe, naming and the API all have to
change. An afternoon now; a refactor later.

⚠ Keep the **detected** language and the **original tag** separately. A file tagged
`ja-jp` and a file tagged `.jpn.` are the same language and must dedupe together, but the
output name should preserve what the user's other tooling expects.

> 🚨 **THIS PARAGRAPH AND THE `[cc]` / `[sdh]` / `ja-jp` ENTRIES IN THE LIST ABOVE WERE
> NOT IMPLEMENTED UNTIL 2026-09-09, AND NOTHING NOTICED FOR TWO STEPS.**
> `sidecar.parse_path` read only DOT-separated tokens, so `.ja[cc].srt`, `.en[cc].srt`,
> `.ja-jp[sdh].srt` and `.ja-jp.srt` — the forms ABEMA, Netflix and Amazon write — all
> resolved to `und`. ⛔ **Two different languages then shared one slot and dedupe trashed
> one of them.**
>
> ⭐ **Measured: 4,677 of 40,572 real corpus subtitle filenames (11.53%) read `und` while
> carrying a code the file plainly declared. After the fix: 8** — every one a shape the
> guard refuses on purpose (`ja[no-sdh]`, `ja[cc][no furigana]`), because a filename is
> full of brackets that are not flags and turning `[E27C3F25]` into English is worse than
> reading `und`.
>
> 🚨 **AND ZERO SLOTS IN THAT CORPUS COULD EVER HAVE EXHIBITED THE LOSS**, because it is
> Japanese-only — no episode has both a `ja[cc]` and an `en[cc]`. It took the end-to-end
> benchmark (RUNBOOK 3c-0) constructing a bilingual library to see it at all. ⭐ That is
> `07-test-plan.md`'s own rule arriving from the other side: a **real-data** pass is blind
> to a defect the real data cannot contain.

---

## Trash, never delete

⭐ OS-native trash via `send2trash` (MIT), falling back to a local `.tsubasa-trash/`
where the OS has none — network shares, some Linux configurations.

**Recoverable in the way the user already knows.** Nothing this tool does may be
unrecoverable.

---

## ⭐ Explicit pairing — the escape hatch

**Ruled 2026-09-07.** *"I would also want the option to explicitly match the subs as a mode
option… for anything that falls through the cracks."*

```bash
tsubasa --pair VIDEO SUBTITLE            # one explicit pair
tsubasa --pair A.mkv A.srt --pair B.mkv B.srt    # repeatable
tsubasa --pairs pairs.json               # a manifest, for many
```

**Cost: near zero.** Pairing and alignment are already separate stages, so this is simply a
different entry point that skips stage 1. The library API takes it natively:

```python
sync([(video, subtitle), ...], write=True)
```

### 🚨 Explicit pairing skips the PAIRER, never the VERDICT

⛔ **The timing check still runs, and it can still refuse.** The user is asserting *"these
two files go together"* — they are **not** asserting *"the alignment is findable."* Those
are different claims, and a subtitle for a different cut of the same film satisfies the
first while failing the second.

| Outcome | Behaviour |
| --- | --- |
| Timing agrees | Written normally |
| Timing refuses | ⛔ **Refused, with the reason.** The pairing was accepted; the alignment was not |
| `--force` | Writes anyway. The only way to override, and it must be typed deliberately |

**Why this matters:** the whole value of the tool is that it will not produce a confidently
wrong file. An explicit-pair flag that bypassed the verdict would be the one command
capable of doing exactly that.

---

## Two-folder mode

```bash
tsubasa <videos-dir>                      # subs in the same place
tsubasa <videos-dir> --subs <subs-dir>    # split
```

Both recursive by default. `--no-recurse` opts out.

---

## The two banked features

### `--merge-lines` — off by default

Joins cues that are one sentence split across several for reading comfort: continuation
arrows (`→`), mid-sentence breaks, dialogue dashes. **For analysis you want whole
sentences.**

Pure cue-list transform. Depends only on the parser — independent of pairing and
alignment entirely.

### The cleanup extension point — shell only at launch

A named registry, a no-op default, and **one worked example** so the shape is proven.
Furigana stripping and the rest land when Sonic supplies the use case. surasura calls it
through the same API.

```python
from tsubasa.cleanup import register, apply

@register("strip-furigana")
def _(cues): ...

cues = apply(cues, ["strip-furigana"])
```

⛔ **Do not build transforms at launch.** Build the shell, prove it with one example,
stop.
