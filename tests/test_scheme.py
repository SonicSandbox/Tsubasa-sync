# -*- coding: utf-8 -*-
"""
Per-folder scheme inference. RUNBOOK step A4.

⭐ The claim: a user's own folder is a labelled corpus of one show. Across one
season the group, resolution, codec and year are CONSTANT and the episode
number MOVES, so the episode column can be found without recognising any
pattern at all.

This is the mechanism the spec names for the cases no regex can reach --
`86 (Eighty-Six)`, `91 Days`, `07-Ghost`, `5-toubun no Hanayome`. Alone, both
numbers in `86 - Eighty Six - 03` are plausible episodes. In a folder it is
trivial: `86` appears in every filename and `03` does not.

⛔ And the counter-claim, tested just as hard: it must return NOTHING on weak
evidence. It exists to rescue files the parsers got wrong; a bad inference
would instead overrule the ones they got right.
"""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tsubasa.naming import scheme as S                      # noqa: E402
from tsubasa.naming.episode import parse_ours               # noqa: E402


def folder(*names):
    return S.resolve_folder(list(names))


# --------------------------------------------------------------------------
# ⭐ the cases no regex can reach
# --------------------------------------------------------------------------

def test_a_numeric_title_is_disambiguated_by_the_folder():
    """`86 - Eighty Six - 03` alone is ambiguous: 86 and 03 are both plausible
    episodes. Across a folder, 86 never moves."""
    got, schemes = folder(
        u"[SubsPlease] 86 - Eighty Six - 01 (720p) [AAAAAAAA].ass",
        u"[SubsPlease] 86 - Eighty Six - 02 (720p) [BBBBBBBB].ass",
        u"[SubsPlease] 86 - Eighty Six - 03 (720p) [CCCCCCCC].ass",
        u"[SubsPlease] 86 - Eighty Six - 04 (720p) [DDDDDDDD].ass",
    )
    assert sorted(v for v in got.values() if v is not None) == [1, 2, 3, 4], got


def test_a_leading_number_in_the_title_is_not_the_episode():
    got, _s = folder(
        u"5-toubun no Hanayome - 05.srt",
        u"5-toubun no Hanayome - 06.srt",
        u"5-toubun no Hanayome - 07.srt",
    )
    assert sorted(v for v in got.values() if v is not None) == [5, 6, 7], got


def test_3_gatsu_no_lion():
    got, _s = folder(
        u"[HorribleSubs] 3-gatsu no Lion - 01 [1080p].ass",
        u"[HorribleSubs] 3-gatsu no Lion - 02 [1080p].ass",
        u"[HorribleSubs] 3-gatsu no Lion - 03 [1080p].ass",
    )
    assert sorted(v for v in got.values() if v is not None) == [1, 2, 3], got


def test_a_real_coalgirls_style_folder():
    got, schemes = folder(
        u"[Coalgirls]_Bakemonogatari_01_(1920x1080_Blu-ray_FLAC)_[9787055F].ass",
        u"[Coalgirls]_Bakemonogatari_02_(1920x1080_Blu-ray_FLAC)_[A1B2C3D4].ass",
        u"[Coalgirls]_Bakemonogatari_03_(1920x1080_Blu-ray_FLAC)_[E5F6A7B8].ass",
    )
    assert sorted(v for v in got.values() if v is not None) == [1, 2, 3], got


# --------------------------------------------------------------------------
# ⛔ what must NOT be chosen as the episode column
# --------------------------------------------------------------------------

def test_a_constant_resolution_is_never_the_episode():
    got, _s = folder(
        u"Show - 01 [1080p].ass",
        u"Show - 02 [1080p].ass",
        u"Show - 03 [1080p].ass",
    )
    assert sorted(v for v in got.values() if v is not None) == [1, 2, 3]


def test_a_VARYING_resolution_is_still_not_the_episode():
    """⚠ The harder case. A folder mixing 720p and 1080p has a resolution
    column that VARIES -- so 'it changes' alone is not enough evidence."""
    got, schemes = folder(
        u"Show - 01 [720p].ass",
        u"Show - 02 [1080p].ass",
        u"Show - 03 [720p].ass",
        u"Show - 04 [1080p].ass",
    )
    vals = sorted(v for v in got.values() if v is not None)
    assert vals == [1, 2, 3, 4], (vals, schemes)


def test_a_year_column_is_not_the_episode():
    got, _s = folder(
        u"Broadcast 2012 01.srt",
        u"Broadcast 2013 02.srt",
        u"Broadcast 2014 03.srt",
    )
    vals = sorted(v for v in got.values() if v is not None)
    assert vals == [1, 2, 3], vals


