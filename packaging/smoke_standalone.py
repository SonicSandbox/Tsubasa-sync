# -*- coding: utf-8 -*-
u"""Is the frozen app whole, and does it do the job? RUNBOOK 4c.

    python packaging/smoke_standalone.py <app folder> --media <yomi18 folder>

`<app folder>` is the `--onedir` output holding `tsubasa.exe` and
`tsubasa-gui.exe`. `--media` is `$TSUBASA_CORPUS/video-derived/yomi18/`; with
it absent the media half SKIPS and says so, and the build half still runs.

⛔ Run this with the venv Python the app was BUILT from, never the system one:
it imports `tsubasa.gui.run` to ask the product where it would look for its own
CLI, and that has to be the same code the bundle carries.

===========================================================================
🚨 WHAT EACH CHECK IS FOR — every one is a measured failure, not a guess
===========================================================================

  1. **Both executables, one folder.** `STANDALONE-BUILD-SCOPE.md` trap 1:
     frozen, the GUI runs `tsubasa.exe` from its own directory, so *ship only
     the GUI and every single run fails at launch.*
  2. **`--version` says the build is WHOLE.** Trap 8: a frozen build that lost
     its alias table still runs, still exits 0, and settles pairs by name
     51.4% of the time instead of 80.0%, with nothing raising anywhere. ⛔ The
     exit code alone is not the evidence — the counts are read.
  3. **A Japanese filename survives end to end.** Trap 2: a frozen app IGNORES
     `PYTHONIOENCODING`, and this project's worst bug class is an encoding
     assumption. ⚠ The child's stdout is captured as BYTES and decoded
     STRICTLY, so a `U+FFFD` found in it is the child's own mojibake and never
     this script's decoding.
  4. **A dry run writes nothing**, proved by a content hash of the tree.
     `LEDGER-HOT.md` trap 0d: a retime is length-preserving, so `{name: size}`
     is blind to exactly what this tool does.
  5. **The run the Sync button spawns**, driven through the product's own
     `gui.run.Runner` with `sys.frozen` set and `sys.executable` pointing at
     the built `tsubasa-gui.exe`. That is `cli_argv` -> `argv_for` ->
     `child_env` -> `Popen` -> the NDJSON parse -> the counts: everything the
     button does except the widget.
     ⚠ **What it still does NOT prove:** that the frozen GUI *process* takes
     that branch. Nothing but opening the window does, and that is §4 step 4's
     acceptance test — a person, on a machine with no Python.
"""
import argparse
import hashlib
import io
import os
import shutil
import subprocess
import sys
import tempfile

MIN_ALIAS_ENTRIES = 100000

#: ⛔ The real release names, copied from `dev/e2ebench.py` rather than
#: invented. Its own note: *do not "tidy" these into ASCII — the Japanese ones
#: are what the parser, the identity stage and the output namer actually meet,
#: and an ASCII stand-in is the same mistake as an ASCII fixture for an
#: encoding rule.* ⚠ And trap 15 asks for real names in this smoke test
#: specifically, for Windows path length and CJK.
VIDEO = (u"track_2.mkv",
         u"[SubsPlease] Yomi no Tsugai - 18 (1080p) [DD1CA4BC].mkv")
SUBS = (
    # a real subtitle for this episode -- must sync
    (u"abema.streaming.ja.srt",
     u"黄泉のツガイ.S01E18.WEBRip.ABEMA.ja[cc].srt", u"sync"),
    # ⚠ A DIFFERENT EPISODE OF THE SAME SHOW, AND IT IS NOT "REFUSED".
    # This row was tagged `refuse` with a note claiming the run therefore
    # exercised both outcomes. Measured: it produces **no row at all** — it is
    # never a candidate, because candidates are indexed on (season, episode).
    # ⛔ The tag was also read nowhere. It is here as a file that must be left
    # completely alone, which is a real property and the one it can prove.
    (u"wrong-episode.s01e15.srt",
     u"[NanakoRaws] Yomi no Tsugai S01E15 (AT-X 1080p HEVC AAC).srt",
     u"untouched"),
)

FAILURES = []
SKIPPED = []


