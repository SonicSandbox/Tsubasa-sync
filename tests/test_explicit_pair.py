# -*- coding: utf-8 -*-
"""
Explicit pairing -- the escape hatch. RUNBOOK step A11.
Authority: `05-interface.md` §*Explicit pairing -- the escape hatch*.

⭐ THE TWO CLAIMS, and the second one is the whole feature.

1. **The pairer is skipped.** A user naming two files gets them paired without
   discovery, the `(season, episode)` index, the alias table or a single name
   being parsed. That is what *"for anything that falls through the cracks"*
   means, and it includes the files discovery deliberately ignores --
   `a.synced.srt`, `a.srt.bak`, a subtitle with the wrong extension entirely.
2. 🚨 **The verdict is NOT skipped, and it is not skipped STRUCTURALLY.**
   `05-interface.md`: *"an explicit-pair flag that bypassed the verdict would
   be the one command capable of"* producing a confidently wrong file. So the
   checks below do not test that today's caller remembers -- they test that
   the bypass has no syntax: no write flag on the pair, no unpacking into a
   tuple, no `force` without a verdict, and no list of things to write until
   every pair has one.

⚠ BOTH DIRECTIONS THROUGHOUT. `doctrine/robustness`: *a refusal-only test
passes against a function that refuses everything.* Every refusal below has an
acceptance beside it, and the verdict gate has a positive control.

⛔ Fully hermetic. Every file is built under `tmp_path`; nothing points at real
media, and no check needs any.
"""
import inspect
import json
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tsubasa import explicit as X                              # noqa: E402

# A real, minimal SRT. ⚠ Built from a literal rather than a format string:
# `LEDGER.md` records two green-and-worthless fixtures in one day where `%d`
# quietly emitted the wrong character class. Nothing here is generated.
SRT = (u"1\n00:00:01,000 --> 00:00:03,000\nline one\n\n"
       u"2\n00:00:05,000 --> 00:00:07,500\nline two\n\n"
       u"3\n00:00:11,250 --> 00:00:13,000\nline three\n\n")


# ==========================================================================
# fixtures
# ==========================================================================

def video(root, name=u"Show - 01.mkv"):
    """A stub container. ⚠ Never opened by this module -- the video side is
    checked by extension only, which is why a stub is honest here."""
    path = Path(root) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\x1a\x45\xdf\xa3 stub, never read by explicit.py")
    return str(path)


def subtitle(root, name=u"Show - 01.srt", text=SRT):
    path = Path(root) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return str(path)


def manifest(root, entries, name=u"pairs.json", raw=None, encoding="utf-8"):
    path = Path(root) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if raw is not None:
        path.write_bytes(raw)
    else:
        path.write_text(json.dumps(entries), encoding=encoding)
    return str(path)


class Verdict(object):
    """What the aligner will hand `decide()` at RUNBOOK 3b.

    Deliberately a stand-in and not a real `Fit`: `decide()`'s contract is an
    object carrying an `outcome`, and pinning it to a concrete class here would
    make the check pass for a reason the contract does not claim.
    """

    def __init__(self, outcome, reason=u""):
        self.outcome = outcome
        self.reason = reason


def kinds(plan):
    return sorted(r.kind for r in plan.refusals)


# ==========================================================================
# ⭐ THE PAIRER IS SKIPPED -- the accepting half
# ==========================================================================

def test_one_explicit_pair_is_accepted(tmp_path):
    plan = X.explicit_pairs(pair_args=[(video(tmp_path),
                                        subtitle(tmp_path))])
    assert plan.accepted == 1
    assert plan.refused == 0
    assert plan.ok is True
    assert plan.pairs[0].source == u"--pair #1"


def test_repeatable_pairs_are_all_accepted(tmp_path):
    """`--pair A.mkv A.srt --pair B.mkv B.srt` -- `05-interface.md`."""
    plan = X.explicit_pairs(pair_args=[
        (video(tmp_path, u"A.mkv"), subtitle(tmp_path, u"A.srt")),
        (video(tmp_path, u"B.mkv"), subtitle(tmp_path, u"B.srt")),
    ])
    assert plan.accepted == 2 and plan.refused == 0
    assert [p.index for p in plan.pairs] == [0, 1]


def test_a_manifest_of_lists_is_accepted(tmp_path):
    path = manifest(tmp_path, [[video(tmp_path, u"A.mkv"),
                                subtitle(tmp_path, u"A.srt")],
                               [video(tmp_path, u"B.mkv"),
                                subtitle(tmp_path, u"B.srt")]])
    plan = X.explicit_pairs(manifest_path=path)
    assert plan.accepted == 2 and plan.ok is True
    assert plan.pairs[0].source == u"pairs.json #1"


def test_a_manifest_of_objects_is_accepted(tmp_path):
    path = manifest(tmp_path, [{"video": video(tmp_path, u"A.mkv"),
                                "subtitle": subtitle(tmp_path, u"A.srt")}])
    plan = X.explicit_pairs(manifest_path=path)
    assert plan.accepted == 1 and plan.ok is True


def test_a_manifest_and_extra_pairs_combine(tmp_path):
    path = manifest(tmp_path, [[video(tmp_path, u"A.mkv"),
                                subtitle(tmp_path, u"A.srt")]])
    plan = X.explicit_pairs(
        pair_args=[(video(tmp_path, u"B.mkv"), subtitle(tmp_path, u"B.srt"))],
        manifest_path=path)
    assert plan.accepted == 2
    assert sorted(p.source for p in plan.pairs) == [u"--pair #1",
                                                    u"pairs.json #1"]


