# -*- coding: utf-8 -*-
"""
The alias table: a Japanese title and a Latin one, bridged by a shared entity.

RUNBOOK step A7. `D6` ruled it in at launch — **three-way, ranking-only,
time-boxed to one day, and sequenced after the A5b benchmark so its value is
measured rather than assumed.** Gated by Probe G at **38.8%** realised
Japanese→romaji coverage against a 15% kill threshold (`08-probes.md` §G2).

⭐ WHAT IT IS FOR, IN ONE LINE

`same_series` compares CHARACTERS, and a Japanese title and its romaji share
none. `series.py` says so itself: *"A Japanese title and its romaji CANNOT
match on characters — kana is not Latin. That is the alias table's job (A7),
not a threshold's."* This is that job.

    宇宙戦艦ヤマト        vs  Space Battleship Yamato     score 0.00
    Ansatsu Kyoushitsu   vs  Assassination Classroom     score 0.09

Both are the same show. No threshold reaches either, and 9.9% of the real pairs
in the benchmark are exactly this shape.

🚨 A PART 1 DEFECT — THE SPEC ASKED FOR A COLUMN THAT DOES NOT EXIST

`02-data-model.md` and `09-corpus-strategy.md` describe a **three-way table:
romaji ↔ Japanese ↔ English**. ⛔ **Wikidata has no romaji field.** Measured by
probe A7/1 on 40 anime-television-series rows: `ja` label 100%, `en` label
100%, `mul` label **0%**, English aliases 90% — and the romaji lives *inside
those aliases*, beside abbreviations and alternative English titles:

    新世紀エヴァンゲリオン   en: Neon Genesis Evangelion
                       ~ Shin Seiki Evangelion    <- the romaji
                       ~ Eva · NGE · Evangelion   <- abbreviations
    宇宙戦艦ヤマト        en: Space Battleship Yamato
                       ~ Uchū Senkan Yamato       <- the romaji, with macrons
                       ~ Star Blazers             <- a DIFFERENT English title

⭐ **So the row is not three columns; it is one entity and N names.** That
shape is strictly better than the one specified: it holds `Star Blazers`,
which no romaji column could, and it is what `D6`'s ranking-only ruling wants.

🚨 THE SAFETY PROPERTY, AND IT IS THE ONLY THING KEEPING A FISH CAKE OUT

Probe G's original instrument matched `ナルト` to `narutomaki`, a Japanese fish
cake, at 0.75 — and reported a coverage number while its own positive control
was resolving to it. A table built from aliases carries that risk by
construction: `Eva`, `NGE`, `GuP` and `TTGL` are all real rows.

⭐ **The guard is that BOTH titles must independently resolve to a COMMON
entity.** A one-sided hit answers nothing. A video called `Eva.mkv` reaches
Q662 and stops there; it becomes a bridge only if the subtitle *also* reaches
Q662 — via `新世紀エヴァンゲリオン`, `エヴァ` or `Neon Genesis Evangelion`. That
is a far stronger claim than any similarity score, and it is what makes an
exact table safe where a fuzzy one is not.

⛔ AND IT NEVER RETURNS `DIFFERENT`.

Two names resolving to two *different* entities is NOT evidence they are
different shows. Wikidata models a series and each of its seasons as separate
entities (`Q63952888` vs `Q117467246`), and a manga and its adaptation as
separate entities again. Reading a non-intersection as DIFFERENT would
manufacture exactly the confidently wrong answer `00-INDEX.md` Rule 2 exists to
prevent. **Absence of a bridge is absence of an answer.**

⚠ RULE 1: THE TABLE IS AN ACCELERATOR, NEVER A DEPENDENCY. With no data file
it loads EMPTY and every verdict is identical to the one before A7 existed.
That is a deliberate fail-open and it is written down here because
`doctrine/robustness` requires the choice to be stated at the site.
"""
import gzip
import io
import json
import os

