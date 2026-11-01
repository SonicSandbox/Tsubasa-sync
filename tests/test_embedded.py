# -*- coding: utf-8 -*-
"""
`tsubasa.embedded_subs()` -- the subtitle tracks INSIDE a video. RUNBOOK 3f.

⭐ THE CLAIM UNDER TEST

hato skips a fetch when a video already carries a Japanese text track. So the
three answers this function gives must never be confused with each other:

  * *these are the tracks*          -- ok, and the list is right
  * *there are none*                -- ok, and the list is EMPTY
  * *nobody could tell*             -- not ok, and there is NO list to misread

and a bitmap track must never be reported as text, because that is the mistake
that skips a download somebody needed.

The fixtures are real Matroska bytes written by `test_container.py`'s element-
table writer, which shares no code with the reader, and read by the REAL
reader -- `LEDGER-HOT.md`: *a fake that disagrees with the real thing about a
type measures the fake.* Where ffprobe's answer is needed without ffprobe, it
is a RECORDING of the real tool's output, never a hand-written stand-in.

🚨 AN ADVERSARIAL PASS FOUND THE FIRST VERSION OF THIS FILE WANTING, and every
check below marked *(adversary)* exists because a defect survived without it:
a truncated or damaged header read as *"has none"*; track numbers written
1, 2, 3... so an index computed as `TrackNumber - 1` could not be told apart;
three bitmap names pinned out of eleven; `japanese` the only bad tag tried;
the ffmpeg rung's `forced` and `language` checked only where ffprobe existed;
and a byte ceiling a full read never reached.
"""
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import tsubasa                                             # noqa: E402
from tsubasa import container                              # noqa: E402
from tsubasa import embedded as E                          # noqa: E402
from tsubasa.container import ffmpeg as ffmod              # noqa: E402

import test_container as W                                 # noqa: E402  (the writer)

META = 0x21
EMPTY = object()      # write the element with a zero-length body

# number, type, codec, legacy Language (None = the element ABSENT), BCP-47,
# forced, default (None = ABSENT), name
VIDEO = (1, W.VIDEO, u"V_MPEG4/ISO/AVC", u"und", None, False, True, u"")
AUDIO = (2, W.AUDIO, u"A_AAC", u"jpn", None, False, True, u"")


def _entry(number, ttype, codec, lang, bcp47, forced, default, name):
    body = (W._el(W.E_TRACKNUM, W._u(number)) + W._el(W.E_TRACKTYPE, W._u(ttype))
            + W._el(W.E_CODECID, W._s(codec)))
    if lang is EMPTY:
        body += W._el(W.E_LANG, b"")
    elif lang is not None:
        body += W._el(W.E_LANG, W._s(lang))
    if bcp47:
        body += W._el(W.E_LANG_BCP47, W._s(bcp47))
    if default is EMPTY:
        body += W._el(W.E_FLAGDEFAULT, b"")
    elif default is not None:
        body += W._el(W.E_FLAGDEFAULT, W._u(1 if default else 0))
    body += W._el(W.E_FLAGFORCED, W._u(1 if forced else 0))
    if name:
        body += W._el(W.E_TRACKNAME, W._s(name))
    return W._el(W.E_TRACKENTRY, body)


def _bytes(tracks, tail=None, entries=None, seekhead=True, tracks_unknown_size=False,
           segment_unknown_size=False):
    u"""A Matroska file whose header lists `tracks`. -> bytes

    `tail` replaces the one well-formed cluster; `entries` replaces the track
    list's body with raw bytes, so damage can sit INSIDE a list whose declared
    size is still right; `tracks_unknown_size` writes the illegal unknown-size
    Tracks element a damaged muxer produces.
    """
    info = W._el(W.E_INFO, W._el(W.E_TIMESCALE, W._u(1000000)))
    body_of_tracks = entries if entries is not None else b"".join(_entry(*t) for t in tracks)
    tracks_el = (W._el_unknown(W.E_TRACKS, body_of_tracks) if tracks_unknown_size
                 else W._el(W.E_TRACKS, body_of_tracks))
    first = tracks[0][0] if tracks else 1
    cluster = (W._el(W.E_CLUSTER, W._el(W.E_CLUSTERTS, W._u(0))
                     + W._el(W.E_SIMPLEBLOCK, W._block(first, 0, b"hello")))
               if tail is None else tail)

    def head(info_pos, tracks_pos):
        if not seekhead:
            return b""
        return W._el(W.E_SEEKHEAD, b"".join(
            W._el(W.E_SEEK, W._el(W.E_SEEKID, W._eid(e))
                  + W._el(W.E_SEEKPOS, W._u(p, width=8)))
            for e, p in ((W.E_INFO, info_pos), (W.E_TRACKS, tracks_pos))))

    size = len(head(0, 0))
    body = head(size, size + len(info)) + info + tracks_el + cluster
    segment = (W._el_unknown(W.E_SEGMENT, body) if segment_unknown_size
               else W._el(W.E_SEGMENT, body))
    return _ebml() + segment


def _ebml():
    return W._el(W.E_EBML, W._el(0x4286, W._u(1)) + W._el(0x42F7, W._u(1))
                 + W._el(0x42F2, W._u(4)) + W._el(0x42F3, W._u(8))
                 + W._el(0x4282, W._s(u"matroska"))
                 + W._el(0x4287, W._u(4)) + W._el(0x4285, W._u(2)))


def _mkv(path, tracks, **kwargs):
    with open(str(path), "wb") as fh:
        fh.write(_bytes(tracks, **kwargs))
    return str(path)


