# -*- coding: utf-8 -*-
"""
Episode and season extraction. RUNBOOK step A2.

Every case is from spec/06-edge-cases.md §1, and the ones marked 🚨 are real
files that a released parser gets wrong.

⭐ The finding that shapes this whole suite: **an absent episode number is
often the CORRECT answer.** ~8% of the corpus is films, specials and OVAs that
legitimately have none. A suite that treats those as failures chases a target
that should not move -- so `kind` is asserted everywhere, not just `episode`.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tsubasa.naming import episode as E                   # noqa: E402
from tsubasa.naming.episode import (BATCH, CONJUNCTION, EPISODE,  # noqa: E402
                                    FILM, UNKNOWN, parse_ours, union)


def ep(name):
    return parse_ours(name).episode


def kind(name):
    return parse_ours(name).kind


# --------------------------------------------------------------------------
# 🚨 §1.2 -- the verified ≥1000 defect
# --------------------------------------------------------------------------

def test_episodes_over_999_parse():
    """🚨 VERIFIED against real files. `(\\d{1,3})` caps at 999, so One Piece
    1121 parsed to None -- and the boundary is exactly 999/1000."""
    p = parse_ours(u"[SubsPlease] One Piece - 1121 (1080p) [9C7F37DD].ass")
    assert p.episode == 1121, p


def test_the_1000_boundary_from_both_sides():
    assert ep(u"[SubsPlease] One Piece - 999 (1080p) [ABCDEF12].ass") == 999
    assert ep(u"[SubsPlease] One Piece - 1000 (1080p) [ABCDEF12].ass") == 1000


def test_a_high_episode_does_not_poison_the_title():
    """🚨 The defect was DOUBLE. The number was also absorbed into the series
    slug as `onepiece1121`, so the file could not match other One Piece
    episodes by title either."""
    p = parse_ours(u"[SubsPlease] One Piece - 1121 (1080p) [9C7F37DD].ass")
    from tsubasa.naming import normalize
    assert "1121" not in normalize(p.title).key, (p.title, normalize(p.title).key)


def test_detective_conan_1100_fails_identically_without_the_fix():
    assert ep(u"[Group] Detective Conan - 1100 [1080p].srt") == 1100


def test_a_resolution_is_never_an_episode():
    """⚠ The direct consequence of widening to 4 digits: `1080` must already be
    gone before the episode patterns run."""
    for name in (u"Show Name - 05 [1080p].srt",
                 u"Show Name - 05 [1920x1080].srt",
                 u"Show.Name.S01E05.2160p.WEB-DL.srt"):
        assert ep(name) == 5, (name, ep(name))


def test_audio_layout_tags_are_not_episodes():
    """🚨 9% of Western names carry `DDP5.1` or `AAC2.0` inside dot-separated
    filenames, right next to patterns that read trailing numbers."""
    p = parse_ours(u"Yuru.Camp.SP.1080p.AMZN.WEB-DL.DDP2.0.H.264-MagicStar.srt")
    assert p.episode not in (2, 0, 264, 1080), p


def test_86_eighty_six_parses_correctly():
    """A title that IS a number, with an episode. The episode pattern matches
    before the title-number problem bites."""
    p = parse_ours(u"[SubsPlease] 86 - Eighty Six - 03v2 (720p) [EE188BDE].ass")
    assert p.episode == 3, p


def test_v2_is_a_version_not_a_digit():
    assert ep(u"[Group] Show - 51v2 [1080p].ass") == 51


# --------------------------------------------------------------------------
# 🚨 §1.2 -- the two defects measured at catalogue scale on 2026-09-08
# --------------------------------------------------------------------------

@pytest.mark.parametrize("name,want", [
    # the three most common shapes of it, all real corpus filenames
    (u"Yumeiro Patissiere SP Professional - E13 [TV].srt", 13),
    (u"[Zoro.to] Ascendance of a Bookworm - E01.srt", 1),
    (u"ヒロイック・エイジ.E25.Bandai.ja.srt", 25),
    (u"Angel Beats! - E09 - [BD].ass", 9),
    (u"Detective Conan - E0795 [Remastered version][TV].srt", 795),
    (u"Ace Of Diamond - E01 [TV].srt", 1),
    # `S1 - E01` splits the season code from the episode with a dash, so
    # S##E## cannot fire and only the bare marker is left.
    (u"Legal High S1 - E01.srt", 1),
])
def test_a_bare_E_marker_is_an_episode(name, want):
    """🚨 The third most common naming scheme on jimaku.cc, and there was no
    pattern for it. Measured over 201,785 catalogue files: adding it takes
    `unknown` from 10.6% to 2.4%."""
    assert ep(name) == want, (name, parse_ours(name))


def test_a_bare_E_marker_outranks_a_title_number():
    """🚨 `Kamen Rider 555 - E30` returned episode **555**. With no marker to
    match, the positional walk took the title's own number -- which is why the
    pattern sits ABOVE the dash/bracket/trailing patterns, not below them."""
    assert ep(u"Kamen Rider 555 - E30 [TV].srt") == 30


@pytest.mark.parametrize("name", [
    u"Yumeiro Patissiere SP Professional - E13 [TV].srt",
    u"ヒロイック・エイジ.E25.Bandai.ja.srt",
])
def test_a_bare_E_marker_does_not_survive_into_the_series_title(name):
    """⭐ The half the parser GATE could not see. Another parser rescued the
    episode, so the file scored as resolved -- while our title kept a
    different `E##` on every file of the show, and two files of one series
    looked like two different series. Measured: 9.1% of titles, now 0.9%."""
    import re as _re
    title = parse_ours(name).title
    assert not _re.search(r"(?<![A-Za-z0-9])[eE]\d{1,4}(?![A-Za-z0-9])", title), title


@pytest.mark.parametrize("name,want", [
    (u"[Anime Time] JoJo's Bizarre Adventure Stone Ocean - 03 (2).ass", 3),
    (u"[Judas] Bleach - 162 (2).sup", 162),
    (u"Neon Genesis Evangelion - 01 - 1080p Hi10p [462728C9] (10).ass", 1),
    (u"Link Click S01E01 (2).ass", 1),
])
def test_the_browser_collision_suffix_is_never_the_episode(name, want):
    """🚨 SONIC'S OWN LIBRARY SHAPE. One video's language tracks land as
    `name.ass`, `name (2).ass`, `name (3).ass`; the bracket-of-pure-digits rule
    takes the LAST match, so the copy index won.

    Measured on the non-sealed video corpus: 2,602 files carry the suffix on a
    base that parses, and **2,108 of them (81.0%) got the wrong episode** --
    a confident wrong answer on a real pair, in the layout the tool exists to
    serve."""
    assert ep(name) == want, (name, parse_ours(name))


def test_the_collision_suffix_does_not_eat_a_real_year_or_a_real_number():
    """⚠ The other direction. Four digits is a year, not a copy index, and a
    bare trailing number with no parentheses is untouched."""
    assert parse_ours(u"Kimi no Na wa. (2016).srt").episode is None
    assert ep(u"[Group] Show - 05.ass") == 5


# --------------------------------------------------------------------------
# §1.3 -- new cases
# --------------------------------------------------------------------------

def test_episode_zero_is_valid_and_falsy():
    """⚠ `0` is a real episode (OVAs, prologues) AND it is falsy. Every check
    must be `is not None`, never truthiness."""
    p = parse_ours(u"[Group] Show - 00 [1080p].ass")
    assert p.episode == 0
    assert p.has_episode is True, "a falsy episode was treated as absent"


@pytest.mark.parametrize("name,want", [
    (u"[Group] Show - 13.5 [1080p].ass", 13.5),
    # 🚨 Single-digit halves were eaten by the audio-layout stripper before the
    # half-episode pattern ran, so 13.5 worked and 7.5 returned nothing. Both
    # are named in spec/06 §1.3; testing only one hid the bug.
    (u"[Group] Show - 7.5 [1080p].ass", 7.5),
])
def test_half_episodes(name, want):
    assert parse_ours(name).episode == want, parse_ours(name)


def test_an_audio_layout_is_still_not_a_half_episode():
    """The other direction of the same fix -- `DDP5.1` must not read as 5.5."""
    p = parse_ours(u"Show.Name.S01E05.1080p.WEB-DL.DDP5.1.H.264-GROUP.srt")
    assert p.episode == 5, p


def test_season_zero_is_a_real_season():
    p = parse_ours(u"Show.Name.S00E01.WEBRip.srt")
    assert p.season == 0 and p.episode == 1, p


def test_double_episodes_are_captured_as_a_range():
    p = parse_ours(u"[Group] Show - 01-02 [1080p].ass")
    assert p.episode == 1 and p.episode_end == 2, p


def test_a_batch_range_refuses_rather_than_guessing():
    """⛔ `01~12` is a whole batch. Assigning it episode 1 silently retimes
    twelve episodes to one video's timing."""
    p = parse_ours(u"[Group] Show 01~12 [1080p][Batch].ass")
    assert p.kind == BATCH
    assert p.episode is None
    assert p.reason


