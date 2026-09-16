# -*- coding: utf-8 -*-
"""
SubRip (.srt).

Traps this reader is built around (spec/06-edge-cases.md §6.4, LEDGER.md):

  * SRT with NO blank lines between blocks -- lenient block splitting.
  * Duplicate, missing or non-sequential indices -- read what is there,
    renumber only on write, and only when a cue was dropped.
  * `,` is the decimal separator, but `.` appears in the wild. Accept both,
    and ⭐ WRITE BACK THE ONE THE FILE USED -- the whitelist forbids gratuitous
    changes, and a player that wanted commas gets commas.
  * Hours may be missing (`MM:SS,mmm`) or run past 99.
  * A cue may legitimately have zero duration.

⛔ This module never rebuilds the file. It reports the character span of every
timestamp and the writer replaces those spans -- see `tsubasa/cues.py`.
"""
import re

from ..cues import Cue, ParseError, ParseResult, Outcome

# Deliberately permissive: hours optional, either decimal separator, any run of
# whitespace around the arrow, and trailing cue settings tolerated (some
# muxers emit VTT-style coordinates into .srt).
TIME = r"(?:(\d+):)?(\d{1,3}):(\d{1,2})[,.](\d{1,3})"
LINE = re.compile(
    r"(?P<start>" + TIME + r")"
    r"[ \t]*-->[ \t]*"
    r"(?P<end>" + TIME + r")"
)

_INDEX = re.compile(r"^\s*\d+\s*$")

# Precompiled: parse_timestamp runs twice per cue, so ~70,000 times over a
# 150-file sample. Compiling it inline pays re._compile's cache lookup every
# one of those calls for nothing.
_TS_EXACT = re.compile(r"^\s*(?:(\d+):)?(\d{1,3}):(\d{1,2})[,.](\d{1,3})\s*$")

# A format signature lives at the top of a file. Sniffing the WHOLE text costs
# a full scan of every file that ISN'T this format -- measured at 24% of total
# parse time, because a 2.5 MB ASS file was scanned end to end looking for an
# SRT arrow that was never going to be there.
SNIFF_HEAD = 8192


def parse_timestamp(s):
    """`HH:MM:SS,mmm` -> seconds. Accepts a missing hour and either separator."""
    m = _TS_EXACT.match(s)
    if not m:
        raise ValueError("not an SRT timestamp: %r" % s)
    h, mnt, sec, frac = m.groups()
    # "5" means 500 ms, not 5 ms -- pad right, never left.
    ms = int((frac + "000")[:3])
    return int(h or 0) * 3600 + int(mnt) * 60 + int(sec) + ms / 1000.0


_SHAPE = re.compile(r"^(\s*)(?:(\d+):)?(\d{1,3}):(\d{1,2})([,.])(\d+)(\s*)$")


