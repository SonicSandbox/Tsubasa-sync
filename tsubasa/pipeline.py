# -*- coding: utf-8 -*-
u"""
`sync()` -- the run. RUNBOOK step 3b. Authority: `05-interface.md` §*The library
API*, `09-corpus-strategy.md` §Stage 3-4, `03-permissions.md`.

===========================================================================
⭐ `api.py` IS WHAT IS HERE. THIS IS WHAT HAPPENS TO IT.
===========================================================================

`scan()` walks names and opens nothing. `sync()` opens the containers, reads
the subtitles, aligns, probes clusters, decides, and -- only when told --
writes. The split is not cosmetic: `scan()` is the half a caller is invited to
run over a whole library, and it has to stay free.

---------------------------------------------------------------------------
🚨 THE TUPLE PATH GOES THROUGH `explicit_pairs()`. RULED, BINDING.
---------------------------------------------------------------------------

`05-interface.md` promises `sync([(video, subtitle), ...], write=True)` and the
signature stays. ⛔ **The tuples are converted through
`explicit.explicit_pairs()` and every decision is made from the resulting
`PairPlan`.** Sonic's words: *"a tuple path that silently skips every refusal
is the one shape the whole project exists to prevent."*

A11 built five refusals -- the missing path, the swapped arguments, the same
subtitle claimed twice, the directory given where a file goes, the 8 GB file
that is not a subtitle. A `for video, subtitle in pairs:` loop here walks past
every one of them, and `ExplicitPair.__iter__` raises specifically so that loop
cannot be written by accident.

---------------------------------------------------------------------------
⭐ ONE `Result` PER (VIDEO x LANGUAGE) SLOT -- not per candidate
---------------------------------------------------------------------------

`05-interface.md`'s ruled output is one line per video, with the subtitle that
won named on it. That is the same unit dedupe works in: *keep one subtitle per
(video x language)*. The candidates that lost are `Result.superseded`; the
candidates that were never plausible are `Result.notes`.

⚠ A video with NOTHING to try is not in `results` at all. It is not a pair, so
it has no outcome -- `03-permissions.md` is explicit that there is no fourth --
and inventing one would be a lie. It is `SyncReport.unpaired`, and
`summary()` leads with it so it cannot be silent.

---------------------------------------------------------------------------
⛔ `--force` BELONGS TO THE EXPLICIT PATH AND NOWHERE ELSE
---------------------------------------------------------------------------

On a `Scan`, forcing would mean *write the best of several REFUSED candidates*
-- which is precisely what `dedupe.py`'s rule 1 is a GATE rather than a sort
key to prevent. So `sync(scan_result, force=True)` **refuses loudly**. Silently
ignoring it would leave the user believing they had overridden something.
"""
import bisect
import os

from . import api as _api
from . import apply as _apply
from . import arbitrate as _arbitrate
from . import dedupe as _dedupe
from . import duration as _duration
from . import explicit as _explicit
from . import formats as _formats
from . import movies as _movies
from . import paths as _paths
from . import results as _results
from . import sidecar as _sidecar
from . import verdict as _verdict
from .align import (BUCKET, MIN_ALIGNABLE_CUES, align, mapper_for,
                    removed_spans, unique_starts)
from .apply import apply_plan
from .naming import series as _series
from .verdict import BITMAP_TRACK, CONFIDENT, ERROR, REFUSED, TEXT_TRACK

#: Codec fragments that mean a track carries BITMAPS rather than text. Matroska
#: says `S_HDMV/PGS` and `S_VOBSUB`; ffmpeg says `hdmv_pgs_subtitle` and
#: `dvd_subtitle`, so both vocabularies are matched.
#:
#: ⚠ THE LABEL IS ALL THIS DECIDES. `verdict.py`: a bitmap track's ON-times are
#: cue moments like any other -- the container block timestamps know nothing
#: about the codec -- so the band is identical either way. Getting it wrong
#: costs a wrong word in a report, never a wrong file.
_BITMAP_CODECS = ("pgs", "vobsub", "dvd_sub", "dvdsub", "hdmv")


class Reference(object):
    u"""What a video's timing was read from.

    ⭐ `00-INDEX.md` Rule 1: *the embedded subtitle track is an ACCELERATOR,
    never a dependency.* This is the accelerator; when it is absent the answer
    is the speech mask (RUNBOOK B6), and until B6 fits its band the honest
    answer is a refusal that names what would change it.
    """

    __slots__ = ("starts", "kind", "description", "duration", "track")

    def __init__(self, starts, kind, description, duration, track=None):
        self.starts = starts
        self.kind = kind                # verdict.TEXT_TRACK / BITMAP_TRACK
        self.description = description
        self.duration = duration
        self.track = track

    def __repr__(self):
        return "Reference(%s, %d cues, %s)" % (
            self.kind, len(self.starts), self.description)


class SyncReport(object):
    u"""Everything one run came to. A SEQUENCE of `Result`, plus the rest.

    ⚠ ITERABLE, unlike `Scan`, `PairPlan` and `MoviePairing` -- and the reason
    is written here rather than assumed. `05-interface.md` types this
    `list[Result]` and iterating it yields **every** result including every
    refusal, so iteration loses no decision. What it does not carry is
    `unpaired`, which is a COUNT of videos that never became a pair, and
    `summary()` leads with that so it cannot go unsaid.
    """

    __slots__ = ("results", "unpaired", "skipped", "settled", "notes")

    def __init__(self, results, unpaired=(), skipped=None, notes=(),
                 settled=()):
        self.results = list(results)
        #: [(path, reason)] -- videos no subtitle was offered for.
        self.unpaired = list(unpaired)
        #: {path: reason} -- files discovery deliberately left out.
        self.skipped = dict(skipped or {})
        #: ⭐ [(path, reason)] -- videos the results DB recognised as ALREADY
        #: SYNCED, so nothing was opened, measured or moved for them
        #: (`06-edge-cases.md` §7, RUNBOOK 3a-bis).
        #:
        #: ⚠ NOT a `Result`, and for the same reason `unpaired` is not: no pair
        #: was measured this run, so there is no outcome to report and
        #: `03-permissions.md` says there is no fourth one to invent. It is a
        #: separate surface that `summary()` names out loud, because a video
        #: this tool decided not to look at must never be a silence.
        self.settled = list(settled)
        self.notes = list(notes)

    # -- the sequence half -------------------------------------------------

    def __len__(self):
        return len(self.results)

    def __getitem__(self, i):
        return self.results[i]

    def __iter__(self):
        return iter(self.results)

    # -- counts ------------------------------------------------------------

    @property
    def confident(self):
        return [r for r in self.results if r.outcome == CONFIDENT]

    @property
    def refused(self):
        return [r for r in self.results if r.outcome == REFUSED]

    @property
    def errored(self):
        return [r for r in self.results if r.outcome == ERROR]

    @property
    def written(self):
        u"""🚨 Results whose file was ACTUALLY written -- never *would write*.
        In a dry run this is empty and `confident` is not."""
        return [r for r in self.results if r.output_path]

    @property
    def forced(self):
        return [r for r in self.results if r.forced]

    @property
    def failed(self):
        u"""🚨 Results whose write was ATTEMPTED and did not land.

        ⛔ This surface did not exist, and its absence made a `write=True` run
        whose every write failed **byte-identical in its report to a dry
        run** — same `summary()`, same `confident`, same empty `written`. The
        only trace was a string buried in `Result.notes`. Found by an
        adversarial pass.
        """
        return [r for r in self.results if r.write_failed]

    def summary(self):
        u"""One line. ⚠ Refusals, errors, failed and forced writes lead it.

        `LEDGER.md` §Interface: a GUI painted a run containing refusals green
        because *"11 confident, 1 refused"* contains the word `confident`. So
        when anything went wrong, no positive word precedes it.
        """
        head = []
        if self.failed:
            head.append(u"%d NOT WRITTEN" % len(self.failed))
        if self.forced:
            head.append(u"%d FORCED" % len(self.forced))
        if self.errored:
            head.append(u"%d ERROR" % len(self.errored))
        if self.refused:
            head.append(u"%d refused" % len(self.refused))
        if self.unpaired:
            head.append(u"%d video%s with no subtitle"
                        % (len(self.unpaired),
                           u"" if len(self.unpaired) == 1 else u"s"))
        if self.skipped:
            head.append(u"%d skipped" % len(self.skipped))
        # ⚠ *"would sync"* IS ONLY HONEST ON A DRY RUN. It used to be the
        # fallback whenever `written` was empty, so a real run that wrote
        # nothing because every write failed described itself as a plan.
        if self.written:
            tail = [u"%d synced" % len(self.written)]
        elif self.failed:
            tail = [u"0 synced"]
        elif self.settled and not self.results:
            # ⭐ NOTHING WAS MEASURED, SO THERE IS NO PLAN TO REPORT. *"0 would
            # sync"* over a folder the results DB recognised whole reads as a
            # dry run that decided against everything — the tool announcing a
            # decision it never made. `already in sync` below is the whole
            # story. ⚠ Only when there are NO results at all: a run that
            # settled some videos and measured others still owes both counts.
            tail = []
        else:
            tail = [u"%d would sync" % len(self.confident)]
        # ⭐ A SKIPPED VIDEO IS SAID OUT LOUD. A run that reports `0 synced`
        # over a folder of 24 finished episodes is indistinguishable from one
        # that did nothing because it was broken, and the user would go
        # looking. It sits in the TAIL because *already in sync* is not a
        # problem -- the head is reserved for things that are.
        if self.settled:
            tail.append(u"%d already in sync" % len(self.settled))
        return u" · ".join(head + tail)

    def __repr__(self):
        return "SyncReport(%s)" % self.summary()


# ---------------------------------------------------------------------------
# the front door
# ---------------------------------------------------------------------------

