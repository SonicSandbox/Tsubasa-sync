# -*- coding: utf-8 -*-
"""
The kana phonetic bridge: a kana title and a romaji title, ranked by sound.

RUNBOOK step A3b. `09-corpus-strategy.md` §Stage 2.3, method and numbers in
`CORPUS-OPPORTUNITIES.md` §3.2 (probe `_work/probe_opp4_kana.py`).

⭐ WHY RANKING AND NOT EQUALITY

Kana-only titles converted to romaji and tested for EQUALITY matched **22.7%**,
and the misses were loanwords: `ブラッククローバー` becomes `burakkukuroobaa`
against a catalogue that says `Black Clover`. Those are the same sounds under
two orthographies, and no kana table will ever make them equal.

⭐ **Fold BOTH sides to one phonetic skeleton and rank by similarity.**
`burakkukuroobaa` and `Black Clover` both reduce to `brakkurobar`-shaped
strings, and the right answer comes first.

| Measured on 2,172 kana-only titles against 11,119 candidates | |
| --- | --- |
| strict equality, the old metric | 22.7% |
| **rank-1 across the whole 11k pool** | **80.6%** |
| rank ≤ 5 | 95.2% |
| **rank-1 inside a five-show folder** | **99.1%** |

⚠ **What "wrong at rank 1" actually is: sequels, not phonetics.**
`Dagashi Kashi` → `Dagashi Kashi 2`, `Mob Psycho 100 II` ↔ `III`. The season
markers and episode-set structure are the discriminator, and in a real folder
the tie is between shows the user owns — which is why the folder number is
99.1% and the whole-pool number is 80.6%.

🚨 THE ACCEPT THRESHOLD IS A MEASURED EMPTY BAND, NOT A TASTE

300 fabricated kana strings scored a top-1 median of 0.56, p95 0.70 and a
**maximum of 0.83**. So:

    accept at >= 0.75 with a 0.10 margin  ->  1,169 correct, 42 wrong, 4/300 fabricated
    ⭐ accept at >= 0.85                   ->    964 correct, 106 wrong, 0/300 fabricated

`00-INDEX.md` Rule 2 — a confidently wrong answer is worse than no answer —
picks the second. **`ACCEPT` is 0.85 and `MARGIN` is 0.10.**

⛔ A shipped RULE, not shipped data: a kana table and a dozen substitutions,
no dictionary. `fugashi`+UniDic is the ceiling for KANJI (62.4% strict) and is
a different decision with a real dependency cost, unmeasured.
"""
import difflib
import re
import unicodedata

# ⭐ Ranking only. The timing referee decides, exactly as for the alias table
# (`09-corpus-strategy.md` §Stage 2): this narrows candidates, it never pairs.
ACCEPT = 0.85          # measured: 0 of 300 fabricated reach it
MARGIN = 0.10          # over the runner-up
PREFILTER = 300        # candidates kept by the bigram index before scoring

_KANA_RE = re.compile(u"[぀-ゟ゠-ヿｦ-ﾟ]")

BASE = {
    u"あ": "a", u"い": "i", u"う": "u", u"え": "e", u"お": "o",
    u"か": "ka", u"き": "ki", u"く": "ku", u"け": "ke", u"こ": "ko",
    u"さ": "sa", u"し": "shi", u"す": "su", u"せ": "se", u"そ": "so",
    u"た": "ta", u"ち": "chi", u"つ": "tsu", u"て": "te", u"と": "to",
    u"な": "na", u"に": "ni", u"ぬ": "nu", u"ね": "ne", u"の": "no",
    u"は": "ha", u"ひ": "hi", u"ふ": "fu", u"へ": "he", u"ほ": "ho",
    u"ま": "ma", u"み": "mi", u"む": "mu", u"め": "me", u"も": "mo",
    u"や": "ya", u"ゆ": "yu", u"よ": "yo",
    u"ら": "ra", u"り": "ri", u"る": "ru", u"れ": "re", u"ろ": "ro",
    u"わ": "wa", u"ゐ": "wi", u"ゑ": "we", u"を": "wo", u"ん": "n",
    u"が": "ga", u"ぎ": "gi", u"ぐ": "gu", u"げ": "ge", u"ご": "go",
    u"ざ": "za", u"じ": "ji", u"ず": "zu", u"ぜ": "ze", u"ぞ": "zo",
    u"だ": "da", u"ぢ": "ji", u"づ": "zu", u"で": "de", u"ど": "do",
    u"ば": "ba", u"び": "bi", u"ぶ": "bu", u"べ": "be", u"ぼ": "bo",
    u"ぱ": "pa", u"ぴ": "pi", u"ぷ": "pu", u"ぺ": "pe", u"ぽ": "po",
    u"ゔ": "vu", u"ゕ": "ka", u"ゖ": "ke",
}
SMALL = {u"ゃ": "ya", u"ゅ": "yu", u"ょ": "yo", u"ぁ": "a", u"ぃ": "i",
         u"ぅ": "u", u"ぇ": "e", u"ぉ": "o", u"ゎ": "wa"}