def check(label, condition, detail=u""):
    print(u"  %-5s %s%s" % (u"ok" if condition else u"FAIL", label,
                            u"" if condition else u"  <- %s" % detail))
    if not condition:
        FAILURES.append((label, detail))
    return condition


def skip(label, why):
    print(u"  %-5s %s  <- %s" % (u"SKIP", label, why))
    SKIPPED.append((label, why))


def digest(path):
    h = hashlib.sha256()
    with io.open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def tree(root):
    u"""-> {relative path: (size, content hash)}. ⭐ THE HASH IS THE POINT.

    `e2ebench.tree()`'s shape, kept here rather than imported so this script
    runs against a bundle whose `tsubasa.dev` was pruned. A retime is
    length-preserving: `00:00:01,918` and `00:00:00,888` are the same byte
    count, so a size-only snapshot cannot see what this tool does.
    """
    out = {}
    for base, dirs, files in os.walk(root):
        dirs.sort()
        for name in files:
            full = os.path.join(base, name)
            rel = os.path.relpath(full, root).replace(os.sep, u"/")
            out[rel] = (os.path.getsize(full), digest(full))
    return out


def run_exe(argv, env=None):
    u"""-> (code, text). ⚠ BYTES, DECODED STRICTLY.

    Capturing with `encoding="utf-8", errors="replace"` would put `U+FFFD`
    into the text itself, and check 3 exists to find `U+FFFD` the CHILD
    produced. Strict decoding separates the two: a decode error is the child
    emitting something that is not UTF-8, and is reported as its own failure.
    """
    proc = subprocess.run(argv, capture_output=True,
                          env=env or dict(os.environ), timeout=900)
    raw = proc.stdout + proc.stderr
    try:
        return proc.returncode, raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        return proc.returncode, u"� NOT-UTF-8 FROM THE CHILD: %s" % exc


# ---------------------------------------------------------------------------
# 1 + 2 -- the build
# ---------------------------------------------------------------------------

