# -*- coding: utf-8 -*-
u"""
The GUI's non-visual half. RUNBOOK step 3d. Authority: `05-interface.md`,
`07-test-plan.md` §gui, `LEDGER.md` §Interface.

===========================================================================
🚨 THIS SUITE EXISTS BECAUSE OF TWO REAL DEFECTS, BOTH IN A GUI
===========================================================================

`LEDGER.md` §Interface records them, and this project has now paid for the
lesson four times:

  1. **The GUI painted a run containing refusals green**, because
     *"11 confident, 1 refused"* contains the word `confident`.
  2. **A DPI-aware window clipped its own button off the screen.** Every
     assertion passed; one screenshot showed it immediately.

🚨 **AND AN ADVERSARIAL PASS ON 2026-09-10 REBUILT DEFECT 1 OUT OF FIELDS,
AGAINST 36 GREEN CHECKS AND 32 KILLED MUTANTS.** Every individual number was
right and the sentence was false — a failed write read `1 synced`, a dry run
read `1 synced`, three videos with no subtitle read *"everything here is
already in sync"*, and a cancelled run read `3 synced`. ⭐ **Counting from the
field is necessary and not sufficient. The categories have to PARTITION, and
`CONFIDENT` is not `written`.**

---------------------------------------------------------------------------
⚠ WHAT THIS SUITE STRUCTURALLY CANNOT COVER
---------------------------------------------------------------------------

`07-test-plan.md` is explicit: **macOS UX**, and anything that is a claim
about what a person SEES. A check can assert a window is 2646x1647 and cannot
assert the button is inside it — the same pass proved that by putting a
window reading *"THIS IS SOMEBODY ELSE'S APPLICATION"* past the capture
harness's identity check. That is the screenshot's job, and the reason 3d's
runbook row says *build it, then LOOK at it.*

---------------------------------------------------------------------------
⭐ AND THE DOUBLE IS BUILT FROM THE REAL THING
---------------------------------------------------------------------------

`LEDGER-HOT.md`: *a fake that disagrees with the real thing about a type
measures the fake.* So the end-to-end checks spawn the **real CLI**, and the
fake is used only for the shapes a real run will not produce on demand: a
crash, a torn line, a child whose pipes close while it keeps running.
"""
import io
import json
import os
import subprocess
import sys
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tsubasa.gui import run as RUN                            # noqa: E402
from tsubasa.gui import scale as SCALE                        # noqa: E402
from tsubasa.gui import settings as SETTINGS                  # noqa: E402
from tsubasa.dev import e2ebench as E                         # noqa: E402


# ---------------------------------------------------------------------------
# fixtures -- shaped like `cli.as_json` and nothing else
# ---------------------------------------------------------------------------

def a_record(outcome=u"CONFIDENT", **kw):
    u"""One NDJSON record with EVERY field `cli.as_json` emits.

    ⚠ Built from the real writer's key set, not from what the reader happens
    to touch. ⭐ And `write_failed` is a PARAMETER, not a constant — the first
    draft pinned it to `False`, which is exactly *the fixture held constant
    what the defect varied.*
    """
    raw = {
        u"video": u"/lib/片田舎のおっさん S02E01.mkv",
        u"subtitle": u"/lib/[shincaps] Katainaka - 01 (AT-X).srt",
        u"outcome": outcome,
        u"reason": u"" if outcome == u"CONFIDENT" else u"no subtitle track",
        u"segments": [[None, 0.13]],
        u"offset": 0.13,
        u"match_rate": 0.96,
        u"match_percent": 96,
        u"excess_over_chance": 4.6,
        u"raw_excess": 4.6,
        u"verdict_word": u"locked" if outcome == u"CONFIDENT" else None,
        u"holds_throughout": True,
        u"runtime_check": u"held",
        u"cluster_coherence": None,
        u"dropped_in_gap": 0,
        u"dropped_before_zero": 0,
        u"reference_kind": u"text track",
        u"reference": u"embedded ASS track 2",
        u"output_path": (u"/lib/片田舎のおっさん S02E01.ja.srt"
                         if outcome == u"CONFIDENT" else None),
        u"superseded": [],
        u"lang": u"ja",
        u"lang_tag": u"ja",
        u"forced": False,
        u"write_failed": False,
        u"episode": 1,
        u"notes": [],
    }
    raw.update(kw)
    return raw


def a_row(outcome=u"CONFIDENT", **kw):
    return RUN.Row(a_record(outcome, **kw))


def a_run(rows=(), faults=(), summary=u"", stderr=u"", code=0,
          argv=None, cancelled=False):
    return RUN.Run(list(rows), list(faults), summary, stderr, code,
                   argv or [u"python", u"-m", u"tsubasa", u"--json", u"/lib"],
                   cancelled=cancelled)


class FakeProc(object):
    u"""A `subprocess.Popen` for the shapes a real run will not make on cue.

    ⛔ ITS STREAMS ARE REAL TEXT STREAMS AND ITS EXIT CODE IS A REAL INT.

    🚨 AND THE FIRST DRAFT DISAGREED WITH A REAL `Popen` ANYWAY. `poll()`
    returned the exit code immediately — so a just-spawned child claimed to
    have ALREADY EXITED, `cancel()` correctly declined to terminate something
    it was told was finished, and the check went red against production code
    that was right. A real `Popen.poll()` returns **None while running**.

    ⭐ `wait_delay` models the shape that broke `drain()`: pipes closed, child
    still alive.
    """

    def __init__(self, stdout=u"", stderr=u"", code=0, wait_delay=0.0):
        self.stdout = io.StringIO(stdout)
        self.stderr = io.StringIO(stderr)
        self._code = code
        self._exited = False
        self._wait_delay = wait_delay
        self.terminated = False
        self.argv = None
        self.kwargs = None

    def wait(self, timeout=None):
        if self._wait_delay and not self._exited:
            time.sleep(self._wait_delay)
        self._exited = True
        return self._code

    def poll(self):
        u"""⛔ None WHILE RUNNING. See the class note."""
        return self._code if self._exited else None

    def terminate(self):
        self.terminated = True
        self._exited = True


def fake_popen(stdout=u"", stderr=u"", code=0, box=None, wait_delay=0.0):
    def _popen(argv, **kwargs):
        proc = FakeProc(stdout, stderr, code, wait_delay)
        proc.argv = list(argv)
        proc.kwargs = kwargs
        if box is not None:
            box.append(proc)
        return proc
    return _popen


def ndjson(*records):
    return u"".join(json.dumps(r, ensure_ascii=False) + u"\n"
                    for r in records)


#: Starts a Tk root gets when Tk fails to READ ITS OWN library. See `_tk_root`.
TK_START_ATTEMPTS = 4


def _tk_root():
    u"""A real Tk root — or a skip that tells the truth, or a failure. -> Tk

    ===================================================================
    🚨 IT SKIPPED AS "no display" ON A MACHINE THAT HAS ONE
    ===================================================================

    Every site that made a root caught ANY `TclError` and skipped with
    *"no display"*. On Windows there is always a display, and about one run of
    this file in seven skipped a test anyway — a different test each time.
    The whole message, captured instead of its first line:

        Can't find a usable tk.tcl in the following directories: ...
        couldn't read file "C:/Python310/tcl/tk8.6/ttk/spinbox.tcl":
        no such file or directory

    ⛔ THE FILE EXISTS. Tk's startup sources about thirty of its own `.tcl`
    files, and one open intermittently comes back ENOENT — `init.tcl` one
    time, `ttk/spinbox.tcl` another.

    ⭐ INVESTIGATED 2026-09-16 AND NOT REPRODUCED OUTSIDE THIS FILE: 600 bare
    roots, 600 with a thread churning temp files, 600 with a CPU-bound thread,
    150 real `App` windows, and 400 roots inside pytest with output capture
    on and 400 with it off — 2,750 startups, zero failures, against about one
    in 350 here. Windows Defender's real-time scanning is on, and the next
    root in the same process always starts. So it is transient and
    environmental rather than tsubasa's, and a user's app makes exactly one
    root per launch.

    So a failure to START is RETRIED, and says so with a warning when it had
    to be. Nothing is dressed up as a skip: a missing display skips at once,
    and a start that fails every attempt FAILS with Tcl's own message.

    🚨 THE FIRST VERSION RETRIED ONE MESSAGE, AND CI MET ANOTHER — 0.1.2.
    It retried only *"Can't find a usable"* + *"couldn't read file"*, the
    shape measured here. `windows-latest · py3.10` then failed one test with
    **"Tk could not start (1 attempt)"** while every other root in the same
    job started — transient, a different wording. ⛔ AND ITS TEXT WAS LOST:
    the message put Tcl's words on a second line, and the CI reporter
    annotates only the first line of each failure (deliberately, so the test
    NAMES survive). So every message here is ONE line.
    """
    import warnings
    tk = pytest.importorskip(u"tkinter")
    message = u""
    for attempt in range(1, TK_START_ATTEMPTS + 1):
        try:
            root = tk.Tk()
        except tk.TclError as exc:
            message = u" | ".join(line.strip() for line in
                                  (u"%s" % exc).splitlines() if line.strip())
            if u"display" in message.lower():
                break
            time.sleep(0.05 * attempt)
            continue
        if attempt > 1:
            warnings.warn(u"Tk started on attempt %d, after a transient "
                          u"failure to start: %s" % (attempt, message[:300]))
        return root
    if u"display" in message.lower():
        pytest.skip(u"no display: %s" % message)
    pytest.fail(u"Tk could not start (%d attempt%s): %s"
                % (attempt, u"" if attempt == 1 else u"s", message))


# ⭐ THE HELPER IS AN INSTRUMENT, SO IT IS CHECKED LIKE ONE. Tk's own flake
# cannot be summoned on demand, so these hand `_tk_root` a Tk that fails the
# way Tcl does — and each was watched go red against the helper it guards.

