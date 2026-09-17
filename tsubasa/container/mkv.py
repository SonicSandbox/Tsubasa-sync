# -*- coding: utf-8 -*-
"""
Matroska: the native container reader. RUNBOOK step 1d, decision `D2`.

⭐ WHAT THIS BUYS, and it is the whole reason the step exists

The fast path needs three things from a video: its duration, its list of
subtitle tracks, and the block TIMESTAMPS of one of them. None of that is
decoding, and none of it needs ffmpeg. Measured on a real 1.44 GB SubsPlease
MKV (`08-probes.md` §J5/J6):

    ffmpeg extract + ffprobe        3.04 s cold, 1.4 GB read
    pure-Python block walk          7.96 s cold, 0.2 MB read, 88,340 seeks
    ⭐ Cues-indexed walk            0.085 s,     30.5 KB,      5,056 seeks

All three agree to 0.0000 s on all 323 cues. The container already carries an
index of where every subtitle block lives; mkvmerge -- which SubsPlease,
Erai-raws and most groups use -- writes a CuePoint for every subtitle block by
default. **Ask what the format already indexes before walking it.**

🚨 THE GUARD THAT MAKES THE FAST PATH SAFE TO TRUST

A muxer is not *obliged* to index every subtitle block. One that indexes
sparsely hands us a SUBSET of the cues, in perfect shape, with nothing on
screen to say so -- a confidently wrong answer, which `00-INDEX.md` Rule 2
calls worse than no answer, and which would feed alignment a subtitle that is
missing half its lines.

So the Cues result is VERIFIED before it is returned: one cluster -- the one
the index attributes the most subtitle blocks to -- is walked linearly and its
subtitle blocks counted. If the walk finds more than the index claimed, the
index is partial and we fall back to the full block walk.

⚠ And a verification that could not run reports `None`, not `True`.
"An absent answer and an unanswered question are different results"
(`LEDGER.md` §Harness) -- a caller must be able to tell "checked and clean"
from "never checked".

⚠ TEXT IS NEVER READ ON THIS PATH. The block payload is skipped; only its
header is touched. Extraction of a track AS a subtitle file is hato's use and
lands with RUNBOOK 3a -- the seam is `_block_header`, which already returns
where the payload begins.
"""
import os
import struct

from ..cues import Cue

# --------------------------------------------------------------------------
# EBML element IDs, written as they come off the wire WITH their length
# marker -- which is how every Matroska reference writes them, and how
# read_vint(keep_marker=True) returns them.
# --------------------------------------------------------------------------
EBML_HEADER = 0x1A45DFA3
SEGMENT = 0x18538067
SEEK_HEAD = 0x114D9B74
INFO = 0x1549A966
TRACKS = 0x1654AE6B
CLUSTER = 0x1F43B675
CUES = 0x1C53BB6B
CHAPTERS = 0x1043A770

SEEK = 0x4DBB
SEEK_ID = 0x53AB
SEEK_POSITION = 0x53AC

TIMESTAMP_SCALE = 0x2AD7B1
DURATION = 0x4489

TRACK_ENTRY = 0xAE
TRACK_NUMBER = 0xD7
TRACK_TYPE = 0x83
CODEC_ID = 0x86
TRACK_LANGUAGE = 0x22B59C
TRACK_LANGUAGE_BCP47 = 0x22B59D
TRACK_NAME = 0x536E
FLAG_DEFAULT = 0x88
FLAG_FORCED = 0x55AA

CLUSTER_TIMESTAMP = 0xE7
SIMPLE_BLOCK = 0xA3
BLOCK_GROUP = 0xA0
BLOCK = 0xA1
BLOCK_DURATION = 0x9B

CUE_POINT = 0xBB
CUE_TIME = 0xB3
CUE_TRACK_POSITIONS = 0xB7
CUE_TRACK = 0xF7
CUE_CLUSTER_POSITION = 0xF1
CUE_RELATIVE_POSITION = 0xF0

EDITION_ENTRY = 0x45B9
CHAPTER_ATOM = 0xB6
CHAPTER_TIME_START = 0x91
CHAPTER_DISPLAY = 0x80
CHAP_STRING = 0x85

# Matroska TrackType. 0x11 is the one this module exists for.
SUBTITLE = 0x11
TRACK_TYPES = {1: "video", 2: "audio", 3: "complex", 0x10: "logo",
               SUBTITLE: "subtitle", 0x12: "buttons", 0x20: "control",
               0x21: "metadata"}

MAGIC = b"\x1a\x45\xdf\xa3"

# A vint of length n whose value bits are all 1 means "size unknown" -- legal
# for Segment, and for Cluster in a live-muxed or streamed file.
UNKNOWN_SIZE = {1: 0x7F, 2: 0x3FFF, 3: 0x1FFFFF, 4: 0xFFFFFFF,
                5: 0x7FFFFFFFF, 6: 0x3FFFFFFFFFF, 7: 0x1FFFFFFFFFFFF,
                8: 0xFFFFFFFFFFFFFF}

