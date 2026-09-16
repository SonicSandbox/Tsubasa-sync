# -*- coding: utf-8 -*-
"""
Writing: the field whitelist, enforced by measurement rather than by intent.

`spec/03-permissions.md` says tsubasa MAY change cue Start/End and essentially
nothing else. The way that is guaranteed here is structural -- the writer
replaces only timestamp character spans and copies every other byte through --
so the strongest possible test is available and cheap:

    ⭐ A ZERO SHIFT MUST PRODUCE BYTE-IDENTICAL OUTPUT.

If any part of the file were being rebuilt rather than passed through, that
check fails immediately. Every format gets it.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tsubasa import formats                                  # noqa: E402
from tsubasa.cues import RewriteRefused, apply_spans, retime  # noqa: E402
from tsubasa.formats import srt                              # noqa: E402


SRT = (
    u"1\r\n"
    u"00:00:12,500 --> 00:00:15,000\r\n"
    u"第113話「うずまきナルト」\r\n"
    u"\r\n"
    u"2\r\n"
    u"00:00:16,000 --> 00:00:18,250\r\n"
    u"つまり相手の人格の否定だ。\r\n"
)

ASS_WITH_BINARY = (
    u"[Script Info]\n"
    u"Title: test\n"
    u"\n"
    u"[V4+ Styles]\n"
    u"Format: Name, Fontname, Fontsize\n"
    u"Style: Default,Arial,20\n"
    u"\n"
    u"[Fonts]\n"
    u"fontname: embedded.ttf\n"
    u"!!0(!!0(!!0(!!0(3!!0(!!0(qw3rty+/=\n"
    u"\n"
    u"[Events]\n"
    u"Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    u"Dialogue: 0,0:00:12.50,0:00:15.00,Default,,0,0,0,,{\\pos(960,1050)}第113話\n"
    u"Comment: 0,0:00:20.00,0:00:22.00,Default,,0,0,0,,a comment\n"
)

VTT = (
    u"WEBVTT\n"
    u"\n"
    u"STYLE\n"
    u"::cue { color: yellow }\n"
    u"\n"
    u"NOTE dropping this turns a valid file invalid\n"
    u"\n"
    u"1\n"
    u"00:00:12.500 --> 00:00:15.000 align:start position:10%\n"
    u"第113話「うずまきナルト」\n"
)


# --------------------------------------------------------------------------
# ⭐ the headline: a zero shift changes nothing at all
# --------------------------------------------------------------------------

@pytest.mark.parametrize("text,name,codec", [
    (SRT, "a.srt", "utf-8"),
    (SRT, "a.srt", "cp932"),
    (ASS_WITH_BINARY, "a.ass", "utf-8"),
    (VTT, "a.vtt", "utf-8"),
    (SRT, "a.srt", "utf-16-le"),
    (SRT, "a.srt", "utf-8-sig"),
])
def test_a_zero_shift_is_byte_identical(text, name, codec):
    original = text.encode(codec)
    r = formats.read_bytes(original, filename=name)
    assert r.ok and len(r) > 0, r.reason
    assert formats.rewrite_bytes(r, shift=0.0) == original


def test_shift_jis_stays_shift_jis_after_a_real_retime():
    """🚨 The encoding is on the MUST-NEVER-CHANGE list. A Shift-JIS file
    retimed by 2.5 s must come back Shift-JIS with its text intact."""
    original = SRT.encode("cp932")
    r = formats.read_bytes(original, filename="a.srt")
    out = formats.rewrite_bytes(r, shift=2.5)

    assert out != original, "the shift did not take"
    assert out.decode("cp932")                       # still valid Shift-JIS
    assert u"第113話" in out.decode("cp932")
    with pytest.raises(UnicodeDecodeError):
        out.decode("utf-8")                          # i.e. it was NOT converted

    again = formats.read_bytes(out, filename="a.srt")
    assert abs(again.cues[0].start - 15.0) < 0.001


# --------------------------------------------------------------------------
# what must not move
# --------------------------------------------------------------------------

def test_only_timestamps_differ_after_a_shift():
    """Diff the before and after line by line: every changed line must contain
    a timing arrow. Anything else changing is a whitelist violation."""
    original = ASS_WITH_BINARY
    r = formats.read_bytes(original.encode("utf-8"), filename="a.ass")
    out = formats.rewrite_bytes(r, shift=1.25).decode("utf-8")

    before, after = original.split("\n"), out.split("\n")
    assert len(before) == len(after), "the line count changed"
    changed = [(a, b) for a, b in zip(before, after) if a != b]
    assert changed, "nothing changed at all -- the shift did not apply"
    for a, b in changed:
        assert a.lower().startswith(("dialogue:", "comment:")), (
            "a non-event line changed:\n  before: %r\n  after:  %r" % (a, b))


def test_ass_embedded_binary_survives():
    r = formats.read_bytes(ASS_WITH_BINARY.encode("utf-8"), filename="a.ass")
    out = formats.rewrite_bytes(r, shift=3.0).decode("utf-8")
    assert u"[Fonts]" in out
    assert u"!!0(!!0(!!0(!!0(3!!0(!!0(qw3rty+/=" in out
    assert u"Style: Default,Arial,20" in out
    assert u"{\\pos(960,1050)}" in out, "an override tag was mangled"


def test_vtt_settings_and_blocks_survive():
    r = formats.read_bytes(VTT.encode("utf-8"), filename="a.vtt")
    out = formats.rewrite_bytes(r, shift=5.0).decode("utf-8")
    assert u"align:start position:10%" in out
    assert u"NOTE dropping this turns a valid file invalid" in out
    assert u"STYLE" in out and u"::cue { color: yellow }" in out


def test_crlf_line_endings_survive():
    """Line endings are on the never-change list. They survive because nothing
    splits and rejoins lines."""
    original = SRT.encode("utf-8")
    assert b"\r\n" in original
    r = formats.read_bytes(original, filename="a.srt")
    out = formats.rewrite_bytes(r, shift=1.0)
    assert b"\r\n" in out
    assert out.count(b"\r\n") == original.count(b"\r\n")


def test_the_decimal_separator_is_written_back_unchanged():
    """A file using dots keeps dots. Gratuitous normalisation is a change the
    whitelist does not permit."""
    dotted = SRT.replace(u",5", u".5").replace(u",0", u".0").replace(u",2", u".2")
    r = formats.read_bytes(dotted.encode("utf-8"), filename="a.srt")
    out = formats.rewrite_bytes(r, shift=1.0).decode("utf-8")
    assert u"00:00:13.500" in out, out[:200]
    assert u",", "sanity"


# --------------------------------------------------------------------------
# the shift itself
# --------------------------------------------------------------------------

def test_a_shift_moves_every_cue():
    r = formats.read_bytes(SRT.encode("utf-8"), filename="a.srt")
    out = formats.rewrite_bytes(r, shift=-2.5)
    again = formats.read_bytes(out, filename="a.srt")
    assert abs(again.cues[0].start - 10.0) < 0.001
    assert abs(again.cues[1].end - 15.75) < 0.001


def test_a_negative_result_clamps_to_zero_rather_than_wrapping():
    r = formats.read_bytes(SRT.encode("utf-8"), filename="a.srt")
    out = formats.rewrite_bytes(r, shift=-9999.0).decode("utf-8")
    assert u"-" not in out.split(u"-->")[0].split(u"\n")[-1]
    again = formats.read_bytes(out.encode("utf-8"), filename="a.srt")
    assert all(c.start >= 0 for c in again.cues)


def test_a_mapper_gives_different_segments_different_offsets():
    """A cut file has more than one offset, so a single shift cannot express
    it. This is the shape splits will need."""
    r = formats.read_bytes(SRT.encode("utf-8"), filename="a.srt")
    out = formats.rewrite_bytes(
        r, mapper=lambda t: t + (1.0 if t < 15.0 else 10.0))
    again = formats.read_bytes(out, filename="a.srt")
    assert abs(again.cues[0].start - 13.5) < 0.001
    assert abs(again.cues[1].start - 26.0) < 0.001


# --------------------------------------------------------------------------
# the rewriter refuses rather than half-doing the job
# --------------------------------------------------------------------------

def test_overlapping_spans_are_refused():
    """Two edits on one span means the parser reported a timestamp twice.
    Applying both corrupts the file into something that still LOOKS like a
    timestamp, which is the worst kind of failure."""
    with pytest.raises(RewriteRefused):
        apply_spans(u"0123456789", [((2, 6), u"XX"), ((4, 8), u"YY")])


def test_a_span_outside_the_text_is_refused():
    with pytest.raises(RewriteRefused):
        apply_spans(u"short", [((2, 99), u"X")])


def test_a_cue_with_no_span_refuses_the_whole_rewrite():
    """⚠ Skipping it would leave the file HALF-RETIMED, which is worse than
    refusing: some cues move and some do not, and nothing says so."""
    r = formats.read_bytes(SRT.encode("utf-8"), filename="a.srt")
    r.cues[1].start_span = None
    with pytest.raises(RewriteRefused):
        retime(r, shift=1.0, formatter=srt.format_timestamp)


def test_rewriting_a_file_that_did_not_read_is_refused():
    r = formats.read_bytes(b"\x00\x01\x02not a subtitle\xff")
    assert not r.ok
    with pytest.raises(ValueError):
        formats.rewrite_bytes(r, shift=1.0)


def test_apply_spans_leaves_everything_outside_the_spans_alone():
    assert apply_spans(u"abcdefghij", [((2, 4), u"XY")]) == u"abXYefghij"
    assert apply_spans(u"abcdefghij", []) == u"abcdefghij"


# --------------------------------------------------------------------------
# on disk
# --------------------------------------------------------------------------

def test_write_file_is_atomic_and_byte_exact(tmp_path):
    target = tmp_path / "out.srt"
    original = SRT.encode("cp932")
    r = formats.read_bytes(original, filename="a.srt")
    formats.write_file(target, formats.rewrite_bytes(r, shift=0.0))
    assert target.read_bytes() == original
    assert [p.name for p in tmp_path.iterdir()] == ["out.srt"], "temp litter"
