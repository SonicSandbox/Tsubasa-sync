# -*- coding: utf-8 -*-
u"""
The write half of 3a: removing cue blocks, and performing a `DedupePlan`.
Authority: `03-permissions.md` (the field whitelist), `12-alignment.md` §6
(`D9`), `05-interface.md` §Naming and dedupe, `doctrine/robustness`.

===========================================================================
⛔ EVERYTHING HERE IS ABOUT A FILE THE USER CANNOT REPLACE.
===========================================================================

`02-data-model.md` lists four stores and marks exactly one **NOT disposable**:
the user's subtitle files. This is the only module that writes to them, so the
checks are weighted accordingly -- most of them assert that something did NOT
happen.

🚨 THE CHEAPEST PROOF THE WHITELIST HOLDS IS THE ZERO CASE. A retime by 0.0
with nothing dropped must come back **byte-identical**. Any accidental
rebuild -- a re-serialised style block, a normalised timestamp shape, a
rewritten line ending -- shows up there and nowhere else, on every format at
once. It is asserted first, and again on real corpus files.
"""
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# 🚨 `sys.modules`, NOT `from tsubasa import align`. Since RUNBOOK 3b the
# package exports the aligner FUNCTION under that name (`05-interface.md`:
# `from tsubasa import scan, sync, align, Result`), which shadows the
# subpackage of the same name -- so `from tsubasa import align as AL` hands
# back a function and every `AL.mapper_for` fails naming the wrong cause.
# ⭐ It is `LEDGER-HOT.md` trap 8 one level up, and it is caught rather than
# avoided because the spec's name is a promise hato pins.
AL = sys.modules.setdefault("tsubasa.align",
                            __import__("tsubasa.align", fromlist=["fit"]))
from tsubasa import apply as A                                # noqa: E402
from tsubasa import cues as C                                 # noqa: E402
from tsubasa import dedupe as D                               # noqa: E402
from tsubasa import formats                                   # noqa: E402
from tsubasa import sidecar as S                              # noqa: E402
from tsubasa import verdict as V                              # noqa: E402
from tsubasa.cues import RewriteRefused                       # noqa: E402
from tsubasa.paths import corpus_root, load_config            # noqa: E402

# ⚠ THE FUNCTIONS ARE REACHED THROUGH THEIR MODULE, NEVER IMPORTED BY NAME.
# `from tsubasa.cues import drop_cues` binds the name HERE at import time, so a
# mutation run that rebinds `tsubasa.cues.drop_cues` never reaches this file --
# and three mutants SURVIVED against checks written that way before this note
# existed. A check that cannot see the thing it names is not a check.
drop_cues = None            # noqa: F811 -- shadowed on purpose; use C.drop_cues
mapper_for = None           # use AL.mapper_for
removed_spans = None        # use AL.removed_spans
del drop_cues, mapper_for, removed_spans

# ---------------------------------------------------------------------------
# fixtures -- one of every writable format, each carrying something the
# whitelist forbids touching
# ---------------------------------------------------------------------------

SRT = (u"1\n00:00:01,000 --> 00:00:02,000\nfirst\n\n"
       u"2\n00:00:03,000 --> 00:00:04,000\nSPONSOR\n\n"
       u"3\n00:00:05,000 --> 00:00:06,000\nthird\n")

# 🚨 THE NOTE SITS **AFTER** THE CUE THE CHECKS DROP, and that placement is
# the whole point. It was written BEFORE it at first, and a mutation giving
# WebVTT an SRT-style span (which runs FORWARD to the next cue) SURVIVED --
# because a forward span cannot reach backwards over a NOTE that precedes it.
# The fixture did not contain the shape its own check was named for.
# ⚠ One before as well, so the check covers both sides.
VTT = (u"WEBVTT\n\nSTYLE\n::cue { color: peachpuff }\n\n"
       u"NOTE a comment before the first cue\n\n"
       u"first-id\n00:00:01.000 --> 00:00:02.000 align:start\nfirst\n\n"
       u"00:00:03.000 --> 00:00:04.000\nSPONSOR\n\n"
       u"NOTE this comment must survive\n\n"
       u"00:00:05.000 --> 00:00:06.000\nthird\n")

ASS = (u"[Script Info]\nTitle: keep me\n\n[V4+ Styles]\nFormat: Name\n"
       u"Style: Default\n\n[Events]\n"
       u"Format: Layer, Start, End, Style, Text\n"
       u"Dialogue: 0,0:00:01.00,0:00:02.00,Default,first\n"
       u"Dialogue: 0,0:00:03.00,0:00:04.00,Default,SPONSOR\n"
       u"Comment: 0,0:00:05.00,0:00:06.00,Default,third\n")

SAMPLES = {"srt": SRT, "vtt": VTT, "ass": ASS}


def parsed(fmt):
    result = formats.read_bytes(SAMPLES[fmt].encode("utf-8"), "x." + fmt)
    assert result.ok and len(result.cues) == 3, (fmt, result)
    return result


def dropping(fmt, which, **kw):
    u"""Drop cue `which` (0-based) and return the new text."""
    result = parsed(fmt)
    kw.setdefault("shift", 0.0)
    return C.drop_cues(result, [result.cues[which]],
                     formatter=formats.formatter_for(result), **kw)


# ---------------------------------------------------------------------------
# 🚨 the zero case -- the whitelist's cheapest proof
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fmt", sorted(SAMPLES))
def test_a_zero_shift_with_NO_drop_is_byte_identical(fmt):
    u"""⭐ Any accidental rebuild shows up here and nowhere else."""
    result = parsed(fmt)
    out = C.drop_cues(result, [], formatter=formats.formatter_for(result),
                    shift=0.0)
    assert out == result.text, "%s changed under a zero shift" % fmt


@pytest.mark.parametrize("fmt", sorted(SAMPLES))
def test_the_zero_case_is_not_vacuous(fmt):
    u"""⛔ The check above passes trivially against a `drop_cues` that returns
    its input. This one proves the function actually rewrites."""
    result = parsed(fmt)
    out = C.drop_cues(result, [], formatter=formats.formatter_for(result),
                    shift=5.0)
    assert out != result.text, "%s did not retime at all" % fmt


