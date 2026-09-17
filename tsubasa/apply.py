# -*- coding: utf-8 -*-
u"""
Performing a `DedupePlan`: the retimed file written, the losers trashed.
RUNBOOK step 3a, the write half. Authority: `03-permissions.md` (the field
whitelist and the three outcomes), `05-interface.md` §Naming and dedupe,
`12-alignment.md` §6 (`D9`), `doctrine/robustness` §destructive.

===========================================================================
⛔ THIS IS THE ONLY MODULE IN THE PROJECT THAT CHANGES A USER'S FOLDER.
===========================================================================

Everything upstream decides. `discover` walks, `align` measures, `verdict`
judges, `dedupe` plans -- and none of them can touch a byte. This is where a
decision becomes an edit, so every rule that has been structural elsewhere has
to actually hold here.

    dry_run=True BY DEFAULT      `doctrine/robustness`: a destructive tool is
                                 dry-run by default, and its first dry run is
                                 a design review.
    WRITE FIRST, TRASH SECOND    If the trash fails after a good write the
                                 user has both files. The other order can
                                 leave them with neither.
    NOTHING IS DELETED           `dedupe.trash` moves. This module calls it and
                                 owns no deletion primitive of its own --
                                 asserted from the syntax tree, as there.
    THE WRITE IS ATOMIC          `formats.write_file` goes via a temp file and
                                 `os.replace`. `LEDGER.md` §Delivery: a crash
                                 part-way through an in-place write left a
                                 346-cue file with 0 cues.

---------------------------------------------------------------------------
⭐ `D9` -- THE CUES THAT CANNOT BE RENDERED AT ALL
---------------------------------------------------------------------------

A broadcast subtitle against a streaming video needs a NEGATIVE jump after the
break. Cues timed inside the removed CM block -- sponsor cards, eyecatch
captions -- then map to reference time that no longer exists and would overlap
the next segment's opening cues.

⛔ Ruled 2026-09-08: **drop them, COUNT them, REPORT the count.** They are not
silently discarded and they are not left to overlap; the number reaches the
result line, because a person who sees `3 cues dropped` can go and look, and a
person who sees nothing cannot.
"""
import os
import shutil

from . import dedupe as _dedupe
from . import formats
from .align import mapper_for, removed_spans
from .cues import RewriteRefused, drop_cues


class ApplyReport(object):
    u"""What was done, or what would have been done. ⚠ Read `performed`."""

    __slots__ = ("performed", "written", "trashed", "dropped_in_gap",
                 "dropped_before_zero", "notes", "errors")

    def __init__(self, performed=False):
        self.performed = performed
        #: [(source path, written path)]
        self.written = []
        #: [`dedupe.TrashResult`]
        self.trashed = []
        #: ⭐ `D9`'s count. Reaches the result line; never silent.
        self.dropped_in_gap = 0
        #: Cues ending before t=0 -- the other removal the whitelist permits.
        self.dropped_before_zero = 0
        self.notes = []
        #: 🚨 [(path, reason)]. A per-pair failure NEVER aborts the folder --
        #: `06-edge-cases.md` §7: *per-pair atomicity; completed pairs stay
        #: done*. It is recorded and the run continues.
        self.errors = []

    @property
    def ok(self):
        return not self.errors

    def __repr__(self):
        return "ApplyReport(%s, %d written, %d trashed, %d dropped, %d errors)" % (
            "performed" if self.performed else "dry run", len(self.written),
            len(self.trashed), self.dropped_in_gap, len(self.errors))