from .normalize import normalize

_DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

# 🚨 A LINE FORMAT, NOT JSON, AND IT IS A MEASUREMENT NOT A PREFERENCE.
#
# The table went in as JSON and `load()` took **1.708 s** for 147,873 keys.
# B5's target is a 24-episode folder in under 5 s, of which RUNBOOK 1d's
# container reading is already ~2.1 s — so a 1.7 s load ate **59% of what was
# left**, on the hot path, for something Rule 1 calls an accelerator.
#
# Probe A7/4 broke it down (best of three, on the real artefact):
#
#     decompress only              0.247 s   <- the achievable floor
#     decompress + json.load       1.799 s   <- ⭐ 1.55 s is the JSON parse
#     rebuild the dicts           +0.335 s
#     ⭐ flat lines, one loop       0.965 s   and 1.84 MB against 2.72 MB
#
# ⭐ Same data, verified key-for-key identical against the JSON build before
# the format changed. `00-INDEX.md`: never accept a speedup without proving the
# answer did not move.
#
# ⚠ It is still ~1 s, and the honest next step is an ON-DISK index — a run
# makes a few hundred lookups against 148,000 keys, so loading all of them is
# the wrong shape however fast the parse is. That is **B5's** decision, where
# the performance budget lives, and the measurement above is what it needs.
#
# The format, and it is deliberately boring:
#
#     line 1        a JSON object -- the metadata
#     then          <key>\t<qid> <qid> ...
#     a bare "##"   then <qid>\t<display name>
#
_FORMAT = "tsubasa-alias/1"
_SECTION = u"##"
_PLAIN = os.path.join(_DATA_DIR, "aliases.tsv")
_GZIP = os.path.join(_DATA_DIR, "aliases.tsv.gz")

# 🚨 A KEY SHARED BY MANY ENTITIES IS NOT IDENTIFYING -- and the cost of
# capping it too hard falls on exactly the shows a user is most likely to own.
#
# `Movie`, `Kiss` and a hundred bare-kanji titles name several unrelated works,
# and two unrelated titles both carrying such a name would meet on it. That is
# the one way the intersection rule can be fooled.
#
# 🚨 AND A BIG FRANCHISE LOOKS IDENTICAL FROM HERE -- WHICH IS WHY THE FIRST
# VALUE WAS WRONG BY A FACTOR OF SIX.
#
# The cap was set at 4 from the key-size distribution alone: 90% of keys name
# exactly one entity, 99.9% name four or fewer. Probe A7/3 then printed the
# lookup path and the cost was immediate:
#
#     ナルト        13 entities -> BLOCKED   Naruto      13 -> BLOCKED
#     進撃の巨人      9 entities -> BLOCKED   (intersection with the Latin side
#                                            was 2 -- a CORRECT bridge, refused)
#     宇宙戦艦ヤマト   5 entities -> BLOCKED
#
# ⭐ A franchise naming thirteen entities is not ambiguous BETWEEN shows; it is
# **one show with thirteen works**, and the intersection is large precisely
# because they are the same franchise. The distribution cannot tell that from a
# generic word, so the value is fitted on a measured sweep instead:
#
#     python -m tsubasa.dev alias --grade --sweep
#
# Measured on the complete 113,845-entity harvest, 233,507 keys:
#
# | cap | ja->romaji recall | ja->english | cross-row false SAME |
# | --- | --- | --- | --- |
# | 1 | 17.4% | 25.3% | 0.00% |
# | 4 | 32.7% | 42.9% | 0.00% |
# | 16 | 34.7% | 45.4% | 0.00% |
# | 64 | 34.8% | 45.5% | 0.00% |
# | 256 | 34.8% | 45.6% | 0.00% |
#
# ⛔ **There is no trade-off to trade.** The false-positive rate is flat at zero
# across the entire range, so the cap only ever costs recall -- up to 17.4
# points. The intersection rule provides the precision, and the real false
# positive found this session (`Dr Stone` against its own TV special) was under
# the cap on both sides and untouched by it.
#
# 🚨 AND IT WAS RE-FITTED THREE TIMES WITHOUT EVER MOVING A PRECISION NUMBER.
# 4 blocked `ナルト` at 13 entities. 24 blocked it again at 35, once the Naruto
# GAMES arrived in a later harvest batch. **A franchise's entity count is
# unbounded** -- it tracks how much of the franchise Wikidata has catalogued,
# which has nothing to do with ambiguity. Each re-fit cost recall and bought
# nothing measurable.
#
# ⭐ So it is named for what it is: a **BOUND on a pathological key, not a
# precision guard.** 64 sits at the recall plateau, comfortably above the
# largest observed real franchise (35), and below the observed key maximum
# (189) so it stays reachable and testable.
# ⚠ Re-fit with `alias --grade --sweep`, never from the key-size distribution
# -- that is the mistake this comment exists to record.
MAX_ENTITIES_PER_KEY = 64

