# -*- coding: utf-8 -*-
u"""
The settings. RUNBOOK 3d, ruled 2026-09-10.

    s = Settings.load()
    s.get(u"auto_run_on_drop")          # -> True
    s.set(u"recurse", False)
    s.save()
    run.argv_for(folder, **s.run_options())

===========================================================================
⭐ SONIC'S RULING, IN HIS WORDS
===========================================================================

  *"Auto-run on drop unless setting is toggled. Write without confirm unless
  reckless toggled in settings. The window must look clean as it does, and
  the settings organized but the settings would likely be powerful for
  various features."*

Three things follow, and they are the shape of this module:

  1. **The main window stays as clean as the mockup.** Every option lives
     here, in groups, behind one button.
  2. **The defaults are the ruled ones.** Drop a folder and it runs; a write
     needs no confirmation.
  3. ⭐ **`RECKLESS` is the one group that changes that.** Nothing in it is on
     by default, and while anything in it IS on, the app asks before it
     writes — because the whole reason those options are separated out is
     that they can do something the rest of the tool refuses to do.

===========================================================================
🚨 THE PANEL IS GENERATED FROM `SCHEMA`. THAT IS NOT A CONVENIENCE.
===========================================================================

`doctrine/architecture`: *a control whose identifier is missing from the
dispatch list renders perfectly and is **completely inert.** It shipped three
separate times in one build, and every time a human found it by tapping.*

A settings panel is that failure waiting to happen: a checkbox drawn by hand,
bound to a key nobody reads, looks exactly like a working one. ⛔ So the
window does not know the names of any options. It walks `SCHEMA`, and
`test_every_setting_in_the_schema_reaches_the_run` walks it too.

⚠ **AND THE DEFAULTS ARE THE CLI'S DEFAULTS, DERIVED NOT COPIED.** `recurse`,
`rename` and `results` are ON in `cli.parse`; writing that `True` twice is two
places to change it. `run_options()` emits only what DIFFERS from the default,
which is the same discipline `argv_for` already follows — and it means a
settings file from an older version cannot silently pin a flag whose meaning
has moved.
"""
import io
import json
import os

from .. import paths as _paths
from . import run as _run

#: The filename under `paths.cache_root()`. ⛔ Never beside the media.
FILENAME = u"gui-settings.json"

#: Groups, in the order the panel shows them. ⭐ The last one is separated
#: because of what is in it, not because it is advanced.
GROUPS = (
    (u"run", u"Running", u"What happens when you press Sync."),
    (u"output", u"Output", u"Where the synced subtitle goes and what it is "
                           u"called."),
    (u"window", u"Window", u"How this window behaves."),
    (u"reckless", u"Reckless", u"Off by default. While any of these is on, "
                               u"tsubasa asks before it writes — they are the "
                               u"options that can change a file you already "
                               u"had, rather than adding one beside it."),
)


class Option(object):
    u"""One setting. ⛔ Its `key` is the only name for it, anywhere."""

    __slots__ = ("key", "group", "label", "kind", "default", "why", "flag")

    def __init__(self, key, group, label, kind, default, why, flag=None):
        self.key = key
        self.group = group
        self.label = label
        self.kind = kind            # "bool" | "path" | "choice"
        self.default = default
        self.why = why
        #: The `argv_for` keyword this drives, when it drives one.
        self.flag = flag

    @property
    def reckless(self):
        return self.group == u"reckless"

    def __repr__(self):
        return "<Option %s=%r>" % (self.key, self.default)


