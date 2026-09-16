# -*- coding: utf-8 -*-
"""
RUNBOOK Step 0 -- prove the wiring end to end, before building anything.

One check per layer, each failure pointing somewhere specific.  A config that
is wrong about where things live otherwise fails at the worst possible moment:
three features in, mid-diagnosis.

Two of these do not merely assert a value -- they reproduce an incident:

  * test_atomic_write_survives_a_crash_mid_write replays the exact failure that
    destroyed spec/RUNBOOK.md TWICE in one session (a script crashing on a
    surrogate escape AFTER open(path,'w') had already truncated the target).
  * test_sealed_slice_is_refused proves the seal is a mechanism rather than a
    sentence in a ledger.
"""
import os
import sys
import unicodedata
from pathlib import Path

import pytest

from tsubasa import __version__
from tsubasa.dev import corpus as corpus_mod
from tsubasa.paths import (
    atomic_write_text,
    cache_root,
    corpus_root,
    find_config,
    load_config,
    media_root,
    repo_root,
)

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def cfg():
    return load_config(ROOT)


# --------------------------------------------------------------------------
# layer 1 -- the config resolves
# --------------------------------------------------------------------------

def test_config_is_found_from_anywhere(tmp_path, monkeypatch):
    """Walking up must work with the cwd somewhere else entirely.

    Asserting it resolves from the repo root would pass even if the walk-up
    were deleted, because the file is sitting right there.
    """
    monkeypatch.chdir(tmp_path)
    found = find_config(Path(__file__).resolve().parent)
    assert found.name == "tsubasa.config.json"
    assert found.parent == ROOT


def test_config_declares_what_the_runner_needs(cfg):
    for key in ("harnessDir", "harnessPattern", "runLogDir", "suites", "excused"):
        assert key in cfg["test"], "test.%s missing from tsubasa.config.json" % key
    assert cfg["test"]["suites"], "no suites registered -- the runner has nothing to run"


def test_package_imports_and_is_versioned():
    assert __version__


# --------------------------------------------------------------------------
# layer 2 -- the corpus is reachable, and is NOT inside the vault
# --------------------------------------------------------------------------

def test_corpus_path_resolves(cfg):
    root = corpus_root(cfg, ROOT)
    assert root.is_absolute()


def test_corpus_is_outside_the_repo(cfg):
    """⛔ Rule 3: no media, no corpora inside TheForge. Ever.

    TheForge auto-commits to Gitea on a ~5 minute timer, and git history has no
    undo -- a gigabyte of video is permanent before anyone notices.  This is the
    mechanical form of that rule; the prose form is in LEDGER-HOT.md.
    """
    root = corpus_root(cfg, ROOT).resolve()
    repo = repo_root(ROOT).resolve()
    assert repo not in root.parents and root != repo, (
        "the corpus resolved to %s, which is INSIDE the repo at %s. "
        "The vault auto-commits; move it out before anything reads it." % (root, repo)
    )


def test_media_root_is_outside_the_repo(cfg):
    """⛔ Rule 3 again, for the media root added at RUNBOOK 1d.

    The container reader needs REAL video to be proved against, and
    TSUBASA_MEDIA is how a machine says where its videos are. Pointed inside
    TheForge it would put gigabytes of video into a vault that auto-commits
    every five minutes, into a history with no undo -- the same shape as the
    key that landed in `Workshop/tsubasa/Key.md` and was minutes from
    permanent.

    ⚠ Checked whether or not the folder exists. A path that is wrong is worth
    refusing before somebody creates it.
    """
    root = media_root(cfg, ROOT).resolve()
    repo = repo_root(ROOT).resolve()
    assert repo not in root.parents and root != repo, (
        "the media root resolved to %s, which is INSIDE the repo at %s. "
        "The vault auto-commits and git history has no undo -- move it out "
        "before anything reads it." % (root, repo)
    )


def test_corpus_is_present_on_this_machine(cfg):
    root = corpus_root(cfg, ROOT)
    if not root.is_dir():
        pytest.skip(
            "SKIPPED, NOT PASSED: the corpus is absent at %s. Set %s or copy it "
            "over (spec/10-deployment.md migration step 2). Every corpus-backed "
            "assertion below is therefore unproven on this machine."
            % (root, cfg["corpus"]["envVar"])
        )
    scopes = list(cfg["corpus"]["split"])
    present = [s for s in scopes if (root / s).is_dir()]
    assert present == scopes, (
        "split scopes missing from the corpus: %s" % sorted(set(scopes) - set(present))
    )


# --------------------------------------------------------------------------
# layer 3 -- the cache resolves somewhere writable, and not beside the media
# --------------------------------------------------------------------------

def test_cache_resolves_and_is_writable(cfg, monkeypatch):
    # ⛔ THE REAL DEFAULT, NOT THE SESSION'S SANDBOX. `conftest.py` points
    # TSUBASA_CACHE at a temp directory for the whole run, and a temp
    # directory satisfies this claim vacuously.
    monkeypatch.delenv("TSUBASA_CACHE", raising=False)
    path = cache_root(cfg, ROOT)
    path.mkdir(parents=True, exist_ok=True)
    probe = path / ".wiring-probe"
    atomic_write_text(probe, "ok")
    assert probe.read_text(encoding="utf-8") == "ok"
    probe.unlink()


def test_cache_is_not_inside_the_corpus(cfg, monkeypatch):
    """subsync wrote a 500 KB .npy beside the subtitles it was reading, inside
    a corpus its own README marks do-not-modify."""
    # ⛔ THE REAL DEFAULT, NOT THE SESSION'S SANDBOX. `conftest.py` points
    # TSUBASA_CACHE at a temp directory for the whole run, and a temp
    # directory satisfies this claim vacuously.
    monkeypatch.delenv("TSUBASA_CACHE", raising=False)
    cache = cache_root(cfg, ROOT).resolve()
    media = corpus_root(cfg, ROOT).resolve()
    assert media not in cache.parents and cache != media


