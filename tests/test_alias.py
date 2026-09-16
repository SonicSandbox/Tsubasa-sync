# -*- coding: utf-8 -*-
"""
The alias table. RUNBOOK step A7.

⭐ THE CLAIM UNDER TEST

`same_series` compares characters, and a Japanese title and its romaji share
none — `宇宙戦艦ヤマト` against `Space Battleship Yamato` scores **0.00**, and
no threshold ever reaches it. 9.9% of the benchmark's real pairs are that
shape. The table bridges them through a shared Wikidata entity.

🚨 AND THE CLAIM THAT MATTERS MORE: that it cannot be fooled the way probe G
was.

Probe G's instrument matched `ナルト` to `narutomaki`, a **Japanese fish
cake**, at 0.75, and reported a coverage number while its own positive control
was resolving to it. A table built from aliases carries that risk by
construction — `Eva`, `NGE`, `GuP` and `TTGL` are all real rows.

⭐ **The guard is that BOTH titles must independently reach a COMMON entity.**
A one-sided hit answers nothing, and that is the property most of this file
exists to hold shut. It is far stronger than any similarity score: `Eva.mkv`
reaches Q662 and stops, unless the subtitle also reaches Q662.

⛔ AND IT NEVER RETURNS `DIFFERENT`. Wikidata models a series and each of its
seasons as separate entities, and a manga and its adaptation as separate
entities again — so two names reaching two entities is an ABSENT answer, not a
negative one. `00-INDEX.md` Rule 2.

⚠ The corpus-backed validation is `python -m tsubasa.dev alias --grade`, which
scores every eligible answer-key row. What runs here is the MECHANISM — the
intersection rule, the fail-open, the fan-out cap, the fold, the additivity —
plus a corpus sample and a fabricated control when the corpus is present. A
skip says so.
"""
import gzip
import io
import json
import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tsubasa.naming import alias as A                        # noqa: E402
from tsubasa.naming.normalize import normalize                # noqa: E402
from tsubasa.naming.series import (DIFFERENT, SAME, UNSURE,   # noqa: E402
                                   same_series)
from tsubasa.paths import corpus_root, load_config            # noqa: E402


# ⚠ BUILT FROM LITERALS, NEVER FROM A FORMAT STRING. `LEDGER.md` §Harness
# records this trap twice in one day: a cp1252 fixture that was pure ASCII, and
# a "full-width" fixture built as `u"（０%d）" % i` where `%d` emits an ASCII
# digit. Both were green and worthless. Every macron and every kana below is a
# real character, so the fold is exercised by the fixture rather than assumed.
YAMATO = u"Q4292"
EVA = u"Q662"
GURREN = u"Q4277"


def _table():
    """A small hand-built table with the real hazards in it.

    Contains, deliberately:
      * a three-script entity (ja label, ja alias, en label, romaji alias)
      * an ABBREVIATION alias (`Eva`) -- the fish-cake shape
      * a name shared by MORE entities than the cap allows
      * two entities that share nothing, to prove non-intersection is UNSURE
    """
    def k(text):
        return normalize(text).key

    keys = {}

    def add(qid, *names):
        for name in names:
            keys.setdefault(k(name), set()).add(qid)

    add(YAMATO, u"宇宙戦艦ヤマト", u"Space Battleship Yamato",
        u"Uchū Senkan Yamato", u"Star Blazers")
    add(EVA, u"新世紀エヴァンゲリオン", u"エヴァ", u"Neon Genesis Evangelion",
        u"Shin Seiki Evangelion", u"Eva")
    add(GURREN, u"天元突破グレンラガン", u"Gurren Lagann",
        u"Tengen Toppa Gurren Lagann")
    # A generic name naming more entities than the cap -- `Movie`, `Kiss`, a
    # bare kanji. It must answer NOTHING rather than bridge on a coincidence.
    for i in range(A.MAX_ENTITIES_PER_KEY + 3):
        add(u"Q90000%d" % i, u"Kiss")

    names = {YAMATO: [u"Space Battleship Yamato"],
             EVA: [u"Neon Genesis Evangelion"],
             GURREN: [u"Gurren Lagann"]}
    return A.Table({key: tuple(sorted(v)) for key, v in keys.items()},
                   names, {"source": "test"})


@pytest.fixture()
def table():
    return _table()


# ==========================================================================
# ⭐ the intersection rule -- the only thing keeping a fish cake out
# ==========================================================================

@pytest.mark.parametrize("ja,latin", [
    (u"宇宙戦艦ヤマト", u"Space Battleship Yamato"),
    (u"宇宙戦艦ヤマト", u"Uchū Senkan Yamato"),      # a REAL macron
    (u"宇宙戦艦ヤマト", u"Uchuu Senkan Yamato"),     # the digraph spelling
    (u"宇宙戦艦ヤマト", u"Star Blazers"),            # a different English title
    (u"新世紀エヴァンゲリオン", u"Neon Genesis Evangelion"),
    (u"エヴァ", u"Shin Seiki Evangelion"),          # ja alias <-> romaji alias
    (u"天元突破グレンラガン", u"Tengen Toppa Gurren Lagann"),
])
def test_two_names_of_one_entity_bridge(table, ja, latin):
    """The whole point: characters share nothing and the entity is shared.

    ⭐ `Star Blazers` is the row a three-column romaji table could never have
    held, and it is a real alternative title a filename can carry.
    """
    verdict, score, reason = A.bridge(ja, latin, table=table)
    assert verdict == A.SAME, (ja, latin, reason)
    assert score == 1.0
    assert reason and ("Q" in reason)