def check_the_build(app, expect_version):
    print(u"\n1. the folder, and trap 1")
    cli = os.path.join(app, u"tsubasa.exe" if os.name == "nt" else u"tsubasa")
    gui = os.path.join(app, u"tsubasa-gui.exe" if os.name == "nt"
                       else u"tsubasa-gui")
    check(u"tsubasa.exe is in the app folder", os.path.isfile(cli), cli)
    check(u"tsubasa-gui.exe is BESIDE it", os.path.isfile(gui), gui)

    # ⛔ The hook's job, asserted on the artefact rather than on the hook. A
    # wheel check cannot see a freezer that dropped the file.
    inside = os.path.join(app, u"_internal", u"tsubasa", u"data",
                          u"aliases.tsv.gz")
    check(u"the alias table is inside the bundle",
          os.path.isfile(inside) and os.path.getsize(inside) > 1000000,
          inside)

    print(u"\n2. --version, and trap 8")
    code, text = run_exe([cli, u"--version"])
    lines = text.splitlines()
    print(u"".join(u"       | %s\n" % line for line in lines))
    check(u"--version exits 0 on a whole build", code == 0, u"exit %d" % code)
    if not lines:
        check(u"--version printed anything", False, u"no output")
        return cli, gui
    check(u"the first line is `tsubasa <version>`",
          len(lines[0].split()) == 2 and lines[0].split()[0] == u"tsubasa",
          lines[0])
    if expect_version:
        check(u"it reports the version this build was made from",
              lines[0].split()[-1] == expect_version,
              u"%s, wanted %s" % (lines[0], expect_version))
    check(u"it knows it is frozen",
          len(lines) > 1 and lines[1].endswith(u", frozen"),
          lines[1] if len(lines) > 1 else u"")
    check(u"the last line is `ok`", lines[-1] == u"ok", lines[-1])

    # ⛔ THE COUNTS, NOT THE WORD. `ok` is computed from them, so reading it
    # alone would pass against a self_check() that had itself been broken.
    counts = [l for l in lines if l.startswith(u"aliases ")]
    loaded = declared = -1
    if check(u"it reports the alias counts", bool(counts), lines):
        # ⚠ `aliases 221258/221258,` — the line continues into the vocabulary
        # and ffmpeg, so the comma comes with the token.
        # 🚨 AND IT PARSES DEFENSIVELY, because the first version CRASHED ON
        # THE EXACT DEFECT IT EXISTS TO DETECT: a build with no alias table
        # prints `aliases 0/?`, `int()` raised, and §2b, §2c and the whole
        # summary never ran. `LEDGER-HOT.md`: a non-zero exit is not evidence
        # until you know why — here it hid ten checks behind a traceback.
        pair = counts[0].split()[1].rstrip(u",").split(u"/")
        loaded = int(pair[0]) if pair[0].isdigit() else -1
        declared = int(pair[1]) if len(pair) > 1 and pair[1].isdigit() else -1
    check(u"the alias table LOADED, at full size",
          loaded >= MIN_ALIAS_ENTRIES and loaded == declared,
          u"%s of %s (from %r)" % (loaded, declared, counts[:1]))

    code, text = run_exe([cli, u"--help"])
    check(u"--help exits 0 and offers --version",
          code == 0 and u"--version" in text, u"exit %d" % code)

    # ⚠ GPL-3.0 TRAVELS WITH BINARIES (trap 11). A person who downloads the zip
    # and never opens GitHub must still receive the terms, so these are checked
    # on the FOLDER THAT GETS ZIPPED, not on the repository.
    print(u"\n2b. what has to travel with the binary")
    # 🚨 EVERY NEEDLE IS A PHRASE FROM THE BODY, NOT FROM THE TITLE, AND EVERY
    # FLOOR IS THE REAL FILE'S SIZE. Measured 2026-09-17: `THIRD_PARTY_LICENSES`
    # was given the needle `u""`, which is in every string — 252 bytes of the
    # word *banana* passed it — and a GPL **cut to its first 400 bytes**, with
    # the masthead and ZERO terms, passed the licence check. ⛔ Trap 11 is about
    # conveying the TERMS; a title is not the terms.
    licences = (
        # ⚠ EVERY NEEDLE HERE WAS GREPPED OUT OF THE REAL FILE, not recalled.
        # The first draft used *"You must cause the modified files to carry
        # prominent notices"* — which is **GPL-2.0's** wording and appears
        # nowhere in GPL-3.0, so the check failed against a perfectly good
        # licence. A fixture written from memory is a fixture about memory.
        (u"LICENSE", 30000,
         (u"GNU GENERAL PUBLIC LICENSE", u"Version 3, 29 June 2007",
          u"TERMS AND CONDITIONS",
          u"5. Conveying Modified Source Versions",
          u"15. Disclaimer of Warranty",
          u"END OF TERMS AND CONDITIONS")),
        (u"THIRD_PARTY_LICENSES.md", 800, (u"numpy", u"tsubasa")),
        (u"README-FIRST.txt", 800,
         (u"not code-signed", u"SmartScreen", u"--version", u"GPL-3.0")),
    )
    for name, floor, needles in licences:
        path = os.path.join(app, name)
        body = u""
        if os.path.isfile(path):
            body = io.open(path, encoding="utf-8", errors="replace").read()
        missing = [n for n in needles if n not in body]
        check(u"%s is beside the executables, whole" % name,
              os.path.isfile(path) and len(body) >= floor and not missing,
              u"%s: %d bytes (floor %d), missing %r"
              % (path, len(body), floor, missing))

    # ⚠ AND THE VERSION IT TELLS THE READER. `README-FIRST.txt` is generated
    # per build; rewritten to say `tsubasa 9.9.9-WRONG` it passed every check,
    # because the only needle looked at was about signing.
    notes = os.path.join(app, u"README-FIRST.txt")
    if os.path.isfile(notes) and lines:
        said = io.open(notes, encoding="utf-8", errors="replace").read()
        check(u"README-FIRST.txt names the version this build reports",
              lines[0] in said, u"%r is not in README-FIRST.txt" % lines[0])

    # ⭐ MEASURED, not guessed — `STANDALONE-BUILD-SCOPE.md` §4 step 6 asks for
    # the number. A frozen `--onedir` app pays its unpack cost once at build
    # time, so this is the real cold start a user waits through.
    import time
    started = time.time()
    run_exe([cli, u"--help"])
    print(u"       cold start to a printed --help: %.2f s"
          % (time.time() - started))

    check_the_table_RESOLVES_a_name(inside)
    check_the_data_check_can_fail(app, cli, inside)
    check_the_gui_executable_actually_runs(gui)
    return cli, gui


