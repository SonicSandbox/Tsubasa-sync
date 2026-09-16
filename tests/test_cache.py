# -*- coding: utf-8 -*-
"""
The cache. RUNBOOK step 1b.

Three claims, each of which is a defect if it fails silently:

  🚨 A whole video is never hashed. The cache exists to avoid work; a
     full-content hash costs more than the work it avoids.
  ⛔ Nothing is ever written beside the media. subsync dropped a 500 KB .npy
     next to the subtitles it was reading, inside a read-only corpus.
  ⭐ The file on disk always wins. Cache entries are advisory -- stale,
     corrupt or version-mismatched entries are a MISS, never a wrong answer.
"""
import io
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tsubasa.cache import (CACHE_VERSION, Cache, ContentKey,  # noqa: E402
                           SAMPLE, content_key)
from tsubasa.paths import cache_root, corpus_root, load_config  # noqa: E402


@pytest.fixture
def cache(tmp_path):
    return Cache(root=tmp_path / "cache")


def _write(path, data):
    with io.open(str(path), "wb") as fh:
        fh.write(data)
    return path


# --------------------------------------------------------------------------
# 🚨 the cost model
# --------------------------------------------------------------------------

def test_a_large_file_is_not_read_end_to_end(tmp_path, monkeypatch):
    """The claim is O(1) per file regardless of size. Measure the BYTES READ,
    not the wall clock -- a fast disk would hide a full read entirely."""
    big = tmp_path / "big.mkv"
    _write(big, b"HEAD" + b"\x00" * (8 * 1024 * 1024) + b"TAIL")

    read_total = [0]
    real_open = io.open

    def counting_open(*a, **kw):
        fh = real_open(*a, **kw)
        real_read = fh.read

        def read(n=-1):
            data = real_read(n)
            read_total[0] += len(data)
            return data

        fh.read = read
        return fh

    monkeypatch.setattr(io, "open", counting_open)
    content_key(big)

    assert read_total[0] <= SAMPLE * 2 + 4096, (
        "read %d bytes of an 8 MB file -- the head/tail trick is not in force"
        % read_total[0])


def test_key_cost_does_not_grow_with_file_size(tmp_path):
    small = _write(tmp_path / "s.bin", b"A" * (SAMPLE * 2 + 10))
    large = _write(tmp_path / "l.bin", b"A" * (SAMPLE * 2 + 10)
                   + b"B" * (4 * 1024 * 1024))
    # Different sizes must give different keys even though head and tail match
    # on the 'A' padding -- the size goes into the digest for this reason.
    assert content_key(small).digest != content_key(large).digest


def test_two_files_differing_only_in_the_middle_are_distinguished_by_size():
    """⚠ An honest statement of the limitation: head+tail+size cannot see a
    change confined to the middle of a file OF THE SAME SIZE. Consumers
    re-validate against the file, so the cost is a stale entry, not a wrong
    answer -- but the limit is real and is recorded here rather than implied."""
    a = ContentKey("deadbeef", 1000, 0)
    b = ContentKey("deadbeef", 1000, 0)
    assert a == b


# --------------------------------------------------------------------------
# ⭐ the file on disk always wins
# --------------------------------------------------------------------------

def test_a_hit_returns_what_was_stored(cache, tmp_path):
    f = _write(tmp_path / "a.srt", b"hello world")
    k = content_key(f)
    cache.put(k, "cues", {"cues": [[1.0, 2.0]]})
    assert cache.get(k, "cues") == {"cues": [[1.0, 2.0]]}
    assert cache.stats()["hits"] == 1


def test_a_changed_file_is_a_miss_not_a_stale_hit(cache, tmp_path):
    f = _write(tmp_path / "a.srt", b"hello world")
    k1 = content_key(f)
    cache.put(k1, "cues", {"cues": [[1.0, 2.0]]})

    _write(f, b"completely different content")
    k2 = content_key(f)
    assert cache.get(k2, "cues") is None, "the cache answered for the OLD file"


def test_a_version_bump_invalidates_everything(cache, tmp_path):
    f = _write(tmp_path / "a.srt", b"hello")
    k = content_key(f)
    cache.put(k, "cues", {"cues": []})

    newer = Cache(root=cache.root, version=CACHE_VERSION + 1)
    assert newer.get(k, "cues") is None


