---
type: spec
title: tsubasa — The Minimal LGPL ffmpeg Build
desc: Exactly what to build, how to build it, what to publish alongside it, and the acceptance test that proves it does the three things tsubasa needs.
date: 2026-09-08
---

# 11 — The minimal LGPL ffmpeg build

> ⛔ **STRUCK 2026-09-08 — decision `D1`, RULED by Sonic the same day.** This part was
> written under the MIT premise. tsubasa is **GPL-3.0** (ruled 2026-09-07), under which a
> stock ffmpeg build may be bundled or downloaded, so the minimal LGPL build is
> unnecessary work: five unverified items, a build on another machine, and a published
> source mirror, all to avoid a constraint that no longer exists. Acquisition is now
> `tsubasa setup --ffmpeg` with a pinned sha256 (`10-deployment.md`), and ffmpeg is needed
> only for audio and for non-MKV containers (`08-probes.md` §J6). **Kept as the record;
> nothing below is a build step.** If the licence is ever changed to a permissive one,
> this part comes back verbatim — that is the only condition that revives it.

> **Why this file existed:** tsubasa needs three narrow things from ffmpeg and none of them
> is encoding. A stock build is 78 MB and, in almost every distribution channel, **GPL**.
> A build configured for exactly our needs is ~15–25 MB and unambiguously LGPL.

---

## 🚨 Proof this matters — the ffmpeg already on this machine

`Workshop/media-kit/bin/ffmpeg.exe` reports:

```
--enable-gpl --enable-version3 --enable-libx264 --enable-libx265 ...
```

**That is a GPL build.** Shipping it inside an MIT product would relicense the product.
This is not a hypothetical — it is the binary this project has been using, and it is
typical: gyan.dev, BtbN's default variants and most distro packages are all GPL because
they bundle x264. **Never vendor a build you did not configure yourself.**

---

## What tsubasa actually needs

| # | Need | Used by |
| --- | --- | --- |
| 1 | Probe a container — stream list, duration | every run *(replaced by native demux later)* |
| 2 | Extract a **text** subtitle track | fast path *(replaced by native demux later)* |
| 3 | **Decode audio to raw PCM** | 🔴 **the VAD path — the one that cannot be replaced** |

⛔ **No video decoding. No encoding. No filters beyond resampling. No network.**

---

## The configure line

⚠️ **UNVERIFIED — must be confirmed by an actual build.** Flag names are from ffmpeg's
documented `configure` options; nobody has run this yet. The acceptance test below is what
settles it.

```bash
./configure \
  --prefix=./out \
  --disable-everything \
  --disable-gpl --disable-nonfree --disable-version3 \
  --disable-autodetect \
  --disable-doc --disable-debug --disable-ffplay \
  --disable-network --disable-devices --disable-hwaccels \
  --enable-small \
  --enable-demuxer=matroska,mov,mpegts,avi,ogg,flac,wav,mp3,aac,ac3 \
  --enable-decoder=aac,aac_latm,ac3,eac3,mp3,mp3float,flac,opus,vorbis,dca,truehd,mlp,pcm_s16le,pcm_s24le,pcm_s32le,pcm_f32le \
  --enable-decoder=ass,ssa,subrip,srt,webvtt,mov_text,text,dvdsub,pgssub \
  --enable-encoder=ass,ssa,subrip,srt,webvtt,pcm_s16le \
  --enable-muxer=ass,srt,webvtt,s16le \
  --enable-parser=aac,aac_latm,ac3,flac,opus,vorbis,dca \
  --enable-protocol=file,pipe \
  --enable-filter=aresample,aformat,anull \
  --enable-swresample
```

### Why each block is there

| Block | Reason |
| --- | --- |
| `--disable-everything` | Start from nothing and add back. The only way to get near 15 MB |
| `--disable-gpl --disable-nonfree` | 🚨 **The whole point.** Without these you get a GPL binary |
| `--disable-version3` | Keeps it at **LGPLv2.1**, the most permissive option. ⚠️ If a needed decoder refuses to build, `--enable-version3` is acceptable — LGPLv3 is still fine for MIT — but try without it first |
| `--disable-autodetect` | Stops the build silently linking whatever happens to be installed. **Without this the licence is whatever your machine had lying around** |
| `--disable-network --disable-devices` | We read local files. Nothing else |
| `--enable-decoder=...` audio | AAC, AC3/E-AC3, FLAC, Opus, Vorbis, DTS, TrueHD, PCM — covers anime and Western media |
| `--enable-decoder=...` subtitle | Text formats, plus `dvdsub`/`pgssub` for **timing extraction from bitmap tracks** |
| `--enable-muxer=s16le` | Required for `-f s16le -` , the raw PCM the VAD consumes |
| `--enable-protocol=pipe` | Required to write PCM to stdout |
| ⛔ no video decoders | We never decode a frame |

---

## Building it

**Linux / macOS**

```bash
git clone --depth 1 --branch n7.1 https://git.ffmpeg.org/ffmpeg.git ffmpeg-src
cd ffmpeg-src
./configure <the line above>
make -j"$(nproc)"
strip ffmpeg ffprobe
ls -la ffmpeg ffprobe        # expect roughly 8-15 MB each after strip
```

