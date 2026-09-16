# -*- coding: utf-8 -*-
u"""
Runtime as a pairing signal. RUNBOOK step A9. `spec/06-edge-cases.md` §3.45.

⭐ THE STANDING RULE THIS SUITE ENFORCES: **both directions.** A duration
filter is trivially satisfiable in either direction -- one that rejects
nothing passes every "a correct pair survives" check, and one that rejects
everything passes every "a wrong pair is caught" check. Every section below
carries its own opposite.

🚨 AND THE SHORT SIDE IS THE ONE TO READ. `06-edge-cases.md` §3.45 proposes
*"shorter by more than ~15%"* and RUNBOOK A9 measured it: it destroys 2.5% of
correct same-video pairs and 2.5% of correct cross-release pairs to catch 1.8%
of wrong-EPISODE candidates -- which is the population the `(season, episode)`
index actually hands it. **It is not built**, and several checks here exist
specifically to go red if anyone adds it back.

⚠ HERMETIC. Every value is a number typed into the check. No media, no corpus,
no environment -- so nothing here can SKIP and quietly read as a pass.
"""
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tsubasa.duration import (IMPOSSIBLE, LONG_ABSOLUTE,        # noqa: E402
                              LONG_RATIO,
                              MIN_CUES_FOR_A_RUNTIME_CLAIM,
                              ORPHAN_GAP, PLAUSIBLE,
                              SCORE_LONG_SCALE, SCORE_SHORT_SCALE,
                              THRESHOLDS_ARE_MEASURED, UNKNOWN,
                              content_end, duration_score, duration_verdict)

#: A 24-minute episode, the shape most of the corpus is. `[SubsPlease] 86 -
#: Eighty Six - 03v2` measures 1420.06 s by ffprobe.
EPISODE = 1420.0
#: A feature film. `Sintel` is 888.9 s; a 2-hour film is the movie-library case
#: `06-edge-cases.md` §3.5 calls a launch use case.
FILM = 7200.0


def verdict(video, subtitle, cues=None):
    return duration_verdict(video, subtitle, cues)[0]


def reason(video, subtitle, cues=None):
    return duration_verdict(video, subtitle, cues)[1]


# ==========================================================================
# ⭐ Sonic's observation -- the case the whole step exists for
# ==========================================================================

def test_a_ninety_minute_subtitle_cannot_belong_to_a_sixty_minute_video():
    u"""⭐ *"you won't have a movie that is 1 hour long and subs that are 1
    hour 30 minutes."* Stated in seconds, exactly as he said it.

    🚨 It is also why `LONG_RATIO` is 1.25 and not 1.50: his own example is
    EXACTLY 1.50, and the comparison is strict, so a bound at 1.50 would let
    the one case he named walk straight through it.
    """
    assert verdict(3600.0, 5400.0) == IMPOSSIBLE
    assert 5400.0 / 3600.0 == 1.5
    assert LONG_RATIO < 1.5, (
        "a bound at 1.50 does not catch the 1.50 case Sonic named")


def test_a_subtitle_that_fits_its_video_is_plausible():
    u"""The positive control for the check above. ⚠ Without it, a function
    that returned IMPOSSIBLE for everything would pass."""
    assert verdict(3600.0, 3500.0) == PLAUSIBLE
    assert verdict(EPISODE, 1416.5) == PLAUSIBLE
    assert verdict(FILM, 7100.0) == PLAUSIBLE


def test_an_episode_subtitle_on_a_film_is_impossible_and_the_reverse_is_not():
    u"""⭐ BOTH DIRECTIONS OF THE SAME PAIR, and they are not symmetric.

    A film's subtitle on an episode's video is impossible -- 7,200 s of
    content cannot fit 1,420 s. An episode's subtitle on a film's video is
    NOT: that is a subtitle covering part of the runtime, which
    `06-edge-cases.md` §5.1 requires to align its covered stretch.
    """
    assert verdict(EPISODE, 7100.0) == IMPOSSIBLE
    assert verdict(FILM, 1416.5) == PLAUSIBLE


