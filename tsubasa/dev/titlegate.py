# -*- coding: utf-8 -*-
"""
The TITLE gate. RUNBOOK step A2b+.

    python -m tsubasa.dev titlegate             # sample, report
    python -m tsubasa.dev titlegate --all       # every catalogue row
    python -m tsubasa.dev titlegate --baseline  # record the floor

⭐ WHY THIS EXISTS, AND IT IS A DEFECT THE PARSER GATE STRUCTURALLY CANNOT SEE.

`A2-fix` moved *series keys still carrying an `E##` token* from **9.1% to
0.00%**, while the headline parser number barely moved (97.38 -> 96.78). That
is not a contradiction. `parsergate` scores the UNION of three parsers, and
anitopy was already rescuing those episodes -- so the episode came out right
and **our own TITLE stayed wrong on every one of them.** Series identity
consumes the title, so the parser gate was green over a defect that broke
pairing (`RUNBOOK.md` §A2-fix, `09-corpus-strategy.md` §The three gates).

🚨 THE HEADLINE IS NOT "DO THE KEYS AGREE", AND PROBE A2b+/1 IS WHY.

The obvious metric -- *the share of same-show files whose series key differs* --
was measured before this gate was written, and it does not mean what it says:

| | |
| --- | --- |
| entries carrying **more than one script** | **21.6%** |
| files off the modal key within (entry, script) | **19.25%** |

⛔ Grouping by entry alone charges the parser for the corpus's own shape:
`Heroic Age` and `ヒロイック・エイジ` are one jimaku entry and **correctly** key
differently -- that is what the kana bridge (A3b) and the alias table (A7) are
for. And grouping by (entry, script) does not fix it either, because
`Space Ironmen Kyodyne` and `Uchuu Tetsujin Kyoudain` are both Latin, both the
same entry, and both **right**. Reading the disagreements showed the 19.25% is
mostly release-name typos (`Lirycal` / `Lyrical`), entries holding several
distinct works, and English-against-romaji.

⚠ AND AGREEMENT IS TRIVIALLY SATISFIABLE ANYWAY. A parser returning `""` for
every name is **100% self-consistent**. Any metric shaped as *"do the keys
agree"* has to count empty keys as failures out loud, or it is the same class
as `0 broken of 0`.

⭐ SO THE HEADLINE IS SELF-REFERENTIAL, AND THAT IS WHAT MAKES IT UNGAMEABLE:

    CONTAMINATED  =  the parser extracted an episode number,
                     and that number is STILL IN THE TITLE it returned.

The parser is being held to its own answer. No exception list is needed, and
`Gundam 0080`, `Steins;Gate 0`, `86` and `Mob Psycho 100` cannot trip it --
🚨 which matters, because `LEDGER.md` records that *"One Piece really does
reach episode 1121, so four digits is not the tell."*

Three numbers, and only the first is a gate:

    CONTAMINATED  🚨 the real failure -- the episode survived in the title
    EMPTY         ⚠ no title at all. An empty key pairs with EVERY video
                    sharing an episode number (`08-probes.md` §C: 4,133 files)
    SPLIT         a trend line, with its confounds named. NOT a defect count

⭐ Rule 4 applied: this reads FILENAMES ONLY. Not one file is opened.
🔒 The sealed slice is excluded by split key, on the show name.
"""
import io
import json
import os
import random
import re
import sys
import time
from collections import Counter, defaultdict

from ..naming.episode import parse_ours
from ..naming.normalize import normalize, script_of
from ..paths import corpus_root, load_config, repo_root, write_json

BASELINE = "title-gate-baseline.json"
SAMPLE_DEFAULT = 40000

CLEAN = "clean"
CONTAMINATED = "contaminated"
EMPTY = "empty"

