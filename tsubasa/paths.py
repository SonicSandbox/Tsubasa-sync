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
import errno
import json
import os
import secrets
import sys
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

#: The cache override, when no project config names one.
CACHE_ENV_VAR = "TSUBASA_CACHE"


def cache_root(cfg=None, start=None):
    """Per-user app data.  NEVER beside the media.

    subsync wrote _ref_2.ass and a 500 KB .npy next to the subtitles it was
    aligning, inside a corpus its own README marks do-not-modify.
    spec/02-data-model.md pins the locations below.

    ===================================================================
    🚨 NO CONFIG REQUIRED — AND 0.1.0 SHIPPED REQUIRING ONE
    ===================================================================

    This read `cfg or load_config(start)`, and `load_config` walks up from
    the working directory and from this package looking for
    `tsubasa.config.json` — the DEVELOPMENT config at the repository root,
    which no installed copy has. So `pip install tsubasa-sync` followed by
    `sync(scan(folder))` raised `ConfigError` for every user, and so did the
    results store and the cache, all of which come through here.

    ⛔ Nothing caught it before publication, because nothing ran outside a
    checkout: every suite, every CI job and every example found the config by
    walking up from the source tree. The frozen-app and wheel jobs DID run
    outside it — and called only `scan()` and `self_check()`, neither of
    which reaches here. Found by running the usage guide's examples against
    the package installed from PyPI, after 0.1.0 was already public.

    ⭐ The config's cache section only ever named the override variable; the
    locations below were always built in. A caller holding a config still has
    its `envVar` honoured, so the development tools are unchanged.
    """
    section = (cfg or {}).get("cache") or {}
    env_name = section.get("envVar") or CACHE_ENV_VAR

    env_val = os.environ.get(env_name)
    if env_val:
        _resolution["cache"] = env_val
        _resolution["cacheHow"] = "%s environment variable" % env_name
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

    fd, tmp = _temporary(str(path.parent), path.name)
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

    ⚠ It REPLACES a file that is there -- `sync()`'s own ownership rules decide
    that first. A caller that must never replace one uses `write_new_bytes`.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp = _temporary(str(path.parent), path.name)
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


#: ⭐ How many names a temporary file tries before giving up (hato 14z, A-1). A few,
#: never `tempfile.TMP_MAX` -- which is 2**31 on Windows.
_TEMP_TRIES = 8

#: How much of the target's name a temporary carries, so a killed run's leftover says
#: whose it was -- and stays short: the target's own name may be the full 255.
_TEMP_PREFIX = 32


def _temporary(folder, name):
    """A NEW temporary file in `folder`, created exclusively. -> (fd, path)

    🚨 hato 14z (A-1): `tempfile.mkstemp` SPUN FOR DAYS in a folder that denies
    adding a file. On Windows its loop reads ACCESS_DENIED as *"that name is
    taken"* and tries the next -- up to `TMP_MAX`, 2**31 names -- whenever the
    folder exists and `os.access(folder, W_OK)` is True, and on Windows that
    reads only the READ-ONLY attribute, never the folder's permissions.
    Measured: 40,052 names in 8 s, one core at 100%, the caller's run lock held.
    ⭐ So a few random names, each opened exclusively: a name taken by a FILE --
    or, on Windows, by a DIRECTORY, which answers ACCESS_DENIED too -- tries the
    next, and ⛔ any other refusal RAISES at once, for the caller to report.

    ⚠ hato's 15z (A12) -- CREATED AS ANY NEW FILE IS (0o666, the umask applied): the
    file it becomes -- by hard link or by rename -- keeps its mode, and `mkstemp`'s
    0600 left a subtitle on Linux unreadable to a media server running as another user.
    """
    flags = (os.O_RDWR | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
             | getattr(os, "O_NOINHERIT", 0))
    for _ in range(_TEMP_TRIES):
        tmp = os.path.join(folder, ".%s.%s.tmp" % (name[:_TEMP_PREFIX],
                                                   secrets.token_hex(4)))
        try:
            return os.open(tmp, flags, 0o666), tmp
        except FileExistsError:
            continue
        except PermissionError:
            if os.path.isdir(tmp):
                continue
            raise
    raise FileExistsError(errno.EEXIST, "%d temporary names in a row were already "
                          "taken" % _TEMP_TRIES, folder)


class AlreadyThere(FileExistsError):
    """`write_new_bytes`: the target's NAME is taken, and what is there was left
    exactly as it was.

    ⚠ Its own class, not a bare `FileExistsError`: `mkdir` raises one of those for
    an out-dir that is a FILE, and *"already there"* is the wrong thing to tell a
    person about that -- it could not be written at all."""


