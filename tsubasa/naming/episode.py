# -*- coding: utf-8 -*-
r"""
Episode and season extraction from a filename. RUNBOOK step A2.

⭐ THE CENTRAL FINDING, and it is not intuitive: **an episode number is not
always missing by mistake.** ~8% of the corpus parses to nothing under all
three parsers, and inspection shows it is overwhelmingly films, specials and
OVAs that CORRECTLY have no episode number (spec/09-corpus-strategy.md).

    ⛔ A film is NOT a parser failure. Any coverage metric that counts one is
       chasing a target that should not move.

So this module returns a KIND, not merely a number:

    EPISODE      an episode number was found
    FILM         no episode, and that is correct -- pair by title + duration
    BATCH        a range (`01~12`); refuse to assign an episode
    CONJUNCTION  🚨 TWO SHOWS in one file; refuse rather than pick a half
    UNKNOWN      an episode is probably there and we did not find it
                 -- the ONLY one of these that is a defect

🚨 The ≥1000 bug, verified against real files: `(\d{1,3})` caps at 999, so
`[SubsPlease] One Piece - 1121` parses to episode None **and** the number is
absorbed into the title as `onepiece1121`, so it cannot match other One Piece
episodes by title either. The fix is `(\d{1,4})` PLUS stripping resolutions
first, or `1080` becomes episode 1080.

⚠ `0` is a valid episode (OVAs, prologues) and is falsy. Every check is
`is not None`, never truthiness.
"""
import re
import unicodedata
from collections import Counter

from .normalize import normalize
# ⚠ The numeric-sanity tables live in scheme.py and are imported, not copied.
# Two lists of "numbers that are never episodes" would drift, and the stale one
# is the one somebody reads. scheme.py imports nothing from here, so the
# dependency is one-way and its "does not consult the parsers" claim holds --
# a constant table is not a parser.
from .scheme import CODEC_NUMS, MAX_EPISODE, RESOLUTIONS

EPISODE = "episode"
FILM = "film"
BATCH = "batch"
CONJUNCTION = "conjunction"
UNKNOWN = "unknown"


class Parsed(object):
    """What one parser made of one filename."""

    __slots__ = ("title", "episode", "episode_end", "season", "kind",
                 "reason", "source", "group", "extras")

    def __init__(self, title=u"", episode=None, episode_end=None, season=None,
                 kind=UNKNOWN, reason=u"", source=u"", group=None, extras=None):
        self.title = title
        self.episode = episode
        self.episode_end = episode_end
        self.season = season
        self.kind = kind
        self.reason = reason
        self.source = source
        self.group = group
        self.extras = extras or {}

    @property
    def has_episode(self):
        return self.episode is not None      # ⚠ never truthiness: 0 is valid

    def key(self):
        """(season, episode) -- what candidate grouping must use.

        🚨 Episode ALONE manufactured 305 false pairs on multi-season shows:
        Series 1 Episode 3 scored against Series 3 Episode 3. Made three
        separate times in one session (LEDGER.md §Harness).
        """
        return (self.season, self.episode)

    def __repr__(self):
        return "Parsed(%r, s=%r, e=%r, %s, via=%s)" % (
            self.title[:28], self.season, self.episode, self.kind, self.source)


# --------------------------------------------------------------------------
# noise
# --------------------------------------------------------------------------

# ⚠ ORDER MATTERS. Resolutions go first: with `(\d{1,4})` for episodes, a
# surviving `1080` reads as episode 1080.
NOISE = [
    # resolutions, as WxH and as shorthand
    r"\b\d{3,4}\s*[xX×]\s*\d{3,4}\b",
    r"\b(?:2160|1440|1080|1088|720|576|540|480|360)[pi]\b",
    r"\b4k\b", r"\buhd\b", r"\bfhd\b", r"\bhd\b", r"\bsd\b",
    # audio layouts BEFORE generic codec words -- `DDP5.1` contains a dot and
    # sits next to patterns that read trailing numbers as episodes. Measured at
    # 9% of Western release names and the concrete false-positive risk.
    r"\b(?:ddp?|dd\+|eac3|ac3|aac|dts(?:-?hd)?|truehd|atmos|flac|opus|mp3|pcm)"
    r"(?:\s*\d\.\d)?\b",
    r"\b\d\.\d\s*(?:ch|channels?)\b",
    # 🚨 An audio layout is ATTACHED to its codec: `DDP5.1`, `AAC2.0`. A bare
    # `\d.\d` also matches a HALF EPISODE -- `Show - 7.5` -- and stripping it
    # here deleted the number before P_HALF ever ran, so `13.5` worked and
    # `7.5` returned nothing. Require a letter immediately before.
    r"(?<=[A-Za-z])\d\.\d\b",
    # video codecs
    r"\b(?:x|h)\.?26[45]\b", r"\bhevc\b", r"\bavc\b", r"\bav1\b", r"\bvp9\b",
    r"\bxvid\b", r"\bdivx\b", r"\bmpeg-?\d\b", r"\bqsv\d*\b", r"\bnvenc\b",
    # bit depth
    r"\b(?:hi10p?|ma10p?|10\s*bits?|8\s*bits?|10bit|8bit)\b",
    # source
    r"\b(?:bd(?:rip|mv|box)?|blu-?ray|web-?dl|web-?rip|web|hdtv|tvrip|"
    r"dvd(?:rip|iso)?|r2j?|r2dvd|remux|vhs|laserdisc|ld)\b",
    # frame rate and misc
    r"\b\d{2,3}(?:\.\d+)?\s*fps\b", r"\bcrf\s*\d+\b", r"\byadif\d*\b",
    r"\bkfmvfr\b", r"\bvfr\b", r"\bcfr\b",
    # CRC32 -- stripped for parsing, captured as an identity key elsewhere
    r"\[[0-9a-fA-F]{8}\]",
    r"\[(?:cc|sdh|forced)\]",
    r"(?:字幕|外挂|内嵌|简体|繁體|简日|繁日)",
]
NOISE_RE = [re.compile(p, re.IGNORECASE) for p in NOISE]

