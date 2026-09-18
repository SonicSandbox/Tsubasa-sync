# -*- coding: utf-8 -*-
r"""
The alignment primitive: offset, cuts and the whole-runtime walk, in one pass.
RUNBOOK step B1. Authority: spec/12-alignment.md.

⭐ THE IDEA, AND WHY IT IS NOT A SPEEDUP

`subsync` asks "if I shift the subtitle by X, how many reference lines land?"
for ~4,800 candidate X, then re-asks it per split position, then re-asks it per
bucket. Three separate sweeps of the same question, 6.6 s per pair.

    Every pair (r, a) with |r - a| <= window contributes one difference
    d = r - a. Histogram those differences and box-smooth by 2*MR_TOL: the
    value at bin `o` IS the match count at offset `o`.

So one pass over the differences answers EVERY offset at once -- and, unlike a
scan, it still holds the individual differences, which is what gives sub-bin
refinement for free.

🚨 AND THE SECOND DIMENSION IS NOT OPTIONAL. Bucketed by reference time as well
as by offset, a minority segment becomes visible. Globally it cannot be: at a
random offset the expected hit count is chance * |R| -- about 60 for 300 cues at
20% -- so a pre-break segment carrying 8% of the cues contributes ~23 hits,
inside the noise of thousands of bins. subsync only sees such a segment because
it rescans every offset per split position. Measured (spec/08-probes.md §J2):
with global candidates only, both real broadcast cuts were MISSED; with
per-bucket candidates added, 29 of 29 offsets are right.

⛔ WHAT DID NOT CHANGE: the objective, and every guard. This module decides
WHERE TO LOOK. `objective.py` decides what is believable, and it is subsync's,
constant for constant. An efficiency change must not change the answer --
`tests/test_alignment_oracle.py` is what makes that provable.

⚠ Memory is bounded by the difference list, not by the search window: |R| times
the average number of subtitle cues within `window`. A 24-minute episode is
~60k floats; a four-hour concatenation ~1.7M.
"""
# ⚠ NOT `import numpy as np` — DEFERRED. numpy costs 245 ms and is used only
# INSIDE the functions below, but importing any tsubasa submodule runs the
# package `__init__`, which reaches here — so the GUI paid for the numeric
# stack to draw a window. `..lazynp` carries the whole reasoning, including
# why the obvious fix (a lazy package `__init__`) is measured to break a
# pinned compatibility shape.
from ..lazynp import numpy_when_needed

np = numpy_when_needed(globals())

from .objective import (BUCKET, BUCKET_LOCAL_WINDOW, BUCKET_RATE_SLACK,
                        MAX_BREAK, MAX_BUCKET_DRIFT, MIN_ALIGNABLE_CUES,
                        MIN_BREAK, MIN_BUCKET_CUES, MIN_CUES, MIN_EXCESS,
                        MIN_LOCAL_MARGIN, MIN_SPLIT_GAIN, MR_TOL, WINDOW,
                        bucket_noise_floor, chance_rate, hits)

#: Histogram bin, seconds. Fine enough that the box smoothing, not the bin, sets
#: the resolution; the refinement below then works from the raw differences.
BIN = 0.01
#: How many peaks to take from the whole-file histogram...
K_GLOBAL = 6
#: ...and from each time bucket's own histogram. ⭐ This is the line that makes
#: a minority segment visible. See the module docstring.
K_BUCKET = 2
#: Bucket width used for CANDIDATE GENERATION only (the walk keeps BUCKET).
CANDIDATE_BUCKET = 120.0
#: Two candidates closer than this are the same answer.
CANDIDATE_SEP = 0.5
#: Passes of median refinement. Converges in two on real data; three is cheap.
REFINE_PASSES = 3

#: Hits by which two cut positions may differ and still be called UNDETERMINED.
#:
#: 🚨 ONE CUE'S MEMBERSHIP IS NOT EVIDENCE. Measured on Clevatess 07: the
#: recorded truth cuts at t=52.1 and the best-scoring position is t=165.0 --
#: 113 s later, on the far side of the same silence -- and the entire argument
#: between them is **one cue landing**, 203 hits against 202. Treating that as
#: decisive reports a break two minutes from where it is.
#:
#: A cue contributes at most one hit, so a one-hit margin is exactly the
#: resolution at which a single cue's assignment cannot be established. This is
#: the same small-sample argument that `bucket_noise_floor` makes for buckets.
TIE_SLACK = 1.0


