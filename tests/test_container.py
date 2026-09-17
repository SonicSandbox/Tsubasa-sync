# -*- coding: utf-8 -*-
"""
The native container reader. RUNBOOK step 1d, decision `D2`.

⭐ THE CLAIM UNDER TEST

A Matroska file's own Cues index points at every subtitle block, so the timing
of a subtitle track can be read in **0.085 s and 30 KB** instead of ffmpeg's
3.04 s and 1.4 GB -- and the answer is identical to 1 ms.

🚨 AND THE CLAIM THAT MATTERS MORE: that the shortcut REFUSES to be wrong.

An index that lists only some of a track's blocks returns a perfectly
well-formed subtitle that is missing lines, with nothing on screen to say so.
That is `00-INDEX.md` Rule 2 -- a confidently wrong answer -- arriving through
the door we opened for speed. Half the checks here are about that door.

## Why the fixtures are synthetic, and what stops them lying

`LEDGER.md` §Harness, twice: *an ASCII fixture cannot test an encoding rule*,
and *a test named after a mechanism is not a test of that mechanism*. The
version of that trap here is sharper -- **a synthetic Matroska file written by
the same person who wrote the reader can encode the same misunderstanding
twice and agree with itself perfectly.**

Three things stop that, and no one of them would:

  1. `_write_mkv` is built from the Matroska element table, not from the
     reader -- it shares no code with `tsubasa/container/` at all.
  2. ⭐ The real-container checks compare against the **ffmpeg-extracted
     `.ass` of the same track**, already sitting in the corpus. That is an
     independent implementation, and it is what makes the synthetic set
     trustworthy rather than merely self-consistent.
  3. The mutation list in `LEDGER.md` -- every guard here was watched fail.

⚠ The real-container checks SKIP, loudly, on a machine with no video. A skip
is not a pass, and the message says exactly what would turn them on.
"""
import io
import os
import struct
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tsubasa import container                              # noqa: E402
from tsubasa.container import ffmpeg as ffmod              # noqa: E402
from tsubasa.container import mkv                          # noqa: E402
from tsubasa.cues import Outcome                           # noqa: E402
from tsubasa.dev.roundtrip import iter_corpus_files        # noqa: E402
from tsubasa.paths import (corpus_root, load_config,       # noqa: E402
                           media_root)

# ==========================================================================
# a Matroska writer, built from the element table and sharing no code with
# the reader. Every fixture below IS its own answer key.
# ==========================================================================

E_EBML = 0x1A45DFA3
E_SEGMENT = 0x18538067
E_SEEKHEAD = 0x114D9B74
E_SEEK = 0x4DBB
E_SEEKID = 0x53AB
E_SEEKPOS = 0x53AC
E_INFO = 0x1549A966
E_TIMESCALE = 0x2AD7B1
E_DURATION = 0x4489
E_TRACKS = 0x1654AE6B
E_TRACKENTRY = 0xAE
E_TRACKNUM = 0xD7
E_TRACKTYPE = 0x83
E_CODECID = 0x86
E_LANG = 0x22B59C
E_LANG_BCP47 = 0x22B59D
E_TRACKNAME = 0x536E
E_FLAGDEFAULT = 0x88
E_FLAGFORCED = 0x55AA
E_CLUSTER = 0x1F43B675
E_CLUSTERTS = 0xE7
E_SIMPLEBLOCK = 0xA3
E_BLOCKGROUP = 0xA0
E_BLOCK = 0xA1
E_BLOCKDURATION = 0x9B
E_CUES = 0x1C53BB6B
E_CUEPOINT = 0xBB
E_CUETIME = 0xB3
E_CUETRACKPOS = 0xB7
E_CUETRACK = 0xF7
E_CUECLUSTERPOS = 0xF1
E_CUERELPOS = 0xF0
E_CHAPTERS = 0x1043A770
E_EDITIONENTRY = 0x45B9
E_CHAPTERATOM = 0xB6
E_CHAPTERTIMESTART = 0x91
E_CHAPTERDISPLAY = 0x80
E_CHAPSTRING = 0x85
E_VOID = 0xEC

VIDEO, AUDIO, SUB = 1, 2, 0x11


def _eid(value):
    """An element ID is written as its raw bytes, marker included."""
    n = 1
    while value >> (8 * n):
        n += 1
    return value.to_bytes(n, "big")


def _vint(value, length=None):
    """An EBML size, with its length marker."""
    if length is None:
        length = 1
        while value >= (1 << (7 * length)) - 1:
            length += 1
    return ((1 << (7 * length)) | value).to_bytes(length, "big")


def _u(value, width=None):
    """An EBML unsigned integer. `width` pads it, which is legal and is what
    keeps the Cues element a FIXED size however large the offsets get."""
    if width is not None:
        return value.to_bytes(width, "big")
    if value == 0:
        return b"\x00"
    n = 1
    while value >> (8 * n):
        n += 1
    return value.to_bytes(n, "big")


def _el(eid, body):
    return _eid(eid) + _vint(len(body)) + body


def _el_unknown(eid, body):
    """An element declaring an unknown size -- legal for Segment and Cluster,
    and what a live-muxed or streamed file actually contains."""
    return _eid(eid) + b"\xff" + body


def _s(text):
    return text.encode("utf-8")


def _block(track, rel_tc, payload=b"\x2a\x2a"):
    """track vint + int16 relative timecode + flags byte + payload."""
    return _vint(track) + struct.pack(">h", rel_tc) + b"\x00" + payload


def _track_entry(number, ttype, codec, language=u"und", name=u"",
                 default=True, forced=False, bcp47=None):
    body = (_el(E_TRACKNUM, _u(number))
            + _el(E_TRACKTYPE, _u(ttype))
            + _el(E_CODECID, _s(codec))
            # `language=None` leaves the element OUT, which is a real shape.
            + (b"" if language is None else _el(E_LANG, _s(language)))
            + _el(E_FLAGDEFAULT, _u(1 if default else 0))
            + _el(E_FLAGFORCED, _u(1 if forced else 0)))
    if name:
        body += _el(E_TRACKNAME, _s(name))
    if bcp47:
        body += _el(E_LANG_BCP47, _s(bcp47))
    return _el(E_TRACKENTRY, body)


