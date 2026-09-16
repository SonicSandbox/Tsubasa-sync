# -*- coding: utf-8 -*-
u"""
The library API -- RUNBOOK step 3b. Authority: `05-interface.md` §*The library
API*, `03-permissions.md` §*The three outcomes*.

===========================================================================
🚨 THIS IS THE STEP WHERE THE STACK BECOMES A PRODUCT.
===========================================================================

Everything under it was green and UNREACHABLE: `verdict()`,
`movies.pair_movies()`, `explicit.explicit_pairs()`, `dedupe.plan()` and
`apply.apply_plan()` were all mutation-proved and could not be called from
outside a test. So the checks here are weighted towards the SEAMS, which is
where the 2026-09-09 adversarial pass found its worst findings: a public
function trusting an upstream gate, a dead parameter, an output name taken
from the wrong layer.

⭐ THE THREE THAT MATTER MOST, and each is a whole class:

  1. `scan()` OPENS NOTHING. Asserted by making `open()` raise for any path
     inside the scanned tree -- not by trusting the code to have no reads in
     it, which is a claim about today's source and not about the contract.
  2. `sync()` ON TUPLES GOES THROUGH `explicit_pairs()`. Ruled 2026-09-08 and
     binding: *"a tuple path that silently skips every refusal is the one
     shape the whole project exists to prevent."* Asserted by feeding it the
     refusals A11 exists for and requiring each one back.
  3. NOTHING IS WRITTEN unless `write=True` -- checked by comparing the whole
     tree's bytes before and after, not by reading a flag.
"""
import io
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import tsubasa                                                # noqa: E402
from tsubasa import api as API                                # noqa: E402
from tsubasa import discover as DISC                          # noqa: E402
from tsubasa import duration as DUR                           # noqa: E402
from tsubasa import verdict as V                              # noqa: E402
from tsubasa.naming import series as SERIES                   # noqa: E402

# ⚠ Reached through the module, never imported by name. `from tsubasa.api
# import scan` binds the name HERE at import time, so a mutation rebinding
# `tsubasa.api.scan` would never reach this file -- three mutants survived
# checks written that way at 3a before the rule was written down.


# ---------------------------------------------------------------------------
# fixtures -- a folder that looks like somebody's actual library
# ---------------------------------------------------------------------------

SRT = (u"1\n00:00:%02d,000 --> 00:00:%02d,500\nline\n\n")


def _srt(starts):
    u"""An SRT with a cue starting at each of `starts` (seconds).

    ⚠ Built from an explicit table, never a format string over a range --
    `LEDGER-HOT.md`: an ASCII fixture cannot test an encoding rule, and the
    same trap has produced two green worthless checks in this project. Here
    the content is deliberately ASCII and the checks that need otherwise say so.
    """
    out = []
    for i, t in enumerate(starts):
        out.append(u"%d\n%s --> %s\nline %d\n\n"
                   % (i + 1, _stamp(t), _stamp(t + 1.5), i + 1))
    return u"".join(out)


def _stamp(seconds):
    ms = int(round(seconds * 1000.0))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return u"%02d:%02d:%02d,%03d" % (h, m, s, ms)


def _write(path, text):
    with io.open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text)
    return path


@pytest.fixture()
def library(tmp_path):
    u"""surasura's real case: videos in one place, subtitles in another,
    and the subtitle folder full of junk.

    `05-interface.md`: *subtitles sitting in a folder alongside lots of `.txt`
    and other junk, videos in a separate location.*
    """
    videos = tmp_path / "videos"
    subs = tmp_path / "subs"
    videos.mkdir()
    subs.mkdir()

    for n in (1, 2, 3):
        (videos / (u"Katainaka no Ossan S02E%02d.mkv" % n)).write_bytes(b"\x1aE\xdf\xa3junk")
    # ⚠ JUNK IS EXPECTED INPUT, NOT AN ERROR. Three shapes: a plain text file,
    # an archive, and a note. None may become a candidate and none may raise.
    (subs / "notes.txt").write_text(u"nothing to see", encoding="utf-8")
    (subs / "release.nfo").write_text(u"scene info", encoding="utf-8")
    (subs / "cover.jpg").write_bytes(b"\xff\xd8\xff\xe0junk")
    for n in (1, 2, 3):
        _write(str(subs / (u"[Erai-raws] Katainaka no Ossan - %02d.ja.srt" % n)),
               _srt([10.0 + n, 40.0 + n, 70.0 + n, 100.0 + n, 130.0 + n]))
    return {"root": tmp_path, "videos": videos, "subs": subs}


# ---------------------------------------------------------------------------
# scan -- what it finds
# ---------------------------------------------------------------------------

def test_scan_finds_the_videos_and_the_subtitles(library):
    got = API.scan(videos=str(library["videos"]), subs=str(library["subs"]))
    assert len(got.videos) == 3
    assert len(got.subtitles) == 3


def test_scan_ignores_junk_silently(library):
    u"""⛔ `05-interface.md` constraint 2. Junk is expected input."""
    got = API.scan(videos=str(library["videos"]), subs=str(library["subs"]))
    names = {s.name for s in got.subtitles}
    assert not any(n.endswith((".txt", ".nfo", ".jpg")) for n in names)
    # ⚠ And it did not merely refuse them -- it did not mention them at all.
    # A refusal for every `.txt` in a working folder is noise the user has to
    # read past, which is how a real refusal gets skipped.
    assert not any(p.endswith((".txt", ".nfo", ".jpg")) for p in got.skipped)


def test_scan_takes_one_folder_for_both(library):
    u"""`scan("/media/anime/s2")` -- the commonest case, positionally."""
    both = library["root"] / "both"
    both.mkdir()
    (both / "Show S01E01.mkv").write_bytes(b"\x1aE\xdf\xa3junk")
    _write(str(both / "Show S01E01.ja.srt"), _srt([1.0, 2.0, 3.0]))
    got = API.scan(str(both))
    assert len(got.videos) == 1 and len(got.subtitles) == 1
    assert len(got.for_video(got.videos[0])) == 1


def test_scan_takes_explicit_lists_of_paths(library):
    u"""`05-interface.md`: *takes paths OR iterables of paths.*"""
    vs = sorted(str(p) for p in library["videos"].iterdir())
    ss = sorted(str(p) for p in library["subs"].glob("*.srt"))
    got = API.scan(videos=vs, subs=ss)
    assert len(got.videos) == 3 and len(got.subtitles) == 3


def test_a_bare_string_is_ONE_root_not_a_list_of_characters(library):
    u"""⚠ `scan("/media")` must not iterate into `/`, `m`, `e`, ..."""
    assert API._as_roots("/media/anime") == ("/media/anime",)
    assert API._as_roots(["/a", "/b"]) == ("/a", "/b")


def test_the_subtitle_folder_never_contributes_a_VIDEO(library):
    u"""🚨 A stray `.mkv` in the subtitle folder is not something to sync.

    Without this, two-folder mode means nothing: `--subs` would widen the
    video side as well and the user would find an episode they never asked
    about being retimed.
    """
    (library["subs"] / "stray.mkv").write_bytes(b"\x1aE\xdf\xa3junk")
    got = API.scan(videos=str(library["videos"]), subs=str(library["subs"]))
    assert len(got.videos) == 3
    assert not any(v.name == "stray.mkv" for v in got.videos)