PALATAL = {"shi": "sh", "chi": "ch", "ji": "j"}


def is_kana(text):
    """Does this string contain kana at all?"""
    return bool(text) and bool(_KANA_RE.search(text))


def is_kana_only(text):
    """Kana and punctuation, no kanji. The population this bridge is for."""
    if not is_kana(text):
        return False
    return not re.search(u"[一-鿿㐀-䶿]", text)


def kata_to_hira(text):
    out = []
    for ch in text:
        code = ord(ch)
        out.append(chr(code - 0x60) if 0x30A1 <= code <= 0x30F6 else ch)
    return u"".join(out)


def to_romaji(text):
    """Kana -> Hepburn-ish romaji. Katakana is shifted to hiragana first.

    Handles the three things a naive table gets wrong: っ (gemination, doubles
    the next consonant), ー (the long mark, repeats the previous vowel), and
    the small kana ゃゅょ (palatalisation — きゃ is `kya`, not `kiya`).
    """
    text = kata_to_hira(unicodedata.normalize("NFKC", text or u""))
    syllables = []
    geminate = False
    for ch in text:
        if ch == u"っ":
            geminate = True
            continue
        if ch == u"ー":
            if syllables and syllables[-1] and syllables[-1][-1] in "aeiou":
                syllables[-1] += syllables[-1][-1]
            continue
        if ch in SMALL and syllables:
            prev, small = syllables[-1], SMALL[ch]
            if small.startswith("y") and prev.endswith("i"):
                # ⚠ Hepburn keeps the `y` after most consonants (きゃ -> kya)
                # and drops it after the palatals (しゃ -> sha, ちょ -> cho,
                # じゃ -> ja). The probe this was ported from dropped it
                # everywhere, giving `kaku` for きゃく — invisible in its own
                # numbers, because `fold` deletes `y` before a vowel on BOTH
                # sides anyway, so the ranking never noticed.
                # ⭐ Fixed here because `to_romaji` is public and its output is
                # also compared to catalogue romanisations directly, where
                # `kya` and `ka` are not the same word.
                if prev in PALATAL:
                    syllables[-1] = PALATAL[prev] + small[1:]
                else:
                    syllables[-1] = prev[:-1] + small
            elif prev == "fu":
                syllables[-1] = "f" + small
            elif prev == "vu":
                syllables[-1] = "v" + small
            elif prev == "u":
                syllables[-1] = "w" + small
            elif prev in ("te", "de") and small == "i":
                syllables[-1] = prev[0] + "i"
            elif prev in ("to", "do") and small == "u":
                syllables[-1] = prev[0] + "u"
            elif prev.endswith("i") and len(small) == 1:
                syllables[-1] = PALATAL.get(prev, prev[:-1]) + small
            else:
                syllables[-1] = prev[:-1] + small
            continue
        romaji = BASE.get(ch)
        if romaji is None:
            if ch.isspace() or re.match(u"[・･]", ch):
                syllables.append(" ")
            elif re.match(u"[A-Za-z0-9]", ch):
                syllables.append(ch.lower())
            continue
        if geminate:
            romaji = ("t" if romaji.startswith("ch") else romaji[0]) + romaji
            geminate = False
        syllables.append(romaji)
    return re.sub(r"\s+", " ", u"".join(syllables)).strip()


