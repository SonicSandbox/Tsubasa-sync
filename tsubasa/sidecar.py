# -*- coding: utf-8 -*-
u"""
Subtitle filenames: reading the language out of one, and writing the next one.
RUNBOOK step 3a. Authority: `05-interface.md` §Naming and dedupe,
`06-edge-cases.md` §3, and hato's `02-data-model.md` §*What "already exists"
means*.

===========================================================================
🚨 BOTH REFERENCE IMPLEMENTATIONS HAVE LIVE BUGS HERE, IN OPPOSITE DIRECTIONS
===========================================================================

hato's `08-research.md` measured them:

| | subliminal 2.7.1 | Bazarr `subliminal_patch` |
| --- | --- | --- |
| `.ja.forced.srt` | 🚨 reads as **`und`** -- it expects `.ja.fo.` | works |
| flag matching | whole token | 🚨 **substring** |
| consequence | a correctly-named forced sub reads as *"no subtitle"* and is re-downloaded **forever** | `Show.chi.srt` -> Chinese **+ hearing-impaired**; `Show.hin.srt` -> Hindi **+ hearing-impaired** |

⭐ **Two one-line rules fix both, and each project got one of them wrong in the
opposite direction:**

    1. Parse the language BEFORE trimming flag tokens.
    2. Strip flags as whole dot-delimited tokens, never substrings.

⚠ **This reader lives HERE and hato imports it** (hato's spec says so, and
tsubasa needs it for dedupe). Write it once, correctly, in one place.

---------------------------------------------------------------------------
⭐ THE ALGORITHM, AND WHY IT IS NOT "SPLIT AND TAKE THE SECOND-TO-LAST"
---------------------------------------------------------------------------

A stem contains arbitrary dots -- `Kimi no Na wa. (2016)`,
`Show.S01E01.1080p.WEB-DL` -- so no fixed position holds the language.

    Take the LEFTMOST dot token, inside a bounded window before the
    extension, that is a language code AND has nothing but known FLAG
    tokens to its right.

Both rules fall out of that one sentence rather than being bolted on:

    Show.chi.srt        `chi` is a code, nothing to its right   -> chi, []
    Show.hin.srt        likewise                                -> hin, []
    Show.ja.forced.srt  `ja` is a code, `forced` is a flag      -> ja, [forced]
    Show.en.sdh.srt     `en` is a code, `sdh` is a flag         -> en, [sdh]
    Show.srt            no code in the window                   -> und, []

🚨 AND IT IS WHAT KEEPS AN ENGLISH WORD FROM BECOMING A LANGUAGE. `is` is
Icelandic, so `My.Name.Is.Khan.hi.srt` offers `Is` as a candidate -- and it is
rejected because `Khan` to its right is not a flag. The right-hand constraint
is not a tidiness rule; it is the whole guard.
"""
import os
import re
import unicodedata

# ---------------------------------------------------------------------------
# the language codes -- ONE owner for the whole project
# ---------------------------------------------------------------------------
# ⭐ `movies.py` grew a private `_LANG2` and `naming/episode.py` a private
# `_SOFT`, and `HANDOFF.md` already carried the consequence as an open item:
# `_SOFT` has no European codes, so `.es`, `.fr.forced` and `.pt-BR` measured
# **0%** coverage against 100% for `.en`/`.ja`. `doctrine/architecture` rule 4
# -- a derived value needs one writer -- applies to a vocabulary too, and this
# is that one place. `movies.py` imports `ISO_639_1` from here.