def test_the_video_folder_never_contributes_a_SUBTITLE(library):
    u"""The other half of the same rule, and it is not symmetric by accident:
    a `.srt` beside the videos in two-folder mode is somebody else's."""
    _write(str(library["videos"] / "Katainaka no Ossan S02E01.en.srt"),
           _srt([1.0, 2.0, 3.0]))
    got = API.scan(videos=str(library["videos"]), subs=str(library["subs"]))
    assert len(got.subtitles) == 3
    assert not any(s.name.endswith(".en.srt") for s in got.subtitles)


def test_no_recurse_stops_at_the_named_directory(library):
    deep = library["subs"] / "extras" / "deeper"
    deep.mkdir(parents=True)
    _write(str(deep / "Katainaka no Ossan - 01.ja.srt"), _srt([1.0, 2.0]))

    wide = API.scan(videos=str(library["videos"]), subs=str(library["subs"]))
    narrow = API.scan(videos=str(library["videos"]), subs=str(library["subs"]),
                      recurse=False)
    assert len(wide.subtitles) == 4
    assert len(narrow.subtitles) == 3


def test_scan_with_nowhere_to_look_refuses_loudly():
    u"""⛔ Not an empty scan. A caller that asked for a scan and got a silent
    no-op believes it ran (`doctrine/robustness`)."""
    with pytest.raises(ValueError) as exc:
        API.scan()
    assert "somewhere to look" in str(exc.value)


# ---------------------------------------------------------------------------
# 🚨 scan() OPENS NOTHING
# ---------------------------------------------------------------------------

def test_scan_opens_no_file_inside_the_tree_it_was_given(library, monkeypatch):
    u"""🚨 The contract `RUNBOOK.md` 3b states, asserted as a contract.

    ⭐ Not *"there is no read in the source"* -- that is a claim about today's
    code. This makes `open()` RAISE for any path inside the scanned tree, so
    the next person who adds a container read here finds out immediately.

    ⚠ Scoped to the tree, deliberately: the alias table and the decoration
    vocabulary are bundled data files this project opens whenever it likes,
    and forbidding those would make the check about the wrong thing.
    """
    root = os.path.normcase(os.path.abspath(str(library["root"])))
    real_open = io.open
    opened = []

    def _guard(path, *a, **kw):
        try:
            here = os.path.normcase(os.path.abspath(str(path)))
        except (TypeError, ValueError):
            return real_open(path, *a, **kw)
        if here.startswith(root):
            opened.append(here)
            raise AssertionError(
                "scan() opened %s. RUNBOOK 3b: scan() returns candidate sets "
                "with no media I/O -- every read belongs in sync()." % path)
        return real_open(path, *a, **kw)

    monkeypatch.setattr(io, "open", _guard)
    monkeypatch.setattr("builtins.open", _guard)
    got = API.scan(videos=str(library["videos"]), subs=str(library["subs"]))
    # ⚠ The scan is lazy in places, so DRAIN it: a check that never asked for
    # the candidates would pass against a `for_video` that opens every file.
    for video in got.videos:
        got.for_video(video)
    got.pairings()
    got.unpaired()
    got.summary()
    assert not opened


def test_the_open_guard_can_actually_fail(library, monkeypatch):
    u"""⭐ The control for the check above. A guard that cannot fire is a green
    check that proves nothing -- `doctrine/verification`: break the fix and
    watch the test fail."""
    root = os.path.normcase(os.path.abspath(str(library["root"])))
    real_open = io.open

    def _guard(path, *a, **kw):
        here = os.path.normcase(os.path.abspath(str(path)))
        if here.startswith(root):
            raise AssertionError("opened %s" % path)
        return real_open(path, *a, **kw)

    monkeypatch.setattr(io, "open", _guard)
    monkeypatch.setattr("builtins.open", _guard)
    with pytest.raises(AssertionError):
        io.open(str(library["subs"] / "notes.txt"), "r")


# ---------------------------------------------------------------------------
# ranking -- ⚠ named so the winner sorts LAST under every lower key
# ---------------------------------------------------------------------------

def test_candidates_are_ranked_by_identity_first(tmp_path):
    u"""🚨 `LEDGER-HOT.md`: *a ranking check is rescued by its own lower
    tiebreaks.* Two mutants deleting the rule under test survived checks named
    after it, because the path tiebreak ordered the fixtures correctly anyway.

    ⭐ So the expected winner here loses EVERY lower key: its path sorts LAST
    and it sits in a different directory from the video, so its proximity is
    worse than the decoy's. Only the identity rule can put it first.

    ⚠ The rank is made to lose through the DIRECTORY name, not the filename.
    The first version prefixed the winner with `zzz ` -- which the parser reads
    as part of the title, so `zzz Katainaka no Ossan` against
    `Katainaka no Ossan` came back UNSURE and the fixture had destroyed the
    very signal it was built to isolate.
    """
    videos = tmp_path / "v"
    far = tmp_path / "zzz"
    videos.mkdir()
    far.mkdir()
    (videos / "Katainaka no Ossan S01E01.mkv").write_bytes(b"\x1aE\xdf\xa3x")
    # decoy: same folder (proximity 1.0), path sorts first, WRONG show
    _write(str(videos / "Completely Different Show S01E01.ja.srt"),
           _srt([1.0, 2.0]))
    # winner: a sibling tree (proximity 0.5), path sorts last, RIGHT show
    _write(str(far / "Katainaka no Ossan S01E01.ja.srt"), _srt([1.0, 2.0]))

    got = API.scan(videos=str(videos), subs=[str(videos), str(far)])
    ranked = got.for_video(got.videos[0])
    assert len(ranked) == 2, [c.subtitle.name for c in ranked]
    assert ranked[0].subtitle.path.startswith(str(far))
    assert ranked[0].identity == SERIES.SAME
    # ⭐ Both lower keys point the OTHER way, so only identity can have decided.
    assert ranked[0].proximity < ranked[1].proximity
    assert ranked[0].subtitle.path > ranked[1].subtitle.path


def test_a_DIFFERENT_title_is_ranked_last_and_never_dropped(tmp_path):
    u"""⚠ `RUNBOOK.md` Track A: *DIFFERENT is not terminal below the fan-out
    budget -- 9.9% of real pairs are DIFFERENT-by-title and right.* A Japanese
    folder name against an English release name reaches DIFFERENT honestly,
    and timing is what settles it.

    🚨 THIS CHECK PROVED NEITHER HALF OF ITS NAME. An adversarial pass replayed
    its fixture: **one** candidate (so nothing was "last" of anything), and an
    assertion admitting `UNSURE` -- which is exactly what it got, so
    `DIFFERENT` never appeared in it at all. The mutant it was named for was
    killed by a *different* check that happened to have a wrong-show decoy.

    ⭐ Now: two candidates, one measurably `DIFFERENT`, and the DIFFERENT one is
    required to be **present and last** -- and it sorts FIRST by path, so
    nothing but the identity rank can put it there.
    """
    d = tmp_path / "d"
    d.mkdir()
    (d / "Katainaka no Ossan S01E01.mkv").write_bytes(b"\x1aE\xdf\xa3x")
    _write(str(d / "Aaa Completely Different Show S01E01.en.srt"),
           _srt([1.0, 2.0]))
    _write(str(d / "Zzz Katainaka no Ossan S01E01.ja.srt"), _srt([1.0, 2.0]))
    got = API.scan(str(d))
    ranked = got.for_video(got.videos[0])
    assert len(ranked) == 2, [c.subtitle.name for c in ranked]
    assert ranked[-1].identity == SERIES.DIFFERENT, [
        (c.subtitle.name, c.identity) for c in ranked]
    # ⛔ Present, not dropped -- and it sorts first by path, so only the
    # identity rank could have moved it to the back.
    assert ranked[-1].subtitle.path < ranked[0].subtitle.path


