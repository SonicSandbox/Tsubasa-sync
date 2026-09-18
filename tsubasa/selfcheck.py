# -*- coding: utf-8 -*-
u"""
`self_check()` — is this installation as good as it is supposed to be?

===========================================================================
🚨 WHY IT EXISTS: THE TWO DATA FILES FAIL OPEN, SO NOTHING ELSE WILL SAY
===========================================================================

`naming/alias.py::load()` and `naming/decoration.py::load()` return EMPTY when
their file is missing, and that is deliberate — `00-INDEX.md` Rule 1, an
accelerator never a dependency. Refusing to run would cost a user everything
for a file one command regenerates. **The price is that a broken install is
silent**: it imports, runs, exits 0, and settles pairs by name 51.4% of the
time instead of 80.0%.

⛔ MEASURED 2026-09-16: a PyInstaller build of a plain `import tsubasa` loaded
0 alias entries and 0 vocabulary tokens, and a cross-script pair that settles
by name came back `unsure`. No exception, no warning, no log line.

⭐ So the fail-open stays and this is the instrument that makes it visible. An
application calls it from its own smoke test, under whatever freezer it uses,
and gets a yes/no plus sentences a person can act on.

===========================================================================
⚠ WHAT `ok` MEANS, EXACTLY
===========================================================================

**Is anything SILENTLY worse than it should be?** That is the only question.

- Each table is compared with the size it DECLARES in its own header — not
  with a threshold written here. A table that says 221,258 entries and loads
  12,000 is truncated, and a hard-coded floor would have called it fine.
- ffmpeg and the optional parsers are REPORTED and never counted. Missing
  ffmpeg is not silent: every container that needs it comes back ERROR with a
  sentence naming the fix. A missing optional parser degrades to a documented
  behaviour. An application that needs ffmpeg checks `.ffmpeg` itself.

⛔ IT OPENS NOTHING OF THE USER'S AND RUNS NOTHING. It loads the two tables the
first `scan()` would load anyway (cached for the process), asks
`ffmpeg.find()` where the binaries are — a lookup, never an execution — and
asks `importlib.util.find_spec` whether the optional imports resolve, which
does not import them.
"""
import importlib.util

from .container import ffmpeg as _ffmpeg
from .naming import alias as _alias
from .naming import decoration as _decoration

#: Optional imports, and what each buys. ⚠ Absence is never a problem: every
#: one is reached through a guarded lazy import (`pyproject.toml` extras).
OPTIONAL = (
    (u"anitopy", u"a second opinion on unusual release names"),
    (u"guessit", u"a third opinion on unusual release names"),
    (u"send2trash", u"the OS trash and uses a local .tsubasa-trash/ folder "
                    u"instead"),
)

#: The consequence of a missing alias table, in the one place it is stated.
#:
#: 🚨 EVERY SENTENCE THIS MODULE RETURNS IS ASCII, AND THAT IS MEASURED, NOT
#: TASTE. It read *"ヘルモード with Hell Mode —"*, and a PyInstaller app built
#: without the hook — the exact case this exists to report — crashed on
#: `print(sentence)` with `UnicodeEncodeError: 'charmap'`: a frozen Windows
#: app's stdout is cp1252, and the bootloader runs Python isolated, so
#: `PYTHONIOENCODING` is IGNORED. ⭐ The third instrument in one day killed by
#: its own output, after the CI reporter and `find_spec`. A diagnostic must be
#: printable in the environment it diagnoses. ⚠ Paths are still reported
#: verbatim — a path is evidence and is not rewritten — so a caller printing to
#: a legacy console should still print defensively.
_ALIAS_COST = (u"pairing across scripts and titles (a Japanese title with its "
               u"English one) falls back to timing alone. Measured: settled "
               u"by name drops from 80.0% to 51.4%")

_FROZEN_HINT = (u" If this application is frozen, its build did not collect "
                u"tsubasa's data files: PyInstaller does that automatically "
                u"through the hook tsubasa ships, and any other freezer needs "
                u"tsubasa/data/ copied in beside the package.")


