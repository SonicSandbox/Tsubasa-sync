# -*- coding: utf-8 -*-
u"""
The verdict: whether to write, and what to tell a person. RUNBOOK step B8.

Authority: `12-alignment.md` §4 (the band, computed from the same pass),
`05-interface.md` (the confidence words and the output contract),
`03-permissions.md` (the three outcomes and the hand-back path).

===========================================================================
⭐ THIS MODULE IS WHERE "IT FAILED" BECOMES SOMETHING A PERSON CAN ACT ON.
===========================================================================

`align()` answers *how far off is this, and does the answer hold*. It does not
answer *should we write it* or *what do I tell someone who wanted this to
work*. Those are one decision and one sentence, and they are here so there is
exactly ONE writer of both -- `doctrine/architecture` rule 4. `explicit.py`
says the same thing from the other side: *"`decide()` consumes a verdict that
already carries one ... the band rule belongs to the verdict, not to its
consumer."*

---------------------------------------------------------------------------
🚨 THREE THINGS THIS MODULE EXISTS TO PREVENT, ALL MEASURED
---------------------------------------------------------------------------

1. **A single threshold.** `LEDGER.md` §Logic, escalated 2026-09-07 on the
   first non-Japanese data: correct English cross-platform pairs score
   **1.70-2.12x** while wrong anime pairs score **1.37-1.95x**. A correct pair
   scores BELOW a wrong one. 57 of 364 measured cross-platform pairs (16%) sit
   under 2.5x while being correct. ⛔ No single number separates them, so the
   escalation band is STRUCTURAL and its second signal is not optional.

2. **Conflating REFUSED with ERROR.** `03-permissions.md`: *"REFUSED and ERROR
   are different and must never be conflated"* -- `subsync` shipped that
   confusion twice and both times a real failure disguised itself as a
   different one. REFUSED means *measured, and not good enough*. ERROR means
   *not measured at all*, so there is no offset to stand behind and `--force`
   does not apply.

3. **A high score over a stretch that is wrong.** A whole-file rate is
   dominated by the larger segment, so a file can score beautifully and be
   confidently mis-timed for its opening minutes -- four did, and the mistake
   was then repeated on a second folder. `holds_throughout` outranks the
   score, in that order, always.

---------------------------------------------------------------------------
⛔ WHAT THIS MODULE DELIBERATELY DOES NOT DO
---------------------------------------------------------------------------

- **It does not re-check duration.** `duration_verdict` is a PAIRING filter and
  `discover.Candidates` already applied it; by the time a `Fit` exists the pair
  has passed it. A second call site for a filter that already ran is the
  *"two resolvers, not one bug"* shape in `doctrine/architecture`.
- **It does not write, rename or trash.** That is RUNBOOK 3a.
- **It does not format the CLI line.** It returns the pieces; 3c arranges them.
"""
import math

from .align import MIN_ALIGNABLE_CUES, bucket_noise_floor
from .arbitrate import ACCEPT_AT, REFUSE_BELOW
from .arbitrate import verdict as band_of

# ---------------------------------------------------------------------------
# the outcome vocabulary
# ---------------------------------------------------------------------------
# ⚠ `05-interface.md`'s three names, and this is their ONE definition.
# `explicit.py` imports them from here rather than declaring its own: the
# escape hatch CONSUMES a verdict, so the vocabulary belongs to the verdict.
# Two copies of an enumeration is the drift `doctrine/architecture` rule 4
# describes, and the names reaching `decide()` must be the same objects the
# verdict minted or the gate is comparing strings by luck.

CONFIDENT = u"CONFIDENT"
REFUSED = u"REFUSED"
ERROR = u"ERROR"

OUTCOMES = frozenset((CONFIDENT, REFUSED, ERROR))


# ---------------------------------------------------------------------------
# what the reference was made of
# ---------------------------------------------------------------------------
# 🚨 The verdict depends on it. Correct UNCUT pairs measured **2.42-2.77x** on
# a speech mask (`12-alignment.md` §5) -- straddling the 2.5 cue-vs-cue accept
# line -- while the two real broadcast cuts sat at 1.94x and a wrong episode at
# 1.36x. Probe F's band was 1.42-2.63x. On a mask the matched rate is ~0.3-0.5
# even when correct, so every margin calibrated on 60-95% cue-vs-cue rates is
# out of reach.

TEXT_TRACK = u"text track"
BITMAP_TRACK = u"bitmap track"
SPEECH_MASK = u"speech mask"

REFERENCE_KINDS = frozenset((TEXT_TRACK, BITMAP_TRACK, SPEECH_MASK))

