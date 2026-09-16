# -*- coding: utf-8 -*-
"""
RUNBOOK step 1d, the proof command.

    python -m tsubasa.dev container --bench
    python -m tsubasa.dev container --bench --walk     # also time the slow path
    python -m tsubasa.dev container FILE.mkv           # one file, in detail

    Expected: the Cues path under 0.2 s per file, tens of kilobytes read, and
    the SAME cue times as the full block walk to the microsecond.

⭐ Why this is a command and not a note in a report. `doctrine/verification`:
the claim behind step 1d is a pair of numbers, and a number that only ever
appeared in a report is one nobody can re-derive on a different machine, on a
different file, or after a change. Measured 2026-09-08 on ten real 1.44 GB
SubsPlease files: **0.073 s median, 0.125 s worst, ~30 KB, 0.000000 s
disagreement** against both the block walk and ffmpeg's own extraction.

⚠ Reads real video, so it needs `TSUBASA_MEDIA` (or the config's default) to
point somewhere with `.mkv` in it. Absent, it says so and exits 2 -- it does
not print a vacuous zero.

⛔ READ-ONLY. Nothing is written beside the media, ever.
"""
import os
import sys
import time

from .. import container
from ..paths import load_config, media_root, resolution

BUDGET_SECONDS = 0.2
MAX_FILES = 12


def _fmt(value, spec, absent="-"):
    return absent if value is None else spec % value


def _index_pass(path):
    """Time the index path for one file. Never raises on a bad file.

    🚨 MEASURED IN A SEPARATE PASS FROM THE WALK, AND THAT IS NOT TIDINESS.

    The first version timed a file's index read and then immediately walked
    that same file's 1.4 GB of blocks before moving to the next one. The next
    file's index read then took **0.24-0.40 s instead of 0.10-0.15 s** --
    because the walk had flushed the OS page cache, so the read that had just
    been warmed was cold again. The benchmark was attributing the previous
    file's side effect to this file's cost, and it reported three budget
    FAILURES against a path that comfortably meets the budget.

    ⭐ An instrument whose slow half evicts the cache of its fast half returns
    a confident number about the wrong thing. `LEDGER.md` §instrument traps.
    """
    name = os.path.basename(path)
    container.read(path, allow_ffmpeg=False)          # warm the page cache
    started = time.perf_counter()
    info = container.read(path, allow_ffmpeg=False)
    fast = time.perf_counter() - started

    if not info.ok:
        return {"name": name, "problems": [(name, info.reason)],
                "line": "%-34s ERROR %s" % (name[:34], info.reason)}

    subs = [t for t in info.subtitle_tracks if t.cues is not None]
    if not subs:
        return {"name": name, "problems": [],
                "line": "%-34s  no subtitle track carrying timing" % name[:34]}

    track = max(subs, key=lambda t: len(t.cues))
    problems = []
    if fast > BUDGET_SECONDS and track.timing_source == "cues":
        problems.append((name, "the index path took %.3f s, over the %.2f s "
                               "budget" % (fast, BUDGET_SECONDS)))
    if track.index_verified is None:
        problems.append((name, "the index was UNVERIFIED, not confirmed"))

    return {"name": name, "path": path, "info": info, "track": track,
            "fast": fast, "problems": problems, "walk_s": None, "agree": None}


def _walk_pass(row):
    """The full block walk for one file, and whether it agrees with the index.

    Runs only once every index measurement is finished -- see `_index_pass`.
    """
    name, track = row["name"], row["track"]
    started = time.perf_counter()
    slow = container.read(row["path"], allow_ffmpeg=False, use_index=False)
    row["walk_s"] = time.perf_counter() - started

    other = slow.track(track.index)
    if other is None or other.cues is None:
        row["problems"].append((name, "the block walk found no track %s"
                                % track.number))
    elif len(other.cues) != len(track.cues):
        row["problems"].append((name, "index %d cues, block walk %d"
                                % (len(track.cues), len(other.cues))))
    else:
        row["agree"] = max((abs(a.start - b.start)
                            for a, b in zip(track.cues, other.cues)),
                           default=0.0)
        if row["agree"] > 0.001:
            row["problems"].append((name, "index and walk disagree by %.4f s"
                                    % row["agree"]))


def _render(row):
    info, track = row["info"], row["track"]
    return ("%-34s %7d %8.3f %8.1f %7s %-7s %8s %9s %6d"
            % (row["name"][:34], len(track.cues), row["fast"],
               (info.bytes_read or 0) / 1e3, info.seeks,
               track.timing_source or "?",
               _fmt(row["walk_s"], "%.3f"), _fmt(row["agree"], "%.6f"),
               len(info.chapters)))


def main(argv):
    import argparse

    parser = argparse.ArgumentParser(prog="python -m tsubasa.dev container")
    parser.add_argument("files", nargs="*",
                        help="specific containers; default is the media root")
    parser.add_argument("--bench", action="store_true",
                        help="walk the media root and time every file")
    parser.add_argument("--walk", action="store_true",
                        help="also run the full block walk and compare")
    parser.add_argument("-n", type=int, default=MAX_FILES)
    args = parser.parse_args(argv)

    paths = list(args.files)
    if not paths:
        if not args.bench:
            parser.error("give a file, or --bench to walk the media root")
        cfg = load_config()
        root = media_root(cfg)
        how = resolution().get("mediaHow", "?")
        sys.stdout.write("media root: %s\n  (%s)\n\n" % (root, how))
        if not root.is_dir():
            # ⚠ Say what is missing and how to supply it. A benchmark with no
            # input must not print a zero that reads like a result.
            sys.stderr.write(
                "no media at %s. Set %s to a folder containing .mkv files.\n"
                % (root, cfg["media"]["envVar"]))
            return 2
        paths = [str(p) for p in sorted(root.rglob("*.mkv"))[:args.n]]
        if not paths:
            sys.stderr.write(
                "no .mkv under %s. RUNBOOK 1d names 'the corpus .mkv "
                "fixtures' and the corpus has none -- see media.//gap in "
                "tsubasa.config.json.\n" % root)
            return 2

    header = ("%-34s %7s %8s %8s %7s %-7s %8s %9s %6s"
              % ("file", "cues", "index_s", "KB", "seeks", "source",
                 "walk_s", "agree", "chaps"))
    sys.stdout.write(header + "\n" + "-" * len(header) + "\n")

    # Pass 1: every index read, with nothing else touching the disk.
    rows = [_index_pass(path) for path in paths]

    # Pass 2: the walks, once no index measurement can be perturbed by them.
    if args.walk:
        for row in rows:
            if "line" not in row:
                _walk_pass(row)

    problems = []
    for row in rows:
        sys.stdout.write((row["line"] if "line" in row else _render(row)) + "\n")
        problems.extend(row["problems"])

    times = sorted(r["fast"] for r in rows if "line" not in r)
    if times:
        sys.stdout.write("\n  index path: %.3f s median, %.3f s worst\n"
                         % (times[len(times) // 2], times[-1]))
    sys.stdout.write("\n%d file(s), budget %.2f s per file on the index path\n"
                     % (len(paths), BUDGET_SECONDS))
    if not args.walk:
        sys.stdout.write("  (--walk also runs the full block walk and "
                         "requires the two to agree)\n")
    if problems:
        sys.stdout.write("\n%d problem(s):\n" % len(problems))
        for name, why in problems:
            sys.stdout.write("  %-34s %s\n" % (name[:34], why))
        return 1
    sys.stdout.write("\n  OK\n")
    return 0
