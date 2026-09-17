# Using tsubasa

A practical guide: the command line, the Python API, and building an app on top of it.
Every example here has a runnable version in [`examples/`](../examples) — each one
builds its own demo data, so you can run it before pointing it at your library.

- [Install](#install)
- [From the command line](#from-the-command-line)
- [From Python](#from-python)
  - [1. See what is there — `scan()`](#1-see-what-is-there--scan)
  - [2. Measure, then write — `sync()`](#2-measure-then-write--sync)
  - [3. Read the results](#3-read-the-results)
  - [4. A subtitle against another subtitle](#4-a-subtitle-against-another-subtitle)
  - [5. Languages and names](#5-languages-and-names)
  - [6. What a run leaves behind](#6-what-a-run-leaves-behind)
- [Building an app on tsubasa](#building-an-app-on-tsubasa)
- [Runnable examples](#runnable-examples)

---

## Install

```bash
pip install tsubasa-sync
```

The package installs as **`tsubasa-sync`** and imports as **`tsubasa`**. Python 3.10–3.13.
The only hard dependency is numpy.

| Extra | Adds | Without it |
| --- | --- | --- |
| `tsubasa-sync[parsing]` | anitopy and guessit, second opinions on unusual release names | tsubasa's own parser, which reads the large majority of names alone |
| `tsubasa-sync[trash]` | the OS trash for superseded subtitles | a `.tsubasa-trash/` folder in tsubasa's per-user cache directory |
| `tsubasa-sync[gui]` | the desktop window, `tsubasa-gui` | the library and command line are unaffected |

**ffmpeg** is needed only for containers other than Matroska (`.mkv`). A Matroska file with a
subtitle track is read directly. Without ffmpeg, other containers are refused with a sentence
that says so.

---

## From the command line

```bash
tsubasa ~/Anime                                  # subtitles sitting beside the videos
tsubasa ~/Anime --subs ~/Downloads/subs          # subtitles somewhere else
tsubasa --pair "Show - 01.mkv" "Show - 01.srt"   # one pair, named explicitly
tsubasa --pairs pairs.json                       # a manifest: [["video", "subtitle"], ...]
```

Folders are searched recursively. Anything that is not a video or a subtitle is ignored.

| Option | Does |
| --- | --- |
| `--dry-run` | print every intended action; write and trash **nothing** |
| `--subs DIR` | where the subtitles are, when they are not beside the videos |
| `--out DIR` | write the results there instead, mirroring the library's folders |
| `--no-rename` | retime in place, keeping each file's own name |
| `--suffix TEXT` | write a retimed **copy** beside each original, named after it — `--suffix _rt` gives `Show - 01_rt.ja.srt`. Nothing else is changed or trashed |
| `--keep-all` | write every candidate; supersede nothing |
| `--no-recurse` | do not descend into sub-folders |
| `--pair V S` | an explicit pair. Repeatable |
| `--pairs FILE` | a JSON manifest of pairs |
| `--force` | write a pair the timing REFUSED. Explicit pairs only |
| `--json` | one JSON object per result, on stdout |
| `--verbose` | add the raw measurements and which reference was used |
| `--no-results` | ignore, and do not update, the record of what was already synced |

Start with `--dry-run`. It measures everything and changes nothing.

### What the results mean

| Outcome | Meaning | What to do |
| --- | --- | --- |
| **CONFIDENT** | Measured, and the timing agrees well enough to trust | Nothing — it is written (or would be) |
| **REFUSED** | Measured, and **not** good enough to trust | Read the reason. Usually the wrong subtitle, or a different edit of the video. `--force` writes it anyway, for explicit pairs |
| **ERROR** | Could not be measured at all — unreadable, empty, no track to align against | Read the reason; it names what is missing |

A result that is not CONFIDENT **always** carries a reason.

A CONFIDENT result also carries a word for how far the match is above chance: **locked**, then
**strong**, then **fair**. **uncertain** means the pair was weak on its own, and the rest of its
release — other episodes from the same group, agreeing with each other — vouched for it.

### Exit codes

| Code | Meaning |
| --- | --- |
| `0` | every pair was decided, and written or would be |
| `1` | something was REFUSED, was an ERROR, or failed to write |
| `2` | the command could not be run as typed |

A refusal is a non-zero exit on purpose, so a script can tell.

### For scripts: `--json`

```bash
tsubasa ~/Anime --json --dry-run > results.ndjson
```

Each line is one result, with the same fields as the Python `Result` below. The one-line
summary goes to stderr, so stdout stays machine-readable.

---

## From Python

The Python API is the product; the command line and the desktop app are built on it.

### 1. See what is there — `scan()`

```python
import tsubasa

scan = tsubasa.scan(videos="/media/anime", subs="/downloads/subs")   # or scan("/media/anime")
print(scan.summary())                    # "24 videos · 26 subtitles"

for video, candidates in scan.pairings():
    print(video.name, "->", [c.subtitle.name for c in candidates])

for video, reason in scan.unpaired():
    print(video.name, "has nothing:", reason)
```

**`scan()` opens none of your files.** It reads names, so it is fast and safe on a whole
library. It returns *candidates* — which subtitles might belong to each video, best first —
not decisions. `sync()` settles them by timing.

Each candidate has an `identity`: **`same`** (the names refer to the same show — including
across scripts, `黄泉のツガイ` and `Yomi no Tsugai`), **`unsure`**, or **`different`**.

→ [`examples/scan_a_library.py`](../examples/scan_a_library.py)

### 2. Measure, then write — `sync()`

```python
report = tsubasa.sync(scan)                  # measures everything. Writes NOTHING
report = tsubasa.sync(scan, write=True)      # the only call that writes
```

**Nothing is written unless you pass `write=True`.** The measurement is identical either way.

Choose what writing does:

| Call | Originals | New file |
| --- | --- | --- |
| `sync(scan, write=True)` | subtitles that lose to the winner go to the trash | beside the video, named after it |
| `sync(scan, write=True, dedupe=False)` | **all left exactly where they are** | beside the video, named after it |
| `sync(scan, write=True, out_dir="/elsewhere")` | untouched | under `/elsewhere`, mirroring the library |
| `sync(scan, write=True, rename=False)` | the subtitle is **retimed in place** | — |
| `sync(scan, write=True, suffix="_rt")` | **all left exactly where they are** | beside each **original**, named after it: `Show - 01_rt.ja.srt` |

The output is named `<video name>.<language>.<ext>` — the form media players load
automatically — and keeps the subtitle's original format and text encoding.

**With a suffix**, the suffix goes *before* the language tag, so the copy still reads as
Japanese to tsubasa and to media players. A copy is never retimed again on a later run, and it
cannot be combined with `rename=False`, `out_dir` or `keep_all` — each would mean something
other than *a copy beside the original*, so each raises `ValueError`.

**Explicit pairs** skip the name-matching and go straight to timing:

```python
report = tsubasa.sync([("Show - 01.mkv", "some other name.srt")], write=True)
```

`force=True` writes an explicit pair that was REFUSED. It never overrides an ERROR — there is
no measured offset to write — and it is refused on a scan, where it would mean writing the
best of several rejected candidates.

→ [`examples/sync_a_folder.py`](../examples/sync_a_folder.py)

### 3. Read the results

A `SyncReport` is a sequence of `Result`, one per decision, including every refusal:

```python
for r in report:
    if r.outcome == "CONFIDENT":
        print(r.video, r.offset, r.match_percent, r.verdict_word, r.output_path)
    else:
        print(r.video, r.outcome, r.reason)

print(report.summary())    # "1 refused · 23 synced" — anything needing attention leads
```

| `Result` field | Holds |
| --- | --- |
| `outcome` | `"CONFIDENT"`, `"REFUSED"` or `"ERROR"` |
| `reason` | why it is not CONFIDENT — never empty when it is not |
| `video` · `subtitle` | the paths. ⚠ `subtitle` is `None` when the video itself could not be read, so no subtitle was tried |
| `offset` | seconds to add to the subtitle's times. A file with a cut has more than one — see `segments` |
| `segments` | `[(until, offset), ...]`: each offset applies up to `until` on the corrected clock; the last `until` is `None`, meaning to the end |
| `match_percent` · `verdict_word` | how well the timing agreed, and the word for it |
| `output_path` | the file written — set only when one actually was |
| `superseded` | files that went to the trash |
| `lang` · `lang_tag` | the language resolved (`ja`), and as the name wrote it (`jpn`) |
| `forced` · `write_failed` | a forced write happened; a write was attempted and did not land |
| `dropped_in_gap` · `dropped_before_zero` | lines removed because they fell in a cut, or before the video starts |
| `notes` | anything else worth telling a person |

`SyncReport` also has `confident`, `refused`, `errored`, `written`, `forced` and `failed`
(lists of results), `unpaired` and `settled` (videos with no candidate, and videos already
synced on an earlier run — neither is a `Result`), and `skipped` (files deliberately left out,
with why).

### 4. A subtitle against another subtitle

When one subtitle is in time — say an English one — and another is not:

```python
r = tsubasa.sync_to_reference("Show - 01.ja.srt", "Show - 01.en.srt")

if r.outcome == "CONFIDENT":
    out = tsubasa.render(r)          # the retimed file, as bytes, original encoding
    Path("Show - 01.ja.retimed.srt").write_bytes(out.data)
else:
    print(r.reason)
```

- **Nothing is written for you.** `render()` returns bytes, and your code chooses the name and
  the place. It works on any result — a dry run of `sync()` too.
- **It makes the two subtitles agree.** It cannot know whether the reference itself matches
  the video.
- **A reference that covers only part of the subtitle is REFUSED.** If the reference stops
  after four minutes, a cut at minute fifteen would be invisible, and the rest of the file
  would be written wrong with nothing to say so. `render(r, force=True)` writes it anyway, using
  the offset measured where the two overlap.
- `render()` raises `ValueError`, with a sentence, for anything it will not render: an ERROR, a
  REFUSED result without `force=True`, or a subtitle that no longer reads.

→ [`examples/subtitle_to_subtitle.py`](../examples/subtitle_to_subtitle.py)

### 5. Languages and names

Every file a scan finds is read into structured fields:

```python
video = scan.videos[0]
video.title, video.season, video.episode    # "Yomi no Tsugai", 1, 18
video.episode_candidates                    # (18,) — more than one if the parsers disagreed

subtitle = scan.subtitles[0]
subtitle.lang, subtitle.lang_tag            # "ja", "ja[cc]"
```

- `episode` is an `int`, or a `float` for a half episode such as `13.5` — never rounded.
- `lang` is resolved: `.ja.`, `.jpn.`, `.JA.` and `.ja-JP.` all read `ja`. A name with no
  language reads `und`. For a video, `lang` is `None`.

**Which videos have no subtitle in a language:**

```python
for video, reason in scan.unpaired(lang="ja"):
    print(video.title, video.episode, reason)
```

A subtitle with no language in its name does not count as any language, so a video whose only
subtitle is `Show - 03.srt` is still reported. A language tag tsubasa does not recognise
raises `ValueError` rather than quietly reporting every video.

**Reading a subtitle filename on its own:**

```python
tsubasa.parse_subtitle_name("Show - 01.ja[cc].srt")
# Sidecar('Show - 01', lang=ja tag=ja[cc] +cc) — stem, lang, tag, flags, ext
```

→ [`examples/find_missing_subtitles.py`](../examples/find_missing_subtitles.py)

### 6. What a run leaves behind

| | Default | To turn it off |
| --- | --- | --- |
| **A record of what was synced**, so a settled folder re-runs in a fraction of a second | kept in a per-user store | `sync(..., results=False)` |
| **Superseded subtitles** | the OS trash with `[trash]` installed; otherwise `.tsubasa-trash/` in tsubasa's per-user cache directory — never beside your media | `sync(..., dedupe=False)` or `suffix=` keeps them all in place; `trash_root=` chooses the folder |

Nothing is ever deleted outright. `scan()` leaves nothing behind at all.

If the OS trash **refuses** a file — one Windows has locked, one on a network drive with no
recycle bin — it goes to the local `.tsubasa-trash/` instead, and the result's `notes` say where.

---

## Building an app on tsubasa

### Check the install

```python
check = tsubasa.self_check()
if not check.ok:
    for sentence in check.problems:
        log.warning("tsubasa: %s", sentence)
```

tsubasa's data files are optional by design, so **a damaged install still runs** — it just
settles far fewer pairs by name, with no error. `self_check()` is how you find out.

- `ok` is `False` only for what is **silently** worse than it should be: each data table is
  compared with the size it records for itself, so a truncated file is caught as well as a
  missing one.
- `notes` reports things that are fine but worth knowing — no ffmpeg, an optional parser not
  installed. Those fail loudly when they matter, so they never make `ok` false.
- It opens none of your files and runs nothing. `as_dict()` gives plain data for a
  diagnostics report.

→ [`examples/check_the_install.py`](../examples/check_the_install.py)

### Freezing your app

**PyInstaller needs nothing extra.** tsubasa ships a hook that PyInstaller finds on its own,
and it collects the data files.

**Any other freezer** (Nuitka, cx_Freeze, Briefcase): copy the `tsubasa/data/` folder in beside
the package.

Either way, call `self_check()` from your frozen build's smoke test. Without the data, a frozen
app runs normally and pairs by name far less often — nothing else will tell you.

### Bundling ffmpeg

```python
tsubasa.set_ffmpeg(app_dir / "vendor" / "ffmpeg")   # the folder, or either binary
```

This takes priority over `PATH`, so a different ffmpeg on the user's machine cannot win over the
one you ship. Pass an absolute path. `set_ffmpeg(None)` restores the normal search.

### Keeping your interface responsive

`sync()` measures in the calling thread and has no cancel switch. For a desktop app, **run
tsubasa as a separate process**: you can cancel by ending it, and nothing it does can freeze or
crash your interface.

```python
command = [sys.executable, "-m", "tsubasa", "--pair", video, subtitle, "--json"]
env = dict(os.environ, PYTHONIOENCODING="utf-8")

with tempfile.TemporaryFile() as err:          # not a pipe: two pipes can deadlock
    child = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=err,
                             env=env, encoding="utf-8")
    for line in child.stdout:                  # one result per line, as each lands
        result = json.loads(line)
        ...
    code = child.wait()                        # 0, 1 or 2 — see Exit codes
```

To cancel, call `child.terminate()`.

⚠ **In an app frozen with PyInstaller, `sys.executable` is your app, not Python.** Relaunch your
own executable with a flag of your choosing, and in that child call:

```python
import tsubasa.cli
sys.exit(tsubasa.cli.main(["--pair", video, subtitle, "--json"]))
```

→ [`examples/run_as_a_subprocess.py`](../examples/run_as_a_subprocess.py)

### Licence

tsubasa is **GPL-3.0-or-later**. Make sure the licence of the project you build on it is
compatible.

---

## Runnable examples

Each builds its own demo data when run with no arguments, so every one works on a fresh install.

| Example | Shows |
| --- | --- |
| [`scan_a_library.py`](../examples/scan_a_library.py) | what might pair, across scripts and numbering schemes, from names alone |
| [`find_missing_subtitles.py`](../examples/find_missing_subtitles.py) | which videos have no subtitle in a language |
| [`sync_a_folder.py`](../examples/sync_a_folder.py) | a dry run, then `--write`, keeping every original |
| [`subtitle_to_subtitle.py`](../examples/subtitle_to_subtitle.py) | retiming against a reference subtitle, including a cut |
| [`check_the_install.py`](../examples/check_the_install.py) | `self_check()` for an app's startup or smoke test |
| [`run_as_a_subprocess.py`](../examples/run_as_a_subprocess.py) | the separate-process pattern for desktop apps |

```bash
python examples/scan_a_library.py                 # a demo
python examples/scan_a_library.py ~/Anime         # your own library
```
