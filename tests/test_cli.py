# -*- coding: utf-8 -*-
u"""
The command line. RUNBOOK step 3c. Authority: `05-interface.md` §*The CLI
output — RULED, do not redesign*, `LEDGER.md` §Interface.

===========================================================================
🚨 THE THREE CLAIMS THAT CARRY THIS FILE
===========================================================================

  1. **Refusals and errors are printed FIRST.** `05-interface.md`: *the one
     thing needing attention must not sit below 23 successes.* ⭐ Asserted by
     LINE INDEX on a mixed report, not by reading the source for a `sort`.
  2. ⛔ **No positive word precedes a problem.** `LEDGER.md` §Interface: a GUI
     painted a run containing refusals green because *"11 confident, 1
     refused"* contains the word `confident`. The summary is
     `SyncReport.summary()` — checked where it lives — and this file asserts
     the CLI does not put anything in front of it.
  3. ⛔ **The CLI decides nothing.** Every word, number and reason on screen
     came from a `Result`. Asserted by feeding a `Result` a value and
     requiring that value back verbatim, so a CLI that recomputed anything
     would have to reproduce it exactly to stay green.

⚠ AND THE COLUMNS ARE MEASURED IN CELLS, NOT CHARACTERS. `05-interface.md`'s
own worked example is `片田舎のおっさん S02E01.ass`; a CJK character takes two
of them. A suite built only from ASCII fixtures cannot see the misalignment
that produces, which is why every layout check here has a Japanese twin.

⚠ THE END-TO-END CHECKS drive `main()` over a real synthetic Matroska with a
real subtitle beside it, because the ruled output is a claim about what a
person sees after a real run — not about a formatter.
"""
import io
import json
import os
import sys
import unicodedata

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from tsubasa import api as API                                # noqa: E402
from tsubasa import cli as CLI                                # noqa: E402
from tsubasa import pipeline as PIPE                          # noqa: E402
from tsubasa.verdict import CONFIDENT, ERROR, REFUSED         # noqa: E402

# ⭐ REUSED, NOT REBUILT. `doctrine/tooling` §anti-rederivation.
from test_pipeline import (                                   # noqa: E402
    MKV_CUES, RUNTIME, _shifted, _srt, _tree, _write, _write_mkv, CUE_STARTS,
)


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------

def a_result(outcome=CONFIDENT, video=u"/lib/Show S01E01.mkv",
             subtitle=u"/lib/[Grp] Show - 01.ja.srt", **kw):
    u"""A `Result` with the invariants satisfied. ⚠ Built through the real
    constructor, which raises on a refusal carrying a confidence word and on a
    CONFIDENT with none — so a fixture that drifts fails loudly here rather
    than rendering something impossible."""
    fields = dict(reason=u"", segments=[(None, -2.0)], match_rate=0.96,
                  excess_over_chance=4.3, raw_excess=4.3, episode=1,
                  verdict_word=u"locked", runtime_check=u"held")
    if outcome != CONFIDENT:
        fields.update(verdict_word=None, reason=u"measured, and not a match")
    fields.update(kw)
    return API.Result(video, subtitle, outcome, **fields)


def a_report(results, **kw):
    return PIPE.SyncReport(results, **kw)


def render(report, **kw):
    return CLI.render(report, **kw)


def one_episode(folder, stem=u"Show S01E01", delay=2.0, sub_name=None):
    folder = str(folder)
    if not os.path.isdir(folder):
        os.makedirs(folder)
    video = os.path.join(folder, stem + u".mkv")
    _write_mkv(video, MKV_CUES, duration_s=RUNTIME, per_cluster=4)
    sub = _write(os.path.join(folder, sub_name or (u"[Grp] %s.ja.srt" % stem)),
                 _shifted(delay))
    return video, sub


class Stream(object):
    u"""A stand-in for stdout that keeps what was written. ⚠ It also answers
    `reconfigure` by raising `AttributeError`, which is the branch `_console_utf8`
    takes on a stream that has no such method — the real case on Python 2 and on
    a `StringIO`."""

    def __init__(self):
        self.parts = []

    def write(self, text):
        self.parts.append(text)

    @property
    def text(self):
        return u"".join(self.parts)

    @property
    def lines(self):
        return self.text.splitlines()


