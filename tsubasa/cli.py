# -*- coding: utf-8 -*-
u"""
The command line. RUNBOOK step 3c. Authority: `05-interface.md` §*The CLI
output — RULED, do not redesign*.

===========================================================================
⛔ THIS MODULE DECIDES NOTHING.
===========================================================================

`05-interface.md`: *the importable API is the product; the CLI is a thin
wrapper over it.* Every outcome, every confidence word, every reason and every
count on the screen below was produced by `sync()` and is **read** here, never
recomputed. ⚠ The moment this file contains a threshold, a ranking rule or a
second opinion about what a run meant, there are two answers to the same
question and the library's is no longer the product.

---------------------------------------------------------------------------
🚨 NO POSITIVE WORD MAY PRECEDE A PROBLEM
---------------------------------------------------------------------------

`LEDGER.md` §Interface: a GUI painted a run containing refusals **green**,
because *"11 confident, 1 refused"* contains the word `confident` and the bare
word was being matched — on the one line a user reads at a glance. So:

  * refusals and errors are printed **first**, above the successes;
  * the summary line is `SyncReport.summary()`, which already leads with what
    is wrong and is checked where it lives. ⛔ Not reimplemented here.

---------------------------------------------------------------------------
⚠ COLUMNS ARE MEASURED IN DISPLAY WIDTH, NOT IN CHARACTERS
---------------------------------------------------------------------------

The ruled output aligns `old → new` in columns, and its own worked example is
`片田舎のおっさん S02E01.ass`. A CJK character occupies **two** cells in every
terminal that renders it, so `"%-30s" % name` misaligns every Japanese line in
the file — which is most of them, for this tool. `_width` and `_pad` below are
the whole fix and they exist for that reason.
"""
import io
import json
import os
import sys
import time
import unicodedata

from . import api as _api
from . import pipeline as _pipeline
from .verdict import CONFIDENT, ERROR, REFUSED

USAGE = u"""\
tsubasa — pair subtitles to videos and retime them to match.

  tsubasa <folder>                        subtitles beside the videos
  tsubasa <folder> --subs <folder>        videos and subtitles apart
  tsubasa --pair VIDEO SUBTITLE           one pair, named explicitly
  tsubasa --pairs pairs.json              a manifest of pairs

Options
  --subs DIR         where the subtitles are, when not beside the videos
  --out DIR          write the results here instead, mirroring the library
  --no-recurse       do not descend into sub-folders
  --no-rename        retime in place; keep each file's own name
  --suffix TEXT      write a retimed COPY beside each original, named after it:
                     --suffix _rt gives Show - 01_rt.ja.srt. Changes nothing else
  --keep-all         write every candidate; supersede nothing
  --pair V S         an explicit pair. Repeatable
  --pairs FILE       a JSON manifest: [["video", "subtitle"], ...]
  --force            write a pair the timing REFUSED. Explicit pairs only
  --dry-run          print every intended action; write and trash nothing
  --json             NDJSON, one object per result — the library's own shape
  --verbose          add the raw multiples, the chance level and the reference
  --no-results       ignore and do not update the record of what was synced
  -h, --help         this
"""

#: ⚠ `sync()` DEFAULTS TO `write=False` AND THIS DEFAULTS TO WRITING, and the
#: difference is deliberate rather than an inconsistency.
#:
#: A library call that forgets an argument must not move a user's bytes, so
#: `doctrine/robustness` makes the API dry by default. A CLI is a different
#: actor: the person typed the command and named the folder. And
#: `05-interface.md` rules `--dry-run` as a MODE — *"every intended action
#: printed, nothing written, nothing trashed"* — which is not a flag a tool can
#: offer if it already describes the default. Its ruled output block ends
#: `23 synced` and `2 subtitles superseded → trash`; that is a run that wrote.
#:
#: ⛔ The safety property is not the default, it is `03-permissions.md`: nothing
#: this tool does is unrecoverable. Losers go to the trash, never to deletion.
WRITES_BY_DEFAULT = True