def _write_mkv(path, cues, *, timescale=1000000, duration_s=None,
               sub_track=3, codec=u"S_TEXT/ASS", language=u"jpn",
               track_name=u"", bcp47=None, second_sub=None,
               block_style="group", per_cluster=6, noise_blocks=2,
               cue_style="full", cues_at="end", with_seekhead=True,
               unknown_segment=False, unknown_cluster=False, chapters=(),
               leading_void=False):
    """Write a Matroska file whose subtitle timing is exactly `cues`.

    `cues` is [(start_seconds, duration_seconds or None)].

    The knobs are not decoration -- each is a shape that exists in the wild
    and that the reader has to survive:

      cue_style      full | thinned | skip_clusters | none | notime | broken
      cues_at        end (found through the SeekHead) | front (found by scan)
      block_style    group (BlockGroup + BlockDuration) | simple (SimpleBlock)
      unknown_*      the size-unknown forms a live muxer writes
    """
    ticks = [int(round(s * 1e9 / timescale)) for s, _d in cues]
    durs = [None if d is None else int(round(d * 1e9 / timescale))
            for _s, d in cues]

    # ---- clusters, recording where each subtitle block lands --------------
    clusters = []          # [(bytes, cluster_ts)]
    placed = []            # [(cluster_index, offset_in_cluster_body)]
    for i in range(0, len(ticks), per_cluster):
        chunk = list(range(i, min(i + per_cluster, len(ticks))))
        cl_ts = ticks[chunk[0]]
        body = _el(E_CLUSTERTS, _u(cl_ts))
        # A little video traffic, so the completeness walk has to skip past
        # blocks on other tracks exactly as it does in a real file.
        for k in range(noise_blocks):
            body += _el(E_SIMPLEBLOCK, _block(VIDEO, min(k, 32000)))
        for j in chunk:
            rel = ticks[j] - cl_ts
            if not (-32768 <= rel <= 32767):
                raise AssertionError(
                    "fixture bug: relative timecode %d does not fit in the "
                    "int16 a Matroska block header carries. Lower "
                    "per_cluster (currently %d) so a cluster spans less time."
                    % (rel, per_cluster))
            offset = len(body)
            if block_style == "simple":
                body += _el(E_SIMPLEBLOCK, _block(sub_track, rel))
            else:
                inner = _el(E_BLOCK, _block(sub_track, rel))
                if durs[j] is not None:
                    inner += _el(E_BLOCKDURATION, _u(durs[j]))
                body += _el(E_BLOCKGROUP, inner)
            placed.append((len(clusters), offset))
        if second_sub is not None:
            for s, _d in second_sub:
                rel = int(round(s * 1e9 / timescale)) - cl_ts
                if -32768 <= rel <= 32767:
                    body += _el(E_SIMPLEBLOCK, _block(second_sub_track(), rel))
        clusters.append(body)

    if unknown_cluster:
        cluster_bytes = [_el_unknown(E_CLUSTER, b) for b in clusters]
    else:
        cluster_bytes = [_el(E_CLUSTER, b) for b in clusters]

    # ---- the header elements ---------------------------------------------
    info_body = _el(E_TIMESCALE, _u(timescale))
    if duration_s is not None:
        info_body += _el(E_DURATION,
                         struct.pack(">d", duration_s * 1e9 / timescale))
    info = _el(E_INFO, info_body)

    entries = (_track_entry(1, VIDEO, u"V_MPEG4/ISO/AVC")
               + _track_entry(2, AUDIO, u"A_AAC", u"jpn")
               + _track_entry(sub_track, SUB, codec, language, track_name,
                              bcp47=bcp47))
    if second_sub is not None:
        entries += _track_entry(second_sub_track(), SUB, u"S_TEXT/UTF8",
                                u"eng", u"English", default=False)
    tracks = _el(E_TRACKS, entries)

    chapters_el = b""
    if chapters:
        atoms = b"".join(
            _el(E_CHAPTERATOM,
                _el(E_CHAPTERTIMESTART, _u(int(round(t * 1e9))))
                + _el(E_CHAPTERDISPLAY, _el(E_CHAPSTRING, _s(name))))
            for t, name in chapters)
        chapters_el = _el(E_CHAPTERS, _el(E_EDITIONENTRY, atoms))

    # ---- the Cues element, at a FIXED size whatever the offsets are -------
    def cue_indices():
        if cue_style == "none":
            return []
        if cue_style == "thinned":
            # Every other block INSIDE each cluster -- a keyframe-style
            # indexer. Each cluster keeps some entries, so a check that looks
            # at one cluster's presence would be fooled; only counting is not.
            keep = []
            for idx, (cl, _off) in enumerate(placed):
                same = [i for i, (c, _o) in enumerate(placed) if c == cl]
                if same.index(idx) % 2 == 0:
                    keep.append(idx)
            return keep
        if cue_style == "skip_clusters":
            # Whole clusters missing from the index. Every cluster that IS
            # indexed is indexed completely, so counting inside one cluster
            # cannot see this -- only walking into the neighbour can.
            return [i for i, (cl, _off) in enumerate(placed) if cl % 2 == 0]
        return list(range(len(placed)))

    def build_cues(cluster_positions):
        points = b""
        for idx in cue_indices():
            cl, off = placed[idx]
            pos = cluster_positions[cl]
            trackpos = (_el(E_CUETRACK, _u(sub_track))
                        + _el(E_CUECLUSTERPOS,
                              _u(0 if cue_style == "broken"
                                 else pos, width=8)))
            if cue_style != "notime":
                trackpos += _el(E_CUERELPOS,
                                _u(7 if cue_style == "broken" else off,
                                   width=8))
            points += _el(E_CUEPOINT,
                          _el(E_CUETIME, _u(ticks[idx], width=8))
                          + _el(E_CUETRACKPOS, trackpos))
        return _el(E_CUES, points) if points else b""

    cues_len = len(build_cues([0] * len(clusters)))

    def build_seekhead(positions):
        if not with_seekhead:
            return b""
        seeks = b""
        for eid, pos in positions:
            seeks += _el(E_SEEK, _el(E_SEEKID, _eid(eid))
                         + _el(E_SEEKPOS, _u(pos, width=8)))
        return _el(E_SEEKHEAD, seeks)

    wanted = [E_INFO, E_TRACKS] + ([E_CHAPTERS] if chapters_el else []) \
        + ([E_CUES] if cues_len else [])
    seek_len = len(build_seekhead([(e, 0) for e in wanted]))

    # ---- lay the segment out ---------------------------------------------
    void = _el(E_VOID, b"\x00" * 16) if leading_void else b""
    pos = seek_len + len(void)
    info_pos = pos
    pos += len(info)
    tracks_pos = pos
    pos += len(tracks)
    chapters_pos = pos
    pos += len(chapters_el)

    if cues_at == "front":
        cues_pos = pos
        pos += cues_len
        cluster_positions = []
        for cb in cluster_bytes:
            cluster_positions.append(pos)
            pos += len(cb)
    else:
        cluster_positions = []
        for cb in cluster_bytes:
            cluster_positions.append(pos)
            pos += len(cb)
        cues_pos = pos

    cues_el = build_cues(cluster_positions)
    assert len(cues_el) == cues_len, "fixture bug: the Cues element changed size"

    lookup = {E_INFO: info_pos, E_TRACKS: tracks_pos,
              E_CHAPTERS: chapters_pos, E_CUES: cues_pos}
    seekhead = build_seekhead([(e, lookup[e]) for e in wanted])
    assert len(seekhead) == seek_len, "fixture bug: the SeekHead changed size"

    head = seekhead + void + info + tracks + chapters_el
    body = (head + cues_el + b"".join(cluster_bytes) if cues_at == "front"
            else head + b"".join(cluster_bytes) + cues_el)

    ebml = _el(E_EBML,
               _el(0x4286, _u(1)) + _el(0x42F7, _u(1))
               + _el(0x42F2, _u(4)) + _el(0x42F3, _u(8))
               + _el(0x4282, _s(u"matroska"))
               + _el(0x4287, _u(4)) + _el(0x4285, _u(2)))
    segment = (_el_unknown(E_SEGMENT, body) if unknown_segment
               else _el(E_SEGMENT, body))

    path = str(path)
    with io.open(path, "wb") as fh:
        fh.write(ebml + segment)
    return path