# 🚨 A SHORT AMBIGUOUS TOKEN IS ONLY NOISE IN A TAG CONTEXT.
#
# Found by review. Stripping these as bare words corrupted real titles:
#
#     Kingsglaive - Final Fantasy XV  ->  'Kingsglaive Fantasy XV'   ("final")
#     Bakemono no Ko                  ->  'Bakemono no'              ("ko")
#     Ja Ja Uma - 05                  ->  'Uma'                      ("ja")
#     Mad Max Fury Road               ->  'Mad Fury Road'            ("max")
#
# The first is spec/09-corpus-strategy.md's own example of a legitimate film
# title, and `Gintama Final` is a real season. A two-letter language code and a
# word in a title are the same characters -- only the CONTEXT differs.
#
# ⭐ So these are stripped only when bracketed, dot-delimited, or trailing after
# a dot: `.ja[cc].srt`, `[1080p NF WEB-DL]`, `Inception.2010.1080p.BluRay`.
# Left alone when they are simply words in a name.
_SOFT = (r"repack|proper|internal|extended|uncut|limited|complete|final|remux"
         r"|nf|amzn|dsnp|hmax|atvp|max|cr|funi|hulu|netflix|amazon|disney"
         r"|ja|jp|jpn|en|eng|zh|chs|cht|kor|ko|cc|sdh|forced|字")
_PLATFORM = r"nf|amzn|dsnp|hmax|atvp"

SOFT_NOISE_RE = [
    re.compile(r"(?<=[\[\(])\s*(?:%s)\s*(?=[\]\)])" % _SOFT, re.I),
    re.compile(r"(?<=\.)(?:%s)(?=[.\[\]])" % _SOFT, re.I),
    re.compile(r"\.(?:%s)$" % _SOFT, re.I),
    re.compile(r"(?<=[\s\[])(?:%s)(?=[\s\]])" % _PLATFORM, re.I),
]

# 🚨 A group name can be a LEADING bracket (dominant in anime, 1% of Western
# names) or a TRAILING suffix after a hyphen (33% of 904 Western release
# names). subsync handled only the first. Both cultures must work.
LEADING_GROUP = re.compile(r"^\s*[\[\(【]([^\]\)】]{1,40})[\]\)】]\s*")
TRAILING_GROUP = re.compile(r"-\s*([A-Za-z0-9_]{2,20})\s*$")

# 🚨 ` (2)` … ` (35)` IS A FILESYSTEM COLLISION SUFFIX, NEVER AN EPISODE.
#
# Windows, browsers and track extractors append it when a name already exists,
# so one video's language tracks come out as `Bleach - 162.sup`,
# `Bleach - 162 (2).sup`, `Bleach - 162 (3).sup`. It is the shape of Sonic's
# own library, and the bracket-of-pure-digits rule takes the LAST match, so
# the suffix won.
#
# Measured 2026-09-08 over the non-sealed video corpus: 2,602 files carry the
# suffix on a base that parses, and **2,108 of them (81.0%) got the wrong
# episode**. Stripping it first takes that to zero -- and the series title
# stops carrying the real episode number as a side effect.
#
# ⚠ Two digits, at the very end, after a space. `Show (2019)` is a year and is
# four digits; `Kimi no Na wa. (2016)` is untouched.
P_DUP_SUFFIX = re.compile(r"\s\((\d{1,2})\)\s*$")

