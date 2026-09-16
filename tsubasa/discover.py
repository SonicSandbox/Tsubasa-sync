# -*- coding: utf-8 -*-
"""
Discovery and candidate generation: what is here, and what might pair.

RUNBOOK step A5. `06-edge-cases.md` §3.4, §3.45, §4.

⛔ NO LAYOUT FLAG. NO MODE. THE USER DECLARES NOTHING.

Sonic named eight real-world directory shapes, from *film and subs in one
folder* to *one folder containing subs, movies AND shows at once*.
**Enumerating them is the wrong design — the ninth would break it.** So:

1. **Walk everything.** Every video, every subtitle, with its full path
2. **Score every plausible pairing** — name, episode, duration, proximity
3. ⭐ **Proximity is a SIGNAL, never a rule.** Same folder scores highest,
   parent and sibling next, a different tree contributes nothing — but it
   never *disqualifies*, and that is the only reason layouts 5-7 (a tree of
   subs against a tree of movies) work at all

⭐ **Movies and shows need no separate mode either.** The discriminator falls
out of parsing: a name yielding an episode number takes the TV path, one that
does not takes the movie path. Layout 8 is then not a special case — it is the
two paths running over one directory.

🚨 SCALE IS THE CONSTRAINT, NOT LOGIC

`06-edge-cases.md` §4: *500 videos × 1500 subs* must never be a nested loop.
Candidates are generated from an **index keyed by (season, episode)**, so the
cost is O(videos + subtitles) plus the pairs that actually share a key — and
the fan-out per video is a handful, not fifteen hundred.

⚠ **Season AND episode.** Episode alone manufactured 305 false pairs on
multi-season shows — Series 1 Episode 3 scored against Series 3 Episode 3 —
and that mistake was made three separate times in one session
(`LEDGER-HOT.md`).
"""
import os

from .formats import KNOWN_SUBTITLE_EXT
from .container import KNOWN_VIDEO_EXT

# ⚠ Junk is IGNORED SILENTLY, never an error. A subtitle folder full of `.txt`
# and stray archives is surasura's real case and is expected input
# (`06-edge-cases.md` §4). An error here would make the normal case look broken.
SKIP_NAMES = {".ds_store", "thumbs.db", "desktop.ini", ".directory"}
SKIP_SUFFIXES = (".bak", ".orig", ".tmp", ".part", ".!ut", "~")

# `sample.mkv` and `-sample` are decoys: a 30-second clip with the right name
# and the wrong content, which pairs plausibly and aligns to nothing.
SAMPLE_MARKERS = ("sample",)

# A file we have already written. `06-edge-cases.md` §4 — also checked against
# the results DB by content hash, but the name is the free half.
ALREADY_SYNCED = (".synced",)

# Proximity tiers, best first. ⚠ These are SCORES, not gates: the lowest tier
# is 0.0 and still a candidate, which is what makes a tree of subtitles pair
# with a separate tree of videos.
#: How many same-season subtitles the absolute-numbering fallback may offer a
#: video that was offered nothing at all. ⚠ A COST BOUND, NOT A CORRECTNESS
#: ONE -- precision comes from the series-identity filter upstream and from
#: the verdict downstream. It exists so one unpaired video in a 300-subtitle
#: season cannot quietly cost 300 alignments. Generous against any real
#: season; `Candidates._absolute_fallback` is the reasoning.
ABSOLUTE_FALLBACK_CAP = 64

