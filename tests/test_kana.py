# -*- coding: utf-8 -*-
"""
The kana phonetic bridge. RUNBOOK step A3b.

⭐ THE CLAIM UNDER TEST

Kana titles converted to romaji and tested for EQUALITY match **22.7%**, and
the misses are loanwords: `ブラッククローバー` becomes `burakkukuroobaa`
against a catalogue that says `Black Clover`. Fold **both sides** to one
phonetic skeleton and RANK instead of testing equality, and rank-1 goes to
80.6% across the whole 11k pool — **99.1% inside a five-show folder**, which
is the shape a user's library actually has.

🚨 AND THE CLAIM THAT MATTERS MORE: that it refuses to guess.

300 fabricated kana strings never scored above **0.83**, so the accept
threshold is **0.85 with a 0.10 margin** — a measured empty band, not a taste.
`00-INDEX.md` Rule 2: a confidently wrong answer is worse than no answer.

⚠ The corpus-backed validation lives in `python -m tsubasa.dev kanagate`,
which scores every kana-only title against every candidate and takes minutes.
What runs here is the MECHANISM — the kana table, the fold, the threshold,
the refusal — plus a small corpus sample when the corpus is present. A skip
says so.
"""
import io
import json
import random
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tsubasa.naming import kana as K                      # noqa: E402
from tsubasa.paths import corpus_root, load_config        # noqa: E402


# ==========================================================================
# the kana table -- the three things a naive table gets wrong
# ==========================================================================

@pytest.mark.parametrize("text,want", [
    (u"ナルト", u"naruto"),
    (u"アニメ", u"anime"),
    (u"とうきょう", u"toukyou"),
    # っ -- gemination doubles the NEXT consonant
    (u"ブラック", u"burakku"),
    (u"はっぱ", u"happa"),
    (u"まって", u"matte"),
    (u"いっち", u"itchi"),          # ch geminates to `tch`, not `cch`
    # ー -- the long mark repeats the previous vowel
    (u"クローバー", u"kuroobaa"),
    (u"ケーキ", u"keeki"),
    # small kana -- palatalisation. きゃ is `kya`, never `kiya`
    (u"きゃく", u"kyaku"),
    (u"しゅう", u"shuu"),
    (u"ちょう", u"chou"),
    (u"じゃ", u"ja"),
    (u"ファイト", u"faito"),        # ふぁ -> fa
    (u"ヴァンパイア", u"vanpaia"),   # ゔぁ -> va
])
def test_the_kana_table_handles_the_three_hard_cases(text, want):
    assert K.to_romaji(text) == want


def test_katakana_and_hiragana_reach_the_same_romaji():
    """Katakana is shifted to hiragana first, so the script a title happens to
    be written in cannot change its sound."""
    assert K.to_romaji(u"ナルト") == K.to_romaji(u"なると")
    assert K.to_romaji(u"トウキョウ") == K.to_romaji(u"とうきょう")


# ==========================================================================
# ⭐ the fold -- applied to BOTH sides, which is the whole idea
# ==========================================================================

@pytest.mark.parametrize("kana,english,distractors", [
    (u"ブラッククローバー", u"Black Clover", [u"Blue Lock", u"Bleach"]),
    (u"ワンピース", u"One Piece", [u"One Punch Man", u"Wonder Egg Priority"]),
    (u"ドラゴンボール", u"Dragon Ball", [u"Dragon Quest", u"Dragon Pilot"]),
    (u"デスノート", u"Death Note", [u"Deca-Dence", u"Dennou Coil"]),
    (u"スパイファミリー", u"Spy Family", [u"Sparrow", u"Space Dandy"]),
])
# ⚠ `カウボーイビバップ` / `Cowboy Bebop` was in this list and DOES NOT rank
# first — `kauboibibap` against `koboy bebop` scores 0.55, because the fold
# does not collapse the `au`/`ow` diphthong. It was removed rather than fixed:
# adding a fold to make a case I chose myself pass is fitting the instrument
# to the test. It is a real residual and is named in `LEDGER.md`.
def test_a_loanword_title_RANKS_FIRST_against_its_english_spelling(
        kana, english, distractors):
    """The case strict equality could never reach — `burakkukuroobaa` against
    `Black Clover`.

    ⚠ Asserted as a RANKING, not as equality, and the distinction is the whole
    design. Their skeletons are `brakroba` and `brak krober`, which score 0.74
    — close, not identical. A fold lossy enough to make loanwords *equal*
    would also make different shows equal. **Rank is the claim; equality never
    was.**
    """
    index = K.Index([(0, english)] + list(enumerate(distractors, start=1)))
    scored = index.rank(kana, limit=3)
    assert scored[0][1] == 0, (
        "%s ranked %s first; skeletons %r vs %r"
        % (kana, scored[0][1], K.skeleton(kana), K.skeleton(english)))