@pytest.fixture()
def out():
    return Stream()


@pytest.fixture()
def err():
    return Stream()


# ---------------------------------------------------------------------------
# 🚨 CLAIM 1 — refusals and errors are printed FIRST
# ---------------------------------------------------------------------------

def test_a_REFUSAL_is_printed_ABOVE_every_success():
    u"""🚨 `05-interface.md`: *the one thing needing attention must not sit
    below 23 successes.*

    ⭐ ASSERTED BY LINE INDEX, on a report whose refusal is LAST in the list.
    A check that fed them in the right order already would be green against a
    renderer that did no ordering at all.
    """
    report = a_report([a_result(subtitle=u"/lib/ok-%d.ja.srt" % i)
                       for i in range(23)]
                      + [a_result(REFUSED, subtitle=u"/lib/bad.ja.srt")])
    lines = render(report)
    where_bad = next(i for i, l in enumerate(lines) if u"bad.ja.srt" in l)
    where_good = next(i for i, l in enumerate(lines) if u"ok-0.ja.srt" in l)
    assert where_bad < where_good, u"\n".join(lines)


def test_an_ERROR_is_printed_above_every_success_too():
    u"""⚠ ERROR and REFUSED are different outcomes and this ordering is about
    *needs attention*, which both are. `03-permissions.md`: there is no fourth
    outcome, so the two together are the whole of it."""
    report = a_report([a_result(subtitle=u"/lib/ok.ja.srt"),
                       a_result(ERROR, subtitle=u"/lib/broken.ja.srt")])
    lines = render(report)
    assert (next(i for i, l in enumerate(lines) if u"broken" in l)
            < next(i for i, l in enumerate(lines) if u"ok.ja.srt" in l))


def test_the_ordering_holds_when_EVERYTHING_is_refused():
    u"""⚠ The control. A renderer that simply reversed the list would pass the
    check above and fail here."""
    report = a_report([a_result(REFUSED, subtitle=u"/lib/a.ja.srt"),
                       a_result(REFUSED, subtitle=u"/lib/b.ja.srt")])
    lines = render(report)
    assert (next(i for i, l in enumerate(lines) if u"a.ja.srt" in l)
            < next(i for i, l in enumerate(lines) if u"b.ja.srt" in l))


# ---------------------------------------------------------------------------
# ⛔ CLAIM 2 — no positive word precedes a problem
# ---------------------------------------------------------------------------

def test_the_summary_is_the_LIBRARY_S_and_nothing_is_put_in_front_of_it():
    u"""⛔ `LEDGER.md` §Interface: a GUI painted a run containing refusals green
    because *"11 confident, 1 refused"* contains the word `confident`.

    ⭐ `SyncReport.summary()` already leads with what is wrong and is checked
    where it lives. The claim HERE is that the CLI does not reimplement it and
    does not prepend anything — so the last line ends with the library's own
    sentence, verbatim.
    """
    report = a_report([a_result(), a_result(REFUSED, subtitle=u"/lib/x.srt")])
    lines = render(report)
    assert lines[-1].strip() == report.summary()


def test_the_summary_line_LEADS_with_the_refusal_even_with_an_elapsed_time():
    report = a_report([a_result(), a_result(REFUSED, subtitle=u"/lib/x.srt")])
    tail = render(report, elapsed=3.14)[-1].strip()
    assert tail.startswith(u"1 refused"), tail
    assert tail.endswith(u"3.1 s"), tail


def test_no_confidence_word_appears_on_a_REFUSED_line():
    u"""⛔ `LEDGER.md` §Interface, from the other side. A refusal carries **no
    word at all** — `Result` raises if one is set, so the renderer has nothing
    to filter; this is the check that keeps it that way.

    ⭐ AND THE STRUCTURAL HALF: a refused line never goes through `_evidence`
    at all, which is why a mutant that made `_evidence` invent a word could not
    reach it. Asserted here so the branch cannot quietly start calling it.
    """
    report = a_report([a_result(REFUSED, subtitle=u"/lib/x.srt",
                                reason=u"measured, and not a match")])
    lines = render(report)
    block = u"\n".join(lines)
    for word in (u"locked", u"strong", u"fair", u"uncertain"):
        assert word not in block, (word, block)
    # ⛔ No evidence line at all: a refusal has no match percentage to stand
    # behind, and printing one would be evidence for a claim not made.
    assert u"% match" not in block, block