# ==========================================================================
# 🚨 the SHORT side -- the measured decision not to reject
# ==========================================================================

def test_a_partial_coverage_subtitle_is_never_rejected_on_shortness():
    u"""🚨 THE MEASURED DECISION, AND THE CHECK THAT GUARDS IT.

    `06-edge-cases.md` §3.45 proposes rejecting below ~85% of the runtime.
    Measured over the corpus (`_work/probe_a9_duration.py`):

        correct same-video pairs it destroys      7 of 280  (2.5%)
        correct cross-release pairs it destroys  10 of 399  (2.5%)
        wrong-EPISODE candidates it catches       7 of 399  (1.8%)

    and 14 of the 17 correct pairs it destroys carry >= 40 cues, so they are
    real dialogue tracks and a cue-count floor does not save them. **The
    lowest ratio measured between two CORRECT subtitles of one video is
    0.056.**

    ⛔ Every ratio below is one a correct pair has actually been measured at.
    """
    for ratio in (0.998, 0.931, 0.855, 0.783, 0.709, 0.634, 0.492, 0.217,
                  0.104, 0.056):
        assert verdict(EPISODE, EPISODE * ratio, 400) == PLAUSIBLE, ratio


def test_the_shipped_pairing_check_would_still_pass():
    u"""⚠ `tests/test_pairing.py::test_a_subtitle_that_stops_before_the_
    credits_is_still_accepted` is a GREEN check in another suite asserting
    that 900 s against 1,420 s is accepted. A short-side bound anywhere above
    0.634 breaks a shipped assertion, and this suite should feel that before
    the other one does."""
    for last_cue in (1417.0, 1300.0, 1100.0, 900.0):
        assert verdict(1420.0, last_cue) != IMPOSSIBLE, last_cue


def test_a_signs_only_track_is_not_a_wrong_pair():
    u"""⭐ THE 0.056 CASE, AS ITS OWN CHECK. A 22-cue signs/songs track ending
    at 79 s against a 259-cue dialogue track of the SAME video -- measured in
    `samevid_hard`, and both are correct for that video.

    ⚠ It is exactly the shape a percentage cannot describe: it is not a
    subtitle that is 94% short, it is a different kind of object.
    """
    assert verdict(1427.0, 79.4, 22) == PLAUSIBLE


# ==========================================================================
# ⛔ the long bound needs BOTH halves
# ==========================================================================

def test_a_short_video_is_not_rejected_on_a_small_absolute_overshoot():
    u"""⛔ THE RATIO ALONE IS NOT THE RULE. On a 60-second clip a 1.25x bound
    is 15 seconds, and 15 seconds is inside cue rounding and inside a single
    trailing credit. `LONG_ABSOLUTE` is what stops the cheapest check in the
    pipeline getting *sharper* on content that cannot support it.

    ⭐ Measured floor: real cross-release offsets group at ±90 s (with-OP
    against without-OP) and +9.5-10 s (the broadcast CM block) --
    `CORPUS-OPPORTUNITIES.md` §3.4.
    """
    assert verdict(60.0, 90.0) == PLAUSIBLE          # 1.50x, but only +30 s
    assert verdict(180.0, 260.0) == PLAUSIBLE        # 1.44x, but only +80 s
    assert verdict(300.0, 400.0) == PLAUSIBLE        # 1.33x, but only +100 s


def test_a_long_video_is_not_rejected_on_a_small_relative_overshoot():
    u"""⛔ AND THE ABSOLUTE MARGIN ALONE IS NOT THE RULE EITHER. On a two-hour
    film 120 s is 1.7% -- well inside an OP/credits difference -- so a rule
    that fired on the absolute margin alone would reject correct film pairs
    at the far end of the scale it was fitted at the near end of."""
    assert verdict(FILM, FILM + 300.0) == PLAUSIBLE   # +300 s, only 1.04x
    assert verdict(FILM, 8600.0) == PLAUSIBLE         # +1400 s, only 1.19x