# ⛔ Bounds. Each guards a damaged or hostile file, and each produces a
# REFUSAL naming what was found rather than a crash, a hang, or a huge read.
MAX_STRING = 4096            # a CodecID or TrackName longer than this is damage
MAX_UINT_BYTES = 8           # an integer wider than 8 bytes is not Matroska
MAX_HEADER_ELEMENTS = 4096   # children scanned inside one header element
MAX_CUE_POINTS = 2000000     # CuePoints in one Cues element
MAX_VERIFY_BLOCKS = 20000    # cross-check budget; exceeding it is INCONCLUSIVE
MAX_TOP_LEVEL = 8            # top-level elements searched for the Segment

# ⭐ How many CONSECUTIVE clusters the completeness cross-check walks. One is
# enough to catch an index that THINS a cluster (a keyframe-style indexer);
# it is NOT enough to catch one that skips whole clusters, because the busiest
# indexed cluster is by construction one it did not skip. A contiguous run
# catches both, and the second cluster costs one more header walk.
VERIFY_CLUSTERS = 2


class ContainerError(Exception):
    """The bytes could not be read as Matroska at all.

    ⛔ Not "it had no subtitle tracks". A file that is genuinely Matroska and
    genuinely carries no subtitles is a SUCCESSFUL read of an empty result --
    the same OK-with-zero distinction `formats/__init__.py` exists to hold,
    and the one `subsync` conflated twice.
    """


class _Reader(object):
    """A file handle that counts what it actually touched.

    Not instrumentation for its own sake: this module's claim is an I/O claim,
    and a claim about I/O that is not measured by the thing making it is an
    argument rather than a measurement (`doctrine/evidence`).
    `container --bench` prints these.

    ⚠ Measured 2026-09-08 over ten real files: **~30 KB and ~13,600 seeks**,
    at 0.087 s median. The probe's 5,056 seeks is a DIFFERENT number and not
    a regression -- it read the Cues element sequentially, where `_children`
    seeks to each element it yields. 2.6× the seeks and slightly less wall
    time, on a path already 35× inside its budget, so it is not worth the
    special case. **Recorded because the two figures will otherwise look like
    a regression to whoever compares them next.**
    """

    __slots__ = ("fh", "size", "nread", "nseek")

    def __init__(self, fh, size):
        self.fh = fh
        self.size = size
        self.nread = 0
        self.nseek = 0

    def read(self, n):
        if n < 0:
            raise ContainerError("negative read length %d" % n)
        b = self.fh.read(n)
        self.nread += len(b)
        return b

    def seek(self, pos, whence=0):
        self.nseek += 1
        return self.fh.seek(pos, whence)


# --------------------------------------------------------------------------
# EBML primitives
# --------------------------------------------------------------------------

def read_vint(r, keep_marker=False):
    """EBML variable-size integer -> (value, length), or (None, 0) at EOF.

    `keep_marker` returns the raw bytes as an integer, which is how element
    IDs are written; without it the leading length marker is stripped, which
    is what element SIZES want.
    """
    b = r.read(1)
    if not b:
        return None, 0
    first = b[0]
    if first == 0:
        # No marker bit anywhere in the first byte means a length above 8,
        # which is not legal Matroska -- in practice it means we are reading
        # payload as though it were structure.
        return None, 0
    length = 1
    mask = 0x80
    while not (first & mask):
        mask >>= 1
        length += 1
    rest = r.read(length - 1) if length > 1 else b""
    if len(rest) != length - 1:
        return None, 0
    value = first if keep_marker else (first & (mask - 1))
    for c in rest:
        value = (value << 8) | c
    return value, length


def read_uint(r, n):
    if n > MAX_UINT_BYTES:
        raise ContainerError(
            "an EBML integer declared %d bytes; Matroska allows at most %d"
            % (n, MAX_UINT_BYTES))
    v = 0
    for c in r.read(n):
        v = (v << 8) | c
    return v


def read_float(r, n):
    if n == 4:
        return struct.unpack(">f", r.read(4))[0]
    if n == 8:
        return struct.unpack(">d", r.read(8))[0]
    if n == 0:
        return 0.0
    raise ContainerError(
        "an EBML float declared %d bytes; only 0, 4 and 8 are legal" % n)


def read_string(r, n):
    if n > MAX_STRING:
        raise ContainerError(
            "an EBML string declared %d bytes, over the %d-byte sanity bound"
            % (n, MAX_STRING))
    return r.read(n).decode("utf-8", "replace").rstrip(u"\x00")


class _Element(object):
    """One EBML element: where it starts, where its body starts, how long.

    `size is None` means the element declared an unknown size, which only
    Segment and Cluster may legally do. Carrying `start` as well as `body` is
    what lets a caller re-open an element it was handed -- reconstructing the
    header length afterwards is guesswork and was a bug in the first draft.
    """

    __slots__ = ("id", "size", "start", "body", "clamped")

    def __init__(self, eid, size, start, body, clamped=False):
        self.id = eid
        self.size = size
        self.start = start
        self.body = body
        # ⚠ True when the element declared MORE bytes than its parent or the
        # file has, and `size` was cut down to fit. Reading on is right for
        # most elements; for the track list it means entries are missing
        # (RUNBOOK 3f), so it has to be visible to the caller.
        self.clamped = clamped

    @property
    def end(self):
        return None if self.size is None else self.body + self.size


