# -*- coding: utf-8 -*-
"""
Round-trip the REAL corpus: read every file, write it back with a zero shift,
require the bytes to be identical.

    python -m tsubasa.dev roundtrip            # sample
    python -m tsubasa.dev roundtrip --all      # every dev+validation file

⭐ Why this exists even though 141 synthetic checks already pass:

    "A green suite proves only what the corpus contains." -- LEDGER.md

The synthetic fixtures were written by the same person who wrote the parser, so
they test the cases that person thought of. The corpus contains ~38,000 files
written by hundreds of strangers over twenty years, and it is the only thing
that can find the case nobody imagined.

🔒 Reads the dev and validation slices ONLY. The sealed slice is opened once,
at the final gate; spending it on a parser smoke test would destroy the only
independent evidence this project will ever have.

⛔ Writes nothing anywhere near the corpus. Every comparison is in memory.
"""
import io
import os
import random
import sys
import time
from collections import Counter

from .. import formats
from ..cues import Outcome
from ..paths import corpus_root, load_config

SAMPLE_DEFAULT = 400


def iter_corpus_files(cfg, root, slices=("dev", "validation")):
    """Every subtitle file in the named slices, with its scope and show.

    ⛔ `slices` deliberately has no "sealed" default and the caller cannot pass
    one by accident -- `shows()` refuses it anyway, but this makes the
    intention visible at the call site too.
    """
    from . import corpus as C

    for scope in sorted(cfg["corpus"]["split"]):
        spec = cfg["corpus"]["split"][scope]
        base = root / scope
        pattern = spec["showsAt"]
        if pattern != "*":
            base = base / pattern.rstrip("/*").rstrip("/")
        if not base.is_dir():
            continue
        for slice_name in slices:
            for show in C.shows(slice_name, scope=scope, cfg=cfg):
                show_dir = base / show
                if not show_dir.is_dir():
                    continue
                for dirpath, _dirs, files in os.walk(str(show_dir)):
                    for fn in files:
                        ext = os.path.splitext(fn)[1].lower()
                        if ext in formats.KNOWN_SUBTITLE_EXT:
                            yield scope, show, os.path.join(dirpath, fn)