# ---------------------------------------------------------------------------
# ⛔ CLAIM 3 — the CLI decides nothing
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("word", [u"locked", u"strong", u"fair", u"uncertain"])
def test_the_confidence_word_is_REPRODUCED_never_derived(word):
    u"""⛔ Every one of the four, verbatim. A CLI that recomputed the band from
    `excess_over_chance` would have to reproduce `verdict.py` exactly to stay
    green — and `05-interface.md` measured that a single threshold refuses 16%
    of correct pairs, so a second implementation is a second defect."""
    report = a_report([a_result(verdict_word=word, excess_over_chance=99.0)])
    assert word in u"\n".join(render(report))


def test_the_match_PERCENTAGE_is_the_results_own():
    u"""⚠ THE RATE IS CHOSEN SO TRUNCATION AND ROUNDING DISAGREE. At 0.913 both
    give 91 and a mutant that recomputed the percentage its own way was a
    no-op; 0.918 is 91 truncated and 92 rounded, and `Result.match_percent`
    rules that it is 92."""
    report = a_report([a_result(match_rate=0.918)])
    assert int(0.918 * 100) != int(round(0.918 * 100)), u"the fixture is blind"
    assert u"92% match" in u"\n".join(render(report))


def test_the_REASON_is_printed_verbatim_not_summarised():
    reason = (u"no subtitle track; on the audio the first 3:42 want a "
              u"different offset")
    report = a_report([a_result(REFUSED, reason=reason)])
    block = u" ".join(l.strip() for l in render(report))
    assert reason in block, block


def test_the_EPISODE_column_is_the_results_own_number():
    u"""⛔ THE NUMBER IS ON THE `Result`, and the renderer may not re-derive it.

    ⭐ Asserted by DISAGREEING WITH THE FILENAME on purpose: the video is
    `Show S01E01.mkv` and the result says episode 7. A renderer that parsed the
    name would print 01. The source-import check next door cannot see this —
    a re-parse with an already-imported `re` adds no import at all.
    """
    report = a_report([a_result(video=u"/lib/Show S01E01.mkv", episode=7)])
    line = next(l for l in render(report) if u"✓" in l)
    assert u" 07 " in line, line
    assert u" 01 " not in line, line


def test_a_result_with_NO_episode_leaves_the_column_blank():
    u"""⚠ A film has no episode, and `Result.episode` is None. Printing `00`
    would be a number nothing measured."""
    report = a_report([a_result(episode=None)])
    line = next(l for l in render(report) if u"✓" in l)
    assert u"00" not in line, line


def test_the_cli_imports_no_decision_making_module():
    u"""⛔ READ FROM THE SOURCE, because *it happens not to call one today* is a
    statement about today's code. `05-interface.md`: the library is the
    product and the CLI is a thin wrapper — the moment this file can reach a
    threshold or an aligner, there are two answers to one question."""
    import ast
    src = io.open(os.path.join(ROOT, "tsubasa", "cli.py"),
                  encoding="utf-8").read()
    imported = set()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(u".")[0])
        elif isinstance(node, ast.Import):
            imported.update(a.name.split(u".")[0] for a in node.names)
    for banned in ("align", "arbitrate", "dedupe", "duration", "cues",
                   "movies", "explicit", "sidecar", "naming"):
        assert banned not in imported, \
            u"cli.py imports %s; a decision has moved into the wrapper" % banned


# ---------------------------------------------------------------------------
# ⭐ the ruled shape — evidence, and `old → new`
# ---------------------------------------------------------------------------

