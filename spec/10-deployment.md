---
type: spec
title: tsubasa — Deployment and Environment Migration
desc: The release shape under GPL-3.0, how ffmpeg is acquired and when it is needed at all, the native container reader's place, and the plan for moving build and test to stronger hardware.
date: 2026-09-08
---

# 10 — Deployment

> ⚠ **Corrected 2026-09-08:** this part said *"MIT, public repo"*. tsubasa is **GPL-3.0**
> (`01-scope.md`). Every consequence below follows from that — chiefly that ffmpeg no
> longer needs a special build (`D1`).

## Release shape

**GitHub Releases, GPL-3.0, public repo.** No installer, no package manager at launch.

| Platform | Artifact | Built by |
| --- | --- | --- |
| Windows x64 | `tsubasa-windows-x64.zip` | GH Actions `windows-latest` |
| Linux x86-64 | `tsubasa-linux-amd64.tar.gz` | `ubuntu-latest` |
| macOS arm64 | `tsubasa-macos-arm64.tar.gz` | `macos-latest` |
| macOS x86-64 | `tsubasa-macos-x86_64.tar.gz` | `macos-15-intel` |

Plus `SHA256SUMS`, the source tarball (GPL requires it — it is the repo), and
`THIRD_PARTY_LICENSES`.

### Freezing

⭐ PyInstaller `--onedir`, not `--onefile` (which unpacks on every invocation). Expect
40–90 MB with numpy; prune `scipy`, `matplotlib`, `numpy.testing`, `pandas.testing`.
Nuitka is the alternative if cold start binds.

### What ships inside

| Item | Size | Licence |
| --- | --- | --- |
| Python runtime + numpy | ~40–90 MB | PSF / BSD |
| `silero_vad.onnx` | 2.2 MB | MIT |
| onnxruntime | ~15 MB | MIT |
| ⭐ **Wikidata alias table** (`aliases.json.gz`, A7) | **~3 MB gzipped** — measured, not "small" | CC0 |
| decoration vocabulary, kana table | KB | ours |
| `THIRD_PARTY_LICENSES` | — | mandatory |

⛔ **Nothing derived from AniList, TMDB, AniDB or jimaku filenames ships.**

---

## ⭐ The container reader, and where ffmpeg still stands

✅ **BUILT 2026-09-08** — `tsubasa/container/`, RUNBOOK 1d. One accessor, `container.read()`,
and nothing else opens a video file.

| Need | Launch answer | ffmpeg needed? | State |
| --- | --- | --- | --- |
| probe a container (duration, tracks) | native EBML read of `Info` + `Tracks` | no (MKV) · yes (other containers) | ✅ `timing=False`, **315 bytes / 104 seeks** measured |
| a subtitle track's **timing** | **Cues-indexed block read — measured 0.087 s median, ~30 KB over 10 real files**; block walk when the index is missing, partial or wrong | no (MKV) · yes (MP4 until the `moov` reader lands) | ✅ 0.000000 s from ffmpeg's own extraction |
| **chapters** (ad-break hints, `06-edge-cases.md` §5.2) | same walk, free | no (MKV) | ✅ built; none of the ten test files carry any |
| a subtitle track's **text** (extraction, hato) | native block payload read | no (MKV) | ⏸ **not built** — RUNBOOK 3a. The seam is `mkv._block_header`, which returns the payload offset |
| **audio → PCM for VAD** | ffmpeg subprocess | **yes — the one thing that cannot be replaced** | ⏸ B6 |

So a folder whose videos carry subtitle tracks never touches ffmpeg, and the importable
module has **no binary dependency** on the fast path. That is what *"included in other
packages"* required, and `test_a_matroska_file_never_starts_a_subprocess` holds it shut by
making `subprocess.run` raise.

🚨 **The index is verified before it is trusted.** A muxer that indexes only some subtitle
blocks returns a well-formed subtitle **missing lines**. Before the fast path's answer is
returned, a contiguous run of two clusters is walked and its blocks counted; a disagreement
sends the track to the full walk. `Track.index_verified` is `True` / `False` / **`None` for
"could not be checked"**.

⚠ **The ffmpeg fallback has never actually executed.** ffprobe is not installed on the
build machine, so its routing and its refusal are proved and its argument construction,
JSON handling and packet parsing are **unexercised**. Named in RUNBOOK 1d as unchecked.

### Acquiring ffmpeg — never during a run

1. Look for `ffmpeg`/`ffprobe` on PATH, then `$TSUBASA_FFMPEG`, then the cache directory
2. If absent and a run needs it (the VAD path, or a non-MKV container), that pair is
   **REFUSED with an actionable reason**
3. ⏳ **`tsubasa setup --ffmpeg` — specified here, never built, and RULED TO BUILD on
   2026-09-17** when Sonic chose an installer over bundling ffmpeg in the standalone
   (`STANDALONE-BUILD-SCOPE.md`, RUNBOOK **Step 3g**). The only thing that reaches the
   network: explicit, run once, a **stock build** (any licence is acceptable under
   GPL-3.0 — and fetching is not redistributing), **pinned sha256**, never touching
   system paths. 🚨 **Step 3g must first close a wiring gap measured the same day: the
   cache-directory rung of `ffmpeg.find()` is never reached**, because nothing in the
   product passes `cache_dir` — so a downloaded binary would sit where nobody looks
