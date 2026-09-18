<!--
  ⚠ AN ABSOLUTE URL, BECAUSE THIS FILE IS ALSO THE PyPI PAGE.
  `pyproject.toml` sets `readme = "README.md"`, and PyPI does not resolve
  repository-relative paths — `docs/brand/…` renders perfectly on GitHub and
  as a broken image there.

  ⚠ `main`, NOT a tag, and that was a correction. Pinning to `v0.1.4` looked
  more careful and was simply broken: these assets did not exist at that tag,
  so the image would have 404'd on every PyPI page. A tag can only be used
  once the tag contains the file. `main` always resolves and always shows the
  current mark, which for a logo is the behaviour you want; the cost is that
  moving this file breaks older PyPI pages, so it does not move.

  ⚠ The `original` variant deliberately: GitHub renders READMEs on both light
  and dark themes, and it is the one that works on either. The `dark` and
  `wordmark` variants are for light backgrounds only.
-->
<p align="center">
  <img src="https://raw.githubusercontent.com/SonicSandbox/Tsubasa-sync/main/docs/brand/tsubasa-original-512.png"
       alt="tsubasa" width="140" height="140">
</p>

<h1 align="center">tsubasa</h1>

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

<!--
  ⚠ ABSOLUTE, for the same reason as the logo above: this file is also the
  PyPI long description, and PyPI does not resolve repository-relative paths.
-->
<p align="center">
  <img src="https://raw.githubusercontent.com/SonicSandbox/Tsubasa-sync/main/docs/screenshot.png"
       alt="the tsubasa window: four episodes paired, three synced with their offsets and match rates, one refused because it is a different episode"
       width="820">
</p>

<p align="center"><sub>
  Every row is a decision you can audit — the offset applied, the match rate,
  and <b>why</b>. The refused one is a different episode, and it was left alone.
</sub></p>

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
pip install tsubasa-sync
```

Or with everything optional turned on:

```bash
pip install "tsubasa-sync[parsing,trash,gui]"
```

> ⚠ **The install name and the import name differ.** The distribution is
> `tsubasa-sync`; the module you import is `tsubasa`. The short name was
> already taken on PyPI by an unrelated project.
>
> ```python
> import tsubasa          # not `import tsubasa_sync`
> ```

**On Windows, without installing Python at all:** grab
`tsubasa-windows-x64.zip` from the [releases
page](https://github.com/SonicSandbox/Tsubasa-sync/releases) — see
[below](#windows-without-installing-python).

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

### Check the install from your own app

```python
check = tsubasa.self_check()
if not check.ok:
    for sentence in check.problems:
        log.warning("tsubasa: %s", sentence)
```

tsubasa's data files are optional by design, so **a broken install is silent**:
it runs, and settles far fewer pairs by name. `self_check()` is how you find
out. It opens none of your files and runs nothing.

**Freezing with PyInstaller needs nothing extra.** tsubasa ships a hook that
PyInstaller finds on its own. With any other freezer, copy `tsubasa/data/` in
beside the package — and call `self_check()` in your smoke test either way.

### A subtitle against another subtitle

```python
r = tsubasa.sync_to_reference("Show - 01.ja.srt", "Show - 01.en.srt")
if r.outcome == "CONFIDENT":
    out = tsubasa.render(r)            # bytes, in the file's original encoding
    Path("Show - 01.ja_retimed.srt").write_bytes(out.data)
```

Nothing is written for you. `render()` works on any result — a dry run of
`sync()` too — so your app names and places files its own way.

> ⚠ This makes the two subtitles **agree with each other** — it can't know
> whether the reference matches the video. A reference that covers only part
> of the subtitle is **refused**, because a cut in the uncovered part would be
> invisible; `render(r, force=True)` writes it anyway if you accept that.

### Reading names

```python
scan = tsubasa.scan("/media/anime")
video = scan.videos[0]
video.title, video.season, video.episode        # "Show", 2, 7

scan.unpaired(lang="ja")                        # videos with no Japanese subtitle
tsubasa.parse_subtitle_name("Show.ja[cc].srt")  # stem, lang "ja", tag "ja[cc]"
```

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
pip install "tsubasa-sync[gui]"
tsubasa-gui
```

Drag a folder onto the window and it runs. Refusals and errors pin to the top;
click one to read the full reason. Every option lives behind one button.

### Windows, without installing Python

> ⭐ **If you already have Python, use `pip install "tsubasa-sync[gui]"`
> instead.** It is the same application, it starts in about a second rather
> than a few, and antivirus never touches it. The zip below exists for
> people who do not have Python — it carries a whole interpreter, and that
> is what makes it both slower to start and prone to false positives.

`tsubasa-windows-x64.zip` on the [releases
page](https://github.com/SonicSandbox/Tsubasa-sync/releases) is the whole app
with Python inside it. Unzip it anywhere and double-click **`tsubasa-gui.exe`**;
`tsubasa.exe` beside it is the same command line described above. `SHA256SUMS`
on the same page is the checksum.

> ⚠ **It is not code-signed, so the first launch is noisy.** Windows
> SmartScreen shows *"Windows protected your PC"* — click **More info**, then
> **Run anyway**. The
> zip carries no installer and writes nothing outside `%LOCALAPPDATA%\tsubasa`
> and the subtitles it syncs.

> 🚨 **If your antivirus removes the download, it is a false positive
> — and the file is not gone.** Defender *quarantines*; it does not delete,
> and it is a few clicks from coming back.
> [`docs/WINDOWS-STARTUP.md`](docs/WINDOWS-STARTUP.md#if-defender-removed-the-download)
> has both ways to restore it. What gets flagged is PyInstaller's launcher
> — the same stub every app packaged this way carries — not anything
> specific to tsubasa. `pip install tsubasa-sync` avoids it entirely.

> ⏱ **The first launch after a reboot takes a few seconds.** Being unsigned,
> the app gets scanned in full — 1,274 files — every cold start. Later launches
> are quick. [`docs/WINDOWS-STARTUP.md`](docs/WINDOWS-STARTUP.md) explains it
> and gives the one-folder Defender exclusion if you want the seconds back.

**ffmpeg is not bundled.** Matroska files with a subtitle track inside need
nothing; any other container needs `ffmpeg` and `ffprobe` on `PATH`, or the
folder holding them in `TSUBASA_FFMPEG`.

**`tsubasa.exe --version`** reports the build, whether its data tables are
intact and whether ffmpeg was found — it is the one thing worth pasting into a
bug report.

> Windows only for now. On Linux you already have Python, which is the only
> thing freezing removes — so install it instead, **with the extras**, since
> that is what the zip actually carries:
>
> ```bash
> pipx install "tsubasa-sync[parsing,trash,gui]"
> ```
>
> ⚠ A bare `pipx install tsubasa-sync` pulls numpy alone: worse filename
> parsing, no OS trash, no drag-and-drop. ⚠ And the GUI needs your distro's Tk
> package (`sudo apt install python3-tk`, `sudo dnf install python3-tkinter`) —
> that one is genuinely the thing a frozen build would have fixed.

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