#: ⛔ UNFITTED, AND STRUCTURALLY SO. `12-alignment.md` §5.2: *"The mask-path
#: thresholds are fitted separately, with negative controls, before any mask
#: verdict ships (RUNBOOK B6)."*
#:
#: ⭐ It is `None` rather than a comment saying *"fit these at B6"* because
#: `doctrine/robustness`: **a rule that relies on remembering will be
#: forgotten.** A borrowed 2.5 would refuse the 2.42x uncut pair that this
#: project measured as CORRECT, and it would do it silently. When B6 fits the
#: band this becomes `(refuse_below, accept_at)` and `MaskBandNotFitted`
#: becomes unreachable -- that is the whole change.
MASK_BAND = None

#: A bitmap track's ON-times are cue moments like any other -- the container
#: block timestamps that produced them know nothing about the codec -- so the
#: cue-vs-cue band applies unchanged. `06-edge-cases.md` §6.1: PGS and VobSub
#: are *"free extra reference material"*, not a different measurement.
_CUE_KINDS = frozenset((TEXT_TRACK, BITMAP_TRACK))


# ---------------------------------------------------------------------------
# the confidence words
# ---------------------------------------------------------------------------
# `05-interface.md`: Sonic ruled `96% match · [VERDICT]`. The percentage is the
# human-readable number; the word carries the chance-adjusted judgement the
# percentage alone cannot.
#
# 🚨 SPEC DEFECT, RECORDED NOT DECIDED (Part 1). `05-interface.md`'s word table
# still reads *"uncertain 2.0-2.5x"* and *"refused below 2.0x"*. That predates
# the 2026-09-07 escalation recorded three paragraphs below it in the same
# file, which widened the band to **1.5-2.5 escalate / < 1.5 refuse** -- and
# `12-alignment.md` §4, the build authority for Track B, cites the wide band.
# Built to the wide band; the stale rows are amended in the spec.
#
# 🚨 `certain` WAS THE TOP WORD AND WAS RULED OUT ON 2026-09-09. It is a
# SUBSTRING of `uncertain` — the word printed on the weakest thing this tool
# writes contained the word printed on the strongest, which re-arms
# `LEDGER.md` §Interface's defect (a GUI painted a run green because
# *"11 confident, 1 refused"* matched a bare word) for any consumer that
# substring-matches. Found by an adversarial pass; Sonic ruled the swap.
#
# ⭐ `locked` is his own word for the outcome — *"every part of the episode
# locks in well"* (`12-alignment.md`, the objective in his words) — and the
# four words are now mutually non-substring, which
# `test_the_confidence_vocabulary_is_mutually_NON_SUBSTRING` enforces so the
# next word added cannot quietly reintroduce this.
_WORDS = ((4.0, u"locked"), (3.0, u"strong"), (ACCEPT_AT, u"fair"))

#: ⭐ THE CLOSED VOCABULARY, derived from `_WORDS` rather than restated beside
#: it. `05-interface.md` rules these four and
#: `test_the_confidence_vocabulary_is_mutually_NON_SUBSTRING` keeps them apart;
#: `api.Result` validates against this set, because it has a public constructor
#: and `Result(CONFIDENT, verdict_word="REFUSED")` was constructible.
#: ⚠ A second hand-written tuple here would be the two-copies-of-an-enumeration
#: drift `doctrine/architecture` rule 4 describes, on the very vocabulary this
#: module exists to keep straight.
CONFIDENCE_WORDS = frozenset([w for _floor, w in _WORDS] + [u"uncertain"])

#: What a pair lifted out of the escalation band by a second signal is called.
#: ⚠ It is written, and it is NOT called "fair" -- the evidence that carried it
#: is a cluster's agreement, not its own score.
LIFTED_WORD = u"uncertain"


class MaskBandNotFitted(RuntimeError):
    u"""A mask verdict was asked for before RUNBOOK B6 fitted its constants.

    🚨 A TOOLING FAULT, NOT A PRODUCT REFUSAL, and it is loud on purpose.
    `doctrine/robustness`: *"a guard that announces a harness/tooling fault is
    never caught, never suppressed, never made non-fatal."* Refusing quietly
    here would ship a tool that says no to every VAD pair and looks like it is
    working correctly.
    """