def apply_plan(plan, trash_root, out_dir=None, dry_run=True, sender=None,
               force=False):
    u"""Perform one slot's plan. -> `ApplyReport`

    `out_dir`
        where the written file goes. Defaults to the source's own folder.
        ⚠ `05-interface.md`: `--out` **mirrors, never flattens** -- flattening
        collides the moment two shows both have an `ep01`. Mirroring is the
        caller's job because only it knows the library root; this takes the
        directory it is given.

    ⛔ Returns a report even when everything failed. A caller must be able to
    tell *"nothing to do"* from *"everything broke"*, and an exception escaping
    here would abort a whole folder over one unreadable file.
    """
    report = ApplyReport(performed=not dry_run)
    if not plan.writes:
        report.notes.append(
            plan.reason or u"nothing to write for this slot")
        return report

    written_paths = set()
    for candidate, name in plan.writes:
        # 🚨 THE VERDICT IS CHECKED HERE TOO, and that is not belt-and-braces.
        #
        # `dedupe.plan()` gates on `confident`, but `apply_plan` is a public
        # function and this is the module that touches a user's files. Handed a
        # plan carrying a REFUSED candidate it wrote the file with a +99 s
        # offset and no error -- the exact shape `05-interface.md` calls *"the
        # one command capable of producing a confidently wrong file"*, and the
        # one A11 made structurally impossible on its own path.
        #
        # ⚠ `force` mirrors A11 exactly: it overrides a REFUSAL, never an
        # ERROR, because ERROR means unmeasured and there is no offset to stand
        # behind. And a forced write is REPORTED as forced, never as a success.
        outcome = getattr(candidate.verdict, "outcome", None)
        if outcome != u"CONFIDENT":
            if not (force and outcome == u"REFUSED"):
                report.errors.append((
                    candidate.path,
                    u"the verdict is %s, so nothing is written. %s"
                    % (outcome or u"missing",
                       u"--force overrides a refusal, not a missing "
                       u"measurement." if outcome != u"REFUSED"
                       else u"Pass force=True to write it anyway.")))
                continue
            report.notes.append(
                u"%s was WRITTEN UNDER FORCE. The pairing was accepted; the "
                u"alignment was NOT." % os.path.basename(candidate.path))

        target = os.path.join(out_dir or os.path.dirname(candidate.path), name)
        try:
            data, dropped_gap, dropped_zero = _render(candidate)
        except (RewriteRefused, ValueError, IOError, OSError) as exc:
            # ⚠ Recorded, not raised. One bad file must not cost the folder.
            report.errors.append((candidate.path, u"%s" % exc))
            continue

        moved = None
        report.dropped_in_gap += dropped_gap
        report.dropped_before_zero += dropped_zero
        if dropped_gap:
            one = dropped_gap == 1
            report.notes.append(
                u"%d cue%s dropped: %s timed inside a stretch this video does "
                u"not have -- a sponsor card or eyecatch caption from a "
                u"commercial break, which no offset can render"
                % (dropped_gap, u"" if one else u"s",
                   u"it is" if one else u"they are"))
        if dropped_zero:
            one = dropped_zero == 1
            report.notes.append(
                u"%d cue%s dropped: %s before the video starts"
                % (dropped_zero, u"" if one else u"s",
                   u"it ends" if one else u"they end"))

        # 🚨 A FILE ALREADY AT THE TARGET IS SOMEBODY'S, AND `os.replace`
        # DESTROYS IT SILENTLY. A hand-corrected subtitle, a previous run's
        # output, anything created since discovery -- and with `--out` the plan
        # cannot know what is already in the destination, which is exactly the
        # documented case. It is not in `plan.superseded`, so the
        # written-over guard below never sees it. Found by an adversarial pass.
        #
        # ⭐ Overwriting OUR OWN previous output is the intended re-run; what is
        # refused is overwriting a file this plan never accounted for.
        here = os.path.normcase(os.path.abspath(target))
        known = {os.path.normcase(os.path.abspath(c.path))
                 for c, _n in plan.writes}
        known.update(os.path.normcase(os.path.abspath(c.path))
                     for c in plan.superseded)
        if os.path.exists(target) and here not in known:
            report.errors.append((
                candidate.path,
                u"%s already exists and is not one of the files this run "
                u"accounted for, so writing would destroy it. Nothing was "
                u"written. Move or remove it, or choose another --out."
                % target))
            continue

        # 🚨 A SUPERSEDED FILE AT THE TARGET IS TRASHED FIRST, AND THE ORDER
        # INVERTS **HERE ONLY** — with its justification.
        #
        # ⛔ *"Write first, trash second"* exists so that a trash that fails
        # after a good write leaves the user BOTH files. When the target IS the
        # file, that justification is void: a good write leaves them NEITHER,
        # because the write destroyed it. Measured, on a first run with default
        # flags — a user who already had `Show S01E01.ja.srt` and
        # downloaded a better one: cue count outranks name-match, so the new
        # file won and `output_name` named the output the LOSER's own
        # path. `os.replace` obliterated it, the trash loop skipped it as
        # *"written over"*, the report said `1 synced` with
        # `superseded=[]`, and a tree-wide search for the old bytes found
        # NONE.
        #
        # ⭐ The branch below is right about the PATH and was wrong about the
        # BYTES: an in-place retime is the winner writing over ITSELF, which is
        # `target == candidate.path`. Anything else at that path is
        # somebody's file, and `LEDGER-HOT.md` is unconditional — never
        # delete a user's file, trash only. Found by an adversarial pass.
        # ⚠ NOT GATED ON dry_run. _dedupe.trash takes dry_run and reports what
        # it WOULD move, so the plan describes the real behaviour. Gated, the
        # dry run fell through to the old written_paths arm and printed
        # *"was not trashed: the new file was written over it"* -- a design
        # review of a design this module no longer has, promising the exact
        # destruction the branch below exists to prevent.
        # doctrine/robustness: a destructive tool's first dry run IS the
        # design review.
        if here != os.path.normcase(os.path.abspath(candidate.path)):
            doomed = [c for c in plan.superseded
                      if os.path.normcase(os.path.abspath(c.path)) == here]
            if doomed:
                try:
                    moved = _dedupe.trash(doomed[0].path, trash_root,
                                          dry_run=dry_run, sender=sender)
                    report.trashed.append(moved)
                    # ⚠ Only a move that HAPPENED is described as one. Since
                    # 0.1.2 `trash()` can return performed=False having raised
                    # nothing — the system trash refused and the file had
                    # already left its path — and this note used to be added
                    # regardless.
                    if moved.performed or dry_run:
                        report.notes.append(
                            u"%s was moved to the trash before %s was written "
                            u"over it -- they are different files and the "
                            u"write would have destroyed it"
                            % (os.path.basename(doomed[0].path),
                               os.path.basename(candidate.path)))
                    if moved.reason and not dry_run:
                        report.notes.append(moved.reason)
                except Exception as exc:
                    # ⛔ AND IF THE TRASH FAILS, NOTHING IS WRITTEN. Writing now
                    # would destroy the file we have just failed to make
                    # recoverable, which is the whole thing this branch exists
                    # to prevent.
                    report.errors.append((
                        candidate.path,
                        u"%s is already at the target and could not be moved "
                        u"to the trash (%s), so nothing was written -- writing "
                        u"would have destroyed it."
                        % (os.path.basename(doomed[0].path), exc)))
                    continue

        # ⚠ THE WRITE IS INSIDE THE TRY TOO. It sat outside one, so a target
        # occupied by a directory, a read-only file, an open handle or a
        # too-long path raised straight out of `apply_plan` -- discarding the
        # report and abandoning every pair after it, against this function's
        # own promise and `06-edge-cases.md` §7's per-pair atomicity.
        if not dry_run:
            try:
                formats.write_file(target, data)
            except (IOError, OSError) as exc:
                report.errors.append(
                    (candidate.path, u"could not write %s: %s" % (target, exc)))
                # 🚨 PUT IT BACK. If this write was preceded by trashing an
                # occupant to make room, the folder now has NEITHER file --
                # the exact outcome "write first, trash second" exists to
                # prevent, arriving through the branch that had to invert that
                # order. ⛔ And the report said the opposite: the *"nothing was
                # written, so trashing them would leave neither file"* note is
                # emitted further down and was flatly false here.
                # ⚠ Restoring is best-effort and says so. The bytes are in the
                # trash either way, which is what LEDGER-HOT requires; this is
                # about leaving the FOLDER as it was found.
                _restore(moved, report)
                continue
        report.written.append((candidate.path, target))
        written_paths.add(here)

    # 🚨 WRITE FIRST, TRASH SECOND — AND ONLY IF SOMETHING WAS WRITTEN.
    #
    # ⛔ "Write first, trash second" is an ORDER, and it was being read as the
    # whole rule. With every write in the plan failing, the loop below still
    # ran: nothing was written and the surviving candidate went to the trash,
    # leaving the user with **neither file**. That is the exact outcome this
    # module's header says the order exists to prevent — *"if the trash fails
    # after a good write the user has both files"* — arriving through the case
    # where there was no good write at all. Found by an adversarial pass.
    #
    # ⚠ A DRY RUN STILL REPORTS what it would trash: `report.written` is
    # populated there with what it *would* write, so the condition reads the
    # same and the plan is fully described without moving anything.
    if not report.written:
        if plan.superseded:
            report.notes.append(
                u"%d candidate%s NOT trashed: nothing was written for this "
                u"slot, so trashing them would leave neither file"
                % (len(plan.superseded),
                   u"" if len(plan.superseded) == 1 else u"s"))
        return report

    already = set(os.path.normcase(os.path.abspath(t.path))
                  for t in report.trashed)
    for loser in plan.superseded:
        here = os.path.normcase(os.path.abspath(loser.path))
        if here in already:
            # ⭐ Sent to the trash above, before the write that would have
            # destroyed it. Recoverable, and already reported.
            continue
        if here in written_paths:
            # ⛔ The output landed on this exact file -- an in-place retime,
            # the winner writing over ITSELF. Trashing it now would delete the
            # file we just produced and the user would have neither.
            # ⚠ It reaches here only when the loser IS the winner; a DIFFERENT
            # file at the target was trashed above. That distinction was
            # missing and the difference was a destroyed file.
            report.notes.append(
                u"%s was not trashed: the new file was written over it"
                % os.path.basename(loser.path))
            continue
        # ⚠ AND THE TRASH LOOP HAS ONE. `send2trash` raises `OSError(32)` on a
        # file Windows has locked -- and that escaped AFTER a successful write,
        # so the report recording it was thrown away and the remaining losers
        # were never attempted. An outbound side effect must never be able to
        # fail the operation that caused it (`doctrine/robustness`).
        try:
            gone = _dedupe.trash(loser.path, trash_root, dry_run=dry_run,
                                 sender=sender)
            report.trashed.append(gone)
            # ⭐ A fallback is said out loud: which trash a file went to is
            # where the user will look for it.
            if gone.reason and not dry_run:
                report.notes.append(gone.reason)
        except Exception as exc:
            # ⭐ `except Exception` is correct here and the reason is at the
            # site: the sender is third-party and may raise anything. The file
            # stays where it is, which is the safe outcome.
            report.errors.append(
                (loser.path, u"could not move it to the trash: %s. It is "
                             u"still where it was." % exc))
    return report


