# -*- coding: utf-8 -*-
"""
The corpus: statistics, the train/validation/sealed split, and the seal itself.

RUNBOOK step 0a.  spec/07-test-plan.md is the authority:

    If you tune the parser on the corpus and test on the same corpus, you have
    overfit and the test proves nothing.

    Split by SHOW, not by file -- files from one show share a naming scheme, so
    a file-level split leaks the scheme across the boundary and the sealed slice
    is no longer independent.

Three properties this module is built around, each paid for:

  1. THE SPLIT NEVER MOVES A FILE.  The corpus is read-only (spec/07-test-plan
     §Test environment) and half the test value is in the filenames themselves.
     The split is a MANIFEST, not a directory layout.

  2. ASSIGNMENT IS DETERMINISTIC AND NFC-NORMALIZED.  sha256 over the NFC form
     of the show name, so the same show lands in the same slice on every
     machine.  macOS stores filenames as NFD; without the normalization, moving
     to stronger hardware (spec/10-deployment.md §migration) would silently
     reshuffle which shows are sealed -- destroying the only independent
     evidence this project will ever have, with nothing on screen to say so.

  3. THE SEAL IS MECHANICAL, NOT PROSE.  shows() REFUSES the sealed slice
     unless the caller both passes allow_sealed=True and sets the unseal token
     in the environment.  LEDGER-HOT.md lists reading the sealed slice early
     under "Never do this", and TRIGGERS.md ranks a mechanical check above a
     written rule for exactly this reason.
"""
import hashlib
import os
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from ..paths import (
    ConfigError,
    cache_root,
    corpus_root,
    load_config,
    read_json,
    repo_root,
    resolution,
    write_json,
)

SLICES = ("dev", "validation", "sealed")
MANIFEST_VERSION = 1

ALGORITHM = (
    "int(sha256(NFC(scope + '/' + show)).hexdigest()[:16], 16) % 100 "
    "-> [0,dev) dev, [dev,dev+validation) validation, else sealed"
)


class SealedSliceError(RuntimeError):
    """Something tried to read the sealed slice before the final gate.

    Not a warning.  The sealed slice is opened ONCE, at the end; reading it
    early destroys the only independent evidence this project will ever have,
    and it cannot be undone by re-sealing the same material.
    """


# A leading corpus ordinal ("00002 Heroic Age") and bracketed release tags
# ("[HorribleSubs]", "(1080p)") are how the SAME show is spelled differently in
# different corpus folders.  They must come off before hashing or the show
# lands in a different slice per folder.
_ORDINAL = re.compile(r"^\d{3,6}\s+")
_TAGS = re.compile(r"[\[\(（【][^\]\)）】]*[\]\)）】]")
_NOISE = re.compile(r"[^0-9a-z぀-ヿ一-鿿]+")


def split_key(name):
    """Canonical key for SPLIT ASSIGNMENT ONLY.

    ⛔ NEVER use this for pairing or series identity.  It deliberately
    OVER-MERGES: it folds punctuation and case, so `Gintama` and `Gintama'`
    collapse to one key.  For matching those are different shows and conflating
    them is a defect (spec/09-corpus-strategy.md §Stage 2).

    Over-merging is the SAFE direction here and under-merging is not.  Two
    spellings of one show landing in different slices silently breaks the seal
    -- we would tune on material the "independent" slice also contains, and
    nothing on screen would say so.  Merging two genuinely different shows only
    makes the 60/20/20 split slightly less even.

    Measured: `naming/` spells a show `00002 Heroic Age` while `video-naming/`
    spells it `Akatsuki no Yona [HorribleSubs] [1080]`. 148 of video-naming's
    229 shows also exist in the jimaku corpus, so this is a live leak, not a
    hypothetical one.
    """
    s = unicodedata.normalize("NFKC", name)
    s = _ORDINAL.sub("", s)
    s = _TAGS.sub(" ", s)
    s = _NOISE.sub(" ", s.lower())
    return " ".join(s.split())


class Show(object):
    """One split unit: a directory whose files share a naming scheme."""

    __slots__ = ("scope", "name", "path")

    def __init__(self, scope, name, path):
        self.scope = scope
        self.name = name
        self.path = path

    @property
    def key(self):
        """The hash key.

        ⭐ Keyed on the SHOW, not on scope+show.  A show appearing in two
        corpus folders must land in the SAME slice in both, or the sealed slice
        stops being independent.  NFC-normalized because macOS stores filenames
        NFD and the split must survive the move to other hardware
        (spec/10-deployment.md §migration).
        """
        return unicodedata.normalize("NFC", split_key(self.name))

    def __repr__(self):
        return "Show(%r, %r)" % (self.scope, self.name)


