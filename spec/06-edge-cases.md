---
type: spec
title: tsubasa — Edge Cases
desc: Every edge case by section, each with a defined behaviour. Entries marked REGRESSION already work in subsync and must not break; entries marked NEW are unhandled today.
date: 2026-09-08
---

# 06 — Edge Cases

> **A shrug is not a behaviour.** Every row below has a defined outcome.

**Legend:** `REG` = already handled in `subsync`, must not regress · `NEW` = unhandled
today · 🚨 = has already caused a real defect, or would cause a silent wrong answer.

---

## §1 — Episode number parsing

### 1.1 Already handled — regression suite

| Case | Behaviour |
| --- | --- |
| `1080p`, `720p`, `2160p`, `1440x1080`, `3840x2160` | `REG` Stripped as noise before episode patterns run |
| `x264`, `x265`, `HEVC`, `AVC`, `AAC`, `FLAC`, `Opus`, `MPEG-2` | `REG` Stripped |
| `10bit`, `Hi10P`, `Ma10p`, `BD`, `BDRip`, `WEB-DL`, `WEBRip`, `TV` | `REG` Stripped |
| CRC32 tags `[1EAFC83B]`, `[E27C3F25]` | `REG` Stripped for parsing — but now **captured as an identity key** |
| `- 51v2` | `REG` Reads as episode **51**, not 512 |
| `Code_Geass_05_(...)` — underscores | `REG` Underscores are separators |
| `Gurren.Lagann.-.01` — dots | `REG` Dots are separators |
| `Code Geass R1 1x05` | `REG` `SxE` notation |
| `... 3rd Season [53][Ma10p_1080p]` | `REG` A bracket of **pure digits** is an episode number |
| `NARUTO...疾風伝.S06E01.第113話` | `REG` `第N話` **outranks** a platform's `S##E##` → episode 113 |

### 1.2 🚨 Known defect to fix at launch

| Case | Behaviour |
| --- | --- |
| 🚨 **Episodes ≥ 1000** | `NEW` ✅ **VERIFIED 2026-09-07 against real files.** The failure is **double**: `[SubsPlease] One Piece - 1121` parses to `ep=None` **and** the number is absorbed into the series slug as `onepiece1121`, so it cannot match other One Piece episodes by title either. `- 999` parses fine; the boundary is exactly 999/1000. `Detective Conan - 1100` fails identically. Widen to `(\d{1,4})` and re-tune the noise strippers so `1080` is still excluded |
| ✅ Title that IS a number, with an episode | `86 - Eighty Six - 03v2` **parses correctly** — `ep=3`, slug `86eightysix`. The episode pattern matches before the title-number problem bites. Keep the test; the case is less dangerous than feared |
| 🚨 **Bare `E##`** — `Ascendance of a Bookworm - E01`, `ヒロイック・エイジ.E25.Bandai.ja` | `NEW` ✅ **VERIFIED 2026-09-08 on the current code.** The third most common scheme on jimaku; 14.7% of series keys carry the token; 77.2% of our unknowns. `Kamen Rider 555 - E30` returns **555**. One pattern below `S##E##`; measured to take catalogue unknowns from 10.6% to 2.4% |
| 🚨 **Browser-collision suffix ` (N)`** — `Bleach - 162 (2).sup`, `Evangelion - 01 - … (10).ass` | `NEW` ✅ **VERIFIED 2026-09-08.** Sonic's own library shape (language tracks extracted from one video): the last bracket-digit wins, so **2,108 of 2,602 files got the wrong episode**. Strip a trailing ` (N)`, N ≤ 99, before parsing; measured to 0 |
| 🚨 **Full-width episode markers** `（０１）`, `＃０１`, `第０１話` | `NEW` 6.2% of the catalogue. The parser folds width; **scheme inference did not** — `tokenize()` ate the digits as a separator. Fold inside `tokenize()` |
| 🚨 **A release year as the episode** — `Inception (2010)`, `君を愛したひとりの僕へ.2022` | `REG` fixed 2026-09-08 by the builder; kept as a named case. Two films keying to `(None, 2010)` bucket a library under one fabricated episode |

### 1.3 New cases to handle

