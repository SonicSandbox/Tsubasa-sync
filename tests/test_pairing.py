# -*- coding: utf-8 -*-
"""
Candidate generation: what might pair, and what must never. RUNBOOK step A5.

`06-edge-cases.md` §4 and §3.45.

⭐ THE TWO CLAIMS

1. **Scale.** *500 videos × 1500 subtitles* must never be a nested loop.
   Keyed on `(season, episode)` the cost is one pass plus the handful that
   share a key — 750,000 comparisons become a few thousand.
2. 🚨 **Season AND episode, never episode alone.** Grouping on the episode
   number by itself manufactured **305 false pairs** on multi-season shows —
   Series 1 Episode 3 scored against Series 3 Episode 3 — and that mistake was
   made **three separate times in one session** (`LEDGER-HOT.md`). It is the
   single most repeated defect in this project.

⚠ Candidate generation is not pairing. Everything here answers *"is this worth
scoring?"*; the answer to *"is this the pair?"* is timing's, and refusing to
confuse the two is what keeps a wrong-but-plausible name from deciding
anything.
"""
import os
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tsubasa import discover as D                          # noqa: E402


def build(root, names):
    for rel in names:
        path = Path(root) / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")
    return str(root)


def candidates(root):
    return D.Candidates(D.parse_all(D.walk(root)))


# ==========================================================================
# 🚨 season AND episode
# ==========================================================================

def test_two_seasons_sharing_an_episode_number_do_not_cross_pair(tmp_path):
    """🚨 THE 305-FALSE-PAIR DEFECT, as a check.

    Series 1 Episode 3 against Series 3 Episode 3. It looked like a threshold
    problem for three shows before anyone noticed the measuring script had
    grouped on the episode number alone.
    """
    root = build(tmp_path, [
        "Show/S01/Show S01E03.mkv", "Show/S01/Show S01E03.srt",
        "Show/S03/Show S03E03.mkv", "Show/S03/Show S03E03.srt",
    ])
    cand = candidates(root)
    for video in cand.videos:
        got = cand.for_video(video)
        assert len(got) == 1, (video.name, [s.name for s in got])
        assert got[0].key == video.key
        assert got[0].key[0] == video.key[0], "seasons crossed"


def test_a_seasonless_subtitle_still_meets_its_season_one_video(tmp_path):
    """⚠ The other direction, and it is a whole naming culture.

    `Show - 03.srt` carries no season; `Show S01E03.mkv` carries season 1.
    They are the same episode written two ways. A key that demanded an exact
    season match would refuse every anime-style subtitle against every
    Western-style video.
    """
    root = build(tmp_path, ["V/Show S01E03.mkv", "S/Show - 03.srt"])
    cand = candidates(root)
    video = cand.videos[0]
    got = cand.for_video(video)
    assert len(got) == 1, [s.name for s in got]
    assert got[0].key == (None, 3), got[0].key


def test_a_seasonless_subtitle_reaches_ANY_season_and_that_is_correct(tmp_path):
    """⚠ The leniency is symmetric, and this row was written the wrong way
    round first.

    `Show - 03.srt` sitting beside a `S02` folder is episode 3 of season 2.
    Restricting a season-less subtitle to season 1 would break layout 4 —
    `Show/S02/episodes + subs` — for every anime-style subtitle in it. What
    the index must never do is put two names that BOTH state a season, and
    state different ones, together; that is the check above.

    ⭐ An ambiguity is handed to timing, not resolved by a guess about
    folders (`06-edge-cases.md` §4).
    """
    root = build(tmp_path, ["V/Show S02E03.mkv", "S/Show - 03.srt"])
    cand = candidates(root)
    got = cand.for_video(cand.videos[0])
    assert [s.name for s in got] == ["Show - 03.srt"]
    assert got[0].key == (None, 3)


# ==========================================================================
# ⭐ scale -- an index, never a loop
# ==========================================================================