class Verdict(object):
    u"""One pair's outcome, the evidence for it, and the sentence a person reads.

    ⭐ This is the object `ExplicitPair.decide()` consumes. It carries an
    `outcome` and a `reason` and **no write flag** -- for the same reason A11
    gives: nothing here may be read INSTEAD of asking.
    """

    __slots__ = ("outcome", "reason", "word", "match_rate", "excess",
                 "raw_excess", "band", "reference_kind", "segments",
                 "holds_throughout", "runtime_check", "failing", "lifted_by")

    def __init__(self, outcome, reason, word=None, match_rate=0.0, excess=0.0,
                 raw_excess=0.0, band=None, reference_kind=TEXT_TRACK,
                 segments=(), holds_throughout=True, runtime_check=u"absent",
                 failing=(), lifted_by=None):
        if outcome not in OUTCOMES:
            raise ValueError(
                "outcome %r is not one of %s (05-interface.md). An "
                "unrecognised outcome is never treated as a success."
                % (outcome, u", ".join(sorted(OUTCOMES))))
        # 🚨 `03-permissions.md` §hand-back: *`reason` is never empty on a
        # non-confident outcome*. Structural, not remembered -- a blank refusal
        # reads as a success at every surface downstream, and `explicit.py`
        # would then have to invent one from nothing.
        if outcome != CONFIDENT and not (reason or u"").strip():
            raise ValueError(
                "a %s verdict was built with no reason. '03-permissions.md' "
                "§hand-back: every refusal states what was measured, why it "
                "fell short, and what would change it. \"It failed\" is not "
                "actionable and is not acceptable output." % outcome)
        # 🚨 AND NO CONFIDENCE WORD ON SOMETHING NOT WRITTEN. `verdict()` never
        # takes that route, but the CONSTRUCTOR handed it out -- and 3b's
        # `Result` and 3c's CLI line are both specified to build
        # Verdict-shaped objects. `LEDGER.md` §Interface is a GUI that painted
        # a run green off a bare word; this is the raw material for it, and a
        # comment saying *"None on anything not written"* is not a guard.
        if outcome != CONFIDENT and word:
            raise ValueError(
                "a %s verdict was built carrying the confidence word %r. A "
                "refusal has no word to print: LEDGER.md §Interface records a "
                "GUI painting a run green because \"11 confident, 1 refused\" "
                "contains `confident`." % (outcome, word))
        self.outcome = outcome
        self.reason = reason or u""
        #: ⚠ `None` on anything not written, deliberately. `LEDGER.md`
        #: §Interface: the GUI painted a run containing refusals green because
        #: *"11 confident, 1 refused"* contains the word *confident*. A
        #: confidence word on a refused pair is that bug's raw material, so a
        #: refusal has no word to print at all.
        self.word = word
        self.match_rate = match_rate
        #: ⚠ The internal decision statistic. `05-interface.md`: *never show
        #: the raw multiple in the default output* -- it belongs in
        #: `--verbose` and the JSON, because that is what a bug report needs.
        self.excess = excess
        self.raw_excess = raw_excess
        self.band = band
        self.reference_kind = reference_kind
        self.segments = list(segments)
        self.holds_throughout = holds_throughout
        #: "held" | "failed" | "weak" | "absent" -- see `_runtime_check`.
        self.runtime_check = runtime_check
        self.failing = list(failing)
        #: What lifted this out of the escalation band, if anything did.
        self.lifted_by = lifted_by

    @property
    def written(self):
        u"""⚠ Whether the verdict PERMITS a write, not whether one happened.

        The write itself is `explicit.Decision` (A11) and RUNBOOK 3a. This says
        only that the alignment cleared the band, so a caller cannot read a
        truthy field here and skip `decide()`.
        """
        return self.outcome == CONFIDENT

    @property
    def match_percent(self):
        u"""The human-readable number. `05-interface.md`: *96% match*."""
        return int(round(self.match_rate * 100.0))

    def __repr__(self):
        return "Verdict(%s%s, %d%% match, %.2fx)" % (
            self.outcome, u", " + self.word if self.word else u"",
            self.match_percent, self.excess)


# ---------------------------------------------------------------------------
# the front door
# ---------------------------------------------------------------------------