def test_the_two_halves_meet_where_they_should():
    u"""⭐ The structural property `LONG_ABSOLUTE` produces, asserted rather
    than described: below `LONG_ABSOLUTE / (LONG_RATIO - 1)` seconds of video
    the absolute margin is the operative rule and the ratio can never fire on
    its own."""
    crossover = LONG_ABSOLUTE / (LONG_RATIO - 1.0)
    assert abs(crossover - 480.0) < 1.0, crossover
    # Just under the crossover: at the ratio bound, the overshoot is still
    # inside the absolute margin.
    short_video = crossover - 100.0
    assert verdict(short_video, short_video * LONG_RATIO * 1.001) == PLAUSIBLE
    # Just over it: the ratio is what binds, and it fires.
    long_video = crossover + 100.0
    assert verdict(long_video, long_video * LONG_RATIO * 1.001) == IMPOSSIBLE


def test_the_op_shift_case_survives():
    u"""🚨 THE CORRECT PAIR THE SPEC WARNS ABOUT. A subtitle authored against
    a broadcast carrying the opening song, applied to a video without it, is
    measured at ±90 s -- 6.3% of a 24-minute episode. It must pair.

    ⭐ This is the check that makes a "tighten the bound to 1.05" change go
    red. Measured: a bound at 1.05 is exceeded by a subtitle's own stray final
    cue, with no video involved at all, on **21.14%** of real corpus files.
    """
    assert verdict(EPISODE, EPISODE + 90.0) == PLAUSIBLE
    assert verdict(EPISODE, EPISODE + 90.0 + 30.0) == PLAUSIBLE   # + 3 CM
    assert verdict(EPISODE, EPISODE * 1.10) == PLAUSIBLE


# ==========================================================================
# ⛔ absent is not a rejection
# ==========================================================================

@pytest.mark.parametrize("video,subtitle", [
    (None, 1416.0),
    (EPISODE, None),
    (None, None),
    (0.0, 1416.0),
    (EPISODE, 0.0),
    (-1.0, 1416.0),
    (EPISODE, float("nan")),
    (float("nan"), 1416.0),
    (float("inf"), 1416.0),
    (EPISODE, float("inf")),
    ("", 1416.0),
    (EPISODE, "not a number"),
])
def test_an_absent_or_nonsense_runtime_is_UNKNOWN_never_a_rejection(video,
                                                                    subtitle):
    u"""⛔ A video nobody probed must not have its candidates thrown away.

    🚨 `LEDGER.md` §Harness: a failed network request scored as a measured
    zero, so *"Wikidata has no alias for this show"* and *"I never got an
    answer"* became the same number -- and the coverage figure fell smoothly
    and plausibly with nothing on screen to say the instrument had changed.
    **An absent answer and an unanswered question are different results.**

    ⚠ NaN is in this list on purpose: every comparison against NaN is False,
    so a naive `<= 0` guard passes it through and every ratio test then reads
    as PLAUSIBLE -- a silent wrong answer rather than a loud one.
    """
    assert duration_verdict(video, subtitle)[0] == UNKNOWN


def test_zero_cues_is_not_zero_seconds():
    u"""🚨 `LEDGER-HOT.md`, shipped twice: *never conflate "parsed zero cues"
    with "could not read the file."* Both are the absence of an answer and
    neither is the number 0 -- and a subtitle whose end reads 0.0 must not be
    called impossibly SHORT or plausibly anything."""
    assert duration_verdict(EPISODE, 0.0)[0] == UNKNOWN
    assert content_end([]) is None
    assert content_end(None) is None


def test_every_non_plausible_verdict_names_what_it_FOUND():
    u"""`doctrine/robustness`: a failure message says what it found, not what
    it wanted, and is written for someone who cannot see the code.

    ⚠ And the two UNKNOWN reasons must not be one reason. *"the video was not
    probed"* and *"the subtitle has no cue times"* send the reader to
    different places, and a single generic string sends them to neither.
    """
    assert u"1420" in reason(EPISODE, None)
    assert reason(None, 1416.0) != reason(EPISODE, None)
    assert reason(None, 1416.0) != reason(None, None)
    r = reason(EPISODE, 7100.0)
    assert u"7100" in r and u"1420" in r, r
    assert u"5680" in r, ("the overshoot itself is what a reader needs", r)
    assert reason(EPISODE, 1416.0) == u""