def test_every_confident_line_carries_EVIDENCE_never_a_bare_tick():
    u"""`05-interface.md`: *evidence on every line — `96% match · locked`,
    never a bare tick.*"""
    report = a_report([a_result()])
    lines = render(report)
    tick = next(i for i, l in enumerate(lines) if u"✓" in l)
    evidence = lines[tick + 1]
    assert u"96% match" in evidence and u"locked" in evidence, evidence


def test_old_to_new_is_shown_when_the_name_changed():
    u"""`05-interface.md`: *the user sees what happened to their folder before
    trusting it.*"""
    report = a_report([a_result(output_path=u"/lib/Show S01E01.ja.srt")])
    line = next(l for l in render(report) if u"✓" in l)
    assert u"[Grp] Show - 01.ja.srt" in line
    assert u"→" in line and u"Show S01E01.ja.srt" in line


def test_an_IN_PLACE_retime_does_not_print_an_arrow_pointing_at_itself():
    u"""⭐ Found by LOOKING at a real run. `--no-rename` writes back over the
    subtitle's own name, and `x → x` is noise on the one line whose job is to
    say what changed."""
    same = u"/lib/[Grp] Show - 01.ja.srt"
    report = a_report([a_result(subtitle=same, output_path=same)])
    line = next(l for l in render(report) if u"✓" in l)
    assert u"→" not in line, line
    assert u"retimed in place" in line, line


def test_a_DRY_RUN_shows_no_arrow_because_nothing_moved():
    u"""⚠ `output_path` is set ONLY when a file actually moved, so a dry run
    correctly has no arrow — and `summary()` says *would sync* rather than
    *synced*, which is the other half of the same honesty.

    ⛔ AND IT MAY NOT CLAIM TO HAVE RETIMED IN PLACE EITHER. A mutant that
    substituted the SOURCE path for the missing output printed no arrow — and
    passed — while telling the user the file had been rewritten where it sat.
    Found by `probe_adj30`.
    """
    lines = render(a_report([a_result(output_path=None)]))
    block = u"\n".join(lines)
    assert u"→" not in block, block
    assert u"retimed in place" not in block, block


def test_a_CUT_file_shows_both_offsets_the_boundary_and_the_gap():
    u"""`05-interface.md`'s ruled line: `-33.07 / -42.96 @3:18   CUT 9.9s`."""
    report = a_report([a_result(segments=[(None, -33.07), (198.0, -42.96)],
                                verdict_word=u"strong", match_rate=0.91)])
    block = u"\n".join(render(report))
    assert u"-33.07 / -42.96" in block, block
    assert u"@3:18" in block, block
    assert u"CUT 9.9s" in block, block
    assert u"2 segments" in block, block
    assert u"⚑" in block, u"a cut file is not marked as one"


def test_a_D9_DROP_is_counted_on_the_result_line():
    u"""`05-interface.md`, `D9`: cues removed are *dropped, counted, and
    reported on the result line*."""
    report = a_report([a_result(dropped_in_gap=3)])
    assert u"3 cues dropped" in u"\n".join(render(report))


def test_the_drop_count_is_not_said_TWICE():
    u"""⚠ `apply` already puts a full sentence in `Result.notes` explaining what
    a dropped cue WAS, and the first version printed a count line as well — so
    the report said *"1 cue dropped"* twice in a row, once ungrammatically
    (*"1 cue ... were dropped"*). Found by looking at a real run."""
    note = u"1 cue dropped: it is timed inside a stretch this video does not have"
    report = a_report([a_result(dropped_in_gap=1, notes=[note])])
    block = u"\n".join(render(report))
    assert block.count(u"1 cue dropped") == 2, block   # the count, and the note
    assert u"were dropped" not in block, block


def test_an_offset_that_rounds_to_zero_is_never_NEGATIVE_zero():
    u"""⚠ A second run over its own output aligns at about `-1e-9`, and
    `%+.2f` renders that as `-0.00` — a small negative shift, on the line that
    means NOTHING MOVED. ⛔ `x + 0.0 or 0.0` does not fix it: that catches an
    exact `-0.0` and `-1e-9` is truthy."""
    for tiny in (-1e-9, -0.0, -0.004):
        report = a_report([a_result(segments=[(None, tiny)])])
        block = u"\n".join(render(report))
        assert u"-0.00" not in block, (tiny, block)
        assert u"+0.00s" in block, (tiny, block)


