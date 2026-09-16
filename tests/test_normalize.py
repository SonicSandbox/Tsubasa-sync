# -*- coding: utf-8 -*-
"""
Title normalization. RUNBOOK step A1.

Every case here comes from spec/06-edge-cases.md §2, and most of them are real
shows that a naive slug gets wrong.

⭐ The organising tension: fold hard enough that four romanisations of one
title match, but not so hard that four DIFFERENT SEASONS collapse into one.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tsubasa.naming import normalize, overlap, script_of      # noqa: E402

# ⚠ `tsubasa.naming.normalize` is BOTH a module and -- after __init__ re-exports
# it -- a function. Attribute access gives the function, so `import
# tsubasa.naming.normalize as _n` binds the wrong thing and every attribute
# check on it fails naming the wrong cause. Reach into sys.modules for the
# module itself.
_n = sys.modules["tsubasa.naming.normalize"]                   # noqa: E402


def key(s):
    return normalize(s).key


def sig(s):
    return normalize(s).signature


# --------------------------------------------------------------------------
# 🚨 §2.2 -- titles differing ONLY by punctuation are DIFFERENT SHOWS
# --------------------------------------------------------------------------

def test_gintama_seasons_are_not_collapsed():
    """subsync's slug was `[^A-Za-z0-9]+ -> ''`, which makes these one show.
    They are four separate seasons."""
    titles = [u"Gintama", u"Gintama'", u"Gintama°", u"Gintama."]
    normed = [normalize(t) for t in titles]
    assert len(set(normed)) == 4, (
        "collapsed to %d distinct values: %s"
        % (len(set(normed)), [(n.key, n.signature) for n in normed]))


def test_the_punctuation_signature_is_what_separates_them():
    """The KEYS are equal on purpose -- that is what makes them candidates.
    The SIGNATURE is what tells them apart."""
    assert key(u"Gintama") == key(u"Gintama'") == key(u"Gintama°")
    assert sig(u"Gintama") == u""
    assert sig(u"Gintama'") == u"'"
    assert sig(u"Gintama°") == u"°"


def test_steins_gate_zero_is_a_different_show():
    assert key(u"Steins;Gate") == key(u"Steins Gate")
    assert key(u"Steins;Gate") != key(u"Steins;Gate 0")


@pytest.mark.parametrize("title", [u"Yuru Camp△", u"K-On!"])
def test_trailing_punctuation_survives_in_the_signature(title):
    assert sig(title), "%r lost its punctuation entirely" % title


@pytest.mark.parametrize("title", [u"Re:Zero", u"Steins;Gate", u"Fate/Zero"])
def test_internal_punctuation_is_not_in_the_signature(title):
    """⭐ POSITION is the rule, and it is what makes both spec cases work at
    once. `Steins;Gate` and `Steins Gate` are the SAME show, so an internal
    semicolon cannot be a distinguishing mark -- while `Gintama` / `Gintama'` /
    `Gintama°` / `Gintama.` are four different seasons, distinguished purely by
    what sits at the END."""
    assert sig(title) == u"", (title, sig(title))


def test_the_position_rule_satisfies_both_spec_cases():
    from tsubasa.naming.series import same_series
    assert same_series(u"Steins;Gate", u"Steins Gate")[0] == "same"
    assert same_series(u"Gintama", u"Gintama'")[0] == "different"


def test_smart_and_straight_quotes_fold():
    """🚨 NFKC does NOT fold U+2019, so `Gintama’` and `Gintama'` were two
    different shows -- the exact show the signature mechanism exists for."""
    assert sig(u"Gintama’") == sig(u"Gintama'") == u"'"
    assert normalize(u"Gintama’") == normalize(u"Gintama'")


def test_full_width_punctuation_reaches_the_signature():
    """🚨 The signature was taken BEFORE width folding, so `K-On！` scored an
    empty signature against `K-On!`'s `!` and they became different shows.
    11.9% of corpus filenames carry a full-width character."""
    assert sig(u"K-On！") == sig(u"K-On!") == u"!"


# --------------------------------------------------------------------------
# §2.3 -- romanisation and Unicode all fold to one key
# --------------------------------------------------------------------------

def test_macrons_and_digraphs_fold_together():
    """Tōkyō / Toukyou / Tokyo / Tohkyoh are one place."""
    forms = [u"Tōkyō", u"Toukyou", u"Tokyo", u"Tohkyoh"]
    keys = {key(f) for f in forms}
    assert len(keys) == 1, dict(zip(forms, [key(f) for f in forms]))


def test_long_vowel_folding_does_not_eat_a_real_h():
    """⚠ `oh` is a long vowel only before a consonant. Folding it everywhere
    turns `ohayou` into `oayo`, which is a different word."""
    assert key(u"Ohayou") == key(u"Ohayo")
    assert u"h" in key(u"Ohayou"), key(u"Ohayou")


def test_hepburn_and_kunrei_fold():
    assert key(u"Shinshi") == key(u"Sinsi")
    assert key(u"Tsutsu") == key(u"Tutu")
    assert key(u"Fuji") == key(u"Huzi")


def test_diacritics_fold():
    assert key(u"Pokémon") == key(u"Pokemon")


def test_full_width_folds_to_half_width():
    assert key(u"ＴＯＫＹＯ") == key(u"TOKYO")
    assert key(u"１２３") == key(u"123")


def test_nfc_and_nfd_agree():
    """🚨 macOS stores NFD. Without this the same file compares unequal across
    platforms -- and the corpus split would reshuffle on migration."""
    import unicodedata
    composed = u"ポケモン"
    decomposed = unicodedata.normalize("NFD", composed)
    assert composed != decomposed
    assert key(composed) == key(decomposed)


def test_ampersand_and_and_fold():
    assert key(u"Fruits & Vegetables") == key(u"Fruits and Vegetables")


def test_cjk_variants_fold():
    """剣 vs 劍 -- traditional and simplified forms of one character."""
    assert key(u"剣風伝") == key(u"劍風伝")


def test_the_cjk_variant_table_is_honest_about_being_partial():
    """⚠ A complete table needs Unihan's kTraditionalVariant data, which is a
    real dependency and is not vendored. An incomplete table that LOOKS
    complete is worse than a small one that says so -- so the source must state
    the limitation where the table is defined, not only in a commit message."""
    src = open(_n.__file__, encoding="utf-8").read()
    assert "partial" in src.lower(), (
        "the CJK variant table does not declare itself incomplete")
    assert 0 < len(_n.CJK_VARIANTS) < 500, len(_n.CJK_VARIANTS)


# --------------------------------------------------------------------------
# 🚨 §2.4 -- the CJK slug, and what keeping it costs
# --------------------------------------------------------------------------

def test_naruto_and_shippuuden_are_distinguished():
    """The discriminating information (疾風伝) is IN the filename and subsync's
    ASCII-only slug threw it away before comparing."""
    a = u"NARUTO"
    b = u"NARUTO疾風伝"
    assert key(a) != key(b)
    assert u"疾" in key(b), key(b)


def test_dropping_cjk_is_what_caused_the_bug():
    """The control: with CJK discarded, the two titles become identical. This
    is the defect, demonstrated, so the fix cannot be quietly reverted."""
    from tsubasa.naming.normalize import normalize as N
    assert N(u"NARUTO", keep_cjk=False).key == N(u"NARUTO疾風伝", keep_cjk=False).key


def test_a_purely_japanese_title_keeps_its_key():
    n = normalize(u"片田舎のおっさん、剣聖になる")
    assert n.key, "a Japanese title reduced to an EMPTY key -- this is the "\
                  "40.4% empty-slug problem Probe C measured"
    assert n.script == "cjk"


# --------------------------------------------------------------------------
# overlap -- substring, not prefix
# --------------------------------------------------------------------------

def test_same_show_under_two_romanisations_overlaps():
    """`Ace of Diamond` / `Diamond no Ace` share no prefix at all, which is why
    a prefix test failed on them."""
    assert overlap(u"Ace of Diamond", u"Diamond no Ace") >= 0.4


def test_different_shows_sharing_a_long_prefix_are_still_separable():
    """`Tongari Boushi no Memole` / `Tongari Boushi no Atelier` share 15
    characters and must NOT be treated as one show by the slug alone."""
    o = overlap(u"Tongari Boushi no Memole", u"Tongari Boushi no Atelier")
    assert o < 1.0
    assert normalize(u"Tongari Boushi no Memole") != normalize(
        u"Tongari Boushi no Atelier")


def test_aria_seasons_are_distinct():
    for a, b in [(u"Aria the Animation", u"Aria the Natural"),
                 (u"Aria the Natural", u"Aria the Origination")]:
        assert key(a) != key(b), (a, b, key(a))


def test_identical_titles_overlap_completely():
    assert overlap(u"Bleach", u"Bleach") == 1.0


def test_unrelated_titles_barely_overlap():
    assert overlap(u"Bleach", u"Naruto") < 0.4


def test_overlap_of_nothing_is_zero():
    assert overlap(u"", u"Bleach") == 0.0
    assert overlap(u"Bleach", u"") == 0.0


# --------------------------------------------------------------------------
# §2.1 -- titles that ARE numbers
# --------------------------------------------------------------------------

@pytest.mark.parametrize("title", [u"86", u"91 Days", u"07-Ghost", u"18if",
                                   u"5-toubun no Hanayome", u"3-gatsu no Lion"])
def test_numeric_titles_produce_a_usable_key(title):
    """⚠ No regex resolves these -- but normalization must not make them WORSE
    by discarding the digits that are the title."""
    assert key(title), title
    assert any(c.isdigit() for c in key(title)), (title, key(title))


# --------------------------------------------------------------------------
# script detection
# --------------------------------------------------------------------------

@pytest.mark.parametrize("text,expect", [
    (u"Bleach", "latin"),
    (u"ブリーチ", "cjk"),
    (u"片田舎のおっさん", "cjk"),
    (u"BLEACH 千年血戦篇", "mixed"),
    (u"", "other"),
])
def test_script_detection(text, expect):
    assert script_of(text) == expect


def test_script_is_recorded_not_folded_away():
    """A Japanese title and its romaji reduce to different keys BY
    CONSTRUCTION -- kana is not Latin. That is the alias table's job, and the
    pipeline needs to know which mechanism it is about to need."""
    ja = normalize(u"進撃の巨人")
    ro = normalize(u"Shingeki no Kyojin")
    assert ja.key != ro.key
    assert ja.script == "cjk" and ro.script == "latin"


# --------------------------------------------------------------------------
# robustness
# --------------------------------------------------------------------------

@pytest.mark.parametrize("junk", [None, u"", u"   ", u"[]", u"...", u"!!!",
                                  u"​", u"\U0001F600"])
def test_normalize_never_raises(junk):
    n = normalize(junk)
    assert isinstance(n.key, type(u""))