def format_timestamp(seconds, like=None, sep=","):
    """seconds -> `HH:MM:SS,mmm`, in the SHAPE of `like` when one is given.

    ⚠ Rounds to the nearest millisecond rather than truncating. Truncation
    biases every cue earlier, and a systematic sub-frame bias is exactly the
    class of defect that produced the -0.3 s plateau error in subsync.

    `like` preserves the separator, the hour width, and the fractional-digit
    count of THAT timestamp -- so a zero shift cannot change the file even when
    one file mixes conventions. See ass.format_timestamp for the corpus case
    that forced this.
    """
    if seconds < 0:
        seconds = 0.0

    hour_width, min_width, sec_width = 2, 2, 2
    frac_digits, lead, trail = 3, "", ""
    if like:
        m = _SHAPE.match(like)
        if m:
            lead, hh, mm, ss, sep, frac, trail = m.groups()
            hour_width = len(hh) if hh else 0
            # ⚠ Minutes and seconds too, not just the hour. Real files in the
            # corpus write `00:00:9,864` -- a ONE-digit seconds field, which is
            # legal. Forcing %02d there changed 155 files on a zero shift.
            min_width, sec_width = len(mm), len(ss)
            frac_digits = len(frac)

    scale = 10 ** frac_digits
    total = int(round(seconds * scale))
    frac = total % scale
    total_s = total // scale
    s = total_s % 60
    m_ = (total_s // 60) % 60
    h = total_s // 3600

    if hour_width == 0:
        # The source omitted the hour. Keep omitting it -- unless the shift has
        # pushed the cue past an hour, in which case dropping it would be a
        # 3600-second error and the shape must give way to correctness.
        if h == 0:
            return "%s%0*d:%0*d%s%0*d%s" % (
                lead, min_width, m_, sec_width, s, sep, frac_digits, frac, trail)
        hour_width = 2

    return "%s%0*d:%0*d:%0*d%s%0*d%s" % (
        lead, hour_width, h, min_width, m_, sec_width, s,
        sep, frac_digits, frac, trail)


def detect_separator(text):
    """Which decimal separator this file uses. Written back unchanged."""
    m = LINE.search(text)
    if not m:
        return ","
    return "," if "," in m.group("start") else "."


def make_formatter(text):
    # The per-file separator is now only a FALLBACK: each timestamp is written
    # in its own shape, taken from the `like` string retime() passes in.
    sep = detect_separator(text)
    return lambda seconds, like=None: format_timestamp(seconds, like, sep)


def parse(text, decoded=None):
    """Text -> ParseResult. Records the span of every timestamp.

    🚨 Returns OK with zero cues for a readable file that contains none.
    Raises ParseError only when the bytes are not SRT at all. Those are
    different outcomes and conflating them shipped twice.
    """
    cues = []
    warnings = []

    matches = list(LINE.finditer(text))
    if not matches:
        # No timing line anywhere. Distinguish "an empty/other file" from
        # "SRT whose timings are corrupt" -- an index line with no arrow is
        # the signature of a truncated or mangled SRT.
        if text.strip() and _looks_like_srt_without_timings(text):
            raise ParseError(
                "looks like SRT (index lines present) but contains no "
                "`-->` timing line -- truncated or corrupt")
        return ParseResult([], text, decoded, "srt", Outcome.OK,
                           u"no SRT timing lines found", warnings)

    for i, m in enumerate(matches):
        try:
            start = parse_timestamp(m.group("start"))
            end = parse_timestamp(m.group("end"))
        except ValueError as exc:
            warnings.append(u"cue %d: %s" % (i + 1, exc))
            continue

        body_start = text.find("\n", m.end())
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        if body_start == -1 or body_start > body_end:
            body = u""
        else:
            body = text[body_start + 1:body_end]
            # Trim the trailing index line belonging to the NEXT cue.
            lines = body.split("\n")
            while lines and not lines[-1].strip():
                lines.pop()
            if lines and _INDEX.match(lines[-1]):
                lines.pop()
            body = "\n".join(lines)

        if end < start:
            warnings.append(
                u"cue %d ends before it starts (%.3f < %.3f)"
                % (i + 1, end, start))

        cues.append(Cue(
            start, end, body.strip("\n"), index=i + 1,
            start_span=(m.start("start"), m.end("start")),
            end_span=(m.start("end"), m.end("end")),
            # ⭐ The whole block: from this cue's index line to where the next
            # cue's index line begins, so removing it takes the blank
            # separator with it and leaves no gap.
            #
            # ⚠ Extending to the NEXT cue is safe here and nowhere else: SRT
            # has no comment syntax (`03-permissions.md` -- *any cue is
            # visible on screen*), so there is nothing between two blocks that
            # this could swallow. WebVTT is not like that and does not do it.
            block_span=_span(text, matches, i),
        ))

    return ParseResult(cues, text, decoded, "srt", Outcome.OK, u"", warnings)


def _span(text, matches, i):
    u"""Cue `i`'s whole block. -> (begin, end) or None if it cannot be located.

    ⚠ `None` propagates: if either edge is unknown the span is unknown, and
    `cues.drop_cues` REFUSES rather than removing an approximate range from a
    file the user cannot replace.
    """
    begin = _block_start(text, matches[i].start())
    if begin is None:
        return None
    if i + 1 >= len(matches):
        return (begin, len(text))
    end = _block_start(text, matches[i + 1].start())
    if end is None or end < begin:
        return None
    return (begin, end)


def _block_start(text, timestamp_at):
    u"""Where the block owning the timestamp at `timestamp_at` begins.

    ⭐ An SRT block usually opens with a bare index line, and that line belongs
    to the cue below it -- so a removal that started at the TIMING line would
    leave an orphan number sitting in the file. Walk back exactly one line, and
    only when it looks like an index.

    ⚠ `LINE` is NOT anchored to the start of a line, so `m.start()` is the
    timestamp and not the line -- a leading space or tab sits before it. The
    first step here is finding the line, and forgetting it would put the cut
    mid-line on every indented file.

    ⚠ One line back, never more. Walking further would eat the previous cue's
    trailing text on a file whose blank separators are missing, which
    `06-edge-cases.md` §6.4 lists as a real shape (*SRT with no blank lines
    between blocks*).
    """
    line_begin = text.rfind("\n", 0, timestamp_at) + 1
    if line_begin <= 0:
        # ⚠ The first cue, OR a CR-only file (classic Mac) in which there is no
        # `\n` at all. ⛔ Returning 0 for the latter made every block start at
        # byte zero: a middle removal became a silent no-op that was still
        # COUNTED and reported, and a last-cue removal erased the file. Found
        # by an adversarial pass. `None` means *cannot be located*, and
        # `cues.drop_cues` refuses on it rather than guessing.
        if timestamp_at > 0 and "\n" not in text[:timestamp_at]:
            return None
        return 0

    # 🚨 THE PRECEDING LINE IS ONLY AN INDEX IF A BLANK LINE PRECEDES *IT*.
    #
    # Without that, an SRT written with no blank separators -- which
    # `06-edge-cases.md` §6.4 lists as a real shape -- lets a cue whose TEXT is
    # a bare number be read as the next cue's index. Measured: a countdown line
    # `42` was DELETED with the block below it, and `_renumber_srt` overwrote
    # another one with a sequence number. Both are the MUST-NEVER-CHANGE
    # column, both silent. Found by an adversarial pass.
    prev_break = text.rfind("\n", 0, line_begin - 1)
    index_begin = prev_break + 1
    candidate = text[index_begin:line_begin].strip("\r\n")
    if _INDEX.match(candidate) and _starts_a_block(text, index_begin):
        return index_begin
    return line_begin


def _starts_a_block(text, at):
    u"""Is `at` the beginning of the file, or preceded by a blank line?

    ⚠ That is what separates an index line from a line of dialogue that
    happens to be a number. Handles LF, CRLF and CR-only.
    """
    if at <= 0:
        return True
    before = text[:at]
    return (before.endswith("\n\n") or before.endswith("\r\n\r\n")
            or before.endswith("\r\r") or before.strip("\r\n") == "")


def _looks_like_srt_without_timings(text):
    """Two or more bare integer lines: an SRT whose timings went missing."""
    n = 0
    for line in text.split("\n")[:200]:
        if _INDEX.match(line):
            n += 1
            if n >= 2:
                return True
    return False


def sniff(text):
    """Confidence that this text is SRT. Used by the tolerance ladder.

    ⚠ Scans only the head. An SRT's first timing line is within the first few
    hundred bytes; scanning the rest only slows down every file that is not an
    SRT. A false negative here is harmless -- the extension hint still puts
    this reader in the ladder, and the reader itself scans the whole file.
    """
    head = text[:SNIFF_HEAD]
    m = LINE.search(head)
    if not m:
        return 0.0
    text = head
    # A comma separator and a bare-integer line before the arrow are the two
    # things that distinguish SRT from WebVTT, which shares the arrow.
    score = 0.6
    if "," in m.group("start"):
        score += 0.3
    head = text[:m.start()].split("\n")
    if any(_INDEX.match(l) for l in head[-3:]):
        score += 0.1
    if text.lstrip().startswith("WEBVTT"):
        return 0.0
    return min(score, 1.0)