# Every extension `parse_ours` peels before it reads a title.
#
# ⛔ The video half is IMPORTED from `container.KNOWN_VIDEO_EXT`, never retyped
# here: one definition, so adding a format in one place cannot leave the parser
# behind. The subtitle half is listed because `formats/` keys its readers on
# them individually and has no single exported set to borrow.
_SUBTITLE_EXT = ("srt", "ass", "ssa", "vtt", "sub", "idx", "sup", "sbv",
                 "smi", "ttml", "dfxp", "itt", "stl")


def _ext_pattern():
    from ..container import KNOWN_VIDEO_EXT
    every = sorted(set(_SUBTITLE_EXT)
                   | {e.lstrip(".") for e in KNOWN_VIDEO_EXT},
                   key=len, reverse=True)
    return re.compile(r"\.(%s)$" % "|".join(re.escape(e) for e in every),
                      re.IGNORECASE)


_EXT_RE = _ext_pattern()


def fold_width(name):
    """Full-width -> half-width, for pattern matching only.

    🚨 Measured on the corpus and it is the single largest miss class: Japanese
    broadcast recordings write the episode in FULL-WIDTH parentheses and
    FULL-WIDTH digits --

        花子とアン（０７６）「その恋、忘れられますか？」
        あまちゃん（１０９）「おらのハート、再点火」
        書けないッ！？～脚本家・吉丸圭佑の筋書きのない生活～ ＃05

    `（０７６）` shares not one codepoint with `(076)`, so every ASCII pattern
    misses it. NFKC folds the digits, the parens and the ＃ in one step.

    ⚠ Applied to a COPY used for matching. The original name is untouched --
    the filename is half the test corpus and must not be normalised on disk.
    """
    return unicodedata.normalize("NFKC", name)


def strip_noise(name):
    # Soft (context-dependent) tokens FIRST, while the brackets and dots that
    # identify them as tags are still in place. The hard patterns remove some
    # of that punctuation, so running them first would destroy the evidence.
    for pat in SOFT_NOISE_RE:
        name = pat.sub(" ", name)
    for pat in NOISE_RE:
        name = pat.sub(" ", name)
    return re.sub(r"\s{2,}", " ", name).strip()


# --------------------------------------------------------------------------
# episode patterns, in priority order
# --------------------------------------------------------------------------

# 🚨 `第N話` OUTRANKS a platform's `S##E##`. `NARUTO…疾風伝.S06E01.第113話` is
# episode 113; reading the S06E01 gives 1 and it never pairs.
P_JA_EPISODE = re.compile(u"第\\s*(\\d{1,4})\\s*[話话回]")
P_SXXEXX = re.compile(r"[sS](\d{1,3})\s*[eE](?:[pP])?\s*(\d{1,4})")
P_SEASON_X_EP = re.compile(r"(?<![\w])(\d{1,2})\s*[xX]\s*(\d{1,3})(?![\w])")
P_EP_WORD = re.compile(r"\b(?:ep|episode|epis[oó]dio|話数)\s*[-. ]?\s*(\d{1,4})\b",
                       re.IGNORECASE)
# 🚨 A BARE `E##` IS AN EPISODE MARKER -- and it is the third most common
# naming scheme on jimaku.cc, which had no pattern here at all.
#
#     Yumeiro Patissiere SP Professional - E13 [TV].srt
#     [Zoro.to] Ascendance of a Bookworm - E01.srt
#     ヒロイック・エイジ.E25.Bandai.ja.srt
#
# Measured 2026-09-08 across 201,785 non-sealed catalogue files: adding this
# one pattern takes `unknown` from **10.6% to 2.4%**, and takes the share of
# series TITLES still carrying an episode token from **9.1% to 0.9%** -- which
# is the half the parser gate could never see, because another parser rescued
# the episode while the title stayed wrong and two files of one show looked
# like two different shows.
#
# ⚠ IT MUST SIT ABOVE THE POSITIONAL PATTERNS. `Kamen Rider 555 - E30 [TV]`
# returned episode **555**: with no marker to match, the dash/trailing walk
# took the title's own number.
#
# ⛔ Both lookarounds are load-bearing. An `E` glued to a letter or a digit is
# not a marker: `hevc10` (letter before), `[E27C3F25]` (letter after).
P_BARE_E = re.compile(r"(?<![A-Za-z0-9])[eE](\d{1,4})(?:v\d)?(?![A-Za-z0-9])")
P_BRACKET_DIGITS = re.compile(r"[\[\(](\d{1,4})(?:v\d)?[\]\)]")
# `＃05` folds to `#05` -- common in Japanese broadcast recordings.
P_HASH = re.compile(r"#\s*(\d{1,4})(?![\d])")
# ` - 05`, `_05_`, `.05.`, and 🚨 `tsukaiyou-01` -- a hyphen attached directly
# to a word, with no separating space. Found by Probe A and common.
P_DASH = re.compile(r"(?:^|[\s._\-])[-–—]?\s*(\d{1,4})(?:v\d)?(?=[\s._\-\[\(]|$)")
P_TRAILING = re.compile(r"(?:^|[\s._])(\d{1,4})(?:v\d)?\s*$")

