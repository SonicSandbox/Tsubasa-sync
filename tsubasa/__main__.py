# -*- coding: utf-8 -*-
u"""
    python -m tsubasa <folder>

RUNBOOK step 3c. ⛔ A launcher and nothing else: `cli.main` owns the argument
handling, the report and the exit code, so that `python -m tsubasa` and the
console script installed at 4a cannot behave differently.
"""
import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
