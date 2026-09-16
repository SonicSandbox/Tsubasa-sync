# -*- coding: utf-8 -*-
"""
Bitmap subtitles: PGS (.sup) and VobSub (.idx). RUNBOOK step 1c.

⭐ Promoted to launch by Probe E: 16.7% of a real library is bitmap-only, and
reading their TIMING brings 62.5% within reach of the unchanged verdict. It is
the cheapest large win in the project.

**Timing only. No OCR, no bitmap decode.** The claim under test is that we can
extract cue boundaries from the container structure alone.

⛔ And the other half of the claim: these are a timing REFERENCE and are never
writable. That is enforced structurally -- their cues carry no rewrite spans --
and asserted here so a future change cannot quietly make them writable.

Runs against the REAL corpus: 382 `.sup` and 46 `.idx` files.
"""
import io
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tsubasa import formats                              # noqa: E402
from tsubasa.cues import Outcome                         # noqa: E402
from tsubasa.dev.roundtrip import iter_corpus_files      # noqa: E402
from tsubasa.formats import pgs, vobsub                  # noqa: E402
from tsubasa.paths import corpus_root, load_config       # noqa: E402

MAX_FILES = 60          # enough for a real claim, fast enough for the runner


@pytest.fixture(scope="module")
def bitmap_files():
    cfg = load_config(ROOT)
    root = corpus_root(cfg, ROOT)
    if not root.is_dir():
        pytest.skip("SKIPPED, NOT PASSED: corpus absent on this machine")

    sup, idx = [], []
    for _s, _sh, p in iter_corpus_files(cfg, root):
        ext = os.path.splitext(p)[1].lower()
        if ext == ".sup" and len(sup) < MAX_FILES:
            sup.append(p)
        elif ext == ".idx" and len(idx) < MAX_FILES:
            idx.append(p)
        if len(sup) >= MAX_FILES and len(idx) >= MAX_FILES:
            break
    if not sup and not idx:
        pytest.skip("SKIPPED, NOT PASSED: no bitmap subtitles in dev+validation")
    return sup, idx


# --------------------------------------------------------------------------
# PGS
# --------------------------------------------------------------------------

def test_pgs_files_were_found(bitmap_files):
    """⚠ Print the denominator. '0 failures of 0 files' is a vacuous pass."""
    sup, _idx = bitmap_files
    assert len(sup) >= 5, "only %d .sup files -- too few to claim anything" % len(sup)


def test_every_pgs_file_parses_for_timing(bitmap_files):
    sup, _idx = bitmap_files
    failures = []
    for path in sup:
        with io.open(path, "rb") as fh:
            data = fh.read()
        r = formats.read_bytes(data, filename=path)
        if r.outcome != Outcome.OK:
            failures.append((os.path.basename(path), r.reason))
        elif r.format != "pgs":
            failures.append((os.path.basename(path),
                             "read as %r, not pgs" % r.format))
    assert not failures, "%d of %d .sup files failed:\n  %s" % (
        len(failures), len(sup),
        "\n  ".join("%s -- %s" % (n, w) for n, w in failures[:8]))


def test_pgs_cues_are_sane(bitmap_files):
    """Monotonic, positive duration, plausible count. A parser that returns
    garbage in the right SHAPE passes a mere 'it parsed' check."""
    sup, _idx = bitmap_files
    problems = []
    total_cues = 0
    for path in sup:
        with io.open(path, "rb") as fh:
            r = formats.read_bytes(fh.read(), filename=path)
        if r.outcome != Outcome.OK or not r.cues:
            continue
        total_cues += len(r.cues)
        prev = -1.0
        for c in r.cues:
            if c.end <= c.start:
                problems.append((os.path.basename(path),
                                 "non-positive duration at %.3f" % c.start))
                break
            if c.start < prev:
                problems.append((os.path.basename(path),
                                 "cue starts before the previous one: "
                                 "%.3f after %.3f" % (c.start, prev)))
                break
            if c.start < 0:
                problems.append((os.path.basename(path), "negative start"))
                break
            prev = c.start
    assert total_cues > 0, "no cues at all across %d files" % len(sup)
    assert not problems, problems[:8]


def test_a_pgs_stream_is_recognised_without_its_extension(bitmap_files):
    """Magic bytes, not the filename. A .sup renamed to .srt must still be
    read as PGS rather than decoded as text into an 'empty' file."""
    sup, _idx = bitmap_files
    with io.open(sup[0], "rb") as fh:
        data = fh.read()
    r = formats.read_bytes(data, filename="renamed.srt")
    assert r.format == "pgs", r.format
    assert r.outcome == Outcome.OK