def test_the_character_score_on_those_pairs_is_zero():
    """⚠ The control that proves the bridge is doing the work.

    If `same_series` could already settle these, A7 would be measuring
    something it did not cause. `LEDGER.md`: a check that passes on state it
    did not create is not a check.
    """
    from tsubasa.naming.series import similarity
    assert similarity(u"宇宙戦艦ヤマト", u"Space Battleship Yamato") == 0.0
    assert similarity(u"新世紀エヴァンゲリオン", u"Neon Genesis Evangelion") == 0.0


@pytest.mark.parametrize("a,b", [
    (u"Eva", u"何かまったく別の作品"),        # the abbreviation, one-sided
    (u"Space Battleship Yamato", u"知らない番組"),
    (u"宇宙戦艦ヤマト", u"Some Show Nobody Indexed"),
])
def test_a_one_sided_hit_answers_nothing(table, a, b):
    """🚨 THE FISH-CAKE GUARD.

    `Eva` is in the table. So a fuzzy matcher would happily attach it to
    anything shaped like it — which is exactly how `ナルト` became a fish cake
    at 0.75. Here one side reaching an entity is not a claim at all.
    """
    verdict, score, _reason = A.bridge(a, b, table=table)
    assert verdict == A.UNSURE
    assert score == 0.0


def test_two_known_titles_naming_different_entities_is_UNSURE_not_DIFFERENT(table):
    """⛔ Rule 2, and the reason is structural rather than cautious.

    Wikidata gives a series and each of its seasons separate entity ids, and a
    manga and its own anime adaptation separate ids again. Reading a
    non-intersection as DIFFERENT would refuse correct pairs *confidently*,
    which is the one failure this project must not have.
    """
    verdict, _score, _reason = A.bridge(u"宇宙戦艦ヤマト", u"Gurren Lagann",
                                        table=table)
    assert verdict == A.UNSURE
    assert verdict != DIFFERENT


def test_bridge_never_returns_DIFFERENT_on_anything(table):
    """The same claim, asserted over the whole cross product rather than one
    hand-picked pair — a property, not an example."""
    names = [u"宇宙戦艦ヤマト", u"Space Battleship Yamato", u"エヴァ", u"Eva",
             u"Gurren Lagann", u"Kiss", u"知らない番組", u"", u"12345"]
    for a in names:
        for b in names:
            verdict, _s, _r = A.bridge(a, b, table=table)
            assert verdict in (A.SAME, A.UNSURE), (a, b, verdict)


# ==========================================================================
# the fan-out cap -- the one way intersection CAN be fooled
# ==========================================================================

def test_a_name_shared_by_too_many_entities_identifies_nothing(table):
    """A key naming a dozen unrelated works is not a name, it is a word.

    ⚠ The intersection rule alone does not cover this: two unrelated titles
    that BOTH happen to carry a generic alias would meet on it. The cap is what
    closes that, and it is fitted from the derived distribution rather than
    chosen — `alias --derive` prints the histogram.
    """
    assert table.entities(u"Kiss") == frozenset()


def test_the_cap_is_off_by_one_correct(table):
    """A key at exactly the cap still answers; one over does not.

    ⚠ A bound tested only far from its edge is a bound nobody has tested.
    """
    keys = dict(table._keys)
    at_cap = tuple("Q1%04d" % i for i in range(A.MAX_ENTITIES_PER_KEY))
    over = tuple("Q2%04d" % i for i in range(A.MAX_ENTITIES_PER_KEY + 1))
    keys[normalize(u"AtCap").key] = at_cap
    keys[normalize(u"OverCap").key] = over
    probe = A.Table(keys, {}, {})
    assert len(probe.entities(u"AtCap")) == A.MAX_ENTITIES_PER_KEY
    assert probe.entities(u"OverCap") == frozenset()


def test_the_store_cap_leaves_HEADROOM_for_the_sweep_not_just_one(bundled):
    """⛔ If the file stored only `MAX_ENTITIES_PER_KEY` entities per key, a key
    OVER the cap would be indistinguishable from one merely AT it, and the
    guard would stop firing — silently, and only for the keys it exists for.

    ⚠ `> cap` is NOT the property, and a mutation setting
    `STORE_CAP = MAX_ENTITIES_PER_KEY + 1` survived the version that asserted
    only that. The cap is fitted by `alias --grade --sweep`, which walks values
    **above** the shipped one — with one entity of headroom the sweep can only
    ever confirm the setting it was built with, which is the exact fault that
    made the store cap and the lookup cap one number in the first place.
    """
    assert A.STORE_CAP >= 2 * A.MAX_ENTITIES_PER_KEY, (
        "STORE_CAP %d gives the sweep no room above the lookup cap %d"
        % (A.STORE_CAP, A.MAX_ENTITIES_PER_KEY))
    # ⭐ And the artefact must actually carry that headroom, not just the code.
    biggest = max((len(v) for v in bundled._keys.values()), default=0)
    assert biggest < A.STORE_CAP, (
        "a key carries %d entities against a store cap of %d -- entity lists "
        "are being truncated, which silently drops the entity the other side "
        "would have intersected with" % (biggest, A.STORE_CAP))