# ==========================================================================
# 🚨 the one-cue hazard
# ==========================================================================

def test_a_one_cue_subtitle_cannot_make_a_runtime_claim():
    u"""🚨 `LEDGER-HOT.md`: a subtitle containing ONE cue scored **5.15x
    chance** against a real reference, because the best of thousands of
    candidate offsets always lands one cue on something. The same fragility
    arrives here through a different door -- one cue's timestamp is a moment,
    not a runtime.

    ⛔ UNKNOWN, not IMPOSSIBLE. A thin subtitle is refused downstream by
    `align()`'s own floor with a better reason than this could give, and
    answering IMPOSSIBLE would be a confident verdict built from a single
    number.

    🚨 THE COUNTS ARE LITERAL, AND THE FIRST VERSION'S WERE NOT. It looped
    `range(1, MIN_CUES_FOR_A_RUNTIME_CLAIM)` -- so a mutation setting that
    constant to 0 emptied the loop and **the check skipped itself into a
    pass.** `doctrine/verification`: *a wait for `count >= 2` before the thing
    existed... the block then skipped itself, which looks like a pass.* Found
    by the mutation run and by nothing else.
    """
    ran = 0
    for n in (1, 2, 3, 4):
        v, r = duration_verdict(EPISODE, 99999.0, n)
        assert v == UNKNOWN, (n, v)
        assert str(n) in r, (n, r)
        ran += 1
    assert ran == 4, "the loop must actually have run"
    assert verdict(EPISODE, 99999.0, 5) == IMPOSSIBLE


def test_an_unknown_cue_count_does_not_disable_the_check():
    u"""⚠ The count is optional and its absence is not a veto. A caller that
    has a duration and an end time but has not counted the cues still gets an
    answer -- the alternative is a filter that silently stops working for
    every caller who did not pass every argument."""
    assert verdict(EPISODE, 7100.0, None) == IMPOSSIBLE
    assert verdict(EPISODE, 7100.0) == IMPOSSIBLE


def test_the_cue_floor_is_the_projects_OWN_floor():
    u"""⭐ REUSED, NOT INVENTED. `align.MIN_ALIGNABLE_CUES` is the floor this
    project already measured for *"this input can be measured at all"*, and
    `duration.py` keeps a local copy so the cheapest check in the pipeline
    does not import the aligner (and numpy) to read one integer.

    ⛔ A copy is a thing that drifts, so the coupling is asserted here rather
    than trusted to a comment. `doctrine/robustness`: a rule that relies on
    remembering will be forgotten -- make it structural.
    """
    from tsubasa.align import MIN_ALIGNABLE_CUES
    assert MIN_CUES_FOR_A_RUNTIME_CLAIM == MIN_ALIGNABLE_CUES


# ==========================================================================
# the three verdicts
# ==========================================================================

def test_all_three_verdicts_are_reachable():
    u"""⭐ Three outcomes, never a bare boolean -- the same shape as
    `naming/series.py` and the verdict band, for the same reason. A design
    that forces this to two manufactures a confident wrong answer.

    ⚠ `LEDGER.md`: a mutation setting `SAME_AT == DIFFERENT_BELOW` -- the
    entire UNSURE band deleted -- killed **zero** checks, because the one
    check named after the band got its only UNSURE from a different
    mechanism's short-circuit. So this asserts all three from THIS module's
    own inputs.
    """
    seen = {
        duration_verdict(EPISODE, 1416.0)[0],
        duration_verdict(EPISODE, 7100.0)[0],
        duration_verdict(None, 1416.0)[0],
    }
    assert seen == {PLAUSIBLE, IMPOSSIBLE, UNKNOWN}, seen