#: ISO 639-1 two-letter codes -- **148 of them**, not the full 184.
#:
#: ⚠ THE COUNT WAS WRONG IN THIS DOCSTRING and an adversarial pass caught it:
#: it claimed 184 while the tuple has 148. The 36 absent codes are the ones
#: `movies.py`'s Western-film measurement never contained (`ae an av bh bi ch
#: cr cu ho hz ia ie ii ik io iu kg ki kj kr ks kv li mh na ng nr nv oj os pi
#: sm tw ty vo wa za`). ⭐ Leaving them out is not neutral and not an accident
#: to fix casually: `ch`, `na`, `pi`, `wa`, `an` and `os` are all ordinary
#: filename tokens, so adding them would create new false positives on the
#: trailing-token shape recorded in `LEDGER.md` §Logic. **Widen this only with
#: a measurement.**
#:
#: ⚠ Byte-identical to the list `movies.py` measured its peel against; moved
#: here rather than rewritten, so that measurement still describes it.
#: ⚠ A TUPLE, not a list: it is aliased into `movies.py` and baked into a
#: compiled regex there, so a mutation would desync the two silently.
ISO_639_1 = tuple(
    "aa ab af ak am ar as ay az ba be bg bm bn bo br bs ca ce co cs cv cy da "
    "de dv dz ee el en eo es et eu fa ff fi fj fo fr fy ga gd gl gn gu gv ha "
    "he hi hr ht hu hy id ig is it iw ja jv ka kk kl km kn ko ku kw ky la lb "
    "lg ln lo lt lu lv mg mi mk ml mn mr ms mt my nb nd ne nl nn no ny oc om "
    "or pa pl ps pt qu rm rn ro ru rw sa sc sd se sg si sk sl sn so sq sr ss "
    "st su sv sw ta te tg th ti tk tl tn to tr ts tt ug uk ur uz ve vi wo xh "
    "yi yo zh zu".split())

#: ISO 639-1 -> ISO 639-2/T, written as pairs so ONE table holds the knowledge
#: and the three-letter set is derived rather than transcribed twice.
#:
#: ⚠ Deliberately bounded to languages that HAVE a two-letter code. A
#: three-letter-only code then reads as `und`, which costs a duplicate file and
#: never a wrong one -- and it is what makes `sdh` unambiguous below.
_ISO_1_TO_2 = (
    "aa aar|ab abk|af afr|ak aka|am amh|ar ara|as asm|ay aym|az aze|ba bak|"
    "be bel|bg bul|bm bam|bn ben|bo bod|br bre|bs bos|ca cat|ce che|co cos|"
    "cs ces|cv chv|cy cym|da dan|de deu|dv div|dz dzo|ee ewe|el ell|en eng|"
    "eo epo|es spa|et est|eu eus|fa fas|ff ful|fi fin|fj fij|fo fao|fr fra|"
    "fy fry|ga gle|gd gla|gl glg|gn grn|gu guj|gv glv|ha hau|he heb|hi hin|"
    "hr hrv|ht hat|hu hun|hy hye|id ind|ig ibo|is isl|it ita|iw heb|ja jpn|"
    "jv jav|ka kat|kk kaz|kl kal|km khm|kn kan|ko kor|ku kur|kw cor|ky kir|"
    "la lat|lb ltz|lg lug|ln lin|lo lao|lt lit|lu lub|lv lav|mg mlg|mi mri|"
    "mk mkd|ml mal|mn mon|mr mar|ms msa|mt mlt|my mya|nb nob|nd nde|ne nep|"
    "nl nld|nn nno|no nor|ny nya|oc oci|om orm|or ori|pa pan|pl pol|ps pus|"
    "pt por|qu que|rm roh|rn run|ro ron|ru rus|rw kin|sa san|sc srd|sd snd|"
    "se sme|sg sag|si sin|sk slk|sl slv|sn sna|so som|sq sqi|sr srp|ss ssw|"
    "st sot|su sun|sv swe|sw swa|ta tam|te tel|tg tgk|th tha|ti tir|tk tuk|"
    "tl tgl|tn tsn|to ton|tr tur|ts tso|tt tat|ug uig|uk ukr|ur urd|uz uzb|"
    "ve ven|vi vie|wo wol|xh xho|yi yid|yo yor|zh zho|zu zul")

