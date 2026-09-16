# -*- coding: utf-8 -*-
u"""
The subtitle-filename reader and the output namer. RUNBOOK step 3a.
Authority: `05-interface.md` §Naming and dedupe, `06-edge-cases.md` §3, and
hato's `02-data-model.md` §*What "already exists" means*.

⭐ THIS SUITE IS AIMED AT TWO DEFECTS THAT ARE LIVE IN SHIPPED SOFTWARE, and
they fail in opposite directions -- so a check for one of them passes happily
against the other:

    subliminal 2.7.1   `.ja.forced.srt` reads as `und`, so a correctly-named
                       forced subtitle is re-downloaded FOREVER
    Bazarr             flags matched as SUBSTRINGS, so `Show.chi.srt` is
                       Chinese-and-hearing-impaired and `Show.hin.srt` is
                       Hindi-and-hearing-impaired

⚠ Both are cheap to reproduce and neither is exotic, which is the point: this
module is thirty lines of string handling that two mature projects got wrong.

🚨 AND THE REAL-DATA HALF IS NOT DECORATION. `doctrine/verification`: a fixture
cannot show a failure only real data produces. The corpus pass runs the reader
over real subtitle filenames written by strangers and asserts the two
invariants those defects violate.
"""
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tsubasa import sidecar as S                              # noqa: E402
from tsubasa.paths import corpus_root, load_config            # noqa: E402


# ---------------------------------------------------------------------------
# 🚨 THE TWO DEFECTS, FIRST AND BY NAME
# ---------------------------------------------------------------------------

def test_BAZARR_Show_chi_srt_is_Chinese_and_NOT_hearing_impaired():
    u"""🚨 A substring test finds `hi` inside `chi`. There is no substring here
    to find: the name is split on dots and `chi` is never cut."""
    sc = S.parse(u"Show.chi.srt")
    assert sc.lang == u"zh", sc
    assert sc.flags == [], sc
    assert sc.hearing_impaired is False


def test_BAZARR_Show_hin_srt_is_Hindi_and_NOT_hearing_impaired():
    sc = S.parse(u"Show.hin.srt")
    assert sc.lang == u"hi", sc
    assert sc.hearing_impaired is False


def test_SUBLIMINAL_Show_ja_forced_srt_is_Japanese_and_forced():
    u"""🚨 Read as `und` by subliminal, which expects `.ja.fo.` -- so the file
    it just wrote correctly reads back as *"no subtitle present"* and is
    fetched again on every run, forever."""
    sc = S.parse(u"Show.ja.forced.srt")
    assert sc.lang == u"ja", sc
    assert sc.forced is True
    assert sc.known is True, "a correctly-named forced subtitle read as und"


# ---------------------------------------------------------------------------
# rule 1 -- parse the language BEFORE trimming flags
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name,lang", [
    (u"Show.hi.srt", u"hi"),          # Hindi, not "hearing impaired"
    (u"Show.fo.srt", u"fo"),          # Faroese, not "forced"
    (u"Show.is.srt", u"is"),          # Icelandic
    (u"Show.no.srt", u"no"),          # Norwegian
    (u"Show.it.srt", u"it"),          # Italian
])
def test_a_code_that_LOOKS_like_a_flag_is_still_a_language(name, lang):
    u"""⭐ *`hi` is Hindi, `fo` is Faroese, `sdh` is Southern Kurdish. Only
    `cc` is collision-free.* With nothing to its left, a code is the
    language -- a file named `Show.hi.srt` meaning *hearing impaired* would
    carry no language at all."""
    sc = S.parse(name)
    assert sc.lang == lang, sc
    assert sc.flags == [], sc


def test_the_SAME_token_becomes_a_flag_once_a_language_sits_to_its_left():
    u"""⭐ Rule 1 expressed as a POSITION rather than as an order of
    operations, because an order of operations is a thing you have to
    remember."""
    sc = S.parse(u"Show.en.hi.srt")
    assert sc.lang == u"en", sc
    assert sc.flags == [u"hi"], sc
    assert sc.hearing_impaired is True


