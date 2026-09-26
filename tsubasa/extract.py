# -*- coding: utf-8 -*-
u"""Take an embedded TEXT subtitle track out of a Matroska file, in its own format.

RUNBOOK step 3h, for hato (its RUNBOOK LAYER 14, ruled by Sonic 2026-09-25): a video that
already carries a Japanese text track can have it SAVED BESIDE IT, as a file -- for a tool
that only ever reads subtitle files.

    from tsubasa import embedded_subs, extract_subtitle
    subs = embedded_subs(video, lang="ja")
    got = extract_subtitle(video, subs.tracks[0])
    if got.ok:
        write got.data to "<video stem>.ja.<got.ext>"

🚨 NEVER CONVERTED (`LEDGER-HOT.md`: *never re-encode a subtitle file*). An `S_TEXT/UTF8`
track comes out as `.srt`, `S_TEXT/ASS` as `.ass` with its header and styles, `S_TEXT/SSA`
as `.ssa` (and their legacy ids `S_TEXT/ASCII`, `S_ASS`, `S_SSA`) -- each event's text
exactly as the file stores it, never decoded and re-encoded; only its trailing line break
is left to the framing. Only the FRAMING is written here: an SRT cue's number and times,
an ASS event's `Dialogue:` line and times, which is what a Matroska muxer took apart when
it stored them -- and an ASS header's sections go back where the file had them, the
events under `[Events]` and anything after it (Aegisub's data, `[Fonts]`) after them.

⛔ REFUSED, WITH A REASON, NEVER GUESSED -- `ok=False`, and nothing to write:
  * an empty file, or one that is not Matroska. MP4's `mov_text` has no file format of its
    own, so taking it out would mean CONVERTING it -- and hato downloads instead;
  * a WebVTT track (its cue settings live in BlockAdditions, which this does not read yet),
    an image track (it has no text), or any other codec;
  * an encrypted track, one compressed with bzlib or lzo, or an encoding of a kind
    Matroska does not define;
  * a laced subtitle block; an ASS/SSA track with no header (its styles are not in the
    file, and none are invented);
  * a file that ends before its own header says it does, or that cannot be read to its
    end -- a download still filling a sparse file reads as the right size with holes in it
    -- and an event holding NUL bytes, which text never does: *"unreadable"* is never a
    shorter subtitle, and a track with no events at all is never an empty file.

⭐ WRITTEN BY TSUBASA, WHEN ASKED (`write=True`): hato rules that the only write in a
media folder is tsubasa's (its Whitelist 1, ruled by Sonic 2026-09-17), and a caller that
wrote the bytes itself would be a second writer there. So `extract_subtitle` writes the
file as tsubasa names every file it writes -- `<video basename>.<lang>[.forced].<ext>`
(`sidecar.output_name`) -- beside the video or in `out_dir`, atomically, and NEVER over a
file that is there: `write_failed` and the reason instead, `ok` still True -- a write that
did not land is not an extraction that failed.

⚠ A block with no duration of its own takes the track's DefaultDuration, else it is a
zero-length event -- start = end, which is what the file says and what ffmpeg writes (the
3h pass: one such line in 288 used to refuse the whole track). A time before zero is
written as zero.

⚠ WHAT IT CAN NEVER DO. An ASS track's FONTS are attachments of the VIDEO, not part of the
track, so they do not come along -- the words and the styles do. And the lines are the
track's own: a subtitle taken out will not match a jimaku download line for line (Sonic's
own note, 2026-09-25).
"""
import os
import zlib

from .container import mkv as _mkv

#: The text codecs taken out, and the file each becomes. ⛔ An allow-list: anything else
#: is refused by name rather than written in a guessed format. ⚠ The legacy ids are the
#: same framing (the 3h pass: `embedded_subs` called them text and ffmpeg copies them).
FORMATS = {u"S_TEXT/UTF8": u"srt", u"S_TEXT/ASCII": u"srt",
           u"S_TEXT/ASS": u"ass", u"S_ASS": u"ass",
           u"S_TEXT/SSA": u"ssa", u"S_SSA": u"ssa"}

#: What an ASS/SSA header's [Events] section is given when CodecPrivate carries none.
_EVENTS_FORMAT = {
    u"ass": b"Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    u"ssa": b"Format: Marked, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
}

#: One event past this, once its compression is undone, is damage -- or a bomb.
MAX_EVENT = _mkv.MAX_PAYLOAD
MAX_HEADER = _mkv.MAX_CODEC_PRIVATE


