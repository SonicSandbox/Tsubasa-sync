# -*- coding: utf-8 -*-
u"""
Shelling out to the CLI, and reading what comes back. RUNBOOK 3d constraint 2.

    runner = Runner(folder, dry_run=True)
    runner.start()
    for event in runner.drain():      # non-blocking; call it from `after()`
        ...
    run = runner.finished()           # None until the child has exited

===========================================================================
⛔ NO TKINTER IN THIS FILE
===========================================================================

Everything here is testable without a display, and that is the point: the
subprocess, the decoding, the parse and the counts are where the failures
live, and a check that needs a window to run is a check that gets skipped on
CI. `07-test-plan.md` gives the gui row *"output painted right, then looked
at"* — the painting is looked at, and everything under it is asserted.

===========================================================================
🚨 THE HEADLINE MUST PARTITION, AND *"N SYNCED"* IS A CLAIM ABOUT FILES
===========================================================================

`LEDGER.md` §Interface's original defect was a GUI reading the word
`confident` out of prose. **An adversarial pass on 2026-09-10 found the same
defect rebuilt out of fields**, which is worse, because every individual
number was right:

| The run | The CLI said | The first draft of this file said |
| --- | --- | --- |
| a write that FAILED (`write_failed`, outcome still CONFIDENT) | `1 NOT WRITTEN · 0 synced` | 🚨 **`1 synced`**, and `needs_attention` False |
| a **dry run** | `1 would sync` | 🚨 `1 synced` |
| three videos with **no subtitle** | `3 videos with no subtitle · 0 would sync` | 🚨 *"nothing to do — everything here is already in sync"* |
| a run the user **cancelled** mid-plan | — | 🚨 `3 synced` |
| a `⚑` repaired cut | — | counted **twice**: once in `confident`, once in `cut` |

⭐ **The rules that came out of it, and they are the shape of `counts` now:**

1. **The categories PARTITION.** `clean + cut + refused + errored + unknown`
   is `len(rows)`, asserted. A subset presented as a sibling is how eight
   files became eleven on the one line a person reads at a glance.
2. **A CONFIDENT row is not a written file.** `write_failed`, a dry run and a
   cancellation each break that link, and the outcome field cannot see any of
   them. ⛔ Never say *"synced"* off `outcome` alone.
3. ⭐ **When there are no rows, SHOW THE CLI'S OWN SENTENCE.** Displaying the
   summary is not the banned thing; *deciding* from it is. `--json` emits no
   record for an unpaired video — `03-permissions.md` says there is no fourth
   outcome — so the GUI is **structurally blind** there and the honest move is
   to quote the layer that can see.

---------------------------------------------------------------------------
🚨 FOUR THINGS ABOUT THE CHILD THAT READ AS FAILURE AND ARE NOT
---------------------------------------------------------------------------

| Looks like | Actually |
| --- | --- |
| **exit 1** | *"something was REFUSED"* — the whole value proposition. `cli.main`'s own table: *a refusal is a non-zero exit.* ⛔ Only exit **2** means the command could not be run |
| **output on stderr** | `--json` puts NDJSON on stdout and the SUMMARY on stderr, deliberately, *so a pipe stays pure NDJSON and a person is still told what happened.* stderr is an information channel here |
| **zero rows** | could be a settled library, an empty folder, or nothing pairable. ⛔ Three states, one row count |
| **a `⚑` result** | CONFIDENT, and it repaired a broadcast cut. It belongs with the successes, flagged |

---------------------------------------------------------------------------
🚨 AND THE CONSOLE WINDOW
---------------------------------------------------------------------------

`LEDGER.md`: *every ffprobe call flashed a console window that stole focus.
Under a GUI it is worse: the parent has no console, so each child allocates
its own.* `tsubasa/container/ffmpeg.py` already carries the flag for its own
calls; this is the same fix one level up, for the CLI process itself.
"""
import io
import json
import os
import subprocess
import sys
import threading
import time

try:
    import queue
except ImportError:                                       # pragma: no cover
    import Queue as queue

#: `cli.main`'s exit codes, named. ⛔ 1 is not an error.
EXIT_CLEAN = 0
EXIT_ATTENTION = 1
EXIT_CANNOT_RUN = 2

CONFIDENT = u"CONFIDENT"
REFUSED = u"REFUSED"
ERROR = u"ERROR"

