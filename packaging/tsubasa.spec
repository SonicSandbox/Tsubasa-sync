# -*- mode: python ; coding: utf-8 -*-
u"""tsubasa, frozen. RUNBOOK 4c · `STANDALONE-BUILD-SCOPE.md` §3–§5.

    pyinstaller --noconfirm --distpath <dir> --workpath <dir> packaging/tsubasa.spec

===========================================================================
🚨 ONE SPEC, TWO EXECUTABLES, ONE `COLLECT` — AND THAT IS THE WHOLE BUILD
===========================================================================

`gui/run.py::cli_argv()`: frozen, `sys.executable` is the BUNDLE, so `-m
tsubasa` would re-enter the GUI and open a second window. The frozen branch
therefore runs `tsubasa.exe` **from the directory the GUI is sitting in** —
so ⛔ **ship only the GUI and every single run fails at launch.**

⛔ AND TWO SEPARATE `pyinstaller` RUNS INTO ONE `--distpath` IS NOT THE SAME
THING. That is the version that silently overwrites one app's payload with
the other's: both COLLECT steps write `_internal/`, second one wins, and the
loser's analysis is gone. Two `Analysis` objects and ONE `COLLECT` is the
only arrangement where both binaries share a payload that contains both
their imports.

===========================================================================
⚠ `--onedir`, NEVER `--onefile`
===========================================================================

`10-deployment.md` §Freezing ruled it: onefile unpacks the whole payload to a
temp directory on every launch. It also multiplies
`STANDALONE-BUILD-SCOPE.md` trap 6 — Tcl intermittently failing to find one
of its own library files, about 1 run in 350.

===========================================================================
⛔ NO `--add-data` FOR TSUBASA'S OWN FILES
===========================================================================

`tsubasa/__pyinstaller/hook-tsubasa.py` ships INSIDE the package and is found
through `pyproject.toml`'s `pyinstaller40` entry point, so the alias table and
the decoration vocabulary are collected with no help from here.
`tests/test_packaging.py` reads that hook's syntax tree and fails if its
patterns stop matching the package's real data files — and it guards only the
hook. ⚠ A hand-written copy in this file would drift out from under that
check, silently, and a frozen build that lost the table still runs and exits
0 (settled by name 80.0% → 51.4%).
"""
import os

from PyInstaller.utils.hooks import collect_all

HERE = os.path.abspath(SPECPATH)                          # noqa: F821

# ⭐ COLLECTED, NOT DECLARED. `tkinterdnd2` carries a Tcl package that is
# loaded by PATH at runtime, not imported, so an ordinary hidden-import is
# not enough — `STANDALONE-BUILD-SCOPE.md` trap 4. It is OPTIONAL: `gui/app.py`
# imports it in a try/except and degrades to Browse with a stated reason, so
# its absence is a smaller window, never a failure.
try:
    _dnd_datas, _dnd_binaries, _dnd_hidden = collect_all("tkinterdnd2")
except Exception:                                         # noqa: BLE001
    _dnd_datas, _dnd_binaries, _dnd_hidden = [], [], []

# ⚠ guessit reads its own configuration and babelfish its language tables from
# data files, and neither is IMPORTED, so an ordinary dependency scan misses
# them. ⛔ This comment used to claim a frozen guessit without them *"raises on
# the first unusual release name rather than returning a worse answer"* — wrong
# twice: `naming/episode.py` catches `Exception` and returns None, so it would
# not raise; and measured over 904 real western release names, guessit is
# consulted on 44.14% and changes the union's answer on **0.00%**. Collected
# because it is cheap and correct, not because its absence would be loud.
_opt_datas, _opt_binaries, _opt_hidden = [], [], []
for _name in ("guessit", "babelfish", "rebulk"):
    try:
        d, b, h = collect_all(_name)
    except Exception:                                     # noqa: BLE001
        continue
    _opt_datas += d
    _opt_binaries += b
    _opt_hidden += h

HIDDEN = ["anitopy", "send2trash"] + _opt_hidden

