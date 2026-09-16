# -*- coding: utf-8 -*-
"""
Text encoding: sniff it, decode it strictly, and write the SAME codec back.

🚨 This module exists because of the worst bug this class of tool can have, and
`subsync` shipped it:

    A Shift-JIS caption decoded with errors="replace" had all 346 cues turn
    into U+FFFD.  Timestamps are ASCII so they survived -- the alignment scored
    4x chance, the tool reported CONFIDENT, and it wrote a file that plays with
    perfect timing and no readable text.

Two rules follow, and neither is negotiable (spec/03-permissions.md):

  ⛔ NEVER decode with errors="replace" or errors="ignore".  A lossy decode
     produces a plausible-looking string, and every check downstream passes on
     it.  Decode strictly and fall through the ladder; `latin-1` is the
     byte-exact last resort precisely because it round-trips every byte even
     when the guess is wrong.

  ⛔ NEVER convert the encoding.  Same codec in, same codec out.

The ladder (spec/06-edge-cases.md §6.3):

    BOM -> UTF-16-without-BOM by null density -> UTF-8 strict
        -> plausibility-scored candidates -> latin-1

⚠ The scored step is the subtle one.  Shift-JIS and Big5 both decode many of
the same byte sequences "successfully", so FIRST-SUCCESS IS NOT DETECTION -- it
just returns whichever codec you happened to try first.  Candidates are scored
on whether the characters they produce look like real text.
"""
import re
import unicodedata

# Byte-order marks, longest first: UTF-32-LE's BOM starts with UTF-16-LE's.
BOMS = [
    (b"\x00\x00\xfe\xff", "utf-32-be"),
    (b"\xff\xfe\x00\x00", "utf-32-le"),
    (b"\xef\xbb\xbf", "utf-8-sig"),
    (b"\xfe\xff", "utf-16-be"),
    (b"\xff\xfe", "utf-16-le"),
]

# Tried in order, but every one that decodes is SCORED -- see pick_by_plausibility.
CANDIDATES = [
    "utf-8",
    "cp932",        # Shift-JIS as Windows actually writes it
    "shift_jis",
    "euc-jp",
    "iso-2022-jp",
    "gb18030",      # supersets gbk/gb2312
    "big5",
    "euc-kr",
    "cp1251",       # Cyrillic
    "koi8-r",
    "cp1252",       # Western European
    "iso-8859-2",
    "cp874",        # Thai
    "cp1256",       # Arabic
]

_MOJIBAKE_HALFWIDTH = re.compile("[ｦ-ﾟ]{3,}")


class DecodeResult(object):
    """What was read, and everything needed to write the same bytes back."""

    __slots__ = ("text", "encoding", "bom", "how", "score", "candidates")

    def __init__(self, text, encoding, bom=b"", how="", score=0.0, candidates=None):
        self.text = text
        self.encoding = encoding
        self.bom = bom
        self.how = how
        self.score = score
        self.candidates = candidates or []

    def __repr__(self):
        return "DecodeResult(%r, how=%r, score=%.3f)" % (
            self.encoding, self.how, self.score)


class UndecodableError(ValueError):
    """Nothing in the ladder could read these bytes.

    ⛔ This is ERROR ("could not read the file"), which is a DIFFERENT outcome
    from parsing zero cues.  Conflating those two shipped twice in subsync and
    both times a real failure disguised itself as something else
    (spec/03-permissions.md §The three outcomes).
    """


# --------------------------------------------------------------------------
# plausibility
# --------------------------------------------------------------------------