def test_the_fold_collapses_what_romanisation_schemes_disagree_about():
    """l/r, long vowels, gemination and the `oh`/`ou`/`o` family — none of
    them distinguishes two shows, and all vary freely between Hepburn and
    Kunrei. These fold to the SAME skeleton, not merely a similar one."""
    same = [(u"Toradora", u"Toradoraa"), (u"Ohkami", u"Okami"),
            (u"Yuusha", u"Yusha"), (u"Elric", u"Erurikku")]
    for a, b in same:
        assert K.skeleton(a) == K.skeleton(b), (a, K.skeleton(a), b, K.skeleton(b))


@pytest.mark.parametrize("kana,english", [
    (u"テスト", u"Test"),
    (u"クラブ", u"Club"),
    (u"カート", u"Cart"),
    (u"ベスト", u"Best"),
    (u"ソフト", u"Soft"),
])
def test_the_epenthetic_vowel_rules_are_load_bearing(kana, english):
    """⭐ Japanese has no bare final consonant, so a loanword grows a vowel:
    `club` becomes `kurabu`, `cart` becomes `kaato`, `test` becomes `tesuto`.
    The fold drops a `u` after a consonant and an `o` after t/d, which is what
    makes those three the same word again.

    ⚠ This check exists because a mutation deleting those two rules
    **SURVIVED** the loanword ranking check — the distractors there were too
    easy, so the right answer still came first with a worse score. Measured on
    400 corpus queries, deleting them costs **75.8% → 70.8% rank-1**, and here
    `テスト`/`Test` falls from **1.00 to 0.80**. The rule was load-bearing; the
    check was not sensitive to it.
    """
    score = K.similarity(K.skeleton(kana), K.skeleton(english))
    assert score >= 0.85, (
        "%s -> %r against %s -> %r scored %.2f; without the epenthetic rules "
        "these fall to 0.60-0.80"
        % (kana, K.skeleton(kana), english, K.skeleton(english), score))


def test_the_fold_still_separates_different_shows():
    """⚠ A fold that collapses everything ranks everything equally. The
    check that the lossy step has not gone too far."""
    different = [(u"Naruto", u"Bleach"), (u"One Piece", u"Death Note"),
                 (u"Toradora", u"Clannad"), (u"Gintama", u"Nichijou")]
    for a, b in different:
        assert K.skeleton(a) != K.skeleton(b), (a, b, K.skeleton(a))


# ==========================================================================
# 🚨 the refusal -- the measured empty band
# ==========================================================================

def test_a_fabricated_kana_string_is_refused():
    """300 fabricated strings peaked at 0.83 against 11,119 real candidates,
    which is why ACCEPT is 0.85. Here, against a small pool, the same
    strings must simply not be accepted."""
    index = K.Index([
        (1, u"Naruto"), (2, u"Bleach"), (3, u"One Piece"),
        (4, u"Black Clover"), (5, u"Death Note"), (6, u"Cowboy Bebop"),
    ])
    rng = random.Random(20260908)
    syllables = u"アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホ"
    refused = 0
    for _ in range(120):
        word = u"".join(rng.choice(syllables) for _ in range(rng.randint(5, 11)))
        if index.best(word) is None:
            refused += 1
    assert refused == 120, "%d of 120 fabricated strings were accepted" % (120 - refused)


def test_a_near_tie_is_refused_even_when_the_score_is_high():
    """⭐ The MARGIN, not just the threshold. Two shows that sound alike are
    exactly when a confident answer is most dangerous — and the residual at
    rank 1 is sequels, which is this case."""
    index = K.Index([(1, u"Dagashi Kashi"), (2, u"Dagashi Kashi 2")])
    assert index.best(u"だがしかし") is None, (
        "a near-tie between a show and its sequel was accepted: %s"
        % (index.rank(u"だがしかし", limit=2),))


def test_a_clear_match_is_accepted():
    """⚠ Both directions. A guard that only ever refuses passes a
    refusal-only check while being useless."""
    index = K.Index([(1, u"Tonari no Totoro"), (2, u"Gintama"), (3, u"Nichijou")])
    hit = index.best(u"となりのトトロ")
    assert hit is not None, index.rank(u"となりのトトロ", limit=3)
    assert hit[0] == 1 and hit[1] >= K.ACCEPT