class ExtractedSubtitle(object):
    u"""A subtitle track taken out of a video -- or why it could not be.

    `ok`      True when `data` is a whole subtitle file, ready to write
    `reason`  why not, when `ok` is False -- in words a person can act on
    `data`    the file's bytes (`b""` when not ok)
    `ext`     `srt` · `ass` · `ssa` -- the track's own format (`u""` when not ok)
    `codec`   the container's codec name, as read
    `index`   the track's position in the video, as `embedded_subs()` numbers it
    `cues`    how many events it holds
    `lang`    the track's language, resolved (`ja`), `und` when it states none
    `output_path`   the file written, when `write=True` and it landed; else None
    `write_failed`  True when a write was asked and did not land -- `reason` says why,
                    and `ok` and `data` still stand
    `notes`   anything the name had to change, said (`sidecar.output_name`)

    ⛔ `if not got:` RAISES, as `EmbeddedSubtitles` does: ask `.ok`. A falsy answer would
    let *"could not take it out"* and *"took out nothing"* read the same.
    """

    __slots__ = ("video", "ok", "reason", "data", "ext", "codec", "index", "cues", "lang",
                 "output_path", "write_failed", "notes", "_forced")

    def __init__(self, video, ok, reason=u"", data=b"", ext=u"", codec=u"", index=None,
                 cues=0, lang=u"und", forced=False):
        self.video = video
        self.ok = bool(ok)
        self.reason = reason
        self.data = data
        self.ext = ext
        self.codec = codec
        self.index = index
        self.cues = cues
        self.lang = lang
        self.output_path = None
        self.write_failed = False
        self.notes = ()
        self._forced = bool(forced)

    def __bool__(self):
        raise TypeError(u"ask ExtractedSubtitle.ok -- its truth is not whether it worked")

    def __repr__(self):
        if self.ok:
            return u"<ExtractedSubtitle track %s: %d event(s) as .%s>" % (
                self.index, self.cues, self.ext)
        return u"<ExtractedSubtitle track %s: not taken out -- %s>" % (self.index, self.reason)


class _Refusal(Exception):
    u"""A track this module will not write, and why."""


def extract_subtitle(video, track, write=False, out_dir=None):
    u"""Take subtitle `track` out of `video`, in its own format. -> `ExtractedSubtitle`

    `track`  an `EmbeddedSubtitle` from `embedded_subs(video)`, or its `index` (an int).
             ⚠ A track object is CHECKED against the video's own track at that index --
             codec, language and title -- and refused when they differ: a track read
             from another video, or by ffmpeg's reader, which can number them otherwise.

    `write`  ⭐ tsubasa writes the file: `<video basename>.<lang>[.forced].<ext>` beside the
             video, or in `out_dir` -- atomically, and ⛔ never over a file that is there
             (`write_failed`, the reason, and `ok` still True). Default: nothing written.

    ⛔ NEVER RAISES for a video or a track it cannot take out -- that is `ok=False` with
    the reason (the 3h pass found a locked file and a hostile index raising). Raises only
    `TypeError`, for a caller's mistake: a `track` that is neither. ⭐ Matroska only,
    through tsubasa's own reader: no ffmpeg, and no byte of the video read beyond the
    headers, every block's header, and the subtitle's own blocks.
    """
    path = os.fsdecode(os.fspath(video))
    index, given = _track_asked_for(track)
    try:
        got = _extract(path, index, given)
        if write and got.ok:
            _write(got, path, out_dir)
        return got
    except _mkv.ContainerError as exc:
        return ExtractedSubtitle(path, False, u"the video could not be read: %s" % exc,
                                 index=index)
    except (OSError, ValueError, OverflowError, MemoryError) as exc:
        return ExtractedSubtitle(
            path, False, u"%s could not be read (%s: %s)"
            % (os.path.basename(path), type(exc).__name__, exc), index=index)


def _track_asked_for(track):
    u"""-> (index, the track object or None). ⛔ `True` is not track 1 and `2.9` is not
    track 2 (the 3h pass): only an int, or a track object carrying one."""
    index = getattr(track, u"index", track)
    if isinstance(index, bool) or not isinstance(index, int):
        raise TypeError(u"track must be an EmbeddedSubtitle or its index (an int), not %r"
                        % (track,))
    return index, (None if index is track else track)


