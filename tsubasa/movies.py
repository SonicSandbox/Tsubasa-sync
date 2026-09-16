# -*- coding: utf-8 -*-
"""
The MOVIE path: pairing a film to its subtitle from names and folders alone.

RUNBOOK step A10. `06-edge-cases.md` §3.5, §3.45, §3.4 (layouts 1, 2, 5, 6, 8).

⛔ PROVEN BROKEN, AND IT IS A LAUNCH USE CASE

    *"someone pointing it at a media library of their movies with subs in the
    same directory, and automatically fixes all the subs to the movie version"*

A folder holding `Inception (2010).mkv` and `Inception (2010).en.srt` -- an
identical stem plus a language tag -- produced **zero pairs**, because every
candidate index in this project is keyed on `(season, episode)` and a film has
neither. `discover.Candidates.for_video` returns `[]` the moment
`episode is None`. **The easiest possible pairing case, and nothing reached
it.** This module is the path that does.

⭐ NO SEPARATE MODE. The discriminator falls out of parsing (`06-edge-cases.md`
line ~169): a name yielding an episode number takes the TV path, one that does
not takes this one. Layout 8 -- one folder holding subs, movies AND shows -- is
then not a special case; it is the two paths running over one directory.

---

THE RUNGS, cheapest and strongest first

    1  STEM        the comparison key agrees exactly, year included
    2  TITLE_YEAR  the key agrees and the years are COMPATIBLE (one side is
                   silent). Different stated years are DIFFERENT FILMS
    0  SOLE_VIDEO  ⭐ a folder holding exactly one video: any subtitle in it,
                   or in a `Subs/` child that holds none, belongs to that video
    3  TIMING      not decided here. An ambiguity is handed on with its
                   candidates, never guessed

⚠ **Name evidence outranks folder evidence**, so SOLE_VIDEO is tried LAST even
though it is cheapest. A subtitle whose stem exactly names a video elsewhere in
the walk belongs to that video, not to whatever happens to share its directory.
All three are dict lookups, so the ordering costs nothing.

---

🚨 THE TWO TRAPS THIS USE CASE INTRODUCES, AND WHAT MEASUREMENT CHANGED

**Different CUTS of one film.** `06-edge-cases.md` predicts the slugs of
`Blade Runner (1982) [Final Cut]` and `[Theatrical]` overlap at **0.52**,
above the 0.4 threshold, so `same_series()` matches them. ⚠ **Measured here on
2026-09-08 it is worse than that: the overlap is 1.000.** `episode._title_from`
deletes every bracketed run, so both names reduce to the title `Blade Runner`
and the edition is not merely outweighed -- it is *gone* before any comparison
happens. No title measure of any kind can separate them.

⭐ So the edition is carried as a SECOND VALUE, exactly as `normalize` carries a
punctuation signature beside its key. **The edition is to a film what the
signature is to a season**, and this project already paid for that shape once,
on the four Gintama seasons. Two names that both state an edition and state
different ones are never paired -- an exact rule with nothing to tune.

⚠ **And duration is NOT the whole answer, contrary to §3.45.** Blade Runner's
theatrical, director's and final cuts run 116-117 minutes -- inside any
tolerance a subtitle's last-cue time could support. Duration rejects the
unambiguous cases and ranks the rest; the edition tag is what actually settles
a cut. Both are here, and neither is trusted alone.

**Language tags pollute the key.** `Inception (2010).en.srt` keys as
`inceptionen` while the video gives `inception`; §3.5 records that it survives
today *"only because one is a prefix of the other -- luck, not design."*
Language, edition, quality and group tags are stripped BEFORE the key is built,
through the project's own strippers rather than a new one.

---

⛔ WHAT THIS MODULE MAY NOT DO

* **No media I/O.** Not one file is opened. Names and directory structure only
* **No bare-word stripping.** `LEDGER.md`: stripping tags as words gave
  `Kingsglaive Fantasy XV`, `Bakemono no`, `Mad Fury Road`. Every strip here
  goes through `episode.strip_noise` or `decoration.strip`, both of which are
  context-gated for exactly that reason
* ⚠ **No empty key may ever pair.** An empty key matches everything --
  `08-probes.md` §C measured 4,133 files. Refused by name at three separate
  points below
* **No guess where two candidates are equally good.** Rule 2: a refusal with a
  stated reason is a feature

---

THE THREE SEAMS, all optional, all injected, NONE imported

`duration_of(path) -> seconds | None`
    RUNBOOK A9's territory. For a video its runtime; for a subtitle its last
    cue time. ⛔ Not imported and not re-derived: this module never opens a
    file, and A9 was being built alongside this step. Absent, duration
    contributes nothing -- it can neither create a pair nor break one, because
    *unknown is not evidence* (`discover.duration_verdict`'s own rule).

`duration_verdict(video_seconds, subtitle_seconds) -> str`
    ⭐ The RULE, separately from the numbers, because A9 owns the thresholds
    and this module must not hold a second copy of them. Defaults to
    `discover.duration_verdict`. **Any verdict word in `REJECTING_VERDICTS`
    forbids the pair**, and that set holds both vocabularies -- `discover`'s
    `"reject"` and A9's `IMPOSSIBLE` -- so wiring A9 in is one argument and no
    edit here. Anything else, including a word this module has never heard of,
    is not a rejection.

`parsed_of(path) -> Parsed | Union | None`
    `discover.parse_all` has already parsed every name by the time this runs;
    handing that in avoids a second parse. Absent, `parse_ours` is used --
    NOT `union`, deliberately: the movie path asks the parser one question
    (*did this name yield an episode number*), and `union` on an episode-less
    name falls off its 97.6% fast path into anitopy and guessit at
    **1.79 and 27.5 ms/name** against our 0.22 (`episode.Union`). On a
    1,500-file library that is 41 seconds to answer a boolean.
"""
import os
import re

from .naming import decoration as _decoration
from .naming import episode as _episode
from .naming.normalize import normalize

# --------------------------------------------------------------------------
# the rungs
# --------------------------------------------------------------------------

STEM = "stem"
TITLE_YEAR = "title-year"
SOLE_VIDEO = "sole-video"
TIMING = "timing"

# The order they are TRIED, which is not the order they are numbered in the
# spec. See the module note: name evidence outranks folder evidence.
RUNGS = (STEM, TITLE_YEAR, SOLE_VIDEO)

# --------------------------------------------------------------------------
# editions -- the second value, and the only exact discriminator for a cut
# --------------------------------------------------------------------------