def test_five_hundred_videos_against_fifteen_hundred_subs_is_not_a_nested_loop(tmp_path):
    """🚨 `06-edge-cases.md` §4, by name. The naive form is 750,000
    comparisons; keyed, it is one pass plus what actually shares a key.

    ⚠ Asserted as WORK DONE, not as wall time — a timing assertion on someone
    else's machine is a flake generator. The witness is the total number of
    candidate pairs, which is what a nested loop would blow up.
    """
    names = []
    for show in range(10):
        for ep in range(50):
            names.append("V/Show %02d/Show %02d - %02d.mkv" % (show, show, ep + 1))
    for show in range(10):
        for ep in range(50):
            for lang in ("en", "ja", "es"):
                names.append("S/Show %02d/Show %02d - %02d.%s.srt"
                             % (show, show, ep + 1, lang))
    root = build(tmp_path, names)

    started = time.time()
    cand = candidates(root)
    fan = cand.fan_out()
    elapsed = time.time() - started

    assert len(cand.videos) == 500 and len(cand.subtitles) == 1500
    total = sum(fan.values())
    # Ten shows share every episode number, and each has three languages, so
    # the honest fan-out is 10 x 3 = 30 per video: 15,000 pairs, not 750,000.
    assert total <= 40000, (
        "%d candidate pairs for 500 videos x 1500 subtitles -- a nested loop "
        "would be 750,000" % total)
    assert max(fan.values()) <= 40, "fan-out per video reached %d" % max(fan.values())
    assert elapsed < 60, "%.1fs -- generation should be seconds, not minutes" % elapsed


def test_the_index_is_built_once_and_reused(tmp_path):
    """⚠ A per-call rebuild is a nested loop wearing an index's clothes."""
    root = build(tmp_path, ["V/Show - %02d.mkv" % i for i in range(1, 31)] +
                           ["S/Show - %02d.srt" % i for i in range(1, 31)])
    cand = candidates(root)
    first = [s.path for s in cand.for_video(cand.videos[0])]
    second = [s.path for s in cand.for_video(cand.videos[0])]
    assert first == second and first


# ==========================================================================
# languages, and what "the same episode" means
# ==========================================================================

def test_every_language_of_one_episode_is_a_candidate(tmp_path):
    """`06-edge-cases.md` §4: several languages, same episode — all pair, all
    sync, one kept per language. So all of them must survive to scoring."""
    root = build(tmp_path, [
        "Show/Show - 01.mkv",
        "Show/Show - 01.en.srt", "Show/Show - 01.ja.srt",
        "Show/Show - 01.es.srt", "Show/Show - 01.ja.forced.srt",
    ])
    cand = candidates(root)
    got = cand.for_video(cand.videos[0])
    assert len(got) == 4, sorted(s.name for s in got)


def test_language_tags_do_not_change_the_episode_key(tmp_path):
    """Stripped for MATCHING, retained for output naming. The key must not
    notice them at all."""
    root = build(tmp_path, [
        "Show/Show - 07.mkv", "Show/Show - 07.ja.srt",
        "Show/Show - 07.sdh.srt", "Show/Show - 07.ja.cc.srt",
    ])
    cand = candidates(root)
    keys = {s.key for s in cand.subtitles}
    assert keys == {cand.videos[0].key}, keys


# ==========================================================================
# films
# ==========================================================================

def test_films_are_kept_out_of_the_episode_index(tmp_path):
    """⭐ Every film has no episode, so every film keys as `(None, None)`.
    Indexing them together would make each one a candidate for all the others
    — the same collapse a release year caused when it was returned as an
    episode number (`LEDGER.md` §Logic)."""
    root = build(tmp_path, [
        "Films/Inception (2010).mkv", "Films/Inception (2010).srt",
        "Films/Blade Runner (1982).mkv", "Films/Blade Runner (1982).srt",
        "Films/Sintel.mkv", "Films/Sintel.srt",
    ])
    cand = candidates(root)
    assert len(cand.films()) == 3, [f.name for f in cand.films()]
    for film in cand.films():
        assert cand.for_video(film) == [], (
            "a film was given episode candidates: %s"
            % [s.name for s in cand.for_video(film)])


def test_a_release_year_is_not_treated_as_an_episode(tmp_path):
    """🚨 `Inception (2010)` returning episode 2010 bucketed an entire film
    library under one fabricated episode. Found by review against 318 green
    checks (`LEDGER.md` §Logic)."""
    root = build(tmp_path, ["F/Inception (2010).mkv",
                            "F/Blade Runner (1982) [Final Cut].mkv"])
    cand = candidates(root)
    for video in cand.videos:
        assert video.key == (None, None), (video.name, video.key)


# ==========================================================================
# duration -- the cheapest filter there is
# ==========================================================================

