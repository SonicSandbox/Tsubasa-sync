# -*- coding: utf-8 -*-
u"""
The verdict, the band, coherence and the hand-back path. RUNBOOK step B8.
Authority: `12-alignment.md` §4, `05-interface.md`, `03-permissions.md`.

⭐ WHAT THIS SUITE IS FOR, AND IT IS NOT THE HAPPY PATH

`align()` already has an oracle proving its offsets. What nothing else can see
is whether the DECISION on top of those offsets is honest -- and every defect
this module exists to prevent is a case where the alignment was fine and the
answer was wrong anyway:

  * a cut file scoring 91% overall while its opening minutes are visibly out
  * a one-cue subtitle scoring 5.15x chance and reading as CONFIDENT
  * a correct English pair at 1.70x refused by a threshold fitted on anime
  * a refusal with no reason, which reads as a success at every surface below

⛔ SO THE CHECKS ARE MOSTLY ABOUT REFUSALS AND ABOUT ORDER, not about accepts.

🚨 AND BOTH KINDS OF MATERIAL ARE HERE ON PURPOSE. The synthetic `Fit`s exist
because a band boundary cannot be hit reliably with real files; the oracle
pairs exist because `doctrine/verification` is explicit that a fixture cannot
show a failure only real data produces. The drifting TV edit in `MUST_REFUSE`
is a REAL specimen of the shape `_diagnose` calls drift -- its buckets want
offsets from -89 s to -108 s -- and no synthetic fixture would have earned
that claim.
"""
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tsubasa import verdict as V                             # noqa: E402
from tsubasa.align import (BUCKET, Fit, align,               # noqa: E402
                           bucket_noise_floor, unique_starts)
from tsubasa.arbitrate import ACCEPT_AT, Cluster, REFUSE_BELOW  # noqa: E402
from tsubasa.paths import load_config, oracle_root           # noqa: E402


# ---------------------------------------------------------------------------
# synthetic material -- a Fit with the exact score we want to reason about
# ---------------------------------------------------------------------------

def cues_needed_for(excess, chance):
    u"""Fewest reference cues at which `excess` is distinguishable from luck.

    ⭐ SOLVED, NOT PINNED. `bucket_noise_floor` is
    `chance + z*sqrt(chance*(1-chance)/n)`, so the smallest measurable excess
    at `n` cues is `1 + z*sqrt((1-chance)/(chance*n))`. Inverting it means the
    helper below cannot quietly start producing unmeasurable fits when a
    constant moves -- `doctrine/verification`: *derive expected values, never
    pin*. The 1.2 factor is headroom, not a threshold.

    ⚠ It is also a real finding in its own right, pinned by
    `test_a_low_excess_needs_a_large_file_to_be_measurable_at_all`.
    """
    from tsubasa.align.objective import BUCKET_NOISE_Z
    if excess <= 1.0:
        return 10 ** 9
    return int(1.2 * (1 - chance)
               / (chance * ((excess - 1.0) / BUCKET_NOISE_Z) ** 2)) + 1


def make_fit(excess=4.0, n=None, chance=0.15, failing=(), buckets=None,
             segments=None, n_sub=None, offset=+1.5):
    u"""A `Fit` whose `excess` is the number asked for, and that is MEASURABLE.

    ⚠ The score is DERIVED from the chance level rather than pinned, and `n`
    defaults to whatever makes that score beat its own noise floor. It asserts
    both postconditions, because a fixture that quietly fails to produce the
    state under test is the *"passed on an empty set"* shape -- and here it
    would silently divert every band check down the ERROR branch, where they
    would all still pass.
    """
    if segments is None:
        segments = ((None, offset),)
    if n is None:
        n = max(300, cues_needed_for(excess, chance))
    score = excess * chance
    if buckets is None:
        buckets = [(t * BUCKET, 40, score, None, None) for t in range(12)]
    fit = Fit(list(segments), score, chance, (segments[0][1], score),
              list(buckets), list(failing), [segments[0][1]], n,
              n if n_sub is None else n_sub, [])
    assert abs(fit.raw_excess - excess) < 1e-9, (
        "the helper did not produce the excess it was asked for: %.4f, not %.4f"
        % (fit.raw_excess, excess))
    return fit


@pytest.mark.parametrize("excess", [1.2, 1.49, 1.7, 2.0, 2.5, 4.0, 6.0])
def test_the_helper_produces_MEASURABLE_fits_or_the_band_checks_are_vacuous(excess):
    u"""⛔ FIRST, and it is not ceremony.

    `excess` is ZERO when a fit is not measurable, so a helper that quietly
    produced unmeasurable fits would send every band check down the
    not-a-match branch -- and they would all still pass, for the wrong reason.
    This is the *"it passed on an empty set"* failure with the denominator
    hidden inside a property.
    """
    fit = make_fit(excess=excess)
    assert fit.measurable, "the synthetic fit at %.2fx is not measurable" % excess
    assert fit.excess == fit.raw_excess > 0.0
    floor = bucket_noise_floor(fit.chance, min(fit.n_ref, fit.n_sub))
    assert fit.score > floor, (
        "score %.3f is under the %d-cue noise floor %.3f, so `excess` would "
        "read zero" % (fit.score, fit.n_ref, floor))


def test_a_low_excess_needs_a_large_file_to_be_measurable_at_all():
    u"""⭐ A MEASURED PROPERTY WORTH KNOWING, and it explains why the bottom of
    the band is barely reachable on real files.

    At a 0.15 chance level, an excess of 1.2x is indistinguishable from luck
    below ~2,300 cues -- more than three times what a real episode carries.
    So a genuinely wrong pair at a realistic cue count does not land *below the
    1.5x floor*; it lands in `not measurable`, which is why the verdict needs
    a branch for *measured, and not a match* at all (probe B8/1)."""
    assert cues_needed_for(1.2, 0.15) > 2000
    assert cues_needed_for(4.0, 0.15) < 300


# ---------------------------------------------------------------------------
# the Verdict object's own guards
# ---------------------------------------------------------------------------

def test_an_unrecognised_outcome_is_refused_at_construction():
    with pytest.raises(ValueError) as e:
        V.Verdict(u"OK", u"looks fine")
    assert "not one of" in str(e.value)


