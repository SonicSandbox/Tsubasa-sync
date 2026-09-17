# -*- coding: utf-8 -*-
"""
The ffmpeg fallback, and the refusal when it is not there.

RUNBOOK step 1d. `10-deployment.md` fixes both halves of this:

  * Acquisition order -- PATH, then `$TSUBASA_FFMPEG`, then the cache dir.
    ⛔ **Never during a run.** A tool that downloads a binary mid-run is a tool
    that behaves differently on its second use than its first.
  * When it is absent and a pair needs it, that pair is **REFUSED with an
    actionable reason** -- naming PATH and `$TSUBASA_FFMPEG` -- rather than
    failing with a stack trace or, worse, quietly producing nothing.
    ⚠ It named `tsubasa setup --ffmpeg` until 0.1.4. That command is
    `10-deployment.md`'s plan and was never built; see `missing_reason`.

⭐ WHEN THIS RUNS AT ALL

Almost never, and that is the point of RUNBOOK 1d. The native reader covers
Matroska, which is 62.5% of the measured library and the whole of the fast
path. ffmpeg is reached only for a container the native reader does not
implement -- MP4's `moov` sample tables are evolution -- for one that is
corrupt beyond the native walk, and for audio (VAD), which cannot be replaced
at all.

⚠ TIMING ONLY, exactly like the native path. `-show_packets` reports each
subtitle packet's presentation time without decoding anything, which is the
direct analogue of reading a block header. Extracting the TEXT is a different
operation belonging to a different step.

TRAPS ALREADY PAID FOR, from `LEDGER.md` §Environment:

  * 🚨 **Every ffprobe call flashed a console window that stole focus.** Under
    a GUI it is worse -- the parent has no console, so each child allocates
    its own. The flag has to be on the calls themselves, which is what
    `_no_window()` is.
  * 🚨 **Never suppress stderr while diagnosing.** A `2>/dev/null` hid 39 EBML
    errors and produced a confident wrong conclusion about a video file.
    stderr is captured and carried into the failure reason, never discarded.
"""
import json
import os
import shutil
import subprocess
import sys

from ..cues import Cue

# Matroska TrackType numbers, so both readers describe a track the same way.
KIND_TO_TYPE = {"video": 1, "audio": 2, "subtitle": 0x11}

TIMEOUT_PROBE = 60          # a header read that takes a minute is a hung tool
TIMEOUT_PACKETS = 600       # a full packet listing on a long file


class FfmpegMissing(Exception):
    """ffmpeg is needed and is not on this machine.

    Carries the actionable sentence `10-deployment.md` specifies, because a
    failure message the user cannot act on costs a round trip.
    """


def _no_window():
    """Keyword args that stop a console window flashing on Windows.

    🚨 Not cosmetic. Under the GUI the parent process has no console at all,
    so every child allocates its own and steals focus -- once per probed file,
    which on a 24-episode folder is 24 stolen focus events.
    """
    if sys.platform != "win32":
        return {}
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return {"creationflags": flags, "startupinfo": startupinfo}


#: An explicit location, set by an embedding application. ⛔ Not a path this
#: module ever discovers for itself -- see `set_location`.
_OVERRIDE = None


def set_location(where):
    """Tell tsubasa where YOUR ffmpeg is. -> the path that was set, or None.

    ===================================================================
    ⭐ FOR AN APPLICATION THAT ALREADY BUNDLES ffmpeg
    ===================================================================

        import tsubasa
        tsubasa.set_ffmpeg(my_app_dir / "vendor" / "ffmpeg")

    `where` may be the directory holding `ffmpeg`/`ffprobe`, or either binary
    itself — the sibling is found beside it.

    🚨 **PASS AN ABSOLUTE PATH.** A library does not own the process and must
    never resolve against `cwd`; an embedder knows their own layout
    (`Path(__file__).parent / ...`) and we take what we are given rather than
    guessing at a structure we cannot see.

    ⛔ **THIS BEATS `PATH`, AND THAT IS THE WHOLE POINT.** `10-deployment.md`
    puts PATH first, which is right for a person who installed ffmpeg once and
    wants it used. It is WRONG for an application that shipped a specific
    build: some unrelated ffmpeg earlier on PATH would silently win over the
    one they vendored and tested against. An explicit instruction outranks a
    search every time.

    ⚠ Pass `None` to clear it and fall back to the ordinary order.
    """
    global _OVERRIDE
    _OVERRIDE = str(where) if where is not None else None
    return _OVERRIDE


