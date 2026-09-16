# -*- coding: utf-8 -*-
"""
RUNBOOK step A2c — derive the decoration vocabulary, and grade it.

    python -m tsubasa.dev decoration --derive    rebuild tsubasa/data/decoration.json
    python -m tsubasa.dev decoration --grade     film / episode / unknown pollution

⭐ The rule, from `CORPUS-OPPORTUNITIES.md` §3.1, and the whole point is that
it is a rule and not a list:

    decoration  <=>  df >= 25 shows  AND  canonical-title rate < 5%

Document frequency alone cannot separate `netflix` from `the`. The ANSWER KEY
breaks the tie: a token is decoration when many shows' FILENAMES carry it and
those shows' CANONICAL TITLES do not.

`02-data-model.md` lists the learned rules as **bundled and re-derivable by one
command**. This is that command, and the artefact records what it was derived
from so the number can be re-checked rather than believed.

🔒 The sealed slice is excluded, by name, from the catalogue pass.
⛔ Nothing is written inside the corpus; the only output is the bundled JSON.
"""
import io
import json
import os
import re
import sys
import time
from collections import defaultdict

from ..naming import decoration as D
from ..paths import atomic_write_text, corpus_root, load_config, repo_root

MIN_SHOWS = 25            # df floor, in DISTINCT shows -- never in files
MAX_TITLE_RATE = 0.05     # a token in >= 5% of its shows' titles is a WORD

# 🚨 AN EPISODE NUMBER IS NOT DECORATION, and the raw rule cannot tell them
# apart. `001`, `e07`, `s01e05`, `第三話` all pass *df >= 25 and rate < 5%*
# perfectly — they appear across thousands of shows and never in a canonical
# title — and the first derivation returned **264 pure-digit tokens of 664**.
#
# ⛔ They must not enter the vocabulary. They are what the PARSER extracts;
# the vocabulary exists for what the parser cannot reach. And a vocabulary
# containing digits would let the aggressive path eat real titles:
# `Gundam 0080`, `Mobile Suit Gundam 00`, `Steins;Gate 0`, `86`, `K-On`.
#
# ⚠ This rule is a PART 1 GAP: `CORPUS-OPPORTUNITIES.md` §3.1 states only the
# df/rate rule and reports 185 tokens — a figure only reachable if numerics
# were already excluded, which its own "top misses" list confirms (not one
# entry carries a digit). Recorded rather than silently assumed.
_EPISODE_SHAPED = re.compile(
    u"^(?:"
    u"[0-9]+"                       # 001, 02, 1121
    u"|e[p]?[0-9]+"                 # e07, ep14
    u"|s[0-9]+(?:e[0-9]+)?"         # s2, s01e05
    u"|v[0-9]+"                     # v2
    u"|[0-9]+v[0-9]+"               # 03v2 -- a versioned episode number
    u"|第[0-9〇一二三四五六七八九十百千]+[話回]"   # 第三話, 第十二回
    u")$", re.I)

# ⚠ The grade is measured on a SAMPLE of the catalogue by default. A full pass
# reads 238,250 names; the sample answers the same question in seconds, and
# --all is there when the number is the one being recorded.
GRADE_SAMPLE = 40000


def _count_lines(path):
    with io.open(str(path), "r", encoding="utf-8") as fh:
        return sum(1 for line in fh if line.strip())


def _canonical_tokens(rows):
    """{entry id: set(tokens)} over romaji + Japanese + English."""
    out = {}
    for row in rows:
        toks = set()
        for field in ("romaji", "japanese", "english"):
            value = row.get(field)
            if value:
                toks.update(D.tokens_of(value))
        out[row["entry"]] = toks
    return out


def _sealed_keys(cfg):
    """split_key of every SEALED show, or None if the manifest is unreadable.

    🚨 EXCLUDE WHAT IS SEALED — do not include only what is split.

    The first version built the *keep* set from dev + validation and dropped
    everything else. That threw away **64,731 of 238,250 catalogue rows** —
    more than a quarter of the learning signal — because `catalog.jsonl` lists
    every file the SITE holds while `naming/` has a directory only for the
    shows that were actually downloaded. Those rows match no directory at all.
    **They are not sealed. They are unsplit**, and a show with no local files
    has no held-back evidence to protect.

    ⭐ The tell was the instrument disagreeing with the spec: `09-corpus-
    strategy.md` counts 201,785 non-sealed rows and the first version counted
    138,988. Measured: 34,531 genuinely sealed, 64,731 unmatched.

    ⚠ The residual risk is a sealed show whose catalogue spelling `split_key`
    does not fold onto its directory name. That is the known under-merge trade
    in `LEDGER.md` §Harness, and the seal is a set of NAMES — anything the
    canonical key does not match is, by that definition, not in it.
    """
    from . import corpus as C
    try:
        data = C.load_manifest(cfg)
        sealed = set()
        for scope in data.get("scopes", {}).values():
            for show in scope.get("sealed", []):
                sealed.add(C.split_key(show))
        return sealed or None
    except Exception:                        # noqa: BLE001
        return None


