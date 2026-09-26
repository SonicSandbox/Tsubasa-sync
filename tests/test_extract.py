# -*- coding: utf-8 -*-
"""
Step 3h -- `tsubasa.extract_subtitle()`: take an embedded TEXT track OUT of an MKV, in its
own format, for hato's LAYER 14 (ruled by Sonic 2026-09-25): a video that already carries
a Japanese track can have it saved beside it, as a file.

🚨 NEVER CONVERTED. Every check that says so compares BYTES, and every fixture's text is
Japanese built from LITERALS -- an ASCII fixture cannot test an encoding rule
(`LEDGER-HOT.md`, bitten twice).

⛔ Refused, with a reason, never guessed: a container that is not Matroska, a WebVTT or
image or video track, an encrypted or bzlib/lzo track, a laced block, an ASS track with
no header, an empty track, a file cut off or with an empty stretch. *"Unreadable"* and
*"empty"* are never a file. ⚠ A block with no duration is NOT refused (the 3h pass):
it takes the track's DefaultDuration, else it is a zero-length event, as ffmpeg writes it.

🚨 The 3h ADVERSARIAL PASS's checks close the file: every finding, and the thirteen
defects that all thirty checks and twenty-one mutants had missed.

⭐ And against REAL media: two real tracks whose ffmpeg-extracted files already sit in the
corpus, compared event by event (SKIPPED, NOT PASSED, where the corpus is absent).
"""
import io
import os
import re
import sys
import zlib

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import tsubasa                                             # noqa: E402
from tsubasa import embedded_subs, extract_subtitle        # noqa: E402
from tsubasa.paths import corpus_root, load_config         # noqa: E402

from test_container import _el, _u, _write_mkv            # noqa: E402

#: ⚠ FROM LITERALS. `%d`, `%s` and `str()` emit ASCII, and an ASCII fixture passes against
#: a writer that would have converted every byte (`LEDGER-HOT.md`).
JA = (u"葬送のフリーレン", u"「ありがとう、ヒンメル」", u"魔法は想いを形にする…",
      u"ＯＰ：晴る", u"また会おう。")
CUES = [(1.0 + 3 * i, 2.5) for i in range(len(JA))]

ASS_HEADER = (u"[Script Info]\r\n"
              u"; 翼 test header\r\n"
              u"ScriptType: v4.00+\r\n"
              u"PlayResX: 1920\r\n"
              u"PlayResY: 1080\r\n"
              u"\r\n"
              u"[V4+ Styles]\r\n"
              u"Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
              u"OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, "
              u"ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
              u"MarginR, MarginV, Encoding\r\n"
              u"Style: 本文,Noto Sans JP,48,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,"
              u"0,0,100,100,0,0,1,2,0,2,10,10,10,1\r\n"
              u"\r\n"
              u"[Events]\r\n"
              u"Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, "
              u"Text\r\n").encode("utf-8")


def _ass_payload(order, text, layer=0, style=u"本文"):
    return (u"%d,%d,%s,,0,0,0,,%s" % (order, layer, style, text)).encode("utf-8")


def _srt_payloads():
    return [t.encode("utf-8") for t in JA]


def _zlib_encodings(scope=1):
    comp = _el(0x5034, _el(0x4254, _u(0)))
    return _el(0x6240, _el(0x5031, _u(0)) + _el(0x5032, _u(scope))
               + _el(0x5033, _u(0)) + comp)


def _stripping_encodings(stripped):
    comp = _el(0x5034, _el(0x4254, _u(3)) + _el(0x4255, stripped))
    return _el(0x6240, _el(0x5031, _u(0)) + _el(0x5032, _u(1)) + _el(0x5033, _u(0)) + comp)


def _text_track(video):
    subs = embedded_subs(video)
    assert subs.ok, subs.reason
    return [t for t in subs.tracks if t.codec.startswith(u"S_TEXT")][0]


def _srt_events(data):
    text = data.decode("utf-8")
    out = []
    for block in re.split(r"\r?\n\r?\n", text.strip()):
        lines = block.splitlines()
        start, end = [s.strip() for s in lines[1].split(u"-->")]
        out.append((start, end, u"\n".join(lines[2:])))
    return out


def _ass_dialogues(data):
    return [line for line in data.decode("utf-8").splitlines() if line.startswith(u"Dialogue:")]


# ---------------------------------------------------------------------------
# SRT
# ---------------------------------------------------------------------------

def test_an_srt_track_comes_out_as_srt_with_its_bytes_untouched(tmp_path):
    u"""S_TEXT/UTF8 -> `.srt`: numbered cues in time order, each cue's bytes exactly as the
    track stores them (Japanese, from literals), the times to the millisecond."""
    video = _write_mkv(tmp_path / u"ep.mkv", CUES, codec=u"S_TEXT/UTF8",
                       payloads=_srt_payloads())
    got = extract_subtitle(video, _text_track(video))
    assert got.ok, got.reason
    assert (got.ext, got.codec, got.cues) == (u"srt", u"S_TEXT/UTF8", len(JA))
    for payload in _srt_payloads():
        assert payload in got.data, u"a cue's bytes did not come out as stored"
    events = _srt_events(got.data)
    assert [e[2] for e in events] == list(JA)
    assert events[0][:2] == (u"00:00:01,000", u"00:00:03,500"), events[0]
    assert events[-1][:2] == (u"00:00:13,000", u"00:00:15,500"), events[-1]
    assert got.data.startswith(b"1\n00:00:01,000 --> 00:00:03,500\n"), got.data[:60]


def test_an_srt_cue_keeps_its_own_line_breaks(tmp_path):
    u"""Sonic, 2026-09-25: the lines are the TRACK's own. A two-line cue stored with CRLF
    keeps CRLF inside it, and the framing around it follows the track, not a preference."""
    payloads = [u"一行目\r\n二行目".encode("utf-8")] + _srt_payloads()[1:]
    video = _write_mkv(tmp_path / u"ep.mkv", CUES, codec=u"S_TEXT/UTF8", payloads=payloads)
    got = extract_subtitle(video, _text_track(video))
    assert got.ok, got.reason
    assert u"一行目\r\n二行目".encode("utf-8") in got.data
    assert b"1\r\n00:00:01,000 --> 00:00:03,500\r\n" in got.data, got.data[:60]