def test_a_refusal_with_no_reason_cannot_be_BUILT():
    u"""🚨 `03-permissions.md`: *`reason` is never empty on a non-confident
    outcome*. Structural, not remembered -- a blank refusal reads as a success
    at every surface downstream."""
    for outcome in (V.REFUSED, V.ERROR):
        with pytest.raises(ValueError) as e:
            V.Verdict(outcome, u"   ")
        assert "hand-back" in str(e.value)


def test_a_confident_verdict_needs_no_reason():
    u"""The other direction. A refusal-only check passes against a constructor
    that refuses everything -- `doctrine/robustness`, *test both directions*."""
    assert V.Verdict(V.CONFIDENT, u"").outcome == V.CONFIDENT


def test_match_percent_is_the_human_number():
    assert V.Verdict(V.CONFIDENT, u"", match_rate=0.9612).match_percent == 96


# ---------------------------------------------------------------------------
# ⛔ THE ORDER OF THE THREE TESTS
# ---------------------------------------------------------------------------

def test_an_unmeasurable_fit_is_ERROR_and_never_REFUSED():
    u"""🚨 The confusion `subsync` shipped twice. REFUSED means *measured and
    not good enough*; ERROR means *never measured*, so there is no offset to
    stand behind and `--force` does not apply."""
    thin = make_fit(excess=5.15, n=1, n_sub=1)
    v = V.verdict(thin)
    assert v.outcome == V.ERROR, (
        "a 1-cue fit was called %s. A one-cue subtitle measured 5.15x chance "
        "against a real reference; that is the case this branch exists for."
        % v.outcome)
    assert v.outcome != V.REFUSED


def test_the_score_does_not_rescue_an_unmeasurable_fit():
    u"""⚠ The band must not run first. `excess` is deliberately zeroed when a
    fit is unmeasurable, so a band-first reading calls a never-measured pair
    *refused* -- which is the wrong sentence AND the wrong outcome."""
    v = V.verdict(make_fit(excess=99.0, n=2, n_sub=2))
    assert v.outcome == V.ERROR
    assert "could not be measured" in v.reason


def test_a_FULL_file_that_scores_at_chance_is_REFUSED_and_never_ERROR():
    u"""🚨 THE SPEC CLAIM PROBE B8/1 DISPROVED, and the check that pins it.

    `12-alignment.md` §3.6 says *"`measurable is False` means ERROR"*. Measured,
    that routes **every wrong pair this project has** to ERROR -- including a
    time-reversed subtitle with **528 cues** that matched 2% of the reference.
    It was measured perfectly well. Reporting *"could not be read at all"* for
    it is the REFUSED/ERROR conflation `03-permissions.md` forbids, running in
    the other direction.

    ⭐ `Fit.measurable` is right about what it answers -- *does `excess` mean
    anything* -- and is unchanged. The two OUTCOMES behind it are the verdict's
    to separate."""
    at_chance = make_fit(excess=1.38, n=391, n_sub=452, chance=0.205)
    assert not at_chance.measurable, "the fixture is not the state under test"
    assert min(at_chance.n_ref, at_chance.n_sub) > 100
    v = V.verdict(at_chance)
    assert v.outcome == V.REFUSED, (
        "a 391/452-cue pair scoring 1.38x was called %s. That is a real "
        "gurren-vs-rezero measurement, and it was measured." % v.outcome)
    assert v.outcome != V.ERROR


def test_the_two_branches_are_split_on_CUE_COUNT_not_on_score():
    u"""The boundary itself, from both sides, so the split cannot drift into
    being a score test."""
    from tsubasa.align import MIN_ALIGNABLE_CUES
    assert V.verdict(make_fit(excess=1.1, n=MIN_ALIGNABLE_CUES - 1,
                              n_sub=MIN_ALIGNABLE_CUES - 1)).outcome == V.ERROR
    assert V.verdict(make_fit(excess=1.1, n=MIN_ALIGNABLE_CUES,
                              n_sub=MIN_ALIGNABLE_CUES)).outcome == V.REFUSED


def test_a_failing_bucket_refuses_a_fit_that_scores_well():
    u"""🚨 THE ORDER THAT MATTERS MOST. A cut file scores well overall because
    the larger segment dominates. Four megatest files were confidently
    mis-timed for their opening minutes, and the mistake was repeated on a
    second folder before the whole-runtime walk existed."""
    failing = [(0.0, 40, 0.30, +10.0, 0.62)]
    v = V.verdict(make_fit(excess=6.0, failing=failing))
    assert v.outcome == V.REFUSED, (
        "a fit at 6.0x with a failing bucket was called %s -- the band ran "
        "before the runtime check" % v.outcome)
    assert v.band == u"refuse"
    assert v.holds_throughout is False


def test_the_same_fit_WITHOUT_the_failing_bucket_is_confident():
    u"""The control for the check above. Without it, that check passes against
    a verdict that refuses every input."""
    v = V.verdict(make_fit(excess=6.0))
    assert v.outcome == V.CONFIDENT
    assert v.word == u"locked"


# ---------------------------------------------------------------------------
# the band -- 12-alignment.md §4
# ---------------------------------------------------------------------------

def test_at_or_above_the_accept_line_is_written():
    v = V.verdict(make_fit(excess=ACCEPT_AT))
    assert v.outcome == V.CONFIDENT and v.band == u"accept"


def test_below_the_refuse_line_is_refused():
    v = V.verdict(make_fit(excess=REFUSE_BELOW - 0.01))
    assert v.outcome == V.REFUSED and v.band == u"refuse"


def test_the_escalation_band_alone_is_REFUSED_not_written():
    u"""🚨 An absent second signal is not a passing one.

    `05-interface.md`: *escalate to a second signal ... only refuse if that
    also fails*. With nothing to escalate TO, the honest answer is refusal --
    wrong pairs measured **1.37-1.95x**, which is inside this band, so
    accepting on a bare escalate writes exactly the confidently wrong file
    Rule 2 exists to prevent."""
    v = V.verdict(make_fit(excess=2.0))
    assert v.band == u"escalate"
    assert v.outcome == V.REFUSED
    assert v.word is None


