#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
The runner.

    python run_tests.py                 everything
    python run_tests.py --list          what would run, and what each covers
    python run_tests.py -k pairing      pass through to pytest; iterate mode

Five properties, each one paid for somewhere in doctrine/verification.md:

  1. ⭐ A TEST NOT IN THE RUNNER DOES NOT EXIST -- AND THE RUNNER PROVES IT.
     It enumerates every harness file on disk and FAILS on any that is neither
     registered in tsubasa.config.json nor excused there with a written reason.
     The prose version of this rule did not hold: the build that wrote it down
     still ENDED with four orphaned harnesses, and a harness written
     specifically to close a blind spot was run twice, never registered, and
     the identical blind spot caused the worst failure of that build.

  2. ZERO CHECKS IS A FAILURE, NOT A PASS -- AND SO IS ALL-SKIPPED.  Exit 0
     means "nothing went wrong", which is also what an empty suite returns.
     Counts come from pytest's JUnit XML rather than from regexing "49 passed"
     out of prose -- a suite once printed "REPRODUCED: returning visitor gets a
     broken app", emitted no result line, exited 0, and scored green.
     🚨 The all-skipped half was added 2026-09-17 after an adversary showed
     `PASS alignment-oracle 10 checks, 10 skipped` inside a run reporting
     GREEN.  A suite can vanish without its count reaching zero.

  3. A TOOLING FAULT ANNOUNCES ITSELF AS A TOOLING FAULT, with its own exit
     code.  The oracle's own runner reported a missing pytest module as
     "corpus 1" -- indistinguishable from one failing test.  That exact
     confusion has produced four wrong diagnoses.

  4. EVERY FAILING SUITE'S FULL OUTPUT IS WRITTEN TO DISK, named for the run.
     A full run once reported one failure with its name scrolled off, costing a
     second 8-minute run to learn a name the first run already had.

  5. THE RUNNER RUNS ALONE.  Two runs at once race on shared state, read
     exactly like a regression, and leave litter.  A lock file makes that a
     refusal instead of a diagnosis.