def test_two_shows_in_one_file_refuses():
    """🚨 FOUND IN THE REAL CORPUS. Two series, two seasons, two episode
    numbers, one subtitle file. Every parser returns one answer or none;
    picking a half silently retimes to the wrong show."""
    p = parse_ours(u"RinjouS01EP10_(1st_part)_&_AibouS06EP11_(2nd_part).srt")
    assert p.kind == CONJUNCTION, p
    assert p.episode is None
    assert p.reason


def test_a_hyphen_with_no_separating_space():
    """🚨 Found by Probe A. The old pattern needed `[\\s._]-`, so a hyphen
    attached directly to a word was missed. A real and common form."""
    assert ep(u"tsukaiyou-01.srt") == 1


def test_date_stamped_broadcasts_do_not_invent_an_episode():
    """🚨 Found by Probe A. No episode number exists -- the date IS the
    identifier. Reading `08` as an episode is a confident wrong answer."""
    for name in (u"照柿（２）堕落の森 - (2012.08.25).srt",
                 u"Something 2012-08-07 broadcast.srt"):
        p = parse_ours(name)
        assert p.episode is None, (name, p)
        assert p.kind == FILM and "date" in p.extras, p


@pytest.mark.parametrize("name", [
    u"劇場版 Free!-Timeless Medley- 約束.srt",
    u"闘牌伝説アカギ2006特別版.srt",
    u"Show Name - Making-of.srt",
    u"Show Name - Director's Cut.srt",
    u"Show Name OVA.srt",
])
def test_an_explicit_film_marker_classifies_the_file(name):
    """⛔ ~8% of the corpus correctly has no episode number. Where the filename
    SAYS so, we must say so too -- with a reason, so a human reading the
    refusal knows it was a classification and not a failure."""
    p = parse_ours(name)
    assert p.kind == FILM, (name, p)
    assert p.episode is None
    assert p.reason


