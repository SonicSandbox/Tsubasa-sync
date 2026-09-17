# -*- coding: utf-8 -*-
u"""
One subtitle per (video x language): which candidate wins, and where the rest
go. RUNBOOK step 3a. Authority: `05-interface.md` §Naming and dedupe,
`LEDGER-HOT.md`, `doctrine/robustness` §destructive.

===========================================================================
⛔ NOTHING HERE DELETES ANYTHING. EVER.
===========================================================================

`LEDGER-HOT.md`, in the never-do-this list: **never delete a user's file --
trash only**, and `05-interface.md`: *"Recoverable in the way the user already
knows. Nothing this tool does may be unrecoverable."*

⭐ SO IT IS STRUCTURAL RATHER THAN REMEMBERED, in the same style A11 used for
the verdict gate:

  1. This module imports no deletion primitive. `os.remove`, `os.unlink`,
     `shutil.rmtree` and `Path.unlink` do not appear in it, and
     `test_dedupe.py` READS THIS FILE and fails if one ever does.
  2. `trash()` is **dry-run by default**. `doctrine/robustness`: *a destructive
     tool is dry-run by default, and its first dry run is a design review.*
  3. The fallback is a **move**, never a remove -- into `.tsubasa-trash/`
     beside nothing (see below), with the original name preserved.

---------------------------------------------------------------------------
⚠ THE RANKING IS A ROBUSTNESS BACKSTOP, NOT A FEATURE
---------------------------------------------------------------------------

Sonic's note, quoted in `05-interface.md`: *"most people won't have multiple
subs of the same show... I just have it here as an extra test to make this
incredibly robust."* **Implement it correctly; do not over-invest.** The order
is the spec's, unchanged:

    1. aligned confidently -- ⛔ A REFUSED CANDIDATE NEVER WINS
    2. not SDH, unless SDH is the only one
    3. higher cue count and wider runtime coverage
    4. fewer segments -- an uncut source is cleaner than a repaired broadcast
    5. tie -> the one already matching the video's name

🚨 RULE 1 IS A GATE, NOT A TIEBREAK, and that distinction is the whole point.
Sorting by it would make the *least bad* refusal win whenever every candidate
was refused -- and writing the best of several files that were all rejected is
exactly the confidently wrong answer `00-INDEX.md` Rule 2 exists to prevent.
When nothing is confident there is **no winner and nothing is written**.
"""
import os
import shutil

from .sidecar import output_name

#: Where the fallback puts things when the OS has no trash.
#:
#: ⛔ NOT beside the media. `LEDGER-HOT.md`: *never write scratch files beside
#: the media* -- `subsync` wrote `_ref_2.ass` and a 500 KB `.npy` next to the
#: subtitles it was aligning, inside a corpus its own README marks
#: do-not-modify. The caller supplies the root; there is no default that could
#: quietly be the media folder.
TRASH_DIR = u".tsubasa-trash"

#: 🚨 Every deletion primitive by ATTRIBUTE NAME, so the suite can assert this
#: module calls none of them. Prose said *never delete*; this is the version
#: that holds -- `doctrine/robustness`: *can this be a script, a gate, a schema
#: constraint or a type? If yes, that is the version that ships.*
#:
#: ⚠ The check reads the module's **AST**, not its text. A text scan fails on
#: this very comment -- the first version did -- and, worse, it can be silenced
#: by rephrasing a docstring rather than by fixing the code. The syntax tree
#: has no comments in it.
DELETION_PRIMITIVES = (
    "remove", "unlink", "rmdir", "removedirs", "rmtree",
)