def test_SETTLED_videos_are_said_out_loud(tmp_path):
    u"""⭐ RUNBOOK 3a-bis. A run that printed nothing over a folder of finished
    episodes is indistinguishable from one that broke."""
    report = a_report([], settled=[(u"/lib/Show S01E01.mkv",
                                    u"already in sync — nothing changed")])
    lines = render(report)
    # ⛔ NOT `in the whole block`. `SyncReport.summary()` says *1 already in
    # sync* too, so a renderer that dropped the dedicated line entirely was
    # green against the summary alone. Found by `probe_adj30`.
    assert lines[-1].strip() == report.summary()
    body = [l for l in lines[:-1] if l.strip()]
    assert any(u"already in sync" in l and u"nothing to do" in l
               for l in body), u"\n".join(lines)


# ---------------------------------------------------------------------------
# ⚠ display width — every layout claim has a Japanese twin
# ---------------------------------------------------------------------------

def test_width_counts_CELLS_not_characters():
    u"""⚠ THE THREE CLASSES ARE SEPARATE, and a fixture missing one cannot see
    a rule that drops it. `LEDGER-HOT.md` records the same shape for encoding:
    *an ASCII fixture cannot test an encoding rule.*

      * `W`  — Wide: ordinary CJK, 片田舎
      * `F`  — Fullwidth: the ASCII range's double-width twins, ＳＯ２. ⛔ The
                first version had none, and a mutant that counted only `W`
                survived a check named for counting cells.
      * combining — no cell of its own
    """
    assert CLI._width(u"abc") == 3
    assert CLI._width(u"片田舎") == 6, u"Wide"
    # ⛔ FULLWIDTH LITERALS, never a format string. `u"%d" % 2` emits an ASCII
    # digit and the fixture would be half-real (`LEDGER-HOT.md`).
    assert CLI._width(u"ＳＯ２") == 6, u"Fullwidth"
    assert CLI._width(u"Ａ") == 2 and CLI._width(u"A") == 1
    assert CLI._width(u"片田舎のおっさん S02E01.ass") == 27
    # ⚠ A combining mark occupies no cell of its own.
    assert CLI._width(u"て\u3099") == 2


def _cells(text):
    u"""An INDEPENDENT width, written here on purpose.

    🚨 `LEDGER.md` trap 10: *a check whose expectation is computed by the code
    under test cannot fail.* The first version of the check below measured both
    lines with `CLI._width`, so replacing `_width` with `len` kept the two
    sides agreeing and the mutant survived — against the single most important
    layout property in this file. Found by `probe_adj30`.
    """
    wide = 0
    for ch in text:
        if unicodedata.combining(ch):
            continue
        wide += 2 if unicodedata.east_asian_width(ch) in (u"W", u"F") else 1
    return wide


def test_a_CJK_name_pads_to_the_same_column_as_an_ASCII_one():
    u"""🚨 THE DEFECT A `%-30s` FORMAT PRODUCES, and it is invisible to `len()`.
    This tool's files are mostly Japanese; a report that lines up under ASCII
    fixtures and is ragged on real data is the whole point of this check.

    ⛔ MEASURED WITH `_cells`, NOT WITH `CLI._width` — see above.
    """
    ascii_line = next(l for l in render(a_report(
        [a_result(subtitle=u"/lib/Show - 01.ja.srt",
                  output_path=u"/lib/out.ja.srt")])) if u"✓" in l)
    cjk_line = next(l for l in render(a_report(
        [a_result(subtitle=u"/lib/片田舎のおっさん S02E01.ass",
                  output_path=u"/lib/out.ja.srt")])) if u"✓" in l)
    assert _cells(ascii_line.split(u"→")[0]) == _cells(cjk_line.split(u"→")[0]), \
        u"the arrow does not land in the same column:\n%s\n%s" \
        % (ascii_line, cjk_line)