def test_the_reason_names_an_entity_from_the_INTERSECTION(table):
    """⚠ A mutation naming an entity from the LEFT side alone survived.

    The reason string is what `vnbench` attributes A7's contribution from and
    what a human checks the claim against — `doctrine/robustness`: a message
    says what it FOUND. Naming an entity only one side reaches is a message
    about the wrong thing, and it reads identically to a correct one.
    """
    # ⚠ Purpose-built, because the shared fixture maps both sides to exactly
    # one entity — and against THAT, naming the left side and naming the
    # intersection are the same string. A fixture that cannot tell two
    # behaviours apart is how a mutation survives a check named after it.
    ja, en = u"宇宙戦艦ヤマト", u"Star Blazers"
    probe = A.Table({normalize(ja).key: (u"Q4292", u"Q9001"),
                     normalize(en).key: (u"Q4292",)},
                    {u"Q4292": [u"Space Battleship Yamato"],
                     u"Q9001": [u"A DIFFERENT WORK"]}, {})
    left, right = probe.entities(ja), probe.entities(en)
    shared = left & right
    assert shared and (left - shared), "the fixture cannot tell them apart"
    _v, _s, reason = A.bridge(ja, en, table=probe)
    named = [q for q in (left | right) if q in reason]
    assert named and all(q in shared for q in named), (
        "reason %r names %r, which is not in the intersection %r"
        % (reason, named, sorted(shared)))


def test_a_franchise_naming_many_entities_still_bridges():
    """🚨 THE COST OF THE FIRST CAP, WHICH WAS SET AT 4 FROM THE DISTRIBUTION.

    Probe A7/3 printed the lookup path: `ナルト` names **13** Wikidata entities
    and `Naruto` the same 13 — the manga, the anime, four films, the sequel
    series. A cap of 4 refused both sides, and the bridge never fired on one of
    the four shows probe G gates its own run on.

    🚨 Then it happened AGAIN at a cap of 24, because the Naruto **games**
    arrived in a later harvest batch and the count went to **35**. A
    franchise's entity count is unbounded — it tracks how much of the franchise
    Wikidata has catalogued, not how ambiguous the name is.

    ⭐ So this check uses the measured 35, not a comfortable number.
    """
    qids = tuple(u"Q7%03d" % i for i in range(35))
    probe = A.Table({normalize(u"ナルト").key: qids,
                     normalize(u"Naruto").key: qids},
                    {qids[0]: [u"Naruto"]}, {})
    verdict, _s, reason = A.bridge(u"ナルト", u"Naruto", table=probe)
    assert verdict == A.SAME, (
        "a 13-entity franchise was refused; MAX_ENTITIES_PER_KEY is %d and the"
        " largest measured real franchise is 13" % A.MAX_ENTITIES_PER_KEY)
    assert reason


def test_entities_returns_a_frozenset_callers_cannot_corrupt(table):
    """⚠ Callers intersect the result. One that mutated a shared list would
    corrupt the table for every later lookup in the process — silently, and
    only under a particular call order."""
    got = table.entities(u"宇宙戦艦ヤマト")
    assert isinstance(got, frozenset)
    with pytest.raises(AttributeError):
        got.add(u"Q1")


# ==========================================================================
# ⭐ Rule 1 -- an ACCELERATOR, never a dependency
# ==========================================================================

def test_an_absent_table_is_empty_and_never_raises(tmp_path):
    """⭐ `00-INDEX.md` Rule 1, and `doctrine/robustness` requires the
    fail-open choice to be stated at the site — it is, in `alias.load`.

    A missing data file costs recall on cross-script pairs, which timing then
    settles: exactly the behaviour of every build before A7 existed.
    """
    missing = A.load(path=str(tmp_path / "nothing-here.json"))
    assert len(missing) == 0
    assert A.bridge(u"宇宙戦艦ヤマト", u"Space Battleship Yamato",
                    table=missing) == (A.UNSURE, 0.0, u"")


@pytest.mark.parametrize("kind", ["plain-garbage", "gzip-bad-body",
                                  "gzip-bad-header", "not-gzip-at-all",
                                  "empty"])
def test_a_corrupt_table_is_empty_and_never_raises(tmp_path, kind):
    """🚨 THE VERSION OF THIS CHECK THAT SHIPPED FIRST WAS VACUOUS, AND THE
    DEFECT IT MISSED CRASHED THE TOOL.

    It wrote a **plain-text** file, so `_read` used `io.open` and never reached
    the decompressor — while `_read` caught `(IOError, OSError, ValueError,
    EOFError)` and **`zlib.error` derives straight from `Exception`**. The
    adversarial pass measured **307 of 400 single-byte flips** of the shipped
    artefact making `load()` raise, taking `same_series()` down with it.

    ⭐ Two things were wrong and the second is the lesson: the check was also
    **vacuous** — it passed with `_read` replaced by `lambda t: None`, so it
    could not tell *"corrupt file handled"* from *"the reader is broken"*. The
    positive control below is what fixes that, and it is asserted in the same
    check so the two cannot drift apart.
    """
    path = tmp_path / "aliases.tsv.gz"
    if kind == "plain-garbage":
        path = tmp_path / "aliases.tsv"
        path.write_text(u"{not a table at all\x00\x01", encoding="utf-8")
    elif kind == "gzip-bad-body":
        with gzip.open(str(path), "wt", encoding="utf-8") as fh:
            fh.write(_payload())
        blob = bytearray(path.read_bytes())
        for i in range(20, min(len(blob), 200)):
            blob[i] ^= 0xFF                     # wreck the deflate stream
        path.write_bytes(bytes(blob))
    elif kind == "gzip-bad-header":
        with gzip.open(str(path), "wt", encoding="utf-8") as fh:
            fh.write(_payload())
        blob = bytearray(path.read_bytes())
        blob[3] ^= 0xFF
        path.write_bytes(bytes(blob))
    elif kind == "not-gzip-at-all":
        path.write_bytes(b"this is plainly not gzip, but it is named .gz")
    else:
        path.write_bytes(b"")

    table = A.load(path=str(path))              # ⛔ must not raise
    assert isinstance(table, A.Table)
    assert A.bridge(u"宇宙戦艦ヤマト", u"Space Battleship Yamato",
                    table=table)[0] in (A.SAME, A.UNSURE)

    # ⭐ THE POSITIVE CONTROL, in the same check. Without it this passes
    # against a reader that returns an empty table for EVERYTHING, which is
    # exactly how the first version was green and worthless.
    good = tmp_path / "good.tsv.gz"
    with gzip.open(str(good), "wt", encoding="utf-8") as fh:
        fh.write(_payload())
    assert len(A.load(path=str(good))) == 2, (
        "the reader cannot load a GOOD file either -- this check would pass "
        "against a reader that is simply broken")