def test_manifest_paths_resolve_against_the_MANIFEST_not_the_cwd(tmp_path,
                                                                 monkeypatch):
    """⭐ A manifest written beside the media and run from elsewhere.

    Resolving relative entries against the working directory would turn every
    one of them into *"does not exist"* -- a refusal that names the wrong
    problem entirely.
    """
    media = tmp_path / "media"
    media.mkdir()
    video(media, u"A.mkv")
    subtitle(media, u"A.srt")
    path = manifest(media, [["A.mkv", "A.srt"]])

    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)

    plan = X.explicit_pairs(manifest_path=path)
    assert plan.ok is True, [r.reason for r in plan.refusals]
    assert os.path.dirname(plan.pairs[0].video) == str(media)


def test_a_manifest_with_a_utf8_BOM_is_read(tmp_path):
    """⚠ Notepad and PowerShell's Out-File write one. `json.load` on a BOM
    raises *"Expecting value: line 1 column 1"*, which names the wrong cause."""
    entries = [[video(tmp_path, u"A.mkv"), subtitle(tmp_path, u"A.srt")]]
    raw = b"\xef\xbb\xbf" + json.dumps(entries).encode("utf-8")
    plan = X.explicit_pairs(manifest_path=manifest(tmp_path, None, raw=raw))
    assert plan.accepted == 1 and plan.ok is True


# ==========================================================================
# ⛔ EXPLICIT MEANS EXPLICIT -- the filters this hatch exists to escape
# ==========================================================================

def test_a_subtitle_discovery_would_call_JUNK_is_still_accepted(tmp_path):
    """`discover.is_junk` drops `a.synced.srt` -- and that is exactly the file
    a user names by hand when the automatic pass got it wrong. Re-running the
    filter the escape hatch exists to escape would defeat it."""
    from tsubasa import discover as D
    sub = subtitle(tmp_path, u"Show - 01.synced.srt")
    assert D.is_junk(sub) is True, "the fixture no longer exercises the rule"

    plan = X.explicit_pairs(pair_args=[(video(tmp_path), sub)])
    assert plan.accepted == 1 and plan.ok is True


def test_a_subtitle_with_the_WRONG_EXTENSION_is_accepted_on_content(tmp_path):
    """⭐ `discover.classify` would never look at `notes.txt`, so this pair is
    unreachable any other way. The content decides, and the note says so."""
    sub = subtitle(tmp_path, u"Show - 01.txt")
    plan = X.explicit_pairs(pair_args=[(video(tmp_path), sub)])
    assert plan.accepted == 1
    assert any(u"parses as srt" in n for n in plan.pairs[0].notes)


def test_the_subtitle_is_parsed_ONCE_and_carried_on_the_pair(tmp_path):
    """Rule 4 asked of the validator: the content check is work `sync()` must
    do anyway, so the result is carried rather than paid for twice."""
    plan = X.explicit_pairs(pair_args=[(video(tmp_path),
                                        subtitle(tmp_path))])
    parsed = plan.pairs[0].subtitle_parse
    assert parsed is not None and parsed.ok and len(parsed.cues) == 3


# ==========================================================================
# 🚨 THE REFUSALS -- where the value of this feature is
# ==========================================================================

def test_a_missing_video_is_refused(tmp_path):
    plan = X.explicit_pairs(pair_args=[
        (str(tmp_path / u"nope.mkv"), subtitle(tmp_path))])
    assert kinds(plan) == ["missing"]
    assert u"the video does not exist" in plan.refusals[0].reason
    assert plan.ok is False


def test_a_missing_subtitle_is_refused(tmp_path):
    plan = X.explicit_pairs(pair_args=[
        (video(tmp_path), str(tmp_path / u"nope.srt"))])
    assert kinds(plan) == ["missing"]
    assert u"the subtitle does not exist" in plan.refusals[0].reason


def test_a_directory_where_a_file_belongs_is_refused(tmp_path):
    folder = tmp_path / "a folder"
    folder.mkdir()
    plan = X.explicit_pairs(pair_args=[(str(folder), subtitle(tmp_path))])
    assert kinds(plan) == ["not-a-file"]
    assert u"is a directory" in plan.refusals[0].reason


def test_SWAPPED_arguments_are_refused_and_the_fix_is_printed(tmp_path):
    """⭐ The commonest mistake this flag attracts. Two independent complaints
    ("not a video" / "not a subtitle") describe one cause far worse than one
    message that names the corrected command."""
    v, s = video(tmp_path, u"A.mkv"), subtitle(tmp_path, u"A.srt")
    plan = X.explicit_pairs(pair_args=[(s, v)])
    assert kinds(plan) == ["swapped"]
    assert u"--pair A.mkv A.srt" in plan.refusals[0].reason


def test_a_video_where_the_subtitle_goes_is_refused(tmp_path):
    plan = X.explicit_pairs(pair_args=[(video(tmp_path, u"A.mkv"),
                                        video(tmp_path, u"B.mkv"))])
    assert kinds(plan) == ["not-a-subtitle"]
    assert u"B.mkv is a video, not a subtitle" in plan.refusals[0].reason


def test_a_subtitle_where_the_video_goes_is_refused(tmp_path):
    """Both sides subtitles -- not a clean swap, so it is not reported as one."""
    plan = X.explicit_pairs(pair_args=[(subtitle(tmp_path, u"A.srt"),
                                        subtitle(tmp_path, u"B.srt"))])
    assert kinds(plan) == ["not-a-video"]
    assert u"A.srt is a subtitle, not a video" in plan.refusals[0].reason


def test_one_file_on_both_sides_is_refused(tmp_path):
    s = subtitle(tmp_path)
    plan = X.explicit_pairs(pair_args=[(s, s)])
    assert kinds(plan) == ["same-file"]