# ---------------------------------------------------------------------------
# ASS
# ---------------------------------------------------------------------------

def test_an_ass_track_comes_out_with_its_header_and_events_in_read_order(tmp_path):
    u"""S_TEXT/ASS -> `.ass`: the track's header byte for byte (styles and all), then each
    event as a `Dialogue:` line -- back in its ReadOrder, which is the file's own order and
    not the time order (two events at one moment, stored second-first)."""
    cues = [(1.0, 2.0), (1.0, 2.0), (5.0, 1.5)]
    payloads = [_ass_payload(1, u"上の行", layer=1), _ass_payload(0, u"下の行"),
                _ass_payload(2, u"{\\i1}斜体{\\i0}、まだ")]
    video = _write_mkv(tmp_path / u"ep.mkv", cues, codec=u"S_TEXT/ASS",
                       codec_private=ASS_HEADER, payloads=payloads)
    got = extract_subtitle(video, _text_track(video))
    assert got.ok, got.reason
    assert (got.ext, got.cues) == (u"ass", 3)
    assert got.data.startswith(ASS_HEADER.rstrip(b"\r\n")), u"the header was not kept"
    assert _ass_dialogues(got.data) == [
        u"Dialogue: 0,0:00:01.00,0:00:03.00,本文,,0,0,0,,下の行",
        u"Dialogue: 1,0:00:01.00,0:00:03.00,本文,,0,0,0,,上の行",
        u"Dialogue: 0,0:00:05.00,0:00:06.50,本文,,0,0,0,,{\\i1}斜体{\\i0}、まだ"]


def test_a_header_with_no_events_section_is_given_one(tmp_path):
    u"""A CodecPrivate that stops before `[Events]` is still a header; the file written
    from it has the section, or no player reads its Dialogue lines."""
    header = ASS_HEADER.split(b"[Events]")[0]
    video = _write_mkv(tmp_path / u"ep.mkv", CUES[:1], codec=u"S_TEXT/ASS",
                       codec_private=header, payloads=[_ass_payload(0, JA[0])])
    got = extract_subtitle(video, _text_track(video))
    assert got.ok, got.reason
    assert b"[Events]\r\nFormat: Layer, Start, End, Style" in got.data, got.data[-200:]


def test_an_ssa_track_comes_out_as_ssa(tmp_path):
    video = _write_mkv(tmp_path / u"ep.mkv", CUES[:1], codec=u"S_TEXT/SSA",
                       codec_private=b"[Script Info]\nScriptType: v4.00\n",
                       payloads=[_ass_payload(0, JA[0])])
    got = extract_subtitle(video, _text_track(video))
    assert got.ok and got.ext == u"ssa", got.reason
    assert b"Format: Marked, Start, End" in got.data


# ---------------------------------------------------------------------------
# compression
# ---------------------------------------------------------------------------

def test_zlib_compressed_events_come_out_decompressed(tmp_path):
    video = _write_mkv(tmp_path / u"ep.mkv", CUES, codec=u"S_TEXT/UTF8",
                       payloads=[zlib.compress(p) for p in _srt_payloads()],
                       encodings=_zlib_encodings())
    got = extract_subtitle(video, _text_track(video))
    assert got.ok, got.reason
    assert [e[2] for e in _srt_events(got.data)] == list(JA)


def test_header_stripped_events_get_their_bytes_back(tmp_path):
    u"""mkvmerge's header stripping keeps the bytes every frame begins with ONCE, in the
    track entry; each frame must get them back, in front."""
    # ⚠ The stripped bytes must begin EVERY frame -- a multi-byte one here, so a frame given
    # back its first byte only would read as broken UTF-8, not as a near miss
    stripped = u"「".encode("utf-8")
    whole = [(u"「" + t).encode("utf-8") for t in JA]
    assert all(w.startswith(stripped) for w in whole), u"fixture: a frame lacks the prefix"
    video = _write_mkv(tmp_path / u"ep.mkv", CUES, codec=u"S_TEXT/UTF8",
                       payloads=[w[len(stripped):] for w in whole],
                       encodings=_stripping_encodings(stripped))
    got = extract_subtitle(video, _text_track(video))
    assert got.ok, got.reason
    assert [e[2] for e in _srt_events(got.data)] == [u"「" + t for t in JA]


def test_two_encodings_are_undone_last_applied_first(tmp_path):
    u"""A muxer applies ContentEncodings in ascending order -- here the prefix stripped
    (order 0), THEN zlib (order 1) -- so they are undone from the highest order down:
    decompress, then give the prefix back. The other way round decompresses garbage."""
    stripped = u"「".encode("utf-8")
    whole = [(u"「" + t).encode("utf-8") for t in JA]
    strip = _el(0x6240, _el(0x5031, _u(0)) + _el(0x5032, _u(1)) + _el(0x5033, _u(0))
                + _el(0x5034, _el(0x4254, _u(3)) + _el(0x4255, stripped)))
    deflate = _el(0x6240, _el(0x5031, _u(1)) + _el(0x5032, _u(1)) + _el(0x5033, _u(0))
                  + _el(0x5034, _el(0x4254, _u(0))))
    video = _write_mkv(tmp_path / u"ep.mkv", CUES, codec=u"S_TEXT/UTF8",
                       payloads=[zlib.compress(w[len(stripped):]) for w in whole],
                       encodings=strip + deflate)
    got = extract_subtitle(video, _text_track(video))
    assert got.ok, got.reason
    assert [e[2] for e in _srt_events(got.data)] == [u"「" + t for t in JA]