def _restore(moved, report):
    u"""Undo a trash-first when the write it made room for then failed.

    ⛔ BEST EFFORT, AND IT SAYS SO EITHER WAY. The bytes are in the trash
    whatever happens, which is what LEDGER-HOT.md requires -- never delete,
    trash only. What this is about is leaving the FOLDER as it was found, so a
    failed run is not silently a destructive one.
    """
    if moved is None or not moved.performed or not moved.destination:
        return
    try:
        shutil.move(moved.destination, moved.path)
        report.trashed = [t for t in report.trashed if t is not moved]
        report.notes.append(
            u"%s was put back: the write it was moved aside for did not "
            u"land, so the folder is as it was found"
            % os.path.basename(moved.path))
    except Exception as exc:
        report.notes.append(
            u"⛔ %s was moved to the trash to make room for a write that then "
            u"FAILED, and it could not be put back (%s). It is recoverable "
            u"from %s." % (os.path.basename(moved.path), exc,
                           moved.destination))


def _render(candidate):
    u"""The bytes to write for one candidate. -> (data, in_gap, before_zero)

    ⚠ Reads the file HERE rather than trusting anything carried from the pairing
    stage. `06-edge-cases.md` §7: *the file always wins; the DB is advisory* --
    and between discovery and the write the user may have edited it.
    """
    result = formats.read_file(candidate.path)
    if not result.ok:
        raise ValueError(u"could not re-read the subtitle: %s" % result.reason)

    # 🚨 READ FINE, AND EMPTY. `formats` is explicit that OK-with-zero-cues and
    # ERROR are different outcomes, so a file can arrive here perfectly
    # readable and containing nothing -- and writing it produces an empty
    # subtitle sitting beside the video under the name a player will load.
    #
    # ⭐ It is refused HERE rather than trusted to the verdict upstream. The
    # verdict refuses anything under five cues, but it judged the file as it
    # was at discovery, and `06-edge-cases.md` §7 lists *subtitle edited since
    # last sync* as a real case -- which is the whole reason this function
    # re-reads instead of carrying a parse forward.
    if not result.cues:
        raise ValueError(
            u"the file now parses to zero cues, so there is nothing to write. "
            u"It read cleanly, so this is not a corrupt file -- it is most "
            u"likely one that was edited or emptied since it was measured.")

    segments = list(getattr(candidate.verdict, "segments", None) or [])
    if not segments:
        raise ValueError(
            u"the verdict carries no segments, so there is no offset to "
            u"write. A file is never retimed by a number nobody measured.")

    mapper = mapper_for(segments)
    spans = removed_spans(segments)

    doomed, in_gap, before_zero = [], 0, 0
    for cue in result.cues:
        if any(lo <= cue.start < hi for lo, hi in spans):
            doomed.append(cue)
            in_gap += 1
            continue
        # ⚠ The END, not the start: a cue straddling t=0 is still partly
        # visible and the whitelist only permits removing one that *ends*
        # before zero.
        # ⚠ AND IT IS `mapper(cue.end)`, NOT `cue.end`. The question is where
        # the cue lands AFTER the measured offset is applied; the raw end is
        # positive for every cue in a normal subtitle. `cues.clamp_negative`
        # asked it the raw way, had no callers, and was deleted at 3b -- the
        # note where it stood says why.
        if mapper(cue.end) <= 0.0:
            doomed.append(cue)
            before_zero += 1

    # 🚨 A DROP THAT REMOVES EVERYTHING WRITES A 0-BYTE FILE, and the write is
    # perfectly atomic -- it atomically writes nothing. `LEDGER.md` §Delivery's
    # *346-cue file with 0 cues* arriving through a different door: an
    # in-place retime where every cue fell inside the removed stretch, or a
    # confidently wrong negative offset that put every cue before t=0. It
    # reported `ok=True` with a cheerful note about how many were dropped.
    # Found by an adversarial pass.
    #
    # ⭐ The zero-cue refusal already existed on the INPUT side; this is the
    # same refusal on the OUTPUT side, which is where it was missing.
    survivors = len(result.cues) - len(doomed)
    if survivors <= 0:
        raise ValueError(
            u"every one of the %d cues would be dropped, so the write would "
            u"produce an EMPTY subtitle in place of the user's file. %d fell "
            u"inside a stretch this video does not have and %d ended before "
            u"it starts -- which together means the offset is wrong, not that "
            u"the subtitle is."
            % (len(result.cues), in_gap, before_zero))

    # 🚨 A CUE THAT STRADDLES THE BREAK IS ANCHORED TO ITS **START**.
    #
    # `retime` maps start and end independently, so a line of dialogue running
    # into a commercial break lost the whole jump from its duration and came
    # out INVERTED: `00:03:41,400 --> 00:03:33,175`. tsubasa's own parser flags
    # it on re-read; nothing flagged it on the way out. Found by an adversarial
    # pass on `12-alignment.md` §5's real cut.
    #
    # ⭐ The cue belongs to the moment it STARTS, so both ends take that
    # segment's offset. Duration is preserved and the cue can never invert.
    # ⚠ Its end may then extend past the boundary into the next segment's
    # opening -- which `06-edge-cases.md` §5.1 already calls normal
    # (*"Overlapping cues | REG Normal in ASS. No special handling"*), and it
    # is strictly better than a cue that plays backwards.
    def _whole_cue(cue):
        at_start = mapper(cue.start)
        return at_start, at_start + (cue.end - cue.start)

    text = drop_cues(result, doomed, formatter=formats.formatter_for(result),
                     cue_mapper=_whole_cue)

    from .encoding import encode_back
    # ⭐ THE ORIGINAL CODEC, always. `03-permissions.md` puts the text encoding
    # in the never-change column in red: a Shift-JIS caption decoded with
    # `errors="replace"` had all 346 cues become U+FFFD, and because timestamps
    # are ASCII the tool said CONFIDENT and wrote perfect timing with no
    # readable text.
    return encode_back(text, result.decoded), in_gap, before_zero


__all__ = ["ApplyReport", "apply_plan"]