def test_tk_root_RETRIES_a_start_failure_and_says_so_on_one_line(monkeypatch):
    tk = pytest.importorskip(u"tkinter")
    calls, root = [], object()

    def flaky():
        calls.append(1)
        if len(calls) < 3:
            # ⚠ NOT the "couldn't read file" wording the first version keyed
            # on — a start failure worded differently still has to be retried.
            raise tk.TclError(u"Can't find a usable init.tcl in the following "
                              u"directories:\n    {C:/x/tcl/tcl8.6}\n\nThis "
                              u"probably means that Tcl wasn't installed "
                              u"properly.")
        return root

    monkeypatch.setattr(tk, "Tk", flaky)
    monkeypatch.setattr(time, "sleep", lambda seconds: None)
    with pytest.warns(UserWarning) as caught:
        assert _tk_root() is root
    assert len(calls) == 3, calls
    said = u"%s" % caught[0].message
    assert u"attempt 3" in said and u"init.tcl" in said, said
    assert u"\n" not in said, said


def test_tk_root_FAILS_with_Tcls_whole_message_on_the_FIRST_line(monkeypatch):
    u"""🚨 The CI reporter annotates the first line of a failure and nothing
    else. A message whose first line ends *"(1 attempt):"* is a failure nobody
    without credentials can read — which is exactly what CI produced."""
    tk = pytest.importorskip(u"tkinter")
    calls = []

    def broken():
        calls.append(1)
        raise tk.TclError(u'invalid command name "tcl_findLibrary"\n'
                          u'    while executing\n"tcl_findLibrary tk"')

    monkeypatch.setattr(tk, "Tk", broken)
    monkeypatch.setattr(time, "sleep", lambda seconds: None)
    # ⛔ NOT `pytest.raises(pytest.fail.Exception)` alone: were the helper to
    # SKIP — the original defect — the skip would pass straight through it and
    # this check would report as skipped, not failed. A skip is not a pass.
    try:
        _tk_root()
    except pytest.fail.Exception as exc:
        failed = exc
    except pytest.skip.Exception as exc:
        raise AssertionError(u"a failure to start Tk was SKIPPED: %s" % exc.msg)
    else:
        raise AssertionError(u"a Tk that never starts produced no failure")
    assert len(calls) == TK_START_ATTEMPTS, calls
    first = (u"%s" % failed.msg).splitlines()[0]
    assert u"%d attempts" % TK_START_ATTEMPTS in first, first
    assert u"tcl_findLibrary" in first and u"while executing" in first, first


def test_tk_root_SKIPS_at_once_for_a_missing_display(monkeypatch):
    tk = pytest.importorskip(u"tkinter")
    calls = []

    def headless():
        calls.append(1)
        raise tk.TclError(u"no display name and no $DISPLAY environment "
                          u"variable")

    monkeypatch.setattr(tk, "Tk", headless)
    with pytest.raises(pytest.skip.Exception) as skipped:
        _tk_root()
    assert len(calls) == 1, calls
    assert u"$DISPLAY" in (u"%s" % skipped.value.msg), skipped.value.msg


# ===========================================================================
# CONSTRAINT 4 -- what the glance line claims
# ===========================================================================

def test_counts_come_from_the_outcome_FIELD_not_from_the_summary_prose():
    u"""🚨 THE ORIGINAL DEFECT, REPRODUCED AS A CHECK.

    The stderr summary below is EXACTLY the string `LEDGER.md` §Interface
    names: it contains the word `confident`, and a refusal is in the run.
    """
    rows = [a_row() for _ in range(11)] + [a_row(u"REFUSED")]
    run = a_run(rows, summary=u"11 confident, 1 refused",
                stderr=u"11 confident, 1 refused\n", code=1)

    assert u"confident" in run.summary          # the trap is present
    assert run.counts[u"refused"] == 1
    assert run.counts[u"confident"] == 11
    assert run.needs_attention is True


def test_the_five_categories_PARTITION_the_rows():
    u"""🚨 COUNTING FROM THE FIELD IS NOT ENOUGH — THE SECOND DEFECT.

    `cut` is a SUBSET of `confident`. A footer printing both read
    `✓ 8 synced  ⚑ 1 repaired  ✗ 1 refused  ! 1 error` — **eleven, over ten
    files** — while another panel in the same window said `7 synced cleanly`.
    Every individual number was right.
    """
    rows = ([a_row() for _ in range(7)]
            + [a_row(segments=[[222.4, -33.07], [None, -42.96]])]
            + [a_row(u"REFUSED"), a_row(u"ERROR")])
    run = a_run(rows, code=1)

    assert run.partitions is True
    assert sum(run.counts[k] for k in RUN.PARTITION) == len(rows) == 10
    assert run.counts[u"clean"] == 7
    assert run.counts[u"cut"] == 1
    assert run.counts[u"confident"] == 8          # the convenience total
    # ⛔ AND THE HEADLINE MAY NOT ADD THE SUBSET TO THE WHOLE.
    assert u"8 synced" in run.headline()
    assert u"9 synced" not in run.headline()


def test_the_headline_names_what_is_WRONG_before_what_worked():
    u"""`05-interface.md`: *the one thing needing attention must not sit below
    23 successes.* The same ordering, one line long."""
    run = a_run([a_row() for _ in range(8)] + [a_row(u"REFUSED"),
                                               a_row(u"ERROR")], code=1)
    head = run.headline()
    assert head.index(u"error") < head.index(u"synced")
    assert head.index(u"refused") < head.index(u"synced")


def test_a_reason_containing_the_word_confident_moves_no_count():
    u"""⚠ THE FIELD IS NOT THE ONLY PLACE THE WORD APPEARS."""
    run = a_run([a_row(u"REFUSED",
                       reason=u"the first 3:42 are confidently a different "
                              u"offset — a broadcast cut")], code=1)
    assert run.counts[u"confident"] == 0
    assert run.counts[u"refused"] == 1


# ===========================================================================
# 🚨 A CONFIDENT ROW IS NOT A WRITTEN FILE -- three ways
# ===========================================================================

def test_a_write_that_FAILED_is_never_reported_as_synced():
    u"""🚨 THE WORST FINDING OF THE ADVERSARIAL PASS.

    `pipeline` leaves `outcome` at CONFIDENT when a write fails — deliberately,
    because the ALIGNMENT was confident — and sets `write_failed`. The CLI said
    `1 NOT WRITTEN · 0 synced`; the first draft of the GUI said **`1 synced`**
    with `needs_attention` False. Measured against a real run.
    """
    run = a_run([a_row(write_failed=True, output_path=None,
                       reason=u"⛔ NOT WRITTEN: the name is a directory")],
                code=1)
    assert run.counts[u"write_failed"] == 1
    assert run.counts[u"landed"] == 0
    assert run.needs_attention is True
    head = run.headline()
    assert u"NOT written" in head
    assert head.index(u"NOT written") < head.index(u"synced")


def test_a_dry_run_says_WOULD_sync_and_never_synced():
    u"""🚨 THE GUI'S OWN PREVIEW MODE REPORTED A WRITE.

    `--dry-run` moves not one byte, and `07-test-plan.md`'s end-to-end checks
    all run in it — so this is the mode the suite exercises most and the one
    the first draft described wrongly. ⭐ Read off the ARGV, which is the only
    record of what was actually asked for.
    """
    argv = [u"python", u"-m", u"tsubasa", u"--json", u"--dry-run", u"/lib"]
    run = a_run([a_row()], code=0, argv=argv)
    assert run.dry_run is True
    assert u"1 would sync" in run.headline()
    assert u"1 synced" not in run.headline()

    wet = a_run([a_row()], code=0)
    assert wet.dry_run is False
    assert u"1 synced" in wet.headline()


def test_a_cancelled_run_is_never_a_clean_success():
    u"""🚨 On Windows a terminated child exits **1**, which is exactly what an
    honest refusal exits. The first draft read a cancelled run as `3 synced`,
    because `_cancelled` lived on the `Runner` and never reached the `Run`."""
    run = a_run([a_row(), a_row(), a_row()], code=1, cancelled=True)
    assert run.cancelled is True
    assert run.needs_attention is True
    assert u"stopped" in run.headline()
    assert not run.headline().startswith(u"3 synced")


def test_three_states_of_one_folder_do_not_share_a_headline():
    u"""⭐ THE CHECK THAT WOULD HAVE CAUGHT ALL THREE AT ONCE. A real write,
    a preview, and a write that failed each said `1 synced`."""
    landed = a_run([a_row()], code=0)
    preview = a_run([a_row(output_path=None)], code=0,
                    argv=[u"python", u"-m", u"tsubasa", u"--json",
                          u"--dry-run", u"/lib"])
    failed = a_run([a_row(write_failed=True, output_path=None)], code=1)

    heads = {landed.headline(), preview.headline(), failed.headline()}
    assert len(heads) == 3, u"three different states, %d sentences: %s" \
                            % (len(heads), heads)


def test_a_forced_write_is_REFUSED_and_still_counts_as_refused():
    u"""`05-interface.md`: *a forced write is reported as REFUSED and it does
    write.* ⛔ The count follows the outcome, not the bytes."""
    run = a_run([a_row(u"REFUSED", forced=True,
                       output_path=u"/lib/x.ja.srt")], code=1)
    assert run.counts[u"refused"] == 1
    assert run.counts[u"confident"] == 0
    assert run.counts[u"forced"] == 1
    assert run.counts[u"landed"] == 1


def test_superseded_files_are_counted_and_said_out_loud():
    u"""⚠ `12 synced` over twelve files that went to the trash is a true
    sentence and an incomplete one. The CLI prints the trash line; the GUI's
    one-line summary omitted it entirely."""
    run = a_run([a_row(superseded=[u"/lib/a.srt", u"/lib/b.srt"]),
                 a_row(superseded=[u"/lib/c.srt"])], code=0)
    assert run.counts[u"superseded"] == 3
    assert u"3 superseded" in run.headline()


def test_a_cut_result_is_CONFIDENT_and_is_also_counted_as_repaired():
    cut = a_row(segments=[[222.4, -33.07], [None, -42.96]])
    run = a_run([cut, a_row()])
    assert cut.is_cut is True
    assert run.counts[u"cut"] == 1
    assert run.counts[u"clean"] == 1
    assert run.counts[u"confident"] == 2
    assert run.needs_attention is False