class Fit(object):
    """What the aligner concluded, and the evidence for it."""

    __slots__ = ("segments", "score", "chance", "single", "buckets",
                 "failing", "candidates", "n_ref", "n_sub", "gaps")

    def __init__(self, segments, score, chance, single, buckets, failing,
                 candidates, n_ref, n_sub, gaps):
        self.segments = segments        # [(split_time or None, offset), ...]
        self.score = score              # combined match rate
        self.chance = chance
        self.single = single            # (offset, rate) for the one-offset fit
        self.buckets = buckets          # [(t0, n, applied, want_off, want_rate)]
        self.failing = failing          # the subset that genuinely fails
        self.candidates = candidates
        self.n_ref = n_ref
        self.n_sub = n_sub
        #: Per boundary, `(lo, hi)`: the stretch of reference time across which
        #: the break's position is UNDETERMINED, because every cue in it misses
        #: under both offsets. `segments[i][0]` is a point inside it.
        #: ⭐ This is what makes a correctness claim honest -- assert cues
        #: OUTSIDE these spans, and report what falls inside.
        self.gaps = gaps

    def undetermined(self, t):
        """Is reference time `t` inside a boundary's undetermined span?"""
        return any(lo <= t <= hi for lo, hi in self.gaps)

    @property
    def measurable(self):
        """Is there enough here for the score to mean anything?

        🚨 ERROR AND REFUSED ARE DIFFERENT OUTCOMES and must never be
        conflated -- subsync shipped that confusion twice. This is the line
        between them: `measurable is False` means *the file could not be
        measured*, not *it was measured and rejected*.

        Two conditions, both from the same small-sample argument:

        1. at least `MIN_ALIGNABLE_CUES` on each side
        2. the achieved rate must beat what the BEST OF MANY candidate offsets
           reaches by luck at this cue count -- the same noise floor the bucket
           walk applies, computed on the SMALLER side, because that is what
           bounds how many matches are even possible

        ⚠ Measured: without (2), a one-cue subtitle scored 5.15x chance.
        """
        n = min(self.n_ref, self.n_sub)
        if n < MIN_ALIGNABLE_CUES:
            return False
        return self.score > bucket_noise_floor(self.chance, n)

    @property
    def raw_excess(self):
        """The score over chance, whatever the sample size. ⚠ Diagnostics only:
        it is the number that reads 5.15x on a single cue."""
        return (self.score / self.chance) if self.chance else 0.0

    @property
    def excess(self):
        """Match rate as a multiple of the chance level, or ZERO when the
        input is too thin to have produced a meaning.

        ⭐ Zeroed rather than merely flagged, deliberately. A caller that reads
        `excess` and nothing else must not be handed a confident number built
        out of one cue -- "a rule that relies on remembering will be forgotten;
        make it structural".

        ⚠ The internal decision statistic -- never the number shown to a person.
        """
        return self.raw_excess if self.measurable else 0.0

    @property
    def is_cut(self):
        return len(self.segments) > 1

    @property
    def holds_throughout(self):
        """Does the applied answer hold across the WHOLE runtime?

        🚨 A whole-file score cannot see that one stretch is badly served: a cut
        file scores well overall because the larger segment dominates. This is
        what turns "confidently mis-timed for five minutes" into a refusal.
        """
        return not self.failing

    def offset_at(self, t):
        """The offset this fit gives a reference cue at time `t`."""
        for split, off in self.segments:
            if split is None or t < split:
                return off
        return self.segments[-1][1]

    # ----------------------------------------------------------------
    # turning a fit into something that can retime a SUBTITLE
    # ----------------------------------------------------------------
    # 🚨 `offset_at` TAKES A REFERENCE TIME AND THE WRITER HAS A SUBTITLE
    # TIME. They are not the same axis, and `segments` is expressed on the
    # reference one -- a split at 52.1 s means 52.1 s *into the video*. A
    # writer that fed a subtitle timestamp to `offset_at` would pick the wrong
    # segment for every cue within one jump of a boundary, which is exactly
    # the stretch a cut file is most wrong about.
    #
    # Segment i covers subtitle times below `split_i - offset_i`, because that
    # is the subtitle time its own offset carries to the boundary.

    # ⭐ Thin wrappers over the module-level functions below. Those take
    # `segments` and nothing else, so the WRITER never needs a whole `Fit` --
    # a `Verdict` already carries `segments`, and 3a's write path works from
    # that. Keeping the knowledge in one place and the convenience here.

    def subtitle_boundaries(self):
        """Each boundary in SUBTITLE time. -> [(sub_time, from_off, to_off)]"""
        return subtitle_boundaries(self.segments)

    def mapper(self):
        """callable(subtitle_seconds) -> new seconds. What `retime` wants."""
        return mapper_for(self.segments)

    def removed_spans(self):
        """Stretches of SUBTITLE time with no home. -> [(lo, hi)]"""
        return removed_spans(self.segments)

    def is_removed(self, seconds):
        """Does this subtitle time fall inside a removed stretch?"""
        return is_removed(self.segments, seconds)

    def __repr__(self):
        return "Fit(%s, %.2fx chance, %d segment%s%s)" % (
            " / ".join("%+.3f" % o for _s, o in self.segments), self.excess,
            len(self.segments), "" if len(self.segments) == 1 else "s",
            "" if self.holds_throughout else ", DOES NOT HOLD")


