# -*- coding: utf-8 -*-
"""
Advanced SubStation Alpha (.ass) and SubStation Alpha (.ssa).

🚨 THE TRAP THAT SHIPPED: the `Format:` line is authoritative and its field
order is NOT fixed.  A legally-reordered `Format:` line made subsync parse zero
cues and report "could not read the file" -- one real failure disguised as
another.  This reader reads the column positions out of the file, every time,
and never assumes `Start` is field 1.

What the whitelist permits here (spec/03-permissions.md):

  MAY change   Start/End on `Dialogue:` lines
               Start/End on `Comment:` lines
  NEVER        cue text · styles · fonts · [Script Info] · [V4+ Styles]
               · [V4 Styles] · [Fonts]/[Graphics] embedded binary

⭐ All of that is preserved structurally: this module reports the character span
of each timestamp and nothing else is ever touched.  The embedded binary in
`[Fonts]` survives because no code path writes to it.
"""
import re

from ..cues import Cue, ParseError, ParseResult, Outcome

_SECTION = re.compile(r"^\s*\[([^\]]+)\]\s*$")
_FORMAT = re.compile(r"^\s*Format\s*:\s*(.*)$", re.IGNORECASE)
_EVENT = re.compile(r"^\s*(Dialogue|Comment)\s*:\s*(.*)$", re.IGNORECASE)

# 0:00:12.50 -- one-digit hour, centiseconds. Tolerate 2-3 fractional digits
# and a 2-digit hour, both of which appear in files written by other tools.
_TS = re.compile(r"^\s*(\d{1,2}):(\d{2}):(\d{2})[.,](\d{1,3})\s*$")


def parse_timestamp(s):
    m = _TS.match(s)
    if not m:
        raise ValueError("not an ASS timestamp: %r" % s)
    h, mnt, sec, frac = m.groups()
    # ASS is centiseconds: "5" means 50 cs = 500 ms. Pad right.
    if len(frac) == 1:
        ms = int(frac) * 100
    elif len(frac) == 2:
        ms = int(frac) * 10
    else:
        ms = int(frac)
    return int(h) * 3600 + int(mnt) * 60 + int(sec) + ms / 1000.0


_SHAPE = re.compile(r"^(\s*)(\d+):(\d{1,2}):(\d{1,2})([.,])(\d+)(\s*)$")