SCHEMA = (
    # -- run ---------------------------------------------------------------
    # 🚨 EVERY `why` BELOW IS PLAIN PROSE FOR A PERSON. No ⭐/⛔/⚠, no
    # `backticks`, no *asterisks* — this project's markers are for its own
    # documents, and a Tk label renders them literally. Found by looking at
    # the real panel: a hollow star sat mid-sentence like a typo and
    # `*would sync*` showed its asterisks. ⛔ The reasoning that earned a
    # marker belongs in a comment beside the option, not in the sentence the
    # user reads.
    Option(u"dry_run", u"run", u"Measure everything, write nothing",
           u"bool", False,
           u"A preview. Every decision is made and reported and not one byte "
           u"moves. The window says “would sync” rather than “synced” while "
           u"this is on, because those are different claims about your "
           u"folder.",
           flag=u"dry_run"),
    Option(u"recurse", u"run", u"Search sub-folders", u"bool", True,
           u"On, a season folder full of episode folders works. Off, only "
           u"the folder you picked is looked at.",
           flag=u"recurse"),
    Option(u"results", u"run", u"Remember what has already been synced",
           u"bool", True,
           u"A settled 24-episode folder re-runs in about a quarter of a "
           u"second with no video reads at all. Off, every run redoes the "
           u"whole thing.",
           flag=u"results"),
    Option(u"verbose", u"run", u"Keep the raw numbers", u"bool", False,
           u"Chance multiples and per-bucket timings. This is what a bug "
           u"report needs and what the default view has no room for.",
           flag=u"verbose"),

    # -- output ------------------------------------------------------------
    Option(u"subs", u"output", u"Look for subtitles somewhere else",
           u"path", u"",
           u"Leave empty and subtitles are expected beside the videos. Set "
           u"it to a Downloads folder to pair across two places.",
           flag=u"subs"),
    Option(u"out", u"output", u"Write the results somewhere else",
           u"path", u"",
           u"Leave empty and each subtitle is written beside its video. Set "
           u"it and the library's folder shape is mirrored underneath — "
           u"never flattened.",
           flag=u"out"),
    Option(u"keep_all", u"output", u"Keep every candidate", u"bool", False,
           u"Normally one subtitle survives per video per language and the "
           u"rest go to the trash. On, every candidate is written under its "
           u"own tag and nothing is trashed.",
           flag=u"keep_all"),

    # -- window ------------------------------------------------------------
    Option(u"auto_run_on_drop", u"window", u"Run as soon as a folder is "
                                           u"dropped", u"bool", True,
           u"Drop a folder on the window and it starts straight away. Off, "
           u"the folder is filled in and waits for you to press Sync.",),
    Option(u"remember_folder", u"window", u"Reopen on the last folder used",
           u"bool", True,
           u"The folder box starts filled in with wherever you were last."),

    # -- reckless ----------------------------------------------------------
    # ⛔ The RECKLESS half of this option is its INVERSE — the default is the
    # safe one, so `reckless_active()` fires when it is turned OFF.
    Option(u"rename", u"reckless", u"Retime the subtitle where it sits "
                                   u"(do not rename)", u"bool", True,
           u"Normally the output takes the video's name, which is what makes "
           u"a player load it automatically, and your original goes to the "
           u"trash intact. Turn renaming off and tsubasa writes the new "
           u"timing over the file you already had, under its own name. It is "
           u"the only setting here that changes a file rather than adding "
           u"one, and it is why this group asks before it writes.",
           flag=u"rename"),
)

BY_KEY = dict((o.key, o) for o in SCHEMA)
DEFAULTS = dict((o.key, o.default) for o in SCHEMA)

#: ⭐ Not every option drives the run. `auto_run_on_drop` and
#: `remember_folder` are about this window and mean nothing to the CLI.
FLAGGED = tuple(o for o in SCHEMA if o.flag)