def write_new_bytes(path, data):
    """Byte-exact and atomic, like `atomic_write_bytes` -- and ⛔ NEVER OVER A FILE
    THAT IS THERE, not even one landing while this writes. -> [notes]

    ⭐ hato 14z (C3): the media-folder writer asked whether the name was free and
    THEN replaced it -- a file landing between the two (3.6 ms median on a local
    disk: a pick racing a scheduled run, the library API, another tool) was
    overwritten. Here the file appears under its name in ONE step that refuses a
    name already taken:

        a hard link from the temporary    refuses an existing name, everywhere --
                                          NTFS, ext4, APFS and HFS+ all have them
        Windows, with no hard links       `os.rename`, which on Windows refuses an
                                          existing target
        elsewhere, with no hard links     ⭐ the name RESERVED first -- created
        (exFAT, FAT, some SMB mounts)     exclusively, refused if anything is there --
                                          then the temporary REPLACES that reservation,
                                          its own, and the notes say it stood empty a
                                          moment (hato's 15z, A5: a look-then-rename
                                          stood here, the old race)

    ⭐ And it LOOKS FIRST, as 0.1.9's writer did (15z, A3): a name already taken is
    `AlreadyThere` before any temporary exists -- so a folder that lets a file be
    added but not deleted never holds one it cannot remove. The publish, not the
    look, is the guarantee.

    Raises `AlreadyThere` when the name is taken -- the file there untouched --
    and `OSError` for anything else: a folder that refuses a new file raises at
    once (`_temporary`, A-1); a FILE where the folder should be raises
    `NotADirectoryError`. ⛔ A temporary that cannot be removed is never raised
    over what happened: it is said -- in `notes` when the file landed, and as the
    raised error's `leftover` when it did not (15z, A3).
    """
    path = Path(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except FileExistsError:
        # ⭐ 15z (A11) -- mkdir's own words (*"Cannot create a file when that file
        # already exists"*) read as the TARGET being there.
        raise NotADirectoryError(errno.ENOTDIR, "a file stands where its folder should be",
                                 str(path.parent))
    target = str(path)
    if os.path.lexists(target):
        raise AlreadyThere(errno.EEXIST, "already there", target)
    fd, tmp = _temporary(str(path.parent), path.name)
    notes = []
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        _publish(tmp, target, path.name, notes)
    except BaseException as exc:
        left = _remove(tmp)
        if left is not None and isinstance(exc, OSError):
            exc.leftover = left
        raise
    # ⚠ The file IS there now. A temporary that will not go is a leftover to SAY, never
    # a failed write: the caller would report a file that landed as one that did not.
    left = _remove(tmp)
    if left is not None:
        notes.append(u"%s was written, but %s" % (path.name, left))
    return notes


#: Does `os.rename` refuse an existing target here? Windows' does; POSIX's REPLACES.
#: ⚠ A constant, not `os.name` read in place: the check proving the POSIX road on
#: Windows switches this, never `os.name` -- which turns every `Path` into a
#: `PosixPath` that cannot be made here.
_WINDOWS_RENAME = os.name == "nt"


def _publish(tmp, target, name, notes):
    """Make `tmp`'s bytes appear as `target` in ONE step that refuses a name already
    taken. Raises `AlreadyThere`, or the `OSError` that stopped it."""
    try:
        os.link(tmp, target)
        return
    except FileExistsError:
        raise AlreadyThere(errno.EEXIST, "already there", target)
    except OSError as exc:
        no_link = exc
    if _WINDOWS_RENAME:
        try:
            os.rename(tmp, target)
        except FileExistsError:
            raise AlreadyThere(errno.EEXIST, "already there", target)
        return
    try:
        held = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError:
        raise AlreadyThere(errno.EEXIST, "already there", target)
    os.close(held)
    try:
        os.replace(tmp, target)
    except OSError:
        _remove(target)                       # the reservation -- ours, still empty
        raise
    notes.append(u"this folder's volume could not make a hard link (%s), so the name %s "
                 u"was reserved first and then filled -- for that moment it stood empty"
                 % (no_link.strerror or no_link, name))


def _remove(path):
    """Remove `path` when it is there. -> None, or the sentence saying it could not be.
    ⛔ Never raises (15z, A3): a leftover is said, never raised over what happened."""
    try:
        if os.path.lexists(path):
            os.unlink(path)
    except OSError as exc:
        return u"its temporary %s could not be removed (%s)" % (os.path.basename(path),
                                                               exc.strerror or exc)
    return None


def read_json(path):
    """Read JSON with an explicit encoding.  See the module docstring."""
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def write_json(path, obj):
    atomic_write_text(path, json.dumps(obj, ensure_ascii=False, indent=1) + "\n")
