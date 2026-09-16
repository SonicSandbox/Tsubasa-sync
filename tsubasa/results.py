# -*- coding: utf-8 -*-
u"""
The results DB. RUNBOOK step 3a-bis. Authority: `02-data-model.md` §*The results
DB*, `06-edge-cases.md` §7.

===========================================================================
⭐ IT ANSWERS ONE QUESTION THE FILENAME CANNOT: *has this already been synced?*
===========================================================================

Sonic ruled **no `.synced` marker in the filename** (`03-permissions.md`), so
the only thing that can answer it is the bytes. Every record here is keyed on
the **content hash of the subtitle**, which is why it survives renaming -- and
renaming is what this tool DOES, so a path-keyed store would miss its own
output on the very next run.

---------------------------------------------------------------------------
⛔ ADVISORY, NEVER AUTHORITATIVE. THE FILE ALWAYS WINS.
---------------------------------------------------------------------------

`06-edge-cases.md` §7 is explicit and it is the whole safety property:

    Results DB says synced, file says otherwise -> 🚨 the file always wins.

A DB that can veto a re-sync is a DB that can make the tool refuse to fix
something it broke. So every question this module answers is asked **of the
files that are actually in front of it this run**: a record is consulted only
when a file on disk hashes to it. There is no path in here that reads a record
and concludes something about a file it has not hashed.

⭐ That single rule is also what makes the store safe to share between
unrelated runs. A record for video X names the OUTPUT it produced; a fresh
library holding an identical copy of X but none of that output cannot match
it, because the output digest is not among the files on offer. Two suites
built from the same fixture bytes therefore cannot skip each other's work --
not by luck, by construction.

---------------------------------------------------------------------------
⚠ WHAT IS RECORDED IS WHAT HAPPENED, NEVER WHAT WAS PLANNED
---------------------------------------------------------------------------

`LEDGER-HOT.md`: *a report composed from the plan is not a report about what
happened*, fixed once for `output_path` and found again next door for
`superseded`. A record is written only from a write that landed -- a dry run
records nothing at all -- because a record is a claim that a file with these
bytes exists, and the next run acts on it.
"""
import io
import json
import os
import time

import hashlib

from .cache import SAMPLE, ContentKey, content_key
from .paths import atomic_write_bytes, cache_root, load_config


def subtitle_key(path):
    u"""The WHOLE file, hashed. -> `ContentKey`

    🚨 NOT `cache.content_key`, AND THE DIFFERENCE IS A RULED PROPERTY.
    That one samples head 64 KB + tail 64 KB + size, which is the entire cost
    model for VIDEOS — a 1.4 GB file must never be read whole, and
    `02-data-model.md` pins it. ⛔ But a retime is length-preserving, so
    above 2 × SAMPLE the middle is never read: measured, a **188 KB** subtitle
    with 61 of its cues moved by +9 s hashed identically, and the run reported
    *already in sync* with **zero container reads** — against
    `06-edge-cases.md` §7, which says the file always wins.

    ⭐ Subtitles are kilobytes. Hash them whole and the digest becomes a real
    witness. Videos keep the sampled key; the two questions were never the
    same question.

    ⚠ AND IT RETIRES A FALSE COMMENT. `Results.get` claimed *"the SIZE is
    the independent witness"*. It is not independent — `content_key`
    hashes the size INTO the digest, so that guard was unreachable for any file
    that exists. With a full hash there is nothing left for it to witness.
    """
    st = os.stat(str(path))
    h = hashlib.sha256()
    with io.open(str(path), "rb") as fh:
        while True:
            chunk = fh.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return ContentKey(h.hexdigest(), st.st_size, st.st_mtime)

#: Bump when the SHAPE of a record changes, or when a change to the tool means
#: last week's answers should be re-measured rather than believed. A record
#: stamped with an older value is ignored, never reinterpreted -- the same rule
#: `cache.py` holds, and here it is also the release valve for *"the aligner
#: got better and yesterday's refusal might not be one any more."*
#: ⚠ 2 since the subtitle digest became a FULL hash (F5). Every record
#: written before that was keyed on head+tail+size, so it names a digest this
#: build will never compute again — stale, re-measured, overwritten. That is
#: exactly what the stamp is for.
RESULTS_VERSION = 2

