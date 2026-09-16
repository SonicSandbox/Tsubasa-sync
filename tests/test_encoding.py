# -*- coding: utf-8 -*-
"""
Encoding: the highest-stakes code in the project.

🚨 The bug this suite exists to prevent, quoted from LEDGER.md:

    A Shift-JIS caption decoded with errors="replace" had all 346 cues turn
    into U+FFFD. Timestamps are ASCII so they survived -- the alignment scored
    4x chance, the tool said CONFIDENT, and it wrote a file that plays with
    perfect timing and no readable text.

⚠ NEITHER new corpus can exercise this. `video-naming` is 3,026 UTF-8 files out
of 3,039; the jimaku corpus is UTF-8 throughout. So these fixtures are
GENERATED, byte by byte, here -- the alternative is that the project's worst
documented defect ships with no test at all.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tsubasa import encoding as E   # noqa: E402

# A real caption line, and one that exercises kana, kanji and punctuation.
JA = u"第113話「うずまきナルト」\nそれをしないってことは\nつまり相手の人格の否定だ。\n"
SRT_JA = (
    u"1\n"
    u"00:00:12,500 --> 00:00:15,000\n"
    u"第113話「うずまきナルト」\n"
    u"\n"
    u"2\n"
    u"00:00:16,000 --> 00:00:18,250\n"
    u"つまり相手の人格の否定だ。\n"
)


# --------------------------------------------------------------------------
# the incident, replayed
# --------------------------------------------------------------------------

def test_shift_jis_survives_a_read_write_cycle():
    """🚨 THE ONE. Read a Shift-JIS caption, write it back, get the same bytes."""
    original = SRT_JA.encode("cp932")
    d = E.sniff_and_decode(original)

    assert u"�" not in d.text, (
        "the decode was LOSSY -- this is the exact failure: timestamps are "
        "ASCII so they survive, and the tool reports CONFIDENT on a file with "
        "no readable text"
    )
    assert u"第113話" in d.text
    assert E.encode_back(d.text, d) == original, "the codec was converted"


def test_shift_jis_is_not_read_as_utf8():
    """It must not merely 'work' -- it must be RECOGNISED as Shift-JIS.

    If this returned utf-8 with replacement characters the test above would
    still pass on the byte comparison for an ASCII-only file. This is the check
    that the identification itself happened.
    """
    d = E.sniff_and_decode(SRT_JA.encode("cp932"))
    assert d.encoding in ("cp932", "shift_jis"), d.encoding


def test_a_lossy_decode_is_never_returned():
    """No path through the ladder may produce U+FFFD.

    errors='replace' is what made the original bug invisible. Any decode that
    needed it is wrong, and latin-1 (which cannot fail) is the correct floor.
    """
    for codec in ("cp932", "euc-jp", "big5", "cp1251", "iso-8859-2"):
        data = JA.encode(codec, errors="replace")
        d = E.sniff_and_decode(data)
        assert u"�" not in d.text, "%s produced a lossy decode" % codec


# --------------------------------------------------------------------------
# the ladder, rung by rung
# --------------------------------------------------------------------------

@pytest.mark.parametrize("codec,bom_expected", [
    ("utf-8", False),
    ("utf-8-sig", False),
    ("utf-16-le", True),
    ("utf-16-be", True),
    ("utf-32-le", True),
    ("utf-32-be", True),
])
def test_round_trip_is_byte_exact(codec, bom_expected):
    data = SRT_JA.encode(codec)
    assert E.round_trips(data), "%s did not round-trip" % codec
    d = E.sniff_and_decode(data)
    assert u"第113話" in d.text


def test_utf16_without_a_bom_is_found_by_null_density():
    """⚠ Without this rung a UTF-16 file decodes 'successfully' as latin-1 into
    text full of NULs, parses to zero cues, and reads as an EMPTY FILE rather
    than a misread one -- the conflation that shipped twice."""
    body = SRT_JA.encode("utf-16-le")[2:]        # strip the BOM
    d = E.sniff_and_decode(body)
    assert d.encoding == "utf-16-le", d.encoding
    assert u"第113話" in d.text
    assert E.encode_back(d.text, d) == body


def test_a_bom_wins_over_content_sniffing():
    data = SRT_JA.encode("utf-8-sig")
    d = E.sniff_and_decode(data)
    assert d.how == "byte-order mark"
    assert E.encode_back(d.text, d) == data


def test_latin1_is_the_byte_exact_floor():
    """Undecodable-as-anything-sensible bytes must still round-trip.

    Preserving the user's bytes matters more than being right about what they
    mean -- a wrong guess we can round-trip is recoverable; a lossy one is not.
    """
    data = bytes(bytearray(range(1, 256))) * 4
    d = E.sniff_and_decode(data)
    assert E.encode_back(d.text, d) == data
    assert u"�" not in d.text


def test_an_empty_file_is_readable_not_an_error():
    """🚨 'Parsed zero cues' and 'could not read the file' are DIFFERENT.

    An empty file is perfectly readable and contains nothing. Raising here
    would report ERROR for a file that is merely empty.
    """
    d = E.sniff_and_decode(b"")
    assert d.text == u""
    assert d.encoding


# --------------------------------------------------------------------------
# plausibility -- the rung that is not first-success
# --------------------------------------------------------------------------

def test_scoring_beats_first_success_on_ambiguous_bytes():
    """🚨 Shift-JIS and Big5 both decode many of the same bytes without error.

    First-success returns whichever codec is earlier in the list -- a coin flip
    wearing detection's clothes. The real Japanese text must score higher as
    Japanese than as Chinese.
    """
    data = JA.encode("cp932")
    picked = E.pick_by_plausibility(data)
    assert picked is not None
    _score, codec, text, all_scores = picked

    decoded_ok = dict((c, s) for c, s in all_scores)
    assert codec in ("cp932", "shift_jis"), (
        "picked %s; scores were %s" % (codec, all_scores))
    assert u"うずまき" in text

    # If big5 also decoded it, it must have scored strictly worse -- otherwise
    # this test is passing on absence rather than on discrimination.
    if "big5" in decoded_ok:
        assert decoded_ok["big5"] < decoded_ok[codec], all_scores


def test_plausibility_prefers_real_text_to_mojibake():
    real = E.plausibility(u"第113話「うずまきナルト」それをしないってことは")
    junk = E.plausibility(u"�\x01\x02\x03")
    assert real > 0.9, real
    assert junk < 0.2, junk
    assert real > junk


def test_plausibility_penalises_halfwidth_katakana_runs():
    """Long half-width katakana runs are what Japanese looks like through the
    wrong table. Real subtitles use one or two; they do not use ten."""
    clean = E.plausibility(u"それをしないってことは、つまり相手の人格の否定だ。")
    moji = E.plausibility(u"ｿﾚｦｼﾅｲｯﾃｺﾄﾊﾂﾏﾘｱｲﾃﾉｼﾞﾝｶｸﾉﾋﾃｲﾀﾞ")
    assert clean > moji, (clean, moji)


def test_plausibility_of_nothing_is_zero():
    assert E.plausibility(u"") == 0.0


# --------------------------------------------------------------------------
# writing back
# --------------------------------------------------------------------------

def test_encode_back_refuses_rather_than_substituting():
    """⛔ If edited text cannot be written in the original codec that is a
    REFUSAL the caller must handle. Silently switching to UTF-8 is the bug this
    whole module exists to prevent."""
    # Must be a file that is genuinely NOT utf-8, or the ladder resolves it as
    # utf-8 and the test proves nothing. `café` in cp1252 is 0xE9, which is
    # invalid utf-8, so this reaches the scored rung.
    data = u"Café naïve résumé crème brûlée\n".encode("cp1252")
    d = E.sniff_and_decode(data)
    assert d.encoding != "utf-8", d.encoding
    assert E.encode_back(d.text, d) == data

    with pytest.raises(UnicodeEncodeError):
        E.encode_back(d.text + u"日本語", d)


def test_line_endings_are_preserved_by_round_trip():
    """Line endings are on the MUST NEVER CHANGE list (spec/03-permissions).

    They survive here because nothing splits or rejoins lines -- the text keeps
    whatever it arrived with.
    """
    for ending in ("\r\n", "\n", "\r"):
        data = (u"1%s00:00:01,000 --> 00:00:02,000%shi%s" % (ending, ending, ending)).encode("utf-8")
        d = E.sniff_and_decode(data)
        assert E.encode_back(d.text, d) == data, repr(ending)


def test_mixed_line_endings_survive():
    data = b"1\r\n00:00:01,000 --> 00:00:02,000\nhi\rthere\r\n"
    d = E.sniff_and_decode(data)
    assert E.encode_back(d.text, d) == data


def test_sniff_rejects_a_string():
    """A str here means somebody already decoded it with unknown rules, which
    is precisely the information this module exists to preserve."""
    with pytest.raises(TypeError):
        E.sniff_and_decode(u"already text")