def test_a_long_name_is_clipped_from_the_MIDDLE():
    u"""⚠ A release name's distinguishing parts are its group and its episode,
    at opposite ends. Cutting the tail leaves twenty files all reading
    `[SubsPlease] Some Very Long Show Ti…`."""
    name = u"[SubsPlease] A Very Long Show Title Indeed - 07 (1080p).ja.srt"
    got = CLI._clip(name, 34)
    assert CLI._width(got) <= 34
    assert got.startswith(u"[SubsPlease]")
    assert got.endswith(u".ja.srt")


def test_clipping_a_CJK_name_never_OVERSHOOTS_the_column():
    u"""⚠ A wide character cannot be half-included. A clipper that counted
    characters would land one cell over on every odd boundary."""
    name = u"黄泉のツガイ.S01E18.風神と雷神.WEBRip.Netflix.ja[cc].srt"
    for cells in range(2, 40):
        assert CLI._width(CLI._clip(name, cells)) <= cells, cells


def test_the_header_FITS_and_keeps_the_end_of_a_long_path():
    u"""⭐ Found by looking: a real temp path pushed the counts to column 100.
    ⚠ Clipped from the LEFT here, the opposite of a filename — a path's tail is
    the part that identifies it."""
    scan = API.Scan([], [], _Candidates(), _Films(), {}, {})
    long_path = u"C:\\Users\\Someone\\AppData\\Local\\Temp\\x\\library\\Katainaka S2"
    line = CLI._header(long_path, scan)
    assert CLI._width(line) <= CLI.LINE, (CLI._width(line), line)
    assert line.rstrip().endswith(scan.summary())
    assert u"Katainaka S2" in line


class _Candidates(object):
    def for_video(self, video):
        return []


class _Films(object):
    pairs = ()
    refusals = ()


# ---------------------------------------------------------------------------
# arguments — ⛔ every refusal is a sentence, never a traceback
# ---------------------------------------------------------------------------

def test_the_flags_map_to_the_library_s_own_arguments():
    opts = CLI.parse([u"/lib", u"--subs", u"/subs", u"--out", u"/out",
                      u"--no-recurse", u"--keep-all", u"--verbose",
                      u"--dry-run", u"--json", u"--no-results"])
    assert opts[u"roots"] == [u"/lib"]
    assert opts[u"subs"] == u"/subs" and opts[u"out"] == u"/out"
    assert opts[u"recurse"] is False and opts[u"keep_all"] is True
    assert opts[u"dry_run"] and opts[u"json"] and opts[u"verbose"]
    assert opts[u"results"] is False


def test_pair_is_repeatable_and_takes_TWO_paths():
    opts = CLI.parse([u"--pair", u"a.mkv", u"a.srt",
                      u"--pair", u"b.mkv", u"b.srt"])
    assert opts[u"pairs"] == [(u"a.mkv", u"a.srt"), (u"b.mkv", u"b.srt")]


@pytest.mark.parametrize("argv,expect", [
    ([u"--pair", u"only.mkv"], u"TWO paths"),
    ([u"--subs"], u"needs a value"),
    ([u"--nonsense"], u"not an option"),
])
def test_a_command_that_cannot_be_run_is_REFUSED_in_a_sentence(argv, expect):
    u"""⛔ `03-permissions.md` §hand-back: state what was measured, why it fell
    short, and what would change it. ⚠ Never a traceback: a stack trace tells
    the user about our call stack, not about their command."""
    with pytest.raises(CLI.Usage) as caught:
        CLI.parse(argv)
    assert expect in u"%s" % caught.value


def test_a_manifest_names_the_ENTRY_that_is_wrong(tmp_path):
    u"""⛔ A manifest is typed by hand or generated by somebody else's script,
    and *"list index out of range"* three frames down says nothing about which
    line to fix."""
    bad = tmp_path / "pairs.json"
    _write(bad, u'[["a.mkv", "a.srt"], ["b.mkv"]]')
    with pytest.raises(CLI.Usage) as caught:
        CLI.parse([u"--pairs", str(bad)])
    assert u"entry 2" in u"%s" % caught.value


def test_a_manifest_that_is_not_JSON_says_so(tmp_path):
    bad = tmp_path / "pairs.json"
    _write(bad, u"not json at all")
    with pytest.raises(CLI.Usage) as caught:
        CLI.parse([u"--pairs", str(bad)])
    assert u"not valid JSON" in u"%s" % caught.value