# ⚠ A FULL-WIDTH FOLD WAS WRITTEN HERE AND DELETED — IT WAS DEAD CODE, and a
# mutation removing it SURVIVED, which is how that was found rather than
# assumed. Verified directly: Python's `re` `\d` on a `str` pattern matches
# **Unicode decimal digits**, so `第０４話` matches, and `int(u"０４")` returns
# **4**. Both halves already handle full width natively.
#
# ⭐ The CHECK stays, though, and it is not redundant: it is what catches
# anyone "tightening" `\d` to `[0-9]`, which would silently stop matching
# **11.9% of corpus filenames** (`normalize.py` — that share carries a
# full-width character). ⛔ The guard was dead; the check is not.

# 🚨 AN EPISODE **MARKER**, NOT A BARE NUMBER -- AND THE FIRST VERSION OF THIS
# GATE GOT THAT WRONG, IN THE EXACT SHAPE THE LEDGER WARNS ABOUT.
#
# It accused any title whose digits equalled the extracted episode. Read on the
# first run, 2 of the first 5 accusations were FALSE:
#
#     ５→９～私に恋したお坊さん～ ＃05   ep=5   the show IS CALLED `5→9`
#     ラスト・コップ２nd ＃02          ep=2   the show IS CALLED `Last Cop 2nd`
#
# ⚠ `LEDGER.md` records the same trap from the other direction -- *"One Piece
# really does reach episode 1121, so four digits is not the tell"* -- and a
# number-only test walks into it whichever way you point it.
#
# ⭐ The real defect always carries the MARKER, because that is what the parser
# failed to cut: `S01E124`, `第124回`, `第06話`. So the test is *"is an episode
# PATTERN still in the title"*, which no ordinary show name contains.
_MARKERS = [
    re.compile(u"(?i)\\bs\\d{1,3}\\s*e(\\d{1,4})\\b"),        # S01E124
    re.compile(u"(?i)(?:^|[^a-z0-9])e(?:p|pisode)?\\s*(\\d{1,4})\\b"),
    # ⚠ MEASURED UNREACHABLE ON REAL DATA — 0 hits over the full catalogue,
    # because the parser already truncates the `＃05` shape correctly every
    # time. ⛔ It is KEPT anyway, on the same footing as the container reader's
    # unreachable position guards: it costs nothing, the shape plainly exists
    # in filenames, and the day someone changes how `＃` is stripped is the day
    # the invariant stops being free. **What must not happen is someone citing
    # the green suite as evidence that it can go.**
    re.compile(u"[#＃]\\s*(\\d{1,4})"),                        # #05 / ＃05
    re.compile(u"第\\s*(\\d{1,4})\\s*[話回]"),                  # 第124回
]


def episode_survives_in_title(parsed):
    """Did an episode MARKER carrying the extracted number survive the parse?

    ⭐ TWO CONDITIONS, AND BOTH ARE LOAD-BEARING:

      1. an episode **pattern** is still in the title, and
      2. its number is the one the parser itself called the episode.

    (1) alone would accuse a show genuinely named `第1話`; (2) alone accuses
    `5→9` and `Last Cop 2nd`, which is what the first version did. Together
    they are self-referential -- **the parser is held to its own answer** -- and
    they cannot fire on `Gundam 0080`, `Steins;Gate 0`, `86` or
    `Mob Psycho 100`, none of which carries a marker at all.

    ⚠ The number is compared as an INTEGER. `第06話` and episode 6 are the same
    number, and a string test would miss every zero-padded name in the corpus.
    """
    if parsed.episode is None or not parsed.title:
        return False
    wanted = {parsed.episode}
    if parsed.episode_end is not None:
        wanted.add(parsed.episode_end)
    for pattern in _MARKERS:
        for run in pattern.findall(parsed.title):
            try:
                if int(run) in wanted:
                    return True
            except (TypeError, ValueError):               # pragma: no cover
                continue
    return False


def classify(name):
    """-> (verdict, key, parsed). Filenames only; nothing is opened."""
    parsed = parse_ours(name)
    key = normalize(parsed.title or u"").key
    if not key:
        return EMPTY, key, parsed
    if episode_survives_in_title(parsed):
        return CONTAMINATED, key, parsed
    return CLEAN, key, parsed


