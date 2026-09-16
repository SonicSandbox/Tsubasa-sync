# -*- coding: utf-8 -*-
"""
The decoration vocabulary: learned tokens that are never part of a title.

RUNBOOK step A2c. `09-corpus-strategy.md` §Stage 2.2, derived by the method in
`CORPUS-OPPORTUNITIES.md` §3.1.

⭐ WHY THIS IS LEARNED AND NOT WRITTEN

Document frequency alone cannot separate `netflix` from `the` -- both appear in
thousands of shows. **The answer key breaks the tie**: a token is decoration
when it appears in many shows' FILENAMES and almost never in those shows'
CANONICAL TITLES.

    decoration  <=>  df >= 25 shows  AND  canonical-title rate < 5%

That rule finds the 361 release groups, the Japanese broadcasters, the
streaming services and the caption markers nobody wrote a regex for -- and it
keeps `the`, `no`, `movie`, `love`, `kamen`, `rider`, `season`, `ova`, which a
frequency-only rule would destroy. It is **own work product and ships**
(`02-data-model.md`: learned rules are bundled, re-derived by one command).

🚨 THE TRAP THIS MODULE IS SHAPED AROUND

`LEDGER.md` §Logic: **a short ambiguous token is only noise in a TAG CONTEXT.**
Stripping decoration as bare words corrupted real titles --

    Kingsglaive - Final Fantasy XV  ->  'Kingsglaive Fantasy XV'   ("final")
    Bakemono no Ko                  ->  'Bakemono no'              ("ko")
    Mad Max Fury Road               ->  'Mad Fury Road'            ("max")

A learned vocabulary does not escape that: `ja` and `tv` are decoration by the
measure above and are also real title words somewhere. ⭐ So the applier is
**context-gated exactly like `episode.SOFT_NOISE_RE`** -- a token is stripped
where it is bracketed, dot-delimited or trailing, and left alone where it is
simply a word in a name. **The vocabulary decides WHICH tokens; the context
decides WHETHER.**

⚠ And a stripped result is never allowed to be empty. A title reduced to
nothing by cleaning is worse than an uncleaned one, because it pairs with
everything (`08-probes.md` §C: an empty ASCII slug matches every video sharing
its episode number).
"""
import io
import json
import os
import re

# A token is a run of Latin/digits, or a run of CJK. CJK does not word-break,
# so a contiguous run is the unit -- which is why the derived vocabulary
# contains whole phrases like 最終話 and 日本統一シリーズ.
_CJK_CLASS = u"぀-ゟ゠-ヿ一-鿿ｦ-ﾟ"
# What counts as a tag separator. ⚠ Not a space — see `_contexts`.
_SEP = u"._\\-\\[\\]\\(\\)【】&+,;~"
_TOKEN = re.compile(u"[a-z0-9]+|[%s]+" % _CJK_CLASS, re.UNICODE)

_DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "data", "decoration.json")

# ⛔ Tokens the vocabulary may never contain, whatever the measurement says.
# Not a taste list: each is a word that carries meaning inside a real title and
# whose loss changes which show a name refers to. A future crawl could push one
# of them under the 5% rate by adding enough decorated filenames, and the
# vocabulary would then silently start eating titles.
PROTECTED = frozenset(u"""
the no movie love season ova final gekijouban special specials part chapter
kamen rider gundam precure conan sailor moon dragon ball one piece naruto
zero alpha omega plus next first second third last new old big little
war peace life death king queen god devil angel demon
""".split())


class Vocabulary(object):
    """The learned tokens, plus where they came from.

    Carries its own provenance because a bundled data file with no record of
    how it was made is a number nobody can re-derive or trust -- and this one
    is re-derivable by a single command.
    """

    __slots__ = ("tokens", "meta")

    def __init__(self, tokens=None, meta=None):
        self.tokens = frozenset(tokens or ())
        self.meta = meta or {}

    def __contains__(self, token):
        return token in self.tokens

    def __len__(self):
        return len(self.tokens)

    def __repr__(self):
        return "Vocabulary(%d tokens, derived %s)" % (
            len(self.tokens), self.meta.get("derived", "?"))


_CACHED = None


