# -*- coding: utf-8 -*-
u"""
The subtitle tracks a video file carries INSIDE it. RUNBOOK 3f.

    subs = tsubasa.embedded_subtitles("Show - 01.mkv", lang="ja")
    if not subs.ok:
        ...          # could not tell -- NOT "there are none"; subs.reason says why
    elif any(t.text and not t.forced for t in subs.tracks):
        ...          # a full Japanese text subtitle is already inside

⭐ ADDED IN 0.1.3 FOR CODE BUILT ON TSUBASA, AND NEVER RENAMED. hato's read
rule opens with it -- *a video with an embedded Japanese text track already has
its subtitle, in sync, for free* (hato `06-edge-cases.md` §6) -- and the reader
that answers it (`container.read`, RUNBOOK 1d) was reachable only through
internals.

## Three things this refuses to blur

| | Why |
| --- | --- |
| ⛔ **Could not read is not "has none"** | `ok=False` carries the reader's reason and `tracks` RAISES. A container with no subtitle track is `ok=True` with `tracks == []` -- the normal case for 37.5% of a real library (`08-probes.md` §E) |
| ⛔ **An unrecognised codec is not text** | `text` and `bitmap` are both False for a codec neither list in `container/` names. A bitmap track called text makes a fetcher skip a download the user needed; the reverse costs one download |
| **Forced is reported, never filtered** | A forced track is signs only. Whether that counts is the caller's rule -- hato's is *"A forced sub is not a full sub"* |

⛔ And the result is not a yes/no. `if tsubasa.embedded_subtitles(video):` would
be true for EVERY video -- an object is truthy -- and a fetcher written that way
skips every fetch. So truth-testing it raises and says what to ask instead.
"""
import os

from . import container as _container
from . import sidecar as _sidecar
from .api import _language_asked_for

__all__ = ["embedded_subtitles", "EmbeddedSubtitles", "EmbeddedSubtitle"]


class EmbeddedSubtitle(object):
    u"""One subtitle track inside a video.

    `index`      its position among ALL the tracks tsubasa read from the
                 container, video and audio included -- the same for both of
                 tsubasa's readers on an ordinary file, and usually ffmpeg's
                 stream index. ⚠ Not always: ffmpeg drops some exotic entries
                 (button, logo or control tracks, an entry with no type or
                 codec), so on such a file `-map 0:<index>` can differ
    `lang`       ISO 639-1 where one exists (`ja`), else `und`. Resolved through
                 the same language table as a filename's tag, so `jpn`,
                 `ja-JP` and `ja` agree
    `tag`        the container's language string as read (`jpn`, `ja-JP`,
                 `und`). ⚠ A Matroska track that states none reads `eng`,
                 which is that format's default
    `codec`      the container's codec name as read -- `S_TEXT/ASS` natively,
                 `ass` through ffmpeg
    `text`       True only for a codec KNOWN to carry text
    `bitmap`     True only for a codec KNOWN to carry pictures (PGS, VobSub, DVB)
    `forced`     the container's forced flag -- signs only, usually
    `default`    the container's default flag
    `name`       the track's title, when it has one (`Signs & Songs`, `日本語`)
    """

    __slots__ = ("index", "lang", "tag", "codec", "text", "bitmap", "forced",
                 "default", "name")

    def __init__(self, index, lang, tag, codec, text, bitmap, forced, default,
                 name):
        self.index = index
        self.lang = lang
        self.tag = tag
        self.codec = codec
        self.text = text
        self.bitmap = bitmap
        self.forced = forced
        self.default = default
        self.name = name

    def __repr__(self):
        form = u"text" if self.text else u"bitmap" if self.bitmap else u"?"
        return u"EmbeddedSubtitle(%d, %s, %s %s%s)" % (
            self.index, self.lang, form, self.codec or u"?",
            u", forced" if self.forced else u"")


