# -*- coding: utf-8 -*-
u"""
The window. RUNBOOK 3d, layout RULED 2026-09-10.

    python -m tsubasa.gui

===========================================================================
⭐ THE RULING, IN SONIC'S WORDS
===========================================================================

  *"Table is best. Cleanest and easiest to digest."*
  *"Auto-run on drop unless setting is toggled. Write without confirm unless
  reckless toggled in settings."*
  *"The window must look clean as it does, and the settings organized but the
  settings would likely be powerful for various features."*

⛔ **So the main window gains nothing.** It is the mockup: a folder row, a
table, a detail pane, a counts strip. Every option lives in `settings.py` and
is reached through one button. A feature that wants a control on this window
needs a ruling, not a commit.

===========================================================================
⛔ THIS MODULE DECIDES NOTHING
===========================================================================

`cli.py`'s header rule, one process boundary further out. Every outcome,
word, number and reason on this screen came from `sync()` through
`python -m tsubasa --json`, and is **read** here. The moment this file holds a
threshold, a ranking rule or a second opinion about what a run meant, the
library's answer stops being the product.

⭐ **And the counts come from `run.counts`, which PARTITIONS.** An adversarial
pass rebuilt `LEDGER.md` §Interface's original defect out of correct fields —
a failed write reading `1 synced`, a repaired cut counted twice so ten files
read as eleven. Nothing in this file adds two of those numbers together.

---------------------------------------------------------------------------
⚠ WHAT A CHECK CANNOT SAY ABOUT THIS FILE
---------------------------------------------------------------------------

Whether it looks right. `07-test-plan.md` gives the gui row *"output painted
right, then **looked at**"*, and the looking is
`_work/probe_3d_2_look_at_the_app.py`. A check can assert this window is
2646x1647 and can never assert the Sync button is inside it — that exact
mistake shipped, twice, and is in the ledger both times.
"""
import os
import sys

import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, ttk

from . import folderpick as _folderpick
from . import run as _run
from . import settings as _settings
from .scale import Scale, make_process_dpi_aware

# ⚠ OPTIONAL, AND THE WINDOW OPENS WITHOUT IT. `doctrine/architecture`:
# *instruction, not refusal — an unavailable feature renders what would make
# it available.* Dropping a folder is the ruled way in; if the toolkit that
# provides it is missing, the app says so and the Browse button still works.
try:
    from tkinterdnd2 import DND_FILES, TkinterDnD
    DND_ERROR = u""
except Exception as _exc:                                 # pragma: no cover
    DND_FILES, TkinterDnD = None, None
    DND_ERROR = u"%s: %s" % (type(_exc).__name__, _exc)


# ---------------------------------------------------------------------------
# theme -- dark by default (`build-ui` standing rule, FROZEN)
# ---------------------------------------------------------------------------

BG = u"#15171b"          # window ground
PANEL = u"#1c1f25"       # raised surface
EDGE = u"#2b3038"        # hairline
SEL = u"#2c3846"         # selected row
INK = u"#e7e9ec"         # primary text
DIM = u"#8b929c"         # secondary text
OK = u"#6cc08a"          # confident
CUT = u"#e0a94a"         # confident, and it repaired something
BAD = u"#e0736c"         # refused
ERR = u"#c76ad0"         # errored -- ⛔ NOT the same colour as refused
ACCENT = u"#6aa8d8"

MARK = {_run.CONFIDENT: u"✓", _run.REFUSED: u"✗", _run.ERROR: u"!"}
COLOUR = {_run.CONFIDENT: OK, _run.REFUSED: BAD, _run.ERROR: ERR}

#: Where the credit line points. ⛔ One place, because it is rendered in the
#: window AND opened in a browser, and two copies is one you can change and
#: leave stale.
HOME_URL = u"https://github.com/SonicSandbox/Tsubasa-sync"

# ---------------------------------------------------------------------------
# ⭐ interaction — the one thing a dark UI cannot skip
# ---------------------------------------------------------------------------
#
# `doctrine/architecture`: a control that does not answer the pointer reads as
# disabled. On a dark ground the answer has to be a LIFT, not a tint — a hue
# shift on hover looks like a state change ("did I just turn something on?"),
# while a small lightening reads as *this is live* and nothing else.
#
# ⚠ The amounts are small on purpose. 10% up on hover and 8% down on press is
# about the smallest step that is unambiguous at a glance, and anything
# louder becomes the distraction the brief ruled out.

HOVER_LIFT = 0.10
PRESS_SINK = 0.08


def _shade(colour, amount):
    u"""Move a `#rrggbb` toward white (amount > 0) or black (< 0). -> unicode

    ⭐ TOWARD THE EXTREME, not a multiply. Scaling each channel by `1 + amount`
    leaves a near-black ground almost unmoved — `#15171b` lifted 10% is
    `#171920`, which nobody can see — because the step is proportional to a
    value that is already tiny. Interpolating toward white gives every colour
    the same *perceptual* step regardless of where it started.
    """
    colour = colour.lstrip(u"#")
    parts = [int(colour[i:i + 2], 16) for i in (0, 2, 4)]
    target = 255 if amount >= 0 else 0
    weight = abs(amount)
    return u"#%02x%02x%02x" % tuple(
        int(round(c + (target - c) * weight)) for c in parts)