def test_pgs_does_not_read_the_whole_file_as_text(bitmap_files):
    """The failure this guards: a binary stream decoded as latin-1 produces a
    plausible string that parses to zero cues, and the user is told their
    subtitle file is empty."""
    sup, _idx = bitmap_files
    with io.open(sup[0], "rb") as fh:
        r = formats.read_bytes(fh.read(), filename=sup[0])
    assert r.text == u"", "a bitmap stream should carry no decoded text"
    assert r.decoded is None


# --------------------------------------------------------------------------
# VobSub
# --------------------------------------------------------------------------

def test_vobsub_files_were_found(bitmap_files):
    _sup, idx = bitmap_files
    if not idx:
        pytest.skip("SKIPPED, NOT PASSED: no .idx files in dev+validation")
    assert len(idx) >= 3


def test_every_vobsub_index_parses(bitmap_files):
    _sup, idx = bitmap_files
    if not idx:
        pytest.skip("SKIPPED, NOT PASSED: no .idx files in dev+validation")
    failures = []
    counts = []
    for path in idx:
        with io.open(path, "rb") as fh:
            r = formats.read_bytes(fh.read(), filename=path)
        if r.outcome != Outcome.OK:
            failures.append((os.path.basename(path), r.reason))
        else:
            counts.append(len(r.cues))
    assert not failures, failures[:8]
    assert sum(counts) > 0, "every .idx parsed but none produced a cue"


def test_vobsub_end_times_are_flagged_as_derived(bitmap_files):
    """⚠ A VobSub index carries only START times. Reporting the derived ends
    as if they were measured is how a downstream check inherits a fiction."""
    _sup, idx = bitmap_files
    if not idx:
        pytest.skip("SKIPPED, NOT PASSED: no .idx files in dev+validation")
    with io.open(idx[0], "rb") as fh:
        r = formats.read_bytes(fh.read(), filename=idx[0])
    assert any("derived" in w for w in r.warnings), r.warnings


# --------------------------------------------------------------------------
# ⛔ never writable
# --------------------------------------------------------------------------

def test_a_bitmap_subtitle_cannot_be_rewritten(bitmap_files):
    """Structural, not remembered. Its image data is not ours to regenerate,
    so the writer must refuse even when asked directly."""
    sup, idx = bitmap_files
    for path in ([sup[0]] if sup else []) + ([idx[0]] if idx else []):
        with io.open(path, "rb") as fh:
            r = formats.read_bytes(fh.read(), filename=path)
        if r.outcome != Outcome.OK:
            continue
        with pytest.raises(ValueError) as exc:
            formats.rewrite_bytes(r, shift=1.0)
        assert "not writable" in str(exc.value), str(exc.value)


def test_pgs_cues_carry_no_rewrite_spans(bitmap_files):
    sup, _idx = bitmap_files
    with io.open(sup[0], "rb") as fh:
        r = formats.read_bytes(fh.read(), filename=sup[0])
    assert r.cues
    assert all(c.start_span is None and c.end_span is None for c in r.cues)


# --------------------------------------------------------------------------
# synthetic edge cases
# --------------------------------------------------------------------------

def test_a_pgs_stream_with_a_corrupt_segment_resyncs():
    """One corrupt segment in a long stream should cost that segment, not the
    other nine hundred."""
    import struct

    def seg(pts, seg_type, payload):
        return (b"PG" + struct.pack(">I", pts) + struct.pack(">I", 0)
                + bytes([seg_type]) + struct.pack(">H", len(payload)) + payload)

    on = bytes([0, 0, 0, 0, 0, 0, 0, 0x80, 0, 0, 1])   # 11 bytes, 1 object
    off = bytes([0, 0, 0, 0, 0, 0, 0, 0x00, 0, 0, 0])  # 0 objects

    stream = (seg(90000, pgs.PCS, on) + seg(180000, pgs.PCS, off)
              + b"\xde\xad\xbe\xef"
              + seg(270000, pgs.PCS, on) + seg(360000, pgs.PCS, off))
    r = pgs.parse(stream)
    assert len(r.cues) == 2, r.cues
    assert abs(r.cues[0].start - 1.0) < 1e-6
    assert abs(r.cues[1].start - 3.0) < 1e-6


def test_pgs_rejects_a_file_that_is_not_pgs():
    from tsubasa.cues import ParseError
    with pytest.raises(ParseError):
        pgs.parse(b"1\n00:00:01,000 --> 00:00:02,000\nhi\n")


def test_vobsub_rejects_a_file_that_is_not_an_index():
    from tsubasa.cues import ParseError
    with pytest.raises(ParseError):
        vobsub.parse(u"1\n00:00:01,000 --> 00:00:02,000\nhi\n")
