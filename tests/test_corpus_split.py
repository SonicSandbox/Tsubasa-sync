# -*- coding: utf-8 -*-
"""
The split, and the seal it protects.

RUNBOOK step 0a.  These drive the real functions against SYNTHETIC manifests,
because verifying only the live corpus proves that today's manifest happens to
be tidy -- not that the checks can see one that is not.

The most important check here is test_a_show_lands_in_one_slice_everywhere.
It guards a leak that was latent when the split was first built (no show name
appeared in two corpus folders) and went LIVE the moment the video-naming
corpus arrived carrying 148 shows that also exist in the jimaku corpus.
"""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tsubasa.dev import corpus as C          # noqa: E402
from tsubasa.paths import corpus_root, load_config, write_json   # noqa: E402


@pytest.fixture(scope="module")
def cfg():
    return load_config(ROOT)


# --------------------------------------------------------------------------
# the leak guard
# --------------------------------------------------------------------------

def test_a_show_lands_in_one_slice_everywhere(cfg):
    """⭐ One show, one slice -- across every corpus folder.

    `naming/` spells a show `00002 Heroic Age`; `video-naming/` spells the same
    show with release tags attached.  If those hash differently the show can be
    dev in one folder and SEALED in another, and we would tune on material the
    held-out slice also contains.  Nothing on screen would say so.
    """
    root = corpus_root(cfg, ROOT)
    if not root.is_dir():
        pytest.skip("SKIPPED, NOT PASSED: corpus absent on this machine")

    data = C.load_manifest(cfg, ROOT)
    placed = {}
    collisions = []
    for scope, buckets in data["scopes"].items():
        for slice_name in C.SLICES:
            for name in buckets[slice_name]:
                key = C.split_key(name)
                prior = placed.get(key)
                if prior and prior[0] != slice_name:
                    collisions.append((key, prior, (slice_name, scope, name)))
                placed.setdefault(key, (slice_name, scope, name))

    assert not collisions, (
        "%d show(s) land in different slices in different corpus folders:\n  "
        % len(collisions)
        + "\n  ".join(
            "%r: %s in %s (%s) vs %s in %s (%s)"
            % (k, a[0], a[1], a[2], b[0], b[1], b[2])
            for k, a, b in collisions[:8]
        )
    )


def test_the_leak_guard_can_actually_fail(cfg):
    """A guard that cannot fail is not a guard.

    Feed the same comparison a manifest that DOES leak, and require it to be
    seen.  Without this, the check above passes forever the moment split_key
    starts returning a constant.
    """
    leaky = {
        "naming": {"dev": ["00002 Heroic Age"], "validation": [], "sealed": []},
        "video-naming": {"dev": [], "validation": [], "sealed": ["Heroic Age [BD]"]},
    }
    placed, collisions = {}, []
    for scope, buckets in leaky.items():
        for slice_name in C.SLICES:
            for name in buckets[slice_name]:
                key = C.split_key(name)
                prior = placed.get(key)
                if prior and prior[0] != slice_name:
                    collisions.append((key, prior, (slice_name, scope, name)))
                placed.setdefault(key, (slice_name, scope, name))
    assert collisions, (
        "the two spellings did not collide, so split_key is not folding them: "
        "%r vs %r" % (C.split_key("00002 Heroic Age"),
                      C.split_key("Heroic Age [BD]"))
    )


# --------------------------------------------------------------------------
# split_key
# --------------------------------------------------------------------------

@pytest.mark.parametrize("a,b", [
    ("00002 Heroic Age", "Heroic Age"),
    ("Akatsuki no Yona [HorribleSubs] [1080]", "Akatsuki no Yona"),
    ("3-Gatsu No Lion", "3-gatsu no lion"),
    ("Arifureta Shokugyou de Sekai Saikyou S2 (01-13) (1080p) [Batch]",
     "Arifureta Shokugyou de Sekai Saikyou S2"),
])
def test_split_key_folds_corpus_spelling_differences(a, b):
    assert C.split_key(a) == C.split_key(b), "%r != %r" % (C.split_key(a), C.split_key(b))


def test_split_key_keeps_genuinely_different_shows_apart():
    """Over-merging is safe for splitting but it is not free -- two unrelated
    shows must still be two keys, or the 60/20/20 stops meaning anything."""
    assert C.split_key("Naruto") != C.split_key("Bleach")
    assert C.split_key("Naruto") != C.split_key("Naruto Shippuuden")