def sync(source, write=False, rename=True, dedupe=True, vad=False,
         force=False, keep_all=False, out_dir=None, trash_root=None,
         sender=None, reader=None, results=None, suffix=None):
    u"""Measure, decide, and -- only when told -- write. -> `SyncReport`

        sync(scan(...))                       measures. ⛔ Writes NOTHING.
        sync(scan(...), write=True)           the only call that writes.
        sync([(video, subtitle), ...])        explicit pairs, same guarantees.

    `source`
        a `Scan` from `scan()`, an iterable of `(video, subtitle)` pairs, or an
        `explicit.PairPlan`. 🚨 The tuples are converted through
        `explicit.explicit_pairs()` -- see the module note; that is ruled and
        binding, not a convention.
    `write`
        ⛔ **False by default.** `doctrine/robustness`: a destructive tool is
        dry-run by default. Everything is measured and reported either way; the
        only difference is whether bytes move.
    `rename`
        the output takes the video's basename, which is what makes a player
        auto-load it. `rename=False` writes back over the subtitle's own name.
    `dedupe`
        the candidates that lost the slot go to the trash. `dedupe=False`
        leaves every one of them exactly where it is.
    `vad`
        ⛔ RUNBOOK B6. The band for a speech mask has not been FITTED, so this
        cannot silently do anything -- see `_vad_note`.
    `force`
        ⛔ Explicit pairs only, and it overrides a REFUSAL, never an ERROR.
    `out_dir`
        `05-interface.md`: `--out` **mirrors, never flattens**. Only the caller
        knows the library root, so this takes the directory it is given.
    `reader`
        the container reader, injected. ⛔ A SEAM, the same shape as
        `dedupe.trash(sender=...)` and `movies.pair_movies(duration_of=...)`:
        it is what lets the suite drive a run without a video, while the real
        reader stays the default so it is never *code that never runs here*.
    `results`
        ⭐ the results DB (RUNBOOK 3a-bis), injected on the same seam. It is
        what makes *"re-run with nothing changed"* cost a hash per file instead
        of a container read and an alignment per pair -- `06-edge-cases.md` §7.
        ⛔ Pass `results=False` to consult and record nothing; that is not the
        same as `None`, which means *use the real per-user store*.
    `suffix`
        ⭐ 0.1.2. Write the retimed subtitle BESIDE ITS ORIGINAL, under the
        original's name with this inserted before the language tag —
        `suffix="_rt"` turns `Show - 01.ja.srt` into `Show - 01_rt.ja.srt`.
        ⛔ **Nothing is replaced, renamed or trashed**: every original stays
        exactly where it was, so this implies `dedupe=False`. On a scan, a
        subtitle that is already such a copy is never retimed again. It
        contradicts `rename=False` (in place), `out_dir` (elsewhere) and
        `keep_all` (every candidate), and raises with any of them.
    """
    reader = reader or _default_reader
    trash_root = trash_root or _default_trash_root()
    # ⚠ `False` IS DISTINCT FROM `None` HERE, deliberately. `None` is *"you
    # decide"* and gets the real store; `False` is a caller saying *do not read
    # or write any history*, which a bare falsy test would silently turn into
    # the opposite. `05-interface.md`'s `--no-cache` is the flag this serves.
    if results is None:
        results = _results.Results()
    elif results is False:
        results = None
    notes = []
    if vad:
        notes.append(_vad_note())

    # ⛔ `out_dir` AND `rename=False` CONTRADICT EACH OTHER, and the result was
    # the exact file `_out_dir_for`'s own docstring forbids: the subtitle's
    # release-group name, in a third folder that is neither beside the video
    # nor where the user left it -- and the loser trashed anyway. `--rename`
    # off means *do not touch the name*, which is an in-place retime; `--out`
    # means *put the output somewhere else*. Found by an adversarial pass.
    if out_dir and rename is False:
        raise ValueError(
            "out_dir and rename=False contradict each other. rename=False "
            "means an in-place retime -- the file keeps its own name where "
            "the user left it -- and out_dir means the output goes somewhere "
            "else. Choose one (05-interface.md).")

    if suffix is not None:
        suffix = _sidecar.check_suffix(suffix)
        for clash, why in ((rename is False, "rename=False retimes the "
                            "original IN PLACE"),
                           (bool(out_dir), "out_dir writes the output "
                            "somewhere else"),
                           (bool(keep_all), "keep_all writes every "
                            "candidate under a distinguishing tag")):
            if clash:
                raise ValueError(
                    "suffix writes a copy beside the original and changes "
                    "nothing else, but %s. Choose one." % why)
        # ⭐ The copy lives in the ORIGINAL's folder, which is exactly where
        # `rename=False` already puts a write — so the directory and every
        # ownership check are reused rather than re-derived. The NAME is what
        # differs, and `_decide_slot` applies it. `dedupe=False` because
        # superseding an original is the one thing this mode promises not to do.
        rename, dedupe = False, False

    if isinstance(source, _api.Scan):
        if force:
            # ⛔ REFUSED LOUDLY, never ignored. On the discovery path forcing
            # means *write the best of several REFUSED candidates*, which is
            # exactly what `dedupe.py`'s rule 1 is a gate rather than a sort
            # key to prevent. A caller who passed `force=True` and got a
            # normal-looking run would believe they had overridden something.
            raise ValueError(
                "force=True is for explicit pairs only. On a scan it would "
                "mean writing the best of several refused candidates, which "
                "is the one thing dedupe's rule 1 exists as a GATE to "
                "prevent (05-interface.md). Pair the file explicitly: "
                "sync([(video, subtitle)], write=True, force=True).")
        return _sync_scan(source, write=write, rename=rename, dedupe=dedupe,
                          keep_all=keep_all, out_dir=out_dir,
                          trash_root=trash_root, sender=sender, reader=reader,
                          vad=vad, notes=notes, results=results,
                          suffix=suffix)

    plan = source if isinstance(source, _explicit.PairPlan) else \
        _explicit.explicit_pairs(pair_args=source)
    return _sync_plan(plan, write=write, rename=rename, dedupe=dedupe,
                      keep_all=keep_all, out_dir=out_dir,
                      trash_root=trash_root, sender=sender, reader=reader,
                      force=force, vad=vad, notes=notes, results=results,
                      suffix=suffix)


# ---------------------------------------------------------------------------
# ⭐ a subtitle against ANOTHER SUBTITLE, and the bytes of a result
# ---------------------------------------------------------------------------

def sync_to_reference(subtitle, reference):
    u"""Retime `subtitle` against another subtitle FILE. -> `Result`

        r = sync_to_reference("Show - 01.ja.srt", "Show - 01.en.srt")
        if r.outcome == "CONFIDENT":
            data = render(r).data          # the retimed file, as bytes

    ⛔ WRITES NOTHING, and there is no switch that makes it. `render()` gives
    the retimed bytes and the caller writes them — under its own name, beside
    whatever it likes, with its own rules about what may be replaced. A path a
    caller names is exactly where `os.replace` would destroy somebody's file,
    and the slot machinery that protects `sync(write=True)` is built around a
    video this call does not have.

    ⭐ NOTHING HERE IS A SECOND ALIGNER. The reference file becomes a
    `Reference` — cue starts, a kind, a description — and from there it is the
    same `measure()`, the same `judge()` and the same verdict bands as a
    video's embedded track, so this can never come to disagree with `sync()`
    about what a good alignment is.

    ⚠ THE KIND IS `text track`, AND THAT IS A CLAIM ABOUT THE EVIDENCE. The
    bands were fitted on text cue starts against text cue starts; an external
    text subtitle is that population, and a new kind would have needed bands
    nobody has measured — `verdict()` raises on one it does not know.
    `Result.reference` names the file, so the source is never hidden.

    🚨 WHAT THIS CANNOT TELL YOU: whether `reference` is itself in time with
    the video. The result is *these two agree*, never *this now matches the
    picture* — a reference that is 2 s late produces a subtitle 2 s late with
    a perfect match rate.

    ===================================================================
    🚨 A PARTIAL REFERENCE IS REFUSED — RULED 2026-09-16, ON MEASUREMENT
    ===================================================================

    An embedded track spans its whole video, so the verdict was fitted on
    references that cover everything. A reference FILE need not, and the
    whole-runtime walk cannot tell *a short episode* from *a long subtitle
    whose reference stops early* — both simply give it few buckets. Measured
    against a 266-cue subtitle:

        reference = its first 4 minutes, subtitle CUT at 15:00
            -> CONFIDENT, `locked`, runtime_check `held`, ONE segment

    **The cut was invisible and every word said trust it.** `render()` would
    have written the last eight minutes ten seconds wrong. ⛔ And the earlier
    advice in this docstring — *read `runtime_check`* — was wrong too: it
    said `held`, because `held` needs only two usable buckets.

    ⭐ SO COVERAGE IS MEASURED DIRECTLY, WITH THE VERDICT'S OWN UNIT. Every
    subtitle line is placed at its corrected time, and a line with no
    reference line within one `BUCKET` (120 s — the runtime walk's resolution)
    was never checked by anything. Then:

    * **a run of unchecked lines spanning at least one bucket → REFUSED.** It
      is a stretch the walk would have judged as a bucket had the reference
      covered it, so the whole-runtime claim cannot be made — the same rule
      `verdict()` applies when an answer does not hold throughout.
      `render(result, force=True)` still writes it, with the offset measured
      where the two overlap.
    * **isolated lines, spanning less than a bucket → CONFIDENT, capped at
      `fair`**, with a note naming them. A preview line the reference lacks is
      not a stretch anything could have measured — the same narrowing
      `verdict()` applies when its walk saw nothing.

    ⭐ Checked against the cases that must NOT change, and none did: a full
    reference, shifted or cut; a reference lacking one trailing line; a
    realistic other-language pair with jittered timing and a fifth of each
    side's lines unique to it. All `locked`, zero unchecked lines.

    ⚠ `sync()` is unchanged. Its references are tracks that span their video,
    and its verdict sits in bands measured on that population.

    ⚠ The runtime gate has nothing to compare against, because a subtitle
    file has no runtime of its own, so `duration_verdict` answers UNKNOWN and
    the aligner spreads its chance baseline over the cues' own span. Both are
    the documented behaviour for an unprobed video, not a special case.
    """
    subtitle = os.path.abspath(str(subtitle))
    reference = os.path.abspath(str(reference))

    for label, path in ((u"subtitle", subtitle), (u"reference", reference)):
        refusal = _not_a_subtitle_file(label, path)
        if refusal:
            return _api.Result(None, subtitle, ERROR, reason=refusal,
                               notes=[u"refused before anything was opened"])
    if _explicit._same_file(subtitle, reference):
        return _api.Result(
            None, subtitle, ERROR,
            reason=u"the subtitle and the reference are the same file: %s"
                   % subtitle,
            notes=[u"refused before anything was opened"])

    parsed = _formats.read_file(reference)
    if not parsed.ok:
        return _api.Result(
            None, subtitle, ERROR,
            reason=u"the reference %s could not be read as a subtitle: %s"
                   % (os.path.basename(reference), parsed.reason))
    starts = [c.start for c in parsed.cues]
    # ⛔ NO THIN-REFERENCE GUARD HERE, AND ONE WAS WRITTEN AND DELETED. The
    # verdict already answers a reference too thin to measure against — ERROR,
    # *"the reference has 3 cues and at least 5 are needed on both sides"* —
    # at exactly the same boundary: measured at 0, 1, 3, 4 and 5 cues, with
    # and without the guard, and the outcome never differed. Its mutant was
    # killed only by its own wording. Two copies of one floor is one that can
    # be changed and leave the other wrong (`doctrine/tooling`).

    ref = Reference(starts, TEXT_TRACK,
                    u"subtitle file %s (%d cues)"
                    % (os.path.basename(reference), len(starts)),
                    None)
    m = measure(None, subtitle, ref)
    judge([m], clusters_for([m]))
    outcome, reason = _outcome_of(m), _reason_of(m)
    notes = [u"aligned against a subtitle file, not a video: this makes the "
             u"subtitle agree with %s, and cannot tell whether that file "
             u"agrees with the video" % os.path.basename(reference)]

    if outcome == CONFIDENT:
        runs = _unchecked_by_reference(subtitle, starts, m.verdict.segments)
        if runs:
            lines = sum(len(run) for run in runs)
            longest = max(runs, key=lambda run: run[-1] - run[0])
            first, last = (_verdict._clock(longest[0]),
                           _verdict._clock(longest[-1]))
            stretch = first if first == last else u"%s to %s" % (first, last)
            if longest[-1] - longest[0] >= BUCKET:
                outcome = REFUSED
                reason = (
                    u"the reference covers only part of this subtitle: %d of "
                    u"its %d lines are more than %d s from any reference line "
                    u"(the longest unchecked stretch runs %s), so their "
                    u"timing was never checked and a cut or drift there "
                    u"would not be seen. render(result, force=True) writes "
                    u"it anyway, using the offset measured where the two "
                    u"overlap" % (lines, m.cue_count, int(BUCKET), stretch))
            else:
                if m.verdict.word in (u"locked", u"strong"):
                    m.verdict.word = u"fair"
                notes.append(
                    u"%d line%s near %s %s more than %d s from any reference "
                    u"line and went unchecked, so the word is capped at fair"
                    % (lines, u"" if lines == 1 else u"s", stretch,
                       u"is" if lines == 1 else u"are", int(BUCKET)))

    return _result_for(None, m, outcome, reason, notes=notes)


def _unchecked_by_reference(subtitle, reference_starts, segments):
    u"""Runs of subtitle lines no reference line comes near. -> [[seconds]]

    ⭐ Each line is placed at its CORRECTED time — sorted afterwards, because
    `mapper_for` is not monotonic across a negative jump — and lines inside a
    removed stretch are skipped, exactly as `apply._render` skips them: they
    are never written, so they are not unchecked output.
    """
    parsed = _formats.read_file(subtitle)
    if not parsed.ok or not segments or not reference_starts:
        return []
    mapper = mapper_for(segments)
    gone = removed_spans(segments)
    placed = sorted(mapper(c.start) for c in parsed.cues
                    if not any(lo <= c.start < hi for lo, hi in gone))
    ref = sorted(reference_starts)

    runs, current = [], []
    for t in placed:
        i = bisect.bisect_left(ref, t)
        near = min(abs(t - ref[j]) for j in (i - 1, i) if 0 <= j < len(ref))
        if near > BUCKET:
            current.append(t)
        elif current:
            runs.append(current)
            current = []
    if current:
        runs.append(current)
    return runs


def _not_a_subtitle_file(label, path):
    u"""-> a sentence when `path` cannot be the `label` side, else ``""``."""
    if os.path.isdir(path):
        return u"the %s is a directory, not a file: %s" % (label, path)
    if not os.path.isfile(path):
        return u"the %s does not exist: %s" % (label, path)
    ext = os.path.splitext(path)[1].lower()
    from .container import KNOWN_VIDEO_EXT
    if ext in KNOWN_VIDEO_EXT:
        # ⭐ The one mistake worth naming: this call is for two SUBTITLES, and
        # the video call is right next to it.
        return (u"the %s is a video (%s). This call aligns a subtitle against "
                u"another subtitle; for a video use "
                u"sync([(video, subtitle)])" % (label, os.path.basename(path)))
    return u""