def test_a_case_different_path_is_still_the_SAME_file(tmp_path):
    """⚠ `A.SRT` and `a.srt` are one file on Windows and two strings
    everywhere. The identity is `normcase(realpath(...))` for that reason."""
    s = subtitle(tmp_path, u"Show - 01.srt")
    other = os.path.join(os.path.dirname(s), os.path.basename(s).upper())
    if not os.path.exists(other):
        # ⚠ A skip is not a pass, so it says so and names what it looked at.
        pytest.skip("SKIP: case-sensitive filesystem -- %r does not name the "
                    "same file as %r here, so there is no fold to test"
                    % (os.path.basename(other), os.path.basename(s)))
    plan = X.explicit_pairs(pair_args=[(s, other)])
    assert kinds(plan) == ["same-file"]


def test_the_same_file_answer_does_not_depend_on_normcase_FOLDING(tmp_path,
                                                                  monkeypatch):
    u"""🚨 macOS, REPRODUCED ON WHATEVER MACHINE IS READING THIS.

    `os.path.normcase` folds case on Windows and is a **no-op on every POSIX
    platform**. macOS is POSIX with a case-insensitive filesystem, so it is
    the one place where the filesystem says *one file* and the string identity
    says *two* — and the check above passed for months on a Windows desktop
    while being wrong there.

    ⭐ Neutering `normcase` IS that machine, so the gap is reachable without
    owning one. The three-OS matrix found this; a check that can only be run
    on the OS that has the bug is how it stayed hidden in the first place.

    ⚠ Same shape as the UNC check two files over: **a check written on one OS
    can encode that OS's semantics invisibly.** That one had to be taught not
    to run elsewhere; this one had to be taught to run elsewhere. Both are the
    same mistake seen from opposite ends.
    """
    s = subtitle(tmp_path, u"Show - 01.srt")
    other = os.path.join(os.path.dirname(s), os.path.basename(s).upper())
    if not os.path.exists(other):
        pytest.skip("SKIP: case-sensitive filesystem -- %r does not name the "
                    "same file as %r here, so there is no fold to test"
                    % (os.path.basename(other), os.path.basename(s)))

    # ⛔ BOTH HALVES, AND THE FIRST ATTEMPT AT THIS CHECK ONLY HAD ONE. It
    # neutered `normcase` alone and passed against the unfixed code, which
    # would have shipped a check that proved nothing. The reason is
    # `ntpath.realpath`: since 3.8 it goes through `GetFinalPathNameByHandle`
    # and hands back the file's TRUE case from disk, so on Windows the two
    # spellings already collapse before `normcase` is consulted at all.
    # `posixpath.realpath` resolves symlinks and `..` and leaves case alone.
    # ⚠ `abspath` stands in for it: no input here has a symlink or a `..`.
    monkeypatch.setattr(os.path, "realpath", lambda p, **kw: os.path.abspath(p))
    monkeypatch.setattr(os.path, "normcase", lambda p: p)

    assert X._identity(str(s)) != X._identity(other), (
        "the positive control failed: this machine is supposed to be standing "
        "in for macOS, where these two spellings produce different identity "
        "keys. If they match here, the check below proves nothing")

    plan = X.explicit_pairs(pair_args=[(s, other)])
    assert kinds(plan) == ["same-file"], (
        "with POSIX's normcase, one file read as two -- which is precisely "
        "what macOS did, and it reported 'not-a-video' because the same-file "
        "gate never fired")


def test_an_unreadable_subtitle_carries_the_READERS_OWN_reason(tmp_path):
    """⚠ `.ttml` is a known subtitle extension with no reader yet. The refusal
    quotes the ladder verbatim rather than inventing a sentence."""
    sub = subtitle(tmp_path, u"Show - 01.ttml", text=u"<tt></tt>")
    plan = X.explicit_pairs(pair_args=[(video(tmp_path), sub)])
    assert kinds(plan) == ["unreadable"]
    assert u"not implemented yet" in plan.refusals[0].reason


def test_junk_given_as_a_subtitle_is_refused(tmp_path):
    plan = X.explicit_pairs(pair_args=[
        (video(tmp_path), subtitle(tmp_path, u"notes.txt",
                                   text=u"just prose, nothing timed\n"))])
    assert kinds(plan) == ["unreadable"]
    assert u"no reader recognised this file" in plan.refusals[0].reason


def test_an_unrecognised_VIDEO_extension_is_a_note_not_a_refusal(tmp_path):
    """⭐ The escape hatch exists for what falls through the cracks. Refusing
    an unknown container extension here would make `--pair` unable to do the
    one thing it is for; the container reader refuses it by name if it must."""
    v = video(tmp_path, u"Show - 01.mkv3")
    plan = X.explicit_pairs(pair_args=[(v, subtitle(tmp_path))])
    assert plan.accepted == 1 and plan.refused == 0
    assert any(u"container reader will decide" in n
               for n in plan.pairs[0].notes)


def test_a_file_too_large_to_be_a_subtitle_is_NOT_READ(tmp_path, monkeypatch):
    """🚨 The claim is the MECHANISM, not the outcome: the guard exists so a
    content sniff cannot read a video-sized file into memory. So the reader is
    replaced with something that fails loudly if it is ever called."""
    def boom(path):
        raise AssertionError("read_file was called on an oversized file: %s"
                             % path)

    monkeypatch.setattr(X.formats, "read_file", boom)
    monkeypatch.setattr(X, "MAX_SUBTITLE_BYTES", 16)

    plan = X.explicit_pairs(pair_args=[
        (video(tmp_path), subtitle(tmp_path, u"huge.srt", text=SRT))])
    assert kinds(plan) == ["not-a-subtitle"]
    assert u"far larger than any subtitle" in plan.refusals[0].reason


