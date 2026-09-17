# -*- coding: utf-8 -*-
u"""The frozen CLI's entry script. RUNBOOK 4c.

⚠ PyInstaller freezes SCRIPTS, not entry points, so `pyproject.toml`'s
`tsubasa = "tsubasa.cli:main"` cannot be handed to it directly. This file is
that console script, written out — and it must stay a one-liner over
`cli.main`, because `05-interface.md`'s rule is that the CLI decides nothing
and a second entry point that grew its own behaviour would be a third answer
to every question.
"""
import sys

from tsubasa.cli import main

if __name__ == "__main__":
    sys.exit(main())
