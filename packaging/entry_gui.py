# -*- coding: utf-8 -*-
u"""The frozen GUI's entry script. RUNBOOK 4c.

⚠ `console=False` IN THE SPEC MEANS THIS PROCESS HAS NO VALID STANDARD
HANDLES. `STANDALONE-BUILD-SCOPE.md` trap 3: on Windows a windowed app's
stdout and stderr are invalid, so a stray `print()` here can raise. ⛔ Nothing
in this file writes to a stream, and nothing added to it should — the GUI
reads its CHILD's stdout, which is a pipe it opened itself and is fine.
"""
import sys

from tsubasa.gui.app import main

if __name__ == "__main__":
    sys.exit(main())