def fold(text):
    """The shared phonetic skeleton. ⭐ APPLIED TO BOTH SIDES.

    That is the whole idea: neither the kana-derived romaji nor the catalogue's
    romanisation is canonical, so both are reduced to the same lossy shape and
    compared there. Every substitution below collapses a distinction Japanese
    does not make or that romanisation schemes disagree about — l/r, b/v, long
    vowels, gemination, and the epenthetic vowels that turn `club` into
    `kurabu` and `cart` into `kaato`.
    """
    text = unicodedata.normalize("NFKC", text or u"").lower()
    text = unicodedata.normalize("NFD", text)
    text = u"".join(c for c in text if not unicodedata.combining(c))
    text = re.sub(r"[^a-z ]+", " ", text)
    text = text.replace("ch", "C")                      # protect before c->k
    text = re.sub(r"(.)\1", r"\1", text)                # geminates
    text = (text.replace("ph", "f").replace("th", "s")
                .replace("ck", "k").replace("sh", "s"))
    text = re.sub(r"c(?=[eiy])", "s", text)
    text = text.replace("c", "k")
    text = (text.replace("q", "k").replace("x", "ks").replace("l", "r")
                .replace("v", "b").replace("j", "z"))
    text = text.replace("C", "c")                       # ch -> c, now unique
    text = text.replace("w", "u")
    text = re.sub(r"y(?=[aeiou])", "", text)            # kya -> ka, both sides
    text = re.sub(r"ou|oo|oh(?=[^aeiou]|$)", "o", text)
    text = re.sub(r"uu", "u", text)
    text = re.sub(r"aa", "a", text)
    text = re.sub(r"ee|ei", "e", text)
    text = re.sub(r"ii", "i", text)
    # Epenthetic vowels: Japanese inserts `u` after a consonant (kurabu = club)
    # and `o` after t/d (kaato = cart). Drop them between consonants or at a
    # word end -- this is what makes the loanword cases work at all.
    text = re.sub(r"(?<=[bcdfghkmnprstz])u(?=[bcdfghkmnprstz]|\b)", "", text)
    text = re.sub(r"(?<=[td])o(?=[bcdfghkmnprstz]|\b)", "", text)
    text = re.sub(r"(.)\1", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


def skeleton(text):
    """A title -> its phonetic skeleton, whichever script it is written in."""
    return fold(to_romaji(text) if is_kana(text) else text)


def bigrams(text):
    text = text.replace(" ", "")
    if len(text) < 2:
        return {text} if text else set()
    return {text[i:i + 2] for i in range(len(text) - 1)}


def similarity(a, b):
    return difflib.SequenceMatcher(None, a, b).ratio()


class Index(object):
    """A bigram-prefiltered index over candidate titles.

    ⭐ Rule 4, asked here: scoring a query against all 11,119 candidates is
    11k `SequenceMatcher` calls. A bigram inverted index cuts that to the few
    hundred that share any two adjacent letters — and it is SAFE rather than
    merely fast, because a pair scoring above 0.85 cannot share zero bigrams.
    """

    __slots__ = ("_skel", "_index", "_size")

    def __init__(self, candidates=()):
        self._skel = {}
        self._index = {}
        self._size = {}
        for key, title in candidates:
            self.add(key, title)

    def add(self, key, title):
        skel = skeleton(title)
        grams = bigrams(skel)
        self._skel[key] = skel
        self._size[key] = max(1, len(grams))
        for bg in grams:
            self._index.setdefault(bg, set()).add(key)

    def __len__(self):
        return len(self._skel)

    def rank(self, query, restrict=None, limit=5):
        """-> [(score, key)], best first. `query` is a title in any script."""
        skel = skeleton(query)
        if restrict is not None:
            keys = [k for k in restrict if k in self._skel]
        else:
            grams = bigrams(skel)
            counts = {}
            for bg in grams:
                for key in self._index.get(bg, ()):
                    counts[key] = counts.get(key, 0) + 1
            # 🚨 JACCARD, NOT A RAW COUNT — and the difference is 9 points of
            # recall for the same cost.
            #
            # Ranking candidates by how many bigrams they share favours LONG
            # titles: a short true match like `Puzzle` shares few bigrams and
            # is pushed out by long titles that happen to share several.
            # Measured over 500 kana queries against 11,210 candidates, the
            # true entry was dropped by the prefilter:
            #
            #     raw count, 300 wide     16.0%
            #     raw count, 600 wide     12.8%
            #     ⭐ Jaccard, 300 wide      7.4%
            #     Jaccard, 600 wide        4.8%
            #
            # ⚠ Widening the raw filter is the obvious fix and it is the wrong
            # one: at 3,000 wide rank-1 got *worse*, because more candidates
            # means more chances for a spurious high scorer. Normalising fixes
            # the ordering; widening only buys more of a bad ordering.
            query_size = max(1, len(grams))
            keys = sorted(
                counts,
                key=lambda k: counts[k] / float(query_size + self._size[k]
                                                - counts[k]),
                reverse=True)[:PREFILTER]
        scored = sorted(((similarity(skel, self._skel[k]), k) for k in keys),
                        reverse=True)
        return scored[:limit] if limit else scored

    def best(self, query, restrict=None):
        """The accepted match, or None. ⭐ RANKING ONLY -- the timing referee
        decides; this narrows candidates and never pairs on its own.

        ⚠ Returns None rather than a low-confidence guess. The threshold sits
        in a measured empty band: 300 fabricated kana never exceeded 0.83.
        """
        scored = self.rank(query, restrict=restrict, limit=2)
        if not scored:
            return None
        top_score, top_key = scored[0]
        runner_up = scored[1][0] if len(scored) > 1 else 0.0
        if top_score < ACCEPT or (top_score - runner_up) < MARGIN:
            return None
        return top_key, top_score