def test_a_crc32_hex_run_is_not_mistaken_for_a_number():
    """CRC tags are hex; `9787055F` tokenises as digits+word, not one number."""
    got, _s = folder(
        u"[G] Show - 01 [9787055F].ass",
        u"[G] Show - 02 [A1B2C3D4].ass",
        u"[G] Show - 03 [12345678].ass",
    )
    vals = sorted(v for v in got.values() if v is not None)
    assert vals == [1, 2, 3], vals


# --------------------------------------------------------------------------
# ⛔ silence on weak evidence
# --------------------------------------------------------------------------

def test_a_single_file_yields_no_scheme():
    """Inference needs a folder. One file is not a corpus."""
    got, schemes = folder(u"[G] Show - 01 [1080p].ass")
    assert schemes == {}
    assert all(v is None for v in got.values())


def test_two_files_are_not_enough_evidence():
    """🚨 With two files a CONSTANT column passes by arithmetic alone: one
    distinct value of two is a ratio of 0.5, which is not `< 0.5`. So two
    copies of one episode produced `Scheme(slot=0, conf=0.75)` and answered 5
    for both -- a confident inference from no evidence at all.

    ⚠ The check is on the SCHEME, not just the answer. Asserting only that
    `episode_of` returns None would still pass if the scheme were believed and
    happened to point at a column these two files share."""
    got, schemes = folder(u"Show - 05.srt", u"Show - 05.ass")
    assert schemes == {}, schemes
    assert all(v is None for v in got.values()), got


def test_three_files_are():
    """The other direction, or the fix above is just 'infer nothing'."""
    got, _s = folder(u"Show - 05.srt", u"Show - 06.srt", u"Show - 07.srt")
    assert sorted(v for v in got.values() if v is not None) == [5, 6, 7], got


def test_an_unknown_shape_returns_none_rather_than_guessing():
    _got, schemes = folder(
        u"[G] Show - 01 [1080p].ass",
        u"[G] Show - 02 [1080p].ass",
    )
    assert S.episode_of(u"totally.different.naming.S01E05.srt", schemes) is None


def test_files_with_no_numbers_at_all_yield_nothing():
    got, schemes = folder(u"Movie Title.srt", u"Another Movie.srt")
    assert all(v is None for v in got.values())


def test_a_constant_number_column_is_rejected():
    """Every file says `01`. That is not an episode column, it is a constant."""
    got, _s = folder(
        u"Show 01 partA.srt", u"Show 01 partB.srt", u"Show 01 partC.srt")
    assert all(v is None for v in got.values()), got


# --------------------------------------------------------------------------
# mixed folders
# --------------------------------------------------------------------------

def test_two_schemes_in_one_folder_are_handled_separately():
    """🚨 Measured on the real corpus: 35 of 229 video-naming shows carry more
    than one naming scheme inside a single directory."""
    got, schemes = folder(
        u"Bakemonogatari - 11.ass",
        u"Bakemonogatari - 12.ass",
        u"Bakemonogatari - 13.ass",
        u"[Coalgirls]_Bakemonogatari_01_(1920x1080_Blu-ray)_[9787055F].ass",
        u"[Coalgirls]_Bakemonogatari_02_(1920x1080_Blu-ray)_[A1B2C3D4].ass",
        u"[Coalgirls]_Bakemonogatari_03_(1920x1080_Blu-ray)_[E5F6A7B8].ass",
    )
    assert len(schemes) >= 2, schemes
    resolved = sorted(v for v in got.values() if v is not None)
    assert resolved == [1, 2, 3, 11, 12, 13], resolved


def test_the_dominant_scheme_is_the_one_with_most_files():
    _got, schemes = folder(
        u"[G] Show - 01 [1080p].ass",
        u"[G] Show - 02 [1080p].ass",
        u"[G] Show - 03 [1080p].ass",
        u"Show 11.srt",
        u"Show 12.srt",
    )
    d = S.dominant(schemes)
    assert d is not None and d.n_files == 3, schemes


# --------------------------------------------------------------------------
# tokenisation
# --------------------------------------------------------------------------

def test_separators_are_collapsed_so_punctuation_variants_group_together():
    a, _n = S.tokenize(u"Show - 01 [1080p].ass")
    b, _n2 = S.tokenize(u"Show_-_02_[1080p].ass")
    assert a == b, (a, b)


def test_numbers_are_returned_in_order():
    shape, nums = S.tokenize(u"[G] Show S2 - 05 [1080p] [ABCD1234].ass")
    assert nums[0] == 2 and 5 in nums and 1080 in nums, nums


def test_full_width_digits_are_seen_as_numbers():
    """🚨 The separator class is "not a digit, Latin letter, kana or kanji" --
    and FULL-WIDTH digits are in it, so `（０１）` was eaten as punctuation and
    the episode column simply vanished. Measured: **6.2% of the catalogue**
    carries a full-width episode marker."""
    _shape, nums = S.tokenize(
        u"正直不動産（０１）「木曜劇場」 - [1440-FHD@KFMVFR.hevc10_crf 20_p 8][字].ass")
    assert 1 in nums, nums
    assert nums[0] == 1, (
        "the episode must be the FIRST number; got %r, so an encoder tag "
        "still leads and inference will learn the wrong slot" % (nums,))


