# -*- coding: utf-8 -*-
u"""
The results DB -- *has this already been synced?* RUNBOOK step 3a-bis.
Authority: `02-data-model.md` §*The results DB*, `06-edge-cases.md` §7.

===========================================================================
🚨 THE THREE CLAIMS THAT CARRY THIS FILE
===========================================================================

  1. **A re-run over an unchanged folder opens nothing.** `06-edge-cases.md`
     §7: *hash-and-skip, ≤ 1 s for 24 episodes, zero decoding.* ⭐ Asserted by
     COUNTING CONTAINER READS through an injected reader that wraps the real
     one -- never by timing alone, because a machine under load makes a
     wall-clock check flaky and a fast machine makes it vacuous. The second is
     timed too, but the read count is the claim.
  2. **The file always wins.** `06-edge-cases.md` §7: *DB says synced, file
     says otherwise -- the file wins.* ⭐ Asserted from BOTH sides: an edited
     output and a deleted one, each re-measured rather than believed.
  3. ⛔ **A skip never costs a user a file.** The store's whole risk is that
     it makes a video invisible to the run, and `_resolve_ownership` decides
     what gets trashed from the videos it can SEE. ⭐ Asserted twice: on the
     guard itself, and on the library shape that reaches it -- two rips of one
     episode, one of them re-encoded, so one is skipped while its twin is
     re-measured and supersedes everything that lost.
     ⚠ NOT on two shows with bare episode numbers, though that is the 3b
     defect this inherits. There, each video is offered BOTH files, so a new
     neighbour makes both candidate sets change and NEITHER video settles --
     the hazard cannot arise. Written that way first and it proved nothing.

⚠ THE STORE IS INJECTED EVERYWHERE, the same seam as `sync(reader=...)` and
`dedupe.trash(sender=...)`. `conftest.py` also points `TSUBASA_CACHE` at a
throwaway directory for the whole session, so a check that forgets cannot
reach the developer's real history.
"""
import io
import os
import shutil
import sys
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tsubasa import api as API                                # noqa: E402
from tsubasa import container as CONTAINER                    # noqa: E402
from tsubasa import pipeline as PIPE                          # noqa: E402
from tsubasa import results as R                              # noqa: E402
from tsubasa.cache import content_key                         # noqa: E402
from tsubasa.verdict import CONFIDENT                         # noqa: E402

# ⭐ REUSED, NOT REBUILT. `doctrine/tooling` §anti-rederivation. `test_pipeline`
# already owns the synthetic episode shape and every one of its numbers is a
# floor in the code -- a second copy would drift from the aligner it exercises.
from test_pipeline import (                                   # noqa: E402
    CUE_STARTS, MKV_CUES, RUNTIME, _shifted, _srt, _tree, _write, _write_mkv,
)


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def store(tmp_path):
    return R.Results(root=str(tmp_path / "db"))


class CountingReader(object):
    u"""The REAL container reader, with a turnstile on it.

    🚨 THIS IS THE INSTRUMENT FOR CLAIM 1 and it wraps the real reader rather
    than replacing it. `07-test-plan.md` forbids code that never runs in the
    local configuration, and a fake reader would also make *"zero decoding"* a
    statement about the fake. Every call is a real Matroska Cues-indexed read.
    """

    def __init__(self):
        self.paths = []

    def __call__(self, path):
        self.paths.append(path)
        return CONTAINER.read(path, timing=True)

    @property
    def count(self):
        return len(self.paths)


def one_episode(folder, stem=u"Show S01E01", delay=2.0, sub_name=None,
                variant=None):
    u"""A real MKV with a real subtitle track, and a late subtitle beside it.

    🚨 `variant` MAKES THE EPISODE'S BYTES ITS OWN, and a whole-folder check
    is worthless without it. Built with 24 identical copies first: every video
    hashed the same, every subtitle hashed the same, and the store held **ONE
    record for twenty-four episodes** -- so the skip was matching each episode
    against a record made for a different one, and a check keyed on the wrong
    thing entirely would have passed. Found by the probe, not by the suite.

    ⭐ The two knobs are chosen so NOTHING ELSE MOVES. The subtitle's cue TEXT
    carries the episode number, and `per_cluster` re-frames the Matroska blocks
    without touching a single timestamp -- so every episode still aligns to the
    same offset and the alignment is not what is under test here.
    """
    folder = str(folder)
    if not os.path.isdir(folder):
        os.makedirs(folder)
    video = os.path.join(folder, stem + u".mkv")
    _write_mkv(video, MKV_CUES, duration_s=RUNTIME,
               per_cluster=4 if variant is None else 3 + (variant % 3))
    text = u"line" if variant is None else u"ep%02d line" % variant
    sub = _write(os.path.join(folder, sub_name or (u"[Grp] %s.ja.srt" % stem)),
                 _srt([t + delay for t in CUE_STARTS], text=text))
    return video, sub


def settle(folder, store, trash, runs=2, **kw):
    u"""Run `sync` until the folder is a fixed point. -> the last `SyncReport`

    ⭐ TWO RUNS, NOT ONE, AND THE REASON IS `Record.stable`. Run 1 writes a file
    it had never weighed against anything, so the folder holds two subtitles
    and `05-interface.md` rules that it should hold one; run 2 is what trashes
    the stale original. Only after that is *"nothing changed"* true.

    🚨 AND NOT THREE, WHICH IS WHAT IT WAS AND WHAT MADE FOUR MUTANTS SURVIVE.
    A third run re-records the slot from a folder that has ALREADY converged,
    so a defect in what run 2 wrote down is simply overwritten by a run with
    nothing left to get wrong. `probe_adj29`: *expected() counts a trashed
    candidate as still present* changed `settled()` from True to False when
    asked directly, and could not be seen through a fixture that ran the system
    one more time than the property needs.
    ⭐ **A fixture that iterates more than the claim requires lets the system
    route around the defect.** Two is the number that converges; two is the
    number to use.
    """
    report = None
    for _ in range(runs):
        report = PIPE.sync(API.scan(str(folder)), write=True,
                           trash_root=trash, results=store, **kw)
    return report


# ---------------------------------------------------------------------------
# ⭐ CLAIM 1 -- a re-run over an unchanged folder opens NOTHING
# ---------------------------------------------------------------------------

def test_a_settled_folder_is_re_run_with_ZERO_container_reads(
        tmp_path, store, monkeypatch):
    u"""`06-edge-cases.md` §7: *re-run, nothing changed -> hash-and-skip, zero
    decoding.*

    🚨 COUNTED, NOT TIMED. A wall-clock assertion is flaky on a loaded machine
    and vacuous on a fast one; the container read is the cost the skip exists
    to avoid, so the number of them is the claim itself.
    """
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    folder = tmp_path / "Show S01"
    one_episode(folder)
    trash = str(tmp_path / "trash")

    settle(folder, store, trash)
    reader = CountingReader()
    after = PIPE.sync(API.scan(str(folder)), write=True, trash_root=trash,
                      results=store, reader=reader)

    assert reader.count == 0, reader.paths
    assert after.written == []
    assert len(after.settled) == 1
    assert u"already in sync" in after.settled[0][1]


def test_the_skip_leaves_the_TREE_byte_identical(tmp_path, store, monkeypatch):
    u"""⛔ HASHED, NOT LISTED. `LEDGER-HOT.md` trap 0d: *a retime is
    length-preserving*, so `{name: size}` is blind to the one thing this tool
    does -- three separate mutations passed a check written to catch them."""
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    folder = tmp_path / "Show S01"
    one_episode(folder)
    trash = str(tmp_path / "trash")

    settle(folder, store, trash)
    before = _tree(tmp_path)
    PIPE.sync(API.scan(str(folder)), write=True, trash_root=trash,
              results=store)
    assert _tree(tmp_path) == before