def test_a_subtitle_longer_than_its_video_is_rejected_on_runtime_alone():
    """⭐ Sonic's observation: *"you won't have a movie that is 1 hour long and
    subs that are 1 hour 30 minutes."* Rejects before any timing work."""
    video = D.Item("v.mkv", "video", duration=3600.0)
    fits = D.Item("a.srt", "subtitle", cues=3500.0)
    too_long = D.Item("b.srt", "subtitle", cues=5400.0)
    assert D.duration_verdict(video, fits) == "ok"
    assert D.duration_verdict(video, too_long) == "reject"


def test_an_unknown_duration_is_not_evidence():
    """⚠ Absent is not short. A video we have not probed must not have its
    candidates thrown away — the same distinction as UNANSWERED vs ABSENT."""
    video = D.Item("v.mkv", "video", duration=None)
    sub = D.Item("a.srt", "subtitle", cues=99999.0)
    assert D.duration_verdict(video, sub) == "ok"
    assert D.duration_verdict(D.Item("v.mkv", "video", duration=3600.0),
                              D.Item("a.srt", "subtitle", cues=None)) == "ok"


def test_a_subtitle_that_stops_before_the_credits_is_still_accepted():
    """⚠ The tolerance is ASYMMETRIC on purpose. A subtitle's last cue
    precedes the credits, and a broadcast recording carries CM breaks the
    release does not — being shorter is normal, being longer is not. Tighter
    than this and legitimate pairs get thrown away."""
    video = D.Item("v.mkv", "video", duration=1420.0)
    for last_cue in (1417.0, 1300.0, 1100.0, 900.0):
        sub = D.Item("a.srt", "subtitle", cues=last_cue)
        assert D.duration_verdict(video, sub) == "ok", last_cue


# ==========================================================================
# proximity is a SIGNAL
# ==========================================================================

def test_proximity_ranks_but_never_disqualifies(tmp_path):
    """⭐ The property layouts 5-7 stand on. Distance orders candidates; it
    never removes one."""
    root = build(tmp_path, [
        "Lib/Show/Show - 01.mkv",
        "Lib/Show/Show - 01.srt",            # same dir
        "Lib/Show/Subs/Show - 01.en.srt",    # child
        "Lib/Other/Show - 01.ja.srt",        # sibling tree
        "Far/Away/Show - 01.es.srt",         # different tree
    ])
    cand = candidates(root)
    video = cand.videos[0]
    got = cand.for_video(video)
    assert len(got) == 4, sorted(s.name for s in got)

    scores = {os.path.basename(s.path): D.proximity(video, s) for s in got}
    assert scores["Show - 01.srt"] == D.SAME_DIR
    assert scores["Show - 01.en.srt"] == D.PARENT_OR_CHILD
    assert scores["Show - 01.ja.srt"] == D.SIBLING
    assert scores["Show - 01.es.srt"] < D.SIBLING
    assert min(scores.values()) >= 0.0, "distance must never be a veto"


# ==========================================================================
# ⭐ the FILM gate -- one file, one path, never both
# ==========================================================================

def test_a_numbered_sequel_is_owned_by_the_MOVIE_path_not_the_episode_index():
    """🚨 A NUMBERED SEQUEL PARSES AS AN EPISODE, so `key == (None, None)` does
    not find it and the file is claimed by BOTH paths.

    Measured at A10 over 904 real Western release names: **45 of them (5.0%)** —
    `Toy Story 2 (1999)` → episode 2, `Iron Man 3` → 3, `Alien 3` → 3 — each
    bucketing a film library under a fabricated episode. It is the
    `Inception (2010)` → `(None, 2010)` defect `LEDGER.md` §Logic records,
    wearing a smaller number.

    ⛔ Being paired twice is a CORRECTNESS bug, not an inefficiency: the two
    paths can reach different answers and both write.
    """
    items = [D.Item(u"Toy Story 2 (1999).mkv", "video"),
             D.Item(u"Toy Story 2 (1999).en.srt", "subtitle")]
    D.parse_all(items, scheme_hint=False)
    cand = D.Candidates(items)
    video = cand.videos[0]

    assert video.key == (None, 2), (
        "the fixture no longer exhibits the defect -- the parser stopped "
        "reading the sequel number as an episode, read it before editing this")
    assert cand.is_film(video)
    assert cand.for_video(video) == [], "a film must not use the episode index"
    assert [f.name for f in cand.films()] == [u"Toy Story 2 (1999).mkv"]