def test_a_manifest_that_is_a_JSON_OBJECT_says_so(tmp_path):
    bad = tmp_path / "pairs.json"
    _write(bad, u'{"a.mkv": "a.srt"}')
    with pytest.raises(CLI.Usage) as caught:
        CLI.parse([u"--pairs", str(bad)])
    assert u"list of [video, subtitle]" in u"%s" % caught.value


def test_a_manifest_round_trips(tmp_path):
    good = tmp_path / "pairs.json"
    _write(good, json.dumps([["a.mkv", "a.srt"], ["b.mkv", "b.srt"]]))
    assert CLI.parse([u"--pairs", str(good)])[u"pairs"] == \
        [(u"a.mkv", u"a.srt"), (u"b.mkv", u"b.srt")]


# ---------------------------------------------------------------------------
# end to end — ⚠ over a real Matroska, because the ruled output is a claim
# about what a person sees after a real run
# ---------------------------------------------------------------------------

def test_a_real_run_writes_and_reports_it(tmp_path, out, err, monkeypatch):
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    monkeypatch.setenv("TSUBASA_CACHE", str(tmp_path / "store"))
    folder = tmp_path / "Show S01"
    one_episode(folder)

    code = CLI.main([str(folder)], out=out, err=err)
    assert code == 0, out.text + err.text
    assert os.path.isfile(str(folder / "Show S01E01.ja.srt"))
    assert u"1 synced" in out.text, out.text
    assert u"→" in out.text


def test_a_DRY_RUN_moves_NOT_ONE_BYTE(tmp_path, out, err, monkeypatch):
    u"""⛔ HASHED, NOT LISTED. `05-interface.md`: *every intended action
    printed, nothing written, nothing trashed.* ⚠ `LEDGER-HOT.md` trap 0d — a
    retime is length-preserving, so a name-and-size snapshot is blind to it."""
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    monkeypatch.setenv("TSUBASA_CACHE", str(tmp_path / "store"))
    folder = tmp_path / "Show S01"
    one_episode(folder)
    before = _tree(str(tmp_path))

    code = CLI.main([str(folder), u"--dry-run"], out=out, err=err)
    assert code == 0, out.text + err.text
    assert _tree(str(tmp_path)) == before
    assert u"would sync" in out.text, out.text


def test_a_REFUSAL_exits_NON_ZERO(tmp_path, out, err, monkeypatch):
    u"""🚨 The whole point of the tool is that it declines to produce a
    confidently wrong file. A script piping this into something else has to be
    able to tell."""
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    monkeypatch.setenv("TSUBASA_CACHE", str(tmp_path / "store"))
    folder = tmp_path / "Show S01"
    video, _sub = one_episode(folder)
    wrong = _write(folder / "wrong.srt",
                   _srt([3.3 + 7.8 * i for i in range(180)]))

    code = CLI.main([u"--pair", video, wrong], out=out, err=err)
    assert code == 1, out.text
    assert u"✗" in out.text and u"REFUSED" in out.text


def test_a_CONTRADICTORY_pair_of_flags_exits_2_with_the_librarys_sentence(
        tmp_path, out, err, monkeypatch):
    u"""⭐ `sync()` refuses `--out` with `--no-rename` by raising, in a sentence
    written for a person. Printing that is better than re-deriving the rule
    here and letting the two drift."""
    monkeypatch.setenv("TSUBASA_CACHE", str(tmp_path / "store"))
    folder = tmp_path / "Show S01"
    one_episode(folder)
    code = CLI.main([str(folder), u"--out", str(tmp_path / "o"),
                     u"--no-rename"], out=out, err=err)
    assert code == 2
    assert u"contradict" in err.text, err.text
    assert u"Traceback" not in err.text


def test_force_on_a_SCAN_exits_2_rather_than_silently_ignoring_it(
        tmp_path, out, err, monkeypatch):
    monkeypatch.setenv("TSUBASA_CACHE", str(tmp_path / "store"))
    folder = tmp_path / "Show S01"
    one_episode(folder)
    code = CLI.main([str(folder), u"--force"], out=out, err=err)
    assert code == 2
    assert u"explicit pairs only" in err.text, err.text


