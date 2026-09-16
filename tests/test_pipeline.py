# -*- coding: utf-8 -*-
u"""
`sync()` -- the run. RUNBOOK step 3b. Authority: `05-interface.md` §*The library
API*, `03-permissions.md`, `09-corpus-strategy.md` §Stage 3-4.

===========================================================================
🚨 THE THREE CLAIMS THAT CARRY THIS FILE
===========================================================================

  1. **The tuple path goes through `explicit_pairs()`.** Ruled 2026-09-08 and
     binding: *"a tuple path that silently skips every refusal is the one
     shape the whole project exists to prevent."* ⭐ It is asserted by feeding
     `sync()` the five refusals A11 exists for and requiring each one back as
     a result -- **not** by reading the source for a call, which is a claim
     about today's code.
  2. **Nothing is written unless `write=True`.** Asserted by hashing every
     byte in the tree before and after, never by reading a flag.
  3. **`output_path` is set only when a file actually moved.** `apply_plan`
     fills `report.written` in a dry run too -- that list is *what it would
     write* -- so this is the seam where a dry run learns to claim it wrote
     the folder.

⚠ THE CONTAINER READER IS INJECTED for the shape-specific checks (no track, a
thin track, a forced track) and REAL for the end-to-end ones. That is the same
seam shape as `dedupe.trash(sender=...)` and `movies.pair_movies(duration_of=)`
-- `07-test-plan.md` forbids code that never runs in the local configuration,
so the real reader stays the default and is driven here on a real Matroska file.
"""
import hashlib
import io
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tsubasa import api as API                                # noqa: E402
from tsubasa import arbitrate as _ARB                         # noqa: E402
from tsubasa import container as CONTAINER                    # noqa: E402
from tsubasa import cues as CUES                              # noqa: E402
from tsubasa import explicit as EXPLICIT                      # noqa: E402
from tsubasa import pipeline as PIPE                          # noqa: E402
from tsubasa import verdict as V                              # noqa: E402

# ⭐ REUSED, NOT REBUILT. `doctrine/tooling` §anti-rederivation: 20 throwaway
# scripts in one session re-derived a helper they were already importing a
# sibling of. `_write_mkv` is a complete synthetic Matroska writer and a second
# one would drift from the reader it is meant to exercise.
from test_container import _write_mkv                         # noqa: E402


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

#: 200 cues, 7 s apart, over a ~23-minute runtime -- an episode's shape.
#: ⚠ THE NUMBERS ARE LOAD-BEARING and each one is a floor in the code:
#:   * 200 cues over 1440 s gives 12 buckets of ~16, clearing MIN_BUCKET_CUES
#:     (8). At 24 cues every bucket is too thin, `runtime_check` comes back
#:     `absent` and the verdict CAPS the word at `fair` -- so a check for
#:     `locked` would have been failing for a reason that is not its own.
#:   * per_cluster=4 keeps a cluster under 32.767 s, which is what a Matroska
#:     block's int16 relative timecode can hold. The fixture writer raises
#:     rather than truncating, but only if you get it right.
CUE_STARTS = [5.0 + 7.0 * i for i in range(200)]
RUNTIME = 1440.0
MKV_CUES = [(t, 2.0) for t in CUE_STARTS]

#: A subtitle that is a different show: 180 cues on a rhythm that matches
#: nothing in `CUE_STARTS`.
#:
#: 🚨 IT ENDS AT 1,399 s ON PURPOSE. The first version ran to 2,098 s against a
#: 1,440 s video, so the RUNTIME GATE refused it before the aligner ever ran --
#: and the checks named for a refused ALIGNMENT were measuring the duration
#: filter instead. A fixture that fails for the wrong reason is green and
#: worthless.
WRONG_STARTS = [3.3 + 7.8 * i for i in range(180)]


def _stamp(seconds):
    ms = int(round(seconds * 1000.0))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return u"%02d:%02d:%02d,%03d" % (h, m, s, ms)


def _srt(starts, text=u"line"):
    out = []
    for i, t in enumerate(starts):
        out.append(u"%d\n%s --> %s\n%s %d\n\n"
                   % (i + 1, _stamp(t), _stamp(t + 1.5), text, i + 1))
    return u"".join(out)