def episode_offset(video_eps, sub_eps):
    u"""The shift that makes these two episode sets line up. -> int or None

    ===================================================================
    🚨 ABSOLUTE NUMBERING, AND WHY THE OBVIOUS INSTRUMENT IS WRONG
    ===================================================================

    ABEMA and DMMTV write a per-season SEASON tag with an ABSOLUTE episode
    number, so a season-2 library reads `S02E13..E36` where the videos read
    `S02E01..E24`. ⛔ **Those ranges OVERLAP**, and the overlap is what makes
    this dangerous rather than merely missing: twelve videos pair by number
    with the wrong subtitle and the other twelve are offered nothing.

    ⚠ **THE PAIRWISE DIFFERENCE HISTOGRAM DOES NOT WORK HERE, and it was the
    first thing proposed.** Measured on exactly that case: the true offset
    wins with **24 votes against 23 for each of its neighbours.** Two
    contiguous runs overlap almost as well at ±1, so the distribution is a
    triangle rather than a spike, and picking its apex would be a threshold
    set by taste on a one-vote margin. `00-INDEX.md` Rule 4's histogram is
    exact for CUE TIMES because those are continuous and a wrong offset
    matches nothing; episode numbers are a dense integer run and behave
    completely differently.

    ⭐ **COVERAGE IS THE SIGNAL, AND IT NEEDS NO THRESHOLD.** Score each
    candidate shift by how many videos have a subtitle at `episode + k`:

        offset 12   covers 24 of 24      <- unique maximum
        offset 11   covers 23 of 24
        offset 13   covers 23 of 24
        offset  0   covers 12 of 24      <- the accidental overlap

    The rule is a strict comparison and a uniqueness requirement: **a single
    argmax, non-zero, strictly better than no shift at all.** Nothing is
    tuned, and there is no band to fit.

    ⛔ **AMBIGUITY RETURNS None, WHICH IS A REAL ANSWER.** One video against
    three subtitles gives coverage 1 at three different offsets — the
    reported case — and guessing between them would be exactly the
    confidently-wrong answer `01-scope.md` Rule 2 exists to refuse. The
    caller falls back to offering the season as a hypothesis and letting
    timing decide.
    """
    videos = set(e for e in video_eps if e is not None)
    subs = set(e for e in sub_eps if e is not None)
    if not videos or not subs:
        return None
    # ⚠ Only shifts some real pair actually suggests. Sweeping a fixed range
    # would invent offsets nothing in the data proposes.
    shifts = set(s - v for v in videos for s in subs)
    shifts.add(0)
    best, coverage = None, -1
    ties = 0
    for k in sorted(shifts):
        hits = sum(1 for v in videos if v + k in subs)
        if hits > coverage:
            best, coverage, ties = k, hits, 1
        elif hits == coverage:
            ties += 1
    if best in (None, 0) or ties != 1:
        return None
    # 🚨 ONE VIDEO IS NOT A PATTERN, IT IS A COINCIDENCE. With a single video
    # ANY shift that reaches a subtitle scores a perfect 1 of 1 and is
    # trivially unique — `{1}` against `{13}` confidently returned 12.
    # ⭐ `LEDGER-HOT.md` records the identical shape one domain over: *a
    # subtitle containing ONE cue scored 5.15x chance, because the best of
    # thousands of candidate offsets always lands that one cue on something.*
    # ⛔ TWO is the boundary between a coincidence and a pattern, not a fitted
    # number: a second video has to line up under the SAME shift, and the
    # uniqueness test above does the rest.
    if coverage < 2:
        return None
    # ⚠ NO SEPARATE "must beat doing nothing" TEST HERE, and there was one.
    # It is UNREACHABLE: `best` is the strict argmax over a set that always
    # contains 0, and ties are already refused above — so a non-zero winner
    # has beaten `k = 0` by construction. ⛔ Two mutants proved it by masking
    # each other, each surviving because the other guard caught its case.
    # `doctrine/verification`: *a mutant that cannot fail is noise.*
    return best


SAME_DIR = 1.0
PARENT_OR_CHILD = 0.7
SIBLING = 0.5
SAME_ROOT = 0.2
ELSEWHERE = 0.0