def location():
    """Whatever `set_location` was last given. -> str or None"""
    return _OVERRIDE


def _beside(where, tool, exe):
    """`where` as a directory or as either binary -> the tool's path, or None."""
    if not where:
        return None
    candidate = os.path.join(where, exe) if os.path.isdir(where) else where
    if not os.path.isfile(candidate):
        return None
    # ⚠ The caller may have named `ffmpeg` while we want `ffprobe`; look for
    # the sibling rather than running one as the other.
    if os.path.basename(candidate).lower().startswith(tool):
        return candidate
    sibling = os.path.join(os.path.dirname(candidate), exe)
    return sibling if os.path.isfile(sibling) else None


def find(tool="ffprobe", cache_dir=None):
    """Locate `ffmpeg` or `ffprobe`. -> a path, or None.

    Order: ⭐ an explicit `set_location`, then PATH, then `$TSUBASA_FFMPEG`,
    then the cache directory (which nothing writes into yet -- the downloader
    `10-deployment.md` describes was never built; the rung is kept because an
    application may put one there).
    `10-deployment.md` fixes the last three; the first is ahead of them
    because an application that told us where its ffmpeg is has answered the
    question this function exists to ask.
    ⛔ Nothing here downloads anything.
    """
    exe = tool + (".exe" if sys.platform == "win32" else "")

    explicit = _beside(_OVERRIDE, tool, exe)
    if explicit:
        return explicit

    found = shutil.which(tool)
    if found:
        return found

    # ⭐ THE SAME RESOLUTION AS THE OVERRIDE, THROUGH THE SAME FUNCTION.
    # `$TSUBASA_FFMPEG` and `set_location` accept exactly the same shapes — a
    # directory, or either binary — and this branch used to carry its own copy
    # of that logic. `doctrine/tooling` §anti-rederivation: two copies of one
    # rule is one you can fix and leave wrong.
    from_env = _beside(os.environ.get("TSUBASA_FFMPEG"), tool, exe)
    if from_env:
        return from_env

    if cache_dir:
        for candidate in (os.path.join(str(cache_dir), exe),
                          os.path.join(str(cache_dir), "ffmpeg", exe),
                          os.path.join(str(cache_dir), "bin", exe)):
            if os.path.isfile(candidate):
                return candidate
    return None


def missing_reason(need=u"reading this container"):
    """The one sentence a user can act on.

    ⚠ Says what is missing, what it was wanted FOR, and the exact command --
    "a failure message says what it FOUND, not what it wanted"
    (`doctrine/robustness`), and an unactionable refusal is a round trip.
    """
    # 🚨 THIS SENTENCE NAMED A COMMAND THAT DOES NOT EXIST, in every release up
    # to 0.1.3: `tsubasa setup --ffmpeg` is `10-deployment.md`'s acquisition
    # plan and was never built, so the one refusal a user is meant to ACT on
    # told them to run something that answers "unknown option". An actionable
    # reason that cannot be acted on is worse than a bare one -- it spends the
    # reader's time before it fails. It now names only what exists.
    return (u"%s needs ffmpeg, which was not found on PATH, in $TSUBASA_FFMPEG "
            u"or in the tsubasa cache directory. Install ffmpeg (the download "
            u"must carry both ffmpeg and ffprobe), then either put it on PATH "
            u"or set TSUBASA_FFMPEG to the folder holding them." % need)


def _run(argv, timeout):
    """Run a tool, capturing BOTH streams.

    🚨 stderr is captured and returned, never discarded. Suppressing it once
    hid 39 EBML errors and produced a confident wrong conclusion about a video
    file (`LEDGER.md` §Environment).
    """
    try:
        proc = subprocess.run(argv, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=timeout,
                              **_no_window())
    except subprocess.TimeoutExpired:
        return None, u"%s did not finish within %d s" % (
            os.path.basename(argv[0]), timeout)
    except OSError as exc:
        return None, u"could not run %s: %s" % (argv[0], exc)

    err = proc.stderr.decode("utf-8", "replace").strip()
    if proc.returncode != 0:
        tail = u"\n".join(err.splitlines()[-4:]) if err else u"(no output)"
        return None, u"%s exited %d: %s" % (
            os.path.basename(argv[0]), proc.returncode, tail)
    return proc.stdout.decode("utf-8", "replace"), err