#: Where records live under the per-user root. ⛔ NEVER beside the media
#: (`02-data-model.md`); `subsync` wrote scratch files next to the subtitles it
#: was aligning, inside a corpus its own README marks do-not-modify.
RESULTS_DIR = u"synced"


def run_shape(rename=True, out_dir=None, keep_all=False, dedupe=True):
    u"""What a run was asked to PRODUCE. -> a comparable dict

    ⭐ Built in one place and called from both ends — the run that records and
    the run that asks — because two descriptions of the same thing drift, and
    the drift here reads as *already in sync*.

    ⚠ `write` is deliberately absent: a dry run records nothing, so it
    can never be the shape of a record. ⚠ `force` too — it is
    explicit-pairs-only and the explicit path never skips.
    """
    return {
        u"rename": bool(rename),
        # ⚠ NORMALISED. The same directory typed two ways is one destination,
        # and a run refusing to skip because the user wrote a trailing slash
        # would be a cache that never hits.
        u"out_dir": (os.path.normcase(os.path.abspath(out_dir))
                     if out_dir else None),
        u"keep_all": bool(keep_all),
        u"dedupe": bool(dedupe),
    }


def _same_file(path):
    u"""The identity two paths share only when they are the same file.

    ⚠ The same normalisation `pipeline._key` uses. Two layers disagreeing
    about whether two strings name one file is how a store counts one subtitle
    as two.
    """
    if not path:
        return None
    return os.path.normcase(os.path.realpath(str(path)))


def _within(small, big):
    u"""Is every digest in `small` in `big` at least as often? -> bool

    ⚠ Written out rather than leaning on `collections.Counter.__le__`,
    which only became a rich comparison in Python 3.10. A version dependency in
    the one predicate that decides whether a folder is finished is not worth
    taking.
    """
    for digest, count in small.items():
        if big.get(digest, 0) < count:
            return False
    return True


def _tally(keys):
    u"""{digest: how many files hold it} for the candidates on disk now."""
    seen = {}
    for key in keys:
        seen[key.digest] = seen.get(key.digest, 0) + 1
    return seen


class Considered(object):
    u"""One file in the slot -- what it was, and whether it survived the run.

    ⭐ THE RECORD CARRIES THE WHOLE SLOT, NOT JUST THE WINNER, and it carries
    it from BOTH SIDES of the work: the candidates the plan was made from, and
    the files still on disk when the run finished. Neither alone can answer
    *"has anything changed?"* -- see `Record.stable`.
    """

    __slots__ = ("digest", "size", "path", "outcome", "survived")

    def __init__(self, digest, size, path, outcome, survived=True):
        self.digest = digest
        self.size = size
        self.path = path
        self.outcome = outcome
        #: ⭐ False when this run superseded the file to the trash. A trashed
        #: candidate is legitimately not on offer next time, so it must not be
        #: part of what the next run is checked against.
        self.survived = bool(survived)

    def as_json(self):
        return {"digest": self.digest, "size": self.size, "path": self.path,
                "outcome": self.outcome, "survived": self.survived}

    @classmethod
    def from_json(cls, d):
        return cls(d["digest"], d["size"], d["path"], d["outcome"],
                   d["survived"])

    def __repr__(self):
        return "Considered(%s..., %s%s)" % (
            self.digest[:8], self.outcome,
            u"" if self.survived else u", trashed")