def test_the_band_is_the_WIDE_one_and_not_the_stale_word_table():
    u"""⛔ `05-interface.md`'s word table still says *refused below 2.0x*. The
    escalation recorded below it in the same file, and `12-alignment.md` §4,
    both say **< 1.5x**. A pair at 1.7x is the measured English case: correct,
    and refused outright by the stale reading."""
    assert REFUSE_BELOW == 1.5
    v = V.verdict(make_fit(excess=1.70))
    assert v.band == u"escalate", (
        "1.70x fell to %r. Three Manifest episodes measured 1.70-2.12x and "
        "were unambiguously correct pairs." % v.band)


# ---------------------------------------------------------------------------
# coherence -- the lift is ONE-DIRECTIONAL
# ---------------------------------------------------------------------------

# ⚠ `make_fit`'s offset is +1.5 s, so a cluster that VOUCHES for it must sit at
# about +1500 ms. The first version of these checks used `Cluster([100, 120,
# 150, 130])` — a group 1.35 s away from the pair it was lifting — and asserted
# CONFIDENT. **The suite was asserting the defect.**
AGREEING = [1500, 1520, 1480, 1510, 1495]      # ms, and they match make_fit
DISAGREEING = [100, 120, 150, 130, 110]        # ms, coherent but not about US
#: ⚠ A cluster the pair BELONGS to which does NOT cohere — the ordinary case
#: `arbitrate.py` describes (broadcast subtitles against a web release differ
#: per episode). Three mutants survived against a SCATTERED fixture the pair
#: was not part of: the pair failed `agrees_with` first, so the cluster never
#: reached the band at all and a mutant keyed on it could not fire.
INCOHERENT = [1500, 5000, 9000, 15000]


def test_a_coherent_cluster_lifts_a_pair_that_IS_IN_IT():
    cluster = Cluster(AGREEING)
    assert cluster.coheres
    v = V.verdict(make_fit(excess=2.0), cluster=cluster)
    assert v.outcome == V.CONFIDENT
    assert v.word == V.LIFTED_WORD
    assert v.lifted_by and "coherence" in v.lifted_by


def test_a_COHERENT_cluster_does_not_lift_a_pair_that_DISAGREES_WITH_IT():
    u"""🚨 THE WORST DEFECT THIS PROJECT HAS HAD, found by an adversarial pass.

    `coheres` is a statement about the CLUSTER. Lifting on it alone lifts the
    one member that does **not** agree — and `arbitrate.py`'s own docstring
    names that shape: *"a cluster where nine episodes agree and one is wildly
    off is a coherent cluster with one bad episode."*

    Measured on the oracle: two entirely different shows, 1.62x, own offset
    **52 seconds** from the consensus of the four siblings vouching for it —
    written as CONFIDENT. Five such pairs exist among 324 cross-show
    combinations. The whole value proposition is that this cannot happen.
    """
    cluster = Cluster(DISAGREEING)
    assert cluster.coheres, "the fixture must be a COHERENT cluster"
    v = V.verdict(make_fit(excess=2.0), cluster=cluster)
    assert v.outcome == V.REFUSED, (
        "a pair %s from its cluster's consensus was lifted to %s"
        % (1.5, v.outcome))
    assert v.lifted_by is None


def test_the_outlier_and_the_member_get_OPPOSITE_answers_from_one_cluster():
    u"""The pair of checks above, as one statement: the same cluster must lift
    the episode that agrees and refuse the episode that does not."""
    mixed = Cluster([-9550, -9480, -9600, -9520, -62499])   # four agree, one wild
    assert mixed.coheres
    member = V.verdict(make_fit(excess=2.0, offset=-9.520), cluster=mixed)
    outlier = V.verdict(make_fit(excess=2.0, offset=-62.499), cluster=mixed)
    assert member.outcome == V.CONFIDENT, member.reason
    assert outlier.outcome == V.REFUSED, "the 52-second outlier was written"


def test_the_units_are_converted_in_ONE_place():
    u"""⚠ Cluster offsets are MILLISECONDS; `Fit` offsets are SECONDS. Nothing
    structural stopped a 1000x error, so the conversion lives in
    `arbitrate.Cluster.agrees_with` and nowhere else."""
    cluster = Cluster(AGREEING)
    assert cluster.agrees_with(1.5) is True          # seconds
    assert cluster.agrees_with(1500) is False        # would be ms — a 1000x slip
    assert cluster.agrees_with(None) is False


def test_a_lifted_pair_is_NOT_called_fair_or_better():
    u"""⚠ The evidence that carried it is the cluster's agreement, not its own
    score, and the word a person reads has to say so."""
    v = V.verdict(make_fit(excess=2.0), cluster=Cluster(AGREEING))
    assert v.word not in (u"locked", u"strong", u"fair")


def test_an_incoherent_cluster_never_pushes_an_accepted_pair_DOWN():
    u"""⭐ The asymmetry is the whole design. A correct cluster with low
    coherence is ordinary -- broadcast subtitles against a web release differ
    per episode -- while a wrong cluster essentially never coheres. The
    evidence is strong in one direction only, so only one direction is used."""
    scattered = Cluster(INCOHERENT)
    assert not scattered.coheres
    assert scattered.agrees_with(1.5), (
        "the pair must BELONG to this cluster, or the lift never reaches the "
        "band and a mutation keyed on it cannot fire")
    v = V.verdict(make_fit(excess=4.0), cluster=scattered)
    assert v.outcome == V.CONFIDENT, (
        "an incoherent cluster demoted a 4.0x pair to %s" % v.outcome)
    assert v.lifted_by is None


def test_two_agreeing_episodes_do_not_lift():
    u"""Two pairs agreeing is a coin landing the same way twice, and it scores
    a perfect 1.00."""
    pair = Cluster([100, 120])
    assert pair.coherence == 1.0 and not pair.coheres
    assert V.verdict(make_fit(excess=2.0), cluster=pair).outcome == V.REFUSED


def test_a_coherent_cluster_does_not_rescue_a_pair_below_the_floor():
    u"""⛔ Coherence lifts the escalation band. It does not replace the
    referee -- `09-corpus-strategy.md` §Stage 4.4."""
    vouching = Cluster(AGREEING)
    assert vouching.coheres and vouching.agrees_with(1.5)
    v = V.verdict(make_fit(excess=1.2), cluster=vouching)
    assert v.outcome == V.REFUSED


