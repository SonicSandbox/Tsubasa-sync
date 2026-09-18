# -*- coding: utf-8 -*-
u"""Ask for a folder, using the picker the rest of Windows uses.

    chosen = folderpick.ask(parent_hwnd, title=u"Pick a folder", start=last)

===========================================================================
🚨 WHY THIS EXISTS: `askdirectory` IS THE 2001 DIALOG
===========================================================================

`tkinter.filedialog.askdirectory` calls Tk's `tk_chooseDirectory`, which on
Windows is **`SHBrowseForFolder`** — the small tree-in-a-box from Windows XP.
⛔ MEASURED 2026-09-17: the window it opens has class **`#32770`**, a classic
Win32 dialog, where the modern picker builds a shell view with `DirectUIHWND`
children. It has no address bar, no search, no resize worth having, no typing
a path, and it puts a **wait cursor** over the application while it walks the
shell namespace.

⚠ **AND THE APPLICATION IS NOT ACTUALLY FROZEN WHILE IT IS UP** — measured:
29 `after()` ticks ran during 3.4 s of dialog, and `IsHungAppWindow` stayed
False throughout. So the report *"the gui freezes"* is about what it LOOKS
like, and the fix is the dialog, not a thread. ⛔ A thread could not have
fixed it anyway: Tk is single-threaded and a native modal must pump messages
on the thread that owns the parent window.

⭐ `IFileOpenDialog` with `FOS_PICKFOLDERS` is what Explorer, Office and every
current application opens. Same process, same thread, no new dependency —
`ctypes` and the COM ABI, which is stable and documented.

===========================================================================
⚠ IT FALLS BACK, ALWAYS
===========================================================================

Every failure path returns to `askdirectory`. A folder picker is not the
place to be clever: if COM is unavailable, if the interface is not there, if
anything at all raises, the user still gets a dialog. `00-INDEX.md` Rule 1 in
miniature — **an accelerator, never a dependency.**
"""
import sys

#: Filled on first use and reported by `ask`, so a fallback is explicable
#: rather than mysterious. ⚠ Not a log: nothing here writes to a stream,
#: because the GUI process has none (`console=False`).
LAST_REASON = u""

#: `HRESULT` for *the user pressed Cancel*. ⛔ NOT an error.
HRESULT_CANCELLED = 0x800704C7


def verdict_of(hr):
    u"""What an `HRESULT` from `Show` means. -> `"ok"` · `"cancel"` · `"failed"`

    🚨 EXTRACTED SO IT CAN BE CHECKED. It lived inside `_modern`, which opens
    a real dialog through COM and therefore cannot run in a suite — so the
    only check over it replaced `_modern` wholesale and the branching was
    never exercised. ⛔ A mutant deleting the cancel arm **survived**, and the
    defect it models is one a person meets on their first click: press Cancel,
    get told the modern picker failed, and watch the 2001 dialog open in your
    face a moment later.

    ⭐ The decision is logic and the dialog is I/O. Separating them is what
    made the rule testable at all.
    """
    hr &= 0xFFFFFFFF
    if hr == 0:
        return u"ok"
    if hr == HRESULT_CANCELLED:
        return u"cancel"
    return u"failed"


def ask(parent=None, title=u"", start=u""):
    u"""-> the chosen folder, or `u""` if the person cancelled.

    `parent` is a window handle (`root.winfo_id()`), used to own the dialog so
    Windows dims and blocks the right window. Falsy is allowed.
    """
    global LAST_REASON
    LAST_REASON = u""
    if sys.platform.startswith("win"):
        try:
            chosen = _modern(parent, title, start)
            if chosen is not None:
                return chosen
            # ⛔ A SILENT FALLBACK IS AN UNDIAGNOSABLE ONE. The first version
            # recorded a reason only when something RAISED, so a COM call that
            # merely returned a bad HRESULT fell through to the 2001 dialog
            # with `LAST_REASON` empty — and the probe reported *"no fallback
            # reason"* over a legacy dialog, which is a measurement that lies.
            # `LEDGER-HOT.md`: a non-zero exit is not evidence until you know
            # why, and neither is a quiet one.
            if not LAST_REASON:
                LAST_REASON = u"the modern picker declined without raising"
        except Exception as exc:                          # noqa: BLE001
            # ⛔ BARE, AND DELIBERATE. Anything at all from the COM layer —
            # a missing interface, a denied apartment, a driver's shell
            # extension misbehaving — must end in a working dialog rather
            # than in a traceback the windowed process cannot even print.
            LAST_REASON = u"%s: %s" % (type(exc).__name__, exc)
    return _classic(title, start)


