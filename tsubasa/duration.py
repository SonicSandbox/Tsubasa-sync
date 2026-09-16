# -*- coding: utf-8 -*-
u"""
Runtime as a pairing signal: could this subtitle belong to this video at all?
RUNBOOK step A9. `spec/06-edge-cases.md` §3.45, §3.5, §5.1.

⭐ SONIC'S OBSERVATION, WHICH IS THE WHOLE IDEA: *"you won't have a movie that
is 1 hour long and subs that are 1 hour 30 minutes."* It is free -- the
container is probed anyway and the subtitle's cue times are parsed anyway --
and it rejects before any timing work happens.

    from tsubasa.duration import duration_verdict, duration_score, content_end

    verdict, reason = duration_verdict(video_seconds, subtitle_end, n_cues)
    score           = duration_score(video_seconds, subtitle_end)   # RANKING
    subtitle_end    = content_end(cue_start_times)                  # optional

⚠ PURE. It takes numbers, opens nothing, and knows nothing about files. That
is what lets the whole suite run with no media present.

===========================================================================
🚨 THE ASYMMETRY, AND IT IS NOT THE ONE THE SPEC PROPOSED
===========================================================================

`06-edge-cases.md` §3.45 proposes: *"Reject only when the subtitle is LONGER
than the video by a real margin, or shorter by more than ~15%."* The `~15%`
is the only number in that section and it carries no population, so RUNBOOK A9
measured it (`_work/probe_a9_duration.py`, `_lastcue.py`, `_longbound.py`).

⛔ **IT IS THE WRONG SIGN OF TRADE AND THE SHORT-SIDE REJECTION IS NOT BUILT.**

| A `shorter than 0.85 -> reject` rule | measured |
| --- | --- |
| correct same-video pairs it DESTROYS | **7 of 280 (2.5%)** |
| correct cross-release pairs it DESTROYS | **10 of 399 (2.5%)** |
| wrong-EPISODE candidates it catches | **7 of 399 (1.8%)** |
| wrong-SHOW candidates it catches | 48 of 400 (12.0%) |

The candidate index keys on `(season, episode)`, so the population this filter
actually meets is the wrong-EPISODE one -- where **it destroys more right
answers than it catches wrong ones.** And the two errors are not symmetric:
a destroyed pair is silent, while a surviving wrong pair is refused downstream
by `align()` at 1.3-1.9x chance. `spec/00-INDEX.md` Rule 2.

⚠ A CUE-COUNT FLOOR DOES NOT RESCUE IT. **14 of the 17** correct pairs it
destroys carry >= 40 cues -- they are real dialogue tracks, not fragments.
They are `One Pace` re-cuts, a 2-episode batch file, and a compilation film
against its TV episode.

⭐ And two other parts of the pack say the same thing independently:

* §5.1 requires *"Sub covers only part of the video (TV sub on a BD) -- aligns
  the covered stretch; buckets outside it are excluded, not failed"*;
* `tests/test_pairing.py::test_a_subtitle_that_stops_before_the_credits_is_still_accepted`
  is a **shipped green check** asserting that 900 s against 1420 s (0.634) is
  accepted. A 15% bound breaks it.

**The lowest ratio measured between two CORRECT subtitles of one video is
0.056** -- a 22-cue signs track against a 259-cue dialogue track. Below that
nothing is measured at all, so the conservative side is: *shortness never
rejects.* ⭐ It moves the SCORE instead, which is §3.45's third use and the one
the evidence supports.

===========================================================================
🚨 AND THE LAST CUE IS NOT A ROBUST STATISTIC
===========================================================================

A long-side rejection reads ONE number off the end of a file. Measured over
1,495 real corpus subtitles (`probe_a9_lastcue.py`), the gap between the last
cue and the one before it runs **median 2.79 s, p99 187.6 s, max 2,141.6 s** --
so on **1.94%** of real files the last cue sits more than two minutes past the
rest of its own file, and `last / p99(starts)` reaches **9.18x**.

⭐ That is a machine for confident wrong answers, and it is why `LONG_RATIO`
sits where it does and why `content_end` exists.

===========================================================================
WHAT THIS CANNOT DO -- 🚨 including the thing §3.45 says it is FOR
===========================================================================

§3.45 offers duration as *"the fix for that trap"* -- `[Final Cut]` against
`[Theatrical]`, which `same_series()` matches at 0.52. ⚠ **Not as a
rejection.** Blade Runner's cuts differ by about a minute in ~117, i.e. ~1%,
which is deep inside any bound that survives the credits. **Ranking is the
fix; rejection is not**, and `duration_score` is built with enough resolution
near 1.0 to order them. A cut that differs by 17% -- an extended edition --
still must NOT be rejected, because §3.5 says a theatrical subtitle on an
extended video is a multi-break alignment, not a wrong pair.
"""

