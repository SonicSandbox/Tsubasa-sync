# -*- coding: utf-8 -*-
u"""Run by PyInstaller while it freezes an application that imports tsubasa.

⛔ NEVER IMPORTED BY THE LIBRARY. It imports PyInstaller, which is a dependency
of nothing here, and its filename is not a valid module name on purpose.

⚠ THE PATTERNS MIRROR `[tool.setuptools.package-data]` in `pyproject.toml`.
A new data-file TYPE has to be added to both, and `tests/test_packaging.py`
reads this file's syntax tree and fails if `tsubasa/data/` holds a file that
neither pattern covers — without importing PyInstaller to do it.
"""
from PyInstaller.utils.hooks import collect_data_files

#: ⚠ THREE FILES MUST AGREE OR SOMETHING SHIPS WITHOUT ITS DATA: this list,
#: `pyproject.toml`'s `[tool.setuptools.package-data]`, and the real contents
#: of `tsubasa/data/`. `tests/test_packaging.py` reads this list out of the
#: SYNTAX TREE and fails when they drift — which is how the icons were caught
#: the moment they were added, with the fix named in the failure message.
DATA_PATTERNS = ["data/*.tsv.gz", "data/*.json", "data/*.png", "data/*.ico"]

#: ⭐ BELT AS WELL AS BRACES, added at RUNBOOK 4g. numpy's import was deferred
#: into the two `align` modules that use it, so nothing imports it at module
#: level any more.
#:
#: ⚠ **PyInstaller still finds it** — verified by an adversarial pass that
#: froze the real package and counted **139 numpy modules and 15 numpy
#: binaries** in the graph, because `modulegraph` recurses into nested code
#: objects and an `import` inside a method is an ordinary `IMPORT_NAME` to the
#: scanner. So this line changes nothing today.
#:
#: ⛔ It is here because of what a MISS would cost: a frozen app with no numpy
#: imports cleanly, passes `self_check()` — and raises on the first alignment.
#: That is this project's worst failure shape, and one line is cheaper than
#: trusting a static analyser to keep behaving.
hiddenimports = ["numpy"]

datas = collect_data_files("tsubasa", includes=DATA_PATTERNS)