def _extract(path, index, given):
    if not os.path.isfile(path):
        return ExtractedSubtitle(path, False, u"there is no file at %s" % path, index=index)
    name = os.path.basename(path)
    if os.path.getsize(path) == 0:
        return ExtractedSubtitle(path, False, u"%s is empty -- there is nothing in it to "
                                 u"take out" % name, index=index)
    with open(path, u"rb") as fh:
        head = fh.read(12)
    if not _mkv.looks_like_matroska(head[:4]):
        if head[4:8] == b"ftyp":
            why = (u"%s is an MP4 file -- its subtitles have no file format of their own, "
                   u"so taking them out would mean CONVERTING them; tsubasa takes "
                   u"subtitles out of MKV only" % name)
        else:
            why = (u"%s is not a Matroska (MKV) file -- tsubasa takes subtitles out of MKV "
                   u"only" % name)
        return ExtractedSubtitle(path, False, why, index=index)
    header = _mkv.read(path, timing=False)
    tracks = header.get(u"tracks") or []
    if not 0 <= index < len(tracks):
        return ExtractedSubtitle(path, False, u"the video has no track %d" % index,
                                 index=index)
    entry = tracks[index]
    codec = entry.get(u"codec") or u""
    if given is not None:
        differs = _differs(given, entry)
        if differs:
            return ExtractedSubtitle(
                path, False, u"track %d of %s is not the track given (%s) -- read its "
                u"tracks again with embedded_subs()" % (index, name, differs),
                codec=codec, index=index)
    if entry.get(u"type") != _mkv.SUBTITLE:
        return ExtractedSubtitle(path, False, u"track %d is not a subtitle track" % index,
                                 codec=codec, index=index)
    ext = FORMATS.get(codec)
    if ext is None:
        return ExtractedSubtitle(path, False, _unsupported(codec), codec=codec, index=index)
    try:
        raw = _mkv.read_payloads(path, entry[u"number"])
        blocks, private = _decode(raw[u"encodings"], raw[u"blocks"], raw[u"codec_private"])
        if not blocks:
            raise _Refusal(u"track %d holds no subtitle events -- there is nothing to take "
                           u"out" % index)
        if any(laced for _t, _d, _p, laced in blocks):
            raise _Refusal(u"a subtitle event in track %d is laced -- several frames under "
                           u"one header, which is not taken apart here" % index)
        for ticks, _d, payload, _l in blocks:
            if b"\x00" in payload:
                raise _Refusal(
                    u"an event of track %d holds empty bytes -- a stretch of the file has "
                    u"not been written yet (a download in progress?) or is damaged, so the "
                    u"track is not all there" % index)
        timescale = raw[u"timescale"]
        blocks = _with_durations(blocks, raw.get(u"default_duration"), timescale)
        if ext == u"srt":
            data = _as_srt(blocks, timescale)
        else:
            if not (private or b"").strip():
                raise _Refusal(u"track %d is %s with no header -- its styles are not in the "
                               u"file, and none are invented" % (index, codec))
            data = _as_ass(blocks, timescale, private, ext)
    except _Refusal as exc:
        return ExtractedSubtitle(path, False, u"%s" % exc, codec=codec, index=index)
    except _mkv.ContainerError as exc:
        return ExtractedSubtitle(path, False, u"track %d could not be read: %s" % (index, exc),
                                 codec=codec, index=index)
    from .embedded import _track_language
    lang = _track_language(entry.get(u"language_bcp47") or entry.get(u"language"))
    return ExtractedSubtitle(path, True, u"", data, ext, codec, index, len(blocks),
                             lang=lang, forced=entry.get(u"forced"))


def _write(got, path, out_dir):
    u"""Write `got.data` under tsubasa's name for it. ⛔ Never over a file that is there;
    a write that does not land sets `write_failed` -- `ok` and `data` stand."""
    from .paths import atomic_write_bytes
    from .sidecar import output_name
    folder = os.fsdecode(os.fspath(out_dir)) if out_dir else os.path.dirname(path)
    stem = os.path.splitext(os.path.basename(path))[0]
    name, notes = output_name(stem, got.lang, got.ext,
                              flags=(u"forced",) if got._forced else ())
    got.notes = tuple(notes)
    target = os.path.join(folder, name)
    if os.path.lexists(target):
        got.write_failed = True
        got.reason = (u"%s is already there -- nothing was written over it"
                      % os.path.basename(target))
        return
    try:
        atomic_write_bytes(target, got.data)
    except OSError as exc:
        got.write_failed = True
        got.reason = u"%s could not be written: %s" % (os.path.basename(target), exc)
        return
    got.output_path = target


