# -*- coding: utf-8 -*-
"""
The universal reader, and its tolerance ladder.

    extension -> content sniffing -> lenient parse -> ERROR

🚨 THE OUTCOME RULE, which this module exists to enforce:

    "Parsed zero cues" and "could not read the file" are DIFFERENT outcomes.

`subsync` conflated them twice -- a WebVTT reference routed to the ASS parser,
and a legally-reordered ASS `Format:` line -- and both times a real failure
disguised itself as an empty file and silently degraded the run. Here:

    Outcome.OK    with 0 cues -> the file was read; it contains no timings
    Outcome.ERROR                -> the file could not be read at all, and the
                                    reason says which rung of the ladder failed

⚠ The extension is a HINT, never a decision. Spruce STL and EBU-STL are
different binary formats sharing an extension; `.sub` is MicroDVD or VobSub
depending on content; and every one of the traps above began with a file that
was not what its name said.
"""
from ..cues import ParseError, ParseResult, Outcome
from ..encoding import UndecodableError, sniff_and_decode
from . import ass, pgs, srt, vobsub, vtt

# Text formats, in the order the ladder tries them when sniffing is ambiguous.
TEXT_READERS = {
    "srt": srt,
    "ass": ass,
    "vtt": vtt,
    "vobsub": vobsub,
}

# Binary formats, matched on their magic bytes BEFORE any text decoding.
# ⚠ Decoding a binary stream as text and parsing the result is how a bitmap
# subtitle gets reported as an empty file rather than as what it is.
BINARY_READERS = [pgs]

# ⛔ What may be WRITTEN back (spec/06-edge-cases.md §6.1). Bitmap formats are
# a timing reference and are never writable as text -- the image data is not
# ours to regenerate. Enforced in rewrite_bytes, not left to the caller.
WRITABLE_FORMATS = {"srt", "ass", "vtt"}

# Extension -> reader name. A HINT that reorders the ladder; never a decision.
EXT_HINT = {
    ".srt": "srt",
    ".ass": "ass",
    ".ssa": "ass",
    ".vtt": "vtt",
    ".idx": "vobsub",
}

# Everything spec/06-edge-cases.md §6.1 says we must read timing from. The ones
# without a reader yet are listed so discovery can still SEE them -- a format
# we cannot parse must produce an honest ERROR, not be silently invisible.
# ⚠ subsync's SUB_EXT excluded .vtt while its parser supported it, so a folder
# of .vtt files would not pair or batch. Discovery and parsing must agree.
KNOWN_SUBTITLE_EXT = {
    ".srt", ".ass", ".ssa", ".vtt", ".sub", ".sbv", ".smi", ".ttml",
    ".dfxp", ".itt", ".stl", ".idx", ".sup",
}

NOT_IMPLEMENTED_YET = {
    ".sub": "MicroDVD text or VobSub bitmap data -- the extension says nothing "
            "and MicroDVD is frame-based, needing the video's FPS",
    ".sbv": "YouTube SBV",
    ".smi": "SAMI",
    ".ttml": "TTML", ".dfxp": "DFXP", ".itt": "iTT",
    ".stl": "Spruce STL or EBU-STL -- two different binary formats sharing one "
            "extension, so this must sniff content and does not yet",
}