def test_a_coherent_cluster_does_not_rescue_a_failing_bucket_walk():
    u"""The other bypass of the same shape: a whole release can be coherent and
    still be a broadcast recording against streaming video."""
    failing = [(0.0, 40, 0.30, +10.0, 0.62)]
    vouching = Cluster(AGREEING)
    assert vouching.coheres and vouching.agrees_with(1.5)
    v = V.verdict(make_fit(excess=2.0, failing=failing), cluster=vouching)
    assert v.outcome == V.REFUSED


# ---------------------------------------------------------------------------
# the hand-back path -- 03-permissions.md
# ---------------------------------------------------------------------------

def _refusals():
    u"""One verdict of every non-confident shape this module can produce."""
    return {
        u"thin": V.verdict(make_fit(excess=5.15, n=1, n_sub=1)),
        u"noise": V.verdict(make_fit(excess=1.05, n=40, chance=0.40)),
        u"below floor": V.verdict(make_fit(excess=1.2)),
        u"escalated alone": V.verdict(make_fit(excess=2.0)),
        u"escalated in an incoherent cluster": V.verdict(
            make_fit(excess=2.0), cluster=Cluster(INCOHERENT)),
        u"escalated in a cluster too small to vote": V.verdict(
            make_fit(excess=2.0), cluster=Cluster([100, 120])),
        u"cut": V.verdict(make_fit(
            excess=6.0, failing=[(0.0, 40, 0.30, +10.0, 0.62)])),
        u"drift": V.verdict(make_fit(excess=6.0, failing=[
            (t * BUCKET, 40, 0.30, 2.0 + 2.0 * t, 0.62) for t in range(5)])),
    }


def test_every_refusal_states_what_was_measured():
    u"""Part 1 of the hand-back contract.

    ⚠ A NUMBER, not specifically a percentage. On the thin branch there is no
    meaningful percentage to quote -- the measurement IS the cue count -- and
    demanding a `%` there would push a made-up figure into the one message
    whose whole point is that nothing was measured."""
    for label, v in _refusals().items():
        assert any(ch.isdigit() for ch in v.reason), (
            "%s: no measurement in %r" % (label, v.reason))


def test_every_refusal_says_what_would_change_it():
    u"""Part 3, and the one that makes the difference between a report and a
    dead end. ⛔ *"It failed"* is not actionable and is not acceptable output."""
    fixes = ("will pair", "--pair", "one run", "check the", "wrong episode")
    for label, v in _refusals().items():
        lowered = v.reason.lower()
        assert any(f in lowered for f in fixes), (
            "%s offers no next move: %r" % (label, v.reason))


def test_a_confidence_word_cannot_be_CONSTRUCTED_onto_a_refusal():
    u"""🚨 `verdict()` never takes that route, but the CONSTRUCTOR handed it
    out — and 3b's `Result` and 3c's CLI line are both specified to build
    Verdict-shaped objects. `LEDGER.md` §Interface is a GUI that painted a run
    green off a bare word; this was the raw material for it, and the comment
    saying *"None on anything not written"* was not a guard."""
    for outcome in (V.REFUSED, V.ERROR):
        with pytest.raises(ValueError) as e:
            V.Verdict(outcome, u"a reason", word=u"locked")
        assert "no word to print" in str(e.value)


def test_the_confidence_vocabulary_is_mutually_NON_SUBSTRING():
    u"""🚨 THE DEFECT THIS REPLACED, AND WHY IT IS NOW STRUCTURAL.

    The top word was `certain` — a SUBSTRING of `uncertain`. The word printed
    on the weakest thing this tool writes contained the word printed on the
    strongest, which re-arms `LEDGER.md` §Interface's defect (a GUI painted a
    run green because *"11 confident, 1 refused"* matched a bare word) one
    level down, for any consumer that substring-matches.

    ⭐ Found by an adversarial pass and pinned as a known hazard; Sonic then
    ruled the swap to `locked` — his own word for the outcome, *"every part of
    the episode locks in well"*. **This check is the fix**: the next word added
    to the vocabulary cannot quietly reintroduce the collision.

    ⚠ `confident` is in the set too. It is not a confidence WORD — it is the
    outcome name — and it is exactly the string the GUI matched.
    """
    words = [w for _floor, w in V._WORDS] + [V.LIFTED_WORD, V.CONFIDENT.lower()]
    assert len(set(words)) == len(words), words
    for a in words:
        for b in words:
            if a is not b and a != b:
                assert a not in b, (
                    "%r is a substring of %r — a consumer matching the bare "
                    "word will read one as the other" % (a, b))


def test_no_refusal_carries_a_confidence_word():
    u"""🚨 `LEDGER.md` §Interface: the GUI painted a run containing refusals
    green, because *"11 confident, 1 refused"* contains the word *confident*
    and the bare word was being matched -- on the one line a user reads at a
    glance. A refusal has no word to print, and its sentence does not supply
    one either."""
    for label, v in _refusals().items():
        assert v.word is None, "%s carries the word %r" % (label, v.word)
        assert v.written is False
        lowered = v.reason.lower()
        for banned in (u"confident",) + tuple(w for _f, w in V._WORDS):
            assert banned not in lowered, (
                "%s: the refusal sentence contains %r, which is what the GUI "
                "matched on" % (label, banned))


def test_the_two_unmeasurable_reasons_are_DIFFERENT_sentences():
    u"""`doctrine/robustness`: a failure message says what it FOUND. *Too few
    cues* and *the rate did not beat luck* send the reader to completely
    different places -- one is a file that cannot be used, the other is
    probably the wrong episode."""
    thin = V.verdict(make_fit(excess=5.15, n=1, n_sub=1)).reason
    noise = V.verdict(make_fit(excess=1.05, n=40, chance=0.40)).reason
    assert thin != noise
    assert "at least" in thin and "cue" in thin
    assert "luck" in noise