@pytest.mark.parametrize("name", [
    u"Fragtime (BD 1280x720).srt",
    u"Kingsglaive - Final Fantasy XV.srt",
])
def test_a_film_with_no_marker_is_honestly_unknown(name):
    """⚠ These ARE films, but nothing in the filename says so, and inventing a
    classification we cannot support is worse than admitting we do not know.
    The pipeline resolves them by title + duration, not by the name.

    What matters here is only that no episode number is INVENTED."""
    p = parse_ours(name)
    assert p.episode is None, (name, p)
    assert p.kind in (FILM, UNKNOWN)


def test_leading_zeros_are_the_same_episode():
    assert ep(u"[Group] Show - 007 [1080p].ass") == 7
    assert ep(u"[Group] Show - 7 [1080p].ass") == 7


@pytest.mark.parametrize("name,season", [
    (u"[Group] Show S2 - 05.ass", 2),
    (u"[Group] Show 2nd Season - 05.ass", 2),
    (u"[Group] Show Part 2 - 05.ass", 2),
    (u"[Group] Show Cour 2 - 05.ass", 2),
])
def test_season_markers_are_season_level_never_episode_level(name, season):
    p = parse_ours(name)
    assert p.season == season, p
    assert p.episode == 5, p


# --------------------------------------------------------------------------
# §1.1 -- the regression set
# --------------------------------------------------------------------------

@pytest.mark.parametrize("name,expected", [
    (u"Code_Geass_05_(1080p).srt", 5),
    (u"Gurren.Lagann.-.01.srt", 1),
    (u"Code Geass R1 1x05.srt", 5),
    (u"Show 3rd Season [53][Ma10p_1080p].ass", 53),
    (u"[Erai-raws] Show - 02 [1080p][Multiple Subtitle].ass", 2),
])
def test_regression_patterns(name, expected):
    assert ep(name) == expected, (name, parse_ours(name))


def test_japanese_episode_marker_outranks_a_platform_season_code():
    """🚨 `NARUTO…疾風伝.S06E01.第113話` is episode 113. Reading the S06E01
    gives 1, and the file never pairs."""
    p = parse_ours(u"NARUTO-ナルト-疾風伝.S06E01.第113話.WEBRip.Netflix.ja[cc].srt")
    assert p.episode == 113, p


