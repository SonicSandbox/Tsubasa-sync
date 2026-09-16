# -*- coding: utf-8 -*-
"""
The parser regression gate. RUNBOOK step A2b.

    python -m tsubasa.dev parsergate            # sample, report
    python -m tsubasa.dev parsergate --all      # every dev+validation filename
    python -m tsubasa.dev parsergate --baseline # record the current numbers

⭐ Every distinct filename fingerprint in the corpus is one test case. Coverage
is a NUMBER THAT MUST NOT REGRESS -- a change that lowers it fails, even when
it looks like a simplification.

🚨 THE RULE THAT MAKES THIS METRIC HONEST:

    ⛔ A FILM IS NOT A PARSER FAILURE.

~8% of the corpus parses to nothing under all three parsers, and inspection
shows it is overwhelmingly films, specials, OVAs and date-stamped broadcasts
that CORRECTLY have no episode number. A first-pass classifier called half of
that bucket "possible missed pattern" purely because the names contained digits
-- resolution, year, codec (spec/09-corpus-strategy.md).

**Any coverage metric that counts those as failures chases a target that should
not move.** So three verdicts, not two:

    RESOLVED       an episode number was produced
    EPISODE-LESS   correctly has none, or is a range/conjunction we refuse
    MISSED         🚨 the only real failure

⭐ Rule 4 applied: this reads FILENAMES ONLY. Not one file is opened.
🔒 dev + validation only.
"""
import io
import json
import os
import random
import sys
import time
from collections import Counter

from ..naming.episode import (BATCH, CONJUNCTION, EPISODE, FILM, UNKNOWN,
                              parse_anitopy, parse_guessit, parse_ours, union)
from ..paths import corpus_root, load_config, repo_root, write_json

BASELINE = "parser-gate-baseline.json"
SAMPLE_DEFAULT = 3000

RESOLVED = "resolved"
EPISODE_LESS = "episode-less"
ARBITRATE = "arbitrate"
MISSED = "missed"


def iter_filenames(cfg, root, slices=("dev", "validation")):
    """Filenames only. Nothing is opened."""
    from . import corpus as C

    for scope in sorted(cfg["corpus"]["split"]):
        spec = cfg["corpus"]["split"][scope]
        base = root / scope
        if spec["showsAt"] != "*":
            base = base / spec["showsAt"].rstrip("/*").rstrip("/")
        if not base.is_dir():
            continue
        for slice_name in slices:
            for show in C.shows(slice_name, scope=scope, cfg=cfg):
                show_dir = base / show
                if not show_dir.is_dir():
                    continue
                for dirpath, _d, files in os.walk(str(show_dir)):
                    for fn in files:
                        if fn.startswith("_") or fn.endswith(".json"):
                            continue
                        yield scope, show, fn


def classify(parsed_or_union):
    """Four verdicts, and only ONE of them is a defect.

    ⚠ A first version of this collapsed ARBITRATE into MISSED and reported
    coverage as 65.2% when it was really ~96%. A parser DISAGREEMENT is not a
    failure -- it is a candidate SET, and timing arbitration is the stage that
    already exists to resolve one. Counting it as a miss measures the wrong
    thing and would have sent the next week of work at a non-problem.
    """
    kind = parsed_or_union.kind
    if kind == EPISODE and parsed_or_union.episode is not None:
        return RESOLVED
    if getattr(parsed_or_union, "candidates", None):
        return ARBITRATE
    if kind in (FILM, BATCH, CONJUNCTION):
        return EPISODE_LESS
    return MISSED