#: Full-width digits, for building fixtures that are ACTUALLY full-width.
#
# 🚨 An ASCII fixture cannot test an encoding rule (LEDGER.md §Harness), and
# this test caught itself doing it: `u"（０%d）" % i` substitutes an **ASCII**
# digit, so `（０1）` was half real and the ASCII `1` was matched by `\d+`
# whatever the tokenizer did with width. The check passed with the fix removed
# -- found by the mutation run, not by reading it.
_FW = u"０１２３４５６７８９"


def _fw(n):
    return u"".join(_FW[int(c)] for c in str(n))


@pytest.mark.parametrize("names", [
    # `（０１）` -- the NHK broadcast-rip shape, with encoder tags that vary
    [u"正直不動産（%s）「木曜劇場」 - [1440-FHD@KFMVFR.hevc10_crf 20_p 8][字].ass" % _fw("0%d" % i)
     for i in (1, 2, 3, 4)],
    # `＃０１` -- the other full-width marker, common on TBS captures
    [u"アンナチュラル ＃%s.srt" % _fw("0%d" % i) for i in (1, 2, 3, 4)],
])
def test_a_full_width_episode_column_is_inferred(names):
    """⭐ The compounding failure this closes: the digits vanished, so a
    two-file group promoted the `10` of `hevc10` into the episode slot at 0.75
    confidence, and probe 3 learned that slot for 72 files of the template."""
    got, _s = S.resolve_folder(names)
    assert sorted(v for v in got.values() if v is not None) == [1, 2, 3, 4], got


def test_a_word_token_keeps_its_value_so_shapes_do_not_over_merge():
    """Two different shows must not land in one shape group just because they
    have the same punctuation."""
    a, _ = S.tokenize(u"Bleach - 01.ass")
    b, _ = S.tokenize(u"Naruto - 01.ass")
    assert a != b


# --------------------------------------------------------------------------
# ⭐ against the real corpus
# --------------------------------------------------------------------------

@pytest.fixture(scope="module")
def real_folders():
    from tsubasa.paths import corpus_root, load_config
    from tsubasa.dev.corpus import shows

    cfg = load_config(ROOT)
    root = corpus_root(cfg, ROOT)
    if not root.is_dir():
        pytest.skip("SKIPPED, NOT PASSED: corpus absent on this machine")

    out = []
    base = root / "video-naming"
    if not base.is_dir():
        pytest.skip("SKIPPED, NOT PASSED: video-naming slice absent")
    for show in shows("dev", scope="video-naming", cfg=cfg)[:40]:
        d = base / show
        if not d.is_dir():
            continue
        names = [f for f in os.listdir(str(d)) if not f.startswith("_")]
        if len(names) >= 4:
            out.append((show, names))
    if len(out) < 5:
        pytest.skip("SKIPPED, NOT PASSED: too few real folders")
    return out


def test_inference_agrees_with_the_parser_on_real_folders(real_folders):
    """⭐ Two INDEPENDENT mechanisms on the same files. Inference never
    consults the parsers, so agreement is evidence and disagreement is a
    candidate for arbitration -- not noise."""
    agree = disagree = only_parser = only_scheme = 0
    examples = []
    for show, names in real_folders:
        got, _schemes = S.resolve_folder(names)
        for n in names:
            inferred = got[n]
            parsed = parse_ours(n).episode
            if inferred is None and parsed is None:
                continue
            if inferred is None:
                only_parser += 1
            elif parsed is None:
                only_scheme += 1
            elif inferred == parsed:
                agree += 1
            else:
                disagree += 1
                if len(examples) < 8:
                    examples.append((n, parsed, inferred))

    total = agree + disagree
    assert total >= 50, "only %d comparable files -- too few to mean anything" % total
    rate = agree / float(total)
    assert rate >= 0.90, (
        "inference and the parser agree on only %.1f%% of %d files; "
        "examples (name, parser, inferred): %s" % (100 * rate, total, examples))


def test_inference_rescues_files_the_parser_missed(real_folders):
    """The reason this step exists: it must resolve something the parsers did
    not. If it never does, it is dead weight."""
    rescued = 0
    for show, names in real_folders:
        got, _schemes = S.resolve_folder(names)
        for n in names:
            if got[n] is not None and parse_ours(n).episode is None:
                rescued += 1
    assert rescued > 0, (
        "inference resolved nothing the parser missed across %d folders -- it "
        "is not earning its place" % len(real_folders))
