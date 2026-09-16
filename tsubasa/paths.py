# -*- coding: utf-8 -*-
"""
Config discovery and path resolution.

One config file at the project root; every tool walks UP to find it, so they all
run from anywhere.  A config that is wrong about where things live fails at the
worst possible moment -- three features in, mid-diagnosis -- so every resolver
here also reports HOW it resolved, and `tsubasa.dev corpus --stat` prints it.

Traps this module exists to hold shut (LEDGER-HOT.md):

  * Never open a file without an explicit encoding.  A UTF-8 manifest read back
    with the Windows cp1252 default crashed, in a project whose worst bug is an
    encoding assumption.  Every open() below passes encoding=.
  * Never open(path, 'w') on a file you cannot lose.  It truncates on open; if
    the write then raises, the file is zero bytes.  spec/RUNBOOK.md was
    destroyed twice this way in one session.  Use atomic_write_text().
"""
import json
import os
import sys
import tempfile
from pathlib import Path

CONFIG_NAME = "tsubasa.config.json"

# Where the config was found, and how.  Filled by load_config(); printed by
# `corpus --stat` so a wrong config is visible rather than inferred.
_resolution = {}


class ConfigError(RuntimeError):
    """The project config could not be found or is malformed.

    This is a TOOLING fault, not a test failure.  The runner gives it its own
    exit code so the two never look alike -- the oracle's own runner reported a
    missing pytest as `corpus 1`, which reads exactly like one failing test.
    """


def _walk_up_for(name, start):
    d = Path(start).resolve()
    for candidate in [d] + list(d.parents):
        p = candidate / name
        if p.is_file():
            return p
    return None


def find_config(start=None):
    """Locate tsubasa.config.json.

    Walks up from `start` (default: the working directory), then from this
    file's own location.  The second pass is what lets a suite run with its cwd
    anywhere at all -- pytest, an IDE, or a frozen binary.
    """
    tried = []

    first = Path(start) if start else Path.cwd()
    tried.append(str(first))
    found = _walk_up_for(CONFIG_NAME, first)
    how = "walked up from the working directory"

    if found is None:
        here = Path(__file__).resolve().parent
        tried.append(str(here))
        found = _walk_up_for(CONFIG_NAME, here)
        how = "walked up from the tsubasa package"

    if found is None:
        raise ConfigError(
            "%s not found. Looked upward from:\n  %s"
            % (CONFIG_NAME, "\n  ".join(tried))
        )

    _resolution["config"] = str(found)
    _resolution["configHow"] = how
    return found


def load_config(start=None):
    path = find_config(start)
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except json.JSONDecodeError as exc:
        raise ConfigError("%s is not valid JSON: %s" % (path, exc)) from exc


def repo_root(start=None):
    """The directory holding the config.  Every relative path resolves here."""
    return find_config(start).parent


def resolution():
    """How the last load resolved.  For --stat, and for the wiring suite."""
    return dict(_resolution)


# --------------------------------------------------------------------------
# corpus
# --------------------------------------------------------------------------

def corpus_root(cfg=None, start=None):
    """Resolve the corpus root.

    Order: the TSUBASA_CORPUS env var, then the config's defaultRelative
    resolved against the repo root.  Nothing hardcodes a machine -- moving to
    stronger hardware sets the env var and nothing else changes.
    See spec/10-deployment.md.

    Returns the path even when it does not exist; callers report absence
    themselves, because "the corpus is not on this machine" and "the config is
    wrong" are different problems with different fixes.
    """
    cfg = cfg or load_config(start)
    section = cfg["corpus"]

    env_name = section["envVar"]
    env_val = os.environ.get(env_name)
    if env_val:
        _resolution["corpus"] = env_val
        _resolution["corpusHow"] = "%s environment variable" % env_name
        return Path(env_val).expanduser()

    root = (repo_root(start) / section["defaultRelative"]).resolve()
    _resolution["corpus"] = str(root)
    _resolution["corpusHow"] = (
        "config defaultRelative (%s), resolved against the repo root; %s is unset"
        % (section["defaultRelative"], env_name)
    )
    return root


# --------------------------------------------------------------------------
# the oracle
# --------------------------------------------------------------------------

def oracle_root(cfg=None, start=None):
    """Resolve `Workshop/subsync/` -- the reference implementation.

    Same shape as corpus_root: the env var wins, then the config's relative
    path against the repo root. Returns the path even when it does not exist;
    the suites report absence themselves, because "the oracle is not on this
    machine" and "the config is wrong" are different problems.

    ⛔ READ-ONLY, and that is not a convention. subsync's own tests reference
    SubtitleMegaTest by relative path, and subsync shipped a defect where
    `analyze` wrote scratch files inside a corpus its README marks
    do-not-modify.
    """
    cfg = cfg or load_config(start)
    section = cfg.get("oracle")
    if not section:
        raise ConfigError("no 'oracle' section in %s" % CONFIG_NAME)

    env_val = os.environ.get(section["envVar"])
    if env_val:
        _resolution["oracle"] = env_val
        _resolution["oracleHow"] = "%s environment variable" % section["envVar"]
        return Path(env_val).expanduser()

    root = (repo_root(start) / section["defaultRelative"]).resolve()
    _resolution["oracle"] = str(root)
    _resolution["oracleHow"] = (
        "config defaultRelative (%s), resolved against the repo root; %s is unset"
        % (section["defaultRelative"], section["envVar"])
    )
    return root


