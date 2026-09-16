# -*- coding: utf-8 -*-
"""
The eight directory layouts. RUNBOOK step A5, `06-edge-cases.md` §3.4.

⭐ THE CLAIM UNDER TEST, and it is a claim about what is ABSENT

Sonic named eight real-world shapes. **Enumerating them is the wrong design —
the ninth would break it.** So there is no layout flag, no mode, and nothing
for the user to declare: discovery walks everything, and **proximity is a
score rather than a rule.**

That means the interesting checks here are not *"layout 4 works"*. They are:

  * layout 5 — a whole tree of subtitles against a whole tree of videos —
    works **because** distance never disqualifies, and
  * layout 8 — subs, films and episodes in ONE folder — works **because**
    films and episodes are separated by parsing, not by a mode.

⚠ Every fixture here is built on a real temp tree, not mocked. A layout test
that never touches a filesystem is testing a data structure.
"""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tsubasa import discover as D                          # noqa: E402


def build(root, tree):
    """`tree` is {relative path: b"" or bytes}. Returns the root."""
    for rel, data in tree.items():
        path = Path(root) / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data if isinstance(data, bytes) else b"x")
    return str(root)


def paired(root):
    """(video item, [candidate subtitle items]) for every video found."""
    items = D.parse_all(D.walk(root))
    cand = D.Candidates(items)
    return [(v, cand.for_video(v)) for v in cand.videos]


def names(items):
    return sorted(os.path.basename(i.path) for i in items)


# ==========================================================================
# the eight shapes
# ==========================================================================

def test_1_film_and_subs_in_one_folder(tmp_path):
    root = build(tmp_path, {
        "Library/Sintel/Sintel.mkv": b"",
        "Library/Sintel/Sintel.srt": b"",
    })
    items = D.parse_all(D.walk(root))
    cand = D.Candidates(items)
    assert len(cand.videos) == 1 and len(cand.subtitles) == 1
    # ⭐ A film has no episode key, so it is NOT in the episode index -- it
    # takes the movie path. That is the design, not a miss.
    assert cand.films() == cand.videos
    assert D.proximity(cand.videos[0], cand.subtitles[0]) == D.SAME_DIR


def test_2_film_with_a_subs_subfolder(tmp_path):
    root = build(tmp_path, {
        "Library/Sintel/Sintel.mkv": b"",
        "Library/Sintel/Subs/Sintel.eng.srt": b"",
    })
    items = D.parse_all(D.walk(root))
    cand = D.Candidates(items)
    assert len(cand.videos) == 1 and len(cand.subtitles) == 1
    assert D.proximity(cand.videos[0], cand.subtitles[0]) == D.PARENT_OR_CHILD


def test_3_series_episodes_and_subs_together(tmp_path):
    root = build(tmp_path, {
        "Show/Show - 01.mkv": b"", "Show/Show - 01.srt": b"",
        "Show/Show - 02.mkv": b"", "Show/Show - 02.srt": b"",
    })
    for video, cands in paired(root):
        assert len(cands) == 1, (video, names(cands))
        assert os.path.splitext(video.name)[0] == \
            os.path.splitext(cands[0].name)[0]


def test_4_series_with_a_season_folder(tmp_path):
    root = build(tmp_path, {
        "Show/S02/Show S02E01.mkv": b"", "Show/S02/Show S02E01.srt": b"",
        "Show/S02/Show S02E02.mkv": b"", "Show/S02/Show S02E02.srt": b"",
    })
    for video, cands in paired(root):
        assert len(cands) == 1, (video, names(cands))
        assert video.key == cands[0].key
        assert video.key[0] == 2, video.key


def test_5_a_tree_of_subs_against_a_tree_of_videos(tmp_path):
    """⭐ The layout that only works because distance never disqualifies.

    Nothing here shares a directory, a parent, or a sibling -- the subtitle
    tree and the video tree meet only at the library root. A design that used
    proximity as a RULE would find nothing at all.
    """
    root = build(tmp_path, {
        "Videos/Show A/Show A - 01.mkv": b"",
        "Videos/Show A/Show A - 02.mkv": b"",
        "Subs/Show A/Show A - 01.srt": b"",
        "Subs/Show A/Show A - 02.srt": b"",
    })
    results = paired(root)
    assert len(results) == 2
    for video, cands in results:
        assert cands, "%s found no candidate across the two trees" % video.name
        # ⚠ SAME_ROOT, not ELSEWHERE. Two sibling trees under one walk root
        # share that root, so 0.0 is effectively unreachable in a single-root
        # scan -- a mutation gating at `> ELSEWHERE` therefore removed nothing
        # and SURVIVED. The property under test is that the lowest tier
        # actually present is still returned.
        assert D.proximity(video, cands[0]) <= D.SAME_ROOT, (
            "the fixture is not actually testing distance: %.2f"
            % D.proximity(video, cands[0]))
        assert D.proximity(video, cands[0]) < D.SIBLING


