# -*- coding: utf-8 -*-
"""
RUNBOOK step A3b — grade the kana phonetic bridge.

    python -m tsubasa.dev kanagate            sampled, seconds
    python -m tsubasa.dev kanagate --all      every kana-only title

⭐ The claim, from `CORPUS-OPPORTUNITIES.md` §3.2 (probe `probe_opp4_kana.py`):

    strict equality, the old metric          22.7%
    rank-1 across the whole 11k pool         80.6%
    rank <= 5                                95.2%
    rank-1 inside a five-show folder         99.1%
    300 fabricated kana: top-1 max           0.83   -> accept at 0.85

⚠ The FOLDER number is the one the product lives on. A user's folder holds a
handful of shows, not eleven thousand, and the whole-pool figure exists to
show what the bridge can do without any other signal at all.

🔒 Sealed excluded. ⛔ Nothing is written; this only measures.
"""
import io
import json
import random
import sys
import time

from ..naming import kana as K
from ..paths import corpus_root, load_config

SAMPLE = 500
SEED = 20260908
FABRICATED = 300

# Enough kana to build strings that look real and are not.
_SYLLABLES = (u"アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホ"
              u"マミムメモヤユヨラリルレロワンガギグゲゴザジズゼゾダデドバビ"
              u"ブベボパピプペポ")


def _fabricate(rng, count):
    out = []
    while len(out) < count:
        n = rng.randint(4, 12)
        word = u"".join(rng.choice(_SYLLABLES) for _ in range(n))
        if rng.random() < 0.4:
            word += u"ー"
        out.append(word)
    return out


def main(argv):
    import argparse

    parser = argparse.ArgumentParser(prog="python -m tsubasa.dev kanagate")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("-n", type=int, default=SAMPLE)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args(argv)

    cfg = load_config()
    root = corpus_root(cfg)
    titles_path = root / "naming" / "titles.json"
    if not titles_path.is_file():
        sys.stderr.write("no answer key at %s\n" % titles_path)
        return 2

    from . import corpus as C
    try:
        data = C.load_manifest(cfg)
        sealed = set()
        for scope in data.get("scopes", {}).values():
            for show in scope.get("sealed", []):
                sealed.add(C.split_key(show))
    except Exception:                            # noqa: BLE001
        sealed = set()

    with io.open(str(titles_path), encoding="utf-8") as fh:
        rows = json.load(fh)

    pool, queries = [], []
    for row in rows:
        romaji, japanese = row.get("romaji"), row.get("japanese")
        if not romaji or C.split_key(romaji) in sealed:
            continue
        pool.append((row["entry"], romaji))
        if japanese and K.is_kana_only(japanese):
            queries.append((row["entry"], japanese, romaji))

    started = time.time()
    index = K.Index(pool)
    rng = random.Random(args.seed)
    if not args.all and len(queries) > args.n:
        queries = rng.sample(queries, args.n)

    strict = r1 = r5 = folder1 = accepted = accepted_right = 0
    wrong_examples = []
    keys = [e for e, _t in pool]
    for entry, japanese, romaji in queries:
        # strict equality -- the metric the ranking replaced
        if K.to_romaji(japanese).replace(" ", "").lower() == \
                romaji.replace(" ", "").lower():
            strict += 1

        scored = index.rank(japanese, limit=5)
        ranked = [e for _s, e in scored]
        if ranked[:1] == [entry]:
            r1 += 1
        if entry in ranked:
            r5 += 1

        # a five-show folder: the true show plus four random others
        others = rng.sample(keys, 5)
        restrict = [entry] + [k for k in others if k != entry][:4]
        folder = index.rank(japanese, restrict=restrict, limit=1)
        if folder and folder[0][1] == entry:
            folder1 += 1

        hit = index.best(japanese)
        if hit is not None:
            accepted += 1
            if hit[0] == entry:
                accepted_right += 1
            elif len(wrong_examples) < 5:
                title = dict(pool).get(hit[0], "?")
                wrong_examples.append((japanese, romaji, title, hit[1]))

    fab = _fabricate(rng, FABRICATED)
    fab_scores = []
    fab_accepted = 0
    for word in fab:
        scored = index.rank(word, limit=1)
        fab_scores.append(scored[0][0] if scored else 0.0)
        if index.best(word) is not None:
            fab_accepted += 1
    fab_scores.sort()

    n = len(queries)
    elapsed = time.time() - started

    def pct(part):
        return 100.0 * part / n if n else 0.0

    print("")
    print("  candidate pool (non-sealed romaji titles) %s" % "{:,}".format(len(pool)))
    print("  kana-only queries                         %s%s"
          % ("{:,}".format(n), "" if args.all else "  (sampled; --all for every one)"))
    print("")
    print("  %-38s %6.1f%%   (probe: 22.7%%)" % ("strict equality, the old metric", pct(strict)))
    print("  %-38s %6.1f%%   (probe: 80.6%%)" % ("rank-1 across the whole pool", pct(r1)))
    print("  %-38s %6.1f%%   (probe: 95.2%%)" % ("rank <= 5", pct(r5)))
    print("  ⭐%-37s %6.1f%%   (probe: 99.1%%)" % ("rank-1 in a five-show folder", pct(folder1)))
    print("")
    print("  accepted at >= %.2f with a %.2f margin    %s of %s   %s right"
          % (K.ACCEPT, K.MARGIN, "{:,}".format(accepted), "{:,}".format(n),
             "{:,}".format(accepted_right)))
    print("  🚨 fabricated kana accepted               %d of %d   "
          "(top-1 median %.2f, p95 %.2f, max %.2f)"
          % (fab_accepted, FABRICATED,
             fab_scores[len(fab_scores) // 2],
             fab_scores[int(len(fab_scores) * 0.95)], fab_scores[-1]))
    print("")
    for japanese, romaji, got, score in wrong_examples:
        print("  wrong: %-18s want %-26s got %-26s %.2f"
              % (japanese[:18], romaji[:26], got[:26], score))
    print("")
    print("  %.1fs" % elapsed)

    ok = pct(r1) >= 75.0 and fab_accepted == 0
    print("  gate: rank-1 %.1f%% (>= 75%% required) and %d fabricated accepted "
          "(0 required) -> %s" % (pct(r1), fab_accepted, "PASS" if ok else "FAIL"))
    return 0 if ok else 1