def test_a_bracket_of_pure_digits_is_an_episode():
    assert ep(u"[Group] Show [05] [1080p].ass") == 5


# --------------------------------------------------------------------------
# group extraction -- both cultures
# --------------------------------------------------------------------------

def test_a_leading_bracket_group_is_captured():
    p = parse_ours(u"[SubsPlease] Show - 05 (1080p).ass")
    assert p.group == "SubsPlease", p


def test_a_trailing_suffix_group_is_captured():
    """🚨 33% of 904 Western release names put the group AFTER a hyphen.
    subsync stripped only a leading bracket, which is 1% there."""
    p = parse_ours(u"Show.Name.S01E05.1080p.WEB-DL.DDP5.1.H.264-MagicStar.srt")
    assert p.group == "MagicStar", p


def test_a_trailing_number_is_not_mistaken_for_a_group():
    """⚠ The old input had a LEADING bracket, so the trailing branch was an
    `else` that never ran and the isdigit() guard this test is named for was
    completely unexercised. Use a name with no leading group."""
    p = parse_ours(u"Show.Name.S01E05-05.srt")
    assert p.group is None, p
    p2 = parse_ours(u"[Group] Show - 05.ass")
    assert p2.group == "Group"


# --------------------------------------------------------------------------
# 🚨 a release year is never an episode  (found by review)
# --------------------------------------------------------------------------

@pytest.mark.parametrize("name", [
    u"Inception (2010).en.srt",
    u"Inception.2010.1080p.BluRay.x264-GROUP.srt",
    u"Blade Runner (1982) [Final Cut].srt",
    u"君を愛したひとりの僕へ.2022.srt",
])
def test_a_release_year_is_never_an_episode(name):
    """🚨 A Rule 2 violation that shipped: `ep=2010`. Worse than a miss --
    two different films both key to (None, 2010), so an episode-keyed index
    buckets a whole film library under one fabricated episode."""
    p = parse_ours(name)
    assert p.episode is None, (name, p)


def test_a_film_whose_only_number_is_a_year_is_classified_not_missed():
    p = parse_ours(u"Inception.2010.1080p.BluRay.x264-GROUP.srt")
    assert p.kind == FILM, p
    assert p.reason and "year" in p.reason


def test_a_four_digit_episode_still_parses_despite_the_year_rule():
    """The guard must not cost real coverage: One Piece really does reach 1121."""
    assert parse_ours(
        u"[SubsPlease] One Piece - 1121 (1080p) [9C7F37DD].ass").episode == 1121


# --------------------------------------------------------------------------
# 🚨 the noise list must not eat real title words  (found by review)
# --------------------------------------------------------------------------

@pytest.mark.parametrize("name,must_keep", [
    (u"Kingsglaive - Final Fantasy XV.srt", u"final"),
    (u"Bakemono no Ko.srt", u"ko"),
    (u"Ja Ja Uma - 05.srt", u"ja"),
    (u"Mad Max Fury Road.srt", u"max"),
    (u"Gintama Final.srt", u"final"),
])
def test_short_tokens_are_only_noise_in_a_tag_context(name, must_keep):
    """🚨 A two-letter language code and a word in a title are the same
    characters; only the context differs. Stripping them as bare words turned
    `Kingsglaive - Final Fantasy XV` -- spec/09's own example of a legitimate
    film title -- into `Kingsglaive Fantasy XV`."""
    title = parse_ours(name).title.lower()
    assert must_keep in title, (name, title)


def test_tags_in_a_real_tag_context_are_still_stripped():
    """The other direction, or the fix above is just 'strip nothing'."""
    t = parse_ours(
        u"Show.Name.S01E05.1080p.NF.WEB-DL.DDP5.1.H.264-GROUP.ja[cc].srt").title
    assert "nf" not in t.lower().split()
    assert "cc" not in t.lower()


# --------------------------------------------------------------------------
# robustness
# --------------------------------------------------------------------------

@pytest.mark.parametrize("name", [
    u"", u".", u"[", u"[Unclosed - 01", u"[Group [Sub] Name] - 05.ass",
    u"[A][B]Name - 01[D][E].ass", u"...", u"----", u"\U0001F600.srt",
])
def test_malformed_names_never_crash(name):
    p = parse_ours(name)
    assert p.kind in (EPISODE, FILM, BATCH, CONJUNCTION, UNKNOWN)


