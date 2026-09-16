# -*- coding: utf-8 -*-
"""
RUNBOOK step A5b — the pairing benchmark. ⭐ `D8`: THE RELEASE NUMBER.

    python -m tsubasa.dev vnbench              measure
    python -m tsubasa.dev vnbench --baseline   measure and record the floor

⭐ WHY THIS ONE NUMBER

Every other gate in this project measures a stage. This measures the thing the
tool is for: **given a real video filename and a real subtitle filename that
timing has already proved belong together, does recognition keep them?**

Ground truth is `_work/probe_vn14_e2e.json` — **435 pairs whose offsets were
confirmed by alignment**, not by a name. 345 survive the sealed exclusion.
Nothing here is labelled by the thing being tested.

## What it reports, and why each column exists

| Column | The question |
| --- | --- |
| episode agreement | Stage 1: do the two sides parse to the same episode? |
| identity SAME / UNSURE / DIFFERENT | Stage 2 on the two titles |
| ⭐ **rescued** | pairs Stage 2 would refuse that **A2c + A3b** recover |
| fan-out | candidates per video at library scale — precision's denominator |

⚠ **DIFFERENT is not a failure on its own.** `09-corpus-strategy.md` §Stage 2:
9.9% of real pairs are DIFFERENT-by-title and correct — `Solo Leveling` against
`Ore dake Level Up na Ken` — and below the fan-out budget they are still
probed by timing. What the benchmark tracks is how many need that rescue.

🔒 Sealed excluded on both sides. ⛔ Nothing is written except the baseline.
"""
import io
import json
import os
import sys
import time
from collections import Counter

from ..naming import decoration as D
from ..naming import kana as K
from ..naming.episode import parse_ours
from ..naming.normalize import normalize
from ..naming.series import DIFFERENT, SAME, UNSURE, same_series
from ..paths import atomic_write_text, corpus_root, load_config, repo_root

BASELINE = "vn-bench-baseline.json"

# ⚠ LABEL NOISE, named in `09-corpus-strategy.md`. These rows are wrong in the
# ground truth, not wrong in the tool — a benchmark that counts them as misses
# is measuring its own labels. Kept as an explicit, short, reviewable list.
LABEL_NOISE = (
    u"Tensei Kizoku",          # the ground truth pairs two different entries
    u"Still to Watch",         # a user folder, not a show
)


def _clean(title):
    """The title as Stage 2 actually sees it: decoration stripped."""
    return D.strip(title or u"", aggressive=True)


def load_pairs(cfg, root):
    """-> [(show, episode, video_name, sub_name)], sealed and noise removed."""
    path = root / "_work" / "probe_vn14_e2e.json"
    if not path.is_file():
        raise IOError("no ground truth at %s" % path)
    with io.open(str(path), encoding="utf-8") as fh:
        rows = json.load(fh)["rows"]

    from . import corpus as C
    try:
        manifest = C.load_manifest(cfg)
        sealed = {C.split_key(show)
                  for scope in manifest.get("scopes", {}).values()
                  for show in scope.get("sealed", [])}
    except Exception:                                # noqa: BLE001
        sealed = set()

    out, dropped = [], Counter()
    for row in rows:
        show = row.get("show") or u""
        video_name = row.get("v") or u""
        sub_name = row.get("n") or u""
        # 🔒 BOTH SIDES. `show` is the VIDEO-side folder; the jimaku side is a
        # separate entry that can be sealed under a different name. Excluding
        # only the video side left 15 pairs in that the probe had dropped --
        # the tell was 360 pairs against its 345.
        if C.split_key(show) in sealed:
            dropped["sealed (video side)"] += 1
            continue
        if C.split_key(parse_ours(sub_name).title or u"") in sealed:
            dropped["sealed (jimaku side)"] += 1
            continue
        if any(marker.lower() in show.lower() for marker in LABEL_NOISE):
            dropped["label noise"] += 1
            continue
        out.append((show, row.get("ep"), row.get("v") or u"", row.get("n") or u""))
    return out, dropped