#: A library-shaped file: video and audio FIRST, and track NUMBERS that are
#: not consecutive (adversary), so a subtitle's container index can coincide
#: neither with its place among subtitles nor with `TrackNumber - 1`.
SHAPES = [
    VIDEO, AUDIO,
    (7, W.SUB, u"S_TEXT/ASS", u"jpn", None, False, True, u"日本語"),
    (12, W.SUB, u"S_HDMV/PGS", u"jpn", None, False, False, u""),
    (30, W.SUB, u"S_TEXT/UTF8", u"eng", None, True, False, u"Signs & Songs"),
    (45, W.SUB, u"S_TEXT/UTF8", u"und", None, False, False, u""),
]


@pytest.fixture
def no_ffmpeg(monkeypatch):
    u"""The native reader ALONE: a native refusal must surface as `ok=False`,
    not be rescued by whichever ffprobe this machine happens to have."""
    monkeypatch.delenv("TSUBASA_NO_NATIVE_DEMUX", raising=False)
    monkeypatch.setattr(ffmod, "find", lambda tool="ffprobe", cache_dir=None: None)


def _by_index(subs):
    return dict((t.index, t) for t in subs.tracks)


# ===========================================================================
# the three answers
# ===========================================================================

def test_every_subtitle_track_is_reported_with_its_CONTAINER_index_and_fields(tmp_path):
    subs = tsubasa.embedded_subs(_mkv(tmp_path / "v.mkv", SHAPES))
    assert subs.ok and subs.reason == u"", subs
    got = _by_index(subs)
    # ⚠ 2, 3, 4, 5 -- NOT 0, 1, 2, 3 (place among subtitles) and NOT
    # 6, 11, 29, 44 (TrackNumber - 1).
    assert sorted(got) == [2, 3, 4, 5], sorted(got)

    ass, pgs, signs, und = got[2], got[3], got[4], got[5]
    assert (ass.lang, ass.tag, ass.codec) == (u"ja", u"jpn", u"S_TEXT/ASS")
    assert (ass.text, ass.bitmap, ass.forced, ass.default) == (True, False, False, True)
    assert ass.name == u"日本語"

    assert (pgs.lang, pgs.text, pgs.bitmap) == (u"ja", False, True), pgs

    assert (signs.lang, signs.forced, signs.default) == (u"en", True, False)
    assert signs.text and signs.name == u"Signs & Songs"

    assert (und.lang, und.tag) == (u"und", u"und"), und


def test_a_readable_video_with_NO_subtitle_track_is_ok_and_empty(tmp_path, no_ffmpeg):
    u"""⭐ 37.5% of a real library (`08-probes.md` §E). Not an error."""
    subs = tsubasa.embedded_subs(_mkv(tmp_path / "v.mkv", [VIDEO, AUDIO]))
    assert subs.ok, subs
    assert subs.tracks == []


def test_an_unreadable_video_is_NOT_a_video_with_no_tracks(tmp_path):
    u"""🚨 THE CONFLATION THIS PROJECT HAS SHIPPED TWICE. An empty list here
    would tell a fetcher *"no Japanese track"* about a file nobody opened."""
    empty = tmp_path / "empty.mkv"
    empty.write_bytes(b"")
    for path, said in ((empty, u"0 bytes"),
                       (tmp_path / "missing.mkv", u"no such file")):
        subs = tsubasa.embedded_subs(path)
        assert subs.ok is False, subs
        assert said in subs.reason, subs.reason
        with pytest.raises(ValueError) as raised:
            subs.tracks
        assert said in (u"%s" % raised.value), raised.value


def test_a_DAMAGED_track_list_is_unreadable_not_short(tmp_path, no_ffmpeg):
    u"""🚨 (adversary) The reader stopped quietly where the bytes stopped making
    sense and returned what it had: damage at the second entry returned ONE
    track, damage at the first returned NONE, an unknown-size list or a
    Segment of zeros returned none -- each as a READABLE file. Every one of
    these files is complete; only the track list is wrong."""
    first = _entry(*SHAPES[2])
    second = _entry(*SHAPES[3])
    third = _entry(*SHAPES[4])
    language = W._el(W.E_LANG, W._s(u"jpn"))
    torn = first.replace(language, b"\x00" * len(language), 1)
    assert torn != first
    cases = {
        u"zeros where a field should be, INSIDE an entry": _bytes(
            SHAPES, entries=torn + second + third),
        u"zeros at the 2nd entry": _bytes(SHAPES, entries=first + b"\x00" * len(second) + third),
        u"zeros at the 1st entry": _bytes(SHAPES, entries=b"\x00" * len(first) + second + third),
        u"an unknown-size list, nothing pointing at it": _bytes(
            SHAPES, seekhead=False, tracks_unknown_size=True),
    }
    cases[u"a Segment of zeros"] = _ebml() + W._el(W.E_SEGMENT, b"\x00" * 256)
    ran = 0
    for label, data in cases.items():
        path = tmp_path / ("%d.mkv" % ran)
        path.write_bytes(data)
        subs = tsubasa.embedded_subs(path)
        assert subs.ok is False, (label, subs)
        assert subs.reason, label
        with pytest.raises(ValueError):
            subs.tracks
        # ⚠ And at the READER, which `sync()` calls without this function in
        # between: with no ffmpeg to fall back to, a damaged or missing track
        # list is an unreadable file there too, never an empty one. (The round-2
        # mutation probe found the function-level guard hiding this one.)
        assert container.read(str(path), timing=False).ok is False, label
        ran += 1
    assert ran == 5


