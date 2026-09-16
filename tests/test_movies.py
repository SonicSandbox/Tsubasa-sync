# -*- coding: utf-8 -*-
"""
The MOVIE path. RUNBOOK step A10, `06-edge-cases.md` §3.5.

⭐ THE CLAIM UNDER TEST, and it starts from a measured zero.

    A folder containing `Inception (2010).mkv` and `Inception (2010).en.srt`
    -- an identical stem plus a language tag -- produces **0 pairs**.

Every candidate index in this project is keyed on `(season, episode)`, and a
film has neither, so `discover.Candidates.for_video` returns `[]` for every
film in a library. The first check below asserts **both halves**: that the TV
path still cannot see the pair, and that the movie path does. A check that only
asserted the second would stay green if somebody quietly made the episode index
answer for films -- which is the defect that manufactured 305 false pairs.

🚨 THE FIXTURE RULE, AND IT IS WHY THIS FILE IS SHAPED THE WAY IT IS.

`doctrine/verification`: *a fixture where every row looks the same tests one
branch and leaves the other to production -- it is what let `0 broken of 0`
look like coverage.* So the library fixture holds **a folder with one video, a
folder with several, a folder with none, and a cuts collision**, and the
negative controls are drawn twice: uniformly, and again with the failure shape
constructed on purpose.

⚠ WHAT THIS SUITE STRUCTURALLY CANNOT COVER

* **Timing.** Rung 3 is arbitration and lives in `align`/`arbitrate`. What is
  asserted here is that an ambiguity is HANDED ON with its candidates rather
  than guessed
* **Real runtimes.** Duration is an injected seam (A9). Every duration here is
  a dictionary, so this proves the module *asks correctly*, not that any
  container reports the number -- `doctrine/verification`, the haptics case
* **Whether a pair is genuinely the same film.** Only the aligner can say that.
  This suite scores the NAME decision, which is the only thing A10 owns
"""
import io
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tsubasa import discover as D                              # noqa: E402
from tsubasa import movies as M                                # noqa: E402
from tsubasa.naming import episode as E                        # noqa: E402
from tsubasa.naming.normalize import normalize, overlap        # noqa: E402
from tsubasa.paths import corpus_root, load_config             # noqa: E402


def build(root, tree):
    """`tree` is an iterable of relative paths. Returns the root as a str."""
    for rel in tree:
        path = Path(root) / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")
    return str(root)


def walked(root):
    """(video paths, subtitle paths) as `discover` really finds them.

    ⭐ Driven through the real walk, not a hand-written list.
    `doctrine/verification`: *test the WRAPPER and the thing together* -- in
    every recorded case here it was the wrapper that lied.
    """
    items = D.walk(root)
    return ([i.path for i in items if i.kind == "video"],
            [i.path for i in items if i.kind == "subtitle"])


def by_subtitle(result):
    return dict((os.path.basename(p.subtitle), p) for p in result.pairs)


def refusal_for(result, subtitle_basename):
    for r in result.refusals:
        if os.path.basename(r.subtitle) == subtitle_basename:
            return r
    return None


# ==========================================================================
# ⭐ the regression this whole step exists for
# ==========================================================================

def test_the_proven_broken_case_now_produces_exactly_one_pair(tmp_path):
    """🚨 `06-edge-cases.md` §3.5, *Proven broken 2026-09-07*.

    ⭐ BOTH HALVES ARE ASSERTED. The episode index must still refuse the film
    -- filing films under `(None, None)` is how an entire library ends up
    bucketed under one fabricated key -- and the movie path must find it.
    """
    root = build(tmp_path, ["Films/Inception (2010)/Inception (2010).mkv",
                            "Films/Inception (2010)/Inception (2010).en.srt"])
    items = D.parse_all(D.walk(root))
    candidates = D.Candidates(items)
    videos = candidates.videos
    assert len(videos) == 1
    assert candidates.for_video(videos[0]) == [], (
        "the episode-keyed index answered for a film -- that is the "
        "(None, None) collision, not a fix")

    v, s = walked(root)
    result = M.pair_movies(v, s)
    assert len(result.pairs) == 1, result
    assert result.pairs[0].rung == M.STEM
    assert os.path.basename(result.pairs[0].video) == "Inception (2010).mkv"
    assert not result.refusals


# ==========================================================================
# the comparison key -- what has to be stripped before anything is compared
# ==========================================================================

def test_the_VIDEO_extension_is_stripped_from_the_key():
    """🚨 FIXED IN THE PARSER 2026-09-08, AND THIS CHECK RECORDS BOTH STATES.

    A10 measured that `parse_ours` stripped SUBTITLE extensions only, so
    `Inception (2010).mkv` parsed to the title `'Inception mkv'` while
    `Inception (2010).en.srt` gave `'Inception'`. On the episode path the
    marker truncation removes the extension as a side effect; on the film path
    there is no marker, so **every video title in a movie library carried
    `mkv`** — §3.5's language-tag defect arriving from the other side of the
    pair. It survived 98 naming checks and a 96.8% parser gate.

    ⭐ `episode._EXT_RE` now peels both halves, importing
    `container.KNOWN_VIDEO_EXT` rather than keeping a second copy.

    ⚠ `movies.movie_stem` still strips the extension itself, deliberately: it
    is fed raw filenames by callers who never went through the parser, and a
    key that depends on someone else having cleaned its input is a key that
    breaks at the one call site that forgot. **Both are asserted here**, so
    neither can quietly stop.
    """
    assert E.parse_ours(u"Inception (2010).mkv").title == u"Inception", (
        "the parser kept the video extension again -- see episode._EXT_RE")
    assert M.movie_stem(u"Inception (2010).mkv") == u"inception"
    assert M.movie_stem(u"Inception (2010).en.srt") == u"inception"
    # ⭐ And the property that actually matters, over every known container:
    # no key may contain its own extension.
    from tsubasa.container import KNOWN_VIDEO_EXT
    for ext in sorted(KNOWN_VIDEO_EXT):
        stem = M.movie_stem(u"Inception (2010)%s" % ext)
        assert stem == u"inception", (ext, stem)
        assert E.parse_ours(u"Inception (2010)%s" % ext).title == u"Inception"


@pytest.mark.parametrize("name", [
    u"Inception (2010).en.srt",
    u"Inception (2010).eng.forced.srt",
    u"Inception (2010).ja[sdh].srt",
    u"Inception (2010).WEBRip.Amazon.ja-jp[sdh].srt",
    u"Inception (2010).1080p.BluRay.x264-GROUP.srt",
    u"Inception (2010) (2).srt",
    # ⚠ THE CRC32 IS THE ROW ONLY `strip_noise` CAN CLEAN. Every other tag here
    # is ALSO in the learned decoration vocabulary, so a mutation removing
    # `strip_noise` alone changed nothing and the mutant read NO-OP -- real
    # defence in depth, and invisible until the mutation run said so. A hex
    # checksum appears once in the corpus and is in no vocabulary.
    u"Inception (2010) [6E211CCF].srt",
])
def test_language_and_quality_tags_are_stripped_before_the_key(name):
    """🚨 §3.5's second trap: `Inception (2010).en.srt` keys as `inceptionen`
    while the video gives `inception`, and *"it survives today only because one
    is a prefix of the other -- luck, not design."*

    ⚠ The last row is the filesystem collision suffix, which
    `LEDGER.md` measures at **2,108 of 2,602 real files** getting the wrong
    answer when it is left in place."""
    assert M.movie_stem(name) == u"inception", M.read_name(name)


