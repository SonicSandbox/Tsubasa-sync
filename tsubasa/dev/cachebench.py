# -*- coding: utf-8 -*-
"""
RUNBOOK step 1b, the proof command.

    python -m tsubasa.dev cache --bench

    Expected: 24 files, run twice. The SECOND run is under 1 second with zero
    parsing -- the re-run-nothing-changed target from spec/01-scope.md.

⚠ Uses a THROWAWAY cache directory, never the user's real one. A benchmark
that warms or pollutes the live cache measures itself into a better number on
the next run, and that is how a performance claim becomes untrue quietly.
"""
import random
import shutil
import sys
import tempfile
import time
from pathlib import Path

from .. import formats
from ..cache import Cache, content_key
from ..paths import corpus_root, load_config

N_FILES = 24
TARGET_SECONDS = 1.0


def _pick_files(cfg, root, n, seed):
    from .roundtrip import iter_corpus_files
    files = [p for _s, _sh, p in iter_corpus_files(cfg, root)
             if Path(p).suffix.lower() in (".srt", ".ass")]
    if not files:
        return []
    rng = random.Random(seed)
    return rng.sample(files, min(n, len(files)))


def _parse(path):
    return formats.read_file(path)


def _pass(cache, files, parse_allowed):
    """One sweep. Returns (elapsed, parses_done)."""
    parses = [0]

    def parse_fn(p):
        parses[0] += 1
        return _parse(p)

    t0 = time.perf_counter()
    for path in files:
        key = content_key(path)
        hit = cache.get(key, "cues")
        if hit is None:
            result = parse_fn(path)
            cache.put(key, "cues", {
                "format": result.format,
                "outcome": result.outcome,
                "cues": [[round(c.start, 3), round(c.end, 3)]
                         for c in result.cues],
            })
    return time.perf_counter() - t0, parses[0]


def main(argv):
    import argparse

    parser = argparse.ArgumentParser(prog="python -m tsubasa.dev cache")
    parser.add_argument("--bench", action="store_true", required=True)
    parser.add_argument("-n", type=int, default=N_FILES)
    parser.add_argument("--seed", type=int, default=20260908)
    args = parser.parse_args(argv)

    cfg = load_config()
    root = corpus_root(cfg)
    if not root.is_dir():
        sys.stderr.write("corpus not found at %s\n" % root)
        return 2

    files = _pick_files(cfg, root, args.n, args.seed)
    if len(files) < args.n:
        sys.stderr.write("only %d files available\n" % len(files))
        if not files:
            return 2

    tmp = Path(tempfile.mkdtemp(prefix="tsubasa-bench-"))
    try:
        cache = Cache(root=tmp)

        # Read every file once first, so the OS page cache is warm for BOTH
        # passes. Otherwise pass 1 measures cold disk and pass 2 measures the
        # cache, and the ratio is mostly an artefact of the filesystem.
        for p in files:
            with open(p, "rb") as fh:
                fh.read()

        cold, cold_parses = _pass(cache, files, True)
        warm, warm_parses = _pass(cache, files, False)

        print("=" * 70)
        print("CACHE BENCH  (RUNBOOK 1b)")
        print("=" * 70)
        print("  files                    %6d" % len(files))
        print("  cache dir                %s" % tmp)
        print("")
        print("  run 1 (cold cache)       %8.3f s   %d parsed" % (cold, cold_parses))
        print("  run 2 (warm cache)       %8.3f s   %d parsed" % (warm, warm_parses))
        print("  speedup                  %8.1fx" % (cold / warm if warm else 0))
        print("")

        stats = cache.stats()
        print("  hits %d  misses %d  stale %d  corrupt %d"
              % (stats["hits"], stats["misses"], stats["stale"],
                 stats["corrupt"]))
        print("")

        ok = True
        if warm > TARGET_SECONDS:
            print("  ❌ run 2 took %.3f s, target is under %.1f s"
                  % (warm, TARGET_SECONDS))
            ok = False
        else:
            print("  ✅ run 2 under %.1f s" % TARGET_SECONDS)

        if warm_parses != 0:
            print("  ❌ run 2 parsed %d file(s) -- the target is ZERO decoding"
                  % warm_parses)
            ok = False
        else:
            print("  ✅ run 2 parsed nothing")

        if stats["hits"] != len(files):
            print("  ❌ %d hits for %d files" % (stats["hits"], len(files)))
            ok = False
        else:
            print("  ✅ every file served from cache on the second pass")

        return 0 if ok else 1
    finally:
        shutil.rmtree(str(tmp), ignore_errors=True)