def test_a_subtitle_under_the_ceiling_IS_read(tmp_path):
    """The positive control for the check above -- without it, that check
    passes against a guard that refuses every size. It asserts the read
    HAPPENED, not merely that the pair survived."""
    plan = X.explicit_pairs(pair_args=[(video(tmp_path),
                                        subtitle(tmp_path))])
    assert plan.accepted == 1
    assert len(plan.pairs[0].subtitle_parse.cues) == 3


# ==========================================================================
# 🚨 ONE SUBTITLE, TWO VIDEOS
# ==========================================================================

def test_one_subtitle_claimed_for_two_videos_refuses_BOTH(tmp_path):
    """🚨 The user's assertion contradicts itself and there is no basis to
    prefer either half, so neither is trusted."""
    s = subtitle(tmp_path, u"Show - 01.srt")
    plan = X.explicit_pairs(pair_args=[(video(tmp_path, u"A.mkv"), s),
                                       (video(tmp_path, u"B.mkv"), s)])
    assert plan.accepted == 0
    assert kinds(plan) == ["duplicate-subtitle", "duplicate-subtitle"]
    assert u"A.mkv" in plan.refusals[0].reason
    assert u"B.mkv" in plan.refusals[0].reason


def test_the_duplicate_refusal_is_NOT_ORDER_DEPENDENT(tmp_path):
    """⚠ Refusing only the second claim would be a defect that hides until
    somebody reorders a manifest."""
    s = subtitle(tmp_path, u"Show - 01.srt")
    a, b = video(tmp_path, u"A.mkv"), video(tmp_path, u"B.mkv")
    forward = X.explicit_pairs(pair_args=[(a, s), (b, s)])
    reverse = X.explicit_pairs(pair_args=[(b, s), (a, s)])
    assert forward.accepted == reverse.accepted == 0
    assert forward.refused == reverse.refused == 2


def test_one_video_with_TWO_LANGUAGE_subtitles_is_not_a_collision(tmp_path):
    """The positive control. `05-interface.md` keeps one subtitle per
    (video x LANGUAGE), so two subtitles for one video is the normal case --
    a collision rule that refused it would break ordinary use."""
    v = video(tmp_path, u"A.mkv")
    plan = X.explicit_pairs(pair_args=[(v, subtitle(tmp_path, u"A.ja.srt")),
                                       (v, subtitle(tmp_path, u"A.en.srt"))])
    assert plan.accepted == 2 and plan.refused == 0


def test_an_exact_repeat_is_COLLAPSED_not_refused(tmp_path):
    """The same instruction said twice is not a contradiction."""
    v, s = video(tmp_path, u"A.mkv"), subtitle(tmp_path, u"A.srt")
    plan = X.explicit_pairs(pair_args=[(v, s), (v, s)])
    assert plan.accepted == 1 and plan.refused == 0
    assert any(u"collapsed" in n for n in plan.pairs[0].notes)


# ==========================================================================
# THE MANIFEST -- a whole-file fault RAISES, a bad ENTRY refuses
# ==========================================================================

def test_a_manifest_that_is_not_JSON_raises(tmp_path):
    path = manifest(tmp_path, None, raw=b"{not json at all")
    with pytest.raises(X.ManifestError) as exc:
        X.explicit_pairs(manifest_path=path)
    assert u"is not valid JSON" in str(exc.value)
    assert u"line 1" in str(exc.value)


def test_a_manifest_that_is_not_a_list_raises(tmp_path):
    path = manifest(tmp_path, {"video": "a.mkv", "subtitle": "a.srt"})
    with pytest.raises(X.ManifestError) as exc:
        X.explicit_pairs(manifest_path=path)
    assert u"must hold a JSON list of pairs" in str(exc.value)


def test_a_manifest_that_is_not_UTF_8_raises_a_MANIFEST_error(tmp_path):
    """⚠ In a project whose worst bug class is an encoding assumption, an
    undecodable manifest must arrive as this module's own fault with the path
    in it -- not as a raw `UnicodeDecodeError` from three frames down."""
    raw = b'[["\xff\xfe not utf-8.mkv", "a.srt"]]'
    with pytest.raises(X.ManifestError) as exc:
        X.explicit_pairs(manifest_path=manifest(tmp_path, None, raw=raw))
    assert u"is not UTF-8 text" in str(exc.value)


def test_an_absent_manifest_raises(tmp_path):
    with pytest.raises(X.ManifestError) as exc:
        X.explicit_pairs(manifest_path=str(tmp_path / u"nope.json"))
    assert u"does not exist" in str(exc.value)


def test_an_EMPTY_manifest_raises_rather_than_doing_nothing(tmp_path):
    """⛔ A request that would silently do nothing while looking like work."""
    with pytest.raises(X.ManifestError) as exc:
        X.explicit_pairs(manifest_path=manifest(tmp_path, []))
    assert u"holds no pairs" in str(exc.value)


def test_ONE_bad_entry_refuses_ITSELF_and_the_others_still_run(tmp_path):
    """⭐ Both directions in one check. A malformed entry is data, not a
    tooling fault -- refusing the whole manifest over entry 2 of 3 would throw
    away two correct instructions."""
    path = manifest(tmp_path, [
        [video(tmp_path, u"A.mkv"), subtitle(tmp_path, u"A.srt")],
        [video(tmp_path, u"B.mkv")],
        [video(tmp_path, u"C.mkv"), subtitle(tmp_path, u"C.srt")],
    ])
    plan = X.explicit_pairs(manifest_path=path)
    assert plan.accepted == 2
    assert kinds(plan) == ["entry"]
    assert plan.refusals[0].source == u"pairs.json #2"
    assert u"exactly 2 paths" in plan.refusals[0].reason