@pytest.mark.parametrize("tag", [
    u".es", u".fr", u".de", u".it", u".pt-BR", u".zh-Hans", u".zh_Hant",
    u".es-419", u"[es]", u".fr.forced",
])
def test_EUROPEAN_language_tags_are_stripped_too(tag):
    """🚨 MEASURED, one tag form at a time, over the 737 real Western film
    names. `episode.SOFT_NOISE_RE` handles the Japanese-corpus forms perfectly
    -- `.en`, `.eng`, `.ja`, `.jpn`, `.en.forced`, `.en.sdh` all measured
    **100%** -- and `episode._SOFT` lists exactly `ja jp jpn en eng zh chs cht
    kor ko`, the languages this project's corpus contains.

    ⛔ **`.es`, `.fr.forced`, `.pt-BR` and `.zh-Hans` each measured 0%.** A
    Western movie library is not that population, and §3.5 is a Western-film
    use case. §4 requires language tags to be *"stripped for matching,
    retained for output naming"*."""
    assert M.movie_stem(u"Inception (2010)" + tag + u".srt") == u"inception", \
        M.read_name(u"Inception (2010)" + tag + u".srt")


@pytest.mark.parametrize("name", [
    u"It (2017).mkv", u"Us (2019).mkv", u"Up (2009).mkv", u"Pi (1998).mkv",
    u"It.2017.1080p.BluRay.x264-GROUP.mkv",
])
def test_a_TWO_LETTER_film_title_is_never_peeled_away(name):
    """⛔ `It` is Italian, `is` is Icelandic, `pa` is Punjabi -- and `It`,
    `Us`, `Up` and `Pi` are real films whose entire title is two letters. The
    language peel refuses to remove the last thing in a name for exactly this
    reason: an empty key pairs with every video in the library.

    ⭐ THE OTHER BRANCH OF THE CHECK ABOVE. A peel that only ever fires and a
    peel that never fires both pass a one-directional test."""
    read = M.read_name(name)
    assert read.is_film, read.refusal
    assert read.key, read
    assert M.movie_stem(name) == M.movie_stem(
        M.strip_extension(name) + u".en.srt"), read


def test_a_dot_separated_release_group_is_peeled_and_X_Men_is_not():
    """⭐ §3.5's own rung-2 example needs the group gone: `Inception (2010)`
    against `Inception.2010.1080p.BluRay-GROUP`.

    🚨 AND THE GATE IS WHY THIS IS SAFE. `episode.TRAILING_GROUP` matches
    `-Men` in `X-Men` perfectly happily; `parse_ours` gets away with it because
    it only RECORDS the group and never removes it. Peeling is allowed only in
    a dot-separated release name -- the naming culture, not a word list."""
    assert M.movie_stem(u"Inception.2010.1080p.BluRay.x264-GROUP.mkv") == \
        u"inception"
    assert M.movie_stem(u"Inception (2010).mkv") == u"inception"
    assert M.movie_stem(u"X-Men (2000).mkv") == M.movie_stem(u"X-Men.mkv")
    assert u"men" in M.movie_stem(u"X-Men (2000).mkv")


@pytest.mark.parametrize("name,intact_title", [
    (u"Kingsglaive - Final Fantasy XV (2016).mkv",
     u"Kingsglaive Final Fantasy XV"),
    (u"Bakemono no Ko (2015).mkv", u"Bakemono no Ko"),
    (u"Mad Max Fury Road (2015).mkv", u"Mad Max Fury Road"),
    (u"Anime Gataris.mkv", u"Anime Gataris"),
    (u"The End of Evangelion (1997).mkv", u"The End of Evangelion"),
    (u"Ja Ja Uma (2005).mkv", u"Ja Ja Uma"),
    (u"Gintama Final (2021).mkv", u"Gintama Final"),
    (u"Studio Life (2004).mkv", u"Studio Life"),
    # ⛔ THE THREE-LETTER LANGUAGE CODES ARE WHY THE TAIL PEEL IS TWO LETTERS
    # ONLY. `cat` is Catalan, `nor` Norwegian, `ice` Icelandic, `may` Malay --
    # all ISO 639-2 codes and all ordinary English words. This is the row that
    # goes red if anybody widens `_LANG2`.
    # ⚠ NO YEAR ON THESE TWO, DELIBERATELY. With a year the title word is not
    # at the tail at all -- `Big.Cat.2019.1080p` ends in the year -- so the
    # peel could never have reached it and the row would prove nothing. The
    # bare `Title.Word` form is the one where a three-letter code would bite.
    (u"Big.Cat.mkv", u"Big Cat"),
    (u"Black.Ice.mkv", u"Black Ice"),
    (u"Big.Cat.2019.1080p.BluRay.mkv", u"Big Cat"),
])
def test_no_real_title_word_is_eaten(name, intact_title):
    """🚨 `LEDGER.md` §Logic, the whole list, and every one of them is a film:
    stripping tags as bare words gave `Kingsglaive Fantasy XV`, `Bakemono no`,
    `Mad Fury Road`, `Uma`. A learned vocabulary does not escape it -- `ja`,
    `anime`, `studio` and `final` are decoration by every measure and are also
    real title words. `LEDGER.md` also records that a four-character floor was
    tried and destroyed `Anime Gataris`.

    ⭐ ASSERTED AGAINST THE UNTOUCHED TITLE'S OWN KEY, not against a substring.
    `normalize` folds romaji -- `ja` becomes `zya` and `fu` becomes `hu` -- so
    a substring test would be asserting the folding rather than the stripping,
    and would go green if a word were eaten and the fold changed.

    ⭐ This is the check that stops anyone reaching for a bare-word stripper to
    make the coverage number go up."""
    assert M.movie_stem(name) == normalize(intact_title).key, M.read_name(name)


def test_a_name_that_reduces_to_NOTHING_never_pairs(tmp_path):
    """⚠ An empty key equals every other empty key, so ONE bad reduction pairs
    a subtitle with every film in the library -- `08-probes.md` §C measured
    that at **4,133 files**. Three guards stand behind it and this drives the
    outermost one."""
    root = build(tmp_path, ["Lib/A/Real Film (1999).mkv",
                            "Lib/B/[].srt",
                            "Lib/B/....srt"])
    v, s = walked(root)
    result = M.pair_movies(v, s)
    assert result.pairs == [], result.pairs
    assert len(result.refusals) + len(result.skipped) == len(s)


def test_an_empty_key_is_refused_by_name_not_by_accident():
    """⭐ The refusal says what it FOUND. `doctrine/robustness`: a failure
    message written for somebody who cannot see the code."""
    name = M.read_name(u"[].srt")
    assert name.key == u"" or not name.is_film
    if not name.is_film:
        assert "empty key" in name.refusal


# ==========================================================================
# 🚨 the CUTS trap -- the corruption this feature must not produce
# ==========================================================================

def test_the_cut_tag_is_INVISIBLE_to_the_title_layer():
    """🚨 THE MEASUREMENT THAT RESHAPED THIS MODULE, and it is worse than the
    spec predicts.

    `06-edge-cases.md` §3.5 says the two slugs *"overlap at 0.52, above the 0.4
    threshold, so `same_series()` MATCHES them."* Measured 2026-09-08:
    `episode._title_from` deletes every bracketed run, so both names reduce to
    the title `Blade Runner` and the overlap is **1.000**. The edition is not
    outweighed -- it is gone before any comparison happens.

    ⭐ Which is why the edition is carried as a SECOND VALUE, exactly as
    `normalize` carries a punctuation signature beside its key."""
    a = E.parse_ours(u"Blade Runner (1982) [Final Cut].mkv")
    b = E.parse_ours(u"Blade Runner (1982) [Theatrical].srt")
    assert overlap(a.title, b.title) == 1.0, (
        "the parser stopped deleting the bracketed edition -- re-read §3.5 "
        "before relaxing anything here")
    assert M.edition_of(u"Blade Runner (1982) [Final Cut].mkv") == u"final cut"
    assert M.edition_of(u"Blade Runner (1982) [Theatrical].srt") == \
        u"theatrical"