class Rendered(object):
    u"""A retimed subtitle, not yet on disk. See `render()`."""

    __slots__ = ("data", "ext", "dropped_in_gap", "dropped_before_zero")

    def __init__(self, data, ext, dropped_in_gap, dropped_before_zero):
        self.data = data
        self.ext = ext
        self.dropped_in_gap = dropped_in_gap
        self.dropped_before_zero = dropped_before_zero

    def __repr__(self):
        return "Rendered(%d bytes, %s, %d dropped in a cut, %d before zero)" % (
            len(self.data), self.ext, self.dropped_in_gap,
            self.dropped_before_zero)


class _Rendering(object):
    u"""The two attributes `apply._render` reads, taken from a `Result`."""

    __slots__ = ("path", "verdict")

    def __init__(self, result):
        self.path = result.subtitle
        self.verdict = result


def render(result, force=False):
    u"""The retimed subtitle a `Result` describes, as bytes. -> `Rendered`

    ⛔ WRITES NOTHING. It is for a caller that writes files its own way —
    `<name>_retimed.srt`, a temp directory, a database — and works on any
    `Result`: from `sync()` in a dry run as well as from `sync_to_reference()`.

    ⭐ THE SAME RENDERER `sync(write=True)` USES, so the rules are the ones the
    written files already obey: the subtitle is RE-READ rather than trusted
    from the measurement, a cue straddling a cut keeps its duration and cannot
    invert, only the two whitelisted removals ever drop a cue, and the bytes
    come back **in the file's original format and encoding**. `Rendered`
    counts both removals so a caller can report them.

    `force`
        ⚠ Renders a REFUSED result. The alignment was measured and judged not
        good enough to trust; this writes it anyway, and it is the most
        dangerous thing this library does. An ERROR has no measured offset at
        all and is never rendered.

    Raises `ValueError` with a sentence for anything it will not render: an
    ERROR, a REFUSED result without `force`, a subtitle that no longer reads
    or now holds no cues, and an offset that would drop every cue.
    """
    outcome = getattr(result, "outcome", None)
    if outcome == ERROR or not getattr(result, "segments", None):
        raise ValueError(
            u"%s was never measured (%s), so there is no offset to apply — "
            u"a file is never retimed by a number nobody measured"
            % (os.path.basename(getattr(result, "subtitle", "") or u"?"),
               getattr(result, "reason", u"") or u"no segments"))
    if outcome != CONFIDENT and not force:
        raise ValueError(
            u"%s was measured and REFUSED: %s. Pass force=True to render it "
            u"anyway." % (os.path.basename(result.subtitle), result.reason))
    data, in_gap, before_zero = _apply._render(_Rendering(result))
    return Rendered(data, os.path.splitext(result.subtitle)[1], in_gap,
                    before_zero)


def _vad_note():
    u"""⛔ `vad=True` may not silently do nothing, and it may not raise from
    four frames down either.

    `doctrine/architecture`: *instruction, not refusal -- an unavailable
    feature renders what would make it available.* `verdict.MASK_BAND` is
    `None` and a mask verdict RAISES, deliberately, because borrowing the
    cue-vs-cue 2.5x would silently refuse the 2.42x uncut pair
    `12-alignment.md` §5 measured as CORRECT.
    """
    return (u"vad=True was asked for and the speech-mask path is not built "
            u"yet (RUNBOOK B6): its accept/refuse band has never been fitted, "
            u"and borrowing the cue-vs-cue band would silently refuse pairs "
            u"12-alignment.md §5 measured as correct. Videos with no usable "
            u"subtitle track are refused by name rather than guessed at.")


def _default_reader(path):
    from . import container as _container
    return _container.read(path, timing=True)


def _default_trash_root():
    u"""⛔ NEVER beside the media. `LEDGER-HOT.md`: subsync wrote `_ref_2.ass`
    and a 500 KB `.npy` next to the subtitles it was aligning, inside a corpus
    its own README marks do-not-modify.

    ⚠ `dedupe.py` deliberately has no default for this -- *the caller supplies
    the root; there is no default that could quietly be the media folder.*
    `sync()` is that caller, and the per-user cache directory is the answer.
    """
    return os.path.join(str(_paths.cache_root()), _dedupe.TRASH_DIR)


# ---------------------------------------------------------------------------
# reading the reference
# ---------------------------------------------------------------------------

def reference_for(video_path, reader):
    u"""What to align against. -> (`Reference` or None, reason)

    ⭐ THE TRACK WITH THE MOST CUES WINS, and that is not arbitrary: a
    `forced` track carries signs only -- a few dozen moments over a whole
    episode -- so it aligns to a correct offset with almost no whole-runtime
    evidence behind it. Ranking on cue count deprioritises it without
    excluding it, because `00-INDEX.md` Rule 1 says the embedded track is an
    accelerator and a thin accelerator still beats none.

    ⚠ And a thin one is not silently trusted: the runtime walk finds every
    bucket too thin, `_runtime_check` calls that `absent`, and the verdict
    caps the word at `fair`.
    """
    info = reader(video_path)
    if not info.ok:
        return None, info.reason or u"the video could not be read"

    usable = [t for t in info.subtitle_tracks
              if t.cues is not None and len(t.cues) >= MIN_ALIGNABLE_CUES]
    if not usable:
        thin = [t for t in info.subtitle_tracks if t.cues is not None]
        if thin:
            why = (u"its %d subtitle track%s carr%s too few cues to measure "
                   u"against (%s, and %d are needed)"
                   % (len(thin), u"" if len(thin) == 1 else u"s",
                      u"ies" if len(thin) == 1 else u"y",
                      u", ".join(u"%d" % len(t.cues) for t in thin[:4]),
                      MIN_ALIGNABLE_CUES))
        else:
            why = u"it has no subtitle track to align against"
        # 🚨 The hand-back sentence `03-permissions.md` §hand-back requires:
        # what was measured, why it fell short, and WHAT WOULD CHANGE IT.
        return None, (u"%s. The speech-mask path that does not need one lands "
                      u"at RUNBOOK B6 and its band has not been fitted yet, "
                      u"so nothing is guessed here." % why)

    usable.sort(key=lambda t: (-len(t.cues), not t.default, bool(t.forced),
                               t.index))
    track = usable[0]
    kind = BITMAP_TRACK if _is_bitmap(track.codec) else TEXT_TRACK
    description = (u"track %d (%s%s%s, %d cues)"
                   % (track.index, track.codec or u"?",
                      u", %s" % track.language if track.language else u"",
                      u", forced" if track.forced else u"",
                      len(track.cues)))
    # 🚨 `Track.cues` IS A LIST OF `cues.Cue`, NOT OF NUMBERS, and `align()`
    # takes cue-start MOMENTS. Passing the objects straight through raised
    # `float() argument must be ... not 'Cue'` from four frames down inside
    # `unique_starts`, on every real container.
    # ⭐ Worse than the bug: the INJECTED reader in the suite handed back
    # floats, so every seam check was green against a shape the product never
    # produces. `LEDGER-HOT.md`'s *an ASCII fixture cannot test an encoding
    # rule*, wearing a new hat -- the fake and the real thing must agree about
    # the type, or the seam tests measure the fake.
    return Reference([c.start for c in track.cues], kind, description,
                     info.duration, track), u""


def _is_bitmap(codec):
    lowered = (codec or u"").lower()
    return any(fragment in lowered for fragment in _BITMAP_CODECS)


# ---------------------------------------------------------------------------
# measuring one candidate
# ---------------------------------------------------------------------------

class _Measured(object):
    u"""One (video, subtitle) pair, read and aligned but NOT yet judged.

    ⚠ There is no verdict on it, on purpose. The cluster is not known until
    every pair in the run has been measured, and the cluster is the escalation
    band's second signal -- so judging as we go would decide the weak pairs
    before the evidence that lifts them exists.
    """

    __slots__ = ("video", "subtitle", "fit", "sidecar", "cue_count",
                 "content_end", "reference", "verdict", "notes", "rejection",
                 "cluster_coherence", "pair", "decision", "speculative")

    def __init__(self, video, subtitle, fit=None, sidecar=None, cue_count=0,
                 content_end=None, reference=None, notes=(), rejection=None):
        #: The cluster this pair sat in, when one existed. ⚠ Recorded whether
        #: or not it lifted anything -- `05-interface.md` puts it on `Result`,
        #: and a reader needs to know a cluster was consulted and did not help.
        self.cluster_coherence = None
        #: Set on the explicit path only.
        self.pair = None
        self.decision = None
        #: ⛔ THE ABSOLUTE-NUMBERING FALLBACK OFFERED THIS PAIR ON A GUESS
        #: about how the two names count episodes, and `dedupe` may never
        #: TRASH a speculative loser -- it is a subtitle for an episode the
        #: user may simply not have a video for yet.
        #: `discover.Candidates._absolute_fallback` carries the reasoning.
        self.speculative = False
        self.video = video
        self.subtitle = subtitle
        self.fit = fit
        self.sidecar = sidecar
        self.cue_count = cue_count
        self.content_end = content_end
        self.reference = reference
        self.verdict = None
        self.notes = list(notes)
        #: Set when the candidate never reached the aligner -- unreadable, or
        #: refused by the runtime gate. ⚠ NOT the same as a refused verdict,
        #: and it carries its own sentence.
        self.rejection = rejection

    @property
    def measured(self):
        return self.fit is not None


def measure(video_path, subtitle_path, reference):
    u"""Read one subtitle and align it. -> `_Measured`. ⛔ Judges nothing.

    ⭐ THE CHEAP GATE RUNS FIRST. `09-corpus-strategy.md` Stage 3: runtime is
    the cheapest possible filter and `duration.py` fitted every constant
    against a measured population. A subtitle 90 minutes long cannot belong to
    a 24-minute video, and finding that out costs one subtraction.
    """
    parsed = _formats.read_file(subtitle_path)
    sidecar = _sidecar.parse_path(subtitle_path)
    if not parsed.ok:
        # 🚨 ERROR, not REFUSED. `LEDGER-HOT.md`: never conflate *"parsed zero
        # cues"* with *"could not read the file"* -- subsync shipped that
        # confusion twice. This branch is only the second one; a file that
        # reads cleanly and contains nothing falls through to the aligner and
        # the VERDICT calls it unmeasurable, which is the honest word.
        return _Measured(video_path, subtitle_path, sidecar=sidecar,
                         reference=reference,
                         rejection=(ERROR,
                                    u"%s could not be read as a subtitle: %s"
                                    % (os.path.basename(subtitle_path),
                                       parsed.reason)))

    starts = [c.start for c in parsed.cues]
    content_end = _duration.content_end(starts)
    gate, why = _duration.duration_verdict(reference.duration, content_end,
                                           len(parsed.cues))
    if gate == _duration.IMPOSSIBLE:
        # 🚨 ERROR, NOT REFUSED, AND THE TEST IS *IS THERE AN OFFSET TO STAND
        # BEHIND* -- not *was the file readable*.
        #
        # REFUSED promises *"it aligned, but not well enough to trust"*
        # (`03-permissions.md`), and nothing here aligned at all. Built as
        # REFUSED first, and `--force` then authorised a write that
        # `apply._render` correctly refused -- *"the verdict carries no
        # segments... a file is never retimed by a number nobody measured"* --
        # leaving the user a forced write that silently did nothing.
        #
        # ⭐ `verdict.py` already rules this exact shape the same way: a file
        # that reads perfectly and carries three cues is `_too_thin` and comes
        # back **ERROR**, because *not measured* and *measured and rejected*
        # are different results. This is that rule, one stage earlier.
        # ⛔ And it is what makes `--force` correct without a special case:
        # force overrides a refusal, never a missing measurement.
        return _Measured(video_path, subtitle_path, sidecar=sidecar,
                         cue_count=len(parsed.cues), content_end=content_end,
                         reference=reference,
                         rejection=(ERROR, why))

    fit = align(unique_starts(reference.starts), unique_starts(starts),
                reference.duration)
    return _Measured(video_path, subtitle_path, fit=fit, sidecar=sidecar,
                     cue_count=len(parsed.cues), content_end=content_end,
                     reference=reference)


# ---------------------------------------------------------------------------
# clusters -- 09-corpus-strategy.md Stage 4
# ---------------------------------------------------------------------------