def plausibility(text):
    """How much does this look like real subtitle text? 0.0 - 1.0.

    Scored on character CLASS, not on whether the decode raised.  A wrong codec
    usually decodes fine and produces characters nobody writes: private-use
    glyphs, stray control codes, or long runs of half-width katakana -- the
    classic signature of Japanese text read through the wrong table.
    """
    if not text:
        return 0.0

    good = bad = 0
    for ch in text:
        o = ord(ch)
        if ch in "\n\r\t":
            good += 1
        elif o < 0x20:
            bad += 2                      # control characters in a text file
        elif o == 0xFFFD:
            bad += 5                      # replacement char: a lossy decode
        elif 0x20 <= o < 0x7F:
            good += 1                     # ASCII
        elif 0xE000 <= o <= 0xF8FF:
            bad += 3                      # private use area
        elif 0x3040 <= o <= 0x30FF:
            good += 1                     # kana
        elif 0x4E00 <= o <= 0x9FFF:
            good += 1                     # CJK unified
        elif 0xAC00 <= o <= 0xD7AF:
            good += 1                     # hangul
        elif 0x0400 <= o <= 0x04FF:
            good += 1                     # cyrillic
        elif 0x0600 <= o <= 0x06FF:
            good += 1                     # arabic
        elif 0xFF01 <= o <= 0xFF60:
            good += 1                     # full-width forms
        else:
            cat = unicodedata.category(ch)
            if cat in ("Cn", "Co", "Cs"):
                bad += 3                  # unassigned / private / surrogate
            elif cat.startswith("L") or cat.startswith("N") or cat.startswith("P"):
                good += 1
            elif cat.startswith("Z") or cat.startswith("S") or cat.startswith("M"):
                good += 1
            else:
                bad += 1

    # Long half-width katakana runs are how Japanese looks through a wrong
    # table.  Real subtitles occasionally use one or two; they do not use ten.
    for run in _MOJIBAKE_HALFWIDTH.findall(text):
        bad += len(run)

    total = good + bad
    return (good / float(total)) if total else 0.0


def _looks_utf32_without_bom(data):
    """UTF-32 with no BOM: three NUL bytes in every group of four.

    Checked BEFORE the UTF-16 test, because a UTF-32 file is also null-heavy
    and the UTF-16 detector would otherwise claim it and decode garbage.
    Python's `utf-32-le`/`utf-32-be` codecs emit no BOM, so a file written by
    anything explicit about endianness arrives here rather than at the BOM
    table.
    """
    head = data[:4096]
    head = head[:len(head) - (len(head) % 4)]
    if len(head) < 8:
        return None

    # ⚠ TWO nulls per quad, not three. Every BMP codepoint is <= U+FFFF, so the
    # high half is always zero -- but the low half is NOT: `第` is U+7B2C, which
    # is 00 00 7B 2C big-endian. Testing for three nulls only matches ASCII and
    # silently fails on the CJK this project exists to handle.
    groups = len(head) // 4
    le = be = 0
    for i in range(0, len(head), 4):
        quad = head[i:i + 4]
        if quad[2] == 0 and quad[3] == 0:
            le += 1
        if quad[0] == 0 and quad[1] == 0:
            be += 1

    # Demand near-unanimity: a stray run of nulls in a latin-1 file must not
    # be enough to reinterpret the whole thing.
    if le >= groups * 0.9 and le > be:
        return "utf-32-le"
    if be >= groups * 0.9 and be > le:
        return "utf-32-be"
    return None


def _looks_utf16_without_bom(data):
    """UTF-16 with no BOM shows as nulls in every other byte.

    Checked BEFORE the codec ladder: such a file often decodes "successfully"
    as latin-1 or cp1252 into text full of NUL characters, which then parses to
    zero cues and reads as an empty file rather than a misread one.
    """
    head = data[:4096]
    if len(head) < 4:
        return None
    nulls = head.count(0)
    if nulls * 4 < len(head):             # fewer than ~25% nulls: not utf-16
        return None
    even = sum(1 for i in range(0, len(head) - 1, 2) if head[i] == 0)
    odd = sum(1 for i in range(1, len(head), 2) if head[i] == 0)
    if odd > even * 2:
        return "utf-16-le"
    if even > odd * 2:
        return "utf-16-be"
    return None


def pick_by_plausibility(data, candidates=None):
    """Score every codec that decodes, and return the best.

    ⭐ Not first-success.  Shift-JIS and Big5 both decode many of the same byte
    sequences without raising, so returning the first that works returns
    whichever one is earlier in the list -- a coin flip dressed as detection.
    """
    scored = []
    for codec in (candidates or CANDIDATES):
        try:
            text = data.decode(codec)
        except (UnicodeDecodeError, LookupError):
            continue
        scored.append((plausibility(text), codec, text))

    if not scored:
        return None
    # Stable: ties break toward the earlier candidate, which is the more common
    # encoding.  Sorting on score alone would make the answer depend on dict
    # ordering.
    best = max(range(len(scored)), key=lambda i: (scored[i][0], -i))
    score, codec, text = scored[best]
    return score, codec, text, [(c, round(s, 3)) for s, c, _t in scored]