Exit codes:  0 green · 1 a suite failed · 3 tooling fault · 4 orphaned harness
"""
import json
import os
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from tsubasa.paths import ConfigError, load_config  # noqa: E402

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_TOOLING = 3
EXIT_ORPHAN = 4

# pytest's own exit codes.  2 interrupted, 3 internal error, 4 usage error,
# 5 nothing collected -- none of these mean "a test failed", and conflating
# them with 1 is how a broken harness reads as a broken product.
PYTEST_TOOLING_CODES = {2: "interrupted", 3: "internal error",
                        4: "usage error", 5: "no tests collected"}


def stderr(msg):
    # Flush stdout FIRST. The two streams buffer independently, so without this
    # the parent's own headers land after the error they were meant to
    # introduce -- which is how a report reads as if the failure came first.
    sys.stdout.flush()
    sys.stderr.write(msg + "\n")
    sys.stderr.flush()


def rule(title):
    sys.stdout.write("\n%s\n  %s\n%s\n" % ("=" * 74, title, "=" * 74))
    sys.stdout.flush()


# --------------------------------------------------------------------------
# 1. the self-check
# --------------------------------------------------------------------------

def harnesses_on_disk(cfg):
    import re
    d = HERE / cfg["test"]["harnessDir"]
    pattern = re.compile(cfg["test"]["harnessPattern"])
    if not d.is_dir():
        return d, []
    return d, sorted(p for p in d.rglob("*.py") if pattern.match(p.name))


def coverage_of(cfg, suite, harness_dir, all_harnesses):
    """Which harness files this suite's command actually runs.

    Derived from the command, not declared beside it -- a declaration is a
    second copy that drifts from the thing it describes.
    """
    covered = set()
    for token in suite["cmd"]:
        candidate = (HERE / token)
        if not candidate.exists():
            continue
        candidate = candidate.resolve()
        if candidate.is_dir():
            covered.update(h for h in all_harnesses
                           if str(h.resolve()).startswith(str(candidate)))
        elif candidate in {h.resolve() for h in all_harnesses}:
            covered.add(candidate)
    return {h.resolve() if isinstance(h, Path) else h for h in covered}


def self_check(cfg):
    """Fail on any harness that is neither registered nor excused in writing."""
    harness_dir, found = harnesses_on_disk(cfg)
    excused = cfg["test"].get("excused", {})

    registered = set()
    for suite in cfg["test"]["suites"]:
        registered |= coverage_of(cfg, suite, harness_dir, found)

    excused_paths = {(HERE / cfg["test"]["harnessDir"] / name).resolve()
                     for name in excused}

    orphans = [h for h in found
               if h.resolve() not in registered and h.resolve() not in excused_paths]

    missing = []
    for suite in cfg["test"]["suites"]:
        for token in suite["cmd"]:
            if token.startswith(cfg["test"]["harnessDir"]) and token.endswith(".py"):
                if not (HERE / token).exists():
                    missing.append((suite["name"], token))

    return found, orphans, missing, excused


# --------------------------------------------------------------------------
# 2. counting what actually ran
# --------------------------------------------------------------------------

def parse_junit(path):
    """(tests, failures, errors, skipped) from pytest's JUnit XML.

    Asking pytest for a machine-readable count beats parsing "49 passed" out of
    its prose: the prose changes between versions, and a summary line that
    never printed at all reads as zero rather than as an error.
    """
    if not path.is_file():
        return None
    try:
        root = ET.parse(str(path)).getroot()
    except ET.ParseError:
        return None
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    total = fail = err = skip = 0
    for s in suites:
        total += int(s.get("tests", 0))
        fail += int(s.get("failures", 0))
        err += int(s.get("errors", 0))
        skip += int(s.get("skipped", 0))
    return total, fail, err, skip


# --------------------------------------------------------------------------
# 3. running one suite
# --------------------------------------------------------------------------

def run_suite(suite, run_dir, passthrough):
    name = suite["name"]
    log_path = run_dir / ("%s.txt" % name.replace(" ", "-"))
    junit_path = run_dir / ("%s.xml" % name.replace(" ", "-"))

    cmd = [sys.executable] + list(suite["cmd"])
    if "pytest" in cmd:
        cmd += ["--junitxml=%s" % junit_path, "-p", "no:cacheprovider"]
    cmd += passthrough

    rule(name)
    sys.stdout.write("  %s\n\n" % " ".join(cmd[1:]))
    sys.stdout.flush()

    started = time.time()
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    # Capture, then echo AND write to disk.  Not a pipe into a filter: a
    # line-filter block-buffers when it is not writing to a terminal, so a job
    # that is stuck looks identical to one that is working.
    proc = subprocess.run(cmd, cwd=str(HERE), env=env,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    elapsed = time.time() - started

    output = proc.stdout.decode("utf-8", errors="replace")
    sys.stdout.write(output)
    sys.stdout.flush()

    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(str(log_path), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("$ %s\n\n" % " ".join(cmd))
        fh.write(output)
        fh.write("\nexit=%d  elapsed=%.1fs\n" % (proc.returncode, elapsed))

    counts = parse_junit(junit_path)

    result = {"name": name, "rc": proc.returncode, "elapsed": elapsed,
              "log": log_path, "counts": counts, "verdict": None, "why": ""}

    if proc.returncode in PYTEST_TOOLING_CODES and "pytest" in cmd:
        result["verdict"] = "TOOLING"
        result["why"] = "pytest: %s (exit %d)" % (
            PYTEST_TOOLING_CODES[proc.returncode], proc.returncode)
        return result

    if counts is None:
        result["verdict"] = "TOOLING"
        result["why"] = "no machine-readable result -- the suite produced no report"
        return result

    total, failures, errors, skipped = counts
    if total == 0:
        result["verdict"] = "TOOLING"
        result["why"] = "ZERO checks ran. Exit 0 is not a pass."
        return result

    # 🚨 AND A SUITE WHERE EVERY CHECK SKIPPED IS THE SAME THING WEARING
    # A DIFFERENT NUMBER. Property 2 tested `total == 0` only, so a suite
    # that ran 10 checks and skipped 10 of them scored PASS and the whole
    # run said GREEN. Demonstrated live by an adversary:
    #
    #     PASS  alignment-oracle   10 checks, 10 skipped
    #     PASS  negative-controls  11 checks, 11 skipped
    #     GREEN
    #
    # ⛔ Those two are the ground-truth oracle and the suite that proves the
    # aligner can FAIL — both entirely absent, both green. The config has
    # said *a skip is not a pass* in prose since 3a-bis; prose does not
    # enforce, and this is the line that does.
    if skipped == total:
        # 🚨 AND WHICH OF THE TWO IT IS DEPENDS ON WHAT THE SUITE CLAIMED.
        # A suite that needs the corpus, real media or the oracle is
        # EXPECTED to vanish where those are absent -- CI has none of them,
        # and failing there would be a lie in the other direction. But a
        # suite that declared it needs NOTHING and then ran nothing is
        # broken.
        #
        # ⛔ EITHER WAY IT IS NOT A PASS. `alignment-oracle` reported
        # "PASS  10 checks, 10 skipped" on every CI run this project has
        # ever had -- so **the 29-pair alignment oracle has never run in
        # CI**, and the summary said GREEN. Its own fixture docstring says
        # *"a suite that silently skips everything is a green zero"*: the
        # author knew, wrote it down, and nothing enforced it.
        needs = [k for k in ("needsCorpus", "needsMedia", "needsOracle")
                 if suite.get(k)]
        if needs:
            result["verdict"] = "ABSENT"
            result["why"] = ("all %d checks skipped: %s not here"
                             % (total, ", ".join(needs)))
        else:
            result["verdict"] = "TOOLING"
            result["why"] = ("every one of %d checks SKIPPED, and this "
                             "suite declares it needs nothing." % total)
        return result

    if failures or errors or proc.returncode != 0:
        result["verdict"] = "FAIL"
        result["why"] = "%d failed, %d errored of %d" % (failures, errors, total)
        return result

    result["verdict"] = "PASS"
    result["why"] = "%d checks%s" % (
        total, (", %d skipped" % skipped) if skipped else "")
    return result


# --------------------------------------------------------------------------
# the lock
# --------------------------------------------------------------------------

class RunLock(object):
    def __init__(self, path):
        self.path = path
        self.held = False

    def __enter__(self):
        if self.path.exists():
            try:
                info = json.loads(self.path.read_text(encoding="utf-8"))
            except Exception:
                info = {}
            stderr("\nA run is already in flight (pid %s, started %s)."
                   % (info.get("pid", "?"), info.get("started", "?")))
            stderr("  Two runners at once race on shared state, read exactly")
            stderr("  like a regression, and leave litter behind.")
            stderr("  If that run is dead: del %s" % self.path)
            raise SystemExit(EXIT_TOOLING)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(
            {"pid": os.getpid(),
             "started": datetime.now().strftime("%Y-%m-%d %H:%M:%S")}),
            encoding="utf-8")
        self.held = True
        return self

    def __exit__(self, *exc):
        if self.held and self.path.exists():
            self.path.unlink()
        return False


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

    argv = sys.argv[1:]
    want_list = "--list" in argv
    passthrough = [a for a in argv if a != "--list"]

    try:
        cfg = load_config(HERE)
    except ConfigError as exc:
        stderr("\nTOOLING FAULT -- the project config, not a test")
        stderr("  %s" % exc)
        return EXIT_TOOLING

    found, orphans, missing, excused = self_check(cfg)

    if want_list:
        print("harness files on disk (%s/):" % cfg["test"]["harnessDir"])
        for h in found:
            print("  %s" % h.relative_to(HERE))
        print("\nsuites:")
        for s in cfg["test"]["suites"]:
            print("  %-16s %s" % (s["name"], " ".join(s["cmd"])))
        if excused:
            print("\nexcused:")
            for name, why in excused.items():
                print("  %-24s %s" % (name, why))
        return EXIT_OK

    rule("RUNNER SELF-CHECK  (every harness registered or excused in writing)")
    print("  %d harness file(s) on disk, %d suite(s), %d excused"
          % (len(found), len(cfg["test"]["suites"]), len(excused)))

    if missing:
        stderr("\nTOOLING FAULT -- a suite names a harness that does not exist:")
        for suite_name, token in missing:
            stderr("  %-16s -> %s" % (suite_name, token))
        return EXIT_TOOLING

    if orphans:
        stderr("\nORPHANED HARNESS -- on disk, in no suite, with no written excuse:")
        for h in orphans:
            stderr("  %s" % h.relative_to(HERE))
        stderr("\n  A test not in the runner does not exist. Either register it")
        stderr("  under test.suites in tsubasa.config.json, or excuse it there")
        stderr("  WITH THE REASON, which is what the next reader will need.")
        return EXIT_ORPHAN

    print("  OK  no orphans")

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    run_dir = HERE / cfg["test"]["runLogDir"] / stamp

    results = []
    with RunLock(HERE / cfg["test"]["runLogDir"] / ".run.lock"):
        for suite in cfg["test"]["suites"]:
            results.append(run_suite(suite, run_dir, passthrough))

    rule("SUMMARY")
    worst = EXIT_OK
    for r in results:
        print("  %-8s %-16s %-28s %5.1fs"
              % (r["verdict"], r["name"], r["why"], r["elapsed"]))
        if r["verdict"] == "TOOLING":
            worst = EXIT_TOOLING
        elif r["verdict"] == "FAIL" and worst != EXIT_TOOLING:
            worst = EXIT_FAILED

    # ⛔ ABSENT DOES NOT FAIL THE RUN AND IS NEVER FOLDED INTO THE GREEN.
    # The whole defect was a summary that read as *everything ran*, so the
    # count goes next to the verdict where it cannot be missed.
    absent = [r["name"] for r in results if r["verdict"] == "ABSENT"]
    if absent:
        print("\n  ⚠ %d SUITE(S) DID NOT RUN AT ALL -- every check in them"
              " skipped:" % len(absent))
        for name in absent:
            print("      %s" % name)
        print("    They need the corpus, real media or the oracle, none of"
              " which is here.")
        print("    ⛔ This run says NOTHING about what they cover.")

    bad = [r for r in results if r["verdict"] != "PASS"]
    if bad:
        print("\n  full output on disk:")
        for r in bad:
            print("    %s" % r["log"].relative_to(HERE))
    else:
        print("\n  GREEN")

    if worst == EXIT_TOOLING:
        print("\n  ⚠ TOOLING FAULT -- the harness is broken, which says NOTHING")
        print("    about whether the product works. Fix the harness first.")

    return worst


if __name__ == "__main__":
    sys.exit(main())