def second_sub_track():
    return 4


# The default fixture: 24 cues over ~72 s, durations of 2 s.
DEFAULT_CUES = [(1.5 + 3.0 * i, 2.0) for i in range(24)]


def _starts(track):
    return [round(c.start, 6) for c in track.cues]


def _sub(info, number=3):
    for t in info.subtitle_tracks:
        if t.number == number:
            return t
    return None


# ==========================================================================
# 0 -- the fixture builder itself
# ==========================================================================

def test_the_fixture_builder_writes_something_a_reader_must_work_for(tmp_path):
    """⚠ A fixture that is trivially small proves nothing about a walk.

    The builder shares no code with the reader, but it could still emit
    something degenerate -- one cluster, no other tracks -- that the reader
    would get right by accident. This pins the shape the rest of the file
    assumes: several clusters, blocks on other tracks in every one of them,
    and real EBML magic.
    """
    p = _write_mkv(tmp_path / "shape.mkv", DEFAULT_CUES, per_cluster=6)
    data = io.open(p, "rb").read()
    assert data[:4] == b"\x1a\x45\xdf\xa3", "not an EBML file"
    assert data.count(_eid(E_CLUSTER)) >= 4, "too few clusters to be a walk"
    assert len(data) > 400, "a %d-byte file is not a container" % len(data)
    assert _eid(E_CUES) in data and _eid(E_SEEKHEAD) in data


# ==========================================================================
# 1 -- the fast path
# ==========================================================================

def test_the_cues_index_gives_every_cue_start_exactly(tmp_path):
    p = _write_mkv(tmp_path / "cues.mkv", DEFAULT_CUES)
    info = container.read(p)
    assert info.ok, info.reason
    assert info.reader == "matroska"
    track = _sub(info)
    assert track is not None, [repr(t) for t in info.tracks]
    assert track.timing_source == "cues", track.timing_source
    assert len(track.cues) == len(DEFAULT_CUES), (
        "read %d cues, the file contains %d"
        % (len(track.cues), len(DEFAULT_CUES)))
    for got, (want, _d) in zip(_starts(track), DEFAULT_CUES):
        assert abs(got - want) <= 0.001, "cue at %.3f, expected %.3f" % (got, want)


def test_block_durations_become_cue_end_times(tmp_path):
    p = _write_mkv(tmp_path / "dur.mkv", DEFAULT_CUES)
    track = _sub(container.read(p))
    for cue, (start, dur) in zip(track.cues, DEFAULT_CUES):
        assert abs(cue.end - (start + dur)) <= 0.001, repr(cue)


def test_a_block_with_no_duration_does_not_get_one_invented(tmp_path):
    """⚠ `LEDGER.md`: reporting a DERIVED end as though it were measured is
    how a downstream check inherits a fiction. A SimpleBlock carries no
    duration, so end == start and the caller can see that it does."""
    p = _write_mkv(tmp_path / "simple.mkv", DEFAULT_CUES, block_style="simple")
    track = _sub(container.read(p))
    assert len(track.cues) == len(DEFAULT_CUES)
    assert all(c.end == c.start for c in track.cues), (
        "a SimpleBlock has no BlockDuration, so no end time can be honest")
    assert _starts(track) == [round(s, 6) for s, _d in DEFAULT_CUES]


def test_the_index_is_found_through_the_seekhead_at_the_end_of_the_file(tmp_path):
    """The real mkvmerge layout: Cues written last, reachable only through
    the SeekHead. A reader that only scans forward to the first cluster finds
    nothing and silently takes the slow path on every real file."""
    p = _write_mkv(tmp_path / "end.mkv", DEFAULT_CUES, cues_at="end")
    track = _sub(container.read(p))
    assert track.timing_source == "cues"
    assert len(track.cues) == len(DEFAULT_CUES)


def test_the_index_is_also_found_when_it_precedes_the_clusters(tmp_path):
    p = _write_mkv(tmp_path / "front.mkv", DEFAULT_CUES, cues_at="front",
                   with_seekhead=False)
    track = _sub(container.read(p))
    assert track.timing_source == "cues", track.timing_source
    assert len(track.cues) == len(DEFAULT_CUES)


def test_the_fast_path_reads_a_tiny_fraction_of_the_file(tmp_path):
    """The claim is 30 KB and 5,056 seeks against 1.4 GB and 88,340.

    🚨 THE FIXTURE HAS TO CARRY THE REAL RATIO OR IT INVERTS THE CLAIM.

    Written first with 2 video blocks per cluster, the index path made **510**
    seeks and the block walk **208** -- the opposite of the measured result,
    and it would have read as a defect in the reader. It is not: the index
    only pays when a file is mostly blocks we do not want, and a real 1080p
    episode carries hundreds of video blocks per cluster, not two.

    ⭐ A fixture that is not representative of the real ratio disproves the
    thing it was built to prove. `LEDGER.md` §Harness.
    """
    common = dict(per_cluster=6, noise_blocks=250)
    fast = container.read(
        _write_mkv(tmp_path / "bytes.mkv", DEFAULT_CUES, **common))
    slow = container.read(
        _write_mkv(tmp_path / "bytes2.mkv", DEFAULT_CUES,
                   cue_style="none", with_seekhead=False, **common))
    assert _sub(fast).timing_source == "cues"
    assert _sub(slow).timing_source == "blocks"
    assert fast.seeks < slow.seeks, (
        "the Cues path made %d seeks, the block walk %d -- the index bought "
        "nothing" % (fast.seeks, slow.seeks))
    assert fast.bytes_read < slow.bytes_read, (
        "the Cues path read %d bytes, the block walk %d"
        % (fast.bytes_read, slow.bytes_read))


# ==========================================================================
# 2 -- 🚨 the guard: an index that is not complete must not be trusted
# ==========================================================================

def test_an_index_that_thins_each_cluster_is_rejected(tmp_path):
    """🚨 The defect this whole guard exists for.

    A muxer that indexes every other subtitle block hands back a subtitle
    missing half its lines, in perfect shape, with a plausible cue count. It
    would align, produce a confident offset, and be wrong.
    """
    p = _write_mkv(tmp_path / "thin.mkv", DEFAULT_CUES, cue_style="thinned")
    info = container.read(p)
    track = _sub(info)
    assert track.timing_source == "blocks", (
        "a partial index was trusted: source=%s, %d of %d cues returned"
        % (track.timing_source, len(track.cues), len(DEFAULT_CUES)))
    assert len(track.cues) == len(DEFAULT_CUES)
    assert any("partial" in w for w in info.warnings), info.warnings


