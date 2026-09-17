# -*- coding: utf-8 -*-
"""
The container reader: one accessor over video files. RUNBOOK step 1d, `D2`.

    from tsubasa import container
    info = container.read(path)              # duration, tracks, cue timing
    info = container.read(path, timing=False)  # header only -- the cheap probe

⭐ ONE ACCESSOR, and nothing else opens a video file.

`doctrine/architecture` rule 2. Discovery, duration checks, pairing, alignment
and hato all come through `read()`, so *"change where container data comes
from"* stays a one-function edit. That is not theoretical here: the whole point
of step 1d is that it just changed -- from an ffmpeg subprocess to a 30 KB
native read -- and every caller written against this function got that for
free.

## The ladder, and what each rung is FOR

    1  Matroska + a complete Cues index   0.085 s, 30 KB      the fast path
    2  Matroska, index absent or partial  ~1 s warm, 0.2 MB   the block walk
    3  anything else, or a broken walk    one subprocess      ffmpeg
    4  ffmpeg absent and needed           REFUSED, actionably

Rung 4 is a real outcome, not an error state. `10-deployment.md` requires the
pair to be refused with a sentence naming `tsubasa setup --ffmpeg`.

## Fail open, fail closed -- decided at each site, as the doctrine requires

| Situation | Choice | Why |
| --- | --- | --- |
| Matroska walk raises part-way | **open** -> ffmpeg | Reading it slowly beats not reading it |
| A partial Cues index | **open** -> block walk | The data is there; only the shortcut was wrong |
| ffmpeg missing and needed | **closed, loudly** | Silence would look like "no subtitles in this video" |
| A file that is genuinely not a container | **closed** | Naming what was found, not what was wanted |
| A Matroska track list cut off, damaged, or absent | **open** -> ffmpeg | 🚨 RUNBOOK 3f: it read as "no tracks" -- 582 of 588 truncations of a real file. The native reader raises now |
| A Matroska file that ends before its Segment does | **OK, and `incomplete` says so** | A download in progress. Readers that can use what is there still may; a header-only answer about it may not (`embedded_subs`) |

🚨 And the distinction this project has shipped wrong twice: **a container
with no subtitle tracks is `OK` with an empty list, NOT an error.** 37.5% of a
real library has no embedded track at all (`08-probes.md` §E) -- that is the
normal case for the pairing pipeline, and calling it a failure would refuse
more than a third of the library.
"""
import os

from ..cues import Outcome
from . import ffmpeg, mkv
from .ffmpeg import FfmpegMissing
from .mkv import ContainerError

# `06-edge-cases.md` §5.1 -- what discovery treats as a video. The native
# reader implements the Matroska family; everything else routes to ffmpeg
# until its own reader lands (MP4's `moov` sample tables are evolution).
KNOWN_VIDEO_EXT = {
    ".mkv", ".mk3d", ".mka", ".webm",
    ".mp4", ".m4v", ".mov", ".avi", ".ts", ".m2ts", ".wmv", ".flv", ".ogm",
    ".rmvb", ".vob", ".divx", ".mpg", ".mpeg",
}

# ---------------------------------------------------------------------------
# what a subtitle track CARRIES, from its codec -- ONE owner (RUNBOOK 3f)
# ---------------------------------------------------------------------------
# ⭐ Both readers' vocabularies, as MEASURED side by side on one file
# (`_work/probe_3f_1_language_parity.py`): Matroska's CodecID natively,
# ffmpeg's codec_name through the fallback. `S_TEXT/ASS` is `ass`,
# `S_HDMV/PGS` is `hdmv_pgs_subtitle`, `S_VOBSUB` is `dvd_subtitle`,
# `S_DVBSUB` is `dvb_subtitle`.
#
# 🚨 `pipeline.py` kept a private fragment list that had no DVB entry, so a
# DVB bitmap track was labelled TEXT. There it cost a word in a report; for a
# caller deciding whether a video already HAS a subtitle it skips a fetch the
# user needed. So both now read this.
#
# ⛔ TEXT IS AN ALLOW-LIST, NOT "NOT BITMAP". An unrecognised codec is neither
# -- `S_KATE`, `arib_caption`, `dvb_teletext` can each carry text or pictures
# -- because calling a bitmap track text is the expensive mistake and calling
# a text track unknown costs one download. And exact names, never fragments:
# a fragment like `hdmv` calls Blu-ray TEXT subtitles (`S_HDMV/TEXTST`,
# `hdmv_text_subtitle`) bitmaps.

