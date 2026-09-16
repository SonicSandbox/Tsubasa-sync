# -*- coding: utf-8 -*-
"""
Cluster-level arbitration: the escalation band's second signal.

RUNBOOK step A6. `09-corpus-strategy.md` §Stage 4, decision `D7`.

⭐ THE PROBLEM THIS SOLVES, AND IT IS MEASURED

`LEDGER.md` §Logic escalated it: **no single per-pair threshold can work.**
A correct English cross-platform pair scores **1.70×** and a wrong anime pair
scores **1.95×** — the bands overlap, so any single number both accepts
garbage and refuses real pairs. The 2.5× line refuses **16% of correct pairs**
over 364 measured.

⭐ So the band is structural, and it needs a SECOND SIGNAL:

    >= 2.5x      accept
    1.5 - 2.5x   ⭐ escalate -- ask this module
    < 1.5x       refuse

## Coherence — the second signal

Files come in clusters: one release group's episodes share a `tokenize()`
shape, and **97.0% of the video corpus sits in clusters of >= 3**. A whole
cluster either belongs to a whole other cluster, or it does not.

> **Coherence = the share of a cluster's episode-matched pairs whose offsets
> agree within ±500 ms.**

| Measured on 44 correct and 60 wrong clusters | |
| --- | --- |
| correct | min 0.17 · p10 0.20 · **median 0.67** |
| wrong | median 0.25 · p90 0.33 · **max 0.50** |
| ⭐ at **>= 0.60** | 24 of 44 correct kept, **0 of 60 wrong accepted** |

⚠ **The value is asymmetric, and that is the point.** A correct cluster with
LOW coherence is ordinary — broadcast subtitles against a web release differ
per episode — and those still pass per pair. **A wrong cluster essentially
never coheres**, so coherence is trustworthy in one direction only: it may
LIFT a weak member, and it may never refuse one.

⛔ **Coherence never writes a file by itself.** Every pair still gets its own
verdict (`09-corpus-strategy.md` §Stage 4.4). This lifts the band; it does not
replace the referee.
"""

# ⚠ Milliseconds, because the probe that measured the separation worked in
# milliseconds and the recorded cluster data is in milliseconds. Converting
# here would put a rounding step between the constant and its evidence.
COHERENCE_TOL_MS = 500

# ⭐ 0.60, and it sits in a MEASURED EMPTY BAND: wrong clusters never exceeded
# 0.50. `00-INDEX.md` Rule 2 -- a threshold set by taste breaks the whole
# value proposition, and this one has 60 negative controls under it.
COHERENCE_ACCEPT = 0.60

# The escalation band, from `05-interface.md` and `LEDGER.md` §Logic.
ACCEPT_AT = 2.5
REFUSE_BELOW = 1.5

# A cluster needs enough episodes for agreement to mean anything. Two pairs
# agreeing is a coin landing the same way twice.
MIN_CLUSTER = 3


def coherence(offsets, tol_ms=COHERENCE_TOL_MS):
    """The largest share of offsets that agree within ±`tol_ms`.

    ⭐ A share, not a variance. A cluster where nine episodes agree and one
    is wildly off is a coherent cluster with one bad episode — which is
    exactly what a broadcast recording with a missing week looks like — and a
    variance would score it as incoherent.

    ⚠ Returns 0.0 for an empty input rather than raising: an absent
    measurement must not be able to lift anything, and it must not crash the
    caller either.
    """
    values = sorted(v for v in offsets if v is not None)
    if not values:
        return 0.0
    return _largest_group(values, tol_ms)[0] / float(len(values))


def _largest_group(values, tol_ms):
    """(size, members) of the biggest set within ±tol of an OBSERVED offset.

    🚨 CENTRED ON A VALUE, NOT A SLIDING WINDOW, and the difference is real.

    A sliding window of width 2·tol groups any two offsets 666 ms apart, and
    the probe that measured this separation does not. Checked against all 104
    recorded clusters: a sliding window disagrees on **4** of them —
    `Darwin's Game` 2/3 against the recorded 1/3, `Neon Genesis Evangelion`
    10/10 against 9/10 — because a chain of near-neighbours can span twice the
    tolerance end to end while no single offset is within tolerance of them
    all. **Agreement has to be with a common reference, not transitively.**

    ⭐ Found by requiring this implementation to reproduce all 104 recorded
    coherence values, rather than by reading the sentence that describes it.
    """
    best_size, best_members = 0, []
    for centre in values:
        members = [v for v in values if abs(v - centre) <= tol_ms]
        if len(members) > best_size:
            best_size, best_members = len(members), members
    return best_size, best_members