def read_bytes(data, filename=None):
    """bytes -> ParseResult. Never raises for a merely-unparseable file.

    Every failure path returns Outcome.ERROR with a reason naming what was
    actually found -- "a failure message says what it FOUND, not what it
    wanted" (doctrine/robustness).
    """
    # Binary formats FIRST, on magic bytes. A PGS stream decoded as text
    # produces a plausible-looking string that parses to zero cues, which then
    # reads as "an empty subtitle file" instead of "a bitmap subtitle".
    for mod in BINARY_READERS:
        try:
            if mod.sniff_bytes(data) > 0.0:
                return mod.parse(data, None, filename=filename)
        except ParseError as exc:
            return ParseResult([], u"", None, None, Outcome.ERROR,
                               u"%s" % exc)
        except Exception as exc:
            return ParseResult([], u"", None, None, Outcome.ERROR,
                               u"unexpected %s reading a binary subtitle: %s"
                               % (type(exc).__name__, exc))

    try:
        decoded = sniff_and_decode(data)
    except (UndecodableError, TypeError) as exc:
        return ParseResult([], u"", None, None, Outcome.ERROR,
                           u"could not decode the bytes: %s" % exc)

    text = decoded.text
    if not text.strip():
        return ParseResult([], text, decoded, None, Outcome.OK,
                           u"file is empty")

    # Score every reader on content. The extension only breaks ties.
    scores = []
    for name, mod in TEXT_READERS.items():
        try:
            scores.append((mod.sniff(text), name))
        except Exception:                       # a sniffer must never decide
            scores.append((0.0, name))          # the outcome by throwing
    scores.sort(reverse=True)

    ext = _ext(filename)
    hint = EXT_HINT.get(ext)

    order = [n for _s, n in scores if _s > 0.0]
    if hint:
        # The extension moves its reader to the front -- and puts it in the
        # list even when content-sniffing scored it zero, so a file whose
        # signature is damaged still gets tried by the parser its name claims.
        order = [hint] + [n for n in order if n != hint]

    attempts = []
    empty_ok = None
    for name in order:
        try:
            result = TEXT_READERS[name].parse(text, decoded)
        except ParseError as exc:
            attempts.append(u"%s: %s" % (name, exc))
            continue
        except Exception as exc:                # a crash is still an ERROR,
            attempts.append(u"%s: unexpected %s: %s"   # never a traceback at
                            % (name, type(exc).__name__, exc))  # the user
            continue
        if result.cues:
            return result
        # Parsed cleanly but found nothing. Hold it and try the next reader --
        # but do NOT discard it, because a genuinely empty subtitle file is
        # OK-with-zero-cues, and calling that ERROR is the conflation this
        # module exists to prevent.
        attempts.append(u"%s: read the file but found no cues" % name)
        if empty_ok is None:
            empty_ok = result

    if empty_ok is not None:
        empty_ok.reason = u"read as %s; contains no cues" % empty_ok.format
        return empty_ok

    if ext in NOT_IMPLEMENTED_YET:
        return ParseResult([], text, decoded, None, Outcome.ERROR,
                           u"%s is not implemented yet (%s)"
                           % (ext, NOT_IMPLEMENTED_YET[ext]))

    return ParseResult([], text, decoded, None, Outcome.ERROR,
                       u"no reader recognised this file. Tried -- %s"
                       % (u"; ".join(attempts) if attempts
                          else u"nothing matched on content"))


def read_file(path):
    """Read from disk. Binary mode always -- the codec is ours to decide."""
    try:
        with open(str(path), "rb") as fh:
            data = fh.read()
    except (IOError, OSError) as exc:
        return ParseResult([], u"", None, None, Outcome.ERROR,
                           u"could not open the file: %s" % exc)
    return read_bytes(data, filename=str(path))


def rewrite_bytes(result, shift=None, mapper=None):
    """Retime and re-encode, returning the new file's bytes.

    ⭐ The two properties that make this safe, and neither depends on anyone
    remembering a rule:

      * Only timestamp SPANS are replaced. Cue text, styles, fonts, embedded
        binary, VTT settings and NOTE blocks are copied through by slicing, so
        no code path exists that could alter them.
      * The ORIGINAL CODEC is written back. A Shift-JIS file goes out
        Shift-JIS. `encode_back` raises rather than substituting characters.

    ⚠ A zero shift must produce byte-identical output. That is asserted in the
    suite and it is the cheapest possible proof that the whitelist holds.
    """
    from ..cues import retime

    if not result.ok:
        raise ValueError("refusing to rewrite a file that did not read: %s"
                         % result.reason)
    if result.format not in WRITABLE_FORMATS:
        # ⛔ Refuse loudly, never drop silently. A bitmap subtitle is a timing
        # REFERENCE -- its image data is not ours to regenerate, and a caller
        # that believes it wrote one has a corrupt library and does not know.
        raise ValueError(
            "%r is readable as a timing reference but is not writable; "
            "writable formats are %s"
            % (result.format, ", ".join(sorted(WRITABLE_FORMATS))))
    if result.decoded is None:
        raise ValueError("no decode information; cannot write the same codec back")

    new_text = retime(result, shift=shift, mapper=mapper,
                      formatter=formatter_for(result))

    from ..encoding import encode_back
    return encode_back(new_text, result.decoded)


def write_file(path, data):
    """Atomic write. Never truncates the target.

    🚨 BITTEN TWICE (LEDGER-HOT.md): open(path,'w') truncates on open, so a
    write that then raises leaves ZERO BYTES. This is a user's subtitle file --
    the one thing in this project that is not disposable.
    """
    from ..paths import atomic_write_bytes
    atomic_write_bytes(path, data)


def formatter_for(result):
    """The timestamp formatter matching the file's own convention."""
    mod = TEXT_READERS.get(result.format)
    if mod is None:
        raise ValueError("no formatter for format %r" % result.format)
    return mod.make_formatter(result.text)


def _ext(filename):
    if not filename:
        return ""
    i = str(filename).rfind(".")
    return str(filename)[i:].lower() if i != -1 else ""