def test_the_at_chance_reason_quotes_the_RAW_multiple_not_the_zeroed_one():
    u"""⚠ `excess` is zero on this branch by design, and *"0.0 times chance"*
    is not what was found. `doctrine/robustness`: a message says what it found,
    not what it wanted -- and the luck level sits beside it in the same
    sentence, which is what makes quoting the raw figure honest.

    🚨 THE FIXTURE IS CHOSEN SO THE TWO NUMBERS PRINT DIFFERENTLY. The first
    version used one where `raw_excess` was 1.3800 and the noise floor 1.3984 —
    **both render as `1.4`** — so a mutation swapping them left the suite
    green. A check that cannot tell apart the two values it was written to
    tell apart is true for the wrong reason.
    """
    fit = make_fit(excess=1.05, n=40, chance=0.40)
    floor = bucket_noise_floor(fit.chance, min(fit.n_ref, fit.n_sub))
    assert round(fit.raw_excess, 1) != round(floor / fit.chance, 1), (
        "the fixture's two numbers round to the same string, so this check "
        "cannot distinguish them: %.4f vs %.4f"
        % (fit.raw_excess, floor / fit.chance))

    v = V.verdict(fit)
    assert v.excess == 0.0, "the machine-readable field must stay zeroed"
    assert "%.1f times what cue density" % fit.raw_excess in v.reason, v.reason
    assert "%.1f times chance by luck" % (floor / fit.chance) in v.reason, v.reason


def test_the_escalated_refusal_quotes_the_REAL_cluster_numbers():
    u"""⚠ Replacing both figures with `0` left the suite green — the check
    asserted a literal `%` and the phrase, never the values. *"0% agree on one
    offset, and 0% is the bar"* is self-contradictory output."""
    cluster = Cluster(INCOHERENT)
    reason = V.verdict(make_fit(excess=2.0), cluster=cluster).reason
    assert "%d%% agree" % round(cluster.coherence * 100) in reason, reason
    assert "%d%% is the bar" % round(V._coherence_bar() * 100) in reason, reason


def test_the_small_cluster_floor_is_ARBITRATES_not_a_literal():
    u"""⚠ A literal `3` stood in `_band_reason`, in a file that routes every
    other constant through a helper. Changing it left the suite green."""
    from tsubasa.arbitrate import MIN_CLUSTER
    assert V._min_cluster() == MIN_CLUSTER
    reason = V.verdict(make_fit(excess=2.0),
                       cluster=Cluster([1500] * (MIN_CLUSTER - 1))).reason
    assert "coin landing" in reason, reason


def test_the_thin_reason_names_WHICH_side_was_thin():
    sub_thin = V.verdict(make_fit(excess=5.15, n=300, n_sub=1))
    assert "the subtitle has 1 cue" in sub_thin.reason
    ref_thin = V.verdict(make_fit(excess=5.15, n=2, n_sub=300))
    assert "the reference has 2 cues" in ref_thin.reason


# --- the CM-break refusal, written out in 12-alignment.md §5 ---------------

def test_the_cut_refusal_names_the_stretch_the_size_the_cause_and_the_fix():
    u"""⭐ THE FOUR PROPERTIES ARE THE CONTRACT, not the sentence.

    `12-alignment.md` §5 gives the refusal the VAD path issues most:

        "the first 3:42 want a different offset (about +10 s) -- a broadcast
         recording with a commercial break; a subtitle from the streaming
         release of this episode will pair."

    ⚠ Asserting that literal string would pin the RECORDED TRUTH's precision
    onto the instrument. The walk measures in 120 s buckets, so it reports a
    bucket boundary; quoting 3:42 would invent two digits it never had.
    """
    v = V.verdict(make_fit(excess=6.0, segments=((None, +1.5),),
                           failing=[(0.0, 40, 0.30, +10.0, 0.62)]))
    assert v.outcome == V.REFUSED
    reason = v.reason
    assert "the first 2:00" in reason, "no stretch named: %r" % reason
    # ⚠ +8.5, not +10.0. The size is the DIFFERENCE from the offset the rest
    # of the file agreed on (+1.5), which is what `12-alignment.md` §5's own
    # worked example quotes. An absolute offset here would be off by the whole
    # applied value -- on a broadcast recording, most of the answer.
    assert "+8.5 s" in reason, "no size named: %r" % reason
    assert "moved" in reason, "the size must read as a shift: %r" % reason
    assert "commercial break" in reason, "no likely cause named: %r" % reason
    assert "STREAMING release" in reason, "no fix named: %r" % reason


def test_the_cut_refusal_reports_a_SHIFT_and_not_an_absolute_offset():
    u"""The check that pins the paragraph above: change the offset the rest of
    the file agreed on, and the reported size must move with it."""
    failing = [(0.0, 40, 0.30, +10.0, 0.62)]
    a = V.verdict(make_fit(excess=6.0, segments=((None, 0.0),), failing=failing))
    b = V.verdict(make_fit(excess=6.0, segments=((None, -9.55),), failing=failing))
    assert "+10.0 s" in a.reason, a.reason
    assert "+19.6 s" in b.reason, b.reason


def test_the_cut_refusal_reports_a_MID_FILE_stretch_as_a_range():
    u"""A break that is not at the start is not *"the first N"*."""
    failing = [(240.0, 40, 0.30, -9.8, 0.62), (360.0, 40, 0.30, -9.8, 0.62)]
    reason = V.verdict(make_fit(excess=6.0, failing=failing)).reason
    assert "4:00-8:00" in reason, reason
    assert "the first" not in reason


def test_a_drifting_file_is_diagnosed_as_drift_and_not_as_a_cut():
    u"""⭐ Two candidate explanations of data the walk already produced, and
    telling them apart needs NO new constant: a cut is a contiguous run wanting
    ONE offset, drift is a monotonic series wanting a growing one. A threshold
    fitted by taste here would break Rule 2."""
    failing = [(t * BUCKET, 40, 0.30, 2.0 + 2.0 * t, 0.62) for t in range(5)]
    reason = V.verdict(make_fit(excess=6.0, failing=failing)).reason
    assert "grows steadily" in reason, reason
    assert "commercial break" not in reason
    assert "named ratio" in reason, (
        "the drift refusal must say it will not snap to a framerate ratio: %r"
        % reason)


