# -*- coding: utf-8 -*-
"""
Derive the series-identity thresholds from the corpus. RUNBOOK step A3.

    python -m tsubasa.dev seriesgate

🚨 A3 IS THE RISKY STEP. Keeping CJK in the slug fixes Naruto / Naruto 疾風伝 --
the discriminating information was being thrown away -- but it makes matching
LESS PERMISSIVE, so Japanese-named files that used to pair on an empty slug may
stop. The spec is explicit that the threshold must be RE-TUNED against the dev
corpus and BOTH DIRECTIONS asserted, not inherited.

⭐ Ground truth is free here: `naming/<show>/` is a show. Two files in one
directory are the same series; two files in different directories are not.

⚠ And the negatives that matter are the HARD ones -- `Naruto` vs
`Naruto 疾風伝`, `Aria the Animation` vs `Aria the Natural`. Sampling random
pairs measures a problem nobody has: almost any two random shows are obviously
different. This deliberately over-samples pairs whose names already look alike,
because those are the only ones a threshold has to adjudicate.

Rule 2 of the pack: **every threshold sits in a MEASURED empty band between
real cases and controls.** A threshold set by taste breaks the value
proposition, so this prints the band and refuses to invent one that is not
there.
"""
import os
import random
import sys
import time
from collections import defaultdict

from ..naming.series import (DIFFERENT, SAME, UNSURE, same_series, similarity)
from ..paths import corpus_root, load_config

PAIRS_PER_CLASS = 4000


def collect(cfg, root, slices=("dev",)):
    """show -> [filenames]. Directory membership is the ground truth."""
    from . import corpus as C

    shows = defaultdict(list)
    for scope in sorted(cfg["corpus"]["split"]):
        spec = cfg["corpus"]["split"][scope]
        base = root / scope
        if spec["showsAt"] != "*":
            base = base / spec["showsAt"].rstrip("/*").rstrip("/")
        if not base.is_dir():
            continue
        for slice_name in slices:
            for show in C.shows(slice_name, scope=scope, cfg=cfg):
                d = base / show
                if not d.is_dir():
                    continue
                names = [f for f in os.listdir(str(d))
                         if not f.startswith("_") and not f.endswith(".json")]
                if names:
                    shows["%s/%s" % (scope, show)] = names
    return shows


def title_of(filename):
    from ..naming.episode import parse_ours
    p = parse_ours(filename)
    return p.title or filename


def percentiles(values, ps):
    if not values:
        return {p: 0.0 for p in ps}
    s = sorted(values)
    out = {}
    for p in ps:
        i = min(len(s) - 1, max(0, int(round((p / 100.0) * (len(s) - 1)))))
        out[p] = s[i]
    return out