#: The three outcomes. ⭐ Never a bare boolean -- `naming/series.py` and the
#: verdict band in `05-interface.md` are the same shape, for the same reason:
#: *impossible*, *plausible* and *cannot tell* are three different answers,
#: and forcing them into two manufactures a confident wrong one.
IMPOSSIBLE = u"impossible"
PLAUSIBLE = u"plausible"
UNKNOWN = u"unknown"

#: How much longer than the video a subtitle may run before the pair is
#: impossible. ⭐ MEASURED, over 1,138 correct and 1,564 wrong directed pairs
#: with a full dialogue track (>= 100 cues) on both sides:
#:
#:     bound   correct rejected      wrong rejected
#:     1.05     76 (6.68%)           229 (14.64%)
#:     1.10     22 (1.93%)            82 ( 5.24%)
#:     1.25     11 (0.97%)            46 ( 2.94%)
#:     1.50      6 (0.53%)            41 ( 2.62%)
#:
#: ⚠ THE BAND IS NOT EMPTY, and saying so is the point -- every other
#: threshold in this pack sits in a measured empty band and this one does not.
#: All 16 correct-side rejections at 1.25 were inspected one by one: every one
#: is a genuine runtime mismatch the corpus mislabelled as *same episode,
#: different release* -- a 55-minute special (`Dr. Stone: Ryuusui`, 3,285 s), a
#: two-episode batch file (`Gintama - 016`, 3,344 s), a compilation film
#: (`Kimetsu no Yaiba`, 2,933 s) against a 24-minute episode. **They are
#: answers this check should be giving.** The residual is named, not rounded.
#:
#: 🚨 THE FLOOR UNDER IT IS THE TRAILING-OUTLIER REACH, not the pair data. A
#: bound is exceeded by a subtitle's own stray final cue -- no video involved
#: -- on 21.14% of real files at 1.05, 2.74% at 1.10, 0.67% at 1.15 and
#: **0.27% at 1.25**. ⛔ Below ~1.15 this rule fires mostly on the subtitle's
#: own junk rather than on a wrong pairing.
#:
#: ⭐ AND IT CATCHES SONIC'S OWN EXAMPLE WITH MARGIN. *"a movie that is 1 hour
#: long and subs that are 1 hour 30 minutes"* is exactly 1.50, which a bound
#: AT 1.50 does not catch -- the comparison is strict. 1.25 does.
LONG_RATIO = 1.25

#: ...and the absolute margin it must ALSO clear, seconds. ⛔ BOTH are
#: required, and collapsing them into one number is the failure this constant
#: exists to prevent.
#:
#: ⭐ MEASURED from the corpus's own offset census
#: (`CORPUS-OPPORTUNITIES.md` §3.4): real cross-release offsets group at 0,
#: +-1.0 s, **+9.5-10 s** (the broadcast sponsor-card/CM block, eight shows)
#: and **+-90 s** (with-OP against without-OP). A CORRECT subtitle can
#: therefore sit ~90 s plus a few CM blocks past a video that lacks the
#: opening -- which is precisely the case §3.45 warns about. 120 s is 90 plus
#: three CM blocks.
#:
#: ⭐ Its structural effect: for any video under 480 s the absolute margin is
#: the operative rule and the ratio can never fire alone. That is the right
#: behaviour and it is the same degradation §5.1 records for `BUCKET` on a
#: 3-minute short -- the check gets weaker on short content and says so,
#: rather than getting sharper on content that cannot support it.
LONG_ABSOLUTE = 120.0