def check_the_table_RESOLVES_a_name(table):
    u"""🚨 A COUNT IS NOT A TABLE. Measured 2026-09-17.

    `self_check()` and every check above compare the number of entries against
    the number the header declares. ⛔ An adversary **reversed every key** — a
    bijection, so the count and the header are untouched — and the bundle
    reported `aliases 221258/221258 … ok`, exit 0, **all eighteen checks
    green**, over a table in which not one real title resolves. That is the
    80.0% → 51.4% loss exactly, passing the gate written to catch it.

    ⚠ And it is the SECOND attempt at a semantic check here. The first was a
    cross-script *pairing*, retired the same day because it still paired with
    the table deleted — candidates index on (season, episode), so the titles
    never mattered. ⭐ This one asks the table the question the table exists to
    answer, and a negative control makes sure the answer is not just *yes*.

    ⚠ Read through the installed package's own reader, from the BUNDLE's file
    — so it is the shipped bytes being asked, not the repository's copy.
    """
    print(u"\n2d. and the table RESOLVES a real name, not just a count")
    try:
        from tsubasa.naming import alias as ALIAS
    except ImportError as exc:
        return skip(u"the table resolves a name", u"tsubasa not importable "
                    u"here: %s" % exc)

    loaded = ALIAS.load(path=table)
    verdict, score, reason = ALIAS.bridge(u"Yomi no Tsugai", u"黄泉のツガイ",
                                          table=loaded)
    check(u"a romaji title and its Japanese one reach one entity",
          verdict == u"same" and u"Q" in reason,
          u"%r %r %r" % (verdict, score, reason))

    # ⛔ THE NEGATIVE CONTROL. Without it, a table rewritten to answer SAME for
    # everything would pass the line above — and that is a worse table than an
    # empty one, because it pairs confidently and wrongly.
    other, _score, _why = ALIAS.bridge(u"Hell Mode", u"黄泉のツガイ",
                                       table=loaded)
    check(u"and two unrelated titles do NOT", other != u"same", other)


def check_the_gui_executable_actually_runs(gui):
    u"""🚨 THE THING THE README TELLS PEOPLE TO DOUBLE-CLICK WAS NEVER RUN.

    Every check here drove `tsubasa.exe`; `tsubasa-gui.exe` was only ever
    `os.path.isfile`'d. ⛔ A missing Tcl payload, a bad `MERGE`, or an exclude
    that took something the window needs would all ship green — and the GUI
    failing to start is the one failure a person meets before anything else.

    ⭐ Started and required to STAY started. A frozen Tk app that dies on
    launch exits within a second or two; one that opened a window sits there.
    """
    print(u"\n2e. and the window opens")
    if os.name != "nt":
        return skip(u"the GUI starts", u"a windowed .exe is Windows-only here")
    import subprocess
    import time
    try:
        proc = subprocess.Popen([gui], stdout=subprocess.DEVNULL,
                                stderr=subprocess.PIPE)
    except OSError as exc:
        return check(u"tsubasa-gui.exe starts", False, u"%s" % exc)
    try:
        time.sleep(12)
        alive = proc.poll() is None
        said = u""
        if not alive:
            said = (proc.stderr.read() or b"").decode("utf-8", "replace")
        check(u"tsubasa-gui.exe is still running 12 s after launch",
              alive, u"exited %s: %s" % (proc.poll(), said.strip()[:300]))
    finally:
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=30)


