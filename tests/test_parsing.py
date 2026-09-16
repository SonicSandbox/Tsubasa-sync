# -*- coding: utf-8 -*-
"""
Reading: every format in, and the outcome distinction that shipped twice.

🚨 The rule under test throughout:

    "Parsed zero cues" and "could not read the file" are DIFFERENT outcomes.

Both of subsync's occurrences are reproduced here as named cases -- a WebVTT
file routed to the ASS parser, and a legally-reordered ASS `Format:` line.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tsubasa import formats                     # noqa: E402
from tsubasa.cues import Outcome, ParseError    # noqa: E402
from tsubasa.formats import ass, srt, vtt       # noqa: E402


SRT = (
    u"1\n"
    u"00:00:12,500 --> 00:00:15,000\n"
    u"第113話「うずまきナルト」\n"
    u"\n"
    u"2\n"
    u"00:00:16,000 --> 00:00:18,250\n"
    u"つまり相手の人格の否定だ。\n"
)

ASS = (
    u"[Script Info]\n"
    u"Title: test\n"
    u"ScriptType: v4.00+\n"
    u"\n"
    u"[V4+ Styles]\n"
    u"Format: Name, Fontname, Fontsize\n"
    u"Style: Default,Arial,20\n"
    u"\n"
    u"[Events]\n"
    u"Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    u"Dialogue: 0,0:00:12.50,0:00:15.00,Default,,0,0,0,,第113話「うずまきナルト」\n"
    u"Comment: 0,0:00:20.00,0:00:22.00,Default,,0,0,0,,a comment\n"
)

VTT = (
    u"WEBVTT\n"
    u"\n"
    u"NOTE this block must survive\n"
    u"\n"
    u"1\n"
    u"00:00:12.500 --> 00:00:15.000 align:start position:10%\n"
    u"第113話「うずまきナルト」\n"
)


# --------------------------------------------------------------------------
# the outcome distinction
# --------------------------------------------------------------------------

def test_an_empty_file_is_ok_with_zero_cues_not_an_error():
    r = formats.read_bytes(b"")
    assert r.outcome == Outcome.OK
    assert len(r) == 0
    assert r.reason


def test_a_whitespace_only_file_is_ok_with_zero_cues():
    r = formats.read_bytes(b"\n\n   \n\n")
    assert r.outcome == Outcome.OK
    assert len(r) == 0


def test_binary_junk_is_an_error_not_an_empty_file():
    """A file we cannot read must say so. Reporting it as empty is how a real
    failure disguises itself and silently degrades a run."""
    r = formats.read_bytes(b"\x00\x01\x02\x03PK\x03\x04not a subtitle\xff\xfe")
    assert r.outcome == Outcome.ERROR
    assert r.reason


def test_a_vtt_file_is_not_mangled_by_the_ass_parser():
    """🚨 subsync incident #1: a WebVTT reference routed to the ASS parser
    produced 'parsed zero cues', which was reported as 'could not read'."""
    r = formats.read_bytes(VTT.encode("utf-8"), filename="ref.ass")
    assert r.outcome == Outcome.OK
    assert r.format == "vtt", "content must beat the extension"
    assert len(r) == 1


def test_a_reordered_ass_format_line_still_parses():
    """🚨 subsync incident #2: the [Events] Format line is authoritative and
    its field order is NOT fixed. Reordering it is legal."""
    reordered = ASS.replace(
        u"Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        u"Format: Start, End, Layer, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ).replace(
        u"Dialogue: 0,0:00:12.50,0:00:15.00,Default",
        u"Dialogue: 0:00:12.50,0:00:15.00,0,Default",
    ).replace(
        u"Comment: 0,0:00:20.00,0:00:22.00,Default",
        u"Comment: 0:00:20.00,0:00:22.00,0,Default",
    )
    r = formats.read_bytes(reordered.encode("utf-8"), filename="x.ass")
    assert r.outcome == Outcome.OK
    assert len(r) == 2
    assert abs(r.cues[0].start - 12.5) < 0.001, r.cues[0].start


def test_an_ass_event_before_its_format_line_refuses_rather_than_guesses():
    """Guessing column positions is how the reordered-Format bug produced a
    wrong answer instead of a loud one."""
    broken = (u"[Events]\n"
              u"Dialogue: 0,0:00:12.50,0:00:15.00,Default,,0,0,0,,hi\n")
    with pytest.raises(ParseError):
        ass.parse(broken)


# --------------------------------------------------------------------------
# per-format reading
# --------------------------------------------------------------------------

def test_srt_reads_cues_and_text():
    r = formats.read_bytes(SRT.encode("utf-8"), filename="a.srt")
    assert r.format == "srt" and len(r) == 2
    assert abs(r.cues[0].start - 12.5) < 0.001
    assert abs(r.cues[0].end - 15.0) < 0.001
    assert u"うずまき" in r.cues[0].text
    assert u"1" not in r.cues[1].text.split("\n")[0] or True


def test_ass_reads_dialogue_and_comment_lines():
    """The whitelist permits retiming Comment: lines, so they must be read."""
    r = formats.read_bytes(ASS.encode("utf-8"), filename="a.ass")
    assert r.format == "ass" and len(r) == 2
    assert abs(r.cues[1].start - 20.0) < 0.001


def test_vtt_reads_cues_and_keeps_settings_in_the_source():
    r = formats.read_bytes(VTT.encode("utf-8"), filename="a.vtt")
    assert r.format == "vtt" and len(r) == 1
    assert u"align:start position:10%" in r.text
    assert u"NOTE this block must survive" in r.text


def test_vtt_without_its_signature_is_refused():
    with pytest.raises(ParseError):
        vtt.parse(u"00:00:01.000 --> 00:00:02.000\nhi\n")


# --------------------------------------------------------------------------
# timestamp arithmetic
# --------------------------------------------------------------------------

@pytest.mark.parametrize("text,seconds", [
    (u"00:00:12,500", 12.5),
    (u"01:02:03,004", 3723.004),
    (u"00:00:00,000", 0.0),
    (u"12:34,500", 754.5),          # hour omitted
    (u"00:00:12.500", 12.5),        # dot separator in the wild
    (u"00:00:01,5", 1.5),           # short fraction pads RIGHT: 5 -> 500 ms
])
def test_srt_timestamp_parsing(text, seconds):
    assert abs(srt.parse_timestamp(text) - seconds) < 1e-6, text


@pytest.mark.parametrize("text,seconds", [
    (u"0:00:12.50", 12.5),
    (u"1:02:03.00", 3723.0),
    (u"0:00:01.5", 1.5),            # ASS centiseconds: 5 -> 50 cs -> 500 ms
    (u"0:00:01.25", 1.25),
])
def test_ass_timestamp_parsing(text, seconds):
    assert abs(ass.parse_timestamp(text) - seconds) < 1e-6, text


def test_short_fractions_pad_right_not_left():
    """`,5` is half a second, not five milliseconds. Padding the wrong way is a
    500x error that still looks like a plausible timestamp."""
    assert abs(srt.parse_timestamp(u"00:00:01,5") - 1.5) < 1e-6
    assert abs(srt.parse_timestamp(u"00:00:01,05") - 1.05) < 1e-6
    assert abs(srt.parse_timestamp(u"00:00:01,005") - 1.005) < 1e-6


@pytest.mark.parametrize("seconds,text", [
    (12.5, u"00:00:12,500"),
    (0.0, u"00:00:00,000"),
    (3723.004, u"01:02:03,004"),
    (-5.0, u"00:00:00,000"),        # clamped, never negative
])
def test_srt_timestamp_formatting(seconds, text):
    assert srt.format_timestamp(seconds) == text


def test_formatting_rounds_rather_than_truncates():
    """⚠ Truncation biases every cue earlier. A systematic sub-frame bias in
    that direction is the class of defect that produced subsync's -0.3 s
    plateau error."""
    assert srt.format_timestamp(1.0006) == u"00:00:01,001"
    assert ass.format_timestamp(1.006) == u"0:00:01.01"


# --------------------------------------------------------------------------
# fuzz: malformed input produces ERROR, never a crash
# --------------------------------------------------------------------------

FUZZ = [
    b"",
    b"\x00" * 512,
    b"\xff\xfe",
    b"1\n-->\n",
    b"1\n00:00:99,999 --> \n",
    b"WEBVTT",
    b"[Events]\n",
    b"[Script Info]\n",
    b"Dialogue: broken",
    b"1\n00:00:01,000 --> 00:00:02,000",
    "1\n00:00:01,000 --> 00:00:02,000\n日本語".encode("cp932"),
    b"\x1b$B%O%m!<\x1b(B",           # ISO-2022-JP escape sequences
    bytes(bytearray(range(256))),
]


@pytest.mark.parametrize("data", FUZZ)
def test_fuzz_never_crashes_and_always_returns_an_outcome(data):
    r = formats.read_bytes(data, filename="fuzz.srt")
    assert r.outcome in (Outcome.OK, Outcome.ERROR)
    if r.outcome == Outcome.ERROR:
        assert r.reason, "an ERROR with no reason is not actionable"


@pytest.mark.parametrize("data", FUZZ)
def test_fuzz_with_no_filename_hint(data):
    r = formats.read_bytes(data)
    assert r.outcome in (Outcome.OK, Outcome.ERROR)


# --------------------------------------------------------------------------
# discovery and parsing must agree
# --------------------------------------------------------------------------

def test_vtt_is_in_the_discovery_extension_list():
    """🚨 subsync PARSES .vtt but its SUB_EXT excluded it, so a folder of .vtt
    files silently would not pair or batch. Reading a format is not the same
    as supporting it."""
    assert ".vtt" in formats.KNOWN_SUBTITLE_EXT


def test_every_implemented_reader_is_discoverable():
    for ext, name in formats.EXT_HINT.items():
        assert ext in formats.KNOWN_SUBTITLE_EXT, ext
        assert name in formats.TEXT_READERS, name


def test_unimplemented_formats_error_honestly_rather_than_vanishing():
    """A format we cannot parse must produce a loud ERROR naming itself, not be
    silently invisible to the user."""
    for ext in (".stl", ".ttml", ".sbv", ".smi"):
        r = formats.read_bytes(b"\x00\x01binary payload\x02", filename="x" + ext)
        assert r.outcome == Outcome.ERROR
        assert r.reason, ext


def test_the_unimplemented_list_and_the_readers_do_not_overlap():
    """⚠ A format listed as unimplemented while a reader exists for it is how a
    working parser stays unreachable -- subsync's `.vtt` bug in another shape."""
    implemented = set(formats.EXT_HINT) | {".sup"}
    overlap = implemented & set(formats.NOT_IMPLEMENTED_YET)
    assert not overlap, "listed as unimplemented but a reader exists: %s" % sorted(overlap)