def test_ONE_failing_bucket_is_only_a_cut_if_the_jump_is_BREAK_SIZED():
    u"""🚨 `_contiguous` on a one-element list is `all(... range(0))` — **True
    unconditionally** — so a single failing bucket was called a commercial
    break whatever it wanted, including the corpus's own DRIFTING TV edit, with
    the actively wrong advice *"a subtitle from the streaming release will
    pair."* It will not; the clock is wrong.

    ⭐ A cut now has to look like a break, using `MIN_BREAK`/`MAX_BREAK` — the
    constants the aligner already measured (real breaks 8.2–40.1 s, artefacts
    108–202 s), not a new one.
    """
    def one(want):
        return V._diagnose(make_fit(excess=6.0, offset=0.0,
                                    failing=[(960.0, 40, 0.30, want, 0.62)]))[3]
    assert one(10.0) == u"cut"          # a plausible commercial block
    assert one(0.9) == u"local"         # under MIN_BREAK — not a break
    assert one(-147.0) == u"local"      # over MAX_BREAK — an artefact


def test_the_drift_gate_is_SCALE_INDEPENDENT():
    u"""🚨 `abs(jumps[-1] - jumps[0]) > abs(jumps[0])` compared a SPREAD to the
    first jump's MAGNITUDE, so the same 8 s spread read as drift at a base of
    2 s and as a **commercial break** at 20 s. Deleting that clause entirely
    left the suite green — it was a taste threshold wearing arithmetic, of the
    kind `00-INDEX.md` Rule 2 forbids. It is now `MAX_BUCKET_DRIFT`."""
    def sweep(base):
        rows = [(t * BUCKET, 40, 0.30, base + 2.0 * t, 0.62) for t in range(5)]
        return V._diagnose(make_fit(excess=6.0, offset=0.5, failing=rows))[3]
    assert sweep(2.0) == sweep(20.0) == sweep(100.0) == u"drift"


def test_two_failing_buckets_do_not_support_a_drift_claim():
    u"""⚠ Two points are a line whatever they do. `arbitrate.MIN_CLUSTER`
    makes the same argument about agreement, for the same reason."""
    failing = [(0.0, 40, 0.30, 2.0, 0.62), (BUCKET, 40, 0.30, 8.0, 0.62)]
    reason = V.verdict(make_fit(excess=6.0, failing=failing)).reason
    assert "grows steadily" not in reason


def test_scattered_failing_buckets_are_neither_a_cut_nor_drift():
    failing = [(0.0, 40, 0.30, +9.0, 0.62), (600.0, 40, 0.30, +9.0, 0.62)]
    reason = V.verdict(make_fit(excess=6.0, failing=failing)).reason
    assert "commercial break" not in reason and "grows steadily" not in reason
    assert "same cut of the episode" in reason


def test_scattered_stretches_are_named_SEPARATELY_not_as_one_span():
    u"""⚠ Two failing buckets at 0:00 and 10:00 were reported as *"the first
    12:00"* — ten minutes of which are fine. `lo`/`hi` were a min and a max
    with no gap awareness, while the branch's own prose says *"ONE stretch is
    served badly."*"""
    failing = [(0.0, 40, 0.30, +9.0, 0.62), (600.0, 40, 0.30, +9.0, 0.62)]
    reason = V.verdict(make_fit(excess=6.0, failing=failing)).reason
    assert "0:00-2:00 and 10:00-12:00" in reason, reason
    assert "the first 12:00" not in reason


def test_a_contiguous_run_is_still_named_as_ONE_stretch():
    u"""The control for the check above — grouping must not fragment a real
    contiguous run."""
    failing = [(0.0, 40, 0.30, +9.0, 0.62), (BUCKET, 40, 0.30, +9.0, 0.62)]
    reason = V.verdict(make_fit(excess=6.0, failing=failing)).reason
    assert "the first 4:00" in reason, reason
    assert " and " not in reason.split("wants")[0]


def test_the_escalated_refusal_tells_a_lone_pair_to_sync_the_folder():
    u"""The second signal is a cluster, so the actionable move is to give the
    run one."""
    reason = V.verdict(make_fit(excess=2.0)).reason
    assert "whole folder" in reason


def test_the_escalated_refusal_reports_the_cluster_that_disagreed():
    reason = V.verdict(make_fit(excess=2.0),
                       cluster=Cluster(INCOHERENT)).reason
    assert "did not agree" in reason
    assert "%" in reason


# ---------------------------------------------------------------------------
# the mask band -- UNFITTED, and structurally so
# ---------------------------------------------------------------------------

def test_a_speech_mask_verdict_RAISES_until_B6_fits_its_band():
    u"""🚨 `12-alignment.md` §5.2. Correct UNCUT pairs measured **2.42-2.77x**
    on a mask while real broadcast CUTS sat at **1.94x** -- straddling the 2.5
    cue-vs-cue accept line. Borrowing that line refuses a correct pair,
    silently.

    ⛔ It raises rather than refuses because this is a TOOLING fault, not a
    product verdict: a quiet refusal ships a tool that says no to every VAD
    pair and looks like it is working."""
    with pytest.raises(V.MaskBandNotFitted) as e:
        V.verdict(make_fit(excess=2.6), reference_kind=V.SPEECH_MASK)
    message = str(e.value)
    assert "B6" in message, message
    assert "2.42-2.77x" in message, (
        "the fault must carry the measurement that makes it a fault: %s"
        % message)


def test_the_mask_band_is_ABSENT_rather_than_a_borrowed_default():
    u"""⭐ `doctrine/robustness`: a rule that relies on remembering will be
    forgotten. A comment saying *"fit these at B6"* beside a copied 2.5 is the
    version of this that does not hold."""
    assert V.MASK_BAND is None


def test_a_bitmap_track_uses_the_cue_band_unchanged():
    u"""A PGS/VobSub ON-time is a cue moment like any other -- the container
    block timestamps that produced it know nothing about the codec."""
    v = V.verdict(make_fit(excess=4.0), reference_kind=V.BITMAP_TRACK)
    assert v.outcome == V.CONFIDENT
    assert v.reference_kind == V.BITMAP_TRACK


def test_an_unknown_reference_kind_is_refused_loudly():
    with pytest.raises(ValueError) as e:
        V.verdict(make_fit(), reference_kind=u"vibes")
    assert "12-alignment.md" in str(e.value)


# ---------------------------------------------------------------------------
# the runtime check's denominator -- 06-edge-cases.md §5.1
# ---------------------------------------------------------------------------