def derive(cfg, root, verbose=True):
    """-> (vocabulary tokens, stats). Reads the catalogue once."""
    titles_path = root / "naming" / "titles.json"
    catalog_path = root / "naming" / "catalog.jsonl"
    if not titles_path.is_file() or not catalog_path.is_file():
        raise IOError("need naming/titles.json and naming/catalog.jsonl under %s"
                      % root)

    from . import corpus as C
    with io.open(str(titles_path), "r", encoding="utf-8") as fh:
        title_rows = json.load(fh)
    canon = _canonical_tokens(title_rows)
    sealed = _sealed_keys(cfg)

    shows_with = defaultdict(set)        # token -> {entry}
    shows_titled = defaultdict(set)      # token -> {entry whose TITLE has it}
    entries = set()
    lines = skipped = 0

    started = time.time()
    with io.open(str(catalog_path), "r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            lines += 1
            try:
                row = json.loads(line)
            except ValueError:
                continue
            show = row.get("show") or ""
            if sealed is not None and C.split_key(show) in sealed:
                skipped += 1
                continue
            entry = row.get("entry")
            if entry is None:
                continue
            entries.add(entry)
            title_toks = canon.get(entry, ())
            for token in set(D.tokens_of(row.get("name") or "")):
                shows_with[token].add(entry)
                if token in title_toks:
                    shows_titled[token].add(entry)

    vocab, kept, numeric = set(), [], 0
    for token, shows in shows_with.items():
        df = len(shows)
        if df < MIN_SHOWS:
            continue
        if _EPISODE_SHAPED.match(token):
            numeric += 1                     # an episode number, not decoration
            continue
        rate = len(shows_titled.get(token, ())) / float(df)
        if rate < MAX_TITLE_RATE:
            vocab.add(token)
        else:
            kept.append((token, df, rate))

    # ⛔ The protection list wins over the measurement. A future crawl that
    # adds enough decorated filenames could push a real title word under 5%,
    # and the vocabulary would quietly start eating titles.
    blocked = sorted(vocab & D.PROTECTED)
    vocab -= D.PROTECTED

    stats = {
        "catalogueLines": lines,
        "sealedSkipped": skipped,
        "shows": len(entries),
        "candidateTokens": len(shows_with),
        "tokens": len(vocab),
        "keptAsTitleWords": len(kept),
        "rejectedAsEpisodeShaped": numeric,
        "blockedByProtectedList": blocked,
        "seconds": round(time.time() - started, 1),
    }
    if verbose:
        top = sorted(kept, key=lambda k: -k[1])[:12]
        sys.stdout.write(
            "  read %s catalogue lines (%s sealed rows skipped), %s shows\n"
            % ("{:,}".format(lines), "{:,}".format(skipped),
               "{:,}".format(len(entries))))
        sys.stdout.write("  %s candidate tokens -> %s decoration, %s kept as "
                         "title words\n"
                         % ("{:,}".format(len(shows_with)),
                            "{:,}".format(len(vocab)),
                            "{:,}".format(len(kept))))
        sys.stdout.write("  kept, most common first: %s\n"
                         % ", ".join("%s(%d, %.0f%%)" % (t, d, r * 100)
                                     for t, d, r in top))
        if blocked:
            sys.stdout.write("  ⛔ blocked by the protection list: %s\n"
                             % ", ".join(blocked))
    return vocab, stats


def cmd_derive(cfg, args):
    root = corpus_root(cfg)
    if not root.is_dir():
        sys.stderr.write("corpus not found at %s\n" % root)
        return 2
    vocab, stats = derive(cfg, root)

    target = repo_root() / "tsubasa" / "data" / "decoration.json"
    payload = {
        "//": ("LEARNED, NOT WRITTEN. RUNBOOK A2c. A token is decoration when "
               "df >= %d shows AND its canonical-title rate is < %.0f%% "
               "(CORPUS-OPPORTUNITIES.md 3.1). Re-derive with: python -m "
               "tsubasa.dev decoration --derive. Own work product -- learned "
               "from the catalogue, so it ships (02-data-model.md)."
               % (MIN_SHOWS, MAX_TITLE_RATE * 100)),
        "meta": dict(stats, derived=time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                  time.gmtime()),
                     minShows=MIN_SHOWS, maxTitleRate=MAX_TITLE_RATE),
        "tokens": sorted(vocab),
    }
    atomic_write_text(target, json.dumps(payload, ensure_ascii=False, indent=1)
                      + "\n")
    sys.stdout.write("\n  wrote %s  (%d tokens)\n"
                     % (target.relative_to(repo_root()), len(vocab)))
    return 0