#: Matroska's text namespace -- every `S_TEXT/...` CodecID is text.
_TEXT_PREFIX = "s_text/"

TEXT_CODECS = frozenset((
    # Matroska, outside the S_TEXT/ namespace
    "s_ssa", "s_ass", "s_hdmv/textst",
    "d_webvtt/subtitles", "d_webvtt/captions", "d_webvtt/descriptions",
    # ffmpeg codec_name
    "subrip", "srt", "ass", "ssa", "webvtt", "mov_text", "text", "microdvd",
    "mpl2", "pjs", "realtext", "sami", "stl", "subviewer", "subviewer1",
    "vplayer", "jacosub", "ttml", "eia_608", "hdmv_text_subtitle",
))

BITMAP_CODECS = frozenset((
    # Matroska
    "s_hdmv/pgs", "s_vobsub", "s_vobsub/zlib", "s_dvbsub", "s_image/bmp",
    # ffmpeg codec_name, and the decoder names some builds print instead
    "hdmv_pgs_subtitle", "dvd_subtitle", "dvb_subtitle", "xsub",
    "pgssub", "dvdsub", "dvbsub",
))


def _codec_key(codec):
    return (codec or u"").strip().lower()


def is_text_codec(codec):
    """True only for a codec KNOWN to carry text. Unrecognised is False."""
    key = _codec_key(codec)
    return key.startswith(_TEXT_PREFIX) or key in TEXT_CODECS


def is_bitmap_codec(codec):
    """True only for a codec KNOWN to carry pictures. Unrecognised is False."""
    return _codec_key(codec) in BITMAP_CODECS


class Track(object):
    """One track in a container.

    ⚠ `number` is the container's OWN identifier and its meaning depends on
    which reader produced it -- a Matroska TrackNumber natively, an ffmpeg
    stream index through the fallback. They are not interchangeable. `index`
    is the position in `ContainerInfo.tracks` and is the stable one.
    """

    __slots__ = ("index", "number", "kind", "codec", "language", "name",
                 "default", "forced", "cues", "timing_source",
                 "index_verified")

    def __init__(self, index, number, kind, codec=u"", language=u"", name=u"",
                 default=True, forced=False, cues=None, timing_source=None,
                 index_verified=None):
        self.index = index
        self.number = number
        self.kind = kind
        self.codec = codec
        self.language = language
        self.name = name
        self.default = default
        self.forced = forced
        # ⚠ None means "timing was not read", [] means "read, and it has no
        # cues". Collapsing those to [] is the OK-with-zero conflation that
        # `formats/__init__.py` exists to prevent, one layer up.
        self.cues = cues
        self.timing_source = timing_source
        self.index_verified = index_verified

    def __repr__(self):
        return "Track(%d, #%s, %s, %s, %s, %s)" % (
            self.index, self.number, self.kind, self.codec or "?",
            self.language or "und",
            "no timing" if self.cues is None else "%d cues" % len(self.cues))