def verdict(fit, cluster=None, reference_kind=TEXT_TRACK):
    u"""Decide one pair. -> `Verdict`

    `fit`
        what `align()` returned.
    `cluster`
        the `arbitrate.Cluster` this pair sits in, when a cluster probe ran.
        ⭐ The escalation band's second signal, and the ONLY thing that can
        lift a pair out of it.
    `reference_kind`
        `TEXT_TRACK`, `BITMAP_TRACK` or `SPEECH_MASK`.

    ⛔ THE ORDER OF THESE TESTS IS LOAD-BEARING and it is not the obvious one:

        measurable?  ->  holds throughout?  ->  the band

    **Measurability first**, because an unmeasured pair has no score to put in
    a band -- `excess` is deliberately ZERO when the input is too thin, so a
    band-first reading would call a one-cue subtitle *refused* when the honest
    answer is *never measured*.

    🚨 **Then the runtime check, BEFORE the score.** A cut file scores well
    overall because the larger segment dominates, so a band-first reading
    accepts it and writes a file that is confidently wrong for its opening
    minutes. Four files in the megatest were exactly that, and the second
    reading of the same defect on another folder is what put the whole-runtime
    walk in the design.
    """
    if reference_kind not in REFERENCE_KINDS:
        raise ValueError(
            "reference_kind %r is not one of %s. The verdict depends on it: "
            "correct uncut pairs measure 2.42-2.77x on a speech mask against "
            "60-95%% cue-vs-cue rates, so a mask scored on the cue-vs-cue "
            "band is refused while being right (12-alignment.md §5)."
            % (reference_kind, u", ".join(sorted(REFERENCE_KINDS))))

    accept_at, refuse_below = _band_for(reference_kind)
    common = {
        "match_rate": float(fit.score),
        "excess": float(fit.excess),
        "raw_excess": float(fit.raw_excess),
        "reference_kind": reference_kind,
        "segments": list(fit.segments),
        "holds_throughout": bool(fit.holds_throughout),
        "runtime_check": _runtime_check(fit),
        "failing": list(fit.failing),
    }

    # 1 -- was there enough input to measure? ERROR is "not measured", never
    #      "measured and rejected".
    if _too_thin(fit):
        return Verdict(ERROR, _too_thin_reason(fit), band=u"error", **common)

    # 1b -- there was plenty of input and the rate did not beat luck.
    if not fit.measurable:
        return Verdict(REFUSED, _at_chance_reason(fit), band=u"refuse",
                       **common)

    # 2 -- does the answer hold across the whole runtime?
    if not fit.holds_throughout:
        return Verdict(REFUSED, _does_not_hold_reason(fit), band=u"refuse",
                       **common)

    # 3 -- the band, with coherence as the escalation band's second signal.
    #
    # 🚨 THE CLUSTER ONLY VOUCHES FOR A PAIR THAT IS ACTUALLY IN IT. `coheres`
    # is a statement about the CLUSTER; it says nothing about this pair. Lifting
    # on it alone lifts the one member that does NOT agree -- measured on the
    # oracle at **52 seconds** from its own group's consensus, two different
    # shows, written as CONFIDENT. `arbitrate.Cluster.agrees_with` is the
    # question that was missing, and it owns the ms/s conversion.
    vouching = cluster if (cluster is not None
                           and cluster.agrees_with(_own_offset(fit))) else None
    band = band_of(fit.excess, vouching) if reference_kind in _CUE_KINDS \
        else _mask_band_of(fit.excess, accept_at, refuse_below)
    common["band"] = band

    if band == u"accept":
        lifted = (vouching is not None and vouching.coheres
                  and fit.excess < accept_at)
        cluster = vouching or cluster
        word = LIFTED_WORD if lifted else _word(fit.excess)
        # 🚨 A VACUOUS RUNTIME CHECK MAY NOT PRODUCE THE STRONGEST WORD.
        # `holds_throughout` is `not failing`, so a walk in which EVERY bucket
        # was too thin to speak returns True having evaluated nothing --
        # `_runtime_check` calls that `absent`, and this used to record it and
        # never read it. Found by an adversarial pass on a thinned real file:
        # 0 of 12 buckets usable, six cues 10 s out, reported `locked`.
        # ⚠ Capped, not refused. The SCORE is real evidence; what is missing is
        # the whole-runtime evidence, so the claim is narrowed to match.
        if common["runtime_check"] == u"absent" and word in (u"locked",
                                                             u"strong"):
            word = u"fair"
        return Verdict(
            CONFIDENT, u"", word=word,
            lifted_by=(u"cluster coherence %.2f over %d episodes"
                       % (cluster.coherence, cluster.size)) if lifted else None,
            **common)

    return Verdict(REFUSED, _band_reason(fit, band, cluster, accept_at,
                                         refuse_below, reference_kind),
                   **common)


def _own_offset(fit):
    u"""This pair's offset, for comparison against a cluster's consensus.

    ⭐ The SINGLE-offset fit, not `segments[0]`. A cluster probe measures one
    alignment per episode (`09-corpus-strategy.md` §Stage 4.1), so the
    single-offset answer is the like-for-like number. On an uncut pair they are
    the same; on a cut one, `segments[0]` is only the pre-break stretch.
    """
    single = getattr(fit, "single", None)
    if single:
        return single[0]
    segments = getattr(fit, "segments", None)
    return segments[0][1] if segments else None


