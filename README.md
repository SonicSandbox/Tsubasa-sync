# tsubasa

**Works out which subtitle belongs to which video — however differently the two are named — then retimes it to match.**

Point it at a folder of videos and a folder of subtitles. It pairs them and
fixes the timing. **You do not have to name anything, sort anything, or match
anything up by hand.**

```bash
tsubasa ~/Anime                              # subtitles sitting with the videos
tsubasa ~/Anime --subs ~/Downloads/subs      # or in a completely separate place
```

Both are searched recursively, so *"my whole anime folder"* and *"everything I
ever downloaded"* are valid inputs. Point and go.

---

## The hard part is knowing which file goes with which

Most subtitle tools take one video and one subtitle that **you** have already
matched, and shift the timing. That is the easy half.

tsubasa does the half nobody else does: **it decides which subtitle belongs to
which video**, across release groups, languages, writing systems and numbering
schemes that share nothing in common.

These are real pairs it makes, with no help:

```
[SubsPlease] Hell Mode S2 - 10 (1080p) [DD805213].mkv
  ↳ ヘルモード.～やり込み好きのゲーマーは廃設定の異世界で無双する～.S02E22.祈りが満ちて.WEBRip.ABEMA.ja[cc].srt
```
*Different language, different script, different title, **different episode
number** — one counts per season, the other counts from the start of the
series.*

```
[NanakoRaws] Yomi no Tsugai S01E18 (AT-X TV 1080p HEVC AAC).mkv
  ↳ 黄泉のツガイ.S01E18.WEBRip.ABEMA.ja[cc].srt
```
*English romanisation against the original Japanese title.*

```
片田舎のおっさん、剣聖になる S02E01.mkv
  ↳ [Erai-raws] Katainaka no Ossan Kensei ni Naru - 01 [1080p].ass
```
*Japanese video, romanised subtitle, and the subtitle carries no season at
all.*

### How it knows

| | |
| --- | --- |
| **A 221,258-entry alias table** | Every name a show is known by, linked to one entity. Enumerated from Wikidata (CC0) — `ヘルモード` and `Hell Mode` resolve to the same work |
| **Phonetic bridging** | Kana against romaji, so `ナルト` meets `Naruto` without either being in a lookup |
| **A learned decoration vocabulary** | 176 tokens — `1080p`, `WEBRip`, `x265`, `AT-X` — stripped for matching, kept for naming |
| **Season and episode, never episode alone** | *Series 1 Episode 3* must never meet *Series 3 Episode 3* |
| **Absolute vs per-season numbering** | Detected from the library itself when the two sides count differently |
| ⭐ **Timing has the final word** | A name is a hypothesis. The pair is confirmed by whether the two actually line up |

### Measured, on 350 real pairs

| | |
| --- | --- |
| **92.3%** | the right subtitle is among the candidates offered (323 / 350) |
| **80.0%** | settled on names alone (280 / 350) — **the rest are decided by timing**, not left unpaired |
| **0** | wrong-show pairs accepted, across 5,645 real videos against a 116-show pool |

⚠ Turning the alias table off drops name-settling to **51.4%**. The table is
why cross-script pairing works at all.

---

## Then it fixes the timing

Pairing is what it is *best* at; syncing is what it is *for*.

It matches on **when lines appear**, never on what they say — so a Japanese
subtitle can be timed against an English one, or against the video's own
embedded track, and neither has to be in a language anyone here can read.

```
tsubasa  ~/Anime/片田舎のおっさん S2                  24 videos · 26 subtitles

  ✗  04   [shincaps] Katainaka - 04 (AT-X).srt              REFUSED
          no subtitle track; on the audio the first 3:42 want a different
          offset (about +10 s) — a broadcast cut. The streaming release's
          subtitle will pair.

  ✓  01   片田舎のおっさん S02E01.ass      →  Katainaka no Ossan S2 - 01.ja.ass
          +0.13s          96% match · locked · holds throughout
  ⚑  03   [shincaps] ... - 03 (AT-X).srt   →  Katainaka no Ossan S2 - 03.ja.srt
          -33.07 / -42.96 @3:18   CUT 9.9s
                          91% match · strong · 2 segments

  23 synced · 1 refused · 3.1 s
```