#: ⛔ `03-permissions.md`: *the three outcomes.* There is no fourth, and a
#: record claiming one is a `Fault` rather than a row nobody counts.
OUTCOMES = (CONFIDENT, REFUSED, ERROR)


class NotStarted(Exception):
    u"""`wait()` or `cancel()` before `start()`."""


class StillRunning(Exception):
    u"""`wait(timeout=...)` gave up. ⛔ NOT the same as the run finishing."""


# ---------------------------------------------------------------------------
# what to run
# ---------------------------------------------------------------------------

def cli_argv():
    u"""How to invoke the CLI from here. -> [str]

    ⭐ ONE PLACE, because there are three hosts and they disagree:

      * from source, `sys.executable` is python and `-m tsubasa` is right;
      * frozen by PyInstaller, `sys.executable` is the BUNDLE — `-m` would
        re-enter the GUI and open a second window rather than run the CLI, so
        the bundled console entry point beside it is used instead;
      * `TSUBASA_CLI` overrides both, which is how the suite drives a
        deliberately-failing child without inventing a fake process object.

    ⚠ The frozen branch is `10-deployment.md`'s to finish at 4a.
    """
    override = os.environ.get("TSUBASA_CLI")
    if override:
        # 🚨 A PATH MAY BEGIN WITH `[`. Half this corpus's release groups are
        # named `[shincaps]`, `[Erai-raws]`, `[SubsPlease]`, so *"starts with
        # a bracket, therefore JSON"* turns an ordinary directory into a
        # `JSONDecodeError` raised out of `Runner.__init__`. Try the list
        # form, fall back to the literal, and never let the guess raise.
        if override.startswith("["):
            try:
                loaded = json.loads(override)
            except ValueError:
                return [override]
            if isinstance(loaded, list) and loaded and \
                    all(isinstance(x, str) for x in loaded):
                return list(loaded)
            return [override]
        return [override]
    if getattr(sys, u"frozen", False):
        exe = os.path.join(os.path.dirname(sys.executable),
                           u"tsubasa.exe" if sys.platform.startswith("win")
                           else u"tsubasa")
        return [exe]
    return [sys.executable, u"-m", u"tsubasa"]


def argv_for(folder, subs=None, out=None, dry_run=False, recurse=True,
             rename=True, keep_all=False, force=False, verbose=False,
             results=True):
    u"""The full command for one run. -> [unicode]

    🚨 `--json` IS NOT OPTIONAL AND IS NOT A DISPLAY CHOICE. It is what makes
    constraint 4 keepable: with NDJSON there is an `outcome` field to count,
    and without it the only thing on stdout is prose containing the word
    `confident` next to the word `refused`.

    🚨 **THE FOLDER IS MADE ABSOLUTE, AND THAT IS A CORRECTNESS FIX, NOT
    TIDINESS.** `cli.parse` reads any token starting with `-` as a flag and
    refuses it, and with no roots left `cli.main` prints the whole `USAGE`
    block to stderr — so a relative folder called `--json`, or any name
    beginning with a dash, came back as exit 2 whose first stderr line is the
    tool's own tagline. An absolute Windows or POSIX path cannot start with a
    dash. It is also right on its own terms: a GUI's cwd is wherever the
    shortcut pointed.

    ⛔ `force` on a folder scan is refused by `sync()` and always exits 2 —
    *"writing the best of several refused candidates, which is the one thing
    dedupe's rule 1 exists as a GATE to prevent."* Refused HERE instead, in
    the same words, so no control can offer it on this path.
    """
    if folder is None or not str(folder).strip():
        raise ValueError(
            "a folder is needed. Pick one with Browse, or type a path — "
            "tsubasa searches it for videos and subtitles.")
    if force:
        raise ValueError(
            "force applies to an explicit pair, not to a folder. On a folder "
            "it would mean writing the best of several REFUSED candidates, "
            "which is the one thing the ranking exists as a gate to prevent "
            "(05-interface.md). Pair the two files explicitly to force one.")
    # ⛔ REFUSED HERE, BEFORE ANYTHING IS SPAWNED. `sync()` raises on this pair
    # and `cli.main` prints the sentence and exits 2 — correct, and a whole
    # process later. The settings panel can produce the combination with two
    # clicks, so the answer belongs where the two clicks are.
    if out and rename is False:
        raise ValueError(
            "writing somewhere else and retiming in place contradict each "
            "other. Retiming in place means the file keeps its own name "
            "where you left it; writing somewhere else means the output goes "
            "to another folder. Choose one (05-interface.md).")
    argv = list(cli_argv()) + [u"--json"]
    if dry_run:
        argv.append(u"--dry-run")
    if not recurse:
        argv.append(u"--no-recurse")
    if not rename:
        argv.append(u"--no-rename")
    if keep_all:
        argv.append(u"--keep-all")
    if verbose:
        argv.append(u"--verbose")
    if not results:
        argv.append(u"--no-results")
    if subs:
        argv.extend([u"--subs", os.path.abspath(subs)])
    if out:
        argv.extend([u"--out", os.path.abspath(out)])
    argv.append(os.path.abspath(folder))
    return argv


