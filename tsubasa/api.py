# -*- coding: utf-8 -*-
u"""
The library API. RUNBOOK step 3b. Authority: `05-interface.md` §*The library
API*, `03-permissions.md` §*The three outcomes*, `09-corpus-strategy.md` §Stage
3-4.

===========================================================================
⭐ THIS IS THE PRODUCT. The CLI (3c) and the GUI (3d) are wrappers over it.
===========================================================================

    from tsubasa import scan, sync, align, Result

    cands   = scan(videos="/media/anime/s2", subs="/data/subs")
    results = sync(cands)                       # measures. Writes NOTHING.
    results = sync(cands, write=True)           # the only call that writes.

`05-interface.md` gives three constraints and they are the reason this module
looks the way it does:

  1. ⛔ **Never assumes it owns a directory.** Takes paths *or* iterables.
  2. ⛔ **Ignores non-subtitle files silently.** Junk is expected input, not an
     error -- surasura's real case is a subtitle folder full of `.txt`.
  3. ⛔ **Returns structured results. Prints nothing. Writes nothing unless
     told.**

---------------------------------------------------------------------------
🚨 `sync()` TAKES A `PairPlan`, NEVER RAW TUPLES -- RULED 2026-09-08, BINDING
---------------------------------------------------------------------------

`05-interface.md` promises `sync([(video, subtitle), ...], write=True)`
natively, and the tuple signature stays. But the tuples are converted through
`explicit.explicit_pairs()` and the work is done from the resulting `PairPlan`.

Sonic's words: *"a tuple path that silently skips every refusal is the one
shape the whole project exists to prevent."* A11 built five refusals -- the
missing path, the swapped arguments, the same subtitle claimed twice, the
directory given where a file goes, the 8 GB file that is not a subtitle -- and
a `for video, subtitle in pairs:` loop here would walk past every one of them.

⚠ And `force` routes to `ExplicitPair.decide(verdict, force=True)`, **never**
to `explicit_pairs()`, which has no such parameter. That routing IS the
mechanism: force overrides a VERDICT and can never override a broken input.

---------------------------------------------------------------------------
⭐ WHERE THE WORK HAPPENS -- scan() HYPOTHESISES, sync() DECIDES
---------------------------------------------------------------------------

🚨 A SPEC CONFLICT, RESOLVED HERE AND RECORDED (Part 1 defect).
`05-interface.md`'s comment says `scan()` reads *"filenames, stat and the
container INDEX only (30 KB per MKV)"*; `RUNBOOK.md` step 3b says `scan()`
returns candidate sets **"(no media I/O)"**. Those are different contracts --
30 KB per MKV is the Cues-indexed TIMING read (1d), not a header peek, and on a
1,500-file library it is minutes of work before a single decision is made.

⭐ Built to the tighter one: **`scan()` opens nothing inside the tree it was
given.** It walks names, parses them, and returns hypotheses. Every read of the
user's files -- the container, the subtitle, the duration gate -- happens in
`sync()`, which needs the track's timing anyway, so a read in `scan()` would be
either duplicated or cached, and both are worse than not doing it.
`05-interface.md` already says the important half: *"`scan()` returns hypotheses
and `sync()` returns the pairs it made."*

⚠ **IT IS NOT "OPENS NOTHING", AND THAT WORDING WAS HERE UNTIL AN ADVERSARIAL
PASS SPIED ON IT.** Ranking asks `series.same_series`, which loads this
project's own bundled data -- a 4.2 MB gzipped alias table and the decoration
vocabulary -- once per process. Measured over a fully drained scan: **0 opens
inside the scanned tree, 2 outside it**, both under `tsubasa/data/`.
⭐ The distinction is the whole contract. What `scan()` promises is that it does
not touch the user's media, and that is what
`test_scan_opens_no_file_inside_the_tree_it_was_given` enforces. Bundled data is
this program's own weight, and the argument for the tighter reading -- *minutes
of work before a single decision* -- was about per-file media reads, which scale
with the library, not about one table that does not.

⚠ The visible consequence: without runtimes the movie path refuses a set of
films it cannot separate on name and folder alone. `sync()` re-runs the same
`movies.pair_movies()` **with** the durations it has opened, and that is the
pairing that decides. One authority called twice with different evidence, never
two implementations.
"""
import os

from . import discover as _discover
from . import movies as _movies
from . import sidecar as _sidecar
from .naming import series as _series
from .verdict import (BITMAP_TRACK, CONFIDENCE_WORDS, CONFIDENT, ERROR,
                      OUTCOMES, REFUSED, SPEECH_MASK, TEXT_TRACK)

# ---------------------------------------------------------------------------
# how a candidate is ranked, with no file opened
# ---------------------------------------------------------------------------
# `09-corpus-strategy.md` Stage 2 ranks by identity and Stage 3 adds proximity
# as a SCORE. Both are computed from names alone, which is what lets the whole
# of `scan()` stay off the disk.
#
# ⚠ DIFFERENT IS NOT TERMINAL. `RUNBOOK.md` Track A: *9.9% of real pairs are
# DIFFERENT-by-title and right* -- a Japanese folder name against an English
# release name reaches DIFFERENT honestly. It sorts last; it is never dropped,
# because timing is what decides and this is only the order it decides in.
_IDENTITY_RANK = {_series.SAME: 0, _series.UNSURE: 1, _series.DIFFERENT: 2}