#: 🚨 ISO 639-2/B, the *bibliographic* variants, which are what actually appear
#: in filenames -- `.fre.`, `.ger.`, `.chi.`. Japanese has **no B/T split**,
#: which is why `05-interface.md` can call `ja`/`jpn` safe on all three players
#: and dodge the `fre`/`fra` class of problem entirely.
_BIBLIOGRAPHIC = {
    "alb": "sq", "arm": "hy", "baq": "eu", "bur": "my", "chi": "zh",
    "cze": "cs", "dut": "nl", "fre": "fr", "geo": "ka", "ger": "de",
    "gre": "el", "ice": "is", "mac": "mk", "mao": "mi", "may": "ms",
    "per": "fa", "rum": "ro", "slo": "sk", "tib": "bo", "wel": "cy",
}

#: ⛔ *Undetermined*, and it is a real answer rather than a missing one.
#: `06-edge-cases.md` §6 (hato's): a file tagged `und` is *"treated as NOT the
#: target language"* -- so it is never overwritten and a tagged file coexists
#: with it.
UND = u"und"

_TWO_TO_THREE = dict(pair.split() for pair in _ISO_1_TO_2.split("|"))
_THREE_TO_TWO = {}
for _two, _three in _TWO_TO_THREE.items():
    _THREE_TO_TWO.setdefault(_three, _two)
_THREE_TO_TWO.update(_BIBLIOGRAPHIC)

#: Every token this module will accept as naming a language.
#: 🚨 `und` IS A RECOGNISED TAG, not just an internal answer.
#:
#: subliminal and Bazarr both WRITE `.und.` onto a file whose language they
#: could not determine — and this module exists to interoperate with exactly
#: those two. Without it here, `Show.und.srt` parsed to stem `Show.und` and
#: slot `('show.und', 'und')`, which is **not** the slot of `Show.srt`. A file
#: either of them wrote was therefore invisible as belonging to the video and
#: we would write a second copy beside it. Found by an adversarial pass.
#:
#: ⚠ It canonicalises to `UND`, so an explicitly-tagged file and an untagged
#: one land in ONE slot — which is the whole point.
_THREE_TO_TWO[UND] = UND

LANGUAGE_TOKENS = frozenset(list(ISO_639_1) + list(_THREE_TO_TWO))


# ---------------------------------------------------------------------------
# the flags
# ---------------------------------------------------------------------------
# ⭐ TWO CLASSES, AND THE SPLIT IS THE POINT. `03-permissions.md`'s sibling
# rule in hato's spec: *"`hi` is Hindi, `fo` is Faroese, `sdh` is Southern
# Kurdish. Only `cc` is collision-free."*

#: Flags that can never be a language, so they need no context.
#: ⚠ `sdh` IS Southern Kurdish in ISO 639-3 -- and Southern Kurdish has no
#: two-letter code, so it is absent from the bounded table above and lands here
#: unambiguously. That is a consequence of bounding the table, not an accident,
#: and it is why the bound is documented as a decision rather than a shortcut.
UNAMBIGUOUS_FLAGS = frozenset(("forced", "sdh", "cc"))

#: 🚨 Flags that ARE valid language codes, so they are only flags when a
#: language has already been found to their LEFT.
#:
#:     Show.hi.srt      -> Hindi.   Nobody names a file this way meaning
#:                         "hearing impaired" -- there would be no language.
#:     Show.en.hi.srt   -> English, hearing-impaired.
#:
#: This is rule 1 -- *parse the language before trimming flags* -- expressed as
#: a position rather than as an order of operations, because an order of
#: operations is a thing you have to remember.
CONTEXTUAL_FLAGS = frozenset(("hi",))

FLAG_TOKENS = UNAMBIGUOUS_FLAGS | CONTEXTUAL_FLAGS