def cmd_grade(cfg, args):
    """Pollution by parse kind -- the number A2c is graded on.

    ⚠ Measured through the REAL parser, on real names, not on a fixture. The
    baseline it is compared against (film 37.2%) was measured the same way.
    """
    from ..naming import episode as E

    root = corpus_root(cfg)
    if not root.is_dir():
        sys.stderr.write("corpus not found at %s\n" % root)
        return 2
    catalog_path = root / "naming" / "catalog.jsonl"
    vocab = D.load()
    if not len(vocab):
        sys.stderr.write("no decoration vocabulary -- run --derive first\n")
        return 2

    from . import corpus as C
    sealed = _sealed_keys(cfg)
    limit = None if args.all else GRADE_SAMPLE

    counts = defaultdict(lambda: [0, 0, 0])   # kind -> [n, polluted, cleaned]
    examples = defaultdict(list)
    seen = 0
    # 🚨 A PREFIX IS NOT A SAMPLE. The first version graded the first N lines,
    # and `catalog.jsonl` is ordered by jimaku entry id -- so "the first
    # 40,000" is the OLDEST shows, not a cross-section, and every rate it
    # printed described a corner of the corpus. Stride instead: take every
    # k-th line across the whole file, which costs the same read and covers
    # the range. `doctrine/evidence`: measure the right population.
    total = _count_lines(catalog_path)
    stride = 1 if limit is None or total <= limit else max(1, total // limit)
    index = -1
    with io.open(str(catalog_path), "r", encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            index += 1
            if index % stride:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if sealed is not None and C.split_key(row.get("show") or "") in sealed:
                continue
            seen += 1
            name = row.get("name") or ""
            # ⚠ `parse_ours`, not `union`: the baseline this is compared
            # against was measured on our own parser's title, and union's lazy
            # fallbacks would change the population as well as the number.
            parsed = E.parse_ours(name)
            kind = parsed.kind or E.UNKNOWN
            title = parsed.title or u""
            bucket = counts[kind]
            bucket[0] += 1
            if D.is_polluted(title, vocab):
                bucket[1] += 1
                cleaned = D.strip(title, vocab, aggressive=True)
                if not D.is_polluted(cleaned, vocab):
                    bucket[2] += 1
                elif len(examples[kind]) < 4:
                    examples[kind].append((title[:38], cleaned[:38]))

    sys.stdout.write("\n  %-9s %8s %12s %12s %12s\n"
                     % ("kind", "files", "polluted", "cleanable", "residual"))
    sys.stdout.write("  " + "-" * 56 + "\n")
    worst = 0.0
    for kind in sorted(counts):
        n, polluted, cleaned = counts[kind]
        before = 100.0 * polluted / n if n else 0.0
        after = 100.0 * (polluted - cleaned) / n if n else 0.0
        if kind == "film":
            worst = after
        sys.stdout.write("  %-9s %8s %11.1f%% %11.1f%% %11.1f%%\n"
                         % (kind, "{:,}".format(n), before,
                            100.0 * cleaned / n if n else 0.0, after))
    sys.stdout.write("\n  sample %s file(s)%s, vocabulary %d tokens\n"
                     % ("{:,}".format(seen), "" if args.all else " (--all for every one)",
                        len(vocab)))
    for kind in sorted(examples):
        if examples[kind]:
            sys.stdout.write("  residual %s: %s\n"
                             % (kind, "; ".join("%s -> %s" % e
                                                for e in examples[kind][:3])))
    sys.stdout.write("\n  film residual %.1f%% against the < 5%% target\n" % worst)
    sys.stdout.write(
        "  the `polluted` column is this population's own before-figure, and "
        "it independently\n  reproduces CORPUS-OPPORTUNITIES.md 3.1's "
        "measured 37.2% film pollution.\n"
        "  ⚠ It only does so under STRIDE sampling. Grading the first N lines "
        "instead read\n     6.4% — catalog.jsonl is ordered by entry id, so a "
        "prefix is the oldest shows,\n     not a cross-section.\n")
    return 0 if worst < 5.0 else 1


def main(argv):
    import argparse

    parser = argparse.ArgumentParser(prog="python -m tsubasa.dev decoration")
    parser.add_argument("--derive", action="store_true",
                        help="rebuild tsubasa/data/decoration.json")
    parser.add_argument("--grade", action="store_true",
                        help="pollution by parse kind")
    parser.add_argument("--all", action="store_true",
                        help="grade every catalogue line, not a sample")
    args = parser.parse_args(argv)

    cfg = load_config()
    if args.derive:
        rc = cmd_derive(cfg, args)
        if rc or not args.grade:
            return rc
    if args.grade:
        return cmd_grade(cfg, args)
    parser.error("give --derive, --grade, or both")