def test_a_folder_AND_explicit_pairs_together_is_refused(tmp_path, out, err):
    code = CLI.main([u"/lib", u"--pair", u"a.mkv", u"a.srt"], out=out, err=err)
    assert code == 2
    assert u"not both" in err.text, err.text


def test_no_arguments_prints_the_usage_and_exits_2(out, err):
    assert CLI.main([], out=out, err=err) == 2
    assert u"tsubasa <folder>" in err.text


def test_help_prints_the_usage_and_exits_0(out, err):
    assert CLI.main([u"--help"], out=out, err=err) == 0
    assert u"tsubasa <folder>" in out.text
    # ⚠ Every flag the parser accepts is in the help. A flag nobody can find is
    # a flag that does not exist.
    for flag in (u"--subs", u"--out", u"--no-recurse", u"--no-rename",
                 u"--keep-all", u"--pair", u"--pairs", u"--force",
                 u"--dry-run", u"--json", u"--verbose", u"--no-results"):
        assert flag in out.text, flag


# ---------------------------------------------------------------------------
# --json
# ---------------------------------------------------------------------------

def test_json_is_one_valid_object_per_result(tmp_path, out, err, monkeypatch):
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    monkeypatch.setenv("TSUBASA_CACHE", str(tmp_path / "store"))
    folder = tmp_path / "Show S01"
    one_episode(folder)

    code = CLI.main([str(folder), u"--json"], out=out, err=err)
    assert code == 0, err.text
    rows = [json.loads(line) for line in out.lines if line.strip()]
    assert len(rows) == 1
    row = rows[0]
    assert row[u"outcome"] == CONFIDENT
    assert row[u"verdict_word"] == u"locked"
    # ⚠ The raw multiple belongs HERE and never in the default output.
    assert u"raw_excess" in row and u"excess_over_chance" in row
    assert row[u"output_path"].endswith(u"Show S01E01.ja.srt")


def test_json_carries_EVERY_field_Result_carries():
    u"""🚨 `05-interface.md`: *the same structure the library returns.* ⭐ Read
    off `Result.__slots__`, so a field added there and forgotten here fails —
    which is the whole risk, since `Result`'s shape is a compatibility promise
    to hato and fields are *added, never renamed*."""
    row = CLI.as_json(a_result())
    for field in API.Result.__slots__:
        assert field in row, u"--json drops Result.%s" % field


def test_json_is_NEVER_SILENT_over_a_settled_library(tmp_path, out, err,
                                                     monkeypatch):
    u"""⛔ Found by looking. A settled library produces no `Result` at all, so
    `--json` printed nothing and exited 0 — exactly what a broken run looks
    like. The summary goes to STDERR so a pipe stays pure NDJSON."""
    monkeypatch.setenv("TSUBASA_NO_OS_TRASH", "1")
    monkeypatch.setenv("TSUBASA_CACHE", str(tmp_path / "store"))
    folder = tmp_path / "Show S01"
    one_episode(folder)
    for _ in range(3):
        CLI.main([str(folder)], out=Stream(), err=Stream())

    code = CLI.main([str(folder), u"--json"], out=out, err=err)
    assert code == 0
    assert out.text.strip() == u"", u"stdout should be pure NDJSON: %r" % out.text
    assert u"already in sync" in err.text, err.text


def test_verbose_puts_the_raw_multiple_on_its_OWN_line():
    u"""⚠ Appended to the evidence line first, and measured at over 150 cells on
    a real run — past the edge of every terminal, so the part a bug report needs
    was the part that scrolled off."""
    report = a_report([a_result(raw_excess=4.33, cluster_coherence=1.0,
                                reference=u"track 0 (S_TEXT/ASS, jpn)")])
    plain = u"\n".join(render(report))
    loud = u"\n".join(render(report, verbose=True))
    assert u"4.33× chance" not in plain
    assert u"4.33× chance" in loud
    for line in loud.splitlines():
        assert CLI._width(line) <= 100, (CLI._width(line), line)