class Candidacy(object):
    u"""One subtitle offered for one video, and the name-level evidence for it.

    ⚠ A HYPOTHESIS. Nothing here has been measured -- `identity` and
    `proximity` are computed from the two filenames and the two directories,
    and `05-interface.md` is explicit that *pairing is decided by timing*.
    """

    __slots__ = ("video", "subtitle", "identity", "score", "proximity",
                 "reason", "speculative")

    def __init__(self, video, subtitle, identity, score, proximity, reason,
                 speculative=False):
        #: ⛔ THE ABSOLUTE-NUMBERING FALLBACK INVENTED THIS PAIR, and the
        #: trash depends on knowing that: `dedupe` may never supersede a
        #: speculative loser. See `discover.Candidates._absolute_fallback`.
        self.speculative = bool(speculative)
        self.video = video              # discover.Item
        self.subtitle = subtitle        # discover.Item
        #: `series.SAME` / `UNSURE` / `DIFFERENT`.
        self.identity = identity
        self.score = score              # the title similarity, 0..1
        self.proximity = proximity      # discover.proximity, 0..1
        self.reason = reason

    @property
    def rank_key(self):
        u"""Ascending: best first.

        ⚠ The path is the last key and it is there for STABILITY, not for
        preference -- two candidates identical on every real signal must not
        change order between runs, or a re-run renames a different file.
        """
        return (_IDENTITY_RANK.get(self.identity, 3), -self.score,
                -self.proximity, self.subtitle.path)

    def __repr__(self):
        return "Candidacy(%s <- %s, %s %.2f, prox %.1f)" % (
            self.video.name[:24], self.subtitle.name[:24], self.identity,
            self.score, self.proximity)


# ---------------------------------------------------------------------------
# what a scan found
# ---------------------------------------------------------------------------