def _luma(colour):
    u"""Perceived brightness of `#rrggbb`, 0.0–1.0. -> float

    ⚠ ITU-R BT.601 weights, not the mean. Green carries most of the perceived
    light and blue almost none, so a flat average calls this window's accent
    blue *brighter* than it looks and picks the wrong hover direction for it.
    """
    colour = colour.lstrip(u"#")
    r, g, b = (int(colour[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    return 0.299 * r + 0.587 * g + 0.114 * b


def _hover_of(colour):
    u"""What `colour` becomes under the pointer. -> unicode

    ⭐ DIRECTION FOLLOWS THE SURFACE, which is what every current UI does and
    what *good taste of modern UI design* actually means here: a dark, recessed
    control LIFTS toward the light, and a bright filled control DEEPENS. Both
    read as *pressed toward you*; doing the same thing to both does not.

    ⚠ MEASURED, and this is why it is not one rule: lifting the accent
    `#6aa8d8` by 10% gives `#79b1dc` — a 15/255 step on an already-bright fill,
    invisible in a screenshot — while lifting the dark `#2b3038` gives
    `#43474e`, which is obvious. The same number is a different amount of
    signal depending on where it starts.
    """
    if _luma(colour) >= 0.5:
        return _shade(colour, -PRESS_SINK)
    return _shade(colour, HOVER_LIFT)


def _interactive(widget, base, fg=None):
    u"""Give a widget a hover and a press state. -> the widget

    ⛔ `activebackground` IS NOT A HOVER. Tk's `active` state is the PRESSED
    state for a Button; the widget was built with `activebackground=bg`, so
    pressing changed nothing and hovering changed nothing either — every
    button in the window was visually inert under the pointer.

    ⚠ The bindings read the widget's CURRENT background rather than closing
    over the one passed in, because the Sync button legitimately changes
    colour when a run starts (Sync → Stop, accent → red). A closure would
    restore the wrong colour on leave, which is worse than no hover at all.
    """
    widget.configure(activebackground=_shade(base, -PRESS_SINK))
    if fg is not None:
        widget.configure(activeforeground=fg)

    def enter(_e):
        if str(widget.cget(u"state")) == u"disabled":
            return
        widget._resting = widget.cget(u"bg")
        widget.configure(bg=_hover_of(widget._resting))

    def leave(_e):
        resting = getattr(widget, u"_resting", None)
        if resting:
            widget.configure(bg=resting, activebackground=_shade(
                resting, -PRESS_SINK))
            widget._resting = None

    widget.bind(u"<Enter>", enter, add=u"+")
    widget.bind(u"<Leave>", leave, add=u"+")
    return widget

#: How often the window asks the runner what has arrived. ⚠ Milliseconds of
#: wall clock, not a pixel count -- it does NOT go through `px()`.
TICK_MS = 60


class App(object):
    u"""One state object; every view is a pure function of it.

    `doctrine/architecture` rule 1. `self.run`, `self.runner`, `self.folder`
    and `self.settings` are the whole state, and `_repaint()` is the only
    thing that writes to the screen from it. ⚠ Rows are INSERTED as they
    arrive rather than re-rendered, which is the one deliberate exception —
    and refusals still land first, because a non-confident row is inserted at
    index 0 and a confident one at the end, so the ruled ordering holds
    incrementally instead of being restored by a sort that could be forgotten.
    """

    def __init__(self, root, settings=None, runner_factory=None):
        self.root = root
        self.settings = settings or _settings.Settings.load()
        #: ⭐ INJECTED, on the same seam as `pipeline.sync(reader=...)`. It is
        #: what lets the suite drive this window without spawning anything.
        self.runner_factory = runner_factory or _run.Runner
        self.scale = Scale(root)
        self.fonts = _fonts()
        self.runner = None
        self.run = None
        self.rows = []
        self.notes = []
        #: Tk item id -> the `Row` it was built from. ⚠ CLEARED ON EVERY RUN.
        #: Tk reuses item ids (`I001` and up) after a `delete`, so an entry
        #: left over from the previous run can be reached by a fresh item that
        #: has not been mapped yet — a detail pane describing a file from a
        #: folder the user has already moved on from. Narrow, because each
        #: insert overwrites its own id immediately, and free to close.
        self._row_by_item = {}
        self.message = u""
        self.folder = u""
        self._build()
        self._restore_folder()
        self._repaint()

    # -- construction -------------------------------------------------------

    def _build(self):
        S, F = self.scale, self.fonts
        self.root.title(u"tsubasa")
        self.root.configure(bg=BG)

        style = ttk.Style(self.root)
        style.theme_use(u"clam")
        style.configure(u"T.Treeview", background=BG, fieldbackground=BG,
                        foreground=INK, rowheight=S.px(30), borderwidth=0,
                        font=F[u"ui"])
        style.configure(u"T.Treeview.Heading", background=PANEL,
                        foreground=DIM, relief=u"flat", font=F[u"small"],
                        padding=S.px(6))
        # 🚨 THE HEADINGS TURNED **WHITE** UNDER THE POINTER, in a dark window.
        # `configure` sets the resting look and says nothing about any state,
        # so clam's own `active` and `pressed` maps were still in force — and
        # clam is a LIGHT theme, so its active background is near-white. The
        # column titles flashed white on a #1c1f25 panel every time the mouse
        # crossed them.
        # ⭐ The fix is a map, not a different colour: the heading lifts by the
        # same step every other control uses, and its text brightens DIM → INK
        # so the feedback reads as *this is live* rather than as a selection.
        # ⚠ `pressed` is mapped too — a heading here sorts nothing, so it must
        # not look like it just did something.
        style.map(u"T.Treeview.Heading",
                  background=[(u"pressed", _shade(PANEL, HOVER_LIFT)),
                              (u"active", _shade(PANEL, HOVER_LIFT))],
                  foreground=[(u"pressed", INK), (u"active", INK)],
                  relief=[(u"pressed", u"flat"), (u"active", u"flat")])
        # 🚨 THE SELECTION MAY NOT ERASE THE OUTCOME COLOUR. clam maps
        # `foreground` on `selected`, which overrode the row's tag — so the
        # REFUSED row, the one the eye lands on, rendered plain white while
        # the ERROR row below it kept its colour. An empty list is how you say
        # *no dynamic mapping*, and lets the tag through.
        style.map(u"T.Treeview", background=[(u"selected", SEL)],
                  foreground=[])
        style.configure(u"T.Vertical.TScrollbar", background=PANEL,
                        troughcolor=BG, bordercolor=BG, arrowcolor=DIM)

        # 🚨 THE BOTTOM IS PACKED BEFORE THE MIDDLE, AND THAT ORDER IS THE
        # WHOLE FIX. Tk's packer walks widgets in packing order and hands each
        # one what it asks for out of the remaining cavity; a middle packed
        # `expand=True` first takes everything, and the counts strip packed
        # afterwards gets **nothing** — measured, on the first real run of this
        # window: the footer was starved to zero height and the capture
        # harness reported *"the counts strip is not at the bottom."*
        # ⭐ `doctrine/architecture`: *make the bug structurally impossible,
        # not compensated for.* Header, then footer, then the scroller that
        # takes what is left — in that order the overlap cannot happen at any
        # window size, rather than being correct at the size we happened to
        # test.
        self._build_bar()
        tk.Frame(self.root, bg=EDGE, height=S.px(1)).pack(fill=u"x")
        # ⚠ THE CREDIT CLAIMS THE BOTTOM FIRST, so the counts strip packed
        # next sits ABOVE it. `side="bottom"` gives the LAST-packed widget
        # the position nearest the middle, which reads backwards and is
        # exactly the ordering trap the note above was written about.
        self._build_credit()
        self._build_footer()
        tk.Frame(self.root, bg=EDGE,
                 height=S.px(1)).pack(fill=u"x", side=u"bottom")
        middle = tk.Frame(self.root, bg=BG)
        middle.pack(fill=u"both", expand=True)
        self._build_detail(middle)
        self._build_table(middle)
        self._arm_drop_target()
        self._size_the_window()

    def _size_the_window(self):
        u"""Give it the ruled size, then let the person resize it.

        🚨 PINNED AFTER THE CONTENT EXISTS, NEVER BEFORE. `geometry()` set on
        a toplevel with no children yet loses to the geometry manager on first
        map — measured twice now, and the second time in this very file: the
        window asked for 1647 px and came out **1089**, because a `Treeview`
        asks for its `height=` rows and gets them.

        ⛔ AND THE FIRST DRAFT UNDID ITS OWN FIX ON THE NEXT LINE, calling
        `minsize`/`maxsize` again straight after `pin()` — which is exactly
        the clamp `pin` had just set, replaced with a loose one. The order is
        load-bearing: pin, map, *then* relax.

        ⭐ `pin` clamps `min == max` so the manager cannot improve on the
        size; that also forbids the USER resizing, which is wrong for a window
        holding a table. So the clamp is released once the window is mapped —
        by which point the requested size has already been honoured and the
        manager has nothing left to argue about.
        """
        S = self.scale
        self.root.update_idletasks()
        # 🚨 PROPAGATION OFF **BEFORE** THE CLAMP IS RELEASED, or the size is
        # a coin toss. Measured: two consecutive runs of the same probe, one
        # window 1647 px tall and the next 1089, with nothing changed between
        # them. `pin`'s `min == max` was the only thing holding the height,
        # and releasing it handed the toplevel straight back to the geometry
        # manager, which resized it to whatever its children happened to ask
        # for. ⭐ `pack_propagate(False)` is what makes the window's size the
        # window's own business — then the clamp can go and the size stays.
        # ⚠ A non-deterministic layout is worse than a wrong one: it is green
        # on the run you look at.
        self.pin = pin = S.pin(self.root, 1060, 660)
        if pin.clamped:
            self.message = pin.why
        self.root.pack_propagate(False)
        self.root.after(0, self._allow_resize)

    def _allow_resize(self):
        u"""Let the person make it BIGGER. ⛔ Never smaller.

        🚨 THE SHRINK PATH IS THE BUG, SO IT IS THE PATH THAT STAYS CLOSED.
        Releasing the clamp to a loose minimum made the size a coin toss —
        two consecutive runs of the same probe, nothing changed between them,
        one window 1647 px tall and the next **1089**, because the geometry
        manager took the toplevel back and resized it to what its children
        asked for. `pack_propagate(False)` did not stop it either.

        ⭐ A floor AT the ruled size is deterministic and still resizable:
        the manager has nothing to shrink into, and a person can still drag it
        larger for a big library. ⚠ And the floor is `pin`'s ACTUAL size, not
        the design size — on a small screen `pin` clamps, and a minimum bigger
        than the window it is applied to is the clipping defect again.
        """
        S = self.scale
        self.root.minsize(self.pin.width, self.pin.height)
        self.root.maxsize(S.area[2] - S.area[0], S.area[3] - S.area[1])
        self.root.resizable(True, True)

    def _build_bar(self):
        S, F = self.scale, self.fonts
        bar = tk.Frame(self.root, bg=PANEL)
        bar.pack(fill=u"x", side=u"top")
        inner = tk.Frame(bar, bg=PANEL)
        inner.pack(fill=u"x", padx=S.px(12), pady=S.px(10))

        tk.Label(inner, text=u"Folder", bg=PANEL, fg=DIM,
                 font=F[u"small"]).pack(side=u"left", padx=(0, S.px(8)))
        self.folder_var = tk.StringVar()
        self.entry = tk.Entry(inner, textvariable=self.folder_var, bg=BG,
                              fg=INK, font=F[u"ui"], insertbackground=INK,
                              relief=u"flat", highlightthickness=S.px(1),
                              highlightbackground=EDGE, highlightcolor=ACCENT)
        self.entry.pack(side=u"left", fill=u"x", expand=True,
                        ipady=S.px(5), padx=(0, S.px(8)))
        self.folder_var.trace_add(u"write", lambda *_: self._folder_typed())

        # ⚠ PACKED RIGHT-TO-LEFT, so this list is REVERSED on screen:
        # `Browse…  Sync  ☐ Dry run  ⚙`. ⭐ That is the order in the mockup
        # Sonic ruled on, and the first build silently swapped Browse and
        # Sync — you browse for a folder and then sync it, so the primary
        # action sitting to the LEFT of the thing that fills its input reads
        # backwards. Found by looking at a screenshot of the real window.
        self.settings_btn = _button(inner, S, F, u"⚙", EDGE, INK,
                                    self.open_settings, pad=10)

        # ⭐ DRY RUN STAYS ON THE BAR, and it is the one option that does.
        # Everything else went into settings because Sonic ruled the window
        # stays clean — but a preview is a per-RUN decision, not a
        # configuration, and it was in the picture he approved. ⛔ It is the
        # SAME state as the settings panel's copy; there is one value, and
        # both controls read and write it.
        self.dry_var = tk.BooleanVar(value=bool(self.settings.get(u"dry_run")))
        self.dry_chk = tk.Checkbutton(
            inner, text=u"Dry run", variable=self.dry_var, bg=PANEL, fg=DIM,
            font=F[u"ui"], selectcolor=BG, activebackground=PANEL,
            activeforeground=INK, relief=u"flat", highlightthickness=0,
            borderwidth=0, command=self._dry_toggled)
        self.dry_chk.pack(side=u"right", padx=(S.px(8), 0))

        self.sync_btn = _button(inner, S, F, u"Sync", ACCENT, u"#0e1114",
                                self.toggle_run)
        self.browse_btn = _button(inner, S, F, u"Browse…", EDGE, INK,
                                  self.browse)

    def _dry_toggled(self):
        self.settings.set(u"dry_run", bool(self.dry_var.get()))
        try:
            self.settings.save()
        except (IOError, OSError):
            pass                        # ⚠ never fatal — see `_remember_folder`
        self._repaint()

    def _build_table(self, parent):
        S, F = self.scale, self.fonts
        self._cell_px = {}
        holder = tk.Frame(parent, bg=BG)
        holder.pack(fill=u"both", expand=True, padx=S.px(12),
                    pady=(S.px(10), 0))
        bar = ttk.Scrollbar(holder, orient=u"vertical",
                            style=u"T.Vertical.TScrollbar")
        cols = (u"ep", u"sub", u"out", u"off", u"ev")
        self.tree = ttk.Treeview(holder, columns=cols, show=u"tree headings",
                                 style=u"T.Treeview", yscrollcommand=bar.set)
        bar.config(command=self.tree.yview)
        bar.pack(side=u"right", fill=u"y")
        self.tree.pack(side=u"left", fill=u"both", expand=True)

        self.tree.heading(u"#0", text=u"")
        self.tree.column(u"#0", width=S.px(36), stretch=False,
                         anchor=u"center")
        for key, title, w, anchor in (
                (u"ep", u"EP", 44, u"center"),
                (u"sub", u"SUBTITLE", 296, u"w"),
                (u"out", u"WRITTEN", 236, u"w"),
                (u"off", u"OFFSET", 186, u"w"),
                (u"ev", u"EVIDENCE", 216, u"w")):
            self.tree.heading(key, text=title)
            self.tree.column(key, width=S.px(w), anchor=anchor,
                             stretch=(key == u"ev"))
            # ⚠ A MARGIN, so a trimmed name does not touch the next column.
            # ttk gives no cell padding, and *touching* is what made a
            # filename and the next column's em-dash read as one token.
            self._cell_px[key] = S.px(w) - S.px(10)
        for name, fg in ((_run.CONFIDENT, OK), (_run.REFUSED, BAD),
                         (_run.ERROR, ERR), (u"cut", CUT)):
            self.tree.tag_configure(name, foreground=fg)
        self.tree.bind(u"<<TreeviewSelect>>", lambda _e: self._repaint())

    def _build_detail(self, parent):
        S, F = self.scale, self.fonts
        tk.Frame(parent, bg=EDGE, height=S.px(1)).pack(fill=u"x",
                                                       side=u"bottom",
                                                       pady=(S.px(10), 0))
        pane = tk.Frame(parent, bg=PANEL)
        pane.pack(fill=u"x", side=u"bottom")
        box = tk.Frame(pane, bg=PANEL)
        box.pack(fill=u"x", padx=S.px(14), pady=S.px(12))
        self.detail_head = tk.Label(box, text=u"", bg=PANEL, fg=DIM,
                                    font=F[u"ui_b"], anchor=u"w")
        self.detail_head.pack(fill=u"x")
        self.detail_body = tk.Label(box, text=u"", bg=PANEL, fg=INK,
                                    font=F[u"ui"], anchor=u"w",
                                    justify=u"left", wraplength=S.px(980))
        self.detail_body.pack(fill=u"x", pady=(S.px(6), S.px(8)))
        self.detail_foot = tk.Label(box, text=u"", bg=PANEL, fg=DIM,
                                    font=F[u"small"], anchor=u"w")
        self.detail_foot.pack(fill=u"x")

    def _build_footer(self):
        S, F = self.scale, self.fonts
        foot = tk.Frame(self.root, bg=PANEL)
        foot.pack(fill=u"x", side=u"bottom")
        row = tk.Frame(foot, bg=PANEL)
        row.pack(fill=u"x", padx=S.px(12), pady=S.px(9))
        self.chips = tk.Frame(row, bg=PANEL)
        self.chips.pack(side=u"left")
        self.elapsed_lbl = tk.Label(row, text=u"", bg=PANEL, fg=DIM,
                                    font=F[u"ui"])
        self.elapsed_lbl.pack(side=u"right")
        self.tail_lbl = tk.Label(row, text=u"", bg=PANEL, fg=DIM,
                                 font=F[u"ui"])
        self.tail_lbl.pack(side=u"right", padx=(0, S.px(16)))

    def _build_credit(self):
        u"""`Created by SonicSandbox | GitHub`, bottom right, faded.

        ⭐ RULED 2026-09-17: *"bottom right in faded text so its not in the
        way but there."* So it is `DIM` on the window ground rather than on
        the counts panel, a size down, and it sits BELOW the counts strip —
        the counts are the thing being read, this is the thing being noticed
        once.

        ⚠ The link is a `Label`, not a `Button`: a button draws a box, and a
        box in the corner of every screenshot is exactly the distraction that
        was ruled out. It gets the hand cursor and an underline on hover, so
        it still announces itself as clickable — `doctrine/architecture`: a
        control that does not answer the pointer reads as decoration.
        """
        S, F = self.scale, self.fonts
        strip = tk.Frame(self.root, bg=BG)
        strip.pack(fill=u"x", side=u"bottom")
        row = tk.Frame(strip, bg=BG)
        row.pack(side=u"right", padx=S.px(14), pady=(0, S.px(6)))

        #: ⚠ A size below the small font and dimmer than DIM. Measured against
        #: the brief — *not in the way* — rather than chosen by feel.
        faint = _shade(DIM, -0.35)
        self.credit_lbl = tk.Label(row, text=u"Created by SonicSandbox",
                                   bg=BG, fg=faint, font=F[u"tiny"])
        self.credit_lbl.pack(side=u"left")
        tk.Label(row, text=u"|", bg=BG, fg=_shade(faint, -0.25),
                 font=F[u"tiny"]).pack(side=u"left", padx=S.px(6))
        self.github_lbl = _link(row, F[u"tiny"], u"GitHub", HOME_URL,
                                self._open_url)
        self.github_lbl.pack(side=u"left")

    def _open_url(self, url):
        u"""⛔ NEVER FATAL, and never a traceback. A windowed build has no
        stream to print one on, and a browser that will not start is not a
        reason for the window to do anything at all."""
        import webbrowser
        try:
            webbrowser.open(url)
        except Exception as exc:                          # noqa: BLE001
            self._say(u"could not open %s: %s" % (url, exc))

    def _arm_drop_target(self):
        u"""⭐ RULED: *auto-run on drop unless setting is toggled.*"""
        self.drop_armed = False
        if TkinterDnD is None or not hasattr(self.root,
                                             u"drop_target_register"):
            return
        try:
            self.root.drop_target_register(DND_FILES)
            self.root.dnd_bind(u"<<Drop>>", self._on_drop)
            self.drop_armed = True
        except tk.TclError:                               # pragma: no cover
            self.drop_armed = False

    # -- state ---------------------------------------------------------------

    def _restore_folder(self):
        if self.settings.get(u"remember_folder"):
            last = self.settings.values.get(u"_last_folder") or u""
            if last and os.path.isdir(last):
                self.folder_var.set(last)

    def _folder_typed(self):
        self.folder = self.folder_var.get()
        self._repaint()

    def _on_drop(self, event):
        u"""A folder was dropped on the window.

        ⚠ THE PAYLOAD IS A TK LIST, NOT A PATH. A dropped path containing a
        space arrives brace-wrapped — `{C:/Anime/片田舎のおっさん S2}` — and
        reading it raw gives a folder that does not exist. `splitlist` is the
        thing that knows the quoting rules.

        ⭐ And a dropped FILE means the folder it is in. Dragging one episode
        onto the window is a reasonable way to say *"this show"*, and
        refusing it would be pedantry.
        """
        paths = _dropped_paths(self.root, event.data)
        if not paths:
            self._say(u"nothing usable was dropped — drop a folder, or a "
                      u"video or subtitle inside one.")
            return
        first = paths[0]
        folder = first if os.path.isdir(first) else os.path.dirname(first)
        if not os.path.isdir(folder):
            self._say(u"%s is not a folder and is not in one." % first)
            return
        self.folder_var.set(folder)
        if self.settings.get(u"auto_run_on_drop"):
            self.start()

    def browse(self):
        u"""Ask for a folder. ⛔ THE DIALOG IS OWNED, AND IT STARTS SOMEWHERE.

        🚨 *"it has the thinking icon, the gui freezes, it feels
        discontinued."* Measured 2026-09-17, and the app is **not** frozen:
        29 `after()` ticks ran during 3.4 s of dialog and `IsHungAppWindow`
        stayed False throughout. ⛔ So no amount of threading was ever the fix
        — and it could not have been, since a native modal must pump messages
        on the thread that owns its parent.

        Three things were actually wrong, and all three are here:

          1. **The dialog had no owner.** Windows could not dim or block the
             right window, so the app sat there looking live and ignoring
             clicks. `parent` is now the real window handle.
          2. **It started nowhere**, so it walked the whole shell namespace
             with a wait cursor — the *"thinking icon"*. It now opens on the
             folder already in the box.
          3. **It was the 2001 dialog** (`folderpick`, measured: window class
             `#32770`). The modern picker is tried first and falls back.

        ⚠ The busy cursor is set DELIBERATELY and `update_idletasks()` forces
        it to paint before the modal opens — a cursor change queued behind a
        blocking call arrives after the thing it was meant to explain.
        """
        start = (self.folder_var.get() or u"").strip()
        if not os.path.isdir(start):
            start = u""
        try:
            self.root.configure(cursor=u"watch")
            self.root.update_idletasks()
            chosen = _folderpick.ask(parent=self.root.winfo_id(),
                                     title=u"Pick a folder of videos",
                                     start=start)
        finally:
            # ⛔ RESTORED IN A `finally`. A window left holding the busy
            # cursor is the exact complaint this method exists to answer, and
            # the dialog can raise.
            self.root.configure(cursor=u"")
        if chosen:
            self.folder_var.set(chosen)
            self._folder_typed()

    def toggle_run(self):
        if self.running:
            self.stop()
        else:
            self.start()

    @property
    def running(self):
        return self.runner is not None and self.runner.finished() is None

    def start(self):
        u"""Spawn a run. ⛔ Every refusal is a sentence, never a traceback."""
        if self.running:
            return
        folder = self.folder_var.get().strip()
        try:
            options = self.settings.run_options()
            runner = self.runner_factory(folder, **options)
        except ValueError as exc:
            # ⭐ `argv_for` refuses a blank folder, `--force` on a scan, and
            # `--out` with in-place retiming, each in a sentence written for a
            # person. Printing that sentence is better than re-deriving the
            # rule here and letting the two drift.
            self._say(u"%s" % exc)
            return

        self.runner = runner
        self.run = None
        self.rows = []
        self.notes = []
        self.message = u""
        self.tree.delete(*self.tree.get_children())
        self._row_by_item = {}          # ⚠ see the note in `__init__`
        self._remember_folder(folder)
        try:
            self.runner.start()
        except OSError as exc:
            # 🚨 THE CHILD COULD NOT BE SPAWNED AT ALL, AND BEFORE THIS GUARD
            # THAT WAS COMPLETELY SILENT. `Popen` raises `FileNotFoundError`
            # when `tsubasa.exe` is not beside `tsubasa-gui.exe` — the exact
            # state `STANDALONE-BUILD-SCOPE.md` trap 1 exists for, and the one
            # Defender produces by quarantining one executable and not the
            # other. Found by an adversarial pass driving the NEGATIVE of trap
            # 1, which every check here had only ever driven positively.
            #
            # ⛔ AND `self.runner` MUST BE CLEARED, not just reported. It was
            # assigned above, before the throwing call, so `running` —
            # *runner is not None and finished() is None* — stayed True FOR
            # EVER: the button never left "Stop", the next click went to
            # `stop()` and raised `NotStarted`, and **putting the missing file
            # back did not help.** Only killing the app did.
            self.runner = None
            self._say(
                u"the command line could not be started: %s. This app runs "
                u"%s. If this is the standalone, tsubasa.exe must sit in the "
                u"same folder as tsubasa-gui.exe — antivirus quarantine is "
                u"the usual reason one of them is missing."
                % (exc, runner.argv[0] if runner.argv else u"?"))
            return
        self._repaint()
        self.root.after(TICK_MS, self._tick)

    def stop(self):
        if self.runner is not None and self.running:
            self.runner.cancel()
            self._say(u"stopping — waiting for the current file to finish so "
                      u"nothing is left half-written.")

    def _remember_folder(self, folder):
        if not self.settings.get(u"remember_folder"):
            return
        try:
            self.settings.values[u"_last_folder"] = folder
            self.settings.save()
        except (IOError, OSError):
            # ⚠ NOT FATAL. Failing to remember a folder must never stop a run.
            pass

    def _tick(self):
        u"""⛔ NEVER BLOCKS. `drain()` is guaranteed not to wait on the child;
        this is the only thing that calls it."""
        if self.runner is None:
            return
        for kind, payload in self.runner.drain():
            if kind == u"row":
                self._add_row(payload)
            elif kind == u"fault":
                self.notes.append(payload.why)
            elif kind == u"note":
                if payload.strip():
                    self.notes.append(payload.strip())
            elif kind == u"done":
                self.run = payload
        self._repaint()
        if self.running:
            self.root.after(TICK_MS, self._tick)

    def _add_row(self, row):
        u"""⭐ REFUSALS AT INDEX 0, SUCCESSES AT THE END.

        `05-interface.md` makes the ordering load-bearing — *the one thing
        needing attention must not sit below 23 successes* — and this keeps it
        true while rows are still arriving, rather than restoring it with a
        sort at the end that a later edit could drop.
        """
        self.rows.append(row)
        bad = row.outcome != _run.CONFIDENT
        tag = u"cut" if row.is_cut else row.outcome
        mark = u"⚑" if row.is_cut else MARK.get(row.outcome, u"·")
        evidence = (u"%d%% match · %s" % (row.match_percent, row.verdict_word)
                    if row.match_percent is not None and row.verdict_word
                    else row.outcome)
        offsets = _offsets(row)
        font = self.fonts[u"ui"]
        item = self.tree.insert(
            u"", 0 if bad else u"end", text=mark, tags=(tag,), values=(
                u"%02d" % row.episode if row.episode is not None else u"",
                _fit(row.name, font, self._cell_px[u"sub"]),
                _fit(row.written_name or u"—", font, self._cell_px[u"out"]),
                offsets, evidence))
        # ⚠ Mapped before selected. Not load-bearing — `<<TreeviewSelect>>` is
        # QUEUED, not synchronous, so both lines complete before any handler
        # runs. Measured while writing the check that assumed otherwise. It is
        # this way round because it reads as obviously correct, not because
        # the other order was a bug.
        self._row_by_item[item] = row
        if len(self.rows) == 1 or (bad and not self.tree.selection()):
            self.tree.selection_set(item)

    def _say(self, message):
        self.message = message
        self._repaint()

    # -- painting ------------------------------------------------------------

    def _repaint(self):
        u"""The only thing that writes to the screen. ⛔ No static derived text:
        every value here is read from state on every tick."""
        self.sync_btn.config(text=u"Stop" if self.running else u"Sync",
                             bg=BAD if self.running else ACCENT)
        state = u"disabled" if self.running else u"normal"
        self.browse_btn.config(state=state)
        self.settings_btn.config(state=state)
        self.dry_chk.config(state=state)
        # ⭐ ONE VALUE, TWO CONTROLS. The settings panel can change `dry_run`
        # while the bar's checkbox is on screen; without this the two disagree
        # and the one you are looking at is a lie. `doctrine/architecture`:
        # *every displayed value derives from the state on every render.*
        if bool(self.dry_var.get()) != bool(self.settings.get(u"dry_run")):
            self.dry_var.set(bool(self.settings.get(u"dry_run")))
        self._paint_detail()
        self._paint_footer()

    def _paint_detail(self):
        selected = self.selected_row()
        if self.message:
            self.detail_head.config(text=u"", fg=DIM)
            self.detail_body.config(text=self.message, fg=INK)
            self.detail_foot.config(text=u"")
            return
        if selected is None:
            self.detail_head.config(text=u"", fg=DIM)
            self.detail_body.config(text=self._idle_text(), fg=DIM)
            self.detail_foot.config(text=u"")
            return
        row = selected
        self.detail_head.config(
            text=u"%s   %s%s" % (
                row.outcome,
                u"ep %02d   " % row.episode if row.episode is not None
                else u"",
                row.name),
            fg=CUT if row.is_cut else COLOUR.get(row.outcome, DIM))
        self.detail_body.config(text=row.reason or _confident_sentence(row),
                                fg=INK)
        self.detail_foot.config(text=_detail_line(row))

    def _idle_text(self):
        if self.running:
            return u"running…"
        if self.drop_armed:
            return u"Drop a folder here, or pick one above."
        return (u"Pick a folder above. Dropping one on the window needs "
                u"tkinterdnd2, which did not load: %s" % (DND_ERROR or u"?"))

    def _paint_footer(self):
        u"""🚨 THE ONE LINE A PERSON READS AT A GLANCE.

        ⛔ Every number is `run.counts`, which partitions, and nothing here
        adds two of them together. `clean` and `cut` are separate chips
        because `cut` is a SUBSET of `confident` — printing both from
        `confident` is how ten files read as eleven.
        """
        for child in self.chips.winfo_children():
            child.destroy()
        counts = _run.counts(self.rows)
        S, F = self.scale, self.fonts

        def chip(text, fg):
            tk.Label(self.chips, text=text, bg=PANEL, fg=fg,
                     font=F[u"ui_b"]).pack(side=u"left", padx=(0, S.px(16)))

        # ⛔ NO COUNTS BEFORE THERE IS ANYTHING TO COUNT. An idle window read
        # `✓ 0 would sync`, which is a claim that a run happened and found
        # nothing — the same shape as every other defect on this strip, at its
        # smallest. `doctrine/architecture`: *controls vanish when they would
        # be meaningless.* Found by looking at the window before pressing Sync.
        if not self.rows and self.run is None and not self.running:
            return

        dry = self.run.dry_run if self.run is not None \
            else self.settings.get(u"dry_run")
        verb = u"would sync" if dry else u"synced"
        chip(u"✓ %d %s" % (counts[u"clean"], verb), OK)
        if counts[u"cut"]:
            chip(u"⚑ %d repaired" % counts[u"cut"], CUT)
        if counts[u"write_failed"]:
            # ⚠ `⊘` AND NOT `⛔`. The static check caught the latter: it is one
            # of this project's DOCTRINE markers, and using it as a UI glyph
            # means the check that keeps markers off the screen has to carve
            # out an exception — at which point it stops being a check.
            chip(u"⊘ %d NOT written" % counts[u"write_failed"], BAD)
        if counts[u"refused"]:
            chip(u"✗ %d refused" % counts[u"refused"], BAD)
        if counts[u"errored"]:
            chip(u"! %d error" % counts[u"errored"], ERR)
        if counts[u"unknown"]:
            chip(u"? %d not understood" % counts[u"unknown"], ERR)

        # 🚨 THE RIGHT-HAND SIDE MAY NOT RESTATE THE COUNTS.
        #
        # The first build put the chips on the left and `Run.headline()` on
        # the right, so one window read `✓ 4 would sync  ⚑ 2 repaired` beside
        # `1 error · 1 refused · 6 would sync · 2 repaired` — **4 and 6, on
        # one line, both correct.** The chips PARTITION (clean and cut are
        # separate); the headline totals them for a caller that wants one
        # sentence. Showing both is the ten-files-read-as-eleven defect
        # arriving from the opposite direction, and looking at a real run is
        # the only thing that found it. ⭐ The right-hand side now says what
        # the chips CANNOT: what happened to the folder, and how long it took.
        tail = []
        if counts[u"superseded"]:
            tail.append(u"%d superseded → trash" % counts[u"superseded"])
        if self.notes:
            tail.append(u"%d note%s" % (len(self.notes),
                                        u"" if len(self.notes) == 1 else u"s"))
        if self.run is not None and self.run.cancelled:
            tail.append(u"stopped before it finished")
        if self.run is not None and self.run.could_not_run:
            tail.append(u"the command could not be run")
        self.tail_lbl.config(text=u"   ·   ".join(tail))
        self.elapsed_lbl.config(
            text=u"running…" if self.running
            else (u"%d file%s looked at" % (len(self.rows),
                                            u"" if len(self.rows) == 1
                                            else u"s")
                  if self.run is not None else u""))

    def selected_row(self):
        items = self.tree.selection()
        if not items:
            return None
        return getattr(self, u"_row_by_item", {}).get(items[0])

    # -- settings ------------------------------------------------------------

    def open_settings(self):
        SettingsWindow(self)


def _offsets(row):
    u"""The OFFSET cell. ⚠ A cut file has more than one.

    🚨 AN UNMEASURED ROW HAS NO OFFSET, AND `+0.00s` IS NOT NONE. Found by
    looking at a real run: the ERROR row — a file with zero cues that could
    not be measured at all — displayed **`+0.00s`**, because the object still
    carries a zero-filled segment. `LEDGER.md` §Interface already records the
    same shape from the CLI at 3c (`-0.00s` on a converged folder) and
    `05-interface.md` rules that a refusal carries **no confidence word**; a
    refusal carrying a confident-looking NUMBER is the same defect wearing
    digits. ⛔ Only a row that was actually measured may show one.
    """
    if row.outcome == _run.ERROR:
        return u"—"
    segments = row.segments or ()
    if not segments:
        return u"—"
    if len(segments) == 1:
        return u"%+0.2fs" % segments[0][1]
    return u" / ".join(u"%+0.2f" % o for _s, o in segments)


def _confident_sentence(row):
    u"""What to say about a row that has no `reason`. ⛔ NOT A VERDICT — every
    word of it is a field read back."""
    if row.raw.get(u"write_failed"):
        return u"the timing was found and the file could not be written."
    if not row.raw.get(u"output_path"):
        return u"measured only — nothing was written, because this was a " \
               u"preview."
    return u"written to %s." % row.written_name


def _detail_line(row):
    bits = [u"reference: %s" % (row.raw.get(u"reference") or u"—")]
    if row.raw.get(u"raw_excess") is not None:
        bits.append(u"%.2f× chance" % row.raw.get(u"raw_excess"))
    if row.raw.get(u"runtime_check"):
        bits.append(u"runtime %s" % row.raw.get(u"runtime_check"))
    if row.raw.get(u"lang"):
        bits.append(u"language %s" % row.raw.get(u"lang"))
    for note in (row.raw.get(u"notes") or ()):
        bits.append(note)
    return u"   ·   ".join(bits)


def _dropped_paths(widget, data):
    u"""Tk's drop payload -> [str]. ⚠ See `App._on_drop`."""
    try:
        return [p for p in widget.tk.splitlist(data) if p]
    except tk.TclError:                                   # pragma: no cover
        return [data] if data else []


def _fit(text, font, pixels):
    u"""Trim `text` with an ellipsis until it fits `pixels`. -> unicode

    🚨 MEASURED, NEVER COUNTED. `doctrine/architecture`: *any "it always fits"
    guarantee is a measurement, not a formula* — and this project has the
    sharpest possible reason, because a CJK character is **two terminal cells
    and one proportional glyph of no fixed width.** `len()` is wrong twice
    over on `黄泉のツガイ.S01E01.WEBRip.ABEMA.ja[cc].srt`.

    ⚠ WITHOUT THIS, ttk CLIPS AT THE COLUMN EDGE WITH NO GAP, and a real run
    rendered `…[Multiple].s—` — the filename running straight into the next
    column's em-dash and reading as one token. That is the CLI's
    `…HEVC AAC).srtREFUSED` defect, in a table.

    ⭐ Trimmed from the END, not the middle: two release names for the same
    show differ in their tail (`- 03 (AT-X 1280x720)`), and a middle ellipsis
    eats exactly the part that tells them apart.
    """
    if not text:
        return u""
    if font.measure(text) <= pixels:
        return text
    ell = u"…"
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if font.measure(text[:mid] + ell) <= pixels:
            lo = mid
        else:
            hi = mid - 1
    return (text[:lo] + ell) if lo else ell


def _button(parent, S, F, label, bg, fg, command, pad=14):
    b = tk.Button(parent, text=label, bg=bg, fg=fg, font=F[u"ui_b"],
                  relief=u"flat", command=command, borderwidth=0,
                  highlightthickness=0, cursor=u"hand2",
                  disabledforeground=DIM)
    _interactive(b, bg, fg)
    b.pack(side=u"right", padx=(S.px(8), 0), ipadx=S.px(pad), ipady=S.px(4))
    return b


def _link(parent, font, label, url, opener):
    u"""A text link: accent colour, UNDERLINED, hand cursor, brighter on hover.

    ⭐ UNDERLINED AT REST, matching the reference Sonic gave — his example
    renders the link word underlined, not underlined-on-approach. An earlier
    draft underlined only on hover because it reads tidier; that is a
    preference, and the reference is a requirement.

    ⚠ The hover is then a BRIGHTEN rather than a rule appearing, because the
    underline is already spent as an affordance. Every interactive thing in
    this window answers the pointer with the same lift.
    """
    under = tkfont.Font(font=font)
    under.configure(underline=1)
    lbl = tk.Label(parent, text=label, bg=parent.cget(u"bg"), fg=ACCENT,
                   font=under, cursor=u"hand2")
    lbl.bind(u"<Enter>", lambda _e: lbl.configure(
        fg=_shade(ACCENT, HOVER_LIFT * 2)))
    lbl.bind(u"<Leave>", lambda _e: lbl.configure(fg=ACCENT))
    lbl.bind(u"<Button-1>", lambda _e: opener(url))
    return lbl


def _fonts():
    return dict(
        ui=tkfont.Font(family=u"Segoe UI", size=10),
        ui_b=tkfont.Font(family=u"Segoe UI", size=10, weight=u"bold"),
        small=tkfont.Font(family=u"Segoe UI", size=9),
        #: ⚠ For the credit line only. A size below `small`, so it reads as
        #: a footnote rather than as something the eye has to price in.
        tiny=tkfont.Font(family=u"Segoe UI", size=8),
    )


# ---------------------------------------------------------------------------
# the settings window
# ---------------------------------------------------------------------------

class SettingsWindow(object):
    u"""⭐ GENERATED FROM `settings.SCHEMA`, GROUP BY GROUP.

    ⛔ It does not know the name of a single option. `doctrine/architecture`:
    *a control whose identifier is missing renders perfectly and is completely
    inert — it shipped three separate times in one build.* A settings panel
    written by hand is that defect with a checkbox on it, so this one cannot
    be written by hand.
    """

    def __init__(self, app):
        self.app = app
        self.settings = app.settings
        S, F = app.scale, app.fonts
        self.top = tk.Toplevel(app.root)
        self.top.title(u"tsubasa — settings")
        self.top.configure(bg=BG)
        self.top.transient(app.root)
        self.vars = {}

        # ⚠ THE BOTTOM STRIP IS PACKED FIRST, for the same reason the main
        # window's is: a canvas packed `expand=True` before it would starve it.
        # ⛔ And the window is sized at the END — see `App._size_the_window`.
        canvas = tk.Canvas(self.top, bg=BG, highlightthickness=0)
        bar = ttk.Scrollbar(self.top, orient=u"vertical",
                            command=canvas.yview,
                            style=u"T.Vertical.TScrollbar")
        body = tk.Frame(canvas, bg=BG)
        body.bind(u"<Configure>",
                  lambda _e: canvas.configure(scrollregion=canvas.bbox(u"all")))
        window = canvas.create_window((0, 0), window=body, anchor=u"nw")
        canvas.bind(u"<Configure>",
                    lambda e: canvas.itemconfigure(window, width=e.width))
        canvas.configure(yscrollcommand=bar.set)

        strip = tk.Frame(self.top, bg=PANEL)
        strip.pack(fill=u"x", side=u"bottom")
        bar.pack(side=u"right", fill=u"y")
        canvas.pack(side=u"left", fill=u"both", expand=True)

        for key, title, blurb, options in _settings.grouped():
            self._group(body, key, title, blurb, options)

        inner = tk.Frame(strip, bg=PANEL)
        inner.pack(fill=u"x", padx=S.px(14), pady=S.px(10))
        _button(inner, S, F, u"Done", ACCENT, u"#0e1114", self.close)
        self.warning = tk.Label(inner, text=u"", bg=PANEL, fg=CUT,
                                font=F[u"small"], anchor=u"w",
                                justify=u"left", wraplength=S.px(400))
        self.warning.pack(side=u"left", fill=u"x", expand=True)
        if self.settings.note:
            tk.Label(inner, text=self.settings.note, bg=PANEL, fg=BAD,
                     font=F[u"small"]).pack(side=u"left")
        # ⛔ SIZED LAST. Same reason as `App._size_the_window`: a `geometry()`
        # set before the content exists loses to the geometry manager, and a
        # scrolling panel asks for whatever its content happens to be tall.
        self.top.update_idletasks()
        S.pin(self.top, 620, 720, x=90, y=70)
        self.top.pack_propagate(False)          # ⛔ see `_size_the_window`
        self.top.after(0, lambda: self.top.maxsize(S.screen[0], S.screen[1]))
        self._repaint()

    def _group(self, parent, key, title, blurb, options):
        S, F = self.app.scale, self.app.fonts
        head = tk.Frame(parent, bg=BG)
        head.pack(fill=u"x", padx=S.px(16), pady=(S.px(16), S.px(2)))
        tk.Label(head, text=title.upper(), bg=BG,
                 fg=BAD if key == u"reckless" else DIM,
                 font=F[u"small"], anchor=u"w").pack(fill=u"x")
        tk.Label(head, text=blurb, bg=BG, fg=DIM, font=F[u"small"],
                 anchor=u"w", justify=u"left",
                 wraplength=S.px(560)).pack(fill=u"x", pady=(S.px(2), 0))

        card = tk.Frame(parent, bg=PANEL)
        card.pack(fill=u"x", padx=S.px(16), pady=(S.px(6), 0))
        for option in options:
            self._option(card, option)

    def _option(self, parent, option):
        S, F = self.app.scale, self.app.fonts
        box = tk.Frame(parent, bg=PANEL)
        box.pack(fill=u"x", padx=S.px(14), pady=S.px(10))

        if option.kind == u"bool":
            var = tk.BooleanVar(value=bool(self.settings.get(option.key)))
            ctl = tk.Checkbutton(
                box, text=option.label, variable=var, bg=PANEL, fg=INK,
                font=F[u"ui"], selectcolor=BG, activebackground=PANEL,
                activeforeground=INK, anchor=u"w", relief=u"flat",
                highlightthickness=0, borderwidth=0,
                command=lambda k=option.key, v=var: self._changed(k, v.get()))
            ctl.pack(fill=u"x")
        else:
            tk.Label(box, text=option.label, bg=PANEL, fg=INK, font=F[u"ui"],
                     anchor=u"w").pack(fill=u"x")
            var = tk.StringVar(value=self.settings.get(option.key) or u"")
            row = tk.Frame(box, bg=PANEL)
            row.pack(fill=u"x", pady=(S.px(4), 0))
            entry = tk.Entry(row, textvariable=var, bg=BG, fg=INK,
                             font=F[u"ui"], insertbackground=INK,
                             relief=u"flat", highlightthickness=S.px(1),
                             highlightbackground=EDGE, highlightcolor=ACCENT)
            entry.pack(side=u"left", fill=u"x", expand=True, ipady=S.px(4))
            var.trace_add(u"write",
                          lambda *_a, k=option.key, v=var:
                          self._changed(k, v.get()))
            tk.Button(row, text=u"…", bg=EDGE, fg=INK, font=F[u"ui_b"],
                      relief=u"flat", borderwidth=0, highlightthickness=0,
                      cursor=u"hand2",
                      command=lambda v=var: self._pick(v)).pack(
                          side=u"left", padx=(S.px(6), 0), ipadx=S.px(8))

        self.vars[option.key] = var
        # ⭐ THE SUBSTANCE, NOT THE COMMENTARY. `build-ui`: *the tooltips need
        # to be the effect of it, not the commentary* — the harshest note in
        # that session, and it was a data-modelling error rather than a
        # display one. `Option.why` says what the setting DOES.
        tk.Label(box, text=option.why, bg=PANEL, fg=DIM, font=F[u"small"],
                 anchor=u"w", justify=u"left",
                 wraplength=S.px(520)).pack(fill=u"x", pady=(S.px(4), 0))

    def _pick(self, var):
        chosen = filedialog.askdirectory(parent=self.top)
        if chosen:
            var.set(chosen)

    def _changed(self, key, value):
        self.settings.set(key, value)
        try:
            self.settings.save()
        except (IOError, OSError) as exc:
            self.warning.config(text=u"could not save: %s" % exc, fg=BAD)
            return
        self._repaint()
        self.app._repaint()

    def _repaint(self):
        active = self.settings.reckless_active()
        if active:
            self.warning.config(
                text=u"%s on — tsubasa will ask before it writes."
                     % u", ".join(o.label for o in active), fg=CUT)
        else:
            self.warning.config(text=u"", fg=DIM)

    def close(self):
        self.top.destroy()


# ---------------------------------------------------------------------------
# entry
# ---------------------------------------------------------------------------

def make_root():
    u"""The Tk root, DPI-aware, with drag-and-drop if the toolkit is here.

    ⛔ `make_process_dpi_aware()` RUNS FIRST AND THAT IS NOT NEGOTIABLE. Tk
    reads the screen metrics once, at root creation; called afterwards the
    call still SUCCEEDS and every geometry number in the process is of a
    virtualised 96 dpi screen. `LEDGER.md`: *a DPI-aware window clipped its
    own button off the screen.*
    """
    awareness = make_process_dpi_aware()
    root = _dnd_root_or_plain()
    _make_failures_visible(root)
    return root, awareness


def _dnd_root_or_plain():
    u"""The root, with drag-and-drop if the toolkit actually WORKS. -> `tk.Tk`

    🚨 GUARDING THE IMPORT IS NOT GUARDING THE TOOLKIT. `tkinterdnd2` imports
    cleanly and then `TkinterDnD.Tk()` calls `_require`, which loads a **Tcl**
    package from disk and raises `RuntimeError('Unable to load tkdnd
    library.')` when it is not there.

    ⛔ MEASURED IN THE FROZEN APP: renaming ONE file —
    `_internal/tkinterdnd2/tkdnd/win-x64/libtkdnd2.10.2.dll` — replaced the
    whole window with *"Failed to execute script 'entry_gui' due to unhandled
    exception."* The module note above promises the opposite, and the footer
    sentence that states the reason was **unreachable in a frozen build**: the
    Python module lives in the PYZ and cannot go missing, so the only thing
    that CAN go missing was the one thing not guarded.

    ⭐ Falling back to a plain root costs the drop target and nothing else —
    Browse still works, which is what `doctrine/architecture`'s *instruction,
    not refusal* asks for.
    """
    global DND_FILES, TkinterDnD, DND_ERROR
    if TkinterDnD is None:
        return tk.Tk()
    try:
        return TkinterDnD.Tk()
    except Exception as exc:                              # noqa: BLE001
        # ⚠ The names are cleared too, so `App` takes the same no-drop branch
        # it takes when the import failed — one state, not two.
        DND_ERROR = u"%s: %s" % (type(exc).__name__, exc)
        DND_FILES, TkinterDnD = None, None
        return tk.Tk()


def _make_failures_visible(root, show=None):
    u"""🚨 A WINDOWED APP SWALLOWS EVERY EXCEPTION A BUTTON RAISES.

    `console=False` means `sys.stdout` and `sys.stderr` are **None**. Tk's
    default `report_callback_exception` prints to `sys.stderr`; `print` then
    falls back to `sys.stdout`; with both None `print` is a documented no-op.
    ⛔ So a callback that raised did **absolutely nothing observable** — no
    dialog, no log, no change on screen. CPython's own `tkinter` docstring
    says an application *"should override this when sys.stderr is None"*, and
    this one did not.

    ⭐ Measured by an adversarial pass: with `tsubasa.exe` removed, pressing
    Sync left the window byte-identical and the app permanently wedged. The
    specific cause is fixed in `start()`; this is the net under every OTHER
    button, because the next one will not be found the same way.

    ⚠ `show` IS INJECTED, and not only for the suite: a real `tk_messageBox`
    BLOCKS until somebody clicks it, so a check that reached the shipped
    delivery would hang the runner rather than fail it. The seam is the same
    one `Runner(popen=)` and `sync(reader=)` use.
    """
    deliver = show or (lambda title, detail: messagebox.showerror(
        title, detail, parent=root))

    def report(exc_type, exc_value, _tb):
        try:
            deliver(u"tsubasa hit a problem it did not expect",
                    u"%s: %s" % (exc_type.__name__, exc_value))
        except Exception:                                 # noqa: BLE001
            # ⛔ The reporter may not become the failure. `LEDGER-HOT.md` has
            # three instruments killed by their own subject matter in one day,
            # and this one runs in a process with no stream to complain on.
            pass

    root.report_callback_exception = report


def main(argv=None):
    root, awareness = make_root()
    app = App(root)
    if awareness.note:
        app._say(awareness.note)
    root.mainloop()
    return 0


__all__ = ["App", "SettingsWindow", "main", "make_root"]