#: Fewest cues before a subtitle's last cue may be read as a claim about
#: RUNTIME at all.
#:
#: 🚨 THE ONE-CUE HAZARD, and it is this project's most expensive statistic
#: lesson. `LEDGER-HOT.md`: a subtitle containing ONE cue scored **5.15x
#: chance** against a real reference, because the best of thousands of
#: candidate offsets always lands one cue on something. The same fragility is
#: here in a different door: a one-cue subtitle's "last cue time" is one
#: arbitrary moment, not the end of anything.
#:
#: ⭐ REUSED, NOT INVENTED. This is `align.MIN_ALIGNABLE_CUES`, the floor the
#: project already measured for *"this input can be measured at all"*.
#: `test_duration.py::test_the_cue_floor_is_the_project_s_OWN_floor` imports
#: both and asserts they agree, so the copy cannot drift.
#:
#: ⛔ It is NOT imported here. `align.objective` pulls in numpy, and A9 is the
#: filter that runs *before any timing work* -- making the cheapest check in
#: the pipeline import the aligner is backwards. The coupling lives in the
#: check, which is where a claim about two constants belongs.
MIN_CUES_FOR_A_RUNTIME_CLAIM = 5

#: Ranking only. How far short of the video a subtitle may run before
#: `duration_score` halves.
#:
#: ⭐ MEASURED twice, by two populations that agree. |sub/vid - 1| over 1,358
#: correct directed pairs: median 0.0017 · p75 0.0150 · **p90 0.0633** · p95
#: 0.0786. And against nine REAL video durations, `last cue / duration` ran
#: 0.931-0.998 -- a worst short deviation of 0.069.
SCORE_SHORT_SCALE = 0.065

#: ...and the same for running LONG. ⚠ CONSERVATIVE BY ARGUMENT, NOT
#: MEASURED, and the distinction is written here rather than left to be
#: inferred.
#:
#: There is no population to fit it to: of the nine pairs measured against a
#: real video duration, **not one exceeded 1.000**. You cannot fit a scale to
#: an absence. So it is set to half `SCORE_SHORT_SCALE`, expressing the one
#: thing the evidence does say -- running short has a benign mechanism (the
#: credits, an ED nobody captioned) and running long has none except a file
#: defect or an OP shift.
#:
#: ⛔ The asymmetry is PINNED BY A CHECK
#: (`test_the_score_penalises_running_LONG_harder_than_running_SHORT`) rather
#: than by this comment, because the obvious tidy-up is to collapse the two
#: into one scale and the suite must feel that.
SCORE_LONG_SCALE = 0.0325

#: `content_end`: a final cue further than this past the cue before it is an
#: ORPHAN, not the end of the content.
#:
#: ⭐ MEASURED over 1,495 real corpus subtitles: the final gap runs median
#: 2.79 s, p90 78.79 s, p99 187.64 s, max 2,141.58 s. The p90 is large and
#: legitimate -- an ED card or a translator credit a minute after the last
#: line is normal. 300 s is above the measured p99 and fires on **0.67%**
#: (10 of 1,495), which is the population whose last cue is 5+ minutes past
#: everything else in the file.
ORPHAN_GAP = 300.0

#: ⭐ Every constant above was fitted to a measured population, except
#: `SCORE_LONG_SCALE`, which says so at its own site. `naming/series.py`
#: carries the same flag for the same reason.
THRESHOLDS_ARE_MEASURED = True


def _seconds(value):
    """A usable positive runtime, or None. ⭐ ONE place decides that.

    🚨 `LEDGER-HOT.md`: *never conflate "parsed zero cues" with "could not
    read the file."* Shipped twice. Both arrive here as an unusable number and
    both must leave as None -- but the CALLER's reason string is what says
    which, so this returns None and never a verdict.

    ⚠ NaN is not caught by `<= 0`: every comparison against NaN is False, so
    a NaN would sail through a naive guard and then make every ratio False,
    silently reading as PLAUSIBLE. The `!= value` test is what catches it.
    """
    if value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    if value != value or value in (float("inf"), float("-inf")):
        return None
    if value <= 0.0:
        return None
    return value