#: ⚠ Pruned per `10-deployment.md` §Freezing. ⛔ NOTHING UNDER `numpy` IS
#: EXCLUDED: numpy is the one hard dependency and excluding a submodule of it
#: trades tens of megabytes for a crash on some path nobody exercised.
EXCLUDE = [
    "scipy", "matplotlib", "pandas", "PIL", "IPython", "notebook",
    "PyQt5", "PyQt6", "PySide2", "PySide6",
    "pytest", "_pytest", "pluggy", "sphinx", "docutils",
]

cli = Analysis(                                           # noqa: F821
    [os.path.join(HERE, "entry_cli.py")],
    pathex=[],
    binaries=_opt_binaries,
    datas=_opt_datas,
    hiddenimports=HIDDEN,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDE + ["tkinter", "tkinterdnd2"],
    noarchive=False,
)

gui = Analysis(                                           # noqa: F821
    [os.path.join(HERE, "entry_gui.py")],
    pathex=[],
    binaries=_opt_binaries + _dnd_binaries,
    datas=_opt_datas + _dnd_datas,
    hiddenimports=HIDDEN + _dnd_hidden,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDE,
    noarchive=False,
)

# ===========================================================================
# 🚨 THERE IS NO `MERGE` HERE, AND THAT IS A MEASURED DECISION
# ===========================================================================
#
# This spec had one, credited with keeping the zip at 29 MB instead of ~50.
# ⛔ An adversarial pass rebuilt it with the call removed and nothing else
# changed: **30,369,361 bytes vs 30,368,860, 1262 files either way.** The
# dedup belongs to the single `COLLECT` below, which keys on `dest_name`.
#
# `MERGE` processes only `analysis.binaries` and `analysis.datas`;
# `analysis.pure` is never touched, and the `DEPENDENCY` entries it creates
# land in `analysis.dependencies`, which this spec never passed to either
# `EXE` — so they were discarded and the call did nothing at all.
#
# ⛔ AND WIRING IT UP PROPERLY IS WORSE. Its own docstring: every executable
# then *"gains onefile semantics, because it needs to extract its referenced
# dependencies from other executables"* — the unpack-on-every-launch behaviour
# `10-deployment.md` ruled against.
#
# ⚠ What it was credited with removing is therefore still here: both PYZ
# archives carry the same ~572 shared modules, about 3.6 MB on disk, which the
# zip's compression largely absorbs. That is the price of two executables in
# one folder, and one folder is what trap 1 requires.

cli_pyz = PYZ(cli.pure, cli.zipped_data)                  # noqa: F821
gui_pyz = PYZ(gui.pure, gui.zipped_data)                  # noqa: F821

cli_exe = EXE(                                            # noqa: F821
    cli_pyz,
    cli.scripts,
    [],
    exclude_binaries=True,
    name="tsubasa",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    # ⛔ TRUE, AND IT IS NOT A DETAIL. This is the command line; a console app
    # with no console has nowhere to print, and `--version` — the one thing a
    # person is asked to run when they report a bug — would produce nothing.
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    codesign_identity=None,
    entitlements_file=None,
)

gui_exe = EXE(                                            # noqa: F821
    gui_pyz,
    gui.scripts,
    [],
    exclude_binaries=True,
    name="tsubasa-gui",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    # ⛔ FALSE: `pyproject.toml` uses `gui_scripts` for the same reason one
    # layer down — a console entry point attaches a console window to the
    # process for its whole life, which is the one packaging detail every user
    # of the desktop app can see.
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    codesign_identity=None,
    entitlements_file=None,
)

# ⭐ ONE COLLECT, BOTH EXECUTABLES. This is trap 1's fix, expressed as a
# build: `tsubasa.exe` and `tsubasa-gui.exe` land in the same folder, which is
# where the frozen GUI looks for the CLI.
coll = COLLECT(                                           # noqa: F821
    cli_exe,
    cli.binaries,
    cli.datas,
    gui_exe,
    gui.binaries,
    gui.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="tsubasa",
)