class ContainerInfo(object):
    """What a container turned out to hold. Mirrors `cues.ParseResult`."""

    __slots__ = ("path", "format", "duration", "tracks", "chapters",
                 "outcome", "reason", "warnings", "reader", "bytes_read",
                 "seeks", "incomplete")

    def __init__(self, path=None, format=None, duration=None, tracks=None,
                 chapters=None, outcome=Outcome.OK, reason=u"", warnings=None,
                 reader=None, bytes_read=None, seeks=None, incomplete=u""):
        self.path = path
        self.format = format
        self.duration = duration
        self.tracks = tracks if tracks is not None else []
        self.chapters = chapters if chapters is not None else []
        self.outcome = outcome
        self.reason = reason
        self.warnings = warnings if warnings is not None else []
        self.reader = reader
        self.bytes_read = bytes_read
        self.seeks = seeks
        # ⚠ RUNBOOK 3f: a sentence when a Matroska file ends before its own
        # Segment does (a download in progress, or a cut), whichever reader
        # answered; u"" otherwise. The read is still OK -- this says the file
        # it describes is not all there.
        self.incomplete = incomplete

    @property
    def ok(self):
        return self.outcome == Outcome.OK

    @property
    def subtitle_tracks(self):
        return [t for t in self.tracks if t.kind == "subtitle"]

    def track(self, index):
        for t in self.tracks:
            if t.index == index:
                return t
        return None

    def __repr__(self):
        return "ContainerInfo(%s, %s, %s, %d tracks (%d subtitle)%s)" % (
            self.format, self.outcome,
            "?" if self.duration is None else "%.1fs" % self.duration,
            len(self.tracks), len(self.subtitle_tracks),
            (", %s" % self.reason) if self.reason else "")


def _to_info(path, raw, reader):
    tracks = []
    for i, t in enumerate(raw.get("tracks", [])):
        tracks.append(Track(
            index=i, number=t.get("number"), kind=t.get("kind") or "other",
            codec=t.get("codec") or u"", language=t.get("language") or u"",
            name=t.get("name") or u"", default=bool(t.get("default", True)),
            forced=bool(t.get("forced", False)), cues=t.get("cues"),
            timing_source=t.get("timing_source"),
            index_verified=t.get("index_verified")))
    return ContainerInfo(
        path=str(path), format=raw.get("format"), duration=raw.get("duration"),
        tracks=tracks, chapters=raw.get("chapters") or [],
        outcome=Outcome.OK, reason=u"",
        warnings=list(raw.get("warnings") or []), reader=reader,
        bytes_read=raw.get("bytes_read"), seeks=raw.get("seeks"),
        incomplete=raw.get("incomplete") or u"")


def _error(path, reason):
    return ContainerInfo(path=str(path), outcome=Outcome.ERROR, reason=reason)


