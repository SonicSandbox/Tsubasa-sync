# -*- coding: utf-8 -*-
"""Put the repo root on sys.path so suites import `tsubasa` without an install.

And point the per-user store at a throwaway directory for the whole session --
see `isolate_the_per_user_store` below.
"""
import ctypes
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# =========================================================================
# 🚨 THE GUI SUITE'S WINDOWS GO ON A DESKTOP OF THEIR OWN
# =========================================================================
#
# REPORTED BY SONIC, 2026-09-17: *"Please make all these tests occur out of
# focus, as it interrupts what I am doing."* The GUI suite maps REAL Tk
# windows — deliberately, because that is how it catches what assertions do
# not — but each one flashed up and took the keyboard, over a hundred times
# in a full run, out of whatever he was typing into.
#
# ⛔ THREE WINDOW-LEVEL FIXES WERE TRIED FIRST AND EACH WAS MEASURED TO FAIL:
#
#     -alpha 0.0                            invisible, still took the focus
#     + WS_EX_NOACTIVATE applied on <Map>   bits set, STILL took the focus:
#                                           the map had already handed it over
#     + withdraw, style, SW_SHOWNOACTIVATE  STILL took the focus, because Tk
#                                           re-activates on update()
#
# ⭐ `WS_EX_NOACTIVATE` stops Windows activating a window WHEN IT IS SHOWN. It
# does not stop Tk asking for the foreground afterwards, and Tk does. So the
# fix is not a window property at all: the thread runs on a **private
# desktop**, where there is no foreground to take and nothing is on screen.
# Measured side by side — styles: STOLE FOCUS **YES**; desktop: **no**, with
# geometry identical (420×300, child at the same offset), which matters
# because a third of `test_gui.py` measures layout.
#
# ⚠ IT MUST HAPPEN HERE, AT IMPORT, NOT IN A FIXTURE. `SetThreadDesktop` fails
# on a thread that already owns a window, so it has to beat the first `Tk()`.
#
# ⛔ AND IT CANNOT BE ALLOWED TO FAIL THE RUN. `_has_icon` once called Win32
# with no `argtypes`, raised `OverflowError`, and took down a whole smoke run
# — 44 unrelated checks reported nothing. Every step here is guarded; the
# worst case is windows appearing as they always did.

#: Set to anything non-empty to put the windows back on the real desktop.
#: ⭐ Not a nicety: *ASSERT THE OUTPUT, THEN LOOK AT IT* is doctrine here, and
#: you cannot look at a window on a desktop you are not on.
SHOW_WINDOWS = u"TSUBASA_TEST_SHOW_WINDOWS"
DESKTOP_NAME = u"tsubasa-tests"
#: `GetUserObjectInformationW` — ask an object for its name.
UOI_NAME = 2
_GENERIC_ALL = 0x10000000

#: u"" when the thread moved; otherwise why it did not. Read by the checks in
#: `test_gui.py`, so a silent regression to focus-stealing goes red.
DESKTOP_MOVED = u"not attempted"
#: ⚠ The handle, kept so it can be named or closed later. ⛔ **AN EARLIER
#: COMMENT HERE WAS FALSE** and said this reference is what stops Windows
#: destroying the desktop. It is not: `restype = wintypes.HANDLE` hands back
#: a plain Python `int`, which has no finalizer, and `CloseDesktop` is never
#: called — so dropping this assignment releases nothing. **What actually
#: keeps the desktop alive is the thread being on it.** Found by an
#: adversary, which is also why the mutant that deletes this line survives
#: and is recorded as equivalent rather than chased.
_DESKTOP = None


def why_not_a_private_desktop():
    u"""-> the reason to skip the private desktop, or u"" to go ahead.

    ⚠ Split out from `use_a_private_desktop` so the DECISION is testable
    without moving a real thread between desktops — the move is one-way on a
    thread that has windows, so a check cannot simply do it twice.
    """
    if not sys.platform.startswith(u"win"):
        return u"not Windows"
    if os.environ.get(SHOW_WINDOWS):
        return u"off: %s is set" % SHOW_WINDOWS
    return u""


def use_a_private_desktop():
    u"""Move this thread to a desktop of its own. -> u"" or the reason not."""
    global _DESKTOP

    reason = why_not_a_private_desktop()
    if reason:
        return reason

    try:
        from ctypes import wintypes

        u32 = ctypes.WinDLL(u"user32", use_last_error=True)
        # 🚨 EVERY argtype AND restype DECLARED — undeclared, ctypes assumes
        # `int` and truncates a 64-bit handle. That exact mistake crashed a
        # whole smoke run once already.
        u32.CreateDesktopW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR,
                                       ctypes.c_void_p, wintypes.DWORD,
                                       wintypes.DWORD, ctypes.c_void_p]
        u32.CreateDesktopW.restype = wintypes.HANDLE
        u32.SetThreadDesktop.argtypes = [wintypes.HANDLE]
        u32.SetThreadDesktop.restype = wintypes.BOOL

        desktop = u32.CreateDesktopW(DESKTOP_NAME, None, None, 0,
                                     _GENERIC_ALL, None)
        if not desktop:
            return u"CreateDesktop failed: %d" % ctypes.get_last_error()
        if not u32.SetThreadDesktop(desktop):
            return u"SetThreadDesktop failed: %d" % ctypes.get_last_error()
        _DESKTOP = desktop
        return u""
    except Exception as exc:                              # noqa: BLE001
        # ⚠ NOT `# pragma: no cover` — it carried that marker and the marker
        # was WRONG: `test_entering_the_private_desktop_can_NEVER_fail_the_run`
        # drives this arm with a hostile `WinDLL`, and a mutation that makes it
        # return `u""` is KILLED. A stale exclusion marker is a small lie that
        # tells the next reader not to bother.
        return u"%s: %s" % (type(exc).__name__, exc)


DESKTOP_MOVED = use_a_private_desktop()


@pytest.fixture(scope="session", autouse=True)
def isolate_the_per_user_store(tmp_path_factory):
    """Every suite gets its own cache, trash and results root.

    RUNBOOK 3a-bis. Two things live under `paths.cache_root()` that a test run
    must never touch: the trash `dedupe.py` sends losers to, and -- from
    3a-bis -- the results DB `sync()` consults to decide whether a video has
    ALREADY been synced.

    ⛔ The second one is the reason this is autouse rather than opt-in. A suite
    that writes real records leaves the developer's own history holding
    fixtures, and the next real run over their library would consult it. The
    blast radius of forgetting `results=` once is somebody else's media.

    ⚠ It also closes a hole that was already open: `sync()` falls back to
    `_default_trash_root()` under this same root whenever a check forgets
    `trash_root=`, so a forgotten argument has been writing into
    `%LOCALAPPDATA%\\tsubasa` all along.

    ⭐ The FOUR checks that assert something about the REAL default clear this
    variable themselves -- two in `test_cache.py`, two in `test_wiring.py` --
    because *"the cache is not inside the repo"* is a claim about the shipped
    resolver and a temp directory would satisfy it vacuously. ⚠ They were
    already vacuous for any developer who happened to have the variable set.
    """
    root = tmp_path_factory.mktemp("per-user-store")
    before = os.environ.get("TSUBASA_CACHE")
    os.environ["TSUBASA_CACHE"] = str(root)
    yield root
    if before is None:
        os.environ.pop("TSUBASA_CACHE", None)
    else:
        os.environ["TSUBASA_CACHE"] = before