def _differs(given, entry):
    u"""What differs between a track object and the video's own entry. -> words or u\"\""""
    language = entry.get(u"language_bcp47") or entry.get(u"language") or u""
    for what, theirs, ours in ((u"codec", getattr(given, u"codec", None), entry.get(u"codec")),
                               (u"language", getattr(given, u"tag", None), language),
                               (u"title", getattr(given, u"name", None), entry.get(u"name"))):
        if theirs is not None and (theirs or u"") != (ours or u""):
            return u"its %s is %s, not %s" % (what, ours or u"none", theirs or u"none")
    return u""


def _unsupported(codec):
    if codec == u"S_TEXT/WEBVTT":
        return (u"a WebVTT track keeps its cue settings beside its text, and tsubasa does "
                u"not take those out yet")
    from .container import is_bitmap_codec
    if is_bitmap_codec(codec):
        return u"an image subtitle (%s) has no text to take out" % codec
    return u"tsubasa does not take a %s track out as a file" % (codec or u"codec-less")


def _decode(encodings, blocks, private):
    u"""Undo the track's ContentEncodings. -> (blocks, codec_private)

    ⚠ A muxer applies encodings in ascending ContentEncodingOrder, so they are undone in
    DESCENDING order. `scope` bit 1 is the frames, bit 2 the CodecPrivate. ⛔ Each
    decompressed event is bounded (`MAX_EVENT`) -- a 40 KB event inflating to 42 MB made a
    167 MB file, `ok=True` (the 3h pass)."""
    for enc in sorted(encodings, key=lambda e: e[u"order"], reverse=True):
        if enc[u"encrypted"] or enc[u"type"] == 1:
            raise _Refusal(u"the subtitle track is encrypted")
        if enc[u"type"] != 0:
            raise _Refusal(u"the subtitle track uses an encoding of a kind Matroska does not "
                           u"define (type %s)" % enc[u"type"])
        algo = enc[u"algo"]
        if algo == 0:
            def undo(data, what, limit):
                return _inflate(data, what, limit)
        elif algo == 3:
            stripped = enc[u"settings"]

            def undo(data, what, limit, stripped=stripped):
                return stripped + data
        else:
            raise _Refusal(u"the subtitle track is compressed with %s, which is not undone "
                           u"here" % {1: u"bzlib", 2: u"lzo"}.get(algo, u"algorithm %s" % algo))
        if enc[u"scope"] & 1:
            blocks = [(t, d, undo(p, u"a subtitle event", MAX_EVENT), l)
                      for t, d, p, l in blocks]
        if enc[u"scope"] & 2 and private is not None:
            private = undo(private, u"the subtitle track's header", MAX_HEADER)
    for _t, _d, payload, _l in blocks:
        if len(payload) > MAX_EVENT:
            raise _Refusal(u"a subtitle event holds %d bytes -- damage, not a line of text"
                           % len(payload))
    return blocks, private


def _inflate(data, what, limit):
    u"""zlib, bounded. ⚠ `zlib.error` is not an IOError (LEDGER-HOT): caught here."""
    engine = zlib.decompressobj()
    try:
        out = engine.decompress(data, limit + 1)
    except zlib.error as exc:
        raise _Refusal(u"%s could not be decompressed (%s)" % (what, exc))
    if len(out) > limit:
        raise _Refusal(u"%s decompresses to more than %d bytes -- damage, not text"
                       % (what, limit))
    if not engine.eof:
        raise _Refusal(u"%s could not be decompressed (it is cut off)" % what)
    return out


def _with_durations(blocks, default_ns, timescale):
    u"""Every block's duration in ticks: its own, else the track's DefaultDuration, else
    0 -- a zero-length event, as the file has it (the 3h pass: ffmpeg writes a line with no
    BlockDuration as start = end, and refusing the track lost 5.1% of real ASS files)."""
    default = int(round(default_ns / float(timescale))) if default_ns else 0
    return [(t, default if d is None else d, p, l) for t, d, p, l in blocks]


def _ns(ticks, timescale):
    return ticks * timescale


def _srt_time(ns):
    ms = (max(ns, 0) + 500000) // 1000000
    hours, ms = divmod(ms, 3600000)
    minutes, ms = divmod(ms, 60000)
    seconds, ms = divmod(ms, 1000)
    return (u"%02d:%02d:%02d,%03d" % (hours, minutes, seconds, ms)).encode(u"ascii")


def _ass_time(ns):
    cs = (max(ns, 0) + 5000000) // 10000000
    hours, cs = divmod(cs, 360000)
    minutes, cs = divmod(cs, 6000)
    seconds, cs = divmod(cs, 100)
    return (u"%d:%02d:%02d.%02d" % (hours, minutes, seconds, cs)).encode(u"ascii")