# ---------------------------------------------------------------------------
# removing a block, per format, and each format's own hazard
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("fmt", sorted(SAMPLES))
def test_the_dropped_cue_is_gone_and_the_others_remain(fmt):
    out = dropping(fmt, 1)
    assert "SPONSOR" not in out, out
    assert "first" in out and "third" in out, out


@pytest.mark.parametrize("which", [0, 1, 2])
def test_SRT_leaves_no_orphan_index_line_behind(which):
    u"""🚨 An SRT block opens with a bare number that belongs to the cue BELOW
    it. A removal starting at the timing line leaves that number stranded, and
    the file then has a block with no timing -- which is what
    `_looks_like_srt_without_timings` calls truncated or corrupt.

    ⚠ EVERY POSITION, and the LAST one is the one that matters. Dropping a
    middle cue with a wrong span produces an *accidentally valid* file -- the
    orphaned number simply acquires the next cue's timing line and the
    renumbering tidies it up. Only the last cue leaves the orphan with nothing
    underneath it, and a mutation survived a middle-only check for exactly
    that reason.
    """
    out = dropping("srt", which)
    reread = formats.read_bytes(out.encode("utf-8"), "x.srt")
    assert reread.ok and len(reread.cues) == 2, (reread, out)
    # 🚨 EVERY line, not `[:1]`. The first version of this sliced the first
    # line only -- a typo -- and a mutation that started the span at the timing
    # line SURVIVED it, leaving exactly the orphan this check is named for.
    lines = [ln.strip() for ln in out.split("\n")]
    for i, line in enumerate(lines):
        if line.isdigit():
            following = lines[i + 1] if i + 1 < len(lines) else u""
            assert "-->" in following, (
                "line %d is a bare index %r with no timing under it: %r"
                % (i, line, out))


def test_SRT_survivors_are_RENUMBERED_to_close_the_gap():
    u"""⛔ The one thing the whitelist explicitly adds for a drop: *SRT
    sequence numbers (renumbered after a drop)*. A gap is legal in the wild
    and some players stop at the first one."""
    out = dropping("srt", 1)
    numbers = [ln.strip() for ln in out.split("\n") if ln.strip().isdigit()]
    assert numbers == ["1", "2"], numbers


def test_dropping_the_LAST_cue_leaves_the_file_exactly_as_it_should_be():
    u"""⚠ THE EXPECTED TEXT IS WRITTEN OUT, not derived from `block_span`.

    🚨 The first version asserted `out == text[:cues[2].block_span[0]]` -- an
    expression built from the very span under test, so a mutation that moved
    the span moved BOTH sides and the check could not fail. A check whose
    expectation is computed by the code it is checking is checking nothing.

    Dropping the last cue also leaves the survivors already numbered 1, 2, so
    this is where an over-eager renumberer would show.
    """
    result = parsed("srt")
    out = C.drop_cues(result, [result.cues[2]],
                      formatter=formats.formatter_for(result), shift=0.0)
    assert out == (u"1\n00:00:01,000 --> 00:00:02,000\nfirst\n\n"
                   u"2\n00:00:03,000 --> 00:00:04,000\nSPONSOR\n\n"), repr(out)


def test_VTT_keeps_a_NOTE_that_sits_between_two_cues():
    u"""🚨 THE DIFFERENCE BETWEEN VTT AND SRT, AND WHY EACH FORMAT DEFINES ITS
    OWN BLOCK SPAN. An SRT-style span running to the next cue would take this
    NOTE with it -- silently, and only on files that bothered to carry one.
    `03-permissions.md` puts NOTE/STYLE/REGION in the never-change column."""
    out = dropping("vtt", 1)
    assert "NOTE this comment must survive" in out, out


def test_VTT_keeps_its_STYLE_block_and_its_cue_settings():
    out = dropping("vtt", 1)
    assert "peachpuff" in out, out
    assert "align:start" in out, out


def test_VTT_takes_the_cue_IDENTIFIER_with_the_cue():
    u"""An identifier belongs to its cue; left behind it becomes the
    identifier of whatever follows."""
    out = dropping("vtt", 0)
    assert "first-id" not in out, out


def test_ASS_keeps_Script_Info_and_the_styles():
    out = dropping("ass", 1)
    assert "Title: keep me" in out and "Style: Default" in out, out


def test_ASS_removes_the_whole_event_line_and_nothing_else():
    out = dropping("ass", 1)
    assert "Dialogue: 0,0:00:03.00" not in out, out
    assert out.count("Dialogue:") == 1 and out.count("Comment:") == 1, out
    # ⚠ AND ITS NEWLINE. A span one character short leaves a blank line where
    # the event was -- a mutation doing exactly that survived the two
    # assertions above, because neither of them can see whitespace.
    events = out.split("[Events]\n", 1)[1]
    assert "\n\n" not in events, "a blank line was left behind: %r" % events


def test_a_COMMENT_line_is_droppable_too():
    u"""⚠ `03-permissions.md` permits `Start`/`End` on `Comment:` lines, so a
    Comment is a cue like any other and must be removable."""
    out = dropping("ass", 2)
    assert "Comment:" not in out, out


# ---------------------------------------------------------------------------
# the refusals
# ---------------------------------------------------------------------------

def test_a_cue_with_no_block_span_is_REFUSED_not_skipped():
    u"""⚠ Half a removal is worse than none -- the same rule `retime` applies
    to a missing timestamp span."""
    result = parsed("srt")
    result.cues[1].block_span = None
    with pytest.raises(RewriteRefused) as e:
        C.drop_cues(result, [result.cues[1]],
                  formatter=formats.formatter_for(result), shift=0.0)
    assert "half-edited" in str(e.value)


# ⚠ THESE TWO PASS A NON-EMPTY `doomed` ON PURPOSE.
#
# 🚨 With an empty one, `drop_cues` returns `retime(...)` immediately -- and
# `retime` re-checks BOTH of these arguments itself. So the guards inside
# `drop_cues` were shadowed, the checks passed for the wrong function, and two
# mutations deleting them SURVIVED. A guard is only tested on a path that
# actually reaches it.