# 🚨 EVERY ENTRY IS A PHRASE OR AN UNAMBIGUOUS WORD, AND THE OMISSIONS ARE THE
# DESIGN.
#
# `final` is not here, and must never be: `LEDGER.md` records
# `Kingsglaive - Final Fantasy XV` losing a word to it, and `Gintama Final` is
# a real season. `cut` alone is not here either. What IS here is `final cut` --
# two words in sequence, which no film title in the corpus carries.
#
# ⚠ Single words are admitted only where the word is not a plausible title on
# its own AND the context rule below requires a delimiter on both sides.
_EDITION_WORDS = [
    "final cut", "director's cut", "directors cut", "director cut",
    "theatrical cut", "theatrical version", "theatrical",
    "extended cut", "extended edition", "extended version",
    "special edition", "collector's edition", "collectors edition",
    "ultimate edition", "anniversary edition", "limited edition",
    "international cut", "international version",
    "assembly cut", "rogue cut", "workprint", "open matte",
    "unrated", "uncut", "remastered", "redux", "recut", "imax",
]

# Words inside a phrase may be separated by a space, a dot, an underscore or a
# hyphen -- `Final.Cut` and `Final Cut` are one tag written twice.
_EDITION_GAP = u"[\\s._\\-]+"
_EDITION_ALT = u"|".join(
    _EDITION_GAP.join(re.escape(w) for w in phrase.split())
    for phrase in sorted(_EDITION_WORDS, key=len, reverse=True))

# ⭐ CONTEXT, NEVER MEMBERSHIP -- the rule `decoration.py` was reshaped around.
# The phrase counts as an edition only when it is delimiter-bounded: a bracket,
# a dot, an underscore, a hyphen, or a string edge on BOTH sides.
#
# ⚠ A plain space is deliberately NOT a left delimiter, for the same reason
# `decoration._contexts` excludes it: a space-delimited word is just a word.
# A closing bracket IS one, so `Aliens (1986) Special Edition` is caught by the
# `)` before it.
_EDITION_SEP = u"\\[\\]\\(\\)\\{\\}【】._\\-"
_EDITION_RE = re.compile(
    u"(?:^|[%s])\\s*(%s)\\s*(?=$|[%s])" % (_EDITION_SEP, _EDITION_ALT,
                                           _EDITION_SEP),
    re.IGNORECASE | re.UNICODE)

# --------------------------------------------------------------------------
# 🚨 the LANGUAGE tag, in the forms a Western movie library actually uses
# --------------------------------------------------------------------------

# MEASURED 2026-09-08 over the 736 real Western film names in
# `western-naming/`, one tag form at a time. `episode.SOFT_NOISE_RE` already
# handles the Japanese-corpus forms and handles them perfectly:
#
#     (no tag)  100%   .en  100%   .eng  100%   .ja  100%   .jpn  100%
#     .en.forced 100%  .en.sdh 100%
#     🚨 .es  0%    .fr.forced  0%    .pt-BR  0%    .zh-Hans  0%
#
# `episode._SOFT` lists `ja jp jpn en eng zh chs cht kor ko` -- the languages
# this project's Japanese corpus contains. **A movie library is not that
# population**, and §3.5 is a Western-film use case. `06-edge-cases.md` §4
# requires language tags to be *"stripped for matching, retained for output
# naming"*, and four of the commonest forms were not being stripped at all.
#
# ⭐ TWO LETTERS ONLY, AND THAT IS THE WHOLE GUARD. `LEDGER.md` is emphatic
# that a length floor does not separate decoration from a title word -- but
# that finding is about words, and it cuts the other way here: `ja`, `es`,
# `it` and `us` are two letters precisely because they are CODES, and a
# two-letter token standing alone after a dot at the very end of a filename is
# not a title. Three-letter codes are left to `_SOFT`, where they already are,
# because `cat`, `may`, `nor` and `ice` are all ISO 639-2 codes AND English
# words.
#
# ⚠ AND `It`, `Us`, `Up` and `Pi` ARE REAL FILMS, all two letters. They survive
# because the peel refuses to remove the last thing in the name -- see
# `_peel_language_tail`.
#
# ⭐ MOVED TO `sidecar.py` AT 3a, byte-identical, and imported rather than
# copied. It was declared here and a THIRD, narrower list lived in
# `naming/episode._SOFT` -- `HANDOFF.md` carried the consequence as an open
# item: `_SOFT` has no European codes, so `.es`, `.fr.forced` and `.pt-BR`
# measured **0%** coverage against 100% for `.en`/`.ja`. A vocabulary is a
# derived value and `doctrine/architecture` rule 4 gives it one writer.
# ⚠ The order and contents are unchanged, so the Western-film measurement
# above still describes this regex.
from .sidecar import ISO_639_1 as _LANG2  # noqa: E402

# A BCP-47 script or region subtag: `Hans`, `Hant`, `BR`, `419`, `Latn`.
_LANG_TAIL = re.compile(
    u"[.\\[\\(_]\\s*(?:%s)(?:[-_](?:[A-Za-z]{2,4}|[0-9]{3}))?"
    u"\\s*[\\]\\)]?\\s*$" % u"|".join(_LANG2), re.IGNORECASE)


_EMPTY_BRACKETS = re.compile(u"\\[\\s*\\]|\\(\\s*\\)|\\{\\s*\\}|【\\s*】")
_TRAILING_SEPARATORS = re.compile(u"[\\s._\\-\\[\\]\\(\\)\\{\\}【】]+$")


def _tidy_residue(text):
    """Remove what a strip left behind. ⭐ ONE definition, used everywhere.

    🚨 THREE SEPARATE FAULTS IN THIS MODULE WERE RESIDUE, NOT LOGIC, and each
    was a pattern anchored at `$` meeting a leftover delimiter:

        …x264-N3WS .             the group anchor no longer reaches the group
        Absolute Strangers 1991[]  `P_YEAR_TOKEN` needs `$` or a delimiter
                                   after the year, and `[` is neither

    Removing an empty bracket pair and a trailing separator run is cosmetic
    right up until something anchored reads the string, which everything after
    this point does.
    """
    out = _EMPTY_BRACKETS.sub(u" ", text)
    out = re.sub(u"[\\s]{2,}", u" ", out)
    return _TRAILING_SEPARATORS.sub(u"", out)


