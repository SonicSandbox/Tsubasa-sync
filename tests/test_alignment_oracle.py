# -*- coding: utf-8 -*-
"""
The aligner against MEASURED GROUND TRUTH. RUNBOOK step B1, spec/12-alignment.md §8.

⭐ THIS IS THE SUITE THAT MAKES AN EFFICIENCY CHANGE ADMISSIBLE. B1 replaced a
4,800-offset scan with a difference histogram and made a pair 135x cheaper; the
only thing standing between that and a silent accuracy loss is 29 pairs of truth
that were measured without it.

    "An efficiency change must not change the answer." -- spec/00-INDEX.md §Rule 4

The truth comes from `subsync/tests/corpus.py`, derived TWO independent ways
that agree -- cross-comparing the 2-3 subtitle files each episode ships, and
against the video's own embedded track -- and **neither route uses a split
fitter**, so this is not the tool grading its own homework.

🚨 WHAT IS ASSERTED, AND WHY IT IS NOT "the split time matches"

The corpus is explicit that the recorded split TIME is loose:

    "A split is accepted anywhere inside the quiet gap around the real break,
     so this is deliberately loose -- what matters is that EVERY cue lands on
     the right side of it."

A real break falls in a silence. Every cut position across that silence assigns
every CUE the same offset and differs only in the timestamp reported, so
asserting the number invents a precision the evidence does not contain. This
suite therefore asserts, per pair:

  1. the OFFSETS, within the corpus's own per-pair tolerance
  2. every cue OUTSIDE the reported undetermined span gets the truth's offset
  3. the truth's break lies INSIDE that span (or within the corpus's SPLIT_TOL)

⚠ (3) is what stops (2) being gamed: a fit could pass (2) trivially by
declaring the whole file undetermined, and (3) plus the offset check forbids it.
"""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tsubasa.align import MR_TOL, align, unique_starts   # noqa: E402
from tsubasa.paths import load_config, oracle_root       # noqa: E402


@pytest.fixture(scope="module")
def oracle():
    """(subsync module, corpus module, megatest dir, vidref dir).

    ⚠ A skip SAYS SO. `pytest.skip` with a bare reason reads as a pass in a
    summary line; the runner counts checks, so a suite that silently skips
    everything is a green zero.
    """
    root = oracle_root(load_config(ROOT), ROOT)
    if not root.is_dir():
        pytest.skip("SKIPPED, NOT PASSED: the oracle is absent at %s" % root)
    mega = root / "SubtitleMegaTest"
    vidref = root / "tests" / "fixtures" / "vidref"
    if not (mega.is_dir() and vidref.is_dir()):
        pytest.skip("SKIPPED, NOT PASSED: the oracle's corpus or fixtures are absent")
    for p in (str(root), str(root / "tests")):
        if p not in sys.path:
            sys.path.insert(0, p)
    argv = sys.argv
    sys.argv = ["pytest"]                      # subsync parses argv on import
    try:
        import subsync
        import corpus
    finally:
        sys.argv = argv
    return subsync, corpus, mega, vidref


def _pairs(oracle):
    """Every ground-truth pair, as (label, ref_cues, sub_cues, truth, tol)."""
    S, C, mega, vidref = oracle
    out = []
    for (rk, sk), (truth, tol) in sorted(C.TRUTH_SUB_VS_SUB.items()):
        out.append(("%s vs %s" % (rk, sk),
                    S.parse_cues(str(mega / C.SUBS[rk])),
                    S.parse_cues(str(mega / C.SUBS[sk])), truth, tol))
    video_of = {sk: vk for vk, subs in C.EXPECTED_PAIRS.items() for sk in subs}
    for sk, (truth, tol) in sorted(C.TRUTH_VS_VIDEO.items()):
        fixture = C.VIDEOS[video_of[sk]][1]
        if fixture is None:                    # a name-only placeholder video
            continue
        out.append((sk, S.parse_cues(str(vidref / fixture)),
                    S.parse_cues(str(mega / C.SUBS[sk])), truth, tol))
    return out