# --------------------------------------------------------------------------
# assignment
# --------------------------------------------------------------------------

def assign(key, shares):
    """Deterministically place a show key into a slice.

    Pure function of the key -- no seed file, no RNG, no ordering dependence.
    Reproducible on any machine, any Python, any run order.
    """
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    bucket = int(digest[:16], 16) % 100

    edge = shares["dev"]
    if bucket < edge:
        return "dev"
    edge += shares["validation"]
    if bucket < edge:
        return "validation"
    return "sealed"


# --------------------------------------------------------------------------
# discovery
# --------------------------------------------------------------------------

def _iter_dirs(parent):
    """Directory names directly under `parent`, sorted, skipping dotfiles.

    os.scandir rather than glob: one syscall per entry, and it does not build
    an intermediate list of 5,630 Path objects just to throw them away.
    """
    if not parent.is_dir():
        return
    with os.scandir(str(parent)) as it:
        for entry in sorted(it, key=lambda e: e.name):
            if entry.name.startswith("."):
                continue
            try:
                if entry.is_dir():
                    yield entry.name, Path(entry.path)
            except OSError:
                # A path too long for the platform, or a permission fault.
                # Report it rather than silently dropping a test case --
                # filenames are half this corpus.
                sys.stderr.write("  ! could not stat: %s\n" % entry.path)


def discover_shows(cfg, root):
    """Every split unit on disk, per configured scope.

    `showsAt` is either "*" (shows are directly under the slice) or a path with
    a trailing "*" (shows are one or more levels down, e.g. consolidated's
    "scriptfolder/*").
    """
    found = {}
    for scope, spec in cfg["corpus"]["split"].items():
        pattern = spec["showsAt"]
        base = root / scope
        if pattern != "*":
            base = base / pattern.rstrip("/*").rstrip("/")

        found[scope] = [Show(scope, name, path) for name, path in _iter_dirs(base)]
    return found


def count_files(path):
    """Files under `path`, recursively.  Used only by --stat.

    Rule 4 (spec/00-INDEX.md) applied honestly: --verify-split needs directory
    NAMES, not file counts, so it never pays this walk.  Over 33,769 files that
    is the difference between a report and a wait.
    """
    total = 0
    for _root, _dirs, files in os.walk(str(path)):
        total += len(files)
    return total


# --------------------------------------------------------------------------
# the manifest
# --------------------------------------------------------------------------

def manifest_path(cfg=None, start=None):
    cfg = cfg or load_config(start)
    return repo_root(start) / cfg["corpus"]["splitManifest"]


def build_manifest(cfg, root):
    shares = cfg["corpus"]["shares"]
    discovered = discover_shows(cfg, root)

    scopes = {}
    for scope, shows_in_scope in sorted(discovered.items()):
        buckets = {s: [] for s in SLICES}
        for show in shows_in_scope:
            buckets[assign(show.key, shares)].append(show.name)
        scopes[scope] = {s: sorted(buckets[s]) for s in SLICES}

    return {
        "version": MANIFEST_VERSION,
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "algorithm": ALGORITHM,
        "shares": shares,
        "note": (
            "Show names are stored NFC-normalized for hashing but written here "
            "exactly as they appear on disk. The split is a manifest -- no file "
            "is ever moved, and the corpus stays read-only."
        ),
        "scopes": scopes,
    }


def load_manifest(cfg=None, start=None):
    path = manifest_path(cfg, start)
    if not path.is_file():
        raise ConfigError(
            "No split manifest at %s.\n"
            "  Run:  python -m tsubasa.dev corpus --split" % path
        )
    data = read_json(path)
    if data.get("version") != MANIFEST_VERSION:
        raise ConfigError(
            "Split manifest is version %r, this build expects %r: %s"
            % (data.get("version"), MANIFEST_VERSION, path)
        )
    return data


# --------------------------------------------------------------------------
# the guarded accessor -- the only supported way to read the split
# --------------------------------------------------------------------------