# Ranges and conjunctions -- both REFUSE rather than pick.
P_BATCH = re.compile(r"(?<![\w])(\d{1,4})\s*[~〜～]\s*(\d{1,4})(?![\w])")
P_DOUBLE = re.compile(r"(?<![\w])(\d{1,4})\s*[-+&]\s*(\d{1,4})(?![\w])")
P_CONJUNCTION = re.compile(
    r"[sS]\d{1,2}\s*[eE][pP]?\d{1,3}.{0,24}?[&＆].{0,24}?[sS]\d{1,2}\s*[eE][pP]?\d{1,3}")

# Films and specials CORRECTLY have no episode number.
P_FILM = re.compile(
    u"(?:\\b(?:movie|film|gekijou-?ban|theatrical|director'?s?\\s*cut|"
    u"making[- ]of|special|ova|oad|ona|picture\\s*drama|recap|"
    u"complete\\s*season)\\b|劇場版|特別編|特別版|総集編|映画|短編)",
    re.IGNORECASE)
# A date IS the identifier for a broadcast recording. Never read `08` as an
# episode from one.
P_DATE = re.compile(r"(?<![\d])(20\d{2})[.\-/年]\s*(\d{1,2})[.\-/月]\s*(\d{1,2})日?(?![\d])")

# 🚨 A RELEASE YEAR IS NEVER AN EPISODE NUMBER.
#
# Found by review, and it is a Rule 2 violation -- a confidently wrong answer
# on the launch movie use case (spec/06 §3.5):
#
#     Inception (2010).en.srt           -> ep=2010
#     Blade Runner (1982) [Final Cut]   -> ep=1982
#     君を愛したひとりの僕へ.2022.srt            -> ep=2022
#
# That last file is spec/09-corpus-strategy.md's OWN example of a file that
# correctly has no episode number. Worse than a miss: two different films both
# key to (None, 2010), so an episode-keyed index buckets a whole film library
# under one fabricated episode.
#
# ⚠ 1900-2100 only, and only when the number stands alone as a year -- One
# Piece really does reach episode 1121, and `Show - 2010` in a folder of
# four-digit episodes is a different thing from `Inception (2010)`.
YEAR_MIN, YEAR_MAX = 1900, 2100
P_YEAR_STANDALONE = re.compile(r"[\[\(（]\s*((?:19|20)\d{2})\s*[\]\)）]")
# ⭐ A year delimited by dots or spaces, the dominant Western release form:
# `Inception.2010.1080p.BluRay.x264-GROUP`. Without this the file has no
# episode AND no film marker, so it lands in MISSED -- reported as a parser
# defect when it is a film that correctly has no episode number. Measured: it
# was 73.9% of the 904 Western release names.
P_YEAR_TOKEN = re.compile(r"(?:^|[.\s_\-\[\(])((?:19|20)\d{2})(?:$|[.\s_\-\]\)])")


def _is_year(value, name):
    """Is this number a release year rather than an episode?

    Two signals, and either is enough:
      * it sits alone in brackets -- `(2010)`, `[1982]`
      * it is in the year range AND the name carries no episode marker
    """
    if not (YEAR_MIN <= value <= YEAR_MAX):
        return False
    for m in P_YEAR_STANDALONE.finditer(name):
        if int(m.group(1)) == value:
            return True
    # A bare four-digit year in a dotted release name: `Inception.2010.1080p`.
    return bool(re.search(r"(?<![\w])%d(?![\w])" % value, name))

# Season markers that are season-level and never episode-level.
P_SEASON_WORD = re.compile(
    r"\b(?:s|season|series|cour|part|pt)\s*[-. ]?\s*(\d{1,2})\b", re.IGNORECASE)
P_SEASON_ORDINAL = re.compile(
    r"\b(\d{1,2})(?:nd|rd|th|st)\s*(?:season|series)\b", re.IGNORECASE)
P_SEASON_ROMAN = re.compile(r"\b(?:season\s*)?(II|III|IV|V|VI)\b")
ROMAN = {"II": 2, "III": 3, "IV": 4, "V": 5, "VI": 6}

# Half episodes: 13.5, 7.5. A real, distinct episode key.
P_HALF = re.compile(r"(?<![\w.])(\d{1,4})\.(5)(?![\d])")


def _int(s):
    return int(s.lstrip("0") or "0")       # leading zeros: 007 == 7