# ===========================================================================
# the outcomes that read as failure and are not -- and the one that reads as
# success and is not
# ===========================================================================

def test_exit_1_is_a_REFUSAL_and_not_a_broken_command():
    run = a_run([a_row(u"REFUSED")], code=RUN.EXIT_ATTENTION)
    assert run.could_not_run is False
    assert run.needs_attention is True


def test_exit_2_is_the_only_could_not_run_and_it_says_why():
    run = a_run(code=RUN.EXIT_CANNOT_RUN,
                stderr=u"--out and --no-rename contradict each other.\n")
    assert run.could_not_run is True
    assert run.headline().startswith(u"--out and --no-rename")


def test_exit_2_never_shows_the_tools_TAGLINE_as_the_error():
    u"""🚨 `cli.main` writes the WHOLE usage block to stderr when it is left
    with no folder, and `splitlines()[0]` of that is
    *"tsubasa — pair subtitles to videos and retime them to match."* — the
    tagline, presented as the reason the command failed."""
    usage = (u"tsubasa — pair subtitles to videos and retime them to match.\n"
             u"\n"
             u"  tsubasa <folder>\n"
             u"  tsubasa <folder> --subs <folder>\n"
             u"\n"
             u"  --dry-run     measure everything, write nothing\n")
    run = a_run(code=RUN.EXIT_CANNOT_RUN, stderr=usage)
    head = run.headline()
    assert u"pair subtitles to videos" not in head
    assert u"no folder" in head


def test_no_rows_QUOTES_the_cli_instead_of_claiming_the_folder_is_finished():
    u"""🚨 THREE STATES SHARE A ROW COUNT OF ZERO, AND ONLY ONE IS GOOD NEWS.

    `--json` emits **no record** for an unpaired video — `03-permissions.md`
    says there is no fourth outcome — and `cli.main` exits 0 because unpaired
    is none of failed/errored/refused. So three videos with no subtitle at all
    came back as *"everything here is already in sync"*.

    ⭐ The GUI is structurally blind here. Displaying the CLI's own sentence
    is not the banned thing; DECIDING from it is.
    """
    unpaired = a_run(code=0,
                     stderr=u"3 videos with no subtitle · 0 would sync\n",
                     summary=u"3 videos with no subtitle · 0 would sync")
    settled = a_run(code=0, stderr=u"24 already in sync — nothing to do\n",
                    summary=u"24 already in sync — nothing to do")

    assert unpaired.no_rows is True and settled.no_rows is True
    assert unpaired.headline() != settled.headline()
    assert u"no subtitle" in unpaired.headline()
    assert u"already in sync" in settled.headline()
    assert u"already in sync" not in unpaired.headline()


def test_stderr_is_an_information_channel_and_not_an_error_signal():
    run = a_run([a_row()], stderr=u"1 synced\n", code=RUN.EXIT_CLEAN)
    assert run.stderr
    assert run.needs_attention is False


# ===========================================================================
# reading the child
# ===========================================================================

def test_a_torn_line_is_a_FAULT_and_is_never_silently_dropped():
    parsed = RUN.parse_line(u'{"outcome": "CONFI')
    assert isinstance(parsed, RUN.Fault)
    assert u'{"outcome": "CONFI' in parsed.text


def test_valid_json_that_is_not_a_result_is_also_a_fault():
    assert isinstance(RUN.parse_line(u'{"hello": 1}'), RUN.Fault)
    assert isinstance(RUN.parse_line(u'["a", "b"]'), RUN.Fault)
    assert isinstance(RUN.parse_line(u'"just a string"'), RUN.Fault)


@pytest.mark.parametrize("outcome", [u"confident", u"CONFIDENT ", u"SKIPPED",
                                     None, 1, u""])
def test_an_outcome_this_reader_does_not_know_is_a_FAULT_not_a_silent_row(
        outcome):
    u"""🚨 A ROW NOBODY COUNTS IS A ROW THAT VANISHED FROM THE SCREEN.

    The first draft accepted any dict carrying an `outcome` key and kept no
    residual, so a case change, a trailing space or a fourth label produced
    `rows=1 counted=0 headline='0 synced'` with nothing saying so — *eight
    rows for a nine-result run*, one field further in than `Fault` reached.
    ⛔ `03-permissions.md`: there are THREE outcomes.
    """
    parsed = RUN.parse_line(json.dumps({u"outcome": outcome}))
    assert isinstance(parsed, RUN.Fault), u"%r parsed as a row" % outcome
    assert u"outcome" in parsed.why


def test_blank_lines_are_not_faults():
    assert RUN.parse_line(u"") is None
    assert RUN.parse_line(u"   \n") is None


def test_a_faulted_line_forces_attention_even_when_every_row_is_confident():
    run = a_run([a_row(), a_row()],
                faults=[RUN.Fault(u"unreadable", u"{oops")], code=0)
    assert run.needs_attention is True
    assert u"could not be read" in run.headline()


def test_output_that_could_not_be_READ_is_not_a_quiet_folder():
    u"""🚨 ZERO ROWS AND A FAULT IS THE WORST OF THE THREE ZERO-ROW STATES,
    and `no_rows` must not swallow it: the CLI printed something, this layer
    could not read it, and *"nothing to do"* over that is a guess dressed as
    a result.

    ⭐ Added because a mutant reading `no_rows` as `not self.rows` survived —
    every existing check had rows in it, so none could see it.
    """
    run = a_run(faults=[RUN.Fault(u"unreadable", u"{oops")],
                code=0, summary=u"24 already in sync — nothing to do",
                stderr=u"24 already in sync — nothing to do\n")
    assert run.rows == ()
    assert run.no_rows is False
    assert run.needs_attention is True
    assert u"could not be read" in run.headline()
    assert u"already in sync" not in run.headline()


def test_a_Run_freezes_its_rows_so_counts_and_no_rows_cannot_diverge():
    u"""⛔ `_collect` used to pass the `Runner`'s own list object. `counts` is
    computed once in `__init__` and `no_rows` re-reads `self.rows`, so a live
    alias is two answers to one question waiting to disagree — measured at
    `0 synced` beside a row list of length 1."""
    rows = [a_row()]
    run = a_run(rows)
    rows.append(a_row(u"REFUSED"))
    assert isinstance(run.rows, tuple)
    assert len(run.rows) == 1
    assert run.partitions is True


def test_a_row_for_an_unpaired_video_has_a_name_and_does_not_raise():
    row = a_row(u"ERROR", subtitle=None, output_path=None)
    assert row.name == u"片田舎のおっさん S02E01.mkv"
    assert row.written_name == u""


def test_a_missing_field_raises_AttributeError_not_KeyError():
    row = a_row()
    with pytest.raises(AttributeError):
        row.a_field_the_cli_has_never_emitted
    assert getattr(row, u"a_field_the_cli_has_never_emitted", u"—") == u"—"


# ===========================================================================
# CONSTRAINT 2 -- shelling out
# ===========================================================================

def test_every_command_carries_json_because_the_counts_depend_on_it():
    for opts in ({}, {u"dry_run": True}, {u"keep_all": True},
                 {u"verbose": True, u"recurse": False}):
        assert u"--json" in RUN.argv_for(u"/lib", **opts)


def test_the_folder_is_the_LAST_argument_and_is_made_ABSOLUTE():
    u"""🚨 `cli.parse` reads any token starting with `-` as a flag, and with
    no roots left `cli.main` prints its whole usage block. A relative folder
    named `--json` came back as exit 2 whose first stderr line was the tool's
    tagline. An absolute path cannot start with a dash."""
    argv = RUN.argv_for(u"--json")
    assert argv[-1] == os.path.abspath(u"--json")
    assert not argv[-1].startswith(u"-")

    argv = RUN.argv_for(u"Show", subs=u"downloads")
    assert os.path.isabs(argv[-1])
    assert os.path.isabs(argv[argv.index(u"--subs") + 1])


def test_a_blank_folder_is_refused_here_with_a_sentence():
    u"""⭐ `doctrine/architecture`: *instruction, not refusal.*"""
    for blank in (None, u"", u"   "):
        with pytest.raises(ValueError) as exc:
            RUN.argv_for(blank)
        assert u"Browse" in str(exc.value)


def test_force_on_a_FOLDER_is_refused_here_and_not_discovered_by_the_user():
    u"""⛔ `sync()` raises on `force` over a scan and `cli.main` exits 2 —
    *writing the best of several REFUSED candidates, which is the one thing
    the ranking exists as a gate to prevent.* `argv_for` used to build that
    command happily, so a control offering it would always fail."""
    with pytest.raises(ValueError) as exc:
        RUN.argv_for(u"/lib", force=True)
    assert u"explicit pair" in str(exc.value)


def test_the_defaults_add_no_flags_beyond_json():
    argv = RUN.argv_for(u"/lib")
    assert u"--no-recurse" not in argv
    assert u"--no-rename" not in argv
    assert u"--no-results" not in argv
    assert argv.count(u"--json") == 1


def test_the_child_gets_utf8_and_a_pythonpath_that_does_not_depend_on_cwd():
    env = RUN.child_env({u"PATH": u"/usr/bin"})
    assert env[u"PYTHONIOENCODING"] == u"utf-8"
    assert os.path.isdir(os.path.join(env[u"PYTHONPATH"].split(os.pathsep)[0],
                                      u"tsubasa"))

    # 🚨 AND WITH ONE ALREADY SET, WHICH THE FIRST DRAFT NEVER EXERCISED. A
    # mutant that dropped the package whenever the variable already had a
    # value SURVIVED, because the empty case makes both branches identical.
    kept = RUN.child_env({u"PYTHONPATH": u"/somebody/elses/libs"})
    parts = kept[u"PYTHONPATH"].split(os.pathsep)
    assert os.path.isdir(os.path.join(parts[0], u"tsubasa"))
    assert u"/somebody/elses/libs" in parts