def test_sdh_is_a_flag_because_the_code_table_is_BOUNDED():
    u"""⚠ `sdh` is Southern Kurdish in ISO 639-3, and Southern Kurdish has no
    two-letter code -- so it is absent from the bounded table and lands
    unambiguously in the flags. That is a consequence of the bound, recorded
    so nobody widens the table without noticing what it costs."""
    assert u"sdh" not in S.LANGUAGE_TOKENS
    sc = S.parse(u"Show.en.sdh.srt")
    assert sc.lang == u"en" and sc.flags == [u"sdh"], sc


def test_cc_is_the_only_collision_free_flag():
    assert u"cc" not in S.LANGUAGE_TOKENS
    assert S.CONTEXTUAL_FLAGS == frozenset((u"hi",)), (
        "a flag was added to the contextual set without a check naming why")


# ---------------------------------------------------------------------------
# rule 2 -- whole dot-delimited tokens, never substrings
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", [
    u"Show.chi.srt", u"Show.hin.srt", u"Show.chi.forced.srt",
    u"Show.thi.srt", u"Machine.srt",
])
def test_no_flag_is_ever_found_INSIDE_a_token(name):
    sc = S.parse(name)
    assert not sc.hearing_impaired, "%r read as hearing-impaired: %r" % (name, sc)


def test_a_flag_only_counts_as_a_WHOLE_token():
    u"""The positive side of the same rule: the flag has to actually be there
    as its own token, or the check above passes against a reader that never
    finds any flag at all."""
    assert S.parse(u"Show.en.cc.srt").flags == [u"cc"]
    assert S.parse(u"Show.en.forced.srt").flags == [u"forced"]


# ---------------------------------------------------------------------------
# the window, and why it is bounded
# ---------------------------------------------------------------------------

def test_an_ORDINARY_WORD_that_is_a_language_code_does_not_win():
    u"""🚨 `is` is Icelandic. `My.Name.Is.Khan.hi.srt` offers it as a
    candidate, and the right-hand constraint is what rejects it -- `Khan` is
    not a flag. The constraint is the guard, not a tidiness rule."""
    sc = S.parse(u"My.Name.Is.Khan.hi.srt")
    assert sc.lang == u"hi", sc
    assert sc.stem == u"My.Name.Is.Khan", sc


# ⚠ `we` was in this list and is NOT an ISO 639-1 code -- the guard assertion
# below caught it on the first run. A parametrised case that is not the thing
# it claims to be is a green check testing nothing.
@pytest.mark.parametrize("word", [u"is", u"it", u"no", u"so", u"to", u"am",
                                  u"as", u"be", u"he", u"my", u"or"])
def test_the_RIGHT_HAND_CONSTRAINT_is_the_guard_and_nothing_else_is(word):
    u"""⭐ MEASURED, probe 3a/1. A `WINDOW = 4` bound stood beside this rule on
    the reasoning that an ordinary English word which is also a code had to be
    kept far from the extension. A mutation setting the window to 999
    **survived**, and both arms then measured **identical over 24,315 real
    subtitle filenames**. The bound was noise; this is the guard.

    Every word below is a real ISO 639-1 code AND a common English word. Each
    is rejected for one reason only: what follows it is not a flag.
    """
    assert word in S.LANGUAGE_TOKENS, "%r is not a code, so this proves nothing" % word
    sc = S.parse(u"A.%s.Story.ja.srt" % word.title())
    assert sc.lang == u"ja", "%r won over the real tag: %r" % (word, sc)
    assert sc.stem == u"A.%s.Story" % word.title(), sc


def test_a_filename_that_is_ONLY_a_language_code_has_no_subject():
    u"""⚠ The first token is the start of the stem and can never be the tag.
    ⭐ This is the half of the old bound that DID survive its mutation."""
    sc = S.parse(u"ja.srt")
    assert sc.lang == S.UND, sc
    assert sc.stem == u"ja"