def clusters_for(measured):
    u"""Group the run's pairs into clusters. -> {group key: `arbitrate.Cluster`}

    ⭐ `09-corpus-strategy.md` Stage 4: *files come in clusters -- one release
    group's episodes share a `tokenize()` shape*, and 97.0% of the video
    corpus sits in clusters of at least three. Coherence across those episodes
    is the escalation band's SECOND SIGNAL, and the only thing that can lift a
    weak pair out of it.

    ⚠ THE OFFSETS ARE MILLISECONDS. `arbitrate` owns that unit and
    `Cluster.agrees_with` owns the conversion back -- `LEDGER-HOT.md` records a
    lift written from seconds against a consensus in milliseconds.

    🚨 ONLY A **MEASURABLE** FIT IS EVIDENCE, and this is a fix. Every measured
    pair used to vote, including the ones `Fit.measurable` says cannot be
    scored at all. Measured on four episodes each carrying one correct subtitle
    and one wrong one:

        every measured pair   size 7   coherence 0.57  <- BELOW the 0.60 bar
        only measurable fits  size 4   coherence 1.00

    ⛔ The failure is silent and it runs the WRONG WAY: a video's *rejected*
    candidates drag the cluster under the bar, so it can no longer vouch for
    the correct pairs beside it -- and the pair that loses is exactly the
    weak-but-correct one in the 1.5-2.5x escalation band this mechanism exists
    to rescue. Found twice: by reading one rendered run, and by an adversarial
    pass that measured the lift being lost (`CONFIDENT` -> `REFUSED`).

    🚨 `Fit.excess` WAS ALREADY ZEROED FOR THIS REASON -- *"a caller that reads
    `excess` and nothing else must not be handed a confident number built out
    of one cue"*. `_own_offset` reads `single[0]`, which is not zeroed, so the
    argument had been made once and applied in one place. ⭐ **When a value is
    deliberately neutered for unmeasurable input, ask the same question of
    every other field derived from the same object.**

    ⚠ AND THE OBVIOUS ALTERNATIVE WAS MEASURED AND REJECTED. This docstring
    used to claim *"the best-ranked candidate for each video, not every
    candidate"* -- which the code never did, and which is WORSE: with identical
    names the rank falls to its path tiebreak, so a wrong `.en.srt` sorts above
    the right `.ja.srt` and best-per-video coheres at **0.75 around the WRONG
    offset**. ⛔ A candidate rank is a hypothesis order, not a quality order.
    Only the alignment can say which is which, so only the alignment decides
    what counts as evidence.
    """
    groups = {}
    for m in measured:
        if not m.measured or not m.fit.measurable:
            continue
        key = _cluster_key(m)
        if key is None:
            continue
        offset = _verdict._own_offset(m.fit)
        if offset is None:
            continue
        groups.setdefault(key, []).append(offset * 1000.0)
    return {k: _arbitrate.Cluster(v) for k, v in groups.items()}


def _cluster_key(m):
    u"""What makes two pairs members of one cluster.

    The subtitle's own release title, **its season**, and the folder it sits
    in: a release group's episodes share all three, and two groups' releases of
    the same show share neither the title nor the folder. ⚠ Normalised, so
    `[Erai-raws] Show - 01` and `[Erai-raws] Show - 02` land together while
    `Show (2019)` does not join them by accident.

    🚨 THE SEASON IS PART OF THE KEY, and leaving it out was the same mistake
    `LEDGER-HOT.md` records as made **four separate times** on the pairing
    side: *never group on episode alone -- multi-season shows collide.* Without
    it, `Show S01E01` and `Show S02E01` sitting in one folder pooled into a
    single cluster, and `_series.normalize` also folds `Gintama` and `Gintama'`
    to one key -- four real seasons whose only separator is the punctuation
    signature. Found by an adversarial pass.
    """
    title = _series.normalize(_stem_title(m.subtitle)).key
    if not title:
        return None
    parsed = _episode_of(m.subtitle)
    season = parsed.key()[0] if parsed else None
    # 🚨 AND THE RELEASE GROUP, WHEN THE NAME CARRIES ONE. The docstring above
    # says a cluster is *one release group's episodes*, and the folder alone
    # does not deliver that: `[ATX] Show - 01` and `[Web] Show - 01` sitting in
    # ONE folder -- the ordinary downloads case -- pooled into a single
    # cluster, because `_stem_title` strips the group and both became `Show`.
    #
    # ⛔ Measured on four episodes each having a broadcast rip and a web rip,
    # both genuinely alignable at different offsets: coherence **0.50** and
    # `coheres=False`, so the escalation band's second signal stopped firing in
    # a folder where each source agrees with itself perfectly. Found by an
    # adversarial pass.
    # ⚠ `episode.union()` returns a `Union`, which carries the per-parser
    # `results` and NOT a `group` of its own -- only `Parsed` has one. Reaching
    # for `parsed.group` raised `AttributeError` on every real name.
    return (title, season, _release_group(parsed),
            os.path.normcase(os.path.dirname(m.subtitle)))


def _release_group(parsed):
    u"""The release group this name declares, folded. -> unicode

    ⚠ Read from our OWN parser's `Parsed`, through the `Union` that wraps it.
    An absent group is the empty string, so two names that both lack one still
    cluster together -- which is the ordinary single-source folder.
    """
    for result in (getattr(parsed, "results", None) or ()):
        group = getattr(result, "group", None)
        if group:
            return group.strip().lower()
    return u""


def _episode_of(path):
    from .naming import episode as _episode

    return _episode.union(os.path.basename(path))


def _stem_title(path):
    u"""The subtitle's series title, from the parser this project ships."""
    from .naming import episode as _episode

    parsed = _episode.union(os.path.basename(path))
    return parsed.title if parsed and parsed.title else \
        os.path.splitext(os.path.basename(path))[0]


def judge(measured, clusters):
    u"""Give EVERY pair a verdict. ⛔ One authority: `verdict()`.

    ⚠ The cluster is passed in and `verdict()` asks `agrees_with` about THIS
    pair before letting it lift -- `LEDGER-HOT.md`: *a cluster that coheres
    says nothing about any one pair in it.*

    🚨 A PAIR THAT NEVER REACHED THE ALIGNER STILL GETS A `Verdict` OBJECT,
    and that is a fix, not tidiness. It used to be left at `None`, so a
    candidate refused by the runtime gate reached `dedupe.Candidate(verdict=
    None)` -- and `apply_plan`, which reads `getattr(candidate.verdict,
    "outcome", None)`, saw *"the verdict is missing"* and refused a write the
    user had explicitly FORCED. The report then said **"WRITTEN UNDER
    --force"** while `output_path` was `None`: a confidently wrong report,
    which is worse than the missing write.

    ⭐ The rejection already carries an outcome and a sentence, which is
    exactly what a `Verdict` is. Manufacturing it here means nothing
    downstream has to remember that `verdict` can be absent.
    """
    for m in measured:
        if m.measured:
            cluster = clusters.get(_cluster_key(m))
            m.cluster_coherence = (cluster.coherence if cluster is not None
                                   else None)
            m.verdict = _verdict.verdict(m.fit, cluster=cluster,
                                         reference_kind=m.reference.kind)
        elif m.verdict is None and m.rejection is not None:
            outcome, reason = m.rejection
            m.verdict = _verdict.Verdict(outcome, reason, band=u"error")
    return measured


# ---------------------------------------------------------------------------
# the scan path
# ---------------------------------------------------------------------------

def _sync_scan(scan, write, rename, dedupe, keep_all, out_dir, trash_root,
               sender, reader, vad, notes, results=None, suffix=None):
    u"""Measure and decide a whole discovery. -> `SyncReport`

    ⭐ TWO PASSES, and the reason is the cluster. Every pair is measured first
    and judged second, because a cluster's coherence is the escalation band's
    second signal and it does not exist until every episode has been aligned.
    Judging as we go would decide the weak pairs before the evidence that
    lifts them was in hand.

    ⭐ AND A HASH-AND-SKIP PASS IN FRONT OF BOTH (RUNBOOK 3a-bis). It runs
    before `reference_for`, which is the whole point: the container read is
    0.087 s a file and `06-edge-cases.md` §7 asks for *zero decoding* on a
    re-run, so the question has to be settled before anything is opened.

    ⚠ TWO CONSEQUENCES OF SKIPPING, BOTH NAMED RATHER THAN HIDDEN:

      1. **A settled FILM library still pays for `pair_movies`.** The film
         pairing above runs before the loop and its `duration_of` seam reads
         containers -- lazily, so a library of television pays nothing, but a
         film set that reaches the runtime veto is opened whatever the store
         says. *Zero decoding* is measured and true for the episode case; for
         films it is *fewer*. Fixing it means asking the store before the
         candidate set exists, and the candidate set is what the store's
         question is about.
      2. 🚨 **A new episode in a settled folder gets a THINNER CLUSTER.**
         `clusters_for` sees only what was measured this run, so an episode
         added beside twenty-three skipped ones has no neighbours to cohere
         with -- and cluster coherence is `D7`, the escalation band's second
         signal. It errs safe (a borderline pair is REFUSED where a full run
         would have lifted it) and it is a real difference between *sync the
         folder* and *sync the folder again*. ⛔ NOT quietly patched by feeding
         remembered offsets into the cluster: `D7` is a Sonic ruling about what
         evidence may lift a pair, and changing its inputs is not a cache's
         decision to make.
    """
    references, measured, unpaired, out = {}, [], [], []
    settled, protected, video_keys = [], {}, {}
    #: ⭐ The subset of `protected` a skipped video actually WROTE — its
    #: answers. Rule 2 gets this; rule 1 gets the wider set. Two hazards, two
    #: sets — see `_resolve_ownership`.
    answers = {}
    #: ⭐ {path: ContentKey} for this discovery loop only. A subtitle offered to
    #: several videos is hashed ONCE. ⚠ Owned by the run and discarded with it:
    #: the loop completes before any slot is performed, so nothing can change
    #: underneath it — and a memo that outlived that would be a cache claiming
    #: a file had not changed, which is the one thing the store may not do.
    hashes = {}
    # ⭐ WHAT THIS RUN WAS ASKED TO PRODUCE, built once and used at BOTH ends —
    # the skip that reads a record and the record this run writes. Two
    # descriptions of one thing drift, and the drift reads as *already in sync*.
    shape = _results.run_shape(rename=rename, out_dir=out_dir,
                               keep_all=keep_all, dedupe=dedupe, suffix=suffix)
    #: {video: {subtitle path: ContentKey}} as of BEFORE anything moved.
    #: ⭐ The skip check has already hashed every candidate; the recording
    #: half needs exactly that set and cannot recompute it afterwards, because
    #: by then the losers are in the trash.
    before = {}

    # ⚠ THE FILM PAIRING IS MADE AGAIN HERE, WITH RUNTIMES. `scan()` opens
    # nothing, so its pairing had neither the duration veto nor the runtime
    # tiebreak and refused any film set it could not separate on name and
    # folder alone. Same function, better evidence -- never a second
    # implementation. `05-interface.md` §*this file and the RUNBOOK disagreed*.
    films = _movies.pair_movies(
        [v.path for v in scan.videos], [s.path for s in scan.subtitles],
        duration_of=_durations_for(scan, references, reader),
        parsed_of=_api._parsed_of(scan.videos + scan.subtitles))
    film_subs = {}
    for pair in films.pairs:
        film_subs.setdefault(pair.video, []).append(pair.subtitle)
    by_path = {s.path: s for s in scan.subtitles}

    for video in scan.videos:
        offered = list(scan.candidates.for_video(video))
        for path in film_subs.get(video.path, ()):
            item = by_path.get(path)
            if item is not None and item not in offered:
                offered.append(item)
        if not offered:
            unpaired.append((video.path, scan.nothing_reason(video)))
            continue

        # ⭐ `Scan.rank` -- the ranking rule lives in `Candidacy.rank_key` and
        # `Scan` owns the sort. `scan.for_video` cannot be called instead
        # because its film half is the PROVISIONAL pairing, and this list is
        # the one made with runtimes.
        ranked = scan.rank(video, offered)

        # ⭐ A COPY IS NEVER RETIMED AGAIN. With a suffix, the previous run's
        # `Show - 01_rt.ja.srt` sits beside its original and is offered for
        # the same episode; measuring it would write `Show - 01_rt_rt.ja.srt`.
        # ⚠ Removed BEFORE the skip check below, so what the store records as
        # this video's candidates is the same set a re-run asks about.
        copies = []
        if suffix:
            copies = [c for c in ranked
                      if _sidecar.is_suffixed(c.subtitle.name, suffix)]
            ranked = [c for c in ranked
                      if not _sidecar.is_suffixed(c.subtitle.name, suffix)]
            if not ranked:
                unpaired.append((
                    video.path,
                    u"every subtitle offered for it is itself a retimed copy "
                    u"(its name ends in %s), and a copy is never retimed "
                    u"again" % suffix))
                continue

        # ⭐ 3a-bis: THE HASH-AND-SKIP READ, AND IT IS HERE FOR THE COST, NOT
        # FOR TIDINESS. One line further down is `_reference_cached`, which
        # opens the container. Everything this decision saves is saved by
        # being asked before that call.
        if results is not None:
            # ⭐ THE COPIES ARE SHOWN TO THE STORE, NEVER TO THE ALIGNER. The
            # store recognises a finished video by finding its recorded OUTPUT
            # among the files on offer — and a suffix run's output is exactly
            # the copy measurement leaves out. Without it here, a suffixed
            # folder was re-measured on every run and then refused its own
            # write, because the copy it had made was in the way.
            state = _results.settled(results, video.path,
                                     [c.subtitle.path for c in ranked + copies],
                                     shape=shape, hashes=hashes)
            video_keys[video.path] = state.video_key
            before[video.path] = state.digests
            if state.skip:
                settled.append((video.path, state.reason))
                # 🚨 A SKIPPED VIDEO STILL OWNS ITS FILES. `_resolve_ownership`
                # rule 1 is computed from the slots of the run and a skipped
                # video contributes none, so without this its answer is just
                # another video's losing candidate -- and the two-shows library
                # that lost every subtitle it had comes back through a door the
                # 3b fix does not cover.
                protected.update((_key(p), v)
                                 for p, v in state.protected.items())
                answers.update((_key(p), v)
                               for p, v in state.answers.items())
                continue

        reference, why = _reference_cached(video.path, references, reader)
        if reference is None:
            # ⭐ ONE result for the video, not one per candidate. Every
            # candidate fails identically and for a reason that is about the
            # VIDEO, so N copies of the same sentence would bury it.
            out.append(_api.Result(
                video.path, None, ERROR,
                reason=u"%s could not be measured: %s"
                       % (os.path.basename(video.path), why),
                episode=_episode_number(video.path),
                notes=[_waiting_note(ranked)] + list(notes)))
            continue
        for candidacy in ranked:
            m = measure(video.path, candidacy.subtitle.path, reference)
            # ⭐ CARRIED ACROSS THE SEAM. `measure()` takes two PATHS, so the
            # candidacy -- and with it the fact that this pair was a guess
            # about episode numbering -- ends here unless it is copied. The
            # trash depends on it downstream.
            m.speculative = candidacy.speculative
            measured.append(m)

    judge(measured, clusters_for(measured))

    by_video = {}
    for m in measured:
        by_video.setdefault(m.video, []).append(m)

    # ⭐ THREE PHASES, and the middle one is the fix. Every slot is PLANNED
    # first, ownership is resolved across the whole run, and only then is
    # anything performed -- because *"which video does this file belong to"* is
    # a question no single slot can answer. See `_resolve_ownership`.
    slots = []
    for video in scan.videos:
        slots.extend(_decide_video(video.path, by_video.get(video.path, ()),
                                   rename=rename, dedupe=dedupe,
                                   keep_all=keep_all, explicit=False,
                                   suffix=suffix))
    mirror = _mirror_root([v.path for v in scan.videos])
    _resolve_ownership(slots, out_dir=out_dir, mirror_root=mirror,
                       rename=rename, protected=protected, answers=answers)
    for slot in slots:
        done = _perform_slot(slot, write=write, rename=rename,
                             out_dir=out_dir, mirror_root=mirror,
                             trash_root=trash_root, sender=sender,
                             force=False)
        _record_slot(results, slot, done, video_keys,
                     before.get(slot.video, {}), shape=shape)
        out.extend(done)

    return SyncReport(out, unpaired=unpaired, skipped=scan.skipped,
                      notes=notes, settled=settled)