def load(path=None):
    """The bundled vocabulary. Absent is not an error -- it is empty.

    ⚠ Fail OPEN, deliberately and written down here: a missing data file makes
    the tool skip a cleaning step, which costs recall. Refusing to run would
    cost the user everything for a file that is regenerable by one command.
    """
    global _CACHED
    if path is None and _CACHED is not None:
        return _CACHED
    target = path or _DATA
    try:
        with io.open(target, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (IOError, OSError, ValueError):
        vocab = Vocabulary()
    else:
        tokens = set(data.get("tokens") or ())
        # ⛔ Enforced at LOAD, not only at derivation. A hand-edited or stale
        # data file cannot reintroduce a protected word by being on disk.
        tokens -= PROTECTED
        vocab = Vocabulary(tokens, data.get("meta") or {})
    if path is None:
        _CACHED = vocab
    return vocab


def tokens_of(text):
    """The tokens of a name, lowercased. The one definition, used by both the
    derivation and the applier -- two tokenisers would drift and the
    vocabulary would stop matching what it was measured on."""
    if not text:
        return []
    return _TOKEN.findall(text.lower())


def _contexts(token):
    """The patterns that make a token DECORATION rather than a word.

    Mirrors `episode.SOFT_NOISE_RE`: bracketed, dot-delimited, or trailing
    after a separator. A bare occurrence between spaces is left alone.
    """
    t = re.escape(token)
    # ONE rule, not three: the token is DELIMITER-BOUNDED. Both sides must be
    # a separator or a string edge.
    #
    # ⚠ A plain SPACE is deliberately not a separator here. A space-delimited
    # word is just a word — including `\s` made the safe path strip `End` from
    # `The End of Evangelion` and `Studio` from `Studio Life`, which is the
    # aggressive behaviour arriving through the door marked safe.
    #
    # ⚠ And it must be symmetric. Three hand-written patterns missed `ja-jp`
    # in `シン・ゴジラ.WEBRip.Amazon.ja-jp[sdh]` — §3.1's own worked example —
    # because `ja` was preceded by `.` and followed by `-`, and no single
    # pattern covered that pair.
    return (
        re.compile(u"(?<=[%s])%s(?=[%s])" % (_SEP, t, _SEP), re.I),
        re.compile(u"^%s(?=[%s])" % (t, _SEP), re.I),
        re.compile(u"(?<=[%s])%s$" % (_SEP, t), re.I),
    )


# ⚠ A length floor was tried here and DELETED. Gating bare-word stripping at
# 4+ characters still destroyed `Anime Gataris`, because `anime`, `studio`,
# `raws` and `final` are all long enough and all live inside real names. The
# floor made the damage rarer without making it impossible, which is the worst
# of both — a guard that holds until the day it does not. Context and position
# replaced it; see `strip` and `_strip_trailing_run`.


def strip(text, vocab=None, aggressive=False):
    """Remove decoration from a name. -> cleaned text.

    `aggressive=True` also strips a vocabulary token that stands alone between
    separators anywhere in the string. ⛔ It is for FILM STEMS, UNKNOWNS and
    FOLDER NAMES -- the places `09-corpus-strategy.md` §Stage 2.2 names,
    where episode-marker truncation cannot reach and the name is otherwise
    unusable. It is NOT for episode filenames, which the parser already
    truncates at the marker.

    ⚠ Never returns empty. If cleaning would remove everything, the ORIGINAL
    is returned -- an empty key pairs with every video sharing an episode
    number, which is the defect `08-probes.md` §C measured at 4,133 files.
    """
    if not text:
        return text
    vocab = load() if vocab is None else vocab
    if not len(vocab):
        return text

    out = text
    present = [t for t in set(tokens_of(text)) if t in vocab]
    for token in sorted(present, key=len, reverse=True):
        for pattern in _contexts(token):
            out = pattern.sub(u" ", out)
        # ⛔ THERE IS NO INTERIOR BARE-WORD RULE, and that is the design.
        #
        # It existed, gated by a length floor of 4, and it turned `Anime
        # Gataris` into `Gataris` -- `anime` is decoration by every measure
        # and is also that show's actual title. No length threshold can fix
        # that: `anime`, `studio`, `raws` and `final` are all long enough and
        # all live inside real names.
        #
        # ⭐ The interior of a title is where the WORDS are. Decoration is
        # identified by CONTEXT (separator-bounded, above) or by POSITION
        # (the trailing run, below) -- never by being in the vocabulary alone.

    # Collapse the punctuation the removals left behind. Without this the
    # §3.1 example comes back as `シン・ゴジラ. . .` — cleaned of decoration and
    # still carrying its scars, which keys no better than the original.
    if aggressive:
        out = _strip_trailing_run(out, vocab)

    # Collapse the punctuation the removals left behind. Without this the
    # §3.1 example comes back as `シン・ゴジラ. . .` — cleaned of decoration and
    # still carrying its scars, which keys no better than the original.
    out = re.sub(u"\\s*[._\\-]{2,}\\s*", u" ", out)
    out = re.sub(u"\\[\\s*\\]|\\(\\s*\\)|【\\s*】", u" ", out)
    out = re.sub(u"[\\s_]+", u" ", out).strip(u" ._-[](){}【】&+,;~")
    if not out or not _TOKEN.search(out.lower()):
        return text
    return out


def _strip_trailing_run(text, vocab):
    """Peel decoration off the END of a title, at any token length.

    🚨 POSITION IS THE DISCRIMINATOR, and it is the only one that works here.

    By the time the parser emits a title its separators are already spaces, so
    the tag context the applier relies on is gone: `Shin Kamen Rider JAPANESE
    sup 7z` and `Tokumei Sentai Go Busters zip` carry their decoration as
    ordinary trailing words. Requiring a separator left **film pollution at
    11.4%** against a < 5% target; stripping any bare word destroyed
    `Ja Ja Uma - 05`.

    ⭐ Trailing position separates them. Decoration accumulates at the end of a
    name; a decoration-shaped token in the MIDDLE — `Ja Ja Uma`, `The End of
    Evangelion`, `Vanguard TV TRY` — is almost always a real word. So the
    trailing run is peeled at any length and the interior keeps its floor.

    ⚠ Leading position is NOT symmetric and is deliberately not peeled:
    `Anime Gataris` opens with a vocabulary token that is its actual title.
    """
    parts = text.split()
    while len(parts) > 1:
        tail = _TOKEN.findall(parts[-1].lower())
        if not tail or not all(t in vocab for t in tail):
            break
        parts.pop()
    return u" ".join(parts) if parts else text


def is_polluted(text, vocab=None):
    """Does this title still carry a decoration token?

    The metric RUNBOOK A2c is graded on: film titles were **37.2%** polluted
    before this step (`CORPUS-OPPORTUNITIES.md` §3.1), against a < 5% target.
    """
    vocab = load() if vocab is None else vocab
    if not len(vocab):
        return False
    return any(t in vocab for t in tokens_of(text))