class Scan(object):
    u"""What is here, and what might pair with what.

    ⛔ **Nothing under the scanned roots was opened** -- not a container, not a
    subtitle, not a `stat` beyond what the walk itself needs. ⚠ The alias table
    and the decoration vocabulary under `tsubasa/data/` are loaded on demand by
    the identity ranking; they are this program's own weight, not the user's
    media. See the module note.

    ⭐ NOT ITERABLE, for the same reason `MoviePairing` and `PairPlan` are not:
    `for x in scan_result` would walk one half and silently lose the other.
    Name the half you want.
    """

    __slots__ = ("videos", "subtitles", "candidates", "films", "skipped",
                 "roots", "_identity_cache", "_ranked", "_film_subs",
                 "_by_path", "_film_refusals")

    def __init__(self, videos, subtitles, candidates, films, skipped, roots):
        # 🚨 O(videos + subtitles), NOT O(videos x subtitles). `discover.py`
        # states that invariant in red -- *at 500 videos x 1500 subs the naive
        # form is 750,000 comparisons* -- and `for_video` broke it by looping
        # `films.pairs` per video and linear-scanning `self.subtitles` inside
        # that. Measured by an adversarial pass on a pure film library:
        # 100 films 0.072 s, 800 films 1.328 s -- **2x the input, 4.4x the
        # time**, extrapolating to ~20 s of bookkeeping on 3,000 films before a
        # byte of media is read. Two dicts, built once.
        self._film_subs = {}
        self._by_path = {}
        self._film_refusals = {}
        self.videos = videos            # [discover.Item]
        self.subtitles = subtitles      # [discover.Item]
        #: `discover.Candidates` -- the (season, episode) index.
        self.candidates = candidates
        #: `movies.MoviePairing` -- ⚠ PROVISIONAL. Made without runtimes, so
        #: `sync()` re-runs it with the durations it opens. See the module note.
        self.films = films
        #: {path: reason} -- discovered, and deliberately not offered to
        #: anything. A creditless opening is the case this exists for.
        self.skipped = skipped
        self.roots = roots
        self._identity_cache = {}
        self._ranked = {}
        for sub in subtitles:
            self._by_path[sub.path] = sub
        for pair in films.pairs:
            self._film_subs.setdefault(pair.video, []).append(pair)
        # ⭐ The film path's own refusal sentences, by subtitle. `_nothing_reason`
        # used to invent a generic line while THIS was sitting unused --
        # `03-permissions.md` §hand-back asks for what was measured, why it
        # fell short and what would change it, and this is the only place that
        # knows.
        for refusal in films.refusals:
            self._film_refusals[refusal.subtitle] = refusal
        # ⭐ LAST, because it needs the film gate and the identity cache above
        # it, and it pushes its answer INTO the index so `pipeline` — which
        # calls `candidates.for_video` directly — sees the same thing this
        # object does. ⛔ Opens no file: `scan()` promises that, and this reads
        # only parsed names.
        self._derive_offsets()

    # -- the one accessor over the candidate sets --------------------------

    def for_video(self, video):
        u"""Every subtitle that could belong to this video, best first.

        -> [`Candidacy`]. ⭐ `doctrine/architecture` rule 2: this is the one
        place the candidate sets are read, so the TV index and the movie path
        cannot drift into disagreeing about which subtitles a video may see.
        """
        cached = self._ranked.get(video.path)
        if cached is not None:
            return list(cached)

        subs, notes = list(self.candidates.for_video(video)), {}
        for pair in self._film_subs.get(video.path, ()):
            sub = self._by_path.get(pair.subtitle)
            if sub is not None:
                subs.append(sub)
                notes[sub.path] = pair.reason
        out = self._candidacies(video, subs, notes)
        self._ranked[video.path] = out
        return list(out)

    def rank(self, video, subtitles):
        u"""`subtitles` ranked for `video`, best first. -> [`Candidacy`]

        ⭐ The ranking RULE is not here -- it is `Candidacy.rank_key`, and this
        only sorts by it. `sync()` needs this because its film half comes from
        the pairing made WITH runtimes, not from `Scan.films`, which is
        provisional; calling `for_video` there would silently use the weaker
        answer.
        """
        return self._candidacies(video, subtitles)

    def pairings(self):
        u"""Every video with something to try, and its ranked candidates.

        -> [(`discover.Item`, [`Candidacy`])]. ⚠ Videos with NOTHING to try are
        not in here; they are `unpaired()`, which is a different fact and must
        not be read as a refusal.
        """
        out = []
        for video in self.videos:
            cands = self.for_video(video)
            if cands:
                out.append((video, cands))
        return out

    def unpaired(self, lang=None):
        u"""Videos no subtitle was offered for. -> [(`discover.Item`, reason)]

        🚨 Not a refusal and not an error -- a folder with 24 videos and 20
        subtitles has four of these and is working perfectly. It is reported
        because a silent nothing reads as success (`doctrine/robustness`).

        `lang`
            ⭐ count only subtitles in this language. `unpaired(lang="ja")` is
            *which videos have no Japanese subtitle*, the question a fetcher
            asks — and without it a video carrying only an English subtitle
            read as covered, so hato would never have fetched for it.
            `ja`, `jpn`, `JA` and `ja-JP` all mean the same thing here.

            ⚠ An UNTAGGED subtitle is `und` and counts as no language:
            `hato/spec/06-edge-cases.md` rules that `<video>.srt` is **not**
            the target language. ⛔ A tag this reader does not recognise
            raises instead of quietly becoming `und`, because that would mark
            every video in the library unpaired.
        """
        want = None if lang is None else _language_asked_for(lang)
        out = []
        for video in self.videos:
            offered = self.for_video(video)
            if want is not None:
                matching = [c for c in offered if c.subtitle.lang == want]
                if not matching and offered:
                    out.append((video, _other_languages_reason(want, offered)))
                    continue
                offered = matching
            if offered:
                continue
            out.append((video, self._nothing_reason(video)))
        return out

    # -- reporting ---------------------------------------------------------

    def summary(self):
        u"""One line. ⚠ Anything needing attention leads it."""
        head = []
        if self.skipped:
            head.append(u"%d skipped" % len(self.skipped))
        if self.films.refusals:
            # 🚨 A `MovieRefusal` IS ABOUT A SUBTITLE, NOT A FILM -- read
            # `movies.MovieRefusal.subtitle`. This line said *"1 film not
            # paired"* for *"1 subtitle found no film"*, on the headline line
            # of the ruled CLI output, and with two films in the folder the
            # count was wrong about which side it was counting. Found by an
            # adversarial pass.
            head.append(u"%d subtitle%s found no film"
                        % (len(self.films.refusals),
                           u"" if len(self.films.refusals) == 1 else u"s"))
        tail = [u"%d video%s" % (len(self.videos),
                                 u"" if len(self.videos) == 1 else u"s"),
                u"%d subtitle%s" % (len(self.subtitles),
                                    u"" if len(self.subtitles) == 1 else u"s")]
        return u" · ".join(head + tail)

    def __iter__(self):
        raise TypeError(
            "a Scan is not iterable: iterating it would walk one of "
            ".videos / .subtitles / .films and silently lose the others, "
            "including the files it skipped. Call .pairings() for what to "
            "try, .unpaired() for the videos with nothing, and .skipped for "
            "what was deliberately left out.")

    def __repr__(self):
        return "Scan(%s)" % self.summary()

    # -- internals ---------------------------------------------------------

    def _derive_offsets(self):
        u"""Find, per video, the episode shift its own series appears to carry.

        ===================================================================
        ⭐ THIS IS HERE AND NOT IN `discover` BECAUSE IT NEEDS IDENTITY
        ===================================================================

        The reported case is a video called `Hell Mode` beside subtitles
        called `ヘルモード ~やり込み好きのゲーマーは廃設定の異世界で無双する~`.
        Grouping on the parsed TITLE would put them in different groups and no
        shift could ever form; the alias table links them at **1.0** via
        Wikidata, and that is the only thing that can.

        ⚠ **Two shows in one folder get two answers**, which is the case that
        would otherwise be silently wrong: the grouping is per video, over the
        subtitles its own series claims, so a shift derived for one show is
        never applied to another.

        ⛔ Cost: identity is memoised on the two TITLES, so a season of 24
        videos and 24 subtitles is a handful of comparisons, not 576.
        """
        offsets = {}
        subs_by_season = {}
        for sub in self.subtitles:
            season, episode = sub.key
            if episode is None or self.candidates.is_film(sub):
                continue
            subs_by_season.setdefault(season, []).append(sub)

        for video in self.videos:
            season, episode = video.key
            if season is None or episode is None or \
                    self.candidates.is_film(video):
                continue
            mine = [s for s in subs_by_season.get(season, ())
                    if self._identity(video, s)[0] == _series.SAME]
            if not mine:
                continue
            # ⚠ THE VIDEO SET IS THE WHOLE SEASON'S, not this one video. A
            # single video cannot evidence a shift -- see `episode_offset`,
            # which refuses a coverage of one.
            peers = [v.key[1] for v in self.videos
                     if v.key[0] == season and v.key[1] is not None
                     and not self.candidates.is_film(v)
                     and self._identity(v, mine[0])[0] == _series.SAME]
            shift = _discover.episode_offset(peers, [s.key[1] for s in mine])
            if shift:
                offsets[video.path] = shift
        if offsets:
            self.candidates.set_offsets(offsets)
        return offsets

    def _candidacy(self, video, sub, note=None):
        identity, score, reason = self._identity(video, sub)
        if note:
            reason = u"%s; %s" % (note, reason)
        speculative = self.candidates.was_speculative(video.path, sub.path)
        if speculative:
            reason = (u"the episode numbers do not match, so this is offered "
                      u"on the chance that one of the two names counts "
                      u"episodes from the start of the series rather than "
                      u"from the start of the season; %s" % reason)
        return Candidacy(video, sub, identity, score,
                         _discover.proximity(video, sub), reason,
                         speculative=speculative)

    def _candidacies(self, video, subs, notes=None):
        u"""Build and FILTER. -> [`Candidacy`], best first.

        ⭐ ONE PLACE, because there are two callers — `for_video` here and
        `sync()` through `rank()` — and `doctrine/architecture` records what
        two resolvers for one question cost: *when one surface shows the thing
        and another shows a broken one for the same record, it is two
        resolvers, not one bug.*

        🚨 **THE SPECULATIVE FILTER IS THE PRECISION.** The index offers a
        whole season on a guess about numbering; what makes that set small and
        right is the series identity, which is already computed for every
        candidate and which the alias table answers from Wikidata. Measured on
        the case that prompted this: `Hell Mode` and
        `ヘルモード ~やり込み好きの…~` come back **SAME at 1.0**, so the three
        ABEMA subtitles survive and anything else in the folder does not.
        ⛔ A guess that identity cannot confirm is not offered at all.
        """
        out = []
        for sub in subs:
            note = (notes or {}).get(sub.path) if notes else None
            cand = self._candidacy(video, sub, note=note)
            if cand.speculative and cand.identity != _series.SAME:
                continue
            out.append(cand)
        out.sort(key=lambda c: c.rank_key)
        return out

    def _identity(self, video, sub):
        u"""`series.same_series` on the two parsed TITLES, memoised.

        ⚠ Memoised on the titles, not on the paths: a folder of 24 episodes has
        one video title and a handful of subtitle titles, so the cache turns
        24xN comparisons into a handful (`00-INDEX.md` Rule 4, asked at the
        smallest level there is).
        """
        key = (video.title, sub.title)
        got = self._identity_cache.get(key)
        if got is None:
            if not video.title or not sub.title:
                got = (_series.UNSURE, 0.0,
                       u"one of the two names yielded no title, so identity "
                       u"has nothing to compare -- timing decides")
            else:
                got = _series.same_series(video.title, sub.title)
            self._identity_cache[key] = got
        return got

    def nothing_reason(self, video):
        u"""Why this video was offered nothing. ⭐ The film path's own sentence
        where it produced one."""
        return self._nothing_reason(video)

    def _nothing_reason(self, video):
        season, episode = video.key
        if self.candidates.is_film(video):
            # 🚨 THE SPECIFIC REASON EXISTS AND WAS BEING THROWN AWAY. The
            # movie path had already said *"no video in the walk shares its key
            # 'bladerunner' and year 1982"*, and this substituted a generic
            # sentence that was also FALSE -- there was a subtitle and it had
            # been considered. `03-permissions.md` §hand-back. Found by an
            # adversarial pass on two cuts of Blade Runner.
            mine = _movies.read_name(video.name,
                                     getattr(video, "parsed", None))
            near = [r for r in self._film_refusals.values()
                    if _same_film(mine, _movies.read_name(
                        os.path.basename(r.subtitle)))]
            if near:
                return (u"the film path refused the subtitle that shares its "
                        u"name: %s" % near[0].reason)
            return (u"no subtitle in the walk pairs with this film on stem, "
                    u"title+year or sole-video-in-folder")
        if episode is None:
            return (u"no episode number could be read from this name and it "
                    u"was not claimed by the film path, so there is no key to "
                    u"look candidates up by")
        return (u"no subtitle in the walk carries episode %s%s"
                % (episode, u"" if season is None else u" of season %s" % season))