@pytest.mark.skipif(not sys.platform.startswith("win"),
                    reason=u"CREATE_NO_WINDOW is a Windows flag")
def test_no_console_window_flashes_over_the_app():
    kw = RUN.no_console_kwargs()
    assert kw[u"creationflags"] & 0x08000000
    assert kw[u"startupinfo"].dwFlags & subprocess.STARTF_USESHOWWINDOW


def test_the_spawn_actually_passes_the_no_window_flags_to_popen():
    u"""⚠ THE FLAG EXISTING IS NOT THE FLAG BEING USED."""
    box = []
    RUN.Runner(u"/lib", popen=fake_popen(box=box)).start()
    proc = box[0]
    if sys.platform.startswith("win"):
        assert proc.kwargs[u"creationflags"] & 0x08000000
    assert proc.kwargs[u"encoding"] == u"utf-8"
    assert proc.kwargs[u"errors"] == u"replace"
    assert proc.kwargs[u"env"][u"PYTHONIOENCODING"] == u"utf-8"


def test_TSUBASA_CLI_overrides_how_the_cli_is_invoked(monkeypatch):
    monkeypatch.setenv(u"TSUBASA_CLI", json.dumps([u"/bin/false", u"--x"]))
    assert RUN.cli_argv() == [u"/bin/false", u"--x"]
    monkeypatch.setenv(u"TSUBASA_CLI", u"/bin/false")
    assert RUN.cli_argv() == [u"/bin/false"]


@pytest.mark.parametrize("value", [u"[shincaps]/tsubasa", u'["a"', u"[]",
                                   u"[1, 2]", u"[null]"])
def test_a_TSUBASA_CLI_that_is_not_a_json_list_never_raises(monkeypatch,
                                                            value):
    u"""🚨 HALF THIS CORPUS'S RELEASE GROUPS ARE NAMED `[something]`.

    *"starts with a bracket, therefore JSON"* turned an ordinary directory
    into a `JSONDecodeError` raised out of `Runner.__init__` — and `[]` and
    `[1, 2]` produced argv lists that would hand ints to `Popen`.
    """
    monkeypatch.setenv(u"TSUBASA_CLI", value)
    argv = RUN.cli_argv()
    assert argv, u"%r produced an empty command" % value
    assert all(isinstance(x, str) for x in argv), argv


# ===========================================================================
# the event loop must never be waited on
# ===========================================================================

def test_drain_never_blocks_even_when_the_pipes_close_before_the_child_dies():
    u"""🚨 MEASURED AT 20.00 SECONDS INSIDE ONE `drain()` CALL.

    Both pipes reaching EOF is not the process exiting — a grandchild
    (ffprobe, a wrapper) that outlives the CLI holds none of them open. The
    first draft's `drain()` called `_collect()`, whose first line was
    `self._proc.wait()`, so the function whose docstring says ⛔ NEVER BLOCKS
    froze the window for the child's whole remaining life.
    """
    runner = RUN.Runner(u"/lib", popen=fake_popen(
        stdout=ndjson(a_record()), stderr=u"1 synced\n", code=0,
        wait_delay=1.5))
    runner.start()

    slowest = 0.0
    for _ in range(6):
        began = time.time()
        runner.drain()
        slowest = max(slowest, time.time() - began)
        time.sleep(0.05)
    assert slowest < 0.25, u"a drain() call took %.2fs" % slowest


def test_the_run_is_not_collected_until_the_child_has_been_REAPED():
    u"""🚨 BOTH PIPES CLOSING IS NOT THE PROCESS EXITING.

    A grandchild that outlives the CLI holds neither pipe, so EOF arrives
    while the child is still running and its exit code does not exist yet.
    Collecting there produces a `Run` whose `code` is `None` — every
    interpretation of which (`could_not_run`, `needs_attention`) is then a
    guess about a run that had not finished.

    ⭐ Added because a mutant dropping the *"and the exit code has arrived"*
    half of the guard survived: against a double that dies instantly, EOF and
    exit land in the same `drain()` sweep and the guard is unobservable.
    """
    runner = RUN.Runner(u"/lib", popen=fake_popen(
        stdout=ndjson(a_record()), stderr=u"1 synced\n", code=2,
        wait_delay=0.6))
    runner.start()

    began = time.time()
    while runner.finished() is None and time.time() - began < 5:
        runner.drain()
        early = runner.finished()
        if early is not None:
            break
        time.sleep(0.02)

    run = runner.finished()
    assert run is not None, u"never collected"
    assert run.code == 2, \
        u"collected with code %r — the child had not been reaped" % run.code
    assert run.could_not_run is True


def test_wait_honours_its_timeout_and_says_the_run_is_still_going():
    u"""🚨 `timeout` went to `Thread.join` and nowhere else, so
    `wait(timeout=2)` was still spinning at fifteen seconds — one core at
    100%, no deadline. Every shipped check passed a timeout it never reached,
    so all of them were green."""
    runner = RUN.Runner(u"/lib", popen=fake_popen(wait_delay=5.0))
    runner.start()
    began = time.time()
    with pytest.raises(RUN.StillRunning) as exc:
        runner.wait(timeout=0.3)
    elapsed = time.time() - began
    assert elapsed < 2.0, u"wait(0.3) took %.2fs" % elapsed
    assert u"not the run failing" in str(exc.value)


def test_wait_or_cancel_before_start_says_so_instead_of_raising_AttributeError():
    u"""⛔ `LEDGER-HOT.md`'s own repeat offender, live in the new file:
    `all()` over an EMPTY thread list is True, so `wait()` fell through the
    guard into `None.wait()`."""
    runner = RUN.Runner(u"/lib", popen=fake_popen())
    with pytest.raises(RUN.NotStarted):
        runner.wait(timeout=1)
    with pytest.raises(RUN.NotStarted):
        runner.cancel()


def test_cancel_terminates_and_never_kills():
    u"""⛔ *Write first, trash second is an ORDER, not a condition.* A hard
    kill mid-plan leaves the user with neither file."""
    # ⚠ `wait_delay` KEEPS THE CHILD ALIVE. Without it the reaper thread
    # reaps the double instantly, `poll()` stops returning None, and `cancel()`
    # correctly declines to terminate something already finished — a green
    # check for the wrong reason, and a red one for a right implementation.
    box = []
    runner = RUN.Runner(u"/lib", popen=fake_popen(box=box, wait_delay=2.0))
    runner.start()
    runner.cancel()
    assert box[0].terminated is True
    assert runner.cancelled is True


def test_the_cancelled_flag_reaches_the_Run():
    runner = RUN.Runner(u"/lib", popen=fake_popen(
        stdout=ndjson(a_record()), stderr=u"1 synced\n", code=1))
    runner.start()
    runner.cancel()
    run = runner.wait(timeout=5)
    assert run.cancelled is True
    assert run.needs_attention is True


def test_a_child_that_writes_nothing_and_dies_still_produces_a_Run():
    runner = RUN.Runner(u"/lib", popen=fake_popen(stdout=u"", stderr=u"",
                                                  code=2))
    runner.start()
    run = runner.wait(timeout=5)
    assert run is not None
    assert run.could_not_run is True
    assert run.rows == ()


def test_a_run_is_assembled_from_the_streams_in_order():
    stdout = ndjson(a_record(u"REFUSED"), a_record(), a_record())
    # 🚨 MORE THAN ONE STDERR LINE, DELIBERATELY. A single line makes *first*
    # and *last* the same string, and a mutant taking `lines[0]` survived a
    # check named after the summary.
    runner = RUN.Runner(u"/lib", popen=fake_popen(
        stdout=stdout,
        stderr=u"note: ffmpeg not found, using the native reader\n"
               u"\n"
               u"2 synced, 1 refused\n",
        code=1))
    runner.start()
    run = runner.wait(timeout=5)
    assert [r.outcome for r in run.rows] == [u"REFUSED", u"CONFIDENT",
                                             u"CONFIDENT"]
    assert run.summary == u"2 synced, 1 refused"
    assert u"ffmpeg not found" in run.stderr
    assert run.counts[u"refused"] == 1


# ===========================================================================
# CONSTRAINT 3 -- DPI
# ===========================================================================

#: The build machine, measured 2026-09-09. ⭐ A CONSTANT WITH A PROVENANCE:
#: `test_FakeRoot_still_describes_THIS_machine` is what stops it drifting into
#: fiction the day the display changes.
BUILD_DPI = 239.62264150943398
BUILD_SCREEN = (3000, 2000)
#: The window frame on this machine: 16 px of border a side, a 72 px caption
#: (which already includes the top border), so 32 px wide and 88 px tall in
#: total. ⛔ Real pixels already — they do NOT go through `px()`.
#: ⚠ The first draft recorded `(16, 72)` — one border, and the TOP offset
#: mistaken for the whole vertical chrome. 16 px short, in the direction that
#: makes `fits()` optimistic. Caught by `measure_chrome` disagreeing with
#: `window_chrome` on its first run.
BUILD_CHROME = (32, 88)


class FakeRoot(object):
    u"""A double for a `tk.Tk`, holding the build machine's real numbers."""

    def __init__(self, dpi=BUILD_DPI, screen=BUILD_SCREEN):
        self._dpi = dpi
        self._screen = screen
        self.geometry_calls = []
        self.min = None
        self.max = None

    def winfo_fpixels(self, _):
        return self._dpi

    def winfo_screenwidth(self):
        return self._screen[0]

    def winfo_screenheight(self):
        return self._screen[1]

    def geometry(self, spec=None):
        # ⚠ A REAL `geometry()` IS DUAL-PURPOSE: with no argument it RETURNS
        # the current string. A double that only records would `TypeError`,
        # or worse, log a getter as a setter.
        if spec is None:
            return self.geometry_calls[-1] if self.geometry_calls else u"1x1+0+0"
        self.geometry_calls.append(spec)

    def minsize(self, w, h):
        # ⚠ A real `minsize` raises TclError on a float.
        if isinstance(w, float) or isinstance(h, float):
            raise ValueError('expected integer but got "%s"' % w)
        self.min = (w, h)

    def maxsize(self, w, h):
        if isinstance(w, float) or isinstance(h, float):
            raise ValueError('expected integer but got "%s"' % w)
        self.max = (w, h)