| Case | Behaviour |
| --- | --- |
| **Episode 0** — OVAs, prologues | Valid episode. ⚠ `0` is falsy — must be `is not None`, never truthiness |
| **Half episodes** `13.5`, `7.5` | Parse as a decimal episode key. Pairs only with a video carrying the same key |
| `S00E01` — specials season | Season 0 is a real season, distinct from "no season" |
| **Double episodes** `01-02`, `1&2`, `01+02` | Pairs with **either** episode's video; the timing decides which |
| **Batch ranges** `01~12` | ⛔ Refuse to assign an episode. Report as unmatched with the reason |
| 🚨 **TWO SHOWS in one file** — `RinjouS01EP10_(1st_part)_&_AibouS06EP11_(2nd_part)` | `NEW` **Found in the real corpus.** Two series, two seasons, two episode numbers, one subtitle. Every parser returns one answer or none. ⛔ **Detect the conjunction and REFUSE** — picking a half silently retimes to the wrong show |
| `Part 1`, `Pt2`, `Cour 2` | Season-level, never episode-level |
| Leading zeros `007` vs `7` | Normalized to integer — they are the same episode |
| 🚨 **Hyphen with NO separating space** — `tsukaiyou-01` | `NEW` **Found by Probe A.** Today's pattern needs `[\s._]-`, so a hyphen attached directly to a word is missed. A real and common form |
| 🚨 **Date-stamped broadcast recordings** — `(2012.08.25)`, `2012-08-07 …` | `NEW` **Found by Probe A.** No episode number exists; the date IS the identifier. Must pair on date, or refuse cleanly — never parse `08` as an episode |
| **Films, specials, Director's Cut, Theatrical Version, Making-of, `特別編`** | `NEW` These **correctly** have no episode number. ⛔ Must not be counted as parse failures — they are a different content class, not a defect |
| Episode number in the **folder**, not the file (`S01/01.srt`) | Folder name participates in parsing when the filename yields nothing |
| **No episode number at all** — a film | Valid. Pairs by title + duration, never by number |
| `5.1`, `7.1`, `DDP5.1`, `DTS-HD`, `TrueHD`, `Atmos`, `EAC3` | Stripped as noise |
| `AV1`, `VP9` | ⚠ **Not in today's noise list.** Add |
| 🚨 **Group as a SUFFIX** — `...H.264-MagicStar` | `NEW` **33% of 904 Western release names.** Today's parser only strips a **leading** `[Group]`, which is 1% there and dominant in anime. **Both cultures must be handled** |
| 🚨 **Audio tags containing dots** — `DDP5.1`, `AAC2.0`, `DD+5.1` | `NEW` **9% of Western names**, inside dot-separated filenames, adjacent to patterns that read trailing numbers as episodes. The concrete false-positive risk |
| **Edition tags** — `REPACK`, `PROPER`, `INTERNAL`, `EXTENDED`, `UNCUT`, `LIMITED` | `NEW` 3% of Western names. Absent from anime. Strip as noise |
| **Platform tags** — `NF`, `AMZN`, `DSNP`, `HMAX`, `ATVP` | `NEW` 5% of Western names. Strip for parsing, **retain** — they identify the source service |
| **Whole-season packs** — `Complete.Season.1` | `NEW` No single episode. Refuse cleanly rather than parsing `1` |
| `H.264`, `H265` | Stripped |
| Trailing bracket groups `[1080p-Raws]` | Only the **leading** bracket is a group name; trailing brackets are parsed, not stripped wholesale |
| Multiple brackets `[A][B]Name - 01[D][E]` | First bracket = group. Rest parsed for content |
| Malformed brackets `[Group [Sub] Name]`, `[Unclosed - 01` | ⛔ Must not crash and must not swallow the episode number |

---

## §2 — Series identity

### 2.1 🚨 Titles that ARE numbers

| Case | Behaviour |
| --- | --- |
| 🚨 `86` (Eighty-Six), `91 Days`, `07-Ghost`, `18if` | **No regex resolves these.** Per-folder scheme inference carries them (100% within-show unanimity measured on 6,734 shapes) — **from three files, never two**. A lone file → pair by timing arbitration alone |
| `5-toubun no Hanayome`, `3-gatsu no Lion`, `100-man no Inochi` | Leading number is part of the title. The **folder's dominant scheme** disambiguates |

### 2.2 🚨 Titles differing only by punctuation

| Case | Behaviour |
| --- | --- |
| 🚨 `Gintama` / `Gintama'` / `Gintama°` / `Gintama.` | **Real, distinct seasons.** The normalizer preserves the **trailing** punctuation as a signature — ⭐ **a TIEBREAK, never a verdict** (ruled 2026-09-08). 84 jimaku entries hold both `Toradora` and `Toradora!`; when only one candidate carries the key, pair it; when two share the key and differ in signature, prefer the exact one |
| `K-On!` / `K-On!!` · `New Game!` / `New Game!!` | Genuinely different seasons — the signature separates them **only when both are present** |
| `Steins;Gate` vs `Steins Gate` vs `Steins;Gate 0` | Same show / same show / **different show**. Internal punctuation carries nothing |
| `Fate/Zero`, `Fate/stay night` | Slashes are illegal in filenames; every release mangles them differently. Normalize all manglings to one form |
| `Yuru Camp△`, `K-On!`, `Re:Zero` | Punctuation preserved through normalization |