def test_malformed_brackets_do_not_swallow_the_episode():
    assert ep(u"[Unclosed - 01.ass") == 1
    assert ep(u"[A][B]Name - 01[D][E].ass") == 1


# --------------------------------------------------------------------------
# ⭐ the union
# --------------------------------------------------------------------------

def test_all_three_parsers_are_reachable():
    """⚠ REPLACES `test_all_three_parsers_run`, which asserted all three ran on
    every name. That is no longer the contract (see the laziness tests below),
    but the reachability it was really guarding still matters: a mutation
    deleting a parser must still be killed by something."""
    u = union(u"[SubsPlease] Show - 05 (1080p) [ABCDEF12].ass", force=True)
    sources = {r.source for r in u.results}
    assert sources == {"ours", "anitopy", "guessit"}, (
        "only %s could be reached even under force=True" % sorted(sources))


def test_a_clean_name_is_settled_by_ours_alone(monkeypatch):
    """⭐ THE 97.6% PATH, and the whole point of the reversal. anitopy costs 8x
    our parser and guessit costs 125x; on a name we resolved, with nothing
    contradicting us, neither can tell us anything we do not already know.

    ⚠ Counts CALLS, not results. Asserting only on `u.results` would pass
    against code that runs a parser and discards its answer -- which pays the
    27.5 ms and is exactly the cost this step exists to remove."""
    called = []
    for fn in ("parse_anitopy", "parse_guessit"):
        monkeypatch.setattr(E, fn,
                            (lambda name, _f=fn: called.append(_f) or None))
    u = union(u"[SubsPlease] Show - 05 (1080p) [ABCDEF12].ass")
    assert u.episode == 5, u
    assert u.state == E.SOLE, u.state
    assert called == [], "a third-party parser was CALLED on a settled name: %s" % called
    assert {r.source for r in u.results} == {"ours"}


def test_a_miss_escalates_to_anitopy():
    """⛔ The laziness must not become blindness. Where ours has no answer, the
    reason to ask someone else exists and the cost is worth paying."""
    u = union(u"Show Name With No Number At All.srt")
    assert "anitopy" in {r.source for r in u.results}, u.results


def test_a_western_name_nobody_settled_reaches_guessit():
    """guessit is built for the dotted, `-GROUP`-suffixed Western scene and is
    27.5 ms a name. It runs exactly there, and only when the cheap parsers
    left the file unresolved."""
    u = union(u"Show.Name.Complete.Series.1080p.WEB-DL-GROUP.srt")
    assert "guessit" in {r.source for r in u.results}, u.results


def test_a_japanese_name_never_pays_for_guessit():
    """⛔ The other direction of the same rule, and the one that carries the
    cost saving: asking guessit about a CJK filename buys nothing."""
    u = union(u"ヒロイック・エイジ.Bandai.ja.srt")
    assert "guessit" not in {r.source for r in u.results}, u.results


def test_a_folder_scheme_that_disagrees_buys_a_second_opinion():
    """⭐ Per-folder inference is the INDEPENDENT second opinion and it is far
    cheaper than another parser, so its dissent is the trigger -- and then a
    vote. ⚠ The minority survives in `candidates`: a vote is a hypothesis, and
    timing still decides."""
    u = union(u"[SubsPlease] Show - 05 (1080p) [ABCDEF12].ass", scheme_episode=9)
    assert "anitopy" in {r.source for r in u.results}, u.results
    assert 9 in u.candidates and 5 in u.candidates, u.candidates


def test_a_folder_scheme_that_AGREES_costs_nothing():
    """⚠ An agreeing scheme must not inflate a majority behind an answer we
    already hold, and must not buy a parser we do not need."""
    u = union(u"[SubsPlease] Show - 05 (1080p) [ABCDEF12].ass", scheme_episode=5)
    assert u.state == E.SOLE and {r.source for r in u.results} == {"ours"}, u