class Candidate(object):
    u"""One subtitle competing for one (video x language) slot."""

    __slots__ = ("path", "sidecar", "verdict", "cues", "content_end",
                 "speculative")

    def __init__(self, path, sidecar, verdict=None, cues=0, content_end=0.0,
                 speculative=False):
        #: ⛔ OFFERED ON A GUESS ABOUT EPISODE NUMBERING, and therefore never
        #: TRASHED when it loses -- see the note in `plan`. Defaults False, so
        #: every existing caller keeps the old behaviour exactly.
        self.speculative = bool(speculative)
        self.path = path
        self.sidecar = sidecar
        #: The `verdict.Verdict` for this candidate, or None if it was never
        #: aligned. ⚠ None is NOT confident -- an unaligned candidate cannot
        #: win, for the same reason a refused one cannot.
        self.verdict = verdict
        self.cues = cues
        self.content_end = content_end

    @property
    def confident(self):
        return getattr(self.verdict, "outcome", None) == u"CONFIDENT"

    @property
    def segments(self):
        u"""⚠ A candidate with no verdict reports a large segment count rather
        than zero. Zero would sort it FIRST under rule 4 -- *fewer segments is
        better* -- so an unmeasured file would beat a measured one on a
        tiebreak it never earned. A missing value is not a good value."""
        segments = getattr(self.verdict, "segments", None)
        return len(segments) if segments else 10 ** 6

    def matches_video_name(self, video_stem):
        u"""Rule 5. ⚠ Folded, because the slot is folded -- see `sidecar`."""
        from .sidecar import _fold
        return _fold(self.sidecar.stem) == _fold(video_stem)

    def __repr__(self):
        return "Candidate(%r, %s, %d cues)" % (
            os.path.basename(self.path),
            getattr(self.verdict, "outcome", u"unaligned"), self.cues)


class DedupePlan(object):
    u"""What would happen to one slot. ⚠ A PLAN. It has performed nothing."""

    __slots__ = ("video_stem", "lang", "winner", "writes", "superseded",
                 "notes", "reason")

    def __init__(self, video_stem, lang, winner=None, writes=(),
                 superseded=(), notes=(), reason=u""):
        self.video_stem = video_stem
        self.lang = lang
        self.winner = winner
        #: [(candidate, output filename)] -- what to write, in order.
        self.writes = list(writes)
        #: Candidates that lose the slot and go to trash.
        self.superseded = list(superseded)
        self.notes = list(notes)
        #: 🚨 Never empty when there is no winner. Same contract as a verdict:
        #: `03-permissions.md` §hand-back -- a silent nothing reads as success.
        self.reason = reason

    @property
    def writes_anything(self):
        return bool(self.writes)

    def __repr__(self):
        return "DedupePlan(%s, %d write%s, %d superseded)" % (
            self.lang, len(self.writes), "" if len(self.writes) == 1 else "s",
            len(self.superseded))


def rank(candidates, video_stem=u""):
    u"""The spec's five rules, best first. -> list[Candidate]

    ⛔ RANKING ONLY. It does not apply rule 1's GATE -- `plan()` does, because
    *"a refused candidate never wins"* is a different statement from *"a
    refused candidate sorts lower"*, and collapsing them is how the best of
    several rejected files gets written.
    """
    def key(c):
        return (
            0 if c.confident else 1,              # 1, as a sort (see plan())
            1 if c.sidecar.hearing_impaired else 0,   # 2
            # 🚨 RULE 5 SITS ABOVE RULE 3. RULED BY SONIC 2026-09-09, and it is
            # a reordering of the spec's own list, recorded here and in
            # `05-interface.md`.
            #
            # Rule 3 is *higher cue count and wider runtime coverage*, which is
            # a **proxy for completeness** — and it fails in exactly the case
            # this tool creates: a subtitle we retimed by a NEGATIVE offset
            # ends earlier than its own source, and one we applied `D9` or the
            # before-zero drop to has fewer cues. So a correct output ranked
            # BELOW the stale file it came from, forever, and every run
            # re-did the work and marked its own previous output superseded.
            #
            # ⭐ Sonic: *"cue count is a proxy for completeness that fails
            # exactly when we have deliberately dropped cues. Rule 3 was
            # written to choose between INDEPENDENT SOURCES; it should never
            # rank a derived output against its own source."* Rule 5 —
            # *already matching the video's name* — is the one signal that
            # identifies our own previous output, so it decides first.
            #
            # ⚠ AND IT IS A SYMPTOM FIX. *"Every run re-does the work"* is the
            # results DB's job — `02-data-model.md` lists it as one of four
            # stores and no runbook step built it. RUNBOOK 3a-bis now does.
            #
            # 🚨 IT IS PROMOTED ABOVE `content_end` AND **NOT** ABOVE `cues`,
            # and that split is measured rather than chosen. Promoted above
            # both, a name-matched **10-cue** file beat a **900-cue** one —
            # `test_the_LANGUAGE_comes_from_the_winner_not_from_the_input_order`
            # went red at once, which is rule 3 doing exactly the job it was
            # written for.
            #
            # ⭐ Rule 3 is TWO comparisons and only one of them is broken here.
            # A derived output has the **same cue count** as its source
            # (an uncut retime drops nothing) and a **lower `content_end`**,
            # because every cue moved earlier by the offset. So `cues` still
            # separates genuinely different sources, and `content_end` — which
            # a negative offset lowers on every single sync — no longer
            # outranks *already matching the video's name*.
            # ⚠ Residual, named: a retime that DID drop cues (`D9`, or the
            # before-zero drop) is still a cue or two short of its source and
            # still loses. That is the results DB's case, not the ranking's.
            -_finite(c.cues),                         # 3a — completeness
            0 if c.matches_video_name(video_stem) else 1,   # 5
            -_finite(c.content_end),                  # 3b — coverage
            _finite(c.segments, big=True),            # 4
            c.path,                               # ⚠ total order -- see below
        )
    # ⚠ THE PATH IS A TIEBREAK OF LAST RESORT, and it is here on purpose:
    # without it, two identical candidates order by whatever the filesystem
    # listed first, so the same folder produces a different winner on two
    # machines and the results DB disagrees with itself. `LEDGER.md` §Harness
    # records the general shape -- an instrument that is not deterministic
    # reads as a defect somewhere else entirely.
    return sorted(candidates, key=key)