def _band_for(reference_kind):
    u"""(accept_at, refuse_below) for this kind of reference.

    ⛔ Raises for a speech mask until RUNBOOK B6 fits the mask band. See
    `MASK_BAND`.
    """
    if reference_kind in _CUE_KINDS:
        return ACCEPT_AT, REFUSE_BELOW
    if MASK_BAND is None:
        raise MaskBandNotFitted(
            "a %s verdict was asked for, but the mask-path band has not been "
            "fitted (RUNBOOK B6). 12-alignment.md §5 measured correct UNCUT "
            "pairs at 2.42-2.77x on a mask and real broadcast CUTS at 1.94x, "
            "straddling the %.1fx cue-vs-cue accept line -- so borrowing it "
            "would refuse a correct pair, silently. Fit MASK_BAND on "
            "video-derived/yomi18/ plus Probe F's controls first."
            % (reference_kind, ACCEPT_AT))
    return MASK_BAND[1], MASK_BAND[0]


def _mask_band_of(excess, accept_at, refuse_below):
    u"""The band on a mask. ⛔ No coherence lift.

    ⚠ Cluster coherence was measured on cue-vs-cue offsets. Nothing has
    measured whether a mask-derived cluster coheres the same way, and an
    unmeasured lift is exactly the confidently wrong answer Rule 2 forbids.
    B6 owns that question too.
    """
    if excess >= accept_at:
        return u"accept"
    if excess < refuse_below:
        return u"refuse"
    return u"escalate"


def _word(excess):
    u"""The confidence word for an accepted pair. `05-interface.md`."""
    for floor, word in _WORDS:
        if excess >= floor:
            return word
    return LIFTED_WORD


# ---------------------------------------------------------------------------
# the hand-back path -- 03-permissions.md
# ---------------------------------------------------------------------------
# Every refusal states three things, in this order:
#
#   1. WHAT WAS MEASURED    -- the match percentage and the verdict word
#   2. WHY IT FELL SHORT    -- which specific guard failed, in plain language
#   3. WHAT WOULD CHANGE IT -- the actual next move
#
# ⛔ *"It failed"* is not actionable and is not acceptable output.

def _too_thin(fit):
    u"""Is there too little input for ANY answer? -> the ERROR condition.

    ===========================================================================
    🚨 SPEC CLAIM DISPROVED BY MEASUREMENT, 2026-09-09 -- probe B8/1
    ===========================================================================

    `12-alignment.md` §3.6 rules: *"`measurable is False` means ERROR, not
    REFUSED"*. Built literally, that routes **every wrong pair this project
    has** to ERROR:

        diamondact2_01 vs diamond01   354/340 cues   1.28x   measurable=False
        atelier03_haruhana vs katainaka03  205/266   1.64x   measurable=False
        memole_1985 vs seihantai01    377/164 cues   1.47x   measurable=False
        time-reversed rezero53        391/528 cues   0.09x   measurable=False
        a different show (gurren)     391/452 cues   1.38x   measurable=False

    ⛔ A time-reversed subtitle with **528 cues** was measured perfectly well.
    It matched 2% of the reference. Reporting *"could not be read at all"* for
    that is the REFUSED/ERROR conflation `03-permissions.md` forbids, running
    in the other direction -- and `subsync` shipped that confusion twice.

    ⭐ THE CAUSE IS THAT ONE NAME ANSWERS TWO QUESTIONS. `Fit.measurable`
    bundles *"is there enough input"* with *"did the rate beat luck"*. Both
    correctly zero `excess`, because a caller must never read a confident
    number out of either -- but they are different OUTCOMES:

        too few cues on a side       -> ERROR    (nothing was measured)
        plenty of cues, rate ~chance -> REFUSED  (measured; it is not a match)

    ⛔ `Fit.measurable` is NOT changed. It answers *"does `excess` mean
    anything"* and it answers it correctly; the aligner and its 29-pair oracle
    are untouched. The distinction is the VERDICT's, which is the layer whose
    job is to say which of the three outcomes this is.
    """
    return min(fit.n_ref, fit.n_sub) < MIN_ALIGNABLE_CUES


def _too_thin_reason(fit):
    u"""The ERROR sentence. `doctrine/robustness`: say what it FOUND."""
    n = min(fit.n_ref, fit.n_sub)
    thin = u"the subtitle" if fit.n_sub <= fit.n_ref else u"the reference"
    return (u"could not be measured: %s has %d cue%s and at least %d are "
            u"needed on both sides. Below that the statistic INVERTS -- a "
            u"one-cue subtitle measured 5.15x chance against a real "
            u"reference, because the best of thousands of offsets always "
            u"lands one cue on something. Check the file parsed: a subtitle "
            u"that read as almost empty is usually the wrong format for its "
            u"extension, not a short episode."
            % (thin, n, u"" if n == 1 else u"s", MIN_ALIGNABLE_CUES))


