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

    ⚠ **Every window this makes is on a desktop of its own and cannot be
    seen or focused** — see `conftest.use_a_private_desktop`, and
    `TSUBASA_TEST_SHOW_WINDOWS=1` to put them back on screen.

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

    # ===================================================================
    # 🚨 DPI-AWARE FIRST, EXACTLY AS `app.make_root()` DOES
    # ===================================================================
    # `make_process_dpi_aware` MUST run before the first `Tk()` in a process:
    # Tk reads the screen metrics once, and afterwards the call still succeeds
    # while every number in the process is of a virtualised 96 dpi screen.
    #
    # ⛔ FOUND 2026-09-17, AND IT WAS AN ORDER DEPENDENCY, NOT A NEW BUG.
    # `test_the_window_opens_at_the_size_it_was_built_to_be` measured 239.6 dpi
    # and passed — but only because the test defined immediately ABOVE it
    # happens to call `make_process_dpi_aware()`. Adding checks earlier in this
    # file moved the process's first root ahead of that call, the DPI read 95.8,
    # and the check turned itself into a SKIP. ⚠ A skip is the worst outcome
    # here: it is green, and the thing it guards (a window that clipped its own
    # button off the screen) went unguarded.
    #
    # ⭐ Making it unconditional costs nothing, matches the shipped path, and
    # removes a landmine under every future check in this file. It is safe to
    # call repeatedly — `E_ACCESSDENIED` means *already set*, which the
    # function treats as success.
    SCALE.make_process_dpi_aware()

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

@pytest.mark.skipif(not sys.platform.startswith("win"),
                    reason=u"needs a display")
