# -*- coding: utf-8 -*-
"""
Series identity: are these two names the same show? RUNBOOK step A3.

🚨 THIS IS THE HARD ONE, and character overlap alone provably cannot do it.

Four cases from spec/06-edge-cases.md §2.4, and any measure that gets all four
right is doing something a substring ratio cannot:

    Ace of Diamond      / Diamond no Ace          SAME  (no shared prefix)
    Tongari Boushi no Memole / ...no Atelier      DIFFERENT (15 chars shared)
    Naruto              / Naruto 疾風伝            DIFFERENT (one contains the other)
    Aria the Animation  / Aria the Natural        DIFFERENT (shared prefix)

Measured with a longest-common-substring ratio, the true POSITIVE (Ace /
Diamond, ~0.57) scores BELOW a true NEGATIVE (Tongari, ~0.71). There is no
threshold on that measure that separates them, so a better measure is required
rather than a better number.

⭐ What works is asking about the LEFTOVER, not the overlap. `Diamond no Ace`
is `Ace of Diamond` REORDERED -- nothing is left over. `...no Atelier` shares a
prefix and then says something completely different.

    Latin titles -> token-set similarity (word bags, order-free)
    CJK titles   -> character-bigram similarity (no spaces to tokenise on)

⚠ AND IT STILL DOES NOT ALWAYS SEPARATE. So this returns a BAND, not a
boolean -- SAME / UNSURE / DIFFERENT -- exactly like the verdict. UNSURE is
handed to timing arbitration, which is the stage that already exists to settle
a candidate set. A design that forces a boolean here manufactures confident
wrong answers, which is the one thing this project must not do.

🚨 The thresholds below are MEASURED, not chosen. See
`python -m tsubasa.dev seriesgate`, which derives them from the dev corpus
where directory membership is ground truth.
"""
import re
from functools import lru_cache

from .normalize import Normalized, normalize

# Words that carry no identity. Dropping them is what lets `Ace of Diamond`
# and `Diamond no Ace` become the same token set.
STOPWORDS = {
    "the", "a", "an", "of", "no", "wa", "ga", "ni", "de", "to", "wo", "he",
    "and", "&", "season", "series", "part", "cour", "tv", "special",
}

_TOKEN = re.compile(u"[0-9a-z]+|[぀-ヿ一-鿿]+")

# ⭐ MEASURED against the dev corpus (3,541 shows, 2,000 pairs per class, half
# the negatives deliberately hard). `python -m tsubasa.dev seriesgate`.
#
#   same-show, same-script:  p5 0.111 · p10 0.200 · median 1.000
#   diff-show, same-script:  median 0.000 · p90 0.333 · p95 0.600 · p99 1.000
#
# ⚠ THERE IS NO EMPTY BAND. same-p5 (0.111) sits below diff-p95 (0.600), so no
# single threshold separates the classes -- exactly the shape the verdict
# problem has (spec/05-interface.md). The UNSURE rung is STRUCTURAL, not a
# refinement, and any design that forces a boolean here manufactures confident
# wrong pairings.
#
# At these values, measured:
#   same-show  ->  SAME 66.5%  UNSURE 13.1%  DIFFERENT 20.4%
#   diff-show  ->  SAME  4.2%  UNSURE  4.5%  DIFFERENT 91.2%
#
# 🚨 CORRECTED 2026-09-08 after review. An earlier version of this block read
# "same-show SAME 57.3% / diff-show SAME 0.5%". BOTH were wrong, for two
# separate instrument faults found by an independent reviewer:
#
#   1. The gate filtered its SCORE lists to same-script pairs but not its PAIR
#      lists, then indexed one with the other's index. Every verdict row and
#      every diagnostic it printed named the wrong pair.
#   2. Its "deliberately hard" negatives bucketed on the corpus scrape ordinal
#      (`NNNNN Title`), so 95.4% of shows landed in an all-digit bucket and the
#      hard pool was pairs sharing nothing but a number.
#
# ⛔ The false-match rate is therefore **4.2%, not 0.5% -- eight times worse
# than first recorded.** That is the number that matters: a missed pair is an
# inconvenience, a WRONG pair silently retimes a subtitle to the wrong episode.
#
# ⚠ And 4.2% is an UPPER BOUND that includes label noise: 123 title keys in the
# corpus are produced by more than one directory with different split keys
# (`Boku no Hero Academia` across three, `Dr. STONE` vs `Dr. STONE: NEW WORLD`),
# so some "different-show" pairs are genuinely the same franchise. Real, but
# not all of it is the matcher's fault -- and it is a production hazard either
# way, because the matcher sees the same collision.
SAME_AT = 0.80
DIFFERENT_BELOW = 0.40
THRESHOLDS_ARE_MEASURED = True