def _finite(value, big=False):
    u"""A sortable number. NaN and infinities become the WORST value.

    🚨 NaN DESTROYS A TOTAL ORDER SILENTLY. Every comparison with NaN is False,
    so `sorted()` degrades to input order and the `c.path` tiebreak below never
    runs — the same three candidates returned three different winners depending
    on how they were passed in, and `plan()` trashed whichever lost. Found by
    an adversarial pass; the docstring under the tiebreak promised exactly the
    guarantee NaN was breaking.

    ⭐ Not merely made deterministic: a non-finite measurement is a MISSING
    measurement, and a missing value must never win a tiebreak it did not earn
    (the same argument `Candidate.segments` already makes).
    """
    try:
        number = float(value)
    except (TypeError, ValueError):
        return float(10 ** 6) if big else 0.0
    if number != number or number in (float("inf"), float("-inf")):
        return float(10 ** 6) if big else 0.0
    return number


def plan(video_stem, candidates, lang=None, keep_all=False, ext=None):
    u"""Decide one slot. -> `DedupePlan`. ⛔ Performs nothing.

    `keep_all` writes **every** candidate as `<video>.<lang>.<tag>.<ext>` and
    trashes nothing (`05-interface.md`).
    """
    candidates = list(candidates)
    if not candidates:
        return DedupePlan(video_stem, lang, reason=u"no candidates for this slot")

    ordered = rank(candidates, video_stem)
    confident = [c for c in ordered if c.confident]
    # 🚨 THE LANGUAGE COMES FROM THE WINNER, NOT FROM `candidates[0]`.
    #
    # Taking it from the input list's first element made the output name depend
    # on ARGUMENT ORDER: a Japanese winner beside an untagged 10-cue file was
    # written as `Show - 01.ass` — **no language tag at all** — and reversing
    # the list gave `Show - 01.ja.srt`. Both trashed the loser.
    #
    # ⛔ And the untagged form is precisely the subliminal defect `sidecar.py`
    # exists to fix, produced by this module: a correctly-aligned Japanese
    # subtitle reads back as *"no subtitle present"* and is re-fetched forever.
    # Found by an adversarial pass.
    lang = lang or (confident[0].sidecar.lang if confident
                    else ordered[0].sidecar.lang)

    # ⛔ RULE 1, AS A GATE. Nothing is written and nothing is trashed.
    if not confident:
        return DedupePlan(
            video_stem, lang, superseded=[], notes=[],
            reason=(u"none of the %d candidate%s for %s aligned confidently, "
                    u"so there is nothing to choose between -- every one is "
                    u"left exactly where it is, with its own reason. ⛔ The "
                    u"best of several refused files is still a refused file."
                    % (len(ordered), u"" if len(ordered) == 1 else u"s", lang)))

    if keep_all:
        # ⭐ Every candidate is written under a distinguishing tag, and
        # NOTHING is superseded. `05-interface.md`: *writes every candidate as
        # `<video>.<lang>.<tag>.<ext>` and trashes nothing.*
        writes, notes = [], []
        used, taken = set(), set()
        for c in confident:
            name, more = output_name(
                video_stem, lang, ext or c.sidecar.ext,
                flags=c.sidecar.flags,
                tag=_distinguishing_tag(c, used, video_stem))
            # 🚨 A COLLISION HERE IS DATA LOSS, so it is checked rather than
            # trusted: two writes to one path means the second overwrites the
            # first and `--keep-all` has kept one. The tag derivation is meant
            # to prevent it; this is what proves it did.
            if name in taken:
                raise ValueError(
                    "--keep-all produced the name %r twice, for %r and an "
                    "earlier candidate. Writing it would destroy the file it "
                    "was asked to keep." % (name, c.path))
            taken.add(name)
            writes.append((c, name))
            notes.extend(more)
        # ⚠ `--keep-all` SAYS WHAT IT IGNORED. It relaxes the dedupe, never the
        # verdict -- so a refused or unaligned candidate is not written, and
        # silence about that reads as *"everything was kept"*, which is the
        # one thing the flag's name promises. `DedupePlan.reason`'s own
        # contract: a silent nothing reads as success.
        ignored = [c for c in ordered if not c.confident]
        if ignored:
            notes.append(
                u"%d of the %d candidates were not written because they did "
                u"not align confidently -- --keep-all keeps every ACCEPTED "
                u"subtitle, and it does not relax the verdict: %s"
                % (len(ignored), len(ordered),
                   u", ".join(os.path.basename(c.path) for c in ignored[:4])))
        return DedupePlan(video_stem, lang, winner=confident[0], writes=writes,
                          superseded=[], notes=notes)

    winner = confident[0]
    name, notes = output_name(video_stem, lang, ext or winner.sidecar.ext,
                              flags=winner.sidecar.flags)
    # ⚠ EVERY other candidate is superseded, including the ones that were
    # never aligned -- they are competing for a slot that now has an answer.
    #
    # ⛔ EXCEPT A SPECULATIVE ONE, AND THIS IS THE GUARD THE WHOLE
    # ABSOLUTE-NUMBERING FALLBACK RESTS ON.
    #
    # The sentence above is true of a candidate that CLAIMED this slot by
    # name. A speculative candidate claimed nothing: it was offered on a guess
    # that one of the two filenames counts episodes from the start of the
    # series rather than the season (`discover.Candidates._absolute_fallback`),
    # and the losers of that guess are, in the case that prompted it,
    # **subtitles for episodes the user has no video for yet.**
    #
    # 🚨 Without this line, offering `E17`/`E18`/`E22` to a video that is
    # season-2 episode 10 and letting `E22` win sends the other two to the
    # trash. That is `LEDGER-HOT.md`'s *A SLOT CANNOT DECIDE WHAT TO THROW
    # AWAY -- ONLY THE RUN CAN* arriving through a door the 3b cross-slot
    # rules do not cover, because no slot WRITES those files and so nothing
    # protects them.
    superseded = [c for c in ordered
                  if c is not winner and not c.speculative]
    kept = [c for c in ordered
            if c is not winner and c.speculative]
    if kept:
        # ⛔ NEVER SILENT. A file left alone for a reason the user cannot see
        # reads as a file the tool forgot about.
        notes.append(
            u"%d subtitle%s offered only because the episode numbers might be "
            u"counted differently, and %s not chosen -- left exactly where "
            u"%s: %s"
            % (len(kept), u"" if len(kept) == 1 else u"s",
               u"was" if len(kept) == 1 else u"were",
               u"it is" if len(kept) == 1 else u"they are",
               u", ".join(os.path.basename(c.path) for c in kept[:4])))
    return DedupePlan(video_stem, lang, winner=winner, writes=[(winner, name)],
                      superseded=superseded, notes=notes)