def test_a_file_CUT_OFF_or_still_downloading_is_unreadable(tmp_path, no_ffmpeg):
    u"""🚨 (adversary) Cut inside its track list, a real file read as *"no
    tracks"* or as FEWER tracks; cut after it, its header described a file that
    is not all there. Both are `ok=False` -- and the reason says which."""
    whole = _bytes(SHAPES)
    # ⚠ rindex: the SeekHead carries the Tracks ID too, and comes first.
    tracks_at = whole.rindex(W._eid(W.E_TRACKS))
    inside = tmp_path / "inside.mkv"
    inside.write_bytes(whole[:tracks_at + 40])
    after = tmp_path / "after.mkv"
    after.write_bytes(whole[:-3])
    # ⚠ A live-muxed file declares an UNKNOWN Segment size, so nothing says it
    # is short: only the track list running past the end of the file can.
    unknown = _bytes(SHAPES, segment_unknown_size=True)
    live_tracks_at = unknown.rindex(W._eid(W.E_TRACKS))
    live = tmp_path / "live.mkv"
    live.write_bytes(unknown[:live_tracks_at + 40])
    # ⚠ And cut EXACTLY between two entries, where every entry that remains is
    # whole and only the LIST is short -- the mutation probe found the mid-entry
    # cut above could not tell a list-level guard from an entry-level one.
    entries = b"".join(_entry(*t) for t in SHAPES)
    header = len(W._eid(W.E_TRACKS)) + len(W._vint(len(entries)))
    boundary = live_tracks_at + header + len(_entry(*VIDEO)) + len(_entry(*AUDIO))
    live_boundary = tmp_path / "live_boundary.mkv"
    live_boundary.write_bytes(unknown[:boundary])
    for path in (inside, after, live, live_boundary):
        subs = tsubasa.embedded_subs(path)
        assert subs.ok is False, (path.name, subs)
    assert u"incomplete" in tsubasa.embedded_subs(after).reason
    for path in (live, live_boundary):
        assert u"track list" in tsubasa.embedded_subs(path).reason, path.name


def test_the_result_refuses_to_be_read_as_a_yes_or_no(tmp_path):
    u"""⛔ `if tsubasa.embedded_subs(video):` would be true for every video
    -- an object is truthy -- and a fetcher written that way skips every fetch."""
    readable = tsubasa.embedded_subs(_mkv(tmp_path / "v.mkv", [VIDEO]))
    unreadable = tsubasa.embedded_subs(tmp_path / "missing.mkv")
    for subs in (readable, unreadable):
        with pytest.raises(TypeError) as raised:
            bool(subs)
        assert u".tracks" in (u"%s" % raised.value), raised.value


# ===========================================================================
# language
# ===========================================================================

def test_lang_asks_the_same_question_however_Japanese_is_spelled(tmp_path):
    path = _mkv(tmp_path / "v.mkv", SHAPES)
    for spelling in (u"ja", u"jpn", u"JA", u"ja-JP"):
        subs = tsubasa.embedded_subs(path, lang=spelling)
        assert subs.lang == u"ja", (spelling, subs.lang)
        assert sorted(t.index for t in subs.tracks) == [2, 3], spelling
    assert [t.index for t in tsubasa.embedded_subs(path, lang="en").tracks] == [4]
    assert [t.index for t in tsubasa.embedded_subs(path, lang="und").tracks] == [5]


def test_an_unrecognised_lang_RAISES_rather_than_matching_nothing(tmp_path):
    u"""*"No Japanese track"* is an answer a caller acts on, so a typo may not
    produce it -- including the two-letter one (adversary: `jp`).

    ⚠ `japanese` WAS IN THIS LIST AND IS NOT A TYPO. RUNBOOK 4f made the
    filename reader accept English display names, because Jellyfin and Emby
    write them -- and `api._language_asked_for`'s whole rule is *through the
    SAME reader, so `unpaired(lang=...)` and a filename can never disagree
    about what Japanese is.* ⛔ Refusing it here would break that, and would
    make this function's own error message -- *"not a language tag tsubasa
    reads from filenames"* -- a false statement about a name it now reads.

    ⭐ The check's INTENT is untouched: the two entries that remain are
    genuine typos, and they still raise.

    ⚠ AND `jp` LEFT IT ON 2026-09-23, for the same reason: the filename reader
    reads `.jp.` as Japanese now (271 of 17,790 real names are written that
    way), so an argument spelled the same must mean the same.
    """
    path = _mkv(tmp_path / "v.mkv", SHAPES)
    tried = 0
    for typo in (u"ja_JP", u"japanse", u"nihongo"):
        with pytest.raises(ValueError) as raised:
            tsubasa.embedded_subs(path, lang=typo)
        assert typo in (u"%s" % raised.value), raised.value
        tried += 1
    assert tried == 3
    as_code = tsubasa.embedded_subs(path, lang=u"ja")
    as_country = tsubasa.embedded_subs(path, lang=u"jp")
    assert [t.index for t in as_country.tracks] == [t.index for t in as_code.tracks]

    # ⭐ AND THE ENGLISH NAME IS ACCEPTED, resolving to the same code the
    # two- and three-letter forms do.
    for spelling in (u"japanese", u"Japanese", u"JAPANESE"):
        assert tsubasa.embedded_subs(path, lang=spelling).ok, spelling
    assert ([t.lang for t in tsubasa.embedded_subs(path, lang=u"Japanese").tracks]
            == [t.lang for t in tsubasa.embedded_subs(path, lang=u"ja").tracks])


def test_BCP47_wins_and_a_region_or_script_does_not_hide_the_language(tmp_path):
    u"""⚠ A container's language field IS a language tag, so the primary subtag
    decides -- unlike a filename, where `sidecar` is strict about hyphens. And
    BCP-47 wins when the legacy field is ABSENT too (adversary): that is the
    shape the `eng` default created."""
    path = _mkv(tmp_path / "v.mkv", [
        VIDEO,
        (2, W.SUB, u"S_TEXT/ASS", u"und", u"ja-JP", False, True, u""),
        (3, W.SUB, u"S_TEXT/ASS", u"und", u"ja-Latn-JP", False, True, u""),
        (4, W.SUB, u"S_TEXT/ASS", u"und", u"zh-Hant", False, True, u""),
        (5, W.SUB, u"S_TEXT/ASS", u"qaa", None, False, True, u""),
        (6, W.SUB, u"S_TEXT/ASS", None, u"ja", False, True, u""),
    ])
    got = _by_index(tsubasa.embedded_subs(path))
    assert (got[1].lang, got[1].tag) == (u"ja", u"ja-JP"), got[1]
    assert got[2].lang == u"ja", got[2].tag
    assert got[3].lang == u"zh", got[3].tag
    assert (got[4].lang, got[4].tag) == (u"und", u"qaa"), got[4]
    assert (got[5].lang, got[5].tag) == (u"ja", u"ja"), got[5]