def parse_ours(filename):
    """Our own parser. One of three -- see `union` below.

    Returns a Parsed whose `kind` says what sort of thing this is, because
    "no episode" is a legitimate answer for a film and a defect for a series.
    """
    # 🚨 VIDEO EXTENSIONS TOO, AND THEIR ABSENCE WAS A LIVE DEFECT.
    #
    # This stripped subtitle extensions only, so **every video filename kept
    # its container suffix inside the title**:
    #
    #     Inception (2010).mkv      ->  title 'Inception mkv'
    #     Inception (2010).en.srt   ->  title 'Inception'
    #
    # ⚠ Invisible on the episode path, because truncating at the episode marker
    # eats the tail anyway — so it survived 98 naming checks and a 96.8% parser
    # gate. On the MOVIE path there is no marker, so it hit **every video in a
    # film library**: the same *survives-by-prefix* shape `06-edge-cases.md`
    # §3.5 records for language tags, arriving on the other side of the pair.
    # Found by RUNBOOK A10.
    #
    # ⛔ THE SET IS IMPORTED, NOT RETYPED. `container.KNOWN_VIDEO_EXT` is the
    # one definition; a second copy here would drift the day a format is added,
    # and `doctrine/tooling` §anti-rederivation is explicit about that.
    name = _EXT_RE.sub("", filename)
    name = name.replace("\\", "/").rsplit("/", 1)[-1]
    # Full-width digits and brackets, folded for matching only.
    name = fold_width(name)
    # 🚨 The collision suffix goes BEFORE anything reads a number -- see
    # P_DUP_SUFFIX. Leaving it in place made 81% of a real library's duplicate
    # tracks report the copy index as the episode.
    name = P_DUP_SUFFIX.sub("", name)

    group = None
    m = LEADING_GROUP.match(name)
    if m:
        group = m.group(1)
        name = name[m.end():]
    else:
        m = TRAILING_GROUP.search(name)
        if m and not m.group(1).isdigit():
            group = m.group(1)

    # 🚨 Two shows in one file: refuse before anything else, or we confidently
    # retime someone else's episode.
    if P_CONJUNCTION.search(name):
        return Parsed(name, kind=CONJUNCTION, source="ours", group=group,
                      reason=u"two series and two episode numbers in one file")

    working = strip_noise(name)

    # ⚠ Find the season AND REMOVE IT from the working string before looking
    # for an episode. `Show Part 2 - 05` otherwise reads episode 2: the season
    # digit is a perfectly good match for every positional episode pattern.
    season = None
    for pat in (P_SEASON_ORDINAL, P_SEASON_WORD):
        m = pat.search(working)
        if m:
            season = _int(m.group(1))
            working = working[:m.start()] + " " + working[m.end():]
            break
    if season is None:
        m = P_SEASON_ROMAN.search(working)
        if m:
            season = ROMAN.get(m.group(1))
            if season is not None:
                working = working[:m.start()] + " " + working[m.end():]

    # Batch ranges: no single episode exists.
    m = P_BATCH.search(working)
    if m:
        return Parsed(working, kind=BATCH, season=season, source="ours",
                      group=group,
                      reason=u"a range (%s-%s), not one episode"
                             % (m.group(1), m.group(2)))

    # Explicit patterns, highest authority first.
    # `cut` records WHERE the marker was, so the series title can be taken as
    # everything before it rather than everything except it -- see _title_from.
    episode = episode_end = cut = None
    m = P_JA_EPISODE.search(name)          # on the RAW name: 第113話 survives
    if m:                                  # noise stripping either way
        episode = _int(m.group(1))
        # 🚨 AND THE CUT HAS TO BE TAKEN FROM `working`, NOT FROM THIS MATCH.
        #
        # This branch searches the RAW `name` so noise stripping cannot eat
        # `第113話`, which means `m.start()` indexes a DIFFERENT string from the
        # one `_title_from` slices. So `cut` was simply never set here -- and
        # the title kept everything:
        #
        #     ワンピース.S10E026.第1025話 最悪の世代全滅！
        #     -> title `ワンピース S10E026 第1025話 最悪の世代全滅!`
        #
        # ⭐ Found by RUNBOOK A2b+'s title gate, which measured **6.45% of the
        # catalogue** carrying an episode marker in its series key -- the exact
        # defect `parsergate` cannot see, because the episode came out RIGHT.
        # One Piece and Naruto Shippuuden are both in it.
        m2 = P_JA_EPISODE.search(working)
        if m2:
            cut = m2.start()
    if episode is None:
        m = P_SXXEXX.search(working)
        if m:
            season, episode = _int(m.group(1)), _int(m.group(2))
            cut = m.start()
    if episode is None:
        m = P_SEASON_X_EP.search(working)
        if m:
            season, episode = _int(m.group(1)), _int(m.group(2))
            cut = m.start()
    if episode is None:
        m = P_EP_WORD.search(working)
        if m:
            episode = _int(m.group(1))
            cut = m.start()
    if episode is None:
        # ⭐ Above the positional patterns, below every explicit season code.
        m = P_BARE_E.search(working)
        if m:
            episode = _int(m.group(1))
            cut = m.start()
    if episode is None:
        m = P_HASH.search(working)
        if m:
            episode = _int(m.group(1))
            cut = m.start()
    if episode is None:
        m = P_HALF.search(working)
        if m:
            episode = float("%s.5" % _int(m.group(1)))
            cut = m.start()

    # A date-stamped broadcast has no episode number; the date is the id.
    date = P_DATE.search(name)

    if episode is None and not date:
        m = P_DOUBLE.search(working)
        if m:
            a, b = _int(m.group(1)), _int(m.group(2))
            # Only a plausible consecutive pair, or `1-1080` reads as a double.
            if 0 <= b - a <= 3:
                episode, episode_end = a, b

    if episode is None and not date:
        # ⭐ The LAST match, not the first. An episode number sits at the END of
        # a title, and a title can begin with one: `86 - Eighty Six - 03v2` is
        # episode 3, not episode 86, and `5-toubun no Hanayome - 07` is 7.
        # Taking the first match gets both of those wrong.
        for pat in (P_BRACKET_DIGITS, P_DASH, P_TRAILING):
            found = list(pat.finditer(working))
            if found:
                # 🚨 Walk from the LAST match backwards, skipping years. A film
                # named `Inception (2010)` otherwise reports episode 2010 --
                # confidently wrong, on the launch movie use case.
                for m in reversed(found):
                    v = _int(m.group(1))
                    if _is_year(v, name):
                        continue
                    episode = v
                    cut = m.start()
                    break
                if episode is not None:
                    break

    # ⭐ CUT AT THE EARLIEST MARKER, not merely at the one that produced the
    # number.
    #
    # `ワンピース.S10E026.第1025話 …` takes its episode from `第1025話` -- the
    # broadcast number, which is the RIGHT one, and that preference is itself a
    # documented fix. But `S10E026` sits EARLIER in the name, so cutting at the
    # source marker leaves it inside the series title. Both are markers, and
    # **the series name ends at the first of them.**
    #
    # ⚠ `start() > 0` is load-bearing: a name that BEGINS with a marker
    # (`S01E01-The Harvest Festival…`) has no series name in it at all, and
    # cutting at 0 would trade a contaminated title for an EMPTY one -- which
    # is worse, because an empty key pairs with every video sharing an episode
    # number (`08-probes.md` §C measured 4,133 files).
    if episode is not None:
        for pat in (P_SXXEXX, P_JA_EPISODE, P_SEASON_X_EP, P_EP_WORD):
            found = pat.search(working)
            if found and found.start() > 0 and (cut is None
                                                or found.start() < cut):
                cut = found.start()

    title = _title_from(working, episode, season, cut)

    # A film whose only number was its year has no episode, and that is the
    # CORRECT answer -- not a parse failure.
    if episode is None and not date:
        m = P_YEAR_STANDALONE.search(name) or P_YEAR_TOKEN.search(name)
        if m:
            return Parsed(title, season=season, kind=FILM, source="ours",
                          group=group,
                          reason=u"the only number is a release year (%s); a "
                                 u"film correctly has no episode number"
                                 % m.group(1),
                          extras={"year": m.group(1)})

    if episode is not None:
        return Parsed(title, episode=episode, episode_end=episode_end,
                      season=season, kind=EPISODE, source="ours", group=group)

    if date:
        return Parsed(title, season=season, kind=FILM, source="ours",
                      group=group,
                      reason=u"date-stamped broadcast (%s-%s-%s); the date is "
                             u"the identifier" % date.groups(),
                      extras={"date": "-".join(date.groups())})

    if P_FILM.search(name):
        return Parsed(title, season=season, kind=FILM, source="ours",
                      group=group,
                      reason=u"film, special or OVA -- correctly has no "
                             u"episode number")

    return Parsed(title, season=season, kind=UNKNOWN, source="ours",
                  group=group, reason=u"no episode pattern matched")