# --------------------------------------------------------------------------
# the primitive
# --------------------------------------------------------------------------

def subtitle_boundaries(segments):
    """Each boundary in SUBTITLE time. -> [(sub_time, from_off, to_off)]

    Segment i covers subtitle times below `split_i - offset_i`, because that is
    the subtitle time its own offset carries to the boundary.
    """
    out = []
    for i in range(len(segments) - 1):
        split, off = segments[i]
        if split is None:
            # 🚨 REFUSE, do not skip. `None` marks the LAST segment, so a
            # `None` before the end means the list is malformed -- and
            # `continue` silently discarded every later segment, giving the
            # whole file the first offset with no raise and no note. Found by
            # an adversarial pass. `align()` cannot produce this, but these
            # functions were extracted precisely so a caller can hand in bare
            # `segments` from a `Verdict`.
            raise ValueError(
                "segments[%d] has split=None but is not the last of %d: a "
                "None split marks the final segment, so this list is "
                "malformed and every segment after it would be discarded"
                % (i, len(segments)))
        out.append((split - off, off, segments[i + 1][1]))
    return out


def mapper_for(segments):
    """callable(subtitle_seconds) -> new seconds. What `retime` wants.

    ⚠ A cue inside a removed stretch is given the FOLLOWING segment's offset
    rather than being left alone. `cues.drop_cues` is what makes it disappear;
    this is what its value would be if it stayed.

    🚨 AND THE RESULT IS **NOT MONOTONIC** ACROSS A NEGATIVE JUMP. An earlier
    version of this docstring claimed it was, and an adversarial pass measured
    the opposite: with `[(100.0, +10.0), (None, 0.0)]`, `89.9 -> 99.9` but
    `90.0 -> 90.0` — the map goes **backwards 9.9 s**. That is not a defect in
    this function; it is the removed stretch, and it is exactly why `D9`
    exists. ⛔ **A caller that does not drop those cues produces an out-of-order
    file.** `removed_spans()` is not optional for anyone who writes.
    """
    bounds = subtitle_boundaries(segments)
    first = segments[0][1] if segments else 0.0

    def _map(seconds):
        offset = first
        for sub_time, _from_off, to_off in bounds:
            if seconds >= sub_time:
                offset = to_off
        return seconds + offset
    return _map


def removed_spans(segments):
    """Stretches of SUBTITLE time with no home. -> [(lo, hi)]

    ⭐ `D9`, ruled 2026-09-08 (`12-alignment.md` §6). A broadcast subtitle
    against a streaming video needs a NEGATIVE jump after the break, so cues
    timed inside the removed CM block -- sponsor cards, eyecatch captions --
    map to reference time that no longer exists and would overlap the next
    segment's opening cues. **They cannot render correctly under any offset**,
    so they are dropped, counted and reported.

    The span is `[split - off_before, split - off_after)`, and its width is
    exactly the size of the jump.

    ⚠ ONLY WHERE THE JUMP IS NEGATIVE. A positive jump INSERTS time rather
    than removing it, and leaves no cue homeless -- returning a span there
    would delete cues that render perfectly.
    """
    spans = []
    for sub_time, from_off, to_off in subtitle_boundaries(segments):
        if to_off < from_off:
            spans.append((sub_time, sub_time + (from_off - to_off)))
    return spans