def _distinguishing_tag(candidate, used, video_stem=u""):
    u"""A `--keep-all` tag that tells two candidates apart in the filename.

    ⭐ It is the part of the candidate's own stem that the VIDEO's stem does
    not account for -- which for the real case is the release group:

        [Erai-raws] Show - 01.ja.ass   ->  Erai-raws
        [SubsPlease] Show - 01.ja.ass  ->  SubsPlease

    ⚠ Never a counter. `1` and `2` tell the user nothing about which is which,
    and they change when the folder changes -- so the same two files get
    different names on a second run.

    ⚠ AND NEVER THE LANGUAGE. The first version of this took everything after
    the video stem in the FILENAME, which is `.ja`, so both candidates were
    tagged with the language they already share and one fell through to the
    digest. The stem is the right input; the filename is not.
    """
    from .sidecar import _fold
    stem = candidate.sidecar.stem
    folded_video = _fold(video_stem)
    # ⭐ The candidate already named after the video keeps the plain name. It
    # is the one rule 5 prefers, so handing IT the digest -- which is what
    # happened before this line existed -- puts the ugliest name on the most
    # likely file.
    if folded_video and _fold(stem) == folded_video:
        # ⚠ REGISTERED, even though it returns no tag. It did not, so a second
        # candidate with the same basename in a different folder took the same
        # branch, produced the same plain name, and `plan()` raised -- the
        # collision-avoidance mechanism was bypassed for exactly the branch
        # that needs it most. Found by an adversarial pass.
        if u"" in used:
            return _digest(candidate)
        used.add(u"")
        return None
    tag = stem
    # 🚨 THE INDEX MUST COME FROM THE STRING IT IS USED ON. `_fold` is NFKC, and
    # NFKC CHANGES LENGTH -- `Ⅷ` becomes `VIII`, `№` becomes `No`. Locating the
    # video name in the folded text and then slicing the ORIGINAL by that index
    # cut in the wrong place: `[Ⅷ]Show - 01` produced the tag `ⅧSho01`, which
    # contains a fragment of the video's own name. Found by an adversarial pass;
    # every keep-all fixture was ASCII.
    #
    # ⭐ Fold both, cut the folded one. The tag loses the user's original
    # casing on a non-ASCII stem, which is a far smaller cost than a tag built
    # from a mis-sliced name -- and it is stated rather than silent.
    folded_stem = _fold(stem)
    if folded_video and folded_video in folded_stem:
        at = folded_stem.index(folded_video)
        tag = folded_stem[:at] + folded_stem[at + len(folded_video):]
    tag = u"".join(ch for ch in tag if ch.isalnum() or ch in u"-_")[:24]
    if not tag or tag.lower() in used:
        tag = _digest(candidate)
    used.add(tag.lower())
    return tag