_MARK = {CONFIDENT: u"✓", REFUSED: u"✗", ERROR: u"✗"}


# ---------------------------------------------------------------------------
# display width
# ---------------------------------------------------------------------------

def _width(text):
    u"""How many terminal cells `text` occupies. -> int

    ⚠ NOT `len()`. East-Asian Wide and Fullwidth characters take two cells, and
    this tool's own ruled example is a Japanese filename. Combining marks take
    none — a decomposed dakuten would otherwise widen a column that does not
    move on screen.
    """
    total = 0
    for ch in text:
        if unicodedata.combining(ch):
            continue
        total += 2 if unicodedata.east_asian_width(ch) in (u"W", u"F") else 1
    return total


def _pad(text, cells):
    u"""Left-justify `text` to `cells` display columns."""
    return text + u" " * max(0, cells - _width(text))


def _clip(text, cells):
    u"""Shorten `text` to `cells` display columns, with an ellipsis.

    ⚠ Clipped from the MIDDLE. A release name's distinguishing part is its
    episode and its group, which sit at opposite ends — cutting the tail leaves
    twenty files all reading `[SubsPlease] Some Very Long Show Ti…`.
    """
    if _width(text) <= cells:
        return text
    if cells <= 1:
        return u"…"[:cells]
    keep = cells - 1
    head_cells = keep - keep // 2
    head, seen = [], 0
    for ch in text:
        w = _width(ch)
        if seen + w > head_cells:
            break
        head.append(ch)
        seen += w
    tail, seen = [], 0
    for ch in reversed(text):
        w = _width(ch)
        if seen + w > keep - head_cells:
            break
        tail.append(ch)
        seen += w
    return u"".join(head) + u"…" + u"".join(reversed(tail))


# ---------------------------------------------------------------------------
# the pieces of a line
# ---------------------------------------------------------------------------