def test_TWENTY_FOUR_episodes_re_run_in_under_a_second_and_open_nothing(
        tmp_path, store, monkeypatch):
    u"""🚨 THE RULED NUMBER, and it is `06-edge-cases.md` §7's own: *≤ 1 s for
    24 episodes, zero decoding.*

    ⚠ THE READ COUNT IS THE HARD ASSERTION AND THE CLOCK IS THE SOFT ONE. A
    budget check on a shared machine is the flakiest thing a suite can hold, so
    the second is generous -- but it is here, because *"zero reads"* would
    still be satisfied by an implementation that hashed every byte of every
    1.4 GB video. `02-data-model.md`: head 64 KB + tail 64 KB + size, O(1) per
    file regardless of size.
    """
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    folder = tmp_path / "Show S01"
    folder.mkdir()
    for i in range(1, 25):
        one_episode(folder, stem=u"Show S01E%02d" % i, delay=2.0, variant=i)
    trash = str(tmp_path / "trash")

    settle(folder, store, trash)
    # 🚨 TWENTY-FOUR DISTINCT RECORDS, ASSERTED. With identical fixtures
    # every episode hashes the same and the store holds ONE -- so the skip
    # matches each episode against another episode's record and the check is
    # green for a reason that is not its own. Found by the probe.
    assert len(_files_under(store.root)) == 24,         u"the fixtures are not distinct, so this measures one episode 24 times"

    reader = CountingReader()
    started = time.time()
    after = PIPE.sync(API.scan(str(folder)), write=True, trash_root=trash,
                      results=store, reader=reader)
    took = time.time() - started

    assert reader.count == 0, reader.paths
    assert len(after.settled) == 24, after.summary()
    assert after.written == []
    assert took < 5.0, u"24 settled episodes took %.2f s" % took


def test_the_summary_SAYS_the_run_skipped_rather_than_going_quiet(
        tmp_path, store, monkeypatch):
    u"""⛔ A SKIP MAY NOT BE A SILENCE. `05-interface.md`: a run that reports
    nothing over a folder of finished episodes is indistinguishable from one
    that broke, and the user goes looking."""
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    folder = tmp_path / "Show S01"
    one_episode(folder)
    trash = str(tmp_path / "trash")

    settle(folder, store, trash)
    after = PIPE.sync(API.scan(str(folder)), write=True, trash_root=trash,
                      results=store)
    assert u"1 already in sync" in after.summary(), after.summary()
    # ⚠ AND IT IS NOT A `Result`. `03-permissions.md`: there is no fourth
    # outcome, and nothing was measured this run, so there is none to report.
    assert list(after) == []


def test_a_skipped_video_is_NOT_reported_as_unpaired(tmp_path, store,
                                                     monkeypatch):
    u"""⚠ THE TWO SURFACES ARE DIFFERENT FACTS. `unpaired` means *no subtitle
    was offered for this video*, which would send a user hunting for a file
    that is sitting right there, already synced."""
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    folder = tmp_path / "Show S01"
    one_episode(folder)
    trash = str(tmp_path / "trash")

    settle(folder, store, trash)
    after = PIPE.sync(API.scan(str(folder)), write=True, trash_root=trash,
                      results=store)
    assert after.unpaired == []
    assert len(after.settled) == 1


# ---------------------------------------------------------------------------
# 🚨 CLAIM 2 -- the file always wins
# ---------------------------------------------------------------------------

def test_a_DB_that_says_synced_loses_to_a_file_that_says_otherwise(
        tmp_path, store, monkeypatch):
    u"""🚨 `06-edge-cases.md` §7, the row that is the whole safety property:
    *Results DB says synced, file says otherwise -- **the file always wins**.*

    ⛔ A DB that can veto a re-sync is a DB that can make the tool refuse to
    fix something it broke. Here the output is edited behind the store's back
    and the run must open the video again.
    """
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    folder = tmp_path / "Show S01"
    one_episode(folder)
    trash = str(tmp_path / "trash")
    settle(folder, store, trash)

    output = str(folder / "Show S01E01.ja.srt")
    assert os.path.isfile(output)
    _write(output, _shifted(4.0))          # somebody re-timed it by hand

    reader = CountingReader()
    after = PIPE.sync(API.scan(str(folder)), write=True, trash_root=trash,
                      results=store, reader=reader)
    assert reader.count == 1, u"the edited file was believed, not measured"
    assert after.settled == []
    assert len(after.written) == 1


def test_a_deleted_output_is_re_synced_rather_than_assumed_present(
        tmp_path, store, monkeypatch):
    u"""⭐ THE OTHER HALF OF *the file wins*, and it is the half a subset test
    would miss. If the recorded output is simply GONE, a rule that only asked
    *"is everything here accounted for?"* would answer yes over an empty
    folder."""
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    folder = tmp_path / "Show S01"
    _video, sub = one_episode(folder)
    trash = str(tmp_path / "trash")
    settle(folder, store, trash)

    output = str(folder / "Show S01E01.ja.srt")
    os.remove(output)
    _write(sub, _shifted(2.0))             # put the source back

    reader = CountingReader()
    after = PIPE.sync(API.scan(str(folder)), write=True, trash_root=trash,
                      results=store, reader=reader)
    assert reader.count == 1
    assert after.settled == []
    assert os.path.isfile(output)


def test_a_NEW_subtitle_beside_a_settled_episode_is_measured(
        tmp_path, store, monkeypatch):
    u"""⭐ *Nothing changed* is a claim about the WHOLE candidate set. A file
    the run has never weighed might be the better one, and a store that only
    checked its own output would never look at it."""
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    folder = tmp_path / "Show S01"
    one_episode(folder)
    trash = str(tmp_path / "trash")
    settle(folder, store, trash)

    _write(folder / "[Other] Show - 01.ja.srt", _shifted(3.0))

    reader = CountingReader()
    after = PIPE.sync(API.scan(str(folder)), write=True, trash_root=trash,
                      results=store, reader=reader)
    assert reader.count == 1, u"a new candidate was skipped unmeasured"
    assert after.settled == []


def test_an_edited_SOURCE_is_re_processed(tmp_path, store, monkeypatch):
    u"""`06-edge-cases.md` §7: *subtitle edited since last sync -> hash differs
    -> re-processed.* ⚠ Here with `dedupe=False`, so the source survives the
    run and is still on offer to be edited."""
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    folder = tmp_path / "Show S01"
    _video, sub = one_episode(folder)
    trash = str(tmp_path / "trash")
    settle(folder, store, trash, dedupe=False)

    _write(sub, _shifted(6.0))

    reader = CountingReader()
    after = PIPE.sync(API.scan(str(folder)), write=True, trash_root=trash,
                      results=store, reader=reader, dedupe=False)
    assert reader.count == 1
    assert after.settled == []


def test_a_RENAMED_output_is_still_recognised(tmp_path, store, monkeypatch):
    u"""⭐ THE REASON THE KEY IS A CONTENT HASH. `02-data-model.md`: *keyed on
    the content hash of the subtitle, so it survives renaming* -- and renaming
    is what this tool DOES, so a path-keyed store would miss its own output.

    ⚠ Renamed to a form the tool would ALSO write for this video, so the run
    still offers it as a candidate. A subtitle renamed out of the episode's
    identity is a different question -- discovery stops offering it at all.
    """
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    folder = tmp_path / "Show S01"
    one_episode(folder)
    trash = str(tmp_path / "trash")
    settle(folder, store, trash)

    output = str(folder / "Show S01E01.ja.srt")
    moved = str(folder / "Show S01E01.jpn.srt")
    os.rename(output, moved)

    reader = CountingReader()
    after = PIPE.sync(API.scan(str(folder)), write=True, trash_root=trash,
                      results=store, reader=reader)
    assert reader.count == 0, u"the renamed file was not recognised: %s" \
                              % reader.paths
    assert len(after.settled) == 1


# ---------------------------------------------------------------------------
# ⛔ CLAIM 3 -- a skip never costs a user a file
# ---------------------------------------------------------------------------

def _measured(subtitle):
    u"""The one field `_out_dir_for` reads off a `_Measured`: where
    the subtitle is, for the `rename=False` case."""
    return PIPE._Measured(u"video.mkv", subtitle)


