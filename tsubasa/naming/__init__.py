# -*- coding: utf-8 -*-
"""
Naming: the librarian half of the tool, and the genuine invention.

    "tsubasa is a librarian and a referee. The aligner is the cheap part."

RUNBOOK Track A. Two questions that do NOT substitute for each other
(spec/09-corpus-strategy.md):

    Axis 1  What episode is this?      one filename   -> parsers
    Axis 2  Are these the same show?   TWO names      -> the alias table

anitopy will tell you `片田舎のおっさん S02E02` is episode 2. It will never tell
you that is the same show as `[SubsPlease] Katainaka no Ossan - 02`.
"""
from .normalize import Normalized, normalize, overlap, same_key, script_of

# ⚠ TRAP: this line rebinds `tsubasa.naming.normalize` from the MODULE to the
# FUNCTION. `import tsubasa.naming.normalize as x` therefore gives the function,
# and any attribute access on it fails naming the wrong cause. To reach the
# module, use sys.modules["tsubasa.naming.normalize"].
# Kept deliberately: `normalize()` is the right name for the call and
# `normalize.py` is the right name for the file. The collision is documented
# rather than worked around with a worse name for one of them.

__all__ = ["Normalized", "normalize", "overlap", "same_key", "script_of"]
