# -*- coding: utf-8 -*-
"""
The cue model, the three outcomes, and the in-place rewriter.

⭐ THE DESIGN DECISION THIS MODULE EXISTS FOR

`spec/03-permissions.md` lists what tsubasa may change in a user's file.  The
MUST-NEVER-CHANGE column is long: cue text, styles, fonts, `[V4+ Styles]`,
`[Script Info]`, `[Fonts]`/`[Graphics]` embedded binary, VTT cue settings, VTT
NOTE/STYLE/REGION blocks, the text encoding, and the line endings.

A parse -> model -> re-serialize writer has to REPRODUCE all of that faithfully,
and every format quirk it forgets is a silent corruption of something the user
cannot replace.

⭐ So the writer does not rebuild the file.  It replaces ONLY the character
spans holding timestamps and leaves every other byte exactly where it was.
Everything on the never-change list is preserved by construction rather than by
remembering -- which is what `doctrine/robustness` means by "a rule that relies
on remembering will be forgotten; make it structural".

A parser's job is therefore to report, per cue, WHERE the timestamps live --
not merely what they say.
"""


class Outcome(object):
    """The three outcomes.  There is no fourth and no silent success.

    🚨 OK-with-zero-cues and ERROR are DIFFERENT and must never be conflated.
    subsync shipped that confusion twice -- a WebVTT file routed to the ASS
    parser, and a legally-reordered ASS `Format:` line -- and both times a real
    failure disguised itself as an empty file and silently degraded the run.
    """
    OK = "OK"
    ERROR = "ERROR"


class Cue(object):
    """One timed line, and where its timestamps live in the source text."""

    __slots__ = ("start", "end", "text", "index", "start_span", "end_span",
                 "block_span")

    def __init__(self, start, end, text=u"", index=None,
                 start_span=None, end_span=None, block_span=None):
        self.start = start
        self.end = end
        self.text = text
        self.index = index
        self.start_span = start_span      # (begin, end) char offsets, or None
        self.end_span = end_span
        #: ⭐ (begin, end) of THE WHOLE CUE, for the two removals the field
        #: whitelist permits: a cue that ends before t=0, and `D9`'s cues
        #: inside a removed stretch.
        #:
        #: 🚨 EACH FORMAT DEFINES THIS DIFFERENTLY AND MUST, because the
        #: honest answer differs:
        #:
        #:   srt  the block, up to where the next one starts -- safe only
        #:        because SRT has NO COMMENT SYNTAX, so there is nothing
        #:        between two cues that could be swallowed
        #:   vtt  the cue's OWN extent and no further. ⛔ A `NOTE`, `STYLE`
        #:        or `REGION` block may sit between two cues and the
        #:        whitelist forbids touching it
        #:   ass  the single `Dialogue:`/`Comment:` line and its newline
        #:
        #: ⚠ `None` means the parser could not say, and `drop_cues` REFUSES
        #: rather than guessing -- the same rule `retime` applies to a missing
        #: timestamp span. Deriving the extent by scanning outward would
        #: re-derive structure the parser already knew.
        self.block_span = block_span

    @property
    def duration(self):
        return self.end - self.start

    def __repr__(self):
        return "Cue(%.3f, %.3f, %r)" % (self.start, self.end, self.text[:24])


class ParseResult(object):
    """What a reader returns.  Carries the source, so the file can be rewritten
    without being read twice -- and without any chance of the two reads
    disagreeing."""

    __slots__ = ("cues", "text", "decoded", "format", "outcome", "reason",
                 "warnings")

    def __init__(self, cues=None, text=u"", decoded=None, format=None,
                 outcome=Outcome.OK, reason=u"", warnings=None):
        self.cues = cues if cues is not None else []
        self.text = text
        self.decoded = decoded
        self.format = format
        self.outcome = outcome
        self.reason = reason
        self.warnings = warnings if warnings is not None else []

    @property
    def ok(self):
        return self.outcome == Outcome.OK

    def __len__(self):
        return len(self.cues)

    def __repr__(self):
        return "ParseResult(%s, %s, %d cues%s)" % (
            self.format, self.outcome, len(self.cues),
            (", %s" % self.reason) if self.reason else "")


class ParseError(Exception):
    """The file could not be read AT ALL.

    ⛔ Not "it had no cues".  Raise this only when the bytes are genuinely
    unreadable as this format -- the caller turns it into Outcome.ERROR, which
    surfaces to the user differently from a file that simply contained nothing.
    """


class RewriteRefused(Exception):
    """The rewrite would have changed something outside the field whitelist.

    Refuse loudly; never drop silently. A silent drop makes the caller believe
    it wrote (doctrine/robustness).
    """