def test_resolve_ownership_never_trashes_a_PROTECTED_file(tmp_path):
    u"""⭐ THE GUARD ITSELF, unit-tested, because the library shape that
    reaches it is narrow and a unit check cannot be rescued by luck.

    `_resolve_ownership` rule 1 -- *a file any slot would write is never
    superseded by another* -- is computed from the SLOTS OF THIS RUN, and a
    video the results DB skipped contributes none. `protected` is that rule
    extended to the videos that are not here.
    """
    import tsubasa.dedupe as D
    import tsubasa.sidecar as SC

    mine = str(tmp_path / "Alpha" / "01.ja.srt")
    loser = D.Candidate(mine, SC.parse(u"01.ja.srt"), None, 10, 100.0)
    winner_path = str(tmp_path / "Bravo" / "01.ja.srt")
    winner = D.Candidate(winner_path, SC.parse(u"01.ja.srt"), None, 300, 1400.0)

    def a_slot():
        # ⚠ A FAITHFUL by_path. It was empty because the branch under test did
        # not read it — and `_refuse_target_collisions` does, so the
        # double went from harmless to a KeyError. `LEDGER-HOT.md` trap
        # 0b: build an injected double from the REAL type, never from what the
        # signature looks like it wants.
        return PIPE._Slot(
            video=str(tmp_path / "Bravo" / "01.mkv"), stem=u"01", lang=u"ja",
            group=[], by_path={winner.path: _measured(winner.path),
                               loser.path: _measured(loser.path)},
            candidates=[winner, loser],
            plan=None, writes=[(winner, u"01.ja.srt")], superseded=[loser],
            notes=[], explicit=False)

    unguarded = a_slot()
    PIPE._resolve_ownership([unguarded])
    assert [c.path for c in unguarded.superseded] == [mine],         u"the fixture does not reach the trash, so it proves nothing"

    guarded = a_slot()
    PIPE._resolve_ownership([guarded], protected={PIPE._key(mine)})
    assert guarded.superseded == []
    assert any(u"already in sync" in n for n in guarded.notes), guarded.notes


def test_a_SKIPPED_rip_keeps_its_subtitle_when_its_TWIN_is_replaced(
        tmp_path, store, monkeypatch):
    u"""🚨 THE LIBRARY THAT LOST EVERYTHING, ARRIVING THROUGH A NEW DOOR.

    Two rips of one episode -- the ordinary library Sonic ruled on at 3b --
    share an episode key, so each video is offered BOTH answers. Replace one
    rip's video file and its records stop matching, so it is re-measured while
    its twin is skipped. ⛔ The re-measured slot then supersedes every
    candidate that lost, and one of those is the SKIPPED rip's answer.

    ⭐ That file has no slot of its own this run to claim it, which is exactly
    what `Settled.protected` supplies.
    """
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    folder = tmp_path / "Show S01"
    folder.mkdir()
    _write_mkv(folder / "Show S01E01 [720p].mkv", MKV_CUES,
               duration_s=RUNTIME, per_cluster=4)
    _write_mkv(folder / "Show S01E01 [1080p].mkv", MKV_CUES,
               duration_s=RUNTIME, per_cluster=4)
    _write(folder / "[Grp] Show - 01.ja.srt", _shifted(2.0))
    trash = str(tmp_path / "trash")

    settle(folder, store, trash)
    kept = str(folder / "Show S01E01 [720p].ja.srt")
    assert os.path.isfile(kept)
    was = io.open(kept, "rb").read()

    # ⚠ A DIFFERENT ENCODE OF THE SAME EPISODE: same cues, so the alignment
    # is unchanged, and different bytes, so the recorded video no longer
    # matches. `per_cluster` is the one knob that moves the file without
    # moving a single timestamp.
    _write_mkv(folder / "Show S01E01 [1080p].mkv", MKV_CUES,
               duration_s=RUNTIME, per_cluster=3)

    after = PIPE.sync(API.scan(str(folder)), write=True, trash_root=trash,
                      results=store)
    assert [os.path.basename(v) for v, _w in after.settled] ==         ["Show S01E01 [720p].mkv"], after.settled
    assert os.path.isfile(kept),         u"a skipped video's answer was trashed by the twin beside it"
    assert io.open(kept, "rb").read() == was


def test_a_SETTLED_slot_is_never_re_timed_by_the_run_that_skipped_it(
        tmp_path, store, monkeypatch):
    u"""⛔ THE -4.0 s SHAPE. `apply._render` re-reads at write time, so a file
    retimed twice gets double the offset and both runs report CONFIDENT. A skip
    that still wrote would be that defect with the store's name on it."""
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    folder = tmp_path / "Show S01"
    one_episode(folder)
    trash = str(tmp_path / "trash")
    settle(folder, store, trash)

    output = str(folder / "Show S01E01.ja.srt")
    was = io.open(output, "rb").read()
    # 🚨 THE BYTES ALONE CANNOT SEE THIS. A re-run of a converged folder writes
    # at an offset of ~0, so the file it produces is byte-identical to the one
    # it read — which means "it skipped" and "it did the work again and got the
    # same answer" look the same from the disk. `probe_adj29`: deleting the
    # skip's own `continue` survived a check written to catch exactly that.
    # ⭐ So assert BOTH: nothing moved, and nothing was opened to decide it.
    for _ in range(3):
        reader = CountingReader()
        again = PIPE.sync(API.scan(str(folder)), write=True, trash_root=trash,
                          results=store, reader=reader)
        assert reader.count == 0, reader.paths
        assert again.written == []
        assert len(again.settled) == 1, again.summary()
    assert io.open(output, "rb").read() == was


# ---------------------------------------------------------------------------
# ⛔ nothing is recorded that did not happen
# ---------------------------------------------------------------------------

def test_a_DRY_RUN_records_NOTHING(tmp_path, store, monkeypatch):
    u"""🚨 `LEDGER-HOT.md`: *a report composed from the plan is not a report
    about what happened.* Here the stakes are higher than a wrong sentence --
    the next run ACTS on a record, so a dry run that wrote one would tell
    tomorrow's run the work was done and tomorrow's run would agree."""
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    folder = tmp_path / "Show S01"
    one_episode(folder)
    trash = str(tmp_path / "trash")

    dry = PIPE.sync(API.scan(str(folder)), write=False, trash_root=trash,
                    results=store)
    assert len(dry.confident) == 1, dry.summary()
    assert store.recorded == 0
    assert not os.path.isdir(store.root) or _files_under(store.root) == []

    # ⭐ And the run that follows it is a full one, not a skip.
    reader = CountingReader()
    PIPE.sync(API.scan(str(folder)), write=True, trash_root=trash,
              results=store, reader=reader)
    assert reader.count == 1


def test_a_FORCED_write_is_deliberately_not_recorded(tmp_path, store,
                                                     monkeypatch):
    u"""⛔ A forced write is the most dangerous thing this tool does and is
    reported as REFUSED for that reason (`LEDGER.md` §Interface). Recording it
    would make the next ordinary run skip it **in silence** -- so the refusal
    is re-measured and re-stated every time."""
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    folder = tmp_path / "Show S01"
    video, _sub = one_episode(folder)
    wrong = _write(folder / "wrong.ja.srt",
                   _srt([3.3 + 7.8 * i for i in range(180)]))
    trash = str(tmp_path / "trash")

    forced = PIPE.sync([(video, wrong)], write=True, force=True,
                       trash_root=trash, results=store)
    assert len(forced.forced) == 1, forced.summary()
    assert forced.written, u"the fixture did not force a write"
    assert store.recorded == 0


def test_results_False_reads_and_writes_NOTHING(tmp_path, store, monkeypatch):
    u"""⚠ `False` IS NOT `None`. `None` means *you decide* and gets the real
    per-user store; `False` means *no history at all*, and a bare falsy test
    would silently turn one into the other."""
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    folder = tmp_path / "Show S01"
    one_episode(folder)
    trash = str(tmp_path / "trash")

    for _ in range(3):
        report = PIPE.sync(API.scan(str(folder)), write=True,
                           trash_root=trash, results=False)
    assert report.settled == []
    assert store.recorded == 0


# ---------------------------------------------------------------------------
# the store itself
# ---------------------------------------------------------------------------

def _files_under(root):
    out = []
    for dirpath, _dirs, names in os.walk(str(root)):
        out.extend(os.path.join(dirpath, n) for n in names)
    return sorted(out)