class Record(object):
    u"""One completed sync: these bytes were written, for that video, then.

    Keyed on `output.digest` -- the content hash of the file this tool WROTE.
    `02-data-model.md`: *keyed on the content hash of the subtitle, so it
    survives renaming.* The output is the file that will still be on disk next
    run, so it is the one worth being able to recognise.
    """

    __slots__ = ("video_digest", "video_size", "video_path", "lang",
                 "outcome", "word", "segments", "dropped_in_gap",
                 "dropped_before_zero", "output_digest", "output_size",
                 "output_path", "source_digest", "source_size", "source_path",
                 "considered", "written_at", "version", "shape")

    def __init__(self, video_digest, video_size, video_path, lang, outcome,
                 word, segments, dropped_in_gap, dropped_before_zero,
                 output_digest, output_size, output_path, source_digest,
                 source_size, source_path, considered, written_at=None,
                 version=RESULTS_VERSION, shape=None):
        self.video_digest = video_digest
        self.video_size = video_size
        self.video_path = video_path
        self.lang = lang
        self.outcome = outcome
        self.word = word
        #: [(start, offset)] -- the offsets applied. `02-data-model.md` names
        #: them as part of what the DB records, and a bug report wants them.
        self.segments = [list(s) for s in segments]
        self.dropped_in_gap = dropped_in_gap
        self.dropped_before_zero = dropped_before_zero
        self.output_digest = output_digest
        self.output_size = output_size
        self.output_path = output_path
        self.source_digest = source_digest
        self.source_size = source_size
        self.source_path = source_path
        self.considered = list(considered)
        #: 🚨 WHAT THE RUN WAS ASKED TO PRODUCE — rename, out_dir, keep_all,
        #: dedupe. A record without it says *this content was synced* and
        #: cannot say *synced INTO WHAT*. Measured: settle a library, then ask
        #: for `--out elsewhere`, and the run reported
        #: `1 already in sync` with **the output directory never
        #: created** — the user asked for files somewhere and got nothing, with
        #: a success-shaped report. Same for `--keep-all` and for
        #: `--no-rename` in either direction.
        #: ⛔ It is compared as a WHOLE. Reasoning about which flags can safely
        #: differ is how the first version had none at all.
        self.shape = dict(shape or {})
        self.written_at = time.time() if written_at is None else written_at
        self.version = version

    # -- the two sets, and why there are two -----------------------------

    def survivors(self):
        u"""The slot's surviving candidates. -> {digest: how many files}

        ⚠ SHARED BY EVERY RECORD OF ONE SLOT. `--keep-all` writes several
        files from one slot and mints one record per file, each carrying the
        same `considered` list — so a caller that SUMS `expected()`
        across them counts every survivor once per kept file. Measured: one
        slot, two kept files, and the shortfall arm fired on four digests that
        were all present. Split out so the summing caller can take these ONCE
        per slot and add only the outputs.
        """
        seen = {}
        for c in self.considered:
            if c.survived and c.digest is not None:
                seen[c.digest] = seen.get(c.digest, 0) + 1
        return seen

    def wrote(self):
        u"""This record's own output, unless it IS one of the survivors.

        -> {digest: 0 or 1}. ⭐ One FILE, counted once, keyed on its path: an
        in-place retime makes the output one of the survivors and adding it
        again made a converged folder expect a digest twice while holding one
        file.
        """
        if self.output_digest is None:
            return {}
        out = _same_file(self.output_path)
        for c in self.considered:
            if c.survived and _same_file(c.path) == out:
                return {}
        return {self.output_digest: 1}

    def expected(self):
        u"""What should still be on disk for this slot. -> {digest: how many}

        The file this run WROTE, plus every candidate that survived it.

        🚨 A COUNT, NOT A SET, AND THE DIFFERENCE IS TWO DEFECTS.
        `05-interface.md`'s ruled property — *one subtitle per (video ×
        language)* — is about FILES. This store is keyed on CONTENT, because
        renaming is what the tool does. Two paths holding one digest are
        therefore **one entry in a set**, and both of these followed:

          * Delete one of two byte-identical subtitles and the run still
            reports *already in sync*: the set does not change.
          * At an offset of ZERO, `apply` writes back the bytes it read, so
            the output hashes to its own source. As a set, expected <= offered
            and run 1 calls itself a fixed point — with the stale original
            still in the folder, for ever. ⛔ The input is the ordinary one: a
            subtitle already correct for that release, which is precisely what
            hato fetches.

        ⭐ Counted, the zero-offset record expects that digest **twice** and was
        offered it **once**, so run 1 is correctly unstable and run 2 does the
        trashing the ruling requires. Found by two adversaries independently.
        """
        seen = dict(self.survivors())
        for digest, count in self.wrote().items():
            seen[digest] = seen.get(digest, 0) + count
        return seen

    def offered(self):
        u"""What the plan was made FROM. -> {digest: how many}"""
        seen = {}
        for c in self.considered:
            if c.digest is not None:
                seen[c.digest] = seen.get(c.digest, 0) + 1
        return seen

    @property
    def stable(self):
        u"""🚨 IS THIS A FIXED POINT, OR JUST THE STATE AFTER ONE RUN?

        =====================================================================
        ⭐ THE FIRST RUN OVER A FOLDER LEAVES WORK UNDONE, AND SAYS SO HERE.
        =====================================================================

        Run 1 sees one candidate -- the release-named original -- writes it out
        under the video's basename, and leaves the original alone, because a
        winner is never superseded. So the folder now holds TWO subtitles, and
        `05-interface.md` rules that it should hold one. Run 2 is what fixes
        that: the canonical file is now a candidate, it wins on rule 5, and the
        stale original goes to the trash.

        ⛔ A store that called run 1's state *settled* would skip run 2 and the
        folder would keep both files FOREVER -- a ruled property defeated by
        the cache meant to make it cheap. Measured exactly that way while this
        was being built: `test_ONE_FOLDER_mode_converges_and_never_trashes_
        its_own_output` went red with the original still sitting there.

        ⭐ THE TEST IS WHETHER THE RUN'S OWN OUTPUT WAS ALREADY SOMETHING IT
        HAD CONSIDERED. Run 1 wrote a file that was not among its candidates,
        so the next run has an input it has never weighed -- not settled. Run 2
        rewrites a file that WAS among its candidates and trashes the rest, so
        nothing new exists -- settled, and the run after it is the cheap one.
        """
        # ⛔ A RECORD THAT WROTE NOTHING IS NOT A FIXED POINT. With
        # `output_digest` None the comparison below was vacuously true, so
        # a doctored or truncated record settled the video for ever and printed
        # a hand-back sentence naming no file at all.
        if not self.output_digest:
            return False
        return _within(self.expected(), self.offered())

    # -- serialisation ---------------------------------------------------

    def as_json(self):
        return {
            "version": self.version,
            "written_at": self.written_at,
            "video": {"digest": self.video_digest, "size": self.video_size,
                      "path": self.video_path},
            "lang": self.lang,
            "outcome": self.outcome,
            "word": self.word,
            "segments": self.segments,
            "dropped_in_gap": self.dropped_in_gap,
            "dropped_before_zero": self.dropped_before_zero,
            "output": {"digest": self.output_digest, "size": self.output_size,
                       "path": self.output_path},
            "source": {"digest": self.source_digest, "size": self.source_size,
                       "path": self.source_path},
            "considered": [c.as_json() for c in self.considered],
            "shape": self.shape,
        }

    @classmethod
    def from_json(cls, d):
        video, output, source = d["video"], d["output"], d["source"]
        return cls(
            video_digest=video["digest"], video_size=video["size"],
            video_path=video["path"], lang=d["lang"], outcome=d["outcome"],
            word=d["word"], segments=d["segments"],
            dropped_in_gap=d["dropped_in_gap"],
            dropped_before_zero=d["dropped_before_zero"],
            output_digest=output["digest"], output_size=output["size"],
            output_path=output["path"], source_digest=source["digest"],
            source_size=source["size"], source_path=source["path"],
            considered=[Considered.from_json(c) for c in d["considered"]],
            written_at=d["written_at"], version=d["version"],
            shape=d.get("shape"))

    def __repr__(self):
        return "Record(%s..., %s, %s)" % (
            self.output_digest[:8], self.outcome,
            os.path.basename(self.output_path or u"?"))