def test_a_short_file_reports_its_runtime_check_as_WEAK_not_as_held():
    u"""🚨 A 3-minute short gives ~1.5 buckets at `BUCKET = 120 s`, so *"it
    holds throughout"* degrades to nothing while still reading as a pass.
    `doctrine/verification`: print the denominator, so a vacuous pass is
    visible at a glance."""
    short = make_fit(excess=4.0, buckets=[(0.0, 40, 0.30, None, None),
                                          (BUCKET, 3, None, None, None)])
    v = V.verdict(short)
    assert v.runtime_check == u"weak", (
        "one usable bucket reported as %r" % v.runtime_check)
    assert v.outcome == V.CONFIDENT       # ⚠ weak evidence, not bad evidence


def test_a_VACUOUS_runtime_check_may_not_produce_the_strongest_word():
    u"""🚨 `holds_throughout` is `not failing`, so a walk in which EVERY bucket
    was too thin returns True having evaluated nothing. Found by an adversarial
    pass on a thinned real file: 0 of 12 buckets usable, six cues 10 s out,
    reported `locked`. ⚠ Capped, not refused — the SCORE is real evidence;
    what is missing is the whole-runtime evidence."""
    absent = make_fit(excess=6.0, buckets=[(0.0, 3, None, None, None)])
    v = V.verdict(absent)
    assert v.runtime_check == u"absent"
    assert v.outcome == V.CONFIDENT
    assert v.word not in (u"locked", u"strong"), v.word


def test_the_cap_does_not_fire_when_the_walk_DID_run():
    u"""The control. Without it the check above passes against a verdict that
    caps every word."""
    assert V.verdict(make_fit(excess=6.0)).word == u"locked"


def test_the_strongest_word_is_reachable_at_all():
    u"""⚠ `strong` was mutable to `fair` with the suite green — nothing named
    the middle rung. Each word must be produced by some excess."""
    seen = {V.verdict(make_fit(excess=e)).word for e in (6.0, 3.5, 2.7)}
    assert seen == {u"locked", u"strong", u"fair"}, seen


def test_a_normal_file_reports_its_runtime_check_as_HELD():
    assert V.verdict(make_fit(excess=4.0)).runtime_check == u"held"


def test_a_file_with_no_usable_buckets_reports_ABSENT():
    none_usable = make_fit(excess=4.0,
                           buckets=[(0.0, 3, None, None, None)])
    assert V.verdict(none_usable).runtime_check == u"absent"


def test_a_failing_walk_reports_FAILED():
    v = V.verdict(make_fit(excess=6.0,
                           failing=[(0.0, 40, 0.30, +10.0, 0.62)]))
    assert v.runtime_check == u"failed"


# ---------------------------------------------------------------------------
# the clock format a person reads
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("seconds,text", [
    (0.0, u"0:00"), (222.0, u"3:42"), (59.6, u"1:00"),
    (3600.0, u"1:00:00"), (5025.0, u"1:23:45"), (-90.0, u"-1:30"),
])
def test_the_clock_reads_like_a_player(seconds, text):
    assert V._clock(seconds) == text


# ---------------------------------------------------------------------------
# 🚨 REAL MATERIAL -- the oracle's own ground truth
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def oracle():
    u"""(subsync, corpus, megatest dir, vidref dir).

    ⚠ A skip SAYS SO. A bare skip reads as a pass in a summary line.
    """
    root = oracle_root(load_config(ROOT), ROOT)
    if not root.is_dir():
        pytest.skip("SKIPPED, NOT PASSED: the oracle is absent at %s" % root)
    mega, vidref = root / "SubtitleMegaTest", root / "tests" / "fixtures" / "vidref"
    if not (mega.is_dir() and vidref.is_dir()):
        pytest.skip("SKIPPED, NOT PASSED: the oracle's corpus or fixtures are absent")
    for p in (str(root), str(root / "tests")):
        if p not in sys.path:
            sys.path.insert(0, p)
    argv = sys.argv
    sys.argv = ["pytest"]                    # subsync parses argv on import
    try:
        import corpus
        import subsync
    finally:
        sys.argv = argv
    return subsync, corpus, mega, vidref


def _reference(oracle, key):
    u"""The reference cue list for `key`, whether it names a SUBTITLE or a VIDEO.

    ⚠ `MUST_REFUSE` rows are `(subtitle key, VIDEO key, why)` -- the second
    names an entry in `VIDEOS`, whose reference track lives as a small fixture
    in `vidref/`. Reading it out of `SUBS` raises `KeyError`, which is how this
    was found. Returns `None` for a name-only placeholder video.
    """
    _S, C, mega, vidref = oracle
    if key in C.SUBS:
        return mega / C.SUBS[key]
    fixture = C.VIDEOS[key][1]
    return (vidref / fixture) if fixture else None


def _aligned(oracle, ref_key, sub_key):
    u"""Align two of the oracle's real files. -> Fit, or None if unavailable."""
    S, _C, _mega, _vidref = oracle
    ref_path, sub_path = _reference(oracle, ref_key), _reference(oracle, sub_key)
    if ref_path is None or sub_path is None:
        return None
    ref, sub = S.parse_cues(str(ref_path)), S.parse_cues(str(sub_path))
    duration = max(max(c[1] for c in ref), max(c[1] for c in sub))
    return align(unique_starts([c[0] for c in S.dialogue_only(ref)]),
                 unique_starts([c[0] for c in sub]), duration)


def test_a_real_correct_pair_is_written_with_a_word(oracle):
    u"""⛔ THE POSITIVE CONTROL, and it comes first. Everything below asserts a
    refusal, and a suite of refusals passes trivially against a function that
    refuses everything."""
    v = V.verdict(_aligned(oracle, "rezero53_atx", "rezero53_netflix"))
    assert v.outcome == V.CONFIDENT, "%s: %s" % (v.outcome, v.reason)
    assert v.word in (u"locked", u"strong", u"fair")
    assert v.match_percent > 50