def a_record(tmp_path, digest=None, **kw):
    payload = tmp_path / "payload.srt"
    _write(payload, _srt(CUE_STARTS[:20]))
    key = content_key(str(payload))
    fields = dict(
        video_digest=u"v" * 64, video_size=1234,
        video_path=str(tmp_path / "ep.mkv"), lang=u"ja", outcome=CONFIDENT,
        word=u"locked", segments=[[None, -2.0]], dropped_in_gap=0,
        dropped_before_zero=0,
        output_digest=digest or key.digest, output_size=key.size,
        output_path=str(payload), source_digest=u"s" * 64, source_size=99,
        source_path=str(tmp_path / "src.srt"),
        considered=[R.Considered(digest or key.digest, key.size, str(payload),
                                 CONFIDENT)])
    fields.update(kw)
    return R.Record(**fields), key


def test_a_record_round_trips_through_json(tmp_path, store):
    record, key = a_record(tmp_path)
    store.record(record)
    back = store.get(key)
    assert back is not None
    assert back.output_digest == record.output_digest
    assert back.segments == [[None, -2.0]]
    assert back.word == u"locked"
    assert [c.digest for c in back.considered] == \
        [c.digest for c in record.considered]


def test_a_record_from_an_older_VERSION_is_ignored_not_reinterpreted(
        tmp_path, store):
    u"""⭐ The same rule `cache.py` holds, and here it is also the release valve
    for *the aligner got better and yesterday's refusal might not be one.*"""
    record, key = a_record(tmp_path)
    store.record(record)
    newer = R.Results(root=store.root, version=store.version + 1)
    assert newer.get(key) is None
    # ⛔ STALE, NOT MISSING. The record is FOUND and refused for its version,
    # which is what keeps the branch live -- a version in the directory name
    # would make it unreachable and the refusal untestable.
    assert newer.stale == 1, newer.stats()
    assert newer.misses == 1


def test_a_CORRUPT_record_is_a_miss_and_never_an_exception(tmp_path, store):
    u"""🚨 A store that can break a run is worse than no store. ⚠ And
    `except Exception` is deliberate: `LEDGER-HOT.md` records `zlib.error`
    deriving straight from `Exception`, so enumerating the types you thought of
    turns a fail-open into a crash in the caller."""
    record, key = a_record(tmp_path)
    store.record(record)
    path = _files_under(store.root)[0]
    with io.open(path, "w", encoding="utf-8") as fh:
        fh.write(u'{"version": 1, "video": {"digest": 1}}')
    assert store.get(key) is None
    assert store.corrupt == 1


def test_a_record_whose_file_CHANGED_SIZE_is_stale(tmp_path, store):
    u"""⚠ The digest matched by construction -- it is the filename -- so the
    SIZE is the independent witness. `content_key` samples head and tail, so a
    file edited only in its middle keeps its digest."""
    record, key = a_record(tmp_path)
    store.record(record)
    fatter = type(key)(key.digest, key.size + 1, key.mtime)
    assert store.get(fatter) is None
    assert store.stale == 1


def test_forget_drops_a_record(tmp_path, store):
    u"""⭐ `02-data-model.md` marks this store DISPOSABLE, and a store nobody
    can clear is not."""
    record, key = a_record(tmp_path)
    store.record(record)
    assert store.forget(record.output_digest) is True
    assert store.get(key) is None
    assert store.forget(record.output_digest) is False


def test_a_record_is_written_ATOMICALLY(tmp_path, store, monkeypatch):
    u"""⛔ `LEDGER-HOT.md`, bitten three times: `open(path, 'w')` truncates the
    moment it opens, so a write that then raises leaves zero bytes. A record
    half-written by a crashed run is read by the next one."""
    record, key = a_record(tmp_path)
    store.record(record)
    before = io.open(_files_under(store.root)[0], "rb").read()

    from tsubasa import paths as PATHS
    real = PATHS.atomic_write_bytes

    def explode(path, data):
        raise IOError("disk full")

    monkeypatch.setattr(R, "atomic_write_bytes", explode)
    with pytest.raises(IOError):
        store.record(record)
    monkeypatch.setattr(R, "atomic_write_bytes", real)
    assert io.open(_files_under(store.root)[0], "rb").read() == before
    assert store.get(key) is not None


def test_the_store_never_writes_beside_the_media(tmp_path, store, monkeypatch):
    u"""⛔ `02-data-model.md`: NEVER beside the media. `subsync` wrote
    `_ref_2.ass` and a 500 KB `.npy` next to the subtitles it was aligning,
    inside a corpus its own README marks do-not-modify."""
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    folder = tmp_path / "Show S01"
    one_episode(folder)
    trash = str(tmp_path / "trash")

    settle(folder, store, trash)
    left = sorted(os.listdir(str(folder)))
    assert left == ["Show S01E01.ja.srt", "Show S01E01.mkv"], left


def test_the_default_root_is_under_the_per_user_cache(monkeypatch, tmp_path):
    u"""⭐ `02-data-model.md`: per-user app data, overridable by
    `TSUBASA_CACHE`. ⚠ Asserted through the env var rather than against a
    hardcoded platform path -- `paths.cache_root` owns the platform question
    and has its own checks for it."""
    monkeypatch.setenv("TSUBASA_CACHE", str(tmp_path / "elsewhere"))
    assert R.Results().root == str(tmp_path / "elsewhere" / R.RESULTS_DIR)


# ---------------------------------------------------------------------------
# 🚨 `Record.stable` -- the fixed point, not the state after one run
# ---------------------------------------------------------------------------

def test_a_first_run_is_NOT_stable_and_the_second_one_IS(tmp_path,
                                                         monkeypatch):
    u"""🚨 THE DEFECT THIS PROPERTY WAS BUILT AGAINST, ASSERTED DIRECTLY.

    Run 1 sees one candidate, writes it out under the video's basename, and
    leaves the original -- so the folder holds TWO subtitles and
    `05-interface.md` rules that it should hold one. ⛔ A store that called run
    1's state *settled* would skip run 2 and keep both files FOREVER. Measured
    exactly that way while this was built.
    """
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    folder = tmp_path / "Show S01"
    one_episode(folder)
    trash = str(tmp_path / "trash")

    store = R.Results(root=str(tmp_path / "db"))
    PIPE.sync(API.scan(str(folder)), write=True, trash_root=trash,
              results=store)
    first = _records_in(store)
    assert len(first) == 1
    assert first[0].stable is False, \
        u"run 1 wrote a file it had never weighed and called the folder done"

    PIPE.sync(API.scan(str(folder)), write=True, trash_root=trash,
              results=store)
    settled_now = [r for r in _records_in(store) if r.stable]
    assert settled_now, u"run 2 left the folder unsettled for ever"

    # ⭐ AND THE RULED PROPERTY SURVIVED: one subtitle, at the name a player
    # loads, with the original recoverable in the trash.
    left = sorted(n for n in os.listdir(str(folder)) if n.endswith(".srt"))
    assert left == ["Show S01E01.ja.srt"], left
    assert os.listdir(trash) == ["[Grp] Show S01E01.ja.srt"]