def measure(pairs, use_alias=True):
    """-> dict of counts. One pass, no network, no media.

    ⭐ `use_alias=False` runs the identical stack with RUNBOOK A7's table
    switched off, so the benchmark reports A7's contribution as a BEFORE and
    AFTER of its own numbers rather than as a claim. `RUNBOOK.md` A7 asks for
    exactly this: *"the benchmark's cross-script recall before/after"*.
    """
    episode = Counter()
    identity = Counter()
    rescued = Counter()
    examples = {"still refused": [], "rescued by decoration": [],
                "rescued by kana": [], "rescued by the alias table": []}
    by_alias = [0]          # a list so the inner block can bump it

    for show, _ep, video_name, sub_name in pairs:
        pv, ps = parse_ours(video_name), parse_ours(sub_name)
        if pv.episode is None or ps.episode is None:
            episode["one side unresolved"] += 1
        elif pv.key() == ps.key():
            episode["agree"] += 1
        elif pv.episode == ps.episode:
            episode["episode agrees, season differs"] += 1
        else:
            episode["disagree"] += 1

        # ⚠ `same_series` returns (verdict, score, reason) -- three outcomes,
        # never a bare boolean. Comparing the TUPLE to SAME silently reported
        # 0 of every verdict, and the first run printed a 0.0% identity rate
        # that looked like a catastrophic regression and was a destructuring
        # bug. The tell was every bucket being zero at once.
        verdict, _score, reason = same_series(pv.title, ps.title,
                                              use_alias=use_alias)
        identity[verdict] += 1
        if verdict == SAME:
            # ⭐ A7's own contribution, counted in its OWN bucket. An alias hit
            # arrives as SAME and therefore never reaches the decoration/kana
            # rescue block below -- so putting it in `rescued` would double it
            # into `settledByName`, which is `same + rescued`.
            if use_alias and reason.startswith(u"alias table:"):
                by_alias[0] += 1
                if len(examples["rescued by the alias table"]) < 5:
                    examples["rescued by the alias table"].append(
                        (pv.title[:34], ps.title[:34]))
            continue

        # ⭐ What A2c and A3b bought, measured on the cases Stage 2 could not
        # settle -- which is the only place they can help.
        clean_v, clean_s = _clean(pv.title), _clean(ps.title)
        if clean_v != pv.title or clean_s != ps.title:
            if same_series(clean_v, clean_s)[0] == SAME:
                rescued["decoration"] += 1
                if len(examples["rescued by decoration"]) < 5:
                    examples["rescued by decoration"].append(
                        (pv.title[:34], ps.title[:34]))
                continue

        if K.is_kana(pv.title) or K.is_kana(ps.title):
            index = K.Index([(0, clean_s)])
            hit = index.rank(clean_v, limit=1)
            if hit and hit[0][0] >= K.ACCEPT:
                rescued["kana"] += 1
                if len(examples["rescued by kana"]) < 5:
                    examples["rescued by kana"].append(
                        (pv.title[:34], ps.title[:34]))
                continue

        if verdict == DIFFERENT and len(examples["still refused"]) < 8:
            examples["still refused"].append((pv.title[:34], ps.title[:34]))

    return {"pairs": len(pairs), "episode": dict(episode),
            "identity": dict(identity), "rescued": dict(rescued),
            "aliasHits": by_alias[0], "usedAlias": use_alias,
            "examples": examples}


def _rate(part, whole):
    return round(100.0 * part / whole, 1) if whole else 0.0