def test_a_language_carrying_several_flags_is_read_whole():
    u"""🚨 The shape the deleted bound got WRONG. At `WINDOW = 4` this read as
    `hi` with `no.forced.sdh.cc` swallowed into the stem; unbounded it is
    Norwegian with four flags, which is what the name says."""
    sc = S.parse(u"Show.no.forced.sdh.cc.hi.srt")
    assert sc.lang == u"no", sc
    assert sc.flags == [u"forced", u"sdh", u"cc", u"hi"], sc
    assert sc.stem == u"Show", sc


def test_a_language_and_three_flags_is_read_whole():
    sc = S.parse(u"Show.en.forced.sdh.cc.srt")
    assert sc.lang == u"en", sc
    assert sc.flags == [u"forced", u"sdh", u"cc"], sc


# ---------------------------------------------------------------------------
# und -- an answer, not a missing one
# ---------------------------------------------------------------------------

def test_an_untagged_file_is_und_and_not_a_guess():
    sc = S.parse(u"Show.srt")
    assert sc.lang == S.UND
    assert sc.known is False
    assert sc.stem == u"Show"


def test_und_does_not_collide_with_a_tagged_file_in_the_same_slot():
    u"""🚨 hato's `06-edge-cases.md`: a `und` file is *treated as NOT the
    target language* -- so it is never overwritten, and the new file gets the
    `.ja` suffix and both coexist. That only works if their slots differ."""
    assert S.parse(u"Show.srt").slot() != S.parse(u"Show.ja.srt").slot()


# ---------------------------------------------------------------------------
# canonicalisation -- .ja and .jpn are ONE slot
# ---------------------------------------------------------------------------

def test_two_letter_and_three_letter_tags_dedupe_together():
    u"""⭐ `05-interface.md` requires it, and no substring comparison can do
    it: `ja` is not a prefix of `jpn` in any useful sense."""
    a, b = S.parse(u"Show.ja.ass"), S.parse(u"Show.jpn.ass")
    assert a.lang == b.lang == u"ja"
    assert a.slot() == b.slot()


def test_the_ORIGINAL_tag_is_kept_beside_the_resolved_one():
    u"""⚠ *Keep the detected language and the original tag separately* -- the
    output name should preserve what the user's other tooling expects."""
    sc = S.parse(u"Show.jpn.ass")
    assert sc.lang == u"ja" and sc.tag == u"jpn"


def test_the_BIBLIOGRAPHIC_variants_resolve():
    u"""🚨 `.fre.`, `.ger.`, `.chi.` are what appears in filenames, and they
    are the ISO 639-2/B codes rather than the /T ones. Japanese has no B/T
    split, which is why `ja`/`jpn` dodges this whole class."""
    assert S.parse(u"Show.fre.srt").lang == u"fr"
    assert S.parse(u"Show.ger.srt").lang == u"de"
    assert S.parse(u"Show.dut.srt").lang == u"nl"


# ---------------------------------------------------------------------------
# slots, case and width
# ---------------------------------------------------------------------------

def test_the_slot_is_case_insensitive_because_two_platforms_say_so():
    u"""🚨 `06-edge-cases.md` §3: `EP01.SRT` and `ep01.srt` are ONE file on
    Windows and macOS and two on Linux."""
    assert S.parse(u"EP01.JA.SRT").slot() == S.parse(u"ep01.ja.srt").slot()


def test_an_EXPLICIT_und_tag_lands_in_the_same_slot_as_an_untagged_file():
    u"""🚨 subliminal and Bazarr both WRITE `.und.` onto a file whose language
    they could not determine — and this module exists to interoperate with
    exactly those two. `und` was in neither code table, so `Show.und.srt`
    parsed to stem `Show.und` and a slot of its own: a file either of them
    wrote was invisible as belonging to the video, and we would write a second
    copy beside it. Found by an adversarial pass."""
    assert S.parse(u"Show.und.srt").slot() == S.parse(u"Show.srt").slot()
    assert S.parse(u"Show.und.srt").lang == S.UND
    assert S.parse(u"Show.und.srt").stem == u"Show"


