# -*- coding: utf-8 -*-
u"""
    python -m tsubasa.gui

RUNBOOK step 3d. ⛔ A launcher and nothing else, the same shape as
`tsubasa/__main__.py`: `app.main` owns the window, so `python -m tsubasa.gui`
and the entry point installed at 4a cannot behave differently.

⚠ THE IMPORT ORDER IN `app.py` IS LOAD-BEARING and this file must not
reorder it — `make_root()` makes the process DPI-aware *before* it creates a
Tk root, because Tk reads the screen metrics once and a call made afterwards
still succeeds while every number in the process stays wrong.
"""
import sys

from .app import main

if __name__ == "__main__":
    sys.exit(main())