def check_the_data_check_can_fail(app, cli, table):
    u"""🚨 EVERYTHING ABOVE ASSERTED `ok`. THIS ASSERTS IT CAN SAY OTHERWISE.

    ⭐ *A test that has never failed has not been tested* — and here it is the
    artefact's own instrument, not a unit under a monkeypatch. Trap 8 is a
    claim about THIS binary: that a build which lost its alias table would be
    caught. The only way to know is to take the table away from the built
    bundle and look.

    ⚠ MEASURED 2026-09-17, and it retired a check that could not fail: a
    cross-script pair (`Yomi no Tsugai` / `黄泉のツガイ`) was going to be the
    data proof, and it **still paired with the table deleted** — candidates
    are indexed on (season, episode), so the note about a waiting subtitle
    says nothing about the alias table at all.

    ⛔ The table is moved aside and put back in a `finally`, then hash-compared
    — the shape every mutation probe in this project uses.
    """
    print(u"\n2c. and the same instrument can say NOT ok")
    if not os.path.isfile(table):
        return skip(u"the data check can fail", u"no table at %s" % table)
    before = digest(table)
    held = table + u".held"
    os.replace(table, held)
    # 🚨 THE RESTORE IS THE ONLY THING THAT MAY NOT BE SKIPPED, and the first
    # version could skip it two ways: if `run_exe` raised (a timeout, a kill),
    # the exception escaped `main()` and NONE of this section's checks were
    # recorded; and if the restore ITSELF raised (an antivirus lock), the
    # bundle was left broken with a `.held` file beside it and the line that
    # would have said so was never reached. ⛔ Chained with the packager,
    # which used to zip whatever it found, that state shipped.
    trouble = u""
    try:
        try:
            code, text = run_exe([cli, u"--version"])
            lines = text.splitlines()
            check(u"with the table gone, the last line is NOT ok",
                  bool(lines) and lines[-1] == u"NOT ok", lines[-1:])
            check(u"with the table gone, it exits 1", code == 1,
                  u"exit %d" % code)
            check(u"and the sentence tells a frozen app's author what to do",
                  u"frozen" in text and u"hook" in text,
                  [l for l in lines if l.startswith(u"PROBLEM:")][:1])
            check(u"it still names the measured cost of the loss",
                  u"80.0% to 51.4%" in text, text[:200])
        except Exception as exc:                          # noqa: BLE001
            trouble = u"%s: %s" % (type(exc).__name__, exc)
    finally:
        restored = u""
        try:
            os.replace(held, table)
        except Exception as exc:                          # noqa: BLE001
            restored = u"%s: %s" % (type(exc).__name__, exc)

    check(u"the bundle was restored byte-identical",
          not restored and os.path.isfile(table) and digest(table) == before,
          u"🚨 THE BUNDLE IS BROKEN AND %s IS STILL THERE. %s"
          % (held, restored) if restored else table)
    check(u"the removal check ran to completion", not trouble, trouble)


# ---------------------------------------------------------------------------
# 3 + 4 + 5 -- real media with real Japanese names
# ---------------------------------------------------------------------------

def stage(media, into):
    folder = os.path.join(into, u"Yomi no Tsugai")
    os.makedirs(folder)
    shutil.copy2(os.path.join(media, VIDEO[0]), os.path.join(folder, VIDEO[1]))
    for source, name, _want in SUBS:
        shutil.copy2(os.path.join(media, source), os.path.join(folder, name))
    return folder