def test_an_index_that_skips_whole_clusters_is_rejected(tmp_path):
    """⚠ The case a one-cluster cross-check CANNOT see.

    Every cluster this index mentions is indexed completely, so counting
    inside the busiest one agrees perfectly. Only walking into the next
    cluster -- which the index never mentions -- exposes it.
    """
    p = _write_mkv(tmp_path / "skip.mkv", DEFAULT_CUES,
                   cue_style="skip_clusters")
    info = container.read(p)
    track = _sub(info)
    assert track.timing_source == "blocks", (
        "an index missing whole clusters was trusted: %d of %d cues"
        % (len(track.cues), len(DEFAULT_CUES)))
    assert len(track.cues) == len(DEFAULT_CUES)
    assert any("partial" in w for w in info.warnings), info.warnings


def test_a_complete_index_is_reported_as_verified(tmp_path):
    """Both directions. A guard that only ever refuses passes a refusal-only
    check while being useless (`doctrine/robustness`)."""
    p = _write_mkv(tmp_path / "ok.mkv", DEFAULT_CUES)
    track = _sub(container.read(p))
    assert track.index_verified is True, track.index_verified
    assert track.timing_source == "cues"


def test_an_index_pointing_at_nothing_falls_back_rather_than_returning_junk(tmp_path):
    p = _write_mkv(tmp_path / "broken.mkv", DEFAULT_CUES, cue_style="broken")
    info = container.read(p)
    track = _sub(info)
    assert track.timing_source == "blocks", track.timing_source
    assert _starts(track) == [round(s, 6) for s, _d in DEFAULT_CUES]


def test_a_cue_point_without_a_block_position_still_yields_its_time(tmp_path):
    """Some muxers write CueTime and no CueRelativePosition. Failing open on
    the muxer's own timestamp is right; inventing a duration is not."""
    p = _write_mkv(tmp_path / "notime.mkv", DEFAULT_CUES, cue_style="notime")
    track = _sub(container.read(p))
    assert len(track.cues) == len(DEFAULT_CUES)
    assert _starts(track) == [round(s, 6) for s, _d in DEFAULT_CUES]
    assert all(c.end == c.start for c in track.cues)


def test_verification_that_could_not_run_reports_unknown_not_true(tmp_path,
                                                                  monkeypatch):
    """⛔ `LEDGER.md` §Harness: an absent answer and an unanswered question
    are different results. A cross-check that hit its budget must not be
    recorded as a clean one."""
    monkeypatch.setattr(mkv, "MAX_VERIFY_BLOCKS", 2)
    p = _write_mkv(tmp_path / "budget.mkv", DEFAULT_CUES)
    info = container.read(p)
    track = _sub(info)
    assert track.index_verified is None, (
        "the cross-check could not finish but reported %r"
        % (track.index_verified,))
    assert any("UNVERIFIED" in w for w in info.warnings), info.warnings


# ==========================================================================
# 3 -- the block walk
# ==========================================================================

def test_a_file_with_no_cues_element_is_read_by_walking_the_blocks(tmp_path):
    p = _write_mkv(tmp_path / "nocues.mkv", DEFAULT_CUES, cue_style="none",
                   with_seekhead=False)
    info = container.read(p)
    track = _sub(info)
    assert info.ok, info.reason
    assert track.timing_source == "blocks"
    assert _starts(track) == [round(s, 6) for s, _d in DEFAULT_CUES]


def test_both_paths_return_the_same_answer(tmp_path):
    """⭐ `00-INDEX.md`: an efficiency change must not change the answer. This
    is that rule as a check -- the fast path and the slow path, same file,
    same cues, to the microsecond."""
    fast = _sub(container.read(
        _write_mkv(tmp_path / "f.mkv", DEFAULT_CUES)))
    slow = _sub(container.read(
        _write_mkv(tmp_path / "s.mkv", DEFAULT_CUES, cue_style="none",
                   with_seekhead=False)))
    assert fast.timing_source == "cues" and slow.timing_source == "blocks"
    assert _starts(fast) == _starts(slow)
    assert [round(c.end, 6) for c in fast.cues] == \
           [round(c.end, 6) for c in slow.cues]


def test_use_index_false_forces_the_walk_on_the_very_same_bytes(tmp_path):
    """The strongest form of *"the shortcut did not change the answer"*: one
    file, two paths, identical bytes underneath both. The no-Cues comparison
    above uses two different files, so it can only show that the writer is
    consistent."""
    p = _write_mkv(tmp_path / "same.mkv", DEFAULT_CUES)
    fast = _sub(container.read(p))
    slow = _sub(container.read(p, use_index=False))
    assert fast.timing_source == "cues"
    assert slow.timing_source == "blocks"
    assert _starts(fast) == _starts(slow)
    assert [round(c.end, 6) for c in fast.cues] == \
           [round(c.end, 6) for c in slow.cues]


def test_a_segment_of_unknown_size_is_read(tmp_path):
    """What a live muxer writes. A reader that trusts the declared size reads
    zero clusters and reports an empty subtitle."""
    p = _write_mkv(tmp_path / "unk.mkv", DEFAULT_CUES, unknown_segment=True,
                   cue_style="none", with_seekhead=False)
    track = _sub(container.read(p))
    assert _starts(track) == [round(s, 6) for s, _d in DEFAULT_CUES]


def test_clusters_of_unknown_size_are_read(tmp_path):
    p = _write_mkv(tmp_path / "unkcl.mkv", DEFAULT_CUES, unknown_cluster=True,
                   cue_style="none", with_seekhead=False)
    track = _sub(container.read(p))
    assert _starts(track) == [round(s, 6) for s, _d in DEFAULT_CUES], (
        "unknown-size clusters lost cues")


def test_a_leading_void_element_does_not_hide_the_header(tmp_path):
    p = _write_mkv(tmp_path / "void.mkv", DEFAULT_CUES, leading_void=True)
    info = container.read(p)
    assert info.ok, info.reason
    assert len(_sub(info).cues) == len(DEFAULT_CUES)


# ==========================================================================
# 4 -- tracks, duration, chapters
# ==========================================================================

def test_the_track_list_carries_type_codec_language_and_name(tmp_path):
    p = _write_mkv(tmp_path / "tracks.mkv", DEFAULT_CUES,
                   codec=u"S_TEXT/ASS", language=u"jpn",
                   track_name=u"日本語")
    info = container.read(p, timing=False)
    kinds = [t.kind for t in info.tracks]
    assert kinds == ["video", "audio", "subtitle"], kinds
    sub = info.subtitle_tracks[0]
    assert sub.codec == u"S_TEXT/ASS", sub.codec
    assert sub.language == u"jpn", sub.language
    assert sub.name == u"日本語", sub.name


def test_the_bcp47_language_field_wins_over_the_legacy_one(tmp_path):
    """⚠ A file carrying `und` in the legacy field and `ja` in the new one is
    common. Taking the legacy field throws away the only answer there is --
    and `05-interface.md` reads container language as a pairing signal."""
    p = _write_mkv(tmp_path / "bcp.mkv", DEFAULT_CUES, language=u"und",
                   bcp47=u"ja")
    sub = container.read(p, timing=False).subtitle_tracks[0]
    assert sub.language == u"ja", (
        "legacy 'und' beat the BCP-47 'ja'; got %r" % sub.language)