def _waiting_note(ranked):
    return (u"%d subtitle%s waiting for it: %s"
            % (len(ranked), u" was" if len(ranked) == 1 else u"s were",
               u", ".join(os.path.basename(c.subtitle.path)
                          for c in ranked[:4])))


def _reference_cached(video_path, cache, reader):
    u"""One container read per VIDEO per run, never one per candidate.

    ⭐ `00-INDEX.md` Rule 4 at the level that matters most here: the container
    read is 0.087 s and the alignment is 0.049 s, so re-reading the track for
    each of a video's candidates would make the read the dominant cost of the
    whole run.
    """
    if video_path not in cache:
        cache[video_path] = reference_for(video_path, reader)
    return cache[video_path]


def _durations_for(scan, references, reader):
    u"""The `duration_of` seam `movies.pair_movies` takes, answering for BOTH
    kinds of file -- a video's container runtime and a subtitle's content end.

    ⚠ LAZY. It is called only for the films that actually reach the runtime
    veto, so a library of television pays nothing for it. And it reuses the
    reference cache, so a film whose track was read for alignment is not read
    twice.
    """
    ends = {}
    subs = set(s.path for s in scan.subtitles)

    def duration_of(path):
        if path in subs:
            if path not in ends:
                parsed = _formats.read_file(path)
                ends[path] = _duration.content_end(
                    [c.start for c in parsed.cues]) if parsed.ok else None
            return ends[path]
        reference, _why = _reference_cached(path, references, reader)
        return reference.duration if reference is not None else None

    return duration_of


# ---------------------------------------------------------------------------
# the explicit path -- 🚨 through explicit_pairs(), ruled and binding
# ---------------------------------------------------------------------------

def _sync_plan(plan, write, rename, dedupe, keep_all, out_dir, trash_root,
               sender, reader, force, vad, notes, results=None, suffix=None):
    u"""Measure and decide a `PairPlan`. -> `SyncReport`

    🚨 EVERY REFUSAL THE PLAN CARRIES BECOMES A RESULT. That is the whole
    point of routing the tuples through `explicit_pairs()`: a swapped pair, a
    missing file, a subtitle claimed by two videos and a directory given where
    a file goes all come back as ERROR results with their own sentences,
    instead of vanishing.

    ⛔ AND EVERY ACCEPTED PAIR IS DECIDED. `PairPlan.writable()` raises
    `VerdictRequired` naming any pair a loop skipped, so it is called here as
    the structural proof rather than trusted to this function's control flow.

    ⛔ IT RECORDS, AND IT NEVER SKIPS -- the asymmetry is the point (RUNBOOK
    3a-bis). ⭐ Recording: a completed sync is a completed sync however the
    pair was named, and a file synced explicitly that a later discovery run
    then re-aligned would be *"every run re-does the work"* with an extra step.
    ⛔ Skipping: the user typed these pairs. Naming a pair is an instruction
    to act on it, and answering an instruction with *"I did that last week"* is
    the same silence `--force` on a `Scan` is refused for. It is also what
    would leave `plan.writable()` with an undecided pair, which raises -- so
    the structure says it too.
    """
    references, measured, out = {}, [], []
    video_keys = {}

    for refusal in plan.refusals:
        out.append(_api.Result(
            refusal.video, refusal.subtitle, refusal.outcome,
            reason=refusal.reason,
            episode=_episode_number(refusal.video) if refusal.video else None,
            notes=[u"refused before anything was opened (%s)" % refusal.kind]))

    for pair in plan.pairs:
        reference, why = _reference_cached(pair.video, references, reader)
        if reference is None:
            m = _Measured(pair.video, pair.subtitle,
                          sidecar=_sidecar.parse_path(pair.subtitle),
                          notes=pair.notes,
                          rejection=(ERROR,
                                     u"%s could not be measured: %s"
                                     % (os.path.basename(pair.video), why)))
        else:
            m = measure(pair.video, pair.subtitle, reference)
            m.notes.extend(pair.notes)
        m.pair = pair
        measured.append(m)

    judge(measured, clusters_for(measured))

    # 🚨 THE DECISION IS MINTED BY `ExplicitPair.decide(verdict)` AND BY
    # NOTHING ELSE. `Decision` refuses to be constructed directly, so there is
    # no route from here to `write is True` that did not cost a verdict object.
    for m in measured:
        m.decision = m.pair.decide(_verdict_of(m), force=force)
    plan.writable()          # ⛔ raises if any accepted pair went undecided

    by_video = {}
    for m in measured:
        by_video.setdefault(m.video, []).append(m)
    slots = []
    for video_path in _ordered(m.video for m in measured):
        slots.extend(_decide_video(video_path, by_video[video_path],
                                   rename=rename, dedupe=dedupe,
                                   keep_all=keep_all, explicit=True,
                                   suffix=suffix))
    mirror = _mirror_root([m.video for m in measured])
    _resolve_ownership(slots, out_dir=out_dir, mirror_root=mirror,
                       rename=rename)
    # ⭐ HASHED BEFORE ANYTHING MOVES, for the same reason as on the scan
    # path: `Record.stable` compares the run's output against what the plan
    # was made FROM, and a superseded candidate is in the trash by the time
    # the record is written. ⚠ Only when there is a store to write to -- an
    # explicit run with `results=False` pays nothing.
    before = {}
    if results is not None:
        for slot in slots:
            known = before.setdefault(slot.video, {})
            for candidate in slot.candidates:
                if candidate.path in known:
                    continue
                try:
                    known[candidate.path] = _results.subtitle_key(candidate.path)
                except (IOError, OSError):
                    pass
    for slot in slots:
        done = _perform_slot(slot, write=write, rename=rename,
                             out_dir=out_dir, mirror_root=mirror,
                             trash_root=trash_root, sender=sender,
                             force=force)
        _record_slot(results, slot, done, video_keys,
                     before.get(slot.video, {}),
                     shape=_results.run_shape(rename=rename, out_dir=out_dir,
                                              keep_all=keep_all,
                                              dedupe=dedupe, suffix=suffix))
        out.extend(done)

    if vad:
        for r in out:
            r.notes.extend(notes)
    return SyncReport(out, notes=notes)


def _verdict_of(m):
    u"""The `Verdict` object `decide()` requires. ⭐ `judge()` has already
    given every pair one, including the ones that never reached the aligner --
    so this is a read, and the guard below is what proves it stays that way.

    ⚠ `decide()` takes a verdict POSITIONALLY and `force=True` with no verdict
    RAISES `VerdictRequired`, which must never be caught. Returning `None`
    here would trip it four frames away from the cause.
    """
    if m.verdict is None:
        raise _explicit.VerdictRequired(
            "judge() left %s without a verdict, so there is nothing to decide "
            "with. Every measured pair gets one from verdict(), and every "
            "rejected one gets it from its own rejection -- reaching here "
            "means a third state was added and not handled."
            % os.path.basename(m.subtitle))
    return m.verdict


def _ordered(paths):
    u"""Unique, in first-seen order. ⚠ Never a set: the report's order is the
    order the user gave, and a set would reshuffle it per process."""
    seen, out = set(), []
    for p in paths:
        if p not in seen:
            seen.add(p)
            out.append(p)
    return out


# ---------------------------------------------------------------------------
# from measurements to results -- one per (video x language) slot
# ---------------------------------------------------------------------------

class _Slot(object):
    u"""One (video x language) slot, PLANNED but not performed."""

    __slots__ = ("video", "stem", "lang", "group", "by_path", "candidates",
                 "plan", "writes", "superseded", "notes", "explicit",
                 "refused_writes")

    def __init__(self, video, stem, lang, group, by_path, candidates, plan,
                 writes, superseded, notes, explicit):
        self.video = video
        self.stem = stem
        self.lang = lang
        self.group = group
        self.by_path = by_path
        self.candidates = candidates
        self.plan = plan
        self.writes = writes            # [(dedupe.Candidate, output name)]
        self.superseded = superseded    # [dedupe.Candidate]
        self.notes = notes
        self.explicit = explicit
        #: [(candidate, name)] rule 2 refused. ⚠ NOT the same as having no
        #: winner: these were decided and then withheld, and a report that
        #: cannot tell the two apart describes a run that wrote nothing as a
        #: plan it chose not to carry out.
        self.refused_writes = []