def test_split_key_is_documented_as_split_only():
    """⛔ It over-merges on purpose. If someone reuses it for pairing, Gintama
    and Gintama' become one show and that is a shipped defect."""
    assert C.split_key("Gintama") == C.split_key("Gintama'")
    assert "NEVER use this for pairing" in C.split_key.__doc__


# --------------------------------------------------------------------------
# verify() must SEE a broken manifest, not just bless a good one
# --------------------------------------------------------------------------

def _fake_project(tmp_path, cfg, scopes, shows_on_disk):
    """A throwaway repo + corpus so verify() can be driven against a manifest
    that is deliberately wrong."""
    repo = tmp_path / "repo"
    media = tmp_path / "media"
    repo.mkdir()
    (media / "naming").mkdir(parents=True)
    for name in shows_on_disk:
        (media / "naming" / name).mkdir()

    local = json.loads(json.dumps(cfg))          # deep copy, no aliasing
    local["corpus"]["split"] = {"naming": {"showsAt": "*", "why": "test"}}
    local["corpus"]["fixtures"] = {}
    local["corpus"]["defaultRelative"] = "../media"
    (repo / "tsubasa.config.json").write_text(
        json.dumps(local, ensure_ascii=False), encoding="utf-8")

    write_json(repo / local["corpus"]["splitManifest"], {
        "version": C.MANIFEST_VERSION, "generated": "test",
        "algorithm": C.ALGORITHM, "shares": local["corpus"]["shares"],
        "scopes": scopes,
    })
    return repo, media, local


def test_verify_sees_a_show_in_two_slices(tmp_path, cfg):
    scopes = {"naming": {"dev": ["Alpha"], "validation": ["Alpha"], "sealed": []}}
    repo, media, local = _fake_project(tmp_path, cfg, scopes, ["Alpha"])
    ok, problems, _s = C.verify(local, media, start=repo)
    assert not ok
    assert any("BOTH" in p for p in problems), problems


def test_verify_sees_a_show_on_disk_but_in_no_slice(tmp_path, cfg):
    """The scrape is still growing. An unassigned show is a silent hole."""
    scopes = {"naming": {"dev": ["Alpha"], "validation": [], "sealed": []}}
    repo, media, local = _fake_project(tmp_path, cfg, scopes, ["Alpha", "Beta"])
    ok, problems, _s = C.verify(local, media, start=repo)
    assert not ok
    assert any("Beta" in p and "no slice" in p for p in problems), problems


def test_verify_sees_a_manifest_show_missing_from_disk(tmp_path, cfg):
    scopes = {"naming": {"dev": ["Alpha", "Ghost"], "validation": [], "sealed": []}}
    repo, media, local = _fake_project(tmp_path, cfg, scopes, ["Alpha"])
    ok, problems, _s = C.verify(local, media, start=repo)
    assert not ok
    assert any("Ghost" in p and "not on disk" in p for p in problems), problems


def test_verify_sees_a_hand_edited_assignment(tmp_path, cfg):
    """Moving a show between slices by hand is how a seal quietly reopens."""
    shares = cfg["corpus"]["shares"]
    name = "Alpha"
    correct = C.assign(C.Show("naming", name, None).key, shares)
    wrong = next(s for s in C.SLICES if s != correct)

    scopes = {"naming": {s: [] for s in C.SLICES}}
    scopes["naming"][wrong] = [name]
    repo, media, local = _fake_project(tmp_path, cfg, scopes, [name])
    ok, problems, _s = C.verify(local, media, start=repo)
    assert not ok
    assert any("algorithm places it in" in p for p in problems), problems


def test_verify_passes_a_correct_manifest(tmp_path, cfg):
    """...and the inverse, or every check above could be an always-fail."""
    shares = cfg["corpus"]["shares"]
    names = ["Alpha", "Beta", "Gamma", "Delta"]
    scopes = {"naming": {s: [] for s in C.SLICES}}
    for n in names:
        scopes["naming"][C.assign(C.Show("naming", n, None).key, shares)].append(n)
    repo, media, local = _fake_project(tmp_path, cfg, scopes, names)
    ok, problems, summary = C.verify(local, media, start=repo)
    assert ok, problems
    assert summary["totals"]["dev"] + summary["totals"]["validation"] \
        + summary["totals"]["sealed"] == len(names)