# ---------------------------------------------------------------------------
# ⛔ THERE IS NO WINDOW, AND THAT WAS MEASURED -- probe 3a/1, 2026-09-09
# ---------------------------------------------------------------------------
# A `WINDOW = 4` bound stood here, on the reasoning that scanning a whole stem
# offers every ordinary word as a candidate and two-letter English words that
# are also codes are common (`is`, `it`, `no`, `so`, `to`, `am`, `as`, `be`,
# `he`, `my`, `or`, `we`).
#
# 🚨 A mutation setting it to 999 SURVIVED the suite. `doctrine/verification`:
# *a surviving mutant is information either way -- either the check does not
# work, or the thing you thought was load-bearing is not.* Measured both arms
# over **24,315 real subtitle filenames** from the corpus's dev slice:
#
#     answers that differ: 0
#
# ⭐ The right-hand constraint was doing the whole job. An ordinary word cannot
# win, not because it is far from the extension, but because the words after it
# are not flags. The only shape the bound could change is a name with four or
# more TRAILING FLAG tokens -- and there the bound produced the WORSE answer:
#
#     Show.no.forced.sdh.cc.hi.srt   bounded -> lang `hi`, the rest swallowed
#                                    unbounded -> lang `no` + four flags  ✅
#
# ⛔ So it went, and its mutant with it -- the same sequence `LEDGER.md` §Logic
# records for the alias score gate. A guard that cannot fail is noise, and
# noise is what gets a check switched off.
#
# ⚠ WHAT REMAINS load-bearing is the `start = 1` below: the first token is the
# beginning of the stem and can never be the tag, because a filename that is
# nothing but a language code has no subject. That one has a mutant and it
# dies.

#: What `05-interface.md` writes back out, in the order players expect.
_FLAG_ORDER = ("forced", "sdh", "cc", "hi")


class Sidecar(object):
    u"""One subtitle filename, taken apart.

    ⚠ `lang` is the RESOLVED code and `tag` is what the file actually said.
    `05-interface.md`: *keep the detected language and the original tag
    separately -- a file tagged `ja-jp` and one tagged `.jpn.` are the same
    language and must dedupe together, but the output name should preserve
    what the user's other tooling expects.*
    """

    __slots__ = ("stem", "lang", "tag", "flags", "ext", "name")

    def __init__(self, stem, lang, tag, flags, ext, name):
        self.stem = stem
        self.lang = lang
        self.tag = tag
        self.flags = list(flags)
        self.ext = ext
        self.name = name

    @property
    def known(self):
        return self.lang != UND

    @property
    def forced(self):
        return "forced" in self.flags

    @property
    def hearing_impaired(self):
        u"""⚠ `sdh`, `cc` and a CONTEXTUAL `hi` all mean this. A file whose
        language IS Hindi does not, which is the whole Bazarr defect."""
        return bool({"sdh", "cc", "hi"} & set(self.flags))

    def slot(self):
        u"""The `(video, language)` key dedupe is keyed on.

        🚨 Case-INSENSITIVE. `06-edge-cases.md` §3: `EP01.SRT` and `ep01.srt`
        are one file on Windows and macOS and two on Linux. Compared folded;
        written with the case the user had.
        """
        return (_fold(self.stem), self.lang)

    def __repr__(self):
        return "Sidecar(%r, lang=%s%s%s)" % (
            self.stem, self.lang,
            "" if self.lang == self.tag or not self.tag else " tag=%s" % self.tag,
            (" +" + "+".join(self.flags)) if self.flags else "")