def test_a_track_with_NO_language_element_reads_eng_the_matroska_default(tmp_path):
    """🚨 RUNBOOK 3f, measured: this read `""` natively and `eng` through
    ffmpeg for the SAME file, so a video's language depended on which rung of
    the ladder answered. `eng` is the format's default, like `default=True`."""
    p = _write_mkv(tmp_path / "nolang.mkv", DEFAULT_CUES, language=None)
    sub = container.read(p, timing=False).subtitle_tracks[0]
    assert sub.language == u"eng", sub.language
    explicit = _write_mkv(tmp_path / "und.mkv", DEFAULT_CUES, language=u"und")
    assert container.read(explicit, timing=False).subtitle_tracks[0].language == u"und"


def test_the_duration_is_read_and_scaled(tmp_path):
    p = _write_mkv(tmp_path / "dur2.mkv", DEFAULT_CUES, duration_s=1421.5)
    info = container.read(p, timing=False)
    assert info.duration is not None
    assert abs(info.duration - 1421.5) < 0.01, info.duration


def test_a_non_default_timestamp_scale_is_honoured(tmp_path):
    """🚨 Every time in a Matroska file is in TimestampScale units. A reader
    that assumes 1 ms is wrong by whatever factor the file chose -- silently,
    with plausible-looking numbers."""
    # per_cluster=2: at a 0.1 ms scale a tick is a tenth of a
    # millisecond, so 32767 of them is 3.27 s -- barely more than one
    # gap between these cues. A cluster spanning more overflows the
    # int16 a block header carries, which the builder refuses to write.
    p = _write_mkv(tmp_path / "scale.mkv", DEFAULT_CUES,
                   timescale=100000, per_cluster=2)
    track = _sub(container.read(p))
    assert _starts(track) == [round(s, 6) for s, _d in DEFAULT_CUES], (
        "a 0.1 ms timestamp scale was read as though it were 1 ms")


def test_chapters_are_read_as_split_point_hints(tmp_path):
    """`06-edge-cases.md` §5.2 -- chapters marking ad breaks are free
    split-point hints sitting unused in the container."""
    marks = [(0.0, u"Intro"), (85.0, u"Part A"), (742.5, u"Part B")]
    p = _write_mkv(tmp_path / "chap.mkv", DEFAULT_CUES, chapters=marks)
    info = container.read(p, timing=False)
    assert [round(t, 3) for t, _n in info.chapters] == [0.0, 85.0, 742.5], \
        info.chapters
    assert [n for _t, n in info.chapters] == [u"Intro", u"Part A", u"Part B"]


def test_a_chapter_time_is_nanoseconds_not_scale_units(tmp_path):
    """🚨 ChapterTimeStart is the one time field in Matroska that does NOT
    take the timestamp scale. Reading it like the others is wrong by a factor
    of a million -- and 742.5 s would read as 742,500,000 s, which is a
    plausible-looking number in the wrong universe."""
    p = _write_mkv(tmp_path / "chapscale.mkv", DEFAULT_CUES,
                   timescale=100000, per_cluster=2,
                   chapters=[(742.5, u"Part B")])
    info = container.read(p, timing=False)
    assert abs(info.chapters[0][0] - 742.5) < 0.001, info.chapters


def test_two_subtitle_tracks_are_both_read(tmp_path):
    p = _write_mkv(tmp_path / "two.mkv", DEFAULT_CUES,
                   second_sub=[(2.0, None), (5.0, None)])
    info = container.read(p)
    assert len(info.subtitle_tracks) == 2, [repr(t) for t in info.tracks]
    assert all(t.cues is not None for t in info.subtitle_tracks)
    assert len(_sub(info, 3).cues) == len(DEFAULT_CUES)
    assert len(_sub(info, second_sub_track()).cues) > 0


def test_a_pgs_track_yields_on_times_through_the_same_interface(tmp_path):
    """RUNBOOK 1d: *PGS/VobSub tracks yield ON-times through the same
    interface*. Block timestamps are a container fact and know nothing about
    the codec, which is exactly why the bitmap case comes free."""
    p = _write_mkv(tmp_path / "pgs.mkv", DEFAULT_CUES, codec=u"S_HDMV/PGS")
    track = _sub(container.read(p))
    assert track.codec == u"S_HDMV/PGS"
    assert _starts(track) == [round(s, 6) for s, _d in DEFAULT_CUES]


def test_timing_false_reads_the_header_and_nothing_else(tmp_path):
    """The cheap probe step A9 wants: duration and the track list, with no
    cluster opened at all. `cues is None` says timing was not read -- which
    is not the same as a track with no cues."""
    p = _write_mkv(tmp_path / "hdr.mkv", DEFAULT_CUES, duration_s=90.0)
    info = container.read(p, timing=False)
    assert info.ok
    assert info.duration is not None
    assert all(t.cues is None for t in info.tracks)
    full = container.read(p)
    assert info.bytes_read < full.bytes_read


# ==========================================================================
# 5 -- refusals, damage and the OK-with-nothing distinction
# ==========================================================================

def test_a_container_with_no_subtitle_tracks_is_OK_not_an_error(tmp_path):
    """🚨 37.5% of a real library has no embedded subtitle track
    (`08-probes.md` §E). Calling that an error refuses more than a third of
    the library -- the same OK-with-zero conflation subsync shipped twice."""
    p = _write_mkv(tmp_path / "novideo.mkv", [], cue_style="none",
                   with_seekhead=False)
    info = container.read(p)
    assert info.outcome == Outcome.OK, info.reason
    assert info.subtitle_tracks == [] or all(
        not t.cues for t in info.subtitle_tracks)


def test_a_file_that_is_not_a_container_is_refused_by_name(tmp_path):
    p = tmp_path / "notavideo.mkv"
    p.write_bytes(b"1\n00:00:01,000 --> 00:00:02,000\nhello\n")
    info = container.read(p, allow_ffmpeg=False)
    assert info.outcome == Outcome.ERROR
    assert "not Matroska" in info.reason or "ffmpeg" in info.reason, info.reason


def test_an_empty_file_says_it_is_empty(tmp_path):
    p = tmp_path / "empty.mkv"
    p.write_bytes(b"")
    info = container.read(p)
    assert info.outcome == Outcome.ERROR
    assert "0 bytes" in info.reason, info.reason


def test_a_missing_file_says_so_rather_than_raising(tmp_path):
    info = container.read(tmp_path / "nope.mkv")
    assert info.outcome == Outcome.ERROR
    assert "no such file" in info.reason, info.reason


def test_a_truncated_file_does_not_raise_out_of_the_reader(tmp_path):
    """Half a real file. Whatever it does, it must be an outcome the caller
    can read -- never a traceback in a user's face."""
    whole = io.open(_write_mkv(tmp_path / "w.mkv", DEFAULT_CUES), "rb").read()
    for fraction in (0.15, 0.4, 0.75, 0.95):
        p = tmp_path / ("cut-%d.mkv" % int(fraction * 100))
        p.write_bytes(whole[:int(len(whole) * fraction)])
        info = container.read(p, allow_ffmpeg=False)
        assert info.outcome in (Outcome.OK, Outcome.ERROR)
        if not info.ok:
            assert info.reason, "an ERROR with no reason is unactionable"