def test_a_theatrical_subtitle_is_REFUSED_on_a_final_cut(tmp_path):
    """🚨 *A theatrical subtitle on a Final Cut is exactly the corruption this
    must prevent* -- `00-INDEX` Rule 2, and §3.5 names it as trap 1.

    ⚠ The folder holds **one** video, so the sole-video rung would otherwise
    claim this subtitle outright. The veto has to survive the cheapest rung,
    not only the strictest one."""
    root = build(tmp_path, [
        "Films/Blade Runner/Blade Runner (1982) [Final Cut].mkv",
        "Films/Blade Runner/Blade Runner (1982) [Theatrical].en.srt"])
    v, s = walked(root)
    result = M.pair_movies(v, s)
    assert result.pairs == [], result.pairs
    ref = refusal_for(result, "Blade Runner (1982) [Theatrical].en.srt")
    assert ref is not None
    assert "final cut" in ref.reason and "theatrical" in ref.reason, ref.reason


def test_each_cut_takes_its_OWN_subtitle_when_both_are_present(tmp_path):
    """⭐ The positive control that lives beside the refusal. A guard that only
    ever refuses passes against a function that refuses everything --
    `doctrine/robustness`: **test both directions.**"""
    root = build(tmp_path, [
        "BR/Blade Runner (1982) [Final Cut].mkv",
        "BR/Blade Runner (1982) [Theatrical].mkv",
        "BR/Blade Runner (1982) [Final Cut].en.srt",
        "BR/Blade Runner (1982) [Theatrical].en.srt"])
    v, s = walked(root)
    result = M.pair_movies(v, s)
    assert len(result.pairs) == 2, result
    for pair in result.pairs:
        assert M.edition_of(os.path.basename(pair.video)) == \
            M.edition_of(os.path.basename(pair.subtitle))


def test_an_edition_stated_on_ONE_side_is_not_a_disagreement(tmp_path):
    """⚠ `LEDGER.md` §Logic: *A SEASON STATED ON ONE SIDE ONLY IS NOT A
    DISAGREEMENT*, and counting it as one made a 92.3% stack read as 46.0%
    because **46.3% of real pairs are exactly that shape.** A subtitle named
    `Blade Runner (1982).srt` beside `…[Final Cut].mkv` is the same shape and
    gets the same answer: the name is silent, not contradictory."""
    root = build(tmp_path, ["BR/Blade Runner (1982) [Final Cut].mkv",
                            "BR/Blade Runner (1982).en.srt"])
    v, s = walked(root)
    result = M.pair_movies(v, s)
    assert len(result.pairs) == 1, result
    assert result.pairs[0].rung == M.SOLE_VIDEO


@pytest.mark.parametrize("name,expected", [
    (u"Blade Runner (1982) [Final Cut].mkv", u"final cut"),
    (u"Blade.Runner.1982.Final.Cut.1080p.BluRay.mkv", u"final cut"),
    (u"Aliens (1986) Special Edition.mkv", u"special edition"),
    (u"Apocalypse Now (1979) [Redux].mkv", u"redux"),
    (u"Alien (1979).Director's.Cut.mkv", u"director's cut"),
    # ⛔ THE OMISSIONS ARE THE DESIGN. `final` alone is not an edition -- these
    # are real titles and real seasons, and `LEDGER.md` records a word being
    # eaten from the first one.
    (u"Kingsglaive - Final Fantasy XV (2016).mkv", u""),
    (u"Gintama Final (2021).mkv", u""),
    (u"The Extended Family (1980).mkv", u""),
    (u"Uncut Gems (2019).mkv", u""),
    # ⭐ ADDED BECAUSE A MUTANT MUTATED NOTHING. *Bare `final` admitted to the
    # vocabulary* was written to break the context rule and could not: in
    # `Kingsglaive - Final Fantasy XV` the word is followed by a SPACE, so the
    # delimiter rule refuses it whatever the vocabulary says. The dotted form
    # is where membership alone would bite, and it is an ordinary Western
    # release shape.
    (u"The.Extended.Family.1980.1080p.BluRay.mkv", u""),
])
def test_an_edition_is_only_recognised_in_a_TAG_context(name, expected):
    """⭐ `decoration.py`'s rule, applied to a second vocabulary: **the
    vocabulary decides WHICH tokens, the context decides WHETHER.** A plain
    space is not a left delimiter, for the same reason it is not one there --
    a space-delimited word is just a word.

    ⚠ `Uncut Gems` is the single-word case that would break a membership test:
    `uncut` is a real edition tag and is also the first word of a real film."""
    assert M.edition_of(name) == expected


# ==========================================================================
# the year -- two films can share a title
# ==========================================================================

def test_a_release_year_is_never_an_episode_number():
    """🚨 `LEDGER.md` §Logic, found by review over 318 green checks:
    `Inception (2010)` returned **ep=2010**, and two different films both
    keying to `(None, 2010)` bucket a whole library under one fabricated
    episode. This is the launch use case, so it is pinned here as well as in
    the parser's own suite."""
    for name in (u"Inception (2010).en.srt",
                 u"Blade Runner (1982) [Final Cut].mkv",
                 u"\u541b\u3092\u611b\u3057\u305f\u3072\u3068\u308a"
                 u"\u306e\u50d5\u3078.2022.srt"):
        parsed = E.parse_ours(name)
        assert parsed.episode is None, (name, parsed)
        assert M.read_name(name).is_film, name


@pytest.mark.parametrize("name,year", [
    (u"Inception (2010).mkv", 2010),
    (u"Inception.2010.1080p.BluRay.x264-GROUP.mkv", 2010),
    # ⭐ THE LAST YEAR, NOT THE FIRST, and this is the film that proves it:
    # the title itself contains a year-shaped number.
    (u"Blade Runner 2049 (2017).mkv", 2017),
    (u"Blade.Runner.2049.2017.1080p.BluRay.mkv", 2017),
    (u"Spirited Away.mkv", None),
])
def test_the_release_year_is_the_LAST_year_shaped_number(name, year):
    assert M.year_of(name) == year


def test_the_year_is_read_AFTER_the_tags_are_stripped(tmp_path):
    """🚨 THE THIRD ORDERING FAULT IN THIS MODULE, AND THE SAME SHAPE AS THE
    OTHER TWO. `episode.P_YEAR_TOKEN` requires a delimiter or the end of the
    string after the year -- and `[` is neither. Read before the tag was
    stripped, `Absolute Strangers 1991[eng].srt` reported **no year at all**,
    so it could not reach rung 1 against `Absolute Strangers 1991.mkv`.

    ⚠ Stripping `eng` is not enough either: it leaves `1991[]` behind, and the
    empty bracket pair blocks the anchor exactly as the bracket did. Residue
    is not cosmetic once something anchored reads the string."""
    assert M.year_of(u"Absolute Strangers 1991[eng].srt") == 1991
    root = build(tmp_path, ["F/Absolute Strangers 1991.mkv",
                            "F/Absolute Strangers 1991[eng].srt"])
    v, s = walked(root)
    result = M.pair_movies(v, s)
    assert len(result.pairs) == 1, result.refusals
    assert result.pairs[0].rung == M.STEM


@pytest.mark.parametrize("name,key", [
    (u"2012 (2009).mkv", u"2012"),
    (u"1917 (2019).mkv", u"1917"),
    (u"1408 (2007).mkv", u"1408"),
])
def test_a_title_that_IS_a_year_keeps_its_key(name, key):
    """⚠ Removing the year must never empty the key. `2012`, `1917` and `1408`
    are real films whose entire title is a year, and an empty key pairs with
    every video in the library."""
    read = M.read_name(name)
    assert read.key == key, read
    assert read.year is not None and read.year != int(key)