### 2.3 Romanisation and Unicode

| Case | Behaviour |
| --- | --- |
| 🚨 **NFC vs NFD** | **macOS stores NFD.** `が` is one codepoint on Linux, two on macOS — the same file compares unequal across platforms. **Normalize to NFC on every path, always** |
| Macrons `Tōkyō` / `Toukyou` / `Tokyo` / `Tohkyoh` | All fold to one key |
| Hepburn vs Kunrei — `shi`/`si`, `tsu`/`tu`, `ji`/`zi` | Fold |
| Diacritics `Pokémon` / `Pokemon` | Fold |
| Full-width `ＴＯＫＹＯ`, `１` | Fold to half-width |
| 🚨 **CJK unification** 剣 vs 劍 | Traditional/simplified variants of one character. Fold via a variant table — **required for Chinese support** |
| Katakana / hiragana / kanji for one title | Kept distinct in the slug; the index resolves cross-script aliases |
| `&` vs `and`, smart vs straight quotes | Fold |

### 2.4 Prefix and overlap traps

| Case | Behaviour |
| --- | --- |
| 🚨 **Naruto / Naruto Shippuuden** | **The slug must keep CJK.** Today's ASCII-only slug discards 疾風伝 — the discriminating information is in the filename and is being thrown away. ⚠ Keeping CJK makes `same_series()` **less permissive**, which must be re-tuned or Japanese-named files stop pairing |
| `Aria the Animation` / `the Natural` / `the Origination` | Three seasons, shared prefix. Suffix is discriminating |
| `Ace of Diamond` / `Diamond no Ace` | `REG` Same show, no shared prefix — substring-overlap test handles it |
| `Tongari Boushi no Memole` / `no Atelier` | `REG` Different shows sharing 15 characters — must **not** match |
| Season markers `2`, `II`, `S2`, `2nd Season`, `Zoku`, `Shin`, `Next`, `Final` | Normalized to a season integer where unambiguous |

---

## §3 — Filesystem and filenames