def test_a_compressed_header_is_decompressed_too(tmp_path):
    u"""Scope bit 2: the CodecPrivate is compressed as well as the frames."""
    video = _write_mkv(tmp_path / u"ep.mkv", CUES[:1], codec=u"S_TEXT/ASS",
                       codec_private=zlib.compress(ASS_HEADER),
                       payloads=[zlib.compress(_ass_payload(0, JA[0]))],
                       encodings=_zlib_encodings(scope=3))
    got = extract_subtitle(video, _text_track(video))
    assert got.ok, got.reason
    assert got.data.startswith(ASS_HEADER.rstrip(b"\r\n"))


# ---------------------------------------------------------------------------
# refusals -- a reason, never a guessed file
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("encodings,said", [
    (_el(0x6240, _el(0x5033, _u(1)) + _el(0x5035, b"")), u"encrypted"),
    (_el(0x6240, _el(0x5034, _el(0x4254, _u(1)))), u"bzlib"),
    (_el(0x6240, _el(0x5034, _el(0x4254, _u(2)))), u"lzo"),
])
def test_a_track_it_cannot_undo_is_refused(tmp_path, encodings, said):
    video = _write_mkv(tmp_path / u"ep.mkv", CUES, codec=u"S_TEXT/UTF8",
                       payloads=_srt_payloads(), encodings=encodings)
    got = extract_subtitle(video, _text_track(video))
    assert not got.ok and said in got.reason and got.data == b"", got


def test_a_corrupt_zlib_event_is_refused_not_raised(tmp_path):
    video = _write_mkv(tmp_path / u"ep.mkv", CUES, codec=u"S_TEXT/UTF8",
                       payloads=[b"not zlib at all"] * len(JA), encodings=_zlib_encodings())
    got = extract_subtitle(video, _text_track(video))
    assert not got.ok and u"decompressed" in got.reason, got


@pytest.mark.parametrize("codec,said", [
    (u"S_TEXT/WEBVTT", u"WebVTT"),
    (u"S_HDMV/PGS", u"image subtitle"),
    (u"S_TEXT/USF", u"does not take"),
])
def test_a_track_of_another_codec_is_refused_by_name(tmp_path, codec, said):
    video = _write_mkv(tmp_path / u"ep.mkv", CUES, codec=codec)
    got = extract_subtitle(video, 2)                    # video, audio, then the subtitle
    assert not got.ok and said in got.reason, got


def test_a_video_track_is_not_a_subtitle(tmp_path):
    video = _write_mkv(tmp_path / u"ep.mkv", CUES, codec=u"S_TEXT/UTF8",
                       payloads=_srt_payloads())
    got = extract_subtitle(video, 0)
    assert not got.ok and u"not a subtitle track" in got.reason, got


def test_a_file_that_is_not_matroska_is_refused_never_converted(tmp_path):
    u"""MP4's mov_text has no file of its own: taking it out would mean CONVERTING it."""
    mp4 = tmp_path / u"ep.mp4"
    mp4.write_bytes(b"\x00\x00\x00\x20ftypisom" + b"\x00" * 64)
    got = extract_subtitle(str(mp4), 0)
    assert not got.ok and u"MKV only" in got.reason and u"CONVERTING" in got.reason, got


def test_a_laced_block_is_refused(tmp_path):
    video = _write_mkv(tmp_path / u"ep.mkv", CUES, codec=u"S_TEXT/UTF8",
                       payloads=_srt_payloads(), laced=True)
    got = extract_subtitle(video, _text_track(video))
    assert not got.ok and u"laced" in got.reason, got


def test_an_empty_track_is_not_an_empty_file(tmp_path):
    video = _write_mkv(tmp_path / u"ep.mkv", [], codec=u"S_TEXT/UTF8")
    got = extract_subtitle(video, 2)
    assert not got.ok and u"nothing to take out" in got.reason and got.data == b"", got


def test_a_file_cut_off_is_refused(tmp_path):
    video = _write_mkv(tmp_path / u"ep.mkv", CUES, codec=u"S_TEXT/UTF8",
                       payloads=_srt_payloads())
    whole = open(video, "rb").read()
    open(video, "wb").write(whole[:len(whole) - 40])
    got = extract_subtitle(video, 2)
    assert not got.ok, got
    # ⚠ AND CUT EXACTLY WHERE A CLUSTER BEGINS (the 3h pass's gate: the cut above lands in
    # the trailing index, which the walk sees too). Every block that is left is whole --
    # only the Segment's own size says clusters are missing.
    video = _write_mkv(tmp_path / u"b.mkv", CUES, codec=u"S_TEXT/UTF8",
                       payloads=_srt_payloads(), per_cluster=2, cue_style="none")
    whole = open(video, "rb").read()
    last = whole.rfind(b"\x1f\x43\xb6\x75")
    open(video, "wb").write(whole[:last])
    got = extract_subtitle(video, 2)
    assert not got.ok and u"cut off" in got.reason, (u"at a cluster's start", got)


def test_a_missing_file_and_a_bad_track_argument(tmp_path):
    got = extract_subtitle(str(tmp_path / u"nothing.mkv"), 0)
    assert not got.ok and u"no file" in got.reason
    with pytest.raises(TypeError):
        extract_subtitle(str(tmp_path / u"nothing.mkv"), object())


def test_asking_its_truth_raises():
    u"""`if not got:` would read *"could not take it out"* and *"took out nothing"* alike."""
    with pytest.raises(TypeError):
        bool(tsubasa.ExtractedSubtitle(u"x", True))