def test_stable_COUNTS_and_is_not_a_set_test(tmp_path):
    u"""🚨 THE PREDICATE, IN ISOLATION.

    Every other check reaches `stable` through a whole run — where
    `settled()`'s own counting catches the same shape anyway, so a mutant
    that reduced `stable` to a set test SURVIVED all of them. Defence in
    depth is why; a guard with no check of its own is not.

    The shape is the zero-offset one: `apply` writes back the bytes it
    read, so the output hashes to its own source. As SETS that reads
    {d} <= {d} — stable, on run 1, with two files in the folder. COUNTED it is
    {d: 2} <= {d: 1}, which is false, and run 2 does the trashing
    `05-interface.md` requires.
    """
    src = str(tmp_path / "source.srt")
    _write(src, _srt(CUE_STARTS[:20]))
    key = R.subtitle_key(src)
    out = str(tmp_path / "out.srt")
    shutil.copy2(src, out)                # ⭐ byte-identical, a second FILE

    def record(**kw):
        fields = dict(
            video_digest=u"v" * 64, video_size=1, video_path=u"ep.mkv",
            lang=u"ja", outcome=CONFIDENT, word=u"locked", segments=[],
            dropped_in_gap=0, dropped_before_zero=0,
            output_digest=key.digest, output_size=key.size, output_path=out,
            source_digest=key.digest, source_size=key.size, source_path=src,
            considered=[R.Considered(key.digest, key.size, src, CONFIDENT)])
        fields.update(kw)
        return R.Record(**fields)

    # RUN 1 — one candidate offered, and the output is a NEW file beside it.
    # Two files, one digest: expected {d: 2}, offered {d: 1}.
    run1 = record()
    assert run1.expected() == {key.digest: 2}, run1.expected()
    assert run1.offered() == {key.digest: 1}, run1.offered()
    assert run1.stable is False, u"run 1 called itself a fixed point"

    # RUN 2 — the output is now one OF the candidates and the stale original
    # was trashed. One file, one digest. ⚠ And the output must not be counted
    # twice merely because it was rewritten in place: that made a converged
    # slot expect the digest twice while holding one file, so it could never
    # settle at all.
    run2 = record(
        considered=[R.Considered(key.digest, key.size, out, CONFIDENT),
                    R.Considered(key.digest, key.size, src, CONFIDENT,
                                 survived=False)])
    assert run2.expected() == {key.digest: 1}, run2.expected()
    assert run2.offered() == {key.digest: 2}, run2.offered()
    assert run2.stable is True, u"a converged slot never settles"


def test_a_TRASHED_candidate_is_recorded_as_not_surviving(tmp_path,
                                                          monkeypatch):
    u"""⭐ `Considered.survived`. A candidate this run sent to the trash is
    legitimately not on offer next time, so counting it as expected would make
    the folder disagree with the record for ever."""
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    folder = tmp_path / "Show S01"
    one_episode(folder)
    trash = str(tmp_path / "trash")
    store = R.Results(root=str(tmp_path / "db"))

    PIPE.sync(API.scan(str(folder)), write=True, trash_root=trash,
              results=store)
    PIPE.sync(API.scan(str(folder)), write=True, trash_root=trash,
              results=store)

    trashed = [c for r in _records_in(store) for c in r.considered
               if not c.survived]
    assert [os.path.basename(c.path) for c in trashed] == \
        ["[Grp] Show S01E01.ja.srt"]


def test_an_IN_PLACE_retime_is_not_counted_as_a_surviving_candidate(tmp_path):
    u"""🚨 THE BYTES, NOT THE PATH. `LEDGER-HOT.md` trap 0d: a retime is
    length-preserving, so `os.path.exists` -- and even a size check -- calls
    an in-place rewrite *"survived"*. Recording the OLD digest as still present
    would make the next run expect bytes that are not there, for ever."""
    path = str(tmp_path / "sub.srt")
    _write(path, _srt(CUE_STARTS))
    # ⚠ THE SUBTITLE KEY, NOT THE CACHE'S. Since F5 a subtitle is hashed WHOLE
    # and a video is sampled — head 64 KB + tail 64 KB + size — because a
    # retime is length-preserving and a middle edit above 128 KB was invisible.
    # A fixture built with the sampled key measures a digest the code no longer
    # computes.
    was = R.subtitle_key(path)
    assert PIPE._still_there(path, was) is True

    _write(path, _srt([t - 2.0 for t in CUE_STARTS]))
    assert os.path.getsize(path) == was.size, \
        u"the fixture is not length-preserving, so it tests the size check"
    assert PIPE._still_there(path, was) is False


def _records_in(store):
    out = []
    for path in _files_under(store.root):
        with io.open(path, "r", encoding="utf-8") as fh:
            import json
            out.append(R.Record.from_json(json.load(fh)))
    return out


# ---------------------------------------------------------------------------
# 🚨 THE ADVERSARIAL PASS — 2026-09-09. Every one of these was GREEN while the
# defect below it was live, and three of them cost a user's file.
# ---------------------------------------------------------------------------

def test_a_SKIPPED_videos_answer_is_never_written_OVER_in_place(
        tmp_path, store, monkeypatch):
    u"""🚨 THE ONE THAT DESTROYED A USER'S ONLY COPY. Found independently by
    THREE adversaries, on DEFAULT FLAGS.

    `_resolve_ownership` holds two rules. `Settled.protected` was
    wired into rule 1 — *never superseded*, the trash guard — and rule 2 —
    *never written OVER in place* — is computed from `slots` forty lines
    earlier, which a skipped video has none of. So the sharing was invisible
    and the write landed: the settled video's subtitle retimed for its
    neighbour, **destroyed rather than trashed**, in the run that called it
    already in sync. ⛔ And it never healed: afterwards both videos are live,
    rule 2 fires for both, and it protects the corrupted file for ever.

    ⚠ THE FIXTURE NEEDS THE SAME STEM AND DIFFERENT TIMING. An adversary
    turned each knob: different stems mean the live video writes a different
    NAME so no overwrite is possible, and identical timing means the byte
    assertion is satisfied BY the defect. Only this corner is red.
    """
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    folder = tmp_path / "Show S01"
    folder.mkdir()
    _write_mkv(folder / "Show S01E01.mkv", MKV_CUES, duration_s=RUNTIME,
               per_cluster=4)
    sub = _write(folder / "[Grp] Show - 01.ja.srt", _shifted(2.0))
    trash = str(tmp_path / "trash")
    settle(folder, store, trash, rename=False)
    was = io.open(sub, "rb").read()

    # ⚠ A SECOND CONTAINER OF THE SAME EPISODE, five seconds later — an
    # ordinary re-download. Same stem, different timing.
    _write_mkv(folder / "Show S01E01 [v2].mkv",
               [(t + 5.0, 2.0) for t, _d in MKV_CUES],
               duration_s=RUNTIME, per_cluster=4)

    after = PIPE.sync(API.scan(str(folder)), write=True, rename=False,
                      trash_root=trash, results=store)
    assert io.open(sub, "rb").read() == was, (
        u"a settled video's only subtitle was written over in place: %s"
        % after.summary())


def test_a_run_asked_for_a_DIFFERENT_DESTINATION_does_the_work(
        tmp_path, store, monkeypatch):
    u"""🚨 A RECORD CARRIED NO TRACE OF THE FLAGS OF THE RUN THAT WROTE IT.

    Measured: settle a library, then ask for `--out elsewhere`, and the
    run reported *1 already in sync* with **the output directory never
    created**. The user asked for files somewhere and got nothing, with a
    success-shaped report. ⛔ No check could catch it — every check in this file
    re-ran with identical flags.
    """
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    folder = tmp_path / "Show S01"
    one_episode(folder)
    trash = str(tmp_path / "trash")
    settle(folder, store, trash)

    out = str(tmp_path / "elsewhere")
    after = PIPE.sync(API.scan(str(folder)), write=True, out_dir=out,
                      trash_root=trash, results=store)
    assert after.settled == [], after.summary()
    assert os.path.isdir(out) and os.listdir(out), \
        u"--out on a settled library produced nothing: %s" % after.summary()


def test_an_already_correct_subtitle_still_converges_to_ONE_file(
        tmp_path, store, monkeypatch):
    u"""🚨 AT AN OFFSET OF ZERO, `apply` WRITES BACK THE BYTES IT READ.

    So the output hashes to its own source, and a `stable` built on SETS
    declared run 1 a fixed point with **two** subtitles in the folder — the
    exact failure it was invented to prevent. ⭐ The input is the ordinary one:
    a subtitle already correct for that release, which is precisely what hato
    fetches. ⚠ This suite could not see it because `one_episode`
    hardcoded a 2.0 s delay, so every fixture wrote bytes no candidate had.
    """
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    folder = tmp_path / "Show S01"
    folder.mkdir()
    _write_mkv(folder / "Show S01E01.mkv", MKV_CUES, duration_s=RUNTIME,
               per_cluster=4)
    _write(folder / "[Grp] Show S01E01.ja.srt", _shifted(0.0))
    trash = str(tmp_path / "trash")
    for _ in range(3):
        PIPE.sync(API.scan(str(folder)), write=True, trash_root=trash,
                  results=store)
    left = sorted(n for n in os.listdir(str(folder)) if n.endswith(".srt"))
    assert left == ["Show S01E01.ja.srt"], left


