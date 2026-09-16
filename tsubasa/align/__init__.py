# -*- coding: utf-8 -*-
"""
Alignment: how far off is this subtitle, and does the answer hold?

⭐ ONE FUNCTION IS THE PRODUCT SURFACE.

    from tsubasa.align import align, unique_starts

    fit = align(unique_starts(ref_starts), unique_starts(sub_starts), duration)
    fit.segments          # [(split_time or None, offset), ...]
    fit.excess            # match rate as a multiple of chance
    fit.holds_throughout  # does it hold across the WHOLE runtime?

`align()` is one of the four surfaces `hato` pins (spec/RUNBOOK.md step 3b), so
its shape is a compatibility promise, not an implementation detail.

⚠ It takes CUE-START MOMENTS, never files and never a video. That is what lets
the whole alignment suite run from ~400 KB of extracted reference tracks with no
media present -- and it is why the same function serves a text track, a bitmap
track's ON-times and a speech mask without knowing which it was given.
"""
from .fit import (BIN, K_BUCKET, K_GLOBAL, Fit, candidates, differences, fit,
                  is_removed, mapper_for, removed_spans, subtitle_boundaries)
from .objective import (BUCKET, CLUSTER_TOL, MAX_BREAK, MIN_ALIGNABLE_CUES,
                        MIN_BREAK, MIN_CUES,
                        MIN_EXCESS, MIN_LOCAL_MARGIN, MIN_SPLIT_GAIN, MR_TOL,
                        WINDOW, bucket_noise_floor, chance_rate, hits,
                        match_rate, unique_starts)

#: ⭐ The name the rest of the project calls it by.
align = fit

# ⚠ TRAP, the same one `tsubasa.naming` documents: the import above rebinds
# `tsubasa.align.fit` from the MODULE to the FUNCTION. So
# `import tsubasa.align.fit as F` hands you the function, and every attribute
# access on it then fails naming the wrong cause. To reach the module, use
# `sys.modules["tsubasa.align.fit"]`. Kept deliberately -- `fit()` is the right
# name for the call and `fit.py` is the right name for the file.

__all__ = [
    "align", "fit", "Fit", "candidates", "differences",
    "unique_starts", "chance_rate", "match_rate", "hits", "bucket_noise_floor",
    "MR_TOL", "CLUSTER_TOL", "MIN_BREAK", "MAX_BREAK", "MIN_SPLIT_GAIN",
    "MIN_LOCAL_MARGIN", "MIN_EXCESS", "MIN_CUES", "MIN_ALIGNABLE_CUES",
    "BUCKET", "WINDOW",
    "BIN", "K_GLOBAL", "K_BUCKET",
    # ⭐ 3a's write path works from `segments` alone -- a `Verdict` carries
    # them, so the writer never needs a whole `Fit`.
    "subtitle_boundaries", "mapper_for", "removed_spans", "is_removed",
]