# ---------------------------------------------------------------------------
# scan
# ---------------------------------------------------------------------------

def scan(videos=None, subs=None, recurse=True, follow_links=False):
    u"""What is here, and what might pair. -> `Scan`. ⛔ Opens nothing.

        scan("/media/anime/s2")                     one folder for both
        scan(videos="/media/anime/s2", subs="/data/subs")
        scan(videos=[...paths...], subs=[...paths...])

    `videos` and `subs` each take a path or an iterable of paths, and either
    may be a FILE rather than a directory -- `05-interface.md`: *never assumes
    it owns a directory.*

    ⚠ `subs` defaults to `videos`, which is the one-folder case and by far the
    commonest. Passing `subs` explicitly never widens the video side: a file
    found under `subs` is only ever offered as a subtitle, and one found under
    `videos` only as a video. That is what makes the two-folder mode mean
    anything -- without it, a stray `.mkv` in the subtitle folder becomes a
    video to be synced.
    """
    if videos is None and subs is None:
        raise ValueError(
            "scan() needs somewhere to look: pass a path, or "
            "videos=... and subs=... . Both may be a path or a list of paths.")
    if videos is None:
        videos = subs
    video_roots = _as_roots(videos)
    sub_roots = _as_roots(videos if subs is None else subs)

    _require_roots_exist(video_roots, sub_roots)
    found = _discover.walk(video_roots, follow_links=follow_links,
                           recurse=recurse)
    if _same_roots(sub_roots, video_roots):
        video_items = [i for i in found if i.kind == "video"]
        sub_items = [i for i in found if i.kind == "subtitle"]
    else:
        sub_found = _discover.walk(sub_roots, follow_links=follow_links,
                                   recurse=recurse)
        # 🚨 THE ROOTS CAN NEST, AND THE CLAIM ABOVE WAS FALSE WHEN THEY DO.
        #
        # `scan(videos="lib", subs="lib/subs")` walked `lib` for videos, which
        # descends INTO `lib/subs` -- so a stray `.mkv` a release group left in
        # the subtitle folder became a video to be synced. The mirror image is
        # `subs="lib"` with `videos="lib/videos"`, where a subtitle sitting
        # beside the videos was collected from the subtitle side.
        # ⛔ Both checks written for this used DISJOINT roots, so neither could
        # see it. Found by an adversarial pass. `Film/Subs/` is a layout
        # `movies._sole_video_dir` documents by name.
        #
        # ⭐ THE MORE SPECIFIC ROOT WINS. A file under both `lib` and
        # `lib/subs` belongs to `lib/subs`, because that is the root the user
        # named for it -- and naming a deeper folder is how anyone expresses
        # *"the subtitles are in here"*.
        video_items = [i for i in found
                       if i.kind == "video" and not _claimed_by(i, sub_roots,
                                                                video_roots)]
        sub_items = [i for i in sub_found
                     if i.kind == "subtitle" and not _claimed_by(i, video_roots,
                                                                 sub_roots)]

    items = video_items + sub_items
    _discover.parse_all(items)

    # 🚨 NCOP / NCED -- REFUSED, NEVER GUESSED. `06-edge-cases.md` §4: a
    # creditless opening has *no dialogue at all*, so there is nothing for the
    # objective to match and any offset it "finds" is the documented 108 s
    # orphan-cue failure. `movies.is_creditless` was the one writer for this
    # rule and it was reachable only from the FILM path, so an `NCOP.mkv`
    # sitting in a season folder with an episode number went straight to the TV
    # path. Recorded as open at 3b in `HANDOFF.md`; closed here.
    #
    # ⚠ Both sides. A creditless SUBTITLE is the same fact wearing the other
    # extension, and refusing only the video leaves it offered to every episode.
    skipped = {}
    keep = []
    for item in items:
        if _movies.is_creditless(item.name):
            skipped[item.path] = (
                u"creditless opening/ending (NCOP/NCED): it carries no "
                u"dialogue, so there is nothing to align against and any "
                u"offset found would be noise")
            continue
        keep.append(item)

    videos_kept = [i for i in keep if i.kind == "video"]
    subs_kept = [i for i in keep if i.kind == "subtitle"]

    candidates = _discover.Candidates(keep)
    # ⚠ PROVISIONAL, and the module note says why: with `duration_of=None` the
    # runtime veto and the runtime tiebreak are both absent, so a set of films
    # this pass cannot separate is REFUSED rather than guessed at. `sync()`
    # runs the same function again with the durations it opens.
    films = _movies.pair_movies([v.path for v in videos_kept],
                                [s.path for s in subs_kept],
                                parsed_of=_parsed_of(keep))

    return Scan(videos_kept, subs_kept, candidates, films, skipped,
                {"videos": video_roots, "subs": sub_roots})