def _resolve_ownership(slots, out_dir=None, mirror_root=None, rename=True,
                       protected=(), answers=None):
    u"""Decide, ACROSS THE WHOLE RUN, which slot owns which file.

    ===========================================================================
    🚨 THIS FUNCTION EXISTS BECAUSE AN ORDINARY LIBRARY LOST EVERY SUBTITLE.
    ===========================================================================

    Two shows using bare episode numbers -- `Alpha/01.mkv` + `01.ja.srt`,
    `Bravo/01.mkv` + `01.ja.srt` -- and the episode index correctly offers each
    video BOTH files. The foreign one is correctly REFUSED. But `dedupe.plan`
    supersedes every non-winner **within its slot**, and the file it supersedes
    is the WINNER of another slot. Measured, on default flags:

        summary: '2 synced'
        LOST from the library: Alpha/01.ja.srt  Alpha/02.ja.srt
                               Bravo/01.ja.srt  Bravo/02.ja.srt

    ⛔ `dedupe.plan` cannot see this and should not have to: it decides ONE
    slot, correctly, from the candidates it was given. `sync()` is the only
    layer that sees the whole run, so the cross-slot question is its own.
    `03-permissions.md`: a REFUSED pair is *"left untouched, reason stated"* --
    it was being moved instead. Found by an adversarial pass.

    TWO RULES, and both are about a file belonging to exactly one place:

      1. ⭐ **A file that any slot would WRITE is never superseded by another
         slot.** That is what makes a refusal leave it alone.
      2. 🚨 **A shared source is never WRITTEN OVER while another slot still
         needs to read it.**

    ⚠ RULE 2 WAS FIRST BUILT AS *"a file two slots would both write belongs to
    NEITHER"*, and Sonic ruled that too narrow:

        *"It is not a new mechanism, it is arbitration widening from 'pick the
        best' to 'keep everyone who clears the bar and shares the episode key'.
        Two rips of one episode both align confidently, and that fact IS the
        evidence they are the same content. The rule does not change: the
        timing decides. What changes is that the answer may be a set."*

    ⭐ `Show [720p].mkv` and `Show [1080p].mkv` sharing one subtitle is an
    ordinary library, and refusing it threw away a correct answer. Each video
    already gets **its own alignment and its own offset** -- `measure()` runs
    per (video, subtitle) pair -- so the two outputs are independently derived,
    never a copied file. ⛔ Sonic's condition: *"two rips can differ by a trim,
    and writing one result twice would be a confidently wrong file."*

    🚨 SO THE REAL HAZARD IS NARROWER, AND IT IS AN ORDERING ONE.
    `apply._render` re-reads the source at write time -- correctly, *"the file
    always wins"* -- so if one slot's TARGET is the shared source itself, it
    mutates the bytes the other slots have not read yet. Measured before this:
    **-4.0 s applied for a true offset of -2.0 s**, both reported CONFIDENT,
    and under `rename=False` the user's only copy destroyed.

    ⭐ That is the only write refused: an **in-place** write over a source
    somebody else still needs. Everything else goes ahead.

    ⭐ `protected` IS RULE 1 EXTENDED TO THE VIDEOS THAT ARE NOT HERE. A video
    the results DB settled has no slot in this run, so it claims nothing --
    and its answer would be an ordinary losing candidate to whichever
    neighbour also matched it. That is the two-shows-bare-episodes shape
    exactly, arriving through a door the 3b fix does not cover, because the
    3b fix reads `slots`. Keyed with `_key`, like everything else here.
    """
    # 🚨 THE ABSENT OWNERS GO IN FIRST, AND THIS IS THE WHOLE FIX.
    #
    # `protected` used to be read forty lines below, where rule 1 lives — so a
    # video the results DB skipped contributed no slot, `claimed` saw ONE owner
    # for a file two videos need, `shared` was empty, and rule 2 could not fire
    # for it. Measured on DEFAULT FLAGS: a settled `.mkv` and a newly-added
    # `.mp4` of one episode, and the `.mkv`'s only subtitle was retimed by
    # +5 s **in place** — destroyed, not trashed, nothing recoverable — in the
    # same run that reported `1 synced · 1 already in sync` and named that
    # video as already in sync. ⛔ And it never heals: afterwards both videos
    # are live, so rule 2 works perfectly and protects the corrupted file.
    #
    # ⭐ The 3b fix was extended to rule 1 BY NAME, and rule 2 has the identical
    # dependency on `slots`. **Any new way to make a video invisible to a run
    # re-arms both rules, not one.**
    _refuse_target_collisions(slots, out_dir, mirror_root, rename)

    answers = protected if answers is None else answers
    claimed = {}
    # 🚨 RULE 2 GETS THE SETTLED VIDEOS' **ANSWERS**, NOT EVERY FILE THEY WERE
    # OFFERED — and the two rules genuinely want different sets.
    #
    # ⛔ Seeded with every candidate, a settled video stood in as an owner of
    # its live NEIGHBOUR's own output — merely one of the files it was offered
    # — so rule 2 called that path shared, saw the live slot's target was that
    # same path (an ordinary in-place re-sync, because the output already
    # carries the video's name) and refused it. **Permanently**: the settled
    # twin's candidates never change, so it stays settled and the live one
    # stays refused, with the correction measured and never applied.
    #
    # ⭐ Rule 2's hazard is *my write mutates bytes another slot must still
    # READ*. A skipped video reads nothing this run — what it needs is that its
    # ANSWER is not overwritten, which is the file it had written. Rule 1's
    # hazard is different and wider: anything it was offered may not be
    # TRASHED, including a source that survived under `dedupe=False`. Two
    # hazards, two sets; conflating them cost a defect in each direction.
    for key, absent in _absent_owners(answers).items():
        claimed.setdefault(key, []).append(absent)
    for slot in slots:
        for candidate, _name in slot.writes:
            claimed.setdefault(_key(candidate.path), []).append(slot)

    # ⚠ DISTINCT slots, not entries. `--keep-all` puts several writes in one
    # slot, and counting entries would call a path shared with itself the
    # moment two of them ever named the same file.
    shared = set(k for k, owners in claimed.items()
                 if len(set(id(s) for s in owners)) > 1)
    for slot in slots:
        kept = []
        for candidate, name in slot.writes:
            source = _key(candidate.path)
            if source in shared:
                target = _key(os.path.join(
                    _out_dir_for(slot.video, slot.by_path[candidate.path],
                                 out_dir, mirror_root, rename), name))
                if target == source:
                    # ⚠ AN ABSENT OWNER NAMING THIS SLOT'S OWN VIDEO IS NOT
                    # ANOTHER CLAIMANT. Two rips with identical container bytes
                    # share a video digest, so a record written for one is
                    # offered to the other and its answer arrives looking
                    # foreign — which refused a live rip its own ordinary
                    # in-place re-sync, permanently.
                    others = [s for s in claimed[source]
                              if s is not slot
                              and _key(getattr(s, "video", u"")) != _key(slot.video)]
                    if not others:
                        kept.append((candidate, name))
                        continue
                    slot.notes.append(
                        u"⛔ %s is also the answer for %s, and writing it here "
                        u"would write OVER the file they still have to read — "
                        u"so their offsets would be applied to bytes this run "
                        u"had already shifted. The others are written "
                        u"normally; this one is not. Rename it, or pair it "
                        u"explicitly."
                        % (os.path.basename(candidate.path),
                           u", ".join(os.path.basename(s.video)
                                      for s in others[:3])))
                    # 🚨 RECORDED, NOT MERELY NOTED. A dropped write used to
                    # leave the slot with none at all, so `_perform_slot` took
                    # its no-winner branch, `expected_write` defaulted to False,
                    # and the result stayed CONFIDENT — making a `write=True`
                    # run byte-identical in its report to a dry run, which is
                    # the defect `SyncReport.failed` exists to end. The only
                    # trace was the sentence above.
                    slot.refused_writes.append((candidate, name))
                    continue
            kept.append((candidate, name))
        slot.writes = kept

    # ⭐ RULE 1. Anything some slot writes is that slot's, and every other slot
    # leaves it alone. ⚠ Computed AFTER the contested ones are dropped, so a
    # file nobody writes any more is not protected by a claim that no longer
    # exists.
    protected = set(protected)
    owned = set(protected)
    # ⚠ Rule 1 and rule 2 read DIFFERENT sets on purpose, and the reason is at
    # the top of this function. A caller that names only `protected` gets the
    # conservative reading — every candidate protected from both — which is
    # what the unit check passes and what a future caller will do by accident.
    # ⚠ Rule 1 and rule 2 now read the SAME absent owners. They were allowed to
    # disagree for exactly one session and it cost a user's file.
    for slot in slots:
        for candidate, _name in slot.writes:
            owned.add(_key(candidate.path))
    for slot in slots:
        kept = []
        for loser in slot.superseded:
            key = _key(loser.path)
            if key in owned:
                # ⚠ THE TWO SENTENCES ARE DIFFERENT FACTS. One says another
                # video is writing it now; the other says a video that was not
                # measured at all still owns it. A user reading the second one
                # under the first's wording would go looking for a run that is
                # not there.
                whose = (u"a video this run recognised as already in sync"
                         if key in protected else
                         u"another video in this run")
                slot.notes.append(u"%s was not trashed: it is the answer for %s"
                                  % (os.path.basename(loser.path), whose))
                continue
            kept.append(loser)
        slot.superseded = kept
    return slots


def _refuse_target_collisions(slots, out_dir, mirror_root, rename):
    u"""⛔ TWO SLOTS MAY NOT WRITE TO ONE PATH. Neither is written.

    ===========================================================================
    🚨 THERE IS NO OUTPUT NAME THAT SERVES BOTH, AND THAT IS WHY THIS REFUSES.
    ===========================================================================

    `05-interface.md` names the output `<video-basename>.<lang>.<ext>`,
    and the basename drops the container extension — so `Show S01E01.mkv`
    and `Show S01E01.mp4`, an ordinary re-download, both resolve to
    `Show S01E01.ja.srt`. Measured before this existed: `2 synced`,
    one video handed a subtitle **5 s wrong** and reported CONFIDENT · locked,
    and from the next run on rule 2 froze the wrong file in place for ever.

    ⭐ AND DISAMBIGUATING WOULD DEFEAT THE FEATURE. The whole point of renaming
    is that a player auto-loads a subtitle matching the video's basename — both
    players look for the same name, so `Show S01E01.mp4.ja.srt` is a name
    nothing loads. The clash is in the user's library, not in this code, and
    the only honest answers are *refuse both and say why* or *write one and be
    confidently wrong about the other*.

    ⚠ DISTINCT SLOTS, not entries — `--keep-all` writes several files
    from one slot under distinguishing tags, and `dedupe.plan` already
    refuses a collision within a slot.
    """
    wanted = {}
    for slot in slots:
        for candidate, name in slot.writes:
            target = _key(os.path.join(
                _out_dir_for(slot.video, slot.by_path[candidate.path],
                             out_dir, mirror_root, rename), name))
            wanted.setdefault(target, []).append((slot, candidate, name))

    for target, wanting in wanted.items():
        if len(set(id(s) for s, _c, _n in wanting)) < 2:
            continue
        refused = set()
        for slot, candidate, name in wanting:
            others = [s.video for s, _c, _n in wanting if s is not slot]
            slot.notes.append(
                u"⛔ %s and %s would both be written to %s, and one subtitle "
                u"cannot be two videos' answer — a player loads a subtitle "
                u"matching the video's basename, and these videos share one. "
                u"NEITHER was written. Rename one of the videos so their names "
                u"differ, or pair them explicitly."
                % (os.path.basename(slot.video),
                   u", ".join(os.path.basename(v) for v in others[:3]),
                   os.path.basename(name)))
            slot.refused_writes.append((candidate, name))
            refused.add((id(slot), _key(candidate.path), name))
        for slot in set(s for s, _c, _n in wanting):
            slot.writes = [(c, n) for c, n in slot.writes
                           if (id(slot), _key(c.path), n) not in refused]


class _AbsentOwner(object):
    u"""A video the results DB skipped, standing in for the slot it has not got.

    ⭐ `_resolve_ownership` counts DISTINCT owners by `id()`, so a settled
    video needs an object to BE one. It carries `.video` because the refusal
    sentence names the other claimants by video — and the honest answer there
    is the video that is already in sync, not a slot, which is exactly the
    thing it does not have.
    """

    __slots__ = ("video",)

    def __init__(self, video):
        self.video = video


def _absent_owners(protected):
    u"""Every file a skipped video still owns. -> {path key: _AbsentOwner}

    ⚠ Takes the mapping `Settled.protected` supplies, and tolerates a bare
    iterable of paths: a caller handing in a set gets owners named for the file
    instead of the video, which is worse prose and identical protection.
    """
    out = {}
    try:
        pairs = list(protected.items())
    except AttributeError:
        pairs = [(p, p) for p in protected]
    for path, video in pairs:
        out[_key(path)] = _AbsentOwner(video)
    return out


def _key(path):
    u"""The identity two paths share only when they are the same file.

    ⭐ The same `normcase(realpath(...))` `explicit._identity` and
    `discover.walk` use, so the three cannot disagree about whether they have
    seen a file.
    """
    return os.path.normcase(os.path.realpath(str(path)))


def _decide_video(video_path, measured, rename, dedupe, keep_all, explicit,
                  suffix=None):
    u"""Every slot this video has, PLANNED. ⛔ Performs nothing."""
    measured = list(measured)
    if not measured:
        return []
    video_stem = os.path.splitext(os.path.basename(video_path))[0]
    groups = {}
    for m in measured:
        groups.setdefault(m.sidecar.lang, []).append(m)
    out = []
    for lang in _ordered(m.sidecar.lang for m in measured):
        out.append(_decide_slot(video_path, video_stem, lang, groups[lang],
                                rename=rename, dedupe=dedupe,
                                keep_all=keep_all, explicit=explicit,
                                suffix=suffix))
    return out