def _clock(seconds):
    u"""`3:18` — the split time in the ruled cut line."""
    seconds = int(round(seconds))
    return u"%d:%02d" % (seconds // 60, seconds % 60)


def _offsets(result):
    u"""`+0.13s`, or `-33.07 / -42.96 @3:18   CUT 9.9s` for a cut file.

    ⛔ READ FROM `Result.segments`, never recomputed. `05-interface.md`'s ruled
    line shows the offset per split and the size of the jump between them —
    `12-alignment.md` calls a cut two stretches with a boundary, and both
    numbers are what the user checks against their player.
    """
    segments = list(result.segments)
    if not segments:
        return u""
    if len(segments) == 1:
        # ⚠ NEGATIVE ZERO. A second run over its own output aligns at about
        # -1e-9, and `%+.2f` renders that as `-0.00` — a small negative shift,
        # on the one line that means NOTHING MOVED.
        # ⛔ `x + 0.0 or 0.0` does NOT fix it: that catches an exact -0.0 and
        # -1e-9 is truthy. Round to what will be SHOWN, then decide.
        return u"%+.2fs" % _shown(segments[0][1])

    line = u" / ".join(u"%+.2f" % _shown(off) for _split, off in segments)
    split = next((s for s, _o in segments if s is not None), None)
    if split is not None:
        line += u" @%s" % _clock(split)
    # ⚠ The GAP, not an offset: what the video does not carry. It is the
    # difference between consecutive offsets, and `05-interface.md`'s example
    # (`-33.07 / -42.96` → `CUT 9.9s`) is exactly that subtraction.
    jump = max(abs(segments[i + 1][1] - segments[i][1])
               for i in range(len(segments) - 1))
    return u"%s   CUT %.1fs" % (line, jump)


def _shown(offset):
    u"""The offset as it will be PRINTED, with negative zero normalised away."""
    return 0.0 if abs(round(offset, 2)) < 0.005 else offset


def _evidence(result):
    u"""`96% match · locked · holds throughout`

    ⛔ EVERY PART IS READ OFF THE `Result`. `05-interface.md`: *evidence on
    every line — never a bare tick.* ⚠ And a refusal carries NO confidence
    word (`LEDGER.md` §Interface); `Result` raises if one is set, so there is
    nothing to filter here.
    """
    parts = [u"%d%% match" % result.match_percent]
    if result.verdict_word:
        parts.append(result.verdict_word)
    if len(result.segments) > 1:
        parts.append(u"%d segments" % len(result.segments))
    elif result.holds_throughout and result.runtime_check == u"held":
        parts.append(u"holds throughout")
    elif result.runtime_check == u"absent":
        # ⚠ `holds_throughout` is True when every bucket was too thin to
        # SPEAK, and saying *holds throughout* there is a claim nothing
        # measured. `Result.runtime_check` is the only field that tells the
        # two apart, which is why it exists.
        parts.append(u"runtime unchecked")
    elif result.runtime_check == u"weak":
        parts.append(u"runtime check weak")
    # ⭐ `05-interface.md`, `D9`: cues removed under it are *dropped, COUNTED,
    # and reported on the result line*. This is the result line.
    # ⛔ The COUNT only. `apply` already puts a full sentence in
    # `Result.notes` saying what a dropped cue was, and a separate line here
    # made the report say *"1 cue dropped"* twice in a row.
    dropped = result.dropped_in_gap + result.dropped_before_zero
    if dropped:
        parts.append(u"%d cue%s dropped"
                     % (dropped, u"" if dropped == 1 else u"s"))
    return u" · ".join(parts)


def _detail(result):
    u"""What `--verbose` adds, on its OWN line.

    ⚠ Appended to the evidence line first, and measured at **over 150 cells**
    on a real run — past the edge of every terminal, so the part a bug report
    needs was the part that scrolled off. `05-interface.md` rules the raw
    multiple out of the default output and into here; it is no use if it is
    unreadable when it arrives.
    """
    parts = [u"%.2f× chance" % result.raw_excess]
    if result.excess_over_chance != result.raw_excess:
        # ⭐ ZEROED means the input was too thin to mean anything, and the
        # difference between the two numbers IS the finding.
        parts.append(u"scored as %.2f× (too thin to count)"
                     % result.excess_over_chance)
    if result.cluster_coherence is not None:
        parts.append(u"cluster %.2f" % result.cluster_coherence)
    if result.lang:
        parts.append(u"lang %s" % result.lang)
    if result.reference:
        parts.append(result.reference)
    return u" · ".join(parts)


def _wrap(text, width, indent):
    u"""Fold a reason to `width` cells, every line prefixed with `indent`."""
    out, line = [], []
    for word in text.split():
        trial = u" ".join(line + [word])
        if line and _width(trial) > width:
            out.append(indent + u" ".join(line))
            line = [word]
        else:
            line.append(word)
    if line:
        out.append(indent + u" ".join(line))
    return out


# ---------------------------------------------------------------------------
# the report
# ---------------------------------------------------------------------------

#: The `old → new` columns. ⚠ Display cells, not characters.
NAME_CELLS = 34
NEW_CELLS = 32
BODY = u"          "
#: The width the ruled block is drawn to. `05-interface.md`'s own example runs
#: to 78 columns, which is the width every terminal has.
LINE = 78


def render(report, root=None, scan=None, elapsed=None, verbose=False):
    u"""The ruled output, as a list of lines. -> [unicode]

    🚨 REFUSALS AND ERRORS FIRST. `05-interface.md`: *the one thing needing
    attention must not sit below 23 successes.* That ordering is the property,
    not a preference, and it is asserted rather than described.
    """
    lines = []

    lines.append(_header(root, scan))
    lines.append(u"")

    bad = [r for r in report if r.outcome != CONFIDENT]
    good = [r for r in report if r.outcome == CONFIDENT]

    for result in bad:
        lines.extend(_result_lines(result, verbose))
    if bad and good:
        lines.append(u"")
    for result in good:
        lines.extend(_result_lines(result, verbose))

    _blank(lines)
    for path, why in report.unpaired:
        # ⚠ NO EPISODE COLUMN HERE. An unpaired video is not a `Result` —
        # `03-permissions.md` says there is no fourth outcome — so nothing has
        # parsed it, and parsing it in the renderer is exactly the second
        # answer this file is not allowed to hold.
        lines.append(u"  ·      %s"
                     % _clip(os.path.basename(path), NAME_CELLS))
        lines.extend(_wrap(why, 62, BODY))

    # ⭐ SETTLED VIDEOS ARE SAID OUT LOUD (RUNBOOK 3a-bis). A run that printed
    # nothing over a folder of finished episodes is indistinguishable from one
    # that broke, and the user goes looking.
    if report.settled:
        _blank(lines)
        lines.append(u"  %d already in sync — nothing to do"
                     % len(report.settled))
        if verbose:
            for path, why in report.settled:
                lines.extend(_wrap(u"%s: %s" % (os.path.basename(path), why),
                                   62, BODY))

    moved = sum(len(r.superseded) for r in report)
    if moved:
        _blank(lines)
        lines.append(u"  %d subtitle%s superseded → trash"
                     % (moved, u"" if moved == 1 else u"s"))

    _blank(lines)
    tail = report.summary()
    if elapsed is not None:
        tail += u" · %.1f s" % elapsed
    lines.append(u"  " + tail)
    return lines


def _blank(lines):
    u"""One blank line between sections, never two. ⚠ A run that produced no
    result lines at all had a section separator with nothing before it."""
    if lines and lines[-1] != u"":
        lines.append(u"")


def _header(root, scan):
    u"""`tsubasa  <root>` on the left, `24 videos · 26 subtitles` on the right.

    ⚠ CLIPPED FROM THE LEFT, which is the opposite of everywhere else in this
    file. A filename's distinguishing part is its middle; a PATH's is its tail
    — `…/Anime/Katainaka S2` says everything and `C:\\Users\\…` says nothing.
    Measured on a real run: the temp-directory path alone was 62 cells and
    pushed the counts to column 100.
    """
    right = scan.summary() if scan is not None else u""
    room = LINE - _width(u"tsubasa  ") - _width(right) - 2
    shown = root or u""
    if shown and _width(shown) > room:
        kept, seen = [], 0
        for ch in reversed(shown):
            w = _width(ch)
            if seen + w > room - 1:
                break
            kept.append(ch)
            seen += w
        shown = u"…" + u"".join(reversed(kept))
    left = u"tsubasa" + (u"  " + shown if shown else u"")
    if not right:
        return left
    return left + u" " * max(2, LINE - _width(left) - _width(right)) + right


def _result_lines(result, verbose):
    u"""One result, as the ruled two- or three-line block."""
    mark = _MARK.get(result.outcome, u"·")
    # ⚑ A CUT FILE IS ITS OWN MARK in the ruled output: it succeeded, and it
    # succeeded by doing something the user should know about.
    if result.outcome == CONFIDENT and len(result.segments) > 1:
        mark = u"⚑"
    # ⭐ `Result.episode` is an int or None. The WIDTH of the column is a
    # display decision and belongs here; the number is not and does not.
    episode = u"%02d" % result.episode if result.episode is not None else u"  "
    name = os.path.basename(result.subtitle) if result.subtitle \
        else os.path.basename(result.video)

    out = []
    if result.outcome == CONFIDENT:
        # ⭐ `old → new`, which `05-interface.md` makes load-bearing: *the user
        # sees what happened to their folder before trusting it.*
        # ⚠ `output_path` is set ONLY when a file actually moved, so a dry run
        # correctly shows no arrow — and says so on the summary line.
        written = os.path.basename(result.output_path or u"")
        if result.output_path and written != name:
            out.append(u"  %s  %s   %s  →  %s"
                       % (mark, _pad(episode, 2), _pad(_clip(name, NAME_CELLS),
                                                       NAME_CELLS),
                          _clip(written, NEW_CELLS)))
        elif result.output_path:
            # ⭐ THE NAME DID NOT CHANGE, so an arrow pointing at itself is
            # noise on the line whose job is *the user sees what happened to
            # their folder*. It was retimed where it sits.
            out.append(u"  %s  %s   %s   (retimed in place)"
                       % (mark, _pad(episode, 2), _clip(name, NAME_CELLS)))
        else:
            out.append(u"  %s  %s   %s"
                       % (mark, _pad(episode, 2), _clip(name, NAME_CELLS)))
        evidence = _evidence(result)
        offsets = _offsets(result)
        if len(result.segments) > 1:
            out.append(BODY + offsets)
            out.append(BODY + u"                " + evidence)
        else:
            out.append(BODY + _pad(offsets, 16) + evidence)
    else:
        # ⚠ THE SEPARATOR IS PART OF THE FORMAT, not part of the padding. A
        # name that clipped to exactly the column width printed
        # `...HEVC AAC).srtREFUSED` — `_pad` adds nothing when the text
        # already fills the column, so the gap has to be its own.
        out.append(u"  %s  %s   %s  %s"
                   % (mark, _pad(episode, 2),
                      _pad(_clip(name, NAME_CELLS + 10), NAME_CELLS + 10),
                      result.outcome))
        out.extend(_wrap(result.reason, 62, BODY))

    if verbose:
        out.extend(_wrap(_detail(result), 62, BODY))
    # ⛔ THE COUNT ONLY. `05-interface.md` rules that a `D9` drop is *counted
    # and reported on the result line*, and `apply` already puts a full
    # sentence in `Result.notes` explaining what a dropped cue WAS. Printing
    # both said the same thing twice, and the first version said *"1 cue ...
    # were dropped"* — the noun pluralised and the verb did not.
    for note in result.notes:
        out.extend(_wrap(note, 62, BODY))
    return out


# ---------------------------------------------------------------------------
# --json
# ---------------------------------------------------------------------------

def as_json(result):
    u"""One result as the library's own shape. -> dict

    `05-interface.md`: *the same structure the library returns, NDJSON per
    pair.* ⚠ Every field `Result` carries, including the ones the human output
    deliberately leaves out — `raw_excess` is what a bug report needs and what
    the default output may never show.
    """
    return {
        u"video": result.video,
        u"subtitle": result.subtitle,
        u"outcome": result.outcome,
        u"reason": result.reason,
        u"segments": [[s, o] for s, o in result.segments],
        u"offset": result.offset,
        u"match_rate": result.match_rate,
        u"match_percent": result.match_percent,
        u"excess_over_chance": result.excess_over_chance,
        u"raw_excess": result.raw_excess,
        u"verdict_word": result.verdict_word,
        u"holds_throughout": result.holds_throughout,
        u"runtime_check": result.runtime_check,
        u"cluster_coherence": result.cluster_coherence,
        u"dropped_in_gap": result.dropped_in_gap,
        u"dropped_before_zero": result.dropped_before_zero,
        u"reference_kind": result.reference_kind,
        u"reference": result.reference,
        u"output_path": result.output_path,
        u"superseded": list(result.superseded),
        u"lang": result.lang,
        u"lang_tag": result.lang_tag,
        u"forced": result.forced,
        u"write_failed": result.write_failed,
        u"episode": result.episode,
        u"notes": list(result.notes),
    }


# ---------------------------------------------------------------------------
# arguments
# ---------------------------------------------------------------------------

class Usage(Exception):
    u"""A command that cannot be run as typed. ⛔ Never a traceback.

    `doctrine/architecture`: *instruction, not refusal* — every message this
    carries names what would make the command work.
    """


def parse(argv):
    u"""-> a dict of options. ⛔ Hand-rolled, and that is deliberate.

    ⚠ `argparse` cannot express `--pair V S` repeatably without `nargs=2` plus
    `action="append"`, which it then reports with its own vocabulary — and this
    tool's refusals are written to `03-permissions.md` §hand-back: *state what
    was measured, why it fell short, and what would change it.* Forty lines of
    parsing keeps every message ours.
    """
    opts = {
        u"roots": [], u"subs": None, u"out": None, u"recurse": True,
        u"rename": True, u"suffix": None,
        u"keep_all": False, u"pairs": [], u"force": False,
        u"dry_run": False, u"json": False, u"verbose": False,
        u"results": True, u"help": False,
    }
    rest = list(argv)
    while rest:
        arg = rest.pop(0)
        if arg in (u"-h", u"--help"):
            opts[u"help"] = True
        elif arg == u"--subs":
            opts[u"subs"] = _value(rest, arg)
        elif arg == u"--out":
            opts[u"out"] = _value(rest, arg)
        elif arg == u"--no-recurse":
            opts[u"recurse"] = False
        elif arg == u"--no-rename":
            opts[u"rename"] = False
        elif arg == u"--suffix":
            opts[u"suffix"] = _value(rest, arg)
        elif arg == u"--keep-all":
            opts[u"keep_all"] = True
        elif arg == u"--force":
            opts[u"force"] = True
        elif arg == u"--dry-run":
            opts[u"dry_run"] = True
        elif arg == u"--json":
            opts[u"json"] = True
        elif arg == u"--verbose":
            opts[u"verbose"] = True
        elif arg == u"--no-results":
            opts[u"results"] = False
        elif arg == u"--pair":
            video = _value(rest, arg)
            if not rest or rest[0].startswith(u"--"):
                raise Usage(u"--pair takes TWO paths, a video and a subtitle: "
                            u"--pair VIDEO SUBTITLE. Got only %r." % video)
            opts[u"pairs"].append((video, rest.pop(0)))
        elif arg == u"--pairs":
            opts[u"pairs"].extend(_manifest(_value(rest, arg)))
        elif arg.startswith(u"-"):
            raise Usage(u"%s is not an option this tool has. Run "
                        u"`tsubasa --help` for the list." % arg)
        else:
            opts[u"roots"].append(arg)
    return opts


def _value(rest, flag):
    if not rest or rest[0].startswith(u"--"):
        raise Usage(u"%s needs a value after it." % flag)
    return rest.pop(0)


def _manifest(path):
    u"""`[["video", "subtitle"], ...]` -> [(video, subtitle)]

    ⛔ EVERY SHAPE ERROR IS NAMED. A manifest is typed by hand or generated by
    somebody else's script, and *"list index out of range"* three frames down
    tells the user nothing about which entry is wrong.
    """
    try:
        with io.open(path, u"r", encoding=u"utf-8") as fh:
            loaded = json.load(fh)
    except (IOError, OSError) as exc:
        raise Usage(u"--pairs could not read the manifest: %s" % exc)
    except ValueError as exc:
        raise Usage(u"--pairs expects JSON and %s is not valid JSON: %s"
                    % (path, exc))
    if not isinstance(loaded, list):
        raise Usage(u"--pairs expects a JSON list of [video, subtitle] pairs; "
                    u"%s holds %s." % (path, type(loaded).__name__))
    out = []
    for i, entry in enumerate(loaded):
        if not isinstance(entry, (list, tuple)) or len(entry) != 2:
            raise Usage(u"--pairs entry %d of %s is not a [video, subtitle] "
                        u"pair: %r" % (i + 1, path, entry))
        out.append((entry[0], entry[1]))
    return out


# ---------------------------------------------------------------------------
# the run
# ---------------------------------------------------------------------------

def main(argv=None, out=None, err=None):
    u"""-> an exit code.

    | Code | Meaning |
    | --- | --- |
    | 0 | every pair this run decided is written, or would be |
    | 1 | something was REFUSED, ERRORED, or failed to write |
    | 2 | the command could not be run as typed |

    🚨 A REFUSAL IS A NON-ZERO EXIT. It is the whole point of the tool that it
    declines to produce a confidently wrong file, and a script that pipes this
    into something else has to be able to tell.
    """
    argv = list(sys.argv[1:] if argv is None else argv)
    out = out or sys.stdout
    err = err or sys.stderr
    _console_utf8(out, err)

    try:
        opts = parse(argv)
    except Usage as exc:
        err.write(u"%s\n" % exc)
        return 2

    if opts[u"help"] or (not opts[u"roots"] and not opts[u"pairs"]):
        (out if opts[u"help"] else err).write(USAGE)
        return 0 if opts[u"help"] else 2

    if opts[u"roots"] and opts[u"pairs"]:
        err.write(u"Give a folder to search OR explicit --pair arguments, not "
                  u"both: a run cannot half-discover its own pairs.\n")
        return 2

    started = time.time()
    try:
        scan, report = _run(opts)
    except Usage as exc:
        err.write(u"%s\n" % exc)
        return 2
    except ValueError as exc:
        # ⭐ `sync()` REFUSES CONTRADICTORY FLAGS BY RAISING, and it says why in
        # a sentence written for a person (`--out` with `--no-rename`,
        # `--force` on a scan). Printing that sentence is better than
        # re-deriving the same rule here and letting the two drift.
        err.write(u"%s\n" % exc)
        return 2

    elapsed = time.time() - started

    if opts[u"json"]:
        for result in report:
            out.write(json.dumps(as_json(result), ensure_ascii=False) + u"\n")
        # ⛔ NEVER SILENT. A settled library produces no `Result` at all, so
        # `--json` printed nothing and exited 0 — which is exactly what a
        # broken run looks like. The summary goes to STDERR so a pipe stays
        # pure NDJSON and a person is still told what happened.
        err.write(report.summary() + u"\n")
    else:
        root = opts[u"roots"][0] if opts[u"roots"] else None
        for line in render(report, root=root, scan=scan, elapsed=elapsed,
                           verbose=opts[u"verbose"]):
            out.write(line + u"\n")

    if report.failed or report.errored or report.refused:
        return 1
    return 0


def _run(opts):
    u"""-> (`Scan` or None, `SyncReport`). ⛔ Every decision belongs to `sync`."""
    write = WRITES_BY_DEFAULT and not opts[u"dry_run"]
    common = dict(write=write, rename=opts[u"rename"],
                  keep_all=opts[u"keep_all"], out_dir=opts[u"out"],
                  results=None if opts[u"results"] else False,
                  suffix=opts[u"suffix"])

    if opts[u"pairs"]:
        return None, _pipeline.sync(opts[u"pairs"], force=opts[u"force"],
                                    **common)

    scan = _api.scan(videos=opts[u"roots"],
                     subs=opts[u"subs"] or None,
                     recurse=opts[u"recurse"])
    return scan, _pipeline.sync(scan, force=opts[u"force"], **common)


def _console_utf8(*streams):
    u"""Stop a CJK show name from killing the report.

    A Windows console defaults to the system ANSI codepage, so printing a
    Japanese filename to one raises `UnicodeEncodeError` — and a print that
    throws mid-loop stops the work after it, silently. ⚠ `errors="replace"` is
    correct HERE because this is a human-readable stream; it is emphatically
    not correct for decoding a subtitle (`03-permissions.md`).

    ⚠ And `line_buffering=True` whenever a stream is reconfigured:
    `reconfigure` resets the buffering mode, so a redirected stream starts
    block-buffering and a long run prints nothing for minutes
    (`LEDGER-HOT.md` §instrument traps).
    """
    for stream in streams:
        try:
            stream.reconfigure(encoding=u"utf-8", errors=u"replace",
                               line_buffering=True)
        except (AttributeError, ValueError):
            pass


__all__ = ["main", "parse", "render", "as_json", "Usage", "USAGE"]