def test_a_FULL_WIDTH_language_token_resolves():
    u"""⚠ The slot is NFKC-folded but the token match was `.lower()` only, so
    the parser and the slot disagreed about the same string: `Show.ｊａ.srt`
    read as `und` while its slot said `show.ja`."""
    assert S.parse(u"Show.ｊａ.srt").lang == u"ja"
    assert S.parse(u"Show.ｊａ.srt").slot() == S.parse(u"Show.ja.srt").slot()


def test_the_code_table_is_an_IMMUTABLE_tuple_of_the_size_it_claims():
    u"""⚠ Its docstring said 184 and the tuple had 148 — a false claim in the
    file that bills itself as the canonical table, with no check on it. And it
    is aliased into `movies.py` and baked into a compiled regex there, so a
    LIST would let a future mutation desync the two silently."""
    assert isinstance(S.ISO_639_1, tuple)
    assert len(S.ISO_639_1) == 148
    from tsubasa.movies import _LANG2
    assert list(_LANG2) == list(S.ISO_639_1)


def test_the_slot_folds_full_width_characters():
    u"""⚠ NFKC before casefold. `str.lower()` alone leaves `Ｅｐ０１` and
    `Ep01` as different names, and A4-fix landed on exactly this."""
    assert S.parse(u"Ｅｐ０１.ja.srt").slot() == S.parse(u"Ep01.ja.srt").slot()


def test_a_directory_component_never_contributes_a_language():
    u"""⚠ `parse_path` takes the basename. A folder called `subs.ja` must not
    make every file inside it Japanese.

    🚨 THE FIRST VERSION OF THIS CHECK COULD NOT FAIL. It used
    `join("ja", "Show.srt")`, and a mutation making `parse_path` read the whole
    path SURVIVED -- because the path separator lands *inside* a dot token
    (`ja\\Show`), so the directory could never have won anyway. The check that
    can fail asserts what `parse_path` actually promises: that the `Sidecar`
    describes the BASENAME.
    """
    sc = S.parse_path(os.path.join(u"subs.ja", u"Show.srt"))
    assert sc.lang == S.UND, sc
    assert sc.name == u"Show.srt", (
        "parse_path kept the directory in the name: %r" % sc.name)
    assert sc.stem == u"Show", sc


def test_parse_path_and_parse_agree_on_the_basename():
    u"""The positive side: whatever `parse` says about a name, `parse_path`
    says about that name at the end of any path."""
    tagged = os.path.join(u"anime", u"Katainaka S2", u"ep01.ja.forced.ass")
    assert S.parse_path(tagged).slot() == S.parse(u"ep01.ja.forced.ass").slot()
    assert S.parse_path(tagged).flags == [u"forced"]


# ---------------------------------------------------------------------------
# writing the next name
# ---------------------------------------------------------------------------

def test_the_output_name_is_exactly_what_players_auto_load():
    name, notes = S.output_name(u"Katainaka no Ossan S2 - 01", u"ja", u"ass")
    assert name == u"Katainaka no Ossan S2 - 01.ja.ass"
    assert notes == []


def test_the_output_name_canonicalises_the_language():
    assert S.output_name(u"Show", u"jpn", u"srt")[0] == u"Show.ja.srt"


def test_an_UNKNOWN_language_writes_NO_TAG_at_all():
    u"""🚨 FOUND BY THE DRY RUN, not by a check -- probe 3a/2.

    95.8% of real corpus slots resolve to `und`, so writing the tag renamed
    **5,980 of 6,192 files** to `.und.` -- a token no player understands, on
    files the user never asked us to touch. `doctrine/robustness`: *a
    destructive tool's first dry run is a design review.* This is what the
    review returned.
    """
    assert S.output_name(u"Show - 01", S.UND, u"ass")[0] == u"Show - 01.ass"
    assert S.output_name(u"Show - 01", u"", u"ass")[0] == u"Show - 01.ass"