def _classic(title, start):
    from tkinter import filedialog
    kw = {}
    if start:
        kw[u"initialdir"] = start
    return filedialog.askdirectory(title=title, **kw) or u""


# ---------------------------------------------------------------------------
# the modern picker, through the COM ABI
# ---------------------------------------------------------------------------

def _modern(parent, title, start):
    u"""-> the folder, `u""` for cancel, or None meaning *could not*.

    ⚠ THREE RETURN SHAPES, and the third is the point: `u""` is a person
    saying no, `None` is this function saying *use the other dialog*. Collapsing
    them would turn a failed COM call into a silent cancel, and the user would
    press Browse and watch nothing happen.
    """
    import ctypes
    from ctypes import POINTER, byref, c_void_p, c_wchar_p
    from ctypes import wintypes

    ole32 = ctypes.oledll.ole32
    combase = ctypes.windll.ole32

    CLSID_FileOpenDialog = _guid(u"{DC1C5A9C-E88A-4dde-A5A1-60F82A20AEF7}")
    IID_IFileOpenDialog = _guid(u"{d57c7288-d4ad-4768-be02-9d969532d960}")
    IID_IShellItem = _guid(u"{43826d1e-e718-42ee-bc55-a1e261c37bfe}")

    CLSCTX_INPROC_SERVER = 1
    FOS_PICKFOLDERS = 0x00000020
    FOS_FORCEFILESYSTEM = 0x00000040
    FOS_PATHMUSTEXIST = 0x00000800
    SIGDN_FILESYSPATH = 0x80058000

    # ⚠ APARTMENT-THREADED, and `RPC_E_CHANGED_MODE` is fine. Tk's thread may
    # already be initialised — by a shell extension, by drag-and-drop, by an
    # earlier call — and re-initialising differently returns that code without
    # breaking anything. ⛔ `CoUninitialize` is NOT called for the same reason:
    # this thread did not necessarily start COM and must not end it.
    COINIT_APARTMENTTHREADED = 0x2
    RPC_E_CHANGED_MODE = 0x80010106
    try:
        combase.CoInitializeEx(None, COINIT_APARTMENTTHREADED)
    except Exception:                                     # noqa: BLE001
        pass

    dialog = c_void_p()
    ole32.CoCreateInstance(byref(CLSID_FileOpenDialog), None,
                           CLSCTX_INPROC_SERVER, byref(IID_IFileOpenDialog),
                           byref(dialog))
    if not dialog:
        return None

    vtbl = ctypes.cast(dialog, POINTER(POINTER(c_void_p))).contents

    def call(index, restype, *argtypes):
        proto = ctypes.WINFUNCTYPE(restype, c_void_p, *argtypes)
        return proto(vtbl[index])

    #: ⛔ THESE INDICES ARE THE `IFileOpenDialog` VTABLE AND THEY ARE NOT
    #: GUESSES. IUnknown takes 0-2; IModalWindow adds `Show` at 3;
    #: IFileDialog runs 4-26; IFileOpenDialog adds its own after that. A
    #: wrong index here calls a different method with the wrong arguments,
    #: which is why every failure in this module falls back rather than
    #: raising at the user.
    RELEASE, SHOW = 2, 3
    SET_OPTIONS, GET_OPTIONS = 9, 10
    SET_FOLDER, SET_TITLE = 12, 17
    GET_RESULT = 20

    try:
        options = wintypes.DWORD()
        call(GET_OPTIONS, ctypes.HRESULT, POINTER(wintypes.DWORD))(
            dialog, byref(options))
        call(SET_OPTIONS, ctypes.HRESULT, wintypes.DWORD)(
            dialog, options.value | FOS_PICKFOLDERS | FOS_FORCEFILESYSTEM
            | FOS_PATHMUSTEXIST)

        if title:
            call(SET_TITLE, ctypes.HRESULT, c_wchar_p)(dialog, title)

        if start:
            item = _item_from_path(start)
            if item:
                try:
                    call(SET_FOLDER, ctypes.HRESULT, c_void_p)(dialog, item)
                finally:
                    _release(item)

        show = ctypes.WINFUNCTYPE(ctypes.c_long, c_void_p, wintypes.HWND)(
            vtbl[SHOW])
        hr = show(dialog, wintypes.HWND(parent or 0))
        verdict = verdict_of(hr)
        if verdict == u"cancel":
            # ⭐ CANCEL IS A RESULT, NOT A FAILURE. Falling back here would
            # open a second dialog the instant the person said no.
            return u""
        if verdict == u"failed":
            global LAST_REASON
            LAST_REASON = u"IFileOpenDialog::Show returned 0x%08X" % (
                hr & 0xFFFFFFFF)
            return None

        result = c_void_p()
        call(GET_RESULT, ctypes.HRESULT, POINTER(c_void_p))(
            dialog, byref(result))
        if not result:
            return None
        try:
            return _path_of(result, SIGDN_FILESYSPATH)
        finally:
            _release(result)
    finally:
        _release(dialog, RELEASE)