def test_follow_links_is_not_a_DEAD_parameter(tmp_path, monkeypatch):
    u"""🚨 An adversarial pass found `follow_links` unexercised by any check —
    it could have been dropped from the call entirely and nothing would have
    said so.

    ⚠ Asserted as WIRING rather than by building a symlink: a symlink needs
    privileges on Windows, so a behavioural check would SKIP on the machine
    this is developed on, which is the same as not existing. What can be
    guaranteed everywhere is that the flag reaches the walker.
    """
    d = tmp_path / "d"
    d.mkdir()
    (d / "Show S01E01.mkv").write_bytes(b"\x1aE\xdf\xa3x")
    seen = []
    real = DISC.walk
    monkeypatch.setattr(DISC, "walk",
                        lambda roots, **kw: (seen.append(kw) or
                                             real(roots, **kw)))
    API.scan(str(d), follow_links=True)
    assert seen and all(kw.get("follow_links") is True for kw in seen), seen
    seen[:] = []
    API.scan(str(d))
    assert seen and all(kw.get("follow_links") is False for kw in seen), seen


def test_ties_are_broken_by_PATH_not_by_discovery_order(tmp_path):
    u"""🚨 THE CHECK BELOW CANNOT FAIL FROM DELETING THE TIEBREAK, and this one
    can. Found by the mutation probe: with two candidates tied on identity,
    score and proximity, Python's sort is STABLE, so removing the path key
    leaves them in discovery order -- which is itself deterministic, so
    running the scan twice agrees either way.

    ⭐ So the mechanism is pinned by making discovery order and path order
    DISAGREE: the roots are handed over in the order `b`, `a` while the files
    sort `a`, `b`. Only the path tiebreak can produce `a` first.
    """
    videos = tmp_path / "v"
    a_dir = tmp_path / "aaa"
    b_dir = tmp_path / "bbb"
    for d in (videos, a_dir, b_dir):
        d.mkdir()
    (videos / "Show S01E01.mkv").write_bytes(b"\x1aE\xdf\xa3x")
    # Identical on identity, score and proximity: same title, both a sibling
    # tree of the video's folder. The ONLY thing separating them is the path.
    _write(str(a_dir / "Show S01E01.ja.srt"), _srt([1.0, 2.0]))
    _write(str(b_dir / "Show S01E01.ja.srt"), _srt([1.0, 2.0]))

    got = API.scan(videos=str(videos), subs=[str(b_dir), str(a_dir)])
    assert [os.path.basename(os.path.dirname(s.path))
            for s in got.subtitles] == ["bbb", "aaa"], "discovery order"
    ranked = got.for_video(got.videos[0])
    assert len(ranked) == 2
    assert ranked[0].identity == ranked[1].identity
    assert ranked[0].proximity == ranked[1].proximity
    assert os.path.basename(os.path.dirname(ranked[0].subtitle.path)) == "aaa"


def test_the_ranking_is_stable_between_runs(tmp_path):
    u"""⚠ Two candidates identical on every real signal must not swap places:
    a re-run would rename a different file.

    🚨 IT NEEDS REAL FAN-OUT AND THE FIRST VERSION DID NOT HAVE IT. Written
    against the `library` fixture, every video had exactly ONE candidate --
    so there was nothing to reorder and a `rank_key` returning
    `random.random()` SURVIVED. `LEDGER-HOT.md`'s *a negative control that
    draws uniformly cannot see a shaped failure*, wearing a different hat:
    the fixture could not produce the input that breaks it.

    ⚠ NAMED FOR WHAT IT ASSERTS: two scans of one tree agree. It cannot catch
    hash-seed instability, which varies between PROCESSES and both scans are
    in this one -- `test_ties_are_broken_by_PATH_not_by_discovery_order` is
    what pins the tiebreak itself.
    """
    d = tmp_path / "d"
    d.mkdir()
    (d / "Show S01E01.mkv").write_bytes(b"\x1aE\xdf\xa3x")
    for group in ("Erai-raws", "SubsPlease", "shincaps", "Judas"):
        _write(str(d / (u"[%s] Show - 01.ja.srt" % group)), _srt([1.0, 2.0]))

    a = API.scan(str(d))
    b = API.scan(str(d))
    assert len(a.for_video(a.videos[0])) == 4, "the fixture must fan out"
    for va, vb in zip(a.videos, b.videos):
        assert [c.subtitle.path for c in a.for_video(va)] == \
               [c.subtitle.path for c in b.for_video(vb)]


# ---------------------------------------------------------------------------
# NCOP / NCED -- 🚨 refused, never guessed
# ---------------------------------------------------------------------------

def test_a_creditless_opening_is_skipped_with_a_reason(tmp_path):
    u"""🚨 `06-edge-cases.md` §4: *no dialogue at all. Must REFUSE, never
    guess. A phantom alignment here is the documented 108 s orphan-cue
    failure.*

    ⚠ It carries an episode number, so before this it went straight down the
    TV path -- `movies.is_creditless` was the only writer and only the FILM
    path called it. `HANDOFF.md` carried it as open at 3b.
    """
    d = tmp_path / "d"
    d.mkdir()
    (d / "Show - NCOP 01.mkv").write_bytes(b"\x1aE\xdf\xa3x")
    (d / "Show - 01.mkv").write_bytes(b"\x1aE\xdf\xa3x")
    _write(str(d / "Show - 01.ja.srt"), _srt([1.0, 2.0]))
    got = API.scan(str(d))
    assert len(got.videos) == 1
    assert any("NCOP" in p or "ncop" in p.lower() for p in got.skipped)
    reason = list(got.skipped.values())[0]
    assert "no dialogue" in reason


def test_a_creditless_SUBTITLE_is_skipped_too(tmp_path):
    u"""⚠ The same fact wearing the other extension. Refusing only the video
    leaves the subtitle offered to every episode in the folder."""
    d = tmp_path / "d"
    d.mkdir()
    (d / "Show - 01.mkv").write_bytes(b"\x1aE\xdf\xa3x")
    _write(str(d / "Show - NCED 01.ja.srt"), _srt([1.0, 2.0]))
    got = API.scan(str(d))
    assert got.subtitles == []
    assert len(got.skipped) == 1


# ---------------------------------------------------------------------------
# unpaired -- 🚨 a normal state, reported rather than silent
# ---------------------------------------------------------------------------

def test_a_video_with_no_subtitle_is_reported_not_silent(library):
    u"""A folder with 24 videos and 20 subtitles has four of these and is
    working perfectly. ⛔ It is still not allowed to be silent."""
    (library["videos"] / "Katainaka no Ossan S02E09.mkv").write_bytes(
        b"\x1aE\xdf\xa3x")
    got = API.scan(videos=str(library["videos"]), subs=str(library["subs"]))
    unpaired = got.unpaired()
    assert len(unpaired) == 1
    video, reason = unpaired[0]
    assert "S02E09" in video.name
    assert "episode 9" in reason and "season 2" in reason


