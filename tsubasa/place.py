# -*- coding: utf-8 -*-
u"""Place a subtitle beside a video, UNTOUCHED AND UNTIMED.

RUNBOOK step 3i, for hato (its RUNBOOK LAYER 15, signed off by Sonic 2026-09-26): a video
with NO subtitle track has nothing a subtitle could be timed against until the audio path
exists (B6). hato's opt-in road for such a video picks a subtitle by its NAME and asks
tsubasa to put it beside the video as it is -- because hato's Whitelist 1 (ruled
2026-09-17) makes the only write in a media folder tsubasa's.

    from tsubasa import place_subtitle
    got = place_subtitle(video, u"[Group] Show - 01.ja.ass", write=True, lang_tag=u"jpn")
    if got.ok and got.output_path:
        ...                         # <video stem>.jpn.ass -- the subtitle's own bytes

🚨 NEVER TIMED, NEVER CONVERTED, NEVER RE-ENCODED: the bytes written are the bytes read
(`LEDGER-HOT.md`). ⛔ It cannot tell whether the subtitle belongs to the video -- that is
the caller's claim, and the caller's to say out loud.

⭐ `lang_tag` WRITES THE LANGUAGE CODE AS GIVEN. hato marks a file nobody timed
`<video>.jpn.<ext>`, beside `<video>.ja.<ext>` for one tsubasa timed: both read as Japanese
to every player measured (mpv 0.33 under its defaults and under Sonic's config, VLC) and
to `parse_subtitle_name`, while `output_name` alone canonicalises `jpn` back to `ja` and
would erase the mark. ⛔ Refused unless it resolves to the subtitle's own language.

⛔ REFUSED, WITH A REASON -- `ok=False`, and nothing written:
  * a subtitle whose NAME gives no language: written untagged as `<video>.<ext>`, it reads
    as no language at all, and a caller like hato fetches again for ever (hato's
    `LEDGER-HOT.md`). Name it `<stem>.<lang>.<ext>`;
  * an empty file, one over `MAX_BYTES`, or one whose extension is not a subtitle's;
  * a video that is not there, or that is itself a subtitle (the arguments swapped);
  * a subtitle that already IS the file it would be written as;
  * a `lang_tag` that does not name the subtitle's own language.

⭐ WRITTEN AS EVERY FILE tsubasa PUTS IN A MEDIA FOLDER FOR A CALLER IS -- `_name_for` then
`_write_new`, which `extract_subtitle(write=True)` calls too, so the two can never write
differently: under tsubasa's name for it, atomically, and ⛔ NEVER over a file that is
there -- not even one that lands while it is being written (hato 14z, C3). That is
`write_failed` and the reason, with `ok` still True: a write that did not land is not a
placing that was refused. A folder that refuses a new file fails at once (hato 14z, A-1:
the writer under it used to spin for days) and comes back the same way.
"""
import os

from . import paths as _paths
from . import sidecar as _sidecar

#: The extensions a subtitle given here may carry -- text subtitles, each written back in
#: its own format. ⛔ An image subtitle has no file of its own to place beside a video.
EXTENSIONS = (u"srt", u"ass", u"ssa", u"vtt")

#: Past this a "subtitle" is damage, or not a subtitle -- hato's own bound on a file it will
#: read whole (`present.READ_LIMIT`, measured over 25,153 real subtitles: the largest
#: 20.7 MB, ONE past 16).
MAX_BYTES = 16 * 1024 * 1024