def _children(r, start, end, budget=MAX_HEADER_ELEMENTS):
    """Yield each child _Element in [start, end).

    ⭐ The read position is checked to ADVANCE on every iteration. A
    zero-length element -- which a damaged file produces readily -- otherwise
    spins here forever on a user's machine with no output and no error. A hang
    is the one failure mode that looks like nothing at all.
    """
    pos = start
    seen = 0
    while pos < end:
        if seen >= budget:
            raise ContainerError(
                "more than %d child elements inside one container element; "
                "refusing to keep walking what is almost certainly payload"
                % budget)
        seen += 1
        r.seek(pos)
        eid, id_len = read_vint(r, keep_marker=True)
        if eid is None:
            return
        size, size_len = read_vint(r)
        if size is None:
            return
        body = pos + id_len + size_len
        if size == UNKNOWN_SIZE.get(size_len):
            # Unknown size at child level: the caller cannot skip past it, so
            # hand it over and stop. Reported, never silently truncated.
            yield _Element(eid, None, pos, body)
            return
        if body + size > end:
            # Declared longer than its parent -- a damaged tail. Yield it
            # clamped so the elements before it are not lost, then stop.
            yield _Element(eid, end - body, pos, body, clamped=True)
            return
        yield _Element(eid, size, pos, body)
        nxt = body + size
        if nxt <= pos:
            raise ContainerError(
                "a container element at byte %d declared size %d and did not "
                "advance the read position -- the file is damaged"
                % (pos, size))
        pos = nxt


def _open_element(r, pos, want_id, limit):
    """The _Element at `pos`, if it is `want_id`. Used to follow a SeekHead."""
    if not (0 <= pos < r.size):
        return None
    r.seek(pos)
    eid, id_len = read_vint(r, keep_marker=True)
    size, size_len = read_vint(r)
    if eid != want_id or size is None:
        return None
    body = pos + id_len + size_len
    room = max(0, limit - body)
    return _Element(eid, min(size, room), pos, body, clamped=size > room)


# --------------------------------------------------------------------------
# the header: Info, Tracks, SeekHead, Chapters
# --------------------------------------------------------------------------

def _read_info(r, el, out):
    for c in _children(r, el.body, el.end):
        if c.size is None:
            break
        r.seek(c.body)
        if c.id == TIMESTAMP_SCALE:
            out["timescale"] = read_uint(r, c.size)
        elif c.id == DURATION:
            out["duration_raw"] = read_float(r, c.size)


def _damaged_tracks(what, where, detail):
    return ContainerError(u"the track list is %s at byte %d (%s), so the tracks "
                          u"it names cannot be trusted" % (what, where, detail))


def _read_tracks(r, el):
    u"""The TrackEntries of a Tracks element. Raises when the list is not WHOLE.

    🚨 RUNBOOK 3f, found by an adversarial pass: this used to stop quietly
    wherever the bytes stopped making sense and return what it had. A file cut
    off inside its track list, or with damage at its second entry, came back
    as a READABLE file with NO or FEWER subtitle tracks -- *"could not read"*
    reported as *"has none"*, which `ContainerError`'s own docstring forbids.
    So a clamped, unknown-size or short-stopping list raises, and the ladder
    falls back to ffmpeg exactly as it does for any walk that cannot finish.
    """
    if el.clamped:
        raise _damaged_tracks(u"cut off", el.start,
                              u"it declares more bytes than the file has")
    tracks = []
    reached = el.body
    for c in _children(r, el.body, el.end):
        if c.size is None:
            raise _damaged_tracks(u"damaged", c.start,
                                  u"an element inside it declares an unknown size")
        if c.clamped:
            raise _damaged_tracks(u"cut off", c.start,
                                  u"an entry runs past the end of the list")
        reached = c.end
        if c.id != TRACK_ENTRY:
            continue
        # ⚠ `eng` IS THE MATROSKA DEFAULT FOR AN ABSENT `Language` ELEMENT, the
        # same way `default` defaults to True just below. It read `""` here,
        # and ffmpeg -- which applies the spec default -- read `eng` for the
        # SAME file, so one video's language depended on which rung of the
        # ladder answered. Measured side by side at RUNBOOK 3f
        # (`_work/probe_3f_1_language_parity.py`).
        t = {"number": None, "type": None, "codec": u"", "language": u"eng",
             "language_bcp47": u"", "name": u"", "default": True,
             "forced": False}
        field_reached = c.body
        for f in _children(r, c.body, c.end):
            if f.size is None:
                raise _damaged_tracks(u"damaged", f.start,
                                      u"a field declares an unknown size")
            if f.clamped:
                raise _damaged_tracks(u"cut off", f.start,
                                      u"a field runs past the end of its entry")
            field_reached = f.end
            r.seek(f.body)
            if f.id == TRACK_NUMBER:
                t["number"] = read_uint(r, f.size)
            elif f.id == TRACK_TYPE:
                t["type"] = read_uint(r, f.size)
            elif f.id == CODEC_ID:
                t["codec"] = read_string(r, f.size)
            elif f.id == TRACK_LANGUAGE:
                # ⚠ An EMPTY element takes its default too (EBML): `eng`.
                t["language"] = read_string(r, f.size) or u"eng"
            elif f.id == TRACK_LANGUAGE_BCP47:
                # ⚠ The newer BCP-47 field WINS when both are present. A file
                # carrying `und` in the legacy field and `ja` here is common,
                # and preferring the legacy one throws the answer away.
                t["language_bcp47"] = read_string(r, f.size)
            elif f.id == TRACK_NAME:
                t["name"] = read_string(r, f.size)
            elif f.id == FLAG_DEFAULT:
                # ⚠ An EMPTY flag is its default, which for FlagDefault is 1.
                t["default"] = bool(read_uint(r, f.size)) if f.size else True
            elif f.id == FLAG_FORCED:
                t["forced"] = bool(read_uint(r, f.size))
        if field_reached != c.end:
            raise _damaged_tracks(u"damaged", field_reached,
                                  u"an entry's fields stop before the entry ends")
        if t["number"] is not None:
            tracks.append(t)
    if reached != el.end:
        raise _damaged_tracks(u"damaged or cut off", reached,
                              u"its entries stop before the list ends")
    return tracks