def test_an_ABSENT_or_EMPTY_element_reads_as_Matroskas_default(tmp_path):
    u"""🚨 MEASURED AT 3f: the native reader read `""` and ffmpeg read `eng` for
    the same file. EBML gives an absent element its default AND an empty one
    (adversary): `Language` is `eng`, `FlagDefault` is 1."""
    path = _mkv(tmp_path / "v.mkv", [
        VIDEO,
        (2, W.SUB, u"S_TEXT/UTF8", None, None, False, None, u""),
        (3, W.SUB, u"S_TEXT/UTF8", EMPTY, None, False, EMPTY, u""),
    ])
    assert container.read(path, timing=False).subtitle_tracks[0].language == u"eng"
    got = _by_index(tsubasa.embedded_subs(path))
    for index in (1, 2):
        track = got[index]
        assert (track.lang, track.tag, track.default) == (u"en", u"eng", True), track


# ===========================================================================
# text or bitmap -- the expensive mistake
# ===========================================================================

#: Every name each list holds, as LITERALS (adversary: pinning three of eleven
#: let a mutant move five bitmap names into the text list unseen).
TEXT_NAMES = (u"S_TEXT/ASS", u"S_TEXT/UTF8", u"S_TEXT/SSA", u"S_TEXT/WEBVTT",
              u"S_TEXT/USF", u"S_SSA", u"S_ASS", u"S_HDMV/TEXTST",
              u"D_WEBVTT/SUBTITLES", u"D_WEBVTT/CAPTIONS", u"D_WEBVTT/DESCRIPTIONS",
              u"subrip", u"srt", u"ass", u"ssa", u"webvtt", u"mov_text", u"text",
              u"microdvd", u"mpl2", u"pjs", u"realtext", u"sami", u"stl",
              u"subviewer", u"subviewer1", u"vplayer", u"jacosub", u"ttml",
              u"eia_608", u"hdmv_text_subtitle")
BITMAP_NAMES = (u"S_HDMV/PGS", u"S_VOBSUB", u"S_VOBSUB/ZLIB", u"S_DVBSUB",
                u"S_IMAGE/BMP", u"hdmv_pgs_subtitle", u"dvd_subtitle",
                u"dvb_subtitle", u"xsub", u"pgssub", u"dvdsub", u"dvbsub")
NEITHER = (u"S_KATE", u"S_ARIBSUB", u"arib_caption", u"dvb_teletext",
           u"D_WEBVTT/METADATA", u"", None)


def test_text_and_bitmap_are_KNOWN_lists_that_never_overlap_and_the_rest_is_neither():
    counted = 0
    for codec in TEXT_NAMES:
        assert container.is_text_codec(codec), codec
        assert not container.is_bitmap_codec(codec), codec
        counted += 1
    for codec in BITMAP_NAMES:
        assert container.is_bitmap_codec(codec), codec
        assert not container.is_text_codec(codec), codec
        counted += 1
    for codec in NEITHER:
        assert not container.is_text_codec(codec), codec
        assert not container.is_bitmap_codec(codec), codec
        counted += 1
    assert counted == len(TEXT_NAMES) + len(BITMAP_NAMES) + len(NEITHER)
    assert not (container.TEXT_CODECS & container.BITMAP_CODECS)


def test_a_DVB_or_unrecognised_track_is_never_reported_as_text(tmp_path):
    u"""🚨 `pipeline.py`'s old fragment list had no DVB entry, so a DVB bitmap
    track was labelled TEXT -- here that would skip a fetch."""
    path = _mkv(tmp_path / "v.mkv", [
        VIDEO,
        (2, W.SUB, u"S_DVBSUB", u"jpn", None, False, True, u""),
        (3, W.SUB, u"S_KATE", u"jpn", None, False, True, u""),
        (4, W.SUB, u"S_VOBSUB/ZLIB", u"jpn", None, False, True, u""),
    ])
    got = _by_index(tsubasa.embedded_subs(path, lang="ja"))
    assert (got[1].text, got[1].bitmap) == (False, True), got[1]
    assert (got[2].text, got[2].bitmap) == (False, False), got[2]
    assert (got[3].text, got[3].bitmap) == (False, True), got[3]


# ===========================================================================
# the ffmpeg rung, without ffmpeg -- a RECORDING of the real tool
# ===========================================================================