# ---------------------------------------------------------------------------
# the index and the walk
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("cue_style", ["none", "thinned", "skip_clusters", "head", "hostile"])
def test_an_absent_or_partial_index_is_walked_and_loses_nothing(tmp_path, cue_style):
    u"""⛔ A file is WRITTEN from this: an index that lists only some blocks must never
    hand back a subtitle missing lines. Every shape gives the whole track."""
    many = [(1.0 + 2 * i, 1.5) for i in range(18)]
    payloads = [(u"%s・%s" % (JA[i % len(JA)], u"〇一二三四五六七八九"[i % 10])).encode("utf-8")
                for i in range(18)]
    whole = _write_mkv(tmp_path / u"whole.mkv", many, codec=u"S_TEXT/UTF8",
                       payloads=payloads)
    other = _write_mkv(tmp_path / (u"%s.mkv" % cue_style), many, codec=u"S_TEXT/UTF8",
                       payloads=payloads, cue_style=cue_style)
    a = extract_subtitle(whole, 2)
    b = extract_subtitle(other, 2)
    assert a.ok and b.ok, (a.reason, b.reason)
    assert a.cues == b.cues == 18 and a.data == b.data


# ---------------------------------------------------------------------------
# the public name
# ---------------------------------------------------------------------------

def test_the_names_are_exported():
    assert {u"extract_subtitle", u"ExtractedSubtitle"} <= set(tsubasa.__all__)
    assert tsubasa.extract_subtitle is extract_subtitle


# ---------------------------------------------------------------------------
# REAL media -- ffmpeg's own extraction of the same tracks, already in the corpus
# ---------------------------------------------------------------------------

def _corpus():
    root = corpus_root(load_config(ROOT), ROOT)
    if not root or not os.path.isdir(root):
        pytest.skip("SKIPPED, NOT PASSED: corpus absent on this machine")
    return root


def _ffmpeg_ass_events(text):
    out = []
    for line in text.splitlines():
        if line.startswith(u"Dialogue:"):
            out.append(line)
    return out


def test_a_real_japanese_ass_track_matches_ffmpegs_own_extraction():
    u"""`video-derived/yomi18`: a real SubsPlease episode's track and ffmpeg's `.ass` of
    it. Every event identical -- start, end, style, text -- and the header identical but
    for its line breaks, which the TRACK stores as CRLF and ffmpeg rewrites."""
    folder = os.path.join(_corpus(), u"video-derived", u"yomi18")
    video = os.path.join(folder, u"track_2.mkv")
    got = extract_subtitle(video, _text_track(video))
    assert got.ok, got.reason
    theirs = io.open(os.path.join(folder, u"track_2.ass"), encoding="utf-8-sig").read()
    mine = got.data.decode("utf-8")
    assert _ffmpeg_ass_events(mine) == _ffmpeg_ass_events(theirs)
    assert len(_ffmpeg_ass_events(mine)) == got.cues == 323
    assert (mine.split(u"[Events]")[0].replace(u"\r\n", u"\n").strip()
            == theirs.split(u"[Events]")[0].replace(u"\r\n", u"\n").strip())


def test_a_real_srt_track_matches_ffmpegs_own_extraction():
    folder = os.path.join(_corpus(), u"video")
    video = os.path.join(folder, u"Sintel-60s.mkv")
    got = extract_subtitle(video, _text_track(video))
    assert got.ok, got.reason
    theirs = io.open(os.path.join(folder, u"Sintel-60s.srt"), encoding="utf-8-sig").read()
    assert _srt_events(got.data) == _srt_events(theirs.encode("utf-8"))
    assert got.cues == 24


# ===========================================================================
# ⭐ RUNBOOK 3h's ADVERSARIAL PASS -- every finding, a check that fails without its fix
# ===========================================================================

ASS_TAIL = (b"\r\n[Aegisub Project Garbage]\r\nScroll Position: 3\r\n\r\n"
            b"[Fonts]\r\nfontname: a.ttf\r\nM4XKA\r\n")

SSA_HEADER = (u"[Script Info]\r\n"
              u"ScriptType: v4.00\r\n"
              u"\r\n"
              u"[V4 Styles]\r\n"
              u"Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
              u"TertiaryColour, BackColour, Bold, Italic, BorderStyle, Outline, Shadow, "
              u"Alignment, MarginL, MarginR, MarginV, AlphaLevel, Encoding\r\n"
              u"Style: 本文,MS Gothic,24,16777215,65535,65535,-2147483640,-1,0,1,2,2,2,"
              u"10,10,10,0,128\r\n"
              u"\r\n"
              u"[Events]\r\n"
              u"Format: Marked, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, "
              u"Text\r\n").encode("utf-8")


def _ass_video(tmp_path, header, codec=u"S_TEXT/ASS", name=u"ep.mkv", **kw):
    payloads = [_ass_payload(i, t) for i, t in enumerate(JA)]
    return _write_mkv(tmp_path / name, CUES, codec=codec, payloads=payloads,
                      codec_private=header, **kw)


def test_an_ass_headers_sections_after_the_events_stay_after_the_events(tmp_path):
    u"""🚨 The 3h pass, #1 -- REAL on 179 of 250 real ASS files with a trailing section
    (1.17% of the corpus): the header was written whole, the events after it, so every
    Dialogue sat under `[Aegisub Project Garbage]` or `[Fonts]` -- pysubs2 read 0 events and
    libass drew nothing. ⭐ ffmpeg's rule, which reproduces the source line for line: the
    head runs to the end of the Format line after `[Events]`, the rest follows the events."""
    video = _ass_video(tmp_path, ASS_HEADER + ASS_TAIL)
    got = extract_subtitle(video, _text_track(video))
    assert got.ok, got.reason
    lines = got.data.split(b"\r\n")
    events_at = lines.index(b"[Events]")
    garbage_at = lines.index(b"[Aegisub Project Garbage]")
    dialogues = [n for n, l in enumerate(lines) if l.startswith(b"Dialogue:")]
    assert dialogues and events_at < min(dialogues) and max(dialogues) < garbage_at, (
        u"a Dialogue sits outside [Events]: events at %d, the next section at %d, the "
        u"dialogues at %s" % (events_at, garbage_at, dialogues))
    assert got.data.startswith(ASS_HEADER) and got.data.endswith(ASS_TAIL), (
        u"the header's sections did not go back where the file had them")
    assert len(dialogues) == len(JA)