def parse(filename):
    u"""Take a subtitle filename apart. -> `Sidecar`

    ⚠ Takes a NAME, not a path -- a directory component must never contribute
    a language token. The caller passes `os.path.basename(...)`; `parse_path`
    below does it for them.
    """
    name = filename
    stem, ext = os.path.splitext(name)
    ext = ext[1:].lower()

    tokens = stem.split(".")
    # ⚠ The first token is the start of the stem and can never be the tag: a
    # filename that is nothing but a language code has no subject.
    start = 1

    for i in range(start, len(tokens)):
        # ⚠ NFKC-folded, not merely lowercased. The SLOT folds width, so a
        # token match that did not would make the parser and the slot disagree
        # about the same string: `Show.ｊａ.srt` read as `und` while its slot
        # said `show.ja`. Found by an adversarial pass.
        token, bracketed = _peel_brackets(_fold(tokens[i]))
        if bracketed is None:
            continue
        code = _language_of(token)
        if code is None:
            continue
        rest = []
        for t in tokens[i + 1:]:
            base, more = _peel_brackets(_fold(t))
            if more is None:
                rest.append(_fold(t))        # forces the rejection below
                continue
            if base:
                rest.append(base)
            rest.extend(more)
        rest = bracketed + rest
        # ⭐ RULE 2, and it is a whole-token test by construction: `rest` came
        # from splitting on dots, so there is no substring to get wrong.
        # `Show.chi.srt` never reaches here with `hi` in `rest`, because `chi`
        # was never cut into pieces.
        if any(t not in FLAG_TOKENS for t in rest):
            continue
        return Sidecar(".".join(tokens[:i]), code,
                       _fold(tokens[i]), _ordered(rest), ext, name)

    return Sidecar(stem, UND, u"", [], ext, name)


def _language_of(token):
    u"""The ISO 639-1 code a tag resolves to, or `None`. -> unicode or None

    🚨 THE HYPHENATED LOCALE WAS THE OTHER HALF OF THE 3c-0 DEFECT.
    `05-interface.md` §*Filename tags* lists ``ja-jp`` by name and then rules
    it explicitly: *"A file tagged `ja-jp` and a file tagged `.jpn.` are the
    same language and must dedupe together"* — and `x.ja-jp.srt` read `und`,
    so they did not. Amazon writes this form on every file.

    ⛔ ONLY `<language>-<region>`, and only when the left half is a real code.
    A hyphen is an ordinary character in a filename, so anything looser turns
    release tags into languages. The region is not validated and not used: it
    is deliberately discarded for the CODE and preserved in `Sidecar.tag`,
    which is exactly the split the spec asks for — *"keep the detected language
    and the original tag separately... the output name should preserve what the
    user's other tooling expects."*
    """
    if token in LANGUAGE_TOKENS:
        return _canonical(token)
    if u"-" in token:
        left, _sep, right = token.partition(u"-")
        if left in ISO_639_1 and right and right.isalnum():
            return left
    return None


def _peel_brackets(token):
    u"""`ja[cc]` -> `("ja", ["cc"])`. -> (base, flags) or (token, None).

    🚨 ADDED 2026-09-09, RUNBOOK 3c-0. `05-interface.md` §*Filename tags* lists
    the forms this parser must read: ``.en.`` ``.ja.`` ``.jpn.`` ``ja-jp``
    ``[cc]`` ``[sdh]`` ``.forced.`` — and the bracketed two were **not read**.
    Every ABEMA, Netflix and Amazon file writes them, so `.ja[cc].srt` and
    `.en[cc].srt` both resolved to `und`, **two different languages shared one
    slot, and dedupe trashed one of them.** Measured before the fix: 4,677 of
    40,572 real corpus filenames (11.53%) read `und` while carrying a code the
    file plainly declares.

    ⛔ **`None` MEANS "DO NOT TREAT THIS AS A LANGUAGE TOKEN AT ALL", and that
    is the guard, not a detail.** A filename is full of brackets that are not
    flags — `[Erai-raws]`, `[E27C3F25]`, `[1080p]`. If what is inside is not a
    known flag, this refuses rather than guessing, so `Show.en[E27C3F25].srt`
    stays `und` instead of becoming English. ⭐ Same shape as the right-hand
    constraint the whole algorithm rests on: *`Is` is Icelandic, and it is
    rejected because `Khan` to its right is not a flag.*

    ⚠ A bare bracket group with no base (`Show.ja.[cc].srt`) yields `("", [cc])`
    and the caller treats the empty base as contributing no language, which is
    what lets a trailing `[sdh]` qualify a language token two places to its left.
    """
    if u"[" not in token:
        return token, []
    base, rest = token.split(u"[", 1)
    rest = u"[" + rest
    flags = []
    while rest:
        if not rest.startswith(u"["):
            return token, None
        close = rest.find(u"]")
        if close < 0:
            return token, None
        inner = rest[1:close]
        rest = rest[close + 1:]
        for piece in re.split(r"[^0-9a-z]+", inner):
            if not piece:
                continue
            if piece not in FLAG_TOKENS:
                return token, None
            flags.append(piece)
    return base, flags


