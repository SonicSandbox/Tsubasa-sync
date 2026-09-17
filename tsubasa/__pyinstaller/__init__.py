# -*- coding: utf-8 -*-
u"""
PyInstaller support, found automatically. ⛔ Nothing in the library imports this.

===========================================================================
🚨 WITHOUT IT, A FROZEN APPLICATION SHIPS TSUBASA WITH NO DATA AND NO ERROR
===========================================================================

PyInstaller follows imports. It does not collect a package's DATA files unless
a hook says to, and `naming/alias.py` and `naming/decoration.py` find their
tables beside their own `__file__` and **fail open** when they are absent —
deliberately, `00-INDEX.md` Rule 1: an accelerator, never a dependency.

⛔ MEASURED 2026-09-16, NOT REASONED. A PyInstaller 6.22 build of a plain
`import tsubasa`, installed from the real wheel, launched and exited 0 with
**0 alias entries and 0 vocabulary tokens**. A cross-script pair that settles
by name unfrozen — `Yomi no Tsugai S01E18` against `黄泉のツガイ.S01E18` — came
back `unsure / 0.000` frozen. Nothing raised and nothing logged.

⭐ `pyproject.toml` registers `get_hook_dirs` under the `pyinstaller40` entry
point, which is how PyInstaller finds hooks that ship INSIDE an installed
package. The application freezing us changes nothing — no spec edit, no
`--collect-data`, no `hookspath` — and the same build carried all 221,258
entries and settled that pair `same / 1.000`.

⚠ PYINSTALLER ONLY. Nuitka, cx_Freeze and Briefcase do not read this entry
point. `tsubasa.self_check()` is how an application built any other way finds
out, and it is worth calling under PyInstaller too.
"""
import os


def get_hook_dirs():
    u"""Where `hook-tsubasa.py` lives. -> [str]"""
    return [os.path.dirname(os.path.abspath(__file__))]