def _peel_language_tail(text):
    """Peel trailing two-letter language tags. -> text.

    ⛔ NEVER TO NOTHING. `It (2017)`, `Us (2019)`, `Up (2009)` and `Pi (1998)`
    are real films whose entire title is a two-letter token, and `it` is
    Italian, `us` has no code but `es` does, `pi` does not. Emptying a key is
    the one outcome this module treats as worse than a miss -- an empty key
    pairs with every video in the library (`08-probes.md` §C, 4,133 files).

    ⚠ Applied repeatedly, because `.zh-Hans.en` and `.es.pt` both occur.
    """
    out = text
    for _ in range(3):
        trimmed = _LANG_TAIL.sub(u"", out)
        if trimmed == out:
            break
        if not normalize(trimmed).key:
            break                        # ⛔ the last content token: keep it
        out = trimmed
    return out


# --------------------------------------------------------------------------
# creditless openings and endings -- no dialogue at all
# --------------------------------------------------------------------------

# 🚨 `06-edge-cases.md` §4: NCOP/NCED carry **no dialogue**, so any subtitle
# fitted to one is a phantom -- the documented 108 s orphan-cue failure. They
# must REFUSE, never guess.
#
# ⚠ Delimiter-bounded, like everything else here. `NCOP` as a bare substring
# would fire inside a real word; and `OP`/`ED` alone are far too short to be
# safe at all, so they are not here.
#
# ===========================================================================
# 🚨 IT FIRED ON THE ORDINARY WORD **"cleaned"**. FOUND BY AN ADVERSARIAL PASS
# ===========================================================================
#
# `clean[\s._\-]*(?:op|ed|...)` accepts ZERO separators, so `clean` + `ed` is
# `cleaned`. Swept over **40,993 real corpus filenames**: 28 hits, and **3 of
# the 28 (10.7%) were real subtitles**:
#
#     Hibike! Euphonium S3 - 01 (NHKE 1440x1080i MPEG2 AAC)[cleaned-retimed].srt
#     [Anon][QYQ][Kanon][DVDRIP][22][AVC_AAC][A8E2A2B3] (cleaned).ass
#     [Cleaned] Megaton-kyuu Musashi - 03 (TOKYO MX).srt
#
# ⛔ AND `cleaned` IS A SUBTITLE-COMMUNITY CONVENTION -- it marks a sub with
# ads and typesetting stripped, which is precisely the file this tool exists to
# sync. The user was told it *"carries no dialogue"*, which is a lie, and
# `unpaired()` then said no subtitle carried that episode, which is a second
# one. It became reachable at 3b, where discovery started calling this.
#
# ⭐ THE FIX: the two-letter forms REQUIRE a separator; the spelled-out ones do
# not. `Clean Opening`, `CleanOpening` and `Clean-OP` are creditless;
# `cleaned` is a word.
#
# ⚠ And the same pass measured FALSE NEGATIVES, all of them real shapes:
# `NCOP1v2` and `NCOP01v2` (the commonest way a creditless file actually
# arrives -- the trailing `(?:[\s._\-]*\d{1,2})?` ate the digit and the
# lookahead then met `v`), `NC-OP`, `NC OP 01`, `NC_ED`, `Textless Opening`,
# `Textless OP 01`. A missed one is offered to every episode in the folder.
_CREDITLESS_RE = re.compile(
    u"(?:^|[\\s._\\-\\[\\(])"
    u"(?:"
    u"nc[\\s._\\-]*(?:op|ed)"          # NCOP, NC-OP, NC_ED, NC OP
    u"|creditless"
    u"|textless[\\s._\\-]*(?:op|ed|opening|ending)?"
    u"|clean[\\s._\\-]+(?:op|ed)"      # ⛔ separator REQUIRED -- not `cleaned`
    u"|clean[\\s._\\-]*(?:opening|ending)"
    u")"
    # ⚠ `v2` and friends: a re-release suffix sits between the number and the
    # boundary, so it has to be part of the token rather than after it.
    u"(?:[\\s._\\-]*\\d{1,2})?(?:v\\d{1,2})?"
    u"(?=$|[\\s._\\-\\]\\)])", re.IGNORECASE)

# --------------------------------------------------------------------------
# 🚨 the numbered SEQUEL, which the parser reads as an episode number
# --------------------------------------------------------------------------

# MEASURED 2026-09-08 over the 904 real Western release names in
# `western-naming/`: **45 of them (5.0%) carry BOTH a release year and a number
# the parser calls an episode.**
#
#     Toy Story 2 (1999)      -> ep=2      Shrek 2 (2004)   -> ep=2
#     Iron Man 3 (2013)       -> ep=3      Alien 3 (1992)   -> ep=3
#     Kill Bill Vol 2 (2004)  -> ep=2      Scream 4 (2011)  -> ep=4
#
# ⛔ Every one is a film, and left as an episode every one of them is worse
# than merely absent from the movie path: `Toy Story 2` and `Iron Man 3` and
# `Shrek 2` all key to `(None, 2)` and `(None, 3)`, which is a whole film
# library bucketed under a fabricated episode number -- the exact shape
# `LEDGER.md` records for the release year itself.
#
# ⭐ THE PARSER ALREADY OWNS HALF OF THIS RULE. *A release year is never an
# episode number* is `episode._is_year`; what it does not say is that a release
# year also makes every OTHER bare number in the name a title word. A sequel
# ordinal is exactly that.
#
# ⚠ AND THE GUARD IS THE EXPLICIT MARKER, not the number. `Doctor Who (2005)
# S01E01` is the standard Plex naming for television and it also carries a
# bracketed year -- so *year present* alone is emphatically not the tell.
# The tell is a release year AND no explicit episode marker anywhere in the
# name. `S##E##`, `第N話`, `E##`, `EP##`, `#N` and `2x05` all keep a name on
# the TV path whatever year it states.
#
# ⛔ This DISAGREES WITH `parse_ours`, deliberately and in one direction only:
# it can move a name from the TV path to the movie path and never the reverse.
# It is a Part 1 defect recorded rather than silently absorbed -- see the
# report for A10.
_EXPLICIT_MARKERS = (_episode.P_SXXEXX, _episode.P_JA_EPISODE,
                     _episode.P_SEASON_X_EP, _episode.P_EP_WORD,
                     _episode.P_BARE_E, _episode.P_HASH)


def has_explicit_episode_marker(name):
    """Does the name carry an episode MARKER, as opposed to a bare number?

    ⭐ The parser's own patterns, called rather than restated -- two copies of
    an episode-marker list would drift and the stale one is the one somebody
    reads.
    """
    stem = _episode.strip_noise(strip_extension(_fold(name)))
    return any(pattern.search(stem) for pattern in _EXPLICIT_MARKERS)