def _title_from(working, episode, season, cut_at=None):
    """The SERIES title -- everything before the episode marker.

    🚨 Measured: deleting the episode marker and keeping the rest gives a
    SERIES title that still contains the EPISODE title --

        来世ではちゃんとします S03E03 第三話「檜山くんの可愛いアレ」
                          ^^^^^^ removed        ^^^^^^^^^^^^^^^^ kept

    Two files from one show then look almost unrelated, because their episode
    subtitles differ. It dragged median same-show similarity down to 0.425 and
    read as a threshold problem when it was a title-extraction problem.

    ⭐ TRUNCATE at the marker instead. Platform releases put the series name
    first and the episode name after, so everything before the marker is the
    series and everything after is not.
    """
    s = working[:cut_at] if cut_at else working
    if not s.strip() and cut_at:
        s = working                       # marker was at position 0; keep all
    if episode is not None and not cut_at:
        s = re.sub(r"(?<![\w])0*%d(?:v\d)?(?![\d])" % int(episode), " ", s, count=1)
    s = P_SEASON_WORD.sub(" ", s)
    s = re.sub(r"[\[\(【][^\]\)】]*[\]\)】]", " ", s)
    s = re.sub(r"[\s._\-]+", " ", s).strip(" -_.")
    return s


# --------------------------------------------------------------------------
# the union
# --------------------------------------------------------------------------