def shows(slice_name="dev", scope=None, allow_sealed=False, cfg=None, start=None):
    """Show names in a slice.

    ⛔ The sealed slice needs BOTH allow_sealed=True AND the unseal token in the
    environment.  Two independent gestures, because one of them is an argument a
    caller could add without thinking, and the other has to be typed on purpose.
    """
    cfg = cfg or load_config(start)

    if slice_name not in SLICES:
        raise ValueError("Unknown slice %r; expected one of %s" % (slice_name, SLICES))

    if slice_name == "sealed":
        section = cfg["corpus"]
        token = os.environ.get(section["unsealEnvVar"], "")
        if not allow_sealed or token != section["unsealToken"]:
            raise SealedSliceError(
                "The sealed slice is opened ONCE, at the final gate.\n"
                "  Reading it early destroys the only independent evidence this\n"
                "  project will ever have. See LEDGER-HOT.md.\n"
                "  If this really is the final gate: pass allow_sealed=True and set\n"
                "  %s=%s" % (section["unsealEnvVar"], section["unsealToken"])
            )

    data = load_manifest(cfg, start)
    if scope is not None:
        return list(data["scopes"].get(scope, {}).get(slice_name, []))

    out = []
    for scope_name in sorted(data["scopes"]):
        out.extend(
            "%s/%s" % (scope_name, name)
            for name in data["scopes"][scope_name][slice_name]
        )
    return out


# --------------------------------------------------------------------------
# verification
# --------------------------------------------------------------------------

def verify(cfg, root, start=None):
    """Check the manifest against the disk.

    Returns (ok, list_of_problems, summary_dict).  Every problem names the
    scope and the show, because a message that does not name the actual problem
    is a check that is half built.

    `start` is where to walk up from for the manifest -- threaded through so
    the suite can drive this against a synthetic repo. Verifying only the live
    corpus would prove that today's manifest happens to be tidy, not that the
    checks below can see a manifest that is not.
    """
    problems = []
    data = load_manifest(cfg, start)
    discovered = discover_shows(cfg, root)
    shares = cfg["corpus"]["shares"]

    summary = {"scopes": {}, "totals": {s: 0 for s in SLICES}}

    for scope in sorted(set(list(data["scopes"]) + list(discovered))):
        on_disk = {s.name for s in discovered.get(scope, [])}
        recorded = data["scopes"].get(scope)

        if recorded is None:
            problems.append(
                "scope %r exists on disk with %d shows but is absent from the "
                "manifest -- regenerate with --split" % (scope, len(on_disk))
            )
            continue

        if scope not in discovered:
            problems.append(
                "scope %r is in the manifest but its directory is missing from "
                "the corpus" % scope
            )
            continue

        # 1. disjointness -- no show in two slices
        seen = {}
        for slice_name in SLICES:
            for name in recorded[slice_name]:
                if name in seen:
                    problems.append(
                        "%s/%s appears in BOTH %s and %s -- the slices are not "
                        "disjoint" % (scope, name, seen[name], slice_name)
                    )
                seen[name] = slice_name

        # 2. drift -- the scrape is still growing, so an unassigned show is a
        #    real and silent hole in the split, not a curiosity
        missing_from_manifest = sorted(on_disk - set(seen))
        for name in missing_from_manifest[:10]:
            problems.append(
                "%s/%s is on disk but in no slice -- the corpus grew since the "
                "split was built; re-run --split" % (scope, name)
            )
        if len(missing_from_manifest) > 10:
            problems.append(
                "...and %d more unassigned shows in %r"
                % (len(missing_from_manifest) - 10, scope)
            )

        missing_from_disk = sorted(set(seen) - on_disk)
        for name in missing_from_disk[:10]:
            problems.append(
                "%s/%s is in the manifest but not on disk" % (scope, name)
            )
        if len(missing_from_disk) > 10:
            problems.append(
                "...and %d more manifest shows missing from disk in %r"
                % (len(missing_from_disk) - 10, scope)
            )

        # 3. reproducibility -- the recorded slice must equal what the algorithm
        #    produces now.  This is what catches a hand-edited manifest, and a
        #    machine whose filesystem normalizes differently.
        mismatched = []
        for slice_name in SLICES:
            for name in recorded[slice_name]:
                expected = assign(Show(scope, name, None).key, shares)
                if expected != slice_name:
                    mismatched.append((name, slice_name, expected))
        for name, was, expected in mismatched[:10]:
            problems.append(
                "%s/%s is recorded as %s but the algorithm places it in %s -- the "
                "manifest was hand-edited, or this filesystem normalizes names "
                "differently (NFC vs NFD)" % (scope, name, was, expected)
            )
        if len(mismatched) > 10:
            problems.append(
                "...and %d more assignment mismatches in %r"
                % (len(mismatched) - 10, scope)
            )

        counts = {s: len(recorded[s]) for s in SLICES}
        counts["total"] = sum(counts[s] for s in SLICES)
        summary["scopes"][scope] = counts
        for s in SLICES:
            summary["totals"][s] += counts[s]

    return (not problems), problems, summary


