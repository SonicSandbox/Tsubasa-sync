# tsubasa

**Pairs subtitle files to their videos and retimes them to match — by cue timing rather than text, so it works in any language.**

Point it at a folder. It works out which subtitle belongs to which video, measures how far out the timing is, fixes it, and **tells you when it isn't sure instead of guessing.**

```bash
pip install tsubasa
tsubasa ~/Anime/"Katainaka no Ossan S2"
```

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

---

## Why it's different

**A confidently wrong answer is worse than no answer.** Every threshold in this
tool sits in a measured band, and when the evidence isn't there it refuses and
says why — in a sentence you can act on.

| | |
| --- | --- |
| **Language-agnostic** | It matches on *when lines appear*, not what they say. Japanese against English works exactly as well as like-for-like |
| **It pairs, not just shifts** | Most tools retime a file you hand them. This one works out *which* file, across release groups and scripts — `Hell Mode` and `ヘルモード ~やり込み好きの…~` are the same show |
| **Broadcast cuts** | A TV edit with ad breaks removed needs *two* offsets. It finds the break and applies both |
| **It refuses** | Below the evidence bar it writes nothing and hands back a reason |
| **Nothing is destroyed** | Superseded files go to the trash, never `unlink` |

---

## Use it as a library

The importable API is the product; the CLI is a thin wrapper over it.

```python
from tsubasa import scan, sync

cands  = scan(videos="/media/anime/s2")        # filenames and stat only — opens nothing
report = sync(cands)                            # measures. Writes NOTHING
report = sync(cands, write=True)                # the only call that writes

for r in report:
    print(r.outcome, r.offset, r.match_percent, r.reason)
```

### Fixing subtitles without touching the originals

This is the common case for an application embedding tsubasa — **add a
corrected file, leave everything else alone.**

```python
sync(cands, write=True, rename=True, dedupe=False)
```

Measured by content hash on a real library:

| Call | Originals lost | Originals rewritten | New files |
| --- | --- | --- | --- |
| `sync(..., write=True)` *(default)* | to trash | 0 | ✔ |
| **`dedupe=False`** | **0** | **0** | ✔ |
| **`out_dir="/somewhere"`** | **0** | **0** | written elsewhere |

The output takes the **video's** basename (`<video>.<lang>.<ext>`) — which is
what makes a player load it automatically. `rename=False` retimes the subtitle
in place under its own name instead, which **overwrites the file you already
had**; it is the one option here that changes a file rather than adding one.

### If your application already bundles ffmpeg

```python
import tsubasa
tsubasa.set_ffmpeg(my_app_dir / "vendor" / "ffmpeg")   # a directory, or either binary
```

This **takes priority over `PATH`**, so a different ffmpeg installed on the
machine can't win over the build you shipped and tested against. Pass an
absolute path — a library doesn't own the process and must never resolve
against the working directory.

ffmpeg is only needed for containers the native reader can't open and for
audio analysis. **A Matroska file with a subtitle track never touches it.**

### What you get back

`Result` carries the outcome (`CONFIDENT` / `REFUSED` / `ERROR`), per-segment
offsets, match rate, the chance multiple, the confidence word, the language
resolved *and* as-written, what was written, what was superseded, and a
`reason` that is **never empty on a non-confident outcome**.

`SyncReport` adds the run-level view: `confident` / `refused` / `errored` /
`written` / `unpaired` / `settled` / `summary()`.

> ⚠ **Two side effects worth knowing before you embed it.** `sync()` consults a
> per-user results database (so a settled folder re-runs in a fraction of a
> second) and sends superseded files to the OS trash. Both are overridable —
> `results=False`, `trash_root=...` — but a library keeping state in your
> user profile shouldn't be a surprise you discover in production.

---

## Desktop app

```bash
pip install "tsubasa[gui]"
tsubasa-gui
```

Drag a folder onto the window and it runs. Refusals and errors pin to the top;
click one to read the full reason. Every option lives behind one button.

---

## Requirements

**Python 3.10+ and numpy.** That's the hard dependency list, and it's enforced
by a test rather than documented.

| Extra | Gives you | Without it |
| --- | --- | --- |
| `[parsing]` | anitopy + guessit for unusual release names | our own parser, which resolves 97.6% of a real catalogue alone |
| `[trash]` | OS-native trash | a local `.tsubasa-trash/` — still recoverable |
| `[gui]` | the desktop window | the library and CLI are unaffected |

---

## What it can't do yet

Stated plainly, because a tool that refuses should be honest about *why* it
sometimes refuses:

- **A video with no embedded subtitle track and no bitmap track is refused.**
  Audio analysis (VAD) is specified but not yet wired.
- **Non-Matroska containers need ffmpeg**, and that fallback path is not yet
  exercised against real files.
- **macOS is built and tested in CI but not hand-verified.**

---

## Licence

**GPL-3.0-or-later.** See `LICENSE`. Third-party attribution is in
`THIRD_PARTY_LICENSES`.

The bundled alias table is derived from [Wikidata](https://www.wikidata.org)
(CC0). **Nothing derived from AniList, TMDB, AniDB or subtitle-site filenames
ships in this package.**