class Settled(object):
    u"""The answer to *"can this video be skipped?"* -- and WHY, either way.

    ⚠ A BOOLEAN WOULD BE A SILENCE. `03-permissions.md` §hand-back: every
    refusal states what was measured and what would change it. A skip is a
    decision not to look at a user's files, so it owes the same sentence -- and
    so does a re-run the user expected to be instant.
    """

    __slots__ = ("skip", "reason", "records", "protected", "video_key",
                 "digests", "answers")

    def __init__(self, skip, reason, records=(), protected=None, video_key=None,
                 digests=None, answers=None):
        self.skip = bool(skip)
        self.reason = reason
        self.records = list(records)
        #: ⭐ {path: ContentKey} for every candidate, hashed BEFORE anything
        #: moved. The recording half needs exactly that -- the set the plan was
        #: made from -- and by then the losers are in the trash and cannot be
        #: hashed at all. Handed back rather than recomputed, because this is
        #: the one read the skip is allowed to cost.
        self.digests = dict(digests or {})
        #: ⭐ The video's `ContentKey`, hashed once and handed back so the
        #: recording half does not pay for it again. Every skip decision costs
        #: one head+tail read per video and that is the entire budget.
        self.video_key = video_key
        #: 🚨 {path: video} for every file a skipped video still OWNS, and it
        #: feeds BOTH of `pipeline._resolve_ownership`'s rules.
        #:
        #: Both are computed from the slots of the run and a skipped video
        #: contributes none. ⛔ It shipped feeding rule 1 only — *never
        #: superseded* — and rule 2, *never written OVER in place*, was left
        #: blind: measured on default flags, a settled video's only subtitle
        #: was retimed for its neighbour, **destroyed rather than trashed**,
        #: in the run that called it already in sync.
        #: ⭐ It maps to the VIDEO rather than being a bare list because the
        #: refusal sentence names who else needs the file, and *"the video
        #: that is already in sync"* is the honest answer.
        self.protected = dict(protected or {})
        #: ⭐ {path: video} for the files this skipped video WROTE — its
        #: answers. ⚠ A STRICT SUBSET of `protected`, and the two exist
        #: separately because the two ownership rules guard different hazards.
        #: Rule 1 asks *may this be TRASHED* and the answer covers everything
        #: the video was offered. Rule 2 asks *may this be WRITTEN OVER while
        #: somebody still has to read it* — and a skipped video reads nothing;
        #: what it needs is that its own answer survives.
        #: ⛔ Conflating them cost a defect in EACH direction: outputs-only let
        #: a neighbour trash a surviving source, and everything-offered let a
        #: settled video veto its live neighbour's own re-sync for ever.
        self.answers = dict(answers or {})

    def __nonzero__(self):          # Python 2 name, kept for symmetry
        return self.skip

    __bool__ = __nonzero__

    def __repr__(self):
        return "Settled(%s, %s)" % (self.skip, self.reason)