def test_the_namer_is_IDEMPOTENT_on_a_file_it_already_named():
    u"""⭐ The property the `.und.` defect broke, and the one that makes a
    re-run cheap: naming a file we already named must produce the same name,
    so there is nothing to rename and nothing to trash."""
    for stem, lang, ext in ((u"Show - 01", u"ja", u"ass"),
                            (u"Show - 01", S.UND, u"ass"),
                            (u"Show - 01", u"en", u"srt")):
        first, _ = S.output_name(stem, lang, ext)
        back = S.parse(first)
        second, _ = S.output_name(back.stem, back.lang, back.ext,
                                  flags=back.flags)
        assert second == first, "%r became %r on a second pass" % (first, second)


def test_flags_are_written_in_the_documented_order():
    assert S.output_name(u"Show", u"en", u"srt",
                         flags=[u"sdh", u"forced"])[0] == u"Show.en.forced.sdh.srt"


def test_the_original_extension_is_preserved():
    u"""⛔ *Converting to `.srt` destroys styling and is not this tool's
    business.*"""
    assert S.output_name(u"Show", u"ja", u"ass")[0].endswith(u".ass")


def test_a_round_trip_returns_the_same_slot():
    u"""⭐ The property that makes dedupe work at all: whatever we write must
    read back as the language we wrote it for."""
    for lang, flags in ((u"ja", ()), (u"en", (u"sdh",)), (u"zh", (u"forced",))):
        name, _ = S.output_name(u"Show - 01", lang, u"srt", flags=flags)
        back = S.parse(name)
        assert back.lang == lang, "%r read back as %r" % (name, back.lang)
        assert back.flags == list(flags), name


# --- NAME_MAX, in BYTES ----------------------------------------------------

def test_the_length_limit_is_measured_in_BYTES_not_characters():
    u"""🚨 `06-edge-cases.md` §3: 255 bytes, and CJK hits it at ~85
    characters. Counting characters overstates the budget threefold and the
    rename then fails at the filesystem, which is the silent failure."""
    stem = u"片" * 100                                   # 300 bytes of stem
    name, notes = S.output_name(stem, u"ja", u"ass")
    assert len(name.encode("utf-8")) <= S.NAME_MAX
    assert notes, "the name was trimmed and nothing said so"
    assert len(name) < len(stem), "nothing was actually trimmed"


def test_a_trim_is_REPORTED_and_says_what_it_costs():
    u"""⛔ Never let a rename change the name silently. A trimmed stem no
    longer matches the video's basename, which is the entire mechanism."""
    _name, notes = S.output_name(u"片" * 100, u"ja", u"ass")
    assert any("trimmed" in n for n in notes), notes
    assert any("auto-load" in n for n in notes), (
        "the note must say what the trim costs, not just that it happened")


def test_a_trim_never_splits_a_multibyte_character():
    name, _ = S.output_name(u"片" * 100, u"ja", u"ass")
    name.encode("utf-8").decode("utf-8")              # would raise if split
    assert u"�" not in name


def test_a_name_with_no_room_at_all_RAISES_rather_than_writing_a_stub():
    with pytest.raises(S.NameTooLong):
        S.output_name(u"Show", u"ja", u"ass", name_max=4)


def test_a_short_name_is_untouched_and_reports_nothing():
    u"""The control. Without it the trim checks pass against a namer that
    trims everything."""
    name, notes = S.output_name(u"Show - 01", u"ja", u"srt")
    assert notes == [] and name == u"Show - 01.ja.srt"


# --- Windows ---------------------------------------------------------------

@pytest.mark.parametrize("stem", [u"CON", u"con", u"NUL", u"COM1", u"lpt9",
                                  u"PRN", u"AUX"])
def test_a_reserved_device_name_is_suffixed_and_reported(stem):
    u"""🚨 These cannot exist on Windows, extension or not."""
    name, notes = S.output_name(stem, u"ja", u"srt")
    assert not S.is_reserved(name.split(u".")[0]), name
    assert notes, "a reserved name was changed silently"