def _write(path, text):
    with io.open(str(path), "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    return str(path)


def _shifted(delay):
    u"""A subtitle `delay` seconds LATE. ⚠ It needs a NEGATIVE offset:
    `12-alignment.md` §1 -- the offset is what is ADDED to every subtitle
    timestamp."""
    return _srt([t + delay for t in CUE_STARTS])


def _tree(root):
    u"""Every file under `root`, with its bytes hashed.

    ⭐ This is how *"nothing was written"* is asserted. A flag says what the
    code believes; this says what is on the disk.
    """
    out = {}
    for dirpath, _dirs, names in os.walk(str(root)):
        for name in names:
            p = os.path.join(dirpath, name)
            with io.open(p, "rb") as fh:
                out[p] = hashlib.md5(fh.read()).hexdigest()
    return out


@pytest.fixture()
def episode(tmp_path):
    u"""One real Matroska video with a real subtitle track, and one subtitle
    file that is 2.0 s late."""
    video = _write_mkv(tmp_path / "Show S01E01.mkv", MKV_CUES,
                       duration_s=RUNTIME, per_cluster=4, language=u"jpn")
    sub = _write(tmp_path / "Show S01E01.ja.srt", _shifted(2.0))
    return {"root": tmp_path, "video": str(video), "subtitle": sub}


# ---------------------------------------------------------------------------
# the injected reader -- for shapes a fixture file cannot cheaply carry
# ---------------------------------------------------------------------------

def _reader(tracks, duration=RUNTIME, ok=True, reason=u""):
    def read(path):
        if not ok:
            return CONTAINER.ContainerInfo(
                path=path, outcome=CUES.Outcome.ERROR, reason=reason)
        return CONTAINER.ContainerInfo(path=path, format="matroska",
                                       duration=duration, tracks=list(tracks))
    return read


def _track(index, starts, codec=u"S_TEXT/ASS", forced=False, default=True,
           language=u"jpn"):
    u"""🚨 REAL `Cue` OBJECTS, because that is what the real reader returns.

    The first version of this helper handed back bare floats. Every check
    driving the injected reader was green -- and `sync()` raised
    `float() argument must be ... not 'Cue'` on every actual container, from
    four frames down inside `unique_starts`. `LEDGER-HOT.md`'s *an ASCII
    fixture cannot test an encoding rule*, wearing a new hat: **a fake that
    disagrees with the real thing about a TYPE measures the fake.**
    """
    return CONTAINER.Track(index, index + 1, "subtitle", codec=codec,
                           language=language, default=default, forced=forced,
                           cues=[CUES.Cue(t, t + 2.0, u"") for t in starts])


# ===========================================================================
# 1. 🚨 THE TUPLE PATH GOES THROUGH explicit_pairs() -- ruled, binding
# ===========================================================================

def test_a_swapped_pair_comes_back_as_a_refusal(episode):
    u"""🚨 `--pair A.srt A.mkv` is the commonest mistake this flag attracts.

    ⭐ A `for video, subtitle in pairs:` loop cannot produce this result. It
    would hand the `.srt` to the container reader and report whatever that
    said -- which is a sentence about EBML, not about the user's mistake.
    """
    got = PIPE.sync([(episode["subtitle"], episode["video"])])
    assert len(got) == 1
    assert got[0].outcome == V.ERROR
    assert "swapped" in got[0].reason
    assert not got.confident


def test_a_missing_file_comes_back_as_a_refusal(episode, tmp_path):
    got = PIPE.sync([(str(tmp_path / "nope.mkv"), episode["subtitle"])])
    assert got[0].outcome == V.ERROR
    assert "does not exist" in got[0].reason


def test_a_directory_where_a_file_goes_comes_back_as_a_refusal(episode,
                                                               tmp_path):
    got = PIPE.sync([(str(tmp_path), episode["subtitle"])])
    assert got[0].outcome == V.ERROR
    assert "directory" in got[0].reason


def test_one_subtitle_claimed_by_TWO_videos_refuses_BOTH(episode, tmp_path):
    u"""🚨 A contradiction inside the user's own assertion, and there is no
    basis to prefer either. ⚠ Refusing only the second would be
    ORDER-DEPENDENT, which hides until somebody reorders a manifest."""
    second = _write_mkv(tmp_path / "Show S01E02.mkv", MKV_CUES,
                        duration_s=RUNTIME, per_cluster=4)
    got = PIPE.sync([(episode["video"], episode["subtitle"]),
                     (str(second), episode["subtitle"])])
    assert len(got) == 2
    assert all(r.outcome == V.ERROR for r in got)
    assert all("claimed" in r.reason or "twice" in r.reason or
               "two" in r.reason for r in got), [r.reason for r in got]


def test_a_flat_pair_is_refused_with_the_shape_that_would_work(episode):
    u"""⚠ `("a.mkv", "a.srt")` is one flat pair, not two malformed entries, and
    guessing either way would be wrong. Only `explicit_pairs()` says so."""
    with pytest.raises(EXPLICIT.ExplicitPairError) as exc:
        PIPE.sync((episode["video"], episode["subtitle"]))
    assert "list of pairs" in str(exc.value)


def test_a_bare_string_is_refused_rather_than_iterated(episode):
    with pytest.raises(EXPLICIT.ExplicitPairError) as exc:
        PIPE.sync(episode["video"])
    assert "list OF pairs" in str(exc.value)


def test_EVERY_accepted_pair_is_given_a_verdict(episode):
    u"""⛔ `PairPlan.writable()` raises `VerdictRequired` naming any pair a
    loop skipped. ⭐ It is called inside `sync()` as the structural proof --
    so if it did not raise, every pair was decided."""
    plan = EXPLICIT.explicit_pairs(
        pair_args=[(episode["video"], episode["subtitle"])])
    PIPE.sync(plan)
    assert plan.undecided() == []
    assert len(plan.decisions()) == 1


def test_the_refusals_and_the_measured_pairs_arrive_TOGETHER(episode,
                                                             tmp_path):
    u"""⭐ The whole point of the conversion: a run containing one good pair
    and one broken input returns BOTH, and the broken one is not lost."""
    got = PIPE.sync([(episode["video"], episode["subtitle"]),
                     (str(tmp_path / "gone.mkv"), episode["subtitle"])])
    assert len(got) == 2
    assert len(got.errored) == 1
    assert len(got.confident) == 1


# ===========================================================================
# 2. 🚨 NOTHING IS WRITTEN UNLESS write=True
# ===========================================================================

def test_a_plain_sync_changes_not_one_byte(episode):
    before = _tree(episode["root"])
    got = PIPE.sync([(episode["video"], episode["subtitle"])])
    assert got.confident, "the fixture must actually align, or this proves nothing"
    assert _tree(episode["root"]) == before


def test_a_scan_sync_changes_not_one_byte(episode):
    before = _tree(episode["root"])
    got = PIPE.sync(API.scan(str(episode["root"])))
    assert got.confident
    assert _tree(episode["root"]) == before


def test_output_path_is_EMPTY_on_a_dry_run(episode):
    u"""🚨 `apply_plan` fills `report.written` in a dry run -- that list is
    *what it would write*. Reading it without checking `report.performed`
    makes every dry run claim it wrote the folder."""
    got = PIPE.sync([(episode["video"], episode["subtitle"])])
    assert got.confident
    assert got.confident[0].output_path is None
    assert got.written == []


# ===========================================================================
# 3. THE REFERENCE -- 00-INDEX Rule 1: an accelerator, never a dependency
# ===========================================================================

def test_a_video_with_no_subtitle_track_is_refused_with_what_would_fix_it():
    u"""🚨 `03-permissions.md` §hand-back: every refusal states what was
    measured, why it fell short, and WHAT WOULD CHANGE IT."""
    ref, why = PIPE.reference_for("/x/v.mkv", _reader([]))
    assert ref is None
    assert "no subtitle track" in why
    assert "B6" in why


def test_a_track_too_thin_to_measure_says_so_and_says_how_thin():
    ref, why = PIPE.reference_for("/x/v.mkv", _reader([_track(0, [1.0, 2.0])]))
    assert ref is None
    assert "too few cues" in why and "2" in why


def test_the_track_with_the_MOST_cues_wins_over_a_forced_one():
    u"""⭐ A forced track carries signs only -- a few dozen moments over a
    whole episode -- so it aligns to a correct offset with almost no
    whole-runtime evidence behind it.

    ⚠ NAMED SO THE WINNER LOSES EVERY LOWER KEY: the fat track is NOT default,
    IS at the higher index, and the thin one is default and first. Only the
    cue-count rule can put the fat one in front.
    """
    thin = _track(0, CUE_STARTS[:20], forced=True, default=True)
    fat = _track(1, CUE_STARTS, forced=False, default=False)
    ref, _why = PIPE.reference_for("/x/v.mkv", _reader([thin, fat]))
    assert len(ref.starts) == 200
    assert ref.track.index == 1


def test_a_forced_track_is_used_when_it_is_the_ONLY_one():
    u"""⭐ Rule 1: the embedded track is an accelerator, and a thin accelerator
    still beats none. Excluding forced outright would refuse a video this can
    honestly measure."""
    only = _track(0, CUE_STARTS[:40], forced=True)
    ref, _why = PIPE.reference_for("/x/v.mkv", _reader([only]))
    assert ref is not None and ref.track.forced


def test_a_bitmap_track_is_labelled_as_one_in_both_vocabularies():
    u"""⚠ Matroska says `S_HDMV/PGS`; ffmpeg says `hdmv_pgs_subtitle`. The
    label is all this decides -- the band is identical -- but a wrong label in
    a bug report costs somebody an hour."""
    for codec in (u"S_HDMV/PGS", u"hdmv_pgs_subtitle", u"S_VOBSUB",
                  u"dvd_subtitle"):
        ref, _why = PIPE.reference_for(
            "/x/v.mkv", _reader([_track(0, CUE_STARTS, codec=codec)]))
        assert ref.kind == V.BITMAP_TRACK, codec
    ref, _why = PIPE.reference_for(
        "/x/v.mkv", _reader([_track(0, CUE_STARTS, codec=u"S_TEXT/UTF8")]))
    assert ref.kind == V.TEXT_TRACK


def test_an_unreadable_container_is_reported_as_the_containers_own_reason():
    ref, why = PIPE.reference_for(
        "/x/v.mkv", _reader([], ok=False, reason=u"the file is empty (0 bytes)"))
    assert ref is None and "0 bytes" in why


def test_one_container_read_per_VIDEO_however_many_candidates(episode,
                                                              tmp_path):
    u"""⭐ `00-INDEX.md` Rule 4 where it matters most here: the container read
    is 0.087 s and the alignment is 0.049 s, so re-reading per candidate would
    make the read the dominant cost of the run.

    🚨 IT IS DRIVEN THROUGH THE **EXPLICIT** PATH, and that is the fix rather
    than a preference. Written against a `Scan` it could not fail: `_sync_scan`
    calls `_reference_cached` once per VIDEO, outside the candidate loop, so
    deleting the cache changed nothing there and the mutant survived honestly.
    The cache earns its keep where a video appears in several PAIRS -- the
    explicit path, and the film-duration seam.
    """
    subs = []
    for lang in ("ja", "en", "de"):
        subs.append(_write(tmp_path / (u"Show S01E01.%s.srt" % lang),
                           _shifted(2.0)))
    reads = []
    real = CONTAINER.read

    def counting(path, **kw):
        reads.append(path)
        return real(path, **kw)

    got = PIPE.sync([(episode["video"], s) for s in subs],
                    reader=lambda p: counting(p, timing=True))
    assert len(got) == 3, [(r.subtitle, r.outcome) for r in got]
    assert len(reads) == 1, reads
    # ⭐ And the scan path agrees, though it cannot fail on its own.
    reads[:] = []
    PIPE.sync(API.scan(str(tmp_path)),
              reader=lambda p: counting(p, timing=True))
    assert len(reads) == 1, reads


# ===========================================================================
# 4. MEASURING -- the cheap gate first, and the two outcomes kept apart
# ===========================================================================

def test_a_correct_pair_is_CONFIDENT_with_the_offset_it_was_built_with(episode):
    got = PIPE.sync([(episode["video"], episode["subtitle"])])
    r = got[0]
    assert r.outcome == V.CONFIDENT, r.reason
    assert r.verdict_word == u"locked", (r.verdict_word, r.excess_over_chance)
    # ⚠ NEGATIVE. `12-alignment.md` §1: the offset is ADDED to every subtitle
    # timestamp, and this subtitle is 2.0 s LATE.
    assert abs(r.offset - (-2.0)) < 0.05, r.segments
    assert r.match_percent >= 95
    assert r.holds_throughout and r.runtime_check == u"held"
    assert r.lang == u"ja"


def test_a_subtitle_far_too_long_is_stopped_BEFORE_the_aligner_runs(tmp_path):
    u"""⭐ `09-corpus-strategy.md` Stage 3: runtime is the cheapest possible
    filter. ⚠ Asserted by proving `align` was NOT called -- a check on the
    outcome alone would pass against a gate that ran after it.

    🚨 AND THE OUTCOME IS **ERROR**, not REFUSED. REFUSED promises *"it
    aligned, but not well enough to trust"* and nothing here aligned at all.
    Built as REFUSED first, and `--force` then authorised a write that
    `apply._render` correctly refused for having no segments -- a forced write
    that silently did nothing. `verdict.py` already rules the same shape the
    same way: a readable file with three cues is `_too_thin` and comes back
    ERROR, because *not measured* and *measured and rejected* are different
    results.
    """
    video = _write_mkv(tmp_path / "Show S01E01.mkv", MKV_CUES,
                       duration_s=600.0, per_cluster=4)
    sub = _write(tmp_path / "Show S01E01.ja.srt",
                 _srt([5.0 + 7.0 * i for i in range(600)]))
    calls = []
    real = PIPE.align
    PIPE.align = lambda *a, **k: (calls.append(a) or real(*a, **k))
    try:
        got = PIPE.sync([(str(video), sub)])
    finally:
        PIPE.align = real
    assert got[0].outcome == V.ERROR, got[0].reason
    assert calls == [], "the aligner ran despite the runtime gate"
    assert "longer" in got[0].reason


def test_an_UNREADABLE_subtitle_is_ERROR_and_a_readable_empty_one_is_not(
        episode, tmp_path):
    u"""🚨 `LEDGER-HOT.md`: never conflate *"parsed zero cues"* with *"could
    not read the file."* subsync shipped that confusion twice.

    ⭐ Both come back non-confident, and they must not come back the SAME. The
    unreadable one is refused by the reader with the reader's own sentence; the
    empty one reaches the aligner and the VERDICT calls it unmeasurable.

    🚨 BINARY JUNK IS NOT THE UNREADABLE CASE, and the first version of this
    check used it. Measured: `formats.read_file` returns **OK with zero cues**
    for NUL bytes, a JPEG header and plain English prose alike -- the SRT
    parser accepts any bytes and finds no cues in them, which is the
    OK-with-zero-cues design working exactly as `03-permissions.md` requires.
    So both halves took the same branch and the check was comparing a sentence
    with itself.
    ⭐ The branch that genuinely produces ERROR is a format with no reader --
    `formats.NOT_IMPLEMENTED_YET`, an honest *"we cannot read this"* rather
    than a guess.
    """
    unreadable = _write(tmp_path / "Show S01E01.en.ttml",
                        u"<tt><body><p begin='1s'>hi</p></body></tt>")
    empty = _write(tmp_path / "Show S01E01.de.srt", u"")

    bad = PIPE.sync([(episode["video"], unreadable)])[0]
    nil = PIPE.sync([(episode["video"], empty)])[0]
    assert bad.outcome == V.ERROR and nil.outcome == V.ERROR
    assert bad.reason != nil.reason
    assert "could not be read" in bad.reason and "TTML" in bad.reason
    assert "could not be read" not in nil.reason
    assert "0 cues" in nil.reason


def test_binary_junk_reads_as_zero_cues_rather_than_as_unreadable(episode,
                                                                  tmp_path):
    u"""⭐ The measurement that corrected the check above, pinned so it stays
    true. `03-permissions.md`: *never conflate "parsed zero cues" with "could
    not read the file"* -- and this is the direction that surprises people:
    an SRT parser handed a JPEG says *zero cues*, not *unreadable*."""
    from tsubasa import formats
    for payload in (b"\x00" * 64, b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 8,
                    b"the quick brown fox\n"):
        p = tmp_path / "x.srt"
        p.write_bytes(payload)
        parsed = formats.read_file(str(p))
        assert parsed.ok and len(parsed.cues) == 0, payload[:8]


def test_a_wrong_show_is_REFUSED_rather_than_written(episode, tmp_path):
    u"""⭐ Rule 2, end to end: a confidently wrong answer is worse than no
    answer. The subtitle here has nothing to do with the video's timing."""
    wrong = _write(tmp_path / "Show S01E01.fr.srt",
                   _srt(WRONG_STARTS))
    got = PIPE.sync([(episode["video"], wrong)], write=True)
    assert got[0].outcome == V.REFUSED, got[0].reason
    assert got[0].output_path is None
    assert got[0].reason.strip()


# ===========================================================================
# 5. WRITING
# ===========================================================================

def test_write_true_produces_the_file_a_player_auto_loads(episode):
    got = PIPE.sync([(episode["video"], episode["subtitle"])], write=True)
    r = got[0]
    assert r.outcome == V.CONFIDENT
    assert r.output_path is not None
    assert os.path.basename(r.output_path) == "Show S01E01.ja.srt"
    assert os.path.exists(r.output_path)
    # ⭐ And the bytes actually moved: the first cue is now where the video's is.
    parsed = CUES  # noqa: F841 -- reached through formats below
    from tsubasa import formats
    again = formats.read_file(r.output_path)
    assert abs(again.cues[0].start - CUE_STARTS[0]) < 0.05


def test_rename_false_writes_back_over_the_subtitles_own_name(tmp_path):
    video = _write_mkv(tmp_path / "Show S01E01.mkv", MKV_CUES,
                       duration_s=RUNTIME, per_cluster=4)
    sub = _write(tmp_path / "whatever the user called it.srt", _shifted(2.0))
    got = PIPE.sync([(str(video), sub)], write=True, rename=False)
    assert got[0].output_path == sub
    assert os.path.exists(sub)


def test_the_loser_of_a_slot_goes_to_the_trash(tmp_path, monkeypatch):
    u"""⚠ `TSUBASA_NO_OS_TRASH` forces the local fallback, which is the tested
    path -- `send2trash` is not installed on the build machine and the OS arm
    is reached through the injected sender."""
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    video = _write_mkv(tmp_path / "Show S01E01.mkv", MKV_CUES,
                       duration_s=RUNTIME, per_cluster=4)
    good = _write(tmp_path / "[Erai-raws] Show - 01.ja.srt", _shifted(2.0))
    thin = _write(tmp_path / "[shincaps] Show - 01.ja.srt",
                  _srt([t + 2.0 for t in CUE_STARTS[:60]]))
    trash = tmp_path / "trash"
    got = PIPE.sync(API.scan(str(tmp_path)), write=True,
                    trash_root=str(trash))
    winners = [r for r in got if r.output_path]
    assert len(winners) == 1, [(r.subtitle, r.outcome) for r in got]
    assert winners[0].superseded
    assert not os.path.exists(winners[0].superseded[0])
    assert os.listdir(str(trash))
    assert good and thin


def test_a_DIFFERENT_loser_at_the_winners_target_goes_to_the_trash_FIRST(
        tmp_path, monkeypatch):
    u"""🚨 THIS CHECK USED TO ASSERT THE DEFECT, AND THE DEFECT DESTROYED A
    USER'S FILE.

    `[Erai-raws] Show - 01.ja.srt` (200 cues) beats a thin
    `Show S01E01.ja.srt` (60 cues) on rule 3a — and then writes to exactly that
    file's path. It was written as *"the file at that path survives — it IS
    the output now"*, and required it NOT to be trashed.

    ⛔ It is not the output. It is a **different file**: the 60-cue subtitle the
    user already had. `os.replace` obliterated it, the trash loop skipped it as
    *"written over"*, and a tree-wide search for its bytes found none — on a
    first run, default flags, no results DB. Found by an adversarial pass.

    ⭐ THE ORDER INVERTS HERE, WITH ITS JUSTIFICATION. *"Write first, trash
    second"* exists so a failed trash after a good write leaves the user BOTH
    files; when the target IS the file, a good write leaves them NEITHER. So a
    different file at the target is trashed FIRST — recoverable — and only then
    written over. ⚠ A genuine in-place retime, the winner over ITSELF, is
    unchanged and has its own check below.
    """
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    d = tmp_path / "d"
    d.mkdir()
    _write_mkv(d / "Show S01E01.mkv", MKV_CUES, duration_s=RUNTIME,
               per_cluster=4)
    _write(d / "[Erai-raws] Show - 01.ja.srt", _shifted(2.0))
    thin = _write(d / "Show S01E01.ja.srt",
                  _srt([t + 2.0 for t in CUE_STARTS[:60]]))
    was = io.open(thin, "rb").read()
    trash = tmp_path / "trash"

    got = PIPE.sync(API.scan(str(d)), write=True, trash_root=str(trash))
    assert len(got.written) == 1
    assert os.path.basename(got.written[0].output_path) == "Show S01E01.ja.srt"
    # ⛔ THE USER'S BYTES ARE RECOVERABLE. `LEDGER-HOT.md` is unconditional:
    # never delete a user's file, trash only.
    recovered = [os.path.join(str(trash), n) for n in os.listdir(str(trash))]
    assert any(io.open(p, "rb").read() == was for p in recovered), recovered
    # ⭐ AND THE REPORT SAYS SO. It read `superseded=[]` while destroying it.
    assert [os.path.basename(p) for p in got.written[0].superseded] == \
        ["Show S01E01.ja.srt"], got.written[0].superseded
    assert any("before" in n and "written over it" in n
               for n in got.written[0].notes), got.written[0].notes


def test_a_TRUE_in_place_retime_is_never_trashed(tmp_path, monkeypatch):
    u"""⭐ THE OTHER HALF, and the distinction the defect above was missing.

    Under `rename=False` the winner writes back over its OWN name. Trashing it
    then would delete the file just produced and leave the user with neither —
    so this one is correctly left alone. The difference is whether the file at
    the target is the winner itself or somebody else.
    """
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    d = tmp_path / "d"
    d.mkdir()
    _write_mkv(d / "Show S01E01.mkv", MKV_CUES, duration_s=RUNTIME,
               per_cluster=4)
    only = _write(d / "[Erai-raws] Show - 01.ja.srt", _shifted(2.0))
    trash = tmp_path / "trash"

    got = PIPE.sync(API.scan(str(d)), write=True, rename=False,
                    trash_root=str(trash))
    assert len(got.written) == 1
    assert got.written[0].output_path == only
    assert os.path.exists(only)
    assert not trash.exists() or os.listdir(str(trash)) == [], \
        os.listdir(str(trash))


def test_a_DRY_RUN_reports_no_superseded_even_with_a_loser(tmp_path,
                                                           monkeypatch):
    u"""⚠ `superseded` is documented *"paths trashed"* and it is populated from
    what actually MOVED. A dry run with a real loser is where reading it from
    the PLAN and reading it from the report differ."""
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    d = tmp_path / "d"
    d.mkdir()
    _write_mkv(d / "Show S01E01.mkv", MKV_CUES, duration_s=RUNTIME,
               per_cluster=4)
    good = _write(d / "[Erai-raws] Show - 01.ja.srt", _shifted(2.0))
    loser = _write(d / "[shincaps] Show - 01.ja.srt",
                   _srt([t + 2.0 for t in CUE_STARTS[:60]]))
    before = _tree(tmp_path)

    got = PIPE.sync(API.scan(str(d)), trash_root=str(tmp_path / "trash"))
    assert got.confident, "the fixture must align, or this proves nothing"
    assert all(r.superseded == [] for r in got), [r.superseded for r in got]
    assert got.written == []
    assert _tree(tmp_path) == before
    assert os.path.exists(good) and os.path.exists(loser)


def test_dedupe_false_trashes_nothing_and_SAYS_so(tmp_path, monkeypatch):
    u"""⚠ *"nothing was trashed"* and *"nothing lost"* are different claims,
    so the losers are still named."""
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    video = _write_mkv(tmp_path / "Show S01E01.mkv", MKV_CUES,
                       duration_s=RUNTIME, per_cluster=4)
    a = _write(tmp_path / "[Erai-raws] Show - 01.ja.srt", _shifted(2.0))
    b = _write(tmp_path / "[shincaps] Show - 01.ja.srt",
               _srt([t + 2.0 for t in CUE_STARTS[:60]]))
    got = PIPE.sync(API.scan(str(tmp_path)), write=True, dedupe=False,
                    trash_root=str(tmp_path / "trash"))
    assert os.path.exists(a) and os.path.exists(b)
    written = [r for r in got if r.output_path]
    assert written and written[0].superseded == []
    assert any("dedupe is off" in n for n in written[0].notes)


def test_keep_all_writes_every_confident_candidate_and_trashes_nothing(
        tmp_path, monkeypatch):
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    video = _write_mkv(tmp_path / "Show S01E01.mkv", MKV_CUES,
                       duration_s=RUNTIME, per_cluster=4)
    a = _write(tmp_path / "[Erai-raws] Show - 01.ja.srt", _shifted(2.0))
    b = _write(tmp_path / "[SubsPlease] Show - 01.ja.srt", _shifted(3.0))
    got = PIPE.sync(API.scan(str(tmp_path)), write=True, keep_all=True,
                    trash_root=str(tmp_path / "trash"))
    written = sorted(r.output_path for r in got if r.output_path)
    assert len(written) == 2, [(r.subtitle, r.outcome, r.reason) for r in got]
    assert os.path.exists(a) and os.path.exists(b)
    assert all(r.superseded == [] for r in got)


def test_out_dir_is_taken_as_given_and_never_flattened(episode, tmp_path):
    u"""`05-interface.md`: `--out` mirrors, never flattens. Only the caller
    knows the library root, so this takes the directory it is handed."""
    out = tmp_path / "out"
    out.mkdir()
    got = PIPE.sync([(episode["video"], episode["subtitle"])], write=True,
                    out_dir=str(out))
    assert os.path.dirname(got[0].output_path) == str(out)


# ===========================================================================
# 6. ⛔ --force IS EXPLICIT-PAIRS-ONLY
# ===========================================================================

def test_force_on_a_scan_is_REFUSED_loudly(episode):
    u"""⛔ On the discovery path forcing means *write the best of several
    REFUSED candidates*, which is exactly what `dedupe.py`'s rule 1 is a GATE
    rather than a sort key to prevent. Ignoring it silently would leave the
    user believing they had overridden something."""
    with pytest.raises(ValueError) as exc:
        PIPE.sync(API.scan(str(episode["root"])), write=True, force=True)
    assert "explicit pairs only" in str(exc.value)


def test_force_writes_a_REFUSED_pair_and_still_reports_it_as_REFUSED(
        episode, tmp_path):
    u"""🚨 `LEDGER.md` §Interface: a GUI painted a run green because
    *"11 confident, 1 refused"* contains `confident`. A forced write is the
    most dangerous thing this tool does and it may NEVER be relabelled."""
    wrong = _write(tmp_path / "Show S01E01.fr.srt",
                   _srt(WRONG_STARTS))
    plain = PIPE.sync([(episode["video"], wrong)], write=True)
    assert plain[0].output_path is None

    forced = PIPE.sync([(episode["video"], wrong)], write=True, force=True)
    r = forced[0]
    assert r.outcome == V.REFUSED
    assert r.verdict_word is None
    assert r.forced is True
    assert r.output_path is not None and os.path.exists(r.output_path)
    assert forced.summary().startswith("1 FORCED")


def test_a_forced_DRY_RUN_never_claims_the_file_was_written(episode, tmp_path):
    u"""🚨 A REASON THAT SAYS "WRITTEN" WHEN NOTHING WAS WRITTEN IS A
    CONFIDENTLY WRONG REPORT, and worse than the missing write because the
    user stops looking.

    `Decision.reason` is composed by A11 *before* the attempt -- *"WRITTEN
    UNDER --force"* -- so on a dry run it is a claim about something that did
    not happen. Found while chasing a real defect: a forced write silently did
    nothing (the candidate carried no `Verdict` object) and the result still
    read `WRITTEN UNDER --force` with `output_path` empty.
    """
    wrong = _write(tmp_path / "Show S01E01.fr.srt", _srt(WRONG_STARTS))
    got = PIPE.sync([(episode["video"], wrong)], force=True)
    r = got[0]
    assert r.forced is True
    assert r.output_path is None
    assert r.reason.startswith("(dry run")


def test_a_pair_the_runtime_gate_stopped_still_carries_a_VERDICT_OBJECT(
        episode, tmp_path):
    u"""🚨 THE DEFECT THIS PINS, and it took two forms.

    A candidate stopped before the aligner ran was left with `verdict=None`,
    so `apply_plan` -- which reads `getattr(candidate.verdict, "outcome",
    None)` -- saw *"the verdict is missing"*, refused the write, and the report
    still said **"WRITTEN UNDER --force"** with `output_path` empty. A
    confidently wrong report is worse than the missing write.

    ⭐ Two fixes, and the second is the real one: `judge()` now gives EVERY
    pair a `Verdict` object, and the gate's outcome is **ERROR** rather than
    REFUSED -- so `--force` correctly declines it, because force overrides a
    refusal and never a missing measurement.
    """
    long_sub = _write(tmp_path / "Show S01E01.es.srt",
                      _srt([5.0 + 7.0 * i for i in range(300)]))
    got = PIPE.sync([(episode["video"], long_sub)], write=True, force=True)
    r = got[0]
    assert r.outcome == V.ERROR
    assert "longer" in r.reason
    # ⛔ Nothing written, and the report does not pretend otherwise.
    assert r.output_path is None
    assert r.forced is False
    assert "WRITTEN UNDER" not in r.reason


def test_force_never_writes_an_ERROR(episode, tmp_path):
    u"""⛔ ERROR means unmeasured, so there is no offset to stand behind.
    `--force` overrides a refusal, never a missing measurement."""
    junk = tmp_path / "Show S01E01.en.srt"
    junk.write_bytes(b"\x00\x01\x02not a subtitle\xff")
    got = PIPE.sync([(episode["video"], str(junk))], write=True, force=True)
    assert got[0].outcome == V.ERROR
    assert got[0].output_path is None


# ===========================================================================
# 7. ⛔ vad=True NEITHER WORKS SILENTLY NOR RAISES FROM FOUR FRAMES DOWN
# ===========================================================================

def test_vad_true_says_the_band_has_not_been_fitted(episode):
    u"""⛔ `verdict.MASK_BAND` is `None` until RUNBOOK B6, and borrowing the
    cue-vs-cue 2.5x would silently refuse the 2.42x uncut pair
    `12-alignment.md` §5 measured as CORRECT.

    ⭐ `doctrine/architecture`: *instruction, not refusal* -- the run says what
    would make it available instead of exploding or pretending.
    """
    got = PIPE.sync([(episode["video"], episode["subtitle"])], vad=True)
    assert got[0].outcome == V.CONFIDENT
    assert any("B6" in n for n in got.notes)
    assert any("B6" in n for n in got[0].notes)


def test_vad_true_does_not_raise_MaskBandNotFitted(episode):
    got = PIPE.sync(API.scan(str(episode["root"])), vad=True)
    assert got.confident


# ===========================================================================
# 8. THE REPORT
# ===========================================================================

def test_the_summary_leads_with_what_went_wrong(episode, tmp_path):
    got = PIPE.sync([(episode["video"], episode["subtitle"]),
                     (str(tmp_path / "gone.mkv"), episode["subtitle"])])
    assert got.summary().startswith("1 ERROR")


def test_a_report_is_a_sequence_of_results(episode):
    u"""`05-interface.md` types this `list[Result]`. ⚠ Iterating it loses no
    DECISION -- every refusal is in the list -- which is why this one is
    iterable where `Scan` and `PairPlan` are not."""
    got = PIPE.sync([(episode["video"], episode["subtitle"])])
    assert len(got) == 1
    assert isinstance(list(got)[0], API.Result)
    assert got[0] is got.results[0]


def test_a_video_with_nothing_to_pair_is_unpaired_not_a_result(tmp_path):
    u"""⚠ It is not a pair, so it has no outcome -- `03-permissions.md` says
    there is no fourth. Inventing one would be a lie, and silence would be
    worse."""
    _write_mkv(tmp_path / "Show S01E09.mkv", MKV_CUES, duration_s=RUNTIME,
               per_cluster=4)
    _write_mkv(tmp_path / "Show S01E01.mkv", MKV_CUES, duration_s=RUNTIME,
               per_cluster=4)
    _write(tmp_path / "Show S01E01.ja.srt", _shifted(2.0))
    got = PIPE.sync(API.scan(str(tmp_path)))
    assert len(got.unpaired) == 1
    assert "S01E09" in got.unpaired[0][0]
    assert "1 video with no subtitle" in got.summary()


# ===========================================================================
# 9. CLUSTERS -- 09-corpus-strategy Stage 4, and the ms/s conversion
# ===========================================================================

def test_a_cluster_is_built_per_release_group_IN_ONE_FOLDER(tmp_path):
    u"""⭐ *One release group's episodes share a `tokenize()` shape.*

    🚨 THE FOLDER IS NOT ENOUGH, and the first version of this check hid that
    by putting each group in its OWN folder — so the folder component alone
    separated them and the title/group half was never exercised. In ONE folder
    — the ordinary downloads case — `_stem_title` strips the group and both
    became `Show`, so a broadcast rip and a web rip of every episode pooled
    into a single cluster at **coherence 0.50**, below the bar, and the
    escalation band's second signal stopped firing. Found by an adversarial
    pass.
    """
    d = tmp_path / "downloads"
    d.mkdir()
    measured = []
    for n in (1, 2, 3):
        for group, delay in (("Erai-raws", 2.0), ("shincaps", 10.0)):
            p = _write(d / (u"[%s] Show - %02d.ja.srt" % (group, n)),
                       _shifted(delay))
            measured.append(_fake_measured(p, offset=-delay))
    got = PIPE.clusters_for(measured)
    assert len(got) == 2, list(got)
    for cluster in got.values():
        assert cluster.size == 3
        # ⭐ Each source agrees with itself perfectly, which is the whole point.
        assert cluster.coherence == 1.0
        assert cluster.coheres is True


def test_two_groups_in_SEPARATE_folders_also_stay_apart(tmp_path):
    u"""⭐ The other half, kept: the folder is still part of the key, so the
    same group's episodes in two libraries do not pool either."""
    a = tmp_path / "erai"
    b = tmp_path / "shin"
    a.mkdir()
    b.mkdir()
    measured = []
    for n in (1, 2, 3):
        for folder in (a, b):
            p = _write(folder / (u"Show - %02d.ja.srt" % n), _shifted(2.0))
            measured.append(_fake_measured(p, offset=-2.0))
    got = PIPE.clusters_for(measured)
    assert len(got) == 2, list(got)
    assert all(c.size == 3 for c in got.values())
    # ⚠ MILLISECONDS. `arbitrate` owns that unit; `Fit` offsets are SECONDS,
    # and `LEDGER-HOT.md` records a lift written across that gap.
    assert all(abs(c.offset - (-2000.0)) < 1.0 for c in got.values())


def test_the_cluster_offsets_are_MILLISECONDS_not_seconds(tmp_path):
    m = [_fake_measured(_write(tmp_path / (u"Show - %02d.ja.srt" % n),
                               _shifted(1.5)), offset=-1.5)
         for n in (1, 2, 3)]
    cluster = list(PIPE.clusters_for(m).values())[0]
    assert cluster.offset == pytest.approx(-1500.0, abs=1.0)
    assert cluster.agrees_with(-1.5) is True
    assert cluster.agrees_with(-1500.0) is False


# ===========================================================================
# 9b. 🚨 CROSS-SLOT OWNERSHIP — the adversary's catastrophic case
# ===========================================================================

def _two_show_library(tmp_path):
    u"""Two shows using bare episode numbers — the shape that lost everything.

    The episode index correctly offers each video BOTH shows' same-numbered
    subtitle, and the foreign one is correctly REFUSED. What went wrong was
    afterwards.
    """
    root = tmp_path / "Anime"
    made = {}
    for show, starts in (("Alpha", CUE_STARTS),
                         ("Bravo", [3.3 + 7.8 * i for i in range(180)])):
        folder = root / show / "Season 1"
        folder.mkdir(parents=True)
        for ep in (1, 2):
            _write_mkv(folder / ("%02d.mkv" % ep),
                       [(t, 2.0) for t in starts], duration_s=RUNTIME,
                       per_cluster=4)
            made["%s/%02d" % (show, ep)] = _write(
                folder / ("%02d.ja.srt" % ep),
                _srt([t + 2.0 for t in starts]))
    return root, made


def test_a_TWO_SHOW_library_does_not_lose_every_subtitle(tmp_path,
                                                         monkeypatch):
    u"""🚨 THE WORST DEFECT 3b HAD, and default flags reached it.

    Two shows with bare episode numbers. Each video is offered both shows'
    `01.ja.srt`; the foreign one is correctly REFUSED — and `dedupe.plan`
    supersedes every non-winner **within its slot**, which is another slot's
    WINNER. Measured before the fix:

        summary: '2 synced'
        LOST from the library: Alpha/01.ja.srt Alpha/02.ja.srt
                               Bravo/01.ja.srt Bravo/02.ja.srt

    ⛔ `03-permissions.md`: a REFUSED pair is *"left untouched, reason
    stated"*. It was being moved. `dedupe.plan` cannot see this and should not
    have to — `sync()` is the only layer that sees the whole run.
    """
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    root, made = _two_show_library(tmp_path)
    got = PIPE.sync(API.scan(str(root)), write=True,
                    trash_root=str(tmp_path / "trash"))

    # ⛔ EVERY source subtitle is still exactly where the user left it.
    for label, path in sorted(made.items()):
        assert os.path.exists(path), "%s was lost: %s" % (label, path)
    # ⭐ And each show's own episodes were synced.
    assert len(got.written) == 4, [(r.video, r.output_path) for r in got]
    for r in got.written:
        assert os.path.dirname(r.output_path) == os.path.dirname(r.video)
    assert got.summary().startswith("4 synced") or "synced" in got.summary()


def test_a_refused_candidate_that_is_ANOTHER_videos_answer_is_never_trashed(
        tmp_path, monkeypatch):
    u"""⭐ Rule 1 of `_resolve_ownership`, isolated: a file some slot WRITES is
    never superseded by another slot. Asserted on the trash, not on a flag."""
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    root, made = _two_show_library(tmp_path)
    trash = tmp_path / "trash"
    got = PIPE.sync(API.scan(str(root)), write=True, trash_root=str(trash))
    assert not trash.exists() or not os.listdir(str(trash)), \
        os.listdir(str(trash))
    assert all(r.superseded == [] for r in got), [
        (r.subtitle, r.superseded) for r in got]


def test_TWO_RIPS_of_one_episode_SHARE_a_subtitle_and_both_get_one(
        tmp_path, monkeypatch):
    u"""⭐ RULED BY SONIC, 2026-09-09, and it widened this rule.

        *"It is not a new mechanism, it is arbitration widening from 'pick the
        best' to 'keep everyone who clears the bar and shares the episode key'.
        Two rips of one episode both align confidently, and that fact IS the
        evidence they are the same content. The rule does not change: the
        timing decides. What changes is that the answer may be a set."*

    Built first as *refuse both*, which threw away a correct answer on an
    ordinary library. ⛔ Sonic's condition is the one that matters: **each video
    gets its own alignment and its own offset, never a copied file** — *"two
    rips can differ by a trim, and writing one result twice would be a
    confidently wrong file."* `measure()` already runs per (video, subtitle)
    pair, so the two outputs are independently derived.
    """
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    d = tmp_path / "d"
    d.mkdir()
    for name in ("Show S01E01 [720p].mkv", "Show S01E01 [1080p].mkv"):
        _write_mkv(d / name, MKV_CUES, duration_s=RUNTIME, per_cluster=4)
    shared = _write(d / "Show S01E01.ja.srt", _shifted(2.0))

    got = PIPE.sync(API.scan(str(d)), write=True,
                    trash_root=str(tmp_path / "trash"))
    written = sorted(os.path.basename(r.output_path) for r in got.written)
    assert written == ["Show S01E01 [1080p].ja.srt",
                       "Show S01E01 [720p].ja.srt"], written
    # ⛔ The source is untouched, and it was never trashed.
    assert os.path.exists(shared)
    assert all(r.superseded == [] for r in got)
    # ⭐ Each output was derived independently — same offset here because the
    # rips are identical, but each came from its own alignment.
    assert len({r.offset for r in got.written}) == 1
    assert all(abs(r.offset - (-2.0)) < 0.05 for r in got.written)


def test_a_shared_source_is_never_WRITTEN_OVER_while_others_need_it(
        tmp_path, monkeypatch):
    u"""🚨 THE NARROW HAZARD THAT REMAINS, and it is an ORDERING one.

    `apply._render` re-reads the source at write time — correct in isolation,
    *"the file always wins"* — so a slot whose TARGET **is** the shared source
    mutates the bytes the other slots have not read yet. Measured before the
    guard: **−4.0 s applied for a true offset of −2.0 s**, both CONFIDENT, and
    under `rename=False` the user's only copy destroyed.

    ⭐ Only that one write is refused. The others go ahead — which is what
    Sonic's ruling requires and what *refuse both* got wrong.
    """
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    d = tmp_path / "d"
    d.mkdir()
    for name in ("Show S01E01.mkv", "Zeta S01E01.mkv"):
        _write_mkv(d / name, MKV_CUES, duration_s=RUNTIME, per_cluster=4)
    # ⚠ This subtitle's name matches ONE of the videos, so that video's output
    # path IS the source.
    shared = _write(d / "Show S01E01.ja.srt", _shifted(2.0))
    before = open(shared, "rb").read()

    got = PIPE.sync(API.scan(str(d)), write=True,
                    trash_root=str(tmp_path / "trash"))
    written = [os.path.basename(r.output_path) for r in got.written]
    assert written == ["Zeta S01E01.ja.srt"], written
    # ⛔ The shared source is byte-for-byte untouched.
    assert open(shared, "rb").read() == before
    assert any("write OVER" in n for r in got for n in r.notes), [
        r.notes for r in got]


def test_rename_false_with_a_SHARED_source_writes_nothing(tmp_path,
                                                          monkeypatch):
    u"""⭐ The extreme of the same rule: with `--no-rename` every slot's target
    IS the source, so there is one file and N different offsets. Every write is
    refused and the file is untouched."""
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    d = tmp_path / "d"
    d.mkdir()
    for name in ("Show S01E01 [720p].mkv", "Show S01E01 [1080p].mkv"):
        _write_mkv(d / name, MKV_CUES, duration_s=RUNTIME, per_cluster=4)
    _write(d / "Show S01E01.ja.srt", _shifted(2.0))
    before = _tree(tmp_path)

    got = PIPE.sync(API.scan(str(d)), write=True, rename=False,
                    trash_root=str(tmp_path / "trash"))
    assert got.written == [], [r.output_path for r in got.written]
    assert _tree(tmp_path) == before


def test_a_slot_whose_write_FAILED_trashes_nothing(tmp_path, monkeypatch):
    u"""🚨 *"Write first, trash second"* is an ORDER, and it was read as the
    whole rule. With every write failing, the trash loop still ran — nothing
    written, the survivor trashed, and the user left with **neither file**."""
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    d = tmp_path / "d"
    d.mkdir()
    _write_mkv(d / "Show S01E01.mkv", MKV_CUES, duration_s=RUNTIME,
               per_cluster=4)
    winner = _write(d / "[Erai-raws] Show - 01.ja.srt", _shifted(2.0))
    loser = _write(d / "[shincaps] Show - 01.ja.srt",
                   _srt([t + 2.0 for t in CUE_STARTS[:60]]))
    # ⛔ A DIRECTORY occupying the target makes every write fail.
    # ⚠ NOT a stray `.srt`: discovery classifies that as a CANDIDATE, so it
    # joins the slot, the target becomes a file the plan accounted for, and
    # the write SUCCEEDS by overwriting it. The first version of this fixture
    # did exactly that and was measuring a successful run.
    (d / "Show S01E01.ja.srt").mkdir()
    trash = tmp_path / "trash"

    got = PIPE.sync(API.scan(str(d)), write=True, trash_root=str(trash))
    assert os.path.exists(winner) and os.path.exists(loser)
    assert not trash.exists() or not os.listdir(str(trash))
    assert got.written == []
    # 🚨 And the run does not describe itself as a plan.
    assert got.failed, [(r.outcome, r.reason[:60]) for r in got]
    assert got.summary().startswith("1 NOT WRITTEN")
    assert "would sync" not in got.summary()


def test_a_write_that_FAILED_on_the_SCAN_path_says_so(tmp_path):
    u"""🚨 The correction was gated on `m.decision`, which only the EXPLICIT
    path sets — so on a scan a failed write produced a CONFIDENT result with an
    EMPTY reason, and a `write=True` run whose every write failed was
    byte-identical in its report to a dry run."""
    d = tmp_path / "d"
    d.mkdir()
    _write_mkv(d / "Show S01E01.mkv", MKV_CUES, duration_s=RUNTIME,
               per_cluster=4)
    _write(d / "[Erai-raws] Show - 01.ja.srt", _shifted(2.0))
    # ⚠ A DIRECTORY, not a stray `.srt` — see the fixture note above.
    (d / "Show S01E01.ja.srt").mkdir()

    dry = PIPE.sync(API.scan(str(d)), trash_root=str(tmp_path / "t"))
    wet = PIPE.sync(API.scan(str(d)), write=True,
                    trash_root=str(tmp_path / "t"))
    assert dry.summary() != wet.summary(), wet.summary()
    assert wet.failed and not dry.failed
    assert "NOT WRITTEN" in wet[0].reason
    assert wet[0].write_failed is True and dry[0].write_failed is False


def test_out_dir_MIRRORS_and_does_not_flatten(tmp_path):
    u"""🚨 `apply_plan`'s docstring names this obligation and assigns it to its
    caller — *"flattening collides the moment two shows both have an ep01;
    mirroring is the caller's job because only it knows the library root"* —
    and `sync()`, which IS that caller, returned `out_dir` verbatim.

    ⛔ The check named for the rule used a ONE-video fixture, so it asserted
    exactly what flattening looks like and could not fail. Found by an
    adversarial pass.
    """
    root, _made = _two_show_library(tmp_path)
    out = tmp_path / "out"
    out.mkdir()
    got = PIPE.sync(API.scan(str(root)), write=True, out_dir=str(out),
                    trash_root=str(tmp_path / "trash"))
    outs = [r.output_path for r in got.written]
    assert len(outs) == 4, [(r.video, r.output_path, r.outcome) for r in got]
    assert len(set(outs)) == 4, outs
    # ⭐ The library's shape is preserved under --out.
    rel = sorted(os.path.relpath(p, str(out)) for p in outs)
    assert rel == [os.path.join("Alpha", "Season 1", "01.ja.srt"),
                   os.path.join("Alpha", "Season 1", "02.ja.srt"),
                   os.path.join("Bravo", "Season 1", "01.ja.srt"),
                   os.path.join("Bravo", "Season 1", "02.ja.srt")], rel


def test_out_dir_with_rename_false_is_a_CONTRADICTION(episode, tmp_path):
    u"""⛔ `--rename` off means an in-place retime; `--out` means somewhere
    else. Together they produced the file `_out_dir_for` forbids: the
    release-group name, in a third folder, with the loser trashed anyway."""
    with pytest.raises(ValueError) as exc:
        PIPE.sync(API.scan(str(episode["root"])), write=True, rename=False,
                  out_dir=str(tmp_path / "out"))
    assert "contradict" in str(exc.value)


def test_TWO_explicit_pairs_for_one_slot_BOTH_come_back(episode, tmp_path):
    u"""🚨 The user asserted two pairs and got ONE Result — the other file was
    TRASHED and its verdict, reason and outcome never reached the caller.

    ⭐ `03-permissions.md`: a refusal is *left untouched, reason stated*.
    Dedupe still decides which one is WRITTEN, because two writes to one name
    is data loss; it no longer decides what is thrown away.
    """
    bad = _write(tmp_path / "bad.ja.srt", _srt(WRONG_STARTS))
    got = PIPE.sync([(episode["video"], episode["subtitle"]),
                     (episode["video"], bad)], write=True,
                    trash_root=str(tmp_path / "trash"))
    assert len(got) == 2, [(r.subtitle, r.outcome) for r in got]
    assert os.path.exists(bad), "an explicitly asserted pair was trashed"
    assert len(got.written) == 1
    assert {r.outcome for r in got} == {V.CONFIDENT, V.REFUSED}
    assert all(r.reason.strip() for r in got if r.outcome != V.CONFIDENT)


def test_a_SCAN_slot_is_still_ONE_result_however_many_candidates(tmp_path,
                                                                 monkeypatch):
    u"""⛔ THE OTHER HALF OF THE FIX ABOVE, and it is a regression this session
    nearly shipped.

    Making every asserted pair come back is right on the EXPLICIT path, where
    the user named each one. Applied to a scan it floods the report: the
    candidates are ours, not theirs, and `05-interface.md`'s ruled output is
    **one line per video** — a video with twenty candidates would produce
    twenty lines for one episode and bury the refusals the format exists to
    surface.

    ⭐ Found by reviewing the seam after fixing the explicit case; the fix for
    one finding had quietly broken a property documented three functions away.
    A candidate that simply lost a fair fight is `superseded`, not a line.
    """
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    d = tmp_path / "d"
    d.mkdir()
    _write_mkv(d / "Show S01E01.mkv", MKV_CUES, duration_s=RUNTIME,
               per_cluster=4)
    for group in ("Erai-raws", "SubsPlease", "shincaps", "Judas"):
        _write(d / (u"[%s] Show - 01.ja.srt" % group), _shifted(2.0))
    got = PIPE.sync(API.scan(str(d)), write=True,
                    trash_root=str(tmp_path / "trash"))
    assert len(got) == 1, [(r.subtitle, r.outcome) for r in got]
    assert len(got.written) == 1
    # ⭐ The three that lost are named on the winner, not as lines of their own.
    assert len(got[0].superseded) == 3, got[0].superseded


def test_force_marks_the_pair_it_ACTUALLY_overrode(episode, tmp_path):
    u"""🚨 `explicit.Decision` records `forced=bool(force)` on every decision it
    mints — correctly, it records how it was called. Reading it alone made all
    fifty pairs of a `--force` manifest report `forced=True` and the summary
    lead `50 FORCED`, so the marker for the most dangerous thing this tool does
    stopped identifying WHICH file it happened to."""
    good = episode["subtitle"]
    second = _write_mkv(tmp_path / "Zeta S01E01.mkv", MKV_CUES,
                        duration_s=RUNTIME, per_cluster=4)
    wrong = _write(tmp_path / "Zeta S01E01.ja.srt", _srt(WRONG_STARTS))
    got = PIPE.sync([(episode["video"], good), (str(second), wrong)],
                    write=True, force=True,
                    trash_root=str(tmp_path / "trash"))
    by_outcome = dict((r.outcome, r) for r in got)
    assert by_outcome[V.CONFIDENT].forced is False
    assert by_outcome[V.REFUSED].forced is True
    assert got.summary().startswith("1 FORCED")


# ===========================================================================
# 10. ⭐ THE INTEGRATION TEST RUNBOOK 3b ASKS FOR, IN surasura's SHAPE
# ===========================================================================

@pytest.fixture()
def surasura(tmp_path):
    u"""`05-interface.md`: *subtitles sitting in a folder alongside lots of
    `.txt` and other junk, videos in a separate location, results consumed
    programmatically as part of a content-creation pipeline.*"""
    videos = tmp_path / "media"
    subs = tmp_path / "downloads"
    videos.mkdir()
    subs.mkdir()
    for n in (1, 2, 3):
        _write_mkv(videos / (u"Show S01E%02d.mkv" % n), MKV_CUES,
                   duration_s=RUNTIME, per_cluster=4)
    # ⚠ The junk is the point. A refusal per `.txt` is noise a real refusal
    # then hides in.
    (subs / "notes.txt").write_text(u"nothing", encoding="utf-8")
    (subs / "release.nfo").write_text(u"scene", encoding="utf-8")
    (subs / "poster.jpg").write_bytes(b"\xff\xd8\xff\xe0junk")
    (subs / "archive.zip").write_bytes(b"PK\x03\x04junk")
    for n in (1, 2, 3):
        _write(subs / (u"[Erai-raws] Show - %02d.ja.srt" % n), _shifted(2.0))
    return {"root": tmp_path, "videos": videos, "subs": subs}


def test_surasura_gets_three_pairs_out_of_a_junk_filled_folder(surasura):
    got = PIPE.sync(API.scan(videos=str(surasura["videos"]),
                             subs=str(surasura["subs"])))
    assert len(got.confident) == 3, [(r.subtitle, r.outcome, r.reason)
                                     for r in got]
    assert got.unpaired == []
    assert all(r.lang == u"ja" for r in got.confident)


def test_the_written_file_lands_BESIDE_THE_VIDEO_in_two_folder_mode(surasura,
                                                                    monkeypatch):
    u"""🚨 THE WHOLE POINT OF RENAMING. `05-interface.md`: *media players
    auto-load a subtitle matching the video's basename* -- which requires it to
    be in the **video's** folder.

    `apply_plan` defaults to *the source's own folder*, which is right for a
    function that knows nothing about videos and wrong for `sync()`. Measured
    before the fix: `Show S01E01.ja.srt` written into `downloads/`, beside the
    `.txt` junk.
    """
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    got = PIPE.sync(API.scan(videos=str(surasura["videos"]),
                             subs=str(surasura["subs"])), write=True,
                    trash_root=str(surasura["root"] / "trash"))
    assert got.written
    for r in got.written:
        assert os.path.dirname(r.output_path) == os.path.dirname(r.video), (
            r.output_path, r.video)
        assert os.path.dirname(r.output_path) != os.path.dirname(r.subtitle)


def test_rename_false_keeps_the_subtitle_where_the_user_put_it(surasura,
                                                               monkeypatch):
    u"""⭐ The named exception. `--rename` off means *do not touch the name* --
    an in-place retime. A file put beside the video under its own
    release-group name would be neither renamed nor in place."""
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    got = PIPE.sync(API.scan(videos=str(surasura["videos"]),
                             subs=str(surasura["subs"])), write=True,
                    rename=False, trash_root=str(surasura["root"] / "trash"))
    assert got.written
    for r in got.written:
        assert r.output_path == r.subtitle


def test_the_library_PRINTS_NOTHING(surasura, capsys):
    u"""⛔ `05-interface.md` constraint 3: *returns structured results. Prints
    nothing. Writes nothing unless told.*

    ⭐ A stray `print` in a library is not cosmetic -- surasura consumes this
    as a module inside a content pipeline, where stdout is somebody else's
    data channel.
    """
    scan_result = API.scan(videos=str(surasura["videos"]),
                           subs=str(surasura["subs"]))
    PIPE.sync(scan_result, write=True,
              trash_root=str(surasura["root"] / "trash"))
    captured = capsys.readouterr()
    assert captured.out == "", captured.out
    assert captured.err == "", captured.err


def test_the_whole_run_is_byte_for_byte_inert_without_write(surasura):
    before = _tree(surasura["root"])
    got = PIPE.sync(API.scan(videos=str(surasura["videos"]),
                             subs=str(surasura["subs"])))
    assert got.confident, "the fixture must align, or this proves nothing"
    assert _tree(surasura["root"]) == before


def test_with_write_it_produces_exactly_the_three_files_and_no_others(
        surasura, monkeypatch):
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    before = set(_tree(surasura["root"]))
    got = PIPE.sync(API.scan(videos=str(surasura["videos"]),
                             subs=str(surasura["subs"])), write=True,
                    trash_root=str(surasura["root"] / "trash"))
    after = set(_tree(surasura["root"]))
    # 🚨 RELATIVE PATHS, NOT BASENAMES. The first version compared basenames
    # and was green while every file landed in the DOWNLOADS folder, beside
    # the `.txt` junk, where no player will ever look -- the tool renamed
    # perfectly and achieved nothing. `doctrine/verification` §shape vs
    # substance: ask the second question, *and is it where it has to be?*
    new = sorted(os.path.relpath(p, str(surasura["root"]))
                 for p in after - before)
    assert new == [os.path.join("media", "Show S01E01.ja.srt"),
                   os.path.join("media", "Show S01E02.ja.srt"),
                   os.path.join("media", "Show S01E03.ja.srt")], new
    # ⛔ AND THE JUNK IS UNTOUCHED. `doctrine/robustness`: a destructive tool's
    # first dry run is a design review, and this is the same question asked of
    # a real one -- what did it touch that nobody asked it to?
    for name in ("notes.txt", "release.nfo", "poster.jpg", "archive.zip"):
        assert os.path.exists(str(surasura["subs"] / name)), name
    assert len(got.written) == 3


def test_ONE_FOLDER_mode_converges_and_never_trashes_its_own_output(
        tmp_path, monkeypatch):
    u"""🚨 THE SECOND RUN SEES ITS OWN OUTPUT AS A COMPETING CANDIDATE, and
    what it does with it is not obvious.

    Measured over three runs: run 1 writes `Show S01E01.ja.srt` and leaves the
    original; runs 2 and 3 are byte-identical to run 2. Nothing is ever
    trashed and nothing is lost.

    ⭐ AND IT CONVERGES TO **ONE** SUBTITLE, which is what `05-interface.md`
    rules: *keep one subtitle per (video × language); every other candidate for
    that slot goes to trash.* Run 1 writes the canonical name and leaves the
    source; run 2 recognises the canonical file as the winner and sends the
    stale original to the **trash** — recoverable, never deleted; run 3 changes
    nothing.

    🚨 THAT TOOK A RULING. Dedupe rule 3 is *higher cue count and **wider
    runtime coverage***, and a subtitle retimed by a NEGATIVE offset has every
    cue earlier — so its content ends earlier and it read as *less* coverage
    than the stale source it was made from. The output ranked below its own
    source **forever**, so every run re-did the work and kept both files.
    ⭐ Sonic ruled rule 5 promoted, and the measurement narrowed it: above
    `content_end` (which a negative offset lowers on every sync) and **not**
    above `cues` — promoted above both, a 10-cue file beat a 900-cue one.

    ⭐ AND FROM RUNBOOK 3a-bis, RUN 3 NO LONGER DOES THE WORK AT ALL: the
    results DB recognises the folder as already in sync and nothing is opened.
    🚨 Run 2 still does, and that is the whole design of `Record.stable` --
    run 1 wrote a file it had never weighed against anything, so the folder was
    not finished. A store that called run 1 settled would skip run 2 and leave
    BOTH subtitles in the folder for ever, defeating the ruling above with the
    cache meant to make it cheap. Measured that way once, while it was built.
    """
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    folder = tmp_path / "Show S01"
    folder.mkdir()
    _write_mkv(folder / "Show S01E01.mkv", MKV_CUES, duration_s=RUNTIME,
               per_cluster=4)
    original = _write(folder / "[Erai-raws] Show - 01.ja.srt", _shifted(2.0))
    trash = str(tmp_path / "trash")

    first = PIPE.sync(API.scan(str(folder)), write=True, trash_root=trash)
    assert len(first.written) == 1
    after_first = _tree(tmp_path)

    second = PIPE.sync(API.scan(str(folder)), write=True, trash_root=trash)
    after_second = _tree(tmp_path)
    third = PIPE.sync(API.scan(str(folder)), write=True, trash_root=trash)

    # ⭐ Converged: run 3 changed nothing run 2 had not already settled.
    assert _tree(tmp_path) == after_second
    # ⭐ ONE subtitle in the folder, at the name a player loads.
    left = sorted(n for n in os.listdir(str(folder)) if n.endswith(".srt"))
    assert left == ["Show S01E01.ja.srt"], left
    # ⛔ AND THE ORIGINAL IS IN THE TRASH, NOT GONE. Nothing this tool does may
    # be unrecoverable.
    assert not os.path.exists(original)
    assert os.path.basename(original) in os.listdir(trash), os.listdir(trash)
    # 🚨 `superseded` names what actually MOVED, never what the plan intended.
    assert second.written[0].superseded == [original]
    assert len(after_second) == len(after_first)
    # ⭐ RUN 3 IS THE CHEAP ONE, AND IT SAYS SO OUT LOUD. ⛔ Nothing written
    # is not the same as nothing reported: a run that quietly produced an empty
    # report over a finished folder is indistinguishable from one that broke.
    assert third.written == []
    assert [v for v, _why in third.settled] == [
        str(folder / "Show S01E01.mkv")], third.settled
    assert u"already in sync" in third.summary(), third.summary()


def test_a_run_that_was_ENTIRELY_SETTLED_does_not_report_a_plan():
    u"""🚨 *"0 would sync"* OVER A FOLDER THAT IS ALREADY IN SYNC IS A LIE ABOUT
    A DECISION.

    `would sync` is the dry-run voice: *here is what I would do.* A run that
    measured nothing because the results DB recognised every video did not
    consider anything and decline it — it did not consider anything at all.
    ⛔ The two are different claims and a user reading the first goes looking
    for the pairs the tool rejected.

    ⭐ Found by LOOKING at a real run at RUNBOOK 3c, not by a check.
    ⚠ And only when there are NO results: a run that settled some videos and
    measured others still owes both counts.
    """
    settled = [(u"/lib/Show S01E01.mkv", u"already in sync")]
    empty = PIPE.SyncReport([], settled=settled)
    assert empty.summary() == u"1 already in sync", empty.summary()
    assert u"would sync" not in empty.summary()

    # ⚠ THE CONTROL: with something actually measured, both halves are owed.
    mixed = PIPE.SyncReport([_a_confident_result()], settled=settled)
    assert u"would sync" in mixed.summary(), mixed.summary()
    assert u"1 already in sync" in mixed.summary(), mixed.summary()


def _a_confident_result():
    return API.Result(u"/lib/Show S01E02.mkv", u"/lib/b.ja.srt", V.CONFIDENT,
                      verdict_word=u"locked", segments=[(None, -1.0)],
                      match_rate=0.9)


def test_a_second_run_over_its_own_output_is_IDEMPOTENT(surasura, monkeypatch):
    u"""🚨 `LEDGER-HOT.md`, the `.und.` defect: a namer that is not idempotent
    renames the whole library again on every run. Here the second pass meets
    files this tool wrote, and must not churn them."""
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    trash = str(surasura["root"] / "trash")
    PIPE.sync(API.scan(videos=str(surasura["videos"]),
                       subs=str(surasura["subs"])), write=True,
              trash_root=trash)
    after_first = _tree(surasura["root"])
    PIPE.sync(API.scan(videos=str(surasura["videos"]),
                       subs=str(surasura["subs"])), write=True,
              trash_root=trash)
    after_second = _tree(surasura["root"])
    assert set(after_second) == set(after_first), (
        sorted(set(after_second) ^ set(after_first)))


class _FakeFit(object):
    u"""⚠ `measurable` IS PART OF THE SHAPE, not decoration. `clusters_for`
    now refuses to let an unmeasurable fit vote, so a double without it is a
    double that cannot exercise the rule."""

    def __init__(self, offset, measurable=True):
        self.single = (offset, 0.9)
        self.segments = [(None, offset)]
        self.measurable = measurable


def _fake_measured(path, offset, measurable=True):
    return PIPE._Measured("/x/v.mkv", path,
                          fit=_FakeFit(offset, measurable=measurable))


def test_an_UNMEASURABLE_fit_does_not_vote_in_a_cluster(tmp_path):
    u"""🚨 THE DEFECT: every measured pair voted, including ones
    `Fit.measurable` says cannot be scored at all. Measured on four episodes
    each carrying one correct subtitle and one wrong one, coherence fell from
    **1.00 to 0.57 — under the 0.60 bar** — so a video's REJECTED candidates
    stopped the cluster vouching for the correct pairs beside it, and the pair
    that lost was the weak-but-correct one in the escalation band this whole
    mechanism exists to rescue.

    ⭐ `Fit.excess` was already zeroed for exactly this reason; `_own_offset`
    reads `single[0]`, which is not. Found twice — by reading one rendered run,
    and by an adversarial pass that watched the lift go CONFIDENT -> REFUSED.
    """
    good = [_fake_measured(_write(tmp_path / (u"Show - %02d.ja.srt" % n),
                                  _shifted(2.0)), offset=-2.0)
            for n in (1, 2, 3, 4)]
    noise = [_fake_measured(_write(tmp_path / (u"Show - %02d.en.srt" % n),
                                   _shifted(8.8)), offset=-8.8,
                            measurable=False)
             for n in (1, 2, 3, 4)]

    clusters = PIPE.clusters_for(good + noise)
    assert len(clusters) == 1, list(clusters)
    cluster = list(clusters.values())[0]
    assert cluster.size == 4, cluster.offsets
    assert cluster.coherence == 1.0
    assert cluster.coheres is True
    assert all(abs(o - (-2000.0)) < 1.0 for o in cluster.offsets), \
        cluster.offsets

    # ⭐ The control: had they voted, the cluster would fall under the bar and
    # stop lifting anything. This is what the shipped code used to do.
    everyone = PIPE.clusters_for(
        good + [_fake_measured(m.subtitle, -8.8) for m in noise])
    diluted = list(everyone.values())[0]
    assert diluted.coherence < _ARB.COHERENCE_ACCEPT, diluted.coherence
    assert diluted.coheres is False


def test_a_cluster_is_keyed_on_the_SEASON_too(tmp_path):
    u"""🚨 `LEDGER-HOT.md` records *never group on episode alone — multi-season
    shows collide* as made FOUR times on the pairing side. The clustering side
    had the same hole: `Show S01E01` and `Show S02E01` in one folder pooled
    into a single cluster, and `series.normalize` folds `Gintama` and
    `Gintama'` — four real seasons — to one key."""
    for season, delay in ((1, 2.0), (2, 9.0)):
        for ep in (1, 2, 3):
            _fake_measured(_write(
                tmp_path / (u"Show S%02dE%02d.ja.srt" % (season, ep)),
                _shifted(delay)), offset=-delay)
    measured = []
    for season, delay in ((1, 2.0), (2, 9.0)):
        for ep in (1, 2, 3):
            measured.append(_fake_measured(
                str(tmp_path / (u"Show S%02dE%02d.ja.srt" % (season, ep))),
                offset=-delay))
    clusters = PIPE.clusters_for(measured)
    assert len(clusters) == 2, list(clusters)
    assert sorted(c.size for c in clusters.values()) == [3, 3]
    assert all(c.coherence == 1.0 for c in clusters.values())


# ===========================================================================
# 🚨 ABSOLUTE NUMBERING -- AND THE FILES THAT MUST SURVIVE IT
# ===========================================================================

def test_the_absolute_numbering_fallback_never_trashes_a_guess(tmp_path):
    u"""🚨 THE CHECK THAT PROVES A REAL USER'S FILES SURVIVE.

    Reported by Sonic, 2026-09-10: `[SubsPlease] Hell Mode S2 - 10` and
    `ヘルモード…S02E22…ABEMA.ja[cc].srt` are the same episode, and nothing was
    ever offered for the video — ABEMA writes a per-season SEASON tag with an
    ABSOLUTE episode number.

    The fallback offers the whole season on that hypothesis, and one of them
    wins. ⛔ **The losers are subtitles for episodes the user has no video
    for**, and `dedupe.plan` supersedes every non-winner. Without the
    speculative exemption this run sends E17 and E18 to the trash.

    ⭐ THIS IS THE ONLY CHECK THAT CAN SEE THE SEAM. `test_dedupe`'s version
    sets `speculative` by hand, so it is structurally blind to the flag being
    dropped between `measure()` — which takes two PATHS — and the slot. A
    mutant that dropped it there survived every dedupe check and is killed
    here.
    """
    lib = tmp_path / u"Hell Mode"
    lib.mkdir()
    _write_mkv(lib / u"Hell Mode S02E10.mkv", MKV_CUES,
               duration_s=RUNTIME, per_cluster=4)
    # ⚠ DISJOINT NUMBERING: video {10}, subtitles {17, 18, 22}. Nothing shared,
    # which is what a difference in numbering SCHEME looks like from outside.
    for episode in (17, 18, 22):
        _write(lib / (u"Hell Mode S02E%d.ja.srt" % episode), _shifted(2.0))

    before = _tree(lib)
    report = PIPE.sync(API.scan(str(lib)), write=True,
                       trash_root=str(tmp_path / u"trash"), results=False)

    # ⭐ Something was measured -- a run that offered nothing would pass every
    # assertion below by doing nothing at all.
    assert report.results, u"the fallback offered nothing: %s" % report.summary()

    after = _tree(lib)
    for path in before:
        assert path in after, (
            u"%s was taken from the library -- a subtitle for an episode the "
            u"user has no video for" % os.path.basename(path))

    trash = tmp_path / u"trash"
    in_trash = list(trash.rglob(u"*")) if trash.exists() else []
    assert [p for p in in_trash if p.is_file()] == [], (
        u"a speculative loser was trashed: %s"
        % [p.name for p in in_trash if p.is_file()])


def test_a_gap_in_an_AGREEING_library_is_still_reported_unpaired(tmp_path):
    u"""⛔ THE CONTROL, AND IT GUARDS A SIGNAL THE FIRST DESIGN DESTROYED.

    `Scan.unpaired`'s own docstring: *a folder with 24 videos and 20 subtitles
    has four of these and is working perfectly.* The first trigger fired
    wherever a video was offered nothing, which is that ordinary state — it
    would have spent an alignment per candidate rediscovering that a subtitle
    is absent, and reported no gaps at all.
    """
    _write_mkv(tmp_path / u"Show S01E01.mkv", MKV_CUES,
               duration_s=RUNTIME, per_cluster=4)
    _write_mkv(tmp_path / u"Show S01E09.mkv", MKV_CUES,
               duration_s=RUNTIME, per_cluster=4)
    _write(tmp_path / u"Show S01E01.ja.srt", _shifted(2.0))

    report = PIPE.sync(API.scan(str(tmp_path)), results=False)
    assert len(report.unpaired) == 1, report.unpaired
    assert u"E09" in report.unpaired[0][0]