class Item(object):
    """One file discovery found, with what parsing made of its name."""

    __slots__ = ("path", "kind", "parsed", "duration", "cues")

    def __init__(self, path, kind, parsed=None, duration=None, cues=None):
        self.path = path
        self.kind = kind                 # "video" | "subtitle"
        self.parsed = parsed             # naming.episode.Parsed
        self.duration = duration         # seconds, or None if not probed
        # 🚨 WHERE THE CONTENT ENDS, from `duration.content_end(starts)` --
        # NOT `max(starts)`. It used to read "last cue time", and on 1.94% of
        # real corpus files the last cue is an orphan more than 120 s past the
        # rest (`Gintama - 074.ass`: 429 cues to ~1,475 s, plus one at
        # 3,616.9 s). Fed the raw maximum, `duration_verdict` calls a perfectly
        # good subtitle IMPOSSIBLE for its own video. `HANDOFF.md` carried this
        # as open at 3b; use `set_content_end()` and it cannot be got wrong.
        self.cues = cues

    @property
    def dirname(self):
        return os.path.dirname(self.path)

    @property
    def name(self):
        return os.path.basename(self.path)

    def set_content_end(self, cue_starts):
        """Fill in `cues` from a list of cue-start moments. -> the value set.

        ⭐ The one writer for that field IN THIS CODEBASE, so
        `duration.content_end`'s orphan walk is not skipped by a caller
        reaching for `max()`. `doctrine/architecture` rule 4: a derived value
        needs one writer.

        ⚠ AND THE CLAIM STOPS THERE. An earlier version of this said the field
        *"cannot be got wrong"*, and an adversarial pass measured three ways to
        get it wrong: `Item(..., cues=max(starts))` through the constructor
        parameter, a plain `item.cues = ...`, and a plain assignment AFTER a
        correct `set_content_end`. `cues` is a `__slots__` entry and Python
        cannot stop any of them.

        ⭐ What holds is that **nothing in this package does it**: `walk()` and
        `parse_all()` never pass `cues=`, and
        `test_nothing_in_the_package_writes_Item_cues_by_hand` reads the source
        tree and fails if that changes. A grep-able check is the enforceable
        version of a claim prose could only assert.
        """
        from . import duration as _duration

        self.cues = _duration.content_end(cue_starts)
        return self.cues

    @property
    def key(self):
        """(season, episode) — ⚠ never episode alone. See the module note."""
        return self.parsed.key() if self.parsed else (None, None)

    @property
    def title(self):
        return self.parsed.title if self.parsed else u""

    def __repr__(self):
        return "Item(%s, %s, %r)" % (self.kind, self.name[:28],
                                     self.key if self.parsed else None)


def is_junk(path):
    """Should discovery ignore this file entirely?

    ⚠ Returns True for things that are NOT subtitles or videos too — the
    caller filters on extension first, so this is only about files that would
    otherwise look pairable.
    """
    name = os.path.basename(path)
    lowered = name.lower()
    if lowered in SKIP_NAMES or lowered.startswith("."):
        return True
    if lowered.endswith(SKIP_SUFFIXES):
        return True
    stem = os.path.splitext(lowered)[0]
    if any(stem.endswith(marker) for marker in ALREADY_SYNCED):
        return True
    # `sample.mkv`, `Show - 01-sample.mkv`, `sample/` — but not `Free! Samples`
    for marker in SAMPLE_MARKERS:
        if stem == marker or stem.endswith("-" + marker) or \
                stem.endswith("." + marker):
            return True
    return False


def classify(path):
    """"video" | "subtitle" | None, from the extension alone.

    ⚠ A HINT, exactly as `formats` treats it: the magic bytes decide what a
    file really is. This only decides what is worth opening.
    """
    ext = os.path.splitext(path)[1].lower()
    if ext in KNOWN_VIDEO_EXT:
        return "video"
    if ext in KNOWN_SUBTITLE_EXT:
        return "subtitle"
    return None