def _number_precedes_the_year(stem, episode, year_start):
    """Does every occurrence of `episode` sit BEFORE the release year?

    🚨 THIS GUARD WAS ADDED BECAUSE THE NEGATIVE CONTROL CAUGHT THE RULE
    WITHOUT IT. *Release year plus no explicit marker* alone claimed **23 of
    2,107 non-sealed video-corpus names** -- real television:

        [HorribleSubs] Fruits Basket (2019) - 01 [1080p].ass

    A disambiguating year inside a SERIES title is ordinary anime naming, and
    the rule as first written read every one of those episodes as a film.

    ⭐ POSITION SEPARATES THEM, and it is the third time this project has
    arrived at that answer (`decoration._strip_trailing_run`,
    `normalize.signature_of`, `episode._title_from`). **A sequel ordinal is
    part of the TITLE, so it stands before the release year; an episode number
    is appended after everything.**

        Toy Story 2 (1999)                 2 before 1999   -> film
        Fruits Basket (2019) - 01          01 after 2019   -> television

    ⚠ EVERY occurrence, not the first. A number appearing on both sides of the
    year is not evidence of anything, and the safe reading of *not evidence* is
    to leave the parser's answer alone.
    """
    try:
        value = int(episode)
        if value != episode:
            return False                 # a half-episode: 13.5 is a marker
    except (TypeError, ValueError):       # pragma: no cover
        return False
    spots = [m.start() for m in
             re.finditer(u"(?<![0-9])0*%d(?![0-9])" % value, stem)]
    return bool(spots) and all(spot < year_start for spot in spots)

# --------------------------------------------------------------------------
# extensions
# --------------------------------------------------------------------------


def _known_extensions():
    """Both extension sets, from the modules that own them.

    ⚠ Imported here rather than at module scope: `formats` and `container`
    pull in the readers, and this module is pure name handling. Deferred, it
    also keeps `discover` free to import this file without a cycle.
    """
    from .formats import KNOWN_SUBTITLE_EXT
    from .container import KNOWN_VIDEO_EXT
    return KNOWN_SUBTITLE_EXT | KNOWN_VIDEO_EXT


_EXT_CACHE = None


def strip_extension(name):
    """Drop ONE known media extension. -> the stem.

    🚨 `parse_ours` strips SUBTITLE extensions only, so a video keeps its own:
    measured 2026-09-08, `Inception (2010).mkv` parses to the title
    `'Inception mkv'` while `Inception (2010).en.srt` gives `'Inception'`. On
    the episode path the marker truncation cuts the extension off as a side
    effect and it is never seen; on the FILM path there is no marker, so every
    video title in a movie library carries `mkv` or `mp4`. That is the same
    *survives-by-luck-of-prefix* shape §3.5 records for language tags, on the
    other side of the pair.

    ⚠ ONE extension, not a loop. `.en` in `Inception (2010).en.srt` is a
    language tag, not an extension, and it is `strip_noise`'s job.
    """
    global _EXT_CACHE
    if _EXT_CACHE is None:
        _EXT_CACHE = _known_extensions()
    stem, ext = os.path.splitext(name or u"")
    if ext.lower() in _EXT_CACHE:
        return stem
    return name or u""


# --------------------------------------------------------------------------
# the year
# --------------------------------------------------------------------------


def _years_in(name):
    """Every year-shaped run in the name, in order. -> [(value, start, end)].

    ⚠ OVERLAPPING MATCHES ARE REQUIRED, and `finditer` cannot give them.
    `episode.P_YEAR_TOKEN` consumes its trailing delimiter, so in
    `Blade Runner 2049.2017.1080p` the match on `2049` eats the dot that `2017`
    needs as its own leading delimiter and the second year is never seen. The
    scan restarts one character into each match for exactly that reason.
    """
    found = []
    for pattern in (_episode.P_YEAR_STANDALONE, _episode.P_YEAR_TOKEN):
        pos = 0
        while True:
            m = pattern.search(name, pos)
            if not m:
                break
            found.append((int(m.group(1)), m.start(1), m.end(1)))
            pos = m.start(1) + 1
        if found:
            break                      # a bracketed year wins outright
    return found


def year_of(name):
    """The RELEASE year a film name states, or None.

    ⭐ THE LAST one, not the first, and the reason is a real film: in
    `Blade Runner 2049 (2017)` and `Blade Runner 2049.2017.1080p` the title
    itself contains a year-shaped number. Release names put the title first and
    the year after it, so the last candidate is the release year and anything
    before it belongs to the title.

    ⚠ `2012`, `1917` and `1408` are films whose entire title is a year. The
    caller must not be handed a stem of nothing, so `read_name` restores the
    year to the key when removing it would empty it -- see `_strip_year`.

    ⭐ DELEGATES TO `read_name` RATHER THAN RE-DERIVING. It did re-derive, and
    it drifted within the hour: `read_name` now finds the year on the
    tag-stripped string, because `Absolute Strangers 1991[eng].srt` reports no
    year at all when read before `[eng]` is removed. Two derivations of one
    value is `doctrine/architecture` §4 exactly -- the second writer is the one
    that goes stale.
    """
    return read_name(name).year


def _fold(name):
    """Basename, full-width folded. ⭐ `episode.fold_width` is the one
    definition; a second would drift, and 11.9% of corpus filenames carry a
    full-width character."""
    base = os.path.basename((name or u"").replace(u"\\", u"/"))
    return _episode.fold_width(base)


def _strip_year(text, year):
    """Remove the LAST occurrence of `year` from already-cleaned text.

    ⚠ Refuses to empty the string. `2012 (2009)` keys as `2012`, not as
    nothing -- an empty key pairs with every video in the library
    (`08-probes.md` §C, 4,133 files).
    """
    if year is None:
        return text
    pattern = re.compile(u"(?<![0-9])%d(?![0-9])" % year)
    matches = list(pattern.finditer(text))
    if not matches:
        return text
    last = matches[-1]
    out = text[:last.start()] + u" " + text[last.end():]
    if not normalize(out).key:
        return text
    return out


# --------------------------------------------------------------------------
# the edition
# --------------------------------------------------------------------------


def edition_of(name):
    """The edition/cut a film name states, normalised, or `u""`.

    ⭐ This is the film's equivalent of `normalize`'s punctuation signature: a
    second value that never widens a match and can only ever refuse one.

    ⭐ AND THAT IS WHY A MODEST VOCABULARY IS SAFE HERE, which is worth writing
    down because it is the opposite of the situation `decoration.py` faces.
    A FALSE edition is harmless whenever it is SYMMETRIC -- and it is symmetric
    exactly when the subtitle is named after the video, which is the case this
    rung exists for. `The.Final.Cut.2004.mkv` and `The.Final.Cut.2004.en.srt`
    both read `final cut`, they agree, and they pair. An edition on one side
    only is not a disagreement by design. **The only harmful case is two
    DIFFERENT false editions on the two sides**, which needs two different
    edition-shaped words in two names of one film.

    ⛔ So the vocabulary is still kept small and still context-gated -- but the
    argument for its safety is the symmetry, not the completeness of the list,
    and a future addition should be judged on that.
    """
    m = _EDITION_RE.search(strip_extension(_fold(name)))
    if not m:
        return u""
    return u" ".join(re.split(u"[\\s._\\-]+", m.group(1).lower().strip()))