def test_an_entry_missing_the_subtitle_key_names_the_key(tmp_path):
    path = manifest(tmp_path, [{"video": video(tmp_path, u"A.mkv")}])
    plan = X.explicit_pairs(manifest_path=path)
    assert kinds(plan) == ["entry"]
    assert u"no 'subtitle'" in plan.refusals[0].reason


def test_an_entry_with_an_UNKNOWN_key_fails_closed_and_names_it(tmp_path):
    """⛔ `{"video": ..., "sub": ...}` must not read as *the subtitle is
    missing*; that hides the typo that caused it. `doctrine/robustness`: a
    machine writer meeting an unlisted field fails closed, loudly."""
    path = manifest(tmp_path, [{"video": video(tmp_path, u"A.mkv"),
                                "sub": subtitle(tmp_path, u"A.srt")}])
    plan = X.explicit_pairs(manifest_path=path)
    assert kinds(plan) == ["entry"]
    assert u"unknown key 'sub'" in plan.refusals[0].reason


def test_an_entry_whose_path_is_not_text_is_refused(tmp_path):
    path = manifest(tmp_path, [[video(tmp_path, u"A.mkv"), 17]])
    plan = X.explicit_pairs(manifest_path=path)
    assert kinds(plan) == ["entry"]
    assert u"must be text" in plan.refusals[0].reason


def test_an_entry_with_an_empty_path_is_refused(tmp_path):
    path = manifest(tmp_path, [[video(tmp_path, u"A.mkv"), u"   "]])
    plan = X.explicit_pairs(manifest_path=path)
    assert kinds(plan) == ["entry"]
    assert u"is empty" in plan.refusals[0].reason


def test_an_entry_that_is_a_bare_string_is_refused(tmp_path):
    path = manifest(tmp_path, ["A.mkv"])
    plan = X.explicit_pairs(manifest_path=path)
    assert kinds(plan) == ["entry"]
    assert u"must be [video, subtitle]" in plan.refusals[0].reason


# ==========================================================================
# USAGE FAULTS -- raised, because there is nothing to attribute a refusal to
# ==========================================================================

def test_a_bare_string_does_not_iterate_into_CHARACTERS(tmp_path):
    """⚠ Without this, `pair_args="a.mkv"` produces five baffling refusals."""
    with pytest.raises(X.ExplicitPairError) as exc:
        X.explicit_pairs(pair_args=u"a.mkv")
    assert u"list OF pairs" in str(exc.value)


def test_ONE_FLAT_PAIR_is_named_rather_than_guessed(tmp_path):
    """`("a.mkv", "a.srt")` could be one pair or two malformed entries and
    guessing either way would be wrong."""
    with pytest.raises(X.ExplicitPairError) as exc:
        X.explicit_pairs(pair_args=(video(tmp_path), subtitle(tmp_path)))
    assert u"ONE flat pair" in str(exc.value)


def test_a_pair_argument_of_the_wrong_length_is_refused(tmp_path):
    """The `--pair` side of the entry check, not only the manifest side."""
    plan = X.explicit_pairs(pair_args=[[video(tmp_path)]])
    assert kinds(plan) == ["entry"]
    assert plan.refusals[0].source == u"--pair #1"
    assert u"exactly 2 paths" in plan.refusals[0].reason


def test_a_manifest_that_is_a_DIRECTORY_raises(tmp_path):
    folder = tmp_path / "pairs.json"
    folder.mkdir()
    with pytest.raises(X.ManifestError) as exc:
        X.explicit_pairs(manifest_path=str(folder))
    assert u"is a directory" in str(exc.value)


def test_every_record_survives_being_printed(tmp_path):
    """⚠ A `__repr__` that raises turns a real failure into a traceback about
    formatting, which is how a diagnosis gets lost at 2am."""
    plan = X.explicit_pairs(pair_args=[
        (video(tmp_path, u"A.mkv"), subtitle(tmp_path, u"A.srt")),
        (str(tmp_path / u"gone.mkv"), subtitle(tmp_path, u"B.srt"))])
    decision = plan.pairs[0].decide(Verdict(X.REFUSED, u"a cut"), force=True)
    for record in (plan, plan.pairs[0], plan.refusals[0], decision):
        assert repr(record)


def test_asking_for_explicit_pairing_with_NOTHING_raises(tmp_path):
    with pytest.raises(X.ExplicitPairError):
        X.explicit_pairs()
    with pytest.raises(X.ExplicitPairError):
        X.explicit_pairs(pair_args=[])


# ==========================================================================
# 🚨 THE VERDICT GATE -- structural, not remembered
# ==========================================================================

def one_pair(tmp_path):
    plan = X.explicit_pairs(pair_args=[(video(tmp_path),
                                        subtitle(tmp_path))])
    assert plan.accepted == 1
    return plan, plan.pairs[0]


def test_a_pair_carries_NO_WRITE_AUTHORIZATION_of_any_kind(tmp_path):
    """🚨 Mechanism 1. There is nothing on the object to read instead of
    asking -- no output path, no write flag, no `ok`. Enumerated from
    `__slots__` rather than from recollection."""
    _plan, pair = one_pair(tmp_path)
    for name in ("write", "output_path", "ok", "confident", "may_write",
                 "outcome", "decision"):
        assert not hasattr(pair, name), \
            "ExplicitPair.%s exists and could be read instead of the verdict" \
            % name
    assert set(X.ExplicitPair.__slots__) == {
        "index", "source", "video", "subtitle", "notes", "subtitle_parse",
        "_plan"}


def test_a_pair_does_NOT_UNPACK_into_a_video_and_a_subtitle(tmp_path):
    """🚨 Mechanism 3. `for video, sub in pairs:` is the bypass shape, so it
    raises -- and the message names the route that does not skip the verdict."""
    _plan, pair = one_pair(tmp_path)
    with pytest.raises(TypeError) as exc:
        _v, _s = pair
    assert u"skips the verdict" in str(exc.value)
    assert u"decide" in str(exc.value)


