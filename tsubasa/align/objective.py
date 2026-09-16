# -*- coding: utf-8 -*-
"""
The objective, and the constants it is measured against. RUNBOOK step B1.

⭐ CARRIED FORWARD FROM `subsync` UNCHANGED, deliberately. Every threshold here
sits in a MEASURED EMPTY BAND between real cases and controls, and the whole
value of the tool rests on that. What B1 replaces is the SEARCH -- how
candidate offsets are found -- not what makes an answer trustworthy.

    "Never loosen a guard to make a cut detectable. All three are
     load-bearing." -- LEDGER-HOT.md

🚨 THE ONE IDEA: a match rate means nothing until you know what it would be by
CHANCE. Measured against a raw cue list at ±0.5 s, chance sits near 45% -- so a
genuine 49% match looked like strong evidence when it was almost noise, and an
earlier build could not tell a right answer from a wrong one. On unique starts
at ±0.35 s chance falls to ~18% and real alignments score 45-90%.
"""
import math

import numpy as np

#: Cue-start match tolerance, seconds. A reference cue "lands" if a subtitle
#: cue sits within this. ⚠ It is also what makes coarse search safe -- any real
#: peak is at least 2*MR_TOL wide -- so anything that changes it changes the
#: search. Write the dependency down wherever it is used.
MR_TOL = 0.35

#: Two cue starts closer than this are ONE moment, not two.
#:
#: 🚨 A bilingual release carries every line twice, often ~0.100 s apart rather
#: than identically, so exact dedup cannot see it. Counting both nearly doubles
#: apparent cue density, which inflates chance: a 90%-matching, perfectly
#: aligned file scored 2.1x and was REFUSED. Well under MR_TOL, so nothing that
#: would have matched separately is lost.
CLUSTER_TOL = 0.15

#: The smallest believable commercial break, seconds.
MIN_BREAK = 1.0

#: ...and the largest. 🚨 Without an upper bound the split search papers over
#: MISSING DATA: a BluRay reference carrying 15 OP-karaoke cues the subtitle
#: lacks found those orphans a home 108 s away at 57% -- which is exactly what
#: the best of thousands of offsets scores BY CHANCE on 14 cues. Measured: real
#: breaks 8.2-40.1 s, artefacts 108-202 s. 60 sits in the gap.
MAX_BREAK = 60.0

#: Match-rate points a split must add OVERALL.
#:
#: 🚨 This guard is what stops a split being invented to paper over missing
#: data. With it removed, a file whose opening cues had been DELETED rather
#: than shifted "found" a 127 s break and cleared every other test.
MIN_SPLIT_GAIN = 0.02

#: ...and the points it must add to the SMALLER segment alone, scored against
#: the other segment's offset.
#:
#: ⭐ This is the guard that makes an EARLY break detectable at all. A global
#: gain shrinks with the size of the affected segment: when 5% of the cues sit
#: before a break, fixing every one of them moves the overall rate by at most 5
#: points, so a global bar can never fire. Four files in the megatest were
#: confidently mis-timed for their opening minutes by exactly that.
#: Measured: real cuts 37.5-70.0 points here, files that must not split 1.3-32.3.
MIN_LOCAL_MARGIN = 0.35

#: Excess over chance required to call an alignment real.
#:
#: ⚠ A FLOOR FOR THE SEGMENT GUARDS, NOT THE PRODUCT'S VERDICT. The shipped
#: verdict is a BAND -- accept >= 2.5, ESCALATE 1.5-2.5, refuse below -- because
#: a single line refuses 16% of correct cross-platform pairs, measured over 364.
#: See spec/05-interface.md. This constant is what a SEGMENT must clear to be
#: believed, which is a different question from what a PAIR must clear to be
#: written.
MIN_EXCESS = 2.5

#: Fewest reference cues a segment may contain. Below this a segment's rate is
#: noise: the best of many offsets on a dozen cues scores well by luck.
MIN_CUES = 12