def is_creditless(name):
    """Is this an NCOP/NCED -- a creditless opening or ending with no dialogue?

    `06-edge-cases.md` §4 requires a REFUSAL, never a guess. Cheapest possible
    place to make it is here, before anything opens a file.
    """
    return bool(_CREDITLESS_RE.search(strip_extension(_fold(name))))


# --------------------------------------------------------------------------
# the comparison key
# --------------------------------------------------------------------------


def _peel_group(stem):
    """Remove a Western scene release group suffix -- `…-RARBG`, `…-GROUP`.

    🚨 `X-Men` IS WHY THIS IS GATED. `episode.TRAILING_GROUP` matches `-Men`
    happily, and `parse_ours` gets away with it because it only RECORDS the
    group and never removes it. Removing it unconditionally turns `X-Men
    (2000)` into `X`.

    ⭐ The gate is the naming CULTURE, not a word list: a trailing `-GROUP` is
    a group only in a dot-separated release name, which is what
    `episode.looks_western` already keys on. `X-Men (2000)` carries no dots and
    is untouched; `Inception.2010.1080p.BluRay.x264-GROUP` carries four and is
    peeled -- which is what makes §3.5's own rung-2 example reduce to
    `inception` on both sides.

    ⚠ AND IT IS FED A RIGHT-STRIPPED STRING, which is not cosmetic.
    `episode.TRAILING_GROUP` is anchored at `$`, and stripping a language tag
    leaves the separator that carried it behind:

        …x264-N3WS            -> group peeled
        …x264-N3WS.en.forced  -> ` . ` left where the tags were, so the group
                                 is no longer last and STAYS in the key

    That is the same ordering fault as the one in `_read_uncached`, one layer
    down, and it cost 10% of the measured rung-1 rate on real Western names.
    """
    stem = _tidy_residue(stem)
    if stem.count(u".") < 2:
        return stem
    m = _episode.TRAILING_GROUP.search(stem)
    if m and not m.group(1).isdigit():
        return stem[:m.start()]
    return stem


class MovieName(object):
    """One film name, reduced. Everything the movie path compares on.

    ⭐ ONE ACCESSOR over a name, not four functions each re-running the
    pipeline. `doctrine/architecture` §2, and it is also Rule 4: pairing a
    library asks for the key, the year and the edition of every name, and
    deriving them three times over is three passes for one answer.
    """

    __slots__ = ("original", "key", "year", "edition", "episode", "kind",
                 "creditless", "refusal")

    def __init__(self, original, key, year, edition, episode, kind,
                 creditless, refusal):
        self.original = original
        self.key = key                   # the normalised comparison key
        self.year = year                 # int, or None if the name is silent
        self.edition = edition           # u"" when the name states none
        self.episode = episode           # not None -> this is NOT a film
        self.kind = kind                 # episode.EPISODE / FILM / BATCH / ...
        self.creditless = creditless
        self.refusal = refusal           # why the movie path will not take it

    @property
    def is_film(self):
        """Does this name belong on the movie path at all?"""
        return self.refusal is None

    @property
    def stem_key(self):
        """The rung-1 key: the title AND the year it states."""
        return (self.key, self.year)

    def __repr__(self):
        return "MovieName(%r, year=%r, edition=%r%s)" % (
            self.key[:24], self.year, self.edition,
            "" if self.is_film else ", refused")