def test_a_scan_is_not_iterable(library):
    u"""⭐ Same discipline as `PairPlan` and `MoviePairing`: iterating would
    walk one half and lose the others."""
    got = API.scan(videos=str(library["videos"]), subs=str(library["subs"]))
    with pytest.raises(TypeError) as exc:
        list(got)
    assert ".pairings()" in str(exc.value)


def test_the_summary_leads_with_what_needs_attention(tmp_path):
    d = tmp_path / "d"
    d.mkdir()
    (d / "Show - NCOP 01.mkv").write_bytes(b"\x1aE\xdf\xa3x")
    (d / "Show - 01.mkv").write_bytes(b"\x1aE\xdf\xa3x")
    got = API.scan(str(d))
    assert got.summary().startswith("1 skipped")


# ---------------------------------------------------------------------------
# Item.cues -- 🚨 content_end, never max()
# ---------------------------------------------------------------------------

def test_item_content_end_walks_back_over_an_orphan_cue():
    u"""🚨 `LEDGER-HOT.md`: on 1.94% of 1,495 real files the last cue sits
    >120 s past the previous one (`Gintama - 074.ass`: 429 cues to ~1,475 s,
    plus one at 3,616.9 s). Fed the raw maximum, `duration_verdict` calls a
    perfectly good subtitle IMPOSSIBLE for its own video.

    `HANDOFF.md` carried `Item.cues` as documented *"last cue time"* and open
    at 3b.
    """
    # ⚠ THE FIXTURE HAS TO BE THE REAL SHAPE. The first version was
    # `[10, 20, 30, 1475, 3616.9]` -- which has TWO orphan gaps, so the walk
    # correctly went back twice and returned 30.0, and the check failed against
    # working code. `Gintama - 074.ass` is 429 cues running continuously to
    # ~1,475 s and then ONE at 3,616.9 s; a fixture with a hole in the middle
    # is a different file testing a different thing.
    item = DISC.Item("/x/Show - 01.srt", "subtitle")
    body = [10.0 * (i + 1) for i in range(147)]      # 10 .. 1470, no gaps
    starts = body + [1475.0, 3616.9]
    got = item.set_content_end(starts)
    assert got == 1475.0
    assert item.cues == 1475.0
    assert got != max(starts)


def test_item_content_end_leaves_a_normal_file_alone():
    u"""⭐ The positive control: the orphan walk must not shorten a file whose
    tail is ordinary. Without this, the check above passes against a function
    that always drops the last cue."""
    item = DISC.Item("/x/Show - 02.srt", "subtitle")
    assert item.set_content_end([10.0, 20.0, 30.0, 40.0]) == 40.0


def test_item_content_end_and_duration_content_end_are_one_function():
    u"""⭐ `doctrine/architecture` rule 4: a derived value needs ONE writer."""
    starts = [5.0, 900.0, 3000.0]
    item = DISC.Item("/x/y.srt", "subtitle")
    assert item.set_content_end(starts) == DUR.content_end(starts)


# ---------------------------------------------------------------------------
# Result -- 🚨 the shape hato pins
# ---------------------------------------------------------------------------

def test_result_carries_every_field_the_spec_names():
    u"""🚨 `05-interface.md` §*`Result` carries*. Fields are added, never
    renamed -- hato is written against these names."""
    named = ("video", "subtitle", "outcome", "segments", "match_rate",
             "excess_over_chance", "verdict_word", "reason",
             "holds_throughout", "cluster_coherence", "dropped_in_gap",
             "reference_kind", "output_path", "superseded")
    r = API.Result("/v.mkv", "/s.srt", V.CONFIDENT, verdict_word=u"locked")
    for field in named:
        assert hasattr(r, field), field


def test_result_keeps_the_detected_language_and_the_tag_apart():
    u"""`05-interface.md`: *a file tagged `ja-jp` and one tagged `.jpn.` are
    the same language and must dedupe together, but the output name should
    preserve what the user's other tooling expects.*"""
    r = API.Result("/v.mkv", "/s.srt", V.CONFIDENT, verdict_word=u"locked",
                   lang=u"ja", lang_tag=u"jpn")
    assert r.lang == u"ja" and r.lang_tag == u"jpn"


def test_a_non_confident_result_cannot_be_built_without_a_reason():
    u"""🚨 `03-permissions.md` §hand-back. A blank refusal reads as a success
    at every surface downstream."""
    for outcome in (V.REFUSED, V.ERROR):
        with pytest.raises(ValueError) as exc:
            API.Result("/v.mkv", "/s.srt", outcome)
        assert "hand-back" in str(exc.value)


def test_a_non_confident_result_cannot_carry_a_confidence_word():
    u"""🚨 `LEDGER.md` §Interface: a GUI painted a run green because
    *"11 confident, 1 refused"* contains `confident`."""
    with pytest.raises(ValueError) as exc:
        API.Result("/v.mkv", "/s.srt", V.REFUSED, reason=u"too low",
                   verdict_word=u"locked")
    assert "confident" in str(exc.value)


def test_an_ERROR_result_cannot_claim_an_output_path():
    u"""🚨 ERROR means never measured, so there is no offset to have written
    -- and `--force` overrides a refusal, never a missing measurement."""
    with pytest.raises(ValueError) as exc:
        API.Result("/v.mkv", "/s.srt", V.ERROR, reason=u"unreadable",
                   output_path="/v.ja.srt")
    assert "never measured" in str(exc.value)


def test_a_FORCED_result_may_carry_an_output_path():
    u"""⚠ The named exception. A forced write is reported as REFUSED and it
    does write; refusing to model that would make the report a lie.

    🚨 AND `forced=True` IS WHAT NAMES IT. This check used to omit it and pass
    — because the guard only covered `outcome == ERROR` while the comment
    above it claimed the exception was `forced`. **The check written for the
    exception was testing the hole.** Found by an adversarial pass.
    """
    r = API.Result("/v.mkv", "/s.srt", V.REFUSED, reason=u"written under force",
                   output_path="/v.ja.srt", forced=True)
    assert r.output_path == "/v.ja.srt" and r.forced is True


def test_a_REFUSED_result_may_NOT_carry_an_output_path_unforced():
    u"""🚨 The other half, and the half that was missing. A refusal that wrote
    a file is a forced write and must say so; anything else is the confidently
    wrong file this project exists to prevent."""
    with pytest.raises(ValueError) as exc:
        API.Result("/v.mkv", "/s.srt", V.REFUSED, reason=u"too low",
                   output_path="/v.ja.srt")
    assert "forced=False" in str(exc.value)


def test_a_CONFIDENT_result_may_not_be_a_BARE_TICK():
    u"""`05-interface.md`: *evidence on every line — `96% match · locked`,
    never a bare tick.* A CONFIDENT result with no word renders as `OK 0%
    match · None`."""
    with pytest.raises(ValueError) as exc:
        API.Result("/v.mkv", "/s.srt", V.CONFIDENT)
    assert "bare tick" in str(exc.value)


def test_a_result_cannot_invent_a_FIFTH_confidence_word():
    u"""🚨 `Result` has a public constructor that hato and the CLI both call,
    so `Result(CONFIDENT, verdict_word="REFUSED")` was constructible — and it
    re-arms `LEDGER.md` §Interface's GUI defect from the other side.
    `verdict.py` keeps the four mutually non-substring; nothing was keeping
    this one to the four at all. Found by an adversarial pass."""
    for bad in (u"REFUSED", u"certain", u"perfect", u"ok"):
        with pytest.raises(ValueError) as exc:
            API.Result("/v.mkv", "/s.srt", V.CONFIDENT, verdict_word=bad)
        assert "confidence words" in str(exc.value), bad
    for good in sorted(V.CONFIDENCE_WORDS):
        API.Result("/v.mkv", "/s.srt", V.CONFIDENT, verdict_word=good)