def test_a_PLAN_is_not_iterable_so_the_refusals_cannot_be_lost(tmp_path):
    """Iterating a plan would walk the accepted half and silently drop
    `plan.refusals` -- the shape behind the interface ledger's green run."""
    plan, _pair = one_pair(tmp_path)
    with pytest.raises(TypeError) as exc:
        list(plan)
    assert u".refusals" in str(exc.value)


def test_deciding_with_NO_VERDICT_raises(tmp_path):
    _plan, pair = one_pair(tmp_path)
    with pytest.raises(X.VerdictRequired) as exc:
        pair.decide(None)
    assert u"skips the PAIRER, never the VERDICT" in str(exc.value)


def test_FORCE_WITHOUT_A_VERDICT_STILL_RAISES(tmp_path):
    """🚨 Mechanism 2, and the single most important check in this file.
    `--force` overrides a refusal. It is not itself a verdict, and a caller
    reaching for it must not thereby skip the measurement."""
    _plan, pair = one_pair(tmp_path)
    with pytest.raises(X.VerdictRequired) as exc:
        pair.decide(None, force=True)
    assert u"force=True is not a verdict" in str(exc.value)


def test_force_cannot_even_be_passed_POSITIONALLY(tmp_path):
    """`decide(True)` must not be readable as *force it*. `force` is
    keyword-only so the first positional argument is always the verdict."""
    _plan, pair = one_pair(tmp_path)
    with pytest.raises(TypeError):
        pair.decide(Verdict(X.REFUSED, u"nope"), True)


def test_a_merely_TRUTHY_object_is_not_a_verdict(tmp_path):
    """Nothing that is merely truthy may authorize a write."""
    _plan, pair = one_pair(tmp_path)
    for impostor in (True, 1, u"CONFIDENT", object()):
        with pytest.raises(X.VerdictRequired):
            pair.decide(impostor, force=True)


def test_an_UNRECOGNISED_outcome_is_never_treated_as_a_success(tmp_path):
    _plan, pair = one_pair(tmp_path)
    with pytest.raises(X.VerdictRequired) as exc:
        pair.decide(Verdict(u"PROBABLY_FINE", u"looks alright"))
    assert u"not one of" in str(exc.value)


def test_an_ENUM_outcome_is_accepted(tmp_path):
    """`Result.outcome` may well be an enum at RUNBOOK 3b, and
    `str(SomeEnum.CONFIDENT)` is `'SomeEnum.CONFIDENT'` -- so the members are
    read rather than the object stringified. Untested, this branch would be
    found by whoever writes `Result`, at full price."""
    import enum

    class Outcome(enum.Enum):
        CONFIDENT = u"CONFIDENT"
        REFUSED = u"REFUSED"

    _plan, pair = one_pair(tmp_path)
    assert pair.decide(Verdict(Outcome.CONFIDENT)).write is True
    assert pair.decide(Verdict(Outcome.REFUSED, u"a cut")).write is False


def test_a_CONFIDENT_verdict_writes(tmp_path):
    """⭐ The positive control. Without it every check above passes against a
    `decide()` that authorizes nothing at all."""
    _plan, pair = one_pair(tmp_path)
    decision = pair.decide(Verdict(X.CONFIDENT))
    assert decision.write is True
    assert decision.outcome == X.CONFIDENT
    assert decision.forced is False


def test_a_REFUSED_verdict_does_not_write(tmp_path):
    _plan, pair = one_pair(tmp_path)
    decision = pair.decide(Verdict(X.REFUSED, u"a broadcast cut"))
    assert decision.write is False
    assert u"a broadcast cut" in decision.reason


def test_FORCE_overrides_a_refusal_and_it_is_STILL_reported_refused(tmp_path):
    """⚠ `LEDGER.md` §Interface: *"11 confident, 1 refused"* was painted green
    because the bare word "confident" was matched. A forced write is the most
    dangerous thing this feature can do and may never be relabelled."""
    _plan, pair = one_pair(tmp_path)
    decision = pair.decide(Verdict(X.REFUSED, u"a broadcast cut"), force=True)
    assert decision.write is True
    assert decision.outcome == X.REFUSED
    assert decision.forced is True
    assert u"WRITTEN UNDER --force" in decision.reason
    assert u"a broadcast cut" in decision.reason


def test_force_does_NOT_override_an_ERROR_and_says_why(tmp_path):
    """⚠ `REFUSED` is *measured and rejected* -- there is an offset to trust.
    `ERROR` is *could not be measured*; there is no answer to stand behind, so
    force has nothing to override. `LEDGER.md`: subsync shipped that confusion
    twice."""
    _plan, pair = one_pair(tmp_path)
    decision = pair.decide(Verdict(X.ERROR, u"only one cue"), force=True)
    assert decision.write is False
    assert decision.outcome == X.ERROR
    assert u"--force does not apply" in decision.reason


def test_a_DECISION_CANNOT_BE_CONSTRUCTED_by_hand(tmp_path):
    """🚨 A `Decision` IS the write authorization, so holding one must mean
    having been given it by `decide()`. Without the mint,
    `Decision(pair, CONFIDENT, "")` is a permission slip with no verdict behind
    it -- the last hand-writable route to `write is True`."""
    _plan, pair = one_pair(tmp_path)

    # The obvious hand-construction does not even have the right arity...
    with pytest.raises(TypeError):
        X.Decision(pair, X.CONFIDENT, u"")

    # ...and supplying a plausible token is what the guard is actually for.
    with pytest.raises(X.VerdictRequired) as exc:
        X.Decision(object(), pair, X.CONFIDENT, u"")
    assert u"no verdict behind it" in str(exc.value)

    # ...and the positive control: the minted one works, so the check above
    # is not passing against a constructor that refuses everything.
    assert pair.decide(Verdict(X.CONFIDENT)).write is True


