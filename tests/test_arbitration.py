# -*- coding: utf-8 -*-
"""
Cluster arbitration — the escalation band's second signal. RUNBOOK step A6,
decision `D7`. `09-corpus-strategy.md` §Stage 4.

⭐ THE CLAIM UNDER TEST

`LEDGER.md` §Logic escalated it: **no single per-pair threshold can work.** A
correct English cross-platform pair scores **1.70×** and a wrong anime pair
scores **1.95×** — the bands overlap. So the band is structural, and the
2.0–2.5× middle needs a *second* signal.

**Coherence** is that signal: the share of a cluster's episode-matched pairs
whose offsets agree within ±500 ms. Measured on **44 correct and 60 wrong
clusters**:

| | |
| --- | --- |
| correct | min 0.17 · median **0.67** |
| wrong | median 0.25 · **max 0.50** |
| ⭐ at **≥ 0.60** | 24 of 44 correct kept, **0 of 60 wrong accepted** |

🚨 AND THE LIFT IS ONE-DIRECTIONAL, which is the design and not a shortcut.
A coherent cluster may LIFT a weak member out of the band. An incoherent one
may **not** push a member down — because a correct cluster with low coherence
is ordinary (broadcast subtitles against a web release differ per episode)
while a wrong cluster essentially never coheres. **The evidence is strong in
one direction only, so only one direction is used.**

⚠ The fixture is the probe's own 104 clusters, read from the corpus. Nothing
here is a hand-written offset list pretending to be data.
"""
import io
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tsubasa import arbitrate as A                         # noqa: E402
from tsubasa.paths import corpus_root, load_config         # noqa: E402


@pytest.fixture(scope="module")
def clusters():
    """The measured clusters: 44 correct, 60 wrong, with their offsets."""
    cfg = load_config(ROOT)
    path = corpus_root(cfg, ROOT) / "_work" / "probe_opp6_coherence.json"
    if not path.is_file():
        pytest.skip("SKIPPED, NOT PASSED: no cluster ground truth at %s" % path)
    with io.open(str(path), encoding="utf-8") as fh:
        data = json.load(fh)
    # correct: [show, n, coherence, offsets] · wrong: [a, b, n, coherence, offsets]
    correct = [(row[0], row[2], row[3]) for row in data["correct"]]
    wrong = [(row[0] + " / " + row[1], row[3], row[4]) for row in data["wrong"]]
    return correct, wrong


# ==========================================================================
# ⭐ the implementation must reproduce the measurement
# ==========================================================================

def test_coherence_reproduces_every_recorded_value(clusters):
    """⭐ The check that makes every number below mean something.

    104 clusters were measured by a probe before this module existed. If the
    implementation disagrees with even one of them, the thresholds derived
    from that measurement do not apply to this code.

    🚨 It disagreed on **4** at first, and the disagreement found a real
    definition error: a sliding window of width 2·tol groups offsets 666 ms
    apart transitively, and the measurement does not. Agreement has to be with
    a **common reference**, not a chain of near-neighbours.
    """
    correct, wrong = clusters
    problems = []
    for name, want, offsets in correct + wrong:
        got = A.coherence(offsets)
        if abs(got - want) > 1e-9:
            problems.append((name, want, got, sorted(offsets)[:6]))
    assert not problems, "%d of %d clusters disagree:\n  %s" % (
        len(problems), len(correct) + len(wrong),
        "\n  ".join("%s want %.4f got %.4f %s" % p for p in problems[:6]))


def test_the_separation_the_threshold_was_chosen_from(clusters):
    """🚨 `09-corpus-strategy.md` §Stage 4.2, by name: at ≥ 0.60, **24 of 44
    correct kept and 0 of 60 wrong accepted**. The 0 is the load-bearing
    half."""
    correct, wrong = clusters
    kept = sum(1 for _n, _w, o in correct if A.coherence(o) >= A.COHERENCE_ACCEPT)
    accepted = [n for n, _w, o in wrong if A.coherence(o) >= A.COHERENCE_ACCEPT]
    assert accepted == [], "wrong clusters accepted: %s" % accepted[:5]
    assert kept >= 20, "only %d of 44 correct clusters cohere" % kept


def test_no_wrong_cluster_reaches_the_threshold_by_any_margin(clusters):
    """⚠ The empty band, stated as a distance rather than a count. Wrong
    clusters top out at 0.50 against a 0.60 line — if that gap closes, the
    threshold is no longer sitting in empty space and `00-INDEX.md` Rule 2 is
    no longer satisfied."""
    _correct, wrong = clusters
    worst = max(A.coherence(o) for _n, _w, o in wrong)
    assert worst <= 0.55, "a wrong cluster reached %.2f" % worst
    assert A.COHERENCE_ACCEPT - worst >= 0.05, (
        "the empty band is only %.2f wide" % (A.COHERENCE_ACCEPT - worst))


# ==========================================================================
# the mechanism
# ==========================================================================

def test_agreement_must_be_with_a_common_reference_not_transitive():
    """🚨 The definition error the 104-cluster check caught.

    Two offsets 600 ms apart are not within ±500 of each other, so no
    reference explains both — the measurement counts 1. A sliding window of
    width 1000 counts 2, because it only asks about the span end to end.

    ⚠ The first version of this check used `[0, 400, 800]`, which does NOT
    discriminate: 400 is within ±500 of both ends, so a common reference does
    exist and both definitions say 3. A distinguishing example has to have no
    valid centre at all.
    """
    assert A.coherence([0, 600, 1200]) == pytest.approx(1 / 3.0)
    assert A.coherence([0, 400, 800]) == 1.0, "400 is a valid common reference"
    assert A.coherence([0, 400]) == 1.0
    assert A.coherence([0, 600]) == 0.5