def _at_chance_reason(fit):
    u"""The REFUSED sentence for a pair that was measured and did not match.

    ⚠ It quotes `raw_excess`, not `excess`. `excess` is deliberately ZERO here
    (`12-alignment.md` §3.6) so no caller can read a confident number out of
    it -- but *"0.0 times chance"* is not what was found, and a message that
    says what it wanted rather than what it found is the failure
    `doctrine/robustness` names. The raw figure is safe in a sentence that
    puts the luck level immediately beside it, which is the whole point of
    LEDGER-HOT's *never trust a match rate without its chance baseline*.
    """
    n = min(fit.n_ref, fit.n_sub)
    floor = bucket_noise_floor(fit.chance, n)
    return (u"%d%% of reference lines matched -- %.1f times what cue density "
            u"alone would land, but across %d cues the BEST of many candidate "
            u"offsets reaches %.1f times chance by luck, so this is not a "
            u"match. Nothing is written. Most often it is simply the wrong "
            u"episode or the wrong show; if the two files really do belong "
            u"together, the subtitle is for a different cut."
            % (int(round(fit.score * 100)), fit.raw_excess, n,
               floor / fit.chance if fit.chance else 0.0))


def _does_not_hold_reason(fit):
    u"""The refusal for a fit that scores well and is wrong somewhere.

    ⭐ THIS IS THE ONE `12-alignment.md` §5 WROTE OUT IN FULL, because it is
    the refusal the VAD path issues most and the one that has to be worth
    reading:

        "the first 3:42 want a different offset (about +10 s) -- a broadcast
         recording with a commercial break; a subtitle from the streaming
         release of this episode will pair."

    It names **the stretch, the size, the likely cause and the fix**, and those
    four are the contract -- not the sentence.

    ⚠ The stretch is reported at BUCKET BOUNDARIES, which is where it was
    measured, rather than at the spec example's `3:42`. That number is the
    recorded truth's precision, not the instrument's, and quoting it would
    manufacture two decimal places the walk never had.
    """
    lo, hi, jump, shape = _diagnose(fit)
    # ⚠ SCATTERED BUCKETS ARE NAMED SEPARATELY, not as one span from the first
    # to the last. Two failing buckets at 0:00 and 16:00 were reported as
    # *"the first 18:00"* -- fourteen minutes of which are fine. `lo`/`hi` are
    # a min and a max with no gap awareness, and the `local` branch's own prose
    # says *"ONE stretch is served badly."*
    stretches = _stretches(fit)
    if len(stretches) > 1:
        where = u" and ".join(u"%s-%s" % (_clock(a), _clock(b))
                              for a, b in stretches)
    elif lo <= 0.0:
        where = u"the first %s" % _clock(hi)
    else:
        where = u"%s-%s" % (_clock(lo), _clock(hi))

    if shape == u"cut":
        cause = (u"a broadcast recording with a commercial break the video "
                 u"does not have")
        fix = (u"a subtitle from the STREAMING release of this episode will "
               u"pair; this one is timed around an advert break")
    elif shape == u"drift":
        cause = (u"the wanted offset grows steadily across the runtime, which "
                 u"is a clock or framerate mismatch rather than a break")
        fix = (u"a release with the same framerate as this video will pair. "
               u"⛔ Nothing is snapped to a named ratio -- guessing one is how "
               u"a whole file ends up subtly wrong")
    else:
        cause = u"one stretch is served badly by the offset the rest agrees on"
        fix = (u"check that this subtitle is for the same cut of the episode "
               u"-- a recap, a different edit or a missing scene does this")

    # ⚠ "moved BY", not "wants an offset OF". The number is the DIFFERENCE
    # from the offset the rest of the file agreed on, and `12-alignment.md`
    # §5's worked example is that difference too (+0.400 against -9.55 is the
    # "+10 s" it quotes). Read as an absolute offset it is off by the whole
    # applied value, which on a broadcast recording is most of the answer.
    return (u"%d%% of reference lines matched overall, but %s wants its "
            u"timing moved about %+.1f s from where the rest of the episode "
            u"agrees -- %s. Refused rather than written: the whole-file "
            u"number is carried by the rest of the episode, and this stretch "
            u"would be visibly out. %s."
            % (int(round(fit.score * 100)), where, jump, cause, fix))