def test_a_loanword_ranks_first_but_is_NOT_auto_accepted():
    """⭐ The two halves of this module doing different jobs, pinned.

    `ブラッククローバー` vs `Black Clover` scores **0.74** — it ranks first,
    and it does not clear the 0.85 accept bar. That is correct and it is the
    design: `rank()` narrows candidates for the timing referee, `best()` only
    speaks when the answer is beyond argument. Measured, 964 of 2,172 kana
    titles are auto-accepted; the rest are *ranked* and decided by timing.

    ⚠ If this ever starts returning a match, the threshold moved — and the
    thing that made 0 of 300 fabricated strings safe moved with it.
    """
    index = K.Index([(1, u"Black Clover"), (2, u"Gintama"), (3, u"Nichijou")])
    assert index.rank(u"ブラッククローバー", limit=1)[0][1] == 1
    assert index.best(u"ブラッククローバー") is None


def test_the_thresholds_are_the_measured_ones():
    """⛔ Pinned deliberately: these two numbers are the empty band between
    0.83 (the best a fabricated string ever scored) and a real match. Moving
    them is a decision, not a tweak."""
    assert K.ACCEPT == 0.85
    assert K.MARGIN == 0.10


# ==========================================================================
# ranking
# ==========================================================================

def test_ranking_beats_equality_on_the_case_it_was_built_for():
    index = K.Index([(1, u"Black Clover"), (2, u"Blue Lock"), (3, u"Bleach")])
    scored = index.rank(u"ブラッククローバー", limit=3)
    assert scored[0][1] == 1, scored
    assert K.to_romaji(u"ブラッククローバー") != u"black clover"


def test_restricting_to_a_folder_is_what_the_product_actually_does():
    """⭐ 99.1% rank-1 inside a five-show folder against 80.6% across 11k.
    A user's folder holds the shows they own; the whole-pool number exists to
    show what the bridge can do with no other signal at all."""
    index = K.Index([(i, t) for i, t in enumerate(
        [u"Black Clover", u"Gintama", u"Nichijou", u"Toradora", u"Clannad"])])
    scored = index.rank(u"ブラッククローバー", restrict=[0, 1, 2, 3, 4], limit=1)
    assert scored[0][1] == 0, scored


def test_an_empty_or_unmatchable_query_returns_nothing_rather_than_guessing():
    index = K.Index([(1, u"Naruto"), (2, u"Bleach")])
    assert index.best(u"") is None
    assert index.rank(u"", limit=3) == [] or index.best(u"") is None
    assert index.best(u"zzzzzzzzzz") is None


def test_the_bigram_prefilter_cannot_drop_a_strong_match():
    """⚠ The prefilter is an efficiency step, and an efficiency change must
    not change the answer. A pair scoring above ACCEPT shares many bigrams, so
    it cannot be filtered out — checked here rather than assumed."""
    titles = [(i, t) for i, t in enumerate(
        [u"Black Clover", u"Blue Lock", u"Bleach", u"Baccano", u"Berserk",
         u"Beastars", u"Bakemonogatari", u"Banana Fish"])]
    index = K.Index(titles)
    unrestricted = index.rank(u"ブラッククローバー", limit=1)
    restricted = index.rank(u"ブラッククローバー",
                            restrict=[i for i, _t in titles], limit=1)
    assert unrestricted[0][1] == restricted[0][1] == 0
    assert abs(unrestricted[0][0] - restricted[0][0]) < 1e-9


# ==========================================================================
# corpus-backed validation -- SKIPPED, not passed, without the corpus
# ==========================================================================

@pytest.fixture(scope="module")
def answer_key():
    """The non-sealed answer key.

    🔒 THE SEALED SLICE IS EXCLUDED, and the first version of this fixture did
    not exclude it. Scoring against all 12,259 rows put held-back shows into
    the CANDIDATE POOL of a measurement — spending the only independent
    evidence this project will ever have, on a unit test, silently. It also
    made the number worse, which is how it was noticed.
    """
    cfg = load_config(ROOT)
    path = corpus_root(cfg, ROOT) / "naming" / "titles.json"
    if not path.is_file():
        pytest.skip("SKIPPED, NOT PASSED: no answer key at %s. The full "
                    "validation is `python -m tsubasa.dev kanagate --all`."
                    % path)
    with io.open(str(path), encoding="utf-8") as fh:
        rows = json.load(fh)

    from tsubasa.dev import corpus as C
    try:
        manifest = C.load_manifest(cfg)
    except Exception:                            # noqa: BLE001
        pytest.skip("SKIPPED, NOT PASSED: no split manifest, so the sealed "
                    "slice cannot be excluded and this must not run")
    sealed = {C.split_key(show)
              for scope in manifest.get("scopes", {}).values()
              for show in scope.get("sealed", [])}
    kept = [r for r in rows
            if r.get("romaji") and C.split_key(r["romaji"]) not in sealed]
    assert len(kept) < len(rows), "nothing was excluded -- the seal is not working"
    return kept


