# -*- coding: utf-8 -*-
"""
VobSub (.idx) -- the DVD bitmap subtitle index.

RUNBOOK step 1c, alongside PGS. The corpus carries 39 `.idx`/`.sub` pairs
(Aoi Blink), ~350 timestamps each.

⭐ Unlike PGS, the `.idx` is a TEXT file: a header of key/value settings
followed by one line per caption --

    timestamp: 00:00:12:500, filepos: 000000000

so it is read through the normal encoding ladder, and its timestamps DO have
source spans. The bitmaps live in the sibling `.sub`, which is never touched.

🚨 Two traps this format brings:

  * The separator between seconds and milliseconds is a COLON, not a comma or
    a dot -- `00:00:12:500`. Reusing the SRT timestamp parser here silently
    reads the wrong field.
  * A `.sub` file is EITHER VobSub bitmap data OR MicroDVD text, depending
    entirely on content. The extension says nothing. MicroDVD is frame-based
    and needs the video's FPS, so it stays unimplemented rather than guessing
    (spec/06-edge-cases.md §6.4).

⚠ An .idx has no cue END times -- a caption is shown until the next one starts.
The end times below are DERIVED, and the last cue is given a nominal duration.
That is a real limitation of the format, recorded here so nobody later reads
these durations as measured.
"""
import re

from ..cues import Cue, ParseError, ParseResult, Outcome

# `timestamp: 00:00:12:500, filepos: 000000000`
_TS_LINE = re.compile(
    r"^timestamp:\s*(?P<ts>(\d+):(\d{2}):(\d{2}):(\d{1,3}))\s*,\s*filepos:",
    re.MULTILINE | re.IGNORECASE)

_TS_EXACT = re.compile(r"^\s*(\d+):(\d{2}):(\d{2}):(\d{1,3})\s*$")

# How long to show the final caption, which has nothing after it to end it.
TRAILING_DURATION = 2.0


def parse_timestamp(s):
    """`HH:MM:SS:mmm` -> seconds. Note the COLON before milliseconds."""
    m = _TS_EXACT.match(s)
    if not m:
        raise ValueError("not a VobSub timestamp: %r" % s)
    h, mnt, sec, ms = m.groups()
    return (int(h) * 3600 + int(mnt) * 60 + int(sec)
            + int((ms + "000")[:3]) / 1000.0)


def format_timestamp(seconds, like=None):
    if seconds < 0:
        seconds = 0.0
    total_ms = int(round(seconds * 1000.0))
    ms = total_ms % 1000
    total_s = total_ms // 1000
    return "%02d:%02d:%02d:%03d" % (
        total_s // 3600, (total_s // 60) % 60, total_s % 60, ms)


def make_formatter(_text=None):
    return format_timestamp


def parse(text, decoded=None):
    matches = list(_TS_LINE.finditer(text))
    if not matches:
        if "# VobSub index file" in text or re.search(r"^id:\s", text, re.M):
            return ParseResult([], text, decoded, "vobsub", Outcome.OK,
                               u"VobSub index with no timestamp lines", [])
        raise ParseError("no VobSub `timestamp:` lines and no index header")

    starts = []
    warnings = []
    for i, m in enumerate(matches):
        try:
            starts.append((parse_timestamp(m.group("ts")),
                           (m.start("ts"), m.end("ts"))))
        except ValueError as exc:
            warnings.append(u"line %d: %s" % (i + 1, exc))

    cues = []
    for i, (start, span) in enumerate(starts):
        # ⚠ DERIVED, not measured -- the format carries no end time.
        end = starts[i + 1][0] if i + 1 < len(starts) else start + TRAILING_DURATION
        cues.append(Cue(start, end, u"", index=i + 1,
                        start_span=span, end_span=None))

    warnings.append(
        u"end times are derived (a VobSub index carries only start times)")
    return ParseResult(cues, text, decoded, "vobsub", Outcome.OK, u"", warnings)


def sniff(text):
    head = text[:8192]
    score = 0.0
    if "# VobSub index file" in head:
        score += 0.6
    if re.search(r"^id:\s*\w+", head, re.MULTILINE):
        score += 0.2
    if _TS_LINE.search(head):
        score += 0.4
    return min(score, 1.0)
