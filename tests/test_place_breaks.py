# -*- coding: utf-8 -*-
u"""
`align.place_breaks` -- a cut file's break, placed by the lines' own extents
inside the span `fit()` left it in (0.1.12). Hermetic: hand-built lines.

⭐ Each case is a real shape scaled down. A dense scene, then the opening
song's silence, then the next scene; the subtitle carries the same lines, the
first part shifted by one offset and the rest by another. On cue STARTS alone
every split inside the silence -- and some inside the scenes -- ties, and
`fit()` reports the earliest. `tests/test_alignment_oracle.py` carries the same
claim on the oracle's real cut pairs; the measurement is in `place_breaks`.

🚨 The reference lines here are given DIFFERENT lengths on purpose. A lines-
of-equal-length fixture would let a placement that ignores the ends pass.
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

AL = sys.modules.setdefault("tsubasa.align",
                            __import__("tsubasa.align", fromlist=["fit"]))
FIT = sys.modules["tsubasa.align.fit"]
from tsubasa.align import Fit, mapper_for, place_breaks, removed_spans  # noqa: E402

#: The scene before the song (reference seconds) and after it. Lengths vary.
BEFORE = [(40.0, 42.6), (43.1, 47.9), (48.4, 49.5), (50.2, 53.8), (54.3, 55.1),
          (55.9, 59.7), (60.2, 61.4), (62.0, 65.3), (65.9, 68.2), (68.9, 70.0)]
AFTER = [(160.0, 161.9), (162.5, 166.8), (167.4, 168.3), (169.0, 172.6),
         (173.2, 174.0), (174.7, 178.9), (179.5, 181.2), (181.8, 185.5)]
REF = BEFORE + AFTER


def subtitle_for(o1, o2):
    u"""The same lines, as a subtitle that needs `o1` before the break and
    `o2` after it: subtitle time = reference time - offset."""
    return ([(s - o1, e - o1) for s, e in BEFORE]
            + [(s - o2, e - o2) for s, e in AFTER])


def fit_at(split, gap, o1, o2):
    u"""What `fit()` hands back for a cut file: the split at the earliest tie
    and the span it is undetermined across. The other fields do not take part."""
    return Fit([(split, o1), (None, o2)], 0.9, 0.1, (o1, 0.5), [], [], [o1, o2],
               len(REF), len(REF), [gap])


def fates(sub, segments):
    u"""Per subtitle line: the reference start it is written at, or None when
    the writer drops it (`removed_spans`, `D9`)."""
    mapper, gone = mapper_for(segments), removed_spans(segments)
    return [None if any(a <= s < b for a, b in gone) else mapper(s)
            for s, _e in sub]


@pytest.mark.parametrize("o1, o2", [(-1.2, +8.8),     # a positive jump
                                    (+0.4, -9.8)])    # a NEGATIVE one (D9)
def test_a_break_left_at_the_earliest_tie_is_moved_into_the_silence(o1, o2):
    u"""⭐ The defect, then the fix, on one fixture. With the split at the
    earliest tie (50.2, inside the scene) the lines from there to the song take
    the second offset -- or, on a negative jump, ten seconds of them are
    DROPPED. Placed, every line lands back on its own reference line."""
    sub = subtitle_for(o1, o2)
    early = fit_at(50.2, (50.2, 175.0), o1, o2)
    want = [s for s, _e in REF]

    before = fates(sub, early.segments)
    assert sum(1 for got, w in zip(before, want)
               if got is None or abs(got - w) > 0.01) >= 5, (
        "the fixture does not show the defect, so this check proves nothing")

    placed = place_breaks(early, REF, sub)
    after = fates(sub, placed.segments)
    wrong = [(w, got) for got, w in zip(after, want)
             if got is None or abs(got - w) > 1e-6]
    assert not wrong, "lines written off their own reference line: %s" % wrong
    split = placed.segments[0][0]
    assert 70.0 < split < 160.0, split
    # ⭐ The offsets are `fit()`'s, untouched.
    assert [o for _s, o in placed.segments] == [o1, o2]


def test_the_span_becomes_the_silence_and_no_line_starts_inside_it():
    u"""The span narrows to the stretch between the last line surely before
    the break and the first surely after it -- and never grows past `fit()`'s."""
    o1, o2 = -1.2, +8.8
    sub = subtitle_for(o1, o2)
    placed = place_breaks(fit_at(50.2, (50.2, 175.0), o1, o2), REF, sub)
    (lo, hi), = placed.gaps
    assert lo == pytest.approx(70.0) and hi == pytest.approx(160.0)
    assert 50.2 <= lo <= hi <= 175.0
    starts = [w for w in fates(sub, placed.segments) if w is not None]
    assert not [w for w in starts if lo < w < hi], (lo, hi, starts)


