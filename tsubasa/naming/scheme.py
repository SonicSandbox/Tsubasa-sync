# -*- coding: utf-8 -*-
r"""
Per-folder scheme inference. RUNBOOK step A4.

⭐ THE IDEA: A USER'S OWN FOLDER IS A LABELLED CORPUS OF ONE SHOW.

Across the files of one season, the release group, the resolution, the codec
and the year are CONSTANT. The episode number is the thing that MOVES. So the
episode column can be found without recognising a single pattern:

    [Coalgirls]_Bakemonogatari_01_(1920x1080_Blu-ray_FLAC)_[9787055F].ass
    [Coalgirls]_Bakemonogatari_02_(1920x1080_Blu-ray_FLAC)_[A1B2C3D4].ass
                                ^^ varies      ^^^^ ^^^^ constant

This is the mechanism the spec names for the cases no regex can reach
(spec/06-edge-cases.md §2.1):

    86 (Eighty-Six) · 91 Days · 07-Ghost · 18if
        -> "No regex resolves these. The identity index and per-folder scheme
            inference carry them."
    5-toubun no Hanayome · 3-gatsu no Lion · 100-man no Inochi
        -> "Leading number is part of the title. The FOLDER'S DOMINANT SCHEME
            disambiguates."

`86 - Eighty Six - 03` is unresolvable alone -- both numbers are plausible
episodes. In a folder it is trivial: `86` is in every filename and `03` is not.

⚠ It needs 2+ files of one show together, so it complements the parsers rather
than replacing them: parsers handle the loose file, inference handles the
folder, and neither is required for the other to work.

⛔ It infers, it does not decide. A scheme with weak evidence returns nothing
rather than a guess -- the whole point is to resolve cases the parsers got
wrong, and a bad inference would instead overrule cases they got right.
"""
import re
import unicodedata
from collections import Counter, defaultdict

DIGITS = "d"
WORD = "w"
CJK = "j"
SEP = "s"

_TOKEN = re.compile(
    u"(?P<d>\\d+)|(?P<w>[A-Za-z]+)|(?P<j>[぀-ヿ一-鿿]+)|(?P<s>[^0-9A-Za-z぀-ヿ一-鿿]+)")

# Numbers that are never episode numbers, however much they vary.
RESOLUTIONS = {240, 360, 480, 540, 576, 720, 1080, 1088, 1440, 2160, 4320,
               640, 848, 852, 854, 960, 1024, 1280, 1920, 3840, 2560}
CODEC_NUMS = {264, 265, 8, 10, 16, 24, 264, 265, 26}
MAX_EPISODE = 2000

# Minimum evidence before a scheme is believed at all.
#
# 🚨 THREE, not two. With two files a constant column passes the distinctness
# test by arithmetic alone -- 1 distinct of 2 is a ratio of 0.5, which is not
# `< 0.5` -- so `Show - 05.srt` and `Show - 05.ass` produced a confident
# `Scheme(slot=0, conf=0.75)` and `episode_of` answered 5 for both. On the NHK
# broadcast shape that same arithmetic promoted the `10` of `hevc10` into the
# episode slot, and probe 3 then learned it for 72 files of the template.
#
# ⚠ The cost is real and accepted: a folder holding exactly two files gets no
# scheme. That is the correct answer -- two files are not a corpus, and the
# parsers still cover them. Measured: fine shapes with >= 3 files agree on the
# episode slot **100% of the time** (6,732 of 6,734), which is where the
# evidence actually is.
MIN_FILES = 3
MIN_DISTINCT_RATIO = 0.5


class Scheme(object):
    """A filename shape, and which of its number slots holds the episode."""

    __slots__ = ("shape", "slot", "n_files", "confidence", "values", "reason")

    def __init__(self, shape, slot, n_files, confidence, values, reason=u""):
        self.shape = shape
        self.slot = slot
        self.n_files = n_files
        self.confidence = confidence
        self.values = values
        self.reason = reason

    def __repr__(self):
        return "Scheme(slot=%r, files=%d, conf=%.2f)" % (
            self.slot, self.n_files, self.confidence)


# 🚨 CRC32 tags must go BEFORE tokenising, not after. `[AAAAAAAA]` is one word
# token; `[9787055F]` is a number token followed by a word token. So two files
# from one release differ in their TYPE SEQUENCE, every file lands in its own
# shape group, no group ever reaches two files, and inference silently returns
# nothing at all -- which looks exactly like "this folder has no scheme".
#
# The spec already classifies a CRC tag as noise (§1.1). It carries no scheme
# information by construction: it is a checksum of the video.
_CRC = re.compile(r"[\[\(][0-9a-fA-F]{8}[\]\)]")
# `01v2` -- a version suffix would otherwise add a number slot to some files
# and not others, fragmenting the group the same way.
_VERSION = re.compile(r"(?<=\d)v\d\b")


