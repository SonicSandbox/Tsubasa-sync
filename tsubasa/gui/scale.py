# -*- coding: utf-8 -*-
u"""
DPI. RUNBOOK 3d constraint 3.

    state = make_process_dpi_aware()          # BEFORE the first Tk()
    S = Scale(root)
    frame.pack(padx=S.px(12), pady=S.px(8))
    S.pin(root, 1060, 660)

===========================================================================
🚨 TK SCALES FONTS AND NOTHING ELSE
===========================================================================

Once the process is DPI-aware, Tk multiplies point sizes by `tk scaling` and
paints text at the right physical size. It does **not** touch `width=`,
`height=`, `padx=`, `pady=`, `ipadx=`, `ipady=`, `wraplength=`, `borderwidth=`,
`rowheight`, or the string handed to `geometry()`. Every one of those stays a
raw pixel count.

⭐ Measured on the build machine, 2026-09-09: 3000x2000 at **239.6 dpi**,
`tk scaling` **3.328**, ratio **2.496**. This is not an exotic configuration —
it is the machine the tool is being written on, which means the un-scaled
version of this window has never once been seen at 1.0.

⛔ **Never write a literal pixel number into a widget. Write `S.px(n)`.**

===========================================================================
🚨 THREE THINGS AN ADVERSARIAL PASS PROVED WRONG ON 2026-09-10
===========================================================================

1. **`fits()` was optimistic by 88 px and said yes to a window 85 px off the
   bottom of the screen.** `wm geometry` positions the **frame**;
   `winfo_rootx/rooty` report the **client**. The first draft added a
   requested origin to a client size and counted neither the 72 px title bar
   nor the 16 px border — nor the taskbar, which is why the **work area** and
   not the screen is the rectangle that matters. ⭐ The capture harness's own
   check disagreed with it, and the permissive one was the one that ran
   *before* the window opened.
2. **`pin()` never consulted `fits()`.** `pin(root, 1060, 1200)` produced a
   real 2646x2995 window on a 2000-px screen, unresizable because
   `min == max`, with no scrollbar — the exact clipping defect this module
   exists to prevent, mechanically guaranteed by the module.
3. 🚨 **`make_process_dpi_aware()` returned the name of what "worked" without
   checking that anything had.** Called after `Tk()` it still reported
   `shcore.SetProcessDpiAwareness(1)` while `Scale` went on to read **95.8
   dpi on a 1200x800 screen** — every number in the process wrong, and a
   mutant whose body called nothing survived all six DPI checks, because the
   only assertion was that a non-empty string came back. ⭐ `doctrine/evidence`
   §*read-backs*: **ask the system what it actually ended up with.**
"""
import ctypes
import sys

#: The dpi every design number in this project is written against.
NOMINAL_DPI = 96.0

#: `GetSystemMetrics` indices, named so the arithmetic below is readable.
SM_CYCAPTION = 4
SM_CXSIZEFRAME = 32
SM_CYSIZEFRAME = 33
SM_CXPADDEDBORDER = 92

#: `SystemParametersInfoW`
SPI_GETWORKAREA = 0x0030


class _RECT(ctypes.Structure):
    _fields_ = [("left", ctypes.c_long), ("top", ctypes.c_long),
                ("right", ctypes.c_long), ("bottom", ctypes.c_long)]


class Awareness(object):
    u"""What `make_process_dpi_aware()` actually achieved. ⛔ Not a string.

    A string saying which call was made is a claim about the CODE PATH. The
    thing that matters is what the SYSTEM now reports, and those came apart:
    the call succeeds when it is too late to matter and still returns its own
    name. ⭐ `level` is read back out of Windows afterwards.
    """

    __slots__ = ("call", "level", "note")

    #: `PROCESS_DPI_AWARENESS`
    UNAWARE, SYSTEM, PER_MONITOR = 0, 1, 2

    def __init__(self, call, level, note=u""):
        self.call = call
        self.level = level
        self.note = note

    @property
    def aware(self):
        u"""Is this process actually DPI-aware NOW? -> bool"""
        return self.level is not None and self.level > self.UNAWARE

    def __repr__(self):
        return "<Awareness %s -> level=%r aware=%s%s>" % (
            self.call, self.level, self.aware,
            (" " + self.note) if self.note else "")