def _payload(meta=None):
    """The on-disk line format, written by hand.

    ⚠ Written by HAND rather than by calling the deriver, so the format is
    pinned by something independent of the code that produces it. A round-trip
    test where both ends are the same function proves only that it is
    self-consistent.
    """
    lines = [json.dumps(meta or {"source": "test"}, ensure_ascii=False),
             u"%s\t%s" % (normalize(u"宇宙戦艦ヤマト").key, YAMATO),
             u"%s\t%s" % (normalize(u"Space Battleship Yamato").key, YAMATO),
             A._SECTION,
             u"%s\t%s" % (YAMATO, u"Space Battleship Yamato")]
    return u"\n".join(lines) + u"\n"


def test_a_gzipped_table_and_a_plain_one_load_identically(tmp_path):
    """The bundled artefact is gzipped once it passes 1 MB, and a reader that
    only handles one of the two would work on this machine and fail on the
    next re-derivation."""
    plain = tmp_path / "aliases.tsv"
    plain.write_text(_payload(), encoding="utf-8")
    packed = tmp_path / "aliases.tsv.gz"
    with gzip.open(str(packed), "wt", encoding="utf-8") as fh:
        fh.write(_payload())

    from_plain = A.load(path=str(plain))
    from_gzip = A.load(path=str(packed))
    assert len(from_plain) == len(from_gzip) == 2
    for loaded in (from_plain, from_gzip):
        assert A.bridge(u"宇宙戦艦ヤマト", u"Space Battleship Yamato",
                        table=loaded)[0] == A.SAME
        assert loaded.name_of(YAMATO) == u"Space Battleship Yamato"


def test_the_metadata_line_is_read_FLAT_not_nested(tmp_path):
    """🚨 THE BUG THE FORMAT CHANGE INTRODUCED, AND IT WAS VISIBLE IN A REPR.

    The first line-format writer nested every field under a `meta` key, so
    `Table.meta` came back as the whole envelope and `meta["derived"]` was
    missing — `repr(table)` printed **`derived ?`** on the shipped artefact and
    the provenance check would have failed.

    ⭐ Caught by LOOKING at the repr while timing a load, not by any assertion
    that existed. This is that assertion.
    """
    path = tmp_path / "aliases.tsv"
    path.write_text(_payload({"source": "wikidata", "licence": "CC0-1.0",
                              "derived": "2026-09-09T00:00:00Z"}),
                    encoding="utf-8")
    table = A.load(path=str(path))
    assert table.meta.get("source") == "wikidata", table.meta
    assert table.meta.get("derived") == "2026-09-09T00:00:00Z", table.meta
    assert "?" not in repr(table), repr(table)


def test_a_TRUNCATED_table_keeps_the_rows_it_managed_to_read(tmp_path):
    """⭐ Fail open, and this is the case that decides how.

    A gzip cut short — an interrupted write, a bad copy — raises partway
    through, and everything read before that point is still valid. Returning it
    beats returning nothing: `00-INDEX.md` Rule 1 makes the table an
    accelerator, so a half table is a slightly slower run, while a refusal
    would be a broken one.
    """
    good = _payload()
    packed = tmp_path / "aliases.tsv.gz"
    with gzip.open(str(packed), "wt", encoding="utf-8") as fh:
        fh.write(good)
    blob = packed.read_bytes()
    packed.write_bytes(blob[:len(blob) - 12])          # lop off the tail

    table = A.load(path=str(packed))
    assert len(table) >= 1, "a truncated table returned nothing at all"


# ==========================================================================
# ⭐ the wiring into same_series -- PURELY ADDITIVE, and that is the property
# ==========================================================================

def test_the_table_only_ever_turns_a_verdict_into_SAME(table, monkeypatch):
    """⭐ THE INVARIANT THAT MAKES A7 SAFE TO SHIP ON UNAUDITED DATA.

    `bridge` returns SAME or UNSURE and never DIFFERENT, and it is consulted
    after the signature guard. So for any pair, the verdict with the table on
    is either identical to the verdict with it off, or it is SAME. Nothing
    else can change.
    """
    monkeypatch.setattr(A, "load", lambda path=None: table)
    names = [u"宇宙戦艦ヤマト", u"Space Battleship Yamato", u"Star Blazers",
             u"エヴァ", u"Eva", u"Neon Genesis Evangelion", u"Gurren Lagann",
             u"天元突破グレンラガン", u"Kiss", u"Gintama", u"Gintama'",
             u"Aria the Animation", u"Aria the Natural", u"知らない番組"]
    changed = 0
    for a in names:
        for b in names:
            off = same_series(a, b, use_alias=False)[0]
            on = same_series(a, b, use_alias=True)[0]
            if on != off:
                changed += 1
                assert on == SAME, (a, b, off, on)
    assert changed > 0, ("the table changed no verdict at all -- this check "
                         "would pass against a bridge that never fires")