def test_drop_cues_needs_exactly_one_of_shift_or_mapper():
    result = parsed("srt")
    fmt = formats.formatter_for(result)
    doomed = [result.cues[1]]
    with pytest.raises(ValueError):
        C.drop_cues(result, doomed, formatter=fmt)
    with pytest.raises(ValueError):
        C.drop_cues(result, doomed, formatter=fmt, shift=0.0,
                    mapper=lambda t: t)


def test_drop_cues_needs_the_formats_own_formatter():
    result = parsed("srt")
    with pytest.raises(ValueError):
        C.drop_cues(result, [result.cues[1]], shift=0.0)


# ---------------------------------------------------------------------------
# ⭐ D9 -- the arithmetic, on 12-alignment.md §5's own measured numbers
# ---------------------------------------------------------------------------

#: The real broadcast cut §5 records: `+0.400 / −9.825 @3:42`.
CUT = [(222.0, 0.400), (None, -9.825)]


def test_the_removed_span_is_exactly_the_size_of_the_jump():
    (lo, hi), = AL.removed_spans(CUT)
    assert abs((hi - lo) - (0.400 + 9.825)) < 1e-9, (lo, hi)


def test_the_removed_span_starts_at_the_boundary_in_SUBTITLE_time():
    u"""🚨 `segments` is on the REFERENCE axis and the writer has a SUBTITLE
    time. The boundary in subtitle time is `split - offset`, and a writer that
    confused the two would pick the wrong segment for every cue within one
    jump of the break -- the stretch a cut file is most wrong about."""
    (lo, _hi), = AL.removed_spans(CUT)
    assert abs(lo - (222.0 - 0.400)) < 1e-9, lo


def test_a_POSITIVE_jump_removes_nothing():
    u"""⚠ A positive jump INSERTS time; it leaves no cue homeless. Returning a
    span here would delete cues that render perfectly."""
    assert AL.removed_spans([(222.0, -9.825), (None, 0.400)]) == []


def test_an_uncut_fit_removes_nothing():
    assert AL.removed_spans([(None, 1.5)]) == []


def test_the_mapper_applies_the_right_segment_either_side_of_the_break():
    m = AL.mapper_for(CUT)
    assert abs(m(100.0) - 100.400) < 1e-9
    assert abs(m(300.0) - 290.175) < 1e-9


def test_a_cue_inside_the_removed_stretch_would_map_BACKWARDS():
    u"""⭐ The reason D9 exists, stated as a measurement rather than as prose:
    a cue at 225 s maps to 215.175 s, which is BEFORE cues that precede it.
    That is the overlap `12-alignment.md` §6 describes."""
    m = AL.mapper_for(CUT)
    assert m(225.0) < m(221.0), (m(225.0), m(221.0))


# ---------------------------------------------------------------------------
# performing a plan
# ---------------------------------------------------------------------------