def test_UNKNOWN_and_PLAUSIBLE_are_different_answers():
    u"""⚠ Folding *cannot tell* into *fine* is the tidy-up this check exists
    to catch. A caller ranking candidates must be able to tell a runtime that
    AGREES from one that was never read -- `06-edge-cases.md` §3.45's third
    use is ranking, and a fabricated agreement corrupts an ordering."""
    assert UNKNOWN != PLAUSIBLE
    assert duration_verdict(None, 1416.0)[0] != \
        duration_verdict(EPISODE, 1416.0)[0]


def test_the_thresholds_are_measured_not_chosen():
    u"""`spec/00-INDEX.md` Rule 2. ⚠ And `SCORE_LONG_SCALE` is the one
    conservative-by-argument value in the module; it says so at its own site
    because there is no population to fit it to."""
    assert THRESHOLDS_ARE_MEASURED is True
    assert LONG_RATIO > 1.0 and LONG_ABSOLUTE > 0.0


# ==========================================================================
# ⭐ the score -- ranking, which is what the CUTS trap actually needs
# ==========================================================================

def test_an_absent_score_is_None_never_zero():
    u"""⛔ `LEDGER.md` §Harness: *an absent answer and an unanswered question
    are different results.* A caller sorting candidates on a fabricated 0.0
    ranks *"nothing to compare"* below *"a terrible match"*, which is exactly
    backwards -- the unprobed candidate might be the right one."""
    assert duration_score(None, 1416.0) is None
    assert duration_score(EPISODE, None) is None
    assert duration_score(EPISODE, 0.0) is None
    assert duration_score(float("nan"), 1416.0) is None
    assert duration_score(EPISODE, 1416.0) is not None


def test_the_score_can_separate_two_CUTS_of_one_film():
    u"""🚨 THE TRAP §3.45 SAYS THIS STEP IS THE FIX FOR. `Blade Runner (1982)
    [Final Cut]` and `[Theatrical]` share 11 of 21 slug characters -- 0.52,
    above the 0.4 threshold -- so `same_series()` matches them today.

    ⚠ AND DURATION CANNOT REJECT EITHER OF THEM. Those cuts differ by about a
    minute in 117, i.e. ~1%, which is deep inside any bound that survives the
    credits. **Ranking is the fix and rejection is not**, and this check is
    what says so in the suite rather than only in a docstring.
    """
    video = 7050.0                       # the Final Cut, 117.5 min
    right = duration_score(video, 6900.0)        # its own subtitle
    wrong = duration_score(video, 6830.0)        # the Theatrical's
    assert duration_verdict(video, 6830.0)[0] == PLAUSIBLE
    assert right > wrong, (right, wrong)
    assert right - wrong > 0.01, (
        "a 1% runtime difference must survive into the ordering", right, wrong)


def test_the_score_does_not_TIE_two_candidates_a_second_apart():
    u"""⭐ THE RESOLUTION CLAIM, AT ITS NARROWEST WITNESS.

    ⚠ The `[Final Cut]` check above could not feel a mutation rounding the
    score to two decimals, because its own two cuts differ by 3% of runtime
    and survive rounding easily. `doctrine/verification`: **give each mutant
    the narrowest witness that can see it**, or the check becomes the mutant's
    alibi.

    A tie is not a small error here -- `06-edge-cases.md` §4 says several
    valid subtitles for one video are ranked and all but one are trashed, so
    two candidates scoring equal means an arbitrary file is kept and the
    others deleted.
    """
    exact = duration_score(7050.0, 7050.0)
    one_second_off = duration_score(7050.0, 7049.0)
    assert exact > one_second_off, (exact, one_second_off)
    assert exact != one_second_off


def test_the_score_penalises_running_LONG_harder_than_running_SHORT():
    u"""⛔ THE ASYMMETRY, PINNED. Collapsing the two scales into one is the
    obvious tidy-up and the suite must feel it.

    ⭐ The argument, which is written at the constant because it is NOT a
    measurement: of the nine pairs measured against a REAL video duration,
    `last cue / duration` ran 0.931-0.998 and **not one exceeded 1.000**.
    Running short has a benign mechanism -- the credits, an ED nobody
    captioned. Running long has none except a file defect or an OP shift.
    """
    assert SCORE_LONG_SCALE < SCORE_SHORT_SCALE
    short = duration_score(EPISODE, EPISODE * 0.95)
    long_ = duration_score(EPISODE, EPISODE * 1.05)
    assert long_ < short, (long_, short)