def _read_uncached(name, parsed):
    original = name
    folded = _fold(name)
    stem = strip_extension(folded)

    # The filesystem collision suffix, before anything reads a number. ⭐ Not
    # re-derived: `episode.P_DUP_SUFFIX` carries the measurement (2,108 of
    # 2,602 real files got the wrong episode without it) and the reasoning.
    stem = _episode.P_DUP_SUFFIX.sub(u"", stem)

    # ---- one cleaned string, and EVERYTHING is derived from it ----------
    #
    # 🚨 ORDER, AND IT WAS MEASURED WRONG THREE TIMES IN A ROW. Each fault was
    # the same shape -- a pattern anchored at the end of the string, run before
    # the thing at the end of the string had been removed:
    #
    #   1. the release group was peeled BEFORE the language tag was stripped,
    #      so `…x264-CHD.en.srt` kept `chd` while `…x264-CHD.mkv` did not
    #   2. the group anchor then failed on the SEPARATOR the strip left behind
    #      (`…-N3WS . `), which is the same fault one layer down
    #   3. the release YEAR was read before the tag was stripped, so
    #      `Absolute Strangers 1991[eng].srt` reported no year at all --
    #      `episode.P_YEAR_TOKEN` needs a delimiter after the year and `[` is
    #      not one
    #
    # ⭐ The tell every time was a CONTROL: with no tag at all rung 1 paired
    # **737 of 737 real Western film names (100%)**, and adding `.en` took it
    # to **511 (69.2%)**. A key that disagrees with itself the moment something
    # is appended is an ordering bug, and nothing but the tag-free control
    # could have said so.
    working = _episode.strip_noise(stem)
    working = _tidy_residue(_peel_language_tail(working))

    year = year_start = None
    found = _years_in(working)
    if found:
        year, year_start = found[-1][0], found[-1][1]
    # ⚠ The edition and the creditless marker are read from the RAW stem, not
    # from `working`. Both live inside brackets, which `strip_noise` leaves
    # alone, and reading them before any cleaning means a future noise pattern
    # cannot silently take one away.
    edition = edition_of(name)
    # ⭐ ONE writer for the rule, not two. `is_creditless` is the public
    # accessor and a second in-line `search` here is the shape
    # `doctrine/architecture` §4 names: the copy nobody updates is the one
    # somebody reads.
    creditless = is_creditless(name)

    if parsed is None:
        parsed = _episode.parse_ours(name)
    episode = getattr(parsed, "episode", None)
    kind = getattr(parsed, "kind", _episode.UNKNOWN)

    # ⭐ A SEQUEL ORDINAL IS NOT AN EPISODE. See `_EXPLICIT_MARKERS` above --
    # measured at 45 of 904 real Western film names, and every one of them is
    # a film keyed under a fabricated episode number today.
    sequel_ordinal = (episode is not None and year is not None
                      and not has_explicit_episode_marker(name)
                      and _number_precedes_the_year(working, episode,
                                                    year_start))
    if sequel_ordinal:
        episode = None
        kind = _episode.FILM

    # ---- the refusals, each with its reason -----------------------------
    #
    # ⚠ ORDER. Creditless is tested FIRST because an NCOP is frequently
    # numbered -- `Show - NCED 2.mkv` parses to episode 2 -- and *"it takes the
    # TV path"* is a true sentence that hides the load-bearing one: this file
    # has no dialogue and nothing may ever be fitted to it.
    refusal = None
    if creditless:
        refusal = (u"creditless opening/ending: no dialogue at all, so any "
                   u"subtitle fitted to it is a phantom (06-edge-cases §4)")
    elif episode is not None:
        refusal = (u"the name yields episode %s, so it takes the TV path"
                   % episode)
    elif kind in (_episode.BATCH, _episode.CONJUNCTION):
        # 🚨 `getattr`, NOT `parsed.reason`. The `parsed_of` seam is fed by
        # `discover.parse_all`, which stores a **`Union`** -- and `Union` has
        # `episode` and `kind` but **no `reason`**. Reading it directly raised
        # `AttributeError` on exactly the shape this branch exists for, and
        # only on the integration path, so every hermetic check stayed green.
        # ⭐ Found by asking what the CALLER actually hands in, not by a test.
        why = getattr(parsed, "reason", u"") or (
            u"more than one work in one file (%s)" % kind)
        refusal = (u"%s -- more than one work in one file, which the movie "
                   u"path must never flatten into a film" % why)

    # ---- the key --------------------------------------------------------
    working = _peel_group(working)
    m = _episode.LEADING_GROUP.match(working)
    if m:
        working = working[m.end():]
    working = _decoration.strip(working, aggressive=True)
    working = _strip_year(working, year)
    key = normalize(working).key

    # ⚠ THE EMPTY KEY, REFUSED BY NAME. Cleaning a name down to nothing is not
    # a small loss: an empty key is equal to every other empty key, so one bad
    # reduction pairs a subtitle with every film in the library. `decoration.
    # strip` already refuses to return empty, and `normalize` can still empty
    # it -- a name of pure punctuation, or one that was only a year.
    #
    # ⛔ AND THERE IS NO FALLBACK TO THE RAW STEM, which was tried and removed
    # on measurement. A name whose every token is a release tag --
    # `1080p.AMZN.WEB-DL.DDP5.1.H.264-EVO` -- has no title in it, so a key made
    # from the raw stem is a key made of decoration: it pairs that name with
    # every other file sharing the same tags, which is the empty-slug defect
    # wearing different clothes. Measured on the 904 Western release names,
    # refusing them costs a handful of names that are not films.
    #
    # ⚠ The cost is named rather than hidden: a real film titled `Web` or `DVD`
    # is refused. Rule 2 says that is the correct side to fail on.
    if not key and refusal is None:
        refusal = (u"no title survives once release tags are removed, so "
                   u"there is nothing to compare -- an empty key pairs with "
                   u"every video in the library")

    return MovieName(original, key, year, edition, episode, kind, creditless,
                     refusal)


_NAME_CACHE = {}
_NAME_CACHE_MAX = 200000


def read_name(name, parsed=None):
    """`MovieName` for one filename. Memoised on the name.

    🚨 KEYED ON THE STRING, NEVER ON A DERIVED OBJECT -- `normalize`'s own
    docstring records why: `Normalized` hashes on `(key, signature)`, so
    `Gintama` and `Gin tama` are equal and a cache keyed on the result serves
    one for the other.

    ⚠ Not memoised when a `parsed` is supplied, because two callers could hand
    in different parses of the same name and the second would silently get the
    first one's answer.
    """
    if parsed is not None:
        return _read_uncached(name, parsed)
    hit = _NAME_CACHE.get(name)
    if hit is None:
        hit = _read_uncached(name, None)
        if len(_NAME_CACHE) < _NAME_CACHE_MAX:
            _NAME_CACHE[name] = hit
    return hit


def movie_stem(name):
    """The decoration-stripped, tag-stripped comparison key for a film name.

    ⭐ The one string two sides of a pair must agree on. Language, edition,
    quality, source, codec, group and collision tags are gone; the year is
    carried separately by `year_of` because two films can share a title.
    """
    return read_name(name).key


def is_film(name):
    """Does this name belong on the movie path?"""
    return read_name(name).is_film


# --------------------------------------------------------------------------
# pairing
# --------------------------------------------------------------------------


class MoviePair(object):
    """One accepted pair, the rung that produced it, and why.

    Iterable as `(video, subtitle, rung, reason)` so a caller can unpack it.
    """

    __slots__ = ("video", "subtitle", "rung", "reason")

    def __init__(self, video, subtitle, rung, reason):
        self.video = video
        self.subtitle = subtitle
        self.rung = rung
        self.reason = reason

    def __iter__(self):
        return iter((self.video, self.subtitle, self.rung, self.reason))

    def __len__(self):
        return 4

    def __getitem__(self, i):
        return (self.video, self.subtitle, self.rung, self.reason)[i]

    def __eq__(self, other):
        if isinstance(other, MoviePair):
            other = tuple(other)
        return tuple(self) == other

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(tuple(self))

    def __repr__(self):
        return "MoviePair(%s <- %s, %s)" % (
            os.path.basename(self.video), os.path.basename(self.subtitle),
            self.rung)


class MovieRefusal(object):
    """A subtitle the movie path would not pair, and what stopped it.

    ⭐ Rule 2: *a confidently wrong answer is worse than no answer, and a
    refusal with a stated reason is a feature.* `doctrine/robustness`: refuse
    loudly, never drop silently -- name what was refused and what was there.
    """

    __slots__ = ("subtitle", "candidates", "reason", "rung")

    def __init__(self, subtitle, candidates, reason, rung=None):
        self.subtitle = subtitle
        self.candidates = list(candidates)
        self.reason = reason
        self.rung = rung             # the rung it reached before refusing

    def __repr__(self):
        return "MovieRefusal(%s, %d candidates: %s)" % (
            os.path.basename(self.subtitle), len(self.candidates), self.reason)