def _fit(S, ref, sub):
    duration = max(max(c[1] for c in ref), max(c[1] for c in sub))
    R = unique_starts([c[0] for c in S.dialogue_only(ref)])
    A = unique_starts([c[0] for c in sub])
    return R, align(R, A, duration)


def _offset_at(segments, t):
    for split, off in segments:
        if split is None or t < split:
            return off
    return segments[-1][1]


# --------------------------------------------------------------------------
# ⭐ the three claims, over every pair
# --------------------------------------------------------------------------

def test_the_oracle_has_the_pairs_we_think_it_has(oracle):
    """⛔ ZERO CHECKS IS A FAILURE, NOT A PASS. Every assertion below is driven
    from the corpus, so an empty corpus would make this whole suite green while
    proving nothing. Derived, never pinned."""
    pairs = _pairs(oracle)
    assert len(pairs) >= 25, "only %d ground-truth pairs found" % len(pairs)
    assert sum(1 for _l, _r, _s, truth, _t in pairs if len(truth) > 1) >= 5, (
        "fewer than five CUT pairs -- the split search would be untested")


def test_every_offset_matches_the_measured_truth(oracle):
    S, _C, _m, _v = oracle
    bad = []
    for label, ref, sub, truth, tol in _pairs(oracle):
        _R, fit = _fit(S, ref, sub)
        if len(fit.segments) != len(truth):
            bad.append("%s: %d segments, truth has %d"
                       % (label, len(fit.segments), len(truth)))
            continue
        for (_gs, got), (_ts, want) in zip(fit.segments, truth):
            if abs(got - want) > tol:
                bad.append("%s: %+.3f vs truth %+.3f (tol %.2f)"
                           % (label, got, want, tol))
    assert not bad, "offsets disagree with the oracle:\n  " + "\n  ".join(bad)


def test_every_cue_outside_an_undetermined_span_gets_the_right_offset(oracle):
    """⭐ THE CRITERION THAT MATTERS -- what a viewer would actually see.

    🚨 It is what caught the worst defect in this class: a file reported
    "verified" off three checkpoints that all fell AFTER a cut, with its first
    twelve minutes wrong the whole time.
    """
    S, _C, _m, _v = oracle
    bad = []
    for label, ref, sub, truth, _tol in _pairs(oracle):
        R, fit = _fit(S, ref, sub)
        wrong = [t for t in R if not fit.undetermined(t)
                 and abs(_offset_at(fit.segments, t) - _offset_at(truth, t)) > MR_TOL]
        if wrong:
            bad.append("%s: %d of %d cues get an offset more than %.2fs from "
                       "truth (first at %.1fs)"
                       % (label, len(wrong), len(R), MR_TOL, wrong[0]))
    assert not bad, "cues are given the wrong offset:\n  " + "\n  ".join(bad)


def test_the_truth_break_lies_inside_the_span_we_declare_undetermined(oracle):
    """⚠ The guard on the guard. Without this, a fit could pass the cue check
    by declaring the entire file undetermined and asserting nothing at all."""
    S, C, _m, _v = oracle
    bad = []
    for label, ref, sub, truth, _tol in _pairs(oracle):
        _R, fit = _fit(S, ref, sub)
        if len(fit.segments) != len(truth):
            continue
        for (got_split, _o), (want_split, _w) in zip(fit.segments, truth):
            if want_split is None or got_split is None:
                continue
            span = next((s for s in fit.gaps if s[0] <= got_split <= s[1]),
                        (got_split, got_split))
            inside = span[0] - 1e-6 <= want_split <= span[1] + 1e-6
            if not (inside or abs(got_split - want_split) <= C.SPLIT_TOL):
                bad.append("%s: break at %.1fs, truth %.1fs, undetermined span "
                           "%.1f-%.1f" % (label, got_split, want_split, span[0], span[1]))
    assert not bad, "a break is reported outside its own uncertainty:\n  " + "\n  ".join(bad)