def read(path, timing=True, cache_dir=None):
    """The same shape `mkv.read` returns, obtained through ffprobe.

    Raises FfmpegMissing when the tool is absent -- which the caller turns
    into a refusal naming the fix, not into a crash.
    """
    ffprobe = find("ffprobe", cache_dir)
    if ffprobe is None:
        raise FfmpegMissing(missing_reason())

    out, err = _run([ffprobe, "-v", "error", "-print_format", "json",
                     "-show_format", "-show_streams", str(path)],
                    TIMEOUT_PROBE)
    if out is None:
        raise ValueError(err)

    try:
        meta = json.loads(out)
    except ValueError as exc:
        raise ValueError(u"ffprobe returned output that is not JSON: %s" % exc)

    warnings = []
    if err:
        warnings.append(u"ffprobe reported: %s" % err.splitlines()[0])

    duration = None
    fmt = meta.get("format") or {}
    if fmt.get("duration") is not None:
        try:
            duration = float(fmt["duration"])
        except (TypeError, ValueError):
            duration = None

    tracks = []
    for stream in meta.get("streams", []):
        kind = stream.get("codec_type") or "other"
        tags = stream.get("tags") or {}
        if (stream.get("disposition") or {}).get("metadata"):
            # ⚠ ffprobe calls a WebVTT METADATA track (`D_WEBVTT/METADATA`)
            # a subtitle stream and flags it `metadata` -- measured at RUNBOOK
            # 3f. The native reader calls it what it is, so this does too.
            kind = "other"
        tracks.append({
            # ⚠ `number` is the container's own identifier and its MEANING
            # differs by reader: a Matroska TrackNumber on the native path, an
            # ffmpeg stream index here. Callers that need stable identity use
            # the position in this list, which both readers agree on.
            "number": stream.get("index"),
            "type": KIND_TO_TYPE.get(kind),
            "kind": kind if kind in ("video", "audio", "subtitle") else "other",
            "codec": stream.get("codec_name") or u"",
            "language": tags.get("language") or u"",
            "name": tags.get("title") or u"",
            "default": bool((stream.get("disposition") or {}).get("default")),
            "forced": bool((stream.get("disposition") or {}).get("forced")),
            "cues": None,
            "timing_source": None,
            "index_verified": None,
        })

    result = {"format": (fmt.get("format_name") or u"unknown").split(",")[0],
              "duration": duration, "timescale": None, "tracks": tracks,
              "chapters": _chapters(meta), "warnings": warnings,
              "bytes_read": None, "seeks": None}

    if not timing:
        return result

    for track in tracks:
        if track["kind"] != "subtitle":
            continue
        cues, why = _packet_times(ffprobe, path, track["number"])
        if cues is None:
            warnings.append(u"subtitle stream %s: %s" % (track["number"], why))
            continue
        track["cues"] = cues
        track["timing_source"] = "ffmpeg"
        # ffprobe lists every packet, so the result is complete by
        # construction -- there is no index here that could be partial.
        track["index_verified"] = True
    return result


def _chapters(meta):
    out = []
    for ch in meta.get("chapters") or []:
        try:
            start = float(ch.get("start_time"))
        except (TypeError, ValueError):
            continue
        out.append((start, (ch.get("tags") or {}).get("title") or u""))
    out.sort(key=lambda c: c[0])
    return out


def _packet_times(ffprobe, path, stream_index):
    """Every subtitle packet's presentation time. -> ([Cue], None) or (None, why)

    `-show_packets` reports timing without decoding, which is the direct
    analogue of reading a block header on the native path.
    """
    out, _err = _run([ffprobe, "-v", "error", "-print_format", "json",
                      "-select_streams", str(stream_index),
                      "-show_entries", "packet=pts_time,duration_time",
                      str(path)], TIMEOUT_PACKETS)
    if out is None:
        return None, _err
    try:
        packets = json.loads(out).get("packets", [])
    except ValueError as exc:
        return None, u"ffprobe packet output is not JSON: %s" % exc

    pairs = []
    for p in packets:
        try:
            start = float(p["pts_time"])
        except (KeyError, TypeError, ValueError):
            continue
        try:
            dur = float(p["duration_time"])
        except (KeyError, TypeError, ValueError):
            dur = None
        pairs.append((start, dur))

    pairs.sort(key=lambda x: x[0])
    return [Cue(s, s if d is None else s + d, u"", None, None, None)
            for s, d in pairs], None