def test_two_stated_years_that_DIFFER_are_two_films(tmp_path):
    """⛔ `The Thing (1982)` and `The Thing (2011)` share a title and are
    unrelated works. A remake is the movie library's version of the sequel
    shape `series.one_contains_the_other` exists for, and it is settled by an
    exact test rather than by a threshold.

    ⚠ Each film sits alone in its own folder, so the sole-video rung is
    live -- and it must not rescue the wrong pairing."""
    root = build(tmp_path, ["Lib/The Thing (1982)/The Thing (1982).mkv",
                            "Lib/The Thing (2011)/The Thing (2011).mkv",
                            "Lib/The Thing (1982)/The Thing (2011).en.srt"])
    v, s = walked(root)
    result = M.pair_movies(v, s)
    assert len(result.pairs) == 1, [tuple(p) for p in result.pairs]
    pair = result.pairs[0]
    assert "The Thing (2011).mkv" in pair.video, pair
    assert pair.rung == M.STEM


def test_a_remake_does_not_reach_rung_2_when_rung_1_finds_NOTHING(tmp_path):
    """🚨 ADDED BECAUSE A MUTANT SURVIVED, and the reason is the shape of the
    check above rather than of the code.

    *Rung 2 accepts two different stated years* survived
    `test_two_stated_years_that_DIFFER_are_two_films`, because in that fixture
    the correct 2011 video is present -- rung 1 answers first and the mutated
    rung 2 never runs. **A check cannot feel a mutation on a branch it never
    reaches.**

    ⭐ So this is the same claim with the exact rung removed from the board:
    one 1982 video, one 2011 subtitle, and nothing else in the walk."""
    root = build(tmp_path, ["Lib/A/The Thing (1982).mkv",
                            "Lib/B/The Thing (2011).en.srt"])
    v, s = walked(root)
    result = M.pair_movies(v, s)
    assert result.pairs == [], [tuple(p) for p in result.pairs]
    ref = refusal_for(result, "The Thing (2011).en.srt")
    assert ref is not None and ref.candidates == []


def test_a_year_stated_on_only_ONE_side_reaches_rung_2(tmp_path):
    """⭐ §3.5's rung 2, in the shape that is actually distinct from rung 1:
    the title agrees and exactly one side names a year. A library where the
    video is `Inception.mkv` and the downloaded subtitle is
    `Inception (2010).en.srt` is the common case."""
    root = build(tmp_path, ["Lib/Flat/Inception.mkv",
                            "Lib/Flat/Casablanca.mkv",
                            "Lib/Subs/Inception (2010).en.srt"])
    v, s = walked(root)
    result = M.pair_movies(v, s)
    assert len(result.pairs) == 1, result
    assert result.pairs[0].rung == M.TITLE_YEAR
    assert "Inception.mkv" in result.pairs[0].video
    assert "2010" in result.pairs[0].reason


# ==========================================================================
# folder shapes -- one video, several, none, and a collision
# ==========================================================================

LIBRARY = [
    # ⭐ one video and its subtitle, the Plex/Jellyfin/Sonarr shape
    "Lib/Inception (2010)/Inception (2010).mkv",
    "Lib/Inception (2010)/Inception (2010).en.srt",
    # a folder with SEVERAL videos -- no sole-video claim may be made here
    "Lib/Double/Arrival (2016).mkv",
    "Lib/Double/Sicario (2015).mkv",
    "Lib/Double/an unhelpfully named sub.srt",
    # layout 2: a subtitle folder holding NO video, beside its film.
    # ⚠ The subtitle is named so that NO rung above sole-video can reach it --
    # `solaris.eng.srt` was tried first and paired at rung 2, which made this
    # check green while never exercising the rung it is named after.
    "Lib/Solaris (1972)/Solaris (1972).mkv",
    "Lib/Solaris (1972)/Subs/eng sub by a stranger.srt",
    # the cuts collision
    "Lib/Blade Runner/Blade Runner (1982) [Final Cut].mkv",
    "Lib/Blade Runner/Blade Runner (1982) [Theatrical].en.srt",
    # ⭐ layout 8: an episode in the same tree. It must take the TV path
    "Lib/Show/Show S02E03.mkv",
    "Lib/Show/Show S02E03.en.srt",
]


@pytest.fixture
def library(tmp_path):
    root = build(tmp_path, LIBRARY)
    v, s = walked(root)
    return M.pair_movies(v, s)


def test_a_folder_with_ONE_video_claims_a_subtitle_that_matches_nothing(
        library):
    """⭐ §3.5: *a folder holding exactly one video means any subtitle in it
    belongs to that video. Cheapest rung of all.*

    ⚠ AND ITS PARENT, which is layout 2 and is required: §4 says *if the sub
    folder holds no video, check the parent*."""
    pairs = by_subtitle(library)
    subtitle = "eng sub by a stranger.srt"
    assert subtitle in pairs, library.refusals
    assert pairs[subtitle].rung == M.SOLE_VIDEO
    assert "parent" in pairs[subtitle].reason
    assert "Solaris (1972).mkv" in pairs[subtitle].video


def test_a_folder_with_SEVERAL_videos_makes_no_sole_video_claim(library):
    """⚠ Two videos is not *"probably the first one"*. It is an ambiguity, and
    §3.5 rung 3 gives an ambiguity to timing."""
    assert "an unhelpfully named sub.srt" not in by_subtitle(library)
    ref = refusal_for(library, "an unhelpfully named sub.srt")
    assert ref is not None and "no video in the walk shares its key" \
        in ref.reason


def test_an_episode_in_the_same_tree_takes_the_TV_path(library):
    """⭐ `06-edge-cases.md` line ~169: *movies and shows need no separate
    mode -- the discriminator falls out of parsing.* Layout 8 is then not a
    special case, it is the two paths over one directory."""
    names = set(os.path.basename(p) for p in library.skipped)
    assert "Show S02E03.mkv" in names and "Show S02E03.en.srt" in names
    for path, why in library.skipped.items():
        if "Show S02E03" in path:
            assert "episode 3" in why and "TV path" in why


def test_the_result_carries_its_own_denominator(library):
    """⭐ `doctrine/verification`: *print the denominator, so a vacuous pass is
    visible at a glance.* `0 broken of 0` is what this prevents."""
    counts = library.counts
    assert counts["subtitles"] == len([r for r in LIBRARY
                                       if r.endswith(".srt")])
    assert counts["filmSubtitles"] + len(
        [p for p in library.skipped if p.endswith(".srt")]) == \
        counts["subtitles"]
    assert sum(counts[rung] for rung in M.RUNGS) == len(library.pairs)


def test_several_LANGUAGES_for_one_video_all_pair(tmp_path):
    """`06-edge-cases.md` §4: *several languages, same episode -- all pair.*
    The constraint is one video per subtitle, never one subtitle per video."""
    root = build(tmp_path, ["F/Arrival (2016).mkv",
                            "F/Arrival (2016).en.srt",
                            "F/Arrival (2016).ja.srt",
                            "F/Arrival (2016).fr.srt"])
    v, s = walked(root)
    result = M.pair_movies(v, s)
    assert len(result.pairs) == 3, result
    assert len(set(p.video for p in result.pairs)) == 1


# ==========================================================================
# ambiguity -- refused, with the candidates named
# ==========================================================================