def test_a_header_ending_in_a_blank_line_keeps_it_after_the_events(tmp_path):
    u"""The same rule for the commonest tail of all -- one blank line after the Format line
    (yomi18's): it follows the events, as ffmpeg writes it, rather than being dropped."""
    video = _ass_video(tmp_path, ASS_HEADER + b"\r\n")
    got = extract_subtitle(video, _text_track(video))
    assert got.ok, got.reason
    assert got.data.endswith(b"\r\n\r\n") and not got.data.endswith(b"\r\n\r\n\r\n"), (
        repr(got.data[-40:]))


def test_an_ssa_track_whose_format_opens_with_marked_says_marked(tmp_path):
    u"""The 3h pass, #8: every real SSA source whose Format line opens with `Marked` writes
    `Dialogue: Marked=0,...` -- the muxer stores `0`. ⭐ Read from the Format line, never
    from ScriptType's spelling (ffmpeg keys on `ScriptType: v4.00` and wrote `0` for three
    real sources); an ASS header's `Layer` stays a bare number."""
    ssa = _ass_video(tmp_path, SSA_HEADER, codec=u"S_TEXT/SSA", name=u"a.mkv")
    got = extract_subtitle(ssa, _text_track(ssa))
    assert got.ok and got.ext == u"ssa", got
    lines = _ass_dialogues(got.data)
    assert lines and all(l.startswith(u"Dialogue: Marked=0,") for l in lines), lines[:2]
    ass = _ass_video(tmp_path, ASS_HEADER, name=u"b.mkv")
    lines = _ass_dialogues(extract_subtitle(ass, _text_track(ass)).data)
    assert lines and all(l.startswith(u"Dialogue: 0,") for l in lines), lines[:2]


def test_a_line_with_no_duration_is_a_zero_length_event_not_a_refused_track(tmp_path):
    u"""🚨 The 3h pass, #2 -- REAL: for a line whose start equals its end, ffmpeg writes a
    BlockGroup with NO BlockDuration, and one such line (1 in 288, Gingitsune 04) got the
    whole track refused -- 5.1% of the corpus's real ASS files. ⭐ It is a zero-length
    event, start = end, as the file has it."""
    cues = [(1.0, 2.5), (4.0, None), (7.0, 2.5)]
    video = _write_mkv(tmp_path / u"ep.mkv", cues, codec=u"S_TEXT/UTF8",
                       payloads=[t.encode("utf-8") for t in JA[:3]])
    got = extract_subtitle(video, _text_track(video))
    assert got.ok, got.reason
    events = _srt_events(got.data)
    assert events[1][:2] == (u"00:00:04,000", u"00:00:04,000"), events[1]
    assert events[0][:2] == (u"00:00:01,000", u"00:00:03,500"), u"the control: a timed line"


def test_a_track_whose_blocks_carry_no_duration_takes_its_default_duration(tmp_path):
    u"""The 3h pass, #2's variant: SimpleBlocks carry no duration at all, and the track's
    DefaultDuration says how long each is (ffmpeg extracts 1.5 s cues). Without one, every
    event is zero-length -- never a refusal."""
    video = _write_mkv(tmp_path / u"ep.mkv", CUES, codec=u"S_TEXT/UTF8",
                       payloads=_srt_payloads(), block_style="simple",
                       default_duration=1500000000)
    got = extract_subtitle(video, _text_track(video))
    assert got.ok, got.reason
    assert _srt_events(got.data)[0][:2] == (u"00:00:01,000", u"00:00:02,500")
    bare = _write_mkv(tmp_path / u"bare.mkv", CUES, codec=u"S_TEXT/UTF8",
                      payloads=_srt_payloads(), block_style="simple")
    got = extract_subtitle(bare, _text_track(bare))
    assert got.ok and _srt_events(got.data)[0][:2] == (u"00:00:01,000", u"00:00:01,000"), got


def _cluster_starts(data):
    at, out = 0, []
    while True:
        at = data.find(b"\x1f\x43\xb6\x75", at)
        if at < 0:
            return out
        out.append(at)
        at += 4


def test_a_zero_filled_stretch_is_refused_never_a_shorter_subtitle(tmp_path):
    u"""🚨 The 3h pass, #4 -- REAL: a torrent still downloading into a sparse file reads as
    the right size with holes in it, and the walk stopped at the first hole -- 3, 12 or 20
    of 24 events, `ok=True`; a hole in the first cluster said *"holds no subtitle events"*,
    which was false. ⭐ Unreadable before the end is refused. Three holes: at a cluster
    boundary, inside a cluster, and inside one event's own bytes (the structure intact:
    NUL bytes, which text never holds)."""
    video = _write_mkv(tmp_path / u"ep.mkv", CUES * 4, codec=u"S_TEXT/UTF8",
                       payloads=_srt_payloads() * 4, per_cluster=2)
    whole = open(video, "rb").read()
    second = _cluster_starts(whole)[1]
    for what, start, span in ((u"a cluster boundary", second, 24),
                              (u"inside a cluster", second + 12, 10)):
        holed = bytearray(whole)
        holed[start:start + span] = b"\x00" * span
        open(video, "wb").write(bytes(holed))
        got = extract_subtitle(video, 2)
        assert not got.ok and u"not all there" in got.reason, (what, got)
    target = JA[2].encode("utf-8")
    at = whole.find(target)
    holed = whole[:at] + b"\x00" * len(target) + whole[at + len(target):]
    open(video, "wb").write(holed)
    got = extract_subtitle(video, 2)
    assert not got.ok and u"empty bytes" in got.reason, got