ADVERSARIAL = {
    "zero-length cluster": lambda: _el(E_SEGMENT,
        _el(E_INFO, _el(E_TIMESCALE, _u(1000000)))
        + _eid(E_CLUSTER) + _vint(0)),
    "segment of zeros": lambda: _el(E_SEGMENT, b"\x00" * 262144),
    "segment of 0xff": lambda: _el_unknown(E_SEGMENT, b"\xff" * 262144),
    "cluster claiming a huge size": lambda: _el(E_SEGMENT,
        _eid(E_CLUSTER) + _vint(2 ** 40) + b"\x00" * 512),
    "a million empty children": lambda: _el(E_SEGMENT,
        _el(E_CLUSTER, (_eid(E_VOID) + _vint(0)) * 200000)),
    "self-referential seekhead": lambda: _el(E_SEGMENT,
        _el(E_SEEKHEAD, _el(E_SEEK, _el(E_SEEKID, _eid(E_SEEKHEAD))
                            + _el(E_SEEKPOS, _u(0, width=8)))) * 4),
}


def test_the_child_element_budget_refuses_rather_than_grinding(tmp_path):
    """The bound that stops a damaged file walking for ever.

    ⚠ Tested at its OWN level, and it has to be. Through the whole reader the
    guard is invisible: a file big enough to need it takes minutes to walk
    either way, so no fast check can tell the bounded version from the
    unbounded one. The mutation run proved that -- *the budget removed* was
    the one mutant of nineteen that survived, against an adversarial set of
    six pathological files.

    ⭐ A guard that cannot be observed through the front door gets checked at
    the back one, or it is not checked at all.
    """
    from tsubasa.container.mkv import ContainerError, _Reader, _children

    body = (_eid(E_VOID) + _vint(0)) * (mkv.MAX_HEADER_ELEMENTS + 50)
    p = tmp_path / "many.bin"
    p.write_bytes(body)
    with io.open(str(p), "rb") as fh:
        r = _Reader(fh, len(body))
        with pytest.raises(ContainerError) as exc:
            for _ in _children(r, 0, len(body)):
                pass
    assert str(mkv.MAX_HEADER_ELEMENTS) in str(exc.value), str(exc.value)


@pytest.mark.parametrize("name", sorted(ADVERSARIAL))
def test_no_input_can_hang_the_reader(tmp_path, name):
    """⭐ A hang is the one failure mode that looks like nothing at all -- no
    error, no output, a user staring at a still cursor.

    ⚠ Run on a THREAD with a join timeout, and that is the whole point of the
    check. Calling the reader directly and timing it afterwards cannot fail
    on the case it is named for: if the walk never returns, the assertion
    never runs either. The first version of this check did exactly that.
    """
    import threading

    p = tmp_path / ("adv-%s.mkv" % name.replace(" ", "-"))
    p.write_bytes(_el(E_EBML, _el(0x4282, _s(u"matroska")))
                  + ADVERSARIAL[name]())

    box = []
    thread = threading.Thread(
        target=lambda: box.append(container.read(p, allow_ffmpeg=False)),
        daemon=True)
    thread.start()
    thread.join(20.0)
    assert not thread.is_alive(), (
        "%s did not terminate within 20 s -- the reader hangs on it" % name)
    assert box, "the read produced nothing at all"
    info = box[0]
    assert info.outcome in (Outcome.OK, Outcome.ERROR)
    if not info.ok:
        assert info.reason, "an ERROR with no reason is unactionable"


def test_random_bytes_wearing_the_matroska_magic_are_refused(tmp_path):
    """The magic is a hint, not a promise. A file that starts with the EBML
    signature and continues with noise must produce a reason, not a crash."""
    import random
    rng = random.Random(20260908)
    p = tmp_path / "fuzz.mkv"
    p.write_bytes(b"\x1a\x45\xdf\xa3"
                  + bytes(rng.randrange(256) for _ in range(4096)))
    info = container.read(p, allow_ffmpeg=False)
    assert info.outcome in (Outcome.OK, Outcome.ERROR)
    if not info.ok:
        assert info.reason


def test_container_cues_can_never_be_rewritten_in_place(tmp_path):
    """⛔ Structural, not remembered. A cue read out of a container has no
    character offsets in any file, so `retime()` -- which refuses any cue
    without a span -- cannot be talked into writing one. The same guarantee
    `formats/pgs.py` relies on."""
    from tsubasa.cues import ParseResult, RewriteRefused, retime
    track = _sub(container.read(_write_mkv(tmp_path / "rw.mkv", DEFAULT_CUES)))
    assert all(c.start_span is None and c.end_span is None for c in track.cues)
    result = ParseResult(cues=track.cues, text=u"", format="srt")
    with pytest.raises(RewriteRefused):
        retime(result, shift=1.0, formatter=lambda t, like: u"x")


# ==========================================================================
# 6 -- the ffmpeg fallback and its refusal
# ==========================================================================

def test_ffmpeg_absence_refuses_with_a_sentence_the_user_can_act_on(tmp_path,
                                                                    monkeypatch):
    """`10-deployment.md`: a pair that needs ffmpeg and cannot have it is
    REFUSED with an actionable reason. ⛔ Silence would be indistinguishable
    from 'this video has no subtitles', which is a normal state -- so a
    missing dependency would masquerade as a fact about the file."""
    monkeypatch.setattr(ffmod, "find", lambda tool="ffprobe", cache_dir=None: None)
    p = tmp_path / "movie.mp4"
    p.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 256)
    info = container.read(p)
    assert info.outcome == Outcome.ERROR
    assert "tsubasa setup --ffmpeg" in info.reason, info.reason
    assert "ffmpeg" in info.reason


def test_a_non_matroska_file_routes_to_ffmpeg(tmp_path, monkeypatch):
    """Routing, asserted without needing ffmpeg installed: the fallback is
    called with the path it was given."""
    calls = []

    def fake_read(path, timing=True, cache_dir=None):
        calls.append((path, timing))
        return {"format": "mov,mp4", "duration": 12.0, "tracks": [],
                "chapters": [], "warnings": []}

    monkeypatch.setattr(ffmod, "read", fake_read)
    p = tmp_path / "clip.mp4"
    p.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64)
    info = container.read(p)
    assert info.ok, info.reason
    assert info.reader == "ffmpeg"
    assert calls and calls[0][0] == str(p)


def test_allow_ffmpeg_false_never_starts_a_subprocess(tmp_path, monkeypatch):
    """The importable module promises no binary dependency on the fast path.
    A caller can hold it to that."""
    def boom(*a, **k):
        raise AssertionError("a subprocess was started with allow_ffmpeg=False")

    monkeypatch.setattr(subprocess, "run", boom)
    monkeypatch.setattr(ffmod, "read", boom)
    p = tmp_path / "x.mp4"
    p.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 64)
    info = container.read(p, allow_ffmpeg=False)
    assert info.outcome == Outcome.ERROR
    assert "ffmpeg" in info.reason