def test_a_line_on_the_edge_is_never_dropped_by_round_off():
    u"""🚨 Found on yomi18: a split placed at EXACTLY `start + o2` put that line
    3e-14 s inside the removed stretch and the writer dropped it. Offsets whose
    sums do not round cleanly, as real ones do not."""
    o1, o2 = 0.407, -9.7795
    sub = subtitle_for(o1, o2)
    placed = place_breaks(fit_at(50.2, (50.2, 175.0), o1, o2), REF, sub)
    assert None not in fates(sub, placed.segments)
    split = placed.segments[0][0]
    edges = [s + o for s, _e in sub for o in (o1, o2)]
    assert min(abs(split - e) for e in edges) > 0.1, split


def test_among_ties_the_placement_dropping_fewest_lines_wins():
    u"""⛔ A line the reference has nothing for (a gasp, a sound effect)
    scores the same kept or dropped, and a dropped line is gone from the
    written file. So a tie goes to keeping it."""
    o1, o2 = +0.4, -9.8
    gasp = (71.0 - o1, 71.8 - o1)                 # subtitle-only, after the scene
    sub = subtitle_for(o1, o2) + [gasp]
    placed = place_breaks(fit_at(50.2, (50.2, 175.0), o1, o2), REF, sub)
    assert None not in fates(sub, placed.segments)


def test_a_one_segment_fit_comes_back_as_the_same_object():
    one = Fit([(None, 1.5)], 0.9, 0.1, (1.5, 0.9), [], [], [1.5], 9, 9, [])
    assert place_breaks(one, REF, subtitle_for(1.5, 1.5)) is one


@pytest.mark.parametrize("ref, sub", [
    ([], subtitle_for(-1.2, 8.8)),
    (REF, []),
    # Lines with no extent -- a container cue with no duration is (s, s).
    ([(s, s) for s, _e in REF], [(s, s) for s, _e in subtitle_for(-1.2, 8.8)]),
], ids=["no reference lines", "no subtitle lines", "no line has an extent"])
def test_lines_that_cannot_tell_leave_the_fit_as_it_was(ref, sub):
    early = fit_at(50.2, (50.2, 175.0), -1.2, 8.8)
    assert place_breaks(early, ref, sub) is early


def test_the_split_never_leaves_the_span_fit_reported():
    u"""Every guard and offset `fit()` settled stands only inside its own tie;
    so the lines may choose a point in the span, never one outside it -- even
    where they would like to."""
    o1, o2 = -1.2, +8.8
    sub = subtitle_for(o1, o2)
    narrow = fit_at(52.0, (52.0, 58.0), o1, o2)   # a span inside the scene
    placed = place_breaks(narrow, REF, sub)
    split = placed.segments[0][0]
    assert 52.0 <= split <= 58.0
    assert 52.0 <= placed.gaps[0][0] <= placed.gaps[0][1] <= 58.0