def _read_seek_head(r, el, seg_start, found, depth=0):
    """Collect {element id: absolute position} from a SeekHead.

    A file may carry a second SeekHead pointing at the first's targets -- the
    normal mkvmerge layout when Cues live at the end. Followed exactly once;
    the depth bound is what stops a file that points at itself.
    """
    nested = []
    for c in _children(r, el.body, el.end):
        if c.size is None or c.id != SEEK:
            continue
        sid = spos = None
        for f in _children(r, c.body, c.end):
            if f.size is None:
                break
            r.seek(f.body)
            if f.id == SEEK_ID:
                sid = read_uint(r, f.size)
            elif f.id == SEEK_POSITION:
                spos = read_uint(r, f.size)
        if sid is None or spos is None:
            continue
        target = seg_start + spos
        if not (0 <= target < r.size):
            continue
        if sid == SEEK_HEAD:
            nested.append(target)
        else:
            found.setdefault(sid, target)
    if depth == 0:
        for target in nested:
            nxt = _open_element(r, target, SEEK_HEAD, r.size)
            if nxt is not None:
                _read_seek_head(r, nxt, seg_start, found, depth + 1)
    return found


def _read_chapters(r, el):
    """Chapter start times in seconds, sorted.

    `06-edge-cases.md` §5.2: *"Chapters marking ad breaks -- free split-point
    hints sitting unused in the container. Seed the split search with them."*
    Free here because the walk is already open at the header.

    🚨 ChapterTimeStart is in NANOSECONDS and does NOT take the timestamp
    scale. It is the one time field in Matroska that does not, and reading it
    like the others is wrong by a factor of a million on a typical file.
    """
    chapters = []
    for ed in _children(r, el.body, el.end):
        if ed.size is None:
            break
        if ed.id != EDITION_ENTRY:
            continue
        for atom in _children(r, ed.body, ed.end):
            if atom.size is None:
                break
            if atom.id != CHAPTER_ATOM:
                continue
            start = None
            name = None
            for f in _children(r, atom.body, atom.end):
                if f.size is None:
                    break
                if f.id == CHAPTER_TIME_START:
                    r.seek(f.body)
                    start = read_uint(r, f.size) / 1e9
                elif f.id == CHAPTER_DISPLAY and name is None:
                    for d in _children(r, f.body, f.end):
                        if d.size is None:
                            break
                        if d.id == CHAP_STRING:
                            r.seek(d.body)
                            name = read_string(r, d.size)
                            break
            if start is not None:
                chapters.append((start, name or u""))
    chapters.sort(key=lambda c: c[0])
    return chapters


# --------------------------------------------------------------------------
# block headers
# --------------------------------------------------------------------------

def _block_header(r, pos):
    """(track_number, relative_timecode, payload_offset) for a Block.

    Only the header is touched. The payload begins at the returned offset --
    the seam a future extractor (hato's, RUNBOOK 3a) would read the text this
    module deliberately does not.

    ⚠ Lacing lives in the flags byte and is not decoded, because it cannot
    change this answer: every frame in a laced block shares the block's
    timecode and the first frame IS at it. Subtitle tracks are unlaced in
    practice, and audio -- which is laced -- is never read here.
    """
    r.seek(pos)
    track, tlen = read_vint(r)
    if track is None:
        return None, None, None
    raw = r.read(3)                        # int16 timecode + 1 flags byte
    if len(raw) != 3:
        return None, None, None
    tc = struct.unpack(">h", raw[:2])[0]
    return track, tc, pos + tlen + 3