SAME = "same"
UNSURE = "unsure"
DIFFERENT = "different"


_SEPARATORS = re.compile(u"[\\s._\\-\\[\\]()（）【】「」『』、,:;/~〜]+")


def tokens(text):
    """Identity-bearing tokens. Memoised on the ORIGINAL string.

    ⚠ Split the ORIGINAL, then fold each piece -- normalisation removes the
    separators, so tokenising the folded key would give one giant token and
    the whole token-set idea would silently degrade to character matching.

    ⛔ Keyed on the string, never on a Normalized: two different titles can be
    equal-and-same-hash as Normalized objects while having different tokens.
    """
    original = text.original if isinstance(text, Normalized) else text
    return _tokens_cached(original or u"")


@lru_cache(maxsize=200000)
def _tokens_cached(original):
    out = []
    for part in _SEPARATORS.split(original):
        k = normalize(part).key
        if k and k not in STOPWORDS:
            out.append(k)
    return tuple(out)


@lru_cache(maxsize=200000)
def _bigrams_cached(key):
    return _bigrams(key)


def _bigrams(s):
    return {s[i:i + 2] for i in range(len(s) - 1)} if len(s) > 1 else ({s} if s else set())


def _jaccard(a, b):
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / float(union) if union else 0.0


def similarity(a, b):
    """0.0 - 1.0. Symmetric. Penalises leftover, not just shared characters."""
    na = a if isinstance(a, Normalized) else normalize(a)
    nb = b if isinstance(b, Normalized) else normalize(b)

    if not na.key or not nb.key:
        return 0.0
    if na.key == nb.key:
        return 1.0

    ta, tb = set(tokens(na.original)), set(tokens(nb.original))
    # Token sets are only meaningful when both sides actually tokenise into
    # more than one piece -- a single CJK run is one token and tells us nothing.
    token_score = _jaccard(ta, tb) if (len(ta) > 1 and len(tb) > 1) else None

    bigram_score = _jaccard(_bigrams_cached(na.key), _bigrams_cached(nb.key))

    if token_score is None:
        return bigram_score
    # ⚠ The MINIMUM, not the average. Two titles must look alike on BOTH
    # measures; averaging lets a high character overlap carry a title whose
    # words are entirely different, which is the Tongari case exactly.
    return min(token_score, bigram_score) if token_score < 1.0 else \
        max(token_score, bigram_score)