def test_the_film_exclusion_is_SYMMETRIC_and_covers_the_subtitle_side():
    """⛔ Gating only the VIDEO side leaves the film's SUBTITLE filed under
    episode 2, where it is offered to every `- 02` video in the library.

    ⚠ Measured while wiring A10 — the half-applied gate gave `Show - 02.mkv`
    two candidates, one of them a film's subtitle. **A file the movie path owns
    is out of the episode index on BOTH sides**, or the index still carries the
    collision it exists to prevent.
    """
    items = [D.Item(u"Toy Story 2 (1999).mkv", "video"),
             D.Item(u"Toy Story 2 (1999).en.srt", "subtitle"),
             D.Item(u"Show - 02.mkv", "video"),
             D.Item(u"Show - 02.srt", "subtitle")]
    D.parse_all(items, scheme_hint=False)
    cand = D.Candidates(items)
    show = [v for v in cand.videos if v.name.startswith(u"Show")][0]

    got = sorted(s.name for s in cand.for_video(show))
    assert got == [u"Show - 02.srt"], got


def test_a_real_episode_is_NOT_taken_by_the_film_gate():
    """⚠ Test both directions. A gate that classified everything as a film
    would pass every check above and silently empty the episode index."""
    items = [D.Item(u"Show - 02.mkv", "video"),
             D.Item(u"Show - 02.srt", "subtitle")]
    D.parse_all(items, scheme_hint=False)
    cand = D.Candidates(items)
    video = cand.videos[0]
    assert not cand.is_film(video)
    assert len(cand.for_video(video)) == 1
    assert cand.films() == []


def test_a_film_does_not_collect_a_REAL_episode_that_shares_its_number():
    """⭐ THE NARROWEST WITNESS FOR THE VIDEO-SIDE HALF OF THE GATE.

    A mutation removing `for_video`'s film check SURVIVED the sequel test
    above, because that fixture's only subtitle is the film's own — already
    excluded on the subtitle side, so the index is empty and `for_video`
    returns nothing whatever it does.

    ⚠ Same shape as the kana epenthetic-vowel mutant and A10's rung-2 mutant:
    **the rule was fine; the check could not feel it.** Here the film meets a
    *real* episode carrying the same number, so only the video-side gate can
    keep them apart.
    """
    items = [D.Item(u"Toy Story 2 (1999).mkv", "video"),
             D.Item(u"Show - 02.srt", "subtitle")]
    D.parse_all(items, scheme_hint=False)
    cand = D.Candidates(items)
    film = cand.videos[0]

    assert film.key == (None, 2) and cand.is_film(film)
    assert len(cand.subtitles) == 1 and not cand.is_film(cand.subtitles[0]), (
        "the fixture must contain a REAL episode subtitle, or the video-side "
        "gate is not what is being tested")
    assert cand.for_video(film) == [], (
        "a film collected a real episode's subtitle on its fabricated number")


# ==========================================================================
# 🚨 ABSOLUTE EPISODE NUMBERING
#
# Reported by Sonic against his own library, 2026-09-10:
# `[SubsPlease] Hell Mode S2 - 10` and `ヘルモード…S02E22…ABEMA.ja[cc].srt`
# are the same episode and nothing was ever offered for the video.
# ABEMA and DMMTV write a per-season SEASON tag with an ABSOLUTE episode
# number: measured across that folder, E17 → ep 5, E18 → ep 6, E22 → ep 10,
# a constant −12, and season 1 ran twelve episodes.
# ==========================================================================

HELL_VIDEO = u"[SubsPlease] Hell Mode S2 - 10 (1080p) [DD805213].mkv"
HELL_SUBS = [u"Hell Mode S02E17.ja.srt", u"Hell Mode S02E18.ja.srt",
             u"Hell Mode S02E22.ja.srt"]


def test_absolute_numbering_offers_the_season_when_the_two_sides_are_disjoint(
        tmp_path):
    u"""⭐ THE CASE THAT PROMPTED IT. Videos {10} against subtitles
    {17, 18, 22}: no shared number anywhere, which is what a difference in
    numbering SCHEME looks like from the outside."""
    cand = candidates(build(tmp_path, [HELL_VIDEO] + HELL_SUBS))
    video = [v for v in cand.videos if u"Hell Mode" in v.name][0]

    offered = cand.for_video(video)
    assert len(offered) == 3, [s.name for s in offered]
    for sub in offered:
        assert cand.was_speculative(video.path, sub.path), sub.name