# --------------------------------------------------------------------------
# real media
# --------------------------------------------------------------------------

def media_root(cfg=None, start=None):
    """Where real VIDEO containers live, for the checks that need one.

    Same shape as corpus_root and oracle_root: the env var wins, then the
    config's relative path against the repo root.

    ⚠ Why this exists at all. RUNBOOK 1d must be proved against a real
    container, and the only real MKVs on the originating machine sat in a
    Desktop folder OUTSIDE the corpus. Hardcoding that path into a suite is
    the thing `HANDOFF.md` explicitly forbids -- so the suite asks here, and a
    machine without media SKIPS with the reason printed rather than passing
    vacuously.

    Returns the path even when it does not exist; the caller reports absence.
    """
    cfg = cfg or load_config(start)
    section = cfg.get("media")
    if not section:
        raise ConfigError("no 'media' section in %s" % CONFIG_NAME)

    env_val = os.environ.get(section["envVar"])
    if env_val:
        _resolution["media"] = env_val
        _resolution["mediaHow"] = "%s environment variable" % section["envVar"]
        return Path(env_val).expanduser()

    root = (repo_root(start) / section["defaultRelative"]).resolve()
    _resolution["media"] = str(root)
    _resolution["mediaHow"] = (
        "config defaultRelative (%s), resolved against the repo root; %s is unset"
        % (section["defaultRelative"], section["envVar"])
    )
    return root


# --------------------------------------------------------------------------
# cache
# --------------------------------------------------------------------------

def cache_root(cfg=None, start=None):
    """Per-user app data.  NEVER beside the media.

    subsync wrote _ref_2.ass and a 500 KB .npy next to the subtitles it was
    aligning, inside a corpus its own README marks do-not-modify.
    spec/02-data-model.md pins the locations below.
    """
    cfg = cfg or load_config(start)
    section = cfg["cache"]

    env_val = os.environ.get(section["envVar"])
    if env_val:
        _resolution["cache"] = env_val
        _resolution["cacheHow"] = "%s environment variable" % section["envVar"]
        return Path(env_val).expanduser()

    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA")
        if base:
            path = Path(base) / "tsubasa"
            how = "%LOCALAPPDATA%\\tsubasa"
        else:
            # LOCALAPPDATA is effectively always set on Windows, but a service
            # account or a stripped environment can lack it.  Degrade to the
            # POSIX shape rather than crashing -- and say which one was used.
            path = Path.home() / ".cache" / "tsubasa"
            how = "~/.cache/tsubasa (LOCALAPPDATA unset on a win32 host)"
    else:
        path = Path.home() / ".cache" / "tsubasa"
        how = "~/.cache/tsubasa"

    _resolution["cache"] = str(path)
    _resolution["cacheHow"] = how
    return path


# --------------------------------------------------------------------------
# writing
# --------------------------------------------------------------------------

def atomic_write_text(path, text, encoding="utf-8", newline="\n"):
    """Write via a temp file and os.replace.  Never truncate the target.

    BITTEN TWICE (LEDGER-HOT.md).  open(path, 'w') truncates the moment it
    opens; if the write then raises -- a surrogate escape, an encoding error, a
    keyboard interrupt -- the file on disk is zero bytes.  spec/RUNBOOK.md was
    destroyed exactly this way twice in one session, and the prose rule written
    after the first occurrence did not prevent the second.

    Also: close the descriptor BEFORE cleanup.  Windows will not unlink a file
    whose handle is open, so a naive cleanup fails silently and litters .tmp
    files beside the user's data (LEDGER.md, Delivery).
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp = tempfile.mkstemp(
        dir=str(path.parent), prefix=".%s." % path.name, suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline=newline) as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        # fdopen's context manager has closed the descriptor by here, so the
        # replace can succeed on Windows.
        os.replace(tmp, str(path))
        tmp = None
    finally:
        if tmp is not None and os.path.exists(tmp):
            os.unlink(tmp)


def atomic_write_bytes(path, data):
    """Byte-exact atomic write. Same guarantees as atomic_write_text.

    Used for subtitle files, where the encoding was decided at READ time and
    must not be re-decided here -- passing bytes through is what keeps a
    Shift-JIS file Shift-JIS.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp = tempfile.mkstemp(
        dir=str(path.parent), prefix=".%s." % path.name, suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, str(path))
        tmp = None
    finally:
        if tmp is not None and os.path.exists(tmp):
            os.unlink(tmp)


def read_json(path):
    """Read JSON with an explicit encoding.  See the module docstring."""
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path, obj):
    atomic_write_text(path, json.dumps(obj, ensure_ascii=False, indent=1) + "\n")