def _band_reason(fit, band, cluster, accept_at, refuse_below, reference_kind):
    u"""The refusal for a pair that held, and did not score well enough."""
    measured = (u"%d%% of reference lines matched, which is %.1f times what "
                u"this subtitle's cue density would land by chance"
                % (int(round(fit.score * 100)), fit.excess))

    if band == u"refuse":
        # ⚠ NOT *"if you are certain..."*. That sentence was written here and
        # the suite refused it: `LEDGER.md` §Interface records a GUI painting a
        # run green because it matched the bare word `confident`, and *certain*
        # is a word this project prints as a verdict. A refusal may not put any
        # of that vocabulary on the line a person skims.
        return (u"%s -- below the %.1fx floor, so this is not the same "
                u"episode, not the same cut, or not the same show. Nothing is "
                u"written. If the two files really do belong together, --pair "
                u"names them explicitly and still measures them; --force "
                u"writes anyway and says so on the line."
                % (measured, refuse_below))

    # The escalation band, and nothing lifted it.
    if cluster is None:
        second = (u"no second signal was available: this pair was measured on "
                  u"its own. ⭐ Syncing the whole folder in one run lets the "
                  u"other episodes vouch for it -- a release's episodes share "
                  u"an offset, and agreement across them is what carries a "
                  u"pair through this band")
    elif cluster.size < _min_cluster():
        second = (u"its folder offered only %d episode%s to compare against, "
                  u"and two agreeing is a coin landing the same way twice. "
                  u"⭐ Running the whole season in one go gives this pair "
                  u"something to be checked against; --pair will also name it "
                  u"explicitly, and still measure it"
                  % (cluster.size, u"" if cluster.size == 1 else u"s"))
    else:
        second = (u"the other episodes in its folder did not agree with it "
                  u"either (%d%% agree on one offset, and %d%% is the bar) -- "
                  u"which is what a wrong pairing looks like across a whole "
                  u"release. ⭐ Check the episode NUMBERING first: a subtitle "
                  u"set numbered from 1 against a video set numbered from 25 "
                  u"pairs every file with the wrong one, and the whole folder "
                  u"then disagrees exactly like this"
                  % (int(round(cluster.coherence * 100)),
                     int(round(_coherence_bar() * 100))))

    return (u"%s -- inside the %.1f-%.1fx band where correct and incorrect "
            u"pairs overlap, so the score alone cannot decide it, and %s. "
            u"Nothing is written."
            % (measured, refuse_below, accept_at, second))


# ---------------------------------------------------------------------------
# reading the bucket walk
# ---------------------------------------------------------------------------

def _runtime_check(fit):
    u"""How much the whole-runtime walk actually saw. -> str

    "held" | "failed" | "weak" | "absent"

    🚨 `06-edge-cases.md` §5.1: a 3-minute short gives ~1.5 buckets at
    `BUCKET = 120 s`, so *"it holds throughout"* degrades to nothing while
    still reading as a pass. **Say the check is weak** rather than let a
    vacuous one be counted -- `doctrine/verification`: *print the denominator,
    so a vacuous pass is visible at a glance.*

    ⚠ Reported, not repaired. Scaling the bucket to duration changes a guard,
    and every guard here sits in a band measured against the 29-pair oracle;
    re-fitting one to serve short content is B5/B6 work with its own
    population, not a line changed in passing.
    """
    if not fit.failing:
        usable = sum(1 for row in fit.buckets if row[2] is not None)
        if usable == 0:
            return u"absent"
        if usable < 2:
            return u"weak"
        return u"held"
    return u"failed"