def _newline(samples):
    u"""The line break the TRACK uses, so the framing written around its bytes matches
    them. ⚠ The track's own bytes are never changed to match the framing."""
    return b"\r\n" if any(b"\r\n" in s for s in samples if s) else b"\n"


def _as_srt(blocks, timescale):
    u"""SRT: numbered cues in time order -- each event's text as stored."""
    ordered = sorted(enumerate(blocks), key=lambda item: (item[1][0], item[0]))
    nl = _newline(p for _i, (_t, _d, p, _l) in ordered)
    out = []
    for n, (_i, (ticks, duration, payload, _laced)) in enumerate(ordered, 1):
        out.append(b"%d%s%s --> %s%s%s%s%s" % (
            n, nl, _srt_time(_ns(ticks, timescale)),
            _srt_time(_ns(ticks + duration, timescale)), nl,
            payload.rstrip(b"\r\n"), nl, nl))
    return b"".join(out)


def _split_header(private, ext, nl):
    u"""An ASS/SSA header, split where its events go. -> (head, tail)

    🚨 THE 3h PASS: the header was written whole and the events after it -- so in 1.17% of
    real ASS files every Dialogue landed under `[Aegisub Extradata]`, `[Aegisub Project
    Garbage]` or `[Fonts]`, and pysubs2 read 0 events; under `[Fonts]` libass drew nothing.
    ⭐ ffmpeg's rule, which reproduces the source file line for line: the head runs to the
    end of the `Format:` line after `[Events]`; everything after it -- blank lines
    included -- follows the events."""
    at = private.find(b"[Events]")
    if at < 0:
        return (private.rstrip(b"\r\n") + nl + nl + b"[Events]" + nl + _EVENTS_FORMAT[ext]
                + nl, b"")
    fmt = private.find(b"Format:", at)
    if fmt < 0:
        eol = private.find(b"\n", at)
        split = len(private) if eol < 0 else eol + 1
        head = private[:split]
        if not head.endswith(b"\n"):
            head += nl
        return head + _EVENTS_FORMAT[ext] + nl, private[split:]
    eol = private.find(b"\n", fmt)
    split = len(private) if eol < 0 else eol + 1
    head, tail = private[:split], private[split:]
    if not head.endswith(b"\n"):
        head += nl
    return head, tail


def _marked(head):
    u"""Does the header's [Events] Format line open with `Marked` (SSA v4)? -> bool

    ⭐ Then each line is `Dialogue: Marked=0,...` -- the source's own form, which a muxer
    stores as `0`. Read from the Format line, not from `ScriptType`'s spelling: ffmpeg
    keys on `ScriptType: v4.00` exactly and wrote `0` for three real sources that say
    `Marked=0` (the 3h pass)."""
    at = head.find(b"[Events]")
    fmt = head.find(b"Format:", max(at, 0))
    if at < 0 or fmt < 0:
        return False
    first = head[fmt + len(b"Format:"):].split(b",", 1)[0]
    return first.strip().lower() == b"marked"


def _as_ass(blocks, timescale, private, ext):
    u"""ASS/SSA: the header the track carries, each event back in its ReadOrder, then the
    rest of the header after them.

    A Matroska ASS block is `ReadOrder,Layer,Style,Name,MarginL,MarginR,MarginV,Effect,
    Text` -- the Dialogue line with its times taken out and its original position put
    first. The times come back from the block; the rest is the event's own bytes."""
    nl = _newline([private] + [p for _t, _d, p, _l in blocks])
    head, tail = _split_header(private, ext, nl)
    marked = _marked(head)
    events = []
    for position, (ticks, duration, payload, _laced) in enumerate(blocks):
        fields = payload.split(b",", 8)
        if len(fields) < 9:
            raise _Refusal(u"an ASS event is not in Matroska's layout (%d field(s), "
                           u"expected 9)" % len(fields))
        try:
            order = int(fields[0])
        except ValueError:
            raise _Refusal(u"an ASS event's ReadOrder is not a number: %s"
                           % fields[0][:20].decode(u"utf-8", u"replace"))
        first = fields[1]
        if marked and not first.startswith(b"Marked="):
            first = b"Marked=" + first
        line = (b"Dialogue: " + first + b"," + _ass_time(_ns(ticks, timescale)) + b","
                + _ass_time(_ns(ticks + duration, timescale)) + b"," + b",".join(fields[2:]))
        events.append((order, position, line.rstrip(b"\r\n")))
    events.sort(key=lambda e: (e[0], e[1]))
    return head + b"".join(e[2] + nl for e in events) + tail


__all__ = ["ExtractedSubtitle", "extract_subtitle", "FORMATS"]