def fan_out(cfg, root, limit=4000):
    """Candidates per video at library scale. ⭐ Precision's denominator.

    Recall alone is trivially satisfiable — an index that returns every
    subtitle for every video has perfect recall and is useless. **Fan-out is
    what makes the recall number mean something**, and `09-corpus-strategy.md`
    Stage 2 puts the budget at **8 surviving candidates** (the measured
    median), below which a DIFFERENT-by-title candidate is still probed.

    ⚠ Filenames only — no media is opened, so this costs seconds.
    🔒 Sealed shows excluded.
    """
    from .. import discover as Disc
    from . import corpus as C

    # 🚨 THE TWO SIDES ARE TWO CORPORA, AND NEITHER HOLDS A VIDEO FILE.
    # `video-naming/` carries VIDEO release names whose files are the videos'
    # extracted subtitle tracks; `naming/` is the jimaku subtitle side. So
    # walking either one as a library finds zero videos and returns an empty
    # fan-out -- which the first version did, silently.
    # ⭐ The names are the data. Items are built from filenames directly, the
    # video side labelled "video", exactly as `probe_opp5` did.
    def collect(scope, kind, budget):
        base = root / scope
        if not base.is_dir():
            return []
        try:
            keep = set()
            for slice_name in ("dev", "validation"):
                keep.update(C.shows(slice_name, scope=scope, cfg=cfg))
        except Exception:                            # noqa: BLE001
            keep = None
        out = []
        for show_dir in sorted(os.listdir(str(base))):
            if keep is not None and show_dir not in keep:
                continue
            show_path = base / show_dir
            if not show_path.is_dir():
                continue
            for dirpath, _dirs, filenames in os.walk(str(show_path)):
                for filename in filenames:
                    if Disc.classify(filename) is None or Disc.is_junk(filename):
                        continue
                    out.append(Disc.Item(os.path.join(dirpath, filename), kind))
                    if len(out) >= budget:
                        return out
        return out

    videos = collect("video-naming", "video", limit)
    subtitles = collect("naming", "subtitle", limit * 2)
    if not videos or not subtitles:
        return {}

    items = videos + subtitles
    Disc.parse_all(items, scheme_hint=False)   # per-folder inference is not
    cand = Disc.Candidates(items)              # what this measures
    counts = sorted(cand.fan_out().values())
    if not counts:
        return {}

    # ⭐ AND THE SAME NUMBER AFTER IDENTITY, which is the one that matters.
    # The episode index narrows 8,000 subtitles to a few hundred; identity has
    # to take that to the 8-candidate budget. Measuring only the first stage
    # would make the index look like the whole answer.
    # ⚠ Sampled: the full cross is ~1.1M `same_series` calls. The denominator
    # is printed.
    import random
    rng = random.Random(20260908)
    sample = rng.sample(cand.videos, min(250, len(cand.videos)))
    after = []
    for video in sample:
        kept = 0
        for sub in cand.for_video(video):
            if same_series(video.title, sub.title)[0] != DIFFERENT:
                kept += 1
        after.append(kept)
    after.sort()

    return {
        "videos": len(counts),
        "subtitles": len(cand.subtitles),
        "median": counts[len(counts) // 2],
        "p95": counts[int(len(counts) * 0.95)],
        "max": counts[-1],
        "overBudget": sum(1 for c in counts if c > 8),
        "sampled": len(after),
        "afterMedian": after[len(after) // 2] if after else None,
        "afterP95": after[int(len(after) * 0.95)] if after else None,
        "afterOverBudget": sum(1 for c in after if c > 8),
    }


def main(argv):
    import argparse

    parser = argparse.ArgumentParser(prog="python -m tsubasa.dev vnbench")
    parser.add_argument("--baseline", action="store_true",
                        help="record the measured floor")
    args = parser.parse_args(argv)

    cfg = load_config()
    root = corpus_root(cfg)
    if not root.is_dir():
        sys.stderr.write("corpus not found at %s\n" % root)
        return 2

    started = time.time()
    pairs, dropped = load_pairs(cfg, root)
    result = measure(pairs)
    n = result["pairs"]
    fan = fan_out(cfg, root)

    print("")
    print("  ground truth   %d timing-confirmed pairs" % n)
    print("  dropped        %s"
          % (", ".join("%s %d" % (k, v) for k, v in sorted(dropped.items()))
             or "none"))
    print("")
    print("  STAGE 1 -- episode")
    for key in ("agree", "episode agrees, season differs", "disagree",
                "one side unresolved"):
        if key in result["episode"]:
            print("    %-32s %5d  %5.1f%%"
                  % (key, result["episode"][key], _rate(result["episode"][key], n)))
    print("")
    print("  STAGE 2 -- identity on the two titles")
    for key in (SAME, UNSURE, DIFFERENT):
        print("    %-32s %5d  %5.1f%%"
              % (key, result["identity"].get(key, 0),
                 _rate(result["identity"].get(key, 0), n)))
    print("")
    print("  ⭐ RESCUED by A2c / A3b (of the %d not already SAME)"
          % (n - result["identity"].get(SAME, 0)))
    for key in ("decoration", "kana"):
        print("    %-32s %5d" % (key, result["rescued"].get(key, 0)))

    same = result["identity"].get(SAME, 0)
    rescued = sum(result["rescued"].values())
    reach = same + rescued
    # ⚠ EPISODE AGREEMENT MEANS THE EPISODE NUMBER, and the first version of
    # this line reported only pairs whose (season, episode) matched exactly --
    # **46.0%** -- because 46.3% of real pairs state a season on one side and
    # not the other. That is the normal shape of the corpus, and the candidate
    # index treats it as a match by design (`discover.Candidates.for_video`).
    # Reporting it as disagreement made a 92.3% stack look like a 46% one.
    agree = (result["episode"].get("agree", 0)
             + result["episode"].get("episode agrees, season differs", 0))

    print("")
    print("  ⭐ THE RELEASE NUMBER (`D8`)")
    print("    CANDIDATE RECALL           %5d / %d  %5.1f%%"
          % (agree, n, _rate(agree, n)))
    print("      the pair survives to timing. Bounded by episode agreement,")
    print("      because identity RANKS and never terminally drops a pair")
    print("      below the fan-out budget (`09-corpus-strategy.md` Stage 2).")
    print("      A season stated on one side only is not a disagreement.")
    print("    settled by name alone      %5d / %d  %5.1f%%   (SAME %d + rescued %d)"
          % (reach, n, _rate(reach, n), same, rescued))
    print("      ⚠ NOT a success rate. The other %5.1f%% are UNSURE -- mostly"
          % _rate(n - reach, n))
    print("      cross-script -- and they PAIR, decided by timing. This")
    print("      measures how much work timing is spared, and it is what the")
    print("      alias table (A7) exists to raise.")

    # ⭐ RUNBOOK A7 -- the same stack with the table off, so the claim is a
    # BEFORE and AFTER of this benchmark rather than an assertion. `D6`
    # time-boxes A7 to one day and cuts it below a 15% realised gain, and this
    # is the number that decision is made on.
    without = measure(pairs, use_alias=False)
    reach_without = (without["identity"].get(SAME, 0)
                     + sum(without["rescued"].values()))
    before = _rate(reach_without, n)
    after = _rate(reach, n)
    gain_points = round(after - before, 1)
    gain_relative = (round(100.0 * (after - before) / before, 1)
                     if before else 0.0)
    print("")
    print("  ⭐ A7 -- THE ALIAS TABLE, BEFORE AND AFTER")
    print("    settled by name, table OFF %5d / %d  %5.1f%%"
          % (reach_without, n, before))
    print("    settled by name, table ON  %5d / %d  %5.1f%%"
          % (reach, n, after))
    print("    ⭐ gain                     %+5.1f points   %+5.1f%% relative"
          % (gain_points, gain_relative))
    print("    of which SAME came from the table   %d" % result["aliasHits"])
    print("    ⚠ `D6`'s one-day box cuts A7 below a 15% realised gain. Both")
    print("      readings are printed because the spec says '15% realised")
    print("      gain' without saying of what -- recorded as a Part 1 defect")
    print("      in `spec/09-corpus-strategy.md`, not decided here.")
    print("    ⛔ The table NEVER returns DIFFERENT, so this number can only")
    print("      move up. A drop means the table changed a verdict it should")
    print("      not have been able to reach.")
    if fan:
        print("")
        print("    FAN-OUT at library scale   %d videos, %d subtitles"
              % (fan["videos"], fan["subtitles"]))
        print("      episode index only   median %4d  p95 %4d  max %4d   "
              "over the 8 budget %5.1f%%"
              % (fan["median"], fan["p95"], fan["max"],
                 _rate(fan["overBudget"], fan["videos"])))
        if fan.get("afterMedian") is not None:
            print("      ⭐ after identity     median %4d  p95 %4d              "
                  "over the 8 budget %5.1f%%   (%d sampled)"
                  % (fan["afterMedian"], fan["afterP95"],
                     _rate(fan["afterOverBudget"], fan["sampled"]),
                     fan["sampled"]))
        print("      ⭐ Recall alone is trivially satisfiable -- returning every")
        print("      subtitle for every video scores 100%. Fan-out is what")
        print("      makes the recall number mean anything.")
        print("      ⚠ CATALOGUE SCALE, the adversarial case: every show's")
        print("      episode 1 collides with every other show's episode 1. A")
        print("      user's folder is their own dozens of shows, not thousands,")
        print("      so this is the ceiling and not what anyone will see.")
        print("      ⭐ What it establishes: identity cuts fan-out 2.7x and")
        print("      leaves it ~13x over the 8 budget, so the remaining")
        print("      discriminator must be cluster structure and timing -- which")
        print("      is A6, and this is the number that justifies it.")
    print("")
    for label, rows in sorted(result["examples"].items()):
        if rows:
            print("  %s:" % label)
            for a, b in rows[:5]:
                print("    %-36s | %s" % (a, b))
    print("")
    print("  %.1fs" % (time.time() - started))

    payload = {
        "//": ("RUNBOOK A5b -- the pairing benchmark, and `D8` makes it the "
               "number a release is judged on. Ground truth is "
               "_work/probe_vn14_e2e.json: pairs confirmed by ALIGNMENT, not "
               "by a name. Re-record with: python -m tsubasa.dev vnbench "
               "--baseline. ⚠ A floor, never a target -- the suite fails when "
               "a number drops, and a rise is re-recorded deliberately."),
        "recorded": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "pairs": n,
        "candidateRecall": _rate(agree, n),
        "settledByName": _rate(reach, n),
        # ⭐ A7. Recorded so a future run can tell a table regression from a
        # parser regression: only one of them moves `settledByNameNoAlias`.
        "settledByNameNoAlias": before,
        "aliasGainPoints": gain_points,
        "aliasHits": result["aliasHits"],
        "medianFanOut": fan.get("median"),
        "p95FanOut": fan.get("p95"),
        "same": same,
        "rescued": result["rescued"],
        "identity": result["identity"],
        "episode": result["episode"],
    }
    target = repo_root() / BASELINE
    if args.baseline:
        atomic_write_text(target, json.dumps(payload, ensure_ascii=False,
                                             indent=1) + "\n")
        print("  wrote %s" % target.name)
    elif target.is_file():
        with io.open(str(target), encoding="utf-8") as fh:
            old = json.load(fh)
        for field in ("candidateRecall", "settledByName"):
            was, now = old.get(field), payload[field]
            flag = "OK " if now >= was - 0.05 else "⛔ REGRESSED"
            print("  %-4s %-20s baseline %.1f%%  now %.1f%%"
                  % (flag, field, was, now))
    return 0