def write_srt(path, cues):
    def stamp(x):
        return u"%02d:%02d:%02d,%03d" % (
            x // 3600, (x % 3600) // 60, int(x) % 60, round((x % 1) * 1000))
    with open(path, "w", encoding="utf-8") as handle:
        for i, (start, end, text) in enumerate(cues, 1):
            handle.write(u"%d\n%s --> %s\n%s\n\n"
                         % (i, stamp(start), stamp(end), text))


def a_candidate(path, segments=((None, 1.5),), cues=3):
    verdict = V.Verdict(V.CONFIDENT, u"", word=u"locked", match_rate=0.9,
                        segments=list(segments))
    return D.Candidate(path, S.parse(os.path.basename(path)), verdict,
                       cues=cues, content_end=242.0)


@pytest.fixture
def folder(tmp_path):
    path = tmp_path / "[Erai] Show - 01.ja.srt"
    write_srt(str(path), [(10, 12, u"before the break"),
                          (225, 227, u"SPONSOR CARD"),
                          (240, 242, u"after the break")])
    return tmp_path, str(path)


def test_a_DRY_RUN_writes_nothing_and_says_what_it_would_do(folder):
    u"""⭐ `doctrine/robustness`: a destructive tool is dry-run by default, and
    its first dry run is a design review."""
    tmp, path = folder
    before = sorted(p.name for p in tmp.iterdir())
    original = open(path, encoding="utf-8").read()

    plan = D.plan(u"Show - 01", [a_candidate(path, CUT)])
    report = A.apply_plan(plan, str(tmp / D.TRASH_DIR))

    assert report.performed is False
    assert sorted(p.name for p in tmp.iterdir()) == before
    assert open(path, encoding="utf-8").read() == original
    assert report.written, "a dry run must still say what it WOULD write"


def test_the_default_is_a_dry_run(folder):
    u"""The default itself, not just the flag. ⚠ `apply_plan(plan, root)` with
    no third argument must not touch the disk.

    🚨 THE FIRST VERSION OF THIS READ THE SOURCE FILE, and a mutation flipping
    the default to `dry_run=False` SURVIVED it -- because the output goes to a
    DIFFERENT name (`Show - 01.ja.srt`, not `[Erai] Show - 01.ja.srt`), so
    writing left the source untouched and the check passed. Assert the thing
    that would appear, not the thing that would stay.
    """
    tmp, path = folder
    original = open(path, encoding="utf-8").read()
    A.apply_plan(D.plan(u"Show - 01", [a_candidate(path, CUT)]),
                 str(tmp / D.TRASH_DIR))
    assert not (tmp / "Show - 01.ja.srt").exists(), (
        "a default call wrote the output file")
    assert open(path, encoding="utf-8").read() == original


def test_a_real_run_writes_the_retimed_file_under_the_clean_name(folder):
    tmp, path = folder
    plan = D.plan(u"Show - 01", [a_candidate(path, CUT)])
    report = A.apply_plan(plan, str(tmp / D.TRASH_DIR), dry_run=False)

    assert report.ok, report.errors
    target = tmp / "Show - 01.ja.srt"
    assert target.exists(), sorted(p.name for p in tmp.iterdir())
    body = target.read_text(encoding="utf-8")
    assert "before the break" in body and "after the break" in body


def test_D9_drops_the_sponsor_card_and_COUNTS_it(folder):
    u"""⭐ Ruled 2026-09-08: dropped, **counted**, reported. A person who sees
    a number can go and look; a person who sees nothing cannot."""
    tmp, path = folder
    report = A.apply_plan(D.plan(u"Show - 01", [a_candidate(path, CUT)]),
                          str(tmp / D.TRASH_DIR), dry_run=False)
    body = (tmp / "Show - 01.ja.srt").read_text(encoding="utf-8")

    assert "SPONSOR CARD" not in body, body
    assert report.dropped_in_gap == 1, report.dropped_in_gap
    assert any("commercial break" in n for n in report.notes), report.notes


def test_the_D9_note_reads_correctly_for_ONE_cue(folder):
    u"""⚠ *"1 cue ... they are"* shipped in the first draft of this. A count of
    one is the common case and it is the one that reads wrong."""
    tmp, path = folder
    report = A.apply_plan(D.plan(u"Show - 01", [a_candidate(path, CUT)]),
                          str(tmp / D.TRASH_DIR), dry_run=False)
    note = [n for n in report.notes if "commercial break" in n][0]
    assert "1 cue dropped" in note and "they are" not in note, note


def test_an_UNCUT_pair_drops_nothing(folder):
    u"""The control. Without it every D9 check above passes against a writer
    that drops cues indiscriminately."""
    tmp, path = folder
    report = A.apply_plan(D.plan(u"Show - 01", [a_candidate(path)]),
                          str(tmp / D.TRASH_DIR), dry_run=False)
    body = (tmp / "Show - 01.ja.srt").read_text(encoding="utf-8")
    assert report.dropped_in_gap == 0
    assert "SPONSOR CARD" in body, "an uncut pair lost a cue"


def test_a_cue_ending_before_zero_is_dropped_and_counted(tmp_path):
    u"""The other removal the whitelist permits."""
    path = tmp_path / "Show.ja.srt"
    write_srt(str(path), [(1, 2, u"way too early"), (100, 102, u"fine")])
    report = A.apply_plan(
        D.plan(u"Show", [a_candidate(str(path), [(None, -50.0)])]),
        str(tmp_path / D.TRASH_DIR), dry_run=False)
    assert report.dropped_before_zero == 1, report.dropped_before_zero
    body = (tmp_path / "Show.ja.srt").read_text(encoding="utf-8")
    assert "way too early" not in body and "fine" in body


def test_a_cue_STRADDLING_zero_is_kept(tmp_path):
    u"""⚠ The END, not the start. A cue straddling t=0 is still partly on
    screen, and the whitelist only permits removing one that *ends* before
    zero."""
    path = tmp_path / "Show.ja.srt"
    write_srt(str(path), [(10, 20, u"straddles"), (100, 102, u"fine")])
    report = A.apply_plan(
        D.plan(u"Show", [a_candidate(str(path), [(None, -15.0)])]),
        str(tmp_path / D.TRASH_DIR), dry_run=False)
    assert report.dropped_before_zero == 0
    assert "straddles" in (tmp_path / "Show.ja.srt").read_text(encoding="utf-8")


# --- write first, trash second -------------------------------------------

def test_the_losers_are_trashed_and_the_winner_is_not(tmp_path, monkeypatch):
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    winner = tmp_path / "Show - 01.ja.srt"
    loser = tmp_path / "[Other] Show - 01.ja.srt"
    write_srt(str(winner), [(10, 12, u"good"), (20, 22, u"good2")])
    write_srt(str(loser), [(10, 12, u"worse")])

    plan = D.plan(u"Show - 01", [a_candidate(str(winner), cues=2),
                                 a_candidate(str(loser), cues=1)])
    report = A.apply_plan(plan, str(tmp_path / D.TRASH_DIR), dry_run=False)

    assert winner.exists(), "the winner was removed"
    assert not loser.exists(), "the loser is still there"
    assert (tmp_path / D.TRASH_DIR / "[Other] Show - 01.ja.srt").exists()
    assert len(report.trashed) == 1


def test_a_file_written_OVER_is_never_then_trashed(tmp_path, monkeypatch):
    u"""🚨 THE DATA-LOSS SHAPE THIS GUARD EXISTS FOR. When the winner is
    already named `<video>.<lang>.<ext>`, the output lands on the source. If a
    superseded entry resolves to that same path, trashing it afterwards would
    delete the file we just produced -- and the user would have neither."""
    tmp = tmp_path
    winner = tmp / "Show - 01.ja.srt"
    write_srt(str(winner), [(10, 12, u"kept")])
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")

    plan = D.plan(u"Show - 01", [a_candidate(str(winner))])
    # Force the pathological case: the winner also listed as superseded.
    plan.superseded = list(plan.writes and [plan.writes[0][0]])
    report = A.apply_plan(plan, str(tmp / D.TRASH_DIR), dry_run=False)

    assert winner.exists(), "the file we just wrote was trashed"
    assert report.trashed == []
    assert any("written over it" in n for n in report.notes), report.notes


def test_a_dry_run_does_not_trash_either(folder, monkeypatch):
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    tmp, path = folder
    other = tmp / "[Other] Show - 01.ja.srt"
    write_srt(str(other), [(10, 12, u"worse")])
    plan = D.plan(u"Show - 01", [a_candidate(path, cues=3),
                                 a_candidate(str(other), cues=1)])
    A.apply_plan(plan, str(tmp / D.TRASH_DIR))
    assert other.exists(), "a dry run trashed a file"


# --- failure is per-pair, never per-folder --------------------------------

def test_an_unreadable_file_is_RECORDED_and_the_run_continues(tmp_path):
    u"""⚠ `06-edge-cases.md` §7: per-pair atomicity -- completed pairs stay
    done. One bad file must not cost the folder."""
    bad = tmp_path / "broken.ja.srt"
    # Index lines and no `-->` at all: the signature of a truncated SRT, and
    # the one shape the reader calls genuinely unreadable rather than empty.
    bad.write_text(u"1\nsome text\n\n2\nmore text\n", encoding="utf-8")
    report = A.apply_plan(D.plan(u"broken", [a_candidate(str(bad))]),
                          str(tmp_path / D.TRASH_DIR), dry_run=False)
    assert report.errors, "an unreadable file produced no error"
    assert report.ok is False
    assert not report.written


def test_a_file_that_now_parses_to_ZERO_CUES_is_refused(tmp_path):
    u"""🚨 FOUND BY A CHECK THAT WAS AIMED AT SOMETHING ELSE. A file can read
    perfectly and contain nothing -- `formats` is explicit that OK-with-zero-
    cues and ERROR are different outcomes -- and writing it puts an EMPTY
    subtitle beside the video under the name a player will load.

    ⭐ Refused here rather than trusted to the verdict upstream: the verdict
    judged the file at discovery, and `06-edge-cases.md` §7 lists *subtitle
    edited since last sync* as a real case. That is why `_render` re-reads
    instead of carrying a parse forward.
    """
    empty = tmp_path / "empty.ja.srt"
    empty.write_bytes(b"\x00\x01\x02 not a subtitle at all")
    result = formats.read_file(str(empty))
    assert result.ok and not result.cues, (
        "the fixture is not the state under test: %r" % (result,))

    report = A.apply_plan(D.plan(u"empty", [a_candidate(str(empty))]),
                          str(tmp_path / D.TRASH_DIR), dry_run=False)
    assert report.errors, "an empty subtitle was written"
    assert "zero cues" in report.errors[0][1]
    assert not (tmp_path / "empty.ja.srt").read_bytes() == b"", (
        "the source was overwritten with nothing")


def test_a_verdict_with_NO_SEGMENTS_refuses_to_write(tmp_path):
    u"""⛔ *A file is never retimed by a number nobody measured.*"""
    path = tmp_path / "Show.ja.srt"
    write_srt(str(path), [(10, 12, u"x")])
    candidate = a_candidate(str(path))
    candidate.verdict.segments = []
    report = A.apply_plan(D.plan(u"Show", [candidate]),
                          str(tmp_path / D.TRASH_DIR), dry_run=False)
    assert report.errors and "segments" in report.errors[0][1]


def test_an_empty_plan_reports_its_reason_and_writes_nothing(tmp_path):
    plan = D.plan(u"Show", [])
    report = A.apply_plan(plan, str(tmp_path / D.TRASH_DIR), dry_run=False)
    assert report.written == [] and report.notes


# --- the encoding, which is the worst bug this class of tool can have -----

def test_the_ORIGINAL_CODEC_is_written_back(tmp_path):
    u"""🚨 `03-permissions.md` puts this in the never-change column in red: a
    Shift-JIS caption decoded with `errors="replace"` had all 346 cues become
    U+FFFD -- and because timestamps are ASCII the tool said CONFIDENT and
    wrote perfect timing with no readable text."""
    path = tmp_path / "Show.ja.srt"
    body = (u"1\n00:00:10,000 --> 00:00:12,000\n日本語のテスト\n\n"
            u"2\n00:00:20,000 --> 00:00:22,000\nもう一つ\n")
    path.write_bytes(body.encode("shift_jis"))

    result = formats.read_file(str(path))
    assert result.ok and "日本語" in result.cues[0].text, result

    report = A.apply_plan(D.plan(u"Show", [a_candidate(str(path), cues=2)]),
                          str(tmp_path / D.TRASH_DIR), dry_run=False)
    assert report.ok, report.errors
    raw = (tmp_path / "Show.ja.srt").read_bytes()
    assert u"日本語のテスト" in raw.decode("shift_jis"), "the codec changed"
    assert b"\xef\xbf\xbd" not in raw, "a replacement character was written"


def test_the_write_is_ATOMIC_and_leaves_no_temp_file(tmp_path):
    u"""`LEDGER.md` §Delivery: a crash part-way through an in-place write left
    a 346-cue file with 0 cues; and on Windows an unclosed handle litters
    `.tmp` files beside the user's data."""
    path = tmp_path / "Show.ja.srt"
    write_srt(str(path), [(10, 12, u"x")])
    A.apply_plan(D.plan(u"Show", [a_candidate(str(path))]),
                 str(tmp_path / D.TRASH_DIR), dry_run=False)
    leftovers = [p.name for p in tmp_path.iterdir() if ".tmp" in p.name]
    assert leftovers == [], leftovers


# ---------------------------------------------------------------------------
# 🚨 WHAT AN ADVERSARIAL PASS FOUND, 2026-09-09 — all of it green beforehand
# ---------------------------------------------------------------------------

CRLF_VTT = (u"WEBVTT\r\n\r\n00:00:01.000 --> 00:00:02.000\r\nfirst\r\n\r\n"
            u"00:00:03.000 --> 00:00:04.000\r\nSPONSOR\r\n\r\n"
            u"NOTE this comment must survive\r\n\r\n"
            u"00:00:05.000 --> 00:00:06.000\r\nthird\r\n")


def test_VTT_with_CRLF_keeps_a_NOTE_that_FOLLOWS_the_dropped_cue():
    u"""🚨 `text.find("\\n\\n")` DOES NOT MATCH `\\r\\n\\r\\n`, so on a CRLF file
    the span fell through to *"stop at the next cue"* — silently degrading to
    exactly the SRT-style forward span the function exists to avoid, and
    deleting a block `03-permissions.md` puts in the never-change column.

    ⭐ **66% of the corpus (7,941 of 12,024 files) is CRLF**, and there are
    **zero `.vtt` files in it** — so the real-data checks in this suite
    exercise no WebVTT at all. Every VTT claim rests on these fixtures, which
    is why this one is here in both line endings.
    """
    r = formats.read_bytes(CRLF_VTT.encode("utf-8"), "x.vtt")
    out = C.drop_cues(r, [r.cues[1]], formatter=formats.formatter_for(r),
                      shift=0.0)
    assert "NOTE this comment must survive" in out, out
    assert "SPONSOR" not in out


def test_VTT_with_CRLF_is_byte_identical_under_a_zero_shift():
    r = formats.read_bytes(CRLF_VTT.encode("utf-8"), "x.vtt")
    assert C.drop_cues(r, [], formatter=formats.formatter_for(r),
                       shift=0.0) == r.text


def test_SRT_without_blank_separators_does_not_eat_a_NUMERIC_cue_line():
    u"""🚨 `06-edge-cases.md` §6.4 lists an SRT with no blank lines as a real
    shape. A cue whose TEXT is a bare number — a countdown, a score, a year —
    was read as the next cue's index line, so the removal DELETED IT and the
    renumberer OVERWROTE another one with a sequence number. Both silent, both
    the MUST-NEVER-CHANGE column."""
    text = (u"00:00:01,000 --> 00:00:02,000\n42\n"
            u"00:00:03,000 --> 00:00:04,000\nSPONSOR\n"
            u"00:00:05,000 --> 00:00:06,000\nthird\n")
    r = formats.read_bytes(text.encode("utf-8"), "x.srt")
    out = C.drop_cues(r, [r.cues[1]], formatter=formats.formatter_for(r),
                      shift=0.0)
    assert "42" in out, "a line of cue TEXT was deleted: %r" % out
    assert "SPONSOR" not in out and "third" in out


def test_a_CR_ONLY_file_REFUSES_rather_than_silently_doing_nothing():
    u"""🚨 Classic-Mac line endings, which `06-edge-cases.md` §6.3 requires to
    survive. Every `block_span` came back `(0, 0)`, so a middle removal was a
    **no-op that was still counted and reported**, and a last-cue removal
    erased the file. ⭐ `None` — *cannot be located* — is the honest answer."""
    text = (u"1\r00:00:01,000 --> 00:00:02,000\rfirst\r\r"
            u"2\r00:00:03,000 --> 00:00:04,000\rSPONSOR\r")
    r = formats.read_bytes(text.encode("utf-8"), "x.srt")
    assert r.ok and len(r.cues) == 2, r
    assert r.cues[0].block_span is None
    with pytest.raises(RewriteRefused):
        C.drop_cues(r, [r.cues[1]], formatter=formats.formatter_for(r),
                    shift=0.0)


def test_dropping_EVERY_cue_is_refused_rather_than_writing_an_empty_file(tmp_path):
    u"""🚨 `LEDGER.md` §Delivery's *346-cue file with 0 cues*, through a
    different door: the write is perfectly atomic — it atomically writes
    nothing. An in-place retime where every cue fell inside the removed
    stretch reported `ok=True` with a cheerful note about how many it dropped.
    ⭐ The zero-cue refusal existed on the INPUT side; this is the same refusal
    on the OUTPUT side, which is where it was missing."""
    path = tmp_path / "Show - 01.ja.srt"
    write_srt(str(path), [(224, 226, u"a"), (226, 228, u"b"), (228, 230, u"c")])
    before = path.read_text(encoding="utf-8")

    report = A.apply_plan(D.plan(u"Show - 01", [a_candidate(str(path), CUT)]),
                          str(tmp_path / D.TRASH_DIR), dry_run=False)
    assert report.errors, "an empty subtitle was written"
    assert "EMPTY" in report.errors[0][1]
    assert path.read_text(encoding="utf-8") == before, "the source was emptied"


def test_a_BYSTANDER_file_at_the_target_is_never_destroyed(tmp_path):
    u"""🚨 `os.replace` obliterates whatever is already there — a hand-corrected
    subtitle, a previous run's output, anything created since discovery. It is
    not in `plan.superseded`, so the written-over guard never saw it, and with
    `--out` the plan cannot know what is in the destination at all."""
    source = tmp_path / "src"
    source.mkdir()
    winner = source / "[Erai] Show - 01.ja.srt"
    write_srt(str(winner), [(10, 12, u"new")])

    out = tmp_path / "out"
    out.mkdir()
    bystander = out / "Show - 01.ja.srt"
    bystander.write_text(u"PRECIOUS HAND-CORRECTED WORK", encoding="utf-8")

    report = A.apply_plan(D.plan(u"Show - 01", [a_candidate(str(winner))]),
                          str(tmp_path / D.TRASH_DIR), out_dir=str(out),
                          dry_run=False)
    assert bystander.read_text(encoding="utf-8") == u"PRECIOUS HAND-CORRECTED WORK"
    assert report.errors, "a bystander was overwritten with no error"


def test_our_OWN_previous_output_is_still_overwritten(tmp_path):
    u"""The control. A re-run must overwrite what it wrote last time, or the
    check above has made the tool unable to work twice."""
    path = tmp_path / "Show - 01.ja.srt"
    write_srt(str(path), [(10, 12, u"x")])
    report = A.apply_plan(D.plan(u"Show - 01", [a_candidate(str(path))]),
                          str(tmp_path / D.TRASH_DIR), dry_run=False)
    assert report.ok, report.errors
    assert report.written


def test_a_cue_STRADDLING_the_break_is_never_written_inverted(tmp_path):
    u"""🚨 `retime` maps start and end independently, so a line of dialogue
    running into a commercial break lost the whole jump from its duration and
    came out `00:03:41,400 --> 00:03:33,175`. tsubasa's own parser flags it on
    re-read; nothing flagged it on the way out.
    ⭐ The cue belongs to the moment it STARTS, so both ends take that
    segment's offset and the duration is preserved."""
    path = tmp_path / "Show - 01.ja.srt"
    write_srt(str(path), [(10, 12, u"early"), (221, 223, u"straddles"),
                          (300, 302, u"late")])
    A.apply_plan(D.plan(u"Show - 01", [a_candidate(str(path), CUT, cues=3)]),
                 str(tmp_path / D.TRASH_DIR), dry_run=False)

    written = formats.read_file(str(tmp_path / "Show - 01.ja.srt"))
    assert written.ok, written
    assert not written.warnings, written.warnings
    inverted = [c.index for c in written.cues if c.end < c.start]
    assert inverted == [], "cues written end-before-start: %s" % inverted
    straddler = [c for c in written.cues if u"straddles" in c.text][0]
    assert abs(straddler.duration - 2.0) < 1e-6, straddler.duration


def test_a_write_FAILURE_is_recorded_and_the_folder_continues(tmp_path,
                                                              monkeypatch):
    u"""⚠ The write sat OUTSIDE the try, so a failing write raised straight out
    of `apply_plan` — discarding the report and abandoning every pair after it,
    against this function's own promise and §7's per-pair atomicity.

    🚨 THE FIRST VERSION OF THIS PUT A DIRECTORY AT THE TARGET, and the
    bystander guard added in the same pass caught that FIRST — so the write was
    never attempted and a mutation removing this `try` survived. The check
    passed for a reason its name does not describe. Fail the write itself.
    """
    path = tmp_path / "Show - 01.ja.srt"
    write_srt(str(path), [(10, 12, u"x")])

    def refuse(_target, _data):
        raise OSError(13, "Permission denied")

    monkeypatch.setattr(A.formats, "write_file", refuse)
    report = A.apply_plan(D.plan(u"Show - 01", [a_candidate(str(path))]),
                          str(tmp_path / D.TRASH_DIR), dry_run=False)
    assert report.errors and not report.written
    assert "could not write" in report.errors[0][1]


def test_a_DIRECTORY_at_the_target_is_caught_before_the_write(tmp_path):
    u"""The other half, now that the two are distinguishable: a directory
    sitting where the output goes is a bystander, and it is refused without
    ever attempting a write."""
    path = tmp_path / "Show - 01.ja.srt"
    write_srt(str(path), [(10, 12, u"x")])
    (tmp_path / "blocked").mkdir()
    (tmp_path / "blocked" / "Show - 01.ja.srt").mkdir()

    report = A.apply_plan(D.plan(u"Show - 01", [a_candidate(str(path))]),
                          str(tmp_path / D.TRASH_DIR),
                          out_dir=str(tmp_path / "blocked"), dry_run=False)
    assert report.errors and not report.written
    assert "already exists" in report.errors[0][1]


def test_a_REFUSING_system_trash_still_completes_the_run_through_the_local_one(
        tmp_path):
    u"""⭐ 0.1.2. `send2trash` raises `OSError(32)` on a file Windows has
    locked. Before 0.1.2 that was recorded as an error and the loser was LEFT
    beside the winner — safe, and half-done. It now goes to the local trash,
    and the report says which trash it went to."""
    winner = tmp_path / "Show - 01.ja.srt"
    loser = tmp_path / "[Other] Show - 01.ja.srt"
    write_srt(str(winner), [(10, 12, u"a"), (20, 22, u"b")])
    write_srt(str(loser), [(10, 12, u"c")])
    trash_root = tmp_path / D.TRASH_DIR

    def locked(_path):
        raise OSError(32, "The process cannot access the file")

    report = A.apply_plan(
        D.plan(u"Show - 01", [a_candidate(str(winner), cues=2),
                              a_candidate(str(loser), cues=1)]),
        str(trash_root), dry_run=False, sender=locked)

    assert report.written, u"the write was lost"
    assert not report.errors, report.errors
    assert not loser.exists(), u"the superseded file was left beside the winner"
    assert (trash_root / loser.name).exists(), u"and it is not in the local trash"
    assert any(u"refused" in n and u"instead" in n for n in report.notes), \
        report.notes


def test_a_TRASH_failure_is_recorded_and_does_not_lose_the_write(tmp_path):
    u"""⚠ THE ORIGINAL GUARANTEE, NOW WHERE IT STILL APPLIES: when the system
    trash refuses AND the local fallback cannot be made either. `send2trash`
    once raised `OSError(32)` AFTER a successful write and threw away the report
    recording it. `doctrine/robustness`: an outbound side effect must never fail
    the operation that caused it."""
    winner = tmp_path / "Show - 01.ja.srt"
    loser = tmp_path / "[Other] Show - 01.ja.srt"
    write_srt(str(winner), [(10, 12, u"a"), (20, 22, u"b")])
    write_srt(str(loser), [(10, 12, u"c")])
    # ⚠ A FILE where the trash directory should go, so the fallback's
    # `makedirs` fails as well — the one case left with nowhere to put it.
    blocked = tmp_path / "not-a-directory"
    blocked.write_text(u"x", encoding="utf-8")

    def explode(_path):
        raise OSError(32, "The process cannot access the file")

    report = A.apply_plan(
        D.plan(u"Show - 01", [a_candidate(str(winner), cues=2),
                              a_candidate(str(loser), cues=1)]),
        str(blocked / D.TRASH_DIR), dry_run=False, sender=explode)
    assert report.written, "the successful write was lost with the exception"
    assert report.errors and "still where it was" in report.errors[0][1]
    assert loser.exists()


def test_apply_refuses_a_candidate_whose_verdict_is_not_CONFIDENT(tmp_path):
    u"""🚨 `dedupe.plan()` gates on `confident`, but `apply_plan` is a public
    function and this is the module that touches user files. Handed a plan
    carrying a REFUSED candidate it wrote with a +99 s offset and no error —
    the shape `05-interface.md` calls *the one command capable of producing a
    confidently wrong file*."""
    path = tmp_path / "Show.ja.srt"
    write_srt(str(path), [(10, 12, u"a"), (20, 22, u"b")])
    before = path.read_text(encoding="utf-8")

    refused = a_candidate(str(path), cues=2)
    refused.verdict = V.Verdict(V.REFUSED, u"not a match",
                                segments=[(None, 99.0)])
    plan = D.DedupePlan(u"Show", u"ja", winner=refused,
                        writes=[(refused, u"Show.ja.srt")])

    report = A.apply_plan(plan, str(tmp_path / D.TRASH_DIR), dry_run=False)
    assert not report.written and report.errors
    assert path.read_text(encoding="utf-8") == before


def test_force_overrides_a_REFUSAL_and_says_so(tmp_path):
    path = tmp_path / "Show.ja.srt"
    write_srt(str(path), [(10, 12, u"a"), (20, 22, u"b")])
    refused = a_candidate(str(path), cues=2)
    refused.verdict = V.Verdict(V.REFUSED, u"not a match",
                                segments=[(None, 1.0)])
    plan = D.DedupePlan(u"Show", u"ja", winner=refused,
                        writes=[(refused, u"Show.ja.srt")])

    report = A.apply_plan(plan, str(tmp_path / D.TRASH_DIR), dry_run=False,
                          force=True)
    assert report.written
    assert any("UNDER FORCE" in n for n in report.notes), report.notes


def test_force_does_NOT_override_an_ERROR(tmp_path):
    u"""⛔ Ruled 2026-09-08 and mirrored from A11: ERROR means unmeasured, so
    there is no offset to stand behind."""
    path = tmp_path / "Show.ja.srt"
    write_srt(str(path), [(10, 12, u"a"), (20, 22, u"b")])
    broken = a_candidate(str(path), cues=2)
    broken.verdict = V.Verdict(V.ERROR, u"could not be measured")
    plan = D.DedupePlan(u"Show", u"ja", winner=broken,
                        writes=[(broken, u"Show.ja.srt")])

    report = A.apply_plan(plan, str(tmp_path / D.TRASH_DIR), dry_run=False,
                          force=True)
    assert not report.written
    assert "--force overrides a refusal" in report.errors[0][1]


def test_apply_plan_has_no_DEAD_parameters():
    u"""⚠ `keep_all` was declared and never read — a flag that reads as
    accepted and does nothing, which is `LEDGER.md` §Delivery's
    *`apply --in-place` did nothing* exactly. `--keep-all` is `dedupe.plan()`'s
    decision and the plan already encodes it."""
    import inspect
    names = set(inspect.signature(A.apply_plan).parameters)
    assert "keep_all" not in names, names
    source = inspect.getsource(A.apply_plan)
    for name in names - {"plan"}:
        assert source.count(name) > 1, (
            "%r appears once in apply_plan, so it is declared and never read"
            % name)


def test_a_malformed_segment_list_RAISES_rather_than_discarding_the_rest():
    u"""🚨 `split=None` marks the LAST segment. One in the middle used to be
    `continue`d, silently discarding every later segment and giving the whole
    file the first offset."""
    with pytest.raises(ValueError) as e:
        AL.subtitle_boundaries([(None, 1.0), (None, 2.0), (None, 3.0)])
    assert "malformed" in str(e.value)
    assert AL.subtitle_boundaries([(100.0, 1.0), (None, 2.0)])


def test_the_mapper_is_NOT_monotonic_across_a_removed_stretch():
    u"""⚠ Its docstring claimed it was, and that was measured false. The claim
    mattered: a caller trusting it would skip `removed_spans()` and write an
    out-of-order file. ⭐ Not a defect in the mapper — it is the removed
    stretch, and it is exactly why `D9` exists."""
    segments = [(100.0, +10.0), (None, 0.0)]
    m = AL.mapper_for(segments)
    assert m(89.9) > m(90.0), (m(89.9), m(90.0))
    assert AL.is_removed(segments, 90.0), (
        "the non-monotonic input must be inside a removed span, or D9 would "
        "not drop it and the file really would go out of order")


def test_apply_owns_no_deletion_primitive():
    u"""The same structural guard `dedupe` carries, applied to the module that
    actually performs the plan."""
    import ast
    with open(os.path.join(ROOT, "tsubasa", "apply.py"), encoding="utf-8") as h:
        tree = ast.parse(h.read())
    called = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            called.add(node.func.attr)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            called.add(node.func.id)
    assert called, "the AST walk found no calls -- it is not looking"
    for primitive in D.DELETION_PRIMITIVES:
        assert primitive not in called, (
            "apply.py calls %r; the losers go to TRASH" % primitive)


# ---------------------------------------------------------------------------
# 🚨 REAL DATA -- the zero case over files written by strangers
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def real_subtitles():
    u"""A sample of real corpus subtitles in the writable formats."""
    from tsubasa.dev import corpus as C
    cfg = load_config(ROOT)
    root = corpus_root(cfg, ROOT)
    if not os.path.isdir(root):
        pytest.skip("SKIPPED, NOT PASSED: corpus absent on this machine")
    try:
        shows = C.shows("dev", scope="naming", cfg=cfg, start=ROOT)
    except Exception as exc:
        pytest.skip("SKIPPED, NOT PASSED: %s" % exc)

    out = []
    for show in shows:
        folder = os.path.join(root, "naming", show)
        if not os.path.isdir(folder):
            continue
        for entry in sorted(os.listdir(folder)):
            if os.path.splitext(entry)[1].lower() in (".srt", ".ass", ".ssa",
                                                      ".vtt"):
                out.append(os.path.join(folder, entry))
        if len(out) >= 120:
            break
    if len(out) < 40:
        pytest.skip("SKIPPED, NOT PASSED: only %d real subtitles" % len(out))
    return out


def test_a_zero_shift_on_REAL_files_is_byte_identical(real_subtitles):
    u"""⭐ The fixtures above were written by whoever wrote the parser. These
    were written by hundreds of strangers over twenty years, and the whitelist
    has to hold against both."""
    checked = 0
    for path in real_subtitles:
        result = formats.read_file(path)
        if not result.ok or not result.cues:
            continue
        out = C.drop_cues(result, [], formatter=formats.formatter_for(result),
                        shift=0.0)
        assert out == result.text, "a zero shift changed %s" % path
        checked += 1
    assert checked >= 30, "only %d real files were exercised" % checked


def test_every_real_cue_reports_where_its_BLOCK_lives(real_subtitles):
    u"""⚠ A parser that returned `None` here would make every removal refuse,
    which is safe but useless -- and no other check would notice, because
    refusing is a legitimate answer."""
    missing, seen = [], 0
    for path in real_subtitles:
        result = formats.read_file(path)
        if not result.ok:
            continue
        for cue in result.cues:
            seen += 1
            if cue.block_span is None:
                missing.append(path)
                break
    assert seen > 1000, "only %d real cues were examined" % seen
    assert not missing, missing[:5]


def test_a_real_block_span_CONTAINS_its_own_timestamps(real_subtitles):
    u"""The span is only useful if it is the right span. A block that does not
    enclose its own timing line would remove the wrong text -- and every check
    above would still pass, because they use fixtures the parser agrees with."""
    checked = 0
    for path in real_subtitles:
        result = formats.read_file(path)
        if not result.ok:
            continue
        for cue in result.cues:
            if cue.block_span is None or cue.start_span is None:
                continue
            lo, hi = cue.block_span
            assert lo <= cue.start_span[0] and cue.end_span[1] <= hi, (
                path, cue.index, cue.block_span, cue.start_span)
            checked += 1
    assert checked > 1000, "only %d spans were checked" % checked