#: ffprobe 5.0.1 (gyan.dev essentials build), `-show_format -show_streams`, on
#: the file `RECORDED_TRACKS` below writes -- recorded by
#: `_work/probe_3f_4_record_ffprobe.py`, values verbatim, trimmed to the fields
#: `container/ffmpeg.py` reads. ⚠ Note what the TOOL did: the absent Language
#: came back `eng`, the explicit `und` came back with NO tag, and the metadata
#: track came back as a SUBTITLE stream flagged `metadata`.
RECORDED_FFPROBE = {
    "format": {"format_name": "matroska,webm"},
    "streams": [
        {"index": 0, "codec_type": "subtitle", "codec_name": "ass", "tags": {"language": "jpn"},
         "disposition": {"default": 1, "forced": 0, "metadata": 0}},
        {"index": 1, "codec_type": "subtitle", "codec_name": "subrip", "tags": {"language": "eng"},
         "disposition": {"default": 0, "forced": 0, "metadata": 0}},
        {"index": 2, "codec_type": "subtitle", "codec_name": "subrip",
         "disposition": {"default": 0, "forced": 0, "metadata": 0}},
        {"index": 3, "codec_type": "subtitle", "codec_name": "hdmv_pgs_subtitle",
         "tags": {"language": "jpn"}, "disposition": {"default": 0, "forced": 0, "metadata": 0}},
        {"index": 4, "codec_type": "subtitle", "codec_name": "ass", "tags": {"language": "eng"},
         "disposition": {"default": 0, "forced": 1, "metadata": 0}},
        {"index": 5, "codec_type": "subtitle", "codec_name": "dvd_subtitle",
         "tags": {"language": "jpn"}, "disposition": {"default": 0, "forced": 0, "metadata": 0}},
        {"index": 6, "codec_type": "subtitle", "codec_name": "dvb_subtitle",
         "tags": {"language": "jpn"}, "disposition": {"default": 0, "forced": 0, "metadata": 0}},
        {"index": 7, "codec_type": "subtitle", "codec_name": "webvtt", "tags": {"language": "jpn"},
         "disposition": {"default": 0, "forced": 0, "metadata": 1}},
    ],
}

RECORDED_TRACKS = [
    (3, W.SUB, u"S_TEXT/ASS", u"jpn", None, False, True, u""),
    (8, W.SUB, u"S_TEXT/UTF8", None, None, False, False, u""),
    (9, W.SUB, u"S_TEXT/UTF8", u"und", None, False, False, u""),
    (12, W.SUB, u"S_HDMV/PGS", u"jpn", None, False, False, u""),
    (13, W.SUB, u"S_TEXT/ASS", u"eng", None, True, False, u""),
    (20, W.SUB, u"S_VOBSUB", u"jpn", None, False, False, u""),
    (21, W.SUB, u"S_DVBSUB", u"jpn", None, False, False, u""),
    (30, META, u"D_WEBVTT/METADATA", u"jpn", None, False, False, u""),
]

EXPECTED = [  # (index, lang, text, bitmap, forced, default)
    (0, u"ja", True, False, False, True),
    (1, u"en", True, False, False, False),
    (2, u"und", True, False, False, False),
    (3, u"ja", False, True, False, False),
    (4, u"en", True, False, True, False),
    (5, u"ja", False, True, False, False),
    (6, u"ja", False, True, False, False),
]


@pytest.fixture
def recorded_ffprobe(monkeypatch):
    u"""The ffmpeg rung, answering with the recording instead of a process."""
    monkeypatch.setenv("TSUBASA_NO_NATIVE_DEMUX", "1")
    monkeypatch.setattr(ffmod, "find", lambda tool="ffprobe", cache_dir=None: u"ffprobe")
    monkeypatch.setattr(ffmod, "_run",
                        lambda argv, timeout: (json.dumps(RECORDED_FFPROBE), u""))


def _answer(subs):
    return [(t.index, t.lang, t.text, t.bitmap, t.forced, t.default) for t in subs.tracks]


def test_the_ffmpeg_rung_maps_forced_default_language_and_kind_like_the_tool_says(
        tmp_path, recorded_ffprobe):
    u"""(adversary) `forced` dropped and `eng` invented on this rung SURVIVED
    every check on a machine without ffprobe -- and MP4 always comes this way,
    so a forced Japanese track read as unforced makes hato skip."""
    subs = tsubasa.embedded_subs(_mkv(tmp_path / "v.mkv", RECORDED_TRACKS))
    assert subs.ok, subs.reason
    assert _answer(subs) == EXPECTED, _answer(subs)


def test_the_native_reader_agrees_with_the_RECORDED_tool_on_the_same_file(tmp_path, no_ffmpeg):
    u"""⭐ Reader parity on every machine, not only one with ffprobe."""
    subs = tsubasa.embedded_subs(_mkv(tmp_path / "v.mkv", RECORDED_TRACKS))
    assert subs.ok, subs.reason
    assert _answer(subs) == EXPECTED, _answer(subs)


#: ffprobe 4.4.2 (Ubuntu 22.04's `ffmpeg` package) on the same file, recorded
#: on the server 2026-10-04 with `ffprobe -v error -print_format json
#: -show_format -show_streams` and trimmed to the fields `container/ffmpeg.py`
#: reads. 🚨 Its disposition has NO `metadata` key at all: 4.x prints twelve
#: dispositions and `metadata` is not among them, so its JSON cannot tell the
#: METADATA track from a subtitle -- and read as absent = 0, track 30 became a
#: Japanese TEXT track, the mistake that skips a download somebody needed.
RECORDED_FFPROBE_4 = {
    "format": {"format_name": "matroska,webm"},
    "streams": [dict(s, disposition={"default": s["disposition"]["default"],
                                     "forced": s["disposition"]["forced"]})
                for s in RECORDED_FFPROBE["streams"]],
}

#: The same tool's stream listing for the same file -- `ffprobe -hide_banner
#: -v info`, stderr, verbatim but for the path. It DOES print the flag.
RECORDED_DUMP_4 = u"""\
[matroska,webm @ 0x557a622f0980] Could not find codec parameters for stream 3 (Subtitle: hdmv_pgs_subtitle (pgssub)): unspecified size
Consider increasing the value for the 'analyzeduration' (0) and 'probesize' (5000000) options
Input #0, matroska,webm, from 'v.mkv':
  Duration: N/A, start: 0.000000, bitrate: N/A
  Stream #0:0(jpn): Subtitle: ass (default)
  Stream #0:1(eng): Subtitle: subrip
  Stream #0:2: Subtitle: subrip
  Stream #0:3(jpn): Subtitle: hdmv_pgs_subtitle
  Stream #0:4(eng): Subtitle: ass (forced)
  Stream #0:5(jpn): Subtitle: dvd_subtitle
  Stream #0:6(jpn): Subtitle: dvb_subtitle
  Stream #0:7(jpn): Subtitle: webvtt (metadata)"""


