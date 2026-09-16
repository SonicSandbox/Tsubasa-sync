# -*- coding: utf-8 -*-
"""
WebVTT (.vtt).

🚨 Two traps, both already paid for:

  * `subsync` PARSES and REWRITES .vtt but its `SUB_EXT` list excludes it, so a
    folder of .vtt files silently will not pair or batch (LEDGER.md, corrected
    entries). Reading it is not the same as supporting it -- the extension has
    to be in the discovery list too.
  * A WebVTT reference routed to the ASS parser produced "parsed zero cues",
    which was reported as "could not read the file". Those are different
    outcomes; the tolerance ladder must sniff content, not trust extensions.

Whitelist notes (spec/03-permissions.md): cue SETTINGS (`align:start
position:10%`) are preserved verbatim, and `NOTE` / `STYLE` / `REGION` blocks
must survive -- dropping them turns a valid file invalid. All three are safe
here for the same structural reason as everywhere else: only timestamp spans
are ever replaced.
"""
import re

from ..cues import Cue, ParseError, ParseResult, Outcome

# WebVTT uses a dot separator and allows the hour to be omitted.
TIME = r"(?:(\d{2,}):)?(\d{2}):(\d{2})\.(\d{3})"
LINE = re.compile(
    r"(?P<start>" + TIME + r")"
    r"[ \t]*-->[ \t]*"
    r"(?P<end>" + TIME + r")"
    r"(?P<settings>[^\n]*)"
)


def parse_timestamp(s):
    m = re.match(r"^\s*(?:(\d{2,}):)?(\d{2}):(\d{2})\.(\d{3})\s*$", s)
    if not m:
        raise ValueError("not a WebVTT timestamp: %r" % s)
    h, mnt, sec, ms = m.groups()
    return int(h or 0) * 3600 + int(mnt) * 60 + int(sec) + int(ms) / 1000.0


_SHAPE = re.compile(r"^(\s*)(?:(\d{2,}):)?(\d{2}):(\d{2})\.(\d{3})(\s*)$")


def format_timestamp(seconds, like=None):
    """seconds -> `HH:MM:SS.mmm`, in the SHAPE of `like` when one is given.

    WebVTT allows the hour to be omitted. A zero shift must not add it, so the
    original's shape is preserved -- but a shift that pushes a cue past an hour
    forces the field back in, because dropping it would be a 3600-second error.
    """
    if seconds < 0:
        seconds = 0.0
    total_ms = int(round(seconds * 1000.0))
    ms = total_ms % 1000
    total_s = total_ms // 1000
    s = total_s % 60
    m = (total_s // 60) % 60
    h = total_s // 3600

    lead = trail = ""
    hour_width = 2
    if like:
        mm = _SHAPE.match(like)
        if mm:
            lead, hh, _m, _s, _ms, trail = mm.groups()
            hour_width = len(hh) if hh else 0

    if hour_width == 0 and h == 0:
        return "%s%02d:%02d.%03d%s" % (lead, m, s, ms, trail)
    return "%s%0*d:%02d:%02d.%03d%s" % (lead, max(hour_width, 2), h, m, s, ms, trail)


def make_formatter(_text=None):
    return format_timestamp


def parse(text, decoded=None):
    cues = []
    warnings = []

    head = text.lstrip("﻿").lstrip()
    if not head.startswith("WEBVTT"):
        # The signature is mandatory in the spec. Its absence is how a file
        # ends up at this parser by extension alone.
        raise ParseError("missing the mandatory WEBVTT signature")

    matches = list(LINE.finditer(text))
    if not matches:
        return ParseResult([], text, decoded, "vtt", Outcome.OK,
                           u"valid WEBVTT header but no cue timings", warnings)

    for i, m in enumerate(matches):
        try:
            start = parse_timestamp(m.group("start"))
            end = parse_timestamp(m.group("end"))
        except ValueError as exc:
            warnings.append(u"cue %d: %s" % (i + 1, exc))
            continue

        body_start = text.find("\n", m.end())
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = u"" if body_start == -1 or body_start > body_end \
            else text[body_start + 1:body_end]

        if end < start:
            warnings.append(u"cue %d ends before it starts" % (i + 1))

        cues.append(Cue(start, end, body.strip("\n"), index=i + 1,
                        start_span=(m.start("start"), m.end("start")),
                        end_span=(m.start("end"), m.end("end")),
                        block_span=_block_span(text, m.start(), body_end)))

    return ParseResult(cues, text, decoded, "vtt", Outcome.OK, u"", warnings)


#: A cue identifier: any single line before the timing line that is not itself
#: a timing line and not one of the block keywords. The spec allows it and
#: players show nothing for it, but it belongs to the cue and an orphan left
#: behind is a syntax error in the next block.
_BLOCK_KEYWORDS = ("NOTE", "STYLE", "REGION", "WEBVTT")


def _block_span(text, timestamp_at, next_cue_at):
    u"""The cue's OWN extent -- ⛔ never as far as the next cue.

    🚨 THIS IS WHERE WEBVTT DIFFERS FROM SRT AND THE DIFFERENCE IS THE WHOLE
    POINT. A `NOTE`, `STYLE` or `REGION` block may sit between two cues, and
    `03-permissions.md` puts all three in the MUST-NEVER-CHANGE column --
    *dropping them turns a valid file invalid*. An SRT-style span running to
    the next cue would take them with it, silently, on exactly the files that
    bothered to carry them.

    So the span ends at the blank line that terminates the cue's payload, and
    anything after that is somebody else's.
    """
    line_begin = text.rfind("\n", 0, timestamp_at) + 1
    begin = line_begin

    # An optional identifier line immediately above, which belongs to the cue.
    if line_begin > 0:
        prev = text.rfind("\n", 0, line_begin - 1) + 1
        candidate = text[prev:line_begin].strip("\r\n").strip()
        if candidate and "-->" not in candidate \
                and not candidate.split()[0].upper() in _BLOCK_KEYWORDS:
            begin = prev

    # The payload ends at the first blank line after the timing line.
    #
    # 🚨 CRLF. `text.find("\n\n")` DOES NOT MATCH `\r\n\r\n`, so on a CRLF file
    # this fell through to *"stop at the next cue"* — silently degrading to
    # exactly the SRT-style forward span this whole function exists to avoid,
    # and deleting the `NOTE`/`STYLE`/`REGION` blocks that
    # `03-permissions.md` puts in the never-change column.
    # **66% of the corpus (7,941 of 12,024 files) is CRLF.** Found by an
    # adversarial pass; every fixture in the suite was LF.
    end = _blank_line(text, timestamp_at)
    if end is None or end[0] > next_cue_at:
        # ⚠ No blank line before the next cue, or none at all. ⛔ REFUSE rather
        # than guess: an SRT-style span here removes somebody else's block, and
        # `cues.drop_cues` treats `None` as *"cannot be removed exactly"*,
        # which is the honest answer.
        return None
    stop = end[1]
    return (begin, min(stop, next_cue_at, len(text)))


def _blank_line(text, at):
    u"""The first blank line at or after `at`. -> (begin, end-of-separator).

    ⚠ Handles LF, CRLF and CR-only, because a subtitle file is whatever its
    author's editor produced and `06-edge-cases.md` §6.3 requires all three to
    survive untouched.
    """
    best = None
    for sep in ("\r\n\r\n", "\n\n", "\r\r"):
        found = text.find(sep, at)
        if found != -1 and (best is None or found < best[0]):
            best = (found, found + len(sep))
    return best


def sniff(text):
    if text.lstrip("﻿").lstrip().startswith("WEBVTT"):
        return 1.0
    return 0.0