def check_a_real_run(cli, gui, media, app):
    print(u"\n3+4. a dry run over real media with Japanese names")
    root = tempfile.mkdtemp(prefix=u"tsubasa-smoke-")
    cache = os.path.join(root, u"cache")
    env = dict(os.environ, TSUBASA_CACHE=cache, TSUBASA_NO_OS_TRASH=u"1")
    try:
        folder = stage(media, root)
        before = tree(folder)

        code, text = run_exe([cli, folder, u"--dry-run"], env=env)
        print(u"".join(u"       | %s\n" % l for l in text.splitlines()[:24]))
        check(u"the dry run exits 0 or 1 (a refusal is expected)",
              code in (0, 1), u"exit %d" % code)
        check(u"no U+FFFD anywhere in what it printed",
              u"�" not in text,
              u"mojibake: %r" % [l for l in text.splitlines()
                                 if u"�" in l][:2])
        check(u"it printed the Japanese subtitle's real name",
              u"黄泉のツガイ" in text, text[:200])
        check(u"a DRY RUN changed nothing, by content hash",
              tree(folder) == before,
              u"%s" % sorted(set(tree(folder).items()) ^ set(before.items()))[:2])

        print(u"\n   the real run")
        code, text = run_exe([cli, folder], env=env)
        print(u"".join(u"       | %s\n" % l for l in text.splitlines()[:24]))
        after = tree(folder)
        written = sorted(set(after) - set(before))
        kept = sorted(set(before) - set(after))
        check(u"no U+FFFD anywhere in the real run either",
              u"�" not in text, text[:200])
        check(u"a synced subtitle is on disk", bool(written), u"nothing new")
        check(u"exactly one file was written, named after the video",
              len(written) == 1
              and written[0].startswith(u"[SubsPlease] Yomi no Tsugai - 18"),
              written)

        # =================================================================
        # 🚨 AND IT IS OPENED. A NAME IS NOT A RETIME.
        # =================================================================
        # The first version asserted a name prefix and never read the file, so
        # a build that wrote 0 bytes, or copied the source through UNSHIFTED,
        # was green — `LEDGER-HOT.md` names three mutations of exactly this
        # shape, and the project's own `e2ebench` asserts by content hash.
        # ⭐ The retime is length-preserving, so the proof is that the bytes
        # DIFFER from the source while the cue count does not.
        if written:
            out_path = os.path.join(folder, written[0])
            src = [n for n in before if n.endswith(u".ja[cc].srt")]
            body = io.open(out_path, encoding="utf-8", errors="replace").read()
            source = io.open(os.path.join(folder, src[0]), encoding="utf-8",
                             errors="replace").read() if src else u""
            check(u"the written subtitle has real content",
                  len(body) > 1000 and u"-->" in body,
                  u"%d bytes" % len(body))
            check(u"it was RETIMED, not copied through unchanged",
                  body != source,
                  u"the output is byte-identical to its source — nothing "
                  u"was shifted")
            check(u"and it kept every cue (a retime preserves the count)",
                  body.count(u"-->") == source.count(u"-->"),
                  u"%d cues out, %d in"
                  % (body.count(u"-->"), source.count(u"-->")))
            check(u"no U+FFFD reached the written file",
                  u"�" not in body,
                  u"the subtitle text itself is mojibake")
        # 🚨 BY CONTENT, NOT BY NAME. `kept` is a set difference over NAMES, so
        # a file retimed in place keeps its name AND its byte count and is
        # invisible to it — `LEDGER-HOT.md` trap 0d, and an adversarial pass
        # demonstrated exactly this against a check written to catch it. The
        # S01E15 file is a different episode, so nothing may touch it at all.
        untouched = [n for n in before if u"S01E15" in n]
        check(u"the other episode's subtitle exists and is byte-identical",
              bool(untouched) and all(after.get(n) == before[n]
                                      for n in untouched),
              u"%r: %r -> %r" % (untouched,
                                 [before.get(n) for n in untouched],
                                 [after.get(n) for n in untouched]))
        print(u"       wrote: %s" % (written or u"-"))
        print(u"       gone:  %s" % (kept or u"-"))

        print(u"\n5. the run the Sync button spawns (trap 1, at runtime)")
        check_the_gui_path(gui, folder, env, root)
    finally:
        shutil.rmtree(root, ignore_errors=True)