class MoviePairing(object):
    """The result of one movie-path pass.

    ⛔ NOT ITERABLE, AND THAT IS DELIBERATE. A bare list of pairs has nowhere
    to put a refusal, and a caller who never asks for the refusals is exactly
    the *silent drop* `doctrine/robustness` opens with. Name the half you want.
    """

    __slots__ = ("pairs", "refusals", "skipped", "counts")

    def __init__(self, pairs, refusals, skipped, counts):
        self.pairs = pairs
        self.refusals = refusals
        self.skipped = skipped       # {path: reason} -- not on the movie path
        self.counts = counts         # ⭐ always carries its own denominator

    def __repr__(self):
        return "MoviePairing(%d paired, %d refused, %d skipped of %d subs)" % (
            len(self.pairs), len(self.refusals), len(self.skipped),
            self.counts.get("subtitles", 0))


def _runtime(path, duration_of):
    if duration_of is None:
        return None
    try:
        return duration_of(path)
    except Exception:                                        # noqa: BLE001
        # ⭐ Fail OPEN, and the reason is written here: duration is an
        # ACCELERATOR (00-INDEX Rule 1). A probe that raises must cost the run
        # a ranking signal, never the pair. `unknown is not evidence`.
        return None


# ⭐ ANY VERDICT WORD THAT MEANS *THESE TWO CANNOT BE THE SAME RUNTIME*.
#
# `discover.duration_verdict` says `"reject"`; RUNBOOK A9's `duration.py` says
# `IMPOSSIBLE`. This module is written to accept EITHER without importing
# either, because a movie library must keep pairing whichever one is wired in
# and because A9 is being built in parallel with this step. Anything not in
# this set -- including `"ok"`, `PLAUSIBLE` and `UNKNOWN` -- is not a rejection:
# **unknown is not evidence.**
REJECTING_VERDICTS = frozenset(("reject", "rejected", "impossible"))


def _default_duration_verdict(video_seconds, subtitle_seconds):
    """⭐ `discover.duration_verdict`'s measured tolerances, called rather than
    copied -- two copies of an asymmetric tolerance would drift and the stale
    one is the one somebody reads.

    ⚠ Deferred import: `discover` is free to import this module once A10 is
    wired in, and a module-scope import would then be a cycle.
    """
    from . import discover

    class _Shim(object):
        __slots__ = ("duration", "cues", "dirname")

        def __init__(self, duration=None, cues=None, dirname=u""):
            self.duration = duration
            self.cues = cues
            self.dirname = dirname

    return discover.duration_verdict(_Shim(duration=video_seconds),
                                     _Shim(cues=subtitle_seconds))


def _rejects(verdict_fn, video_seconds, subtitle_seconds):
    """Does the runtime evidence forbid this pair? -> bool.

    ⛔ FAIL OPEN, and the reason is written here: duration is an ACCELERATOR
    (00-INDEX Rule 1). A verdict function that raises, or returns a word this
    module has never heard of, must cost the run a filter -- never the pair.
    """
    fn = verdict_fn or _default_duration_verdict
    try:
        verdict = fn(video_seconds, subtitle_seconds)
    except Exception:                                        # noqa: BLE001
        return False
    return _lower(verdict) in REJECTING_VERDICTS


def _lower(value):
    """Lowercased, or `u""` for anything that is not a word at all."""
    try:
        return value.lower()
    except AttributeError:
        return u""


def _editions_disagree(a, b):
    """Do two names state DIFFERENT editions?

    ⚠ STATED ON ONE SIDE ONLY IS NOT A DISAGREEMENT, and `LEDGER.md` records
    the cost of getting that backwards: counting a one-sided SEASON as a
    disagreement made a 92.3% stack read as 46.0%, because 46.3% of real pairs
    are exactly that shape. A subtitle named `Blade Runner (1982).srt` beside
    `Blade Runner (1982) [Final Cut].mkv` is the same shape and the same
    answer: the name is silent, not contradictory.
    """
    return bool(a) and bool(b) and a != b


def _index(videos):
    """Three indexes in one pass. ⭐ Rule 4, and `06-edge-cases.md` §4 states
    it outright: *500 videos x 1500 subs -- index by key first, NEVER a nested
    loop.* The naive form is 750,000 comparisons; this is one pass plus one
    dict lookup per subtitle."""
    by_stem = {}          # (key, year)  -> [MovieName-bearing entries]
    by_key = {}           # key          -> [entries]
    by_dir = {}           # dirname      -> [entries]
    for entry in videos:
        by_stem.setdefault(entry["name"].stem_key, []).append(entry)
        by_key.setdefault(entry["name"].key, []).append(entry)
        by_dir.setdefault(entry["dir"], []).append(entry)
    return by_stem, by_key, by_dir


def _normdir(path):
    return os.path.normcase(os.path.dirname(os.path.abspath(str(path))))


def _entry(path, parsed_of):
    parsed = parsed_of(path) if parsed_of else None
    return {"path": str(path),
            "dir": _normdir(path),
            "name": read_name(os.path.basename(str(path)), parsed)}


def _sole_video_dir(sub_entry, by_dir):
    """The directory whose single video this subtitle may belong to.

    ⭐ `06-edge-cases.md` §3.5: *a folder holding exactly one video means any
    subtitle in it belongs to that video* -- the layout Plex, Jellyfin and
    Sonarr all produce.

    ⚠ AND ITS PARENT, which is layout 2 and is required: §4 says *if the sub
    folder holds no video, check the parent*. `Film/Subs/film.en.srt` beside
    `Film/film.mkv` is a shape the spec names, and without this it pairs with
    nothing at all.
    """
    here = by_dir.get(sub_entry["dir"], ())
    if len(here) == 1:
        return here[0], u"the only video in this folder"
    if here:
        return None, None                # several videos: no claim to make
    parent = os.path.normcase(os.path.dirname(sub_entry["dir"]))
    up = by_dir.get(parent, ())
    if len(up) == 1:
        return up[0], (u"the only video in the parent folder, and this "
                       u"subtitle's own folder holds none")
    return None, None


def _rank(candidates, sub_entry, sub_seconds, duration_of):
    """Order candidates best-first: proximity, then closeness of runtime.

    ⭐ `discover.proximity`'s tiers, called rather than restated. Proximity is
    a SCORE and never a gate -- returning 0.0 for *different tree* is the only
    reason layouts 5-7 (a tree of subtitles against a tree of videos) work at
    all.
    """
    from . import discover

    class _Shim(object):
        __slots__ = ("dirname",)

        def __init__(self, dirname):
            self.dirname = dirname

    sub_shim = _Shim(sub_entry["dir"])
    scored = []
    for cand in candidates:
        prox = discover.proximity(_Shim(cand["dir"]), sub_shim)
        gap = None
        if sub_seconds is not None:
            vid = _runtime(cand["path"], duration_of)
            if vid is not None:
                gap = abs(vid - sub_seconds)
        scored.append((-prox, gap if gap is not None else float("inf"),
                       cand["path"], cand))
    scored.sort(key=lambda row: (row[0], row[1], row[2]))
    return [row[3] for row in scored], scored