def a_scale(dpi=BUILD_DPI, screen=BUILD_SCREEN, area=None,
            chrome=BUILD_CHROME):
    u"""⭐ `area` and `chrome` are INJECTED so the arithmetic checks are about
    the arithmetic. The real system values get their own checks below."""
    return SCALE.Scale(FakeRoot(dpi, screen), dpi=dpi, screen=screen,
                       area=area or (0, 0, screen[0], screen[1]),
                       chrome=chrome)


def test_the_build_machines_own_dpi_is_two_and_a_half_times_nominal():
    s = a_scale()
    assert round(s.ratio, 3) == 2.496
    assert s.px(12) == 30
    assert s.px(1) == 2


def test_geometry_scales_all_four_numbers_not_just_the_size():
    assert a_scale().window(1060, 660, 40, 40) == u"2646x1647+100+100"


def test_fits_counts_the_TITLE_BAR_AND_BORDERS_it_does_not_own():
    u"""🚨 OPTIMISTIC BY 88 PX, AND IT SAID YES TO A WINDOW 85 PX OFF THE
    BOTTOM. `wm geometry` sizes the CLIENT and positions the FRAME. The first
    draft added a requested origin to a client size and counted neither."""
    s = a_scale()
    assert s.frame(1060, 660) == (2646 + 32, 1647 + 88)
    # 1060x740: client bottom 2019 with the frame -> off a 2000 px screen.
    assert s.fits(1060, 740) is False
    assert s.fits(1060, 660) is True
    # ⭐ The check that kills a `fits` with the chrome term deleted.
    naive = SCALE.Scale(FakeRoot(), dpi=BUILD_DPI, screen=BUILD_SCREEN,
                        area=(0, 0, 3000, 2000), chrome=(0, 0))
    assert naive.fits(1060, 740) is True, \
        u"the fixture must be one where the chrome term CHANGES the verdict"


def test_fits_uses_the_WORK_AREA_and_not_the_whole_screen():
    u"""⚠ A taskbar at this scale is ~110 real pixels — more than the margin
    the shipped window was designed with."""
    full = a_scale(area=(0, 0, 3000, 2000))
    taskbar = a_scale(area=(0, 0, 3000, 1890))
    assert full.fits(1060, 700) is True
    assert taskbar.fits(1060, 700) is False


def test_the_ORIGIN_is_part_of_the_verdict():
    u"""🚨 A `fits()` WITH THE ORIGIN TERM DELETED SURVIVED EVERY CHECK,
    because the fixture's `x=40,y=40` is 100 real px — too small to flip
    either verdict. The fixture has to be one where the origin decides."""
    s = a_scale()
    assert s.fits(1060, 660, x=40, y=40) is True
    # ⚠ BOTH AXES. A mutant that dropped the origin from the WIDTH term alone
    # survived a check whose only failing case tripped the HEIGHT term.
    assert s.fits(1060, 660, x=40, y=150) is False, u"the y origin must count"
    assert s.fits(1060, 660, x=300, y=40) is False, u"the x origin must count"


def test_pin_makes_the_size_a_constraint_the_manager_cannot_improve_on():
    u"""⛔ `geometry()` alone lost to the geometry manager and a window asked
    for 1647 px came back 1089 — which passes *"does it fit"* by
    construction, because it SHRANK rather than overflowed."""
    root = FakeRoot()
    s = a_scale()
    pin = s.pin(root, 1060, 660)
    assert tuple(pin) == (2646, 1647)
    assert pin.clamped is False
    assert root.min == (2646, 1647)
    assert root.max == root.min
    assert root.geometry_calls == [u"2646x1647+100+100"]
    # ⚠ A real `minsize` raises on a float; these must be ints.
    assert isinstance(root.min[0], int) and isinstance(root.min[1], int)


def test_pin_CONSULTS_fits_and_will_not_hang_a_window_off_the_desktop():
    u"""🚨 `pin(root, 1060, 1200)` produced a real **2646x2995** window on a
    2000-px screen — unresizable because `min == max`, unmaximisable, and with
    no scrollbar. The clipping defect this module exists to prevent,
    mechanically guaranteed by the module."""
    root = FakeRoot()
    s = a_scale()
    assert s.fits(1060, 1200) is False

    pin = s.pin(root, 1060, 1200)
    assert pin.clamped is True
    assert pin.asked == (1060, 1200)
    assert pin.height < s.px(1200)
    assert root.max[1] <= 2000, u"pinned %r on a 2000 px screen" % (root.max,)
    assert s.fits(*pin.asked) is False and s.fits(
        pin.width / s.ratio, pin.height / s.ratio) is True
    assert u"clamped" in pin.why

    with pytest.raises(ValueError):
        s.pin(FakeRoot(), 1060, 1200, clamp=False)


def test_dpi_awareness_reports_the_level_the_SYSTEM_says_not_the_call_it_made():
    u"""🚨 THE FIRST DRAFT RETURNED THE NAME OF WHAT "WORKED".

    Called after `Tk()` it still said `shcore.SetProcessDpiAwareness(1)` while
    `Scale` went on to read **95.8 dpi on a 1200x800 screen** — every number
    in the process wrong. A mutant whose body called nothing and returned the
    same string survived all six DPI checks, because the only assertion was
    that a non-empty string came back.

    ⭐ `doctrine/evidence` §*read-backs*: ask the system what it ended up with.
    """
    state = SCALE.make_process_dpi_aware()
    assert isinstance(state, SCALE.Awareness)
    assert state.call
    if sys.platform.startswith("win"):
        assert state.level == SCALE.dpi_awareness_level()
        assert state.aware is True, state.note
    else:
        assert state.level is None


def test_make_process_dpi_aware_is_reachable_from_the_package():
    u"""⚠ The one function that must run FIRST was the one a caller had to
    reach into a submodule for, while `Scale` — useless without it — sat on
    the package."""
    import tsubasa.gui as G
    assert G.make_process_dpi_aware is SCALE.make_process_dpi_aware
    assert G.Scale is SCALE.Scale


@pytest.mark.skipif(not sys.platform.startswith("win"),
                    reason=u"needs a display")
def test_FakeRoot_still_describes_THIS_machine():
    u"""🚨 THE CHECK THAT STOPS `BUILD_DPI` BECOMING FICTION.

    The first draft's *"agrees with a REAL Tk root"* check re-derived all
    three assertions from the `Scale` object itself — a root reporting **1.0
    dpi on a 1x1 screen** passed every one. Nothing compared the double's
    constant to what the machine actually reports, so the day the display
    changed both would stay green and diverge.
    """
    root = _tk_root()
    try:
        real = SCALE.Scale(root)
        if abs(real.dpi - BUILD_DPI) > 0.5:
            pytest.skip(
                u"this is not the machine the constants were measured on "
                u"(%.1f dpi here, %.1f recorded). ⭐ Re-measure and update "
                u"BUILD_DPI/BUILD_SCREEN/BUILD_CHROME rather than widening "
                u"this check." % (real.dpi, BUILD_DPI))
        assert (root.winfo_screenwidth(),
                root.winfo_screenheight()) == BUILD_SCREEN
        assert real.px(1060) == a_scale().px(1060)
    finally:
        root.destroy()


@pytest.mark.skipif(not sys.platform.startswith("win"),
                    reason=u"needs a display")
def test_the_chrome_FORMULA_agrees_with_a_MEASURED_window():
    u"""⭐ `doctrine/architecture`: *fit by MEASURING, never by calculating.*
    `window_chrome()` is the cheap formula; this is the instrument that
    disagrees with it when it is wrong."""
    root = _tk_root()
    try:
        root.geometry(u"400x300+120+120")
        root.update_idletasks()
        root.update()
        measured = SCALE.measure_chrome(root)
        formula = SCALE.window_chrome()
        assert abs(measured[0] - formula[0]) <= 4, \
            u"border: measured %r, formula %r" % (measured, formula)
        assert abs(measured[1] - formula[1]) <= 4, \
            u"caption: measured %r, formula %r" % (measured, formula)
    finally:
        root.destroy()


@pytest.mark.skipif(not sys.platform.startswith("win"),
                    reason=u"needs Windows")
def test_the_work_area_is_real_and_no_larger_than_the_screen():
    area = SCALE.work_area(BUILD_SCREEN)
    assert area[2] - area[0] > 0 and area[3] - area[1] > 0
    assert area[2] <= BUILD_SCREEN[0] and area[3] <= BUILD_SCREEN[1]


# ===========================================================================
# THE SETTINGS -- ruled 2026-09-10
# ===========================================================================

def test_the_ruled_defaults_are_the_defaults(tmp_path):
    u"""⭐ SONIC'S WORDS: *auto-run on drop unless setting is toggled. Write
    without confirm unless reckless toggled in settings.*"""
    s = SETTINGS.Settings({}, str(tmp_path / u"s.json"))
    assert s.get(u"auto_run_on_drop") is True
    assert s.confirm_before_writing() is False
    assert s.reckless_active() == []
    # ⛔ And nothing in the reckless group is on.
    for option in SETTINGS.SCHEMA:
        if option.reckless:
            assert s.get(option.key) == option.default


def test_run_options_emits_only_what_DIFFERS_from_the_default(tmp_path):
    u"""⭐ A settings layer that passed every value explicitly would pin
    today's defaults into a file that outlives them."""
    s = SETTINGS.Settings({}, str(tmp_path / u"s.json"))
    assert s.run_options() == {}
    s.set(u"dry_run", True)
    assert s.run_options() == {u"dry_run": True}


def test_a_blank_path_is_not_a_folder(tmp_path):
    u"""⚠ `argv_for` reads any truthy string as a path and the settings panel
    hands back `u""` for an empty box. The two disagree, and this is the seam
    where that is resolved."""
    s = SETTINGS.Settings({}, str(tmp_path / u"s.json"))
    s.set(u"subs", u"   ")
    s.set(u"out", u"")
    assert u"subs" not in s.run_options()
    assert u"out" not in s.run_options()