def format_timestamp(seconds, like=None):
    """seconds -> `H:MM:SS.cc`, in the SHAPE of `like` when one is given.

    ⚠ ASS stores CENTISECONDS. Rounding rather than truncating keeps the write
    symmetric with the read; truncating would drag every cue up to 10 ms
    earlier, and a systematic bias in that direction is what produced the
    -0.3 s error subsync shipped.

    🚨 `like` exists because a real Netflix file in the corpus writes
    `00:00:00.00` on two lines and `0:00:00.00` on the other 674. Both are
    legal. Normalising to one of them changed the file on a ZERO shift, which
    the whitelist forbids -- so each timestamp is rewritten in its own shape:
    its hour width, its separator, and its number of fractional digits.
    """
    if seconds < 0:
        seconds = 0.0

    hour_width, min_width, sec_width = 1, 2, 2
    sep, frac_digits, lead, trail = ".", 2, "", ""
    if like:
        m = _SHAPE.match(like)
        if m:
            lead, hh, mm, ss, sep, frac, trail = m.groups()
            hour_width = len(hh)
            min_width, sec_width = len(mm), len(ss)
            frac_digits = len(frac)

    scale = 10 ** frac_digits
    total = int(round(seconds * scale))
    frac = total % scale
    total_s = total // scale
    s = total_s % 60
    m_ = (total_s // 60) % 60
    h = total_s // 3600

    return "%s%0*d:%0*d:%0*d%s%0*d%s" % (
        lead, hour_width, h, min_width, m_, sec_width, s,
        sep, frac_digits, frac, trail)


def make_formatter(_text=None):
    return format_timestamp


def _field_spans(line_text, line_offset, payload_offset, n_fields):
    """Character spans of each comma-separated field on an event line.

    The final field (Text) may itself contain commas, so the split is capped at
    n_fields-1 -- exactly as the format requires.
    """
    # str.find rather than a per-character Python loop: measured at 20% of
    # total parse time across 33,600 calls, doing in the interpreter what the
    # C string routine does for free.
    spans = []
    rel = payload_offset - line_offset
    for _ in range(n_fields - 1):
        comma = line_text.find(",", rel)
        if comma == -1:
            break
        spans.append((line_offset + rel, line_offset + comma))
        rel = comma + 1
    spans.append((line_offset + rel, line_offset + len(line_text)))
    return spans


def parse(text, decoded=None):
    """Text -> ParseResult, with timestamp spans located via the Format line."""
    cues = []
    warnings = []

    section = None
    start_col = end_col = None
    n_fields = None
    saw_events = False

    offset = 0
    index = 0
    for raw in text.split("\n"):
        line_len = len(raw)
        line_start = offset
        offset += line_len + 1              # +1 for the \n we split on

        stripped = raw.rstrip("\r")
        sec = _SECTION.match(stripped)
        if sec:
            section = sec.group(1).strip().lower()
            if section == "events":
                saw_events = True
            continue

        if section != "events":
            continue

        fmt = _FORMAT.match(stripped)
        if fmt:
            names = [n.strip().lower() for n in fmt.group(1).split(",")]
            n_fields = len(names)
            if "start" in names:
                start_col = names.index("start")
            if "end" in names:
                end_col = names.index("end")
            if start_col is None or end_col is None:
                warnings.append(
                    u"[Events] Format line names no Start/End column: %s"
                    % fmt.group(1))
            continue

        ev = _EVENT.match(stripped)
        if not ev:
            continue

        if start_col is None or end_col is None or n_fields is None:
            # An event before any Format line. The format REQUIRES one, and
            # guessing column positions is how the reordered-Format bug got
            # its wrong answer in the first place.
            raise ParseError(
                "[Events] contains a %s line before any Format line, so the "
                "column order is unknown -- refusing to guess" % ev.group(1))

        payload_offset = line_start + stripped.index(ev.group(2), stripped.index(":") + 1)
        spans = _field_spans(stripped, line_start, payload_offset, n_fields)
        if len(spans) <= max(start_col, end_col):
            warnings.append(u"event line has %d fields, Format declares %d"
                            % (len(spans), n_fields))
            continue

        s_span, e_span = spans[start_col], spans[end_col]
        s_raw = text[s_span[0]:s_span[1]]
        e_raw = text[e_span[0]:e_span[1]]
        try:
            start = parse_timestamp(s_raw)
            end = parse_timestamp(e_raw)
        except ValueError as exc:
            warnings.append(u"line %d: %s" % (index + 1, exc))
            continue

        index += 1
        body = text[spans[-1][0]:spans[-1][1]]
        cues.append(Cue(start, end, body, index=index,
                        start_span=s_span, end_span=e_span,
                        # ⭐ One line and its newline. An ASS event IS a line,
                        # so there is no block to find and nothing between two
                        # events that a removal could swallow. ⚠ Clamped, for
                        # a final line with no trailing newline.
                        block_span=(line_start,
                                    min(line_start + line_len + 1, len(text)))))

    if not saw_events:
        raise ParseError("no [Events] section -- not an ASS/SSA file")

    return ParseResult(cues, text, decoded, "ass", Outcome.OK, u"", warnings)


_SNIFF_INFO = re.compile(r"^\s*\[Script Info\]", re.MULTILINE | re.IGNORECASE)
_SNIFF_STYLES = re.compile(r"^\s*\[V4\+? Styles\]", re.MULTILINE | re.IGNORECASE)
_SNIFF_EVENTS = re.compile(r"^\s*\[Events\]", re.MULTILINE | re.IGNORECASE)

# [Events] sits after the style block, which can be long in a heavily-typeset
# file -- so this head is bigger than SRT's. Still bounded: scanning a 2.5 MB
# file to sniff it was 24% of total parse time.
SNIFF_HEAD = 65536


def sniff(text):
    head = text[:SNIFF_HEAD]
    score = 0.0
    if _SNIFF_INFO.search(head[:4096]):
        score += 0.4
    if _SNIFF_STYLES.search(head[:4096]):
        score += 0.3
    if _SNIFF_EVENTS.search(head):
        score += 0.3
    return min(score, 1.0)