class EmbeddedSubtitles(object):
    u"""What one video carries, and whether that could be found out at all.

    `video`    the path that was read
    `ok`       True when the container was read
    `reason`   why it could not be, when `ok` is False
    `lang`     the language asked for, resolved (`ja`), or None for all
    `tracks`   [`EmbeddedSubtitle`] in container order.
               ⛔ RAISES `ValueError` when `ok` is False
    """

    __slots__ = ("video", "ok", "reason", "lang", "_tracks")

    def __init__(self, video, ok, reason=u"", lang=None, tracks=()):
        self.video = video
        self.ok = ok
        self.reason = reason
        self.lang = lang
        self._tracks = list(tracks)

    @property
    def tracks(self):
        if not self.ok:
            raise ValueError(
                u"nothing is known about the subtitle tracks in %s, because "
                u"it could not be read: %s. Check `.ok` first -- an unread "
                u"video is not a video with no tracks."
                % (os.path.basename(self.video), self.reason))
        return list(self._tracks)

    def __bool__(self):
        raise TypeError(
            u"embedded_subtitles() is not a yes/no answer, and every result "
            u"would read as yes. Ask `.ok` whether the video could be read, "
            u"then look at `.tracks` -- e.g. `any(t.text and not t.forced "
            u"for t in subs.tracks)`.")

    def __repr__(self):
        if not self.ok:
            return u"EmbeddedSubtitles(%s, unreadable: %s)" % (
                os.path.basename(self.video), self.reason)
        return u"EmbeddedSubtitles(%s, %d track%s%s)" % (
            os.path.basename(self.video), len(self._tracks),
            u"" if len(self._tracks) == 1 else u"s",
            u" in %s" % self.lang if self.lang else u"")


def embedded_subtitles(video, lang=None):
    u"""The subtitle tracks inside `video`. -> `EmbeddedSubtitles`

    Never raises for a video it cannot read -- that is `ok=False` with the
    reason. Raises only for a caller's mistake: a `lang` it does not recognise.

    `lang`
        only tracks in this language. `ja`, `jpn`, `JA` and `ja-JP` all mean
        Japanese, exactly as for `Scan.unpaired(lang=)`; `und` asks for tracks
        whose language is undetermined. ⛔ An unrecognised tag raises
        `ValueError` rather than matching nothing, because *"no Japanese
        track"* is an answer a caller acts on.
        ⚠ Filtered, an EMPTY list means *no track in this language* -- a
        video with only English subtitles and one with none look the same.
        To ask whether a video has ANY subtitle track, call without `lang`.

    ⚠ `ok=False` also covers a Matroska file that ends before its own header
    says it does -- a download in progress, or a cut -- because its track list
    describes a file that is not all there.

    ⭐ Reads the container HEADER only (`timing=False`): a Matroska file costs a
    few hundred bytes and never a cluster. Any other container goes through
    ffmpeg, and without ffmpeg the answer is `ok=False` with a reason that says
    how to get it -- never an empty list.
    """
    want = None if lang is None else _language_asked_for(lang)
    # `fsdecode` so a bytes path names the same file a str path would.
    path = os.fsdecode(os.fspath(video))
    info = _container.read(path, timing=False)
    if not info.ok:
        return EmbeddedSubtitles(
            path, False, info.reason or u"the video could not be read", want)
    if info.incomplete:
        # 🚨 RUNBOOK 3f, found by an adversarial pass: a file cut off or still
        # downloading read as a whole one with no (or fewer) tracks. Its header
        # describes a file that is not all there, so nothing is claimed.
        return EmbeddedSubtitles(path, False, info.incomplete, want)
    if not info.tracks:
        # 🚨 AND THE SAME DEFECT ONE RUNG DOWN, found re-running the adversary's
        # reproductions against the fix: when the native reader refuses a
        # damaged Matroska file, ffprobe often answers exit 0 with NO streams
        # at all -- which would read, again, as "has no subtitle tracks". A
        # video with no readable track of ANY kind is not a video with no
        # subtitles; it is one nobody could read.
        return EmbeddedSubtitles(
            path, False,
            u"no track of any kind could be read from %s -- it is damaged, or "
            u"not a video%s" % (os.path.basename(path),
                                u" (%s)" % u"; ".join(info.warnings)
                                if info.warnings else u""), want)
    tracks = []
    for track in info.subtitle_tracks:
        code = _track_language(track.language)
        if want is not None and code != want:
            continue
        tracks.append(EmbeddedSubtitle(
            index=track.index, lang=code, tag=track.language or u"",
            codec=track.codec or u"",
            text=_container.is_text_codec(track.codec),
            bitmap=_container.is_bitmap_codec(track.codec),
            forced=bool(track.forced), default=bool(track.default),
            name=track.name or u""))
    return EmbeddedSubtitles(path, True, u"", want, tracks)


def _track_language(tag):
    u"""A container's language string as a code. -> `ja` · `en` · `und`

    ⚠ Only the PRIMARY subtag decides. A container's language field IS a
    language tag (BCP-47 in Matroska), so `ja-Latn-JP` is Japanese -- unlike a
    filename, where a hyphen is an ordinary character and `sidecar` is strict
    about it on purpose. An empty or unrecognised tag is `und`: undetermined,
    never guessed.
    """
    token = (tag or u"").strip().lower()
    if not token:
        return _sidecar.UND
    primary = token.split(u"-", 1)[0]
    code = _sidecar._language_of(primary)
    return code if code is not None else _sidecar.UND