class Settings(object):
    u"""One accessor over the settings. ⛔ Nothing else reads the file.

    `doctrine/architecture` rule 2. It is what makes *"where do settings come
    from"* a one-function question the day they come from somewhere else.
    """

    def __init__(self, values=None, path=None, note=u""):
        self.path = path
        #: ⚠ UNKNOWN KEYS ARE KEPT. A settings file written by a newer build
        #: must survive being opened by an older one — dropping what it does
        #: not recognise turns *"I ran the old version once"* into *"my
        #: settings are gone."*
        self.values = dict(values or {})
        self.note = note

    # -- reading -----------------------------------------------------------

    @classmethod
    def file_path(cls):
        return os.path.join(str(_paths.cache_root()), FILENAME)

    @classmethod
    def load(cls, path=None):
        u"""-> `Settings`. ⛔ NEVER RAISES.

        ⚠ `LEDGER-HOT.md`: *for a regenerable cache, `except Exception` is
        correct and the reason goes at the site.* A settings file is
        regenerable by definition — every value in it has a default — so a
        corrupt one must not stop the app opening. It IS reported, in `note`,
        because silently reverting somebody's configuration is its own defect.
        """
        path = path or cls.file_path()
        if not os.path.isfile(path):
            return cls({}, path)
        try:
            with io.open(path, u"r", encoding=u"utf-8") as fh:
                loaded = json.load(fh)
            if not isinstance(loaded, dict):
                return cls({}, path,
                           u"the settings file holds %s where an object was "
                           u"expected — defaults are in use, and saving will "
                           u"replace it." % type(loaded).__name__)
            return cls(loaded, path)
        except Exception as exc:
            return cls({}, path,
                       u"the settings file could not be read (%s) — defaults "
                       u"are in use, and saving will replace it." % exc)

    def get(self, key):
        u"""-> the stored value, or the default. ⛔ Type-checked.

        ⚠ A hand-edited file can put a string where a bool belongs, and
        `if settings.get("dry_run")` is then True for the string `"false"`.
        A value of the wrong shape is treated as absent.
        """
        option = BY_KEY.get(key)
        if option is None:
            raise KeyError(u"%r is not a setting. The names are: %s"
                           % (key, u", ".join(sorted(BY_KEY))))
        if key not in self.values:
            return option.default
        value = self.values[key]
        if option.kind == u"bool" and not isinstance(value, bool):
            return option.default
        if option.kind == u"path" and not isinstance(value, str):
            return option.default
        return value

    def set(self, key, value):
        if key not in BY_KEY:
            raise KeyError(u"%r is not a setting." % key)
        self.values[key] = value
        return self

    # -- what the run is told ----------------------------------------------

    def run_options(self):
        u"""-> the keyword arguments for `run.argv_for`.

        ⭐ ONLY WHAT DIFFERS FROM THE DEFAULT. `argv_for` already emits no
        flag for a default, and a settings layer that passes every value
        explicitly would pin today's defaults into a file that outlives them.
        """
        out = {}
        for option in FLAGGED:
            value = self.get(option.key)
            if value != option.default:
                out[option.flag] = value
        # ⚠ An empty path means *not set*, and `argv_for` reads any truthy
        # string as a folder. The two disagree about `u""` and this is the
        # seam, so it is resolved here.
        for key in (u"subs", u"out"):
            if key in out and not str(out[key]).strip():
                del out[key]
        return out

    # -- the reckless group -------------------------------------------------

    def reckless_active(self):
        u"""Which reckless options are ON. -> [Option]

        ⭐ SONIC'S RULE, AS CODE: *write without confirm unless reckless
        toggled.* Nothing here is on by default, so the ordinary path never
        confirms; the moment one is, the app asks — because these are the
        options that change a file rather than adding one.
        """
        return [o for o in SCHEMA
                if o.reckless and self.get(o.key) != o.default]

    def confirm_before_writing(self):
        return bool(self.reckless_active())

    # -- writing ------------------------------------------------------------

    def save(self):
        u"""⛔ ATOMIC. `LEDGER-HOT.md`'s first entry, three times over: never
        `open(path, "w")` on a file you cannot afford to lose."""
        folder = os.path.dirname(self.path)
        if folder and not os.path.isdir(folder):
            os.makedirs(folder)
        _paths.atomic_write_text(
            self.path,
            json.dumps(self.values, ensure_ascii=False, indent=2,
                       sort_keys=True) + u"\n")
        return self

    def __repr__(self):
        return "<Settings %d set, %d default>" % (
            len(self.values), len(SCHEMA) - len(self.values))


def grouped():
    u"""The schema, in panel order. -> [(key, title, blurb, [Option])]"""
    return [(key, title, blurb,
             [o for o in SCHEMA if o.group == key])
            for key, title, blurb in GROUPS]


__all__ = ["Settings", "Option", "SCHEMA", "GROUPS", "BY_KEY", "DEFAULTS",
           "FLAGGED", "FILENAME", "grouped"]