def test_the_score_is_monotone_away_from_a_perfect_match():
    u"""A ranking signal that is not monotone is not a ranking signal. Both
    directions, because a score built from `min/max` would pass a one-sided
    check while being blind to the asymmetry above."""
    assert duration_score(EPISODE, EPISODE) == 1.0
    below = [duration_score(EPISODE, EPISODE * r)
             for r in (1.00, 0.99, 0.95, 0.90, 0.50, 0.10)]
    above = [duration_score(EPISODE, EPISODE * r)
             for r in (1.00, 1.01, 1.05, 1.10, 1.50, 2.00)]
    for series in (below, above):
        assert series == sorted(series, reverse=True), series
        assert all(0.0 < s <= 1.0 for s in series), series


def test_the_score_is_scale_free():
    u"""⚠ The same relative disagreement must score the same on a 24-minute
    episode and a 3-hour film. A score built on absolute seconds would rank
    every film pair as a near-miss and every episode pair as a disaster."""
    a = duration_score(EPISODE, EPISODE * 1.02)
    b = duration_score(FILM, FILM * 1.02)
    assert abs(a - b) < 1e-9, (a, b)


# ==========================================================================
# 🚨 content_end -- the last cue is not a robust statistic
# ==========================================================================

def test_an_orphaned_trailing_cue_does_not_set_the_runtime():
    u"""🚨 MEASURED ON THE REAL CORPUS. `Gintama - 074.ass` carries 429 cues
    whose body ends at ~1,475 s and **one cue at 3,616.9 s** -- a 2,141.6 s
    gap. Read raw, that perfectly good 24-minute episode's subtitle is 2.5x
    its video and gets rejected.

    Over 1,495 real files the final gap runs median 2.79 s but reaches
    2,141.58 s, and `last / p99(starts)` reaches **9.18x**.
    """
    body = [10.0 * i for i in range(1, 148)]      # ends at 1470 s
    poisoned = body + [3616.9]
    assert content_end(poisoned) == pytest.approx(1470.0)
    assert duration_verdict(EPISODE, content_end(poisoned),
                            len(poisoned))[0] == PLAUSIBLE
    # ⚠ THE POSITIVE CONTROL FOR THE CHECK, IN THE SAME CHECK. Without it,
    # `content_end` returning a constant would pass the line above.
    # `LEDGER.md`: the zlib check passed with `_read` replaced by
    # `lambda t: None`, so it could not tell "handled" from "does not work".
    assert duration_verdict(EPISODE, max(poisoned),
                            len(poisoned))[0] == IMPOSSIBLE


def test_a_normal_ending_is_returned_unchanged():
    u"""⭐ It walks back over ORPHANS ONLY. On a normal file it must return
    the real last cue, to the millisecond.

    ⚠ Including an ED card 79 s after the last line -- the measured p90 of
    the final gap is 78.79 s and every one of those is legitimate. A trim
    aggressive enough to be safe on 0.67% of files would be wrong on the
    other 99.33%.
    """
    body = [10.0 * i for i in range(1, 140)]
    assert content_end(body) == pytest.approx(1390.0)
    assert content_end(body + [1390.0 + 78.79]) == pytest.approx(1468.79)
    assert content_end(body + [1390.0 + ORPHAN_GAP - 1.0]) == \
        pytest.approx(1390.0 + ORPHAN_GAP - 1.0)


def test_content_end_walks_back_over_several_orphans():
    u"""⚠ One walk-back is not the rule. A batch artefact can leave more than
    one stray cue, and stopping after the first leaves a number just as wrong
    as the one it replaced."""
    body = [10.0 * i for i in range(1, 100)]      # ends at 990 s
    assert content_end(body + [5000.0, 9000.0]) == pytest.approx(990.0)