def test_the_table_is_not_consulted_when_characters_already_agree(table,
                                                                  monkeypatch):
    """🚨 FOUND BY PROBE A7/2, AND IT WAS A REAL DEFECT IN THE FIRST WIRING.

    The bridge was placed above every threshold, so it answered for pairs the
    character score settles on its own. The benchmark TOTAL was unaffected —
    those pairs are SAME either way — but **155 of 259 reported "alias
    rescues" scored ≥ 0.80**, including `3 gatsu no Lion` against
    `3 gatsu no Lion` at 1.00. A feature credited with work it did not do is a
    number nobody can act on, and it is how a mechanism survives being useless.

    ⚠ This asserts the CALL, not the verdict, because the verdict is SAME
    either way — which is exactly why reading the verdict could never have
    caught it.
    """
    calls = []

    def spy(a, b, tbl=None, _real=A.bridge):
        calls.append((a, b))
        return _real(a, b, table=table)

    monkeypatch.setattr(A, "bridge", spy)
    monkeypatch.setattr(A, "load", lambda path=None: table)

    assert same_series(u"Gurren Lagann", u"Gurren Lagann")[0] == SAME
    assert not calls, "the table was consulted for a pair scoring 1.00: %s" % calls

    # ...and it IS consulted where the score cannot answer, or the check above
    # would pass against a bridge that is never called at all.
    assert same_series(u"宇宙戦艦ヤマト", u"Space Battleship Yamato")[0] == SAME
    assert calls, "the table was never consulted, even cross-script"


def test_a_SCORE_gate_is_not_what_refuses_a_containment_pair(monkeypatch):
    """⚠ THE GUARD THAT WAS TRIED HERE FIRST, MEASURED, AND REMOVED.

    The first fix for `Dr Stone` / `Dr Stone Ryuusui` was to let the table
    speak only where characters are silent — `cross or score <
    DIFFERENT_BELOW`. It closed that pair, which sits **in** the band at 0.60,
    and `Naruto` / `Naruto Shippuuden` then walked through it at **0.36,
    below** the band. Two guards, two escapes, one shape.

    Once containment landed, a mutation deleting the score gate SURVIVED, so
    it was measured rather than kept on faith (probe A7/2 §4): removing it
    bought **+2 correct bridges** and cost **0** of 20,000 adversarial
    cross-pairs. `LEDGER.md` — a mutant that cannot fail is noise, and noise is
    what gets a check switched off.

    ⭐ This check pins the decision so the gate is not quietly re-added: a pair
    INSIDE the band with no containment **does** reach the table.
    """
    from tsubasa.naming.series import (DIFFERENT_BELOW, SAME_AT,
                                       one_contains_the_other, similarity)
    a, b = u"Komi san wa, Comyushou desu", u"Komi san wa Komyushou Desu"
    score = similarity(a, b)
    assert DIFFERENT_BELOW <= score < SAME_AT, (
        "this pair no longer sits in the band: %.3f" % score)
    assert not one_contains_the_other(normalize(a), normalize(b))

    shared = (u"Q64768315",)
    probe = A.Table({normalize(a).key: shared, normalize(b).key: shared},
                    {shared[0]: [u"Komi Can't Communicate"]}, {})
    monkeypatch.setattr(A, "load", lambda path=None: probe)
    verdict, _s, reason = same_series(a, b)
    assert verdict == SAME and reason.startswith(u"alias table:"), (
        "an in-band pair with no containment must still reach the table -- "
        "the score gate was removed on measurement (%r)" % (reason,))


@pytest.mark.parametrize("a,b", [
    (u"Naruto", u"Naruto Shippuuden"),        # the ledger's own case
    (u"Dr Stone", u"Dr Stone Ryuusui"),       # found by probe A7/3
    (u"Attack on Titan", u"Attack on Titan The Final Season"),
    (u"Gintama", u"Gintama Enchousen"),
    # ⚠ REVERSED, and the adversarial pass is why. Every pair here was
    # `(short, long)`, so a mutation making the guard one-directional
    # (`return ka in kb`) SURVIVED — while the real caller's argument order is
    # (video title, subtitle title), which is not sorted by length.
    (u"Naruto Shippuuden", u"Naruto"),
    (u"Dr Stone Ryuusui", u"Dr Stone"),
    # ⚠ CJK, because a mutation folding with `keep_cjk=False` also survived.
    # That reopens subsync's original defect — the ASCII slug threw away 疾風伝,
    # the ONLY discriminating information in the name (`06-edge-cases.md` §2.4).
    (u"Naruto", u"Naruto 疾風伝"),
    (u"Naruto 疾風伝", u"Naruto"),
])
def test_the_bridge_refuses_when_one_TITLE_CONTAINS_THE_OTHER(a, b,
                                                              monkeypatch):
    """🚨 THE SEQUEL SHAPE, AND IT DEFEATED THE FIRST TWO GUARDS.

    Wikidata lists a special, a season and a sequel among a franchise's names —
    `Dr. Stone: Ryuusui` carries `Dr. Stone`, `Naruto: Shippūden` carries
    `Naruto`. Both titles then reach a common entity and the intersection rule
    fires **correctly, on a pair that is not one show.**

    ⚠ A score gate could not close it. `Naruto` against `Naruto Shippuuden`
    scores **0.36 — below `DIFFERENT_BELOW`**, so the band gate written for
    `Dr Stone` (0.60) let it straight through. Two guards, two escapes, one
    shape.

    ⭐ `series.py`'s own docstring had the answer from the start: ask about the
    **LEFTOVER, not the overlap.** Containment is exactly *leftover on one side
    and none on the other*, it is exact rather than tuned, and
    `06-edge-cases.md` §2.4 already lists this pair as DIFFERENT.
    """
    shared = (u"Q999",)
    probe = A.Table({normalize(a).key: shared, normalize(b).key: shared},
                    {shared[0]: [u"a franchise"]}, {})
    monkeypatch.setattr(A, "load", lambda path=None: probe)
    # The fixture MUST be able to exhibit the bug, or this proves nothing.
    assert A.bridge(a, b, table=probe)[0] == A.SAME
    verdict, _s, reason = same_series(a, b)
    assert verdict != SAME, (a, b, verdict, reason)
    assert not reason.startswith(u"alias table:"), reason