def dpi_awareness_level():
    u"""What Windows says this process's awareness IS. -> int or None

    ⭐ THE READ-BACK. `doctrine/evidence`: *if you can ask the system what it
    actually ended up with, ask it.* None means the question does not apply
    (not Windows, or too old to answer it).
    """
    if not sys.platform.startswith("win"):
        return None
    value = ctypes.c_int(0)
    try:
        if ctypes.windll.shcore.GetProcessDpiAwareness(
                None, ctypes.byref(value)) == 0:
            return value.value
    except (AttributeError, OSError):
        pass
    try:
        # Pre-8.1 fallback: a boolean, which maps onto SYSTEM.
        return Awareness.SYSTEM if ctypes.windll.user32.IsProcessDPIAware() \
            else Awareness.UNAWARE
    except (AttributeError, OSError):
        return None


def make_process_dpi_aware():
    u"""Ask Windows to stop lying about the screen. -> `Awareness`

    ⛔ MUST RUN BEFORE THE FIRST `Tk()`. Tk reads the metrics once; called
    afterwards this **still succeeds** and every measurement in the process is
    of a virtualised 96 dpi screen — which is worse than not calling it,
    because the fonts change and the numbers do not. The returned `Awareness`
    carries the level Windows reports back, so *"did this work"* is a question
    with an answer instead of a string.

    ⚠ Returns rather than raises. A non-Windows host has neither call and is
    DPI-correct already; a failure here must not stop the app opening.
    """
    if not sys.platform.startswith("win"):
        return Awareness(u"not windows — nothing to do", None,
                         u"the platform has no per-process DPI setting")
    made = None
    try:
        # PROCESS_SYSTEM_DPI_AWARE. ⚠ Deliberately not PER_MONITOR (2): this
        # window does not re-lay-out on a monitor change, and per-monitor
        # awareness without a `WM_DPICHANGED` handler is the same clipping
        # defect armed to fire when the laptop is docked.
        ctypes.windll.shcore.SetProcessDpiAwareness(Awareness.SYSTEM)
        made = u"shcore.SetProcessDpiAwareness(1)"
    except (AttributeError, OSError) as exc:
        # ⚠ E_ACCESSDENIED means it was ALREADY set — by a manifest, or by an
        # earlier call. That is success, not failure, and the read-back below
        # is what tells them apart.
        made = u"shcore.SetProcessDpiAwareness(1) raised %s" % type(exc).__name__
        try:
            ctypes.windll.user32.SetProcessDPIAware()
            made = u"user32.SetProcessDPIAware()"
        except (AttributeError, OSError):
            made = u"neither call is available"
    level = dpi_awareness_level()
    note = u""
    if level == Awareness.UNAWARE:
        note = (u"⛔ the call returned and the process is STILL unaware — "
                u"every geometry number will be of a virtualised 96 dpi "
                u"screen. The usual cause is that a Tk root already exists.")
    return Awareness(made, level, note)


def work_area(screen):
    u"""The desktop minus the taskbar. -> (left, top, right, bottom)

    ⭐ THE RECTANGLE A WINDOW ACTUALLY HAS. The screen is not it: a bottom
    taskbar at this scale is ~110 real pixels, which is more than the margin
    the shipped window was designed with.
    """
    if sys.platform.startswith("win"):
        rect = _RECT()
        try:
            if ctypes.windll.user32.SystemParametersInfoW(
                    SPI_GETWORKAREA, 0, ctypes.byref(rect), 0):
                return (rect.left, rect.top, rect.right, rect.bottom)
        except (AttributeError, OSError):
            pass
    return (0, 0, screen[0], screen[1])