def _count(value):
    """A usable cue count, or None. ⭐ ONE place decides that too.

    🚨 IT EXISTS BECAUSE THE NARROW CATCH WAS WRONG, AND IT WAS WRONG THE SAME
    WAY THIS PROJECT HAS ALREADY BEEN BITTEN. `int(float("-inf"))` raises
    **OverflowError**, which derives from `ArithmeticError` and matches
    neither `TypeError` nor `ValueError` -- so a `try/except (TypeError,
    ValueError)` did not fail open on it, it **crashed the caller**. That is
    `zlib.error` exactly: `LEDGER.md` records a catch of `(IOError, OSError,
    ValueError, EOFError)` that missed a corrupt-gzip failure on 307 of 400
    single-byte flips and took `same_series()` down with it.

    ⚠ Found by `test_never_raises_on_junk[-inf]` on the suite's first run,
    which is the parametrised-junk check earning its place rather than
    decorating the file.

    ⭐ `except Exception` is right here and the reason goes at the site: every
    way of failing to turn a caller's value into a count means the same thing
    -- we do not know how many cues there are, and 00-INDEX Rule 1 says this
    module is an accelerator that must degrade rather than raise.

    ⚠ AND THE TWO GUARDS ARE INDIVIDUALLY UNKILLABLE, WHICH IS WRITTEN DOWN
    HERE SO NOBODY CITES A GREEN SUITE AS PERMISSION TO DROP ONE. The
    non-finite test stops `-inf` ever reaching `int()`, and the broad catch
    would swallow it if it did -- so a mutation removing either one alone
    SURVIVES. The mutant that kills removes **both**, which is the honest
    statement of the claim. Same footing as the container reader's two
    unreachable position-advance guards (`LEDGER.md` §Logic): they cost
    nothing, and the day someone changes the other one is the day this stops
    being free.
    """
    if value is None or isinstance(value, bool):
        return None
    try:
        if value != value or value in (float("inf"), float("-inf")):
            return None
        return int(value)
    except Exception:                                      # noqa: BLE001
        return None


def duration_verdict(video_seconds, subtitle_last_cue_seconds,
                     subtitle_cues=None,
                     long_ratio=None, long_absolute=None):
    u"""(verdict, reason). Three outcomes, never a bare boolean.

    `video_seconds`
        The container's runtime. `container.read(path, timing=False)` returns
        it from the header alone, without opening a cluster.
    `subtitle_last_cue_seconds`
        Where the subtitle's content ends. ⭐ Prefer `content_end(starts)` --
        the raw last cue is an outlier on 1.94% of real files.
    `subtitle_cues`
        How many cues the subtitle has, if known. Below
        `MIN_CUES_FOR_A_RUNTIME_CLAIM` the answer is UNKNOWN, because one
        cue's timestamp is a moment and not a runtime.

    ⭐ IMPOSSIBLE IS THE LONG SIDE ONLY, and the ratio and the absolute margin
    are BOTH required. See the module docstring: a short-side rejection was
    measured and destroys more correct pairs than it catches wrong ones.

    ⛔ An absent duration is UNKNOWN, never a rejection. `LEDGER.md` §Harness
    records the general shape -- a failed network request scored as a measured
    zero, and *"Wikidata has no alias"* became indistinguishable from *"I
    never got an answer"*. An absent answer and an unanswered question are
    different results.
    """
    long_ratio = LONG_RATIO if long_ratio is None else long_ratio
    long_absolute = LONG_ABSOLUTE if long_absolute is None else long_absolute

    video = _seconds(video_seconds)
    subtitle = _seconds(subtitle_last_cue_seconds)

    # ⚠ Named separately on purpose. A message that says what it FOUND is
    # `doctrine/robustness`'s rule, and *"no runtime for the video"* and *"no
    # cue times for the subtitle"* send the reader to different places.
    if video is None and subtitle is None:
        return (UNKNOWN, u"neither runtime is known -- the video was not "
                         u"probed and the subtitle has no usable cue times")
    if video is None:
        return (UNKNOWN, u"the video's runtime is not known, so its subtitle "
                         u"cannot be too long for it")
    if subtitle is None:
        return (UNKNOWN, u"the subtitle has no usable end time, so it cannot "
                         u"be compared with the video's %.0f s" % video)

    if subtitle_cues is not None:
        n = _count(subtitle_cues)
        if n is not None and n < MIN_CUES_FOR_A_RUNTIME_CLAIM:
            # 🚨 Not a rejection. A thin subtitle is refused downstream by
            # `align()`'s own floor with a better reason than this one could
            # give, and answering IMPOSSIBLE here would be a confident verdict
            # built from a single timestamp.
            return (UNKNOWN,
                    u"%d cue%s cannot say how long a subtitle is -- the last "
                    u"one is a moment, not a runtime (fewer than %d)"
                    % (n, u"" if n == 1 else u"s",
                       MIN_CUES_FOR_A_RUNTIME_CLAIM))

    # ⚠ AN `over > 0` TERM STOOD HERE AND WAS DELETED ON MEASUREMENT, WHICH IS
    # the part to copy. A mutant replacing `over` with `abs(over)` SURVIVED the
    # suite -- and the reason was not a weak check: `subtitle > video *
    # long_ratio` with `long_ratio > 1` already implies `subtitle > video`, so
    # the sign test could never fire. ⭐ `LEDGER.md` §Logic has the same
    # sequence for the title gate's full-width fold: *dead guard, live check.*
    # The guard went and the mutant with it; the mutant that replaced it
    # attacks the comparison that is actually load-bearing.
    over = subtitle - video
    if subtitle > video * long_ratio and over > long_absolute:
        return (IMPOSSIBLE,
                u"the subtitle runs to %.0f s but the video is only %.0f s -- "
                u"%.0f s longer (%.2fx), past both the %.2fx and the %.0f s "
                u"margins" % (subtitle, video, over, subtitle / video,
                              long_ratio, long_absolute))

    # ⭐ EVERYTHING ELSE IS PLAUSIBLE, INCLUDING VERY SHORT. §5.1: a subtitle
    # covering only part of the video aligns its covered stretch. The measured
    # floor for a CORRECT same-video pair is 0.056, and below that nothing has
    # been measured -- so nothing is rejected.
    return (PLAUSIBLE, u"")