def test_turning_on_anything_RECKLESS_makes_the_app_ask_first(tmp_path):
    s = SETTINGS.Settings({}, str(tmp_path / u"s.json"))
    s.set(u"rename", False)
    active = s.reckless_active()
    assert [o.key for o in active] == [u"rename"]
    assert s.confirm_before_writing() is True


def test_every_flagged_setting_names_a_real_argv_for_KEYWORD():
    u"""🚨 THE INERT-CONTROL CHECK. `doctrine/architecture`: *a control whose
    identifier is missing renders perfectly and is completely inert — it
    shipped three separate times in one build, and every time a human found it
    by tapping.*

    A settings checkbox bound to a keyword `argv_for` does not take is exactly
    that: it draws, it toggles, it saves, and it changes nothing about the
    run. ⭐ This walks the schema and asks the function.
    """
    import inspect
    accepted = set(inspect.signature(RUN.argv_for).parameters)
    accepted.discard(u"folder")
    for option in SETTINGS.FLAGGED:
        assert option.flag in accepted, \
            u"%s drives %r, which argv_for does not take" % (option.key,
                                                             option.flag)


def test_every_setting_has_a_group_a_label_and_a_reason():
    keys = [o.key for o in SETTINGS.SCHEMA]
    assert len(keys) == len(set(keys)), u"duplicate keys: %s" % keys
    groups = set(g[0] for g in SETTINGS.GROUPS)
    for option in SETTINGS.SCHEMA:
        assert option.group in groups, u"%s is in no group" % option.key
        assert option.label.strip(), option.key
        assert len(option.why.strip()) > 40, \
            u"%s needs a reason, not a restatement" % option.key
    # ⭐ Every group is rendered, so an option in a group the panel never
    # draws is an option nobody can reach.
    drawn = sum(len(opts) for _k, _t, _b, opts in SETTINGS.grouped())
    assert drawn == len(SETTINGS.SCHEMA)


def test_a_corrupt_settings_file_never_stops_the_app_opening(tmp_path):
    u"""⛔ Every value here has a default, so the file is regenerable — but a
    silent revert is its own defect, hence `note`."""
    path = tmp_path / u"s.json"
    path.write_text(u"{not json at all", encoding=u"utf-8")
    s = SETTINGS.Settings.load(str(path))
    assert s.get(u"auto_run_on_drop") is True
    assert s.note and u"defaults" in s.note

    path.write_text(u'["a list, not an object"]', encoding=u"utf-8")
    s = SETTINGS.Settings.load(str(path))
    assert s.get(u"recurse") is True
    assert s.note


def test_a_value_of_the_wrong_SHAPE_is_treated_as_absent(tmp_path):
    u"""⚠ A hand-edited file can put a string where a bool belongs, and
    `if settings.get("dry_run")` is then True for the string `"false"`."""
    path = tmp_path / u"s.json"
    path.write_text(u'{"dry_run": "false", "subs": 12}', encoding=u"utf-8")
    s = SETTINGS.Settings.load(str(path))
    assert s.get(u"dry_run") is False
    assert s.get(u"subs") == u""


def test_a_setting_written_by_a_NEWER_build_survives_an_older_one(tmp_path):
    u"""⚠ Dropping what it does not recognise turns *"I ran the old version
    once"* into *"my settings are gone."*"""
    path = tmp_path / u"s.json"
    s = SETTINGS.Settings({u"a_setting_from_the_future": 7}, str(path))
    s.set(u"dry_run", True).save()
    back = SETTINGS.Settings.load(str(path))
    assert back.values[u"a_setting_from_the_future"] == 7
    assert back.get(u"dry_run") is True


def test_an_unknown_key_is_refused_rather_than_silently_stored(tmp_path):
    s = SETTINGS.Settings({}, str(tmp_path / u"s.json"))
    with pytest.raises(KeyError):
        s.set(u"auto_run_on_drops", True)      # a typo, not a setting
    with pytest.raises(KeyError):
        s.get(u"nonsense")


# ===========================================================================
# 🚨 NO DOCTRINE MARKER MAY REACH THE SCREEN
# ===========================================================================

MARKERS = u"⭐⛔⚠🚨"


def _screen_strings(module):
    u"""Every string literal in `module` that is not a docstring. -> [(line, s)]"""
    import ast
    source = io.open(module.__file__, u"r", encoding=u"utf-8").read()
    tree = ast.parse(source)
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef,
                             ast.AsyncFunctionDef)):
            body = getattr(node, u"body", None)
            if body and isinstance(body[0], ast.Expr) and \
                    isinstance(body[0].value, ast.Constant) and \
                    isinstance(body[0].value.value, str):
                docstrings.add(id(body[0].value))
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                and id(node) not in docstrings:
            out.append((node.lineno, node.value))
    return out


def test_no_doctrine_marker_reaches_a_LABEL_at_RUNTIME():
    u"""⭐ THE SAME RULE, ASKED OF THE LOADED OBJECTS.

    Its twin below reads the SOURCE with `ast`, which is the right instrument
    for a marker somebody types into a literal — and is structurally blind to
    a `why` assembled at import time, or set by anything but a literal. A
    mutation run proved that: setting `SCHEMA[0].why = "⭐ " + …` at runtime
    **survived** the static check by construction.

    ⛔ Both, or neither. The static one names a line number and the runtime
    one covers everything the panel will actually draw.
    """
    bad = []
    for option in SETTINGS.SCHEMA:
        for field, text in ((u"label", option.label), (u"why", option.why)):
            if any(m in text for m in MARKERS) or u"`" in text:
                bad.append(u"%s.%s: %r" % (option.key, field, text[:70]))
    for key, title, blurb in SETTINGS.GROUPS:
        for field, text in ((u"title", title), (u"blurb", blurb)):
            if any(m in text for m in MARKERS) or u"`" in text:
                bad.append(u"group %s.%s: %r" % (key, field, text[:70]))
    assert not bad, u"markers on screen:\n  " + u"\n  ".join(bad)


@pytest.mark.parametrize("modname", [u"app", u"settings"])
def test_no_doctrine_marker_or_markdown_reaches_a_LABEL(modname):
    u"""🚨 FIX THE CLASS, NOT THE INSTANCE.

    Found by looking at the real settings panel: a hollow ☆ sat mid-sentence
    like a typo, and `*would sync*` rendered with its asterisks showing. This
    project's markers and its backticks are for its own documents; a Tk label
    prints them literally, and every one of them is noise to the person the
    sentence was written for.

    ⭐ It is a static check because it can be: no runtime, no display, and it
    names the exact line. `doctrine/verification`'s order of preference —
    *a mechanical check* beats *a trigger line* beats *remembering*.

    ⚠ The UI's OWN glyphs are fine and deliberate: ✓ ✗ ⚑ ⚙ → are what the
    ruled output uses. Only the doctrine markers are banned.
    """
    import importlib
    module = importlib.import_module(u"tsubasa.gui.%s" % modname)
    bad = []
    for line, text in _screen_strings(module):
        if any(m in text for m in MARKERS):
            bad.append((line, u"doctrine marker", text[:70]))
        elif u"`" in text:
            bad.append((line, u"a backtick", text[:70]))
    assert not bad, u"user-facing strings carrying %s:\n%s" % (
        u"markers/markdown",
        u"\n".join(u"  %s:%d  %s  %r" % (modname, l, why, t)
                   for l, why, t in bad))


# ===========================================================================
# THE WINDOW -- needs a display, and says so
# ===========================================================================

def _app(tmp_path, **values):
    u"""A real `App` over a fake child. -> (root, app)

    ⭐ `runner_factory` is the seam. The window drives a REAL `Runner`; only
    the process under it is a double, so everything from `argv_for` through
    the parse to the counts is the shipped path.
    """
    root = _tk_root()
    from tsubasa.gui import app as APP
    s = SETTINGS.Settings(dict(values), str(tmp_path / u"s.json"))
    stdout = ndjson(a_record(u"REFUSED"), a_record(), a_record(),
                    a_record(u"ERROR"))
    factory = lambda folder, **opts: RUN.Runner(  # noqa: E731
        folder, popen=fake_popen(stdout=stdout, stderr=u"2 synced\n", code=1),
        **opts)
    return root, APP.App(root, settings=s, runner_factory=factory)


@pytest.mark.skipif(not sys.platform.startswith("win"),
                    reason=u"needs a display")
def test_the_window_opens_at_the_size_it_was_built_to_be(tmp_path):
    u"""🚨 MEASURED NON-DETERMINISTIC BEFORE THIS EXISTED: two consecutive
    runs of the same probe, nothing changed, one window **1647 px** tall and
    the next **1089** — and the capture harness said OK to both."""
    root, app = _app(tmp_path)
    try:
        root.update_idletasks()
        root.update()
        assert (root.winfo_width(), root.winfo_height()) == \
            (app.pin.width, app.pin.height)
        # ⛔ AND IT MAY NOT SHRINK BELOW IT. The floor is what stops the
        # geometry manager taking the window back.
        assert root.minsize() == (app.pin.width, app.pin.height)
    finally:
        root.destroy()


@pytest.mark.skipif(not sys.platform.startswith("win"),
                    reason=u"needs a display")