# --------------------------------------------------------------------------
# the ladder
# --------------------------------------------------------------------------

def sniff_and_decode(data):
    """bytes -> DecodeResult.  Raises UndecodableError if nothing reads them."""
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError("sniff_and_decode takes bytes, not %s" % type(data).__name__)
    data = bytes(data)

    if data == b"":
        # An empty file is READABLE and contains zero cues. That is not an
        # ERROR, and calling it one is the exact conflation this project has
        # shipped twice.
        return DecodeResult(u"", "utf-8", b"", "empty file", 1.0)

    # 1. BOM -- an explicit declaration, and it wins outright.
    for bom, codec in BOMS:
        if data.startswith(bom):
            body = data if codec == "utf-8-sig" else data[len(bom):]
            try:
                text = body.decode(codec) if codec == "utf-8-sig" else body.decode(codec)
                return DecodeResult(
                    text, codec, b"" if codec == "utf-8-sig" else bom,
                    "byte-order mark", 1.0)
            except UnicodeDecodeError:
                # A BOM followed by bytes that are not that encoding. Rare and
                # broken; keep going rather than trusting the marker.
                break

    # 2. Fixed-width Unicode with no BOM, by null density. UTF-32 first -- it
    #    is also null-heavy, so the UTF-16 test would claim it and decode junk.
    guess = _looks_utf32_without_bom(data)
    if guess:
        try:
            return DecodeResult(data.decode(guess), guess, b"",
                                "null density (utf-32, no BOM)", 1.0)
        except UnicodeDecodeError:
            pass

    guess = _looks_utf16_without_bom(data)
    if guess:
        try:
            return DecodeResult(data.decode(guess), guess, b"",
                                "null density (utf-16, no BOM)", 1.0)
        except UnicodeDecodeError:
            pass

    # 3. UTF-8 strict. By far the common case, and unambiguous when it works:
    #    invalid UTF-8 sequences are rejected, so a success is strong evidence.
    try:
        text = data.decode("utf-8")
        return DecodeResult(text, "utf-8", b"", "utf-8, strict", 1.0)
    except UnicodeDecodeError:
        pass

    # 4. Scored candidates.
    picked = pick_by_plausibility(data)
    if picked:
        score, codec, text, all_scores = picked
        # A very low best score means every candidate produced junk. Prefer the
        # byte-exact fallback over confidently-wrong text.
        if score >= 0.80:
            return DecodeResult(text, codec, b"", "plausibility-scored",
                                score, all_scores)

    # 5. latin-1 -- the byte-exact last resort. Every byte maps to a codepoint,
    #    so decode->encode round-trips exactly even though the characters are
    #    probably wrong. That preserves the user's bytes, which is the thing
    #    that actually matters.
    text = data.decode("latin-1")
    return DecodeResult(text, "latin-1", b"", "latin-1 byte-exact fallback",
                        plausibility(text),
                        picked[3] if picked else [])


def encode_back(text, decoded):
    """Re-encode with the codec it was read as, BOM included.

    ⛔ Raises rather than substituting characters.  If the edited text cannot be
    written in the original codec, that is a refusal the caller must handle --
    silently swapping to UTF-8 is the bug at the top of this file.
    """
    body = text.encode(decoded.encoding)
    return decoded.bom + body


def round_trips(data):
    """Would reading and re-writing these bytes reproduce them exactly?

    Used as an assertion at read time.  If it is False the file is one we can
    read but must not rewrite, and knowing that BEFORE touching a user's file
    is the entire point.
    """
    try:
        d = sniff_and_decode(data)
    except UndecodableError:
        return False
    try:
        return encode_back(d.text, d) == data
    except (UnicodeEncodeError, LookupError):
        return False