@pytest.mark.parametrize("stem", [
    u"CON.eraiws", u"CON.S01E01.1080p", u"nul.720p", u"con.x", u"COM1.y",
])
def test_a_device_name_FOLLOWED_BY_A_DOT_is_still_reserved(stem):
    u"""🚨 PROVEN ON THIS MACHINE TO LOSE THE FILE. Windows resolves a device
    at the FIRST dot, so `CON.eraiws.ja.srt` opens the console: `open()`
    succeeds, `os.path.exists()` returns True, `getsize()` is **0**, and there
    is no file. The tool then reports a successful write and trashes the
    superseded original.

    ⚠ The guard was a whole-stem `in _RESERVED`, and the comment beside it
    already *described* first-dot behaviour as if it were implemented. Prose is
    not a guard. Found by an adversarial pass."""
    name, notes = S.output_name(stem, u"ja", u"srt")
    assert not S.is_reserved(name), name
    assert notes, "a device name was changed silently"


def test_the_suffix_goes_on_the_FIRST_token_not_the_end_of_the_stem():
    u"""⚠ `CON.eraiws_` is still `CON`. Appending to the end looks like a fix
    and is not one — caught by reading the output of the first attempt."""
    name, _ = S.output_name(u"CON.eraiws", u"ja", u"srt")
    assert name == u"CON_.eraiws.ja.srt", name


def test_a_device_name_RECREATED_BY_THE_TRIM_is_caught(tmp_path):
    u"""⚠ `CONsomethinglong` is not reserved; cut to fit, it becomes `CON`,
    which is. The guard ran before the trim and the trim re-created exactly
    what it had just prevented."""
    name, notes = S.output_name(u"CONsomethinglong", u"ja", u"srt", name_max=10)
    assert not S.is_reserved(name), name
    assert any("trimming left" in n for n in notes), notes


def test_a_FULL_WIDTH_device_name_is_NOT_reserved():
    u"""⚠ The inverse defect. `ＣＯＮ` is an ordinary filename on Windows;
    NFKC-folding it to `CON` renames a file for no reason and breaks the
    player auto-load match the whole naming rule exists for. The reserved check
    case-folds; it must not width-fold."""
    name, notes = S.output_name(u"ＣＯＮ", u"ja", u"srt")
    assert name == u"ＣＯＮ.ja.srt", name
    assert notes == []


def test_a_stem_ending_in_a_dot_or_space_is_REPORTED():
    u"""⚠ Windows silently strips them, so the file cannot be found again.
    `has_trailing_junk` existed and **nothing called it** — a predicate with a
    test and no caller, found by grepping for its callers."""
    for stem in (u"Show ", u"Show."):
        _name, notes = S.output_name(stem, u"ja", u"srt")
        assert any("silently strips" in n for n in notes), (stem, notes)
    assert S.output_name(u"Show", u"ja", u"srt")[1] == []


def test_an_ordinary_name_that_merely_CONTAINS_a_device_name_is_untouched():
    u"""⚠ The whole-token lesson again, one layer up: `Conan` is not `CON`."""
    name, notes = S.output_name(u"Conan - 01", u"ja", u"srt")
    assert name == u"Conan - 01.ja.srt" and notes == []


def test_trailing_dots_and_spaces_are_detectable():
    u"""Windows silently strips them, so a name carrying them is a name that
    will not be found again."""
    assert S.has_trailing_junk(u"Show .srt") is False     # inside, not trailing
    assert S.has_trailing_junk(u"Show ") is True
    assert S.has_trailing_junk(u"Show.") is True


