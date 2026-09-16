# Third-party components and attribution

tsubasa itself is **GPL-3.0-or-later** (see `LICENSE`). This file lists what it
depends on, what it bundles, and under what terms.

---

## Bundled in this package

| Component | What it is | Licence |
| --- | --- | --- |
| **Wikidata alias table** (`tsubasa/data/aliases.tsv.gz`) | ~221k `show-alias → entity id` rows, enumerated from Wikidata by work class | **CC0 1.0** (public domain dedication) — credited here regardless |
| **Decoration vocabulary** (`tsubasa/data/decoration.json`) | 176 release-jargon tokens (`1080p`, `aac`, `x265`, …) | Our own work product, GPL-3.0 with the rest |

> ⛔ **Nothing derived from AniList, TMDB, AniDB or subtitle-site filenames is
> included in this package.** The recognition layer was evaluated against such
> material during development; none of it ships.

---

## Runtime dependencies

| Package | Why | Licence |
| --- | --- | --- |
| **numpy** | the alignment primitive | BSD-3-Clause |

### Optional

| Package | Extra | Why | Licence |
| --- | --- | --- | --- |
| **anitopy** | `[parsing]` | anime release-name parsing | MPL-2.0 |
| **guessit** | `[parsing]` | Western release-name parsing | LGPL-3.0 |
| **send2trash** | `[trash]` | OS-native trash | BSD-3-Clause |
| **tkinterdnd2** | `[gui]` | drag-and-drop for the desktop window | MIT |
| **onnxruntime** | `[vad]` | audio analysis (not yet wired) | MIT |

Each is imported lazily and guarded; absent, tsubasa degrades to a documented
behaviour rather than failing.

---

## Not bundled, acquired separately

| Component | Licence | Note |
| --- | --- | --- |
| **ffmpeg / ffprobe** | LGPL-2.1+ or GPL-2+ depending on build | Never bundled by this repository. Found on `PATH`, supplied by the embedding application via `tsubasa.set_ffmpeg()`, or fetched explicitly by the user. ⚠ Anyone **redistributing** a build alongside tsubasa must include that build's licence text and its source or a written offer for it |
| **Silero VAD model** | MIT | Planned for the audio path; not present in this release |

---

## Reference implementations consulted

Named because the GPL-3.0 choice was made partly to permit it, and because
credit is owed for prior art even where no code was copied:

- **subsync** — the predecessor this project rebuilds, and its 29-pair oracle
- **alass**, **lapse**, **AutoSubSync** — compared against during design

---

## Verifying this file

⚠ **Licence identifiers above are recorded from each project's own metadata at
the time of writing and are not a substitute for reading them.** If you
redistribute a build — particularly one bundling ffmpeg — confirm the terms of
the exact versions you ship.