def test_two_equally_good_candidates_are_REFUSED_and_BOTH_are_named(tmp_path):
    """⛔ `00-INDEX` Rule 2: *a confidently wrong answer is worse than no
    answer.* Two copies of one film in two unrelated folders, and a subtitle in
    a third: nothing separates them on name, folder or runtime.

    ⚠ `LEDGER.md`: *never take argmax of a flat plateau.* Picking the first is
    picking by sort order."""
    root = build(tmp_path, ["A/Inception (2010).mkv",
                            "B/Inception (2010).mkv",
                            "C/Inception (2010).en.srt"])
    v, s = walked(root)
    result = M.pair_movies(v, s)
    assert result.pairs == [], result.pairs
    ref = refusal_for(result, "Inception (2010).en.srt")
    assert ref is not None and ref.rung == M.TIMING
    assert len(ref.candidates) == 2
    assert "timing arbitration" in ref.reason


def test_PROXIMITY_separates_two_copies_of_one_film(tmp_path):
    """⭐ The positive control beside the refusal above, and it is the reason
    proximity is a SCORE rather than a gate. Same two candidates -- but this
    time the subtitle sits beside one of them."""
    root = build(tmp_path, ["A/Inception (2010).mkv",
                            "B/Inception (2010).mkv",
                            "B/Inception (2010).en.srt"])
    v, s = walked(root)
    result = M.pair_movies(v, s)
    assert len(result.pairs) == 1, result
    assert os.sep + "B" + os.sep in result.pairs[0].video


# ==========================================================================
# names that are NOT films
# ==========================================================================

@pytest.mark.parametrize("name", [
    u"Show - 03.srt",
    u"Show S02E03.mkv",
    u"[Group] Show - 05 [1080p].mkv",
    u"\u4f5c\u54c1\u540d \u7b2c06\u8a71.srt",
])
def test_a_name_with_an_episode_number_is_NOT_on_the_movie_path(name):
    read = M.read_name(name)
    assert not read.is_film
    assert "TV path" in read.refusal, read.refusal


@pytest.mark.parametrize("name,key", [
    (u"Toy Story 2 (1999).mkv", u"toystory2"),
    (u"Iron Man 3 (2013).mkv", u"ironman3"),
    (u"Shrek 2 (2004).mkv", u"shrek2"),
    (u"Alien 3 (1992).mkv", u"alien3"),
    (u"Kill Bill Vol 2 (2004).mkv", u"killbillvol2"),
    (u"Bad.Ass.2.Bad.Asses.2014.1080p.BluRay.x264-ROVERS.mkv", None),
])
def test_a_numbered_SEQUEL_is_a_film_not_an_episode(name, key):
    """🚨 MEASURED: **45 of the 904 real Western release names (5.0%)** carry
    both a release year and a number `parse_ours` calls an episode.

    Left as episodes they are not merely absent from the movie path -- they are
    actively wrong: `Toy Story 2`, `Iron Man 3` and `Shrek 2` key to
    `(None, 2)` and `(None, 3)`, so an entire film library buckets under a
    fabricated episode number. That is the identical shape `LEDGER.md` records
    for the release year itself, one number to the left.

    ⭐ The tell is the MARKER, never the number: a release year plus no
    explicit episode marker anywhere in the name."""
    assert E.parse_ours(name).episode is not None, (
        "the parser stopped reading the sequel ordinal as an episode -- this "
        "check is now describing history; read `movies._EXPLICIT_MARKERS`")
    read = M.read_name(name)
    assert read.is_film, read.refusal
    assert read.year is not None
    if key is not None:
        assert read.key == key, read


@pytest.mark.parametrize("name", [
    u"Doctor Who (2005) S01E01.mkv",
    u"Doctor Who (2005) - s01e01 - Rose.mkv",
    u"The Office (US) (2005) 2x05.mkv",
    u"Show (2019) EP03.mkv",
    u"\u756a\u7d44 (2019) \u7b2c03\u8a71.srt",
    # \u2b50 ADDED BECAUSE A MUTANT MUTATED NOTHING. *The explicit-marker guard is
    # removed* could not change the answer on any row above, because the
    # POSITION guard also blocks every one of them -- the episode digits sit
    # after the year. This is the row where only the marker guard stands: the
    # marker's digits are before the year, so position says *film* and the
    # marker has to be the thing that says *television*.
    u"Doctor Who - S01E01 - Rose (2005).mkv",
])
def test_a_bracketed_year_does_NOT_move_TELEVISION_onto_the_movie_path(name):
    """⚠ THE OTHER BRANCH, AND IT IS THE ONE THAT MAKES THE RULE SAFE.
    `Doctor Who (2005) S01E01` is the standard Plex naming for television and
    it carries a bracketed year, so *a year is present* is emphatically not the
    tell. Every explicit marker keeps a name on the TV path whatever year it
    states."""
    assert M.has_explicit_episode_marker(name), name
    read = M.read_name(name)
    assert not read.is_film, read
    assert "TV path" in read.refusal


def test_a_name_that_is_ENTIRELY_release_tags_is_refused():
    """⛔ A raw-stem fallback was written here and REMOVED on measurement.
    `1080p.AMZN.WEB-DL.DDP5.1.H.264-EVO` has no title in it, so a key made from
    the raw stem is a key made of decoration -- it pairs that name with every
    other file carrying the same tags, which is the empty-slug defect
    (`08-probes.md` §C, 4,133 files) wearing different clothes."""
    read = M.read_name(u"1080p.AMZN.WEB-DL.DDP5.1.H.264-EVO.mkv")
    assert not read.is_film
    assert "no title survives" in read.refusal
    result = M.pair_movies([u"L:/A/1080p.AMZN.WEB-DL.DDP5.1.H.264-EVO.mkv"],
                           [u"L:/A/1080p.AMZN.WEB-DL.DDP5.1.H.264-NTG.srt"])
    assert result.pairs == []
    assert len(result.skipped) == 2


def test_a_BATCH_name_is_never_flattened_into_a_film():
    """🚨 A batch has `episode is None` and is emphatically not a film. Letting
    it onto the movie path would fit a whole-season subtitle to one video --
    the batch refusal exists precisely to stop a confident wrong answer, and
    `episode.union` already refuses to let anitopy vote it away."""
    read = M.read_name(u"[Group] Show 01~12 [BD 1080p].mkv")
    assert E.parse_ours(u"[Group] Show 01~12 [BD 1080p].mkv").kind == E.BATCH
    assert not read.is_film
    assert "one file" in read.refusal


def test_a_CONJUNCTION_name_is_never_flattened_into_a_film():
    name = u"Show S01E01 & Other Show S02E04.mkv"
    assert E.parse_ours(name).kind == E.CONJUNCTION
    assert not M.read_name(name).is_film


@pytest.mark.parametrize("name", [
    u"Show NCOP.mkv",
    u"Show - NCED 2.mkv",
    u"[Group] Show - Creditless OP.mkv",
    u"Show.Clean.Opening.mkv",
])
def test_a_creditless_opening_is_REFUSED_because_it_has_no_dialogue(name):
    """🚨 `06-edge-cases.md` §4: NCOP/NCED carry **no dialogue at all**, so any
    subtitle fitted to one is a phantom -- the documented 108 s orphan-cue
    failure, where 14 orphaned OP-karaoke cues scored 57% by chance and cleared
    every guard that looks at match rate."""
    read = M.read_name(name)
    assert not read.is_film, read
    assert "no dialogue" in read.refusal


def test_a_real_title_containing_OP_or_ED_is_not_creditless():
    """⚠ The other branch. `OP` and `ED` alone are far too short to be safe,
    which is why the detector requires `ncop`/`nced`/`creditless`/`clean op`
    and requires them delimiter-bounded."""
    for name in (u"Open Water (2003).mkv", u"Edge of Tomorrow (2014).mkv",
                 u"The Operative (2019).mkv"):
        assert M.read_name(name).is_film, name


# ==========================================================================
# ⭐ the DURATION seam -- A9's territory, injected, never imported
# ==========================================================================