# --------------------------------------------------------------------------
# commands
# --------------------------------------------------------------------------

def _pct(part, whole):
    return (100.0 * part / whole) if whole else 0.0


def _answer_key(root):
    """The alias answer key's size, printed as part of `--stat`.

    RUNBOOK 0c proves itself with *"`corpus --stat` shows 12,259 title rows"*,
    and until 0c that number lived only in a report. It is the denominator of
    every alias measurement (Probe G, RUNBOOK A7), so printing it is what
    makes *"the probe ran against the full key"* checkable rather than assumed.

    🚨 `titles.jsonl` and `titles.json` are DIFFERENT counts and both are
    right. The `.jsonl` is the append-only crawl log and includes tombstones —
    entries whose id later redirected to the homepage. `titles.json` is the
    deduped view with tombstones applied, and it is the answer key. Measured
    2026-09-08: 12,589 logged, 330 tombstoned, **12,259 live**. Reading the
    log's line count as the key size overstates it by exactly those 330.
    """
    live = root / "naming" / "titles.json"
    log = root / "naming" / "titles.jsonl"
    if not live.is_file():
        print("  answer key      ABSENT -- rebuild: node jimaku-corpus.mjs "
              "--titles --root <corpus>/naming")
        return

    try:
        rows = read_json(live)
    except (ValueError, OSError) as exc:
        print("  answer key      UNREADABLE (%s)" % exc)
        return

    def has(row, field):
        value = row.get(field)
        return bool(value and str(value).strip())

    logged = 0
    if log.is_file():
        with open(str(log), "r", encoding="utf-8") as fh:
            logged = sum(1 for line in fh if line.strip())

    print("  answer key      titles.json  %s title rows" % "{:,}".format(len(rows)))
    print("    with Japanese %6s      with English %6s"
          % ("{:,}".format(sum(1 for r in rows if has(r, "japanese"))),
             "{:,}".format(sum(1 for r in rows if has(r, "english")))))
    if logged:
        print("    from titles.jsonl, %s logged row(s), %s tombstoned"
              % ("{:,}".format(logged), "{:,}".format(logged - len(rows))))
    print("")


def cmd_stat(cfg, args):
    root = corpus_root(cfg)
    cache_root(cfg)          # resolve it too, so --stat reports where it landed
    res = resolution()

    print("corpus")
    print("  path      %s" % root)
    print("  resolved  %s" % res.get("corpusHow", "?"))
    print("  config    %s" % res.get("config", "?"))
    print("            (%s)" % res.get("configHow", "?"))
    print("  cache     %s" % res.get("cache", "?"))

    if not root.is_dir():
        print("")
        print("  ABSENT -- the corpus is not on this machine.")
        print("  This is not a config error. Set %s, or copy the corpus over"
              % cfg["corpus"]["envVar"])
        print("  (spec/10-deployment.md, migration step 2).")
        return 2

    print("")
    print("  %-16s %8s %8s   %s" % ("SPLIT SCOPE", "SHOWS", "FILES", "WHY"))
    discovered = discover_shows(cfg, root)
    grand_shows = grand_files = 0
    for scope in sorted(cfg["corpus"]["split"]):
        found = discovered.get(scope, [])
        files = sum(count_files(s.path) for s in found) if not args.fast else -1
        grand_shows += len(found)
        if files >= 0:
            grand_files += files
        print("  %-16s %8d %8s   %s" % (
            scope, len(found),
            "-" if files < 0 else "{:,}".format(files),
            cfg["corpus"]["split"][scope]["why"][:48],
        ))
    print("  %-16s %8d %8s" % (
        "TOTAL", grand_shows,
        "-" if args.fast else "{:,}".format(grand_files),
    ))

    print("")
    print("  %-16s %8s   %s" % ("FIXTURE (unsplit)", "FILES", "WHY"))
    # (the answer-key summary is printed after this block; see _answer_key)
    for name, why in sorted(cfg["corpus"]["fixtures"].items()):
        path = root / name
        files = count_files(path) if (path.is_dir() and not args.fast) else -1
        print("  %-16s %8s   %s" % (
            name,
            "-" if files < 0 else "{:,}".format(files),
            why[:52],
        ))

    print("")
    _answer_key(root)

    manifest = manifest_path(cfg)
    if manifest.is_file():
        data = load_manifest(cfg)
        print("  split manifest  %s" % manifest.name)
        print("  built           %s" % data["generated"])
        totals = {s: 0 for s in SLICES}
        for scope in data["scopes"]:
            for s in SLICES:
                totals[s] += len(data["scopes"][scope][s])
        whole = sum(totals.values())
        for s in SLICES:
            mark = "  (SEALED -- do not read)" if s == "sealed" else ""
            print("    %-11s %6d  %5.1f%%%s"
                  % (s, totals[s], _pct(totals[s], whole), mark))
    else:
        print("  split manifest  ABSENT -- run: python -m tsubasa.dev corpus --split")
        return 2

    return 0