def no_console_kwargs():
    u"""Popen keywords that stop a console flashing over the app. -> dict

    ⚠ The same pair `tsubasa/container/ffmpeg.py` uses, and for the same
    reason one level up. Empty off Windows, where neither exists.
    """
    if not sys.platform.startswith("win"):
        return {}
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    return {"creationflags": flags, "startupinfo": startupinfo}


def child_env(base=None):
    u"""The environment for the child. -> dict

    🚨 `PYTHONIOENCODING` IS LOAD-BEARING AND THE CLI ALONE IS NOT ENOUGH.
    `cli.main` reconfigures its own streams to UTF-8, which covers everything
    it prints — but a traceback from the interpreter, or anything written
    before `main()` is reached, still goes out through the ANSI codepage, and
    on this corpus that means a `UnicodeEncodeError` about a Japanese path
    swallowing the real error. Set it on the process, not just on the streams.
    """
    env = dict(os.environ if base is None else base)
    env["PYTHONIOENCODING"] = "utf-8"
    # ⚠ AND THE CHILD HAS TO BE ABLE TO FIND THE PACKAGE. `python -m tsubasa`
    # resolves through the child's cwd, which is the GUI's cwd — whatever
    # folder the user happened to launch from, and on Windows that is
    # routinely `C:\Windows\System32`. Naming the package's own parent is the
    # only version of this that does not depend on where somebody clicked.
    if not getattr(sys, u"frozen", False):
        parent = os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))))
        existing = env.get("PYTHONPATH", "")
        env["PYTHONPATH"] = (parent + os.pathsep + existing) if existing \
            else parent
    return env


# ---------------------------------------------------------------------------
# what comes back
# ---------------------------------------------------------------------------

class Row(object):
    u"""One NDJSON record from `cli.as_json`, as an object.

    ⛔ EVERY FIELD IS READ, NEVER RECOMPUTED. `cli.py`'s header rule, one
    process boundary further out: the moment this class derives a verdict, a
    percentage or an outcome of its own, the library's answer stops being the
    product.
    """

    __slots__ = ("raw",)

    def __init__(self, raw):
        self.raw = raw

    def __getattr__(self, name):
        try:
            return self.raw[name]
        except KeyError:
            raise AttributeError(name)

    @property
    def is_cut(self):
        u"""Confident, and it needed more than one offset to get there."""
        return (self.raw.get(u"outcome") == CONFIDENT
                and len(self.raw.get(u"segments") or ()) > 1)

    @property
    def landed(self):
        u"""Did bytes actually reach a file? -> bool

        🚨 NOT THE SAME QUESTION AS `outcome == CONFIDENT`, and conflating
        them is the defect at the top of this module. `pipeline` leaves the
        outcome CONFIDENT on a write that failed — deliberately, because the
        ALIGNMENT was confident — and a dry run is confident about a write it
        was told not to perform.
        """
        return bool(self.raw.get(u"output_path")) \
            and not self.raw.get(u"write_failed")

    @property
    def name(self):
        u"""What to show in a list. -> unicode

        ⚠ `subtitle` can be absent on an unpaired video, and `basename` of
        `None` raises rather than returning empty.
        """
        path = self.raw.get(u"subtitle") or self.raw.get(u"video") or u""
        return os.path.basename(path)

    @property
    def written_name(self):
        return os.path.basename(self.raw.get(u"output_path") or u"")

    def __repr__(self):
        return "<Row %s ep=%r %s>" % (self.raw.get(u"outcome"),
                                      self.raw.get(u"episode"), self.name)


class Fault(object):
    u"""Something on stdout that is not a result. Surfaced, never swallowed."""

    __slots__ = ("why", "text")

    def __init__(self, why, text):
        self.why = why
        self.text = text

    def __repr__(self):
        return "<Fault %s: %r>" % (self.why, self.text[:60])