def duration_score(video_seconds, subtitle_last_cue_seconds):
    u"""How well two runtimes agree, in (0, 1]. **None when unknown.**

    ⭐ For RANKING candidates -- §3.45's third use, and the only one the
    `[Final Cut]` / `[Theatrical]` trap can actually be settled by. Those cuts
    differ by ~1% of runtime, so a rejection can never separate them and an
    ordering can.

    ⛔ RETURNS None, NEVER 0.0, WHEN EITHER SIDE IS UNKNOWN. `LEDGER.md`
    §Harness: a failed request scored as a measured zero made a probe report
    three different answers to the same question, and the coverage figure fell
    *smoothly and plausibly* with nothing on screen to say the instrument had
    changed. A caller sorting on this must be able to see the difference
    between *"a poor match"* and *"nothing to compare"*.

    ⚠ MONOTONE AND SCALE-FREE: it reads the relative difference, so a 1%
    disagreement scores the same on a 24-minute episode and a 3-hour film,
    and no rounding flattens the region near 1.0 where cuts live.
    """
    video = _seconds(video_seconds)
    subtitle = _seconds(subtitle_last_cue_seconds)
    if video is None or subtitle is None:
        return None

    d = (subtitle - video) / video
    scale = SCORE_LONG_SCALE if d > 0 else SCORE_SHORT_SCALE
    return 1.0 / (1.0 + abs(d) / scale)


def content_end(cue_starts, orphan_gap=None):
    u"""Where a subtitle's content actually ends. -> seconds, or None.

    🚨 THE LAST CUE IS NOT A ROBUST STATISTIC, AND THIS IS THE INSURANCE.
    Measured over 1,495 real corpus subtitles: the gap between the final cue
    and the one before it runs median 2.79 s but reaches **2,141.58 s**, and
    `last / p99(starts)` reaches **9.18x**. One stray trailing cue -- a
    translator credit parked far past the end, a batch-file artefact -- makes
    a perfectly good subtitle look impossible for its video.

    ⭐ It walks back over ORPHANS ONLY, so on a normal file it returns the
    real last cue unchanged. It is not a percentile: a percentile discards
    the last 1% of every legitimate tail to insure against 0.67% of files,
    which is the wrong trade in the other direction.

    ⚠ AND IT IS NOT ENOUGH ON ITS OWN, which is why `LONG_RATIO` also sits
    above the outlier reach. Probe A9/3 predicted trailing outliers would
    dominate the long side's false rejections and measured **0 of 16** -- the
    two hazards are independent and each needs its own guard.
    """
    orphan_gap = ORPHAN_GAP if orphan_gap is None else orphan_gap
    if cue_starts is None:
        return None
    try:
        xs = sorted(float(t) for t in cue_starts)
    except (TypeError, ValueError):
        return None
    xs = [x for x in xs if x == x and x not in (float("inf"), float("-inf"))]
    if not xs:
        # ⚠ Zero cues is not zero seconds. `LEDGER-HOT.md`: never conflate
        # "parsed zero cues" with "could not read the file" -- both are the
        # absence of an answer and neither is the number 0.
        return None

    i = len(xs) - 1
    while i > 0 and (xs[i] - xs[i - 1]) > orphan_gap:
        i -= 1
    return xs[i] if xs[i] > 0 else None