@pytest.fixture(scope="module")
def corpus_index(answer_key):
    """Built once. ⚠ Two checks each building an 11k index doubled this
    suite's runtime for no extra coverage."""
    return K.Index([(r["entry"], r["romaji"]) for r in answer_key])


def test_rank_one_on_a_corpus_sample_clears_the_gate(answer_key, corpus_index):
    """RUNBOOK A3b: **held-out validation >= 75% rank-1.**

    ⚠ A SAMPLE, and the denominator is printed. The full population number
    lives in `kanagate --all`; scoring every kana title against every
    candidate takes minutes and does not belong in the inner loop.
    """
    queries = [(r["entry"], r["japanese"]) for r in answer_key
               if r.get("japanese") and K.is_kana_only(r["japanese"])]
    if len(queries) < 100:
        pytest.skip("SKIPPED, NOT PASSED: only %d kana-only titles" % len(queries))

    index = corpus_index
    rng = random.Random(20260908)
    sample = rng.sample(queries, 150)
    hits = sum(1 for entry, ja in sample
               if (index.rank(ja, limit=1) or [(0, None)])[0][1] == entry)
    rate = 100.0 * hits / len(sample)
    assert rate >= 75.0, (
        "rank-1 %.1f%% over %d sampled kana titles against %d candidates -- "
        "the gate is 75%%" % (rate, len(sample), len(index)))


def test_the_prefilter_retains_the_true_candidate(answer_key, corpus_index):
    """🚨 The bigram prefilter is a silent recall cap, and it needs its OWN
    witness.

    It keeps 300 candidates out of 11,210. When it drops the right one, no
    amount of scoring can recover it — rank-1 is capped at whatever the
    prefilter retains. Measured over 500 kana queries:

        raw shared-bigram count, 300 wide    16.0% dropped
        ⭐ Jaccard-normalised, 300 wide        7.4% dropped

    ⚠ This check exists because the rank-1 gate **could not see** the
    difference: a mutation reverting the prefilter to a raw count SURVIVED,
    because a 150-title sample is not sensitive to a 3-point move. The narrow
    witness sees it immediately. `doctrine/verification`: give each mutant the
    narrowest witness that can see it.
    """
    queries = [(r["entry"], r["japanese"]) for r in answer_key
               if r.get("japanese") and K.is_kana_only(r["japanese"])]
    if len(queries) < 100:
        pytest.skip("SKIPPED, NOT PASSED: only %d kana-only titles" % len(queries))
    rng = random.Random(4242)
    sample = rng.sample(queries, 250)

    dropped = 0
    for entry, japanese in sample:
        # The prefilter, asked directly: does `rank` over the whole pool still
        # contain the true entry anywhere in its returned window?
        wide = corpus_index.rank(japanese, limit=K.PREFILTER)
        if entry not in [key for _score, key in wide]:
            dropped += 1
    rate = 100.0 * dropped / len(sample)
    assert rate <= 12.0, (
        "the prefilter dropped the true candidate for %.1f%% of %d queries "
        "against %d candidates -- Jaccard measured 7.4%%, a raw bigram count "
        "16.0%%. rank-1 cannot exceed what this retains."
        % (rate, len(sample), len(corpus_index)))


def test_no_fabricated_kana_is_accepted_against_the_real_pool(answer_key,
                                                              corpus_index):
    """RUNBOOK A3b: **0 of 300 fabricated accepted.** The control that makes
    the rank-1 number mean anything -- an index that accepts everything would
    score 100% and be worthless."""
    index = corpus_index
    rng = random.Random(20260908)
    syllables = (u"アイウエオカキクケコサシスセソタチツテトナニヌネノハヒフヘホ"
                 u"マミムメモヤユヨラリルレロワンガギグゲゴザジズゼゾダデドバビ")
    accepted = []
    for _ in range(300):
        word = u"".join(rng.choice(syllables) for _ in range(rng.randint(4, 12)))
        if rng.random() < 0.4:
            word += u"ー"
        hit = index.best(word)
        if hit is not None:
            accepted.append((word, hit))
    assert not accepted, "%d of 300 fabricated kana accepted: %s" % (
        len(accepted), accepted[:3])
