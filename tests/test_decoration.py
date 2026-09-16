# -*- coding: utf-8 -*-
"""
The decoration vocabulary. RUNBOOK step A2c.

⭐ THE CLAIM UNDER TEST

A token is decoration when it appears in many shows' FILENAMES and almost
never in those shows' CANONICAL TITLES — `df >= 25 shows AND canonical-title
rate < 5%`. That rule, run over 203,591 non-sealed catalogue rows and 11,210
shows, finds **176 tokens**: the release groups, the Japanese broadcasters,
the streaming services and the caption markers nobody wrote a regex for.

🚨 AND THE CLAIM THAT MATTERS MORE: that it never eats a real title.

`LEDGER.md` §Logic: **a short ambiguous token is only noise in a TAG
CONTEXT.** A learned vocabulary does not escape that — `ja`, `tv`, `end` and
the single kanji `新` are all decoration by the measure above and all live
inside real titles. The vocabulary decides WHICH tokens; the CONTEXT decides
whether. Most of this file is about the context.

⚠ The derivation itself needs the corpus and is graded by
`python -m tsubasa.dev decoration --grade`. What is checked here is the
SHIPPED artefact and the applier, both of which travel with the package — so
these checks run on a machine with no corpus at all.
"""
import io
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tsubasa.naming import decoration as D                # noqa: E402

DATA = ROOT / "tsubasa" / "data" / "decoration.json"

# ⭐ Real titles that MUST survive, each one paid for.
# The first four are `LEDGER.md` §Logic's own list of titles the hand list
# destroyed. The CJK ones are the danger a LEARNED vocabulary adds: it
# contains single kanji, which are only ever tokens when they stand alone.
PROTECTED_TITLES = [
    u"Kingsglaive - Final Fantasy XV",
    u"Bakemono no Ko",
    u"Ja Ja Uma - 05",
    u"Mad Max Fury Road",
    u"Gintama Final",
    u"新世紀エヴァンゲリオン",          # 新 is in the vocabulary
    u"終わりのセラフ",                  # 終 is in the vocabulary
    u"初恋",                            # 初 is in the vocabulary
    u"シン・ゴジラ",
    u"Steins;Gate 0",
    u"Mobile Suit Gundam 00",
    u"86 - Eighty Six",
    u"K-On!",
    u"Dungeon ni Deai wo Motomeru no wa Machigatteiru Darou ka",
]


@pytest.fixture(scope="module")
def vocab():
    v = D.load()
    if not len(v):
        pytest.skip("SKIPPED, NOT PASSED: no vocabulary at %s. Derive it with "
                    "`python -m tsubasa.dev decoration --derive` (needs the "
                    "corpus)." % DATA)
    return v


# ==========================================================================
# the shipped artefact
# ==========================================================================

def test_the_vocabulary_ships_and_records_how_it_was_made(vocab):
    """⚠ A bundled data file with no provenance is a number nobody can
    re-derive. `02-data-model.md` calls the learned rules re-derivable by one
    command; the artefact has to say which one and over what."""
    assert DATA.is_file(), "%s is missing" % DATA
    with io.open(str(DATA), encoding="utf-8") as fh:
        raw = json.load(fh)
    meta = raw.get("meta") or {}
    for field in ("derived", "minShows", "maxTitleRate", "shows",
                  "catalogueLines", "sealedSkipped"):
        assert field in meta, "meta is missing %r: %s" % (field, sorted(meta))
    assert meta["minShows"] == 25
    assert abs(meta["maxTitleRate"] - 0.05) < 1e-9
    assert meta["shows"] > 5000, meta["shows"]
    assert "decoration --derive" in (raw.get("//") or "")


def test_the_vocabulary_is_the_right_order_of_magnitude(vocab):
    """⚠ Derived, never pinned. The corpus grows and a future crawl moves this
    number; what would be a defect is it collapsing to nothing or exploding
    into the whole token space."""
    assert 80 <= len(vocab) <= 400, (
        "%d tokens -- the measured derivation gives ~176 and "
        "CORPUS-OPPORTUNITIES.md 3.1 reports 185" % len(vocab))