def test_deciding_TWICE_lets_the_last_answer_stand(tmp_path):
    """Pinned rather than left to chance. A retry after a transient fault is
    real; it is not a bypass, because every call still costs a verdict."""
    plan, pair = one_pair(tmp_path)
    pair.decide(Verdict(X.ERROR, u"could not read the container"))
    pair.decide(Verdict(X.CONFIDENT))
    assert len(plan.decisions()) == 1
    assert plan.decisions()[0].outcome == X.CONFIDENT
    assert len(plan.writable()) == 1


def test_a_decision_cannot_be_ASSIGNED_a_write(tmp_path):
    """`write` is derived, so there is no setter and no slot behind it."""
    _plan, pair = one_pair(tmp_path)
    decision = pair.decide(Verdict(X.REFUSED, u"nope"))
    with pytest.raises(AttributeError):
        decision.write = True
    assert decision.write is False


def test_the_reason_is_NEVER_EMPTY_on_a_non_confident_outcome(tmp_path):
    """`03-permissions.md` §hand-back. A blank refusal reads as a success at
    every surface downstream."""
    _plan, pair = one_pair(tmp_path)
    for outcome in (X.REFUSED, X.ERROR):
        for verdict in (Verdict(outcome), Verdict(outcome, u"   "),
                        Verdict(outcome, None)):
            decision = pair.decide(verdict)
            assert decision.reason.strip(), \
                "%s came back with an empty reason" % outcome


def test_a_REFUSAL_has_no_decide_and_so_cannot_be_forced(tmp_path):
    """🚨 *Force overrides the verdict, never a broken input* -- as a shape,
    not as a rule. A path that does not exist never becomes an `ExplicitPair`,
    so there is no object on which forcing could be expressed."""
    plan = X.explicit_pairs(pair_args=[
        (str(tmp_path / u"nope.mkv"), subtitle(tmp_path))])
    refusal = plan.refusals[0]
    assert not hasattr(refusal, "decide")
    assert not hasattr(refusal, "write")
    assert refusal.outcome == X.ERROR


def test_explicit_pairs_takes_NO_FORCE_PARAMETER(tmp_path):
    """The mechanism behind the check above, asserted directly: force is not
    in scope at the input layer, so it cannot reach a broken input."""
    params = inspect.signature(X.explicit_pairs).parameters
    assert "force" not in params
    assert set(params) == {"pair_args", "manifest_path"}
    with pytest.raises(TypeError):
        X.explicit_pairs(pair_args=[], force=True)


# ==========================================================================
# 🚨 THE WRITE LIST DOES NOT EXIST UNTIL EVERY PAIR HAS A VERDICT
# ==========================================================================

def two_pairs(tmp_path):
    plan = X.explicit_pairs(pair_args=[
        (video(tmp_path, u"A.mkv"), subtitle(tmp_path, u"A.srt")),
        (video(tmp_path, u"B.mkv"), subtitle(tmp_path, u"B.srt")),
    ])
    assert plan.accepted == 2
    return plan


def test_writable_RAISES_before_anything_has_been_decided(tmp_path):
    """🚨 Mechanism 4. The list of things to write is not merely empty before
    the verdicts arrive -- it does not exist."""
    plan = two_pairs(tmp_path)
    with pytest.raises(X.VerdictRequired) as exc:
        plan.writable()
    assert u"2 of 2 explicit pairs have no verdict" in str(exc.value)


def test_writable_NAMES_the_pair_a_loop_skipped(tmp_path):
    """⚠ The real accident: a loop that `continue`s past one pair. A silently
    short write list would look exactly like success."""
    plan = two_pairs(tmp_path)
    plan.pairs[0].decide(Verdict(X.CONFIDENT))
    with pytest.raises(X.VerdictRequired) as exc:
        plan.writable()
    assert u"1 of 2" in str(exc.value)
    assert u"B.srt" in str(exc.value)


def test_writable_returns_ONLY_the_authorized_decisions(tmp_path):
    """⭐ The positive control: without it, the two checks above pass against
    a `writable()` that always raises."""
    plan = two_pairs(tmp_path)
    plan.pairs[0].decide(Verdict(X.CONFIDENT))
    plan.pairs[1].decide(Verdict(X.REFUSED, u"a different cut"))
    writable = plan.writable()
    assert len(writable) == 1
    assert writable[0].pair.subtitle.endswith(u"A.srt")


def test_a_forced_refusal_DOES_reach_the_write_list(tmp_path):
    """`--force` is *the only way to override, and it must be typed
    deliberately* -- but it does have to work."""
    plan = two_pairs(tmp_path)
    plan.pairs[0].decide(Verdict(X.CONFIDENT))
    plan.pairs[1].decide(Verdict(X.REFUSED, u"a different cut"), force=True)
    assert len(plan.writable()) == 2
    assert plan.decision_summary().startswith(u"1 FORCED")


def test_a_run_where_EVERYTHING_was_refused_at_input_still_completes(tmp_path):
    """⚠ `writable()` must not raise when there is nothing to decide. A run
    whose every assertion was refused at the input is a finished run with an
    empty write list, not a tooling fault -- and confusing the two would make
    the commonest bad manifest look like a crash."""
    s = subtitle(tmp_path, u"Show - 01.srt")
    plan = X.explicit_pairs(pair_args=[(video(tmp_path, u"A.mkv"), s),
                                       (video(tmp_path, u"B.mkv"), s)])
    assert plan.accepted == 0 and plan.refused == 2
    assert plan.writable() == []