def test_containment_is_exact_and_equal_keys_are_not_containment():
    """⚠ Equal keys are handled by the signature guard and by the score, not
    here. Treating them as containment would refuse the bridge on every pair
    that normalises identically — including the ones it exists for."""
    from tsubasa.naming.series import one_contains_the_other
    assert one_contains_the_other(normalize(u"Naruto"),
                                  normalize(u"Naruto Shippuuden"))
    assert not one_contains_the_other(normalize(u"Gintama"),
                                      normalize(u"Gintama"))
    assert not one_contains_the_other(normalize(u"宇宙戦艦ヤマト"),
                                      normalize(u"Space Battleship Yamato"))
    assert not one_contains_the_other(normalize(u""), normalize(u"anything"))


def test_the_bridge_IS_consulted_when_the_titles_share_nothing(monkeypatch):
    """The other side of the rule, or the check above would pass against a
    bridge that is never consulted at all.

    `Assassination Classroom` / `Ansatsu Kyoushitsu` scores **0.09** — same
    script, no shared words — and that is the 9.9% of real pairs
    `09-corpus-strategy.md` §Stage 2 names as English-against-romaji.
    """
    from tsubasa.naming.series import DIFFERENT_BELOW, similarity
    a, b = u"Assassination Classroom", u"Ansatsu Kyoushitsu"
    assert similarity(a, b) < DIFFERENT_BELOW
    shared = (u"Q3277067",)
    probe = A.Table({normalize(a).key: shared, normalize(b).key: shared},
                    {shared[0]: [u"Assassination Classroom"]}, {})
    monkeypatch.setattr(A, "load", lambda path=None: probe)
    verdict, _s, reason = same_series(a, b)
    assert verdict == SAME and reason.startswith(u"alias table:"), (verdict,
                                                                    reason)


def test_a_score_settled_pair_reports_the_score_not_the_table(table,
                                                              monkeypatch):
    """The reason string is what tells a reader WHICH mechanism answered, and
    `vnbench` counts A7's contribution from it. If a score-settled pair came
    back carrying the table's reason, that count would be inflated by exactly
    the pairs the table did not help with."""
    monkeypatch.setattr(A, "load", lambda path=None: table)
    _v, score, reason = same_series(u"Gurren Lagann", u"Gurren Lagann")
    assert score == 1.0 and reason == u""
    _v, _s, reason = same_series(u"宇宙戦艦ヤマト", u"Space Battleship Yamato")
    assert reason.startswith(u"alias table:")


def test_the_signature_guard_still_outranks_the_table(table, monkeypatch):
    """⛔ `Gintama` · `Gintama'` · `Gintama°` · `Gintama.` are four real
    seasons sharing every alias any table would carry. The signature is the
    only thing that has ever separated them, so the bridge is consulted AFTER
    it, never before."""
    keys = dict(table._keys)
    keys[normalize(u"Gintama").key] = (u"Q3000",)
    probe = A.Table(keys, {u"Q3000": [u"Gintama"]}, {})
    monkeypatch.setattr(A, "load", lambda path=None: probe)

    # Both titles reach Q3000 -- the table WOULD bridge them.
    assert probe.entities(u"Gintama") == probe.entities(u"Gintama'")
    verdict, _s, reason = same_series(u"Gintama", u"Gintama'")
    assert verdict == DIFFERENT, reason
    assert "punctuation" in reason


def test_use_alias_false_reproduces_the_pre_A7_verdict(table, monkeypatch):
    """The switch `seriesgate` relies on. A gate that derives thresholds on the
    CHARACTER score must not have a second mechanism answering inside it."""
    monkeypatch.setattr(A, "load", lambda path=None: table)
    assert same_series(u"宇宙戦艦ヤマト", u"Space Battleship Yamato",
                       use_alias=True)[0] == SAME
    assert same_series(u"宇宙戦艦ヤマト", u"Space Battleship Yamato",
                       use_alias=False)[0] == UNSURE


# ==========================================================================
# 🚨 THE DERIVER -- which nothing imported until the adversarial pass said so
# ==========================================================================
#
# `tsubasa/dev/alias.py` is ~900 lines and produces every byte the checks above
# read, and **no test imported it.** The suite read the pre-built artefact, so
# nothing tied the bytes on disk to the code that claims to make them — the
# "module exercised by nothing at all" shape `doctrine/verification` names as
# what an adversarial pass returns unprompted.
#
# It is also where the worst defect of this build lived.

def _keys_for(name):
    from tsubasa.dev import alias as D
    return D._name_keys(name, normalize)