def main(argv):
    import argparse

    parser = argparse.ArgumentParser(
        prog="python -m tsubasa.dev roundtrip")
    parser.add_argument("--all", action="store_true",
                        help="every file, not a sample")
    parser.add_argument("-n", type=int, default=SAMPLE_DEFAULT,
                        help="sample size (default %d)" % SAMPLE_DEFAULT)
    parser.add_argument("--seed", type=int, default=20260907)
    parser.add_argument("--show-failures", type=int, default=15)
    args = parser.parse_args(argv)

    cfg = load_config()
    root = corpus_root(cfg)
    if not root.is_dir():
        sys.stderr.write("corpus not found at %s\n" % root)
        return 2

    sys.stderr.write("collecting file list...\n")
    files = list(iter_corpus_files(cfg, root))
    sys.stderr.write("  %d subtitle files in dev+validation\n" % len(files))

    if not args.all:
        rng = random.Random(args.seed)
        files = rng.sample(files, min(args.n, len(files)))

    ok = 0
    by_ext = Counter()
    by_codec = Counter()
    by_format = Counter()
    outcomes = Counter()
    mismatches = []
    errors = []
    empties = []
    read_only = []
    t0 = time.time()

    for i, (scope, show, path) in enumerate(files, 1):
        ext = os.path.splitext(path)[1].lower()
        by_ext[ext] += 1
        try:
            with io.open(path, "rb") as fh:
                data = fh.read()
        except (IOError, OSError) as exc:
            errors.append((path, "unreadable: %s" % exc))
            continue

        result = formats.read_bytes(data, filename=path)
        outcomes[result.outcome] += 1

        if result.outcome == Outcome.ERROR:
            errors.append((path, result.reason))
            continue

        by_codec[result.decoded.encoding if result.decoded else "?"] += 1
        by_format[result.format or "-"] += 1

        if not result.cues:
            empties.append((path, result.reason))
            continue

        # ⚠ INSTRUMENT FIX. The first full sweep counted 43 `.idx` files as
        # round-trip MISMATCHES because the writer refused them -- which is the
        # CORRECT behaviour for a bitmap timing reference. The harness was
        # wrong, not the code, and it inflated the failure count by 22%.
        # A refusal we designed for is not a defect; count it as one and the
        # number stops meaning anything.
        if result.format not in formats.WRITABLE_FORMATS:
            read_only.append((path, result.format))
            continue

        try:
            out = formats.rewrite_bytes(result, shift=0.0)
        except Exception as exc:
            mismatches.append((path, "rewrite raised %s: %s"
                               % (type(exc).__name__, exc)))
            continue

        if out == data:
            ok += 1
        else:
            mismatches.append((path, _describe_diff(data, out)))

        if i % 500 == 0:
            sys.stderr.write("    %d/%d  ok=%d  bad=%d  %.0fs\n"
                             % (i, len(files), ok, len(mismatches),
                                time.time() - t0))
            sys.stderr.flush()

    n = len(files)
    elapsed = time.time() - t0

    print("=" * 74)
    print("CORPUS ROUND-TRIP  (dev + validation; sealed slice untouched)")
    print("=" * 74)
    print("  files tested            %7d %s" % (n, "(ALL)" if args.all else "(sample)"))
    print("  ⭐ byte-identical        %7d  (%.2f%%)" % (ok, 100.0 * ok / n if n else 0))
    print("  parsed, zero cues       %7d" % len(empties))
    print("  read-only by design     %7d  (bitmap timing references)"
          % len(read_only))
    print("  ERROR (unreadable)      %7d" % len(errors))
    print("  🚨 ROUND-TRIP MISMATCH   %7d" % len(mismatches))
    print("  elapsed                 %7.1fs  (%.1f ms/file)"
          % (elapsed, 1000.0 * elapsed / n if n else 0))

    print("")
    print("  by extension:")
    for ext, c in by_ext.most_common():
        print("    %-8s %6d" % (ext, c))
    print("  by detected codec:")
    for codec, c in by_codec.most_common(12):
        print("    %-14s %6d" % (codec, c))
    print("  by parsed format:")
    for fmt, c in by_format.most_common():
        print("    %-8s %6d" % (fmt, c))

    if mismatches:
        print("")
        print("  🚨 MISMATCHES -- a zero shift changed the bytes:")
        for path, why in mismatches[:args.show_failures]:
            print("    %s" % os.path.basename(path)[:70])
            print("       %s" % why)
        if len(mismatches) > args.show_failures:
            print("    ...and %d more" % (len(mismatches) - args.show_failures))

    if errors:
        print("")
        print("  ERRORS -- could not read:")
        for path, why in errors[:args.show_failures]:
            print("    %-52s %s" % (os.path.basename(path)[:52], why[:60]))
        if len(errors) > args.show_failures:
            print("    ...and %d more" % (len(errors) - args.show_failures))

    if empties:
        print("")
        print("  READ BUT EMPTY (not an error -- but worth eyeballing):")
        for path, why in empties[:8]:
            print("    %-52s %s" % (os.path.basename(path)[:52], (why or "")[:52]))
        if len(empties) > 8:
            print("    ...and %d more" % (len(empties) - 8))

    return 0 if not mismatches else 1


def _describe_diff(a, b):
    """Name what actually changed. A failure message says what it FOUND."""
    if len(a) != len(b):
        detail = "length %d -> %d" % (len(a), len(b))
    else:
        detail = "same length"
    for i in range(min(len(a), len(b))):
        if a[i:i + 1] != b[i:i + 1]:
            lo = max(0, i - 24)
            return ("%s; first difference at byte %d: %r -> %r"
                    % (detail, i, a[lo:i + 24], b[lo:i + 24]))
    return detail + "; one is a prefix of the other"