def _guid(text):
    u"""`{...}` -> a `GUID` structure ready to pass by reference."""
    import ctypes

    class GUID(ctypes.Structure):
        _fields_ = [("Data1", ctypes.c_ulong), ("Data2", ctypes.c_ushort),
                    ("Data3", ctypes.c_ushort), ("Data4", ctypes.c_ubyte * 8)]

    out = GUID()
    ctypes.oledll.ole32.CLSIDFromString(text, ctypes.byref(out))
    return out


def _item_from_path(path):
    u"""A folder path -> an `IShellItem*`, or None. ⚠ Never raises: a starting
    folder that has been deleted or unmounted is ordinary, and must open the
    picker somewhere sensible rather than not at all."""
    import ctypes
    from ctypes import byref, c_void_p
    try:
        item = c_void_p()
        iid = _guid(u"{43826d1e-e718-42ee-bc55-a1e261c37bfe}")
        ctypes.oledll.shell32.SHCreateItemFromParsingName(
            ctypes.c_wchar_p(path), None, byref(iid), byref(item))
        return item if item else None
    except Exception:                                     # noqa: BLE001
        return None


def _path_of(item, sigdn):
    u"""`IShellItem*` -> its filesystem path."""
    import ctypes
    from ctypes import POINTER, byref, c_void_p, c_wchar_p
    from ctypes import wintypes

    vtbl = ctypes.cast(item, POINTER(POINTER(c_void_p))).contents
    #: IShellItem: IUnknown 0-2, BindToHandler 3, GetParent 4,
    #: GetDisplayName 5, GetAttributes 6, Compare 7.
    GET_DISPLAY_NAME = 5
    buf = c_wchar_p()
    ctypes.WINFUNCTYPE(ctypes.HRESULT, c_void_p, wintypes.DWORD,
                       POINTER(c_wchar_p))(vtbl[GET_DISPLAY_NAME])(
        item, sigdn, byref(buf))
    try:
        return buf.value or u""
    finally:
        ctypes.windll.ole32.CoTaskMemFree(buf)


def _release(pointer, index=2):
    import ctypes
    from ctypes import POINTER, c_void_p
    try:
        vtbl = ctypes.cast(pointer, POINTER(POINTER(c_void_p))).contents
        ctypes.WINFUNCTYPE(ctypes.c_ulong, c_void_p)(vtbl[index])(pointer)
    except Exception:                                     # noqa: BLE001
        pass


__all__ = ["ask", "LAST_REASON"]