#: ffprobe 4.4.2 on a file holding only `VIDEO` and an `A_MPEG/L3` audio
#: track, recorded the same way -- JSON trimmed, listing verbatim but for the
#: path. Its listing has no `Subtitle:` line to read.
RECORDED_FFPROBE_4_NO_SUBS = {
    "format": {"format_name": "matroska,webm"},
    "streams": [
        {"index": 0, "codec_type": "video", "codec_name": "h264",
         "disposition": {"default": 1, "forced": 0}},
        {"index": 1, "codec_type": "audio", "codec_name": "mp3", "tags": {"language": "jpn"},
         "disposition": {"default": 1, "forced": 0}},
    ],
}
RECORDED_DUMP_4_NO_SUBS = u"""\
[matroska,webm @ 0x55835d5ca980] Could not find codec parameters for stream 0 (Video: h264, none): unspecified size
Consider increasing the value for the 'analyzeduration' (0) and 'probesize' (5000000) options
[matroska,webm @ 0x55835d5ca980] Could not find codec parameters for stream 1 (Audio: mp3 (mp3float), 0 channels, fltp): unspecified frame size
Consider increasing the value for the 'analyzeduration' (0) and 'probesize' (5000000) options
Input #0, matroska,webm, from 'v.mkv':
  Duration: N/A, bitrate: N/A
  Stream #0:0: Video: h264, none, 1k tbr, 1k tbn, 2k tbc (default)
    Side data:
      stereo3d: 2D
  Stream #0:1(jpn): Audio: mp3, 0 channels, fltp (default)"""


def _ffprobe_4(monkeypatch, dump=RECORDED_DUMP_4, probe=RECORDED_FFPROBE_4):
    u"""The ffmpeg rung answering as ffprobe 4.4.2 did: the JSON to a
    `-show_streams` call, the stream listing (on stderr, exit 0) to a bare
    one. `dump=None` is a listing call that fails. -> the argv of every call"""
    calls = []

    def run(argv, timeout):
        calls.append(list(argv))
        if u"-show_streams" in argv:
            return json.dumps(probe), u""
        if dump is None:
            return None, u"ffprobe exited 1: v.mkv: Invalid data found when processing input"
        return u"", dump

    monkeypatch.setenv("TSUBASA_NO_NATIVE_DEMUX", "1")
    monkeypatch.setattr(ffmod, "find", lambda tool="ffprobe", cache_dir=None: u"ffprobe")
    monkeypatch.setattr(ffmod, "_run", run)
    return calls


def test_an_ffprobe_too_old_to_print_the_metadata_flag_still_never_calls_it_text(
        tmp_path, monkeypatch):
    u"""🚨 Found on the first Linux run (2026-10-04): the live parity check
    below went red against Ubuntu's ffprobe 4.4.2, which reported the WebVTT
    METADATA track as a seventh Japanese text track. The recording holds the
    fix on every machine, whatever ffprobe it has."""
    _ffprobe_4(monkeypatch)
    subs = tsubasa.embedded_subs(_mkv(tmp_path / "v.mkv", RECORDED_TRACKS))
    assert subs.ok, subs.reason
    assert _answer(subs) == EXPECTED, _answer(subs)


def test_on_an_old_ffprobe_a_WebVTT_SUBTITLE_track_is_still_text(tmp_path, monkeypatch):
    u"""The other half: the listing decides, not the codec. A WebVTT track the
    listing does NOT flag stays a text subtitle -- dropping every WebVTT track
    on an old ffprobe would hide a real one. (The recording with its one flag
    removed: constructed, not recorded.)"""
    _ffprobe_4(monkeypatch, dump=RECORDED_DUMP_4.replace(u"webvtt (metadata)", u"webvtt"))
    subs = tsubasa.embedded_subs(_mkv(tmp_path / "v.mkv", RECORDED_TRACKS))
    assert subs.ok, subs.reason
    assert _answer(subs) == EXPECTED + [(7, u"ja", True, False, False, False)], _answer(subs)


@pytest.mark.parametrize("dump", [None, u"Input #0, matroska,webm, from 'v.mkv':"],
                         ids=["listing-fails", "listing-names-no-streams"])
def test_on_an_old_ffprobe_a_listing_that_cannot_say_is_nobody_could_tell(
        tmp_path, monkeypatch, dump):
    u"""⛔ When neither the JSON nor the listing says whether a track is
    METADATA, the answer is *nobody could tell* -- never a guess, in either
    direction, that hato would act on."""
    _ffprobe_4(monkeypatch, dump=dump)
    subs = tsubasa.embedded_subs(_mkv(tmp_path / "v.mkv", RECORDED_TRACKS))
    assert subs.ok is False, subs
    assert u"metadata" in subs.reason, subs.reason


def test_on_an_old_ffprobe_a_file_with_no_subtitle_track_has_none_and_is_asked_ONCE(
        tmp_path, monkeypatch):
    u"""(mutant) Only a SUBTITLE stream's silence is a question: asked of the
    video and audio too, every file an old ffprobe reads would wait on a
    listing that has no `Subtitle:` line to answer it -- and be refused."""
    calls = _ffprobe_4(monkeypatch, dump=RECORDED_DUMP_4_NO_SUBS,
                       probe=RECORDED_FFPROBE_4_NO_SUBS)
    subs = tsubasa.embedded_subs(_mkv(tmp_path / "v.mkv", [VIDEO, AUDIO]))
    assert subs.ok, subs.reason
    assert subs.tracks == [], subs.tracks
    assert len(calls) == 1, calls


def _recorded_4(**streams):
    u"""`RECORDED_FFPROBE_4` with some streams' tags replaced: {index: tags}."""
    probe = json.loads(json.dumps(RECORDED_FFPROBE_4))
    for s in probe["streams"]:
        if "s%d" % s["index"] in streams:
            s["tags"] = streams["s%d" % s["index"]]
    return probe