def test_duration_ABSENT_changes_nothing(tmp_path):
    """⭐ The control that makes every duration check below mean something.
    `discover.duration_verdict`'s own rule: *unknown is not evidence.* An
    absent probe may neither create a pair nor break one."""
    root = build(tmp_path, ["F/Arrival (2016).mkv", "F/Arrival (2016).en.srt"])
    v, s = walked(root)
    without = M.pair_movies(v, s)
    silent = M.pair_movies(v, s, duration_of=lambda path: None)
    assert [tuple(p) for p in without.pairs] == \
        [tuple(p) for p in silent.pairs]
    assert len(without.pairs) == 1


def test_duration_REJECTS_an_impossible_runtime(tmp_path):
    """⭐ Sonic's observation, `06-edge-cases.md` §3.45: *you won't have a movie
    that is 1 hour long and subs that are 1 hour 30 minutes.* The cheapest
    possible filter, and it must survive the cheapest rung."""
    root = build(tmp_path, ["F/Only Video Here.mkv", "F/Subs/whatever.srt"])
    v, s = walked(root)
    runtime = {}
    for path in v:
        runtime[path] = 3600.0
    for path in s:
        runtime[path] = 5400.0
    assert len(M.pair_movies(v, s).pairs) == 1, "the control did not pair"
    result = M.pair_movies(v, s, duration_of=runtime.get)
    assert result.pairs == []
    ref = refusal_for(result, "whatever.srt")
    assert ref is not None and "runtime" in ref.reason
    assert "5400" in ref.reason and "3600" in ref.reason, (
        "the message must say what it FOUND, not what it wanted")


def test_duration_RANKS_when_the_names_tie(tmp_path):
    """⭐ §3.45's third use: *closest runtime wins among otherwise-equal
    candidates.* The same fixture that is REFUSED without runtimes resolves
    with them -- which is what makes this an accelerator rather than a gate."""
    root = build(tmp_path, ["A/Inception (2010).mkv",
                            "B/Inception (2010).mkv",
                            "C/Inception (2010).en.srt"])
    v, s = walked(root)
    assert M.pair_movies(v, s).pairs == [], "the control resolved on its own"
    runtime = {s[0]: 8800.0}
    for path in v:
        runtime[path] = 8880.0 if os.sep + "B" + os.sep in path else 3000.0
    result = M.pair_movies(v, s, duration_of=runtime.get)
    assert len(result.pairs) == 1, result
    assert os.sep + "B" + os.sep in result.pairs[0].video


@pytest.mark.parametrize("word,rejects", [
    (u"reject", True),            # `discover.duration_verdict`
    (u"impossible", True),        # RUNBOOK A9's `duration.duration_verdict`
    (u"IMPOSSIBLE", True),        # …and its constant, however it is cased
    (u"ok", False),
    (u"plausible", False),
    (u"unknown", False),          # ⛔ unknown is not evidence
    (u"something nobody has written yet", False),
    (None, False),
])
def test_the_verdict_seam_accepts_BOTH_vocabularies(tmp_path, word, rejects):
    """⭐ THE RULE IS INJECTED SEPARATELY FROM THE NUMBERS, because A9 owns the
    thresholds and this module must not hold a second copy of them --
    `doctrine/architecture` §4: a derived value needs ONE writer.

    `discover.duration_verdict` says `"reject"`; A9's `duration.py` says
    `IMPOSSIBLE`. Both are accepted, so wiring A9 in is one argument and no
    edit here.

    ⚠ AND EVERY OTHER WORD IS NOT A REJECTION, including one this module has
    never heard of. A verdict vocabulary that grows must not silently start
    refusing pairs -- fail OPEN, written down, because duration is an
    accelerator and never a dependency (Rule 1)."""
    root = build(tmp_path, ["F/Arrival (2016).mkv", "F/Arrival (2016).en.srt"])
    v, s = walked(root)
    result = M.pair_movies(v, s, duration_of=lambda p: 3600.0,
                           duration_verdict=lambda a, b: word)
    assert (result.pairs == []) is rejects, (word, result.pairs,
                                             result.refusals)


def test_a_verdict_function_that_RAISES_does_not_break_the_pair(tmp_path):
    """⛔ Fail OPEN. A rule that cannot be evaluated costs the run a filter,
    never a pair."""
    root = build(tmp_path, ["F/Arrival (2016).mkv", "F/Arrival (2016).en.srt"])
    v, s = walked(root)

    def explode(a, b):
        raise ValueError("A9 is mid-edit")

    result = M.pair_movies(v, s, duration_of=lambda p: 3600.0,
                           duration_verdict=explode)
    assert len(result.pairs) == 1, result.refusals


def test_a_duration_probe_that_RAISES_never_reaches_the_caller(tmp_path):
    """⭐ Rule 1: the duration probe is an ACCELERATOR, never a dependency. A
    container that cannot be read must cost the run a ranking signal, not the
    pair -- and the choice is written down at the site, because
    `doctrine/robustness` says an undocumented fail-open is indistinguishable
    from a bug."""
    root = build(tmp_path, ["F/Arrival (2016).mkv", "F/Arrival (2016).en.srt"])
    v, s = walked(root)

    def explode(path):
        raise IOError("this container is unreadable")

    result = M.pair_movies(v, s, duration_of=explode)
    assert len(result.pairs) == 1, result


def test_the_duration_seam_is_asked_for_the_SUBTITLE_as_well(tmp_path):
    """⚠ `doctrine/verification`: *a green suite proves the app ASKED
    CORRECTLY* when the effect leaves the process. Haptics shipped with three
    passing checks on a machine with no vibration motor. Here the claim is
    narrow and stated: the module asks for the runtime of the video AND the
    last cue time of the subtitle. What those numbers mean is A9's to answer."""
    root = build(tmp_path, ["F/Arrival (2016).mkv", "F/Arrival (2016).en.srt"])
    v, s = walked(root)
    asked = []

    def record(path):
        asked.append(path)
        return None

    M.pair_movies(v, s, duration_of=record)
    assert any(p.endswith(".srt") for p in asked), asked


# ==========================================================================
# structural -- what the module may not do
# ==========================================================================

def test_NOTHING_in_the_library_is_opened(tmp_path, monkeypatch):
    """⛔ *No media I/O.* Filenames and directory structure only, which is what
    makes a 10,000-file library cost milliseconds.

    ⚠ The bundled decoration vocabulary IS opened, once, and that is named here
    rather than warmed away -- a check that pre-warms the thing it is about to
    forbid is asserting state it created."""
    root = build(tmp_path, ["F/Arrival (2016).mkv", "F/Arrival (2016).en.srt",
                            "F/Sicario (2015).mkv"])
    v, s = walked(root)
    opened = []
    real_open, real_io_open = open, io.open

    def spy(path, *args, **kwargs):
        opened.append(str(path))
        return real_open(path, *args, **kwargs)

    def spy_io(path, *args, **kwargs):
        opened.append(str(path))
        return real_io_open(path, *args, **kwargs)

    monkeypatch.setattr("builtins.open", spy)
    monkeypatch.setattr(io, "open", spy_io)
    M.pair_movies(v, s)
    monkeypatch.undo()

    media = [p for p in opened if p in set(v) | set(s)]
    assert media == [], "the movie path opened media: %r" % media