def same_series(a, b, same_at=None, different_below=None, use_alias=True):
    """(verdict, score, reason). Three outcomes, never a bare boolean.

    ⛔ A different PUNCTUATION SIGNATURE means different shows outright, at any
    score. `Gintama` and `Gintama'` normalise to the same key by design -- the
    signature is the only thing that separates four real seasons.

    ⭐ `use_alias=False` turns RUNBOOK A7 off. It exists for ONE reason: a gate
    that measures the CHARACTER mechanism must not silently include the table
    (`seriesgate`, which derives the two thresholds above). `LEDGER.md`
    §Harness: a check can pass through a filter that is not the one it is
    named for.
    """
    same_at = SAME_AT if same_at is None else same_at
    different_below = DIFFERENT_BELOW if different_below is None else different_below

    na = a if isinstance(a, Normalized) else normalize(a)
    nb = b if isinstance(b, Normalized) else normalize(b)

    score = similarity(na, nb)

    if na.signature != nb.signature and na.key == nb.key:
        return (DIFFERENT, score,
                u"same title, different punctuation (%r vs %r) -- these are "
                u"distinct seasons" % (na.signature, nb.signature))

    cross = cross_script(na, nb)

    # ⭐ CHARACTERS FIRST. If the score already settles the pair, the table is
    # never consulted -- it has nothing to add and it would take the credit.
    #
    # 🚨 THIS SHORT-CIRCUIT IS A FIX, NOT AN OPTIMISATION. The first wiring put
    # the bridge above every threshold, and probe A7/2 measured the result:
    # **155 of 259 "alias rescues" on the benchmark scored >= 0.80** -- pairs
    # like `3 gatsu no Lion` against `3 gatsu no Lion` at 1.00, which the
    # character score settles on its own. The benchmark TOTAL was unaffected
    # (those pairs are SAME either way), but the attribution was wrong, and a
    # feature credited with work it did not do is a number nobody can act on.
    # `LEDGER.md`: a check can pass through a filter that is not the one it is
    # named for -- and so can a measurement.
    if not cross and score >= same_at:
        return (SAME, score, u"")

    # ⭐ RUNBOOK A7 -- the alias table. Consulted only where characters could
    # not answer, which is exactly the population it was built for.
    #
    # PURELY ADDITIVE, and that is the property to keep: `bridge` returns SAME
    # or UNSURE and NEVER DIFFERENT, so the only verdicts that change are ones
    # that become SAME. Every other path below is byte-identical to the build
    # before A7 existed, which is what makes the whole feature safe to ship on
    # a table nobody has audited row by row.
    #
    # ⚠ It sits ABOVE `cross_script` because that is the branch it exists to
    # rescue -- the comment there names A7 as the answer -- and above the
    # thresholds because 9.9% of real pairs are DIFFERENT-by-title and correct,
    # and every one of those is English against romaji
    # (`09-corpus-strategy.md` §Stage 2). Both sides Latin, no script gap, no
    # score: `Solo Leveling` vs `Ore dake Level Up na Ken`.
    #
    # ⚠ The returned score is the BRIDGE's 1.0, not the character score, which
    # is 0.00 on exactly these pairs. A caller reading `(SAME, 0.00)` would
    # reasonably distrust it. The REASON string is what says which mechanism
    # answered, and it names the entity so the claim can be checked.
    # ⛔ Ordered AFTER the signature guard, never before: `Gintama` and
    # `Gintama'` share every alias in the table and the signature is the only
    # thing that has ever separated those four seasons.
    #
    # 🚨 AND IT MAY NOT SPEAK ABOUT A CONTAINMENT PAIR. Measured, probe A7/3:
    # `Dr Stone` against `Dr Stone Ryuusui` -- a series and its own TV special
    # -- bridged to SAME, because `Dr. Stone: Ryuusui` carries `Dr. Stone`
    # among its Wikidata names. Then `Naruto` against `Naruto Shippuuden` did
    # the same. Both are the shape `LEDGER.md` §Logic already records, and
    # `one_contains_the_other` is the exact test for it.
    #
    # ⚠ A SCORE GATE WAS TRIED HERE FIRST AND REMOVED, WITH THE MEASUREMENT.
    # The first fix was `(cross or score < different_below)` -- let the table
    # speak only where characters are silent. It closed `Dr Stone` (0.60, in
    # the band) and **`Naruto` / `Naruto Shippuuden` walked straight through
    # it at 0.36, BELOW the band**. Two guards, two escapes, one shape.
    #
    # Once containment landed, a mutation deleting the score gate SURVIVED the
    # suite -- so it was measured rather than kept on faith (probe A7/2 §4):
    #
    #     score gate KEPT     73 bridges on the 350 real pairs · 26/20,000 wrong
    #     score gate REMOVED  75 bridges                        · 26/20,000 wrong
    #
    # ⛔ It bought **nothing** and cost **two correct bridges** -- the
    # spelling-variant class, `Komi san wa, Comyushou desu` against
    # `…Komyushou Desu`, one letter apart at 0.60. `LEDGER.md`: a mutant that
    # cannot fail is noise, and noise is what gets a check switched off. Do not
    # re-add it; add a case that can feel it, or leave containment to do the
    # job it is measurably doing.
    if use_alias and not one_contains_the_other(na, nb):
        from . import alias as _alias
        bridged, _bscore, breason = _alias.bridge(na.original, nb.original)
        if bridged == _alias.SAME:
            return (SAME, 1.0, breason)

    if cross:
        # A Japanese title and its romaji CANNOT match on characters -- kana is
        # not Latin. That is the alias table's job (A7), not a threshold's.
        return (UNSURE, score,
                u"different scripts (%s vs %s) -- needs the alias table or "
                u"timing" % (na.script, nb.script))

    if score >= same_at:
        return (SAME, score, u"")
    if score < different_below:
        return (DIFFERENT, score, u"too little in common")
    return (UNSURE, score,
            u"score %.2f falls between %.2f and %.2f -- hand to timing "
            u"arbitration" % (score, different_below, same_at))