def test_content_end_sorts_and_survives_junk():
    u"""Cues out of order in the file are normal -- `06-edge-cases.md` §5.1
    says they are sorted on parse. ⚠ And a NaN in the list must not become
    the answer, nor make the whole call fail.

    🚨 THE NaN GOES LAST, AND THE FIRST VERSION PUT IT IN THE MIDDLE, WHERE IT
    PROVED NOTHING. Every comparison against NaN is False, so `sorted()`
    leaves it roughly where it was -- `[100, nan, 200]` sorts to
    `[100, nan, 200]` and the last element is a good number either way. **The
    check passed with the non-finite filter deleted.** Only a NaN that would
    BE the answer can see that filter. `LEDGER-HOT.md`: an ASCII fixture
    cannot test an encoding rule, bitten twice -- the same shape, a fixture
    that does not contain the thing under test.
    """
    assert content_end([300.0, 100.0, 200.0]) == pytest.approx(300.0)
    assert content_end([100.0, 200.0, float("nan")]) == pytest.approx(200.0)
    assert content_end([float("nan")]) is None
    assert content_end([float("inf")]) is None
    assert content_end([100.0, float("inf")]) == pytest.approx(100.0)
    assert content_end([0.0]) is None
    assert content_end("not a list of numbers") is None


def test_content_end_and_the_verdict_agree_on_a_thin_track():
    u"""⭐ THE TWO GUARDS ARE INDEPENDENT AND BOTH ARE NEEDED, which probe
    A9/3 established by predicting the opposite and being wrong: it expected
    trailing outliers to dominate the long side's false rejections and
    measured **0 of 16**.

    A 3-cue signs track with an orphan is caught by the cue floor whatever
    `content_end` says; a 400-cue dialogue track with an orphan is caught by
    `content_end` and nothing else.
    """
    thin = [12.0, 40.0, 5000.0]
    assert duration_verdict(EPISODE, max(thin), len(thin))[0] == UNKNOWN
    fat = [10.0 * i for i in range(1, 141)] + [5000.0]
    assert duration_verdict(EPISODE, max(fat), len(fat))[0] == IMPOSSIBLE
    assert duration_verdict(EPISODE, content_end(fat),
                            len(fat))[0] == PLAUSIBLE


# ==========================================================================
# it never raises
# ==========================================================================

@pytest.mark.parametrize("bad", [
    None, u"", u"abc", [], {}, object(), float("nan"), float("-inf"), -5,
])
def test_never_raises_on_junk(bad):
    u"""⭐ `00-INDEX.md` Rule 1: duration is an ACCELERATOR, never a
    dependency. A caller whose container probe returned something strange must
    still get a pairing run, not a traceback.

    🚨 `LEDGER.md`: `zlib.error` derives straight from `Exception`, so a catch
    of `(IOError, OSError, ValueError, EOFError)` did not fail open on a
    corrupt cache -- it **crashed the caller**, making the module's own
    "accelerator, never a dependency" claim false for the commonest kind of
    file damage there is.
    """
    assert duration_verdict(bad, 1416.0)[0] in (UNKNOWN, PLAUSIBLE, IMPOSSIBLE)
    assert duration_verdict(EPISODE, bad)[0] in (UNKNOWN, PLAUSIBLE,
                                                 IMPOSSIBLE)
    assert duration_verdict(EPISODE, 1416.0, bad)[0] in (UNKNOWN, PLAUSIBLE,
                                                         IMPOSSIBLE)
    assert duration_score(bad, 1416.0) is None or \
        isinstance(duration_score(bad, 1416.0), float)


def test_an_infinite_cue_count_does_not_crash_the_pairer():
    u"""🚨 A REAL DEFECT, FOUND BY THE PARAMETRISED JUNK CHECK ON THIS SUITE'S
    FIRST RUN, AND KEPT AS ITS OWN NAMED CASE.

    `int(float("-inf"))` raises **OverflowError**, which derives from
    `ArithmeticError` and matches neither `TypeError` nor `ValueError` -- so
    the first `try/except (TypeError, ValueError)` around the cue count did
    not fail open on it, it **crashed the caller**.

    ⛔ That is `zlib.error` again, in a new module, the same day.
    `LEDGER.md`: a catch of `(IOError, OSError, ValueError, EOFError)` did not
    fail open on a corrupt gzip -- it took `same_series()` down with it on 307
    of 400 single-byte flips, making *"an accelerator, never a dependency"*
    false for the commonest kind of file damage there is.
    """
    for junk in (float("-inf"), float("inf"), float("nan"), 10 ** 400):
        v, _r = duration_verdict(EPISODE, 7100.0, junk)
        assert v in (UNKNOWN, IMPOSSIBLE), junk