# --------------------------------------------------------------------------
# the in-place rewriter
# --------------------------------------------------------------------------

def apply_spans(text, replacements):
    """Replace character spans in `text`, leaving everything else untouched.

    `replacements` is an iterable of ((begin, end), new_text).

    Three properties, each load-bearing:

      * NON-OVERLAPPING is enforced, not assumed. Two edits touching the same
        span means the parser reported the same timestamp twice, and applying
        both would corrupt the file in a way that still looks like a timestamp.
      * Applied back-to-front, so earlier offsets stay valid as we go.
      * Everything outside the spans is passed through by slicing -- there is
        no code path that can rewrite it.
    """
    spans = sorted(replacements, key=lambda r: r[0][0])

    prev_end = -1
    for (begin, end), new in spans:
        if begin < 0 or end > len(text) or begin > end:
            raise RewriteRefused(
                "span (%d,%d) is outside the source text of %d chars"
                % (begin, end, len(text)))
        if begin < prev_end:
            raise RewriteRefused(
                "overlapping edit spans: (%d,%d) starts before the previous "
                "one ended at %d -- the parser reported the same timestamp "
                "twice" % (begin, end, prev_end))
        prev_end = end

    out = []
    cursor = 0
    for (begin, end), new in spans:
        out.append(text[cursor:begin])
        out.append(new)
        cursor = end
    out.append(text[cursor:])
    return u"".join(out)


def retime(result, shift=None, mapper=None, formatter=None):
    """Produce new text with every cue's timestamps moved.

    `shift`  -- seconds to add to every cue, or
    `mapper` -- a callable(seconds) -> seconds for per-segment offsets (a cut
                file has more than one offset, so a single shift is not enough).
    `formatter` -- callable(seconds, like) -> str, supplied by the format
                module. `like` is the ORIGINAL text of that exact timestamp, so
                each one is rewritten in its own shape.

    ⭐ Per-timestamp, not per-file. A real Netflix .ass in the corpus mixes
    `00:00:00.00` on two lines with `0:00:00.00` on the other 674 -- both legal.
    A single per-file convention silently rewrote the odd ones out and changed
    the file by four bytes, which is a whitelist violation for a zero shift.

    ⚠ Cues whose parser gave no span are REFUSED, not skipped. A parser that
    cannot say where a timestamp lives cannot have it rewritten, and quietly
    leaving that cue at its old time is how a file ends up half-retimed.
    """
    if (shift is None) == (mapper is None):
        raise ValueError("retime needs exactly one of shift= or mapper=")
    if formatter is None:
        raise ValueError("retime needs the format's own timestamp formatter")

    fn = mapper if mapper is not None else (lambda t: t + shift)

    replacements = []
    for cue in result.cues:
        if cue.start_span is None or cue.end_span is None:
            raise RewriteRefused(
                "cue %r has no source span, so it cannot be rewritten in "
                "place; rewriting the rest would leave the file half-retimed"
                % (cue.index if cue.index is not None else cue))
        s_like = result.text[cue.start_span[0]:cue.start_span[1]]
        e_like = result.text[cue.end_span[0]:cue.end_span[1]]
        replacements.append((cue.start_span, formatter(fn(cue.start), s_like)))
        replacements.append((cue.end_span, formatter(fn(cue.end), e_like)))

    return apply_spans(result.text, replacements)