def test_an_EMPTY_STRING_does_not_slip_the_word_or_path_guards():
    u"""⚠ The falsy evasions. `verdict_word=u""` and `output_path=u""` both
    slipped guards written as `if x:`."""
    with pytest.raises(ValueError):
        API.Result("/v.mkv", "/s.srt", V.REFUSED, reason=u"low",
                   verdict_word=u"")
    # ⭐ And an empty output_path is not a write, so it is ACCEPTED — the point
    # is that it is not treated as one either.
    r = API.Result("/v.mkv", "/s.srt", V.ERROR, reason=u"unreadable",
                   output_path=u"")
    assert not r.output_path


def test_result_rejects_a_fourth_outcome():
    u"""⛔ `03-permissions.md`: *there is no fourth, and no silent success.*"""
    with pytest.raises(ValueError) as exc:
        API.Result("/v.mkv", "/s.srt", u"MAYBE", reason=u"...")
    assert "fourth outcome" in str(exc.value)


def test_result_excess_is_the_spec_name_over_the_verdicts_own():
    u"""⚠ `Verdict.excess` -> `Result.excess_over_chance`, and `Verdict.word`
    -> `Result.verdict_word`. Taking an output name from the layer below is
    one of the seam defects the 2026-09-09 adversarial pass found."""
    r = API.Result("/v.mkv", "/s.srt", V.CONFIDENT, excess_over_chance=4.2,
                   raw_excess=4.2, verdict_word=u"locked")
    assert r.excess_over_chance == 4.2
    assert r.verdict_word == u"locked"
    assert not hasattr(r, "excess")
    assert not hasattr(r, "word")


def test_match_percent_is_the_human_number():
    r = API.Result("/v.mkv", "/s.srt", V.CONFIDENT, verdict_word=u"locked",
                   match_rate=0.9612)
    assert r.match_percent == 96


# ===========================================================================
# 🚨 THE ADVERSARIAL PASS, 2026-09-09 -- fourteen findings, and the twelve
#    mutants that survived EVERY suite in the project
# ===========================================================================

def test_two_UNC_shares_do_not_crash_the_library(monkeypatch):
    u"""🚨 `os.path.commonpath` RAISES on two UNC shares, and the guard could
    not see it because **both UNC paths start with a backslash**.

    `\\\\nas\\media` against `\\\\nas\\subs` — one server, two shares — is the
    canonical two-folder layout for this tool's audience, and a `ValueError`
    escaped the library that promises to *return structured results*. Before
    3b nothing public called `proximity`; `scan()` made it the first thing any
    caller hits.
    """
    a = DISC.Item(u"\\\\nas\\media\\Show\\Show S01E01.mkv", "video")
    b = DISC.Item(u"\\\\nas\\subs\\Show S01E01.ja.srt", "subtitle")
    assert DISC.proximity(a, b) == DISC.ELSEWHERE
    c = DISC.Item(u"\\\\other\\share\\x.srt", "subtitle")
    assert DISC.proximity(a, c) == DISC.ELSEWHERE
    # ⭐ And the positive control: paths it CAN compare still score.
    d = DISC.Item(u"\\\\nas\\media\\Show\\Show S01E01.ja.srt", "subtitle")
    assert DISC.proximity(a, d) == DISC.SAME_DIR


def test_the_same_file_twice_is_discovered_ONCE(tmp_path):
    u"""🚨 The file-root branch of `walk()` bypassed the `seen` dedupe, so a
    glob expanding to a folder plus a file inside it produced TWO `Item`s for
    one file — two `dedupe.Candidate`s for one slot, and `dedupe.plan`
    supersedes every candidate that is not the winner OBJECT. The duplicate
    loses and the user's only copy goes to the trash."""
    d = tmp_path / "d"
    d.mkdir()
    (d / "Show S01E01.mkv").write_bytes(b"\x1aE\xdf\xa3x")
    sub = _write(str(d / "Show S01E01.ja.srt"), _srt([1.0, 2.0]))

    assert len(DISC.walk([sub, sub])) == 1
    assert len(DISC.walk([str(d), sub])) == 2      # the video and the subtitle
    got = API.scan(videos=str(d), subs=[str(d), sub])
    assert len(got.subtitles) == 1
    assert len(got.for_video(got.videos[0])) == 1


def test_a_MISSING_root_is_refused_rather_than_read_as_an_empty_library(
        tmp_path):
    u"""⛔ `scan(videos="/medai/anime")` returned a cheerful empty `Scan`. A
    typo and an empty library must not look the same."""
    with pytest.raises(ValueError) as exc:
        API.scan(str(tmp_path / "no-such-folder"))
    assert "do not exist" in str(exc.value) or "does not exist" in str(exc.value)


def test_an_EMPTY_LIST_of_roots_is_refused_too(tmp_path):
    u"""⚠ The guard only caught `videos is None and subs is None`, so
    `subs=[]` slipped it."""
    for kwargs in ({"subs": []}, {"videos": []}, {"videos": (), "subs": ()}):
        with pytest.raises(ValueError):
            API.scan(**kwargs)


def test_an_EMPTY_folder_is_NOT_an_error(tmp_path):
    u"""⭐ The control. A root that exists and holds nothing is an ordinary
    state, and `unpaired()` is where it is reported."""
    empty = tmp_path / "empty"
    empty.mkdir()
    got = API.scan(str(empty))
    assert got.videos == [] and got.subtitles == []


def test_a_NESTED_subs_root_does_not_widen_the_video_side(tmp_path):
    u"""🚨 `scan(videos="lib", subs="lib/subs")` walked `lib` for videos, which
    descends INTO `lib/subs` — so a stray `.mkv` a release group left in the
    subtitle folder became a video to be synced.

    ⛔ Both checks written for this rule used DISJOINT roots, so neither could
    see it. `Film/Subs/` is a layout `movies._sole_video_dir` documents by
    name. ⭐ The more specific root wins.
    """
    lib = tmp_path / "lib"
    subs = lib / "subs"
    subs.mkdir(parents=True)
    (lib / "Show S01E01.mkv").write_bytes(b"\x1aE\xdf\xa3x")
    (subs / "stray.mkv").write_bytes(b"\x1aE\xdf\xa3x")
    _write(str(subs / "Show S01E01.ja.srt"), _srt([1.0, 2.0]))

    got = API.scan(videos=str(lib), subs=str(subs))
    assert [v.name for v in got.videos] == ["Show S01E01.mkv"]
    assert len(got.subtitles) == 1


def test_a_PARENT_subs_root_does_not_take_the_videos_own_subtitle(tmp_path):
    u"""The mirror image: `subs` is the parent of `videos`, so a `.srt` sitting
    beside the videos was collected from the subtitle side."""
    lib = tmp_path / "lib"
    videos = lib / "videos"
    videos.mkdir(parents=True)
    (videos / "Show S01E01.mkv").write_bytes(b"\x1aE\xdf\xa3x")
    _write(str(videos / "Show S01E01.en.srt"), _srt([1.0, 2.0]))
    _write(str(lib / "Show S01E01.ja.srt"), _srt([1.0, 2.0]))

    got = API.scan(videos=str(videos), subs=str(lib))
    assert [s.name for s in got.subtitles] == ["Show S01E01.ja.srt"]