4. ⛔ The library never downloads and never prompts. It reports in `Result.reason`

🚨 **AND THE REFUSAL NAMED THAT UNBUILT COMMAND UNTIL 0.1.4 (fixed 2026-09-17).** Every
release to 0.1.3 told the reader to run `tsubasa setup --ffmpeg`, which answers *"unknown
option"* — the one sentence written to be acted on could not be. ⭐ **An actionable reason
that cannot be acted on is worse than a bare one**, because it spends the reader's time
first. The sentence now names only PATH and `$TSUBASA_FFMPEG`, and
`test_ffmpeg_absence_refuses_with_a_sentence_the_user_can_act_on` checks every backticked
`tsubasa <command>` in it against the CLI's own usage text — so a command invented in a
message fails in the suite rather than in a user's terminal. If the downloader is ever
built, this rung and that sentence come back together.

⚠ Pin the sha256 in the client. An unverified download of an executable is a
supply-chain hole.

### Attribution

Wikidata (CC0, credit anyway) · Silero · onnxruntime · send2trash · anitopy · guessit ·
ffmpeg (when bundled: its licence text and the build's source or a pointer to it, in the
same release).

---

## Where the tool stores things — asked and answered 2026-09-17

| | |
| --- | --- |
| **Windows** | `%LOCALAPPDATA%\tsubasa` |
| **Linux / macOS** | `~/.cache/tsubasa` |
| **Override** | `TSUBASA_CACHE`, and `sync(trash_root=)` for the trash alone |
| **What is in it** | the pairing cache · the results store · the GUI's settings file · the fallback `.tsubasa-trash/` |

⛔ **Not `%APPDATA%\Roaming\<Company>\<Product>`, and the distinction is deliberate.**
Windows splits the two: **Roaming** carries small settings and credentials that should
follow a user to another machine; **Local** carries caches, derived data and anything
machine-specific. Everything tsubasa writes is regenerable or machine-specific — nobody
wants a subtitle cache or a trash folder syncing between PCs. ⭐ And a vendor folder names
an application: `SonicSandbox\Surasura` is right for surasura, which stores credentials and
usage counts; **tsubasa is a published library other people's apps import**, so it uses its
own name. An application that wants tsubasa's files inside its own folder sets
`TSUBASA_CACHE` at startup — no code change.

⚠ **Two consequences, named rather than fixed:** the GUI's settings file lives in the CACHE
directory, so clearing the cache discards preferences (⭐ lean: leave it — one location is
easier to explain); and the fallback trash lives there too, so "clear the cache" also
discards recoverable subtitles.

## Version stamping

A content hash, never a timestamp, never hand-bumped; wired as a preflight on publish.

## Proving a release — three separate claims

1. The archive contains the expected files, by name and size
2. The live downloaded artifact's reported version equals the local one
3. The binary runs on a clean machine with no Python installed

⚠ Read `doctrine/release` before the release block; pipe nothing inside it.

---

# 🚚 Migration plan — moving build and test to stronger hardware

Sonic: *"i will port much of this to another device for the compute necessary… When that
happens I need a migration plan."*

## What is portable today, by design

| Artifact | Portable? |
| --- | --- |
| the spec pack, the source, the harness, `subsync/tests/fixtures/` | ✅ git |
| the corpus | ⚠ not in git; copied by hand, **filenames preserved byte-for-byte** |
| cache, results DB | ✅ disposable |

Nothing hardcodes a machine: `TSUBASA_CORPUS`, `TSUBASA_CACHE`, `TSUBASA_FFMPEG`.

## ⭐ The trigger: RUNBOOK B6

Everything before VAD is text-file and container-header work this laptop handles (the
whole fast path measures in milliseconds). **VAD is compute-bound: ~21 s per episode
here.** Fitting the mask-path constants across the corpus is the move. Set up the GitHub
repo first — it is the transport.

## The steps

| # | Step | Proof |
| --- | --- | --- |
| 1 | push the repo | `git log` matches on both machines |
| 2 | copy `tsubasa-corpus/` preserving filenames | `python -m tsubasa.dev corpus --verify-split` reports identical counts and hashes |
| 3 | set `TSUBASA_CORPUS` | `corpus --stat` resolves |
| 4 | install Python 3.10+, numpy, onnxruntime, anitopy, guessit, send2trash, pytest | `python run_tests.py` green |
| 5 | re-run the perf and VAD baselines | **targets re-baselined, not inherited** |
| 6 | leave the old corpus in place until step 2's proof passes | nothing deleted before it is verified elsewhere |

## Three traps in this move

- 🚨 **Filenames are half the corpus.** A copy that normalises Unicode, truncates at
  NAME_MAX or case-folds destroys test cases silently. Verify a CJK-named file survives
- 🚨 **NFC vs NFD** on a macOS target. Normalise at read time; verify after the copy
- 🚨 **Performance targets do not transfer.** Restate them after measuring

**The sealed slice stays sealed across the migration.**