def tokenize(name):
    """(shape, numbers) -- the type signature, and the digit runs in order.

    🚨 NFKC FIRST, and it is not cosmetic. The separator class below is
    "anything that is not a digit, a Latin letter, kana or kanji" -- and
    FULL-WIDTH digits are in it. So `正直不動産（０１）「…」` had its episode column
    eaten as punctuation: the raw numbers were `[1440, 10, 20, 8]` from the
    encoder tags, and inference happily promoted the `10` of `hevc10`.

    Measured on the non-sealed catalogue: **12,476 files (6.2%) carry a
    full-width episode marker** -- `（０１）`, `＃０１`, `第０１話`. The episode parser
    folded width from the start; this did not, and the two disagreed on every
    one of them.

    ⚠ Folding here also merges half-width katakana with full-width, which is
    the same show under two encodings and should have been one shape anyway.
    """
    name = unicodedata.normalize("NFKC", name)
    name = re.sub(r"\.[A-Za-z0-9]{2,4}$", "", name)
    name = _CRC.sub(" ", name)
    name = _VERSION.sub("", name)
    shape = []
    numbers = []
    for m in _TOKEN.finditer(name):
        for kind in (DIGITS, WORD, CJK, SEP):
            v = m.group(kind)
            if v is None:
                continue
            if kind == DIGITS:
                shape.append(DIGITS)
                numbers.append(int(v))
            elif kind == SEP:
                # Separators carry no identity and vary freely between
                # releases; collapsing them keeps two files in one shape group
                # when only the punctuation differs.
                shape.append(SEP)
            else:
                shape.append(kind)
                shape[-1] = "%s:%s" % (kind, v.lower())
            break
    return tuple(shape), numbers


def _looks_like_episodes(values, n_files):
    """Score a number slot on whether it behaves like an episode column."""
    if not values:
        return 0.0, u"no values"

    distinct = sorted(set(values))
    ratio = len(distinct) / float(len(values))

    if ratio < MIN_DISTINCT_RATIO:
        return 0.0, u"constant or near-constant (%d distinct of %d)" % (
            len(distinct), len(values))
    if any(v > MAX_EPISODE for v in distinct):
        return 0.0, u"values exceed %d -- a year or a resolution" % MAX_EPISODE
    if all(v in RESOLUTIONS for v in distinct):
        return 0.0, u"every value is a known resolution"

    # ⭐ A real episode column nearly fills its own range: 1..12 with 12
    # distinct values is dense; {720, 1080} is not, even though both vary.
    span = distinct[-1] - distinct[0] + 1
    density = len(distinct) / float(span) if span else 0.0

    penalty = 0.0
    if any(v in RESOLUTIONS for v in distinct):
        penalty += 0.4
    if all(1900 <= v <= 2100 for v in distinct):
        penalty += 0.6          # a year column varies across a folder too

    score = max(0.0, (0.5 * ratio + 0.5 * density) - penalty)
    return score, u"%d distinct, span %d, density %.2f" % (
        len(distinct), span, density)


def infer(filenames):
    """Filenames of ONE show -> {shape: Scheme}.

    Cost: one pass to tokenise, one dict group, one pass per number slot.
    Linear in total characters -- no pairwise comparison anywhere.
    """
    groups = defaultdict(list)
    for name in filenames:
        shape, numbers = tokenize(name)
        groups[shape].append((name, numbers))

    schemes = {}
    for shape, entries in groups.items():
        if len(entries) < MIN_FILES:
            continue
        n_slots = min(len(nums) for _n, nums in entries)
        if n_slots == 0:
            continue

        best_slot, best_score, best_reason, best_values = None, 0.0, u"", []
        for slot in range(n_slots):
            values = [nums[slot] for _n, nums in entries]
            score, reason = _looks_like_episodes(values, len(entries))
            if score > best_score:
                best_slot, best_score = slot, score
                best_reason, best_values = reason, values

        if best_slot is None:
            continue
        schemes[shape] = Scheme(shape, best_slot, len(entries), best_score,
                                best_values, best_reason)
    return schemes


def episode_of(name, schemes):
    """Episode for `name` using an inferred scheme, or None.

    ⛔ Returns None rather than guessing when the shape is unknown or the
    scheme's evidence is weak. Overruling a parser that was right is worse than
    declining to help one that was wrong.
    """
    shape, numbers = tokenize(name)
    sch = schemes.get(shape)
    if sch is None or sch.slot >= len(numbers):
        return None
    if sch.confidence < 0.5:
        return None
    return numbers[sch.slot]


def dominant(schemes):
    """The scheme covering the most files -- the folder's house style."""
    if not schemes:
        return None
    return max(schemes.values(), key=lambda s: (s.n_files, s.confidence))


def resolve_folder(filenames):
    """{filename: episode or None} for a whole folder, by inference alone.

    ⚠ Deliberately does NOT consult the parsers. This is the independent
    second opinion the arbitration step compares against; folding the parsers
    in here would make the two agree by construction and prove nothing.
    """
    schemes = infer(filenames)
    return {name: episode_of(name, schemes) for name in filenames}, schemes