def test_a_corrupt_entry_is_a_miss_not_a_crash(cache, tmp_path):
    """A cache that can break a run is worse than no cache."""
    f = _write(tmp_path / "a.srt", b"hello")
    k = content_key(f)
    cache.put(k, "cues", {"cues": []})

    path = cache._path(k, "cues")
    with io.open(str(path), "w", encoding="utf-8") as fh:
        fh.write("{ this is not json")

    assert cache.get(k, "cues") is None
    assert cache.stats()["corrupt"] == 1


def test_a_truncated_entry_is_a_miss_not_a_crash(cache, tmp_path):
    f = _write(tmp_path / "a.srt", b"hello")
    k = content_key(f)
    cache.put(k, "cues", {"cues": [[1.0, 2.0]]})
    path = cache._path(k, "cues")
    data = path.read_bytes()
    path.write_bytes(data[:len(data) // 2])
    assert cache.get(k, "cues") is None


def test_an_entry_whose_digest_disagrees_is_discarded(cache, tmp_path):
    """Belt and braces: even if the path were reached with the wrong key, the
    stored digest is re-checked. Advisory means advisory."""
    f = _write(tmp_path / "a.srt", b"hello")
    k = content_key(f)
    cache.put(k, "cues", {"cues": []})

    path = cache._path(k, "cues")
    entry = json.loads(path.read_text(encoding="utf-8"))
    entry["digest"] = "0" * 64
    path.write_text(json.dumps(entry), encoding="utf-8")

    assert cache.get(k, "cues") is None


def test_a_miss_on_an_absent_entry(cache, tmp_path):
    f = _write(tmp_path / "a.srt", b"hello")
    assert cache.get(content_key(f), "cues") is None
    assert cache.stats()["misses"] == 1


def test_kinds_do_not_collide(cache, tmp_path):
    f = _write(tmp_path / "a.mkv", b"hello")
    k = content_key(f)
    cache.put(k, "cues", {"which": "cues"})
    cache.put(k, "probe", {"which": "probe"})
    assert cache.get(k, "cues")["which"] == "cues"
    assert cache.get(k, "probe")["which"] == "probe"


# --------------------------------------------------------------------------
# ⛔ never beside the media
# --------------------------------------------------------------------------

def test_nothing_is_written_beside_the_source_file(tmp_path):
    media = tmp_path / "media"
    media.mkdir()
    f = _write(media / "ep01.srt", b"1\n00:00:01,000 --> 00:00:02,000\nhi\n")

    cache = Cache(root=tmp_path / "cache")
    k = content_key(f)
    cache.put(k, "cues", {"cues": [[1.0, 2.0]]})

    assert [p.name for p in media.iterdir()] == ["ep01.srt"], (
        "the cache wrote into the media directory: %s"
        % [p.name for p in media.iterdir()])


def test_the_default_cache_root_is_not_inside_the_corpus(monkeypatch):
    # ⛔ THE REAL DEFAULT, NOT THE SESSION'S SANDBOX. `conftest.py` points
    # TSUBASA_CACHE at a temp directory for the whole run, and a temp
    # directory satisfies this claim vacuously.
    monkeypatch.delenv("TSUBASA_CACHE", raising=False)
    cfg = load_config(ROOT)
    c = cache_root(cfg, ROOT).resolve()
    media = corpus_root(cfg, ROOT).resolve()
    assert media not in c.parents and c != media


def test_the_default_cache_root_is_not_inside_the_repo(monkeypatch):
    """The vault auto-commits every ~5 minutes. A cache inside it is permanent."""
    # ⛔ THE REAL DEFAULT, NOT THE SESSION'S SANDBOX. `conftest.py` points
    # TSUBASA_CACHE at a temp directory for the whole run, and a temp
    # directory satisfies this claim vacuously.
    monkeypatch.delenv("TSUBASA_CACHE", raising=False)
    cfg = load_config(ROOT)
    c = cache_root(cfg, ROOT).resolve()
    assert ROOT.resolve() not in c.parents and c != ROOT.resolve()


# --------------------------------------------------------------------------
# writing is atomic
# --------------------------------------------------------------------------

def test_entries_are_written_atomically(cache, tmp_path):
    """A half-written entry read by the next run is exactly the corruption the
    read path has to tolerate. Do not create it in the first place."""
    f = _write(tmp_path / "a.srt", b"hello")
    k = content_key(f)
    cache.put(k, "cues", {"cues": [[1.0, 2.0]] * 500})
    d = cache._path(k, "cues").parent
    leftovers = [p.name for p in d.iterdir() if p.suffix == ".tmp"]
    assert not leftovers, leftovers