# --------------------------------------------------------------------------
# layer 4 -- the split, and the seal
# --------------------------------------------------------------------------

def test_split_manifest_exists_and_verifies(cfg):
    root = corpus_root(cfg, ROOT)
    if not root.is_dir():
        pytest.skip("SKIPPED, NOT PASSED: corpus absent, split unverifiable here")
    ok, problems, summary = corpus_mod.verify(cfg, root)
    assert ok, "split does not verify:\n  " + "\n  ".join(problems)

    total = sum(summary["totals"].values())
    assert total > 0, "the split is empty -- 0 shows assigned"
    # Derived, never a pinned production count: the corpus grows.
    for name in corpus_mod.SLICES:
        assert summary["totals"][name] > 0, (
            "slice %r is empty of %d shows -- a 60/20/20 split that puts "
            "everything in one bucket is not a split" % (name, total)
        )


def test_assignment_is_deterministic(cfg):
    shares = cfg["corpus"]["shares"]
    key = "naming/Some Show"
    first = corpus_mod.assign(key, shares)
    assert all(corpus_mod.assign(key, shares) == first for _ in range(50))


def test_assignment_is_nfc_stable(cfg):
    """⭐ macOS stores filenames NFD. Without normalization the same show lands
    in a different slice there, silently reshuffling what is sealed the moment
    the project moves to stronger hardware (spec/10-deployment.md §migration).
    """
    shares = cfg["corpus"]["shares"]
    composed = "ポケモン"                      # NFC
    decomposed = unicodedata.normalize("NFD", composed)
    assert composed != decomposed, "picked a title with no NFD form; test is vacuous"

    a = corpus_mod.Show("naming", composed, None)
    b = corpus_mod.Show("naming", decomposed, None)
    assert a.key == b.key
    assert corpus_mod.assign(a.key, shares) == corpus_mod.assign(b.key, shares)


def test_sealed_slice_is_refused(cfg):
    """⛔ The seal is a mechanism, not a sentence.

    If the guard in shows() were deleted this returns a list and the test
    fails -- which is the question doctrine/verification.md says to ask of
    every new check.
    """
    os.environ.pop(cfg["corpus"]["unsealEnvVar"], None)
    with pytest.raises(corpus_mod.SealedSliceError):
        corpus_mod.shows("sealed", cfg=cfg, start=ROOT)
    # ...and not merely because allow_sealed defaults to False:
    with pytest.raises(corpus_mod.SealedSliceError):
        corpus_mod.shows("sealed", allow_sealed=True, cfg=cfg, start=ROOT)


def test_sealed_slice_opens_at_the_final_gate(cfg, monkeypatch):
    """The other half: a guard that always refuses is not a guard either."""
    root = corpus_root(cfg, ROOT)
    if not root.is_dir():
        pytest.skip("SKIPPED, NOT PASSED: corpus absent")
    monkeypatch.setenv(cfg["corpus"]["unsealEnvVar"], cfg["corpus"]["unsealToken"])
    names = corpus_mod.shows("sealed", allow_sealed=True, cfg=cfg, start=ROOT)
    assert len(names) > 0


def test_dev_slice_is_open(cfg):
    root = corpus_root(cfg, ROOT)
    if not root.is_dir():
        pytest.skip("SKIPPED, NOT PASSED: corpus absent")
    names = corpus_mod.shows("dev", cfg=cfg, start=ROOT)
    sealed_free = set(names)
    assert len(sealed_free) == len(names), "duplicate show in the dev slice"
    assert len(names) > 0


def test_slices_are_disjoint(cfg):
    root = corpus_root(cfg, ROOT)
    if not root.is_dir():
        pytest.skip("SKIPPED, NOT PASSED: corpus absent")
    dev = set(corpus_mod.shows("dev", cfg=cfg, start=ROOT))
    val = set(corpus_mod.shows("validation", cfg=cfg, start=ROOT))
    assert not (dev & val), sorted(dev & val)[:5]


# --------------------------------------------------------------------------
# layer 5 -- writing cannot destroy a file it fails to write
# --------------------------------------------------------------------------

def test_atomic_write_survives_a_crash_mid_write(tmp_path):
    """🚨 BITTEN TWICE. This is the incident, replayed.

    spec/RUNBOOK.md was truncated to zero bytes twice in one session, both
    times by a Python script that crashed on a surrogate escape AFTER
    open(path,'w') had already truncated the target.  A lone surrogate is
    unencodable in utf-8, so it raises at exactly the same point.
    """
    target = tmp_path / "precious.md"
    original = "# Do not lose me\n\nseveral lines\nof real content\n"
    atomic_write_text(target, original)

    with pytest.raises(UnicodeEncodeError):
        atomic_write_text(target, "start\udc80end")

    assert target.read_text(encoding="utf-8") == original, (
        "the failed write destroyed the target -- this is the exact defect "
        "atomic_write_text exists to prevent"
    )
    leftovers = [p.name for p in tmp_path.iterdir() if p.name != "precious.md"]
    assert not leftovers, "temp files littered beside the target: %s" % leftovers


def test_atomic_write_round_trips_cjk(tmp_path):
    """An explicit encoding on the way out AND on the way back in.

    A UTF-8 manifest read back with the Windows cp1252 default crashed once, in
    a project whose worst bug is an encoding assumption.
    """
    target = tmp_path / "日本語.txt"
    text = "第113話「うずまきナルト」\n全角ＡＢＣ\n"
    atomic_write_text(target, text)
    assert target.read_text(encoding="utf-8") == text