def window_chrome():
    u"""How much bigger the FRAME is than the client area. -> (w, h)

    🚨 `wm geometry` SIZES THE CLIENT AND POSITIONS THE FRAME. Mixing those is
    what made `fits()` optimistic by 88 px. Measured on the build machine:
    a 72 px caption and a 16 px border, which `GetSystemMetrics` reproduces.

    ⚠ These are already real pixels — the system reports them post-scaling —
    so they must NOT go through `px()`.
    """
    if not sys.platform.startswith("win"):
        return (0, 0)
    try:
        get = ctypes.windll.user32.GetSystemMetrics
        pad = get(SM_CXPADDEDBORDER)
        border_x = get(SM_CXSIZEFRAME) + pad
        border_y = get(SM_CYSIZEFRAME) + pad
        return (2 * border_x, get(SM_CYCAPTION) + 2 * border_y)
    except (AttributeError, OSError):
        return (0, 0)


def measure_chrome(root):
    u"""The same figure, taken off a REAL mapped window. -> (w, h)

    ⭐ `doctrine/architecture`: *fit by MEASURING, never by calculating.*
    `window_chrome()` is the cheap formula and this is the instrument that
    disagrees with it when it is wrong — the suite compares the two, which is
    the only reason either can be trusted.

    ⚠ The window must already be mapped; the caller does that.
    """
    root.update_idletasks()
    spec = root.winfo_geometry()                # "WxH+X+Y" — X/Y is the FRAME
    plus = spec.split(u"+")
    frame_x, frame_y = int(plus[1]), int(plus[2])
    side = root.winfo_rootx() - frame_x         # one border
    top = root.winfo_rooty() - frame_y          # caption PLUS one border
    # 🚨 THE TOP OFFSET IS NOT THE TOTAL. `rooty - frame_y` is how far the
    # client starts BELOW the frame — caption + top border — and the window is
    # also that border tall again at the BOTTOM. The first draft returned the
    # top offset as the whole vertical chrome and came out **16 px short**,
    # which is exactly the direction that makes `fits()` optimistic again.
    # ⭐ Caught on this check's first run by disagreeing with `window_chrome`:
    # measured (32, 72) against a formula of (32, 88).
    return (2 * side, top + side)


class Pin(object):
    u"""What `Scale.pin` actually gave the window."""

    __slots__ = ("width", "height", "asked", "clamped", "why")

    def __init__(self, width, height, asked, clamped, why=u""):
        self.width = width
        self.height = height
        self.asked = asked
        self.clamped = clamped
        self.why = why

    def __iter__(self):
        return iter((self.width, self.height))

    def __eq__(self, other):
        return tuple(self) == tuple(other)

    def __repr__(self):
        return "<Pin %dx%d asked=%r clamped=%s>" % (
            self.width, self.height, self.asked, self.clamped)