def pair_movies(video_paths, subtitle_paths, duration_of=None,
                parsed_of=None, duration_verdict=None):
    """Pair films to subtitles from names and folders alone. -> MoviePairing.

    ⛔ NOTHING IS OPENED. Every input is a path string; the only file-system
    fact used is which directory each one sits in, taken from the path itself.

    `duration_of`, `duration_verdict` and `parsed_of` are the three seams --
    see the module note. All three are optional and none is imported.
    """
    videos, skipped = [], {}
    for path in video_paths:
        entry = _entry(path, parsed_of)
        if entry["name"].is_film:
            videos.append(entry)
        else:
            skipped[entry["path"]] = entry["name"].refusal

    subtitles = []
    for path in subtitle_paths:
        entry = _entry(path, parsed_of)
        if entry["name"].is_film:
            subtitles.append(entry)
        else:
            skipped[entry["path"]] = entry["name"].refusal

    by_stem, by_key, by_dir = _index(videos)

    pairs, refusals = [], []
    counts = {"videos": len(video_paths), "subtitles": len(subtitle_paths),
              "films": len(videos), "filmSubtitles": len(subtitles),
              "skipped": len(skipped),
              STEM: 0, TITLE_YEAR: 0, SOLE_VIDEO: 0, "refused": 0}

    for sub in subtitles:
        name = sub["name"]
        sub_seconds = _runtime(sub["path"], duration_of)

        rung, candidates, why = _candidates(name, by_stem, by_key)
        if not candidates:
            cand, why_sole = _sole_video_dir(sub, by_dir)
            if cand is not None:
                rung, candidates, why = SOLE_VIDEO, [cand], why_sole

        if not candidates:
            refusals.append(MovieRefusal(
                sub["path"], [],
                u"no video in the walk shares its key %r%s"
                % (name.key, u"" if name.year is None
                   else u" and year %d" % name.year)))
            counts["refused"] += 1
            continue

        kept, vetoed = [], []
        for cand in candidates:
            veto = _veto(cand, sub, name, sub_seconds, duration_of,
                         duration_verdict)
            (vetoed if veto else kept).append((cand, veto))

        if not kept:
            reasons = u"; ".join(sorted(set(v for _c, v in vetoed)))
            refusals.append(MovieRefusal(
                sub["path"], [c["path"] for c, _v in vetoed],
                u"every candidate was vetoed: %s" % reasons, rung))
            counts["refused"] += 1
            continue

        survivors = [c for c, _v in kept]
        if len(survivors) > 1:
            ordered, scored = _rank(survivors, sub, sub_seconds, duration_of)
            if not _separated(scored):
                refusals.append(MovieRefusal(
                    sub["path"], [c["path"] for c in ordered],
                    u"%d candidates are equally good on name, folder and "
                    u"runtime -- 06-edge-cases §3.5 rung 3 hands this to "
                    u"timing arbitration, and guessing here is the "
                    u"corruption Rule 2 forbids" % len(ordered), TIMING))
                counts["refused"] += 1
                continue
            survivors = ordered

        pairs.append(MoviePair(survivors[0]["path"], sub["path"], rung, why))
        counts[rung] += 1

    return MoviePairing(pairs, refusals, skipped, counts)


def _candidates(name, by_stem, by_key):
    """(rung, [entries], reason). Rung 1 then rung 2, both dict lookups.

    ⚠ AN EMPTY KEY NEVER LOOKS ANYTHING UP. It would collide with every other
    empty key in the index -- `08-probes.md` §C measured that at 4,133 files.
    `read_name` already refuses such a name outright; this is the second of the
    three guards, because the index is the place the damage would happen.
    """
    if not name.key:
        return None, [], u""

    exact = by_stem.get(name.stem_key)
    if exact:
        return (STEM, list(exact),
                u"the comparison key %r%s is identical" %
                (name.key, u"" if name.year is None
                 else u" (%d)" % name.year))

    # ⭐ RUNG 2 -- the same title where exactly one side states a year.
    #
    # ⛔ TWO STATED YEARS THAT DIFFER ARE TWO FILMS, not a near miss:
    # `The Thing (1982)` and `The Thing (2011)` share a title and are unrelated
    # works. A remake is the movie library's version of the sequel shape
    # `series.one_contains_the_other` exists for, and it is settled here by an
    # exact test rather than by a threshold.
    loose = [c for c in by_key.get(name.key, ())
             if (c["name"].year is None) != (name.year is None)]
    if loose:
        stated = name.year if name.year is not None else loose[0]["name"].year
        return (TITLE_YEAR, loose,
                u"the title %r agrees and only one side states a year (%s)"
                % (name.key, stated))
    return None, [], u""


def _veto(cand, sub, name, sub_seconds, duration_of, duration_verdict=None):
    """Why this candidate may NOT take this subtitle, or None.

    Both vetoes are exact rules, not thresholds, and both exist because a
    wrong pair here writes a wrong subtitle onto a user's film.
    """
    if _editions_disagree(cand["name"].edition, name.edition):
        # 🚨 THE CUT TRAP. A theatrical subtitle on a Final Cut is *the*
        # corruption this feature must not produce (`00-INDEX` Rule 2), and
        # measured on 2026-09-08 the two names' titles are IDENTICAL after
        # `_title_from` deletes the bracketed run -- overlap 1.000, not the
        # 0.52 §3.5 predicts. Nothing but the tag itself can see this.
        return (u"different cuts of one film: the video says %r and the "
                u"subtitle says %r" % (cand["name"].edition, name.edition))

    if sub_seconds is not None:
        vid = _runtime(cand["path"], duration_of)
        if vid is not None and _rejects(duration_verdict, vid, sub_seconds):
            return (u"runtime: the subtitle runs to %.0fs against a %.0fs "
                    u"video" % (sub_seconds, vid))
    return None


def _separated(scored):
    """Is the best candidate actually better than the second?

    ⚠ Two candidates tying on proximity AND runtime is not a winner with a
    runner-up; it is an ambiguity, and picking the first is picking by sort
    order. `LEDGER.md`: *never take argmax of a flat plateau.*
    """
    if len(scored) < 2:
        return True
    best, second = scored[0], scored[1]
    return (best[0], best[1]) != (second[0], second[1])