#: Fewest cues on EITHER side for an alignment to be attempted at all.
#:
#: 🚨 Below this the excess-over-chance statistic is not merely weak, it is
#: INVERTED. Found by the negative controls, 2026-09-08: a subtitle containing
#: ONE cue scored **5.15x chance** against a real reference. The arithmetic is
#: not a bug -- chance falls linearly with cue count while the best of thousands
#: of candidate offsets always places that one cue on top of something -- which
#: is exactly why a thin input must be refused rather than scored.
#:
#: subsync used the same floor at its input stage; spec/06-edge-cases.md §5.1
#: calls one or two cues "below the measurable floor, stated as such".
MIN_ALIGNABLE_CUES = 5

#: Seconds of reference time per bucket in the whole-runtime walk.
BUCKET = 120.0
#: Below this a bucket cannot say anything.
MIN_BUCKET_CUES = 8
#: How far either side of the applied offset a bucket may look for something
#: better. 🚨 Searching the whole window per bucket does not work -- a dozen
#: cues find a spurious 53%-matching peak eighty seconds away.
BUCKET_LOCAL_WINDOW = 15.0
#: A bucket fails only if it BOTH loses this many match-rate points AND wants an
#: offset this far away. ⚠ Both are required: independently authored files
#: jitter by a couple of tenths, so a stretch can genuinely prefer an offset
#: 0.3 s away and gain ~19 points by it. That is inside MR_TOL and invisible to
#: a viewer. Ten seconds is not.
BUCKET_RATE_SLACK = 0.15
MAX_BUCKET_DRIFT = 0.75
#: Standard deviations above chance a thin bucket must clear before its
#: complaint is believed.
BUCKET_NOISE_Z = 4.0

#: Default half-width of the offset search, seconds.
WINDOW = 120.0


def unique_starts(starts, tol=CLUSTER_TOL):
    """Distinct cue-start MOMENTS, clustered at `tol`. -> sorted np.ndarray."""
    xs = sorted(set(round(float(t), 3) for t in starts))
    if not xs:
        return np.empty(0)
    out = [xs[0]]
    for x in xs[1:]:
        if x - out[-1] > tol:
            out.append(x)
    return np.asarray(out)


def chance_rate(A, span, tol=MR_TOL):
    """The match rate cue DENSITY alone produces, with no real alignment.

    ⚠ `span` is the runtime the density is spread over. Passing a span shorter
    than the real one inflates chance and refuses correct pairs.
    """
    if span is None or span <= 0:
        return 1.0
    return min(1.0, 2.0 * tol * len(A) / float(span))


def hits(R, A, offset, tol=MR_TOL):
    """Boolean per reference cue: does it land, at this offset? -> np.ndarray.

    `offset` is ADDED to the subtitle's timestamps, so a reference cue at `r`
    is compared against `A + offset`, i.e. `r - offset` against `A`.
    """
    if len(R) == 0 or len(A) == 0:
        return np.zeros(len(R), dtype=bool)
    shifted = R - offset
    k = np.searchsorted(A, shifted)
    lo = A[np.clip(k - 1, 0, len(A) - 1)]
    hi = A[np.clip(k, 0, len(A) - 1)]
    return np.minimum(np.abs(shifted - lo), np.abs(shifted - hi)) <= tol


def match_rate(R, A, offset, tol=MR_TOL):
    """Fraction of reference cues that land at this offset."""
    if len(R) == 0:
        return 0.0
    return float(hits(R, A, offset, tol).mean())


def bucket_noise_floor(chance, n, z=BUCKET_NOISE_Z):
    """The match rate a bucket of `n` cues reaches by CHANCE alone.

    🚨 A bucket takes the best of many candidate offsets, and the best of many
    tries is far above the plain chance level when there are few cues to try it
    on. With 19 cues at a 22% chance level the floor is about 60% -- so a
    transcript's last bucket "wanting" 47% at an offset 10 s away was not
    evidence of anything, and it vetoed an otherwise correct alignment. The
    same arithmetic explains the 108 s phantom break.
    """
    if n <= 0 or not chance or chance <= 0:
        return 1.0
    return min(1.0, chance + z * math.sqrt(max(chance * (1.0 - chance), 0.0) / float(n)))