def test_deleting_one_of_TWO_IDENTICAL_files_is_noticed(tmp_path, store,
                                                        monkeypatch):
    u"""🚨 A SET CANNOT COUNT. `here` and `expected` were sets of
    digests, so two paths holding one digest were **one entry** — and deleting
    one of them changed nothing the skip could see."""
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    folder = tmp_path / "Show S01"
    one_episode(folder)
    trash = str(tmp_path / "trash")
    settle(folder, store, trash)

    out = str(folder / "Show S01E01.ja.srt")
    twin = str(folder / "Show S01E01.en.srt")
    shutil.copy2(out, twin)
    video = str(folder / "Show S01E01.mkv")
    here = [str(folder / n) for n in os.listdir(str(folder))
            if n.endswith(".srt")]
    assert R.settled(store, video, here).skip is False, \
        u"a brand-new duplicate was invisible to a set"

    os.remove(twin)
    os.remove(out)
    assert R.settled(store, video, [str(folder / n)
                                    for n in os.listdir(str(folder))
                                    if n.endswith(".srt")]).skip is False


def test_a_MIDDLE_edit_in_a_large_subtitle_is_seen(tmp_path, store,
                                                    monkeypatch):
    u"""🚨 *THE FILE ALWAYS WINS* WAS FALSE ABOVE 128 KB.
    `cache.content_key` is head 64 KB + tail 64 KB + size — the cost
    model for VIDEOS — and a retime is length-preserving, so an adversary
    retimed 61 cues in the middle of a 188 KB output and the run reported
    *already in sync* with zero container reads.
    ⭐ Subtitles are hashed WHOLE now; videos stay sampled."""
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    folder = tmp_path / "Show S01"
    folder.mkdir()
    _write_mkv(folder / "Show S01E01.mkv", MKV_CUES, duration_s=RUNTIME,
               per_cluster=4)
    # ⚠ BIG ENOUGH THAT HEAD+TAIL CANNOT COVER IT. An 8 KB fixture — every
    # other one in this file — makes the defect unreachable.
    # ⚠ BIG ENOUGH TO HAVE A MIDDLE AT ALL. At 700 chars the file was 148 KB:
    # over 2 x SAMPLE, so it looked large, but head and tail together still
    # covered 88% of it and every span an edit could land in was sampled.
    fat = _srt([t + 2.0 for t in CUE_STARTS],
               text=u"line " + u"x" * 1500)
    _write(folder / "[Grp] Show S01E01.ja.srt", fat)
    trash = str(tmp_path / "trash")
    settle(folder, store, trash)

    out = str(folder / "Show S01E01.ja.srt")
    raw = io.open(out, "rb").read()
    assert len(raw) > 4 * 64 * 1024, u"the fixture is too small to have a middle"
    # 🚨 THE EDIT MUST LAND BEYOND THE HEAD SAMPLE AND BEFORE THE TAIL, OR THE
    # SAMPLED HASH SEES IT AND THE CHECK PASSES FOR THE WRONG REASON. The first
    # version replaced a timestamp that sits ~32 KB in — inside head — and the
    # mutant restoring head+tail hashing survived it. Measured, not assumed:
    # the assertion below proves the bytes changed ONLY in the untouched span.
    lo, hi = 64 * 1024, len(raw) - 64 * 1024
    swapped = raw[:lo] + raw[lo:hi].replace(b" --> ", b" ==> ", 1) + raw[hi:]
    assert swapped != raw and len(swapped) == len(raw)
    assert swapped[:lo] == raw[:lo] and swapped[hi:] == raw[hi:],         u"the edit escaped the middle, so head+tail can see it"
    io.open(out, "wb").write(swapped)

    reader = CountingReader()
    after = PIPE.sync(API.scan(str(folder)), write=True, trash_root=trash,
                      results=store, reader=reader)
    assert after.settled == [], u"an edited output was believed"
    assert reader.count == 1


def test_a_store_that_RAISES_never_breaks_the_run(tmp_path, monkeypatch):
    u"""🚨 *A STORE THAT CAN BREAK A RUN IS WORSE THAN NO STORE* — the rule
    `Results.get` has held since it was written, and neither
    `record` nor the read in `settled` honoured it. Measured:
    `sync()` died mid-folder AFTER a write had landed, so episode 1 was
    written, 2 and 3 never were, and no report said which half was done."""
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    folder = tmp_path / "Show S01"
    folder.mkdir()
    for i in (1, 2, 3):
        one_episode(folder, stem=u"Show S01E%02d" % i, variant=i)
    trash = str(tmp_path / "trash")

    class Hostile(R.Results):
        def record(self, record):
            raise IOError("the profile is read-only")

        def get(self, key):
            raise IOError("the store is unreachable")

    after = PIPE.sync(API.scan(str(folder)), write=True, trash_root=trash,
                      results=Hostile(root=str(tmp_path / "db")))
    assert len(after.written) == 3, after.summary()
    for i in (1, 2, 3):
        assert os.path.isfile(str(folder / (u"Show S01E%02d.ja.srt" % i)))


def test_a_KEEP_ALL_name_collision_does_not_abandon_the_folder(
        tmp_path, store, monkeypatch):
    u"""🚨 `dedupe.plan` REFUSES TWO WRITES TO ONE PATH — correctly, that
    is data loss — but it did so by RAISING, two frames above
    `apply_plan`, so `sync()` died with no report at all and every
    later folder went unprocessed. ⛔ `06-edge-cases.md` §7 rules per-pair
    atomicity. The guard is kept; the escalation is not."""
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    folder = tmp_path / "Show S01"
    folder.mkdir()
    _write_mkv(folder / "Show S01E01.mkv", MKV_CUES, duration_s=RUNTIME,
               per_cluster=4)
    _write(folder / "[Grp] Show - 01.ja.srt", _shifted(2.0))
    trash = str(tmp_path / "trash")
    last = None
    for _ in range(4):
        last = PIPE.sync(API.scan(str(folder)), write=True, keep_all=True,
                         trash_root=trash, results=store)
    assert last is not None, u"sync() raised instead of reporting"
    # ⭐ AND IT IS NOT REPORTED AS A PLAN. A run that was asked to write and
    # could not is not a dry run.
    assert u"would sync" not in last.summary(), last.summary()


def test_a_WITHHELD_write_is_never_reported_as_a_plan(tmp_path, store,
                                                       monkeypatch):
    u"""🚨 A WRITE RULE 2 REFUSES IS NOT A DRY RUN. It was decided and then
    withheld, and the slot arrived at the report with no writes — so
    `expected_write` defaulted to False, the outcome stayed CONFIDENT, and
    a `write=True` run was **byte-identical in its report to a dry run**.
    The only trace was a note."""
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    folder = tmp_path / "Show S01"
    folder.mkdir()
    for tag in (u"720p", u"1080p"):
        _write_mkv(folder / (u"Show S01E01 [%s].mkv" % tag), MKV_CUES,
                   duration_s=RUNTIME, per_cluster=4)
    _write(folder / "[Grp] Show - 01.ja.srt", _shifted(2.0))
    trash = str(tmp_path / "trash")

    wet = PIPE.sync(API.scan(str(folder)), write=True, rename=False,
                    trash_root=trash, results=store)
    dry = PIPE.sync(API.scan(str(folder)), write=False, rename=False,
                    trash_root=trash, results=False)
    assert wet.failed, wet.summary()
    assert wet.summary() != dry.summary(), \
        u"a run that was asked to write reads exactly like a plan: %s" \
        % wet.summary()
    assert u"NOT WRITTEN" in wet.summary(), wet.summary()


# ---------------------------------------------------------------------------
# 🚨 THE SECOND ADVERSARIAL PASS — against the FIXES. Seven findings, and one
# of them was a regression the first round's fix caused.
# ---------------------------------------------------------------------------