def walk(roots, follow_links=False, recurse=True):
    """Every video and subtitle under `roots`. -> [Item], unparsed.

    ⛔ One walk, whatever the layout. There is no branch here for *film in its
    own folder* against *a tree of subtitles* — those are the same walk with
    different scores later.

    ⚠ `recurse=False` is `05-interface.md`'s `--no-recurse`: the named
    directories themselves and nothing below them. It is a keyword with a
    default because this function is one of the four shapes hato pins
    (`RUNBOOK.md` 3b) — adding a parameter is compatible, changing one is not.
    """
    if isinstance(roots, (str, bytes)) or hasattr(roots, "__fspath__"):
        roots = [roots]
    seen = set()
    items = []
    for root in roots:
        root = str(root)
        if os.path.isfile(root):
            kind = classify(root)
            # 🚨 THE `seen` DEDUPE APPLIES HERE TOO, AND IT DID NOT. Found by
            # an adversarial pass: `walk([dir, a_file_inside_it])` returned the
            # SAME path twice, and so did `walk([S, S.upper()])` on Windows.
            #
            # ⛔ Two `Item`s for one file become two `dedupe.Candidate`s for
            # one slot, and `dedupe.plan` supersedes *every candidate that is
            # not the winner object* -- compared by identity, so the duplicate
            # loses and `apply_plan` trashes the user's only copy while the
            # report names it as some other file's supersession.
            #
            # ⚠ Reachable from an ordinary shell: a glob that expands to a
            # folder plus a file inside it, or a case-differing drive letter.
            # ⭐ `normcase(realpath(...))` is the same identity `explicit.py`
            # uses, for the same reason.
            real = os.path.normcase(os.path.realpath(os.path.abspath(root)))
            if kind and not is_junk(root) and real not in seen:
                seen.add(real)
                items.append(Item(os.path.abspath(root), kind))
            continue
        for dirpath, dirnames, filenames in os.walk(root,
                                                    followlinks=follow_links):
            dirnames[:] = [d for d in dirnames
                           if d.lower() not in SKIP_NAMES
                           and not d.startswith(".")]
            # ⚠ Pruned rather than `break`-ed, because a break stops the whole
            # walk of this root while emptying `dirnames` stops only the
            # descent — and with several roots those are different things.
            #
            # ⛔ AND IT DEPENDS ON `topdown=True`, WHICH IS `os.walk`'s DEFAULT
            # AND IS NOT PASSED HERE. Python's contract is explicit that
            # modifying `dirnames` has **no effect** when `topdown=False`. An
            # earlier version of this comment claimed the opposite — that
            # pruning was the robust choice *because* a break would break under
            # `topdown=False` — and an adversarial pass measured it: forced to
            # `topdown=False`, `recurse=False` returned every file in the tree.
            # ⭐ `LEDGER-HOT.md`'s *grep the code for the threshold the
            # docstring says is not there*, in its other direction: a comment
            # claiming robustness against a change it does not survive.
            if not recurse:
                dirnames[:] = []
            for filename in filenames:
                path = os.path.join(dirpath, filename)
                kind = classify(path)
                if not kind or is_junk(path):
                    continue
                # ⚠ Same identity as the file-root branch above, so the two
                # cannot disagree about whether they have already seen a file.
                real = os.path.normcase(os.path.realpath(
                    os.path.abspath(path)))
                if real in seen:
                    continue
                seen.add(real)
                items.append(Item(os.path.abspath(path), kind))
    return items


def parse_all(items, scheme_hint=True):
    """Fill in `parsed` for every item, using the per-folder scheme as the
    second opinion where one can be inferred.

    ⭐ `09-corpus-strategy.md` Stage 1: ours first, the folder scheme as the
    independent check, the other parsers only on doubt. The folder scheme is
    inferred ONCE per directory, not once per file.
    """
    from .naming import episode as E
    from .naming import scheme as S

    by_dir = {}
    for item in items:
        by_dir.setdefault(item.dirname, []).append(item)

    for dirname, group in by_dir.items():
        hint = None
        if scheme_hint and len(group) >= S.MIN_FILES:
            try:
                hint = S.resolve_folder([i.name for i in group])
            except Exception:            # noqa: BLE001
                hint = None              # a scheme is an accelerator, never
                                         # a dependency (00-INDEX Rule 1)
        for item in group:
            scheme_episode = None
            if hint is not None:
                try:
                    scheme_episode = S.episode_of(item.name, hint)
                except Exception:        # noqa: BLE001
                    scheme_episode = None
            item.parsed = E.union(item.name, scheme_episode=scheme_episode)
    return items


