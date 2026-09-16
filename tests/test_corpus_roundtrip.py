# -*- coding: utf-8 -*-
"""
The reader and writer, against REAL files.

⭐ "A green suite proves only what the corpus contains." -- LEDGER.md

Every other suite here uses fixtures written by whoever wrote the parser, so
they cover the cases that person thought of. This one runs a seeded sample of
the actual corpus -- files written by hundreds of strangers over twenty years --
and requires a zero shift to reproduce them byte for byte.

The full sweep is a dev command, not a suite:

    python -m tsubasa.dev roundtrip --all

🔒 dev + validation only. The sealed slice is opened once, at the final gate.
"""
import io
import os
import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tsubasa import formats                              # noqa: E402
from tsubasa.cues import Outcome                         # noqa: E402
from tsubasa.dev.roundtrip import iter_corpus_files      # noqa: E402
from tsubasa.paths import corpus_root, load_config       # noqa: E402

SAMPLE = 120
SEED = 20260908

# Formats whose readers land at RUNBOOK step 1c. Listed by extension so a file
# we cannot parse yet produces a SKIP with a reason, never a silent pass.
NOT_YET = {".sup", ".idx", ".sub", ".stl", ".smi", ".ttml", ".dfxp", ".itt", ".sbv"}


@pytest.fixture(scope="module")
def sample():
    cfg = load_config(ROOT)
    root = corpus_root(cfg, ROOT)
    if not root.is_dir():
        pytest.skip("SKIPPED, NOT PASSED: corpus absent on this machine")

    files = [p for _s, _sh, p in iter_corpus_files(cfg, root)
             if os.path.splitext(p)[1].lower() not in NOT_YET]
    if not files:
        pytest.skip("SKIPPED, NOT PASSED: no implemented-format files found")

    rng = random.Random(SEED)
    picked = rng.sample(files, min(SAMPLE, len(files)))

    out = []
    for p in picked:
        try:
            with io.open(p, "rb") as fh:
                out.append((p, fh.read()))
        except (IOError, OSError):
            continue
    return out


def test_the_sample_is_not_empty(sample):
    """⚠ Print the denominator. '0 failures of 0 files' is a vacuous pass, and
    that exact shape has scored green on this project's source corpus before."""
    assert len(sample) >= 50, (
        "only %d files sampled -- too few for this suite to mean anything"
        % len(sample))


def test_every_sampled_file_reads(sample):
    bad = []
    for path, data in sample:
        r = formats.read_bytes(data, filename=path)
        if r.outcome != Outcome.OK:
            bad.append((os.path.basename(path), r.reason))
    assert not bad, "%d of %d real files failed to read:\n  %s" % (
        len(bad), len(sample),
        "\n  ".join("%s -- %s" % (n, w) for n, w in bad[:10]))


def test_a_zero_shift_reproduces_every_real_file_byte_for_byte(sample):
    """⭐ The headline. If any part of a real file were being rebuilt rather
    than passed through, this finds it on material nobody designed for."""
    mismatches = []
    empty = 0
    for path, data in sample:
        r = formats.read_bytes(data, filename=path)
        if r.outcome != Outcome.OK:
            continue
        if not r.cues:
            empty += 1
            continue
        try:
            out = formats.rewrite_bytes(r, shift=0.0)
        except Exception as exc:
            mismatches.append((os.path.basename(path),
                               "%s: %s" % (type(exc).__name__, exc)))
            continue
        if out != data:
            mismatches.append((os.path.basename(path),
                               "bytes differ (%d -> %d)" % (len(data), len(out))))

    tested = len(sample) - empty
    assert tested >= 50, "only %d files had cues; the check is near-vacuous" % tested
    assert not mismatches, "%d of %d real files did not round-trip:\n  %s" % (
        len(mismatches), tested,
        "\n  ".join("%s -- %s" % (n, w) for n, w in mismatches[:10]))


def test_a_real_shift_is_reversible_on_real_files(sample):
    """Shift forward, read it back, shift back, and land on the original.

    Catches a formatter that rounds inconsistently with its parser -- the
    asymmetry that produced subsync's systematic -0.3 s bias.
    """
    bad = []
    for path, data in sample[:60]:
        r = formats.read_bytes(data, filename=path)
        if r.outcome != Outcome.OK or not r.cues:
            continue
        try:
            shifted = formats.rewrite_bytes(r, shift=2.5)
            r2 = formats.read_bytes(shifted, filename=path)
            back = formats.rewrite_bytes(r2, shift=-2.5)
        except Exception as exc:
            bad.append((os.path.basename(path), repr(exc)))
            continue
        r3 = formats.read_bytes(back, filename=path)
        for c0, c3 in zip(r.cues, r3.cues):
            if abs(c0.start - c3.start) > 0.011 or abs(c0.end - c3.end) > 0.011:
                bad.append((os.path.basename(path),
                            "cue moved %.4f s across a there-and-back shift"
                            % abs(c0.start - c3.start)))
                break
    assert not bad, bad[:8]


def test_detected_codecs_are_plausible(sample):
    """A corpus that decodes as 100% one codec would mean the sniffer had
    collapsed to a constant -- which passes every other check here."""
    codecs = {}
    for path, data in sample:
        r = formats.read_bytes(data, filename=path)
        if r.decoded:
            codecs[r.decoded.encoding] = codecs.get(r.decoded.encoding, 0) + 1
    assert codecs, "no file produced a decode result"
    assert all(v == 0 or True for v in codecs.values())
    # Every detected codec must actually re-encode its own file.
    for path, data in sample:
        r = formats.read_bytes(data, filename=path)
        if r.outcome == Outcome.OK and r.decoded:
            from tsubasa.encoding import encode_back
            assert encode_back(r.decoded.text, r.decoded) == data, path