# ---------------------------------------------------------------------------
# 🚨 REAL DATA -- what a fixture structurally cannot show
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def real_names():
    u"""Real subtitle filenames from the corpus's DEV slice.

    ⛔ Sealed shows are excluded by asking `dev.corpus` for the slice rather
    than by walking everything and filtering -- `LEDGER.md` §Harness records a
    test whose candidate pool broke the seal silently.
    """
    from tsubasa.dev import corpus as C
    cfg = load_config(ROOT)
    root = corpus_root(cfg, ROOT)
    if not os.path.isdir(root):
        pytest.skip("SKIPPED, NOT PASSED: corpus absent on this machine")
    try:
        dev_shows = C.shows("dev", scope="naming", cfg=cfg, start=ROOT)
    except Exception as exc:
        pytest.skip("SKIPPED, NOT PASSED: %s" % exc)

    out = []
    for show in dev_shows[:400]:
        folder = os.path.join(root, "naming", show)
        if not os.path.isdir(folder):
            continue
        for entry in os.listdir(folder):
            if entry.startswith("_"):
                continue
            if os.path.splitext(entry)[1].lower() in (
                    ".srt", ".ass", ".ssa", ".vtt", ".sub", ".sup", ".idx"):
                out.append(entry)
    if len(out) < 200:
        pytest.skip("SKIPPED, NOT PASSED: only %d real names reachable"
                    % len(out))
    return out


def test_the_reader_never_raises_on_a_real_filename(real_names):
    u"""These were written by hundreds of strangers over twenty years."""
    for name in real_names:
        S.parse(name)
    assert len(real_names) >= 200


def test_a_real_name_ending_in_a_ja_TOKEN_reads_as_Japanese(real_names):
    u"""⭐ THE SUBLIMINAL DEFECT, over real data. Any name whose last dot token
    before the extension is `ja` or `jpn` must read as Japanese -- with or
    without a flag after it."""
    seen = 0
    for name in real_names:
        stem = os.path.splitext(name)[0]
        tokens = [t.lower() for t in stem.split(".")]
        if len(tokens) < 2:
            continue
        # the tag block: a language token followed only by flags
        for i in range(1, len(tokens)):
            if tokens[i] in (u"ja", u"jpn") and all(
                    t in S.FLAG_TOKENS for t in tokens[i + 1:]):
                seen += 1
                assert S.parse(name).lang == u"ja", (
                    "%r carries a whole `.%s.` token and read as %r"
                    % (name, tokens[i], S.parse(name).lang))
                break
    # ⚠ The denominator, printed. A loop that matched nothing is a vacuous pass.
    assert seen >= 10, (
        "only %d of %d real names carried a Japanese tag -- this check did "
        "not exercise anything" % (seen, len(real_names)))


def test_no_real_name_reads_as_hearing_impaired_without_a_whole_flag_token(real_names):
    u"""⭐ THE BAZARR DEFECT, over real data. This is the check a fixture
    cannot make: the corpus contains real `chi`, `hin` and `thi` tags, and a
    substring reader would light them all up.

    ⚠ THE TOKENIZER HERE SPLITS ON BRACKETS AS WELL AS DOTS, and it did not
    until RUNBOOK 3c-0. `るろうに剣心.伝説の最期編.WEBRip.Netflix.ja[cc].srt` is a
    real corpus name, and `cc` inside `ja[cc]` **is** a whole flag token — it
    is simply not a whole *dot* token. When the reader learned to read the
    bracketed form the spec always required, this check went red on a name it
    was now reading correctly.

    ⛔ THE CLAIM IS UNCHANGED AND THE GUARD IS INTACT: hearing-impaired must
    come from a **whole token**, never a substring. `chi`, `hin` and `thi`
    still cannot produce it.

    🚨 AND THE SPLIT IS DELIBERATELY ITS OWN, not `sidecar._peel_brackets`.
    `LEDGER.md` §Harness: *a check whose expectation is computed by the code
    under test cannot fail.* Two independent tokenizers agreeing is the whole
    value; one calling the other is a tautology.
    """
    for name in real_names:
        sc = S.parse(name)
        if not sc.hearing_impaired:
            continue
        stem = os.path.splitext(name)[0]
        tokens = [t for t in re.split(r"[.\[\]]+", stem.lower()) if t]
        assert {u"sdh", u"cc", u"hi"} & set(tokens), (
            "%r read as hearing-impaired with no whole flag token in %r"
            % (name, tokens))