def one_contains_the_other(na, nb):
    """Is one title's key a strict substring of the other's?

    🚨 THE SEQUEL SHAPE, AND IT IS THE ONE THE ALIAS TABLE GETS WRONG.

    Wikidata lists a special, a season and a sequel among a franchise's names,
    so `Dr. Stone: Ryuusui` carries `Dr. Stone` and `Naruto: Shippūden` carries
    `Naruto`. Both titles then reach a common entity and the intersection rule
    fires — correctly, on a pair that is not one show. Measured this session:
    `Dr Stone` / `Dr Stone Ryuusui` and `Naruto` / `Naruto Shippuuden` both came
    back SAME.

    ⭐ `06-edge-cases.md` §2.4 already names this as a case no overlap measure
    can settle -- *"Naruto / Naruto 疾風伝 DIFFERENT (one contains the other)"* --
    and this module's own docstring says the answer is to ask about the
    **leftover**, not the overlap. Containment is exactly "there is leftover on
    one side and none on the other".

    ⛔ EXACT, not a threshold. Two titles where one is the other plus more words
    are a series and its season, its film or its special, whatever any table
    says about them. There is nothing here to tune, which is the point: every
    threshold in this pack sits in a measured empty band, and this one does not
    need to exist at all.

    🚨 AND IT WAS SCRIPT-BLIND, WHICH MADE IT USELESS ON THE POPULATION A7
    EXISTS FOR. Found by the adversarial pass: comparing folded KEYS works only
    when both titles are in the same script, because a Japanese title shares no
    characters with its own romaji. Measured on the same 32 shows from the
    answer key, the guard fired **32 of 32** times with both sides Latin and
    **0 of 32** with the left side Japanese:

        ナルト  /  Naruto Shippuuden      ->  was SAME
        デュエル・マスターズ  /  Duel Masters VS  ->  was SAME

    ⭐ So the second arm asks the same question in the PHONETIC space, using
    `kana.skeleton` -- the bridge A3b already ships and measured. `ナルト` folds
    to the same skeleton as `naruto`, which *is* a prefix of `narutosippuden`.

    ⚠ A kanji run has no skeleton without a dictionary and folds to empty, so a
    kanji-vs-romaji sequel is still not reachable here. It is named as
    uncovered rather than papered over, and the residual is measured by
    `alias --grade`'s hard negative control.

    ⚠ Equal keys and equal skeletons are NOT containment. They are handled
    above -- by the signature guard, or by the score.
    """
    ka, kb = na.key, nb.key
    if not ka or not kb:
        return False
    if ka != kb and (ka in kb or kb in ka):
        return True

    # ⛔ CROSS-SCRIPT CONTAINMENT IS NOT GUARDED HERE, AND THAT IS A MEASURED
    # DECISION RATHER THAN AN OVERSIGHT. Two mechanisms were built and both
    # were removed; probe A7/5 has the numbers.
    #
    # **A phonetic arm** (`kana.skeleton`) changed **0 of 9** known cases, and
    # its unrestricted form REFUSED A CORRECT BRIDGE: `to_romaji` has no
    # dictionary and silently drops kanji, so `宇宙戦艦ヤマト` reduces to
    # `yamato`, which is inside `Space Battleship Yamato`. **A lossy transform
    # makes a fragment, and a fragment is inside everything** -- the same class
    # as the deriver's run-split bug, through a different door. The fold is
    # lossy the other way too: `ドラゴンボール` skeletons to `dragonbor` and
    # `Dragon Ball Z` to `dragonbarz`, so the containment is not even there.
    #
    # **An entity-subset rule** was worse: it fired on **4 of 5 pairs that must
    # be kept** (`進撃の巨人`, `宇宙戦艦ヤマト`, `鬼滅の刃`, `Assassination
    # Classroom`) and missed the one that must be refused. A franchise entity
    # legitimately contains its own romanisation's entities.
    #
    # ⭐ What removed the NEED for it was fixing the deriver: the cross-script
    # sequel bridges were fragment keys (`NARUTO -ナルト- 疾風伝` split into
    # `ナルト`), not real aliases, and they are gone.
    #
    # ⚠ THE RESIDUAL, NAMED: cases where Wikidata genuinely lists the base
    # title among a sequel entity's names -- `ドラゴンボール` / `Dragon Ball Z`.
    # Measured at **13 of 6,692 (0.19%)** by `alias --grade`'s hard negative
    # control, which is now a standing gate rather than a probe. ⭐ And the cost
    # is a wrong REPORT, not a wrong file: SAME makes the pair a candidate, and
    # `align()` refuses a wrong-show pair at 1.3-1.9x chance. Rule 1 holds.
    return False


def cross_script(na, nb):
    """Is one side CJK-bearing and the other not?

    🚨 MIXED counts as CJK-bearing, and getting that wrong cost the measurement
    its answer. `Captain Tsubasa Junior Youth Hen` vs
    `キャプテン翼シーズン2 ジュニアユース編 S01E17` -- the second is MIXED, because a
    platform tag put Latin letters in a Japanese title. Comparing the script
    LABELS ("latin" != "mixed", but neither is "cjk") let that pair fall
    through to a character score of 0.000 and be called DIFFERENT, when it is
    the same show and the honest answer is "I need the alias table".

    Ask what a title CONTAINS, never what its label happens to be.
    """
    a_cjk = na.script in ("cjk", "mixed")
    b_cjk = nb.script in ("cjk", "mixed")
    return a_cjk != b_cjk