def test_an_undetermined_span_never_swallows_the_file(oracle):
    """⛔ The other half of the same guard, stated as a bound: uncertainty is a
    silence between two cues, not a licence."""
    S, _C, _m, _v = oracle
    for label, ref, sub, _truth, _tol in _pairs(oracle):
        R, fit = _fit(S, ref, sub)
        undetermined = sum(1 for t in R if fit.undetermined(t))
        assert undetermined <= max(12, 0.10 * len(R)), (
            "%s: %d of %d cues declared undetermined" % (label, undetermined, len(R)))


# --------------------------------------------------------------------------
# the cut files, specifically
# --------------------------------------------------------------------------

def test_every_cut_file_is_found_to_be_cut(oracle):
    """🚨 Every broadcast capture in this corpus IS cut and every streaming rip
    is not -- and all four breaks land in the first 3.5 minutes, which is the
    half a spot-check never looks at. Four files were confidently mis-timed for
    their opening minutes by exactly this."""
    S, _C, _m, _v = oracle
    for label, ref, sub, truth, _tol in _pairs(oracle):
        if len(truth) < 2:
            continue
        _R, fit = _fit(S, ref, sub)
        assert fit.is_cut, "%s is CUT and was fitted with one offset" % label
        assert len(fit.segments) == len(truth), (
            "%s: %d segments, truth has %d" % (label, len(fit.segments), len(truth)))


def test_no_uncut_file_is_split(oracle):
    """⛔ The direction that costs correctness. A split adds a free parameter,
    and a free parameter will overfit if you let it."""
    S, _C, _m, _v = oracle
    for label, ref, sub, truth, _tol in _pairs(oracle):
        if len(truth) != 1:
            continue
        _R, fit = _fit(S, ref, sub)
        assert not fit.is_cut, (
            "%s is NOT cut and was split into %d segments at %s"
            % (label, len(fit.segments), [s for s, _o in fit.segments[:-1]]))


# --------------------------------------------------------------------------
# properties that need no ground truth
# --------------------------------------------------------------------------

def test_a_file_aligned_against_itself_returns_exactly_zero(oracle):
    """A named suite assertion in spec/06-edge-cases.md §5.1."""
    S, C, mega, _v = oracle
    for key in ("katainaka02_erai", "rezero53_netflix", "geass05_lambert"):
        cues = S.parse_cues(str(mega / C.SUBS[key]))
        R = unique_starts([c[0] for c in S.dialogue_only(cues)])
        fit = align(R, R, max(c[1] for c in cues))
        assert len(fit.segments) == 1, "%s self-aligned into %d segments" % (key, len(fit.segments))
        assert abs(fit.segments[0][1]) < 1e-6, "%s self-aligned to %+.6f" % (key, fit.segments[0][1])


def test_the_answer_holds_across_the_whole_runtime(oracle):
    """The bucket walk is computed from the same pass. On pairs the oracle
    calls correct, it must not report the answer failing."""
    S, _C, _m, _v = oracle
    bad = []
    for label, ref, sub, truth, _tol in _pairs(oracle):
        _R, fit = _fit(S, ref, sub)
        if len(fit.segments) == len(truth) and not fit.holds_throughout:
            bad.append("%s: %d failing bucket(s) on a correct answer"
                       % (label, len(fit.failing)))
    assert not bad, "\n  ".join(bad)


def test_the_pairs_the_oracle_says_to_refuse_score_low(oracle):
    """🚨 MUST_REFUSE. A confidently wrong shift is worse than none, and these
    are the pairs a filename would happily propose: a sequel season sharing an
    episode number, a different show with the same number, a 1985 OVA against a
    2025 episode."""
    S, C, mega, vidref = oracle
    checked = 0
    for sk, vk, why in C.MUST_REFUSE:
        fixture = C.VIDEOS[vk][1]
        if fixture is None:
            continue
        ref = S.parse_cues(str(vidref / fixture))
        sub = S.parse_cues(str(mega / C.SUBS[sk]))
        _R, fit = _fit(S, ref, sub)
        checked += 1
        assert fit.excess < 2.5, (
            "%s vs %s scored %.2fx and would be ACCEPTED -- %s"
            % (sk, vk, fit.excess, why))
    assert checked >= 4, "only %d refusal pairs were checked" % checked