def _as_roots(value):
    u"""A path or an iterable of paths -> a stable tuple of strings.

    ⚠ A bare string is ONE root, never an iterable of characters. That mistake
    turns `scan("/media")` into a walk of `/`, `m`, `e`, ... and the report
    that comes back is baffling rather than wrong-looking.
    """
    if value is None:
        return ()
    if isinstance(value, (str, bytes)) or hasattr(value, "__fspath__"):
        return (str(value),)
    return tuple(str(v) for v in value)


def _same_film(video_name, subtitle_name):
    u"""Are these two `movies.MovieName`s about the same film?

    ⚠ THE EDITION IS IN THE KEY, so `Blade Runner (1982) [Final Cut]` keys as
    `bladerunnerfinalcut` and its subtitle as `bladerunner` -- they never
    compare equal. The edition is appended, so the shorter key is a PREFIX of
    the longer one.

    ⛔ A prefix relation alone would let a two-character key match half a
    library, so the YEAR is the guard rather than a length threshold: an exact
    key match needs nothing, and a prefix match needs both years present and
    equal. `LEDGER-HOT.md`: *a run of a compound title is a fragment, and a
    fragment is inside everything.*
    """
    a, b = video_name.key or u"", subtitle_name.key or u""
    if not a or not b:
        return False
    if a == b:
        return True
    if a.startswith(b) or b.startswith(a):
        return (video_name.year is not None
                and video_name.year == subtitle_name.year)
    return False