class PlacedSubtitle(object):
    u"""A subtitle placed beside a video -- or why it could not be.

    `ok`            True when the subtitle can be placed: its name gives a language, it
                    is a subtitle, and the video is there
    `reason`        why not, when `ok` is False; why it was not written, when
                    `write_failed`; and with `write=False`, that the name is already
                    taken (15z, A8) -- in words a person can act on
    `output_path`   the file written, when `write=True` and it landed; else None
    `target`        ⭐ hato's 15z (B5): the file it is -- or, with `write=False`, WOULD BE --
                    written as, once a name was made; else None. A caller that must find
                    the file again asks this BEFORE writing it
    `write_failed`  True when a write was asked and did not land -- `reason` says why,
                    and `ok` stands
    `notes`         anything the name had to change, said (`sidecar.output_name`), and
                    anything the write could not promise
    `ext`           the subtitle's own format (`srt` · `ass` · `ssa` · `vtt`)
    `lang`          its language, resolved from its NAME (`ja`)

    ⛔ `if not got:` RAISES, as `ExtractedSubtitle` does: ask `.ok`. A falsy answer would
    let *"could not place it"* and *"placed nothing"* read the same.
    """

    __slots__ = ("video", "subtitle", "ok", "reason", "output_path", "target",
                 "write_failed", "notes", "ext", "lang")

    def __init__(self, video, subtitle, ok, reason=u"", ext=u"", lang=_sidecar.UND):
        self.video = video
        self.subtitle = subtitle
        self.ok = bool(ok)
        self.reason = reason
        self.output_path = None
        self.target = None
        self.write_failed = False
        self.notes = ()
        self.ext = ext
        self.lang = lang

    def __bool__(self):
        raise TypeError(u"ask PlacedSubtitle.ok -- its truth is not whether it worked")

    def __repr__(self):
        if not self.ok:
            return u"<PlacedSubtitle %s: not placed -- %s>" % (
                os.path.basename(self.subtitle), self.reason)
        if self.output_path:
            return u"<PlacedSubtitle placed as %s>" % os.path.basename(self.output_path)
        if self.write_failed:
            return u"<PlacedSubtitle not written -- %s>" % self.reason
        if self.reason:
            return u"<PlacedSubtitle %s: %s>" % (os.path.basename(self.subtitle), self.reason)
        return u"<PlacedSubtitle %s: can be placed (.%s, %s)>" % (
            os.path.basename(self.subtitle), self.ext, self.lang)


def place_subtitle(video, subtitle, write=False, out_dir=None, lang_tag=None):
    u"""Put `subtitle` beside `video`, untouched and untimed. -> `PlacedSubtitle`

    `video`     the video it is for -- its basename names the file written
    `subtitle`  a subtitle FILE whose name gives its language: `<stem>.<lang>.<ext>`
                (hato hands over `<jimaku stem>.ja.<ext>`)
    `write`     ⭐ tsubasa writes the file: `<video stem>.<lang>[.flags].<ext>` beside the
                video, or in `out_dir` -- atomically, and ⛔ never over a file that is
                there (`write_failed`, the reason, and `ok` still True). Default: every
                check made, nothing written.
    `lang_tag`  the language code to write, as given (`jpn`) -- ⛔ refused unless it
                resolves to the subtitle's own language. Default: the canonical code.

    ⛔ NEVER RAISES for a subtitle or a video it cannot place -- that is `ok=False` with the
    reason, and a write that does not land is `write_failed`. Raises only `TypeError`, for a
    caller's mistake: a path that is not one, or a `lang_tag` that is not text.
    """
    video = os.fsdecode(os.fspath(video))
    subtitle = os.fsdecode(os.fspath(subtitle))
    if lang_tag is not None and not isinstance(lang_tag, str):
        raise TypeError(u"lang_tag must be a language code such as 'jpn', not %r"
                        % (lang_tag,))
    got, data, flags = _checked(video, subtitle, lang_tag)
    if not got.ok:
        return got
    if out_dir is not None and u"\x00" in os.fsdecode(os.fspath(out_dir)):
        # ⭐ hato's 15z (A9) -- no file system allows one, and every path call RAISED on it
        return _refused(video, subtitle, u"the folder given holds a NUL character -- no file "
                                         u"system allows one in a name")
    try:
        target, notes = _name_for(video, out_dir, got.lang, got.ext, flags, lang_tag)
    except ValueError as exc:
        return _refused(video, subtitle, u"no name could be made for it: %s" % exc)
    got.notes = tuple(notes)
    got.target = target
    if _same_file(subtitle, target):
        return _refused(video, subtitle,
                        u"%s already IS the file it would be placed as -- there is nothing "
                        u"to place" % os.path.basename(subtitle))
    if write:
        _write_new(got, target, data)
    elif os.path.lexists(target):
        # ⭐ hato's 15z (A8) -- every check made means THIS one too: *can be placed* over a
        # name already taken was a promise the write would break
        got.reason = (u"%s is already there -- a write would put nothing over it"
                      % os.path.basename(target))
    return got


def _refused(video, subtitle, reason):
    return PlacedSubtitle(video, subtitle, False, reason)