class Results(object):
    u"""A keyed, versioned, per-user store of completed syncs.

    ⚠ INJECTED WHEREVER IT IS USED, the same seam shape as
    `dedupe.trash(sender=...)`, `movies.pair_movies(duration_of=...)` and
    `sync(reader=...)`. The real store is the default so it is never *code that
    never runs here*, and a suite hands in its own root so a check can never
    depend on -- or corrupt -- the developer's own history.
    """

    def __init__(self, root=None, version=RESULTS_VERSION, cfg=None):
        if root is None:
            root = os.path.join(str(cache_root(cfg or load_config())),
                                RESULTS_DIR)
        self.root = str(root)
        self.version = version
        self.hits = 0
        self.misses = 0
        self.stale = 0
        self.corrupt = 0
        self.recorded = 0

    # -- layout ----------------------------------------------------------

    def _path(self, digest):
        # Two-level fan-out, the same as `cache.py`: a flat directory of
        # 30,000 entries is slow to enumerate on every platform this ships to.
        #
        # ⚠ AND NO `v%d` IN THE PATH, WHICH IS WHERE THIS DIFFERS FROM
        # `cache.py` ON PURPOSE. Namespacing the directory by version makes an
        # old record simply invisible -- so the version test in `get` below
        # could never fire, and a defensive branch that cannot fire is
        # `07-test-plan.md`'s *code that never runs in this configuration*. It
        # also strands the whole old tree on disk for ever. Keyed on the digest
        # alone, a stale record is FOUND, refused for its version, and
        # overwritten by the run that re-does the work: self-cleaning, and the
        # check that refuses it is a live one with a check of its own.
        return os.path.join(self.root, digest[:2], digest[2:4],
                            digest + u".json")

    # -- reading ---------------------------------------------------------

    def get(self, key):
        u"""The record written for a file with these bytes, or None.

        `key` is a `cache.ContentKey`, so asking this question at all requires
        having hashed a file that is really there. ⛔ There is deliberately no
        `get_by_digest(str)`: the one thing this module may never do is
        conclude something about a file it has not looked at.

        🚨 NEVER RAISES ON A BAD ENTRY. `cache.py` holds the same rule and the
        reason is identical -- a store that can break a run is worse than no
        store. A corrupt record is a MISS, so the work is simply done again.
        """
        p = self._path(key.digest)
        if not os.path.isfile(p):
            self.misses += 1
            return None
        try:
            with io.open(p, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
            record = Record.from_json(raw)
        except Exception:
            # ⭐ `except Exception` on purpose, and the reason goes at the site
            # (`LEDGER-HOT.md`): the record is REGENERABLE by re-running, and
            # enumerating exception types by thinking about them is how
            # `zlib.error` -- which derives straight from `Exception` -- turned
            # a fail-open into a crash in the caller. A truncated file raises
            # ValueError, a doctored one KeyError or TypeError, and a record
            # written by a future build could raise anything at all.
            self.corrupt += 1
            self.misses += 1
            return None

        if record.version != self.version:
            self.stale += 1
            self.misses += 1
            return None
        # 🚨 THE FILE ON DISK ALWAYS WINS -- and since F5 the DIGEST is what
        # enforces it, because a subtitle is now hashed whole.
        #
        # ⚠ THIS BRANCH ONCE CLAIMED TO BE THE MECHANISM AND WAS NOT. It read
        # *"the size is the independent witness"*; the size is hashed INTO the
        # digest, and the digest is the filename, so it could not fire for any
        # file that exists -- an adversary confirmed it misses only on an
        # internally inconsistent record. It is kept for exactly that: a record
        # whose stored size disagrees with its own content is corrupt, and a
        # corrupt record is a miss.
        if record.output_size != key.size:
            self.stale += 1
            self.misses += 1
            return None

        self.hits += 1
        return record

    # -- writing ---------------------------------------------------------

    def record(self, record):
        u"""Store one completed sync. -> the record

        ⛔ Atomic. `paths.atomic_write_bytes` writes a temp file and
        `os.replace`s it, because a half-written record read by the next run is
        exactly the corruption `get` above has to tolerate -- and tolerating it
        costs a re-align nobody asked for.
        """
        data = json.dumps(record.as_json(), ensure_ascii=False).encode("utf-8")
        atomic_write_bytes(self._path(record.output_digest), data)
        self.recorded += 1
        return record

    def forget(self, digest):
        u"""Drop one record. -> True if there was one.

        ⭐ `02-data-model.md` marks this store *disposable*, and a store nobody
        can clear is not. Deleting a RECORD is not deleting a user's file --
        `LEDGER-HOT.md`'s never-delete rule is about the media, and the worst
        this can cost is one re-align.
        """
        try:
            os.remove(self._path(digest))
            return True
        except (OSError, TypeError, AttributeError):
            # ⚠ TypeError TOO. `_path` slices the digest, so `forget(None)`
            # and `forget(123)` raised out of a helper whose entire job is
            # disposal — and `02-data-model.md` marks this store disposable.
            # Nothing to remove and could-not-remove are the same answer here:
            # False.
            return False

    def stats(self):
        total = self.hits + self.misses
        return {"hits": self.hits, "misses": self.misses,
                "stale": self.stale, "corrupt": self.corrupt,
                "recorded": self.recorded,
                "hit_rate": (self.hits / float(total)) if total else 0.0}


# ---------------------------------------------------------------------------
# the question `sync()` asks
# ---------------------------------------------------------------------------

def settled(store, video_path, candidate_paths, shape=None, hashes=None):
    u"""Can this video be skipped entirely? -> `Settled`

    ===========================================================================
    🚨 THE SKIP IS PER VIDEO, NOT PER SLOT, AND THAT IS THE COST MODEL TALKING.
    ===========================================================================

    The expensive thing is the container read -- 0.087 s a file, against 0.049 s
    for an alignment -- and it is paid **once per video**, before any slot
    exists. `06-edge-cases.md` §7 asks for *zero decoding*, so the question has
    to be answerable before the video is opened, which means it is a question
    about the video and everything on offer for it.

    ⚠ The consequence is deliberate and it errs the safe way: a video whose
    Japanese slot is settled but whose English one has a new file is **not**
    skipped. Doing the settled half again costs an alignment; skipping the
    unsettled half would cost the user a subtitle.

    FOUR CONDITIONS, all of them about files that are in front of us now:

      1. ⭐ At least one candidate on disk **is** a recorded output for this
         video. That is `06-edge-cases.md`'s *"the synced file's hash is in the
         DB"*, and it is also the check that the DB and the file agree -- if
         the output was deleted, edited, or was for a different video, nothing
         matches and the work is simply done again.
      2. 🚨 Every one of those records is `stable` -- a FIXED POINT, not
         merely the state after a run. See `Record.stable`: the first run over
         a folder writes a file it had never weighed, and the folder is not
         finished until the run that weighs it has happened.
      3. ⭐ The digests present now are EXACTLY what those records expect. Not
         a subset and not a superset: a missing file is the DB and the disk
         disagreeing, which `06-edge-cases.md` §7 settles in the disk's favour,
         and an extra file might be the better subtitle.
      4. ⛔ Nothing about paths. The store is keyed on content precisely so a
         renamed file is still recognised, and a path test would throw that
         away.
    """
    name = os.path.basename(str(video_path))
    try:
        video_key = content_key(video_path)
    except (IOError, OSError) as exc:
        # ⭐ A video we cannot hash is a video we know nothing about. The
        # measuring path will report what is wrong with it in a sentence; a
        # silent skip would report nothing at all.
        return Settled(False, u"%s could not be read to check whether it had "
                              u"already been synced (%s)" % (name, exc))

    # ⭐ ONE HASH PER FILE PER RUN, NOT ONE PER VIDEO IT IS OFFERED TO.
    # The episode index offers each subtitle to every video sharing its number,
    # which is what it is for — so a file in a two-rip or bare-episode library
    # was hashed once per offer. Since F5 that is a WHOLE-FILE read, and an
    # `.ass` with embedded fonts is routinely 5-30 MB.
    #
    # ⚠ THE CONDITION THAT MAKES THIS SAFE, and it is why the memo is the
    # caller's and not this module's: the discovery loop runs to completion
    # BEFORE any slot is performed, so nothing on disk can change between two
    # lookups within it. A memo that outlived a run would be a cache claiming
    # the file had not changed, which is the one thing this module may not do.
    hashes = {} if hashes is None else hashes
    present = {}
    for path in candidate_paths:
        try:
            # ⭐ SUBTITLES IN FULL, videos sampled — see `subtitle_key`.
            key = hashes.get(str(path))
            present[str(path)] = key if key is not None else subtitle_key(path)
            hashes[str(path)] = present[str(path)]
        except (IOError, OSError):
            # ⭐ A candidate we cannot even hash is a reason to NOT skip. It is
            # unaccountable by definition, and the measuring path reports what
            # is wrong with it far better than a silent skip would.
            # ⛔ NO DIGESTS HANDED BACK. `Settled.digests` is documented as
            # *every candidate, hashed before anything moved*, and population
            # stops at the first failure — so this used to return a PARTIAL
            # dict that the caller stores as `before`, the set the plan was
            # made from. A record built from a partial `before` re-hashes the
            # missing entries AFTER the writes, recording a post-move digest as
            # a plan-time one. An adversary traced the exploit and found it
            # blocked elsewhere; the contract was still a lie.
            return Settled(False, u"%s could not be read to check whether it "
                                  u"had already been synced"
                                  % os.path.basename(str(path)),
                           video_key=video_key)

    by_digest = {}
    for path, key in present.items():
        by_digest.setdefault(key.digest, []).append(path)

    records, wanted = [], []
    for digest, found in by_digest.items():
        try:
            record = store.get(present[found[0]])
        except Exception:
            # 🚨 FAIL OPEN, the same rule as `Results.get`'s own body and
            # for the same reason. `get` tolerates a corrupt ENTRY; this
            # tolerates a broken STORE — an unreadable root, a permission
            # change, an injected double that raises. The honest outcome is to
            # measure the video again, never to abort a run that has not
            # written anything yet.
            record = None
        if record is None:
            continue
        # 🚨 A RECORD FOUND UNDER A CANDIDATE'S HASH IS NOT AUTOMATICALLY THIS
        # VIDEO'S ANSWER. The same subtitle bytes can be the output for one
        # video and merely a considered candidate for its neighbour -- the two
        # rips of one episode Sonic ruled on at 3b. Only a record whose VIDEO
        # is this video says anything about skipping this video.
        if record.video_digest != video_key.digest:
            continue
        # 🚨 A RECORD MADE FOR A DIFFERENT RUN SHAPE SAYS NOTHING ABOUT THIS
        # ONE. It records that this content was synced; it cannot record that
        # it was synced into the place this run is asking for.
        if shape is not None and record.shape != shape:
            wanted.append(record)
            continue
        records.append(record)

    if not records and wanted:
        return Settled(
            False,
            u"%s was synced, but for a different destination than this run is "
            u"asking for — so the work is done again" % name,
            video_key=video_key, digests=present)
    if not records:
        return Settled(False,
                       u"no completed sync is recorded for %s whose output is "
                       u"still on disk" % name,
                       video_key=video_key, digests=present)

    # 🚨 CONDITION 2. An unstable record is the FIRST run's state, and the
    # second run is the one that leaves the folder with a single subtitle in it
    # (`05-interface.md`). Skipping here keeps both files for ever.
    unstable = [r for r in records if not r.stable]
    if unstable:
        return Settled(
            False,
            u"%s was synced, but that run left files it had not weighed "
            u"against each other (%s) — this run settles the slot"
            % (name, u", ".join(sorted(set(
                os.path.basename(r.output_path or u"?") for r in unstable))[:3])),
            video_key=video_key, digests=present)

    # ⭐ SUMMED ACROSS THE VIDEO'S SLOTS, which are disjoint by construction:
    # `_decide_video` groups candidates by language, so no file is in two.
    # ⚠ And if that ever stopped being true the error is an over-count, which
    # reads as a shortfall and sends the run back to do the work — the safe
    # direction.
    # ⭐ ONE SLOT'S SURVIVORS ARE COUNTED ONCE, HOWEVER MANY FILES IT WROTE.
    # ⛔ The first version summed `expected()` across records and the comment
    # said the slots *"are disjoint by construction"* — true of SLOTS, false of
    # RECORDS, and `--keep-all` is the one flag whose whole meaning is
    # several records per slot. It counted every survivor once per kept file,
    # so the shortfall arm fired on digests that were all present and a
    # keep-all folder could never settle at all.
    # ⚠ A slot is (video × language) and every record names its `lang`, so
    # that is the grouping — not the record.
    expected = {}
    by_lang = {}
    for record in records:
        by_lang.setdefault(record.lang, []).append(record)
    for group in by_lang.values():
        shared = {}
        for record in group:
            for digest, count in record.survivors().items():
                shared[digest] = max(shared.get(digest, 0), count)
        for digest, count in shared.items():
            expected[digest] = expected.get(digest, 0) + count
        for record in group:
            for digest, count in record.wrote().items():
                expected[digest] = expected.get(digest, 0) + count

    here = _tally(present[p] for p in present)
    added = sorted(d for d, n in here.items() if n > expected.get(d, 0))
    if added:
        names = sorted(os.path.basename(by_digest[d][0]) for d in added)
        return Settled(
            False,
            u"%d subtitle%s on offer %s not part of any recorded sync for %s "
            u"(%s), so it is measured again"
            % (len(names), u"" if len(names) == 1 else u"s",
               u"is" if len(names) == 1 else u"are", name,
               u", ".join(names[:3])),
            video_key=video_key, digests=present)

    # 🚨 CONDITION 3, THE OTHER HALF, AND IT IS THE SAFETY PROPERTY ITSELF.
    # `06-edge-cases.md` §7: *the DB says synced, the file says otherwise -- the
    # FILE always wins.* A record naming bytes that are no longer anywhere in
    # this video's candidates is a record about a file the user has deleted,
    # edited, or moved out of reach, and the answer to that is to do the work.
    gone = set(d for d, n in expected.items() if here.get(d, 0) < n)
    if gone:
        return Settled(
            False,
            u"the recorded sync for %s names %d file%s that %s not on offer any "
            u"more, so the file on disk wins and it is measured again"
            % (name, len(gone), u"" if len(gone) == 1 else u"s",
               u"is" if len(gone) == 1 else u"are"),
            video_key=video_key, digests=present)

    outputs = set(r.output_digest for r in records)
    kept = sorted(set(p for d in outputs for p in by_digest.get(d, ())))
    return Settled(
        True,
        u"already in sync — %s %s the output of a completed run and nothing "
        u"else on offer has changed"
        % (u", ".join(os.path.basename(p) for p in kept[:3]),
           u"is" if len(kept) == 1 else u"are"),
        records=records,
        # 🚨 EVERY candidate, not just the outputs. A source this run would
        # have superseded is still a file another video's slot must not trash
        # — nor write over in place — and a skipped video has no slot of its
        # own to say either.
        protected=dict((p, video_path) for p in present),
        # ⭐ THE OUTPUT PATH ON THE RECORD, not a digest lookup.
        # ⛔ Two rips of one episode retimed by the same offset produce
        # BYTE-IDENTICAL outputs, so `by_digest[d]` returned both files and
        # every settled video claimed its neighbour's answer as its own —
        # which put rule 2 straight back to refusing the neighbour's re-sync.
        # A record wrote exactly one file and it says which.
        answers=dict((r.output_path, r.video_path) for r in records
                     if r.output_path),
        video_key=video_key, digests=present)


__all__ = ["RESULTS_VERSION", "RESULTS_DIR", "Considered", "Record",
           "Results", "Settled", "settled", "content_key"]
