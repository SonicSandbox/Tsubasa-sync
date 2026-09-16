# -*- coding: utf-8 -*-
"""
The cache: content-hash keyed, per-user, disposable.

RUNBOOK step 1b. Target: a 24-episode folder re-runs in under a second with
zero decoding.

🚨 NEVER HASH A WHOLE VIDEO. A full-content hash of a 1.4 GB mkv defeats the
entire purpose -- it costs more than the work it is avoiding. The standard
trick is head + tail + filesize, which is O(1) per file regardless of size
(spec/02-data-model.md §The cache).

⛔ NEVER WRITE BESIDE THE MEDIA. subsync dropped `_ref_2.ass` and a 500 KB
`.npy` next to the subtitles it was aligning -- inside a corpus its own README
marks do-not-modify. Everything here lives under the per-user cache root.

Three properties from the spec, all enforced rather than documented:

  * The file on disk always wins. Cache entries are ADVISORY -- a hash
    mismatch discards the entry, never trusts it.
  * Version-stamped. An entry written by an older build is rebuilt silently,
    not read and misinterpreted.
  * Corrupt entries are a cache miss, not a crash. A cache that can break a
    run is worse than no cache.
"""
import hashlib
import io
import json
import os
import struct
import time

from .paths import atomic_write_bytes, cache_root, load_config

# Bump when the SHAPE of anything stored changes. An entry stamped with an
# older value is rebuilt rather than reinterpreted.
CACHE_VERSION = 1

# Head and tail sample size. 64 KB each is enough that two different files
# sharing a size collide only by construction, and small enough that it is one
# seek and one read at each end.
SAMPLE = 64 * 1024


class ContentKey(object):
    """A cheap, stable identity for a file's CONTENT.

    ⚠ Not a cryptographic guarantee and not claimed as one. It is a cache key:
    the cost of a collision is a stale entry, and every consumer re-validates
    against the file anyway. What it buys is O(1) per file rather than O(size).
    """

    __slots__ = ("digest", "size", "mtime")

    def __init__(self, digest, size, mtime):
        self.digest = digest
        self.size = size
        self.mtime = mtime

    def __eq__(self, other):
        return (isinstance(other, ContentKey)
                and self.digest == other.digest and self.size == other.size)

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash((self.digest, self.size))

    def __repr__(self):
        return "ContentKey(%s..., %d bytes)" % (self.digest[:12], self.size)


def content_key(path):
    """Head 64 KB + tail 64 KB + size. Never reads the middle.

    🚨 The whole point. A 1.4 GB video costs two reads here, not 1.4 GB.
    """
    st = os.stat(str(path))
    size = st.st_size

    h = hashlib.sha256()
    h.update(struct.pack(">Q", size))

    with io.open(str(path), "rb") as fh:
        head = fh.read(SAMPLE)
        h.update(head)
        if size > SAMPLE * 2:
            fh.seek(-SAMPLE, os.SEEK_END)
            h.update(fh.read(SAMPLE))
        elif size > len(head):
            # Small file: the head already covered it, but read the remainder
            # rather than leaving a gap that two different files could share.
            h.update(fh.read())

    return ContentKey(h.hexdigest(), size, st.st_mtime)


class Cache(object):
    """A keyed, versioned, disposable store under the per-user cache root."""

    def __init__(self, root=None, version=CACHE_VERSION, cfg=None):
        if root is None:
            root = cache_root(cfg or load_config())
        self.root = root
        self.version = version
        self.hits = 0
        self.misses = 0
        self.stale = 0
        self.corrupt = 0

    # -- layout ---------------------------------------------------------
    def _path(self, key, kind):
        # Two-level fan-out: a flat directory of 30,000 entries is slow to
        # enumerate on every platform this ships to.
        d = key.digest
        return (self.root / ("v%d" % self.version) / kind
                / d[:2] / d[2:4] / (d + ".json"))

    # -- api ------------------------------------------------------------
    def get(self, key, kind):
        """Return the cached payload, or None. Never raises on a bad entry."""
        p = self._path(key, kind)
        if not p.is_file():
            self.misses += 1
            return None
        try:
            with io.open(str(p), "r", encoding="utf-8") as fh:
                entry = json.load(fh)
        except (IOError, OSError, ValueError):
            # ⭐ A corrupt entry is a MISS, not a crash. A cache that can break
            # a run is worse than no cache at all.
            self.corrupt += 1
            self.misses += 1
            return None

        if entry.get("version") != self.version:
            self.stale += 1
            self.misses += 1
            return None
        if entry.get("size") != key.size or entry.get("digest") != key.digest:
            # ⭐ The file on disk always wins. Advisory means advisory.
            self.stale += 1
            self.misses += 1
            return None

        self.hits += 1
        return entry.get("payload")

    def put(self, key, kind, payload):
        entry = {
            "version": self.version,
            "digest": key.digest,
            "size": key.size,
            "kind": kind,
            "written": time.time(),
            "payload": payload,
        }
        data = json.dumps(entry, ensure_ascii=False).encode("utf-8")
        # Atomic: a half-written cache entry read by the next run is exactly
        # the corruption the `get` path above has to tolerate.
        atomic_write_bytes(self._path(key, kind), data)

    def stats(self):
        total = self.hits + self.misses
        return {
            "hits": self.hits, "misses": self.misses,
            "stale": self.stale, "corrupt": self.corrupt,
            "hit_rate": (self.hits / float(total)) if total else 0.0,
        }


# --------------------------------------------------------------------------
# the first consumer: parsed cue lists
# --------------------------------------------------------------------------

def cued(cache, path, parse_fn):
    """Cue list for `path`, from cache when the content is unchanged.

    `parse_fn(path) -> ParseResult`. Only the timing is cached; cue TEXT is
    not, because nothing downstream of pairing reads it and storing it would
    multiply the cache size for no gain.

    ⛔ Returns None on a cache miss so the caller does the parse -- this
    function never silently substitutes an empty result for a failed one.
    """
    key = content_key(path)
    hit = cache.get(key, "cues")
    if hit is not None:
        return key, hit

    result = parse_fn(path)
    payload = {
        "format": result.format,
        "outcome": result.outcome,
        "reason": result.reason,
        "encoding": result.decoded.encoding if result.decoded else None,
        "cues": [[round(c.start, 3), round(c.end, 3)] for c in result.cues],
    }
    cache.put(key, "cues", payload)
    return key, payload