def test_6_videos_flat_in_one_directory(tmp_path):
    root = build(tmp_path, {
        "Videos/Show A - 01.mkv": b"", "Videos/Show B - 01.mkv": b"",
        "Subs/Show A/Show A - 01.srt": b"", "Subs/Show B/Show B - 01.srt": b"",
    })
    results = paired(root)
    assert len(results) == 2
    for _video, cands in results:
        assert cands


def test_7_a_mix_of_flat_and_foldered(tmp_path):
    root = build(tmp_path, {
        "Videos/Flat Show - 01.mkv": b"",
        "Videos/Foldered Show/Foldered Show - 01.mkv": b"",
        "Subs/Flat Show - 01.srt": b"",
        "Subs/Foldered Show/Foldered Show - 01.srt": b"",
    })
    results = paired(root)
    assert len(results) == 2
    for _video, cands in results:
        assert cands


def test_8_subs_films_AND_shows_in_one_folder(tmp_path):
    """🚨 Everything at once — the shape the design has to make ordinary.

    ⭐ It is not a special case: films and episodes separate themselves by
    PARSING. A name yielding an episode number takes the TV path; one that
    does not takes the movie path. No mode, no flag, no folder convention.
    """
    root = build(tmp_path, {
        "All/Sintel.mkv": b"", "All/Sintel.srt": b"",
        "All/Show - 01.mkv": b"", "All/Show - 01.srt": b"",
        "All/Show - 02.mkv": b"", "All/Show - 02.srt": b"",
        "All/Other Film (2019).mkv": b"", "All/Other Film (2019).srt": b"",
    })
    items = D.parse_all(D.walk(root))
    cand = D.Candidates(items)
    assert len(cand.videos) == 4 and len(cand.subtitles) == 4

    films = {os.path.basename(f.path) for f in cand.films()}
    assert films == {"Sintel.mkv", "Other Film (2019).mkv"}, films

    for video in cand.videos:
        if video.key == (None, None):
            continue                      # the movie path
        cands = cand.for_video(video)
        assert len(cands) == 1, (video.name, names(cands))
        assert cands[0].key == video.key
        # ⚠ And a film's subtitle must NOT be offered to an episode.
        assert "Sintel" not in cands[0].name


# ==========================================================================
# junk tolerance -- expected input, never an error
# ==========================================================================

def test_a_subs_folder_full_of_junk_is_tolerated_silently(tmp_path):
    """surasura's real case (`06-edge-cases.md` §4). Non-subtitle files are
    ignored SILENTLY — an error here would make the normal case look broken.

    ⚠ This passes on EXTENSION, not on the junk filter: `.txt`, `.jpg`,
    `.zip` and `Thumbs.db` never reach `is_junk` at all. A mutation removing
    the junk filter therefore survives here, and rightly — the filter's real
    job is files that DO carry a subtitle extension, which is the next check.
    ⭐ A check can pass through a filter that is not the one it is named for.
    """
    root = build(tmp_path, {
        "Show/Show - 01.mkv": b"",
        "Show/Subs/Show - 01.srt": b"",
        "Show/Subs/readme.txt": b"", "Show/Subs/notes.md": b"",
        "Show/Subs/cover.jpg": b"", "Show/Subs/archive.zip": b"",
        "Show/Subs/Thumbs.db": b"", "Show/Subs/.DS_Store": b"",
        "Show/Subs/desktop.ini": b"",
    })
    items = D.walk(root)
    kinds = sorted(i.name for i in items)
    assert kinds == ["Show - 01.mkv", "Show - 01.srt"], kinds


@pytest.mark.parametrize("junk", [
    "Show - 01.srt.bak", "Show - 01.srt.orig", "Show - 01.srt~",
    "Show - 01.synced.srt", "sample.mkv", "Show - 01-sample.mkv",
    ".hidden.srt",
])
def test_the_files_that_must_be_skipped_are_skipped(tmp_path, junk):
    """⚠ `sample.mkv` is a DECOY, not clutter: a 30-second clip with the right
    name and the wrong content, which pairs plausibly and aligns to nothing.
    `.synced.*` is our own previous output."""
    root = build(tmp_path, {"Show/Show - 01.mkv": b"", "Show/" + junk: b""})
    found = [i.name for i in D.walk(root)]
    assert junk not in found, found


def test_a_real_title_containing_the_word_sample_is_kept(tmp_path):
    """⚠ The other direction. A skip list that matches a substring eats real
    titles — the same class as the decoration vocabulary's `Ja Ja Uma`."""
    root = build(tmp_path, {"Show/Free Samples - 01.mkv": b"",
                            "Show/Sample Kingdom - 02.mkv": b""})
    found = sorted(i.name for i in D.walk(root))
    assert found == ["Free Samples - 01.mkv", "Sample Kingdom - 02.mkv"], found


def test_an_empty_tree_is_an_empty_result_not_an_error(tmp_path):
    assert D.walk(str(tmp_path)) == []
    assert D.Candidates([]).videos == []


def test_a_single_file_path_is_accepted_as_a_root(tmp_path):
    root = build(tmp_path, {"Show/Show - 01.mkv": b""})
    items = D.walk(os.path.join(root, "Show", "Show - 01.mkv"))
    assert len(items) == 1 and items[0].kind == "video"