def test_the_index_is_NOT_a_nested_loop():
    """🚨 `06-edge-cases.md` §4: *500 videos x 1500 subs -- index by key first,
    NEVER a nested loop.* The naive form is 750,000 comparisons.

    ⭐ Asserted as a MECHANISM, not as a clock. `LEDGER.md` records two
    separate diagnoses lost to timing a thing instead of instrumenting it, and
    a wall-clock ceiling on a shared machine is a check that cries wolf. What
    is counted is how many candidate comparisons the pass actually makes."""
    # ⚠ NO TRAILING NUMBER IN A TITLE HERE, and the first version of this
    # fixture had one. `Film 0001 (1900)` parses to episode 1, so all 500
    # "films" were skipped as television and the check asserted 0 == 1500 --
    # a fixture that could not exhibit the thing it was built to measure.
    words = ["alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf",
             "hotel", "india", "juliet", "kilo", "lima", "mike", "november",
             "oscar", "papa", "quebec", "romeo", "sierra", "tango",
             "uniform", "victor", "whiskey", "xray", "yankee"]
    titles = [u"The %s %s (19%02d)" % (words[i // 25].title(),
                                       words[i % 25].title(), i % 100)
              for i in range(500)]
    videos = [u"L:/V/%s/%s.mkv" % (t, t) for t in titles]
    subs = [u"L:/S/%s.en.srt" % titles[i % 500] for i in range(1500)]

    calls = [0]
    real_veto = M._veto

    def counting(*args, **kwargs):
        calls[0] += 1
        return real_veto(*args, **kwargs)

    M._veto = counting
    try:
        result = M.pair_movies(videos, subs)
    finally:
        M._veto = real_veto

    assert len(result.pairs) == 1500, result.counts
    assert calls[0] <= len(subs) * 4, (
        "%d candidate comparisons for %d subtitles against %d videos -- a "
        "nested loop would be %d"
        % (calls[0], len(subs), len(videos), len(subs) * len(videos)))


def test_the_parsed_of_seam_takes_what_DISCOVER_actually_produces(tmp_path):
    """🚨 THIS CHECK CAUGHT A REAL DEFECT, and it caught it because it drives
    the seam with the caller's OWN objects rather than with a convenient one.

    `discover.parse_all` stores an `episode.Union`, not a `Parsed` -- and
    `Union` has `episode` and `kind` but **no `reason`**. The batch branch read
    `parsed.reason` directly and raised `AttributeError` on the integration
    path only, so every hermetic check in this file stayed green.

    ⭐ `doctrine/verification`: *test the WRAPPER and the thing together.* The
    seam is what `discover.py` will call, so the seam is what has to be driven.
    """
    root = build(tmp_path, ["Lib/Inception (2010)/Inception (2010).mkv",
                            "Lib/Inception (2010)/Inception (2010).en.srt",
                            "Lib/Batch/[Group] Show 01~12 [BD 1080p].mkv",
                            "Lib/Batch/[Group] Show 01~12 [BD 1080p].srt",
                            "Lib/Show/Show S02E03.mkv"])
    items = D.parse_all(D.walk(root))
    by_path = dict((i.path, i.parsed) for i in items)
    assert any(isinstance(p, E.Union) for p in by_path.values()), (
        "discover stopped storing a Union -- re-read this check before "
        "changing it")

    videos = [i.path for i in items if i.kind == "video"]
    subtitles = [i.path for i in items if i.kind == "subtitle"]
    result = M.pair_movies(videos, subtitles, parsed_of=by_path.get)

    assert len(result.pairs) == 1, result
    assert "Inception (2010).mkv" in result.pairs[0].video
    batch = [why for path, why in result.skipped.items() if "01~12" in path]
    assert len(batch) == 2, result.skipped
    for why in batch:
        assert "one file" in why, why


def test_the_result_is_not_iterable_so_a_refusal_cannot_be_missed(tmp_path):
    """⛔ `doctrine/robustness` opens with it: *refuse loudly, never drop
    silently.* A bare list of pairs has nowhere to put a refusal, and a caller
    who never asks for the refusals is the silent-drop case. Naming the half
    you want is one word and it makes the other half unmissable."""
    root = build(tmp_path, ["F/Arrival (2016).mkv", "F/Arrival (2016).en.srt"])
    v, s = walked(root)
    result = M.pair_movies(v, s)
    with pytest.raises(TypeError):
        list(result)
    assert isinstance(result.pairs, list) and isinstance(result.refusals, list)


@pytest.mark.parametrize("videos,subtitles", [
    ([], []),
    ([u"L:/A/Arrival (2016).mkv"], []),
    ([], [u"L:/A/Arrival (2016).en.srt"]),
])
def test_an_EMPTY_side_is_answered_not_crashed(videos, subtitles):
    """A user pointing the tool at an empty folder, at a folder of videos with
    no subtitles, or at a subtitle folder whose videos are elsewhere and were
    not in the walk. All three are ordinary input, and `06-edge-cases.md` §4 is
    explicit that expected input is never an error."""
    result = M.pair_movies(videos, subtitles)
    assert result.pairs == []
    assert result.counts["videos"] == len(videos)
    assert result.counts["subtitles"] == len(subtitles)
    assert len(result.refusals) == len(subtitles)


def test_a_pair_unpacks_as_video_subtitle_rung_reason(tmp_path):
    root = build(tmp_path, ["F/Arrival (2016).mkv", "F/Arrival (2016).en.srt"])
    v, s = walked(root)
    video, subtitle, rung, reason = M.pair_movies(v, s).pairs[0]
    assert video.endswith(".mkv") and subtitle.endswith(".srt")
    assert rung in M.RUNGS and reason


# ==========================================================================
# the corpus pass -- skips loudly rather than passing vacuously
# ==========================================================================

SEED = 20260908


@pytest.fixture(scope="module")
def western_names():
    """904 real Western release names.

    `tsubasa.config.json` declares `western-naming` a FIXTURE: *"a names-only
    text file (904 release names). No files, no shows, nothing to seal."* So
    there is no seal to break here, and that is quoted rather than assumed."""
    cfg = load_config(ROOT)
    root = corpus_root(cfg, ROOT)
    path = root / "western-naming" / "release_names.txt"
    if not path.is_file():
        pytest.skip("SKIPPED, NOT PASSED: no %s" % path)
    with io.open(str(path), encoding="utf-8", errors="replace") as fh:
        names = [line.strip() for line in fh if line.strip()]
    if len(names) < 500:
        pytest.skip("SKIPPED, NOT PASSED: only %d names" % len(names))
    return names


def test_the_stem_rung_covers_the_EASY_half_on_real_names(western_names):
    """⭐ §3.5 rung 1: *the overwhelming majority. Movie libraries usually
    already name the sub after the video.*

    ⚠ THE POPULATION IS SAID OUT LOUD, and half of it is CONSTRUCTED. The film
    NAMES are real and carry real Western pollution; what is constructed is the
    language tag a library appends to make the subtitle's name. That is exactly
    the variable rung 1 is about. `LEDGER.md` §Harness has two entries about a
    number that was right about its sample and wrong about its scope.

    The floor is a measured floor, not a target -- probe
    `_work/probe_a10_5_misses.py` records the run it came from.

    🚨 MEASURED PER TAG, NOT OVER A MIX, AND THE FIRST VERSION WAS A MIX.
    Rotating seven tags through one population gives ONE number that is a
    blend -- and the tag list is the harness's own invention, so a badly chosen
    tag moves the headline while nothing in the product changes. Broken out, it
    said something a blend could never say:

        (no tag) 100%   .en 100%   .eng 100%   .ja 100%   .jpn 100%
        🚨 .es 0%   .fr.forced 0%   .pt-BR 0%   .zh-Hans 0%

    ⭐ AND THE TAG-FREE ROW IS THE CONTROL. A miss with no tag at all is not a
    coverage gap -- it is the key disagreeing with ITSELF, which is a defect.
    It caught three ordering faults in this module in a row."""
    tags = [u"", u".en", u".eng", u".ja", u".jpn", u".en.forced", u".en.sdh",
            u".es", u".fr.forced", u".pt-BR", u".zh-Hans", u"[eng]",
            u".ja[sdh]"]
    films = [n for n in western_names if M.is_film(n)]
    assert len(films) > 200, "only %d of %d parse as a film" % (
        len(films), len(western_names))

    worst, report = None, []
    for tag in tags:
        paired, misses = 0, []
        for name in films:
            # ⚠ `os.path.splitext` was used here and it was WRONG on the exact
            # population this measures: it truncates
            # `1080p.AMZN.WEB-DL.DDP5.1.H.264-EVO` at `.264-EVO`, because a
            # dotted release name is all "extension" to it. `strip_extension`
            # removes only a KNOWN media extension.
            stem = M.strip_extension(name)
            video, subtitle = stem + u".mkv", stem + tag + u".srt"
            if M.read_name(video).stem_key == M.read_name(subtitle).stem_key:
                paired += 1
            elif len(misses) < 3:
                misses.append((video, subtitle))
        rate = 100.0 * paired / len(films)
        report.append((tag or "(none)", paired, rate, misses))
        if worst is None or rate < worst[2]:
            worst = report[-1]

    control = [row for row in report if row[0] == "(none)"][0]
    assert control[2] == 100.0, (
        "⭐ THE CONTROL FAILED, which is not a coverage gap: with no tag at "
        "all the key disagreed with itself on %d of %d names -- %r"
        % (len(films) - control[1], len(films), control[3]))
    # A measured floor, recorded from the run in
    # `_work/probe_a10_5_misses.py`. Every tag form measured 99.73-100%.
    assert worst[2] >= 99.0, (
        "rung 1 on tag %r paired %d of %d real Western film names (%.2f%%); "
        "first misses %r  ·  full table %r"
        % (worst[0], worst[1], len(films), worst[2], worst[3],
           [(t, round(r, 2)) for t, _p, r, _m in report]))


def test_the_SHAPED_negative_control_produces_no_false_pairs():
    """🚨 `LEDGER.md` §Harness: *A NEGATIVE CONTROL THAT DRAWS UNIFORMLY CANNOT
    SEE A SHAPED FAILURE.* Zero of four thousand was true and measured almost
    nothing -- the shape it existed to catch occurred **3 times in 3,999**.

    So the three shapes a real movie library produces that LOOK like one film
    are constructed on purpose: a remake, a cut, and a sequel."""
    shaped = [
        (u"The Thing (1982).mkv", u"The Thing (2011).en.srt", "remake"),
        (u"Suspiria (1977).mkv", u"Suspiria (2018).en.srt", "remake"),
        (u"Dune (1984).mkv", u"Dune (2021).en.srt", "remake"),
        (u"Blade Runner (1982) [Final Cut].mkv",
         u"Blade Runner (1982) [Theatrical].en.srt", "cut"),
        (u"Aliens (1986) [Special Edition].mkv",
         u"Aliens (1986) [Theatrical Cut].en.srt", "cut"),
        (u"Apocalypse Now (1979) [Redux].mkv",
         u"Apocalypse Now (1979) [Theatrical].en.srt", "cut"),
        (u"Alien (1979).mkv", u"Aliens (1986).en.srt", "sequel"),
        (u"Blade Runner (1982).mkv", u"Blade Runner 2049 (2017).en.srt",
         "sequel"),
        (u"Toy Story (1995).mkv", u"Toy Story 2 (1999).en.srt", "sequel"),
    ]
    wrong = []
    for video, subtitle, shape in shaped:
        result = M.pair_movies([u"L:/A/" + video], [u"L:/B/" + subtitle])
        if result.pairs:
            wrong.append((shape, video, subtitle))
    assert wrong == [], wrong
    # ⭐ The positive control lives inside the same check, so the two cannot
    # drift apart: a harness that refuses everything would pass the assertion
    # above and mean nothing.
    same = M.pair_movies([u"L:/A/The Thing (1982).mkv"],
                         [u"L:/B/The Thing (1982).en.srt"])
    assert len(same.pairs) == 1, same


def test_the_UNIFORM_negative_control_never_pairs_two_DIFFERENT_titles(
        western_names):
    """⚠ Both controls are kept, and this is the weaker one on purpose: it says
    no rung fires across a random draw of a real population, which the shaped
    control cannot say because it only contains nine constructed rows.

    🚨 ITS FIRST VERSION WAS WRONG, AND IN AN INSTRUCTIVE DIRECTION. It skipped
    a draw only when both sides carried the SAME `(key, year)`, then counted
    every shared title key as a false pair -- and reported **3 of 3,998**. All
    three were correct: `gentlemen prefer blondes eng dvd` against
    `Gentlemen.Prefer.Blondes.1953.1080p.BluRay…` is one film named twice, and
    rung 2 firing on it is the mechanism working. **A negative control that
    counts successes is not a control.**

    ⭐ So the claim is stated exactly: **two names with DIFFERENT title keys
    never pair.** Both rungs require key equality, so this pins the
    construction -- and it is what goes red if anybody adds a fuzzy rung."""
    import random

    films = [n for n in western_names
             if M.is_film(n) and M.read_name(n).key]
    if len(films) < 200:
        pytest.skip("SKIPPED, NOT PASSED: only %d film names" % len(films))
    rng = random.Random(SEED)
    drawn, wrong = 0, []
    for _ in range(4000):
        a, b = rng.choice(films), rng.choice(films)
        ra, rb = M.read_name(a), M.read_name(b)
        if ra.key == rb.key:
            continue                     # the same title, whatever the year
        drawn += 1
        if M.pair_movies([u"L:/A/" + a], [u"L:/B/" + b]).pairs:
            wrong.append((a, b))
    assert drawn > 3000, "only %d of 4000 draws were cross pairs" % drawn
    assert wrong == [], (
        "%d of %d uniform cross pairs with DIFFERENT title keys were paired: "
        "%r" % (len(wrong), drawn, wrong[:3]))


def test_real_EPISODE_names_are_never_taken_by_the_movie_path():
    """🔒 The sealed slice is excluded by `split_key` on the show name, the
    same folding the corpus split itself uses -- and the exclusion is asserted
    to have FIRED, because asserting only absence passes against a corpus that
    happens to contain no sealed shows.

    ⚠ `LEDGER.md`: *a test's CANDIDATE POOL can break the seal, and nothing
    says so.* It was noticed once only because it made a number worse."""
    from tsubasa.dev import corpus as C

    cfg = load_config(ROOT)
    root = corpus_root(cfg, ROOT)
    if not root.is_dir():
        pytest.skip("SKIPPED, NOT PASSED: corpus absent on this machine")
    scope = root / "video-naming"
    if not scope.is_dir():
        pytest.skip("SKIPPED, NOT PASSED: no video-naming corpus")
    try:
        manifest = C.load_manifest(cfg, ROOT)
    except Exception as exc:                                 # noqa: BLE001
        pytest.skip("SKIPPED, NOT PASSED: %s" % exc)
    sealed = {C.split_key(show)
              for scope_data in manifest.get("scopes", {}).values()
              for show in scope_data.get("sealed", [])}

    names, skipped_sealed = [], 0
    for show_dir in sorted(scope.iterdir()):
        if not show_dir.is_dir():
            continue
        if C.split_key(show_dir.name) in sealed:
            skipped_sealed += 1
            continue
        for entry in sorted(show_dir.iterdir())[:12]:
            if entry.is_file():
                names.append(entry.name)
    assert skipped_sealed > 0, (
        "nothing was excluded as sealed -- the exclusion never fired, so this "
        "check proves nothing about the seal")
    if len(names) < 500:
        pytest.skip("SKIPPED, NOT PASSED: only %d names" % len(names))

    claimed = [n for n in names
               if E.parse_ours(n).episode is not None
               and M.read_name(n).is_film]
    assert claimed == [], (
        "%d of %d non-sealed video-corpus names carry an episode number and "
        "were still offered to the movie path; first five %r"
        % (len(claimed), len(names), claimed[:5]))
