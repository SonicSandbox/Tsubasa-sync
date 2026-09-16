# -*- coding: utf-8 -*-
"""
PGS (.sup) -- Presentation Graphic Stream, the Blu-ray bitmap subtitle format.

⭐ RUNBOOK step 1c, PROMOTED to launch: Probe E measured 16.7% of a real library
as bitmap-only, and reading their TIMING brings 62.5% within reach of the
unchanged verdict. It is the cheapest large win in the project.

**No OCR, and no bitmap decode.** A PGS display set begins with a Presentation
Composition Segment carrying a 90 kHz presentation timestamp; a PCS with
objects turns a caption ON and a PCS with none turns it OFF. That is the whole
mechanism -- 25 bytes read per segment, the image data skipped entirely.

⛔ These cues carry NO source spans, and that is deliberate. A bitmap subtitle
is readable as a timing reference and is NEVER writable as text
(spec/06-edge-cases.md §6.1). Because `retime()` refuses any cue without a
span, the architecture cannot be talked into rewriting one -- the guarantee is
structural rather than a rule somebody has to remember.

Provenance: the segment-walking logic was measured against all 380 `.sup` files
in the video-naming corpus -- 0 failures, 0 empty, 0 non-monotonic, 0 negative
durations, at 298 MB/s -- and cross-checked against sibling text tracks of the
same episodes at 98.9-99.5% agreement.
"""
import struct

from ..cues import Cue, ParseError, ParseResult, Outcome

MAGIC = b"PG"
HEADER = 13            # magic(2) + pts(4) + dts(4) + type(1) + length(2)

PCS = 0x16             # presentation composition -- the only one we read
WDS = 0x17
PDS = 0x14
ODS = 0x15
END = 0x80

# Composition states, reported as warnings rather than acted on.
EPOCH_START = 0x80
ACQUISITION = 0x40


def looks_like_pgs(data):
    return data[:2] == MAGIC


def parse(data, decoded=None, filename=None):
    """bytes -> ParseResult. Timing only.

    ⚠ Takes BYTES, not text. Decoding a binary format as text and parsing the
    result is how a bitmap file ends up reported as an empty subtitle.
    """
    if not looks_like_pgs(data):
        raise ParseError(
            "not a PGS stream: expected the bytes 'PG' at offset 0, found %r"
            % data[:2])

    n = len(data)
    i = 0
    cues = []
    open_pts = None
    stats = {"segments": 0, "pcs": 0, "on": 0, "off": 0, "bad_magic": 0,
             "truncated": 0, "epoch": 0, "acquisition": 0, "palette_only": 0}

    while i + HEADER <= n:
        if data[i:i + 2] != MAGIC:
            stats["bad_magic"] += 1
            # Resync rather than abandon: one corrupt segment in a long stream
            # should cost that segment, not the other nine hundred.
            j = data.find(MAGIC, i + 1)
            if j < 0:
                break
            i = j
            continue

        pts = struct.unpack(">I", data[i + 2:i + 6])[0]
        seg_type = data[i + 10]
        seg_len = struct.unpack(">H", data[i + 11:i + 13])[0]
        payload_start = i + HEADER
        payload_end = payload_start + seg_len
        if payload_end > n:
            stats["truncated"] += 1
            break

        stats["segments"] += 1

        if seg_type == PCS and seg_len >= 11:
            stats["pcs"] += 1
            p = data[payload_start:payload_end]
            comp_state = p[7]
            palette_update = p[8]
            n_objects = p[10]

            if comp_state == EPOCH_START:
                stats["epoch"] += 1
            elif comp_state == ACQUISITION:
                stats["acquisition"] += 1
            if palette_update:
                stats["palette_only"] += 1

            # PGS timestamps are 90 kHz ticks.
            seconds = pts / 90000.0

            if n_objects > 0:
                stats["on"] += 1
                if open_pts is None:
                    open_pts = seconds
                else:
                    # An ON with no intervening OFF: the previous caption is
                    # replaced rather than cleared. Close it here.
                    if seconds > open_pts:
                        cues.append((open_pts, seconds))
                    open_pts = seconds
            else:
                stats["off"] += 1
                if open_pts is not None:
                    if seconds > open_pts:
                        cues.append((open_pts, seconds))
                    open_pts = None

        i = payload_end

    warnings = []
    if open_pts is not None:
        warnings.append(u"stream ends with a caption still displayed")
    for key, label in (("bad_magic", u"segments with a bad magic number"),
                       ("truncated", u"truncated segment at end of stream")):
        if stats[key]:
            warnings.append(u"%d %s" % (stats[key], label))

    if stats["segments"] == 0:
        raise ParseError(
            "PGS magic present but no readable segments -- %d bytes" % n)

    out = []
    for idx, (start, end) in enumerate(cues, 1):
        # ⛔ No spans: a bitmap subtitle is a timing reference, never writable.
        out.append(Cue(start, end,
                       u"", index=idx, start_span=None, end_span=None))

    if stats["pcs"] and not out:
        warnings.append(
            u"%d presentation segments but no complete on/off pair"
            % stats["pcs"])

    result = ParseResult(out, u"", decoded, "pgs", Outcome.OK, u"", warnings)
    return result


def sniff_bytes(data):
    return 1.0 if looks_like_pgs(data) else 0.0