def test_a_SETTLED_neighbour_never_blocks_a_live_video_from_re_syncing(
        tmp_path, store, monkeypatch):
    u"""🚨 THE REGRESSION THE FIRST FIX CAUSED, AND IT MADE THE STORE WORSE
    THAN NOT HAVING ONE.

    `Settled.protected` was *every candidate*, so a settled video stood in
    as an owner of its live NEIGHBOUR's own output — merely one of the files it
    had been offered — and rule 2 refused that neighbour's ordinary in-place
    re-sync. **Permanently**: the settled twin's candidates never change, so it
    stays settled and the live one stays refused, with the correction measured
    and never applied.

    ⭐ The two rules want DIFFERENT sets. Rule 2 asks *may this be written over
    while somebody still has to read it* — a skipped video reads nothing; what
    it needs is that its own ANSWER survives. Rule 1 asks *may this be trashed*
    and that covers everything it was offered.
    """
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    folder = tmp_path / "Show S01"
    folder.mkdir()
    for tag in (u"720p", u"1080p"):
        _write_mkv(folder / (u"Show S01E01 [%s].mkv" % tag), MKV_CUES,
                   duration_s=RUNTIME, per_cluster=4)
    _write(folder / "[Grp] Show - 01.ja.srt", _shifted(2.0))
    trash = str(tmp_path / "trash")
    settle(folder, store, trash)

    live = str(folder / "Show S01E01 [1080p].ja.srt")
    assert os.path.isfile(live)
    was = io.open(live, "rb").read()
    # ⚠ THE 1080p IS RE-ENCODED five seconds later — an ordinary re-download.
    _write_mkv(folder / "Show S01E01 [1080p].mkv",
               [(t + 5.0, 2.0) for t, _d in MKV_CUES],
               duration_s=RUNTIME, per_cluster=4)

    after = PIPE.sync(API.scan(str(folder)), write=True, trash_root=trash,
                      results=store)
    assert io.open(live, "rb").read() != was, (
        u"a live video could not re-sync its own output while a settled "
        u"neighbour held it as a candidate: %s" % after.summary())


def test_TWO_VIDEOS_that_want_ONE_output_name_are_BOTH_refused(
        tmp_path, store, monkeypatch):
    u"""🚨 ONE SUBTITLE CANNOT BE TWO VIDEOS' ANSWER, AND THERE IS NO NAME THAT
    SERVES BOTH.

    `05-interface.md` names the output `<video-basename>.<lang>.<ext>`
    and the basename drops the container extension — so `Show S01E01.mkv`
    and `Show S01E01.mp4`, an ordinary re-download, resolve to one path.
    Measured before the rule existed: `2 synced`, one video handed a
    subtitle **5 s wrong** and reported CONFIDENT · locked, then frozen there.

    ⭐ Refused rather than disambiguated: a player loads the basename, so both
    players look for the same file and `Show S01E01.mp4.ja.srt` is a name
    nothing loads. The clash is in the library, not in the code.
    """
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    folder = tmp_path / "Show S01"
    folder.mkdir()
    _write_mkv(folder / "Show S01E01.mkv", MKV_CUES, duration_s=RUNTIME,
               per_cluster=4)
    _write_mkv(folder / "Show S01E01.mp4",
               [(t + 5.0, 2.0) for t, _d in MKV_CUES],
               duration_s=RUNTIME, per_cluster=4)
    sub = _write(folder / "[Grp] Show - 01.ja.srt", _shifted(2.0))
    was = io.open(sub, "rb").read()
    trash = str(tmp_path / "trash")

    after = PIPE.sync(API.scan(str(folder)), write=True, trash_root=trash,
                      results=store)
    assert after.written == [], after.summary()
    assert len(after.failed) == 2, after.summary()
    assert not os.path.isfile(str(folder / "Show S01E01.ja.srt"))
    assert io.open(sub, "rb").read() == was
    assert any(u"cannot be two videos' answer" in n
               for r in after for n in r.notes), [r.notes for r in after]


def test_a_TRASHED_occupant_is_PUT_BACK_when_the_write_then_fails(
        tmp_path, monkeypatch):
    u"""🚨 THE TRASH SUCCEEDED AND THE WRITE FAILED, SO THE FOLDER HAD NEITHER.

    The trash-first branch inverts *write first, trash second* for the one case
    where the target IS the file. ⛔ It inherited that rule's failure mode: with
    the write then failing, the occupant was in the trash, nothing was written,
    and the report carried TWO contradictory notes — the second being the very
    sentence the previous fix added to promise this could not happen.

    ⭐ The bytes were always recoverable (`LEDGER-HOT.md` is satisfied by
    the trash). What this restores is the FOLDER, so a failed run is not
    silently a destructive one.
    """
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    import tsubasa.formats as FORMATS

    # ⚠ DRIVEN THROUGH sync(), NOT A HAND-BUILT PLAN. The first version built a
    # `DedupePlan` whose candidates carried `verdict=None`, so
    # `_render` raised and the run never reached the trash-first branch —
    # the check was green with the occupant intact for a reason that was not
    # its own. `LEDGER-HOT.md` trap 0b, in the plan rather than the
    # reader.
    folder = tmp_path / "Show S01"
    folder.mkdir()
    _write_mkv(folder / "Show S01E01.mkv", MKV_CUES, duration_s=RUNTIME,
               per_cluster=4)
    _write(folder / "[Erai-raws] Show - 01.ja.srt", _shifted(2.0))
    # ⭐ 60 cues loses rule 3a to the 200-cue file, so the winner's output name
    # IS this file's path — the shape the trash-first branch exists for.
    occupant = _write(folder / "Show S01E01.ja.srt",
                      _srt([t + 2.0 for t in CUE_STARTS[:60]]))
    was = io.open(occupant, "rb").read()
    trash = str(tmp_path / "trash")

    real = FORMATS.write_file

    def explode(target, data):
        raise IOError("[Errno 28] no space left on device")

    monkeypatch.setattr(FORMATS, "write_file", explode)
    report = PIPE.sync(API.scan(str(folder)), write=True, trash_root=trash,
                       results=False)
    monkeypatch.setattr(FORMATS, "write_file", real)

    assert report.written == [], report.summary()
    assert os.path.isfile(occupant), \
        u"the occupant was trashed for a write that never landed"
    assert io.open(occupant, "rb").read() == was
    notes = [n for r in report for n in r.notes]
    assert any(u"put back" in n for n in notes), notes


# ---------------------------------------------------------------------------
# ⛔ the explicit path records but never skips
# ---------------------------------------------------------------------------

def test_an_EXPLICIT_pair_is_always_carried_out_even_when_recorded(
        tmp_path, store, monkeypatch):
    u"""⛔ THE ASYMMETRY IS THE POINT. The user typed this pair. Naming a pair
    is an instruction to act on it, and answering an instruction with *"I did
    that last week"* is the same silence `--force` on a `Scan` is refused for.
    ⚠ It is also what would leave `plan.writable()` with an undecided pair,
    which raises -- so the structure says it too."""
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    folder = tmp_path / "Show S01"
    video, sub = one_episode(folder)
    trash = str(tmp_path / "trash")

    # ⚠ `rename=False` -- AN IN-PLACE RETIME, so the second run has somewhere
    # to write. With renaming on, run 1's output occupies the target name and
    # run 2 is refused for that reason instead, which would make this check
    # green for something that is not its subject.
    reader = CountingReader()
    for _ in range(2):
        report = PIPE.sync([(video, sub)], write=True, trash_root=trash,
                           results=store, reader=reader, rename=False)
    assert reader.count == 2, u"an explicit pair was skipped"
    assert report.settled == []
    assert len(report.written) == 1, report.summary()


# ---------------------------------------------------------------------------
# 🚨 THE ARMS `probe_adj29` PROVED WERE MASKED BY THEIR NEIGHBOURS
# ---------------------------------------------------------------------------