def test_every_MUST_REFUSE_pair_is_not_written(oracle):
    u"""Five real pairs the corpus records as wrong: a sequel season sharing an
    episode number, a TV edit that drifts against the BluRay, two different
    shows, and a 1985 OVA against a 2025 episode."""
    _S, C, _mega, _vidref = oracle
    seen = 0
    for sub_key, video_key, why in C.MUST_REFUSE:
        fit = _aligned(oracle, video_key, sub_key)
        if fit is None:
            continue
        seen += 1
        v = V.verdict(fit)
        assert v.outcome in (V.REFUSED, V.ERROR), (
            "%s vs %s was WRITTEN at %.2fx -- %s"
            % (sub_key, video_key, v.excess, why))
        assert v.reason.strip(), "%s vs %s refused with no reason" % (
            sub_key, video_key)
        assert v.word is None
    # ⚠ The denominator, printed. A loop over an empty list passes.
    assert seen == len(C.MUST_REFUSE), (
        "only %d of %d MUST_REFUSE pairs were reachable" % (
            seen, len(C.MUST_REFUSE)))


def test_the_real_wrong_pairs_are_REFUSED_and_not_reported_as_unreadable(oracle):
    u"""🚨 THE CHECK THAT WOULD HAVE CAUGHT §3.6 BEING BUILT LITERALLY.

    Every one of these files parsed cleanly and carries 164-528 cues. They are
    the wrong episode, the wrong season or the wrong show -- which is a REFUSAL
    with a reason a person can act on, not *"could not be read at all"*."""
    _S, C, _mega, _vidref = oracle
    for sub_key, video_key, _why in C.MUST_REFUSE:
        fit = _aligned(oracle, video_key, sub_key)
        if fit is None or min(fit.n_ref, fit.n_sub) < 100:
            continue
        v = V.verdict(fit)
        assert v.outcome == V.REFUSED, (
            "%s vs %s has %d/%d cues and was reported %s"
            % (sub_key, video_key, fit.n_ref, fit.n_sub, v.outcome))


def test_the_real_drifting_TV_EDIT_is_refused_by_the_runtime_walk(oracle):
    u"""🚨 A REAL SPECIMEN of the shape, and the reason this claim is worth
    anything. The corpus records it as *"a TV edit that drifts against the
    BluRay - no consistent offset exists"*: its buckets want offsets from
    -89 s to -108 s, a 19 s spread that is not any framerate ratio.

    ⚠ Asserted as *not written, and diagnosed*, not as the word "drift" --
    which explanation the walk reaches depends on how the failing buckets fall,
    and pinning that would be pinning the corpus rather than the rule."""
    fit = _aligned(oracle, "diamond01", "diamond01_tv")
    assert fit is not None
    # ⭐ It scores 2.02x and is MEASURABLE -- so it clears the not-a-match
    # branch and the escalation floor, and the only thing standing between it
    # and being written is the whole-runtime walk. That is what makes it the
    # specimen for this claim rather than another wrong pair.
    assert fit.measurable and fit.excess > REFUSE_BELOW
    assert not fit.holds_throughout
    v = V.verdict(fit)
    assert v.outcome == V.REFUSED, "%s: %s" % (v.outcome, v.reason)
    assert v.runtime_check == u"failed"
    assert v.reason.strip()


# ---------------------------------------------------------------------------
# the SEAM -- the verdict is only worth anything if its consumers accept it
# ---------------------------------------------------------------------------

def test_a_verdict_drives_A11s_decide_END_TO_END(tmp_path):
    u"""⭐ `doctrine/verification`: *test the WRAPPER and the thing together.*
    Every case in that ledger entry had the wrapper lying while the functions
    underneath were provably correct.

    `explicit.decide()` was written before `verdict.py` existed, against a
    described shape rather than a real object. This is the only check that the
    real one satisfies it.
    """
    from tsubasa import explicit as E
    video = tmp_path / "Show - 01.mkv"
    video.write_bytes(b"\x1aE\xdf\xa3" + b"0" * 2048)
    subtitle = tmp_path / "Show - 01.ja.srt"
    subtitle.write_text(u"1\n00:00:01,000 --> 00:00:02,000\nhi\n\n",
                        encoding="utf-8")

    plan = E.explicit_pairs(pair_args=[(str(video), str(subtitle))])
    assert plan.accepted == 1, plan.summary()
    pair = plan.pairs[0]

    good = V.verdict(make_fit(excess=6.0))
    assert pair.decide(good).write is True

    bad = V.verdict(make_fit(excess=6.0,
                             failing=[(0.0, 40, 0.30, +10.0, 0.62)]))
    assert pair.decide(bad).write is False

    # ⚠ A forced write is the most dangerous thing this feature can do, and it
    # may never be relabelled a success. `LEDGER.md` §Interface: a GUI painted
    # a run green because "11 confident, 1 refused" contains `confident`.
    forced = pair.decide(bad, force=True)
    assert forced.write is True and forced.outcome == V.REFUSED


def test_an_ERROR_verdict_is_not_overridden_by_force(tmp_path):
    u"""⛔ Ruled 2026-09-08: `--force` overrides a REFUSAL, never an ERROR --
    ERROR means unmeasured, so there is no offset to stand behind."""
    from tsubasa import explicit as E
    video = tmp_path / "Show - 01.mkv"
    video.write_bytes(b"\x1aE\xdf\xa3" + b"0" * 2048)
    subtitle = tmp_path / "Show - 01.ja.srt"
    subtitle.write_text(u"1\n00:00:01,000 --> 00:00:02,000\nhi\n\n",
                        encoding="utf-8")
    pair = E.explicit_pairs(pair_args=[(str(video), str(subtitle))]).pairs[0]

    unmeasured = V.verdict(make_fit(excess=5.15, n=1, n_sub=1))
    assert unmeasured.outcome == V.ERROR
    decision = pair.decide(unmeasured, force=True)
    assert decision.write is False
    assert "force" in decision.reason.lower()


def test_a_real_CUT_file_is_written_WITH_its_segments(oracle):
    u"""⭐ The case that separates *"refuses cut files"* from *"repairs them"*.
    A broadcast cut the aligner splits correctly is a CONFIDENT multi-segment
    answer, not a refusal -- refusing it would be the tool failing at the job
    it exists to do."""
    v = V.verdict(_aligned(oracle, "clevatess07_abema", "clevatess07_nanako"))
    assert v.outcome == V.CONFIDENT, "%s: %s" % (v.outcome, v.reason)
    assert len(v.segments) > 1, (
        "the cut file resolved to one segment, so this check is not looking "
        "at what it claims to")