def parse_anitopy(filename):
    try:
        import anitopy
    except ImportError:
        return None
    try:
        d = anitopy.parse(filename)
    except Exception:
        return None
    if not d:
        return None

    ep = d.get("episode_number")
    if isinstance(ep, list):
        ep = ep[0] if ep else None
    season = d.get("anime_season")
    if isinstance(season, list):
        season = season[0] if season else None

    try:
        ep = _int(str(ep)) if ep is not None else None
    except ValueError:
        ep = None
    try:
        season = _int(str(season)) if season is not None else None
    except ValueError:
        season = None

    return Parsed(d.get("anime_title") or u"", episode=ep, season=season,
                  kind=EPISODE if ep is not None else UNKNOWN,
                  source="anitopy", group=d.get("release_group"))


def parse_guessit(filename):
    try:
        from guessit import guessit
    except ImportError:
        return None
    try:
        d = guessit(filename)
    except Exception:
        return None

    ep = d.get("episode")
    if isinstance(ep, list):
        ep = ep[0] if ep else None
    season = d.get("season")
    if isinstance(season, list):
        season = season[0] if season else None

    return Parsed(str(d.get("title") or u""),
                  episode=ep if isinstance(ep, int) else None,
                  season=season if isinstance(season, int) else None,
                  kind=EPISODE if isinstance(ep, int) else UNKNOWN,
                  source="guessit", group=d.get("release_group"))


AGREE = "agree"
PARTIAL = "partial"
MAJORITY = "majority"
DISAGREE = "disagree"
NONE = "none"
# ⭐ Ours answered and nothing gave a reason to ask anyone else. An honest
# state, not a synonym for AGREE: exactly one parser ran, so calling it
# agreement would be a claim about parsers that never spoke.
SOLE = "sole"


def _plausible(value, filename):
    """Could this number be an episode AT ALL?

    ⭐ Applied to the THIRD-PARTY parsers' answers before they count as a
    disagreement. Measured 2026-09-08 on 1,200 ambiguous files: when ours and
    anitopy already agreed, guessit differed 565 times -- and **537 of those
    (95%) were a resolution or a year**. Every one of them was routed to
    timing arbitration, the only stage that opens a file.

    ⚠ It is NOT applied to our own parser's answer. Our noise strippers remove
    resolutions before the episode patterns run, so a `720` that survives them
    is a real episode -- Detective Conan reaches 1100 and One Piece 1121, and
    a blanket filter would delete those.
    """
    if value is None:
        return False
    if value in RESOLUTIONS or value in CODEC_NUMS:
        return False
    if value > MAX_EPISODE:
        return False
    return not _is_year(value, filename)


_CJK_ANY = re.compile(u"[぀-ヿ一-鿿]")


def looks_western(filename):
    """Is this a Western-scene release name rather than an anime one?

    The two naming cultures are structurally different (spec/06 §1.3): dots as
    separators and the group as a trailing `-SUFFIX`, versus a leading
    `[Group]` and spaced dashes. guessit is built for the first and costs
    **27.5 ms per name against our 0.22** -- 41 s of pure parsing on a
    1,500-file library. Asking it about a Japanese filename buys nothing.
    """
    if _CJK_ANY.search(filename):
        return False
    stem = re.sub(r"\.[A-Za-z0-9]{2,4}$", "", filename)
    return bool(TRAILING_GROUP.search(stem)) or stem.count(".") >= 2


def _wants_guessit(filename, ours, ani):
    """The third opinion, only where it can earn 27.5 ms."""
    if not looks_western(filename):
        return False
    a = ours.episode
    b = ani.episode if ani is not None else None
    if a is None and b is None:
        return True                      # nothing has resolved it
    return a is not None and b is not None and a != b   # a genuine tie