# ⚠ The derived file stores up to this many entities per key, INDEPENDENTLY of
# the lookup cap above. The two were one number at first, which made the
# artefact unable to answer *"what would a different cap buy?"* -- a table that
# can only confirm its own setting, and the sweep above would have been
# impossible. ⛔ It must stay strictly ABOVE the lookup cap, or a key over the
# cap is indistinguishable from one merely at it and the guard stops firing.
#
# ⚠ It is also a SILENT DROP if it ever binds: truncating a key's entity list
# can remove the very entity the other side would have intersected with. So
# `alias --derive` prints how many keys reach it, and the number must stay 0.
STORE_CAP = 256

SAME = "same"
UNSURE = "unsure"


class Table(object):
    """key -> the entities that name it, plus where the table came from.

    ⭐ ONE ACCESSOR. Nothing outside this class touches the underlying dict —
    `doctrine/architecture`: a store read from thirty places makes *"change
    where the data comes from"* a thirty-site edit.
    """

    __slots__ = ("_keys", "_names", "meta")

    def __init__(self, keys=None, names=None, meta=None):
        # {folded key: (qid, qid, ...)}
        self._keys = keys or {}
        # {qid: [display names]} -- for the REASON string, so a bridge can say
        # WHY it fired. `doctrine/robustness`: a message says what it found.
        self._names = names or {}
        self.meta = meta or {}

    def __len__(self):
        return len(self._keys)

    def __repr__(self):
        return "Table(%d keys, %d entities, derived %s)" % (
            len(self._keys), len(self._names), self.meta.get("derived", "?"))

    def entities(self, title):
        """The entities a title names. ⭐ Empty when it names too many.

        ⚠ Returns a frozenset, never a list: callers intersect, and a caller
        that mutated a shared list would corrupt the table for every later
        lookup in the process.
        """
        key = normalize(title).key
        if not key:
            return frozenset()
        found = self._keys.get(key)
        if not found:
            return frozenset()
        if len(found) > MAX_ENTITIES_PER_KEY:
            return frozenset()
        return frozenset(found)

    def name_of(self, qid):
        """A display name for an entity, for the reason string."""
        names = self._names.get(qid)
        return names[0] if names else qid


_CACHED = None


def load(path=None):
    """The bundled table. ⚠ Absent is NOT an error — it is empty.

    ⭐ FAIL OPEN, deliberately, and stated here as `doctrine/robustness`
    requires. A missing table costs recall on cross-script pairs, which timing
    then has to settle — exactly the behaviour of every build before A7.
    Refusing to run would cost the user everything for a file that one command
    regenerates. `00-INDEX.md` Rule 1: an accelerator, never a dependency.
    """
    global _CACHED
    if path is None and _CACHED is not None:
        return _CACHED

    table = None
    for target in ([path] if path else [_GZIP, _PLAIN]):
        if not target or not os.path.isfile(target):
            continue
        table = _read(target)
        if table is not None:
            break

    table = Table() if table is None else table
    if path is None:
        _CACHED = table
    return table