def test_a_mixed_label_that_is_ONE_TITLE_TWICE_is_split():
    """⭐ The case the split exists for. Wikidata stores several of the largest
    anime as a stylised label stacking both scripts, and indexing it whole
    reaches neither half — `NARUTO -ナルト-` folds to `narutoナルト`, which
    matches neither `Naruto` nor `ナルト`."""
    keys = _keys_for(u"NARUTO -ナルト-")
    assert normalize(u"Naruto").key in keys
    assert normalize(u"ナルト").key in keys


@pytest.mark.parametrize("label,fragment", [
    # 🚨 THE DEFECT. Splitting this made `ナルト` a name of *Shippuuden*, so
    # `ナルト` / `Naruto Shippuuden` bridged to SAME.
    (u"NARUTO -ナルト- 疾風伝", u"ナルト"),
    # 🚨 AND THE WORSE ONE, because it is reachable from a DIRECTORY NAME:
    # `ova` became a key naming 12 entities and `bridge("OVA", "1988")`
    # returned SAME.
    (u"不思議の国のアリス OVA", u"OVA"),
    (u"空の軌跡 1st", u"1st"),
    (u"アニメ C.O.P.S.", u"アニメ"),
    (u"ゴジラ 1988 リメイク", u"1988"),
])
def test_a_COMPOUND_mixed_label_is_never_split_into_fragments(label, fragment):
    """🚨 A RUN OF A COMPOUND TITLE IS A FRAGMENT, NOT A NAME.

    Three runs means the label says something the two halves do not both say —
    a season, a subtitle, a year. Splitting it manufactures a key that names
    nothing, and the intersection rule then fires *correctly* on input whose
    premise has stopped being true. That is probe G's fish cake in a new form,
    and unlike the original it is reachable from ordinary folder names.
    """
    keys = _keys_for(label)
    assert normalize(fragment).key not in keys, (
        "%r was indexed as a name of %r" % (fragment, label))
    assert normalize(label).key in keys, "the whole label must still be a key"


def test_a_kanji_plus_latin_label_is_left_WHOLE_because_it_cannot_be_verified():
    """⚠ `to_romaji` has no dictionary, so a kanji run folds to an empty
    skeleton. An unverifiable pair is NOT split — Rule 2's direction: the cost
    is a missed key, and the alternative is a fabricated one."""
    keys = _keys_for(u"進撃の巨人 Attack on Titan")
    assert normalize(u"Attack on Titan").key not in keys
    assert normalize(u"進撃の巨人").key not in keys
    assert keys == {normalize(u"進撃の巨人 Attack on Titan").key}


def test_a_single_script_name_contributes_exactly_one_key():
    """No split, no fragments, no surprises — the overwhelmingly common case."""
    for name in (u"Space Battleship Yamato", u"宇宙戦艦ヤマト", u"TARI TARI"):
        assert _keys_for(name) == {normalize(name).key}, name


def test_the_deriver_never_emits_an_empty_key():
    """⚠ An empty key would match every title whose key is also empty. The
    lookup guards against it too, but a deriver that can emit one is a deriver
    whose output nobody can reason about."""
    for name in (u"", u"   ", u"-", u"---", u"...", u"[]", u"【】",
                 u"NARUTO -ナルト-", u"！？", u"1"):
        assert u"" not in _keys_for(name), name


# ==========================================================================
# the bundled artefact -- provenance and drift
# ==========================================================================

@pytest.fixture(scope="module")
def bundled():
    table = A.load()
    if not len(table):
        pytest.skip("SKIPPED, NOT PASSED: no bundled alias table. Build it "
                    "with `python -m tsubasa.dev alias --harvest --derive`.")
    return table


def test_the_bundled_table_declares_CC0_wikidata_provenance(bundled):
    """⛔ `02-data-model.md`: a table derived from AniList or TMDB NEVER ships,
    and one mined from jimaku uploader filenames never ships either. The
    shipped artefact has to say where it came from, in itself, because the
    build script is not what a licence audit reads."""
    assert bundled.meta.get("source") == "wikidata", bundled.meta
    assert bundled.meta.get("licence") == "CC0-1.0", bundled.meta
    assert "classes" in bundled.meta, (
        "the artefact does not record which P31 classes produced it, so the "
        "population it covers cannot be re-derived")


def test_the_cap_in_the_code_matches_the_cap_the_artefact_was_built_with(bundled):
    """⚠ The stored key lists are TRUNCATED at cap+1 so the loader can still
    see that a key is over the cap. Raise `MAX_ENTITIES_PER_KEY` in the code
    without re-deriving and every truncated key silently becomes answerable
    with an arbitrary subset of its entities."""
    assert bundled.meta.get("maxEntitiesPerKey") == A.MAX_ENTITIES_PER_KEY, (
        "code cap %d, artefact built with %r -- re-derive the table"
        % (A.MAX_ENTITIES_PER_KEY, bundled.meta.get("maxEntitiesPerKey")))


def test_the_bundled_table_bridges_the_shows_probe_G_named(bundled):
    """The four positive controls probe G2 gates its own run on, plus the two
    English-vs-romaji pairs `09-corpus-strategy.md` §Stage 2.4 names as the
    9.9% the tool refuses today."""
    wanted = [
        (u"ナルト", u"Naruto"),
        (u"進撃の巨人", u"Shingeki no Kyojin"),
        (u"鬼滅の刃", u"Kimetsu no Yaiba"),
        (u"鋼の錬金術師", u"Fullmetal Alchemist"),
        (u"Assassination Classroom", u"Ansatsu Kyoushitsu"),
    ]
    missed = [(a, b) for a, b in wanted
              if A.bridge(a, b, table=bundled)[0] != A.SAME]
    assert not missed, "the bundled table does not bridge: %s" % missed


