# -*- coding: utf-8 -*-
"""
Negative controls for the aligner. RUNBOOK B1, spec/07-test-plan.md.

🚨 THE POINT: a positive result is not evidence until the same instrument has
been shown to say NO. `subsync` runs 7/7 positive, 5/5 negative, 3/3 cut and is
trustworthy for that reason -- and the one time a control was dropped as
"redundant", a file whose opening cues had been DELETED invented a 127-second
break and passed every other test.

Each control corrupts a KNOWN-GOOD pair by a known amount, so the right answer
is known without any new ground truth. One per positive class:

    time-reversed            REFUSED
    per-cue jitter sigma=4s  REFUSED
    a different show         REFUSED
    a sequel season          REFUSED  (from the oracle's MUST_REFUSE)
    opening cues DELETED     🚨 ONE segment -- no phantom break
"""
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tsubasa.align import MIN_EXCESS, align, unique_starts   # noqa: E402
from tsubasa.paths import load_config, oracle_root           # noqa: E402

#: What a control must score BELOW to count as refused. The verdict the product
#: ships is a band (spec/05-interface.md); this is the segment-level floor.
REFUSE_BELOW = MIN_EXCESS


@pytest.fixture(scope="module")
def material():
    """A known-good pair, plus a different show. -> (R, A, duration, other_A)"""
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
    sys.argv = ["pytest"]
    try:
        import subsync as S
        import corpus as C
    finally:
        sys.argv = argv
    ref = S.parse_cues(str(vidref / "rezero-53.ass"))
    sub = S.parse_cues(str(mega / C.SUBS["rezero53_netflix"]))
    other = S.parse_cues(str(mega / C.SUBS["gurren01_netflix"]))
    duration = max(max(c[1] for c in ref), max(c[1] for c in sub))
    return (unique_starts([c[0] for c in S.dialogue_only(ref)]),
            unique_starts([c[0] for c in sub]), duration,
            unique_starts([c[0] for c in other]))


def test_the_positive_control_is_actually_positive(material):
    """⛔ FIRST. A negative control proves nothing if the instrument says no to
    everything -- a suite of five refusals passes trivially against a function
    that returns zero."""
    R, A, duration, _other = material
    fit = align(R, A, duration)
    assert fit.excess >= REFUSE_BELOW, (
        "the KNOWN-GOOD pair scored %.2fx; every refusal below is meaningless"
        % fit.excess)
    assert not fit.is_cut, "the known-good pair is not cut"


def test_a_time_reversed_subtitle_is_refused(material):
    R, A, duration, _other = material
    fit = align(R, np.sort(duration - A), duration)
    assert fit.excess < REFUSE_BELOW, "time-reversed scored %.2fx" % fit.excess


def test_a_jittered_subtitle_is_refused(material):
    """Every cue displaced independently by ~4 s. The show is right, the
    episode is right, and the timing carries no information."""
    R, A, duration, _other = material
    jittered = np.sort(A + np.random.default_rng(1).normal(0, 4.0, len(A)))
    fit = align(R, jittered, duration)
    assert fit.excess < REFUSE_BELOW, "jittered scored %.2fx" % fit.excess


def test_a_different_shows_subtitle_is_refused(material):
    R, _A, duration, other = material
    fit = align(R, other, duration)
    assert fit.excess < REFUSE_BELOW, "a different show scored %.2fx" % fit.excess


@pytest.mark.parametrize("dropped", [30, 60, 90])
def test_deleted_opening_cues_do_not_invent_a_break(material, dropped):
    """🚨 THE CONTROL THAT WAS ONCE REMOVED AS REDUNDANT.

    The subtitle is not SHIFTED, it is MISSING its opening. A split search will
    happily explain the hole with a break: with the overall-gain guard dropped,
    this exact case "found" a 127-second break and cleared every other test.

    ⛔ The assertion is on the SHAPE, not the score. The file still aligns --
    that is what makes it dangerous -- so a check on `excess` alone passes while
    the tool writes a fabricated cut.
    """
    R, A, duration, _other = material
    fit = align(R, A[dropped:], duration)
    assert not fit.is_cut, (
        "a subtitle missing its first %d cues was split into %d segments at %s "
        "-- a phantom break invented to explain missing data"
        % (dropped, len(fit.segments), [round(s, 1) for s, _o in fit.segments[:-1]]))