class SelfCheck(object):
    u"""The answer. ⭐ `problems` is never empty when `ok` is False."""

    __slots__ = ("ok", "problems", "notes", "version", "data_dir",
                 "alias_entries", "alias_declared", "vocabulary_tokens",
                 "vocabulary_declared", "ffmpeg", "ffprobe", "optional")

    def __init__(self, problems, notes, version, data_dir, alias_entries,
                 alias_declared, vocabulary_tokens, vocabulary_declared,
                 ffmpeg, ffprobe, optional):
        self.problems = list(problems)
        self.ok = not self.problems
        self.notes = list(notes)
        self.version = version
        self.data_dir = data_dir
        self.alias_entries = alias_entries
        self.alias_declared = alias_declared
        self.vocabulary_tokens = vocabulary_tokens
        self.vocabulary_declared = vocabulary_declared
        self.ffmpeg = ffmpeg
        self.ffprobe = ffprobe
        self.optional = dict(optional)

    def as_dict(self):
        u"""Plain JSON-serialisable values — for a diagnostics bundle."""
        return dict((name, getattr(self, name)) for name in self.__slots__)

    def __repr__(self):
        return "SelfCheck(%s, aliases %d/%s, vocabulary %d/%s, ffmpeg %s)" % (
            u"ok" if self.ok else u"%d problem%s" % (
                len(self.problems), u"" if len(self.problems) == 1 else u"s"),
            self.alias_entries, self.alias_declared,
            self.vocabulary_tokens, self.vocabulary_declared,
            u"found" if self.ffmpeg else u"not found")