def cmd_split(cfg, args):
    root = corpus_root(cfg)
    if not root.is_dir():
        sys.stderr.write("corpus not found at %s\n" % root)
        return 2

    path = manifest_path(cfg)

    if path.is_file() and not args.force:
        # Rebuilding reshuffles nothing (the assignment is a pure function of
        # the name), but a rebuild after the corpus grows DOES move new shows
        # into the sealed slice -- and if anyone has already looked at the
        # existing split, that matters.  Make it a deliberate act.
        existing = load_manifest(cfg)
        ok, problems, _summary = verify(cfg, root)
        if ok:
            print("Split manifest already present and verified: %s" % path)
            print("  built %s" % existing["generated"])
            print("  Nothing to do. Use --force to rebuild.")
            return 0
        print("Split manifest exists but does not verify (%d problem(s))."
              % len(problems))
        for p in problems[:5]:
            print("  - %s" % p)
        print("  Rebuild with --force, having read why it drifted.")
        return 1

    data = build_manifest(cfg, root)
    write_json(path, data)

    print("Wrote %s" % path)
    totals = {s: 0 for s in SLICES}
    for scope in sorted(data["scopes"]):
        counts = {s: len(data["scopes"][scope][s]) for s in SLICES}
        total = sum(counts.values())
        print("  %-16s %5d shows -> dev %d / validation %d / sealed %d"
              % (scope, total, counts["dev"], counts["validation"], counts["sealed"]))
        for s in SLICES:
            totals[s] += counts[s]
    whole = sum(totals.values())
    print("  %-16s %5d shows -> dev %d (%.1f%%) / validation %d (%.1f%%) / sealed %d (%.1f%%)"
          % ("TOTAL", whole,
             totals["dev"], _pct(totals["dev"], whole),
             totals["validation"], _pct(totals["validation"], whole),
             totals["sealed"], _pct(totals["sealed"], whole)))
    return 0


def cmd_verify_split(cfg, args):
    root = corpus_root(cfg)
    if not root.is_dir():
        sys.stderr.write("corpus not found at %s\n" % root)
        return 2

    ok, problems, summary = verify(cfg, root)

    for scope in sorted(summary["scopes"]):
        c = summary["scopes"][scope]
        print("  %-16s %5d shows   dev %-5d validation %-5d sealed %-5d"
              % (scope, c["total"], c["dev"], c["validation"], c["sealed"]))
    t = summary["totals"]
    whole = sum(t.values())
    print("  %-16s %5d shows   dev %-5d validation %-5d sealed %-5d"
          % ("TOTAL", whole, t["dev"], t["validation"], t["sealed"]))
    print("")

    if ok:
        print("OK  three disjoint sets, every show assigned, every assignment "
              "reproducible.")
        return 0

    print("FAIL  %d problem(s):" % len(problems))
    for p in problems:
        print("  - %s" % p)
    return 1


def main(argv):
    import argparse

    parser = argparse.ArgumentParser(prog="python -m tsubasa.dev corpus")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--stat", action="store_true",
                       help="counts, paths, and how each path resolved")
    group.add_argument("--split", action="store_true",
                       help="build the dev/validation/sealed manifest")
    group.add_argument("--verify-split", action="store_true",
                       help="check the manifest against the disk")
    parser.add_argument("--force", action="store_true",
                        help="rebuild an existing manifest")
    parser.add_argument("--fast", action="store_true",
                        help="--stat without the file-count walk")
    args = parser.parse_args(argv)

    cfg = load_config()

    if args.stat:
        return cmd_stat(cfg, args)
    if args.split:
        return cmd_split(cfg, args)
    return cmd_verify_split(cfg, args)
