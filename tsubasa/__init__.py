# -*- coding: utf-8 -*-
"""
tsubasa -- pair subtitle files to their videos and retime them to match, by cue
timing rather than text, so it works in any language.

Library-first: the importable API is the product and the CLI is a thin wrapper
over it (spec/05-interface.md).

    from tsubasa import scan, sync, align, Result

    cands   = scan(videos="/media/anime/s2", subs="/data/subs")
    results = sync(cands)                       # measures. Writes NOTHING.
    results = sync(cands, write=True)           # the only call that writes.
    fit     = align(reference_starts, subtitle_starts, duration)

For an application building on it (spec/05-interface.md §For code built on
tsubasa):

    check = self_check()                        # is this install whole?
    todo  = cands.unpaired(lang="ja")           # videos with no Japanese sub
    r     = sync_to_reference(sub, other_sub)   # a subtitle against a subtitle
    data  = render(r).data                      # retimed bytes; caller writes
    side  = parse_subtitle_name("Show.ja[cc].srt")   # stem, lang, tag, flags

⚠ THESE NAMES ARE A COMPATIBILITY PROMISE (spec/RUNBOOK.md step 3b). hato pins
four shapes through them -- the parser, discovery, the sidecar reader and
`align()` -- so they are added to, never renamed.
"""

#: ⭐ THE SINGLE SOURCE OF TRUTH FOR THE VERSION. `pyproject.toml` reads it
#: from here with `dynamic = ["version"]`, so the two can never disagree —
#: and `tests/test_packaging.py` refuses a `0.0.0` placeholder, because a
#: published artifact reporting that cannot be told apart from any other
#: build of it (`10-deployment.md`: *the live artifact's version equals the
#: local one*).
__version__ = "0.1.2"

# ⚠ The submodule imports are here rather than at the bottom, and that is safe
# because no submodule imports a name FROM this package. Every one of them
# reaches its siblings with `from . import x`, which resolves against
# sys.modules while this file is still executing.
#
# ===========================================================================
# 🚨 `tsubasa.align` IS THE FUNCTION, NOT THE SUBPACKAGE. DELIBERATE.
# ===========================================================================
#
# `05-interface.md` promises `from tsubasa import scan, sync, align, Result`
# and `fit = align(reference_starts, subtitle_starts, duration)`, so the name
# has to be callable -- hato pins it. The line below therefore REBINDS the
# `align` attribute on this package from the subpackage to the function.
#
# ⭐ It is `LEDGER-HOT.md` trap 8 one level up, and it is recorded rather than
# avoided. What still works, and what does not:
#
#     from tsubasa import align            ✅ the FUNCTION (the spec's promise)
#     from tsubasa.align import mapper_for ✅ the module -- `from X import Y`
#                                             resolves X through sys.modules,
#                                             never through getattr on parent
#     from . import align                  ✅ inside the package, same reason
#     import tsubasa.align as X            ⛔ the FUNCTION -- getattr on parent
#     from tsubasa import align as AL      ⛔ the FUNCTION
#
# ⛔ THE LAST TWO FAIL SILENTLY IN A MUTATION RUN. A function accepts arbitrary
# attributes, so `setattr(X, "mapper_for", mutant)` succeeds and mutates
# nothing -- the mutants go from KILLED to SURVIVED with no fault to explain
# it. `_work/probe_adj25_applymutants.py` had exactly that shape and was fixed
# to read `sys.modules["tsubasa.align"]` when this landed.
from .align import align                                      # noqa: E402,F401
from .api import Candidacy, Result, Scan, scan                 # noqa: E402,F401
from .container.ffmpeg import set_location as set_ffmpeg       # noqa: E402,F401
from .pipeline import (Rendered, SyncReport, render,           # noqa: E402,F401
                       sync, sync_to_reference)
from .selfcheck import SelfCheck, self_check                   # noqa: E402,F401
# ⭐ The sidecar reader was already one of the four frozen shapes hato pins; it
# was reachable only as `tsubasa.sidecar.parse`, which reads like an internal.
from .sidecar import Sidecar                                   # noqa: E402,F401
from .sidecar import parse as parse_subtitle_name              # noqa: E402,F401

__all__ = ["align", "scan", "sync", "set_ffmpeg", "Result", "Scan",
           "Candidacy", "SyncReport", "__version__",
           # added 2026-09-16 for code built on tsubasa -- never renamed
           "self_check", "SelfCheck", "sync_to_reference", "render",
           "Rendered", "parse_subtitle_name", "Sidecar"]