def _diagnose(fit):
    u"""(lo, hi, jump, shape) for the failing stretch. shape: cut|drift|local.

    ⭐ Two candidate explanations of data the walk already produced, decided
    with constants THIS PROJECT ALREADY MEASURED -- `MIN_BREAK`/`MAX_BREAK`
    (real breaks 8.2-40.1 s, artefacts 108-202 s) and `MAX_BUCKET_DRIFT`.
    `00-INDEX.md` Rule 2: a threshold set by taste breaks the whole value
    proposition.

    🚨 AN EARLIER VERSION OF THIS DOCSTRING CLAIMED IT NEEDED *NO* CONSTANT,
    and that was false twice over. An adversarial pass found both:

      * `_contiguous` on a ONE-element list is `all(... range(0))` -- **True
        unconditionally** -- so a single failing bucket was called a commercial
        break whatever it wanted, including the corpus's own drifting TV edit,
        with the actively wrong advice *"a subtitle from the streaming release
        will pair."* It will not; the clock is wrong.
      * `abs(jumps[-1] - jumps[0]) > abs(jumps[0])` compares a SPREAD to the
        first jump's MAGNITUDE, so the same 8 s spread reads as drift at a
        base of 2 s and as a cut at 20 s. That is a taste threshold wearing
        arithmetic, and deleting it entirely left the suite green.

    ⭐ A CUT now has to look like a break: contiguous, and every jump inside the
    band the aligner already refuses outside of. Anything else is `local`,
    whose advice is safe for all of them.
    """
    # ⚠ `MAX_BUCKET_DRIFT` is not re-exported by `tsubasa.align`, so it comes
    # from `objective` where it is defined. Reaching past the package for one
    # constant is worth a note: the alternative is restating the number here,
    # which is the drift `doctrine/architecture` rule 4 forbids.
    from .align import MAX_BREAK, MIN_BREAK
    from .align.objective import MAX_BUCKET_DRIFT

    rows = sorted(fit.failing, key=lambda r: r[0])
    lo = rows[0][0]
    hi = rows[-1][0] + _bucket_width()
    jumps = [row[3] - fit.offset_at(row[0]) for row in rows]
    jump = jumps[len(jumps) // 2]
    break_sized = all(MIN_BREAK <= abs(j) <= MAX_BREAK for j in jumps)

    # ⚠ Three points before any drift claim. Two are a line whatever they do,
    # and one is not even that. `arbitrate.MIN_CLUSTER` makes the same argument
    # about agreement, for the same reason.
    if len(rows) >= 3 and _monotonic(jumps) \
            and abs(jumps[-1] - jumps[0]) > MAX_BUCKET_DRIFT:
        return lo, hi, jumps[-1], u"drift"
    if _contiguous(rows) and break_sized:
        return lo, hi, jump, u"cut"
    return lo, hi, jump, u"local"


def _stretches(fit):
    u"""The failing buckets grouped into contiguous runs. -> [(lo, hi)]"""
    rows = sorted(fit.failing, key=lambda r: r[0])
    width = _bucket_width()
    out = []
    for row in rows:
        if out and abs(row[0] - out[-1][1]) < 1e-6:
            out[-1] = (out[-1][0], row[0] + width)
        else:
            out.append((row[0], row[0] + width))
    return out


def _contiguous(rows):
    u"""Do these failing buckets sit next to each other in time?

    ⚠ A SINGLE ROW IS NOT EVIDENCE OF CONTIGUITY. `all()` over an empty range
    is True, so this returned True unconditionally for one bucket and every
    lone failure was called a commercial break. One bucket is contiguous in the
    trivial sense and tells you nothing; `_diagnose` now also requires the jump
    to be break-sized, which is what actually separates the cases.
    """
    width = _bucket_width()
    return all(abs(rows[i + 1][0] - rows[i][0] - width) < 1e-6
               for i in range(len(rows) - 1))


def _monotonic(values):
    u"""Strictly one-directional, with no equal steps to fake a trend."""
    ups = all(values[i + 1] > values[i] for i in range(len(values) - 1))
    downs = all(values[i + 1] < values[i] for i in range(len(values) - 1))
    return ups or downs


def _bucket_width():
    u"""⚠ Read from `align`, never restated. It is the walk's own constant."""
    from .align import BUCKET
    return BUCKET


def _coherence_bar():
    u"""⚠ Likewise -- `arbitrate` owns the number and its 60 negative controls."""
    from .arbitrate import COHERENCE_ACCEPT
    return COHERENCE_ACCEPT


def _min_cluster():
    u"""⚠ And likewise. A literal `3` stood here in a file that routes `BUCKET`
    and `COHERENCE_ACCEPT` through helpers *specifically* so a constant is
    never restated -- an adversarial pass changed the literal and the suite
    stayed green. If `MIN_CLUSTER` ever moves, a cluster at the new floor would
    otherwise print *"the others did not agree (100% agree, and 60% is the
    bar)"*, which is nonsense a person would have to debug."""
    from .arbitrate import MIN_CLUSTER
    return MIN_CLUSTER


def _clock(seconds):
    u"""`222.0 -> "3:42"`. What a person reads off a player."""
    if seconds is None or (isinstance(seconds, float) and math.isnan(seconds)):
        return u"?"
    total = int(round(float(seconds)))
    sign = u"-" if total < 0 else u""
    total = abs(total)
    if total >= 3600:
        return u"%s%d:%02d:%02d" % (sign, total // 3600,
                                    (total % 3600) // 60, total % 60)
    return u"%s%d:%02d" % (sign, total // 60, total % 60)


__all__ = [
    "CONFIDENT", "REFUSED", "ERROR", "OUTCOMES",
    "TEXT_TRACK", "BITMAP_TRACK", "SPEECH_MASK", "REFERENCE_KINDS",
    "MASK_BAND", "MaskBandNotFitted",
    "ACCEPT_AT", "REFUSE_BELOW", "LIFTED_WORD",
    "Verdict", "verdict",
]