def drop_cues(result, doomed, formatter=None, mapper=None, shift=None,
              cue_mapper=None):
    u"""Remove whole cue blocks, retiming the survivors. -> new text

    `doomed` is an iterable of cue OBJECTS (identity, not index -- an index
    into a list that is about to shrink is the classic off-by-one here).

    ⭐ THE TWO REMOVALS THE FIELD WHITELIST PERMITS, AND NO OTHERS
    (`03-permissions.md`):

      * SRT/VTT cue blocks that end before t=0
      * ⭐ `D9`, ruled 2026-09-08: cue blocks falling INSIDE a removed stretch
        -- a CM block the video does not carry. Under any offset they map to
        time that no longer exists and would overlap the next segment, so they
        *cannot render correctly*, and they are **dropped, counted and
        reported**.

    🚨 REMOVAL AND RETIMING HAPPEN IN ONE PASS, deliberately. Doing them in two
    means the second pass works on text whose offsets the first pass moved --
    and every span the parser recorded is an offset into the ORIGINAL. That is
    not a subtle bug: it is a guaranteed one, and `apply_spans` would not catch
    it because the spans it received would all still look well-formed.

    ⚠ A cue with no `block_span` is REFUSED, not skipped -- the same rule
    `retime` applies to a missing timestamp span, and for the same reason: half
    a removal is worse than none.
    """
    if formatter is None:
        raise ValueError("drop_cues needs the format's own timestamp formatter")
    if cue_mapper is None and (shift is None) == (mapper is None):
        raise ValueError("drop_cues needs exactly one of shift= or mapper=")

    doomed_ids = set(id(c) for c in doomed)
    if not doomed_ids and cue_mapper is None:
        return retime(result, shift=shift, mapper=mapper, formatter=formatter)

    if cue_mapper is not None:
        fn = None
    else:
        fn = mapper if mapper is not None else (lambda t: t + shift)
    replacements = []
    survivors = []

    for cue in result.cues:
        if id(cue) in doomed_ids:
            if cue.block_span is None:
                raise RewriteRefused(
                    "cue %r must be removed but its parser did not report "
                    "where the block lives, so the removal cannot be made "
                    "exactly; removing the rest would leave the file "
                    "half-edited"
                    % (cue.index if cue.index is not None else cue))
            replacements.append((cue.block_span, u""))
            continue
        if cue.start_span is None or cue.end_span is None:
            raise RewriteRefused(
                "cue %r has no source span, so it cannot be rewritten in "
                "place" % (cue.index if cue.index is not None else cue))
        s_like = result.text[cue.start_span[0]:cue.start_span[1]]
        e_like = result.text[cue.end_span[0]:cue.end_span[1]]
        new_start, new_end = (cue_mapper(cue) if cue_mapper is not None
                              else (fn(cue.start), fn(cue.end)))
        replacements.append((cue.start_span, formatter(new_start, s_like)))
        replacements.append((cue.end_span, formatter(new_end, e_like)))
        survivors.append(cue)

    if result.format == "srt":
        # ⛔ THE ONE THING THE WHITELIST EXPLICITLY ADDS FOR A DROP: *SRT
        # sequence numbers (renumbered after a drop)*. A gap in the numbering
        # is legal in the wild but some players stop at the first one, so a
        # removal that left holes would produce a file that plays halfway.
        replacements.extend(_renumber_srt(result, survivors))

    return apply_spans(result.text, replacements)


def _renumber_srt(result, survivors):
    u"""Sequence-number replacements so the survivors read 1..N.

    ⚠ Only where the block actually STARTS with an index line. A file whose
    blocks carry no numbers is legal, and inventing them would be a change
    outside the whitelist -- the rule permits *renumbering*, not *numbering*.
    """
    import re as _re
    out = []
    number = 0
    for cue in survivors:
        number += 1
        if cue.block_span is None:
            continue
        head_end = result.text.find("\n", cue.block_span[0])
        if head_end == -1 or head_end > cue.block_span[1]:
            continue
        head = result.text[cue.block_span[0]:head_end]
        match = _re.match(r"^(\s*)(\d+)(\s*)$", head.rstrip("\r"))
        if not match:
            continue                       # no index line: nothing to renumber
        if match.group(2) == str(number):
            continue                       # already right; do not touch it
        out.append(((cue.block_span[0] + len(match.group(1)),
                     cue.block_span[0] + len(match.group(1))
                     + len(match.group(2))), u"%d" % number))
    return out


# ---------------------------------------------------------------------------
# ⛔ `clamp_negative` WAS HERE AND WAS DELETED AT 3b, 2026-09-09.
# ---------------------------------------------------------------------------
#
# It took a cue list and dropped anything with `end <= 0.0`, and it had **zero
# callers** -- `HANDOFF.md` carried it as *"a near-duplicate of what
# `apply._render` does; fold one in once the call site settles."* The call site
# settled at 3b, and folding turned out to be the wrong verb: the two were not
# duplicates, they answered on **different axes**.
#
# 🚨 `apply._render` asks `mapper(cue.end) <= 0.0` -- the cue's end AFTER the
# measured offset is applied, which is the only version of the question that
# means anything. `clamp_negative` compared the RAW end, i.e. where the cue sat
# before any retiming, and every cue in a normal subtitle is positive there. So
# it would have dropped nothing on the files that need it and dropped
# everything on a subtitle whose own timestamps start negative.
#
# ⭐ It is deleted rather than fixed because a fixed version would need the
# mapper, at which point it IS `_render`'s loop -- and `_render` is one pass
# over the cues doing both removals the whitelist permits, which two passes
# cannot be (the second would apply to offsets the first had moved).
#
# ⚠ This is the `duration_verdict` shape `LEDGER.md` §Logic records at A9: a
# public helper that was never called, so it cost nothing -- and was a landmine
# wired to its first caller. `doctrine/architecture`: *edit in place; never
# accrete parallel implementations.*