def _cluster_timestamp(r, body, end):
    """The cluster's own timestamp.

    Normally the first child, and it was in every file measured -- but
    "normally" is not "always", so it is searched for rather than assumed. The
    scan stops at the first block, which bounds it to a handful of reads.
    """
    for c in _children(r, body, end, budget=64):
        if c.id == CLUSTER_TIMESTAMP and c.size is not None:
            r.seek(c.body)
            return read_uint(r, c.size)
        if c.id in (SIMPLE_BLOCK, BLOCK_GROUP):
            break
    return 0


def _block_in_group(r, group):
    """(block_start, block_size, duration_or_None) inside a BlockGroup."""
    block_at = None
    duration = None
    for g in _children(r, group.body, group.end):
        if g.size is None:
            break
        if g.id == BLOCK:
            block_at = g.body
        elif g.id == BLOCK_DURATION:
            r.seek(g.body)
            duration = read_uint(r, g.size)
    return block_at, duration


# --------------------------------------------------------------------------
# path 1 -- the Cues index
# --------------------------------------------------------------------------

def _read_cue_points(r, cues_el, seg_end, wanted):
    """{track: [(cue_time, cluster_pos, relative_pos)]} from the Cues element.

    Reads the whole Cues element -- 30 KB on the measured file -- and keeps
    only the tracks asked for.
    """
    by_track = {}
    end = min(cues_el.end, seg_end)
    for cp in _children(r, cues_el.body, end, budget=MAX_CUE_POINTS):
        if cp.size is None:
            break
        if cp.id != CUE_POINT:
            continue
        ctime = None
        positions = []
        for f in _children(r, cp.body, cp.end):
            if f.size is None:
                break
            if f.id == CUE_TIME:
                r.seek(f.body)
                ctime = read_uint(r, f.size)
            elif f.id == CUE_TRACK_POSITIONS:
                track = cpos = rpos = None
                for g in _children(r, f.body, f.end):
                    if g.size is None:
                        break
                    r.seek(g.body)
                    if g.id == CUE_TRACK:
                        track = read_uint(r, g.size)
                    elif g.id == CUE_CLUSTER_POSITION:
                        cpos = read_uint(r, g.size)
                    elif g.id == CUE_RELATIVE_POSITION:
                        rpos = read_uint(r, g.size)
                if track is not None and cpos is not None:
                    positions.append((track, cpos, rpos))
        if ctime is None:
            continue
        for track, cpos, rpos in positions:
            if track in wanted:
                by_track.setdefault(track, []).append((ctime, cpos, rpos))
    return by_track


def _cues_from_index(r, points, seg_start, seg_end, timescale):
    """Jump to each indexed block; read its timecode and duration.

    ⚠ The BLOCK is read rather than CueTime being trusted, and the difference
    is the point: CueTime is what the muxer INTENDED, the block header is what
    the file actually contains. On a correct file they agree exactly, which
    makes this the cheapest available check that the index points where it
    says it does.

    Returns (cues, unresolved) -- `unresolved` counts indexed entries that did
    not land on a block at all, which is an index that is not merely sparse
    but wrong, and sends the whole track to the slow walk.
    """
    out = []
    unresolved = 0
    clusters = {}
    for ctime, cpos, rpos in points:
        cl = seg_start + cpos
        if not (seg_start <= cl < seg_end):
            unresolved += 1
            continue
        if cl not in clusters:
            el = _open_element(r, cl, CLUSTER, seg_end)
            if el is None:
                unresolved += 1
                continue
            end = seg_end if el.size is None else min(el.end, seg_end)
            clusters[cl] = (el.body, end, _cluster_timestamp(r, el.body, end))
        cl_body, _cl_end, cl_ts = clusters[cl]

        if rpos is None:
            # No CueRelativePosition: the index gives the time but not the
            # block. Fail OPEN on CueTime -- it is the muxer's own answer and
            # is what a file omitting the position is telling us -- and leave
            # the duration unknown rather than inventing one.
            out.append((ctime * timescale / 1e9, None))
            continue

        r.seek(cl_body + rpos)
        bid, id_len = read_vint(r, keep_marker=True)
        bsize, size_len = read_vint(r)
        if bid is None or bsize is None:
            unresolved += 1
            continue
        bbody = cl_body + rpos + id_len + size_len
        duration = None
        block_at = bbody
        if bid == BLOCK_GROUP:
            block_at, duration = _block_in_group(
                r, _Element(bid, bsize, cl_body + rpos, bbody))
            if block_at is None:
                unresolved += 1
                continue
        elif bid != SIMPLE_BLOCK:
            unresolved += 1
            continue

        _track, tc, _payload = _block_header(r, block_at)
        if tc is None:
            unresolved += 1
            continue
        out.append(((cl_ts + tc) * timescale / 1e9,
                    None if duration is None else duration * timescale / 1e9))
    return out, unresolved