def test_the_same_root_spelled_two_ways_WALKS_THE_TREE_ONCE(tmp_path,
                                                            monkeypatch):
    u"""⚠ The `sub_roots == video_roots` shortcut was a raw string compare, so
    `lib` and `lib\\` — and on Windows `C:\\lib` and `c:\\lib` — took the
    two-folder branch depending on spelling.

    ⭐ NAMED FOR WHAT IS OBSERVABLE. The *answer* is right either way, because
    `_claimed_by` gives equal-length roots to both sides — so asserting the
    counts proved nothing and the mutant survived honestly. What the shortcut
    buys is **one walk instead of two over the same tree**, and that is what
    this measures.
    """
    d = tmp_path / "d"
    d.mkdir()
    (d / "Show S01E01.mkv").write_bytes(b"\x1aE\xdf\xa3x")
    _write(str(d / "Show S01E01.ja.srt"), _srt([1.0, 2.0]))

    walks = []
    real = DISC.walk
    monkeypatch.setattr(DISC, "walk",
                        lambda roots, **kw: (walks.append(roots)
                                             or real(roots, **kw)))
    got = API.scan(videos=str(d), subs=str(d) + os.sep)
    assert len(got.videos) == 1 and len(got.subtitles) == 1
    assert len(walks) == 1, walks


def test_the_parsed_of_seam_is_actually_HIT(tmp_path):
    u"""🚨 IT WAS KEYED ON THE BASENAME AND `movies._entry` CALLS IT WITH THE
    FULL PATH — **0 hits out of 0/2**, so the Rule 4 optimisation saved nothing
    and the per-folder scheme hint was silently discarded. Two mutants
    (returning `None`, and not passing the seam at all) survived every suite in
    the project. Found by an adversarial pass.

    ⚠ Asserted by CALLING the seam with what `movies` really passes, not by
    reading the code.
    """
    d = tmp_path / "d"
    d.mkdir()
    (d / "Inception (2010).mkv").write_bytes(b"\x1aE\xdf\xa3x")
    _write(str(d / "Inception (2010).en.srt"), _srt([1.0, 2.0]))
    got = API.scan(str(d))
    seam = API._parsed_of(got.videos + got.subtitles)
    hits = [seam(i.path) for i in got.videos + got.subtitles]
    assert all(h is not None for h in hits), hits
    # ⛔ And the basename is NOT the key: two `01`s in two folders collide.
    assert seam(os.path.basename(got.videos[0].path)) is None


def test_the_film_paths_OWN_refusal_reason_reaches_the_user(tmp_path):
    u"""🚨 `03-permissions.md` §hand-back. The movie path had already said
    *"no video in the walk shares its key 'bladerunner' and year 1982"*, and
    `_nothing_reason` substituted a generic sentence that was also FALSE —
    there was a subtitle and it had been considered."""
    d = tmp_path / "d"
    d.mkdir()
    (d / "Blade Runner (1982) [Final Cut].mkv").write_bytes(b"\x1aE\xdf\xa3x")
    (d / "Blade Runner (1982) [Theatrical].mkv").write_bytes(b"\x1aE\xdf\xa3x")
    _write(str(d / "Blade Runner (1982).en.srt"), _srt([1.0, 2.0]))
    got = API.scan(str(d))
    if not got.films.refusals:
        pytest.skip("SKIPPED, NOT PASSED: the movie path paired these, so "
                    "there is no refusal to surface")
    reasons = [r for _v, r in got.unpaired()]
    assert reasons, got.unpaired()
    assert any("the film path refused" in r for r in reasons), reasons


def test_the_summary_counts_SUBTITLES_not_films(tmp_path):
    u"""🚨 A `MovieRefusal` is about a SUBTITLE — read
    `movies.MovieRefusal.subtitle`. The headline line of the ruled CLI output
    said *"1 film not paired"* for *"1 subtitle found no film"*."""
    d = tmp_path / "d"
    d.mkdir()
    (d / "Blade Runner (1982) [Final Cut].mkv").write_bytes(b"\x1aE\xdf\xa3x")
    (d / "Blade Runner (1982) [Theatrical].mkv").write_bytes(b"\x1aE\xdf\xa3x")
    _write(str(d / "Blade Runner (1982).en.srt"), _srt([1.0, 2.0]))
    got = API.scan(str(d))
    if not got.films.refusals:
        pytest.skip("SKIPPED, NOT PASSED: nothing was refused here")
    assert "subtitle" in got.summary() and "film not paired" not in got.summary()


# --- the rank_key's MIDDLE keys, which nothing pinned ----------------------

def test_the_SCORE_tiebreak_decides_when_identity_ties(tmp_path):
    u"""🚨 `-score` could be INVERTED or DELETED and no check noticed.
    `test_candidates_are_ranked_by_identity_first` asserts a proximity ordering
    that is a CONSEQUENCE of identity winning, not a test of any lower key.
    `LEDGER-HOT.md`'s *a ranking check is rescued by its own lower tiebreaks*,
    one level up. Found by an adversarial pass.

    ⭐ Both candidates are UNSURE and in the same folder, so identity and
    proximity tie and only the similarity score can order them — and the
    expected winner sorts LAST by path.

    ⚠ THE FIRST VERSION OF THIS FIXTURE WAS RESCUED BY A HIGHER KEY, which is
    the same trap one level up: its two candidates measured `unsure` and
    `different`, so IDENTITY decided and the score mutant survived. Measured
    against `Katainaka no Ossan`: `Zzz Katainaka Ossan` scores **0.667** and
    `Aaa Katainaka no Ossan Gaiden` **0.500**, and both are `unsure`.
    """
    d = tmp_path / "d"
    d.mkdir()
    (d / "Katainaka no Ossan S01E01.mkv").write_bytes(b"\x1aE\xdf\xa3x")
    _write(str(d / "Aaa Katainaka no Ossan Gaiden S01E01.ja.srt"),
           _srt([1.0, 2.0]))
    _write(str(d / "Zzz Katainaka Ossan S01E01.ja.srt"), _srt([1.0, 2.0]))
    got = API.scan(str(d))
    ranked = got.for_video(got.videos[0])
    assert len(ranked) == 2
    assert ranked[0].identity == ranked[1].identity, [
        (c.subtitle.name, c.identity, c.score) for c in ranked]
    assert ranked[0].proximity == ranked[1].proximity
    assert ranked[0].score > ranked[1].score
    assert ranked[0].subtitle.path > ranked[1].subtitle.path


def test_the_PROXIMITY_tiebreak_decides_when_identity_and_score_tie(tmp_path):
    u"""🚨 `-proximity` was equally unpinned. ⭐ Identical names, so identity
    and score tie exactly, and the NEAR one is in `zzz/` so it sorts LAST under
    the path tiebreak — only the proximity key can put it first."""
    videos = tmp_path / "zzz"
    far = tmp_path / "elsewhere"
    videos.mkdir()
    far.mkdir()
    (videos / "Show S01E01.mkv").write_bytes(b"\x1aE\xdf\xa3x")
    _write(str(far / "Show S01E01.ja.srt"), _srt([1.0, 2.0]))
    _write(str(videos / "Show S01E01.ja.srt"), _srt([1.0, 2.0]))
    got = API.scan(videos=str(videos), subs=[str(far), str(videos)])
    ranked = got.for_video(got.videos[0])
    assert len(ranked) == 2
    assert ranked[0].identity == ranked[1].identity
    assert ranked[0].score == ranked[1].score
    assert ranked[0].proximity > ranked[1].proximity
    assert ranked[0].subtitle.path > ranked[1].subtitle.path