def parse_line(line):
    u"""One NDJSON line -> a `Row`, or a `Fault`.

    🚨 NEVER CONFLATE *"THIS LINE IS NOT A RESULT"* WITH *"NOTHING WENT
    WRONG"*. `LEDGER-HOT.md` records the same shape one layer down — *never
    conflate parsed zero cues with could not read the file, shipped twice.*

    ⛔ **AND THE OUTCOME IS CHECKED AGAINST THE THREE.** An adversarial pass
    fed `'confident'`, `'CONFIDENT '`, `'SKIPPED'` and `None`: each parsed
    into a `Row` that **every count then ignored**, so the row vanished from
    the screen with nothing saying so — *eight rows for a nine-result run*,
    one field further in than the `Fault` machinery was reaching.
    """
    text = line.strip()
    if not text:
        return None
    try:
        raw = json.loads(text)
    except ValueError as exc:
        return Fault(u"unreadable line from the CLI: %s" % exc, text)
    if not isinstance(raw, dict) or u"outcome" not in raw:
        return Fault(u"a line the CLI printed is not a result record", text)
    if raw.get(u"outcome") not in OUTCOMES:
        return Fault(u"a result carries an outcome this reader does not know: "
                     u"%r is not one of %s" % (raw.get(u"outcome"),
                                               u"/".join(OUTCOMES)), text)
    return Row(raw)


def counts(rows):
    u"""-> a dict whose first five keys PARTITION `rows`.

    ===================================================================
    🚨 THIS FUNCTION IS CONSTRAINT 4.
    ===================================================================

    Every number reads a FIELD. `LEDGER.md` §Interface: *the GUI painted a run
    containing refusals green, because "11 confident, 1 refused" contains the
    word "confident".*

    🚨 **AND THE PARTITION IS THE HALF THE FIRST DRAFT GOT WRONG.** `cut` is a
    SUBSET of `confident`, and a footer that printed both read
    `✓ 8 synced  ⚑ 1 repaired  ✗ 1 refused  ! 1 error` — **eleven, over ten
    files** — while another panel in the same window said `7 synced cleanly`.
    Every individual number was right. ⭐ `clean`, `cut`, `refused`,
    `errored` and `unknown` sum to `len(rows)`; `confident` is kept as the
    convenience total and **may never be added to `cut`**.

    ⚠ `landed` is not `confident`: see `Row.landed`.
    """
    rows = [r for r in rows if isinstance(r, Row)]
    cut = sum(1 for r in rows if r.is_cut)
    confident = sum(1 for r in rows if r.raw.get(u"outcome") == CONFIDENT)
    out = {
        # -- the partition ------------------------------------------------
        u"clean": confident - cut,
        u"cut": cut,
        u"refused": sum(1 for r in rows
                        if r.raw.get(u"outcome") == REFUSED),
        u"errored": sum(1 for r in rows if r.raw.get(u"outcome") == ERROR),
        u"unknown": sum(1 for r in rows
                        if r.raw.get(u"outcome") not in OUTCOMES),
        # -- totals and facts about files ---------------------------------
        u"confident": confident,
        u"landed": sum(1 for r in rows if r.landed),
        u"write_failed": sum(1 for r in rows
                             if r.raw.get(u"write_failed")),
        u"forced": sum(1 for r in rows if r.raw.get(u"forced")),
        u"superseded": sum(len(r.raw.get(u"superseded") or ())
                           for r in rows),
    }
    return out


PARTITION = (u"clean", u"cut", u"refused", u"errored", u"unknown")