def test_the_window_still_WORKS_on_a_small_screen_it_has_to_clamp_to(tmp_path,
                                                                    monkeypatch):
    u"""🚨 THE SCREEN THE AUTHOR OWNS IS A CONFIGURATION, NOT A CONSTANT.

    This machine is **3000x2000 at 239.6 dpi**. A GitHub Windows runner is
    **1024x768 at 96**, and the window asks for 1060 design px — so it clamps
    there and never clamps here. ⛔ Every check in this file ran for weeks
    against the one screen that makes clamping unreachable, and the clamp path
    broke a sibling check on six runners at once.

    ⭐ So the runner's geometry is pinned here as a supported configuration.
    `Scale` takes `dpi`, `screen`, `area` and `chrome` as arguments precisely
    so it can be asked about a machine that is not this one.

    ⚠ **AND THE FIRST SIMULATION OF IT WAS WRONG IN A WAY THAT INVENTED A
    DEFECT.** Patching only `work_area` to 1024x768 left this machine's 2.496
    ratio in place, so 1060 design px still meant 2646 real ones: the window
    came out **381 px wide**, controls fell off it, and a second check
    'failed'. It was an artifact — CI had reported no such failure, and at the
    runner's real ratio of 1.0 the window is 968x660 and everything fits.
    **A simulation that is harsher than the thing it simulates manufactures
    work.** Both halves have to be faithful, not just the one you thought of.
    """
    real_init = SCALE.Scale.__init__

    def as_a_runner(self, root, dpi=None, screen=None, area=None, chrome=None):
        real_init(self, root, dpi=96.0, screen=(1024, 768),
                  area=(0, 0, 1024, 768), chrome=(16, 39))

    monkeypatch.setattr(SCALE.Scale, u"__init__", as_a_runner)
    root, app = _app(tmp_path)
    try:
        root.update()
        assert app.pin.clamped, (
            u"1060 design px at ratio 1.0 plus frame does not fit 1024 of "
            u"work area, so this must clamp — if it stopped clamping, this "
            u"check is no longer standing where it thinks it is")
        assert app.message and u"clamped" in app.message, (
            u"it clamped and did not say so: %r" % app.message)

        # ⛔ CLAMPED IS NOT THE SAME AS USABLE, and clamping correctly while
        # putting a control off the edge is the defect `pin` exists to stop.
        for widget, name in ((app.browse_btn, u"Browse"),
                             (app.sync_btn, u"Sync"),
                             (app.dry_chk, u"Dry run"),
                             (app.settings_btn, u"Settings")):
            assert widget.winfo_ismapped(), \
                u"%s is off a clamped %dx%d window" % (
                    name, app.pin.width, app.pin.height)

        assert app.pin.width <= 1024 and app.pin.height <= 768, \
            u"clamped to %dx%d, which is larger than the screen" % (
                app.pin.width, app.pin.height)
    finally:
        root.destroy()


@pytest.mark.skipif(not sys.platform.startswith("win"),
                    reason=u"needs a display")
def test_the_controls_are_in_the_order_that_was_RULED(tmp_path):
    u"""⭐ `Browse…  Sync  Dry run  ⚙`, left to right.

    The mockup Sonic approved put Browse before Sync — you browse for a
    folder and then sync it — and the first build silently swapped them,
    because `pack(side="right")` reverses the order they are created in.
    Found by looking at a screenshot of the real window.
    """
    root, app = _app(tmp_path)
    try:
        # 🚨 `update()`, NOT `update_idletasks()` — AND PROVE IT LANDED.
        # Measured: after `update_idletasks()` alone every widget is at
        # **x=0 and unmapped**, so this check was sorting four zeros and
        # `sorted()` fell through to its tiebreak on the LABEL — returning
        # them alphabetically, which happens to be
        # `Browse, Dry run, Settings, Sync`. ⛔ It passed once and failed once
        # on identical code. A geometry assertion that does not first
        # establish the widget IS laid out is reading a default.
        root.update()
        widgets = [(app.browse_btn, u"Browse"), (app.sync_btn, u"Sync"),
                   (app.dry_chk, u"Dry run"),
                   (app.settings_btn, u"Settings")]
        for widget, name in widgets:
            assert widget.winfo_ismapped(), u"%s is not on screen" % name
        xs = [widget.winfo_x() for widget, _n in widgets]
        assert len(set(xs)) == len(xs), \
            u"two controls share an x — the layout has not run: %s" % xs

        order = sorted((widget.winfo_x(), name) for widget, name in widgets)
        assert [name for _x, name in order] == [u"Browse", u"Sync",
                                                u"Dry run", u"Settings"]
    finally:
        root.destroy()


@pytest.mark.skipif(not sys.platform.startswith("win"),
                    reason=u"needs a display")
def test_refusals_are_put_at_the_TOP_as_they_arrive(tmp_path):
    u"""`05-interface.md`: *the one thing needing attention must not sit below
    23 successes.* ⭐ Held incrementally rather than restored by a sort at the
    end that a later edit could drop — the fake emits REFUSED, CONFIDENT,
    CONFIDENT, ERROR **in that order**, so a renderer that simply appended
    would put the ERROR last."""
    root, app = _app(tmp_path)
    try:
        app.folder_var.set(str(tmp_path))
        app.start()
        for _ in range(200):
            root.update()
            if app.run is not None:
                break
            time.sleep(0.01)
        assert app.run is not None, u"the run never finished"
        marks = [app.tree.item(i, u"text") for i in app.tree.get_children()]
        assert marks[:2] == [u"!", u"✗"] or marks[:2] == [u"✗", u"!"], marks
        assert marks[2:] == [u"✓", u"✓"], marks
    finally:
        root.destroy()


@pytest.mark.skipif(not sys.platform.startswith("win"),
                    reason=u"needs a display")
def test_the_dry_run_checkbox_and_the_settings_are_ONE_value(tmp_path):
    u"""⭐ Two controls, one state. The settings panel can change `dry_run`
    while the bar's checkbox is on screen; without the sync in `_repaint` the
    two disagree and the one you are looking at is a lie."""
    root, app = _app(tmp_path)
    try:
        assert app.dry_var.get() is False
        app.settings.set(u"dry_run", True)
        app._repaint()
        assert app.dry_var.get() is True

        app.dry_var.set(False)
        app._dry_toggled()
        assert app.settings.get(u"dry_run") is False
    finally:
        root.destroy()


@pytest.mark.skipif(not sys.platform.startswith("win"),
                    reason=u"needs a display")
def test_a_dropped_FILE_means_the_folder_it_is_in(tmp_path):
    u"""⚠ THE PAYLOAD IS A TK LIST, NOT A PATH. A dropped path containing a
    space arrives brace-wrapped — `{C:/Anime/片田舎のおっさん S2}` — and
    reading it raw gives a folder that does not exist."""
    root, app = _app(tmp_path, auto_run_on_drop=False)
    try:
        from tsubasa.gui import app as APP
        folder = tmp_path / u"片田舎のおっさん S2"
        folder.mkdir()
        episode = folder / u"01.mkv"
        episode.write_bytes(b"x")

        assert APP._dropped_paths(root, u"{%s}" % episode) == [str(episode)]

        class _E(object):
            data = u"{%s}" % episode
        app._on_drop(_E())
        assert app.folder_var.get() == str(folder)
        assert app.runner is None, u"auto_run_on_drop was off"
    finally:
        root.destroy()


@pytest.mark.skipif(not sys.platform.startswith("win"),
                    reason=u"needs a display")
def test_auto_run_on_drop_is_ON_by_default_and_the_setting_turns_it_off(
        tmp_path):
    u"""⭐ SONIC'S RULING: *auto-run on drop unless setting is toggled.*"""
    root, app = _app(tmp_path)
    try:
        from tsubasa.gui import app as APP
        folder = tmp_path / u"lib"
        folder.mkdir()

        class _E(object):
            data = str(folder)
        assert app.settings.get(u"auto_run_on_drop") is True
        app._on_drop(_E())
        assert app.runner is not None, u"a drop did not start a run"
    finally:
        root.destroy()


@pytest.mark.skipif(not sys.platform.startswith("win"),
                    reason=u"needs a display")
def test_the_detail_pane_describes_the_row_that_is_actually_selected(tmp_path):
    u"""🚨 THE MAP WAS NEVER CLEARED BETWEEN RUNS.

    Tk reuses item ids (`I001` and up) after a `delete`, so an entry from the
    previous run is reachable by a fresh item: a detail pane describing a file
    from a folder the user has already moved on from.

    ⚠ **AND A CLAIM THIS CHECK DISPROVED.** It was written believing
    `selection_set` fires `<<TreeviewSelect>>` **synchronously**, so that
    writing the map after the selection would leave the first row undescribed.
    Measured: `detail_head` is empty immediately after `_add_row` and
    populated once the event loop turns — **the event is queued, not
    synchronous**, so both lines complete before any handler runs and the
    ordering inside `_add_row` cannot matter. The reorder stays because it is
    more obviously correct; it is not a fix, and saying so is cheaper than a
    comment that misleads the next reader.

    ⛔ AND THE CHECK STILL ASSUMED SOMETHING TRUE ONLY ON THIS DESKTOP: that
    the head belongs to the selected row. It belongs to `self.message` first,
    and a window clamped to fit the screen sets one. **This machine is
    3000x2000 and never clamps; a GitHub Windows runner is 1024x768 and always
    does**, so the check failed on six runners against a product doing exactly
    what it was built to do. The screen the author happens to own is a
    configuration, not a constant.
    """
    root, app = _app(tmp_path)
    try:
        only = a_row(u"REFUSED")
        app._add_row(only)
        assert app.selected_row() is only, \
            u"the row on screen does not map to the object it was built from"
        root.update()               # ⚠ the virtual event fires HERE, not above

        # ===================================================================
        # ⛔ THE DETAIL PANE IS SHARED, AND ON A SMALL SCREEN IT IS TAKEN
        # ===================================================================
        # `_paint_detail` gives the head to `self.message` whenever there is
        # one, and `__init__` sets one when the window had to be CLAMPED to
        # fit the work area. A GitHub Windows runner is **1024x768** and the
        # window asks for 1060 wide, so on CI a message is ALWAYS showing and
        # the head is blank **by design** — the product was behaving
        # correctly and this check called it a blank pane.
        #
        # ⚠ The first attempt at a fix pumped the event loop to a deadline, on
        # the theory that the queued `<<TreeviewSelect>>` was not being
        # delivered. It was being delivered the whole time. Two seconds of
        # turning the loop changed nothing, which is what said the theory was
        # wrong — a fix that does not work is evidence, and it was cheaper
        # than the reasoning that produced it.
        #
        # ⭐ So the note is cleared, and ASSERTED before it is cleared, so that
        # clearing it can never quietly become a way to hide a real message.
        if app.message:
            assert app.pin.clamped, (
                u"a message is showing and it is not the window-clamp note, "
                u"so something else went wrong: %r" % app.message)
            app.message = u""
            app._repaint()

        assert only.name in app.detail_head.cget(u"text"), \
            u"the detail pane is blank for the row it just selected"

        app.folder_var.set(str(tmp_path))
        app.start()
        for _ in range(200):
            root.update()
            if app.run is not None:
                break
            time.sleep(0.01)
        first = app.selected_row()
        assert first is not None, u"a row is selected and nothing describes it"
        assert app.detail_head.cget(u"text"), u"the detail head is empty"
        assert first.name in app.detail_head.cget(u"text")

        # ⭐ EVERY item on screen resolves to a row, and to nothing stale.
        for item in app.tree.get_children():
            assert item in app._row_by_item, u"%s maps to nothing" % item
        assert len(app._row_by_item) == len(app.tree.get_children())

        # ⛔ A SECOND RUN STARTS FROM AN EMPTY MAP.
        app.start()
        assert app._row_by_item == {}, \
            u"a new run inherited %d stale item(s)" % len(app._row_by_item)
    finally:
        root.destroy()