def _verify_index(r, points, seg_start, seg_end, track_number):
    """Is the Cues index COMPLETE for this track, or only a sample of it?

    🚨 The failure this exists for: a muxer that indexes some subtitle blocks
    and not others hands back a perfectly well-formed SUBSET of the subtitle,
    with nothing to distinguish it from the whole. Alignment would then be fed
    a file missing lines nobody knows are missing -- Rule 2's confidently
    wrong answer, arriving through the door we opened for speed.

    The check: start at the cluster the index attributes the most blocks to,
    walk a CONTIGUOUS RUN of clusters linearly, and count their blocks on this
    track. Equal to what the index claims for that same stretch means the
    index is per-block, which is what mkvmerge writes.

    ⚠ The run has to be contiguous, and one cluster is not enough. The busiest
    indexed cluster is, by construction, one the indexer did NOT skip -- so an
    index that omits whole clusters looks perfect there. Walking into the
    neighbour is what makes an omission visible.

    -> (True complete | False partial | None unknown, why)
    ⚠ None is a real answer and must not be read as True.
    """
    if not points:
        return None, u"no indexed blocks to check"

    per_cluster = {}
    for _ctime, cpos, _rpos in points:
        per_cluster[cpos] = per_cluster.get(cpos, 0) + 1
    start_cpos = max(per_cluster.items(), key=lambda kv: kv[1])[0]

    found = 0
    seen = 0
    walked = []
    pos = seg_start + start_cpos
    try:
        for _ in range(VERIFY_CLUSTERS):
            if not (seg_start <= pos < seg_end):
                break
            el = _open_element(r, pos, CLUSTER, seg_end)
            if el is None:
                break
            walked.append(pos - seg_start)
            end = seg_end if el.size is None else min(el.end, seg_end)
            for c in _children(r, el.body, end, budget=MAX_VERIFY_BLOCKS):
                if c.size is None:
                    break
                seen += 1
                if c.id == SIMPLE_BLOCK:
                    track, _tc, _p = _block_header(r, c.body)
                    if track == track_number:
                        found += 1
                elif c.id == BLOCK_GROUP:
                    block_at, _dur = _block_in_group(r, c)
                    if block_at is not None:
                        track, _tc, _p = _block_header(r, block_at)
                        if track == track_number:
                            found += 1
            if el.size is None:
                break                    # an unknown-size cluster has no end
            pos = el.end
    except ContainerError as exc:
        # Either the cluster is bigger than the budget, or it is damaged.
        # Both are "could not check", and neither is "checked and clean".
        return None, (u"the completeness cross-check could not finish after "
                      u"%d element(s) (%s), so the index is UNVERIFIED for "
                      u"track %d, not confirmed" % (seen, exc, track_number))

    if not walked:
        return None, (u"the busiest indexed position (cluster at %d) is not a "
                      u"cluster, so completeness could not be checked"
                      % start_cpos)

    indexed = sum(per_cluster.get(c, 0) for c in walked)
    if found > indexed:
        return False, (u"the Cues index lists %d block(s) for track %d across "
                       u"the %d cluster(s) at %s, but those clusters actually "
                       u"contain %d -- the index is partial, so it would have "
                       u"returned a subtitle missing lines"
                       % (indexed, track_number, len(walked),
                          ", ".join(str(c) for c in walked), found))
    return True, u""


# --------------------------------------------------------------------------
# path 2 -- the linear block walk
# --------------------------------------------------------------------------

def _walk_blocks(r, seg_start, seg_end, wanted, first_cluster):
    """Every block header in every cluster. 88,340 seeks on the measured file.

    The fallback, and the reason the fast path is allowed to be clever: when
    the index is missing, partial or wrong, this reads the same answer the
    slow way, from the blocks themselves.
    """
    out = {t: [] for t in wanted}
    pos = seg_start if first_cluster is None else first_cluster
    while pos < seg_end:
        r.seek(pos)
        eid, id_len = read_vint(r, keep_marker=True)
        if eid is None:
            break
        size, size_len = read_vint(r)
        if size is None:
            break
        body = pos + id_len + size_len
        unknown = size == UNKNOWN_SIZE.get(size_len)
        end = seg_end if unknown else min(body + size, seg_end)

        if eid != CLUSTER:
            if unknown:
                break
            nxt = body + size
            if nxt <= pos:
                break
            pos = nxt
            continue

        cl_ts = 0
        cursor = body
        while cursor < end:
            r.seek(cursor)
            cid, cid_len = read_vint(r, keep_marker=True)
            if cid is None:
                break
            csize, csize_len = read_vint(r)
            if csize is None:
                break
            cbody = cursor + cid_len + csize_len
            if csize == UNKNOWN_SIZE.get(csize_len):
                break
            if cid == CLUSTER:
                # An unknown-size cluster ends where the next one begins.
                break
            if cid == CLUSTER_TIMESTAMP:
                r.seek(cbody)
                cl_ts = read_uint(r, csize)
            elif cid == SIMPLE_BLOCK:
                track, tc, _p = _block_header(r, cbody)
                if track in out and tc is not None:
                    out[track].append((cl_ts + tc, None))
            elif cid == BLOCK_GROUP:
                block_at, duration = _block_in_group(
                    r, _Element(cid, csize, cursor, cbody))
                if block_at is not None:
                    track, tc, _p = _block_header(r, block_at)
                    if track in out and tc is not None:
                        out[track].append((cl_ts + tc, duration))
            nxt = cbody + csize
            if nxt <= cursor:
                break
            cursor = nxt

        if unknown:
            end = cursor
        if end <= pos:
            break
        pos = end
    return out