class Run(object):
    u"""One finished run: what came back, and what it means."""

    def __init__(self, rows, faults, summary, stderr, code, argv,
                 cancelled=False):
        # ⛔ FROZEN. `counts` is computed once and `settled` reads `self.rows`,
        # so a live alias out of the `Runner`'s own list is two answers to one
        # question waiting to diverge. An adversarial pass appended a REFUSED
        # row after construction and got `0 synced` beside `settled = False`.
        self.rows = tuple(rows)
        self.faults = tuple(faults)
        self.summary = summary
        self.stderr = stderr
        self.code = code
        self.argv = list(argv)
        self.cancelled = bool(cancelled)
        self.counts = counts(self.rows)

    @property
    def dry_run(self):
        u"""⭐ READ OFF THE COMMAND THAT RAN, not off a flag passed alongside
        it. The argv is the only record of what was actually asked for, and a
        preview reporting *"N synced"* is this module's second-worst lie."""
        return u"--dry-run" in self.argv

    @property
    def could_not_run(self):
        u"""⛔ ONLY exit 2. A refusal exits 1 and is the tool working."""
        return self.code == EXIT_CANNOT_RUN

    @property
    def partitions(self):
        u"""Do the five categories account for every row? -> bool"""
        return sum(self.counts[k] for k in PARTITION) == len(self.rows)

    @property
    def needs_attention(self):
        u"""Is there anything a person has to look at? -> bool

        ⭐ FROM THE ROWS AND THE RUN, NEVER FROM THE EXIT CODE ALONE. The
        first draft's docstring claimed they agreed; a write that failed exits
        1 with a CONFIDENT row, and a cancelled child exits 1 on Windows —
        neither is visible in `outcome`, and both were reassuring.
        """
        c = self.counts
        return bool(c[u"refused"] or c[u"errored"] or c[u"unknown"]
                    or c[u"write_failed"] or self.faults
                    or self.could_not_run or self.cancelled)

    @property
    def no_rows(self):
        u"""Nothing was decided. ⛔ A FACT, NOT AN INTERPRETATION.

        🚨 The first draft called this `settled` and had `headline()` say
        *"everything here is already in sync"*. Measured against three videos
        with no subtitle at all: `--json` emits **no record** for an unpaired
        video (`03-permissions.md`: there is no fourth outcome), `cli.main`
        exits 0 because unpaired is none of failed/errored/refused — and the
        GUI told the user their folder was finished.

        ⭐ **Three states share this row count** — a settled library, an empty
        folder, and nothing pairable — and the row list cannot tell them
        apart. `headline()` quotes the CLI instead of guessing.
        """
        return not self.rows and not self.faults

    def headline(self):
        u"""The one line, worded from the fields. -> unicode

        ⛔ Composed from `counts`, never MATCHED against `self.summary`.
        ⭐ But when there is nothing to compose from, the summary is
        DISPLAYED — quoting the layer that can see is not the banned thing.
        """
        if self.could_not_run:
            return self._refusal_line()
        if self.cancelled:
            return u"stopped — %d of the files it had got to were written" \
                % self.counts[u"landed"]
        if self.no_rows:
            # ⭐ THE CLI'S OWN SENTENCE. It knows about unpaired videos and
            # settled episodes; this layer does not, and `--json` carries
            # neither. ⛔ Never silent: `cli.main` guarantees a summary on
            # stderr even over a folder that produced no `Result` at all.
            return self.summary or u"nothing was decided — and the CLI said " \
                                   u"nothing about why, which is itself odd"
        c = self.counts
        parts = []
        # 🚨 WHAT IS WRONG COMES FIRST, exactly as the ruled CLI output puts
        # refusals above successes. A headline reading "8 synced" with the
        # refusal appended is the same defect in a different font.
        if c[u"write_failed"]:
            parts.append(u"%d NOT written" % c[u"write_failed"])
        if c[u"errored"]:
            parts.append(u"%d error%s" % (c[u"errored"],
                                          u"" if c[u"errored"] == 1 else u"s"))
        if c[u"refused"]:
            parts.append(u"%d refused" % c[u"refused"])
        if c[u"unknown"]:
            parts.append(u"%d this version does not understand"
                         % c[u"unknown"])
        if self.faults:
            parts.append(u"%d line%s the CLI printed could not be read"
                         % (len(self.faults),
                            u"" if len(self.faults) == 1 else u"s"))
        # ⚠ `would sync` on a dry run. The word `synced` is a claim that a
        # file on disk changed, and a preview changed nothing.
        verb = u"would sync" if self.dry_run else u"synced"
        good = c[u"clean"] + c[u"cut"]
        parts.append(u"%d %s" % (good, verb))
        if c[u"cut"]:
            parts.append(u"%d repaired" % c[u"cut"])
        if c[u"superseded"]:
            parts.append(u"%d superseded → trash" % c[u"superseded"])
        return u" · ".join(parts)

    def _refusal_line(self):
        u"""What to show when the command could not be run at all.

        ⚠ `cli.main` writes a one-line refusal for a bad flag and the WHOLE
        usage block when it is left with no roots. Taking `splitlines()[0]`
        of the second one shows the user the tool's tagline as though it were
        the error — measured. `argv_for` now makes the no-roots case
        unreachable from here, and this is the belt to that brace.
        """
        lines = [l.rstrip() for l in self.stderr.splitlines() if l.strip()]
        if not lines:
            return u"the command could not be run as typed"
        # ⚠ EVERY REFUSAL THIS TOOL WRITES IS ONE SENTENCE. `cli.Usage` and
        # `sync()`'s ValueErrors are single strings with no newlines, so more
        # than a couple of non-empty lines means the usage block.
        if len(lines) > 2:
            return u"the command could not be run as typed — the CLI " \
                   u"answered with its usage, which means it was left with " \
                   u"no folder to search"
        return lines[0]

    def __repr__(self):
        return "<Run exit=%d rows=%d %s>" % (self.code, len(self.rows),
                                             self.counts)