def test_it_contains_the_tokens_the_corpus_review_named(vocab):
    """⭐ The independent check: `CORPUS-OPPORTUNITIES.md` §3.1 lists the
    tokens ITS derivation found, written down before this code existed. All of
    them must appear, or the rule was implemented differently from the one
    that produced the reported figure."""
    named = (u"ja cc netflix dl jp jpn jptvclub amazon sdh aac2 magicstar end "
             u"hulu tv dougal nanakoraws raws chs kamigami amzn ddp2 nf sub "
             u"erai sup hevc10 crf shincaps kissaten nekomoe bdsup 最終話 前編 "
             u"後編 retimed anime studio idx bandai vcb ddp5 lolihouse abema "
             u"wowow fod tx tbs judas subsplease 日本統一シリーズ 最終回 ocr "
             u"tver kktv viki dmmtv").split()
    missing = [t for t in named if t not in vocab]
    assert not missing, "%d of %d named tokens absent: %s" % (
        len(missing), len(named), missing)


def test_no_episode_number_is_in_the_vocabulary(vocab):
    """🚨 `001`, `e07`, `s01e05`, `第三話` all satisfy *df >= 25 and rate < 5%*
    perfectly, and the first derivation returned **264 pure-digit tokens of
    664**. They are not decoration — they are what the PARSER extracts — and a
    vocabulary carrying digits would let the aggressive path eat
    `Gundam 0080`, `Steins;Gate 0` and `86`."""
    import re
    bad = [t for t in vocab.tokens
           if re.match(u"^(?:[0-9]+|e[p]?[0-9]+|s[0-9]+(?:e[0-9]+)?|v[0-9]+"
                       u"|[0-9]+v[0-9]+|第[0-9〇一二三四五六七八九十百千]+[話回])$",
                       t, re.I)]
    assert not bad, "episode-shaped tokens in the vocabulary: %s" % sorted(bad)[:12]


def test_the_protection_list_is_enforced_at_load_not_only_at_derivation(tmp_path):
    """⛔ A hand-edited or stale data file must not be able to reintroduce a
    real title word. The derivation strips `PROTECTED`; so does `load`."""
    path = tmp_path / "poisoned.json"
    path.write_text(json.dumps(
        {"tokens": sorted(D.PROTECTED) + ["subsplease"], "meta": {}}),
        encoding="utf-8")
    loaded = D.load(str(path))
    assert "subsplease" in loaded
    for word in D.PROTECTED:
        assert word not in loaded, "%r survived the load-time filter" % word


# ==========================================================================
# 🚨 the guard: a real title is never damaged
# ==========================================================================

@pytest.mark.parametrize("title", PROTECTED_TITLES)
def test_a_real_title_survives_even_aggressive_stripping(title, vocab):
    """The defect class this whole module is shaped around. Aggressive is the
    strongest setting, used for films, unknowns and folder names."""
    assert D.strip(title, vocab, aggressive=True) == title, (
        "%r was damaged" % title)


def test_a_single_kanji_inside_a_word_is_not_stripped(vocab):
    """🚨 The danger a LEARNED vocabulary adds that a hand list did not.

    Single kanji — 新, 終, 初, 話, 字 — are legitimately in the vocabulary,
    because CJK does not word-break and they are only ever tokens when they
    stand alone.

    ⭐ What protects `新世紀エヴァンゲリオン` is the TOKENISER, not a word
    boundary: `_TOKEN` groups contiguous CJK, so `新` is never *found* inside
    the title and the vocabulary never gets a chance to match it. That was
    established by the mutation run — a mutant breaking the old Latin-only
    boundary survived, and so did one reintroducing interior stripping; only
    per-character tokenisation AND interior stripping together take this title
    to `世紀エヴァンゲリオン`. `_work/probe_adj12_decorationmutants.py`.
    """
    assert u"新" in vocab or u"終" in vocab, (
        "this check is vacuous unless a single kanji is in the vocabulary")
    for title in (u"新世紀エヴァンゲリオン", u"新機動戦記ガンダムW", u"終わりのセラフ"):
        assert D.strip(title, vocab, aggressive=True) == title, title


def test_cleaning_never_returns_an_empty_title(vocab):
    """⚠ An empty key pairs with EVERY video sharing an episode number —
    `08-probes.md` §C measured that at 4,133 files. A name made entirely of
    decoration comes back unchanged rather than blank."""
    for name in (u"[SubsPlease][1080p][x264]", u"sup 7z", u"ja.cc.sdh",
                 u"[Erai-raws]", u"webrip amazon jp"):
        out = D.strip(name, vocab, aggressive=True)
        assert out.strip(), "%r cleaned to nothing" % name


def test_a_decoration_word_between_spaces_is_left_alone_without_aggressive(vocab):
    """The context gate, in the direction that protects titles. `end`, `tv`
    and `studio` are in the vocabulary and are also ordinary words."""
    for title in (u"The End of Evangelion", u"Studio Life", u"TV Show Time"):
        assert D.strip(title, vocab) == title, title