def test_a_live_recording_cut_off_is_refused(tmp_path):
    u"""🚨 The 3h pass, #5 -- REAL: a Segment of UNKNOWN size (anything written to a pipe or
    recorded live) cut off returned 8, 13 or 18 of 24 events, `ok=True`. ⭐ A block that
    runs past the end of the file is a file not all there."""
    from test_container import E_BLOCK, E_BLOCKDURATION, E_BLOCKGROUP, _block
    # ⚠ TWO ARMS, each the only guard for its shape: an UNKNOWN-size cluster cut inside a
    # block (the block runs past the file), and a KNOWN-size cluster cut exactly between
    # blocks (every block whole -- only the cluster's own size says lines are missing)
    video = _write_mkv(tmp_path / u"u.mkv", CUES, codec=u"S_TEXT/UTF8",
                       payloads=_srt_payloads(), unknown_segment=True, unknown_cluster=True,
                       cue_style="none")
    assert extract_subtitle(video, 2).ok, u"the control: the whole file is taken"
    whole = open(video, "rb").read()
    open(video, "wb").write(whole[:-3])
    got = extract_subtitle(video, 2)
    assert not got.ok and u"cut off" in got.reason, (u"inside a block", got)
    video = _write_mkv(tmp_path / u"k.mkv", CUES, codec=u"S_TEXT/UTF8",
                       payloads=_srt_payloads(), unknown_segment=True, cue_style="none")
    assert extract_subtitle(video, 2).ok, u"the control: the whole file is taken"
    whole = open(video, "rb").read()
    last = _el(E_BLOCKGROUP, _el(E_BLOCK, _block(3, 12000, JA[4].encode("utf-8")))
               + _el(E_BLOCKDURATION, _u(2500)))
    assert whole.endswith(last), u"fixture: the file ends with its last cue's block group"
    open(video, "wb").write(whole[:-len(last)])
    got = extract_subtitle(video, 2)
    assert not got.ok and u"cut off" in got.reason, (u"between blocks", got)


@pytest.mark.skipif(not sys.platform.startswith("win"), reason="a share-deny open is Windows'")
def test_a_file_another_program_holds_is_ok_false_never_a_raise(tmp_path):
    u"""🚨 The 3h pass, #6: *"never raises for a video it cannot take out"* -- and a file
    another program held without read sharing raised PermissionError out of it."""
    import ctypes
    from ctypes import wintypes
    video = _write_mkv(tmp_path / u"ep.mkv", CUES, codec=u"S_TEXT/UTF8",
                       payloads=_srt_payloads())
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateFileW.restype = wintypes.HANDLE
    handle = kernel32.CreateFileW(str(video), 0x80000000, 0, None, 3, 0x80, None)
    assert handle not in (None, wintypes.HANDLE(-1).value), u"the control: the file is held"
    try:
        got = extract_subtitle(video, 2)
    finally:
        kernel32.CloseHandle(handle)
    assert not got.ok and u"could not be read" in got.reason, got


def test_a_hostile_index_offset_raises_nothing_anywhere(tmp_path):
    u"""The 3h pass, #6: a CueRelativePosition of 2**63 raised OverflowError out of the
    reader. ⭐ The shared reader now takes a position past the end as the end -- for the
    timing read too, which still uses the index -- and extraction never reads the index."""
    from tsubasa.container import mkv
    video = _write_mkv(tmp_path / u"ep.mkv", CUES, codec=u"S_TEXT/UTF8",
                       payloads=_srt_payloads(), cue_style="hostile")
    got = extract_subtitle(video, 2)
    assert got.ok and got.cues == len(JA), got
    try:
        mkv.read(str(video), timing=True)
    except mkv.ContainerError:
        pass                                    # refused is fine; raising anything else is not


def test_a_track_from_another_video_or_reader_is_refused(tmp_path):
    u"""The 3h pass, #7: a track was trusted by its POSITION alone -- with ffmpeg's reader
    numbering a file otherwise, the English track came out as the Japanese one, `ok=True`.
    ⭐ A track object is checked against the video's own track: codec, language, title."""
    from tsubasa.embedded import EmbeddedSubtitle
    ja = _write_mkv(tmp_path / u"ja.mkv", CUES, codec=u"S_TEXT/UTF8",
                    payloads=_srt_payloads())
    en = _write_mkv(tmp_path / u"en.mkv", CUES, codec=u"S_TEXT/UTF8", language=u"eng",
                    payloads=_srt_payloads())
    got = extract_subtitle(en, _text_track(ja))
    assert not got.ok and u"not the track given" in got.reason, got
    by_ffmpeg = EmbeddedSubtitle(2, u"ja", u"jpn", u"subrip", True, False, False, True, u"")
    got = extract_subtitle(ja, by_ffmpeg)
    assert not got.ok and u"not the track given" in got.reason, got
    assert extract_subtitle(ja, _text_track(ja)).ok, u"the control: its own track"


def test_a_time_before_zero_is_written_as_zero(tmp_path):
    u"""The 3h pass, #8: `-1:59:59,500`, `ok=True`. ⭐ An SRT time cannot be negative."""
    video = _write_mkv(tmp_path / u"ep.mkv", [(0.1, 1.0), (-0.4, 1.0)],
                       codec=u"S_TEXT/UTF8", payloads=[JA[0].encode("utf-8"),
                                                       JA[1].encode("utf-8")],
                       cue_style="none")
    got = extract_subtitle(video, 2)
    assert got.ok, got.reason
    first = _srt_events(got.data)[0]
    assert first[:2] == (u"00:00:00,000", u"00:00:00,600"), first


def test_an_event_that_inflates_past_its_bound_is_refused(tmp_path):
    u"""The 3h pass, #8: the 1 MB bound was read on the STORED size -- a 40 KB event came
    out 41.9 MB, a 167 MB file, `ok=True`. ⭐ Bounded after inflating too."""
    big = (u"あ" * 400000).encode("utf-8")
    payloads = [zlib.compress(p) for p in _srt_payloads()]
    payloads[1] = zlib.compress(big)
    video = _write_mkv(tmp_path / u"ep.mkv", CUES, codec=u"S_TEXT/UTF8",
                       payloads=payloads, encodings=_zlib_encodings())
    got = extract_subtitle(video, 2)
    assert not got.ok and u"decompresses to more than" in got.reason, got