def test_a_matroska_file_never_starts_a_subprocess(tmp_path, monkeypatch):
    """⭐ The headline of step 1d: a folder of MKVs never touches ffmpeg."""
    def boom(*a, **k):
        raise AssertionError("the native path started a subprocess")

    monkeypatch.setattr(subprocess, "run", boom)
    p = _write_mkv(tmp_path / "native.mkv", DEFAULT_CUES)
    info = container.read(p)
    assert info.ok and info.reader == "matroska"
    assert len(_sub(info).cues) == len(DEFAULT_CUES)


def test_the_ffmpeg_locator_prefers_path_then_env_then_cache(tmp_path,
                                                             monkeypatch):
    import shutil as sh
    monkeypatch.setattr(sh, "which", lambda t: None)
    monkeypatch.delenv("TSUBASA_FFMPEG", raising=False)
    assert ffmod.find("ffprobe", cache_dir=tmp_path) is None

    exe = "ffprobe.exe" if sys.platform == "win32" else "ffprobe"
    (tmp_path / exe).write_bytes(b"#!/bin/sh\n")
    assert ffmod.find("ffprobe", cache_dir=tmp_path) == str(tmp_path / exe)

    monkeypatch.setattr(sh, "which", lambda t: "/usr/bin/" + t)
    assert ffmod.find("ffprobe", cache_dir=tmp_path) == "/usr/bin/ffprobe"


def test_is_video_is_a_hint_and_covers_what_the_spec_lists():
    """What discovery opens at all. `06-edge-cases.md` §5.1 fixes the list.

    ⚠ A HINT, never a decision -- the magic bytes choose the reader. It is
    checked here because an extension list with no consumer drifts out of
    step with the spec silently, and because discovery (RUNBOOK A5) is the
    caller that will trust it.
    """
    for name in ("a.mkv", "A.MKV", "b.mp4", "c.webm", "d.m2ts", "e.avi",
                 "f.mov"):
        assert container.is_video(name), name
    for name in ("a.srt", "b.ass", "c.sup", "d.idx", "e.txt", "noext",
                 "f.mkv.part"):
        assert not container.is_video(name), name
    # The native family must be a subset of what discovery will open at all;
    # a container we can read natively and never look at is worse than useless.
    assert {".mkv", ".webm"} <= container.KNOWN_VIDEO_EXT


def test_the_windows_console_flag_is_on_every_ffmpeg_call():
    """🚨 `LEDGER.md` §Environment: every ffprobe call flashed a console
    window that stole focus. Under the GUI the parent has no console, so each
    child allocates its own -- once per probed file."""
    kwargs = ffmod._no_window()
    if sys.platform == "win32":
        assert kwargs.get("creationflags"), kwargs
        assert kwargs.get("startupinfo") is not None
    else:
        assert kwargs == {}


# ==========================================================================
# 7 -- real containers. SKIPPED, not passed, where there are none.
# ==========================================================================

@pytest.fixture(scope="module")
def real_mkvs():
    cfg = load_config(ROOT)
    try:
        root = media_root(cfg, ROOT)
    except Exception as exc:                       # noqa: BLE001
        pytest.skip("SKIPPED, NOT PASSED: no media root configured (%s)" % exc)
    if not root.is_dir():
        pytest.skip("SKIPPED, NOT PASSED: the media root %s does not exist on "
                    "this machine. Point TSUBASA_MEDIA at a folder of videos "
                    "to run the real-container checks." % root)
    found = sorted(p for p in root.rglob("*.mkv"))[:6]
    if not found:
        pytest.skip("SKIPPED, NOT PASSED: no .mkv under %s. RUNBOOK 1d names "
                    "'the corpus .mkv fixtures' and the corpus has none -- "
                    "recorded as a Part 1 defect in tsubasa.config.json "
                    "(media.//gap). Point TSUBASA_MEDIA at real videos to run "
                    "these." % root)
    return found


def test_every_real_mkv_reads_through_the_cues_index(real_mkvs):
    """⚠ Print the denominator. '0 failures of 0 files' is a vacuous pass."""
    problems = []
    for path in real_mkvs:
        info = container.read(str(path), allow_ffmpeg=False)
        if not info.ok:
            problems.append((path.name, info.reason))
            continue
        subs = info.subtitle_tracks
        if not subs:
            continue
        for t in subs:
            if t.cues is None:
                problems.append((path.name, "track %s got no timing at all"
                                 % t.number))
            elif t.timing_source != "cues":
                problems.append((path.name,
                                 "track %s took the %s path, not the index"
                                 % (t.number, t.timing_source)))
    assert not problems, "%d of %d real files:\n  %s" % (
        len(problems), len(real_mkvs),
        "\n  ".join("%s -- %s" % (n, w) for n, w in problems[:8]))


def test_real_cue_times_match_the_ffmpeg_extraction_to_a_millisecond(real_mkvs):
    """⭐ The check that makes the synthetic fixtures trustworthy.

    The corpus already holds the `.ass` ffmpeg extracted from these same
    tracks. An independent implementation, produced by different code on a
    different day, is the only thing that can tell 'my reader is right' from
    'my reader and my fixture writer are wrong together'.

    ⚠ Matched by FILE STEM through the dev+validation slices only, so the
    sealed slice is unreachable by construction rather than by care.
    """
    cfg = load_config(ROOT)
    root = corpus_root(cfg, ROOT)
    if not root.is_dir():
        pytest.skip("SKIPPED, NOT PASSED: corpus absent on this machine")

    by_stem = {}
    for _scope, _show, p in iter_corpus_files(cfg, root):
        stem = os.path.splitext(os.path.basename(p))[0]
        by_stem.setdefault(stem, []).append(p)

    from tsubasa import formats

    compared = 0
    problems = []
    for path in real_mkvs:
        stem = path.stem
        # A sidecar beside the video counts too, and it is what lets this run
        # on a fresh clone: `video/Sintel-60s.srt` is ffmpeg's OWN extraction
        # of `video/Sintel-60s.mkv`, so it is still an independent answer.
        beside = [str(p) for p in path.parent.glob(stem + ".*")
                  if p.suffix.lower() in (".ass", ".srt", ".ssa")]
        for ref in beside + by_stem.get(stem, []):
            if os.path.splitext(ref)[1].lower() not in (".ass", ".srt", ".ssa"):
                continue
            parsed = formats.read_file(ref)
            if not parsed.ok or not parsed.cues:
                continue
            info = container.read(str(path), allow_ffmpeg=False)
            if not info.ok:
                problems.append((path.name, info.reason))
                break
            want = sorted(round(c.start, 4) for c in parsed.cues)
            best = None
            for t in info.subtitle_tracks:
                if t.cues and len(t.cues) == len(want):
                    got = sorted(round(c.start, 4) for c in t.cues)
                    worst = max(abs(a - b) for a, b in zip(got, want))
                    if best is None or worst < best[0]:
                        best = (worst, t)
            if best is None:
                problems.append(
                    (path.name, "no track had %d cues; tracks had %s"
                     % (len(want), [len(t.cues or []) for t in
                                    info.subtitle_tracks])))
                break
            compared += 1
            if best[0] > 0.001:
                problems.append((path.name,
                                 "worst start disagreement %.4f s against the "
                                 "ffmpeg extraction" % best[0]))
            break

    if compared == 0:
        pytest.skip("SKIPPED, NOT PASSED: none of the %d real videos had a "
                    "matching extracted subtitle beside them or in the "
                    "dev/validation slices" % len(real_mkvs))
    assert not problems, "%d problem(s) over %d compared file(s):\n  %s" % (
        len(problems), compared,
        "\n  ".join("%s -- %s" % (n, w) for n, w in problems[:8]))