def test_undecided_reports_what_is_outstanding(tmp_path):
    plan = two_pairs(tmp_path)
    assert len(plan.undecided()) == 2
    plan.pairs[0].decide(Verdict(X.CONFIDENT))
    assert [p.index for p in plan.undecided()] == [1]


# ==========================================================================
# ⚠ A REFUSAL MUST BE UNMISSABLE IN THE SUMMARY
# ==========================================================================

def test_a_summary_with_refusals_LEADS_with_them(tmp_path):
    """⚠ `LEDGER.md` §Interface: the GUI painted a run containing refusals
    green because *"11 confident, 1 refused"* contains the word "confident".
    So no positive word may precede the refusal count."""
    plan = X.explicit_pairs(pair_args=[
        (video(tmp_path, u"A.mkv"), subtitle(tmp_path, u"A.srt")),
        (str(tmp_path / u"nope.mkv"), subtitle(tmp_path, u"B.srt")),
    ])
    line = plan.summary()
    assert u"REFUSED" in line
    assert line.index(u"REFUSED") < line.index(u"accepted")
    assert line.startswith(u"1 REFUSED")
    assert plan.ok is False


def test_a_clean_summary_says_so_without_the_word_refused(tmp_path):
    """The other direction: a clean run must not carry an alarming word."""
    plan, _pair = one_pair(tmp_path)
    assert plan.summary() == u"1 accepted"
    assert u"REFUSED" not in plan.summary()
    assert plan.ok is True


def test_the_decision_summary_puts_refusals_and_forces_FIRST(tmp_path):
    plan = X.explicit_pairs(pair_args=[
        (video(tmp_path, u"A.mkv"), subtitle(tmp_path, u"A.srt")),
        (video(tmp_path, u"B.mkv"), subtitle(tmp_path, u"B.srt")),
        (video(tmp_path, u"C.mkv"), subtitle(tmp_path, u"C.srt")),
    ])
    plan.pairs[0].decide(Verdict(X.CONFIDENT))
    plan.pairs[1].decide(Verdict(X.REFUSED, u"a different cut"))
    plan.pairs[2].decide(Verdict(X.ERROR, u"one cue only"))
    line = plan.decision_summary()
    assert line.index(u"REFUSED") < line.index(u"confident")
    assert line.index(u"ERROR") < line.index(u"confident")


def test_a_PART_DECIDED_run_says_so_rather_than_reading_as_finished(tmp_path):
    """⚠ Two confident pairs out of three is not *"2 confident"*. A summary
    printed mid-run that omits the outstanding work reads as a completed run
    with fewer files than the user gave it."""
    plan = two_pairs(tmp_path)
    plan.pairs[0].decide(Verdict(X.CONFIDENT))
    assert u"1 not yet decided" in plan.decision_summary()


def test_a_run_that_is_entirely_confident_reads_as_such(tmp_path):
    plan = two_pairs(tmp_path)
    for pair in plan.pairs:
        pair.decide(Verdict(X.CONFIDENT))
    assert plan.decision_summary() == u"2 confident"


# ==========================================================================
# ⭐ THE FLAGSHIP: a VALID pairing whose alignment is still refused
# ==========================================================================

def test_a_subtitle_with_NO_CUES_is_a_valid_PAIRING(tmp_path):
    """🚨 *Parsed zero cues* and *could not read the file* are different
    outcomes and this project has shipped them conflated twice
    (`formats/__init__.py`). An empty subtitle read cleanly, so the PAIRING
    stands; there is simply nothing to align, and that is the VERDICT's
    sentence to pass, not this module's."""
    sub = subtitle(tmp_path, u"Show - 01.srt", text=u"")
    plan = X.explicit_pairs(pair_args=[(video(tmp_path), sub)])
    assert plan.accepted == 1 and plan.refused == 0
    assert any(u"contains no cues" in n for n in plan.pairs[0].notes)

    # ...and the verdict is what refuses it, exactly as the spec describes.
    decision = plan.pairs[0].decide(Verdict(X.ERROR, u"fewer than 5 cues"))
    assert decision.write is False
    assert plan.writable() == []


def test_the_whole_shape_end_to_end(tmp_path):
    """⭐ *"The pairing was accepted; the alignment was not."*

    One manifest, four assertions by the user: one that aligns, one whose
    timing refuses, one refused at the input, and one forced through. This is
    the check that would go red if any layer stopped talking to the next.
    """
    good_v, good_s = video(tmp_path, u"A.mkv"), subtitle(tmp_path, u"A.srt")
    cut_v, cut_s = video(tmp_path, u"B.mkv"), subtitle(tmp_path, u"B.srt")
    old_v, old_s = video(tmp_path, u"C.mkv"), subtitle(tmp_path, u"C.srt")
    path = manifest(tmp_path, [[good_v, good_s], [cut_v, cut_s],
                               [str(tmp_path / u"gone.mkv"),
                                subtitle(tmp_path, u"gone.srt")],
                               [old_v, old_s]])

    plan = X.explicit_pairs(manifest_path=path)
    assert plan.accepted == 3 and plan.refused == 1
    assert plan.summary().startswith(u"1 REFUSED")

    plan.pairs[0].decide(Verdict(X.CONFIDENT))
    plan.pairs[1].decide(Verdict(X.REFUSED, u"a broadcast cut"))
    plan.pairs[2].decide(Verdict(X.REFUSED, u"a different cut"), force=True)

    writable = plan.writable()
    assert {os.path.basename(d.pair.subtitle) for d in writable} == \
        {u"A.srt", u"C.srt"}
    assert plan.decision_summary().startswith(u"1 FORCED · 2 REFUSED")