def proximity(a, b):
    """How close two files sit. ⭐ A SCORE, never a gate.

    Returning 0.0 for *different tree* rather than refusing is the whole
    reason layouts 5-7 work — a folder of subtitles beside a folder of videos
    is the normal case for the people this tool is for, not an error.
    """
    da, db = os.path.normcase(a.dirname), os.path.normcase(b.dirname)
    if da == db:
        return SAME_DIR
    if da.startswith(db + os.sep) or db.startswith(da + os.sep):
        return PARENT_OR_CHILD
    if os.path.dirname(da) == os.path.dirname(db):
        return SIBLING
    # A shared ancestor beyond the drive root is still a hint.
    #
    # 🚨 `commonpath` RAISES `ValueError: Paths don't have the same drive` on
    # two UNC shares, and the `da[:1] == db[:1]` guard cannot see it because
    # **both UNC paths start with a backslash**. `\\nas\media` against
    # `\\nas\subs` -- one server, two shares -- raised, and that is the
    # canonical two-folder layout for the people this tool is for.
    #
    # ⛔ Before 3b nothing public called this, so the crash was unreachable;
    # `scan()` made it the first thing any caller hits. Found by an adversarial
    # pass, which drove it end to end and watched a `ValueError` escape the
    # library that promises to *return structured results*.
    #
    # ⭐ Caught rather than predicted. Enumerating the path shapes that share a
    # first character is how this was got wrong once already -- `os.path` knows
    # what it cannot compare, and the answer when it cannot is ELSEWHERE, which
    # is a SCORE and never a refusal.
    try:
        common = os.path.commonpath([da, db])
    except ValueError:
        return ELSEWHERE
    if common and common not in (os.sep, ""):
        return SAME_ROOT
    return ELSEWHERE


def duration_verdict(video, subtitle):
    """"reject" | "ok", from runtime alone. ⭐ The cheapest possible filter.

    `06-edge-cases.md` §3.45, and it is Sonic's observation: *"you won't have a
    movie that is 1 hour long and subs that are 1 hour 30 minutes."*

    ⛔ THIS IS NOW A THIN ADAPTER. The rule and every constant live in
    `tsubasa/duration.py` (RUNBOOK A9), which fitted them against measured
    populations. This function exists only to keep the `Item`-shaped,
    two-word contract the pairing path already uses.

    🚨 WHAT IT REPLACED, AND WHY THAT MATTERED. The hand-written version here
    carried a **0.50 short bound** — reject anything under half the video's
    runtime — and A9 measured the lowest *correct* same-video ratio at
    **0.056**. It also used a 1.15 long bound where the measured cost/yield
    optimum is 1.25 plus a 120 s absolute floor.
    ⭐ It was never called by anything, so it cost nothing; but it was a
    landmine wired to the first caller. See `LEDGER.md` §Logic, A9.

    ⚠ `UNKNOWN` maps to `"ok"`, exactly as before: **absent is not short.**
    """
    from . import duration as _duration

    verdict, _reason = _duration.duration_verdict(video.duration, subtitle.cues)
    return "reject" if verdict == _duration.IMPOSSIBLE else "ok"