def read(path, timing=True, cache_dir=None, allow_ffmpeg=True,
         use_index=True):
    """Read a video container. Never raises for a merely-unreadable file.

    `timing=False` reads the header only -- duration and the track list, with
    every `Track.cues` left at None. That is the shape step A9's duration
    check wants and it never opens a cluster.

    `allow_ffmpeg=False` keeps the read inside this process, which is what a
    caller that has promised no subprocesses (the importable module on the
    fast path) asks for.

    `use_index=False` forces the Matroska block walk, ignoring the Cues
    index. It answers *"is the fast path telling me the truth about this
    file"* -- and it is what `container --bench` compares the two paths with.

    ⭐ `TSUBASA_NO_NATIVE_DEMUX=1` disables the native reader entirely, so a
    Matroska file routes to ffmpeg. `07-test-plan.md` requires it: without a
    way to reach the fallback on a file we can read natively, **the fallback
    is code that never runs in the local configuration** -- and code that
    never runs rots silently until the day something depends on it.
    """
    path = str(path)
    if not os.path.isfile(path):
        return _error(path, u"no such file: %s" % path)
    try:
        if os.path.getsize(path) == 0:
            return _error(path, u"the file is empty (0 bytes)")
    except OSError as exc:
        return _error(path, u"could not stat the file: %s" % exc)

    native_reason = None
    try:
        with open(path, "rb") as fh:
            head = fh.read(4)
    except (IOError, OSError) as exc:
        return _error(path, u"could not open the file: %s" % exc)

    # ⚠ Read at call time, never cached at import. A suite sets it per block,
    # and a value frozen at import would silently ignore that.
    no_native = os.environ.get("TSUBASA_NO_NATIVE_DEMUX", "").strip() not in (
        "", "0", "false", "False")

    if mkv.looks_like_matroska(head) and not no_native:
        try:
            return _to_info(path, mkv.read(path, timing=timing,
                                           use_index=use_index), "matroska")
        except ContainerError as exc:
            # Fail OPEN. The file announced itself as Matroska and the walk
            # could not finish -- ffmpeg is more tolerant of damage than we
            # are, and reading it slowly beats not reading it.
            native_reason = u"%s" % exc
        except (IOError, OSError) as exc:
            return _error(path, u"could not read the file: %s" % exc)
        except Exception as exc:            # noqa: BLE001 -- see below
            # ⚠ A crash in a binary parser is still an outcome the caller has
            # to survive, not a traceback in the user's face. It routes to
            # ffmpeg exactly like a ContainerError, and says which it was.
            native_reason = u"unexpected %s in the Matroska reader: %s" % (
                type(exc).__name__, exc)

    if not allow_ffmpeg:
        if native_reason:
            why = native_reason
        elif no_native:
            # ⚠ Say which of the two switches closed the door. "Not Matroska"
            # would be a lie about a file that is Matroska, and a wrong reason
            # costs more than no reason.
            why = (u"the native reader is disabled by TSUBASA_NO_NATIVE_DEMUX "
                   u"and this read was also asked not to use ffmpeg, so there "
                   u"is no reader left for %s" % os.path.basename(path))
        else:
            why = (u"%s is not Matroska, and this read was asked not to use "
                   u"ffmpeg" % os.path.basename(path))
        return _error(path, why)

    try:
        raw = ffmpeg.read(path, timing=timing, cache_dir=cache_dir)
    except FfmpegMissing as exc:
        # ⛔ Fail CLOSED and loudly. Silence here would be indistinguishable
        # from "this video has no subtitles", which is a normal, common state
        # -- so a missing dependency would masquerade as a fact about the file.
        why = ffmpeg.missing_reason(
            u"reading %s" % os.path.basename(path)) if not native_reason else (
            u"the native Matroska reader stopped (%s) and falling back to "
            u"ffmpeg is not possible: %s" % (native_reason, exc))
        return _error(path, why)
    except ValueError as exc:
        return _error(path, u"ffmpeg could not read this file: %s%s" % (
            exc, u" (the native reader stopped first: %s)" % native_reason
            if native_reason else u""))

    info = _to_info(path, raw, "ffmpeg")
    if mkv.looks_like_matroska(head):
        # ⚠ ffprobe reads a cut-off file happily ("File ended prematurely",
        # exit 0), so the Matroska header is asked directly -- an incomplete
        # file reads as incomplete whichever rung answered (RUNBOOK 3f).
        try:
            info.incomplete = mkv.incompleteness(path)
        except (IOError, OSError):
            pass
    if native_reason:
        info.warnings.insert(0, u"the native Matroska reader stopped (%s), so "
                                u"this file was read through ffmpeg instead"
                             % native_reason)
    elif no_native and mkv.looks_like_matroska(head):
        # Not silent. A switch that quietly makes the tool 35x slower on every
        # file should be visible in the result, not just in someone's shell.
        info.warnings.insert(0, u"TSUBASA_NO_NATIVE_DEMUX is set, so this "
                                u"Matroska file was read through ffmpeg "
                                u"instead of the native reader")
    return info


def is_video(path):
    """Extension-based, and a HINT only -- the same rule `formats` applies.

    Used by discovery to decide what to open at all. The magic bytes are what
    actually decide which reader runs.
    """
    return os.path.splitext(str(path))[1].lower() in KNOWN_VIDEO_EXT