| | |
| --- | --- |
| **Broadcast cuts** | A TV edit with ad breaks removed needs *two* offsets. It finds the break and applies both |
| **It refuses** | Below the evidence bar it writes nothing and says why, in a sentence you can act on |
| **Nothing is destroyed** | Superseded files go to the trash, never deleted |
| **Any format in** | SRT, ASS/SSA, VTT, and PGS/VobSub for timing. Written back in the format it came from, in its original encoding |

> **A confidently wrong answer is worse than no answer.** Every threshold sits
> in a measured band. When the evidence isn't there, it says so.

---

## Install

```bash
pip install git+https://github.com/SonicSandbox/Tsubasa-sync.git
```

> ⚠ **The install name and the import name differ.** The distribution is
> `tsubasa-sync`; the module you import is `tsubasa`. The short name was
> already taken on PyPI by an unrelated project.

**Python 3.10+ and numpy** — that is the whole hard dependency list.

| Extra | Gives you | Without it |
| --- | --- | --- |
| `[parsing]` | anitopy + guessit for unusual release names | our own parser, which handles 97.6% of a real catalogue alone |
| `[trash]` | OS-native trash | a local `.tsubasa-trash/` — still recoverable |
| `[gui]` | the desktop window | library and CLI unaffected |

---

## Use it from Python

The importable API is the product; the CLI and desktop app are wrappers over it.

```python
from tsubasa import scan, sync

cands  = scan(videos="/media/anime", subs="/downloads/subs")   # opens nothing
report = sync(cands)                                            # measures. Writes NOTHING
report = sync(cands, write=True)                                # the only call that writes

for r in report:
    print(r.outcome, r.offset, r.match_percent, r.reason)
```

### Fixing subtitles without touching the originals

The common case when embedding this — **add a corrected file, leave everything
else alone:**

```python
sync(cands, write=True, rename=True, dedupe=False)
```

Measured by content hash on a real library:

| Call | Originals lost | Originals rewritten | New files |
| --- | --- | --- | --- |
| `sync(..., write=True)` *(default)* | to trash | 0 | ✔ |
| **`dedupe=False`** | **0** | **0** | ✔ |
| **`out_dir="/somewhere"`** | **0** | **0** | written elsewhere |

Output takes the **video's** basename (`<video>.<lang>.<ext>`), which is what
makes a player load it automatically. `rename=False` retimes in place under the
subtitle's own name instead — the one option that changes a file rather than
adding one.

### If your application already bundles ffmpeg

```python
import tsubasa
tsubasa.set_ffmpeg(my_app_dir / "vendor" / "ffmpeg")   # a directory, or either binary
```

Takes priority over `PATH`, so a different ffmpeg on the machine can't win over
the build you shipped. Pass an absolute path — a library shouldn't resolve
against your working directory.

**ffmpeg is only needed** for containers the native reader can't open and for
audio analysis. A Matroska file with a subtitle track never touches it.

### What comes back

`Result` carries the outcome (`CONFIDENT` / `REFUSED` / `ERROR`), per-segment
offsets, match rate, the confidence word, the language resolved *and* as
written, what was written, what was superseded, and a `reason` that is **never
empty on a non-confident outcome**.

`SyncReport` adds the run-level view: `confident` / `refused` / `errored` /
`written` / `unpaired` / `settled` / `summary()`.

> ⚠ **Two side effects to know before embedding.** `sync()` consults a per-user
> results database (so a settled folder re-runs in a fraction of a second) and
> sends superseded files to the OS trash. Both are overridable — `results=False`,
> `trash_root=...` — but a library keeping state in your user profile shouldn't
> be a surprise you find in production.

---

## Desktop app

```bash
pip install "tsubasa-sync[gui] @ git+https://github.com/SonicSandbox/Tsubasa-sync.git"
tsubasa-gui
```

Drag a folder onto the window and it runs. Refusals and errors pin to the top;
click one to read the full reason. Every option lives behind one button.

---

## What it can't do yet

- **A video with no embedded subtitle track and no bitmap track is refused.**
  Audio analysis is specified but not yet wired.
- **Non-Matroska containers need ffmpeg**, and that path is not yet exercised
  against real files.
- **macOS** is built and tested in CI but not hand-verified.

---

## Licence

**GPL-3.0-or-later.** See `LICENSE`; third-party attribution in
`THIRD_PARTY_LICENSES.md`.

The bundled alias table is derived from [Wikidata](https://www.wikidata.org)
(CC0). **Nothing derived from AniList, TMDB, AniDB or subtitle-site filenames
ships in this package.**