def _digest(candidate):
    u"""A stable fallback tag. ⚠ Never `hash()` -- Python randomises it per
    process, so the same folder would produce different filenames on two runs:
    the non-determinism the sort tiebreak exists to avoid, arriving through a
    different door."""
    import hashlib
    return hashlib.sha1(candidate.path.encode("utf-8")).hexdigest()[:8]


# ---------------------------------------------------------------------------
# the trash -- a MOVE, never a remove
# ---------------------------------------------------------------------------

class TrashResult(object):
    u"""What `trash()` did, or would have done."""

    __slots__ = ("path", "destination", "method", "performed", "reason")

    def __init__(self, path, destination=None, method=u"", performed=False,
                 reason=u""):
        self.path = path
        self.destination = destination
        #: "os" (the platform's own trash) or "local" (`.tsubasa-trash/`).
        self.method = method
        self.performed = performed
        self.reason = reason

    def __repr__(self):
        return "TrashResult(%r, %s, %s)" % (
            os.path.basename(self.path), self.method,
            "performed" if self.performed else "dry run")


def trash(path, trash_root, dry_run=True, sender=None):
    u"""Send one file to the trash. -> `TrashResult`

    ⭐ `dry_run=True` BY DEFAULT. `doctrine/robustness`: *a destructive tool is
    dry-run by default, and its first dry run is a design review* -- the first
    dry run of a file-deleting sweeper printed two live user files and a
    fixture, and exposed a query written from memory.

    `sender`
        the OS-trash callable, injected. ⛔ A SEAM, not a convenience:
        `send2trash` is **not installed on the build machine**, so without this
        the OS path would be *code that never runs in the local
        configuration* -- which `07-test-plan.md` forbids by name. The suite
        drives both arms; `TSUBASA_NO_OS_TRASH=1` forces the fallback the way
        `TSUBASA_NO_NATIVE_DEMUX=1` forces the ffmpeg reader.

    ⚠ The local fallback is a MOVE. `shutil.move` is imported for that and for
    nothing else -- `shutil.rmtree` is not imported and must never be.
    """
    if not os.path.exists(path):
        return TrashResult(path, reason=u"already gone: %s" % path)

    # 🚨 A FILE, NEVER A DIRECTORY. `shutil.move` falls back to
    # copytree + **`shutil.rmtree`** when the destination is on another
    # volume — which is the ordinary case here, media on a NAS and the trash on
    # the system drive. An adversarial pass forced `EXDEV` and recorded
    # `rmtree` on a user's season folder. This module's own docstring claims
    # `rmtree` *"is not imported and must never be"*; it was reachable one call
    # deeper, and the AST check could not see that because it scans this file
    # only.
    #
    # ⛔ For a plain FILE the cross-device path is copy2 + unlink, which IS a
    # move and is correct. Restricting the input to files is what makes the
    # claim true rather than nearly true.
    if not os.path.isfile(path):
        return TrashResult(
            path, reason=u"refused: %s is not a file. Only a file is ever "
                         u"trashed -- a cross-device move of a DIRECTORY "
                         u"deletes it recursively, and nothing this tool does "
                         u"may be unrecoverable." % path)

    refused = u""
    sender = sender if sender is not None else _os_trash()
    if sender is not None and not os.environ.get("TSUBASA_NO_OS_TRASH"):
        if dry_run:
            return TrashResult(path, method=u"os", performed=False,
                               reason=u"would go to the system trash")
        # =================================================================
        # ⭐ A REFUSING SYSTEM TRASH FALLS BACK TO THE LOCAL ONE — 0.1.2
        # =================================================================
        # The system trash refuses real files: one Windows has locked
        # (`OSError(32)`), one on a network share or a drive with no recycle
        # bin, one in a sandbox. This let the exception out, and `apply.py`
        # caught it at both call sites — so nothing crashed, but the operation
        # stopped half-done: a superseded subtitle stayed beside its
        # replacement, or a write was abandoned because the file in its way
        # could not be moved. ⛔ The local `.tsubasa-trash/` is exactly as
        # recoverable, and it exists for when the system trash is not there;
        # refusing is that case arriving at runtime rather than at install.
        #
        # ⭐ `except Exception` is correct and the reason is at the site: the
        # sender is third-party and may raise anything. What is caught is
        # never swallowed — it rides out on `reason`, and `apply.py` puts it
        # in front of the person.
        try:
            sender(path)
        except Exception as exc:                    # noqa: BLE001 — reported
            refused = u"the system trash refused %s (%s: %s)" % (
                os.path.basename(path), type(exc).__name__, exc)
            if not os.path.exists(path):
                # ⚠ It raised AND the file left its path, so where it went is
                # not ours to know. Nothing more is moved, and nothing is
                # claimed: performed=False, and the sentence says why.
                return TrashResult(
                    path, method=u"os", performed=False,
                    reason=u"%s, and the file is no longer at its path, so "
                           u"nothing more was done" % refused)
        else:
            return TrashResult(path, method=u"os", performed=True)

    destination = _local_slot(path, trash_root)
    if dry_run:
        return TrashResult(path, destination, u"local", False,
                           u"would move to %s" % destination)
    parent = os.path.dirname(destination)
    if not os.path.isdir(parent):
        os.makedirs(parent)
    shutil.move(path, destination)
    return TrashResult(path, destination, u"local", True,
                       (u"%s, so it was moved to %s instead"
                        % (refused, destination)) if refused else u"")


def _os_trash():
    u"""`send2trash`, if this machine has it. -> callable or None.

    ⚠ Fail OPEN, deliberately, and the reason is written at the site
    (`doctrine/robustness`: *an undocumented fail-open is indistinguishable
    from a bug*): a missing optional dependency must degrade to the local
    trash, never refuse to tidy up. The user still gets a recoverable file.
    """
    try:
        from send2trash import send2trash as _send
    except Exception:
        return None
    return _send


def _local_slot(path, trash_root):
    u"""Where `path` goes inside `trash_root`, without colliding.

    ⚠ Keeps the original NAME. A trash whose contents are `1`, `2`, `3` is not
    *"recoverable in the way the user already knows"*.
    """
    name = os.path.basename(path)
    stem, ext = os.path.splitext(name)
    candidate = os.path.join(trash_root, name)
    n = 2
    while os.path.exists(candidate):
        candidate = os.path.join(trash_root, u"%s (%d)%s" % (stem, n, ext))
        n += 1
    return candidate


__all__ = [
    "TRASH_DIR", "DELETION_PRIMITIVES",
    "Candidate", "DedupePlan", "TrashResult",
    "rank", "plan", "trash",
]