def iter_rows(cfg, root, sample=None, seed=20260908):
    """Catalogue rows with the sealed slice removed.

    🔒 Excluded by `split_key` on the SHOW name -- the same folding the corpus
    split itself uses. ⛔ *"Not in the keep list"* is NOT the same as *"sealed"*:
    the catalogue lists every file the site holds, while `naming/` has a
    directory only for shows actually downloaded, and excluding by keep-list
    threw away **64,731 rows** at A2c (`LEDGER.md` §Harness).
    """
    from . import corpus as C

    path = root / "naming" / "catalog.jsonl"
    if not path.is_file():
        raise IOError("no catalogue at %s" % path)

    manifest = C.load_manifest(cfg)
    sealed = {C.split_key(show)
              for scope in manifest.get("scopes", {}).values()
              for show in scope.get("sealed", [])}

    rows, skipped = [], 0
    with io.open(str(path), encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if C.split_key(row.get("show") or u"") in sealed:
                skipped += 1
                continue
            rows.append(row)

    if sample and sample < len(rows):
        # ⚠ SAMPLED, NOT PREFIXED. `catalog.jsonl` is ordered by jimaku entry
        # id, so "the first N" is the OLDEST shows, not a cross-section --
        # measured at A2c, where a prefix read film pollution as 6.4% against a
        # strided 39.9% (`LEDGER.md` §Harness).
        rows = random.Random(seed).sample(rows, sample)
    return rows, skipped, len(sealed)


def measure(rows):
    """-> dict of counts. One pass over the names."""
    verdicts = Counter()
    groups = defaultdict(list)
    examples = {CONTAMINATED: [], EMPTY: []}

    for row in rows:
        name = row.get("name") or u""
        verdict, key, parsed = classify(name)
        verdicts[verdict] += 1
        groups[(row.get("entry"), script_of(name))].append(key)
        if len(examples.get(verdict, [])) < 8 and verdict != CLEAN:
            examples[verdict].append(
                (name, parsed.title, parsed.episode, key))

    scored = files = off_modal = 0
    spread = Counter()
    for keys in groups.values():
        if len(keys) < 2:
            continue
        counts = Counter(keys)
        scored += 1
        files += len(keys)
        off_modal += len(keys) - counts.most_common(1)[0][1]
        spread[len(counts)] += 1

    return {"rows": len(rows), "verdicts": dict(verdicts),
            "groups": scored, "groupedFiles": files, "offModal": off_modal,
            "spread": dict(spread), "examples": examples}


def _rate(part, whole):
    return round(100.0 * part / whole, 2) if whole else 0.0


def main(argv):
    import argparse

    parser = argparse.ArgumentParser(prog="python -m tsubasa.dev titlegate")
    parser.add_argument("--all", action="store_true",
                        help="every catalogue row, not a sample")
    parser.add_argument("--baseline", action="store_true",
                        help="record the measured floor")
    parser.add_argument("-n", type=int, default=SAMPLE_DEFAULT)
    args = parser.parse_args(argv)

    cfg = load_config()
    root = corpus_root(cfg)
    if not root.is_dir():
        sys.stderr.write("corpus not found at %s\n" % root)
        return 2

    started = time.time()
    try:
        rows, skipped, sealed_shows = iter_rows(
            cfg, root, sample=None if args.all else args.n)
    except IOError as exc:
        sys.stderr.write("%s\n" % exc)
        return 2
    result = measure(rows)
    n = result["rows"]

    contaminated = result["verdicts"].get(CONTAMINATED, 0)
    empty = result["verdicts"].get(EMPTY, 0)

    print("")
    print("  population    %s rows%s · %s skipped as sealed (%d shows)"
          % ("{:,}".format(n), "" if args.all else " (SAMPLED)",
             "{:,}".format(skipped), sealed_shows))
    # ⭐ The population is printed beside the number, always. `LEDGER.md`: a
    # gate cannot measure a population it never reads, and the parser gate's
    # 97.4% was wrong about its SCOPE rather than about its sample.
    print("")
    print("  🚨 CONTAMINATED  %8s  %6.2f%%   the episode the parser extracted"
          % ("{:,}".format(contaminated), _rate(contaminated, n)))
    print("                                     is STILL IN the title it "
          "returned")
    print("  ⚠ EMPTY         %8s  %6.2f%%   no title at all -- an empty key"
          % ("{:,}".format(empty), _rate(empty, n)))
    print("                                     pairs with EVERY video sharing"
          " an episode")
    print("  CLEAN           %8s  %6.2f%%"
          % ("{:,}".format(result["verdicts"].get(CLEAN, 0)),
             _rate(result["verdicts"].get(CLEAN, 0), n)))

    for kind, label in ((CONTAMINATED, u"contaminated"), (EMPTY, u"empty")):
        rows_ex = result["examples"].get(kind) or []
        if not rows_ex:
            continue
        print("")
        print("  e.g. %s" % label)
        for name, title, episode, key in rows_ex[:5]:
            print("    ep=%-5s %-30s <- %s"
                  % (episode, (key or u"-")[:30], name[:52]))

    print("")
    print("  SPLIT -- files off the modal key within (entry, script)")
    print("    %s of %s grouped files   %.2f%%   over %s groups"
          % ("{:,}".format(result["offModal"]),
             "{:,}".format(result["groupedFiles"]),
             _rate(result["offModal"], result["groupedFiles"]),
             "{:,}".format(result["groups"])))
    print("    ⚠ A TREND LINE, NOT A DEFECT COUNT, and the confounds are")
    print("      named rather than subtracted: 21.6% of entries carry more")
    print("      than one script; `Space Ironmen Kyodyne` and `Uchuu Tetsujin")
    print("      Kyoudain` are both Latin, both this entry, and both right;")
    print("      and release-name typos (`Lirycal`/`Lyrical`) are real")
    print("      differences. ⛔ Do not tune against this number.")

    payload = {
        "//": ("RUNBOOK A2b+ -- the TITLE gate. ⭐ CONTAMINATED is the gate: "
               "the parser extracted an episode number and left it in the "
               "title, which is the defect `parsergate` structurally cannot "
               "see because it scores the UNION and another parser rescues "
               "the episode. Re-record with: python -m tsubasa.dev titlegate "
               "--all --baseline. ⚠ A CEILING, never a target -- the suite "
               "fails when a number RISES, and a fall is re-recorded "
               "deliberately. ⛔ SPLIT is a trend line and is not gated."),
        "recorded": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "rows": n,
        "sampled": not args.all,
        "contaminatedPct": _rate(contaminated, n),
        "emptyPct": _rate(empty, n),
        "offModalPct": _rate(result["offModal"], result["groupedFiles"]),
        "groups": result["groups"],
    }

    target = repo_root() / BASELINE
    if args.baseline:
        if not args.all:
            sys.stderr.write(
                "\n⛔ refusing to record a baseline from a SAMPLE. The parser "
                "gate's 97.38% was an 800-file sample recorded as a floor and "
                "was never comparable to anything (`LEDGER.md` §Harness). "
                "Use --all --baseline.\n")
            return 2
        write_json(target, payload)
        print("")
        print("  wrote %s" % target.name)
    elif target.is_file():
        with io.open(str(target), encoding="utf-8") as fh:
            old = json.load(fh)
        print("")
        for field in ("contaminatedPct", "emptyPct"):
            was, now = old.get(field), payload[field]
            if was is None:
                continue
            flag = "OK " if now <= was + 0.05 else "⛔ REGRESSED"
            print("  %-4s %-18s baseline %.2f%%  now %.2f%%"
                  % (flag, field, was, now))
        if not args.all and old.get("sampled") is False:
            print("  ⚠ this run is a SAMPLE and the baseline is a FULL pass. "
                  "A gap of a few hundredths is the sample, not a regression.")

    print("")
    print("  %.1fs" % (time.time() - started))
    return 0