def main(argv):
    import argparse

    parser = argparse.ArgumentParser(prog="python -m tsubasa.dev parsergate")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("-n", type=int, default=SAMPLE_DEFAULT)
    parser.add_argument("--seed", type=int, default=20260908)
    parser.add_argument("--baseline", action="store_true",
                        help="record these numbers as the floor")
    parser.add_argument("--no-guessit", action="store_true",
                        help="skip guessit (it is by far the slowest)")
    parser.add_argument("--show", type=int, default=20)
    args = parser.parse_args(argv)

    cfg = load_config()
    root = corpus_root(cfg)
    if not root.is_dir():
        sys.stderr.write("corpus not found at %s\n" % root)
        return 2

    sys.stderr.write("collecting filenames...\n")
    names = [(sc, sh, fn) for sc, sh, fn in iter_filenames(cfg, root)]
    sys.stderr.write("  %d filenames in dev+validation\n" % len(names))

    if not args.all:
        rng = random.Random(args.seed)
        names = rng.sample(names, min(args.n, len(names)))

    verdicts = Counter()
    per_parser = {"ours": Counter(), "anitopy": Counter(), "guessit": Counter()}
    union_states = Counter()
    kinds = Counter()
    missed = []
    # 🚨 The measurement that justified the union at all: how often does OURS
    # fail while another parser succeeds? Measured at 13.2% -- one in eight.
    ours_missed_other_got = 0
    other_missed_ours_got = 0

    t0 = time.time()
    for i, (_scope, _show, fn) in enumerate(names, 1):
        ours = parse_ours(fn)
        per_parser["ours"][classify(ours)] += 1
        kinds[ours.kind] += 1

        ani = parse_anitopy(fn)
        if ani is not None:
            per_parser["anitopy"][
                RESOLVED if ani.episode is not None else MISSED] += 1

        gue = None
        if not args.no_guessit:
            gue = parse_guessit(fn)
            if gue is not None:
                per_parser["guessit"][
                    RESOLVED if gue.episode is not None else MISSED] += 1

        others = [p for p in (ani, gue) if p is not None and p.episode is not None]
        if ours.episode is None and others and ours.kind not in (BATCH, CONJUNCTION, FILM):
            ours_missed_other_got += 1
        if ours.episode is not None and not others and (ani or gue):
            other_missed_ours_got += 1

        u = union(fn)
        union_states[u.state] += 1
        v = classify(u)
        verdicts[v] += 1
        if v == MISSED and len(missed) < 400:
            missed.append(fn)

        if i % 1000 == 0:
            sys.stderr.write("    %d/%d  %.0fs\n" % (i, len(names), time.time() - t0))
            sys.stderr.flush()

    n = len(names)
    elapsed = time.time() - t0

    def pct(c):
        return 100.0 * c / n if n else 0.0

    print("=" * 74)
    print("PARSER REGRESSION GATE  (A2b)")
    print("=" * 74)
    print("  filenames            %7d %s" % (n, "(ALL)" if args.all else "(sample)"))
    print("  elapsed              %7.1fs  (%.2f ms/name)"
          % (elapsed, 1000.0 * elapsed / n if n else 0))
    print("")
    print("  ⭐ UNION COVERAGE")
    print("    resolved           %7d  %5.1f%%" % (verdicts[RESOLVED], pct(verdicts[RESOLVED])))
    print("    to arbitration     %7d  %5.1f%%   (a candidate set, not a failure)"
          % (verdicts[ARBITRATE], pct(verdicts[ARBITRATE])))
    print("    episode-less (ok)  %7d  %5.1f%%" % (verdicts[EPISODE_LESS], pct(verdicts[EPISODE_LESS])))
    print("    🚨 missed           %7d  %5.1f%%" % (verdicts[MISSED], pct(verdicts[MISSED])))
    print("")
    accounted_n = verdicts[RESOLVED] + verdicts[ARBITRATE] + verdicts[EPISODE_LESS]
    print("    ⭐ ACCOUNTED FOR    %7d  %5.1f%%   <- the gate"
          % (accounted_n, pct(accounted_n)))

    print("")
    print("  per parser (episode found):")
    for name in ("ours", "anitopy", "guessit"):
        c = per_parser[name]
        tot = sum(c.values())
        if tot:
            print("    %-10s %7d / %-7d  %5.1f%%"
                  % (name, c[RESOLVED], tot, 100.0 * c[RESOLVED] / tot))
        else:
            print("    %-10s not available" % name)

    print("")
    print("  🚨 ours missed, another parser succeeded: %d  (%.1f%%)"
          % (ours_missed_other_got, pct(ours_missed_other_got)))
    print("     ^ this is why all three run. spec/09 recorded 13.2%% when ours")
    print("       was at 79.0%%; ours has since risen, so expect this LIVE")
    print("       figure to be lower. Do not read the spec's number as current.")
    print("     ours succeeded where every other failed: %d  (%.1f%%)"
          % (other_missed_ours_got, pct(other_missed_ours_got)))

    print("")
    print("  union agreement:")
    for state, c in union_states.most_common():
        print("    %-10s %7d  %5.1f%%" % (state, c, pct(c)))

    print("")
    print("  our classification:")
    for k, c in kinds.most_common():
        print("    %-12s %7d  %5.1f%%" % (k, c, pct(c)))

    if missed:
        print("")
        print("  🚨 MISSED -- an episode is probably there and we did not find it:")
        for fn in missed[:args.show]:
            print("    %s" % fn[:88])
        if len(missed) > args.show:
            print("    ...and %d more" % (len(missed) - args.show))

    # ---- 🚨 the population the gate could not see ----------------------
    #
    # `western-naming` is a names-only TEXT FILE, so it lives under `fixtures`
    # rather than `split` -- and `iter_filenames()` therefore never yielded one
    # Western release name. The 97.4% headline was computed on an all-anime
    # population while spec/06 §1.3 devotes five rows to Western naming.
    #
    # ⛔ Reported SEPARATELY, never averaged in. They are two naming cultures
    # and one number over both hides whichever is worse.
    western = root / "western-naming" / "release_names.txt"
    if western.is_file():
        wnames = [l.strip() for l in
                  io.open(str(western), encoding="utf-8", errors="replace")
                  if l.strip()]
        if wnames:
            wv = Counter()
            wyear = 0
            for fn in wnames:
                u = union(fn)
                v = classify(u)
                wv[v] += 1
                if v == RESOLVED and u.episode is not None \
                        and 1900 <= u.episode <= 2100:
                    wyear += 1
            wn = float(len(wnames))
            waccounted = 100.0 * (wv[RESOLVED] + wv[ARBITRATE]
                                  + wv[EPISODE_LESS]) / wn
            print("")
            print("  " + "=" * 68)
            print("  WESTERN RELEASE NAMES (%d) -- a separate population" % len(wnames))
            print("  " + "=" * 68)
            print("    resolved         %6d  %5.1f%%" % (wv[RESOLVED], 100 * wv[RESOLVED] / wn))
            print("    to arbitration   %6d  %5.1f%%" % (wv[ARBITRATE], 100 * wv[ARBITRATE] / wn))
            print("    episode-less     %6d  %5.1f%%" % (wv[EPISODE_LESS], 100 * wv[EPISODE_LESS] / wn))
            print("    🚨 missed         %6d  %5.1f%%" % (wv[MISSED], 100 * wv[MISSED] / wn))
            print("    ⭐ ACCOUNTED FOR  %6d  %5.1f%%"
                  % (wv[RESOLVED] + wv[ARBITRATE] + wv[EPISODE_LESS], waccounted))
            print("")
            print("    🚨 'episodes' in the year range 1900-2100: %d  (%.1f%% of resolved)"
                  % (wyear, 100.0 * wyear / max(1, wv[RESOLVED])))
            print("       ^ a release year reported as an episode is a Rule 2")
            print("         violation, not a coverage shortfall. Watch this row.")

    # ---- the gate ------------------------------------------------------
    accounted = pct(verdicts[RESOLVED] + verdicts[ARBITRATE]
                    + verdicts[EPISODE_LESS])
    path = repo_root() / BASELINE

    if args.baseline:
        write_json(path, {
            "recorded": time.strftime("%Y-%m-%d %H:%M:%S"),
            "sample": n, "all": bool(args.all), "seed": args.seed,
            "accounted_pct": round(accounted, 3),
            "resolved_pct": round(pct(verdicts[RESOLVED]), 3),
            "missed_pct": round(pct(verdicts[MISSED]), 3),
            "note": "Coverage must not regress. A film is NOT a parser "
                    "failure -- see spec/09-corpus-strategy.md.",
        })
        print("")
        print("  baseline recorded: %s  (accounted %.2f%%)" % (path.name, accounted))
        return 0

    if path.is_file():
        from ..paths import read_json
        base = read_json(path)
        floor = base.get("accounted_pct", 0.0)
        print("")
        print("  baseline %.2f%% (recorded %s)  ->  now %.2f%%"
              % (floor, base.get("recorded", "?"), accounted))
        # A sampled run has sampling noise; allow a small band, and say so.
        tolerance = 0.0 if args.all and base.get("all") else 1.0
        if accounted + tolerance < floor:
            print("  ❌ REGRESSION: coverage fell by %.2f points"
                  % (floor - accounted))
            return 1
        print("  ✅ no regression")
    else:
        print("")
        print("  no baseline yet -- record one with --baseline")

    return 0
