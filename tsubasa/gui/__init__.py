# -*- coding: utf-8 -*-
u"""
The GUI. RUNBOOK step 3d. Authority: `05-interface.md`, `01-scope.md` item 17.

    python -m tsubasa.gui

⭐ **A WINDOW OVER THE CLI, AND NOTHING MORE.** `01-scope.md` item 17 is
*"GUI — tkinter, shelling out to the CLI"*, and that is a design constraint
rather than an implementation note: the CLI already owns every outcome, every
confidence word, every reason and every count, and it is the thing 50 checks
and 45 mutants are pointed at. A GUI that imported `sync()` would become a
second caller with its own opinions about flags, ordering and failure — which
is the shape `cli.py`'s own header refuses in the same words.

⛔ **So nothing in this package decides anything either.** It spawns
`python -m tsubasa --json`, reads NDJSON, and paints it.

---------------------------------------------------------------------------
The four constraints this step is, in the RUNBOOK's own words
---------------------------------------------------------------------------

  1  tkinter
  2  shells out to the CLI
  3  DPI-aware geometry
  4  the `"confident"` substring

⭐ **3 and 4 are the two defects `LEDGER.md` §Interface actually records**, and
both are load-bearing enough to live in code rather than in prose:

  * `scale.Scale` — Tk scales FONTS once the process is DPI-aware and leaves
    every pixel number alone. Measured on the build machine: 239.6 dpi, so a
    window asked for `900x600` is 360 logical pixels wide around 3.3x-scaled
    text. *A DPI-aware window clipped its own button off the screen.*
  * `run.counts` — every number a person reads at a glance is computed from
    the `outcome` FIELD of the parsed rows. *"11 confident, 1 refused"*
    contains the word `confident`.

---------------------------------------------------------------------------
⚠ A PART 1 DEFECT, RECORDED RATHER THAN DECIDED QUIETLY
---------------------------------------------------------------------------

**The spec never says how the GUI is launched.** `01-scope.md` item 17 names
it, `07-test-plan.md` covers it, `10-deployment.md` describes a PyInstaller
`--onedir` bundle and names no entry point for it. `python -m tsubasa.gui`
is chosen here to mirror `python -m tsubasa`, and `RUNBOOK.md` §3d carries the
gap so 4a resolves it deliberately — a Windows bundle wants a `gui_scripts`
entry point, not a `console_scripts` one, or the app opens with a console
window attached for the life of the process.
"""
from .run import (Fault, NotStarted, Row, Run, Runner,            # noqa: F401
                  StillRunning, argv_for, counts, parse_line)
# ⚠ `make_process_dpi_aware` IS EXPORTED, and it was not. The one function in
# this package that has to run FIRST — before any `Tk()` exists — was the one
# a caller had to reach into a submodule for, while `Scale`, which is useless
# without it, sat on the package. An adversarial pass named that as the reason
# the ordering would eventually be got wrong.
from .scale import (Awareness, Pin, Scale,                        # noqa: F401
                    dpi_awareness_level, make_process_dpi_aware)

from .settings import Settings                                    # noqa: F401

# ⛔ `app` IS DELIBERATELY NOT IMPORTED HERE, and that is a contract rather
# than an oversight: it is the only module in this package that imports
# tkinter, and `test_gui.py` plus any headless CI depend on
# `from tsubasa.gui import run` working with no display attached. Importing
# the window here would make the whole package need one.
# ⭐ `test_the_package_does_not_drag_tkinter_in` is what keeps that true.

__all__ = ["Awareness", "Fault", "NotStarted", "Pin", "Row", "Run", "Runner",
           "Scale", "Settings", "StillRunning", "argv_for", "counts",
           "dpi_awareness_level", "make_process_dpi_aware", "parse_line"]