def test_the_measured_populations_are_reproduced_as_cases():
    u"""⭐ THE REAL NUMBERS, AS A REGRESSION. Nine `(video duration, last
    cue)` pairs measured against real durations -- ffprobe's own
    `format.duration` for three, the yomi18 ground-truth set for five, and
    our own container reader for `Sintel-60s.mkv`. **Every one must pair.**

    ⚠ `LEDGER.md`: a gate's fixtures cannot be the defect it exists to
    outlive -- so these are not fixtures for the detector, they are the
    measurement itself, pinned so that a later tightening has to argue with
    real files rather than with a docstring.
    """
    measured = [
        (1460.01, 1454.97, u"Gintama - 201, ffprobe"),
        (1420.06, 1416.54, u"[SubsPlease] 86 - Eighty Six - 03v2, ffprobe"),
        (1430.91, 1420.75, u"[SubsPlease] One Piece - 1121, ffprobe"),
        (1420.00, 1417.01, u"yomi18 the video's own track"),
        (1420.00, 1415.21, u"yomi18 ABEMA streaming, uncut"),
        (1420.00, 1416.12, u"yomi18 Netflix streaming, uncut"),
        (1420.00, 1321.95, u"yomi18 NanakoRaws AT-X broadcast, CUT"),
        (1420.00, 1355.19, u"yomi18 shincaps AT-X broadcast, CUT"),
        (60.02, 56.70, u"Sintel-60s.mkv, our own container reader"),
    ]
    for video, last, label in measured:
        assert verdict(video, last, 400) == PLAUSIBLE, label
        assert 0.93 <= last / video <= 1.0, (label, last / video)
    # ⚠ THE ASYMMETRY'S ONLY HONEST SOURCE: not one of them exceeded 1.000.
    assert max(last / video for video, last, _ in measured) < 1.0


def test_the_wrong_episode_control_is_NOT_caught_by_duration():
    u"""⚠ AND THE HONEST LIMIT OF THIS STEP, AS A CHECK.

    `yomi18/wrong-episode.s01e15.srt` is the corpus's own wrong-episode
    control and its last cue is 1,321.99 s against the same 1,420 s video --
    `cue/D` **0.9310**, indistinguishable from the correct AT-X broadcast file
    at 0.9310. **Duration cannot see it, and must not pretend to.**

    ⭐ `align()` refuses it at 1.36x chance, which is the stage that owns that
    question. A duration check tuned until it caught this one would be tuned
    to reject the correct file beside it -- which is `LEDGER.md`'s *never
    loosen a guard to make a cut detectable*, pointing the other way.
    """
    assert verdict(1420.0, 1321.99, 400) == PLAUSIBLE
    assert verdict(1420.0, 1321.95, 400) == PLAUSIBLE
    assert duration_score(1420.0, 1321.99) == \
        pytest.approx(duration_score(1420.0, 1321.95), abs=1e-3)


def test_a_finite_score_never_reaches_zero_or_exceeds_one():
    u"""⚠ A ranking score that can hit 0.0 collides with the *absent* answer
    the module deliberately returns as None, and one that can exceed 1.0
    breaks any caller combining it with the other signals in
    `06-edge-cases.md` §3.4 (name, episode, proximity), all of which are
    0.0-1.0."""
    for ratio in (0.001, 0.056, 0.5, 1.0, 2.0, 100.0):
        s = duration_score(EPISODE, EPISODE * ratio)
        assert 0.0 < s <= 1.0, (ratio, s)
        assert math.isfinite(s)