def test_two_breaks_are_placed_each_inside_its_own_span():
    u"""A batch file has many breaks. Each is read only between its
    neighbours, so one boundary's lines never vote on the next."""
    o1, o2, o3 = -1.2, +8.8, +20.0
    later = [(s + 200.0, e + 200.0) for s, e in BEFORE]       # 240-270
    ref = REF + later
    sub = subtitle_for(o1, o2) + [(s - o3, e - o3) for s, e in later]
    two = Fit([(50.2, o1), (190.0, o2), (None, o3)], 0.9, 0.1, (o1, 0.5), [],
              [], [o1, o2, o3], len(ref), len(sub),
              [(50.2, 175.0), (186.0, 239.0)])
    placed = place_breaks(two, ref, sub)
    s1, s2 = placed.segments[0][0], placed.segments[1][0]
    assert 70.0 < s1 < 160.0 and 185.5 < s2 < 240.0 and s1 < s2
    want = [s for s, _e in ref]
    got = fates(sub, placed.segments)
    assert all(g is not None and abs(g - w) < 1e-6 for g, w in zip(got, want))


def test_a_line_moved_onto_a_line_ALREADY_COVERED_gains_nothing():
    u"""⭐ Why each REFERENCE line counts once. Two subtitle lines say one
    reference line's words here (a split translation): `a` exactly, and `b`
    -- the second segment's first line -- a little late. Moved by the jump,
    `a` would land squarely on the line `b` already covers. Counted per
    subtitle line, that move scores as well as `a` staying on its own line,
    the placements tie, and the earliest one hands `a` the wrong offset."""
    o1, o2 = 0.0, 10.0
    ref = [(30.0, 32.0), (34.0, 36.0), (100.0, 102.0),        # ... A
           (110.0, 112.0), (114.0, 116.0), (118.0, 120.0)]     # B ...
    sub = [(30.0, 32.0), (34.0, 36.0), (100.0, 102.0),        # a = A at o1
           (100.6, 102.6), (104.0, 106.0), (108.0, 110.0)]     # b ~ B at o2
    placed = place_breaks(fit_at(99.0, (99.0, 112.0), o1, o2), ref, sub)
    mapper = mapper_for(placed.segments)
    assert mapper(100.0) == pytest.approx(100.0), placed.segments
    assert mapper(100.6) == pytest.approx(110.6), placed.segments


def test_placed_breaks_never_come_out_of_order():
    u"""⛔ Found by an adversarial fuzz (0.1.12's review): each break is placed
    inside its OWN span, and spans that overlap -- or opposite jumps crossing
    in subtitle time -- put 245 of 4,000 multi-break fits out of order, so
    `mapper_for` gave a middle segment nothing. Placed fits whose input was in
    order stay in order, in reference and in subtitle time. Seeded."""
    import random
    from tsubasa.align import subtitle_boundaries
    rnd = random.Random(1)
    checked = 0
    for _ in range(600):
        n = rnd.choice([3, 3, 4])
        offs = [rnd.uniform(-100, 100) for _ in range(n)]
        cuts = sorted(rnd.uniform(50, 900) for _ in range(n - 1))
        ref, t = [], 0.0
        while t < 1000:
            ref.append((t, t + rnd.uniform(0.3, 4)))
            t += rnd.uniform(0.2, 5)
        side = lambda x: sum(1 for c in cuts if x >= c)       # noqa: E731
        sub = [(s - offs[side(s)], e - offs[side(s)]) for s, e in ref
               if rnd.random() < 0.8]
        gaps = [(c - rnd.uniform(0, 80), c + rnd.uniform(0, 80)) for c in cuts]
        segs = [(gaps[i][0], offs[i]) for i in range(n - 1)] + [(None, offs[-1])]
        splits = [s for s, _o in segs[:-1]]
        before = [b for b, _f, _t in subtitle_boundaries(segs)]
        if splits != sorted(splits) or before != sorted(before):
            continue
        checked += 1
        fit = Fit(segs, 0.9, 0.1, (offs[0], 0.5), [], [], offs, len(ref),
                  len(sub), gaps)
        placed = place_breaks(fit, ref, sub)
        got = [s for s, _o in placed.segments[:-1]]
        after = [b for b, _f, _t in subtitle_boundaries(placed.segments)]
        assert got == sorted(got) and len(set(got)) == len(got), (segs, got)
        assert after == sorted(after), (segs, placed.segments)
    assert checked >= 100, checked