def _decide_slot(video_path, video_stem, lang, group, rename, dedupe,
                 keep_all, explicit, suffix=None):
    u"""One (video x language) slot, PLANNED. -> `_Slot`

    ⛔ `dedupe.plan()` DECIDES. This function never picks a winner and never
    invents a name -- rule 1 is a gate there, `sidecar.output_name` is the one
    namer there, and both were mutation-proved at 3a.
    """
    # ⛔ `speculative` IS CARRIED, and this is the call whose output reaches
    # `dedupe.plan` -- the one place that decides what goes to the trash.
    candidates = [_dedupe.Candidate(m.subtitle, m.sidecar, verdict=m.verdict,
                                    cues=m.cue_count,
                                    content_end=m.content_end or 0.0,
                                    speculative=m.speculative)
                  for m in group]
    by_path = dict((m.subtitle, m) for m in group)
    collided = []
    try:
        plan = _dedupe.plan(video_stem, candidates, lang=lang,
                            keep_all=keep_all)
    except ValueError as exc:
        # 🚨 ONE SLOT'S IMPOSSIBLE NAMING MAY NOT ABANDON THE FOLDER.
        # `dedupe.plan` refuses to emit two writes to one path — correctly,
        # because that is data loss — but it does so by RAISING, two frames
        # above `apply_plan`, so `sync()` died with no `SyncReport` at all and
        # every later folder went unprocessed. Measured under `--keep-all` on a
        # third run, where two candidates hold identical bytes and the
        # distinguishing tag cannot tell them apart.
        # ⛔ `06-edge-cases.md` §7 rules per-pair atomicity: completed pairs
        # stay done, the interrupted one is untouched. The guard is kept and
        # the escalation is not. Found by two adversaries.
        plan = _dedupe.DedupePlan(
            video_stem, lang, winner=None, writes=[], superseded=[],
            notes=[u"%s Nothing was written for this slot; the rest of the "
                   u"run continues." % exc],
            reason=u"%s" % exc)
        # 🚨 AND IT IS A WITHHELD WRITE, NOT AN ABSENT ONE. These candidates
        # were decided and then refused; a slot that merely has no writes
        # reports as a plan, which would make this collision look like a dry
        # run on a run that was asked to write. Same defect F8 fixed, arriving
        # through this branch a few minutes later.
        collided = list(candidates)

    writes = list(plan.writes)
    superseded = list(plan.superseded)
    notes = list(plan.notes)

    if not writes:
        forced = _forced_write(video_stem, lang, group, plan)
        if forced is not None:
            writes, superseded = [forced], []
            # ⛔ NO NOTE HERE, AND THAT IS THE FIX RATHER THAN AN OMISSION.
            # Three layers each composed *"written under force"* on their own
            # judgement and the CLI printed all three in one block. Two of them
            # are right to: `explicit.Decision.reason` states the DECISION and
            # `apply` states that the bytes MOVED, and `_result_for` corrects
            # the first if they did not. This one said *"is written"* at PLAN
            # time — a claim about the future, which is the shape
            # `LEDGER-HOT.md` records being fixed once for `output_path` and
            # found again next door for `superseded`. Found by LOOKING at a
            # forced run at 3c.

    if explicit:
        # 🚨 THE USER ASSERTED EVERY ONE OF THESE PAIRS, so none of them is a
        # candidate that "lost" anything. Two explicit pairs for one
        # (video x language) used to collapse into a single Result and the
        # other file was TRASHED -- its verdict, reason and outcome never
        # reaching the caller at all. `03-permissions.md`: a refusal is *left
        # untouched, reason stated*. Found by an adversarial pass.
        # ⚠ Dedupe still decides which one is WRITTEN, because two writes to
        # one output name is data loss; it just no longer decides what is
        # thrown away.
        if superseded:
            notes.append(
                u"%d other pair%s you asserted for this slot %s left exactly "
                u"where they are; only one file can carry the video's name"
                % (len(superseded), u"" if len(superseded) == 1 else u"s",
                   u"is" if len(superseded) == 1 else u"are"))
        superseded = []

    if suffix:
        # ⭐ A COPY BESIDE THE ORIGINAL, named after the original. `sync()` has
        # already set `rename=False`, so the folder is the original's; only the
        # NAME differs from an in-place retime, which makes the target a new
        # file — `apply_plan`'s occupied-target check refuses to write over
        # anything already there that this run did not produce.
        writes = [(c, _sidecar.suffixed_name(os.path.basename(c.path), suffix))
                  for c, _n in writes]
    elif rename is False:
        # ⚠ `--rename` off writes back over the subtitle's OWN name, so the
        # namer is bypassed rather than reimplemented. `apply_plan` then sees
        # a target identical to the source, which it already handles as an
        # in-place retime and refuses to trash afterwards.
        writes = [(c, os.path.basename(c.path)) for c, _n in writes]
    if dedupe is False:
        # ⚠ Recorded, not silent: the losers stay where they are and the
        # result still names them, because *"nothing was trashed"* and
        # *"nothing lost"* are different claims.
        if superseded:
            notes.append(
                u"dedupe is off, so the %d candidate%s that lost this slot "
                u"stay%s exactly where they are"
                % (len(superseded), u"" if len(superseded) == 1 else u"s",
                   u"s" if len(superseded) == 1 else u""))
        superseded = []

    slot = _Slot(video_path, video_stem, lang, group, by_path, candidates,
                 plan, writes, superseded, notes, explicit)
    slot.refused_writes.extend((c, u"") for c in collided)
    return slot


def _perform_slot(slot, write, rename, out_dir, mirror_root, trash_root,
                  sender, force):
    u"""Carry out one planned slot. -> [`Result`]"""
    written_paths = set(_key(c.path) for c, _n in slot.writes)
    results = []

    for index, (candidate, name) in enumerate(slot.writes):
        m = slot.by_path[candidate.path]
        # ⚠ ONE `apply_plan` PER WRITE. `--keep-all` writes several files and
        # trashes nothing, so the per-file drop counts would otherwise be a
        # SUM attributed to whichever result was built first. In the ordinary
        # single-winner case this is byte-for-byte the same call.
        last = index == len(slot.writes) - 1
        one = _dedupe.DedupePlan(
            slot.stem, slot.lang, winner=candidate,
            writes=[(candidate, name)],
            superseded=slot.superseded if last else [],
            notes=[], reason=slot.plan.reason)
        report = apply_plan(one, trash_root,
                            out_dir=_out_dir_for(slot.video, m, out_dir,
                                                 mirror_root, rename),
                            dry_run=not write, sender=sender, force=force)
        results.append(_result_for(
            slot.video, m, outcome=_outcome_of(m), reason=_reason_of(m),
            report=report,
            # ⚠ WHAT ACTUALLY MOVED, never what the plan intended.
            superseded=[t.path for t in report.trashed if t.performed],
            notes=slot.notes + m.notes, expected_write=True))

    # ⭐ ON THE EXPLICIT PATH, EVERY PAIR THE USER ASSERTED GETS A RESULT.
    # Two pairs for one (video x language) used to collapse into a single one
    # and the other file was trashed -- its verdict, reason and outcome never
    # reaching the caller. The user named it; they get an answer about it.
    #
    # ⛔ AND NOT ON THE SCAN PATH, where the candidates are ours rather than
    # theirs. `05-interface.md`'s ruled output is one line per video, and a
    # video with twenty candidates would otherwise produce twenty lines for one
    # episode -- burying the refusals the format exists to surface. A candidate
    # that simply lost a fair fight is `superseded`, not a line.
    # ⚠ Found by reviewing this seam after fixing the explicit case: the fix
    # for one finding had quietly broken a property documented three functions
    # away.
    if slot.explicit:
        for m in slot.group:
            if _key(m.subtitle) in written_paths:
                continue
            results.append(_result_for(
                slot.video, m, outcome=_outcome_of(m),
                reason=_reason_of(m) or slot.plan.reason,
                superseded=[], notes=slot.notes + m.notes))
    elif not results:
        # ⭐ A SCAN SLOT WITH NO WINNER IS STILL A RESULT, NOT A SILENCE.
        # `dedupe.plan` never returns an empty reason here, and the best-ranked
        # candidate is named so the line points at a file to go and look at.
        #
        # 🚨 AND A SLOT WHOSE WRITES WERE REFUSED IS NOT A SLOT WITH NO WINNER.
        # Rule 2 withholds a write that was decided; the slot then arrived here
        # with `writes == []`, `expected_write` defaulted to False, the outcome
        # stayed CONFIDENT, and a `write=True` run became **byte-identical in
        # its report to a dry run** — same summary, same `confident`, same
        # empty `written`. The only trace was a note. That is the defect
        # `SyncReport.failed` was added to end, arriving through a door it did
        # not cover. Found by an adversarial pass.
        refused = slot.refused_writes
        best = (refused[0][0] if refused
                else _dedupe.rank(slot.candidates, slot.stem)[0])
        m = slot.by_path[best.path]
        results.append(_result_for(
            slot.video, m, outcome=_outcome_of(m),
            reason=_reason_of(m) or slot.plan.reason,
            superseded=[], notes=slot.notes + m.notes,
            withheld=(u"%s is also another video's answer and writing it here "
                      u"would destroy what they still have to read"
                      % os.path.basename(refused[0][0].path))
            if (refused and write) else None))
    return results


def _record_slot(store, slot, done, video_keys, before, shape=None):
    u"""Write this slot's completed syncs to the results DB. ⛔ Nothing else.

    ===========================================================================
    🚨 A RECORD IS A CLAIM THAT A FILE WITH THESE BYTES EXISTS, so it is minted
    from `Result.output_path` and nothing else.
    ===========================================================================

    `LEDGER-HOT.md`: *a report composed from the plan is not a report about
    what happened* -- found once for `output_path`, then again next door for
    `superseded`. Here the stakes are higher than a wrong sentence: the next
    run **acts** on this. A record written from the plan would make a dry run
    tell tomorrow's run that the work is done, and tomorrow's run would agree
    and skip it. `_result_for` sets `output_path` only when
    `report.performed and report.written`, which is exactly the condition, so
    this reads it rather than re-deriving it.

    ⛔ CONFIDENT ONLY, AND FORCED WRITES ARE DELIBERATELY LEFT OUT. A forced
    write is the most dangerous thing this tool does (`LEDGER.md` §Interface)
    and it is reported as REFUSED for that reason. Recording it would make the
    next ordinary run skip it in silence -- so the refusal is re-measured and
    re-stated every time, which is the behaviour a user who typed `--force`
    once should get.

    ⭐ `before` IS THE SLOT AS IT WAS WHEN THE PLAN WAS MADE, hashed by the
    caller before `_perform_slot` ran. It cannot be recomputed here: the losers
    are in the trash by now, and *what the plan was made from* is precisely
    what `Record.stable` compares against.
    """
    if store is None:
        return []

    # ⚠ NOTHING IS HASHED UNTIL THERE IS SOMETHING TO RECORD. A dry run
    # reaches here for every slot in the library and must cost nothing at all
    # -- and this is also the structural half of *a dry run records nothing*:
    # the loop below cannot write a record the filter above did not pass.
    recordable = [r for r in done
                  if r.output_path and r.outcome == CONFIDENT and not r.forced]
    if not recordable:
        return []

    key = video_keys.get(slot.video)
    if key is None:
        try:
            key = _results.content_key(slot.video)
        except (IOError, OSError):
            # 🚨 FAIL OPEN. No key, no record, and the work is simply
            # done again next run. Never an exception across a good write.
            return []
        video_keys[slot.video] = key

    # ⭐ THE WHOLE SLOT, from both sides. Each candidate is recorded with the
    # digest it had at plan time and with whether it is still there now, so
    # `Record.stable` and `Record.expected` can be answered separately.
    considered = []
    for candidate in slot.candidates:
        m = slot.by_path.get(candidate.path)
        ck = before.get(candidate.path) or before.get(str(candidate.path))
        if ck is None:
            try:
                ck = _results.subtitle_key(candidate.path)
            except (IOError, OSError):
                continue
        considered.append(_results.Considered(
            ck.digest, ck.size, candidate.path,
            _outcome_of(m) if m is not None else ERROR,
            survived=_still_there(candidate.path, ck)))

    written = []
    for r in recordable:
        try:
            out_key = _results.subtitle_key(r.output_path)
            src_key = _results.subtitle_key(r.subtitle)
        except (IOError, OSError):
            # 🚨 FAIL OPEN. A store that can break a run is worse than no
            # store (`cache.py` holds the same rule): if the file we just wrote
            # cannot be re-read, the honest outcome is no record and a re-align
            # next time -- never an exception thrown across a successful write.
            continue
        record = _results.Record(
            video_digest=key.digest, video_size=key.size,
            video_path=slot.video, lang=slot.lang, outcome=r.outcome,
            word=r.verdict_word, segments=r.segments,
            dropped_in_gap=r.dropped_in_gap,
            dropped_before_zero=r.dropped_before_zero,
            output_digest=out_key.digest, output_size=out_key.size,
            output_path=r.output_path,
            source_digest=src_key.digest, source_size=src_key.size,
            source_path=r.subtitle,
            considered=considered, shape=shape)
        try:
            written.append(store.record(record))
        except Exception as exc:
            # 🚨 FAIL OPEN, AND THIS LINE IS THE ONE THE DOCSTRING ABOVE
            # ALREADY PROMISED. Both `try` blocks above wrapped
            # `content_key`; `store.record` was called bare, and
            # `atomic_write_bytes` raises `PermissionError` on
            # Windows whenever anything else has the destination open — a
            # second run, an indexer, Defender scanning a file it just saw
            # created. Measured: `sync()` died mid-folder AFTER a write
            # had landed, so episode 1 was written, episodes 2 and 3 were never
            # performed, and no `SyncReport` said which half was done.
            # ⛔ *A store that can break a run is worse than no store* — the
            # rule `Results.get` has held since it was written.
            r.notes.append(
                u"the record of this sync could not be saved (%s), so the "
                u"next run will measure it again. The file itself is "
                u"written." % exc)
    return written