# ---------------------------------------------------------------------------
# running it without freezing the window
# ---------------------------------------------------------------------------

class Runner(object):
    u"""Spawn the CLI, read it on a thread, hand lines back without blocking.

    ⛔ THE TK EVENT LOOP MAY NEVER WAIT ON A CHILD. A 24-episode folder takes
    seconds and a library takes minutes; `communicate()` on the main thread is
    a window that stops repainting, which Windows then paints over with
    *"not responding"* — a working run reported as a crash by the OS itself.

    🚨 **AND THE FIRST DRAFT DID EXACTLY THAT, THROUGH A SIDE DOOR.** Both
    pipes reaching EOF is not the process exiting: a grandchild that outlives
    the CLI holds nothing open, so `drain()` — the function whose docstring
    says ⛔ NEVER BLOCKS — called `_collect()`, whose first line was
    `self._proc.wait()`. **Measured at 20.00 seconds inside one `drain()`
    call**, which is the whole failure this class note was written about.
    ⭐ A third thread reaps the process and posts the exit code as an event;
    `drain()` collects only once it has arrived.

    ⚠ `popen` is injected on the same seam as `dedupe.trash(sender=...)` and
    `pipeline.sync(reader=...)`. ⭐ And the gui suite drives the REAL CLI for
    its end-to-end checks: `LEDGER-HOT.md` records a whole seam going green
    against an injected double that disagreed with the real object about a
    type, so the double here is used for the shapes a real run cannot produce
    on demand — a crash, a torn line, a hang — and never as the only witness.
    """

    def __init__(self, folder, popen=None, **opts):
        self.folder = folder
        self.opts = opts
        self.argv = argv_for(folder, **opts)
        self._popen = popen or subprocess.Popen
        self._q = queue.Queue()
        self._proc = None
        self._threads = []
        self._rows = []
        self._faults = []
        self._notes = []
        self._eofs = 0
        self._exit = None
        self._finished = None
        self._cancelled = False

    # -- lifecycle ---------------------------------------------------------

    def start(self):
        u"""Spawn. -> self"""
        self._proc = self._popen(
            self.argv,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
            env=child_env(),
            # ⚠ TEXT MODE WITH AN EXPLICIT ENCODING. `LEDGER-HOT.md`: *never
            # open a file without an explicit encoding — a UTF-8 manifest read
            # back with the Windows cp1252 default crashed, in a project whose
            # worst bug is an encoding assumption.* A pipe is a file.
            universal_newlines=True, encoding="utf-8", errors="replace",
            bufsize=1,
            **no_console_kwargs())
        for name, stream in ((u"out", self._proc.stdout),
                             (u"err", self._proc.stderr)):
            self._spawn_thread(self._pump, (name, stream))
        self._spawn_thread(self._reap, ())
        return self

    def _spawn_thread(self, target, args):
        t = threading.Thread(target=target, args=args)
        t.daemon = True
        t.start()
        self._threads.append(t)
        return t

    def _pump(self, which, stream):
        try:
            for line in iter(stream.readline, u""):
                self._q.put((which, line))
        finally:
            try:
                stream.close()
            except (IOError, OSError, ValueError):
                pass
            self._q.put((u"eof", which))

    def _reap(self):
        u"""⭐ THE ONLY PLACE THAT BLOCKS ON THE CHILD, and it is a thread."""
        try:
            code = self._proc.wait()
        except Exception as exc:                          # pragma: no cover
            code = -1
            self._q.put((u"err", u"the child could not be reaped: %s\n" % exc))
        self._q.put((u"exit", code))

    def cancel(self):
        u"""Stop the run. ⭐ A CONTROL, not an offer to operate one.

        ⛔ `terminate`, never `kill`: the CLI's write path is *write first,
        trash second* and `LEDGER-HOT.md` records what happens when only half
        of that runs — *nothing written, the survivor trashed, the user left
        with neither file.* A hard kill mid-plan is exactly that window.

        ⚠ AND THE FLAG REACHES THE `Run`. On Windows a terminated child exits
        **1**, which is indistinguishable from an honest refusal, so a
        cancelled run read back as `3 synced` until this was carried through.
        """
        if self._proc is None:
            raise NotStarted("cancel() before start(): there is no child to "
                             "stop. Call start() first.")
        self._cancelled = True
        if self._proc.poll() is None:
            try:
                self._proc.terminate()
            except OSError:
                pass

    @property
    def cancelled(self):
        return self._cancelled

    # -- reading -----------------------------------------------------------

    def drain(self):
        u"""Whatever has arrived since last time. -> [(kind, payload)]

        Kinds: `row` · `fault` · `note` (a stderr line) · `done` (a `Run`).
        ⛔ NEVER BLOCKS — and that is now structural rather than intended:
        nothing in this method or anything it calls waits on the child.
        """
        events = []
        while True:
            try:
                which, payload = self._q.get_nowait()
            except queue.Empty:
                break
            if which == u"eof":
                self._eofs += 1
            elif which == u"exit":
                self._exit = payload
            elif which == u"err":
                self._notes.append(payload)
                events.append((u"note", payload.rstrip(u"\r\n")))
            else:
                parsed = parse_line(payload)
                if parsed is None:
                    continue
                if isinstance(parsed, Fault):
                    self._faults.append(parsed)
                    events.append((u"fault", parsed))
                else:
                    self._rows.append(parsed)
                    events.append((u"row", parsed))
        # ⚠ BOTH PIPES CLOSED **AND** THE PROCESS REAPED. Either alone is a
        # half-finished run: pipes close early when a grandchild holds none of
        # them, and the exit arrives before EOF when the child dies fast.
        if self._finished is None and self._eofs >= 2 and self._exit is not None:
            events.append((u"done", self._collect()))
        return events

    def _collect(self):
        stderr = u"".join(self._notes)
        # ⭐ THE SUMMARY IS THE LAST NON-EMPTY STDERR LINE, and it is KEPT
        # rather than parsed. It is what a bug report quotes, and what
        # `headline()` DISPLAYS when there are no rows to compose from.
        lines = [l.strip() for l in stderr.splitlines() if l.strip()]
        self._finished = Run(self._rows, self._faults,
                             lines[-1] if lines else u"",
                             stderr, self._exit, self.argv,
                             cancelled=self._cancelled)
        return self._finished

    def finished(self):
        u"""The `Run`, or None while the child is still going."""
        return self._finished

    def wait(self, timeout=None):
        u"""Block until done. ⛔ FOR THE SUITE AND FOR NOTHING ELSE.

        🚨 THE FIRST DRAFT'S `timeout` WENT TO `Thread.join` AND NOWHERE ELSE,
        so `wait(timeout=2)` was still spinning at fifteen seconds — one core
        at 100%, no deadline, and every shipped check passing a timeout it
        never reached. ⛔ It also fell through `all(...)` over an EMPTY thread
        list when called before `start()` — `LEDGER-HOT.md`'s own repeat
        offender, *`all()` over an empty range is True* — into
        `None.wait()`.
        """
        if self._proc is None:
            raise NotStarted("wait() before start(): there is no child to "
                             "wait for. Call start() first.")
        deadline = None if timeout is None else time.time() + timeout
        while self._finished is None:
            self.drain()
            if self._finished is not None:
                break
            if deadline is not None and time.time() >= deadline:
                raise StillRunning(
                    "the CLI has not finished after %.1fs. ⛔ This is not the "
                    "run failing — it is this call giving up on it. The child "
                    "is still going; cancel() it or wait longer." % timeout)
            time.sleep(0.01)
        return self._finished


__all__ = ["Row", "Run", "Runner", "Fault", "NotStarted", "StillRunning",
           "argv_for", "cli_argv", "counts", "parse_line", "child_env",
           "no_console_kwargs", "OUTCOMES", "PARTITION",
           "EXIT_CLEAN", "EXIT_ATTENTION", "EXIT_CANNOT_RUN"]
