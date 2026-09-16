# -*- coding: utf-8 -*-
"""
The pairing benchmark. RUNBOOK step A5b — ⭐ `D8`: THE RELEASE NUMBER.

⭐ WHY THIS ONE MATTERS MORE THAN THE OTHERS

Every other gate measures a stage. This measures the thing the tool is for:
**given a real video filename and a real subtitle filename that ALIGNMENT has
already proved belong together, does recognition keep them?**

Ground truth is `_work/probe_vn14_e2e.json` — 435 pairs whose offsets were
confirmed by timing, not by a name. 350 survive the sealed exclusion and the
label-noise list. ⚠ **Nothing here is labelled by the thing being tested.**

## The two numbers, and why one of them is not a success rate

| | |
| --- | --- |
| **candidate recall** | the pair survives to timing. **92.3%** |
| settled by name alone | **49.7%** — SAME plus what A2c/A3b rescue |

⚠ *Settled by name* is NOT a success rate. The other half are UNSURE, mostly
cross-script, and they **pair** — decided by timing. It measures how much work
timing is spared, and it is what the alias table (A7) exists to raise.

🚨 AND RECALL ALONE IS TRIVIALLY SATISFIABLE. An index returning every
subtitle for every video scores 100%. **Fan-out is what makes it mean
anything**, so it is checked here too.

⚠ The baseline is a FLOOR, never a target: the suite fails when a number
drops, and a rise is re-recorded deliberately with
`python -m tsubasa.dev vnbench --baseline`.
"""
import io
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tsubasa.dev import vnbench as B                       # noqa: E402
from tsubasa.naming.series import DIFFERENT, SAME, UNSURE  # noqa: E402
from tsubasa.paths import corpus_root, load_config         # noqa: E402

BASELINE = ROOT / B.BASELINE


@pytest.fixture(scope="module")
def measured():
    cfg = load_config(ROOT)
    root = corpus_root(cfg, ROOT)
    if not root.is_dir():
        pytest.skip("SKIPPED, NOT PASSED: corpus absent on this machine")
    try:
        pairs, dropped = B.load_pairs(cfg, root)
    except IOError as exc:
        pytest.skip("SKIPPED, NOT PASSED: %s" % exc)
    if len(pairs) < 100:
        pytest.skip("SKIPPED, NOT PASSED: only %d ground-truth pairs" % len(pairs))
    return B.measure(pairs), pairs, dropped


@pytest.fixture(scope="module")
def baseline():
    if not BASELINE.is_file():
        pytest.skip("SKIPPED, NOT PASSED: no %s. Record it with "
                    "`python -m tsubasa.dev vnbench --baseline`." % B.BASELINE)
    with io.open(str(BASELINE), encoding="utf-8") as fh:
        return json.load(fh)


# ==========================================================================
# the ground truth itself
# ==========================================================================

def test_the_ground_truth_is_confirmed_by_timing_not_by_a_name(measured):
    """⚠ The property that makes this a benchmark rather than a mirror.

    Every pair was confirmed by ALIGNMENT. If the labels came from the naming
    stack, this would measure whether the naming stack agrees with itself.
    """
    _result, pairs, _dropped = measured
    assert len(pairs) >= 300, "%d pairs -- too few to claim anything" % len(pairs)
    for show, episode, video_name, sub_name in pairs[:20]:
        assert video_name and sub_name and video_name != sub_name
        assert episode is not None


def test_the_sealed_slice_is_excluded_from_BOTH_sides(measured):
    """🔒 `show` is the VIDEO-side folder; the jimaku side is a separate entry
    that can be sealed under a different name. Excluding only the video side
    left 15 pairs in — the tell was 360 pairs against the probe's 345."""
    _result, _pairs, dropped = measured
    assert dropped.get("sealed (video side)", 0) > 0
    assert dropped.get("sealed (jimaku side)", 0) > 0, (
        "nothing was dropped for the jimaku side; the seal is one-sided")


def test_the_label_noise_list_is_applied_and_small(measured):
    """⚠ Rows that are wrong in the GROUND TRUTH, not in the tool. A benchmark
    that counts them as misses is measuring its own labels — but a long
    exclusion list is a benchmark being tuned, so it stays short and named."""
    _result, _pairs, dropped = measured
    assert len(B.LABEL_NOISE) <= 4, B.LABEL_NOISE
    assert dropped.get("label noise", 0) <= 10, dropped


# ==========================================================================
# ⭐ the release numbers
# ==========================================================================

def test_candidate_recall_has_not_regressed(measured, baseline):
    """⭐ `D8`. The pair survives to timing.

    Bounded by episode agreement, because identity RANKS and never terminally
    drops a pair below the fan-out budget. ⚠ A season stated on one side only
    is NOT a disagreement — 46% of real pairs are that shape, and counting
    them as misses made a 92.3% stack read as 46%.
    """
    result, _pairs, _dropped = measured
    n = result["pairs"]
    agree = (result["episode"].get("agree", 0)
             + result["episode"].get("episode agrees, season differs", 0))
    rate = 100.0 * agree / n
    floor = baseline["candidateRecall"]
    assert rate >= floor - 0.5, (
        "candidate recall %.1f%% over %d pairs, baseline %.1f%%"
        % (rate, n, floor))