def _language_asked_for(lang):
    u"""A caller's language, resolved exactly as a filename's is. -> code

    ⭐ THROUGH THE SAME READER, so `unpaired(lang="jpn")` and a file named
    `.ja-JP.srt` can never disagree about what Japanese is.
    ⛔ Unrecognised RAISES. Resolving it to `und` would compare every subtitle
    against *no language* and report the whole library unpaired — a
    confidently wrong answer to a typo.
    """
    token = (u"%s" % (lang,)).strip().lower()
    if token == u"und":
        return token
    code = _sidecar._language_of(token)
    if code is None:
        raise ValueError(
            u"%r is not a language tag tsubasa reads from filenames. Use an "
            u"ISO 639 code as it appears in a name: ja, jpn, en, eng, zh, "
            u"ja-JP. (`und` asks for subtitles whose name carries no "
            u"language.)" % (lang,))
    return code


def _other_languages_reason(want, offered):
    u"""Why a video with subtitles still counts as unpaired for `want`."""
    found = sorted(set(c.subtitle.lang for c in offered))
    said = [u"untagged" if code == u"und" else code for code in found]
    return (u"no %s subtitle among the %d offered for it (%s)%s"
            % (want, len(offered), u", ".join(said),
               u" — an untagged name is not taken to be any language"
               if u"und" in found else u""))


def _same_roots(a, b):
    u"""Are these the same set of roots? ⚠ Compared as normalised paths.

    A raw string compare made `C:\\lib` and `c:\\lib`, and `lib` and `lib\\`,
    two different roots -- which sent the one-folder case down the two-folder
    branch and back again depending on how the caller happened to spell it.
    """
    return set(_normal(p) for p in a) == set(_normal(p) for p in b)


def _normal(path):
    return os.path.normcase(os.path.abspath(str(path))).rstrip(os.sep)


def _claimed_by(item, other_roots, own_roots):
    u"""Does a MORE SPECIFIC root on the other side own this file?

    ⭐ Longest match wins. Naming a deeper folder is how a person says *"the
    subtitles are in here"*, so the deeper root is the one that decides.
    """
    here = _normal(item.path)
    mine = max((len(r) for r in (_normal(p) for p in own_roots)
                if here == r or here.startswith(r + os.sep)), default=-1)
    theirs = max((len(r) for r in (_normal(p) for p in other_roots)
                  if here == r or here.startswith(r + os.sep)), default=-1)
    return theirs > mine


def _require_roots_exist(video_roots, sub_roots):
    u"""⛔ A root that is not there is a typo, not an empty library.

    `scan(videos="/medai/anime")` returned a perfectly cheerful empty `Scan`,
    indistinguishable from a folder with nothing in it. The guard that was here
    only caught `videos=None and subs=None`, so `subs=[]` and a mistyped path
    both slipped it. Found by an adversarial pass.

    ⚠ A root that EXISTS and holds nothing is not an error -- that is a real
    and ordinary state, and `unpaired()` reports it.
    """
    roots = tuple(video_roots) + tuple(sub_roots)
    if not roots:
        raise ValueError(
            "scan() was given an EMPTY list of paths, so there is nowhere to "
            "look. An empty result would be indistinguishable from a library "
            "with nothing in it.")
    missing = [str(p) for p in roots if not os.path.exists(str(p))]
    if missing:
        raise ValueError(
            "scan() was pointed at %d path%s that do%s not exist: %s. An "
            "empty result would be indistinguishable from a library with "
            "nothing in it."
            % (len(missing), u"" if len(missing) == 1 else u"s",
               u"es" if len(missing) == 1 else u"", u", ".join(missing[:4])))


def _parsed_of(items):
    u"""The parse `scan()` already did, handed to the movie path.

    ⭐ `00-INDEX.md` Rule 4 at the smallest level: `pair_movies` would otherwise
    re-parse every name it was given, and `parse_all` has just done it with the
    per-folder scheme hint the movie path has no way to reproduce.

    🚨 IT WAS KEYED ON THE BASENAME AND `movies._entry` CALLS IT WITH THE FULL
    PATH, so every lookup missed -- **0 hits out of 0/2 measured**, and two
    mutants (returning `None`, and not passing the seam at all) survived every
    suite in the project. The Rule 4 optimisation was saving nothing and the
    per-folder scheme hint was being silently discarded, which lets
    `Candidates.is_film` and `pair_movies` disagree about whether a file is a
    film -- the *paired twice, both write* shape `discover.films()` calls a
    correctness bug. Found by an adversarial pass.

    ⚠ The basename was also the wrong KEY even with the right argument:
    measured over a `Season 1`/`Season 2` library, 15 items collapsed to 10
    distinct basenames. Two episodes numbered `01` in different folders would
    have shared one parse.
    """
    by_path = {}
    for item in items:
        by_path[item.path] = item.parsed
    return lambda path: by_path.get(path)