def test_coherence_is_a_share_not_a_variance():
    """⭐ Nine episodes agreeing and one wildly off is a coherent cluster with
    one bad episode — which is what a broadcast recording with a missing week
    looks like. A variance would score it as incoherent."""
    offsets = [100, 120, 140, 160, 180, 200, 220, 240, 260, 99000]
    assert A.coherence(offsets) == pytest.approx(0.9)


def test_an_empty_cluster_cannot_lift_anything():
    """⚠ Absent is not agreement. A cluster with no measured offsets scores
    zero and lifts nothing, rather than raising or defaulting to true."""
    assert A.coherence([]) == 0.0
    assert A.consensus_offset([]) is None
    assert A.Cluster([]).coheres is False


def test_the_consensus_offset_is_the_median_of_the_agreeing_group():
    """⚠ Never the mean, and never the whole set's average. One outlier
    inside a window drags a mean; the whole set's average belongs to
    nothing."""
    cluster = A.Cluster([1000, 1050, 1100, 90000])
    assert cluster.offset == 1050
    assert cluster.coherence == pytest.approx(0.75)


def test_two_agreeing_pairs_are_not_a_coherent_cluster():
    """⚠ A coin landing the same way twice scores a perfect 1.00. The size
    floor is what stops that being evidence."""
    tiny = A.Cluster([500, 520])
    assert tiny.coherence == 1.0
    assert tiny.coheres is False, "two pairs were treated as a cluster"
    assert A.Cluster([500, 520, 540]).coheres is True


# ==========================================================================
# 🚨 the lift, and its direction
# ==========================================================================

def test_a_coherent_cluster_lifts_a_weak_pair_out_of_the_band():
    """⭐ The Hulu case, by name. `LEDGER.md`: Hulu Japan commissions its own
    transcription, so its correct pairs sit at a **1.58× median** — under any
    single threshold that also rejects garbage."""
    coherent = A.Cluster([900, 950, 1000, 1010, 1050])
    assert A.verdict(1.8, coherent) == "accept"
    assert A.verdict(1.8, None) == "escalate"


def test_an_incoherent_cluster_never_pushes_a_pair_DOWN():
    """🚨 The asymmetry, and it is the whole design.

    A correct cluster with low coherence is ordinary — broadcast subtitles
    against a web release differ per episode, and 20 of the 44 measured
    correct clusters score under 0.60. Letting incoherence refuse would throw
    those away. The evidence is strong in ONE direction: a wrong cluster
    essentially never coheres.
    """
    incoherent = A.Cluster([-40000, 5000, 60000, 120000])
    assert incoherent.coheres is False
    assert A.verdict(1.8, incoherent) == "escalate", "incoherence refused a pair"
    assert A.verdict(3.0, incoherent) == "accept", "incoherence overrode a strong pair"


def test_coherence_can_never_rescue_a_pair_below_the_refusal_line():
    """⛔ The band has a floor, and the second signal does not reach under it.
    Below 1.5× the pair is refused whatever its neighbours did."""
    coherent = A.Cluster([900, 950, 1000, 1010, 1050])
    assert A.verdict(1.2, coherent) == "refuse"
    assert A.verdict(0.9, coherent) == "refuse"


def test_a_strong_pair_needs_no_cluster_at_all():
    for cluster in (None, A.Cluster([]), A.Cluster([1, 90000])):
        assert A.verdict(4.4, cluster) == "accept"


# ==========================================================================
# episode-set renumbering
# ==========================================================================

def test_a_constant_renumbering_is_found():
    """⭐ `09-corpus-strategy.md` §Stage 4.3: `Blue Lock S2` numbered 25…38
    against jimaku's 1…24 is a constant **−24**. One alignment confirms the
    hypothesis and the rest pair by arithmetic — verified, never searched."""
    videos = list(range(25, 39))
    subs = list(range(1, 25))
    got = A.offset_hypothesis(videos, subs)
    assert got is not None, "no hypothesis for a clean constant shift"
    assert got["offset"] == -24, got


@pytest.mark.parametrize("videos,subs,offset", [
    (list(range(12, 25)), list(range(1, 14)), -11),      # Oshi no Ko S2
    (list(range(13, 26)), list(range(1, 13)), -12),      # Solo Leveling S2
    (list(range(25, 37)), list(range(1, 25)), -24),      # Kusuriya S2
    (list(range(38, 48)), list(range(1, 13)), -37),      # Bungou Stray Dogs
])
def test_the_renumbered_shows_from_the_corpus_resolve(videos, subs, offset):
    """The real shapes `probe_opp5` §C found in the corpus."""
    got = A.offset_hypothesis(videos, subs)
    assert got is not None, (videos[:3], subs[:3])
    assert got["offset"] == offset, got


def test_sets_that_already_line_up_produce_no_hypothesis():
    """⚠ Returning a zero 'correction' would let a caller apply it and call
    that a finding."""
    assert A.offset_hypothesis(list(range(1, 13)), list(range(1, 13))) is None


def test_a_shift_explaining_only_a_few_episodes_is_refused():
    """⛔ A shift that lines up three episodes of forty is arithmetic noise,
    and acting on it renumbers a library."""
    assert A.offset_hypothesis(list(range(1, 41)), [95, 96, 97]) is None


def test_too_few_episodes_is_not_a_renumbering():
    assert A.offset_hypothesis([5, 6], [1, 2]) is None
    assert A.offset_hypothesis([], []) is None