def test_a_test_WINDOW_CANNOT_TOUCH_THE_SCREEN_SONIC_IS_USING():
    u"""🚨 REPORTED: *"Please make all these tests occur out of focus, as
    it interrupts what I am doing."*

    This file maps **real** Tk windows on purpose — that is why it catches
    things assertions do not — but every one of them used to flash up and take
    the keyboard, so a full run interrupted whatever he was doing over a
    hundred times.

    ⛔ **THREE WINDOW-LEVEL FIXES WERE TRIED AND MEASURED TO FAIL**, and the
    measurement is the reason this check exists in the shape it does:

        -alpha 0.0                         invisible, still took the focus
        + WS_EX_NOACTIVATE on <Map>        bits set, STILL took the focus —
                                           the map had already handed it over
        + withdraw, style, SW_SHOWNOACTIVATE   STILL took the focus: Tk
                                           re-activates the window on update()

    ⭐ `WS_EX_NOACTIVATE` stops Windows activating a window **when it is
    shown**; it does not stop Tk asking for the foreground afterwards. The
    thing that works is not a window property at all — the whole thread runs
    on a **private desktop**, where there is no foreground to take.

    ⚠ This asserts the DESKTOP, not a style bit, because the desktop is what
    the guarantee rests on.
    """
    import ctypes
    from ctypes import wintypes
    import conftest

    # 🚨 SKIP, DO NOT FAIL, WHEN THE OFF SWITCH IS SET. This check asserts
    # that the windows are NOT on Sonic's desktop — which is deliberately
    # false when he has asked for them to be, and asserting it anyway made
    # the documented escape hatch guarantee a red run.
    #
    # ⛔ THAT IS WORSE THAN IT SOUNDS. `TSUBASA_TEST_SHOW_WINDOWS=1` exists
    # so somebody can LOOK at the real window, which is paid-for doctrine
    # here — fifty green checks once sat over a header running off the
    # screen. With this failing, *look at it* and *run the suite green* were
    # mutually exclusive, and a developer who leaves the variable set learns
    # to ignore a permanent failure. Reported by an adversarial pass; the
    # off switch was mine, and so was this.
    if os.environ.get(conftest.SHOW_WINDOWS):
        pytest.skip(u"SKIPPED, NOT PASSED: %s is set, so the windows are "
                    u"deliberately on the real desktop"
                    % conftest.SHOW_WINDOWS)
    assert conftest.DESKTOP_MOVED == u"", \
        u"the private desktop was not entered: %s" % conftest.DESKTOP_MOVED

    u32 = ctypes.WinDLL(u"user32", use_last_error=True)
    u32.GetThreadDesktop.argtypes = [wintypes.DWORD]
    u32.GetThreadDesktop.restype = wintypes.HANDLE
    u32.GetUserObjectInformationW.argtypes = [
        wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
        wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    u32.GetUserObjectInformationW.restype = wintypes.BOOL
    u32.GetForegroundWindow.argtypes = []
    u32.GetForegroundWindow.restype = wintypes.HWND
    u32.GetAncestor.argtypes = [wintypes.HWND, wintypes.UINT]
    u32.GetAncestor.restype = wintypes.HWND
    k32 = ctypes.WinDLL(u"kernel32", use_last_error=True)
    k32.GetCurrentThreadId.restype = wintypes.DWORD

    buf = ctypes.create_unicode_buffer(256)
    got = wintypes.DWORD()
    assert u32.GetUserObjectInformationW(
        u32.GetThreadDesktop(k32.GetCurrentThreadId()),
        conftest.UOI_NAME, buf, ctypes.sizeof(buf), ctypes.byref(got)), \
        u"could not read the thread's desktop"
    ours = buf.value

    # 🚨 COMPARING `ours` TO `conftest.DESKTOP_NAME` WAS THE ORIGINAL
    # CHECK AND IT WAS WORTHLESS: it read the name out of `conftest` and
    # compared it to the name in `conftest`, so it passed for ANY value —
    # including `"Default"`, which is Sonic's own desktop. `CreateDesktopW`
    # OPENS an existing desktop rather than failing, so that is a real
    # reachable state, not a hypothetical. Proven by an adversary.
    #
    # ⭐ THE ONLY MEANINGFUL COMPARISON IS AGAINST THE DESKTOP RECEIVING
    # THE USER'S INPUT, which is what `OpenInputDesktop` answers. That is
    # the thing the whole feature is about: not "are we somewhere named X"
    # but "are we somewhere that is NOT where he is typing."
    u32.OpenInputDesktop.argtypes = [wintypes.DWORD, wintypes.BOOL,
                                     wintypes.DWORD]
    u32.OpenInputDesktop.restype = wintypes.HANDLE
    u32.CloseDesktop.argtypes = [wintypes.HANDLE]
    u32.CloseDesktop.restype = wintypes.BOOL

    DESKTOP_READOBJECTS = 0x0001
    inp = u32.OpenInputDesktop(0, False, DESKTOP_READOBJECTS)
    if not inp:
        pytest.skip(u"cannot open the input desktop (locked session?)")
    try:
        other = ctypes.create_unicode_buffer(256)
        assert u32.GetUserObjectInformationW(
            inp, conftest.UOI_NAME, other, ctypes.sizeof(other),
            ctypes.byref(got)), u"could not name the input desktop"
        assert ours != other.value, (
            u"the checks are running on %r, which IS the desktop "
            u"receiving Sonic's keyboard — every test window will "
            u"interrupt him" % ours)
    finally:
        u32.CloseDesktop(inp)

    # ⛔ AND NOT THE VACUOUS VERSION. `GetForegroundWindow()` returns None
    # on a private desktop UNCONDITIONALLY — a desktop nobody is viewing
    # has no foreground by definition — so `assert GetForegroundWindow() !=
    # hwnd` held for every reachable state. An adversary made the window
    # call `lift()`, `focus_force()` and `SetForegroundWindow()` immediately
    # before it, and the assertion still passed. ⭐ The desktop comparison
    # above is what that assertion was TRYING to say.
    root = _tk_root()
    try:
        root.update()
        hwnd = u32.GetAncestor(wintypes.HWND(root.winfo_id()), 2)
        assert hwnd, u"the window has no top-level"
    finally:
        root.destroy()


def test_the_private_desktop_is_REFUSED_off_windows(monkeypatch):
    u"""🚨 NO `skipif` ON THIS ONE, DELIBERATELY — IT IS THE ONLY CHECK HERE
    THAT RUNS ON ALL SIXTEEN CI JOBS.

    `why_not_a_private_desktop()` is the DECISION, split out from the doing
    precisely so it can be driven without Win32: it touches no `ctypes`, opens
    no window and needs no display. Everything else about the private desktop
    is Windows-only plumbing and is skipped off Windows.

    ⛔ THE ARM THIS GUARDS HAS TWICE PUT 8 RED JOBS ON THE BOARD. Deleting the
    platform guard was measured SURVIVING the whole suite on Windows — because
    on Windows it is always true — and what it lets through is a Linux job
    walking into `ctypes.WinDLL`, which does not exist there, followed one line
    later by `from ctypes import wintypes`, which does not either.
    """
    import conftest

    monkeypatch.delenv(conftest.SHOW_WINDOWS, raising=False)
    for platform in (u"linux", u"darwin", u"freebsd12"):
        monkeypatch.setattr(conftest.sys, u"platform", platform)
        assert conftest.why_not_a_private_desktop() == u"not Windows", (
            u"on %s it still tries to create a Win32 desktop" % platform)

    monkeypatch.setattr(conftest.sys, u"platform", u"win32")
    assert conftest.why_not_a_private_desktop() == u"", \
        u"on Windows it refuses the private desktop"

    # ⭐ AND THE OFF SWITCH OUTRANKS THE PLATFORM, on every platform.
    monkeypatch.setenv(conftest.SHOW_WINDOWS, u"1")
    assert conftest.SHOW_WINDOWS in conftest.why_not_a_private_desktop()


@pytest.mark.skipif(not sys.platform.startswith("win"),
                    reason=u"needs a display")
def test_the_hidden_windows_have_an_OFF_SWITCH(monkeypatch):
    u"""⛔ *ASSERT THE OUTPUT, THEN LOOK AT IT* is paid-for doctrine here —
    fifty green checks once sat over a header running off the screen. A harness
    that made the window permanently unlookable-at would quietly retire that,
    so `TSUBASA_TEST_SHOW_WINDOWS=1` puts every window back on Sonic's own
    desktop, visible and normal.

    ⚠ The switch is read ONCE, before any window exists, because
    `SetThreadDesktop` only works on a thread that has none — so this drives
    the decision, which is the part that can regress, not a second move.
    """
    import conftest

    monkeypatch.setenv(conftest.SHOW_WINDOWS, u"1")
    assert conftest.SHOW_WINDOWS in conftest.why_not_a_private_desktop(), \
        u"the off switch does not turn it off"

    monkeypatch.delenv(conftest.SHOW_WINDOWS, raising=False)
    assert conftest.why_not_a_private_desktop() == u"", \
        u"it refuses the private desktop with the switch unset"

    # ⚠ AND THE PLATFORM ARM, which is unreachable on the machine that
    # runs it. Deleting the `sys.platform` guard was measured SURVIVING the
    # whole suite here, because here it is always Windows — so the only way
    # to check it is to say we are not. Without the guard a Linux job walks
    # into `ctypes.WinDLL`, which does not exist there.
    monkeypatch.setattr(conftest.sys, u"platform", u"linux")
    assert conftest.why_not_a_private_desktop() == u"not Windows", \
        u"off Windows it still tries to create a desktop"


@pytest.mark.skipif(not sys.platform.startswith("win"),
                    reason=u"drives Win32 desktop plumbing; see the note")
def test_a_desktop_that_CANNOT_be_entered_SAYS_SO_instead_of_lying(monkeypatch):
    u"""🚨 WRITTEN BECAUSE TWO MUTANTS SURVIVED. Dropping the `CreateDesktopW`
    result, and swallowing a failed `SetThreadDesktop`, both left every other
    check green — because on this machine neither call ever fails, so the
    error arms are code nothing runs.

    ⛔ **And the failure they let through is exactly the reported complaint,
    silently.** `use_a_private_desktop()` would return `u""` — *moved, all
    fine* — while the thread was still on Sonic's own desktop and every window
    went on taking his keyboard. `DESKTOP_MOVED` is what the check above
    trusts, so a lie here disarms that one too.

    ⭐ So both arms are driven with a Win32 that fails on demand.
    """
    import conftest

    def win32_where(create, set_thread):
        class Fn(object):
            def __init__(self, value):
                self.value = value

            def __call__(self, *a, **k):
                return self.value

        dll = type(str(u"FakeUser32"), (object,), {})()
        dll.CreateDesktopW = Fn(create)
        dll.SetThreadDesktop = Fn(set_thread)
        return lambda *a, **k: dll

    monkeypatch.delenv(conftest.SHOW_WINDOWS, raising=False)

    # 🚨 WINDOWS-ONLY, AND IT COST 8 RED CI JOBS TO SETTLE THAT.
    # Everything here drives a FAKE Win32, so the first instinct was that it
    # needs no real one — forcing `sys.platform` to `"win32"` and letting
    # Linux run it too. ⛔ That does not work: past the guard,
    # `use_a_private_desktop()` does `from ctypes import wintypes`, and
    # **`ctypes.wintypes` does not exist off Windows** — so forcing the
    # platform only moves the failure one line down.
    #
    # ⚠ THIS FUNCTION HAS NOW MADE THE SAME MISTAKE TWICE: the
    # `raising=False` below was added in this session to fix a Windows-only
    # assumption, and a new one arrived two edits later.
    # ⭐ THE GAP IS COVERED ELSEWHERE, which is why skipping is honest here:
    # `test_the_private_desktop_is_REFUSED_off_windows` carries NO `skipif`
    # and drives `why_not_a_private_desktop()` on linux, darwin and freebsd —
    # that is the DECISION, it touches no Win32, and it runs on all sixteen
    # CI jobs. ⚠ An earlier version of this note named
    # `..._have_an_OFF_SWITCH` instead and said it *runs on every platform*;
    # it is `skipif not win`, so that was false the moment it was written.
    #
    # 🚨 THE DECLARATIONS ARE LOAD-BEARING AND NOTHING CHECKED THEM.
    # `conftest.py` says so in capitals — *undeclared, ctypes assumes int
    # and truncates a 64-bit handle* — and an adversary deleted BOTH
    # `CreateDesktopW.restype` and `SetThreadDesktop.argtypes` with a fully
    # green run, because every desktop handle on this machine is small
    # (304, 360) and truncation is invisible until it is not.
    declared = {}

    class _Recording(object):
        def __init__(self, name, value):
            self._name, self._value = name, value

        def __setattr__(self, key, value):
            if key in (u"argtypes", u"restype"):
                declared.setdefault(self._name, set()).add(key)
            object.__setattr__(self, key, value)

        def __call__(self, *a, **k):
            return self._value

    recorder = type(str(u"RecordingUser32"), (object,), {})()
    recorder.CreateDesktopW = _Recording(u"CreateDesktopW", 7)
    recorder.SetThreadDesktop = _Recording(u"SetThreadDesktop", 1)
    monkeypatch.setattr(conftest.ctypes, u"WinDLL",
                        lambda *a, **k: recorder, raising=False)
    assert conftest.use_a_private_desktop() == u""
    for fn in (u"CreateDesktopW", u"SetThreadDesktop"):
        assert declared.get(fn) == {u"argtypes", u"restype"}, (
            u"%s is called with %s declared — an undeclared 64-bit handle "
            u"is truncated silently and the windows come back to Sonic's "
            u"desktop" % (fn, sorted(declared.get(fn, ())) or u"nothing"))

    for label, create, set_thread in ((u"CreateDesktop", 0, 1),
                                      (u"SetThreadDesktop", 41, 0)):
        # ⚠ `raising=False`: `ctypes.WinDLL` DOES NOT EXIST off Windows, and
        # without this the check dies with AttributeError on eight Linux and
        # macOS jobs — the identical mistake `test_off_WINDOWS_the_picker_...`
        # exists to record.
        monkeypatch.setattr(conftest.ctypes, u"WinDLL",
                            win32_where(create, set_thread), raising=False)
        reason = conftest.use_a_private_desktop()
        assert reason, (
            u"%s failed and it reported SUCCESS — the windows are back on "
            u"Sonic's desktop and nothing says so" % label)
        assert label in reason, \
            u"the reason does not name what failed: %r" % (reason,)


def test_entering_the_private_desktop_can_NEVER_fail_the_run(monkeypatch):
    u"""🚨 `_has_icon` called Win32 with no `argtypes`, raised
    `OverflowError: int too long to convert`, and **took down a whole smoke
    run** — 44 unrelated checks reported nothing. A comfort feature that can
    abort its host is worse than no comfort feature.
    """
    import conftest

    class Hostile(object):
        def __getattr__(self, name):
            raise RuntimeError(u"no")

    monkeypatch.setattr(conftest.ctypes, u"WinDLL",
                        lambda *a, **k: Hostile(), raising=False)
    monkeypatch.delenv(conftest.SHOW_WINDOWS, raising=False)
    reason = conftest.use_a_private_desktop()
    assert isinstance(reason, type(u"")) and reason, \
        u"a broken Win32 did not come back with a reason: %r" % (reason,)


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


def test_the_FROZEN_branch_looks_for_the_cli_BESIDE_the_executable(monkeypatch):
    u"""🚨 RUNBOOK 4c TRAP 1, AND IT DECIDES THE WHOLE STANDALONE BUILD.

    `STANDALONE-BUILD-SCOPE.md`: *ship only the GUI and every single run fails
    at launch.* Frozen, `sys.executable` is the bundle, so `-m tsubasa` would
    re-enter the GUI and open a SECOND WINDOW rather than run the CLI — the
    console entry point beside it is used instead, which is why the `.spec`
    file puts both executables in one `COLLECT`.

    ⛔ **This branch had never run**; its own docstring said it was
    `10-deployment.md`'s to finish at 4a. Written here before the first build,
    so the freezer is not the thing that discovers it.

    ⚠ Both platforms are driven, not just this machine's — the `.exe` suffix
    is decided inside the branch, and macOS resumes against the POSIX half
    (`STANDALONE-BUILD-SCOPE.md` §8b step 2).
    """
    monkeypatch.delenv(u"TSUBASA_CLI", raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    home = os.path.join(os.sep + u"apps", u"tsubasa")

    monkeypatch.setattr(sys, "executable",
                        os.path.join(home, u"tsubasa-gui.exe"))
    monkeypatch.setattr(sys, "platform", u"win32")
    assert RUN.cli_argv() == [os.path.join(home, u"tsubasa.exe")]

    monkeypatch.setattr(sys, "executable", os.path.join(home, u"tsubasa-gui"))
    monkeypatch.setattr(sys, "platform", u"darwin")
    assert RUN.cli_argv() == [os.path.join(home, u"tsubasa")]


def test_an_UNFROZEN_run_still_goes_through_the_interpreter(monkeypatch):
    u"""⚠ The other direction, and the one every developer runs. A branch that
    fires unconditionally would send a source checkout looking for a
    `tsubasa.exe` that does not exist — green on the build machine, broken
    everywhere this is developed."""
    monkeypatch.delenv(u"TSUBASA_CLI", raising=False)
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    assert RUN.cli_argv() == [sys.executable, u"-m", u"tsubasa"]


@pytest.mark.skipif(not sys.platform.startswith("win"),
                    reason=u"needs a display")
def test_a_CLI_THAT_CANNOT_BE_SPAWNED_says_so_and_does_not_wedge_the_app(
        tmp_path):
    u"""🚨 THE NEGATIVE OF TRAP 1, AND IT WAS A SILENT NO-OP.

    Found by an adversarial pass, 2026-09-17, against three green checks that
    had only ever driven the branch POSITIVELY. With `tsubasa.exe` removed
    from beside the frozen GUI, pressing Sync produced **nothing at all** —
    `neg-after.png` was byte-identical to the shot before the click — and the
    app was then dead for good:

      * `Popen` raised `FileNotFoundError` out of an unguarded
        `self.runner.start()`;
      * `self.runner` had already been assigned, so `running` stayed True FOR
        EVER — the button never left *Stop*, the next click went to `stop()`
        and raised `NotStarted`, and **restoring the missing file did not
        help.** Only killing the app did;
      * and `console=False` means `sys.stderr` is None, so Tk's default
        handler printed the traceback precisely nowhere.

    ⛔ Reach is not hypothetical: `README-FIRST.txt` warns that Defender may
    quarantine a fresh download, and quarantining one executable and not the
    other produces exactly this.

    ⭐ Asserted on the SCREEN, not on a flag — `doctrine/verification`, and the
    original symptom was a window that did not change.
    """
    def refuses(folder, **opts):
        def popen(argv, **kwargs):
            raise OSError(2, u"The system cannot find the file specified")
        return RUN.Runner(folder, popen=popen, **opts)

    root = _tk_root()
    from tsubasa.gui import app as APP
    s = SETTINGS.Settings({}, str(tmp_path / u"s.json"))
    app = APP.App(root, settings=s, runner_factory=refuses)
    try:
        app.folder_var.set(str(tmp_path))
        app.start()
        root.update()

        assert not app.running, u"the app is stuck believing a run is going"
        assert app.runner is None, u"the dead runner was kept"
        assert app.sync_btn.cget(u"text") == u"Sync", (
            u"the button still offers to stop a run that never began")
        said = app.message
        assert u"could not be started" in said, said
        assert u"tsubasa-gui.exe" in said, (
            u"the sentence never names the fix — that both executables live "
            u"in one folder: %r" % said)

        # ⭐ AND IT RECOVERS. The original defect survived putting the file
        # back, so a second attempt that works is the half that matters.
        app.runner_factory = lambda folder, **opts: RUN.Runner(
            folder, popen=fake_popen(stdout=ndjson(a_record()),
                                     stderr=u"1 synced\n", code=0), **opts)
        app.start()
        for _ in range(200):
            root.update()
            if app.run is not None:
                break
            time.sleep(0.01)
        assert app.run is not None, u"the app never recovered from the failure"
    finally:
        root.destroy()


@pytest.mark.skipif(not sys.platform.startswith("win"),
                    reason=u"needs a display")
def test_an_exception_in_ANY_callback_is_reported_rather_than_swallowed(
        tmp_path):
    u"""🚨 `console=False` MAKES EVERY BUTTON SILENT ON FAILURE.

    `sys.stderr` is None in a windowed build, Tk's default
    `report_callback_exception` prints there, `print` falls back to
    `sys.stdout` — also None — and `print` is then a documented no-op. CPython's
    own tkinter docstring says to override this when `sys.stderr` is None.

    ⭐ The net under every OTHER button, because the next one will not be found
    the way this one was. Asserted by driving a real Tk callback that raises
    and requiring the override to be reached.
    """
    from tsubasa.gui import app as APP
    root = _tk_root()
    try:
        seen = []
        APP._make_failures_visible(
            root, show=lambda title, detail: seen.append((title, detail)))
        assert root.report_callback_exception is not \
            APP.tk.Tk.report_callback_exception, u"the default was left in place"

        # ⭐ THROUGH A REAL BUTTON, not by calling the hook. Tk routes a
        # raising callback through `report_callback_exception` itself; a
        # direct call would prove the function works and say nothing about
        # whether Tk ever reaches it.
        button = APP.tk.Button(root, command=_raises)
        button.pack()
        root.update()
        button.invoke()
        root.update()

        assert seen, u"the exception was swallowed exactly as before"
        title, detail = seen[0]
        assert u"a button blew up" in detail, detail
        assert u"ValueError" in detail, detail
        assert u"tsubasa" in title, title
    finally:
        root.destroy()


def _raises():
    u"""A callback that fails, for the check above. ⚠ Module level: Tk calls
    it through its own C loop, so a closure defined inside a `try` is fine but
    reads as part of the test's control flow rather than as a fixture."""
    raise ValueError(u"a button blew up")


# ===========================================================================
# 🚨 THE MARK — RUNBOOK 4e. FIVE SURFACES, FIVE MECHANISMS
# ===========================================================================
#
# `BRANDING-SCOPE.md` §1: the title bar, the .exe's icon in Explorer, the
# in-app marks, the README and the settings window are FIVE different
# mechanisms. ⛔ *"The icon is set"* is five separate claims, and putting a
# logo in one place does not put it in any of the others.

def test_every_shipped_icon_size_loads_and_is_the_size_it_claims():
    u"""⚠ EVERY SIZE IS A REAL EXPORT — the pack has no vector source, so
    `image(24)` must return the 24 px file rather than the 256 resampled.
    That is the difference between a legible small icon and mush.

    ⛔ And a file named for a size it is not would be invisible otherwise:
    Tk scales silently.
    """
    from tsubasa.gui import branding as B

    sizes = B.available()
    assert sizes, u"no icon-*.png shipped inside the package at %s" % B.data_dir()
    assert 16 in sizes and 256 in sizes, sizes
    for size in sizes:
        assert os.path.isfile(B.icon_path(size))

    # ⛔ A ROOT IS BUILT RATHER THAN SKIPPED AROUND. `PhotoImage` needs a Tk
    # interpreter, and the first version simply skipped when there was none —
    # which on a headless runner is coverage on nobody's machine. `_tk_root`
    # already skips honestly if there is genuinely no display.
    root = _tk_root()
    try:
        for size in sizes:
            img = B.image(size, master=root)
            assert img is not None, B.icon_path(size)
            assert (img.width(), img.height()) == (size, size), (
                u"icon-%d.png is %dx%d — a file named for a size it is not "
                u"would be invisible, because Tk scales silently"
                % (size, img.width(), img.height()))
    finally:
        root.destroy()


def test_an_icon_that_cannot_be_read_is_NEVER_fatal(monkeypatch):
    u"""⛔ `doctrine/architecture`: *instruction, not refusal.* A decorative
    asset may not be load-bearing — a missing icon is a plainer window, not a
    reason the application does not open."""
    from tsubasa.gui import branding as B

    monkeypatch.setattr(B, "data_dir", lambda: u"/nowhere-at-all")
    assert B.available() == []
    assert B.image(32) is None

    class Root(object):
        def iconphoto(self, *a):
            raise RuntimeError(u"no")

    assert B.set_window_icon(Root()) is False


@pytest.mark.skipif(not sys.platform.startswith("win"),
                    reason=u"needs a display")
def test_the_icons_are_NOT_cached_across_interpreters_and_the_root_holds_them():
    u"""🚨 A `PhotoImage` BELONGS TO THE Tk INTERPRETER THAT CREATED IT.

    ⛔ The first design cached images in the module, for the life of the
    process. It broke **eighteen checks at once** with `TclError: image
    "pyimage1" doesn't exist`: the second root in a process was handed an
    image built by the first, which had since been destroyed. ⚠ The product
    makes one root per launch and would never have seen it — a suite, an
    embedding application, or anything that reopens a window would.

    ⭐ So the module hands out a FRESH image and the ROOT holds it, because
    that is what the lifetime actually follows. Both halves are asserted here:
    a second root works, and the images survive the call that set them.
    """
    from tsubasa.gui import branding as B

    first = _tk_root()
    try:
        assert B.set_window_icon(first) is True
        assert getattr(first, u"_tsubasa_icons", None), (
            u"nothing holds the images, so Python frees them the moment "
            u"set_window_icon returns and the title bar goes blank")
    finally:
        first.destroy()

    # ⭐ THE REGRESSION ITSELF: a second interpreter, after the first is gone.
    second = _tk_root()
    try:
        assert B.set_window_icon(second) is True, (
            u"a second Tk root could not be given an icon — the images are "
            u"being shared across interpreters again")
        assert B.image(32, master=second) is not B.image(32, master=second), (
            u"image() is handing back the same object, which is the cache "
            u"that caused the regression")
    finally:
        second.destroy()


@pytest.mark.skipif(not sys.platform.startswith("win"),
                    reason=u"needs a display")
def test_the_window_carries_the_mark_and_so_do_its_dialogs(tmp_path):
    u"""🚨 `default=True` IS THE WHOLE REASON THE SETTINGS WINDOW GETS ONE.

    The first argument of `iconphoto` is `default`, and only when it is true
    do toplevels created LATER inherit the icon. With it false the main window
    is branded and every dialog is not, which reads as a bug rather than as a
    choice — `BRANDING-SCOPE.md` §1 surface 5.
    """
    from tsubasa.gui import app as APP
    from tsubasa.gui import branding as B

    root = _tk_root()
    try:
        asked = []
        real = root.iconphoto
        root.iconphoto = lambda *a: asked.append(a) or real(*a)
        assert B.set_window_icon(root) is True
        assert asked, u"iconphoto was never called"
        assert asked[0][0] is True, (
            u"iconphoto(default=%r) — with it false, every dialog opens "
            u"unbranded" % (asked[0][0],))
        assert len(asked[0]) > 2, (
            u"only one size was handed over, so Windows resamples it for the "
            u"title bar, Alt-Tab and the taskbar instead of picking")
    finally:
        root.destroy()


@pytest.mark.skipif(not sys.platform.startswith("win"),
                    reason=u"needs a display")
def test_the_mark_is_in_the_header_and_in_the_EMPTY_table_only(tmp_path):
    u"""⭐ RULED: *"needs to be somewhere very clean in the app itself"*, and
    *"nothing distracting."*

    So: the header bar always, and the empty table **only while it is empty**.
    ⛔ The visibility is DERIVED from the tree's own children on every repaint,
    not from a flag someone has to remember to clear — a boolean set at the
    start of a run and unset at the end has two places to be wrong, and one of
    them is a cancelled run.
    """
    from tsubasa.gui import app as APP

    root, app = _app(tmp_path)
    root.update()
    try:
        if app.mark_small is None:
            pytest.skip(u"no icon available on this host")
        assert app.mark_small.width() == 24
        assert app.mark_big.width() == 128

        # empty -> the big mark is placed
        assert not app.tree.get_children()
        app._repaint()
        root.update_idletasks()
        assert app.empty_mark.winfo_ismapped(), (
            u"the empty table shows no mark at all")

        # a row arrives -> it goes away
        app.tree.insert(u"", u"end", text=u"✓", values=(u"1", u"a", u"b",
                                                        u"c", u"d"))
        app._repaint()
        root.update_idletasks()
        assert not app.empty_mark.winfo_ismapped(), (
            u"the mark is still there with results on screen, competing with "
            u"the thing the person came to read")

        # and it comes back
        app.tree.delete(*app.tree.get_children())
        app._repaint()
        root.update_idletasks()
        assert app.empty_mark.winfo_ismapped()
    finally:
        root.destroy()


def test_the_empty_state_mark_is_GENUINELY_fainter_and_not_pre_blended():
    u"""⚠ *"Nothing distracting"* — and the first version simply used the
    full-strength mark while the scope said *faded*. A claim in prose that the
    pixels do not support is the same defect as any other false claim.

    ⭐ TRANSLUCENT, NOT PRE-BLENDED ONTO THE THEME COLOUR. Compositing onto
    `#15171b` at build time would bake this window's background into a file
    that ships in the PACKAGE — so any application embedding tsubasa gets our
    ground baked in, and changing the theme leaves a halo. Asserted on the
    ALPHA channel, which is what distinguishes the two.
    """
    from tsubasa.gui import branding as B

    PIL = pytest.importorskip(u"PIL.Image")
    faint_path = B.icon_path(128, faint=True)
    assert os.path.isfile(faint_path), (
        u"%s is missing — it is DERIVED by packaging/make_icon.py" % faint_path)

    full = PIL.open(B.icon_path(128)).convert("RGBA")
    faint = PIL.open(faint_path).convert("RGBA")
    assert full.size == faint.size

    full_a = sum(full.split()[3].getdata())
    faint_a = sum(faint.split()[3].getdata())
    assert faint_a < full_a * 0.7, (
        u"the faint variant carries %d alpha against %d — it is not fainter"
        % (faint_a, full_a))
    assert faint_a > 0, u"the faint variant is completely invisible"

    # ⛔ Still translucent where the mark is absent: a pre-blended file would
    # have alpha 255 everywhere, having painted the background in.
    assert min(faint.split()[3].getdata()) == 0, (
        u"the faint mark has no transparent pixels at all, so it was blended "
        u"onto a background colour rather than made translucent")


def test_the_ico_exists_and_is_genuinely_MULTI_SIZE():
    u"""🚨 THE `.ico` IS WHAT EXPLORER, THE TASKBAR AND ALT-TAB READ, and it
    is a different mechanism from the window icon entirely — a Win32 resource
    compiled into the executable and read **before Python starts.** A frozen
    app with `iconphoto` set still shows PyInstaller's default without it.

    ⛔ And a single-size `.ico` is the failure that looks like success:
    Windows accepts it and resamples 256 down to 16, which is mush at exactly
    the size people see most.
    """
    from tsubasa.gui import branding as B

    path = B.ico_path()
    assert os.path.isfile(path), (
        u"%s is missing — it is DERIVED from the shipped PNGs by "
        u"packaging/make_icon.py, not a separate asset" % path)
    PIL = pytest.importorskip(u"PIL.Image")
    with PIL.open(path) as ico:
        sizes = sorted(set(w for w, _h in ico.info.get(u"sizes", ())))
    for want in (16, 32, 48, 256):
        assert want in sizes, (
            u"the .ico carries %s and is missing %d" % (sizes, want))


def _descendants(widget):
    u"""Every widget under `widget`, itself included. -> [widget]

    ⭐ WALKED, NEVER ENUMERATED BY NAME. `LEDGER-HOT.md`: *a check that
    hand-enumerates which keys to compare stops guarding every key added
    later.* A button added to this window next month is covered by the hover
    check without anyone remembering to come back here.
    """
    out = [widget]
    for child in widget.winfo_children():
        out.extend(_descendants(child))
    return out


# ===========================================================================
# 🚨 INTERACTION — RUNBOOK 4d, and every one of these was a REPORTED defect
# ===========================================================================
#
# Sonic, 2026-09-17: *"all buttons need a hover over color change… when you
# click on browse it has the thinking icon, the gui freezes… when you hover
# over the category headers they turn white. it looks bad."*
#
# ⭐ All three were invisible to 103 green checks, because every one of them
# is about a STATE the suite never entered: the pointer being over something.

def test_shade_LIFTS_a_near_black_ground_visibly(monkeypatch):
    u"""🚨 A MULTIPLY WOULD NOT HAVE WORKED, and that is why this is a check.

    Scaling each channel by `1 + amount` moves `#15171b` to `#171920` — a
    step nobody can see — because it is proportional to a value that is
    already almost zero. Interpolating toward white gives the same
    perceptual step wherever it starts.
    """
    from tsubasa.gui import app as APP
    from tsubasa.gui import app as APP

    ground = APP._shade(APP.BG, APP.HOVER_LIFT)
    assert ground != APP.BG
    gap = min(int(ground[i:i + 2], 16) - int(APP.BG.lstrip(u"#")[i - 1:i + 1], 16)
              for i in (1, 3, 5))
    assert gap >= 12, (
        u"a %s ground lifted to %s — %d/255 is not a visible hover"
        % (APP.BG, ground, gap))

    # ⛔ AND IT MUST NOT OVERSHOOT. A lift that saturates turns a subtle
    # affordance into a flash.
    #
    # 🚨 THE OLD FORM OF THIS WAS ARITHMETICALLY INCAPABLE OF FAILING:
    # it sliced two hex characters and asserted `<= 255`, and the maximum
    # of every two-character hex string IS 255. An adversary broke `_shade`
    # into emitting `#12e12d12d` — ten characters — and the guard passed;
    # worse, **Tk ACCEPTS that string** as a 12-bit-per-channel colour and
    # silently renders the wrong one. ⭐ So the SHAPE is what has to be
    # asserted, not a bound that the parse already guarantees.
    assert len(ground) == 7 and ground[0] == u"#", (
        u"_shade produced %r, which is not #rrggbb — Tk will accept some "
        u"longer forms and render a different colour without complaining"
        % (ground,))
    for channel in (ground[1:3], ground[3:5], ground[5:7]):
        assert 0 <= int(channel, 16) <= 255

    assert APP._shade(u"#ffffff", 0.10) == u"#ffffff", u"white cannot lift"
    assert APP._shade(u"#000000", -0.10) == u"#000000", u"black cannot sink"


def test_the_hover_direction_follows_the_SURFACE_not_one_rule():
    u"""⭐ A dark recessed control LIFTS; a bright filled one DEEPENS.

    Both read as *pressed toward you*, and doing the same thing to both does
    not. ⚠ MEASURED, and it is why this is not one rule: lifting the accent
    `#6aa8d8` by 10% gives `#79b1dc` — a 15/255 step on an already-bright
    fill, which did not survive a screenshot — while the same 10% on the dark
    `#2b3038` is obvious. The same number is a different amount of signal
    depending on where it starts.

    ⛔ Asserted over EVERY surface the theme defines, read off the module, so
    a colour added later is covered without anyone coming back here.
    """
    from tsubasa.gui import app as APP

    surfaces = [APP.BG, APP.PANEL, APP.EDGE, APP.SEL,
                APP.ACCENT, APP.OK, APP.CUT, APP.BAD, APP.ERR]
    for colour in surfaces:
        hover = APP._hover_of(colour)
        step = max(abs(int(hover[i:i + 2], 16)
                       - int(colour.lstrip(u"#")[i - 1:i + 1], 16))
                   for i in (1, 3, 5))
        assert step >= 10, (
            u"%s -> %s is a %d/255 step; nobody sees that" % (colour, hover,
                                                              step))
        lifted = APP._luma(hover) > APP._luma(colour)
        assert lifted == (APP._luma(colour) < 0.5), (
            u"%s (luma %.2f) went %s — a dark surface must lift and a bright "
            u"one must deepen" % (colour, APP._luma(colour),
                                  u"lighter" if lifted else u"darker"))

    # ⚠ Green carries most of the perceived light and blue almost none, so a
    # flat average picks the wrong direction for this window's accent.
    assert APP._luma(u"#0000ff") < APP._luma(u"#00ff00")


@pytest.mark.skipif(not sys.platform.startswith("win"),
                    reason=u"needs a display")
def test_every_button_answers_the_pointer_and_puts_itself_back(tmp_path):
    u"""🚨 REPORTED: *"all buttons need a hover over color change."*

    ⛔ `activebackground=bg` is not a hover. Tk's `active` state is the
    PRESSED state for a Button, and it was set to the resting colour anyway —
    so the window's controls did not move under the pointer at all.

    ⭐ Walks the real widgets rather than naming them, so a button added
    later is covered without anyone remembering to come back here.
    """
    from tsubasa.gui import app as APP
    import tkinter as tk
    root, app = _app(tmp_path)
    # ⚠ MAPPED FIRST. Tk does not deliver `<Enter>` to an unmapped
    # widget and `winfo_rooty()` answers 0 for one, so a check that
    # skipped this would report *"no hover"* and *"not at the
    # bottom"* against a window that does both. `update_idletasks`
    # is not enough — the window has to actually map.
    root.update()
    try:
        buttons = [w for w in _descendants(root)
                   if isinstance(w, tk.Button)]
        assert len(buttons) >= 3, u"expected Browse, Sync and the gear: %r" % buttons
        for b in buttons:
            resting = b.cget(u"bg")
            b.event_generate(u"<Enter>")
            root.update_idletasks()
            hovered = b.cget(u"bg")
            assert hovered != resting, (
                u"%r does not change under the pointer" % b.cget(u"text"))
            b.event_generate(u"<Leave>")
            root.update_idletasks()
            assert b.cget(u"bg") == resting, (
                u"%r kept its hover colour after the pointer left"
                % b.cget(u"text"))
    finally:
        root.destroy()


@pytest.mark.skipif(not sys.platform.startswith("win"),
                    reason=u"needs a display")
def test_the_hover_reads_the_CURRENT_colour_not_the_one_it_was_built_with(
        tmp_path):
    u"""🚨 THE SYNC BUTTON LEGITIMATELY CHANGES COLOUR MID-RUN.

    It goes accent → red and *Sync* → *Stop* while a run is going. A hover
    that closed over the colour passed to the constructor would restore the
    OLD one on leave — so hovering a running Stop button would quietly turn it
    blue again, which is worse than no hover at all.
    """
    from tsubasa.gui import app as APP
    root, app = _app(tmp_path)
    # ⚠ MAPPED FIRST. Tk does not deliver `<Enter>` to an unmapped
    # widget and `winfo_rooty()` answers 0 for one, so a check that
    # skipped this would report *"no hover"* and *"not at the
    # bottom"* against a window that does both. `update_idletasks`
    # is not enough — the window has to actually map.
    root.update()
    try:
        b = app.sync_btn
        b.configure(bg=APP.BAD)          # as `_repaint` does mid-run
        b.event_generate(u"<Enter>")
        root.update_idletasks()
        assert b.cget(u"bg") != APP.BAD
        b.event_generate(u"<Leave>")
        root.update_idletasks()
        assert b.cget(u"bg") == APP.BAD, (
            u"leaving restored %s, not the colour the button actually had"
            % b.cget(u"bg"))
    finally:
        root.destroy()


def test_the_theme_helpers_NEVER_RAISE_on_an_ordinary_Tk_colour():
    u"""🚨 `_hover_of` RAISED `ValueError` ON EVERY ORDINARY TK COLOUR, AND IT
    RUNS INSIDE AN EVENT HANDLER. `enter` calls `_hover_of(widget.cget("bg"))`
    and Tk returns whatever the widget holds — `#fff`, `red`, `gray50`,
    `SystemButtonFace`. Each of those went straight out of a `<Enter>` binding
    into `report_callback_exception`.

    ⚠ Latent, not live: every palette constant is 6-digit hex today, and no
    check fed anything else — which is exactly why an adversary found it and
    the suite did not. One stock widget, or one `#fff` in the palette, makes it
    live for every hover in the window.

    ⭐ A PAINT PATH FAILS SOFT: an unshadeable colour comes back unchanged, so
    that widget simply has no hover — a missing affordance rather than a
    traceback.
    """
    from tsubasa.gui import app as APP

    for colour in (u"red", u"white", u"gray50", u"SystemButtonFace", u"",
                   u"#", u"#12", u"#aabbccdd", u"#12e12d12d", u"#zzzzzz",
                   None, 0):
        assert APP._shade(colour, 0.10) == colour, colour
        assert APP._hover_of(colour) == colour, colour
        APP._luma(colour)                 # must not raise
        APP._press_of(colour)             # nor must this

    # ⛔ AND `#rgb` EXPANDS BY REPETITION, NOT BY PADDING. `#fff` is white;
    # reading it as `#0f0f0f` would be a silently WRONG colour, which is worse
    # than an error.
    assert APP._channels(u"#fff") == [255, 255, 255]
    assert APP._channels(u"#abc") == [170, 187, 204]
    assert APP._luma(u"#fff") > 0.99 and APP._luma(u"#000") < 0.01

    # ⭐ AND THE REAL PALETTE IS UNCHANGED BY THE REWRITE — the whole point of
    # hardening a parser is that it still parses what it used to.
    assert APP._shade(u"#15171b", 0.10) == u"#2c2e32"
    assert APP._shade(u"#6aa8d8", -0.08) == u"#629bc7"


@pytest.mark.skipif(not sys.platform.startswith("win"),
                    reason=u"needs a display")
def test_the_PRESS_state_is_VISIBLE_and_is_not_just_the_hover_colour(tmp_path):
    u"""🚨 PRESSING SYNC OR STOP DID NOTHING VISIBLE, AND 126 CHECKS WERE
    GREEN OVER IT — because nothing asserted `activebackground` at all.

    `_hover_of` DEEPENS a bright fill by `PRESS_SINK`, and the press state was
    `_shade(base, -PRESS_SINK)` — the same expression. Measured before the fix:
    **identical on 7 of 11 palette colours**, which is every bright fill in the
    window (ACCENT, BAD, OK, CUT, ERR, INK, DIM) — i.e. on exactly the buttons
    a person clicks. Found by an adversarial pass.

    ⭐ **THE PAIR THAT MATTERS IS HOVER → PRESS, NOT REST → PRESS**, because you
    are always hovering when you press. That is what this asserts.
    """
    from tsubasa.gui import app as APP

    palette = [n for n in dir(APP)
               if n.isupper() and isinstance(getattr(APP, n), str)
               and getattr(APP, n).startswith(u"#")]
    assert len(palette) >= 8, u"the palette did not resolve: %r" % (palette,)

    for name in palette:
        base = getattr(APP, name)
        hover, press = APP._hover_of(base), APP._press_of(base)
        assert press != hover, (
            u"%s: pressing looks identical to hovering (%s) — the button has "
            u"no press feedback" % (name, press))
        assert press != base, u"%s: pressing looks identical to resting" % name

    # ⭐ AND ON A REAL WIDGET, not only in the arithmetic.
    root, app = _app(tmp_path)
    root.update()
    try:
        for btn in (app.sync_btn, app.browse_btn):
            bg = str(btn.cget(u"bg"))
            active = str(btn.cget(u"activebackground"))
            assert active == APP._press_of(bg), (
                u"%r presses to %s, which is not the press colour for %s"
                % (str(btn.cget(u"text")), active, bg))
            assert active != APP._hover_of(bg)
    finally:
        root.destroy()


@pytest.mark.skipif(not sys.platform.startswith("win"),
                    reason=u"needs a display")
def test_hovering_TWICE_without_leaving_does_not_stick_the_button_lit(tmp_path):
    u"""🚨 IT RATCHETED. `enter` wrote `_resting` unconditionally from the
    CURRENT background — which after one hover is the hover colour — so a
    second `<Enter>` without a `<Leave>` between them captured the wrong
    resting colour and `<Leave>` restored the button to *lit*. And it
    compounded. Measured on EDGE before the fix:

        1 x <Enter> then <Leave>:  #2b3038 -> #2b3038   ok
        2 x <Enter> then <Leave>:  #2b3038 -> #40454c   *** STUCK ***
        3 x <Enter> then <Leave>:  #2b3038 -> #53585e   *** STUCK ***

    ⚠ The old check sent exactly one `<Enter>` and one `<Leave>`, so it could
    not see this. Tk delivers a second `<Enter>` without an intervening
    `<Leave>` across a grab/ungrab, which is what a modal dialog does.
    """
    root, app = _app(tmp_path)
    root.update()
    try:
        btn = app.browse_btn
        base = str(btn.cget(u"bg"))
        for repeats in (1, 2, 3):
            btn.configure(bg=base)
            btn._resting = None
            for _ in range(repeats):
                btn.event_generate(u"<Enter>")
                root.update_idletasks()
            btn.event_generate(u"<Leave>")
            root.update_idletasks()
            assert str(btn.cget(u"bg")) == base, (
                u"%d <Enter> then <Leave> left the button at %s, not %s"
                % (repeats, btn.cget(u"bg"), base))
    finally:
        root.destroy()


@pytest.mark.skipif(not sys.platform.startswith("win"),
                    reason=u"needs a display")
def test_the_press_colour_FOLLOWS_the_button_when_Sync_becomes_Stop(tmp_path):
    u"""🚨 A RED STOP BUTTON FLASHED BLUE WHEN PRESSED. `_repaint` set `bg`
    accent → red and never touched `activebackground`, so the press colour was
    the one from before the run started — stale for the whole run, until a
    hover in-and-out happened to repair it (`_interactive`'s `<Leave>` was the
    only writer).

    ⭐ This is the general shape worth remembering: **a derived attribute that
    only one event handler maintains is stale everywhere that handler does not
    run.**
    """
    from tsubasa.gui import app as APP
    root, app = _app(tmp_path)
    root.update()
    try:
        # ⚠ `running` is a read-only property derived from `runner`, so it
        # is driven the way the app drives it. That is the better check
        # anyway — assigning to it would have tested a field the app does
        # not have.
        class _Going(object):
            def finished(self):
                return None

        for runner, want in ((None, APP.ACCENT), (_Going(), APP.BAD)):
            app.runner = runner
            assert app.running is (runner is not None)
            app._repaint()
            root.update_idletasks()
            assert str(app.sync_btn.cget(u"bg")) == want
            assert str(app.sync_btn.cget(u"activebackground")) == \
                APP._press_of(want), (
                    u"running=%s: the button is %s but presses to %s, which "
                    u"belongs to the other state"
                    % (app.running, want,
                       app.sync_btn.cget(u"activebackground")))
    finally:
        root.destroy()


@pytest.mark.skipif(not sys.platform.startswith("win"),
                    reason=u"needs a display")
def test_a_run_that_starts_UNDER_THE_POINTER_survives_the_pointer_leaving(
        tmp_path):
    u"""🚨 THE COMMON PATH, AND IT WAS BROKEN. You click **Sync** — so the
    pointer is on the button — the run starts and `_repaint` turns it red
    **Stop**. Then you move the mouse away and it turned back into a blue
    **Sync** while the run was still going.

        rest #6aa8d8 -> hover #629bc7 -> run starts #e0736c
        -> pointer leaves #6aa8d8   *** blue again, mid-run ***

    `<Leave>` restored `_resting`, captured BEFORE the repaint.

    ⭐ **FOUND BY CHASING A MUTANT THAT SURVIVED.** The mutation said
    `<Leave>`'s press-colour repair was not load-bearing; the reason it was
    not was this defect sitting underneath it. `doctrine/verification`: *a
    surviving mutant is information either way — find out which.*

    ⚠ The sibling check drives repaint-THEN-hover, which always worked.
    This one drives hover-THEN-repaint, which is the order a person makes.
    """
    from tsubasa.gui import app as APP

    root, app = _app(tmp_path)
    root.update()
    try:
        btn = app.sync_btn
        btn.event_generate(u"<Enter>")          # the pointer is on Sync
        root.update_idletasks()

        class _Going(object):
            def finished(self):
                return None

        app.runner = _Going()                   # the click started a run
        app._repaint()
        root.update_idletasks()
        assert str(btn.cget(u"bg")) == APP.BAD

        btn.event_generate(u"<Leave>")          # and you move away
        root.update_idletasks()
        assert str(btn.cget(u"bg")) == APP.BAD, (
            u"the running Stop button went back to %s when the pointer "
            u"left — it should still be red" % btn.cget(u"bg"))
        assert str(btn.cget(u"activebackground")) == APP._press_of(APP.BAD)
    finally:
        root.destroy()


@pytest.mark.skipif(not sys.platform.startswith("win"),
                    reason=u"needs a display")
def test_a_DISABLED_button_does_not_pretend_to_be_live(tmp_path):
    u"""⚠ A disabled control that lights up under the pointer is a promise it
    will not keep."""
    from tsubasa.gui import app as APP
    root, app = _app(tmp_path)
    # ⚠ MAPPED FIRST. Tk does not deliver `<Enter>` to an unmapped
    # widget and `winfo_rooty()` answers 0 for one, so a check that
    # skipped this would report *"no hover"* and *"not at the
    # bottom"* against a window that does both. `update_idletasks`
    # is not enough — the window has to actually map.
    root.update()
    try:
        b = app.sync_btn
        b.configure(state=u"disabled")
        resting = b.cget(u"bg")
        b.event_generate(u"<Enter>")
        root.update_idletasks()
        assert b.cget(u"bg") == resting
    finally:
        root.destroy()


@pytest.mark.skipif(not sys.platform.startswith("win"),
                    reason=u"needs a display")
def test_the_column_headings_do_NOT_turn_white_under_the_pointer(tmp_path):
    u"""🚨 REPORTED: *"it's a darkish theme, when you hover over the category
    headers they turn white. it looks bad."*

    ⛔ `style.configure` sets the RESTING look and says nothing about any
    state, so clam's own `active` map was still in force — and clam is a
    **light** theme, so its active background is near-white. The column
    titles flashed white on a #1c1f25 panel on every pass of the mouse.

    ⭐ Asserted as a BRIGHTNESS BOUND, not as an exact colour: the point is
    *not white*, and pinning the hex would fail the next time the panel
    colour is tuned.
    """
    from tsubasa.gui import app as APP
    from tkinter import ttk
    root, app = _app(tmp_path)
    try:
        style = ttk.Style(root)
        mapped = dict((state[0], colour) for state, colour in
                      [(s[:-1], s[-1]) for s in
                       style.map(u"T.Treeview.Heading", u"background")])
        assert u"active" in mapped, (
            u"no `active` background is mapped, so clam's near-white default "
            u"is still what the pointer produces: %r" % (mapped,))
        hover = mapped[u"active"]
        brightness = max(int(hover.lstrip(u"#")[i:i + 2], 16)
                         for i in (0, 2, 4))
        assert brightness < 110, (
            u"the heading hover is %s — brightness %d/255 is a light flash in "
            u"a dark window" % (hover, brightness))
        # ⭐ And it must still be a VISIBLE answer, not merely not-white.
        assert hover != APP.PANEL, u"the heading does not react at all"
    finally:
        root.destroy()


@pytest.mark.skipif(not sys.platform.startswith("win"),
                    reason=u"needs a display")
def test_the_credit_sits_at_the_very_bottom_right_and_links_out(tmp_path):
    u"""⭐ RULED: *"at the very bottom include a 'Created by SonicSandbox'…
    bottom right in faded text so its not in the way but there. And the
    github link."*

    ⚠ Asserted by GEOMETRY, not by existence — *at the very bottom* and
    *bottom right* are the requirement, and a label that exists somewhere
    else satisfies neither.
    """
    from tsubasa.gui import app as APP
    root, app = _app(tmp_path)
    # ⚠ MAPPED FIRST. Tk does not deliver `<Enter>` to an unmapped
    # widget and `winfo_rooty()` answers 0 for one, so a check that
    # skipped this would report *"no hover"* and *"not at the
    # bottom"* against a window that does both. `update_idletasks`
    # is not enough — the window has to actually map.
    root.update()
    try:
        root.update_idletasks()
        credit, link = app.credit_lbl, app.github_lbl
        assert u"SonicSandbox" in credit.cget(u"text")

        # below the counts strip -- the counts are what gets read, this is not
        assert credit.winfo_rooty() > app.elapsed_lbl.winfo_rooty(), (
            u"the credit is not below the counts strip")
        # right half of the window
        centre = root.winfo_rootx() + root.winfo_width() // 2
        assert credit.winfo_rootx() > centre, u"the credit is not on the right"
        # and the link sits after the name, not before it
        assert link.winfo_rootx() > credit.winfo_rootx()

        # ⚠ FADED, and measured against DIM rather than by eye: the brief is
        # *not in the way*, so it must be quieter than the secondary text.
        faded = max(int(credit.cget(u"fg").lstrip(u"#")[i:i + 2], 16)
                    for i in (0, 2, 4))
        secondary = max(int(APP.DIM.lstrip(u"#")[i:i + 2], 16)
                        for i in (0, 2, 4))
        assert faded < secondary, (
            u"the credit (%s) is not quieter than DIM (%s)"
            % (credit.cget(u"fg"), APP.DIM))

        # ⭐ UNDERLINED AT REST. The reference Sonic gave renders the link
        # word underlined; an earlier draft underlined only on hover because
        # it reads tidier, which is a preference where the reference is a
        # requirement.
        import tkinter.font as tkfont
        assert tkfont.Font(font=link.cget(u"font")).actual(u"underline"), (
            u"the GitHub link is not underlined, so it does not look like a "
            u"link until the pointer is already on it")
        assert link.cget(u"cursor") == u"hand2"
        assert link.cget(u"fg") == APP.ACCENT

        # 🚨 THIS USED TO REBIND THE LINK AND THEN ASSERT ITS OWN LAMBDA.
        # `bind()` without `add="+"` DISCARDS the handler the app
        # installed, so the check proved only that Tk delivers
        # `<Button-1>` to a Label. Measured by an adversary: deleting the
        # app's real binding, pointing the URL at `http://evil.example/pwn`,
        # and rebinding the trigger from a CLICK to `<Enter>` — so that
        # merely moving the pointer across the credit launched a browser —
        # every one of them stayed green.
        #
        # ⭐ ONLY THE OPENER IS STUBBED NOW. The binding, the event and the
        # URL are all the app's own.
        # ⚠ THE BROWSER IS THE SEAM, not `_open_url`. `_link` closes over
        # the opener at construction time, so replacing `app._open_url`
        # afterwards cannot reach the binding — which is exactly why the
        # old version of this check rebound the label instead, and thereby
        # stopped testing the app at all. Stubbing `webbrowser.open` drives
        # the WHOLE real chain: the app's binding, the app's `_open_url`,
        # and the app's URL.
        import webbrowser

        opened = []
        real_open = webbrowser.open
        webbrowser.open = lambda url, *a, **k: opened.append(url)
        try:
            link.event_generate(u"<Button-1>")
        finally:
            webbrowser.open = real_open
        root.update_idletasks()
        assert opened == [APP.HOME_URL], (
            u"clicking the credit link opened %r, not the project" % opened)

        # ⛔ AND IT MUST NOT FIRE ON HOVER. A browser launching because the
        # pointer crossed a label is a real shape of this defect, and the
        # old check could not tell the two events apart.
        opened[:] = []
        webbrowser.open = lambda url, *a, **k: opened.append(url)
        try:
            link.event_generate(u"<Enter>")
            link.event_generate(u"<Motion>")
            link.event_generate(u"<Leave>")
        finally:
            webbrowser.open = real_open
        assert opened == [], (
            u"moving the pointer over the credit opened %r" % opened)
        assert APP.HOME_URL.startswith(u"https://github.com/")
    finally:
        root.destroy()


@pytest.mark.skipif(not sys.platform.startswith("win"),
                    reason=u"needs a display")
def test_browse_owns_its_dialog_and_starts_somewhere(tmp_path):
    u"""🚨 REPORTED: *"when you click on browse it has the thinking icon, the
    gui freezes."*

    ⚠ MEASURED, and it was never hung: `IsHungAppWindow` stayed False
    throughout. ⛔ So threading was never the fix, and could not have been — a
    native modal must pump messages on the thread owning its parent. Two real
    things were wrong: the dialog had **no owner**, so Windows could not block
    the right window; and it started **nowhere**, so it walked the whole shell
    namespace behind a wait cursor.

    ⛔ AND THERE IS DELIBERATELY NO BUSY CURSOR — see
    `test_a_timer_CANNOT_fire_while_the_modern_dialog_is_up` below, which is
    the check that stops one being re-added.
    """
    from tsubasa.gui import app as APP

    root, app = _app(tmp_path)
    root.update()
    try:
        seen = {}

        def fake_ask(parent=None, title=u"", start=u""):
            seen.update(parent=parent, title=title, start=start,
                        cursor=str(root.cget(u"cursor")))
            return str(tmp_path)

        monkey = APP._folderpick.ask
        APP._folderpick.ask = fake_ask
        try:
            app.folder_var.set(str(tmp_path))
            app.browse()
        finally:
            APP._folderpick.ask = monkey

        assert seen[u"parent"] == root.winfo_id(), u"the dialog is not owned"
        assert seen[u"start"] == str(tmp_path), u"it starts nowhere"
        assert seen[u"cursor"] == u"", (
            u"a busy cursor is being set again: %r" % seen[u"cursor"])
        assert str(root.cget(u"cursor")) == u"", u"the cursor was left set"

        # ⛔ AND ON THE FAILING PATH. The dialog can raise, and the window must
        # come out of it in the state it went in.
        def explodes(parent=None, title=u"", start=u""):
            raise OSError(u"the shell is having a day")

        APP._folderpick.ask = explodes
        try:
            with pytest.raises(OSError):
                app.browse()
        finally:
            APP._folderpick.ask = monkey
        assert str(root.cget(u"cursor")) == u""
    finally:
        root.destroy()


@pytest.mark.skipif(not sys.platform.startswith("win"),
                    reason=u"needs a display")
def test_browse_SCHEDULES_NO_TIMER_around_the_picker(tmp_path):
    u"""🚨 THIS REPLACES A CHECK THAT DID NOT WORK, AND THE STORY IS THE
    POINT.

    4d shipped a delayed busy cursor built on a true number — *29 Tk timer
    ticks during 3.4 s of open dialog* — measured against
    `filedialog.askdirectory()`, **the dialog `folderpick` had replaced
    minutes earlier, in the same step, by the same agent.** Re-measured on
    the shipped path, same harness, only the dialog differing:

        folderpick.ask()  (IFileOpenDialog)   0 ticks in 2.26 s
        filedialog.askdirectory()            48 ticks in 2.30 s

    ⛔ The feature could never fire, and it shipped. ⭐ **A measurement is
    about the thing it was measured on.**

    🚨**AND THE CHECK WRITTEN TO STOP IT BEING REBUILT DID NOT STOP IT.**
    It opened no dialog, never imported `folderpick`, and asserted that a
    timer does not fire during `time.sleep` — true of every single-threaded
    Python program ever written. Two adversaries independently rebuilt the
    dead feature verbatim and the suite stayed green; it was also flaky,
    failing 4 runs in 12 under load and being mis-attributed to two
    unrelated mutants.

    ⭐ **SO THIS ASSERTS THE MECHANISM INSTEAD OF THE FOLKLORE:** a busy
    cursor needs a timer, so `browse()` must schedule none. That is a fact
    about OUR code, checkable without a dialog and without Tk's scheduler
    being the subject.
    """
    from tsubasa.gui import app as APP

    root, app = _app(tmp_path)
    root.update()
    try:
        scheduled = []
        real_after = root.after

        def spy(*a, **k):
            if a and isinstance(a[0], int):
                scheduled.append(a[0])
            return real_after(*a, **k)

        seen = {}

        def blocking_ask(parent=None, title=u"", start=u""):
            # ⚠ THE FAKE BLOCKS, because the real one does. The previous
            # fake returned in microseconds, so `assert cursor == ""` could
            # only ever see an UNCONDITIONAL cursor and never a delayed one
            # — wrong in exactly the property the check was about. That is
            # the same mistake as the fake that pumped the event loop.
            time.sleep(0.40)
            seen[u"cursor"] = str(root.cget(u"cursor"))
            return str(tmp_path)

        monkey = APP._folderpick.ask
        APP._folderpick.ask = blocking_ask
        root.after = spy
        try:
            app.browse()
        finally:
            APP._folderpick.ask = monkey
            root.after = real_after

        assert scheduled == [], (
            u"browse() scheduled %r — a delayed busy cursor is being "
            u"rebuilt. It CANNOT fire: IFileOpenDialog::Show runs its modal "
            u"loop on the Tk thread, measured at 0 ticks. Re-measure "
            u"against the REAL dialog before reinstating anything."
            % (scheduled,))
        assert seen.get(u"cursor") == u"", (
            u"the cursor was %r while the picker was up"
            % (seen.get(u"cursor"),))
        assert str(root.cget(u"cursor")) == u""
    finally:
        root.destroy()


@pytest.mark.skipif(not sys.platform.startswith("win"),
                    reason=u"IFileOpenDialog is a Windows COM interface")
def test_the_COM_half_of_the_picker_ACTUALLY_RUNS_without_a_dialog(tmp_path):
    u"""🚨 NOTHING IN THIS SUITE EXECUTED THE COM HALF. MEASURED: the whole
    GUI suite ran **31 lines** of `folderpick.py`, and `_modern`,
    `_modern_is_possible`, `_classic`, `_guid`, `_item_from_path`, `_path_of`
    and `_release` had **zero** — the entire thing RUNBOOK 4d exists to add.
    Both checks that touch the gate patch AROUND it: one forces it True, the
    other forces it False, and neither runs the real one. An adversary set
    `_modern_is_possible()` to `return False`, reverting every Windows user to
    the 2001 dialog, and the suite stayed green.

    ⛔ **GREEN SAYS NOTHING ABOUT CODE THAT DOES NOT RUN.** Found by
    line-tracing, now `_work/probe_4i_5_what_the_suite_never_runs.py`.

    ⭐ **AND IT DOES NOT NEED A DIALOG.** `Show` is the only part that does;
    the shell-item plumbing underneath it round-trips a path through real COM
    with no window at all — which is what this drives. A broken CLSID, a
    wrong vtable index or an undeclared argtype fails here instead of in front
    of a person.
    """
    from tsubasa.gui import folderpick as FP

    assert FP._modern_is_possible() is True, (
        u"the modern picker is switched off on Windows — every user is back "
        u"on the 2001 dialog")

    # ⛔ COM MUST BE INITIALISED ON THIS THREAD FIRST, exactly as `_modern`
    # does before it touches anything. Without it
    # `SHCreateItemFromParsingName` fails and `_item_from_path` returns
    # None — and because that function swallows everything by design, the
    # failure is silent. ⚠ That is a real property worth knowing: the
    # "never raises" contract means a COM failure reads exactly like a
    # deleted folder, so the picker would start nowhere and say nothing.
    import ctypes

    COINIT_APARTMENTTHREADED = 0x2
    RPC_E_CHANGED_MODE = 0x80010106
    hr = ctypes.windll.combase.CoInitializeEx(
        None, COINIT_APARTMENTTHREADED)
    # ⚠ A thread already in MTA answers RPC_E_CHANGED_MODE and STAYS MTA;
    # the shell functions still work, so that is not a failure here.
    assert hr in (0, 1, RPC_E_CHANGED_MODE - (1 << 32), RPC_E_CHANGED_MODE), \
        u"CoInitializeEx said 0x%08x" % (hr & 0xFFFFFFFF)

    folder = tmp_path / u"日本語 folder"     # ⚠ not ASCII, on purpose
    folder.mkdir()

    item = FP._item_from_path(str(folder))
    assert item, u"SHCreateItemFromParsingName returned nothing for a real folder"
    try:
        SIGDN_FILESYSPATH = 0x80058000
        back = FP._path_of(item, SIGDN_FILESYSPATH)
        assert back == str(folder), (
            u"the path did not survive the round trip: %r -> %r"
            % (str(folder), back))
    finally:
        FP._release(item)

    # ⛔ AND THE DOCUMENTED NON-RAISING CONTRACT, which is what lets a
    # deleted start folder still open the picker somewhere sensible.
    assert FP._item_from_path(str(tmp_path / u"gone")) is None

    # ⚠ AN EMPTY PATH IS NOT IN THAT CONTRACT, and asserting it was
    # WAS MY MISTAKE, NOT THE CODE'S: `""` parses to a real shell item (the
    # desktop root), so a check demanding None there would have been
    # demanding a behaviour change. `_modern` never asks — it guards on
    # `if start:` first — so THAT is the property worth pinning, and it is
    # pinned where it can actually regress.
    import inspect

    body = inspect.getsource(FP._modern)
    assert u"if start:" in body, (
        u"_modern no longer guards the start folder, so an empty start "
        u"would open the picker at the desktop root instead of nowhere")


@pytest.mark.skipif(not sys.platform.startswith("win"),
                    reason=u"needs the Windows shell")
def test_the_classic_fallback_REALLY_OPENS_something(monkeypatch, tmp_path):
    u"""⚠ `_classic` was never executed either — both fallback checks
    monkeypatch it away, so *"it ALWAYS falls back"* rested on a function no
    check had ever called.

    ⛔ A REAL `askdirectory` CANNOT RUN HERE — it is modal and nothing could
    close it. So this drives the seam one layer down: `_classic` must call
    Tk's dialog with the arguments it claims to, and must turn a cancel
    (`askdirectory` returns `""` or `()`) into `u""` rather than into a
    traceback.
    """
    from tkinter import filedialog
    from tsubasa.gui import folderpick as FP

    seen = {}

    def fake_askdirectory(**kw):
        seen.update(kw)
        return seen.pop(u"_answer", str(tmp_path))

    monkeypatch.setattr(filedialog, u"askdirectory", fake_askdirectory)

    assert FP._classic(u"Pick one", str(tmp_path)) == str(tmp_path)
    assert seen[u"title"] == u"Pick one"
    assert seen[u"initialdir"] == str(tmp_path), (
        u"the fallback starts nowhere, which is the defect 4d fixed for the "
        u"modern path")

    # ⚠ NO `initialdir` KEY AT ALL when there is no start folder — passing
    # `initialdir=""` is not the same call.
    seen.clear()
    FP._classic(u"Pick one", u"")
    assert u"initialdir" not in seen, seen

    # ⛔ AND BOTH SHAPES OF CANCEL. Tk returns `""` on some platforms and an
    # empty TUPLE on others, and `or u""` is what flattens them.
    for cancelled in (u"", ()):
        monkeypatch.setattr(filedialog, u"askdirectory",
                            lambda **kw: cancelled)
        assert FP._classic(u"t", u"") == u""


def test_the_folder_picker_ALWAYS_falls_back_and_says_why(monkeypatch):
    u"""⛔ `00-INDEX.md` Rule 1 in miniature: the modern picker is an
    ACCELERATOR, never a dependency. Whatever COM does, the person gets a
    dialog.

    ⚠ And a silent fallback is an undiagnosable one — the first version
    recorded a reason only when something RAISED, so a COM call that merely
    returned a bad HRESULT dropped to the 2001 dialog with `LAST_REASON`
    empty, and the probe reported *"no fallback reason"* over a legacy
    dialog. A measurement that lies is worse than none.
    """
    from tsubasa.gui import folderpick as FP

    called = []
    monkeypatch.setattr(FP, "_classic",
                        lambda title, start: called.append((title, start))
                        or u"/fallback")
    # 🚨 THE PLATFORM GATE IS FORCED ON, and that is the whole reason it is a
    # named predicate. `IFileOpenDialog` is Windows COM, so off Windows `ask`
    # goes straight to the classic dialog and this contract is vacuous —
    # there is nothing to fall back FROM. ⛔ Written without this, the check
    # went red on EIGHT CI jobs across Linux and macOS with
    # `assert 'no COM here' in ''`, having only ever been run on Windows.
    monkeypatch.setattr(FP, "_modern_is_possible", lambda: True)

    monkeypatch.setattr(FP, "_modern",
                        lambda *a, **k: (_ for _ in ()).throw(
                            OSError(u"no COM here")))
    assert FP.ask(title=u"t", start=u"s") == u"/fallback"
    assert u"no COM here" in FP.LAST_REASON

    # the quiet decline -- returns None without raising
    monkeypatch.setattr(FP, "_modern", lambda *a, **k: None)
    assert FP.ask(title=u"t", start=u"s") == u"/fallback"
    assert FP.LAST_REASON, u"a silent fallback recorded no reason at all"

    # ⭐ CANCEL IS NOT A FAILURE. An empty string means the person said no,
    # and falling back there would open a second dialog in their face.
    called[:] = []
    monkeypatch.setattr(FP, "_modern", lambda *a, **k: u"")
    assert FP.ask(title=u"t", start=u"s") == u""
    assert called == [], u"a cancel opened the fallback dialog"


def test_off_WINDOWS_the_picker_goes_straight_to_the_classic_dialog(monkeypatch):
    u"""🚨 THE HALF THAT WAS NEVER COVERED, AND IT TURNED CI RED ON EIGHT JOBS.

    `IFileOpenDialog` is a Windows COM interface. Off Windows there is no
    modern picker to try, so `ask` must go straight to `askdirectory` **and
    must not invent a fallback reason** — there was nothing to fall back from.

    ⛔ Everything about this module had only ever been run on Windows, where
    the other branch is the one that executes. `doctrine/verification`: ask
    what your real-data pass does NOT contain — here it was an entire
    platform, and the CI matrix is the only reason it surfaced before a user
    did.
    """
    from tsubasa.gui import folderpick as FP

    called = []
    monkeypatch.setattr(FP, "_classic",
                        lambda title, start: called.append((title, start))
                        or u"/classic")
    monkeypatch.setattr(FP, "_modern_is_possible", lambda: False)
    monkeypatch.setattr(FP, "_modern", lambda *a, **k: (_ for _ in ()).throw(
        AssertionError(u"the modern picker was tried where it cannot exist")))

    assert FP.ask(title=u"t", start=u"s") == u"/classic"
    assert called == [(u"t", u"s")], called
    assert FP.LAST_REASON == u"", (
        u"a reason was recorded for a fallback that was never a fallback: %r"
        % FP.LAST_REASON)


def test_a_CANCEL_is_read_as_a_cancel_and_not_as_a_failure():
    u"""🚨 FOUND BY A SURVIVING MUTANT, and the defect is a first-click one.

    Deleting the cancel arm survived every check, because the only check over
    the picker replaces `_modern` wholesale — and `_modern` opens a real COM
    dialog, so it can never run in a suite. ⛔ The branching inside it was
    therefore asserted by nothing.

    ⭐ The decision is now `verdict_of`, a pure function over an `HRESULT`:
    the dialog is I/O and the ruling is logic. Press Cancel with the arm
    missing and you are told the modern picker failed, then the 2001 dialog
    opens in your face.
    """
    from tsubasa.gui import folderpick as FP

    assert FP.verdict_of(0) == u"ok"
    assert FP.verdict_of(FP.HRESULT_CANCELLED) == u"cancel"
    # ⚠ The sign matters: `Show` comes back through a `c_long`, so the value
    # arrives NEGATIVE. Masking is the whole reason this is a function.
    assert FP.verdict_of(-2147023673) == u"cancel", (
        u"the same code as a signed long must still read as a cancel")
    for bad in (0x80004005, 0x80070005, 0x8007000E, -2147467259):
        assert FP.verdict_of(bad) == u"failed", hex(bad & 0xFFFFFFFF)


def test_a_tkdnd_THAT_IMPORTS_BUT_CANNOT_LOAD_falls_back_to_a_plain_root(
        monkeypatch):
    u"""🚨 GUARDING THE IMPORT IS NOT GUARDING THE TOOLKIT.

    `tkinterdnd2` imports fine and then `TkinterDnD.Tk()` loads a **Tcl**
    package from disk. Measured in the frozen app: renaming one file,
    `_internal/tkinterdnd2/tkdnd/win-x64/libtkdnd2.10.2.dll`, replaced the
    whole window with *"Failed to execute script 'entry_gui'"*. ⛔ The module's
    own note promises it degrades to Browse with a stated reason, and that
    path was **unreachable in a frozen build** — the Python module lives in
    the PYZ and cannot go missing, so the only thing that CAN was the one
    thing unguarded.

    ⚠ No display needed: the fallback is asserted by which constructor is
    reached, not by a window.
    """
    from tsubasa.gui import app as APP

    class Exploding(object):
        @staticmethod
        def Tk():
            raise RuntimeError(u"Unable to load tkdnd library.")

    made = []
    monkeypatch.setattr(APP, "TkinterDnD", Exploding)
    monkeypatch.setattr(APP, "DND_FILES", u"DND_Files")
    monkeypatch.setattr(APP, "DND_ERROR", u"")
    monkeypatch.setattr(APP.tk, "Tk", lambda: made.append(u"plain") or u"root")

    assert APP._dnd_root_or_plain() == u"root", u"no plain root was built"
    assert made == [u"plain"]
    # ⭐ ONE no-drop state, not two: `App` reads these to decide, so a failed
    # LOAD must look exactly like a failed import or the footer says nothing.
    assert APP.TkinterDnD is None and APP.DND_FILES is None
    assert u"Unable to load tkdnd" in APP.DND_ERROR, APP.DND_ERROR


def test_TSUBASA_CLI_still_wins_inside_a_frozen_app(monkeypatch):
    u"""⭐ `STANDALONE-BUILD-SCOPE.md` trap 1: the override is *"how you can
    point the GUI at a known-good CLI while bisecting"* — which is worth
    nothing if the frozen branch outranks it, because frozen is the only state
    anyone ever needs to bisect."""
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv(u"TSUBASA_CLI", u"/known/good/tsubasa")
    assert RUN.cli_argv() == [u"/known/good/tsubasa"]


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