@pytest.mark.skipif(not sys.platform.startswith("win"),
                    reason=u"needs a display")
def test_an_IDLE_window_reports_no_counts_at_all(tmp_path):
    u"""⛔ `✓ 0 would sync` BEFORE A RUN IS A CLAIM THAT ONE HAPPENED.

    `doctrine/architecture`: *controls vanish when they would be meaningless.*
    The smallest member of this window's whole family of defects, and found
    the same way as the rest — by looking at it before pressing Sync.
    """
    root, app = _app(tmp_path)
    try:
        root.update_idletasks()
        assert app.chips.winfo_children() == [], \
            u"an idle window drew %d count chip(s)" \
            % len(app.chips.winfo_children())
        assert app.elapsed_lbl.cget(u"text") == u""

        app.folder_var.set(str(tmp_path))
        app.start()
        for _ in range(200):
            root.update()
            if app.run is not None:
                break
            time.sleep(0.01)
        # ⭐ AND THEY APPEAR THE MOMENT THERE IS SOMETHING TO SAY.
        assert app.chips.winfo_children(), u"a finished run drew no chips"
    finally:
        root.destroy()


@pytest.mark.skipif(not sys.platform.startswith("win"),
                    reason=u"needs a display")
def test_an_UNMEASURED_row_shows_no_offset(tmp_path):
    u"""🚨 `+0.00s` IS NOT `NONE`. Found by looking at a real run: the ERROR
    row — a file with zero cues that could not be measured at all — displayed
    a confident-looking `+0.00s`, because the object still carries a
    zero-filled segment. Same shape as the CLI's `-0.00s` at 3c."""
    from tsubasa.gui import app as APP
    assert APP._offsets(a_row(u"ERROR", segments=[[None, 0.0]])) == u"—"
    assert APP._offsets(a_row(segments=[[None, 0.13]])) == u"+0.13s"
    assert APP._offsets(a_row(segments=[[222.4, -33.07],
                                        [None, -42.96]])) == u"-33.07 / -42.96"


@pytest.mark.skipif(not sys.platform.startswith("win"),
                    reason=u"needs a display")
def test_a_cell_is_trimmed_to_FIT_and_never_touches_the_next_column(tmp_path):
    u"""🚨 MEASURED, NEVER COUNTED — and a CJK character is two terminal cells
    and one proportional glyph of no fixed width.

    Without this, ttk clips at the column edge with no gap and a real run
    rendered `…[Multiple].s—`: the filename running straight into the next
    column's em-dash, reading as one token. That is the CLI's
    `…HEVC AAC).srtREFUSED` defect, in a table.
    """
    root, app = _app(tmp_path)
    try:
        from tsubasa.gui import app as APP
        font = app.fonts[u"ui"]
        long_ja = u"黄泉のツガイ.S01E01.風神と雷神.WEBRip.Netflix.ja[cc].srt"
        for width in (80, 160, 320):
            fitted = APP._fit(long_ja, font, width)
            assert font.measure(fitted) <= width, \
                u"%r measures %d in %d" % (fitted, font.measure(fitted), width)
            assert fitted.endswith(u"…")
        # ⭐ Short enough to fit is returned untouched — no gratuitous ellipsis.
        assert APP._fit(u"01.srt", font, 400) == u"01.srt"
    finally:
        root.destroy()


# ===========================================================================
# END TO END -- the real CLI, over real media
# ===========================================================================

def _material():
    try:
        return E.material()
    except E.Missing as exc:
        pytest.skip(str(exc))


def test_the_real_cli_is_spawned_and_its_rows_come_back(tmp_path):
    u"""⭐ THE ONE THAT WOULD NOTICE. Everything above drives a double."""
    mat = _material()
    lib = tmp_path / u"library" / u"Yomi no Tsugai"
    lib.mkdir(parents=True)
    E.build_yomi_folder(str(lib), mat)

    runner = RUN.Runner(str(lib), dry_run=True, results=False)
    runner.start()
    run = runner.wait(timeout=300)

    assert run is not None
    assert run.code in (RUN.EXIT_CLEAN, RUN.EXIT_ATTENTION), \
        u"exit %d, stderr: %s" % (run.code, run.stderr[:400])
    assert not run.could_not_run, run.stderr[:400]
    assert run.faults == (), [f.text for f in run.faults]
    assert run.rows, u"no rows on stdout; stderr was: %s" % run.stderr[:400]
    for row in run.rows:
        assert row.outcome in RUN.OUTCOMES
        if row.outcome != u"CONFIDENT":
            assert row.reason, u"%r is non-confident with no reason" % row
    assert run.partitions is True
    # ⭐ AND IT IS A DRY RUN, so nothing may claim a file moved.
    assert run.dry_run is True
    assert run.counts[u"landed"] == 0
    assert u"would sync" in run.headline()


def test_a_japanese_filename_survives_the_pipe(tmp_path):
    u"""🚨 THE ENCODING CLAIM, END TO END."""
    mat = _material()
    lib = tmp_path / u"lib" / u"Yomi no Tsugai"
    lib.mkdir(parents=True)
    E.build_yomi_folder(str(lib), mat)

    staged = [p.name for p in lib.iterdir()]
    japanese = [n for n in staged if any(u"　" <= c <= u"鿿"
                                         for c in n)]
    assert japanese, u"no CJK name to test with: %s" % staged

    runner = RUN.Runner(str(lib), dry_run=True, results=False)
    runner.start()
    run = runner.wait(timeout=300)

    seen = u" ".join([r.name for r in run.rows]
                     + [os.path.basename(r.video or u"") for r in run.rows])
    assert u"�" not in seen, u"a replacement character came back: %r" % seen
    assert any(any(u"　" <= c <= u"鿿" for c in n)
               for n in seen.split()), u"no CJK survived: %r" % seen


def test_out_with_in_place_retiming_is_refused_BEFORE_anything_is_spawned():
    u"""⛔ `sync()` raises on this pair and `cli.main` exits 2 with the
    sentence — correct, and a whole process later. ⭐ The settings panel can
    produce the combination with two clicks, so the answer belongs where the
    two clicks are: `argv_for` refuses it locally, in the same words."""
    with pytest.raises(ValueError) as exc:
        RUN.argv_for(u"/lib", out=u"/elsewhere", rename=False)
    assert u"contradict" in str(exc.value)


def test_a_command_that_cannot_be_run_comes_back_as_exit_2(tmp_path):
    u"""⭐ THE REAL CLI'S OWN REFUSAL, not one this layer pre-empts. A folder
    that does not exist reaches `scan()`, which raises, and `cli.main` turns
    that into exit 2 and a sentence."""
    missing = tmp_path / u"no such folder"
    runner = RUN.Runner(str(missing), results=False)
    runner.start()
    run = runner.wait(timeout=120)

    assert run.code == RUN.EXIT_CANNOT_RUN, \
        u"exit %d, stderr %r" % (run.code, run.stderr[:400])
    assert run.could_not_run is True
    assert run.rows == ()
    assert run.headline().strip()
    assert u"no such folder" in run.stderr or u"does not exist" in run.stderr


def test_videos_with_NO_SUBTITLE_are_never_called_already_in_sync(tmp_path):
    u"""🚨 THE ADVERSARY'S FINDING, AGAINST THE REAL CLI.

    Three videos and not one subtitle. The CLI says so; `--json` emits no
    record, exits 0, and the first draft rendered *"everything here is already
    in sync"* over a folder where nothing had been done at all.

    ⭐ And it is `07-test-plan.md`'s own rule from the other side: the check
    that passed used an EMPTY folder, which cannot contain an unpaired video.
    """
    mat = _material()
    lib = tmp_path / u"lib" / u"Videos Only"
    lib.mkdir(parents=True)
    E.build_yomi_folder(str(lib), mat)
    for p in lib.iterdir():
        if p.suffix.lower() not in (u".mkv", u".mp4"):
            p.unlink()
    assert any(p.suffix.lower() == u".mkv" for p in lib.iterdir())

    runner = RUN.Runner(str(lib), dry_run=True, results=False)
    runner.start()
    run = runner.wait(timeout=300)

    assert run.rows == ()
    assert run.no_rows is True
    assert run.summary, u"the CLI must never be silent: %r" % run.stderr
    assert u"already in sync" not in run.headline(), \
        u"headline %r over stderr %r" % (run.headline(), run.stderr[:200])
    assert run.headline() == run.summary


def test_an_empty_folder_quotes_the_cli_too(tmp_path):
    empty = tmp_path / u"nothing here"
    empty.mkdir()
    runner = RUN.Runner(str(empty), dry_run=True, results=False)
    runner.start()
    run = runner.wait(timeout=120)

    assert run.rows == ()
    assert run.faults == ()
    assert run.code == RUN.EXIT_CLEAN, u"stderr: %r" % run.stderr[:400]
    assert run.no_rows is True
    assert run.headline() == run.summary