def _checked(video, subtitle, lang_tag):
    u"""Everything that decides whether `subtitle` may be placed at all.
    -> (PlacedSubtitle, its bytes or None, its flags)"""
    name = os.path.basename(subtitle)
    if not os.path.isfile(subtitle):
        return _refused(video, subtitle, u"there is no file at %s" % subtitle), None, ()
    side = _sidecar.parse(name)
    if side.ext not in EXTENSIONS:
        return _refused(video, subtitle,
                        u"%s is not a subtitle file tsubasa places (%s)"
                        % (name, u" ".join(u"." + e for e in EXTENSIONS))), None, ()
    if not side.known:
        return _refused(video, subtitle,
                        u"%s gives no language in its name -- placed untagged as the "
                        u"video's own name, it would read as no language at all. Name it "
                        u"<name>.<language>.<ext>, for example .ja.%s"
                        % (name, side.ext)), None, ()
    if lang_tag is not None:
        written = _sidecar.check_code(lang_tag, side.lang)
        if written is not None:
            return _refused(video, subtitle, written), None, ()
    if not os.path.isfile(video):
        return _refused(video, subtitle, u"there is no video at %s" % video), None, ()
    video_ext = os.path.splitext(video)[1][1:].lower()
    if video_ext in EXTENSIONS:
        return _refused(video, subtitle,
                        u"%s is a subtitle, not a video -- the video comes first, the "
                        u"subtitle second" % os.path.basename(video)), None, ()
    try:
        with open(subtitle, u"rb") as fh:
            data = fh.read(MAX_BYTES + 1)
    except OSError as exc:
        return _refused(video, subtitle, u"%s could not be read (%s: %s)"
                        % (name, type(exc).__name__, exc)), None, ()
    if not data:
        return _refused(video, subtitle, u"%s is empty -- there is nothing in it to place"
                        % name), None, ()
    if len(data) > MAX_BYTES:
        return _refused(video, subtitle,
                        u"%s is over %d MB -- damage, or not a subtitle" % (
                            name, MAX_BYTES // (1024 * 1024))), None, ()
    return (PlacedSubtitle(video, subtitle, True, ext=side.ext, lang=side.lang), data,
            tuple(side.flags))


def _same_file(subtitle, target):
    u"""Is `subtitle` the very file `target` names? -> bool. ⚠ `samefile` and not the
    text: on Windows `Show.JA.srt` and `show.ja.srt` are one file."""
    try:
        return os.path.exists(target) and os.path.samefile(subtitle, target)
    except OSError:
        return False


# ---------------------------------------------------------------------------
# ⭐ THE ONE WRITE tsubasa MAKES IN A MEDIA FOLDER FOR A CALLER -- shared with extract
# ---------------------------------------------------------------------------

def _name_for(video, out_dir, lang, ext, flags=(), code=None):
    u"""Where a file for `video` goes, under tsubasa's name for it. -> (path, notes)

    `<video basename>.<lang>[.flags].<ext>` (`sidecar.output_name`), beside the video or in
    `out_dir`. `code` writes the language code as given (3i). Raises `ValueError` when no
    name can be made (`NameTooLong`, or a `code` for another language)."""
    folder = os.fsdecode(os.fspath(out_dir)) if out_dir else os.path.dirname(video)
    stem = os.path.splitext(os.path.basename(video))[0]
    name, notes = _sidecar.output_name(stem, lang, ext, flags=flags, code=code)
    return os.path.join(folder, name), list(notes)


def _write_new(result, target, data):
    u"""Write `data` as `target` for `result`. -> None; sets `output_path` when it landed.

    ⛔ Never over a file that is there -- `paths.write_new_bytes` refuses in the same step
    that publishes it (hato 14z, C3). A write that does not land sets `write_failed` and
    says why; the caller's `ok` and its bytes stand. ⛔ Nothing raised past here: an
    `OSError` is a destination that failed, not a subtitle that did."""
    name = os.path.basename(target)
    try:
        more = _paths.write_new_bytes(target, data)
    except _paths.AlreadyThere as exc:
        result.write_failed = True
        result.reason = u"%s is already there -- nothing was written over it%s" % (
            name, _leftover(exc))
        return
    except OSError as exc:
        result.write_failed = True
        result.reason = u"%s could not be written: %s%s" % (name, _why(exc), _leftover(exc))
        return
    result.notes = tuple(result.notes) + tuple(more)
    result.output_path = target


def _why(exc):
    u"""An `OSError` in words a person can act on. ⭐ hato's 15z (A11): never the TEMPORARY's
    path (a file that never existed for them) -- the system's own sentence, and the folder
    when a file stands where the folder should be."""
    words = exc.strerror or u"%s" % exc
    if isinstance(exc, NotADirectoryError) and exc.filename:
        return u"%s (%s)" % (words, exc.filename)
    return words


def _leftover(exc):
    u"""A temporary the writer could not remove, said after the reason (15z, A3). -> text"""
    left = getattr(exc, "leftover", None)
    return u"; %s" % left if left else u""


__all__ = ["PlacedSubtitle", "place_subtitle", "EXTENSIONS", "MAX_BYTES"]