def test_a_flag_inside_a_bracket_is_read_and_a_release_hash_is_NOT(real_names):
    u"""🚨 THE 3c-0 DEFECT AND ITS GUARD, in one check.

    `05-interface.md` §*Filename tags* lists the forms this reader must
    handle — ``.en.`` ``.ja.`` ``.jpn.`` ``ja-jp`` ``[cc]`` ``[sdh]``
    ``.forced.`` — and the bracketed two were not read, so `.ja[cc].srt` and
    `.en[cc].srt` both resolved to `und`, **two different languages shared one
    slot, and dedupe trashed one**. 4,677 of 40,572 real corpus filenames
    (11.53%) were affected.

    ⛔ THE OTHER HALF IS THE GUARD, and it is the half that could go wrong: a
    filename is full of brackets that are **not** flags. If the reader ate them
    it would turn `[E27C3F25]` into evidence. So this drives both directions.
    """
    got = S.parse(u"Show.S01E01.WEBRip.Netflix.ja[cc].srt")
    assert got.lang == u"ja", got
    assert got.flags == [u"cc"], got
    assert got.hearing_impaired is True, got
    # ⭐ The tag preserves what the user wrote — `05-interface.md`: *the output
    # name should preserve what the user's other tooling expects.*
    assert got.tag == u"ja[cc]", got.tag
    assert got.stem == u"Show.S01E01.WEBRip.Netflix", got.stem

    # ⛔ A bracket that is not a flag is not read AT ALL — not the language,
    # not the flag. Guessing here is how a release hash becomes English.
    for hostile in (u"Show.en[E27C3F25].srt", u"Show.en[1080p].srt",
                    u"Show.[E27C3F25].srt", u"Show.ja[.srt",
                    u"Show.ja[cc.srt"):
        assert S.parse(hostile).lang == S.UND, (hostile,
                                                S.parse(hostile).lang)

    # ⭐ AND IT HAPPENS ON REAL DATA, so this is not a fixture talking to
    # itself. The denominator is printed so a vacuous pass is visible.
    seen = [n for n in real_names
            if u"[cc]" in n.lower() or u"[sdh]" in n.lower()]
    assert len(seen) >= 10, (
        "only %d real names carry a bracketed flag -- this check did not "
        "exercise anything" % len(seen))
    resolved = [n for n in seen if S.parse(n).lang != S.UND]
    assert len(resolved) >= len(seen) // 2, (
        "%d of %d real bracketed-flag names still read `und`"
        % (len(seen) - len(resolved), len(seen)))


def test_a_hyphenated_locale_dedupes_with_its_plain_code(real_names):
    u"""🚨 `05-interface.md` RULES THIS BY NAME: *"A file tagged `ja-jp` and a
    file tagged `.jpn.` are the same language and must dedupe together"* — and
    `x.ja-jp.srt` read `und`, so they did not. Amazon writes this form.

    ⭐ The region is discarded from the CODE and kept in the TAG, which is the
    split the same paragraph asks for.
    """
    for form in (u"Show.ja-jp.srt", u"Show.ja-JP.srt", u"Show.jpn.srt",
                 u"Show.ja.srt"):
        assert S.parse(form).lang == u"ja", (form, S.parse(form).lang)
    assert S.parse(u"Show.ja-jp.srt").tag == u"ja-jp"
    assert S.parse(u"Show.ja-jp[sdh].srt").flags == [u"sdh"]
    assert S.parse(u"Show.pt-BR.srt").lang == u"pt"

    # ⛔ A hyphen is an ordinary filename character. Only `<code>-<region>`,
    # and only when the left half is a real code.
    for hostile in (u"Show.ja-.srt", u"Show.-jp.srt", u"Show.xx-jp.srt",
                    u"Show.non-linear.srt", u"Show.blu-ray.srt"):
        assert S.parse(hostile).lang == S.UND, (hostile,
                                                S.parse(hostile).lang)


def test_every_resolved_language_on_real_data_is_a_real_code(real_names):
    u"""A reader that invents codes would still pass every check above."""
    for name in real_names:
        sc = S.parse(name)
        if sc.known:
            assert sc.lang in S.ISO_639_1, (
                "%r resolved to %r, which is not an ISO 639-1 code"
                % (name, sc.lang))