# ==========================================================================
# stripping the thing it exists for
# ==========================================================================

def test_the_corpus_reviews_own_example_is_cleaned(vocab):
    """⭐ `CORPUS-OPPORTUNITIES.md` §3.1's worked example, verbatim: it keys as
    `シンゴジラwebripamazonjajpsdh` today, and §3.1 is the fix."""
    got = D.strip(u"シン・ゴジラ.WEBRip.Amazon.ja-jp[sdh]", vocab, aggressive=True)
    assert got == u"シン・ゴジラ", got


@pytest.mark.parametrize("name,want", [
    (u"[SubsPlease] Yomi no Tsugai - 18 (1080p)", u"Yomi no Tsugai - 18"),
    # ⚠ `[Erai-raws]` goes too, and that is correct: `erai` and `raws` are
    # both vocabulary tokens inside a bracket, which is the tag context the
    # applier exists for. The first version of this row expected the group to
    # survive -- the expectation was wrong, not the code.
    (u"[Erai-raws] Show Name - 05 [1080p][Multiple Subtitle]",
     u"Show Name - 05 [Multiple Subtitle"),
    (u"Title.2021.WEBRip.Netflix.ja[cc]", u"Title.2021"),
])
def test_decoration_is_removed_in_a_tag_context(name, want, vocab):
    assert D.strip(name, vocab, aggressive=True) == want


@pytest.mark.parametrize("name,want", [
    (u"Tokumei Sentai Go Busters zip", u"Tokumei Sentai Go Busters"),
    (u"Shin Kamen Rider JAPANESE sup 7z", u"Shin Kamen Rider JAPANESE"),
    (u"Yomi no Tsugai webrip amazon jp", u"Yomi no Tsugai"),
])
def test_decoration_is_peeled_off_the_END_at_any_length(name, want, vocab):
    """🚨 POSITION is the discriminator, and it is the only one that works.

    By the time the parser emits a title its separators are already spaces, so
    the tag context is gone and decoration sits as ordinary trailing words.
    Requiring a separator left **film pollution at 11.4%** against a < 5%
    target; stripping any bare word destroyed `Ja Ja Uma - 05`. Peeling the
    trailing run took film to **2.0%** and damaged nothing.
    """
    assert D.strip(name, vocab, aggressive=True) == want


def test_the_trailing_rule_is_NOT_applied_to_the_front(vocab):
    """⚠ Leading position is not symmetric. `Anime Gataris` opens with a
    vocabulary token that is its actual title, so the front is never peeled --
    and a title whose every token is decoration comes back whole."""
    assert u"anime" in vocab
    assert D.strip(u"Anime Gataris", vocab, aggressive=True) == u"Anime Gataris"
    assert D.strip(u"Vanguard TV TRY", vocab, aggressive=True) == u"Vanguard TV TRY"


def test_is_polluted_is_the_metric_the_step_is_graded_on(vocab):
    """film pollution 39.9% -> 1.3% (`decoration --grade`), against < 5%."""
    assert D.is_polluted(u"Yomi no Tsugai webrip amazon", vocab)
    assert not D.is_polluted(u"Yomi no Tsugai", vocab)
    assert not D.is_polluted(u"Kingsglaive - Final Fantasy XV", vocab)


def test_an_absent_vocabulary_degrades_instead_of_refusing(tmp_path):
    """⚠ Fail OPEN, and it is written down at the site. A missing data file
    costs a cleaning step; refusing would cost the user everything, for a file
    one command regenerates."""
    empty = D.load(str(tmp_path / "nope.json"))
    assert len(empty) == 0
    assert D.strip(u"[SubsPlease] Show - 01 (1080p)", empty) == \
        u"[SubsPlease] Show - 01 (1080p)"
    assert D.is_polluted(u"anything", empty) is False


def test_the_tokeniser_is_one_definition(vocab):
    """⚠ The derivation and the applier must tokenise identically. Two
    tokenisers drift, and the vocabulary silently stops matching the thing it
    was measured on."""
    assert D.tokens_of(u"[SubsPlease] Yomi no Tsugai - 18 (1080p) [DD1CA4BC]") == \
        [u"subsplease", u"yomi", u"no", u"tsugai", u"18", u"1080p", u"dd1ca4bc"]
    assert D.tokens_of(u"新世紀エヴァンゲリオン") == [u"新世紀エヴァンゲリオン"]
    assert D.tokens_of(u"") == []
    assert D.tokens_of(None) == []