def test_settled_by_name_has_not_regressed(measured, baseline):
    """How much work timing is spared. ⚠ Not a success rate — see the module
    docstring. This is what A7 exists to raise."""
    result, _pairs, _dropped = measured
    n = result["pairs"]
    reach = result["identity"].get(SAME, 0) + sum(result["rescued"].values())
    rate = 100.0 * reach / n
    floor = baseline["settledByName"]
    assert rate >= floor - 0.5, (
        "settled-by-name %.1f%% over %d pairs, baseline %.1f%%"
        % (rate, n, floor))


@pytest.fixture(scope="module")
def measured_without_alias(measured):
    """The identical stack with RUNBOOK A7's table switched off."""
    _result, pairs, _dropped = measured
    return B.measure(pairs, use_alias=False)


def test_the_kana_bridge_rescues_pairs_identity_alone_refuses(
        measured_without_alias):
    """⭐ A3b earning its place on the benchmark rather than on its own gate.

    These are cross-script pairs — `Gachiakuta` / `ガチアクタ` — that Stage 2
    cannot settle by characters, because kana is not Latin.

    🚨 `use_alias=False`, AND THAT IS THE WHOLE POINT OF THIS DOCSTRING.
    A7 shipped a table that settles five of the six pairs this check was
    written for, so `rescued["kana"]` on the shipping stack fell **6 → 1** and
    this check went red. **Nothing about the kana bridge changed.** Measuring
    it with the table on measures *kana minus alias*, which is not what the
    check is named for — `LEDGER.md` §Harness, a check passing through a filter
    that is not its own.

    ⚠ The kana bridge is not made redundant by A7: it is a shipped RULE with no
    data, so it works on shows Wikidata has never heard of, which is precisely
    where a bundled table cannot help.
    """
    result = measured_without_alias
    assert result["rescued"].get("kana", 0) >= 3, result["rescued"]


def test_the_alias_table_raises_settled_by_name(measured,
                                                measured_without_alias,
                                                baseline):
    """⭐ RUNBOOK A7, measured as a BEFORE and AFTER of this benchmark rather
    than asserted. `D6` time-boxed A7 to one day and cut it below a 15%
    realised gain; this is the number that decision was made on.

    ⛔ The table returns SAME or UNSURE and never DIFFERENT, so this can only
    move up. A drop means it changed a verdict it should not have been able to
    reach.
    """
    result, _pairs, _dropped = measured
    n = result["pairs"]
    after = (result["identity"].get(SAME, 0)
             + sum(result["rescued"].values()))
    before = (measured_without_alias["identity"].get(SAME, 0)
              + sum(measured_without_alias["rescued"].values()))
    assert after > before, (
        "the alias table settled nothing: %d before, %d after" % (before, after))
    gain = 100.0 * (after - before) / n
    assert gain >= baseline.get("aliasGainPoints", 0) - 0.5, (
        "A7's gain fell to %.1f points from a recorded %.1f"
        % (gain, baseline.get("aliasGainPoints", 0)))
    assert result["aliasHits"] > 0
    assert measured_without_alias["aliasHits"] == 0, (
        "the table answered with use_alias=False -- the switch does not work")


def test_a_verdict_is_a_tuple_and_is_destructured(measured):
    """⚠ `same_series` returns (verdict, score, reason). Comparing the TUPLE
    to SAME silently reported 0 of every verdict, and the first run printed a
    0.0% identity rate that looked like a catastrophic regression and was a
    destructuring bug. **The tell was every bucket being zero at once.**"""
    result, _pairs, _dropped = measured
    counts = result["identity"]
    assert sum(counts.values()) == result["pairs"], counts
    assert set(counts) <= {SAME, UNSURE, DIFFERENT}, sorted(counts)
    assert counts.get(SAME, 0) > 0 and counts.get(UNSURE, 0) > 0


# ==========================================================================
# 🚨 fan-out -- what makes recall mean anything
# ==========================================================================

def test_fan_out_is_recorded_and_identity_materially_reduces_it(baseline):
    """🚨 An index returning every subtitle for every video has perfect recall
    and is useless.

    ⭐ Measured at CATALOGUE scale, which is adversarial: every show's episode
    1 collides with every other show's episode 1. Identity cuts the median
    from **282 to 103** — a real 2.7× — and leaves it ~13× over the
    8-candidate budget, which is precisely why A6 exists.
    """
    if baseline.get("medianFanOut") is None:
        pytest.skip("SKIPPED, NOT PASSED: the baseline carries no fan-out")
    assert baseline["medianFanOut"] > 0
    assert baseline["p95FanOut"] >= baseline["medianFanOut"]