def test_a_stored_event_past_its_bound_is_refused(tmp_path):
    u"""The 3h pass, #9: removing the stored-size bound left every check green. ⚠ It is
    refused BEFORE it is read -- a hostile block of gigabytes never reaches memory -- so the
    check asks for the bound's own words, not the size check after inflating."""
    payloads = _srt_payloads()
    payloads[1] = (u"あ" * 360000).encode("utf-8")
    video = _write_mkv(tmp_path / u"ep.mkv", CUES, codec=u"S_TEXT/UTF8", payloads=payloads)
    got = extract_subtitle(video, 2)
    assert not got.ok and u"declares a" in got.reason, got


@pytest.mark.parametrize("codec, ext", [(u"S_TEXT/ASCII", u"srt"), (u"S_ASS", u"ass"),
                                        (u"S_SSA", u"ssa")])
def test_the_legacy_codec_ids_are_taken(tmp_path, codec, ext):
    u"""The 3h pass, #8: `embedded_subs` calls them text and ffmpeg copies them out."""
    if ext == u"srt":
        video = _write_mkv(tmp_path / u"ep.mkv", CUES, codec=codec, payloads=_srt_payloads())
    else:
        video = _ass_video(tmp_path, ASS_HEADER if ext == u"ass" else SSA_HEADER, codec=codec)
    got = extract_subtitle(video, 2)
    assert got.ok and got.ext == ext, got


def test_an_ass_track_with_no_header_is_refused_never_given_one(tmp_path):
    u"""The 3h pass, #8: written with no [Script Info] and no styles. ⛔ Not invented."""
    for header in (None, b""):
        video = _ass_video(tmp_path, header, name=u"h%s.mkv" % (header is None))
        got = extract_subtitle(video, 2)
        assert not got.ok and u"no header" in got.reason, (header, got)


def test_a_track_argument_is_an_int_or_a_track_nothing_else(tmp_path):
    u"""The 3h pass, #8: `track=True` meant track 1 and `track=2.9` track 2. And a negative
    index is no track -- it never wraps to the last one."""
    video = _write_mkv(tmp_path / u"ep.mkv", CUES, codec=u"S_TEXT/UTF8",
                       payloads=_srt_payloads())
    for wrong in (True, 2.9, u"2"):
        with pytest.raises(TypeError):
            extract_subtitle(video, wrong)
    got = extract_subtitle(video, -1)
    assert not got.ok and u"no track -1" in got.reason, got


@pytest.mark.parametrize("timescale, start, srt, ass", [
    (100000, 1.0005, u"00:00:01,001", u"0:00:01.00"),
    (100000, 1.005, u"00:00:01,005", u"0:00:01.01"),
    (1000000, 1.0, u"00:00:01,000", u"0:00:01.00")])
def test_times_honour_the_timescale_and_round(tmp_path, timescale, start, srt, ass):
    u"""The 3h pass, #9: TimestampScale ignored, and times truncated instead of rounded,
    left every check green -- every fixture used 1 ms ticks."""
    cues = [(start + 3 * i, 2.5) for i in range(len(JA))]
    video = _write_mkv(tmp_path / u"a.mkv", cues, codec=u"S_TEXT/UTF8",
                       payloads=_srt_payloads(), timescale=timescale, per_cluster=1)
    got = extract_subtitle(video, 2)
    assert got.ok and _srt_events(got.data)[0][0] == srt, (got, srt)
    payloads = [_ass_payload(i, t) for i, t in enumerate(JA)]
    video = _write_mkv(tmp_path / u"b.mkv", cues, codec=u"S_TEXT/ASS", payloads=payloads,
                       codec_private=ASS_HEADER, timescale=timescale, per_cluster=1)
    line = _ass_dialogues(extract_subtitle(video, 2).data)[0]
    assert line.split(u",")[1] == ass, (line, ass)


def test_a_tracks_own_number_is_read_not_its_position(tmp_path):
    u"""The 3h pass, #9: every fixture's track numbers were position + 1, so reading the
    position as the TrackNumber was invisible."""
    video = _write_mkv(tmp_path / u"ep.mkv", CUES, codec=u"S_TEXT/UTF8",
                       payloads=_srt_payloads(), sub_track=7)
    got = extract_subtitle(video, 2)
    assert got.ok and got.cues == len(JA), got


@pytest.mark.parametrize("bits", [0x02, 0x04, 0x06])
def test_every_kind_of_lacing_is_refused(tmp_path, bits):
    u"""The 3h pass, #9: only Xiph lacing was checked; fixed-size slipped through."""
    video = _write_mkv(tmp_path / u"ep.mkv", CUES, codec=u"S_TEXT/UTF8",
                       payloads=_srt_payloads(), laced=bits)
    got = extract_subtitle(video, 2)
    assert not got.ok and u"laced" in got.reason, got


def test_an_encoding_that_states_only_what_it_must_is_read_by_its_defaults(tmp_path):
    u"""The 3h pass, #8 and #9: EBML defaults -- no scope is the frames, no type is
    compression, and no algorithm (even no ContentCompression at all) is zlib. It read
    *"compressed with algorithm None"*."""
    payloads = [zlib.compress(p) for p in _srt_payloads()]
    for encodings in (_el(0x6240, _el(0x5034, b"")),                  # compression, empty
                      _el(0x6240, _el(0x5031, _u(0)))):               # no compression at all
        video = _write_mkv(tmp_path / u"ep.mkv", CUES, codec=u"S_TEXT/UTF8",
                           payloads=payloads, encodings=encodings)
        got = extract_subtitle(video, 2)
        assert got.ok and [e[2] for e in _srt_events(got.data)] == list(JA), got


def test_several_unknown_size_clusters_are_all_walked(tmp_path):
    u"""The 3h pass, #9: the walk stopping after the first unknown-size cluster left every
    check green."""
    video = _write_mkv(tmp_path / u"ep.mkv", CUES * 3, codec=u"S_TEXT/UTF8",
                       payloads=_srt_payloads() * 3, per_cluster=2, unknown_cluster=True,
                       cue_style="none")
    got = extract_subtitle(video, 2)
    assert got.ok and got.cues == 3 * len(JA), got