def main(argv):
    import argparse

    parser = argparse.ArgumentParser(prog="python -m tsubasa.dev seriesgate")
    parser.add_argument("-n", type=int, default=PAIRS_PER_CLASS)
    parser.add_argument("--seed", type=int, default=20260908)
    parser.add_argument("--show", type=int, default=12)
    args = parser.parse_args(argv)

    cfg = load_config()
    root = corpus_root(cfg)
    if not root.is_dir():
        sys.stderr.write("corpus not found at %s\n" % root)
        return 2

    sys.stderr.write("collecting shows (dev slice only)...\n")
    shows = collect(cfg, root)
    sys.stderr.write("  %d shows with files\n" % len(shows))

    rng = random.Random(args.seed)
    names = sorted(shows)

    # ---- positives: two files from the SAME show --------------------
    positives = []
    multi = [s for s in names if len(shows[s]) >= 2]
    for _ in range(args.n):
        if not multi:
            break
        s = rng.choice(multi)
        a, b = rng.sample(shows[s], 2)
        positives.append((s, title_of(a), title_of(b)))

    # ---- negatives: two files from DIFFERENT shows ------------------
    # ⚠ Over-sample HARD negatives -- shows whose folded keys already share a
    # prefix. Random pairs are trivially separable and measuring them produces
    # a band that looks wide and is not.
    # 🚨 Bucket on the SPLIT KEY, not a raw normalise. `naming/` directories are
    # spelled `NNNNN Title`, so a raw key starts with the scrape ordinal --
    # 95.4% of shows landed in an all-digit bucket and the "deliberately hard"
    # negatives were pairs like `10495 Konbanwa...` vs `10492 Saint Oniisan`,
    # which share nothing but a number. Measured: the false-match rate reads
    # 0.5% on that pool and 4.4% on a genuinely title-keyed one.
    from ..naming.normalize import normalize
    from .corpus import split_key
    by_prefix = defaultdict(list)
    for s in names:
        k = normalize(split_key(s.split("/", 1)[1])).key
        if len(k) >= 4:
            by_prefix[k[:4]].append(s)
    hard_pool = [v for v in by_prefix.values() if len(v) >= 2]

    # 🚨 GROUND-TRUTH CONTAMINATION, found by the first run of this probe.
    # Two DIRECTORIES can hold the same show -- the corpus has `Dr Stone` and
    # `Dr Stone` under different scrape ids. Labelling those "different shows"
    # and then reporting a false positive at 1.000 measures MY LABELLING, not
    # the matcher. Exclude any pair whose directory names fold to one key.
    contaminated = 0
    negatives = []
    for i in range(args.n):
        if hard_pool and i % 2 == 0:
            group = rng.choice(hard_pool)
            s1, s2 = rng.sample(group, 2)
        else:
            s1, s2 = rng.sample(names, 2)
        if s1 == s2:
            continue
        # ⚠ Use the corpus split key, not a raw normalise: directory names
        # carry a scrape ordinal (`01403 Dr Stone`), so normalising them
        # directly makes two copies of one show look like different keys and
        # the filter silently never fires. It reported 0 contaminated while
        # `Dr Stone` vs `Dr Stone` sat at the top of the false-positive list.
        from .corpus import split_key
        d1 = split_key(s1.split("/", 1)[1])
        d2 = split_key(s2.split("/", 1)[1])
        if d1 == d2:
            contaminated += 1
            continue
        negatives.append((s1, s2,
                          title_of(rng.choice(shows[s1])),
                          title_of(rng.choice(shows[s2]))))

    # ---- score -------------------------------------------------------
    t0 = time.time()
    pos_scores = [similarity(a, b) for _s, a, b in positives]
    neg_scores = [similarity(a, b) for _s1, _s2, a, b in negatives]
    elapsed = time.time() - t0

    print("=" * 74)
    print("SERIES IDENTITY -- threshold derivation (A3)")
    print("=" * 74)
    print("  shows (dev slice)      %6d" % len(shows))
    print("  same-show pairs        %6d" % len(pos_scores))
    print("  different-show pairs   %6d  (half deliberately HARD)" % len(neg_scores))
    print("  dropped as contaminated %5d  (two dirs, one show -- not a valid"
          " negative)" % contaminated)
    print("  scoring                %6.1fs  (%.3f ms/pair)"
          % (elapsed, 1000.0 * elapsed / max(1, len(pos_scores) + len(neg_scores))))

    # ⭐ Partition by script BEFORE deriving a band. A cross-script pair never
    # reaches the threshold -- `same_series` short-circuits it to UNSURE,
    # because kana is not Latin and no number can bridge that. Including those
    # zeros in the distribution measures the alias-table gap and calls it a
    # threshold problem, which are different problems with different fixes.
    from ..naming.normalize import normalize as _N
    from ..naming.series import cross_script

    # 🚨 Filter the PAIRS alongside the scores. A first version replaced only
    # the score lists and then indexed `pairs[i]` with `i` from the filtered
    # list -- so every diagnostic the gate printed named the wrong pair, and
    # the verdict table it produced was copied into series.py as the
    # derivation record. Two lists, one index: filter both or neither.
    def split_by_script(pairs, scores, ia, ib):
        same_s, cross_s, same_p, cross_p = [], [], [], []
        for i, sc in enumerate(scores):
            a, b = pairs[i][ia], pairs[i][ib]
            if cross_script(_N(a), _N(b)):
                cross_s.append(sc)
                cross_p.append(pairs[i])
            else:
                same_s.append(sc)
                same_p.append(pairs[i])
        return same_s, cross_s, same_p, cross_p

    pos_same, pos_cross, positives_same, _pc = split_by_script(
        positives, pos_scores, 1, 2)
    neg_same, neg_cross, negatives_same, _nc = split_by_script(
        negatives, neg_scores, 2, 3)

    print("")
    print("  SCRIPT SPLIT -- cross-script pairs bypass the threshold entirely")
    print("    same-show:  %5d same-script, %5d cross-script (%.1f%%)"
          % (len(pos_same), len(pos_cross),
             100.0 * len(pos_cross) / max(1, len(pos_scores))))
    print("    diff-show:  %5d same-script, %5d cross-script (%.1f%%)"
          % (len(neg_same), len(neg_cross),
             100.0 * len(neg_cross) / max(1, len(neg_scores))))
    print("    ^ the cross-script share of SAME-show pairs is the alias-table")
    print("      gap (RUNBOOK A7), not a tuning problem.")

    pos_scores_all, neg_scores_all = pos_scores, neg_scores
    pos_scores, neg_scores = pos_same, neg_same
    positives, negatives = positives_same, negatives_same   # keep them aligned

    pp = percentiles(pos_scores, [1, 5, 10, 25, 50])
    np_ = percentiles(neg_scores, [50, 75, 90, 95, 99])

    print("")
    print("  SAME show (want HIGH):     min %.3f  p1 %.3f  p5 %.3f  p10 %.3f  median %.3f"
          % (min(pos_scores) if pos_scores else 0, pp[1], pp[5], pp[10], pp[50]))
    print("  DIFF show (want LOW):   median %.3f  p75 %.3f  p90 %.3f  p95 %.3f  p99 %.3f  max %.3f"
          % (np_[50], np_[75], np_[90], np_[95], np_[99],
             max(neg_scores) if neg_scores else 0))

    # ---- the band ----------------------------------------------------
    print("")
    print("  ⭐ THE BAND")
    p5 = pp[5]
    n95 = np_[95]
    if p5 > n95:
        print("     EMPTY BAND EXISTS: %.3f (diff p95) .. %.3f (same p5)" % (n95, p5))
        print("     A single threshold at %.3f separates 95%% of both classes."
              % ((p5 + n95) / 2))
    else:
        print("     ⚠ NO EMPTY BAND. same-p5 %.3f <= diff-p95 %.3f -- the classes"
              % (p5, n95))
        print("       OVERLAP, so no single threshold works and the UNSURE rung")
        print("       is structural, not a refinement. This is the same shape as")
        print("       the verdict problem (spec/05-interface.md).")

    # ---- what the current constants do -------------------------------
    print("")
    print("  CURRENT CONSTANTS (same_at / different_below):")
    for label, scores, want in (("same-show", pos_scores, SAME),
                                ("diff-show", neg_scores, DIFFERENT)):
        v = {SAME: 0, UNSURE: 0, DIFFERENT: 0}
        pairs = positives if label == "same-show" else negatives
        for i, sc in enumerate(scores):
            a, b = (pairs[i][1], pairs[i][2]) if label == "same-show" \
                else (pairs[i][2], pairs[i][3])
            # ⛔ `use_alias=False`. This gate DERIVES `SAME_AT` and
            # `DIFFERENT_BELOW`, which are thresholds on the CHARACTER score.
            # Letting RUNBOOK A7's table answer here would fold a second,
            # unrelated mechanism into the verdict table that `series.py`
            # carries as its derivation record -- and the thresholds would then
            # be fitted to a distribution the score never produced.
            # `LEDGER.md` §Harness: a check can pass through a filter that is
            # not the one it is named for, and this gate has already been
            # wrong once (the filtered-scores / unfiltered-pairs index bug).
            verdict, _s, _r = same_series(a, b, use_alias=False)
            v[verdict] += 1
        tot = float(len(scores)) or 1.0
        print("    %-10s SAME %5.1f%%   UNSURE %5.1f%%   DIFFERENT %5.1f%%"
              % (label, 100 * v[SAME] / tot, 100 * v[UNSURE] / tot,
                 100 * v[DIFFERENT] / tot))

    print("")
    print("  🚨 The number that matters is the bottom-left one: a DIFFERENT-show")
    print("     pair called SAME is a confidently wrong pairing. UNSURE is not a")
    print("     failure -- it goes to timing arbitration.")

    worst = sorted(range(len(neg_scores)), key=lambda i: -neg_scores[i])[:args.show]
    print("")
    print("  hardest false-positive candidates (different shows, highest score):")
    for i in worst:
        s1, s2, a, b = negatives[i]
        print("    %.3f  %-32s  vs  %s" % (neg_scores[i], a[:32], b[:32]))

    lowest = sorted(range(len(pos_scores)), key=lambda i: pos_scores[i])[:args.show]
    print("")
    print("  hardest false-negative candidates (same show, lowest score):")
    for i in lowest:
        s, a, b = positives[i]
        print("    %.3f  %-32s  vs  %s" % (pos_scores[i], a[:32], b[:32]))

    return 0