def parse_path(path):
    u"""`parse()` on a path's basename. The form callers actually want."""
    return parse(os.path.basename(path))


def _canonical(token):
    u"""A tag as its ISO 639-1 code, when one exists.

    ⭐ This is what makes `.ja` and `.jpn` dedupe together, which
    `05-interface.md` requires and which no substring comparison can do.
    """
    token = token.lower()
    if token in _THREE_TO_TWO:
        return _THREE_TO_TWO[token]
    return token


def _ordered(flags):
    u"""Flags in the documented order, deduped, unknown ones dropped."""
    seen = []
    for flag in _FLAG_ORDER:
        if flag in flags and flag not in seen:
            seen.append(flag)
    return seen


def _fold(text):
    u"""Case- and width-folded, for comparison only.

    ⚠ NFKC first. `06-edge-cases.md` §2.3 and `A4-fix` both landed on this:
    full-width `Ｅｐ０１` and `Ep01` are the same name to a person and to a
    media player, and `str.lower()` alone does not fold them.
    """
    return unicodedata.normalize("NFKC", text).casefold()


# ---------------------------------------------------------------------------
# writing the next one
# ---------------------------------------------------------------------------

#: 🚨 255 BYTES, not characters. `06-edge-cases.md` §3: CJK hits it at ~85
#: characters, and a rename that fails silently is the failure mode.
NAME_MAX = 255

#: Windows refuses these as a whole stem, case-insensitively, with or without
#: an extension. `06-edge-cases.md` §3.
_RESERVED = frozenset(
    ["con", "prn", "aux", "nul"]
    + ["com%d" % i for i in range(1, 10)]
    + ["lpt%d" % i for i in range(1, 10)])


class NameTooLong(ValueError):
    u"""A name could not be trimmed to fit and stay unique."""