def test_a_sequel_season_sharing_an_episode_number_is_refused(material):
    """`Ace of Diamond Act II` episode 1 is not `Ace of Diamond` episode 1.
    Same franchise, same number, same studio -- and a different episode."""
    root = oracle_root(load_config(ROOT), ROOT)
    import corpus as C
    import subsync as S
    ref = S.parse_cues(str(root / "tests" / "fixtures" / "vidref" / "diamondnoace-01.ass"))
    sub = S.parse_cues(str(root / "SubtitleMegaTest" / C.SUBS["diamondact2_01"]))
    R = unique_starts([c[0] for c in S.dialogue_only(ref)])
    A = unique_starts([c[0] for c in sub])
    fit = align(R, A, max(max(c[1] for c in ref), max(c[1] for c in sub)))
    assert fit.excess < REFUSE_BELOW, "a sequel season scored %.2fx" % fit.excess


def test_an_empty_or_tiny_input_cannot_produce_a_confident_answer(material):
    """⛔ Below the measurable floor. spec/06-edge-cases.md §5.1: one or two
    cues is an ERROR, stated as such -- never a confident zero."""
    R, A, duration, _other = material
    for tiny in (unique_starts([]), unique_starts([10.0]), unique_starts([10.0, 20.0])):
        fit = align(R, tiny, duration)
        assert fit.excess < REFUSE_BELOW, (
            "%d subtitle cues produced %.2fx" % (len(tiny), fit.excess))
        fit_r = align(tiny, A, duration)
        assert fit_r.excess < REFUSE_BELOW, (
            "%d reference cues produced %.2fx" % (len(tiny), fit_r.excess))


def test_the_break_size_guard_is_load_bearing(monkeypatch):
    """🚨 THE ORPHANED-KARAOKE CASE, and the one inherited guard this search
    still needs.

    The Gurren Lagann BluRay reference opens with fifteen OP-karaoke cues the
    subtitle simply does not have. Those orphans will find a "home" a hundred
    seconds away -- with only fourteen cues, the best of many candidate offsets
    scores ~57% BY CHANCE, which clears every guard that looks at match rate.
    A commercial break is tens of seconds; two minutes is something else.

    ⭐ This test asserts the guard DOES something, by removing it and watching
    the answer change. Measured 2026-09-08 across 39 cases (29 oracle pairs and
    10 adversarial controls): `MAX_BREAK` is the ONLY inherited guard whose
    removal changes any answer under the histogram search -- see
    `LEDGER.md` §Logic. Without a check like this it would look like dead code
    and be "simplified" away.
    """
    root = oracle_root(load_config(ROOT), ROOT)
    if not root.is_dir():
        pytest.skip("SKIPPED, NOT PASSED: the oracle is absent")
    import corpus as C
    import subsync as S
    import tsubasa.align
    module = sys.modules["tsubasa.align.fit"]

    ref = S.parse_cues(str(root / "tests" / "fixtures" / "vidref" / "gurrenlagann-01.ass"))
    sub = S.parse_cues(str(root / "SubtitleMegaTest" / C.SUBS["gurren01_bluray"]))
    R = unique_starts([c[0] for c in S.dialogue_only(ref)])
    A = unique_starts([c[0] for c in sub])
    duration = max(max(c[1] for c in ref), max(c[1] for c in sub))

    guarded = align(R, A, duration)
    assert not guarded.is_cut, (
        "this pair is NOT cut and the guard is supposed to be why; it split at %s"
        % [round(s, 1) for s, _o in guarded.segments[:-1]])

    monkeypatch.setattr(module, "MAX_BREAK", 1e9)
    unguarded = align(R, A, duration)
    assert unguarded.is_cut, (
        "removing MAX_BREAK changed nothing, so this check proves the guard is "
        "load-bearing only by assertion. Either the material no longer contains "
        "the orphaned-cue case, or the guard is now dead -- find out which "
        "before deleting either the guard or this test")


def test_a_shifted_file_is_recovered_rather_than_refused(material):
    """⚠ The control on the controls, and a mistake this project has already
    made: a "shifted" negative is NOT a negative. A search that spans the shift
    simply recovers it, which is the aligner working. It is here so nobody
    re-adds it to the list above."""
    R, A, duration, _other = material
    base = align(R, A, duration).segments[0][1]
    for shift in (-45.0, +18.5):
        fit = align(R, A - shift, duration)
        assert abs((fit.segments[0][1] - base) - shift) < 0.35, (
            "a %+.1f s shift was not recovered: %+.3f vs %+.3f"
            % (shift, fit.segments[0][1], base + shift))