| Case | Behaviour |
| --- | --- |
| 🚨 **255-byte NAME_MAX** | CJK hits it at ~85 characters. On rename, **trim the stem to fit** and report the trim. Never let a rename fail silently |
| Newlines, quotes, backticks, `$` in filenames | Every path quoted, every subprocess arg passed as a list — **never through a shell** |
| Leading dash | Parses as a CLI flag. Always `--` before positional paths |
| Emoji, RTL override marks | Passed through byte-for-byte |
| 🚨 **Case sensitivity** | Linux case-sensitive; Windows/macOS not. `EP01.SRT` and `ep01.srt` are **one file** on two platforms and two on the third. Compare case-insensitively; preserve case on write |
| Windows reserved names `CON`, `NUL`, `COM1`, `PRN` | Cannot exist on Windows. On rename, suffix to avoid |
| Trailing dots/spaces | Windows silently strips them. Never generate them |
| `MAX_PATH` 260 on Windows | Use extended-length paths (`\\?\`) for all file operations |
| Symlinks, junctions, hardlinks | Resolve once, track by real path, **never process the same file twice** |
| 🚨 **Network shares (SMB/NFS)** | `os.replace` atomicity is **not guaranteed**. Detect and fall back to write-verify-rename with an explicit check |
| Read-only media | ⛔ Fail cleanly before doing any work, not halfway through a folder |
| 🚨 **Two instances on one folder** | Lockfile in the cache directory keyed on the target path. Second instance reports and exits |

---

## §3.4 — ⭐ DIRECTORY LAYOUTS — do not enumerate them, make layout irrelevant

Sonic named eight real-world shapes. **Enumerating them is the wrong design** — the ninth
would break it. Discovery is layout-agnostic and **proximity becomes a scoring signal, not
a constraint.**

### The layouts that must work

| # | Shape |
| --- | --- |
| 1 | `Library / Film Name / film + subs` — both in one folder |
| 2 | `Library / Film Name / film` **+** `…/Subs/` subfolder |
| 3 | `Library / Series Name / episodes + subs` |
| 4 | `Library / Series Name / S02 / episodes + subs` |
| 5 | A whole tree of **subs** ←→ a whole tree of **movies in their own folders** |
| 6 | Same, but movies **flat** in one directory |
| 7 | **A mix** of 5 and 6 |
| 8 | 🚨 **One folder containing subs, movies AND shows** — everything at once |

### The design

⛔ **No layout flag. No mode. The user declares nothing.**

1. **Walk everything.** Collect every video and every subtitle with its full path
2. **Score every plausible pairing** on: name match · episode number · **duration** ·
   **directory proximity** · then timing
3. **Proximity is a SIGNAL, never a rule.** Same folder scores highest, parent/sibling
   next, different tree contributes nothing — but never *disqualifies*, which is what makes
   layouts 5–7 work at all

⭐ **Movies and shows need no separate mode.** The discriminator falls out of parsing: a
name yielding an episode number takes the TV path, one that does not takes the movie path.
**Layout 8 is then not a special case** — it is the two paths running over one directory.

⚠ **Scale is the real constraint here, not logic.** A "gigantic media directory" makes this
O(videos × subtitles) if written naively. **Index by episode key and duration bucket
first** — see §4 and `02-data-model.md` on the 10× cost model. Rule 4 applies directly.

---

## §3.45 — ⭐ DURATION AS A PAIRING SIGNAL

**Sonic's observation, and it is a strong one:** *"you won't have a movie that is 1 hour
long and subs that are 1 hour 30 minutes."*

**Free, because the container is already probed** and a subtitle's last cue time is already
parsed. It earns its place three separate ways:

| Use | Why |
| --- | --- |
| ⭐ **Hard rejection** | A 90-minute subtitle cannot belong to a 60-minute video. Rejects before any timing work — the cheapest possible filter |
| 🚨 **Distinguishing CUTS** | `[Final Cut]` vs `[Theatrical]` slugs overlap at 0.52, above the 0.4 threshold, so `same_series()` **matches them today**. Their runtimes differ by minutes. **This is the fix for that trap** |
| **Ranking candidates** | Closest runtime wins among otherwise-equal candidates |

⚠ **Use a tolerance, not equality.** A subtitle's last cue precedes the credits, and
broadcast recordings carry CM breaks the release does not.

### 🚨 AMENDED BY MEASUREMENT AT A9 — this section was wrong twice

This paragraph used to read *"reject when the subtitle is LONGER than the video by a real
margin, **or shorter by more than ~15%**."* ⛔ **The short bound was not built, because it
was measured and it loses.**

| The short rule costs | The short rule catches |
| --- | --- |
| **7 of 280 (2.5%)** correct same-video pairs | **7 of 399 (1.8%)** wrong-*episode* candidates |
| **10 of 399 (2.5%)** correct cross-release pairs | — |

⭐ **And the two errors are not symmetric.** A destroyed pair is **silent**; a surviving
wrong pair is refused by `align()` at 1.3–1.9× chance. `00-INDEX.md` Rule 2 points the
other way here from how it reads at first glance — *the confidently wrong answer this rule
produces is the REJECTION*, not the pairing.

⚠ A cue-count floor does not rescue it: **14 of the 17** correct pairs it destroys carry
≥ 40 cues. The lowest measured correct same-video ratio is **0.056**. And a **shipped green
check** in `test_pairing.py` already asserted the opposite (900 s against 1,420 s = 0.634,
accepted). ⭐ **Shortness RANKS. It never rejects.**

**What ships instead**, every constant measured with its population — `tsubasa/duration.py`:

| | |
| --- | --- |
| `LONG_RATIO` **1.25** | cost/yield over 1,138 correct and 1,564 wrong directed pairs, floored by how often a subtitle's **own stray final cue** exceeds the bound: 21.14% of files at 1.05, **0.27% at 1.25** |
| `LONG_ABSOLUTE` **120 s** | the offset census — CM blocks group at +9.5–10 s, with-OP/without-OP at ±90 s. 120 = 90 + three CM blocks. **Both bounds required**; below 480 s of video the absolute one is operative |
| `ORPHAN_GAP` **300 s** | 🚨 **the last cue is not a robust statistic.** On **1.94%** of 1,495 real files it sits > 120 s past the previous cue — `Gintama - 074.ass` has 429 cues ending at ~1,475 s **plus one at 3,616.9 s**. `content_end()` drops orphan trailing cues before any ratio is taken |

### 🚨 And "duration is the fix for the CUTS trap" is also wrong — it RANKS

Blade Runner's cuts differ by **~1% of runtime**. No rejection bound can separate them
without destroying legitimate pairs, and an extended edition differing by 17% must still
not be rejected (§3.5 makes it a multi-break alignment). ⭐ **`duration_score` is the fix**:
it resolves two candidates **one second apart** without tying. Rejection was never
available here.

---

## §3.5 — 🚨 MOVIE LIBRARIES — a launch use case that does not work at all today

**Sonic's stated use case:** *"someone pointing it at a media library of their movies with
subs in the same directory, and automatically fixes all the subs to the movie version."*

### ⛔ Proven broken 2026-09-07

A folder containing `Inception (2010).mkv` and `Inception (2010).en.srt` — **an identical
stem plus a language tag** — produces **0 pairs**.

**Cause:** `pair_folder` contains `if vm["ep"] is None: continue`. A movie has no episode
number, so **every movie is skipped.** The whole folder workflow is episode-gated. This is
the easiest possible pairing case, and it fails.

### The path movies need

| Rung | Method | Covers |
| --- | --- | --- |
| ⭐ **1** | **Stem match** — strip language, edition, group and quality tags **through the learned decoration vocabulary** (film titles are 37.2% polluted by tokens the hand list misses), compare the remaining stem | The overwhelming majority. Movie libraries usually already name the sub after the video |
| 2 | **Title + year** | `Inception (2010)` vs `Inception.2010.1080p.BluRay-GROUP` |
| 3 | **Timing arbitration** | Ambiguity between candidates |

⭐ **A folder holding exactly one video means any subtitle in it belongs to that video.**
Cheapest rung of all, and it covers the single-movie-per-folder layout that Plex, Jellyfin
and Sonarr all produce.

### 🚨 Two traps this use case introduces

| Trap | Detail |
| --- | --- |
| 🚨 **Different CUTS of one film** | ⛔ **BOTH HALVES OF THIS ROW WERE WRONG AND WERE AMENDED AT A10 — see below.** The trap is real and worse than stated |
| 🚨 **Language tags pollute the series slug** | `Inception (2010).en.srt` → slug `inceptionen`, while the video gives `inception`. It survives today only because one is a prefix of the other — **luck, not design.** Strip language and edition tags **before** building the slug |

### 🚨 AMENDED BY MEASUREMENT AT A10 — the CUTS row was wrong twice over

This row used to say cuts *"produce slugs sharing 11 of 21 characters — **0.52**, above the
0.4 overlap threshold"*, and that **"duration is the discriminator."** Measured on the
shipped parser, **neither is true, and the trap is worse than the row described.**

**1. The overlap is not 0.52. It is 1.000.** `_title_from` deletes bracketed runs, so the
edition marker is gone before any comparison happens:

```
Blade Runner (1982) [Final Cut].mkv     ->  title 'Blade Runner'
Blade Runner (1982) [Theatrical].en.srt ->  title 'Blade Runner'
```

⛔ **No title measure at any threshold can separate them**, because there is nothing left to
separate. ⚠ The two were briefly distinguishable only by an *unrelated defect* — the parser
kept `mkv` in video titles, giving 0.667 — which is the same *survives-by-prefix* accident
this section already condemns for language tags. **Fixing that defect (A10) made the cuts
trap fully live**, which is the correct outcome: the mask is gone and the real mechanism
has to do the work.

**2. Duration does not discriminate them either.** Blade Runner's theatrical, director's
and final cuts all run **116–117 minutes** — inside every tolerance A9 measured, and they
have to be, or a 17%-different extended edition gets destroyed (§3.45).

⭐ **THE EDITION TAG IS THE LOAD-BEARING SIGNAL.** It must be carried as a **second value**
beside the key — `movies.MovieName.edition` — never folded into it. `movies.py` vetoes a
pair whose editions are **stated and differ**, and hands the ambiguous ones to timing
rather than guessing.

### 🚨 WHAT ACTUALLY CATCHES IT WHEN THE EDITION IS NOT STATED — write this down

⛔ **The veto only fires when BOTH sides name an edition.** The common real case does not:

```
Blade Runner (1982) [Final Cut].mkv   +   Blade Runner (1982).srt
```

Identity says **SAME** (titles are identical after the bracketed run is deleted).
Duration says **plausible** (116 against 117 minutes). The edition veto **does not fire**,
because one side states nothing. ⭐ **So both spec discriminators are gone, and the thing
that stops a theatrical subtitle landing on a Final Cut is `align()` REFUSING** — the cuts
carry genuinely different edits (removed narration, a changed ending, an added scene), so
the cue timings diverge, the match rate collapses toward chance, and the verdict refuses.

⭐ **That is the designed backstop and it is the whole architecture working**: identity
RANKS, timing DECIDES, and `00-INDEX.md` Rule 2 means a pair nobody can settle is refused
rather than written. ⛔ **Do not read *"identity says same, duration says same"* as a defect
in identity and go to fix it** — identity is not the layer that owns this.

⚠ **AND IT HAS NO SPECIMEN.** `CORPUS-COVERAGE.md` **gap 8** — *"the A10 use case has no
real specimen, only synthetic names"* — so the refusal above is **reasoned, not measured**.
It is the one claim in this section carrying no number, and it is named as such. Two cuts
of one film, with subtitles, is the fixture that would close it.

⚠ **Movies also make multi-break MORE likely, not less.** An extended cut inserts scenes
mid-film, so a theatrical subtitle needs several offsets rather than one. This is where
uncapped splitting earns its place.

---

## §4 — Pairing logic

| Case | Behaviour |
| --- | --- |
| Several valid subs for one video | Rank per `05-interface.md`, keep one, trash the rest. `--keep-all` opts out |
| Several videos for one subtitle | `REG` Timing arbitration picks. ⚠️ **Adopt at ≥2.5×; ESCALATE between 2.0–2.5×; refuse below 2.0×** — see `05-interface.md` §The verdict is a BAND. A single 2.5× line refuses 16% of correct pairs, measured over 364 |
| 🚨 **500 videos × 1500 subs** | Index by episode key first — **never a nested loop.** O(n) not O(n²) |
| `Subs/` sibling folder | If the sub folder holds no video, check the parent |
| 🚨 **Subs folder full of `.txt` and other junk** | surasura's real case. Non-subtitle files are **ignored silently** — expected input, never an error |
| Language tags `.en.srt`, `.jpn.srt`, `.forced.srt`, `.sdh.srt` | Stripped for **matching**, retained for **output naming** |
| Several languages, same episode | All pair, all sync, one kept per language |
| Already-synced `.synced.ass` | `REG` Skipped. Also checked against the results DB by content hash |
| `.bak`, `.orig`, `~` | Skipped |
| `.DS_Store`, `Thumbs.db`, `desktop.ini` | Skipped |
| `sample.mkv`, `-sample` | Skipped |
| 🚨 **NCOP / NCED** (creditless OP/ED) | **No dialogue at all.** Must REFUSE, never guess. A phantom alignment here is the documented 108 s orphan-cue failure |
| OVAs and specials in a season folder | Season 0 or unnumbered; paired by timing only |
| Zero-byte and truncated videos | `REG` Pair on filename (pairing needs no media), then ERROR with *"unreadable video (the file is empty)"* |

---

## §5 — Alignment

### 5.1 Content shape

| Case | Behaviour |
| --- | --- |
| **3-minute short** | `BUCKET = 120 s` and `MIN_BUCKET_CUES = 8` give ~1.5 buckets — the whole-runtime check degrades to nothing. **Scale the bucket to duration** below a floor, and say the check is weak |
| **4-hour film / concatenated season** | Uncapped splits handle it. ⚠ A 12-episode batch file needs ~11 breaks — the old `MAX_SEGMENTS = 4` was wildly wrong |
| Sub covers only part of the video (TV sub on a BD) | Aligns the covered stretch; buckets outside it are excluded, not failed |
| Sub longer than the video | Same handling, inverted |
| **Reference track == the subtitle** (self-align) | Must return exactly `0.000` — a suite assertion |
| 1 or 2 cues | ⛔ ERROR: below the measurable floor, stated as such |
| **100,000 cues** (karaoke-heavy ASS) | Must complete. Memory bounded by the chunked hit matrix |
| Zero-length cues `5.00 → 5.00` | `REG` Present in the corpus. Parsed, retimed, never dropped |
| Overlapping cues | `REG` Normal in ASS. No special handling |
| Cues out of order in the file | Sorted on parse; **original order preserved on write** |
| Cues past the video duration | Retimed normally; not evidence of misalignment |
| Negative timestamps | Clamped to 0 on write, counted, reported |

### 5.2 Timing pathology

| Case | Behaviour |
| --- | --- |
| 🚨 **Identical-source pairs** | Cue starts are **identical**, so the match-rate curve is a flat plateau, not a peak. `argmax` returns its left edge — a systematic −0.30 to −0.33 s error on the files that should be easiest. **Take the plateau centre.** ⚠ The median of supporting differences disagrees with it by up to 0.2 s on three oracle pairs — `12-alignment.md` §3.5, decision `D3b` |
| 🚨 **A break inside a quiet gap** (the opening song) | The cut index is a **tie** across the gap; the boundary lands at the gap's midpoint and is reported. Cues outside the gap decide correctness; cues inside it are reported, not asserted (`12-alignment.md` §3.5) |
| 🚨 **Cues inside a removed stretch** — sponsor cards and eyecatch captions timed into a CM block the video lacks | Under any offset they overlap the next segment. ✅ **`D9` ruled 2026-09-08: drop, count, report** (`03-permissions.md`) |
| **A minority segment (< 10% of cues)** | Invisible to a global offset histogram (its ~23 hits sit inside the noise of 4,800 bins). **The per-bucket histogram sees it** — the second dimension is not optional (`12-alignment.md` §3.2) |
| 🚨 **Bilingual dual-track subs** (0.1 s apart) | Doubles apparent cue density, inflates the chance baseline, and a **90%-matching perfect alignment scored 2.1× and was refused.** Cluster cue starts within `CLUSTER_TOL` |
| 🚨 **Orphaned OP karaoke cues** | 15 cues the subtitle lacks "found a home" 108 s away at 57% — exactly what the best of 4800 offsets scores by chance on 14 cues. Guarded by `MAX_BREAK` **and** a small-sample noise floor |
| Named framerate ratios (PAL etc.) | `REG` Tested on the **single-offset fit only** — a stretch and a split can absorb the same mismatch and hide each other |
| Unnamed drift (0.1% capture clock) | Least-squares residual slope detects it; refuse rather than snap to a wrong named ratio |
| **Non-linear drift** (VFR video) | ⛔ Cannot be fixed by offset or rate. Must be **detected and refused**, with the reason |
| Source A/V desync | Not fixable. The subtitle matches the reference; say so |
| Merged/split lines in a translation | Legitimately depresses match rate. The chance baseline already accounts for density |
| 💡 **Chapters marking ad breaks** | **Free split-point hints sitting unused in the container.** Seed the split search with them |

### 5.3 VAD — measured 2026-09-08

| Case | Behaviour |
| --- | --- |
| 🚨 **A broadcast cut on a track-less video** | **MEASURED** (`12-alignment.md` §5): the break is invisible on a speech mask — pre-break margin 0.04 against 0.35 required. ⭐ **At launch the VAD path fits ONE offset and REFUSES on a failing bucket**, naming the stretch, the ~10 s jump, the likely cause and the fix. Both real cut files refused at 1.94×; both uncut streaming subtitles accepted. Mask-path split detection is evolution |
| 🚨 **The verdict constants** | Correct uncut pairs measured at **2.42–2.77×** on a mask — straddling the cue-vs-cue 2.5. **Fit the mask-path band separately** with negative controls before any mask verdict ships |
| 🚨 **OP/ED karaoke** | Singing reads as speech to a VAD, but the subtitle may have **zero** OP lines — or **only** karaoke lines. Worst case in anime. Exclude the first/last ~90 s from VAD scoring unless cues exist there |
| 🚨 **Continuous background music** | `subsync` measured ffmpeg `silencedetect` returning a **94% speech mask** — all ones, zero information. Silero is the reason this is now viable; **verify against that same material** |
| Silence-heavy content (art film) | Fewer anchors, wider confidence interval. Refuse rather than stretch |
| Laugh tracks, applause | Non-speech vocalisation. Silero handles better than energy thresholding — assert it |
| Overlapping speakers | No special handling; VAD is binary presence |
| 🚨 **Container corruption that decodes "successfully" but drops most of the audio** | **REAL SPECIMEN:** `(SB-RAW)NARUTO 113`. The MKV carries scattered EBML corruption; ffmpeg walks the full `time=00:23:03` and reports success, but emits only **379 s of samples out of 1383 s** — 27%. **The file plays normally**, so nothing looks wrong. ⛔ **After decoding, compare sample count against container duration. If it is short by more than a few percent, REFUSE** — running VAD on a quarter of an episode produces a confident wrong answer, which is the exact class this tool exists to prevent |
| **No audio track at all** | ⛔ ERROR with the reason, never a crash |
| Commentary track selected by accident | Prefer the default/first audio track; `--audio-track N` overrides |
| Dub vs sub audio with different sync | Document that the chosen track defines the answer |
| 5.1 vs stereo | Downmix to mono 16 kHz — already the pipeline |

---

## §6 — Formats and encoding

### 6.1 The read/write split

> **Read timing from everything. Write back only what people keep.**

| | Formats |
| --- | --- |
| **Read timing** | `srt` `ass` `ssa` `vtt` `sub` (MicroDVD) `sbv` `smi` `ttml` `dfxp` `itt` **both STL variants** `idx` (VobSub) `sup` (PGS) · embedded `mov_text`, DVB-sub, teletext |
| **Write back** | `srt` `ass` `ssa` `vtt` `sub` `sbv` |

PGS and VobSub are **bitmaps** — readable as a timing reference, never writable as text.
That is not a limitation; it is free extra reference material.

### 6.2 🚨 ERROR must mean genuinely broken

A tolerance ladder, in order: **extension → content sniffing → lenient parse → ERROR.**

🚨 **"Parsed zero cues" and "could not read the file" are DIFFERENT outcomes.**
`subsync` conflated them twice — a WebVTT reference routed to the ASS parser, and a
legally-reordered ASS `Format:` line — and both times a real failure disguised itself as
something else and silently degraded the run.

### 6.3 Encoding

| Case | Behaviour |
| --- | --- |
| 🚨 **Any non-UTF-8 file** | Sniff, and **write back the same codec.** `latin-1` is the byte-exact last resort |
| **UTF-16 without a BOM** | Nulls throughout. Detect by null-density before the codec ladder |
| 🚨 **Ambiguous bytes** (Shift-JIS vs Big5) | Both decode some inputs "validly". A wrong guess is **silent mojibake.** Score candidates by character-class plausibility, not first-success |
| Mixed encodings in one file | Decode what is decodable, preserve the rest byte-exact, warn |
| BOM mid-file | Treated as content, not a marker |
| **CR-only line endings** (classic Mac) | Detected and preserved |
| Mixed CRLF and LF | Preserve per-line |
| No line endings at all | Single-line file; parse or ERROR honestly |

### 6.4 Per-format traps

| Format | Trap and behaviour |
| --- | --- |
| 🚨 **MicroDVD** `{start}{end}` | **Frame-based.** Needs FPS. Wrong FPS makes everything wrong. Read FPS from the video; refuse if unavailable |
| 🚨 **STL** | Spruce STL and **EBU-STL are different binary formats sharing an extension.** Sniff content, never trust the extension |
| **ASS `[Fonts]` / `[Graphics]`** | Embedded binary. Must survive the rewrite **byte-identical** |
| ASS `[V4 Styles]` vs `[V4+ Styles]` | Both parsed; `Format:` line read per file, never assumed |
| SRT with no blank lines between blocks | Lenient block splitting |
| SRT with duplicate/missing/non-sequential indices | Renumbered on write |
| VTT cue settings (`align:start position:10%`) | **Preserved verbatim** |
| VTT `NOTE` / `STYLE` / `REGION` | `REG` Preserved — dropping them turns a valid file invalid |
| TTML / DFXP | XML namespaces, multiple dialects. Parse defensively |
| **`.zip` / `.rar` of subtitles** | The normal OpenSubtitles delivery. Extract to temp, process, never write back into the archive |

---

## §7 — State and re-runs

| Case | Behaviour |
| --- | --- |
| Re-run, nothing changed | Hash-and-skip. ≤1 s for 24 episodes, zero decoding |
| ⚠ **Re-run under `--keep-all`** | 🚨 **DOES NOT SETTLE, and that is measured rather than intended.** Every run's outputs become the next run's candidates, and the flag never trashes, so the candidate set grows; two byte-identical candidates then collide on the distinguishing tag and the slot writes nothing. ⭐ Safe — no loss, no wrong file, and it reports `NOT WRITTEN` — but *zero decoding* is false for this flag. ⛔ **The fix wants a ruling, not a patch:** *keep every candidate* most likely means *every distinct **subtitle***, so a candidate byte-identical to an output already present is not a new one. That reading is consistent with *trashes nothing* and would converge. Recorded, not taken |
| Subtitle edited since last sync | Hash differs → re-processed |
| **Results DB says synced, file says otherwise** | 🚨 **The file always wins.** DB is advisory |
| Cache present, file changed | Hash mismatch → cache entry discarded, never trusted |
| Cache corrupt or from an older version | Version-stamped. Mismatched version → rebuilt silently |
| Index missing entirely | ⛔ **Everything still works.** Falls back to patterns + timing. Rule 1 |
| Index fetch fails (offline) | Silent. Uses the bundled floor. **Never blocks a run** |
| User trashed the original, then re-runs | Synced file's hash is in the DB → recognised as already done |
| Interrupted mid-folder | Per-pair atomicity. Completed pairs stay done; the interrupted one is untouched |