def test_a_gap_is_a_gap_when_the_two_sides_DO_share_a_number(tmp_path):
    u"""🚨 THE FIRST TRIGGER WAS WRONG AND THIS IS THE CHECK THAT SAID SO.

    *"The video was offered nothing"* is the ORDINARY state of a partly
    subtitled library — `Scan.unpaired`'s own docstring says a folder with 24
    videos and 20 subtitles has four of them and is working perfectly. Firing
    there would spend an alignment per candidate rediscovering that a subtitle
    is simply absent, and would erase `unpaired`, which is a real signal.

    ⭐ One shared episode number proves both sides count the same way.
    """
    cand = candidates(build(tmp_path, [u"Show S01E01.mkv", u"Show S01E09.mkv",
                                       u"Show S01E01.ja.srt"]))
    nine = [v for v in cand.videos if u"E09" in v.name][0]
    one = [v for v in cand.videos if u"E01" in v.name][0]

    assert cand.for_video(nine) == [], (
        "episode 1 pairs by number, so the schemes agree and episode 9 simply "
        "has no subtitle")
    assert [s.name for s in cand.for_video(one)] == [u"Show S01E01.ja.srt"]


def test_the_fallback_can_never_change_an_answer_that_already_existed(
        tmp_path):
    u"""⛔ THE PROPERTY THAT MAKES THIS SAFE TO SHIP. It fires only where the
    ordinary path returned nothing, so no video that pairs today can be
    given a different answer."""
    names = [u"Show S01E01.mkv", u"Show S01E02.mkv",
             u"Show S01E01.ja.srt", u"Show S01E02.ja.srt"]
    cand = candidates(build(tmp_path, names))
    for video in cand.videos:
        offered = cand.for_video(video)
        assert len(offered) == 1
        assert not cand.was_speculative(video.path, offered[0].path)


def test_the_fallback_never_crosses_a_SEASON(tmp_path):
    u"""🚨 `LEDGER-HOT.md`: grouping on episode alone made *Series 1 Ep 3*
    score against *Series 3 Ep 3* and manufactured **305 false pairs**, three
    separate times. That guard is not reopened — the fallback is same-season
    only, and a season-2 video sees nothing from season 1."""
    cand = candidates(build(tmp_path, [u"Show S02E10.mkv",
                                       u"Show S01E17.ja.srt",
                                       u"Show S01E22.ja.srt"]))
    video = cand.videos[0]
    assert video.key == (2, 10)
    assert cand.for_video(video) == [], (
        "a season-2 video was offered season-1 subtitles")


def test_a_film_never_reaches_the_fallback(tmp_path):
    u"""⛔ A numbered sequel parses as an episode. `Toy Story 2` must not
    collect a season's worth of subtitles on its fabricated number."""
    items = [D.Item(u"Toy Story 2 (1999).mkv", "video"),
             D.Item(u"Show S01E17.srt", "subtitle"),
             D.Item(u"Show S01E22.srt", "subtitle")]
    D.parse_all(items, scheme_hint=False)
    cand = D.Candidates(items)
    film = cand.videos[0]
    assert cand.is_film(film)
    assert cand.for_video(film) == []


def test_the_fallback_is_capped(tmp_path):
    u"""⚠ A COST BOUND, not a correctness one. One unpaired video in a
    300-subtitle season must not quietly cost 300 alignments.

    🚨 ASSERTED AGAINST A LITERAL, NOT AGAINST THE CONSTANT UNDER TEST. The
    first version read `<= D.ABSOLUTE_FALLBACK_CAP`, so a mutant that raised
    the cap to a million raised the assertion with it and SURVIVED — the check
    read its own subject. `LEDGER-HOT.md` records the same shape: *a check
    looping `range(1, CONST)` empties itself when `CONST` is zeroed.*
    """
    names = [u"Show S01E900.mkv"]
    names += [u"Show S01E%03d.ja.srt" % n for n in range(1, 200)]
    cand = candidates(build(tmp_path, names))
    video = [v for v in cand.videos if u"900" in v.name][0]
    offered = cand.for_video(video)
    assert 0 < len(offered) <= 64, len(offered)
    assert len(offered) < 199, (
        "every subtitle in the season was offered — the cap did nothing")