def _still_there(path, was):
    u"""Is this candidate still the file it was before the run? -> bool

    🚨 THE BYTES, NOT THE PATH. `os.path.exists` would call an IN-PLACE
    RETIME *"survived"* -- and an in-place retime is the one case where the
    file at that path is a different subtitle from the one the plan weighed.
    `LEDGER-HOT.md`: *a retime is length-preserving*, so even a size check is
    blind to it. Recording the old digest as a survivor would tell the next run
    to expect bytes that are not there, and it would work for ever.
    """
    try:
        return _results.subtitle_key(path).digest == was.digest
    except (IOError, OSError):
        return False


def _mirror_root(video_paths):
    u"""The ancestor `--out` mirrors against. -> a directory, or None

    ⚠ `commonpath` RAISES across drives and UNC shares -- the same trap
    `discover.proximity` records. Here the honest answer to *"these videos have
    no common ancestor"* is that `--out` cannot mirror them, which the caller
    turns into a refusal rather than a silent flatten.
    """
    dirs = sorted(set(os.path.dirname(os.path.abspath(p))
                      for p in video_paths))
    if not dirs:
        return None
    if len(dirs) == 1:
        return dirs[0]
    try:
        return os.path.commonpath(dirs)
    except ValueError:
        return None


def _out_dir_for(video_path, m, out_dir, mirror_root, rename):
    u"""Where the written subtitle goes. -> a directory

    🚨 `--out` MIRRORS, IT DOES NOT FLATTEN, and `sync()` is the layer that has
    to make that true. `apply_plan`'s own docstring says so and names the
    reason -- *"flattening collides the moment two shows both have an ep01;
    mirroring is the caller's job because only it knows the library root"* --
    and this function returned `out_dir` verbatim. Measured:

        Alpha/Season 1/01.mkv  ->  out/01.ja.srt
        Bravo/Season 1/01.mkv  ->  (blocked, target occupied)
        out/ holds ONE file for two episodes, and the second reported CONFIDENT

    ⛔ And the check named for the rule could not fail: it asserted
    `dirname(output_path) == out_dir` on a ONE-video fixture, which is exactly
    what flattening looks like. Found by an adversarial pass.

    🚨 BESIDE THE VIDEO, NOT BESIDE THE SUBTITLE, AND THAT IS THE WHOLE POINT
    OF RENAMING. `05-interface.md`: *media players auto-load a subtitle
    matching the video's basename* -- which requires it to be **in the video's
    folder**. `apply_plan` defaults to *the source's own folder*, which is
    right for a function that knows nothing about videos and wrong here.

    ⛔ Measured before this existed, in surasura's own two-folder shape: a
    perfectly retimed `Show S01E01.ja.srt` was written into the DOWNLOADS
    folder, beside the `.txt` junk, where no player will ever look. The tool
    did the renaming exactly right and achieved nothing.
    ⚠ It survived a check that asserted the new files by BASENAME -- shape
    without substance (`doctrine/verification`). Ask the second question:
    *and is it where it has to be?*

    ⭐ `rename=False` is the exception and keeps the subtitle's own folder,
    because that flag means *do not touch the name* -- an in-place retime. A
    file put beside the video under its own release-group name would be
    neither renamed nor in place.
    """
    if out_dir:
        here = os.path.dirname(os.path.abspath(video_path))
        if not mirror_root:
            return out_dir
        try:
            below = os.path.relpath(here, mirror_root)
        except ValueError:
            return out_dir
        if below in (os.curdir, u""):
            return out_dir
        return os.path.join(out_dir, below)
    if rename is False:
        return os.path.dirname(m.subtitle)
    return os.path.dirname(video_path)


def _forced_write(video_stem, lang, group, plan):
    u"""The one write `--force` authorises when the verdict refused it.

    🚨 THIS IS THE ONLY PLACE A NAME IS BUILT OUTSIDE `dedupe.plan`, and the
    reason is structural: rule 1 there is a GATE -- *a refused candidate never
    wins* -- so a forced pair can never come back as a winner, by design. It
    must not: on the discovery path that gate is what stops the best of
    several refused files being written, and `sync()` refuses `force=True` on
    a `Scan` for exactly that reason.

    ⛔ So this runs only where the user asserted the pair AND typed the
    override, and it uses `sidecar.output_name` -- the same namer -- rather
    than inventing one.
    """
    authorised = [m for m in group
                  if m.decision is not None and m.decision.write]
    if not authorised:
        return None
    order = {c.path: i for i, c in
             enumerate(_dedupe.rank([_dedupe.Candidate(m.subtitle, m.sidecar,
                                                       verdict=m.verdict,
                                                       cues=m.cue_count)
                                     for m in group], video_stem))}
    authorised.sort(key=lambda m: order.get(m.subtitle, len(order)))
    m = authorised[0]
    name, _notes = _sidecar.output_name(video_stem, lang, m.sidecar.ext,
                                        flags=m.sidecar.flags)
    return (_dedupe.Candidate(m.subtitle, m.sidecar, verdict=m.verdict,
                              cues=m.cue_count,
                              content_end=m.content_end or 0.0), name)


def _outcome_of(m):
    u"""⚠ THE DECISION OUTRANKS THE VERDICT WHERE ONE EXISTS, and a forced
    write still reports REFUSED. `LEDGER.md` §Interface: a forced write is the
    most dangerous thing this tool does and it may never be relabelled a
    success."""
    if m.decision is not None:
        return m.decision.outcome
    if m.verdict is not None:
        return m.verdict.outcome
    return m.rejection[0]


def _reason_of(m):
    if m.decision is not None:
        return m.decision.reason
    if m.verdict is not None:
        return m.verdict.reason
    return m.rejection[1]


def _episode_number(path):
    u"""The episode this video is, as an int, or None. ⚠ Never a string:
    padding it is the caller's decision and this object should not have one.

    ⚠ No video, no episode: `sync_to_reference` measures a subtitle against
    another subtitle and there is no video path to read one from.
    """
    if not path:
        return None
    got = _episode_of(path)
    number = getattr(got, "episode", None) if got is not None else None
    return number if isinstance(number, int) else None


def _result_for(video_path, m, outcome, reason, report=None, superseded=(),
                notes=(), expected_write=False, withheld=None):
    u"""One `Result`, built in ONE place. -> `api.Result`

    🚨 `output_path` IS SET ONLY WHEN A FILE ACTUALLY MOVED. `apply_plan` fills
    `report.written` in a dry run too -- that list is *what it would write* --
    so reading it without checking `report.performed` makes every dry run
    claim it wrote the folder.
    """
    v = m.verdict
    written = None
    if report is not None and report.performed and report.written:
        written = report.written[0][1]
    notes = list(notes)
    if report is not None:
        notes.extend(report.notes)
        notes.extend(u"%s: %s" % (os.path.basename(p), why)
                     for p, why in report.errors)

    # 🚨 A REASON THAT SAYS "WRITTEN" WHEN NOTHING WAS WRITTEN IS A
    # CONFIDENTLY WRONG REPORT -- worse than the missing write, because the
    # user stops looking. `Decision.reason` is composed by A11 *before* the
    # attempt ("WRITTEN UNDER --force. The pairing was accepted; the alignment
    # was NOT"), so on a dry run, or on a write that failed, it is a claim
    # about something that did not happen.
    # ⭐ Corrected here rather than in `explicit.py`: A11 decides, and only
    # this layer knows whether the bytes moved.
    #
    # 🚨 AND IT IS NO LONGER GATED ON `m.decision`, WHICH IS SET ONLY ON THE
    # EXPLICIT PATH. On a scan a failed write produced a CONFIDENT result with
    # an EMPTY reason, and `summary()` said *"1 would sync"* — so a `write=True`
    # run whose every write failed was **byte-identical in its report to a dry
    # run**. Found by an adversarial pass; the two paths are now symmetric.
    write_failed = False
    if withheld:
        # 🚨 WITHHELD IS NOT A DRY RUN, AND NOT AN ATTEMPT THAT FAILED. Rule 2
        # decided this write and then refused to carry it out, because the
        # target is a file another video still has to read. `report` is None
        # here — nothing was ever handed to `apply_plan` — and inferring *dry
        # run* from that made a `write=True` run **byte-identical in its
        # report to a dry run**: same summary, same `confident`, same empty
        # `written`. Only the caller knows which of the three happened.
        reason = u"⛔ NOT WRITTEN: %s%s" % (
            withheld, u" — %s" % reason if reason else u"")
        write_failed = True
    elif expected_write and written is None:
        if report is not None and report.performed:
            failure = u"; ".join(why for _p, why in report.errors) or \
                u"nothing was written and no reason was recorded"
            reason = u"⛔ NOT WRITTEN: %s%s" % (
                failure, u" — %s" % reason if reason else u"")
            write_failed = True
        else:
            reason = (u"(dry run — nothing was written)%s"
                      % (u" %s" % reason if reason else u""))
    return _api.Result(
        video_path, m.subtitle, outcome,
        reason=reason,
        segments=(v.segments if v is not None else ()),
        match_rate=(v.match_rate if v is not None else 0.0),
        excess_over_chance=(v.excess if v is not None else 0.0),
        raw_excess=(v.raw_excess if v is not None else 0.0),
        verdict_word=(v.word if v is not None and outcome == CONFIDENT
                      else None),
        holds_throughout=(v.holds_throughout if v is not None else True),
        runtime_check=(v.runtime_check if v is not None else u"absent"),
        cluster_coherence=m.cluster_coherence,
        dropped_in_gap=(report.dropped_in_gap if report is not None else 0),
        dropped_before_zero=(report.dropped_before_zero
                             if report is not None else 0),
        reference_kind=(v.reference_kind if v is not None else TEXT_TRACK),
        reference=(m.reference.description if m.reference is not None
                   else u""),
        output_path=written,
        superseded=superseded,
        lang=(m.sidecar.lang if m.sidecar is not None else None),
        lang_tag=(m.sidecar.tag if m.sidecar is not None else u""),
        # 🚨 `forced` MARKS THE PAIR THAT WAS ACTUALLY OVERRIDDEN, not every
        # pair in a run that passed the flag. `explicit.Decision` sets
        # `forced=bool(force)` on every decision it mints -- correctly, it
        # records how it was called -- so reading it alone made all fifty pairs
        # of a `--force` manifest report `forced=True` and the summary lead
        # `50 FORCED`. ⛔ The marker for the most dangerous thing this tool does
        # then no longer identifies WHICH file it happened to. Found by an
        # adversarial pass.
        # ⭐ A force only did something when the verdict was REFUSED and the
        # write went ahead anyway; on a CONFIDENT pair the flag changed nothing.
        forced=bool(m.decision is not None and m.decision.forced
                    and m.decision.write
                    and m.decision.outcome == REFUSED),
        write_failed=write_failed,
        # ⭐ FROM THE VIDEO, and from the same `_episode_of` the cluster keys
        # use. `05-interface.md`'s ruled output has an episode column, and a
        # consumer that re-parsed the filename to fill it would be a second
        # answer to a question this run has already settled.
        episode=_episode_number(m.video),
        notes=notes)


__all__ = ["Reference", "SyncReport", "sync", "reference_for", "measure",
           "clusters_for", "judge"]