def output_name(video_stem, lang, ext, flags=(), tag=None, name_max=NAME_MAX):
    u"""`<video-basename>[.<tag>].<lang>[.forced][.sdh].<ext>`. -> (name, notes)

    ⭐ THE POINT OF THE RULE, from `05-interface.md`: *media players auto-load
    a subtitle matching the video's basename.* That is what "clean" means
    operationally -- so `{video}` is not decoration, it is the mechanism.

    `tag`
        `--keep-all`'s distinguishing token, when several candidates are all
        being written.

    🚨 SPEC AMENDED HERE, 2026-09-09 -- `05-interface.md` says `--keep-all`
    writes `<video>.<lang>.<tag>.<ext>`, with the tag AFTER the language. Built
    that way, **our own reader returns `und` for every file it writes**: `tag`
    is not a flag, so it violates the right-hand constraint and the language
    token is rejected. A second run would then see a folder of untagged files
    and redo all of it.
    ⭐ The tag goes BEFORE the language, where it reads as part of the stem and
    the whole name round-trips. Verified by
    `test_keep_all_names_round_trip_to_the_same_language`.

    `notes` carries anything a person must be told: a trim, a reserved-name
    suffix. ⛔ **Never let a rename change the name silently** -- the whole
    class of bug here is a file that quietly is not where the player looks.
    """
    notes = []
    lang = _canonical(lang or UND)
    suffix = u"".join(u"." + f for f in _ordered([f.lower() for f in flags]))
    # 🚨 AN UNKNOWN LANGUAGE WRITES NO TAG AT ALL, and this was found by the
    # dry run rather than by any check -- probe 3a/2, 2026-09-09.
    #
    # 95.8% of real corpus slots resolve to `und`, so writing the tag renamed
    # **5,980 of 6,192 files** to `.und.` -- a token that means nothing to any
    # player, on a file the user did not ask us to touch, and it made the
    # namer non-idempotent so a second run would do it again.
    #
    # ⚠ A SPEC GAP, recorded not decided (Part 1 defect): `05-interface.md`
    # gives the form `<video>.<lang>.<ext>` and never says what `<lang>` is
    # when there is no language. hato's `06-edge-cases.md` implies this
    # answer -- an untagged file *"is treated as NOT the target language ...
    # never overwrite it; the new file gets the `.ja` suffix and both
    # coexist"* -- which only works if the untagged one keeps its plain name.
    lang_part = u"" if lang == UND else u"." + lang
    tail = u"%s%s.%s" % (lang_part, suffix, ext.lstrip("."))

    stem = video_stem
    # ⚠ RESERVED FIRST, before the tag is appended, and on the FIRST DOT TOKEN
    # -- see `is_reserved`. A whole-stem check stood here and let
    # `CON.eraiws.ja.srt` through, which writes to the console device and
    # leaves no file on disk.
    if is_reserved(stem):
        stem = _disarm(stem)
        notes.append(u"%r begins with a reserved device name on Windows, "
                     u"which would write to the device and leave no file; "
                     u"wrote %r instead" % (video_stem, stem))
    if tag:
        # ⚠ Sanitised to dot-free, so it cannot invent a token boundary and
        # split the stem somewhere the reader would then scan.
        clean = u"".join(ch for ch in tag if ch.isalnum() or ch in u"-_")
        if clean:
            stem = u"%s.%s" % (stem, clean)

    name = stem + tail
    if _bytes(name) > name_max:
        keep = _trim_to(stem, name_max - _bytes(tail))
        if not keep:
            raise NameTooLong(
                "%r leaves no room for a name: the language and extension "
                "alone are %d bytes of the %d-byte limit"
                % (tail, _bytes(tail), name_max))
        notes.append(
            u"the name was %d bytes and the limit is %d, so the stem was "
            u"trimmed from %d characters to %d -- the subtitle will still "
            u"auto-load only if the video's own name is trimmed the same way"
            % (_bytes(name), name_max, len(stem), len(keep)))
        # 🚨 RE-CHECK AFTER THE TRIM. `CONsomethinglong` is not reserved; cut
        # to fit it becomes `CON`, which is. The guard ran before the trim and
        # the trim then re-created exactly what it had just prevented.
        if is_reserved(keep):
            keep = _disarm(keep)
            notes.append(u"trimming left %r, which is a reserved device name; "
                         u"wrote %r instead" % (keep[:-1], keep))
        name = keep + tail
    # ⚠ Windows silently strips a trailing dot or space, so a name carrying one
    # is a name that cannot be found again. `has_trailing_junk` existed and
    # NOTHING CALLED IT -- a predicate with a test and no caller, which an
    # adversarial pass found by grepping for its callers.
    # ⚠ Checked on the STEM. By the time the tail is appended the trailing
    # character is mid-name and harmless-looking, which is how the first
    # attempt at this wiring managed to report nothing.
    if has_trailing_junk(stem):
        notes.append(u"the stem ends in a dot or a space, which Windows "
                     u"silently strips -- the file may not be found again "
                     u"under this name")
    return name, notes


def _disarm(stem):
    u"""Make a reserved device stem safe, preserving what the user had.

    🚨 THE SUFFIX GOES ON THE FIRST DOT TOKEN, not on the end of the stem.
    Windows resolves the device at the first dot, so `CON.eraiws_` is still
    `CON` — appending to the end looks like a fix and is not one. (Caught by
    running the fix and reading its output, which is the only reason it was not
    shipped.)
    """
    head, dot, rest = str(stem).partition(u".")
    return head + u"_" + dot + rest


def _bytes(text):
    u"""⚠ NAME_MAX is a BYTE limit and this project's names are CJK. Measuring
    it in characters overstates the budget by a factor of three."""
    return len(text.encode("utf-8"))