@pytest.mark.parametrize("value,name,plausible", [
    (1080, u"Show.Name.1080p.WEB-DL.srt", False),
    (720, u"Show.Name.720p.srt", False),
    (264, u"Show.Name.H.264-GROUP.srt", False),
    (2010, u"Inception (2010).en.srt", False),
    (9999, u"Show - 9999.srt", False),
    # ⚠ and the coverage the guard must not cost: One Piece really does reach
    # 1121, and Detective Conan passed 1100.
    (1121, u"[SubsPlease] One Piece - 1121 (1080p).ass", True),
    (5, u"[Group] Show - 05.ass", True),
])
def test_a_third_party_candidate_is_sanity_checked(value, name, plausible):
    """🚨 Measured on 1,200 ambiguous files: when ours and anitopy already
    agreed, guessit differed 565 times and **537 of those (95%) were a
    resolution or a year**. Every one was routed to timing arbitration -- the
    only stage that opens a file."""
    assert E._plausible(value, name) is plausible, (value, name)


def test_agreement_yields_the_episode():
    name = u"[SubsPlease] Show Name - 05 (1080p) [ABCDEF12].ass"
    u = union(name)
    assert u.episode == 5, u
    assert not u.needs_arbitration
    # ⚠ SOLE, not AGREE. Exactly one parser ran, so reporting agreement would
    # be a claim about parsers that never spoke. Asked, they do agree:
    forced = union(name, force=True)
    assert forced.episode == 5, forced
    assert forced.state in (E.AGREE, E.PARTIAL), forced.state


def test_a_refusal_is_authoritative_and_not_voted_away():
    """⛔ anitopy will happily return ONE episode for a file containing two
    shows. Letting a majority overrule the refusal reintroduces exactly the
    confident wrong answer the refusal exists to prevent."""
    u = union(u"RinjouS01EP10_(1st_part)_&_AibouS06EP11_(2nd_part).srt")
    assert u.kind == CONJUNCTION
    assert u.episode is None


def test_a_batch_refusal_survives_the_union():
    u = union(u"[Group] Show 01~12 [1080p][Batch].ass")
    assert u.kind == BATCH and u.episode is None


def test_a_strict_majority_settles_a_disagreement_for_free():
    """⭐ 90.8% of disagreements already have a 2-of-3 majority in hand.
    `sorted(set(...))` threw the multiplicity away and sent them to the only
    stage that opens a file, costed at seconds each.

    Drives the REAL `union()`. The previous version of this check constructed a
    Union by hand and asserted the constructor stored its arguments -- so the
    routing for 28.4% of live traffic had zero coverage, confirmed by a
    mutation that deleted it and killed nothing.

    ⚠ UPDATED 2026-09-08. Under lazy parsing a clean name never reaches the
    majority rule at all -- ours settles it alone, which is the point. The live
    path to it is a DISSENTING FOLDER SCHEME, which is also the shape that
    actually occurs: two mechanisms read the name one way, per-folder inference
    reads it another."""
    u = union(u"[SubsPlease] Show - 05 (1080p) [ABCDEF12].ass", scheme_episode=9)
    assert u.episode == 5, u
    assert u.state == E.MAJORITY, u.state
    # ⚠ The outvoted answer is KEPT: a majority is a strong hypothesis, not a
    # verdict, and timing may still overrule it.
    assert 9 in u.candidates, (
        "the dissenting answer was discarded, so arbitration can never see "
        "what the folder thought: %r" % (u.candidates,))


def test_a_genuine_tie_still_goes_to_arbitration():
    """A majority needs a MAJORITY. Two parsers, two answers, no winner."""
    u = E.Union(
        results=[E.Parsed(episode=3, source="ours"),
                 E.Parsed(episode=5, source="anitopy")],
        state=E.DISAGREE, episode=None, season=None,
        kind=EPISODE, candidates=[3, 5])
    assert u.needs_arbitration and u.candidates == [3, 5]


def test_the_majority_rule_cannot_invent_a_winner_from_one_vote():
    from tsubasa.naming.episode import parse_anitopy, parse_guessit
    name = u"[Group] Show - 05 [1080p].ass"
    votes = [p.episode for p in
             (parse_ours(name), parse_anitopy(name), parse_guessit(name))
             if p is not None and p.episode is not None]
    u = union(name)
    if len(set(votes)) == 1:
        assert u.state != E.MAJORITY, "unanimous is AGREE/PARTIAL, not MAJORITY"


def test_the_grouping_key_is_season_and_episode():
    """🚨 Episode ALONE manufactured 305 false pairs on multi-season shows --
    Series 1 Episode 3 scored against Series 3 Episode 3. Made three separate
    times in one session."""
    a = parse_ours(u"Show.S01E03.srt")
    b = parse_ours(u"Show.S03E03.srt")
    assert a.episode == b.episode == 3
    assert a.key() != b.key(), "season is missing from the grouping key"