def is_removed(segments, seconds):
    """Does this subtitle time fall inside a removed stretch?"""
    return any(lo <= seconds < hi for lo, hi in removed_spans(segments))


def differences(R, A, window=WINDOW):
    """Every (r - a) within +-window, and the reference index each came from.

    ⭐ Windowed with searchsorted, so the full |R|x|A| outer product is never
    materialised -- for a 24-minute episode and a +-120 s window that is ~6x
    less work, and it is what keeps a four-hour film affordable.
    """
    if len(R) == 0 or len(A) == 0:
        return np.empty(0), np.empty(0, dtype=np.int64)
    lo = np.searchsorted(A, R - window, side="left")
    hi = np.searchsorted(A, R + window, side="right")
    counts = hi - lo
    total = int(counts.sum())
    if total == 0:
        return np.empty(0), np.empty(0, dtype=np.int64)
    d = np.empty(total)
    ri = np.empty(total, dtype=np.int64)
    pos = 0
    for i in range(len(R)):
        c = counts[i]
        if c:
            d[pos:pos + c] = R[i] - A[lo[i]:hi[i]]
            ri[pos:pos + c] = i
            pos += c
    return d, ri


def _peaks(d, k, window):
    """Top-k offsets from the box-smoothed histogram of `d`.

    Two properties, each paid for:

    🚨 PLATEAU CENTRE, not argmax. Two files cut from the same authoring source
    have IDENTICAL cue starts, so every offset within +-MR_TOL scores the same
    and the curve is a flat table, not a peak. `argmax` returns its left edge --
    measured across five identical-source pairs, all five came back 0.30-0.33 s
    early, on precisely the files that should be easiest to get exactly right.

    ⭐ THEN MEDIAN-REFINE from the raw differences. The histogram, unlike a
    scan, still HOLDS them -- so the answer is not limited by the bin width.
    """
    if d.size == 0:
        return []
    nbins = int(2 * window / BIN) + 1
    idx = ((d + window) / BIN).astype(np.int64)
    idx = idx[(idx >= 0) & (idx < nbins)]
    if idx.size == 0:
        return []
    h = np.bincount(idx, minlength=nbins).astype(float)
    width = int(round(2 * MR_TOL / BIN)) | 1          # odd, so it is centred
    smooth = np.convolve(h, np.ones(width), mode="same")
    centres = np.arange(nbins) * BIN - window
    sep = max(1, int(CANDIDATE_SEP / BIN))

    out = []
    for _ in range(k):
        i = int(np.argmax(smooth))
        top = smooth[i]
        if top <= 0:
            break
        j = i
        while j + 1 < len(smooth) and smooth[j + 1] >= top - 1e-9:
            j += 1
        offset = float(centres[(i + j) // 2])
        # ⭐ D3b, RULED 2026-09-08: plateau centre, and the median ONLY when the
        # plateau is narrower than the tolerance.
        #
        # 🚨 A WIDE PLATEAU MEANS THE TWO FILES SHARE AN AUTHORING SOURCE, and
        # then the median is the wrong estimator. The differences are not
        # scattered around one true offset; they are a handful of exact values
        # plus the mismatched remainder, so the median chases the remainder.
        # Measured on the three identical-source pairs in the oracle, it lands
        # 0.20-0.21 s from the recorded truth while the plateau centre sits
        # inside it. Where the peak is genuinely narrow the median is strictly
        # better -- it is not limited by the bin width -- which is why both
        # estimators are here and the plateau decides between them.
        if (j - i) * BIN < MR_TOL:
            for _pass in range(REFINE_PASSES):
                near = d[np.abs(d - offset) <= MR_TOL]
                if near.size == 0:
                    break
                offset = float(np.median(near))
        out.append((offset, float(top)))
        smooth[max(0, i - sep):j + sep + 1] = 0
    return out


def candidates(R, A, window=WINDOW):
    """Offsets worth considering: the whole file's peaks, plus each bucket's.

    ⭐ The per-bucket peaks are the second dimension. Inside its own 120 s a
    minority segment's offset is the MAJORITY, so it is a plain peak there while
    being invisible globally.
    """
    d, ri = differences(R, A, window)
    if d.size == 0:
        return []
    found = [o for o, _h in _peaks(d, K_GLOBAL, window)]

    buckets = (R // CANDIDATE_BUCKET).astype(np.int64)
    for b in range(int(buckets.max()) + 1) if len(R) else []:
        mask = buckets[ri] == b
        if int(mask.sum()) < MIN_CUES:
            continue
        for o, _h in _peaks(d[mask], K_BUCKET, window):
            if all(abs(o - c) > CANDIDATE_SEP for c in found):
                found.append(o)
    return found


# --------------------------------------------------------------------------
# the split search -- subsync's, over the candidate set
# --------------------------------------------------------------------------

def _best_boundary(H, i0, i1):
    """Best single cut of reference cues [i0, i1). -> (score, k, c1, c2, tie_ks)

    One cumulative sum answers every cut position at once: the best head at k is
    the running total up to k, and the best tail is the total minus it.
    """
    m = i1 - i0
    if m < 2 * MIN_CUES:
        return None
    seg = H[:, i0:i1]
    head = np.concatenate([np.zeros((H.shape[0], 1)), np.cumsum(seg, axis=1)], axis=1)
    tail = head[:, -1:] - head
    ks = np.arange(MIN_CUES, m - MIN_CUES + 1)
    if ks.size == 0:
        return None
    hk, tk = head[:, ks], tail[:, ks]
    c1 = np.argmax(hk, axis=0)
    c2 = np.argmax(tk, axis=0)
    span = np.arange(len(ks))
    total = hk[c1, span] + tk[c2, span]
    total[c1 == c2] = -1.0                 # a "cut" into one offset is no cut
    best = float(total.max())
    if best < 0:
        return None
    tie = ks[np.flatnonzero(total >= best - 1e-9)]
    j = int(np.argmax(total))
    return best, i0 + int(ks[j]), int(c1[j]), int(c2[j]), i0 + tie


def _tie_range(H, i0, i1, c1, c2):
    """Every cut index of [i0, i1) that scores the maximum for (c1 -> c2).

    ⚠ The tie has to be recomputed after the greedy loop settles, not carried
    from the pass that proposed the boundary: later cuts change the segment this
    boundary divides, and a stale tie describes a range that no longer exists.
    """
    m = i1 - i0
    if m < 2 * MIN_CUES:
        return np.array([i0 + m // 2])
    head = np.concatenate([[0.0], np.cumsum(H[c1, i0:i1])])      # c1 serves [i0, k)
    run2 = np.concatenate([[0.0], np.cumsum(H[c2, i0:i1])])
    tail = run2[-1] - run2                                        # c2 serves [k, i1)
    ks = np.arange(MIN_CUES, m - MIN_CUES + 1)
    total = head[ks] + tail[ks]
    best = float(total.max())
    return i0 + ks[np.flatnonzero(total >= best - TIE_SLACK - 1e-9)]


def _boundary_time(R, tie_ks):
    """Where to PUT a boundary whose cut index is a tie. -> (time, lo, hi)

    ⭐ THE QUIET-GAP CONVENTION (spec/12-alignment.md §3.5). A real break falls
    in a SILENCE -- typically the opening song -- so every cut position across
    that silence scores identically and the index is genuinely undetermined.
    Every one of them assigns every CUE the same offset, which is what a viewer
    sees; they differ only in where the reported timestamp lands.

    🚨 A TIE IS NOT A GAP IN THE REFERENCE -- it is a run of cues that miss
    under BOTH offsets. Which offset they receive changes nothing that can be
    measured, so the break's position is genuinely undetermined across it, and
    the honest output is a POINT PLUS ITS SPAN rather than a false precision.

    ⭐ The point is the EARLIEST tie position. That is subsync's convention --
    the argmax takes the first maximum -- and it is the convention the recorded
    ground truth was measured with, so reporting anything else manufactures a
    disagreement with the oracle out of nothing.

    ⚠ Two other conventions were tried and measured on the 29 pairs. The gap's
    MIDPOINT moved reported breaks by up to 57 s and cost three answers. The
    WIDEST gap fixed both Clevatess cases and broke all three Re:Zero ones. The
    earliest tie plus a reported span is the only one that is honest about what
    is known, and it is why the suite asserts cue correctness OUTSIDE the span
    rather than a tolerance around a single number.
    """
    ks = [int(k) for k in tie_ks if 0 < int(k) < len(R)]
    if not ks:
        k = min(max(int(tie_ks[0]), 0), len(R) - 1)
        return float(R[k]), float(R[k]), float(R[k])
    lo, hi = min(ks), max(ks)
    return float(R[lo]), float(R[lo]), float(R[hi])


#: Half-width of the final local refinement, seconds, and its step.
REFINE_WINDOW = 0.60
REFINE_STEP = 0.01


def _refine(R, A, offset, window=None):
    """Re-centre one segment's offset on its OWN cues, USING THE OBJECTIVE.

    🚨 THE HISTOGRAM FINDS THE PEAK; IT MUST NOT SET THE FINAL VALUE.

    A histogram bin counts every (reference, subtitle) PAIR whose difference
    falls in it. The objective counts every reference CUE that finds a
    neighbour -- at most once. Where a reference cue has two subtitle cues
    inside the tolerance (a translation that split one line into two, a caption
    plus its speaker label), the histogram counts both and its peak drifts.
    Measured on three oracle pairs: 0.21 s of drift, just outside the corpus's
    0.20 s tolerance, on files that are otherwise exactly right.

    ⭐ So the last step scores the real objective on a fine local grid and takes
    the PLATEAU CENTRE -- subsync's estimator, which is what the ground truth
    was measured with. It costs ~120 evaluations over a 1.2 s window, against a
    ±120 s search, so the accuracy is free.

    ⚠ Plateau centre, not argmax: identical-source pairs give a flat top, and
    argmax returns its left edge. That defect cost five pairs 0.30-0.33 s.
    """
    if len(R) == 0 or len(A) == 0:
        return offset
    offs = np.arange(offset - REFINE_WINDOW, offset + REFINE_WINDOW + REFINE_STEP,
                     REFINE_STEP)
    rates = np.array([hits(R, A, o).mean() for o in offs])
    top = rates.max()
    if top <= 0:
        return offset
    on = np.flatnonzero(rates >= top - 1e-12)
    return float((offs[on[0]] + offs[on[-1]]) / 2.0)


def _earns_itself(R, H, bounds, labels, offsets, chance):
    """Every guard, applied to a whole multi-segment fit.

    Reduces exactly to the two-segment rules when there are two segments; each
    boundary justifies itself on its own, so a third segment cannot be carried
    by how good the first two were.
    """
    rates = [float(H[labels[i], bounds[i]:bounds[i + 1]].mean())
             for i in range(len(labels))]
    if chance and min(rates) < MIN_EXCESS * chance:
        return None
    for i in range(len(offsets) - 1):
        if not (MIN_BREAK <= abs(offsets[i + 1] - offsets[i]) <= MAX_BREAK):
            return None
        na = bounds[i + 1] - bounds[i]
        nb = bounds[i + 2] - bounds[i + 1]
        # The LOCAL margin, on the smaller of the two segments this boundary
        # separates, scored against the other one's offset. It does not shrink
        # with segment size, which is what makes an early break detectable.
        if na <= nb:
            sl, own, other = slice(bounds[i], bounds[i + 1]), labels[i], labels[i + 1]
        else:
            sl, own, other = slice(bounds[i + 1], bounds[i + 2]), labels[i + 1], labels[i]
        if float(H[own, sl].mean()) - float(H[other, sl].mean()) < MIN_LOCAL_MARGIN:
            return None
    return rates


# --------------------------------------------------------------------------
# the whole-runtime walk -- free, from the same candidates
# --------------------------------------------------------------------------

def _walk(R, H, cands, bounds, labels, chance):
    """Per-bucket rows, and the ones that genuinely fail.

    ⭐ No second computation. The candidate set already contains each bucket's
    own preferred offset BY CONSTRUCTION (that is what K_BUCKET is for), so
    "what would this stretch rather have?" is a lookup.
    """
    rows, failing = [], []
    if len(R) == 0:
        return rows, failing
    applied_idx = np.empty(len(R), dtype=np.int64)
    for i in range(len(labels)):
        applied_idx[bounds[i]:bounds[i + 1]] = labels[i]

    buckets = (R // BUCKET).astype(np.int64)
    for b in range(int(buckets.max()) + 1):
        mask = buckets == b
        n = int(mask.sum())
        t0 = b * BUCKET
        if n < MIN_BUCKET_CUES:
            rows.append((t0, n, None, None, None))
            continue
        applied_here = H[applied_idx[mask], np.flatnonzero(mask)]
        applied = float(applied_here.mean())
        centre = float(np.median([cands[i] for i in applied_idx[mask]]))
        # ⚠ Only offsets NEAR the applied one. A dozen cues will happily find a
        # spurious peak eighty seconds away, and a bucket must not veto a good
        # answer on that basis.
        near = [i for i, o in enumerate(cands)
                if abs(o - centre) <= BUCKET_LOCAL_WINDOW]
        if not near:
            rows.append((t0, n, applied, None, None))
            continue
        rates = [float(H[i, mask].mean()) for i in near]
        j = int(np.argmax(rates))
        want_off, want_rate = cands[near[j]], rates[j]
        rows.append((t0, n, applied, want_off, want_rate))

        # A bucket fails only if it BOTH loses real match rate AND wants a
        # materially different offset -- and only if what it wants is above its
        # own noise floor.
        if (want_rate - applied > BUCKET_RATE_SLACK
                and abs(want_off - centre) > MAX_BUCKET_DRIFT
                and want_rate > bucket_noise_floor(chance, n)):
            failing.append(rows[-1])
    return rows, failing


# --------------------------------------------------------------------------
# the front door
# --------------------------------------------------------------------------

def fit(R, A, duration=None, window=WINDOW, max_segments=None):
    """Align reference starts `R` against subtitle starts `A`. -> Fit

    Both are sorted second-valued arrays of DISTINCT cue-start moments -- run
    them through `objective.unique_starts` first. `duration` is the runtime the
    chance baseline is spread over; without it the cues' own span is used.

    ⛔ `max_segments` exists for tests and for a caller that knows better. The
    default is UNCAPPED: a 12-episode batch file needs ~11 breaks, and the old
    cap of 4 was wildly wrong. The guards, not a cap, are the safeguard.
    """
    R = np.asarray(R, dtype=float)
    A = np.asarray(A, dtype=float)
    n = len(R)
    span = duration
    if not span:
        span = float(A.max() - A.min()) if len(A) else 0.0
    elif len(A):
        span = max(float(duration), float(A.max() - A.min()))
    chance = chance_rate(A, span)

    cands = candidates(R, A, window)
    if n == 0 or len(A) == 0 or not cands:
        return Fit([(None, 0.0)], 0.0, chance, (0.0, 0.0), [], [], cands,
                   n, len(A), [])

    H = np.stack([hits(R, A, o) for o in cands]).astype(float)
    totals = H.sum(axis=1)
    best = int(np.argmax(totals))
    single = (cands[best], float(totals[best]) / n)

    bounds, labels = [0, n], [best]
    combined = single[1]
    while max_segments is None or len(labels) < max_segments:
        pick = None
        for si in range(len(bounds) - 1):
            found = _best_boundary(H, bounds[si], bounds[si + 1])
            if found is None:
                continue
            _score, cut, c1, c2, tie = found
            trial_b = bounds[:si + 1] + [cut] + bounds[si + 1:]
            trial_l = labels[:si] + [c1, c2] + labels[si + 1:]
            trial_o = [cands[l] for l in trial_l]
            rates = _earns_itself(R, H, trial_b, trial_l, trial_o, chance)
            if rates is None:
                continue
            trial_score = sum(r * (trial_b[i + 1] - trial_b[i])
                              for i, r in enumerate(rates)) / float(n)
            if trial_score - combined < MIN_SPLIT_GAIN:
                continue
            if pick is None or trial_score > pick[2]:
                pick = (trial_b, trial_l, trial_score, si, tie)
        if pick is None:
            break
        bounds, labels, combined = pick[0], pick[1], pick[2]

    # Each segment's offset is re-centred on its own cues, and each boundary is
    # placed by the quiet-gap convention.
    offsets, gaps = [], []
    for i, label in enumerate(labels):
        offsets.append(_refine(R[bounds[i]:bounds[i + 1]], A, cands[label]))
    segments = []
    for i in range(len(offsets)):
        if i == len(offsets) - 1:
            segments.append((None, offsets[i]))
            continue
        tie = _tie_range(H, bounds[i], bounds[i + 2], labels[i], labels[i + 1])
        if tie.size == 0:
            tie = np.array([bounds[i + 1]])
        t, lo, hi = _boundary_time(R, tie)
        segments.append((t, offsets[i]))
        gaps.append((lo, hi))

    rows, failing = _walk(R, H, cands, bounds, labels, chance)
    return Fit(segments, combined, chance, single, rows, failing, cands,
               n, len(A), gaps)