# --------------------------------------------------------------------------
# cues
# --------------------------------------------------------------------------

def _to_cues(pairs):
    """(start, duration) -> [Cue], sorted by start.

    ⛔ No source spans, and that is structural rather than an omission. A cue
    read out of a container has no character offsets in any file, so
    `cues.retime()` -- which refuses any cue without a span -- cannot be
    talked into rewriting one. The same guarantee `formats/pgs.py` relies on,
    reached the same way.

    ⚠ A block with no BlockDuration gets end == start rather than an invented
    duration. Reporting a derived end as though it were measured is the defect
    the VobSub reader carries an explicit warning for.
    """
    cues = []
    for start, duration in sorted(pairs, key=lambda p: p[0]):
        end = start if duration is None else start + duration
        cues.append(Cue(start, end, u"", None, None, None))
    return cues


# --------------------------------------------------------------------------
# the reader
# --------------------------------------------------------------------------

def _find_segment(r, size):
    u"""The Segment element, and a sentence if the file ends before it does.

    -> (`_Element`, u"" or the incompleteness sentence). Raises ContainerError.
    Skips non-Segment top-level elements rather than assuming position, because
    a leading Void is legal.
    """
    hdr = _open_element(r, 0, EBML_HEADER, size)
    if hdr is None:
        raise ContainerError(
            "the EBML header at offset 0 could not be read as an element")
    pos = hdr.end
    for _ in range(MAX_TOP_LEVEL):
        if not (0 <= pos < size):
            break
        r.seek(pos)
        eid, id_len = read_vint(r, keep_marker=True)
        if eid is None:
            break
        ssize, size_len = read_vint(r)
        if ssize is None:
            break
        body = pos + id_len + size_len
        if eid == SEGMENT:
            unknown = ssize == UNKNOWN_SIZE.get(size_len)
            seg = _Element(eid, (size - body) if unknown
                           else min(ssize, size - body), pos, body)
            incomplete = u""
            if not unknown and body + ssize > size:
                # ⭐ RUNBOOK 3f: the file ENDS BEFORE ITS OWN SEGMENT DOES -- a
                # download in progress, or a cut. Not an error for a read that
                # can still use what is there, but a header-only answer about
                # such a file is an answer about a file that does not exist
                # yet. Reported, never silently dropped.
                incomplete = (u"the file is incomplete: it is %d bytes and its "
                              u"own header says it runs to %d -- still "
                              u"downloading, or cut off" % (size, body + ssize))
            return seg, incomplete
        nxt = body + ssize
        if nxt <= pos:
            break
        pos = nxt
    raise ContainerError(
        "no Segment element found in the first %d top-level elements"
        % MAX_TOP_LEVEL)


def incompleteness(path):
    u"""The sentence `read()` records when a Matroska file ends before its own
    Segment does, from the headers alone. -> u"" when it does not, when the
    Segment's size is unknown, or when the file is not readable Matroska.

    ⭐ For the ffmpeg rung: `container.read` asks this so an incomplete file is
    reported the same whichever reader answered (RUNBOOK 3f).
    """
    size = os.path.getsize(path)
    with open(str(path), "rb") as raw:
        r = _Reader(raw, size)
        if not looks_like_matroska(r.read(4)):
            return u""
        try:
            return _find_segment(r, size)[1]
        except ContainerError:
            return u""


def looks_like_matroska(head):
    """The EBML magic. WebM is Matroska and reads identically here."""
    return head[:4] == MAGIC