def _read(target):
    """Parse one file. -> Table, or None if it could not be read at all.

    ⚠ Explicit encoding, always. A UTF-8 manifest read back with the Windows
    cp1252 default crashed once already, in a project whose worst bug is an
    encoding assumption.
    """
    opener = (gzip.open if str(target).endswith(".gz") else io.open)
    keys, names, meta = {}, {}, {}
    try:
        with opener(target, "rt", encoding="utf-8") as fh:
            first = fh.readline()
            try:
                meta = json.loads(first) if first.strip() else {}
            except ValueError:
                meta = {}
            in_names = False
            for line in fh:
                line = line.rstrip(u"\n")
                if not line:
                    continue
                if line == _SECTION:
                    in_names = True
                    continue
                left, tab, right = line.partition(u"\t")
                if not tab:
                    continue
                if in_names:
                    names[left] = [right]
                else:
                    keys[left] = tuple(right.split(u" "))
    except Exception:                                     # noqa: BLE001
        # 🚨 `except Exception`, DELIBERATELY, AND THE NARROW TUPLE THAT WAS
        # HERE FIRST WAS A REAL DEFECT.
        #
        # It caught `(IOError, OSError, ValueError, EOFError)`. **`zlib.error`
        # derives straight from `Exception`** and matches none of them, so a
        # corrupt gzip did not fail open -- it took the whole tool down, and
        # `same_series()` raised with it. Measured by the adversarial pass:
        # **307 of the first 400 single-byte flips** of the shipped 4.4 MB
        # artefact made `load()` raise. Rule 1 says this table is an
        # ACCELERATOR, never a dependency; a narrow catch made that sentence
        # false for the commonest kind of file damage there is.
        #
        # ⭐ This is the one place in the project where a bare catch is right,
        # and `doctrine/robustness` requires the choice to be stated at the
        # site: **every** way of failing to read a regenerable cache means the
        # same thing -- run without it. A guard that announces a TOOLING fault
        # is a different case and is still never swallowed.
        #
        # ⚠ Partial reads are kept. A gzip cut short raises partway through and
        # everything read before that point is valid -- measured, 89,791 of
        # 233,507 keys survived a truncation. Returning them beats returning
        # nothing. But an empty result and a genuinely absent file must stay
        # the same outcome, so an empty parse is still `None`.
        if not keys:
            return None
    return Table(keys, names, meta)


def reset_cache():
    """Forget the loaded table. For tests that swap the data file underneath."""
    global _CACHED
    _CACHED = None


def bridge(a, b, table=None):
    """Do two titles name the same entity? -> (verdict, score, reason).

    ⛔ SAME or UNSURE. **Never DIFFERENT** — see the module docstring: a
    series and its own season are two Wikidata entities, so a non-intersection
    is an absent answer, not a negative one.

    ⭐ Ranking only (`D6`). A SAME here lifts a pair into the candidate set the
    timing referee then settles. It never writes a file, and `align()` still
    has to agree.
    """
    table = load() if table is None else table
    if not len(table):
        return (UNSURE, 0.0, u"")

    left = table.entities(a)
    if not left:
        return (UNSURE, 0.0, u"")
    right = table.entities(b)
    if not right:
        return (UNSURE, 0.0, u"")

    shared = left & right
    if not shared:
        # ⚠ Deliberately not DIFFERENT, and deliberately carrying no score.
        # Both titles are IN the table and name different entities -- which is
        # the exact shape of `Gintama` (the series) against `Gintama` (season
        # 2), and of a manga against its own anime adaptation.
        return (UNSURE, 0.0, u"")

    qid = sorted(shared)[0]
    return (SAME, 1.0,
            u"alias table: both name %s (%s)" % (qid, table.name_of(qid)))