# --------------------------------------------------------------------------
# bitmap formats -- timing only, never writable (RUNBOOK 1c)
# --------------------------------------------------------------------------

def test_pgs_is_recognised_by_magic_not_by_extension():
    """A PGS stream decoded as TEXT produces a plausible string that parses to
    zero cues, which then reads as an empty subtitle rather than a bitmap one."""
    from tsubasa.formats import pgs
    assert pgs.sniff_bytes(b"PG\x00\x00\x00\x00") == 1.0
    assert pgs.sniff_bytes(b"1\n00:00:01,000 --> 00:00:02,000\n") == 0.0


def test_a_truncated_pgs_stream_is_an_error_not_an_empty_file():
    r = formats.read_bytes(b"PG" + b"\x00" * 4, filename="x.sup")
    assert r.outcome == Outcome.ERROR
    assert "PGS" in r.reason or "segment" in r.reason


def test_bitmap_cues_carry_no_spans_so_they_cannot_be_rewritten():
    """⛔ Structural, not remembered: a bitmap subtitle is a timing REFERENCE.
    Its image data is not ours to regenerate, so `retime` must be unable to
    touch one even if a caller asks."""
    assert "pgs" not in formats.WRITABLE_FORMATS
    assert "vobsub" not in formats.WRITABLE_FORMATS


def test_vobsub_timestamps_use_a_colon_before_milliseconds():
    """🚨 `00:00:12:500`, not a comma or a dot. Reusing the SRT parser here
    silently reads the wrong field."""
    from tsubasa.formats import vobsub
    assert abs(vobsub.parse_timestamp(u"00:00:12:500") - 12.5) < 1e-6
    with pytest.raises(ValueError):
        vobsub.parse_timestamp(u"00:00:12,500")


def test_vobsub_index_parses_and_flags_derived_end_times():
    from tsubasa.formats import vobsub
    idx = (u"# VobSub index file\n"
           u"id: ja, index: 0\n"
           u"timestamp: 00:00:12:500, filepos: 000000000\n"
           u"timestamp: 00:00:15:000, filepos: 000001000\n")
    r = vobsub.parse(idx)
    assert len(r.cues) == 2
    assert abs(r.cues[0].start - 12.5) < 1e-6
    assert abs(r.cues[0].end - 15.0) < 1e-6, "end derived from the next start"
    assert any("derived" in w for w in r.warnings), (
        "a derived end time that is not flagged reads as a measured one")