def read(path, timing=True, want_types=(SUBTITLE,), use_index=True):
    """Read a Matroska file's structure, and optionally its subtitle timing.

    Returns a plain dict; `container/__init__.py` turns it into the public
    Track/ContainerInfo shapes. Raises ContainerError when the file is not
    readable as Matroska -- the caller decides whether that means ffmpeg.

    `timing=False` reads only the header, which is the cheap probe step A9's
    duration check wants: it never opens a cluster at all.

    `use_index=False` ignores the Cues element and walks every block. It is
    the answer to *"is the fast path telling me the truth about THIS file"*,
    and it exists as a real option rather than as a test helper because three
    separate places -- the suite, the bench and the adjudicator probe -- had
    each grown their own copy of it. ⭐ `doctrine/tooling`: a one-off probe is
    still a harness, and a helper re-derived three times belongs in the
    product.
    """
    size = os.path.getsize(path)
    with open(str(path), "rb") as raw:
        r = _Reader(raw, size)

        head = r.read(4)
        if not looks_like_matroska(head):
            raise ContainerError(
                "not Matroska: expected the EBML magic %r at offset 0, found %r"
                % (MAGIC, head))

        seg, incomplete = _find_segment(r, size)
        seg_start, seg_end = seg.body, min(seg.end, size)

        info = {"timescale": 1000000, "duration_raw": None}
        seek_targets = {}
        track_dicts = []
        tracks_found = False
        chapters = []
        cues_el = None
        first_cluster = None
        warnings = []

        # Walk the Segment's children, stopping at the first Cluster.
        # Everything this module needs lives before it in every real file, and
        # a SeekHead points at whatever does not.
        for c in _children(r, seg_start, seg_end):
            if c.id == CLUSTER:
                first_cluster = c.start
                break
            if c.size is None:
                break
            if c.id == INFO:
                _read_info(r, c, info)
            elif c.id == TRACKS:
                track_dicts = _read_tracks(r, c)
                tracks_found = True
            elif c.id == SEEK_HEAD:
                _read_seek_head(r, c, seg_start, seek_targets)
            elif c.id == CHAPTERS:
                chapters = _read_chapters(r, c)
            elif c.id == CUES:
                cues_el = c

        # Anything the linear scan did not reach, the SeekHead knows about --
        # which is the normal layout for Cues, and for a file whose Tracks
        # element was rewritten after muxing.
        if not tracks_found and TRACKS in seek_targets:
            el = _open_element(r, seek_targets[TRACKS], TRACKS, seg_end)
            if el is not None:
                track_dicts = _read_tracks(r, el)
                tracks_found = True
        if not tracks_found:
            # 🚨 RUNBOOK 3f: NO track list is not an EMPTY track list. Every
            # real video names its tracks; finding none means the walk never
            # reached them -- a Segment of zeros, a size field that lies, a
            # Tracks element after the clusters with nothing pointing at it --
            # and ffmpeg, which scans harder, can often still read them.
            raise ContainerError(
                u"no track list was found in this Matroska file%s"
                % (u" (%s)" % incomplete if incomplete else u""))
        if info["duration_raw"] is None and INFO in seek_targets:
            el = _open_element(r, seek_targets[INFO], INFO, seg_end)
            if el is not None:
                _read_info(r, el, info)
        if not chapters and CHAPTERS in seek_targets:
            el = _open_element(r, seek_targets[CHAPTERS], CHAPTERS, seg_end)
            if el is not None:
                chapters = _read_chapters(r, el)
        if timing and cues_el is None and CUES in seek_targets:
            # Only a TIMING read uses the index; a header read has no reason
            # to seek to the end of a 1.4 GB file for it.
            cues_el = _open_element(r, seek_targets[CUES], CUES, seg_end)

        timescale = info["timescale"] or 1000000
        duration = (None if info["duration_raw"] is None
                    else info["duration_raw"] * timescale / 1e9)

        for t in track_dicts:
            t["kind"] = TRACK_TYPES.get(t["type"], "other")
            if t["language_bcp47"]:
                t["language"] = t["language_bcp47"]
            t.pop("language_bcp47")
            t["cues"] = None
            t["timing_source"] = None
            t["index_verified"] = None

        result = {"format": "matroska", "duration": duration,
                  "timescale": timescale, "tracks": track_dicts,
                  "chapters": chapters, "warnings": warnings,
                  "incomplete": incomplete,
                  "bytes_read": r.nread, "seeks": r.nseek}

        wanted = {t["number"] for t in track_dicts
                  if t["type"] in want_types and t["number"] is not None}
        if not timing or not wanted:
            result["bytes_read"], result["seeks"] = r.nread, r.nseek
            return result

        per_track = {}
        sources = {}
        verified = {}

        if cues_el is not None and use_index:
            points = {}
            try:
                points = _read_cue_points(r, cues_el, seg_end, wanted)
            except ContainerError as exc:
                # Fail OPEN to the block walk. A damaged index is a reason to
                # read the slow way, not a reason to refuse a readable file.
                warnings.append(
                    u"the Cues index could not be read (%s); falling back to "
                    u"the full block walk" % exc)
            for track in sorted(wanted):
                pts = points.get(track)
                if not pts:
                    continue
                complete, why = _verify_index(r, pts, seg_start, seg_end, track)
                if complete is False:
                    warnings.append(why)
                    continue
                cue_pairs, unresolved = _cues_from_index(
                    r, pts, seg_start, seg_end, timescale)
                if unresolved:
                    warnings.append(
                        u"%d of %d indexed entries on track %d did not resolve "
                        u"to a block; reading that track the slow way instead"
                        % (unresolved, len(pts), track))
                    continue
                per_track[track] = cue_pairs
                sources[track] = "cues"
                verified[track] = complete
                if complete is None and why:
                    warnings.append(u"track %d: %s" % (track, why))

        missing = sorted(wanted - set(per_track))
        if missing:
            walked = _walk_blocks(r, seg_start, seg_end, set(missing),
                                  first_cluster)
            for track, raw_pairs in walked.items():
                per_track[track] = [
                    (ts * timescale / 1e9,
                     None if d is None else d * timescale / 1e9)
                    for ts, d in raw_pairs]
                sources[track] = "blocks"
                # A full walk IS the ground truth; there is nothing to verify
                # it against that is cheaper than itself.
                verified[track] = True

        for t in track_dicts:
            n = t["number"]
            if n in per_track:
                t["cues"] = _to_cues(per_track[n])
                t["timing_source"] = sources.get(n)
                t["index_verified"] = verified.get(n)

        result["bytes_read"], result["seeks"] = r.nread, r.nseek
        return result