class Union(object):
    """Whichever parsers ran, their answers, and whether they agree.

    ⚠ REVERSED 2026-09-08, on measurement. The rule used to be *"do not pick a
    parser -- run all three"*, from a reading where ours resolved 79.0% and
    failed where another succeeded on 13.2% of files. Ours has since risen to
    **97.6% accounted for**, and the cost of the other two was measured:

        ours 0.22 ms/name · anitopy 1.79 · guessit 27.5

    So the order is now **ours first, the others on a REASON**: our parser
    missed, the folder's own scheme disagrees with it, or a caller forced it.
    A reason is exactly where the other parsers were ever worth their price;
    running them everywhere else bought a 10x parse cost and 28.4% of files
    sent to timing arbitration, 95% of it over resolutions and years.

    ⛔ What did NOT change: a disagreement is still a candidate SET handed to
    arbitration, never a vote silently resolved in the parser layer.
    """

    __slots__ = ("results", "state", "episode", "season", "kind", "candidates")

    def __init__(self, results, state, episode, season, kind, candidates):
        self.results = results
        self.state = state
        self.episode = episode
        self.season = season
        self.kind = kind
        self.candidates = candidates

    @property
    def needs_arbitration(self):
        return self.state == DISAGREE

    @property
    def title(self):
        """Our own parser's title. ⚠ Deliberately not a vote: the other
        parsers vote on the EPISODE, and their titles are a different quality
        of answer (`09-corpus-strategy.md` Stage 1)."""
        return self.results[0].title if self.results else u""

    def key(self):
        """(season, episode) -- what candidate grouping must use.

        🚨 Episode ALONE manufactured 305 false pairs on multi-season shows.
        Made three separate times in one session (`LEDGER-HOT.md`), which is
        why this exists on `Union` as well as on `Parsed`: the rule was
        available on one shape and not the other, and the caller that had the
        wrong shape is exactly where the mistake gets made again.
        """
        return (self.season, self.episode)

    def __repr__(self):
        return "Union(%s, e=%r, s=%r, %s, candidates=%r)" % (
            self.state, self.episode, self.season, self.kind, self.candidates)


def union(filename, scheme_episode=None, force=False):
    """Ours first; the others only when there is a reason to ask them.

    `scheme_episode` -- what per-folder inference (A4) made of this file, when
        the caller knows it. It is the INDEPENDENT second opinion, it is far
        cheaper than another parser, and it agrees with us on ≥90% of real
        folders -- so a disagreement is the trigger that buys anitopy, AND a
        vote once the tie is open. ⚠ It votes only when it dissents: an
        agreeing scheme changes nothing, so it can never inflate a majority
        behind an answer we already hold. The minority always survives in
        `candidates`, so timing can still overrule the vote.
    `force` -- run every parser regardless. For the gate and the suites.
    """
    ours = parse_ours(filename)
    results = [ours]

    # ⛔ A refusal from our parser is authoritative and is NOT a disagreement to
    # be voted away. anitopy will happily return one episode for a file
    # containing two shows; that is exactly the confident wrong answer the
    # refusal exists to prevent.
    if ours.kind in (CONJUNCTION, BATCH):
        return Union(results, AGREE, None, ours.season, ours.kind, [])

    disputed = (scheme_episode is not None and ours.episode is not None
                and scheme_episode != ours.episode)

    # ⭐ The 97.6% path: our parser answered and nothing contradicts it.
    if not force and ours.episode is not None and not disputed:
        return Union(results, SOLE, ours.episode, ours.season, EPISODE,
                     [ours.episode])

    ani = parse_anitopy(filename)
    if ani is not None:
        results.append(ani)
    if force or _wants_guessit(filename, ours, ani):
        gue = parse_guessit(filename)
        if gue is not None:
            results.append(gue)

    # ⚠ Our own answer is trusted as-is; the third parties' are sanity-checked.
    episodes = [ours.episode] if ours.episode is not None else []
    episodes += [r.episode for r in results[1:]
                 if _plausible(r.episode, filename)]
    if disputed:
        episodes.append(scheme_episode)
    if not episodes:
        kind = ours.kind if ours.kind == FILM else UNKNOWN
        return Union(results, NONE, None, ours.season, kind, [])

    distinct = sorted(set(episodes))
    seasons = [r.season for r in results if r.season is not None]
    season = seasons[0] if seasons else None

    if len(distinct) == 1:
        state = AGREE if len(episodes) == len(results) else PARTIAL
        return Union(results, state, distinct[0], season, EPISODE, distinct)

    # ⭐ A STRICT MAJORITY IS AN ANSWER, and `sorted(set(...))` threw it away.
    #
    # Measured by review: 28.4% of files reach arbitration as disagreements,
    # and 90.8% of those already have a 2-of-3 majority sitting in hand. That
    # is a stage costing SECONDS -- the only stage that opens a file -- being
    # asked to settle a vote that was already decided for free.
    #
    # ⚠ The minority answer is KEPT in `candidates`. A majority is a strong
    # hypothesis, not a verdict: if the timing check later disagrees with it,
    # the other candidate is still there to try. Discarding it would trade the
    # project's reliability for its speed, which is the wrong way round
    # (spec/01-scope.md: accuracy outranks speed).
    counts = Counter(episodes)
    top, top_n = counts.most_common(1)[0]
    if top_n >= 2 and top_n > (len(episodes) - top_n):
        return Union(results, MAJORITY, top, season, EPISODE, distinct)

    return Union(results, DISAGREE, None, season, EPISODE, distinct)