# ==========================================================================
# 🚨 THE DERIVED EPISODE OFFSET
#
# A complete absolute-numbered season OVERLAPS the per-season one: videos
# S02E01–E24 against subtitles S02E13–E36. Twelve videos then paired BY NUMBER
# with the wrong subtitle and the other twelve were offered nothing, because
# `out` was non-empty and short-circuited the fallback. Measured 2026-09-10.
# ==========================================================================

@pytest.mark.parametrize("videos,subs,want", [
    (set(range(1, 25)), set(range(1, 25)), None),      # agreeing
    (set(range(1, 25)), set(range(13, 37)), 12),       # absolute, complete
    (set(range(1, 13)), set(range(13, 37)), None),     # half library, ambiguous
    ({10}, {17, 18, 22}, None),                        # the reported folder
    ({1}, {13}, None),                                 # one video is not a pattern
    ({1, 2}, {13, 14}, 12),                            # two is
    ({1, 2}, {13, 14, 15}, None),                      # two shifts tie
    ({1, 2, 4, 5}, {13, 14, 16, 17}, 12),              # gaps do not matter
    (set(), {13}, None),
])
def test_the_offset_is_derived_or_REFUSED(videos, subs, want):
    u"""⭐ COVERAGE, NOT A DIFFERENCE HISTOGRAM.

    The obvious instrument fails here and was measured failing: on the
    complete overlapping season the true offset wins with **24 votes against
    23 for each neighbour**, because two contiguous integer runs overlap
    almost as well at ±1. Picking that apex is a threshold set by taste on a
    one-vote margin.

    ⛔ Coverage needs none: a single argmax, non-zero, strictly better than no
    shift, over at least two videos. Ambiguity returns None, which is a real
    answer — `01-scope.md` Rule 2.
    """
    assert D.episode_offset(videos, subs) == want


def test_ONE_video_can_never_evidence_a_shift():
    u"""🚨 THE ONE-SAMPLE TRAP, IN A NEW DOMAIN. With a single video ANY shift
    that reaches a subtitle scores a perfect 1 of 1 and is trivially unique.
    `LEDGER-HOT.md` records the identical shape: *a subtitle containing ONE
    cue scored 5.15x chance, because the best of thousands of candidate
    offsets always lands that one cue on something.*"""
    for sub in (13, 40, 999):
        assert D.episode_offset({1}, {sub}) is None, sub


def test_the_overlapping_season_offers_every_video_its_TRUE_subtitle(tmp_path):
    u"""🚨 THE DEFECT THIS EXISTS FOR. Before the offset: twelve videos paired
    by number with a subtitle that was really a different episode, and twelve
    were offered nothing at all."""
    names = [u"Show S02E%02d.mkv" % n for n in range(1, 25)]
    names += [u"Show S02E%02d.ja.srt" % (n + 12) for n in range(1, 25)]
    cand = candidates(build(tmp_path, names))
    # ⚠ The index alone cannot derive this — grouping needs series identity,
    # which lives on `Scan`. Here the titles are equal, so it is provable
    # without it.
    cand.set_offsets({v.path: 12 for v in cand.videos})

    for video in cand.videos:
        offered = cand.for_video(video)
        wanted = video.key[1] + 12
        assert wanted in [s.key[1] for s in offered], (
            u"episode %d was not offered subtitle E%d"
            % (video.key[1], wanted))
        # ⛔ EVERY candidate is speculative, including the by-number one:
        # a shift means the numbers are not trustworthy for this group, and
        # trashing the loser would destroy a real subtitle.
        for sub in offered:
            assert cand.was_speculative(video.path, sub.path), sub.name


def test_an_agreeing_season_gets_no_offset_and_no_speculation(tmp_path):
    u"""⛔ THE CONTROL. A library whose numbers already line up must be
    untouched — same candidates, none of them speculative."""
    names = [u"Show S02E%02d.mkv" % n for n in range(1, 25)]
    names += [u"Show S02E%02d.ja.srt" % n for n in range(1, 25)]
    cand = candidates(build(tmp_path, names))
    for video in cand.videos:
        offered = cand.for_video(video)
        assert [s.key[1] for s in offered] == [video.key[1]]
        assert not cand.was_speculative(video.path, offered[0].path)