def test_the_identity_memo_is_keyed_on_BOTH_titles(tmp_path):
    u"""🚨 A memo keyed on the subtitle title alone survived every suite. Two
    videos with different titles asking about the same subtitle would then get
    the FIRST video's answer."""
    d = tmp_path / "d"
    d.mkdir()
    (d / "Katainaka no Ossan S01E01.mkv").write_bytes(b"\x1aE\xdf\xa3x")
    (d / "Completely Different Show S01E01.mkv").write_bytes(b"\x1aE\xdf\xa3x")
    _write(str(d / "Katainaka no Ossan S01E01.ja.srt"), _srt([1.0, 2.0]))
    got = API.scan(str(d))
    by_name = dict((v.name, v) for v in got.videos)
    right = got.for_video(by_name["Katainaka no Ossan S01E01.mkv"])[0]
    wrong = got.for_video(by_name["Completely Different Show S01E01.mkv"])[0]
    assert right.identity == SERIES.SAME
    assert wrong.identity != SERIES.SAME, wrong


def test_the_ranked_cache_is_keyed_on_the_PATH_not_the_basename(tmp_path):
    u"""🚨 Two videos sharing a basename in different folders —
    `Season 1/01.mkv`, `Season 2/01.mkv`, a real layout — would share one
    candidate list. Survived every suite."""
    s1 = tmp_path / "Season 1"
    s2 = tmp_path / "Season 2"
    s1.mkdir()
    s2.mkdir()
    # ⚠ THE SAME BASENAME IN BOTH FOLDERS, which is the whole point. The first
    # version named them `Show S01E01` and `Show S02E01` — different basenames,
    # so nothing collided and the mutant survived honestly.
    for folder in (s1, s2):
        (folder / "Show - 01.mkv").write_bytes(b"\x1aE\xdf\xa3x")
        _write(str(folder / "Show - 01.ja.srt"), _srt([1.0, 2.0]))
    got = API.scan(str(tmp_path))
    assert len(got.videos) == 2
    for video in got.videos:
        ranked = got.for_video(video)
        assert len(ranked) == 2, [c.subtitle.path for c in ranked]
        # ⭐ Each video's own folder ranks first on proximity. With one shared
        # cache entry the second video gets the FIRST one's order.
        assert os.path.dirname(ranked[0].subtitle.path) == \
            os.path.dirname(video.path), (video.path,
                                          ranked[0].subtitle.path)


def test_no_recurse_applies_to_the_VIDEO_side_too(tmp_path):
    u"""🚨 `recurse` was only exercised on the subs side, so `--no-recurse`
    could have been entirely inert for videos and no check would have said so."""
    lib = tmp_path / "lib"
    deep = lib / "Season 2"
    deep.mkdir(parents=True)
    (lib / "Show S01E01.mkv").write_bytes(b"\x1aE\xdf\xa3x")
    (deep / "Show S02E01.mkv").write_bytes(b"\x1aE\xdf\xa3x")
    _write(str(lib / "Show S01E01.ja.srt"), _srt([1.0, 2.0]))
    wide = API.scan(str(lib))
    narrow = API.scan(str(lib), recurse=False)
    assert len(wide.videos) == 2
    assert len(narrow.videos) == 1


def test_the_summary_still_leads_when_only_a_FILM_was_refused(tmp_path):
    u"""🚨 Dropping `films.refusals` from the summary's head survived every
    suite — the only summary check had a `skipped` entry leading it anyway."""
    d = tmp_path / "d"
    d.mkdir()
    (d / "Blade Runner (1982) [Final Cut].mkv").write_bytes(b"\x1aE\xdf\xa3x")
    (d / "Blade Runner (1982) [Theatrical].mkv").write_bytes(b"\x1aE\xdf\xa3x")
    _write(str(d / "Blade Runner (1982).en.srt"), _srt([1.0, 2.0]))
    got = API.scan(str(d))
    if not got.films.refusals:
        pytest.skip("SKIPPED, NOT PASSED: nothing was refused here")
    assert got.summary().startswith("1 subtitle found no film")


def test_nothing_in_the_package_writes_Item_cues_by_hand():
    u"""⭐ The enforceable version of `set_content_end`'s claim.

    An adversarial pass measured three ways to skip the orphan walk — the
    constructor parameter, a plain assignment, and a plain assignment AFTER a
    correct call — and `cues` is a `__slots__` entry, so Python cannot stop
    any of them. What CAN be guaranteed is that nothing in this package does
    it, and that is a grep rather than a sentence.
    """
    import ast
    import tsubasa as pkg

    def _offenders(source, label):
        found = []
        for node in ast.walk(ast.parse(source, label)):
            if isinstance(node, ast.Call) and \
                    getattr(node.func, "id", None) == "Item" and \
                    any(k.arg == "cues" for k in node.keywords):
                found.append("%s: Item(cues=...)" % label)
        return found

    # ⭐ THE DETECTOR IS PROVED ABLE TO FIRE FIRST, on a constructed string.
    # ⛔ The obvious alternative -- append an offending call to a real module
    # and restore it -- is `open(path, 'w')` on a file this project cannot
    # afford to lose, and `LEDGER-HOT.md` records that as BITTEN THREE TIMES.
    # A detector with a self-control needs nothing on disk touched.
    assert _offenders(
        "def f(starts):\n    return Item('/x', 'subtitle', cues=max(starts))\n",
        "<control>")
    assert _offenders("Item('/x', 'subtitle')\n", "<negative>") == []

    root = os.path.dirname(os.path.abspath(pkg.__file__))
    offenders = []
    for dirpath, _dirs, names in os.walk(root):
        for name in names:
            if not name.endswith(".py") or name == "discover.py":
                continue
            path = os.path.join(dirpath, name)
            with io.open(path, encoding="utf-8") as fh:
                offenders.extend(_offenders(fh.read(), name))
    assert offenders == [], offenders


def test_the_creditless_guard_does_not_fire_on_the_word_cleaned():
    u"""🚨 MEASURED OVER 40,993 REAL CORPUS FILENAMES: the guard fired 28
    times and **3 of the 28 were real subtitles** — `[cleaned-retimed]`,
    `(cleaned)`, `[Cleaned]`. `clean[\\s._\\-]*(?:op|ed)` accepts ZERO
    separators, so `clean` + `ed` is `cleaned`.

    ⛔ And `cleaned` is a subtitle-community convention for a sub with ads and
    typesetting stripped — precisely the file this tool exists to sync. The
    user was told it carried no dialogue, which is a lie, and `unpaired()`
    then said no subtitle carried that episode, which is a second one.
    Found by an adversarial pass; it became reachable at 3b.
    """
    from tsubasa import movies as MOV
    must_not = [
        u"Hibike! Euphonium S3 - 01 (NHKE)[cleaned-retimed].srt",
        u"[Anon][QYQ][Kanon][DVDRIP][22] (cleaned).ass",
        u"[Cleaned] Megaton-kyuu Musashi - 03 (TOKYO MX).srt",
        u"Cleaned Up (2013).mkv", u"cleaner.srt", u"encoded.srt",
    ]
    for name in must_not:
        assert not MOV.is_creditless(name), name
    # ⭐ And the positive control, including the shapes the same pass found
    # were being MISSED: the `v2` re-release form and the separated spellings.
    must = [u"Show - NCOP.mkv", u"Show - NCED1.ass", u"Show NCOP1v2.mkv",
            u"Show NCOP01v2.mkv", u"Show NC-OP.mkv", u"Show NC_ED.mkv",
            u"Show NC OP 01.mkv", u"Show Creditless ED1.ass",
            u"Show Clean Opening.mkv", u"Show CleanOpening.mkv",
            u"Show Textless Opening.mkv", u"Show Textless OP 01.mkv"]
    for name in must:
        assert MOV.is_creditless(name), name


