# -*- coding: utf-8 -*-
"""Put the repo root on sys.path so suites import `tsubasa` without an install.

And point the per-user store at a throwaway directory for the whole session --
see `isolate_the_per_user_store` below.
"""
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture(scope="session", autouse=True)
def isolate_the_per_user_store(tmp_path_factory):
    """Every suite gets its own cache, trash and results root.

    RUNBOOK 3a-bis. Two things live under `paths.cache_root()` that a test run
    must never touch: the trash `dedupe.py` sends losers to, and -- from
    3a-bis -- the results DB `sync()` consults to decide whether a video has
    ALREADY been synced.

    ⛔ The second one is the reason this is autouse rather than opt-in. A suite
    that writes real records leaves the developer's own history holding
    fixtures, and the next real run over their library would consult it. The
    blast radius of forgetting `results=` once is somebody else's media.

    ⚠ It also closes a hole that was already open: `sync()` falls back to
    `_default_trash_root()` under this same root whenever a check forgets
    `trash_root=`, so a forgotten argument has been writing into
    `%LOCALAPPDATA%\\tsubasa` all along.

    ⭐ The FOUR checks that assert something about the REAL default clear this
    variable themselves -- two in `test_cache.py`, two in `test_wiring.py` --
    because *"the cache is not inside the repo"* is a claim about the shipped
    resolver and a temp directory would satisfy it vacuously. ⚠ They were
    already vacuous for any developer who happened to have the variable set.
    """
    root = tmp_path_factory.mktemp("per-user-store")
    before = os.environ.get("TSUBASA_CACHE")
    os.environ["TSUBASA_CACHE"] = str(root)
    yield root
    if before is None:
        os.environ.pop("TSUBASA_CACHE", None)
    else:
        os.environ["TSUBASA_CACHE"] = before