def test_a_recorded_SURVIVOR_that_vanishes_refuses_the_skip(tmp_path, store,
                                                            monkeypatch):
    u"""🚨 THE `gone` ARM, ISOLATED — and it took `dedupe=False` to reach it.

    ⛔ `test_a_deleted_output_is_re_synced` was green for a reason that is not
    its own. Records are FOUND through the candidates on disk, so deleting the
    output means no record is found at all and the *"no completed sync is
    recorded"* arm answers first. The `gone` arm never ran.

    ⭐ It is reachable only when a record expects a file that is **not** its own
    output: with `dedupe=False` the losing source survives, is recorded as a
    survivor, and can then be deleted while the output stays put.
    """
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    folder = tmp_path / "Show S01"
    _video, sub = one_episode(folder)
    trash = str(tmp_path / "trash")
    settle(folder, store, trash, dedupe=False)

    assert os.path.isfile(sub), u"dedupe=False did not keep the source"
    reader = CountingReader()
    before = PIPE.sync(API.scan(str(folder)), write=True, trash_root=trash,
                       results=store, reader=reader, dedupe=False)
    assert len(before.settled) == 1 and reader.count == 0, before.summary()

    os.remove(sub)
    reader = CountingReader()
    after = PIPE.sync(API.scan(str(folder)), write=True, trash_root=trash,
                      results=store, reader=reader, dedupe=False)
    assert after.settled == [], u"a record named a file that is gone and the run skipped anyway"
    assert reader.count == 1


def test_no_recorded_sync_says_SO_rather_than_blaming_the_files(tmp_path,
                                                                store,
                                                                monkeypatch):
    u"""⭐ THE `if not records` ARM BUYS A SENTENCE, NOT AN OUTCOME — measured,
    and worth saying rather than pretending otherwise.

    Blind every lookup and the run still refuses to skip, because the `added`
    arm catches it too. What changes is what the user is told: *"no completed
    sync is recorded for this video"* rather than *"1 subtitle on offer is not
    part of any recorded sync"*, which would be a true sentence that points at
    the wrong thing. `03-permissions.md` §hand-back makes the sentence
    load-bearing, so it gets a check.
    """
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    folder = tmp_path / "Show S01"
    one_episode(folder)
    trash = str(tmp_path / "trash")
    settle(folder, store, trash)

    video = str(folder / "Show S01E01.mkv")
    here = [str(folder / n) for n in os.listdir(str(folder))
            if n.endswith(".srt")]
    assert R.settled(store, video, here).skip is True

    monkeypatch.setattr(R.Results, "get", lambda self, key: None)
    state = R.settled(store, video, here)
    assert state.skip is False
    assert u"no completed sync is recorded" in state.reason, state.reason


def test_a_skipped_video_protects_a_SURVIVING_SOURCE_too(tmp_path, store,
                                                          monkeypatch):
    u"""⛔ `Settled.protected` IS EVERY CANDIDATE, NOT JUST THE OUTPUTS, and the
    twin fixture could not tell the two apart.

    With `dedupe=False` the losing source stays on disk. It is still a file a
    skipped video owns, and still one a neighbour's slot would happily
    supersede — so restricting `protected` to outputs loses it. Measured with
    `probe_adj29`: outputs-only and all-candidates are identical on every
    fixture where dedupe is on.
    """
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    folder = tmp_path / "Show S01"
    _video, sub = one_episode(folder)
    trash = str(tmp_path / "trash")
    settle(folder, store, trash, dedupe=False)

    video = str(folder / "Show S01E01.mkv")
    here = [str(folder / n) for n in os.listdir(str(folder))
            if n.endswith(".srt")]
    state = R.settled(store, video, here)
    assert state.skip is True
    names = sorted(os.path.basename(p) for p in state.protected)
    assert names == ["Show S01E01.ja.srt", os.path.basename(sub)], names


def test_a_record_for_ANOTHER_video_does_not_settle_this_one(tmp_path, store,
                                                              monkeypatch):
    u"""🚨 THE SAME BYTES CAN BE ONE VIDEO'S ANSWER AND ANOTHER'S CANDIDATE —
    Sonic's 3b ruling, *one subtitle may serve several videos*. A single-video
    fixture cannot see the guard that keeps them apart, so this uses two.
    """
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    folder = tmp_path / "Show S01"
    folder.mkdir()
    _write_mkv(folder / "Show S01E01 [720p].mkv", MKV_CUES,
               duration_s=RUNTIME, per_cluster=4)
    _write(folder / "[Grp] Show - 01.ja.srt", _shifted(2.0))
    trash = str(tmp_path / "trash")
    settle(folder, store, trash)

    # ⚠ A SECOND RIP JOINS, sharing the episode key and therefore the answer.
    _write_mkv(folder / "Show S01E01 [1080p].mkv", MKV_CUES,
               duration_s=RUNTIME, per_cluster=3)
    twin = str(folder / "Show S01E01 [1080p].mkv")
    here = [str(folder / n) for n in os.listdir(str(folder))
            if n.endswith(".srt")]
    state = R.settled(store, twin, here)
    assert state.skip is False, \
        u"a record made for its neighbour settled a video nothing was recorded for"
    assert u"no completed sync is recorded" in state.reason, state.reason


def test_a_candidate_that_cannot_be_READ_refuses_the_skip(tmp_path, store,
                                                           monkeypatch):
    u"""⭐ AN UNACCOUNTABLE FILE IS A REASON TO WORK, NOT TO GUESS. A candidate
    the store cannot hash is one it can say nothing about, and the measuring
    path reports what is wrong with it in a sentence — a silent skip reports
    nothing at all."""
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    folder = tmp_path / "Show S01"
    one_episode(folder)
    trash = str(tmp_path / "trash")
    settle(folder, store, trash)

    video = str(folder / "Show S01E01.mkv")
    here = [str(folder / n) for n in os.listdir(str(folder))
            if n.endswith(".srt")]
    assert R.settled(store, video, here).skip is True

    real = R.subtitle_key

    def refuse(path):
        if str(path).endswith(".srt"):
            raise IOError("locked by another process")
        return real(path)

    # ⚠ `subtitle_key` is what `settled()` calls for a candidate since F5.
    # Patching `content_key` still passed — against a guard that no longer ran.
    monkeypatch.setattr(R, "subtitle_key", refuse)
    state = R.settled(store, video, here)
    assert state.skip is False
    assert u"could not be read" in state.reason, state.reason


def test_the_store_writes_through_the_ATOMIC_writer_and_nothing_else(tmp_path):
    u"""⛔ READ FROM THE SOURCE, because a behaviour check cannot see this one.
    `test_a_record_is_written_ATOMICALLY` monkeypatches the writer, so a mutant
    that replaced it with a truncating `open(path, 'wb')` was overwritten by
    the check itself and survived. `probe_adj29`.

    ⭐ Same shape as `dedupe.py`'s AST check for deletion primitives: the rule
    is about which primitive is used, so the source is what states it.
    `LEDGER-HOT.md`, bitten three times: `open(path, 'w')` truncates on open,
    and a write that then raises leaves zero bytes.
    """
    import ast
    src = io.open(os.path.join(ROOT, "tsubasa", "results.py"),
                  encoding="utf-8").read()
    tree = ast.parse(src)
    called = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            name = getattr(fn, "id", None) or getattr(fn, "attr", None)
            if name:
                called.add(name)
    assert "atomic_write_bytes" in called
    # ⚠ `io.open` is used for READING and that is fine; what may never appear
    # is a write mode. Checked on the literal, because that is the thing.
    for bad in ('"w"', "'w'", '"wb"', "'wb'", '"a"', "'a'", '"ab"', "'ab'"):
        assert bad not in src, \
            u"results.py opens a file for writing directly (%s) instead of " \
            u"going through atomic_write_bytes" % bad


def test_an_EXPLICIT_run_records_so_a_later_DISCOVERY_run_can_skip(
        tmp_path, store, monkeypatch):
    u"""⭐ *Every run re-does the work* is the complaint 3a-bis exists to fix,
    and it does not stop being true because the first run named its pairs."""
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    folder = tmp_path / "Show S01"
    video, sub = one_episode(folder)
    trash = str(tmp_path / "trash")

    PIPE.sync([(video, sub)], write=True, trash_root=trash, results=store,
              dedupe=False)
    assert store.recorded >= 1

    # ⭐ Then the ordinary discovery path, settling the folder and skipping.
    settle(folder, store, trash, runs=2)
    reader = CountingReader()
    after = PIPE.sync(API.scan(str(folder)), write=True, trash_root=trash,
                      results=store, reader=reader)
    assert reader.count == 0, reader.paths
    assert len(after.settled) == 1