def check_the_gui_path(gui, folder, env, root):
    u"""⭐ THE PRODUCT'S OWN RULE, NOT A RE-DERIVED PATH JOIN.

    `gui.run.Runner` is what `gui/app.py`'s Sync button calls. Told it is
    frozen and that it lives where the built `tsubasa-gui.exe` lives, it must
    find `tsubasa.exe` beside itself and get a real run back.
    """
    try:
        from tsubasa.gui import run as RUN
    except ImportError as exc:
        return skip(u"the Sync button's own path", u"tsubasa not importable "
                    u"here: %s. Run this with the venv the app was built from"
                    % exc)

    real_frozen = getattr(sys, "frozen", None)
    real_exe = sys.executable
    real_env = dict(os.environ)
    # ⚠ `Runner.start()` calls `child_env()` with no base, so the child's
    # environment IS `os.environ` — the cache redirect has to go there, not
    # into a keyword `Runner` does not take (`**opts` goes to `argv_for`).
    os.environ.update(env)
    os.environ.pop(u"TSUBASA_CLI", None)
    try:
        sys.frozen = True
        sys.executable = gui
        argv = RUN.cli_argv()
        check(u"the frozen rule resolves to an executable that EXISTS",
              len(argv) == 1 and os.path.isfile(argv[0]), argv)
        runner = RUN.Runner(folder, dry_run=True)
        print(u"       argv: %s" % runner.argv)
        runner.start()
        # ⛔ `wait()` exists for exactly this, and its own docstring records a
        # first draft that span a core at 100% with no deadline.
        run = runner.wait(timeout=600)
    except Exception as exc:                              # noqa: BLE001
        return check(u"the Sync button's own path ran", False,
                     u"%s: %s" % (type(exc).__name__, exc))
    finally:
        sys.executable = real_exe
        if real_frozen is None:
            if hasattr(sys, "frozen"):
                del sys.frozen
        else:
            sys.frozen = real_frozen
        os.environ.clear()
        os.environ.update(real_env)

    print(u"       counts: %r" % (run.counts,))
    check(u"the child the button spawns came back with rows",
          bool(run.rows), u"stderr: %s" % (run.stderr or u"")[:300])
    check(u"and it was not a `could not run`", not run.could_not_run,
          u"exit %r: %s" % (run.code, (run.stderr or u"")[:300]))
    check(u"it knows it was a dry run, off the argv that ran", run.dry_run,
          run.argv)


def from_the_zip(zip_path, into):
    u"""Extract the shipped zip and hand back the app folder inside it.

    🚨 NOTHING OPENED THE ZIP. Every check ran against PyInstaller's output
    FOLDER, and `grep -rn "unzip\\|extractall\\|ZipFile" .github/ packaging/`
    found the wheel checked three ways and `tsubasa-windows-x64.zip` never
    read after it was written. ⛔ A truncated, mis-rooted or short zip would
    upload green — `doctrine/release`: *assert the live artefact*, and the
    artefact is the zip, not the folder it was made from.
    """
    import zipfile
    with zipfile.ZipFile(zip_path) as z:
        bad = [n for n in z.namelist()
               if n.startswith(u"/") or u".." in n.split(u"/")]
        if bad:
            raise ValueError(u"the zip contains escaping paths: %r" % bad[:3])
        z.extractall(into)
    return os.path.join(into, u"tsubasa")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("app", nargs="?", default=None,
                    help="the --onedir folder holding tsubasa.exe")
    ap.add_argument("--zip", dest="zip_path", default=None,
                    help="⭐ the SHIPPED artefact; extracted and tested "
                         "instead of `app`")
    ap.add_argument("--media", default=None)
    ap.add_argument("--version", dest="version", default=None)
    args = ap.parse_args()

    unpacked = None
    if args.zip_path:
        unpacked = tempfile.mkdtemp(prefix=u"tsubasa-zip-")
        args.app = from_the_zip(args.zip_path, unpacked)
        print(u"⭐ testing THE ZIP, extracted to a folder with nothing above "
              u"it:\n   %s" % args.zip_path)
    if not args.app:
        ap.error("give an app folder, or --zip")
    try:
        return _run_everything(args)
    finally:
        if unpacked:
            shutil.rmtree(unpacked, ignore_errors=True)


def _run_everything(args):

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace",
                               line_buffering=True)
    except (AttributeError, ValueError):
        pass

    app = os.path.abspath(args.app)
    print(u"tsubasa standalone smoke test")
    print(u"  app:   %s" % app)
    print(u"  media: %s" % (args.media or u"(none given -- media half skips)"))

    cli, gui = check_the_build(app, args.version)
    if args.media and os.path.isdir(args.media):
        check_a_real_run(cli, gui, args.media, app)
    else:
        skip(u"everything that needs real media",
             u"--media is not a folder: %r" % args.media)

    print(u"\n%d failure(s), %d skipped" % (len(FAILURES), len(SKIPPED)))
    for label, detail in FAILURES:
        print(u"  FAIL  %s  <- %s" % (label, detail))
    for label, why in SKIPPED:
        print(u"  SKIP  %s  <- %s" % (label, why))
    return 1 if FAILURES else 0


if __name__ == "__main__":
    sys.exit(main())