def _trim_to(text, budget):
    u"""The longest prefix of `text` fitting `budget` bytes, cut on a character
    boundary. ⚠ Truncating the encoded bytes would split a multi-byte
    character and produce a name that is not valid UTF-8."""
    if budget <= 0:
        return u""
    out = text
    while out and _bytes(out) > budget:
        out = out[:-1]
    return out.rstrip()


_TRAILING = re.compile(r"[ .]+$")


def is_reserved(stem):
    u"""Would Windows refuse this stem? Exposed so a caller can ask.

    🚨 THE FIRST DOT TOKEN, NOT THE WHOLE STEM, and the difference is a file
    that is not on disk. Windows resolves a device name at the first dot, so
    `CON.eraiws.ja.srt` opens **the console** — measured on this machine:
    `open()` succeeds, `os.path.exists()` returns True, `getsize()` is 0, and
    there is no file. The tool then reports a successful write and trashes the
    superseded original, so the subtitle is simply gone.

    ⚠ An adversarial pass found this against a whole-stem `in _RESERVED`
    check — and the comment beside that check already **described** this
    behaviour as if it were implemented. Prose is not a guard.

    ⚠ CASE-folded, NOT NFKC-folded. Full-width `ＣＯＮ` is a perfectly ordinary
    filename on Windows; NFKC-folding it to `CON` renames a file for no reason
    and breaks the player auto-load match the whole naming rule exists for.
    """
    head = str(stem).split(u".")[0].strip().casefold()
    return head in _RESERVED


def has_trailing_junk(name):
    u"""Windows silently strips trailing dots and spaces, so a name carrying
    them is a name that will not be found again. `06-edge-cases.md` §3."""
    return bool(_TRAILING.search(name))


#: Characters a suffix may not contain: a path separator would write
#: somewhere else, a DOT would become a token the language reader parses, and
#: the rest are refused by Windows.
_SUFFIX_FORBIDDEN = frozenset(u"./\\:*?\"<>|")


def check_suffix(suffix):
    u"""A suffix a caller asked for, or a `ValueError` saying why not. -> str"""
    text = u"%s" % (suffix,)
    bad = sorted(set(c for c in text
                     if c in _SUFFIX_FORBIDDEN or ord(c) < 32))
    if not text or text != text.strip() or bad or len(text) > 32:
        raise ValueError(
            u"%r cannot be a suffix: it must be 1 to 32 characters with no "
            u"leading or trailing space and none of %s. A dot would be read "
            u"as a language or flag tag; a separator would write somewhere "
            u"else. Something like _rt works."
            % (suffix, u" ".join(sorted(_SUFFIX_FORBIDDEN))))
    return text


def suffixed_name(name, suffix):
    u"""`Show - 01.ja[cc].srt` + `_rt` -> `Show - 01_rt.ja[cc].srt`. -> str

    🚨 THE SUFFIX GOES BEFORE THE LANGUAGE, NEVER AT THE VERY END. The same
    trap `output_name`'s `--keep-all` tag fell into: `Show - 01.ja_rt.srt`
    makes `ja_rt` a token this reader does not know, so the file reads `und`
    — to tsubasa, which would then redo it every run, and to every media
    player, which reads the same `.ja.` convention. Inserted after the stem,
    the whole name round-trips and still says Japanese.
    """
    stem = parse(name).stem
    if stem and name.startswith(stem):
        return stem + suffix + name[len(stem):]
    root, ext = os.path.splitext(name)
    return root + suffix + ext


def is_suffixed(name, suffix):
    u"""Is this name already a copy written with `suffix`? -> bool

    ⭐ What stops a re-run retiming its own copies into `_rt_rt`.
    """
    return parse(name).stem.endswith(suffix)


__all__ = [
    "ISO_639_1", "LANGUAGE_TOKENS", "FLAG_TOKENS", "UNAMBIGUOUS_FLAGS",
    "CONTEXTUAL_FLAGS", "UND", "NAME_MAX",
    "Sidecar", "NameTooLong",
    "parse", "parse_path", "output_name", "is_reserved", "has_trailing_junk",
    "check_suffix", "suffixed_name", "is_suffixed",
]
