---
type: spec
title: tsubasa — Data Model
desc: The four stores, the canonicity rule in one line, the cache cost model, and what the identity index actually is.
date: 2026-09-08
---

# 02 — Data Model

No accounts, no server, no rows owned by people. **Four things hold state**, and only one
of them is not disposable.

| Store | Keyed on | Lives | Disposable? |
| --- | --- | --- | --- |
| ⭐ **Alias table** — one ENTITY, N names, each tagged by script (built 2026-09-08 — `09-corpus-strategy.md` §Stage 2.4) | normalized title | bundled + refreshable | yes — rebuildable |
| **Learned rules** — the decoration vocabulary and the kana table | token | bundled | yes — re-derived from the catalogue by one command |
| **Cache** | content hash | per-user app data | yes — always |
| **Results DB** | content hash | per-user app data | yes, but see below |
| 🚨 **The user's subtitle files** | path | their media folder | **NO** |

---

## ⭐ Canonicity, in one line

> **The newest successfully-fetched index wins; the bundled one is the offline floor.**

Two conditions Sonic attached to that approval, both now hard constraints:

1. ⛔ **The network never touches the hot path.** Index lookup is a local O(1) read.
   Fetching happens only on an explicit `tsubasa update`, or a background check that a
   sync run **never waits on**. A user with no internet must notice nothing.
2. ⛔ **Prove the index earns its place before building it.** See `07-test-plan.md`
   §Probe A. If pattern matching already resolves ~everything, the index is dead weight.

**For the other stores:** the file on disk always wins. Cache and results are advisory —
if a hash mismatches, the cached entry is discarded, never trusted.

---

## ⛔ SUPERSEDED 2026-09-07 — everything below about the CRC32 index

> 🚨 **The CRC32 index was CANCELLED by Probe A** — it rescues at most **1.11%** of a
> 15,378-file corpus, because 97% of the files it would need to fix carry no CRC32 tag.
> **Do not build it.** See `07-test-plan.md` §Probe A and `RUNBOOK.md` step ~~A7b~~.
>
> ⭐ **What replaces it is a different mechanism entirely: the Japanese↔romaji ALIAS
> TABLE**, validated by Probe C at a **47.3% ceiling** — 42× the value. A Japanese filename
> reduces to an *empty* ASCII slug, so it pairs with every video sharing its episode number;
> 4,133 of 10,222 parsed files. Build it from **Wikidata (CC0)**. See `RUNBOOK.md` step A7.
>
> ⚠ **2026-09-08:** Probe C and Probe G were measured against `titles.json` — 4,620 rows,
> a mid-crawl artefact. **The answer key is `titles.jsonl`: 12,259 entries, 12,152 with
> romaji + Japanese, 10,762 with English.** The table is a **ranking accelerator** — the
> timing referee decides — so Rule 1 applies to it exactly as to the embedded track
> (`09-corpus-strategy.md` §Stage 2, `08-probes.md` §G, §O5).
>
> 🚨 **AMENDED BY THE BUILD, 2026-09-08 (A7): "three-way" was not buildable.** This
> paragraph said the table *must be three-way* — romaji, Japanese, English. **Wikidata
> has no romaji field**: probe A7/1 measured `ja` 100%, `en` 100%, `mul` 0%, English
> aliases 90%, with the romaji living *inside those aliases* beside abbreviations and
> alternative English titles. ⭐ **The shipped shape is one entity and N names, each
> tagged by script** — which also holds `Star Blazers` for `宇宙戦艦ヤマト`, a real name
> no romaji column could have carried. Full record: `LEDGER.md` §Logic, A7.
>
> 🚨 **These two were once described together as "the identity index." They are not the
> same thing and they reached opposite verdicts.** The section below is kept only as the
> record of what was investigated and why it was dropped.

## ~~What the identity index is~~ *(cancelled — read the banner above)*

> **A lookup table shipped inside the tool that turns a filename clue into a definite
> show and episode.**

Release groups put a CRC32 checksum in anime filenames —
`[Erai-raws] Katainaka - 02 [1EAFC83B].mkv`. AnimeTosho publishes a **daily database
export**, licensed *"without restriction"*, in which that checksum resolves to an exact
series and episode.

**Verified empirically, not assumed:** a live query for `CE838CE0` returned exactly one
entry — `[SubsPlease] Kamiina Botan… - 05 (1080p) [CE838CE0].mkv` — carrying
`anidb_aid: 19206`, `anidb_eid: 311540`.

### How it is built

| | |
| --- | --- |
| **Source** | `https://storage.animetosho.org/dbexport/` — daily |
| **Tables** | **Files** (~397 MB, carries `crc32` hex) joined to **Torrents** (~70 MB, carries `aid`/`eid`) via `torrent_id` |
| **Wrinkle** | AniDB IDs live at the **torrent** level, not the file level. The join is required |
| **Shipped artifact** | A derived CRC32 → (series, episode) index. **Never the raw 470 MB dumps** |
| **Plus** | ⭐ **`titles.json` from [[jimaku-corpus]]** — already built, see below |
| **Plus** | Wikidata (CC0) for non-anime title aliases |

### ⭐ The romanisation table already exists

`Workshop/jimaku-corpus/` harvests **romaji ↔ Japanese ↔ English for every jimaku.cc
entry it visits** — ~12,500 entries uploaded by hundreds of people, written to
`titles.json`, and a row is recorded **even when the entry keeps no file**. Its own
documentation names the purpose exactly:

> *"That is the bridge that lets a matcher know a romaji filename and a Japanese one are
> the same show."*

**This is the single most valuable input to Track A and it is already in hand.** It is
also the widest sample of real Japanese subtitle *filenames* in existence, which makes it
simultaneously the romanisation source **and** the naming-scheme test corpus.

### 🚨 RESOLVED 2026-09-07 — `titles.json` never ships

Every entry carries an `anilist_id`. **It is AniList data**, and AniList's terms
explicitly prohibit mass collection and redistribution.

⛔ **Encryption is not a fix.** If redistribution is not permitted, obfuscating the file
does not permit it — and in an open-source project the key ships with the code, so it is
reversible in a minute. Exposure intact, with extra steps.

**The objection is how the data was obtained, not what it contains** — so stripping the
`anilist_id` field does not help either. Titles are facts and facts are not copyrightable,
but terms of service are contract law and do not care.

#### The split that IS clean

| Ships in the GPL-3.0 build? | |
| --- | --- |
| ✅ **Regexes and normalization rules learned from the corpus** | Own work product. Learning from data is not redistributing it |
| ✅ Scheme-inference logic | |
| ✅ **The decoration vocabulary** (185 tokens, learned by frequency against the key) and **the kana phonetic bridge** (a rule) | Own work product; re-derivable from a future crawl |
| ✅ `tsubasa index --build` — the code that builds and reads an index | Code is ours; the data the user builds is theirs |
| ✅ A table derived from **Wikidata (CC0) + AnimeTosho** (unrestricted) | Both permit redistribution |
| ⛔ **Any table derived from AniList or TMDB** — `titles.jsonl` | Never |
| ⛔ **A table mined from jimaku uploader filenames** (2,003 far Latin aliases, 3,270 CJK) | Provenance unruled — **Sonic's private build and surasura only** |

**`titles.json`'s role:** the **answer key**, used locally, to measure how complete the
Wikidata+AnimeTosho rebuild is. That use never redistributes it. If coverage measures
poorly, that is a number to decide on — not a guess to make now.

**Sonic's private build and surasura may use any local index.** Personal use is not
redistribution.

### The other corpus tool already built

`Workshop/consolidate-subs/consolidate-subs.sh` gathers every subtitle from a media
library into one flat folder per show, **preserving pathology rather than tidying it** —
filenames never normalised, bytes never touched. With `-e` it also extracts tracks
embedded in the videos. That is the corpus-acquisition half of Step 0a, already written.

### What it is NOT

- 🚨 **Not AniDB.** AniDB indexes by **ed2k hash + filesize** and has explicitly rejected
  CRC32 lookup as collision-prone. Its data is also CC BY-NC-SA and unbundleable.
- **Not a decision.** It produces a stronger *hypothesis*. **The timing still decides.**
  A fuzzy title match to the wrong series is a confident error, and only the timing
  referee catches it.
- **Not universal.** AnimeTosho matches on filename *words*, so it fires only when the
  group put the CRC in the name. Anime: usually. Everything else: rarely.

---

## The cache

**What is cached**, keyed by content hash:

| Item | Cost to rebuild |
| --- | --- |
| Container index — duration, tracks, the subtitle track's cue times | **one 30 KB Cues-indexed read (0.085 s)** on MKV; one subprocess elsewhere |
| Parsed cue lists | milliseconds |
| Extracted reference tracks (text) | one native block read, or one subprocess |
| 🔥 **VAD speech onsets** | **~21 s of Silero per 24-minute episode on this laptop** — the one that matters; keyed on the video hash, never recomputed |
| Cluster probe results | milliseconds; keyed on the pair of hashes |

### ⚠ Cost model, as the doctrine requires

| | |
| --- | --- |
| **Cost when nothing changed** | One `stat` plus a **head/tail + filesize hash** per file. **O(1) per file regardless of video size** — never reads gigabytes. A 24-episode folder re-runs in well under a second with zero decoding |
| **Cost at 10× the data** | Linear in **file count**, not bytes. 10,000 files ≈ 10,000 cheap hashes |

🚨 **Never hash a whole video file.** A full-content hash of a 1.4 GB mkv defeats the
entire purpose of the cache. Head 64 KB + tail 64 KB + filesize is the standard trick and
is what makes the re-run target reachable.

### Location

Per-user app data — `%LOCALAPPDATA%\tsubasa` on Windows, `~/.cache/tsubasa` on
Linux/macOS. Overridable by `TSUBASA_CACHE`.

⛔ **Never beside the media.** `subsync` wrote `_ref_2.ass` and a 500 KB `.npy` next to
the subtitles it was aligning — inside a corpus its own README marks do-not-modify.

---

## The results DB

Records what was synced, the verdict, the offsets applied, and when. Keyed on the
**content hash of the subtitle**, so it survives renaming.

**It answers one question the filename cannot:** *"has this already been synced?"*

That matters because Sonic ruled **no `.synced` marker in the filename**. See
`03-permissions.md` for the in-file marker rules and `06-edge-cases.md` §7 for what
happens when the DB and the file disagree.

---

## Does any record own a file?

**Yes — this is the whole product.** Every consequence of that lives in
`03-permissions.md` (what may be changed) and `05-interface.md` (naming, dedupe, trash).