def test_on_an_old_ffprobe_a_language_with_a_SPACE_still_reads(tmp_path, monkeypatch):
    u"""(adversary) `Stream #0:0(ja n): Subtitle: ass` -- ffprobe 4.4.2's real
    listing of a Language element `ja n`. The first pattern stopped at the
    space, the stream went unnamed, and a file that read before the fix was
    refused."""
    dump = RECORDED_DUMP_4.replace(u"Stream #0:0(jpn)", u"Stream #0:0(ja n)")
    _ffprobe_4(monkeypatch, dump=dump, probe=_recorded_4(s0={"language": "ja n"}))
    subs = tsubasa.embedded_subs(_mkv(tmp_path / "v.mkv", RECORDED_TRACKS))
    assert subs.ok, subs.reason
    assert [t.index for t in subs.tracks] == [0, 1, 2, 3, 4, 5, 6], _answer(subs)


#: ffprobe 4.4.2's real listing for `RECORDED_TRACKS` with two TITLES carrying
#: U+2028 and a forged stream line. ffmpeg escapes `\n` in a title and not
#: U+2028, which `str.splitlines()` breaks on -- so a title could write lines.
RECORDED_DUMP_4_FORGED = RECORDED_DUMP_4.replace(
    u"  Stream #0:0(jpn): Subtitle: ass (default)",
    u"  Stream #0:0(jpn): Subtitle: ass (default)\n    Metadata:\n      title           : "
    u"Signs   Stream #0:0(jpn): Subtitle: webvtt (metadata)") + (
    u"\n    Metadata:\n      title           : x   Stream #0:7(jpn): Subtitle: webvtt")


def test_on_an_old_ffprobe_a_TITLE_cannot_write_a_line_of_the_listing(tmp_path, monkeypatch):
    u"""(adversary) Read through `splitlines()`, these titles hid the real
    Japanese ASS track and turned the METADATA track into text."""
    _ffprobe_4(monkeypatch, dump=RECORDED_DUMP_4_FORGED, probe=_recorded_4(
        s0={"language": "jpn", "title": u"Signs   Stream #0:0(jpn): Subtitle: webvtt (metadata)"},
        s7={"language": "jpn", "title": u"x   Stream #0:7(jpn): Subtitle: webvtt"}))
    subs = tsubasa.embedded_subs(_mkv(tmp_path / "v.mkv", RECORDED_TRACKS))
    assert subs.ok, subs.reason
    assert _answer(subs) == EXPECTED, _answer(subs)


def test_on_an_old_ffprobe_a_listing_that_skips_ONE_stream_is_nobody_could_tell(
        tmp_path, monkeypatch):
    u"""(adversary) *Unnamed = not metadata* survived every check while the
    only incomplete listing named no stream at all. Here it names seven of
    eight, and the missing one is the METADATA track."""
    dump = RECORDED_DUMP_4.replace(u"\n  Stream #0:7(jpn): Subtitle: webvtt (metadata)", u"")
    _ffprobe_4(monkeypatch, dump=dump)
    subs = tsubasa.embedded_subs(_mkv(tmp_path / "v.mkv", RECORDED_TRACKS))
    assert subs.ok is False, subs
    assert u"stream 7" in subs.reason, subs.reason


def test_on_an_old_ffprobe_a_container_that_is_NOT_Matroska_is_asked_ONCE(
        tmp_path, monkeypatch):
    u"""Only the Matroska demuxer flags a track `metadata` (`D_WEBVTT/METADATA`);
    MP4 and MPEG-TS always come through ffprobe, so a second probe for them is
    a cost -- and a new way to refuse a file that read before -- for a
    question nothing else can raise. (The 4.4.2 shape, with the container
    swapped: constructed.)"""
    probe = _recorded_4()
    probe["format"]["format_name"] = "mpegts"
    calls = _ffprobe_4(monkeypatch, dump=u"", probe=probe)
    subs = tsubasa.embedded_subs(_mkv(tmp_path / "v.mkv", RECORDED_TRACKS))
    assert subs.ok, subs.reason
    assert len(calls) == 1, calls


def test_a_current_ffprobe_is_asked_ONCE(tmp_path, monkeypatch, recorded_ffprobe):
    u"""⭐ The Windows path, unchanged: ffprobe 5.0 and later print `metadata`
    in the JSON, so the stream listing is never asked for."""
    calls = []
    monkeypatch.setattr(ffmod, "_run", lambda argv, timeout: (
        calls.append(list(argv)) or (json.dumps(RECORDED_FFPROBE), u"")))
    subs = tsubasa.embedded_subs(_mkv(tmp_path / "v.mkv", RECORDED_TRACKS))
    assert _answer(subs) == EXPECTED, _answer(subs)
    assert len(calls) == 1 and u"-show_streams" in calls[0], calls


#: What ffprobe 5.0.1 printed for a Matroska file with 4 zero bytes where its
#: first TrackEntry should start -- exit 0, NO streams -- recorded by the
#: adversarial pass (`adv3f/probes/p04_b_layouts.py`), verbatim.
RECORDED_DAMAGED = ({"format": {"format_name": "matroska,webm"}, "streams": []},
                    u"[matroska,webm @ 000001bd9a89f9c0] 0x00 at pos 110 (0x6e) "
                    u"invalid as first byte of an EBML number")