@pytest.fixture(scope="module")
def ffprobe():
    """ffprobe, or a SKIP saying how to supply it.

    ⚠ Found through the product's own resolver -- PATH, then `$TSUBASA_FFMPEG`,
    then the cache dir. ⛔ No path to any particular install is hardcoded here:
    this ships to other people, and `subsync` hardcoding one is the mistake not
    being repeated.
    """
    found = ffmod.find("ffprobe")
    if found is None:
        pytest.skip("SKIPPED, NOT PASSED: ffprobe not found on PATH, in "
                    "$TSUBASA_FFMPEG or in the tsubasa cache directory. Set "
                    "TSUBASA_FFMPEG to a folder containing ffmpeg and ffprobe "
                    "to run the fallback checks.")
    return found


def test_the_ffmpeg_fallback_reads_the_same_cues_as_the_native_reader(
        real_mkvs, ffprobe, monkeypatch):
    """⭐ `07-test-plan.md`: *the fallback is exercised with the native reader
    disabled, so the fallback cannot rot either.*

    Without this the ffmpeg path is **code that never runs in the local
    configuration** -- every real file here is Matroska, so the native reader
    always wins and the fallback is never reached. It would rot silently until
    the first MP4 someone points at it.
    """
    monkeypatch.setenv("TSUBASA_NO_NATIVE_DEMUX", "1")
    path = str(real_mkvs[0])
    slow = container.read(path)
    assert slow.ok, slow.reason
    assert slow.reader == "ffmpeg", (
        "TSUBASA_NO_NATIVE_DEMUX did not disable the native reader; "
        "reader=%s" % slow.reader)
    assert any("TSUBASA_NO_NATIVE_DEMUX" in w for w in slow.warnings), (
        "a switch that makes every read 35x slower must be visible in the "
        "result, not only in the shell: %s" % slow.warnings)

    monkeypatch.delenv("TSUBASA_NO_NATIVE_DEMUX")
    fast = container.read(path, allow_ffmpeg=False)
    assert fast.reader == "matroska"

    native = [t for t in fast.subtitle_tracks if t.cues]
    viaff = [t for t in slow.subtitle_tracks if t.cues]
    assert native and viaff, (len(native), len(viaff))
    assert len(native) == len(viaff), (
        "native saw %d subtitle track(s) with timing, ffmpeg saw %d"
        % (len(native), len(viaff)))

    for a, b in zip(native, viaff):
        assert len(a.cues) == len(b.cues), (
            "native %d cues, ffmpeg %d on track %s of %s"
            % (len(a.cues), len(b.cues), a.number, os.path.basename(path)))
        worst = max(abs(x.start - y.start) for x, y in zip(a.cues, b.cues))
        assert worst <= 0.001, (
            "native and ffmpeg disagree by %.4f s on %s"
            % (worst, os.path.basename(path)))


def test_the_duration_matches_ffprobe(real_mkvs, ffprobe):
    """RUNBOOK 1d: *duration equal to ffprobe's*.

    ⚠ This was recorded as UNRUN at 1d because ffprobe was not installed. It
    is run now. `Info/Duration` is a float in TimestampScale units, so getting
    it wrong is a silent factor-of-something error, not a crash.
    """
    import json
    import subprocess as sp

    problems = []
    for path in real_mkvs:
        ours = container.read(str(path), timing=False,
                              allow_ffmpeg=False).duration
        out = sp.run([ffprobe, "-v", "error", "-print_format", "json",
                      "-show_format", str(path)],
                     stdout=sp.PIPE, stderr=sp.PIPE, timeout=120)
        theirs = json.loads(out.stdout.decode("utf-8", "replace"))
        theirs = float((theirs.get("format") or {}).get("duration"))
        if ours is None:
            problems.append((path.name, "we read no duration at all"))
        elif abs(ours - theirs) > 0.05:
            problems.append((path.name, "we say %.3f s, ffprobe says %.3f s"
                             % (ours, theirs)))
    assert not problems, "%d of %d files:\n  %s" % (
        len(problems), len(real_mkvs),
        "\n  ".join("%s -- %s" % (n, w) for n, w in problems))


def test_the_fast_path_meets_its_measured_budget_on_a_real_file(real_mkvs):
    """RUNBOOK 1d: *≤ 0.2 s per file on the Cues path (measured 0.085 s)*.

    ⚠ A ceiling, deliberately loose, and never pinned to the measurement --
    this runs on other people's machines and CI. The number that matters is
    recorded in the runbook, not asserted here.
    """
    path = str(real_mkvs[0])
    container.read(path, allow_ffmpeg=False)        # warm the page cache
    started = time.time()
    info = container.read(path, allow_ffmpeg=False)
    elapsed = time.time() - started
    subs = [t for t in info.subtitle_tracks if t.timing_source == "cues"]
    if not subs:
        pytest.skip("SKIPPED, NOT PASSED: %s has no index-read subtitle track"
                    % os.path.basename(path))
    assert elapsed < 1.0, (
        "the Cues path took %.3f s on %s (%d cues, %s bytes read); the "
        "runbook's budget is 0.2 s and the measurement was 0.085 s"
        % (elapsed, os.path.basename(path), len(subs[0].cues),
           info.bytes_read))
    assert info.bytes_read < 5_000_000, (
        "the Cues path read %d bytes; the whole point is that it reads tens "
        "of kilobytes" % info.bytes_read)


def test_a_real_file_reads_the_same_answer_both_ways(real_mkvs):
    """⭐ `00-INDEX.md`: an efficiency change must not change the answer --
    against a real muxer's output rather than against our own writer.

    ⚠ The slow path is forced with `use_index=False`, a real option on the
    reader, rather than by editing a copy of the file. A check that mutates
    somebody's media to prove a point is the class `LEDGER-HOT.md` forbids --
    and the option had grown a private copy in the suite, in the bench and in
    an adjudicator probe before it was made part of the product.
    """
    path = str(real_mkvs[0])
    fast = container.read(path, allow_ffmpeg=False)
    indexed = [t for t in fast.subtitle_tracks if t.timing_source == "cues"]
    if not indexed:
        pytest.skip("SKIPPED, NOT PASSED: no index-read track in %s"
                    % os.path.basename(path))

    slow = container.read(path, allow_ffmpeg=False, use_index=False)
    for t in indexed:
        other = slow.track(t.index)
        assert other is not None and other.cues is not None, (
            "the block walk found no track %s" % t.number)
        assert other.timing_source == "blocks", other.timing_source
        assert len(other.cues) == len(t.cues), (
            "index %d cues, block walk %d on track %s of %s"
            % (len(t.cues), len(other.cues), t.number,
               os.path.basename(path)))
        worst = max(abs(a.start - b.start) for a, b in zip(t.cues, other.cues))
        assert worst <= 0.0005, "worst disagreement %.4f s" % worst