class Candidates(object):
    """The pairs worth scoring, built from an index rather than a loop.

    🚨 O(videos + subtitles), never O(videos × subtitles). At *500 videos ×
    1500 subs* the naive form is 750,000 comparisons; keyed on (season,
    episode) it is one pass plus the handful of subtitles that share a key.

    ⚠ Films have no episode key, so they cannot use this index at all — they
    are matched by stem and title, which is a different and much smaller
    population. Keeping them out of the episode index is what stops every
    film in a library colliding on `(None, None)`.
    """

    __slots__ = ("videos", "subtitles", "_by_key", "_by_episode",
                 "_by_season", "_speculative", "_offsets")

    def __init__(self, items):
        self.videos = [i for i in items if i.kind == "video"]
        self.subtitles = [i for i in items if i.kind == "subtitle"]
        self._by_key = {}         # (season, episode) -> subs, EXACT
        self._by_episode = {}     # episode -> subs, any season
        #: season -> subs. ⭐ ONLY read by the absolute-numbering fallback,
        #: and only for a video that would otherwise get nothing at all.
        self._by_season = {}
        #: (video.path, sub.path) for every pair the fallback invented.
        #: ⛔ Load-bearing downstream: `dedupe` may never TRASH one of these.
        self._speculative = set()
        #: video.path -> a derived episode shift. Filled by `set_offsets`.
        self._offsets = {}
        for sub in self.subtitles:
            season, episode = sub.key
            if episode is None:
                continue                 # a film, or an unparsed name
            # ⛔ AND THE EXCLUSION IS SYMMETRIC. Gating only the VIDEO side
            # leaves `Toy Story 2 (1999).en.srt` filed under episode 2, where
            # it is offered to every `- 02` video in the library. Measured
            # while wiring A10: the video side alone gave `Show - 02.mkv` two
            # candidates, one of them a film's subtitle.
            # ⭐ A file the movie path owns is out of the episode index on
            # BOTH sides, or the index still carries the collision it was
            # built to prevent.
            if self.is_film(sub):
                continue
            # 🚨 A SEASONED SUBTITLE IS INDEXED UNDER ITS OWN SEASON AND
            # NOWHERE ELSE. The first version also filed it under
            # `(None, episode)` as a convenience, which handed `Show S01E03`
            # to an `S03E03` video -- reintroducing, inside the index built to
            # prevent it, the exact 305-false-pair defect `LEDGER-HOT.md`
            # records as made three times. Caught by the check named after it.
            self._by_key.setdefault((season, episode), []).append(sub)
            self._by_episode.setdefault(episode, []).append(sub)
            if season is not None:
                self._by_season.setdefault(season, []).append(sub)

    def for_video(self, video):
        """Subtitles that could belong to this video. Never the whole set.

        ⭐ The leniency is SYMMETRIC and it is about what a name does not say,
        never about mixing two things that disagree:

        * a video with a season sees that season's subtitles, **plus the
          season-less ones** — `Show - 03.srt` in a `S02` folder is episode 3
          of season 2, and there is nothing in the name to say otherwise
        * a season-less video sees every season's episode 3, because it has
          made no claim either
        * two names that BOTH state a season and state different ones are
          never candidates

        ⚠ A season-less subtitle reaching several seasons is not a defect —
        it is an honest ambiguity, and `06-edge-cases.md` §4 gives it to
        timing arbitration rather than to a guess about folders.
        """
        season, episode = video.key
        if episode is None:
            return []
        # ⛔ A FILM NEVER USES THE EPISODE INDEX, even when its name parsed to
        # an episode number. `Toy Story 2 (1999)` yields episode 2 and would
        # otherwise collect every `- 02` subtitle in the library while the
        # movie path is also claiming it. See `films()` for the measurement.
        if self.is_film(video):
            return []
        if season is None:
            return list(self._by_episode.get(episode, ()))
        out = []
        seen = set()
        for key in ((season, episode), (None, episode)):
            for sub in self._by_key.get(key, ()):
                if id(sub) not in seen:
                    seen.add(id(sub))
                    out.append(sub)

        shift = self._offsets.get(video.path)
        if shift:
            # 🚨 A DERIVED SHIFT MAKES THE BY-NUMBER PAIR SUSPECT TOO, AND
            # THAT IS THE WHOLE POINT OF THIS BRANCH.
            #
            # When season 1 ran twelve and the subtitles are absolute, the two
            # ranges OVERLAP: video `S02E13` finds subtitle `S02E13`, which is
            # really episode 1. Measured — twelve of twenty-four videos paired
            # with the wrong file and the other twelve got nothing, because
            # `out` was non-empty and short-circuited the fallback.
            #
            # ⛔ So both readings are offered and TIMING decides, and every one
            # of them is speculative: trashing the loser would destroy either
            # a real subtitle for another episode or the one the user has.
            for sub in self._by_key.get((season, episode + shift), ()):
                if id(sub) not in seen:
                    seen.add(id(sub))
                    out.append(sub)
            for sub in out:
                self._speculative.add((video.path, sub.path))
            return out

        return out or self._absolute_fallback(video, season)

    def set_offsets(self, mapping):
        u"""video.path -> the shift its subtitles appear to carry.

        ⛔ Computed by `api.Scan`, not here: grouping needs SERIES IDENTITY,
        and the whole reported case is a video called `Hell Mode` beside a
        subtitle called `ヘルモード ~やり込み好きの…~`. Grouping on the parsed
        title would put them in different groups and no shift would ever form.
        ⭐ Pushed INTO the index so both callers of `for_video` — `Scan` and
        `pipeline` — see the same answer.
        """
        self._offsets.update(mapping)
        return self

    def _absolute_fallback(self, video, season):
        u"""Same season, ANY episode. ⛔ Only for a video offered nothing.

        ===================================================================
        🚨 ABSOLUTE EPISODE NUMBERING
        ===================================================================

        Reported by Sonic against his own library, 2026-09-10:
        `[SubsPlease] Hell Mode S2 - 10` and
        `ヘルモード…S02E22…ABEMA.ja[cc].srt` are **the same episode**, and
        nothing was ever offered for the video. Both names parse correctly and
        the alias table links the two titles at **1.0** — the only thing that
        disagrees is the number.

        ⭐ **ABEMA and DMMTV write a per-season SEASON tag with an ABSOLUTE
        episode number.** Measured across the three files in that folder:
        `E17 → ep 5`, `E18 → ep 6`, `E22 → ep 10` — a constant −12, and
        season 1 ran twelve episodes. The two halves of one filename are
        counting on different scales, and no amount of parsing fixes that
        because both readings are internally consistent.

        ⛔ **The offset is NOT derivable here and this does not try.** One
        video and three subtitles admit three different offsets. Instead the
        same-season set is offered as a HYPOTHESIS and the timing decides —
        which is the whole architecture: *pairing is decided by timing*
        (`05-interface.md`), and `align()` refuses a wrong episode rather than
        guessing (measured: 23% match, and a segment wanting +5.2 s).

        ⚠ **THREE GUARDS, and each one is load-bearing:**

        1. ⛔ **It fires ONLY when the ordinary path returned nothing.** Every
           video that pairs today is untouched, so this cannot change a single
           existing answer — it can only fill in a blank.
        2. ⛔ **Same season only.** `LEDGER-HOT.md`: grouping on episode alone
           made *Series 1 Ep 3* score against *Series 3 Ep 3* and manufactured
           **305 false pairs**, three times. That guard is not reopened: a
           video and a subtitle that both state a season and state different
           ones are still never candidates.
        3. ⛔ **Every pair is marked SPECULATIVE**, and `dedupe` may never
           trash one. Without that, offering E17/E18/E22 to the ep-10 video
           and letting E22 win would send the other two — subtitles for
           episodes the user has no video for — **to the trash**, which is
           `LEDGER-HOT.md`'s *a slot cannot decide what to throw away* through
           a new door.
        """
        pool = self._by_season.get(season, ())
        if not pool:
            return []
        # 🚨 THE TRIGGER, AND THE FIRST VERSION OF IT WAS WRONG.
        #
        # *"The video was offered nothing"* is not rare — it is the ORDINARY
        # state of a partly-subtitled library, and `Scan.unpaired`'s own
        # docstring says so: *a folder with 24 videos and 20 subtitles has
        # four of these and is working perfectly.* Firing on that would spend
        # an alignment per candidate rediscovering that a subtitle simply is
        # not there, and would erase `unpaired`, which is a real signal.
        # Caught by `test_a_video_with_nothing_to_pair_is_unpaired_not_a_result`.
        #
        # ⭐ THE DISCRIMINATOR IS DISJOINTNESS, and only the RUN can see it.
        # If any video in this season shares an episode number with any
        # subtitle in it, the two sides are counting the same way and a gap is
        # just a gap. Hell Mode's folder has videos {10} against subtitles
        # {17, 18, 22} — no overlap at all, which is what a difference in
        # numbering SCHEME looks like from the outside.
        if self._numbering_agrees(season):
            return []
        # ⚠ BOUNDED. A season of 300 subtitles would otherwise cost one
        # alignment each for a single unpaired video. The cap is generous
        # against real seasons and is a cost bound, not a correctness one --
        # `identity` filtering upstream is what makes the set precise.
        # ⚠ NO "skip the exact match" GUARD HERE, DELIBERATELY. The first
        # version had one and a mutant deleting it survived, because it is
        # unreachable: this method only runs when the ordinary lookup came
        # back EMPTY, and a subtitle carrying this video's own episode number
        # would have been in `_by_key[(season, episode)]` and made it
        # non-empty. `doctrine/verification`: *a mutant that cannot fail is
        # noise, and noise is what gets a check switched off.*
        out = []
        for sub in pool:
            out.append(sub)
            if len(out) >= ABSOLUTE_FALLBACK_CAP:
                break
        for sub in out:
            self._speculative.add((video.path, sub.path))
        return out

    def _numbering_agrees(self, season):
        u"""Do the videos and subtitles of `season` share ANY episode number?

        -> bool. ⭐ One shared number is enough: it proves both sides count
        the same way, so a video with no subtitle is a video with no subtitle.
        ⛔ Computed over the whole RUN, because a single video cannot tell a
        gap from a different scale — which is the whole reason the offset is
        not derivable and the fallback offers a hypothesis instead.
        """
        subs = set()
        for sub in self._by_season.get(season, ()):
            subs.add(sub.key[1])
        if not subs:
            return False
        for video in self.videos:
            v_season, v_episode = video.key
            if v_episode is None or self.is_film(video):
                continue
            if v_season == season and v_episode in subs:
                return True
        return False

    def was_speculative(self, video_path, subtitle_path):
        u"""Did the absolute-numbering fallback invent this pair? -> bool

        ⛔ THE TRASH DEPENDS ON THIS ANSWER. One accessor, so the index and
        `dedupe` cannot drift into disagreeing about which pairs were guesses.
        """
        return (video_path, subtitle_path) in self._speculative

    def films(self):
        """Videos the MOVIE path owns. ⭐ Not merely "no episode number".

        🚨 A NUMBERED SEQUEL PARSES AS AN EPISODE, so `key == (None, None)`
        misses it and the file is claimed by BOTH paths. Measured at A10 over
        904 real Western release names: **45 of them, 5.0%** —
        `Toy Story 2 (1999)` → episode 2, `Iron Man 3` → 3, `Alien 3` → 3,
        `Shrek 2` → 2 — every one bucketing a film library under a fabricated
        episode, which is the `Inception (2010)` → `(None, 2010)` defect
        `LEDGER.md` §Logic already records, wearing a smaller number.

        ⛔ Being paired twice is a CORRECTNESS bug, not an inefficiency: the
        two paths can reach different answers and both write.

        ⭐ `movies.read_name()` is the one authority on whether a name is a
        film — it has the context the parser deliberately does not (a release
        year, no explicit episode marker, and the number sitting BEFORE the
        year). ⚠ Ruled 2026-09-08: that rule stays in `movies.py`. The
        parser's job is to extract an episode when one exists; deciding that
        `Toy Story 2` is a film is a different question. Promote it only if
        the same shape shows up on the anime side.
        """
        from . import movies as _movies

        out = []
        for video in self.videos:
            if video.key == (None, None):
                out.append(video)
            elif _movies.read_name(video.name, getattr(video, "parsed", None)).is_film:
                out.append(video)
        return out

    def is_film(self, item):
        """Does the MOVIE path own this item? ⭐ One accessor, so the episode
        index and `films()` cannot drift into disagreeing about a file."""
        from . import movies as _movies

        if item.key == (None, None):
            return True
        return _movies.read_name(item.name,
                                 getattr(item, "parsed", None)).is_film

    def fan_out(self):
        """Candidates per video, for the benchmark. ⚠ Print the denominator."""
        return {v.path: len(self.for_video(v)) for v in self.videos}