# ---------------------------------------------------------------------------
# the package surface
# ---------------------------------------------------------------------------

def test_the_package_exports_what_the_spec_promises():
    u"""`05-interface.md`: `from tsubasa import scan, sync, align, Result`."""
    assert callable(tsubasa.scan)
    assert callable(tsubasa.align)
    assert tsubasa.Result is API.Result


# ===========================================================================
# 🚨 THE ABSOLUTE-NUMBERING FALLBACK IS FILTERED BY SERIES IDENTITY
# ===========================================================================

def test_a_speculative_candidate_the_SERIES_cannot_confirm_is_not_offered(
        tmp_path):
    u"""⭐ THE PRECISION. The index offers a whole season on a guess about
    numbering; what keeps that set small and right is the series identity,
    which is already computed for every candidate.

    Two unrelated shows share a folder and neither pairs by number. The guess
    must reach only the one the titles agree about — ⛔ a guess identity
    cannot confirm is not offered at all.
    """
    for name in (u"Alpha S02E10.mkv",
                 u"Alpha S02E22.ja.srt",
                 u"Bravo S02E31.ja.srt"):
        (tmp_path / name).write_bytes(b"x")

    scan = API.scan(str(tmp_path))
    video = [v for v in scan.videos if v.name.startswith(u"Alpha")][0]
    offered = scan.for_video(video)

    names = [c.subtitle.name for c in offered]
    assert names == [u"Alpha S02E22.ja.srt"], names
    assert offered[0].speculative is True
    assert u"counts episodes from the start of the series" in offered[0].reason


def test_a_speculative_pair_says_WHY_it_was_offered(tmp_path):
    u"""⛔ NEVER SILENT. A candidate offered on a guess must say so, or a
    person reading the reason cannot tell it from a name-level match."""
    for name in (u"Alpha S02E10.mkv", u"Alpha S02E22.ja.srt"):
        (tmp_path / name).write_bytes(b"x")
    scan = API.scan(str(tmp_path))
    video = scan.videos[0]
    cand = scan.for_video(video)[0]
    assert cand.speculative is True
    assert u"episode numbers do not match" in cand.reason


def test_an_ordinary_candidate_is_NOT_marked_speculative(tmp_path):
    u"""⚠ The control. If everything were speculative, dedupe would stop
    trashing anything and this feature would read as working."""
    for name in (u"Alpha S02E10.mkv", u"Alpha S02E10.ja.srt"):
        (tmp_path / name).write_bytes(b"x")
    scan = API.scan(str(tmp_path))
    cand = scan.for_video(scan.videos[0])[0]
    assert cand.speculative is False
    assert u"episode numbers do not match" not in cand.reason


# ===========================================================================
# 🚨 THE DERIVED OFFSET NEEDS SERIES IDENTITY, AND TWO SHOWS GET TWO ANSWERS
# ===========================================================================

def test_two_shows_in_one_folder_get_their_OWN_offsets(tmp_path):
    u"""🚨 THE CASE THAT WOULD BE SILENTLY WRONG.

    A shift derived for one show must never be applied to another. Both are
    season 2 and both number their videos 1–6, so nothing but SERIES IDENTITY
    tells them apart — which is also why the derivation lives on `Scan` and
    not in the index.
    """
    for n in range(1, 7):
        (tmp_path / (u"Alpha S02E%02d.mkv" % n)).write_bytes(b"x")
        (tmp_path / (u"Alpha S02E%02d.ja.srt" % (n + 12))).write_bytes(b"x")
        (tmp_path / (u"Bravo S02E%02d.mkv" % n)).write_bytes(b"x")
        (tmp_path / (u"Bravo S02E%02d.ja.srt" % (n + 20))).write_bytes(b"x")

    scan = API.scan(str(tmp_path))

    # 🚨 ASSERTED ON THE DERIVED OFFSETS THEMSELVES, NOT ON WHAT REACHES THE
    # SCREEN. The first version only checked that no foreign subtitle was
    # offered — which stays true even when NO offset is derived at all,
    # because `_candidacies` filters speculative candidates by identity
    # anyway. Two mutants hid behind that: one grouping without identity, one
    # deriving from a single video. Both left the offsets EMPTY and both
    # passed. ⭐ A check that measures a downstream consequence cannot see a
    # defect the downstream also happens to catch.
    offsets = scan._derive_offsets()
    assert offsets, u"no offset was derived at all"
    for video in scan.videos:
        show = video.name.split(u" ")[0]
        shift = 12 if show == u"Alpha" else 20
        assert offsets.get(video.path) == shift, (
            u"%s got offset %r, expected %d"
            % (video.name, offsets.get(video.path), shift))

        offered = scan.for_video(video)
        names = [c.subtitle.name for c in offered]
        wanted = u"%s S02E%02d.ja.srt" % (show, video.key[1] + shift)
        assert wanted in names, (video.name, names)
        # ⛔ AND NOTHING FROM THE OTHER SHOW.
        assert all(n.startswith(show) for n in names), (video.name, names)


def test_a_derived_offset_makes_every_candidate_SPECULATIVE(tmp_path):
    u"""⛔ THE SAFETY PROPERTY. A shift means the episode numbers are not
    trustworthy for this group, so the BY-NUMBER pair is suspect too —
    trashing its loser would destroy a real subtitle for another episode."""
    for n in range(1, 25):
        (tmp_path / (u"Show S02E%02d.mkv" % n)).write_bytes(b"x")
        (tmp_path / (u"Show S02E%02d.ja.srt" % (n + 12))).write_bytes(b"x")

    scan = API.scan(str(tmp_path))
    seen = 0
    for video in scan.videos:
        for cand in scan.for_video(video):
            assert cand.speculative is True, (video.name, cand.subtitle.name)
            seen += 1
    assert seen >= 24, seen


def test_an_agreeing_library_derives_NO_offset(tmp_path):
    u"""⛔ THE CONTROL. Deriving a shift where the numbers already agree would
    move every video off its own answer."""
    for n in range(1, 13):
        (tmp_path / (u"Show S02E%02d.mkv" % n)).write_bytes(b"x")
        (tmp_path / (u"Show S02E%02d.ja.srt" % n)).write_bytes(b"x")

    scan = API.scan(str(tmp_path))
    assert scan._derive_offsets() == {}
    for video in scan.videos:
        offered = scan.for_video(video)
        assert [c.subtitle.key[1] for c in offered] == [video.key[1]]
        assert offered[0].speculative is False