def test_a_damaged_file_ffmpeg_reads_as_EMPTY_is_still_unreadable(tmp_path, monkeypatch):
    u"""🚨 Round 2 of the same defect, found re-running the adversary's own
    reproductions against the fix: the native reader now refuses a damaged
    track list, the ladder falls back to ffmpeg, and ffprobe answers exit 0
    with no streams at all -- *"has no subtitle tracks"* all over again. A file
    with no readable track of ANY kind is not a video with no subtitles."""
    monkeypatch.delenv("TSUBASA_NO_NATIVE_DEMUX", raising=False)
    monkeypatch.setattr(ffmod, "find", lambda tool="ffprobe", cache_dir=None: u"ffprobe")
    monkeypatch.setattr(ffmod, "_run", lambda argv, timeout: (
        json.dumps(RECORDED_DAMAGED[0]), RECORDED_DAMAGED[1]))
    first, second = _entry(*SHAPES[2]), _entry(*SHAPES[3])
    path = tmp_path / "rot.mkv"
    path.write_bytes(_bytes(SHAPES, entries=b"\x00" * 4 + first[4:] + second))
    info = container.read(str(path), timing=False)
    assert info.ok and info.reader == "ffmpeg" and info.tracks == [], info
    subs = tsubasa.embedded_subs(path)
    assert subs.ok is False, subs
    assert u"no track of any kind" in subs.reason and u"0x00 at pos" in subs.reason, subs.reason


def test_an_incomplete_file_is_unreadable_on_the_ffmpeg_rung_too(tmp_path, recorded_ffprobe):
    u"""⚠ ffprobe reads a cut-off Matroska file with exit 0 (measured by the
    adversary: *"File ended prematurely"*), so completeness is asked of the
    header, whichever rung answered."""
    path = tmp_path / "cut.mkv"
    path.write_bytes(_bytes(RECORDED_TRACKS)[:-3])
    subs = tsubasa.embedded_subs(path)
    assert subs.ok is False and u"incomplete" in subs.reason, subs


# ===========================================================================
# cost, and the promise
# ===========================================================================

def test_it_reads_the_HEADER_and_never_a_cluster(tmp_path, monkeypatch):
    u"""⭐ A header-only read, COUNTED through a wrapper round the REAL reader.

    🚨 Twice wrong before this: garbage after the track list survived a mutant
    asking for a FULL read, and then a fixed 64 KB ceiling did too, because a
    full read of this very file costs ~7 KB -- block headers, not payloads
    (adversary). So the ceiling is measured on the same file: a header read
    must cost a small fraction of a full one."""
    blocks = b"".join(W._el(W.E_SIMPLEBLOCK, W._block(7, i * 10, b"x" * 1000))
                      for i in range(1000))
    cluster = W._el(W.E_CLUSTER, W._el(W.E_CLUSTERTS, W._u(0)) + blocks)
    path = _mkv(tmp_path / "v.mkv", SHAPES, tail=cluster)
    real, seen = container.read, []

    def counted(p, *args, **kwargs):
        info = real(p, *args, **kwargs)
        seen.append((kwargs.get("timing", args[0] if args else True), info.bytes_read))
        return info

    monkeypatch.setattr(container, "read", counted)
    subs = tsubasa.embedded_subs(path)
    assert subs.ok, subs.reason
    assert sorted(t.index for t in subs.tracks) == [2, 3, 4, 5]
    assert len(seen) == 1, seen
    timing, header_bytes = seen[0]
    assert timing is False, seen
    full_bytes = real(path, timing=True).bytes_read
    assert header_bytes is not None and header_bytes * 4 < full_bytes, (header_bytes, full_bytes)


def test_garbage_after_the_track_list_does_not_stop_it(tmp_path):
    garbage = b"\x1f\x43\xb6\x75" + b"\x01\xff\xff\xff\xff\xff\xff\xff" + b"\x00" * 64
    subs = tsubasa.embedded_subs(_mkv(tmp_path / "v.mkv", SHAPES, tail=garbage))
    assert subs.ok, subs.reason
    assert sorted(t.index for t in subs.tracks) == [2, 3, 4, 5]


def test_a_bytes_path_names_the_same_file(tmp_path):
    u"""(adversary) It came back `no such file: b'C:\\\\...'`."""
    path = _mkv(tmp_path / "v.mkv", SHAPES)
    as_bytes = tsubasa.embedded_subs(os.fsencode(path))
    assert as_bytes.ok, as_bytes.reason
    assert _answer(as_bytes) == _answer(tsubasa.embedded_subs(Path(path)))


def test_it_is_exported_as_a_compatibility_promise():
    for name in (u"embedded_subs", u"EmbeddedSubtitles", u"EmbeddedSubtitle"):
        assert name in tsubasa.__all__, name
        assert getattr(tsubasa, name) is getattr(E, name), name


# ===========================================================================
# both readers, one answer -- LIVE, where ffprobe exists
# ===========================================================================

@pytest.fixture
def ffprobe():
    found = ffmod.find("ffprobe")
    if not found:
        pytest.skip("SKIPPED, NOT PASSED: ffprobe not found on PATH, in "
                    "TSUBASA_FFMPEG or the cache dir. Set TSUBASA_FFMPEG to a "
                    "folder containing ffmpeg and ffprobe to run this check")
    return found


def test_both_readers_give_the_same_answer_for_the_same_file(tmp_path, ffprobe, monkeypatch):
    u"""⭐ `container.read` is ONE accessor over a ladder of readers, so the
    answer may not depend on the rung. The recorded check above holds this on
    every machine; this one re-measures it against whatever ffprobe is here.
    ⚠ No BCP-47 in the file: ffmpeg ignores `LanguageBCP47` (measured), which
    is the native reader being right, not a disagreement to paper over."""
    path = _mkv(tmp_path / "v.mkv", RECORDED_TRACKS)
    monkeypatch.delenv("TSUBASA_NO_NATIVE_DEMUX", raising=False)
    native = _answer(tsubasa.embedded_subs(path))
    monkeypatch.setenv("TSUBASA_NO_NATIVE_DEMUX", "1")
    through_ffmpeg = _answer(tsubasa.embedded_subs(path))
    assert native == through_ffmpeg == EXPECTED, (native, through_ffmpeg)