# ---------------------------------------------------------------------------
# what one pair came to
# ---------------------------------------------------------------------------

class Result(object):
    u"""One pair's outcome, and everything a caller needs to act on it.

    🚨 THIS SHAPE IS A COMPATIBILITY PROMISE. `05-interface.md`: *these four
    shapes -- the parser, discovery, the sidecar reader, `align()` -- freeze at
    RUNBOOK 3b*, and `Result` is what carries three of them out to hato and
    surasura. Fields are added, never renamed.

    ⚠ THE NAMES ARE THE SPEC'S, NOT THE INTERNALS'. `Verdict.excess` becomes
    `excess_over_chance` and `Verdict.word` becomes `verdict_word`, because
    that is what `05-interface.md` §*`Result` carries* lists and what hato will
    be written against. Taking an output name from the layer below is one of
    the seam defects the 2026-09-09 adversarial pass found.
    """

    __slots__ = ("video", "subtitle", "outcome", "segments", "match_rate",
                 "excess_over_chance", "raw_excess", "verdict_word", "reason",
                 "holds_throughout", "runtime_check", "cluster_coherence",
                 "dropped_in_gap", "dropped_before_zero", "reference_kind",
                 "reference", "output_path", "superseded", "would_supersede",
                 "lang", "lang_tag",
                 "forced", "write_failed", "episode", "notes")

    def __init__(self, video, subtitle, outcome, reason=u"", segments=(),
                 match_rate=0.0, excess_over_chance=0.0, raw_excess=0.0,
                 verdict_word=None, holds_throughout=True,
                 runtime_check=u"absent", cluster_coherence=None,
                 dropped_in_gap=0, dropped_before_zero=0,
                 reference_kind=TEXT_TRACK, reference=u"", output_path=None,
                 superseded=(), would_supersede=(), lang=None,
                 lang_tag=u"", forced=False,
                 write_failed=False, episode=None, notes=()):
        if outcome not in OUTCOMES:
            raise ValueError(
                "outcome %r is not one of %s (03-permissions.md). There is no "
                "fourth outcome and no silent success."
                % (outcome, u", ".join(sorted(OUTCOMES))))
        # 🚨 The same two invariants `Verdict` enforces, enforced again here --
        # and that is not belt-and-braces. `Result` has a public constructor
        # that hato and the CLI both call, so a Result can exist that no
        # `Verdict` ever produced.
        if outcome != CONFIDENT and not (reason or u"").strip():
            raise ValueError(
                "a %s result was built with no reason. '03-permissions.md' "
                "§hand-back: every refusal states what was measured, why it "
                "fell short, and what would change it." % outcome)
        if outcome != CONFIDENT and verdict_word is not None:
            raise ValueError(
                "a %s result was built carrying the confidence word %r. "
                "LEDGER.md §Interface records a GUI painting a run green "
                "because \"11 confident, 1 refused\" contains `confident`."
                % (outcome, verdict_word))
        # 🚨 AND THE VOCABULARY IS CLOSED. `verdict.py` enforces that the four
        # words stay mutually non-substring and `05-interface.md` rules what
        # they are -- but `Result` has a public constructor that hato and the
        # CLI both call, so `Result(CONFIDENT, verdict_word="REFUSED")` was
        # constructible and re-armed `LEDGER.md` §Interface's defect from the
        # other side. Found by an adversarial pass.
        if verdict_word is not None and verdict_word not in CONFIDENCE_WORDS:
            raise ValueError(
                "%r is not one of this tool's confidence words (%s). "
                "05-interface.md rules the vocabulary and verdict.py keeps "
                "the four mutually non-substring; a Result that invents a "
                "fifth defeats both." % (verdict_word,
                                         u", ".join(sorted(CONFIDENCE_WORDS))))
        # 🚨 A NON-CONFIDENT RESULT MAY NOT CLAIM AN OUTPUT PATH -- it says the
        # tool wrote a file it had just declined to stand behind, which is the
        # single thing `05-interface.md` says this project exists to prevent.
        #
        # ⚠ A FORCED write is reported as REFUSED and it DOES write, so that
        # exception is NAMED -- and it has to be named in the CODE. This guard
        # read `if outcome == ERROR` while the comment above it claimed the
        # exception was `forced`, so `Result(REFUSED, output_path=...)` with
        # `forced=False` was accepted, and the check written for the exception
        # was passing against the hole. Found by an adversarial pass.
        if outcome == REFUSED and output_path and not forced:
            raise ValueError(
                "a REFUSED result was built with output_path=%r and "
                "forced=False. A refusal that wrote a file is a forced write "
                "and must say so; anything else is the confidently wrong file "
                "05-interface.md exists to prevent." % (output_path,))
        if outcome == ERROR and output_path:
            raise ValueError(
                "an ERROR result was built with output_path=%r. ERROR means "
                "the pair was never measured, so there is no offset to have "
                "written -- and --force overrides a refusal, never a missing "
                "measurement (05-interface.md)." % (output_path,))
        # ⚠ A CONFIDENT result with no word is a bare tick, which
        # `05-interface.md` forbids by name: *evidence on every line --
        # `96% match · locked`, never a bare tick.*
        if outcome == CONFIDENT and not verdict_word:
            raise ValueError(
                "a CONFIDENT result was built with no confidence word. "
                "05-interface.md: evidence on every line -- '96% match, "
                "locked', never a bare tick.")
        self.video = video
        self.subtitle = subtitle
        self.outcome = outcome
        self.reason = reason or u""
        self.segments = list(segments)
        self.match_rate = match_rate
        #: ⚠ The internal decision statistic, ZERO when the input was too thin
        #: to mean anything. `05-interface.md`: *never show the raw multiple in
        #: the default output* -- it belongs in `--verbose` and the JSON.
        self.excess_over_chance = excess_over_chance
        #: The same number before the measurability floor zeroes it. Diagnostics
        #: only: it is what reads 5.15x on a one-cue subtitle.
        self.raw_excess = raw_excess
        self.verdict_word = verdict_word
        self.holds_throughout = holds_throughout
        #: "held" | "failed" | "weak" | "absent" -- ⚠ `holds_throughout` is
        #: True when every bucket was too thin to speak, and this is the field
        #: that tells those apart.
        self.runtime_check = runtime_check
        self.cluster_coherence = cluster_coherence
        self.dropped_in_gap = dropped_in_gap
        self.dropped_before_zero = dropped_before_zero
        self.reference_kind = reference_kind
        #: What was aligned against, in words -- the track and its codec, or
        #: the mask. `--verbose` and every bug report want it.
        self.reference = reference
        #: 🚨 Set ONLY when a file was actually written. Not "would write".
        self.output_path = output_path
        #: 🚨 A write was ATTEMPTED and did not land. ⛔ Not the same as a dry
        #: run, and not the same as a refusal — the alignment was good enough,
        #: the file is not there, and the reason says why. Without this a run
        #: whose every write failed was byte-identical in its report to a dry
        #: run: `outcome=CONFIDENT`, `output_path=None`, *"1 would sync"*.
        self.write_failed = bool(write_failed)
        #: ⚠ Paths ACTUALLY moved to the trash, never *would supersede*.
        #: `05-interface.md` calls this *"paths trashed"*, and it was being
        #: copied from the PLAN — so a dry run, and a run whose trash raised,
        #: both reported files as superseded that were still sitting there.
        #: The same defect `output_path` above already had fixed, left in place
        #: next door. Found by an adversarial pass.
        self.superseded = list(superseded)
        #: ⚠ Paths this run WOULD have moved to the trash, populated on a
        #: DRY RUN only. Empty on a run that wrote, where `superseded` above is
        #: the truth and this would merely duplicate it.
        #:
        #: 🚨 IT EXISTS BECAUSE `superseded` CORRECTLY REFUSES TO ANSWER
        #: THIS QUESTION. That field is *paths actually moved*, and a dry run
        #: moves nothing -- so the mode whose entire job is to PREDICT the
        #: destructive action had no channel to report it, and `--dry-run`
        #: printed *"7 would sync"* over a folder where the very next real run
        #: said *"1 subtitle superseded → trash"* and emptied a file out of
        #: the library. `--dry-run`'s own help is *"print every intended
        #: action"*; the one intended action that is not reversible was the one
        #: it left out.
        #:
        #: ⭐ Taken from `report.trashed`, not from `plan.superseded`. The
        #: plan is what dedupe WANTED; `apply_plan` walks the same branches in
        #: dry-run mode and drops the losers it must not touch -- nothing
        #: written for the slot, or the winner writing over itself. Reading the
        #: plan would over-promise a deletion in exactly the cases the trash
        #: rules exist to prevent.
        self.would_supersede = list(would_supersede)
        self.lang = lang
        #: What the file itself said, kept apart from the resolved code --
        #: `05-interface.md`: *`ja-jp` and `.jpn.` are the same language and
        #: must dedupe together, but the output name should preserve what the
        #: user's other tooling expects.*
        self.lang_tag = lang_tag
        self.forced = forced
        #: The episode this pair is about, or None for a film or an unnumbered
        #: file. ⭐ It is here because `05-interface.md`'s ruled output has a
        #: COLUMN for it, and the alternative is every consumer re-parsing the
        #: filename — the CLI did exactly that for one afternoon, which is a
        #: second answer to a question the run has already answered, and with
        #: better evidence: it had the whole folder and the scheme it inferred
        #: from it. ⚠ An int, or None. Never a formatted string; the width of
        #: the column is the caller's decision, not this object's.
        self.episode = episode
        self.notes = list(notes)

    @property
    def match_percent(self):
        u"""The human-readable number. `05-interface.md`: *96% match*."""
        return int(round(self.match_rate * 100.0))

    @property
    def offset(self):
        u"""The first segment's offset, in seconds, or None.

        ⚠ A CUT FILE HAS MORE THAN ONE and this returns the first. Anything
        reporting a cut file reads `segments`; this is the convenience for the
        single-offset case and it is named for what it returns.
        """
        return self.segments[0][1] if self.segments else None

    def __repr__(self):
        return "Result(%s%s, %s <- %s)" % (
            self.outcome, u", " + self.verdict_word if self.verdict_word
            else u"", os.path.basename(self.video or u"?"),
            os.path.basename(self.subtitle or u"?"))


__all__ = ["Candidacy", "Result", "Scan", "scan"]