def self_check():
    u"""Is this installation as good as it is supposed to be? -> `SelfCheck`

        check = tsubasa.self_check()
        if not check.ok:
            for sentence in check.problems:
                log.warning("tsubasa: %s", sentence)

    See the module note for exactly what `ok` does and does not cover.
    """
    from . import __version__

    problems, notes = [], []

    table = _alias.load()
    alias_entries = len(table)
    alias_declared = table.meta.get(u"keys")
    problems.extend(_compare(
        u"alias table", alias_entries, alias_declared,
        _alias._GZIP, _ALIAS_COST))

    vocab = _decoration.load()
    vocabulary_tokens = len(vocab)
    vocabulary_declared = vocab.meta.get(u"tokens")
    problems.extend(_compare(
        u"decoration vocabulary", vocabulary_tokens, vocabulary_declared,
        _decoration._DATA,
        u"release tags such as 1080p, WEBRip and AT-X are no longer told "
        u"apart from title words and titles match less often"))

    ffmpeg = _ffmpeg.find(u"ffmpeg")
    ffprobe = _ffmpeg.find(u"ffprobe")
    if ffprobe is None:
        notes.append(
            u"ffprobe was not found. Matroska files with a subtitle track do "
            u"not need it; any other container is refused with a sentence "
            u"naming the fix. An application that bundles ffmpeg can point "
            u"tsubasa at it with tsubasa.set_ffmpeg().")

    # =======================================================================
    # 🚨 numpy IS THE ONE HARD DEPENDENCY, AND IT BECAME SILENT — RUNBOOK 4g
    # =======================================================================
    # Its import was deferred so the GUI stops paying for the numeric stack to
    # draw a window. ⛔ THE PRICE, FOUND BY AN ADVERSARIAL PASS: `import
    # tsubasa` used to raise `ModuleNotFoundError` the instant numpy was
    # missing — loud, immediate, unmissable. Now the package imports, this
    # function said `ok`, `tsubasa --version` said `ok`, and the failure waited
    # until the first real sync.
    #
    # ⭐ That is precisely the class this module's own note is about, arriving
    # through a door it did not cover. It is a PROBLEM rather than a note
    # because nothing works without it — unlike ffmpeg or the parsers, which
    # degrade to documented behaviour.
    #
    # ⚠ `find_spec`, never an import: asking whether numpy exists must not
    # load it, or this check would undo the change that made it necessary.
    # 🚨 IT IS IMPORTED, NOT MERELY LOOKED UP, AND THAT IS THE WHOLE POINT.
    # `find_spec` answers *is it installed*, which is a different question
    # from *does it work* — and the commonest real numpy failure on Windows
    # is neither: it is present, findable, and raises on import
    # (`ImportError: DLL load failed while importing _multiarray_umath`).
    #
    # ⛔ BEFORE 4g THAT WAS LOUD — `import tsubasa` raised it at import. After
    # 4g deferred numpy, `import tsubasa` succeeded, `self_check()` said
    # **ok**, `--version` said **ok**, and the failure waited for the first
    # sync. 4g closed the *absent* half of the door it opened and left the
    # *present-but-unimportable* half wide. Found by an adversarial pass.
    #
    # ⭐ The cost is ~245 ms, paid ONLY here. `self_check()` is a diagnostic:
    # the CLI calls it for `--version`, and nothing on the GUI's startup path
    # calls it at all — which is what 4g was protecting. ⛔ **Do not call
    # `self_check()` while opening a window.**
    # ⚠ A FINDER THAT REFUSES TO ANSWER IS NOT A VERDICT. `find_spec`
    # consults every finder on the meta path, and a freezer's or a
    # sandbox's can RAISE rather than decline — that already crashed
    # `self_check()` once, in exactly the environments it exists for.
    # ⛔ But neither arm of *assume broken* / *assume fine* is right: the
    # first makes `--version` exit 1 for every frozen user whose freezer has
    # an opinionated finder, and the second is the silence 4g created.
    # ⭐ So the import below settles it either way, and the lookup only
    # decides which SENTENCE to use.
    found, why_not = True, u""
    try:
        found = importlib.util.find_spec(u"numpy") is not None
    except Exception as exc:                              # noqa: BLE001
        why_not = u"%s: %s" % (type(exc).__name__, exc)

    try:
        importlib.import_module(u"numpy")
        if why_not:
            notes.append(u"an import hook raised while being asked whether "
                         u"numpy exists (%s), but numpy itself loads fine."
                         % why_not)
    except Exception as exc:                              # noqa: BLE001
        if found and not why_not:
            problems.append(
                u"numpy is installed but will not load (%s: %s), and it is "
                u"the one dependency tsubasa cannot work without: every "
                u"alignment raises. Reinstalling it usually fixes this: "
                u"`pip install --force-reinstall numpy`."
                % (type(exc).__name__, exc))
        else:
            problems.append(
                u"numpy is not installed, and it is the one dependency "
                u"tsubasa cannot work without: every alignment raises. "
                u"Install it with `pip install numpy`, or reinstall tsubasa "
                u"with `pip install tsubasa-sync`, which requires it.")

    optional = {}
    for name, buys in OPTIONAL:
        # 🚨 `find_spec` CAN RAISE, and the instrument may not die on it. It
        # consults every finder on the meta path, and an import hook that
        # raises instead of declining — a freezer's, a sandbox's, this
        # project's own dependency check — made `self_check()` crash on the
        # line that was only asking whether a module exists. Found the first
        # time the suite ran it under a blocking finder. ⭐ The same shape as
        # the CI reporter killed by the failure it existed to report: a
        # diagnostic that can be silenced by its subject matter is not one.
        try:
            present = importlib.util.find_spec(name) is not None
            why = u""
        except Exception as exc:                  # noqa: BLE001 — reported
            present = False
            why = u" (looking it up raised %s: %s)" % (type(exc).__name__, exc)
        optional[name] = present
        if not present:
            notes.append(u"%s is not available%s, so tsubasa goes without %s."
                         % (name, why, buys))

    return SelfCheck(problems, notes, __version__, _alias._DATA_DIR,
                     alias_entries, alias_declared, vocabulary_tokens,
                     vocabulary_declared, ffmpeg, ffprobe, optional)


def _compare(what, loaded, declared, path, cost):
    u"""-> [sentence]. ⚠ Empty means the file loaded everything it declares."""
    if loaded == 0:
        return [u"the %s did not load: nothing usable at %s, so %s.%s"
                % (what, path, cost, _FROZEN_HINT)]
    if declared is None:
        return [u"the %s loaded %d entries but its header does not say how "
                u"many it should have, so a truncated file cannot be told "
                u"apart from a complete one. It was not built by this "
                u"release's tooling." % (what, loaded)]
    if loaded != declared:
        return [u"the %s loaded %d of the %d entries its own header declares "
                u"- the file at %s is truncated or was rewritten, so %s."
                % (what, loaded, declared, path, cost)]
    return []
