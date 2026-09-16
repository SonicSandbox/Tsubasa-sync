# -*- coding: utf-8 -*-
"""
Series identity. RUNBOOK step A3 -- the risky one.

🚨 The four cases that prove a substring ratio cannot do this job. Measured
with longest-common-substring, the true POSITIVE scores BELOW a true NEGATIVE,
so no threshold on that measure separates them:

    Ace of Diamond / Diamond no Ace           SAME       LCS ~0.57
    Tongari Boushi no Memole / ...no Atelier  DIFFERENT  LCS ~0.71

⭐ And the standing rule this suite enforces: **both directions.** Keeping CJK
in the slug fixes Naruto/Shippuuden but makes matching LESS permissive, so a
suite that only checks "different shows stay apart" would pass a matcher that
matches nothing at all.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tsubasa.naming import normalize                            # noqa: E402
from tsubasa.naming.series import (DIFFERENT, SAME, UNSURE,     # noqa: E402
                                   cross_script, same_series,
                                   similarity, tokens,
                                   THRESHOLDS_ARE_MEASURED)


def verdict(a, b):
    return same_series(a, b)[0]


# --------------------------------------------------------------------------
# 🚨 the four cases
# --------------------------------------------------------------------------

def test_same_show_under_two_romanisations_matches():
    """No shared prefix at all -- which is why a prefix test failed on it."""
    assert verdict(u"Ace of Diamond", u"Diamond no Ace") == SAME


def test_different_shows_sharing_a_long_prefix_do_not_match():
    """15 shared characters, and they are two different shows."""
    assert verdict(u"Tongari Boushi no Memole",
                   u"Tongari Boushi no Atelier") != SAME


def test_a_title_containing_another_is_not_the_same_show():
    """Naruto vs Naruto Shippuuden. One CONTAINS the other, which is exactly
    what a containment ratio cannot see."""
    assert verdict(u"Naruto", u"Naruto Shippuuden") != SAME


def test_shared_prefix_seasons_do_not_match():
    for a, b in [(u"Aria the Animation", u"Aria the Natural"),
                 (u"Aria the Natural", u"Aria the Origination")]:
        assert verdict(a, b) != SAME, (a, b, similarity(a, b))


def test_the_measure_beats_substring_overlap_on_these_four():
    """The point of the token/bigram measure, stated as a comparison: the true
    positive must now outscore the true negative, which LCS did not manage."""
    positive = similarity(u"Ace of Diamond", u"Diamond no Ace")
    negative = similarity(u"Tongari Boushi no Memole",
                          u"Tongari Boushi no Atelier")
    assert positive > negative, (positive, negative)


# --------------------------------------------------------------------------
# punctuation outranks the score
# --------------------------------------------------------------------------

def test_gintama_seasons_are_different_at_any_score():
    """⛔ Same key by design -- the signature is the ONLY thing separating four
    real seasons, so it must beat a perfect similarity score."""
    for other in (u"Gintama'", u"Gintama°", u"Gintama."):
        v, score, reason = same_series(u"Gintama", other)
        assert v == DIFFERENT, (other, v, score)
        assert "punctuation" in reason


def test_identical_titles_match():
    assert verdict(u"Bleach", u"Bleach") == SAME


# --------------------------------------------------------------------------
# ⭐ cross-script is the alias table's job, not a threshold's
# --------------------------------------------------------------------------

def test_a_japanese_title_and_its_romaji_are_unsure_not_different():
    """A Japanese title and its romaji CANNOT match on characters -- kana is
    not Latin. Calling that DIFFERENT is a confident wrong answer; UNSURE hands
    it to the alias table or to timing, which can actually settle it.

    ⚠ `use_alias=False` PINS THE CHARACTER MECHANISM, which is what this file
    is about. RUNBOOK A7 shipped a table that bridges this exact pair, so
    without the switch this check would silently stop testing the thing it is
    named for and start testing the table instead. `LEDGER.md`: a check can
    pass through a filter that is not the one it is named for.
    """
    v, _s, reason = same_series(u"Shingeki no Kyojin", u"進撃の巨人",
                                use_alias=False)
    assert v == UNSURE, v
    assert "script" in reason


def test_the_alias_table_settles_what_characters_cannot():
    """⭐ The other half of the check above, and the reason A7 exists: the same
    pair, with the table on, is SAME rather than handed to timing.

    ⚠ SKIPS rather than passing when no table has been derived on this
    machine — a skip that says so is honest; a pass would be vacuous.
    """
    from tsubasa.naming import alias as A
    if not len(A.load()):
        pytest.skip("SKIPPED, NOT PASSED: no bundled alias table. Build it "
                    "with `python -m tsubasa.dev alias --harvest --derive`.")
    v, _s, reason = same_series(u"Shingeki no Kyojin", u"進撃の巨人")
    assert v == SAME, (v, reason)
    assert reason.startswith(u"alias table:"), reason


def test_mixed_script_counts_as_cjk_bearing():
    """🚨 The bug this closes: `キャプテン翼シーズン2 ... S01E17` is MIXED because a
    platform tag put Latin letters in a Japanese title. Comparing script LABELS
    ('latin' != 'mixed', but neither is 'cjk') let a same-show pair fall through
    to a score of 0.000 and be called DIFFERENT."""
    a = normalize(u"Captain Tsubasa Junior Youth Hen")
    b = normalize(u"キャプテン翼シーズン2 ジュニアユース編 S01E17")
    assert b.script == "mixed"
    assert cross_script(a, b) is True


def test_two_latin_titles_are_not_treated_as_cross_script():
    a, b = normalize(u"Bleach"), normalize(u"Naruto")
    assert cross_script(a, b) is False


# --------------------------------------------------------------------------
# tokens
# --------------------------------------------------------------------------

def test_stopwords_are_dropped_so_word_order_stops_mattering():
    assert set(tokens(u"Ace of Diamond")) == set(tokens(u"Diamond no Ace"))


def test_tokens_come_from_the_original_not_the_folded_key():
    """⚠ Normalisation strips separators. Tokenising the KEY would give one
    giant token and the whole token-set idea would silently degrade to
    character matching."""
    assert len(tokens(u"Tongari Boushi no Memole")) >= 3


def test_cjk_runs_stay_whole():
    """⚠ Was `all(len(x) >= 1)`, which is true of every value `tokens()` can
    return -- it drops empties by construction. That asserted nothing."""
    t = tokens(u"進撃の巨人")
    assert t == (u"進撃の巨人",), t


def test_never_raises_on_none():
    """⚠ Was parametrised with `junk or u''`, which converts None to '' before
    the call -- so the None case was never actually exercised."""
    v, s, _r = same_series(None, u"Bleach")
    assert v in (SAME, UNSURE, DIFFERENT)
    assert 0.0 <= s <= 1.0
    # ⚠ A TUPLE, not a list. `tokens()` is memoised, and returning a mutable
    # list would hand every caller the same object -- one `.append()` anywhere
    # would silently corrupt the cache for every subsequent lookup.
    assert tokens(None) == ()


# --------------------------------------------------------------------------
# both directions, and the honest band
# --------------------------------------------------------------------------

def test_the_thresholds_are_measured_not_chosen():
    """Rule 2 of the pack: every threshold sits in a MEASURED band. A number
    set by taste breaks the whole value proposition."""
    assert THRESHOLDS_ARE_MEASURED is True
    import tsubasa.naming.series as S
    src = open(S.__file__, encoding="utf-8").read()
    assert "seriesgate" in src, "the derivation is not cited where the "\
                                "constants live"


def test_unsure_is_reachable_through_the_THRESHOLD():
    """⛔ There is no empty band -- measured. UNSURE must be a real outcome.

    ⚠ The previous version of this check got its only UNSURE from
    `cross_script`'s short-circuit, a completely different mechanism -- so it
    passed with the entire band collapsed (`SAME_AT == DIFFERENT_BELOW`).
    A mutation that deleted the band killed zero checks.

    This pair is same-script and scores between the two constants, so it can
    ONLY come out UNSURE if the band exists.
    """
    from tsubasa.naming.series import DIFFERENT_BELOW, SAME_AT
    a, b = u"Dr Stone", u"Dr Stone Ryuusui"
    v, score, _r = same_series(a, b)
    assert not cross_script(normalize(a), normalize(b)), "must be same-script"
    assert DIFFERENT_BELOW <= score < SAME_AT, (
        "score %.3f is outside the band, so this pair no longer tests it" % score)
    assert v == UNSURE, (v, score)


def test_collapsing_the_band_would_change_this_pair():
    """The mutation, run as a check: with SAME_AT == DIFFERENT_BELOW the pair
    above cannot be UNSURE. If this ever passes, the band is gone."""
    v, _s, _r = same_series(u"Dr Stone", u"Dr Stone Ryuusui",
                            same_at=0.5, different_below=0.5)
    assert v != UNSURE, "a zero-width band still produced UNSURE"


def test_all_three_verdicts_are_reachable():
    seen = set()
    for a, b in [(u"Bleach", u"Bleach"),
                 (u"Bleach", u"Naruto"),
                 (u"Dr Stone", u"Dr Stone Ryuusui")]:
        seen.add(verdict(a, b))
    assert seen == {SAME, DIFFERENT, UNSURE}, seen


def test_a_refusal_carries_a_reason():
    for a, b in [(u"Gintama", u"Gintama'"),
                 (u"Shingeki no Kyojin", u"進撃の巨人")]:
        _v, _s, reason = same_series(a, b)
        assert reason, (a, b)


@pytest.mark.parametrize("junk", [u"", u"   ", u"[]", u"...", None])
def test_never_raises(junk):
    v, s, _r = same_series(junk or u"", u"Bleach")
    assert v in (SAME, UNSURE, DIFFERENT)
    assert 0.0 <= s <= 1.0