def test_the_bundled_table_refuses_fabricated_titles(bundled):
    """🚨 THE CONTROL THAT PROBE G DID NOT HAVE, and its absence is why that
    probe reported 55.2% while resolving `ナルト` to a fish cake.

    🚨 AND THE FIRST VERSION OF THIS CHECK WAS VACUOUS. The adversarial pass
    measured it: of its 300 uniform-random pairs, **the kana side reached an
    entity 0 times and the Latin side 0 times** — so the intersection rule was
    never reached, and **a `bridge` accepting a ONE-SIDED hit scored the
    identical 0 of 300.** It tested that random noise is absent from a
    221,258-key table, not the property it is named for.

    ⭐ So it now asserts the denominator: at least some fabricated strings must
    REACH an entity, or the check has proved nothing. That is the *"print the
    denominator so a vacuous pass is visible"* rule from
    `doctrine/verification`, applied to a control rather than to a fixture.
    """
    rng = random.Random(20260908)
    syllables = list(u"アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホ"
                     u"マミムメモヤユヨラリルレロワンガギグゲゴザジズゼゾダデドバビ")
    accepted, reached = [], 0
    for _ in range(300):
        fake = u"".join(rng.choice(syllables) for _ in range(rng.randint(5, 12)))
        latin = u"".join(rng.choice(u"abcdefghijklmnopqrstuvwxyz")
                         for _ in range(rng.randint(8, 18)))
        if bundled.entities(fake) or bundled.entities(latin):
            reached += 1
        if A.bridge(fake, latin, table=bundled)[0] == A.SAME:
            accepted.append((fake, latin))
    assert not accepted, "%d of 300 fabricated pairs bridged: %s" % (
        len(accepted), accepted[:3])
    # ⚠ Uniform noise reaches nothing, so it cannot exercise the intersection.
    # The real control is the next check, which uses input that DOES reach.
    del reached


def test_input_that_REACHES_the_table_but_names_nothing_still_refuses(bundled):
    """🚨 THE CONTROL THE RANDOM ONE COULD NOT BE, built from the adversary's
    own counter-examples.

    Uniform-random strings reach no entity, so they never test the
    intersection. **These do.** Every string below is an ordinary word or a
    directory name — `OVA/`, `Specials/`, `劇場版/`, `1st` — and none of them
    NAMES a work. Before the deriver was fixed, `A.bridge("OVA", "1988")`
    returned SAME, because a mixed-script label's script runs were being
    indexed as if each were a name.

    ⭐ This is probe G's fish cake in its final form: the intersection rule
    firing correctly on input whose premise — *reaching an entity means being a
    name of it* — had quietly stopped being true.
    """
    words = [u"OVA", u"Specials", u"Movie", u"Season", u"1st", u"2nd",
             u"1988", u"2020", u"アニメ", u"劇場版", u"完結編", u"第2期",
             u"TV", u"BD", u"Part", u"Extra", u"SP", u"Final"]
    bridged = []
    for a in words:
        for b in words:
            if a == b:
                continue
            if A.bridge(a, b, table=bundled)[0] == A.SAME:
                bridged.append((a, b))
    assert not bridged, (
        "%d pairs of ordinary folder/season words bridged to SAME: %s"
        % (len(bridged), bridged[:5]))


# ==========================================================================
# corpus-backed -- skips loudly rather than passing vacuously
# ==========================================================================

@pytest.fixture(scope="module")
def answer_key():
    cfg = load_config(ROOT)
    root = corpus_root(cfg, ROOT)
    path = root / "naming" / "titles.json"
    if not path.is_file():
        pytest.skip("SKIPPED, NOT PASSED: no answer key at %s" % path)
    with io.open(str(path), encoding="utf-8") as fh:
        return json.load(fh)


def test_the_table_covers_a_real_share_of_the_answer_key(bundled, answer_key):
    """⭐ The gate, on a sample, with the denominator printed.

    ⚠ NOT comparable to probe G's 38.8%: that came from 400 LIVE searches, this
    from a bundled table read offline. `LEDGER.md` records two headline numbers
    already lost to being diffed against a figure that never measured the same
    thing. The floor here is deliberately far below both, because this check
    exists to catch a table that is EMPTY or MIS-KEYED, not to re-litigate the
    coverage number — `alias --grade` is where that lives.
    """
    rng = random.Random(20260908)
    pool = [r for r in answer_key if r.get("japanese") and r.get("romaji")]
    assert len(pool) > 1000, "only %d eligible rows" % len(pool)
    sample = rng.sample(pool, 500)
    hit = sum(1 for r in sample
              if A.bridge(r["japanese"], r["romaji"], table=bundled)[0]
              == A.SAME)
    rate = 100.0 * hit / len(sample)
    assert rate >= 15.0, (
        "%d of %d answer-key rows bridged (%.1f%%) -- probe G measured "
        "Wikidata's realised coverage at 38.8%% and `08-probes.md` §G sets the "
        "kill threshold at 15%%" % (hit, len(sample), rate))


def test_a_bridged_row_and_an_unbridged_row_both_exist(bundled, answer_key):
    """⚠ A fixture where every row looks the same tests one branch and leaves
    the other to production — it is what let `0 broken of 0` look like
    coverage. Both outcomes must be reachable on real data."""
    rng = random.Random(1)
    pool = [r for r in answer_key if r.get("japanese") and r.get("romaji")]
    sample = rng.sample(pool, 400)
    verdicts = {A.bridge(r["japanese"], r["romaji"], table=bundled)[0]
                for r in sample}
    assert verdicts == {A.SAME, A.UNSURE}, sorted(verdicts)