def consensus_offset(offsets, tol_ms=COHERENCE_TOL_MS):
    """The offset the coherent group agrees on, or None.

    ⚠ The MEDIAN of the agreeing group, never the mean: one outlier inside a
    window drags a mean and cannot move a median. And never the whole set's
    average, which is what makes an incoherent cluster produce a confident
    number that belongs to nothing.
    """
    values = sorted(v for v in offsets if v is not None)
    if not values:
        return None
    group = _largest_group(values, tol_ms)[1]
    return group[len(group) // 2]


class Cluster(object):
    """One (video-cluster, subtitle-cluster) pairing under consideration."""

    __slots__ = ("offsets", "_coherence")

    def __init__(self, offsets=()):
        self.offsets = list(offsets)
        self._coherence = None

    @property
    def size(self):
        return len([o for o in self.offsets if o is not None])

    @property
    def coherence(self):
        if self._coherence is None:
            self._coherence = coherence(self.offsets)
        return self._coherence

    @property
    def offset(self):
        return consensus_offset(self.offsets)

    @property
    def coheres(self):
        """⚠ Requires BOTH the threshold and enough episodes. Two pairs
        agreeing is a coin landing the same way twice, and it would score a
        perfect 1.00.

        ⛔ THIS SAYS THE CLUSTER AGREES. IT SAYS NOTHING ABOUT ANY ONE PAIR.
        A caller lifting a pair on this alone lifts the one member that does
        NOT agree -- see `agrees_with`, and the docstring above about a
        cluster with one bad episode.
        """
        return self.size >= MIN_CLUSTER and self.coherence >= COHERENCE_ACCEPT

    def agrees_with(self, offset_seconds, tol_ms=COHERENCE_TOL_MS):
        """Is THIS pair's own offset inside the group that cohered?

        🚨 FOUND BY AN ADVERSARIAL PASS, 2026-09-09, and it defeated the
        project's whole value proposition. `verdict.py` lifted a pair out of
        the escalation band on `coheres` alone -- never asking whether the pair
        being lifted was one of the episodes that agreed.

        The docstring on `coherence` above names the exact shape: *"a cluster
        where nine episodes agree and one is wildly off is a coherent cluster
        with one bad episode -- which is what a broadcast recording with a
        missing week looks like."* ⛔ **That one bad episode was precisely the
        pair the lift wrote.** Measured on the oracle: two entirely different
        shows, 1.62x, own offset **52 seconds** from the consensus of the four
        siblings vouching for it -- CONFIDENT, written. Five such pairs exist
        among 324 cross-show combinations.

        ⚠ AND THE UNITS ARE THE OTHER HALF OF THIS. Cluster offsets are
        MILLISECONDS -- the probe that measured the separation worked in them
        -- and `Fit.segments` offsets are SECONDS. Nothing structural stopped a
        1000x error, so the conversion lives here, once, in the module that
        owns the milliseconds.
        """
        if offset_seconds is None:
            return False
        centre = self.offset
        if centre is None:
            return False
        return abs(float(offset_seconds) * 1000.0 - centre) <= tol_ms

    def __repr__(self):
        return "Cluster(%d pairs, coherence %.2f, offset %s)" % (
            self.size, self.coherence, self.offset)


def verdict(excess, cluster=None):
    """"accept" | "escalate" | "refuse" for one pair, given its cluster.

    ⭐ THE LIFT IS ONE-DIRECTIONAL, and that is the whole design.

    A coherent cluster lifts a member out of the escalation band. An
    incoherent one does **not** push a member down — because a correct cluster
    with low coherence is ordinary (broadcast against web), while a wrong
    cluster essentially never coheres. The evidence is only strong in one
    direction, so only one direction is used.
    """
    if excess >= ACCEPT_AT:
        return "accept"
    if excess < REFUSE_BELOW:
        return "refuse"
    if cluster is not None and cluster.coheres:
        return "accept"
    return "escalate"


def offset_hypothesis(video_episodes, subtitle_episodes):
    """A constant renumbering between two episode sets, or None.

    ⭐ `09-corpus-strategy.md` §Stage 4.3: `Blue Lock S2` numbered 25…38
    against jimaku's 1…24 is a constant **−24**. One alignment confirms the
    hypothesis and the rest pair by arithmetic — **verified, never searched**.

    ⚠ Returns None when the sets already line up, so a caller cannot apply a
    zero "correction" and call that a finding.
    """
    videos = sorted(set(e for e in video_episodes if e is not None))
    subs = sorted(set(e for e in subtitle_episodes if e is not None))
    if len(videos) < MIN_CLUSTER or len(subs) < MIN_CLUSTER:
        return None

    direct = len(set(videos) & set(subs))
    best_offset, best_overlap = None, direct
    # The plausible offsets line a range END up with a range end. Searching
    # every integer finds spurious partial overlaps on long-running shows.
    # ⚠ ORDERED, and start-to-start comes first: `Solo Leveling S2` is videos
    # 13-25 against subtitles 1-12, where -12 and -13 both explain twelve
    # episodes. The recorded answer is -12 -- the one that lines the two
    # FIRST episodes up -- so ties resolve toward it rather than toward
    # whichever candidate a set happened to yield first.
    for candidate in (subs[0] - videos[0], subs[-1] - videos[-1],
                      subs[0] - videos[-1], subs[-1] - videos[0]):
        if candidate == 0:
            continue
        overlap = len({v + candidate for v in videos} & set(subs))
        if overlap > best_overlap:
            best_offset, best_overlap = candidate, overlap

    if best_offset is None:
        return None

    # ⛔ TWO GUARDS, and the second is the one that matters.
    #
    # A hypothesis must explain most of the smaller set -- and it must also
    # account for a real share of the LARGER one. Without the second guard,
    # three subtitles numbered 95-97 against a forty-episode show produce a
    # confident +94 shift: it explains 3 of 3, which is 100% of the smaller
    # set, and 3 of 40, which is nothing. Acting on that renumbers a library.
    #
    # ⚠ The larger-set share is 0.4 rather than something tighter because a
    # real case needs it: `Bungou Stray Dogs` is 10 videos against 12
    # subtitles at an offset of -37, and a tighter floor throws it away.
    smaller, larger = min(len(videos), len(subs)), max(len(videos), len(subs))
    if best_overlap < max(MIN_CLUSTER, 0.6 * smaller):
        return None
    if best_overlap < 0.4 * larger:
        return None
    return {"offset": best_offset, "overlap": best_overlap, "of": smaller}
