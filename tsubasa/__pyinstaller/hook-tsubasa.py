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

DATA_PATTERNS = ["data/*.tsv.gz", "data/*.json"]

datas = collect_data_files("tsubasa", includes=DATA_PATTERNS)