**Windows** — build under MSYS2/MinGW64, same configure line, add `--target-os=mingw32`
if cross-compiling. Output is `ffmpeg.exe` / `ffprobe.exe`.

**Reproducibility:** pin the tag (`n7.1`, or whatever is current) and record it. A build
you cannot reproduce cannot have its source published honestly.

---

## ✅ The acceptance test — this is what proves the build

**A build that compiles is not a build that works.** Run all five. Any failure means a
missing `--enable-` flag.

```bash
FF=./ffmpeg; FP=./ffprobe

# 1. LICENCE — must print neither "gpl" nor "nonfree"
$FF -hide_banner -version | grep -i configuration | grep -Eo '(gpl|nonfree)' && echo "FAIL: not LGPL" || echo "OK: LGPL"

# 2. PROBE a container
$FP -v error -show_streams -show_format -of json sample.mkv > /dev/null && echo "OK: probe"

# 3. EXTRACT a text subtitle track
$FF -v error -y -i sample.mkv -map 0:s:0 out.ass && echo "OK: subtitle extract"

# 4. DECODE audio to raw PCM  <- the one that cannot be replaced
$FF -v error -i sample.mkv -map 0:a:0 -af "highpass=f=300,lowpass=f=3400" \
    -ac 1 -ar 16000 -f s16le - | head -c 32000 | wc -c   # expect 32000
```

⚠️ Test 4's filter chain is what the VAD path actually runs. If `highpass`/`lowpass` are
missing, add `--enable-filter=highpass,lowpass` — **they are not in the configure line
above and this is the most likely first failure.**

```bash
# 5. SIZE
du -h $FF $FP     # target: under 25 MB combined
```

---

## What to publish in the GitHub release

Four items, in the **same** release as the binaries:

| Item | Why |
| --- | --- |
| `ffmpeg-lgpl-<platform>.zip` | The binaries |
| ⭐ **`ffmpeg-<tag>-source.tar.xz`** | **The LGPL obligation.** Mirroring it in the same release removes every question about whether "we linked to it" is sufficient |
| `FFMPEG-BUILD.md` | The exact tag, the exact configure line, the build command, and the acceptance-test output |
| `LICENSE.LGPLv2.1` | ffmpeg's licence text verbatim |

### `FFMPEG-BUILD.md` must state

1. **ffmpeg version/tag and commit hash**
2. **The verbatim configure line** — the one actually used, not the one in this doc
3. Build host and toolchain
4. `sha256` of every published binary
5. The line *"This build contains no GPL or non-free components. Source is published alongside it in this release."*

---

## How tsubasa uses it at runtime

🚨 **CORRECTED 2026-09-07.** An earlier draft had tsubasa prompt and download **mid-run**.
That broke three rules at once: *"no network during a sync run"* (stated in
`03-permissions.md`, `00-INDEX.md`, `02-data-model.md` and `07-test-plan.md`), the library's
*"prints nothing"* contract in `05-interface.md`, and it would block an unattended batch on
a `[Y/n]` prompt nobody is there to answer.

**The download is a SEPARATE, EXPLICIT command. Never part of a run.**

1. **Look for a system `ffmpeg`** on PATH, then `$TSUBASA_FFMPEG`, then the cache
   directory. If found, use it — nothing downloaded, no obligation at all
2. ⭐ **If absent and a run needs it** — i.e. the VAD path — that pair is **REFUSED with an
   actionable reason**, exactly like any other refusal:

```
✗  04  [shincaps] ... - 04.srt                    REFUSED
       no subtitle track in the video, and audio analysis needs ffmpeg
       run:  tsubasa setup --ffmpeg
```

3. ⭐ **`tsubasa setup --ffmpeg`** is the only thing that reaches the network. Explicit,
   interactive, run once. Downloads to the cache directory, **verifies the pinned
   `sha256`**, never touches system paths
4. ⛔ **The library NEVER downloads and NEVER prompts.** It reports the missing dependency
   in `Result.reason` and returns. The caller decides

**Everything not needing audio keeps working throughout.** A folder whose videos carry
subtitle tracks never touches ffmpeg at all once native demux lands.

⚠️ **Pin the `sha256` in the client.** An unverified download of an executable is a
supply-chain hole.

⚠️ **Pin the sha256 in the client.** An unverified download of an executable is a
supply-chain hole.

---

## Open, and needing a real build to settle

- [ ] Does the configure line compile? Which flags are missing?
- [ ] Is `--disable-version3` achievable, or does a needed decoder force LGPLv3?
- [ ] Actual stripped size — is 25 MB combined realistic?
- [ ] Are `highpass`/`lowpass` needed explicitly? *(almost certainly yes)*
- [ ] Does `pgssub`/`dvdsub` decoding suffice for **timing** extraction, or is a demuxer-level read needed?

**None of these blocks anything else.** ffmpeg is only on the VAD path, and the VAD path is
Track B6 — which is also the machine-move trigger. This build happens on the other machine.