def test_the_reasons_say_what_is_true(tmp_path):
    u"""The 3h pass, #10: an empty file and a file of zeros were both told they would have
    to be CONVERTED; an unknown encoding was "encrypted"; a header that would not inflate
    was an "event"; a ReadOrder error showed escaped bytes."""
    empty = tmp_path / u"empty.mkv"
    empty.write_bytes(b"")
    got = extract_subtitle(str(empty), 0)
    assert not got.ok and u"is empty" in got.reason, got
    zeros = tmp_path / u"zeros.mkv"
    zeros.write_bytes(b"\x00" * 64)
    got = extract_subtitle(str(zeros), 0)
    assert u"not a Matroska" in got.reason and u"CONVERT" not in got.reason, got
    odd = _write_mkv(tmp_path / u"odd.mkv", CUES, codec=u"S_TEXT/UTF8",
                     payloads=_srt_payloads(), encodings=_el(0x6240, _el(0x5033, _u(2))))
    got = extract_subtitle(odd, 2)
    assert u"does not define" in got.reason and u"encrypted" not in got.reason, got
    hdr = _ass_video(tmp_path, b"not zlib at all", name=u"hdr.mkv",
                     encodings=_zlib_encodings(scope=2))
    got = extract_subtitle(hdr, 2)
    assert u"header could not be decompressed" in got.reason, got
    payloads = [_ass_payload(i, t) for i, t in enumerate(JA)]
    payloads[0] = u"一,0,本文,,0,0,0,,x".encode("utf-8")
    bad = _write_mkv(tmp_path / u"bad.mkv", CUES, codec=u"S_TEXT/ASS", payloads=payloads,
                     codec_private=ASS_HEADER)
    got = extract_subtitle(bad, 2)
    assert u"ReadOrder" in got.reason and u"一" in got.reason, got


# ===========================================================================
# ⭐ WRITTEN BY TSUBASA, WHEN ASKED -- hato's rule: the only write in a media folder is
# tsubasa's (its Whitelist 1, ruled by Sonic 2026-09-17). Found building hato's 14c.
# ===========================================================================

def _listing(folder):
    return sorted(p.name for p in folder.iterdir())


def test_asked_to_it_writes_the_file_beside_the_video_under_tsubasas_name(tmp_path):
    u"""`<video basename>.<lang>.<ext>`, the name every player loads and tsubasa's own
    reader reads back as the language -- atomically: nothing else is left in the folder."""
    video = _write_mkv(tmp_path / u"frieren S2 - 01.mkv", CUES, codec=u"S_TEXT/UTF8",
                       payloads=_srt_payloads())
    got = extract_subtitle(video, _text_track(video), write=True)
    assert got.ok and not got.write_failed, got
    assert got.output_path == str(tmp_path / u"frieren S2 - 01.ja.srt"), got.output_path
    assert open(got.output_path, "rb").read() == got.data
    assert _listing(tmp_path) == [u"frieren S2 - 01.ja.srt", u"frieren S2 - 01.mkv"]
    assert tsubasa.parse_subtitle_name(os.path.basename(got.output_path)).lang == u"ja"


def test_it_writes_into_out_dir_when_given(tmp_path):
    video = _write_mkv(tmp_path / u"ep.mkv", CUES, codec=u"S_TEXT/UTF8",
                       payloads=_srt_payloads())
    out = tmp_path / u"Subs"
    got = extract_subtitle(video, 2, write=True, out_dir=str(out))
    assert got.ok and got.output_path == str(out / u"ep.ja.srt"), got
    assert _listing(tmp_path) == [u"Subs", u"ep.mkv"], u"it wrote beside the video too"


def test_it_never_writes_over_a_file_that_is_there(tmp_path):
    u"""⛔ A subtitle already beside the video is the person's -- or an earlier run's -- and
    is never replaced: `write_failed`, the reason, and the file untouched. ⭐ `ok` still
    True: the extraction worked; the destination did not."""
    video = _write_mkv(tmp_path / u"ep.mkv", CUES, codec=u"S_TEXT/UTF8",
                       payloads=_srt_payloads())
    theirs = tmp_path / u"ep.ja.srt"
    theirs.write_bytes(u"彼らのファイル".encode("utf-8"))
    got = extract_subtitle(video, 2, write=True)
    assert got.ok and got.write_failed and got.output_path is None, got
    assert u"already there" in got.reason and got.data, got
    assert theirs.read_bytes() == u"彼らのファイル".encode("utf-8"), u"it wrote over theirs"


def test_a_write_that_cannot_land_is_not_a_failed_extraction(tmp_path):
    video = _write_mkv(tmp_path / u"ep.mkv", CUES, codec=u"S_TEXT/UTF8",
                       payloads=_srt_payloads())
    blocked = tmp_path / u"not-a-folder"
    blocked.write_bytes(b"x")
    got = extract_subtitle(video, 2, write=True, out_dir=str(blocked))
    assert got.ok and got.write_failed and got.output_path is None, got
    assert u"could not be written" in got.reason and got.data, got


def test_without_write_nothing_is_written(tmp_path):
    video = _write_mkv(tmp_path / u"ep.mkv", CUES, codec=u"S_TEXT/UTF8",
                       payloads=_srt_payloads())
    got = extract_subtitle(video, 2)
    assert got.ok and got.output_path is None and not got.write_failed, got
    assert _listing(tmp_path) == [u"ep.mkv"]


def test_a_forced_track_is_written_under_a_forced_name(tmp_path):
    u"""A forced track is signs only; its name says so, as tsubasa names every file it
    writes -- so a reader never takes it for the full subtitle."""
    video = _write_mkv(tmp_path / u"ep.mkv", CUES, codec=u"S_TEXT/UTF8",
                       payloads=_srt_payloads(), forced=True)
    got = extract_subtitle(video, 2, write=True)
    assert got.ok and got.output_path == str(tmp_path / u"ep.ja.forced.srt"), got