class Scale(object):
    u"""Every pixel number in the window goes through this.

    ⭐ ONE OBJECT, read from one place, so *"the display changed"* is a
    one-function question rather than a sweep — `doctrine/architecture` rule 2
    applied to geometry instead of to records.

    ⚠ `dpi`, `screen`, `area` and `chrome` are read ONCE. This process is
    system-DPI-aware, not per-monitor, so those cannot change under it without
    the whole window being wrong anyway — but a dock, an undock or a
    resolution change makes every number here stale for the life of the
    process, and nothing can notice. Recorded rather than solved: solving it
    means `WM_DPICHANGED` and a relayout, which is `evolution`.
    """

    def __init__(self, root, dpi=None, screen=None, area=None, chrome=None):
        #: ⚠ `winfo_fpixels("1i")` and not `tk scaling`. They differ by a
        #: constant 72/96 and mixing them is a silent 1.33x on every number.
        self.dpi = float(dpi if dpi is not None else root.winfo_fpixels(u"1i"))
        self.ratio = self.dpi / NOMINAL_DPI
        self.screen = screen or (root.winfo_screenwidth(),
                                 root.winfo_screenheight())
        self.area = area or work_area(self.screen)
        self.chrome = window_chrome() if chrome is None else chrome

    def px(self, n):
        u"""A design pixel -> a real one. -> int"""
        return int(round(n * self.ratio))

    def window(self, w, h, x=40, y=40):
        u"""A geometry string, every number scaled. -> unicode"""
        return u"%dx%d+%d+%d" % (self.px(w), self.px(h), self.px(x),
                                 self.px(y))

    def frame(self, w, h):
        u"""The real size the WINDOW MANAGER will hand out. -> (w, h)

        The client size plus the caption and borders. ⛔ This, not `px(w)`, is
        what has to fit on the desktop.
        """
        return (self.px(w) + self.chrome[0], self.px(h) + self.chrome[1])

    def fits(self, w, h, x=40, y=40):
        u"""Would a window of this design size fit in the work area? -> bool

        🚨 `LEDGER.md`: *a DPI-aware window clipped its own button off the
        screen.* Asked BEFORE the window opens, because the answer on this
        machine is not obvious: 1060x660 design pixels is **2646x1647 real
        ones**, plus the frame, inside a work area that is not the screen.
        """
        fw, fh = self.frame(w, h)
        left, top, right, bottom = self.area
        return (left + self.px(x) + fw <= right
                and top + self.px(y) + fh <= bottom)

    def largest_that_fits(self, w, h, x=40, y=40):
        u"""The biggest design size <= (w, h) that fits. -> (w, h)"""
        left, top, right, bottom = self.area
        room_w = right - left - self.px(x) - self.chrome[0]
        room_h = bottom - top - self.px(y) - self.chrome[1]
        return (min(w, max(1, int(room_w / self.ratio))),
                min(h, max(1, int(room_h / self.ratio))))

    def pin(self, root, w, h, x=40, y=40, clamp=True):
        u"""Give the window a size the manager cannot improve on. -> `Pin`

        ⛔ `geometry()` alone does not hold: its SIZE loses to the geometry
        manager on first map — a `tk.Text` asks for 24 lines and a
        `ttk.Treeview` for its `height=` rows, and a window asked for 1647 px
        came back **1089** — and its POSITION loses to the window manager,
        which cascades successive toplevels. `min == max` is what makes the
        size a constraint.

        🚨 **AND IT CONSULTS `fits()` NOW.** Pinning a size that does not fit
        produces an unresizable, unmaximisable window hanging off the bottom
        of the desktop: the clipping defect, guaranteed by the code written to
        prevent it. ⭐ Clamped by default, and it SAYS it clamped — a caller
        that gets a smaller window than it asked for has content to reflow,
        and `Pin.clamped` is how it finds out.

        ⚠ **Clamping is not the whole answer.** A window shrunk to the desktop
        still has to put its content somewhere, and content that overflows a
        pinned window is unreachable without a scroller. That belongs to the
        layout, and `RUNBOOK.md` §3d carries it as a requirement.
        """
        asked = (w, h)
        clamped, why = False, u""
        if not self.fits(w, h, x, y):
            if clamp:
                w, h = self.largest_that_fits(w, h, x, y)
                clamped = True
                why = (u"%dx%d design px does not fit the work area %s at "
                       u"%.3fx with %dx%d of window frame — clamped to %dx%d"
                       % (asked[0], asked[1], self.area, self.ratio,
                          self.chrome[0], self.chrome[1], w, h))
            else:
                raise ValueError(
                    "a %dx%d design-pixel window is %dx%d real pixels with "
                    "its frame, and the work area is %s. Pinning it would "
                    "make an unresizable window hanging off the desktop."
                    % (asked[0], asked[1], self.frame(*asked)[0],
                       self.frame(*asked)[1], self.area))
        rw, rh = self.px(w), self.px(h)
        root.geometry(self.window(w, h, x, y))
        root.minsize(rw, rh)
        root.maxsize(rw, rh)
        return Pin(rw, rh, asked, clamped, why)

    def __repr__(self):
        return "<Scale %.1f dpi, ratio %.3f, screen %dx%d, area %s, " \
               "chrome %dx%d>" % (self.dpi, self.ratio, self.screen[0],
                                  self.screen[1], self.area, self.chrome[0],
                                  self.chrome[1])


__all__ = ["Scale", "Pin", "Awareness", "make_process_dpi_aware",
           "dpi_awareness_level", "work_area", "window_chrome",
           "measure_chrome", "NOMINAL_DPI"]
